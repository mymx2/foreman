#!/usr/bin/env python3
"""场景：把文档排到纸张上出一份打印 PDF，不真的送印；再确认 serve/MCP/桌面会拒绝打印。

用法: python 40-print-proof.py [图片]      不带参数时用内置风景图
"""
from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

from pcx import *


def main(args):
    src = pcx_input(args[0] if args else "", "landscape.jpg", kind="file")
    pcx_init("40-print-proof")
    shutil.copy2(src, "in.jpg")
    root = str(Path.cwd())

    step("CLI：file.print 写 A4 PDF，dryRun 不送印")
    params = {
        "paper": "a4",
        "orientation": "portrait",
        "scaleToFit": True,
        "cornerCropMarks": True,
        "bleed": 0.125,
        "output": "proof.pdf",
        "send": False,
        "dryRun": True,
    }
    r = pc_run([("file.print", params)], input="in.jpg", check=True)
    result = pc_result(r, "file.print")
    print(json.dumps(result, ensure_ascii=False, indent=2))

    expect_file("proof.pdf")
    data = Path("proof.pdf").read_bytes()
    if not data.startswith(b"%PDF-"):
        fail("proof.pdf is not a PDF")
    if result.get("sent"):
        fail("dryRun should not send the job")
    if result.get("pdf") != "proof.pdf":
        fail("file.print did not report the PDF path")
    rect = result.get("imageRect") or []
    if len(rect) != 4 or rect[2] <= 0 or rect[3] <= 0:
        fail(f"bad imageRect: {rect!r}")
    note("ok  PDF written, dryRun did not spool, imageRect is non-empty")

    step("serve：file.* 的 ambient 规则拒绝打印")
    requests = [
        {"id": 1, "method": "doc.open", "params": {"path": "in.jpg"}},
        {"id": 2, "method": "engine.execute",
         "params": {"command": "file.print", "params": {"output": "serve.pdf", "send": False}}},
    ]
    proc = subprocess.run(
        [str(init_cli()), "serve", "--automation-read-root", root, "--automation-write-root", root],
        input="\n".join(json.dumps(x) for x in requests) + "\n",
        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=300,
        env=os.environ.copy(),
    )
    print(proc.stdout, end="")
    if "ambient filesystem paths" not in proc.stdout:
        fail("serve did not refuse file.print with the ambient rule")
    if Path("serve.pdf").exists():
        fail("serve wrote a PDF despite refusing the command")
    note("ok  serve refused file.print")

    step("file.printers 不打开文档也能查队列（无打印机时可以为空）")
    r = pc_run([("file.printers", {})], new={"width": 1, "height": 1}, check=True)
    printers = pc_result(r, "file.printers")
    print(json.dumps(printers, ensure_ascii=False, indent=2))
    note("ok  printer list returned (may be empty)")


run(main)
