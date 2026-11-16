#!/usr/bin/env python3
"""19：版本链：build → patch → diff → restore（离线结构，不启动剪映）。"""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

from _jy_example import build, finish, run_cli


def cli(root, *args):
    completed = run_cli(list(args), root)
    try:
        return json.loads(completed.stdout), completed.returncode
    except json.JSONDecodeError:
        print(completed.stdout, completed.stderr)
        return None, completed.returncode


def text_of(document):
    item = (document.get("materials") or {}).get("texts", [{}])[0]
    return json.loads(item.get("content") or "{}").get("text")


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="jy-example-") as tmp:
        root = Path(tmp)
        plan = {
            "schema": "jianying-plan/v1",
            "name": "版本链",
            "canvas": {"width": 640, "height": 360, "fps": 30},
            "tracks": [{"type": "text", "name": "字幕", "segments": [{
                "text": "第一版", "start": 0, "duration": 2, "font_size": 10,
            }]}],
        }
        built, document = build(root, plan)
        if not document:
            return 1
        ops = root / "ops.json"
        ops.write_text(json.dumps({
            "ops": [{"op": "set_text", "segment": 0, "text": "第二版"}]
        }, ensure_ascii=False), "utf-8")
        patched, code = cli(root, "patch", "draft", "--ops", "ops.json",
                            "--out", "copy", "--version-label", "改文案")
        if code != 0 or not patched or not patched.get("ok"):
            print(json.dumps(patched, ensure_ascii=False, indent=2))
            return 1
        listed, _ = cli(root, "version", "list", "copy")
        diff, _ = cli(root, "version", "diff", "copy", "v002")
        restored, code = cli(root, "version", "restore", "copy", "v001",
                             "--out", "restored", "--name", "恢复第一版")
        if code != 0 or not restored or not restored.get("ok"):
            print(json.dumps(restored, ensure_ascii=False, indent=2))
            return 1
        restored_document = json.loads(
            (root / "restored" / "draft_info.json").read_text("utf-8"))
        versions = (listed or {}).get("data", {}).get("versions", [])
        checks = {
            "build_v001": [item.get("id") for item in versions] == ["v001", "v002"],
            "patch_parent": versions[1].get("parent") == "v001" if len(versions) > 1 else False,
            "patch_label": versions[1].get("label") == "改文案" if len(versions) > 1 else False,
            "plan_copied": bool((root / "copy" / versions[0].get("plan", "missing")).is_file()),
            "ops_copied": bool((root / "copy" / versions[1].get("ops", "missing")).is_file()),
            "diff_sees_text": "text added: '第二版'" in (diff or {}).get("data", {}).get("changes", []),
            "restore_old_text": text_of(restored_document) == "第一版",
            "restore_new_id": restored_document.get("id") != document.get("id"),
            "restore_has_history": (root / "restored" / ".jianying-versions" / "versions.json").is_file(),
        }
        return finish("19-version-chain", checks)


if __name__ == "__main__":
    raise SystemExit(main())
