#!/usr/bin/env python3
"""场景：客户想看同一张照片的几种风格再挑。一次出 8 个方案（油画、水彩+纹理、波普网点、移轴微缩、动感模糊、
小星球、素描线稿、复古光晕），每个方案独立从原图出发，最后拼成带标题的方案对比联系表。

用法: python 18-creative-filter-looks.py [照片]
"""
from __future__ import annotations

import shutil
from pathlib import Path

from pcx import *


def main(args):
    src = pcx_input(args[0] if args else "", "landscape.jpg", kind="file")
    pcx_init("18-creative-filter-looks")
    shutil.copy2(src, "source.jpg")
    Path("looks").mkdir()

    def look(name, cmds):
        pc_run(cmds, input="source.jpg", out=f"looks/{name}.jpg", extra=("--quality", "88"), check=True)
        note(f"looks/{name}.jpg")

    step("8 个风格方案")
    look("01-oil-paint", [("filter.stylize.oilPaint", {"stylization": 5, "cleanliness": 6,
                                                       "bristleDetail": 4, "lighting": True})])
    look("02-watercolor-paper", [("filter.filterGallery", {"effects": [
        {"filter": "watercolor", "params": {"brushDetail": 11, "shadowIntensity": 1, "texture": 1}},
        {"filter": "texturizer", "params": {}}]})])
    look("03-pop-halftone", [("image.adjustments.vibrance", {"vibrance": 60}),
                             ("filter.pixelate.colorHalftone", {"maxRadius": 6})])
    look("04-tilt-shift-miniature", [("filter.blurGallery.tiltShift", {"blur": 22, "centerY": 0.72,
                                                                        "focus": 0.08, "transition": 0.2}),
                                     ("image.adjustments.vibrance", {"vibrance": 40, "saturation": 10})])
    look("05-motion-speed", [("filter.blur.motionBlur", {"angle": 0, "distance": 40})])
    # 小星球：先按画布尺寸裁成正方形并上下翻转，再直角坐标转极坐标
    j = info("source.jpg")
    side = min(j.width, j.height)
    look("06-tiny-planet", [("image.crop", {"x": (j.width - side) // 2, "y": 0, "width": side, "height": side,
                                            "targetWidth": 1200, "targetHeight": 1200}),
                            ("image.imageRotation.flipCanvasVertical",),
                            ("filter.distort.polarCoordinates", {"mode": "rectangularToPolar"})])
    look("07-pencil-sketch", [("image.adjustments.desaturate",),
                              ("filter.stylize.findEdges",),
                              ("image.adjustments.levels", {"inBlack": 60, "inWhite": 250})])
    look("08-retro-flare", [("filter.render.lensFlare", {"brightness": 120, "centerX": 0.68, "centerY": 0.22,
                                                          "lens": "prime105"}),
                            ("layer.newAdjustmentLayer.gradientMap", {"stops": [[0, "#2b1a3d"], [0.55, "#d9825b"],
                                                                                [1, "#fff1c9"]]}),
                            ("layer.setProps", {"opacity": 0.45, "blend": "Soft Light"})])

    step("方案对比联系表：4 列 2 行，文件名作标题")
    pc_run([("file.automate.contactSheetII", {"input": "looks", "units": "pixels", "width": 2000, "height": 1000,
                                              "resolution": 150, "columns": 4, "rows": 2, "caption": True,
                                              "fontSize": 9, "flatten": True})],
           new={"width": 1, "height": 1}, out="looks-contact-sheet.jpg", extra=("--quality", "90"), check=True)

    step("核对")
    expect_count("looks", "*.jpg", 8)
    expect_size("looks/06-tiny-planet.jpg", 1200, 1200)
    expect_size("looks-contact-sheet.jpg", 2000, 1000)


run(main)
