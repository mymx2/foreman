#!/usr/bin/env python3
"""从 PSD 生成状态复合快照，供 verify_state_comps.py 校验。

调用 photocraft-cli：
  layerComp.list  -> 复合名
  layerComp.apply -> missingLayers
  file.export.layerCompsToFiles -> 每个复合的导出文件（可选）

只读：不带 --out 的 run 不改原文件；apply 只在进程内切换状态。
"""

import argparse
import hashlib
import json
import os
import subprocess
import sys
import tempfile


def find_cli(explicit):
    try:
        import pclib
        return str(pclib.find_cli(explicit=explicit or None))
    except Exception:
        return None


def run_cli(cli, args, timeout):
    proc = subprocess.run(
        [cli] + args,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or proc.stdout.strip() or f"exit {proc.returncode}")
    return proc.stdout


def parse_json_line(text):
    fallback = None
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict) and ("command" in value or "result" in value):
            return value
        fallback = value
    if fallback is not None:
        return fallback
    raise ValueError("no JSON object in CLI output")


def _result(payload):
    if isinstance(payload, dict) and isinstance(payload.get("result"), dict):
        return payload["result"]
    return payload if isinstance(payload, dict) else {}


def extract_comps(payload):
    result = _result(payload)
    comps = result.get("comps") or result.get("layerComps") or []
    names = []
    for item in comps:
        if isinstance(item, str):
            names.append(item)
        elif isinstance(item, dict) and item.get("name"):
            names.append(str(item["name"]))
    return names


def extract_missing(payload):
    result = _result(payload)
    value = result.get("missingLayers", result.get("missing_layers"))
    return value


def sha256(path):
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


def map_exports(files, comps, export_dir=None):
    exports = []
    fallback = len(files) == len(comps)
    for index, path in enumerate(files):
        if export_dir and not _is_inside(export_dir, path):
            raise ValueError(f"export file is outside --export-dir: {path}")
        stem = os.path.splitext(os.path.basename(path))[0]
        comp = next((name for name in comps if stem == name or stem.endswith("_" + name)), None)
        if comp is None and fallback and index < len(comps):
            comp = comps[index]
        item = {"path": path}
        if comp:
            item["comp"] = comp
        if os.path.isfile(path):
            item["sha256"] = sha256(path)
        exports.append(item)
    return exports


def build_snapshot(cli, psd, states=None, skip_apply=False, export_dir=None, timeout=120):
    stdout = run_cli(cli, ["run", psd, "--cmd", "layerComp.list", "--params", "{}"], timeout)
    comps = extract_comps(parse_json_line(stdout))
    if not comps:
        raise RuntimeError("no layer comps found in the PSD")

    apply_results = {}
    if not skip_apply:
        for name in comps:
            out = run_cli(
                cli,
                ["run", psd, "--cmd", "layerComp.apply", "--params", json.dumps({"comp": name})],
                timeout,
            )
            missing = extract_missing(parse_json_line(out))
            apply_results[name] = {"missingLayers": missing} if missing is not None else {"error": "missingLayers not found"}

    snapshot = {
        "layerComps": comps,
        "applyResults": apply_results,
        "states": states or comps,
        "statesSource": "explicit" if states else "comps",
    }
    if export_dir:
        os.makedirs(export_dir, exist_ok=True)
        out = run_cli(
            cli,
            ["run", psd, "--cmd", "file.export.layerCompsToFiles",
             "--params", json.dumps({"dir": export_dir, "prefix": ""})],
            timeout,
        )
        files = _result(parse_json_line(out)).get("files") or []
        snapshot["exports"] = map_exports(files, comps, export_dir)
        snapshot["exportDir"] = os.path.abspath(export_dir)
    return snapshot


def selftest():
    failures = []
    noisy = '{"elapsed":1.2}\n{"command":"layerComp.list","result":{"comps":[]}}'
    if parse_json_line(noisy).get("command") != "layerComp.list":
        failures.append("parse_json_line")
    try:
        run_cli(sys.executable, ["-c", "import sys; sys.exit(3)"], 10)
        failures.append("run_cli")
    except RuntimeError:
        pass
    payload = {"command": "layerComp.list", "result": {"comps": [{"name": "default"}, "hover"]}}
    if extract_comps(payload) != ["default", "hover"]:
        failures.append("extract_comps")
    if extract_missing({"command": "layerComp.apply", "result": {"missingLayers": 0}}) != 0:
        failures.append("extract_missing")
    with tempfile.TemporaryDirectory() as d:
        paths = []
        for name in ("layer_0000_hover.png", "layer_0001_hover-dark.png"):
            p = os.path.join(d, name)
            with open(p, "wb") as f:
                f.write(b"x")
            paths.append(p)
        exports = map_exports(paths, ["hover", "hover-dark"], d)
        if [e.get("comp") for e in exports] != ["hover", "hover-dark"] or not all(e.get("sha256") for e in exports):
            failures.append("map_exports")
    for name in failures:
        print(f"[FAIL] {name}")
    if not failures:
        print("[PASS] snapshot_state_comps")
    return 1 if failures else 0


def main():
    parser = argparse.ArgumentParser(description="Build a layer-comp state snapshot from a PSD.")
    parser.add_argument("--psd", help="PSD path")
    parser.add_argument("--out", help="output JSON path; omit to print")
    parser.add_argument("--cli", help="photocraft-cli path")
    parser.add_argument("--states", help="comma-separated expected states, e.g. default,hover")
    parser.add_argument("--skip-apply", action="store_true", help="only list comps, skip layerComp.apply")
    parser.add_argument("--export-dir", help="also export each comp and record file hashes")
    parser.add_argument("--timeout", type=int, default=120)
    parser.add_argument("--selftest", action="store_true")
    args = parser.parse_args()

    if args.selftest:
        sys.exit(selftest())
    if not args.psd:
        parser.error("--psd is required (or use --selftest)")

    cli = find_cli(args.cli)
    if not cli:
        print("photocraft-cli not found; pass --cli or set PHOTOCRAFT_CLI", file=sys.stderr)
        sys.exit(2)

    states = [s.strip() for s in args.states.split(",") if s.strip()] if args.states else None
    try:
        snapshot = build_snapshot(cli, args.psd, states, args.skip_apply, args.export_dir, args.timeout)
    except Exception as e:
        print(f"snapshot failed: {e}", file=sys.stderr)
        sys.exit(1)

    text = json.dumps(snapshot, ensure_ascii=False, indent=2)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(text)
        print(f"snapshot written: {args.out}")
    else:
        print(text)


if __name__ == "__main__":
    main()
