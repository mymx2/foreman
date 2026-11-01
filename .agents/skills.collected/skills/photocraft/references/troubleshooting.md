# 报错速查

> 核对版本：命令 id 与参数按 photocraft-cli 0.14.0 复核；行为描述以 0.14.0 为基线，0.18.0 的补充实测在文中标注。按报错原文找原因和做法；跨任务的静默失败在 `SKILL.md` 的 Gotchas 表里，这里只收报错和域内问题。

## 按报错文本查

| 报错片段（原文） | 原因 | 做法 |
|---|---|---|
| `uses ambient filesystem paths and is disabled` | 在 serve / MCP / 桌面通道里调了带路径的 `file.*`、`layer.exportAs`、带 path 的 `actions.save/load`、`file.print*` 等。按命令名/参数拒绝 | 改用 `doc.*` / `app.*`，或回到 CLI `run`；完整清单见 `automation.md` |
| `quality` must be a whole number from 1 to 100 | `doc.save` / MCP `doc_save` 的 quality 严格 1..100；0/101/500 都报错。引擎导出命令才是 0..12 截断 | 用 1..100 或改用引擎导出命令；桌面 `app.save` 用 0..12 |
| `bridge mode saves with the app's current settings; ... need headless mode` | 在 `mcp --bridge` 里给 `doc_save` 传了 `format/quality/tiffLayers/dpxBits/index` | 改用 headless serve/mcp 或 CLI；bridge 只透传 `path/tgaBits/dds*` |
| `file.print` 报 ambient | 打印只在 CLI 可用 | 用 `photocraft-cli run ... --cmd file.print`；默认 `output` PDF + `dryRun` |
| `image.applyDataSet` / `doc.exportDataSets` 报 ambient | 0.14 起像素替换路径按 ambient 规则判定，serve/MCP 里连绝对路径也拒 | 在 CLI 里做像素替换导出，或只用文字/可见性数据组 |
| `automation filesystem access is not granted: read authority is absent` / `write authority is absent` | 启动 serve/mcp 时没给 `--automation-read-root` / `--automation-write-root`（serve/mcp 不读环境变量） | 显式传根目录参数 |
| `automation path rejected: parent traversal is not allowed` | 路径里有 `..` | 用根目录内的相对路径 |
| `automation path rejected: absolute paths must be inside the automation root` | 绝对路径在根目录之外 | 把文件放进根目录，或换根目录启动 |
| `automation path rejected: alternate separators are not allowed; use /` | 相对路径里用了反斜杠 | 相对路径统一用 `/` |
| `I/O: automation write … failed (NotFound)` | `doc.save` / `app.save` / 带 path 的 `doc.render` 不建父目录 | 先建目录；`doc.exportLayers` 会自动建 |
| `I/O: automation create export … failed (AlreadyExists)` | 导出目录里已有同名文件（导出类命令不覆盖） | 清空输出目录或换目录；`doc.exportLayers` 失败时会删掉本次已写文件 |
| `not available right now: no selection` | 当前没有选区，命令需要选区（如 `layer.layerMask.apply`）。注意 `select.deselect` 只有 serve 里才报这句，CLI `run` 里它静默通过（实测 0.18） | 先建选区；不要无脑调 deselect |
| `active layer is a Type layer, not a pixel layer` / `… Type layer without a mask` | 像素类命令（`paint.stroke` 等）作用在文字层上 | 先选像素层，或给文字层加蒙版；空像素层上调色可能静默成功，不作为错误分支 |
| `not available right now: select two or more layers` | `layer.arrange.reverse` 只选了一层 | 多选后再执行 |
| `not available right now: a document must keep at least one layer` | 试图删掉唯一的层 | 保留一层或先新建 |
| `needs \`layer\` or \`name\`` | `layer.select` 缺参数；它只认单数 `layer` | 传 `{"layer":id}` 或 `{"name":"…"}`，多选用 `mode:"add"` |
| `needs \`document\` (a tab index) or \`offset\`` | `document.activate` 的参数名是 `document`（索引），不是 `index` | 改参数名 |
| `missing \`path\`` | `path.set` 需要 `{"path":{subpaths:…}}` 包一层 | 按形状改 |
| `params must be a JSON object` | `--params` / `engine.execute` 传了数组、字符串、数字 | 传对象；省略或 `null` 表示空参数 |
| `unknown parameter \`x\`` | 该命令严格校验参数（`file.new`、`ui.set`、`layer.hideLayers` 等） | 用 `params.py --exact <id>` 查合法键 |
| `unknown command \`x\`` | id 拼错，或把会话方法当引擎命令（`doc.save`） | 引擎命令经 `engine.execute`，会话方法直接调 |
| `unknown method \`x\` (try \`methods\`)` | 在 serve 上调了 `ui.*`/`app.*`，或在桌面通道上调了 `doc.*`/`batch` | 按入口能力对照表换入口 |
| `unknown key`（MCP `-32602`） | MCP 参数名是 snake_case，和 serve 的 camelCase 不同 | `visible_only`、`max_side`、`stop_on_error` |
| `authentication required` | token 错、缺 token，或首帧不是 auth | 首帧发 `{"id":"auth","method":"auth","params":{"token":"…"}}`；无效会断开，需要重连 |
| `already authenticated` | 同一连接重复 auth | 继续用这条连接即可 |
| `the argument '--control-token <64-HEX>' cannot be used with '--control-token-file <PATH>'` | 环境变量和命令行参数各给了一种 token 来源 | 只留一种；`--control-token-file` 只覆盖同名环境变量 |
| `request exceeds 1048576 bytes` | 单行请求超过 1 MiB。serve 只回错误并继续，MCP 会直接退出 | 缩小载荷；大 base64 改走 serve 或 CLI |
| `automation preview side exceeds 2048 pixels` | `doc.render` 的 maxSide 或文档长边超过 2048 | 降 `maxSide`，或改用 CLI `convert`（无此上限） |
| `automation preview source exceeds 67108864 pixels` | 源文档超过 67,108,864 像素 | 先缩小源文档 |
| `automation PNG exceeds 5242880 bytes` | 预览 PNG 超过 5 MiB | 降 `maxSide`，或改用 CLI `convert` |
| `… is still running on this document` | 后台任务还在跑，命令被拒 | `jobs.list` 轮询；或 `wait:false` 后轮询 |
| `timeout: not run — …` | 请求排在队列里就到期，没执行 | 可以安全重发（仅桌面通道） |
| `timeout: no reply in 60s — …` | 已派发，可能已执行 | 先 `ui.inspect` / `document.inspect` 查状态，不要盲目重发 |
| `the Actions set holds N actions: pick one with --action <name>` | 动作集里有多个动作 | `batch --action <名字>` 选一个 |
| `has no Photoshop equivalent; pass "skipUnsupported": true` | `actions.save` 遇到 Photoshop 没有对应事件的步骤 | 传 `skipUnsupported:true`，看返回的 `skipped` |
| `no action named \`X\`` | droplet / batch 里 `actions.play` 找不到被调动作 | 用 `createDroplet` 生成（会写 `calledActions`），或给 `file.automate.batch` 传 `calledActions` |
| `not a PhotoCraft droplet` | 手写 `.pcdroplet` 缺 `photocraftDroplet` 键 | 用 `file.automate.createDroplet` 生成 |
| `import-only` / `cannot be written in this build` / `unknown file format` | 只读格式（KRA、XCF、PDN、Affinity、HEIC、SVG）不能写回；Cineon 在 0.14 可写，DDS 可写 | 另存 PSD / `.pcraft`（KRA 可存 `.ora`）；AVIF 取决于构建特性 |
| `Bitmap needs a Grayscale image` | 位图模式要求先转灰度 | 先 `image.mode.grayscale` |
| `Color Table needs an Indexed Color image` | 颜色表要求索引色（0.18 原文是 `Indexed Color`，按旧文案 `Indexed image` 搜不到） | 先 `image.mode.indexedColor` |
| `Duotone needs a Grayscale image` | 双色调要求灰度 | 先灰度再双色调；0.14 实测 PSD 重开仍为 Duotone，`.pcraft` 保留最全 |
| `Trap needs a CMYK document` | 陷印只对 CMYK 文档 | 先转 CMYK |
| `count, size and gutter must fit inside the target margins` | `view.newGuideLayout` 的 `width` 是单列宽，不是画布宽 | 先 `layout_design.py calc` 拿单列宽 |
| `pass \`quad\` …, \`matrix\`, or \`scaleX\`…` | `edit.transform` 只给了 `rect`（它只是源框） | 加 `quad` / `matrix` / `scaleX` 之一 |
| `the oldest state can't be deleted` | 删历史最早状态 | 先新建一个状态再删，或保留它 |
| `Color Sampler limit reached: at most 10 points per document` | 取样点超过 10 个 | 删掉旧的取样点 |
| `unknown preference` | 首选项键名错（是 camelCase，如 `general.alwaysCreateSmartObjectsWhenPlacing`） | 先 `prefs.get {}` 看完整键树 |
| `command not found` / 找不到 `photocraft-cli` | CLI 默认不在 PATH | 用 `find_cli.py` 定位，或设 `PHOTOCRAFT_CLI`（旧名 `PC_CLI` 也认，但它只是候选，坏路径会被跳过） |
| `bad --new JSON` / `bad JSON` / `lone leading surrogate` | 引号被 shell 吃掉，或 GBK 控制台把中文参数弄坏了 | PowerShell 用 `'{\"a\":1}'` 或 `--%`；Python 用 `-X utf8` 或读 `sys.stdin.buffer` |
| `duplicate name` / 同名输出 | `file.automate.batch` 的结果重名 | 在 `naming` 里加 `{serial}` 或 `{date}`；同名（含大小写差异）保留第一个 |
| `startingSerial plus the input count exceeds 4294967295` | 序号溢出 | 调小 `startingSerial` 或分批 |

