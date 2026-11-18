"""EBU R128 loudness measurement and per-clip gain planning.

The module only reads the draft and source media. Applying gain is done by the
caller through ``draft.patch`` so the normal copy/backup/version rules stay in
one place.
"""

from __future__ import annotations

import json
import math
import re
import subprocess
from pathlib import Path

from .errors import SkillError
from . import media as media_mod
from . import draft as draft_mod


def _finite_number(value):
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _find_loudnorm_json(text):
    """从 ffmpeg stderr 里找 loudnorm 的输入测量 JSON。"""
    decoder = json.JSONDecoder()
    for match in re.finditer(r"\{", text):
        try:
            value, _ = decoder.raw_decode(text[match.start():])
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict) and "input_i" in value:
            return value
    return None


def measure(ffmpeg, path, *, start=0.0, duration=None, timeout=120):
    """Measure one source range with ffmpeg's loudnorm filter.

    Returns ``lufs`` / ``true_peak_dbtp`` / ``lra`` / ``input_threshold``.
    ``None`` means the stream is silent (or the value is ``-inf``).
    """
    if not ffmpeg:
        raise SkillError("没有 ffmpeg，无法测量响度", code="FFMPEG_MISSING",
                         fix="安装 ffmpeg，或使用剪映安装目录自带的 ffmpeg。")
    source = media_mod.local_path(path, field="响度素材")
    if not media_mod.is_plain_file(source):
        raise SkillError("响度素材不存在或是链接路径", code="MEDIA_NOT_FOUND",
                         details={"path": str(source)})
    source = source.resolve()
    command = [
        str(ffmpeg), "-hide_banner", "-nostats", "-loglevel", "info",
        "-ss", f"{max(0.0, float(start)):.6f}",
    ]
    if duration is not None:
        command += ["-t", f"{max(0.0, float(duration)):.6f}"]
    command += [
        "-i", str(source), "-map", "0:a:0",
        "-af", "loudnorm=I=-14:TP=-1.0:LRA=11:print_format=json",
        "-f", "null", "-",
    ]
    try:
        with media_mod.hold_plain_file(source):
            done = subprocess.run(
                command, stdin=subprocess.DEVNULL, capture_output=True, text=True,
                encoding="utf-8", errors="replace", timeout=timeout,
            )
    except FileNotFoundError as exc:
        raise SkillError("ffmpeg 可执行文件不存在", code="FFMPEG_MISSING",
                         details={"tool": str(ffmpeg)}) from exc
    except subprocess.TimeoutExpired as exc:
        raise SkillError("响度测量超时", code="LOUDNESS_TIMEOUT",
                         details={"path": str(source), "timeout": timeout}) from exc
    except OSError as exc:
        raise SkillError("响度素材在读取前发生变化，已拒绝",
                         code="MEDIA_NOT_FOUND",
                         details={"path": str(source), "reason": str(exc)}) from exc
    payload = _find_loudnorm_json(done.stderr or "")
    if payload is None:
        raise SkillError("ffmpeg 没有返回 loudnorm 测量结果",
                         code="LOUDNESS_MEASURE_FAILED",
                         details={"path": str(source), "stderr": (done.stderr or "")[-500:]})
    return {
        "lufs": _finite_number(payload.get("input_i")),
        "true_peak_dbtp": _finite_number(payload.get("input_tp")),
        "lra": _finite_number(payload.get("input_lra")),
        "input_threshold": _finite_number(payload.get("input_thresh")),
        "source": str(source),
    }


def _segment_audio_info(document, track, segment):
    """Return (material, path, source_start, source_duration) or None."""
    material_id = segment.get("material_id")
    materials = document.get("materials") or {}
    material = None
    bucket = None
    for candidate_bucket in ("audios", "videos"):
        for item in materials.get(candidate_bucket) or []:
            if isinstance(item, dict) and item.get("id") == material_id:
                material, bucket = item, candidate_bucket
                break
        if material:
            break
    if material is None:
        return None
    if bucket == "videos" and not material.get("has_audio"):
        return None
    path = str(material.get("path") or "").strip()
    if not path:
        return None
    source = segment.get("source_timerange") or {}
    source_start = float(source.get("start") or 0) / 1_000_000
    source_duration = float(source.get("duration") or 0) / 1_000_000
    if source_duration <= 0:
        target = segment.get("target_timerange") or {}
        source_duration = float(target.get("duration") or 0) / 1_000_000
    if source_duration <= 0:
        source_duration = None
    return material, path, source_start, source_duration


