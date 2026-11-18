# 变更记录

技能自身的版本历史。版本号对应 `SKILL.md` frontmatter 的 `version` 与
`references/version.json` 的 `skill_version`，两者不一致时 `check_docs.py` 会报错。
剪映本体版本的变化不看这里，看 [版本升级与迁移](upgrading.md) 与 [历史归档](history/README.md)。

## 1.5.6 — 2026-11-19

- 修 ASS 覆盖标签前缀误配：`\bord3` / `\blur1` / `\be1` 曾被 `startswith("b")` 吞成加粗、
  `\iclip(...)` 被吞成斜体且不进 `unsupported_tags`；开关标签改为“标签名本身必须是 `b`/`i`/`u`
  且其后为空或纯数字”，`\bord` / `\blur` / `\be` / `\iclip` / `\s` / `\k` 如实登记为未支持，
  `\b1` / `\i0` / `\u` / `\r` 行为不变（各补正向断言）。
- 修 `prune` 引用口径：`_referenced_ids` 补认 `local_material_id`（与 `jy.py` render 扫描器、
  `draft._referenced_material_ids` 统一），并补回归测试钉住效果材质不被误删。
- 修 `beautify` 别名误告警：build 读 `beauty` 或 `beautify`，但 `beautify` 不在 `_KNOWN_SEGMENT_KEYS`，
  会先提示“技能不会读取这些键”再实际生效；已补入白名单。
- 修链接穿透：新增 `media.is_plain_file` / `is_plain_dir`（lstat 不跟随，且检查祖先目录），
  `relink` 目标、`probe_media`、草稿 `missing_media`、体积统计、首页索引、版本快照输入全部改走它；
  `relink --to` 拼出的路径也先过 `local_path`，不会对 UNC 目标先做 lstat；`--dir` 本身拒绝链接目录；
  读取媒体/版本文件时用不跟随链接且禁止删除共享的句柄保持到读取结束，缩小检查与使用之间的替换窗口；
  `st_reparse_tag` 只拒绝 junction/符号链接，不误伤 OneDrive 云占位。`relink` 前缀匹配同时改为
  分隔符归一 + 大小写不敏感，并防 `C:\old` 命中 `C:\older`。
- 修资源下载 scheme：默认只允许 `https://`，仅有 http 地址时报 `UNSAFE_URL`（不写死 md5 比对，
  `db_md5`/`archive_md5` 语义本就不同），确需 http 时显式 `--allow-http`；重定向改为逐跳校验
  scheme 与本机/内网 IP，读响应前再复核最终 `geturl()`，混合 https+http 时在结果里报
  `skipped_insecure_url_count` 而不是静默丢弃。
- 修 `extra_material_refs` 为 dict 时的引用口径：旧代码按 key 迭代或忽略，现统一取 value，
  数字 id 也归一成字符串（`prune`、`remove`、render 扫描器一致）。
- `inspect` 的素材缺失检查补到 images/stickers 桶，不再只看 videos/audios；贴纸资源包目录不再误报缺失。
- `build` / `auto-subtitles` 的 `--fetch-resources` 透传 `--allow-http`，与 `resource download` 一致。
- 文档：`--allow-http` 进 `SKILL.md` 命令表，`UNSAFE_URL` 进 `troubleshooting.md` 错误码表。
- 测试：`test_skill.py` 新增 ASS 标签（含 `\i1`/`\u1`/`\r`）、prune 口径、beautify 白名单、
  junction 拒绝（文件与祖先目录）、资源 https 与重定向、静音区间数学、loudness 边界状态、
  relink 前缀分支与兄弟目录防误配等回归用例。

## 1.5.5 — 2026-11-18

- 修整批未推送改动的提交阻断：`scripts/jy.py` 顶层依赖的 7 个 `jylib` 模块与 2 份 references 文档此前是 untracked，已纳入提交范围；`check_skill.py` 必需清单补齐，避免干净克隆后 `ModuleNotFoundError` / 文档断链。
- 修 `scripts/jy.py` 扫描器边界：`materials`/`tracks` 为 `null` 或非预期类型时安全返回，不抛未捕获 `AttributeError`；效果引用并入 `material_id` / `local_material_id`。
- 修 `scripts/jylib/draft.py` beauty 全 0 值规格误报：无 `figure` 产出时不再写“已写入”，改为明确的“未写入 figure 材质”。
- 文档口径修复：声道 `2` 补“右复制、左-only 源实测双声道静音”；曲线变速在 `03-effects`、`plan-schema`、`SKILL.md` 三处滞后清除；脱敏 `verification-gaps` 的个人绝对路径与 `limits` 的开发机路径；`06-delivery` 证据交付措辞；`verification-gaps` 计数改为 12 项。
- 版本号 1.5.5；`check_skill` / `check_docs` / `test_skill` 全量复查。本批同时把 1.2.6–1.5.5 期间的历史脚本与文档改动首次随包入库；changelog 条目连续，不构成版本链断裂。

