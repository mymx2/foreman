#!/usr/bin/env python3
"""Look up PhotoCraft command ids and their parameter docs in the installed registry (agent: execute).

  python <skill-dir>/scripts/params.py curves levels            id, label or keywords contain any word
  python <skill-dir>/scripts/params.py --exact image.imageSize  these ids only (case-insensitive)
  python <skill-dir>/scripts/params.py --prefix filter.blur     id segments: filter.blur and filter.blur.*
  python <skill-dir>/scripts/params.py --prefix 'filter.blur*'  raw prefix (also filter.blurGallery.*)
  python <skill-dir>/scripts/params.py --json --exact file.new  matching registry rows as JSON

Output per command: `id  [menu > path]  label`, a status line (needs a document or not,
and why it is disabled when that is not just "no document open"), then the params
text. The params text is the registry's own notation, not JSON Schema: `a..b` is a
range, `=x` a default, `?` optional, `→ {…}` the result shape.

Word search matches the same fields as `photocraft-cli commands --filter <word>`
(id, label, keywords; same results, checked on 0.10.0) with one registry read.
Exit codes: 0 something matched, 1 nothing matched, 2 usage error or CLI not found.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import pclib  # noqa: E402


def _matches(row: dict, mode: str, terms: list[str]) -> bool:
    cid = row["id"].lower()
    if mode == "exact":
        return cid in terms
    if mode == "prefix":
        for term in terms:
            if term.endswith("*"):
                if cid.startswith(term[:-1]):
                    return True
            elif cid == term or cid.startswith(term.rstrip(".") + "."):
                return True
        return False
    hay = " ".join((row.get(k) or "") for k in ("id", "label", "keywords")).lower()
    return any(term in hay for term in terms)


def _status(row: dict) -> str:
    parts = ["needs a document" if row.get("needsDocument") else "no document needed"]
    reason = row.get("disabledReason")
    if row.get("enabled") is False and reason and reason != "no document open":
        parts.append(f"disabled in an empty session: {reason}")
    if row.get("shortcut"):
        parts.append(f"shortcut {row['shortcut']}")
    return "; ".join(parts)


def main(argv: list[str] | None = None) -> int:
    pclib.setup_stdio()
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    group = ap.add_mutually_exclusive_group()
    group.add_argument("--exact", action="store_true", help="terms are exact command ids")
    group.add_argument("--prefix", action="store_true", help="terms are id prefixes (segment-aware; trailing * = raw)")
    ap.add_argument("--json", action="store_true", help="print the matching registry rows as a JSON array")
    ap.add_argument("--cli", help="photocraft-cli path (default: find_cli order)")
    ap.add_argument("terms", nargs="+", help="words, ids or prefixes")
    args = ap.parse_args(argv)

    mode = "exact" if args.exact else "prefix" if args.prefix else "word"
    terms = [t.strip().lower() for t in args.terms if t.strip()]
    if not terms:
        ap.error("give at least one non-empty term")
    try:
        rows = pclib.registry(args.cli)
    except pclib.PcError as exc:
        print(f"params.py: {exc}", file=sys.stderr)
        return 2

    hits = [row for row in rows if _matches(row, mode, terms)]
    if args.json:
        print(json.dumps(hits, indent=2, ensure_ascii=False))
    else:
        for row in hits:
            menu = " > ".join(row.get("menu") or []) or "no menu"
            print(f"{row['id']}  [{menu}]  {row.get('label', '')}")
            print(f"    ({_status(row)})")
            print(f"    {row.get('params', '')}\n")
    print(f"{len(hits)} of {len(rows)} commands", file=sys.stderr)
    if not hits:
        hint = "try a word search or --prefix" if mode == "exact" else "try a shorter word or another synonym"
        print(f"no command matched {', '.join(args.terms)}; {hint}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
