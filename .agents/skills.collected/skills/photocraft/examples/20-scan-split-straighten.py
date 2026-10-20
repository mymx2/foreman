#!/usr/bin/env python3
"""场景一：一次扫描了三张老照片，要拆成三张单独的、摆正的图。照片之间要留缝、和扫描底板要有反差，否则会被识别成一张。
场景二：随手拍的风景地平线歪了 3°，用带角度的裁切一步拉直并裁掉旋转露出的空角。

要点：image.crop 的 angle 与 image.rotation.arbitrary 的倾斜角同号——顺时针歪了 3°，就用 angle:3 拉回。

用法: python 20-scan-split-straighten.py [扫描件]
"""
from __future__ import annotations

import math
import shutil
from pathlib import Path

from pcx import *


def main(args):
    scan = pcx_input(args[0] if args else "", "", kind="file")
    pcx_init("20-scan-split-straighten")

    if scan is not None:
        shutil.copy2(scan, "scan.jpg")
    else:
        step("合成一张扫描件：浅色底板上三张倾斜的照片（-7°、4°、-12°）")
        p = pcx_native(fixture("portrait.jpg"))
        l = pcx_native(fixture("landscape.jpg"))
        pc_run([
            ("file.placeEmbedded", {"path": p, "scale": 55, "center": [340, 420]}),
            ("edit.transform", {"rotate": -7}),
            ("file.placeEmbedded", {"path": l, "scale": 55, "center": [1150, 470]}),
            ("edit.transform", {"rotate": 4}),
            ("file.placeEmbedded", {"path": p, "scale": 80, "center": [860, 1500]}),
            ("edit.transform", {"rotate": -12}),
            ("layer.flattenImage",),
            ("filter.noise.addNoise", {"amount": 2, "monochromatic": True, "seed": 5}),
        ], new={"width": 1700, "height": 2200, "background": "#f7f7f4", "resolution": 200, "name": "scan"},
            out="scan.jpg", extra=("--quality", "92"), check=True)

    step("识别照片：每张照片成为一个新文档（第 0 个是扫描件本身）")
    out = pc_run([("file.automate.cropAndStraightenPhotos",)], input="scan.jpg", check=True)
    photos = pc_result(out, "file.automate.cropAndStraightenPhotos")["photos"]
    for p in photos:
        note("doc %d: %dx%d, rotated %.1f deg" % (p["document"], p["width"], p["height"], p["angle"]))
    n = len(photos)

    step("逐个保存：run --out 只存活动文档，多文档用 document.activate + file.saveACopy")
    cmds = [("file.automate.cropAndStraightenPhotos",)]
    for i in range(1, n + 1):
        cmds.append(("document.activate", {"document": i}))
        cmds.append(("file.saveACopy", {"path": f"photo-{i}.jpg", "quality": 10}))
    pc_run(cmds, input="scan.jpg", check=True)

    step("地平线拉直：顺时针旋转 3° 模拟拍歪，再用 image.crop angle:3（同号）反向拉直并裁到最大内接矩形")
    pc_run([("image.rotation.arbitrary", {"angle": 3, "direction": "cw"})], input=str(fixture("landscape.jpg")),
           out="tilted.jpg", extra=("--quality", "92"), check=True)
    j = info("tilted.jpg")
    W, H = j.width, j.height
    a = math.radians(3)
    s = min(W / (W * math.cos(a) + H * math.sin(a)), H / (W * math.sin(a) + H * math.cos(a)))
    w, h = math.floor(W * s), math.floor(H * s)
    crop = {"x": round((W - w) / 2), "y": round((H - h) / 2), "width": w, "height": h, "angle": 3}
    pc_run([("image.crop", crop)], input="tilted.jpg", out="straightened.jpg", extra=("--quality", "92"), check=True)

    step("核对")
    if n < 1:
        fail("no photo found on the scan (expected at least one)")
    expect_count(".", "photo-*.jpg", n)
    if demo_only("fixture scan holds exactly three photos at -12/-7/4 degrees"):
        if n != 3:
            fail(f"expected 3 photos on the scan, found {n}")
        angles = sorted(round(p["angle"]) for p in photos)
        if angles != [-12, -7, 4]:
            fail(f"detected angles {angles}, expected [-12, -7, 4]")
        note("ok  detected rotations -12, -7 and 4 degrees")

    pcx_ppm("straightened.jpg", "straight.ppm")
    im = Img("straight.ppm")
    size = 14
    bad = []
    for x, y in ((0, 0), (im.w - size, 0), (0, im.h - size), (im.w - size, im.h - size)):
        white = sum(1 for p in im.pixels(x, y, size, size) if min(p[:3]) > 0.97)
        if white > size * size * 0.5:
            bad.append((x, y))
    note(("ok  " if not bad else "BAD ") + "blank corners: %s" % (bad or "none"))
    Path("straight.ppm").unlink(missing_ok=True)
    if bad:
        fail("straightened.jpg still has blank corners (wrong crop angle sign?)")


run(main)
