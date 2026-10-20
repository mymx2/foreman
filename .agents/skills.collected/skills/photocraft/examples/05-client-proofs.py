#!/usr/bin/env python3
"""场景：拍摄结束给客户发小样。原片格式混杂（JPG/PNG/PSD），要统一成 sRGB JPEG、长边不超过 1200（小图不放大）、
写入版权信息，再拼一张带文件名的联系表方便客户挑片。

用法: python 05-client-proofs.py [原片目录]     只取目录第一层的文件
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path

from pcx import *


def main(args):
    shoot_dir = pcx_input(args[0] if args else "", "", kind="dir")
    pcx_init("05-client-proofs")
    Path("shoot").mkdir()
    if user_mode():
        pcx_copy_dir(shoot_dir, Path("shoot"))
    else:
        for name in ("portrait.jpg", "landscape.jpg", "product.png", "template.psd"):
            shutil.copy2(fixture(name), Path("shoot") / name)

    step("图像处理器：任意可读格式 → JPEG（quality 是 0..12 档位）、适配 1200x1200 且不放大、转 sRGB")
    out = pc_run([("file.scripts.imageProcessor", {"input": "shoot", "output": "proofs", "format": "jpg",
                                                   "quality": 9, "width": 1200, "height": 1200,
                                                   "convertToSrgb": True})], new={"width": 1, "height": 1})
    r = pc_result(out, "file.scripts.imageProcessor")
    print("files: %d, errors: %s" % (len(r["files"]), json.dumps(r["errors"], ensure_ascii=False)))
    if r["errors"]:
        fail("image processor could not convert every file (see errors above)")

    step("统一色彩模式并写版权元数据（XMP），输出到新目录，小样目录不动")
    Path("meta-actions.json").write_text(json.dumps([
        ["file.automate.conditionalModeChange", {"from": "any", "to": "rgb"}],
        ["file.fileInfo", {"author": "Studio North", "copyright": "(c) 2026 Studio North. Proof only.",
                           "copyrightStatus": "copyrighted"}],
    ], indent=2), encoding="utf-8")
    proc = pc("batch", "--actions", "meta-actions.json", "--in", "proofs", "--out", "final", capture=True)
    print(proc.stdout, end="")
    if proc.returncode != 0:
        fail(f"metadata batch failed\n{proc.stderr[-1000:]}")

    step("联系表：3 列 2 行、A4 横向 150ppi、文件名作说明文字")
    out = pc_run([("file.automate.contactSheetII", {"input": "final", "units": "pixels", "width": 1754,
                                                    "height": 1240, "resolution": 150, "columns": 3,
                                                    "rows": 2, "caption": True, "fontSize": 10,
                                                    "flatten": True})],
                 new={"width": 1, "height": 1}, out="contact-sheet.jpg", extra=("--quality", "90"))
    r = pc_result(out, "file.automate.contactSheetII")
    print("pages: %s, images: %s" % (r["pages"], r["images"]))

    step("核对：数量、长边（大图缩到 1200，小图保持原尺寸）、版权字段")
    sources = sorted(p for p in Path("shoot").iterdir() if p.is_file())
    expect_count("final", "*.jpg", len(sources))
    for src in sources:
        want = min(1200, max(info(src).width, info(src).height))
        got = info(Path("final") / (src.stem + ".jpg"))
        if max(got.width, got.height) != want:
            fail(f"final/{src.stem}.jpg long edge is {max(got.width, got.height)}, expected {want}")
        note(f"ok  final/{src.stem}.jpg long edge is {want}")
    first = sorted(Path("final").glob("*.jpg"))[0]
    copyright_text = pc_result(pc_run([("file.fileInfo", {})], input=str(first)), "file.fileInfo")["copyright"]
    if "Studio North" not in (copyright_text or ""):
        fail(f"copyright not written: {copyright_text}")
    note(f"ok  copyright: {copyright_text}")
    expect_size("contact-sheet.jpg", 1754, 1240)


run(main)
