"""ffprobe/ffmpeg helpers used for planning and for proving the render."""

from __future__ import annotations

import json
import math
import os
import re
import subprocess
from fractions import Fraction
from pathlib import Path

from .errors import SkillError

IMAGE_EXT = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tif", ".tiff", ".gif"}
_REMOTE_SCHEME = re.compile(r"^[A-Za-z][A-Za-z0-9+.-]*://")
_DRIVE_REMOTE = 4  # GetDriveTypeW(DRIVE_REMOTE)


def _is_remote_drive(text):
    """映射网络盘在字符串上看仍是本地盘符，必须问 Windows 盘类型。"""
    if os.name != "nt":
        return False
    drive = os.path.splitdrive(str(text))[0]
    if not drive:
        return False
    try:
        import ctypes
        return ctypes.windll.kernel32.GetDriveTypeW(drive + "\\") == _DRIVE_REMOTE
    except Exception:
        return False


def local_path(value, *, field="path"):
    """Reject UNC/network/URL paths before any filesystem probe.

    Windows resolves ``\\\\host\\share`` through SMB and may send NTLM
    credentials before a media file is even validated. The skill only accepts
    local disk paths; callers that need a remote asset must download it first.
    """
    text = str(value).strip()
    if not text:
        raise SkillError(f"{field} 不能为空", code="VALIDATION",
                         details={"field": field})
    lowered = text.lower()
    if (text.startswith(("\\\\", "//")) or lowered.startswith("file:")
            or _REMOTE_SCHEME.match(text)):
        raise SkillError(
            f"{field} 必须是本地路径，不接受 UNC、网络盘或 URL",
            code="UNSAFE_PATH",
            details={"field": field, "path": text},
            fix="先把素材下载到本地磁盘，再用本地绝对或相对路径。",
        )
    drive = os.path.splitdrive(text)[0]
    if drive and not os.path.isabs(text):
        raise SkillError(
            f"{field} 不能使用盘符相对路径（如 C:foo）",
            code="UNSAFE_PATH",
            details={"field": field, "path": text},
            fix="改用绝对路径，或相对计划文件的普通相对路径。",
        )
    if _is_remote_drive(text):
        raise SkillError(
            f"{field} 不能使用映射网络盘",
            code="UNSAFE_PATH",
            details={"field": field, "path": text},
            fix="先把素材复制到本地磁盘，再用本地路径。",
        )
    return Path(text).expanduser()


def validate_timestamp(value, field="time"):
    """Reject NaN/inf/negative timestamps before they become ffmpeg arguments."""
    try:
        number = float(value)
    except (TypeError, ValueError):
        raise SkillError(f"{field} 必须是数字", code="VALIDATION",
                         details={"field": field, "value": value}) from None
    if not math.isfinite(number) or number < 0:
        raise SkillError(f"{field} 必须是 ≥ 0 的有限秒数", code="VALIDATION",
                         details={"field": field, "value": value})
    return number


def _run(cmd, timeout=60):
    try:
        return subprocess.run(
            cmd, stdin=subprocess.DEVNULL, capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=timeout,
        )
    except FileNotFoundError as exc:
        raise SkillError("媒体工具可执行文件不存在", code="PROBE_FAILED",
                         details={"tool": cmd[0], "reason": str(exc)}) from exc
    except subprocess.TimeoutExpired as exc:
        raise SkillError("媒体工具调用超时", code="PROBE_FAILED",
                         details={"tool": cmd[0], "timeout": timeout}) from exc


