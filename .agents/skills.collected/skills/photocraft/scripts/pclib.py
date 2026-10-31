#!/usr/bin/env python3
"""pclib: shared Python helpers for driving PhotoCraft (stdlib only, Python 3.10+).

Every tool in <skill-dir>/scripts and every client in <skill-dir>/examples/clients
imports this file instead of re-implementing CLI lookup, JSON-lines sessions or
token handling:

    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
    import pclib

CLI (one process per call; argument lists, never shell strings)
  find_cli(explicit=None, *, repo=None) -> Path
      Order: explicit > PHOTOCRAFT_CLI > --repo/PHOTOCRAFT_REPO target dirs > PATH >
      next to `photocraft` on PATH > Windows registry (HKLM/HKCU Software\\PhotoCraft
      InstallDir, App Paths photocraft.exe) > Program Files > standard bin dirs.
      An explicit path or PHOTOCRAFT_CLI is a pin: if it does not run, CliNotFound is
      raised instead of silently using another binary. The macOS app bundle holds no
      CLI (it ships as a separate zip), so it is never searched.
  cli_candidates(explicit=None, *, repo=None) -> list[Candidate(path, source)]
  cli_version(cli=None) -> str                    `photocraft-cli --version`
  run_cli(args, *, cli=None, cwd=None, env=None, timeout=600, check=True, input=None)
      -> subprocess.CompletedProcess with str stdout/stderr (UTF-8)
  run_cmds(input_path, cmds, *, new=None, out=None, extra_args=(), cli=None, cwd=None,
           env=None, timeout=600, check=True) -> RunOutput
      `photocraft-cli run`: exactly one of input_path / new (file.new params).
      cmds: [(id, params|None)] or bare ids. RunOutput is a list of the
      {"command","result"} lines plus .warnings (stderr "warning:" lines), .stderr,
      .returncode and .result(command=None).
  info(path, *, cli=None, cwd=None, timeout=120) -> dict    `info <path> --compact`
  registry(cli=None) -> list[dict]                `commands --json`, cached per process

Sessions (one request at a time; each object is safe to share between threads)
  Serve(read_root=None, write_root=None, *, cli=None, cwd=None, env=None, timeout=300)
      stdio `photocraft-cli serve`. Roots are passed as flags because serve ignores
      PHOTOCRAFT_AUTOMATION_*_ROOT. .call(method, params=None, *, timeout=None),
      .execute(command, params=None, wait=None, *, timeout=None), .methods(),
      .batch(steps, stop_on_error=True, *, check=True, timeout=None) raises BatchFailed
      when result.failed > 0 (the top-level reply is ok:true even then; finished steps
      stay applied), .close(), .kill(), context manager. A timeout leaves the session
      open (the late reply is skipped); a dead child raises NotSent/MayHaveCompleted.
  Control(port=None, *, token=None, token_file=None, timeout=55, connect_timeout=5,
          auth_timeout=10, idle_reconnect=25)
      TCP client for the desktop control port (`photocraft --control <port>`) or
      `serve --port`. Port: argument or PHOTOCRAFT_CONTROL_PORT (no default port).
      First frame is `auth`. Reconnects and re-authenticates only when the socket is
      found closed, or idle for idle_reconnect seconds, BEFORE a request is written
      (both servers drop connections idle for 30 s); a request already written is
      never resent. .call(method, params=None, *, timeout=None), .execute(...), .close().
  Mcp(read_root=None, write_root=None, *, bridge=None, token_file=None, cli=None,
      cwd=None, env=None, timeout=120, protocol_version="2025-06-18")
      stdio JSON-RPC client for `photocraft-cli mcp` (headless, or `bridge=port` for a
      running desktop app). .tools(), .call_tool(name, arguments=None, *, timeout=None,
      check=False) -> result with isError kept, .call_json(name, arguments=None),
      .read_resource(uri), .request(method, params=None), .close(). Requests over
      1 MiB are refused locally: the MCP server exits on an oversized line.
  resolve_token(token=None, token_file=None) -> str
      explicit token / token_file (not both) > PHOTOCRAFT_CONTROL_TOKEN >
      PHOTOCRAFT_CONTROL_TOKEN_FILE. Normalised strip, BOM, lower case; must be 64 hex.
      A named token file that does not exist is an AuthError: no other location
      (config dir, %APPDATA%, ~/.config) is ever searched. Tokens are never printed.
  resolve_port(port=None) -> int                  argument or PHOTOCRAFT_CONTROL_PORT
  content_json(result) / content_images(result)   decode MCP tool/resource content

Errors (all subclass PcError; .safe_to_resend is True, False or None)
  CliNotFound, CliError(.argv .returncode .stdout .stderr .rows), UsageError,
  RpcError(message, method)  server replied ok:false / JSON-RPC error (.code)
    ServerTimeoutNotRun      GUI "timeout: not run": never dispatched, safe to resend
    ServerTimeoutNoReply     GUI "timeout: no reply in 60s": may have completed, inspect
    BatchFailed (.result), ToolError (.result)
  TransportError(message, method)
    NotSent                  nothing reached the server: safe to resend
      AuthError, InvalidRequest, RequestTooLarge
    MayHaveCompleted         request written, reply lost: inspect before resending
      ReplyTimeout

Console helpers: setup_stdio() switches stdout/stderr to UTF-8 (GBK consoles);
read_stdin_text() reads stdin as UTF-8 bytes (BOM tolerated).
"""
from __future__ import annotations

import atexit
import base64
import collections
import json
import os
import queue
import re
import select
import shutil
import socket
import subprocess
import sys
import threading
import time
from dataclasses import dataclass
from pathlib import Path

