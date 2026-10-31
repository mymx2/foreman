---
name: photocraft
description: 驱动 PhotoCraft（开源、离线、兼容 Photoshop 的图像编辑器）完成可复现的修图与 PSD 自动化：通过 photocraft-cli、批处理与动作、serve 会话、MCP 或桌面控制通道执行注册表命令，覆盖调色、抠图换底、文字与形状、滤镜修复、模板批量出图、格式转换与切图导出、打印与打印 PDF、相机 RAW 显影、只读格式导入，以及 PSD 规范化、栅格排版和分层稿交付。当用户要用 PhotoCraft 或 photocraft-cli 处理图片或 PSD、批量处理一个目录、打印/出 PDF、显影 RAW、或把 PhotoCraft 接给 agent 与 MCP 客户端时使用。不适用于生成式 AI 绘图、RAW 图库管理（单张 RAW 显影是支持的）、网页 CSS 或 Figma 设计稿，以及没有安装 PhotoCraft 的环境。
when_to_use: photocraft, photocraft-cli, PSD 自动化, 批量修图, 图片批处理, 抠图换背景, 电商白底图, 加水印, 调色与 LUT, 格式转换, 打印, 打印 PDF, 相机 RAW, RAW 显影, XCF 导入, 图层 XMP, 轮廓库, 切图导出, 多倍图, 文字居中, 栅格排版, PSD 规范化, PSD 复刻, 分层稿交付, 缺失字体, 动作与 Droplet, 模板批量出图, 截图打码, serve 会话, MCP 修图, 桌面控制通道
---

# PhotoCraft

退出码 0 不代表做对了：多数命令会把拼错的参数悄悄忽略、按默认值照跑，serve 的 `batch` 有步骤失败时顶层照样回 `ok:true`。每一步都要用返回 JSON、`info` 和预览图核对。

## Overview

**适用版本**：命令与参数按 0.14.0 复核，行为在 0.14.0 与 0.18.0 上实测过；0.18 的增量与反转项见 `references/whats-new.md`。低于 0.12 不保证——那之前的记录只覆盖少数条目。文档里标「实测 0.18，0.14 未复核」的规则，在 0.14 及更早版本上先验证再用。

PhotoCraft 的绝大多数菜单动作、工具和对话框都对应注册表里的一条命令（条数随版本变，少数桌面菜单项不在注册表里）。CLI、`serve`、MCP、桌面控制通道调用的是同一份注册表，差别在文件权限和可用的方法。本技能负责：选对入口、查准参数、在副本上执行、逐项核对产出。`examples/` 里的 Python 场景脚本在 0.14.0 上实跑通过（41 个案例：40 个通过，案例 31 需要真实窗口，默认跳过），可以照着改；PSD 工程类任务另有审计、比对、切图脚本。入口决策树与质量尺度见 `references/entrypoints.md`；打印见 `references/printing.md`；相机 RAW 见 `references/raw.md`；0.12→0.18 的变化见 `references/whats-new.md`。

## Outcome Contract

- **Outcome**：用户要的图片或文档写到指定（或新建）的输出目录，原文件不变；需要后续修改时同时交付分层母版（PSD 或 `.pcraft`）。打印任务要明确是只出 PDF 还是真的送印；RAW 任务保留 16 位母版和来源信息。
- **Done when**：每个产出都过了核对：尺寸、模式、位深、图层与要求一致（`info`），关键命令的返回值符合预期，抠图、调色、打码、排版这类视觉结果看过预览图；文字层从 `type.info` 读出的 PostScript 字面都在 `type.fonts` 已装列表里；PSD 规范化、复刻或交付任务另有审计、比对或资产清单报告。打印任务检查 PDF 页/纸张/标记和 `sent`；RAW 任务检查位深/色彩空间与 preview-fallback warning。
- **Evidence**：CLI 退出码；`run` 每行 JSON 里的 `result`；`info --compact` 断言；预览 PNG；CLI 批处理的 `N succeeded, 0 failed`、`file.automate.batch` 回复里空的 `errors`、serve `batch` 的 `result.failed == 0`；批次/manifest 记录里的 SHA256 与落盘文件一致；脚本报告（`psd_compare`、`psd_audit`、`trim_export` 的 manifest）；打印的 PDF 文件与 `file.print` 回执；RAW 的 `depth:16`/ProPhoto 与回退警告。
- **Authorization**：读用户给的文件、在新的输出目录里写产出可以直接做。以下先征得同意：覆盖原文件（`--in-place`、写回原 PSD、不带 path 的保存）、启动桌面窗口、关闭用户打开的文档或退出程序（`app.quit` 和引擎命令 `file.close` 都会直接丢弃未保存的修改，不弹提示）、`prefs.set` 或 `prefs.reset`（含 `rawDefaults.*`）、安装插件或字体、把动作重放到用户的文档上、真实送印（`file.print` 不带 `dryRun`/`output` 或 `send:true`）、写入或删除用户文档的图层 XMP、`ui.gpu.simulateLoss {destroy:true}`。