## 1.5.4 — 2026-11-18

- 修复 review 的 2 个 major：`scripts/jylib/draft.py` 的 beauty 警告补上“native bridge 不应用、成片走界面导出”；`scripts/jy.py` 的 render 条件扫描从只认 `mix_mode` 扩到 `figure` / `materials.chromas`，含美颜或绿幕的既有草稿不再静默 `ok: true`。
- 补充 build 侧 warning：`mix_mode` 说明品红是界面生效的正常结果、bridge 纯红表示未应用；`hsl` 对齐 probe 口径“真机无像素变化，不能当已支持”。
- 文档修复：六域/路由/入口表补 `chroma`/`beauty`/`mix_mode` 条件标记；合成验收明确这三项的帧必须取自剪映界面导出；`06-delivery` 的 render 节补边界；曲线变速三处滞后描述更新；花字/气泡拆述；`upstream` 的 UI 自动化措辞对齐“不内置 GUI 自动化”。
- 新增防复发测试 `test_render_reports_beauty_chroma_conditional_warnings`，并加强 beauty build warning 断言；`check_skill` / `check_docs` / `test_skill` 全量复查。

## 1.5.3 — 2026-11-18

- 绿幕 `chroma` 从 `unverified` 升为 `conditional`：用技能构建 `materials.chromas` 的草稿 `real-chroma-built`，11.8 界面打开即预览蓝底红块；`抠像` 面板读回“色度抠图”勾选、关键色绿色、强度 20；界面原生导出 1s 角点 `(0,0,254)`、中心 `(253,0,0)`。native bridge `draftPath` 仍不应用 `chromas`，`jy.py render` 仍出绿幕，成片必须走剪映界面导出。
- 推翻旧结论“取色器无法通过 UIA 自动取色”：真正吸管按钮中心是 `(1575,283)`，旧坐标 `(1606,265)` 落在按钮外；点击后预览即变蓝，导出成功。文档统一改为“UI 可取色、可导出，bridge 不应用”。
- 边界：技能只交付“正确草稿”，不内置 GUI 自动化；绿幕/美颜/混合模式的界面导出是外部步骤，不把 UIA 点击作为技能运行链。
- `capabilities`、`limits`、`verification-gaps`、`plan-schema`、`playbooks/02-compositing.md`、`SKILL.md`、`capability_probe.py` 同步更新；版本号 1.5.3。

## 1.5.2 — 2026-11-18

- 美颜从“结构实验”升为 `conditional`：修 `beauty.py` 只在真正有美妆项时追加 `makeup-root`，单磨皮草稿不再导致剪映退出；`real-smooth2` 打开后右侧 `美颜美体` 面板读回 `磨皮=100`，界面原生导出与同草稿 plain 对照，人脸 `avg_abs_rgb=1.215`、`changed_ratio=0.569`、边缘能量 `-6.2%`；`real-whiten` 读回 `美白=100`，导出皮肤 `RGB +7.09/+8.83/+9.15`。native bridge `draftPath` 仍与 plain 帧 hash 相同，`figure_algorithm` 为空；`shape`/`makeup` 仍 409 entitlement，因此 `render` 不承诺美颜，成片必须走剪映界面导出。
- 复测 `chroma` 时补了 UI 路径：11.8 `抠像` 面板能勾选“色度抠图”，但当时用了错误坐标 `(1606,265)`，实际没点中吸管，自动取色未完成，预览/导出仍绿；关闭草稿后 UI 只写加密 `draft_content.json`，`draft_info.json` 不更新，所以也读不回结构。`visual.chroma` 当时保持 `unverified`；1.5.3 已用正确坐标 `(1575,283)` 复现成功并升为 `conditional`。
- 能力矩阵、`limits`、`verification-gaps`、`plan-schema`、`SKILL.md`、`capability_probe.py` 与 `playbooks/02-compositing.md` 同步更新；版本号 1.5.2。

## 1.5.1 — 2026-11-18

