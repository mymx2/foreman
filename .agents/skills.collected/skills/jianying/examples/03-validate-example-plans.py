#!/usr/bin/env python3
"""案例 03：校验随技能交付的示例计划/补丁仍是合法结构。离线，纯静态。"""
from __future__ import annotations

import json
import sys
from pathlib import Path

EX = Path(__file__).resolve().parent
KNOWN_OPS = {"set_text", "set_style", "set_volume", "set_speed", "shift", "trim",
             "set_transform", "remove", "rename", "set_canvas", "fps"}


def _check_plan(path: Path) -> list[str]:
    issues = []
    plan = json.loads(path.read_text("utf-8"))
    if plan.get("schema") != "jianying-plan/v1":
        issues.append(f"{path.name}: schema 不是 jianying-plan/v1")
    canvas = plan.get("canvas") or {}
    for key in ("width", "height", "fps"):
        if not canvas.get(key):
            issues.append(f"{path.name}: canvas 缺 {key}")
    tracks = plan.get("tracks")
    if not isinstance(tracks, list) or not tracks:
        issues.append(f"{path.name}: tracks 为空")
    else:
        for i, tr in enumerate(tracks):
            if not tr.get("type") or not isinstance(tr.get("segments"), list):
                issues.append(f"{path.name}: 轨道 {i} 缺 type/segments")
    return issues


def main() -> int:
    issues: list[str] = []
    for name in ("plan_basic.json", "plan_vertical.json"):
        path = EX / name
        if not path.is_file():
            issues.append(f"缺少示例 {name}")
            continue
        issues.extend(_check_plan(path))
    ops_path = EX / "ops_example.json"
    if ops_path.is_file():
        ops = json.loads(ops_path.read_text("utf-8")).get("ops")
        if not isinstance(ops, list) or not ops:
            issues.append("ops_example.json: ops 为空")
        else:
            for i, op in enumerate(ops):
                if op.get("op") not in KNOWN_OPS:
                    issues.append(f"ops_example.json: 第 {i} 个 op 非法 {op.get('op')}")
    else:
        issues.append("缺少示例 ops_example.json")
    ok = not issues
    print(json.dumps({"ok": ok, "case": "03-validate-example-plans",
                      "issues": issues}, ensure_ascii=False))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())