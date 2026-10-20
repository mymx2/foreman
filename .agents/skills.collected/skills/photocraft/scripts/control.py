#!/usr/bin/env python3
"""Send JSON-lines requests to a PhotoCraft control port (agent: execute).

Talks to the desktop app started with `photocraft --control <port> --control-token-file F`
(the only way to reach ui.* / app.* methods) or to `photocraft-cli serve --port <port>`.

  python <skill-dir>/scripts/control.py --port 7878 --token-file F '[["ui.inspect"]]'
  python <skill-dir>/scripts/control.py --port 7878 '[["engine.execute",{"command":"document.inspect"}]]'
  printf '%s' '[["engine.execute",{"command":"file.new","params":{"name":"中文"}}]]' | python <skill-dir>/scripts/control.py --port 7878

Payload (argv or UTF-8 stdin): a JSON array of requests, each `[method]`, `[method, params]`
or `{"method":…, "params":…}`; a single `[method, params]` is accepted too. params must be
an object or null. In Windows PowerShell set `$OutputEncoding = [System.Text.UTF8Encoding]::new()`
before piping non-ASCII text.

Output: exactly one JSON line per request, in order, with "status":
  ok                  {"result": …}
  error               the server ran or validated the request and refused it ("error": text)
  not-sent            it did not run, safe to resend: invalid locally, no connection or auth,
                      skipped after an earlier failure, or the desktop's "timeout: not run"
  may-have-completed  it reached PhotoCraft but the reply was lost (client timeout, dropped
                      connection, desktop "timeout: no reply in 60s"): inspect before resending
Processing stops at the first request that is not ok (the rest are not-sent) unless
--keep-going is given; requests after a failed one would act on whatever document is active.

Port: --port, else PHOTOCRAFT_CONTROL_PORT (there is no default port). Token:
--token-file, else PHOTOCRAFT_CONTROL_TOKEN, else PHOTOCRAFT_CONTROL_TOKEN_FILE; a named
file that does not exist is an error and no other location is tried. The token is sent only
to 127.0.0.1:<port> and never printed. Reconnects (and re-authenticates) only before a
request is written, e.g. after the 30 s idle drop; a written request is never resent.

Exit codes: 0 every request ok, 1 some request not ok, 2 usage error (payload, port, flags).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import pclib  # noqa: E402

HINTS = {
    "not-sent": "did not run; safe to resend",
    "may-have-completed": "may have run; inspect the document before resending",
}


class Emitter:
    def __init__(self, ascii_only: bool):
        self.ascii_only = ascii_only
        self.statuses: list[str] = []

    def __call__(self, index: int, method, status: str, *, result=None, error: str | None = None) -> None:
        line: dict = {"index": index, "method": method, "status": status}
        if status == "ok":
            line["result"] = result
        else:
            line["error"] = error
            if status in HINTS:
                line["hint"] = HINTS[status]
        self.statuses.append(status)
        print(json.dumps(line, ensure_ascii=self.ascii_only), flush=True)


def parse_payload(text: str) -> list:
    """[(method, params) | InvalidRequest] in order; UsageError when unusable."""
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise pclib.UsageError(f"payload is not valid JSON: {exc}") from None
    if isinstance(data, dict):
        data = [data]
    elif isinstance(data, list) and data and isinstance(data[0], str):
        data = [data]
    if not isinstance(data, list) or not data:
        raise pclib.UsageError("payload must be a non-empty JSON array of [method, params] requests")
    out: list = []
    for item in data:
        method, params = None, None
        if isinstance(item, list) and 1 <= len(item) <= 2:
            method = item[0]
            params = item[1] if len(item) == 2 else None
        elif isinstance(item, dict) and set(item) <= {"method", "params", "id"}:
            method, params = item.get("method"), item.get("params")
        else:
            out.append(pclib.InvalidRequest(f"a request must be [method, params] or "
                                            f"{{\"method\", \"params\"}}, got {json.dumps(item)[:120]}"))
            continue
        if not isinstance(method, str) or not method:
            out.append(pclib.InvalidRequest(f"method must be a non-empty string, got {json.dumps(method)[:80]}"))
        elif params is not None and not isinstance(params, dict):
            out.append(pclib.InvalidRequest(f"params must be a JSON object or null, got {json.dumps(params)[:80]}",
                                            method))
        else:
            out.append((method, params))
    return out


def status_of(exc: Exception) -> str:
    if isinstance(exc, pclib.NotSent):
        return "not-sent"
    if isinstance(exc, pclib.MayHaveCompleted):
        return "may-have-completed"
    if isinstance(exc, pclib.RpcError):
        if exc.safe_to_resend is True:
            return "not-sent"
        if exc.safe_to_resend is False:
            return "may-have-completed"
        return "error"
    return "error"


def message_of(exc: Exception) -> str:
    return getattr(exc, "message", None) or str(exc)


def main(argv: list[str] | None = None) -> int:
    pclib.setup_stdio()
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--port", help="control port (default: PHOTOCRAFT_CONTROL_PORT)")
    ap.add_argument("--token-file", help="token file the PhotoCraft process was started with")
    ap.add_argument("--timeout", type=float, default=pclib.DEFAULT_CONTROL_TIMEOUT,
                    help="seconds to wait for each reply (default 55, below the desktop's 60 s deadline)")
    ap.add_argument("--keep-going", action="store_true", help="continue after a request that is not ok")
    ap.add_argument("--ascii", action="store_true", help="escape non-ASCII characters in the output")
    ap.add_argument("payload", nargs="?", help="JSON requests (default: read UTF-8 stdin)")
    args = ap.parse_args(argv)
    emit = Emitter(args.ascii)

    try:
        text = args.payload if args.payload is not None else pclib.read_stdin_text()
        requests = parse_payload(text)
    except pclib.UsageError as exc:
        print(f"control.py: {exc}", file=sys.stderr)
        return 2
    if args.timeout <= 0:
        print("control.py: --timeout must be positive", file=sys.stderr)
        return 2

    def name(req):
        return req[0] if isinstance(req, tuple) else getattr(req, "method", None)

    invalid = [i for i, req in enumerate(requests) if not isinstance(req, tuple)]
    if invalid and not args.keep_going:
        for i, req in enumerate(requests):
            if isinstance(req, tuple):
                emit(i, name(req), "not-sent", error=f"nothing was sent: request {invalid[0]} is invalid")
            else:
                emit(i, name(req), "not-sent", error=f"invalid request: {message_of(req)}")
        return 2

    try:
        ctl = pclib.Control(args.port, token_file=args.token_file, timeout=args.timeout,
                            auth_timeout=min(10.0, args.timeout))
    except pclib.PcError as exc:
        for i, req in enumerate(requests):
            emit(i, name(req), "not-sent", error=message_of(exc))
        return 2 if isinstance(exc, pclib.UsageError) else 1

    stop_reason: str | None = None
    with ctl:
        for i, req in enumerate(requests):
            if stop_reason:
                emit(i, name(req), "not-sent", error=stop_reason)
                continue
            if not isinstance(req, tuple):
                emit(i, name(req), "not-sent", error=f"invalid request: {message_of(req)}")
                continue
            method, params = req
            try:
                result = ctl.call(method, params)
            except (pclib.RpcError, pclib.TransportError) as exc:
                status = status_of(exc)
                emit(i, method, status, error=message_of(exc))
                if isinstance(exc, pclib.NotSent) and exc.method == "auth":
                    stop_reason = f"not sent: {message_of(exc)}"
                elif not args.keep_going:
                    stop_reason = (f"skipped: request {i} ended with status {status} "
                                   "(pass --keep-going to continue after failures)")
                continue
            emit(i, method, "ok", result=result)
    return 0 if all(s == "ok" for s in emit.statuses) else 1


if __name__ == "__main__":
    raise SystemExit(main())
