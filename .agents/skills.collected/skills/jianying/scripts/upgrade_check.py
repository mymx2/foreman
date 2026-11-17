#!/usr/bin/env python3
"""Read-only upgrade check for the jianying skill.

Compares the installed 剪映 version and the declared capability matrix
(``code_status``) against ``references/version.json`` and an optional saved
baseline report. It never starts 剪映, never accesses the internet, and never
writes unless ``--save`` is given. Runtime state (bridge health, cached
resources, ASR deps) is reported separately and is not treated as version
drift. The capability probe hashes the install and checks the local loopback
bridge, so a run takes a few seconds.

    python scripts/upgrade_check.py [--baseline FILE] [--save FILE [--force]]

Exit codes: 0 the check passed (in-window; with --baseline, no drift);
10 attention (outside window / not aligned / drift / probe failure);
2 the check or the baseline save could not complete.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from jylib import env as env_mod  # noqa: E402
from jylib import media as media_mod  # noqa: E402
from jylib.errors import SkillError  # noqa: E402
import capability_probe as cap_mod  # noqa: E402

SCHEMA = "jianying-upgrade-baseline/v1"
VERSION_PATH = ROOT.parent / "references" / "version.json"
CHECKLIST_BASE = (
    "跑维护自检：check_skill、check_docs、test_skill、probe_gotchas、"
    "capability_probe、run_examples")


def _emit(data=None, error=None):
    payload = {
        "schema": "jianying-skill/v1",
        "command": "upgrade_check",
        "ok": error is None,
        "data": data,
        "error": error,
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if error is None else 2


def read_version_baseline():
    try:
        data = json.loads(VERSION_PATH.read_text("utf-8"))
    except FileNotFoundError as exc:
        raise SkillError("找不到 references/version.json", code="FILE_NOT_FOUND",
                         details={"path": str(VERSION_PATH)}) from exc
    except json.JSONDecodeError as exc:
        raise SkillError("references/version.json 不是合法 JSON",
                         code="JSON_INVALID",
                         details={"path": str(VERSION_PATH), "reason": str(exc)}) from exc
    if not isinstance(data, dict) or not isinstance(data.get("supported"), dict):
        raise SkillError("references/version.json 缺少 supported 窗口",
                         code="VALIDATION",
                         details={"path": str(VERSION_PATH)})
    return data


def collect_install():
    try:
        install = env_mod.find_install()
    except SkillError:
        return None
    return {"dir": str(install.get("dir") or ""),
            "version": str(install.get("version") or "")}


def collect_capabilities():
    try:
        data = cap_mod.probe()
    except Exception as exc:  # noqa: BLE001
        return {}, {}, [f"{type(exc).__name__}: {exc}"]
    capabilities = {}
    runtime = {}
    for item in data.get("capabilities") or []:
        if not isinstance(item, dict) or not item.get("id"):
            continue
        capability_id = str(item["id"])
        capabilities[capability_id] = (
            item.get("code_status") or item.get("status"))
        runtime[capability_id] = item.get("status")
    return capabilities, runtime, []


def _load_json(path):
    target = media_mod.local_path(path, field="基线文件")
    try:
        return json.loads(target.read_text("utf-8"))
    except FileNotFoundError as exc:
        raise SkillError("找不到基线文件", code="FILE_NOT_FOUND",
                         details={"path": str(target)}) from exc
    except json.JSONDecodeError as exc:
        raise SkillError("基线文件不是合法 JSON", code="JSON_INVALID",
                         details={"path": str(target), "reason": str(exc)}) from exc
    except OSError as exc:
        raise SkillError("基线文件读不了", code="VALIDATION",
                         details={"path": str(target), "reason": str(exc)}) from exc


def load_baseline(path):
    data = _load_json(path)
    if not isinstance(data, dict) or data.get("schema") != SCHEMA:
        raise SkillError("不是本技能保存的升级基线",
                         code="VALIDATION",
                         details={"path": str(path), "schema": SCHEMA})
    capabilities = data.get("capabilities")
    if not isinstance(capabilities, dict):
        raise SkillError("基线文件缺少 capabilities",
                         code="VALIDATION", details={"path": str(path)})
    if not all(isinstance(key, str) and (value is None or isinstance(value, str))
               for key, value in capabilities.items()):
        raise SkillError("基线 capabilities 必须是字符串状态",
                         code="VALIDATION", details={"path": str(path)})
    install = data.get("install")
    if install is not None and not isinstance(install, dict):
        raise SkillError("基线 install 必须是对象",
                         code="VALIDATION", details={"path": str(path)})
    return data


def _capability_drift(baseline, current):
    base = (baseline or {}).get("capabilities") or {}
    changes = []
    for capability_id in sorted(set(base) | set(current)):
        before = base.get(capability_id)
        after = current.get(capability_id)
        if before != after:
            changes.append({"id": capability_id,
                            "baseline": before, "current": after})
    return changes


def build_report(version_data, install, policy, capabilities,
                 baseline=None, capability_errors=None,
                 runtime_capabilities=None):
    capability_errors = list(capability_errors or [])
    policy_status = str((policy or {}).get("status") or "unknown")
    drift = {
        "install": None,
        "capabilities": (_capability_drift(baseline, capabilities)
                         if baseline is not None and not capability_errors
                         else []),
    }
    reasons = []
    if policy_status != "verified":
        reasons.append(f"docs.status={policy_status}: {policy.get('note') or '版本未与基线对齐'}")
    if capability_errors:
        reasons.append("能力探测失败：" + "；".join(capability_errors[:2]))
    elif not capabilities:
        reasons.append("能力矩阵为空，无法判断升级影响")
    if baseline is not None and not capability_errors:
        before_skill = str(baseline.get("skill_version") or "")
        current_skill = str(version_data.get("skill_version") or "")
        if before_skill and current_skill and before_skill != current_skill:
            reasons.append(
                f"基线来自技能 {before_skill}，当前 {current_skill}；建议重新留基线")
    if baseline is not None and not capability_errors:
        before_version = str(((baseline.get("install") or {}).get("version")) or "")
        after_version = str((install or {}).get("version") or "")
        if before_version and before_version != after_version:
            drift["install"] = {"baseline": before_version,
                                "current": after_version}
            reasons.append(f"安装版本从 {before_version} 变为 {after_version}")
    if drift["capabilities"]:
        reasons.append(f"{len(drift['capabilities'])} 项能力状态相对基线变化")

    checklist = []
    if policy_status != "verified":
        checklist.extend([
            "在真实剪映上用临时草稿跑 build → render → verify；未验证前不要改 supported 窗口",
            "把行为差异冻结到 references/history/<旧到达版本>.md（如 11.8.md），数量受 history_max 限制",
            "复验后更新 references/version.json 的 app_baseline/behavior_tested/build_tested/"
            "supported，并同步 limits.md、SKILL.md version 与 changelog",
        ])
    if drift["capabilities"]:
        checklist.append(
            "逐项核对漂移能力：真实导出验收后再改 limits.md / capabilities.md 的状态")
    if capability_errors:
        checklist.append("先修 probe/环境错误，再判断升级影响")
    checklist.append(CHECKLIST_BASE)
    if not reasons:
        if baseline is None:
            checklist = ["版本窗口内；未提供 --baseline，未做能力漂移比对；"
                         "需要留档时用 --save"]
        else:
            checklist = ["与保存的基线一致；如无变更，继续使用该基线"]

    return {
        "status": "ok" if not reasons else "attention",
        "exit_code": 0 if not reasons else 10,
        "baseline_compared": baseline is not None,
        "reasons": reasons,
        "drift": drift,
        "checklist": checklist,
        "baseline": {
            "app_baseline": version_data.get("app_baseline"),
            "behavior_tested": version_data.get("behavior_tested"),
            "build_tested": version_data.get("build_tested"),
            "supported": version_data.get("supported"),
            "skill_version": version_data.get("skill_version"),
        },
        "install": install,
        "policy": {key: (policy or {}).get(key) for key in
                   ("status", "note", "install_version", "install_build",
                    "in_range", "behavior_match", "build_match")},
        "capabilities": capabilities,
        "runtime_capabilities": runtime_capabilities or {},
        "capability_errors": capability_errors,
        "baseline_file": baseline,
    }


def save_report(path, report, *, force=False):
    target = media_mod.ensure_output_path(path, force=force, label="升级基线文件")
    if target.exists():
        if not target.is_file():
            raise SkillError("升级基线目标不是文件", code="VALIDATION",
                             details={"path": str(target)})
        try:
            existing = json.loads(target.read_text("utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise SkillError("只能覆盖本技能保存的基线文件", code="VALIDATION",
                             details={"path": str(target), "reason": str(exc)}) from exc
        if not isinstance(existing, dict) or existing.get("schema") != SCHEMA:
            raise SkillError("只能覆盖本技能保存的基线文件", code="VALIDATION",
                             details={"path": str(target)})
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema": SCHEMA,
        "created": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "skill_version": (report.get("baseline") or {}).get("skill_version"),
        "install": {"version": (report.get("install") or {}).get("version")},
        "policy": report.get("policy"),
        "capabilities": report.get("capabilities") or {},
    }
    handle, temp_name = tempfile.mkstemp(prefix=".jy-upgrade-", suffix=".tmp",
                                         dir=str(target.parent))
    temp = Path(temp_name)
    try:
        with os.fdopen(handle, "w", encoding="utf-8") as sink:
            json.dump(payload, sink, ensure_ascii=False, indent=2)
        os.replace(temp, target)
    except OSError as exc:
        try:
            temp.unlink(missing_ok=True)
        except OSError:
            pass
        raise SkillError("升级基线写入失败", code="OUTPUT_WRITE_FAILED",
                         details={"path": str(target), "reason": str(exc)}) from exc
    return str(target)


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="upgrade_check",
        description="只读升级体检：安装版本 vs 基线、能力矩阵漂移、迁移清单")
    parser.add_argument("--baseline", help="对比此前 --save 保存的基线文件")
    parser.add_argument("--save", help="把本次结果保存为基线文件")
    parser.add_argument("--force", action="store_true", help="允许覆盖 --save 目标")
    args = parser.parse_args(argv)

    try:
        version_data = read_version_baseline()
        install = collect_install()
        policy = env_mod.version_policy(
            (install or {}).get("version") or None)
        capabilities, runtime_capabilities, capability_errors = collect_capabilities()
        baseline = load_baseline(args.baseline) if args.baseline else None
    except SkillError as exc:
        return _emit(error=exc.to_dict())
    except Exception as exc:  # noqa: BLE001
        return _emit(error=SkillError(
            f"升级体检失败：{type(exc).__name__}: {exc}",
            code="INTERNAL", details={"type": type(exc).__name__}).to_dict())

    report = build_report(version_data, install, policy, capabilities,
                          baseline=baseline, capability_errors=capability_errors,
                          runtime_capabilities=runtime_capabilities)
    if args.save:
        try:
            if report.get("capability_errors") or not report.get("capabilities"):
                raise SkillError(
                    "能力探测失败或矩阵为空，拒绝保存升级基线",
                    code="VALIDATION",
                    details={"capability_errors":
                             report.get("capability_errors") or []})
            report["saved_to"] = save_report(args.save, report, force=args.force)
        except SkillError as exc:
            return _emit(report, error=exc.to_dict())
    _emit(report)
    return report["exit_code"]


if __name__ == "__main__":
    raise SystemExit(main())
