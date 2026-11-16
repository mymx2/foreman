"""剪映字幕与草稿辅助入口。verb 分派到同目录脚本，输出单行 JSON。

用法：
    python scripts/subtitles/cli.py draft.list --active-only
    python scripts/subtitles/cli.py probe a.mp4 b.mp3
    python scripts/subtitles/cli.py srt.build --text lines.txt --total 60 --out a.srt
    python scripts/subtitles/cli.py srt.check --in a.srt
    python scripts/subtitles/cli.py burn --video in.mp4 --srt a.srt --out out.mp4

约定：任何失败（含参数错误、内部异常）都输出一行 JSON，stdout 不留裸文本。
"""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import jy_common as C

VERBS = {
    "draft.list": ("draft_list", None),
    "probe": ("probe", None),
    "srt.build": ("srt", "build"),
    "srt.from-audio": ("srt", "from-audio"),
    "srt.from-segments": ("srt", "from-segments"),
    "srt.from-local-asr": ("local_asr", None),
    "srt.tidy": ("srt", "tidy"),
    "srt.check": ("srt", "check"),
    "burn": ("burn", None),
}

USAGE = """剪映字幕与草稿辅助入口

可用 verb：
  draft.list          列出草稿（仅索引层字段，只读）
  probe <files...>    媒体探测（只读）
  srt.build           按总时长生成 SRT
  srt.from-audio      按真实音频时长生成 SRT
  srt.from-segments   逐条音频时长生成 SRT（最精确）
  srt.from-local-asr  用剪映本地 ASR 模型识别音频并生成带时间戳的 SRT
  srt.tidy            断行 / 保底时长 / 修重叠（内部复查）
  srt.check           校验 SRT
  burn                把 SRT 烧进画面（需带 libass 的 ffmpeg）

草稿生成、原生导出与首页登记用 scripts/jy.py，不用本入口。
例：python scripts/subtitles/cli.py srt.from-audio --audio vo.mp3 --text lines.txt --out a.srt
"""


def main() -> int:
    if len(sys.argv) < 2:
        print(USAGE, file=sys.stderr)
        C.emit(C.fail("jy", "bad-args", "未提供 verb",
                      hint="python scripts/subtitles/cli.py --help"))
        return 2
    if sys.argv[1] in {"-h", "--help", "help"}:
        print(USAGE)
        return 0

    verb = sys.argv[1]
    if verb not in VERBS:
        # USAGE 走 stderr，stdout 保持单行 JSON
        print(USAGE, file=sys.stderr)
        C.emit(C.fail(verb, "unknown-verb", f"未知 verb: {verb}",
                      hint="见 stderr 的 USAGE，或运行 --help"))
        return 2

    module_name, prefix = VERBS[verb]
    try:
        mod = importlib.import_module(module_name)
        rest = ([prefix] if prefix else []) + sys.argv[2:]
        sys.argv = [f"{module_name}.py"] + rest
        return mod.main()
    except SystemExit as exc:  # argparse 的参数错误 / --help
        code = exc.code if isinstance(exc.code, int) else 2
        if code == 0:
            return 0
        C.emit(C.fail(verb, "bad-args", "参数错误，详见 stderr 的 usage 提示",
                      hint="python scripts/subtitles/cli.py --help"))
        return code
    except KeyboardInterrupt:
        C.emit(C.fail(verb, "interrupted", "用户中断"))
        return 130
    except Exception as exc:  # noqa: BLE001
        C.emit(C.fail(verb, "internal-error", f"{type(exc).__name__}: {exc}"[:300]))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