def probe_media(ffprobe, path):
    if not ffprobe:
        raise SkillError("没有 ffprobe，无法读取素材信息",
                         code="FFPROBE_MISSING",
                         fix="安装 ffmpeg，或使用剪映安装目录自带的 ffprobe。")
    target = local_path(path, field="媒体文件").resolve()
    if not target.is_file():
        raise SkillError("素材文件不存在", code="MEDIA_NOT_FOUND",
                         details={"path": str(target)})
    done = _run([ffprobe, "-v", "error", "-show_format", "-show_streams",
                 "-of", "json", str(target)], timeout=60)
    if done.returncode != 0:
        raise SkillError(
            "ffprobe 读不了这个文件",
            code="MEDIA_UNREADABLE",
            details={"path": str(target), "stderr": done.stderr.strip()[:400]},
            fix="确认文件没有损坏，格式受支持（mp4/mov/png/jpg/mp3/wav/aac/m4a）。",
        )
    try:
        payload = json.loads(done.stdout or "{}")
    except json.JSONDecodeError as exc:
        raise SkillError("ffprobe 输出不是合法 JSON", code="PROBE_FAILED",
                         details={"path": str(target),
                                  "stdout": (done.stdout or "")[:300]}) from exc
    streams = payload.get("streams") or []
    video = next((s for s in streams if s.get("codec_type") == "video"), None)
    audio = next((s for s in streams if s.get("codec_type") == "audio"), None)
    fmt = payload.get("format") or {}
    duration = 0.0
    try:
        duration = float(fmt.get("duration") or 0.0)
    except (TypeError, ValueError):
        duration = 0.0
    if duration <= 0 and video:
        try:
            duration = float(video.get("duration") or 0.0)
        except (TypeError, ValueError):
            duration = 0.0
    fps = 0.0
    if video and video.get("r_frame_rate"):
        try:
            fps = float(Fraction(video["r_frame_rate"]))
        except (ZeroDivisionError, ValueError):
            fps = 0.0
    suffix = target.suffix.lower()
    kind = "audio"
    if video:
        kind = "image" if (suffix in IMAGE_EXT and duration <= 0.05) else "video"
        if suffix in IMAGE_EXT and video.get("codec_name") in {"png", "mjpeg", "bmp", "gif"}:
            kind = "image"
    return {
        "path": str(target),
        "name": target.name,
        "kind": kind,
        "duration": round(duration, 6),
        "width": int(video.get("width") or 0) if video else 0,
        "height": int(video.get("height") or 0) if video else 0,
        "fps": round(fps, 3),
        "has_video": bool(video),
        "has_audio": bool(audio),
        "codec": (video or audio or {}).get("codec_name"),
    }


def probe_summary(ffprobe, path):
    """Small subset for verifying an exported file."""
    info = probe_media(ffprobe, path)
    return {
        "path": info["path"],
        "bytes": Path(info["path"]).stat().st_size,
        "duration": info["duration"],
        "width": info["width"],
        "height": info["height"],
        "fps": info["fps"],
        "video_codec": info["codec"] if info["has_video"] else None,
        "audio": info["has_audio"],
    }


def ensure_output_path(path, *, force=False, label="输出文件"):
    """拒绝静默覆盖。返回绝对 Path；确需覆盖时调用方显式传 force=True。"""
    out = local_path(path, field=label).resolve()
    if out.exists() and not force:
        raise SkillError(
            f"{label}已存在：{out}",
            code="OUTPUT_EXISTS",
            details={"path": str(out)},
            fix="换一个新的输出路径；确需覆盖时显式加 --force。",
        )
    return out


def extract_frame(ffmpeg, video, at_seconds, output, *, force=False):
    if not ffmpeg:
        raise SkillError("没有 ffmpeg，无法抽帧", code="FFMPEG_MISSING",
                         fix="安装 ffmpeg，或使用剪映安装目录自带的 ffmpeg。")
    at_seconds = validate_timestamp(at_seconds, "at")
    video_path = local_path(video, field="视频文件").resolve()
    out = ensure_output_path(output, force=force, label="抽帧文件")
    out.parent.mkdir(parents=True, exist_ok=True)
    done = _run([ffmpeg, "-y", "-loglevel", "error", "-ss", f"{at_seconds:.3f}",
                 "-i", str(video_path),
                 "-frames:v", "1", "-update", "1", str(out)], timeout=120)
    if done.returncode != 0 or not out.is_file() or out.stat().st_size <= 0:
        raise SkillError(
            "抽帧失败",
            code="FRAME_FAILED",
            details={"at": at_seconds, "stderr": done.stderr.strip()[:400]},
            fix="确认时间点在成片时长内。",
        )
    return str(out)


def extract_frames(ffmpeg, video, times, outdir, prefix="frame", *, force=False):
    times = [validate_timestamp(value, "frames") for value in times]
    outdir = local_path(outdir, field="抽帧目录").resolve()
    outdir.mkdir(parents=True, exist_ok=True)
    results = []
    for index, at in enumerate(times):
        name = f"{prefix}_{index:02d}_{at:.3f}s.png"
        results.append(extract_frame(ffmpeg, video, at, outdir / name, force=force))
    return results
