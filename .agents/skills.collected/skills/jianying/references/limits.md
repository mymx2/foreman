# 能力边界与验证矩阵

基线：Windows，剪映专业版 **11.8.0.14778**，native bridge 11.8.0 / build 14778。
核对日期：2026-11-18。以下“已跑通”条目来自参考工程的 11.8 实测记录；本次会话复验了 `probe`、
草稿构建/结构/补丁/临时根登记、离线测试，并在 14:57 启动剪映后完成一次临时多轨草稿的原生导出。
2026-11-14 又对“未验证”项做了集成复验：position_y/opacity/volume 关键帧、变速、
草稿画布尺寸在导出中被尊重、硬字幕烧录均已实测（native draftPath 导出不接受自定义 options，详见下表）；
volume 关键帧复验时发现并修复了 audio 轨漏写关键帧的 bug。
2026-11-15 全能力 smoke：文字背景/阴影/粗体/下划线、独立音频轨淡入淡出经真实导出抽帧/波形验证
（原始抽帧与回执未归档，只有结论与数字）；
`adjust`、HSL、chroma 的 native 写入在 11.8 真实导出中被忽略；`adjust` 已改为显式拒绝，
HSL 降级为 unverified；chroma 结构在 UI 打开即生效、界面导出可出片，但仍不被 native bridge 应用，
按 conditional 处理，不再当“结构写了就生效”。
其他版本的结构和桥接能力可能不同；`probe` 输出的 `bridge.capabilities` 是当场事实，不要照抄本文。
完整的三层能力矩阵（已实现/计划/资源/宿主/账号）见 [capabilities](capabilities.md)；本文件只写
“已测/未测/不承诺”，两者要一起读。2026-11-15 真机探针的 mask、flip、audio-channel、wheel、sticker
五项已归档在仓库外；2026-11-16 的
render 回归归档在仓库外；
硬字幕重验归档在仓库外；
字幕模板/字体/高亮/文字与视频动画/包装抽帧归档在
证据已移出仓库；
一键字幕/本地转码回执归档在
证据已移出仓库；
审查后真机 `build → render` 复核归档在
证据已移出仓库；
文字背景/阴影、audio fade、裁剪/水平翻转未归档原始文件，下表相关行按“未归档证据”标注，复核时以已归档目录为准。
模板/ASS/OTIO/媒体分析与维护的离线证据在
证据已移出仓库。

## 已在本机跑通

