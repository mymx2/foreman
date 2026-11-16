# 案例

所有案例只写临时目录，不启动剪映，不写用户草稿。运行：

```bash
python scripts/run_examples.py
```

| 案例 | 覆盖 | 依赖 |
|---|---|---|
| `01-build-text-draft.py` | 纯文字草稿 `build` + `inspect` | 无 |
| `02-srt-build-check.py` | `srt.build` + `srt.check` | 无 |
| `03-validate-example-plans.py` | 两个示例计划的结构校验 | 无 |
| `04-media-build.py` | 图片素材相对路径 `build` + 封面生成 | 本机 ffmpeg；缺失时 SKIP |
| `05-capability-report.py` | 只读能力矩阵：六域与状态边界 | 无（不启动剪映） |
| `06-freeze-workflow.py` | 定格工作流：抽帧图片插在前后视频段之间 | 本机 ffmpeg；缺失时 SKIP |
| `07-vertical-title-bgm.py` | 竖屏画布 + 标题/字幕双文字轨 + BGM | 本机 ffmpeg；缺失时 SKIP |
| `08-patch-copy.py` | `set_text` / `set_style` 改副本，原稿不变 | 无 |
| `09-publish-dry-run.py` | `publish` 演练：不复制、不改首页索引 | 无 |
| `10-srt-from-audio.py` | 按真实音频时长生成双行 SRT + `srt.check` | 本机 ffmpeg；缺失时 SKIP |
| `11-burn-subtitles.py` | 硬字幕烧录 + 时长漂移/可见 cue 验收 | 带 libass 的 ffmpeg；缺失时 SKIP |
| `12-advanced-fields.py` | crop/flip/reverse/mask/curve/color wheel + native 逃生舱 | 本机 ffmpeg；缺失时 SKIP |
| `13-multitrack-pip.py` | 多轨画中画 + 关键帧 + 蒙版 + 变速 | 本机 ffmpeg；缺失时 SKIP |
| `14-mask-title.py` | 蒙版 + 文字模板 + 背景/阴影/粗体 | 本机 ffmpeg；缺失时 SKIP |
| `15-text-effects.py` | 花字/气泡/文字动画 + 贴纸 | 无 |
| `16-transition-filter-effect.py` | 转场 + 滤镜 + 画面特效 + 色轮 | 本机 ffmpeg；缺失时 SKIP |
| `17-audio-mix.py` | BGM + 原声 + 淡入淡出 + 声道 + 音效 | 本机 ffmpeg；缺失时 SKIP |
| `18-spoken-piece.py` | 口播成片骨架：主轨 + 标题/字幕 + 画中画 + BGM | 本机 ffmpeg；缺失时 SKIP |
| `19-version-chain.py` | build → patch → version diff → restore，验证多版本递进 | 无 |
| `20-caption-template-highlight.py` | 字幕模板 `caption_template_info` + `caption_info` + 关键词高亮 | 无 |
| `21-auto-subtitles-transcode.py` | 已有 SRT 的 `auto-subtitles` 草稿 + 本地 ffmpeg 码率转码 | 本机 ffmpeg；缺失时 SKIP |

`04` 特意把计划放在 `plans/`、素材放在 `media/`，并从另一个工作目录启动，用来锁住
“相对路径以计划文件为基准”的约定；旧代码会把封面路径解析到当前工作目录。

`05` 只调用 `scripts/capability_probe.py`，检查 JSON schema、状态枚举与六域边界；
它不会连 bridge、不会读账号，也不会写用户草稿。能力矩阵与 `references/capabilities.md` 同步。

`06` 是**工作流级定格**：用 ffmpeg 从源视频抽一帧，把图片片段插在两个视频段之间，
结构上等价于“定格 1 秒”。它不写 native `freeze` 字段，也不声称剪映的“定格”按钮已被调用。

`07` 用来锁住三件事：画布尺寸独立于素材尺寸；标题和字幕可以各占一条文字轨；
同一素材的音轨可以单独作为 BGM。它不验证导出后的字体/像素，只验证草稿结构。

`08` 走 `patch --out` 副本路径：先改文字，再改字号/颜色，最后分别 `inspect` 原稿和副本。
它不测试 `--in-place`，因为原地改写用户草稿需要单独授权。

`09` 只做 dry-run：断言 `action=copy+register`、目标路径不存在、`root_meta_info.json`
字节不变。真正的 `--apply` 会复制并写索引，不在离线案例里执行。

`10` 不做语音识别：它读测试音轨的真实时长，把两行已有文案按字数分配到时间码，
再让 `srt.check` 检查行数/重叠。真正识别仍要回剪映「智能字幕」。

`11` 用外部 ffmpeg 的 `subtitles=` 滤镜烧录，检查 `drift_ok` 和 `cues_fully_visible`；
剪映自带 ffmpeg 没有 libass 时，案例按 `SKIP` 处理，不伪装成 PASS。

`13`–`18` 是**成片级结构案例**：只验证 build 后的轨道、材质桶、refs 和关键帧，不启动剪映、
不假装验证像素。真实成片导出后必须按 `references/limits.md` 抽帧/听音频验收。

`19` 是**版本链案例**：build 生成 `v001`，patch 副本生成 `v002` 并保留父版本、plan/ops 副本；
`version diff` 看到文字变化；`version restore` 回到 `v001` 生成新 `draft_id` 和新历史。它不启动剪映，
也不做像素 diff。

`15` 不依赖 ffmpeg：花字/气泡/动画/贴纸只需要文字与材质结构；资源 id 是示例占位，
真实使用必须换成本机已缓存资源。
