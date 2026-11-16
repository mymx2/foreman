#!/usr/bin/env python3
"""16：转场 + 滤镜 + 画面特效 + 色轮（离线结构）。"""
from __future__ import annotations

import tempfile
from pathlib import Path

from _jy_example import build, finish, make_video, tools


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="jy-example-") as tmp:
        root = Path(tmp)
        ff = tools(root)
        if not ff:
            print("SKIP 16-transition-filter-effect: 没有可用的 ffmpeg/ffprobe")
            return 77
        if not make_video(ff["ffmpeg"], root / "a.mp4", 2):
            print("生成视频失败")
            return 1
        if not make_video(ff["ffmpeg"], root / "b.mp4", 2):
            print("生成第二段视频失败")
            return 1
        plan = {
            "schema": "jianying-plan/v1",
            "name": "转场滤镜特效",
            "canvas": {"width": 640, "height": 360, "fps": 30},
            "filters": [{"resource_id": "987654321", "name": "冷蓝",
                         "value": 0.8, "start": 0, "duration": 4}],
            "tracks": [
                {"type": "video", "segments": [
                    {"path": "a.mp4", "start": 0, "duration": 2,
                     "transition": {"resource_id": "123456789", "name": "叠化",
                                    "duration": 0.5, "path": ""},
                     "color_wheel": {"segment": "gamma", "red": 0.1,
                                     "green": -0.2, "blue": 0.3}},
                    {"path": "b.mp4", "start": 2, "duration": 2},
                ]},
                {"type": "effect", "segments": [{
                    "resource_id": "effect-1", "name": "星火",
                    "path": "C:/cache/effect/effect-1",
                    "start": 0, "duration": 3, "value": 0.8,
                    "adjust_params": {"intensity": 0.5},
                }]},
            ],
        }
        result, document = build(root, plan)
        if not document:
            return 1
        effects = document["materials"].get("video_effects") or []
        transition = (document["materials"].get("transitions") or [{}])[0]
        filter_item = (document["materials"].get("effects") or [{}])[0]
        effect = effects[0] if effects else {}
        wheel = (document["materials"].get("primary_color_wheels") or [{}])[0]
        checks = {
            "transition": transition.get("resource_id") == "123456789",
            "transition_duration": transition.get("duration") == 500000,
            "filter": filter_item.get("resource_id") == "987654321",
            "filter_value": filter_item.get("value") == 0.8,
            "effect_track": document["tracks"][1]["type"] == "effect",
            "effect_resource": effect.get("resource_id") == "effect-1",
            "effect_name": effect.get("name") == "星火",
            "effect_value": effect.get("value") == 0.8,
            "effect_adjust": effect.get("adjust_params", [{}])[0].get("name") == "intensity",
            "effect_adjust_value": effect.get("adjust_params", [{}])[0].get("value") == 0.5,
            "effect_render_index": document["tracks"][1]["segments"][0]["render_index"] == 11000,
            "color_wheel": wheel.get("red") == 0.1 and wheel.get("green") == -0.2,
            "materials_reported": result["materials"].get("video_effects") == 1,
        }
        return finish("16-transition-filter-effect", checks)


if __name__ == "__main__":
    raise SystemExit(main())
