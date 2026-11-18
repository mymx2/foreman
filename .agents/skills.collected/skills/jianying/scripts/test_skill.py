#!/usr/bin/env python3
"""Offline self-test for the jianying skill.

    python scripts/test_skill.py

No 剪映 launch, native export, or user draft is touched. Draft cases run entirely
inside a temporary directory with media probing disabled.
"""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import io
import json
import math
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import threading
import time
import unittest
import urllib.error
import zipfile
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from jylib import ass as ass_mod  # noqa: E402
from jylib import beauty as beauty_mod  # noqa: E402
from jylib import bridge as bridge_mod  # noqa: E402
from jylib import draft as draft_mod  # noqa: E402
from jylib import env as env_mod  # noqa: E402
from jylib import index as index_mod  # noqa: E402
from jylib import interchange as interchange_mod  # noqa: E402
from jylib import loudness as loudness_mod  # noqa: E402
from jylib import maintenance as maintenance_mod  # noqa: E402
from jylib import media as media_mod  # noqa: E402
from jylib import media_tools as media_tools_mod  # noqa: E402
from jylib import packaging as packaging_mod  # noqa: E402
from jylib import resources as resources_mod  # noqa: E402
from jylib import template as template_mod  # noqa: E402
from jylib import transcode as transcode_mod  # noqa: E402
from jylib import versions as versions_mod  # noqa: E402
from jylib import workflow as workflow_mod  # noqa: E402
from jylib.errors import SkillError  # noqa: E402
import capability_probe as capability_mod  # noqa: E402
import check_skill as check_skill_mod  # noqa: E402
import jy as jy_mod  # noqa: E402
import upgrade_check as upgrade_mod  # noqa: E402


def write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), "utf-8")


def text_plan(path: Path) -> None:
    write_json(path, {
        "schema": "jianying-plan/v1",
        "name": "离线测试草稿",
        "canvas": {"width": 1080, "height": 1920, "fps": 30},
        "tracks": [{
            "type": "text",
            "name": "字幕",
            "segments": [
                {"text": "第一句", "start": 0.2, "duration": 2.0,
                 "font_size": 8, "y": -0.72},
                {"text": "第二句", "start": 2.4, "duration": 2.0,
                 "font_size": 8, "y": -0.72},
            ],
        }],
    })


class DraftTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.plan = self.root / "plan.json"
        text_plan(self.plan)
        # 这些测试验证复制/合并/索引逻辑，与剪映是否在运行无关；
        # 隔离编辑器守卫，避免套件结果随本机进程状态漂移。
        guard = mock.patch.object(index_mod, "_ensure_editor_closed", return_value=None)
        guard.start()
        self.addCleanup(guard.stop)

    def tearDown(self):
        self.tmp.cleanup()

    def test_audio_effect_material_fields_match_native_shape(self):
        with tempfile.TemporaryDirectory() as tmp:
            pkg = Path(tmp)
            (pkg / "extra.json").write_text(json.dumps({
                "setting": {"audio_effect_parameters_change": [
                    {"parameterIndex": 0, "portIndex": 0, "sliderName": "音调",
                     "minValue": 0.0, "defaultValue": 0.75, "maxValue": 1.0},
                    {"parameterIndex": 1, "portIndex": 0, "sliderName": "音色",
                     "minValue": 0.0, "defaultValue": 0.6, "maxValue": 1.0},
                ]}
            }, ensure_ascii=False), "utf-8")
            material = draft_mod._audio_effect_materials({
                "resource_id": "7020345789599715848", "name": "萝莉",
                "category_id": "tone", "path": str(pkg),
                "params": {"音调": 0.8, "音色": 0.5},
            })[0]
            self.assertEqual(material["type"], "audio_effect")
            self.assertEqual(material["sub_type"], 0)
            self.assertEqual(material["path"], str(pkg))
            params = material["audio_adjust_params"]
            self.assertEqual([p["parameterIndex"] for p in params], [0, 1])
            self.assertEqual(params[0]["value"], 0.8)
            self.assertEqual(params[0]["defaultValue"], 0.75)
            self.assertEqual(params[0]["maxValue"], 1.0)

    def test_video_animation_material(self):
        segment = {"extra_material_refs": []}
        doc = {"materials": {"material_animations": []}}
        draft_mod._apply_video_animations(
            segment,
            {"animations": [{
                "type": "in", "resource_id": "123", "name": "翻入",
                "duration": 1.17,
            }]},
            doc,
            [],
        )
        material = doc["materials"]["material_animations"][0]
        self.assertEqual(material["type"], "video_animation")
        self.assertEqual(material["animations"][0]["resource_id"], "123")
        self.assertEqual(segment["extra_material_refs"], [material["id"]])

    def test_background_fill_and_mix_mode_extras(self):
        segment = {"extra_material_refs": []}
        doc = {"materials": {}}
        extras = draft_mod._apply_video_extras(
            segment, {}, {
                "background_fill": {"type": "blur", "blur": 0.375},
                "mix_mode": "滤色",
            }, [], doc)
        self.assertEqual([item["kind"] for item in extras],
                         ["background_fill", "mix_mode"])
        fill = extras[0]["material"]
        self.assertEqual(fill["type"], "canvas_blur")
        self.assertEqual(fill["blur"], 0.375)
        self.assertEqual(fill["color"], "#00000000")
        mix = extras[1]["material"]
        self.assertEqual(mix["type"], "mix_mode")
        self.assertEqual(mix["name"], "滤色")
        self.assertEqual(mix["resource_id"], "6758325170760323597")
        self.assertEqual(mix["effect_id"], "871339")
        self.assertEqual(len(segment["extra_material_refs"]), 2)

    def test_background_fill_color_and_custom_mix_mode(self):
        fill = draft_mod._background_fill_material({
            "type": "color", "color": "#11223344"})
        self.assertEqual(fill["type"], "canvas_color")
        self.assertEqual(fill["color"], "#11223344")
        mix = draft_mod._mix_mode_material({
            "name": "自定义", "effect_id": "100", "resource_id": "200"})
        self.assertEqual(mix["name"], "自定义")
        self.assertEqual(mix["effect_id"], "100")
        self.assertEqual(mix["resource_id"], "200")
        with self.assertRaises(SkillError) as caught:
            draft_mod._mix_mode_material("不存在的模式")
        self.assertEqual(caught.exception.code, "VALIDATION")

    def test_loudness_json_parse(self):
        text = ('noise\n{\n "input_i" : "-20.5",\n "input_tp" : "-8.0",\n'
                ' "input_lra" : "2.0",\n "input_thresh" : "-30.0"\n}\n')
        payload = loudness_mod._find_loudnorm_json(text)
        self.assertEqual(payload["input_i"], "-20.5")
        self.assertIsNone(loudness_mod._find_loudnorm_json("no json"))

    def test_loudness_analyze_and_gain_ops(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_json(root / "draft_info.json", {
                "id": "draft",
                "duration": 4_000_000,
                "tracks": [{
                    "type": "audio",
                    "segments": [{
                        "id": "seg-1",
                        "material_id": "audio-1",
                        "target_timerange": {"start": 0, "duration": 4_000_000},
                        "source_timerange": {"start": 0, "duration": 4_000_000},
                        "volume": 1.0,
                    }],
                }],
                "materials": {"audios": [{
                    "id": "audio-1", "path": str(root / "voice.wav"),
                    "name": "voice.wav",
                }]},
            })

            def fake_measure(ffmpeg, path, *, start=0, duration=None, timeout=120):
                return {"lufs": -20.0, "true_peak_dbtp": -9.0,
                        "lra": 2.0, "input_threshold": -30.0,
                        "source": str(path)}

            with mock.patch.object(loudness_mod, "measure", side_effect=fake_measure):
                report = loudness_mod.analyze(
                    root, ffmpeg="ffmpeg", target_lufs=-14.0,
                    max_true_peak=-1.0)
            self.assertEqual(report["measured_count"], 1)
            clip = report["clips"][0]
            self.assertEqual(clip["status"], "gain")
            self.assertEqual(clip["gain_db"], 6.0)
            self.assertAlmostEqual(clip["target_volume"], 1.995262, places=6)
            ops = loudness_mod.gain_ops(report)
            self.assertEqual(ops, [{
                "op": "set_volume", "segment": "seg-1", "volume": 1.995262,
            }])

    def test_loudness_boundary_states_and_clamps(self):
        def draft_with(volume):
            tmp = tempfile.TemporaryDirectory()
            self.addCleanup(tmp.cleanup)
            root = Path(tmp.name)
            write_json(root / "draft_info.json", {
                "id": "draft", "duration": 4_000_000,
                "tracks": [{"type": "audio", "segments": [{
                    "id": "seg-1", "material_id": "audio-1",
                    "target_timerange": {"start": 0, "duration": 4_000_000},
                    "source_timerange": {"start": 0, "duration": 4_000_000},
                    "volume": volume,
                }]}],
                "materials": {"audios": [{
                    "id": "audio-1", "path": str(root / "voice.wav"),
                    "name": "voice.wav",
                }]},
            })
            return root

        def analyze(root, measured, **kwargs):
            def fake_measure(ffmpeg, path, *, start=0, duration=None, timeout=120):
                if isinstance(measured, Exception):
                    raise measured
                return measured

            with mock.patch.object(loudness_mod, "measure", side_effect=fake_measure):
                return loudness_mod.analyze(root, ffmpeg="ffmpeg", **kwargs)

        clip = lambda report: report["clips"][0]

        # 静音：lufs=None → silent
        clip_silent = clip(analyze(draft_with(1.0),
                                   {"lufs": None, "true_peak_dbtp": None}))
        self.assertEqual(clip_silent["status"], "silent")
        self.assertIsNone(clip_silent["gain_db"])

        # 测量失败：SkillError → unmeasured + warning
        report = analyze(draft_with(1.0), SkillError(
            "测不了", code="LOUDNESS_MEASURE_FAILED"))
        self.assertEqual(clip(report)["status"], "unmeasured")
        self.assertEqual(report["unmeasured_count"], 1)
        self.assertTrue(report["warnings"])

        # 无 target：measured，不计算增益
        self.assertEqual(clip(analyze(draft_with(1.0), {
            "lufs": -20.0, "true_peak_dbtp": -9.0}))["status"], "measured")

        # 增益上限 6 dB
        clip_gain = clip(analyze(draft_with(1.0), {
            "lufs": -70.0, "true_peak_dbtp": -9.0},
            target_lufs=-14.0, max_gain_db=6.0))
        self.assertAlmostEqual(clip_gain["gain_db"], 6.0)
        self.assertAlmostEqual(clip_gain["target_volume"], 1.995262, places=6)

        # 衰减上限 24 dB
        clip_att = clip(analyze(draft_with(1.0), {
            "lufs": -5.0, "true_peak_dbtp": -1.0},
            target_lufs=-70.0, max_attenuation_db=24.0))
        self.assertAlmostEqual(clip_att["gain_db"], -24.0)
        self.assertAlmostEqual(clip_att["target_volume"], 10 ** (-24 / 20), places=6)

        # true peak 比增益上限更紧时以 peak 为准
        clip_peak = clip(analyze(draft_with(1.0), {
            "lufs": -20.0, "true_peak_dbtp": -1.0},
            target_lufs=-14.0, max_true_peak=-2.0))
        self.assertAlmostEqual(clip_peak["gain_db"], -1.0)

        # 目标音量超过 10 被钳到 10，并按钳后值重算 gain
        clip_cut = clip(analyze(draft_with(8.0), {
            "lufs": -20.0, "true_peak_dbtp": -9.0},
            target_lufs=-14.0, max_gain_db=6.0))
        self.assertTrue(clip_cut["clipped"])
        self.assertEqual(clip_cut["target_volume"], 10.0)
        self.assertAlmostEqual(clip_cut["gain_db"], 1.9382, places=3)

    def build(self, out: Path, *, force=False):
        with mock.patch.object(env_mod, "find_install", return_value=None), \
                mock.patch.object(env_mod, "find_ffmpeg",
                                  return_value={"ffmpeg": None, "ffprobe": None}):
            return draft_mod.build(self.plan, out, force=force, make_cover=False)

    def test_mixed_visual_audio_route_and_speed_math(self):
        plan = self.root / "mixed-plan.json"
        write_json(plan, {
            "schema": "jianying-plan/v1",
            "name": "混合轨测试",
            "canvas": {"width": 640, "height": 360, "fps": 30},
            "tracks": [
                {"type": "video", "segments": [
                    {"path": "main.mp4", "start": 0, "duration": 1.0, "speed": 1.5}]},
                {"type": "image", "segments": [
                    {"path": "logo.png", "start": 0.2, "duration": 1.0,
                     "scale": 0.2, "keyframes": {"scale": [[0, 1], [1, 0.8]]}}]},
                {"type": "audio", "segments": [
                    {"path": "bgm.m4a", "start": 0, "duration": 1.2, "volume": 0.2}]},
                {"type": "text", "segments": [
                    {"text": "字幕", "start": 0.1, "duration": 1.0, "y": -0.7}]},
            ],
        })

        for name in ("main.mp4", "logo.png", "bgm.m4a"):
            (self.root / name).write_bytes(b"fixture")

        def fake_probe(_ffprobe, path):
            suffix = Path(path).suffix.lower()
            if suffix == ".m4a":                return {"path": str(path), "name": Path(path).name, "kind": "audio",
                        "duration": 3.0, "width": 0, "height": 0, "fps": 0.0,
                        "has_video": False, "has_audio": True, "codec": "aac"}
            if suffix == ".png":
                return {"path": str(path), "name": Path(path).name, "kind": "image",
                        "duration": 0.0, "width": 120, "height": 120, "fps": 0.0,
                        "has_video": True, "has_audio": False, "codec": "png"}
            return {"path": str(path), "name": Path(path).name, "kind": "video",
                    "duration": 3.0, "width": 640, "height": 360, "fps": 30.0,
                    "has_video": True, "has_audio": True, "codec": "h264"}

        out = self.root / "mixed"
        with mock.patch.object(env_mod, "find_install", return_value=None), \
                mock.patch.object(env_mod, "find_ffmpeg",
                                  return_value={"ffmpeg": None, "ffprobe": None}), \
                mock.patch.object(draft_mod.media_mod, "probe_media", side_effect=fake_probe):
            result = draft_mod.build(plan, out, make_cover=False)
        self.assertEqual(result["tracks"]["video"], 2)
        self.assertEqual(result["tracks"]["audio"], 1)
        self.assertEqual(result["tracks"]["text"], 1)

        document = json.loads((out / "draft_info.json").read_text("utf-8"))
        visual = [track for track in document["tracks"] if track["type"] == "video"]
        self.assertEqual([track["flag"] for track in visual], [0, 2])
        self.assertEqual([track["segments"][0]["render_index"] for track in visual], [0, 1])
        self.assertEqual(document["materials"]["texts"][0]["type"], "text")
        video_segment = visual[0]["segments"][0]
        self.assertEqual(video_segment["source_timerange"]["duration"], 1_500_000)
        self.assertTrue(visual[1]["segments"][0]["common_keyframes"])
        info = draft_mod.inspect(out)
        self.assertEqual(info["missing_media"], [])
        self.assertEqual(info["texts"][0]["text"], "字幕")

        # patch 层与 build 层同口径：图片变速必须带 details.field，供调用方分流。
        speed_ops = self.root / "image-speed-ops.json"
        write_json(speed_ops, {"ops": [
            {"op": "set_speed", "segment": 1, "speed": 2},
        ]})
        with self.assertRaises(SkillError) as caught:
            draft_mod.patch(out, speed_ops, self.root / "speed-copy")
        self.assertEqual(caught.exception.code, "VALIDATION")
        self.assertEqual(caught.exception.details.get("field"), "speed")
        self.assertEqual(caught.exception.details.get("speed"), 2.0)

    def test_background_fill_and_mix_mode_build(self):
        plan = self.root / "background-mix-plan.json"
        write_json(plan, {
            "schema": "jianying-plan/v1",
            "name": "背景与混合模式",
            "canvas": {"width": 640, "height": 360, "fps": 30},
            "tracks": [{"type": "image", "segments": [{
                "path": "bg.png", "start": 0, "duration": 2,
                "background_fill": {"type": "color", "color": "#11223344"},
                "mix_mode": "滤色",
            }]}],
        })
        (self.root / "bg.png").write_bytes(b"fixture")

        def fake_probe(_ffprobe, path):
            return {"path": str(path), "name": Path(path).name, "kind": "image",
                    "duration": 0.0, "width": 320, "height": 180, "fps": 0.0,
                    "has_video": True, "has_audio": False, "codec": "png"}

        out = self.root / "background-mix"
        with mock.patch.object(env_mod, "find_install", return_value=None), \
                mock.patch.object(env_mod, "find_ffmpeg",
                                  return_value={"ffmpeg": None, "ffprobe": None}), \
                mock.patch.object(draft_mod.media_mod, "probe_media", side_effect=fake_probe):
            result = draft_mod.build(plan, out, make_cover=False)
        document = json.loads((out / "draft_info.json").read_text("utf-8"))
        self.assertEqual(len(document["materials"]["canvases"]), 1)
        self.assertEqual(document["materials"]["canvases"][0]["type"], "canvas_color")
        self.assertEqual(document["materials"]["canvases"][0]["color"], "#11223344")
        mix_modes = [item for item in document["materials"]["effects"]
                     if item.get("type") == "mix_mode"]
        self.assertEqual(len(mix_modes), 1)
        self.assertEqual(mix_modes[0]["name"], "滤色")
        self.assertEqual(mix_modes[0]["type"], "mix_mode")
        self.assertEqual(result["materials"].get("canvases"), 1)
        effects = [item for item in document["materials"]["effects"]
                   if item.get("type") == "mix_mode"]
        self.assertEqual(len(effects), 1)
        info = draft_mod.inspect(out)
        self.assertEqual([item["type"] for item in info["video_extras"]],
                         ["background_fill", "mix_mode"])

    def test_video_extras_wire_mask_curve_color_crop_flip_reverse(self):
        plan = self.root / "extras-plan.json"
        write_json(plan, {
            "schema": "jianying-plan/v1",
            "canvas": {"width": 640, "height": 360, "fps": 30},
            "tracks": [{"type": "video", "segments": [{
                "path": "main.mp4", "start": 0, "duration": 1.0,
                "crop": {"x": 0.1, "y": 0.2, "w": 0.7, "h": 0.6},
                "flip": {"horizontal": True, "vertical": False},
                "reverse": True,
                "mask": {"resource_type": "line", "name": "线性",
                         "resource_id": "123456", "path": "C:/cache/mask",
                         "config": {"width": 0.5}},
                "curve_speed": {"name": "先慢后快",
                                "points": [{"x": 0, "y": 1}, {"x": 0.5, "y": 0.5},
                                           {"x": 1, "y": 2}]},
                "color_wheel": {"segment": "gamma", "red": 0.1, "green": -0.2,
                                "blue": 0.3, "hsl": True},
            }]}],
        })
        (self.root / "main.mp4").write_bytes(b"fixture")
        fake_probe = {
            "path": str(self.root / "main.mp4"), "name": "main.mp4",
            "kind": "video", "duration": 3.0, "width": 640, "height": 360,
            "fps": 30.0, "has_video": True, "has_audio": True, "codec": "h264",
        }
        out = self.root / "extras"
        with mock.patch.object(env_mod, "find_install", return_value=None), \
                mock.patch.object(env_mod, "find_ffmpeg",
                                  return_value={"ffmpeg": None, "ffprobe": None}), \
                mock.patch.object(draft_mod.media_mod, "probe_media",
                                  return_value=fake_probe):
            result = draft_mod.build(plan, out, make_cover=False)
        document = json.loads((out / "draft_info.json").read_text("utf-8"))
        segment = document["tracks"][0]["segments"][0]
        material = document["materials"]["videos"][0]
        self.assertEqual(material["crop"]["upper_left_x"], 0.1)
        self.assertAlmostEqual(material["crop"]["upper_right_x"], 0.8)
        self.assertTrue(segment["clip"]["flip"]["horizontal"])
        self.assertTrue(segment["reverse"])
        self.assertEqual(len(document["materials"]["common_mask"]), 1)
        self.assertEqual(len(document["materials"]["speeds"]), 1)
        self.assertEqual(len(document["materials"]["primary_color_wheels"]), 1)
        self.assertEqual(len(document["materials"]["hsl"]), 1)
        self.assertTrue(any("11.8" in str(item) for item in result["warnings"]))
        self.assertEqual(
            document["materials"]["speeds"][0]["curve_speed"]["speed_points"][1],
            {"x": 0.5, "y": 0.5})
        self.assertEqual(result["materials"].get("common_mask"), 1)
        self.assertEqual(result["materials"].get("speeds"), 1)
        material_ids = {
            item.get("id")
            for bucket in document["materials"].values()
            if isinstance(bucket, list)
            for item in bucket if isinstance(item, dict)
        }
        self.assertTrue(set(segment["extra_material_refs"]).issubset(material_ids))

    def test_mask_config_warning_covers_empty_and_incomplete(self):
        def run_case(name, config):
            plan = self.root / f"mask-{name}-plan.json"
            write_json(plan, {
                "schema": "jianying-plan/v1",
                "canvas": {"width": 320, "height": 180, "fps": 30},
                "tracks": [{"type": "video", "segments": [{
                    "path": "main.mp4", "start": 0, "duration": 1.0,
                    "mask": {"resource_type": "circle", "resource_id": "82432977",
                             "path": "C:/cache/mask", "config": config},
                }]}],
            })
            (self.root / "main.mp4").write_bytes(b"fixture")
            fake_probe = {
                "path": str(self.root / "main.mp4"), "name": "main.mp4",
                "kind": "video", "duration": 2.0, "width": 320, "height": 180,
                "fps": 30.0, "has_video": True, "has_audio": False, "codec": "h264",
            }
            out = self.root / f"mask-{name}"
            with mock.patch.object(env_mod, "find_install", return_value=None), \
                    mock.patch.object(env_mod, "find_ffmpeg",
                                      return_value={"ffmpeg": None, "ffprobe": None}), \
                    mock.patch.object(draft_mod.media_mod, "probe_media",
                                      return_value=fake_probe):
                return draft_mod.build(plan, out, make_cover=False), out

        empty, _ = run_case("empty", {})
        self.assertTrue(any("mask.config 为空" in str(item)
                            for item in empty["warnings"]), empty["warnings"])

        partial, partial_out = run_case("partial", {"width": 0.5})
        self.assertTrue(any("mask.config 字段不全" in str(item)
                            for item in partial["warnings"]), partial["warnings"])
        partial_doc = json.loads((partial_out / "draft_info.json").read_text("utf-8"))
        self.assertEqual(
            partial_doc["materials"]["common_mask"][0]["config"],
            {"width": 0.5},
            partial_doc["materials"]["common_mask"][0]["config"],
        )

        base = {
            "center_x": 0.5, "center_y": 0.5,
            "width": 0.5, "height": 0.5, "feather": 0.1,
        }
        for index, (field, value) in enumerate((
                ("center_x", "left"), ("center_y", -0.2),
                ("width", "wide"), ("width", 0),
                ("height", 0),
                ("center_x", True), ("center_x", "0.5"),
                ("width", "0.5"), ("feather", 2),
                ("width", 2.0), ("height", 2.0),
                ("center_y", -0.1), ("width", float("nan")),
                ("height", float("inf")))):
            config = dict(base)
            config[field] = value
            with self.subTest(field=field, value=value):
                case, out = run_case(
                    f"bad-{index}-{field}-{type(value).__name__}", config)
                self.assertTrue(
                    any(f"bad=['{field}']" in str(item)
                        for item in case["warnings"]),
                    (field, case["warnings"]),
                )
                document = json.loads((out / "draft_info.json").read_text("utf-8"))
                written = document["materials"]["common_mask"][0]["config"]
                self.assertNotIn(field, written, (field, written))
                for other in base:
                    if other != field:
                        self.assertIn(other, written, (field, written))

        unknown_case, unknown_out = run_case(
            "unknown", {**base, "extra_flag": 1})
        self.assertTrue(
            any("unknown=['extra_flag']" in str(item)
                for item in unknown_case["warnings"]),
            unknown_case["warnings"],
        )
        unknown_doc = json.loads((unknown_out / "draft_info.json").read_text("utf-8"))
        self.assertEqual(
            unknown_doc["materials"]["common_mask"][0]["config"], base)

        edges, edges_out = run_case("edges", {
            "center_x": 0, "center_y": 0,
            "width": 1.0, "height": 1, "feather": 0,
        })
        self.assertFalse(any("mask.config" in str(item)
                             for item in edges["warnings"]), edges["warnings"])
        edges_doc = json.loads((edges_out / "draft_info.json").read_text("utf-8"))
        self.assertEqual(
            edges_doc["materials"]["common_mask"][0]["config"],
            {"center_x": 0, "center_y": 0,
             "width": 1.0, "height": 1, "feather": 0},
        )

        feather_max, feather_out = run_case("feather-max", {
            "center_x": 0.5, "center_y": 0.5,
            "width": 0.5, "height": 0.5, "feather": 1.0,
        })
        self.assertFalse(any("mask.config" in str(item)
                             for item in feather_max["warnings"]),
                         feather_max["warnings"])
        feather_doc = json.loads((feather_out / "draft_info.json").read_text("utf-8"))
        self.assertEqual(
            feather_doc["materials"]["common_mask"][0]["config"],
            {"center_x": 0.5, "center_y": 0.5,
             "width": 0.5, "height": 0.5, "feather": 1.0},
        )

        full, out = run_case("full", base)
        self.assertFalse(any("mask.config" in str(item)
                             for item in full["warnings"]), full["warnings"])
        document = json.loads((out / "draft_info.json").read_text("utf-8"))
        self.assertEqual(document["materials"]["common_mask"][0]["config"],
                         {"center_x": 0.5, "center_y": 0.5,
                          "width": 0.5, "height": 0.5, "feather": 0.1})

    def test_video_extras_reject_invalid_shapes(self):
        cases = [
            ({"mask": {"resource_type": ""}}, "mask.resource_type"),
            ({"mask": {"resource_type": "line", "resource_id": "abc"}},
             "mask.resource_id"),
            ({"curve_speed": {"points": [[0, 1], [0.2, 1], [0.1, 2]]}},
             "curve_speed.points"),
            ({"crop": {"x": 0.8, "y": 0, "w": 0.3, "h": 1}}, "crop"),
            ({"color_wheel": {"segment": "nope"}}, "color_wheel.segment"),
            ({"reverse": "yes"}, "reverse"),
        ]
        for fields, marker in cases:
            with self.subTest(marker=marker):
                plan = self.root / f"bad-{marker.replace('.', '-')}.json"
                segment = {"path": "main.mp4", "start": 0, "duration": 1.0}
                segment.update(fields)
                write_json(plan, {
                    "schema": "jianying-plan/v1",
                    "tracks": [{"type": "video", "segments": [segment]}],
                })
                (self.root / "main.mp4").write_bytes(b"fixture")
                with mock.patch.object(env_mod, "find_install", return_value=None), \
                        mock.patch.object(env_mod, "find_ffmpeg",
                                          return_value={"ffmpeg": None, "ffprobe": None}), \
                        mock.patch.object(draft_mod.media_mod, "probe_media",
                                          return_value={
                                              "path": str(self.root / "main.mp4"),
                                              "name": "main.mp4", "kind": "video",
                                              "duration": 3.0, "width": 640,
                                              "height": 360, "fps": 30.0,
                                              "has_video": True, "has_audio": True,
                                              "codec": "h264"}):
                    with self.assertRaises(SkillError) as caught:
                        draft_mod.build(plan, self.root / f"out-{marker.replace('.', '-')}",
                                        make_cover=False)
                self.assertEqual(caught.exception.code, "VALIDATION")
                message = caught.exception.message
                self.assertIn(marker.split(".")[0], message)

    def test_image_rejects_curve_speed_reverse_and_matting(self):
        for field, value in (
                ("curve_speed", {"points": [[0, 1], [1, 1.5]]}),
                ("reverse", True),
                ("matting", {"path": str(self.root)})):
            with self.subTest(field=field):
                plan = self.root / f"bad-image-{field}.json"
                write_json(plan, {
                    "schema": "jianying-plan/v1",
                    "tracks": [{"type": "image", "segments": [{
                        "path": "cover.png", "start": 0, "duration": 1.0,
                        field: value,
                    }]}],
                })
                (self.root / "cover.png").write_bytes(b"fixture")
                fake_probe = {
                    "path": str(self.root / "cover.png"), "name": "cover.png",
                    "kind": "image", "duration": 3.0, "width": 640,
                    "height": 360, "fps": 0.0, "has_video": True,
                    "has_audio": False, "codec": "png"}
                with mock.patch.object(env_mod, "find_install", return_value=None), \
                        mock.patch.object(env_mod, "find_ffmpeg",
                                          return_value={"ffmpeg": None, "ffprobe": None}), \
                        mock.patch.object(draft_mod.media_mod, "probe_media",
                                          return_value=fake_probe):
                    with self.assertRaises(SkillError) as caught:
                        draft_mod.build(plan, self.root / f"out-image-{field}",
                                        make_cover=False)
                self.assertEqual(caught.exception.code, "VALIDATION")
                self.assertEqual(caught.exception.details.get("field"), field)


        plan = self.root / "text-extras.json"
        write_json(plan, {
            "schema": "jianying-plan/v1",
            "tracks": [{"type": "text", "segments": [{
                "text": "模板标题", "start": 0, "duration": 2,
                "text_template": {
                    "resource_id": "987654", "name": "划重点",
                    "path": "C:/cache/template",
                    "resources": [{"panel": "text", "resource_id": "111",
                                   "path": "C:/cache/panel"}],
                },
                "animations": [{"type": "in", "resource_id": "222",
                                "name": "渐显入场", "duration": 0.5,
                                "path": "C:/cache/anim"}],
            }]}],
        })
        out = self.root / "text-extras"
        with mock.patch.object(env_mod, "find_install", return_value=None), \
                mock.patch.object(env_mod, "find_ffmpeg",
                                  return_value={"ffmpeg": None, "ffprobe": None}):
            result = draft_mod.build(plan, out, make_cover=False)
        document = json.loads((out / "draft_info.json").read_text("utf-8"))
        segment = document["tracks"][0]["segments"][0]
        template = document["materials"]["text_templates"][0]
        self.assertEqual(segment["material_id"], template["id"])
        self.assertEqual(segment["render_index"], 14001)
        self.assertIn(document["materials"]["texts"][0]["id"],
                      segment["extra_material_refs"])
        self.assertEqual(template["resources"][0]["panel"], "text")
        self.assertEqual(len(document["materials"]["material_animations"]), 1)
        self.assertEqual(
            document["materials"]["material_animations"][0]["animations"][0]["type"],
            "in")
        self.assertEqual(result["materials"].get("text_templates"), 1)
        inspected = draft_mod.inspect(out)
        self.assertEqual(len(inspected["texts"]), 1)
        self.assertEqual(inspected["texts"][0]["text"], "模板标题")

    def test_text_template_wins_over_bubble_and_effect(self):
        plan = self.root / "text-template-priority.json"
        write_json(plan, {
            "schema": "jianying-plan/v1",
            "tracks": [{"type": "text", "segments": [{
                "text": "模板优先", "start": 0, "duration": 2,
                "text_template": {
                    "resource_id": "987654", "name": "划重点",
                    "path": "C:/cache/template",
                },
                "text_effect": {"resource_id": "flower-3",
                                "effect_id": "flower-e3"},
                "text_bubble": {"resource_id": "bubble-3",
                                "effect_id": "bubble-e3"},
            }]}],
        })
        out = self.root / "text-template-priority"
        with mock.patch.object(env_mod, "find_install", return_value=None), \
                mock.patch.object(env_mod, "find_ffmpeg",
                                  return_value={"ffmpeg": None, "ffprobe": None}):
            draft_mod.build(plan, out, make_cover=False)
        document = json.loads((out / "draft_info.json").read_text("utf-8"))
        segment = document["tracks"][0]["segments"][0]
        self.assertEqual(document["materials"].get("effects") or [], [])
        self.assertEqual(segment["extra_material_refs"], [
            document["materials"]["texts"][0]["id"]])

    def test_text_animation_rejects_bad_type(self):
        plan = self.root / "bad-animation.json"
        write_json(plan, {
            "schema": "jianying-plan/v1",
            "tracks": [{"type": "text", "segments": [{
                "text": "x", "start": 0, "duration": 1,
                "animations": [{"type": "bounce", "resource_id": "1"}],
            }]}],
        })
        with mock.patch.object(env_mod, "find_install", return_value=None), \
                mock.patch.object(env_mod, "find_ffmpeg",
                                  return_value={"ffmpeg": None, "ffprobe": None}):
            with self.assertRaises(SkillError) as caught:
                draft_mod.build(plan, self.root / "bad-animation-out",
                                make_cover=False)
        self.assertEqual(caught.exception.code, "VALIDATION")
        self.assertIn("animations", caught.exception.message)

    def test_text_style_background_shadow_bold_italic_underline_wired(self):
        plan = self.root / "text-style.json"
        write_json(plan, {
            "schema": "jianying-plan/v1",
            "tracks": [{"type": "text", "segments": [{
                "text": "样式", "start": 0, "duration": 2,
                "bold": True, "italic": True, "underline": True,
                "background": {"color": "#112233", "alpha": 0.6,
                               "round_radius": 0.2, "width": 0.5,
                               "height": 0.2},
                "shadow": {"color": "#000000", "alpha": 0.5,
                           "distance": 4, "diffuse": 12, "angle": -30},
            }]}],
        })
        out = self.root / "text-style"
        with mock.patch.object(env_mod, "find_install", return_value=None), \
                mock.patch.object(env_mod, "find_ffmpeg",
                                  return_value={"ffmpeg": None, "ffprobe": None}):
            draft_mod.build(plan, out, make_cover=False)
        document = json.loads((out / "draft_info.json").read_text("utf-8"))
        material = document["materials"]["texts"][0]
        content = json.loads(material["content"])
        style = content["styles"][0]
        self.assertTrue(style["bold"])
        self.assertTrue(style["italic"])
        self.assertTrue(style["underline"])
        self.assertEqual(material["background_color"], "#112233")
        self.assertAlmostEqual(material["background_alpha"], 0.6)
        self.assertAlmostEqual(material["background_horizontal_offset"], 0.0)
        self.assertTrue(material["has_shadow"])
        self.assertEqual(material["shadow_color"], "#000000")
        self.assertAlmostEqual(material["shadow_distance"], 4.0)
        self.assertIn(16, [material["check_flag"] & 16])
        self.assertIn(32, [material["check_flag"] & 32])

    def test_text_bubble_wins_over_text_effect(self):
        plan = self.root / "text-flower.json"
        write_json(plan, {
            "schema": "jianying-plan/v1",
            "tracks": [{"type": "text", "segments": [{
                "text": "花字", "start": 0, "duration": 2,
                "text_effect": {"resource_id": "flower-1",
                                "effect_id": "flower-e1"},
                "text_bubble": {"resource_id": "bubble-1",
                                "effect_id": "bubble-e1"},
            }]}],
        })
        out = self.root / "text-flower"
        with mock.patch.object(env_mod, "find_install", return_value=None), \
                mock.patch.object(env_mod, "find_ffmpeg",
                                  return_value={"ffmpeg": None, "ffprobe": None}):
            draft_mod.build(plan, out, make_cover=False)
        document = json.loads((out / "draft_info.json").read_text("utf-8"))
        segment = document["tracks"][0]["segments"][0]
        effects = document["materials"]["effects"]
        self.assertEqual({item["type"] for item in effects}, {"text_shape"})
        self.assertEqual(len(segment["extra_material_refs"]), 1)
        bubble = next(item for item in effects if item["type"] == "text_shape")
        self.assertEqual(bubble["effect_id"], "bubble-e1")
        self.assertEqual(bubble["resource_id"], "bubble-1")
        self.assertFalse(document["materials"].get("filters"))
        content = json.loads(document["materials"]["texts"][0]["content"])
        self.assertNotIn("effectStyle", content["styles"][0])

    def test_text_effect_resets_text_style(self):
        """花字接管外观时，文字颜色/描边/阴影应重置为默认值。"""
        plan = self.root / "text-flower-reset.json"
        write_json(plan, {
            "schema": "jianying-plan/v1",
            "tracks": [{"type": "text", "segments": [{
                "text": "重置", "start": 0, "duration": 2,
                "color": "#FF0000", "stroke_width": 5,
                "stroke_color": "#00FF00",
                "shadow": {"color": "#0000FF", "distance": 6},
                "text_effect": {"resource_id": "flower-2",
                                "effect_id": "flower-e2"},
            }]}],
        })
        out = self.root / "text-flower-reset"
        with mock.patch.object(env_mod, "find_install", return_value=None), \
                mock.patch.object(env_mod, "find_ffmpeg",
                                  return_value={"ffmpeg": None, "ffprobe": None}):
            draft_mod.build(plan, out, make_cover=False)
        document = json.loads((out / "draft_info.json").read_text("utf-8"))
        content = json.loads(document["materials"]["texts"][0]["content"])
        style = content["styles"][0]
        self.assertEqual(style["fill"]["content"]["solid"]["color"],
                         [1.0, 1.0, 1.0])
        self.assertEqual(style["strokes"], [])
        self.assertNotIn("shadows", style)
        self.assertEqual(style["effectStyle"]["id"], "flower-e2")

    def test_inspect_lists_text_effects(self):
        plan = self.root / "text-effects-inspect.json"
        write_json(plan, {
            "schema": "jianying-plan/v1",
            "tracks": [{"type": "text", "segments": [{
                "text": "气泡花字", "start": 0, "duration": 2,
                "text_effect": {"resource_id": "flower-9",
                                "effect_id": "flower-e9",
                                "path": "C:/cache/flower"},
                "text_bubble": {"resource_id": "bubble-9",
                                "effect_id": "bubble-e9",
                                "path": "C:/cache/bubble"},
            }]}],
        })
        out = self.root / "text-effects-inspect"
        with mock.patch.object(env_mod, "find_install", return_value=None), \
                mock.patch.object(env_mod, "find_ffmpeg",
                                  return_value={"ffmpeg": None, "ffprobe": None}):
            draft_mod.build(plan, out, make_cover=False)
        info = draft_mod.inspect(out)
        self.assertEqual({item["type"] for item in info["text_effects"]},
                         {"text_shape"})
        effect = next(item for item in info["text_effects"]
                      if item["type"] == "text_shape")
        self.assertEqual(effect["resource_id"], "bubble-9")
        self.assertEqual(effect["effect_id"], "bubble-e9")
        self.assertEqual(effect["text"], "气泡花字")

    def test_text_effect_and_glow_stack(self):
        """花字与发光是两种独立材质：effectStyle + bloom，可同时存在。"""
        plan = self.root / "text-effect-glow.json"
        write_json(plan, {
            "schema": "jianying-plan/v1",
            "tracks": [{"type": "text", "segments": [{
                "text": "叠加", "start": 0, "duration": 2,
                "text_effect": {"resource_id": "flower-1",
                                "effect_id": "flower-e1"},
                "text_glow": {"resource_id": "7202576698775179837",
                              "effect_id": "9762443",
                              "bloom_params": {"color": "#FFFFFF", "dir_x": 0.5,
                                               "dir_y": 0.5, "range": 0.2,
                                               "strength": 0.3}},
            }]}],
        })
        out = self.root / "text-effect-glow"
        with mock.patch.object(env_mod, "find_install", return_value=None), \
                mock.patch.object(env_mod, "find_ffmpeg",
                                  return_value={"ffmpeg": None, "ffprobe": None}):
            draft_mod.build(plan, out, make_cover=False)
        document = json.loads((out / "draft_info.json").read_text("utf-8"))
        effects = document["materials"]["effects"]
        self.assertEqual({item["type"] for item in effects},
                         {"text_effect", "bloom"})
        glow = next(item for item in effects if item["type"] == "bloom")
        self.assertEqual(glow["panel_id"], "text_glow")
        self.assertEqual(glow["value"], 0.0)
        self.assertEqual(glow["effect_id"], "9762443")
        self.assertEqual(glow["resource_id"], "7202576698775179837")
        self.assertEqual(glow["bloom_params"]["range"], 0.2)
        self.assertEqual(glow["bloom_params"]["strength"], 0.3)
        text_material = document["materials"]["texts"][0]
        self.assertEqual(text_material["check_flag"] & 64, 64)
        content = json.loads(text_material["content"])
        self.assertEqual(content["styles"][0]["effectStyle"]["id"], "flower-e1")
        info = draft_mod.inspect(out)
        self.assertIn("bloom", {item["type"] for item in info["text_effects"]})

    def test_hsl_and_chroma_wire_materials_and_refs(self):
        plan = self.root / "hsl-chroma.json"
        write_json(plan, {
            "schema": "jianying-plan/v1",
            "tracks": [{"type": "video", "segments": [{
                "path": "main.mp4", "start": 0, "duration": 1.0,
                "hsl": [{"color": "red", "hue": 10, "saturation": -20},
                        {"color": "blue", "lightness": 30}],
                "chroma": {"color": "#00FF00FF", "intensity": 20,
                           "shadow": 2, "edge_smooth": 1, "spill": 0},
            }]}],
        })
        (self.root / "main.mp4").write_bytes(b"fixture")
        fake_probe = {"path": str(self.root / "main.mp4"), "name": "main.mp4",
                      "kind": "video", "duration": 3.0, "width": 640,
                      "height": 360, "fps": 30.0, "has_video": True,
                      "has_audio": True, "codec": "h264"}
        out = self.root / "hsl-chroma"
        with mock.patch.object(env_mod, "find_install", return_value=None), \
                mock.patch.object(env_mod, "find_ffmpeg",
                                  return_value={"ffmpeg": None, "ffprobe": None}), \
                mock.patch.object(draft_mod.media_mod, "probe_media",
                                  return_value=fake_probe):
            result = draft_mod.build(plan, out, make_cover=False)
        document = json.loads((out / "draft_info.json").read_text("utf-8"))
        segment = document["tracks"][0]["segments"][0]
        self.assertEqual(len(document["materials"]["hsl"]), 2)
        self.assertTrue(segment["enable_hsl"])
        self.assertEqual(document["materials"]["hsl"][0]["hsl_color_type"], "red")
        self.assertEqual(document["materials"]["chromas"][0]["version"], "v2")
        self.assertEqual(document["materials"]["chromas"][0]["intensity_value"], 0.2)
        self.assertEqual(len(segment["extra_material_refs"]), 3)
        self.assertIn("hsl", result["materials"])
        self.assertIn("chromas", result["materials"])

    def test_audio_fade_and_effect_wire_materials(self):
        plan = self.root / "audio-fade.json"
        write_json(plan, {
            "schema": "jianying-plan/v1",
            "tracks": [{"type": "audio", "segments": [{
                "path": "bgm.m4a", "start": 0, "duration": 2.0,
                "audio_fade": {"in": 0.4, "out": 0.6},
                "audio_effect": {"resource_id": "tone-1", "name": "低音",
                                 "category_id": "tone",
                                 "params": {"pitch": 0.8}},
            }]}],
        })
        (self.root / "bgm.m4a").write_bytes(b"fixture")
        fake_probe = {"path": str(self.root / "bgm.m4a"), "name": "bgm.m4a",
                      "kind": "audio", "duration": 3.0, "width": 0,
                      "height": 0, "fps": 0.0, "has_video": False,
                      "has_audio": True, "codec": "aac"}
        out = self.root / "audio-fade"
        with mock.patch.object(env_mod, "find_install", return_value=None), \
                mock.patch.object(env_mod, "find_ffmpeg",
                                  return_value={"ffmpeg": None, "ffprobe": None}), \
                mock.patch.object(draft_mod.media_mod, "probe_media",
                                  return_value=fake_probe):
            draft_mod.build(plan, out, make_cover=False)
        document = json.loads((out / "draft_info.json").read_text("utf-8"))
        fade = document["materials"]["audio_fades"][0]
        self.assertEqual(fade["fade_in_duration"], 400_000)
        self.assertEqual(fade["fade_out_duration"], 600_000)
        self.assertEqual(document["materials"]["audio_effects"][0]["type"],
                         "audio_effect")
        self.assertEqual(
            document["materials"]["audio_effects"][0]["audio_adjust_params"][0]["name"],
            "pitch")
        self.assertEqual(len(document["tracks"][0]["segments"][0]
                             ["extra_material_refs"]), 2)

    def test_audio_fade_longer_than_clip_is_rejected(self):
        plan = self.root / "audio-fade-bad.json"
        write_json(plan, {
            "schema": "jianying-plan/v1",
            "tracks": [{"type": "audio", "segments": [{
                "path": "bgm.m4a", "start": 0, "duration": 1.0,
                "audio_fade": {"in": 0.7, "out": 0.7},
            }]}],
        })
        (self.root / "bgm.m4a").write_bytes(b"fixture")
        with mock.patch.object(env_mod, "find_install", return_value=None), \
                mock.patch.object(env_mod, "find_ffmpeg",
                                  return_value={"ffmpeg": None, "ffprobe": None}), \
                mock.patch.object(draft_mod.media_mod, "probe_media",
                                  return_value={
                                      "path": str(self.root / "bgm.m4a"),
                                      "name": "bgm.m4a", "kind": "audio",
                                      "duration": 3.0, "width": 0, "height": 0,
                                      "fps": 0.0, "has_video": False,
                                      "has_audio": True, "codec": "aac"}):
            with self.assertRaises(SkillError) as caught:
                draft_mod.build(plan, self.root / "audio-fade-bad-out",
                                make_cover=False)
        self.assertEqual(caught.exception.code, "VALIDATION")
        self.assertIn("audio_fade", caught.exception.message)

    def test_video_adjust_is_rejected_not_silently_ignored(self):
        plan = self.root / "adjust-bad.json"
        write_json(plan, {
            "schema": "jianying-plan/v1",
            "tracks": [{"type": "video", "segments": [{
                "path": "main.mp4", "start": 0, "duration": 1.0,
                "adjust": {"brightness": 10},
            }]}],
        })
        (self.root / "main.mp4").write_bytes(b"fixture")
        with mock.patch.object(env_mod, "find_install", return_value=None), \
                mock.patch.object(env_mod, "find_ffmpeg",
                                  return_value={"ffmpeg": None, "ffprobe": None}), \
                mock.patch.object(draft_mod.media_mod, "probe_media",
                                  return_value={
                                      "path": str(self.root / "main.mp4"),
                                      "name": "main.mp4", "kind": "video",
                                      "duration": 3.0, "width": 640,
                                      "height": 360, "fps": 30.0,
                                      "has_video": True, "has_audio": True,
                                      "codec": "h264"}):
            with self.assertRaises(SkillError) as caught:
                draft_mod.build(plan, self.root / "adjust-bad-out",
                                make_cover=False)
        self.assertEqual(caught.exception.code, "VALIDATION")
        self.assertIn("adjust", caught.exception.message)

    def test_text_only_build_does_not_require_install(self):
        """M-8：纯文字草稿不依赖剪映安装/ffprobe。"""
        plan = self.root / "text-only.json"
        write_json(plan, {
            "schema": "jianying-plan/v1",
            "tracks": [{"type": "text", "segments": [
                {"text": "只有文字", "start": 0, "duration": 2}]}],
        })
        with mock.patch.object(env_mod, "find_install",
                               side_effect=SkillError("没有安装", code="INSTALL_NOT_FOUND")), \
                mock.patch.object(env_mod, "find_ffmpeg",
                                  return_value={"ffmpeg": None, "ffprobe": None}):
            result = draft_mod.build(plan, self.root / "text-only-out", make_cover=False)
        self.assertEqual(result["tracks"]["text"], 1)

    def test_adjust_and_freeze_rejected_on_every_track_type(self):
        """H-1：字段级守卫必须在 text/audio/sticker/effect 也触发，不能只在视频段。"""
        specs = {
            "adjust": {"brightness": 10},
            "freeze": True,
        }
        base = {
            "text": {"text": "字幕", "start": 0, "duration": 1},
            "audio": {"path": "a.m4a", "start": 0, "duration": 1},
            "sticker": {"resource_id": "sticker-1", "start": 0, "duration": 1},
            "effect": {"resource_id": "555", "start": 0, "duration": 1},
        }
        (self.root / "a.m4a").write_bytes(b"fixture")

        def fake_probe(_ffprobe, path):
            return {"path": str(path), "name": Path(path).name, "kind": "audio",
                    "duration": 3.0, "width": 0, "height": 0, "fps": 0.0,
                    "has_video": False, "has_audio": True, "codec": "aac"}

        with mock.patch.object(env_mod, "find_install", return_value=None), \
                mock.patch.object(env_mod, "find_ffmpeg",
                                  return_value={"ffmpeg": None, "ffprobe": None}), \
                mock.patch.object(draft_mod.media_mod, "probe_media",
                                  side_effect=fake_probe):
            for field, value in specs.items():
                for kind in base:
                    with self.subTest(field=field, kind=kind):
                        plan = self.root / f"unwired-{field}-{kind}.json"
                        segment = dict(base[kind])
                        segment[field] = value
                        write_json(plan, {
                            "schema": "jianying-plan/v1",
                            "tracks": [{"type": kind, "segments": [segment]}],
                        })
                        with self.assertRaises(SkillError) as caught:
                            draft_mod.build(plan, self.root / f"unwired-{field}-{kind}-out",
                                            make_cover=False)
                        self.assertEqual(caught.exception.code, "VALIDATION")
                        self.assertEqual(caught.exception.details.get("field"), field)
                        self.assertEqual(caught.exception.details.get("track_type"), kind)

    def test_native_escape_hatch_writes_bucket_and_refs(self):
        plan = self.root / "native.json"
        write_json(plan, {
            "schema": "jianying-plan/v1",
            "tracks": [{"type": "text", "segments": [{
                "text": "原生", "start": 0, "duration": 2,
                "native": {
                    "material": {"custom_flag": True},
                    "materials": [{"bucket": "video_shadows",
                                   "value": {"type": "video_shadow",
                                             "shadow_alpha": 0.2}}],
                },
            }]}],
        })
        out = self.root / "native"
        with mock.patch.object(env_mod, "find_install", return_value=None), \
                mock.patch.object(env_mod, "find_ffmpeg",
                                  return_value={"ffmpeg": None, "ffprobe": None}):
            draft_mod.build(plan, out, make_cover=False)
        document = json.loads((out / "draft_info.json").read_text("utf-8"))
        material = document["materials"]["texts"][0]
        self.assertTrue(material["custom_flag"])
        shadow = document["materials"]["video_shadows"][0]
        self.assertEqual(shadow["type"], "video_shadow")
        self.assertIn(shadow["id"],
                      document["tracks"][0]["segments"][0]["extra_material_refs"])

    def test_native_escape_hatch_rejects_structural_keys(self):
        plan = self.root / "native-bad.json"
        write_json(plan, {
            "schema": "jianying-plan/v1",
            "tracks": [{"type": "text", "segments": [{
                "text": "坏", "start": 0, "duration": 2,
                "native": {"segment": {"material_id": "x"}},
            }]}],
        })
        with mock.patch.object(env_mod, "find_install", return_value=None), \
                mock.patch.object(env_mod, "find_ffmpeg",
                                  return_value={"ffmpeg": None, "ffprobe": None}):
            with self.assertRaises(SkillError) as caught:
                draft_mod.build(plan, self.root / "native-bad-out",
                                make_cover=False)
        self.assertEqual(caught.exception.code, "VALIDATION")
        self.assertIn("material_id", caught.exception.message)

    def test_native_guards_cover_render_index_and_material_ids(self):
        """M-1：native 不能改 render_index/local_material_id，且显式 id 不能重复。"""
        cases = {
            "render_index": {"native": {"segment": {"render_index": 999}}},
            "local_material_id": {"native": {"material": {"local_material_id": "x"}}},
            "duplicate": {"native": {"materials": [
                {"bucket": "video_shadows",
                 "value": {"id": "dup-id", "type": "video_shadow"}},
                {"bucket": "video_shadows",
                 "value": {"id": "dup-id", "type": "video_shadow"}},
            ]}},
        }
        with mock.patch.object(env_mod, "find_install", return_value=None), \
                mock.patch.object(env_mod, "find_ffmpeg",
                                  return_value={"ffmpeg": None, "ffprobe": None}):
            for marker, native in cases.items():
                with self.subTest(marker=marker):
                    plan = self.root / f"native-guard-{marker}.json"
                    segment = {"text": "x", "start": 0, "duration": 1, **native}
                    write_json(plan, {
                        "schema": "jianying-plan/v1",
                        "tracks": [{"type": "text", "segments": [segment]}],
                    })
                    with self.assertRaises(SkillError) as caught:
                        draft_mod.build(plan, self.root / f"native-guard-{marker}-out",
                                        make_cover=False)
                    self.assertEqual(caught.exception.code, "VALIDATION")
                    if marker == "duplicate":
                        self.assertIn("重复", caught.exception.message)
                    else:
                        self.assertEqual(caught.exception.details.get("field"), marker)

    def test_unknown_segment_key_warns_instead_of_silent_drop(self):
        """L-6：拼错的字段不能既返回 ok 又零提示。"""
        plan = self.root / "unknown-key.json"
        write_json(plan, {
            "schema": "jianying-plan/v1",
            "tracks": [{"type": "text", "segments": [
                {"text": "x", "start": 0, "duration": 1,
                 "adjusts": {"brightness": 10}}]}],
        })
        with mock.patch.object(env_mod, "find_install", return_value=None), \
                mock.patch.object(env_mod, "find_ffmpeg",
                                  return_value={"ffmpeg": None, "ffprobe": None}):
            result = draft_mod.build(plan, self.root / "unknown-key-out",
                                     make_cover=False)
        self.assertTrue(any("adjusts" in str(item) for item in result["warnings"]))

    def test_sticker_track_writes_material_and_segment(self):
        plan = self.root / "sticker-plan.json"
        write_json(plan, {
            "schema": "jianying-plan/v1",
            "tracks": [{"type": "sticker", "segments": [{
                "resource_id": "8c1d-uuid", "path": "C:/cache/sticker",
                "start": 0.5, "duration": 2, "scale": 0.3, "x": 0.1, "y": -0.2,
            }]}],
        })
        out = self.root / "sticker"
        with mock.patch.object(env_mod, "find_install", return_value=None), \
                mock.patch.object(env_mod, "find_ffmpeg",
                                  return_value={"ffmpeg": None, "ffprobe": None}):
            result = draft_mod.build(plan, out, make_cover=False)
        document = json.loads((out / "draft_info.json").read_text("utf-8"))
        track = document["tracks"][0]
        self.assertEqual(track["type"], "sticker")
        segment = track["segments"][0]
        self.assertEqual(segment["render_index"], 14000)
        self.assertEqual(segment["clip"]["scale"], {"x": 0.3, "y": 0.3})
        material = document["materials"]["stickers"][0]
        self.assertEqual(material["resource_id"], "8c1d-uuid")
        self.assertEqual(segment["material_id"], material["id"])
        self.assertEqual(result["materials"].get("stickers"), 1)

    def test_effect_track_writes_video_effect_material(self):
        plan = self.root / "effect-plan.json"
        write_json(plan, {
            "schema": "jianying-plan/v1",
            "tracks": [{"type": "effect", "segments": [{
                "resource_id": "555", "name": "星火", "path": "C:/cache/effect/555",
                "start": 0.2, "duration": 2.0, "value": 0.8,
                "adjust_params": {"intensity": 0.5},
            }]}],
        })
        out = self.root / "effect"
        with mock.patch.object(env_mod, "find_install", return_value=None), \
                mock.patch.object(env_mod, "find_ffmpeg",
                                  return_value={"ffmpeg": None, "ffprobe": None}):
            result = draft_mod.build(plan, out, make_cover=False)
        document = json.loads((out / "draft_info.json").read_text("utf-8"))
        track = document["tracks"][0]
        self.assertEqual(track["type"], "effect")
        self.assertEqual(track["attribute"], 0)
        self.assertEqual(track["flag"], 0)
        segment = track["segments"][0]
        self.assertEqual(segment["render_index"], 11000)
        self.assertEqual(segment["target_timerange"],
                         {"duration": 2_000_000, "start": 200_000})
        material = document["materials"]["video_effects"][0]
        self.assertEqual(material["resource_id"], "555")
        self.assertEqual(material["apply_target_type"], 2)
        self.assertEqual(material["adjust_params"][0]["name"], "intensity")
        self.assertEqual(result["materials"].get("video_effects"), 1)

    def test_matting_requires_path_and_writes_video_material(self):
        matting_dir = self.root / "matting-frames"
        matting_dir.mkdir()
        plan = self.root / "matting-plan.json"
        write_json(plan, {
            "schema": "jianying-plan/v1",
            "tracks": [{"type": "video", "segments": [{
                "path": "main.mp4", "start": 0, "duration": 1.0,
                "matting": {"path": str(matting_dir), "reverse": True,
                            "feather": 0.1, "expansion": 0.02},
            }]}],
        })
        (self.root / "main.mp4").write_bytes(b"fixture")
        fake_probe = {"path": str(self.root / "main.mp4"), "name": "main.mp4",
                      "kind": "video", "duration": 3.0, "width": 640,
                      "height": 360, "fps": 30.0, "has_video": True,
                      "has_audio": True, "codec": "h264"}
        out = self.root / "matting"
        with mock.patch.object(env_mod, "find_install", return_value=None), \
                mock.patch.object(env_mod, "find_ffmpeg",
                                  return_value={"ffmpeg": None, "ffprobe": None}), \
                mock.patch.object(draft_mod.media_mod, "probe_media",
                                  return_value=fake_probe):
            result = draft_mod.build(plan, out, make_cover=False)
        document = json.loads((out / "draft_info.json").read_text("utf-8"))
        matting = document["materials"]["videos"][0]["matting"]
        self.assertEqual(matting["mask_video_path"], str(matting_dir))
        self.assertTrue(matting["reverse"])
        self.assertEqual(matting["feather"], 0.1)

    def test_matting_without_path_is_rejected(self):
        plan = self.root / "matting-bad.json"
        write_json(plan, {
            "schema": "jianying-plan/v1",
            "tracks": [{"type": "video", "segments": [{
                "path": "main.mp4", "start": 0, "duration": 1.0,
                "matting": {"reverse": True},
            }]}],
        })
        (self.root / "main.mp4").write_bytes(b"fixture")
        with mock.patch.object(env_mod, "find_install", return_value=None), \
                mock.patch.object(env_mod, "find_ffmpeg",
                                  return_value={"ffmpeg": None, "ffprobe": None}), \
                mock.patch.object(draft_mod.media_mod, "probe_media",
                                  return_value={
                                      "path": str(self.root / "main.mp4"),
                                      "name": "main.mp4", "kind": "video",
                                      "duration": 3.0, "width": 640,
                                      "height": 360, "fps": 30.0,
                                      "has_video": True, "has_audio": True,
                                      "codec": "h264"}):
            with self.assertRaises(SkillError) as caught:
                draft_mod.build(plan, self.root / "matting-bad-out",
                                make_cover=False)
        self.assertEqual(caught.exception.code, "VALIDATION")
        self.assertIn("matting", caught.exception.message)

    def test_audio_channel_writes_sound_channel_mapping(self):
        plan = self.root / "channel-plan.json"
        write_json(plan, {
            "schema": "jianying-plan/v1",
            "tracks": [{"type": "audio", "segments": [{
                "path": "bgm.m4a", "start": 0, "duration": 1.0, "channel": 2,
            }]}],
        })
        (self.root / "bgm.m4a").write_bytes(b"fixture")
        fake_probe = {"path": str(self.root / "bgm.m4a"), "name": "bgm.m4a",
                      "kind": "audio", "duration": 3.0, "width": 0,
                      "height": 0, "fps": 0.0, "has_video": False,
                      "has_audio": True, "codec": "aac"}
        out = self.root / "channel"
        with mock.patch.object(env_mod, "find_install", return_value=None), \
                mock.patch.object(env_mod, "find_ffmpeg",
                                  return_value={"ffmpeg": None, "ffprobe": None}), \
                mock.patch.object(draft_mod.media_mod, "probe_media",
                                  return_value=fake_probe):
            result = draft_mod.build(plan, out, make_cover=False)
        document = json.loads((out / "draft_info.json").read_text("utf-8"))
        self.assertEqual(len(document["materials"]["sound_channel_mappings"]), 1)
        self.assertEqual(
            document["materials"]["sound_channel_mappings"][0]["audio_channel_mapping"],
            2)
        self.assertEqual(result["materials"].get("sound_channel_mappings"), 1)

    def test_failed_force_build_keeps_previous_draft(self):
        out = self.root / "draft"
        self.build(out)
        before = (out / "draft_info.json").read_bytes()
        bad = self.root / "bad-plan.json"
        write_json(bad, {
            "schema": "jianying-plan/v1",
            "tracks": [{"type": "text", "segments": [
                {"text": "   ", "start": 0, "duration": 1}]}],
        })
        with mock.patch.object(env_mod, "find_install", return_value=None), \
                mock.patch.object(env_mod, "find_ffmpeg",
                                  return_value={"ffmpeg": None, "ffprobe": None}):
            with self.assertRaises(SkillError) as caught:
                draft_mod.build(bad, out, force=True, make_cover=False)
        self.assertEqual(caught.exception.code, "VALIDATION")
        self.assertEqual((out / "draft_info.json").read_bytes(), before)

    def test_build_and_inspect_text_draft(self):
        out = self.root / "draft"
        result = self.build(out)
        self.assertEqual(result["duration"], 4.4)
        self.assertEqual(result["tracks"]["text"], 1)
        self.assertTrue((out / ".jianying-skill.json").is_file())

        info = draft_mod.inspect(out)
        self.assertEqual(info["name"], "离线测试草稿")
        self.assertEqual(info["canvas"], {"width": 1080, "height": 1920})
        self.assertEqual(info["duration"], 4.4)
        self.assertEqual([item["text"] for item in info["texts"]], ["第一句", "第二句"])
        self.assertEqual(info["missing_media"], [])

    def test_unowned_nonempty_directory_is_refused(self):
        out = self.root / "occupied"
        out.mkdir()
        (out / "keep.txt").write_text("user data", "utf-8")
        with self.assertRaises(SkillError) as caught:
            self.build(out)
        self.assertEqual(caught.exception.code, "OUTPUT_NOT_EMPTY")
        self.assertEqual((out / "keep.txt").read_text("utf-8"), "user data")

    def test_rebuild_requires_force_and_backs_up(self):
        out = self.root / "draft"
        self.build(out)
        before = (out / "draft_info.json").read_bytes()
        with self.assertRaises(SkillError) as caught:
            self.build(out)
        self.assertEqual(caught.exception.code, "OUTPUT_EXISTS")
        self.assertEqual((out / "draft_info.json").read_bytes(), before)

        force_result = self.build(out, force=True)
        previous = force_result.get("previous")
        # 旧草稿整体保留为兄弟目录，不在失败或覆盖时静默删除
        self.assertIsNotNone(previous)
        self.assertTrue(Path(previous).is_dir())
        self.assertEqual((Path(previous) / "draft_info.json").read_bytes(), before)
        self.assertTrue((out / "draft_info.json").is_file())

    def test_patch_copy_then_in_place_backup(self):
        out = self.root / "draft"
        self.build(out)
        original = (out / "draft_info.json").read_bytes()
        (out / "draft_content.json").write_bytes(b'{"unique":"runtime"}')
        ops = self.root / "ops.json"
        write_json(ops, {"ops": [
            {"op": "set_text", "segment": 0, "text": "改过的第一句"},
            {"op": "shift", "segment": 1, "start": 2.6},
        ]})

        copy = self.root / "draft-copy"
        result = draft_mod.patch(out, ops, copy)
        self.assertFalse(result["in_place"])
        self.assertEqual(result["backups"], [])
        self.assertEqual([item["text"] for item in draft_mod.inspect(copy)["texts"]],
                         ["改过的第一句", "第二句"])
        self.assertEqual((copy / "draft_content.json").read_bytes(),
                         b'{"unique":"runtime"}')
        self.assertEqual((out / "draft_info.json").read_bytes(), original)

        result = draft_mod.patch(out, ops, None, in_place=True)
        self.assertTrue(result["in_place"])
        self.assertEqual(len(result["backups"]), 2)
        for backup in result["backups"]:
            self.assertTrue(Path(backup).is_file())

    def test_patch_failure_leaves_no_partial_copy(self):
        out = self.root / "draft"
        self.build(out)
        ops = self.root / "bad-ops.json"
        write_json(ops, {"ops": [{"op": "shift", "segment": 0, "start": -1}]})
        copy = self.root / "failed-copy"
        with self.assertRaises(SkillError) as caught:
            draft_mod.patch(out, ops, copy)
        self.assertEqual(caught.exception.code, "VALIDATION")
        self.assertFalse(copy.exists())
        self.assertEqual([path.name for path in self.root.iterdir()
                          if path.name.startswith(".tmp-")], [])

    def test_add_subtitles_rejects_unwired_style_and_keeps_caption_template(self):
        out = self.root / "draft"
        self.build(out)
        srt = self.root / "subs.srt"
        srt.write_text(
            "1\n00:00:00,000 --> 00:00:01,000\n第一句\n\n"
            "2\n00:00:01,200 --> 00:00:02,000\n第二句\n", "utf-8")
        bad_ops = self.root / "bad-sub-ops.json"
        write_json(bad_ops, {"ops": [{
            "op": "add_subtitles", "srt": "subs.srt",
            "style": {"text_template": {"resource_id": "1"}},
        }]})
        bad_copy = self.root / "bad-sub-copy"
        with self.assertRaises(SkillError) as caught:
            draft_mod.patch(out, bad_ops, bad_copy)
        self.assertEqual(caught.exception.code, "VALIDATION")
        self.assertIn("text_template", caught.exception.details["unsupported"])
        self.assertFalse(bad_copy.exists())

        ops = self.root / "sub-ops.json"
        write_json(ops, {"ops": [{
            "op": "add_subtitles", "srt": "subs.srt",
            "style": {
                "caption_template": {"resource_id": "7369552920146119974",
                                     "path": "C:/tmpl"},
                "font_size": 8, "y": -0.72,
            },
        }]})
        copy = self.root / "sub-copy"
        draft_mod.patch(out, ops, copy)
        document = json.loads((copy / "draft_info.json").read_text("utf-8"))
        track = next(track for track in document["tracks"]
                     if track.get("type") == "text" and track.get("name") == "字幕")
        self.assertEqual(len(track["segments"]), 2)
        self.assertTrue(all(segment.get("caption_info") for segment in track["segments"]))
        material = next(item for item in document["materials"]["texts"]
                        if item.get("caption_template_info"))
        self.assertEqual(material["caption_template_info"]["resource_id"],
                         "7369552920146119974")
        self.assertEqual(material["recognize_text"], "第一句")
        listed = versions_mod.list_versions(copy)
        artifacts = listed["versions"][-1]["artifacts"]
        self.assertEqual(len(artifacts), 1)
        self.assertEqual(Path(copy / ".jianying-versions" / listed["versions"][-1]["id"]
                              / artifacts[0]["name"]).read_text("utf-8"),
                         srt.read_text("utf-8"))

    def test_patch_ops_cover_all_documented_operations(self):
        out = self.root / "draft"
        self.build(out)
        ops = self.root / "all-ops.json"
        write_json(ops, {"ops": [
            {"op": "rename", "name": "全操作"},
            {"op": "set_canvas", "width": 720, "height": 1280},
            {"op": "fps", "value": 25},
            {"op": "set_text", "segment": 0, "text": "改字"},
            {"op": "set_style", "segment": 0, "font_size": 11, "color": "#00FF00",
             "stroke_color": "#000000", "stroke_width": 0.04, "align": "left"},
            {"op": "set_volume", "segment": 0, "volume": 0.4},
            {"op": "shift", "segment": 0, "start": 0.1},
            {"op": "set_transform", "segment": 0, "x": 0.1, "y": 0.2,
             "scale": 0.8, "rotation": 5, "opacity": 0.9},
            {"op": "remove", "segment": 1},
        ]})
        copy = self.root / "all-ops-draft"
        result = draft_mod.patch(out, ops, copy)
        self.assertEqual(len(result["ops"]), 9)
        info = draft_mod.inspect(copy)
        self.assertEqual(info["name"], "全操作")
        self.assertEqual(info["canvas"], {"width": 720, "height": 1280})
        self.assertEqual(info["fps"], 25)
        self.assertEqual(len(info["texts"]), 1)
        self.assertEqual(info["texts"][0]["text"], "改字")
        document = json.loads((copy / "draft_info.json").read_text("utf-8"))
        segment = document["tracks"][0]["segments"][0]
        self.assertAlmostEqual(segment["volume"], 0.4)
        self.assertAlmostEqual(segment["speed"], 1.0)
        self.assertAlmostEqual(segment["clip"]["scale"]["x"], 0.8)

    def test_patch_video_set_speed_and_trim_sync_source(self):
        plan = self.root / "video-plan.json"
        write_json(plan, {
            "schema": "jianying-plan/v1",
            "canvas": {"width": 640, "height": 360, "fps": 30},
            "tracks": [{"type": "video", "segments": [
                {"path": "main.mp4", "start": 0, "duration": 1.0}]}],
        })
        (self.root / "main.mp4").write_bytes(b"fixture")
        fake_probe = {
            "path": str(self.root / "main.mp4"), "name": "main.mp4",
            "kind": "video", "duration": 5.0, "width": 640, "height": 360,
            "fps": 30.0, "has_video": True, "has_audio": False, "codec": "h264",
        }
        out = self.root / "video-draft"
        with mock.patch.object(env_mod, "find_install", return_value=None), \
                mock.patch.object(env_mod, "find_ffmpeg",
                                  return_value={"ffmpeg": None, "ffprobe": None}), \
                mock.patch.object(draft_mod.media_mod, "probe_media",
                                  return_value=fake_probe):
            draft_mod.build(plan, out, make_cover=False)
        speed_ops = self.root / "video-speed.json"
        write_json(speed_ops, {"ops": [
            {"op": "set_speed", "segment": 0, "speed": 1.5}]})
        sped = self.root / "video-speed-copy"
        draft_mod.patch(out, speed_ops, sped)
        segment = json.loads(
            (sped / "draft_info.json").read_text("utf-8"))["tracks"][0]["segments"][0]
        self.assertAlmostEqual(segment["speed"], 1.5)
        self.assertEqual(segment["source_timerange"]["duration"], 1_500_000)

        trim_ops = self.root / "video-trim.json"
        write_json(trim_ops, {"ops": [
            {"op": "trim", "segment": 0, "duration": 0.8}]})
        trimmed = self.root / "video-trim-copy"
        draft_mod.patch(sped, trim_ops, trimmed)
        segment = json.loads(
            (trimmed / "draft_info.json").read_text("utf-8"))["tracks"][0]["segments"][0]
        self.assertEqual(segment["target_timerange"]["duration"], 800_000)
        self.assertEqual(segment["source_timerange"]["duration"], 1_200_000)

    def test_patch_text_speed_rejected_and_trim_keeps_source(self):
        out = self.root / "draft"
        self.build(out)
        speed_ops = self.root / "text-speed.json"
        write_json(speed_ops, {"ops": [
            {"op": "set_speed", "segment": 0, "speed": 1.5}]})
        with self.assertRaises(SkillError) as caught:
            draft_mod.patch(out, speed_ops, self.root / "speed-copy")
        self.assertEqual(caught.exception.code, "VALIDATION")
        self.assertEqual(caught.exception.details.get("field"), "speed")
        trim_ops = self.root / "text-trim.json"
        write_json(trim_ops, {"ops": [
            {"op": "trim", "segment": 0, "duration": 1.2}]})
        copy = self.root / "trim-copy"
        draft_mod.patch(out, trim_ops, copy)
        document = json.loads((copy / "draft_info.json").read_text("utf-8"))
        segment = document["tracks"][0]["segments"][0]
        self.assertEqual(segment["target_timerange"]["duration"], 1_200_000)
        self.assertEqual(segment["source_timerange"]["duration"], 2_000_000)

    def test_build_photo_only_without_canvas_warns(self):
        plan = self.root / "photo-plan.json"
        write_json(plan, {
            "schema": "jianying-plan/v1",
            "tracks": [{"type": "image", "segments": [
                {"path": "logo.png", "start": 0, "duration": 1.0}]}],
        })
        (self.root / "logo.png").write_bytes(b"fixture")
        fake_probe = {
            "path": str(self.root / "logo.png"), "name": "logo.png",
            "kind": "image", "duration": 0.0, "width": 1080, "height": 1920,
            "fps": 0.0, "has_video": True, "has_audio": False, "codec": "png",
        }
        out = self.root / "photo-draft"
        with mock.patch.object(env_mod, "find_install", return_value=None), \
                mock.patch.object(env_mod, "find_ffmpeg",
                                  return_value={"ffmpeg": None, "ffprobe": None}), \
                mock.patch.object(draft_mod.media_mod, "probe_media",
                                  return_value=fake_probe):
            result = draft_mod.build(plan, out, make_cover=False)
        self.assertTrue(any("1920×1080" in item for item in result["warnings"]))
        info = draft_mod.inspect(out)
        self.assertEqual(info["canvas"], {"width": 1920, "height": 1080})

    def test_inspect_accepts_utf8_bom_plaintext(self):
        out = self.root / "draft"
        self.build(out)
        info_path = out / "draft_info.json"
        info_path.write_bytes(b"\xef\xbb\xbf" + info_path.read_bytes())
        info = draft_mod.inspect(out)
        self.assertFalse(info["encrypted"])
        self.assertEqual(info["name"], "离线测试草稿")

    def test_patch_accepts_utf8_bom_draft(self):
        out = self.root / "draft"
        self.build(out)
        info_path = out / "draft_info.json"
        info_path.write_bytes(b"\xef\xbb\xbf" + info_path.read_bytes())
        ops = self.root / "bom-ops.json"
        write_json(ops, {"ops": [{"op": "rename", "name": "BOM 草稿"}]})
        copy = self.root / "bom-copy"
        draft_mod.patch(out, ops, copy)
        self.assertEqual(draft_mod.inspect(copy)["name"], "BOM 草稿")

    def test_build_fps_probe_fallback_warns(self):
        plan = self.root / "fps-plan.json"
        write_json(plan, {
            "schema": "jianying-plan/v1",
            "tracks": [{"type": "video", "segments": [
                {"path": "main.mp4", "start": 0, "duration": 1.0}]}],
        })
        (self.root / "main.mp4").write_bytes(b"fixture")
        fake_probe = {
            "path": str(self.root / "main.mp4"), "name": "main.mp4",
            "kind": "video", "duration": 5.0, "width": 640, "height": 360,
            "fps": 0.0, "has_video": True, "has_audio": False, "codec": "h264",
        }
        out = self.root / "fps-draft"
        with mock.patch.object(env_mod, "find_install", return_value=None), \
                mock.patch.object(env_mod, "find_ffmpeg",
                                  return_value={"ffmpeg": None, "ffprobe": None}), \
                mock.patch.object(draft_mod.media_mod, "probe_media",
                                  return_value=fake_probe):
            result = draft_mod.build(plan, out, make_cover=False)
        self.assertTrue(any("fps 不可用" in item for item in result["warnings"]))
        self.assertEqual(draft_mod.inspect(out)["fps"], 30.0)

    def test_remove_drops_extra_material_refs(self):
        document = {
            "tracks": [
                {"type": "video", "segments": [
                    {"id": "s1", "material_id": "m1",
                     "extra_material_refs": ["e1", "shared"]}]},
                {"type": "video", "segments": [
                    {"id": "s2", "material_id": "m2",
                     "extra_material_refs": ["shared"]}]},
            ],
            "materials": {
                "videos": [{"id": "m1"}, {"id": "m2"}],
                "texts": [{"id": "e1"}],
                "filters": [{"id": "shared"}],
            },
        }
        draft_mod._apply_op(document, {"op": "remove", "segment": 0})
        self.assertEqual([item["id"] for item in document["materials"]["videos"]],
                         ["m2"])
        self.assertEqual(document["materials"]["texts"], [])
        self.assertEqual([item["id"] for item in document["materials"]["filters"]],
                         ["shared"])

    def test_patch_trim_reports_keyframes_beyond_duration(self):
        plan = self.root / "kf-plan.json"
        write_json(plan, {
            "schema": "jianying-plan/v1",
            "canvas": {"width": 640, "height": 360, "fps": 30},
            "tracks": [{"type": "video", "segments": [{
                "path": "main.mp4", "start": 0, "duration": 2.0,
                "keyframes": {"scale": [[0, 1.0], [1.8, 1.2]]}}]}],
        })
        (self.root / "main.mp4").write_bytes(b"fixture")
        fake_probe = {
            "path": str(self.root / "main.mp4"), "name": "main.mp4",
            "kind": "video", "duration": 5.0, "width": 640, "height": 360,
            "fps": 30.0, "has_video": True, "has_audio": False, "codec": "h264",
        }
        out = self.root / "kf-draft"
        with mock.patch.object(env_mod, "find_install", return_value=None), \
                mock.patch.object(env_mod, "find_ffmpeg",
                                  return_value={"ffmpeg": None, "ffprobe": None}), \
                mock.patch.object(draft_mod.media_mod, "probe_media",
                                  return_value=fake_probe):
            draft_mod.build(plan, out, make_cover=False)
        ops = self.root / "kf-ops.json"
        write_json(ops, {"ops": [{"op": "trim", "segment": 0, "duration": 1.0}]})
        result = draft_mod.patch(out, ops, self.root / "kf-copy")
        self.assertTrue(any("关键帧超出新时长" in item
                            for item in result["ops"]))

    def test_inspect_reports_meta_consistency(self):
        out = self.root / "draft"
        self.build(out)
        meta_path = out / "draft_meta_info.json"
        meta = json.loads(meta_path.read_text("utf-8"))
        meta["draft_id"] = "OTHER-DRAFT-ID"
        write_json(meta_path, meta)
        info = draft_mod.inspect(out)
        self.assertFalse(info["consistency"]["meta"]["draft_id_match"])
        self.assertTrue(any("draft_id" in item for item in info["warnings"]))

    def test_publish_dry_run_does_not_write_index(self):
        out = self.root / "draft"
        self.build(out)
        draft_root = self.root / "draft-root"
        draft_root.mkdir()
        index_path = draft_root / "root_meta_info.json"
        write_json(index_path, {"all_draft_store": [], "draft_ids": 0})
        before = index_path.read_bytes()

        result = index_mod.publish(out, apply=False, draft_root=str(draft_root))
        self.assertTrue(result["dry_run"])
        self.assertEqual(result["action"], "copy+register")
        self.assertFalse(Path(result["target"]).exists())
        self.assertEqual(index_path.read_bytes(), before)

    def test_publish_apply_copies_and_registers(self):
        out = self.root / "draft"
        built = self.build(out)
        draft_root = self.root / "draft-root"
        draft_root.mkdir()
        index_path = draft_root / "root_meta_info.json"
        write_json(index_path, {"all_draft_store": [], "draft_ids": 0})

        result = index_mod.publish(out, apply=True, draft_root=str(draft_root))
        self.assertTrue(result["applied"])
        self.assertTrue(result["verified"])
        target = Path(result["target"])
        self.assertTrue((target / "draft_info.json").is_file())
        marker = json.loads((target / ".jianying-skill.json").read_text("utf-8"))
        self.assertEqual(marker["source_draft_id"], built["draft_id"])

        saved = json.loads(index_path.read_text("utf-8"))
        self.assertEqual(len(saved["all_draft_store"]), 1)
        self.assertEqual(len(saved["all_draft_store"][0]), len(index_mod.ENTRY_TEMPLATE))
        self.assertEqual(saved["draft_ids"], 1)
        self.assertTrue(Path(result["backup"]).is_file())

    def test_register_updates_existing_entry_instead_of_faking_unchanged(self):
        out = self.root / "draft"
        self.build(out)
        draft_root = self.root / "draft-root"
        draft_root.mkdir()
        index_path = draft_root / "root_meta_info.json"
        write_json(index_path, {"all_draft_store": [], "draft_ids": 0})
        first = index_mod.publish(out, apply=True, draft_root=str(draft_root))
        target = Path(first["target"])

        saved = json.loads(index_path.read_text("utf-8"))
        saved["all_draft_store"][0]["tm_draft_cloud_entry_id"] = 777
        saved["all_draft_store"][0]["cloud_custom_field"] = "keep-me"
        saved["all_draft_store"][0]["id_persisted"] = True
        saved["all_draft_store"][0]["draft_cover"] = "D:/some/cover.jpg"
        write_json(index_path, saved)

        info_path = target / "draft_info.json"
        document = json.loads(info_path.read_text("utf-8"))
        document["name"] = "更新后的草稿名"
        write_json(info_path, document)

        updated = index_mod.register(target, apply=True, draft_root=str(draft_root))
        self.assertEqual(updated["action"], "update")
        saved = json.loads(index_path.read_text("utf-8"))
        self.assertEqual(len(saved["all_draft_store"]), 1)
        self.assertEqual(saved["all_draft_store"][0]["draft_name"], "更新后的草稿名")
        self.assertEqual(saved["all_draft_store"][0]["tm_draft_cloud_entry_id"], 777)
        self.assertEqual(saved["all_draft_store"][0]["cloud_custom_field"], "keep-me")
        self.assertNotIn("id_persisted", saved["all_draft_store"][0])
        self.assertEqual(saved["all_draft_store"][0]["draft_cover"], "D:/some/cover.jpg")

    def test_publish_same_draft_does_not_create_numbered_copy(self):
        out = self.root / "draft"
        self.build(out)
        draft_root = self.root / "draft-root"
        draft_root.mkdir()
        index_path = draft_root / "root_meta_info.json"
        write_json(index_path, {"all_draft_store": [], "draft_ids": 0})
        first = index_mod.publish(out, apply=True, draft_root=str(draft_root))
        before = index_path.read_bytes()

        second = index_mod.publish(out, apply=True, draft_root=str(draft_root))
        self.assertEqual(second["action"], "already-registered")
        self.assertFalse(second["applied"])
        self.assertEqual(index_path.read_bytes(), before)
        self.assertFalse((draft_root / f"{Path(first['target']).name}-2").exists())

    def test_meta_missing_is_rejected_without_writing_index(self):
        out = self.root / "draft"
        self.build(out)
        (out / "draft_meta_info.json").unlink()
        draft_root = self.root / "draft-root"
        draft_root.mkdir()
        index_path = draft_root / "root_meta_info.json"
        write_json(index_path, {"all_draft_store": [], "draft_ids": 0})
        before = index_path.read_bytes()
        with self.assertRaises(SkillError) as caught:
            index_mod.publish(out, apply=True, draft_root=str(draft_root))
        self.assertEqual(caught.exception.code, "DRAFT_META_MISSING")
        self.assertEqual(index_path.read_bytes(), before)


class SafetyTests(unittest.TestCase):
    def test_output_guard(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "out.mp4"
            target.write_bytes(b"x")
            with self.assertRaises(SkillError) as caught:
                media_mod.ensure_output_path(target)
            self.assertEqual(caught.exception.code, "OUTPUT_EXISTS")
            self.assertEqual(media_mod.ensure_output_path(target, force=True), target.resolve())

    def test_number_rejects_nan_and_inf(self):
        for value in (math.nan, math.inf, -math.inf):
            with self.assertRaises(SkillError) as caught:
                draft_mod._number("duration", value)
            self.assertEqual(caught.exception.code, "VALIDATION")

    def test_backup_stamp_is_filename_safe_and_unique(self):
        stamps = {draft_mod._backup_stamp() for _ in range(20)}
        self.assertEqual(len(stamps), 20)
        for stamp in stamps:
            self.assertRegex(stamp, r"^\d{8}-\d{6}-\d{5}-[0-9a-f]{6}$")

    def test_atomic_json_write_cleans_staging_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "draft_info.json"
            with mock.patch.object(draft_mod.os, "replace",
                                   side_effect=OSError("simulated replace failure")):
                with self.assertRaises(SkillError) as caught:
                    draft_mod._write_json(target, {"ok": True})
            self.assertEqual(caught.exception.code, "OUTPUT_WRITE_FAILED")
            self.assertFalse(target.exists())
            self.assertEqual(list(Path(tmp).glob("*.tmp")), [])

    def test_timestamp_rejects_nan_negative_and_text(self):
        for value in (math.nan, math.inf, -1, "abc", None):
            with self.assertRaises(SkillError) as caught:
                media_mod.validate_timestamp(value)
            self.assertEqual(caught.exception.code, "VALIDATION")
        self.assertEqual(media_mod.validate_timestamp("1.5"), 1.5)

    def test_public_capabilities_strips_credentials(self):
        public = bridge_mod._public_capabilities({
            "video.export": True,
            "localServerToken": "secret",
            "session_cookie": "secret",
            "nested": {"token": "secret"},
            "build": 14778,
        })
        self.assertEqual(public, {"video.export": True, "build": 14778})

    def test_install_fingerprint_hashes_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            exe = root / "JianyingPro.exe"
            exe.write_bytes(b"exe")
            dll = root / "videoeditor.dll"
            dll.write_bytes(b"dll")
            fingerprint = env_mod.install_fingerprint(
                {"dir": str(root), "exe": str(exe), "version": "11.8.0"})
            self.assertEqual(fingerprint["exe_sha256"],
                             hashlib.sha256(b"exe").hexdigest())
            self.assertEqual(fingerprint["videoeditor"],
                             [{"name": "videoeditor.dll",
                               "sha256": hashlib.sha256(b"dll").hexdigest()}])
            self.assertEqual(env_mod.install_fingerprint(None),
                             {"exe_sha256": None, "videoeditor": []})

    def test_connect_retry_only_when_never_established(self):
        import urllib.error

        def make(reason, code="BRIDGE_UNREACHABLE"):
            exc = SkillError("x", code=code)
            exc.__cause__ = urllib.error.URLError(reason)
            return exc

        self.assertTrue(jy_mod._connect_never_established(
            make(ConnectionRefusedError())))
        self.assertTrue(jy_mod._connect_never_established(
            make(TimeoutError())))
        self.assertFalse(jy_mod._connect_never_established(
            make(OSError("reset"))))
        self.assertFalse(jy_mod._connect_never_established(
            make(ConnectionRefusedError(), code="BRIDGE_TIMEOUT")))

    def test_local_path_rejects_unc_and_urls(self):
        for value in (r"\\server\share\a.mp4", "//server/share/a.mp4",
                      "https://example.com/a.mp4", "file:///C:/a.mp4"):
            with self.assertRaises(SkillError) as caught:
                media_mod.local_path(value)
            self.assertEqual(caught.exception.code, "UNSAFE_PATH")
        self.assertEqual(media_mod.local_path("media/a.mp4"), Path("media/a.mp4"))

    def test_timeline_id_cannot_escape_draft(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "draft"
            timelines = root / "Timelines"
            timelines.mkdir(parents=True)
            outside = Path(tmp) / "outside" / "draft_info.json"
            outside.parent.mkdir()
            outside.write_text("{}", "utf-8")
            write_json(timelines / "project.json",
                       {"main_timeline_id": "../outside"})
            resolved = draft_mod.resolve_draft_info(root)
            self.assertIsNone(resolved["info_path"])
            self.assertEqual(resolved["layout"], "missing")

    def test_bridge_descriptor_validation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            descriptor = root / "infinite-canvas-native-bridge.json"
            write_json(descriptor, {"token": "ok", "port": "55639", "pid": 1})
            with mock.patch.object(env_mod, "_temp_dirs", return_value=[root]):
                found = env_mod.find_bridge_descriptor()
            self.assertIsNotNone(found)
            self.assertEqual(found["port"], 55639)
            self.assertEqual(found["origin"], "http://127.0.0.1:55639")

            write_json(descriptor, {"token": "bad\nvalue", "port": 55639})
            with mock.patch.object(env_mod, "_temp_dirs", return_value=[root]):
                self.assertIsNone(env_mod.find_bridge_descriptor())

            write_json(descriptor, {"token": "ok", "port": 70000})
            with mock.patch.object(env_mod, "_temp_dirs", return_value=[root]):
                self.assertIsNone(env_mod.find_bridge_descriptor())


    def test_is_plain_file_rejects_symlink(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            target = root / "real.bin"
            target.write_bytes(b"x")
            self.assertTrue(media_mod.is_plain_file(target))
            self.assertFalse(media_mod.is_plain_file(root / "missing.bin"))
            link = root / "link.bin"
            try:
                os.symlink(str(target), str(link))
            except (OSError, NotImplementedError):
                self.skipTest("本机不允许创建符号链接")
            self.assertFalse(media_mod.is_plain_file(link))
            self.assertFalse(draft_mod._plain_file(link))

    def test_is_plain_file_rejects_reparse_attribute(self):
        """目标自身是重解析点就拒绝；祖先目录走真实 lstat，避免空心断言。"""
        from types import SimpleNamespace

        with tempfile.TemporaryDirectory() as tmp:
            real = Path(tmp) / "real.bin"
            real.write_bytes(b"x")
            fake = SimpleNamespace(st_mode=real.lstat().st_mode,
                                   st_reparse_tag=0,
                                   st_file_attributes=media_mod._REPARSE_POINT)
            original = Path.lstat

            def lstat(self):
                if self == real:
                    return fake
                return original(self)

            with mock.patch.object(Path, "lstat", lstat):
                self.assertFalse(media_mod.is_plain_file(real))

    def test_is_link_stat_allows_cloud_placeholder_tag(self):
        """重解析属性位不够：只有 junction/符号链接标签才拒绝。"""
        from types import SimpleNamespace

        placeholder = SimpleNamespace(
            st_mode=0o100644, st_reparse_tag=0x9000001A,
            st_file_attributes=media_mod._REPARSE_POINT)
        self.assertFalse(media_mod._is_link_stat(placeholder))
        junction = SimpleNamespace(
            st_mode=0o040755, st_reparse_tag=media_mod._REPARSE_MOUNT,
            st_file_attributes=0)
        self.assertTrue(media_mod._is_link_stat(junction))

    def test_open_plain_holds_file_and_rejects_links(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            real = root / "real.bin"
            real.write_bytes(b"abc")
            with media_mod.open_plain(real) as fh:
                self.assertEqual(fh.read(), b"abc")
            self.assertEqual(media_mod.read_plain_bytes(real), b"abc")
            if os.name == "nt":
                with media_mod.hold_plain_file(real):
                    with self.assertRaises(OSError):
                        os.remove(real)
                self.assertTrue(real.exists())

    def test_is_plain_file_rejects_link_ancestor(self):
        """祖先目录是 junction 时，子文件也不能算普通文件。"""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            real = root / "real"
            real.mkdir()
            (real / "clip.bin").write_bytes(b"x")
            link = root / "junction"
            done = subprocess.run(["cmd", "/c", "mklink", "/J", str(link), str(real)],
                                  capture_output=True, text=True)
            if done.returncode != 0:
                self.skipTest(f"本机不能建 junction：{done.stderr.strip()[:120]}")
            self.assertTrue(media_mod.is_plain_file(real / "clip.bin"))
            self.assertFalse(media_mod.is_plain_file(link / "clip.bin"))
            self.assertFalse(media_mod.is_plain_dir(link))
            with self.assertRaises(OSError):
                with media_mod.open_plain(link):
                    pass
            entry = versions_mod._input_entry(root, str(link / "clip.bin"))
            self.assertFalse(entry["exists"])
            # 体积统计也不能跟着 junction 去读目标
            document = {"materials": {"videos": [
                {"path": str(link / "clip.bin")},
                {"path": str(real / "clip.bin")},
            ]}}
            self.assertEqual(draft_mod._materials_bytes(document, root), 1)
            self.assertEqual(index_mod._materials_bytes(document), 1)
            # 递归遍历也不能进入 junction
            self.assertEqual([p.name for p in media_mod.iter_plain_files(root)],
                             ["clip.bin"])

    def test_relink_prefix_strip_and_sibling_guard(self):
        if os.name != "nt":
            self.skipTest("前缀分隔符规则按 Windows 路径定义")
        self.assertEqual(maintenance_mod._strip_prefix(
            r"C:\media\clip.mp4", r"C:\media"), r"\clip.mp4")
        self.assertIsNone(maintenance_mod._strip_prefix(
            r"C:\media2\clip.mp4", r"C:\media"))
        self.assertIsNone(maintenance_mod._strip_prefix(
            r"C:\media\clip.mp4", r"D:\media"))
        self.assertEqual(maintenance_mod._strip_prefix(
            r"c:\MEDIA\clip.mp4", r"C:\media"), r"\clip.mp4")
        self.assertIsNone(maintenance_mod._strip_prefix(
            r"C:\media\..\Windows\win.ini", r"C:\media"))
        self.assertEqual(maintenance_mod._strip_prefix(
            r"C:\media\clip.mp4", "C:\\media\\"), "clip.mp4")
        self.assertEqual(maintenance_mod._join_prefix(
            "C:\\new\\", "\\clip.mp4"), "C:\\new\\clip.mp4")

    def test_prune_tolerates_extra_material_refs_dict(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            draft = root / "prune-dict"
            write_json(draft / "draft_info.json", {
                "id": "d", "duration": 2_000_000,
                "materials": {
                    "videos": [{"id": "V1", "path": "v.mp4", "duration": 2_000_000},
                               {"id": "ORPHAN", "path": "o.mp4"}],
                    "effects": [{"id": "FX2", "type": "mix_mode"}],
                },
                "tracks": [{"type": "video", "segments": [{
                    "id": "s1", "material_id": "V1",
                    "extra_material_refs": {"slot": "FX2"},
                    "target_timerange": {"start": 0, "duration": 2_000_000},
                }]}],
            })
            self.assertTrue(jy_mod._draft_material_present(
                draft / "draft_info.json", "effects", {"mix_mode"}))
            result = maintenance_mod.prune(draft, out_dir=root / "prune-dict-out")
            self.assertEqual(result["removed_count"], 1)
            self.assertEqual(result["removed"][0]["id"], "ORPHAN")
            document = json.loads(
                (Path(result["out"]) / "draft_info.json").read_text("utf-8"))
            self.assertEqual([item["id"]
                              for item in document["materials"]["effects"]], ["FX2"])

    def test_materials_bytes_counts_images_and_stickers(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for name, data in (("v.mp4", b"1"), ("i.png", b"22"), ("s.png", b"333")):
                (root / name).write_bytes(data)
            document = {"materials": {
                "videos": [{"path": str(root / "v.mp4")}],
                "images": [{"path": str(root / "i.png")}],
                "stickers": [{"path": str(root / "s.png")}],
            }}
            self.assertEqual(draft_mod._materials_bytes(document, root), 6)
            self.assertEqual(index_mod._materials_bytes(document), 6)

    def test_remove_op_normalizes_dict_refs(self):
        document = {
            "materials": {
                "videos": [{"id": "V1"}],
                "images": [{"id": "I1"}],
                "effects": [{"id": "FX2", "type": "mix_mode"},
                            {"id": "FX3", "type": "mix_mode"}],
            },
            "tracks": [{"type": "video", "segments": [
                {"id": "s1", "material_id": "V1",
                 "extra_material_refs": {"slot": "FX2"}},
                {"id": "s2", "material_id": "I1",
                 "extra_material_refs": ["FX3"]},
            ]}],
        }
        self.assertEqual(draft_mod._apply_op(
            document, {"op": "remove", "segment": "s1"}), "remove")
        self.assertEqual([s["id"] for s in document["tracks"][0]["segments"]],
                         ["s2"])
        self.assertEqual([m["id"] for m in document["materials"]["videos"]], [])
        self.assertEqual([m["id"] for m in document["materials"]["effects"]],
                         ["FX3"])

    def test_ref_values_keeps_numeric_ids(self):
        self.assertEqual(draft_mod._ref_values([123, "A", None, ""]),
                         {"123", "A"})
        self.assertEqual(draft_mod._ref_values({"a": "FX1", "b": 7}),
                         {"FX1", "7"})

    def test_inspect_reports_missing_image_material(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            draft = root / "inspect-images"
            write_json(draft / "draft_info.json", {
                "id": "d", "duration": 2_000_000,
                "canvas_config": {"width": 640, "height": 360},
                "materials": {"images": [{"id": "I1", "path": str(
                    root / "missing" / "cover.png")}]},
                "tracks": [{"type": "video", "segments": [{
                    "id": "s1", "material_id": "I1",
                    "target_timerange": {"start": 0, "duration": 2_000_000},
                }]}],
            })
            report = draft_mod.inspect(draft)
            self.assertTrue(any("cover.png" in path
                                for path in report["missing_media"]))

    def test_inspect_accepts_sticker_package_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            package = root / "cache" / "sticker" / "pkg"
            package.mkdir(parents=True)
            draft = root / "inspect-sticker"
            write_json(draft / "draft_info.json", {
                "id": "d", "duration": 1_000_000,
                "canvas_config": {"width": 640, "height": 360},
                "materials": {"stickers": [{"id": "S1", "path": str(package)}]},
                "tracks": [{"type": "video", "segments": [{
                    "id": "s1", "material_id": "S1",
                    "target_timerange": {"start": 0, "duration": 1_000_000},
                }]}],
            })
            report = draft_mod.inspect(draft)
            self.assertEqual(report["missing_media"], [])


class ManifestPathTests(unittest.TestCase):
    def test_manifest_paths_reject_escape(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "draft"
            root.mkdir()
            with self.assertRaises(SkillError) as caught:
                versions_mod._doc_at(root, {"snapshot": "../outside.json"})
            self.assertEqual(caught.exception.code, "VERSION_CORRUPTED")
            with self.assertRaises(SkillError):
                versions_mod._doc_at(
                    root, {"snapshot": str(Path(tmp) / "abs.json")})


class AllowHttpCliTests(unittest.TestCase):
    def test_parser_exposes_allow_http(self):
        parser = jy_mod.build_parser()
        build = parser.parse_args(
            ["build", "--plan", "p.json", "--out", "o",
             "--fetch-resources", "--allow-http"])
        self.assertTrue(build.allow_http)
        auto = parser.parse_args(
            ["auto-subtitles", "--video", "v.mp4", "--out", "o",
             "--fetch-resources", "--allow-http"])
        self.assertTrue(auto.allow_http)

    def test_commands_forward_allow_http(self):
        parser = jy_mod.build_parser()
        build_args = parser.parse_args(
            ["build", "--plan", "p.json", "--out", "o",
             "--fetch-resources", "--allow-http"])
        with mock.patch.object(jy_mod, "emit", return_value=None), \
                mock.patch.object(jy_mod.draft_mod, "build",
                                  return_value={"draft_dir": "o"}) as build:
            jy_mod.cmd_build(build_args)
        self.assertTrue(build.call_args.kwargs["allow_http"])
        auto_args = parser.parse_args(
            ["auto-subtitles", "--video", "v.mp4", "--out", "o",
             "--fetch-resources", "--allow-http"])
        with mock.patch.object(jy_mod, "emit", return_value=None), \
                mock.patch.object(jy_mod.workflow_mod, "build_subtitle_draft",
                                  return_value={"warnings": []}) as auto:
            jy_mod.cmd_auto_subtitles(auto_args)
        self.assertTrue(auto.call_args.kwargs["allow_http"])


class CliTests(unittest.TestCase):
    def test_bad_args_still_returns_json(self):
        proc = subprocess.run(
            [sys.executable, str(ROOT / "jy.py"), "render"],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=30,
        )
        self.assertEqual(proc.returncode, 2)
        payload = json.loads(proc.stdout)
        self.assertFalse(payload["ok"])
        self.assertEqual(payload["error"]["code"], "BAD_ARGS")

    def test_render_refuses_existing_output_before_bridge(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "existing.mp4"
            output.write_bytes(b"existing")
            proc = subprocess.run(
                [sys.executable, str(ROOT / "jy.py"), "render",
                 str(Path(tmp) / "missing-draft"), "-o", str(output)],
                capture_output=True, text=True, encoding="utf-8", errors="replace",
                timeout=30,
            )
            self.assertEqual(proc.returncode, 1)
            payload = json.loads(proc.stdout)
            self.assertEqual(payload["error"]["code"], "OUTPUT_EXISTS")
            self.assertEqual(output.read_bytes(), b"existing")

    def test_verify_rejects_non_numeric_frames(self):
        proc = subprocess.run(
            [sys.executable, str(ROOT / "jy.py"), "verify", "missing.mp4",
             "--frames", "0.5,abc"],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=30,
        )
        self.assertEqual(proc.returncode, 2)
        payload = json.loads(proc.stdout)
        self.assertFalse(payload["ok"])
        self.assertEqual(payload["error"]["code"], "BAD_ARGS")

    def test_check_skill_self_test(self):
        proc = subprocess.run(
            [sys.executable, str(ROOT / "check_skill.py"), "--self-test"],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=30,
        )
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        payload = json.loads(proc.stdout)
        self.assertTrue(payload["ok"])
        self.assertTrue(payload["self_test"])
        self.assertEqual(payload["checks"], 10)
        self.assertEqual(payload["failed"], 0)
        self.assertEqual(payload["failed_checks"], [])

    def test_check_skill_self_test_failure_returns_one(self):
        import importlib.util
        path = ROOT / "check_skill.py"
        spec = importlib.util.spec_from_file_location("_jy_check_skill", path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        with mock.patch.object(mod, "self_test", return_value=(False, 9, ["x"])), \
                mock.patch("builtins.print"):
            self.assertEqual(mod.main(["--self-test"]), 1)

    def test_check_skill_json_envelope(self):
        proc = subprocess.run(
            [sys.executable, str(ROOT / "check_skill.py"), "--json"],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=30,
        )
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        payload = json.loads(proc.stdout)
        self.assertTrue(payload["ok"])
        self.assertIsInstance(payload["failed"], int)
        self.assertEqual(payload["failed"], 0)
        self.assertIsInstance(payload["failed_checks"], list)
        self.assertEqual(payload["failed_checks"], [])


class BridgeTests(unittest.TestCase):
    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"
        seen_body = None

        def log_message(self, *_args):
            pass

        def _json(self, status, payload):
            raw = json.dumps(payload).encode("utf-8")
            self.send_response(status)
            self.send_header("content-type", "application/json")
            self.send_header("content-length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def _authorized(self):
            if self.headers.get("x-infinite-canvas-native-token") != "test-token":
                self._json(401, {"error": "bad token"})
                return False
            return True

        def do_GET(self):
            if not self._authorized():
                return
            if self.path == "/.infinite-canvas-native-bridge/health":
                self._json(200, {
                    "compatibility": {
                        "application": {"version": "11.8.0", "build": "14778"},
                        "capabilities": {"video.export": True,
                                         "localServerToken": "must-not-surface"},
                    },
                    "pid": 1234,
                    "application_path": r"C:\Apps\JianyingPro.exe",
                })
            elif self.path == "/custom-agent/context":
                self._json(200, {"authContext": {"principal": {"userId": "42"}}})
            else:
                self._json(404, {"error": "not found"})

        def do_POST(self):
            if not self._authorized():
                return
            length = int(self.headers.get("content-length", "0"))
            body = json.loads(self.rfile.read(length).decode("utf-8"))
            type(self).seen_body = body
            if self.path != "/custom-agent/film-export" or body.get("format") != "mp4":
                self._json(400, {"error": "bad request"})
                return
            output = Path(body["outputPath"])
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_bytes(b"fake mp4")
            self._json(200, {
                "ok": True,
                "path": str(output),
                "format": "mp4",
                "requestId": body["requestId"],
                "revision": body["revision"],
            })

    def setUp(self):
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), self.Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)
        port = self.server.server_address[1]
        self.bridge = bridge_mod.Bridge({
            "token": "test-token",
            "port": port,
            "origin": f"http://127.0.0.1:{port}",
        })

    def test_health_redacts_capability_secret(self):
        health = self.bridge.safe_health()
        self.assertEqual(health["version"], "11.8.0")
        self.assertEqual(health["capabilities"], {"video.export": True})
        self.assertNotIn("must-not-surface", json.dumps(health, ensure_ascii=False))

    def test_export_sends_scope_and_verifies_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            draft = Path(tmp) / "draft"
            draft.mkdir()
            (draft / "draft_info.json").write_text("{}", "utf-8")
            out = Path(tmp) / "out.mp4"
            result = self.bridge.export(draft, out, timeout_ms=1000)
            self.assertEqual(result["path"], str(out.resolve()))
            self.assertTrue(out.is_file())
            self.assertEqual(result["format"], "mp4")
            seen = self.Handler.seen_body
            self.assertEqual(seen["accountScope"], "uid:42")
            self.assertEqual(seen["format"], "mp4")
            self.assertEqual(seen["draftSha256"], seen["revision"].removeprefix("sha256:"))

    def test_export_error_maps_without_token(self):
        class DeniedHandler(self.Handler):
            def do_POST(self):
                if not self._authorized():
                    return
                length = int(self.headers.get("content-length", "0"))
                self.rfile.read(length)
                self._json(409, {"error": "film_export_entitlement_denied"})

        server = ThreadingHTTPServer(("127.0.0.1", 0), DeniedHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        port = server.server_address[1]
        bridge = bridge_mod.Bridge({
            "token": "test-token", "port": port,
            "origin": f"http://127.0.0.1:{port}",
        })
        with tempfile.TemporaryDirectory() as tmp:
            draft = Path(tmp) / "draft"
            draft.mkdir()
            (draft / "draft_info.json").write_text("{}", "utf-8")
            with self.assertRaises(SkillError) as caught:
                bridge.export(draft, Path(tmp) / "out.mp4", timeout_ms=1000)
        self.assertEqual(caught.exception.code, "film_export_entitlement_denied")
        self.assertNotIn("test-token", json.dumps(caught.exception.to_dict()))

    def test_timeout_is_mapped(self):
        class SlowHandler(BaseHTTPRequestHandler):
            def log_message(self, *_args):
                pass

            def do_GET(self):
                time.sleep(0.4)
                self.send_response(200)
                self.send_header("content-length", "0")
                self.end_headers()

        server = ThreadingHTTPServer(("127.0.0.1", 0), SlowHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        port = server.server_address[1]
        bridge = bridge_mod.Bridge({
            "token": "test-token", "port": port,
            "origin": f"http://127.0.0.1:{port}",
        })
        with self.assertRaises(SkillError) as caught:
            bridge.health(timeout=0.05)
        self.assertEqual(caught.exception.code, "BRIDGE_TIMEOUT")


class SubtitleTests(unittest.TestCase):
    def test_caption_template_info_on_text_material(self):
        spec = {
            "caption_template": {
                "resource_id": "7369552920146119974",
                "name": "白字黑边",
                "path": "C:/tmpl",
                "source_platform": 1,
            },
            "font_size": 8,
        }
        material = draft_mod._text_material(
            "测试", spec, draft_mod._asset("text_material.json"))
        info = material.get("caption_template_info")
        self.assertIsNotNone(info)
        self.assertEqual(info["resource_id"], "7369552920146119974")
        self.assertEqual(info["path"], "C:/tmpl")
        self.assertEqual(info["resource_name"], "白字黑边")
        self.assertEqual(material["recognize_text"], "测试")

    def test_highlight_styles(self):
        material = draft_mod._text_material(
            "AI工具分享 AI时代",
            {"highlight": {"words": ["AI"], "color": "#FFD400", "bold": True}},
            draft_mod._asset("text_material.json"))
        content = json.loads(material["content"])
        self.assertEqual(len(content["styles"]), 3)
        self.assertEqual(content["styles"][1]["range"], [0, 2])
        self.assertEqual(content["styles"][2]["range"], [7, 9])
        self.assertTrue(content["styles"][1]["bold"])

    def test_local_asr_fillers_and_punctuation(self):
        from subtitles import local_asr
        tokens = ["嗯", "那", "个", "我们", "就", "是", "说", "开始"]
        spans = [(index * 0.1, index * 0.1 + 0.1) for index in range(len(tokens))]
        out_tokens, out_spans = local_asr.remove_fillers(
            tokens, spans, {"嗯", "那个", "就是说"})
        self.assertEqual(out_tokens, ["我们", "开始"])
        self.assertEqual(len(out_spans), 2)
        cues = [
            {"text": "第一句", "start": 0, "end": 1},
            {"text": "第二句", "start": 1.2, "end": 2.5},
        ]
        local_asr.add_punctuation(cues)
        self.assertEqual(cues[0]["text"], "第一句，")
        self.assertEqual(cues[1]["text"], "第二句。")

    def test_local_asr_fillers_handle_bpe_continuation(self):
        from subtitles import local_asr
        tokens = ["那@@", "个", "我们", "就@@", "是@@", "说", "开始"]
        spans = [(index * 0.1, index * 0.1 + 0.1) for index in range(len(tokens))]
        out_tokens, out_spans = local_asr.remove_fillers(
            tokens, spans, {"那个", "就是说"})
        self.assertEqual(out_tokens, ["我们", "开始"])
        self.assertEqual(len(out_spans), 2)

    def test_local_asr_punc_seps_follow_break_class_and_gap(self):
        from subtitles import local_asr
        spans = [(0.0, 0.5), (0.5, 1.0), (2.0, 2.4)]
        self.assertEqual(local_asr.build_seps([1, 2, 2], spans), ["", "。", "。"])
        spans = [(0.0, 0.5), (0.5, 1.0), (1.2, 1.6)]
        self.assertEqual(local_asr.build_seps([1, 2, 1], spans), ["", "，", ""])

    def test_local_asr_punc_fallback_is_not_silent(self):
        from subtitles import local_asr

        class ShortPunc:
            @staticmethod
            def classes(_tokens):
                return [1]

        seps, source, breaks, detail = local_asr._make_seps(
            ["你", "好"], [(0, 1), (1, 2)], ShortPunc(), True)
        self.assertEqual((source, breaks, seps), ("heuristic", 0, ["", ""]))
        self.assertIn("class-count", detail)

        seps, source, breaks, detail = local_asr._make_seps(
            ["你"], [(0, 1)], None, False)
        self.assertEqual((source, breaks, detail, seps), ("off", 0, "", [""]))

    def test_local_asr_chunks_split_on_long_silence(self):
        try:
            import numpy as np
        except ImportError:
            self.skipTest("numpy 不可用")
        from subtitles import local_asr
        sr = local_asr.SAMPLE_RATE
        tone_t = np.arange(int(sr * 1.5)) / sr
        tone = 0.3 * np.sin(2 * np.pi * 440 * tone_t)
        noise = 0.0002 * np.random.default_rng(0).standard_normal(int(sr * 3.0))
        audio = np.concatenate([tone, noise, tone]).astype(np.float32)
        chunks = local_asr.split_chunks(np, audio, min_sec=2.0, max_sec=30.0)
        self.assertEqual(len(chunks), 2, f"长静音必须切开，实际 {chunks}")
        self.assertAlmostEqual(chunks[0][1] / sr, 1.5, delta=0.3)
        self.assertAlmostEqual(chunks[1][0] / sr, 4.5, delta=0.3)

    def test_local_asr_render_itn_tags(self):
        from subtitles import local_asr
        tagged = ('char { value: "产" } measure { value: "50%" } '
                  'date { year: "2026年" month: "11月" day: "18日" } '
                  'time { hour: "3" minute: "30" } char { value: "。" }')
        self.assertEqual(local_asr.render_tags(tagged), "产50%2026年11月18日3:30。")

    def test_local_asr_quality_summary_is_descriptive_only(self):
        from subtitles import local_asr
        self.assertEqual(local_asr.quality_summary([]),
                         {"source": "absent", "chunks": [], "min": None, "mean": None})
        summary = local_asr.quality_summary([0.9, 0.7])
        self.assertEqual(summary["source"], "model")
        self.assertEqual(summary["chunks"], [0.9, 0.7])
        self.assertEqual(summary["min"], 0.7)
        self.assertEqual(summary["mean"], 0.8)

    def test_local_asr_explicit_model_dir_does_not_fall_back(self):
        from subtitles import local_asr
        with tempfile.TemporaryDirectory() as tmp:
            missing = Path(tmp) / "empty-model"
            missing.mkdir()
            with self.assertRaises(local_asr.S.SrtError) as caught:
                local_asr.find_model_dir(str(missing))
            self.assertEqual(caught.exception.code, "model-missing")
            self.assertIn("--model-dir", caught.exception.detail)

    def test_probe_asr_info_honors_model_env(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "model"
            root.mkdir()
            for name in ("asr-model-encoder.onnx", "asr-model-decoder.onnx",
                         "asr-model-token.txt"):
                (root / name).write_bytes(b"x")
            with mock.patch.dict(os.environ, {"JY_LOCAL_ASR_DIR": str(root)}):
                info = capability_mod._asr_info()
            self.assertTrue(info["available"])
            self.assertEqual(info["model_dir"], str(root))

    def test_speech_problem_rejects_silence_music_and_hallucination(self):
        from subtitles import local_asr
        self.assertIsNotNone(local_asr.speech_problem(0.0, 6.0, 3))
        self.assertIsNotNone(local_asr.speech_problem(0.01, 30.0, 1))
        self.assertIsNotNone(local_asr.speech_problem(0.01, 10.0, 20,
                                                      max_cue_duration=20.0))
        self.assertIsNone(local_asr.speech_problem(0.01, 60.0, 259))

    def test_caption_duration_info_uses_milliseconds(self):
        info = draft_mod._caption_duration_info({"caption_info": {
            "original_text": "测试",
            "words": [{"text": "测试",
                       "time_range": {"start": 0, "duration": 2_000_000}}],
        }})
        self.assertEqual(info["start_time"], 0)
        self.assertEqual(info["end_time"], 2000)
        self.assertEqual(info["words"][0]["start_time"], 0)
        self.assertEqual(info["words"][0]["end_time"], 2000)

    def test_caption_info_rejects_bad_words(self):
        with self.assertRaises(SkillError) as caught:
            draft_mod._validate_caption_info(
                {"original_text": "x", "words": "bad"})
        self.assertEqual(caught.exception.code, "VALIDATION")
        with self.assertRaises(SkillError) as caught:
            draft_mod._validate_caption_info(
                {"original_text": "x",
                 "words": [{"text": "x", "time_range": {"start": -1}}]})
        self.assertEqual(caught.exception.code, "VALIDATION")

    def test_filter_parser_locks_name_column(self):
        """ass 行描述里也有 subtitles 字样，解析只能认第二列滤镜名。"""
        from subtitles import jy_common
        self.assertEqual(
            jy_common.filter_names(
                " .. ass V->V Render ASS subtitles onto input video.\n"
                " .. subtitles V->V Render text subtitles onto input video.\n"),
            {"ass", "subtitles"},
        )
        self.assertEqual(
            jy_common.filter_names(
                " .. ass V->V Render ASS subtitles onto input video.\n"),
            {"ass"},
        )
        self.assertEqual(
            jy_common.filter_names(
                " ?? hflip V->V Flip video horizontally.\n"),
            {"hflip"},
        )
        self.assertEqual(
            jy_common.encoder_names(
                " V....D libx264rgb H.264 RGB encoder.\n"
                " V....D libx264 H.264 encoder.\n"),
            {"libx264rgb", "libx264"},
        )
        self.assertEqual(
            jy_common.encoder_names(
                " V....D libx264rgb H.264 RGB encoder using libx264 core.\n"),
            {"libx264rgb"},
        )

    def test_probe_capabilities_reads_stderr_and_locks_encoder_column(self):
        from subtitles import jy_common

        def fake_run(args, **_kwargs):
            if "-version" in args:
                return 0, "ffmpeg version test\n", ""
            if "-filters" in args:
                return 0, "", " .. subtitles V->V Render text subtitles.\n"
            if "-encoders" in args:
                return 0, "", " V....D libx264rgb H.264 RGB encoder.\n"
            return 1, "", ""

        with mock.patch.object(jy_common, "_run", side_effect=fake_run):
            caps = jy_common.probe_ffmpeg_capabilities(Path("ffmpeg.exe"))
        self.assertTrue(caps["libass"], caps)
        self.assertTrue(caps["subtitle_burn_in"], caps)
        self.assertFalse(caps["libx264"], caps)

    def test_probe_reports_subtitle_ffmpeg(self):
        info = env_mod.subtitle_ffmpeg_info()
        self.assertIn("burn_in_available", info)
        if "error" not in info:
            self.assertIn("subtitle_burn_in", info)

    def test_resolve_ffmpeg_finds_imageio(self):
        import importlib.util

        if importlib.util.find_spec("imageio_ffmpeg") is None:
            self.skipTest("imageio_ffmpeg not installed")
        from subtitles import jy_common

        resolved = jy_common.resolve_ffmpeg()
        sources = [item.get("source")
                   for item in resolved.get("candidates") or []]
        self.assertIn("python:imageio_ffmpeg", sources)

    def test_invalid_total_returns_structured_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            text = root / "lines.txt"
            text.write_text("第一句。", "utf-8")
            cli = ROOT / "subtitles" / "cli.py"
            proc = subprocess.run(
                [sys.executable, str(cli), "srt.build", "--text", str(text),
                 "--total", "-1", "--out", str(root / "bad.srt")],
                capture_output=True, text=True, encoding="utf-8", errors="replace",
                timeout=30,
            )
            self.assertNotEqual(proc.returncode, 0)
            payload = json.loads(proc.stdout)
            self.assertFalse(payload["ok"])
            self.assertFalse((root / "bad.srt").exists())

    def test_build_and_check_srt(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            text = root / "lines.txt"
            text.write_text("第一句。第二句。", "utf-8")
            srt = root / "out.srt"
            cli = ROOT / "subtitles" / "cli.py"
            built = subprocess.run(
                [sys.executable, str(cli), "srt.build", "--text", str(text),
                 "--total", "4", "--out", str(srt)],
                capture_output=True, text=True, encoding="utf-8", errors="replace",
                timeout=30,
            )
            self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
            payload = json.loads(built.stdout)
            self.assertTrue(payload["ok"])
            self.assertEqual(payload["data"]["lines"], 2)
            self.assertTrue(srt.is_file())

            checked = subprocess.run(
                [sys.executable, str(cli), "srt.check", "--in", str(srt)],
                capture_output=True, text=True, encoding="utf-8", errors="replace",
                timeout=30,
            )
            self.assertEqual(checked.returncode, 0, checked.stdout + checked.stderr)
            payload = json.loads(checked.stdout)
            self.assertTrue(payload["ok"])
            self.assertEqual(payload["data"]["issues"], [])


class RegressionTests(unittest.TestCase):
    """审查修复的防复发测试：UNC 防护、零时长字幕、VALIDATION 归类、暂存清理、索引 id 一致。"""

    def _sub_module(self, name):
        import importlib.util
        path = ROOT / "subtitles" / f"{name}.py"
        spec = importlib.util.spec_from_file_location(f"_jy_{name}", path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod

    def _build(self, plan, out):
        with mock.patch.object(env_mod, "find_install", return_value=None), \
                mock.patch.object(env_mod, "find_ffmpeg",
                                  return_value={"ffmpeg": None, "ffprobe": None}):
            return draft_mod.build(plan, out, force=False, make_cover=False)

    def _text_plan(self, root, segment):
        plan = root / "plan.json"
        write_json(plan, {"schema": "jianying-plan/v1", "name": "x",
                          "canvas": {"width": 1080, "height": 1920, "fps": 30},
                          "tracks": [{"type": "text", "segments": [segment]}]})
        return plan

    def test_render_format_choices_are_exposed(self):
        completed = subprocess.run(
            [sys.executable, str(ROOT / "jy.py"), "render", "--help"],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=30)
        self.assertEqual(completed.returncode, 0, completed.stderr)
        for fmt in ("mp4", "mov", "gif", "mp3", "wav", "aac", "flac", "aiff", "ogg"):
            self.assertIn(fmt, completed.stdout)

    def test_version_chain_supports_multi_timeline(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            draft = root / "draft"
            timeline = draft / "Timelines" / "t1"
            timeline.mkdir(parents=True)
            write_json(draft / "Timelines" / "project.json",
                       {"main_timeline_id": "t1"})
            write_json(timeline / "draft_info.json", {
                "id": "ml-1", "name": "多时间线", "duration": 1_000_000,
                "canvas_config": {"width": 1080, "height": 1920},
                "fps": 30, "tracks": [], "materials": {}})
            snapshot = versions_mod.record_snapshot(draft, label="基线")
            self.assertEqual(snapshot["id"], "v001")
            listed = versions_mod.list_versions(draft)
            self.assertEqual(listed["current"], "v001")
            shown = versions_mod.show_version(draft, "v001")
            self.assertEqual(shown["id"], "v001")
            versions_mod.restore_version(draft, "v001", root / "restored")
            info = json.loads(
                (root / "restored" / "draft_info.json").read_text("utf-8"))
            self.assertNotEqual(info["id"], "ml-1")
            self.assertIn("v001", info["name"])

    def test_version_manifest_records_layout(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            draft = root / "draft"
            timeline = draft / "Timelines" / "t1"
            timeline.mkdir(parents=True)
            write_json(draft / "Timelines" / "project.json",
                       {"main_timeline_id": "t1"})
            write_json(timeline / "draft_info.json",
                       {"id": "ml-1", "name": "多时间线",
                        "tracks": [], "materials": {}})
            versions_mod.record_snapshot(draft, label="v1")
            manifest = json.loads(
                (draft / ".jianying-versions" / "versions.json").read_text("utf-8"))
            self.assertEqual(manifest["layout"], "multi-timeline")
            self.assertEqual(manifest["timeline_id"], "t1")
            self.assertEqual(manifest["versions"][0]["layout"], "multi-timeline")
            self.assertEqual(manifest["versions"][0]["timeline_id"], "t1")

            write_json(draft / "draft_info.json",
                       {"id": "single-1", "name": "单时间线",
                        "tracks": [], "materials": {}})
            versions_mod.record_snapshot(draft, label="v2")
            diff = versions_mod.diff_versions(draft, "v002")
            self.assertEqual(diff["layout_change"]["from"]["layout"],
                             "multi-timeline")
            self.assertEqual(diff["layout_change"]["from"]["timeline_id"], "t1")
            self.assertEqual(diff["layout_change"]["to"]["layout"], "single")
            self.assertIsNone(diff["layout_change"]["to"]["timeline_id"])

    def test_version_rejects_unc_path(self):
        with self.assertRaises(SkillError) as caught:
            versions_mod.list_versions(r"\\server\share\draft")
        self.assertEqual(caught.exception.code, "UNSAFE_PATH")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            draft = root / "draft"
            draft.mkdir()
            write_json(draft / "draft_info.json", {
                "id": "d", "name": "d", "tracks": [], "materials": {}})
            versions_mod.record_snapshot(draft)
            with self.assertRaises(SkillError) as caught:
                versions_mod.restore_version(draft, "v001",
                                             r"\\server\share\out")
            self.assertEqual(caught.exception.code, "UNSAFE_PATH")

    def test_read_srt_without_blank_lines_splits_cues(self):
        srt = self._sub_module("srt")
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "tight.srt"
            path.write_text(
                "1\n00:00:01,000 --> 00:00:02,000\n第一句\n"
                "2\n00:00:03,000 --> 00:00:04,000\n第二句\n"
                "3\n00:00:05,000 --> 00:00:06,000\n第三句\n",
                "utf-8")
            entries = srt.read_srt(path)
        self.assertEqual([e["text"] for e in entries],
                         ["第一句", "第二句", "第三句"])
        self.assertAlmostEqual(entries[0]["start"], 1.0)
        self.assertAlmostEqual(entries[2]["end"], 6.0)

    def test_read_srt_keeps_numeric_body_lines(self):
        srt = self._sub_module("srt")
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "numeric.srt"
            path.write_text(
                "1\n00:00:01,000 --> 00:00:02,000\n第 1 集\n2024\n"
                "2\n00:00:03,000 --> 00:00:04,000\n2024\n",
                "utf-8")
            entries = srt.read_srt(path)
        self.assertEqual([e["text"] for e in entries],
                         ["第 1 集 2024", "2024"])

    def test_split_text_keeps_english_words_in_mixed_cjk(self):
        srt = self._sub_module("srt")
        parts = srt.split_text("把我们本机的一些资料呀不管是excel", 16)
        self.assertEqual(parts, ["把我们本机的一些资料呀不管是", "excel"])
        parts = srt.split_text("然后这是操控电脑上的软件比如说photoshop", 16)
        self.assertEqual(parts, ["然后这是操控电脑上的软件比如说", "photoshop"])
        for text in ("西比如说啊我给大家推荐的叫potocraft",
                     "work巴蒂这个软件啊呃workbody"):
            for run in re.findall(r"[A-Za-z0-9]+", text):
                self.assertTrue(any(run in p for p in srt.split_text(text, 16)),
                                f"{run} 被切断: {srt.split_text(text, 16)}")

    def test_split_text_pure_english_space_split_unchanged(self):
        srt = self._sub_module("srt")
        self.assertEqual(srt.split_text("hello world foo bar baz qux", 16),
                         ["hello world foo", "bar baz qux"])

    def test_split_text_leading_long_ascii_run_hard_cuts(self):
        srt = self._sub_module("srt")
        self.assertEqual(srt.split_text("abcdefghijklmnopqrstuvwxyz", 16),
                         ["abcdefghijklmnop", "qrstuvwxyz"])

    def _tidy_cli(self, root, src_text, extra=(), max_chars=16):
        cli = ROOT / "subtitles" / "cli.py"
        src = root / "in.srt"
        src.write_text(src_text, "utf-8")
        out = root / "out.srt"
        completed = subprocess.run(
            [sys.executable, str(cli), "srt.tidy", "--in", str(src),
             "--out", str(out), "--max-chars", str(max_chars), *extra],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=60)
        return completed, out

    def test_tidy_caps_single_char_timestamp_artifacts(self):
        srt = self._sub_module("srt")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            completed, out = self._tidy_cli(
                root,
                "1\n00:00:10,000 --> 00:00:19,040\n验\n"
                "2\n00:00:20,000 --> 00:00:22,000\n下一句正常字幕\n")
            self.assertEqual(completed.returncode, 0, completed.stderr)
            payload = json.loads(completed.stdout)
            self.assertEqual(payload["data"]["short_artifacts_capped"], 1)
            entries = srt.read_srt(out)
        self.assertAlmostEqual(entries[0]["end"] - entries[0]["start"], 1.0)
        self.assertEqual(entries[0]["start"], 10.0)
        self.assertEqual(entries[0]["text"], "验")
        self.assertAlmostEqual(entries[1]["end"] - entries[1]["start"], 2.0)

    def test_tidy_mixed_wide_cues_word_safe_and_check_green(self):
        srt = self._sub_module("srt")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            completed, out = self._tidy_cli(
                root,
                "1\n00:00:01,000 --> 00:00:04,740\n把我们本机的一些资料呀不管是excel\n"
                "2\n00:00:05,000 --> 00:00:14,040\n验\n"
                "3\n00:00:15,000 --> 00:00:17,800\n然后这是操控电脑上的软件比如说photoshop\n")
            self.assertEqual(completed.returncode, 0, completed.stderr)
            entries = srt.read_srt(out)
            for run in ("excel", "photoshop"):
                self.assertTrue(any(run in e["text"] for e in entries),
                                f"{run} 被切断")
            checked = subprocess.run(
                [sys.executable, str(ROOT / "subtitles" / "cli.py"),
                 "srt.check", "--in", str(out)],
                capture_output=True, text=True, encoding="utf-8",
                errors="replace", timeout=60)
            payload = json.loads(checked.stdout)
        self.assertTrue(payload["ok"], payload)
        self.assertEqual(payload["data"]["issues"], [])

    def test_tidy_split_timing_follows_visible_length(self):
        srt = self._sub_module("srt")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            completed, out = self._tidy_cli(
                root,
                "1\n00:00:00,000 --> 00:00:02,800\n然后这是操控电脑上的软件比如说photoshop\n")
            self.assertEqual(completed.returncode, 0, completed.stderr)
            entries = srt.read_srt(out)
        self.assertEqual(len(entries), 2)
        self.assertAlmostEqual(entries[0]["end"] - entries[0]["start"],
                               2.8 * 15 / 24, places=2)
        self.assertAlmostEqual(entries[1]["end"] - entries[1]["start"],
                               2.8 * 9 / 24, places=2)
        self.assertAlmostEqual(entries[1]["start"], entries[0]["end"])
        self.assertAlmostEqual(entries[0]["start"], 0.0)
        self.assertAlmostEqual(entries[-1]["end"], 2.8, places=2)

    def test_tidy_rejects_bad_max_dur(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            completed, out = self._tidy_cli(
                root, "1\n00:00:01,000 --> 00:00:02,000\n你好\n",
                extra=("--max-dur", "0"))
            payload = json.loads(completed.stdout)
        self.assertFalse(payload["ok"])
        self.assertEqual(payload["code"], "bad-max-dur")
        self.assertFalse(out.exists())

    def test_split_text_max_chars_one_keeps_leading_punctuation(self):
        srt = self._sub_module("srt")
        self.assertEqual(srt.split_text("，abc", 1), ["，a", "b", "c"])

    def test_split_text_word_internal_apostrophe_not_a_boundary(self):
        srt = self._sub_module("srt")
        self.assertEqual(srt.split_text("中文don'tstop中文很长很长", 6),
                         ["中文don't", "stop中文", "很长很长"])

    def test_split_text_guard_requires_half_prefix(self):
        srt = self._sub_module("srt")
        word = "abcdefghijklmnop"
        self.assertEqual(srt.split_text("中" * 7 + word, 16),
                         ["中" * 7 + "abcdefghi", "jklmnop"])
        self.assertEqual(srt.split_text("中" * 8 + word, 16),
                         ["中" * 8, word])

    def test_split_text_three_parts_keep_word_intact(self):
        srt = self._sub_module("srt")
        parts = srt.split_text("中" * 15 + "photoshop" + "中" * 15, 16)
        self.assertEqual(len(parts), 3)
        self.assertTrue(any("photoshop" in p for p in parts))
        self.assertTrue(all(visible <= 16 for visible in
                            (srt.visible_len(p) for p in parts)))

    def test_split_text_no_part_starts_with_punctuation(self):
        srt = self._sub_module("srt")
        parts = srt.split_text("中" * 15 + "excel，后续还有很长一段话要说", 16)
        self.assertTrue(all(p[0] not in srt.PUNCT for p in parts))
        self.assertTrue(any("excel，" in p for p in parts))

    def test_tidy_cap_never_lengthens_short_cue(self):
        srt = self._sub_module("srt")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            completed, out = self._tidy_cli(
                root, "1\n00:00:00,000 --> 00:00:00,800\n验\n",
                extra=("--max-dur", "0.5"))
            self.assertEqual(completed.returncode, 0, completed.stderr)
            entries = srt.read_srt(out)
        self.assertAlmostEqual(entries[0]["end"] - entries[0]["start"], 0.8)

    def test_tidy_cap_wins_over_min_dur(self):
        srt = self._sub_module("srt")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            completed, out = self._tidy_cli(
                root, "1\n00:00:00,000 --> 00:00:09,040\n验\n",
                extra=("--min-dur", "2"))
            self.assertEqual(completed.returncode, 0, completed.stderr)
            entries = srt.read_srt(out)
        self.assertAlmostEqual(entries[0]["end"] - entries[0]["start"], 1.0)

    def test_tidy_caps_split_derived_short_parts(self):
        srt = self._sub_module("srt")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            completed, out = self._tidy_cli(
                root, "1\n00:00:00,000 --> 00:00:15,000\n好的\n",
                max_chars=1)
            payload = json.loads(completed.stdout)
            self.assertEqual(payload["data"]["short_artifacts_capped"], 2)
            entries = srt.read_srt(out)
            checked = subprocess.run(
                [sys.executable, str(ROOT / "subtitles" / "cli.py"),
                 "srt.check", "--in", str(out)],
                capture_output=True, text=True, encoding="utf-8",
                errors="replace", timeout=60)
        self.assertTrue(all(e["end"] - e["start"] <= 1.0 + 1e-3 for e in entries))
        self.assertTrue(json.loads(checked.stdout)["ok"])

    def test_tidy_cap_condition_boundaries(self):
        srt = self._sub_module("srt")
        cases = [
            ("1\n00:00:00,000 --> 00:00:09,000\n你好\n", (), 1),
            ("1\n00:00:00,000 --> 00:00:09,000\n你好吗\n", (), 0),
            ("1\n00:00:00,000 --> 00:00:06,000\n验\n", (), 0),
            ("1\n00:00:00,000 --> 00:00:04,000\n你好\n", ("--max-dur", "3"), 1),
            ("1\n00:00:00,000 --> 00:00:09,000\n验\n", ("--max-dur", "100"), 0),
        ]
        with tempfile.TemporaryDirectory() as tmp:
            for i, (text, extra, want) in enumerate(cases):
                root = Path(tmp) / f"case-{i}"
                root.mkdir()
                completed, out = self._tidy_cli(root, text, extra=extra)
                self.assertEqual(completed.returncode, 0, completed.stderr)
                payload = json.loads(completed.stdout)
                self.assertEqual(payload["data"]["short_artifacts_capped"], want,
                                 f"case {i}: {text!r} {extra}")

    def test_render_reports_all_mutated_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            draft = root / "draft"
            draft.mkdir()
            write_json(draft / "draft_info.json", {
                "id": "d1", "name": "d", "duration": 1_000_000,
                "canvas_config": {"width": 320, "height": 180},
                "fps": 30, "tracks": [], "materials": {}})
            write_json(draft / "draft_meta_info.json", {"draft_id": "d1"})
            out = root / "out.mp4"

            class FakeBridge:
                def safe_health(self):
                    return {"version": "11.8.0", "pid": 1}

                def export(self, draft_dir, out_path, **_kwargs):
                    write_json(Path(draft_dir) / "draft_meta_info.json",
                               {"draft_id": "d1", "draft_name": "回写"})
                    Path(out_path).write_bytes(b"mp4")
                    return {"path": str(out_path), "bytes": 3}

            args = argparse.Namespace(draft=str(draft), out=str(out),
                                      force=False, format="mp4", timeout=10)
            buffer = io.StringIO()
            with mock.patch.object(jy_mod.Bridge, "discover",
                                   return_value=FakeBridge()), \
                    mock.patch.object(env_mod, "find_install", return_value=None), \
                    mock.patch.object(env_mod, "find_ffmpeg",
                                      return_value={"ffmpeg": None,
                                                    "ffprobe": None}), \
                    contextlib.redirect_stdout(buffer):
                code = jy_mod.cmd_render(args)
            self.assertEqual(code, 0)
            payload = json.loads(buffer.getvalue())
            self.assertTrue(payload["ok"])
            self.assertTrue(payload["data"]["draft_mutated"])
            self.assertEqual(payload["data"]["draft_files_changed"],
                             ["draft_meta_info.json"])
            self.assertFalse(any(
                "beauty/figure" in item or "chroma" in item or "mix_mode" in item
                for item in payload["data"]["warnings"]))

    def test_render_scan_tolerates_null_and_accepts_material_id(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            bad = root / "bad.json"
            write_json(bad, {"materials": None, "tracks": None})
            self.assertFalse(jy_mod._draft_material_present(bad, "effects"))
            self.assertFalse(jy_mod._draft_beauty_present(bad))
            self.assertFalse(jy_mod._draft_chroma_present(bad))

            good = root / "good.json"
            write_json(good, {
                "materials": {"effects": [{"id": "fig1", "type": "figure"}]},
                "tracks": [{"segments": [{"material_id": "fig1"}]}],
            })
            self.assertTrue(jy_mod._draft_beauty_present(good))

            scalar = root / "scalar.json"
            write_json(scalar, {
                "materials": {"effects": [{"id": "fig1", "type": "figure"}]},
                "tracks": [{"segments": [{"extra_material_refs": "fig1"}]}],
            })
            self.assertTrue(jy_mod._draft_beauty_present(scalar))

    def test_render_reports_beauty_chroma_conditional_warnings(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            draft = root / "draft"
            draft.mkdir()
            write_json(draft / "draft_info.json", {
                "id": "d2", "name": "conditional", "duration": 1_000_000,
                "canvas_config": {"width": 320, "height": 180},
                "fps": 30,
                "tracks": [{"type": "video", "segments": [{
                    "id": "s1",
                    "extra_material_refs": ["fig1", "chr1", "mix1"],
                }]}],
                "materials": {
                    "effects": [
                        {"id": "fig1", "type": "figure"},
                        {"id": "mix1", "type": "mix_mode"},
                    ],
                    "chromas": [{"id": "chr1", "type": "chroma"}],
                },
            })
            write_json(draft / "draft_meta_info.json", {"draft_id": "d2"})
            out = root / "out.mp4"

            class FakeBridge:
                def safe_health(self):
                    return {"version": "11.8.0", "pid": 1}

                def export(self, draft_dir, out_path, **_kwargs):
                    Path(out_path).write_bytes(b"mp4")
                    return {"path": str(out_path), "bytes": 3}

            args = argparse.Namespace(draft=str(draft), out=str(out),
                                      force=False, format="mp4", timeout=10)
            buffer = io.StringIO()
            with mock.patch.object(jy_mod.Bridge, "discover",
                                   return_value=FakeBridge()), \
                    mock.patch.object(env_mod, "find_install", return_value=None), \
                    mock.patch.object(env_mod, "find_ffmpeg",
                                      return_value={"ffmpeg": None,
                                                    "ffprobe": None}), \
                    contextlib.redirect_stdout(buffer):
                code = jy_mod.cmd_render(args)
            self.assertEqual(code, 0)
            payload = json.loads(buffer.getvalue())
            warnings = payload["data"]["warnings"]
            self.assertTrue(any("mix_mode" in item for item in warnings))
            self.assertTrue(any("beauty/figure" in item for item in warnings))
            self.assertTrue(any("chroma" in item for item in warnings))
            self.assertTrue(all("native bridge" in item for item in warnings
                                if "mix_mode" in item or "beauty/figure" in item
                                or "chroma" in item))

    def test_render_rejects_multi_timeline_before_bridge(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            draft = root / "draft"
            timeline = draft / "Timelines" / "t1"
            timeline.mkdir(parents=True)
            write_json(draft / "Timelines" / "project.json",
                       {"main_timeline_id": "t1"})
            write_json(timeline / "draft_info.json",
                       {"id": "ml", "name": "ml"})
            out = root / "out.mp4"

            class NoBridge:
                def safe_health(self):
                    return {"version": "11.8.0", "pid": 1}

            args = argparse.Namespace(draft=str(draft), out=str(out),
                                      force=False, format="mp4", timeout=10)
            with mock.patch.object(jy_mod.Bridge, "discover",
                                   return_value=NoBridge()), \
                    contextlib.redirect_stdout(io.StringIO()):
                with self.assertRaises(SkillError) as caught:
                    jy_mod.cmd_render(args)
            self.assertEqual(caught.exception.code, "DRAFT_LAYOUT_UNSUPPORTED")
            self.assertFalse(out.exists())

    def test_subtitle_chain_rejects_unc(self):
        jc = self._sub_module("jy_common")
        with self.assertRaises(jc.MediaError) as caught:
            jc.local_path(r"\\host\share\a.mp4")
        self.assertEqual(caught.exception.code, "unsafe-path")
        self.assertEqual(jc.local_path("media/a.mp4"), Path("media/a.mp4"))

    def test_srt_allocate_rejects_zero_duration_cue(self):
        srt = self._sub_module("srt")
        with self.assertRaises(srt.SrtError) as caught:
            srt.allocate(["a", "b" * 1000], total=0.05, gap=0.0)
        self.assertEqual(caught.exception.code, "total-too-small")
        entries = srt.allocate(["第一句", "第二句"], total=4.0)
        self.assertTrue(all(e["end"] > e["start"] for e in entries))

    def test_build_non_numeric_duration_is_validation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plan = self._text_plan(root, {"text": "hi", "start": 0, "duration": "abc"})
            with self.assertRaises(SkillError) as caught:
                self._build(plan, root / "out")
            self.assertEqual(caught.exception.code, "VALIDATION")

    def test_transition_source_platform_non_numeric_is_validation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            video = root / "v.mp4"
            video.write_bytes(b"fixture")
            plan = root / "plan.json"
            write_json(plan, {
                "schema": "jianying-plan/v1", "name": "transition",
                "canvas": {"width": 640, "height": 360, "fps": 30},
                "tracks": [{"type": "video", "segments": [{
                    "path": "v.mp4", "start": 0, "duration": 1,
                    "transition": {"resource_id": "123", "source_platform": "abc",
                                   "duration": 0.5},
                }]}],
            })
            info = {"path": str(video), "name": "v.mp4", "kind": "video",
                    "duration": 4_000_000, "width": 640, "height": 360, "fps": 30.0,
                    "has_video": True, "has_audio": True, "codec": "h264"}
            with mock.patch.object(env_mod, "find_install", return_value=None), \
                    mock.patch.object(env_mod, "find_ffmpeg",
                                      return_value={"ffmpeg": None, "ffprobe": None}), \
                    mock.patch.object(draft_mod.media_mod, "probe_media", return_value=info):
                with self.assertRaises(SkillError) as caught:
                    draft_mod.build(plan, root / "out", force=False, make_cover=False)
            self.assertEqual(caught.exception.code, "VALIDATION")
            self.assertEqual(caught.exception.details.get("field"), "source_platform")

    def test_build_negative_keyframe_time_is_validation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plan = self._text_plan(root, {"text": "hi", "start": 0, "duration": 2,
                                          "keyframes": {"scale": [[-1, 1.0], [0, 1.0]]}})
            with self.assertRaises(SkillError) as caught:
                self._build(plan, root / "out")
            self.assertEqual(caught.exception.code, "VALIDATION")

    def test_build_audio_volume_keyframe_is_written(self):
        audio_info = {"path": "a.wav", "name": "a.wav", "kind": "audio", "duration": 4.0,
                      "width": 0, "height": 0, "fps": 0, "has_video": False,
                      "has_audio": True, "codec": "pcm_s16le"}
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "a.wav").write_bytes(b"RIFF")
            plan = root / "plan.json"
            write_json(plan, {"schema": "jianying-plan/v1", "name": "x",
                              "canvas": {"width": 640, "height": 360, "fps": 30},
                              "tracks": [{"type": "audio", "segments": [
                                  {"path": str(root / "a.wav"), "start": 0, "duration": 4,
                                   "keyframes": {"volume": [[0, 0.1], [2, 1.0]]}}]}]})
            with mock.patch.object(env_mod, "find_install", return_value=None), \
                    mock.patch.object(env_mod, "find_ffmpeg",
                                      return_value={"ffmpeg": "/x/f", "ffprobe": "/x/p"}), \
                    mock.patch.object(draft_mod.media_mod, "probe_media",
                                      return_value=audio_info):
                draft_mod.build(plan, root / "out", force=False, make_cover=False)
            info = json.loads((root / "out" / "draft_info.json").read_text("utf-8"))
            seg = next(s for t in info["tracks"] if t["type"] == "audio"
                       for s in t["segments"])
            channels = seg.get("common_keyframes") or []
            self.assertTrue(any(c["property_type"] == "KFTypeVolume" for c in channels),
                            "audio 分支必须写入 volume 关键帧，不能静默丢弃")

    def test_build_failure_leaves_no_staging(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plan = self._text_plan(root, {"text": "  ", "start": 0, "duration": 2})
            with self.assertRaises(SkillError):
                self._build(plan, root / "out")
            self.assertEqual(list(root.glob("**/.tmp-build-*")), [])

    def test_merge_index_keeps_current_draft_id(self):
        entry = {"draft_fold_path": "/x/d", "draft_id": "new-id", "draft_name": "n"}
        index = {"all_draft_store": [
            {"draft_fold_path": "/x/d", "draft_id": "old-id", "draft_name": "n"}],
            "draft_ids": 1}
        new_index, _b, _a, action, stored = index_mod._merge_index(index, entry)
        self.assertEqual(action, "update")
        self.assertEqual(stored["draft_id"], "new-id")
        self.assertEqual(new_index["all_draft_store"][0]["draft_id"], "new-id")

    def test_editor_guard_blocks_only_when_running(self):
        running = mock.Mock(stdout='JianyingPro.exe  1234 Console  1  100 K')
        closed = mock.Mock(stdout="INFO: No tasks are running which match the specified criteria.")
        with mock.patch.object(index_mod.subprocess, "run", return_value=running):
            with self.assertRaises(SkillError) as caught:
                index_mod._ensure_editor_closed()
            self.assertEqual(caught.exception.code, "EDITOR_RUNNING")
        with mock.patch.object(index_mod.subprocess, "run", return_value=closed):
            index_mod._ensure_editor_closed()  # 未运行：不抛异常


    def _media_plan(self, root, track_type, segment, *, source_duration=4.0):
        filename = "clip.mp4" if track_type == "video" else "pic.png"
        media_path = root / filename
        media_path.write_bytes(b"fixture")
        segment = dict(segment, path=filename)
        plan = root / "plan.json"
        write_json(plan, {
            "schema": "jianying-plan/v1", "name": "media",
            "canvas": {"width": 640, "height": 360, "fps": 30},
            "tracks": [{"type": track_type, "segments": [segment]}],
        })
        info = {
            "path": str(media_path.resolve()), "name": filename,
            "kind": "video" if track_type == "video" else "image",
            "duration": source_duration if track_type == "video" else 0.0,
            "width": 640, "height": 360, "fps": 30, "has_video": True,
            "has_audio": False, "codec": "h264",
        }
        with mock.patch.object(env_mod, "find_install", return_value=None), \
                mock.patch.object(env_mod, "find_ffmpeg",
                                  return_value={"ffmpeg": None, "ffprobe": None}), \
                mock.patch.object(draft_mod.media_mod, "probe_media", return_value=info):
            return draft_mod.build(plan, root / "out", force=False, make_cover=False)

    def test_speed_keyframe_bounds_use_target_duration(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result = self._media_plan(root, "video", {
                "start": 0, "duration": 4, "speed": 0.5,
                "keyframes": {"scale": [[0, 1.0], [3.5, 1.1]]},
            })
            document = json.loads(
                (Path(result["draft_dir"]) / "draft_info.json").read_text("utf-8"))
            segment = document["tracks"][0]["segments"][0]
            channels = segment.get("common_keyframes") or []
            scale = next(c for c in channels if c["property_type"] == "KFTypeScaleX")
            self.assertEqual(max(k["time_offset"] for k in scale["keyframe_list"]),
                             3_500_000)

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with self.assertRaises(SkillError) as caught:
                self._media_plan(root, "video", {
                    "start": 0, "duration": 1.5, "speed": 2,
                    "keyframes": {"scale": [[0, 1.0], [2.5, 1.2]]},
                })
            self.assertEqual(caught.exception.code, "VALIDATION")

    def test_build_image_speed_is_validation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with self.assertRaises(SkillError) as caught:
                self._media_plan(root, "image", {"start": 0, "duration": 2, "speed": 2})
            self.assertEqual(caught.exception.code, "VALIDATION")
            self.assertEqual(caught.exception.details.get("field"), "speed")

    def test_build_non_numeric_font_size_is_validation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plan = self._text_plan(root, {"text": "hi", "start": 0, "duration": 2,
                                          "font_size": "abc"})
            with self.assertRaises(SkillError) as caught:
                self._build(plan, root / "out")
            self.assertEqual(caught.exception.code, "VALIDATION")

    def test_patch_non_numeric_style_is_validation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            out = root / "draft"
            self._build(self._text_plan(root, {"text": "hi", "start": 0, "duration": 2}), out)
            ops = root / "ops.json"
            write_json(ops, {"ops": [{"op": "set_style", "segment": 0,
                                      "font_size": "abc"}]})
            copy = root / "copy"
            with self.assertRaises(SkillError) as caught:
                draft_mod.patch(out, ops, copy)
            self.assertEqual(caught.exception.code, "VALIDATION")
            self.assertFalse(copy.exists())

    def test_volume_non_numeric_is_validation(self):
        with self.assertRaises(SkillError) as caught:
            draft_mod._volume({"volume": "abc"})
        self.assertEqual(caught.exception.code, "VALIDATION")

    def test_photo_trim_can_extend_beyond_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            draft = Path(self._media_plan(root, "image",
                                          {"start": 0, "duration": 2})["draft_dir"])
            ops = root / "ops.json"
            write_json(ops, {"ops": [{"op": "trim", "segment": 0, "duration": 5}]})
            copy = root / "copy"
            draft_mod.patch(draft, ops, copy)
            info = draft_mod.inspect(copy)
            self.assertAlmostEqual(info["duration"], 5.0, places=3)

    def test_build_cover_resolves_plan_relative_media(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "media").mkdir()
            (root / "plans").mkdir()
            image = root / "media" / "pic.png"
            image.write_bytes(b"png")
            plan = root / "plans" / "plan.json"
            write_json(plan, {
                "schema": "jianying-plan/v1", "name": "cover",
                "canvas": {"width": 640, "height": 360, "fps": 30},
                "tracks": [{"type": "image", "segments": [
                    {"path": "../media/pic.png", "start": 0, "duration": 2}]}],
            })
            info = {
                "path": str(image.resolve()), "name": "pic.png", "kind": "image",
                "duration": 0.0, "width": 64, "height": 64, "fps": 0,
                "has_video": True, "has_audio": False, "codec": "png",
            }
            captured = {}

            def fake_extract(ffmpeg, source, at, out):
                captured["source"] = source
                Path(out).write_bytes(b"jpg")
                return str(out)

            with mock.patch.object(env_mod, "find_install", return_value=None), \
                    mock.patch.object(env_mod, "find_ffmpeg",
                                      return_value={"ffmpeg": "/x/ffmpeg", "ffprobe": "/x/ffprobe"}), \
                    mock.patch.object(draft_mod.media_mod, "probe_media", return_value=info), \
                    mock.patch.object(draft_mod.media_mod, "extract_frame",
                                      side_effect=fake_extract):
                result = draft_mod.build(plan, root / "out", force=False, make_cover=True)
            self.assertEqual(Path(captured["source"]).resolve(), image.resolve())
            self.assertTrue(Path(result["draft_dir"], "draft_cover.jpg").is_file())

    def test_patch_out_inside_source_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            out = root / "draft"
            self._build(self._text_plan(root, {"text": "hi", "start": 0, "duration": 2}), out)
            ops = root / "ops.json"
            write_json(ops, {"ops": [{"op": "rename", "name": "x"}]})
            with self.assertRaises(SkillError) as caught:
                draft_mod.patch(out, ops, out / "copy")
            self.assertEqual(caught.exception.code, "VALIDATION")
            self.assertFalse((out / "copy").exists())

    def test_from_segments_default_has_no_gap(self):
        srt = self._sub_module("srt")
        entries, _padded = srt.allocate_by_durations(["a", "b"], [1.0, 1.0])
        self.assertAlmostEqual(entries[1]["start"], 1.0, places=3)
        entries_gap, _ = srt.allocate_by_durations(["a", "b"], [1.0, 1.0], gap=0.06)
        self.assertAlmostEqual(entries_gap[1]["start"], 1.06, places=3)

    def test_burn_capability_requires_libass(self):
        burn = self._sub_module("burn")
        problem = burn._capability_error({"usable": True, "libass": False,
                                         "drawtext": True, "source": "bundled"})
        self.assertEqual(problem[0], "ffmpeg-missing-capability")
        self.assertIsNone(burn._capability_error({"usable": True, "libass": True}))

    def test_burn_rejects_inverted_srt_cue(self):
        burn = self._sub_module("burn")
        problem = burn._cue_error([{"start": 1.0, "end": 0.5, "text": "坏字幕"}])
        self.assertEqual(problem[0], "srt-invalid")
        self.assertIn("时长为", problem[2])
        self.assertIsNone(burn._cue_error([{"start": 0.0, "end": 1.0, "text": "正常"}]))

    def test_burn_allows_overlapping_srt_cues(self):
        burn = self._sub_module("burn")
        srt = self._sub_module("srt")
        overlaps = [{"start": 0.5, "end": 2.0, "text": "甲"},
                    {"start": 1.0, "end": 2.5, "text": "乙"}]
        self.assertIsNone(burn._cue_error(overlaps))
        _ordered, issues = srt.cue_issues(overlaps, check_overlap=True)
        self.assertTrue(any("重叠" in issue for issue in issues))

    def test_version_policy_marks_out_of_window(self):
        verified = env_mod.version_policy("11.8.0.14778")
        self.assertEqual(verified["status"], "verified")
        unsupported = env_mod.version_policy("11.9.0.20000")
        self.assertEqual(unsupported["status"], "unsupported")
        self.assertEqual(env_mod.version_policy(None)["status"], "unknown")

    def test_build_and_patch_form_a_version_chain(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plan = self._text_plan(root, {"text": "第一版", "start": 0, "duration": 2})
            out = root / "draft"
            self._build(plan, out)
            listed = versions_mod.list_versions(out)
            self.assertEqual(listed["current"], "v001")
            self.assertEqual(listed["versions"][0]["kind"], "build")
            self.assertTrue((out / listed["versions"][0]["plan"]).is_file())
            ops = root / "ops.json"
            write_json(ops, {"ops": [{"op": "set_text", "segment": 0, "text": "第二版"}]})
            copy = root / "copy"
            draft_mod.patch(out, ops, copy, version_label="改文案")
            listed = versions_mod.list_versions(copy)
            self.assertEqual([item["id"] for item in listed["versions"]], ["v001", "v002"])
            self.assertEqual(listed["versions"][1]["parent"], "v001")
            self.assertEqual(listed["versions"][1]["label"], "改文案")
            self.assertTrue((copy / listed["versions"][1]["ops"]).is_file())
            diff = versions_mod.diff_versions(copy, "v002")
            self.assertIn("text added: '第二版'", diff["changes"])
            restored = versions_mod.restore_version(copy, "v001", root / "restored")
            self.assertEqual(restored["version"], "v001")
            document = json.loads((root / "restored" / "draft_info.json").read_text("utf-8"))
            text = json.loads(document["materials"]["texts"][0]["content"])["text"]
            self.assertEqual(text, "第一版")
            self.assertNotEqual(document["id"], json.loads(
                (out / "draft_info.json").read_text("utf-8"))["id"])

    def test_version_diff_detects_material_change(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            out = root / "draft"
            self._build(self._text_plan(root, {"text": "第一版", "start": 0,
                                              "duration": 2}), out)
            ops = root / "style.json"
            write_json(ops, {"ops": [{"op": "set_style", "segment": 0,
                                      "font_size": 11, "color": "#00FF00"}]})
            copy = root / "styled"
            draft_mod.patch(out, ops, copy)
            diff = versions_mod.diff_versions(copy, "v002")
            self.assertTrue(diff["changed_segments"])
            self.assertTrue(any(item.startswith("segments changed:")
                                for item in diff["changes"]))

    def test_patch_records_editor_rewrite_before_new_version(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            out = root / "draft"
            self._build(self._text_plan(root, {"text": "第一版", "start": 0,
                                              "duration": 2}), out)
            info = out / "draft_info.json"
            document = json.loads(info.read_text("utf-8"))
            content = json.loads(document["materials"]["texts"][0]["content"])
            content["text"] = "剪映回写后的文字"
            document["materials"]["texts"][0]["content"] = json.dumps(
                content, ensure_ascii=False)
            write_json(info, document)
            ops = root / "rename.json"
            write_json(ops, {"ops": [{"op": "rename", "name": "补丁"}]})
            copy = root / "patched"
            draft_mod.patch(out, ops, copy)
            listed = versions_mod.list_versions(copy)
            self.assertEqual([item["kind"] for item in listed["versions"]],
                             ["build", "editor-rewrite", "patch"])
            self.assertEqual(listed["versions"][1]["parent"], "v001")
            self.assertEqual(listed["versions"][2]["parent"], "v002")

    def test_snapshot_inputs_skip_draft_internal_paths(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            draft = base / "draft"
            draft.mkdir()
            cover = draft / "draft_cover.jpg"
            cover.write_bytes(b"cover")
            external = base / "main.mp4"
            external.write_bytes(b"video")
            info = {"materials": {"videos": [{"id": "v1", "path": str(external)}]}}
            inputs = versions_mod._collect_inputs(
                draft, json.dumps(info).encode("utf-8"),
                json.dumps({"draft_cover": "draft_cover.jpg"}).encode("utf-8"))
            paths = [item["path"] for item in inputs]
            self.assertIn(str(external.resolve()), paths)
            self.assertNotIn(str(cover.resolve()), paths)

    def test_snapshot_inputs_and_restore_report_missing_font(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            font = root / "font.ttf"
            font.write_bytes(b"font-fixture")
            out = root / "draft"
            self._build(self._text_plan(root, {
                "text": "字体", "start": 0, "duration": 2,
                "font_path": str(font),
            }), out)
            version = versions_mod.show_version(out, "v001")
            self.assertTrue(any(item["path"] == str(font.resolve())
                                for item in version["inputs"]))
            font.unlink()
            restored = versions_mod.restore_version(out, "v001", root / "restored")
            self.assertTrue(any(item["reason"] == "missing"
                                for item in restored["input_issues"]))

    def test_version_restore_never_overwrites(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            out = root / "draft"
            self._build(self._text_plan(root, {"text": "hi", "start": 0, "duration": 2}), out)
            target = root / "exists"
            target.mkdir()
            with self.assertRaises(SkillError) as caught:
                versions_mod.restore_version(out, "v001", target)
            self.assertEqual(caught.exception.code, "OUTPUT_EXISTS")

    def test_patch_in_place_records_patch_version(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            out = root / "draft"
            self._build(self._text_plan(root, {"text": "hi", "start": 0, "duration": 2}), out)
            ops = root / "ops.json"
            write_json(ops, {"ops": [{"op": "rename", "name": "改名"}]})
            draft_mod.patch(out, ops, None, in_place=True)
            listed = versions_mod.list_versions(out)
            self.assertEqual(listed["current"], "v002")
            self.assertEqual(listed["versions"][1]["kind"], "patch")

    def test_patch_in_place_rolls_back_info_and_meta_on_history_failure(self):
        """H-2：历史写失败时，--in-place 必须还原补丁前的 info/meta。"""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            out = root / "draft"
            self._build(self._text_plan(root, {"text": "hi", "start": 0, "duration": 2}), out)
            info = out / "draft_info.json"
            meta = out / "draft_meta_info.json"
            before_info = info.read_bytes()
            before_meta = meta.read_bytes() if meta.is_file() else None
            (out / ".jianying-versions" / "versions.json").write_text("{bad", "utf-8")
            ops = root / "ops.json"
            write_json(ops, {"ops": [{"op": "rename", "name": "坏补丁"}]})
            with self.assertRaises(SkillError) as caught:
                draft_mod.patch(out, ops, None, in_place=True)
            self.assertEqual(caught.exception.code, "VERSION_CORRUPTED")
            self.assertEqual(info.read_bytes(), before_info)
            if before_meta is not None:
                self.assertEqual(meta.read_bytes(), before_meta)

    def test_restore_rejects_target_inside_source_tree(self):
        """M-2：restore 目标不能落在源草稿内部。"""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            out = root / "draft"
            self._build(self._text_plan(root, {"text": "hi", "start": 0, "duration": 2}), out)
            with self.assertRaises(SkillError) as caught:
                versions_mod.restore_version(out, "v001", out / "nested")
            self.assertEqual(caught.exception.code, "VALIDATION")
            self.assertFalse((out / "nested").exists())

    def test_restore_meta_survives_second_level_restore(self):
        """M-4：restore 记录 meta_snapshot，二级恢复仍带 draft_meta_info.json。"""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            out = root / "draft"
            self._build(self._text_plan(root, {"text": "hi", "start": 0, "duration": 2}), out)
            first = root / "restored-1"
            versions_mod.restore_version(out, "v001", first)
            meta = json.loads((first / ".jianying-versions" / "versions.json").read_text("utf-8"))
            self.assertIsNotNone(meta["versions"][0]["meta_snapshot"])
            self.assertEqual(meta["versions"][0]["kind"], "restore")
            self.assertTrue((first / "draft_meta_info.json").is_file())
            second = root / "restored-2"
            versions_mod.restore_version(first, "v001", second)
            self.assertTrue((second / "draft_meta_info.json").is_file())
            self.assertEqual(
                json.loads((second / "draft_meta_info.json").read_text("utf-8"))["draft_id"],
                json.loads((second / "draft_info.json").read_text("utf-8"))["id"])

    def test_concurrent_snapshots_are_serialized(self):
        """M-3：并发写历史不丢更新、不残留 FileExistsError。"""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            out = root / "draft"
            self._build(self._text_plan(root, {"text": "hi", "start": 0, "duration": 2}), out)
            with ThreadPoolExecutor(max_workers=6) as pool:
                list(pool.map(lambda index: versions_mod.record_snapshot(
                    out, label=f"c{index}"), range(6)))
            listed = versions_mod.list_versions(out)
            self.assertEqual(len(listed["versions"]), 7)
            self.assertEqual(len({item["id"] for item in listed["versions"]}), 7)

    def test_version_show_rejects_missing_snapshot(self):
        """L-1：show 不能对缺失快照报 ok。"""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            out = root / "draft"
            self._build(self._text_plan(root, {"text": "hi", "start": 0, "duration": 2}), out)
            snapshot = out / ".jianying-versions" / "v001" / "draft_info.json"
            snapshot.unlink()
            with self.assertRaises(SkillError) as caught:
                versions_mod.show_version(out, "v001")
            self.assertEqual(caught.exception.code, "VERSION_CORRUPTED")

    def test_encrypted_snapshot_reports_draft_encrypted(self):
        """L-9：二进制/加密快照不能报成 VERSION_CORRUPTED。"""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            out = root / "draft"
            self._build(self._text_plan(root, {"text": "hi", "start": 0, "duration": 2}), out)
            snapshot = out / ".jianying-versions" / "v001" / "draft_info.json"
            snapshot.write_bytes(b"\xff\xfe\x00binary")
            with self.assertRaises(SkillError) as caught:
                versions_mod.restore_version(out, "v001", root / "restored")
            self.assertEqual(caught.exception.code, "DRAFT_ENCRYPTED")
            self.assertFalse((root / "restored").exists())

    def test_record_export_refreshes_same_path(self):
        """L-2：同路径覆盖导出必须刷新 bytes/duration，而不是留下旧回执。"""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            out = root / "draft"
            self._build(self._text_plan(root, {"text": "hi", "start": 0, "duration": 2}), out)
            versions_mod.record_export(out, {"path": "a.mp4", "bytes": 1,
                                             "probe": {"duration": 1.0}})
            versions_mod.record_export(out, {"path": "a.mp4", "bytes": 2,
                                             "probe": {"duration": 2.0}})
            item = versions_mod.show_version(out, "v001")
            self.assertEqual(len(item["exports"]), 1)
            self.assertEqual(item["exports"][0]["bytes"], 2)
            self.assertEqual(item["exports"][0]["duration"], 2.0)


class ResourceCatalogTests(unittest.TestCase):
    def _fixture(self, root: Path):
        db = root / "rp.db"
        connection = sqlite3.connect(db)
        connection.execute(
            "create table effect (id text, title text, name text, panel_name text, "
            "effect_type integer, is_vip integer, is_business integer, md5 text, extra text, "
            "category_id text, category_name text, item_urls text, sdk_extra text)")
        connection.executemany(
            "insert into effect values (?,?,?,?,?,?,?,?,?,?,?,?,?)",
            [
                ("111", "免费花字", "剪映小助手", "flower2", 1, 0, 0, "hash-free",
                 '{"is_vip":false}', "", "",
                 '["https://example.invalid/pkg.zip?x-expires=9999999999"]', "{}"),
                ("222", "会员花字", "剪映小助手", "flower2", 1, 0, 0, "hash-vip",
                 '{"is_vip":true}', "", "", "[]", "{}"),
                ("333", "未缓存贴纸", "剪映小助手", "sticker", 18, 0, 0, "hash-missing",
                 "{}", "", "", "[]", "{}"),
                ("444", "商务气泡", "剪映小助手", "bubble", 49, 0, 1, "hash-business",
                 "{}", "", "", "[]", "{}"),
            ])
        connection.commit()
        connection.close()
        cache = root / "Cache"
        package = cache / "effect" / "outer" / "hash-free"
        package.mkdir(parents=True)
        (package / "config.json").write_text("{}", "utf-8")
        return db, cache

    def test_list_cached_free_and_vip(self):
        with tempfile.TemporaryDirectory() as tmp:
            db, cache = self._fixture(Path(tmp))
            free = resources_mod.list_resources(
                db_path=db, cache_root=cache, panel="flower2", limit=10)
            self.assertEqual(free["total"], 1)
            self.assertEqual(free["items"][0]["title"], "免费花字")
            self.assertTrue(free["items"][0]["cached"])
            self.assertTrue(free["items"][0]["package_path"].endswith("hash-free"))
            with_vip = resources_mod.list_resources(
                db_path=db, cache_root=cache, panel="flower2",
                include_vip=True, limit=10)
            self.assertEqual(with_vip["total"], 2)
            self.assertEqual(sorted(item["vip"] for item in with_vip["items"]),
                             [False, True])
            cached = resources_mod.list_resources(
                db_path=db, cache_root=cache, cached_only=True, limit=10)
            self.assertEqual(cached["total"], 1)
            self.assertEqual(cached["items"][0]["id"], "111")

    def test_resolve_and_stats(self):
        with tempfile.TemporaryDirectory() as tmp:
            db, cache = self._fixture(Path(tmp))
            resolved = resources_mod.resolve("111", db_path=db, cache_root=cache)
            self.assertEqual(resolved["item"]["title"], "免费花字")
            self.assertTrue(resolved["item"]["cached"])
            stats = resources_mod.stats(db_path=db, cache_root=cache)
            self.assertEqual(stats["total"], 4)
            self.assertEqual(stats["cached"], 1)
            self.assertEqual(stats["free"], 2)
            with self.assertRaises(SkillError) as caught:
                resources_mod.resolve("no-such", db_path=db, cache_root=cache)
            self.assertEqual(caught.exception.code, "RESOURCE_NOT_FOUND")

    def test_download_refuses_vip_and_dry_run_free(self):
        with tempfile.TemporaryDirectory() as tmp:
            db, cache = self._fixture(Path(tmp))
            with self.assertRaises(SkillError) as caught:
                resources_mod.download_resource(
                    "222", db_path=db, cache_root=cache, apply=False)
            self.assertEqual(caught.exception.code, "RESOURCE_GATED")
            dry = resources_mod.download_resource(
                "111", db_path=db, cache_root=cache, apply=False, force=True)
            self.assertFalse(dry["applied"])
            self.assertEqual(dry["url_count"], 1)
            self.assertIn("artistEffect", dry["target"])
            self.assertFalse(Path(dry["target"]).exists())

    def test_business_flag_comes_from_db_even_without_extra(self):
        """商务标记不能只信 extra；旧记录 extra 为空时也要拦住下载。"""
        with tempfile.TemporaryDirectory() as tmp:
            db, cache = self._fixture(Path(tmp))
            resolved = resources_mod.resolve("444", db_path=db, cache_root=cache)
            self.assertTrue(resolved["item"]["business"])
            with self.assertRaises(SkillError) as caught:
                resources_mod.download_resource(
                    "444", db_path=db, cache_root=cache, apply=False)
            self.assertEqual(caught.exception.code, "RESOURCE_GATED")
            stats = resources_mod.stats(db_path=db, cache_root=cache)
            self.assertEqual(stats["free"], 2)

    def test_download_rejects_gated_dependency(self):
        """模板主资源免费、依赖字体/花字收费时不能整体下载。"""
        with tempfile.TemporaryDirectory() as tmp:
            db, cache = self._fixture(Path(tmp))
            connection = sqlite3.connect(db)
            connection.execute(
                "update effect set sdk_extra = ? where id = '111'",
                ('{"depend_resource_list":[{"type":"fonts","resource_id":"222"}]}',))
            connection.commit()
            connection.close()
            with self.assertRaises(SkillError) as caught:
                resources_mod.download_resource(
                    "111", db_path=db, cache_root=cache, apply=False, force=True)
            self.assertEqual(caught.exception.code, "RESOURCE_GATED")
            self.assertEqual(caught.exception.details["dependencies"][0]["resource_id"],
                             "222")
            self.assertTrue(caught.exception.details["dependencies"][0]["vip"])

    def test_install_archive_extracts_and_rejects_traversal(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            good = root / "good.zip"
            with zipfile.ZipFile(good, "w") as bundle:
                bundle.writestr("config.json", "{}")
            target = root / "cache" / "effect" / "1" / "hash"
            resources_mod.install_archive(good, target)
            self.assertTrue((target / "config.json").is_file())
            bad = root / "bad.zip"
            with zipfile.ZipFile(bad, "w") as bundle:
                bundle.writestr("../evil.txt", "x")
            with self.assertRaises(SkillError) as caught:
                resources_mod.install_archive(bad, root / "cache2" / "target")
            self.assertEqual(caught.exception.code, "PACKAGE_INVALID")
            self.assertFalse((root / "evil.txt").exists())

    def test_plan_resource_ref_resolves_cached_resource(self):
        plan = {"tracks": [{"segments": [{
            "text": "x", "text_effect": {"resource_ref": "DeepGlow"}}]}]}
        fake = {"item": {
            "id": "1", "title": "DeepGlow", "panel": "tool_text_glow",
            "cached": True, "package_path": "C:/cache/effect/1/hash",
            "vip": False, "business": False, "category_id": "", "category_name": "",
        }}
        with mock.patch.object(resources_mod, "resolve", return_value=fake):
            draft_mod._resolve_plan_resource_refs(plan)
        spec = plan["tracks"][0]["segments"][0]["text_effect"]
        self.assertEqual(spec["resource_id"], "1")
        self.assertEqual(spec["path"], "C:/cache/effect/1/hash")
        self.assertEqual(spec["effect_id"], "1")
        self.assertNotIn("resource_ref", spec)

    def test_plan_resource_ref_font_and_not_cached(self):
        plan = {"segments": [{"text": "x", "resource_ref": "字体"}]}
        cached = {"item": {
            "id": "2", "title": "字体", "panel": "fonts", "cached": True,
            "package_path": "C:/cache/fonts/2/hash", "vip": False,
            "business": False, "category_id": "", "category_name": "",
        }}
        with mock.patch.object(resources_mod, "resolve", return_value=cached), \
                mock.patch.object(resources_mod, "font_file",
                                  return_value=Path("C:/cache/fonts/2/hash/f.ttf")):
            draft_mod._resolve_plan_resource_refs(plan)
        self.assertEqual(plan["segments"][0]["font_path"],
                         "C:\\cache\\fonts\\2\\hash\\f.ttf")
        missing = {"item": {
            "id": "3", "title": "未缓存", "panel": "sticker", "cached": False,
            "package_path": None, "vip": False, "business": False,
            "category_id": "", "category_name": "",
        }}
        with mock.patch.object(resources_mod, "resolve", return_value=missing):
            with self.assertRaises(SkillError) as caught:
                draft_mod._resolve_plan_resource_refs(
                    {"segments": [{"resource_ref": "未缓存"}]})
        self.assertEqual(caught.exception.code, "RESOURCE_NOT_CACHED")

    def test_resolve_ambiguous_title_and_escaped_like(self):
        with tempfile.TemporaryDirectory() as tmp:
            db, cache = self._fixture(Path(tmp))
            with self.assertRaises(SkillError) as caught:
                resources_mod.resolve("花字", db_path=db, cache_root=cache)
            self.assertEqual(caught.exception.code, "RESOURCE_AMBIGUOUS")
            self.assertEqual(len(caught.exception.details["candidates"]), 2)
            with self.assertRaises(SkillError) as caught:
                resources_mod.resolve("%", db_path=db, cache_root=cache)
            self.assertEqual(caught.exception.code, "RESOURCE_NOT_FOUND")
            with self.assertRaises(SkillError) as caught:
                resources_mod.resolve("免费", db_path=db, cache_root=cache,
                                      allow_fuzzy=False)
            self.assertEqual(caught.exception.code, "RESOURCE_NOT_FOUND")
            exact = resources_mod.resolve("免费花字", db_path=db, cache_root=cache,
                                          allow_fuzzy=False)
            self.assertEqual(exact["item"]["id"], "111")

    def test_download_rejects_empty_md5(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            db = root / "rp.db"
            connection = sqlite3.connect(db)
            connection.execute(
                "create table effect (id text, title text, name text, panel_name text, "
                "effect_type integer, is_vip integer, is_business integer, md5 text, extra text, "
                "category_id text, category_name text, item_urls text, sdk_extra text)")
            connection.execute(
                "insert into effect values (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                ("999", "无 md5", "x", "shuziren2408", 1, 0, 0, "",
                 '{"is_vip":false}', "", "",
                 '["https://example.invalid/pkg.zip?x-expires=9999999999"]', "{}"))
            connection.commit()
            connection.close()
            with self.assertRaises(SkillError) as caught:
                resources_mod.download_resource(
                    "999", db_path=db, cache_root=root / "Cache", apply=False)
            self.assertEqual(caught.exception.code, "RESOURCE_MD5_MISSING")

    def test_download_expired_http_error_and_bad_zip(self):
        with tempfile.TemporaryDirectory() as tmp:
            db, cache = self._fixture(Path(tmp))
            connection = sqlite3.connect(db)
            connection.execute(
                "update effect set item_urls = ? where id = '111'",
                ('["https://example.invalid/pkg.zip?x-expires=1"]',))
            connection.commit()
            connection.close()
            with self.assertRaises(SkillError) as caught:
                resources_mod.download_resource(
                    "111", db_path=db, cache_root=cache, apply=True, force=True)
            self.assertEqual(caught.exception.code, "RESOURCE_URL_EXPIRED")

            connection = sqlite3.connect(db)
            connection.execute(
                "update effect set item_urls = ? where id = '111'",
                ('["https://example.invalid/pkg.zip?x-expires=9999999999"]',))
            connection.commit()
            connection.close()
            with mock.patch.object(
                    resources_mod, "_open_url",
                    side_effect=urllib.error.HTTPError(
                        "https://example.invalid/pkg.zip", 403, "denied", {}, None)):
                with self.assertRaises(SkillError) as caught:
                    resources_mod.download_resource(
                        "111", db_path=db, cache_root=cache, apply=True, force=True)
            self.assertEqual(caught.exception.code, "RESOURCE_DOWNLOAD_FAILED")

            with mock.patch.object(
                    resources_mod, "_open_url",
                    return_value=contextlib.closing(io.BytesIO(b"not-a-zip"))):
                with self.assertRaises(SkillError) as caught:
                    resources_mod.download_resource(
                        "111", db_path=db, cache_root=cache, apply=True, force=True)
            self.assertEqual(caught.exception.code, "PACKAGE_INVALID")

    def test_verify_resource_panel_and_gate(self):
        with tempfile.TemporaryDirectory() as tmp:
            db, cache = self._fixture(Path(tmp))
            good = resources_mod.verify(
                "111", expect_panel="flower2", db_path=db, cache_root=cache)
            self.assertTrue(good["usable"])
            self.assertIsNone(good["next"])
            mismatch = resources_mod.verify(
                "111", expect_panel="fonts", db_path=db, cache_root=cache)
            self.assertFalse(mismatch["usable"])
            self.assertTrue(any(item["issue"] == "panel_mismatch"
                                for item in mismatch["issues"]))
            gated = resources_mod.verify("222", db_path=db, cache_root=cache)
            self.assertFalse(gated["usable"])
            self.assertTrue(any(item["issue"] == "gated"
                                for item in gated["issues"]))

    def test_install_archive_rejects_reserved_name_and_force_rolls_back(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            bad = root / "bad-name.zip"
            with zipfile.ZipFile(bad, "w") as bundle:
                bundle.writestr("CON", "x")
                bundle.writestr("config.json", "{}")
            with self.assertRaises(SkillError) as caught:
                resources_mod.install_archive(bad, root / "cache" / "bad")
            self.assertEqual(caught.exception.code, "PACKAGE_INVALID")
            good = root / "good.zip"
            with zipfile.ZipFile(good, "w") as bundle:
                bundle.writestr("config.json", '{"new":true}')
            target = root / "cache" / "effect" / "1" / "hash"
            target.mkdir(parents=True)
            (target / "config.json").write_text('{"old":true}', "utf-8")
            resources_mod.install_archive(good, target, force=True)
            self.assertEqual((target / "config.json").read_text("utf-8"),
                             '{"new":true}')
            self.assertFalse([path for path in target.parent.iterdir()
                              if path.name.endswith(".bak")])


class PackagingTests(unittest.TestCase):
    def test_build_packaging_plan(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            video = root / "video.mp4"
            bgm = root / "bgm.m4a"
            srt = root / "subs.srt"
            out = root / "plan.json"
            video.write_bytes(b"x")
            bgm.write_bytes(b"x")
            srt.write_text(
                "1\n00:00:00,000 --> 00:00:01,000\n你好\n\n"
                "2\n00:00:01,200 --> 00:00:02,000\n世界\n",
                "utf-8")
            probe = {"duration": 5.0, "width": 1280, "height": 720,
                     "fps": 30.0, "has_audio": True}
            with mock.patch.object(packaging_mod, "_probe", return_value=probe):
                result = packaging_mod.build_plan(
                    video, out, title="标题", subtitle_srt=srt, bgm=bgm,
                    font_ref="字体", subtitle_template_ref="白字黑边",
                    title_animation_ref="变色输入", name="包装测试",
                    highlight_words="AI")
            self.assertTrue(out.is_file())
            plan = json.loads(out.read_text("utf-8"))
            self.assertEqual([track["type"] for track in plan["tracks"]],
                             ["video", "text", "text", "audio"])
            self.assertEqual(result["subtitle_cues"], 2)
            title = plan["tracks"][1]["segments"][0]
            self.assertEqual(title["resource_ref"], "字体")
            self.assertEqual(title["animations"][0]["resource_ref"], "变色输入")
            subtitle = plan["tracks"][2]["segments"][0]
            self.assertEqual(subtitle["caption_template"]["resource_ref"], "白字黑边")
            self.assertEqual(subtitle["caption_info"]["original_text"], "你好")
            self.assertEqual(subtitle["highlight"]["words"], ["AI"])
            self.assertEqual(plan["tracks"][3]["segments"][0]["volume"], 0.25)

    def test_packaging_all_cues_outside_duration_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            video = root / "video.mp4"
            srt = root / "subs.srt"
            out = root / "plan.json"
            video.write_bytes(b"x")
            srt.write_text(
                "1\n00:00:10,000 --> 00:00:12,000\n太晚\n", "utf-8")
            probe = {"duration": 5.0, "width": 1280, "height": 720,
                     "fps": 30.0, "has_audio": True}
            with mock.patch.object(packaging_mod, "_probe", return_value=probe):
                with self.assertRaises(SkillError) as caught:
                    packaging_mod.build_plan(video, out, subtitle_srt=srt)
            self.assertEqual(caught.exception.code, "VALIDATION")
            self.assertFalse(out.exists())

    def test_packaging_paths_are_relative_to_plan_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            media = root / "media"
            plans = root / "plans"
            media.mkdir()
            plans.mkdir()
            video = media / "video.mp4"
            bgm = media / "bgm.m4a"
            video.write_bytes(b"x")
            bgm.write_bytes(b"x")
            out = plans / "plan.json"

            def probe(path):
                return {"duration": 10.0 if str(path).endswith("video.mp4") else 4.0,
                        "width": 1280, "height": 720, "fps": 30.0,
                        "has_audio": True}

            with mock.patch.object(packaging_mod, "_probe", side_effect=probe):
                packaging_mod.build_plan(video, out, bgm=bgm)
            plan = json.loads(out.read_text("utf-8"))
            video_ref = Path(plan["tracks"][0]["segments"][0]["path"])
            bgm_ref = Path(plan["tracks"][1]["segments"][0]["path"])
            self.assertFalse(video_ref.is_absolute())
            self.assertFalse(bgm_ref.is_absolute())
            self.assertEqual((out.parent / video_ref).resolve(), video.resolve())
            self.assertEqual((out.parent / bgm_ref).resolve(), bgm.resolve())
            audio = plan["tracks"][1]["segments"][0]
            self.assertEqual(audio["duration"], 4.0)
            self.assertEqual(audio["audio_fade"], {"in": 1.0, "out": 1.0})


class WorkflowTests(unittest.TestCase):
    def test_subtitle_workflow_with_existing_srt(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            video = root / "video.mp4"
            srt = root / "subs.srt"
            out = root / "draft"
            plan = root / "plan.json"
            video.write_bytes(b"video")
            srt.write_text("1\n00:00:00,000 --> 00:00:01,000\n你好\n", "utf-8")
            with mock.patch.object(
                    workflow_mod.packaging_mod, "build_plan",
                    return_value={"warnings": ["plan warning"]}) as build_plan, \
                    mock.patch.object(
                        workflow_mod.draft_mod, "build",
                        return_value={"draft_dir": str(out)}) as build_draft:
                result = workflow_mod.build_subtitle_draft(
                    video, out, srt=srt, plan_out=plan, title="标题")
            self.assertEqual(result["srt"], str(srt.resolve()))
            self.assertEqual(result["plan"], str(plan.resolve()))
            kwargs = build_plan.call_args.kwargs
            self.assertEqual(Path(kwargs["subtitle_srt"]), srt.resolve())
            self.assertEqual(kwargs["title"], "标题")
            build_draft.assert_called_once()
            self.assertIn("plan warning", result["warnings"])

    def test_local_asr_command_and_error_envelope(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            audio = root / "a.wav"
            srt = root / "a.srt"
            audio.write_bytes(b"audio")

            def fake_run(command, **_kwargs):
                out = Path(command[command.index("--out") + 1])
                out.write_text("1\n00:00:00,000 --> 00:00:01,000\n你好\n", "utf-8")
                return subprocess.CompletedProcess(
                    command, 0,
                    json.dumps({"ok": True, "data": {"srt": str(out)},
                                "evidence": {"warnings": ["asr warning"]}}), "")

            with mock.patch.object(workflow_mod.subprocess, "run",
                                   side_effect=fake_run) as run:
                result = workflow_mod.generate_local_asr_srt(
                    audio, srt, remove_fillers=True, fillers="嗯,呃",
                    punctuate=True)
            command = run.call_args.args[0]
            self.assertIn("srt.from-local-asr", command)
            self.assertIn("--remove-fillers", command)
            self.assertIn("--punctuate", command)
            self.assertEqual(result["warnings"], ["asr warning"])

            def failed_run(command, **_kwargs):
                return subprocess.CompletedProcess(
                    command, 1,
                    json.dumps({"ok": False, "code": "no-speech",
                                "detail": "没有语音", "hint": "换音频"}), "")
            srt2 = root / "b.srt"
            with mock.patch.object(workflow_mod.subprocess, "run",
                                   side_effect=failed_run):
                with self.assertRaises(SkillError) as caught:
                    workflow_mod.generate_local_asr_srt(audio, srt2)
            self.assertEqual(caught.exception.code, "no-speech")


class TranscodeTests(unittest.TestCase):
    def test_transcode_builds_ffmpeg_command(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "in.mp4"
            target = root / "out.mp4"
            source.write_bytes(b"input")
            seen = {}

            def fake_run(command, **_kwargs):
                seen["command"] = command
                target.write_bytes(b"output")
                return subprocess.CompletedProcess(command, 0, "", "")

            with mock.patch.object(transcode_mod.env_mod, "find_install",
                                   return_value=None), \
                    mock.patch.object(
                        transcode_mod.env_mod, "find_ffmpeg",
                        return_value={"ffmpeg": "ffmpeg", "ffprobe": "ffprobe"}), \
                    mock.patch.object(transcode_mod.subprocess, "run",
                                      side_effect=fake_run), \
                    mock.patch.object(transcode_mod.media_mod, "probe_summary",
                                      return_value={"duration": 1.0}):
                result = transcode_mod.transcode(
                    source, target, video_bitrate="2M",
                    audio_bitrate="128k", fps=30)
            self.assertEqual(result["video_bitrate"], "2M")
            self.assertIn("-b:v", seen["command"])
            self.assertIn("2M", seen["command"])
            self.assertIn("-c:a", seen["command"])
            self.assertEqual(result["probe"]["duration"], 1.0)

    def test_transcode_rejects_bad_bitrate(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "in.mp4"
            source.write_bytes(b"x")
            with self.assertRaises(SkillError) as caught:
                transcode_mod.transcode(
                    source, root / "out.mp4", video_bitrate="fast")
            self.assertEqual(caught.exception.code, "VALIDATION")


class CapabilityTests(unittest.TestCase):
    @staticmethod
    def _facts(**overrides):
        facts = {
            "install": True,
            "ffprobe": True,
            "ffmpeg": True,
            "ffmpeg_libass": True,
            "bridge": True,
            "draft_root": True,
            "official_skills": {"exists": True},
            "cache": {"counts": {"effect": 1, "artistEffect": 1}},
        }
        facts.update(overrides)
        return facts

    def test_implemented_but_missing_prerequisite_is_conditional(self):
        item = {"status": "implemented", "requires": ["ffmpeg_libass"]}
        self.assertEqual(
            capability_mod._resolve_status(item, self._facts(ffmpeg_libass=False)),
            "conditional",
        )
        self.assertEqual(
            capability_mod._resolve_status(item, self._facts()), "implemented"
        )

    def test_missing_cache_is_missing_resource(self):
        item = {"status": "conditional", "requires": ["cache_effect"]}
        self.assertEqual(
            capability_mod._resolve_status(
                item, self._facts(cache={"counts": {"effect": 0}})),
            "missing_resource",
        )
        self.assertEqual(
            capability_mod._resolve_status(
                item, self._facts(cache={"counts": {"effect": 2}})),
            "conditional",
        )

    def test_matrix_matches_capabilities(self):
        """能力矩阵的“代码状态”必须与 CAPABILITIES 逐条一致。"""
        doc = (ROOT.parent / "references" / "capabilities.md").read_text("utf-8")
        statuses = {"implemented", "planned", "conditional", "missing_resource",
                    "host_only", "account_gated", "manual", "unverified"}
        matrix = {}
        channels = {}
        for line in doc.splitlines():
            if not line.startswith("| `"):
                continue
            cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
            if len(cells) < 4:
                continue
            status = cells[3]
            if status in statuses:
                matrix[cells[0].strip("`")] = status
                channels[cells[0].strip("`")] = cells[2]
        expected = {item["id"]: item["status"] for item in capability_mod.CAPABILITIES}
        self.assertEqual(set(matrix), set(expected))
        for capability_id, status in expected.items():
            self.assertEqual(matrix[capability_id], status, capability_id)
        # 通道列也必须同步，不能只锁 status。
        expected_channels = {item["id"]: item["channel"]
                             for item in capability_mod.CAPABILITIES}
        self.assertEqual(channels, expected_channels)

        # requires 用独立表逐条锁住；label/note 不允许空串。
        deps = {}
        in_deps = False
        for line in doc.splitlines():
            if line.startswith("## 4.1"):
                in_deps = True
                continue
            if in_deps and line.startswith("## "):
                break
            if not in_deps or not line.startswith("|"):
                continue
            cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
            if len(cells) != 3 or cells[0] in {"id", "---"}:
                continue
            deps[cells[0].strip("`")] = ([] if cells[2] == "—"
                                        else [part.strip().strip("`")
                                              for part in cells[2].split(",")
                                              if part.strip()])
        self.assertEqual(deps, {item["id"]: list(item["requires"])
                                for item in capability_mod.CAPABILITIES})
        for item in capability_mod.CAPABILITIES:
            self.assertTrue(str(item.get("label") or "").strip(), item["id"])
            self.assertTrue(str(item.get("note") or "").strip(), item["id"])
        # 关键条目的真机证据说明不能退回纯旧文案；日期只校验格式，不锁定某一次探针。
        for item_id in ("color.wheels", "audio.channel", "crop.flip",
                        "visual.mask", "sticker"):
            item = next(row for row in capability_mod.CAPABILITIES
                        if row["id"] == item_id)
            self.assertRegex(item["note"], r"\d{4}-\d{2}-\d{2}", item_id)

    def test_export_render_not_implemented_when_bridge_unreachable(self):
        """bridge 不可达时 export.render 不能报 implemented。"""
        item = next(entry for entry in capability_mod.CAPABILITIES
                    if entry["id"] == "export.render")
        self.assertNotEqual(item["status"], "implemented")
        self.assertEqual(
            capability_mod._resolve_status(item, self._facts(bridge=False)),
            "conditional",
        )

    def test_out_refuses_existing_without_force(self):
        """--out 默认不覆盖已有文件；--force 才允许覆盖。"""
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "capabilities.json"
            path.write_text("KEEP", "utf-8")
            with mock.patch.object(capability_mod, "probe",
                                   return_value={"summary": {"total": 0}}), \
                    contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(capability_mod.main(["--out", str(path)]), 1)
                self.assertEqual(path.read_text("utf-8"), "KEEP")
                self.assertEqual(
                    capability_mod.main(["--out", str(path), "--force"]), 0)

    def test_check_skill_self_test_survives_subprocess_failure(self):
        """受限环境禁止子进程时，自检返回 False 而不是抛 traceback。"""
        with mock.patch.object(check_skill_mod.subprocess, "run",
                               side_effect=OSError("subprocess denied")):
            ok, _count, _failed = check_skill_mod.self_test()
        self.assertFalse(ok)

    def test_probe_has_three_layers_and_no_credentials(self):
        fake_env = {
            "platform": "windows",
            "install": {"dir": "C:/fake", "version": "11.8.0.14778",
                        "exe": "C:/fake/JianyingPro.exe"},
            "bridge": {"found": True, "descriptor": "C:/fake/bridge.json",
                       "version": 1, "token": "SECRET_TOKEN",
                       "localServerToken": "SECRET_LOCAL",
                       "cookie": "SECRET_COOKIE", "authorization": "SECRET_AUTH"},
            "draft_root": {"path": "C:/fake/draft", "exists": True, "index": True},
            "ffmpeg": {"ffmpeg": "C:/fake/ffmpeg.exe", "ffprobe": "C:/fake/ffprobe.exe"},
            "cache": {"root": "C:/fake/cache", "exists": True,
                      "packages": {"effect": 3, "artistEffect": 1,
                                   "music": 0, "template": 0}},
            "official_cli": {},
        }
        with mock.patch.object(capability_mod.env_mod, "probe", return_value=fake_env), \
                mock.patch.object(capability_mod, "_burn_ffmpeg",
                                  return_value={"available": True, "path": "C:/ffmpeg.exe",
                                                "source": "user", "version": "9"}), \
                mock.patch.object(capability_mod, "_bridge_health",
                                  return_value={"reachable": False, "version": None,
                                                "build": None, "pid": None,
                                                "note": "BRIDGE_HEALTH_FAILED"}):
            data = capability_mod.probe()
        text = json.dumps(data, ensure_ascii=False).lower()
        for forbidden in ("SECRET_TOKEN".lower(), "SECRET_LOCAL".lower(),
                          "SECRET_COOKIE".lower(), "SECRET_AUTH".lower(),
                          "localServerToken".lower(), "cookie", "authorization"):
            self.assertNotIn(forbidden, text)
        export = next(item for item in data["capabilities"]
                      if item["id"] == "export.render")
        self.assertEqual(export["status"], "conditional")
        self.assertFalse(data["environment"]["bridge"]["reachable"])
        statuses = {item["status"] for item in data["capabilities"]}
        self.assertIn("implemented", statuses)
        self.assertIn("planned", statuses)
        self.assertIn("conditional", statuses)
        self.assertIn("host_only", statuses)
        self.assertIn("account_gated", statuses)
        self.assertEqual(data["summary"]["total"], len(data["capabilities"]))


class AuditFixTests(unittest.TestCase):
    """2026-11-17 质量审计修复的回归测试。"""

    def _minimal_draft(self, root: Path) -> Path:
        draft = root / "draft"
        draft.mkdir()
        (draft / "draft_info.json").write_text(json.dumps({
            "id": "DRAFT-1", "name": "n", "duration": 1_000_000,
            "materials": {}, "tracks": []}), "utf-8")
        versions_mod.record_initial(draft)
        return draft

    def test_workflow_force_keeps_old_srt_when_asr_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            audio = root / "a.wav"
            audio.write_bytes(b"audio")
            srt = root / "a.srt"
            srt.write_text("OLD", "utf-8")

            def failed_run(command, **_kwargs):
                return subprocess.CompletedProcess(
                    command, 1,
                    json.dumps({"ok": False, "code": "missing-dep",
                                "detail": "缺 onnxruntime"}), "")

            with mock.patch.object(workflow_mod.subprocess, "run",
                                   side_effect=failed_run):
                with self.assertRaises(SkillError) as caught:
                    workflow_mod.generate_local_asr_srt(audio, srt, force=True)
            self.assertEqual(caught.exception.code, "missing-dep")
            self.assertEqual(srt.read_text("utf-8"), "OLD")
            self.assertEqual(sorted(p.name for p in root.iterdir()),
                             ["a.srt", "a.wav"])

    def test_workflow_force_publishes_temp_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            audio = root / "a.wav"
            audio.write_bytes(b"audio")
            srt = root / "a.srt"
            srt.write_text("OLD", "utf-8")
            json_path = root / "a.json"
            json_path.write_text("OLD", "utf-8")

            def ok_run(command, **_kwargs):
                out = Path(command[command.index("--out") + 1])
                jout = Path(command[command.index("--json-out") + 1])
                self.assertNotEqual(out, srt)
                self.assertNotEqual(jout, json_path)
                out.write_text("NEW", "utf-8")
                jout.write_text("{}", "utf-8")
                return subprocess.CompletedProcess(
                    command, 0,
                    json.dumps({"ok": True,
                                "data": {"srt": str(out), "json": str(jout)}}), "")

            with mock.patch.object(workflow_mod.subprocess, "run",
                                   side_effect=ok_run):
                result = workflow_mod.generate_local_asr_srt(
                    audio, srt, json_out=json_path, force=True)
            self.assertEqual(srt.read_text("utf-8"), "NEW")
            self.assertEqual(json_path.read_text("utf-8"), "{}")
            self.assertEqual(result["data"]["srt"], str(srt))
            self.assertEqual(result["data"]["json"], str(json_path))
            self.assertEqual(sorted(p.name for p in root.iterdir()),
                             ["a.json", "a.srt", "a.wav"])

    def test_stale_lock_requires_dead_owner(self):
        with tempfile.TemporaryDirectory() as tmp:
            draft = self._minimal_draft(Path(tmp))
            lock = draft / versions_mod.VERSION_DIR / ".lock"
            lock.mkdir()
            (lock / "owner.json").write_text(json.dumps(
                {"pid": os.getpid(), "token": "live"}), "utf-8")
            self.assertFalse(versions_mod._remove_stale_lock(
                lock, versions_mod._read_lock_owner(lock)))
            self.assertTrue(lock.is_dir())
            if versions_mod._pid_alive(2 ** 30) is not False:
                self.skipTest("tasklist 不可用，无法判定陈旧锁")
            (lock / "owner.json").write_text(json.dumps(
                {"pid": 2 ** 30, "token": "dead"}), "utf-8")
            self.assertTrue(versions_mod._remove_stale_lock(
                lock, versions_mod._read_lock_owner(lock)))
            self.assertFalse(lock.exists())

    def test_history_lock_release_does_not_remove_foreign_owner(self):
        with tempfile.TemporaryDirectory() as tmp:
            draft = self._minimal_draft(Path(tmp))
            lock = draft / versions_mod.VERSION_DIR / ".lock"
            with versions_mod._history_lock(draft):
                (lock / "owner.json").write_text(json.dumps(
                    {"pid": os.getpid(), "token": "foreign"}), "utf-8")
            self.assertTrue(lock.is_dir())
            shutil.rmtree(lock)

    def test_restore_failure_leaves_no_partial_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            draft = self._minimal_draft(root)
            out = root / "restored"
            with mock.patch.object(
                    versions_mod, "record_initial",
                    side_effect=SkillError("boom", code="VERSION_WRITE_FAILED")):
                with self.assertRaises(SkillError):
                    versions_mod.restore_version(draft, "v001", out)
            self.assertFalse(out.exists())
            self.assertEqual(
                [p.name for p in root.iterdir() if "restore-tmp" in p.name], [])

    def test_audio_segment_rejects_speed_and_curve_speed(self):
        for field in ("speed", "curve_speed"):
            with tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                audio = root / "a.mp3"
                audio.write_bytes(b"x")
                plan = root / "plan.json"
                write_json(plan, {
                    "schema": "jianying-plan/v1", "name": "audio",
                    "canvas": {"width": 640, "height": 360, "fps": 30},
                    "tracks": [{"type": "audio", "segments": [
                        {"path": "a.mp3", "duration": 2, field: 2}]}],
                })
                info = {"path": str(audio.resolve()), "name": "a.mp3",
                        "kind": "audio", "duration": 4.0, "width": 0,
                        "height": 0, "fps": 0.0, "has_video": False,
                        "has_audio": True, "codec": "mp3"}
                with mock.patch.object(env_mod, "find_install",
                                       return_value=None), \
                        mock.patch.object(
                            env_mod, "find_ffmpeg",
                            return_value={"ffmpeg": None, "ffprobe": None}), \
                        mock.patch.object(draft_mod.media_mod, "probe_media",
                                          return_value=info):
                    with self.assertRaises(SkillError) as caught:
                        draft_mod.build(plan, root / "out", make_cover=False)
                self.assertEqual(caught.exception.code, "VALIDATION")
                self.assertFalse((root / "out").exists())

    def test_patch_rejects_audio_set_speed(self):
        document = {
            "materials": {"audios": [{"id": "A1"}]},
            "tracks": [{"type": "audio", "segments": [{
                "material_id": "A1",
                "target_timerange": {"start": 0, "duration": 2_000_000},
                "source_timerange": {"start": 0, "duration": 2_000_000},
            }]}],
        }
        with self.assertRaises(SkillError) as caught:
            draft_mod._apply_op(
                document, {"op": "set_speed", "segment": 0, "speed": 2})
        self.assertEqual(caught.exception.code, "VALIDATION")

    def test_scale_keyframe_vector_splits_per_channel(self):
        segment = {"target_timerange": {"duration": 4_000_000},
                   "extra_material_refs": []}
        draft_mod._apply_keyframes(segment, {"scale": [
            {"time": 0, "values": [1.5, 0.5]},
            {"time": 2, "values": [1, 1]},
        ]})
        channels = segment["common_keyframes"]
        self.assertEqual([c["property_type"] for c in channels],
                         ["KFTypeScaleX", "KFTypeScaleY"])
        self.assertEqual(
            [[k["values"] for k in c["keyframe_list"]] for c in channels],
            [[[1.5], [1.0]], [[0.5], [1.0]]])
        with self.assertRaises(SkillError) as caught:
            draft_mod._apply_keyframes(
                {"target_timerange": {"duration": 4_000_000},
                 "extra_material_refs": []},
                {"scale": [{"time": 0, "values": [1, 2, 3]},
                           {"time": 1, "values": [1, 1]}]})
        self.assertEqual(caught.exception.code, "VALIDATION")

    def test_known_keys_cover_actual_reads(self):
        for key, value in (("line_max_width", 0.5), ("green_screen", {}),
                           ("caption_duration_info", {}), ("beautify", {"smooth": 1})):
            self.assertIsNone(
                draft_mod._warn_unknown_segment_keys({key: value}),
                f"{key} 应被视为已接线字段")

    def test_plan_paths_reject_unc(self):
        with self.assertRaises(SkillError) as caught:
            draft_mod._audio_effect_param_schema(r"\\10.0.0.5\share")
        self.assertEqual(caught.exception.code, "UNSAFE_PATH")
        with self.assertRaises(SkillError) as caught:
            draft_mod._add_subtitles({}, {"srt": r"\\10.0.0.5\share\x.srt"})
        self.assertEqual(caught.exception.code, "UNSAFE_PATH")

    def test_resource_target_rejects_escaping_components(self):
        with tempfile.TemporaryDirectory() as tmp:
            cache = Path(tmp)
            for md5, effect_id in ((r"..\..\x", "1"), ("a" * 32, r"..\x")):
                with self.assertRaises(SkillError) as caught:
                    resources_mod._target_dir(cache, "flower2", effect_id, md5)
                self.assertEqual(caught.exception.code, "RESOURCE_PATH_INVALID")
            target = resources_mod._target_dir(
                cache, "flower2", "111", "0123456789abcdef0123456789abcdef")
            self.assertTrue(target.resolve().is_relative_to(cache.resolve()))

    def test_download_records_archive_md5_and_installs(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            db, cache = ResourceCatalogTests._fixture(None, root)
            buffer = io.BytesIO()
            with zipfile.ZipFile(buffer, "w") as bundle:
                bundle.writestr("config.json", "{}")
            payload = buffer.getvalue()
            with mock.patch.object(
                    resources_mod, "_open_url",
                    return_value=contextlib.closing(io.BytesIO(payload))):
                result = resources_mod.download_resource(
                    "111", db_path=db, cache_root=cache, apply=True, force=True)
            self.assertEqual(result["archive_md5"],
                             hashlib.md5(payload).hexdigest())
            self.assertEqual(result["db_md5"], "hash-free")
            self.assertTrue(Path(result["cache_path"]).is_dir())
            again = resources_mod.download_resource(
                "111", db_path=db, cache_root=cache)
            self.assertTrue(again["already_cached"])
            self.assertEqual(again["db_md5"], "hash-free")

    def test_download_rejects_http_unless_allowed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            db, cache = ResourceCatalogTests._fixture(None, root)
            connection = sqlite3.connect(db)
            connection.execute("update effect set item_urls=? where id='111'",
                               ('["http://example.invalid/pkg.zip"]',))
            connection.commit()
            connection.close()
            with self.assertRaises(SkillError) as caught:
                resources_mod.download_resource(
                    "111", db_path=db, cache_root=cache, apply=True, force=True)
            self.assertEqual(caught.exception.code, "UNSAFE_URL")
            self.assertEqual(caught.exception.details["hosts"], ["example.invalid"])

            self.assertEqual(resources_mod._parse_urls(
                '["http://a/x","https://b/y"]'), ["https://b/y"])
            self.assertEqual(resources_mod._parse_urls(
                '["http://a/x","https://b/y"]', allow_http=True),
                ["http://a/x", "https://b/y"])

            buffer = io.BytesIO()
            with zipfile.ZipFile(buffer, "w") as bundle:
                bundle.writestr("config.json", "{}")
            payload = buffer.getvalue()
            with mock.patch.object(
                    resources_mod, "_open_url",
                    return_value=contextlib.closing(io.BytesIO(payload))):
                result = resources_mod.download_resource(
                    "111", db_path=db, cache_root=cache, apply=True, force=True,
                    allow_http=True)
            self.assertTrue(result["applied"])
            self.assertTrue(Path(result["cache_path"]).is_dir())

            class Redirected(io.BytesIO):
                def geturl(self):
                    return "http://example.invalid/pkg.zip"

            # 302 跳到 http：读 body 前就拒绝
            connection = sqlite3.connect(db)
            connection.execute("update effect set item_urls=? where id='111'",
                               ('["https://example.invalid/pkg.zip"]',))
            connection.commit()
            connection.close()
            with mock.patch.object(
                    resources_mod, "_open_url",
                    return_value=contextlib.closing(Redirected(payload))):
                with self.assertRaises(SkillError) as caught:
                    resources_mod.download_resource(
                        "111", db_path=db, cache_root=cache, apply=True, force=True)
            self.assertEqual(caught.exception.code, "UNSAFE_URL")
            self.assertIn("http://example.invalid", caught.exception.details["url"])

            # 混合 https+http：http 地址不能静默消失
            connection = sqlite3.connect(db)
            connection.execute("update effect set item_urls=? where id='111'",
                               ('["http://example.invalid/pkg.zip",'
                                '"https://example.invalid/pkg.zip"]',))
            connection.commit()
            connection.close()
            with mock.patch.object(
                    resources_mod, "_open_url",
                    return_value=contextlib.closing(io.BytesIO(payload))):
                mixed = resources_mod.download_resource(
                    "111", db_path=db, cache_root=cache, apply=True, force=True)
            self.assertEqual(mixed["skipped_insecure_url_count"], 1)

    def test_download_rejects_private_targets(self):
        self.assertTrue(resources_mod._is_private_target("https://127.0.0.1/x"))
        self.assertTrue(resources_mod._is_private_target("https://10.1.2.3/x"))
        self.assertTrue(resources_mod._is_private_target("https://[::1]/x"))
        self.assertFalse(resources_mod._is_private_target("https://example.invalid/x"))
        handler = resources_mod._GuardedRedirect(allow_http=False, item_id="111")
        for target in ("http://example.invalid/x", "https://127.0.0.1/x"):
            with self.assertRaises(SkillError) as caught:
                handler.redirect_request(None, None, 302, "Found", {}, target)
            self.assertEqual(caught.exception.code, "UNSAFE_URL")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            db, cache = ResourceCatalogTests._fixture(None, root)
            connection = sqlite3.connect(db)
            connection.execute("update effect set item_urls=? where id='111'",
                               ('["https://127.0.0.1/pkg.zip"]',))
            connection.commit()
            connection.close()
            with self.assertRaises(SkillError) as caught:
                resources_mod.download_resource(
                    "111", db_path=db, cache_root=cache, apply=True, force=True)
            self.assertEqual(caught.exception.code, "UNSAFE_URL")

    def test_install_archive_caps_actual_bytes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            archive = root / "pkg.zip"
            with zipfile.ZipFile(archive, "w",
                                 compression=zipfile.ZIP_DEFLATED) as bundle:
                bundle.writestr("config.json", "{}")
                bundle.writestr("big.bin", b"x" * 4096)
            original = zipfile.ZipFile.infolist

            def shrink(self):
                infos = original(self)
                for info in infos:
                    info.file_size = 0
                return infos

            with mock.patch.object(resources_mod, "_MAX_ARCHIVE_BYTES", 1024), \
                    mock.patch.object(zipfile.ZipFile, "infolist", shrink):
                with self.assertRaises(SkillError) as caught:
                    resources_mod.install_archive(archive, root / "target")
            self.assertEqual(caught.exception.code, "PACKAGE_INVALID")
            self.assertFalse((root / "target").exists())

    def test_bridge_descriptor_prefers_newest(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            older = root / "old"
            newer = root / "new"
            older.mkdir()
            newer.mkdir()
            write_json(older / env_mod.BRIDGE_NAME, {"token": "a", "port": 1111})
            write_json(newer / env_mod.BRIDGE_NAME, {"token": "b", "port": 2222})
            os.utime(older / env_mod.BRIDGE_NAME, (1000, 1000))
            with mock.patch.object(env_mod, "_temp_dirs",
                                   return_value=[older, newer]):
                found = env_mod.find_bridge_descriptor()
            self.assertEqual(found["port"], 2222)

    def test_local_asr_rejects_noncompliant_cues(self):
        import importlib.util
        subtitles = str(ROOT / "subtitles")
        sys.path.insert(0, subtitles)
        try:
            spec = importlib.util.spec_from_file_location(
                "_jy_local_asr_fix", ROOT / "subtitles" / "local_asr.py")
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
        finally:
            sys.path.remove(subtitles)
        with self.assertRaises(Exception) as caught:
            module.checked_cues(
                [{"text": "字", "start": 0.0, "end": 9.0}],
                max_dur=5.5, max_chars=16)
        self.assertEqual(getattr(caught.exception, "code", None), "srt-check")
        ordered = module.checked_cues(
            [{"text": "正常", "start": 0.0, "end": 1.0}],
            max_dur=5.5, max_chars=16)
        self.assertEqual(len(ordered), 1)
        borderline = module.checked_cues(
            [{"text": "字", "start": 0.0, "end": 5.9}],
            max_dur=max(5.0 + 0.5, 6.0), max_chars=16)
        self.assertEqual(len(borderline), 1)

    def test_lock_owner_missing_needs_age(self):
        with tempfile.TemporaryDirectory() as tmp:
            draft = self._minimal_draft(Path(tmp))
            lock = draft / versions_mod.VERSION_DIR / ".lock"
            lock.mkdir()
            self.assertFalse(versions_mod._remove_stale_lock(lock, None))
            old = time.time() - 120
            os.utime(lock, (old, old))
            self.assertTrue(versions_mod._remove_stale_lock(lock, None))
            self.assertFalse(lock.exists())

    def test_history_lock_recovers_old_dead_lock(self):
        if versions_mod._pid_alive(2 ** 30) is not False:
            self.skipTest("tasklist 不可用，无法判定陈旧锁")
        with tempfile.TemporaryDirectory() as tmp:
            draft = self._minimal_draft(Path(tmp))
            lock = draft / versions_mod.VERSION_DIR / ".lock"
            lock.mkdir()
            (lock / "owner.json").write_text(json.dumps(
                {"pid": 2 ** 30, "token": "dead"}), "utf-8")
            old = time.time() - 120
            os.utime(lock, (old, old))
            with versions_mod._history_lock(draft):
                pass
            self.assertFalse(lock.exists())

    def test_workflow_keeps_temp_when_srt_publish_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            audio = root / "a.wav"
            audio.write_bytes(b"audio")
            srt_dir = root / "a.srt"
            srt_dir.mkdir()
            json_path = root / "a.json"
            json_path.write_text("OLDJSON", "utf-8")

            def run(command, **_kwargs):
                out = Path(command[command.index("--out") + 1])
                jout = Path(command[command.index("--json-out") + 1])
                out.write_text("NEWSRT", "utf-8")
                jout.write_text("NEWJSON", "utf-8")
                return subprocess.CompletedProcess(
                    command, 0,
                    json.dumps({"ok": True,
                                "data": {"srt": str(out), "json": str(jout)}}), "")

            with mock.patch.object(workflow_mod.subprocess, "run",
                                   side_effect=run):
                with self.assertRaises(SkillError) as caught:
                    workflow_mod.generate_local_asr_srt(
                        audio, srt_dir, json_out=json_path, force=True)
            self.assertEqual(caught.exception.code, "OUTPUT_WRITE_FAILED")
            self.assertTrue(srt_dir.is_dir())
            self.assertEqual(json_path.read_text("utf-8"), "OLDJSON")
            temps = [p for p in root.iterdir()
                     if p.name.startswith(".a.srt.") and p.is_file()]
            self.assertEqual(len(temps), 1)
            self.assertEqual(temps[0].read_text("utf-8"), "NEWSRT")

    def test_media_rejects_mapped_drive_and_drive_relative(self):
        with mock.patch.object(media_mod, "_is_remote_drive", return_value=True):
            with self.assertRaises(SkillError) as caught:
                media_mod.local_path("Z:/share/a.mp4", field="素材")
        self.assertEqual(caught.exception.code, "UNSAFE_PATH")
        if os.name == "nt":
            with self.assertRaises(SkillError) as caught:
                media_mod.local_path("C:foo.srt", field="SRT")
            self.assertEqual(caught.exception.code, "UNSAFE_PATH")
        self.assertEqual(media_mod.local_path("subs/a.srt").as_posix(),
                         "subs/a.srt")

    def test_plan_extras_paths_resolve_relative_to_plan(self):
        plan = {"tracks": [{"type": "video", "segments": [{
            "path": "media/a.mp4",
            "audio_effect": {"path": "pkg/audio"},
            "matting": {"path": "pkg/mask", "mask_video_path": "pkg/mask2"},
            "text_template": {"path": "pkg/tpl",
                              "resources": [{"path": "pkg/res"}]},
        }]}]}
        base = Path("D:/plans") if os.name == "nt" else Path("/plans")
        draft_mod._resolve_relative_extras_paths(plan, base)
        segment = plan["tracks"][0]["segments"][0]
        for value in (segment["audio_effect"]["path"],
                      segment["matting"]["path"],
                      segment["matting"]["mask_video_path"],
                      segment["text_template"]["path"],
                      segment["text_template"]["resources"][0]["path"]):
            self.assertTrue(Path(value).is_absolute(), value)
        absolute = str((base / "abs").resolve())
        plan2 = {"tracks": [{"type": "video", "segments": [
            {"audio_effect": {"path": absolute}}]}]}
        draft_mod._resolve_relative_extras_paths(plan2, base)
        self.assertEqual(
            plan2["tracks"][0]["segments"][0]["audio_effect"]["path"], absolute)

    def test_download_caps_bytes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            db, cache = ResourceCatalogTests._fixture(None, root)
            with mock.patch.object(resources_mod, "_MAX_DOWNLOAD_BYTES", 10), \
                    mock.patch.object(
                        resources_mod, "_open_url",
                        return_value=contextlib.closing(
                            io.BytesIO(b"x" * 100))):
                with self.assertRaises(SkillError) as caught:
                    resources_mod.download_resource(
                        "111", db_path=db, cache_root=cache,
                        apply=True, force=True)
            self.assertEqual(caught.exception.code, "PACKAGE_INVALID")

    def test_bridge_descriptor_prefers_live_pid(self):
        if env_mod._pid_alive(2 ** 30) is not False:
            self.skipTest("tasklist 不可用，无法判定死 pid")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            older = root / "old"
            newer = root / "new"
            older.mkdir()
            newer.mkdir()
            write_json(older / env_mod.BRIDGE_NAME,
                       {"token": "a", "port": 1111, "pid": os.getpid()})
            write_json(newer / env_mod.BRIDGE_NAME,
                       {"token": "b", "port": 2222, "pid": 2 ** 30})
            os.utime(older / env_mod.BRIDGE_NAME, (1000, 1000))
            with mock.patch.object(env_mod, "_temp_dirs",
                                   return_value=[older, newer]):
                found = env_mod.find_bridge_descriptor()
            self.assertEqual(found["port"], 1111)

    def test_editor_guard_reports_unknown_without_tasklist(self):
        with mock.patch.object(index_mod.subprocess, "run",
                               side_effect=OSError("no tasklist")):
            self.assertEqual(index_mod._ensure_editor_closed(), "unknown")
        failed = mock.Mock(stdout="", returncode=1)
        with mock.patch.object(index_mod.subprocess, "run", return_value=failed):
            self.assertEqual(index_mod._ensure_editor_closed(), "unknown")


class UpgradeCheckTests(unittest.TestCase):
    """升级体检：版本窗口 + 能力矩阵漂移，不联网、不自替换。"""

    VERSION = {
        "app_baseline": "11.8.0",
        "behavior_tested": "11.8.0",
        "build_tested": "14778",
        "supported": {"min": "11.8.0", "max": "11.8.0"},
        "skill_version": "1.2.5",
    }

    def _policy(self, status, note=""):
        return {
            "status": status, "note": note,
            "install_version": "11.8.0.14778", "install_build": "14778",
            "in_range": status != "unsupported",
            "behavior_match": status == "verified",
            "build_match": True,
        }

    def test_verified_without_drift_is_ok(self):
        report = upgrade_mod.build_report(
            self.VERSION, {"version": "11.8.0.14778"},
            self._policy("verified"), {"draft.build": "implemented"})
        self.assertEqual(report["status"], "ok")
        self.assertEqual(report["exit_code"], 0)
        self.assertEqual(report["drift"]["capabilities"], [])

    def test_unsupported_requires_migration_checklist(self):
        report = upgrade_mod.build_report(
            self.VERSION, {"version": "11.9.0.14778"},
            self._policy("unsupported", "install 11.9.0 超出 supported"),
            {"draft.build": "implemented"})
        self.assertEqual(report["status"], "attention")
        self.assertEqual(report["exit_code"], 10)
        self.assertTrue(any("history" in item for item in report["checklist"]))
        self.assertTrue(any("build → render → verify" in item
                            for item in report["checklist"]))

    def test_capability_drift_reported(self):
        baseline = {
            "schema": upgrade_mod.SCHEMA,
            "install": {"version": "11.8.0.14778"},
            "capabilities": {"a": "implemented", "b": "conditional"},
        }
        report = upgrade_mod.build_report(
            self.VERSION, {"version": "11.8.0.14778"},
            self._policy("verified"),
            {"a": "implemented", "b": "unverified", "c": "planned"},
            baseline=baseline)
        self.assertEqual(report["status"], "attention")
        self.assertEqual(
            [(item["id"], item["baseline"], item["current"])
             for item in report["drift"]["capabilities"]],
            [("b", "conditional", "unverified"), ("c", None, "planned")])

    def test_save_and_load_baseline_roundtrip(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "baseline.json"
            report = upgrade_mod.build_report(
                self.VERSION, {"version": "11.8.0.14778"},
                self._policy("verified"), {"draft.build": "implemented"})
            saved = upgrade_mod.save_report(path, report)
            self.assertEqual(saved, str(path))
            loaded = upgrade_mod.load_baseline(path)
            self.assertEqual(loaded["capabilities"], {"draft.build": "implemented"})
            self.assertEqual(loaded["install"]["version"], "11.8.0.14778")
            with self.assertRaises(SkillError) as caught:
                upgrade_mod.save_report(path, report)
            self.assertEqual(caught.exception.code, "OUTPUT_EXISTS")

    def test_install_version_drift_reported(self):
        baseline = {
            "schema": upgrade_mod.SCHEMA,
            "install": {"version": "11.8.0.14778"},
            "capabilities": {"a": "implemented"},
        }
        report = upgrade_mod.build_report(
            self.VERSION, {"version": "11.8.0.15000"},
            self._policy("verified"), {"a": "implemented"},
            baseline=baseline)
        self.assertEqual(report["status"], "attention")
        self.assertEqual(report["drift"]["install"],
                         {"baseline": "11.8.0.14778",
                          "current": "11.8.0.15000"})

    def test_probe_failure_is_not_reported_as_capability_drift(self):
        baseline = {
            "schema": upgrade_mod.SCHEMA,
            "install": {"version": "11.8.0.14778"},
            "capabilities": {"a": "implemented"},
        }
        report = upgrade_mod.build_report(
            self.VERSION, {"version": "11.8.0.14778"},
            self._policy("verified"), {}, baseline=baseline,
            capability_errors=["probe boom"])
        self.assertEqual(report["drift"]["capabilities"], [])
        self.assertTrue(any("能力探测失败" in reason
                            for reason in report["reasons"]))
        self.assertTrue(any("probe" in item for item in report["checklist"]))

    def test_load_baseline_rejects_bad_types_and_unc(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "bad.json"
            for payload in (
                    {"schema": upgrade_mod.SCHEMA, "capabilities": []},
                    {"schema": upgrade_mod.SCHEMA, "capabilities": {"a": 1}},
                    {"schema": upgrade_mod.SCHEMA, "capabilities": {},
                     "install": "x"}):
                path.write_text(json.dumps(payload), "utf-8")
                with self.assertRaises(SkillError) as caught:
                    upgrade_mod.load_baseline(path)
                self.assertEqual(caught.exception.code, "VALIDATION")
        with self.assertRaises(SkillError) as caught:
            upgrade_mod.load_baseline(r"\\10.0.0.5\share\b.json")
        self.assertEqual(caught.exception.code, "UNSAFE_PATH")

    def test_save_refuses_foreign_or_directory_target(self):
        with tempfile.TemporaryDirectory() as tmp:
            report = upgrade_mod.build_report(
                self.VERSION, {"version": "11.8.0.14778"},
                self._policy("verified"), {"a": "implemented"})
            foreign = Path(tmp) / "version.json"
            foreign.write_text('{"x":1}', "utf-8")
            with self.assertRaises(SkillError) as caught:
                upgrade_mod.save_report(foreign, report, force=True)
            self.assertEqual(caught.exception.code, "VALIDATION")
            self.assertEqual(foreign.read_text("utf-8"), '{"x":1}')
            with self.assertRaises(SkillError) as caught:
                upgrade_mod.save_report(Path(tmp), report, force=True)
            self.assertEqual(caught.exception.code, "VALIDATION")

    def test_main_save_failure_returns_error_envelope(self):
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.object(
                    env_mod, "find_install",
                    return_value={"dir": "C:/fake",
                                  "version": "11.8.0.14778"}), \
                    mock.patch.object(env_mod, "version_policy",
                                      return_value=self._policy("verified")), \
                    mock.patch.object(upgrade_mod.cap_mod, "probe",
                                      return_value={"capabilities": [
                                          {"id": "draft.build",
                                           "status": "implemented"}]}), \
                    mock.patch.object(
                        upgrade_mod, "save_report",
                        side_effect=SkillError(
                            "写入失败", code="OUTPUT_WRITE_FAILED")), \
                    contextlib.redirect_stdout(io.StringIO()) as out:
                code = upgrade_mod.main(
                    ["--save", str(Path(tmp) / "baseline.json")])
        self.assertEqual(code, 2)
        payload = json.loads(out.getvalue())
        self.assertFalse(payload["ok"])
        self.assertEqual(payload["error"]["code"], "OUTPUT_WRITE_FAILED")

    def test_main_refuses_saving_empty_capabilities(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "baseline.json"
            with mock.patch.object(
                    env_mod, "find_install",
                    return_value={"dir": "C:/fake",
                                  "version": "11.8.0.14778"}), \
                    mock.patch.object(env_mod, "version_policy",
                                      return_value=self._policy("verified")), \
                    mock.patch.object(upgrade_mod.cap_mod, "probe",
                                      return_value={"capabilities": []}), \
                    contextlib.redirect_stdout(io.StringIO()) as out:
                code = upgrade_mod.main(["--save", str(target)])
            self.assertEqual(code, 2)
            self.assertFalse(json.loads(out.getvalue())["ok"])
            self.assertFalse(target.exists())

    def test_runtime_environment_is_not_capability_drift(self):
        baseline = {
            "schema": upgrade_mod.SCHEMA,
            "skill_version": "1.2.5",
            "install": {"version": "11.8.0.14778"},
            "capabilities": {"export.render": "conditional"},
        }
        report = upgrade_mod.build_report(
            self.VERSION, {"version": "11.8.0.14778"},
            self._policy("verified"), {"export.render": "conditional"},
            baseline=baseline,
            runtime_capabilities={"export.render": "implemented"})
        self.assertEqual(report["drift"]["capabilities"], [])
        self.assertEqual(report["runtime_capabilities"],
                         {"export.render": "implemented"})
        self.assertEqual(report["status"], "ok")

    def test_baseline_skill_version_mismatch_is_attention(self):
        baseline = {
            "schema": upgrade_mod.SCHEMA,
            "skill_version": "1.2.4",
            "install": {"version": "11.8.0.14778"},
            "capabilities": {"a": "implemented"},
        }
        report = upgrade_mod.build_report(
            self.VERSION, {"version": "11.8.0.14778"},
            self._policy("verified"), {"a": "implemented"},
            baseline=baseline)
        self.assertEqual(report["status"], "attention")
        self.assertTrue(any("重新留基线" in reason
                            for reason in report["reasons"]))

    def test_without_baseline_reports_no_comparison(self):
        report = upgrade_mod.build_report(
            self.VERSION, {"version": "11.8.0.14778"},
            self._policy("verified"), {"a": "implemented"})
        self.assertFalse(report["baseline_compared"])
        self.assertEqual(report["status"], "ok")
        self.assertTrue(any("未提供 --baseline" in item
                            for item in report["checklist"]))

    def test_main_emits_json_and_attention_exit(self):
        policy = self._policy("unsupported", "install 11.9.0 超出 supported")
        with mock.patch.object(env_mod, "find_install",
                               return_value={"dir": "C:/fake",
                                             "version": "11.9.0.14778"}), \
                mock.patch.object(env_mod, "version_policy",
                                  return_value=policy), \
                mock.patch.object(upgrade_mod.cap_mod, "probe",
                                  return_value={"capabilities": [
                                      {"id": "draft.build",
                                       "status": "implemented"}]}), \
                contextlib.redirect_stdout(io.StringIO()) as out:
            code = upgrade_mod.main([])
        self.assertEqual(code, 10)
        payload = json.loads(out.getvalue())
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["data"]["status"], "attention")


class InterchangeTests(unittest.TestCase):
    """模板、ASS、OTIO、媒体分析与维护命令的离线契约。"""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def _probe(self, kind="video"):
        if kind == "audio":
            return {"path": "audio.m4a", "name": "audio.m4a", "kind": "audio",
                    "duration": 4.0, "width": 0, "height": 0, "fps": 0.0,
                    "has_video": False, "has_audio": True, "codec": "aac"}
        if kind == "image":
            return {"path": "image.png", "name": "image.png", "kind": "image",
                    "duration": 0.0, "width": 320, "height": 180, "fps": 0.0,
                    "has_video": True, "has_audio": False, "codec": "png"}
        return {"path": "video.mp4", "name": "video.mp4", "kind": "video",
                "duration": 6.0, "width": 640, "height": 360, "fps": 30.0,
                "has_video": True, "has_audio": True, "codec": "h264"}

    def _build_with_probe(self, plan_path, out, *, side_effect=None, return_value=None):
        patches = [
            mock.patch.object(env_mod, "find_install", return_value=None),
            mock.patch.object(env_mod, "find_ffmpeg",
                              return_value={"ffmpeg": None, "ffprobe": None}),
        ]
        if side_effect is not None:
            patches.append(mock.patch.object(draft_mod.media_mod, "probe_media",
                                             side_effect=side_effect))
        elif return_value is not None:
            patches.append(mock.patch.object(draft_mod.media_mod, "probe_media",
                                             return_value=return_value))
        for item in patches:
            item.start()
        try:
            return draft_mod.build(plan_path, out, make_cover=False)
        finally:
            for item in patches:
                item.stop()

    def _text_draft(self, name="text", text="第一句"):
        plan = self.root / f"{name}.json"
        write_json(plan, {
            "schema": "jianying-plan/v1", "name": name,
            "canvas": {"width": 640, "height": 360, "fps": 30},
            "tracks": [{"type": "text", "segments": [{
                "text": text, "start": 0.2, "duration": 2.0,
                "font_size": 8, "y": -0.72, "color": "#FF0000",
                "stroke_color": "#00FF00", "stroke_width": 2,
            }]}],
        })
        out = self.root / name
        return self._build_with_probe(plan, out), out

    def test_beauty_material_build_and_integration(self):
        figures = beauty_mod.build({
            "skin": {"smooth": 100, "whitening": 50},
            "shape": {"small_face": 60},
            "makeup": {"look": "淡人妆", "intensity": 80},
        }, video_material_id="video-1", placeholder_id="PLACE")
        self.assertEqual(len(figures), 5)
        names = [item["name"] for item in figures]
        self.assertEqual(names, ["磨皮", "美白", "小脸", "淡人妆", "makeup-root"])
        smooth, whitening, shape, makeup, root = figures
        self.assertEqual(smooth["value"], 1.0)
        self.assertTrue(smooth["algorithm_artifact_path"].endswith("/video-1"))
        self.assertEqual(whitening["value"], 0.5)
        self.assertEqual(whitening["algorithm_artifact_path"], "")
        self.assertEqual(shape["adjust_params"][0]["name"], "0")
        self.assertEqual(shape["adjust_params"][0]["value"], 0.6)
        self.assertEqual(makeup["face_adjust_params"][0]["adjust_params"][0]["name"],
                         "face_adjust_whole")
        self.assertEqual(root["type"], "makeup_root")

        plan = self.root / "beauty-plan.json"
        write_json(plan, {
            "schema": "jianying-plan/v1", "name": "美颜",
            "canvas": {"width": 640, "height": 360, "fps": 30},
            "tracks": [{"type": "video", "segments": [{
                "path": "video.mp4", "start": 0, "duration": 2.0,
                "beauty": {"skin": {"smooth": 100}},
            }]}],
        })
        out = self.root / "beauty"
        result = self._build_with_probe(plan, out, return_value=self._probe("video"))
        document = json.loads((out / "draft_info.json").read_text("utf-8"))
        figures = [item for item in document["materials"]["effects"]
                   if item.get("type") == "figure"]
        self.assertEqual(len(figures), 1)
        self.assertFalse(any(item.get("type") == "makeup_root" for item in figures))
        self.assertEqual(figures[0]["resource_id"], "6976822940608238093")
        segment = document["tracks"][0]["segments"][0]
        self.assertIn(figures[0]["id"], segment["extra_material_refs"])
        info = draft_mod.inspect(out)
        self.assertIn("beauty", [item["type"] for item in info["video_extras"]])
        self.assertTrue(any("beauty" in str(item) for item in result["warnings"]))
        self.assertTrue(any("native bridge" in str(item) and "界面导出" in str(item)
                            for item in result["warnings"]))

    def test_beauty_all_zero_does_not_claim_written(self):
        plan = self.root / "beauty-zero-plan.json"
        write_json(plan, {
            "schema": "jianying-plan/v1", "name": "美颜零值",
            "canvas": {"width": 640, "height": 360, "fps": 30},
            "tracks": [{"type": "video", "segments": [{
                "path": "video.mp4", "start": 0, "duration": 2.0,
                "beauty": {"skin": {"smooth": 0}},
            }]}],
        })
        out = self.root / "beauty-zero"
        result = self._build_with_probe(plan, out, return_value=self._probe("video"))
        document = json.loads((out / "draft_info.json").read_text("utf-8"))
        self.assertFalse(any(item.get("type") == "figure"
                             for item in document["materials"]["effects"]))
        self.assertFalse(any("已写入 materials.effects[type=figure]" in str(item)
                             for item in result["warnings"]))
        self.assertTrue(any("未写入 figure" in str(item) for item in result["warnings"]))

    def test_template_save_and_apply_remaps_ids(self):
        built, source = self._text_draft("template-source")
        document = json.loads((source / "draft_info.json").read_text("utf-8"))
        segment_id = document["tracks"][0]["segments"][0]["id"]
        template_path = self.root / "template.json"
        saved = template_mod.save(source, segment_id, "标题模板", template_path)
        self.assertEqual(saved["type"], "text")
        payload = json.loads(template_path.read_text("utf-8"))
        self.assertEqual(payload["format"], template_mod.FORMAT)
        self.assertEqual(payload["version"], 1)

        target, target_dir = self._text_draft("template-target", "第二句")
        applied = template_mod.apply(target_dir, template_path, 2.2,
                                     text="模板盖印", x=0.1, y=-0.2,
                                     out_dir=self.root / "template-applied")
        result = json.loads((Path(applied["draft_dir"]) / "draft_info.json").read_text("utf-8"))
        texts = result["tracks"][0]["segments"]
        self.assertEqual(len(texts), 2)
        latest = texts[-1]
        self.assertNotEqual(latest["id"], payload["segment"]["id"])
        self.assertEqual(latest["target_timerange"]["start"], 2_200_000)
        material = next(item for item in result["materials"]["texts"]
                        if item["id"] == latest["material_id"])
        content = json.loads(material["content"])
        self.assertEqual(content["text"], "模板盖印")
        self.assertAlmostEqual(latest["clip"]["transform"]["x"], 0.1)

    def test_ass_round_trip_keeps_ranges_and_color(self):
        ass_path = self.root / "subs.ass"
        ass_path.write_text("\n".join([
            "[Script Info]", "ScriptType: v4.00+", "PlayResX: 640", "PlayResY: 360",
            "", "[V4+ Styles]",
            "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
            "Style: Default,Microsoft YaHei,48,&H00FFFFFF,&H00FFFFFF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,2,0,2,10,10,10,1",
            "", "[Events]",
            "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
            "Dialogue: 0,0:00:01.00,0:00:03.00,Default,,0,0,0,,{\\c&H0000FF&}红色{\\r}普通",
        ]), "utf-8")
        parsed = ass_mod.parse_ass(ass_path)
        self.assertEqual(len(parsed["events"]), 1)
        plan = ass_mod.to_plan(parsed)
        segment = plan["tracks"][0]["segments"][0]
        self.assertEqual(segment["text"], "红色普通")
        self.assertEqual(segment["range_styles"][0]["color"], "#FF0000")
        self.assertEqual(segment["range_styles"][0]["start"], 0)
        self.assertEqual(segment["range_styles"][0]["end"], 2)

        _, draft_dir = self._text_draft("ass-export", "红色普通")
        exported = ass_mod.export_draft(draft_dir, self.root / "roundtrip.ass")
        text = Path(exported["out"]).read_text("utf-8-sig")
        self.assertIn("红色普通", text)
        self.assertIn("[Events]", text)

    def test_otio_export_import_skips_text_and_builds(self):
        plan = self.root / "otio-plan.json"
        write_json(plan, {
            "schema": "jianying-plan/v1", "name": "OTIO",
            "canvas": {"width": 640, "height": 360, "fps": 30},
            "tracks": [
                {"type": "video", "segments": [{
                    "path": "video.mp4", "start": 0, "duration": 2.0}]},
                {"type": "audio", "segments": [{
                    "path": "audio.m4a", "start": 0, "duration": 2.0}]},
                {"type": "text", "segments": [{
                    "text": "不会导出", "start": 0, "duration": 1.0}]},
            ],
        })

        def probe(_ffprobe, path):
            return self._probe("audio" if str(path).endswith(".m4a") else "video")

        out = self.root / "otio-draft"
        self._build_with_probe(plan, out, side_effect=probe)
        otio = self.root / "timeline.otio"
        exported = interchange_mod.export_otio(out, otio)
        self.assertEqual(exported["tracks"], 2)
        self.assertEqual(exported["skipped"][0]["type"], "text")
        payload = json.loads(otio.read_text("utf-8"))
        self.assertEqual(payload["OTIO_SCHEMA"], "Timeline.1")

        imported = interchange_mod.import_otio(otio, canvas={"width": 1080, "height": 1920, "fps": 30})
        self.assertEqual(len(imported["tracks"]), 2)
        imported_plan = self.root / "imported.json"
        write_json(imported_plan, {
            "schema": "jianying-plan/v1", "name": imported["name"],
            "canvas": imported["canvas"], "tracks": imported["tracks"],
        })
        result = self._build_with_probe(imported_plan, self.root / "otio-imported",
                                        side_effect=probe)
        self.assertEqual(result["tracks"]["video"], 1)
        self.assertEqual(result["tracks"]["audio"], 1)

    def test_media_tools_parse_and_detect_retakes(self):
        silences = media_tools_mod.parse_silences(
            "[silencedetect @ 0x1] silence_start: 1.20\n"
            "[silencedetect @ 0x1] silence_end: 2.50 | silence_duration: 1.3\n")
        self.assertEqual(silences, [{"start": 1.2, "end": 2.5}])
        scenes = media_tools_mod.parse_scenes(
            "[showinfo @ 0x1] pts_time:0.00\n"
            "[showinfo @ 0x1] pts_time:1.50\n"
            "[showinfo @ 0x1] pts_time:1.70\n", min_gap=0.5)
        self.assertEqual(scenes, [0.0, 1.5])
        report = media_tools_mod.detect_retakes([
            {"text": "今天 我们 来 聊一聊 人工智能", "start": 0, "end": 2},
            {"text": "今天 我们 来 聊一聊 人工智能", "start": 30, "end": 32},
        ], threshold=0.8)
        self.assertEqual(report["cues"], 2)
        self.assertGreaterEqual(report["retakes"][0]["similarity"], 0.8)
        self.assertEqual(report["cuts"][0]["start"], 0.0)

    def test_duplicate_segments_uses_material_and_source_range(self):
        document = {
            "tracks": [{"segments": [
                {"id": "a", "material_id": "m", "source_timerange": {"start": 0, "duration": 1_000_000},
                 "target_timerange": {"start": 0, "duration": 1_000_000}},
                {"id": "b", "material_id": "m", "source_timerange": {"start": 0, "duration": 1_000_000},
                 "target_timerange": {"start": 1_000_000, "duration": 1_000_000}},
                {"id": "c", "material_id": "n", "source_timerange": {"start": 0, "duration": 1_000_000},
                 "target_timerange": {"start": 2_000_000, "duration": 1_000_000}},
            ]}],
            "materials": {},
        }
        draft_dir = self.root / "dup"
        write_json(draft_dir / "draft_info.json", document)
        report = media_tools_mod.duplicate_segments(draft_dir)
        self.assertEqual(len(report["duplicates"]), 1)
        self.assertEqual(report["duplicates"][0]["duplicate"]["segment"], "b")

    def test_relink_replace_and_prune(self):
        media_dir = self.root / "media"
        media_dir.mkdir()
        (media_dir / "old.mp4").write_bytes(b"new")
        plan = self.root / "maintenance-plan.json"
        write_json(plan, {
            "schema": "jianying-plan/v1", "name": "维护",
            "canvas": {"width": 640, "height": 360, "fps": 30},
            "tracks": [{"type": "video", "segments": [{
                "path": str(self.root / "missing" / "old.mp4"), "start": 0, "duration": 2.0}]}],
        })
        out = self.root / "maintenance"
        fake_probe = {"path": str(self.root / "missing" / "old.mp4"), "name": "old.mp4",
                      "kind": "video", "duration": 5.0, "width": 640, "height": 360,
                      "fps": 30.0, "has_video": True, "has_audio": False, "codec": "h264"}
        with mock.patch.object(env_mod, "find_install", return_value=None), \
                mock.patch.object(env_mod, "find_ffmpeg",
                                  return_value={"ffmpeg": None, "ffprobe": None}), \
                mock.patch.object(draft_mod.media_mod, "probe_media",
                                  return_value=fake_probe):
            draft_mod.build(plan, out, make_cover=False)
        relinked = maintenance_mod.relink(out, directory=media_dir,
                                          out_dir=self.root / "relinked")
        self.assertEqual(len(relinked["changes"]), 1)
        self.assertEqual(relinked["missing"], [])
        document = json.loads((Path(relinked["out"]) / "draft_info.json").read_text("utf-8"))
        self.assertIn("old.mp4", document["materials"]["videos"][0]["path"])

        probe = {"path": str(media_dir / "old.mp4"), "name": "old.mp4",
                 "kind": "video", "duration": 2.0, "width": 640, "height": 360,
                 "fps": 30.0, "has_video": True, "has_audio": False, "codec": "h264"}
        with mock.patch.object(maintenance_mod.media_mod, "probe_media",
                               return_value=probe):
            replaced = maintenance_mod.replace_media(
                Path(relinked["out"]), 0, media_dir / "old.mp4", ffprobe="ffprobe",
                out_dir=self.root / "replaced", retime=True)
        self.assertEqual(replaced["new_duration"], 2.0)
        self.assertEqual(replaced["speed"], 1.0)

        orphan_doc = json.loads((Path(relinked["out"]) / "draft_info.json").read_text("utf-8"))
        orphan_doc["materials"]["videos"].append({"id": "orphan", "path": "x.mp4", "duration": 1})
        write_json(Path(relinked["out"]) / "draft_info.json", orphan_doc)
        pruned = maintenance_mod.prune(Path(relinked["out"]),
                                       out_dir=self.root / "pruned")
        self.assertEqual(pruned["removed_count"], 1)
        self.assertEqual(pruned["removed"][0]["id"], "orphan")

    def test_copy_tree_skips_empty_placeholder_dirs(self):
        source = self.root / "copy-source"
        source.mkdir()
        (source / "draft_info.json").write_text("{}", "utf-8")
        empty = source / "##_draftpath_placeholder_X_##" / "video" / "figure_algorithm" / "Y"
        empty.mkdir(parents=True)
        target = self.root / "copy-target"
        media_mod.copy_tree(source, target)
        self.assertTrue((target / "draft_info.json").is_file())
        self.assertFalse((target / "##_draftpath_placeholder_X_##").exists())

    def test_ass_override_tags_report_unsupported_instead_of_swallowing(self):
        r"""\bord/\blur/\be/\iclip 不能被 startswith("b"/"i") 吞成加粗/斜体。"""
        ass_path = self.root / "tags.ass"
        ass_path.write_text("\n".join([
            "[Script Info]", "ScriptType: v4.00+", "PlayResX: 640", "PlayResY: 360",
            "", "[V4+ Styles]",
            "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
            "Style: Default,Microsoft YaHei,48,&H00FFFFFF,&H00FFFFFF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,2,0,2,10,10,10,1",
            "", "[Events]",
            "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
            "Dialogue: 0,0:00:00.00,0:00:02.00,Default,,0,0,0,,{\\bord3\\blur2\\be1}边框",
            "Dialogue: 0,0:00:02.00,0:00:04.00,Default,,0,0,0,,{\\iclip(0,0,100,100)\\b1}裁切",
            "Dialogue: 0,0:00:04.00,0:00:06.00,Default,,0,0,0,,{\\i1}斜体{\\r}{\\u1}下划{\\s1\\k20}杂",
        ]), "utf-8")
        parsed = ass_mod.parse_ass(ass_path)
        self.assertEqual(len(parsed["events"]), 3)
        self.assertEqual(parsed["unsupported_tags"],
                         ["\\be1", "\\blur2", "\\bord3", "\\iclip", "\\k20", "\\s1"])
        # 边框/裁切标签不再被误判成加粗：第一条事件的样式区间保持常规。
        self.assertFalse(parsed["events"][0]["ranges"][0]["bold"])
        self.assertFalse(parsed["events"][0]["ranges"][0]["italic"])
        # 真正的 \b1 仍然生效。
        self.assertTrue(parsed["events"][1]["ranges"][0]["bold"])
        # \i / \u / \r 不能被 \b 分支截走：斜体、下划线各归各位。
        third = parsed["events"][2]["ranges"]
        self.assertTrue(third[0]["italic"])
        self.assertFalse(third[0]["bold"])
        self.assertTrue(third[1]["underline"])
        self.assertFalse(third[1]["bold"])

    def test_detect_silence_interval_math(self):
        spans = [{"start": 0.5, "end": 2.0}, {"start": 3.0, "end": None}]
        closed = media_tools_mod._close_spans(spans, 4.0)
        self.assertEqual(closed, [{"start": 0.5, "end": 2.0},
                                  {"start": 3.0, "end": 4.0}])
        self.assertEqual(media_tools_mod._close_spans(
            [{"start": 5.0, "end": None}], 4.0), [])
        padded = media_tools_mod._pad_spans(closed, 0.1)
        self.assertEqual(padded, [{"start": 0.6, "end": 1.9},
                                  {"start": 3.1, "end": 3.9}])
        self.assertEqual(media_tools_mod._pad_spans(
            [{"start": 0.5, "end": 0.6}], 0.1), [])
        self.assertEqual(media_tools_mod._pad_spans(closed, 0), closed)
        self.assertEqual(media_tools_mod._keep_spans(closed, 4.0),
                         [{"start": 0.0, "end": 0.5}, {"start": 2.0, "end": 3.0}])
        self.assertEqual(media_tools_mod._segments([{"start": 1.25, "end": None}])[0],
                         {"start": 1.25, "end": None,
                          "start_us": 1_250_000, "end_us": None})

    def test_prune_keeps_effect_material_referenced_by_local_material_id(self):
        draft = self.root / "prune-local"
        write_json(draft / "draft_info.json", {
            "id": "d", "duration": 2_000_000,
            "materials": {
                "videos": [
                    {"id": "V1", "path": "v.mp4", "duration": 2_000_000},
                    {"id": "ORPHAN", "path": "o.mp4", "duration": 1_000_000},
                ],
                "effects": [{"id": "FX1", "type": "mix_mode", "name": "混合"}],
            },
            "tracks": [{"type": "video", "segments": [{
                "id": "s1", "material_id": "V1", "local_material_id": "FX1",
                "target_timerange": {"start": 0, "duration": 2_000_000},
            }]}],
        })
        # render 扫描器与 prune 必须同口径。
        self.assertTrue(jy_mod._draft_material_present(
            draft / "draft_info.json", "effects", {"mix_mode"}))
        self.assertIn("FX1", draft_mod._referenced_material_ids(
            json.loads((draft / "draft_info.json").read_text("utf-8"))))
        result = maintenance_mod.prune(draft, out_dir=self.root / "prune-local-out")
        self.assertEqual(result["removed_count"], 1)
        self.assertEqual(result["removed"][0]["id"], "ORPHAN")
        document = json.loads(
            (Path(result["out"]) / "draft_info.json").read_text("utf-8"))
        self.assertEqual([item["id"] for item in document["materials"]["effects"]],
                         ["FX1"])

    def test_relink_from_prefix_branch_and_target_missing(self):
        old_dir = self.root / "old-media"
        new_dir = self.root / "new-media"
        new_dir.mkdir()
        (new_dir / "clip.mp4").write_bytes(b"x")
        draft = self.root / "prefix-draft"
        write_json(draft / "draft_info.json", {
            "id": "d", "duration": 2_000_000,
            "materials": {"videos": [
                {"id": "V1", "path": str(old_dir / "clip.mp4"), "duration": 2_000_000},
                {"id": "V2", "path": str(old_dir / "gone.mp4"), "duration": 1_000_000},
            ]},
            "tracks": [{"type": "video", "segments": [{
                "id": "s1", "material_id": "V1",
                "target_timerange": {"start": 0, "duration": 2_000_000},
                "source_timerange": {"start": 0, "duration": 2_000_000},
            }, {
                "id": "s2", "material_id": "V2",
                "target_timerange": {"start": 2_000_000, "duration": 1_000_000},
                "source_timerange": {"start": 0, "duration": 1_000_000},
            }]}],
        })
        result = maintenance_mod.relink(
            draft, from_prefix=str(old_dir) + "\\", to_prefix=str(new_dir) + "\\",
            out_dir=self.root / "prefix-out")
        self.assertEqual(len(result["changes"]), 1)
        self.assertEqual(Path(result["changes"][0]["new"]),
                         (new_dir / "clip.mp4").resolve())
        self.assertEqual([item["reason"] for item in result["missing"]],
                         ["target_missing"])
        document = json.loads(
            (Path(result["out"]) / "draft_info.json").read_text("utf-8"))
        self.assertEqual(Path(document["materials"]["videos"][0]["path"]),
                         (new_dir / "clip.mp4").resolve())

        # --to 拼出 UNC 时必须在 local_path 阶段就拒绝，不能先 lstat 触发 SMB
        unsafe = maintenance_mod.relink(
            draft, from_prefix=str(old_dir) + "\\",
            to_prefix=r"\\10.0.0.5\share\\", out_dir=self.root / "prefix-unc")
        self.assertEqual(unsafe["changes"], [])
        self.assertEqual({item["reason"] for item in unsafe["missing"]}, {"unsafe"})
        self.assertNotIn("out", unsafe)


if __name__ == "__main__":
    unittest.main(verbosity=2)