## When to Use

- 格式转换、PSD/TIFF 结构检查、导出多种交付格式；读取 XCF/DICOM/Amiga IFF 等只读格式。
- 单张或成批修图：调色、裁切缩放、抠图换底、水印、去瑕疵、打码、风格滤镜。
- 打印与打印 PDF：纸张/方向/缩放/裁切标记/出血/颜色处理，或只出 PDF 不送印。
- 相机 RAW 单张/批量显影：DNG、CR2、NEF、ARW、RW2、PEF、ORF、RAF；输出 16 位 ProPhoto 母版。
- 用模板批量出图：改文案、变量数据组、图层/画板/切片/资源导出。
- PSD 工程：规范化与复刻、栅格排版、文字排版、分层稿交付、补字体；读写图层 XMP、管理用户轮廓库、通道目标与蒙版显示（`channel.options`）。
- 让 agent 连续编辑：serve 长会话、MCP 工具、驱动桌面窗口。
- 不适用：生成式填充或 AI 绘图（PhotoCraft 没有；`select.subject` 一类是经典算法，不是学习型模型）；RAW 图库/XMP sidecar 管理（单张 RAW 显影是支持的）；网页样式与 Figma 稿评审；Web/WASM 版没有自动化入口。

**从零设计视觉方案**：本技能负责落地与处理，不负责方案设计。需要先定视觉方向、系列一致性、电商详情页叙事时，先用 `ai-visual-design` 出方案与参考图，再回来在这里做成可编辑分层稿。

## Process