CLI_NAME = "photocraft-cli.exe" if os.name == "nt" else "photocraft-cli"
MAX_REQUEST_BYTES = 1 << 20          # request line incl. newline (serve, TCP and MCP stdio)
MAX_REPLY_BYTES = 8 << 20            # TCP reply budget
DEFAULT_CONTROL_TIMEOUT = 55.0       # below the desktop app's 60 s reply deadline
IDLE_RECONNECT = 25.0                # servers close connections idle for 30 s
MCP_PROTOCOL_VERSION = "2025-06-18"
_TOKEN_RE = re.compile(r"[0-9a-f]{64}")
_TOKEN_SCRUB = re.compile(r"(?i)(?<![0-9a-f])[0-9a-f]{64}(?![0-9a-f])")
_CONTROL_ENV = ("PHOTOCRAFT_CONTROL_PORT", "PHOTOCRAFT_CONTROL_TOKEN", "PHOTOCRAFT_CONTROL_TOKEN_FILE")


# --------------------------------------------------------------------------- errors
class PcError(Exception):
    """Base class for every pclib error."""

    safe_to_resend: bool | None = None


class CliNotFound(PcError):
    def __init__(self, message: str, searched: list | None = None):
        super().__init__(message)
        self.searched = list(searched or [])


class CliError(PcError):
    def __init__(self, message: str, *, argv=(), returncode=None, stdout="", stderr="", rows=None):
        super().__init__(message)
        self.argv = list(argv)
        self.returncode = returncode
        self.stdout = _scrub(stdout or "")
        self.stderr = _scrub(stderr or "")
        self.rows = rows if rows is not None else []


class UsageError(PcError, ValueError):
    """Bad input to a helper (port, payload, arguments)."""


class RpcError(PcError):
    """The server answered the request with an error."""

    hint = ""

    def __init__(self, message: str, method: str | None = None, *, code=None, data=None, reply=None):
        super().__init__(message)
        self.message = message
        self.method = method
        self.code = code
        self.data = data
        self.reply = reply

    def __str__(self) -> str:
        text = f"{self.method}: {self.message}" if self.method else self.message
        return f"{text} [{self.hint}]" if self.hint else text


class ServerTimeoutNotRun(RpcError):
    safe_to_resend = True
    hint = "not run: safe to resend"


class ServerTimeoutNoReply(RpcError):
    safe_to_resend = False
    hint = "may have completed: inspect the document before resending"


class BatchFailed(RpcError):
    def __init__(self, message: str, method: str = "batch", *, result=None):
        super().__init__(message, method)
        self.result = result or {}


class ToolError(RpcError):
    def __init__(self, message: str, method: str, *, result=None):
        super().__init__(message, method)
        self.result = result or {}


class TransportError(PcError):
    def __init__(self, message: str, method: str | None = None):
        super().__init__(message)
        self.message = message
        self.method = method

    def __str__(self) -> str:
        return f"{self.method}: {self.message}" if self.method else self.message


class NotSent(TransportError):
    """The request never reached the server; resending is safe."""

    safe_to_resend = True


class AuthError(NotSent):
    """No usable token, or the server refused it."""


class InvalidRequest(NotSent, ValueError):
    """Rejected locally before sending (method/params shape)."""


class RequestTooLarge(InvalidRequest):
    pass


class MayHaveCompleted(TransportError):
    """The request was written but its reply was lost; inspect before resending."""

    safe_to_resend = False


class ReplyTimeout(MayHaveCompleted):
    pass


def _rpc_error(error, method: str | None, reply=None) -> RpcError:
    text = error if isinstance(error, str) else json.dumps(error, ensure_ascii=False)
    if text.startswith("timeout: not run"):
        return ServerTimeoutNotRun(text, method, reply=reply)
    if text.startswith("timeout: no reply"):
        return ServerTimeoutNoReply(text, method, reply=reply)
    return RpcError(text, method, reply=reply)


# --------------------------------------------------------------------------- console
def setup_stdio() -> None:
    """Write UTF-8 on stdout/stderr even on a GBK (cp936) Windows console."""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError, OSError):
            pass


def read_stdin_text() -> str:
    """Read all of stdin as UTF-8 bytes, ignoring the console code page."""
    data = sys.stdin.buffer.read()
    try:
        return data.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise UsageError(
            f"stdin is not UTF-8 ({exc}); in Windows PowerShell run "
            "$OutputEncoding = [System.Text.UTF8Encoding]::new() before piping"
        ) from None


def _scrub(text: str) -> str:
    """Hide anything shaped like a control token (64 hex) in diagnostics."""
    return _TOKEN_SCRUB.sub("<token redacted>", text)


def _popen_kwargs() -> dict:
    if os.name == "nt":
        return {"creationflags": getattr(subprocess, "CREATE_NO_WINDOW", 0)}
    return {}


def _child_env(env: dict | None, *, drop_control: bool) -> dict:
    out = dict(os.environ if env is None else env)
    if drop_control:
        for name in _CONTROL_ENV:
            out.pop(name, None)
    return out


# --------------------------------------------------------------------------- locate the CLI
@dataclass(frozen=True)
class Candidate:
    path: Path
    source: str


_TRIPLES = {
    "nt": ("x86_64-pc-windows-msvc", "aarch64-pc-windows-msvc", "x86_64-pc-windows-gnullvm"),
    "darwin": ("aarch64-apple-darwin", "x86_64-apple-darwin"),
    "linux": ("x86_64-unknown-linux-gnu", "aarch64-unknown-linux-gnu"),
}


def _platform_key() -> str:
    if os.name == "nt":
        return "nt"
    return "darwin" if sys.platform == "darwin" else "linux"


def _windows_registry_dirs() -> list[tuple[str, str]]:
    try:
        import winreg  # type: ignore[import-not-found]
    except ImportError:
        return []
    found: list[tuple[str, str]] = []

    def read(root, sub: str, name: str, view: int):
        try:
            with winreg.OpenKey(root, sub, 0, winreg.KEY_READ | view) as key:
                value, _ = winreg.QueryValueEx(key, name)
        except OSError:
            return None
        return value.strip().strip('"') if isinstance(value, str) and value.strip() else None

    views = (winreg.KEY_WOW64_64KEY, winreg.KEY_WOW64_32KEY)
    for root, label in ((winreg.HKEY_LOCAL_MACHINE, "HKLM"), (winreg.HKEY_CURRENT_USER, "HKCU")):
        for view in views:
            install = read(root, r"Software\PhotoCraft", "InstallDir", view)
            if install:
                found.append((install, label + r"\Software\PhotoCraft\InstallDir"))
            app = read(root, r"Software\Microsoft\Windows\CurrentVersion\App Paths\photocraft.exe", "", view)
            if app:
                found.append((str(Path(app).parent), label + r" App Paths\photocraft.exe"))
    return found