- 修复 `publish --apply` / 副本复制遇到空 `##_draftpath_placeholder_...` 长路径目录时报 `COPY_FAILED`：新增 `media.copy_tree`，只按实际文件建目录，并对 Windows 长路径使用扩展前缀；`index`、`draft`、`template`、`maintenance` 的复制入口统一改用该函数。新增 `test_copy_tree_skips_empty_placeholder_dirs` 回归，全套 `229 tests OK, skipped=1`。
- 用真实素材复验 `detect silence` / `detect scenes`：3 秒音/静音/音素材检出 `1.099909–1.900068s`（`--pad 0.1`）；4 秒红蓝硬切素材切点精确 `2.0s`。证据归档在仓库外。
- 证据不再进仓库：`_evidence/jianying`、`skills/jianying/evidence`、`references/evidence` 全部移到仓库外证据库（仓库同级 `rbz-one-evidence/`），证据路径不落在仓库目录内，天然不入库，不靠 ignore 规则；文档里的文件链接改为文字结论，避免中间产物越积越多。

## 1.5.0 — 2026-11-18

- 新增片段模板：`template save/apply` 从真实草稿提取任意片段、主素材和全部 `extra_material_refs`，应用时重映射所有 id；文字模板可 `--text` 覆盖文案。
- 新增 ASS/SSA 交换：`ass import` 解析事件时间、基础样式与 `\c/\fs/\b/\i/\u/\r` 内联标签，转成 build 计划；`ass export` 从文字轨导出 ASS；未支持标签写 `unsupported_tags`，不静默改写。
- 新增 OpenTimelineIO：`otio export` 输出 Timeline/Stack/Track/Clip/Gap，文字/贴纸/特效轨在 `skipped` 里列明；`otio import` 支持 Timeline/Stack/Track/数组并生成 build 计划。
- 新增媒体分析：`detect silence`（ffmpeg silencedetect）、`detect scenes`（select(scene)+showinfo）、`detect retakes`（本地文本 LCS）、`detect duplicates`；只分析不改草稿。
- 新增草稿维护：`relink`（前缀映射或同名搜索，歧义报告）、`replace-media`（保留时间线/特效，可 `--retime`）、`prune`（删无引用材质）；默认写副本，`--in-place` 才回写并备份。
- 新增美颜结构：`beauty` / `beautify` 生成 `materials.effects[type=figure]` + `makeup-root`，覆盖 `skin/shape/makeup/body`；`jy.py beauty list` 列出可用项。11.8 bridge 导出 `smooth/whitening` 与 plain 帧差 0，UI 能识别滑杆但 `figure_algorithm` 为空，`shape/makeup` 409 entitlement，因此能力保持 `unverified`，只当结构实验。
- 新增 `InterchangeTests` 7 项回归；全套 `228 tests OK, skipped=1`。能力矩阵、依赖表、`plan-schema`、`limits`、`verification-gaps`、`SKILL.md` 与 playbooks 同步到 1.5.0。

## 1.4.0 — 2026-11-18

- 新增 `background_fill`（`blur`/`color`）：写 `materials.canvases` + `extra_material_refs`，只对第 0 条视觉轨生效；真机 11.8 导出纯色填充角落 `(0,0,254)`，渐变图模糊填充角落 `(242,0,9)`、边缘 `(101,0,152)`，确认不是默认黑底。
- 新增 `mix_mode`（内置 10 种混合模式或自定义 `effect_id`/`resource_id`）：写 `materials.effects[type=mix_mode]` + refs。11.8 界面预览和 UI 原生导出为品红，但 native bridge `draftPath` 导出仍为纯红；能力保持 `conditional`，`render` 对含 mix_mode 的草稿写 warning，不把 bridge 导出当已生效。
- 新增 `jy.py loudness`：ffmpeg `loudnorm` 按片段测 EBU R128（LUFS/true peak/LRA），按目标 LUFS 计算并写 volume；`--apply` 强制 `--target` + `--out`，只写副本。4 秒 440Hz/-12dB 测试音测得 `-33.75 LUFS`，`--max-gain-db 6 --apply` 后剪映原生导出实测 `-27.86 LUFS`（计划 `-27.75`，差 0.11 dB）；`--target -28 --apply` 导出实测 `-28.06 LUFS`（计划 `-28.00`，差 0.06 dB）。
- `inspect` 新增 `video_extras`，读取 `background_fill` 与 `mix_mode` 的材质引用；`_KNOWN_SEGMENT_KEYS` 接受新字段与别名 `background_filling` / `blend_mode`。
- 文档同步：能力矩阵、`capability_probe.py`、`plan-schema.md`、`limits.md`、`SKILL.md` 与版本号升到 1.4.0；证据归档在仓库外。

## 1.3.0 — 2026-11-18

- `inspect` 新增顶层 `text_effects`：遍历文字片段的 `extra_material_refs`，从
  `materials.effects` 提取 `text_effect` / `text_shape` / `text_glow`，输出
  `start/duration/text/type/effect_id/resource_id/path`；已在 11.8 真机草稿上读到
  DeepGlow 的 `resource_id/effect_id`，用于从手工草稿提取真实花字/气泡资源。
