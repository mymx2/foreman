#!/usr/bin/env python3
"""场景：模板里的文字换掉以后，仍要在指定区域内上下左右居中。

区域固定为 [x,y,w,h]。段落文字的水平 align 是真约束；垂直方向没有对齐字段，
所以每次改字后都要用选区 + layer.align.{horizontal,vertical}Centers 把墨迹框重新对到区域中心。
换行是否完整看 type.info.lines 的 end，不要看 text（框放不下时 text 仍是全文）。

用法: python 38-text-replace-center.py
"""
from __future__ import annotations

from pcx import *

REGION = [120, 120, 660, 240]                 # x, y, w, h
CENTRE = (REGION[0] + REGION[2] / 2, REGION[1] + REGION[3] / 2)


def ink_centre(bounds):
    return ((bounds[0] + bounds[2]) / 2, (bounds[1] + bounds[3]) / 2)


def headline(path):
    out = pc_run([("layer.select", {"name": "Headline"}), ("type.info", {})], input=path, check=True)
    return pc_result(out, "type.info")


def verify(path, text):
    r = headline(path)
    cx, cy = ink_centre(r["bounds"])
    note("ink bounds %s, centre (%.1f, %.1f), target (%.1f, %.1f)"
         % (r["bounds"], cx, cy, CENTRE[0], CENTRE[1]))
    if abs(cx - CENTRE[0]) > 1.5 or abs(cy - CENTRE[1]) > 1.5:
        fail(f"text centre ({cx:.1f}, {cy:.1f}) is not the region centre {CENTRE}")
    if r["text"] != text:
        fail(f"text is {r['text']!r}, expected {text!r}")
    laid_out = r["lines"][-1]["end"] if r["lines"] else 0
    if laid_out < len(text):
        fail(f"only {laid_out}/{len(text)} characters were laid out; the box is too small")
    note("ok  %d line(s), all %d characters laid out" % (len(r["lines"]), len(text)))
    return r


def replace(path, text, out_path):
    x, y, w, h = REGION
    pc_run([
        ("layer.select", {"name": "Headline"}),
        ("type.edit", {"text": text}),
        ("select.rect", {"x": x, "y": y, "width": w, "height": h}),
        ("layer.select", {"name": "Headline"}),
        ("layer.align.horizontalCenters", {"to": "selection"}),
        ("layer.align.verticalCenters", {"to": "selection"}),
    ], input=path, out=out_path, check=True)
    return verify(out_path, text)


def main(args):
    pcx_init("38-text-replace-center")
    x, y, w, h = REGION

    step("建卡片：形状面板 + 段落文字，文字初始状态并不在垂直中心")
    pc_run([
        ("shape.create", {"kind": "roundedRect", "rect": REGION, "radii": 16,
                          "fill": "#f1f5f9", "name": "Panel"}),
        ("type.create", {"box": REGION, "text": "Spring Sale", "size": 48,
                         "color": "#0f172a", "align": "center", "name": "Headline"}),
    ], new={"width": 900, "height": 600, "background": "#ffffff", "name": "card"},
       out="card.psd", check=True)
    before = headline("card.psd")
    note("before: ink centre (%.1f, %.1f)" % ink_centre(before["bounds"]))

    step("第一次居中：水平 align 已生效，垂直用选区 + 图层对齐补上")
    pc_run([
        ("select.rect", {"x": x, "y": y, "width": w, "height": h}),
        ("layer.select", {"name": "Headline"}),
        ("layer.align.horizontalCenters", {"to": "selection"}),
        ("layer.align.verticalCenters", {"to": "selection"}),
    ], input="card.psd", out="centered.psd", check=True)
    verify("centered.psd", "Spring Sale")

    step("替换成长标题：改字后重新居中")
    replace("centered.psd", "Autumn Collection 2026", "autumn.psd")

    step("替换成两行文案：换行后墨迹高度变了，仍然要重新居中")
    wrapped = replace("autumn.psd", "Autumn Collection 2026 — Up to 40% Off", "wrapped.psd")
    if len(wrapped["lines"]) < 2:
        fail("expected the long copy to wrap onto at least two lines")

    pc("convert", "wrapped.psd", "wrapped.png", check=True)
    note("ok  wrapped.png written; vertical centring is a one-shot geometry, rerun after every edit")


run(main)
