#!/usr/bin/env python3
"""场景：商品目录要交给排版（InDesign 一类）：不抠掉背景，而是给图片带一条剪贴路径；同时出一版带矢量蒙版的 PSD
和一个 Alpha 通道，供不同下游使用。

注意：
 - 路径和剪贴路径只有 PSD 和分层 TIFF（--tiff-layers / tiffLayers）能带走，扁平 TIFF、JPEG 都没有。
 - 只有背景层的文档写分层 TIFF 时不写路径，所以先把背景转成普通图层（layer.new.layerFromBackground）。
 - 分层 TIFF 只写一个透明通道，额外的 Alpha 通道留在 PSD 里。
 - 在 serve/MCP 里这些导出命令不可用；桌面通道用 app.save。要分层 TIFF 就走 CLI convert。

用法: python 17-paths-clipping-catalog.py [商品图]
"""
from __future__ import annotations

import shutil

from pcx import *


def main(args):
    src = pcx_input(args[0] if args else "", "product.png", kind="file")
    pcx_init("17-paths-clipping-catalog")
    shutil.copy2(src, "product.png")

    step("选区 → 工作路径（容差 1.5px）→ 存为命名路径 → 设为剪贴路径；同时把选区存成 Alpha 通道")
    out = pc_run([
        ("layer.new.layerFromBackground",),
        ("layer.renameLayer", {"name": "Product"}),
        ("select.subject",),
        ("select.saveSelection", {"name": "Product alpha"}),
        ("select.toWorkPath", {"tolerance": 1.5}),
        ("path.rename", {"to": "Outline"}),
        ("path.clippingPath.set", {"name": "Outline", "flatness": 0.2}),
    ], input="product.png", out="catalog-clip.psd", check=True)
    r = pc_result(out, "select.toWorkPath")
    note("work path: %d subpath(s), %d anchor points" % (r["subpaths"], r["knots"]))
    pc("convert", "catalog-clip.psd", "catalog-clip.tif", "--tiff-layers")

    step("矢量蒙版版本：用命名路径做矢量蒙版（缩放不失真）")
    pc_run([("layer.select", {"name": "Product"}),
            ("layer.vectorMask.fromPath", {"name": "Outline"})],
           input="catalog-clip.psd", out="catalog-vector-mask.psd", check=True)

    step("路径的其他用法：用路径描一圈白色贴纸边，再垫一块深色底")
    pc_run([("layer.new.layer", {"name": "Sticker outline", "position": "below"}),
            ("path.stroke", {"name": "Outline", "tool": "brush", "size": 14, "hardness": 1, "color": "#ffffff"}),
            ("layer.newFillLayer.solidColor", {"color": "#1f2937"}),
            ("layer.arrange.sendToBack",)],
           input="catalog-vector-mask.psd", out="sticker.png", check=True)

    step("核对：路径、剪贴路径、矢量蒙版、Alpha 通道")

    def paths(path):
        r = pc_result(pc_run([("path.list",)], input=path), "path.list")
        return "%s|%s" % (",".join(p["name"] for p in r["paths"]),
                          r["clippingPath"]["name"] if r.get("clippingPath") else "-")

    if paths("catalog-clip.psd") != "Outline|Outline":
        fail("PSD lost the path or clipping path")
    note("ok  PSD keeps path Outline as clipping path")
    if paths("catalog-clip.tif") != "Outline|Outline":
        fail("layered TIFF lost the clipping path")
    note("ok  layered TIFF keeps the clipping path")
    expect("catalog-clip.psd", lambda k: any(a.name == "Product alpha" for a in k.channels.alpha),
           "alpha channel 'Product alpha' saved")
    expect("catalog-vector-mask.psd", lambda k: next(l for l in k.layers if l.name == "Product").hasVectorMask,
           "Product layer has a vector mask")
    expect_file("sticker.png")

    step("扁平导出会丢路径（对照）")
    pc("convert", "catalog-clip.psd", "catalog-flat.tif")
    flat = paths("catalog-flat.tif")
    if flat != "|-":
        fail(f"flat TIFF unexpectedly kept a path: {flat}")
    note("ok  flat TIFF carries no path (use --tiff-layers for print handoff)")


run(main)