- 资源权益判定修复两处安全缺口：
  1. 旧逻辑只读 `extra.is_business`，6472 条 `effect` 记录中有 778 条数据库
     `is_business=1` 而 `extra` 缺字段，会被误判为可下载；现在数据库字段与
     `extra` 任一为真即商务。
  2. 模板主资源免费但依赖会员/商务字体或花字时，原逻辑只查主记录，下载到一半后
     导出才 409；现在读取 `depend_resource_list`，依赖命中会员/商务即整体
     `RESOURCE_GATED`。真实例：免费字幕模板“口播-小火苗动画红色描边花字”
     依赖商务字体“优设字由棒棒体”，已被拦截。
- 官方 11.8 协议复核：`text_effect` 必须绑定 `flower`；`text_glow_*` 是文字宿主属性；
  11.8 选择协议没有 `text_shape`，气泡走 `text_template`。据此把 `text.bubble`
  明确标记为旧草稿兼容路径，`text_glow` 警告补充宿主属性口径。
- 真机像素复核：DeepGlow 分别写 `text_glow` 与 `text_effect`，与无特效基线
  `YAVG=0/YMAX=0`；免费字幕模板“粉黑”依赖 flower 但缺包，导出成功却回落成
  普通白字。两项都写进 `verification-gaps.md`，不把“结构写入/导出成功”当效果生效。
- 新增回归：`text_effects` 提取、`text_effect` 与 `text_glow` 互斥、
  数据库商务标记、模板依赖权益拦截；`ResourceCatalogTests` 13 项通过。
- 修掉 `examples/15-text-effects.py` 的旧断言（仍读 `materials.filters`），
  改为 `materials.effects`；`run_examples.py` 21 项全部通过。
  全套 `test_skill.py` 214 项通过（skipped=1），`check_skill.py` 334 项、`check_docs.py` findings 为空。

## 1.3.1 — 2026-11-18

- `text.effect` 从 `unverified` 升为 `conditional`：从 `jianying-editor-skill` 取真实
  `flower` 包 `7127669365423508767`，构建并真机导出；与同文案无花字帧差
  `YAVG=4.1713`/`YMAX=209`，证据归档在仓库外。
  `7187739440347958589`、`7351316503771368713` 仍 409 entitlement，不能当免费资源。
- 按 `capcut-mate` 的剪映实证修正 `text_glow`：`materials.effects[type="bloom"]`、
  `panel_id="text_glow"`、`value=0.0`、`effect_id`/`resource_id` 分开、`bloom_params`
  写颜色/方向/范围/强度、文字 `check_flag |= 64`；不再写 `effectStyle`，也不再和
  `text_effect` 互斥。本机外发光/轮廓光均 409，仍无像素证据，能力不升级。
- 气泡结构补充 `effect_id`/`resource_id` 必须分开（`capcut-mate` 实证
  `716434` / `6821385652727190024`），但本机无可用气泡包，保持 `unverified`。
- `inspect.text_effects` 现在也读 `type="bloom"`，并输出 `panel_id` / `bloom_params`；
  `text_effect` 与 `text_glow` 回归改为“可叠加”断言。

## 1.3.2 — 2026-11-18

- 按 `capcut-mate` 的剪映行为补齐文字特效优先级：`text_template` > `text_bubble` >
  `text_effect`。模板存在时忽略气泡/花字；无模板时气泡存在则忽略花字；不再把
  三者的 `extra_material_refs` / `effectStyle` 叠成未定义结果。
- 花字接管外观时把文字颜色/描边/阴影重置为默认值（白字、无描边、无阴影），
  与 `capcut-mate` 的 `add_captions` 一致；背景和 `text_glow` 不重置。
  真机验证：同一 712 花字计划显式要求红字、绿描边、蓝阴影，导出帧与默认 712 帧
  差 `YAVG=0`/`YMAX=0`；证据归档 `flower712_reset.mp4` / `flower712_reset_150.png`。
- `text_bubble.effect_id` 改为必填；只给 `resource_id` 时不再猜成同值。
- 新增回归：气泡优先于花字、模板优先于气泡/花字、花字重置文字样式；同步
  `SKILL.md`、`capabilities.md`、`plan-schema.md`、playbook、limits、verification-gaps。

## 1.2.9 — 2026-11-18

