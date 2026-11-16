#!/usr/bin/env python3
"""15：花字/气泡/文字动画 + 贴纸（离线结构）。"""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

from _jy_example import build, finish


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="jy-example-") as tmp:
        root = Path(tmp)
        plan = {
            "schema": "jianying-plan/v1",
            "name": "文字特效",
            "canvas": {"width": 640, "height": 360, "fps": 30},
            "tracks": [
                {"type": "text", "segments": [{
                    "text": "花字标题", "start": 0, "duration": 2,
                    "font_size": 14, "color": "#FFFFFF", "y": 0.1,
                    "text_effect": {"resource_id": "flower-1",
                                    "effect_id": "flower-e1",
                                    "path": "C:/cache/flower"},
                    "text_bubble": {"resource_id": "bubble-1",
                                    "effect_id": "bubble-e1",
                                    "path": "C:/cache/bubble"},
                    "animations": [{"type": "in", "resource_id": "222",
                                    "name": "渐显入场", "duration": 0.5,
                                    "path": "C:/cache/anim"}],
                }]},
                {"type": "sticker", "segments": [{
                    "resource_id": "8c1d-uuid", "path": "C:/cache/sticker",
                    "start": 0.3, "duration": 1.5, "scale": 0.25,
                    "x": 0.35, "y": -0.3,
                }]},
            ],
        }
        result, document = build(root, plan)
        if not document:
            return 1
        filters = document["materials"]["filters"]
        text_seg = document["tracks"][0]["segments"][0]
        sticker = document["materials"]["stickers"][0]
        text_effect = next(f for f in filters if f["type"] == "text_effect")
        bubble = next(f for f in filters if f["type"] == "text_shape")
        animation = document["materials"]["material_animations"][0]
        checks = {
            "text_effect": text_effect["resource_id"] == "flower-1",
            "text_effect_id": text_effect["effect_id"] == "flower-e1",
            "text_bubble": bubble["resource_id"] == "bubble-1",
            "effect_refs": all(f["id"] in text_seg["extra_material_refs"]
                               for f in filters),
            "effect_style": json.loads(
                document["materials"]["texts"][0]["content"]
            )["styles"][0]["effectStyle"]["id"] == "flower-e1",
            "animation": animation["animations"][0]["resource_id"] == "222",
            "animation_type": animation["animations"][0]["type"] == "in",
            "sticker_track": document["tracks"][1]["type"] == "sticker",
            "sticker_material": sticker["resource_id"] == "8c1d-uuid",
            "sticker_scale": document["tracks"][1]["segments"][0]["clip"]["scale"] == {"x": 0.25, "y": 0.25},
            "materials_reported": result["materials"].get("filters") == 2,
        }
        return finish("15-text-effects", checks)


if __name__ == "__main__":
    raise SystemExit(main())
