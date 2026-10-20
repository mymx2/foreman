#!/usr/bin/env python3
"""场景：背景虚化、锐化的力度客户还没定。把图层转成智能对象后再加滤镜，滤镜就成了可回改的"智能滤镜"：
之后改参数、关掉某个滤镜、甚至替换智能对象内部的内容，都不用从头再来。

用法: python 19-smart-filters-revisable.py [照片]
"""
from __future__ import annotations

import json
import shutil

from pcx import *


def main(args):
    src = pcx_input(args[0] if args else "", "landscape.jpg", kind="file")
    pcx_init("19-smart-filters-revisable")
    shutil.copy2(src, "source.jpg")

    step("转为智能滤镜图层 → 高斯模糊 + USM 锐化（都记录在智能对象上）")
    pc_run([("filter.convertForSmartFilters",),
            ("layer.renameLayer", {"name": "Photo"}),
            ("filter.blur.gaussianBlur", {"radius": 6}),
            ("filter.sharpen.unsharpMask", {"amount": 120, "radius": 1.5, "threshold": 3})],
           input="source.jpg", out="v1.psd", check=True)
    photo = next(l for l in info("v1.psd").layers if l.name == "Photo")
    note(json.dumps(photo.get("smartFilters") or photo, ensure_ascii=False)[:600])

    step("客户反馈：模糊太重、先不要锐化 → 改第 0 个滤镜的半径，关掉第 1 个滤镜")
    pc_run([("layer.select", {"name": "Photo"}),
            ("layer.smartFilter.setParams", {"index": 0, "params": {"radius": 2.5}}),
            ("layer.smartFilter.setVisible", {"index": 1, "visible": False})],
           input="v1.psd", out="v2.psd", check=True)

    step("再改内容：打开智能对象内部 → 调亮 → 存回父文档（滤镜自动重新应用）")
    pc_run([("layer.select", {"name": "Photo"}),
            ("layer.smartObjects.editContents",),
            ("image.adjustments.exposure", {"exposure": 0.4}),
            ("layer.smartObjects.saveContents",),
            ("document.activate", {"document": 0})],
           input="v2.psd", out="v3.psd", check=True)
    for v in ("v1", "v2", "v3"):
        pc("convert", f"{v}.psd", f"{v}.jpg", "--quality", "88")

    step("核对：三个版本在细节区域的像素各不相同，v3 仍是智能对象")

    def sample(path):
        out = pc_run([("document.pixel", {"x": 1150, "y": 480}), ("document.pixel", {"x": 820, "y": 260}),
                      ("document.pixel", {"x": 705, "y": 735}), ("document.pixel", {"x": 210, "y": 330})],
                     input=path)
        rows = [row for row in out if row.get("command") == "document.pixel"]
        return [row["result"][:3] for row in rows]

    def differ(a, b):
        return any(abs(x - y) > 0.01 for pa, pb in zip(a, b) for x, y in zip(pa, pb))

    a, b, c = sample("v1.jpg"), sample("v2.jpg"), sample("v3.jpg")
    if not differ(a, b):
        fail("v2 looks the same as v1")
    if not differ(b, c):
        fail("v3 looks the same as v2")
    note("ok  each revision changed the result")
    expect("v3.psd", lambda k: next(l for l in k.layers if l.name == "Photo").kind == "Smart Object",
           "Photo is still a smart object after the edits")


run(main)