## 没报错但结果不对

| 现象 | 原因 | 做法 |
|---|---|---|
| 调色命令成功、历史多一步，画面没变 | 作用是空操作（如灰度图上调色相）；调整层被蒙版/混合模式吞掉 | 用 `document.sampleColor` 证明像素变化 |
| 属性回显变了，渲染没变 | 蒙版、混合模式、智能对象让改动“看起来生效” | 渲染前后做像素对比（`psd_compare.py`） |
| 抠图后边缘发白/有 halo | 羽化过大或背景色混入 | 看三种背景（浅/深/棋盘）100%；`select.refineEdge` 调边缘 |
| `select.subject` 没选到主体 | 背景与主体颜色太接近；浅色主体被当背景 | 看 `changed`/`bounds`；用 `select.rect` 补选或修蒙版 |
| `image.detectFaces` 一张脸都没检出 | 默认 `minScore:0.5` 偏高；插画/卡通不出 | 显式降到 `0.1`；仍不行改手动框 |
| `layer.removeBackground` 抠错区域 | 它忽略已有选区，永远自己跑 subject | 要指定区域用 `select.*` + `refineEdge` |
| 文字“消失” | `type.edit {box}` 把高度改小，超出行不进 layout | 看 `type.info.lines`，恢复框高 |
| 文字整体偏上 | 首基线是框顶 + `'d'` 高度，不是 ascent | 需要视觉居中就补偏移 |
| 拼错的 `align` 没报错 | 非法枚举静默回落到 Left | 用合法值 |
| 智能滤镜参数改了没效果 | 滤镜不在智能对象上，或 `setParams` 的 index 不对 | `filter.convertForSmartFilters` 后再改；核对 index |
| 变量批量出图变量丢了 | 变量不随 PSD 保存 | `define`、导入、导出放在同一会话；用 `.pcraft` 保存定义 |
| CSV 首列没成为数据组名 | 表头不是空或 `DataSet` | JSON 数据组带 `name`，或把首列表头改成 `DataSet` |
| 像素替换图片溢出画框 | 没加 `clip:true` | 变量定义里加 `"clip":true` |
| 像素替换报 `path is relative` | 相对路径按已保存文档目录解析；文档没存过 | 用绝对路径，或先保存文档 |
| 批量修复跑完只抽查 | 失败被静默跳过 | 逐张出 no_op / inconclusive / unrestored 清单，静默跳过算失败 |

