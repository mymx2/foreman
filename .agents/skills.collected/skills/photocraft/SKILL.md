---
name: photocraft
description: 驱动 PhotoCraft（开源、离线、兼容 Photoshop 的图像编辑器）完成可复现的修图与 PSD 自动化：通过 photocraft-cli、批处理与动作、serve 会话、MCP 或桌面控制通道执行注册表命令，覆盖调色、抠图换底、文字与形状、滤镜修复、模板批量出图、格式转换与切图导出，以及 PSD 规范化、栅格排版和分层稿交付。当用户要用 PhotoCraft 或 photocraft-cli 处理图片或 PSD、批量处理一个目录、或把 PhotoCraft 接给 agent 与 MCP 客户端时使用。不适用于生成式 AI 绘图、RAW 照片库管理、网页 CSS 或 Figma 设计稿，以及没有安装 PhotoCraft 的环境。
when_to_use: photocraft, photocraft-cli, PSD 自动化, 批量修图, 图片批处理, 抠图换背景, 电商白底图, 加水印, 调色与 LUT, 格式转换, 切图导出, 多倍图, 文字居中, 栅格排版, PSD 规范化, PSD 复刻, 分层稿交付, 缺失字体, 动作与 Droplet, 模板批量出图, 截图打码, serve 会话, MCP 修图, 桌面控制通道
---

# PhotoCraft

退出码 0 不代表做对了：多数命令会把拼错的参数悄悄忽略、按默认值照跑，serve 的 `batch` 有步骤失败时顶层照样回 `ok:true`。每一步都要用返回 JSON、`info` 和预览图核对。

## Overview

PhotoCraft 的绝大多数菜单动作、工具和对话框都对应注册表里的一条命令（0.10.0 共 918 条；少数桌面菜单项不在注册表里）。CLI、`serve`、MCP、桌面控制通道调用的是同一份注册表，差别在文件权限和可用的方法。本技能负责：选对入口、查准参数、在副本上执行、逐项核对产出。`examples/` 里的 Python 场景脚本在 0.10.0 上实跑通过（案例 31 需要真实窗口，默认跳过），可以照着改；PSD 工程类任务另有审计、比对、切图脚本。

## Outcome Contract

- **Outcome**：用户要的图片或文档写到指定（或新建）的输出目录，原文件不变；需要后续修改时同时交付分层母版（PSD 或 `.pcraft`）。
- **Done when**：每个产出都过了核对：尺寸、模式、位深、图层与要求一致（`info`），关键命令的返回值符合预期，抠图、调色、打码、排版这类视觉结果看过预览图；PSD 规范化、复刻或交付任务另有审计、比对或资产清单报告。
- **Evidence**：CLI 退出码；`run` 每行 JSON 里的 `result`；`info --compact` 断言；预览 PNG；CLI 批处理的 `N succeeded, 0 failed`、`file.automate.batch` 回复里空的 `errors`、serve `batch` 的 `result.failed == 0`；脚本报告（`psd_compare`、`psd_audit`、`trim_export` 的 manifest）。
- **Authorization**：读用户给的文件、在新的输出目录里写产出可以直接做。以下先征得同意：覆盖原文件（`--in-place`、写回原 PSD、不带 path 的保存）、启动桌面窗口、关闭用户打开的文档或退出程序（`app.quit` 和引擎命令 `file.close` 都会直接丢弃未保存的修改，不弹提示）、`prefs.set` 或 `prefs.reset`、安装插件或字体、把动作重放到用户的文档上。

## When to Use

- 格式转换、PSD/TIFF 结构检查、导出多种交付格式。
- 单张或成批修图：调色、裁切缩放、抠图换底、水印、去瑕疵、打码、风格滤镜。
- 用模板批量出图：改文案、变量数据组、图层/画板/切片/资源导出。
- PSD 工程：规范化与复刻、栅格排版、文字排版、分层稿交付、补字体。
- 让 agent 连续编辑：serve 长会话、MCP 工具、驱动桌面窗口。
- 不适用：生成式填充或 AI 绘图（PhotoCraft 没有；`select.subject` 一类是经典算法，不是学习型模型）；照片库与 RAW 管理；网页样式与 Figma 稿评审。

## Process

