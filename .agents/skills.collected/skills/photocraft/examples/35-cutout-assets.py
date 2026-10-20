#!/usr/bin/env python3
"""场景：从一张商品图里抠出主体，按 spec 导出多倍图资产，并生成可复跑的资产清单（manifest）。

流程：确认 spec → 语义抠图（选背景→反选→转蒙版）→ 导出透明 PNG → trim_export 裁边/倍率/命名 → 核对 manifest。

要点：
 - 抠图不擦像素：选区转蒙版，原图保留。
 - 有 alpha 用 --trim alpha；无 alpha 的纯色底用 --trim bg --bg-color；两者都别手写阈值。
 - 资产名、尺寸、倍率、格式来自用户 spec；manifest 的 failures 非空不算成功。
 - 原图与母版不动；脚本只写 --out。

用法: python 35-cutout-assets.py [商品图]
"""
from __future__ import annotations

import json
import shutil
import struct
import subprocess
import sys
from pathlib import Path

from pcx import *

TRIM = SCRIPTS_DIR / "trim_export.py"


def png_size(path):
    head = Path(path).read_bytes()[:24]
    if head[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError(f"{path} is not a PNG")
    return struct.unpack(">II", head[16:24])


def main(args):
    src = pcx_input(args[0] if args else "", "product.png", kind="file")
    pcx_init("35-cutout-assets")
    shutil.copy2(src, "product.png")

    step("语义抠图：选主体 → 反选 → 转蒙版（不擦像素）")
    out = pc_run([("layer.removeBackground",), ("layer.renameLayer", {"name": "Product"}),
                  ("document.inspect",)], input="product.png", out="cutout.psd", check=True)
    r = pc_result(out, "document.inspect")
    note("layers %d, hasMask %s" % (len(r["layers"]), any(l.get("hasMask") for l in r["layers"])))

    step("导出透明 PNG 母版（doc.render 只出 PNG；要别的格式用 CLI convert）")
    pc("convert", "cutout.psd", "cutout.png")
    j = info("cutout.png")
    note(f"cutout.png is {j.width}x{j.height} with alpha")

    step("按 spec 出多倍图：1x/2x/3x，padding 12，命名 {name}@{scale}x{ext}")
    trim = subprocess.run([sys.executable, str(TRIM), "cutout.png", "--out", "assets",
                           "--trim", "alpha", "--alpha-threshold", "8", "--padding", "12",
                           "--scales", "1,2,3", "--format", "png", "--name-pattern", "{name}@{scale}x{ext}",
                           "--source-document", "cutout.psd", "--note", "画心；投影不并入",
                           "--manifest", "assets-manifest.json", "--overwrite"],
                          capture_output=True, text=True, encoding="utf-8")
    if trim.returncode != 0:
        print(trim.stderr, file=sys.stderr)
        fail("trim_export failed")
    print("\n".join(Path("assets-manifest.json").read_text(encoding="utf-8").splitlines()[:40]))

    step("核对")
    expect_count("assets", "cutout@*x.png", 3)
    expect_file("assets-manifest.json")
    manifest = json.loads(Path("assets-manifest.json").read_text(encoding="utf-8"))
    outputs = manifest.get("outputs") or []
    if not outputs:
        fail("manifest lists no outputs")
    if manifest.get("failures"):
        fail("manifest reports failures")
    for o in outputs:
        w, h = png_size(o["path"])
        note("  %s: %dx%d (scale %s, padding %s)" % (Path(o["path"]).name, w, h, o["scale"], o["padding"][0]))
    one = next(o for o in outputs if o["scale"] == 1.0)
    for o in outputs:
        # 实测：整个 1x 输出（含 padding）按倍率等比放大——2x = 1x × 2
        expected = round(one["width"] * o["scale"])
        if abs(o["width"] - expected) > 2:
            fail("scale %s is %d wide, expected %d" % (o["scale"], o["width"], expected))
    note("ok  each scale is the 1x asset multiplied by its factor (padding scales with it)")

    step("拒绝覆盖已有输出（默认不覆盖）")
    again = subprocess.run([sys.executable, str(TRIM), "cutout.png", "--out", "assets", "--trim", "alpha",
                            "--padding", "12", "--format", "png", "--name-pattern", "{name}@{scale}x{ext}"],
                           capture_output=True, text=True, encoding="utf-8")
    if again.returncode == 0:
        fail("a second run silently overwrote the assets")
    note("ok  refused to overwrite: " + (again.stderr.strip().splitlines() or ["(no message)"])[0])


run(main)
