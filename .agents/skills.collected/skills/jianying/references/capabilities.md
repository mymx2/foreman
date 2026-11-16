# 能力矩阵与三层边界

基线：Windows 剪映专业版 **11.8.0.14778**。本文件只描述“当前技能能做什么、哪一层缺什么”，
不把“结构写得进去”当成“效果已生效”。

## 1. 读法：状态不要混

| 状态 | 含义 | 对用户怎么说 |
|---|---|---|
| `implemented` | 技能已实现，且本机前置条件满足 | 可以做；仍按交付验收，不承诺未测效果 |
| `planned` | 官方协议/参考结构里有，技能还没接线 | “现在不支持，已列入扩展”；不要现场假装能写 |
| `conditional` | 有入口，但依赖资源、bridge、账号或本机配置 | “可以试，但要先满足条件；不满足就降级” |
| `missing_resource` | 本机没缓存对应资源包 | “当前不可用；先在剪映里下载/缓存，或去掉该效果” |
| `host_only` | 只能由剪映宿主/官方 `DraftEditing` 写 | “外部不能自动做；给交接步骤” |
| `account_gated` | 账号/云端/会员权益 | “技能不绕过；请在剪映客户端正常获取” |
| `manual` | 只能在 GUI 人工完成 | “给操作路径，不冒充自动化” |
| `unverified` | 结构或字段已写入，但没有真实导出/听感验收 | “结构可写，但未验收；不要当已支持” |

`capability_probe.py` 同时输出 `code_status`（代码是否实现）和 `status`（本机当前是否可用）。
两者不同是正常的：例如 `subtitle.burn` 代码已实现，但没有带 libass 的 ffmpeg 时 `status` 应为
`conditional`，而不是 `implemented`。

## 2. 六域与能力落点

| 域 | 主要能力 | 代表入口/案例 |
|---|---|---|
| 剪辑 | 多轨、分割、拼接、变速、倒放、关键帧、画中画、画布、patch、版本链 | `build` / `patch` / `13-multitrack-pip.py` / `19-version-chain.py` |
| 合成 | 蒙版、抠像、绿幕、混合层级、贴纸/文字模板叠加 | `14-mask-title.py` / `15-text-effects.py` |
| 特效 | 转场、滤镜、画面特效、色轮、曲线变速、调色/HSL | `16-transition-filter-effect.py` |
| 音频 | 音量、音量关键帧、淡入淡出、声道、音效、BGM/原声 | `17-audio-mix.py` |
| 字幕 | 本地 ASR、SRT 生成/规范化/校验、SRT 入轨、字幕模板、版本化编辑、硬字幕 | `subtitle.asr.local` / `srt.from-local-asr` / `20-caption-template-highlight.py`（字幕模板；本地 ASR 需模型，无离线案例） |
| 交付 | probe、inspect、render、verify、抽帧、publish/register、版本链、能力探测 | `09-publish-dry-run.py` / `05-capability-report.py` / `19-version-chain.py` |

字幕只是六域之一；默认流程不再把字幕当主线。用户没要求字幕时不生成 SRT。

## 3. 三层边界

### A. 结构/入口已有，但未验收或明确未接线

- **基础调色 `adjust`**：官方 XML 语义、字段与范围已核对；native `picture_adjust`
  的触发路径未确认。plan 里写 `adjust` 会被**显式拒绝**，不会静默忽略。
- **视频定格 `freeze`**：只有“抽帧图片 + 前后视频段”的工作流，不冒充原生 freeze；
  plan 里写 `freeze` 会被显式拒绝。
- **HSL `hsl`**：已按官方 11.8 白名单写 `materials.hsl` + `enable_hsl`；真实导出首测
  未观察到像素变化，保持 `unverified`。
- **绿幕 `chroma`**：已按 `materials.chromas` 写入并挂 refs；真实导出首测未抠绿，
  可能还缺触发字段，保持 `unverified`。
- **花字/气泡 `text_effect` / `text_bubble`**：结构已写入 `materials.filters`，
  但需要真实缓存资源 id，尚未渲染验收。
- **音效/音色 `audio_effect`**：2026-11-16 免费“萝莉”VC 资源真机输出 440Hz→740Hz；
  需要 `sub_type=0`、`path` 和带索引的 `audio_adjust_params`（证据 `evidence/2026-11-16-audio-effect/`），
  其他资源仍需逐个听感验收。
