#!/usr/bin/env python3
"""场景：agent 要对同一张图反复"改 → 看预览 → 不满意就回退 → 再改"，还要处理多文档和耗时滤镜。
这类交互用常驻的 serve 会话：文档、历史、快照、预设都留在一个进程里，不必每步重开文件。

两种用法：直接向 stdio serve 灌 JSON 行（适合固定流程），或用 clients/serve_session.py 按结果做判断。

用法: python 29-serve-agent-session.py [照片]
"""
from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

from pcx import *


def main(args):
    src = pcx_input(args[0] if args else "", "landscape.jpg", kind="file")
    pcx_init("29-serve-agent-session")
    shutil.copy2(src, "in.jpg")
    root = str(Path.cwd())

    step("固定流程：向 stdio serve 一次喂多行请求（路径相对授权根目录）")
    requests = [
        {"id": 1, "method": "doc.open", "params": {"path": "in.jpg"}},
        {"id": 2, "method": "batch", "params": {"steps": [{"command": "image.autoContrast"},
                                                          {"command": "filter.sharpen.smartSharpen",
                                                           "params": {"amount": 60}}]}},
        {"id": 3, "method": "doc.save", "params": {"path": "quick.jpg", "quality": 85}},
    ]
    cli = init_cli()
    proc = subprocess.run([str(cli), "serve", "--automation-read-root", root, "--automation-write-root", root],
                          input="\n".join(json.dumps(r) for r in requests) + "\n",
                          capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=300,
                          env=os.environ.copy())
    Path("quick.jsonl").write_text(proc.stdout, encoding="utf-8")
    print(proc.stdout, end="")
    if '"id": 3, "ok": true' not in proc.stdout and '"id":3,"ok":true' not in proc.stdout.replace(" ", ""):
        fail("quick pipeline did not save")

    step("交互流程：Python 客户端（快照回退、后台任务轮询、会话内预设、拒绝越权路径）")
    client = subprocess.run([sys.executable, str(EX_DIR / "clients" / "serve_session.py"), root, "in.jpg"],
                            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=600,
                            env=os.environ.copy())
    Path("transcript.txt").write_text(client.stdout, encoding="utf-8")
    print(client.stdout, end="")
    if client.returncode != 0:
        print(client.stderr, file=sys.stderr)
        fail("serve_session client failed")

    step("核对")
    expect_file("quick.jpg")
    expect_file("preview-pass1.png")
    expect_file("preview-pass2.png")
    expect("graded.psd", lambda k: any(l.name == "Soft glow" and l.blend == "Soft Light" for l in k.layers),
           "soft glow layer survived undo/redo")
    expect("graded.psd", lambda k: len([l for l in k.layers if l.kind == "Adjustment"]) == 2,
           "only the gentle second-pass adjustments remain")
    transcript = Path("transcript.txt").read_text(encoding="utf-8")
    if "refused (path traversal)" not in transcript:
        fail("path traversal was not refused")
    if "refused (ambient file command)" not in transcript:
        fail("ambient file command was not refused")
    note("ok  out-of-root path and ambient file command refused")
    if (Path.cwd().parent / "escape.png").exists():
        fail("a file escaped the workspace")


run(main)
