#!/usr/bin/env python3
"""photocraft-bridge.py — PhotoCraft control 端口的 JSON-lines 调用底座。

stdin:  一行 JSON，形如 [[method, params], ...]（params 可省略或为 null）
stdout: 一行 JSON，每个请求对应一个结果（成功为 result，失败为 {"ERROR": ...}）

连接目标优先级：
1. --port 显式指定（连接失败即报错，不回退）
2. 环境变量 PHOTOCRAFT_CONTROL_PORT
3. 端口探测（7878 起，连续试 4 个；token 同步从 PHOTOCRAFT_CONTROL_TOKEN_FILE
   或 %APPDATA%/Photocraft/control.token 读取）

安全注意：探测模式会把 token 发给 7878–7881 中第一个完成 auth 的本地监听进程。
不信任本机环境时，显式用 --port 或 PHOTOCRAFT_CONTROL_PORT 指定端口。

GUI 裸启动（不带 --control）时 PhotoCraft 自动生成端口与 token，
token 文件由 GUI 写入其配置目录；探测到端口后先 auth 再发请求。
"""
import json
import os
import socket
import sys

CONNECT_TIMEOUT = 5
IO_TIMEOUT = 300

def _candidate_ports():
    env = os.environ.get("PHOTOCRAFT_CONTROL_PORT")
    if env:
        return [int(env)]
    return [7878, 7879, 7880, 7881]

def _token_file():
    for cand in (
        os.environ.get("PHOTOCRAFT_CONTROL_TOKEN_FILE"),
        os.path.join(os.environ.get("APPDATA", ""), "Photocraft", "control.token"),
    ):
        if cand and os.path.isfile(cand):
            return cand
    return None

def _normalize(req):
    """把请求整形为 (method, params)。params 仅接受 dict / None。"""
    if not isinstance(req, list) or len(req) < 1:
        raise ValueError(f"bad request entry: {req!r}")
    method = req[0]
    params = req[1] if len(req) >= 2 else None
    if params is not None and not isinstance(params, dict):
        raise ValueError(f"params must be object or null: {req!r}")
    return method, params

def call(reqs, port=None, token=None):
    """执行一批 control 请求，返回结果列表。失败项是 {"ERROR": ...}。"""
    token = token or (open(tf).read().strip() if (tf := _token_file()) else None)
    last_err = None
    for p in ([port] if port else _candidate_ports()):
        try:
            s = socket.create_connection(("127.0.0.1", p), timeout=CONNECT_TIMEOUT)
        except OSError as e:
            last_err = e
            continue
        try:
            s.settimeout(IO_TIMEOUT)
            f = s.makefile("rwb")
            f.write((json.dumps({"id": "auth", "method": "auth", "params": {"token": token}}) + "\n").encode())
            f.flush()
            auth = json.loads(f.readline())
            if not auth.get("ok"):
                last_err = f"auth failed on port {p}"
                continue
            out = []
            for i, req in enumerate(reqs, 1):
                method, params = _normalize(req)
                f.write((json.dumps({"id": i, "method": method, "params": params if params is not None else {}}) + "\n").encode())
                f.flush()
                try:
                    resp = json.loads(f.readline())
                except (TimeoutError, OSError) as e:
                    out.append({"ERROR": f"timeout/IO after {i - 1} replies: {e}"})
                    break
                out.append(resp.get("result") if resp.get("ok") else {"ERROR": resp.get("error")})
            return out
        finally:
            s.close()
    raise SystemExit(f"cannot reach PhotoCraft control port: {last_err}")

def main():
    args = sys.argv[1:]
    port = None
    if args and args[0] == "--port":
        if len(args) < 2:
            raise SystemExit("usage: photocraft-bridge.py [--port N] '[[method, params], ...]'")
        port = int(args[1])
        args = args[2:]
    reqs = json.loads(args[0] if args else sys.stdin.read())
    print(json.dumps(call(reqs, port=port), ensure_ascii=False))

if __name__ == "__main__":
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, OSError):
            pass
    main()
