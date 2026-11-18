# 字幕 Playbook

字幕是六域之一，不是默认主线。用户没有明确要求字幕/SRT 时，不要生成。本域分三条路：

1. **本地 ASR**：视频/音频有语音、没有文案，用剪映已下载的本地 Paraformer 模型识别；
2. **SRT 入轨**：已有 SRT 写进草稿 text 轨，继续改字、改样式、出下一版；
3. **已有文案**：只做时间码分配，或用外部 ffmpeg 烧硬字幕。

## 1. 先确认素材

| 用户给了什么 | 走哪条 |
|---|---|
| 视频/音频，没有文案 | `srt.from-local-asr`；模型缺失时回退剪映「识别字幕」导出 SRT |
| 已有 SRT | `srt.tidy` / `srt.check`，再 `add_subtitles` 入轨 |
| 已有 ASS/SSA | `jy.py ass import` 转 build 计划；或 `jy.py ass export` 从草稿导出 |
| 文案 + 每句时长/总时长 | `srt.build` 或 text 轨 |
| 文案 + 音频 | `srt.from-audio` |
| 文案 + 逐句音频目录 | `srt.from-segments --by-line` |
| 要字幕烧进画面 | `burn`（需带 libass 的 ffmpeg） |

## 2. 本地 ASR

前置条件：

- 剪映里至少用过一次「字幕 → 智能识别 → 识别字幕」，让剪映把本地模型下载到
  `%LOCALAPPDATA%\JianyingPro\User Data\SupplysStore\local-asr-supplies`；
- Python 依赖：`numpy`、`onnxruntime`、`kaldi-native-fbank`（缺失时命令按 `missing-dep` 失败）。

```bash
python scripts/subtitles/cli.py srt.from-local-asr \
  --audio in.mp4 --out out.srt --json-out out.json
# 可选：本地规则去口头禅 + 按停顿加标点（不是剪映 AI）
python scripts/subtitles/cli.py srt.from-local-asr \
  --audio in.mp4 --out out.srt --remove-fillers --punctuate
```

- `--remove-fillers` 删除默认的“嗯/呃/额/啊/哦/那个/就是说”，可用 `--fillers a,b,c` 覆盖；
- `--punctuate` 优先用剪映下发的 `asr-punc.onnx` 断句：模型给断句点，断句点后静音
  ≥0.6 秒写句号、否则写逗号；模型缺失或加载失败才回落到按停顿的启发式，并在
  `evidence.warnings` 记 `punc-fallback`，回执 `punc.source` 说明这次用的是 `model` 还是 `heuristic`；
- `--itn` 用剪映下发的 `asr-itn-fst.fst`（标准 OpenFST，539 KB）做数字规范化：
  需要额外装 `kaldifst`，`二零二六年十一月十八日 → 2026年11月18日`、
  `百分之五十 → 50%`、`下午三点半 → 下午3:30`；拿不准的表达（`早上八点`、`第十个`）
  原样保留；FST 或依赖缺失时跳过并写 `itn-skip` warning，回执 `itn.source` 标注；
- 回执 `quality` 来自剪映的 `asr-model-classifier.onnx`（`enc[512] → [B,1]`）：
  按块给分，**分数含义剪映没有标定**，只做块间相对比较（本机实测正常语句块 0.80–0.86，
  短块会掉到 0.04–0.23）；不要拿它做拦截阈值；
- 模型发现：默认查剪映用户数据；可用 `JY_LOCAL_ASR_DIR` 指向其他模型目录，
  `JY_LOCAL_ASR_PUNC_DIR` 单独指向标点模型目录；标点模型和 ASR 模型同目录时自动启用；
- 不登录、不联网、不调用剪映助手，也不消耗云端识别额度；模型来自剪映自己的本地缓存；
- 切块先按静音分段（VAD 式）：帧 RMS 做 150ms 平滑、阈值取 `p20*1.5`，
  段间停顿 ≤0.6 秒才合并，单块不超过 `strategy.json` 的 `max_slice_duration`（本机 30 秒）；
  这样块内不会夹着长静音，CIF 也就不会把静音吞给前一个字（此前实测「到」一个字挂 4 秒、
  单字挂 6–9 秒，只能靠 `srt.tidy` 截到 1 秒遮住）；`chunk_policy.source` 是
  `strategy.json` 才代表官方参数；
- 输出 SRT 和逐 token JSON（`jianying-local-asr/v1`）；默认 16 字/5 秒一条；
- 回执 `model` 带模型类型/版本/各文件字节数，剪映换了模型能看出来，别把它当性能指标；
- 36 分钟、7761 token 的本机实测约 220 秒，145 个块；
- 识别结果是中文/英文 Paraformer；标点来自剪映本地标点模型（不是云端 AI），
  不包含翻译、划重点、去水词；
- 模型或依赖缺失时明确失败，不自动下载、不伪造结果。

