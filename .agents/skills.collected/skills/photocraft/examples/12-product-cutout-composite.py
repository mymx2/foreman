#!/usr/bin/env python3
"""场景：把棚拍商品抠出来放进场景图做宣传图。抠图用"主体选择 + 调整边缘（净化颜色）"，
合成时商品作为智能对象（可无损缩放），加投影，用剪贴到商品的调整图层让商品色调融入场景。
摆放按场景尺寸计算：商品高约为场景高的 55%（宽不超过场景宽的 30%），放在右侧、底边离画面下沿 8%，整件留在画面内。

用法: python 12-product-cutout-composite.py [商品图] [场景图]
"""
from __future__ import annotations

import shutil
from pathlib import Path

from pcx import *


def main(args):
    product = pcx_input(args[0] if args else "", "product.png", kind="file")
    scene = pcx_input(args[1] if len(args) > 1 else "", "landscape.jpg", kind="file")
    pcx_init("12-product-cutout-composite")
    shutil.copy2(product, "product-src.png")
    shutil.copy2(scene, "scene.jpg")

    step("抠图：主体选择 → 调整边缘（智能半径 + 净化颜色，强制输出为带蒙版的新图层）→ 透明 PNG")
    # 在背景层上调整边缘时，output:"layerMask" 实际按 newLayerWithMask 输出（背景层不能带蒙版），返回值会如实写出
    out = pc_run([("select.subject",),
                  ("select.refineEdge", {"radius": 3, "smartRadius": True, "smooth": 10,
                                         "decontaminate": True, "amount": 80, "output": "layerMask"}),
                  ("layer.select", {"name": "Background"}),
                  ("layer.setProps", {"visible": False})], input="product-src.png", out="cutout.png", check=True)
    print("refine output: %s" % pc_result(out, "select.refineEdge")["output"])
    alpha = pc_result(pc_run([("document.sampleColor", {"x": 3, "y": 3})], input="cutout.png"),
                      "document.sampleColor")[3]
    if alpha not in (0, 0.0):
        fail(f"cutout background is not transparent (alpha {alpha})")
    note("ok  cutout.png background is transparent")
    pc_run([("image.trim", {"basedOn": "transparent"})], input="cutout.png", out="cutout-trimmed.png", check=True)

    step("摆放：按场景与商品的尺寸算缩放和中心点")
    j = info("cutout-trimmed.png")
    sw, sh = info("scene.jpg").width, info("scene.jpg").height
    s = min(0.55 * sh / j.height, 0.30 * sw / j.width)
    tw, th = j.width * s, j.height * s
    cx = min(max(0.72 * sw, tw / 2 + 0.03 * sw), sw - tw / 2 - 0.03 * sw)
    cy = min(max(0.92 * sh - th / 2, th / 2 + 0.03 * sh), sh - th / 2 - 0.03 * sh)
    if s > 1:
        note("note: product enlarged to %.0f%%; use a larger cutout for print" % (s * 100))
    place = {"path": pcx_native(Path("cutout-trimmed.png").resolve()), "scale": round(s * 100, 2),
             "center": [round(cx), round(cy)]}
    note(f"file.placeEmbedded {place}")

    step("合成：置入为智能对象 → 投影 → 剪贴曲线压亮部 + 剪贴暖色滤镜 → 分层 PSD 与 JPG")
    pc_run([
        ("file.placeEmbedded", place),
        ("layer.renameLayer", {"name": "Product"}),
        ("layer.layerStyle.dropShadow", {"color": "#1a1209", "opacity": 55, "angle": 135, "distance": 16,
                                         "spread": 4, "size": 26}),
        ("layer.newAdjustmentLayer.curves", {"points": [[0, 6], [128, 122], [255, 236]]}),
        ("layer.createClippingMask",),
        ("layer.renameLayer", {"name": "Product tone"}),
        ("layer.newAdjustmentLayer.photoFilter", {"filter": "warming81", "density": 22}),
        ("layer.createClippingMask",),
        ("layer.renameLayer", {"name": "Product warm"}),
    ], input="scene.jpg", out="composite.psd", check=True)
    pc("convert", "composite.psd", "composite.jpg", "--quality", "88")

    step("核对")
    for l in info("composite.psd").layers:
        print("  %s (%s)%s%s" % (l.name, l.kind, " clipped" if l.clipped else "", " fx" if l.effects else ""))

    def product_ok(k):
        product_layer = next((l for l in k.layers if l.name == "Product"), None)
        return product_layer is not None and product_layer.kind == "Smart Object" and bool(product_layer.effects)

    def clipped_ok(k):
        return len([l for l in k.layers if l.clipped]) == 2

    def inside_ok(k):
        b = next((l for l in k.layers if l.name == "Product"), None)
        if b is None or not b.bounds:
            return False
        x, y, w, h = b.bounds
        return x >= 0 and y >= 0 and x + w <= sw and y + h <= sh

    expect("composite.psd", product_ok, "product is a smart object with a drop shadow")
    expect("composite.psd", clipped_ok, "two adjustment layers clipped to the product")
    expect("composite.psd", inside_ok, f"the whole product sits inside the {sw}x{sh} scene")
    expect_size("composite.jpg", sw, sh)


run(main)
