#!/usr/bin/env python3
"""场景：App 落地页设计稿交付给前端：手机/平板两个画板，浅色/深色两套图层复合。要交付：
 - 每个画板一张 PNG + 一份给产品评审的多页 PDF
 - 每套复合一张预览图
 - 切图：图层按 Generator 规则命名（"btn.png, 200% btn@2x.png"、"48x48 icons/star.png"），一键导出多倍图
 - 单个图层快速导出；首屏按切片导出为 Web 图片 + HTML

要点：
 - 画板之后新建的图层不会自动进画板：先画内容，再选中这些图层用 artboardFromLayers 生成画板。
 - Save for Web 的 HTML 只有 `slices:"all"` 才写出带占位格的完整表格；`"user"` 只输出用户切片，行高不补齐、位置会错。
 - 导出文件名以命令返回的 files 为准（画板带序号前缀，如 0001_Mobile.png）。

用法: python 24-design-handoff-export.py
"""
from __future__ import annotations

import re
from pathlib import Path

from pcx import *


def main(args):
    pcx_init("24-design-handoff-export")

    def sel(*names):
        cmds = []
        for i, n in enumerate(names):
            cmds.append(("layer.select", {"name": n} if i == 0 else {"name": n, "mode": "add"}))
        return cmds

    dark_sel = ["M bg dark", "T bg dark"]

    step("画内容 → 生成两个画板 → 建浅色/深色两套图层复合")
    cmds = [
        ("shape.create", {"kind": "rect", "rect": [0, 0, 360, 640], "fill": "#f8fafc", "name": "M bg"}),
        ("shape.create", {"kind": "rect", "rect": [0, 0, 360, 640], "fill": "#0f172a", "name": "M bg dark"}),
        ("shape.create", {"kind": "rect", "rect": [0, 0, 360, 240],
                          "fill": {"gradient": {"stops": [[0, "#6366f1"], [1, "#22d3ee"]], "angle": 30}},
                          "name": "M hero"}),
        ("type.create", {"x": 24, "y": 310, "text": "Sync everything", "size": 34, "color": "#64748b",
                         "name": "M title"}),
        ("shape.create", {"kind": "roundedRect", "rect": [24, 540, 312, 56], "radii": 14, "fill": "#2563eb",
                          "name": "btn-primary.png, 200% btn-primary@2x.png"}),
        ("type.create", {"x": 180, "y": 576, "text": "Get started", "size": 20, "color": "#ffffff",
                         "align": "center", "name": "M cta"}),
        ("shape.create", {"kind": "rect", "rect": [460, 0, 768, 1024], "fill": "#f8fafc", "name": "T bg"}),
        ("shape.create", {"kind": "rect", "rect": [460, 0, 768, 1024], "fill": "#0f172a", "name": "T bg dark"}),
        ("shape.create", {"kind": "rect", "rect": [460, 0, 768, 380],
                          "fill": {"gradient": {"stops": [[0, "#6366f1"], [1, "#22d3ee"]], "angle": 30}},
                          "name": "T hero"}),
        ("type.create", {"x": 508, "y": 470, "text": "Sync everything, everywhere", "size": 44,
                         "color": "#64748b", "name": "T title"}),
        ("shape.create", {"kind": "roundedRect", "rect": [508, 880, 320, 64], "radii": 16, "fill": "#2563eb",
                          "name": "btn-primary-tablet.png"}),
        ("type.create", {"x": 668, "y": 921, "text": "Get started", "size": 22, "color": "#ffffff",
                         "align": "center", "name": "T cta"}),
        ("shape.create", {"kind": "star", "rect": [1140, 40, 64, 64], "fill": "#facc15",
                          "name": "48x48 icons/star.png"}),
    ]
    cmds += sel("M bg", "M bg dark", "M hero", "M title", "btn-primary.png, 200% btn-primary@2x.png", "M cta")
    cmds += [("layer.new.artboardFromLayers", {"name": "Mobile"})]
    cmds += sel("T bg", "T bg dark", "T hero", "T title", "btn-primary-tablet.png", "T cta", "48x48 icons/star.png")
    cmds += [("layer.new.artboardFromLayers", {"name": "Tablet"})]
    cmds += sel(*dark_sel) + [("layer.hideLayers",),
                              ("layerComp.new", {"name": "Light", "visibility": True}),
                              ("layer.showLayers",)]
    cmds += sel("M bg", "T bg") + [("layer.hideLayers",),
                                   ("layerComp.new", {"name": "Dark", "visibility": True}),
                                   ("layerComp.apply", {"comp": "Light"})]
    pc_run(cmds, new={"width": 1300, "height": 1100, "background": "transparent", "name": "landing"},
           out="landing.psd", check=True)
    flat = pc_result(pc_run([("layer.list", {"flat": True})], input="landing.psd"), "layer.list")["layers"]
    print("\n".join("  " * (l["depth"] or 0) + "%s (%s)" % (l["name"], l["kind"]) for l in flat))

    step("导出：画板 PNG、评审 PDF、复合预览、Generator 切图、单层快速导出、切片 Web 图 + HTML")
    out = pc_run([
        ("file.export.artboardsToFiles", {"dir": "boards", "format": "png", "prefix": ""}),
        ("file.export.artboardsToPdf", {"path": "review.pdf", "quality": 10}),
        ("file.export.layerCompsToFiles", {"dir": "comps", "format": "png", "prefix": "landing"}),
        ("file.generate.imageAssets", {"on": True, "dir": "assets"}),
        ("layer.select", {"name": "48x48 icons/star.png"}),
        ("layer.quickExportAsPng", {"path": "star-original.png"}),
        ("slice.new", {"rect": [460, 0, 768, 380], "name": "hero", "alt": "Product hero"}),
        ("slice.new", {"rect": [508, 880, 320, 64], "name": "cta", "url": "https://example.com/signup",
                       "alt": "Get started"}),
        ("file.export.saveForWebLegacy", {"dir": "web", "format": "png24", "slices": "all", "html": True}),
    ], input="landing.psd", check=True)
    assets = pc_result(out, "file.generate.imageAssets")
    print("(generator: %d files, %d errors)" % (len(assets["files"]), len(assets["errors"])))

    step("核对（导出文件名以命令返回的 files 为准）")
    boards = pc_result(out, "file.export.artboardsToFiles")["files"]
    print("\n".join("   " + f for f in boards))
    mobile = next(f for f in boards if "Mobile.png" in f)
    tablet = next(f for f in boards if "Tablet.png" in f)
    expect_size(mobile, 360, 640)
    expect_size(tablet, 768, 1024)
    if not Path("review.pdf").read_bytes()[:5] == b"%PDF-":
        fail("review.pdf is not a PDF")
    note("ok  review.pdf (%s pages)" % pc_result(out, "file.export.artboardsToPdf")["pages"])
    expect_count("comps", "*.png", 2)
    expect_size("assets/btn-primary.png", 312, 56)
    expect_size("assets/btn-primary@2x.png", 624, 112)
    expect_size("assets/icons/star.png", 48, 48)
    expect_file("star-original.png")

    html = next(Path("web").glob("*.htm*"), None)
    if html is None:
        fail("Save for Web wrote no HTML")
    text = html.read_text(encoding="utf-8", errors="replace")
    heights = [int(h) for h in re.findall(r'height="(\d+)"', text)]
    images = re.findall(r'<img[^>]+src="([^"]+)"', text)
    rows = sum(h for h in heights if h < 1024)
    note("html: %d cells, %d images, stacked height %d" % (len(heights), len(images), rows))
    if not (len(images) >= 2 and rows >= 700):
        fail('Save for Web HTML lost its filler cells (use slices:"all", not "user")')
    note("ok  web/ has %d slice images and a complete HTML table" % len(list(Path("web").glob("*.png"))))


run(main)
