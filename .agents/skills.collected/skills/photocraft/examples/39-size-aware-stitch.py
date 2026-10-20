#!/usr/bin/env python3
"""场景：两张图按实际尺寸拼接——上图下图，或左图右图，画布和位置都由图片尺寸算出来。

竖向：新建 max(宽) × (高1+高2) 的画布，两张图各置入一次，交叉轴居中。
横向：先打开左图，用 image.canvasSize 向右扩画布（anchor left，交叉轴自动居中），再置入右图。
置入显式给 scale:100，避免"大图自动缩到画布"改变像素尺寸；serve 下改用 doc.place。

用法: python 39-size-aware-stitch.py [左图/上图] [右图/下图]
"""
from __future__ import annotations

import shutil
from pathlib import Path

from pcx import *


def layer(path, name):
    found = next((item for item in info(path).layers if item.name == name), None)
    if found is None:
        fail(f"missing layer {name!r} in {path}")
    return found


def check_box(box, want, what):
    if any(abs(a - b) > 1 for a, b in zip(box, want)):
        fail(f"{what}: bounds {box}, expected {want}")


def main(args):
    a = pcx_input(args[0] if args else "", "landscape.jpg", kind="file")
    b = pcx_input(args[1] if len(args) > 1 else "", "portrait.jpg", kind="file")
    pcx_init("39-size-aware-stitch")

    a_name = "a" + a.suffix.lower()
    b_name = "b" + b.suffix.lower()
    shutil.copy2(a, a_name)
    shutil.copy2(b, b_name)
    ja, jb = info(a_name), info(b_name)
    aw, ah, bw, bh = ja.width, ja.height, jb.width, jb.height
    note(f"a {aw}x{ah}, b {bw}x{bh}")
    place_a = pcx_native(Path(a_name).resolve())
    place_b = pcx_native(Path(b_name).resolve())

    step("竖向：新建 max(宽) × (高1+高2) 的画布，两张图沿交叉轴居中")
    W, H = max(aw, bw), ah + bh
    pc_run([
        ("file.placeEmbedded", {"path": place_a, "scale": 100, "smartObject": False,
                                 "center": [W / 2, ah / 2]}),
        ("file.placeEmbedded", {"path": place_b, "scale": 100, "smartObject": False,
                                 "center": [W / 2, ah + bh / 2]}),
    ], new={"width": W, "height": H, "background": "#ffffff", "name": "vertical"},
       out="vertical.psd", check=True)
    expect_size("vertical.psd", W, H)
    check_box(layer("vertical.psd", "a").bounds, [(W - aw) / 2, 0, aw, ah], "vertical a")
    check_box(layer("vertical.psd", "b").bounds, [(W - bw) / 2, ah, bw, bh], "vertical b")
    for name in ("a", "b"):
        if layer("vertical.psd", name).kind != "Pixel":
            fail(f"{name} was not placed as a pixel layer")
    note("ok  %dx%d: a on top, b below" % (W, H))

    step("横向：打开左图，image.canvasSize 向右扩画布（anchor left），再置入右图")
    W2, H2 = aw + bw, max(ah, bh)
    rows = pc_run([
        ("image.canvasSize", {"width": W2, "height": H2, "anchor": "left",
                              "extensionColor": "#ffffff"}),
        ("file.placeEmbedded", {"path": place_b, "scale": 100, "smartObject": False,
                                 "center": [aw + bw / 2, H2 / 2]}),
    ], input=a_name, out="horizontal.psd", check=True)
    canvas = pc_result(rows, "image.canvasSize")
    if "offset" not in canvas:
        fail("image.canvasSize did not report offset; cannot verify where the existing image sits")
    offset = canvas["offset"]
    note("canvas offset %s, target [0, %.1f]" % (offset, (H2 - ah) / 2))
    if abs(offset[0]) > 1 or abs(offset[1] - (H2 - ah) / 2) > 1:
        fail(f"existing image offset {offset} is not left-aligned and vertically centred")
    expect_size("horizontal.psd", W2, H2)
    check_box(layer("horizontal.psd", "b").bounds, [aw, (H2 - bh) / 2, bw, bh], "horizontal b")
    if layer("horizontal.psd", "b").kind != "Pixel":
        fail("b was not placed as a pixel layer")
    note("ok  %dx%d: a on the left, b on the right" % (W2, H2))

    pc("convert", "vertical.psd", "vertical.jpg", "--quality", "90", check=True)
    pc("convert", "horizontal.psd", "horizontal.jpg", "--quality", "90", check=True)
    note("ok  vertical.jpg and horizontal.jpg written")


run(main)
