#!/usr/bin/env python3
"""Self-test for control.py and pclib.Control (maintainers: execute after changing either).

  python <skill-dir>/scripts/test_control.py           hermetic: fake server, no PhotoCraft needed
  python <skill-dir>/scripts/test_control.py --live    also start a real `photocraft-cli serve --port`
  python <skill-dir>/scripts/test_control.py --live --idle   plus a real 31 s idle-drop reconnect

The fake listener behaves like PhotoCraft's (desktop control and serve --port): the first
frame must be `auth` with the right token, otherwise it answers `authentication required`
and closes; a repeat auth gets `already authenticated`; unauthenticated connections close
at the auth deadline and idle ones after the idle timeout. Children run with every
PHOTOCRAFT_CONTROL_* variable removed (and PYTHONIOENCODING=gbk to imitate a GBK console),
so a token in the caller's environment can neither leak in nor break the test. --live runs
serve with a temporary token file, config dir and automation root, then stops it.
Exit codes: 0 all checks passed, 1 a check failed, 2 setup problem (e.g. no CLI for --live).
"""
from __future__ import annotations

import argparse
import collections
import contextlib
import json
import os
import secrets
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import pclib  # noqa: E402

CONTROL = HERE / "control.py"
NOT_RUN = ("timeout: not run — the request was still queued when its 60s deadline passed, so it was "
           "dropped before dispatch and is safe to re-send")
NO_REPLY = ("timeout: no reply in 60s — the command may still be running and may still apply, or the "
            "app was not drawing frames")
SECRETS: set[str] = set()


class Failed(Exception):
    pass


def check(cond: bool, what: str) -> None:
    if not cond:
        raise Failed(what)


# --------------------------------------------------------------------------- fake listener
class FakeControl:
    """A loopback listener that answers like PhotoCraft's control transport."""

    def __init__(self, token: str, *, idle: float = 30.0, auth_deadline: float = 10.0, silent: bool = False):
        self.token = token
        self.idle = idle
        self.auth_deadline = auth_deadline
        self.silent = silent
        self.lock = threading.Lock()
        self.connections = 0
        self.tokens_seen: list[str] = []
        self.received: collections.Counter = collections.Counter()
        self.server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server.bind(("127.0.0.1", 0))
        self.server.listen(16)
        self.port = self.server.getsockname()[1]
        self.closed = False
        threading.Thread(target=self._accept, daemon=True).start()

    def _accept(self) -> None:
        while not self.closed:
            try:
                conn, _ = self.server.accept()
            except OSError:
                return
            with self.lock:
                self.connections += 1
            threading.Thread(target=self._serve, args=(conn,), daemon=True).start()

    @staticmethod
    def _reply(conn: socket.socket, obj: dict) -> None:
        conn.sendall((json.dumps(obj, ensure_ascii=False) + "\n").encode("utf-8"))

    def _serve(self, conn: socket.socket) -> None:
        reader = conn.makefile("rb")
        try:
            conn.settimeout(self.auth_deadline)
            try:
                first = reader.readline()
            except OSError:
                return
            if not first:
                return
            if self.silent:
                time.sleep(self.auth_deadline)
                return
            try:
                req = json.loads(first)
            except json.JSONDecodeError:
                req = {}
            supplied = ((req.get("params") or {}).get("token") if isinstance(req.get("params"), dict) else None)
            if isinstance(supplied, str):
                with self.lock:
                    self.tokens_seen.append(supplied)
            if req.get("method") != "auth" or supplied != self.token:
                self._reply(conn, {"id": req.get("id"), "ok": False, "error": "authentication required"})
                return
            self._reply(conn, {"id": req.get("id"), "ok": True, "result": {"authenticated": True}})
            conn.settimeout(self.idle)
            while True:
                try:
                    raw = reader.readline()
                except OSError:
                    return   # idle timeout: drop the connection like PhotoCraft does
                if not raw:
                    return
                req = json.loads(raw)
                method, params, rid = req.get("method"), req.get("params"), req.get("id")
                with self.lock:
                    self.received[method] += 1
                if method == "auth":
                    self._reply(conn, {"id": rid, "ok": False, "error": "already authenticated"})
                elif method == "echo":
                    self._reply(conn, {"id": rid, "ok": True, "result": {"got": params}})
                elif method == "sleep":
                    time.sleep(float((params or {}).get("seconds", 1)))
                    self._reply(conn, {"id": rid, "ok": True, "result": {"slept": True}})
                elif method == "gui.notrun":
                    self._reply(conn, {"id": rid, "ok": False, "error": NOT_RUN})
                elif method == "gui.noreply":
                    self._reply(conn, {"id": rid, "ok": False, "error": NO_REPLY})
                elif method == "drop":
                    return
                else:
                    self._reply(conn, {"id": rid, "ok": False, "error": f"unknown method `{method}` (try `methods`)"})
        except OSError:
            return
        finally:
            with contextlib.suppress(OSError):
                reader.close()
                conn.close()

    def close(self) -> None:
        self.closed = True
        with contextlib.suppress(OSError):
            self.server.close()