1. **定位 CLI**：执行 `python <skill-dir>/scripts/find_cli.py --check`。它依次看 `PHOTOCRAFT_CLI`、`PATH`、安装目录（Windows MSI 装在 `C:\Program Files\PhotoCraft\`，不进 PATH）。完成标准：有可执行路径和 `--version` 输出；找不到就请用户提供路径，不要猜。
2. **看输入**：`photocraft-cli info <文件> --compact`。完成标准：知道尺寸、模式、位深、分辨率、有无文字层与智能对象、`warnings`（缺字体等）。
3. **查命令**：先在 `references/commands.md` 找候选 id，再执行 `python <skill-dir>/scripts/params.py --exact <id>` 取已安装版本的参数文本；不知道 id 时传关键词（如 `curves`）。完成标准：要用的每个命令都核对过参数名、范围和默认值。
4. **选入口**：按 `references/entrypoints.md` 的五问决策树（要不要窗口、要不要状态、单文件/目录、是否 MCP、是否并发/远程），再对照下方"入口选择"和"入口能力差异"确认要用的命令在该入口没有被拒。完成标准：确定用 `run`、`convert`、`batch`、`droplet`、`serve`、`mcp` 还是桌面控制通道，并知道文件权限和认证方式。
5. **执行**：在新的输出目录里工作，输入先复制进去；JSON 参数里用相对路径；能合并的步骤放进同一条 `run`；扁平交付（JPG/PNG/WebP）之外保留一份母版。完成标准：命令退出码 0，stderr 的 `warning:` 都看过。
6. **核对**：对每个产出至少做一项检查：`info` 断言尺寸/模式/图层；`document.pixel`（合成结果）或 `document.sampleColor`（可指定合成或当前层）取样；命令返回的 `files`/`count`/`bounds`；颜色要紧的（商品、品牌色）比较处理前后主体的色相和饱和度；文字层从 `type.info` 读出的 PostScript 字面都在 `type.fonts` 已装列表里；视觉相关的生成小尺寸预览并亲自看。完成标准：所有产出都有一条通过的检查，失败的已修正或如实列出。只查尺寸和背景的质检会放过偏色。批处理有失败项时按 `actions-batch.md` 的「批次交付纪律」处理。
7. **交付**：按 Output 格式汇报。

## 入口选择

| 情况 | 用 | 注意 |
|---|---|---|
| 一张图、步骤固定、CI | `photocraft-cli run <文件> --cmd <id> --params '<json>' … --out <文件>` | 每次新进程，跑完即丢；`--out` 只存活动文档 |
| 只换格式/位深 | `photocraft-cli convert <in> <out> [--quality N] [--tiff-layers]` | 输入=输出会被拒，确需覆盖加 `--in-place`；不能 resize/调色 |
| 一个文件夹顶层套同一组步骤 | `photocraft-cli batch --actions <json\|atn> --in <dir> --out <新目录>` | 不递归；无命名模板/序号；部分失败退出码 1 |
| 递归、命名模板、序号、显式路径数组 | `run --cmd file.automate.batch` | 失败进 `errors[]`，整条 `run` 仍退出 0；看 `errors` |
| 要看结果再决定下一步、多文档、长任务 | `photocraft-cli serve --automation-read-root <dir> --automation-write-root <dir>` | stdio 不需要 token；`--port` 时首帧 auth；所有连接共享一个活动文档，串行 |
| 交给 MCP 客户端当工具用 | `photocraft-cli mcp --automation-read-root <dir> --automation-write-root <dir>` | 工具数量随版本变；单行超过 1 MiB 进程退出；`ui_*` 可见但调用报错 |
| 要真实窗口：读界面、截窗口、模拟压感笔 | 独立实例 `photocraft --new-instance --control <port> --control-token-file <文件>`，再用 `scripts/control.py` 或 `photocraft-cli mcp --bridge 127.0.0.1:<port>` 驱动 | 启动前征得同意；临时 `PHOTOCRAFT_CONFIG_DIR`；用完关闭 |
| 要改用户已经打开的文档 | 只有那个实例启动时带了 `--control`（或 `PHOTOCRAFT_CONTROL_PORT`）才连得上 | 否则请用户保存后在 serve 里打开，或按用户同意重启带控制端口的实例 |
| 双击分发到同事机器 | 先 `file.automate.createDroplet`，再 `photocraft-cli droplet …` | droplet 不加载 `calledActions` 时嵌套 action 会失败，用 `createDroplet` 生成 |
| 会话内复用/交换给 Photoshop | 动作或 `.atn` | `.atn` 里无对应步骤要用 `skipUnsupported` 或 `actions.toggle` 跳过 |
| 打印/打印 PDF | CLI `run ... --cmd file.print --params '{"output":"proof.pdf","dryRun":true}'` | serve/MCP/桌面按 `file.*` 拒绝；真实送印要先征得同意 |
| 相机 RAW 显影 | CLI `run`/`convert`/`info`，serve `doc.open` | 自动化打开不弹 Camera Raw；用 `rawDefaults`；详见 `raw.md` |

完整决策树、入口矩阵、质量尺度和反例见 `references/entrypoints.md`。CLI 细节见 `references/cli.md`；serve、MCP、桌面控制通道见 `references/automation.md`；打印见 `references/printing.md`；RAW 见 `references/raw.md`；格式能保留什么见 `references/formats.md`。工作流脚本的可选依赖（Pillow、psd-tools）见 `scripts/requirements.txt`，缺了会打印说明并退出 2。

## 入口能力差异

| | CLI `run` / `batch` | `serve` / MCP | 桌面控制通道 |
|---|---|---|---|
| 文件读写 | 普通操作系统路径，不受限 | 只在 `--automation-*-root` 之下，用 `doc.*`（MCP 为 `doc_*` 工具） | 只在根目录之下，用 `app.open` / `app.save` |
| `file.export.*`、`file.generate.imageAssets`、`file.package`、`file.automate.batch`、`file.placeEmbedded` 等带路径的 `file.*` | 可用 | 按命令名拒绝（例外：`file.export.renderVideo`、`file.export.exportPreferences` 可用，只写到写根目录下） | 按命令名拒绝 |
| `file.print`、`file.printOneCopy`、`file.printers`、`file.print.page` | 可用；`output` 出 PDF，`dryRun` 不送印 | 拒（`file.*` 规则） | 拒；桌面只能人工 File › Print |
| `image.mode.*` | 可用 | 可用 | 拒绝 |
| 状态 | 每次一个进程，跑完即丢 | 常驻：文档、历史、快照、预设 | 真实窗口；所有连接共用一个活动文档 |
| 独有方法 | — | `doc.*`、`session.list`、`batch`、`methods` | `ui.*`、`app.*` |

完整的对照表（含每种拒绝的报错原文）见 `references/automation.md`；入口决策树、术语和反例见 `references/entrypoints.md`。Web/WASM 版只有人工 UI，没有 CLI/serve/MCP/控制通道；Rust `photocraft-automation` 库可嵌入宿主，但不是 agent 的默认入口。

quality 有三套刻度，别混：CLI `--quality` 和 serve/MCP `doc.save` 是 1..100（越界报错）；引擎导出命令（`file.saveACopy`、`file.automate.batch`、`file.export.*` 等）是 0..12（越界静默截断）；桌面 `app.save` 的 `quality` 是 0..12。详见 `entrypoints.md`。

## 场景路由

先找最接近的案例脚本，读它的流程和参数，再按用户的文件改。案例清单和用法在 `examples/README.md`。

| 用户要做的事 | 案例 |
|---|---|
| 看 PSD 结构、导出各种格式 | 01 |
| 不确定命令或参数 | 02 |
| 电商白底主图、批量统一尺寸 | 03 05 |
| 多平台尺寸裁图、人脸居中 | 04 |
| 印刷文件：CMYK、出血、300ppi | 06 |
| 调色、调整图层、LUT | 07 |
| 人像精修、老照片修复 | 08 09 |
| 打码脱敏、去元数据 | 10 |
| 取品牌色、导出色板 | 11 |
| 抠图合成、换背景、双重曝光 | 03 12 36 |
| 做海报、文字排版、形状 | 13 |
| 批量水印、动作集 | 14 |
| 改模板文案、批量出卡片/证书 | 15 16 |
| 剪贴路径、矢量蒙版、通道 | 17 27 |
| 风格滤镜、智能滤镜、程序化纹理 | 18 19 37 |
| 扫描件拆分、拉直、透视矫正、镜头校正 | 20 23 |
| 堆栈去路人、全景、HDR | 21 22 |
| 设计稿切图、画板、图层复合 | 24 |
| GIF 动图、序列帧 | 25 |
| 录动作、.atn、Droplet | 26 |
| 截图标注 | 28 |
| agent 多步会话、MCP、桌面窗口 | 29 30 31 |
| 文字在框里居中、改字后重排、溢出检查 | 32 |
| 按栅格摆放、对齐分布、参考线 | 33 |
| 不规范 PSD 规范化、渲染比对、分层稿交付 | 34 |
| 抠主体、裁边、多倍图与资产清单 | 35 |
| 打印、打印 PDF、裁切标记与出血 | 40 |
| 图层 XMP 读取/写入/清除、资产目录 | 41 |
| 相机 RAW 显影、ProPhoto/16 位交付 | 见 `references/raw.md` |
| XCF/DICOM/Amiga IFF 只读导入 | 见 `references/formats.md` |

## 专项工作流

| 任务 | 先读 | 脚本（执行） |
|---|---|---|
| 不规范 PSD 的规范化与复刻、分层稿交付 | `references/psd-workflow.md` | `scripts/psd_audit.py`、`scripts/psd_compare.py` |
| 栅格排版、对齐分布、参考线 | `references/layout.md` | `scripts/layout_design.py` |
| 抠图、裁边、切图、多倍图与资产导出 | `references/cutout-export.md` | `scripts/trim_export.py` |
| 修复、人像、合成、频率分离（磨皮保纹理）的工序与验收 | `references/retouch.md` | — |
| 文字框内居中、溢出、行距、竖排、路径文字 | `references/text-layout.md` | — |
| 缺字体、换字体、字体授权 | `references/fonts.md` | — |
| 动作、批处理、Droplet、变量数据组 | `references/actions-batch.md` | — |
| 选入口、并发、权限、quality 尺度 | `references/entrypoints.md` | — |
| 打印、打印 PDF、裁切标记、出血 | `references/printing.md` | — |
| 相机 RAW 显影、Camera Raw、ProPhoto/16 位 | `references/raw.md` | — |
| 0.12→0.18 的命令/格式/协议变化 | `references/whats-new.md` | — |
| 报错文本速查 | `references/troubleshooting.md` | — |

## Hard Rules

- 原文件只读：输入先复制进新的输出目录；不加 `--in-place`、不写回输入路径、不用不带 path 的保存，除非用户明确要求。
- 交付白底平图：透明文档存 PNG 得到的是 RGBA（透明区 `0,0,0,0`），不会自动变白。默认在导出后用 Pillow 做 alpha 合成铺白，不动 PSD；非要在文档里加填充层，就只在副本或导出件上做，还要按 `entrypoints.md` 的顺序（先确认有选区再 deselect、建层、`sendToBack` 压底），顺序错了会盖掉全部内容，加进母版则多出根层并改变渲染基线。
- 写 JSON 参数前查参数文本，执行后核对返回值。
- 抠图、智能选区、人脸检测、调色、修复、打码、排版的结果必须看预览图确认，再交付或继续批量。
- 文字类机密（密钥、卡号、证件号、姓名、邮箱）用实心色块覆盖；马赛克和模糊只用于人脸、头像这类"不可辨认即可"的内容。
- serve/MCP 只把本任务的目录授权为读写根目录；控制令牌只放在文件里、显式交给客户端；令牌和密钥不进命令参数、文件名、元数据或日志。不要全局导出 `PHOTOCRAFT_CONTROL_PORT`、`PHOTOCRAFT_CONTROL_TOKEN`、`PHOTOCRAFT_CONTROL_TOKEN_FILE`：桌面版每次启动都会因此打开控制端口，客户端也会读它们。
- 启动桌面窗口前征得同意，用 `--new-instance` 加临时 `PHOTOCRAFT_CONFIG_DIR`，不碰用户已打开的实例和设置；用完关闭这个实例。
- 缺字体阻止交付：先列候选、由用户确认再替换；不用 `type.replaceAllMissingFonts`（它把所有缺失字体无提示地换成 Inter）。
- 字体和素材按授权使用：免费商用不等于允许随稿再分发；占位图只用于测试。
- 变量数据组的像素替换仍是风险点：0.14 起 `image.applyDataSet` 和 `doc.exportDataSets` 的像素路径按 ambient 规则判定，旧版“读根外任意绝对路径”的缺口已关闭；但 CLI 仍是可信本地模式，不可信 CSV/数据组仍可能让导出读到进程能读的文件。只用可信数据，并在最小权限账户里跑。
- 打印只做 `dryRun` 或 `output` PDF；`file.print` 既不给 `output` 也不给 `dryRun` 就会真的送印（实测 0.18），`send:true` 同样是真的送印。两者都必须先征得同意；`file.printOneCopy` 会复用上一次打印设置，不要对用户文档直接调用。
- RAW 自动化打开不弹 Camera Raw，按 `rawDefaults` 显影；改 `rawDefaults.*` 属于 `prefs.set`，先征得同意。导出会保留 EXIF/GPS，对外分享前按需去元数据。
- 图层 XMP 是任意 XML 包，可能含 PII、授权信息或第三方数据；读取可以，写入/删除前确认目标层并保留备份，不要整包覆盖用户未看懂的内容。
- 插件只安装可信的 WebAssembly：沙箱没有文件/网络/时钟，但仍有 32 MiB 模块、512 MiB 内存、60 s 墙钟上限；PhotoCraft 不加载 `.8BF`/CEP/UXP。
- 只读格式不要假设能写回：XCF、KRA、PDN、Affinity、HEIC 等是导入；Cineon 在 0.14 可写，DDS 可写。保存前看 `info`/`session.list` 的 `path`，不要依赖“不带 path 的保存”能回写。
- `ui.gpu.simulateLoss {destroy:true}` 会真销毁窗口 GPU、保存 Recovery 后关闭应用，只用于测试；正常会话不要调用。Web/WASM 版没有 CLI/serve/MCP/控制通道，不要承诺自动化。

## Gotchas

下面这些条目多数有 `scripts/probe_gotchas.py` 探针兜底（当前 24 项，实测 0.18 全绿；0.14 的记录来自更早的批量复跑）；quality/app.save/print/RAW/XMP 等其余条目靠实跑或源码测试核对，更早的记录沿用 0.10.0。按报错文本查问题见 `references/troubleshooting.md`。

| 现象 | 做法 |
|---|---|
| `image.imageSize {"widht":600}` 退出码 0，尺寸没变 | 多数命令静默忽略未知键（`file.new` 这类少数才报错）；拼错的枚举值（如 `align:"centre"`）也静默回落到默认值。`ui.*` 是桌面方法，CLI 里根本没有，不适用此条。看返回值 |
| 引擎导出命令传 `quality:80` 和传 12 结果一样 | 多数引擎导出命令（`file.automate.batch`、`imageProcessor`、`saveACopy`、`createDroplet`、`file.export.layersToFiles` 等）的 `quality` 是 0..12，超出静默截到 12；但 `file.export.saveForWebLegacy` 是 0..100，`file.export.presets.save` 也是 1..100（越界报 `must be within 1..=100`）。CLI `--quality` 和 serve/MCP `doc.save` 是 1..100，越界直接报错；桌面 `app.save` 是 0..12 |
| 无选区时 `select.deselect` 到底会不会中止 | **入口与版本都影响**：0.12–0.14 的 CLI `run` 里它会报 `no selection` 并中止整条 run（后续步骤和 `--out` 都不执行）；0.18 改成了回 `null`、退出码 0、照跑（实测）。serve 的 `engine.execute` 两个版本都报错。所以别无条件调它：先看 `document.inspect` 的 `hasSelection`。`layer.layerMask.revealSelection` 会用掉选区 |
| 单层栅格化遇到不适用的对象，整条 `run` 失败 | `layer.rasterize.layer` 对像素层和组报 `the layer has nothing to rasterize`，后续步骤和 `--out` 都不执行；批量改用 `layer.rasterize.allLayers`（回 `{rasterized:N}`，重复执行回 0），细节见 `commands.md` 的「栅格化」 |
| `select.subject` / `select.sky` 回 `selected:true` 却没选中 | `selected` 只表示"现在有选区"；成败看 `changed`、`coverage`、`message` |
| `document.pixel {sampleLayer:"current"}` 读到的是合成色 | `document.pixel` 只读合成结果、忽略 `sampleLayer`，回 0..1 的 `[r,g,b,a]`；单个图层用 `document.sampleColor {sampleLayer:"current"}` |
| 结果里的图层 id 存盘再打开就变了 | id 只在当前会话有效：serve 里关掉再打开同一 PSD 会重新编号，CLI 每次新进程也从 1 数起。`layer.*` 命令的 `layer` 参数接受图层名，跨进程按名字寻址；但 `type.*` 系列只认数字 id（见下两行） |
| `type.info {layer:"T1"}` 回的是别的层 | `type.info` 的 `layer` 名义上"接受 id 或名字"，但名字对不上时会**静默回落到活动层**，只有不存在的 id 才报 `no such layer`（实测 0.18，0.14 未复核）。`type.edit`、`type.setStyle` 同样会改错层。按名操作先 `layer.select {name}`，后续命令省略 `layer`；或从 `layer.list` 取 id 传 id。用名字批量查会全部得到同一层，字面核对会假通过 |
| 刚改过字的层，字面核对说"没缺" | 会话内新建或改样式后的文字层，`type.info` 的 `runs[].style.postscript_name` 是 `null`，存盘重开才补回来（实测 0.18，0.14 未复核）。只查这个字段会得到全部通过的假结论；退回 `font_family` + `font_style` 推断，或存副本重开再核 |
| 裁剪越界了，批次还是全绿 | `image.crop` 越界不报错，静默输出纯白小图并计入成功（实测 0.18，0.14 未复核）。裁剪、缩放类几何命令要抽查尺寸和像素 |
| 连续复制两层，顺序反了 | `layer.duplicate` 的副本落在**源层**正上方，不是在上一次副本上方；同一源层连复制两次，第二份在下面（实测 0.18）。频率分离、多通道合成这类要显式 `layer.moveTo {target, position:"above"}` 定序，光看命令没报错发现不了 |
| 想回读混合模式，`layer.list` 里没有 | `layer.list` / `layer.list {flat:true}` 不回 `blend`，写进去了也读不到；要用 `document.inspect` 的逐层 `blend` 核对，否则"设了模式但没生效"查不出来 |
| 新建的图层没进想要的组 | 新层插在活动层上方、同一父级里。选中**组本身**再新建时落点随版本变：0.12–0.14 记录为落在组外，0.18 实测落进组内（`parent` 指向该组、`depth` 加一）。选中组内某个子层则两版都进组。要精确控制就用 `layer.moveTo {position:"into"}`（`target` 必填）或 `layer.groupLayers`，别靠活动层推断 |
| `run --out` 只存了一个文档 | 只保存活动文档；多文档用 `document.activate` + `file.saveACopy`，或改用 serve |
| serve/MCP/桌面通道里 `file.*` 报 "uses ambient filesystem paths and is disabled" | 按命令名拒绝，不是安装坏了；改用 `doc.*` / `app.*`，或回到 CLI `run` |
| `doc.render` 存成 `.jpg` 打开是 PNG | `doc.render` 恒出 PNG，默认最长边 1024，上限 2048；要别的格式用 `doc.save` 或 CLI `convert` |
| 存成 PNG 后文档还是"未保存"、名字没变 | 只有 PSD/PSB/`.pcraft`/无损的 OpenRaster 会另存为并改变文档身份，扁平格式只是副本；`doc.save`/`app.save` 要求父目录已存在，CLI 会自动建 |
| 调整命令"执行成功"，历史里也多了一步，画面却没变 | 无效的调整也进历史；用像素取样证明效果 |
| serve `batch` 回 `ok:true` 但文件没存 | 步骤必须是对象；`doc.*` 步骤写 `{"method":…}`，引擎命令写 `{"command":…}`；失败记在 `result.failed` 和 `results[i].error`。`actions.play` 内部失败不算进 `failed`，要看那一步 result 里的 `failed` |
| `file.automate.batch` 退出码 0，部分图却没出 | 单个输入失败只进回复的 `errors:[{file, error}]`，不影响退出码 |
| MCP 工具报 JSON-RPC `-32602` | MCP 参数名多为 snake_case（`visible_only`、`max_side`、`stop_on_error`），和 serve 的 camelCase 不同；单个请求超过 1 MiB 会让 MCP 进程直接退出 |
| serve 启动后说没有读写权限 | serve/mcp 不读 `PHOTOCRAFT_AUTOMATION_*_ROOT` 环境变量，只认命令行参数 |
| `doc_save` 在 bridge 里改了 `quality`/`format` 却没生效 | bridge 只透传 `path`、`tgaBits`、`ddsCompression`、`ddsMipmaps`；其他选项报 `need headless mode`。要 1..100 的 quality 或分层导出，改用 headless serve/mcp 或 CLI |
| 桌面 `app.save` 传 `quality:85` 报错 | 桌面 `app.save` 的 quality 是 0..12（12=最高），不是 1..100；headless `doc.save` 才是 1..100 |
| 在 serve/MCP/桌面里调 `file.print` 被拒 | 打印按 `file.*` 规则禁用，只在 CLI 可用；自动化默认 `output` PDF + `dryRun`，`send:true` 才真的送印 |
| `file.print` 没给 `output` 却找不到 PDF | `pdf` 只在显式 `output` 时写出。实测 0.18：`file.print {}` 不给 `output`、不给 `dryRun`、不给 `send` 会**直接走真实打印队列**（回 `sent:true, backend:"windows"`，或被纸张/方向不匹配拦下）；不是"默认只出 PDF"。自动化一律显式给 `output`（+`dryRun`） |
| `file.saveACopy` 的 `overwrite` 不是“允许覆盖任意文件” | 它只控制替换**文档自己的文件**；其他同名文件本来就静默覆盖。它还有 `jpegFormat`、`tiffCompression`、DDS 选项 |
| 新建文档带 `profile` 在 serve 里被拒 | `file.new {profile}` 支持 ICC 标签，但路径按 ambient 规则被拒；用内置 id/`working`，或改在 CLI 做 |
| `document.activate` 只传索引、回执是 null | 早于 0.14 的版本确实回 null；0.14 起支持 `offset`（相对当前标签）并回 `{document}`（0.18 实测传索引回 `{document:0}`）；越界报错，不回绕 |
| 移动图层时选区没跟着动 | 0.14 `layer.translate` 加 `selection:true`，同一历史步移动选区；不传时只动图层 |
| XCF 文件打不开或存不回去 | XCF（`.xcf/.xcf.gz`）只读；Cineon 在 0.14 可写；KRA/PDN/Affinity/HEIC 也是导入。保存前看 `info` 的 `path`，别假设能回写 |
| 数据组在 0.14 起报 ambient 拒绝 | `image.applyDataSet` 和 `doc.exportDataSets` 的像素路径按 ambient 规则判定。serve/MCP 里不是"根内相对路径就能过"——含像素替换的数据组会被整条拒绝，根内路径同样不行；像素替换导出只能走 CLI |
| `ui.gpu.simulateLoss` 之后应用关了 | 带 `{destroy:true}` 会真销毁窗口 GPU、保存 Recovery 后关闭应用；只用于测试，正常会话用 `{error:true}` 或 `{}` |
| Windows Git Bash 里 JSON 内的路径找不到 | 位置参数会自动转换，JSON 字符串里的不会：写相对路径或 `cygpath -m` 得到的 `C:/…` |
| PowerShell 里 `--params '{"a":1}'` 报 bad JSON | Windows PowerShell 5.1 会吃掉引号；写成 `'{\"a\":1}'`、在参数前加 `--%`，或把 JSON 写进文件 |

## Verification

- 技能自检（执行，维护时用）：`python <skill-dir>/scripts/run_examples.py` 应全部 PASS（0.14.0 实测 40 PASS、0 FAIL、1 SKIP，案例 31 需设 `PCX_DESKTOP=1`）；`python <skill-dir>/scripts/check_docs.py` 核对文档里的命令 id、方法名、参数名与已安装注册表一致（计数以脚本输出的 baseline 为准，不在这里硬编码）；`python <skill-dir>/scripts/probe_gotchas.py` 逐条复验上面的坑点（24 项，实测 0.18 全绿）；`python <skill-dir>/scripts/test_workflow.py` 自测工作流脚本（0.14.0 实测 34/34）；`python <skill-dir>/scripts/test_control.py` 测客户端逻辑（fake server，0.14.0 实测 12/12），加 `--live` 再对真实 `photocraft-cli serve` 跑一遍。升级 PhotoCraft 后全部重跑，并对照 `references/whats-new.md` 更新文档；运行结果与文档冲突时以运行结果为准。
- 用户任务：Process 第 6 步的每项检查都要有输出可查；批处理以成功计数和逐个文件的断言为准，不以“命令跑完了”为准。打印任务检查 PDF/`sent`/纸张/标记；RAW 任务检查 16 位/ProPhoto 与 preview fallback；XMP 任务回读 `rawData` 和 `hasXmp`。

## Output

交付时依次列出：产出文件（路径、尺寸、格式、位深/模式）、母版文件、每项核对的结果、stderr 里值得用户知道的 `warning:`（字体回退、图层拼合、有损压缩、RAW preview fallback、XMP/元数据丢失等）、没能验证的部分及原因；PSD 规范化、复刻或切图任务另附审计、比对报告或资产 manifest 的路径；打印任务另附 PDF 路径、`file.print` 回执（`sent`/`backend`/`spooler`）和纸张/标记/出血设置；RAW 任务另附来源格式、位深/色彩空间（ProPhoto/16 位）和是否使用内嵌预览；XMP 任务列出写入/删除的图层和回读结果。
