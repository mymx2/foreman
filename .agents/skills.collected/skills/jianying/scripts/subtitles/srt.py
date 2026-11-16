"""srt：字幕生成、按真实音频时长对齐、规范化与校验。

子命令：
    build         按字数比例在给定总时长内分配时间码
    from-audio    给定单条音轨，读真实时长后按字数分配
    from-segments 每条字幕对应一个独立音频文件，用各自真实时长（最精确）
    tidy          断行过长（词安全）、单字伪影截短、保底时长、修重叠（内部复查）
    check         校验时间码单调、无重叠、行宽与时长合规

设计约定：
- 任何输入问题都返回 JSON 失败信封，不抛栈
- 解析出 0 条字幕视为"不可解析"，不允许静默通过
- 参数做范围与有限性校验，非法值直接拒绝而不是产出坏时间码
- 判定阈值统一用 EPS 容差，避免 0.15000000000000002 这类浮点假警
"""

from __future__ import annotations

import argparse
import math
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import jy_common as C

EPS = 1e-3          # 时间码比较容差（毫秒级）
MIN_ITEM_SPAN = 0.001
SHORT_CUE_CAP = 1.0  # 单字/双字超时长伪影的显示上限（秒）
PUNCT = "，。！？；：、,.!?;:…—-—\"'（）()《》<>「」【】 "
# 句末标点 + 换行；英文句点要求其后是空白或结尾
SPLIT_RE = re.compile(r"[。！？；!?;]|\.\.\.|…|\.(?=\s|$)|\n+")
TS_RE = re.compile(r"(\d+):(\d{1,2}):(\d{1,2})[,.](\d{1,3})")
INDEX_LINE = re.compile(r"\d+")      # SRT 纯数字序号行，解析时跳过
AUDIO_EXT = {".mp3", ".wav", ".m4a", ".aac", ".flac", ".ogg"}


class SrtError(Exception):
    """可预期的输入问题，转成 JSON 失败信封。"""

    def __init__(self, code: str, detail: str, hint: str = "") -> None:
        super().__init__(detail)
        self.code = code
        self.detail = detail
        self.hint = hint


# ---------- 时间码 ----------

