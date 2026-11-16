#!/usr/bin/env python3
"""18：口播成片骨架：主轨 + 字幕/标题 + 画中画 + BGM（离线结构）。"""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

from _jy_example import build, finish, make_audio, make_video, tools


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="jy-example-") as tmp:
        root = Path(tmp)
        ff = tools(root)
        if not ff:
            print("SKIP 18-spoken-piece: 没有可用的 ffmpeg/ffprobe")
            return 77
        if not make_video(ff["ffmpeg"], root / "talk.mp4", 4):
            print("生成口播视频失败")
            return 1
        if not make_video(ff["ffmpeg"], root / "broll.mp4", 2):
            print("生成补充画面失败")
            return 1
        if not make_audio(ff["ffmpeg"], root / "bgm.m4a", 4):
            print("生成 BGM 失败")
            return 1
        plan = {
            "schema": "jianying-plan/v1",
            "name": "口播成片",
            "canvas": {"width": 1080, "height": 1920, "fps": 30},
            "tracks": [
                {"type": "video", "name": "口播主轨", "segments": [{
                    "path": "talk.mp4", "start": 0, "duration": 4,
                }]},
                {"type": "video", "name": "补充画面", "segments": [{
                    "path": "broll.mp4", "start": 1.5, "duration": 1.5,
                    "scale": 0.3, "x": 0.5, "y": 0.55,
                }]},
                {"type": "text", "name": "标题", "segments": [{
                    "text": "三分钟讲清楚", "start": 0.2, "duration": 2.5,
                    "font_size": 14, "color": "#FFD400", "y": 0.25,
                    "bold": True,
                    "background": {"color": "#000000", "alpha": 0.5},
                }]},
                {"type": "text", "name": "字幕", "segments": [
                    {"text": "第一句口播", "start": 0.5, "duration": 1.5,
                     "font_size": 8, "y": -0.72},
                    {"text": "第二句口播", "start": 2.0, "duration": 1.5,
                     "font_size": 8, "y": -0.72},
                ]},
                {"type": "audio", "name": "BGM", "segments": [{
                    "path": "bgm.m4a", "start": 0, "duration": 4,
                    "volume": 0.25, "audio_fade": {"in": 0.5, "out": 0.5},
                }]},
            ],
        }
        result, document = build(root, plan)
        if not document:
            return 1
        tracks = document["tracks"]
        title = document["materials"]["texts"][0]
        title_content = json.loads(title["content"])
        bgm_seg = tracks[4]["segments"][0]
        checks = {
            "five_tracks": len(tracks) == 5,
            "pip": tracks[1].get("flag") == 2 and tracks[1]["segments"][0]["render_index"] >= 1,
            "pip_scale": tracks[1]["segments"][0]["clip"]["scale"] == {"x": 0.3, "y": 0.3},
            "two_text_tracks": len([t for t in tracks if t["type"] == "text"]) == 2,
            "title_text": title_content["text"] == "三分钟讲清楚",
            "title_font_size": title.get("font_size") == 14,
            "title_background": title.get("background_alpha") == 0.5,
            "subtitle_count": len(tracks[3]["segments"]) == 2,
            "subtitle_bottom": tracks[3]["segments"][0]["clip"]["transform"]["y"] < 0,
            "bgm_volume": bgm_seg.get("volume") == 0.25,
            "bgm_fade": (document["materials"].get("audio_fades") or [{}])[0]
                        .get("fade_in_duration") == 500000,
            "materials_reported": result["materials"].get("audio_fades") == 1,
        }
        return finish("18-spoken-piece", checks)


if __name__ == "__main__":
    raise SystemExit(main())
