#!/usr/bin/env python3
"""Locate a usable photocraft-cli binary (agent: execute).

  python <skill-dir>/scripts/find_cli.py                print the path
  python <skill-dir>/scripts/find_cli.py --check        also run --version and a tiny registry query
  python <skill-dir>/scripts/find_cli.py --json         path, version, source and every place searched
  python <skill-dir>/scripts/find_cli.py --cli PATH     pin a binary (no fallback to others)
  python <skill-dir>/scripts/find_cli.py --repo DIR     also search a PhotoCraft checkout's target/

Search order: --cli, PHOTOCRAFT_CLI, --repo/PHOTOCRAFT_REPO (target/release|debug,
also per target triple), PATH, next to `photocraft` on PATH, then on Windows the
registry (HKLM/HKCU Software\\PhotoCraft InstallDir, App Paths photocraft.exe) and
Program Files; on macOS /usr/local/bin, /opt/homebrew/bin, ~/.local/bin, ~/bin (the
CLI ships as a separate zip, never inside PhotoCraft.app); on Linux /usr/bin (deb/rpm),
/usr/local/bin, ~/.local/bin, ~/bin. --cli and PHOTOCRAFT_CLI are pins: when the pinned
file does not run, the script fails instead of using another binary.

Exit codes: 0 found (and --check passed), 1 not found or check failed, 2 usage error.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import pclib  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    pclib.setup_stdio()
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--cli", help="explicit photocraft-cli path (a pin: no fallback)")
    ap.add_argument("--repo", help="PhotoCraft checkout whose target/ holds a build")
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    ap.add_argument("--check", action="store_true", help="run --version and `commands --json --filter file.new`")
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
    report["searched"] = [{"path": str(c.path), "source": c.source, "exists": c.path.is_file()} for c in searched]

    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
    else:
        print(path)
        if args.check:
            state = "ok" if report.get("registry_ok") else "FAILED: " + report.get("registry_error", "")
            print(f"version: {report.get('version')}; registry: {state}; found via {source}", file=sys.stderr)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