def fmt(t: float) -> str:
    if not math.isfinite(t):
        raise SrtError("bad-timecode", f"时间码非有限值: {t}")
    if t < 0:
        raise SrtError("bad-timecode", f"时间码为负: {t}")
    ms = int(round(t * 1000))
    h, ms = divmod(ms, 3600_000)
    m, ms = divmod(ms, 60_000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def parse_ts(s: str) -> float:
    m = TS_RE.search(s)
    if not m:
        raise SrtError("srt-unparsable", f"时间码无法解析: {s.strip()[:40]}")
    h, mi, sec, frac = m.groups()
    if int(mi) > 59 or int(sec) > 59:
        raise SrtError("bad-timecode", f"时间码超出 59 上限: {s.strip()[:40]}")
    ms = int(frac.ljust(3, "0"))
    return int(h) * 3600 + int(mi) * 60 + int(sec) + ms / 1000


# ---------- 文本切分 ----------

def visible_len(s: str) -> int:
    return len([ch for ch in s if ch not in PUNCT and not ch.isspace()])


def _word_char(seg: str, i: int) -> bool:
    """ASCII 词内字符：字母数字，或夹在字母数字之间的撇号/连字符（don't、state-of-the-art）。"""
    ch = seg[i]
    if not ch.isascii():
        return False
    if ch.isalnum():
        return True
    return (ch in "'-" and 0 < i < len(seg) - 1
            and seg[i - 1].isascii() and seg[i - 1].isalnum()
            and seg[i + 1].isascii() and seg[i + 1].isalnum())


def split_text(text: str, max_chars: int) -> list[str]:
    if max_chars < 1:
        raise SrtError("bad-max-chars", f"--max-chars 必须 ≥ 1，收到 {max_chars}")
    raw = [seg.strip() for seg in SPLIT_RE.split(text) if seg and seg.strip()]
    out: list[str] = []
    for seg in raw:
        guard = 0
        while visible_len(seg) > max_chars:
            guard += 1
            if guard > 2000:
                raise SrtError("split-too-long",
                               f"文本无法切分到 {max_chars} 字以内: {seg[:20]}…")
            cut, acc = 0, 0
            for i, ch in enumerate(seg):
                if ch not in PUNCT and not ch.isspace():
                    acc += 1
                if acc >= max_chars:
                    cut = i + 1
                    break
            if cut <= 0:
                break
            # 中英混排没有空格可借：硬切点落在英文词内部时回退到词起点，
            # 否则 excel 会被切成 ex+cel 这类残词字幕；词起点太靠左时宁可硬切。
            if cut < len(seg) and _word_char(seg, cut):
                run_start = cut
                while run_start > 0 and _word_char(seg, run_start - 1):
                    run_start -= 1
                if run_start > 0 and visible_len(seg[:run_start]) >= max(1, max_chars // 2):
                    cut = run_start
            head = seg[:cut]
            if head and head[-1].isascii() and head[-1].isalnum():
                sp = head.rfind(" ")
                if sp > max_chars // 2:
                    cut = sp + 1
            piece = seg[:cut].strip()
            seg = seg[cut:].strip()
            # 硬切点后的标点归上一行行尾，避免行首标点
            while seg and seg[0] in PUNCT:
                piece += seg[0]
                seg = seg[1:].strip()
            if piece and visible_len(piece):
                out.append(piece)
        if seg and visible_len(seg):
            while out and seg and seg[0] in PUNCT:
                out[-1] += seg[0]
                seg = seg[1:].strip()
            if seg:
                out.append(seg)
    if not out:
        raise SrtError("empty-text", "文本为空或只含标点，没有可用的字幕行")
    return out


# ---------- 时间分配 ----------

def _check_gap(gap: float) -> None:
    if not math.isfinite(gap) or gap < 0:
        raise SrtError("bad-gap", f"--gap 必须是 ≥ 0 的有限数，收到 {gap}")


def allocate(lines: list[str], total: float, gap: float = 0.06) -> list[dict]:
    if not math.isfinite(total) or total <= 0:
        raise SrtError("bad-total", f"--total 必须是正数，收到 {total}")
    _check_gap(gap)
    gapped = gap * max(len(lines) - 1, 0)
    span = total - gapped
    if span <= 0:
        raise SrtError("bad-total",
                       f"总时长 {total}s 不足以容纳 {len(lines)} 条字幕的间隔（需 > {gapped:.2f}s）")
    if span / len(lines) < MIN_ITEM_SPAN:
        raise SrtError("total-too-small",
                       f"总时长 {total}s 平摊到 {len(lines)} 条，每条不足 1ms",
                       hint="加大 --total，或减少字幕条数（提高 --max-chars）")
    weights = [max(visible_len(x), 1) for x in lines]
    wsum = sum(weights)
    # 不只查平均：最短一条的加权份额也必须 ≥ 1ms，否则会出现零时长字幕。
    min_share = span * min(weights) / wsum
    if min_share < MIN_ITEM_SPAN:
        raise SrtError("total-too-small",
                       f"总时长 {total}s 下最短一条仅 {min_share * 1000:.2f}ms，不足 1ms",
                       hint="加大 --total，或减少字幕条数（提高 --max-chars）")
    entries, cur = [], 0.0
    for line, w in zip(lines, weights):
        dur = span * w / wsum
        start, end = round(cur, 3), round(cur + dur, 3)
        if end <= start:
            raise SrtError("total-too-small",
                           "存在四舍五入后零时长的字幕条，请加大 --total",
                           hint="加大 --total，或减少字幕条数")
        entries.append({"start": start, "end": end, "text": line})
        cur += dur + gap
    return entries


def allocate_by_durations(lines: list[str], durs: list[float], gap: float = 0.0,
                          min_display: float = 0.2) -> tuple[list[dict], int]:
    """逐条真实时长。默认不留间隙，时间轴与音频时长严格对齐。
    min_display 只做极短音频兜底，并回报被抬高的条数。"""
    _check_gap(gap)
    entries, cur, padded = [], 0.0, 0
    for line, d in zip(lines, durs):
        if not math.isfinite(d) or d <= 0:
            raise SrtError("bad-audio-duration", f"音频时长异常: {d}")
        dur = d
        if d < min_display:
            dur = min_display
            padded += 1
        entries.append({"start": round(cur, 3), "end": round(cur + dur, 3), "text": line})
        cur += dur + gap
    return entries, padded


# ---------- 读写 ----------

def read_text_any(path: Path) -> str:
    path = C.local_path(path, field="文本路径")
    if not path.is_file():
        raise SrtError("file-not-found", f"文件不存在: {path}")
    raw = path.read_bytes()
    if raw[:2] in (b"\xff\xfe", b"\xfe\xff"):
        encodings = ("utf-16", "utf-8-sig")
    else:
        encodings = ("utf-8-sig", "utf-8", "gb18030")
    for enc in encodings:
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    raise SrtError("bad-encoding", f"无法解码文本（尝试 {'/'.join(encodings)}）: {path.name}",
                   hint="用记事本另存为 UTF-8 后重试")


def read_srt(path: Path) -> list[dict]:
    """解析 SRT。

    按行状态机切分，不依赖空行分隔：每个含 ``-->`` 的行开一条新字幕，纯数字
    序号行跳过，正文一直累积到下一个时间码行。没有空行的紧凑 SRT 也能完整读出。

    正文里出现 ``-->`` 属于不支持的写法：这种行会被当成新的时间码行，随后因
    正文为空触发 ``srt-dropped-blocks``，而不是被静默拼进上一条字幕。
    """
    text = (read_text_any(path).replace("\r\n", "\n").replace("\r", "\n")
            .lstrip("\ufeff"))
    blocks: list[tuple[int, str | None, list[str]]] = []
    start_line, ts_line, body = 0, None, []
    indexed = None
    expected_index = 1
    for line_no, raw in enumerate(text.split("\n"), 1):
        line = raw.strip()
        if "-->" in line:
            # 紧凑 SRT 的序号会落在上一条正文末尾；只有等于预期序号时才当成序号，
            # 避免把正文里的纯数字（如“2024”）删掉。
            if (indexed and body and INDEX_LINE.fullmatch(body[-1])
                    and int(body[-1]) == expected_index):
                body.pop()
                expected_index += 1
            if indexed is None:
                indexed = False
            if ts_line is not None or body:
                blocks.append((start_line or line_no, ts_line, body))
            start_line, ts_line, body = line_no, line, []
            continue
        if not line:
            continue
        if ts_line is None and INDEX_LINE.fullmatch(line) and indexed is not False:
            indexed = True
            expected_index = int(line) + 1
            continue
        if not body and ts_line is None:
            start_line = line_no
        body.append(line)
    if ts_line is not None or body:
        blocks.append((start_line or 1, ts_line, body))

    entries: list[dict] = []
    dropped: list[int] = []
    for no, (line_no, ts, lines) in enumerate(blocks, 1):
        if ts is None or not lines:
            dropped.append(no)
            continue
        a, _, b2 = ts.partition("-->")
        try:
            start, end = parse_ts(a), parse_ts(b2)
        except SrtError as exc:
            raise SrtError(exc.code,
                           f"第 {no} 条（第 {line_no} 行）：{exc.detail}") from exc
        entries.append({"start": start, "end": end, "text": " ".join(lines).strip()})
    if dropped:
        raise SrtError("srt-dropped-blocks",
                       f"{len(dropped)} 个块缺时间码或正文为空（第 {', '.join(map(str, dropped[:8]))} 块），"
                       f"拒绝静默丢弃",
                       hint="修复或删除这些块后重试；本技能不静默丢数据")
    if not entries:
        raise SrtError("srt-unparsable",
                       f"未解析出任何字幕条目: {path.name}",
                       hint="确认是 SRT 格式（含 --> 时间码行），且块之间有换行")
    return entries


def write_srt(entries: list[dict], path: Path) -> int:
    if path.exists():
        raise SrtError("out-exists", f"输出文件已存在: {path}",
                       hint="换一个 --out 路径；本技能不覆盖已有文件")
    out = []
    for i, e in enumerate(entries, 1):
        out.append(f"{i}\n{fmt(e['start'])} --> {fmt(e['end'])}\n{e['text'].strip()}\n")
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("\n".join(out), encoding="utf-8")
    except PermissionError as exc:
        raise SrtError("bad-out-path", f"无法写入 {path}: {exc.strerror or exc}",
                       hint="确认 --out 是文件路径而非目录，且有写权限") from exc
    except OSError as exc:
        raise SrtError("bad-out-path", f"无法写入 {path}: {exc}") from exc
    return len(entries)


def media_duration(path: Path) -> float:
    return C.media_duration(path)


def natural_key(p: Path):
    stem = p.stem
    return [int(x) if x.isdigit() else x.lower() for x in re.split(r"(\d+)", stem)]


# ---------- 子命令 ----------

def _emit_error(verb: str, exc: Exception) -> int:
    if isinstance(exc, SrtError):
        C.emit(C.fail(verb, exc.code, exc.detail, hint=exc.hint))
        return 1
    if isinstance(exc, C.MediaError):
        C.emit(C.fail(verb, exc.code, exc.detail, hint=exc.hint))
        return 1
    if isinstance(exc, FileNotFoundError):
        C.emit(C.fail(verb, "file-not-found", f"文件不存在: {exc.filename or exc}"))
        return 1
    if isinstance(exc, PermissionError):
        C.emit(C.fail(verb, "permission-denied", f"无权限: {exc.filename or exc}"))
        return 1
    if isinstance(exc, OSError):
        C.emit(C.fail(verb, "io-error", str(exc)[:200]))
        return 1
    first = str(exc).splitlines()[0] if str(exc) else ""
    C.emit(C.fail(verb, "internal-error", f"{type(exc).__name__}: {first}"[:200]))
    return 1


def _lines_from(a) -> list[str]:
    text = read_text_any(C.local_path(a.text, field="文本路径"))
    if getattr(a, "by_line", False):
        lines = [ln.strip() for ln in text.splitlines() if ln.strip() and visible_len(ln)]
        if not lines:
            raise SrtError("empty-text", "文本为空或只含标点，没有可用的字幕行")
        return lines
    return split_text(text, a.max_chars)


def _guard_out(out, inputs) -> None:
    out = C.local_path(out, field="输出路径")
    inputs = [C.local_path(p, field="输入路径") for p in inputs]
    try:
        ro = out.resolve()
    except OSError:
        return
    for p in inputs:
        try:
            rp = p.resolve()
        except OSError:
            continue
        if ro == rp:
            raise SrtError("out-is-input", f"--out 与输入同路径，会覆盖原文件: {p}",
                           hint="换一个输出路径；本技能不覆盖输入文件")


def cmd_build(a) -> int:
    try:
        if a.max_chars < 1:
            raise SrtError("bad-max-chars", f"--max-chars 必须 ≥ 1，收到 {a.max_chars}")
        _guard_out(a.out, [a.text])
        lines = _lines_from(a)
        entries = allocate(lines, a.total, a.gap)
        n = write_srt(entries, Path(a.out))
    except Exception as exc:  # noqa: BLE001
        return _emit_error("srt.build", exc)
    C.emit(C.ok("srt.build", {"lines": n, "out": a.out, "total": a.total,
                              "end_seconds": entries[-1]["end"],
                              "method": "按可见字符数比例分配"},
                evidence={"out": a.out}))
    return 0


def cmd_from_audio(a) -> int:
    try:
        if a.max_chars < 1:
            raise SrtError("bad-max-chars", f"--max-chars 必须 ≥ 1，收到 {a.max_chars}")
        audio = C.local_path(a.audio, field="音频路径")
        if not audio.is_file():
            raise SrtError("file-not-found", f"音频不存在: {audio}")
        _guard_out(a.out, [audio, a.text])
        total = media_duration(audio)
        lines = _lines_from(a)
        entries = allocate(lines, total, a.gap)
        n = write_srt(entries, Path(a.out))
    except Exception as exc:  # noqa: BLE001
        return _emit_error("srt.from-audio", exc)
    C.emit(C.ok("srt.from-audio", {"lines": n, "out": a.out,
                                   "audio_seconds": round(total, 3),
                                   "end_seconds": entries[-1]["end"],
                                   "method": "真实音频总时长 + 字数比例"},
                evidence={"audio": a.audio, "out": a.out}))
    return 0


def cmd_from_segments(a) -> int:
    try:
        if a.max_chars < 1:
            raise SrtError("bad-max-chars", f"--max-chars 必须 ≥ 1，收到 {a.max_chars}")
        segdir = C.local_path(a.segments, field="音频目录")
        if not segdir.is_dir():
            raise SrtError("dir-not-found", f"音频目录不存在: {segdir}")
        files = sorted([p for p in segdir.iterdir()
                        if p.is_file() and p.suffix.lower() in AUDIO_EXT], key=natural_key)
        if not files:
            raise SrtError("no-segments", f"{segdir} 下无音频文件（支持 {sorted(AUDIO_EXT)}）")
        keys = [natural_key(p) for p in files]
        for i in range(1, len(keys)):
            if keys[i] == keys[i - 1]:
                raise SrtError("ambiguous-segments",
                               f"音频排序键冲突: {files[i - 1].name} 与 {files[i].name}，无法确定与文本的对应顺序",
                               hint="重命名使每条音频的文件名主干唯一，或移走重复文件")
        _guard_out(a.out, [a.text] + files)
        lines = _lines_from(a)
        if len(lines) != len(files):
            raise SrtError("count-mismatch",
                           f"文本 {len(lines)} 条，音频 {len(files)} 个，无法一一对应",
                           hint="用 --by-line 让每条文本行对应一个音频文件，或重新切分文本")
        durs = [media_duration(p) for p in files]
        entries, padded = allocate_by_durations(lines, durs, a.gap)
        n = write_srt(entries, Path(a.out))
    except Exception as exc:  # noqa: BLE001
        return _emit_error("srt.from-segments", exc)
    C.emit(C.ok("srt.from-segments", {
        "lines": n, "out": a.out, "segments": len(durs),
        "audio_seconds": round(sum(durs), 3),
        "end_seconds": entries[-1]["end"],
        "padded_to_min_display": padded,
        "method": "逐条真实音频时长（不加间隔时误差为 0 帧）",
    }, evidence={"out": a.out}))
    return 0


def _repair(entries: list[dict], min_dur: float, gap: float) -> tuple[list[dict], dict]:
    """先归一化倒挂、再保底（只抬不压）、再收口重叠、最后复查。"""
    if not math.isfinite(min_dur) or min_dur < 0:
        raise SrtError("bad-min-dur", f"--min-dur 必须是 ≥ 0 的有限数，收到 {min_dur}")
    _check_gap(gap)

    out = sorted((dict(e) for e in entries), key=lambda e: (e["start"], e["end"]))
    normalized = 0
    for e in out:
        if e["end"] <= e["start"] + EPS:
            e["end"] = e["start"] + max(min_dur, 0.2)
            normalized += 1

    candidates, achieved = 0, 0
    for i, e in enumerate(out):
        if e.get("_capped"):
            continue
        if e["end"] - e["start"] >= min_dur - EPS:
            continue
        candidates += 1
        limit = out[i + 1]["start"] - gap if i + 1 < len(out) else float("inf")
        want = e["start"] + min_dur
        target = min(want, limit) if math.isfinite(limit) else want
        if target > e["end"]:
            e["end"] = max(e["end"], target)   # 只抬不压
        if e["end"] - e["start"] >= min_dur - EPS:
            achieved += 1

    fixed = 0
    for i in range(len(out) - 1):
        if out[i]["end"] > out[i + 1]["start"] + EPS:
            out[i]["end"] = max(out[i]["start"] + 0.05, out[i + 1]["start"] - gap)
            fixed += 1

    remaining = sum(1 for i in range(len(out) - 1)
                    if out[i]["end"] > out[i + 1]["start"] + EPS)
    return out, {"normalized_inverted": normalized,
                 "min_dur_candidates": candidates,
                 "min_dur_achieved": achieved,
                 "overlaps_fixed": fixed,
                 "remaining_overlaps": remaining}


def cmd_tidy(a) -> int:
    try:
        if a.max_chars < 1:
            raise SrtError("bad-max-chars", f"--max-chars 必须 ≥ 1，收到 {a.max_chars}")
        _check_gap(a.gap)
        if not math.isfinite(a.min_dur) or a.min_dur < 0:
            raise SrtError("bad-min-dur", f"--min-dur 必须是 ≥ 0 的有限数，收到 {a.min_dur}")
        if not math.isfinite(a.max_dur) or a.max_dur <= 0:
            raise SrtError("bad-max-dur", f"--max-dur 必须是正数，收到 {a.max_dur}")
        _guard_out(a.out, [a.inp])
        entries = read_srt(C.local_path(a.inp, field="字幕路径"))
        out: list[dict] = []
        split_count = 0
        capped_count = 0
        for e in entries:
            dur = max(e["end"] - e["start"], 0.0)
            if visible_len(e["text"]) > a.max_chars:
                split_count += 1
                parts = split_text(e["text"], a.max_chars)
                weights = [max(visible_len(p), 1) for p in parts]
                total = sum(weights)
                cursor = e["start"]
                for p, w in zip(parts, weights):
                    span = dur * w / total
                    end = cursor + span
                    if visible_len(p) <= 2 and span > a.max_dur + EPS:
                        capped_count += 1
                        end = cursor + min(span, SHORT_CUE_CAP)
                    out.append({"start": cursor, "end": end, "text": p})
                    cursor += span
            elif dur > a.max_dur + EPS and visible_len(e["text"]) <= 2:
                # Paraformer 块边界会把单字拉成数秒（吞掉静音）；单字无法再拆，
                # 截短让字幕在静音时消失，文字不动。只压不抬，且优先于 min_dur 保底。
                capped_count += 1
                out.append({"start": e["start"],
                            "end": e["start"] + min(dur, SHORT_CUE_CAP),
                            "text": e["text"], "_capped": True})
            else:
                out.append({"start": e["start"], "end": e["start"] + dur, "text": e["text"]})
        out, stats = _repair(out, a.min_dur, a.gap)
        n = write_srt(out, Path(a.out))
    except Exception as exc:  # noqa: BLE001
        return _emit_error("srt.tidy", exc)
    C.emit(C.ok("srt.tidy", {"in_line_count": len(entries), "out_line_count": n,
                             "long_lines_split": split_count,
                             "short_artifacts_capped": capped_count,
                             **stats, "out": a.out},
                hint="" if stats["remaining_overlaps"] == 0 else "仍有重叠，请用 srt.check 复核"))
    return 0


def cue_issues(entries: list[dict], *, min_dur: float = 0.0,
               max_dur: float | None = None,
               max_chars: int | None = None,
               check_overlap: bool = True) -> tuple[list[dict], list[str]]:
    """检查 cue 的时间码/时长/可选行宽；srt.check 默认拒重叠，burn 可关掉。

    返回 (按时间排序的条目, 问题列表)。不修改输入。
    """
    ordered = sorted(entries, key=lambda e: (e["start"], e["end"]))
    issues: list[str] = []
    prev_end = -1.0
    for i, e in enumerate(ordered, 1):
        start, end = float(e["start"]), float(e["end"])
        dur = end - start
        if not (math.isfinite(start) and math.isfinite(end)):
            issues.append(f"#{i} 时间码不是有限数值")
        if start < -EPS:
            issues.append(f"#{i} 起点为负 {start:.3f}s")
        if check_overlap and start < prev_end - EPS:
            issues.append(f"#{i} 与前一条重叠 {prev_end - start:.3f}s")
        if dur <= EPS:
            issues.append(f"#{i} 时长为 {dur:.3f}s")
        if min_dur and dur < min_dur - EPS:
            issues.append(f"#{i} 时长 {dur:.2f}s 短于 {min_dur}s")
        if max_chars is not None and visible_len(e["text"]) == 0:
            issues.append(f"#{i} 正文只含标点或空白")
        if max_chars is not None and visible_len(e["text"]) > max_chars:
            issues.append(f"#{i} 行宽 {visible_len(e['text'])} 超过 {max_chars}")
        if max_dur is not None and dur > max_dur + EPS:
            issues.append(f"#{i} 时长 {dur:.2f}s 超过 {max_dur}s")
        prev_end = max(prev_end, end)
    return ordered, issues


def cmd_check(a) -> int:
    try:
        if a.max_chars < 1:
            raise SrtError("bad-max-chars", f"--max-chars 必须 ≥ 1，收到 {a.max_chars}")
        if not math.isfinite(a.max_dur) or a.max_dur <= 0:
            raise SrtError("bad-max-dur", f"--max-dur 必须是正数，收到 {a.max_dur}")
        if not math.isfinite(a.min_dur) or a.min_dur < 0:
            raise SrtError("bad-min-dur", f"--min-dur 必须是 ≥ 0 的有限数，收到 {a.min_dur}")
        entries = read_srt(C.local_path(a.inp, field="字幕路径"))
    except Exception as exc:  # noqa: BLE001
        return _emit_error("srt.check", exc)

    ordered, issues = cue_issues(entries, min_dur=a.min_dur, max_dur=a.max_dur,
                                 max_chars=a.max_chars)

    payload = {"lines": len(entries), "issues": issues,
               "total_seconds": round(max(e["end"] for e in entries), 3),
               "sorted_for_check": any(x is not y for x, y in zip(ordered, entries))}
    if issues:
        out = C.fail("srt.check", "srt-invalid", f"{len(issues)} 处问题",
                     hint="; ".join(issues[:5]))
        out["data"] = payload
        C.emit(out)
        return 1
    C.emit(C.ok("srt.check", payload))
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="剪映字幕工具")
    sub = ap.add_subparsers(dest="cmd", required=True)

    b = sub.add_parser("build")
    b.add_argument("--text", required=True)
    b.add_argument("--total", type=float, required=True, help="总时长（秒）")
    b.add_argument("--out", required=True)
    b.add_argument("--max-chars", type=int, default=18)
    b.add_argument("--gap", type=float, default=0.06)
    b.add_argument("--by-line", action="store_true", help="按文本行拆分，不做断句")
    b.set_defaults(func=cmd_build)

    fa = sub.add_parser("from-audio")
    fa.add_argument("--audio", required=True)
    fa.add_argument("--text", required=True)
    fa.add_argument("--out", required=True)
    fa.add_argument("--max-chars", type=int, default=18)
    fa.add_argument("--gap", type=float, default=0.06)
    fa.add_argument("--by-line", action="store_true", help="按文本行拆分，不做断句")
    fa.set_defaults(func=cmd_from_audio)

    fs = sub.add_parser("from-segments")
    fs.add_argument("--segments", required=True, help="逐条音频所在目录")
    fs.add_argument("--text", required=True)
    fs.add_argument("--out", required=True)
    fs.add_argument("--max-chars", type=int, default=18)
    # 逐条音频已经决定时间位置，默认 gap=0，避免每条多 60ms 累计漂移。
    fs.add_argument("--gap", type=float, default=0.0)
    fs.add_argument("--by-line", action="store_true")
    fs.set_defaults(func=cmd_from_segments)

    t = sub.add_parser("tidy")
    t.add_argument("--in", dest="inp", required=True)
    t.add_argument("--out", required=True)
    t.add_argument("--max-chars", type=int, default=18)
    t.add_argument("--min-dur", type=float, default=0.8)
    t.add_argument("--max-dur", type=float, default=6.0,
                   help="单字/双字 cue 超过该时长视为时间戳伪影并截短")
    t.add_argument("--gap", type=float, default=0.06)
    t.set_defaults(func=cmd_tidy)

    c = sub.add_parser("check")
    c.add_argument("--in", dest="inp", required=True)
    c.add_argument("--max-chars", type=int, default=18)
    c.add_argument("--max-dur", type=float, default=6.0)
    c.add_argument("--min-dur", type=float, default=0.0)
    c.set_defaults(func=cmd_check)

    args = ap.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
