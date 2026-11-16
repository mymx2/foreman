#!/usr/bin/env python3
"""案例 09：publish 默认 dry-run。

验证 `publish` 在没有 `--apply` 时只计算目标路径、不复制、不改
`root_meta_info.json`。这是“放进剪映首页”的安全前置步骤。
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


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="jy-example-") as tmp:
        root = Path(tmp)
        plan = {
            "schema": "jianying-plan/v1",
            "name": "example-publish",
            "canvas": {"width": 640, "height": 360, "fps": 30},
            "tracks": [{
                "type": "text",
                "segments": [{"text": "待登记", "start": 0, "duration": 2}],
            }],
        }
        (root / "plan.json").write_text(
            json.dumps(plan, ensure_ascii=False, indent=2), "utf-8")
        built = _run(["build", "--plan", "plan.json", "--out", "draft", "--no-cover"], root)
        try:
            build_result = json.loads(built.stdout)
        except json.JSONDecodeError:
            print(f"build 没有返回 JSON：{built.stdout}\n{built.stderr}")
            return 1
        if built.returncode != 0 or not build_result.get("ok"):
            print(json.dumps(build_result, ensure_ascii=False, indent=2))
            return 1

        draft_root = root / "draft-root"
        draft_root.mkdir()
        index = {"all_draft_store": [], "draft_ids": 0}
        index_path = draft_root / "root_meta_info.json"
        index_path.write_text(json.dumps(index, ensure_ascii=False, indent=2), "utf-8")
        before = index_path.read_bytes()

        published = _run([
            "publish", "draft", "--draft-root", str(draft_root), "--name", "首页草稿",
        ], root)
        try:
            result = json.loads(published.stdout)
        except json.JSONDecodeError:
            print(f"publish 没有返回 JSON：{published.stdout}\n{published.stderr}")
            return 1
        data = result.get("data") or {}
        target = Path(str(data.get("target") or ""))
        ok = (
            published.returncode == 0 and result.get("ok")
            and data.get("action") == "copy+register"
            and data.get("dry_run") is True
            and data.get("applied") in (None, False)
            and not target.exists()
            and index_path.read_bytes() == before
        )
        print(json.dumps({
            "ok": bool(ok),
            "case": "09-publish-dry-run",
            "action": data.get("action"),
            "dry_run": data.get("dry_run"),
            "target_exists": target.exists(),
            "index_unchanged": index_path.read_bytes() == before,
        }, ensure_ascii=False))
        return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
