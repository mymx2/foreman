"""ffprobe/ffmpeg helpers used for planning and for proving the render."""

from __future__ import annotations

import json
import math
import os
import re
import shutil
import stat
import subprocess
from contextlib import contextmanager
from fractions import Fraction
from pathlib import Path

from .errors import SkillError

IMAGE_EXT = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tif", ".tiff", ".gif"}
_REMOTE_SCHEME = re.compile(r"^[A-Za-z][A-Za-z0-9+.-]*://")
_DRIVE_REMOTE = 4  # GetDriveTypeW(DRIVE_REMOTE)
_REPARSE_POINT = 0x0400  # FILE_ATTRIBUTE_REPARSE_POINT
_REPARSE_MOUNT = 0xA0000003  # IO_REPARSE_TAG_MOUNT_POINT（junction）
_REPARSE_SYMLINK = 0xA000000C  # IO_REPARSE_TAG_SYMLINK


def _is_link_stat(info):
    """lstat 结果本身是不是链接/重解析点（不跟随）。

    有 ``st_reparse_tag`` 时只拒绝目录联接与符号链接：OneDrive 等云占位
    也带重解析属性，按属性位一刀切会把正常云文件误判成缺失。
    """
    if stat.S_ISLNK(info.st_mode):
        return True
    tag = getattr(info, "st_reparse_tag", 0)
    if tag:
        return tag in (_REPARSE_MOUNT, _REPARSE_SYMLINK)
    return bool(getattr(info, "st_file_attributes", 0) & _REPARSE_POINT)


def _has_link_ancestor(target):
    """祖先目录里只要有一个是指向别处的 junction/符号链接，就不算普通路径。"""
    for parent in Path(target).parents:
        try:
            info = parent.lstat()
        except FileNotFoundError:
            continue
        except OSError:
            return True
        if _is_link_stat(info):
            return True
    return False


def _plain_path(path, *, want_dir):
    target = Path(path)
    try:
        info = target.lstat()
    except OSError:
        return False
    if _is_link_stat(info) or _has_link_ancestor(target):
        return False
    return target.is_dir() if want_dir else target.is_file()


def is_plain_file(path):
    """普通文件：存在，且自身与祖先目录都不是符号链接/junction（不跟随链接）。

    ``local_path`` 只能挡字符串形态的 UNC/网络盘，挡不住本机 junction
    指向 ``\\\\host\\share``——``is_file()`` 会先跟随链接，从而发起 SMB/NTLM
    探测。这里只做 ``lstat``，既不跟随目标，也不跟随祖先目录。
    """
    return _plain_path(path, want_dir=False)


def is_plain_dir(path):
    """普通目录：存在，且自身与祖先目录都不是符号链接/junction。"""
    return _plain_path(path, want_dir=True)


def iter_plain_files(root, *, recursive=True):
    """逐层列出普通文件；进入子目录前先 lstat，链接/junction 一律不跟随。"""
    pending = [Path(root)]
    while pending:
        current = pending.pop()
        try:
            with os.scandir(current) as entries:
                for entry in entries:
                    try:
                        info = entry.stat(follow_symlinks=False)
                    except OSError:
                        continue
                    if _is_link_stat(info):
                        continue
                    if entry.is_dir(follow_symlinks=False):
                        if recursive:
                            pending.append(Path(entry.path))
                    elif entry.is_file(follow_symlinks=False):
                        yield Path(entry.path)
        except OSError:
            continue


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


def _extended(path):
    """Windows long-path prefix; other platforms return the path unchanged."""
    if os.name != "nt":
        return str(path)
    text = str(path)
    if text.startswith("\\\\?\\"):
        return text
    return "\\\\?\\" + os.path.abspath(text)


