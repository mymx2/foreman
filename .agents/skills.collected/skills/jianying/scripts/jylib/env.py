"""Discover 剪映, its draft root, the bundled ffmpeg, and the native bridge.

Everything here is read-only. No token, cookie, or account id is ever returned
to the caller; the bridge descriptor's token stays in memory inside Bridge.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from .errors import SkillError

APP_NAME = "JianyingPro"
BRIDGE_NAME = "infinite-canvas-native-bridge.json"

SYSTEM_DRAFT_SUFFIX = Path("User Data") / "Projects" / "com.lveditor.draft"


def is_windows():
    return os.name == "nt"


def _version_key(name):
    parts = []
    for piece in name.replace("-", ".").split("."):
        parts.append(int(piece) if piece.isdigit() else -1)
    return tuple(parts)


def _version_prefix(value):
    parts = [int(piece) for piece in str(value or "").replace("-", ".").split(".")
             if piece.isdigit()]
    return tuple((parts + [0, 0, 0])[:3]) if parts else ()


def _build_number(value):
    tail = str(value or "").strip().rsplit(".", 1)[-1]
    return tail if tail.isdigit() else None


def version_policy(install_version=None):
    """把 install 版本与 references/version.json 的 supported 窗口对照。

    只读；探测失败返回 unknown，不阻断草稿构建，但调用方要把结论标为未验证。
    """
    path = Path(__file__).resolve().parents[2] / "references" / "version.json"
    try:
        data = json.loads(path.read_text("utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return {"status": "unknown", "version_file": str(path),
                "error": str(exc)}
    supported = data.get("supported") or {}
    min_version = str(supported.get("min") or "")
    max_version = str(supported.get("max") or "")
    install_prefix = _version_prefix(install_version)
    min_prefix = _version_prefix(min_version)
    max_prefix = _version_prefix(max_version)
    in_range = bool(install_prefix and min_prefix and max_prefix
                    and min_prefix <= install_prefix <= max_prefix)
    behavior_match = bool(
        install_prefix
        and install_prefix == _version_prefix(data.get("behavior_tested")))
    install_build = _build_number(install_version)
    build_tested = str(data.get("build_tested") or "")
    build_match = (build_tested == install_build) if (build_tested and install_build) else None

    if not install_prefix:
        status = "unknown"
        note = "没有可对照的剪映安装版本"
    elif not in_range:
        status = "unsupported"
        note = f"install {install_version} 超出 supported {min_version}–{max_version}"
    elif behavior_match and build_match is not False:
        status = "verified"
        note = ""
    else:
        status = "unverified"
        note = "install 在 supported 窗口内，但未与 behavior/build 基线精确一致"

    return {
        "version_file": str(path),
        "app_baseline": data.get("app_baseline"),
        "behavior_tested": data.get("behavior_tested"),
        "build_tested": data.get("build_tested"),
        "supported": {"min": min_version, "max": max_version},
        "install_version": install_version,
        "install_build": install_build,
        "in_range": in_range,
        "behavior_match": behavior_match,
        "build_match": build_match,
        "status": status,
        "note": note,
    }


def install_candidates():
    candidates = []
    if is_windows():
        local = os.environ.get("LOCALAPPDATA")
        bases = []
        if local:
            bases.append(Path(local) / APP_NAME / "Apps")
        bases.append(Path.home() / "AppData" / "Local" / APP_NAME / "Apps")
        for base in bases:
            if not base.is_dir():
                continue
            for child in base.iterdir():
                exe = child / "JianyingPro.exe"
                if exe.is_file():
                    candidates.append({"dir": child, "exe": exe, "version": child.name})
    else:
        for app in (Path("/Applications/VideoFusion-macOS.app"),
                    Path("/Applications/剪映专业版.app"),
                    Path.home() / "Applications" / "VideoFusion-macOS.app"):
            if app.is_dir():
                candidates.append({
                    "dir": app,
                    "exe": app / "Contents" / "MacOS" / "VideoFusion-macOS",
                    "version": "macOS",
                })
    return candidates


def find_install():
    candidates = install_candidates()
    if not candidates:
        raise SkillError(
            "找不到剪映专业版安装目录",
            code="INSTALL_NOT_FOUND",
            fix="确认已安装剪映专业版；Windows 默认在 %LOCALAPPDATA%\\JianyingPro\\Apps，"
                "macOS 默认在 /Applications/VideoFusion-macOS.app。",
            details={"platform": "windows" if is_windows() else "macos"},
        )
    candidates.sort(key=lambda item: _version_key(item["version"]), reverse=True)
    return candidates[0]


HASH_CHUNK = 8 * 1024 * 1024


def _sha256_file(path, chunk_size=HASH_CHUNK):
    """流式计算文件 SHA-256；读不了返回 None。

    指纹是附加信息，缺了不阻断主流程，也不要用占位值冒充成功。
    """
    digest = hashlib.sha256()
    try:
        with open(path, "rb") as handle:
            for chunk in iter(lambda: handle.read(chunk_size), b""):
                digest.update(chunk)
    except OSError:
        return None
    return digest.hexdigest()


def install_fingerprint(install):
    """记录安装身份：exe 与 videoeditor*.dll 的 SHA-256。

    只做指纹记录，不做白名单比对——本技能没有 11.8 的可信哈希基线，
    参考仓库的 11.5 白名单在 11.8 上不成立。这里也不读 token / 账号 /
    登录态，指纹里不允许出现任何凭据。
    """
    fingerprint = {"exe_sha256": None, "videoeditor": []}
    if not install:
        return fingerprint
    exe = install.get("exe")
    if exe:
        fingerprint["exe_sha256"] = _sha256_file(exe)
    base = install.get("dir")
    if base:
        try:
            dlls = sorted((path for path in Path(base).glob("videoeditor*.dll")
                           if path.is_file()), key=lambda path: path.name)
        except OSError:
            dlls = []
        fingerprint["videoeditor"] = [{"name": path.name, "sha256": _sha256_file(path)}
                                      for path in dlls]
    return fingerprint


def _temp_dirs():
    seen = []
    for value in (tempfile.gettempdir(), os.environ.get("TEMP"), os.environ.get("TMP"),
                  os.environ.get("TMPDIR"), "/tmp"):
        if not value:
            continue
        path = Path(value)
        if path not in seen:
            seen.append(path)
    return seen


def _pid_alive(pid):
    """True/False，或 None=无法判定（tasklist 不可用）。"""
    try:
        pid = int(pid)
    except (TypeError, ValueError):
        return None
    if pid <= 0:
        return None
    if os.name == "nt":
        try:
            proc = subprocess.run(
                ["tasklist", "/FI", f"PID eq {pid}", "/NH"],
                capture_output=True, text=True, timeout=5)
        except (OSError, subprocess.SubprocessError):
            return None
        if proc.returncode != 0:
            return None
        return str(pid) in (proc.stdout or "")
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return None
    return True


def find_bridge_descriptor():
    best = None
    best_mtime = -1.0
    best_alive = None
    best_alive_mtime = -1.0
    for directory in _temp_dirs():
        path = directory / BRIDGE_NAME
        if not path.is_file():
            continue
        try:
            if path.stat().st_size > 64 * 1024:
                continue
            mtime = path.stat().st_mtime
            data = json.loads(path.read_text("utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            continue
        if not isinstance(data, dict):
            continue
        token = data.get("token")
        if not isinstance(token, str) or not token.strip() or "\r" in token or "\n" in token:
            continue
        try:
            port = int(data.get("port"))
        except (TypeError, ValueError):
            continue
        if not 1 <= port <= 65535:
            continue
        data["port"] = port
        data["_path"] = str(path)
        data["origin"] = f"http://127.0.0.1:{port}"
        if mtime > best_mtime:
            best = data
            best_mtime = mtime
        if _pid_alive(data.get("pid")) is not False and mtime > best_alive_mtime:
            best_alive = data
            best_alive_mtime = mtime
    return best_alive or best


def find_ffmpeg(install=None):
    """Return {'ffmpeg': path|None, 'ffprobe': path|None}; prefers the app bundle."""
    found = {"ffmpeg": None, "ffprobe": None}
    if install:
        base = Path(install["dir"])
        for name in ("ffmpeg.exe", "ffmpeg"):
            if (base / name).is_file():
                found["ffmpeg"] = str(base / name)
                break
        for name in ("ffprobe.exe", "ffprobe"):
            if (base / name).is_file():
                found["ffprobe"] = str(base / name)
                break
        runtime = base / "Resources" / "agent_runtime_env" / "bin"
        if found["ffprobe"] is None and (runtime / "ffprobe.exe").is_file():
            found["ffprobe"] = str(runtime / "ffprobe.exe")
    for key, names in (("ffmpeg", ("ffmpeg", "ffmpeg.exe")),
                       ("ffprobe", ("ffprobe", "ffprobe.exe"))):
        if found[key] is None:
            found[key] = shutil.which(names[0]) or shutil.which(names[1])
    return found


def draft_root_candidates():
    candidates = []
    if is_windows():
        local = os.environ.get("LOCALAPPDATA")
        if local:
            candidates.append(Path(local) / APP_NAME / SYSTEM_DRAFT_SUFFIX)
        candidates.append(Path.home() / "AppData" / "Local" / APP_NAME / SYSTEM_DRAFT_SUFFIX)
    else:
        candidates.append(Path.home() / "Movies" / "JianyingPro" / SYSTEM_DRAFT_SUFFIX)
    return candidates


def find_draft_root():
    env = os.environ.get("JIANYING_DRAFT_ROOT")
    if env:
        path = Path(env).expanduser()
        if (path / "root_meta_info.json").is_file():
            return path
    for path in draft_root_candidates():
        if (path / "root_meta_info.json").is_file():
            return path
    for path in draft_root_candidates():
        if path.is_dir():
            return path
    return None


def find_cache_root():
    if is_windows():
        local = os.environ.get("LOCALAPPDATA")
        base = Path(local) if local else Path.home() / "AppData" / "Local"
        return base / APP_NAME / "User Data" / "Cache"
    return Path.home() / "Movies" / "JianyingPro" / "User Data" / "Cache"


def official_cli_paths(install):
    if not install:
        return {}
    base = Path(install["dir"])
    runtime = base / "Resources" / "agent_runtime_env" / "bin"
    return {
        "jianying-agent-cli": str(base / "jianying-agent-cli.exe")
        if (base / "jianying-agent-cli.exe").is_file() else None,
        "lyra-cli": str(base / "lyra-cli.exe") if (base / "lyra-cli.exe").is_file() else None,
        "canvas-draft": str(runtime / "canvas-draft.exe")
        if (runtime / "canvas-draft.exe").is_file() else None,
        "agent_runtime": str(runtime) if runtime.is_dir() else None,
    }


def count_packages(cache_root):
    if not cache_root or not cache_root.is_dir():
        return {}
    counts = {}
    for key in ("effect", "artistEffect", "music", "template"):
        path = cache_root / key
        if path.is_dir():
            try:
                counts[key] = sum(1 for child in path.iterdir() if child.is_dir())
            except OSError:
                counts[key] = None
    return counts


def bundled_python(install):
    if not install:
        return None
    path = (Path(install["dir"]) / "Resources" / "agent_runtime_env" / "cli"
            / "python" / "python.exe")
    return str(path) if path.is_file() else None


def subtitle_ffmpeg_info():
    """字幕烧录用的 ffmpeg 选择结果；只读探测，不启动剪映。"""
    try:
        from subtitles import jy_common

        resolved = jy_common.resolve_ffmpeg()
    except Exception as exc:
        return {"error": str(exc)[:200]}
    chosen = resolved.get("chosen") or {}
    return {
        "path": chosen.get("path"),
        "source": chosen.get("source"),
        "version": chosen.get("version"),
        "subtitle_burn_in": bool(chosen.get("subtitle_burn_in")),
        "libass": bool(chosen.get("libass")),
        "libx264": bool(chosen.get("libx264")),
        "burn_in_available": bool(resolved.get("burn_in_available")),
        "warnings": resolved.get("warnings") or [],
    }


def probe():
    result = {"platform": "windows" if is_windows() else "macos"}
    install = None
    try:
        install = find_install()
        # 指纹要读 exe（几十 MB），probe 会慢一点；不做缓存，避免读到重启后
        # 已被替换的安装。仍然只读，不启动剪映。
        result["install"] = {"dir": str(install["dir"]), "version": install["version"],
                             "exe": str(install["exe"]),
                             **install_fingerprint(install)}
    except SkillError as exc:
        result["install"] = {"error": exc.message}

    descriptor = find_bridge_descriptor()
    if descriptor:
        result["bridge"] = {
            "descriptor": descriptor["_path"],
            "port": int(descriptor["port"]),
            "pid": descriptor.get("pid"),
            "app": descriptor.get("app"),
            "version": descriptor.get("version"),
        }
    else:
        result["bridge"] = {"found": False, "descriptor_name": BRIDGE_NAME}

    root = find_draft_root()
    result["draft_root"] = {"path": str(root) if root else None,
                            "exists": bool(root and root.is_dir()),
                            "index": bool(root and (root / "root_meta_info.json").is_file())}

    tools = find_ffmpeg(install)
    result["ffmpeg"] = tools
    result["subtitle_ffmpeg"] = subtitle_ffmpeg_info()
    # executable = 当前运行本技能的解释器（PYTHON 环境变量优先）；
    # bundled 才是剪映自带解释器，两者不要混用。
    result["python"] = {"bundled": bundled_python(install),
                        "executable": os.environ.get("PYTHON") or sys.executable}

    result["official_cli"] = official_cli_paths(install)

    cache = find_cache_root()
    result["cache"] = {"root": str(cache), "exists": cache.is_dir(),
                       "packages": count_packages(cache)}
    result["docs"] = version_policy((result.get("install") or {}).get("version"))
    return result
