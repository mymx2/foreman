#!/usr/bin/env python3
"""跑全部案例（或按名字过滤），汇总 PASS / FAIL / SKIP。维护技能时用。

    python <skill-dir>/scripts/run_examples.py                 # 全部（案例 31 默认 SKIP，设 PCX_DESKTOP=1 才运行）
    python <skill-dir>/scripts/run_examples.py 03 batch        # 名字里含 03 或 batch 的
    PCX_WORK=/tmp/pc python <skill-dir>/scripts/run_examples.py

依赖：Python 3.10+、已安装的 PhotoCraft（PHOTOCRAFT_CLI 可覆盖）。
退出码：0 = 没有 FAIL；1 = 有 FAIL；2 = 用法或环境问题；77 = 过滤器没匹配到任何案例。
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
from pathlib import Path

EX_DIR = Path(__file__).resolve().parent.parent / "examples"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("filters", nargs="*", help="只跑名字里含这些词的案例")
    ap.add_argument("--timeout", type=int, default=1800, help="每个案例的秒数上限（默认 1800）")
    args = ap.parse_args()

    cases = sorted(EX_DIR.glob("[0-9][0-9]-*.py"))
    if args.filters:
        cases = [p for p in cases if any(f in p.name for f in args.filters)]
    if not cases:
        print(f"no example matches: {' '.join(args.filters) or '<all>'}", file=sys.stderr)
        return 77

    env = os.environ.copy()
    env.setdefault("PYTHONUTF8", "1")
    passed = failed = skipped = 0
    names: list[str] = []
    start = time.time()
    for case in cases:
        name = case.stem
        t0 = time.time()
        try:
            proc = subprocess.run([sys.executable, str(case)], capture_output=True, text=True,
                                  encoding="utf-8", errors="replace", env=env, timeout=args.timeout)
            returncode, stdout, stderr = proc.returncode, proc.stdout, proc.stderr
        except subprocess.TimeoutExpired as exc:
            returncode = 124
            stdout = exc.stdout if isinstance(exc.stdout, str) else ""
            stderr = f"timed out after {args.timeout}s"
        dt = time.time() - t0
        if returncode == 0:
            passed += 1
            print(f"{name:<34} PASS  {dt:4.0f}s", flush=True)
        elif returncode == 77:
            skipped += 1
            line = next((l for l in stdout.splitlines() if l.startswith("skip")), "")
            print(f"{name:<34} SKIP  {dt:4.0f}s  {line}", flush=True)
        else:
            failed += 1
            names.append(name)
            print(f"{name:<34} FAIL  {dt:4.0f}s", flush=True)
            tail = (stdout + stderr).strip().splitlines()[-12:]
            print("\n".join("    " + l for l in tail), flush=True)
    print(f"\n{passed} passed, {failed} failed, {skipped} skipped in {time.time() - start:.0f}s")
    if failed:
        print("failed: " + " ".join(names), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