if os.name == "nt":
    import ctypes
    import msvcrt
    from ctypes import wintypes

    _GENERIC_READ = 0x80000000
    _FILE_SHARE_READ = 0x00000001
    _OPEN_EXISTING = 3
    _FILE_FLAG_OPEN_REPARSE_POINT = 0x00200000
    _FILE_FLAG_BACKUP_SEMANTICS = 0x02000000
    _FILE_ATTRIBUTE_REPARSE_POINT = 0x0400
    _FILE_ATTRIBUTE_DIRECTORY = 0x0010
    _INVALID_HANDLE = ctypes.c_void_p(-1).value

    class _BY_HANDLE_FILE_INFORMATION(ctypes.Structure):
        _fields_ = [
            ("dwFileAttributes", wintypes.DWORD),
            ("ftCreationTime", wintypes.FILETIME),
            ("ftLastAccessTime", wintypes.FILETIME),
            ("ftLastWriteTime", wintypes.FILETIME),
            ("dwVolumeSerialNumber", wintypes.DWORD),
            ("nFileSizeHigh", wintypes.DWORD),
            ("nFileSizeLow", wintypes.DWORD),
            ("nNumberOfLinks", wintypes.DWORD),
            ("nFileIndexHigh", wintypes.DWORD),
            ("nFileIndexLow", wintypes.DWORD),
        ]

    _kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    _CreateFileW = _kernel32.CreateFileW
    _CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
                             wintypes.LPVOID, wintypes.DWORD, wintypes.DWORD,
                             wintypes.HANDLE]
    _CreateFileW.restype = wintypes.HANDLE
    _GetFileInformationByHandle = _kernel32.GetFileInformationByHandle
    _GetFileInformationByHandle.argtypes = [
        wintypes.HANDLE, ctypes.POINTER(_BY_HANDLE_FILE_INFORMATION)]
    _GetFileInformationByHandle.restype = wintypes.BOOL
    _CloseHandle = _kernel32.CloseHandle
    _CloseHandle.argtypes = [wintypes.HANDLE]
    _CloseHandle.restype = wintypes.BOOL

    def _win_open_plain(path):
        handle = _CreateFileW(
            _extended(path), _GENERIC_READ, _FILE_SHARE_READ, None,
            _OPEN_EXISTING,
            _FILE_FLAG_OPEN_REPARSE_POINT | _FILE_FLAG_BACKUP_SEMANTICS, None)
        raw = handle if isinstance(handle, int) else getattr(handle, "value", 0)
        if not raw or raw == _INVALID_HANDLE:
            raise OSError(ctypes.get_last_error(), f"无法打开 {path}")
        info = _BY_HANDLE_FILE_INFORMATION()
        if not _GetFileInformationByHandle(handle, ctypes.byref(info)):
            err = ctypes.get_last_error()
            _CloseHandle(handle)
            raise OSError(err, f"无法读取文件属性 {path}")
        if info.dwFileAttributes & (_FILE_ATTRIBUTE_REPARSE_POINT
                                    | _FILE_ATTRIBUTE_DIRECTORY):
            _CloseHandle(handle)
            raise OSError(0, f"不是普通文件: {path}")
        return handle


@contextmanager
def open_plain(path):
    """打开普通文件；打开瞬间不跟随链接，并在持有期间禁止替换/删除。

    Windows 用 ``FILE_FLAG_OPEN_REPARSE_POINT`` + 不含 DELETE 的共享模式；
    句柄持有到调用方结束，检查与读取之间不再留文件级替换窗口。
    POSIX 用 ``O_NOFOLLOW`` + fstat 做到打开时校验（无法阻止持有后 rename）。
    """
    path = Path(path)
    if os.name == "nt":
        handle = _win_open_plain(path)
        raw = handle if isinstance(handle, int) else getattr(handle, "value", 0)
        try:
            fd = msvcrt.open_osfhandle(raw, os.O_RDONLY | os.O_BINARY)
        except OSError:
            _CloseHandle(handle)
            raise
        fh = os.fdopen(fd, "rb")
        try:
            yield fh
        finally:
            fh.close()
        return
    fd = os.open(str(path), os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode):
            raise OSError(f"不是普通文件: {path}")
    except BaseException:
        os.close(fd)
        raise
    with os.fdopen(fd, "rb") as fh:
        yield fh


