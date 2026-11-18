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
| 合成 | 蒙版、抠像、绿幕、混合层级、贴纸/文字模板叠加（绿幕/美颜/混合模式为 conditional，仅界面导出） | `14-mask-title.py` / `15-text-effects.py` |
| 特效 | 转场、滤镜、画面特效、色轮、曲线变速、调色/HSL | `16-transition-filter-effect.py` |
| 音频 | 音量、音量关键帧、淡入淡出、声道、音效、响度、BGM/原声 | `17-audio-mix.py` |
| 字幕 | 本地 ASR、SRT 生成/规范化/校验、SRT 入轨、字幕模板、版本化编辑、硬字幕 | `subtitle.asr.local` / `srt.from-local-asr` / `20-caption-template-highlight.py`（字幕模板；本地 ASR 需模型，无离线案例） |
| 交付 | probe、inspect、render、verify、抽帧、publish/register、版本链、能力探测 | `09-publish-dry-run.py` / `05-capability-report.py` / `19-version-chain.py` |

字幕只是六域之一；默认流程不再把字幕当主线。用户没要求字幕时不生成 SRT。

## 3. 三层边界

### A. 结构/入口已有，但未验收或明确未接线

- **基础调色 `adjust`**：官方 XML 语义、字段与范围已核对；native `picture_adjust`
  的触发路径未确认。plan 里写 `adjust` 会被**显式拒绝**，不会静默忽略。
- **视频定格 `freeze`**：只有“抽帧图片 + 前后视频段”的工作流，不冒充原生 freeze；
  plan 里写 `freeze` 会被显式拒绝。
- **HSL `hsl`**：已按官方 11.8 白名单写 `materials.hsl` + `enable_hsl`；2026-11-18 真机导出
  仍无像素变化，保持 `unverified`。
- **绿幕 `chroma`（conditional）**：`materials.chromas` 已接线；2026-11-18 构建的草稿在 11.8 UI
  打开即预览蓝底红块，`抠像` 面板读回“色度抠图”勾选、关键色绿色、强度 20；界面原生导出 1s 角点
  `(0,0,254)`、中心 `(253,0,0)`。native bridge `draftPath` 仍不应用 chroma，`render` 不能出绿幕成片，
  成片必须走剪映界面导出；技能不内置 GUI 自动化，界面导出是外部步骤。
- **花字 `text_effect`（conditional）**：结构已写入 `materials.effects`
  （2026-11-18 依 `pyJianYingDraft` 与 `jianying-tool` 复核；此前误写 `materials.filters`）；
  712 包真机导出帧差 `YAVG=4.1713` / `YMAX=209`，但需要真实 `flower` 缓存资源，缺包会静默回落。
- **文字气泡 `text_bubble`（unverified）**：同一结构路径；本机 `bubble` 缓存为 0，尚未渲染验收。
- **音效/音色 `audio_effect`**：2026-11-16 免费“萝莉”VC 资源真机输出 440Hz→740Hz；
  需要 `sub_type=0`、`path` 和带索引的 `audio_adjust_params`（证据已移出仓库），
  其他资源仍需逐个听感验收。
- **左右声道 `channel`**：写 `materials.sound_channel_mappings[].audio_channel_mapping`；
  左-only 源实测：0 左 -11.0dB/右静音、1 双声道 -11.0dB、2 双声道静音（2 是复制源右声道，
  源右本身静音）；证据已移出仓库，能力已升为 `implemented`。
- **背景填充 `background_fill`**：写 `materials.canvases`，已在 11.8 真机用纯色与渐变图确认
  不是默认黑底；只对最底层视觉轨生效。
- **混合模式 `mix_mode`**：写 `materials.effects[type=mix_mode]` + refs；11.8 界面预览与
  UI 原生导出为品红（品红即滤色生效的正确结果），但 native bridge `draftPath` 导出仍为纯红
  （纯红表示未应用），因此保持 `conditional`，`render` 会对含 mix_mode 的草稿写 warning。
