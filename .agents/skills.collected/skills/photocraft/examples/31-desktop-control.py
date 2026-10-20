#!/usr/bin/env python3
"""场景：需要真实界面时（读界面状态、用模拟压感笔画画、截窗口图）驱动桌面版的控制通道。

会打开一个 PhotoCraft 窗口，所以默认跳过；显式设置 PCX_DESKTOP=1 才运行。

隔离措施：
 - --new-instance 只另起一个进程，不碰已经打开的 PhotoCraft；
 - PHOTOCRAFT_CONFIG_DIR 指向临时目录，不改用户的首选项、预设、动作和最近文件；
 - 端口从空闲范围里挑，令牌写进读写根之外的私有临时目录（用完即删），读写根目录限定在输出目录；
 - 结束只关自己启动的那个进程；app.quit 会丢弃未保存的修改，不弹提示。

用法: PCX_DESKTOP=1 python 31-desktop-control.py
"""
from __future__ import annotations

import os
import random
import shutil
import socket
import stat
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from pcx import *


def port_open(port: int, timeout=0.5) -> bool:
    with socket.socket() as s:
        s.settimeout(timeout)
        return s.connect_ex(("127.0.0.1", port)) == 0


def main(args):
    if os.environ.get("PCX_DESKTOP") != "1":
        skip("opens a PhotoCraft window; set PCX_DESKTOP=1 to run")
    pcx_init("31-desktop-control")

    cli = init_cli()
    app = Path(str(cli)).with_name("photocraft.exe" if os.name == "nt" else "photocraft")
    if not app.exists():
        skip(f"desktop app not found next to {cli}")
    port = 47000 + random.randrange(2000)
    root = pcx_native(Path.cwd())

    tokdir = Path(tempfile.mkdtemp(prefix="pcx-token."))
    token = tokdir / "control.token"
    try:
        os.chmod(tokdir, stat.S_IRWXU)
    except OSError:
        pass

    step(f"启动独立实例：127.0.0.1:{port}，令牌写入读写根之外的临时目录，配置目录隔离")
    env = os.environ.copy()
    env["PHOTOCRAFT_CONFIG_DIR"] = pcx_native(Path("desktop-config").resolve())
    log = Path("app.log").open("w", encoding="utf-8")
    proc = subprocess.Popen([str(app), "--new-instance", "--control", str(port),
                             "--control-token-file", str(token),
                             "--automation-read-root", root, "--automation-write-root", root],
                            stdout=log, stderr=subprocess.STDOUT, env=env)
    try:
        for _ in range(60):
            if token.exists() and token.stat().st_size and port_open(port):
                break
            time.sleep(0.5)
        if not token.exists():
            print(Path("app.log").read_text(encoding="utf-8", errors="replace")[-1500:], file=sys.stderr)
            fail("control server did not start")

        step("控制通道：认证 → 读界面 → 新建 → 模拟压感笔描边 → 加字 → 保存 → 截窗口")
        demo = _run_client("desktop_control.py", str(port), str(token), "demo")
        Path("transcript.txt").write_text(demo.stdout, encoding="utf-8")
        print(demo.stdout, end="")
        if demo.returncode != 0:
            print(demo.stderr, file=sys.stderr)
            fail("desktop control client failed")

        step("MCP bridge：同一个窗口以 MCP 工具交给 agent")
        env2 = os.environ.copy()
        env2["PCX_BRIDGE_ROOT"] = root
        env2["PHOTOCRAFT_CLI"] = pcx_native(cli)
        bridge = subprocess.run([sys.executable, str(EX_DIR / "clients" / "mcp_bridge.py"), str(port),
                                 str(token), str(Path("bridge-shot.png").resolve())],
                                capture_output=True, text=True, encoding="utf-8", errors="replace",
                                timeout=300, env=env2)
        with Path("transcript.txt").open("a", encoding="utf-8") as fh:
            fh.write(bridge.stdout)
        print(bridge.stdout, end="")
        if bridge.returncode != 0:
            print(bridge.stderr, file=sys.stderr)
            fail("MCP bridge client failed")

        step("退出实例（app.quit 直接退出，不弹未保存提示）")
        quit_ = _run_client("desktop_control.py", str(port), str(token), "quit")
        with Path("transcript.txt").open("a", encoding="utf-8") as fh:
            fh.write(quit_.stdout)
        print(quit_.stdout, end="")
        for _ in range(20):
            if proc.poll() is not None:
                break
            time.sleep(0.5)
        if proc.poll() is None:
            fail("the PhotoCraft instance did not quit")
        note("ok  instance exited")
    finally:
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill()
        log.close()
        shutil.rmtree(tokdir, ignore_errors=True)

    step("核对")
    expect_size("desktop-doc.png", 900, 500)
    expect_file("window.png")
    expect_file("bridge-shot.png")
    if "authenticated" not in Path("transcript.txt").read_text(encoding="utf-8"):
        fail("control channel did not authenticate")


def _run_client(name, *args):
    return subprocess.run([sys.executable, str(EX_DIR / "clients" / name), *args],
                          capture_output=True, text=True, encoding="utf-8", errors="replace",
                          timeout=300, env=os.environ.copy())


run(main)
