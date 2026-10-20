#!/usr/bin/env python3
"""场景：接手一份客户 PSD。先看清尺寸、模式、图层结构和警告，再按用途导出交付格式。

用法: python 01-inspect-and-convert.py [文件.psd]      不带参数时用内置海报模板
"""
from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

from pcx import *


def main(args):
    src = pcx_input(args[0] if args else "", "template.psd", kind="file")
    pcx_init("01-inspect-and-convert")
    shutil.copy2(src, "source.psd")   # 只读原件：所有操作都在副本上做（CLI 按内容识别格式，扩展名不影响打开）

    step("文档概况：info --compact 输出单行 JSON，便于程序解析")
    j = info("source.psd")
    print("%sx%s  %s  %s-bit  %d top-level layers" % (j.width, j.height, j.mode, j.depth, len(j.layers)))
    print("\n".join("  #%s %-12s %s%s" % (l.id, l.kind, l.name, "" if l.visible else "  (hidden)") for l in j.layers))
    note(f"warnings: {j.warnings or 'none'}")

    step("完整层级：layer.list flat 模式带 depth/parent，适合遍历组内图层")
    proc = pc("run", "source.psd", "--cmd", "layer.list", "--params", '{"flat":true}', capture=True)
    if proc.returncode != 0:
        fail(f"layer.list failed\n{proc.stderr[-800:]}")
    rows = [json.loads(line) for line in proc.stdout.splitlines() if line.strip().startswith("{")]
    layers = rows[-1]["result"]["layers"]
    print("\n".join("  " * (l["depth"] + 1) + l["name"] + "  bounds=" + json.dumps(l["bounds"]) for l in layers))

    step("顶层文字图层的内容与字体（改稿前先确认）")
    texts = [l for l in j.layers if l.get("text")]
    print("\n".join("  %s: \"%s\"  %s %spt" % (l.name, l.text.text, l.text.font, l.text.sizePt) for l in texts)
          or "  (no top-level type layers)")

    step("按用途导出（扁平格式会拼合图层，stderr 提示 \"N layer(s) flattened\"；WebP 不存 DPI 也会提示）")
    pc("convert", "source.psd", "preview.png")
    pc("convert", "source.psd", "web.jpg", "--quality", "85")
    pc("convert", "source.psd", "web.webp", "--quality", "80")
    pc("convert", "source.psd", "layered.tif", "--tiff-layers")
    pc("convert", "source.psd", "master.pcraft")
    pc("convert", "source.psd", "archive.psb")

    step("核对：和原件的 info 对比，不假设具体有哪些图层")
    want_kinds = sorted(l.kind for l in j.layers)
    expect_size("preview.png", j.width, j.height)
    expect("web.jpg", lambda k: len(k.layers) == 1, "JPEG is flattened to one layer")
    expect("layered.tif", lambda k: len(k.layers) == len(j.layers), "layered TIFF keeps every top-level layer")
    expect("master.pcraft", lambda k: sorted(l.kind for l in k.layers) == want_kinds, "pcraft keeps every layer and its kind")
    expect("archive.psb", lambda k: sorted(l.kind for l in k.layers) == want_kinds, "PSB keeps every layer and its kind")
    expect_file("web.webp")
    if demo_only("template: live type and smart object survive"):
        expect("master.pcraft", lambda k: any(l.kind == "Type" for l in k.layers), "pcraft keeps live type layers")
        expect("archive.psb", lambda k: any(l.kind == "Smart Object" for l in k.layers), "PSB keeps the smart object")


run(main)
