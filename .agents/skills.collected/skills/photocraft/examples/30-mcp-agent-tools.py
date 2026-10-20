#!/usr/bin/env python3
"""场景：让 Claude Code、Qoder 这类 agent 直接把 PhotoCraft 当工具用。
 1) 生成 MCP 服务配置（读写根目录限定在项目目录，最小授权）
 2) 用一个最小 MCP 客户端跑一遍：查命令 → 打开 → 批量编辑 → 取预览图 → 处理工具错误 → 保存

要点：
 - MCP 参数名多为 snake_case（max_side、stop_on_error、visible_only），写错回 JSON-RPC -32602。
 - 工具执行失败是 isError:true 的结果，不是协议错误。
 - 单行请求超过 1 MiB 会让 MCP 进程直接退出：大载荷改走 serve 或 CLI。

用法: python 30-mcp-agent-tools.py [照片]
"""
from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

from pcx import *


def main(args):
    src = pcx_input(args[0] if args else "", "landscape.jpg", kind="file")
    pcx_init("30-mcp-agent-tools")
    shutil.copy2(src, "in.jpg")
    root = str(Path.cwd())

    step("MCP 配置：多数客户端认 mcpServers 结构（Claude Code 的 .mcp.json、Qoder 等同理）")
    cli = init_cli()
    cfg = {"mcpServers": {"photocraft": {"command": pcx_native(cli),
                                        "args": ["mcp", "--automation-read-root", root,
                                                 "--automation-write-root", root]}}}
    Path("mcp.json").write_text(json.dumps(cfg, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(cfg, indent=2, ensure_ascii=False))

    step("最小 MCP 客户端走一遍")
    client = subprocess.run([sys.executable, str(EX_DIR / "clients" / "mcp_client.py"), root, "in.jpg"],
                            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=600,
                            env=os.environ.copy())
    Path("transcript.txt").write_text(client.stdout, encoding="utf-8")
    print(client.stdout, end="")
    if client.returncode != 0:
        print(client.stderr, file=sys.stderr)
        fail("mcp_client failed")

    step("核对")
    transcript = Path("transcript.txt").read_text(encoding="utf-8")
    if not transcript.startswith("server photocraft"):
        fail("MCP handshake failed")
    expect_file("mcp-preview.png")
    expect("mcp-preview.png", lambda k: max(k.width, k.height) == 512, "preview capped at max_side 512")
    expect("mcp-result.psd", lambda k: any(l.name == "Caption" and l.kind == "Type" for l in k.layers),
           "caption is a live type layer")
    expect_file("mcp-result.jpg")
    if "isError=True" not in transcript:
        fail("bad parameters were not reported as a tool error")
    note("ok  tool error surfaced as isError=true")


run(main)