def cli_candidates(explicit=None, *, repo=None) -> list[Candidate]:
    """Every place find_cli() looks, in order (paths may not exist)."""
    out: list[Candidate] = []

    def add(raw, source: str) -> None:
        if not raw:
            return
        path = Path(os.path.expandvars(os.path.expanduser(os.fspath(raw))))
        if path.is_dir():
            path = path / CLI_NAME
        if all(c.path != path for c in out):
            out.append(Candidate(path, source))

    add(explicit, "--cli")
    add(os.environ.get("PHOTOCRAFT_CLI"), "PHOTOCRAFT_CLI")
    # 旧名，部分仓库（含以 0.12 为基线的那批模板工程）仍只用它
    add(os.environ.get("PC_CLI"), "PC_CLI (legacy)")
    triples = _TRIPLES[_platform_key()]
    for root, source in ((repo, "--repo"), (os.environ.get("PHOTOCRAFT_REPO"), "PHOTOCRAFT_REPO")):
        if not root:
            continue
        base = Path(os.path.expanduser(os.fspath(root))) / "target"
        for profile in ("release", "debug"):
            add(base / profile / CLI_NAME, source)
            for triple in triples:
                add(base / triple / profile / CLI_NAME, source)
    add(shutil.which("photocraft-cli"), "PATH")
    app = shutil.which("photocraft")
    if app:
        add(Path(app).with_name(CLI_NAME), "next to photocraft on PATH")
    key = _platform_key()
    if key == "nt":
        for folder, source in _windows_registry_dirs():
            add(Path(folder) / CLI_NAME, source)
        for var in ("ProgramFiles", "ProgramW6432", "ProgramFiles(x86)"):
            base = os.environ.get(var)
            if base:
                add(Path(base) / "PhotoCraft" / CLI_NAME, "%" + var + "%")
    else:
        dirs = (("/usr/local/bin", "/opt/homebrew/bin", "~/.local/bin", "~/bin") if key == "darwin"
                else ("/usr/bin", "/usr/local/bin", "~/.local/bin", "~/bin"))
        for folder in dirs:
            add(Path(folder).expanduser() / CLI_NAME, "standard bin dir")
    return out


_PROBES: dict[str, tuple[bool, str]] = {}
_FOUND: dict[tuple, Path] = {}


def _probe(path: Path) -> tuple[bool, str]:
    """(usable, version or reason) for one candidate; never launches the GUI binary."""
    key = str(path)
    if key in _PROBES:
        return _PROBES[key]
    if not path.is_file():
        result = (False, "does not exist")
    elif not path.name.lower().startswith("photocraft-cli"):
        result = (False, "is not named photocraft-cli*")
    else:
        try:
            proc = subprocess.run([str(path), "--version"], capture_output=True, timeout=20, **_popen_kwargs())
            text = (proc.stdout or proc.stderr).decode("utf-8", "replace").strip()
            if proc.returncode == 0 and text.startswith("photocraft-cli"):
                result = (True, text.splitlines()[0])
            else:
                result = (False, f"--version exited {proc.returncode}: {text[:200]}")
        except (OSError, subprocess.TimeoutExpired) as exc:
            result = (False, f"cannot run it: {exc}")
    _PROBES[key] = result
    return result


def find_cli(explicit=None, *, repo=None) -> Path:
    """Path of a working photocraft-cli, or CliNotFound naming every place searched."""
    pinned_env = os.environ.get("PHOTOCRAFT_CLI")
    cache_key = (os.fspath(explicit) if explicit else None, os.fspath(repo) if repo else None,
                 pinned_env, os.environ.get("PC_CLI"), os.environ.get("PHOTOCRAFT_REPO"),
                 os.environ.get("PATH"))
    if cache_key in _FOUND:
        return _FOUND[cache_key]
    pin = explicit or pinned_env
    if pin:
        source = "--cli" if explicit else "PHOTOCRAFT_CLI"
        cand = cli_candidates(pin, repo=None)[0]
        ok, detail = _probe(cand.path)
        if not ok:
            raise CliNotFound(
                f"{source} points to {cand.path}, which {detail}; fix or unset it "
                "(a pinned CLI is never replaced by another binary)",
                [Candidate(cand.path, source)])
        _FOUND[cache_key] = cand.path.resolve()
        return _FOUND[cache_key]
    cands = cli_candidates(None, repo=repo)
    for cand in cands:
        if cand.path.is_file() and _probe(cand.path)[0]:
            _FOUND[cache_key] = cand.path.resolve()
            return _FOUND[cache_key]
    lines = "\n".join(f"  {c.path}  ({c.source})" for c in cands)
    if not shutil.which("photocraft-cli"):
        lines = "  PATH  (no photocraft-cli on it)\n" + lines
    raise CliNotFound(
        "photocraft-cli not found. Install PhotoCraft (the Windows MSI puts it in "
        "Program Files, not on PATH; on macOS the CLI is a separate zip) or set "
        "PHOTOCRAFT_CLI=<path> (the legacy name PC_CLI is also read; PHOTOCRAFT_CLI wins). "
        "Searched:\n" + lines, cands)


def _resolve_cli(cli) -> Path:
    return find_cli(cli) if cli else find_cli()


# --------------------------------------------------------------------------- one-shot CLI calls
def _cli_message(stderr: str, returncode) -> str:
    lines = [ln.strip() for ln in stderr.splitlines() if ln.strip()]
    errors = [ln for ln in lines if ln.startswith("error:")]
    text = errors[-1] if errors else (lines[-1] if lines else "no error text")
    return f"exit {returncode}: {_scrub(text)}"