| 能力 | 证据 |
|---|---|
| 新建明文草稿 | `build` 生成 4s 多轨草稿，`inspect` 结构正确 |
| 视频主轨 | 1920×1080 / 30fps / H.264+AAC，成片 4.017s |
| 图片画中画 | 0.45/0.32 缩放、右上角定位，成片可见 |
| 图片作主轨 | 1080×1920 竖屏，3.018s，可见 |
| 独立音频 / BGM | `materials.audios` + audio 轨，volumedetect 证实混合 |
| 音量 | `volume: 0.25` 明显衰减；patch 到 0.15 仍可导 |
| 多段字幕 | 同一文字轨 3 段，按时间切换，抽帧确认 |
| 双文字轨 | 标题轨 + 字幕轨同时显示，1080×1920 抽帧确认 |
| 文字样式 | 字号/颜色/描边/对齐/位置，抽帧确认 |
| 文字背景/阴影/粗体/下划线 | 2026-11-15 真实导出抽帧：深色背景框、阴影、粗体与下划线均可见；原始抽帧未归档 |
| 文字动画 | 2026-11-16 免费“变色输入”经 `animations` → `material_animations`；0.7s 空白、1.2s 显示“打字”、2.0s 显示“打字动画”，颜色/打字动效可见 |
| 本地关键词高亮 | 2026-11-16 “AI工具分享 AI时代”按词高亮 AI，真实导出两处 AI 为黄色粗体、其余白色；本地规则，不是 AI 划重点 |
| 视频动画 | 2026-11-16 免费“翻入”经 `animations` → `material_animations[type=video_animation]`；0.3s 黑、0.8s 翻入中、1.5s 完整画面 |
| 本地包装 preset | 2026-11-16 `jy.py packaging` 由 60s 视频 + 20 cue SRT + 毛笔行楷 + 白字黑边 + 变色输入生成计划；build/render 2s/30s 抽帧看到标题书法字和字幕模板；这是本地组合，不是云端智能包装 |
| 一键字幕工程 | 2026-11-16 `jy.py auto-subtitles --srt ...` 生成 2.5s 可编辑草稿，字幕轨、标题、版本链齐全；证据已移出仓库 |
| 本地转码 | 2026-11-16 `jy.py transcode --video-bitrate 500k` 用完整用户 ffmpeg 输出 86,879B / 2.0s / 320×180 / H.264；这是后处理，不是剪映原生码率 |
| 音频淡入淡出 | 2026-11-15 两次真实导出 volumedetect：`in/out=1.0s`；一次 0s -39.0dB / 1.0s -24.1dB / 2.2s -34.0dB，另一次 0s -36.7dB / 1.0s -26.1dB / 1.8s -36.6dB，首尾衰减、中段抬升趋势一致；视频原声淡入淡出未生效。原始回执未归档。 |
| 缩放关键帧 | 1.0→0.5 逐步缩小，抽帧确认 |
| 位移/透明度关键帧 | 2026-11-14 `position_y`+`opacity` 多段关键帧，导出抽帧确认位移与淡入淡出 |
| 音量关键帧 | 2026-11-14 audio 轨 `keyframes.volume`（修复漏写 bug 后），渲染器写入 KFTypeVolume，volumedetect 证实 -27.5/-18.3dB 渐变 |
| 变速 | `speed: 2.0`，4s 源取 3s 目标出 1.5s，成片 1.509s；2026-11-14 复验 2.02s |
| 原生导出 | 2026-11-14 临时多轨草稿：968,020B / 2.507s / 640×360 / H.264+AAC，`draft_mutated:false` |
| 原生导出（多文件回写） | 2026-11-16 真机：320×180/30 临时草稿导出 30,294B / 1.021s / H.264+AAC；`draft_mutated:true`、`draft_files_changed:["draft_content.json"]`，剪映确实在导出时写 `draft_content.json`（证据已移出仓库） |
| 草稿画布尺寸被导出尊重 | 2026-11-14 640×360/30 草稿画布被导出尊重；native draftPath 导出不接受 options，帧率/分辨率走 `canvas_config` |
| 硬字幕烧录 | 2026-11-14 用 user libass ffmpeg 对真实视频烧录中文 SRT，`drift_ok:true`，抽帧确认“测试字幕”字形正确；2026-11-16 用 `imageio-ffmpeg` 自带 ffmpeg 7.1 重验 30s 中文 SRT，`drift_ok:true`、6/6 cue 完整（证据已移出仓库） |
| 裁剪/翻转 | 垂直翻转有仓库外归档抽帧；裁剪与水平翻转同批导出目视确认，未单独归档抽帧 |
| 形状蒙版 | 2026-11-15 真机 `resource_id=82432977 circle` + `config={center_x:0.5,center_y:0.5,width:0.5,height:0.5,feather:0.1}` 导出抽帧：中央椭圆彩条可见；`config={}` 同机导出全黑（证据已移出仓库） |
| 改已有明文草稿 | `patch` 复制副本，改字+移位+音量后重新导出并抽帧确认 |
| 首页登记（临时根） | 复制+38 键条目+draft_ids 1→2+备份+回读 verified |
| 首页登记（真实根） | `register`/`publish --apply` 会改用户索引；真实根必须逐次获得授权，离线测试只操作临时根 |
| 真实根 publish→首页显示 | 2026-11-14 对真实根 `publish --apply`：applied/verified=true、draft_ids 2→3、自动备份；重启剪映后首页出现该草稿 tile（封面/名称/时长/时间戳正确），条目在应用启动后保留；清理恢复原始索引后 tile 消失，用户既有草稿不受影响 |
| SRT 生成与校验 | `scripts/test_skill.py` 生成 2 行并 `srt.check` 通过 |
| 本地 ASR | 2026-11-16 60s 音频：259 token / 20 cue / 6.2s；完整 36 分钟音频：7761 token / 513 cue / 145 块 / 219.7s；模型来自剪映 `local-asr-supplies`，不登录、不联网 |
| 字幕入轨与版本 | v001 原片 → v002 `add_subtitles` 20 cue → v003 `set_text`/`set_style`；两次真实导出抽帧确认白字黑边、改字和黄色样式（60s 样本） |
| 本机资源目录 | `jy.py resource stats`：6472 条元数据 / 280 个包 / 271 条匹配；已缓存主要是美颜、运镜、抠像、文字光效、调节；字体/贴纸/转场/滤镜为 `cached=0`，字幕模板已按需下载 |
| 免费字体下载+使用 | 2026-11-16 `resource download 毛笔行楷 --apply` 下载 5.9MB 字体包，解出 `HYXingKaiJ.ttf`；用 `font_path` 构建 60s 草稿并真实导出，1.0s 抽帧确认黄色毛笔行楷字形与黑色描边 |
| 资源自动解析 | 2026-11-16 `resource_ref:"DeepGlow"` 能解析到缓存 `tool_text_glow` 包并成功导出；但 640×360 暗底抽帧只有白字、没有可见光效。`resource_ref:"毛笔行楷"` 自动下载字体并导出书法字 |
| 免费资源下载 | `resource download` 支持免费非商业资源；本机字幕模板 788 条、文字模板 9 条、视频效果 3 条有可用 URL；会员/商业资源返回 `RESOURCE_GATED`，过期 URL 返回 `RESOURCE_URL_EXPIRED` |
| 字幕模板（caption_template） | 2026-11-16 免费“白字黑边”下载到缓存；文字材质写 `caption_template_info` + `caption_info`，真实导出 2s 帧显示“这是字幕模板测试”，cue 文本绑定成功；模板字号/间距会覆盖基础样式 |
| 本地去水词/标点 | 2026-11-16 60s ASR 259→247 token，`--remove-fillers` 删除默认口头禅；`--punctuate` 优先用 `asr-punc.onnx` 模型，缺失时回落规则启发式，回执 `punc.source` 区分 model/heuristic；不冒充剪映 AI |
| 离线草稿回归 | `build`/`inspect`/`patch`/`version` 链/`publish` dry-run/覆盖备份、资源下载失败分支、桥接 fake server 等离线测试全部通过 |
| 版本链 | 2026-11-15 真实草稿上 `build` → `patch` → `version diff` → `version restore` 通过；`version-v2.mp4` 真实导出 378,160B / 2.02s / 320×180，回执挂到 `v002` 的 `exports`；2026-11-16 起支持 `Timelines/<id>/draft_info.json` 多时间线草稿的快照与恢复（restore 输出单时间线根布局） |
| 模板/ASS/OTIO/媒体维护 | 2026-11-18 离线端到端：`template save/apply`、ASS 解析/计划/导出、OTIO 2 轨导出/导入、silence/scene/retake 解析、`relink/replace-media/prune`；新增 7 项回归测试，全套 228 项通过；未做剪映真实导出抽帧 |
| 失败事务 | `patch` 中途校验失败不留半成品副本；构建失败不替换旧草稿；JSON 写入失败清理临时文件 |

