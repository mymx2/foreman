"""jianying 技能公共层：路径解析、ffmpeg 选择、JSON 信封、草稿索引。

设计约束：
- 只依赖标准库（脚本要能在任何装了 Python 3.9+ 的机器上跑）
- 所有输出走单行 JSON，便于 Agent 解析
- 除显式产物外不做写操作
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

LOCALAPPDATA = Path(os.environ.get("LOCALAPPDATA", str(Path.home() / "AppData" / "Local")))
APP_ROOT = LOCALAPPDATA / "JianyingPro"
APPS_DIR = APP_ROOT / "Apps"
USER_DATA = APP_ROOT / "User Data"
DRAFT_ROOT = USER_DATA / "Projects" / "com.lveditor.draft"
RECYCLE_BIN = DRAFT_ROOT / ".recycle_bin"
ROOT_META = DRAFT_ROOT / "root_meta_info.json"

# ffmpeg 搜索顺序：显式环境变量 → 用户目录常见位置 → PATH → 剪映自带（能力受限）
# 不扫描盘符根目录（如 C:\、D:\）：这些位置可能被其他本地用户写入。
FFMPEG_ENV = "JY_FFMPEG"
FFMPEG_CANDIDATES = [
    Path.home() / ".local" / "tools" / "ffmpeg" / "bin" / "ffmpeg.exe",
    LOCALAPPDATA / "ffmpeg" / "bin" / "ffmpeg.exe",
]

# 烧字幕相关能力：按"实际是否存在"探测，不靠 configuration 字符串猜
CAPABILITY_FILTERS = {"libass": "subtitles", "drawtext": "drawtext"}
CAPABILITY_ENCODERS = {"libx264": "libx264", "libx265": "libx265"}
FILTER_ROW = re.compile(r"^\s*\S{1,6}\s+([A-Za-z0-9_]+)\s+\S+->\S+")
ENCODER_ROW = re.compile(r"^\s*\S{1,6}\s+([A-Za-z0-9_]+)\s+\S+")


def filter_names(output: str) -> set[str]:
    """只取 ffmpeg -filters 的滤镜名列，避免把描述里的词当成滤镜名。"""
    names = set()
    for line in output.splitlines():
        match = FILTER_ROW.match(line)
        if match:
            names.add(match.group(1))
    return names


def encoder_names(output: str) -> set[str]:
    """只取 ffmpeg -encoders 的编码器名列，避免 libx264rgb 描述误命中 libx264。"""
    names = set()
    for line in output.splitlines():
        match = ENCODER_ROW.match(line)
        if match and match.group(1) != "=":
            names.add(match.group(1))
    return names


def emit(obj: dict) -> None:
    """单行 JSON 输出，中文不转义。"""
    print(json.dumps(obj, ensure_ascii=False, separators=(",", ":")), flush=True)


def ok(verb: str, data, evidence=None, hint: str = "") -> dict:
    out = {"ok": True, "verb": verb, "data": data, "evidence": evidence or {}}
    if hint:
        out["hint"] = hint
    return out


def fail(verb: str, code: str, detail: str, hint: str = "", retriable: bool = False) -> dict:
    out = {"ok": False, "verb": verb, "code": code, "detail": detail, "retriable": retriable}
    if hint:
        out["hint"] = hint
    return out


class MediaError(Exception):
    """媒体读取失败，带可机读错误码。"""

    def __init__(self, code: str, detail: str, hint: str = "") -> None:
        super().__init__(detail)
        self.code = code
        self.detail = detail
        self.hint = hint


_REMOTE_SCHEME = re.compile(r"^[A-Za-z][A-Za-z0-9+.-]*://")


def local_path(value, *, field="path"):
    """拒绝 UNC/网络/URL 路径，与 jylib.media.local_path 同语义。

    Windows 解析 ``\\\\host\\share`` 会走 SMB 并可能先发送 NTLM 凭据；
    字幕链与草稿链一样只接受本地磁盘路径。
    """
    text = str(value).strip()
    if not text:
        raise MediaError("bad-args", f"{field} 不能为空")
    lowered = text.lower()
    if (text.startswith(("\\\\", "//")) or lowered.startswith("file:")
            or _REMOTE_SCHEME.match(text)):
        raise MediaError("unsafe-path",
                         f"{field} 必须是本地路径，不接受 UNC、网络盘或 URL: {text}",
                         hint="先把素材下载到本地磁盘，再用本地绝对或相对路径。")
    return Path(text).expanduser()


def _run(cmd: list[str], timeout: int = 20, cwd: str | None = None) -> tuple[int, str, str]:
    try:
        p = subprocess.run(cmd, capture_output=True, timeout=timeout, text=True,
                           encoding="utf-8", errors="replace", cwd=cwd)
        return p.returncode, p.stdout or "", p.stderr or ""
    except FileNotFoundError:
        return 127, "", "executable not found"
    except subprocess.TimeoutExpired:
        return 124, "", "timeout"
    except OSError as exc:
        return 1, "", f"{type(exc).__name__}: {exc}"


def parse_version(folder_name: str) -> tuple[int, ...]:
    return tuple(int(seg) if seg.isdigit() else 0 for seg in folder_name.split("."))


def find_installations() -> list[dict]:
    """扫描 Apps 目录。只有含 JianyingPro.exe 的目录才算可用安装。

    差量升级残留目录（只有 *_d_<hex> 待删文件、无 exe）会被列出并标注。
    """
    found: list[dict] = []
    if not APPS_DIR.is_dir():
        return found
    for entry in sorted(APPS_DIR.iterdir(), key=lambda p: p.name, reverse=True):
        if not entry.is_dir():
            continue
        exe = entry / "JianyingPro.exe"
        resources = entry / "Resources" / "canvas_agent"
        item = {
            "path": str(entry),
            "folder": entry.name,
            "version": entry.name,
            "version_tuple": list(parse_version(entry.name)),
            "usable": exe.is_file(),
            "has_resources": resources.is_dir(),
        }
        if not exe.is_file():
            item["note"] = "差量升级残留，无 JianyingPro.exe，不可作为安装使用"
        found.append(item)
    return found


def pick_installation(prefer: str | None = None) -> dict | None:
    usable = [i for i in find_installations() if i["usable"]]
    if not usable:
        return None
    if prefer:
        for i in usable:
            if i["version"] == prefer:
                return i
    usable.sort(key=lambda i: i["version_tuple"], reverse=True)
    return usable[0]


def probe_ffmpeg_capabilities(exe: Path) -> dict:
    """用 -filters / -encoders 实际探测能力，而不是匹配 configuration 字符串。

    原因：drawtext 之类内置滤镜不会出现在 configuration 行里，字符串匹配会误报 false。
    """
    code, out, err = _run([str(exe), "-hide_banner", "-version"], timeout=15)
    text = (out or "") + (err or "")
    if code != 0 and "ffmpeg version" not in text:
        return {"usable": False, "reason": (err or text or "无法执行").strip()[:200]}

    version = next((ln.strip() for ln in text.splitlines() if ln.startswith("ffmpeg version")), "")

    caps = {k: False for k in list(CAPABILITY_FILTERS) + list(CAPABILITY_ENCODERS)}
    fcode, fout, ferr = _run([str(exe), "-hide_banner", "-filters"], timeout=20)
    if fcode == 0:
        names = filter_names((fout or "") + "\n" + (ferr or ""))
        for key, fname in CAPABILITY_FILTERS.items():
            caps[key] = fname in names
    ecode, eout, eerr = _run([str(exe), "-hide_banner", "-encoders"], timeout=20)
    if ecode == 0:
        names = encoder_names((eout or "") + "\n" + (eerr or ""))
        for key, ename in CAPABILITY_ENCODERS.items():
            caps[key] = ename in names

    return {
        "usable": True,
        "version": version,
        "libass": caps["libass"],
        "drawtext": caps["drawtext"],
        "libx264": caps["libx264"],
        "libx265": caps["libx265"],
        # burn.py 固定用 subtitles= 滤镜，只有 libass 能烧；drawtext 不能替代。
        "subtitle_burn_in": caps["libass"],
    }


def resolve_ffmpeg(prefer_bundled: bool = False) -> dict:
    """按优先级找 ffmpeg。返回候选清单、选中项与被忽略的无效配置。"""
    candidates: list[tuple[str, Path]] = []
    warnings: list[str] = []

    env_path = os.environ.get(FFMPEG_ENV)
    if env_path:
        p = Path(env_path)
        if p.is_file():
            candidates.append(("env:JY_FFMPEG", p))
        else:
            warnings.append(f"{FFMPEG_ENV} 指向的文件不存在，已忽略：{env_path}")

    for c in FFMPEG_CANDIDATES:
        candidates.append(("user", c))

    # 可选依赖 imageio-ffmpeg：只读包内 binaries，不调用 get_ffmpeg_exe（可能触发下载）。
    try:
        import imageio_ffmpeg

        binaries = Path(imageio_ffmpeg.__file__).resolve().parent / "binaries"
        for candidate in sorted(binaries.glob("ffmpeg-*")):
            if candidate.is_file():
                candidates.append(("python:imageio_ffmpeg", candidate))
    except Exception:
        pass

    try:
        from shutil import which

        hit = which("ffmpeg")
        if hit:
            candidates.append(("path", Path(hit)))
    except Exception:
        pass

    inst = pick_installation()
    if inst:
        b = Path(inst["path"]) / "ffmpeg.exe"
        if b.is_file():
            candidates.append(("jianying-bundled", b))

    seen: list[dict] = []
    seen_paths: set[str] = set()
    for source, path in candidates:
        if not path.is_file():
            continue
        key = str(path.resolve()).lower()
        if key in seen_paths:
            continue
        seen_paths.add(key)
        seen.append({"source": source, "path": str(path), **probe_ffmpeg_capabilities(path)})

    chosen = None
    if prefer_bundled:
        chosen = next((e for e in seen
                       if e.get("usable") and e["source"] == "jianying-bundled"), None)
    if chosen is None:
        chosen = next((e for e in seen if e.get("usable") and e.get("subtitle_burn_in")), None)
    if chosen is None:
        chosen = next((e for e in seen
                       if e.get("usable") and e["source"] != "jianying-bundled"), None)
    if chosen is None and seen:
        chosen = seen[0]

    # JY_FFMPEG 是首选候选，不是硬锁：如果它不可用，回退到其他候选，
    # 但把“没有选中你指定的那个”写进 warnings，避免用户以为设置被忽略。
    env_candidate = next((e for e in seen if e["source"] == "env:JY_FFMPEG"), None)
    if env_candidate and chosen and chosen["path"] != env_candidate["path"]:
        warnings.append(
            f"{FFMPEG_ENV} 指向 {env_candidate['path']}，但不是最终选中项；"
            f"实际使用 {chosen['path']}（{chosen['source']}）")

    return {
        "chosen": chosen,
        "candidates": seen,
        "warnings": warnings,
        "burn_in_available": bool(chosen and chosen.get("subtitle_burn_in")),
        "note": "" if chosen and chosen.get("subtitle_burn_in")
        else "无带 libass 的 ffmpeg：字幕只能生成文件，无法烧录进画面",
    }


def ffprobe_for(ffmpeg_path: str | None) -> str | None:
    """依次找 ffprobe：ffmpeg 同目录 → PATH → 剪映自带。"""
    if ffmpeg_path:
        p = Path(ffmpeg_path).with_name("ffprobe.exe")
        if p.is_file():
            return str(p)
    try:
        from shutil import which

        hit = which("ffprobe")
        if hit:
            return hit
    except Exception:
        pass
    inst = pick_installation()
    if inst:
        p = Path(inst["path"]) / "ffprobe.exe"
        if p.is_file():
            return str(p)
    return None


def media_duration(path: Path) -> float:
    """统一入口：读媒体时长（秒）。

    区分三类失败，避免把"图片没有时长"说成"ffprobe 坏了"：
      - ffprobe-missing  找不到 ffprobe
      - probe-failed     文件损坏或格式不可解析
      - no-duration      能解析但没有时长信息（图片、部分容器）
    """
    ff = resolve_ffmpeg()
    probe = ffprobe_for((ff.get("chosen") or {}).get("path"))
    if not probe:
        raise MediaError("ffprobe-missing", "未找到 ffprobe，无法读取媒体时长",
                         hint="安装 ffmpeg 并确保 ffprobe 可用，或设置 JY_FFMPEG 指向 ffmpeg.exe")
    code, out, err = _run([probe, "-v", "error", "-print_format", "json",
                           "-show_format", "-show_streams", str(path)], timeout=60)
    if code != 0:
        first = (err or out).strip().splitlines()
        raise MediaError("probe-failed",
                         f"ffprobe 无法解析该文件: {first[0][:160] if first else '未知错误'}",
                         hint="确认文件未损坏、格式受支持")
    try:
        info = json.loads(out)
    except Exception as exc:  # noqa: BLE001
        raise MediaError("probe-failed", f"ffprobe 输出不是合法 JSON: {exc}") from exc

    dur = 0.0
    try:
        dur = float((info.get("format") or {}).get("duration") or 0)
    except (TypeError, ValueError):
        dur = 0.0
    if dur <= 0:
        for s in info.get("streams") or []:
            try:
                dur = max(dur, float(s.get("duration") or 0))
            except (TypeError, ValueError):
                continue
    if dur <= 0:
        raise MediaError("no-duration",
                         f"该文件没有时长信息: {path.name}",
                         hint="图片或部分容器不提供时长，换用视频/音频文件")
    return dur


def human_bytes(n: int | float | None) -> str:
    if not n:
        return "-"
    units = ["B", "KB", "MB", "GB", "TB"]
    v = float(n)
    for u in units:
        if v < 1024 or u == units[-1]:
            return f"{v:.1f}{u}"
        v /= 1024
    return f"{v:.1f}TB"


def us_to_hms(us: int | float | None) -> str:
    """剪映 tm_duration 单位是微秒。"""
    if not us:
        return "00:00:00.000"
    total = float(us) / 1_000_000
    h = int(total // 3600)
    m = int((total % 3600) // 60)
    s = total % 60
    return f"{h:02d}:{m:02d}:{s:06.3f}"


def draft_entries() -> list[dict]:
    """读草稿根索引与回收站索引。两者都是明文 JSON。

    folder_exists 按各自桶的基目录判断，回收站草稿在 .recycle_bin 下。
    """
    rows: list[dict] = []
    for path, bucket, base in (
        (ROOT_META, "active", DRAFT_ROOT),
        (RECYCLE_BIN / "root_meta_info.json", "recycled", RECYCLE_BIN),
    ):
        if not path.is_file():
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:  # noqa: BLE001
            rows.append({"bucket": bucket, "error": f"索引不可解析: {exc}"})
            continue
        for d in data.get("all_draft_store") or []:
            name = d.get("draft_name")
            rows.append({
                "bucket": bucket,
                "source_index": str(path),
                "name": name,
                "draft_id": d.get("draft_id"),
                "duration_us": d.get("tm_duration"),
                "duration": us_to_hms(d.get("tm_duration")),
                "materials_bytes": d.get("draft_timeline_materials_size"),
                "materials_size": human_bytes(d.get("draft_timeline_materials_size")),
                "draft_version": d.get("draft_new_version"),
                "created_us": d.get("tm_draft_create"),
                "modified_us": d.get("tm_draft_modified"),
                "removed_us": d.get("tm_draft_removed"),
                "folder_exists": bool(name) and (base / name).is_dir(),
            })
    return rows
