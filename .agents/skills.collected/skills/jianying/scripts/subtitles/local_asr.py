"""本地 ASR：用剪映已缓存的 Paraformer ONNX 模型生成带时间戳的字幕。

不登录、不联网、不调用剪映助手。模型来自剪映「字幕 → 智能识别 → 识别字幕」
首次使用时下载到 ``%LOCALAPPDATA%/JianyingPro/User Data/SupplysStore/local-asr-supplies``。
模型缺失时按 ``model-missing`` 失败，不自动下载。

同一个目录里还躺着剪映下发的其它资产，本文件按需使用：

* ``asr-punc.onnx`` / ``asr-punc-token.txt`` —— 真正的标点模型（``--punctuate``
  优先用它，缺失时才回落到按停顿的启发式）；
* ``strategy.json`` —— 剪映自己的 VAD 切块上下限，切块按它来，不再自拍 8–28 秒；
* encoder 的 ``custom_metadata_map`` —— 模型类型/版本/vocab/max_slice_duration，
  写进 evidence 当指纹，剪映换模型时能看出来。

依赖（可选，缺失时按 ``missing-dep`` 失败）：
    numpy onnxruntime kaldi-native-fbank

时间戳算法与 FunASR ``ts_prediction_lfr6_standard`` 一致：CIF peak 每 20ms
一个上采样帧，peak 过 1.0 的位置即 token 边界。模型 meta 给的
``timestamp_offset=-0.5`` 是 LFR 帧（60ms）单位，等价于这里的 1.5 个 20ms 帧。
"""

from __future__ import annotations

import argparse
import json
import math
import os
import re
import subprocess
import time
from pathlib import Path

import jy_common as C
import srt as S

VERB = "srt.from-local-asr"
MODEL_FILES = ("asr-model-encoder.onnx", "asr-model-decoder.onnx", "asr-model-token.txt")
PUNC_FILES = ("asr-punc.onnx", "asr-punc-token.txt")
QUALITY_FILE = "asr-model-classifier.onnx"
MODEL_ENV = "JY_LOCAL_ASR_DIR"
PUNC_ENV = "JY_LOCAL_ASR_PUNC_DIR"
SAMPLE_RATE = 16000
CHUNK_MIN = 10.0  # 剪映 strategy.json 的默认值，读不到时才用
CHUNK_MAX = 30.0
PUNC_WINDOW = 200  # punc 模型自带 split_size；超过就分段跑
PUNC_MAX_LENGTH = 199
PUNC_BREAK_CLASS = 2  # 导出后只有 3 类：0 占位、1 不断句、2 断句
PUNC_PERIOD_GAP = 0.6  # 断句点后面的静音超过这个长度就写句号，否则逗号
TIME_RATE = 10.0 * 6 / 1000 / 3  # 20ms，与 FunASR LFR6/upsample=3 一致
TIMESTAMP_BACKOFF = 1.5  # 等价于模型 meta 的 timestamp_offset=-0.5 个 LFR 帧


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


def _strategy_limits(model_dir: Path) -> tuple[float, float, str]:
    """读剪映下发的 strategy.json，拿官方 VAD 切块上下限。

    读不到、字段缺失或值不合理时回落到 CHUNK_MIN/CHUNK_MAX；第三个返回值
    记来源，写进 evidence——别让默认值冒充官方参数。
    """
    for base in (model_dir, model_dir.parent):
        path = base / "strategy.json"
        if not path.is_file():
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            continue
        vad = data.get("vad_strategy") if isinstance(data, dict) else None
        if not isinstance(vad, dict):
            continue
        try:
            low = float(vad.get("min_slice_duration"))
            high = float(vad.get("max_slice_duration"))
        except (TypeError, ValueError):
            continue
        if 0 < low < high <= 120:
            return low, high, str(path.name)
    return CHUNK_MIN, CHUNK_MAX, "default"


def find_punc_dir(model_dir: Path) -> Path | None:
    """标点模型目录：环境变量优先，其次和 ASR 模型同目录；缺失返回 None。"""
    env = os.environ.get(PUNC_ENV, "").strip()
    roots = ([Path(env).expanduser()] if env else []) + [model_dir]
    for root in roots:
        if all((root / name).is_file() for name in PUNC_FILES):
            return root
    return None


