# 排错速查

CLI 永远输出一个 JSON：先看 `ok`。`jy.py` 失败看 `error.code`、`error.message`、`error.fix`；
字幕入口 `subtitles/cli.py` 用扁平信封，失败看顶层 `code`、`detail`、`hint`（没有 `error` 嵌套）。
不要只看退出码；不要凭自然语言猜错误。

| `error.code` | 典型现象 | 处理 |
|---|---|---|
| `BRIDGE_NOT_FOUND` | `render`/`probe` 说找不到描述文件 | 剪映没开，或该版本没有开放桥接；打开剪映后重跑 `probe` |
| `BRIDGE_HEALTH_FAILED` | bridge 返回非 200 或响应不是对象 | 重启剪映后重试；仍失败说明该版本没有开放桥接 |
| `BRIDGE_UNREACHABLE` | 端口连不上 | 剪映可能刚退出/重启，端口已变；重跑 `probe` 重新读描述文件 |
| `BRIDGE_TIMEOUT` | health 或导出超时 | 确认剪映没卡住；大草稿加 `--timeout` |
| `NOT_LOGGED_IN` | 导出前读上下文没有 userId | 在剪映客户端登录账号后重试 |
| `DRAFT_ENCRYPTED` | `draft_info.json` 读不出 JSON | 剪映重存后加密；只能回剪映客户端导出，或重新用本技能生成明文草稿 |
| `DRAFT_NOT_FOUND` | 目录里没有 `draft_info.json` | 指到草稿根目录；多时间线布局用 `inspect` 确认 `info_path` |
| `DRAFT_INVALID` | `draft_info.json` 不是 JSON 对象 | 重新 build 或回剪映另存明文草稿；不要手拼结构 |
| `DRAFT_ROOT_NOT_FOUND` | 找不到包含 `root_meta_info.json` 的草稿根 | 用 `--draft-root` 指定；先确认剪映已创建过草稿 |
| `INDEX_NOT_FOUND` | 草稿根缺少 `root_meta_info.json` | 在剪映里新建并保存一条草稿；不要手写空索引 |
| `UNSAFE_PATH` | 素材/草稿是 UNC、网络路径、URL，或草稿含符号链接/junction | 先下载到本地普通目录；不要用远程素材或链接绕过 |
| `DRAFT_META_MISSING` / `DRAFT_META_INVALID` | 缺少可读的 `draft_meta_info.json`，或 `tm_duration` 非法 | 用剪映打开并保存草稿生成明文 meta；不要手写索引条目 |
| `DRAFT_META_MISMATCH` / `DRAFT_ID_MISSING` | `draft_info` 与 meta 的 draft_id 不一致，或都没有 id | 回剪映保存一次，或重新 build；不要伪造 id |
| `DRAFT_INVISIBLE` | meta 把草稿标记为不可见 | 先确认这是用户要登记的草稿；不要强行改可见性 |
| `INDEX_BUSY` | 另一个进程持有索引写锁 | 等当前登记结束；不要并发改索引 |
| `EDITOR_RUNNING` | `register`/`publish --apply` 前检测到剪映仍在运行 | 先让用户保存工作并退出剪映，再重试；不要在运行时写首页索引 |
| `INDEX_CONFLICT` | 写前发现索引被其他进程改动 | 退出剪映后重试，或先核对备份；不要覆盖 |
| `DRAFT_LAYOUT_UNSUPPORTED` | `render` 报只支持单时间线 | 草稿已迁到 `Timelines/<uuid>/`；在剪映客户端里导出 |
| `film_export_token_invalid` | bridge 临时 token 失效 | 不要复用旧 token；重新运行 `probe` 读取新描述文件 |
| `film_export_request_canceled` | 剪映取消导出 | 停止并发重试；检查剪映是否有弹窗或未完成导出 |
| `film_export_timeout` | 导出超过请求超时 | 保留现场，确认剪映是否仍在导出，再决定是否放宽 `--timeout` |
| `film_export_unsupported_timeline` | 剪映不接受当前时间线布局 | 保存为单时间线，或直接在客户端导出；不要改 `Timelines` 结构绕过 |
| `film_export_cancelled_or_timeout` | 导出被取消或等待超时 | 确认剪映是否仍在导出；不要并发重试同一草稿 |
| `film_export_panel_unavailable` | 导出面板/注入执行不可用 | 退出重开剪映；仍失败就改客户端导出，不要改官方文件 |
| `film_export_entitlement_denied` | 409，草稿以前能导出、克隆后突然不能 | 文字素材 `type` 必须是 `text`；`subtitle` 会触发 AI 字幕授权校验。其次去掉会员字体/转场/特效 |
| `film_export_dependency_missing` | 转场/滤镜/特效导出失败 | 素材包没缓存；先在剪映里点开让它下载，或从计划里删掉 |
| `film_export_invalid_state` | 剪映正在播放/导出/切草稿 | 等剪映空闲，或关掉预览播放再重试 |
| `film_export_draft_manager_unavailable` | 草稿管理器不可用 | 重开剪映；仍失败就改客户端导出 |
| `film_export_draft_unreadable` | 剪映读不了草稿 | 确认是单时间线明文草稿；在剪映里重新打开并保存 |
| `film_export_entitlement_bypass_forbidden` | 桥接拒绝绕过会员校验 | 不要改 DLL/token；删掉会员素材或改客户端导出 |
| `film_export_format_unavailable` | 请求的导出格式不可用 | 用已实测的 `mp4/mov/gif/mp3/wav/aac/flac/aiff/ogg`；音频格式要求草稿有音轨 |
| `film_export_frame_canvas_unavailable` | 帧画布不可用 | 检查草稿画布配置；改回常规横/竖屏画布 |
| `film_export_invalid_request` | 桥接请求体非法 | 检查草稿路径/输出路径/格式；不要手拼请求 |
| `film_export_no_audio` | 草稿声明音频但没有可用流 | 检查音频素材 `has_audio`；删掉无效音频段 |
| `film_export_options_unavailable` | 导出选项不可用 | 不要依赖 `video.export.options` 参数；用草稿画布 |
| `film_export_runtime_unavailable` | 导出运行时不可用 | 重启剪映；仍失败就改客户端导出 |
| `EXPORT_EMPTY_OUTPUT` | 回执成功但文件 0 字节 | 换输出目录（权限/磁盘）；检查草稿是否能正常打开 |
| `EXPORT_RECEIPT_MISMATCH` | 回执路径和请求不一致 | 不要用相对路径；输出路径用绝对路径 |
| `OUTPUT_EXISTS` | build 目标已有草稿，或 render/frame/verify 的输出文件、`version restore --out` 目标已存在 | 换新路径；build 目标确认是本技能生成的草稿、成片/抽帧经用户同意后才加 `--force`；restore 不覆盖，换目录 |
| `VERSION_NOT_FOUND` | 草稿没有 `.jianying-versions`，或指定了不存在的版本号 | 导入的旧草稿先 `version snapshot <draft> --label init`；版本号用 `version list` 里的 `vNNN` |
| `VERSION_CORRUPTED` | `versions.json` 或某个版本快照不是合法 JSON/文件缺失 | 保留现场，不要手改历史；从源草稿重建历史，旧版不能 restore |
| `VERSION_WRITE_FAILED` | 写版本清单/标记文件失败（权限、磁盘、路径） | 看 `details.path/reason`；换可写草稿目录，失败时 build/patch 已中止，不留半成品 |
| `OUTPUT_NOT_EMPTY` | build 目标目录非空且没有 `.jianying-skill.json` | 换空目录；不要删除不认识的用户文件 |
| `OUTPUT_WRITE_FAILED` | 写草稿/索引/标记文件或创建目录失败（权限、路径、磁盘） | 看 `details`（草稿写失败给 `path`/`reason`，索引写失败给 `index`）；换可写目录，确认路径所在盘存在 |
| `COPY_FAILED` | 复制草稿目录到草稿根失败 | 检查源草稿完整、目标所在盘可写；失败时临时目录已自动清理，不留半成品 |
| `PROBE_FAILED` | ffprobe 找不到、超时，或输出不是合法 JSON | 确认 ffprobe 路径、素材没坏、进程没超时 |
| `LOUDNESS_TIMEOUT` | ffmpeg `loudnorm` 测量超时 | 缩短片段或加 `--timeout`；确认素材可正常解码 |
| `LOUDNESS_MEASURE_FAILED` | ffmpeg 返回了但解析不出 loudnorm JSON | 换 ffmpeg 构建；确认音频有有效采样；不要伪造测量值 |
| `DRAFT_ENCRYPTED` | 响度测量读到的草稿不是明文 JSON | 回剪映重存为明文，或重新用本技能生成草稿 |
| `INDEX_VERIFY_FAILED` | 索引写完回读不到登记条目 | 从 `.jianying-backups` 恢复备份；不要并发写索引 |
| `BAD_ARGS` | CLI 参数缺项、类型或范围不合法 | 运行 `--help`；不要把非法值当成成功尝试 |
| `INTERRUPTED` | 用户中断 | 检查未完成的输出或备份，再重试 |
| `INTERNAL` | 未预期异常的入口兜底 | 看 `details.type` 与复现输入；兜底后 stdout 仍是结构化 JSON，不吐 traceback，应反馈 |
| `VALIDATION` | 计划字段不合法 | 看 `details.field`/原值；时间/素材区间/颜色/opacity/scale/resource_id 是常见来源；删空所有片段会带 `reason: "empty_draft"` |
| `FILE_NOT_FOUND` | 计划/补丁文件不存在 | 检查路径；计划文件要 UTF-8 |
| `JSON_INVALID` | 计划/补丁 JSON 语法错 | 看 `details.line/column`；PowerShell 里别内联长 JSON |
| `MEDIA_NOT_FOUND` | 素材路径不存在 | 改计划里的 `path`；相对路径以计划文件目录为基准 |
| `MEDIA_UNREADABLE` | ffprobe 读不了素材 | 确认文件没坏、格式受支持（mp4/mov/png/jpg/mp3/wav/m4a/aac） |
| `MEDIA_TIMEOUT` | 静音/镜头检测的 ffmpeg 超时 | 缩短素材或加 `--timeout`；确认 ffmpeg 没有卡在解码 |
| `MEDIA_FAILED` | 静音/镜头检测的 ffmpeg 返回非零 | 看 `details.stderr`；确认媒体有音视频流，换可用 ffmpeg |
| `FFPROBE_MISSING` / `FFMPEG_MISSING` | 找不到 ffprobe/ffmpeg | 用剪映安装目录自带的 `ffprobe.exe`/`ffmpeg.exe`；`probe` 会给出路径 |
| `FRAME_FAILED` | 抽帧失败 | 时间点要在成片时长内；换 `--at` |
| `INSTALL_NOT_FOUND` | 找不到剪映安装目录 | 确认装了剪映专业版；默认在 `%LOCALAPPDATA%\JianyingPro\Apps` |
| `CONTEXT_FAILED` | 读不到剪映登录上下文 | 在剪映里登录后重试；不要伪造 token |
| `INDEX_INVALID` | `root_meta_info.json` 不是合法 JSON 或缺 `all_draft_store` | 先备份，再从剪映正常退出让它重建索引；不要手写坏 JSON |
| `INDEX_UNSUPPORTED` | `draft_ids` 不是整数 | 同上，不要猜写 |
| `ASSET_MISSING` | 技能 `assets/*.json` 缺失 | 技能包不完整，重新拷贝整个目录 |
| `model-missing` / `missing-dep` | 本地 ASR 模型或 Python 依赖缺失 | 先在剪映用一次「识别字幕」下载模型；再 `pip install numpy onnxruntime kaldi-native-fbank` |
| `decode-failed` / `decode-timeout` / `empty-audio` | ffmpeg 抽音频失败、超时或没有采样点 | 确认素材有音轨；换可用 ffmpeg；修复/缩短音频 |
| `no-speech` / `no-cues` / `local-asr-failed` | 本地 ASR 没识别出 token、音频能量/识别密度过低、单条 cue 跨度异常，或无法组成 cue | 确认音频有连续语音；纯音乐/静音不要硬出字幕；检查模型是否完整；保留输入与回执复现 |
| `LOCAL_ASR_TIMEOUT` / `LOCAL_ASR_FAILED` | 一键字幕流水线里的 ASR 超时，或子进程没有返回合法 JSON | 缩短音频/加长超时；直接跑 `srt.from-local-asr` 看具体错误；已有 SRT 可用 `--srt` 跳过 ASR |
| `TRANSCODE_FAILED` | 本机 ffmpeg 转码失败或输出为空 | 看 `details.stderr`；确认输入有音视频流、输出目录可写，换一个 ffmpeg 或码率 |
| `RESOURCE_DB_MISSING` / `RESOURCE_DB_UNREADABLE` / `RESOURCE_NOT_FOUND` | 资源库 `rp.db` 缺失/读不了，或查不到资源 | 先打开剪映素材面板生成缓存；或用 `JY_RESOURCE_DB` 指定；`resource list` 看可用资源 |
| `RESOURCE_AMBIGUOUS` | 标题匹配到多条资源（含短标题、`%`/`_` 通配） | 改用资源 id/md5 或完整标题；先跑 `resource resolve` 看 `candidates`，不要猜 |
| `RESOURCE_MD5_MISSING` | 资源记录没有 md5，无法定位剪映缓存目录 | 换一个资源；这类记录常见于数字人等特殊面板，不能保证剪映能加载 |
| `RESOURCE_PATH_INVALID` | 资源 id/md5 含非法字符，或缓存路径解析后越出 Cache 根 | 资源库记录异常；不要手改 `rp.db`，换资源或让剪映重建资源缓存 |
| `RESOURCE_GATED` | 会员/商业资源 | 在剪映客户端正常获取；技能不绕过权益 |
| `RESOURCE_NOT_CACHED` | `resource_ref` 指向的资源还没下载 | 先 `resource download <ref> --apply`，或 build 加 `--fetch-resources` |
| `RESOURCE_URL_MISSING` / `RESOURCE_URL_EXPIRED` | 资源没有下载地址，或签名 URL 过期 | 在剪映里打开一次素材面板刷新资源；或换一个资源 |
| `UNSAFE_URL` | 下载地址不是 https（含 302 跳转到 http），默认拒绝 | 换 https 源；确认是本机可信来源时才加 `--allow-http`，别为单个镜像全局放宽 |
| `RESOURCE_DOWNLOAD_FAILED` | HTTP 403/网络失败 | 看 `details.status`；刷新资源、换网络或换资源，不要重复轰炸 |
| `PACKAGE_INVALID` | 资源包不是 zip、含越界/非法条目名、下载/条目/解压体积超限、缺 `config.json`，或解压实际写入超过上限 | 不要手改包；换资源或重新下载 |