- **左右声道 `channel`**：写 `materials.sound_channel_mappings[].audio_channel_mapping`；
  左-only 源实测 0 保持原样、1 左复制双声道、2 右复制双声道（证据 `evidence/2026-11-16-channel-mapping/`），
  已从 `unverified` 升为 `implemented`。
- **`native` 逃生舱**：可写 `segment` / `material` / 任意已存在 `materials` 桶；
  技能不校验字段语义，必须自带真实结构并回读验收。

> 官方 `XMLDraft` 的标签名不是 `draft_info.json` 的字段名。每个能力都要先做“XML 语义 →
> native draft 结构”的映射，再用 `inspect` + 真实导出抽帧确认；不能把 XML 标签直接抄进 JSON。

### B. 本地有入口，但受资源缓存/登录/权益影响

- 转场、滤镜、画面特效、贴纸、文字模板、形状蒙版、智能抠像、文字动画、会员字体
- 云端素材、模板包、音乐/音效
- 云端 AI 字幕/翻译/划重点、歌词识别、TTS、数字人

> 本地字幕识别已单独接线：`subtitle.asr.local` 用剪映「识别字幕」首次下载的
> Paraformer 模型，不登录、不联网，不使用云端额度；它不等于剪映客户端的
> 云端翻译/划重点/去水词。

> 画面特效、贴纸、文字模板、形状蒙版、智能抠像、文字动画现在**已有写入口**，但
> 都依赖本机已缓存对应资源包；矩阵里标 `conditional`，资源缺失时探测结果会降为
> `missing_resource`。资源存在也只代表“有条件可用”，不代表账号有权益。

处理口径：

1. 先跑 `capability_probe.py`，看 `Cache/effect` / `Cache/artistEffect` 是否有对应资源；
2. 有资源时也只能说“有条件可用”，因为账号权益仍可能拦；
3. 导出遇到 `film_export_entitlement_denied` / `film_export_dependency_missing` 时，
   按错误码降级，不重试轰炸，不伪造资源 id；
4. 资源缺失时，案例应 `SKIP` 或明确失败，不能把空壳当 PASS。

### C. 必须宿主/官方内部工具或人工界面

- `DraftEditing` / `MaterialRecall` / `Selection Expression`
- 云端字幕识别/翻译/划重点/去水词、歌词识别、镜头切分、智能高光
- 模板套用、云端素材、数字人、AI 成片
- 音色克隆、说话成曲（官方协议本身列为暂不支持）

技能只做：读官方协议、给字段索引、给人工交接步骤。**不做**：伪造宿主 token、改 DLL 哈希、
打补丁绕过 entitlement、解密草稿。

## 4. 能力矩阵（与 `scripts/capability_probe.py` 同步，测试强制校验）

> `test_skill.py::CapabilityTests.test_matrix_matches_capabilities` 会逐行比对本表“代码状态”、
> 通道、`requires` 与 `CAPABILITIES`；`label`/`note` 为空也会让测试变红。

