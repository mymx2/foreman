#!/usr/bin/env python3
"""案例 10：按真实音频时长生成 SRT。

用 3 秒测试音轨 + 两行文案走 `srt.from-audio --by-line`，再用 `srt.check`
验证行数、时间码与重叠。它不做语音识别，只做“已有文案的时间码分配”。
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


def _run(script, args, cwd, timeout=120):
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
            print("SKIP 10-srt-from-audio: 没有可用的 ffmpeg/ffprobe")
            return 77

        audio = root / "voice.m4a"
        made = subprocess.run([
            tools["ffmpeg"], "-y", "-hide_banner", "-loglevel", "error",
            "-f", "lavfi", "-i", "sine=frequency=440:duration=3",
            "-c:a", "aac", str(audio),
        ], capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=60)
        if made.returncode != 0 or not audio.is_file():
            print(f"生成测试音轨失败：{made.stderr}")
            return 1

        text = root / "lines.txt"
        text.write_text("第一句字幕\n第二句字幕\n", "utf-8")

        built = _run(SUB, ["srt.from-audio", "--audio", str(audio), "--text", str(text),
                           "--out", "out.srt", "--by-line"], root)
        try:
            build_result = json.loads(built.stdout)
        except json.JSONDecodeError:
            print(f"srt.from-audio 没有返回 JSON：{built.stdout}\n{built.stderr}")
            return 1

        checked = _run(SUB, ["srt.check", "--in", "out.srt"], root)
        try:
            check_result = json.loads(checked.stdout)
        except json.JSONDecodeError:
            print(f"srt.check 没有返回 JSON：{checked.stdout}\n{checked.stderr}")
            return 1
        check_data = check_result.get("data") or {}
        ok = (
            built.returncode == 0 and build_result.get("ok")
            and checked.returncode == 0 and check_result.get("ok")
            and int(check_data.get("lines") or 0) == 2
            and not (check_data.get("issues") or [])
            and (root / "out.srt").is_file()
        )
        print(json.dumps({
            "ok": bool(ok),
            "case": "10-srt-from-audio",
            "audio_seconds": build_result.get("data", {}).get("audio_seconds"),
            "lines": check_data.get("lines"),
            "issues": check_data.get("issues"),
        }, ensure_ascii=False))
        return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
