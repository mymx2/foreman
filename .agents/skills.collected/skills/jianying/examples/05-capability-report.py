#!/usr/bin/env python3
"""案例 05：只读能力报告。

验证 `capability_probe.py` 能输出可机读的能力矩阵，并且三类边界都有条目：
实现、计划、资源/账号受限。不启动剪映，不读用户素材。
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PROBE = ROOT / "scripts" / "capability_probe.py"
ALLOWED = {"implemented", "planned", "conditional", "missing_resource",
           "host_only", "account_gated", "manual", "unverified"}


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="jy-example-") as tmp:
        out = Path(tmp) / "capabilities.json"
        proc = subprocess.run(
            [sys.executable, str(PROBE), "--out", str(out)],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=120,
        )
        if proc.returncode != 0:
            print(f"capability_probe 失败：{proc.stdout}\n{proc.stderr}")
            return 1
        if not out.is_file():
            print("capability_probe 没有写出 --out 文件")
            return 1
        try:
            payload = json.loads(out.read_text("utf-8"))
        except json.JSONDecodeError as exc:
            print(f"能力报告不是合法 JSON：{exc}")
            return 1

        if payload.get("schema") != "jianying-capabilities/v1":
            print(f"schema 不对：{payload.get('schema')!r}")
            return 1
        capabilities = payload.get("capabilities")
        if not isinstance(capabilities, list) or len(capabilities) < 20:
            print(f"能力条目太少：{len(capabilities) if isinstance(capabilities, list) else None}")
            return 1
        ids = set()
        for index, item in enumerate(capabilities):
            if not isinstance(item, dict):
                print(f"capabilities[{index}] 不是对象")
                return 1
            for key in ("id", "label", "category", "channel", "status", "code_status"):
                if not item.get(key):
                    print(f"capabilities[{index}] 缺 {key}: {item}")
                    return 1
            if item["status"] not in ALLOWED:
                print(f"capabilities[{index}] 状态非法：{item['status']!r}")
                return 1
            if item["id"] in ids:
                print(f"能力 id 重复：{item['id']}")
                return 1
            ids.add(item["id"])

        summary = payload.get("summary") or {}
        if summary.get("total") != len(capabilities):
            print(f"summary.total={summary.get('total')} != {len(capabilities)}")
            return 1
        by_status = summary.get("by_status") or {}
        if not all(isinstance(v, int) and v >= 0 for v in by_status.values()):
            print(f"summary.by_status 有非整数：{by_status}")
            return 1
        if sum(by_status.values()) != len(capabilities):
            print(f"by_status 合计 {sum(by_status.values())} != {len(capabilities)}")
            return 1

        # 三类边界必须都有代表，而不是只列“已实现”。
        for required in ("implemented", "planned", "conditional", "host_only", "account_gated"):
            if by_status.get(required, 0) < 1:
                print(f"缺少 {required} 类能力条目")
                return 1

        # 隐私：只读报告不能出现 token/cookie/secret 字段。
        lowered = json.dumps(payload, ensure_ascii=False).lower()
        for forbidden in ("localServerToken".lower(), "cookie", "authorization"):
            if forbidden in lowered:
                print(f"能力报告出现敏感字段：{forbidden}")
                return 1

        official = (payload.get("official") or {}).get("skills") or {}
        if not isinstance(official.get("directories"), list):
            print("official.skills.directories 不是数组")
            return 1

        print(json.dumps({
            "ok": True,
            "case": "05-capability-report",
            "total": len(capabilities),
            "by_status": by_status,
            "official_skills": len(official.get("directories") or []),
        }, ensure_ascii=False))
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
