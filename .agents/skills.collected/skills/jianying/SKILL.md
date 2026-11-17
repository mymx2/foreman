---
name: jianying
description: 在 Windows 上驱动剪映专业版（JianyingPro）完成可复现的剪辑、合成、特效、音频、字幕与交付：生成多轨明文草稿（视频/图片/文字/字幕/BGM/关键帧/变速/音量/裁剪/翻转/倒放/蒙版/曲线变速/色轮/文字动画/文字背景阴影/贴纸/画面特效/音频淡入淡出）、读取与修改已有明文草稿、调用剪映原生引擎导出视频/音频/动图（mp4/mov/gif/mp3/wav/aac/flac/aiff/ogg）、ffprobe 与抽帧验收，以及把草稿登记到剪映首页。草稿自带可递进的版本链（快照、结构 diff、恢复新分支），不是一次性成片。也包含剪映本地 Paraformer ASR、SRT 生成/规范化/校验、SRT 入轨与版本化编辑、硬字幕烧录工具，以及只读能力矩阵/资源预检（区分已实现、未验收、资源缺失、宿主专属、账号受限）。用户提到剪映、JianyingPro、剪映草稿、draft_info.json、剪映导出/渲染、剪映字幕、本地 ASR、识别字幕、SRT 对齐、SRT 入轨、字幕版本、剪映多轨、关键帧、变速、BGM、裁剪、蒙版、曲线变速、文字动画、文字背景、贴纸、画面特效、音频淡入淡出、修改剪映草稿、剪映多版本/版本回退、把草稿放进剪映首页、剪映能力/支持哪些效果时使用。未在非 11.8 版本验证；不适用于剪映模板创作、AI 成片、云端素材下载、会员素材解锁、手机端剪映、CapCut 国际版。
when_to_use: 剪映, 剪映专业版, JianyingPro, 剪映草稿, draft_info.json, 剪映导出, 剪映渲染, 剪映字幕, 本地 ASR, 识别字幕, SRT, SRT 入轨, 字幕版本, 字幕对齐, 字幕烧录, 剪映多轨, 剪映 BGM, 关键帧, 变速, 裁剪, 蒙版, 曲线变速, 文字动画, 文字背景, 贴纸, 画面特效, 音频淡入淡出, 修改剪映草稿, 剪映版本, 剪映多版本, 版本回退, 版本 diff, 剪映首页登记
version: 1.2.5
updated: 2026-11-17
---

# 剪映剪辑、合成与交付

剪映没有稳定的外部剪辑 API。官方 `jianying-agent-cli.exe` 需要宿主令牌（只在 Agent Runtime 会话内运行）；
`lyra-cli` 用进程祖先校验（外部 shell 得到 `unauthorized host process`）。两者都不作为外部入口；
外部调用还会看到 `PERMISSION_DENIED`。本技能以 **Windows 剪映 11.8.0.14778** 为基线；
2026-11-15 已在临时多轨草稿上完成 `build` → `render` → `verify`，并对文字背景/阴影、独立音频轨淡入淡出
做过真实导出抽帧/波形验收；2026-11-16 又用 320×180 临时草稿复验 `render`，确认剪映会回写
`draft_content.json`（证据：`references/evidence/2026-11-16-render-check/`）。走两条路：

1. **明文草稿**：直接写 `draft_info.json`，剪映可打开、可继续编辑；
2. **本地 native bridge**：调用剪映自己的导出引擎出 MP4，再用 ffprobe 与抽帧验收。

`references/upstream.md` 记录了 skills.sh 候选与本地参考仓库的取舍。`jianying-headless-windows`
（只支持 11.5 DLL 哈希）、`jianying-agent-cli`（macOS 引擎，Windows 进程检测有缺陷）和
`jianying-editor`（自动导出走 Windows UI Automation，与剪映版本的绑定关系未核验）都不作为本机主链路。

## Overview

这是一个 Windows 剪映 11.8 的**剪辑优先**技能，不是字幕工具，也不是通用视频编辑器。能力按六域组织：

| 域 | 解决什么 | 先读 |
|---|---|---|
| 剪辑 | 多轨、分割、拼接、变速、倒放、关键帧、画中画、画布、patch | [剪辑 playbook](references/playbooks/01-editing.md) |
| 合成 | 蒙版、抠像、绿幕、层级、贴纸/文字模板叠加 | [合成 playbook](references/playbooks/02-compositing.md) |
| 特效 | 转场、滤镜、画面特效、色轮、曲线变速、调色/HSL | [特效 playbook](references/playbooks/03-effects.md) |
| 音频 | 音量、音量关键帧、淡入淡出、声道、音效、BGM/原声 | [音频 playbook](references/playbooks/04-audio.md) |
| 字幕 | 本地 ASR、SRT 生成/规范化/校验、SRT 入轨、版本化编辑、硬字幕 | [字幕 playbook](references/playbooks/05-subtitles.md) |
| 交付 | probe、inspect、render、verify、抽帧、publish/register | [交付 playbook](references/playbooks/06-delivery.md) |

