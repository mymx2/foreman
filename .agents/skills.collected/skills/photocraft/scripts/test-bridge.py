"""photocraft-bridge.py 的冒烟测试：内置 fake control server，无需 PhotoCraft。

运行: python scripts/test-bridge.py   （全部通过打印 OK，任何失败 exit 1）
"""
import json
import os
import socket
import socketserver
import subprocess
import sys
import tempfile
import threading
from pathlib import Path

BRIDGE = Path(__file__).with_name("photocraft-bridge.py")
TOKEN = "a" * 64


class Handler(socketserver.StreamRequestHandler):
    def handle(self):
        authed = False
        while True:
            line = self.rfile.readline()
            if not line:
                return
            try:
                req = json.loads(line)
            except json.JSONDecodeError:
                self.wfile.write((json.dumps({"id": None, "ok": False, "error": "bad JSON"}) + "\n").encode())
                self.wfile.flush()
                return
            method, params = req.get("method"), req.get("params")
            if method == "auth":
                ok = params == {"token": TOKEN}
                authed = authed or ok
                resp = {"id": req.get("id"), "ok": ok}
            elif not authed:
                resp = {"id": req.get("id"), "ok": False, "error": "auth required"}
            elif method == "echo":
                resp = {"id": req.get("id"), "ok": True, "result": {"got": params}}
            else:
                resp = {"id": req.get("id"), "ok": False, "error": f"unknown method `{method}`"}
            self.wfile.write((json.dumps(resp) + "\n").encode())
            self.wfile.flush()


class HangingHandler(socketserver.StreamRequestHandler):
    def handle(self):
        self.rfile.readline()  # auth
        self.wfile.write((json.dumps({"id": "auth", "ok": True}) + "\n").encode())
        self.wfile.flush()
        self.rfile.readline()  # 第一条请求（echo）
        self.wfile.write((json.dumps({"id": 1, "ok": True, "result": {"got": {"a": 1}}}) + "\n").encode())
        self.wfile.flush()
        self.rfile.readline()  # 第二条请求（hang）
        threading.Event().wait()  # 永不回复
        return


def serve(port, handler):
    srv = socketserver.ThreadingTCPServer(("127.0.0.1", port), handler)
    srv.daemon_threads = True
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


def run_bridge(port, reqs, timeout=15):
    token_file = Path(tempfile.gettempdir()) / f"bridge-test-token-{port}"
    token_file.write_text(TOKEN, encoding="ascii")
    env = {**os.environ, "PHOTOCRAFT_CONTROL_TOKEN_FILE": str(token_file)}
    try:
        return subprocess.run(
            [sys.executable, str(BRIDGE), "--port", str(port), json.dumps(reqs)],
            capture_output=True, text=True, encoding="utf-8", timeout=timeout, env=env,
        )
    finally:
        try:
            token_file.unlink()
        except FileNotFoundError:
            pass


def parse(p):
    try:
        return json.loads(p.stdout)
    except json.JSONDecodeError:
        return None


def main():
    srv = serve(0, Handler)
    port = srv.server_address[1]
    try:
        cases = [
            ("批量与错误路径", [["echo", {"x": 1}], ["boom"]],
             lambda p, r: p.returncode == 0 and r[0].get("got") == {"x": 1} and "ERROR" in r[1]),
            ("params 省略", [["echo"]],
             lambda p, r: r[0].get("got") == {}),
            ("params null", [["echo", None]],
             lambda p, r: r[0].get("got") == {}),
            ("params 数字被拒", [["echo", 3]],
             lambda p, r: p.returncode != 0 and "params must be object" in p.stderr),
            ("0 元素请求被拒", [[]],
             lambda p, r: p.returncode != 0 and "bad request entry" in p.stderr),
            ("unknown method 走 ERROR", [["nope"]],
             lambda p, r: "unknown method" in str(r[0].get("ERROR"))),
        ]
        for name, reqs, check in cases:
            p = run_bridge(port, reqs)
            assert check(p, parse(p)), (
                f"{name}: rc={p.returncode} stdout={p.stdout[:200]!r} stderr={p.stderr[:200]!r}"
            )
            print(f"ok: {name}")

        sock = socket.socket()
        sock.bind(("127.0.0.1", 0))
        closed_port = sock.getsockname()[1]
        sock.close()
        p = run_bridge(closed_port, [["echo"]])
        assert p.returncode != 0 and "cannot reach" in p.stderr
        print("ok: 连接拒绝报错可读")

        hang = serve(0, HangingHandler)
        hang_port = hang.server_address[1]
        try:
            p = run_bridge(hang_port, [["echo", {"a": 1}], ["hang"]], timeout=45)
            r = parse(p)
            assert r[0].get("got") == {"a": 1} and "ERROR" in r[1], f"hang: {r}"
            print("ok: 挂起服务端超时转 ERROR")
        finally:
            hang.shutdown()

        print("OK: all smoke tests passed")
    finally:
        srv.shutdown()


if __name__ == "__main__":
    main()
