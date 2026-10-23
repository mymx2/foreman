#!/usr/bin/env python3
"""场景：给一个图层写入 XMP、保存 PSD、回读并清除，确认资产目录信息能随文档走。

用法: python 41-layer-xmp.py [图片]      不带参数时用内置风景图
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path

from pcx import *

XMP = """<x:xmpmeta xmlns:x="adobe:ns:meta/">
 <rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">
  <rdf:Description rdf:about="" xmlns:dc="http://purl.org/dc/elements/1.1/">
   <dc:title>PhotoCraft XMP test</dc:title>
  </rdf:Description>
 </rdf:RDF>
</x:xmpmeta>"""


def has_xmp(path: str, layer_name: str) -> bool:
    j = info(path)
    for layer in j.layers:
        if layer.get("name") == layer_name:
            return bool(layer.get("hasXmp"))
    fail(f"layer {layer_name!r} not found in {path}")
    return False


def main(args):
    src = pcx_input(args[0] if args else "", "landscape.jpg", kind="file")
    pcx_init("41-layer-xmp")
    shutil.copy2(src, "in.jpg")

    step("新建一个图层并保存成 PSD")
    pc_run([("layer.new.layer", {"name": "meta"})], input="in.jpg", out="work.psd", check=True)
    if has_xmp("work.psd", "meta"):
        fail("new layer should not have XMP yet")

    step("写入图层 XMP，保存成 PSD")
    r = pc_run([
        ("layer.select", {"name": "meta"}),
        ("layer.xmpMetadata", {"rawData": XMP}),
    ], input="work.psd", out="xmp.psd", check=True)
    result = pc_result(r, "layer.xmpMetadata")
    if not result.get("changed"):
        fail("layer.xmpMetadata did not report changed")
    if result.get("rawData") != XMP:
        fail("write did not echo the XMP packet")
    if not has_xmp("xmp.psd", "meta"):
        fail("PSD did not keep the layer XMP (hasXmp is false)")
    note("ok  XMP written and kept in PSD")

    step("重新打开并回读")
    r = pc_run([
        ("layer.select", {"name": "meta"}),
        ("layer.xmpMetadata", {}),
    ], input="xmp.psd", check=True)
    result = pc_result(r, "layer.xmpMetadata")
    if result.get("rawData") != XMP:
        fail("read back did not match the packet")
    note("ok  XMP read back")

    step("清除 XMP 并再次保存")
    r = pc_run([
        ("layer.select", {"name": "meta"}),
        ("layer.xmpMetadata", {"rawData": None}),
    ], input="xmp.psd", out="cleared.psd", check=True)
    result = pc_result(r, "layer.xmpMetadata")
    if not result.get("changed") or result.get("rawData") is not None:
        fail("clear did not remove the packet")
    if has_xmp("cleared.psd", "meta"):
        fail("hasXmp is still true after clearing")
    note("ok  XMP cleared")


run(main)
