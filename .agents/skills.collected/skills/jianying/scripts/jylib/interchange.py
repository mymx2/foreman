"""OpenTimelineIO JSON 交换。

导出以 `Timeline.1` / `Stack.1` / `Track.1` / `Clip.1` 为骨架，轨道内用
`Gap.1` 保留空档；导入接受同一骨架，也接受单个 Track 或 clip 数组。
文字、贴纸、特效轨道不进入 OTIO，导出回执会明确列出 skipped，而不是静默
丢失。
"""

from __future__ import annotations

import json
from pathlib import Path

from .errors import SkillError
from . import draft as draft_mod
from . import media as media_mod

US = 1_000_000


def _time(value, rate):
    return {"OTIO_SCHEMA": "RationalTime.1", "value": float(value), "rate": float(rate)}


def _range(start, duration, rate):
    return {
        "OTIO_SCHEMA": "TimeRange.1",
        "start_time": _time(start, rate),
        "duration": _time(duration, rate),
    }


def _load_draft(draft_dir):
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
    return resolved["draft_dir"], doc


def export_otio(draft_dir, out_path):
    root, doc = _load_draft(draft_dir)
    fps = float(doc.get("fps") or 30)
    rate = fps
    tracks = []
    skipped = []
    for track in doc.get("tracks") or []:
        track_type = str(track.get("type") or "")
        if track_type not in {"video", "image", "audio"}:
            skipped.append({"type": track_type, "name": track.get("name") or "",
                            "segments": len(track.get("segments") or [])})
            continue
        children = []
        cursor = 0.0
        for segment in track.get("segments") or []:
            target = segment.get("target_timerange") or {}
            start = float(target.get("start") or 0) / US
            duration = float(target.get("duration") or 0) / US
            if duration <= 0:
                continue
            if start > cursor + 1e-9:
                children.append({
                    "OTIO_SCHEMA": "Gap.1", "name": "gap",
                    "source_range": _range(0, start - cursor, rate),
                    "metadata": {},
                })
                cursor = start
            source = segment.get("source_timerange") or {}
            source_start = float(source.get("start") or 0) / US
            source_duration = float(source.get("duration") or target.get("duration") or 0) / US
            material = None
            for bucket in ("videos", "images", "audios"):
                for item in (doc.get("materials") or {}).get(bucket) or []:
                    if item.get("id") == segment.get("material_id"):
                        material = item
                        break
                if material:
                    break
            path = str((material or {}).get("path") or "")
            children.append({
                "OTIO_SCHEMA": "Clip.1",
                "name": str((material or {}).get("material_name") or (material or {}).get("name") or ""),
                "source_range": _range(source_start, source_duration, rate),
                "media_reference": {
                    "OTIO_SCHEMA": "ExternalReference.1",
                    "target_url": path,
                    "available_range": _range(0, float((material or {}).get("duration") or 0) / US, rate),
                    "metadata": {},
                },
                "metadata": {
                    "jianying": {
                        "segment_id": segment.get("id"),
                        "material_id": segment.get("material_id"),
                        "track_type": track_type,
                        "speed": segment.get("speed") or 1.0,
                    }
                },
            })
            cursor = max(cursor, start + duration)
        tracks.append({
            "OTIO_SCHEMA": "Track.1",
            "name": str(track.get("name") or track_type),
            "kind": "Audio" if track_type == "audio" else "Video",
            "metadata": {"jianying": {"track_type": track_type, "flag": track.get("flag")}},
            "source_range": None,
            "children": children,
        })
    timeline = {
        "OTIO_SCHEMA": "Timeline.1",
        "name": str(doc.get("name") or Path(root).name),
        "global_start_time": _time(0, rate),
        "metadata": {
            "jianying": {"fps": fps, "draft_id": doc.get("id"),
                         "canvas": doc.get("canvas_config") or {}},
        },
        "tracks": {
            "OTIO_SCHEMA": "Stack.1", "name": "tracks",
            "source_range": None, "metadata": {}, "children": tracks,
        },
    }
    target = media_mod.local_path(out_path, field="OTIO 输出路径")
    if target.exists():
        raise SkillError("OTIO 输出文件已存在", code="OUTPUT_EXISTS",
                         details={"path": str(target)})
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(timeline, ensure_ascii=False, indent=2), "utf-8")
    return {"out": str(target), "tracks": len(tracks), "skipped": skipped,
            "duration": float(doc.get("duration") or 0) / US}


