#!/usr/bin/env python3
"""04：图片素材走相对路径时，build 仍要生成封面。

这个案例故意把计划放在 plans/、素材放在 media/，并从临时目录根部启动，
用来锁住 “相对路径以计划文件为基准” 的约定；旧实现会把封面路径解析到 CWD。
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
JY = ROOT / "scripts" / "jy.py"


def _run(args, cwd):
    return subprocess.run([sys.executable, str(JY), *args], cwd=str(cwd),
                          capture_output=True, text=True, encoding="utf-8",
                          errors="replace", timeout=120)


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="jy-example-") as tmp:
        root = Path(tmp)
        probe = _run(["probe"], root)
        try:
            payload = json.loads(probe.stdout)
        except json.JSONDecodeError:
            print(f"probe 没有返回 JSON：{probe.stdout}\n{probe.stderr}")
            return 1
        tools = (payload.get("data") or {}).get("ffmpeg") or {}
        if not tools.get("ffmpeg") or not tools.get("ffprobe"):
            print("SKIP 04-media-build: 没有可用的 ffmpeg/ffprobe")
            return 77

        media = root / "media"
        plans = root / "plans"
        media.mkdir()
        plans.mkdir()
        image = media / "pic.png"
        made = subprocess.run(
            [tools["ffmpeg"], "-y", "-hide_banner", "-loglevel", "error",
             "-f", "lavfi", "-i", "color=c=red:s=64x64", "-frames:v", "1",
             str(image)],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=60,
        )
        if made.returncode != 0 or not image.is_file():
            print(f"生成测试图片失败：{made.stderr}")
            return 1

        plan = {
            "schema": "jianying-plan/v1",
            "name": "example-media",
            "canvas": {"width": 640, "height": 360, "fps": 30},
            "tracks": [{
                "type": "image",
                "segments": [{"path": "../media/pic.png", "start": 0, "duration": 2}],
            }],
        }
        (plans / "plan.json").write_text(
            json.dumps(plan, ensure_ascii=False, indent=2), "utf-8")

        built = _run(["build", "--plan", "plans/plan.json", "--out", "out/draft"], root)
        try:
            result = json.loads(built.stdout)
        except json.JSONDecodeError:
            print(f"build 没有返回 JSON：{built.stdout}\n{built.stderr}")
            return 1
        if built.returncode != 0 or not result.get("ok"):
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 1

        data = result.get("data") or {}
        cover = data.get("cover")
        draft = Path(data.get("draft_dir") or "")
        if not cover or not (draft / "draft_cover.jpg").is_file():
            print(f"封面没有生成：cover={cover!r}, draft={draft}")
            return 1

        inspected = _run(["inspect", "out/draft"], root)
        try:
            info = json.loads(inspected.stdout)
        except json.JSONDecodeError:
            print(f"inspect 没有返回 JSON：{inspected.stdout}\n{inspected.stderr}")
            return 1
        if inspected.returncode != 0 or not info.get("ok"):
            print(json.dumps(info, ensure_ascii=False, indent=2))
            return 1
        if (info.get("data") or {}).get("missing_media"):
            print(f"inspect 报告 missing_media：{info['data']['missing_media']}")
            return 1

        print(json.dumps({"ok": True, "case": "04-media-build",
                          "cover": cover, "draft": str(draft)},
                         ensure_ascii=False))
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