## 未验证 / 不承诺

| 能力 | 状态 | 建议 |
|---|---|---|
| 转场 | 2026-11-14 实测：结构能写入且导出成功，但本机 `Cache/effect` 只缓存了 258 个 AmazingFeature 视觉特效，无转场资源；用错类型 id 渲染 ok 却被静默忽略（抽帧与无转场一致） | 当成实验能力；先确认本机已缓存对应转场资源包，失败就删掉 transition |
| 云端字幕翻译/划重点/去水词 | 剪映客户端能力，受账号/权益限制；本技能只做本地 ASR、SRT 与文本后处理，不冒充已支持 | 需要时在剪映客户端完成，或先提供译好的 SRT 再入轨 |
| 贴纸/花字/气泡 | `jy.py resource list --cached` 在本机这些 panel 均为 0；结构已接线但无真实资源可验收 | 先在剪映里正常下载；会员资源仍受 entitlement 限制 |
| 转场/滤镜/贴纸 `resource_ref` | `resource_ref` 只解析 id/md5/完整标题；本机没有这些免费缓存包，真实导出未验证 | 先用 `resource resolve` 取 id/完整标题；下载/缓存再验收，会员/商业资源不绕过 |
| 单片段视频 effect | 2026-11-16 手工 `materials.effects[type=effect]` + extra refs 应用“灼烧出现”，抽帧无变化；独立 effect 轨也不显示 | 需要真实参考草稿或正确 material type；不要当可用 |
| 文字模板（text_template） | 免费 `text` 面板资源多为文字动画，已用“变色输入”在 `animations` 真实导出；“变色输入”当 `caption_template` 用只显示白字；真正的 `text_template` 槽位未验收 | 文字动画走 `animations`；模板槽位需要真实模板资源和槽位映射 |
| Canvas 模板 | 免费 canvas 包下载后只有 `config.json` + `id.json`（约 1KB），实际内容在 `origin_file_uri`，需二次下载；本技能无法离线还原模板 | 需要客户端/云端二次下载；不要当可用 |
| 美颜/美体 | `beauty` 已接线 `materials.effects[type=figure]`，只在有美妆项时追加 `makeup-root`，支持 `skin/shape/makeup/body`；2026-11-18 11.8 UI 读回 `磨皮=100` / `美白=100`，界面原生导出与 plain 同草稿对照：磨皮人脸 `avg_abs_rgb=1.215`、边缘能量 `-6.2%`，美白皮肤 `RGB +7.1/+8.8/+9.2`；native bridge `draftPath` 导出仍与 plain 帧 hash 相同，`figure_algorithm` 为空；`shape/makeup` 409 entitlement | 结构可写、UI 可出片；`jy.py render` 不会应用 `figure`，要美颜成片必须在剪映界面导出；不要承诺 bridge 导出已生效 |
| 调节包（adjust_collection） | 2026-11-16 用 `resource_ref:"新调色小项"` 写 effect 轨并真实导出，2.0s 抽帧与原片几乎一致；参数语义/生效条件未确认 | 不当已支持；需要正确参数或参考帧后再验收 |
| 原生导出参数契约 | draftPath 桥接只接受固定字段；追加 options/exportOptions/videoExportOptions/outputs 均 409 `film_export_invalid_request`。`format` 支持 mp4/mov/gif/mp3/wav/aac/flac/aiff/ogg；分辨率/帧率来自草稿画布；官方 agent 工具的视频 outputs 也只有 format/fps/resolution | 音频格式先确保草稿有音轨；改 `canvas_config` 控制画面；视频码率不在该入口支持范围 |
| 滤镜 | 写了 filter 轨 + `materials.effects[type=filter]`；同转场，本机无对应缓存资源，错类型 id 被静默忽略 | 同上；需要本机已缓存资源包 |
| 画面特效 / 智能抠像 / 绿幕 | 独立 effect 轨、`matting.path`、`materials.chromas` 均已接线；effect/sticker 段已补标准段键；效果包/逐帧蒙版目录必须已缓存，像素未抽帧；绿幕 2026-11-18 构建的草稿在 UI 打开即蓝底红块，抠像面板读回“色度抠图”勾选、关键色绿色、强度 20，界面原生导出角点 `(0,0,254)`、中心 `(253,0,0)`；native bridge 仍不应用，成片走界面导出；技能不内置 GUI 自动化，界面导出是外部步骤 | 可试；未缓存或未生效不要承诺；绿幕要出片必须走剪映界面导出 |
| 贴纸 | 已接线独立 sticker 轨，段结构按标准视觉段补齐；2026-11-15 真机取 `7675620818189077810` 包构建成功，但 render 返回 409 `film_export_entitlement_denied`，未出片；另取 `7202575978646737469` 包 render 成功，但抽帧未见贴纸（证据已移出仓库） | 需要先用客户端确认贴纸免费/已授权且确实可见再承诺；未缓存或权益拒绝不要承诺 |
| 文字模板 / 花字 / 气泡 / 发光 | `text_templates`、`text_effect`、`text_bubble`、`text_glow` 已接线；`text_effect` 必须引用真实 `flower`，2026-11-18 包 `7127669365423508767` 已取得真机像素差（`YAVG=4.1713`/`YMAX=209`），且带自定义字色/描边/阴影的 712 帧与默认 712 帧差 `0/0`，确认花字会重置文字样式；718/735 仍 409；优先级 `text_template` > `text_bubble` > `text_effect`；`text_glow` 已按 `capcut-mate` 实证改为 `type=bloom` + `bloom_params`，但本机外发光/轮廓光均 409，尚无像素证据；官方选择协议没有 `text_shape`，气泡在 11.8 走 `text_template`；本机 `bubble` 缓存 0。文字动画已单独在 `material_animations` 真机验收 | 花字可试但必须用正确 panel 的真实包并确认账号可导出；气泡/发光不要承诺；未缓存不要承诺 |
| 基础调色 / HSL | 官方 XML 字段与范围已核对；native `picture_adjust` 触发路径未确认。plan 里的 `adjust` 会被显式拒绝；2026-11-16 手工写 `materials.effects[type=adjust]` + `adjust_params`，另试 `brightness/contrast` 类型 + extra refs，抽帧均与基线一致；`materials.hsl` 首测也未见像素变化 | 不要承诺；需要调色请用剪映客户端 |
| 色轮 | 2026-11-15 真机写 `primary_color_wheels(gamma red=0.5)` 导出抽帧与无调色帧一致，11.8 未观察到像素变化（证据已移出仓库） | 不要承诺；需要调色请用剪映客户端 |
| 声道 | `materials.sound_channel_mappings[].audio_channel_mapping` 已真机验证：左only 源 `0` 左 -11.0dB/右静音，`1` 左右均 -11.0dB，`2` 双声道静音；`is_config_open` 必须为 true（证据已移出仓库） | 0 保持原声道；1 左声道复制到双声道；2 右声道复制到双声道（复制的是源右声道；左-only 源右声道本身静音，故实测双声道静音，勿误读为“右声道有声音”） |
| 音效 / 变声 | 免费“萝莉”VC 资源真机：补齐 `sub_type=0`、`path`、参数索引后，440Hz 源输出 740Hz（9 半音）；证据已移出仓库 | 其他资源仍需逐个听感验收；不要按资源名一概承诺 |
| 背景填充 | `background_fill` 写 `materials.canvases` + refs，只对第 0 条视觉轨生效；2026-11-18 真机导出纯色填充角落 `(0,0,254)`，渐变图模糊填充角落 `(242,0,9)`/边缘 `(101,0,152)`，确认不是黑底 | 只对最底层视觉轨承诺；非底层会 warning，不要静默当生效 |
| 混合模式 | `mix_mode` 写 `materials.effects[type=mix_mode]` + refs；2026-11-18 11.8 UI 预览/UI 原生导出为品红，native bridge `draftPath` 导出仍纯红 | 需要混合成片请在剪映界面导出；`render` 回执会 warning，不要承诺 bridge 导出已生效 |
| EBU R128 响度 | `jy.py loudness` 用 ffmpeg `loudnorm` 按片段测量并写 volume；4 秒正弦测得 `-33.75 LUFS`，`--max-gain-db 6 --apply` 后剪映原生导出实测 `-27.86 LUFS`（计划 `-27.75`，差 0.11 dB） | `--apply` 必须给 `--target` 和 `--out`，只写副本；目标不可达时按 `max_gain_db` 截断并如实回执 |
| native 逃生舱 | 可写 `segment` / `material` / 已存在 `materials` 桶；禁止改 `id` / `material_id` / `local_material_id` / `extra_material_refs` / `render_index` / `track_render_index`，显式素材 id 不许重复；字段语义仍不校验 | 自带真实结构并回读 + 真实导出验收；不要把“写进去了”当已支持 |
| 曲线变速 | 已接线 `materials.speeds[].curve_speed`；2026-11-18 真机导出：3 秒曲线段白块 1s `0.203` / 2s `0.547`，线性对照 `0.172` / `0.328`，确认按曲线加速；target/source 时长仍按线性计算 | 可承诺曲线像素；不要把材料里的 `speed` 当成时间轴已自动换算 |
| 视频倒放 | 2026-11-15 真实导出抽帧：`segment.reverse=true` 被 11.8 忽略，时间码未倒放；技能写入时会给出 warning | 不要承诺倒放；需要倒放用外部 ffmpeg 生成反向素材，或剪映客户端 |
| 智能抠像 | 已接线 `matting.path`；构建时要求目录已存在，但逐帧蒙版仍需剪映生成；`capability_probe` 的 `requires` 只声明 `python` | 可试；目录不存在直接 `VALIDATION`；不要把“目录存在”当成抠像已生效 |
| 关键帧 position_x/rotation 通道 | scale/position_y/opacity/volume 已实测；position_x、rotation 结构已写但未单独抽帧确认 | 可试，导出后必须抽帧确认 |
| 多时间线布局导出 | `resolve_draft_info` 能读，bridge 只接受根 `draft_info.json` | 多时间线草稿请在剪映里导出 |
| 加密草稿 | 不支持读写 | 只能回剪映客户端 |
| 导出码率参数 | native draftPath 导出对视频码率字段全部拒绝（409 invalid_request）；官方 agent 工具 schema 的视频 outputs 没有 bitrate，只有音频输出支持 192/256/320 kbps | 视频码率走剪映客户端导出，或本技能导出后用 ffmpeg 转码；不要承诺 native 码率参数 |
| `render` 对草稿的回写 | 剪映可能在导出时更新 `draft_info.json`、`draft_meta_info.json`、`draft_content.json`、`attachment_editing.json` 或 `draft.extra`；本技能先备份并记录 before/after SHA，回写后自动落一版 `editor-rewrite` | 看 `draft_mutated` / `draft_files_changed` / `draft_version_after`；成片回执挂在导出前版本，回写内容另成一版 |
| 剪映 GUI 打开/保存后的加密或迁移 | 未实测 | 交付后让用户在剪映里打开确认；保存后结构可能变 |
| 官方 `validate-patch` 的 artifact | 结构未知 | 不要用；本技能不依赖官方 patch 校验 |
| 版本 diff | 比较草稿结构、片段字段与主/附加材质指纹（含动画、字幕模板、高亮、资源路径），不做像素或听感 diff | 改稿后仍要分别 render 两版抽帧/听音频；不要把 `changes` 为空当成画面没变 |
| 版本体积 | 每版保存全量 `draft_info.json` + plan/ops 副本，历史会随草稿变大 | 需要干净草稿时，明确说明可删 `.jianying-versions`，删后不能 restore |
| 历史 smoke 回执 | 早期一次性验证产物（仓库外归档），其草稿 `exports` 未挂该文件；新 `render` 会正常挂回执 | 不要把旧 smoke 当版本链验收；以 `draft-version-v2` 的 v002 为准 |
| 字体授权 | 未校验 | 只用用户已授权的字体；会员字体可能导致 entitlement 拒绝 |

