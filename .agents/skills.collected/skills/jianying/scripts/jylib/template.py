"""片段模板：从真实草稿提取任意片段并盖印到另一个草稿。

与 capcut-cli 的 `save-template` / `apply-template` 对应，但只处理明文
draft_info.json。模板保存片段、主素材和全部 extra_material_refs，应用时重新
分配所有 id，避免不同草稿中的 UUID 冲突。
"""

from __future__ import annotations

import copy
import json
import shutil
import uuid
from pathlib import Path

from .errors import SkillError
from . import draft as draft_mod
from . import media as media_mod

FORMAT = "jianying-segment-template"
VERSION = 1


def _uid():
    return str(uuid.uuid4()).upper()


def _load(draft_dir):
    resolved = draft_mod.resolve_draft_info(draft_dir)
    root = resolved["draft_dir"]
    info = resolved["info_path"]
    if not info:
        raise SkillError("不是剪映草稿目录", code="DRAFT_NOT_FOUND",
                         details={"draft": str(root)})
    try:
        doc = json.loads(info.read_text("utf-8-sig"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise SkillError("草稿不是明文 JSON，模板功能无法读写",
                         code="DRAFT_ENCRYPTED",
                         details={"path": str(info)}) from exc
    return root, info, doc


def _material_of(doc, material_id):
    for bucket, items in (doc.get("materials") or {}).items():
        for item in items or []:
            if isinstance(item, dict) and item.get("id") == material_id:
                return bucket, item
    return None, None


def _segment_track(doc, segment):
    for track in doc.get("tracks") or []:
        for item in track.get("segments") or []:
            if item.get("id") == segment.get("id"):
                return track
    return None


def save(draft_dir, ref, name, out_path):
    root, info, doc = _load(draft_dir)
    segment = draft_mod._find_segment(doc, ref)
    track = _segment_track(doc, segment)
    if track is None:
        raise SkillError("片段不在任何轨道上", code="DRAFT_INVALID")
    bucket, material = _material_of(doc, segment.get("material_id"))
    if material is None:
        raise SkillError("片段的主素材不存在", code="DRAFT_INVALID",
                         details={"material_id": segment.get("material_id")})
    extras = []
    missing = []
    for ref_id in segment.get("extra_material_refs") or []:
        extra_bucket, extra = _material_of(doc, ref_id)
        if extra is None:
            missing.append(ref_id)
        else:
            extras.append({"bucket": extra_bucket, "value": extra})
    if missing:
        raise SkillError("片段引用了不存在的 extra 材质，拒绝生成残缺模板",
                         code="DRAFT_INVALID", details={"missing": missing})
    payload = {
        "format": FORMAT,
        "version": VERSION,
        "name": str(name or "").strip() or "未命名模板",
        "track_type": track.get("type"),
        "track_name": track.get("name") or "",
        "segment": segment,
        "material": {"bucket": bucket, "value": material},
        "extras": extras,
    }
    target = media_mod.local_path(out_path, field="模板输出路径").expanduser()
    if target.exists():
        raise SkillError("模板输出文件已存在", code="OUTPUT_EXISTS",
                         details={"path": str(target)},
                         fix="换一个输出路径，或先确认后手动删除旧模板")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=2), "utf-8")
    return {
        "out": str(target), "name": payload["name"], "type": track.get("type"),
        "material_bucket": bucket, "extras": len(extras),
        "segment_id": segment.get("id"),
    }