1. **定位 CLI**：执行 `python <skill-dir>/scripts/find_cli.py --check`。它依次看 `PHOTOCRAFT_CLI`、`PATH`、安装目录（Windows MSI 装在 `C:\Program Files\PhotoCraft\`，不进 PATH）。完成标准：有可执行路径和 `--version` 输出；找不到就请用户提供路径，不要猜。
2. **看输入**：`photocraft-cli info <文件> --compact`。完成标准：知道尺寸、模式、位深、分辨率、有无文字层与智能对象、`warnings`（缺字体等）。
3. **查命令**：先在 `references/commands.md` 找候选 id，再执行 `python <skill-dir>/scripts/params.py --exact <id>` 取已安装版本的参数文本；不知道 id 时传关键词（如 `curves`）。完成标准：要用的每个命令都核对过参数名、范围和默认值。
4. **选入口**：按下方"入口选择"和"入口能力差异"两张表。完成标准：确定用 `run`、`batch`、`serve`、`mcp` 还是桌面控制通道，并确认要用的命令在这个入口没有被拒。
5. **执行**：在新的输出目录里工作，输入先复制进去；JSON 参数里用相对路径；能合并的步骤放进同一条 `run`；扁平交付（JPG/PNG/WebP）之外保留一份母版。完成标准：命令退出码 0，stderr 的 `warning:` 都看过。
6. **核对**：对每个产出至少做一项检查：`info` 断言尺寸/模式/图层；`document.pixel`（合成结果）或 `document.sampleColor`（可指定合成或当前层）取样；命令返回的 `files`/`count`/`bounds`；颜色要紧的（商品、品牌色）比较处理前后主体的色相和饱和度；视觉相关的生成小尺寸预览并亲自看。完成标准：所有产出都有一条通过的检查，失败的已修正或如实列出。只查尺寸和背景的质检会放过偏色。
7. **交付**：按 Output 格式汇报。

## 入口选择

| 情况 | 用 |
|---|---|
| 一张图、步骤固定、CI | `photocraft-cli run <文件> --cmd <id> --params '<json>' … --out <文件>` |
| 只换格式 | `photocraft-cli convert <in> <out> [--quality N] [--tiff-layers]` |
| 一个文件夹套同一组步骤 | `photocraft-cli batch --actions <json\|atn> --in <dir> --out <新目录>`；要命名模板、子目录、序号时用引擎命令 `file.automate.batch` |
| 要看结果再决定下一步、多文档、长任务 | `photocraft-cli serve --automation-read-root <dir> --automation-write-root <dir>`（stdio 不需要 token） |
| 交给 MCP 客户端当工具用 | `photocraft-cli mcp --automation-read-root <dir> --automation-write-root <dir>` |
| 要真实窗口：读界面、截窗口、模拟压感笔 | 独立实例 `photocraft --new-instance --control <port> --control-token-file <文件>`，再用 `scripts/control.py` 或 `photocraft-cli mcp --bridge 127.0.0.1:<port>` 驱动 |
| 要改用户已经打开的文档 | 只有那个实例启动时带了 `--control`（或 `PHOTOCRAFT_CONTROL_PORT`）才连得上；否则请用户保存后在 serve 里打开该文件，或按用户同意重启带控制端口的实例 |

CLI 细节见 `references/cli.md`；serve、MCP、桌面控制通道见 `references/automation.md`；格式能保留什么见 `references/formats.md`。工作流脚本的可选依赖（Pillow、psd-tools）见 `scripts/requirements.txt`，缺了会打印说明并退出 2。

## 入口能力差异

| | CLI `run` / `batch` | `serve` / MCP | 桌面控制通道 |
|---|---|---|---|
| 文件读写 | 普通操作系统路径，不受限 | 只在 `--automation-*-root` 之下，用 `doc.*`（MCP 为 `doc_*` 工具） | 只在根目录之下，用 `app.open` / `app.save` |
| `file.export.*`、`file.generate.imageAssets`、`file.package`、`file.automate.batch`、`file.placeEmbedded` 等带路径的 `file.*` | 可用 | 按命令名拒绝（例外：`file.export.renderVideo`、`file.export.exportPreferences` 可用，只写到写根目录下） | 按命令名拒绝 |
| `image.mode.*` | 可用 | 可用 | 拒绝 |
| 状态 | 每次一个进程，跑完即丢 | 常驻：文档、历史、快照、预设 | 真实窗口；所有连接共用一个活动文档 |
| 独有方法 | — | `doc.*`、`session.list`、`batch`、`methods` | `ui.*`、`app.*` |

完整的对照表（含每种拒绝的报错原文）见 `references/automation.md`。

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

## 专项工作流

| 任务 | 先读 | 脚本（执行） |
|---|---|---|
| 不规范 PSD 的规范化与复刻、分层稿交付 | `references/psd-workflow.md` | `scripts/psd_audit.py`、`scripts/psd_compare.py` |
| 栅格排版、对齐分布、参考线 | `references/layout.md` | `scripts/layout_design.py` |
| 抠图、裁边、切图、多倍图与资产导出 | `references/cutout-export.md` | `scripts/trim_export.py` |
| 修复、人像、合成的工序与验收 | `references/retouch.md` | — |
| 文字框内居中、溢出、行距、竖排、路径文字 | `references/text-layout.md` | — |
| 缺字体、换字体、字体授权 | `references/fonts.md` | — |
| 动作、批处理、Droplet、变量数据组 | `references/actions-batch.md` | — |
| 报错文本速查 | `references/troubleshooting.md` | — |

## Hard Rules

- 原文件只读：输入先复制进新的输出目录；不加 `--in-place`、不写回输入路径、不用不带 path 的保存，除非用户明确要求。
- 写 JSON 参数前查参数文本，执行后核对返回值。
- 抠图、智能选区、人脸检测、调色、修复、打码、排版的结果必须看预览图确认，再交付或继续批量。
- 文字类机密（密钥、卡号、证件号、姓名、邮箱）用实心色块覆盖；马赛克和模糊只用于人脸、头像这类"不可辨认即可"的内容。
- serve/MCP 只把本任务的目录授权为读写根目录；控制令牌只放在文件里、显式交给客户端；令牌和密钥不进命令参数、文件名、元数据或日志。不要全局导出 `PHOTOCRAFT_CONTROL_PORT`、`PHOTOCRAFT_CONTROL_TOKEN`、`PHOTOCRAFT_CONTROL_TOKEN_FILE`：桌面版每次启动都会因此打开控制端口，客户端也会读它们。
- 启动桌面窗口前征得同意，用 `--new-instance` 加临时 `PHOTOCRAFT_CONFIG_DIR`，不碰用户已打开的实例和设置；用完关闭这个实例。
- 缺字体阻止交付：先列候选、由用户确认再替换；不用 `type.replaceAllMissingFonts`（它把所有缺失字体无提示地换成 Inter）。
- 字体和素材按授权使用：免费商用不等于允许随稿再分发；占位图只用于测试。
- 变量数据组的像素替换会绕过读根目录限制去读图片，只用可信的数据文件。

## Gotchas

以下都在 0.10.0 上实测过。按报错文本查问题见 `references/troubleshooting.md`。

| 现象 | 做法 |
|---|---|
| `image.imageSize {"widht":600}` 退出码 0，尺寸没变 | 多数命令静默忽略未知键（`file.new`、`ui.set`、`ui.screenshot` 等少数才报错）；拼错的枚举值（如 `align:"centre"`）也静默回落到默认值。看返回值 |
| 引擎导出命令传 `quality:80` 和传 12 结果一样 | `file.automate.batch`、`imageProcessor`、`saveACopy`、`createDroplet`、各类 `file.export.*` 的 `quality` 是 0..12，超出静默截到 12；`file.export.saveForWebLegacy` 是 0..100；CLI `--quality` 和 serve `doc.save` 是 1..100 |
| 无选区时 `select.deselect` 让整条 `run` 失败 | 当前状态不可用的命令直接报错，`run` 后面的步骤和 `--out` 都不执行；`layer.layerMask.revealSelection` 会用掉选区 |
| `select.subject` / `select.sky` 回 `selected:true` 却没选中 | `selected` 只表示"现在有选区"；成败看 `changed`、`coverage`、`message` |
| `document.pixel {sampleLayer:"current"}` 读到的是合成色 | `document.pixel` 只读合成结果、忽略 `sampleLayer`；单个图层用 `document.sampleColor {sampleLayer:"current"}` |
| 结果里的图层 id 存盘再打开就变了 | id 只在当前会话有效：serve 里关掉再打开同一 PSD 会重新编号，CLI 每次新进程也从 1 数起。`layer` 参数也接受图层名，跨进程按名字寻址 |
| 新建的图层没进想要的组 | 新层插在活动图层上方、同一个父级里；选中组本身再新建会落在组外。用 `layer.moveTo {position:"into"}` 或 `layer.groupLayers` |
| `run --out` 只存了一个文档 | 只保存活动文档；多文档用 `document.activate` + `file.saveACopy`，或改用 serve |
| serve/MCP/桌面通道里 `file.*` 报 "uses ambient filesystem paths and is disabled" | 按命令名拒绝，不是安装坏了；改用 `doc.*` / `app.*`，或回到 CLI `run` |
| `doc.render` 存成 `.jpg` 打开是 PNG | `doc.render` 恒出 PNG，默认最长边 1024，上限 2048；要别的格式用 `doc.save` 或 CLI `convert` |
| 存成 PNG 后文档还是"未保存"、名字没变 | 只有 PSD/PSB/`.pcraft`/无损的 OpenRaster 会另存为并改变文档身份，扁平格式只是副本；`doc.save`/`app.save` 要求父目录已存在，CLI 会自动建 |
| 调整命令"执行成功"，历史里也多了一步，画面却没变 | 无效的调整也进历史；用像素取样证明效果 |
| serve `batch` 回 `ok:true` 但文件没存 | 步骤必须是对象；`doc.*` 步骤写 `{"method":…}`，引擎命令写 `{"command":…}`；失败记在 `result.failed` 和 `results[i].error`。`actions.play` 内部失败不算进 `failed`，要看那一步 result 里的 `failed` |
| `file.automate.batch` 退出码 0，部分图却没出 | 单个输入失败只进回复的 `errors:[{file, error}]`，不影响退出码 |
| MCP 工具报 JSON-RPC `-32602` | MCP 参数名多为 snake_case（`visible_only`、`max_side`、`stop_on_error`），和 serve 的 camelCase 不同；单个请求超过 1 MiB 会让 MCP 进程直接退出 |
| serve 启动后说没有读写权限 | serve/mcp 不读 `PHOTOCRAFT_AUTOMATION_*_ROOT` 环境变量，只认命令行参数 |
| Windows Git Bash 里 JSON 内的路径找不到 | 位置参数会自动转换，JSON 字符串里的不会：写相对路径或 `cygpath -m` 得到的 `C:/…` |
| PowerShell 里 `--params '{"a":1}'` 报 bad JSON | Windows PowerShell 5.1 会吃掉引号；写成 `'{\"a\":1}'`、在参数前加 `--%`，或把 JSON 写进文件 |

## Verification

- 技能自检（执行，维护时用）：`python <skill-dir>/scripts/run_examples.py` 应全部 PASS（案例 31 默认 SKIP，设 `PCX_DESKTOP=1` 才运行）；`python <skill-dir>/scripts/check_docs.py` 核对文档里的命令 id、方法名、参数名与已安装注册表一致；`python <skill-dir>/scripts/probe_gotchas.py` 逐条复验上面的坑点；`python <skill-dir>/scripts/test_workflow.py` 自测工作流脚本；`python <skill-dir>/scripts/test_control.py` 测客户端逻辑（fake server），加 `--live` 再对真实 `photocraft-cli serve` 跑一遍。升级 PhotoCraft 后全部重跑，运行结果与文档冲突时以运行结果为准并改文档。
- 用户任务：Process 第 6 步的每项检查都要有输出可查；批处理以成功计数和逐个文件的断言为准，不以"命令跑完了"为准。

## Output

交付时依次列出：产出文件（路径、尺寸、格式、位深/模式）、母版文件、每项核对的结果、stderr 里值得用户知道的 `warning:`（字体回退、图层拼合、有损压缩等）、没能验证的部分及原因；PSD 规范化、复刻或切图任务另附审计、比对报告或资产 manifest 的路径。
