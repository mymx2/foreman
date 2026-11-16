#!/usr/bin/env python3
"""案例 06：定格工作流（抽帧图片 + 前后视频段）。

不冒充原生 freeze 字段：用 ffmpeg 从源视频抽一帧，作为图片片段插在两个视频段之间，
再用 inspect 验证“视频段-图片段-视频段”的时间线结构。离线，不启动剪映。
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
JY = ROOT / "scripts" / "jy.py"


def _run(args, cwd, timeout=120):
    return subprocess.run([sys.executable, str(JY), *args], cwd=str(cwd),
                          capture_output=True, text=True, encoding="utf-8",
                          errors="replace", timeout=timeout)


def _tool(path: str, args, timeout=60):
    return subprocess.run([path, *args], capture_output=True, text=True,
                          encoding="utf-8", errors="replace", timeout=timeout)


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
            print("SKIP 06-freeze-workflow: 没有可用的 ffmpeg/ffprobe")
            return 77

        media = root / "media"
        media.mkdir()
        source = media / "source.mp4"
        made = _tool(tools["ffmpeg"], [
            "-y", "-hide_banner", "-loglevel", "error",
            "-f", "lavfi", "-i", "color=c=blue:s=320x180:d=3",
            "-c:v", "mpeg4", "-pix_fmt", "yuv420p", str(source),
        ])
        if made.returncode != 0 or not source.is_file():
            print(f"生成测试视频失败：{made.stderr}")
            return 1

        frame = media / "freeze.png"
        grabbed = _tool(tools["ffmpeg"], [
            "-y", "-hide_banner", "-loglevel", "error",
            "-ss", "1.5", "-i", str(source), "-frames:v", "1", str(frame),
        ])
        if grabbed.returncode != 0 or not frame.is_file():
            print(f"抽帧失败：{grabbed.stderr}")
            return 1

        plan = {
            "schema": "jianying-plan/v1",
            "name": "example-freeze",
            "canvas": {"width": 320, "height": 180, "fps": 30},
            "tracks": [
                {"type": "video", "name": "主轨", "segments": [
                    {"path": "media/source.mp4", "start": 0, "duration": 1,
                     "source_start": 0},
                    {"path": "media/source.mp4", "start": 2, "duration": 1,
                     "source_start": 2},
                ]},
                {"type": "image", "name": "定格帧", "segments": [
                    {"path": "media/freeze.png", "start": 1, "duration": 1},
                ]},
                {"type": "text", "name": "说明", "segments": [
                    {"text": "定格 1 秒", "start": 1, "duration": 1,
                     "font_size": 8, "y": -0.7},
                ]},
            ],
        }
        (root / "plan.json").write_text(
            json.dumps(plan, ensure_ascii=False, indent=2), "utf-8")

        built = _run(["build", "--plan", "plan.json", "--out", "draft", "--no-cover"], root)
        try:
            result = json.loads(built.stdout)
        except json.JSONDecodeError:
            print(f"build 没有返回 JSON：{built.stdout}\n{built.stderr}")
            return 1
        if built.returncode != 0 or not result.get("ok"):
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 1

        inspected = _run(["inspect", "draft"], root)
        try:
            info = json.loads(inspected.stdout)
        except json.JSONDecodeError:
            print(f"inspect 没有返回 JSON：{inspected.stdout}\n{inspected.stderr}")
            return 1
        data = info.get("data") or {}
        tracks = data.get("tracks") or []
        segments = sum(int(track.get("segments") or 0) for track in tracks)
        ok = (
            inspected.returncode == 0 and info.get("ok")
            and not data.get("missing_media")
            and abs(float(data.get("duration") or 0) - 3.0) < 0.01
            and len(tracks) == 3
            and segments == 4
        )
        print(json.dumps({
            "ok": bool(ok),
            "case": "06-freeze-workflow",
            "duration": data.get("duration"),
            "tracks": len(tracks),
            "segments": segments,
        }, ensure_ascii=False))
        return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