def model_manifest(model_dir: Path, punc_dir: Path | None, meta: dict) -> dict:
    """模型身份：文件大小 + 关键 meta，写进 evidence 当指纹。

    不算哈希：154 MB × 2 每个都要整读一遍，同尺寸换模型仍然认不出来；
    文件名集合、字节数、version/model_type 变了就足够提示「模型换过」。
    """
    pairs = [(model_dir, name) for name in MODEL_FILES]
    if punc_dir is not None:
        pairs.extend((punc_dir, name) for name in PUNC_FILES)
    files = []
    for base, name in pairs:
        try:
            size = (base / name).stat().st_size
        except OSError:
            size = None
        files.append({"name": name, "bytes": size})
    return {
        "model_type": meta.get("model_type"),
        "version": meta.get("version"),
        "vocab_size": meta.get("vocab_size"),
        "max_slice_duration": meta.get("max_slice_duration"),
        "files": files,
    }


class Punc:
    """剪映下发的标点模型：token 序列 → 每个 token 的标点类别。

    ONNX 只有 3 类；meta 的 ``punctuations`` 列了 6 个符号，但导出后只会
    给出「断句 / 不断句」，逗号还是句号由断句点后的静音长度决定。
    输入是 punc 自己的 27 万词表 id，和 ASR 的 8404 词表不是一套，按字符串对齐。
    """

    def __init__(self, model_dir: Path, deps: Deps) -> None:
        self.np = deps.np
        raw = (model_dir / PUNC_FILES[1]).read_text(encoding="utf-8").strip()
        self.vocab: dict[str, int] = {}
        for index, item in enumerate(raw.split("|")):
            self.vocab.setdefault(item, index)
        self.unk = self.vocab.get("<unk>", max(0, len(self.vocab) - 1))
        opts = deps.ort.SessionOptions()
        opts.log_severity_level = 3
        self.session = deps.ort.InferenceSession(
            str(model_dir / PUNC_FILES[0]), opts, providers=["CPUExecutionProvider"])

    def _ids(self, pieces: list[str]) -> list[int]:
        ids = []
        for piece in pieces:
            token = piece[:-2] if piece.endswith("@@") else piece
            for candidate in (token, token.lower(), token.strip()):
                if candidate and candidate in self.vocab:
                    ids.append(self.vocab[candidate])
                    break
            else:
                ids.append(self.unk)
        return ids

    def classes(self, pieces: list[str]) -> list[int]:
        np = self.np
        ids = self._ids(pieces)
        out: list[int] = []
        window_size = min(PUNC_WINDOW, PUNC_MAX_LENGTH + 1)
        for start in range(0, len(ids), window_size):
            window = ids[start:start + window_size]
            inputs = np.array([window], dtype=np.int32)
            lengths = np.array([len(window)], dtype=np.int32)
            logits, = self.session.run(
                None, {"inputs": inputs, "text_lengths": lengths})
            out.extend(int(value) for value in logits[0].argmax(-1)[:len(window)])
        return out


def build_seps(classes: list[int], spans: list[tuple[float, float]]) -> list[str]:
    """按断句类 + 断句点后的静音长度，给每个 token 挂一个标点。"""
    seps: list[str] = []
    for index, value in enumerate(classes):
        sep = ""
        if value == PUNC_BREAK_CLASS:
            if index + 1 >= len(spans):
                sep = "。"
            else:
                gap = spans[index + 1][0] - spans[index][1]
                sep = "。" if gap >= PUNC_PERIOD_GAP else "，"
        seps.append(sep)
    return seps


def _make_seps(tokens, spans, punc, enabled):
    """返回 (seps, source, breaks, detail)。

    模型缺失、加载失败或类别数对不上时回落到启发式，并把原因作为 detail
    交给调用方写进 warnings——不静默降级。
    """
    if not enabled:
        return [""] * len(tokens), "off", 0, ""
    if punc is None:
        return [""] * len(tokens), "heuristic", 0, ""
    try:
        classes = punc.classes(tokens)
    except Exception as exc:  # noqa: BLE001
        first = str(exc).splitlines()[0] if str(exc) else ""
        return [""] * len(tokens), "heuristic", 0, f"{type(exc).__name__}: {first}"[:160]
    if len(classes) != len(tokens):
        return ([""] * len(tokens), "heuristic", 0,
                f"class-count {len(classes)} != tokens {len(tokens)}")
    breaks = sum(1 for value in classes if value == PUNC_BREAK_CLASS)
    return build_seps(classes, spans), "model", breaks, ""


ITN_FILE = "asr-itn-fst.fst"
TAG_RE = re.compile(r"([a-z_]+) \{ (.*?) \}")
FIELD_RE = re.compile(r"([a-z_]+): \"([^\"]*)\"")


