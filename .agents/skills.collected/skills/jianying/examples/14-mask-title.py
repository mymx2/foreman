#!/usr/bin/env python3
"""14：蒙版 + 文字模板 + 背景/阴影（离线结构）。"""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

from _jy_example import build, finish, make_video, tools


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="jy-example-") as tmp:
        root = Path(tmp)
        ff = tools(root)
        if not ff:
            print("SKIP 14-mask-title: 没有可用的 ffmpeg/ffprobe")
            return 77
        if not make_video(ff["ffmpeg"], root / "bg.mp4", 3):
            print("生成背景视频失败")
            return 1
        plan = {
            "schema": "jianying-plan/v1",
            "name": "蒙版标题",
            "canvas": {"width": 640, "height": 360, "fps": 30},
            "tracks": [
                {"type": "video", "segments": [{
                    "path": "bg.mp4", "start": 0, "duration": 3,
                    "mask": {"resource_type": "line", "name": "线性",
                             "resource_id": "123456", "path": "C:/cache/mask",
                             "config": {"width": 0.5}},
                }]},
                {"type": "text", "segments": [{
                    "text": "重点标题", "start": 0.4, "duration": 2,
                    "font_size": 14, "color": "#FFD400", "y": 0.1,
                    "bold": True,
                    "background": {"color": "#000000", "alpha": 0.5,
                                   "round_radius": 0.2},
                    "shadow": {"color": "#000000", "alpha": 0.6,
                               "distance": 4, "diffuse": 12},
                    "text_template": {
                        "resource_id": "987654", "name": "划重点",
                        "path": "C:/cache/template",
                        "resources": [{"panel": "text", "resource_id": "111",
                                       "path": "C:/cache/panel"}],
                    },
                }]},
            ],
        }
        result, document = build(root, plan)
        if not document:
            return 1
        text_seg = document["tracks"][1]["segments"][0]
        text_material = document["materials"]["texts"][0]
        template = document["materials"]["text_templates"][0]
        content = json.loads(text_material["content"])
        checks = {
            "mask_bucket": len(document["materials"]["common_mask"]) == 1,
            "mask_ref": document["materials"]["common_mask"][0]["id"]
                        in document["tracks"][0]["segments"][0]["extra_material_refs"],
            "template_bucket": len(document["materials"]["text_templates"]) == 1,
            "template_material_id": text_seg["material_id"] == template["id"],
            "template_resource": template["resource_id"] == "987654",
            "template_panel": template["resources"][0]["panel"] == "text",
            "text_material_ref": text_material["id"] in text_seg["extra_material_refs"],
            "bold": content["styles"][0].get("bold") is True,
            "font_color": text_material.get("text_color") == "#FFD400",
            "background_color": text_material.get("background_color") == "#000000",
            "background_alpha": text_material.get("background_alpha") == 0.5,
            "background_radius": text_material.get("background_round_radius") == 0.2,
            "shadow": text_material.get("has_shadow") is True,
            "shadow_distance": text_material.get("shadow_distance") == 4,
            "shadow_alpha": text_material.get("shadow_alpha") == 0.6,
            "materials_reported": result["materials"].get("text_templates") == 1,
        }
        return finish("14-mask-title", checks)


if __name__ == "__main__":
    raise SystemExit(main())
