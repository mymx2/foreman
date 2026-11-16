# 变更记录

技能自身的版本历史。版本号对应 `SKILL.md` frontmatter 的 `version` 与
`references/version.json` 的 `skill_version`，两者不一致时 `check_docs.py` 会报错。
剪映本体版本的变化不看这里，看 [版本升级与迁移](upgrading.md) 与 [历史归档](history/README.md)。

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
  `references/evidence/2026-11-17-tidy-mixed/`；旧版 9 处英文词被切断、5 条单字伪影未截，
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
  归档在 `references/evidence/2026-11-16-caption-highlight/`。
- 审查修复：空 md5 资源不再假成功；资源标题歧义/会员资源不再静默命中；zip 条目异常、解压体积和
  覆盖回滚补齐；ASR 对静音/纯音乐返回 `no-speech`，`--model-dir` 错误不再回退；`add_subtitles`
  改为样式白名单并支持 `caption_template`；版本 diff 增加材质指纹，导出回写自动落 `editor-rewrite`，
  快照记录外部资源并在 restore 时报告缺失/变更；`add_subtitles` 的 SRT 随版本归档。
- 真机复核：2026-11-16 审查后重新 `build → render`，320×180/2.02s 成片导出成功，回执挂到 v001；
  归档在 `references/evidence/2026-11-16-render-after-review/`。
- 导出参数：实测 native draftPath 入口追加 `options`/`exportOptions`/`videoExportOptions`/`outputs`
  全部 409 `film_export_invalid_request`；官方 agent 工具 schema 的视频输出没有 bitrate。
  文档从“未验证”改为“该入口不支持视频自定义码率”，需要时走客户端或 ffmpeg 转码。
- 导出格式：native bridge 实测支持 mp4/mov/gif/mp3/wav/aac/flac/aiff/ogg，CLI `--format`
  已全部开放；音频格式要求草稿实际有音轨。
- 声道：定位到生效字段 `materials.sound_channel_mappings[].audio_channel_mapping`；
  左-only 源实测 0 保持原声道、1 左复制双声道、2 右复制双声道，状态从 unverified 升为
  implemented，证据在 `references/evidence/2026-11-16-channel-mapping/`。
- 变声：`audio_effect` 补 `path`/`production_path`/`sub_type` 和带索引的
  `audio_adjust_params`；免费“萝莉”VC 真实导出 440Hz→740Hz，状态改为 conditional，
  证据在 `references/evidence/2026-11-16-audio-effect/`。
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
  回执与抽帧归档在 `references/evidence/2026-11-16-burn-check/`。

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
- 证据瘦身：`references/evidence/2026-11-15-real-probes/` 下的 6 个 mp4 移到技能包外的
  `.agents/skills.collected/_evidence/jianying/2026-11-15-real-probes/`，包内只留
  plan/completion/png。
- 真机验证：2026-11-16 用 320×180 临时草稿完成 `build → render → verify`，确认
  `draft_mutated` / `draft_files_changed` 与安装指纹在真实导出中可用（剪映回写
  `draft_content.json`）；回执与抽帧归档在 `references/evidence/2026-11-16-render-check/`。
