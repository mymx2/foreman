"""草稿维护：relink、replace-media、prune。

这些操作会改草稿结构，默认写出副本（`--out`），只有显式 `--in-place`
才写回原目录；写回前会调用 `backup_draft_files` 保留导出前快照。
"""

from __future__ import annotations

import copy
import json
import os
import shutil
from pathlib import Path

from .errors import SkillError
from . import draft as draft_mod
from . import media as media_mod

MEDIA_BUCKETS = ("videos", "images", "audios", "stickers")


def _strip_prefix(text, prefix):
    """按分隔符归一 + Windows 大小写不敏感地剥离前缀。

    纯字面前缀会把 ``C:\\old`` 匹配到 ``C:\\older\\x``；这里要求前缀之后
    必须是分隔符或字符串结束，并容忍 ``/`` 与 ``\\``、盘符大小写差异。
    """
    if not prefix or not text:
        return None
    sep = "\\" if os.name == "nt" else "/"
    other = "/" if sep == "\\" else "\\"
    left = text.replace(other, sep)
    right = prefix.replace(other, sep)
    if os.name == "nt":
        if not left.casefold().startswith(right.casefold()):
            return None
    elif not left.startswith(right):
        return None
    if len(left) == len(right):
        return ""
    if right[-1] in ("\\", "/") or left[len(right)] in ("\\", "/"):
        rest = text[len(right):]
        # ``C:\media\..\Windows\x`` 归一后不在前缀下，不能拼到新前缀去
        if ".." in rest.replace("/", "\\").split("\\"):
            return None
        return rest
    return None


def _join_prefix(to_prefix, rest):
    """拼接新前缀，避免 ``C:\\new\\`` + ``\\clip.mp4`` 拼出双分隔符。"""
    if to_prefix and rest and to_prefix[-1] in ("\\", "/") and rest[0] in ("\\", "/"):
        rest = rest[1:]
    return (to_prefix or "") + rest


