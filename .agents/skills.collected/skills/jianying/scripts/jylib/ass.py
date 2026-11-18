"""ASS/SSA 字幕交换：保留事件时间、基础样式和常用内联覆盖标签。

不做完整 ASS 渲染器。支持的覆盖标签：`\\c`/`\\1c`（颜色）、`\\fs`（字号）、
`\\b`/`\\i`/`\\u`（粗/斜/下划线）、`\\r`（重置）。其他标签会被丢弃并在回执
里报告，避免静默改变语义。
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from .errors import SkillError
from . import media as media_mod

_TIME = re.compile(r"^\s*(\d+):(\d{2}):(\d{2})[.:](\d{1,3})\s*$")
_TAG = re.compile(r"\{([^}]*)\}")
_ASS_COLOR = re.compile(r"&H([0-9A-Fa-f]{6,8})&?")


def _seconds(value):
    match = _TIME.match(str(value))
    if not match:
        raise SkillError("ASS 时间码非法", code="PARSE_FAIL", details={"value": value})
    h, m, s, frac = match.groups()
    return int(h) * 3600 + int(m) * 60 + int(s) + int(frac.ljust(3, "0")) / 1000.0


def _ass_time(seconds):
    total = max(0, float(seconds))
    h = int(total // 3600)
    m = int((total % 3600) // 60)
    s = total % 60
    return f"{h}:{m:02d}:{s:05.2f}"


def _color_to_ass(value):
    text = str(value or "#FFFFFF").strip().lstrip("#")
    if len(text) == 6:
        r, g, b = text[0:2], text[2:4], text[4:6]
    elif len(text) == 8:
        r, g, b = text[2:4], text[4:6], text[6:8]
    else:
        r, g, b = "FF", "FF", "FF"
    return f"&H00{b}{g}{r}&".upper()


def _ass_to_color(raw):
    match = _ASS_COLOR.search(str(raw or ""))
    if not match:
        return None
    digits = match.group(1)
    if len(digits) == 8:
        digits = digits[2:]
    b, g, r = digits[0:2], digits[2:4], digits[4:6]
    return f"#{r}{g}{b}".upper()


def _style_fields(line):
    body = line.split(":", 1)[1].strip()
    fields = [part.strip() for part in body.split(",")]
    return fields


def _parse_sections(text):
    sections = {}
    current = None
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith(";"):
            continue
        if line.startswith("[") and line.endswith("]"):
            current = line[1:-1].strip().lower()
            sections.setdefault(current, [])
            continue
        if current:
            sections[current].append(line)
    return sections


def _parse_styles(lines):
    styles = {}
    fmt = None
    for line in lines:
        if line.lower().startswith("format:"):
            fmt = [part.strip().lower() for part in line.split(":", 1)[1].split(",")]
            continue
        if not line.lower().startswith("style:"):
            continue
        fields = _style_fields(line)
        if fmt and len(fields) >= len(fmt):
            record = dict(zip(fmt, fields))
        else:
            record = {"name": fields[0] if fields else "Default"}
            if len(fields) > 1:
                record["fontname"] = fields[1]
            if len(fields) > 2:
                record["fontsize"] = fields[2]
            if len(fields) > 3:
                record["primarycolour"] = fields[3]
        name = record.get("name") or "Default"
        styles[name] = {
            "font_name": record.get("fontname") or "",
            "font_size": float(record.get("fontsize") or 48),
            "color": _ass_to_color(record.get("primarycolour")) or "#FFFFFF",
            "bold": str(record.get("bold") or "0") not in {"0", "-1"},
            "italic": str(record.get("italic") or "0") not in {"0", "-1"},
            "underline": str(record.get("underline") or "0") not in {"0", "-1"},
            "outline": record.get("outlinecolour"),
            "back": record.get("backcolour"),
        }
    return styles


def _is_flag_tag(raw, name):
    """``\\b1`` / ``\\i0`` 这类开关标签：必须以该标签名开头，且名字后只能为空或纯数字。

    不能只比较剩余字符：``\\i0`` 去掉首字母后是 ``0``，只看余额会把斜体、下划线、
    删除线（``\\s``）、卡拉OK（``\\k``）和 ``\\r`` 全部吞成加粗。也不能只用
    ``startswith``：``\\bord3`` / ``\\blur1`` / ``\\be1`` 都以 ``b`` 开头。
    """
    if not raw.startswith(name):
        return False
    rest = raw[len(name):]
    return rest == "" or rest.isdigit()


def _parse_override_tags(tags):
    """返回 (样式字典, 未支持标签列表)。"""
    style = {}
    unsupported = []
    for raw in tags.split("\\"):
        if not raw:
            continue
        if raw.startswith("c&H") or raw.startswith("1c&H"):
            style["color"] = _ass_to_color(raw)
        elif raw.startswith("fs"):
            try:
                style["font_size"] = float(raw[2:])
            except ValueError:
                unsupported.append("\\" + raw)
        elif _is_flag_tag(raw, "b"):
            style["bold"] = raw[1:] != "0"
        elif _is_flag_tag(raw, "i"):
            style["italic"] = raw[1:] != "0"
        elif _is_flag_tag(raw, "u"):
            style["underline"] = raw[1:] != "0"
        elif raw == "r":
            style["reset"] = True
        elif raw:
            # 命名样式重置（\rStyleName）等未建模的标签如实登记，不静默改写。
            unsupported.append("\\" + raw.split("(")[0])
    return style, unsupported


def parse_ass(path):
    target = media_mod.local_path(path, field="ASS 文件")
    if not target.is_file():
        raise SkillError("ASS 文件不存在", code="FILE_NOT_FOUND",
                         details={"path": str(target)})
    try:
        text = target.read_text("utf-8-sig")
    except UnicodeDecodeError:
        text = target.read_text("gb18030")
    sections = _parse_sections(text)
    styles = _parse_styles(sections.get("v4+ styles", []) or sections.get("v4 styles", []))
    fmt = None
    events = []
    unsupported = set()
    for line in sections.get("events", []):
        if line.lower().startswith("format:"):
            fmt = [part.strip().lower() for part in line.split(":", 1)[1].split(",")]
            continue
        if not line.lower().startswith("dialogue:"):
            continue
        body = line.split(":", 1)[1].lstrip()
        fields = body.split(",", 9) if not fmt else body.split(",", max(0, len(fmt) - 1))
        if fmt and len(fields) >= len(fmt):
            record = dict(zip(fmt, fields))
            start = record.get("start", "")
            end = record.get("end", "")
            style_name = record.get("style", "Default") or "Default"
            raw_text = record.get("text", "")
        else:
            if len(fields) < 10:
                raise SkillError("ASS Dialogue 字段不足", code="PARSE_FAIL",
                                 details={"line": line[:80]})
            start, end, style_name, raw_text = fields[1], fields[2], fields[3], fields[9]
        base = styles.get(style_name) or styles.get("Default") or {
            "font_name": "", "font_size": 48, "color": "#FFFFFF",
            "bold": False, "italic": False, "underline": False,
        }
        visible, ranges = _parse_text_runs(raw_text, base, unsupported)
        events.append({
            "start": _seconds(start), "end": _seconds(end),
            "style": style_name, "text": visible,
            "ranges": ranges, "base": base,
        })
    return {
        "styles": styles, "events": events,
        "unsupported_tags": sorted(tag for tag in unsupported if tag),
    }


def _parse_text_runs(raw_text, base, unsupported):
    """把带覆盖标签的 ASS 文本拆成可见文本 + 非重叠区间样式。"""
    pieces = []
    current = dict(base)
    position = 0
    last = 0
    for match in _TAG.finditer(raw_text):
        chunk = raw_text[last:match.start()]
        if chunk:
            pieces.append((chunk, dict(current)))
            position += len(chunk.replace("\\N", "\n").replace("\\n", "\n"))
        override, bad = _parse_override_tags(match.group(1))
        unsupported.update(bad)
        if override.get("reset"):
            current = dict(base)
        else:
            current.update({key: value for key, value in override.items()
                            if key != "reset" and value is not None})
        last = match.end()
    chunk = raw_text[last:]
    if chunk:
        pieces.append((chunk, dict(current)))

    visible = []
    ranges = []
    offset = 0
    for chunk, style in pieces:
        text = chunk.replace("\\N", "\n").replace("\\n", "\n").replace("\\h", " ")
        if not text:
            continue
        begin = offset
        visible.append(text)
        offset += len(text)
        if style.get("color") or style.get("font_size") or style.get("bold") \
                or style.get("italic") or style.get("underline"):
            ranges.append({
                "start": begin, "end": offset,
                "color": style.get("color"),
                "font_size": style.get("font_size"),
                "bold": style.get("bold"),
                "italic": style.get("italic"),
                "underline": style.get("underline"),
            })
    return "".join(visible), ranges


def to_plan(parsed, *, name="ASS 字幕", canvas=None, font_scale=1.0):
    """把 ASS 事件转成技能 build 计划（单个 text 轨）。"""
    width = int((canvas or {}).get("width") or 1920)
    height = int((canvas or {}).get("height") or 1080)
    segments = []
    for event in parsed["events"]:
        text = event["text"]
        if not text:
            continue
        base = event["base"]
        offset = 0
        ranges = []
        for item in event["ranges"]:
            ranges.append({
                "start": len(text[:item["start"]].encode("utf-16-le")) // 2,
                "end": len(text[:item["end"]].encode("utf-16-le")) // 2,
                **{key: item[key] for key in
                   ("color", "font_size", "bold", "italic", "underline")
                   if item.get(key) is not None},
            })
            offset += 1
        segments.append({
            "text": text,
            "start": round(event["start"], 6),
            "duration": round(max(0.001, event["end"] - event["start"]), 6),
            "font_size": (base.get("font_size") or 48) * float(font_scale),
            "color": base.get("color") or "#FFFFFF",
            "bold": bool(base.get("bold")),
            "italic": bool(base.get("italic")),
            "underline": bool(base.get("underline")),
            "range_styles": ranges,
        })
    return {
        "name": name, "canvas": {"width": width, "height": height, "fps": 30},
        "tracks": [{"type": "text", "name": "ASS", "segments": segments}],
    }


def export_draft(draft_dir, out_path):
    from . import draft as draft_mod
    resolved = draft_mod.resolve_draft_info(draft_dir)
    root = resolved["draft_dir"]
    info = resolved["info_path"]
    if not info:
        raise SkillError("不是剪映草稿目录", code="DRAFT_NOT_FOUND",
                         details={"draft": str(root)})
    try:
        doc = json.loads(info.read_text("utf-8-sig"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise SkillError("草稿不是明文 JSON", code="DRAFT_ENCRYPTED",
                         details={"path": str(info)}) from exc
    canvas = doc.get("canvas_config") or {}
    width, height = int(canvas.get("width") or 1920), int(canvas.get("height") or 1080)
    events = []
    for track in doc.get("tracks") or []:
        if track.get("type") != "text":
            continue
        for segment in track.get("segments") or []:
            material_id = segment.get("material_id")
            ids = [material_id, *(segment.get("extra_material_refs") or [])]
            material = next((item for item in (doc.get("materials") or {}).get("texts") or []
                             if item.get("id") in ids), None)
            if not material:
                continue
            try:
                content = json.loads(material.get("content") or "{}")
            except json.JSONDecodeError:
                content = {}
            text = str(content.get("text") or material.get("recognize_text") or "")
            if not text:
                continue
            start = float((segment.get("target_timerange") or {}).get("start") or 0) / 1e6
            duration = float((segment.get("target_timerange") or {}).get("duration") or 0) / 1e6
            events.append((start, start + duration, text, content.get("styles") or [],
                           material))
    header = [
        "[Script Info]",
        "ScriptType: v4.00+",
        f"PlayResX: {width}",
        f"PlayResY: {height}",
        "ScaledBorderAndShadow: yes",
        "",
        "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
        "Style: Default,Microsoft YaHei,48,&H00FFFFFF,&H00FFFFFF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,2,0,2,10,10,10,1",
        "",
        "[Events]",
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
    ]
    lines = list(header)
    for start, end, text, styles, material in events:
        base = styles[0] if styles else {}
        chunks = []
        ranges = [item for item in styles if isinstance(item, dict)]
        if not ranges:
            ranges = [{"range": [0, len(text)], **base}]
        cursor = 0
        for item in ranges:
            begin, finish = (item.get("range") or [0, len(text)])[:2]
            begin, finish = max(cursor, int(begin)), min(len(text), int(finish))
            if begin > cursor:
                chunks.append(text[cursor:begin])
            style = []
            fill = (((item.get("fill") or {}).get("content") or {}).get("solid") or {})
            color = fill.get("color")
            if isinstance(color, list) and len(color) >= 3:
                color = "#" + "".join(f"{int(round(c * 255)):02X}" for c in color[:3])
            if color:
                style.append(f"\\c{_color_to_ass(color)}")
            if item.get("size"):
                style.append(f"\\fs{float(item['size']):g}")
            if item.get("bold"):
                style.append("\\b1")
            if item.get("italic"):
                style.append("\\i1")
            if item.get("underline"):
                style.append("\\u1")
            escaped = text[begin:finish].replace("\n", "\\N")
            chunks.append("{" + "".join(style) + "}" + escaped if style else escaped)
            cursor = finish
        if cursor < len(text):
            chunks.append(text[cursor:].replace("\n", "\\N"))
        lines.append("Dialogue: 0,%s,%s,Default,,0,0,0,,%s" % (
            _ass_time(start), _ass_time(end), "".join(chunks)))
    target = media_mod.local_path(out_path, field="ASS 输出路径")
    if target.exists():
        raise SkillError("ASS 输出文件已存在", code="OUTPUT_EXISTS",
                         details={"path": str(target)})
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("\n".join(lines) + "\n", "utf-8-sig")
    return {"out": str(target), "events": len(events), "canvas": {"width": width, "height": height}}
