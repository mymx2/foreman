"""photocraft-bridge.py 的冒烟测试：内置 fake control server，无需 PhotoCraft。

运行: python scripts/test-bridge.py   （全部通过打印 OK，任何失败 exit 1）
"""
import json
import os
import socketserver
import subprocess
import sys
import tempfile
import threading
from pathlib import Path

BRIDGE = Path(__file__).with_name("photocraft-bridge.py")
PORT = 7917
TOKEN = "a" * 64


class Handler(socketserver.StreamRequestHandler):
    def handle(self):
        while True:
            line = self.rfile.readline()
            if not line:
                return
            req = json.loads(line)
            method, params = req.get("method"), req.get("params")
            if method == "auth":
                ok = params == {"token": TOKEN}
            elif method == "echo":
                ok = True
            else:
                ok = False
            resp = {"id": req.get("id"), "ok": ok}
            if method == "echo":
                resp["result"] = {"got": params}
            elif not ok and method != "auth":
                resp["error"] = f"unknown method `{method}`"
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
    return subprocess.run(
        [sys.executable, str(BRIDGE), "--port", str(port), json.dumps(reqs)],
        capture_output=True, text=True, encoding="utf-8", timeout=timeout, env=env,
    )


def parse(p):
    try:
        return json.loads(p.stdout)
    except json.JSONDecodeError:
        return None


def main():
    srv = serve(PORT, Handler)
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
            p = run_bridge(PORT, reqs)
            assert check(p, parse(p)), (
                f"{name}: rc={p.returncode} stdout={p.stdout[:200]!r} stderr={p.stderr[:200]!r}"
            )
            print(f"ok: {name}")

        p = run_bridge(7918, [["echo"]])
        assert p.returncode != 0 and "cannot reach" in p.stderr
        print("ok: 连接拒绝报错可读")

        hang = serve(7919, HangingHandler)
        try:
            p = run_bridge(7919, [["echo", {"a": 1}], ["hang"]], timeout=330)
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
