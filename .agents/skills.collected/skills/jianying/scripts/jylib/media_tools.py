"""确定性的媒体分析：静音、镜头切换、重复/重拍与素材体检。

只做分析与报告，不改草稿；输出同时给秒和草稿原生微秒，方便后续
`build` / `patch` / `trim` 使用。
"""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

from .errors import SkillError
from . import draft as draft_mod
from . import media as media_mod

US = 1_000_000
_SILENCE_START = re.compile(r"\bsilence_start:\s*(-?\d+(?:\.\d+)?)")
_SILENCE_END = re.compile(r"\bsilence_end:\s*(-?\d+(?:\.\d+)?)")
_SHOWINFO_PTS = re.compile(r"\bpts_time:\s*(-?\d+(?:\.\d+)?)")


def _run_ffmpeg(ffmpeg, args, *, timeout=600):
    try:
        done = subprocess.run(
            [ffmpeg, "-hide_banner", "-nostdin", *args],
            stdin=subprocess.DEVNULL, capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=timeout,
        )
    except FileNotFoundError as exc:
        raise SkillError("ffmpeg 不存在", code="FFMPEG_MISSING",
                         details={"ffmpeg": ffmpeg}) from exc
    except subprocess.TimeoutExpired as exc:
        raise SkillError("媒体分析超时", code="MEDIA_TIMEOUT",
                         details={"timeout": timeout}) from exc
    if done.returncode != 0:
        raise SkillError("ffmpeg 分析失败", code="MEDIA_FAILED",
                         details={"returncode": done.returncode,
                                  "stderr": (done.stderr or "")[-800:]})
    return done.stderr or ""


def parse_silences(stderr):
    spans = []
    pending = None
    for line in stderr.splitlines():
        start = _SILENCE_START.search(line)
        if start:
            pending = max(0.0, float(start.group(1)))
            continue
        end = _SILENCE_END.search(line)
        if end and pending is not None:
            finish = float(end.group(1))
            if finish > pending:
                spans.append({"start": pending, "end": finish})
            pending = None
    if pending is not None:
        spans.append({"start": pending, "end": None})
    return sorted(spans, key=lambda item: item["start"])


def _close_spans(spans, duration):
    if duration is None:
        return [dict(item) for item in spans]
    closed = []
    for item in spans:
        if item["start"] >= duration:
            continue
        end = duration if item["end"] is None else min(item["end"], duration)
        if end > item["start"]:
            closed.append({"start": item["start"], "end": end})
    return closed


def _pad_spans(spans, pad):
    if pad <= 0:
        return [dict(item) for item in spans]
    padded = []
    for item in spans:
        start = item["start"] + pad
        if item["end"] is None:
            padded.append({"start": start, "end": None})
            continue
        end = item["end"] - pad
        if end > start:
            padded.append({"start": start, "end": end})
    return padded


def _keep_spans(silences, duration):
    keeps = []
    cursor = 0.0
    for item in silences:
        end = duration if item["end"] is None else item["end"]
        if item["start"] > cursor:
            keeps.append({"start": cursor, "end": item["start"]})
        cursor = max(cursor, end)
    if duration and cursor < duration:
        keeps.append({"start": cursor, "end": duration})
    return keeps


def _segments(spans):
    return [{"start": round(item["start"], 6),
             "end": None if item["end"] is None else round(item["end"], 6),
             "start_us": int(round(item["start"] * US)),
             "end_us": None if item["end"] is None else int(round(item["end"] * US))}
            for item in spans]


def detect_silence(ffmpeg, media, *, threshold_db=-30.0, min_silence=0.5,
                   pad=0.1, limit=None, probe=None, timeout=600):
    source = media_mod.local_path(media, field="媒体文件")
    if not media_mod.is_plain_file(source):
        raise SkillError("媒体文件不存在或是链接路径", code="MEDIA_NOT_FOUND",
                         details={"path": str(source)})
    duration = (probe or {}).get("duration")
    try:
        with media_mod.hold_plain_file(source):
            stderr = _run_ffmpeg(ffmpeg, [
                "-i", str(source), "-af",
                f"silencedetect=noise={float(threshold_db):g}dB:d={float(min_silence):g}",
                "-f", "null", "-",
            ], timeout=timeout)
    except OSError as exc:
        raise SkillError("媒体文件在读取前发生变化，已拒绝",
                         code="MEDIA_NOT_FOUND",
                         details={"path": str(source), "reason": str(exc)}) from exc
    silences = _close_spans(parse_silences(stderr), duration)
    silences = _pad_spans(silences, float(pad))
    if limit:
        silences = sorted(silences, key=lambda item: (
            (item["end"] or duration or item["start"]) - item["start"]), reverse=True)[:int(limit)]
        silences.sort(key=lambda item: item["start"])
    keeps = _keep_spans(silences, duration)
    return {
        "media": str(source), "duration": duration,
        "duration_us": None if duration is None else int(round(duration * US)),
        "threshold_db": float(threshold_db), "min_silence": float(min_silence),
        "pad": float(pad), "limit": limit,
        "silences": _segments(silences), "keeps": _segments(keeps),
    }


def parse_scenes(stderr, *, min_gap=0.0):
    times = []
    for line in stderr.splitlines():
        match = _SHOWINFO_PTS.search(line)
        if match:
            value = float(match.group(1))
            if value >= 0 and (not times or value - times[-1] >= min_gap):
                times.append(value)
    return times


