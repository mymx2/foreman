# 2026-11-16 变声材质验证

临时草稿：320×180 黑底 + 3s 440Hz 双声道音频，音频片段挂 `materials.audio_effects`；
资源为免费“萝莉”VC（`resource_id=7020345789599715848`），原生导出后解码 FFT 取峰值。

## 结果

| 材质 | 峰值 | 说明 |
|---|---|---|
| 旧材质 | 440.0 Hz | 只有 `resource_id`/`name`，缺 `path`、`sub_type`、参数索引；导出无效果 |
| 修复后 | 740.0 Hz | `sub_type=0`，补 `path`、`production_path` 和 `audio_adjust_params`（音调/音色，带 parameterIndex/min/max） |

旧代码输出 RMS 0.08779，新代码 0.03705；740Hz 对应 440Hz 上移 9 个半音，与资源
`mdsp_preset.json` 的 `Pitch Shift Semitone=9` 一致。

## 文件

- `audio-effect.mp4`：修复后真实导出（3s）
- `render.json`：脱敏后的 render 回执
- `pitch-probe.json`：FFT 峰值对比

这只证明“萝莉”这个资源在当前材质形状下生效；其他音效/变声资源仍需逐个听感验收。
