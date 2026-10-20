#!/usr/bin/env python3
"""场景：把网页版海报改成印刷文件：A4（210x297mm）300ppi、四边 3mm 出血、裁切线与安全区参考线、
转换前先查超色域比例，再转 CMYK，交付分层 TIFF（给设计）和拼合 TIFF（给印厂）。

尺寸：A4 300ppi = 2480x3508。原图按比例缩放到能放进 A4 的最大尺寸（不拉伸），
剩下的空白用原图对应边缘的平均色补齐；某一侧边缘颜色均匀（纯色底）时空白全补在那一侧。
出血 3mm ≈ 35px：四边各自用该边的颜色向外扩，成品 + 出血 = 2551x3579。
注意：文字和形状是矢量，放大无损；置入的照片会插值，正式印刷应换高分辨率原图。

用法: python 06-print-cmyk-prep.py [海报.psd 或图片]
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path

from pcx import *

A4_W, A4_H = 2480, 3508
BLEED = 35


def main(args):
    src = pcx_input(args[0] if args else "", "template.psd", kind="file")
    pcx_init("06-print-cmyk-prep")
    shutil.copy2(src, "web-poster.psd")
    j = info("web-poster.psd")
    W, H = j.width, j.height
    want_kinds = sorted(l.kind for l in j.layers)

    step("取四条边的颜色：每边 9 个点（5x5 平均），记下均值和起伏")
    cmds = []
    for edge in ("top", "bottom", "left", "right"):
        for k in range(1, 10):
            x = {"top": W * k / 10, "bottom": W * k / 10, "left": 2, "right": W - 3}[edge]
            y = {"top": 2, "bottom": H - 3, "left": H * k / 10, "right": H * k / 10}[edge]
            cmds.append(("document.sampleColor", {"x": round(x), "y": round(y), "size": 5}))
    samples = [pc_result(pc_run([c], input="web-poster.psd"), "document.sampleColor") for c in cmds]

    step("规划：等比缩放进 A4 → 补齐到 A4 → 四边出血（每一步都是一条 image.canvasSize）")
    edges = {}
    for i, name in enumerate(("top", "bottom", "left", "right")):
        part = samples[i * 9:(i + 1) * 9]
        mean = [sum(c[k] for c in part) / len(part) for k in range(3)]
        spread = max(max(c[k] for c in part) - min(c[k] for c in part) for k in range(3))
        edges[name] = ("#" + hexrgb(mean), spread)

    s = min(A4_W / W, A4_H / H)
    w2, h2 = round(W * s), round(H * s)

    def split(total, a, b):
        ua, ub = edges[a][1] < 0.04, edges[b][1] < 0.04
        if ua and not ub:
            return total, 0
        if ub and not ua:
            return 0, total
        return total // 2, total - total // 2

    pt, pb = split(A4_H - h2, "top", "bottom")
    pl, pr = split(A4_W - w2, "left", "right")
    plan = [("image.imageSize", {"width": w2, "height": h2, "resolution": 300, "resample": "bicubicSmoother"})]
    cw, ch = w2, h2
    for pad, side, anchor in ((pt, "top", "bottom"), (pb, "bottom", "top"), (BLEED, "top", "bottom"),
                              (BLEED + 1, "bottom", "top"), (pl, "left", "right"), (pr, "right", "left"),
                              (BLEED, "left", "right"), (BLEED + 1, "right", "left")):
        if pad <= 0:
            continue
        if side in ("top", "bottom"):
            ch += pad
        else:
            cw += pad
        plan.append(("image.canvasSize", {"width": cw, "height": ch, "anchor": anchor,
                                          "extensionColor": edges[side][0]}))
    for name, (hexc, spread) in edges.items():
        note(f"{name:<6} edge {hexc} (spread {spread:.3f})")
    note(f"scaled {w2}x{h2}; pad top {pt} bottom {pb} left {pl} right {pr}")

    step("执行：尺寸 → 补齐 → 出血 → 裁切线（品红）与安全区（青色）参考线")
    plan += [
        ("view.newGuide", {"orientation": "vertical", "position": "3mm", "color": "magenta"}),
        ("view.newGuide", {"orientation": "vertical", "position": "213mm", "color": "magenta"}),
        ("view.newGuide", {"orientation": "horizontal", "position": "3mm", "color": "magenta"}),
        ("view.newGuide", {"orientation": "horizontal", "position": "300mm", "color": "magenta"}),
        ("view.newGuide", {"orientation": "vertical", "position": "8mm", "color": "cyan"}),
        ("view.newGuide", {"orientation": "vertical", "position": "208mm", "color": "cyan"}),
        ("view.newGuide", {"orientation": "horizontal", "position": "8mm", "color": "cyan"}),
        ("view.newGuide", {"orientation": "horizontal", "position": "295mm", "color": "cyan"}),
    ]
    resized = pc_run(plan, input="web-poster.psd", out="print-rgb.psd", check=True)
    expect("print-rgb.psd", lambda k: k.width == 2551 and k.height == 3579 and k.resolution == 300,
           "2551x3579 px at 300 ppi (A4 + 3 mm bleed)")
    scaled = pc_result(resized, "image.imageSize")
    if abs(scaled["width"] * H - scaled["height"] * W) > max(W, H):
        fail("picture was not scaled proportionally")
    note("ok  picture scaled proportionally to %dx%d" % (scaled["width"], scaled["height"]))

    step("印前检查：模拟印刷色域，统计超色域像素")
    out = pc_run([("view.proofSetup", {"profile": "coated-cmyk", "intent": "perceptual"}),
                  ("view.gamutWarning", {"on": True, "profile": "coated-cmyk"})], input="print-rgb.psd")
    r = pc_result(out, "view.gamutWarning")
    print("out of gamut: %.2f%% of pixels (deltaE > %s) against %s"
          % (r["fraction"] * 100, r["threshold"], r["profile"]))

    step("转 CMYK（可感知意图 + 黑场补偿），写入作品信息")
    pc_run([("edit.convertToProfile", {"profile": "coated-cmyk", "intent": "perceptual", "bpc": True}),
            ("file.fileInfo", {"title": "Summer Sale A4",
                               "description": "A4 210x297 mm, 3 mm bleed, coated CMYK"})],
           input="print-rgb.psd", out="print-cmyk.psd", check=True)

    step("交付：分层 TIFF 与拼合 TIFF")
    pc("convert", "print-cmyk.psd", "poster-layered.tif", "--tiff-layers")
    pc("convert", "print-cmyk.psd", "poster-flat.tif")

    step("核对")
    pcx_ppm("print-rgb.psd", "print-rgb.ppm")
    im = Img("print-rgb.ppm")
    bands = {"top": ((BLEED, 0, A4_W, BLEED), (BLEED, BLEED, A4_W, BLEED)),
             "bottom": ((BLEED, 3544, A4_W, BLEED), (BLEED, 3509, A4_W, BLEED)),
             "left": ((0, BLEED, BLEED, A4_H), (BLEED, BLEED, BLEED, A4_H)),
             "right": ((2516, BLEED, BLEED, A4_H), (2481, BLEED, BLEED, A4_H))}
    bad = 0
    for side, (bleed, inner) in bands.items():
        a, b = im.stats(*bleed, step=3)[0], im.stats(*inner, step=3)[0]
        d = max(abs(a[k] - b[k]) for k in range(3))
        note(("ok  " if d <= 0.08 else "BAD ") + "%-6s bleed #%s next to #%s (diff %.3f)"
             % (side, hexrgb(a), hexrgb(b), d))
        bad += d > 0.08
    Path("print-rgb.ppm").unlink(missing_ok=True)
    if bad:
        fail("a bleed band does not continue the picture next to it")

    expect("print-cmyk.psd", lambda k: k.mode == "Cmyk", "CMYK master keeps its mode")
    _same_kinds("print-cmyk.psd", want_kinds, "CMYK master keeps every layer and its kind")
    if demo_only("template: type stays live after the resize"):
        expect("print-cmyk.psd", lambda k: any(l.kind == "Type" for l in k.layers), "CMYK master keeps live type")
    expect("poster-layered.tif", lambda k: k.mode == "Cmyk", "layered TIFF is CMYK")
    _same_kinds("poster-layered.tif", want_kinds, "layered TIFF keeps every layer")
    expect("poster-flat.tif", lambda k: k.mode == "Cmyk" and len(k.layers) == 1, "flat TIFF is a single CMYK layer")


def _same_kinds(path, want, what):
    got = sorted(l.kind for l in info(path).layers)
    if got != want:
        fail(f"{what} ({path})")
    note(f"ok  {what}")


run(main)
