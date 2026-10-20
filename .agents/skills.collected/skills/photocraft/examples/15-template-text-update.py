#!/usr/bin/env python3
"""场景：活动从"夏季"换成"秋季"，海报模板的标题、日期、价格、角标都要改。改字后检查：文字是否仍是可编辑的文字层、
英文有无拼写错误、字体有没有缺失、文字框有没有超出安全边距。

用法: python 15-template-text-update.py [模板.psd]
"""
from __future__ import annotations

import re
import shutil
from pathlib import Path

from pcx import *


def main(args):
    src = pcx_input(args[0] if args else "", "template.psd", kind="file")
    pcx_init("15-template-text-update")
    shutil.copy2(src, "template.psd")

    # 按名字选中再改：layer id 跨保存/重开不保证稳定，名字在同一稿内才是可靠锚点。
    step("改稿：全局查找替换 + 按图层整段替换 + 局部替换（保留原有字符样式）")
    out = pc_run([
        ("edit.findAndReplaceText", {"find": "SUMMER", "replace": "AUTUMN", "action": "changeAll",
                                     "caseSensitive": True}),
        ("layer.select", {"name": "DATE"}),
        ("type.edit", {"text": "2026-10-01 — 10-15"}),
        ("layer.select", {"name": "PRICE"}),
        ("type.edit", {"replace": {"start": 1, "end": 4, "text": "159"}}),
        ("layer.select", {"name": "BADGE_TEXT"}),
        ("type.edit", {"text": "-40%"}),
        ("edit.checkSpelling", {"action": "list"}),
        ("type.resolveMissingFonts",),
    ], input="template.psd", out="autumn.psd", check=True)
    print(json_line(pc_result(out, "edit.findAndReplaceText")))

    # 拼写词典是英文（en_US），中文字符会被当成生词，只看含英文字母的结果
    misspelt = [m for m in pc_result(out, "edit.checkSpelling")["misspellings"]
                if re.search(r"[A-Za-z]", m.get("word", ""))]
    note("spelling: " + (", ".join(m["word"] + " -> " + "/".join(m.get("suggestions") or []) for m in misspelt)
                         or "no English misspellings"))
    note("missing fonts: " + json_line(pc_result(out, "type.resolveMissingFonts")))

    step("版式检查：每个文字层都在 60px 安全边距内")
    j = info("autumn.psd")
    lines = []
    out_of_margin = False
    for l in j.layers:
        if l.kind != "Type" or not l.bounds:
            continue
        x, y, w, h = l.bounds
        ok = x >= 60 and x + w <= j.width - 60
        out_of_margin |= not ok
        lines.append("  %s %s \"%s\" x=%d..%d" % ("ok " if ok else "OUT", l.name.ljust(10),
                                                   l.text.text, x, x + w))
    print("\n".join(lines))
    if out_of_margin:
        fail("text runs into the margin")
    pc("convert", "autumn.psd", "autumn.png")

    step("核对：文字已替换且仍是文字层")

    def text_of(name):
        return next(l for l in info("autumn.psd").layers if l.name == name).text.text

    checks = [("TITLE", "AUTUMN SALE"), ("DATE", "2026-10-01 — 10-15"),
              ("PRICE", "¥159 起"), ("BADGE_TEXT", "-40%")]
    for name, want in checks:
        got = text_of(name)
        if got != want:
            fail(f"{name} is {got!r}, expected {want!r}")
        note(f"ok  {name} -> {got}")


def json_line(value):
    import json
    return json.dumps(value, ensure_ascii=False)


run(main)