def run_cli(args, *, cli=None, cwd=None, env=None, timeout=600, check=True, input=None) -> subprocess.CompletedProcess:
    """Run photocraft-cli with an argument list; stdout/stderr come back as UTF-8 str."""
    exe = _resolve_cli(cli)
    argv = [str(exe), *(os.fspath(a) if isinstance(a, os.PathLike) else str(a) for a in args)]
    data = input.encode("utf-8") if isinstance(input, str) else input
    try:
        proc = subprocess.run(argv, input=data, capture_output=True, cwd=cwd, env=env,
                              timeout=timeout, **_popen_kwargs())
    except FileNotFoundError as exc:
        raise CliNotFound(f"cannot start {exe}: {exc}") from None
    except subprocess.TimeoutExpired:
        # 超时不代表没跑：前几步可能已经写盘（saveACopy 之类），--out 通常没写成
        raise CliError(
            f"photocraft-cli {argv[1] if len(argv) > 1 else ''} timed out after {timeout}s; "
            "earlier steps may have written files, and --out was not written; "
            "check the output directory before resending",
            argv=argv) from None
    proc.stdout = proc.stdout.decode("utf-8", "replace")
    proc.stderr = proc.stderr.decode("utf-8", "replace")
    if check and proc.returncode != 0:
        sub = argv[1] if len(argv) > 1 else ""
        raise CliError(f"photocraft-cli {sub} failed ({_cli_message(proc.stderr, proc.returncode)})",
                       argv=argv, returncode=proc.returncode, stdout=proc.stdout, stderr=proc.stderr)
    return proc


def cli_version(cli=None) -> str:
    return run_cli(["--version"], cli=cli, timeout=30).stdout.strip()


_REGISTRY: dict[str, list] = {}


def registry(cli=None) -> list[dict]:
    """`commands --json` (every command with id, label, menu, params text, enabled,
    needsDocument), cached per process and binary."""
    exe = str(_resolve_cli(cli))
    if exe not in _REGISTRY:
        _REGISTRY[exe] = json.loads(run_cli(["commands", "--json"], cli=exe, timeout=120).stdout)
    return _REGISTRY[exe]


def info(path, *, cli=None, cwd=None, timeout=120) -> dict:
    """`photocraft-cli info <path> --compact` as a dict."""
    return json.loads(run_cli(["info", os.fspath(path), "--compact"], cli=cli, cwd=cwd, timeout=timeout).stdout)


class RunOutput(list):
    """The {"command","result"} lines of `photocraft-cli run`, plus stderr details."""

    def __init__(self, rows=(), *, stderr: str = "", returncode: int = 0, argv=()):
        super().__init__(rows)
        self.stderr = stderr
        self.returncode = returncode
        self.argv = list(argv)
        self.warnings = [ln.strip()[len("warning:"):].strip() for ln in stderr.splitlines()
                         if ln.strip().startswith("warning:")]

    def result(self, command: str | None = None):
        """Result of the last line (of `command`, if given); KeyError if absent."""
        for row in reversed(self):
            if command is None or row.get("command") == command:
                return row.get("result")
        raise KeyError(command or "no output lines")


def _split_step(step) -> tuple[str, dict | None]:
    if isinstance(step, str):
        return step, None
    if isinstance(step, (tuple, list)) and 1 <= len(step) <= 2 and isinstance(step[0], str):
        return step[0], (step[1] if len(step) == 2 else None)
    raise InvalidRequest(f"a step must be an id or (id, params): {step!r}")


def _check_params(params, where: str) -> None:
    if params is not None and not isinstance(params, dict):
        raise InvalidRequest(f"params must be a JSON object or None, got {type(params).__name__}", where)


def _compact(obj) -> str:
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":"))


def run_cmds(input_path, cmds, *, new=None, out=None, extra_args=(), cli=None, cwd=None,
             env=None, timeout=600, check=True) -> RunOutput:
    """`photocraft-cli run` one file (or a new document) through engine commands."""
    if (input_path is None) == (new is None):
        raise UsageError("pass exactly one of input_path or new= (file.new params)")
    args: list[str] = ["run"]
    if new is not None:
        _check_params(new, "--new")
        args += ["--new", _compact(new)]
    else:
        args.append(os.fspath(input_path))
    for step in cmds:
        command, params = _split_step(step)
        _check_params(params, command)
        args += ["--cmd", command]
        if params is not None:
            args += ["--params", _compact(params)]
    if out is not None:
        args += ["--out", os.fspath(out)]
    args += [os.fspath(a) if isinstance(a, os.PathLike) else str(a) for a in extra_args]
    proc = run_cli(args, cli=cli, cwd=cwd, env=env, timeout=timeout, check=False)
    rows = []
    for line in proc.stdout.splitlines():
        line = line.strip()
        if line:
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                rows.append({"command": None, "result": None, "raw": line})
    output = RunOutput(rows, stderr=proc.stderr, returncode=proc.returncode, argv=proc.args)
    if check and proc.returncode != 0:
        raise CliError(f"photocraft-cli run failed ({_cli_message(proc.stderr, proc.returncode)})",
                       argv=proc.args, returncode=proc.returncode, stdout=proc.stdout,
                       stderr=proc.stderr, rows=output)
    return output


# --------------------------------------------------------------------------- tokens and ports
def resolve_port(port=None) -> int:
    """Control port from the argument or PHOTOCRAFT_CONTROL_PORT; 1..65535."""
    source = "port"
    if port is None or (isinstance(port, str) and not port.strip()):
        port = os.environ.get("PHOTOCRAFT_CONTROL_PORT", "").strip()
        source = "PHOTOCRAFT_CONTROL_PORT"
        if not port:
            raise UsageError("no control port: pass --port/port= or set PHOTOCRAFT_CONTROL_PORT "
                             "(PhotoCraft has no default port; the desktop app listens only when "
                             "started with --control <port>)")
    try:
        if isinstance(port, bool):
            raise ValueError
        value = int(str(port).strip(), 10)
    except ValueError:
        raise UsageError(f"bad control port {port!r} from {source}: expected a whole number 1-65535") from None
    if not 1 <= value <= 65535:
        raise UsageError(f"bad control port {value} from {source}: expected 1-65535")
    return value