- 修正花字/气泡/发光的材质桶：`text_effect`、`text_shape`、`text_glow` 从
  `materials.filters` 改写到 `materials.effects`。依据 `pyJianYingDraft 0.3.1`
  与 `jianying-tool 0.4.1` 两个独立实现：二者都把文字特效放在 `effects`；
  `pyJianYingDraft` 的 `draft_content_template.json` 甚至没有 `filters` 桶。
  这解释了此前花字/气泡即使资源类型正确也可能不渲染的结构性原因；像素验收仍待真实资源。
- 回归测试改为断言 `materials.effects`，并显式检查不再产生 `filters` 键。

## 1.2.8 — 2026-11-18

- 复核 GitHub/PyPI 上的剪映草稿项目：pyJianYingDraft、capcut-cli、jianying-tool、
  JianYingAPI MCP、capcut-mate，写进 `references/upstream.md` 的「GitHub 项目复核」，
  按「可借鉴 / 不照搬」分开。
- 按上游字段在 11.8 复测两项：pyJianYingDraft 的最小 `chromas` 结构走 native bridge 仍不抠绿；
  jianying-tool 的 `common_keyframes` 亮度调节也无像素变化。结论记入
  `verification-gaps.md` 与证据 README，避免把「结构支持」当成渲染生效。
  （1.5.3 已修正：同一 `chromas` 结构在 11.8 界面打开即生效，旧结论只对 native bridge 成立。）
- 可借鉴清单：模板模式提取花字/气泡元信息、`common_keyframes` 属性表、
  `videoeditor.dll` 原生编解码思路、`lint`/`diff` 的写入前后校验。

## 1.2.7 — 2026-11-18

- 真机导出验证 4 项 `unverified`：曲线变速、倒放、绿幕、HSL 放进同一个 15 秒草稿，
  用 11.8 原生 bridge 导出后按帧测量。
- `speed.curve` 升为 `implemented`：曲线 1→3 的 3 秒段，白块 1s 0.203 / 2s 0.547，
  线性对照 0.172 / 0.328，确认按曲线加速；`target/source` 时长仍按线性计算。
- `visual.reverse`、`visual.chroma`、`adjust.hsl` 当时保持 `unverified`：
  倒放补 `reverse_path`、绿幕补 `segment.enable_chroma=true`、HSL 带 `enable_hsl`
  均无像素变化，11.8 native bridge 不执行这些字段。（1.5.3 复测：绿幕结构在 UI 打开即生效，
  升为 `conditional`，但 bridge 仍不应用。）
- `text.effect` / `text.bubble` 仍无法验收：本机 `flower2` / `bubble` 缓存为 0。
- 新增真机证据（计划、导出片、关键帧、测量脚本与复算说明），已移出仓库归档。

## 1.2.6 — 2026-11-18

- 本地 ASR 打通剪映自己下发的资产：`asr-punc.onnx` 断句（`--punctuate` 优先模型，
  缺失/加载失败回落启发式并写 `punc-fallback`）、`asr-itn-fst.fst` 数字规范化
  （`--itn`，需 `kaldifst`）、`asr-model-classifier.onnx` 质量分写回执
  （`quality`，分数未标定、只做相对参考，不做拦截）。
- 切块从「8–28 秒窗口 + 切静音中点」改成 VAD 分段：RMS 150ms 平滑、阈值 `p20*1.5`、
  段间停顿 ≤0.6 秒才合并、块长读 `strategy.json`；修掉块内长静音被 CIF 吞给前一个
  token（实测「到」4.0 秒 → 0.36 秒），并让分条优先断在标点。
- 新增 `references/official-host.md`：hubcli 55 份契约、MotionGraph SDK、
  `host_only` 边界；新增 `references/verification-gaps.md`：12 项未验证/条件能力的
  现有证据、阻塞点与解锁条件。
- 能力矩阵新增 `subtitle.itn`、`official.hubcli.canvas`、`official.hubcli.media`、
  `official.motiongraph`，并与 `capability_probe.py` 的 `CAPABILITIES` 同步。
- 测试：新增 5 个回归（标点类别/回落、VAD 切块、ITN tag 渲染、质量分描述），
  全套 210 项通过（skipped=1）。

## 1.2.5 — 2026-11-17

- 新增只读升级体检 `scripts/upgrade_check.py`：对比安装版本窗口与能力矩阵，
  支持 `--save` / `--baseline` 留存与比对基线并输出迁移 checklist；
  不访问外网（只查本机回环 bridge health）、不启动剪映、不自替换技能包，`--save` 才写文件。
  能力对比使用 `code_status`（代码声明），bridge/缓存/ASR 等运行时状态只记录、不参与漂移；
  基线 `skill_version` 不一致会提示重新留基线。退出码 0=体检通过（窗口内；给 `--baseline` 时无漂移），
  10=窗口外/未对齐/漂移/探测失败，2=体检或保存无法完成。
  `--baseline` 读取同样走本地路径校验；`--save` 只允许覆盖本技能保存的基线文件，
  能力探测失败或矩阵为空时拒绝保存。
