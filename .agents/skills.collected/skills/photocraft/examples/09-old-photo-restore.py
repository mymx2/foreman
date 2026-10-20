#!/usr/bin/env python3
"""场景：翻拍的老照片发黄、有灰尘白点和划痕、暗部糊成一团。修复后交付棕褐色调成片，另出一版双色调给印刷。

要点：大幅调色前先转 16 位避免断层；去尘用"蒙尘与划痕"的阈值保住细节；每道划痕用一次 paint.spotHealing，
points 就是沿划痕的折线（一次调用 = 一笔连续笔画）；交付前再转回 8 位。

演示模式先把肖像"做旧"成一张受损照片（灰尘点和划痕位置已知，质检按这些位置核对）；
用户模式只做通用修复，划痕要自己给出折线坐标（预览图上目测）。

用法: python 09-old-photo-restore.py [老照片 ["x1,y1 x2,y2 …" …]]     每个引号里是一道划痕
"""
from __future__ import annotations

import math
import re
import shutil
from pathlib import Path

from pcx import *


def dust_points():
    """固定种子的伪随机灰尘位置（演示模式做旧和质检共用）。"""
    s = 42
    out = []
    for _ in range(28):
        s = (s * 1103515245 + 12345) % 2147483648
        x = round(40 + s / 2147483648 * 640)
        s = (s * 1103515245 + 12345) % 2147483648
        y = round(40 + s / 2147483648 * 770)
        s = (s * 1103515245 + 12345) % 2147483648
        d = 2 + round(s / 2147483648 * 3)
        out.append((x, y, d))
    return out


def parse_line(text):
    pts = [tuple(int(v) for v in part.split(",")) for part in text.split()]
    if len(pts) < 2:
        raise ValueError(f"a scratch needs at least two points \"x1,y1 x2,y2\" (got '{text}')")
    return pts


def main(args):
    src = pcx_input(args[0] if args else "", "", kind="file")
    scratches = [parse_line(t) for t in args[1:]]
    pcx_init("09-old-photo-restore")

    if user_mode():
        shutil.copy2(src, "damaged.jpg")
    else:
        step("做旧：去色 → 发黄 → 压低反差 → 颗粒 → 28 个白色灰尘点 → 两道划痕")
        scratches = [parse_line("120,60 180,420 230,810"), parse_line("600,90 560,500")]
        dots = [("paint.stroke", {"points": [[x, y, 1]], "size": d, "hardness": 1, "color": "#f4efe2"})
                for x, y, d in dust_points()]
        for line in scratches:
            dots.append(("paint.stroke", {"points": [list(p) + [1] for p in line], "size": 2,
                                          "hardness": 1, "color": "#efe8d8"}))
        pc_run([
            ("image.adjustments.desaturate",),
            ("image.adjustments.photoFilter", {"filter": "sepia", "density": 70}),
            ("image.adjustments.levels", {"outBlack": 46, "outWhite": 214}),
            ("filter.noise.addNoise", {"amount": 6, "distribution": "gaussian", "monochromatic": True, "seed": 3}),
            *dots,
        ], input=str(fixture("portrait.jpg")), out="damaged.jpg", extra=("--quality", "90"), check=True)

    step("修复：16 位 → 去尘 → 沿每道划痕污点修复 → 降噪 → 提亮暗部 → 色阶拉开反差")
    heal = [("paint.spotHealing", {"points": [list(p) + [1] for p in line], "size": 9, "type": "contentAware"})
            for line in scratches]
    if not scratches:
        note("no scratch polylines given: skipping the healing strokes")
    pc_run([
        ("image.mode.bits16",),
        ("filter.noise.dustAndScratches", {"radius": 3, "threshold": 22}),
        *heal,
        ("filter.noise.reduceNoise", {"strength": 5, "preserveDetails": 60, "reduceColorNoise": 70,
                                      "sharpenDetails": 20}),
        ("image.adjustments.shadowsHighlights", {"shadowAmount": 28, "shadowRadius": 40, "highlightAmount": 8}),
        ("image.adjustments.levels", {"inBlack": 40, "inWhite": 222, "gamma": 1.05}),
    ], input="damaged.jpg", out="restored-16bit.tif", check=True)
    expect("restored-16bit.tif", lambda k: k.depth == 16, "working master kept at 16 bits per channel")

    step("成片：黑白（偏红通道提亮肤色）+ 棕褐色调，转回 8 位导出")
    pc_run([
        ("image.adjustments.blackWhite", {"reds": 60, "yellows": 70, "tint": True, "tintColor": "#a2865c"}),
        ("image.mode.bits8",),
    ], input="restored-16bit.tif", out="restored-sepia.jpg", extra=("--quality", "92"), check=True)

    step("印刷版：灰度 → 双色调（黑 + 暖棕）。当前版本只有 .pcraft 能保存双色调，PSD 会写成灰度并给 warning")
    pc_run([
        ("image.mode.bits8",),
        ("image.mode.grayscale",),
        ("image.mode.duotone", {"type": "duotone", "inks": [
            {"name": "Black", "color": "#1a1a1a", "curve": [[0, 0], [100, 100]]},
            {"name": "Warm Brown", "color": "#8a5a2b", "curve": [[0, 0], [50, 38], [100, 70]]}]}),
    ], input="restored-16bit.tif", out="restored-duotone.pcraft", check=True)

    step("核对：交付文件位深与模式；划痕处的亮线变淡；（演示）灰尘点普遍变暗")
    expect("restored-sepia.jpg", lambda k: k.depth == 8, "delivery JPEG is 8-bit")
    expect("restored-duotone.pcraft", lambda k: k.mode == "Duotone", "print master keeps duotone inks (.pcraft)")
    pcx_ppm("damaged.jpg", "before.ppm")
    pcx_ppm("restored-16bit.tif", "after.ppm")
    before, after = Img("before.ppm"), Img("after.ppm")

    if scratches:
        bad = 0
        for line in scratches:
            a = _line_contrast(before, line)
            b = _line_contrast(after, line)
            good = b < a * 0.6
            note(("ok  " if good else "BAD ") + "scratch %s: line contrast %.3f -> %.3f"
                 % (" ".join("%d,%d" % p for p in line), a, b))
            bad += not good
        if bad:
            fail("a scratch is still visible")

    if demo_only("dust specks darkened (positions of the synthetic damage)"):
        rows = dust_points()
        fixed = sum(1 for x, y, d in rows if luma(before.px(x, y)) - luma(after.px(x, y)) >= 0.15)
        note("%d/%d dust specks darkened by >= 0.15" % (fixed, len(rows)))
        if fixed / len(rows) < 0.75:
            fail("too many dust specks remain")
    for p in Path(".").glob("*.ppm"):
        p.unlink()


def _line_contrast(im, pts):
    vals = []
    for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
        L = math.hypot(x1 - x0, y1 - y0)
        nx, ny = -(y1 - y0) / L, (x1 - x0) / L
        for k in range(1, 10):
            x, y = x0 + (x1 - x0) * k / 10, y0 + (y1 - y0) * k / 10
            on = luma(im.px(round(x), round(y)))
            side = [luma(im.px(round(x + nx * d), round(y + ny * d))) for d in (-6, 6)]
            vals.append(abs(on - sum(side) / 2))
    return sum(vals) / len(vals)


run(main)
