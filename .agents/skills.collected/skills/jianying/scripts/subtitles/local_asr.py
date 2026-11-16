"""本地 ASR：用剪映已缓存的 Paraformer ONNX 模型生成带时间戳的字幕。

不登录、不联网、不调用剪映助手。模型来自剪映「字幕 → 智能识别 → 识别字幕」
首次使用时下载到 ``%LOCALAPPDATA%/JianyingPro/User Data/SupplysStore/local-asr-supplies``。
模型缺失时按 ``model-missing`` 失败，不自动下载。

依赖（可选，缺失时按 ``missing-dep`` 失败）：
    numpy onnxruntime kaldi-native-fbank

时间戳算法与 FunASR ``ts_prediction_lfr6_standard`` 一致：CIF peak 每 20ms
一个上采样帧，peak 过 1.0 的位置即 token 边界，默认回退 1.5 帧。
"""

from __future__ import annotations

import argparse
import json
import math
import os
import subprocess
import time
from pathlib import Path

import jy_common as C
import srt as S

VERB = "srt.from-local-asr"
MODEL_FILES = ("asr-model-encoder.onnx", "asr-model-decoder.onnx", "asr-model-token.txt")
MODEL_ENV = "JY_LOCAL_ASR_DIR"
SAMPLE_RATE = 16000
CHUNK_MIN = 8.0
CHUNK_MAX = 28.0
TIME_RATE = 10.0 * 6 / 1000 / 3  # 20ms，与 FunASR LFR6/upsample=3 一致


class Deps:
    def __init__(self) -> None:
        try:
            import numpy as np
            import onnxruntime as ort
            import kaldi_native_fbank as knf
        except ImportError as exc:
            raise S.SrtError(
                "missing-dep",
                f"缺少本地 ASR 依赖: {exc.name}",
                hint="pip install numpy onnxruntime kaldi-native-fbank",
            ) from exc
        self.np = np
        self.ort = ort
        self.knf = knf


def _model_in(root: Path) -> Path | None:
    if not root.is_dir():
        return None
    if all((root / name).is_file() for name in MODEL_FILES):
        return root
    try:
        subdirs = [p for p in root.iterdir() if p.is_dir()]
        subdirs.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    except OSError:
        return None
    for sub in subdirs:
        if all((sub / name).is_file() for name in MODEL_FILES):
            return sub
    return None


def find_model_dir(explicit: str | None = None) -> Path:
    if explicit:
        root = Path(explicit).expanduser()
        found = _model_in(root)
        if found is None:
            raise S.SrtError(
                "model-missing",
                f"--model-dir 里没有完整模型: {root}",
                hint=f"需要 {', '.join(MODEL_FILES)} 三个文件；不要再回退到默认模型。",
            )
        return found
    env = os.environ.get(MODEL_ENV, "").strip()
    if env:
        root = Path(env).expanduser()
        found = _model_in(root)
        if found is None:
            raise S.SrtError(
                "model-missing",
                f"{MODEL_ENV} 里没有完整模型: {root}",
                hint=f"需要 {', '.join(MODEL_FILES)} 三个文件。",
            )
        return found
    root = C.USER_DATA / "SupplysStore" / "local-asr-supplies"
    found = _model_in(root)
    if found is not None:
        return found
    hint = (
        "在剪映里用一次「字幕 → 智能识别 → 识别字幕」，让剪映下载本地 ASR 模型；"
        f"或设置 {MODEL_ENV} 指向模型目录"
    )
    raise S.SrtError("model-missing", "未找到剪映本地 ASR 模型", hint=hint)