- 文档：`maintenance.md` / `upgrading.md` 补充升级前后的基线留存、字段与路径约定，
  纠正“exit 10 是红灯”的误读（更新 version.json 前为预期）；修正“没有上游发布源”的过时说法——
  技能已由本仓分发，但仍不在技能内实现自替换更新器。
- 测试：新增 14 个升级体检回归（窗口内、窗口外、安装版本漂移、能力漂移、运行时状态不参与漂移、
  探测失败与漂移区分、基线存取与类型校验、UNC 读取、拒绝覆盖非基线文件、保存失败信封、
  空矩阵拒绝、基线技能版本不一致）。

## 1.2.4 — 2026-11-17

- 事务与并发：`auto-subtitles` 的 `--force` 改为先生成隐藏临时文件、成功后 `os.replace` 发布，
  ASR 失败不再删除既有 SRT/JSON；JSON/SRT 发布失败时保留临时 SRT 并在错误里给出路径，
  SRT 发布失败会回滚旧 JSON；`version restore` 先在暂存目录完整生成（含版本链）再整体发布，
  失败（含 Ctrl+C）不留半成品；版本锁的 `owner.json` 改为原子写，释放只删 token 匹配的自有锁，
  陈旧锁先原子 rename 到 tombstone 再复核 token（被搬错时放回），不再无条件夺锁。
- 路径校验：`audio_effect.path`、`matting.path`、`text_template.path`、`add_subtitles.srt`
  统一接入本地路径校验（拒绝 UNC/网络盘/URL）；新增拒绝映射网络盘（GetDriveTypeW）
  与盘符相对路径（如 `C:foo`）；计划 extras 的相对路径按计划文件目录解析；
  资源缓存目录的 id/md5 增加字符白名单，并断言解析后的目标仍在 Cache 根内
  （新错误码 `RESOURCE_PATH_INVALID`）。
- 资源下载：下载按实际字节限流并记录归档 md5（`archive_md5`）；回执同时给出 `db_md5`
  （缓存目录名的 md5，不冒充下载包校验）；解压按实际写入字节计数，不再只信 zip 自报 `file_size`。
- 计划校验：音频片段在 `build` 和 `patch set_speed` 中显式拒绝 `speed`/`curve_speed`
  （原为静默忽略）；`scale` 关键帧的向量值按 X/Y 通道拆分，值数量不符报 `VALIDATION`；
  `_KNOWN_SEGMENT_KEYS` 补齐 `green_screen`/`caption_duration_info`/`line_max_width`，
  消除“已接线却提示未识别”的误告警。
- 字幕：本地 ASR 生成的 cue 未通过时长/行宽校验时如实失败（`srt-check`），
  阈值与 `srt.check`/`srt.tidy` 的默认 6s 对齐，失败提示改为“调参重试、不会写盘”；
  文档补充该错误码。
- 登记/环境：`tasklist` 不可用或异常时，结果标注 `editor_check: unknown` 而不是静默放行，
  且复制后登记不再被复制前检查覆盖；多个 bridge 描述文件并存时优先 pid 存活的最新一份。
- 测试：新增 23 个回归测试（临时文件事务与半提交、锁属主/陈旧锁、恢复原子性、
  路径/映射盘/下载校验、关键帧拆分、ASR 校验失败、音频变速拒绝、编辑守卫未知状态等），
  离线测试总数 191。

## 1.2.3 — 2026-11-17

- 字幕：`srt.tidy` 超宽行拆分改为词安全——中英混排没有空格可借，硬切点落在英文词内部时
  回退到词起点，不再产出 ex/cel、p/hotoshop 这类残词字幕；词起点太靠左或英文词本身超过
  `--max-chars` 时仍硬切兜底。拆出各段按可见字数比例分配原 cue 时长（原来等分）。
- 字幕：`srt.tidy` 新增单字/双字超时长伪影截短（`--max-dur`，默认 6s 与 check 同阈值）：
  Paraformer 块边界把静音吞进单字时间戳（单字挂 6–9s）时截到 1s 显示，文字不动；
  回执加 `short_artifacts_capped`。本地 ASR → tidy → check 全绿链路由此闭合；
  多字超时长 cue 仍由 check 报，不静默处理。
- 测试：`test_skill.py` 新增 7 个回归（混排词安全、纯英文空格行为不回归、超长英文词硬切兜底、
  单字截短、tidy 后 check 全绿、比例时间、bad-max-dur 信封）。
