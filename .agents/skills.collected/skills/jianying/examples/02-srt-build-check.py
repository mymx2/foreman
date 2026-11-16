#!/usr/bin/env python3
"""案例 02：srt.build 生成字幕再 srt.check 校验，确认行数与无 issues。离线。"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CLI = ROOT / "scripts" / "subtitles" / "cli.py"


def _run(*args):
    proc = subprocess.run([sys.executable, str(CLI), *args],
                          capture_output=True, text=True, encoding="utf-8")
    return json.loads(proc.stdout)


def main() -> int:
    with tempfile.TemporaryDirectory() as td:
        work = Path(td)
        text = work / "lines.txt"
        text.write_text("第一句字幕\n第二句字幕\n第三句字幕\n", "utf-8")
        srt = work / "out.srt"
        build = _run("srt.build", "--text", str(text), "--total", "6", "--out", str(srt))
        if not build.get("ok"):
            print(json.dumps({"ok": False, "stage": "srt.build", "error": build}, ensure_ascii=False))
            return 1
        check = _run("srt.check", "--in", str(srt))
        data = check.get("data") or {}
        ok = check.get("ok") and data.get("lines", 0) == 3 and not data.get("issues")
        print(json.dumps({"ok": bool(ok), "case": "02-srt-build-check",
                          "lines": data.get("lines"), "issues": data.get("issues")}, ensure_ascii=False))
        return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())