def _render_tag(name: str, body: str) -> str:
    fields = {key: value for key, value in FIELD_RE.findall(body)}
    if name == "char":
        return fields.get("value", "")
    if name == "date":
        return "".join(fields.get(key, "") for key in ("year", "month", "day"))
    if name == "time":
        hour = fields.get("hour", "")
        minute = fields.get("minute", "")
        if hour and minute.isdigit():
            return f"{hour}:{int(minute):02d}"
        return hour or "".join(fields.values())
    if "value" in fields:
        return fields["value"]
    return "".join(fields.values())


def render_tags(tagged: str) -> str:
    """把 WeTextProcessing 风格的 tag 流还原成纯文本。

    ``char { value: "今" }`` → ``今``；``date { year: "2026年" ... }`` → ``2026年11月18日``。
    tag 之间的空白只是分隔符，丢掉；tag 外的真实文本保留。
    """
    out: list[str] = []
    pos = 0
    for match in TAG_RE.finditer(tagged):
        gap = tagged[pos:match.start()].strip()
        if gap:
            out.append(gap)
        pos = match.end()
        out.append(_render_tag(match.group(1), match.group(2)))
    tail = tagged[pos:].strip()
    if tail:
        out.append(tail)
    return "".join(out)


class Itn:
    """剪映下发的 ITN FST（标准 OpenFST，539 KB），用 kaldifst 跑。

    只做确定性替换：日期/百分比/小数/量词会被转成阿拉伯数字，拿不准的表达
    （比如「早上八点」「第十个」）原样留在 char 里，不会被乱改。
    """

    def __init__(self, model_dir: Path) -> None:
        try:
            import kaldifst
        except ImportError as exc:
            raise S.SrtError(
                "missing-dep",
                "缺少 ITN 依赖: kaldifst",
                hint="pip install kaldifst",
            ) from exc
        path = model_dir / ITN_FILE
        if not path.is_file():
            raise S.SrtError("model-missing", f"没有 ITN FST: {path}",
                             hint="确认剪映已下载完整本地 ASR 资产")
        self.tn = kaldifst.TextNormalizer(str(path))

    def normalize(self, text: str) -> str:
        try:
            tagged = self.tn.normalize(text)
        except Exception:  # noqa: BLE001
            return text
        return render_tags(tagged)


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


def split_chunks(np, audio, sr: int = SAMPLE_RATE,
                 min_sec: float = CHUNK_MIN, max_sec: float = CHUNK_MAX,
                 max_pause: float = 0.6) -> list[tuple[int, int]]:
    """按静音分段（VAD 式），把连续语音合并成不超过 max_sec 的块。

    不能只按 8–30 秒窗口切：块**内部**的长静音同样会被 CIF 的最后一个 fire
    吞给前一个 token（本机实测「到」一个字挂了 4.0 秒）。所以先把静音之间的
    语音段切出来，再按「段间停顿 ≤ max_pause 才合并」拼块，段尾就是语音尾。

    min_sec 只用来给超长连续段做硬切的参考长度；合并时不强求凑满。
    """
    frame = int(sr * 0.03)
    rms = _rms_frames(np, audio, frame)
    total = audio.size
    if rms.size == 0:
        return [(0, total)]

    # 单帧 RMS 有毛刺（本机实测静音段偶发 0.003 的尖峰），先做 5 帧（150ms）平滑；
    # 阈值取 p20*1.5：原来的 p20*0.6 会被静音段自身的底噪顶穿，整段静音被判成语音，
    # CIF 把 3.8 秒静音全吞给前一个字（「到」挂了 4 秒）。
    smooth = np.convolve(rms, np.ones(5) / 5.0, mode="same")
    threshold = max(1e-4, float(np.percentile(smooth, 20)) * 1.5)
    silent = smooth < threshold
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

    segments: list[tuple[int, int]] = []
    cursor = 0
    for begin, stop in silent_runs:
        if begin > cursor:
            segments.append((cursor, begin))
        cursor = max(cursor, stop)
    if cursor < total:
        segments.append((cursor, total))
    if not segments:
        return [(0, total)]

    max_samples = int(max_sec * sr)
    pause_samples = int(max_pause * sr)
    chunks: list[tuple[int, int]] = []
    start, end = segments[0]
    for begin, stop in segments[1:]:
        if stop - start <= max_samples and begin - end <= pause_samples:
            end = stop
            continue
        chunks.append((start, end))
        start, end = begin, stop
    chunks.append((start, end))

    limited: list[tuple[int, int]] = []
    hard = int(max(min_sec, 1.0) * sr)
    for begin, stop in chunks:
        while stop - begin > max_samples:
            limited.append((begin, begin + max_samples))
            begin += max_samples
        if stop - begin > 0:
            limited.append((begin, stop))
    return limited or [(0, total)]


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
        # 质量打分器是可选资产：10.1 MB，输入 enc[512]，输出 [B,1]。
        # 分数含义剪映没有标定，只做横向比较/低分提示，不拿它做拦截。
        self.classifier = None
        self.quality_error = ""
        quality_path = model_dir / QUALITY_FILE
        if quality_path.is_file():
            try:
                self.classifier = deps.ort.InferenceSession(
                    str(quality_path), opts, providers=providers)
            except Exception as exc:  # noqa: BLE001
                self.quality_error = f"{type(exc).__name__}: {str(exc)[:120]}"
        meta = self.encoder.get_modelmeta().custom_metadata_map
        self.meta = dict(meta)
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

        fire = np.where(peaks[0] >= 1.0 - 1e-4)[0].astype(np.float64) - TIMESTAMP_BACKOFF
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
            fire = np.array(rebuilt) - TIMESTAMP_BACKOFF
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

        score = None
        if self.classifier is not None:
            try:
                out = self.classifier.run(None, {"enc": enc, "enc_len": enc_len})
                values = np.asarray(out[0], dtype=np.float64).reshape(-1)
                score = float(values[0]) if values.size else None
            except Exception as exc:  # noqa: BLE001
                warnings.append(f"quality-skip: {type(exc).__name__}: {str(exc)[:80]}")
        return tokens, spans, warnings, score


