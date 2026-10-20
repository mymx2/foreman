#!/usr/bin/env python3
"""场景：从零做一张 1080x1350 的活动海报（社媒竖版），交付可继续修改的分层 PSD 和 PNG。

覆盖：渐变预设、形状（布尔相减做圆环、虚线分隔线、预设形状）、文字（字符样式、变形文字、
样式预设）、对齐与编组。中文副标题需要中文字体：先查 type.fonts，一个都没装就跳过本案例（退出码 77），
不让引擎悄悄换成没有中文字形的默认字体。

虚线分隔线用开放路径（kind:"path"，closed:false）描边：kind:"line" 是有宽度的闭合形状，描边会沿两条长边各画一遍，
得到两排错开的虚线。

用法: python 13-promo-poster-from-scratch.py
"""
from __future__ import annotations

import json
from pathlib import Path

from pcx import *

CANDIDATES = ["Alibaba PuHuiTi", "Microsoft YaHei", "PingFang SC", "Hiragino Sans GB", "Noto Sans CJK SC",
              "Noto Sans SC", "Source Han Sans SC", "Source Han Sans CN", "SimHei", "WenQuanYi Micro Hei"]


def main(args):
    pcx_init("13-promo-poster-from-scratch")

    step("选字体：按偏好顺序取第一个已安装的中文字体")
    families = pc_result(pc_run([("type.fonts",)], new={"width": 8, "height": 8}), "type.fonts")["families"]
    cjk = next((f for f in CANDIDATES if f in families), "")
    if not cjk:
        skip(f"no Chinese font installed (looked for {CANDIDATES}); the subtitle would render without CJK glyphs")
    note(f"CJK font: {cjk}")

    step("建文档 → 背景渐变 → 装饰形状 → 文字 → 样式 → 对齐编组")
    out = pc_run([
        ("gradient.presets.apply", {"preset": "Purple 03", "angle": 135}),
        ("layer.renameLayer", {"name": "Backdrop"}),
        ("shape.create", {"kind": "ellipse", "rect": [640, -140, 620, 620], "fill": "#f472b6", "name": "Ring"}),
        ("shape.create", {"kind": "ellipse", "rect": [740, -40, 420, 420], "fill": "#f472b6", "name": "Ring hole"}),
        ("layer.select", {"name": "Ring"}),
        ("layer.select", {"name": "Ring hole", "mode": "add"}),
        ("layer.combineShapes.subtractFrontShape",),
        ("layer.renameLayer", {"name": "Ring"}),
        ("layer.setProps", {"opacity": 0.35}),
        ("shape.presets.place", {"preset": "Burst", "rect": [70, 90, 230, 230], "fill": "#facc15", "name": "Badge"}),
        ("type.create", {"x": 185, "y": 222, "text": "FREE", "size": 44, "color": "#1e1b4b",
                         "align": "center", "name": "Badge text"}),
        ("type.create", {"x": 540, "y": 640, "text": "NIGHT MARKET", "size": 118, "color": "#ffffff",
                         "align": "center", "name": "Headline"}),
        ("style.presets.apply", {"preset": "Neon Pink"}),
        ("type.characterStyle.new", {"name": "Headline", "fromSelection": True}),
        ("type.create", {"x": 540, "y": 740, "text": "夜市美食节 · 周五至周日", "size": 52, "font": cjk,
                         "color": "#fde68a", "align": "center", "name": "Subtitle"}),
        ("shape.create", {"kind": "path",
                          "path": {"subpaths": [{"closed": False, "knots": [[240, 800], [840, 800]]}]},
                          "fill": None,
                          "stroke": {"width": 3, "color": "#fde68a", "dashes": [4, 3], "cap": "round"},
                          "name": "Divider"}),
        ("type.create", {"box": [190, 840, 700, 260],
                         "text": "80+ food stalls, live music and craft beer.\nRiverside Plaza, 18:00 - 23:30.",
                         "size": 34, "color": "#ede9fe", "align": "center", "name": "Body"}),
        ("type.create", {"x": 540, "y": 1240, "text": "LIMITED SEATS", "size": 40, "color": "#facc15",
                         "align": "center", "name": "Tag"}),
        ("type.warpText", {"style": "arc", "bend": 25}),
        ("layer.select", {"name": "Headline"}),
        ("layer.select", {"name": "Subtitle", "mode": "add"}),
        ("layer.select", {"name": "Body", "mode": "add"}),
        ("layer.select", {"name": "Tag", "mode": "add"}),
        ("layer.align.horizontalCenters", {"to": "canvas"}),
        ("layer.groupLayers", {"name": "Copy"}),
    ], new={"width": 1080, "height": 1350, "resolution": 72, "background": "white",
            "name": "night-market-poster"}, out="poster.psd", check=True)
    if out.stderr.strip():
        print(out.stderr)
    pc("convert", "poster.psd", "poster.png")

    step("核对：图层结构、文字可编辑、样式与字符样式已生效、分隔线是单排虚线")
    flat = pc_result(pc_run([("layer.list", {"flat": True})], input="poster.psd"), "layer.list")["layers"]
    print("\n".join("  " + "  " * l["depth"] + "%s (%s)" % (l["name"], l["kind"]) for l in flat))

    j = info("poster.psd")
    if not any(l.kind == "Group" and l.name == "Copy" for l in j.layers):
        fail("copy layers are not grouped")
    note("ok  copy layers grouped")
    dumped = json.dumps(j, ensure_ascii=False)
    if "NIGHT MARKET" not in dumped or "夜市美食节" not in dumped:
        fail("headline and Chinese subtitle are not live type")
    note("ok  headline and Chinese subtitle are live type")
    # Neon Pink 在 info 里不按预设名出现，而是展开成外发光/内发光/颜色叠加
    layer_dump = json.dumps(j.layers, ensure_ascii=False)
    if "Neon Pink" not in layer_dump and "Outer Glow" not in layer_dump:
        fail("Neon Pink style was not applied")
    note("ok  Neon Pink style applied")
    print('character style #%s "%s"' % (pc_result(out, "type.characterStyle.new")["id"],
                                        pc_result(out, "type.characterStyle.new")["name"]))
    if "not installed" in out.stderr:
        fail(f"a font fell back: {out.stderr}")
    expect_size("poster.png", 1080, 1350)

    pcx_ppm("poster.png", "poster.ppm")
    im = Img("poster.ppm")

    def dashed(y):
        runs, on = 0, False
        for x in range(230, 851):
            r, g, b = im.px(x, y)[:3]
            hit = r > 0.9 and g > 0.8 and b < 0.7
            if hit and not on:
                runs += 1
            on = hit
        return runs

    rows = {y: dashed(y) for y in range(792, 809)}
    lit = [y for y, n in rows.items() if n]
    counts = sorted({rows[y] for y in lit})
    note("divider rows %s, dashes per row %s" % (lit, counts))
    if not (lit and max(lit) - min(lit) <= 4 and min(rows[y] for y in lit) >= 20):
        fail("divider is not a single dashed line")
    Path("poster.ppm").unlink(missing_ok=True)
    note("ok  divider is one row of dashes")


run(main)