两条路径：**明文草稿**（可继续编辑，是默认交付物）和 **native bridge 导出**（用剪映自己的引擎出 MP4，
再 ffprobe/抽帧验收）。`references/version.json` 是机器可读版本基线，`probe` 的 `docs.status` 会说明当前
安装是否在 supported 窗口；不在窗口时照常做草稿，但结论必须标为未验证。完整能力矩阵看
[capabilities](references/capabilities.md)，已测/未测边界看 [limits](references/limits.md)；
`scripts/capability_probe.py` 只读探测“技能已接线 / 本机资源已缓存 / 账号或宿主专属”，
不启动剪映、不读凭据。

## Outcome Contract

- **Outcome**：用户拿到可继续编辑的剪映草稿和它的版本链（`v001` 起，至少含本次改动前后的快照）；明确要求成片时再给 MP4；字幕任务才交付 SRT 或烧录后的视频。原始素材只读，输出写到新目录或新文件。
- **Done when**：`probe` 确认环境和 `docs.status`；`build` 后 `inspect` 的轨道/素材/时长与计划一致，`version list` 有 `v001`；`render` 后 ffprobe 的时长、分辨率、编码与草稿一致，导出回执挂到当前版本；关键画面抽帧看过；`patch` 后重新导出并确认改动生效，`version list` 有下一版、`version diff` 能解释改了什么；字幕任务 SRT 通过 `srt.check`。
- **Evidence**：CLI 的 JSON `ok` / `error.code`（字幕入口 `subtitles/cli.py` 为顶层 `code`/`detail`/`hint`）；`inspect` 摘要；ffprobe 的 `duration/width/height/codec`；抽帧 PNG；`version list/show/diff` 的版本号、父版本与结构/材质指纹 changes；`srt.check` 的 `lines` 与 `issues`；首页登记的 `verified` 与备份路径。
- **Authorization**：读用户素材、在项目目录新建草稿可以直接做。以下先征得同意：覆盖原草稿、`patch --in-place`、`version restore --out` 覆盖已有目录（默认已拒绝）、`publish --apply` 与 `build --publish-apply`（会复制进草稿根并改剪映首页列表）、覆盖已存在的成片或抽帧（`--force`）、在剪映运行时写索引、删除用户文件或版本历史。

## When to Use

- 新建多轨剪映草稿：视频/图片/文字/BGM、关键帧、变速、音量、画中画、蒙版、贴纸、画面特效；
- 读取或修改已有**明文**草稿：改文字/样式/音量/速度/位置/裁剪，或复制副本再改；
- 把草稿当 PSD 迭代：查版本、做版本 diff、回到旧版另开新分支，而不是只交一个成片；
- 用剪映原生引擎导出 mp4/mov/gif 或 mp3/wav/aac/flac/aiff/ogg，并用 ffprobe + 抽帧验收；
- 用剪映本地 ASR 识别语音、生成 SRT/逐 token 时间戳，并把字幕写进可继续编辑的草稿；
- 需要时再做 SRT 生成/规范化/校验，或用外部 ffmpeg 烧硬字幕；
- 把本技能生成的草稿复制进剪映草稿根并登记首页。

**不适用**：剪映模板创作、AI 成片、云端/会员素材下载与解锁、手机端剪映、CapCut 国际版；
加密草稿只能回剪映重存为明文，本技能不解密。云端翻译、智能划重点、智能去水词仍受账号/权益限制，
不在免费本地 ASR 的承诺范围内。

## Process

1. **探测环境**：`python scripts/jy.py probe`。看 `install.version`、`docs.status`、`bridge`、
   `draft_root`、`ffmpeg`。`docs.status` 取 `verified` / `unverified` / `unsupported` / `unknown`
   （`unknown` = 版本探测失败或版本文件不可读）；不是 `verified` 时照常做草稿，但交付里必须写明
   “未在支持窗口验证”。`bridge` 找不到或 health 失败不等于剪映没装，只表示当前不能原生导出；仍可生成草稿。
   系统没有 `python` 时，用剪映自带解释器：
   `"<安装目录>\Resources\agent_runtime_env\cli\python\python.exe" scripts\jy.py probe`，
   `probe` 的 `python.bundled` 会给出路径。需要判断“这个能力现在到底能不能做”时，再跑
   `python scripts/capability_probe.py --list`；它把已实现、未验收、计划、资源缺失、宿主专属、账号受限分开。
2. **定域**：先问用户这次要的是六域里的哪一域（剪辑/合成/特效/音频/字幕/交付），再读对应 playbook。
   用户没说成片就只交草稿；没说 BGM 就不加；没要求字幕就不做 SRT。
3. **写计划**：按 [计划 schema](references/plan-schema.md) 写 `jianying-plan/v1` JSON。路径相对计划文件；
   时间单位秒。先 `ffprobe` 素材，不要凭文件名猜时长。