def _load(draft_dir):
    resolved = draft_mod.resolve_draft_info(draft_dir)
    root = resolved["draft_dir"]
    info = resolved["info_path"]
    if not info:
        raise SkillError("不是剪映草稿目录", code="DRAFT_NOT_FOUND",
                         details={"draft": str(root)})
    try:
        doc = json.loads(media_mod.read_plain_bytes(info).decode("utf-8-sig"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise SkillError("草稿不是明文 JSON", code="DRAFT_ENCRYPTED",
                         details={"path": str(info)}) from exc
    return root, info, doc


def _save(root, info, doc, out_dir, *, in_place=False):
    if in_place:
        draft_mod.backup_draft_files(root, label="maintenance")
        draft_mod._write_json(info, doc)
        return root
    if out_dir is None:
        raise SkillError("需要 --out 或 --in-place", code="VALIDATION")
    target = media_mod.local_path(out_dir, field="输出草稿目录")
    if target.exists() and any(target.iterdir()):
        raise SkillError("输出草稿目录非空", code="OUTPUT_EXISTS",
                         details={"path": str(target)})
    if target.exists():
        target.rmdir()
    media_mod.copy_tree(root, target)
    draft_mod._write_json(target / info.relative_to(root), doc)
    return target


def _media_paths(doc):
    for bucket in MEDIA_BUCKETS:
        for item in (doc.get("materials") or {}).get(bucket) or []:
            if isinstance(item, dict) and item.get("path"):
                yield bucket, item


def relink(draft_dir, *, out_dir=None, in_place=False, from_prefix=None,
           to_prefix=None, directory=None, recursive=True, missing_only=True):
    root, info, doc = _load(draft_dir)
    if not from_prefix and not directory:
        raise SkillError("relink 需要 --from/--to 或 --dir", code="VALIDATION")
    changes, missing, ambiguous = [], [], []
    index = {}
    search_root = None
    if directory:
        search_root = media_mod.local_path(directory, field="素材目录")
        if not media_mod.is_plain_dir(search_root):
            if search_root.exists():
                raise SkillError(
                    "素材目录是链接/重解析点，不能作为 relink 根目录",
                    code="VALIDATION", details={"path": str(search_root)},
                    fix="改用本地普通目录；链接目录一律不跟随。")
            raise SkillError("素材目录不存在", code="VALIDATION",
                             details={"path": str(search_root)})
        for item in media_mod.iter_plain_files(search_root, recursive=recursive):
            index.setdefault(item.name.casefold(), []).append(item)
    for bucket, item in _media_paths(doc):
        old = str(item.get("path") or "").strip()
        if not old or old.startswith("##_draftpath_placeholder_"):
            continue
        try:
            local = media_mod.local_path(old, field=f"{bucket}.path")
        except SkillError:
            missing.append({"bucket": bucket, "id": item.get("id"), "path": old,
                            "reason": "unsafe"})
            continue
        exists = media_mod.is_plain_file(local)
        if missing_only and exists:
            continue
        new = None
        if from_prefix:
            rest = _strip_prefix(old, from_prefix)
            if rest is not None:
                new = _join_prefix(to_prefix, rest)
        elif directory:
            candidates = index.get(local.name.casefold()) or []
            if len(candidates) == 1:
                new = str(candidates[0])
            elif len(candidates) > 1:
                ambiguous.append({"id": item.get("id"), "name": local.name,
                                  "candidates": [str(path) for path in candidates]})
                continue
        if not new:
            if missing_only and not exists:
                missing.append({"bucket": bucket, "id": item.get("id"), "path": old,
                                "reason": "not_found"})
            continue
        # --from/--to 拼出的新路径同样要先过 local_path：直接 is_plain_file
        # 会对 UNC/junction 目标先发起 lstat，等于把 SMB/NTLM 探测放回来。
        try:
            new_path = media_mod.local_path(new, field="新素材路径")
        except SkillError:
            missing.append({"bucket": bucket, "id": item.get("id"), "path": new,
                            "reason": "unsafe"})
            continue
        if not media_mod.is_plain_file(new_path):
            missing.append({"bucket": bucket, "id": item.get("id"), "path": new,
                            "reason": "target_missing"})
            continue
        item["path"] = str(new_path.resolve())
        changes.append({"bucket": bucket, "id": item.get("id"),
                        "old": old, "new": item["path"]})
    result = {"changes": changes, "missing": missing, "ambiguous": ambiguous}
    if changes:
        result["out"] = str(_save(root, info, doc, out_dir, in_place=in_place))
    return result


def _material_for_segment(doc, segment):
    material_id = segment.get("material_id")
    for bucket in MEDIA_BUCKETS:
        for item in (doc.get("materials") or {}).get(bucket) or []:
            if isinstance(item, dict) and item.get("id") == material_id:
                return bucket, item
    return None, None


def replace_media(draft_dir, segment_ref, new_path, *, ffprobe, out_dir=None,
                  in_place=False, retime=False):
    root, info, doc = _load(draft_dir)
    segment = draft_mod._find_segment(doc, segment_ref)
    bucket, material = _material_for_segment(doc, segment)
    if material is None:
        raise SkillError("片段的主素材不是可替换的视频/图片/音频",
                         code="VALIDATION", details={"segment": segment_ref})
    probe = media_mod.probe_media(ffprobe, new_path)
    if bucket == "videos" and not probe.get("has_video"):
        raise SkillError("新素材没有视频流", code="VALIDATION")
    if bucket == "audios" and not probe.get("has_audio"):
        raise SkillError("新素材没有音频流", code="VALIDATION")
    target = segment.get("target_timerange") or {}
    target_duration = float(target.get("duration") or 0) / 1e6
    old_duration = float(material.get("duration") or 0) / 1e6
    source = segment.get("source_timerange") or {}
    source_start = float(source.get("start") or 0) / 1e6
    warnings = []
    new_duration = float(probe.get("duration") or 0)
    speed = float(segment.get("speed") or 1.0)
    if retime and target_duration > 0 and new_duration > 0:
        speed = round(new_duration / target_duration, 6)
        source["duration"] = int(round(target_duration * speed * 1e6))
        segment["speed"] = speed
    elif target_duration > new_duration > 0:
        warnings.append("新素材短于片段占用时长，已裁短目标区间")
        target["duration"] = int(round(new_duration * 1e6))
        if isinstance(source, dict):
            source["duration"] = int(round(new_duration * speed * 1e6))
    if source_start + (target_duration * speed) > new_duration + 1e-6:
        source["start"] = 0
        warnings.append("原片段源起点超出新素材，已重置为 0")
    material.update({
        "path": probe["path"], "material_name": probe["name"],
        "duration": int(round(new_duration * 1e6)),
        "width": int(probe.get("width") or 0), "height": int(probe.get("height") or 0),
        "has_audio": bool(probe.get("has_audio")) if bucket == "videos" else material.get("has_audio"),
    })
    if bucket == "videos":
        width, height = int(probe.get("width") or 0), int(probe.get("height") or 0)
        material["crop_source_size"] = {"width": width, "height": height}
        material["crop_img_size"] = {"width": width, "height": height}
    segment.setdefault("source_timerange", {})["start"] = int(round(source_start * 1e6))
    result = {
        "segment_id": segment.get("id"), "material_id": material.get("id"),
        "material_bucket": bucket, "old_duration": round(old_duration, 6),
        "new_duration": round(new_duration, 6), "speed": speed,
        "warnings": warnings,
    }
    result["out"] = str(_save(root, info, doc, out_dir, in_place=in_place))
    return result


def _referenced_ids(doc):
    known = set()
    for items in (doc.get("materials") or {}).values():
        for item in items or []:
            if isinstance(item, dict) and item.get("id"):
                known.add(item["id"])
    referenced = set()
    for track in doc.get("tracks") or []:
        for segment in track.get("segments") or []:
            # 与 render 扫描器（jy.py `_draft_material_present`）保持同一口径：
            # 导入/补丁草稿有时把效果 id 放在主素材位或 local_material_id。
            for key in ("material_id", "local_material_id"):
                value = segment.get(key)
                if value:
                    referenced.add(value)
            referenced.update(draft_mod._ref_values(
                segment.get("extra_material_refs")))
    # 被引用的材质还可能通过 text_material_id 等字段间接引用另一个材质。
    changed = True
    while changed:
        changed = False
        for items in (doc.get("materials") or {}).values():
            for item in items or []:
                if not isinstance(item, dict) or item.get("id") not in referenced:
                    continue
                for value in _walk_strings(item):
                    if value in known and value not in referenced:
                        referenced.add(value)
                        changed = True
    return known, referenced


def _walk_strings(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for item in value.values():
            yield from _walk_strings(item)
    elif isinstance(value, list):
        for item in value:
            yield from _walk_strings(item)


def prune(draft_dir, *, out_dir=None, in_place=False, keep_buckets=()):
    root, info, doc = _load(draft_dir)
    known, referenced = _referenced_ids(doc)
    removed = []
    for bucket, items in (doc.get("materials") or {}).items():
        if bucket in keep_buckets:
            continue
        kept = []
        for item in items or []:
            material_id = item.get("id") if isinstance(item, dict) else None
            if material_id and material_id in known and material_id not in referenced:
                removed.append({"bucket": bucket, "id": material_id,
                                "name": item.get("name") or item.get("material_name")})
            else:
                kept.append(item)
        doc["materials"][bucket] = kept
    result = {"removed": removed, "removed_count": len(removed),
              "referenced": len(referenced), "known": len(known)}
    if removed:
        result["out"] = str(_save(root, info, doc, out_dir, in_place=in_place))
    return result
