# 2026-11-16 真实 render 回归

在 Windows 剪映专业版 **11.8.0.14778** 上，用技能生成的临时草稿跑 `build → render → verify`。
草稿为 320×180 / 30fps / 1s：蓝色视频轨 + 0.1–0.9s 的文字“RENDER OK”。

## 结论

- `render`：ok，30,294B，1.021s，H.264+AAC；`draft_mutated:true`，`draft_files_changed:["draft_content.json"]`。
  剪映在导出期间写了 `draft_content.json`，验证了多文件回写检测；旧实现只比 `draft_info.json` 会误报未改写。
- `verify`：320×180 / 30fps / 1.021s；抽帧 0.2s、0.6s 可见文字，0.9s 文字结束、画面无文字。
- 安装指纹：`JianyingPro.exe` SHA-256 `bbe97bb4…`，`videoeditor.dll` SHA-256 `35d24d49…`；完整值见 `render.json`。
- 回执已把本机路径替换为 `<TEMP>` / `<LOCALAPPDATA>`，不含 token、cookie、账号。

## 文件

| 文件 | 说明 |
|---|---|
| `plan.json` | build 用的计划；素材路径是相对 `src.mp4` |
| `render.json` | 脱敏后的 render 回执（含 draft_files_changed、install 指纹、probe） |
| `frame-0.2.png` / `frame-0.6.png` | 文字可见 |
| `frame-0.9.png` | 文字已结束 |
| 成片 mp4 | 归档在仓库 `.agents/skills.collected/_evidence/jianying/2026-11-16-render-check/out.mp4` |

## 复现

先准备 `src.mp4`（320×180、1.2s、蓝色、440Hz 正弦；剪映自带 ffmpeg 没有 libx264，可用 `-c:v mpeg4 -c:a aac` 生成），放到本目录或改 `plan.json` 的 `path`。然后在技能根执行：

```powershell
python scripts/jy.py build --plan references/evidence/2026-11-16-render-check/plan.json `
  --out $env:TEMP\jy-render-check --force --no-cover
python scripts/jy.py render $env:TEMP\jy-render-check -o $env:TEMP\jy-render-check.mp4 --timeout 120
python scripts/jy.py verify $env:TEMP\jy-render-check.mp4 --expect-duration 1.0 --frames 0.2,0.6,0.9
```

`render` 需要剪映运行且 native bridge 可用；抽帧需要 ffmpeg（优先用剪映自带）。
