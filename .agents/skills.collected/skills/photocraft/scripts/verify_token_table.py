#!/usr/bin/env python3
"""校验描述文件里的设计令牌表与 inspect 实测值是否一致。

输入是 JSON 快照：
{
  "revision": "<document.inspect 的 revision>",
  "expected": [{"role": "text-primary", "value": "#18191C"}],
  "measured": {"revision": "<同一 revision>", "tokens": {"text-primary": "#18191C"}},
  "aliases": [{"alias": "body-text", "role": "text-primary"}]
}

退出码：0 通过，1 有问题，2 输入错误。
"""

import argparse
import json
import sys


def _normalize(value):
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        text = value.strip()
        if text.startswith("#"):
            return text.lower()
        try:
            return float(text)
        except ValueError:
            return text
    return value


def _values_equal(a, b):
    na, nb = _normalize(a), _normalize(b)
    if isinstance(na, float) and isinstance(nb, float):
        return abs(na - nb) < 1e-9
    return na == nb


def verify(payload):
    issues = []

    def add(code, severity, message, **extra):
        issues.append({"code": code, "severity": severity, "message": message, **extra})

    revision = payload.get("revision")
    expected = payload.get("expected")
    measured = payload.get("measured") or {}
    aliases = payload.get("aliases") or []

    if not revision:
        add("REVISION_MISSING", "error", "revision is required")
    if not isinstance(expected, list) or not expected:
        add("EXPECTED_MISSING", "error", "expected must be a non-empty array")
        expected = []
    if not isinstance(measured, dict):
        add("MEASURED_INVALID", "error", "measured must be an object")
        measured = {}

    measured_revision = measured.get("revision")
    if not measured_revision:
        add("MEASURED_REVISION_MISSING", "error", "measured.revision is required")
    elif revision and str(revision) != str(measured_revision):
        add("REVISION_MISMATCH", "error", "document revision changed; re-measure the token table",
            expected=revision, actual=measured_revision)

    tokens = measured.get("tokens")
    if not isinstance(tokens, dict):
        add("TOKENS_INVALID", "error", "measured.tokens must be an object")
        tokens = {}

    seen_roles = set()
    for item in expected:
        if not isinstance(item, dict) or not item.get("role"):
            add("TOKEN_INVALID", "error", "each expected token needs role and value")
            continue
        role = str(item["role"])
        if role in seen_roles:
            add("TOKEN_DUPLICATE", "error", f"duplicate role in expected: {role}", role=role)
            continue
        seen_roles.add(role)
        if role not in tokens:
            add("TOKEN_MISSING", "error", f"role is missing from measured tokens: {role}", role=role)
            continue
        if not _values_equal(item.get("value"), tokens[role]):
            add("TOKEN_MISMATCH", "error", f"value mismatch for role: {role}", role=role,
                expected=item.get("value"), actual=tokens[role])

    for role in sorted(set(tokens) - seen_roles):
        add("TOKEN_EXTRA", "warning", f"measured token is not documented: {role}", role=role)

    for item in aliases:
        if not isinstance(item, dict) or not item.get("alias") or not item.get("role"):
            add("ALIAS_INVALID", "warning", "alias entries need alias and role")
            continue
        if str(item["role"]) not in seen_roles:
            add("ALIAS_TARGET", "warning", f"alias target is not documented: {item['alias']} -> {item['role']}",
                alias=item["alias"], role=item["role"])

    return {
        "ok": not any(i["severity"] == "error" for i in issues),
        "stats": {
            "expected": len(seen_roles),
            "measured": len(tokens),
            "errors": sum(1 for i in issues if i["severity"] == "error"),
            "warnings": sum(1 for i in issues if i["severity"] == "warning"),
        },
        "issues": issues,
    }


def selftest():
    good = {
        "revision": "r1",
        "expected": [{"role": "text-primary", "value": "#18191C"}, {"role": "spacing-md", "value": 16}],
        "measured": {"revision": "r1", "tokens": {"text-primary": "#18191c", "spacing-md": "16"}},
        "aliases": [{"alias": "body-text", "role": "text-primary"}],
    }
    bad = {
        "revision": "r1",
        "expected": [{"role": "text-primary", "value": "#18191C"}],
        "measured": {"revision": "r2", "tokens": {"text-primary": "#000000"}},
    }
    failed = []
    result = verify(good)
    if not result["ok"] or result["issues"]:
        failed.append("good")
    print(f"[{'PASS' if 'good' not in failed else 'FAIL'}] good: ok={result['ok']} issues={len(result['issues'])}")

    result = verify(bad)
    codes = {i["code"] for i in result["issues"]}
    if result["ok"] or not {"REVISION_MISMATCH", "TOKEN_MISMATCH"}.issubset(codes):
        failed.append("bad")
    print(f"[{'PASS' if 'bad' not in failed else 'FAIL'}] bad: ok={result['ok']} codes={sorted(codes)}")
    return 1 if failed else 0


def main():
    parser = argparse.ArgumentParser(description="Verify a design token table against an inspect snapshot.")
    parser.add_argument("--input", help="JSON snapshot path")
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

    result = verify(payload)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        for issue in result["issues"]:
            print(f"[{issue['severity']}] {issue['code']}: {issue['message']}")
        s = result["stats"]
        print(f"expected={s['expected']} measured={s['measured']} ok={result['ok']}")
    sys.exit(0 if result["ok"] else 1)


if __name__ == "__main__":
    main()