# --------------------------------------------------------------------------- helpers
def new_token() -> str:
    token = secrets.token_hex(32)
    SECRETS.add(token)
    return token


def child_env(**extra) -> dict:
    env = {k: v for k, v in os.environ.items() if not k.startswith("PHOTOCRAFT_CONTROL_")}
    env["PYTHONIOENCODING"] = "gbk"
    for key, value in extra.items():
        if value is None:
            env.pop(key, None)
        else:
            env[key] = str(value)
    return env


def run_control(args: list[str], *, stdin: str | None = None, env: dict | None = None, timeout: float = 60):
    proc = subprocess.run([sys.executable, str(CONTROL), *args],
                          input=stdin.encode("utf-8") if stdin is not None else None,
                          capture_output=True, env=env if env is not None else child_env(), timeout=timeout)
    out = proc.stdout.decode("utf-8")          # strict: GBK leaking into stdout fails here
    err = proc.stderr.decode("utf-8", "replace")
    for secret in SECRETS:
        check(secret not in out and secret not in err, "a token was printed by control.py")
    check("Traceback" not in err, f"control.py printed a traceback: {err[-400:]}")
    lines = [json.loads(line) for line in out.splitlines() if line.strip()]
    return proc.returncode, lines, err


def statuses(lines) -> list[str]:
    return [line["status"] for line in lines]


@contextlib.contextmanager
def env_vars(**values):
    saved = {k: os.environ.get(k) for k in values}
    try:
        for key, value in values.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = str(value)
        yield
    finally:
        for key, value in saved.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


