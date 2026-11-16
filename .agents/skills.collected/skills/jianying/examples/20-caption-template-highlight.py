#!/usr/bin/env python3
"""20：字幕模板 + caption_info + 关键词高亮（离线结构，不启动剪映）。"""
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
            "name": "字幕模板与高亮",
            "canvas": {"width": 640, "height": 360, "fps": 30},
            "tracks": [{
                "type": "text",
                "name": "字幕",
                "segments": [{
                    "text": "AI工具分享 AI时代",
                    "start": 0,
                    "duration": 3,
                    "caption_template": {
                        "resource_id": "7369552920146119974",
                        "name": "白字黑边",
                        "path": "C:/tmpl",
                    },
                    "caption_info": {
                        "id": "caption-1",
                        "speaker_type": "",
                        "speaker_id": "",
                        "caption_segment_id": "seg-1",
                        "original_text": "AI工具分享 AI时代",
                        "words": [{
                            "id": "word-1",
                            "text": "AI工具分享 AI时代",
                            "tag": "",
                            "origin_text": "AI工具分享 AI时代",
                            "time_range": {"start": 0, "duration": 3000000},
                        }],
                    },
                    "highlight": {
                        "words": ["AI"],
                        "color": "#FFD400",
                        "bold": True,
                    },
                }],
            }],
        }
        built, document = build(root, plan)
        if not document:
            return 1
        material = document["materials"]["texts"][0]
        segment = document["tracks"][0]["segments"][0]
        content = json.loads(material["content"])
        checks = {
            "caption_template": material.get("caption_template_info", {}).get(
                "resource_id") == "7369552920146119974",
            "recognize_text": material.get("recognize_text") == "AI工具分享 AI时代",
            "caption_info": segment.get("caption_info", {}).get(
                "original_text") == "AI工具分享 AI时代",
            "highlight_ranges": len(content.get("styles") or []) == 3,
            "duration": built.get("duration") == 3.0,
        }
        return finish("20-caption-template-highlight", checks)


if __name__ == "__main__":
    raise SystemExit(main())