def decode_audio(path: Path, ffmpeg: str) -> "object":
    np = Deps().np
    cmd = [
        ffmpeg, "-nostdin", "-v", "error", "-i", str(path),
        "-vn", "-ac", "1", "-ar", str(SAMPLE_RATE), "-f", "f32le", "pipe:1",
    ]
    try:
        proc = subprocess.run(cmd, capture_output=True, timeout=600)
    except subprocess.TimeoutExpired as exc:
        raise S.SrtError("decode-timeout", f"音频解码超过 600 秒: {path}") from exc
    if proc.returncode != 0:
        detail = proc.stderr.decode("utf-8", "replace").strip().splitlines()
        raise S.SrtError("decode-failed", detail[-1] if detail else "ffmpeg 解码失败")
    audio = np.frombuffer(proc.stdout, dtype=np.float32)
    if audio.size == 0:
        raise S.SrtError("empty-audio", f"解码后没有采样点: {path}")
    return audio


def _rms_frames(np, audio, frame: int):
    usable = audio.size // frame * frame
    if usable == 0:
        return np.zeros(0, dtype=np.float32)
    frames = audio[:usable].reshape(-1, frame).astype(np.float32)
    return np.sqrt((frames * frames).mean(axis=1))


def split_chunks(np, audio, sr: int = SAMPLE_RATE) -> list[tuple[int, int]]:
    """按静音切块，单块 8–28 秒；找不到静音时在能量最低点切。"""
    frame = int(sr * 0.03)
    rms = _rms_frames(np, audio, frame)
    total = audio.size
    if rms.size == 0:
        return [(0, total)]

    floor = float(np.percentile(rms, 20))
    threshold = max(1e-4, floor * 0.6)
    silent = rms < threshold
    silent_runs: list[tuple[int, int]] = []
    i = 0
    while i < silent.size:
        if not silent[i]:
            i += 1
            continue
        j = i
        while j < silent.size and silent[j]:
            j += 1
        if (j - i) * frame >= int(sr * 0.25):
            silent_runs.append((i * frame, j * frame))
        i = j

    chunks: list[tuple[int, int]] = []
    start = 0
    while start < total:
        end = min(start + int(CHUNK_MAX * sr), total)
        if end >= total:
            chunks.append((start, total))
            break
        lo = start + int(CHUNK_MIN * sr)
        candidates = [
            (a + b) // 2 for a, b in silent_runs
            if lo <= (a + b) // 2 <= end
        ]
        if candidates:
            cut = min(candidates, key=lambda x: abs(x - (start + int(CHUNK_MAX * sr / 2))))
        else:
            lo_frame = max(0, (lo - start) // frame)
            hi_frame = min(rms.size, (end - start) // frame)
            if hi_frame <= lo_frame:
                cut = end
            else:
                idx = lo_frame + int(np.argmin(rms[lo_frame:hi_frame]))
                cut = start + idx * frame
        if cut <= start:
            cut = end
        chunks.append((start, cut))
        start = cut
    return chunks


class Engine:
    def __init__(self, model_dir: Path, deps: Deps) -> None:
        self.np = deps.np
        self.knf = deps.knf
        self.model_dir = model_dir
        opts = deps.ort.SessionOptions()
        opts.log_severity_level = 3
        providers = ["CPUExecutionProvider"]
        self.encoder = deps.ort.InferenceSession(
            str(model_dir / "asr-model-encoder.onnx"), opts, providers=providers)
        self.decoder = deps.ort.InferenceSession(
            str(model_dir / "asr-model-decoder.onnx"), opts, providers=providers)
        meta = self.encoder.get_modelmeta().custom_metadata_map
        self.lfr_m = int(meta.get("lfr_window_size", "7"))
        self.lfr_n = int(meta.get("lfr_window_shift", "6"))
        self.neg_mean = self.np.array(
            [float(x) for x in meta["neg_mean"].split(",")], dtype=self.np.float32)
        self.inv_std = self.np.array(
            [float(x) for x in meta["inv_stddev"].split(",")], dtype=self.np.float32)
        self.vocab = self._load_vocab(model_dir / "asr-model-token.txt")

    def _load_vocab(self, path: Path) -> dict[int, str]:
        vocab: dict[int, str] = {}
        with path.open(encoding="utf-8") as fh:
            for line in fh:
                parts = line.rstrip("\n").rsplit(" ", 1)
                if len(parts) == 2:
                    vocab[int(parts[1])] = parts[0]
        return vocab

    def _fbank(self, audio):
        opts = self.knf.FbankOptions()
        opts.frame_opts.samp_freq = SAMPLE_RATE
        opts.frame_opts.dither = 0.0
        opts.frame_opts.snip_edges = True
        opts.frame_opts.window_type = "povey"
        opts.mel_opts.num_bins = 80
        opts.use_energy = False
        fbank = self.knf.OnlineFbank(opts)
        fbank.accept_waveform(SAMPLE_RATE, audio.astype(self.np.float32))
        fbank.input_finished()
        return self.np.stack(
            [fbank.get_frame(i) for i in range(fbank.num_frames_ready)]
        ).astype(self.np.float32)

    def _lfr(self, feats):
        np = self.np
        m, n = self.lfr_m, self.lfr_n
        total = feats.shape[0]
        out_len = int(math.ceil(total / n))
        left = np.tile(feats[0], ((m - 1) // 2, 1))
        feats = np.vstack((left, feats))
        total += (m - 1) // 2
        out = []
        for i in range(out_len):
            if m <= total - i * n:
                out.append(feats[i * n:i * n + m].reshape(-1))
            else:
                pad = m - (total - i * n)
                frame = feats[i * n:].reshape(-1)
                for _ in range(pad):
                    frame = np.hstack((frame, feats[-1]))
                out.append(frame)
        return np.vstack(out).astype(np.float32)

    def transcribe(self, audio):
        np = self.np
        feats = (self._lfr(self._fbank(audio)) + self.neg_mean) * self.inv_std
        speech = feats[None, :, :]
        lengths = np.array([feats.shape[0]], dtype=np.int32)
        enc, enc_len = self.encoder.run(
            None, {"speech": speech, "speech_lengths": lengths})
        logits, token_num, alphas, peaks = self.decoder.run(
            None, {"enc": enc, "enc_len": enc_len})
        ids = logits[0].argmax(-1)
        count = int(token_num[0])
        raw = [int(x) for x in ids[:count]]
        keep = [x for x in raw if x not in (0, 1, 2)]
        tokens = [self.vocab.get(x, "") for x in keep]
        tokens = [t for t in tokens if t and not (t.startswith("<") and t.endswith(">"))]

        fire = np.where(peaks[0] >= 1.0 - 1e-4)[0].astype(np.float64) - 1.5
        warnings = []
        raw_fire = len(fire)
        raw_tokens = len(tokens)
        if len(fire) != len(tokens) + 1:
            al = alphas[0]
            norm = al / (al.sum() / (len(tokens) + 1))
            integrate = 0.0
            rebuilt = []
            for idx, weight in enumerate(norm):
                integrate += float(weight)
                if integrate >= 1.0 - 1e-4:
                    rebuilt.append(float(idx))
                    integrate -= 1.0
            fire = np.array(rebuilt) - 1.5
        dropped = 0
        if len(fire) > len(tokens) + 1:
            fire = fire[:len(tokens) + 1]
        if len(fire) < len(tokens) + 1:
            dropped = len(tokens) - max(0, len(fire) - 1)
            tokens = tokens[:max(0, len(fire) - 1)]
        if raw_fire != raw_tokens + 1:
            warnings.append(
                f"cif-fire-mismatch: peaks={raw_fire}, tokens={raw_tokens}, "
                f"used_fire={len(fire)}, dropped_tokens={dropped}")

        spans = []
        for i in range(len(tokens)):
            start = max(0.0, float(fire[i]) * TIME_RATE)
            end = max(start, float(fire[i + 1]) * TIME_RATE)
            spans.append((start, end))
        return tokens, spans, warnings


def detokenize(tokens: list[str], spans: list[tuple[float, float]]):
    """合并 BPE 续接符，返回逐 token 的展示片段。"""
    out: list[tuple[str, float, float, bool]] = []
    for token, span in zip(tokens, spans):
        cont = token.endswith("@@")
        piece = token[:-2] if cont else token
        out.append((piece, span[0], span[1], cont))
    return out


DEFAULT_FILLERS = "嗯,呃,额,啊,哦,那个,就是说"


def _token_piece(token: str) -> str:
    return token[:-2] if token.endswith("@@") else token


def remove_fillers(tokens, spans, fillers):
    ordered = sorted((item for item in fillers if item), key=len, reverse=True)
    out_tokens = []
    out_spans = []
    index = 0
    while index < len(tokens):
        matched = 0
        for filler in ordered:
            acc = ""
            end = index
            while end < len(tokens):
                acc += _token_piece(tokens[end])
                if len(acc) > len(filler):
                    break
                if acc == filler:
                    matched = end - index + 1
                    break
                end += 1
            if matched:
                break
        if matched:
            index += matched
        else:
            out_tokens.append(tokens[index])
            out_spans.append(spans[index])
            index += 1
    return out_tokens, out_spans


MIN_SPEECH_RMS = 5e-4
MIN_TOKEN_RATE = 0.05


def speech_problem(audio_rms: float, duration: float, token_count: int,
                   max_cue_duration: float | None = None,
                   max_dur: float = 5.0) -> str | None:
    if duration <= 0:
        return "音频时长为 0"
    if audio_rms < MIN_SPEECH_RMS:
        return f"音频能量过低（RMS {audio_rms:.6f}），没有可识别语音"
    if duration >= 2.0 and token_count / duration < MIN_TOKEN_RATE:
        return (f"识别密度过低（{token_count} token / {duration:.1f}s）；"
                "更像静音、纯音乐或模型误触发")
    if max_cue_duration is not None and max_cue_duration > max(6.0, max_dur * 3):
        return (f"单条字幕跨度 {max_cue_duration:.1f}s，超过上限 "
                f"{max(6.0, max_dur * 3):.1f}s；拒绝把幻觉时间戳写成字幕")
    return None


def add_punctuation(cues):
    for index, cue in enumerate(cues):
        if index + 1 < len(cues):
            gap = cues[index + 1]["start"] - cue["end"]
            cue["text"] = cue["text"].rstrip("，。") + ("。" if gap > 0.6 else "，")
        else:
            cue["text"] = cue["text"].rstrip("，。") + "。"
    return cues


def group_cues(units, max_chars: int, max_dur: float, gap: float):
    cues: list[dict] = []
    text = ""
    start = end = None
    prev_cont = False
    for piece, s, e, cont in units:
        if not text:
            text, start, end = piece, s, e
            prev_cont = cont
            continue
        add_space = (
            not prev_cont
            and text[-1].isascii() and text[-1].isalnum()
            and piece[:1].isascii() and piece[:1].isalnum()
        )
        projected = text + (" " if add_space else "") + piece
        should_break = False
        if not prev_cont:
            if S.visible_len(projected) > max_chars:
                should_break = True
            elif end is not None and (e - start) > max_dur:
                should_break = True
            elif s - end > gap and S.visible_len(text) >= 4:
                should_break = True
        if should_break:
            cues.append({"text": text.strip(), "start": start, "end": end})
            text, start, end = piece, s, e
        else:
            text = projected
            end = e
        prev_cont = cont
    if text.strip():
        cues.append({"text": text.strip(), "start": start, "end": end})
    return cues


def transcribe_audio(audio, engine: Engine, np, deps: Deps):
    tokens: list[str] = []
    spans: list[tuple[float, float]] = []
    chunks = split_chunks(np, audio)
    warnings: list[str] = []
    for start, end in chunks:
        segment = audio[start:end]
        if segment.size < SAMPLE_RATE * 0.2:
            continue
        chunk_tokens, chunk_spans, chunk_warnings = engine.transcribe(segment)
        offset = start / SAMPLE_RATE
        for token, span in zip(chunk_tokens, chunk_spans):
            tokens.append(token)
            spans.append((span[0] + offset, span[1] + offset))
        warnings.extend(chunk_warnings)
    return tokens, spans, len(chunks), warnings


def cmd_local_asr(a) -> int:
    try:
        if a.max_chars < 1:
            raise S.SrtError("bad-max-chars", f"--max-chars 必须 ≥ 1，收到 {a.max_chars}")
        if not math.isfinite(a.max_dur) or a.max_dur <= 0:
            raise S.SrtError("bad-max-dur", f"--max-dur 必须是正数，收到 {a.max_dur}")
        if not math.isfinite(a.gap) or a.gap < 0:
            raise S.SrtError("bad-gap", f"--gap 必须是 ≥ 0 的有限数，收到 {a.gap}")
        audio_path = C.local_path(a.audio, field="音频路径")
        out_path = C.local_path(a.out, field="输出路径")
        if not audio_path.is_file():
            raise S.SrtError("file-not-found", f"音频不存在: {audio_path}")
        if out_path.exists():
            raise S.SrtError("out-exists", f"输出文件已存在: {out_path}",
                             hint="换一个 --out 路径；本技能不覆盖已有文件")
        if getattr(a, "json_out", None):
            json_path = C.local_path(a.json_out, field="JSON 输出路径")
            if json_path.exists():
                raise S.SrtError("out-exists", f"输出文件已存在: {json_path}",
                                 hint="换一个 --json-out 路径；本技能不覆盖已有文件")

        deps = Deps()
        model_dir = find_model_dir(a.model_dir)
        ff = C.resolve_ffmpeg()
        chosen = ff.get("chosen")
        if not chosen:
            raise S.SrtError("ffmpeg-missing", "未找到可用的 ffmpeg",
                             hint="安装 ffmpeg，或设置 JY_FFMPEG")
        t0 = time.time()
        audio = decode_audio(audio_path, chosen["path"])
        duration = audio.size / SAMPLE_RATE
        audio_rms = float(deps.np.sqrt(
            deps.np.mean(deps.np.square(audio.astype(deps.np.float64)))))
        if audio_rms < MIN_SPEECH_RMS:
            raise S.SrtError(
                "no-speech",
                f"音频能量过低（RMS {audio_rms:.6f}），没有可识别语音",
                hint="确认音轨不是静音；纯音乐也会被拒绝，不要硬出字幕。")
        engine = Engine(model_dir, deps)
        tokens, spans, chunk_count, warnings = transcribe_audio(audio, engine, deps.np, deps)
        token_count_before_fillers = len(tokens)
        if a.remove_fillers:
            fillers = {item.strip() for item in a.fillers.split(",") if item.strip()}
            tokens, spans = remove_fillers(tokens, spans, fillers)
        if not tokens:
            raise S.SrtError("no-speech", "本地 ASR 没有识别出任何 token",
                             hint="确认音频有语音，或先用剪映识别一次对比")
        problem = speech_problem(audio_rms, duration, token_count_before_fillers,
                                 max_dur=a.max_dur)
        if problem:
            raise S.SrtError("no-speech", problem,
                             hint="确认音频有连续语音；纯音乐/环境音不要硬出字幕。")
        units = detokenize(tokens, spans)
        cues = group_cues(units, a.max_chars, a.max_dur, a.gap)
        if a.punctuate:
            add_punctuation(cues)
        if not cues:
            raise S.SrtError("no-cues", "识别结果无法组成字幕 cue")
        max_cue_duration = max((cue["end"] - cue["start"] for cue in cues), default=0.0)
        problem = speech_problem(audio_rms, duration, token_count_before_fillers,
                                 max_cue_duration=max_cue_duration,
                                 max_dur=a.max_dur)
        if problem:
            raise S.SrtError("no-speech", problem,
                             hint="检查模型/音频；不要把单 token 拉成整段字幕。")
        ordered = checked_cues(cues, max_dur=max(a.max_dur + 0.5, 6.0),
                               max_chars=a.max_chars)
        lines = S.write_srt(cues, out_path)
        elapsed = round(time.time() - t0, 2)

        payload = {
            "srt": str(out_path),
            "lines": lines,
            "duration": round(duration, 3),
            "audio_rms": round(audio_rms, 6),
            "tokens": len(tokens),
            "chunks": chunk_count,
            "elapsed_seconds": elapsed,
            "model_dir": str(model_dir),
        }
        if getattr(a, "json_out", None):
            json_path = C.local_path(a.json_out, field="JSON 输出路径")
            json_path.parent.mkdir(parents=True, exist_ok=True)
            json_path.write_text(json.dumps({
                "schema": "jianying-local-asr/v1",
                "audio": str(audio_path),
                "model_dir": str(model_dir),
                "tokens": [{"text": t, "start": round(s, 3), "end": round(e, 3)}
                           for t, (s, e) in zip(tokens, spans)],
                "cues": cues,
            }, ensure_ascii=False, indent=2), encoding="utf-8")
            payload["json"] = str(json_path)
        evidence = {
            "ffmpeg": chosen.get("source"),
            "warnings": warnings,
            "deps": ["numpy", "onnxruntime", "kaldi_native_fbank"],
        }
        C.emit(C.ok(VERB, payload, evidence=evidence))
        return 0
    except S.SrtError as exc:
        C.emit(C.fail(VERB, exc.code, exc.detail, hint=exc.hint))
        return 1
    except C.MediaError as exc:
        C.emit(C.fail(VERB, exc.code, exc.detail, hint=exc.hint))
        return 1
    except Exception as exc:  # noqa: BLE001
        first = str(exc).splitlines()[0] if str(exc) else ""
        C.emit(C.fail(VERB, "local-asr-failed", f"{type(exc).__name__}: {first}"[:200]))
        return 1


def checked_cues(cues, *, max_dur, max_chars):
    ordered, issues = S.cue_issues(cues, max_dur=max_dur, max_chars=max_chars,
                                   check_overlap=False)
    if issues:
        raise S.SrtError(
            "srt-check",
            f"{len(issues)} 处字幕不合规：{'; '.join(issues[:3])}",
            hint="调大 --max-chars/--max-dur 后重试；ASR 失败不会写 SRT/JSON")
    return ordered


def main() -> int:
    ap = argparse.ArgumentParser(description="本地 Paraformer 识别字幕")
    ap.add_argument("--audio", required=True, help="音频或视频路径；用 ffmpeg 抽 16k 单声道")
    ap.add_argument("--out", required=True, help="输出 SRT")
    ap.add_argument("--json-out", default="", help="可选：输出逐 token 时间戳 JSON")
    ap.add_argument("--model-dir", default="", help="可选：指定本地 ASR 模型目录")
    ap.add_argument("--max-chars", type=int, default=16, help="单条字幕最大可见字符数")
    ap.add_argument("--max-dur", type=float, default=5.0, help="单条字幕最大时长（秒）")
    ap.add_argument("--gap", type=float, default=0.35, help="静音断句阈值（秒）")
    ap.add_argument("--remove-fillers", action="store_true",
                    help="删除常见口头禅；本地规则，不冒充剪映 AI 去水词")
    ap.add_argument("--fillers", default=DEFAULT_FILLERS,
                    help=f"逗号分隔的待删词，默认 {DEFAULT_FILLERS}")
    ap.add_argument("--punctuate", action="store_true",
                    help="按停顿启发式加逗号/句号；不冒充剪映 AI 标点")
    args = ap.parse_args()
    if not args.model_dir:
        args.model_dir = None
    return cmd_local_asr(args)


if __name__ == "__main__":
    raise SystemExit(main())
