"""Build, read, and re-link 剪映 plaintext drafts.

The JSON shapes here were recovered from drafts that 剪映 11.8 itself rendered;
the notable ones are recorded in references/draft-format.md. Two rules matter
most: manual text must be a ``text`` material (``subtitle`` is AI-subtitle and
fails the export entitlement check), and a non-main video track needs ``flag: 2``.
"""

from __future__ import annotations

import copy
import hashlib
import json
import math
import os
import re
import shutil
import stat
import time
import uuid
from pathlib import Path

from .errors import SkillError
from . import media as media_mod
from . import resources as resources_mod
from . import versions as versions_mod

ASSET_DIR = Path(__file__).resolve().parents[2] / "assets"
MARKER = ".jianying-skill.json"
TRACK_TYPES = {"video", "image", "audio", "text", "sticker", "effect"}


def _backup_stamp():
    """唯一备份名：秒 + 毫秒 + uuid 短后缀，同一秒两次操作也不覆盖。"""
    return f"{time.strftime('%Y%m%d-%H%M%S')}-{int(time.time() * 1000) % 100000:05d}-{uuid.uuid4().hex[:6]}"


def _safe_component(value):
    cleaned = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", str(value)).strip(" .")
    return cleaned or "jianying-draft"


def _number(field, value, *, original=None, positive=False, min_value=None,
            max_value=None):
    """把输入转成有限数值；非法/越界抛 VALIDATION，带 field 与原值。"""
    raw = original if original is not None else value
    if isinstance(value, bool):
        raise SkillError(f"{field} 必须是数字，不能是布尔值：{raw!r}", code="VALIDATION",
                         details={"field": field, "value": raw})
    try:
        number = float(value)
    except (TypeError, ValueError):
        raise SkillError(f"{field} 必须是数字：{raw!r}", code="VALIDATION",
                         details={"field": field, "value": raw})
    if not math.isfinite(number):
        raise SkillError(f"{field} 必须是有限数值", code="VALIDATION",
                         details={"field": field, "value": raw})
    if positive and number <= 0:
        raise SkillError(f"{field} 必须大于 0", code="VALIDATION",
                         details={"field": field, "value": raw})
    if min_value is not None and number < min_value:
        raise SkillError(f"{field} 不能小于 {min_value}", code="VALIDATION",
                         details={"field": field, "value": raw})
    if max_value is not None and number > max_value:
        raise SkillError(f"{field} 不能大于 {max_value}", code="VALIDATION",
                         details={"field": field, "value": raw})
    return number

def _strict_bool(field, value, default=False):
    """只接受 bool/0/1/true/false；字符串 "false" 不能变成 True。"""
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)) and value in (0, 1):
        return bool(value)
    if isinstance(value, str):
        text = value.strip().lower()
        if text in {"true", "1", "yes", "on"}:
            return True
        if text in {"false", "0", "no", "off", ""}:
            return False
    raise SkillError(f"{field} 必须是布尔值", code="VALIDATION",
                     details={"field": field, "value": value})


KEYFRAME_CHANNELS = {
    "scale": ("KFTypeScaleX", "KFTypeScaleY"),
    "scale_x": ("KFTypeScaleX",),
    "scale_y": ("KFTypeScaleY",),
    "position_x": ("KFTypePositionX",),
    "position_y": ("KFTypePositionY",),
    "opacity": ("KFTypeAlpha",),
    "alpha": ("KFTypeAlpha",),
    "rotation": ("KFTypeRotation",),
    "volume": ("KFTypeVolume",),
}


def uid():
    return str(uuid.uuid4()).upper()


def us(seconds):
    return int(round(float(seconds) * 1_000_000))


def _volume(spec):
    return _number("volume", spec.get("volume", 1.0), min_value=0.0, max_value=10.0)


def load_json(path):
    target = media_mod.local_path(path, field="JSON 文件")
    try:
        # utf-8-sig 兼容 Notepad/PowerShell 写出的带 BOM 文件
        text = target.read_text("utf-8-sig")
    except OSError as exc:
        raise SkillError(
            "文件读不了",
            code="FILE_NOT_FOUND",
            details={"path": str(target), "reason": str(exc)},
            fix="确认路径存在；计划/补丁文件要用 UTF-8 保存。",
        ) from exc
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise SkillError(
            "JSON 解析失败",
            code="JSON_INVALID",
            details={"path": str(target), "line": exc.lineno, "column": exc.colno,
                     "reason": exc.msg},
            fix="检查 JSON 语法；不要保存为带 BOM 的 UTF-8；PowerShell 里不要内联长 JSON，写成文件再传。",
        ) from exc


def _write_json(path, document):
    target = Path(path)
    temp = target.with_name(
        f".{target.name}.{os.getpid()}.{uuid.uuid4().hex[:6]}.tmp")
    try:
        payload = json.dumps(document, ensure_ascii=False, separators=(",", ":"))
        temp.write_text(payload, "utf-8")
        os.replace(temp, target)
    except (OSError, TypeError, ValueError) as exc:
        raise SkillError("草稿文件写入失败", code="OUTPUT_WRITE_FAILED",
                         details={"path": str(target), "reason": str(exc)}) from exc
    finally:
        try:
            temp.unlink(missing_ok=True)
        except OSError:
            pass


def backup_draft_files(draft_dir, label="render"):
    """Copy the editable draft JSON before handing it to the app or an export."""
    resolved = resolve_draft_info(draft_dir)
    if not resolved["info_path"]:
        raise SkillError("不是草稿目录", code="DRAFT_NOT_FOUND",
                         details={"draft": str(draft_dir)})
    folder = resolved["draft_dir"]
    backup_dir = folder / ".jianying-backups"
    backups = []
    stamp = _backup_stamp()
    try:
        backup_dir.mkdir(parents=True, exist_ok=True)
        for name in ("draft_info.json", "draft_meta_info.json", "draft_content.json",
                     "attachment_editing.json", "draft.extra", "common_attachment"):
            source = folder / name
            if not source.exists() or _is_link(source):
                continue
            target = backup_dir / f"{label}-{name}.{stamp}"
            if source.is_dir():
                shutil.copytree(source, target, symlinks=True)
            else:
                shutil.copy2(source, target)
            backups.append(str(target))
    except (OSError, shutil.Error) as exc:
        raise SkillError("导出前备份草稿失败，已中止", code="OUTPUT_WRITE_FAILED",
                         details={"draft": str(folder), "reason": str(exc)}) from exc
    return backups


def _asset(name):
    path = ASSET_DIR / name
    if not path.is_file():
        raise SkillError(f"技能资源缺失：{name}", code="ASSET_MISSING",
                         details={"path": str(path)})
    return load_json(path)


_HEX_RGB = re.compile(r"^[0-9a-fA-F]{6}$")
_TIMELINE_ID = re.compile(r"^(?!\.{1,2}$)[A-Za-z0-9._-]{1,128}$")
_REPARSE_POINT = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)


def _is_link(path):
    """Symlink or Windows junction/reparse point; never follow it."""
    path = Path(path)
    try:
        if path.is_symlink():
            return True
        attrs = getattr(path.lstat(), "st_file_attributes", 0)
    except FileNotFoundError:
        return False
    except OSError:
        return True
    return bool(attrs & _REPARSE_POINT)


def _assert_plain_tree(root):
    """Reject symlinks/junctions anywhere below a draft before copying it."""
    root = Path(root)
    if _is_link(root):
        raise SkillError(
            "草稿目录是符号链接或 junction，拒绝复制",
            code="UNSAFE_PATH",
            details={"path": str(root)},
            fix="把草稿复制到普通目录，或先移除链接。",
        )
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        for name in dirnames + filenames:
            path = Path(dirpath) / name
            if _is_link(path):
                raise SkillError(
                    "草稿目录包含符号链接或 junction，拒绝复制",
                    code="UNSAFE_PATH",
                    details={"path": str(path)},
                    fix="第三方草稿不应包含链接；请先检查草稿来源。",
                )


def hex_rgb(value, default="#FFFFFF"):
    text = str(value if value is not None else default).strip().lstrip("#")
    if len(text) == 3:
        text = "".join(ch * 2 for ch in text)
    if not _HEX_RGB.match(text):
        raise SkillError(f"颜色必须是 #RRGGBB：{value!r}", code="VALIDATION",
                         details={"field": "color", "value": value})
    return [int(text[i:i + 2], 16) / 255.0 for i in (0, 2, 4)]


def resolve_draft_info(draft_dir):
    raw = media_mod.local_path(draft_dir, field="草稿目录")
    if _is_link(raw):
        raise SkillError("草稿目录是符号链接或 junction，拒绝读取",
                         code="UNSAFE_PATH", details={"path": str(raw)})
    root = raw.resolve()
    root_info = root / "draft_info.json"
    if _is_link(root_info):
        raise SkillError(
            "draft_info.json 是符号链接，拒绝读取草稿目录之外的文件",
            code="UNSAFE_PATH",
            details={"path": str(root_info)},
            fix="把草稿复制到本地普通目录，或移除符号链接后重试。",
        )
    if root_info.is_file():
        return {"draft_dir": root, "info_path": root_info, "layout": "single",
                "timeline_id": None}
    timelines = root / "Timelines"
    candidate = None
    timeline_id = None
    if _is_link(timelines):
        raise SkillError(
            "Timelines 是符号链接或 junction，拒绝读取",
            code="UNSAFE_PATH",
            details={"path": str(timelines)},
        )
    if timelines.is_dir():
        timeline_base = timelines.resolve()
        if not timeline_base.is_relative_to(root):
            raise SkillError(
                "Timelines 指向草稿目录之外，拒绝读取",
                code="UNSAFE_PATH",
                details={"path": str(timelines), "resolved": str(timeline_base)},
            )
        project = timeline_base / "project.json"
        if not _is_link(project) and project.is_file():
            try:
                main_id = str(load_json(project).get("main_timeline_id") or "")
            except (OSError, json.JSONDecodeError, SkillError):
                main_id = ""
            if _TIMELINE_ID.fullmatch(main_id):
                timeline_root = (timeline_base / main_id).resolve()
                maybe = timeline_root / "draft_info.json"
                if (timeline_root.parent == timeline_base
                        and not _is_link(maybe) and maybe.is_file()):
                    candidate, timeline_id = maybe, main_id
        if candidate is None:
            found = []
            for child in timeline_base.iterdir():
                if _is_link(child) or not child.is_dir():
                    continue
                timeline_root = child.resolve()
                if timeline_root.parent != timeline_base:
                    continue
                info = timeline_root / "draft_info.json"
                if not _is_link(info) and info.is_file():
                    found.append(info)
            if found:
                candidate = max(found, key=lambda p: p.stat().st_mtime)
                timeline_id = candidate.parent.name
    return {"draft_dir": root, "info_path": candidate,
            "layout": "multi-timeline" if candidate else "missing",
            "timeline_id": timeline_id}


def _segment(material_id, start_s, duration_s, *, source_start_s=0.0,
             source_duration_s=None, speed=1.0, volume=1.0, render_index=0,
             track_index=0):
    source = duration_s if source_duration_s is None else source_duration_s
    return {
        "id": uid(),
        "material_id": material_id,
        "target_timerange": {"start": us(start_s), "duration": us(duration_s)},
        "source_timerange": {"start": us(source_start_s), "duration": us(source)},
        "speed": float(speed),
        "volume": float(volume),
        "extra_material_refs": [],
        "is_placeholder": False,
        "render_index": int(render_index),
        "visible": True,
        "clip": {
            "alpha": 1.0,
            "flip": {"horizontal": False, "vertical": False},
            "rotation": 0.0,
            "scale": {"x": 1.0, "y": 1.0},
            "transform": {"x": 0.0, "y": 0.0},
        },
        "uniform_scale": {"on": True, "value": 1.0},
        "hdr_settings": {"intensity": 1.0, "mode": 1, "nits": 1000},
        "caption_info": None,
        "enable_adjust": True,
        "enable_color_correct_adjust": False,
        "enable_lut": False,
        "intensifies_audio": False,
        "last_nonzero_volume": 1.0,
        "reverse": False,
        "template_id": "",
        "track_attribute": 0,
        "track_render_index": int(track_index),
    }


def _apply_video_animations(segment, spec, doc, warnings):
    animations = spec.get("animations")
    if animations is None:
        return
    if not isinstance(animations, list) or not animations:
        raise SkillError("animations 必须是非空数组", code="VALIDATION")
    entries = []
    for index, item in enumerate(animations):
        if not isinstance(item, dict):
            raise SkillError(f"animations[{index}] 必须是对象", code="VALIDATION")
        kind = str(item.get("type") or "").strip().lower()
        if kind not in {"in", "out", "loop"}:
            raise SkillError("animations[].type 只能是 in / out / loop",
                             code="VALIDATION",
                             details={"index": index, "value": kind})
        resource_id = str(item.get("resource_id") or "").strip()
        if not resource_id:
            raise SkillError(f"animations[{index}].resource_id 不能为空",
                             code="VALIDATION")
        duration = _number(f"animations[{index}].duration",
                           item.get("duration", 0.5),
                           original=item.get("duration"), positive=True)
        entries.append({
            "id": resource_id,
            "type": kind,
            "duration": us(duration),
            "path": str(item.get("path") or ""),
            "resource_id": resource_id,
            "third_resource_id": "0",
            "source_platform": int(_number(
                "source_platform", item.get("source_platform", 1),
                original=item.get("source_platform"), min_value=0)),
            "name": str(item.get("name") or ""),
            "category_id": str(item.get("category_id") or ""),
            "category_name": str(item.get("category_name") or ""),
            "material_type": "video",
        })
    material = {
        "id": uid(),
        "type": "video_animation",
        "animations": entries,
        "multi_language_current": "none",
    }
    doc["materials"]["material_animations"].append(material)
    segment["extra_material_refs"].append(material["id"])
    warnings.append(
        "视频动画已写入 material_animations[type=video_animation]；"
        "动画资源必须已缓存，像素未验收。")


def _apply_clip(segment, spec):
    if "opacity" in spec:
        segment["clip"]["alpha"] = _number(
            "opacity", spec["opacity"], original=spec["opacity"],
            min_value=0.0, max_value=1.0)
    if "rotation" in spec:
        segment["clip"]["rotation"] = _number(
            "rotation", spec["rotation"], original=spec["rotation"])
    transform = spec.get("transform") or {}
    if transform:
        segment["clip"]["transform"] = {
            "x": _number("x", transform.get("x", 0.0), original=transform.get("x")),
            "y": _number("y", transform.get("y", 0.0), original=transform.get("y")),
        }
    if "x" in spec or "y" in spec:
        segment["clip"]["transform"] = {
            "x": _number("x", spec.get("x", segment["clip"]["transform"]["x"]),
                         original=spec.get("x")),
            "y": _number("y", spec.get("y", segment["clip"]["transform"]["y"]),
                         original=spec.get("y")),
        }
    scale = spec.get("scale", 1.0)
    if isinstance(scale, dict):
        segment["clip"]["scale"] = {
            "x": _number("scale.x", scale.get("x", 1.0), original=scale.get("x"),
                         positive=True),
            "y": _number("scale.y", scale.get("y", 1.0), original=scale.get("y"),
                         positive=True),
        }
    else:
        value = _number("scale", scale, original=scale, positive=True)
        segment["clip"]["scale"] = {"x": value, "y": value}


_KF_RANGE = {
    "KFTypeScaleX": "positive",
    "KFTypeScaleY": "positive",
    "KFTypeAlpha": "range01",
}


def _keyframe_channel(property_type, points, *, value_index=0, value_count=1):
    channel = {"id": uid(), "material_id": "", "property_type": property_type,
               "keyframe_list": []}
    kind = _KF_RANGE.get(property_type)
    for point in points:
        if isinstance(point, dict):
            at_raw = point.get("time", 0.0)
            values = point.get("values")
            if values is None:
                values = [point.get("value", 0.0)]
        else:
            if not isinstance(point, (list, tuple)) or len(point) < 2:
                raise SkillError(
                    "关键帧点必须是 [time, value] 或 {time, value/values}",
                    code="VALIDATION", details={"point": point})
            at_raw, value = point[0], point[1]
            values = value if isinstance(value, list) else [value]
        at = _number("time", at_raw, original=point, min_value=0.0)
        if not isinstance(values, list):
            values = [values]
        if value_count > 1:
            if len(values) == value_count:
                values = [values[value_index]]
            elif len(values) != 1:
                raise SkillError(
                    f"关键帧值数量必须是 1 或 {value_count}",
                    code="VALIDATION",
                    details={"property": property_type, "values": values})
        parsed = []
        for v in values:
            if kind == "positive":
                num = _number("value", v, original=v, positive=True)
            elif kind == "range01":
                num = _number("value", v, original=v, min_value=0.0, max_value=1.0)
            else:
                num = _number("value", v, original=v)
            parsed.append(num)
        channel["keyframe_list"].append({
            "id": uid(),
            "time_offset": us(at),
            "left_control": {"x": 0.0, "y": 0.0},
            "right_control": {"x": 0.0, "y": 0.0},
            "values": parsed,
        })
    channel["keyframe_list"].sort(key=lambda k: k["time_offset"])
    times = [k["time_offset"] for k in channel["keyframe_list"]]
    if len(set(times)) != len(times):
        raise SkillError("关键帧时间点重复", code="VALIDATION",
                         details={"property": property_type})
    return channel