- 证据：36 分钟会议真实 ASR SRT（568 cue）新旧 tidy 对照与四项质量断言归档在
  证据已移出仓库；旧版 9 处英文词被切断、5 条单字伪影未截，
  新版四项断言全过。
- 审查修复（3 路独立 review）：词内撇号/连字符不再被当词边界（don't 残词回归）；`--max-chars 1`
  不再丢行首标点（守卫下限 `max(1, max_chars//2)`）；截短只压不抬（`--max-dur` <1s 时不再拉长）；
  截短优先于 `--min-dur` 保底；超宽行拆出的单字/双字段同样截短。补 9 个回归测试并加强弱断言。
- 证据更正：旧版残词实为 9 处（断言脚本截断显示遮了第 9 个）；比例拆点与 token 级实测最大差
  1.246s，README 原「≤0.3s」声明已更正；benchmark metadata 的 run 数/模型/ delta 约定占位与
  假计数已更正。

## 1.2.2 — 2026-11-16

- 字幕：新增 `subtitles/cli.py srt.from-local-asr`，用剪映已下载的本地 Paraformer ONNX 模型
  识别音视频并输出 SRT/逐 token 时间；不登录、不联网；长音频静音切块；60s 与 36 分钟实测通过。
- 字幕：本地 ASR 新增 `--remove-fillers` / `--punctuate`，规则删除口头禅、按停顿加标点；
  这是本地启发式，不冒充剪映 AI 去水词/标点。
- 字幕：`patch` 新增 `add_subtitles` op，把 SRT 写进可编辑 text 轨；每次 patch 自动成下一版，
  之后可用 `set_text`/`set_style` 改 cue，`version diff` 看变化，`render` 后验收。
- 字幕模板：新增 `caption_template`/`caption_info`，写入文字材质的 `caption_template_info`；
  免费“白字黑边”真实导出，cue 文本绑定成功；`text_template` 仍用于文字模板。
- 动画：`animations` 现在同时支持文字和视频/图片；免费“变色输入”文字动画与免费“翻入”
  视频动画均真实导出，分别写 `material_animations` 和 `material_animations[type=video_animation]`。
- 关键词高亮：新增 `highlight`，按词匹配追加 `content.styles` range；2026-11-16
  “AI工具分享 AI时代”真实导出两处 AI 黄色粗体。本地规则，不冒充剪映 AI 划重点。
- 包装：新增 `jy.py packaging`，由主视频、标题、SRT 字幕、BGM、字体、字幕模板和标题动画
  生成本地 `jianying-plan/v1`；2026-11-16 用 60s 视频 + 20 cue 真实导出 2s/30s 抽帧验证。
  这是本地 preset，不是剪映云端智能包装。
- 资源：新增 `jy.py resource list/stats/resolve`，只读 `rp.db` 与本机缓存包，列出字体、字幕模板、
  贴纸、花字、特效等资源的 id/title/panel/cached；明确 `cached` 不代表权益。
- 资源下载：新增 `jy.py resource download <id|标题> --apply`，默认 dry-run；只下免费非商业资源，
  会员/商业/过期 URL 明确失败；免费字体已用 `font_path` 真实导出验证；免费字幕模板“白字黑边”
  用文字材质 `caption_template_info` + `caption_info` 绑定 cue 文本，真实导出成功；
  文字模板槽位仍未验收。
- 资源引用：计划里的资源 spec 支持 `resource_ref`（标题/ID/md5），`build` 解析为
  `resource_id`/`path`/`name`/`effect_id`，字体映射为 `font_path`；`--fetch-resources`
  自动下载未缓存的免费资源。字体 `毛笔行楷` 已真实导出验证；文字光效 `DeepGlow`
  能解析并导出，但暗底抽帧无可见光效，像素未验收。
- 声道：补写 `segment.sound_channel_mapping`；2026-11-16 左only 源 + `channel=0` 导出
  左 -5.6dB、右 -91dB，未按官方 left 模式复制到双声道，保持 unverified。
- 资源边界：免费 canvas 包只有 descriptor（`origin_file_uri` 需二次下载）；缓存的美颜/美体包多为
  business；`materials.effects[type=adjust]` 实验抽帧无变化。均未当可用。
- 能力矩阵：新增 `subtitle.asr.local`、`subtitle.apply`、`resource.catalog`；补本地 ASR 与资源目录
  的边界，不把云端翻译/划重点/去水词算成本地能力。
- 测试：新增 `ResourceCatalogTests`（临时 SQLite + 缓存目录），覆盖缓存过滤、VIP 标记与 resolve。
- 真机验证：60s 草稿 v001→v002（20 cue）→v003（改字/改色），两次真实导出抽帧确认字幕与样式；
  36 分钟音频 7761 token / 513 cue / 145 块 / 219.7s。