def _normalise_token(raw: str, source: str) -> str:
    token = raw.strip().lstrip("\ufeff").strip().lower()
    if not _TOKEN_RE.fullmatch(token):
        raise AuthError(f"{source} does not hold a PhotoCraft control token "
                        "(expected 64 hexadecimal characters)", "auth")
    return token


def _read_token_file(raw, source: str) -> str:
    path = Path(os.path.expanduser(os.fspath(raw)))
    if not path.exists():
        raise AuthError(
            f"{source} names {path}, which does not exist. No other token location is "
            f"searched. Start PhotoCraft with --control-token-file {path} (it creates the "
            "file) or point at the file the running instance was started with", "auth")
    if not path.is_file():
        raise AuthError(f"{source}: {path} is not a regular file", "auth")
    if os.name == "posix" and path.stat().st_mode & 0o077:
        raise AuthError(f"{source}: {path} is readable by group or others; chmod 600 it "
                        "(PhotoCraft refuses such token files too)", "auth")
    try:
        text = path.read_bytes().decode("utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise AuthError(f"{source}: cannot read {path}: {exc.__class__.__name__}", "auth") from None
    return _normalise_token(text, f"{source} ({path})")


def resolve_token(token=None, token_file=None) -> str:
    """The control token, from explicit arguments first, then the environment."""
    if token is not None and token_file is not None:
        raise AuthError("pass either a token or a token file, not both", "auth")
    if token is not None:
        return _normalise_token(str(token), "the token argument")
    if token_file is not None:
        return _read_token_file(token_file, "the token file argument")
    env_token = os.environ.get("PHOTOCRAFT_CONTROL_TOKEN", "")
    if env_token.strip():
        return _normalise_token(env_token, "PHOTOCRAFT_CONTROL_TOKEN")
    env_file = os.environ.get("PHOTOCRAFT_CONTROL_TOKEN_FILE", "").strip()
    if env_file:
        return _read_token_file(env_file, "PHOTOCRAFT_CONTROL_TOKEN_FILE")
    raise AuthError("no control token: pass --token-file/token_file= or set "
                    "PHOTOCRAFT_CONTROL_TOKEN_FILE (or PHOTOCRAFT_CONTROL_TOKEN) to the token "
                    "file PhotoCraft was started with (--control-token-file); no default "
                    "location is searched", "auth")


def _check_method(method) -> None:
    if not isinstance(method, str) or not method:
        raise InvalidRequest(f"method must be a non-empty string, got {method!r}")


def _encode_line(obj, method: str) -> bytes:
    try:
        line = json.dumps(obj, ensure_ascii=False).encode("utf-8") + b"\n"
    except (TypeError, ValueError, UnicodeEncodeError) as exc:
        raise InvalidRequest(f"request is not encodable as UTF-8 JSON: {exc}", method) from None
    if len(line) > MAX_REQUEST_BYTES:
        raise RequestTooLarge(f"request is {len(line)} bytes; PhotoCraft accepts at most "
                              f"{MAX_REQUEST_BYTES} per line (pass large data by file path)", method)
    return line


# --------------------------------------------------------------------------- long-lived children
_LIVE: set = set()


@atexit.register
def _kill_leftovers() -> None:
    for child in list(_LIVE):
        child.kill()


class _Child:
    """A CLI child speaking JSON lines on stdin/stdout; stdout is read by a thread."""

    def __init__(self, argv: list[str], *, cwd, env, label: str):
        self.label = label
        try:
            self.proc = subprocess.Popen(argv, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                         stderr=subprocess.PIPE, cwd=cwd, env=env, **_popen_kwargs())
        except OSError as exc:
            raise CliNotFound(f"cannot start {argv[0]}: {exc}") from None
        self._lines: queue.Queue = queue.Queue()
        self._eof = False
        self._stderr: collections.deque = collections.deque(maxlen=200)
        self.noise: collections.deque = collections.deque(maxlen=50)
        _LIVE.add(self)
        threading.Thread(target=self._pump_stdout, daemon=True).start()
        threading.Thread(target=self._pump_stderr, daemon=True).start()

    def _pump_stdout(self) -> None:
        try:
            for raw in iter(self.proc.stdout.readline, b""):
                self._lines.put(raw)
        except (OSError, ValueError):
            pass
        finally:
            self._lines.put(None)

    def _pump_stderr(self) -> None:
        try:
            for raw in iter(self.proc.stderr.readline, b""):
                self._stderr.append(_scrub(raw.decode("utf-8", "replace").rstrip("\r\n")))
        except (OSError, ValueError):
            pass

    def stderr_tail(self, lines: int = 15) -> str:
        return "\n".join(list(self._stderr)[-lines:])

    def _exit_note(self) -> str:
        code = self.proc.poll()
        tail = self.stderr_tail()
        note = f"{self.label} exited with code {code}" if code is not None else f"{self.label} closed its output"
        return note + (f"; stderr: {tail}" if tail else "")

    def send(self, obj, method: str) -> None:
        line = _encode_line(obj, method)
        if self._eof or self.proc.poll() is not None:
            raise NotSent(self._exit_note(), method)
        try:
            self.proc.stdin.write(line)
            self.proc.stdin.flush()
        except (OSError, ValueError):
            raise NotSent(self._exit_note(), method) from None

    def recv(self, deadline: float, method: str, timeout_note: str) -> dict:
        while True:
            if self._eof:
                raise MayHaveCompleted(self._exit_note() + " before replying", method)
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise ReplyTimeout(timeout_note, method)
            try:
                raw = self._lines.get(timeout=remaining)
            except queue.Empty:
                raise ReplyTimeout(timeout_note, method) from None
            if raw is None:
                self._eof = True
                try:
                    self.proc.wait(timeout=1)
                except subprocess.TimeoutExpired:
                    pass
                continue
            text = raw.decode("utf-8", "replace").strip()
            if not text:
                continue
            try:
                msg = json.loads(text)
            except json.JSONDecodeError:
                self.noise.append(text[:500])
                continue
            if isinstance(msg, dict):
                return msg
            self.noise.append(text[:500])

    def close(self, wait: float = 5.0) -> None:
        try:
            if self.proc.stdin and not self.proc.stdin.closed:
                self.proc.stdin.close()
        except OSError:
            pass
        try:
            self.proc.wait(timeout=wait)
        except subprocess.TimeoutExpired:
            self.kill()
        _LIVE.discard(self)

    def kill(self) -> None:
        if self.proc.poll() is None:
            try:
                self.proc.kill()
                self.proc.wait(timeout=5)
            except (OSError, subprocess.TimeoutExpired):
                pass
        _LIVE.discard(self)


class Serve:
    """A stdio `photocraft-cli serve` session: one headless engine, many requests."""

    def __init__(self, read_root=None, write_root=None, *, cli=None, cwd=None, env=None,
                 timeout: float = 300.0):
        self.cli = _resolve_cli(cli)
        argv = [str(self.cli), "serve"]
        if read_root is not None:
            argv += ["--automation-read-root", os.fspath(read_root)]
        if write_root is not None:
            argv += ["--automation-write-root", os.fspath(write_root)]
        self.timeout = float(timeout)
        self._lock = threading.Lock()
        self._id = 0
        self._methods: list | None = None
        self._child = _Child(argv, cwd=cwd, env=_child_env(env, drop_control=True), label="serve")

    def call(self, method: str, params: dict | None = None, *, timeout: float | None = None):
        """One method (`methods` lists them); returns `result` or raises RpcError."""
        _check_method(method)
        _check_params(params, method)
        limit = self.timeout if timeout is None else float(timeout)
        with self._lock:
            self._id += 1
            rid = self._id
            self._child.send({"id": rid, "method": method, "params": params if params is not None else {}}, method)
            deadline = time.monotonic() + limit
            note = (f"no reply within {limit:g}s; the request may still be running and may still "
                    "apply (the session stays open; kill() it if it is stuck)")
            while True:
                reply = self._child.recv(deadline, method, note)
                if reply.get("id") in (rid, None):
                    break
        if reply.get("ok"):
            return reply.get("result")
        raise _rpc_error(reply.get("error"), method, reply)

    def execute(self, command: str, params: dict | None = None, wait: bool | None = None, *,
                timeout: float | None = None):
        """`engine.execute {command, params, wait}`; wait=False returns {job, pending}."""
        _check_params(params, command)
        body: dict = {"command": command}
        if params is not None:
            body["params"] = params
        if wait is not None:
            body["wait"] = bool(wait)
        return self.call("engine.execute", body, timeout=timeout)

    def methods(self) -> list:
        if self._methods is None:
            self._methods = list(self.call("methods"))
        return self._methods

    def _batch_step(self, step) -> dict:
        if isinstance(step, dict):
            if "command" not in step and "method" not in step:
                raise InvalidRequest(f"a batch step needs `command` or `method`: {step!r}", "batch")
            return step
        name, params = _split_step(step)
        _check_params(params, name)
        key = "command"
        if name in self.methods():
            ids = {c["id"] for c in registry(self.cli)}
            if name not in ids:
                key = "method"   # e.g. doc.save: a method, not an engine command
        out: dict = {key: name}
        if params is not None:
            out["params"] = params
        return out

    def batch(self, steps, stop_on_error: bool = True, *, check: bool = True,
              timeout: float | None = None) -> dict:
        """serve `batch`: steps are (id, params) / bare ids / raw {command|method} dicts.

        Returns {completed, failed, results}. With check=True a failed step raises
        BatchFailed (.result holds the reply); steps that completed stay applied."""
        norm = [self._batch_step(s) for s in steps]
        result = self.call("batch", {"steps": norm, "stopOnError": bool(stop_on_error)}, timeout=timeout)
        if check and isinstance(result, dict) and result.get("failed"):
            results = result.get("results") or []
            index = next((i for i, r in enumerate(results) if not r.get("ok")), len(results) - 1)
            step = norm[index] if 0 <= index < len(norm) else {}
            name = step.get("command") or step.get("method") or "?"
            error = results[index].get("error") if 0 <= index < len(results) else "unknown error"
            raise BatchFailed(f"step {index} ({name}) failed: {error}; completed {result.get('completed', 0)}, "
                              f"failed {result.get('failed')} (completed steps stay applied)", result=result)
        return result

    def stderr_tail(self, lines: int = 15) -> str:
        return self._child.stderr_tail(lines)

    def close(self) -> None:
        self._child.close()

    def kill(self) -> None:
        self._child.kill()

    @property
    def alive(self) -> bool:
        return self._child.proc.poll() is None

    def __enter__(self) -> "Serve":
        return self

    def __exit__(self, *exc) -> None:
        self.close()


class Mcp:
    """A stdio JSON-RPC client for `photocraft-cli mcp` (headless or bridge mode)."""

    def __init__(self, read_root=None, write_root=None, *, bridge=None, token_file=None, cli=None,
                 cwd=None, env=None, timeout: float = 120.0, protocol_version: str = MCP_PROTOCOL_VERSION):
        self.cli = _resolve_cli(cli)
        argv = [str(self.cli), "mcp"]
        child_env = _child_env(env, drop_control=bridge is None or token_file is not None)
        if bridge is not None:
            target = f"127.0.0.1:{resolve_port(bridge)}" if str(bridge).isdigit() else str(bridge)
            argv += ["--bridge", target]
            if token_file is not None:
                path = Path(os.path.expanduser(os.fspath(token_file)))
                if not path.is_file():
                    raise AuthError(f"token file {path} does not exist; no other location is searched", "mcp")
                argv += ["--control-token-file", str(path)]
        if read_root is not None:
            argv += ["--automation-read-root", os.fspath(read_root)]
        if write_root is not None:
            argv += ["--automation-write-root", os.fspath(write_root)]
        self.timeout = float(timeout)
        self._lock = threading.Lock()
        self._id = 0
        self._tools: list | None = None
        self.notifications: collections.deque = collections.deque(maxlen=100)
        self._child = _Child(argv, cwd=cwd, env=child_env, label="mcp")
        try:
            self.server = self.request("initialize", {
                "protocolVersion": protocol_version,
                "capabilities": {},
                "clientInfo": {"name": "photocraft-skill", "version": "1"},
            })
            self.notify("notifications/initialized")
        except TransportError as exc:
            self.kill()
            raise CliError(f"photocraft-cli mcp did not start: {exc}", argv=argv) from None
        except Exception:
            self.kill()
            raise

    def notify(self, method: str, params: dict | None = None) -> None:
        msg: dict = {"jsonrpc": "2.0", "method": method}
        if params is not None:
            msg["params"] = params
        with self._lock:
            self._child.send(msg, method)

    def _answer(self, msg: dict) -> None:
        if msg.get("method") == "ping":
            reply = {"jsonrpc": "2.0", "id": msg["id"], "result": {}}
        else:
            reply = {"jsonrpc": "2.0", "id": msg["id"],
                     "error": {"code": -32601, "message": "method not supported by this client"}}
        try:
            self._child.send(reply, str(msg.get("method")))
        except NotSent:
            pass

    def request(self, method: str, params: dict | None = None, *, timeout: float | None = None):
        """One JSON-RPC request; returns `result` or raises RpcError (with .code)."""
        limit = self.timeout if timeout is None else float(timeout)
        with self._lock:
            self._id += 1
            rid = self._id
            msg: dict = {"jsonrpc": "2.0", "id": rid, "method": method}
            if params is not None:
                msg["params"] = params
            self._child.send(msg, method)
            deadline = time.monotonic() + limit
            note = f"no reply within {limit:g}s; a tool call may still run and apply"
            while True:
                reply = self._child.recv(deadline, method, note)
                if "method" in reply:
                    if "id" in reply:
                        self._answer(reply)
                    else:
                        self.notifications.append(reply)
                    continue
                if reply.get("id") == rid or (reply.get("id") is None and "error" in reply):
                    break
        if "error" in reply:
            err = reply.get("error") or {}
            message = err.get("message", str(err)) if isinstance(err, dict) else str(err)
            raise RpcError(message, method, code=err.get("code") if isinstance(err, dict) else None,
                           data=err.get("data") if isinstance(err, dict) else None, reply=reply)
        return reply.get("result")

    def tools(self) -> list:
        """tools/list (cached): [{name, description, inputSchema, …}]."""
        if self._tools is None:
            self._tools = list((self.request("tools/list") or {}).get("tools", []))
        return self._tools

    def call_tool(self, name: str, arguments: dict | None = None, *, timeout: float | None = None,
                  check: bool = False) -> dict:
        """tools/call; returns {content, isError}. Unknown or camelCase arguments raise
        RpcError -32602 before anything runs; a failing tool returns isError:true."""
        _check_params(arguments, name)
        result = self.request("tools/call", {"name": name, "arguments": arguments or {}}, timeout=timeout)
        if check and isinstance(result, dict) and result.get("isError"):
            raise ToolError(_content_text(result) or "tool reported an error", name, result=result)
        return result

    def call_json(self, name: str, arguments: dict | None = None, *, timeout: float | None = None):
        """call_tool with check=True, then the first text block parsed as JSON."""
        return content_json(self.call_tool(name, arguments, timeout=timeout, check=True))

    def read_resource(self, uri: str) -> dict:
        """resources/read; content_json(result) decodes the JSON resources."""
        return self.request("resources/read", {"uri": uri})

    def stderr_tail(self, lines: int = 15) -> str:
        return self._child.stderr_tail(lines)

    def close(self) -> None:
        self._child.close()

    def kill(self) -> None:
        self._child.kill()

    @property
    def alive(self) -> bool:
        return self._child.proc.poll() is None

    def __enter__(self) -> "Mcp":
        return self

    def __exit__(self, *exc) -> None:
        self.close()


def _content_text(result) -> str | None:
    items = (result or {}).get("content") or (result or {}).get("contents") or []
    for item in items:
        if isinstance(item, dict) and isinstance(item.get("text"), str):
            return item["text"]
    return None


def content_json(result):
    """First text block of an MCP tool or resource result, parsed as JSON when possible."""
    text = _content_text(result)
    if text is None:
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return text


def content_images(result) -> list[tuple[str, bytes]]:
    """[(mimeType, bytes)] for the image blocks of an MCP tool result."""
    out = []
    for item in (result or {}).get("content") or []:
        if isinstance(item, dict) and item.get("type") == "image" and item.get("data"):
            out.append((item.get("mimeType", "application/octet-stream"), base64.b64decode(item["data"])))
    return out


# --------------------------------------------------------------------------- TCP control client
class Control:
    """JSON-lines TCP client for the desktop control port or `serve --port`."""

    def __init__(self, port=None, *, token=None, token_file=None, timeout: float = DEFAULT_CONTROL_TIMEOUT,
                 connect_timeout: float = 5.0, auth_timeout: float = 10.0,
                 idle_reconnect: float = IDLE_RECONNECT):
        self.host = "127.0.0.1"
        self.port = resolve_port(port)
        self.timeout = float(timeout)
        self.connect_timeout = float(connect_timeout)
        self.auth_timeout = float(auth_timeout)
        self.idle_reconnect = float(idle_reconnect)
        self.__token = resolve_token(token, token_file)
        self._sock: socket.socket | None = None
        self._buf = bytearray()
        self._id = 0
        self._last_io = 0.0
        self._lock = threading.Lock()
        self.connects = 0      # successful authentications
        self.reconnects = 0    # of which after a drop or idle period

    def __repr__(self) -> str:
        state = "connected" if self._sock is not None else "idle"
        return f"<pclib.Control {self.host}:{self.port} {state}>"

    @property
    def address(self) -> str:
        return f"{self.host}:{self.port}"

    def _drop(self) -> None:
        if self._sock is not None:
            try:
                self._sock.close()
            except OSError:
                pass
        self._sock = None
        self._buf.clear()

    def _read_line(self, deadline: float) -> bytes:
        while True:
            newline = self._buf.find(b"\n")
            if newline >= 0:
                line = bytes(self._buf[:newline])
                del self._buf[:newline + 1]
                return line
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise socket.timeout("timed out")
            self._sock.settimeout(remaining)
            chunk = self._sock.recv(1 << 16)
            if not chunk:
                raise EOFError("connection closed")
            self._buf += chunk
            if len(self._buf) > MAX_REPLY_BYTES + 1024:
                raise EOFError("reply exceeds the 8 MiB budget")

    def _peer_closed(self) -> bool:
        if self._buf:
            return False
        try:
            readable, _, broken = select.select([self._sock], [], [self._sock], 0)
        except (OSError, ValueError):
            return True
        if broken:
            return True
        if not readable:
            return False
        previous = self._sock.gettimeout()
        try:
            self._sock.settimeout(0)
            data = self._sock.recv(1, socket.MSG_PEEK)
        except BlockingIOError:
            return False
        except OSError:
            return True
        finally:
            try:
                self._sock.settimeout(previous)
            except OSError:
                pass
        return data == b""

    def _connect(self) -> None:
        try:
            sock = socket.create_connection((self.host, self.port), timeout=self.connect_timeout)
        except OSError as exc:
            raise NotSent(f"cannot connect to {self.address}: {exc.strerror or exc} "
                          "(is PhotoCraft listening there? the desktop app needs --control <port>)",
                          "auth") from None
        sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        self._sock = sock
        self._buf.clear()
        frame = json.dumps({"id": "auth", "method": "auth", "params": {"token": self.__token}}).encode("ascii") + b"\n"
        try:
            sock.sendall(frame)
            raw = self._read_line(time.monotonic() + self.auth_timeout)
        except socket.timeout:
            self._drop()
            raise AuthError(f"no reply to auth from {self.address} within {self.auth_timeout:g}s "
                            "(not a PhotoCraft control port?)", "auth") from None
        except (EOFError, OSError):
            self._drop()
            raise AuthError(f"{self.address} closed the connection during auth "
                            "(not a PhotoCraft control port, or it is shutting down)", "auth") from None
        try:
            reply = json.loads(raw.decode("utf-8", "replace"))
        except json.JSONDecodeError:
            self._drop()
            raise AuthError(f"{self.address} answered auth with something that is not JSON "
                            "(not a PhotoCraft control port?)", "auth") from None
        if not (isinstance(reply, dict) and reply.get("ok")):
            self._drop()
            said = _scrub(str(reply.get("error") if isinstance(reply, dict) else reply))
            raise AuthError(f"authentication failed on {self.address}: server replied {said!r}; "
                            "the token does not belong to this PhotoCraft instance (stale token "
                            "file or wrong port?)", "auth")
        self.connects += 1
        self._last_io = time.monotonic()

    def _ensure_connected(self) -> None:
        if self._sock is not None:
            idle = time.monotonic() - self._last_io
            if idle >= self.idle_reconnect or self._peer_closed():
                self._drop()
                self.reconnects += 1
        if self._sock is None:
            self._connect()

    def call(self, method: str, params: dict | None = None, *, timeout: float | None = None):
        """Send one request; returns `result` or raises RpcError / NotSent / MayHaveCompleted."""
        _check_method(method)
        _check_params(params, method)
        limit = self.timeout if timeout is None else float(timeout)
        with self._lock:
            rid = self._id + 1
            line = _encode_line({"id": rid, "method": method, "params": params if params is not None else {}}, method)
            self._ensure_connected()
            self._id = rid
            try:
                self._sock.settimeout(limit)
                self._sock.sendall(line)
            except OSError as exc:
                self._drop()
                raise MayHaveCompleted(f"sending failed ({exc.strerror or exc}); the request may "
                                       "have reached PhotoCraft: inspect before resending", method) from None
            deadline = time.monotonic() + limit
            try:
                while True:
                    raw = self._read_line(deadline)
                    try:
                        reply = json.loads(raw.decode("utf-8", "replace"))
                    except json.JSONDecodeError:
                        continue
                    if isinstance(reply, dict) and reply.get("id") in (rid, None):
                        break
            except socket.timeout:
                self._drop()
                raise ReplyTimeout(f"no reply within {limit:g}s; it may still be running and may still "
                                   "apply: inspect the document before resending (long commands: "
                                   "pass wait:false and poll jobs.list)", method) from None
            except (EOFError, OSError) as exc:
                self._drop()
                raise MayHaveCompleted(f"connection lost while waiting for the reply ({exc}); it may "
                                       "have completed: inspect before resending", method) from None
            self._last_io = time.monotonic()
        if reply.get("ok"):
            return reply.get("result")
        raise _rpc_error(reply.get("error"), method, reply)

    def execute(self, command: str, params: dict | None = None, wait: bool | None = None, *,
                timeout: float | None = None):
        """`engine.execute {command, params, wait}`."""
        _check_params(params, command)
        body: dict = {"command": command}
        if params is not None:
            body["params"] = params
        if wait is not None:
            body["wait"] = bool(wait)
        return self.call("engine.execute", body, timeout=timeout)

    def close(self) -> None:
        with self._lock:
            self._drop()

    def __enter__(self) -> "Control":
        return self

    def __exit__(self, *exc) -> None:
        self.close()


if __name__ == "__main__":
    setup_stdio()
    print(__doc__)
