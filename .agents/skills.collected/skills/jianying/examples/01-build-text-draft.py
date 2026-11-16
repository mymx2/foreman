#!/usr/bin/env python3
"""案例 01：用真实 CLI 生成纯文字草稿并 inspect，验证轨道/文字/时长。离线，不启动剪映。"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
JY = ROOT / "scripts" / "jy.py"


def main() -> int:
    plan = {
        "schema": "jianying-plan/v1", "name": "example-text",
        "canvas": {"width": 640, "height": 360, "fps": 30},
        "tracks": [{"type": "text", "segments": [
            {"text": "第一句", "start": 0, "duration": 1, "y": -0.7},
            {"text": "第二句", "start": 1, "duration": 1, "y": -0.7}]}],
    }
    with tempfile.TemporaryDirectory() as td:
        work = Path(td)
        p = work / "plan.json"
        p.write_text(json.dumps(plan, ensure_ascii=False), "utf-8")
        out = work / "draft"
        build = subprocess.run([sys.executable, str(JY), "build", "--plan", str(p), "--out", str(out)],
                               capture_output=True, text=True, encoding="utf-8")
        b = json.loads(build.stdout)
        if not b.get("ok"):
            print(json.dumps({"ok": False, "stage": "build", "error": b.get("error")}, ensure_ascii=False))
            return 1
        inspect = subprocess.run([sys.executable, str(JY), "inspect", str(out)],
                                 capture_output=True, text=True, encoding="utf-8")
        i = json.loads(inspect.stdout)
        data = i.get("data") or {}
        ok = i.get("ok") and not data.get("missing_media") and len(data.get("texts") or []) == 2
        print(json.dumps({"ok": bool(ok), "case": "01-build-text-draft",
                          "duration": data.get("duration"), "texts": len(data.get("texts") or []),
                          "tracks": len(data.get("tracks") or [])}, ensure_ascii=False))
        return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())