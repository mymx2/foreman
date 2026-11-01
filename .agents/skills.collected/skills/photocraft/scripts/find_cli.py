#!/usr/bin/env python3
"""Locate a usable photocraft-cli binary (agent: execute).

  python <skill-dir>/scripts/find_cli.py                print the path
  python <skill-dir>/scripts/find_cli.py --check        also run --version, a tiny registry query,
                                                        and report the documented version range
  python <skill-dir>/scripts/find_cli.py --json         path, version, source and every place searched
  python <skill-dir>/scripts/find_cli.py --cli PATH     pin a binary (no fallback to others)
  python <skill-dir>/scripts/find_cli.py --repo DIR     also search a PhotoCraft checkout's target/

Search order: --cli, PHOTOCRAFT_CLI, PC_CLI (legacy name some repos still set),
--repo/PHOTOCRAFT_REPO (target/release|debug, also per target triple), PATH, next to
`photocraft` on PATH, then on Windows the registry (HKLM/HKCU Software\\PhotoCraft
InstallDir, App Paths photocraft.exe) and Program Files; on macOS /usr/local/bin,
/opt/homebrew/bin, ~/.local/bin, ~/bin (the CLI ships as a separate zip, never inside
PhotoCraft.app); on Linux /usr/bin (deb/rpm), /usr/local/bin, ~/.local/bin, ~/bin.
--cli and PHOTOCRAFT_CLI are pins: when the pinned file does not run, the script fails
instead of using another binary. PC_CLI is only a candidate: a stale value is skipped
and the search continues.

Exit codes: 0 found (and --check passed), 1 not found or check failed, 2 usage error,
3 --check found a usable CLI but the installed version is outside version.json's supported range,
4 --check could not read or validate references/version.json.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import pclib  # noqa: E402


def _read_version_file() -> dict | None:
    path = Path(__file__).resolve().parent.parent / "references" / "version.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def _version_tuple(value: str | None) -> tuple[int, int, int] | None:
    if not value:
        return None
    match = re.search(r"(\d+)\.(\d+)(?:\.(\d+))?", value)
    if not match:
        return None
    return tuple(int(part or 0) for part in match.groups())


def _docs_report(installed: str | None) -> tuple[dict | None, str | None, str | None]:
    info = _read_version_file()
    if info is None:
        return None, ("references/version.json is missing or unreadable; downstream read references/update.md, "
                      "maintainers read references/maintenance.md"), "config"
    supported = info.get("supported")
    if not isinstance(supported, dict):
        return info, ("references/version.json: supported must be an object with min/max; downstream read "
                      "references/update.md"), "config"
    low = _version_tuple(str(supported.get("min")))
    high = _version_tuple(str(supported.get("max")))
    have = _version_tuple(installed)
    if not (low and high and have):
        return info, ("cannot compare the installed version with references/version.json; downstream read "
                      "references/update.md"), "config"
    if low > high:
        return info, "references/version.json: supported.min is greater than supported.max", "config"
    if have[:2] < low[:2] or have[:2] > high[:2]:
        return info, (f"installed {installed} is outside the documented range "
                      f"{supported.get('min')}-{supported.get('max')}; CLI newer than docs is expected, "
                      f"mark unverified and keep using the local skill; downstream update cadence in "
                      f"references/update.md, maintainers in references/maintenance.md"), "range"
    return info, None, None


def _docs_exit(kind: str | None) -> int:
    return 4 if kind == "config" else 3 if kind == "range" else 0


def main(argv: list[str] | None = None) -> int:
    pclib.setup_stdio()
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--cli", help="explicit photocraft-cli path (a pin: no fallback)")
    ap.add_argument("--repo", help="PhotoCraft checkout whose target/ holds a build")
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    ap.add_argument("--check", action="store_true",
                    help="run --version, `commands --json --filter file.new`, and report the documented version range")
    args = ap.parse_args(argv)

    searched = pclib.cli_candidates(args.cli, repo=args.repo)
    report: dict = {"found": False}
    try:
        path = pclib.find_cli(args.cli, repo=args.repo)
    except pclib.CliNotFound as exc:
        report["error"] = str(exc).splitlines()[0]
        report["searched"] = [{"path": str(c.path), "source": c.source, "exists": c.path.is_file()}
                              for c in (exc.searched or searched)]
        if args.json:
            print(json.dumps(report, indent=2, ensure_ascii=False))
        else:
            print(str(exc), file=sys.stderr)
        return 1

    source = next((c.source for c in searched if c.path.is_file() and c.path.resolve() == path), "explicit")
    report.update(found=True, path=str(path), source=source)
    ok = True
    docs_kind = None
    try:
        report["version"] = pclib.cli_version(path)
    except pclib.PcError as exc:
        report["version"] = None
        report["version_error"] = str(exc)
        ok = False
    if args.check:
        try:
            rows = json.loads(pclib.run_cli(["commands", "--json", "--filter", "file.new"], cli=path, timeout=60).stdout)
            report["registry_ok"] = any(row.get("id") == "file.new" for row in rows)
            if not report["registry_ok"]:
                report["registry_error"] = "`commands --json --filter file.new` did not list file.new"
        except (pclib.PcError, json.JSONDecodeError) as exc:
            report["registry_ok"] = False
            report["registry_error"] = str(exc)[-2000:]
        ok = ok and report["registry_ok"]
        if report.get("version") is None:
            report["docs_in_range"] = False
            report["docs_unknown"] = "CLI --version failed; cannot compare with version.json"
        else:
            docs, docs_hint, docs_kind = _docs_report(report.get("version"))
            if docs is not None:
                report["docs"] = {key: docs.get(key) for key in ("params_baseline", "behavior_tested", "supported")}
            report["docs_in_range"] = docs_kind is None
            if docs_kind == "config":
                report["docs_config_error"] = docs_hint
            elif docs_hint:
                report["docs_hint"] = docs_hint
    report["searched"] = [{"path": str(c.path), "source": c.source, "exists": c.path.is_file()} for c in searched]

    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
    else:
        print(path)
        if args.check:
            state = "ok" if report.get("registry_ok") else "FAILED: " + report.get("registry_error", "")
            docs = report.get("docs") or {}
            supported = docs.get("supported")
            if not docs:
                docs_text = "unknown"
            elif isinstance(supported, dict):
                docs_text = (f"params {docs.get('params_baseline')}, behavior {docs.get('behavior_tested')}, "
                             f"supported {supported.get('min')}-{supported.get('max')}")
            else:
                docs_text = (f"params {docs.get('params_baseline')}, behavior {docs.get('behavior_tested')}, "
                             f"supported invalid")
            print(f"version: {report.get('version')}; registry: {state}; docs: {docs_text}; "
                  f"docs_in_range: {report.get('docs_in_range')}; found via {source}", file=sys.stderr)
            if report.get("docs_config_error"):
                print(f"docs config error: {report['docs_config_error']}", file=sys.stderr)
            elif report.get("docs_hint"):
                print(f"docs hint: {report['docs_hint']}", file=sys.stderr)
    if not ok:
        return 1
    if args.check:
        return _docs_exit(docs_kind)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
