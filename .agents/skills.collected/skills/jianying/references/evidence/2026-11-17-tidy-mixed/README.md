# 2026-11-17 tidy 中英混排词安全 + 单字伪影截短

## 背景

36 分钟技术分享会真实本地 ASR 产物（568 cue）暴露两个 tidy 缺陷：

1. 超宽行按字数硬切，中英混排没有空格可借，10 条拆分里 9 条切断英文词
   （excel→ex+cel、photoshop→p+hotoshop、potocraft→pot+ocraft）；
   烧录抽帧直接看到屏幕上只剩残词「ocraft」。
2. Paraformer 块边界把静音吞进单字时间戳：「验/的/嗯/然/改」5 个单字挂 6.10–9.04s，
   `srt.check` 报时长超标，旧 tidy 不处理时长，ASR → check 全绿链路不闭合。

## 复跑

```bash
python scripts/subtitles/cli.py srt.tidy --in input.srt --out new-tidy.srt --max-chars 16
python scripts/subtitles/cli.py srt.check --in new-tidy.srt
python check_quality.py input.srt new-tidy.srt 16
python check_quality.py input.srt old-tidy.srt 16   # 旧版对照，应失败
```

`old-tidy.srt` 由 1.2.2 快照产出（等分时间、无词安全、无截短）。

## 结果

| 断言 | 1.2.2 | 1.2.3 |
|---|---|---|
| ascii_runs_intact（英文词不被切断） | 失败：9 处残词 | 通过 |
| visible_chars_conserved_per_cue（逐 cue 文本守恒） | 通过 | 通过 |
| short_artifacts_capped（5 条单字伪影截到 1s） | 失败：0/5 | 通过：5/5 |
| check_thresholds_met（行宽/时长/重叠合规） | 失败：3 条超时长 | 通过 |

新版 tidy 回执：568 → 578 cue，`long_lines_split=10`、`short_artifacts_capped=5`；
`srt.check` ok、578 行、issues 为空。

拆分时间为可见字数比例（非 token 级）。与本会话交付成片所用的 token 级映射版本逐拆点
实测：词边界完全一致，但拆点时间最大差 1.246s（「呀然后豆包啊等等也是在天天修bug」一条，
cue 内语速不均时比例分配偏差最大），其余多在 0.35s 内。要 token 级精度用
`srt.from-local-asr --json-out` 自行映射；tidy 的比例时间是无 token 输入时的近似。