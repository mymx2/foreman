#!/usr/bin/env python3
"""最小 MCP stdio 客户端：演示 agent 如何通过 `photocraft-cli mcp` 使用 PhotoCraft。由场景脚本执行。

    python clients/mcp_client.py <工作目录> <输入图，相对工作目录>

消息是一行一个 JSON-RPC 2.0 对象。工具结果在 content 里：文本结果是 JSON 字符串，预览图是 base64 PNG。
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
import pclib  # noqa: E402


def log(*parts):
    print(*parts, flush=True)


def must(tool_result):
    if tool_result.get("isError"):
        raise SystemExit(str(pclib.content_json(tool_result) or ""))
    return pclib.content_json(tool_result)


def main(files):
    if len(files) != 2:
        raise SystemExit("usage: mcp_client.py <workspace-dir> <input-relative-to-workspace>")
    root, input_name = files
    with pclib.Mcp(read_root=root, write_root=root) as mcp:
        init = mcp.request("initialize", {"protocolVersion": "2025-06-18", "capabilities": {},
                                         "clientInfo": {"name": "photocraft-skill-example", "version": "1.0"}})
        mcp.notify("notifications/initialized")
        log(f"server {init['serverInfo']['name']} {init['serverInfo']['version']}, protocol {init['protocolVersion']}")

        tools = mcp.tools()
        log(f"{len(tools)} tools: " + ", ".join(t["name"] for t in tools))
        try:
            resources = mcp.request("resources/list")["resources"]
            log("resources: " + (", ".join(r["uri"] for r in resources) or "(none)"))
        except pclib.RpcError:
            log("resources: (none)")

        for command in must(mcp.call_tool("command_list", {"filter": "vibrance"})):
            log(f"  {command['id']}  {command['params'][:80]}")

        opened = must(mcp.call_tool("doc_open", {"path": input_name}))
        log(f"doc_open: {opened['name']} {opened['width']}x{opened['height']}")

        batch = must(mcp.call_tool("command_batch", {
            "steps": [
                {"id": "image.autoContrast", "params": {}},
                {"id": "layer.newAdjustmentLayer.vibrance", "params": {"vibrance": 30}},
                {"id": "type.create", "params": {"x": 40, "y": 80, "text": "Sierra Nevada", "size": 56,
                                                "color": "#ffffff", "name": "Caption"}},
                {"id": "layer.layerStyle.dropShadow", "params": {"opacity": 60, "distance": 3, "size": 8}},
            ],
            "stop_on_error": True,
        }))
        log(f"command_batch: {batch['completed']} completed, {batch['failed']} failed")

        preview = mcp.call_tool("render_preview", {"max_side": 512})
        images = pclib.content_images(preview)
        if not images:
            raise SystemExit("render_preview returned no image content")
        mime, data = images[0]
        Path(root, "mcp-preview.png").write_bytes(data)
        log(f"render_preview: {mime}, saved mcp-preview.png")

        inspect = must(mcp.call_tool("doc_inspect"))
        document = inspect.get("document") or inspect
        log("doc_inspect: " + ", ".join(f"{layer['name']}({layer['kind']})" for layer in document["layers"]))

        # 工具错误是 isError:true 的结果，不是协议错误：读消息、改参数、再试
        bad = mcp.call_tool("command_run", {"id": "filter.blur.gaussianBlur", "params": {"radiuss": 3}})
        message = "".join(item.get("text", "") for item in bad.get("content", []) if item.get("type") == "text")
        log(f"bad params -> isError={bad.get('isError')}: {message[:110]}")
        if not bad.get("isError"):
            raise SystemExit("expected a tool error for a misspelled parameter")

        must(mcp.call_tool("doc_save", {"path": "mcp-result.psd"}))
        must(mcp.call_tool("doc_save", {"path": "mcp-result.jpg"}))
        log("session_list: " + str(must(mcp.call_tool("session_list")))[:120])


if __name__ == "__main__":
    try:
        main(sys.argv[1:])
    except pclib.PcError as exc:
        print(f"FAIL {exc}", file=sys.stderr)
        raise SystemExit(1)