@contextmanager
def hold_plain_file(path):
    with open_plain(path):
        yield Path(path)


def read_plain_bytes(path):
    with open_plain(path) as fh:
        return fh.read()


def copy_tree(src, dst):
    """Copy a draft tree without recreating empty placeholder directories.

    ``shutil.copytree`` creates every directory, including empty
    ``##_draftpath_placeholder_*`` subtrees. On Windows those can exceed the
    260-character legacy path limit and raise ``WinError 3`` even though the
    directory is empty. Empty directories carry no draft data, so this helper
    only creates directories on demand for files and uses the extended-length
    prefix for both source and destination.
    """
    src = Path(src)
    dst = Path(dst)
    os.makedirs(_extended(dst), exist_ok=True)
    for root, dirs, files in os.walk(src):
        kept = []
        for name in dirs:
            try:
                info = (Path(root) / name).lstat()
            except OSError:
                continue
            if not _is_link_stat(info):
                kept.append(name)
        dirs[:] = kept
        rel = os.path.relpath(root, src)
        target_root = dst if rel == "." else dst / rel
        for name in files:
            try:
                info = (Path(root) / name).lstat()
            except OSError:
                continue
            if _is_link_stat(info):
                continue
            os.makedirs(_extended(target_root), exist_ok=True)
            source = Path(root) / name
            destination = target_root / name
            with open_plain(source) as fsrc, \
                    open(_extended(destination), "wb") as fdst:
                shutil.copyfileobj(fsrc, fdst)
            shutil.copystat(_extended(source), _extended(destination))
    return dst


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
    target = local_path(path, field="媒体文件")
    if not is_plain_file(target):
        raise SkillError("素材文件不存在", code="MEDIA_NOT_FOUND",
                         details={"path": str(target)})
    target = target.resolve()
    try:
        with hold_plain_file(target):
            done = _run([ffprobe, "-v", "error", "-show_format", "-show_streams",
                         "-of", "json", str(target)], timeout=60)
    except OSError as exc:
        raise SkillError("素材文件在读取前发生变化，已拒绝",
                         code="MEDIA_NOT_FOUND",
                         details={"path": str(target), "reason": str(exc)}) from exc
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
    out = local_path(path, field=label)
    if _has_link_ancestor(out):
        raise SkillError(f"{label} 位于链接目录下，拒绝写入", code="UNSAFE_PATH",
                         details={"path": str(out)},
                         fix="把输出改到本地普通目录。")
    try:
        info = out.lstat()
    except OSError:
        info = None
    if info is not None and _is_link_stat(info):
        raise SkillError(f"{label} 是链接/重解析点，拒绝写入", code="UNSAFE_PATH",
                         details={"path": str(out)},
                         fix="换一个普通文件路径。")
    out = out.resolve()
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
    video_path = local_path(video, field="视频文件")
    if not is_plain_file(video_path):
        raise SkillError("抽帧素材不存在或是链接路径", code="MEDIA_NOT_FOUND",
                         details={"path": str(video_path)})
    video_path = video_path.resolve()
    out = ensure_output_path(output, force=force, label="抽帧文件")
    out.parent.mkdir(parents=True, exist_ok=True)
    try:
        with hold_plain_file(video_path):
            done = _run([ffmpeg, "-y", "-loglevel", "error", "-ss", f"{at_seconds:.3f}",
                         "-i", str(video_path),
                         "-frames:v", "1", "-update", "1", str(out)], timeout=120)
    except OSError as exc:
        raise SkillError("抽帧素材在读取前发生变化，已拒绝",
                         code="MEDIA_NOT_FOUND",
                         details={"path": str(video_path), "reason": str(exc)}) from exc
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
