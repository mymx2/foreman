#!/usr/bin/env python3
"""案例共用小工具：不启动剪映，只在临时目录里跑 jy.py。"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
JY = ROOT / "scripts" / "jy.py"


def run_cli(args, cwd):
    return subprocess.run([sys.executable, str(JY), *args], cwd=str(cwd),
                          capture_output=True, text=True, encoding="utf-8",
                          errors="replace", timeout=180)


def tools(cwd):
    probe = run_cli(["probe"], cwd)
    try:
        payload = json.loads(probe.stdout)
    except json.JSONDecodeError:
        return None
    data = payload.get("data") or {}
    ff = data.get("ffmpeg") or {}
    if not ff.get("ffmpeg") or not ff.get("ffprobe"):
        return None
    return ff


def make_video(ffmpeg, path, seconds=2, size="320x180", source="testsrc"):
    made = subprocess.run(
        [ffmpeg, "-y", "-hide_banner", "-loglevel", "error",
         "-f", "lavfi", "-i", f"{source}=size={size}:rate=30",
         "-t", str(seconds), "-pix_fmt", "yuv420p", str(path)],
        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60)
    return made.returncode == 0 and path.is_file()


def make_audio(ffmpeg, path, seconds=3, frequency=440):
    made = subprocess.run(
        [ffmpeg, "-y", "-hide_banner", "-loglevel", "error",
         "-f", "lavfi", "-i", f"sine=frequency={frequency}:sample_rate=44100",
         "-t", str(seconds), "-c:a", "aac", str(path)],
        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60)
    return made.returncode == 0 and path.is_file()


def build(root, plan, out="draft"):
    plan_path = root / "plan.json"
    plan_path.write_text(json.dumps(plan, ensure_ascii=False, indent=2), "utf-8")
    built = run_cli(["build", "--plan", "plan.json", "--out", out], root)
    try:
        result = json.loads(built.stdout)
    except json.JSONDecodeError:
        print(f"build 没有返回 JSON：{built.stdout}\n{built.stderr}")
        return None, None
    if built.returncode != 0 or not result.get("ok"):
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return None, None
    document = json.loads((root / out / "draft_info.json").read_text("utf-8"))
    return result.get("data") or {}, document


def finish(case, checks):
    failed = [name for name, ok in checks.items() if not ok]
    if failed:
        print(f"{case} 检查失败：{failed}")
        return 1
    print(json.dumps({"ok": True, "case": case, "checks": checks}, ensure_ascii=False))
    return 0
