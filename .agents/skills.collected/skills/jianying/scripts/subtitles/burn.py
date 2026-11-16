"""burn：把 SRT 烧进画面（硬字幕）。

前置：必须存在带 libass 的 ffmpeg。drawtext 不能替代 subtitles= 滤镜；
剪映自带的 ffmpeg 没有 libass，且无 libx264，只能封装字幕轨，不能烧录。
脚本先检测，不满足直接失败。

安全约定：
- 不覆盖用户任何文件：--out 必须不存在（out-exists 拒绝），临时字幕用 mkstemp 随机名，跑完删除
- 烧录前校验 SRT 是否落在视频时长内，越界条数写进结果
- 产物复核：时长漂移超过 1 帧当量即标记 drift_ok=false；无法复核时也标记 false

用法：
    python scripts/burn.py --video in.mp4 --srt a.srt --out out.mp4
    python scripts/burn.py --video in.mp4 --srt a.srt --out out.mp4 --font "Microsoft YaHei" --size 22
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import jy_common as C
from srt import SrtError, cue_issues, read_srt

DRIFT_LIMIT = 0.05  # 秒；30fps 下约 1.5 帧，60fps 下 3 帧
UNSAFE_FONT = re.compile(r"['\",:;=\\\[\]]")
SAFE_SRT_NAME_CHARS = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-")


def needs_temp_copy(name: str) -> bool:
    """libass 对路径特殊字符敏感；文件名含空格或非白名单字符时需临时复制。"""
    return not set(name) <= SAFE_SRT_NAME_CHARS or " " in name


def _cue_error(cues: list[dict]) -> tuple[str, str, str] | None:
    """烧录前复用 srt.check 的时间码/时长子集；重叠 cue 合法，不在这里拒。"""
    _ordered, issues = cue_issues(cues, check_overlap=False)
    if issues:
        return ("srt-invalid", f"{len(issues)} 处字幕时间码/时长问题",
                "; ".join(issues[:5]))
    return None


def _fail(code: str, detail: str, hint: str = "") -> int:
    C.emit(C.fail("burn", code, detail, hint=hint))
    return 1


def _capability_error(chosen: dict):
    """返回 (code, detail, hint) 或 None。烧录用 subtitles= 滤镜，只认 libass。"""
    if not chosen.get("usable"):
        return ("ffmpeg-missing", "未找到可用的 ffmpeg",
                "安装 ffmpeg 或设置 JY_FFMPEG")
    if not chosen.get("libass"):
        source = chosen.get("source") or "ffmpeg"
        return ("ffmpeg-missing-capability",
                f"{source} 缺少 libass；drawtext 不能替代 subtitles= 滤镜",
                "装带 libass 的外部 ffmpeg 并设置 JY_FFMPEG；剪映自带的不能用于烧录")
    return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--video", required=True)
    ap.add_argument("--srt", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--font", default="Microsoft YaHei", help="字体族名，用英文名更稳")
    ap.add_argument("--size", type=int, default=22)
    ap.add_argument("--crf", type=int, default=20)
    ap.add_argument("--allow-out-of-range", action="store_true",
                    help="允许末条字幕超出视频时长（超出部分不会显示）")
    args = ap.parse_args()

    if not 6 <= args.size <= 200:
        return _fail("bad-size", f"--size 应在 6–200 之间，收到 {args.size}")
    if not 0 <= args.crf <= 51:
        return _fail("bad-crf", f"--crf 应在 0–51 之间，收到 {args.crf}")
    if UNSAFE_FONT.search(args.font):
        return _fail("bad-font", "字体名含引号/逗号/冒号/分号/等号等特殊字符，会破坏滤镜串",
                     hint="用族名，例如 Microsoft YaHei / Source Han Sans SC")

    try:
        video = C.local_path(args.video, field="视频路径")
        srt = C.local_path(args.srt, field="字幕路径")
        out = C.local_path(args.out, field="输出路径")
    except C.MediaError as exc:
        return _fail(exc.code, exc.detail, exc.hint)
    for p, label in ((video, "视频"), (srt, "字幕")):
        if not p.is_file():
            return _fail("file-not-found", f"{label}文件不存在: {p}")
    try:
        if out.exists():
            return _fail("out-exists", f"输出文件已存在: {out}",
                         hint="换一个 --out 路径；本技能不覆盖已有文件")
        ro = out.resolve()
        for p, label in ((video, "输入视频"), (srt, "字幕文件")):
            if ro == p.resolve():
                return _fail("out-is-input", f"输出路径与{label}相同，会覆盖原文件",
                             hint="换一个 --out 路径")
    except OSError as exc:
        return _fail("io-error", f"无法解析输出路径: {exc}")

    ff = C.resolve_ffmpeg()
    chosen = ff.get("chosen") or {}
    problem = _capability_error(chosen)
    if problem:
        return _fail(*problem)

    try:
        cues = read_srt(srt)
    except SrtError as exc:
        return _fail(exc.code, exc.detail, exc.hint)

    problem = _cue_error(cues)
    if problem:
        return _fail(*problem)

    try:
        video_dur = C.media_duration(video)
    except C.MediaError as exc:
        return _fail(exc.code, exc.detail, exc.hint)

    # 按"终点是否超出"统计截断，而不是只看起点
    fully_in = [c for c in cues if c["end"] <= video_dur + 1e-6]
    truncated = [c for c in cues if c["start"] < video_dur and c["end"] > video_dur + 1e-6]
    outside = [c for c in cues if c["start"] >= video_dur]
    if (truncated or outside) and not args.allow_out_of_range:
        return _fail("srt-out-of-range",
                     f"{len(truncated)} 条被截断、{len(outside)} 条完全在外（视频 {video_dur:.2f}s）",
                     hint="截短字幕，或加 --allow-out-of-range 强制烧录（超出部分不会显示）")
    if not fully_in and not truncated:
        return _fail("srt-no-visible-cues",
                     f"全部 {len(cues)} 条字幕都在视频时长 {video_dur:.2f}s 之外，烧录后没有任何字幕可见",
                     hint="检查 SRT 时间码，或用 srt.from-audio 重新生成；--allow-out-of-range 不能救这种情况")

    # libass 对特殊字符路径敏感：不安全时复制成随机名临时文件（不覆盖同名文件）。
    # 校验整个文件名（含扩展名），不只是 stem——扩展名里的 : ; ' [ 同样会破坏滤镜串。
    tmp_path: Path | None = None
    srt_name = srt.name
    if needs_temp_copy(srt.name):
        try:
            fd, tmp_name = tempfile.mkstemp(prefix="_jy_burn_", suffix=".srt", dir=str(srt.parent))
            os.close(fd)
            tmp_path = Path(tmp_name)
            tmp_path.write_bytes(srt.read_bytes())
        except OSError as exc:
            return _fail("temp-srt-failed", f"无法创建临时字幕: {exc}",
                         hint="检查字幕所在目录的写权限")
        srt_name = tmp_path.name

    style = f"FontName={args.font},FontSize={args.size},Outline=2,MarginV=24"
    vf = f"subtitles={srt_name}:force_style='{style}'"
    cmd = [chosen["path"], "-y", "-hide_banner", "-loglevel", "error",
           "-i", str(video.resolve()), "-vf", vf,
           "-c:v", "libx264", "-crf", str(args.crf), "-preset", "medium",
           "-c:a", "copy", str(out.resolve())]

    try:
        proc = subprocess.run(cmd, cwd=str(srt.parent), capture_output=True,
                              text=True, encoding="utf-8", errors="replace", timeout=3600)
    except subprocess.TimeoutExpired:
        return _fail("ffmpeg-timeout", "ffmpeg 超过 1 小时未完成，已中断")
    except OSError as exc:
        return _fail("ffmpeg-start-failed", f"{type(exc).__name__}: {exc}")
    finally:
        if tmp_path and tmp_path.exists():
            try:
                tmp_path.unlink()
            except OSError:
                pass

    if proc.returncode != 0:
        first = (proc.stderr or "").strip().splitlines()
        return _fail("ffmpeg-failed", first[0][:300] if first else "ffmpeg 失败",
                     hint="确认字体族名存在、--size 合理，字幕时间码在视频范围内")
    try:
        if not out.is_file() or out.stat().st_size == 0:
            return _fail("output-empty", "ffmpeg 退出码为 0 但产物为空")
    except OSError as exc:
        return _fail("io-error", f"无法检查产物: {exc}")

    try:
        out_dur = C.media_duration(out)
    except C.MediaError:
        out_dur = None
    drift = None if out_dur is None else round(out_dur - video_dur, 3)
    drift_ok = drift is not None and abs(drift) <= DRIFT_LIMIT

    hints = []
    if drift is None:
        hints.append("无法复核产物时长（ffprobe 不可用或产物不可解析），drift 未验证，请人工核对产物")
    elif not drift_ok:
        hints.append(f"产物时长与源视频差 {drift:+.3f}s，超过 {DRIFT_LIMIT}s，建议抽帧核对")
    if truncated:
        hints.append(f"{len(truncated)} 条字幕被视频结尾截断")
    if outside:
        hints.append(f"{len(outside)} 条字幕完全在视频之外，未渲染")
    if ff.get("warnings"):
        hints.extend(ff["warnings"])

    C.emit(C.ok("burn", {
        "out": str(out),
        "bytes": out.stat().st_size,
        "size_human": C.human_bytes(out.stat().st_size),
        "video_seconds": round(video_dur, 3),
        "output_seconds": None if out_dur is None else round(out_dur, 3),
        "duration_drift": drift,
        "drift_ok": drift_ok,
        "cues": len(cues),
        "cues_fully_visible": len(fully_in),
        "cues_truncated": len(truncated),
        "cues_outside": len(outside),
        "font": args.font,
        "ffmpeg": chosen.get("source"),
        "ffmpeg_warnings": ff.get("warnings") or [],
        "note": "字体族名不存在时 libass 会静默换默认字体：必须抽一帧确认字幕位置与字形后再交付",
    }, evidence={"ffmpeg": chosen["path"], "out": str(out)},
        hint="；".join(hints)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