- **响度 `loudness`**：对已构建草稿按片段测 EBU R128，并按目标 LUFS 写 volume；已用
  剪映原生导出复核增益（证据已移出仓库）。
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
| `timeline.template` | 片段模板保存/盖印 | file | implemented | Python | 从真实草稿提取任意片段、主素材和 extra 材质，应用时重映射全部 id；离线草稿往返已验证，未做像素抽帧 |
| `timeline.otio` | OpenTimelineIO 时间线交换 | file | implemented | Python | 导出 Timeline/Stack/Track/Clip/Gap；文字/贴纸/特效轨在回执里列 skipped；导入支持 Timeline/Stack/Track/数组 |
| `media.relink` | 草稿素材重新链接 | file | implemented | Python | 支持 `--from/--to` 前缀映射或 `--dir` 同名搜索；歧义保留原路径并报告；默认写副本 |
| `media.replace` | 片段素材替换/重定时 | file | implemented | ffprobe | 按 ffprobe 更新素材时长/宽高/音频标记；`--retime` 按新时长重算 speed；默认写副本 |
| `media.prune` | 清理无引用素材 | file | implemented | Python | 删除没有片段引用、也没有被其他已引用材质间接引用的素材；默认写副本 |
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
| `subtitle.asr.local` | 本地 Paraformer 识别字幕 | file | implemented | 剪映本地 ASR 模型 + numpy/onnxruntime/kaldi-native-fbank | 用剪映「识别字幕」已下载的模型；不登录、不联网；输出逐字时间戳与 SRT；先按静音分段（VAD 式）再切块，块长读 `strategy.json`；回执带 `quality`（剪映质量打分器，分数含义未标定，只做相对参考）与模型版本/字节数指纹 |
| `subtitle.apply` | SRT 写入可编辑字幕轨 | file | implemented | Python | `patch` 的 `add_subtitles`；自动成为下一版本，可继续 `set_text`/`set_style` |
| `subtitle.workflow` | 字幕自动流水线 | file | implemented | Python | 本地 ASR/SRT → packaging plan → 可编辑草稿；不给 `--srt` 时需要 ASR 模型/依赖 |
| `subtitle.template` | 字幕模板（caption_template_info） | resource | conditional | `Cache/artistEffect` + 模板资源 | 2026-11-16 免费“白字黑边”真实导出，cue 文本绑定成功；模板依赖字体/花字仍需缓存 |
| `subtitle.postprocess` | 本地去水词/标点 | file | implemented | Python + 剪映 `asr-punc.onnx` | 标点优先用剪映本地标点模型（断句点后静音 ≥0.6s 写句号），模型缺失回落按停顿启发式，回执 `punc.source` 标注；去水词仍是本地规则；不冒充剪映云端 AI |
| `subtitle.itn` | 数字/日期/单位规范化 | file | implemented | 剪映 `asr-itn-fst.fst` + kaldifst | `--itn` 用剪映下发的 ITN FST（标准 OpenFST，539 KB）把中文数字/日期/百分比转成阿拉伯数字；FST 或 kaldifst 缺失时跳过并写 `itn-skip` warning，不静默降级；「早上八点」这类拿不准的表达原样保留 |
| `subtitle.ass` | ASS/SSA 字幕导入导出 | file | implemented | Python | 解析事件时间、基础样式与常用内联标签（颜色/字号/粗斜下划线/重置），其他标签写入 `unsupported_tags`；导出读文字轨写 ASS；离线往返已验证，未做 libass 烧录比对 |
| `subtitle.burn` | 硬字幕烧录 | file | implemented | 带 libass 的 ffmpeg | 剪映自带 ffmpeg 不行；`imageio-ffmpeg` 自带 ffmpeg 7.1 带 libass，会被自动发现 |
| `adjust.basic` | 基础调色 | file | planned | Python | native 写入口未确认；plan 显式拒绝；2026-11-16 `materials.effects[type=adjust]` + `adjust_params` 抽帧无变化；2026-11-18 按 jianying-tool 写 `common_keyframes` `KFTypeBrightness` 也无像素变化 |
| `adjust.hsl` | HSL | file | unverified | Python | 2026-11-18 真机导出：`enable_hsl=true` + red hue=-100 下纯红帧仍 (252,0,0)，像素未变 |
| `color.wheels` | 色轮/色彩匹配 | resource | unverified | 缓存资源 | 2026-11-15 真机 gamma red=0.5 导出抽帧与无调色帧一致（证据已移出仓库）；2026-11-18 复核色轮资源仍无可用的缓存包 |
| `audio.fade` | 音频淡入淡出 | file | implemented | Python | 独立音频轨两次真实导出 volumedetect 渐变通过；原始回执未归档 |
| `audio.effect` | 音效/音色 | resource | conditional | 缓存资源 | 2026-11-16 免费“萝莉”VC 资源真机 440Hz→740Hz；其他资源仍需听感验收，不能一概承诺 |
| `audio.channel` | 左右声道 | file | implemented | Python | 2026-11-16 左only 源实测：channel=0 左 -11.0dB/右静音、channel=1 左右均 -11.0dB、channel=2 双声道静音；写 `materials.sound_channel_mappings` |
| `analysis.silence` | 静音段检测 | file | implemented | ffmpeg | `ffmpeg silencedetect`，输出静音段与保留段，同时给秒和微秒；2026-11-18 3 秒音/静音/音素材检出 1.0999–1.9001s（`--pad 0.1`）；只分析不改草稿 |
| `analysis.scenes` | 镜头切换检测 | file | implemented | ffmpeg | `select(scene)+showinfo`，按阈值和最小间隔输出切点与场景区间；2026-11-18 红蓝硬切 4 秒素材切点精确 2.0s；只分析不改草稿 |
| `analysis.retakes` | 重复/重拍片段检测 | file | implemented | Python | 按 cue 文本做本地 LCS 相似度，返回重复对与建议删除区间；是本地规则，不冒充语义模型 |
| `audio.loudness` | EBU R128 响度测量/增益 | file | implemented | ffmpeg | `loudnorm` 测量每个音频片段，按目标 LUFS 计算并写 volume；2026-11-18 4 秒正弦测得 -33.75 LUFS，`--max-gain-db 6 --apply` 后剪映原生导出实测 -27.86 LUFS（计划 -27.75，差 0.11 dB）；`--target -28` 导出实测 -28.06 LUFS（计划 -28.00，差 0.06 dB） |
| `speed.curve` | 曲线变速 | file | implemented | Python | 2026-11-18 真机导出：3s 段曲线 1→3，白块位置 1s 0.203 / 2s 0.547，线性对照 0.172 / 0.328，确认按曲线加速；`target/source` 时长仍按线性计算 |
| `crop.flip` | 裁剪/翻转 | file | implemented | Python | 垂直翻转有归档抽帧；裁剪/水平翻转同批目视确认，未单独归档 |
| `visual.reverse` | 视频倒放 | file | unverified | Python | `segment.reverse`；2026-11-15 真实导出被 11.8 忽略；2026-11-18 补 `reverse_path` 指向 ffmpeg 反向片仍无效（对照帧 0.172/0.328 与正常一致） |
| `visual.freeze` | 定格 | file | planned | Python | 只做抽帧工作流 |
| `effects.transition` | 转场 | resource | conditional | 缓存资源 | 未缓存会静默忽略 |
| `effects.filter` | 滤镜 | resource | conditional | 缓存资源 | 结构≠效果 |
| `effects.video` | 画面特效 | resource | conditional | 缓存资源 | 独立 effect 轨；效果包需缓存 |
| `visual.mask` | 形状蒙版 | resource | conditional | 缓存资源 | `common_mask` 单材质引用；2026-11-15 真机 `circle` + width/height 抽帧已确认（证据已移出仓库）；`config` 为空/字段不全给 warning |
| `visual.matting` | 智能抠像 | resource | conditional | Python（构建时另校验目录存在） | 构建时校验目录存在；外部不能凭空生成 |
| `visual.chroma` | 绿幕抠像 | file | conditional | Python | 2026-11-18 构建的草稿在 11.8 UI 打开即蓝底红块，`抠像` 面板读回“色度抠图”勾选、关键色绿色、强度 20；界面原生导出角点 `(0,0,254)`、中心 `(253,0,0)`。native bridge `draftPath` 仍不应用 chroma，成片走界面导出 |
| `visual.background_fill` | 视频/图片背景填充 | file | implemented | Python | `blur`/`color`；写 `materials.canvases` + refs，只对最底层视觉轨生效；2026-11-18 纯色填充角落 `(0,0,254)`、渐变图模糊填充角落 `(242,0,9)`/边缘 `(101,0,152)`，确认不是黑底 |
| `visual.mix_mode` | 视频混合模式 | file | conditional | Python | 写 `materials.effects[type=mix_mode]` + refs；2026-11-18 11.8 UI 预览/UI 原生导出为品红，但 native bridge `draftPath` 导出仍是纯红；`render` 会写 warning，需混合成片时走界面导出 |
| `visual.beauty` | 人像美颜/美型/美妆/美体 | file | conditional | Python | 写 `materials.effects[type=figure]`，仅在真正有美妆项时追加 `makeup-root`，支持 `skin/shape/makeup/body`；2026-11-18 11.8 UI 能读回 `磨皮=100` / `美白=100`，同草稿界面原生导出与 plain 对照：磨皮人脸 `avg_abs_rgb=1.215`、边缘能量 `-6.2%`，美白皮肤 `RGB +7.1/+8.8/+9.2`；native bridge `draftPath` 导出仍与 plain 帧 hash 相同，`figure_algorithm` 为空；`shape/makeup` 409 entitlement。结构可用，成片必须走剪映界面导出 |
| `visual.animation` | 视频/图片入场出场动画 | resource | conditional | 缓存资源 | 2026-11-16 免费“翻入”经 `material_animations[type=video_animation]` 真实导出 |
| `text.animation` | 文字动画 | resource | conditional | 缓存资源 | 2026-11-16 免费“变色输入”经 `material_animations` 真实导出 |
| `text.effect` | 花字/文字特效 | resource | conditional | `artistEffect` | `materials.effects[type=text_effect]` + `styles[0].effectStyle`；花字会重置文字颜色/描边/阴影；`text_template` 或 `text_bubble` 存在时花字被忽略。2026-11-18 用真实 `flower` 包 `7127669365423508767` 真机导出，和同文案无花字帧差 `YAVG=4.1713`/`YMAX=209`；带红字/绿描边/蓝阴影的 712 帧与默认 712 帧差 `0/0`，确认重置行为；`7187739440347958589`、`7351316503771368713` 均 409 entitlement。只对已缓存且账号可导出的 flower 资源承诺，不把“有包”当成“能导出” |
| `text.bubble` | 文字气泡 | resource | unverified | `artistEffect` | `materials.effects[type=text_shape]`；`capcut-mate` 实证 `effect_id` 与 `resource_id` 不是同一个值（`716434` / `6821385652727190024`），两者都要给；它只加装饰底板，不改文字填充/描边/阴影。模板 > 气泡 > 花字，气泡存在时花字被忽略。官方 11.8 选择协议没有 `text_shape`，气泡走 `text_template`；本机 `bubble` 缓存 0，未渲染验收 |
| `text.template` | 文字模板 | resource | conditional | 模板包 | 槽位需缓存；2026-11-18 “粉黑”免费字幕模板依赖 flower，缺花字包时导出成功但画面回落成普通文字，模板视觉不能只凭 `ok` 判定 |
| `sticker` | 贴纸 | resource | conditional | 缓存资源 | 独立 sticker 轨；2026-11-15 两个包：`7675620818189077810` 409 entitlement，`7202575978646737469` render ok 但抽帧无贴纸（证据已移出仓库） |
| `official.xml.draft` | 官方 XMLDraft 协议 | official | host_only | 官方技能目录 | 只读协议 |
| `official.hubcli.canvas` | 官方 canvas 命令面（55 条契约） | official | host_only | `agent_runtime_env/cli/hubcli` + 宿主注入的 bun/IPC | 只读契约清单见 [official-host](official-host.md)；技能不调用，调用需要宿主运行时 |
| `official.hubcli.media` | 官方媒体命令（转写/审片） | official | host_only | 同上 | `media.transcribe`（宿主 ASR，按毫秒返回段落/词）、`media.reviewVideo`；与本地 `subtitle.asr.local` 是两条线 |
| `official.motiongraph` | 动态图形（MotionGraph）SDK | official | host_only | `agent_runtime_env/motiongraph` + CEF renderer | SDK 自带 schema/预览/资源加载；技能不调用，无独立渲染入口 |
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
| timeline.template | file | python |
| timeline.otio | file | python |
| media.relink | file | python |
| media.replace | file | ffprobe |
| media.prune | file | python |
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
| audio.loudness | file | ffmpeg |
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
| subtitle.itn | file | python |
| subtitle.ass | file | python |
| subtitle.burn | file | ffmpeg_libass |
| adjust.basic | file | python |
| adjust.hsl | file | python |
| color.wheels | resource | cache_effect |
| audio.fade | file | python |
| audio.effect | resource | cache_effect |
| audio.channel | file | python |
| analysis.silence | file | ffmpeg |
| analysis.scenes | file | ffmpeg |
| analysis.retakes | file | python |
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
| visual.background_fill | file | python |
| visual.mix_mode | file | python |
| visual.beauty | file | python |
| text.animation | resource | cache_effect |
| text.effect | resource | cache_artistEffect |
| text.bubble | resource | cache_artistEffect |
| text.template | resource | cache_artistEffect |
| sticker | resource | cache_effect |
| official.xml.draft | official | official_skills |
| official.hubcli.canvas | official | official_skills |
| official.hubcli.media | official | official_skills |
| official.motiongraph | official | official_skills |
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
其中绿幕 chroma、美颜 figure、混合模式 mix_mode 为 `conditional`，只在剪映界面导出出片。

已接线但未验收：文字气泡、文字模板槽位、转场/滤镜/贴纸、调节包、
HSL/色轮、其他音效资源、视频倒放、智能抠像。

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
