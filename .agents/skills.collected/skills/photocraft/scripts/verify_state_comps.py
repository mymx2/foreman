#!/usr/bin/env python3
"""校验 PSD 状态族与图层复合。

输入是 JSON 快照，不直接调用 PhotoCraft：
{
  "states": ["default", "hover", ...],        // 可选，默认 v1 词表
  "layerComps": ["default", "hover"],         // layerComp.list 的复合名
  "applyResults": {"default": {"missingLayers": []}},  // layerComp.apply 的结果
  "exports": [{"comp": "default", "path": "...", "sha256": "..."}]  // 可选
}

退出码：0 通过，1 有问题，2 输入错误。
"""

import argparse
import hashlib
import json
import os
import sys
import tempfile

STATES_V1 = [
    "default", "hover", "focus", "pressed", "selected",
    "disabled", "loading", "empty", "error", "success",
]


def _missing_layers(result):
    if not isinstance(result, dict):
        return None
    if "missingLayers" in result:
        return result.get("missingLayers")
    nested = result.get("result")
    if isinstance(nested, dict):
        return nested.get("missingLayers")
    return None


def _sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _is_inside(root, path):
    root = os.path.normcase(os.path.realpath(root))
    path = os.path.normcase(os.path.realpath(path))
    try:
        return os.path.commonpath([root, path]) == root
    except ValueError:
        return False


def verify(payload, options=None):
    options = options or {}
    export_root = options.get("export_root")
    max_export_bytes = options.get("max_export_bytes")
    if max_export_bytes is None:
        max_export_bytes = 256 * 1024 * 1024
    issues = []
    raw_states = payload.get("states")
    if raw_states is None:
        states = STATES_V1
    elif isinstance(raw_states, list) and raw_states:
        states = raw_states
    else:
        issues.append({"code": "STATES_INVALID", "severity": "error", "message": "states must be a non-empty array"})
        states = STATES_V1
    comps = payload.get("layerComps")
    apply_results = payload.get("applyResults") or {}
    has_exports = "exports" in payload
    exports = payload.get("exports") or []

    def add(code, severity, message, **extra):
        issues.append({"code": code, "severity": severity, "message": message, **extra})
    if not isinstance(comps, list):
        add("COMPS_MISSING", "error", "layerComps must be an array from layerComp.list")
        comps = []

    seen = {}
    for name in comps:
        key = str(name)
        seen[key] = seen.get(key, 0) + 1
    expected = set(states)
    actual = set(seen)
    for name in sorted(expected - actual):
        add("COMP_MISSING", "error", f"missing layer comp: {name}", comp=name)
    for name in sorted(actual - expected):
        add("COMP_EXTRA", "error", f"unexpected layer comp: {name}", comp=name)
    for name, count in sorted(seen.items()):
        if count > 1:
            add("COMP_DUPLICATE", "error", f"duplicate layer comp: {name} x{count}", comp=name)

    if seen.get("default", 0) != 1:
        add("DEFAULT_INVALID", "error", "exactly one default comp is required")

    if [str(c) for c in comps] != [str(s) for s in states]:
        add("COMP_ORDER", "warning", "layer comp order differs from the state vocabulary", expected=states, actual=comps)
    if payload.get("statesSource") == "comps":
        add("STATES_DERIVED_FROM_COMPS", "warning",
            "states came from the PSD comps, so coverage is not verified; pass --states for the full vocabulary")

    if not isinstance(apply_results, dict) or not apply_results:
        add("APPLY_MISSING", "error", "applyResults is empty; run layerComp.apply for every state")
    else:
        for name in states:
            result = apply_results.get(name)
            if result is None:
                add("APPLY_MISSING", "error", f"no apply result for state: {name}", comp=name)
                continue
            missing = _missing_layers(result)
            if missing is None:
                add("APPLY_INVALID", "error", f"apply result has no missingLayers for state: {name}", comp=name)
            elif missing:
                add("APPLY_BROKEN", "error", f"missingLayers is not empty for state: {name}", comp=name, missingLayers=missing)

    if not has_exports:
        add("EXPORTS_NOT_CHECKED", "warning", "exports were not provided; export completeness was not checked")
    else:
        by_comp = {}
        unmatched = []
        for item in exports:
            if isinstance(item, dict) and item.get("comp"):
                by_comp.setdefault(str(item["comp"]), item)
            else:
                unmatched.append(item)
        if unmatched:
            add("EXPORT_UNMATCHED", "error", "exports must be objects with a comp name", exports=unmatched)
        for name in sorted(set(by_comp) - expected):
            add("EXPORT_EXTRA", "warning", f"export has an unknown comp: {name}", comp=name)
        for name in states:
            item = by_comp.get(name)
            if item is None:
                add("EXPORT_MISSING", "error", f"no export for state: {name}", comp=name)
                continue
            path = item.get("path")
            if not path or not os.path.isfile(path):
                add("EXPORT_FILE", "error", f"export file missing for state: {name}", comp=name, path=path)
                continue
            if export_root and not _is_inside(export_root, path):
                add("EXPORT_OUTSIDE_ROOT", "error", f"export file is outside the export root: {path}", comp=name, path=path)
                continue
            if os.path.getsize(path) > max_export_bytes:
                add("EXPORT_TOO_LARGE", "error", f"export file exceeds {max_export_bytes} bytes: {path}", comp=name, path=path)
                continue
            if os.path.getsize(path) <= 0:
                add("EXPORT_EMPTY", "error", f"export file is empty for state: {name}", comp=name, path=path)
                continue
            expected_hash = item.get("sha256")
            if expected_hash:
                actual_hash = _sha256(path)
                if actual_hash != expected_hash:
                    add("EXPORT_CHANGED", "error", f"export hash mismatch for state: {name}", comp=name, path=path)

    return {
        "ok": not any(i["severity"] == "error" for i in issues),
        "stats": {
            "states": len(states),
            "comps": len(comps),
            "exports": len(exports),
            "exportChecked": has_exports,
            "errors": sum(1 for i in issues if i["severity"] == "error"),
            "warnings": sum(1 for i in issues if i["severity"] == "warning"),
        },
        "issues": issues,
    }