def _apply_keyframes(segment, raw):
    if not raw:
        return
    if not isinstance(raw, dict):
        raise SkillError("keyframes 必须是对象：{scale:[[0,1],[1.5,0.5]], opacity:[...]}",
                         code="VALIDATION")
    channels = []
    for name, points in raw.items():
        key = str(name).strip().lower()
        if key not in KEYFRAME_CHANNELS:
            raise SkillError(
                f"不支持的关键帧通道 {name!r}",
                code="VALIDATION",
                details={"supported": sorted(KEYFRAME_CHANNELS)},
            )
        if not isinstance(points, list) or len(points) < 2:
            raise SkillError(f"关键帧 {name} 至少需要两个点", code="VALIDATION")
        channel_types = KEYFRAME_CHANNELS[key]
        for index, property_type in enumerate(channel_types):
            channels.append(_keyframe_channel(
                property_type, points,
                value_index=index, value_count=len(channel_types)))
    # 关键帧时间相对片段起点，上界是时间线上的占用时长（target），不是源区间。
    duration_us = (segment.get("target_timerange") or {}).get("duration") or 0
    if duration_us:
        for ch in channels:
            for kf in ch["keyframe_list"]:
                if kf["time_offset"] > duration_us:
                    raise SkillError(
                        "关键帧时间超出片段时长", code="VALIDATION",
                        details={"time_offset_us": kf["time_offset"],
                                 "duration_us": duration_us})
    segment["common_keyframes"] = channels


_HSL_COLORS = {"red", "orange", "yellow", "green", "cyan", "blue", "purple",
               "magenta"}

_NATIVE_BUCKETS = {
    "adjusts", "ai_generate_holders", "ai_text_effects", "ai_translates",
    "audio_balances", "audio_effects", "audio_fades", "audio_pannings",
    "audio_pitch_shifts", "audio_track_indexes", "audios", "beats",
    "canvases", "chromas", "color_curves", "common_mask", "digital_humans",
    "effects", "filters", "green_screens", "handwrites", "hsl", "hsl_curves",
    "images", "log_color_wheels", "loudnesses", "manual_beautys",
    "manual_deformations", "material_animations", "material_colors",
    "multi_language_refs", "placeholder_infos", "placeholders", "plugin_effects",
    "primary_color_wheels", "realtime_denoises", "shapes", "smart_crops",
    "smart_relights", "sound_channel_mappings", "speeds", "stickers",
    "tail_leaders", "text_templates", "texts", "time_marks", "transitions",
    "video_effects", "video_radius", "video_shadows", "video_strokes",
    "video_trackings", "videos", "vocal_beautifys", "vocal_separations",
}


_UNWIRED_SEGMENT_FIELDS = ("adjust", "freeze")

_KNOWN_SEGMENT_KEYS = {
    "start", "duration", "source_start", "speed", "volume", "channel",
    "scale", "x", "y", "transform", "rotation", "opacity", "font_path",
    "keyframes", "path", "text", "font_size", "color", "stroke_color",
    "stroke_width", "align", "line_spacing", "letter_spacing", "animations",
    "text_template", "subtitle_template", "caption_template", "template", "text_effect", "text_glow", "flower", "text_bubble",
    "highlight",
    "bubble", "background", "shadow", "bold", "italic", "underline",
    "adjust", "freeze", "native", "crop", "flip", "reverse", "mask",
    "curve_speed", "matting", "color_wheel", "hsl", "chroma", "audio_fade",
    "fade", "audio_effect", "audio_effects", "transition", "resource_id",
    "sticker_id", "name", "value", "adjust_params", "category_id",
    "category_name", "source_platform", "combo_info", "radius", "shadow_point",
    "shape_param", "shape_fill_render_style", "request_id", "effect_id",
    "style_path", "third_resource_id", "panel", "resources", "version",
    "caption_info", "caption_duration_info", "resource_ref", "apply_target_type",
    "green_screen", "line_max_width",
}


def _warn_unknown_segment_keys(spec, *, track_index=None):
    """未知键不改变行为，但要显式提示，避免拼错字段后“绿着丢数据”。"""
    unknown = sorted(set(spec) - _KNOWN_SEGMENT_KEYS)
    if unknown:
        return (f"片段含未识别字段 {unknown}（track {track_index}）；"
                "技能不会读取这些键，若期望生效请改用已接线字段或 native。")
    return None


def _reject_unwired_segment_fields(spec, *, track_index=None, kind=None):
    """未接线字段必须在进入任何轨道分支前统一拒绝，不能按轨道类型漏掉。"""
    for field in _UNWIRED_SEGMENT_FIELDS:
        if spec.get(field) is not None:
            raise SkillError(
                f"{field} 尚未接线：native 写入口未确认，不能静默忽略；"
                "请改用 native 逃生舱（需自带真实结构）或剪映客户端。",
                code="VALIDATION",
                details={"field": field, "track": track_index, "track_type": kind},
                fix="从计划里删除该字段，或把它改成已支持的字段；不要期待它被自动忽略。",
            )


def _deep_update(target, patch, field):
    if not isinstance(patch, dict):
        raise SkillError(f"{field} 必须是对象", code="VALIDATION")
    for key, value in patch.items():
        if value is None:
            target.pop(key, None)
        elif isinstance(value, dict) and isinstance(target.get(key), dict):
            _deep_update(target[key], value, f"{field}.{key}")
        else:
            target[key] = value


def _native_extras(segment, material, spec, doc, warnings):
    """显式 native 逃生舱：只接受用户给出的原生结构，不做字段猜测。"""
    native = spec.get("native")
    if native is None:
        return
    if not isinstance(native, dict):
        raise SkillError("native 必须是对象", code="VALIDATION")
    segment_patch = native.get("segment")
    if segment_patch is not None:
        if not isinstance(segment_patch, dict):
            raise SkillError("native.segment 必须是对象", code="VALIDATION")
        for key in ("id", "material_id", "local_material_id", "extra_material_refs",
                    "render_index", "track_render_index"):
            if key in segment_patch:
                raise SkillError(
                    f"native.segment 不允许改 {key}：结构引用/轨道层级必须由技能维护",
                    code="VALIDATION", details={"field": key})
        _deep_update(segment, segment_patch, "native.segment")
    material_patch = native.get("material")
    if material_patch is not None:
        if not isinstance(material_patch, dict):
            raise SkillError("native.material 必须是对象", code="VALIDATION")
        for key in ("id", "material_id", "local_material_id"):
            if key in material_patch and material_patch[key] != material.get(key):
                raise SkillError(
                    f"native.material 不允许改 {key}：主素材引用必须由技能维护",
                    code="VALIDATION", details={"field": key})
        _deep_update(material, material_patch, "native.material")
    extras = native.get("materials") or []
    if not isinstance(extras, list):
        raise SkillError("native.materials 必须是数组", code="VALIDATION")
    known_ids = {item.get("id") for bucket in doc["materials"].values()
                 for item in bucket if isinstance(item, dict)}
    for index, item in enumerate(extras):
        if not isinstance(item, dict):
            raise SkillError(f"native.materials[{index}] 必须是对象", code="VALIDATION")
        bucket = str(item.get("bucket") or "").strip()
        if bucket not in _NATIVE_BUCKETS:
            raise SkillError(
                f"native.materials[{index}].bucket 不支持：{bucket!r}",
                code="VALIDATION", details={"supported": sorted(_NATIVE_BUCKETS)})
        value = item.get("value")
        if not isinstance(value, dict):
            raise SkillError(f"native.materials[{index}].value 必须是对象",
                             code="VALIDATION")
        value = copy.deepcopy(value)
        value.setdefault("id", uid())
        explicit_id = value.get("id")
        if not isinstance(explicit_id, str) or not explicit_id.strip():
            raise SkillError(
                f"native.materials[{index}].value.id 必须是非空字符串",
                code="VALIDATION", details={"field": "id", "value": explicit_id})
        if explicit_id in known_ids:
            raise SkillError(
                f"native.materials[{index}].value.id 与已有素材重复：{explicit_id}",
                code="VALIDATION", details={"field": "id", "value": explicit_id})
        known_ids.add(explicit_id)
        if bucket not in doc["materials"]:
            doc["materials"][bucket] = []
        doc["materials"][bucket].append(value)
        if item.get("ref", True):
            segment["extra_material_refs"].append(value["id"])
    warnings.append(
        "native 逃生舱已按调用方给出的结构写入；字段语义/像素未由技能验证，"
        "导出前必须回读草稿并抽帧确认。")


def _hsl_materials(spec, index=0):
    if isinstance(spec, dict):
        entries = [spec]
    elif isinstance(spec, list):
        entries = spec
    else:
        raise SkillError("hsl 必须是对象或对象数组", code="VALIDATION")
    materials = []
    seen = set()
    for item_index, item in enumerate(entries):
        if not isinstance(item, dict):
            raise SkillError(f"hsl[{item_index}] 必须是对象", code="VALIDATION")
        color = str(item.get("color") or item.get("hsl_color_type") or "").strip().lower()
        if color not in _HSL_COLORS:
            raise SkillError(
                f"hsl[{item_index}].color 只能是 {sorted(_HSL_COLORS)}",
                code="VALIDATION", details={"value": color})
        if color in seen:
            raise SkillError(f"hsl 颜色重复：{color}", code="VALIDATION")
        seen.add(color)
        hue = _number("hsl.hue", item.get("hue", 0), original=item.get("hue"),
                      min_value=-100.0, max_value=100.0)
        saturation = _number("hsl.saturation", item.get("saturation", 0),
                             original=item.get("saturation"),
                             min_value=-100.0, max_value=100.0)
        lightness = _number("hsl.lightness", item.get("lightness", 0),
                            original=item.get("lightness"),
                            min_value=-100.0, max_value=100.0)
        materials.append({
            "id": uid(),
            "constant_material_id": "",
            "type": "hsl",
            "hue": hue,
            "saturation": saturation,
            "lightness": lightness,
            "hsl_color_type": color,
            "interacting": False,
            "version": "1.0.0",
            "path": str(item.get("path") or ""),
            "lumi_hub_path": str(item.get("lumi_hub_path") or ""),
            "custom_color": str(item.get("custom_color") or ""),
            "resource_id": str(item.get("resource_id") or ""),
            "source_platform": int(_number(
                "source_platform", item.get("source_platform", 1),
                original=item.get("source_platform"), min_value=0)),
        })
    return materials


def _chroma_material(spec, index=0):
    if not isinstance(spec, dict):
        raise SkillError("chroma 必须是对象 {color,intensity?,shadow?,edge_smooth?,spill?}",
                         code="VALIDATION")
    color = str(spec.get("color") or "").strip()
    if not color.startswith("#") or len(color) != 9:
        raise SkillError("chroma.color 必须是 #RRGGBBAA（不透明度用 FF）",
                         code="VALIDATION", details={"value": color})
    hex_rgb(color[:7])
    params = {}
    for key in ("intensity", "shadow", "edge_smooth", "spill"):
        params[key] = _number(f"chroma.{key}", spec.get(key, 0.0),
                              original=spec.get(key), min_value=0.0,
                              max_value=100.0) / 100.0
    return {
        "id": uid(),
        "type": "chroma",
        "version": "v2",
        "color": color.upper(),
        "intensity_value": params["intensity"],
        "shadow_value": params["shadow"],
        "edge_smooth_value": params["edge_smooth"],
        "spill_value": params["spill"],
        "should_transfer_color": True,
    }


def _audio_fade_material(spec, duration_s):
    if not isinstance(spec, dict):
        raise SkillError("audio_fade 必须是对象 {in,out}", code="VALIDATION")
    fade_in = _number("audio_fade.in", spec.get("in", spec.get("fade_in", 0.0)),
                      original=spec.get("in", spec.get("fade_in")), min_value=0.0)
    fade_out = _number("audio_fade.out", spec.get("out", spec.get("fade_out", 0.0)),
                       original=spec.get("out", spec.get("fade_out")), min_value=0.0)
    if fade_in + fade_out > duration_s + 1e-9:
        raise SkillError("audio_fade 的 in+out 不能超过片段时长",
                         code="VALIDATION",
                         details={"in": fade_in, "out": fade_out,
                                  "duration": duration_s})
    if fade_in <= 0 and fade_out <= 0:
        raise SkillError("audio_fade 至少要有 in 或 out", code="VALIDATION")
    return {
        "id": uid(),
        "fade_in_duration": us(fade_in),
        "fade_out_duration": us(fade_out),
        "fade_type": 0,
        "type": "audio_fade",
    }


