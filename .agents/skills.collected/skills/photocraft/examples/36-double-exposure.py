#!/usr/bin/env python3
"""场景：把风景叠进人像做双重曝光：置入为智能对象、改混合模式、用渐变蒙版让下半部分透出人像，再统一调色。

要点：
 - 智能对象保留可回改的置入源；混合模式让两张图相乘/滤色，蒙版决定露出哪一半。
 - 蒙版上用 paint.gradient 画渐变（前景到透明），比手涂自然。
 - 天空/亮部要保住：用曲线或色阶压在蒙版那一层，别直接压人像。

用法: python 36-double-exposure.py [人像] [风景]
"""
from __future__ import annotations

import shutil
from pathlib import Path

from pcx import *


def main(args):
    portrait = pcx_input(args[0] if args else "", "portrait.jpg", kind="file")
    scene = pcx_input(args[1] if len(args) > 1 else "", "landscape.jpg", kind="file")
    pcx_init("36-double-exposure")
    shutil.copy2(portrait, "portrait.jpg")
    shutil.copy2(scene, "scene.jpg")
    scene_abs = pcx_native(Path("scene.jpg").resolve())

    step("置入风景为智能对象，铺满画布，混合模式 Screen")
    pc_run([("file.placeEmbedded", {"path": scene_abs, "fit": True}),
            ("layer.renameLayer", {"name": "Landscape"}),
            ("layer.setProps", {"blend": "Screen", "opacity": 0.85})],
           input="portrait.jpg", out="base.psd", check=True)

    step("渐变蒙版：上半部露出风景，下半部回到人像（蒙版默认全白，画黑色渐变遮住风景）")
    j = info("base.psd")
    W, H = j.width, j.height
    pc_run([("layer.select", {"name": "Landscape"}),
            ("layer.layerMask.hideAll",),
            ("paint.gradient", {"from": [W // 2, H // 3], "to": [W // 2, H * 3 // 4],
                                "colors": ["#ffffff", "#000000"], "dither": True, "target": "mask"})],
           input="base.psd", out="masked.psd", check=True)

    step("调色：曲线抬暗部 + 轻微去饱和，让两张图的色调统一")
    pc_run([("layer.newAdjustmentLayer.curves", {"points": [[0, 20], [64, 72], [192, 208], [255, 245]]}),
            ("layer.renameLayer", {"name": "Tone"}),
            ("layer.newAdjustmentLayer.vibrance", {"vibrance": -8, "saturation": -6})],
           input="masked.psd", out="double-exposure.psd", check=True)
    pc("convert", "double-exposure.psd", "double-exposure.jpg", "--quality", "90")

    step("核对")
    expect("double-exposure.psd",
           lambda k: any(l.name == "Landscape" and l.kind == "Smart Object" for l in k.layers),
           "landscape stays a smart object")
    expect("double-exposure.psd", lambda k: any(l.name == "Landscape" and l.hasMask for l in k.layers),
           "landscape has a layer mask")
    expect_size("double-exposure.jpg", W, H)

    # 蒙版效果：人像下半部（脸/胸口）应该仍接近原人像；上半部应被风景明显改变
    pcx_ppm("portrait.jpg", "p0.ppm")
    pcx_ppm("double-exposure.jpg", "p1.ppm")
    a, b = Img("p0.ppm"), Img("p1.ppm")
    lo = diff(a, b, round(a.w * 0.3), round(a.h * 0.62), round(a.w * 0.4), round(a.h * 0.25), step=4)[0]
    hi = diff(a, b, round(a.w * 0.3), round(a.h * 0.12), round(a.w * 0.4), round(a.h * 0.2), step=4)[0]
    note("mean change vs portrait: top %.3f, bottom %.3f" % (hi, lo))
    for p in Path(".").glob("*.ppm"):
        p.unlink()
    if not hi > lo * 1.5:
        fail("the mask did not keep the lower half closer to the portrait")
    note("ok  the landscape shows through the top and the portrait survives at the bottom")

    step("可回改：换一张置入内容仍保留蒙版和调色")
    flat = pc_result(pc_run([("layer.list", {"flat": True})], input="double-exposure.psd"),
                     "layer.list")["layers"]
    print(", ".join(l["name"] for l in flat))


run(main)
