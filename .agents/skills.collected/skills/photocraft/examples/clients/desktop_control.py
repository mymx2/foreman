#!/usr/bin/env python3
"""通过桌面版的 TCP 控制通道驱动一个 PhotoCraft 窗口。由场景脚本执行。

    python clients/desktop_control.py <端口> <令牌文件> [demo|quit]

每个连接的第一帧必须是 auth；之后一行一个 {"id","method","params"}，回复 {"id","ok","result"|"error"}。
这里能做 CLI/serve 做不到的事：读界面状态、用模拟压感笔驱动工具、截取窗口。
demo：新建文档、描边、加字、保存、截图，窗口保持打开；quit：回答"不保存"并退出。
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
import pclib  # noqa: E402


def log(*parts):
    print(*parts, flush=True)


def main(files):
    if len(files) < 2:
        raise SystemExit("usage: desktop_control.py <port> <token-file> [demo|quit]")
    port, token_file = files[0], files[1]
    mode = files[2] if len(files) > 2 else "demo"
    with pclib.Control(port=port, token_file=token_file) as ctl:
        log("authenticated")
        if mode == "demo":
            ui = ctl.call("ui.inspect")
            log(f"ui.inspect: {len(ui)} top-level fields, {len(ui.get('dialogs') or [])} dialogs open")
            ctl.execute("file.new", {"width": 900, "height": 500, "background": "white", "name": "desktop-demo"})
            # 模拟压感笔：down/move/up，压力 0..1，坐标是文档像素
            ctl.call("ui.pointer", {"tool": "brush", "events": [
                {"kind": "down", "x": 120, "y": 300, "pressure": 0.15},
                {"kind": "move", "x": 300, "y": 220, "pressure": 0.6},
                {"kind": "move", "x": 520, "y": 260, "pressure": 1.0},
                {"kind": "up", "x": 780, "y": 200, "pressure": 0.2},
            ]})
            ctl.execute("type.create", {"x": 120, "y": 120, "text": "Drawn over the control channel",
                                        "size": 40, "color": "#1d4ed8"})
            saved = ctl.call("app.save", {"path": "desktop-doc.png"})
            log(f"app.save -> {saved['path']}")
            # 最小化的窗口不绘制：先 ui.focus，否则 ui.screenshot 会等满 60 s 超时
            ctl.call("ui.focus")
            ctl.call("ui.screenshot", {"path": "window.png", "focus": False})
            log("ui.screenshot -> window.png")
            return

        # 退出：app.quit 不会弹"是否保存"，未保存的修改直接丢弃。
        # 需要保存提示时用菜单命令关文档（ui.menu.invoke {"id":"file.close"}），再回答 discard 对话框。
        try:
            ctl.call("app.quit", timeout=5)
        except pclib.TransportError:
            pass  # 进程退出时连接会先断开
        log("quit requested")


if __name__ == "__main__":
    try:
        main(sys.argv[1:])
    except pclib.PcError as exc:
        print(f"FAIL {exc}", file=sys.stderr)
        raise SystemExit(1)
