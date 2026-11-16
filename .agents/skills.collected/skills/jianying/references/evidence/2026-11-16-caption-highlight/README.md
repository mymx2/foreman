# 2026-11-16 字幕/高亮/动画证据

本目录是对 `changelog.md` 1.2.2 中真机导出结论的原始产物归档。产物来自剪映 11.8.0.14778
的临时草稿；没有改用户草稿，没有下载会员/商业资源。

## 文件

| 文件 | 说明 |
|---|---|
| `caption-template-2s.png` | 免费“白字黑边”字幕模板，2.0s 抽帧，字幕文本 `这是字幕模板测试` 已进入模板 |
| `font-ref-1s.png` | 免费字体“毛笔行楷”通过 `resource_ref` 下载后构建，1.0s 抽帧可见书法字形与黑色描边 |
| `highlight.mp4` / `frames/highlight-1s.png` | 关键词高亮：`AI工具分享 AI时代` 两处 `AI` 为黄色粗体 |
| `text-anim.mp4` / `frames/text-anim-1.2s.png` | 免费文字动画“变色输入”，1.2s 抽帧显示“打字”双色动效 |
| `video-anim.mp4` / `frames/video-anim-0.3s.png` / `frames/video-anim-0.8s.png` / `frames/video-anim-1.5s.png` | 免费视频动画“翻入”：0.3s 黑场，0.8s 已出现画面，1.5s 完整；入场中间帧没有单独归档 |
| `packaging-plan.json` / `packaging.completion.json` / `frames/packaging-2s.png` / `frames/packaging-30s.png` | `jy.py packaging` 由 60s 视频、20 cue SRT、毛笔行楷、白字黑边、变色输入生成；2s 看标题，30s 看字幕模板 |
| `asr-60s.srt` / `asr-60s-tokens.json` | 本地 Paraformer 对 60s 音频的 SRT 与逐 token 时间戳 |
| `asr-36min.srt` | 本地 Paraformer 对 36 分钟音频的 SRT；原始统计为 7761 token / 513 cue / 145 块 / 219.7s |
| `asr-fillers.srt` | `--remove-fillers` 后的 60s SRT；规则删除默认口头禅，不冒充剪映 AI 去水词 |
| `plans-*.json` | 上述导出对应的临时计划；其中路径是当时本机缓存/素材路径，不能直接照抄 |

## 复现边界

- 证据只证明这些具体产物在 11.8 上导出成功，不证明所有模板/字体/动画都生效。
- `resource_ref` 在本轮之后改为只接受 id/md5/完整标题；旧计划里的短标题可能需要在 `resource resolve` 后改成完整标题。
- 本地 ASR 现在会在音频能量过低或识别密度过低时返回 `no-speech`，不再把静音/纯音乐写成字幕。
