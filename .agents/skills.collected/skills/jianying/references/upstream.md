# 来源、候选与取舍

核对日期：2026-11-14。skills.sh 与其索引页会变动，安装第三方技能前重新核对仓库状态、版本和安全审计。

## skills.sh 候选

| 技能 | 来源 | 能力 | 结论 |
|---|---|---|---|
| `jianying-editor` | `luoluoluo22/jianying-editor-skill`，[skills.sh 页面](https://www.skills.sh/luoluoluo22/jianying-editor-skill/jianying-editor) | Python 封装、草稿生成、素材导入、字幕、录屏、自动导出 | 不采用为主链路。自动导出走 Windows UI Automation（页面口径），与剪映版本的绑定关系未核验；页面功能超出本机 11.8 已验证范围；2026-11-14 读取时 GitHub 主页/API 返回 404，2026-11-16 复核页面已可解析，源码仍未逐行核验。 |
| `capcut-edit` | `renezander030/capcut-cli`，[skills.sh 页面](https://www.skills.sh/renezander030/capcut-cli/capcut-edit) | 直接读写 CapCut/JianYing 本地草稿：字幕、时间、速度、音量、模板、切片 | 可选外部工具，不作为本技能运行时依赖。MIT，GitHub 仓库 2026-11-14 可读，默认分支 `master`，README 标注 v0.33.0。吸收其“关闭工程再写、`.bak` 加滚动历史快照、写后视觉验收、输出不静默覆盖”的约束。 |
| `jianying-video-compose` | 社区技能（ClawHub，作者发布），[ClawHub 页面](https://clawhub.ai/2719040953/jianying-video-compose) | 通过剪映代理 API 创建草稿、上传素材、云渲染 | 不采用。依赖第三方 HTTP 服务 `np-newsmgr-uat.eastmoney.com` 与 OSS 上传，素材离开本机，且服务可用性、授权和数据处理边界无法由本技能保证。 |

`capcut-edit` 只有在用户明确同意安装后才使用：

```bash
npx skills add renezander030/capcut-cli --skill capcut-edit
```

安装前必须核对版本：其 README 记录 **≤ 0.17.0** 存在本地命令/滤镜注入与凭据输出类问题，
**0.18.0 / 0.17.1** 已修复。低于修复版本不要使用，也不要把旧版本接进本技能链路。

本技能的 `scripts/` 不调用它。两者同时改一份草稿会产生冲突；同一工程同一时间只用一个写入口。

## 本地参考仓库

| 目录 | 实际定位 | 采用方式 |
|---|---|---|
| `__repros/jianying-1` | Windows 11.8 的明文草稿 + native bridge 导出链路，含 build/inspect/patch/publish 与 ffprobe 验收 | **主实现来源**，复制后补充安全覆盖保护、字幕工具、自测与来源说明 |
| `__repros/jianying-2` | 只读草稿盘点、媒体探测、SRT 生成/规范化/校验、硬字幕烧录 | **字幕与清单辅助来源**，收进 `scripts/subtitles/`；不做语音识别，不替代剪映原生时间线 |
| `jianying-headless-windows` | Apple Silicon macOS 的 11.5 无界面管线，核心项目与 Skill 分离安装；导出依赖固定版本/哈希白名单 | 不调用。Windows 11.8 会在安装发现阶段被版本白名单拒绝，不能改白名单绕过 |
| `jianying-agent-cli` | 官方风格 `jy` CLI，macOS 上走剪映引擎；Windows 适配不完整 | 不调用其 render/preflight。参考其草稿字段形状；Windows 的 `jianying_commands` 依赖 `/bin/ps`，进程存活判断也与非 Windows 语义不同 |

## GitHub 项目复核（2026-11-18）

| 项目 | 定位 | 可借鉴 | 不照搬 |
|---|---|---|---|
| [pyJianYingDraft](https://github.com/GuanYixuan/pyJianYingDraft) `0.3.1` | Python 草稿生成；视频/音频/关键帧/蒙版/色度抠图/特效/模板模式 | 模板模式：加载已有草稿后替换素材、提取贴纸/气泡/花字的 `resource_id` 与元信息——这是本技能没有真实花字资源时最现实的路径 | 文档明确「暂不支持曲线变速」；自动导出只支持剪映 6.8 及以下（新版控件被隐藏）；新版 `draft_content.json` 常为密文，需要 `fallback_loader` |
| [capcut-cli](https://github.com/renezander030/capcut-cli) | 零依赖 CLI，直接读写 `draft_content.json` / `draft_info.json` | 版本感知 schema、`lint` / `diff` / `render` 代理、原子写 + `.bak`；文档确认 6.0+ 的 `draft_content.json` 是 AES 密文，`draft_info.json` 仍是明文 info-primary | 它的 `render` 是 ffmpeg 低清代理，不是剪映引擎；不能当最终画质验收 |
| [jianying-tool](https://pypi.org/project/jianying-tool/) `0.4.1` | 11.x 原生草稿编辑：发现本机 `videoeditor.dll` 解码/重封装 `draft_content.json`，71 个 MCP 工具 | 基础调节写 `segment.common_keyframes` 的 `KFTypeBrightness/Contrast/Saturation`（起点和终点同值）；定格用「抽帧图片 + 独立轨」；导出驱动剪映自己的导出对话框 | 基线是 11.4.2；结构写入不等于 11.8 渲染生效；`draft_content` 编解码依赖本机 DLL，不能移植到无剪映环境 |
| [JianYingAPI MCP](https://lobehub.com/mcp/zhangyukwiver-jianyingapi) | MCP 服务：文字样式、气泡、花字、关键帧、动画、草稿箱 | 文字气泡/花字按「类型 + 素材 ID」维护，共享素材复制后再改，避免影响其他片段 | 不含视频导出；动画资源不独立下载，缺失资源交给剪映打开时处理 |
| [capcut-mate](https://github.com/Hommy-master/capcut-mate) | HTTP API 封装剪映草稿创建/保存/下载 | 文字气泡/发光/花字的真实草稿结构：气泡 `text_shape` 的 `effect_id`/`resource_id` 分开；发光是 `materials.effects[type=bloom]` + `bloom_params` + `value=0.0` + 文字 `check_flag |= 64`；花字重置颜色/描边/阴影；`path` 可由剪映按 ID 拉取 | 依赖本地服务与 Electron 下载链路，本技能不引入常驻服务；它的资源清单不等于本机 11.8 的账号权益 |

`capcut-mate` 的气泡与发光字段在 2026-11-18 被用来修正本技能：

- 气泡：`materials.effects[type="text_shape"]`，真实样本 `effect_id="716434"`、
  `resource_id="6821385652727190024"`（“背景装饰54”），两者必须同时给；它只加装饰底板。
- 发光：`materials.effects[type="bloom"]`，`panel_id="text_glow"`，`value=0.0`，
  `effect_id`/`resource_id` 分开，`bloom_params` 写 `color/dir_x/dir_y/range/strength`，
  文字材质 `check_flag` 置 64；可和花字/气泡/模板叠加。本技能此前把发光写成
  `type="text_glow"` 且复用 `resource_id` 当 `effect_id`，已按此修正；但本机外发光/轮廓光
  都是商务资源，真实导出 409，仍无像素证据。
- 花字：`materials.effects[type="text_effect"]` + `styles[0].effectStyle`，资源必须是真实
  `flower`。2026-11-18 用 `7127669365423508767` 真机导出，与无花字帧差
  `YAVG=4.1713`/`YMAX=209`；718/735 均 409。

### 本轮按上游字段复测（11.8 + native bridge）

- 用 pyJianYingDraft 的最小 `chromas` 结构（8 个字段、`version: v2`）替换本技能的 chroma 材质，
  native bridge 重新导出后绿幕角仍是 `(0, 254, 0)` → bridge 渲染侧不执行；同一结构在 11.8 界面打开
  即蓝底红块，界面导出角点 `(0,0,254)`，说明结构本身正确，限制在 bridge（1.5.3 修正结论）。
- 按 jianying-tool 的思路给纯红片段写 `common_keyframes` 的 `KFTypeBrightness`（起点/终点 `-1.0`，
  `enable_adjust: true`），导出后中心仍是 `(252, 0, 0)`，只有重编码造成的 G+22 → 同样未生效。

- 核对文字特效材质桶：`pyJianYingDraft` 的 `TextBubble/TextEffect` 与
  `jianying-tool` 的 `text.py` 都把 `text_shape` / `text_effect` 写到
  `materials.effects`；`pyJianYingDraft` 的 `draft_content_template.json` 没有
  `filters` 键。本技能此前写 `materials.filters`，已于 1.2.9 修正。

- `capcut-mate` 的 `add_captions` 还给出两条可验证行为：文字优先级
  `text_template > text_bubble > text_effect`；花字接管外观时把文字
  颜色/描边/阴影重置为默认。1.3.2 已落进构建器；712 真机用“红字+绿描边+蓝阴影”
  计划导出，帧与默认 712 帧差 `0/0`，确认重置行为（`flower712_reset_150.png`）。

### 官方 11.8 编辑协议复核（2026-11-18）

官方安装目录里的 `editing-protocol/selection-skill/references/segment-text-sticker.md`
给出比上游更硬的边界：

- `text_effect` 是普通 text/subtitle 的花字资源，ref 必填且必须绑定 `flower`；
  不能用 `text_template` 或普通视频特效替代，暂不支持 template 宿主。
- `text_glow_ref / text_glow_color / text_glow_range / text_glow_strength` 写在
  text/subtitle/lyrics 宿主属性上；新增发光必须先取得真实 `text_glow` blueprint_ref。
- 协议里没有 `text_shape` 节点；`jianying.hub.studio_edit_reference_recall_v2` 的
  `presets/text.md` 把 `text_bubble` 放在“文字模板”表（默认 RID
  `7659366084470000920`）。因此本技能的 `text_bubble → text_shape` 只能算旧草稿
  兼容路径，11.8 的气泡应走 `text_template`。

结论：**上游项目的“已支持”多是结构写入或旧版本行为**，不能直接当 11.8 的验收结论。
可复算记录见仓库外证据归档。

## capcut-cli / jianying-editor-skill 覆盖对照（2026-11-18）

删除参考仓库前逐项对照，避免“命令名没抄过来”被误当成能力缺口：

| 上游能力 | 本技能落点 | 结论 |
|---|---|---|
| `save-template` / `apply-template` | `jy.py template save/apply` | 已覆盖；保存片段、主素材和全部 `extra_material_refs`，应用时全量重映射 id，文字可 `--text` 覆盖 |
| `make-preset` / `templates` | `template save/apply` + `resource list` / `resource resolve` | 已覆盖语义；样式 preset 就是文字片段模板，不另造一套 preset 命令 |
| `import-ass` / `export-ass` | `jy.py ass import/export` | 已覆盖；支持常用内联标签，未支持标签列 `unsupported_tags` |
| `export-timeline` / `import-timeline` | `jy.py otio export/import` | 已覆盖；文字/贴纸/特效轨在 `skipped` 列明，不静默丢弃 |
| `detect-scenes` / `detect-silence` / `detect-retakes` | `jy.py detect scenes/silence/retakes` | 已覆盖；真实素材切点与静音边界已复验 |
| `relink` / `replace-media` / `prune` | `jy.py relink/replace-media/prune` | 已覆盖；默认写副本，`--in-place` 才回写并备份 |
| `bg-blur` | `background_fill`（`blur`/`color`） | 已覆盖并真机抽帧；只对第 0 条视觉轨生效 |
| `mix-mode` | `mix_mode` | 结构已覆盖；11.8 bridge 导出不应用，保持 `conditional`，需界面导出 |
| `text-anim` / `image-anim` | 已有 `animations` / `material_animations` | 已覆盖；文字“变色输入”、视频“翻入”有真机抽帧证据 |
| `loudness` | `jy.py loudness` | 已覆盖；EBU R128 测量 + 增益写入，导出实测差 0.06–0.11 dB |
| `render`（ffmpeg 低清代理） | `jy.py render`（剪映 native bridge）+ `transcode` | 不采用其代理渲染；本技能用剪映引擎出片，转码只做后处理 |
| `template_mode.py` | `template save/apply` + `replace-media` | 片段模板已覆盖；整稿里的单片段素材替换走 `replace-media`，未移植其 shrink/extend 整轨伸缩策略 |
| `draft_inspector.py` | `jy.py inspect` | 已覆盖；额外输出 `video_extras` / `text_effects` |
| `movie_commentary_builder.py` | `jy.py packaging` + `auto-subtitles` | 已覆盖本地包装工作流；不是云端智能成片 |
| `smart_zoomer.py` | 未单独移植 | 录屏后按鼠标事件加关键帧的演示工作流，依赖外部事件 JSON；不属于草稿格式缺口。需要时可用 `animations` / 关键帧手工组合 |
| `web_recorder.py` | 未移植 | 屏幕录制是 GUI/采集能力，不是剪映草稿能力；本技能不接管录屏 |

结论：`capcut-cli` 的命令级能力已在本技能有对应入口；`jianying-editor-skill` 的模板模式已覆盖片段级，
录屏/智能变焦属于工作流示例而非缺失的草稿能力，`pyJianYingDraft` 的 shrink/extend 整轨伸缩属于可选策略。
没有发现必须再移植的核心命令。

## 其余仓库审计（2026-11-18）

| 仓库 | 实际能力 | 处理结论 |
|---|---|---|
| `JianYingApi` | 用 `uiautomation` 驱动剪映 UI，包含素材导入、轨道、文字等 | 不采用。作者自述版本变化快、BUG 多；本技能已有 native bridge 和直接草稿写入。技能不内置 GUI 自动化，也不把界面点击作为交付流程；必须点界面的步骤由用户在剪映完成 |
| `JianyingDraft.PY` | 基础草稿 JSON 生成：`draft_content.json` / `draft_meta_info.json`、素材入轨 | 已覆盖。`build` 的轨道/素材/时间线能力更完整，且带校验、版本链和导出 |
| `jianying-mcp` | MCP 服务器封装草稿创建、轨道、视频/音频/文本、特效/滤镜/动画 | 架构不采用；能力已由本技能 CLI 覆盖。MCP 只是调用形态，不是新的草稿能力 |
| `jy-draftc` | 11.5/11.6 草稿加解密、结构版本升降级、无头导出 | 11.8 基线不适用；仓库只适配到 11.6。加密草稿仍按 `DRAFT_ENCRYPTED` 拒绝，不用旧版本工具硬改 |

## 本机复核

2026-11-14 只读执行 `python scripts/jy.py probe`：

- 安装：`%LOCALAPPDATA%\JianyingPro\Apps\11.8.0.14778`
- 草稿根：`%LOCALAPPDATA%\JianyingPro\User Data\Projects\com.lveditor.draft`
- `root_meta_info.json` 存在；ffmpeg/ffprobe 位于剪映安装目录
- 首次探测时 native bridge 描述文件存在但 health 连接被拒；随后启动剪映，bridge 恢复为 11.8.0
- `probe` 未输出 token、cookie 或账号标识

2026-11-14 14:57 现场验收（临时多轨草稿，未触碰用户草稿）：

- `build`：640×360、2.5s，视频+图片画中画+音频+文字轨
- `render`：968,020B、2.507s、H.264+AAC；`draft_mutated:false`，导出前备份已生成
- `verify`：三帧 `0.2/1.2/2.2s`；目视确认字幕与图片叠加出现

因此本次交付能证明：安装版本、草稿根、ffmpeg、离线测试和一次真实原生导出；不能证明：其他剪映版本、会员素材、云端模板和未实现的 GUI 能力。

## 为什么不用纯 JSON 编辑覆盖一切

`draft_info.json` 只能说明结构存在，不能证明剪映渲染出预期画面。转场、滤镜、文字动画、会员素材和加密草稿都有独立的失败模式。任何写操作都要以 `inspect`、ffprobe 和抽帧为证据，不能拿“JSON 合法”代替“画面正确”。

## 商标与授权

`剪映`、`JianyingPro`、`CapCut` 是字节跳动相关主体的商标。本项目为独立的本地自动化技能，与字节跳动无隶属、赞助或背书关系。素材、字体、模板和会员能力分别受其授权约束；本技能不下载、破解或绕过任何会员资源。