def detokenize(tokens: list[str], spans: list[tuple[float, float]],
               seps: list[str] | None = None):
    """合并 BPE 续接符，返回逐 token 的展示片段（含该 token 后面的标点）。"""
    seps = seps or [""] * len(tokens)
    out: list[tuple[str, float, float, bool, str]] = []
    for token, span, sep in zip(tokens, spans, seps):
        cont = token.endswith("@@")
        piece = token[:-2] if cont else token
        out.append((piece, span[0], span[1], cont, sep))
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
        already_period = cue["text"].endswith("。")
        text = cue["text"].rstrip("，。")
        if index + 1 < len(cues):
            gap = cues[index + 1]["start"] - cue["end"]
            mark = "。" if gap > 0.6 else "，"
        else:
            mark = "。"
        # 模型已经给了句号，就不要因为下一句接得紧就降级成逗号
        if already_period and mark == "，":
            mark = "。"
        cue["text"] = text + mark
    return cues


def _render_units(buf) -> str:
    text = ""
    prev_cont = False
    for piece, _s, _e, cont, sep in buf:
        add_space = (
            bool(text) and not prev_cont
            and text[-1].isascii() and text[-1].isalnum()
            and piece[:1].isascii() and piece[:1].isalnum()
        )
        text = text + (" " if add_space else "") + piece + sep
        prev_cont = cont
    return text


def _cue_from(buf) -> dict:
    return {"text": _render_units(buf).strip(),
            "start": buf[0][1], "end": buf[-1][2]}


