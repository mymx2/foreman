#!/usr/bin/env python3
"""案例 07：竖屏标题 + 双文字轨 + BGM。

用一张竖屏测试视频（自带音轨）做 1080×1920 草稿，验证：
- 画布独立于素材尺寸；
- 标题/字幕两条文字轨同时存在；
- BGM 进入音频轨；
- inspect 的时长/轨道/文字计数与计划一致。
离线，不启动剪映。
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


def _tool(path: str, args, timeout=90):
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
            print("SKIP 07-vertical-title-bgm: 没有可用的 ffmpeg/ffprobe")
            return 77

        media = root / "media"
        media.mkdir()
        source = media / "vertical.mp4"
        made = _tool(tools["ffmpeg"], [
            "-y", "-hide_banner", "-loglevel", "error",
            "-f", "lavfi", "-i", "color=c=teal:s=540x960:d=3",
            "-f", "lavfi", "-i", "sine=frequency=440:duration=3",
            "-c:v", "mpeg4", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-shortest", str(source),
        ])
        if made.returncode != 0 or not source.is_file():
            print(f"生成竖屏测试视频失败：{made.stderr}")
            return 1

        plan = {
            "schema": "jianying-plan/v1",
            "name": "example-vertical",
            "canvas": {"width": 1080, "height": 1920, "fps": 30},
            "tracks": [
                {"type": "video", "name": "主轨", "segments": [
                    {"path": "media/vertical.mp4", "start": 0, "duration": 3},
                ]},
                {"type": "text", "name": "标题", "segments": [
                    {"text": "竖屏标题", "start": 0.2, "duration": 2.6,
                     "font_size": 14, "color": "#FFD400", "y": 0.2},
                ]},
                {"type": "text", "name": "字幕", "segments": [
                    {"text": "底部字幕", "start": 0.5, "duration": 2.4,
                     "font_size": 8, "y": -0.72},
                ]},
                {"type": "audio", "name": "BGM", "segments": [
                    {"path": "media/vertical.mp4", "start": 0, "duration": 3,
                     "volume": 0.25},
                ]},
            ],
        }
        (root / "plan.json").write_text(
            json.dumps(plan, ensure_ascii=False, indent=2), "utf-8")

        built = _run(["build", "--plan", "plan.json", "--out", "draft"], root)
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
        by_type = {}
        for track in tracks:
            by_type[track.get("type")] = by_type.get(track.get("type"), 0) + 1
        ok = (
            inspected.returncode == 0 and info.get("ok")
            and not data.get("missing_media")
            and abs(float(data.get("duration") or 0) - 3.0) < 0.01
            and len(data.get("texts") or []) == 2
            and by_type.get("video") == 1
            and by_type.get("audio") == 1
            and by_type.get("text") == 2
            and (data.get("canvas") or {}).get("width") == 1080
            and (data.get("canvas") or {}).get("height") == 1920
        )
        print(json.dumps({
            "ok": bool(ok),
            "case": "07-vertical-title-bgm",
            "duration": data.get("duration"),
            "canvas": data.get("canvas"),
            "texts": len(data.get("texts") or []),
            "tracks": by_type,
        }, ensure_ascii=False))
        return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
