#!/usr/bin/env python3
"""场景：从活动主视觉里提炼一套配色，给设计和印刷共用：导出 Adobe 色板（.ase/.aco）、记下 CMYK 值、出一张色卡图。

做法：索引色（自适应调色板、不抖动）求出主色 → 读颜色表 → 建色板组 → 取样点记录 RGB/CMYK → 生成色卡。
取样点（view.colorSamplers）一个文档最多 10 个，颜色数超过 10 时只给前 10 色记 CMYK。

用法: python 11-brand-palette.py [主视觉图片] [颜色数]
"""
from __future__ import annotations

from pathlib import Path

from pcx import *


def main(args):
    src = pcx_input(args[0] if args else "", "template.psd", kind="file")
    n = int(args[1]) if len(args) > 1 else 6
    if not 2 <= n <= 256:
        fail(f"colour count must be 2..256 (got '{args[1]}')")
    ns = min(n, 10)
    pcx_init("11-brand-palette")
    pc("convert", str(src), "key-visual.png")

    step("主色：转索引色（自适应 %d 色、不抖动、不强制黑白）后读颜色表" % n)
    out = pc_run([("image.mode.indexedColor", {"palette": "adaptive", "colors": n, "dither": "none",
                                               "forced": "none"}),
                  ("image.mode.colorTable",)], input="key-visual.png", out="key-visual-indexed.gif", check=True)
    palette = list(pc_result(out, "image.mode.colorTable")["colors"])
    print("  ".join(palette))

    step("色板：新建品牌组，逐色加入，导出 .ase 与 .aco")
    cmds = [("swatches.newGroup", {"name": "Brand"})]
    cmds += [("swatches.add", {"color": c, "name": "Brand %d %s" % (i + 1, c), "group": "Brand"})
             for i, c in enumerate(palette)]
    out = pc_run(cmds + [
        ("swatches.export", {"format": "ase", "group": "Brand", "path": "brand.ase"}),
        ("swatches.export", {"format": "aco", "group": "Brand", "path": "brand.aco"}),
    ], new={"width": 8, "height": 8}, check=True)
    r = pc_result(out, "swatches.export")
    print("exported %s swatches (%s)" % (r["count"], r["format"]))

    step(f"色卡：每色一块，前 {ns} 块上放取样点，得到 RGB 与 CMYK（印刷要用的数值）")
    cmds = []
    for i, hexc in enumerate(palette):
        x = 40 + i * 160
        cmds.append(("shape.create", {"kind": "roundedRect", "rect": [x, 40, 140, 140], "radii": 10,
                                      "fill": hexc}))
        cmds.append(("type.create", {"x": x + 70, "y": 214, "text": hexc, "size": 16, "color": "#111827",
                                     "align": "center"}))
        if i < ns:
            cmds.append(("view.colorSamplers.add", {"x": x + 70, "y": 110}))
    out = pc_run(cmds + [("view.colorSamplers.list",)],
                 new={"width": 80 + n * 160, "height": 250, "background": "#ffffff", "name": "brand-card"},
                 out="brand-card.png", check=True)
    samplers = pc_result(out, "view.colorSamplers.list")["samplers"]
    lines = ["  #%s  rgb(%s)  cmyk(%s)" % (s["number"], ",".join(map(str, s["rgb"])), ",".join(map(str, s["cmyk"])))
             for s in samplers]
    print("\n".join(lines))
    Path("samplers.txt").write_text("\n".join(lines), encoding="utf-8")

    step("核对")
    expect_file("brand.ase")
    expect_file("brand.aco")
    expect_file("key-visual-indexed.gif")   # GIF 重新打开会读成 RGB，调色板数量看 palette 列表
    if len(palette) != n:
        fail(f"expected {n} palette colours, got {len(palette)}")
    note(f"ok  {n} palette colours")
    if len(samplers) != ns:
        fail(f"expected {ns} colour samplers, got {len(samplers)}")
    note(f"ok  {ns} samplers with RGB and CMYK values")
    expect_size("brand-card.png", 80 + n * 160, 250)


run(main)
