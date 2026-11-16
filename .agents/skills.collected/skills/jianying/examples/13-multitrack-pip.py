#!/usr/bin/env python3
"""13：多轨画中画 + 关键帧 + 蒙版 + 变速（离线结构）。"""
from __future__ import annotations

import tempfile
from pathlib import Path

from _jy_example import build, finish, make_video, tools


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="jy-example-") as tmp:
        root = Path(tmp)
        ff = tools(root)
        if not ff:
            print("SKIP 13-multitrack-pip: 没有可用的 ffmpeg/ffprobe")
            return 77
        if not make_video(ff["ffmpeg"], root / "main.mp4", 3):
            print("生成主轨视频失败")
            return 1
        if not make_video(ff["ffmpeg"], root / "pip.mp4", 2):
            print("生成画中画视频失败")
            return 1
        plan = {
            "schema": "jianying-plan/v1",
            "name": "多轨画中画",
            "canvas": {"width": 640, "height": 360, "fps": 30},
            "tracks": [
                {"type": "video", "name": "主轨", "segments": [{
                    "path": "main.mp4", "start": 0, "duration": 3,
                    "mask": {"resource_type": "line", "name": "线性",
                             "resource_id": "123456", "path": "C:/cache/mask",
                             "config": {"width": 0.5}},
                }]},
                {"type": "video", "name": "画中画", "segments": [{
                    "path": "pip.mp4", "start": 0.5, "duration": 1.5,
                    "scale": 0.35, "x": 0.55, "y": 0.45, "speed": 0.5,
                    "keyframes": {"scale": [[0, 1.0], [0.75, 1.08]]},
                }]},
            ],
        }
        result, document = build(root, plan)
        if not document:
            return 1
        tracks = document["tracks"]
        pip = tracks[1]["segments"][0]
        checks = {
            "two_visual_tracks": len([t for t in tracks if t["type"] == "video"]) == 2,
            "pip_flag": tracks[1].get("flag") == 2,
            "pip_render_index": pip.get("render_index", 0) >= 1,
            "pip_scale": pip["clip"]["scale"] == {"x": 0.35, "y": 0.35},
            "pip_transform": pip["clip"]["transform"] == {"x": 0.55, "y": 0.45},
            "pip_speed": pip.get("speed") == 0.5,
            "pip_source_duration": pip["source_timerange"]["duration"] == 750000,
            "mask_bucket": len(document["materials"]["common_mask"]) == 1,
            "keyframe_scale": any(k["property_type"] == "KFTypeScaleX"
                                  for k in (pip.get("common_keyframes") or [])),
            "materials_reported": result["materials"].get("common_mask") == 1,
        }
        return finish("13-multitrack-pip", checks)


if __name__ == "__main__":
    raise SystemExit(main())