## 画面类

| 现象 | 原因 | 处理 |
|---|---|---|
| 文字在画面顶部，不在底部 | `y` 正值向上 | 底部字幕用 `y: -0.7` 左右 |
| 图片叠加完全不出现 | 副视频轨没有 `flag: 2`，或 `render_index` 还是 0 | `build` 已自动处理；手改草稿时两处都要设 |
| 文字不显示 | 素材/轨道写成了 `subtitle`，或 segment 没挂到文字轨 | 改成 `text`；`inspect` 看 `tracks` 和 `texts` |
| 文字是方块/乱码 | `content` 不是合法字符串化 JSON，或 `range` 长度不对 | 用 `set_text` 改，不要手拼 `content` |
| 画面全黑 | 素材路径不存在/被移动，或视频没有视频流 | `inspect` 看 `missing_media`；`verify` 看 `video_codec` |
| 图片主轨只显示一瞬间 | 图片 segment 的 `duration` 没写或为 0 | 明确给 `duration` |
| 关键帧不动 | 通道名写错，或时间超出片段时长 | 用 `scale`/`position_y`/`opacity` 等白名单；`inspect` 只看摘要，关键帧要看 JSON |

## 音频类

| 现象 | 原因 | 处理 |
|---|---|---|
| 完全没有声音 | 音频轨没建，或 `volume: 0` | `inspect` 看 `audio` 轨；`set_volume` 设回 1 |
| BGM 太响/太轻 | `volume` 是线性增益 | 0.1–0.4 试；不要用 dB 直接填 |
| 导出报 `film_export_no_audio` | 草稿声明了音频但没有可用流 | 检查音频素材 `has_audio`；必要时删掉音频段 |