| id | 能力 | 通道 | 代码状态 | 本机前置 | 备注 |
|---|---|---|---|---|---|
| `draft.build` | 新建多轨明文草稿 | file | implemented | 剪映安装 + ffprobe | 不启动剪映 |
| `draft.inspect` | 读取草稿结构 | file | implemented | Python | 不解密 |
| `draft.patch` | 修改明文草稿 | file | implemented | Python | 默认写副本 |
| `version.history` | 草稿版本链（快照/差异/恢复） | file | implemented | Python | 全量快照；restore 新目录；diff 比结构+材质指纹；导出回写落 editor-rewrite |
| `export.render` | 原生导出视频/音频/动图 | bridge | conditional | 剪映运行 + bridge health | 端口每次启动变；format 支持 mp4/mov/gif/mp3/wav/aac/flac/aiff/ogg；draftPath 入口不支持视频自定义码率，分辨率/帧率走画布 |
| `export.transcode` | 本机 ffmpeg 转码到目标码率 | file | implemented | ffmpeg | 后处理，不是剪映原生码率；补 native bridge 不支持视频码率 |
| `export.publish` | 登记首页 | file | implemented | 草稿根 | 默认 dry-run |
| `resource.catalog` | 本机资源目录 | file | implemented | Python | 只读 `rp.db` + `Cache` 包；`cached` 不代表权益或导出效果 |
| `resource.download` | 下载免费素材/字体 | file | implemented | Python | 只下载免费非商业资源；字体、字幕模板已真实导出验证；文字模板槽位仍需验收 |
| `resource.verify` | 资源面板/权益/缓存预检 | file | implemented | Python | 检查免费、缓存、期望面板；不验像素，防资源类型混用 |
| `packaging.preset` | 本地包装 preset | file | implemented | Python | 主视频/标题/字幕/BGM/字体/字幕模板/动画组合；本地 preset，不是云端智能包装 |
| `visual.keyframes` | 缩放/位移/透明度/旋转/音量关键帧 | file | implemented | Python | position_x/rotation 未单独抽帧 |
| `speed.linear` | 线性变速 | file | implemented | Python | 图片 speed=1 |
| `audio.volume` | 音量/音量关键帧 | file | implemented | Python | 0..10 |
| `canvas.layout` | 画布/多轨/画中画 | file | implemented | Python | 画中画 flag=2 + render_index≥1 |
| `text.basic` | 文字/字幕样式 | file | implemented | Python | 必须 type=text |
| `text.highlight` | 本地关键词高亮 | file | implemented | Python | 按词匹配写 `content.styles` range；本地规则，不冒充剪映 AI 划重点 |
| `text.decorate` | 文字背景/阴影/粗斜下划线 | file | implemented | Python | 真实导出抽帧已确认背景/阴影/粗体/下划线；原始抽帧未归档 |
| `native.escape` | native 结构逃生舱 | file | unverified | Python | 技能不校验字段语义 |
| `subtitle.srt` | SRT 生成/校验 | file | implemented | Python | 不做语音识别 |
| `subtitle.asr.local` | 本地 Paraformer 识别字幕 | file | implemented | 剪映本地 ASR 模型 + numpy/onnxruntime/kaldi-native-fbank | 用剪映「识别字幕」已下载的模型；不登录、不联网；输出逐字时间戳与 SRT |
| `subtitle.apply` | SRT 写入可编辑字幕轨 | file | implemented | Python | `patch` 的 `add_subtitles`；自动成为下一版本，可继续 `set_text`/`set_style` |
| `subtitle.workflow` | 字幕自动流水线 | file | implemented | Python | 本地 ASR/SRT → packaging plan → 可编辑草稿；不给 `--srt` 时需要 ASR 模型/依赖 |
| `subtitle.template` | 字幕模板（caption_template_info） | resource | conditional | `Cache/artistEffect` + 模板资源 | 2026-11-16 免费“白字黑边”真实导出，cue 文本绑定成功；模板依赖字体/花字仍需缓存 |
| `subtitle.postprocess` | 本地去水词/标点（启发式） | file | implemented | Python | 规则匹配删除口头禅、按停顿加标点；不冒充剪映 AI 去水词/标点 |
| `subtitle.burn` | 硬字幕烧录 | file | implemented | 带 libass 的 ffmpeg | 剪映自带 ffmpeg 不行；`imageio-ffmpeg` 自带 ffmpeg 7.1 带 libass，会被自动发现 |
| `adjust.basic` | 基础调色 | file | planned | Python | native 写入口未确认；plan 显式拒绝；2026-11-16 `materials.effects[type=adjust]` + `adjust_params` 抽帧无变化 |
| `adjust.hsl` | HSL | file | unverified | Python | 结构已写；真实导出未见像素变化 |
| `color.wheels` | 色轮/色彩匹配 | resource | unverified | 缓存资源 | 2026-11-15 真机 gamma red=0.5 导出抽帧与无调色帧一致（证据 `evidence/2026-11-15-real-probes/wheel/`） |
| `audio.fade` | 音频淡入淡出 | file | implemented | Python | 独立音频轨两次真实导出 volumedetect 渐变通过；原始回执未归档 |
| `audio.effect` | 音效/音色 | resource | conditional | 缓存资源 | 2026-11-16 免费“萝莉”VC 资源真机 440Hz→740Hz；其他资源仍需听感验收，不能一概承诺 |
| `audio.channel` | 左右声道 | file | implemented | Python | 2026-11-16 左only 源实测：channel=0 左 -11.0dB/右静音、channel=1 左右均 -11.0dB、channel=2 双声道静音；写 `materials.sound_channel_mappings` |
| `speed.curve` | 曲线变速 | file | unverified | Python | 只写材质，不改 target/source 时长；曲线像素未抽帧 |
| `crop.flip` | 裁剪/翻转 | file | implemented | Python | 垂直翻转有归档抽帧；裁剪/水平翻转同批目视确认，未单独归档 |
| `visual.reverse` | 视频倒放 | file | unverified | Python | `segment.reverse`；2026-11-15 真实导出被 11.8 忽略（案例 12） |
| `visual.freeze` | 定格 | file | planned | Python | 只做抽帧工作流 |
| `effects.transition` | 转场 | resource | conditional | 缓存资源 | 未缓存会静默忽略 |
| `effects.filter` | 滤镜 | resource | conditional | 缓存资源 | 结构≠效果 |
| `effects.video` | 画面特效 | resource | conditional | 缓存资源 | 独立 effect 轨；效果包需缓存 |
| `visual.mask` | 形状蒙版 | resource | conditional | 缓存资源 | `common_mask` 单材质引用；2026-11-15 真机 `circle` + width/height 抽帧已确认（证据 `evidence/2026-11-15-real-probes/mask/`）；`config` 为空/字段不全给 warning |
| `visual.matting` | 智能抠像 | resource | conditional | Python（构建时另校验目录存在） | 构建时校验目录存在；外部不能凭空生成 |
| `visual.chroma` | 绿幕抠像 | file | unverified | Python | 结构已写；真实导出首测未抠绿 |
| `visual.animation` | 视频/图片入场出场动画 | resource | conditional | 缓存资源 | 2026-11-16 免费“翻入”经 `material_animations[type=video_animation]` 真实导出 |
| `text.animation` | 文字动画 | resource | conditional | 缓存资源 | 2026-11-16 免费“变色输入”经 `material_animations` 真实导出 |
| `text.effect` | 花字/文字特效 | resource | unverified | `artistEffect` | 官方要求 ref 为 `flower`；`DeepGlow` 是 `tool_text_glow`，此前资源类型不匹配。需真实 flower 资源再做像素验收 |
| `text.bubble` | 文字气泡 | resource | unverified | `artistEffect` | 需真实气泡资源 |
| `text.template` | 文字模板 | resource | conditional | 模板包 | 槽位需缓存 |
| `sticker` | 贴纸 | resource | conditional | 缓存资源 | 独立 sticker 轨；2026-11-15 两个包：`7675620818189077810` 409 entitlement，`7202575978646737469` render ok 但抽帧无贴纸（证据 `evidence/2026-11-15-real-probes/sticker/`） |
| `official.xml.draft` | 官方 XMLDraft 协议 | official | host_only | 官方技能目录 | 只读协议 |
| `ai.subtitle` | 智能字幕 | account | account_gated | 剪映客户端 | 云端识别/翻译/划重点仍受账号限制；本地识别见 `subtitle.asr.local` |
| `ai.lyric` | 歌词识别/动效 | account | account_gated | 宿主/云端 | 不调用 |
| `ai.tts` | TTS/音色克隆 | account | account_gated | 账号/云端 | 官方暂不支持克隆 |
| `ai.digital_human` | 数字人/AI 成片 | account | account_gated | 云端 | 不解锁 |
| `template.package` | 模板/素材包 | account | account_gated | 客户端/云端 | 人工交接 |

