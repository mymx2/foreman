# 2026-11-16 一键字幕 + 本地转码验证

临时目录里的 2s 测试视频，已有 SRT，执行：

```bash
jy.py auto-subtitles --video main.mp4 --srt subs.srt --out draft --plan-out plan.json --title 自动字幕 --no-cover
jy.py transcode main.mp4 -o transcode.mp4 --video-bitrate 500k --audio-bitrate 96k
```

## 结果

- `auto-subtitles`：生成 2.5s 可编辑草稿，2 条字幕轨、1 条主视频轨；`v001` 带 `subtitle-workflow` 标签和 plan 副本。
- `transcode`：本机完整 ffmpeg（不是剪映自带裁剪版）输出 86,879B / 2.0s / 320×180 / H.264；
  明确是后处理转码，不是剪映原生码率参数。
- 两个命令的 JSON 回执见本目录。
