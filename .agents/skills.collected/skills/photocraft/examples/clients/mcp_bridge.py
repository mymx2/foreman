#!/usr/bin/env python3
"""把运行中的桌面窗口以 MCP 工具交给 agent（bridge 模式）。由场景脚本执行。

    python clients/mcp_bridge.py <端口> <令牌文件> <截图输出路径>

`photocraft-cli mcp --bridge` 把 MCP 工具转发给桌面窗口：ui_* 工具只在这个模式可用；
doc_place / doc_export_layers / doc_export_data_sets / doc_import_data_sets 在 bridge 模式下仍会被桌面拒绝，
要分层导出、数据组导入导出请用无界面的 serve 或 mcp。
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
import pclib  # noqa: E402


def main(files):
    if len(files) != 3:
        raise SystemExit("usage: mcp_bridge.py <port> <token-file> <screenshot-path>")
    port, token_file, shot = files
    # 根目录必须显式给：从截图路径推父目录会把整个盘授权出去（C:/shot.png 之类）。
    root = os.environ.get("PCX_BRIDGE_ROOT")
    if not root:
        raise SystemExit("set PCX_BRIDGE_ROOT to the directory the window may read and write; "
                         "the bridge root is not inferred from the screenshot path")
    root = str(Path(root).resolve())
    if Path(shot).resolve().parent != Path(root):
        raise SystemExit("screenshot path must sit directly in PCX_BRIDGE_ROOT")
    with pclib.Mcp(bridge=f"127.0.0.1:{port}", token_file=token_file, read_root=root, write_root=root) as mcp:
        mcp.request("initialize", {"protocolVersion": "2025-06-18", "capabilities": {},
                                   "clientInfo": {"name": "photocraft-skill-example", "version": "1.0"}})
        mcp.notify("notifications/initialized")
        names = [t["name"] for t in mcp.tools()]
        print(f"bridge tools: {len(names)}", flush=True)
        ui = mcp.call_tool("ui_inspect")
        print(f"ui_inspect: isError={ui.get('isError')}", flush=True)

        shot_name = Path(shot).name
        # bridge 模式的 ui_screenshot 只回图片内容，不接受 path（参数只有 max_side）
        result = mcp.call_tool("ui_screenshot", {"max_side": 1280})
        if result.get("isError"):
            raise SystemExit("ui_screenshot failed: " + str(result.get("content")))
        images = pclib.content_images(result)
        if not images:
            raise SystemExit("ui_screenshot returned no image content")
        Path(shot).write_bytes(images[0][1])
        print(f"ui_screenshot -> {shot_name}", flush=True)

        # 调整类命令作用于活动图层：文字层上报 "the active layer has no pixels"。
        # 先选回像素层再调；bridge 模式里 canvas 里没画东西时 Background 一直存在。
        mcp.call_tool("command_run", {"id": "layer.select", "params": {"name": "Background"}})
        ran = mcp.call_tool("command_run", {"id": "image.autoContrast"})
        text = "".join(i.get("text", "") for i in ran.get("content", []) if i.get("type") == "text")
        print(f"command_run image.autoContrast: isError={ran.get('isError')} {text[:80]}", flush=True)
        if ran.get("isError"):
            raise SystemExit("image.autoContrast failed on the pixel layer")

        # bridge 模式下的分层导出会被桌面拒绝：这正是文档里说的限制
        refused = mcp.call_tool("doc_export_layers", {"dir": "layers"})
        print(f"doc_export_layers in bridge: isError={refused.get('isError')}", flush=True)
        if not refused.get("isError"):
            raise SystemExit("expected doc_export_layers to be refused in bridge mode")


if __name__ == "__main__":
    try:
        main(sys.argv[1:])
    except pclib.PcError as exc:
        print(f"FAIL {exc}", file=sys.stderr)
        raise SystemExit(1)