def analyze(draft_dir, *, ffmpeg, target_lufs=None, max_gain_db=12.0,
            max_attenuation_db=24.0, max_true_peak=None, timeout=120):
    """Measure every audible clip and optionally compute a target volume.

    No draft file is written. ``gain_db`` is capped by ``max_gain_db`` /
    ``max_attenuation_db`` and by ``max_true_peak`` when supplied.
    """
    if target_lufs is not None:
        target_lufs = float(target_lufs)
        if not math.isfinite(target_lufs) or not -70 <= target_lufs <= -5:
            raise SkillError("target_lufs 必须在 -70 到 -5 之间",
                             code="VALIDATION", details={"target": target_lufs})
    if max_gain_db < 0 or max_attenuation_db < 0:
        raise SkillError("增益上限不能为负", code="VALIDATION")
    resolved = draft_mod.resolve_draft_info(draft_dir)
    try:
        document = json.loads(Path(resolved["info_path"]).read_text("utf-8-sig"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise SkillError("草稿不是明文 JSON，无法测量响度", code="DRAFT_ENCRYPTED",
                         details={"draft": str(draft_dir)}) from exc

    clips = []
    cache = {}
    for track_index, track in enumerate(document.get("tracks") or []):
        for segment in track.get("segments") or []:
            info = _segment_audio_info(document, track, segment)
            if info is None:
                continue
            material, path, source_start, source_duration = info
            cache_key = (path, round(source_start, 6),
                         round(source_duration or 0, 6))
            if cache_key not in cache:
                try:
                    cache[cache_key] = measure(
                        ffmpeg, path, start=source_start,
                        duration=source_duration, timeout=timeout)
                except SkillError as exc:
                    cache[cache_key] = {"error": exc.code, "message": exc.message}
            measured = cache[cache_key]
            volume = _finite_number(segment.get("volume"))
            if volume is None:
                volume = 1.0
            entry = {
                "segment_id": segment.get("id"),
                "track_index": track_index,
                "track_type": track.get("type"),
                "material_id": material.get("id"),
                "name": material.get("material_name") or material.get("name") or "",
                "path": path,
                "source_start": round(source_start, 3),
                "source_duration": (round(source_duration, 3)
                                    if source_duration is not None else None),
                "current_volume": round(volume, 6),
                "measured": measured,
            }
            if "error" in measured:
                entry.update({"status": "unmeasured", "gain_db": None,
                              "target_volume": None})
                clips.append(entry)
                continue
            lufs = measured.get("lufs")
            peak = measured.get("true_peak_dbtp")
            if lufs is None:
                entry.update({"status": "silent", "gain_db": None,
                              "target_volume": None})
                clips.append(entry)
                continue
            if target_lufs is None:
                entry.update({"status": "measured", "gain_db": None,
                              "target_volume": None})
                clips.append(entry)
                continue
            gain_db = target_lufs - lufs
            if max_true_peak is not None and peak is not None:
                gain_db = min(gain_db, float(max_true_peak) - peak)
            gain_db = min(gain_db, float(max_gain_db))
            gain_db = max(gain_db, -float(max_attenuation_db))
            target_volume = volume * (10 ** (gain_db / 20.0))
            clipped = target_volume > 10.0
            if clipped:
                target_volume = 10.0
                gain_db = 20.0 * math.log10(target_volume / volume) if volume else 0.0
            entry.update({
                "status": "gain",
                "gain_db": round(gain_db, 3),
                "target_volume": round(target_volume, 6),
                "clipped": clipped,
            })
            clips.append(entry)

    unmeasured = [item for item in clips if item.get("status") == "unmeasured"]
    return {
        "draft": str(Path(draft_dir).resolve()),
        "target_lufs": target_lufs,
        "max_gain_db": max_gain_db,
        "max_attenuation_db": max_attenuation_db,
        "max_true_peak": max_true_peak,
        "clips": clips,
        "measured_count": sum(
            1 for item in clips
            if (item.get("measured") or {}).get("lufs") is not None),
        "unmeasured_count": len(unmeasured),
        "warnings": ([f"{len(unmeasured)} 个音频片段测量失败，未参与增益计划"]
                     if unmeasured else []),
    }


def gain_ops(report):
    """Turn a report into draft.patch set_volume operations."""
    ops = []
    for item in report.get("clips") or []:
        if item.get("status") != "gain" or item.get("target_volume") is None:
            continue
        ops.append({
            "op": "set_volume",
            "segment": item["segment_id"],
            "volume": item["target_volume"],
        })
    return ops
