# 2026-11-16 审查后真机 build/render 复核

在剪映专业版 11.8.0.14778 上，用本技能当前代码构建一个临时草稿并原生导出。
没有打开/修改用户草稿，没有下载会员资源。

## 复现

- 测试素材：`ffmpeg testsrc2` 生成的 320×180 / 30fps / 2s 视频。
- 计划：视频主轨 + 文字“真机复核”，文字含 `highlight: {"words":["复核"]}`。
- 命令：`jy.py build --plan plan.json --out draft` → `jy.py render draft -o out.mp4`。
- 抽帧：`jy.py frame out.mp4 --at 1.0 -o frame-1s.png`。

## 结果

- `build`：`ok:true`，2 条轨道，`v001` 建立；`inputs` 只记录草稿目录外的 `main.mp4`，
  构建暂存目录里的 `draft_cover.jpg` 没有被误记成外部输入。
- `render`：`ok:true`，238,304B / 2.02s / 320×180 / H.264；回执挂在 `v001.exports`。
- `draft_mutated:true`，`draft_files_changed:["draft_content.json"]`；
  `draft_info.json` 的 before/after SHA 相同，所以本次没有生成 `editor-rewrite` 新版本。
  只有剪映重写 `draft_info.json` 时才走那条路径；`draft_content.json` 的回写已经进入
  `draft_files_changed` 和备份路径。
- `frame-1s.png` 可见文字“真机复核”和高亮样式，说明导出不是空片。

## 文件

| 文件 | 说明 |
|---|---|
| `out.mp4` | 本次真机导出的 2s 成片 |
| `frame-1s.png` | 1.0s 抽帧 |
| `render.json` | 脱敏后的 render 回执；本机临时根替换为 `<TEMP>`，安装目录替换为 `<LOCALAPPDATA>` |
| `option-probe.json` | 导出参数探测结果（见下） |
| `format-probe.json` | 视频/音频草稿的格式探测结果 |
| `cli-mov.json` / `cli-mp3.json` | 更新 CLI 后 `--format mov` / `--format mp3` 的真实回执 |

## 导出参数探测

对 `/custom-agent/film-export` 的 draftPath 请求体逐项追加字段：

- 基线：200，`943,778 bps`，238,304B / 2.02s。
- `options.bitrate`、`options.videoBitrate`、`exportOptions.bitrate`、
  `videoExportOptions.bitrate`、`outputs`：全部 409 `film_export_invalid_request`，不生成文件。

本机官方 agent 工具 `custom-agent.film-export.v1` 的 schema 中，视频输出只有
`format`（mp4/mov）、`fps`、`resolution`；`bitrate` 只用于音频输出（192/256/320 kbps）。
因此视频自定义码率不能通过当前 native draftPath 入口实现；分辨率/帧率改草稿画布，
码率需求走剪映客户端导出或导出后 ffmpeg 转码。

## 格式探测

- 视频草稿：`mp4`、`mov`、`gif` 均 200 并生成文件；`mp3`/`wav` 因无音轨返回
  `film_export_no_audio`。
- 音频草稿：`mp3`、`wav`、`aac`、`flac`、`aiff`、`ogg` 均 200 并生成文件。
- 更新后的 CLI 已支持这些格式；`--format mov` 回执 238,419B，`--format mp3` 回执 49,578B。

这次复核不证明 `editor-rewrite` 分支在真实剪映回写 `draft_info.json` 时的行为；该分支目前由
离线测试覆盖，需等到剪映实际改写 `draft_info.json` 时再验。