# --------------------------------------------------------------------------- hermetic cases
def hermetic(tmp: Path) -> list[str]:
    done: list[str] = []
    token = new_token()
    tok = tmp / "good.token"
    tok.write_text(token + "\n", encoding="ascii")
    fake = FakeControl(token)
    base = ["--port", str(fake.port), "--token-file", str(tok)]

    def case(name: str, fn) -> None:
        try:
            fn()
        except Failed:
            raise
        except Exception as exc:  # noqa: BLE001 - report which case broke, not a bare traceback
            raise Failed(f"{name}: unexpected {type(exc).__name__}: {exc}") from exc
        done.append(name)
        print(f"ok: {name}", flush=True)

    def realism():
        # E21: the fake must behave like PhotoCraft or the other cases prove nothing.
        with socket.create_connection(("127.0.0.1", fake.port), timeout=5) as s:
            f = s.makefile("rwb")
            f.write(b'{"id":1,"method":"echo"}\n')
            f.flush()
            check(json.loads(f.readline()).get("error") == "authentication required", "non-auth first frame")
            check(f.readline() == b"", "fake closes the socket after a failed auth")
        with socket.create_connection(("127.0.0.1", fake.port), timeout=5) as s:
            f = s.makefile("rwb")
            for _ in range(2):
                f.write((json.dumps({"id": "auth", "method": "auth", "params": {"token": token}}) + "\n").encode())
                f.flush()
            check(json.loads(f.readline()).get("ok") is True, "auth")
            check(json.loads(f.readline()).get("error") == "already authenticated", "repeat auth")
            f.write(b'{"id":2,"method":"echo","params":{"a":1}}\n')
            f.flush()
            check(json.loads(f.readline()).get("result") == {"got": {"a": 1}}, "still serving after repeat auth")
    case("fake listener answers like PhotoCraft (E21)", realism)

    def batch_stop():
        rc, lines, _ = run_control(base + ['[["echo",{"x":1}],["nope"],["echo"]]'])
        check(statuses(lines) == ["ok", "error", "not-sent"] and rc == 1, f"stop at first error: {lines}")
        check("unknown method" in lines[1]["error"] and "skipped" in lines[2]["error"], f"messages: {lines}")
        rc, lines, _ = run_control(base + ["--keep-going", '[["echo"],["nope"],["echo",null]]'])
        check(statuses(lines) == ["ok", "error", "ok"] and rc == 1, f"--keep-going: {lines}")
        check(lines[0]["result"] == {"got": {}} and lines[2]["result"] == {"got": {}}, "omitted/null params")
        rc, lines, _ = run_control(base + ['["echo",{"single":true}]'])
        check(rc == 0 and lines[0]["result"] == {"got": {"single": True}}, f"single request: {lines}")
    case("one line per request; stop at first failure unless --keep-going (E4)", batch_stop)

    def utf8_stdin():
        text = "中文名称 ✓ é"
        rc, lines, _ = run_control(base, stdin=json.dumps([["echo", {"name": text}]], ensure_ascii=False))
        check(rc == 0 and lines[0]["result"]["got"]["name"] == text, f"UTF-8 stdin round trip: {lines}")
        rc, lines, _ = run_control(base + ["--ascii"], stdin="\ufeff" + json.dumps([["echo", {"n": text}]], ensure_ascii=False))
        check(rc == 0 and lines[0]["result"]["got"]["n"] == text, "BOM-prefixed stdin and --ascii output")
    case("stdin read as UTF-8 under a GBK console encoding (E3)", utf8_stdin)

    def timeout_tail():
        before = fake.received["echo"]
        rc, lines, _ = run_control(base + ["--timeout", "1", '[["echo"],["sleep",{"seconds":4}],["echo"]]'])
        check(statuses(lines) == ["ok", "may-have-completed", "not-sent"] and rc == 1, f"timeout: {lines}")
        check("inspect" in lines[1]["hint"], "may-have-completed carries the inspect hint")
        time.sleep(0.2)
        check(fake.received["echo"] == before + 1, "the request after a lost reply was sent anyway")
        check(fake.received["sleep"] == 1, "the timed-out request was resent")
    case("lost reply: may-have-completed, rest not-sent, nothing resent (E4)", timeout_tail)

    def gui_timeouts():
        rc, lines, _ = run_control(base + ["--keep-going", '[["gui.notrun"],["gui.noreply"]]'])
        check(statuses(lines) == ["not-sent", "may-have-completed"] and rc == 1, f"GUI timeouts: {lines}")
        check(lines[0]["error"].startswith("timeout: not run") and "safe to resend" in lines[0]["hint"], "not run")
        ctl = pclib.Control(fake.port, token_file=tok)
        try:
            ctl.call("gui.notrun")
        except pclib.ServerTimeoutNotRun as exc:
            check(exc.safe_to_resend is True and "safe to resend" in str(exc), str(exc))
        else:
            raise Failed("ServerTimeoutNotRun not raised")
        try:
            ctl.call("gui.noreply")
        except pclib.ServerTimeoutNoReply as exc:
            check(exc.safe_to_resend is False and "inspect" in str(exc), str(exc))
        else:
            raise Failed("ServerTimeoutNoReply not raised")
        ctl.close()
        check(pclib.DEFAULT_CONTROL_TIMEOUT == 55.0, "default reply timeout must be 55 s, just below the GUI's 60 s deadline")
    case("desktop 'timeout: not run' vs 'no reply in 60s'; 55 s default (E7)", gui_timeouts)

    def silent_listener():
        silent = FakeControl(token, silent=True, auth_deadline=5)
        started = time.monotonic()
        rc, lines, err = run_control(["--port", str(silent.port), "--token-file", str(tok), "--timeout", "1",
                                      '[["echo"],["echo"]]'])
        silent.close()
        check(statuses(lines) == ["not-sent", "not-sent"] and rc == 1, f"silent listener: {lines} {err}")
        check("no reply to auth" in lines[0]["error"], lines[0]["error"])
        check(time.monotonic() - started < 15, "silent listener took too long")
    case("auth timeout is reported per request, no traceback (E5)", silent_listener)

    def wrong_token():
        bad = tmp / "wrong.token"
        bad.write_text(new_token(), encoding="ascii")
        rc, lines, _ = run_control(["--port", str(fake.port), "--token-file", str(bad), '[["echo"],["echo"]]'])
        check(rc == 1 and statuses(lines) == ["not-sent", "not-sent"], f"wrong token: {lines}")
        check("authentication failed" in lines[0]["error"] and "cannot reach" not in lines[0]["error"], lines[0]["error"])
        port = free_port()
        rc, lines, _ = run_control(["--port", str(port), "--token-file", str(tok), '[["echo"]]'])
        check(rc == 1 and "cannot connect" in lines[0]["error"], f"refused: {lines}")
    case("wrong token says 'authentication failed'; refused port says 'cannot connect' (E6)", wrong_token)

    def no_fallback():
        decoy = new_token()
        appdata = tmp / "appdata"
        for path in (appdata / "Photocraft" / "control.token", tmp / "cfg" / "control.token",
                     tmp / "xdg" / "photocraft" / "control.token",
                     tmp / "home" / "Library" / "Application Support" / "Photocraft" / "control.token"):
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(decoy, encoding="ascii")
        before = fake.connections
        env = child_env(PHOTOCRAFT_CONTROL_TOKEN_FILE=tmp / "missing.token", APPDATA=appdata,
                        PHOTOCRAFT_CONFIG_DIR=tmp / "cfg", XDG_CONFIG_HOME=tmp / "xdg", HOME=tmp / "home",
                        USERPROFILE=tmp / "home")
        rc, lines, _ = run_control(["--port", str(fake.port), '[["echo"]]'], env=env)
        check(rc == 1 and lines[0]["status"] == "not-sent" and "does not exist" in lines[0]["error"], f"{lines}")
        rc, lines, _ = run_control(["--port", str(fake.port), "--token-file", str(tmp / "nope.token"), '[["echo"]]'],
                                   env=env)
        check(rc == 1 and "does not exist" in lines[0]["error"], f"explicit missing file: {lines}")
        env.pop("PHOTOCRAFT_CONTROL_TOKEN_FILE")
        rc, lines, _ = run_control(["--port", str(fake.port), '[["echo"]]'], env=env)
        check(rc == 1 and "no control token" in lines[0]["error"], f"no token configured: {lines}")
        check(fake.connections == before, "control.py connected although it had no token")
        check(decoy not in fake.tokens_seen, "a token from a default location reached the server")
    case("a missing token file is an error: no %APPDATA%/config-dir fallback (E2)", no_fallback)

    def ports():
        for args, env in ((["--port", "abc"], None), (["--port", "70000"], None), (["--port", "0"], None),
                          ([], child_env(PHOTOCRAFT_CONTROL_PORT="auto")), ([], child_env())):
            rc, lines, err = run_control([*args, "--token-file", str(tok), '[["echo"]]'], env=env)
            check(rc == 2 and lines and lines[0]["status"] == "not-sent", f"port {args}: rc={rc} {lines}")
            check("port" in lines[0]["error"], lines[0]["error"])
        rc, _, err = run_control(base + ["--probe", '[["echo"]]'])
        check(rc == 2 and "unrecognized arguments" in err, "--probe must be gone")
        rc, lines, err = run_control(base + ["not json"])
        check(rc == 2 and not lines and "not valid JSON" in err, f"bad payload: {err}")
    case("ports validated, --probe removed, bad payload is a usage error (E22)", ports)

    def token_forms():
        odd = tmp / "odd.token"
        odd.write_bytes(("\ufeff  " + token.upper() + "\r\n").encode("utf-8"))
        rc, lines, _ = run_control(["--port", str(fake.port), "--token-file", str(odd), '[["echo"]]'])
        check(rc == 0, f"BOM/upper-case/CRLF token: {lines}")
        junk = tmp / "junk.token"
        junk.write_text("not a token", encoding="ascii")
        before = fake.connections
        rc, lines, _ = run_control(["--port", str(fake.port), "--token-file", str(junk), '[["echo"]]'])
        check(rc == 1 and "64 hexadecimal" in lines[0]["error"] and fake.connections == before, f"junk: {lines}")
        with env_vars(PHOTOCRAFT_CONTROL_TOKEN=new_token(), PHOTOCRAFT_CONTROL_TOKEN_FILE=None):
            with pclib.Control(fake.port, token_file=tok) as ctl:
                check(ctl.call("echo") == {"got": {}}, "explicit token file must beat PHOTOCRAFT_CONTROL_TOKEN")
            with pclib.Control(fake.port) as ctl:
                try:
                    ctl.call("echo")
                except pclib.AuthError:
                    pass
                else:
                    raise Failed("the env token (wrong) should have been used")
        with env_vars(PHOTOCRAFT_CONTROL_TOKEN=None, PHOTOCRAFT_CONTROL_TOKEN_FILE=str(odd)):
            with pclib.Control(fake.port) as ctl:
                check(ctl.call("echo") == {"got": {}}, "PHOTOCRAFT_CONTROL_TOKEN_FILE")
        try:
            pclib.resolve_token(token=token, token_file=tok)
        except pclib.AuthError:
            pass
        else:
            raise Failed("token and token_file together must be refused")
    case("token normalised (BOM, case, CRLF) and precedence explicit > env (E23)", token_forms)

    def local_rejects():
        before = sum(fake.received.values())
        rc, lines, _ = run_control(base + ['[["echo",3],["echo"]]'])
        check(rc == 2 and statuses(lines) == ["not-sent", "not-sent"], f"non-object params: {lines}")
        check("params must be a JSON object" in lines[0]["error"], lines[0]["error"])
        with pclib.Control(fake.port, token_file=tok) as ctl:
            for bad in (lambda: ctl.call("echo", [1]), lambda: ctl.call("", {}),
                        lambda: ctl.call("echo", {"blob": "x" * pclib.MAX_REQUEST_BYTES})):
                try:
                    bad()
                except pclib.InvalidRequest:
                    pass
                else:
                    raise Failed("an invalid request was not rejected locally")
        check(sum(fake.received.values()) == before, "a locally rejected request reached the server")
    case("non-object params and oversized lines are rejected before sending", local_rejects)

    def reconnects():
        short = FakeControl(token, idle=1.0)
        with pclib.Control(short.port, token_file=tok, idle_reconnect=60) as ctl:
            check(ctl.call("echo", {"n": 1}) == {"got": {"n": 1}}, "first call")
            time.sleep(1.8)                      # the server drops the idle connection
            check(ctl.call("echo", {"n": 2}) == {"got": {"n": 2}}, "call after the idle drop")
            check(ctl.reconnects == 1 and short.connections == 2, f"reconnects={ctl.reconnects}")
            check(short.received["echo"] == 2, "a request was resent after the reconnect")
            try:
                ctl.call("drop")
            except pclib.MayHaveCompleted as exc:
                check(not isinstance(exc, pclib.NotSent), "drop must not look safe to resend")
            else:
                raise Failed("a dropped reply must raise MayHaveCompleted")
            check(short.received["drop"] == 1, "a written request was resent")
            check(ctl.call("echo") == {"got": {}}, "the next call reconnects")
            try:
                ctl.call("sleep", {"seconds": 2}, timeout=0.5)
            except pclib.ReplyTimeout:
                pass
            else:
                raise Failed("ReplyTimeout not raised")
            check(ctl.call("echo", {"after": "timeout"}) == {"got": {"after": "timeout"}}, "no stale reply mix-up")
            check(short.received["sleep"] == 1, "the timed-out request was resent")
        short.close()
        with pclib.Control(fake.port, token_file=tok, idle_reconnect=0.3) as ctl:
            before = fake.connections
            ctl.call("echo")
            time.sleep(0.5)
            ctl.call("echo")
            check(fake.connections == before + 2, "proactive reconnect after idle_reconnect seconds")
    case("idle drop: reconnect + re-auth before sending; written requests never resent", reconnects)

    fake.close()
    return done