def _rate(value, default=30.0):
    if isinstance(value, dict):
        return float(value.get("rate") or default)
    return default


def _value(value, default=0.0, rate=30.0):
    if isinstance(value, dict):
        return float(value.get("value") or 0.0)
    if value is None:
        return default
    return float(value)


def _children(payload):
    if isinstance(payload, list):
        return payload
    if not isinstance(payload, dict):
        raise SkillError("OTIO JSON 顶层必须是对象或数组", code="PARSE_FAIL")
    schema = str(payload.get("OTIO_SCHEMA") or "")
    if schema.startswith("Timeline"):
        stack = payload.get("tracks") or {}
        return stack.get("children") or []
    if schema.startswith("Stack"):
        return payload.get("children") or []
    if schema.startswith("Track"):
        return [payload]
    raise SkillError("不支持的 OTIO 顶层", code="VALIDATION",
                     details={"OTIO_SCHEMA": schema})


def import_otio(otio_path, *, name=None, canvas=None):
    target = media_mod.local_path(otio_path, field="OTIO 文件")
    if not target.is_file():
        raise SkillError("OTIO 文件不存在", code="FILE_NOT_FOUND",
                         details={"path": str(target)})
    try:
        payload = json.loads(target.read_text("utf-8-sig"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise SkillError("OTIO 不是合法 JSON", code="PARSE_FAIL",
                         details={"path": str(target)}) from exc
    tracks = []
    skipped = []
    timeline_name = name or (payload.get("name") if isinstance(payload, dict) else None) \
        or target.stem
    global_meta = (payload.get("metadata") or {}).get("jianying") if isinstance(payload, dict) else {}
    rate_default = float((global_meta or {}).get("fps") or 30)
    for track in _children(payload):
        if not isinstance(track, dict):
            skipped.append({"reason": "track_not_object"})
            continue
        kind = str(track.get("kind") or "Video")
        track_type = "audio" if kind.lower() == "audio" else "video"
        children = track.get("children") or []
        segments = []
        cursor = 0.0
        for child in children:
            if not isinstance(child, dict):
                continue
            schema = str(child.get("OTIO_SCHEMA") or "")
            source_range = child.get("source_range") or {}
            rate = _rate(source_range.get("start_time"), rate_default) \
                if isinstance(source_range, dict) else rate_default
            duration = _value(source_range.get("duration"), 0.0, rate) \
                if isinstance(source_range, dict) else 0.0
            if schema.startswith("Gap"):
                cursor += duration
                continue
            if not schema.startswith("Clip"):
                skipped.append({"reason": "unsupported_item", "OTIO_SCHEMA": schema})
                continue
            media_reference = child.get("media_reference") or {}
            path = str(media_reference.get("target_url") or "").strip()
            if path.startswith("file://"):
                path = path[7:]
            if not path:
                skipped.append({"reason": "clip_without_target_url",
                                "name": child.get("name") or ""})
                continue
            start = _value(source_range.get("start_time"), 0.0, rate) \
                if isinstance(source_range, dict) else 0.0
            if duration <= 0:
                available = media_reference.get("available_range") or {}
                duration = _value(available.get("duration"), 0.0, rate) \
                    if isinstance(available, dict) else 0.0
            if duration <= 0:
                skipped.append({"reason": "clip_without_duration", "name": child.get("name") or ""})
                continue
            segments.append({
                "path": path, "start": round(cursor, 6),
                "duration": round(duration, 6),
                "source_start": round(start, 6),
            })
            cursor += duration
        if segments:
            tracks.append({"type": track_type,
                           "name": str(track.get("name") or track_type),
                           "segments": segments})
    if not tracks:
        raise SkillError("OTIO 没有可导入的视频/音频片段", code="VALIDATION",
                         details={"skipped": skipped})
    return {
        "name": str(timeline_name), "canvas": canvas or {"width": 1920, "height": 1080, "fps": rate_default},
        "tracks": tracks, "skipped": skipped,
    }
