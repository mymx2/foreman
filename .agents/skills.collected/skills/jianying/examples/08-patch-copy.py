#!/usr/bin/env python3
"""案例 08：对已有明文草稿做 patch，默认写副本。

验证 `set_text` / `set_style` 只改副本，原草稿仍保持旧文案；这是“修改用户草稿”
最常见的入口，也是 `--in-place` 之外的安全路径。
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
JY = ROOT / "scripts" / "jy.py"


def _run(args, cwd, timeout=120):
    return subprocess.run([sys.executable, str(JY), *args], cwd=str(cwd),
                          capture_output=True, text=True, encoding="utf-8",
                          errors="replace", timeout=timeout)


def _inspect(path, cwd):
    proc = _run(["inspect", str(path)], cwd)
    try:
        return proc, json.loads(proc.stdout)
    except json.JSONDecodeError:
        return proc, {}


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="jy-example-") as tmp:
        root = Path(tmp)
        plan = {
            "schema": "jianying-plan/v1",
            "name": "example-patch",
            "canvas": {"width": 640, "height": 360, "fps": 30},
            "tracks": [{
                "type": "text",
                "segments": [{"text": "原文字", "start": 0, "duration": 2,
                              "font_size": 10, "y": -0.5}],
            }],
        }
        (root / "plan.json").write_text(
            json.dumps(plan, ensure_ascii=False, indent=2), "utf-8")

        built = _run(["build", "--plan", "plan.json", "--out", "draft", "--no-cover"], root)
        try:
            result = json.loads(built.stdout)
        except json.JSONDecodeError:
            print(f"build 没有返回 JSON：{built.stdout}\n{built.stderr}")
            return 1
        if built.returncode != 0 or not result.get("ok"):
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 1

        ops = {
            "ops": [
                {"op": "set_text", "segment": 0, "text": "改后文字",
                 "font_size": 10, "color": "#00FF00"},
                {"op": "set_style", "segment": 0, "font_size": 11, "color": "#FF0000"},
            ]
        }
        (root / "ops.json").write_text(
            json.dumps(ops, ensure_ascii=False, indent=2), "utf-8")

        patched = _run(["patch", "draft", "--ops", "ops.json", "--out", "copy"], root)
        try:
            patch_result = json.loads(patched.stdout)
        except json.JSONDecodeError:
            print(f"patch 没有返回 JSON：{patched.stdout}\n{patched.stderr}")
            return 1
        if patched.returncode != 0 or not patch_result.get("ok"):
            print(json.dumps(patch_result, ensure_ascii=False, indent=2))
            return 1

        original_proc, original = _inspect("draft", root)
        copy_proc, copied = _inspect("copy", root)
        original_texts = [item.get("text") for item in (original.get("data") or {}).get("texts") or []]
        copied_texts = [item.get("text") for item in (copied.get("data") or {}).get("texts") or []]
        ok = (
            original_proc.returncode == 0 and copy_proc.returncode == 0
            and original.get("ok") and copied.get("ok")
            and original_texts == ["原文字"] and copied_texts == ["改后文字"]
            and not (copied.get("data") or {}).get("missing_media")
        )
        print(json.dumps({
            "ok": bool(ok),
            "case": "08-patch-copy",
            "original_texts": original_texts,
            "copied_texts": copied_texts,
        }, ensure_ascii=False))
        return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