4. **生成草稿**：`python scripts/jy.py build --plan <plan.json> --out <新目录>`。
   先写到同盘暂存目录，全部轨道和素材校验成功后才发布到 `--out`。已有本技能草稿要覆盖才加 `--force`：
   旧目录整体移到 `<out>` 同级的 `.jianying-backups-<name>-<时间戳>/`，不先删除；非空且无
   `.jianying-skill.json` 的目录一律拒绝。`--publish` 只演练复制登记（dry-run，不复制、不写索引）；
   再加 `--publish-apply` 才真正复制并登记到草稿根；`--publish-apply` 不带 `--publish` 会被拒。
   资源 spec 可写 `resource_ref`（完整标题/ID/md5），短标题先 `resource resolve` 取 id；未缓存时加 `--fetch-resources` 自动下载免费资源；
   会员/商业资源仍返回 `RESOURCE_GATED`。
   `build` 同时写 `v001` 版本快照（`<draft>\.jianying-versions\`），`--version-label` 可命名。
5. **核对结构**：`python scripts/jy.py inspect <draft>`。看 `tracks`、`texts`、`missing_media`、
   `duration`；不对就改计划重 build，不要手改 JSON 补洞。再 `python scripts/jy.py version list <draft>`
   确认 `v001` 和计划副本存在。

**字幕任务**：先跑
`python scripts/subtitles/cli.py srt.from-local-asr --audio <音视频> --out <out.srt> --json-out <out.json>`，
它用剪映已下载的本地 Paraformer 模型，不登录、不联网；可选 `--remove-fillers`/`--punctuate`
是本地规则，不冒充剪映 AI 去水词/标点；再用
`python scripts/jy.py patch <draft> --ops <add_subtitles.json> --out <副本>`（或 `--in-place`）
把 SRT 写进可编辑 text 轨。每次 `patch` 自动生成下一版，之后用 `set_text`/`set_style`
改 cue，`version diff` 看结构与材质变化，`render` 后把成片挂到当前版本。模型/依赖缺失时按
`model-missing`/`missing-dep` 处理，不伪造识别结果；云端翻译/划重点/去水词仍是账号能力。
6. **导出**（仅明确要求）：`python scripts/jy.py render <draft> -o <out.mp4>`；音频/动图用 `--format`。
   `render` 会把明文草稿交给剪映，剪映可能回写 `draft_info.json`、`draft_meta_info.json`、
   `draft_content.json`、`attachment_editing.json` 或 `draft.extra`；执行前自动备份草稿文件到
   `<draft>\.jianying-backups\render-*`，并在回执里给出
   `draft_sha256_before/after`、`draft_mutated` 与 `draft_files_changed`（被回写的文件名列表）。
   默认 `mp4`；超时用 `--timeout`。桥接端口每次启动会变，`render` 会重新读描述文件。
   输出已存在时默认拒绝，确需覆盖才加 `--force`。成功后 MP4 路径/字节/ffprobe 时长挂到当前版本的 `exports`。
7. **验收**：`python scripts/jy.py verify <out.mp4> --expect-duration <秒> --frames 0.5,1.5,3.9`。
   读返回的 ffprobe 字段和帧路径；用 Read 看帧，确认字幕位置、画中画、时间窗、蒙版/特效是否真的出现。
8. **登记首页**（仅用户要求放进剪映）：先让用户保存工作并退出剪映，再
   `python scripts/jy.py publish <draft> --apply`；默认 dry-run，不加 `--apply` 不复制、不写索引。
   必须先有稳定 `draft_id` 和可读的 `draft_meta_info.json`，否则返回 `DRAFT_ID_MISSING` /
   `DRAFT_META_*`，不生成伪造 id。
9. **版本迭代/回退**：改稿用 `patch`（自动成下一版），`version diff` 看结构与材质变化，`render` 后验收；
   要回到旧版就 `version restore <draft> <vNNN> --out <新目录>`，生成新 `draft_id` 和新版本链，
   不覆盖原稿。`version snapshot` 用于给导入的旧草稿建立基线或手动留档。
10. **交付**：草稿目录 + 版本链 +（可选）MP4 + 核对结果 + 未验证项。

## 六域路由

| 用户要做的事 | 先读 | 入口 |
|---|---|---|
| 多轨/画中画/关键帧/变速/倒放/裁剪/拼接 | [01-editing](references/playbooks/01-editing.md) | `jy.py build --plan ... --out ...` / `jy.py patch` |
| 蒙版/抠像/绿幕/贴纸/文字模板/层级合成 | [02-compositing](references/playbooks/02-compositing.md) | `build` 的 `mask` / `matting` / `chroma` / `sticker` 字段 |
| 转场/滤镜/画面特效/色轮/曲线变速/调色 | [03-effects](references/playbooks/03-effects.md) | `build` 的 `transition` / `filters` / `effect` 轨 / `color_wheel` |
| 音量/淡入淡出/声道/音效/BGM/原声 | [04-audio](references/playbooks/04-audio.md) | `build` 的 audio 轨与 `audio_fade` / `audio_effect` |
| SRT/硬字幕/口播字幕轨 | [05-subtitles](references/playbooks/05-subtitles.md) | `subtitles/cli.py srt.build` / `srt.check` / `srt.tidy` / `burn`，或 `build` 的 text 轨 |
| 导出/验收/抽帧/首页登记/能力查询 | [06-delivery](references/playbooks/06-delivery.md) | `jy.py render/verify/frame/publish` / `capability_probe.py` |
| 查版本/版本 diff/回到旧版/多版本递进 | [versioning](references/versioning.md) | `jy.py version list/show/diff/snapshot/restore` |
| 环境不对/导不出 | [troubleshooting](references/troubleshooting.md) | `jy.py probe` → 按 `error.code` 查 |

## 入口选择

| 域 | 用户要的 | 命令 |
|---|---|---|
| 剪辑 | 新建草稿 | `jy.py build --plan ... --out ...`（`--publish` 只演练） |
| 剪辑 | 看草稿结构 | `jy.py inspect <draft>` |
| 剪辑 | 改已有明文草稿 | `jy.py patch <draft> --ops ops.json --out <副本>` |
| 交付 | 看版本/版本 diff | `jy.py version list <draft>` / `jy.py version diff <draft> v002` |
| 交付 | 给当前草稿留一版 | `jy.py version snapshot <draft> --label ...` |
| 交付 | 回到旧版另开分支 | `jy.py version restore <draft> v001 --out <新目录>` |
| 合成 | 蒙版/抠像/贴纸/文字模板 | 写进 plan，再 `jy.py build`；字段见 [plan-schema](references/plan-schema.md) |
| 画面/文字 | 视频或文字的入场/出场动画 | 写 `animations`（支持 `resource_ref`），再 `build`；资源需缓存 |
| 特效 | 转场/滤镜/画面特效/色轮 | 写进 plan，再 `jy.py build`；资源未缓存会降级 |
| 音频 | 音量/淡入淡出/声道/音效 | 写进 audio 轨，再 `jy.py build` |
| 字幕 | 生成/校验 SRT | `subtitles/cli.py srt.build` / `srt.check` / `srt.tidy` |
| 字幕 | 按音频/逐句定时 | `subtitles/cli.py srt.from-audio` / `srt.from-segments` |
| 字幕 | 本地识别并写入可编辑字幕轨 | `subtitles/cli.py srt.from-local-asr` + `jy.py patch` 的 `add_subtitles` |
| 字幕 | 一键生成可编辑字幕工程 | `jy.py auto-subtitles --video ... --out ...`；已有 SRT 加 `--srt`，跳过 ASR |
| 交付 | 转码到目标视频码率 | `jy.py transcode in.mp4 -o out.mp4 --video-bitrate 2M`（本机 ffmpeg，非剪映原生） |
| 交付 | 使用资源前预检 | `jy.py resource verify <ref> --expect-panel flower2` |
| 字幕 | 套用免费字幕模板 | `jy.py resource download <模板> --apply` + 计划 `caption_template`/`caption_info` |
| 字幕 | 烧硬字幕 | `subtitles/cli.py burn --video ... --srt ... --out ...` |
| 交付 | 看环境/为什么导不出 | `jy.py probe` |
| 交付 | 查本机有哪些字体/贴纸/特效/模板、是否已缓存 | `jy.py resource stats` / `resource list` / `resource resolve` |
| 交付 | 下载免费字体/素材到本机 | `jy.py resource download <id\|标题> --apply`（默认 dry-run） |
| 交付 | 生成本地包装 preset | `jy.py packaging --video ... --subtitle-srt ... --bgm ...`（本地组合，不是云端智能包装） |
| 交付 | 看能力矩阵/资源预检 | `scripts/capability_probe.py --list`（只读，不启动剪映） |
| 交付 | 导出成片/音频 | `jy.py render <draft> -o out.mp4`；`--format mov/gif/mp3/wav/aac/flac/aiff/ogg` |
| 交付 | 验收成片/抽帧 | `jy.py verify out.mp4 --frames ...` |
| 交付 | 单独抽一帧 | `jy.py frame <video> --at <秒> -o <png>` |
| 交付 | 放进剪映首页 | `jy.py publish <draft> --apply`（先退出剪映） |
| 交付 | 只登记已在草稿根的草稿 | `jy.py register <draft> --apply` |
| 交付 | 列出现有草稿/探测媒体 | `subtitles/cli.py draft.list` / `probe` |

`patch` 的 ops 支持 `set_text`、`set_style`、`set_volume`、`set_speed`、`shift`、`trim`、
`set_transform`、`remove`、`rename`、`set_canvas`、`fps`。默认写副本，`--in-place` 才改原稿
（同时备份 `draft_info.json` 与 `draft_meta_info.json` 到 `.jianying-backups\`）。

## 计划速查

```json
{
  "schema": "jianying-plan/v1",
  "name": "草稿名",
  "canvas": {"width": 1920, "height": 1080, "fps": 30},
  "tracks": [
    {"type": "video", "segments": [{"path": "media/main.mp4", "start": 0, "duration": 4,
      "mask": {"resource_type": "circle", "name": "圆形", "resource_id": "82432977",
               "path": "<本机剪映缓存>/effect/82432977/<package>",
               "config": {"center_x": 0.5, "center_y": 0.5, "width": 0.5, "height": 0.5,
                          "feather": 0.1}}]},
    {"type": "video", "segments": [{"path": "media/pip.mp4", "start": 0.5, "duration": 2,
      "scale": 0.35, "x": 0.6, "y": 0.5, "speed": 0.5,
      "keyframes": {"scale": [[0, 1.0], [1.5, 1.08]]}}]},
    {"type": "text", "segments": [{"text": "标题", "start": 0.4, "duration": 3,
      "font_size": 12, "color": "#FFD400", "stroke_width": 0.06,
      "background": {"color": "#000000", "alpha": 0.5},
      "shadow": {"color": "#000000", "alpha": 0.6, "distance": 4}}]},
    {"type": "audio", "segments": [{"path": "media/bgm.m4a", "start": 0, "duration": 4,
      "volume": 0.35, "audio_fade": {"in": 0.4, "out": 0.6}}]}
  ]
}
```

蒙版示例用的是 2026-11-15 真机验证过的 circle 包；`resource_id`/`path` 必须换成本机已缓存包，不能照抄占位。

- `tracks` 顺序即层级；第一条 video/image 是主轨，后续自动 `flag: 2`。
- **y 正值向上，负值向下**：底部字幕用 `y: -0.7`，标题居中偏上用 `y: 0` ~ `0.2`。
- 视频 `duration` 超过素材可用长度直接报错；变速时源区间按 `duration*speed` 自动算。
- 关键帧写在 `segments[].keyframes`，如 `"scale": [[0,1.0],[1.2,1.06],[4,1.0]]`。
- 完整字段、贴纸/特效轨、native 逃生舱、patch ops 见 [计划 schema](references/plan-schema.md)。

## Hard Rules

- **先有草稿，再谈成片**：默认交付可编辑草稿；只有用户明确要 MP4 才 `render`。
- **素材只读**：不覆盖、不移动、不删除用户素材；封面/抽帧/成片都写新文件。成片与抽帧已存在时默认拒绝，`--force` 必须由用户明确授权。
- **用户草稿只读**：只在本次任务的新目录里 `build`；修改用户已有草稿默认 `patch --out` 写副本，`--in-place` 需要同意并保留 `.jianying-backups/`。
- **版本链是交付物的一部分**：`build`/`patch` 自动写版本；导入草稿先 `version snapshot` 建基线。不手改 `versions.json`、快照 JSON 或 `draft_info.json` 造版本；旧版本不自动删除。
- **恢复只写新目录**：`version restore` 生成新 `draft_id` 和新版本链，不覆盖原稿；目标目录已存在时直接拒绝，不“先删再恢复”。
- **版本 diff 不是像素验收**：`version diff` 比结构、片段字段和主/附加材质指纹（含动画、字幕模板、高亮、资源路径）；画面/转场/滤镜/听感仍要分别 `render` 两版后抽帧或 `volumedetect`，不能把 `changes` 为空当成效果没变。
- **明文草稿限定**：`DRAFT_ENCRYPTED` 时停止，不要解密、不要 `--in-place`、不要猜结构。
- **本地普通路径限定**：素材、计划、草稿和输出拒绝 UNC、网络盘、URL 及草稿内的符号链接/junction；第三方路径不能触发 SMB 或越界读取。
- **首页登记要有完整 meta**：`draft_info.json` 与 `draft_meta_info.json` 的 `draft_id` 必须一致，`tm_duration` 必须为正，缺 meta 不写索引；更新已有条目只改本技能拥有的字段，不覆盖剪映云字段。
- **文字素材必须是 `type: "text"`**：写成 `subtitle` 会触发 409 `film_export_entitlement_denied`。
- **画中画要 `flag: 2` + `render_index ≥ 1`**：两者缺一，图片/视频不会出现在成片里。
- **不碰会员校验**：不改账号、不伪造 token、不改 DLL 哈希、不打补丁绕过 entitlement。缺素材就让用户在剪映里正常获取或去掉。
- **资源目录只读**：`jy.py resource list/stats/resolve` 只读 `rp.db` 与 `Cache`，不下载、不解锁会员；`cached=true` 只代表本机有包，不代表账号权益或导出一定生效。模板/贴纸/转场/滤镜/花字必须再做真实导出验收。
- **资源下载会写缓存**：`resource download` 默认 dry-run，`--apply` 才下载到剪映缓存；只下 `extra.is_vip/is_business=false` 且 URL 未过期的包；会员/商业/过期 URL 直接失败。写缓存前尽量退出剪映，避免应用同时清理/改写 Cache。字体与字幕模板已真实验收；文字模板（`text_template`）槽位尚未验收，不能当已支持。
- **不泄漏桥接秘密**：`%TEMP%\infinite-canvas-native-bridge.json` 的 token、`/custom-agent/context`
  的 cookie 不写进草稿、日志、Git、回复或交付物。`probe` 只输出白名单字段。
- **不在剪映运行时写首页索引**：`publish --apply` 前让用户保存并退出剪映；写前备份，写后回读。
  没有用户明确要求，不做 `--apply`。
- **`adjust` / `freeze` 不静默忽略**：plan 里出现这两个字段直接报 `VALIDATION`；调色只能交付剪映客户端
  结果，`color_wheel` 在 11.8 真机未见像素变化，不要当可用；定格用抽帧工作流。不要把未接线字段当已支持。
- **不承诺未验证能力**：转场、滤镜、特效、贴纸、花字/气泡、文字模板槽位、曲线变速、HSL、色轮、倒放、色彩匹配、绿幕、
  多时间线导出都先按 [能力边界](references/limits.md) 说明；视频自定义码率不在 native draftPath 导出入口支持范围，
  分辨率/帧率改画布，码率走客户端或 ffmpeg 转码；文字/视频动画、本机关键词高亮、左右声道和“萝莉”变声已真机验收；蒙版已有真机像素证据，
  但资源包必须已缓存且 `config` 不能为空；状态先查
  [能力矩阵](references/capabilities.md) 与 `capability_probe.py`，不把“结构写进去了”当成“效果生效”。
- **`native` 逃生舱自负后果**：技能不校验字段语义，写错不报错；必须 `inspect` + 真实导出验收，且不得改
  `id` / `material_id` / `local_material_id` / `extra_material_refs` / `render_index` / `track_render_index`。
- **不调用官方 CLI（含外部 `jy` 的 render）**：外部 shell 没有宿主令牌；Windows 上 jy 还有进程检测缺陷。
- **字幕不静默丢数据**：SRT 解析出 0 条、时间码越界、行宽或时长不合规时如实失败；不用截断冒充成功。
- **不静默截断**：素材不够、字段非法、输出目录非空都报错退出；不要“先导出来再说”。

## Gotchas

| 现象 | 做法 |
|---|---|
| `probe` 找到 bridge 描述文件但 health 连接被拒 | 描述文件可能是上次运行残留；确认剪映正在运行，`probe` 会重新读端口。仍失败就只能交草稿。 |
| 克隆一份草稿后突然 409 `entitlement_denied` | 文字素材 `type` 被写成 `subtitle`；改成 `text` 再导 |
| 字幕跑到屏幕顶部 | `y` 正值向上；底部用负值，如 `-0.72` |
| 图片叠加不显示 | 副视频轨 `flag` 必须是 `2`，segment `render_index` 必须 ≥ 1 |
| 文字内容改了但画面没变 | `content` 是字符串化 JSON，`range` 要按新文本重算；用 `patch set_text` |
| 文字背景/阴影不显示 | 背景需 `background.color` + `alpha`；阴影需 `shadow.color` + `distance`；`check_flag` 会加 16/32 |
| 文字是方块 | `content` 不是合法 JSON，或 `font_path` 指向不存在的字体；留空用默认字体 |
| 首页看不到刚登记的草稿 | 剪映运行时会覆盖索引；退出剪映后 `publish --apply`，再重开 |
| `render` 说草稿读不了 | 剪映重存后加密或迁到 `Timelines/`；只对根 `draft_info.json` 的明文草稿导出 |
| `build --force` 拒绝 | 目录里没有 `.jianying-skill.json`，不是本技能生成的；换目录，别强删 |
| `OUTPUT_EXISTS` | 成片/抽帧已有同名文件；换新路径，或经用户同意加 `--force`。`version restore --out` 已有目录时换新目录，不覆盖 |
| `VERSION_NOT_FOUND` / `VERSION_CORRUPTED` | 草稿没有版本历史或历史损坏；导入草稿先 `version snapshot`，损坏时不要手改，保留现场并从源草稿重建 |
| 版本 diff 没变化但画面变了 | `version diff` 比结构与材质指纹，不做像素 diff；导出两版抽帧或 `volumedetect` 比较像素/听感 |
| 导出成功但时长不对 | 用 `verify --expect-duration`；差 >0.25s 检查片段越界、变速源区间、图片 duration |
| 烧字幕失败 `Unknown filter 'subtitles'` | 剪映自带 ffmpeg 没有 libass；装外部 full 构建并设 `JY_FFMPEG` |
| SRT 导入剪映后片段重叠 | 标题与字幕在同一轨；标题单独占一轨 |
| 转场/滤镜/贴纸/花字写了却没效果 | 先 `jy.py resource list --panel <panel> --cached` 看资源是否真的在本机；`cached=false` 就在剪映里正常下载一次；会员资源仍会被 entitlement 拦 |
| 本地 ASR 报 `model-missing` / `missing-dep` | 先在剪映用一次「识别字幕」下载模型；再 `pip install numpy onnxruntime kaldi-native-fbank`；不要伪造识别结果 |
| 本地 ASR 生成的字幕没有标点 | 模型只输出文字和 token 时间；不冒充翻译/划重点/去水词，需要标点就另行后处理 |
| 中英混排字幕拆出残词（ex/cel、p/hotoshop） | `srt.tidy` 已词安全拆分：硬切点落在英文词内部时回退到词起点；仍残词说明该英文词比 `--max-chars` 长，调大阈值或接受硬切 |
| 单字字幕挂 6–9 秒不消失 | ASR 块边界把静音吞进单字时间戳；`srt.tidy` 按 `--max-dur` 截到 1s 显示（只压不抬、优先于 `--min-dur` 保底），文字不动，回执看 `short_artifacts_capped` |
| `resource download` 报 `RESOURCE_GATED` | 会员/商业资源 | 在剪映客户端正常获取；技能不绕过权益 |
| `resource download` 报 `RESOURCE_URL_EXPIRED` | 资源签名 URL 已过期 | 在剪映里打开一次素材面板刷新资源，或换一个资源 |
| build 报 `RESOURCE_NOT_CACHED` | `resource_ref` 指向的资源还没下载 | 先 `resource download <ref> --apply`，或给 build 加 `--fetch-resources` |
| 下载字体后文字不显示/仍是默认字体 | `font_path` 指错，或字体包没解压出 TTF/OTF | 用 `resource download` 返回的 `font_path`；先 `resource resolve` 确认包路径 |
| 字幕模板显示 `[字幕输入中…]` 或没带上 cue 文本 | 用了 `text_template` 而不是 `caption_template`，或 `caption_template` 没有 `resource_id`/`path` | 用 `caption_template` 写文字材质的 `caption_template_info` + `recognize_text`；`caption_info` 写 `segment.caption_info`；模板依赖的字体/花字资源要缓存 |
| PowerShell 里 JSON 引号被吃 | 把计划写成 UTF-8 文件再 `--plan`，不要内联长 JSON |

更多报错按 `error.code` 查 [排错速查](references/troubleshooting.md)；桥接错误码见
[桥接与官方 CLI](references/bridge-protocol.md)。

## Verification

交付前至少：

1. `probe` 成功，且 `install.version` 与用户实际版本一致；
2. `inspect` 的 `missing_media` 为空、`duration` 与计划一致、文字在 `texts` 里、图片在第二条 visual 轨；
3. 要成片时 `render` 返回 `ok: true`，`verify` 的 `duration` 与草稿差 ≤ 0.25s，`width/height/fps/codec` 正确；
4. 抽至少 3 帧（开头、叠加出现中段、结尾）并亲自看；字幕位置、画中画、蒙版、特效、文字背景/阴影不对就重做；
5. `patch` 任务要重新导出并抽改动前后的帧/听音频，不能只看 `ok: true`；`version list` 应看到父版本与下一版，
   `version diff` 能解释改了什么，`version show` 的 `exports` 能挂上新成片；
6. `version restore` 任务要确认新目录、新 `draft_id`、旧版内容，且原稿未被改动；
7. 音频淡入淡出/声道/音效任务，导出后用 `volumedetect` 或听音频确认首尾/左右差异，不只看结构；
8. `render` 检查 `draft_mutated` 与 `draft_files_changed`；为 true 时对照 `draft_backups` 复核被回写的文件，再交付；
9. `publish --apply` 要看到 `applied: true`、`verified: true` 和备份路径；没重启剪映就说明“未验证首页显示”；
10. 字幕任务跑 `srt.check`，要求 `ok: true`、`lines > 0`、`issues` 为空；烧录任务再检查
   `drift_ok=true` 并抽帧确认字幕不是方块。同屏双人/双语上下行等**重叠 cue 可以烧**：
   `burn` 只拒负/零/非有限时间码，不拒重叠；`srt.check` 默认仍会报重叠，烧录前以 `burn` 结果为准。

维护技能本身时运行：

```bash
python scripts/test_skill.py
python scripts/check_skill.py
python scripts/check_skill.py --self-test
python scripts/check_docs.py
python scripts/check_docs.py --self-test
python scripts/probe_gotchas.py --allow-skip
python scripts/capability_probe.py --list
python scripts/run_examples.py
```

`test_skill.py` 覆盖 `build`、`inspect`、`patch`、版本链（build/patch/restore）、`publish` dry-run、计划校验、
覆盖保护、失败事务清理与原子化 JSON 写入；不启动剪映，不写用户草稿。`check_skill.py` 校验 frontmatter、相对链接、示例 JSON 与敏感字段。
`check_docs.py` 校验文档里的错误码/动词/版本基线与代码一致；`probe_gotchas.py` 把关键约束变成可跑探针；
`capability_probe.py` 只读输出能力矩阵（不启动剪映、不读凭据）；`run_examples.py` 跑 `examples/NN-*.py`
离线案例（05 只跑能力报告，06–19 只做离线结构/工作流验收，不连 bridge；19 覆盖版本链）。真实 `render`
需要剪映运行，属于交付任务的集成验证，不在离线测试里伪造。

## Output

交付时依次给：

- 草稿目录绝对路径、草稿名、时长、画布、轨道/素材计数；旧草稿被覆盖时给 `previous` 路径；
- 版本链：当前 `version`、`version_count`、`history_path`；改稿时给 `version diff` 的结构/材质指纹 changes；
  恢复时给 `restored_from`、新 `draft_id` 和新目录；
- 成片路径、字节数、ffprobe 的时长/分辨率/帧率/编码（如已导出）；`render` 另给 `draft_mutated` / `draft_files_changed`、导出前备份路径，
  并说明该 MP4 挂在哪个版本；
- 抽帧 PNG 路径与“看过了”的结论；
- 音频任务给淡入淡出/声道/音效的听感或 `volumedetect` 证据；
- SRT 路径、行数、`srt.check` 结果（如做字幕）；
- `publish` 的 `action / applied / backup / verified`（如已登记）；
- 未能验证的部分（`adjust`/`freeze`/HSL/绿幕/花字/气泡/加密草稿等）和原因；不要把未验证说成已支持。

## 参考

| 文件 | 何时读 |
|---|---|
| [references/playbooks/01-editing.md](references/playbooks/01-editing.md) | 多轨、画中画、关键帧、变速、倒放、patch |
| [references/playbooks/02-compositing.md](references/playbooks/02-compositing.md) | 蒙版、抠像、绿幕、贴纸、文字模板、层级 |
| [references/playbooks/03-effects.md](references/playbooks/03-effects.md) | 转场、滤镜、画面特效、色轮、曲线变速 |
| [references/playbooks/04-audio.md](references/playbooks/04-audio.md) | 音量、淡入淡出、声道、音效、BGM/原声 |
| [references/playbooks/05-subtitles.md](references/playbooks/05-subtitles.md) | SRT、硬字幕、口播字幕轨 |
| [references/playbooks/06-delivery.md](references/playbooks/06-delivery.md) | probe、render、verify、抽帧、publish |
| [references/versioning.md](references/versioning.md) | 版本链目录、list/show/diff/snapshot/restore、恢复语义 |
| [references/plan-schema.md](references/plan-schema.md) | 写计划、字段含义、关键帧、patch ops |
| [references/draft-format.md](references/draft-format.md) | 草稿 JSON 结构、素材字段、首页 38 键索引 |
| [references/bridge-protocol.md](references/bridge-protocol.md) | 桥接路由/请求体/错误码、官方 CLI 边界 |
| [references/troubleshooting.md](references/troubleshooting.md) | 按 `error.code` 或画面现象排错 |
| [references/limits.md](references/limits.md) | 已测/未测能力、版本差异、对用户表述边界 |
| [references/capabilities.md](references/capabilities.md) | 六域能力矩阵、资源预检口径、官方 XMLDraft 索引 |
| [references/version.json](references/version.json) | 机器可读版本基线，`check_docs.py` 据此校验 |
| [references/upstream.md](references/upstream.md) | skills.sh 候选、参考仓库取舍、独立 CLI 的可选边界 |
| [references/maintenance.md](references/maintenance.md) | 本地维护、升级流程、版本窗口与不承诺项 |
| [references/upgrading.md](references/upgrading.md) | 版本升级与迁移 |
| [references/changelog.md](references/changelog.md) | 技能变更记录 |
| [examples/plan_basic.json](examples/plan_basic.json) | 横屏视频+图片角标画中画+字幕+BGM 模板 |
| [examples/plan_vertical.json](examples/plan_vertical.json) | 竖屏封面视频+标题/字幕双文字轨+BGM 模板 |
| [examples/ops_example.json](examples/ops_example.json) | patch 补丁示例 |
| [examples/README.md](examples/README.md) | 案例清单、覆盖范围与运行方式 |

## Scripts

| 文件 | 职责 |
|---|---|
| `scripts/jy.py` | 草稿 build/inspect/patch/render/verify/publish/version 统一入口 |
| `scripts/jylib/` | 草稿构建、路径探测、媒体探测、首页索引、native bridge 客户端、版本链、本机资源目录 |
| `scripts/subtitles/cli.py` | 字幕辅助入口：草稿清单、媒体探测、SRT 生成/规范化/校验、硬字幕烧录 |
| `scripts/requirements.txt` | Python 标准库与外部 ffmpeg 依赖说明 |
| `scripts/test_skill.py` | 离线自测，不启动剪映 |
| `scripts/check_skill.py` | 技能文档与静态资源自检 |
| `scripts/check_docs.py` | 文档↔代码一致性自检（错误码/动词/版本基线/脚本引用） |
| `scripts/probe_gotchas.py` | 可执行踩坑探针（UTF-8/UNC/白名单/校验/暂存清理/索引 id/`init-present`/ffmpeg 能力诚实性） |
| `scripts/capability_probe.py` | 只读能力探测：已实现/未验收/计划/资源/宿主/账号六类状态 |
| `scripts/upgrade_check.py` | 只读升级体检：安装版本/能力矩阵对比基线，生成迁移清单；不访问外网、不自替换，`--save` 才写文件 |
| `scripts/run_examples.py` | 编号案例 runner（examples/NN-*.py，PASS/FAIL/SKIP） |
| `references/version.json` | 机器可读版本基线（app/build/supported），与 limits.md 对齐 |
