# 2026-11-16 声道映射验证

剪映 11.8.0.14778，临时草稿，左-only 源 `left-only.wav`，原生导出后用 ffmpeg
解码为双声道 f32le，计算左右 RMS/dBFS。

## 结果

| `materials.sound_channel_mappings[].audio_channel_mapping` | 左 dBFS | 右 dBFS | 结论 |
|---|---|---|---|
| 0 | -11.01 | -240.00 | 保持原样，右侧静音 |
| 1 | -11.03 | -11.03 | 左声道复制到双声道 |
| 2 | -240.00 | -240.00 | 取右声道，源右侧静音 |
| 3 | -11.01 | -240.00 | 未按左右模式处理 |

当前技能代码构建 `channel: 1` 的草稿并导出，复测为左右均 -11.03dB；
回执见 `render.json`，成片见 `channel-1.mp4`。

去重：`segment.sound_channel_mapping` 只保留材质 id；真正生效的是
`materials.sound_channel_mappings[].audio_channel_mapping` 和 `is_config_open`。
