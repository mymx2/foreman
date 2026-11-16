#!/usr/bin/env python3
"""12：逐片段高级字段（crop/flip/reverse/mask/curve/color wheel）离线落盘。

用 ffmpeg 生成 1 秒测试视频，验证 build 会把高级字段写进对应 materials 桶，
而不是只存在于计划 JSON。不启动剪映、不读用户素材。
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
JY = ROOT / "scripts" / "jy.py"


def _run(args, cwd):
    return subprocess.run([sys.executable, str(JY), *args], cwd=str(cwd),
                          capture_output=True, text=True, encoding="utf-8",
                          errors="replace", timeout=120)


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
            print("SKIP 12-advanced-fields: 没有可用的 ffmpeg/ffprobe")
            return 77

        video = root / "clip.mp4"
        made = subprocess.run(
            [tools["ffmpeg"], "-y", "-hide_banner", "-loglevel", "error",
             "-f", "lavfi", "-i", "testsrc=size=320x180:rate=30",
             "-t", "1", "-pix_fmt", "yuv420p", str(video)],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=60,
        )
        if made.returncode != 0 or not video.is_file():
            print(f"生成测试视频失败：{made.stderr}")
            return 1

        plan = {
            "schema": "jianying-plan/v1",
            "name": "advanced-fields",
            "canvas": {"width": 320, "height": 180, "fps": 30},
            "tracks": [{"type": "video", "segments": [{
                "path": "clip.mp4", "start": 0, "duration": 1.0,
                "crop": {"x": 0.05, "y": 0.1, "w": 0.8, "h": 0.7},
                "flip": {"horizontal": True},
                "reverse": True,
                "mask": {"resource_type": "line", "name": "线性",
                         "resource_id": "123456", "path": "C:/cache/mask",
                         "config": {"width": 0.5}},
                "curve_speed": {"name": "先慢后快",
                                "points": [{"x": 0, "y": 1},
                                           {"x": 0.5, "y": 0.5},
                                           {"x": 1, "y": 2}]},
                "color_wheel": {"segment": "gamma", "red": 0.1,
                                "green": -0.2, "blue": 0.3, "hsl": True},
                "native": {"materials": [{
                    "bucket": "video_shadows", "ref": False,
                    "value": {"type": "video_shadow", "shadow_alpha": 0.2},
                }]},
            }]}],
        }
        plan_path = root / "plan.json"
        plan_path.write_text(json.dumps(plan, ensure_ascii=False, indent=2), "utf-8")

        built = _run(["build", "--plan", "plan.json", "--out", "draft"], root)
        try:
            result = json.loads(built.stdout)
        except json.JSONDecodeError:
            print(f"build 没有返回 JSON：{built.stdout}\n{built.stderr}")
            return 1
        if built.returncode != 0 or not result.get("ok"):
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 1

        document = json.loads((root / "draft" / "draft_info.json").read_text("utf-8"))
        segment = document["tracks"][0]["segments"][0]
        material = document["materials"]["videos"][0]
        shadow = document["materials"]["video_shadows"][0]
        speed = document["materials"]["speeds"][0]
        wheel = document["materials"]["primary_color_wheels"][0]
        checks = {
            "crop_x": abs(material["crop"]["upper_left_x"] - 0.05) < 1e-9,
            "crop_ratio": material["crop_ratio"] == "free",
            "flip_horizontal": segment["clip"]["flip"]["horizontal"] is True,
            "flip_vertical": segment["clip"]["flip"]["vertical"] is False,
            "reverse": segment["reverse"] is True,
            "mask_id": document["materials"]["common_mask"][0]["id"]
                       in segment["extra_material_refs"],
            "mask_constant_empty": document["materials"]["common_mask"][0]["constant_material_id"] == "",
            "curve_name": speed["curve_speed"]["name"] == "先慢后快",
            "curve_point": speed["curve_speed"]["speed_points"][1] == {"x": 0.5, "y": 0.5},
            "wheel_red": wheel["red"] == 0.1,
            "wheel_green": wheel["green"] == -0.2,
            "hsl": len(document["materials"]["hsl"]) == 1,
            "native_type": shadow["type"] == "video_shadow",
            "native_alpha": shadow["shadow_alpha"] == 0.2,
            "native_ref_false": shadow["id"] not in segment["extra_material_refs"],
        }
        failed = [name for name, ok in checks.items() if not ok]
        if failed:
            print(f"高级字段没有落盘：{failed}")
            return 1
        print(json.dumps({"ok": True, "case": "12-advanced-fields",
                          "checks": checks}, ensure_ascii=False))
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