def group_cues(units, max_chars: int, max_dur: float, gap: float):
    """按行宽/时长/停顿分条；宽度切分时优先退回最近的标点，别把词切两半。

    标点模型给了断句点，硬切在字数上限上就会出「再讨，/论一下」这种残词。
    超宽时先往回找最近一个带标点的 token，把 cue 断在标点上；只有找不到
    （或断出来的前半行太短）才退回按字数硬切。
    """
    cues: list[dict] = []
    buf: list = []
    min_head = max(3, min(6, max_chars // 3))
    for unit in units:
        if not buf:
            buf.append(unit)
            continue
        _piece, s, e, _cont, _sep = unit
        start, end = buf[0][1], buf[-1][2]
        projected = _render_units(buf + [unit])
        should_break = False
        by_pause = False
        if not buf[-1][3]:
            if S.visible_len(projected) > max_chars or (e - start) > max_dur:
                should_break = True
            elif s - end > gap and S.visible_len(_render_units(buf)) >= 4:
                should_break = True
                by_pause = True
        if not should_break:
            buf.append(unit)
            continue
        cut = len(buf)
        if not by_pause and not buf[-1][4]:
            for index in range(len(buf) - 1, 0, -1):
                if not buf[index][4]:
                    continue
                if S.visible_len(_render_units(buf[:index + 1])) >= min_head:
                    cut = index + 1
                    break
        head, tail = buf[:cut], buf[cut:]
        if head:
            cues.append(_cue_from(head))
        buf = tail + [unit]
    if buf:
        cues.append(_cue_from(buf))
    return cues


def transcribe_audio(audio, engine: Engine, np, deps: Deps,
                     chunk_min: float = CHUNK_MIN, chunk_max: float = CHUNK_MAX):
    tokens: list[str] = []
    spans: list[tuple[float, float]] = []
    chunks = split_chunks(np, audio, min_sec=chunk_min, max_sec=chunk_max)
    warnings: list[str] = []
    qualities: list[float] = []
    for start, end in chunks:
        segment = audio[start:end]
        if segment.size < SAMPLE_RATE * 0.2:
            continue
        chunk_tokens, chunk_spans, chunk_warnings, chunk_quality = engine.transcribe(segment)
        offset = start / SAMPLE_RATE
        for token, span in zip(chunk_tokens, chunk_spans):
            tokens.append(token)
            spans.append((span[0] + offset, span[1] + offset))
        warnings.extend(chunk_warnings)
        if chunk_quality is not None:
            qualities.append(chunk_quality)
    return tokens, spans, len(chunks), warnings, qualities


def quality_summary(scores) -> dict:
    """质量分只做描述：分数含义未标定，不给阈值、不拦截。"""
    values = [round(float(x), 4) for x in scores]
    if not values:
        return {"source": "absent", "chunks": [], "min": None, "mean": None}
    return {
        "source": "model",
        "chunks": values,
        "min": min(values),
        "mean": round(sum(values) / len(values), 4),
    }


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
        chunk_min, chunk_max, chunk_source = _strategy_limits(model_dir)
        punc_dir = find_punc_dir(model_dir) if a.punctuate else None
        punc = None
        punc_error = ""
        if punc_dir is not None:
            try:
                punc = Punc(punc_dir, deps)
            except Exception as exc:  # noqa: BLE001
                first = str(exc).splitlines()[0] if str(exc) else ""
                punc_error = f"load {type(exc).__name__}: {first}"[:160]
        itn = None
        itn_error = ""
        if getattr(a, "itn", False):
            try:
                itn = Itn(model_dir)
            except S.SrtError as exc:
                itn_error = exc.detail
            except Exception as exc:  # noqa: BLE001
                itn_error = f"load {type(exc).__name__}: {str(exc)[:120]}"
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
        tokens, spans, chunk_count, warnings, qualities = transcribe_audio(
            audio, engine, deps.np, deps,
            chunk_min=chunk_min, chunk_max=chunk_max)
        quality = quality_summary(qualities)
        if engine.classifier is None and engine.quality_error:
            warnings.append(f"quality-skip: {engine.quality_error}")
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
        seps, punc_source, break_count, punc_detail = _make_seps(
            tokens, spans, punc, a.punctuate)
        for detail in (punc_error, punc_detail):
            if detail:
                warnings.append(f"punc-fallback: {detail}")
        units = detokenize(tokens, spans, seps)
        cues = group_cues(units, a.max_chars, a.max_dur, a.gap)
        if a.punctuate:
            add_punctuation(cues)
        itn_changes = 0
        if itn is not None:
            for cue in cues:
                before = cue["text"]
                after = itn.normalize(before)
                if after != before:
                    itn_changes += 1
                    cue["text"] = after
        elif itn_error:
            warnings.append(f"itn-skip: {itn_error}")
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
            "punc": {"source": punc_source, "breaks": break_count},
            "chunk_policy": {"min": chunk_min, "max": chunk_max,
                             "source": chunk_source},
            "model": model_manifest(model_dir, punc_dir, engine.meta),
            "quality": quality,
            "itn": {
                "source": "model" if itn is not None else
                          ("off" if not getattr(a, "itn", False) else "unavailable"),
                "changed": itn_changes,
            },
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
            "deps": ["numpy", "onnxruntime", "kaldi_native_fbank"]
                    + (["kaldifst"] if itn is not None else []),
            "punc_model": str(punc_dir / PUNC_FILES[0]) if punc_dir else None,
            "punc_source": punc_source,
            "chunk_policy_source": chunk_source,
            "model_version": engine.meta.get("version"),
            "quality_source": quality["source"],
            "itn_source": "model" if itn is not None else "off",
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
                    help="优先用剪映下发的 asr-punc.onnx 断句；模型缺失时"
                         "回落到按停顿的启发式")
    ap.add_argument("--itn", action="store_true",
                    help="用剪映下发的 asr-itn-fst.fst 把中文数字/日期/百分比转成"
                         "阿拉伯数字；需要 kaldifst，FST 缺失时跳过并记 warning")
    args = ap.parse_args()
    if not args.model_dir:
        args.model_dir = None
    return cmd_local_asr(args)


if __name__ == "__main__":
    raise SystemExit(main())