## 字幕工具

| 错误或现象 | 原因 | 处理 |
|---|---|---|
| `file-not-found` | `--text` 要传**文本文件路径**，不是文本内容 | 先把逐句文案写成 UTF-8 文件 |
| `srt-dropped-blocks` | 有块缺时间码或正文为空 | 修复或删除这些块；本技能不静默丢数据 |
| `count-mismatch` | `srt.from-segments` 文本条数与音频文件数不一致 | 用 `--by-line` 让一行对应一个音频，或重新切分文本 |
| `no-segments` | 逐句音频目录里没有支持的音频文件 | 放入 wav/mp3/m4a 等音频后重试 |
| `ambiguous-segments` | 音频排序键冲突，无法确定与文本的对应顺序 | 重命名使文件主干唯一，或移走重复文件 |
| `bad-encoding` | 文本/SRT 无法按 UTF-8/GB18030 解码 | 用记事本另存为 UTF-8 后重试 |
| `bad-font` / `bad-size` / `bad-crf` | 字体名或字号/CRF 超出允许范围 | 字体用族名；size 6–200、crf 0–51 |
| `unsafe-path` | 字幕链接受了 UNC、网络盘或 URL | 先下载到本地普通目录；不要用远程路径 |
| `srt-out-of-range` | 部分字幕终点超过视频时长 | 调整时间码；确需保留末尾不可见部分才加 `--allow-out-of-range` |
| `srt-no-visible-cues` | 全部字幕都在视频时长之外 | 重新生成时间码，`--allow-out-of-range` 不能救这种情况 |
| `srt-invalid` | `srt.check` 判重叠、时长异常、行宽超限或正文只有标点；`burn` 只拒硬非法（负/零/非有限），**不拒重叠 cue** | 看 `data.issues`，先修再导入；烧录重叠字幕可不改时间码 |
| `srt-check` | 本地 ASR 生成的 cue 未通过时长/行宽校验 | 调大 `--max-chars`/`--max-dur` 后重试；失败不会写 SRT/JSON，不能靠 tidy 挽救 |
| `ffmpeg-missing` | 找不到可执行的 ffmpeg | 安装 ffmpeg 或设置 `JY_FFMPEG`，再重试 |
| `ffmpeg-missing-capability` | 当前 ffmpeg 缺 libass（drawtext 不能替代 `subtitles=`） | 装外部 full 构建并设 `JY_FFMPEG`；剪映自带 ffmpeg 不能烧字幕 |
| `interrupted` | 用户中断了字幕命令 | 检查未完成的输出/临时字幕，再重试 |
| `bad-args` / `bad-gap` / `bad-total` / `bad-timecode` / `bad-max-chars` / `bad-max-dur` / `bad-min-dur` / `bad-audio-duration` / `unknown-verb` | 字幕工具的参数、时间码、总时长或子命令不合法 | 运行 `cli.py <verb> --help`；按报错改值，不要绕过校验 |
| `bad-out-path` / `dir-not-found` / `draft-root-missing` / `out-exists` / `out-is-input` / `permission-denied` / `io-error` | 输出路径、目录、权限或输入输出同路径 | 换可写目录和独立输出名；不要覆盖输入或用户草稿 |
| `empty-text` / `split-too-long` / `srt-unparsable` / `total-too-small` | 正文为空、单行过长、SRT 无法解析，或总时长平摊不足 1ms | 补正文、放宽行宽/延长总时长；坏块修好再重试 |
| `ffprobe-missing` / `probe-failed` / `no-duration` / `no-input` / `partial-failure` | ffprobe 缺失、探测失败、无时长或输入不完整 | 用剪映自带 ffprobe；检查素材路径与容器；批量探测时先修失败项 |
| `ffmpeg-failed` / `ffmpeg-start-failed` / `ffmpeg-timeout` / `output-empty` | ffmpeg 启动失败、执行失败、超时，或产物为空 | 看 stderr 首行；确认外部 ffmpeg 带 libass/libx264，必要时换输出目录 |
| `temp-srt-failed` / `internal-error` | 临时字幕创建失败，或未预期异常 | 检查临时目录权限；保留输入并反馈复现命令 |
| `FILM_EXPORT_FAILED` | bridge 导出返回了未分类失败 | 保留 `status`/`native_error`，重跑 `probe` 后再试；不要并发导出 |
| 烧录后字幕是方块 | 字体族名错误，libass 静默回退 | 用 `Microsoft YaHei` / `Source Han Sans SC`，抽帧确认 |
| 输出已存在 | 字幕工具不覆盖文件 | 换 `--out`；不要删除原文件来腾路径 |

