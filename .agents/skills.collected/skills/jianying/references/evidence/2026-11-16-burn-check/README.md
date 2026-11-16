# 2026-11-16 硬字幕烧录回归

用 `imageio-ffmpeg` 自带的 ffmpeg 7.1（gyan.dev essentials build，带 libass 与 libx264）把 6 条中文 SRT 烧进 30 秒无字幕片段。

- 输入：原视频前 30 秒（2160×1080 / 30fps，无字幕）
- 字幕：`demo.srt`（6 条示例，`srt.check` 通过）
- 结果：`burn` ok，878.1KB，30.067s，`drift_ok:true`，6/6 cue 完整可见，字体 Microsoft YaHei
- 回执：`burn.json`（路径已脱敏）
- 抽帧：`burned-16s.png`（第 4 条字幕）
- 成片：仓库 `.agents/skills.collected/_evidence/jianying/2026-11-16-burn-check/burned-30s.mp4`

## 复现

1. `python scripts/jy.py probe`，确认 `subtitle_ffmpeg.subtitle_burn_in=true`。装了 `imageio-ffmpeg` 时会自动选中它自带的 ffmpeg；否则把 `JY_FFMPEG` 指到带 libass 的 full 构建。
2. 截取片段：`ffmpeg -ss 0 -t 30 -i <video> -c copy src-30s.mp4`
3. 烧录：`python scripts/subtitles/cli.py burn --video src-30s.mp4 --srt demo.srt --out burned-30s.mp4`
4. 验收：`drift_ok=true`、`cues_truncated=0`，并抽帧确认字形与位置。

剪映自带 ffmpeg 没有 libass，不能烧字幕。
