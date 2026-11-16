#!/usr/bin/env python3
"""17：BGM + 原声 + 淡入淡出 + 声道 + 音效（离线结构）。"""
from __future__ import annotations

import tempfile
from pathlib import Path

from _jy_example import build, finish, make_audio, make_video, tools


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="jy-example-") as tmp:
        root = Path(tmp)
        ff = tools(root)
        if not ff:
            print("SKIP 17-audio-mix: 没有可用的 ffmpeg/ffprobe")
            return 77
        if not make_video(ff["ffmpeg"], root / "voice.mp4", 3):
            print("生成口播视频失败")
            return 1
        if not make_audio(ff["ffmpeg"], root / "bgm.m4a", 3):
            print("生成 BGM 失败")
            return 1
        plan = {
            "schema": "jianying-plan/v1",
            "name": "音频混合",
            "canvas": {"width": 640, "height": 360, "fps": 30},
            "tracks": [
                {"type": "video", "segments": [{
                    "path": "voice.mp4", "start": 0, "duration": 3,
                    "volume": 1.0,
                }]},
                {"type": "audio", "segments": [{
                    "path": "bgm.m4a", "start": 0, "duration": 3,
                    "volume": 0.35,
                    "audio_fade": {"in": 0.5, "out": 0.5},
                    "channel": 0,
                    "audio_effect": {"resource_id": "tone-1", "name": "低音",
                                     "category_id": "tone",
                                     "params": {"pitch": 0.8}},
                }]},
            ],
        }
        result, document = build(root, plan)
        if not document:
            return 1
        audio_seg = document["tracks"][1]["segments"][0]
        fade = document["materials"]["audio_fades"][0]
        mapping = document["materials"]["sound_channel_mappings"][0]
        effect = document["materials"]["audio_effects"][0]
        checks = {
            "audio_track": document["tracks"][1]["type"] == "audio",
            "volume": audio_seg["volume"] == 0.35,
            "fade_in": fade["fade_in_duration"] == 500000,
            "fade_out": fade["fade_out_duration"] == 500000,
            "fade_ref": fade["id"] in audio_seg["extra_material_refs"],
            "channel": mapping["audio_channel_mapping"] == 0,
            "channel_ref": mapping["id"] in audio_seg["extra_material_refs"],
            "effect_resource": effect["resource_id"] == "tone-1",
            "effect_param": effect["audio_adjust_params"][0]["name"] == "pitch",
            "effect_value": effect["audio_adjust_params"][0]["value"] == 0.8,
            "effect_ref": effect["id"] in audio_seg["extra_material_refs"],
            "materials_reported": result["materials"].get("audio_fades") == 1,
        }
        return finish("17-audio-mix", checks)


if __name__ == "__main__":
    raise SystemExit(main())
