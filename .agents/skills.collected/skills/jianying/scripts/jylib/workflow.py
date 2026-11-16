"""End-to-end subtitle workflow: local ASR/SRT -> packaging plan -> editable draft."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import uuid
from pathlib import Path

from .errors import SkillError
from . import draft as draft_mod
from . import media as media_mod
from . import packaging as packaging_mod

_SUBTITLE_CLI = Path(__file__).resolve().parent.parent / "subtitles" / "cli.py"


def _temp_sibling(path: Path) -> Path:
    return path.with_name(f".{path.name}.{uuid.uuid4().hex[:8]}.tmp")


def _publish_file(temp: Path, final: Path, label: str) -> None:
    try:
        os.replace(temp, final)
    except OSError as exc:
        raise SkillError(f"{label}发布失败", code="OUTPUT_WRITE_FAILED",
                         details={"path": str(final), "temp": str(temp),
                                  "reason": str(exc)}) from exc


def generate_local_asr_srt(audio, out_srt, *, json_out=None, model_dir=None,
                           remove_fillers=False, fillers=None, punctuate=False,
                           max_chars=16, max_dur=5.0, gap=0.35,
                           force=False, timeout=1800) -> dict:
    audio_path = media_mod.local_path(audio, field="音频路径").resolve()
    if not audio_path.is_file():
        raise SkillError("音频不存在", code="MEDIA_NOT_FOUND",
                         details={"path": str(audio_path)})
    srt_path = media_mod.local_path(out_srt, field="SRT 输出路径")
    if srt_path.exists() and not force:
        raise SkillError("SRT 输出已存在", code="OUTPUT_EXISTS",
                         details={"path": str(srt_path)},
                         fix="换一个 --srt-out，或确认后加 --force")
    srt_path.parent.mkdir(parents=True, exist_ok=True)
    srt_tmp = _temp_sibling(srt_path)
    json_path = json_tmp = None
    if json_out:
        json_path = media_mod.local_path(json_out, field="ASR JSON 输出路径")
        if json_path.exists() and not force:
            raise SkillError("ASR JSON 输出已存在", code="OUTPUT_EXISTS",
                             details={"path": str(json_path)},
                             fix="换一个 --asr-json-out，或确认后加 --force")
        json_path.parent.mkdir(parents=True, exist_ok=True)
        json_tmp = _temp_sibling(json_path)
    command = [sys.executable, str(_SUBTITLE_CLI), "srt.from-local-asr",
               "--audio", str(audio_path), "--out", str(srt_tmp),
               "--max-chars", str(max_chars), "--max-dur", str(max_dur),
               "--gap", str(gap)]
    if json_tmp:
        command.extend(["--json-out", str(json_tmp)])
    if model_dir:
        command.extend(["--model-dir", str(model_dir)])
    if remove_fillers:
        command.append("--remove-fillers")
    if fillers:
        command.extend(["--fillers", str(fillers)])
    if punctuate:
        command.append("--punctuate")
    failed = False
    json_published = False
    json_backup = None
    try:
        try:
            completed = subprocess.run(
                command, capture_output=True, text=True, encoding="utf-8",
                errors="replace", timeout=timeout)
        except subprocess.TimeoutExpired as exc:
            raise SkillError("本地 ASR 超时", code="LOCAL_ASR_TIMEOUT",
                             details={"timeout": timeout}) from exc
        try:
            payload = json.loads((completed.stdout or "").strip())
        except json.JSONDecodeError as exc:
            detail = (completed.stderr or completed.stdout or "").strip()[:400]
            raise SkillError("本地 ASR 没有返回 JSON", code="LOCAL_ASR_FAILED",
                             details={"returncode": completed.returncode,
                                      "output": detail}) from exc
        if not payload.get("ok"):
            raise SkillError(
                payload.get("detail") or "本地 ASR 失败",
                code=payload.get("code") or "LOCAL_ASR_FAILED",
                details={"returncode": completed.returncode},
                fix=payload.get("hint"),
            )
        data = payload.get("data") or {}
        if not srt_tmp.is_file():
            raise SkillError("本地 ASR 返回成功但 SRT 不存在",
                             code="LOCAL_ASR_FAILED",
                             details={"srt": str(srt_tmp)})
        if json_tmp is not None and not json_tmp.is_file():
            raise SkillError("本地 ASR 返回成功但 ASR JSON 不存在",
                             code="LOCAL_ASR_FAILED",
                             details={"json": str(json_tmp)})
        if json_tmp is not None:
            if json_path.exists():
                try:
                    json_backup = json_path.read_bytes()
                except OSError:
                    json_backup = None
            _publish_file(json_tmp, json_path, "ASR JSON")
            json_published = True
        _publish_file(srt_tmp, srt_path, "SRT")
        data["srt"] = str(srt_path)
        if json_tmp is not None:
            data["json"] = str(json_path)
            if "json_out" in data:
                data["json_out"] = str(json_path)
        return {"data": data,
                "warnings": payload.get("evidence", {}).get("warnings") or []}
    except BaseException:
        failed = True
        if json_published:
            try:
                if json_backup is None:
                    json_path.unlink(missing_ok=True)
                else:
                    json_path.write_bytes(json_backup)
            except OSError:
                pass
        raise
    finally:
        if not failed:
            for temp in (srt_tmp, json_tmp):
                if temp is not None:
                    try:
                        temp.unlink(missing_ok=True)
                    except OSError:
                        pass


def build_subtitle_draft(video, out, *, audio=None, srt=None, plan_out=None,
                         srt_out=None, asr_json_out=None, title=None,
                         bgm=None, font_ref=None, subtitle_template_ref=None,
                         title_animation_ref=None, name=None, width=None,
                         height=None, fps=30.0, subtitle_style=None,
                         highlight_words=None, highlight_color="#FFD400",
                         model_dir=None, remove_fillers=False, fillers=None,
                         punctuate=False, max_chars=16, max_dur=5.0, gap=0.35,
                         fetch_resources=False, force=False,
                         make_cover=True) -> dict:
    video_path = media_mod.local_path(video, field="视频路径").resolve()
    out_dir = media_mod.local_path(out, field="草稿输出目录")
    out_dir = out_dir.resolve()
    plan_path = (media_mod.local_path(plan_out, field="计划输出路径").resolve()
                 if plan_out else out_dir.parent / f"{out_dir.name}-plan.json")
    warnings = []
    asr_data = None
    if srt:
        srt_path = media_mod.local_path(srt, field="SRT 路径").resolve()
        if not srt_path.is_file():
            raise SkillError("SRT 不存在", code="FILE_NOT_FOUND",
                             details={"path": str(srt_path)})
    else:
        srt_path = (media_mod.local_path(srt_out, field="SRT 输出路径").resolve()
                    if srt_out else out_dir.parent / f"{out_dir.name}.srt")
        json_path = (media_mod.local_path(asr_json_out, field="ASR JSON 输出路径").resolve()
                     if asr_json_out else out_dir.parent / f"{out_dir.name}.asr.json")
        result = generate_local_asr_srt(
            audio or video_path, srt_path, json_out=json_path,
            model_dir=model_dir, remove_fillers=remove_fillers,
            fillers=fillers, punctuate=punctuate, max_chars=max_chars,
            max_dur=max_dur, gap=gap, force=force)
        asr_data = result["data"]
        warnings.extend(result["warnings"])

    draft_name = name or title
    plan = packaging_mod.build_plan(
        video_path, plan_path, title=title, subtitle_srt=srt_path, bgm=bgm,
        font_ref=font_ref, subtitle_template_ref=subtitle_template_ref,
        title_animation_ref=title_animation_ref, name=draft_name, width=width,
        height=height, fps=fps, subtitle_style=subtitle_style,
        highlight_words=highlight_words, highlight_color=highlight_color,
        force=force)
    warnings.extend(plan.get("warnings") or [])
    built = draft_mod.build(
        plan_path, out_dir, force=force, name=draft_name, make_cover=make_cover,
        version_label="subtitle-workflow", fetch_resources=fetch_resources)
    return {
        "srt": str(srt_path),
        "asr": asr_data,
        "plan": str(plan_path),
        "draft": built,
        "warnings": warnings,
    }