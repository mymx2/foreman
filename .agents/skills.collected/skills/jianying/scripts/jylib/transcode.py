"""Local ffmpeg transcode for target bitrate (not Jianying native export)."""

from __future__ import annotations

import math
import re
import subprocess
from pathlib import Path

from .errors import SkillError
from . import env as env_mod
from . import media as media_mod

_BITRATE = re.compile(r"^[0-9]+(?:\.[0-9]+)?[kKmM]?$")


def _bitrate(value, field):
    text = str(value or "").strip()
    if not _BITRATE.match(text):
        raise SkillError(f"{field} 必须是数字加可选 k/M 后缀",
                         code="VALIDATION",
                         details={"field": field, "value": value})
    return text


def transcode(input_path, output_path, *, video_bitrate, audio_bitrate="128k",
              fps=None, codec="libx264", preset="medium", timeout=600,
              force=False) -> dict:
    source = media_mod.local_path(input_path, field="输入文件").resolve()
    if not source.is_file():
        raise SkillError("输入文件不存在", code="FILE_NOT_FOUND",
                         details={"path": str(source)})
    target = media_mod.ensure_output_path(output_path, force=force, label="转码输出")
    vbr = _bitrate(video_bitrate, "video-bitrate")
    abr = _bitrate(audio_bitrate, "audio-bitrate")
    if fps is not None:
        try:
            fps_value = float(fps)
        except (TypeError, ValueError):
            raise SkillError("fps 必须是数字", code="VALIDATION",
                             details={"field": "fps", "value": fps})
        if not math.isfinite(fps_value) or fps_value <= 0:
            raise SkillError("fps 必须是正数", code="VALIDATION",
                             details={"field": "fps", "value": fps})
    else:
        fps_value = None

    try:
        tools = env_mod.find_ffmpeg(env_mod.find_install())
    except SkillError:
        tools = env_mod.find_ffmpeg(None)
    # 剪映自带 ffmpeg 是裁剪构建，通常没有 libx264；转码优先用完整用户 ffmpeg。
    try:
        subtitle_ffmpeg = env_mod.subtitle_ffmpeg_info()
    except SkillError:
        subtitle_ffmpeg = {}
    ffmpeg = subtitle_ffmpeg.get("path") or tools.get("ffmpeg")
    if not ffmpeg:
        raise SkillError("没有 ffmpeg，无法转码", code="FFMPEG_MISSING",
                         fix="安装 ffmpeg，或设置 JY_FFMPEG")

    target.parent.mkdir(parents=True, exist_ok=True)
    command = [ffmpeg, "-y" if force else "-n", "-i", str(source),
               "-c:v", str(codec), "-b:v", vbr, "-preset", str(preset),
               "-c:a", "aac", "-b:a", abr, "-movflags", "+faststart"]
    if fps_value is not None:
        command.extend(["-r", f"{fps_value:g}"])
    command.append(str(target))
    try:
        proc = subprocess.run(command, stdin=subprocess.DEVNULL,
                              capture_output=True, text=True, encoding="utf-8",
                              errors="replace", timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        raise SkillError("转码超时", code="TRANSCODE_FAILED",
                         details={"timeout": timeout}) from exc
    except OSError as exc:
        raise SkillError("转码进程启动失败", code="TRANSCODE_FAILED",
                         details={"reason": str(exc)}) from exc
    if proc.returncode != 0 or not target.is_file() or target.stat().st_size <= 0:
        raise SkillError(
            "转码失败",
            code="TRANSCODE_FAILED",
            details={"returncode": proc.returncode,
                     "stderr": (proc.stderr or "").strip()[:500]},
        )
    probe = None
    ffprobe = tools.get("ffprobe")
    if ffprobe:
        try:
            probe = media_mod.probe_summary(ffprobe, target)
        except SkillError:
            probe = None
    return {
        "input": str(source),
        "output": str(target),
        "video_bitrate": vbr,
        "audio_bitrate": abr,
        "fps": fps_value,
        "probe": probe,
        "note": "本命令用本机 ffmpeg 转码，不是剪映原生码率参数",
    }