## 环境问题

- **CLI 不在 PATH**：跑 `<skill-dir>/scripts/find_cli.py --check`；Windows MSI 装在 `C:\Program Files\PhotoCraft\`，也查 `HKLM\Software\PhotoCraft\InstallDir`。
- **GBK 控制台**：Python 脚本加 `-X utf8`，或在脚本里 `sys.stdout.reconfigure(encoding="utf-8")`；读 stdin 用字节流再解码。中文路径和中文参数最容易坏在这里。
- **自己再起 Python 子进程**：只 `reconfigure` 本进程不够，子进程会退回系统代码页。显式传环境变量 `PYTHONIOENCODING=utf-8`（必要时加 `PYTHONUTF8=1`），并把这些变量从父进程复制过去，否则中文路径在子进程里会被写坏。
- **读 CLI 输出必须显式按 UTF-8 解码**：CLI 的 stdout/stderr 一律是 UTF-8，但 Windows 中文系统的默认代码页常是 cp936。用 `subprocess.run(..., text=True)` 不指定 `encoding` 会按系统代码页解码，中文图层名和文字全变成 U+FFFD，字数、层名比对跟着错（实测同一份输出按 cp936 解出 42 个替换字符）。写 `encoding="utf-8", errors="replace"`。
- **Python 里传 `/tmp/...` 这类 Git Bash 路径会被当成非法路径**：`bash` 的位置参数会自动转换，Python `subprocess` 不会。实测 CLI 回 `系统找不到指定的路径。(os error 3)` 且 stdout 为空。用 `C:/...` 形式的绝对路径或相对路径。
- **日志 0 字节像卡死**：Python 重定向是块缓冲，用 `python -u`。
- **Git Bash 路径**：位置参数会自动转换，JSON 字符串里的绝对路径不会；用 `cygpath -m` 得到 `C:/…`。
- **全局导出的 `PHOTOCRAFT_CONTROL_*` / `PHOTOCRAFT_AUTOMATION_*`**：会让每次启动的桌面版都开控制端口、让客户端读到不是本任务的 token。跑案例或测试前显式清掉。
- **桌面控制端口连不上**：只有启动时带了 `--control`（或设了 `PHOTOCRAFT_CONTROL_PORT`）才开；端口被占用时程序照常启动但不提供控制服务，只写 stderr，Windows GUI 程序看不到——换端口重启。
- **serve 中途断开**：空闲约 30 s 会被断开；客户端要重连并重新 auth，不要复用旧 socket。
- **并发**：serve / 桌面通道的所有连接共用一个引擎和一个活动文档，命令串行；要并发就开多个 serve（不同端口、不同 token 文件）。
- **`photocraft-cli` 命令成功但没写出文件**：`run` 没给 `--out`；引擎批处理（`file.automate.batch`）的单个输入失败只进 `errors[]`，整条 `run` 仍退出 0。CLI `batch` 子命令相反，任一文件失败退出 1。