def detect_scenes(ffmpeg, media, *, threshold=0.3, min_gap=0.5,
                  probe=None, timeout=600):
    source = media_mod.local_path(media, field="媒体文件")
    if not media_mod.is_plain_file(source):
        raise SkillError("媒体文件不存在或是链接路径", code="MEDIA_NOT_FOUND",
                         details={"path": str(source)})
    duration = (probe or {}).get("duration")
    try:
        with media_mod.hold_plain_file(source):
            stderr = _run_ffmpeg(ffmpeg, [
                "-i", str(source), "-vf",
                f"select='gt(scene,{float(threshold):g})',showinfo",
                "-vsync", "vfr", "-f", "null", "-",
            ], timeout=timeout)
    except OSError as exc:
        raise SkillError("媒体文件在读取前发生变化，已拒绝",
                         code="MEDIA_NOT_FOUND",
                         details={"path": str(source), "reason": str(exc)}) from exc
    cuts = parse_scenes(stderr, min_gap=min_gap)
    if duration and cuts and cuts[0] > 0:
        cuts = [0.0] + cuts
    elif not cuts:
        cuts = [0.0]
    spans = []
    for index, start in enumerate(cuts):
        end = cuts[index + 1] if index + 1 < len(cuts) else duration
        if end is None or end <= start:
            continue
        spans.append({"start": start, "end": end})
    return {
        "media": str(source), "threshold": float(threshold), "min_gap": float(min_gap),
        "duration": duration, "duration_us": None if duration is None else int(round(duration * US)),
        "scenes": _segments(spans), "cut_times": [round(item, 6) for item in cuts],
    }


def _normalize_tokens(text):
    return [token for token in re.split(r"\s+", str(text).strip().lower()) if token]


def _lcs(a, b):
    if not a or not b:
        return 0
    previous = [0] * (len(b) + 1)
    for item in a:
        current = [0] * (len(b) + 1)
        for index, other in enumerate(b, 1):
            current[index] = previous[index - 1] + 1 if item == other \
                else max(previous[index], current[index - 1])
        previous = current
    return previous[-1]


def similarity(a, b):
    if not a and not b:
        return 0.0
    return round(2.0 * _lcs(a, b) / (len(a) + len(b)), 3)


def find_retakes(cues, *, window=60.0, threshold=0.8, min_words=4):
    ordered = sorted(cues, key=lambda item: float(item["start"]))
    tokens = [_normalize_tokens(item.get("text")) for item in ordered]
    pairs = []
    for index, cue in enumerate(ordered):
        if len(tokens[index]) < int(min_words):
            continue
        earlier_end = float(cue.get("end") or cue["start"])
        for later in range(index + 1, len(ordered)):
            other = ordered[later]
            if float(other["start"]) - earlier_end > float(window):
                break
            if len(tokens[later]) < int(min_words):
                continue
            score = similarity(tokens[index], tokens[later])
            if score >= float(threshold):
                pairs.append({
                    "earlier": {**cue, "start_us": int(round(float(cue["start"]) * US)),
                                "end_us": int(round(earlier_end * US))},
                    "later": {**other, "start_us": int(round(float(other["start"]) * US)),
                              "end_us": int(round(float(other.get("end") or other["start"]) * US))},
                    "similarity": score, "words": len(tokens[index]),
                })
                break
    cuts = []
    for pair in pairs:
        span = {"start": float(pair["earlier"]["start"]),
                "end": float(pair["earlier"]["end"])}
        if cuts and span["start"] <= cuts[-1]["end"]:
            cuts[-1]["end"] = max(cuts[-1]["end"], span["end"])
        else:
            cuts.append(span)
    return {"retakes": pairs, "cuts": _segments(cuts)}


def detect_retakes(cues, **options):
    if not isinstance(cues, list):
        raise SkillError("retakes 需要 cue 数组 [{text,start,end}]", code="VALIDATION")
    holes = []
    for index, cue in enumerate(cues):
        if not isinstance(cue, dict) or not str(cue.get("text") or "").strip():
            continue
        try:
            start = float(cue.get("start"))
            end = float(cue.get("end", cue.get("start")))
        except (TypeError, ValueError):
            raise SkillError(f"cues[{index}] 时间码非法", code="VALIDATION")
        if start < 0 or end <= start:
            raise SkillError(f"cues[{index}] 时间范围非法", code="VALIDATION")
        holes.append({"text": str(cue["text"]), "start": start, "end": end})
    report = find_retakes(holes, **options)
    report["cues"] = len(holes)
    return report


def duplicate_segments(draft_dir):
    resolved = draft_mod.resolve_draft_info(draft_dir)
    info = resolved["info_path"]
    if not info:
        raise SkillError("不是剪映草稿目录", code="DRAFT_NOT_FOUND",
                         details={"draft": str(resolved["draft_dir"])})
    try:
        doc = json.loads(info.read_text("utf-8-sig"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise SkillError("草稿不是明文 JSON", code="DRAFT_ENCRYPTED",
                         details={"path": str(info)}) from exc
    seen = {}
    duplicates = []
    for track_index, track in enumerate(doc.get("tracks") or []):
        for segment in track.get("segments") or []:
            source = segment.get("source_timerange") or {}
            key = (segment.get("material_id"), source.get("start"), source.get("duration"))
            if not key[0]:
                continue
            if key in seen:
                duplicates.append({
                    "first": seen[key],
                    "duplicate": {"track": track_index, "segment": segment.get("id"),
                                  "start": float((segment.get("target_timerange") or {}).get("start") or 0) / US},
                    "source": {"material_id": key[0], "start_us": key[1], "duration_us": key[2]},
                })
            else:
                seen[key] = {"track": track_index, "segment": segment.get("id"),
                             "start": float((segment.get("target_timerange") or {}).get("start") or 0) / US}
    return {"draft": str(resolved["draft_dir"]), "duplicates": duplicates}
