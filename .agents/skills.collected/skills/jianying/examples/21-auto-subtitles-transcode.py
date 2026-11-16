#!/usr/bin/env python3
"""21：已有 SRT 的一键字幕草稿 + 本地码率转码（离线）。"""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

from _jy_example import finish, make_video, run_cli, tools


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="jy-example-") as tmp:
        root = Path(tmp)
        ff = tools(root)
        if not ff:
            print("SKIP 21-auto-subtitles-transcode: 没有可用的 ffmpeg/ffprobe")
            return 77
        video = root / "main.mp4"
        if not make_video(ff["ffmpeg"], video, seconds=2):
            print("生成测试视频失败")
            return 1
        (root / "subs.srt").write_text(
            "1\n00:00:00,000 --> 00:00:01,000\n第一句\n\n"
            "2\n00:00:01,200 --> 00:00:02,000\n第二句\n", "utf-8")
        built = run_cli([
            "auto-subtitles", "--video", "main.mp4", "--srt", "subs.srt",
            "--out", "draft", "--plan-out", "plan.json", "--no-cover",
        ], root)
        try:
            result = json.loads(built.stdout)
        except json.JSONDecodeError:
            print(f"auto-subtitles 没有返回 JSON：{built.stdout}\n{built.stderr}")
            return 1
        if built.returncode != 0 or not result.get("ok"):
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 1
        draft = root / "draft"
        version = json.loads((draft / ".jianying-versions" / "versions.json").read_text("utf-8"))
        transcoded = run_cli([
            "transcode", "main.mp4", "-o", "out-500k.mp4",
            "--video-bitrate", "500k", "--audio-bitrate", "96k",
        ], root)
        try:
            transcode_result = json.loads(transcoded.stdout)
        except json.JSONDecodeError:
            print(f"transcode 没有返回 JSON：{transcoded.stdout}\n{transcoded.stderr}")
            return 1
        checks = {
            "subtitle_draft": (draft / "draft_info.json").is_file(),
            "subtitle_version": version.get("current") == "v001",
            "plan_kept": (root / "plan.json").is_file(),
            "transcode": (transcoded.returncode == 0
                          and transcode_result.get("ok") is True
                          and (root / "out-500k.mp4").is_file()),
            "transcode_note": "不是剪映原生" in json.dumps(
                transcode_result, ensure_ascii=False),
        }
        return finish("21-auto-subtitles-transcode", checks)


if __name__ == "__main__":
    raise SystemExit(main())