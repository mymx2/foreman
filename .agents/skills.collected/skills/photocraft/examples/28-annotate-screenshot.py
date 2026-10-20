#!/usr/bin/env python3
"""场景：给测试/客服工单标注截图：红框框出"API Keys"菜单，箭头指过去，编号圆标出两处问题，手绘圈出套餐信息，
加一个说明气泡，再留一条审阅批注。标注都在独立图层上，PSD 留底，PNG 发出去。

要点：工单截图里往往带密钥、卡号、姓名，标注版是要发出去的——先按 10-privacy-redaction 的做法把机密涂掉再标注，
      或者用已经脱敏的截图。脚本默认对内置截图先做一遍脱敏。

用法: python 28-annotate-screenshot.py [截图]     用户截图必须先用 10 脱敏，并设 PCX_PRE_REDACTED=1
"""
from __future__ import annotations

import math
import os
import shutil
from pathlib import Path

from pcx import *


def main(args):
    src = pcx_input(args[0] if args else "", "screenshot.png", kind="file")
    pcx_init("28-annotate-screenshot")
    shutil.copy2(src, "shot.png")

    if demo_only("built-in screenshot: cover its secrets before annotating"):
        step("先脱敏内置截图：姓名、邮箱、API key、卡号实心覆盖，头像马赛克")
        pc_run([
            ("select.rect", {"x": 436, "y": 140, "width": 140, "height": 38}),
            ("select.rect", {"x": 436, "y": 180, "width": 262, "height": 32, "mode": "add"}),
            ("select.rect", {"x": 466, "y": 334, "width": 300, "height": 30, "mode": "add"}),
            ("select.rect", {"x": 466, "y": 398, "width": 236, "height": 30, "mode": "add"}),
            ("edit.fill", {"contents": "color", "color": "#111827"}),
            ("select.deselect",),
            ("select.rect", {"x": 306, "y": 122, "width": 108, "height": 108}),
            ("filter.pixelate.mosaic", {"cellSize": 14}),
            ("select.deselect",),
        ], input="shot.png", out="shot-redacted.png", check=True)
        Path("shot-redacted.png").replace("shot.png")
    else:
        # 标注版是要发出去的：用户截图必须已经脱敏。没有显式确认就停下，不静默产出一张带 PII 的图。
        if os.environ.get("PCX_PRE_REDACTED") != "1":
            fail("a user screenshot must be redacted before annotating: run 10-privacy-redaction.py first, "
                 "then re-run with PCX_PRE_REDACTED=1 (annotations are not redaction)")
        note("user screenshot: confirmed pre-redacted via PCX_PRE_REDACTED=1")

    # 围住"Pro (annual)"的手绘椭圆：沿椭圆取点，带轻微抖动更像手画
    cx, cy, rx, ry = 528, 477, 92, 26
    circle = []
    for i in range(41):
        t = (i / 40) * 2.1 * math.pi
        j = 1 + 0.04 * math.sin(i * 1.7)
        circle.append([round(cx + rx * j * math.cos(t)), round(cy + ry * j * math.sin(t)), 1])

    step("标注图层：红框、箭头、编号、手绘圈、说明气泡、审阅批注")
    pc_run([
        ("layer.new.layer", {"name": "Highlight box"}),
        ("select.rect", {"x": 22, "y": 176, "width": 150, "height": 32}),
        ("edit.stroke", {"width": 3, "color": "#ef4444", "location": "outside"}),
        ("select.deselect",),
        ("shape.presets.place", {"preset": "Arrow Left", "rect": [184, 168, 96, 48], "fill": "#ef4444",
                                 "name": "Arrow"}),
        ("shape.create", {"kind": "ellipse", "rect": [1196, 330, 36, 36], "fill": "#ef4444", "name": "Badge 1"}),
        ("type.create", {"x": 1214, "y": 356, "text": "1", "size": 20, "color": "#ffffff", "align": "center",
                         "name": "Badge 1 label"}),
        ("shape.create", {"kind": "ellipse", "rect": [1196, 394, 36, 36], "fill": "#ef4444", "name": "Badge 2"}),
        ("type.create", {"x": 1214, "y": 420, "text": "2", "size": 20, "color": "#ffffff", "align": "center",
                         "name": "Badge 2 label"}),
        ("layer.new.layer", {"name": "Markup"}),
        ("paint.stroke", {"points": circle, "size": 4, "hardness": 1, "color": "#f59e0b", "smoothing": 0.5}),
        ("shape.create", {"kind": "roundedRect", "rect": [860, 580, 380, 96], "radii": 12, "fill": "#111827",
                          "name": "Callout"}),
        ("type.create", {"box": [880, 596, 340, 70],
                         "text": "1 Key exposed in ticket #482: rotate it.\n2 Card shown unmasked to support staff.",
                         "size": 17, "color": "#ffffff", "name": "Callout text"}),
        ("notes.add", {"x": 470, "y": 356, "text": "Rotate this key before Friday (security)", "author": "QA"}),
    ], input="shot.png", out="annotated.psd", check=True)
    pc("convert", "annotated.psd", "annotated.png")

    step("核对")
    j = info("annotated.psd")
    if len(j.layers) < 10:
        fail("annotation layers are missing")
    note("ok  background + annotation layers")
    expect("annotated.psd", lambda k: k.notes is not None and len(k.notes) == 1, "review note kept in the PSD")
    r = pc_result(pc_run([("document.pixel", {"x": 97, "y": 174})], input="annotated.png"), "document.pixel")
    red = ",".join(str(round(v * 255)) for v in r[:3])
    if red != "239,68,68":
        fail(f"highlight box stroke not found (got {red})")
    note("ok  red highlight box drawn around the menu item")

    if demo_only("built-in screenshot: the secret areas stay covered after annotating"):
        # 出口检查：原图的密钥/卡号区域在标注版里仍然是深色实心块
        pcx_ppm("annotated.png", "ann.ppm")
        im = Img("ann.ppm")
        bad = []
        for name, (x, y, w, h) in {"API key": (470, 340, 280, 16), "card": (470, 404, 220, 16),
                                   "name": (440, 146, 130, 24)}.items():
            m, sd = im.stats(x, y, w, h)
            if max(m) > 0.25 or max(sd) > 0.05:
                bad.append("%s mean %.2f sd %.2f" % (name, max(m), max(sd)))
        note(("ok  " if not bad else "BAD ") + "secret areas covered: %s" % ("; ".join(bad) or "all three"))
        Path("ann.ppm").unlink(missing_ok=True)
        if bad:
            fail("annotated.png exposes secrets")
        note("ok  the redacted areas are still covered in annotated.png")


run(main)