验收：ASR 回执自带的行宽/时长 warnings 先过 `srt.tidy` 规范化，再跑 `srt.check` 要求全绿，
再抽帧/对时；字幕文字明显错时用 `add_subtitles` 入轨后
`set_text` 改，不要在 SRT 上反复覆盖重生成。

## 3. SRT 入轨与版本化

### ASS/SSA 交换

```bash
python scripts/jy.py ass import subs.ass --out ass-plan.json
python scripts/jy.py ass export <draft> --out subs.ass
```

- 支持事件时间、基础样式和常用内联标签：`\c`/`\1c`、`\fs`、`\b`/`\i`/`\u`、`\r`；
  其他标签不静默改写，回执会在 `unsupported_tags` 里列出；
- `ass import` 生成单 text 轨的 `jianying-plan/v1`，区间样式写 `range_styles`；`ass export` 读文字轨写 ASS；
- 离线往返已验证，未做 libass 烧录比对；需要硬字幕仍走 `burn`。

```json
[
  {
    "op": "add_subtitles",
    "srt": "out.srt",
    "name": "字幕",
    "style": {
      "font_size": 8,
      "color": "#FFFFFF",
      "stroke_color": "#000000",
      "stroke_width": 0.05,
      "y": -0.72
    }
  }
]
```

```bash
python scripts/jy.py patch <draft> --ops ops.json --out <副本>
# 或直接改本技能草稿并生成下一版：
python scripts/jy.py patch <draft> --ops ops.json --in-place --version-label "add-subtitles"
```

- `add_subtitles` 新建/替换名为 `name` 的 text 轨；同名轨会被整体替换，旧素材按引用回收；
- SRT 必须不重叠、结束时间不超过草稿现有内容 1 秒以上，否则 `VALIDATION`；
- 支持的 `style`：`font_size`、`color`、`stroke_color`、`stroke_width`、`align`、
  `line_spacing`、`letter_spacing`、`bold`、`italic`、`underline`、`background`、
  `shadow`、`highlight`、`line_max_width`、`font_path`、`y`、`x`、`transform`、`scale`、
  `rotation`、`opacity`、`caption_template`、`subtitle_template`；模板需显式 `resource_id`/`path`，
  每个 cue 会自动生成 `segment.caption_info`；
- `text_template` / `template` / `text_effect` / `effect` / `text_glow` / `text_bubble` /
  `bubble` / `animations` / `native` / `resource_ref` 依赖缓存资源或 build 解析，`add_subtitles`
  明确拒绝；需要时用 `build` 的 text 轨写入并做真实导出验收；
- 每次 `patch` 自动写下一版；之后用 `set_text` / `set_style` 改具体 cue，
  `version diff` 看结构变化，`render` 后把成片挂到当前版本；
- 改 cue 的 `segment` id 从 `draft_info.json` 或 `inspect` 的 `texts` 顺序对应，
  不要把不同版本的 id 混用。

### 字幕模板

免费字幕模板可以程序化下载，并绑定到字幕文本：

```bash
python scripts/jy.py resource download "白字黑边" --apply
```

计划里的文字片段写：

```json
{
  "text": "这是字幕模板测试",
  "start": 1, "duration": 3, "y": -0.7,
  "caption_template": {"resource_ref": "白字黑边", "resources": []},
  "caption_info": {
    "id": "caption-1", "speaker_type": "", "speaker_id": "",
    "caption_segment_id": "seg-1", "original_text": "这是字幕模板测试",
    "words": [{"id": "word-1", "text": "这是字幕模板测试", "tag": "",
               "origin_text": "这是字幕模板测试",
               "time_range": {"start": 0, "duration": 3000000}}]
  }
}
```

`caption_template` 会写进文字材质的 `caption_template_info` 和 `recognize_text`；
`caption_info` 写到 `segment.caption_info`，`words[].time_range` 用微秒。只有 `text_template`
会尝试从模板目录的 `content.json` 派生 `caption_duration_info`，不要混淆。
2026-11-16 用免费“白字黑边”真实导出，cue 文本已进入模板。模板依赖的字体/花字资源仍需缓存；
模板字号/间距可能覆盖片段基础样式，按模板调整 `font_size` 或换更短文案。

## 4. 草稿文字轨

```json
{"type": "text", "segments": [
  {"text": "第一句", "start": 0.2, "duration": 2.0,
   "font_size": 8, "color": "#FFFFFF", "stroke_width": 0.05, "y": -0.72},
  {"text": "第二句", "start": 2.2, "duration": 1.8,
   "font_size": 8, "y": -0.72}
]}
```

- 文字素材必须是 `type:"text"`，不是 `subtitle`；
- 底部字幕 `y: -0.7` 左右；标题单独一轨，不要和字幕同轨；
- 同轨多段按时间切换，不要重叠；
- 文字背景/阴影用 `background` / `shadow`，见 [plan-schema](../plan-schema.md)。

## 5. SRT 生成

