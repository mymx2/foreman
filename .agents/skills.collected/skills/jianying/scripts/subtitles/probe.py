"""probe：媒体探测。优先外部 ffprobe，回退 PATH，最后回退剪映自带。

用法：
    python scripts/probe.py a.mp4 b.mp3
    python scripts/probe.py --dir D:\\素材
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import jy_common as C

MEDIA_EXT = {".mp4", ".mov", ".mkv", ".avi", ".m4v", ".webm", ".flv", ".wmv",
             ".mp3", ".wav", ".m4a", ".aac", ".flac", ".ogg",
             ".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp", ".tif", ".tiff"}


def probe_one(probe_exe: str, path: Path) -> dict:
    code, out, err = C._run([probe_exe, "-v", "quiet", "-print_format", "json",
                             "-show_format", "-show_streams", str(path)], timeout=60)
    if code != 0:
        return {"file": str(path), "name": path.name, "ok": False,
                "error": (err or out).strip()[:200]}
    try:
        info = json.loads(out)
    except Exception as exc:  # noqa: BLE001
        return {"file": str(path), "name": path.name, "ok": False, "error": f"JSON 解析失败: {exc}"}

    fmt = info.get("format") or {}
    streams = info.get("streams") or []
    v = next((s for s in streams if s.get("codec_type") == "video"), None)
    a = next((s for s in streams if s.get("codec_type") == "audio"), None)
    dur = float(fmt.get("duration") or 0)
    if dur <= 0:
        for s in streams:
            try:
                dur = max(dur, float(s.get("duration") or 0))
            except (TypeError, ValueError):
                continue

    def ratio(expr: str) -> float:
        try:
            num, den = expr.split("/")
            return round(float(num) / float(den), 3) if float(den) else 0.0
        except Exception:
            return 0.0

    return {
        "file": str(path),
        "name": path.name,
        "ok": True,
        "duration": round(dur, 3),
        "duration_hms": C.us_to_hms(dur * 1_000_000),
        "size": int(fmt.get("size") or 0),
        "size_human": C.human_bytes(int(fmt.get("size") or 0)),
        "bitrate_kbps": int(float(fmt.get("bit_rate") or 0) / 1000),
        "format": fmt.get("format_name"),
        "video": None if not v else {
            "codec": v.get("codec_name"),
            "width": v.get("width"),
            "height": v.get("height"),
            "fps": ratio(v.get("avg_frame_rate") or v.get("r_frame_rate") or "0/1"),
            "pix_fmt": v.get("pix_fmt"),
        },
        "audio": None if not a else {
            "codec": a.get("codec_name"),
            "sample_rate": int(a.get("sample_rate") or 0),
            "channels": a.get("channels"),
            "bitrate_kbps": int(float(a.get("bit_rate") or 0) / 1000),
        },
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="*")
    ap.add_argument("--dir", help="探测目录下的媒体文件（不递归）")
    ap.add_argument("--limit", type=int, default=200)
    args = ap.parse_args()

    if args.limit < 1:
        C.emit(C.fail("probe", "bad-args", f"--limit 必须 ≥ 1，收到 {args.limit}"))
        return 1

    try:
        for f in args.files:
            C.local_path(f, field="素材路径")
        if args.dir:
            C.local_path(args.dir, field="目录")
    except C.MediaError as exc:
        C.emit(C.fail("probe", exc.code, exc.detail, hint=exc.hint))
        return 1

    targets: list[Path] = []
    for f in args.files:
        targets.append(Path(f))
    if args.dir:
        d = Path(args.dir)
        if not d.is_dir():
            C.emit(C.fail("probe", "dir-not-found", f"目录不存在: {d}"))
            return 1
        targets += [p for p in sorted(d.iterdir()) if p.suffix.lower() in MEDIA_EXT][: args.limit]

    if not targets:
        C.emit(C.fail("probe", "no-input", "未提供文件，也没有在目录中找到媒体文件"))
        return 1

    missing = [str(p) for p in targets if not p.is_file()]
    if missing:
        C.emit(C.fail("probe", "file-not-found", f"{len(missing)} 个文件不存在",
                      hint="; ".join(missing[:3])))
        return 1

    ff = C.resolve_ffmpeg()
    probe_exe = C.ffprobe_for((ff.get("chosen") or {}).get("path"))
    if not probe_exe:
        C.emit(C.fail("probe", "ffprobe-missing", "未找到 ffprobe",
                      hint="安装 ffmpeg 并确保 ffprobe 在 PATH，或设置 JY_FFMPEG 指向 ffmpeg.exe"))
        return 1

    results = [probe_one(probe_exe, p) for p in targets]
    bad = [r for r in results if not r["ok"]]
    C.emit(C.ok("probe", {"count": len(results), "items": results},
                evidence={"ffprobe": probe_exe}) if not bad else
           (C.fail("probe", "partial-failure", f"{len(bad)} 个文件探测失败",
                   hint="; ".join(r["name"] for r in bad[:3])) | {"data": {"items": results}}))
    return 0 if not bad else 1


if __name__ == "__main__":
    raise SystemExit(main())
