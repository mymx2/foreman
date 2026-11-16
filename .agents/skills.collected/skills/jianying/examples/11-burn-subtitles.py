#!/usr/bin/env python3
"""案例 11：硬字幕烧录（需要带 libass 的 ffmpeg）。

不是“生成字幕轨”，而是把两条 SRT 真正烧进画面，并用返回的
`drift_ok` / `cues_fully_visible` 做结构级验收。没有 libass 时 SKIP。
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
JY = ROOT / "scripts" / "jy.py"
SUB = ROOT / "scripts" / "subtitles" / "cli.py"


def _run(script, args, cwd, timeout=180):
    return subprocess.run([sys.executable, str(script), *args], cwd=str(cwd),
                          capture_output=True, text=True, encoding="utf-8",
                          errors="replace", timeout=timeout)


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="jy-example-") as tmp:
        root = Path(tmp)
        probe = _run(JY, ["probe"], root)
        try:
            payload = json.loads(probe.stdout)
        except json.JSONDecodeError:
            print(f"probe 没有返回 JSON：{probe.stdout}\n{probe.stderr}")
            return 1
        tools = (payload.get("data") or {}).get("ffmpeg") or {}
        if not tools.get("ffmpeg") or not tools.get("ffprobe"):
            print("SKIP 11-burn-subtitles: 没有可用的 ffmpeg/ffprobe")
            return 77

        video = root / "input.mp4"
        made = subprocess.run([
            tools["ffmpeg"], "-y", "-hide_banner", "-loglevel", "error",
            "-f", "lavfi", "-i", "color=c=black:s=320x180:d=2",
            "-c:v", "mpeg4", "-pix_fmt", "yuv420p", str(video),
        ], capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=60)
        if made.returncode != 0 or not video.is_file():
            print(f"生成测试视频失败：{made.stderr}")
            return 1

        srt = root / "subs.srt"
        srt.write_text(
            "1\n00:00:00,200 --> 00:00:00,900\n第一句\n\n"
            "2\n00:00:01,000 --> 00:00:01,900\n第二句\n",
            "utf-8",
        )

        burned = _run(SUB, ["burn", "--video", str(video), "--srt", str(srt),
                            "--out", "out.mp4", "--size", "16"], root)
        try:
            result = json.loads(burned.stdout)
        except json.JSONDecodeError:
            print(f"burn 没有返回 JSON：{burned.stdout}\n{burned.stderr}")
            return 1
        if not result.get("ok"):
            code = str(result.get("code") or (result.get("error") or {}).get("code") or "")
            if code in {"ffmpeg-missing", "ffmpeg-missing-capability"}:
                print(f"SKIP 11-burn-subtitles: {code}")
                return 77
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 1

        data = result.get("data") or {}
        out = root / "out.mp4"
        ok = (
            out.is_file() and out.stat().st_size > 0
            and data.get("drift_ok") is True
            and int(data.get("cues") or 0) == 2
            and int(data.get("cues_fully_visible") or 0) == 2
            and int(data.get("cues_truncated") or 0) == 0
        )
        print(json.dumps({
            "ok": bool(ok),
            "case": "11-burn-subtitles",
            "bytes": data.get("bytes"),
            "cues": data.get("cues"),
            "cues_fully_visible": data.get("cues_fully_visible"),
            "drift_ok": data.get("drift_ok"),
            "ffmpeg": data.get("ffmpeg"),
        }, ensure_ascii=False))
        return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