## 4.1 代码依赖（门禁读取）

> 与 `capability_probe.py` 的 `channel` / `requires` 逐条比对；改代码或改本表都必须两边同步。
> `—` 表示不依赖本机资源（账号类能力由宿主/账号侧决定）。

| id | channel | requires |
|---|---|---|
| draft.build | file | install, ffprobe |
| draft.inspect | file | python |
| draft.patch | file | python |
| version.history | file | python |
| export.render | bridge | install, bridge |
| export.transcode | file | ffmpeg |
| export.publish | file | draft_root |
| resource.catalog | file | python |
| resource.download | file | python |
| resource.verify | file | python |
| packaging.preset | file | python |
| visual.keyframes | file | python |
| visual.animation | resource | cache_effect |
| speed.linear | file | python |
| audio.volume | file | python |
| canvas.layout | file | python |
| text.basic | file | python |
| text.highlight | file | python |
| text.decorate | file | python |
| native.escape | file | python |
| subtitle.srt | file | python |
| subtitle.asr.local | file | asr_model, asr_deps |
| subtitle.apply | file | python |
| subtitle.workflow | file | python |
| subtitle.template | resource | cache_artistEffect |
| subtitle.postprocess | file | python |
| subtitle.burn | file | ffmpeg_libass |
| adjust.basic | file | python |
| adjust.hsl | file | python |
| color.wheels | resource | cache_effect |
| audio.fade | file | python |
| audio.effect | resource | cache_effect |
| audio.channel | file | python |
| speed.curve | file | python |
| crop.flip | file | python |
| visual.reverse | file | python |
| visual.freeze | file | python |
| effects.transition | resource | cache_effect |
| effects.filter | resource | cache_effect |
| effects.video | resource | cache_effect |
| visual.mask | resource | cache_effect |
| visual.matting | resource | python |
| visual.chroma | file | python |
| text.animation | resource | cache_effect |
| text.effect | resource | cache_artistEffect |
| text.bubble | resource | cache_artistEffect |
| text.template | resource | cache_artistEffect |
| sticker | resource | cache_effect |
| official.xml.draft | official | official_skills |
| ai.subtitle | account | — |
| ai.lyric | account | — |
| ai.tts | account | — |
| ai.digital_human | account | — |
| template.package | account | — |