```bash
python scripts/subtitles/cli.py srt.build --text lines.txt --total 12 --out out.srt
python scripts/subtitles/cli.py srt.from-audio --audio voice.m4a --text lines.txt --out out.srt
python scripts/subtitles/cli.py srt.from-segments --segments segs/ --text lines.txt --by-line --out out.srt
```

- `srt.build` 按总时长均分；默认 gap 0.06s（与 `srt.tidy` 相同），可显式传 `--gap`；
- `srt.from-audio` 按音频真实时长分配；
- `srt.from-segments` 按逐句音频时长，`--by-line` 表示每行对应一个片段；
- 三者都只做**已有文案**的时间码分配，不做识别。

## 6. 规范化与校验

```bash
python scripts/subtitles/cli.py srt.tidy --in in.srt --out out.srt
python scripts/subtitles/cli.py srt.check --in out.srt
```

`srt.tidy` 做四件事：超宽行拆分、单字伪影截短、保底时长、修重叠。

- 超宽行按 `--max-chars`（默认 18）拆。中英混排没有空格可借，硬切点落在英文词内部时
  回退到词起点（词内撇号/连字符如 don't、state-of-the-art 不算边界），避免 excel 被切成
  ex+cel 这类残词；拆出各段按可见字数比例分配原 cue 时长。英文词本身比 `--max-chars` 长、
  或词起点前不足半行宽时仍硬切，这是最后手段。
- 单字/双字 cue 时长超过 `--max-dur`（默认 6s，与 check 同阈值）视为 ASR 块边界伪影
  （Paraformer 把静音吞进单字时间戳），截到 1s 显示、文字不动；回执 `short_artifacts_capped` 计数。
  截短只压不抬（原时长不足 1s 时保持原样），且优先于 `--min-dur` 保底——伪影 cue 不会被抬回静音里。
  超宽行拆出来的单字/双字段同样适用截短。
- 多字 cue 超 `--max-dur` 不在 tidy 处理范围：check 仍会报，调 ASR `--gap` 重识别或手工拆。
- 拆分时间是字数比例，不是 token 级精确：cue 内语速不均时拆点可偏 1s 以上（实测最大 1.246s，
  见仓库外证据归档）。
  要 token 级对齐用 `srt.from-local-asr --json-out` 的逐 token 时间自行映射。

`srt.check` 看 `ok`、`lines`、`issues`：

- 0 行、负/零时长、时间码倒置、越界 → 失败；
- 行宽/时长不合规 → 报 issue；
- 重叠 cue：`srt.check` 默认报告，但 `burn` **允许**重叠（同屏双人/双语上下行）；
  `add_subtitles` 不允许同轨重叠，入轨前先 `srt.tidy`。

## 7. 硬字幕烧录

```bash
python scripts/subtitles/cli.py burn --video in.mp4 --srt out.srt --out burned.mp4
```

- 需要带 `libass` 的外部 ffmpeg；剪映自带 ffmpeg 不支持 `subtitles` 滤镜；
- 先跑 `python scripts/jy.py probe`，看 `subtitle_ffmpeg.subtitle_burn_in`；为 true 即可烧；
- 装了 `imageio-ffmpeg` Python 包时，技能会自动发现其自带 ffmpeg（7.1 essentials 带 libass），不用设 `JY_FFMPEG`；
- 其他情况把 `JY_FFMPEG` 指到 full 构建；
- 回执看 `drift_ok=true`，再抽帧确认字幕不是方块、位置正确；
- 烧录是有损转码，保留原视频。

## 8. 口播成片

口播视频建议结构：

| 轨 | 内容 |
|---|---|
| 主轨 | 口播视频，原声保留 |
| 文字轨 A | 大标题（开头 3s） |
| 文字轨 B | 逐句字幕（按语音时间） |
| 画中画 | 补充画面/产品图 |
| 音频轨 | BGM（音量 0.2–0.35） |

参考 `examples/18-spoken-piece.py`。字幕时间来自本地 ASR、已有文案或剪映导出的 SRT。

## 9. 验收

1. `srt.check`：`ok:true`、`lines>0`、`issues=[]`；
2. 烧录：`drift_ok=true`，抽帧看字形/位置/遮挡；
3. 草稿字幕：`render` 后抽 3 帧，看每句切换时间与底部安全区；
4. 字幕是方块：`content` JSON 坏了或字体路径不存在；留空用默认字体；
5. 本地 ASR 任务：检查 `srt.from-local-asr` 的 `tokens`、`chunks`、`warnings`，
   抽帧确认字幕在说话时出现、静音时消失。

## 10. 案例

- `examples/02-srt-build-check.py`：SRT 生成 + 校验；
- `examples/10-srt-from-audio.py`：按音频时长；
- `examples/11-burn-subtitles.py`：硬字幕烧录；
- `examples/18-spoken-piece.py`：口播字幕轨 + 标题 + BGM。
