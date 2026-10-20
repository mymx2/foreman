#!/usr/bin/env python3
"""场景：卡片上的文字要在框里居中、改字后重新排版、并且在改动前后判断有没有被框裁掉。

要点：PhotoCraft 的段落样式没有垂直对齐，只有水平 align；"垂直居中"要么把段落框收缩到墨迹高度，
      要么用 select.rect + layer.align.verticalCenters {to:"selection"}。改字后这两步都要重跑。
      type.edit 把框改小，超出的行不进 layout，但 text 字段仍是全文，要查 type.info 的 lines。

用法: python 32-text-in-box.py
"""
from __future__ import annotations

from pathlib import Path

from pcx import *

TXT = "The quick brown fox\njumps over the lazy dog\nand keeps running\nthrough the field"


def main(args):
    pcx_init("32-text-in-box")

    step("段落框：水平居中是真约束，改字后每行中心不变")
    pc_run([("shape.create", {"kind": "roundedRect", "rect": [80, 80, 640, 200], "radii": 16,
                              "fill": "#f1f5f9", "name": "Card"}),
            ("type.create", {"box": [120, 120, 560, 120], "text": TXT, "size": 28, "color": "#0f172a",
                             "align": "center", "name": "Body"})],
           new={"width": 800, "height": 600, "background": "#ffffff", "name": "card"},
           out="card.psd", check=True)

    def body_info(path="card.psd"):
        # type.info 只认活动层或 layer id；先用名字选中，避免依赖打开文件时谁恰好是活动层。
        return pc_result(pc_run([("layer.select", {"name": "Body"}), ("type.info",)], input=path), "type.info")

    def centre_x(path="card.psd"):
        r = body_info(path)
        return (r["bounds"][0] + r["bounds"][2]) / 2

    before = centre_x()
    pc_run([("layer.select", {"name": "Body"}), ("type.edit", {"text": "Shorter title"})], input="card.psd",
           out="card2.psd", check=True)
    after = centre_x("card2.psd")
    note("ink centre before %.2f, after %.2f (box centre 400)" % (before, after))
    if abs(before - after) >= 2 or abs(before - 400) >= 2.5:
        fail("text centre moved after an edit")
    note("ok  horizontal centring survives a text edit")

    step("垂直方向的两种做法")
    ink = body_info("card.psd")["bounds"]
    x0, y0, x1, y1 = ink
    note("ink box: x %.1f..%.1f, y %.1f..%.1f" % (x0, x1, y0, y1))
    # type.info 的 bounds 是 [x0,y0,x1,y1]；改框用 type.edit 的 box [x,y,w,h]
    shrink = {"box": [round(x0), round(y0), round(x1 - x0) + 1, round(y1 - y0) + 1]}
    pc_run([("layer.select", {"name": "Body"}), ("type.edit", shrink)], input="card.psd",
           out="centered.psd", check=True)
    orig_lines = len(body_info("card.psd")["lines"])
    lines = len(body_info("centered.psd")["lines"])
    note("lines laid out before %d, after shrinking to the ink height %d" % (orig_lines, lines))
    if not (lines == orig_lines and orig_lines >= 3):
        fail("shrinking to the ink height dropped lines")

    # 做法二：选区 + 图层对齐（不需要盒子刚好是墨迹高度）
    pc_run([("select.rect", {"x": 120, "y": 120, "width": 560, "height": 120}),
            ("layer.select", {"name": "Body"}),
            ("layer.align.verticalCenters", {"to": "selection"})],
           input="card.psd", out="aligned.psd", check=True)
    bounds = body_info("aligned.psd")["bounds"]
    cy = (bounds[1] + bounds[3]) / 2
    note("after align.verticalCenters: ink centre y %.2f (selection centre 180)" % cy)
    if abs(cy - 180) > 2:
        fail("align.verticalCenters did not move the text to the selection centre")
    note("ok  the selection + align recipe works")

    step("溢出：把框改小，超出的行被丢弃（text 仍是全文）")
    small = {"box": [round(x0), round(y0), round(x1 - x0) + 1, 40]}
    pc_run([("layer.select", {"name": "Body"}), ("type.edit", small)], input="card.psd",
           out="clipped.psd", check=True)
    r = body_info("clipped.psd")
    note("lines laid out %d, characters in the model %d" % (len(r["lines"]), len(r["text"])))
    if not (len(r["lines"]) < orig_lines and len(r["text"]) > 20):
        fail("clipped.psd did not show the overflow (lines should shrink, text stay)")
    note("ok  overflow appears in type.info.lines, not in text")
    expect("clipped.psd", lambda k: k.width == 800 and k.height == 600, "clipped.psd keeps the canvas")

    step("注意：type.info 的 bounds 是 [x0,y0,x1,y1]，document.inspect 的是 [x,y,w,h]")
    t = body_info("card.psd")["bounds"]
    i = next(l.bounds for l in info("card.psd").layers if l.name == "Body")
    note("type.info bounds %s [x0,y0,x1,y1] | inspect bounds %s [x,y,w,h]" % (t, i))
    if not (abs(t[0] - i[0]) < 1 and abs(t[1] - i[1]) < 1
            and abs((t[2] - t[0]) - i[2]) < 2 and abs((t[3] - t[1]) - i[3]) < 2):
        fail("the two bounds shapes disagree")
    note("ok  both bounds describe the same ink box")


run(main)