## 5. 资源预检口径

`capability_probe.py` 只看目录计数与注册表，不读内容、不读 token：

- `Cache/effect`：转场/滤镜/特效/贴纸/动画等资源包；
- `Cache/artistEffect`：文字模板/花字等；
- `Cache/music`：音乐/音效；
- `Cache/template`：模板；
- `Resources/canvas_agent/skills`：官方技能目录；
- `Resources/canvas_agent/packaged-skills.json`：已注册官方技能。

需要知道“具体有哪些、是否已下载”时，跑
`python scripts/jy.py resource stats`、`resource list --panel flower2` 或
`resource resolve <id|标题>`。它只读 `Cache/ressdk_db/*/rp.db` 和已下载包，
不联网、不下载、不解锁会员资源；`cached=true` 只代表本机有包。

下载免费资源用 `jy.py resource download <id|标题> --apply`，默认 dry-run。
它只下免费非商业资源，会员/商业/过期 URL 会明确失败；字体已用 `font_path` 真实导出验证；
字幕模板已用 `caption_template_info` + `caption_info` 真实导出验证；文字模板槽位尚未验收。

计划里的资源 spec 可以直接写 `resource_ref`（完整标题/ID/md5）；短标题不会模糊猜，先用
`resource resolve` 看候选。`build --fetch-resources` 会自动下载未缓存的免费资源，字体映射到
`font_path`，其他资源填 `resource_id`/`path`/`name`。会员/商业资源仍返回 `RESOURCE_GATED`，不做绕过。

计数 > 0 只证明“本机有缓存”，**不证明**：
- 账号有权益；
- 资源 id 与当前版本匹配；
- 导出时剪映会真的应用。

所以资源类能力的状态停在 `conditional` / `unverified`，不能标 `implemented`；必须再用真实导出验收。

## 6. 官方 XMLDraft 索引

安装目录里的官方技能：

```
<install>\Resources\canvas_agent\skills\jianying.hub.studio_lyra_xml_timeline_builder_v2\
```

它覆盖的字段族（只作为扩展来源，不是本技能的已实现清单）：

- `timeline.md`：根、轨道、时间、资源、响度均衡
- `transform.md`：位置/缩放/裁剪/变形/跟踪
- `segment-visual.md`：video/image、蒙版、混合模式、倒放、定格
- `segment-text-sticker.md`：text/subtitle/lyrics/sticker、文字模板、动画
- `segment-audio.md`：audio/sound、淡入淡出、声道、降噪、人声增强
- `segment-effects.md`：filter/effect、转场、视频算法
- `color-adjustment.md`：亮度/对比度/饱和度/色温/锐化/暗角/褪色/颗粒/HSL
- `media-processing.md`：变声、防抖、画质增强、补帧、超分、降噪、人声分离
- `extensions.md`：字幕识别、歌词识别、镜头切分、音视频同步
- `segment-packages.md`：模板包/素材包
- `compound.md`：复合片段
- `no-support.md`：音色克隆、说话成曲、手动美体滑杆等

### 6.1 官方协议能力与技能接线状态

已接线并有真实验收：基础变换/关键帧、文字基础样式与背景阴影、字幕模板
（`caption_template_info` + `caption_info`）、本地 ASR/SRT、文字/视频动画、本地关键词高亮、
音频音量/淡入淡出、形状蒙版、裁剪/翻转、独立 effect/filter 轨（资源缓存时）。

已接线但未验收：文本花字/气泡、文字模板槽位、转场/滤镜/贴纸、调节包、
HSL/色轮/绿幕、其他音效资源、视频倒放、曲线变速、智能抠像。