# --------------------------------------------------------------------------- live serve
def live(tmp: Path, cli_arg, idle: bool) -> list[str]:
    done: list[str] = []
    try:
        cli = pclib.find_cli(cli_arg)
    except pclib.CliNotFound as exc:
        print(f"--live needs photocraft-cli: {exc}", file=sys.stderr)
        raise SystemExit(2) from None
    root, cfg = tmp / "root", tmp / "cfg"
    root.mkdir()
    cfg.mkdir()
    tok = tmp / "serve.token"
    port = free_port()
    env = {k: v for k, v in os.environ.items()
           if not k.startswith(("PHOTOCRAFT_CONTROL_", "PHOTOCRAFT_AUTOMATION_"))}
    env["PHOTOCRAFT_CONFIG_DIR"] = str(cfg)
    argv = [str(cli), "serve", "--port", str(port), "--control-token-file", str(tok),
            "--automation-read-root", str(root), "--automation-write-root", str(root)]
    proc = subprocess.Popen(argv, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, env=env)
    banner: list[str] = []

    def pump() -> None:
        for raw in iter(proc.stderr.readline, b""):
            banner.append(raw.decode("utf-8", "replace").strip())

    threading.Thread(target=pump, daemon=True).start()

    def case(name: str, fn) -> None:
        try:
            fn()
        except Failed:
            raise
        except Exception as exc:  # noqa: BLE001 - report which case broke, not a bare traceback
            raise Failed(f"live {name}: unexpected {type(exc).__name__}: {exc}") from exc
        done.append(name)
        print(f"ok: live {name}", flush=True)

    try:
        deadline = time.monotonic() + 20
        while not any("serving on" in line for line in banner):
            if proc.poll() is not None or time.monotonic() > deadline:
                raise Failed(f"serve did not start: {pclib._scrub(' | '.join(banner))}")
            time.sleep(0.05)
        SECRETS.add(tok.read_text(encoding="ascii").strip())
        check(not any(s in line for s in SECRETS for line in banner), "serve printed the token")
        base = ["--port", str(port), "--token-file", str(tok)]

        def auth():
            with pclib.Control(port, token_file=tok) as ctl:
                check("engine.execute" in ctl.call("methods"), "methods over TCP")
            bad = tmp / "wrong.token"
            bad.write_text(new_token(), encoding="ascii")
            try:
                pclib.Control(port, token_file=bad).call("methods")
            except pclib.AuthError as exc:
                check("authentication failed" in str(exc), str(exc))
            else:
                raise Failed("a wrong token was accepted")
            with socket.create_connection(("127.0.0.1", port), timeout=5) as s:
                f = s.makefile("rwb")
                f.write(b'{"id":1,"method":"methods"}\n')
                f.flush()
                check(json.loads(f.readline()).get("error") == "authentication required", "non-auth first frame")
                check(f.readline() == b"", "serve closes the socket after a failed auth")
        case("auth, wrong token, first frame must be auth", auth)

        def errors():
            rc, lines, _ = run_control(base + ["--keep-going",
                                               '[["nope"],["engine.execute",{"command":"file.new","params":3}]]'])
            check(statuses(lines) == ["error", "error"] and rc == 1, f"{lines}")
            check("unknown method" in lines[0]["error"], lines[0]["error"])
            check("params must be a JSON object" in lines[1]["error"], lines[1]["error"])
            rc, lines, _ = run_control(base + ['[["doc.inspect",3]]'])
            check(rc == 2 and lines[0]["status"] == "not-sent", f"top-level non-object params: {lines}")
        case("unknown method and non-object params", errors)

        def round_trip():
            name = "中文测试 ✓"
            payload = json.dumps([["engine.execute", {"command": "file.new",
                                                      "params": {"width": 16, "height": 8, "name": name}}],
                                  ["engine.execute", {"command": "document.inspect"}]], ensure_ascii=False)
            rc, lines, _ = run_control(base, stdin=payload)
            check(rc == 0 and statuses(lines) == ["ok", "ok"], f"{lines}")
            doc = lines[1]["result"]
            check(doc["width"] == 16 and doc["height"] == 8 and doc.get("name") == name,
                  f"inspect: {doc.get('width')}x{doc.get('height')} {doc.get('name')!r}")
        case("file.new + document.inspect round trip with Chinese text via stdin", round_trip)

        if idle:
            def idle_drop():
                with pclib.Control(port, token_file=tok, idle_reconnect=600) as ctl:
                    ctl.call("methods")
                    time.sleep(31.5)
                    check("engine.execute" in ctl.call("methods"), "call after a 31 s idle")
                    check(ctl.reconnects == 1, f"reconnects={ctl.reconnects}")
            case("31 s idle drop, then reconnect and re-auth", idle_drop)
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=10)
    check(proc.poll() is not None, "serve is still running")
    print("ok: live serve stopped", flush=True)
    return done


def main(argv: list[str] | None = None) -> int:
    pclib.setup_stdio()
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--live", action="store_true", help="also test against a real `photocraft-cli serve --port`")
    ap.add_argument("--idle", action="store_true", help="with --live: wait 31 s to exercise the idle drop")
    ap.add_argument("--cli", help="photocraft-cli path for --live")
    args = ap.parse_args(argv)
    for name in [k for k in os.environ if k.startswith("PHOTOCRAFT_CONTROL_")]:
        os.environ.pop(name)
    # Values a careless child would inherit; the children must not see them (E20).
    os.environ["PHOTOCRAFT_CONTROL_PORT"] = "1"
    os.environ["PHOTOCRAFT_CONTROL_TOKEN"] = new_token()
    tmp = Path(tempfile.mkdtemp(prefix="pc-test-control-"))
    started = time.monotonic()
    try:
        (tmp / "hermetic").mkdir()
        done = hermetic(tmp / "hermetic")
        if args.live:
            (tmp / "live").mkdir()
            done += live(tmp / "live", args.cli, args.idle)
    except Failed as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print(f"OK: {len(done)} checks passed in {time.monotonic() - started:.1f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
