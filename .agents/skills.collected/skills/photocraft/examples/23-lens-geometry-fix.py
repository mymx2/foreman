#!/usr/bin/env python3
"""场景一：手机斜着拍的会议白板/文件，用透视裁切按四个角拉正成矩形，方便存档和打印。
场景二：广角镜头的桶形畸变和暗角，用镜头校正修正。
场景三：横图要改成更宽的横幅，内容识别缩放只拉伸天空和水面，主体不变形。
最后用"高反差保留 + 叠加"做细节锐化；锐化层单独保留，可调不透明度。

用法: python 23-lens-geometry-fix.py [白板照]
"""
from __future__ import annotations

import shutil
from pathlib import Path

from pcx import *

QUAD = [[300, 170], [1080, 250], [1150, 1330], [200, 1240]]   # 白板四角：左上、右上、右下、左下


def main(args):
    shot = pcx_input(args[0] if args else "", "", kind="file")
    pcx_init("23-lens-geometry-fix")
    shutil.copy2(fixture("landscape.jpg"), "scene.jpg")

    if shot is not None:
        shutil.copy2(shot, "whiteboard-photo.jpg")
    else:
        step("合成一张斜拍的白板照：深色桌面 + 白纸和字，整张纸做透视变形")
        pc_run([
            ("filter.noise.addNoise", {"amount": 4, "monochromatic": True, "seed": 9}),
            ("layer.new.layer", {"name": "Page"}),
            ("select.rect", {"x": 300, "y": 200, "width": 800, "height": 1100}),
            ("edit.fill", {"contents": "color", "color": "#fbfbf8"}),
            ("select.deselect",),
            ("type.create", {"x": 360, "y": 320, "text": "Q4 Roadmap", "size": 64, "color": "#1d4ed8",
                             "name": "Title"}),
            ("type.create", {"box": [360, 380, 680, 700], "text":
                             "1. Ship batch export\n2. Fix PSD round trip\n3. Faster blur\n4. Docs for agents",
                             "size": 40, "color": "#111827", "name": "Notes"}),
            ("layer.select", {"name": "Page"}),
            ("layer.select", {"name": "Title", "mode": "add"}),
            ("layer.select", {"name": "Notes", "mode": "add"}),
            ("layer.mergeLayers",),
            ("edit.transform", {"rect": [300, 200, 1100, 1300], "quad": QUAD}),
        ], new={"width": 1400, "height": 1500, "background": "#3b3f45", "name": "desk"},
            out="whiteboard-photo.jpg", extra=("--quality", "90"), check=True)

    if demo_only("known whiteboard corners"):
        step("透视裁切：四个角（左上起顺时针）映射成 800x1100 的正矩形")
        pc_run([("image.perspectiveCrop", {"corners": QUAD, "width": 800, "height": 1100}),
                ("image.autoContrast",)],
               input="whiteboard-photo.jpg", out="whiteboard-flat.jpg", extra=("--quality", "92"), check=True)
        expect_size("whiteboard-flat.jpg", 800, 1100)
        r = pc_result(pc_run([("document.sampleColor", {"x": 12, "y": 12, "size": 5})], input="whiteboard-flat.jpg"),
                      "document.sampleColor")
        corner = "page" if all(v > 0.85 for v in r[:3]) else "desk"
        if corner != "page":
            fail("perspective crop still shows the desk in the corner")
        note("ok  the flattened page fills the frame")
    else:
        note("user photo: read the four corners off a preview, then run image.perspectiveCrop {corners, width, height}")

    step("镜头：先模拟广角的桶形畸变和暗角，再用镜头校正修回来")
    pc_run([("filter.lensCorrection", {"profile": "none", "distortion": -25, "vignetteAmount": -70,
                                       "edge": "edgeExtension"})],
           input="scene.jpg", out="wide-angle.jpg", extra=("--quality", "92"), check=True)
    pc_run([("filter.lensCorrection", {"profile": "none", "distortion": 25, "vignetteAmount": 70,
                                       "autoScale": True, "edge": "edgeExtension"})],
           input="wide-angle.jpg", out="lens-fixed.jpg", extra=("--quality", "92"), check=True)

    def lum(path):
        r = pc_result(pc_run([("document.sampleColor", {"x": 30, "y": 30, "size": 31})], input=path),
                      "document.sampleColor")
        return (r[0] + r[1] + r[2]) / 3

    a, b = lum("wide-angle.jpg"), lum("lens-fixed.jpg")
    note("corner brightness: vignetted %.3f -> corrected %.3f" % (a, b))
    if not b > a + 0.02:
        fail("vignette not corrected")
    note("ok  vignette corrected")

    step("内容识别缩放：1400 → 1700 宽，画布先扩、内容再按内容识别拉宽，落点 x=0")
    pc_run([("layer.new.layerFromBackground",),
            ("image.canvasSize", {"width": 1700, "height": 837, "anchor": "center",
                                  "extensionColor": "transparent"}),
            ("edit.contentAwareScale", {"width": 1700, "x": 0, "y": 0, "amount": 100}),
            ("layer.duplicate", {"name": "High pass"}),
            ("filter.other.highPass", {"radius": 2.5}),
            ("layer.setProps", {"blend": "Overlay", "opacity": 0.7})],
           input="scene.jpg", out="banner.psd", check=True)
    pc("convert", "banner.psd", "banner.jpg", "--quality", "90")
    expect_size("banner.jpg", 1700, 837)
    r = pc_result(pc_run([("document.sampleColor", {"x": 3, "y": 400, "size": 5})], input="banner.jpg"),
                  "document.sampleColor")
    edge = "blank" if all(v > 0.98 for v in r[:3]) else "image"
    if edge != "image":
        fail("content-aware scale left a blank strip on the left")
    note("ok  banner filled edge to edge")
    expect("banner.psd", lambda k: any(l.name == "High pass" and l.blend == "Overlay" for l in k.layers),
           "high-pass sharpening kept as its own Overlay layer")


run(main)