尚未接线：基础调节 `adjust`、色彩匹配、眼睛校正/滑杆参数/智能补光/去闪烁、
媒体处理（音频降噪/人声分离/乐器分离/人声增强/画质增强/补帧/超分/视频降噪/防抖/智能响度）、
画面变形/跟踪、文字关键词/朗读、歌词/贴纸、音频节拍、复合片段、素材包/模板包、
字幕识别/歌词识别/镜头切分/智能高光/音视频同步（本地 ASR 只覆盖字幕识别）。

官方协议明确：`DraftEditing` 是唯一草稿写入口；外部 agent 不能提交 Selection，也不能伪造
`blueprint_ref`。所以本技能只把这份协议当“字段字典”，不把它当可执行 API。

## 7. 不承诺与不做

- 不承诺“支持剪映全部功能”；只承诺矩阵里 `implemented` 且验收过的项。
- 视频自定义码率不在 native draftPath 导出入口支持范围：2026-11-16 实测追加 options 全被 409
  `film_export_invalid_request`；分辨率/帧率来自草稿画布，码率需要客户端导出或 ffmpeg 转码。
- 不下载/解锁会员素材，不绕 entitlement，不伪造 token，不改 DLL 哈希。
- 不把 `render` 的历史成功当本轮证据；bridge 不可达时必须写“未验证”。
- 不为凑案例数写空壳；案例必须有产出 + 断言，缺依赖时 `SKIP`（退出 77）。

## 8. 案例映射

| 案例 | 覆盖能力 |
|---|---|
| `01-build-text-draft.py` | `draft.build` / `draft.inspect` / `text.basic` |
| `02-srt-build-check.py` | `subtitle.srt` |
| `03-validate-example-plans.py` | 计划结构校验 |
| `04-media-build.py` | `draft.build` / `canvas.layout` / 封面 |
| `05-capability-report.py` | 状态矩阵 / `official.xml.draft` |
| `06-freeze-workflow.py` | `visual.freeze`（工作流级，不是 native 字段） |
| `07-vertical-title-bgm.py` | `canvas.layout` / `text.basic` / `audio.volume` |
| `08-patch-copy.py` | `draft.patch` / `text.basic` |
| `09-publish-dry-run.py` | `export.publish`（dry-run） |
| `10-srt-from-audio.py` | `subtitle.srt` |
| `11-burn-subtitles.py` | `subtitle.burn` |
| `12-advanced-fields.py` | `crop` / `flip` / `reverse` / `mask` / `curve_speed` / `matting` / `color_wheel` / `native` |
| `13-multitrack-pip.py` | 多轨画中画 + 关键帧 + 蒙版 + 变速 |
| `14-mask-title.py` | 蒙版 + 文字模板 + 阴影/背景 |
| `15-text-effects.py` | 花字/气泡/文字动画 + 贴纸 |
| `16-transition-filter-effect.py` | 转场 + 滤镜 + 画面特效 + 色轮 |
| `17-audio-mix.py` | BGM + 原声 + 淡入淡出 + 声道 + 音效 |
| `18-spoken-piece.py` | 口播成片：字幕 + 标题 + 画中画 + BGM + 导出验收 |
| `19-version-chain.py` | `version.history`：build → patch → `version diff` → `version restore` |
| `20-caption-template-highlight.py` | `subtitle.template` / `text.highlight` / `caption_info` 结构 |
| `21-auto-subtitles-transcode.py` | `subtitle.workflow` / `export.transcode`（已有 SRT 路径） |

案例只证明“结构/离线行为”，不证明真实导出后的像素、字体与效果。资源类能力没有真实导出证据时，
不要因为矩阵里写了就当成已支持。

## 9. 维护

新增能力时按顺序：

1. 在 `scripts/capability_probe.py` 的 `CAPABILITIES` 加条目（id/label/category/channel/requires/note）；
2. 在本文件表格加同一行；`test_matrix_matches_capabilities` 会校验两处状态逐条一致；
3. 在 `references/plan-schema.md` 写字段、单位、枚举、资源依赖；
4. 在 `references/limits.md` 写“已测/未测”；
5. 加 `examples/NN-*.py` 与 `test_skill.py` 正/负向测试；
6. 跑 `capability_probe.py`、`run_examples.py`、`test_skill.py`、`check_docs.py`。

状态只升不降：从 `planned` 到 `implemented` 需要真实导出证据；没有证据就保持 `planned` 或
`unverified`。
