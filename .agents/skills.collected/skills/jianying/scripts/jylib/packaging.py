"""本地包装 preset：把主视频、标题、字幕、BGM 组合成 jianying-plan/v1。

它不是剪映的云端“智能包装”，只是把本技能已验收的原语组合成可继续编辑的计划。
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

from .errors import SkillError
from . import draft as draft_mod
from . import env as env_mod
from . import media as media_mod


def _probe(path: Path) -> dict:
    facts = env_mod.probe()
    ffprobe = (facts.get("ffmpeg") or {}).get("ffprobe")
    return media_mod.probe_media(ffprobe, str(path))


def _caption_info(text: str, index: int, duration_s: float) -> dict:
    duration_us = max(1, int(round(duration_s * 1_000_000)))
    return {
        "id": f"caption-{index}",
        "speaker_type": "",
        "speaker_id": "",
        "caption_segment_id": f"segment-{index}",
        "original_text": text,
        "words": [{
            "id": f"word-{index}",
            "text": text,
            "tag": "",
            "origin_text": text,
            "time_range": {"start": 0, "duration": duration_us},
        }],
    }


def build_plan(video, out_plan, *, title=None, subtitle_srt=None, bgm=None,
               font_ref=None, subtitle_template_ref=None,
               title_animation_ref=None, name=None, width=None, height=None,
               fps=30.0, subtitle_style=None, highlight_words=None,
               highlight_color="#FFD400", force=False) -> dict:
    video_path = media_mod.local_path(video, field="视频路径")
    out_path = media_mod.local_path(out_plan, field="计划输出路径")
    plan_dir = out_path.parent.resolve()

    def plan_ref(path: Path) -> str:
        target = Path(path).expanduser().resolve()
        try:
            return os.path.relpath(target, plan_dir)
        except ValueError:
            return str(target)

    info = _probe(video_path)
    duration = float(info.get("duration") or 0.0)
    if duration <= 0:
        raise SkillError("视频时长读不出来", code="VALIDATION",
                         details={"path": str(video_path)})
    canvas_width = int(width or info.get("width") or 1920)
    canvas_height = int(height or info.get("height") or 1080)
    canvas_fps = float(fps or info.get("fps") or 30.0)
    if canvas_width <= 0 or canvas_height <= 0 or canvas_fps <= 0:
        raise SkillError("画布参数不合法", code="VALIDATION",
                         details={"width": canvas_width, "height": canvas_height,
                                  "fps": canvas_fps})

    highlight = None
    if highlight_words:
        if isinstance(highlight_words, str):
            words = [word.strip() for word in highlight_words.split(",") if word.strip()]
        else:
            words = [str(word).strip() for word in highlight_words if str(word).strip()]
        if words:
            highlight = {"words": words, "color": str(highlight_color), "bold": True}

    tracks = [{
        "type": "video",
        "name": "主轨",
        "segments": [{"path": plan_ref(video_path), "start": 0, "duration": duration}],
    }]

    if title:
        title_spec = {
            "text": str(title),
            "start": 0.5,
            "duration": min(3.0, max(0.5, duration)),
            "font_size": 16,
            "color": "#FFD400",
            "stroke_color": "#000000",
            "stroke_width": 0.05,
            "y": 0.2,
        }
        if font_ref:
            title_spec["resource_ref"] = str(font_ref)
        if title_animation_ref:
            title_spec["animations"] = [{
                "type": "in",
                "resource_ref": str(title_animation_ref),
                "duration": 1.0,
            }]
        if highlight:
            title_spec["highlight"] = highlight
        tracks.append({"type": "text", "name": "标题",
                       "segments": [title_spec]})

    subtitle_count = 0
    skipped_cues = 0
    warnings = []
    if subtitle_srt:
        srt_path = media_mod.local_path(subtitle_srt, field="SRT 路径")
        cues = draft_mod._read_srt_cues(srt_path)
        style = dict(subtitle_style or {})
        style.setdefault("font_size", 8)
        style.setdefault("color", "#FFFFFF")
        style.setdefault("stroke_color", "#000000")
        style.setdefault("stroke_width", 0.05)
        style.setdefault("y", -0.72)
        segments = []
        for index, cue in enumerate(cues, 1):
            if cue["start"] >= duration:
                skipped_cues += 1
                continue
            end = min(float(cue["end"]), duration)
            if end <= cue["start"]:
                skipped_cues += 1
                continue
            spec = dict(style)
            spec.update({
                "text": cue["text"],
                "start": float(cue["start"]),
                "duration": end - float(cue["start"]),
                "caption_info": _caption_info(cue["text"], index,
                                              end - float(cue["start"])),
            })
            if font_ref:
                spec["resource_ref"] = str(font_ref)
            if subtitle_template_ref:
                spec["caption_template"] = {
                    "resource_ref": str(subtitle_template_ref),
                    "resources": [],
                }
            if highlight:
                spec["highlight"] = highlight
            segments.append(spec)
        if cues and not segments:
            raise SkillError(
                "SRT 全部超出视频时长，不能生成字幕轨",
                code="VALIDATION",
                details={"srt_end": max(float(cue["end"]) for cue in cues),
                         "duration": round(duration, 3)},
                fix="裁剪 SRT 或换与字幕匹配的视频；不要生成一条静默丢字幕的包装。",
            )
        if segments:
            tracks.append({"type": "text", "name": "字幕", "segments": segments})
            subtitle_count = len(segments)
        if skipped_cues:
            warnings.append(
                f"{skipped_cues} 条 SRT cue 超出视频时长，已跳过；"
                "需要完整字幕时先裁剪 SRT 或换视频。")

    if bgm:
        bgm_path = media_mod.local_path(bgm, field="BGM 路径")
        bgm_info = _probe(bgm_path)
        bgm_duration = min(duration, float(bgm_info.get("duration") or duration))
        if bgm_duration > 0:
            fade = min(1.0, bgm_duration / 4)
            tracks.append({"type": "audio", "name": "BGM", "segments": [{
                "path": plan_ref(bgm_path),
                "start": 0,
                "duration": bgm_duration,
                "volume": 0.25,
                "audio_fade": {"in": fade, "out": fade},
            }]})

    plan = {
        "schema": "jianying-plan/v1",
        "name": str(name or "包装预设"),
        "canvas": {"width": canvas_width, "height": canvas_height,
                   "fps": canvas_fps},
        "tracks": tracks,
    }
    if out_path.exists() and not force:
        raise SkillError("计划输出文件已存在", code="OUTPUT_EXISTS",
                         details={"path": str(out_path)},
                         fix="换一个 --out，或加 --force")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    encoded = json.dumps(plan, ensure_ascii=False, indent=2)
    out_path.write_text(encoded, "utf-8")
    return {
        "plan": str(out_path),
        "plan_sha256": hashlib.sha256(encoded.encode("utf-8")).hexdigest(),
        "duration": round(duration, 3),
        "canvas": plan["canvas"],
        "tracks": [{"type": track["type"], "name": track["name"],
                    "segments": len(track["segments"])} for track in tracks],
        "subtitle_cues": subtitle_count,
        "subtitle_cues_skipped": skipped_cues,
        "warnings": warnings,
        "next": "jy.py build --plan <plan> --out <draft> --fetch-resources",
    }
