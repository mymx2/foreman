#!/usr/bin/env python3
"""场景一（游戏美术）：引擎要一张 ORM 打包贴图：R=环境光遮蔽，G=粗糙度，B=金属度。从一张纹理出发，
拆成三个通道分别处理，再按 RGB 合并回去。
场景二（修图）：亮度蒙版只压暗高光；"计算"生成一个遮罩通道；"应用图像"用自身叠加增强反差。

要点：channel.split 默认关闭原文档（closeOriginal 默认为 true），要保留原文档就显式传 closeOriginal:false；
之后的命令要先 document.activate 切过去。

用法: python 27-channels-texture-pack.py [纹理图]
"""
from __future__ import annotations

import shutil
from pathlib import Path

from pcx import *


def main(args):
    tex = pcx_input(args[0] if args else "", "", kind="file")
    pcx_init("27-channels-texture-pack")
    if tex is not None:
        shutil.copy2(tex, "texture-src.png")
    else:
        pc_run([("image.crop", {"x": 120, "y": 200, "width": 512, "height": 512})],
               input=str(fixture("landscape.jpg")), out="texture-src.png", check=True)

    step("拆通道 → R 做 AO（色阶压暗）、G 做粗糙度（反相 + 模糊）、B 做金属度（阈值二值化）→ 合并为 RGB")
    out = pc_run([
        ("channel.split",),
        ("document.activate", {"document": 0}),
        ("image.adjustments.levels", {"inBlack": 30, "inWhite": 230, "gamma": 0.8}),
        ("document.activate", {"document": 1}),
        ("image.adjustments.invert",),
        ("filter.blur.gaussianBlur", {"radius": 2}),
        ("document.activate", {"document": 2}),
        ("image.adjustments.threshold", {"level": 150}),
        ("channel.merge", {"mode": "rgb", "documents": [0, 1, 2], "name": "T_Rock_ORM"}),
    ], input="texture-src.png", out="T_Rock_ORM.png", check=True)
    print(json_line(pc_result(out, "channel.merge")))

    step("高光亮度蒙版 + 计算遮罩通道 + 应用图像增强反差")
    pc_run([
        ("select.loadLuminosity",),
        ("select.saveSelection", {"name": "Highlights"}),
        ("layer.newAdjustmentLayer.curves", {"points": [[0, 0], [128, 124], [255, 228]]}),
        ("layer.renameLayer", {"name": "Tame highlights"}),
        ("image.calculations", {"source1": {"channel": "red"}, "source2": {"channel": "blue", "invert": True},
                                "blending": "multiply", "result": "newChannel", "name": "Warm mask"}),
        ("layer.select", {"name": "Background"}),
        ("image.applyImage", {"source": {"layer": "merged", "channel": "composite"},
                              "blending": "softLight", "opacity": 40}),
    ], input=str(fixture("landscape.jpg")), out="channels-retouch.psd", check=True)

    step("核对")
    expect("T_Rock_ORM.png", lambda k: k.mode == "Rgb" and k.width == 512, "ORM texture is RGB 512x512")
    # 金属度在蓝色通道：取若干点，值只能接近 0 或 1（阈值二值化的结果）
    pcx_ppm("T_Rock_ORM.png", "orm.ppm")
    im = Img("orm.ppm")
    vals = [im.px(x, y)[2] for x, y in ((40, 40), (256, 256), (470, 120), (90, 430), (500, 500))]
    bad = [v for v in vals if 0.02 < v < 0.98]
    note(("ok  " if not bad else "BAD ") + "blue channel samples: " + ", ".join("%.3f" % v for v in vals))
    Path("orm.ppm").unlink(missing_ok=True)
    if bad:
        fail("blue (metallic) channel is not binary")
    note("ok  metallic channel holds only 0 or 1")
    expect("channels-retouch.psd",
           lambda k: ",".join(a.name for a in k.channels.alpha) == "Highlights,Warm mask",
           "alpha channels Highlights and Warm mask")
    expect("channels-retouch.psd", lambda k: any(l.name == "Tame highlights" for l in k.layers),
           "highlight curve layer present")


def json_line(value):
    import json
    return json.dumps(value, ensure_ascii=False)


run(main)