def _audio_effect_param_schema(path):
    if not path:
        return []
    try:
        data = json.loads(
            (media_mod.local_path(path, field="audio_effect.path")
             / "extra.json").read_text("utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return []
    items = ((data.get("setting") or {}).get("audio_effect_parameters_change")
             if isinstance(data, dict) else None)
    if not isinstance(items, list):
        return []
    result = []
    for item in items:
        if not isinstance(item, dict):
            continue
        name = str(item.get("sliderName") or "").strip()
        if not name:
            continue
        result.append({
            "name": name,
            "parameterIndex": int(_number(
                "audio_effect.parameterIndex", item.get("parameterIndex", 0),
                original=item.get("parameterIndex"), min_value=0)),
            "portIndex": int(_number(
                "audio_effect.portIndex", item.get("portIndex", 0),
                original=item.get("portIndex"), min_value=0)),
            "defaultValue": _number(
                "audio_effect.defaultValue", item.get("defaultValue", 0.0),
                original=item.get("defaultValue")),
            "minValue": _number(
                "audio_effect.minValue", item.get("minValue", 0.0),
                original=item.get("minValue")),
            "maxValue": _number(
                "audio_effect.maxValue", item.get("maxValue", 1.0),
                original=item.get("maxValue")),
        })
    return result


def _audio_effect_materials(spec, index=0):
    if isinstance(spec, dict):
        entries = [spec]
    elif isinstance(spec, list):
        entries = spec
    else:
        raise SkillError("audio_effect 必须是对象或对象数组", code="VALIDATION")
    category_names = {
        "voice-change": "变声", "tone": "音色",
        "sound_effect": "场景音", "speech_to_song": "声音成曲",
    }
    sub_types = {"voice-change": 0, "tone": 0, "sound_effect": 1, "speech_to_song": 3}
    materials = []
    for item_index, item in enumerate(entries):
        if not isinstance(item, dict):
            raise SkillError(f"audio_effect[{item_index}] 必须是对象", code="VALIDATION")
        resource_id = str(item.get("resource_id") or "").strip()
        if not resource_id:
            raise SkillError(f"audio_effect[{item_index}].resource_id 不能为空",
                             code="VALIDATION")
        category_id = str(item.get("category_id") or "voice-change").strip()
        if category_id not in category_names:
            raise SkillError(
                "audio_effect.category_id 只能是 voice-change/tone/sound_effect/"
                "speech_to_song", code="VALIDATION", details={"value": category_id})
        category_name = str(item.get("category_name") or category_names[category_id])
        params = item.get("audio_adjust_params") or item.get("params") or []
        if isinstance(params, dict):
            params = [{"name": key, "value": value} for key, value in params.items()]
        if not isinstance(params, list):
            raise SkillError("audio_effect.params 必须是对象或数组", code="VALIDATION")
        provided = {}
        for param_index, param in enumerate(params):
            if not isinstance(param, dict):
                raise SkillError(f"audio_effect.params[{param_index}] 必须是对象",
                                 code="VALIDATION")
            name = str(param.get("name") or param.get("key") or "").strip()
            if not name:
                continue
            provided[name] = param
        schema = _audio_effect_param_schema(item.get("path"))
        parsed = []
        if schema:
            for entry in schema:
                override = provided.pop(entry["name"], None)
                value = _number(
                    "audio_effect.params.value",
                    (override or {}).get("value", entry["defaultValue"]),
                    original=(override or {}).get("value"))
                parsed.append({
                    "name": entry["name"],
                    "value": value,
                    "defaultValue": _number(
                        "audio_effect.params.default_value",
                        (override or {}).get(
                            "default_value",
                            (override or {}).get("defaultValue", entry["defaultValue"])),
                        original=(override or {}).get("default_value",
                                                       (override or {}).get("defaultValue"))),
                    "parameterIndex": entry["parameterIndex"],
                    "portIndex": entry["portIndex"],
                    "minValue": entry["minValue"],
                    "maxValue": entry["maxValue"],
                })
        for param_index, param in enumerate(provided.values()):
            value = _number("audio_effect.params.value", param.get("value", 1.0),
                            original=param.get("value"))
            parsed.append({
                "name": str(param.get("name") or param.get("key") or "").strip(),
                "value": value,
                "defaultValue": value,
                "parameterIndex": int(_number(
                    "audio_effect.params.parameter_index",
                    param.get("parameter_index", len(parsed)),
                    original=param.get("parameter_index"), min_value=0)),
                "portIndex": int(_number(
                    "audio_effect.params.port_index", param.get("port_index", 0),
                    original=param.get("port_index"), min_value=0)),
                "minValue": _number(
                    "audio_effect.params.min_value", param.get("min_value", 0.0),
                    original=param.get("min_value")),
                "maxValue": _number(
                    "audio_effect.params.max_value", param.get("max_value", 1.0),
                    original=param.get("max_value")),
            })
        material = {
            "id": uid(),
            "constant_material_id": str(item.get("constant_material_id") or ""),
            "audio_adjust_params": parsed,
            "name": str(item.get("name") or ""),
            "path": str(item.get("path") or ""),
            "production_path": str(item.get("production_path") or ""),
            "resource_id": resource_id,
            "third_resource_id": str(item.get("third_resource_id") or ""),
            "source_platform": int(_number(
                "audio_effect.source_platform", item.get("source_platform", 0),
                original=item.get("source_platform"), min_value=0)),
            "category_id": category_id,
            "category_name": category_name,
            "speaker_id": str(item.get("speaker_id") or ""),
            "is_vc_clone_tone": _strict_bool(
                "audio_effect.is_vc_clone_tone", item.get("is_vc_clone_tone"), False),
            "is_ugc": _strict_bool("audio_effect.is_ugc", item.get("is_ugc"), False),
            "sub_type": int(_number(
                "audio_effect.sub_type", item.get("sub_type", sub_types[category_id]),
                original=item.get("sub_type"), min_value=0, max_value=4)),
            "type": "audio_effect",
        }
        if item.get("time_range") is not None:
            material["time_range"] = item["time_range"]
        materials.append(material)
    return materials


def _apply_video_extras(segment, material, spec, warnings, doc, *, photo=False):
    """接线已核实 native 形状的逐片段能力：crop/flip/reverse/mask/曲线/色轮/HSL/绿幕。"""
    if photo:
        for photo_unsupported in ("curve_speed", "reverse", "matting"):
            if spec.get(photo_unsupported) is not None:
                raise SkillError(
                    f"图片素材不支持 {photo_unsupported}；请改用视频轨，"
                    "或删除该字段。",
                    code="VALIDATION",
                    details={"field": photo_unsupported})
    extras = []
    crop = spec.get("crop")
    if crop is not None:
        if not isinstance(crop, dict):
            raise SkillError("crop 必须是对象 {x,y,w,h}（0..1）", code="VALIDATION")
        x = _number("crop.x", crop.get("x", 0.0), original=crop.get("x"),
                    min_value=0.0, max_value=1.0)
        y = _number("crop.y", crop.get("y", 0.0), original=crop.get("y"),
                    min_value=0.0, max_value=1.0)
        w = _number("crop.w", crop.get("w", 1.0), original=crop.get("w"),
                    positive=True, max_value=1.0)
        h = _number("crop.h", crop.get("h", 1.0), original=crop.get("h"),
                    positive=True, max_value=1.0)
        if x + w > 1.0 + 1e-9 or y + h > 1.0 + 1e-9:
            raise SkillError("crop 超出画面：x+w 与 y+h 都必须 ≤ 1",
                             code="VALIDATION",
                             details={"crop": {"x": x, "y": y, "w": w, "h": h}})
        material["crop"] = {
            "upper_left_x": x, "upper_left_y": y,
            "upper_right_x": x + w, "upper_right_y": y,
            "lower_left_x": x, "lower_left_y": y + h,
            "lower_right_x": x + w, "lower_right_y": y + h,
        }
        material["crop_ratio"] = "free"
        material["crop_scale"] = 1.0

    flip = spec.get("flip")
    if flip is not None:
        if isinstance(flip, bool):
            flip = {"horizontal": flip}
        if not isinstance(flip, dict):
            raise SkillError("flip 必须是布尔或 {horizontal,vertical}",
                             code="VALIDATION")
        segment["clip"]["flip"] = {
            "horizontal": _strict_bool("flip.horizontal",
                                       flip.get("horizontal"), False),
            "vertical": _strict_bool("flip.vertical",
                                     flip.get("vertical"), False),
        }

    if spec.get("reverse") is not None:
        if not isinstance(spec["reverse"], bool):
            raise SkillError("reverse 必须是布尔值", code="VALIDATION")
        segment["reverse"] = spec["reverse"]
        if spec["reverse"]:
            warnings.append(
                "reverse=true 已写入 segment.reverse；剪映 11.8 真实导出实测会忽略该字段，"
                "倒放像素未生效，交付时不能当作已支持。")

    if spec.get("matting") is not None:
        matting = spec["matting"]
        if not isinstance(matting, dict):
            raise SkillError("matting 必须是对象 {path,reverse?,flag?,feather?,expansion?}",
                             code="VALIDATION")
        path = str(matting.get("path") or matting.get("mask_video_path") or "").strip()
        if not path:
            raise SkillError(
                "matting.path 不能为空：抠像需要剪映生成的逐帧蒙版目录，外部不能凭空生成",
                code="VALIDATION")
        if not media_mod.local_path(path, field="matting.path").is_dir():
            raise SkillError(
                "matting.path 必须是已存在的逐帧蒙版目录",
                code="VALIDATION", details={"path": path})
        shape = material.setdefault("matting", {})
        shape["path"] = path
        shape["mask_video_path"] = path
        shape["reverse"] = _strict_bool("matting.reverse",
                                        matting.get("reverse"), False)
        shape["flag"] = int(_number("matting.flag", matting.get("flag", 0),
                                   original=matting.get("flag"), min_value=0))
        shape["feather"] = _number("matting.feather", matting.get("feather", 0),
                                   original=matting.get("feather"), min_value=0)
        shape["expansion"] = _number("matting.expansion", matting.get("expansion", 0),
                                     original=matting.get("expansion"))
        warnings.append(
            "matting 已写入视频材质；mask_video_path 必须是剪映生成的逐帧蒙版目录，"
            "外部不能凭 id 生成。")

    if spec.get("mask") is not None:
        mask = spec["mask"]
        if not isinstance(mask, dict):
            raise SkillError("mask 必须是对象 {resource_type,name,resource_id,path,config}",
                             code="VALIDATION")
        resource_type = str(mask.get("resource_type") or "").strip()
        if not resource_type:
            raise SkillError("mask.resource_type 不能为空（线性=line / 圆形=circle …）",
                             code="VALIDATION")
        resource_id = str(mask.get("resource_id") or "").strip()
        if resource_id and not resource_id.isdigit():
            raise SkillError("mask.resource_id 必须是十进制资源 ID", code="VALIDATION")
        config = mask.get("config") or {}
        if not isinstance(config, dict):
            raise SkillError("mask.config 必须是对象", code="VALIDATION")
        clean_config = dict(config)
        allowed_keys = {"center_x", "center_y", "width", "height", "feather", "invert"}
        unknown = [key for key in config if key not in allowed_keys]
        for key in unknown:
            clean_config.pop(key, None)
        if not config:
            warnings.append(
                "mask.config 为空：11.8 会把蒙版尺寸当成 0，整段画面可能被遮成黑屏；"
                "至少显式给 center_x/center_y/width/height/feather。")
        else:
            required = ("center_x", "center_y", "width", "height")
            missing = [key for key in required if key not in config]
            bad_values = []
            for key in ("center_x", "center_y"):
                if key not in config:
                    continue
                value = config[key]
                if isinstance(value, bool) or not isinstance(value, (int, float)):
                    bad_values.append(key)
                    continue
                number = float(value)
                if not math.isfinite(number) or number < 0 or number > 1:
                    bad_values.append(key)
            for key in ("width", "height"):
                if key not in config:
                    continue
                value = config[key]
                if isinstance(value, bool) or not isinstance(value, (int, float)):
                    bad_values.append(key)
                    continue
                number = float(value)
                if not math.isfinite(number) or number <= 0 or number > 1:
                    bad_values.append(key)
            if "feather" in config:
                value = config["feather"]
                if isinstance(value, bool) or not isinstance(value, (int, float)):
                    bad_values.append("feather")
                else:
                    number = float(value)
                    if not math.isfinite(number) or number < 0 or number > 1:
                        bad_values.append("feather")
            if missing or bad_values or unknown:
                for key in bad_values:
                    clean_config.pop(key, None)
                warnings.append(
                    "mask.config 字段不全、含未知键或取值非法（相关键已移除）："
                    f"missing={missing}, bad={bad_values}, unknown={unknown}；"
                    "缺尺寸/中心值可能导致蒙版只显示一角或整段全黑。")
        mask_id = uid()
        segment["extra_material_refs"].append(mask_id)
        extras.append({
            "kind": "mask",
            "id": mask_id,
            "material": {
                "id": mask_id,
                "type": "mask",
                "category": str(mask.get("category") or "video"),
                "category_name": str(mask.get("category_name") or "基础"),
                "category_id": str(mask.get("category_id") or "jichu"),
                "resource_id": resource_id,
                "constant_material_id": "",
                "name": str(mask.get("name") or resource_type),
                "resource_type": resource_type,
                "path": str(mask.get("path") or ""),
                "config": clean_config,
                "text_config": {"align_type": 15},
            },
        })

    if spec.get("curve_speed") is not None:
        curve = spec["curve_speed"]
        if not isinstance(curve, dict):
            raise SkillError("curve_speed 必须是对象 {points:[{x,y}…], name?, preset_id?}",
                             code="VALIDATION")
        points = curve.get("points") or curve.get("speed_points") or []
        if not isinstance(points, list) or len(points) < 2:
            raise SkillError("curve_speed.points 至少需要两个点", code="VALIDATION")
        parsed = []
        last_x = -1.0
        for index, point in enumerate(points):
            if isinstance(point, dict):
                raw_x, raw_y = point.get("x"), point.get("y")
            elif isinstance(point, (list, tuple)) and len(point) >= 2:
                raw_x, raw_y = point[0], point[1]
            else:
                raise SkillError(f"curve_speed.points[{index}] 必须是 {x, y}",
                                 code="VALIDATION")
            px = _number(f"curve_speed.points[{index}].x", raw_x, original=raw_x,
                         min_value=0.0, max_value=1.0)
            py = _number(f"curve_speed.points[{index}].y", raw_y, original=raw_y,
                         positive=True)
            if px < last_x:
                raise SkillError("curve_speed.points 的 x 必须单调不减",
                                 code="VALIDATION",
                                 details={"index": index, "x": px, "previous": last_x})
            last_x = px
            parsed.append({"x": round(px, 4), "y": round(py, 4)})
        speed_id = uid()
        avg = round(sum(point["y"] for point in parsed) / len(parsed), 4)
        segment["extra_material_refs"].append(speed_id)
        extras.append({
            "kind": "curve_speed",
            "id": speed_id,
            "material": {
                "id": speed_id,
                "type": "speed",
                "mode": 1,
                "speed": avg,
                "curve_speed": {
                    "id": str(curve.get("preset_id") or uid()),
                    "name": str(curve.get("name") or ""),
                    "speed_points": parsed,
                },
            },
        })
        warnings.append(
            "curve_speed 只写入 materials.speeds；target/source 时长仍按线性 speed 计算，"
            "曲线时间轴换算未验证。")
    wheel = spec.get("color_wheel")
    if wheel is not None:
        if isinstance(wheel, dict):
            wheels = [wheel]
        elif isinstance(wheel, list):
            wheels = wheel
        else:
            raise SkillError("color_wheel 必须是对象或对象数组", code="VALIDATION")
        entries = []
        for index, item in enumerate(wheels):
            if not isinstance(item, dict):
                raise SkillError(f"color_wheel[{index}] 必须是对象", code="VALIDATION")
            segment_name = str(item.get("segment") or "").strip()
            if segment_name not in {"gamma", "lift", "gain", "offset"}:
                raise SkillError(
                    "color_wheel.segment 只能是 gamma / lift / gain / offset",
                    code="VALIDATION", details={"value": segment_name})
            red = _number("color_wheel.red", item.get("red", 0.0),
                          original=item.get("red"))
            green = _number("color_wheel.green", item.get("green", 0.0),
                            original=item.get("green"))
            blue = _number("color_wheel.blue", item.get("blue", 0.0),
                           original=item.get("blue"))
            wheel_id, hsl_id = uid(), uid()
            enable_hsl = _strict_bool("color_wheel.hsl", item.get("hsl"), True)
            wheel_material = {
                "id": wheel_id,
                "type": "primary_color_wheel",
                "segment": segment_name,
                "red": red, "green": green, "blue": blue,
                "resource_id": str(item.get("resource_id") or ""),
                "path": str(item.get("path") or ""),
                "name": str(item.get("name") or segment_name),
                "enable_hsl": enable_hsl,
                "constant_material_id": hsl_id if enable_hsl else "",
            }
            segment["extra_material_refs"].append(wheel_id)
            entries.append(wheel_material)
            if enable_hsl:
                segment["extra_material_refs"].append(hsl_id)
                entries.append({
                    "id": hsl_id,
                    "type": "hsl",
                    "segment": segment_name,
                    "red": red, "green": green, "blue": blue,
                    "resource_id": str(item.get("resource_id") or ""),
                    "path": str(item.get("path") or ""),
                    "constant_material_id": wheel_id,
                    "enable_hsl": True,
                })
        extras.append({"kind": "color_wheel", "materials": entries})

    hsl_spec = spec.get("hsl")
    if hsl_spec is not None:
        hsl_materials = _hsl_materials(hsl_spec)
        for item in hsl_materials:
            segment["extra_material_refs"].append(item["id"])
            extras.append({"kind": "hsl", "material": item})
        segment["enable_hsl"] = True
        warnings.append(
            "hsl 已写入 materials.hsl（官方 11.8 白名单形状）；"
            "颜色通道像素未单独验收。")

    chroma_spec = spec.get("chroma") or spec.get("green_screen")
    if chroma_spec is not None:
        chroma_material = _chroma_material(chroma_spec)
        segment["extra_material_refs"].append(chroma_material["id"])
        extras.append({"kind": "chroma", "material": chroma_material})
        warnings.append(
            "chroma 已写入 materials.chromas；色度抠图像素与边缘参数未单独验收。")

    _native_extras(segment, material, spec, doc, warnings)
    return extras or None


def _validate_caption_info(value, field="caption_info"):
    if not isinstance(value, dict):
        raise SkillError(f"{field} 必须是对象", code="VALIDATION",
                         details={"field": field})
    if not isinstance(value.get("original_text", ""), str):
        raise SkillError(f"{field}.original_text 必须是字符串", code="VALIDATION",
                         details={"field": f"{field}.original_text"})
    words = value.get("words")
    if words is None:
        return
    if not isinstance(words, list):
        raise SkillError(f"{field}.words 必须是数组", code="VALIDATION",
                         details={"field": f"{field}.words"})
    for index, word in enumerate(words):
        if not isinstance(word, dict):
            raise SkillError(f"{field}.words[{index}] 必须是对象", code="VALIDATION",
                             details={"field": f"{field}.words[{index}]"})
        window = word.get("time_range")
        if window is None:
            continue
        if not isinstance(window, dict):
            raise SkillError(f"{field}.words[{index}].time_range 必须是对象",
                             code="VALIDATION",
                             details={"field": f"{field}.words[{index}].time_range"})
        start = _number(f"{field}.words[{index}].time_range.start",
                        window.get("start", 0), min_value=0.0)
        duration = _number(f"{field}.words[{index}].time_range.duration",
                           window.get("duration", 0), min_value=0.0)
        if not math.isfinite(start) or not math.isfinite(duration):
            raise SkillError(f"{field}.words[{index}].time_range 必须是有限数",
                             code="VALIDATION",
                             details={"field": f"{field}.words[{index}].time_range"})


def _caption_duration_info(spec):
    direct = spec.get("caption_duration_info")
    if isinstance(direct, dict) and direct:
        return direct
    info = spec.get("caption_info")
    if not isinstance(info, dict) or not info:
        return None
    words = []
    for word in info.get("words") or []:
        if not isinstance(word, dict):
            continue
        window = word.get("time_range") or {}
        start_ms = int(window.get("start", 0)) / 1000.0
        end_ms = start_ms + int(window.get("duration", 0)) / 1000.0
        words.append({
            "text": str(word.get("text") or ""),
            "start_time": int(round(start_ms)),
            "end_time": int(round(end_ms)),
            "is_key": bool(word.get("is_key")),
            "new_page": bool(word.get("new_page")),
        })
    if not words:
        return None
    text = str(info.get("original_text") or "")
    if not text:
        text = "".join(word["text"] for word in words)
    return {
        "text": text,
        "start_time": min(word["start_time"] for word in words),
        "end_time": max(word["end_time"] for word in words),
        "words": words,
    }


def _apply_text_extras(segment, text_material, spec, doc, warnings):
    """接线文字模板、动画、花字、气泡与 native 逃生舱。"""
    extras = []
    template = spec.get("text_template") or spec.get("template")
    template_type = "text_template"
    if template is not None:
        if not isinstance(template, dict):
            raise SkillError("text_template 必须是对象 {resource_id,name,path,resources}",
                             code="VALIDATION")
        resource_id = str(template.get("resource_id") or "").strip()
        if not resource_id:
            raise SkillError("text_template.resource_id 不能为空", code="VALIDATION")
        resources = template.get("resources") or []
        if not isinstance(resources, list):
            raise SkillError("text_template.resources 必须是数组", code="VALIDATION")
        parsed_resources = []
        for index, item in enumerate(resources):
            if not isinstance(item, dict):
                raise SkillError(f"text_template.resources[{index}] 必须是对象",
                                 code="VALIDATION")
            panel = str(item.get("panel") or "default").strip()
            if panel not in {"default", "sticker", "fonts", "text"}:
                raise SkillError(
                    "text_template.resources[].panel 只能是 default/sticker/fonts/text",
                    code="VALIDATION", details={"value": panel})
            parsed_resources.append({
                "panel": panel,
                "path": str(item.get("path") or ""),
                "resource_id": str(item.get("resource_id") or ""),
                "source_platform": int(_number(
                    "source_platform", item.get("source_platform", 1),
                    original=item.get("source_platform"), min_value=0)),
            })
        template_id = uid()
        text_template_material = {
            "id": template_id,
            "version": str(template.get("version") or "1.0.0"),
            "effect_id": str(template.get("effect_id") or resource_id),
            "resource_id": resource_id,
            "name": str(template.get("name") or ""),
            "type": template_type,
            "path": str(template.get("path") or ""),
            "category_id": str(template.get("category_id") or ""),
            "category_name": str(template.get("category_name") or ""),
            "source_platform": 1,
            "resources": parsed_resources,
            "text_info_resources": [],
            "non_text_info_resources": [],
            "aigc_config": {},
            "origin_word_info": {},
            "current_word_info": {},
            "preview_time": 0,
            "ai_generate_task_info": {},
        }
        request_id = template.get("request_id")
        if request_id:
            text_template_material["request_id"] = str(request_id)
        caption_info = _caption_duration_info(spec)
        template_path = str(template.get("path") or "")
        if caption_info and template_path:
            content_path = (media_mod.local_path(
                template_path, field="text_template.path") / "content.json")
            try:
                content = json.loads(content_path.read_text("utf-8-sig"))
            except (OSError, json.JSONDecodeError):
                content = None
            if isinstance(content, dict):
                for child in content.get("children") or []:
                    if isinstance(child, dict) and isinstance(child.get("text_params"), dict):
                        child["text_params"]["caption_duration_info"] = caption_info
                        break
                text_template_material["content"] = json.dumps(
                    content, ensure_ascii=False, separators=(",", ":"))
            else:
                warnings.append("text_template 的 content.json 读不了，caption_info 未注入")
        # 剪映的文字模板会 fork 片段：material_id 指向模板，文字材质进 refs。
        segment["material_id"] = template_id
        segment["render_index"] = 14001
        segment["extra_material_refs"].append(text_material["id"])
        extras.append({"kind": "text_template", "material": text_template_material})

    effect_spec = spec.get("text_effect") or spec.get("flower")
    if effect_spec is not None:
        if not isinstance(effect_spec, dict):
            raise SkillError("text_effect 必须是对象 {resource_id,effect_id?,path?}",
                             code="VALIDATION")
        resource_id = str(effect_spec.get("resource_id") or "").strip()
        if not resource_id:
            raise SkillError("text_effect.resource_id 不能为空", code="VALIDATION")
        effect_id = str(effect_spec.get("effect_id") or resource_id)
        effect_material = {
            "apply_target_type": 0,
            "effect_id": effect_id,
            "id": uid(),
            "resource_id": resource_id,
            "type": "text_effect",
            "value": _number("text_effect.value", effect_spec.get("value", 1.0),
                             original=effect_spec.get("value")),
            "source_platform": int(_number(
                "text_effect.source_platform", effect_spec.get("source_platform", 1),
                original=effect_spec.get("source_platform"), min_value=0)),
            "path": str(effect_spec.get("path") or ""),
        }
        try:
            content = json.loads(text_material.get("content") or "{}")
        except json.JSONDecodeError:
            content = {}
        styles = content.get("styles") or [{}]
        styles[0]["effectStyle"] = {
            "id": effect_id,
            "path": str(effect_spec.get("style_path")
                        or effect_spec.get("path") or ""),
        }
        encoded = json.dumps(content, ensure_ascii=False, separators=(",", ":"))
        text_material["content"] = encoded
        text_material["base_content"] = encoded
        segment["extra_material_refs"].append(effect_material["id"])
        extras.append({"kind": "text_effect", "bucket": "filters",
                       "material": effect_material})
        warnings.append(
            "text_effect 已写入 materials.filters[type=text_effect] 与文字 effectStyle；"
            "花字资源必须已缓存，像素未验收。")

    glow_spec = spec.get("text_glow")
    if glow_spec is not None:
        if not isinstance(glow_spec, dict):
            raise SkillError("text_glow 必须是对象 {resource_id,effect_id?,path?}",
                             code="VALIDATION")
        resource_id = str(glow_spec.get("resource_id") or "").strip()
        if not resource_id:
            raise SkillError("text_glow.resource_id 不能为空", code="VALIDATION")
        effect_id = str(glow_spec.get("effect_id") or resource_id)
        glow_material = {
            "apply_target_type": 0,
            "effect_id": effect_id,
            "id": uid(),
            "resource_id": resource_id,
            "type": "text_glow",
            "value": _number("text_glow.value", glow_spec.get("value", 1.0),
                             original=glow_spec.get("value")),
            "source_platform": int(_number(
                "text_glow.source_platform", glow_spec.get("source_platform", 1),
                original=glow_spec.get("source_platform"), min_value=0)),
            "path": str(glow_spec.get("path") or ""),
        }
        try:
            content = json.loads(text_material.get("content") or "{}")
        except json.JSONDecodeError:
            content = {}
        styles = content.get("styles") or [{}]
        styles[0]["effectStyle"] = {
            "id": effect_id,
            "path": str(glow_spec.get("path") or ""),
        }
        encoded = json.dumps(content, ensure_ascii=False, separators=(",", ":"))
        text_material["content"] = encoded
        text_material["base_content"] = encoded
        segment["extra_material_refs"].append(glow_material["id"])
        extras.append({"kind": "text_glow", "bucket": "filters",
                       "material": glow_material})
        warnings.append(
            "text_glow 已写入 materials.filters[type=text_glow] 与文字 effectStyle；"
            "光效资源必须已缓存，像素未验收。")

    bubble_spec = spec.get("text_bubble") or spec.get("bubble")
    if bubble_spec is not None:
        if not isinstance(bubble_spec, dict):
            raise SkillError("text_bubble 必须是对象 {resource_id,effect_id?,path?}",
                             code="VALIDATION")
        resource_id = str(bubble_spec.get("resource_id") or "").strip()
        if not resource_id:
            raise SkillError("text_bubble.resource_id 不能为空", code="VALIDATION")
        bubble_material = {
            "apply_target_type": 0,
            "effect_id": str(bubble_spec.get("effect_id") or resource_id),
            "id": uid(),
            "resource_id": resource_id,
            "type": "text_shape",
            "value": _number("text_bubble.value", bubble_spec.get("value", 1.0),
                             original=bubble_spec.get("value")),
            "path": str(bubble_spec.get("path") or ""),
        }
        segment["extra_material_refs"].append(bubble_material["id"])
        extras.append({"kind": "text_bubble", "bucket": "filters",
                       "material": bubble_material})
        warnings.append(
            "text_bubble 已写入 materials.filters[type=text_shape]；"
            "气泡资源必须已缓存，像素未验收。")

    animations = spec.get("animations")
    if animations is not None:
        if not isinstance(animations, list) or not animations:
            raise SkillError("animations 必须是非空数组", code="VALIDATION")
        slot_id = uid()
        entries = []
        for index, item in enumerate(animations):
            if not isinstance(item, dict):
                raise SkillError(f"animations[{index}] 必须是对象", code="VALIDATION")
            kind = str(item.get("type") or "").strip().lower()
            if kind not in {"in", "out", "loop"}:
                raise SkillError(
                    "animations[].type 只能是 in / out / loop",
                    code="VALIDATION", details={"index": index, "value": kind})
            resource_id = str(item.get("resource_id") or "").strip()
            if not resource_id:
                raise SkillError(f"animations[{index}].resource_id 不能为空",
                                 code="VALIDATION")
            duration = _number(
                f"animations[{index}].duration", item.get("duration", 0.5),
                original=item.get("duration"), positive=True)
            entry = {
                "id": resource_id,
                "type": kind,
                "duration": us(duration),
                "path": str(item.get("path") or ""),
                "resource_id": resource_id,
                "third_resource_id": "0",
                "source_platform": int(_number(
                    "source_platform", item.get("source_platform", 1),
                    original=item.get("source_platform"), min_value=0)),
                "name": str(item.get("name") or ""),
                "category_id": str(item.get("category_id") or ""),
                "category_name": str(item.get("category_name") or ""),
                "material_type": "sticker",
            }
            if item.get("request_id"):
                entry["request_id"] = str(item["request_id"])
            entries.append(entry)
        slot = {"id": slot_id, "type": "sticker_animation",
                "animations": entries, "multi_language_current": "none"}
        segment["extra_material_refs"].append(slot_id)
        extras.append({"kind": "text_animations", "material": slot})
    _native_extras(segment, text_material, spec, doc, warnings)
    return extras or None


def _sticker_material(spec, index):
    resource_id = str(spec.get("resource_id") or "").strip()
    if not resource_id:
        raise SkillError(f"stickers[{index}].resource_id 不能为空",
                         code="VALIDATION")
    return {
        "id": uid(),
        "type": "sticker",
        "path": str(spec.get("path") or ""),
        "sticker_id": str(spec.get("sticker_id") or resource_id),
        "resource_id": resource_id,
        "category_id": str(spec.get("category_id") or "none"),
        "category_name": str(spec.get("category_name") or "none"),
        "source_platform": int(_number(
            "source_platform", spec.get("source_platform", 6),
            original=spec.get("source_platform"), min_value=0)),
        "combo_info": {},
        "radius": {},
        "shadow_point": {"x": 0.0, "y": 0.0},
        "shape_param": {},
        "shape_fill_render_style": {
            "color": {"solid": {}, "gradient": {},
                      "texture": {"path": "", "resource_id": ""}}
        },
    }


def _sticker_segment(material_id, start, duration, spec):
    scale = _number("scale", spec.get("scale", 0.26), original=spec.get("scale"),
                    positive=True)
    x = _number("x", spec.get("x", 0.0), original=spec.get("x"))
    y = _number("y", spec.get("y", 0.0), original=spec.get("y"))
    segment = _segment(material_id, start, duration, render_index=14000)
    segment["clip"].update({
        "scale": {"x": scale, "y": scale},
        "transform": {"x": x, "y": y},
        "flip": {"horizontal": False, "vertical": False},
    })
    segment["uniform_scale"] = {"on": True, "value": scale}
    segment["enable_adjust"] = False
    segment["enable_adjust_mask"] = False
    return segment


def _effect_material(spec, index):
    resource_id = str(spec.get("resource_id") or "").strip()
    if not resource_id:
        raise SkillError(f"effects[{index}].resource_id 不能为空", code="VALIDATION")
    adjust_params = spec.get("adjust_params") or []
    if isinstance(adjust_params, dict):
        adjust_params = [{"name": key, "value": value}
                         for key, value in adjust_params.items()]
    if not isinstance(adjust_params, list):
        raise SkillError("effects[].adjust_params 必须是对象或数组", code="VALIDATION")
    params = []
    for item in adjust_params:
        if not isinstance(item, dict):
            raise SkillError("effects[].adjust_params[] 必须是对象", code="VALIDATION")
        name = str(item.get("name") or item.get("key") or "").strip()
        if not name:
            continue
        value = _number("adjust_params.value", item.get("value", 1.0),
                        original=item.get("value"))
        default = _number("adjust_params.default_value",
                          item.get("default_value", value),
                          original=item.get("default_value"))
        params.append({"name": name, "value": value, "default_value": default})
    return {
        "id": uid(),
        "effect_id": resource_id,
        "resource_id": resource_id,
        "name": str(spec.get("name") or ""),
        "type": "video_effect",
        "path": str(spec.get("path") or ""),
        "value": _number("value", spec.get("value", 1.0),
                         original=spec.get("value")),
        "category_id": str(spec.get("category_id") or ""),
        "category_name": str(spec.get("category_name") or "热门"),
        "apply_target_type": int(_number(
            "apply_target_type", spec.get("apply_target_type", 2),
            original=spec.get("apply_target_type"), min_value=0, max_value=3)),
        "source_platform": int(_number(
            "source_platform", spec.get("source_platform", 1),
            original=spec.get("source_platform"), min_value=0)),
        "adjust_params": params,
    }


def _effect_segment(material_id, start, duration):
    segment = _segment(material_id, start, duration, render_index=11000)
    segment["enable_adjust"] = False
    segment["enable_adjust_mask"] = False
    segment["clip"] = {
        "alpha": 1.0,
        "flip": {"horizontal": False, "vertical": False},
        "rotation": 0.0,
        "scale": {"x": 1.0, "y": 1.0},
        "transform": {"x": 0.0, "y": 0.0},
    }
    return segment


def _apply_audio_extras(segment, spec, doc, duration_s, warnings,
                        primary_material=None, apply_native=True):
    changed = False
    channel = spec.get("channel")
    if channel is not None:
        if isinstance(channel, dict):
            channel = channel.get("mapping", channel.get("audio_channel_mapping"))
        mapping = int(_number("channel", channel, original=channel, min_value=0,
                             max_value=2))
        material_id = uid()
        segment["extra_material_refs"].append(material_id)
        channel_config = {
            "id": material_id,
            "type": "sound_channel_mapping",
            "audio_channel_mapping": mapping,
            "is_config_open": True,
        }
        segment["sound_channel_mapping"] = {"id": material_id}
        doc["materials"]["sound_channel_mappings"].append(channel_config)
        changed = True
        warnings.append(
            "channel 已写入 materials.sound_channel_mappings："
            "0 保持原声道，1 左声道复制到双声道，2 右声道复制到双声道。")

    fade_spec = spec.get("audio_fade") or spec.get("fade")
    if fade_spec is not None:
        fade = _audio_fade_material(fade_spec, duration_s)
        segment["extra_material_refs"].append(fade["id"])
        doc["materials"]["audio_fades"].append(fade)
        changed = True
        warnings.append(
            "audio_fade 已写入 materials.audio_fades（微秒）；"
            "独立音频轨的真实导出波形已验证；视频原声淡入淡出未验证。")

    effect_spec = spec.get("audio_effect") or spec.get("audio_effects")
    if effect_spec is not None:
        effects = _audio_effect_materials(effect_spec)
        for effect in effects:
            segment["extra_material_refs"].append(effect["id"])
            doc["materials"]["audio_effects"].append(effect)
        changed = True
        warnings.append(
            "audio_effect 已写入 materials.audio_effects（含 path/sub_type/参数索引）；"
            "2026-11-16 免费“萝莉”VC 实测 440Hz→740Hz；其他资源仍需听感验收。")

    if apply_native:
        _native_extras(segment, primary_material or {}, spec, doc, warnings)
    return changed


def _alignment(value):
    mapping = {"left": 0, "center": 1, "right": 2}
    key = str(value if value is not None else "center").strip().lower()
    if key not in mapping:
        raise SkillError("align 只能是 left / center / right",
                         code="VALIDATION",
                         details={"field": "align", "value": value,
                                  "supported": sorted(mapping)})
    return mapping[key]


def _caption_template_ref(spec):
    for key in ("caption_template", "subtitle_template"):
        template = spec.get(key)
        if not isinstance(template, dict):
            continue
        resource_id = str(template.get("resource_id") or "").strip()
        if not resource_id:
            continue
        return {
            "resource_id": resource_id,
            "path": str(template.get("path") or ""),
            "source_platform": int(_number(
                "source_platform", template.get("source_platform", 1),
                original=template.get("source_platform"), min_value=0)),
            "resource_name": str(template.get("name") or ""),
        }
    return None


def _apply_highlight_styles(content, text, spec):
    highlight = spec.get("highlight")
    if highlight is None:
        return
    if isinstance(highlight, list):
        highlight = {"words": highlight}
    if not isinstance(highlight, dict):
        raise SkillError("highlight 必须是对象或字符串数组", code="VALIDATION")
    words = highlight.get("words") or []
    if not isinstance(words, list):
        raise SkillError("highlight.words 必须是数组", code="VALIDATION")
    color = str(highlight.get("color") or "#FFD400")
    bold = _strict_bool("highlight.bold", highlight.get("bold"), False)
    for word in words:
        word = str(word or "")
        if not word:
            continue
        start = 0
        while True:
            index = text.find(word, start)
            if index < 0:
                break
            begin = len(text[:index].encode("utf-16-le")) // 2
            finish = begin + len(word.encode("utf-16-le")) // 2
            style = copy.deepcopy(content["styles"][0])
            style["range"] = [begin, finish]
            style["fill"] = {
                "alpha": 1.0,
                "content": {"render_type": "solid",
                            "solid": {"alpha": 1.0, "color": hex_rgb(color)}},
            }
            if bold:
                style["bold"] = True
            content["styles"].append(style)
            start = index + len(word)


def _text_material(text, spec, template):
    material = copy.deepcopy(template)
    length = len(text.encode("utf-16-le")) // 2
    size = _number("font_size", spec.get("font_size", 14.0), positive=True)
    color = spec.get("color", "#FFFFFF")
    stroke_color = spec.get("stroke_color", "#000000")
    stroke_width = _number("stroke_width", spec.get("stroke_width", 0.0), min_value=0.0)
    style = {
        "fill": {
            "alpha": 1.0,
            "content": {"render_type": "solid",
                        "solid": {"alpha": 1.0, "color": hex_rgb(color)}},
        },
        "font": {"id": "", "path": str(spec.get("font_path") or "")},
        "range": [0, length],
        "size": size,
        "bold": _strict_bool("bold", spec.get("bold"), False),
        "italic": _strict_bool("italic", spec.get("italic"), False),
        "underline": _strict_bool("underline", spec.get("underline"), False),
        "useLetterColor": True,
        "strokes": [],
    }
    if stroke_width > 0:
        style["strokes"].append({
            "alpha": 1.0,
            "content": {"render_type": "solid",
                        "solid": {"alpha": 1.0, "color": hex_rgb(stroke_color)}},
            "width": stroke_width,
        })
    background = spec.get("background")
    if isinstance(background, str):
        background = {"color": background}
    if background is not None:
        if not isinstance(background, dict):
            raise SkillError("background 必须是颜色字符串或对象", code="VALIDATION")
        bg_color = str(background.get("color") or "#000000")
        bg_style = int(_number("background.style", background.get("style", 1),
                               original=background.get("style"), min_value=1,
                               max_value=2))
        bg_alpha = _number("background.alpha", background.get("alpha", 1.0),
                           original=background.get("alpha"), min_value=0.0,
                           max_value=1.0)
        bg_radius = _number("background.round_radius",
                            background.get("round_radius", 0.0),
                            original=background.get("round_radius"),
                            min_value=0.0, max_value=1.0)
        bg_height = _number("background.height", background.get("height", 0.14),
                            original=background.get("height"), min_value=0.0,
                            max_value=1.0)
        bg_width = _number("background.width", background.get("width", 0.14),
                           original=background.get("width"), min_value=0.0,
                           max_value=1.0)
        bg_x = _number("background.horizontal_offset",
                       background.get("horizontal_offset", 0.5),
                       original=background.get("horizontal_offset"),
                       min_value=0.0, max_value=1.0)
        bg_y = _number("background.vertical_offset",
                       background.get("vertical_offset", 0.5),
                       original=background.get("vertical_offset"),
                       min_value=0.0, max_value=1.0)
        background_shape = {
            "background_style": bg_style,
            "background_color": bg_color,
            "background_alpha": bg_alpha,
            "background_round_radius": bg_radius,
            "background_height": bg_height,
            "background_width": bg_width,
            "background_horizontal_offset": bg_x * 2 - 1,
            "background_vertical_offset": bg_y * 2 - 1,
        }
    else:
        background_shape = None
    shadow = spec.get("shadow")
    if shadow is not None:
        if not isinstance(shadow, dict):
            raise SkillError("shadow 必须是对象 {color?,alpha?,distance?,diffuse?,angle?}",
                             code="VALIDATION")
        sh_color = str(shadow.get("color") or "#000000")
        sh_alpha = _number("shadow.alpha", shadow.get("alpha", 1.0),
                           original=shadow.get("alpha"), min_value=0.0,
                           max_value=1.0)
        sh_distance = _number("shadow.distance", shadow.get("distance", 5.0),
                              original=shadow.get("distance"), min_value=0.0)
        sh_diffuse = _number("shadow.diffuse", shadow.get("diffuse", 15.0),
                             original=shadow.get("diffuse"), min_value=0.0,
                             max_value=100.0)
        sh_angle = _number("shadow.angle", shadow.get("angle", -45.0),
                           original=shadow.get("angle"), min_value=-180.0,
                           max_value=180.0)
        shadow_shape = {
            "diffuse": sh_diffuse / 100.0 / 6.0,
            "alpha": sh_alpha,
            "distance": sh_distance,
            "content": {"solid": {"color": hex_rgb(sh_color)}},
            "angle": sh_angle,
        }
        style["shadows"] = [shadow_shape]
    else:
        shadow_shape = None
    content = {"styles": [style], "text": text}
    _apply_highlight_styles(content, text, spec)
    encoded = json.dumps(content, ensure_ascii=False, separators=(",", ":"))
    material.update({
        "id": uid(),
        "type": "text",
        "content": encoded,
        "base_content": encoded,
        "text_color": color,
        "font_size": size,
        "border_color": stroke_color,
        "border_width": stroke_width,
        "border_mode": 0,
        "border_alpha": 1.0,
        "font_path": str(spec.get("font_path") or ""),
        "font_name": "",
        "font_id": "",
        "alignment": _alignment(spec.get("align", "center")),
        "line_spacing": _number("line_spacing", spec.get("line_spacing", 0.02),
                               min_value=0.0),
        "letter_spacing": _number("letter_spacing", spec.get("letter_spacing", 0.0)),
        "bold_width": 0.1 if _strict_bool("bold", spec.get("bold"), False) else 0.0,
        "italic_degree": 1 if _strict_bool("italic", spec.get("italic"), False) else 0,
        "underline": _strict_bool("underline", spec.get("underline"), False),
        "line_max_width": _number("line_max_width", spec.get("line_max_width", 0.82),
                                  positive=True),
        "recognize_task_id": "",
        "recognize_text": "",
        "text_size": 30,
        "use_effect_default_color": False,
    })
    caption_template = _caption_template_ref(spec)
    if caption_template:
        material["caption_template_info"] = caption_template
        material["recognize_text"] = text
    if background_shape:
        material.update(background_shape)
        material["check_flag"] = 7 | (8 if stroke_width > 0 else 0) | 16
    if shadow_shape:
        material.update({
            "has_shadow": True,
            "shadow_alpha": shadow_shape["alpha"],
            "shadow_color": str(shadow.get("color") or "#000000"),
            "shadow_distance": shadow_shape["distance"],
            "shadow_smoothing": shadow_shape["diffuse"],
            "shadow_angle": shadow_shape["angle"],
            "shadow_point": {"x": 0.6363961030678928, "y": -0.6363961030678927},
        })
        material["check_flag"] = (material.get("check_flag") or 7) | 32
    if stroke_width > 0 or background_shape or shadow_shape:
        material["check_flag"] = ((material.get("check_flag") or 0)
                                  | (8 if stroke_width > 0 else 0))
    return material


def _video_material(probe, template, *, photo=False, duration_s=None):
    material = copy.deepcopy(template)
    duration = duration_s if duration_s is not None else (probe["duration"] or 0)
    kind = "photo" if photo else "video"
    material.update({
        "id": uid(),
        "type": kind,
        "path": probe["path"],
        "material_name": probe["name"],
        "duration": us(duration),
        "width": int(probe["width"]),
        "height": int(probe["height"]),
        "has_audio": bool(probe["has_audio"]) and not photo,
        "crop_source_size": {"width": int(probe["width"]), "height": int(probe["height"])},
        "crop_img_size": {"width": int(probe["width"]), "height": int(probe["height"])},
        "crop_timerange": {"start": 0, "duration": us(duration)},
        "material_id": "",
        "local_material_id": "",
        "category_name": "local",
    })
    return material


def _audio_material(probe, template, duration_s):
    material = copy.deepcopy(template)
    material.update({
        "id": uid(),
        "type": "extract_music",
        "name": probe["name"],
        "duration": us(duration_s),
        "path": probe["path"],
        "category_name": "local",
        "music_id": "",
        "resource_id": "",
        "local_material_id": "",
    })
    return material


def _check_track(track, index):
    if not isinstance(track, dict):
        raise SkillError(f"tracks[{index}] 必须是对象", code="VALIDATION")
    kind = str(track.get("type") or "").strip().lower()
    if kind not in TRACK_TYPES:
        raise SkillError(
            f"tracks[{index}].type 不支持：{track.get('type')!r}",
            code="VALIDATION",
            details={"supported": sorted(TRACK_TYPES)},
        )
    segments = track.get("segments")
    if not isinstance(segments, list) or not segments:
        raise SkillError(f"tracks[{index}].segments 必须是非空数组", code="VALIDATION")
    return kind, segments


def _prepare_output(out_dir, force):
    """Validate the target without modifying it; the new draft is staged first."""
    raw = media_mod.local_path(out_dir, field="输出目录")
    if _is_link(raw):
        raise SkillError("输出目录是符号链接或 junction，拒绝写入",
                         code="UNSAFE_PATH", details={"path": str(raw)})
    out = raw.resolve()
    if out.exists():
        if not out.is_dir():
            raise SkillError("输出路径已存在且不是目录", code="OUTPUT_EXISTS",
                             details={"path": str(out)})
        entries = list(out.iterdir())
        marker = out / MARKER
        if entries and not marker.is_file():
            raise SkillError(
                "输出目录非空，且不是本技能生成的草稿",
                code="OUTPUT_NOT_EMPTY",
                details={"path": str(out), "entries": [p.name for p in entries[:8]]},
                fix="换一个空目录，或确认该目录是本技能生成的草稿后加 --force。",
            )
        if entries and not force:
            raise SkillError("输出目录已有草稿，需要 --force 覆盖",
                             code="OUTPUT_EXISTS", details={"path": str(out)})
    return out


def _commit_output(staging, final, force):
    """Publish a fully built staging directory without deleting old data."""
    previous = None
    if final.exists():
        entries = list(final.iterdir())
        if entries:
            if not force:
                raise SkillError("输出目录已有草稿，需要 --force 覆盖",
                                 code="OUTPUT_EXISTS", details={"path": str(final)})
            previous = final.parent / (
                f".jianying-backups-{_safe_component(final.name)}-{_backup_stamp()}")
            os.replace(final, previous)
        else:
            final.rmdir()
    try:
        staging.parent.mkdir(parents=True, exist_ok=True)
        os.replace(staging, final)
    except OSError as exc:
        restored = False
        rollback_error = None
        if previous and previous.exists() and not final.exists():
            try:
                os.replace(previous, final)
                restored = True
            except OSError as rollback_exc:
                rollback_error = str(rollback_exc)
        details = {"staging": str(staging), "final": str(final),
                   "reason": str(exc), "previous_restored": restored}
        if previous is not None:
            details["previous"] = str(previous)
        if rollback_error:
            details["rollback_error"] = rollback_error
        raise SkillError("草稿发布失败", code="OUTPUT_WRITE_FAILED",
                         details=details) from exc
    return previous


def _resolve_plan_resource_refs(value, *, fetch_resources=False):
    if isinstance(value, list):
        for item in value:
            _resolve_plan_resource_refs(item, fetch_resources=fetch_resources)
        return value
    if not isinstance(value, dict):
        return value
    ref = value.pop("resource_ref", None)
    if ref is not None:
        text = str(ref).strip()
        if not text:
            raise SkillError("resource_ref 不能为空", code="VALIDATION")
        resolved = resources_mod.resolve(text, allow_fuzzy=False)
        item = resolved["item"]
        if not item["cached"]:
            if not fetch_resources:
                raise SkillError("资源未缓存", code="RESOURCE_NOT_CACHED",
                                 details={"ref": text, "id": item["id"],
                                          "title": item["title"]},
                                 fix="先跑 jy.py resource download <ref> --apply，"
                                     "或给 build 加 --fetch-resources")
            resources_mod.download_resource(text, apply=True)
            item = resources_mod.resolve(text)["item"]
        if item["panel"] == "fonts":
            if not value.get("font_path"):
                value["font_path"] = str(resources_mod.font_file(item["package_path"]))
        else:
            if not value.get("resource_id"):
                value["resource_id"] = item["id"]
            if not value.get("path"):
                value["path"] = item["package_path"]
            if not value.get("name"):
                value["name"] = item["title"]
            if not value.get("effect_id"):
                value["effect_id"] = item["id"]
            if not value.get("category_id"):
                value["category_id"] = item["category_id"]
            if not value.get("category_name"):
                value["category_name"] = item["category_name"]
    for child in value.values():
        if isinstance(child, (dict, list)):
            _resolve_plan_resource_refs(child, fetch_resources=fetch_resources)
    return value


def _resolve_relative_extras_paths(plan, base):
    """extras 里的路径与素材 path 一样，以计划文件目录为基准。"""
    def resolve(value):
        text = str(value or "")
        if not text:
            return value
        path = Path(text).expanduser()
        if path.is_absolute():
            return value
        return str(base / path)

    def resolve_entry(entry):
        if isinstance(entry, dict) and entry.get("path"):
            entry["path"] = resolve(entry["path"])

    for track in plan.get("tracks") or []:
        if not isinstance(track, dict):
            continue
        for segment in track.get("segments") or []:
            if not isinstance(segment, dict):
                continue
            effect = segment.get("audio_effect")
            if isinstance(effect, dict):
                resolve_entry(effect)
            elif isinstance(effect, list):
                for item in effect:
                    resolve_entry(item)
            matting = segment.get("matting")
            if isinstance(matting, dict):
                for key in ("path", "mask_video_path"):
                    if matting.get(key):
                        matting[key] = resolve(matting[key])
            for key in ("text_template", "template"):
                template = segment.get(key)
                if not isinstance(template, dict):
                    continue
                if template.get("path"):
                    template["path"] = resolve(template["path"])
                for item in template.get("resources") or []:
                    resolve_entry(item)
    return plan


def build(plan_path, out_dir, *, force=False, name=None, make_cover=True,
          version_label=None, fetch_resources=False):
    plan = load_json(plan_path)
    if not isinstance(plan, dict):
        raise SkillError("计划必须是 JSON 对象", code="VALIDATION")
    _resolve_plan_resource_refs(plan, fetch_resources=fetch_resources)
    tracks = plan.get("tracks")
    if not isinstance(tracks, list) or not tracks:
        raise SkillError("计划缺少 tracks（至少一条视频/图片/音频/文字轨）",
                         code="VALIDATION")
    warnings = []

    plan_paths = []
    for track in tracks:
        for seg in track.get("segments") or []:
            if track.get("type") not in {"text", "sticker", "effect"} and seg.get("path"):
                plan_paths.append(seg["path"])

    from .env import find_ffmpeg, find_install

    try:
        install = find_install()
    except SkillError as exc:
        if plan_paths:
            raise
        install = None
    tools = find_ffmpeg(install)
    ffprobe = tools["ffprobe"]
    ffmpeg = tools["ffmpeg"]

    base = _asset("draft_base.json")
    video_tpl = _asset("video_material.json")
    text_tpl = _asset("text_material.json")
    audio_tpl = _asset("audio_material.json")

    doc = copy.deepcopy(base)
    doc["materials"] = {key: [] for key in base["materials"]}
    doc["tracks"] = []

    probe_cache = {}
    plan_dir = Path(plan_path).expanduser().resolve().parent
    _resolve_relative_extras_paths(plan, plan_dir)

    def probe_of(path):
        raw = media_mod.local_path(path, field="素材路径")
        resolved = raw if raw.is_absolute() else (plan_dir / raw)
        key = str(resolved.resolve())
        if key not in probe_cache:
            probe_cache[key] = media_mod.probe_media(ffprobe, key)
        return probe_cache[key]

    canvas = plan.get("canvas") or {}
    first_video = None
    for path in plan_paths:
        info = probe_of(path)
        if info["has_video"] and info["kind"] == "video":
            first_video = info
            break
    if canvas.get("width") is not None:
        width = int(_number("canvas.width", canvas["width"],
                            original=canvas["width"], positive=True))
    else:
        width = int(first_video["width"] if first_video else 1920)
    if canvas.get("height") is not None:
        height = int(_number("canvas.height", canvas["height"],
                             original=canvas["height"], positive=True))
    else:
        height = int(first_video["height"] if first_video else 1080)
    if canvas.get("width") is None and canvas.get("height") is None and not first_video:
        warnings.append(
            "计划未写 canvas 且没有视频素材，画布按 1920×1080 写入；"
            "请显式设置 canvas.width/height。")
    if canvas.get("fps") is not None:
        fps = _number("canvas.fps", canvas["fps"],
                      original=canvas["fps"], positive=True)
    else:
        fps = 30.0
        if first_video:
            try:
                fps = _number("fps", first_video.get("fps"), positive=True)
            except SkillError:
                fps = 30.0
                warnings.append(
                    f"视频素材 fps 不可用（{first_video.get('fps')!r}），"
                    "已回退 30.0；请在计划里显式设置 canvas.fps。")
    doc["canvas_config"] = {"background": None, "height": height, "width": width,
                            "ratio": "original"}
    doc["fps"] = fps
    doc["name"] = str(name or plan.get("name") or "jianying-draft")
    doc["id"] = uid()
    now = int(time.time())
    doc["create_time"] = now
    doc["update_time"] = now
    doc["duration"] = 0
    final_out = _prepare_output(out_dir, force)
    out = final_out.parent / f".tmp-build-{uid()}"
    try:
        out.mkdir(parents=True, exist_ok=False)
    except OSError as exc:
        raise SkillError("创建草稿暂存目录失败", code="OUTPUT_WRITE_FAILED",
                         details={"path": str(out), "reason": str(exc)}) from exc
    doc["path"] = str(final_out)
    try:

        visual_index = 0
        text_track_index = 0
        max_end = 0

        filter_specs = plan.get("filters") or []

        for track_index, track in enumerate(tracks):
            kind, segments = _check_track(track, track_index)
            if kind in {"effect", "sticker"}:
                new_track = {
                    "id": uid(),
                    "type": kind,
                    "attribute": 0,
                    "flag": 0,
                    "is_default_name": True,
                    "name": str(track.get("name") or ""),
                    "segments": [],
                }
            else:
                new_track = {
                    "id": uid(),
                    "type": ("text" if kind == "text" else
                             ("audio" if kind == "audio" else "video")),
                    "attribute": 0,
                    "flag": 0,
                    "is_default_name": True,
                    "name": str(track.get("name") or ""),
                    "segments": [],
                }
                if kind in {"video", "image"}:
                    new_track["flag"] = 0 if visual_index == 0 else 2
            for seg_spec in segments:
                if not isinstance(seg_spec, dict):
                    raise SkillError(f"tracks[{track_index}].segments 里有非对象", code="VALIDATION")
                _reject_unwired_segment_fields(
                    seg_spec, track_index=track_index, kind=kind)
                unknown_warning = _warn_unknown_segment_keys(
                    seg_spec, track_index=track_index)
                if unknown_warning:
                    warnings.append(unknown_warning)
                if kind == "effect":
                    start = _number("start", seg_spec.get("start", 0.0), min_value=0.0)
                    duration = _number("duration", seg_spec.get("duration", 1.0),
                                       positive=True)
                    material = _effect_material(seg_spec, track_index)
                    doc["materials"]["video_effects"].append(material)
                    new_track["segments"].append(
                        _effect_segment(material["id"], start, duration))
                    max_end = max(max_end, us(start + duration))
                    warnings.append(
                        "effects.video 已写入独立 effect 轨；效果包必须已缓存，"
                        "未缓存时导出报 dependency_missing 或被静默忽略。")
                    continue
                if kind == "sticker":
                    start = _number("start", seg_spec.get("start", 0.0), min_value=0.0)
                    duration = _number("duration", seg_spec.get("duration", 3.0),
                                       positive=True)
                    material = _sticker_material(seg_spec, track_index)
                    doc["materials"]["stickers"].append(material)
                    new_track["segments"].append(
                        _sticker_segment(material["id"], start, duration, seg_spec))
                    max_end = max(max_end, us(start + duration))
                    warnings.append(
                        "sticker 已写入独立 sticker 轨；贴纸包必须已在剪映缓存中，"
                        "否则导出报 dependency_missing 或被静默忽略。")
                    continue
                if kind == "text":
                    text = str(seg_spec.get("text") or "")
                    if not text.strip():
                        raise SkillError("text 片段缺少 text 文本", code="VALIDATION")
                    start = _number("start", seg_spec.get("start", 0.0), min_value=0.0)
                    duration = _number("duration", seg_spec.get("duration", 2.0), positive=True)
                    if start < 0 or duration <= 0:
                        raise SkillError("文字片段的 start 不能为负，duration 必须大于 0",
                                         code="VALIDATION",
                                         details={"track": track_index, "start": start,
                                                  "duration": duration})
                    material = _text_material(text, seg_spec, text_tpl)
                    doc["materials"]["texts"].append(material)
                    segment = _segment(
                        material["id"], start, duration,
                        render_index=15000 + text_track_index,
                        track_index=track_index,
                    )
                    _apply_clip(segment, seg_spec)
                    if "caption_info" in seg_spec:
                        _validate_caption_info(seg_spec["caption_info"])
                        segment["caption_info"] = seg_spec["caption_info"]
                    _apply_keyframes(segment, seg_spec.get("keyframes"))
                    for extra in _apply_text_extras(
                            segment, material, seg_spec, doc, warnings) or []:
                        if extra["kind"] == "text_template":
                            doc["materials"]["text_templates"].append(extra["material"])
                            warnings.append(
                                "text_template 已写入，但模板包必须已缓存；"
                                "resources 槽位缺失会导致导出失败。")
                        elif extra["kind"] == "text_animations":
                            doc["materials"]["material_animations"].append(extra["material"])
                            warnings.append(
                                "文字动画已写入 material_animations，但动画资源必须已缓存；"
                                "未缓存时剪映会忽略或报 dependency_missing。")
                        elif extra["kind"] in {"text_effect", "text_bubble", "text_glow"}:
                            doc["materials"]["filters"].append(extra["material"])
                    new_track["segments"].append(segment)
                    text_track_index += 1
                    max_end = max(max_end, us(start + duration))
                    continue

                path = seg_spec.get("path")
                if not path:
                    raise SkillError(f"{kind} 片段缺少 path", code="VALIDATION")
                info = probe_of(path)

                if kind == "audio":
                    for field in ("speed", "curve_speed"):
                        if seg_spec.get(field) is not None:
                            raise SkillError(
                                f"音频片段不支持 {field}；请在剪映客户端处理，"
                                "或先用 ffmpeg 变速素材",
                                code="VALIDATION",
                                details={"track": track_index, "field": field})
                    if not info["has_audio"]:
                        raise SkillError(f"音频素材没有音频流：{path}", code="VALIDATION")
                    start = _number("start", seg_spec.get("start", 0.0), min_value=0.0)
                    duration = _number(
                        "duration",
                        seg_spec.get("duration") if seg_spec.get("duration") is not None
                        else info["duration"], positive=True)
                    source_start = _number("source_start", seg_spec.get("source_start", 0.0),
                                           min_value=0.0)
                    if start < 0 or duration <= 0:
                        raise SkillError("音频片段的 start 不能为负，duration 必须大于 0",
                                         code="VALIDATION",
                                         details={"track": track_index, "start": start,
                                                  "duration": duration})
                    if source_start < 0:
                        raise SkillError("音频片段的 source_start 不能为负", code="VALIDATION",
                                         details={"source_start": source_start})
                    if source_start + duration > info["duration"] + 0.05:
                        raise SkillError(
                            f"音频区间超出素材时长：{source_start:g}+{duration:g}>{info['duration']:g}",
                            code="VALIDATION")
                    material = _audio_material(info, audio_tpl, info["duration"])
                    doc["materials"]["audios"].append(material)
                    segment = _segment(
                        material["id"], start, duration, source_start_s=source_start,
                        volume=_volume(seg_spec),
                        render_index=0, track_index=track_index,
                    )
                    _apply_keyframes(segment, seg_spec.get("keyframes"))
                    _apply_audio_extras(segment, seg_spec, doc, duration, warnings,
                                        primary_material=material)
                    new_track["segments"].append(segment)
                    max_end = max(max_end, us(start + duration))
                    continue

                if not info["has_video"]:
                    raise SkillError(f"{kind} 轨道里的素材没有视频流：{path}", code="VALIDATION")
                photo = info["kind"] == "image"
                if kind == "image" and not photo:
                    raise SkillError(f"image 轨道只能放图片：{path}", code="VALIDATION")
                start = _number("start", seg_spec.get("start", 0.0), min_value=0.0)
                duration = _number(
                    "duration",
                    seg_spec.get("duration") if seg_spec.get("duration") is not None
                    else (info["duration"] if not photo else 3.0), positive=True)
                source_start = _number("source_start", seg_spec.get("source_start", 0.0),
                                       min_value=0.0)
                speed = _number("speed", seg_spec.get("speed", 1.0), positive=True)
                if start < 0 or duration <= 0:
                    raise SkillError("视频/图片片段的 start 不能为负，duration 必须大于 0",
                                     code="VALIDATION",
                                     details={"track": track_index, "start": start,
                                              "duration": duration})
                if source_start < 0:
                    raise SkillError("视频片段的 source_start 不能为负", code="VALIDATION",
                                     details={"source_start": source_start})
                if speed <= 0:
                    raise SkillError("speed 必须大于 0", code="VALIDATION")
                if photo and abs(speed - 1.0) > 1e-9:
                    raise SkillError(
                        "图片素材不支持变速",
                        code="VALIDATION",
                        details={"field": "speed", "speed": speed},
                        fix="删除图片片段的 speed，或把 speed 设为 1；需要变速请改用视频轨。",
                    )
                if not photo and info["duration"]:
                    needed = source_start + duration * speed
                    if needed > info["duration"] + 0.05:
                        raise SkillError(
                            f"素材区间不够：source_start={source_start:g}s, duration={duration:g}s, "
                            f"speed={speed:g} 需要 {needed:g}s，素材只有 {info['duration']:g}s",
                            code="VALIDATION",
                        )
                material = _video_material(
                    info, video_tpl, photo=photo,
                    duration_s=(duration if photo else (info["duration"] or duration)),
                )
                doc["materials"]["videos"].append(material)
                render_index = 0 if visual_index == 0 else max(1, visual_index)
                segment = _segment(
                    material["id"], start, duration, source_start_s=source_start,
                    source_duration_s=(duration * speed if not photo else duration),
                    speed=speed, volume=_volume(seg_spec),
                    render_index=render_index, track_index=track_index,
                )
                _apply_clip(segment, seg_spec)
                _apply_keyframes(segment, seg_spec.get("keyframes"))
                _apply_video_animations(segment, seg_spec, doc, warnings)
                extra_materials = _apply_video_extras(
                    segment, material, seg_spec, warnings, doc, photo=photo)
                for extra in extra_materials or []:
                    if extra["kind"] == "mask":
                        doc["materials"]["common_mask"].append(extra["material"])
                        warnings.append(
                            "mask 已写入 common_mask，但蒙版资源必须已缓存；"
                            "未缓存时导出会静默忽略或报 dependency_missing。")
                    elif extra["kind"] == "curve_speed":
                        doc["materials"]["speeds"].append(extra["material"])
                    elif extra["kind"] == "color_wheel":
                        for item in extra["materials"]:
                            bucket = ("hsl" if item.get("type") == "hsl"
                                      else "primary_color_wheels")
                            doc["materials"][bucket].append(item)
                        warnings.append(
                            "color_wheel 已写入 primary_color_wheels/hsl；"
                            "2026-11-15 真机 gamma red=0.5 抽帧与无调色帧一致，"
                            "不要当已生效。")
                    elif extra["kind"] == "hsl":
                        doc["materials"]["hsl"].append(extra["material"])
                    elif extra["kind"] == "chroma":
                        doc["materials"]["chromas"].append(extra["material"])
                if material.get("has_audio") and any(
                        key in seg_spec for key in ("channel", "audio_fade",
                                                    "fade", "audio_effect",
                                                    "audio_effects")):
                    _apply_audio_extras(segment, seg_spec, doc, duration, warnings,
                                        primary_material=material, apply_native=False)

                transition = seg_spec.get("transition")
                if transition:
                    resource_id = str(transition.get("resource_id") or "").strip()
                    if not resource_id.isdigit():
                        raise SkillError(
                            "transition.resource_id 必须是剪映资源 ID（十进制数字）",
                            code="VALIDATION",
                            fix="先确认本机 Cache/effect 里已有该转场资源包，再把十进制资源 ID 写进计划；未缓存不要写。",
                        )
                    material_id = uid()
                    doc["materials"]["transitions"].append({
                        "id": material_id,
                        "type": "transition",
                        "name": str(transition.get("name") or ""),
                        "effect_id": resource_id,
                        "resource_id": resource_id,
                        "third_resource_id": resource_id,
                        "source_platform": int(_number(
                            "source_platform", transition.get("source_platform", 1),
                            min_value=0)),
                        "path": str(transition.get("path") or ""),
                        "duration": us(_number("duration", transition.get("duration", 0.5),
                                               positive=True)),
                        "is_overlap": True,
                        "category_id": str(transition.get("category_id") or ""),
                        "category_name": str(transition.get("category_name") or "热门"),
                    })
                    segment["extra_material_refs"].append(material_id)
                    warnings.append(
                        "transition 已写入左片段 refs，但本机未缓存转场素材包；"
                        "未缓存时剪映会静默忽略或报 film_export_dependency_missing。"
                    )

                new_track["segments"].append(segment)
                max_end = max(max_end, us(start + duration))

            doc["tracks"].append(new_track)
            if kind in {"video", "image"}:
                visual_index += 1

        if filter_specs:
            filter_segments = []
            for spec in filter_specs:
                if not isinstance(spec, dict):
                    raise SkillError("filters 里必须是对象", code="VALIDATION")
                resource_id = str(spec.get("resource_id") or "").strip()
                if not resource_id.isdigit():
                    raise SkillError("filters[].resource_id 必须是十进制资源 ID", code="VALIDATION")
                fid = uid()
                doc["materials"]["effects"].append({
                    "id": fid,
                    "effect_id": resource_id,
                    "resource_id": resource_id,
                    "third_resource_id": "0",
                    "name": str(spec.get("name") or ""),
                    "type": "filter",
                    "sub_type": "none",
                    "path": str(spec.get("path") or ""),
                    "value": _number("value", spec.get("value", 1.0)),
                    "category_id": str(spec.get("category_id") or ""),
                    "category_name": str(spec.get("category_name") or ""),
                    "source_platform": 1,
                    "color_match_info": {},
                    "multi_language_current": "",
                    "beauty_face_auto_retouch_info": {},
                })
                start = _number("start", spec.get("start", 0.0), min_value=0.0)
                duration = _number(
                    "duration",
                    spec.get("duration", max(0.1, (max_end - us(start)) / 1_000_000)),
                    positive=True)
                filter_segments.append({
                    "id": uid(),
                    "target_timerange": {"start": us(start), "duration": us(duration)},
                    "render_timerange": {},
                    "material_id": fid,
                    "render_index": 10000,
                    "enable_lut": False,
                    "enable_adjust": False,
                    "enable_hsl": False,
                    "responsive_layout": {},
                    "enable_adjust_mask": False,
                    "source": "segmentsourcenormal",
                })
            doc["tracks"].append({
                "id": uid(), "type": "filter", "segments": filter_segments,
                "is_default_name": True,
            })
            warnings.append("filters 写成独立 filter 轨道 + materials.effects[type=filter]；"
                            "素材必须已缓存，否则导出会失败。")

        doc["duration"] = max_end
        if doc["duration"] <= 0:
            raise SkillError("计划总时长为 0", code="VALIDATION")

        cover = None
        if make_cover and ffmpeg and plan_paths:
            try:
                from .media import extract_frame
                # plan_paths 是原始字符串；封面也必须按计划目录解析，否则相对路径会落到 CWD。
                cover_source = next((info["path"] for info in
                                     (probe_of(path) for path in plan_paths)
                                     if info.get("has_video")), None)
                if cover_source:
                    cover = extract_frame(ffmpeg, cover_source, 0.0, out / "draft_cover.jpg")
                    cover = Path(cover).name
            except SkillError:
                cover = None
                warnings.append("封面生成失败，草稿仍可使用（首页会显示默认封面）。")

        meta = _asset("draft_meta_base.json")
        meta.update({
            "draft_id": doc["id"],
            "draft_name": doc["name"],
            "draft_fold_path": str(final_out),
            "draft_root_path": str(final_out.parent),
            "draft_cover": cover or "",
            "draft_new_version": str(doc.get("new_version") or ""),
            "draft_type": "video",
            "draft_removable_storage_device": final_out.drive or "",
            "tm_draft_create": now * 1_000_000,
            "tm_draft_modified": now * 1_000_000,
            "tm_duration": doc["duration"],
            "draft_timeline_materials_size_": _materials_bytes(doc, out),
        })

        _write_json(out / "draft_info.json", doc)
        _write_json(out / "draft_meta_info.json", meta)
        try:
            (out / MARKER).write_text(json.dumps({
                "schema": "jianying-skill/v1",
                "created": now,
                "plan": str(Path(plan_path).expanduser().resolve()),
                "name": doc["name"],
            }, ensure_ascii=False, indent=2), "utf-8")
        except OSError as exc:
            raise SkillError("草稿标记文件写入失败", code="OUTPUT_WRITE_FAILED",
                             details={"path": str(out / MARKER),
                                       "reason": str(exc)}) from exc
        versions_mod.record_initial(
            out, out / "draft_info.json", out / "draft_meta_info.json",
            plan_path, label=version_label or "build")

    except BaseException:
        shutil.rmtree(out, ignore_errors=True)
        raise
    try:
        previous = _commit_output(out, final_out, force)
    except Exception:
        shutil.rmtree(out, ignore_errors=True)
        raise

    counts = {kind: sum(1 for t in doc["tracks"] if t["type"] == kind) for kind in
              ("video", "audio", "text", "filter")}
    return {
        "draft_dir": str(final_out),
        "info_path": str(final_out / "draft_info.json"),
        "name": doc["name"],
        "draft_id": doc["id"],
        "duration": round(doc["duration"] / 1_000_000, 3),
        "canvas": {"width": width, "height": height, "fps": fps},
        "tracks": counts,
        "materials": {key: len(value) for key, value in doc["materials"].items() if value},
        "cover": cover,
        "previous": str(previous) if previous else None,
        "versions": versions_mod.list_versions(final_out),
        "warnings": warnings,
    }


def _materials_bytes(document, root):
    total = 0
    for bucket in ("videos", "audios"):
        for item in document["materials"].get(bucket) or []:
            try:
                path = media_mod.local_path(item.get("path") or "", field="素材路径")
                if path.is_file():
                    total += path.stat().st_size
            except (OSError, SkillError):
                continue
    return total


def _plain_file(path):
    """普通文件：存在且不是符号链接/junction。"""
    path = Path(path)
    return path.is_file() and not _is_link(path)


def _read_optional_json(path, label, warnings):
    """读取可缺省的同目录 JSON；不可读时记 warning 并返回 None，不抛错。"""
    if not _plain_file(path):
        return None
    try:
        data = json.loads(Path(path).read_text("utf-8-sig"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        warnings.append(f"{label} 读取失败，已跳过一致性检查：{exc}")
        return None
    if not isinstance(data, dict):
        warnings.append(f"{label} 不是 JSON 对象，已跳过一致性检查。")
        return None
    return data


def _consistency_report(root, document, warnings):
    """轻量对比 draft_meta_info.json / draft_content.json 与 draft_info.json 的身份字段。"""
    info_id = document.get("id")
    info_name = document.get("name")
    report = {}
    meta = _read_optional_json(root / "draft_meta_info.json",
                               "draft_meta_info.json", warnings)
    if meta is None:
        report["meta"] = {"present": False}
    else:
        id_match = meta.get("draft_id") == info_id
        name_match = meta.get("draft_name") == info_name
        report["meta"] = {"present": True, "draft_id_match": id_match,
                          "draft_name_match": name_match}
        mismatched = []
        if not id_match:
            mismatched.append(
                f"draft_id（meta={meta.get('draft_id')!r}，draft_info={info_id!r}）")
        if not name_match:
            mismatched.append(
                f"draft_name（meta={meta.get('draft_name')!r}，draft_info={info_name!r}）")
        if mismatched:
            warnings.append(
                "draft_meta_info.json 与 draft_info.json 不一致：" + "、".join(mismatched)
                + "；以 draft_info.json 为准，或在剪映里重新登记草稿。")
    content = _read_optional_json(root / "draft_content.json",
                                  "draft_content.json", warnings)
    if content is None:
        report["content"] = {"present": False}
    else:
        id_match = content.get("id") == info_id
        name_match = content.get("name") == info_name
        report["content"] = {"present": True, "id_match": id_match,
                             "name_match": name_match}
        mismatched = []
        if not id_match:
            mismatched.append(
                f"id（content={content.get('id')!r}，draft_info={info_id!r}）")
        if not name_match:
            mismatched.append(
                f"name（content={content.get('name')!r}，draft_info={info_name!r}）")
        if mismatched:
            warnings.append(
                "draft_content.json 与 draft_info.json 不一致：" + "、".join(mismatched)
                + "；以 draft_info.json 为准，或在剪映里重新登记草稿。")
    return report


def inspect(draft_dir):
    resolved = resolve_draft_info(draft_dir)
    root = resolved["draft_dir"]
    info_path = resolved["info_path"]
    result = {
        "draft_dir": str(root),
        "layout": resolved["layout"],
        "timeline_id": resolved["timeline_id"],
        "info_path": str(info_path) if info_path else None,
        "encrypted": False,
        "name": None,
        "draft_id": None,
        "duration": None,
        "canvas": None,
        "fps": None,
        "tracks": [],
        "texts": [],
        "missing_media": [],
        "warnings": [],
        "consistency": {"meta": {"present": False}, "content": {"present": False}},
    }
    if not info_path:
        raise SkillError("不是剪映草稿目录：找不到 draft_info.json 或 Timelines/*/draft_info.json",
                         code="DRAFT_NOT_FOUND", details={"draft": str(root)})
    try:
        document = json.loads(info_path.read_text("utf-8-sig"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        result["encrypted"] = True
        result["warnings"].append(
            "draft_info.json 不是明文 JSON：剪映重存后可能加密。只能由剪映客户端打开/导出。")
        result["consistency"] = {
            "meta": {"present": _plain_file(root / "draft_meta_info.json")},
            "content": {"present": _plain_file(root / "draft_content.json")},
        }
        return result
    canvas = document.get("canvas_config") or {}
    result.update({
        "name": document.get("name"),
        "draft_id": document.get("id"),
        "duration": round(float(document.get("duration") or 0) / 1_000_000, 3),
        "canvas": {"width": canvas.get("width"), "height": canvas.get("height")},
        "fps": document.get("fps"),
    })
    materials = document.get("materials") or {}
    for track in document.get("tracks") or []:
        segments = track.get("segments") or []
        entry = {"type": track.get("type"), "segments": len(segments),
                 "flag": track.get("flag"), "starts": [], "ends": []}
        for seg in segments:
            window = seg.get("target_timerange") or {}
            start = float(window.get("start") or 0) / 1_000_000
            duration = float(window.get("duration") or 0) / 1_000_000
            entry["starts"].append(round(start, 3))
            entry["ends"].append(round(start + duration, 3))
            material_id = seg.get("material_id")
            for bucket in ("videos", "audios"):
                for item in materials.get(bucket) or []:
                    if item.get("id") != material_id:
                        continue
                    path = str(item.get("path") or "")
                    if path:
                        try:
                            local = media_mod.local_path(path, field="素材路径")
                        except SkillError:
                            result["missing_media"].append(path)
                            result["warnings"].append("草稿引用了 UNC/网络路径，已拒绝访问。")
                        else:
                            if not local.is_file():
                                result["missing_media"].append(path)
            try:
                text_item = _text_material_of(document, seg)
            except SkillError:
                text_item = None
            if text_item:
                try:
                    content = json.loads(text_item.get("content") or "{}")
                except json.JSONDecodeError:
                    content = {}
                result["texts"].append({
                    "start": round(start, 3), "duration": round(duration, 3),
                    "text": str(content.get("text") or "")[:80],
                    "type": text_item.get("type"),
                })
        result["tracks"].append(entry)
    if result["missing_media"]:
        result["warnings"].append("有素材路径不存在，渲染会失败或黑帧。")
    result["consistency"] = _consistency_report(root, document, result["warnings"])
    return result


def _flatten_segments(document):
    flat = []
    for track_index, track in enumerate(document.get("tracks") or []):
        for segment in track.get("segments") or []:
            flat.append((track_index, segment))
    return flat


def _find_segment(document, ref):
    flat = _flatten_segments(document)
    if isinstance(ref, int):
        if ref < 0 or ref >= len(flat):
            raise SkillError(f"segment 下标越界：{ref}（共 {len(flat)} 段）",
                             code="VALIDATION")
        return flat[ref][1]
    if isinstance(ref, str):
        for _, segment in flat:
            if segment.get("id") == ref:
                return segment
        for _, segment in flat:
            if str(segment.get("id") or "").startswith(ref):
                return segment
    raise SkillError(f"找不到片段：{ref!r}", code="VALIDATION")


def _text_material_of(document, segment):
    ids = [segment.get("material_id")]
    ids.extend(segment.get("extra_material_refs") or [])
    for item in (document.get("materials") or {}).get("texts") or []:
        if item.get("id") in ids:
            return item
    raise SkillError("该片段不是文字片段", code="VALIDATION",
                     details={"material_id": segment.get("material_id")})


def _write_text(material, text, *, font_size=None, color=None,
                stroke_color=None, stroke_width=None, align=None):
    try:
        content = json.loads(material.get("content") or "{}")
    except json.JSONDecodeError:
        content = {}
    content["text"] = text
    styles = content.get("styles") or [{}]
    style = styles[0]
    length = len(text.encode("utf-16-le")) // 2
    style["range"] = [0, length]
    if font_size is not None:
        size = _number("font_size", font_size, positive=True)
        style["size"] = size
        material["font_size"] = size
    if color is not None:
        style.setdefault("fill", {}).setdefault("content", {}).setdefault(
            "solid", {})["color"] = hex_rgb(color)
        material["text_color"] = color
    if stroke_color is not None:
        for stroke in style.get("strokes") or []:
            stroke.setdefault("content", {}).setdefault("solid", {})["color"] = \
                hex_rgb(stroke_color)
        material["border_color"] = stroke_color
    if stroke_width is not None:
        width = _number("stroke_width", stroke_width, min_value=0.0)
        if width <= 0:
            style["strokes"] = []
        elif not style.get("strokes"):
            style["strokes"] = [{
                "alpha": 1.0,
                "content": {"render_type": "solid",
                            "solid": {"alpha": 1.0, "color": hex_rgb(stroke_color or "#000000")}},
                "width": width,
            }]
        else:
            style["strokes"][0]["width"] = width
        material["border_width"] = width
    if align is not None:
        material["alignment"] = _alignment(align)
    encoded = json.dumps(content, ensure_ascii=False, separators=(",", ":"))
    material["content"] = encoded
    material["base_content"] = encoded
    material["type"] = "text"


def _referenced_material_ids(document):
    referenced = set()
    for _, segment in _flatten_segments(document):
        referenced.add(segment.get("material_id"))
        referenced.update(segment.get("extra_material_refs") or [])
    return referenced


def _drop_unused_material(document, material_id):
    referenced = _referenced_material_ids(document)
    if material_id in referenced:
        return
    for bucket, items in (document.get("materials") or {}).items():
        if not isinstance(items, list):
            continue
        kept = [item for item in items if item.get("id") != material_id]
        if len(kept) != len(items):
            document["materials"][bucket] = kept


def _material_lookup(document, material_id):
    for bucket in ("videos", "audios", "images", "texts"):
        for item in (document.get("materials") or {}).get(bucket) or []:
            if item.get("id") == material_id:
                return bucket, item
    return None, None


def _is_text_segment(document, segment):
    """只看主素材；extra_material_refs 里的文字材质不能代表片段类型。"""
    material_id = segment.get("material_id")
    return any(item.get("id") == material_id
               for item in (document.get("materials") or {}).get("texts") or [])


def _is_audio_segment(document, segment):
    material_id = segment.get("material_id")
    return any(item.get("id") == material_id
               for item in (document.get("materials") or {}).get("audios") or [])


def _check_source_range(document, segment, target_duration_s, speed):
    """校验 source_start + 目标时长*speed 不超过素材时长；余量不足拒绝。
    文字与图片素材没有源时长约束，跳过。"""
    bucket, material = _material_lookup(document, segment.get("material_id"))
    if bucket is None:
        raise SkillError("找不到对应素材，无法校验片段区间", code="VALIDATION",
                         details={"material_id": segment.get("material_id")})
    if bucket == "texts":
        return
    if bucket == "videos" and material.get("type") == "photo":
        source_start = int((segment.get("source_timerange") or {}).get("start", 0) or 0)
        if source_start < 0:
            raise SkillError("图片片段的源起点不能为负", code="VALIDATION",
                             details={"source_start_us": source_start})
        if abs(speed - 1.0) > 1e-9:
            raise SkillError("图片素材不支持变速", code="VALIDATION",
                             details={"field": "speed",
                                      "material_id": segment.get("material_id"),
                                      "speed": speed})
        return
    value = material.get("duration")
    try:
        material_duration = int(value) if value is not None else None
    except (TypeError, ValueError):
        material_duration = None
    if material_duration is None:
        raise SkillError("素材时长不可用，无法校验片段区间", code="VALIDATION",
                         details={"material_id": segment.get("material_id"),
                                  "bucket": bucket})
    source_start = int((segment.get("source_timerange") or {}).get("start", 0) or 0)
    needed_us = int(round(us(target_duration_s) * speed))
    if source_start < 0 or needed_us < 0:
        raise SkillError("片段区间不能为负", code="VALIDATION",
                         details={"source_start_us": source_start,
                                  "needed_us": needed_us})
    if source_start + needed_us > material_duration + 50_000:
        raise SkillError(
            f"片段区间超出素材长度：源起点 {source_start / 1e6:g}s + "
            f"{target_duration_s:g}s×{speed:g} 超过素材 {material_duration / 1e6:g}s",
            code="VALIDATION",
            details={"material_duration_us": material_duration,
                     "source_start_us": source_start, "needed_us": needed_us})


def _count_keyframes_beyond(segment, target_duration_us):
    """trim 只改片段时长，不重排关键帧；统计 time_offset 超出新时长的关键帧数。"""
    count = 0
    for channel in segment.get("common_keyframes") or []:
        if not isinstance(channel, dict):
            continue
        for keyframe in channel.get("keyframe_list") or []:
            if not isinstance(keyframe, dict):
                continue
            try:
                offset = int(keyframe.get("time_offset") or 0)
            except (TypeError, ValueError):
                continue
            if offset > target_duration_us:
                count += 1
    return count


SRT_TIME_RE = re.compile(
    r"(\d{1,2}):(\d{2}):(\d{2})[,.](\d{1,3})\s*-->\s*"
    r"(\d{1,2}):(\d{2}):(\d{2})[,.](\d{1,3})"
)


def _srt_seconds(hours, minutes, seconds, millis):
    return (int(hours) * 3600 + int(minutes) * 60 + int(seconds)
            + int(str(millis).ljust(3, "0")[:3]) / 1000)


def _read_srt_cues(path):
    try:
        raw = path.read_text("utf-8-sig")
    except OSError as exc:
        raise SkillError("SRT 文件读不了", code="FILE_NOT_FOUND",
                         details={"path": str(path), "reason": str(exc)}) from exc
    lines = raw.splitlines()
    cues = []
    index = 0
    while index < len(lines):
        line = lines[index].strip()
        if not line:
            index += 1
            continue
        if line.isdigit() and index + 1 < len(lines) and "-->" in lines[index + 1]:
            index += 1
            line = lines[index].strip()
        match = SRT_TIME_RE.search(line)
        if not match:
            index += 1
            continue
        start = _srt_seconds(*match.groups()[:4])
        end = _srt_seconds(*match.groups()[4:])
        index += 1
        text_lines = []
        while index < len(lines) and lines[index].strip():
            text_lines.append(lines[index].strip())
            index += 1
        if not text_lines:
            raise SkillError("SRT 时间码后没有字幕文本", code="VALIDATION",
                             details={"path": str(path), "line": index})
        if end <= start:
            raise SkillError("SRT 时间码不是正时长", code="VALIDATION",
                             details={"path": str(path), "start": start, "end": end})
        cues.append({"text": "\n".join(text_lines), "start": start, "end": end})
    if not cues:
        raise SkillError("SRT 没有可用的字幕", code="VALIDATION",
                         details={"path": str(path)})
    ordered = sorted(cues, key=lambda cue: (cue["start"], cue["end"]))
    previous_end = -1.0
    for position, cue in enumerate(ordered, 1):
        if cue["start"] < previous_end - 0.001:
            raise SkillError("SRT 字幕重叠，不能写进同一文字轨", code="VALIDATION",
                             details={"path": str(path), "cue": position,
                                      "start": cue["start"], "previous_end": previous_end},
                             fix="先用 subtitles/cli.py srt.tidy 修正重叠")
        previous_end = cue["end"]
    return ordered


def _find_text_track(document, name):
    for position, track in enumerate(document.get("tracks") or []):
        if track.get("type") == "text" and str(track.get("name") or "") == name:
            return position, track
    return None, None


_ADD_SUBTITLES_STYLE_KEYS = {
    "font_size", "color", "stroke_color", "stroke_width", "font_path", "align",
    "line_spacing", "letter_spacing", "bold", "italic", "underline",
    "background", "shadow", "highlight", "line_max_width",
    "x", "y", "transform", "scale", "rotation", "opacity",
    "caption_template", "subtitle_template",
}


def _caption_info_for_cue(text, start, end):
    duration = us(max(0.0, end - start))
    return {
        "id": uid(),
        "speaker_type": "",
        "speaker_id": "",
        "caption_segment_id": uid(),
        "original_text": text,
        "words": [{
            "id": uid(),
            "text": text,
            "tag": "",
            "origin_text": text,
            "time_range": {"start": 0, "duration": duration},
        }],
    }


def _add_subtitles(document, op, base=None):
    raw_srt = str(op.get("srt") or "").strip()
    if not raw_srt:
        raise SkillError("add_subtitles 需要 srt 路径", code="VALIDATION")
    srt_path = media_mod.local_path(raw_srt, field="add_subtitles.srt")
    if not srt_path.is_absolute() and base is not None:
        srt_path = base / srt_path
    cues = _read_srt_cues(srt_path)
    style = op.get("style") or {}
    if not isinstance(style, dict):
        raise SkillError("add_subtitles.style 必须是对象", code="VALIDATION")
    unsupported = sorted(set(style) - _ADD_SUBTITLES_STYLE_KEYS)
    if unsupported:
        raise SkillError(
            f"add_subtitles 不支持 style.{unsupported[0]}",
            code="VALIDATION",
            details={"unsupported": unsupported,
                     "supported": sorted(_ADD_SUBTITLES_STYLE_KEYS)},
            fix="字幕轨只接受基础文字样式和 caption_template；动画/花字/文字模板/"
                "resource_ref 请走 build 的 text 轨。",
        )
    for key in ("caption_template", "subtitle_template"):
        template = style.get(key)
        if template is None:
            continue
        if not isinstance(template, dict):
            raise SkillError(f"add_subtitles.style.{key} 必须是对象",
                             code="VALIDATION")
        if not str(template.get("resource_id") or "").strip():
            raise SkillError(f"add_subtitles.style.{key}.resource_id 不能为空",
                             code="VALIDATION")
        if "resource_ref" in template:
            raise SkillError(
                f"add_subtitles.style.{key} 不接受 resource_ref",
                code="VALIDATION",
                fix="先用 resource resolve 取 id，再写 resource_id/path；"
                    "resource_ref 由 build 解析。",
            )
    style = dict(style)
    style.setdefault("font_size", 8)
    style.setdefault("y", -0.72)
    caption_template = _caption_template_ref(style)
    name = str(op.get("name") or "字幕").strip() or "字幕"

    tracks = document.setdefault("tracks", [])
    track_index, track = _find_text_track(document, name)
    if track is None:
        track_index = len(tracks)
        track = {"id": uid(), "type": "text", "attribute": 0, "flag": 0,
                 "is_default_name": True, "name": name, "segments": []}
        tracks.append(track)
    else:
        old_refs = []
        for segment in track.get("segments") or []:
            old_refs.append(segment.get("material_id"))
            old_refs.extend(segment.get("extra_material_refs") or [])
        track["segments"] = []
        for ref in old_refs:
            if ref:
                _drop_unused_material(document, ref)

    content_end = 0
    for other in tracks:
        if other is track:
            continue
        for segment in other.get("segments") or []:
            window = segment.get("target_timerange") or {}
            content_end = max(content_end, int(window.get("start", 0))
                              + int(window.get("duration", 0)))
    if content_end and cues[-1]["end"] > content_end / 1_000_000 + 1.0:
        raise SkillError("字幕超出草稿现有内容时长", code="VALIDATION",
                         details={"srt_end": cues[-1]["end"],
                                  "draft_end": content_end / 1_000_000},
                         fix="先裁剪 SRT 或视频；add_subtitles 不自动延长视频轨")

    text_tpl = _asset("text_material.json")
    text_tracks = [item for item in tracks if item.get("type") == "text"]
    text_track_index = text_tracks.index(track)
    for cue in cues:
        spec = dict(style)
        spec["text"] = cue["text"]
        material = _text_material(cue["text"], spec, text_tpl)
        document.setdefault("materials", {}).setdefault("texts", []).append(material)
        segment = _segment(
            material["id"], cue["start"], cue["end"] - cue["start"],
            render_index=15000 + text_track_index, track_index=track_index)
        _apply_clip(segment, spec)
        if caption_template:
            segment["caption_info"] = _caption_info_for_cue(
                cue["text"], cue["start"], cue["end"])
        track["segments"].append(segment)
    return f"add_subtitles -> {len(cues)} cues @ {name}"


def _apply_op(document, op, base=None):
    if not isinstance(op, dict):
        raise SkillError("ops 里每一项都必须是对象", code="VALIDATION")
    kind = str(op.get("op") or "").strip()
    if kind == "rename":
        name = str(op.get("name") or "").strip()
        if not name:
            raise SkillError("rename 需要 name", code="VALIDATION")
        document["name"] = name
        return f"rename -> {name}"
    if kind == "set_canvas":
        canvas = document.setdefault("canvas_config", {})
        if "width" in op:
            canvas["width"] = int(_number("width", op["width"],
                                          original=op["width"], positive=True))
        if "height" in op:
            canvas["height"] = int(_number("height", op["height"],
                                           original=op["height"], positive=True))
        return f"set_canvas -> {canvas.get('width')}x{canvas.get('height')}"
    if kind == "fps":
        fps_value = op.get("value", document.get("fps") or 30)
        document["fps"] = _number("fps", fps_value, original=fps_value, positive=True)
        return f"fps -> {document['fps']}"
    if kind == "add_subtitles":
        return _add_subtitles(document, op, base)

    segment = _find_segment(document, op.get("segment"))
    if kind == "set_text":
        text = str(op.get("text") or "")
        if not text.strip():
            raise SkillError("set_text 需要非空 text", code="VALIDATION")
        material = _text_material_of(document, segment)
        _write_text(material, text, font_size=op.get("font_size"), color=op.get("color"),
                    stroke_color=op.get("stroke_color"),
                    stroke_width=op.get("stroke_width"), align=op.get("align"))
        return f"set_text -> {text[:20]}"
    if kind == "set_style":
        material = _text_material_of(document, segment)
        _write_text(material, _current_text(material), font_size=op.get("font_size"),
                    color=op.get("color"), stroke_color=op.get("stroke_color"),
                    stroke_width=op.get("stroke_width"), align=op.get("align"))
        return "set_style"
    if kind == "set_volume":
        volume = _number("volume", op.get("volume", 1.0),
                         original=op.get("volume", 1.0),
                         min_value=0.0, max_value=10.0)
        segment["volume"] = volume
        if volume > 0:
            segment["last_nonzero_volume"] = volume
        return f"set_volume -> {volume:g}"
    if kind == "set_speed":
        speed = _number("speed", op.get("speed", 1.0),
                        original=op.get("speed", 1.0), positive=True)
        if _is_text_segment(document, segment):
            raise SkillError("文字片段不支持变速", code="VALIDATION",
                             details={"field": "speed",
                                      "material_id": segment.get("material_id")})
        if _is_audio_segment(document, segment):
            raise SkillError(
                "音频片段不支持变速；请在剪映客户端处理，"
                "或先用 ffmpeg 变速素材",
                code="VALIDATION",
                details={"field": "speed",
                         "material_id": segment.get("material_id")})
        target = segment["target_timerange"]
        target_duration_s = int(target.get("duration", 0)) / 1_000_000
        _check_source_range(document, segment, target_duration_s, speed)
        segment["speed"] = speed
        segment["source_timerange"] = {
            "start": (segment.get("source_timerange") or {}).get("start", 0),
            "duration": int(round(target["duration"] * speed)),
        }
        return f"set_speed -> {speed:g}"
    if kind == "shift":
        start = _number("start", op.get("start", 0.0),
                        original=op.get("start", 0.0), min_value=0.0)
        segment["target_timerange"]["start"] = us(start)
        return f"shift -> {start:g}s"
    if kind == "trim":
        duration = _number("duration", op.get("duration", 0.0),
                           original=op.get("duration", 0.0), positive=True)
        speed = _number("speed", segment.get("speed", 1.0),
                        original=segment.get("speed", 1.0), positive=True)
        _check_source_range(document, segment, duration, speed)
        segment["target_timerange"]["duration"] = us(duration)
        if not _is_text_segment(document, segment):
            # 文字片段只改显示窗口；写 source_timerange 会让剪映按源区间裁剪。
            segment.setdefault("source_timerange", {})["duration"] = us(duration * speed)
        message = f"trim -> {duration:g}s"
        beyond = _count_keyframes_beyond(segment, us(duration))
        if beyond:
            message += (f"（{beyond} 个关键帧超出新时长；剪映可能裁掉或压缩它们，"
                        f"需要时用 keyframes 重新生成）")
        return message
    if kind == "set_transform":
        _apply_clip(segment, op)
        return "set_transform"
    if kind == "remove":
        material_id = segment.get("material_id")
        extra_refs = list(segment.get("extra_material_refs") or [])
        for track in document.get("tracks") or []:
            segments = track.get("segments") or []
            for index, item in enumerate(segments):
                if item.get("id") == segment.get("id"):
                    segments.pop(index)
                    break
            if not segments:
                track["segments"] = []
        document["tracks"] = [track for track in document.get("tracks") or []
                              if track.get("segments")]
        # 片段删除后它的主素材与 extra_material_refs 都可能失去全部引用；
        # _drop_unused_material 自带引用检查，仍被其他片段引用的素材不会删。
        for ref in [material_id, *extra_refs]:
            if ref:
                _drop_unused_material(document, ref)
        return "remove"
    raise SkillError(f"不支持的 op：{kind!r}", code="VALIDATION",
                     details={"supported": ["rename", "set_canvas", "fps", "add_subtitles",
                                            "set_text", "set_style", "set_volume", "set_speed",
                                            "shift", "trim", "set_transform", "remove"]})


def _current_text(material):
    try:
        return str((json.loads(material.get("content") or "{}") or {}).get("text") or "")
    except json.JSONDecodeError:
        return ""


def patch(draft_dir, ops_path, out_dir, *, in_place=False, version_label=None):
    ops = load_json(ops_path)
    if isinstance(ops, dict) and "ops" in ops:
        ops = ops["ops"]
    if not isinstance(ops, list) or not ops:
        raise SkillError("补丁文件必须是数组，或 {\"ops\": [...]}", code="VALIDATION")
    resolved = resolve_draft_info(draft_dir)
    if not resolved["info_path"]:
        raise SkillError("不是草稿目录", code="DRAFT_NOT_FOUND")
    source_info_bytes = resolved["info_path"].read_bytes()
    source_meta_path = resolved["draft_dir"] / "draft_meta_info.json"
    source_meta_bytes = source_meta_path.read_bytes() if source_meta_path.is_file() else None
    try:
        document = json.loads(resolved["info_path"].read_text("utf-8-sig"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise SkillError("草稿是加密的，无法用 JSON 补丁修改",
                         code="DRAFT_ENCRYPTED",
                         fix="在剪映里另存为明文副本，或只对本技能生成的草稿打补丁。") from exc
    backups = []
    staging = None
    staging_info = None
    if in_place:
        out = resolved["draft_dir"]
        backup_dir = out / ".jianying-backups"
        try:
            backup_dir.mkdir(parents=True, exist_ok=True)
            info_backup = backup_dir / f"draft_info.{_backup_stamp()}.json"
            shutil.copy2(resolved["info_path"], info_backup)
            backups.append(str(info_backup))
            meta_source = out / "draft_meta_info.json"
            if meta_source.is_file():
                meta_backup = backup_dir / f"draft_meta_info.{_backup_stamp()}.json"
                shutil.copy2(meta_source, meta_backup)
                backups.append(str(meta_backup))
        except OSError as exc:
            raise SkillError("备份原草稿失败，已中止", code="OUTPUT_WRITE_FAILED",
                             details={"path": str(out), "reason": str(exc)}) from exc
    else:
        if not out_dir:
            raise SkillError("patch 需要 --out（默认写副本）；确需改原草稿加 --in-place",
                             code="VALIDATION")
        source = resolved["draft_dir"].resolve()
        out = media_mod.local_path(out_dir, field="输出目录").resolve()
        if out == source or out.is_relative_to(source):
            raise SkillError("--out 不能指向源草稿目录内部",
                             code="VALIDATION",
                             details={"source": str(source), "out": str(out)})
        if out.exists():
            raise SkillError("输出目录已存在", code="OUTPUT_EXISTS",
                             details={"path": str(out)})
        info_relative = resolved["info_path"].relative_to(source)
        try:
            _assert_plain_tree(source)
            staging = out.parent / f".tmp-{uid()}"
            shutil.copytree(source, staging, symlinks=True)
            staging_info = staging / info_relative
            # 只删除能证明与 draft_info 字节一致的镜像；未知运行时文件原样保留，
            # 避免把用户手工塞进草稿目录的资产当垃圾清掉。
            mirror = staging / "draft_content.json"
            if mirror.is_file():
                try:
                    if hashlib.sha256(mirror.read_bytes()).digest() != hashlib.sha256(
                            staging_info.read_bytes()).digest():
                        pass
                    else:
                        mirror.unlink()
                except OSError:
                    pass
            document = json.loads(staging_info.read_text("utf-8-sig"))
            resolved = dict(resolved, draft_dir=out, info_path=out / info_relative)
        except SkillError:
            if staging and staging.exists():
                shutil.rmtree(staging, ignore_errors=True)
            raise
        except (OSError, shutil.Error) as exc:
            if staging and staging.exists():
                shutil.rmtree(staging, ignore_errors=True)
            raise SkillError("复制草稿副本失败", code="COPY_FAILED",
                             details={"source": str(source), "target": str(out),
                                      "reason": str(exc)}) from exc

    try:
        results = []
        ops_base = Path(ops_path).resolve().parent
        for index, op in enumerate(ops):
            try:
                results.append(_apply_op(document, op, base=ops_base))
            except SkillError as exc:
                raise SkillError(f"ops[{index}] 失败：{exc.message}", code=exc.code,
                                 details={"index": index, "op": op, **exc.details}) from exc

        tracks = document.get("tracks") or []
        if not any(track.get("segments") for track in tracks):
            raise SkillError("补丁后草稿没有任何片段", code="VALIDATION",
                             details={"reason": "empty_draft"})
        max_end = 0
        for track in tracks:
            for segment in track.get("segments") or []:
                window = segment.get("target_timerange") or {}
                max_end = max(max_end, int(window.get("start", 0)) + int(window.get("duration", 0)))
        document["duration"] = max_end
        if document["duration"] <= 0:
            raise SkillError("补丁后草稿时长为 0", code="VALIDATION",
                             details={"reason": "empty_draft"})
        document["update_time"] = int(time.time())
        document["path"] = str(resolved["draft_dir"])
        write_root = staging if staging else resolved["draft_dir"]
        write_info = staging_info if staging else resolved["info_path"]
        _write_json(write_info, document)
        meta_path = write_root / "draft_meta_info.json"
        if meta_path.is_file():
            meta = load_json(meta_path)
            meta.update(draft_id=document.get("id"), draft_name=document.get("name"),
                        draft_fold_path=str(resolved["draft_dir"]),
                        draft_root_path=str(resolved["draft_dir"].parent),
                        tm_draft_modified=document["update_time"] * 1_000_000,
                        tm_duration=document["duration"])
            _write_json(meta_path, meta)
        artifacts = []
        for op in ops:
            if not isinstance(op, dict) or op.get("op") != "add_subtitles":
                continue
            raw_srt = str(op.get("srt") or "").strip()
            if not raw_srt:
                continue
            srt_path = Path(raw_srt).expanduser()
            if not srt_path.is_absolute():
                srt_path = ops_base / srt_path
            if srt_path.is_file():
                artifacts.append(srt_path)
        versions_mod.record_patch(
            write_root, write_info, ops_path, label=version_label or "patch",
            baseline_info=source_info_bytes, baseline_meta=source_meta_bytes,
            artifacts=artifacts)
        if staging:
            os.replace(staging, out)
            staging = None
    except BaseException as exc:
        if staging and staging.exists():
            shutil.rmtree(staging, ignore_errors=True)
        elif in_place and backups:
            rollback_errors = []
            try:
                shutil.copy2(backups[0], resolved["info_path"])
            except OSError as rollback_exc:
                rollback_errors.append(f"draft_info: {rollback_exc}")
            meta_target = resolved["draft_dir"] / "draft_meta_info.json"
            if len(backups) > 1:
                try:
                    shutil.copy2(backups[1], meta_target)
                except OSError as rollback_exc:
                    rollback_errors.append(f"draft_meta_info: {rollback_exc}")
            if rollback_errors:
                details = {
                    "reason": "in_place 失败且回滚失败",
                    "rollback_errors": rollback_errors,
                    "original_error": getattr(exc, "to_dict", lambda: str(exc))(),
                }
                raise SkillError(
                    "补丁失败，且原稿回滚失败；请用 .jianying-backups 手工恢复",
                    code="OUTPUT_WRITE_FAILED", details=details) from exc
        raise
    return {
        "draft_dir": str(resolved["draft_dir"]),
        "info_path": str(resolved["info_path"]),
        "duration": round(document["duration"] / 1_000_000, 3),
        "ops": results,
        "in_place": in_place,
        "backup": backups[0] if backups else None,
        "backups": backups,
        "versions": versions_mod.list_versions(resolved["draft_dir"]),
    }