- 证据：字幕模板、毛笔行楷、关键词高亮、文字/视频动画、包装抽帧、60s/36min ASR 与去水词 SRT
  归档在仓库外。
- 审查修复：空 md5 资源不再假成功；资源标题歧义/会员资源不再静默命中；zip 条目异常、解压体积和
  覆盖回滚补齐；ASR 对静音/纯音乐返回 `no-speech`，`--model-dir` 错误不再回退；`add_subtitles`
  改为样式白名单并支持 `caption_template`；版本 diff 增加材质指纹，导出回写自动落 `editor-rewrite`，
  快照记录外部资源并在 restore 时报告缺失/变更；`add_subtitles` 的 SRT 随版本归档。
- 真机复核：2026-11-16 审查后重新 `build → render`，320×180/2.02s 成片导出成功，回执挂到 v001；
  归档在仓库外。
- 导出参数：实测 native draftPath 入口追加 `options`/`exportOptions`/`videoExportOptions`/`outputs`
  全部 409 `film_export_invalid_request`；官方 agent 工具 schema 的视频输出没有 bitrate。
  文档从“未验证”改为“该入口不支持视频自定义码率”，需要时走客户端或 ffmpeg 转码。
- 导出格式：native bridge 实测支持 mp4/mov/gif/mp3/wav/aac/flac/aiff/ogg，CLI `--format`
  已全部开放；音频格式要求草稿实际有音轨。
- 声道：定位到生效字段 `materials.sound_channel_mappings[].audio_channel_mapping`；
  左-only 源实测 0 保持原声道、1 左复制双声道、2 右复制双声道，状态从 unverified 升为
  implemented，证据已移出仓库。
- 变声：`audio_effect` 补 `path`/`production_path`/`sub_type` 和带索引的
  `audio_adjust_params`；免费“萝莉”VC 真实导出 440Hz→740Hz，状态改为 conditional，
  证据已移出仓库。
- 一键字幕：新增 `jy.py auto-subtitles`，把本地 ASR/SRT、包装计划、可编辑草稿串成一条命令；
  已有 SRT 可用 `--srt` 跳过 ASR。
- 转码：新增 `jy.py transcode`，用本机 ffmpeg 转到目标视频/音频码率并 ffprobe 回读；
  明确是后处理，不是剪映原生码率参数。
- 资源预检：新增 `jy.py resource verify`，检查免费/已缓存/期望面板，避免把
  `tool_text_glow` 当 `flower` 之类的资源类型混用。

## 1.2.1 — 2026-11-16

- 字幕：`resolve_ffmpeg` 自动发现 `imageio-ffmpeg` 包内的 ffmpeg；`jy.py probe` 新增
  `subtitle_ffmpeg`（`subtitle_burn_in` / `libass` / `libx264`），不用再手动找 full 构建。
- 证据：2026-11-16 用 imageio-ffmpeg 7.1 烧录 30s 中文 SRT，`drift_ok:true`、6/6 cue 完整；
  回执与抽帧归档在仓库外。

## 1.2.0 — 2026-11-16

- 版本链：多时间线快照与恢复，`version` 子命令校验路径，版本链可以按草稿分支递进；快照读取兼容
  BOM，`project.json` 损坏时回退时间线扫描。
- render：检测剪映回写的多个文件，文件被删除或迁移也计入回写，不再只认第一个产物。
- 文字：变速参数被拒绝时给出明确错误，`trim` 语义统一；文字判定只看主素材。
- 画布：纯图片草稿缺视频轨时给 1920×1080 warning，不再静默采用默认画布。
- 字幕：SRT 切分不依赖空行，序号与正文纯数字分开处理，不吞正文。
- 草稿读取：跳过 UTF-8 BOM，避免首行 key 解析失败。
- `remove`：清理引用时同步修掉悬空的素材引用。
- 文档：证据与结论对账（`limits.md` / `capabilities.md`），补 `upgrading.md`、
  `history/`、`changelog.md`。
- `check_docs.py`：新增版本基线断言（baseline 对齐 `supported.min`、behavior 对齐
  `supported.max`、`skill_version` 对齐 `SKILL.md`、`history_max` 上限），并扩展自检。
- 证据瘦身：6 个 mp4 已移出技能包，统一归档在仓库外；包内不再保留 plan/completion/png。
- 真机验证：2026-11-16 用 320×180 临时草稿完成 `build → render → verify`，确认
  `draft_mutated` / `draft_files_changed` 与安装指纹在真实导出中可用（剪映回写
  `draft_content.json`）；回执与抽帧归档在仓库外。
