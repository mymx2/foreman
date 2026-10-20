#!/usr/bin/env python3
"""场景：热门景点人来人往。三脚架上连拍 5 张（手扶相机有几像素晃动），游客每张都在不同位置。
载入堆栈时自动对齐，转成智能对象后设堆栈模式为"中间值"：每个像素取 5 张的中位数，走动的人就消失了。

要点：loadFilesIntoStack 返回的文档成为活动文档；堆栈模式可反复改，所以保留 .psd 母版。

用法: python 21-crowd-removal-stack.py [连拍目录]
"""
from __future__ import annotations

import shutil
from pathlib import Path

from pcx import *

TOURIST_X = [220, 440, 660, 880, 1100]


def main(args):
    burst = pcx_input(args[0] if args else "", "", kind="dir")
    pcx_init("21-crowd-removal-stack")
    Path("frames").mkdir()
    shutil.copy2(fixture("landscape.jpg"), "scene.jpg")

    if burst is not None:
        pcx_copy_dir(burst, Path("frames"))
        if not any(Path("frames").iterdir()):
            fail(f"no files in {burst}")
    else:
        step("模拟连拍：每张平移 0~3px（手抖），画一个位置不同的游客，再加不同的噪点")
        colors = ["#b91c1c", "#1d4ed8", "#15803d", "#a16207", "#7e22ce"]
        for i, x in enumerate(TOURIST_X):
            jx, jy = (i * 3) % 4, (i * 2) % 3
            pc_run([
                ("filter.other.offset", {"horizontal": jx, "vertical": jy, "undefinedAreas": "repeat"}),
                ("shape.create", {"kind": "ellipse", "rect": [x + 12, 560, 36, 42], "fill": "#3a2a20"}),
                ("shape.create", {"kind": "roundedRect", "rect": [x, 604, 60, 150], "radii": 18,
                                  "fill": colors[i]}),
                ("layer.flattenImage",),
                ("filter.noise.addNoise", {"amount": 2, "monochromatic": True, "seed": i + 11}),
            ], input="scene.jpg", out=f"frames/frame-{i}.jpg", extra=("--quality", "92"), check=True)

    step("载入堆栈（自动对齐、合为智能对象）→ 中间值堆栈模式")
    pc_run([("file.scripts.loadFilesIntoStack", {"paths": "frames", "align": True, "createSmartObject": True}),
            ("layer.smartObjects.stackMode.median",)],
           new={"width": 1, "height": 1}, out="clean.psd", check=True)
    pc("convert", "clean.psd", "clean.jpg", "--quality", "92")
    expect("clean.psd", lambda k: any(l.kind == "Smart Object" for l in k.layers),
           "stack kept as a smart object (stack mode can be changed later)")
    if demo_only("fixture frames are 1400x837"):
        expect_size("clean.jpg", 1400, 837)

    step("核对：第一张里游客身体的位置，在结果里恢复成了背景")
    if demo_only("tourist at a known fixture coordinate"):
        x = TOURIST_X[0]

        def px(path):
            r = pc_result(pc_run([("document.sampleColor", {"x": x + 30, "y": 680, "size": 11})], input=path),
                          "document.sampleColor")
            return r[:3]

        bg, with_tourist, out = px("scene.jpg"), px("frames/frame-0.jpg"), px("clean.jpg")
        note("background %s | frame-0 with tourist %s | stacked %s"
             % (",".join("%.3f" % v for v in bg), ",".join("%.3f" % v for v in with_tourist),
                ",".join("%.3f" % v for v in out)))
        d = lambda a, b: max(abs(x - y) for x, y in zip(a, b))  # noqa: E731
        if not (d(with_tourist, bg) > 0.15 and d(out, bg) < 0.08):
            fail("tourist still visible after the median stack")
        note("ok  tourist removed")
    else:
        note("user burst: compare the stacked frame with a single frame by eye")


run(main)