## 登记与导出字段口径

- `build --publish` / `register` / `publish` 默认是 **dry-run**：不复制目录、不写索引，只返回将要复制/登记的条目。
- 只有显式 `--publish-apply`（`build`）或 `--apply`（`register`/`publish`）才真正复制进草稿根并写索引；`--publish-apply` 未带 `--publish` 时报 `VALIDATION`。
- 复制先落到草稿根下 `.tmp-<uuid>/`，回写/校验完成后原子 `os.replace` 到目标；失败清理临时目录，不留半成品。
- 索引条目为 **38 键**（以 `index.py` 的 `ENTRY_TEMPLATE` 为准）；写索引前先备份到 `.jianying-backups/`，备份名带毫秒 + uuid 短后缀，同一秒两次操作不互相覆盖。
- dry-run 必须有稳定 `draft_id`；缺 id 时拒绝登记并返回 `DRAFT_ID_MISSING`，不再生成临时 uuid。真实写入前会备份索引并校验 `draft_meta_info.json`。
- `render` 回执里的 `duration_ms` 与别名 `export_elapsed_ms` 都是**本次导出的墙钟耗时（毫秒）**，不是成片媒体时长；媒体时长看 `probe.duration`。
- `resource download` 回执里 `db_md5` 是资源库用于缓存目录命名的 md5，`archive_md5` 是实际下载 zip 的散列；两者不保证相等，不以下载包散列冒充资源内容校验。`cached=true` 仍只代表目录存在。
- `register` / `publish --apply` 回执的 `editor_check` 为 `closed` / `unknown`：`unknown` 表示 tasklist 不可用、无法确认剪映是否在运行；索引写入已发生，首页显示仍需重开剪映确认。
- `verified: true` 表示索引已落盘并能回读。2026-11-14 实测：写索引前退出剪映、写后重开，首页确实显示并保留该条目；但剪映**运行时**仍可能用内存索引覆盖磁盘，所以写索引前必须让用户保存并退出剪映，完成后重开确认。
- 首页按**草稿根文件夹扫描**显示草稿：即使 `all_draft_store` 为空，根下已有草稿文件夹仍会出现在首页（实测真实根索引为空时仍显示既有草稿）。因此登记成功与否看索引回读，首页是否显示看文件夹是否存在；清理测试草稿要同时恢复索引并删除其文件夹。
- 真实根清理口径：恢复写前备份的索引精确字节 + 删除本次复制的草稿文件夹 + 移除本次 `.jianying-backups/` 备份，即可精确还原；**不得**删除用户既有草稿文件夹。若历史条目带 `id_persisted`，清理前必须由用户授权。
- `probe.python.executable` 是当前运行本技能的解释器（`PYTHON` 环境变量优先，缺省当前解释器 `sys.executable`）；`probe.python.bundled` 才是剪映自带解释器，两者不要混用。

## 版本差异的处理

1. 先跑 `probe`，确认 `install.version`、`docs.status`、`bridge.version`、`bridge.capabilities`。
   `docs.status` 为 `unverified` / `unsupported` / `unknown` 时，草稿仍可构建，但交付结论必须写明未在支持窗口验证。
2. 如果 `video.export` 不存在，`render` 不可用；仍可 `build` 出草稿，让用户在剪映里导出。
3. 如果 `render` 报 `DRAFT_ENCRYPTED` / `DRAFT_INVALID` 或结构错误，先 `inspect`；不要按旧版本字段硬改。
4. 参考仓库的 11.5 白名单、jy 的 macOS 引擎都不要移植到 11.8；它们的版本约束不是本技能的约束。

## 对用户的表述

- 能交付：可编辑草稿（首选）、按明确要求导出的 mp4、结构摘要、抽帧证据。
- 不能交付：剪映 GUI 里才有的模板/特效/动画成品；不要用“支持剪映全部功能”这类说法。
- 失败时保留现场：草稿目录、`inspect` 输出、`error.code`、备份路径都告诉用户，不自动删除。