def _read_template(template_path):
    target = media_mod.local_path(template_path, field="模板文件")
    if not target.is_file():
        raise SkillError("模板文件不存在", code="FILE_NOT_FOUND",
                         details={"path": str(target)})
    try:
        payload = json.loads(target.read_text("utf-8-sig"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise SkillError("模板不是合法 JSON", code="PARSE_FAIL",
                         details={"path": str(target)}) from exc
    if payload.get("format") != FORMAT:
        raise SkillError("不是本技能生成的片段模板", code="VALIDATION",
                         details={"format": payload.get("format")})
    if int(payload.get("version") or 0) > VERSION:
        raise SkillError("模板版本高于当前技能", code="VALIDATION",
                         details={"version": payload.get("version")})
    return payload


def _rewrite_refs(value, mapping):
    """只替换草稿里的引用字段，不碰 resource_id/path。"""
    if isinstance(value, list):
        return [_rewrite_refs(item, mapping) for item in value]
    if isinstance(value, dict):
        result = {}
        for key, item in value.items():
            if key in {"id", "material_id", "text_material_id"} and isinstance(item, str):
                result[key] = mapping.get(item, item)
            elif key == "extra_material_refs" and isinstance(item, list):
                result[key] = [mapping.get(ref, ref) for ref in item]
            else:
                result[key] = _rewrite_refs(item, mapping)
        return result
    return value


def _track_template(doc, track_type):
    visual = [track for track in doc.get("tracks") or []
              if track.get("type") in {"video", "image"}]
    existing = [track for track in doc.get("tracks") or []
                if track.get("type") == track_type]
    if existing:
        return existing[0], False
    if track_type in {"video", "image"}:
        flag = 2 if visual else 0
    else:
        flag = 0
    track = {
        "attribute": 0, "flag": flag, "id": _uid(), "is_default_name": False,
        "name": "模板-" + track_type, "segments": [], "type": track_type,
    }
    doc.setdefault("tracks", []).append(track)
    return track, True


def _render_index(track_type, doc, track):
    if track_type in {"video", "image"}:
        visual = [item for item in doc.get("tracks") or []
                  if item.get("type") in {"video", "image"}]
        return 0 if track is visual[0] else max(1, visual.index(track))
    if track_type == "text":
        texts = [item for item in doc.get("tracks") or [] if item.get("type") == "text"]
        return 15000 + max(0, texts.index(track))
    return 0


def _apply_text_override(material, text):
    if material.get("type") != "text":
        raise SkillError("text 覆盖只能用于文字模板", code="VALIDATION")
    try:
        content = json.loads(material.get("content") or "{}")
    except json.JSONDecodeError:
        content = {}
    content["text"] = str(text)
    length = len(str(text).encode("utf-16-le")) // 2
    styles = content.get("styles") or [{}]
    styles[0]["range"] = [0, length]
    content["styles"] = styles
    encoded = json.dumps(content, ensure_ascii=False, separators=(",", ":"))
    material["content"] = encoded
    material["base_content"] = encoded


def apply(draft_dir, template_path, start, duration=None, text=None,
          x=None, y=None, out_dir=None):
    root, info, doc = _load(draft_dir)
    payload = _read_template(template_path)
    track_type = str(payload.get("track_type") or "")
    if track_type not in draft_mod.TRACK_TYPES:
        raise SkillError("模板轨道类型不支持", code="VALIDATION",
                         details={"track_type": track_type})
    start_s = draft_mod._number("start", start, min_value=0.0)
    segment = copy.deepcopy(payload["segment"])
    material_entry = payload.get("material") or {}
    bucket = str(material_entry.get("bucket") or "")
    main_material = copy.deepcopy(material_entry.get("value") or {})
    if bucket not in (doc.get("materials") or {}):
        raise SkillError("模板主素材桶在当前草稿不存在", code="VALIDATION",
                         details={"bucket": bucket})
    extras = []
    for entry in payload.get("extras") or []:
        extra_bucket = str(entry.get("bucket") or "")
        if extra_bucket not in (doc.get("materials") or {}):
            raise SkillError("模板 extra 材质桶在当前草稿不存在", code="VALIDATION",
                             details={"bucket": extra_bucket})
        extras.append((extra_bucket, copy.deepcopy(entry.get("value") or {})))

    old_ids = [segment.get("id"), main_material.get("id")]
    old_ids.extend(value.get("id") for _, value in extras)
    mapping = {old: _uid() for old in old_ids if old}
    segment = _rewrite_refs(segment, mapping)
    main_material = _rewrite_refs(main_material, mapping)
    extras = [(bucket_name, _rewrite_refs(value, mapping))
              for bucket_name, value in extras]

    if text is not None:
        _apply_text_override(main_material, text)
    target_duration = (segment.get("target_timerange") or {}).get("duration") or 0
    if duration is not None:
        target_duration = draft_mod.us(draft_mod._number(
            "duration", duration, positive=True))
        segment.setdefault("target_timerange", {})["duration"] = target_duration
        source = segment.get("source_timerange")
        if isinstance(source, dict):
            speed = float(segment.get("speed") or 1.0)
            source["duration"] = int(round(target_duration * speed))
    segment.setdefault("target_timerange", {})["start"] = draft_mod.us(start_s)
    if target_duration and segment.setdefault("target_timerange", {}).get("duration") is None:
        segment["target_timerange"]["duration"] = 0

    track, created = _track_template(doc, track_type)
    segment["id"] = mapping.get(segment.get("id"), _uid())
    segment["material_id"] = main_material.get("id")
    segment["extra_material_refs"] = [value.get("id") for _, value in extras
                                      if value.get("id")]
    segment["track_render_index"] = (doc.get("tracks") or []).index(track)
    segment["render_index"] = _render_index(track_type, doc, track)
    if x is not None or y is not None:
        clip = segment.setdefault("clip", {})
        transform = clip.setdefault("transform", {"x": 0.0, "y": 0.0})
        if x is not None:
            transform["x"] = draft_mod._number("x", x, min_value=-1.0, max_value=1.0)
        if y is not None:
            transform["y"] = draft_mod._number("y", y, min_value=-1.0, max_value=1.0)
    track.setdefault("segments", []).append(segment)
    doc["materials"][bucket].append(main_material)
    for bucket_name, value in extras:
        doc["materials"][bucket_name].append(value)

    end = (segment.get("target_timerange", {}).get("start") or 0) + \
          (segment.get("target_timerange", {}).get("duration") or 0)
    doc["duration"] = max(int(doc.get("duration") or 0), end)

    if out_dir is None:
        draft_mod.backup_draft_files(root, label="template-apply")
        draft_mod._write_json(info, doc)
        out_root = root
    else:
        out_root = media_mod.local_path(out_dir, field="输出草稿目录")
        if out_root.exists() and any(out_root.iterdir()):
            raise SkillError("输出草稿目录非空", code="OUTPUT_EXISTS",
                             details={"path": str(out_root)})
        if out_root.exists():
            out_root.rmdir()
        media_mod.copy_tree(root, out_root)
        relative = info.relative_to(root)
        draft_mod._write_json(out_root / relative, doc)
    return {
        "draft_dir": str(out_root), "track": track_type, "created_track": created,
        "segment_id": segment.get("id"), "material_id": main_material.get("id"),
        "extras": len(extras), "start": round(start_s, 6),
        "duration": round((segment.get("target_timerange") or {}).get("duration", 0) / 1_000_000, 6),
    }