def selftest():
    good = {
        "layerComps": list(STATES_V1),
        "applyResults": {s: {"missingLayers": 0} for s in STATES_V1},
    }
    bad = {
        "layerComps": ["default", "hover"],
        "applyResults": {"default": {"missingLayers": 0}, "hover": {"missingLayers": 1}},
    }
    failed = []

    result = verify(good)
    if not result["ok"] or any(i["severity"] == "error" for i in result["issues"]):
        failed.append("good")
    print(f"[{'PASS' if 'good' not in failed else 'FAIL'}] good: ok={result['ok']} codes={sorted({i['code'] for i in result['issues']})}")

    result = verify(bad)
    codes = {i["code"] for i in result["issues"]}
    required = {"COMP_MISSING", "APPLY_MISSING", "APPLY_BROKEN"}
    if result["ok"] or not required.issubset(codes):
        failed.append("bad")
    print(f"[{'PASS' if 'bad' not in failed else 'FAIL'}] bad: ok={result['ok']} codes={sorted(codes)}")

    invalid_states = verify({"states": [], "layerComps": ["default"], "applyResults": {}})
    if "STATES_INVALID" not in {i["code"] for i in invalid_states["issues"]}:
        failed.append("states")
    print(f"[{'PASS' if 'states' not in failed else 'FAIL'}] states: codes={sorted({i['code'] for i in invalid_states['issues']})}")

    unmatched = verify({
        "states": ["default"],
        "layerComps": ["default"],
        "applyResults": {"default": {"missingLayers": 0}},
        "exports": [{"path": "x"}],
    })
    if "EXPORT_UNMATCHED" not in {i["code"] for i in unmatched["issues"]}:
        failed.append("exports")
    print(f"[{'PASS' if 'exports' not in failed else 'FAIL'}] exports: codes={sorted({i['code'] for i in unmatched['issues']})}")

    with tempfile.TemporaryDirectory() as root, tempfile.TemporaryDirectory() as other:
        inside = os.path.join(root, "state.png")
        outside = os.path.join(other, "state.png")
        for path, data in ((inside, b"xx"), (outside, b"xx")):
            with open(path, "wb") as f:
                f.write(data)
        base = {
            "states": ["default"],
            "layerComps": ["default"],
            "applyResults": {"default": {"missingLayers": 0}},
        }
        escaped = verify({**base, "exports": [{"comp": "default", "path": outside}]}, {"export_root": root})
        too_big = verify({**base, "exports": [{"comp": "default", "path": inside}]},
                         {"export_root": root, "max_export_bytes": 1})
        empty = os.path.join(root, "empty.png")
        with open(empty, "wb"):
            pass
        empty_result = verify({**base, "exports": [{"comp": "default", "path": empty}]}, {"export_root": root})
        changed = verify({**base, "exports": [{"comp": "default", "path": inside, "sha256": "0" * 64}]},
                         {"export_root": root})
        missing = verify({**base, "exports": []}, {"export_root": root})
        checks = {
            "export_root": escaped,
            "export_size": too_big,
            "export_empty": empty_result,
            "export_changed": changed,
            "export_missing": missing,
        }
        expected_codes = {
            "export_root": "EXPORT_OUTSIDE_ROOT",
            "export_size": "EXPORT_TOO_LARGE",
            "export_empty": "EXPORT_EMPTY",
            "export_changed": "EXPORT_CHANGED",
            "export_missing": "EXPORT_MISSING",
        }
        for name, result in checks.items():
            if expected_codes[name] not in {i["code"] for i in result["issues"]}:
                failed.append(name)
            print(f"[{'PASS' if name not in failed else 'FAIL'}] {name}")
    return 1 if failed else 0


def main():
    parser = argparse.ArgumentParser(description="Verify PSD layer comps against the state vocabulary.")
    parser.add_argument("--input", help="JSON snapshot path")
    parser.add_argument("--export-root", help="directory that exported state files must stay inside")
    parser.add_argument("--max-export-bytes", type=int, default=256 * 1024 * 1024,
                        help="reject export files larger than this (default 256 MiB)")
    parser.add_argument("--json", action="store_true", help="print JSON result")
    parser.add_argument("--selftest", action="store_true")
    args = parser.parse_args()

    if args.selftest:
        sys.exit(selftest())
    if not args.input:
        parser.error("--input is required (or use --selftest)")

    try:
        with open(args.input, "r", encoding="utf-8") as f:
            payload = json.load(f)
    except Exception as e:
        print(f"cannot read input: {e}", file=sys.stderr)
        sys.exit(2)
    if not isinstance(payload, dict):
        print("input must be a JSON object", file=sys.stderr)
        sys.exit(2)

    export_root = args.export_root or os.path.dirname(os.path.abspath(args.input))
    result = verify(payload, {"export_root": export_root, "max_export_bytes": args.max_export_bytes})
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        for issue in result["issues"]:
            print(f"[{issue['severity']}] {issue['code']}: {issue['message']}")
        s = result["stats"]
        print(f"states={s['states']} comps={s['comps']} exports={s['exports']} ok={result['ok']}")
    sys.exit(0 if result["ok"] else 1)


if __name__ == "__main__":
    main()