## 首页登记

| 现象 | 原因 | 处理 |
|---|---|---|
| `publish --apply` 后剪映首页看不到 | 剪映正在运行，内存里的索引覆盖了磁盘；或条目路径不是草稿根下的目录 | 先让用户保存工作并退出剪映，再 `publish --apply`，然后重开剪映 |
| 跑了 `--publish` 但首页没变 | `--publish` 只是 dry-run，不写盘；要真正改首页必须再加 `--publish-apply`（build）或 `--apply`（register/publish） | 确认命令里带了 apply 标志；`--publish-apply` 单独用会报 `VALIDATION` |
| 首页出现两份同名草稿 | 同一路径被登记两次，或复制出了 `-2` 目录 | `register` 会按路径/draft_id 去重；复制前确认 `--name` |
| 登记后草稿打不开 | 复制时只拷了 `draft_info.json`，漏了素材或封面 | 用 `publish` 整目录复制，不要手工搬单个文件 |
| 索引写坏 | 并发写 / 非 UTF-8 | 技能写前备份、写临时文件再 `os.replace`；仍失败就从 `.jianying-backups` 恢复 |

## 环境与版本

| 现象 | 原因 | 处理 |
|---|---|---|
| `jy` 报 `descriptor pid is not alive` | jy 的 Windows 进程检测有 bug | 不要用 jy 的 render；本技能直接走桥接 |
| `headless-windows` 拒绝安装 | 只支持 11.5 的 DLL 哈希 | 不要改白名单；本技能不依赖它 |
| `lyra-cli` 报 unauthorized host process | 只允许剪映宿主调用 | 不要重试；用桥接 |
| `jianying-agent-cli` 报 `PERMISSION_DENIED` | 缺 `JIANYING_AGENT_RUNTIME_TOKEN` | 外部 shell 没有宿主令牌；不要伪造，用桥接 |
| `probe` 的 bridge 为空 | 剪映 11.8 的桥接只在主进程启动后写描述文件 | 启动剪映并等 3–5 秒；仍没有就确认版本 |

## 不要做的事

- 不要为了绕过 `film_export_entitlement_denied` 改账号、伪造 token、改 DLL 哈希或补丁官方程序。
- 不要把 `%TEMP%\infinite-canvas-native-bridge.json` 的 token、`/custom-agent/context` 的 cookie
  写进草稿、日志、Git 或用户交付物。
- 不要在剪映运行时手改 `root_meta_info.json` 后指望它立刻生效；先退出应用再登记。
- 不要对加密草稿做 `patch --in-place`；先确认 `inspect` 的 `encrypted` 为 false。
