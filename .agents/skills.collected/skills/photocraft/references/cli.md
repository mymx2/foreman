# photocraft-cli 参考

> 核对版本：命令 id 与参数按 photocraft-cli 0.12.0 (6a2d027ee) 复核；行为描述写于 0.10.0 (8407d9ccb)。

任何子命令加 `--help` 都打印同一份总帮助。serve、MCP、桌面控制通道见 automation.md；动作文件的写法、`file.automate.batch`、变量数据组见 actions-batch.md；各格式的读写与警告见 formats.md。

## 定位可执行文件

按顺序找，找到就停：

1. 环境变量 `PHOTOCRAFT_CLI`（技能约定，指向可执行文件的绝对路径）。
2. `PATH` 里的 `photocraft-cli`。
3. Windows：MSI 装在 `C:\Program Files\PhotoCraft\`，`photocraft-cli.exe` 和 `photocraft.exe` 在同一目录，安装程序不把它加进 PATH，所以 `command not found` 不代表没装。改过安装目录时查注册表：`reg query "HKLM\Software\PhotoCraft" /v InstallDir`（Git Bash 里把 `/v` 写成 `//v`）。便携版 zip 解压到哪里就在哪里，两个 exe 同目录。
4. macOS：CLI 是单独的 `photocraft-cli-<版本>-macos-universal.zip`；`PhotoCraft.app` 里只有桌面版。
5. Linux：deb、rpm 装到 `/usr/bin/photocraft-cli`；tar.gz 在解压目录的 `bin/` 下；Flatpak 不带 CLI。

（执行）`python <skill-dir>/scripts/find_cli.py --check` 按这个顺序查找，并跑 `--version` 和一次注册表查询；`--json` 列出查过的每个位置。

安装检查就是用绝对路径跑 `--version`，输出 `photocraft-cli 0.12.0 (6a2d027ee, 2026-10-21)` 这样一行即可，不要求 CLI 在 PATH 上。找不到时请用户给出路径，不要猜。

## 子命令与参数

| 子命令 | 位置参数 | 取值 flag | 开关 flag | 用途 |
|---|---|---|---|---|
| `convert` | `<in> <out>` | `--format` `--quality` `--tga-bits` `--dpx-bits` `--dds-compression` | `--tiff-layers` `--dds-mipmaps` | 打开一个文件，按输出扩展名导出 |
| `info` | `<file>` | — | `--compact` | 打印文档 JSON |
| `run` | `<file>` 或 `--new <json>` | `--new` `--cmd` `--params` `--out` `--format` `--quality` `--tga-bits` `--dpx-bits` `--dds-compression` | `--tiff-layers` `--dds-mipmaps` | 打开或新建文档，按顺序执行引擎命令，给了 `--out` 才保存 |
| `batch` | — | `--actions` `--action` `--in` `--out` `--format` `--quality` `--tga-bits` `--dpx-bits` `--dds-compression` | `--in-place` `--tiff-layers` `--dds-mipmaps` | 目录里每个文件跑同一组步骤 |
| `droplet` | `<file.pcdroplet> <文件或目录>…` | `--out` | — | 运行 Droplet |
| `commands` | — | `--filter` | `--json` | 列出命令注册表 |
| `serve` | — | `--port` `--control-token` `--control-token-file` `--automation-read-root` `--automation-write-root` | — | 常驻 JSON-lines 会话 |
| `mcp` | — | `--bridge` `--control-token` `--control-token-file` `--automation-read-root` `--automation-write-root` | — | MCP 服务 |

- `--format <ext>` 覆盖输出扩展名推断的格式，`--format .jpg` 与 `--format jpg` 等价。
- `--quality <1-100>` 只作用于 JPEG 和 WebP，刻度见下文"quality 刻度"。
- `--tga-bits 24|32`、`--dpx-bits 8|10|12|16` 设定位数；`--dds-compression none|bc1|bc2|bc3` 设 DDS 压缩（DXT1/DXT3/DXT5），`--dds-mipmaps` 写完整 mip 链；TIFF 默认扁平，`--tiff-layers` 才写图层。
- 取值 flag 写成 `--quality 80` 或 `--quality=80` 都行；开关 flag 带值（`--tiff-layers=1`）是用法错误。
- `run` 里每个 `--params` 属于它前面那个 `--cmd`；不需要参数时省略。`--params` 和 `--new` 都只收 JSON 对象，不支持 `@文件` 写法。

## 输出与退出码

| 退出码 | 含义 | 实际报错（stderr） |
|---|---|---|
| 0 | 成功，可能带 warning | `warning: lossy compression` |
| 1 | 执行失败 | `error: bad --quality \`101\`: expected a whole number from 1 to 100`<br>`error: --params must follow a --cmd`<br>`error: bad --new JSON: key must be a string at line 1 column 2`<br>`error: run needs at least one --cmd (or --out)`<br>`error: convert needs <in> <out>`<br>`error: \`select.deselect\`: command \`select.deselect\` is not available right now: no selection`<br>批处理有文件失败：`error: 1 file(s) failed` |
| 2 | 用法错误，后面附整份帮助 | `error: unknown flag --fromat for convert`<br>`error: unknown command \`frobnicate\``<br>`error: --quality needs a value`<br>`error: --tiff-layers takes no value`<br>`error: unknown flag --naming for batch` |

各子命令的输出：

- `run`：每条 `--cmd` 向 stdout 打一行紧凑 JSON `{"command":"<id>","result":…}`，没有返回值的命令 `result` 是 `null`。某条命令第一次用到未安装的字体时，那一行多一个顶层 `warnings` 数组，stderr 打一次 `warning: font '…' is not installed; text may render using a fallback face`（`type.create` 自己的 `result.warnings` 每次都带）。命令失败时 stderr 打 `error: \`<id>\`: <原因>`，之前成功的行已经打印。
- `convert`：成功时 stdout 为空。
- 警告一律写 stderr，以 `warning: ` 开头，不改变退出码。导出相关的警告原文见 formats.md。
- `batch`：stdout 每个成功文件一行 `ok    <in> -> <out>`，最后一行 `N succeeded, M failed`；stderr 是 `FAIL  <in>: <原因>`、各文件的 warning 和最后的 `error: N file(s) failed`。
- `droplet`：每个成功文件一行 `ok    <输出文件>`，失败为 `FAIL  <文件>: <原因>`。
- `info`：与引擎命令 `document.inspect` 结构相同，多了 `file` 和 `warnings`，去掉 `history`、`canUndo`、`canRedo`、`revision`。缺字体等警告留在 JSON 的 `warnings` 里，stderr 为空，加不加 `--compact` 都一样；`--compact` 只是输出成一行。
- `commands`：默认每行 id、标签、菜单；`--json` 输出数组，每项 `{id, label, menu, shortcut, params, enabled, disabledReason, needsDocument}`，个别命令另有 `keywords`（0.10.0 里只有 `select.rect`）。`--filter` 对 id、标签、`keywords` 做不分大小写的子串匹配。

## run 的执行模型

1. 打开 `<file>`（按文件内容识别格式，扩展名写错也能打开），或用 `--new` 新建。`--new` 收 `file.new` 的参数：`width` `height`（1..300000，小数四舍五入）`mode` `depth` `background` `backgroundColor` `resolution` `name`。超出范围直接报错，例如 `error: --new: invalid parameters for \`file.new\`: \`height\` must be a number within 1..=300000`；`file.new` 不认识的键也报错。
2. 命令按顺序作用于活动文档。
3. 任何一条命令报错，整条 `run` 以退出码 1 结束，后面的命令和 `--out` 都不执行，磁盘上什么都不写。"当前状态不可用"的命令也算报错（例如没有选区时 `select.deselect`）。
4. 下列命令会新建文档并把它设为活动文档：`file.new`、`image.duplicate`、`channel.split`（拆出的文档编号 0/1/2，最后一个活动，原文档默认关闭）、`layer.smartObjects.editContents`、`history.newDocument`、`file.scripts.loadFilesIntoStack`、`file.automate.contactSheetII`、`file.automate.cropAndStraightenPhotos`、`file.automate.photomerge`、`file.automate.mergeToHdrPro`。之后的命令都落在新文档上，用 `document.activate {"document":i}` 切回。
5. `--out` 只保存活动文档。其他文档先 `document.activate`，再 `file.saveACopy {"path":…}` 逐个保存。
6. `run <file> --out <file>` 不带 `--cmd` 时等于一次转换。
7. 进程退出后什么都不留：选区、快照、预设、动作、变量定义、插件都只活在这一次 `run` 里。要根据结果决定下一步、在多文档之间来回，改用 serve。

## batch

```sh
photocraft-cli batch --actions <steps.json|set.atn> [--action <名字>] --in <目录> --out <新目录> \
  [--format <ext>] [--quality <1-100>] [--tiff-layers] [--in-place]
```

- 动作文件的几种写法、动作集与 `.atn` 的规则见 actions-batch.md。动作集里有多个动作时必须用 `--action` 选一个。
- 只处理 `--in` 顶层的文件，按文件名排序；没有可读扩展名的文件静默跳过，子目录不进入。要递归、命名模板、序号，改用 `file.automate.batch`（见 actions-batch.md）。CLI `batch` 没有 `--naming`、`--startingSerial`。
- 读不了的文件记为 `FAIL  in\bad.png: codec: unrecognized image format`，其余文件照常处理，最后退出码 1。
- 输出为 `<--out>/<原文件名>.<扩展名>`。扩展名默认沿用输入，大小写也保留（`d.JPG` → `d.JPG`）；给了 `--format` 就用它（`--format jpg` → `d.jpg`）。`--out` 不存在时自动创建，包括多级目录。
- 输出目录里的同名文件直接覆盖，不提示。
- 同一轮里两个输入映射到同一个输出名（`a.png` 和 `a.jpg` 配 `--format jpg`）时，先处理的写入，后一个失败：`FAIL  in\a.png: not written: out2\a.jpg already holds the result of in\a.jpg from this run (same output name)`。
- `--out` 与 `--in` 是同一目录（写成 `./in/` 也一样）会被拒绝，退出码 1；确实要覆盖原图才加 `--in-place`。
- 不是事务：中途有文件失败，之前写出的文件留在原处。

## droplet

```sh
photocraft-cli droplet <file.pcdroplet> <文件或目录>… [--out <目录>]
```

- 输出目录的优先级：`--out` > droplet 文件里的 `options.output` > `<输入所在目录>/droplet-output/`。不给 `--out` 时结果写在原图旁边的 `droplet-output/` 里。
- droplet 文件用引擎命令 `file.automate.createDroplet` 生成（见 actions-batch.md）。
- 任何一个输入失败，退出码 1。

## commands 与参数文本

查参数的两种方式：`photocraft-cli commands --json --filter <关键字>`；或（执行）`python <skill-dir>/scripts/params.py <关键字…>`，`--exact <id>` 只看指定 id，`--prefix filter.blur` 按 id 分段前缀。两者读的都是已安装版本的注册表，以它为准。

`params` 是给人读的说明，不是 JSON Schema：

| 写法 | 含义 |
|---|---|
| `"width":1..300000=1920` | 取值范围 1..300000，默认 1920 |
| `"mode":"rgb\|gray\|grayscale\|cmyk\|lab"="rgb"` | 枚举，默认 `rgb` |
| `"layer":id?` | 可选；多数图层命令不给时作用于活动图层或选中的图层，括号里会写明（`no layer: every selected layer`） |
| `"color":"#rrggbb"=foreground` | 默认取前景色 |
| `"red":json` | 嵌套对象或数组，结构写在后面的括号说明里 |
| `…character keys` | 省略了的键；`type.create` 接受 `type.setStyle` 列出的全部字符属性 |
| `→ {width,height}` | 返回值的形状 |

注册表也有不全的地方：`file.export.renderVideo` 写着 `{} → {}`，实际接受 `dir` 和 `format`（`png`/`gif`）。

未知键的处理因命令而异。0.10.0 时对当时全部 918 条命令各传一次 `{"bogusKey":1}` 的扫描结果（0.12.0 新增或变更的条目未重扫）：36 条报 `unknown parameter`（下表，含全部 36 条），336 条静默忽略并按默认值执行，323 条先因前置条件失败（没有文字层、没有选区等）而没测出未知键的处理，其余 223 条因缺少必填参数等其它原因报错。换一份测试文档重扫，后三类的数字会变；报错的那 36 条是命令自身的校验，不随文档变。

| 报 `unknown parameter \`bogusKey\`` 的命令 | 范围 |
|---|---|
| `file.new`、`layer.hideLayers`、`layer.showLayers` | — |
| `filter.blur.*` | gaussianBlur blur blurMore boxBlur motionBlur radialBlur surfaceBlur smartBlur shapeBlur（lensBlur、average 不校验） |
| `filter.sharpen.*`、`filter.noise.*` | 全部 |
| `filter.distort.*` | twirl pinch spherize wave ripple polarCoordinates（shear、zigZag 不校验） |
| `filter.other.*` | highPass minimum maximum offset |
| 其他 | `filter.pixelate.mosaic`、`filter.stylize.emboss`、`filter.stylize.findEdges`、`filter.stylize.solarize` |

滤镜库（`filter.gallery.*`、`filter.filterGallery` 的效果）、模糊画廊、渲染类、`filter.stylize.oilPaint`、`filter.liquify`、`filter.cameraRaw`、`filter.lensCorrection` 和绝大多数非滤镜命令都不校验未知键。

枚举值拼错也分两种：

- 报错并列出合法值：`layer.setProps {blend}`（`unknown blend mode \`Multipy\``，大小写不敏感）、`image.canvasSize {anchor}`、`edit.fill {contents}`、`image.rotation.arbitrary {direction}`、`filter.noise.addNoise {distribution}`、`layer.newAdjustmentLayer.photoFilter {filter}`、`filter.liquify` 的笔画 `tool`（`unknown variant \`twirl\`, expected one of …`）。
- 静默回落到默认值，退出码 0：`image.imageSize {resample}`、`image.trim {basedOn}`、`select.rect {mode}`、`type.create` / `type.setStyle` 的 `align`（回落为左对齐）、`type.edit {antialias}`。

所以退出码 0 不能证明参数生效，要看返回值或 `info`。

## 路径与 shell

- CLI 子命令是"本地可信"模式：路径就是普通操作系统路径，不受 automation 根目录限制，引擎命令里的路径参数（`file.saveACopy`、`file.placeEmbedded`、各类导出目录）也直接读写。
- JSON 参数里的相对路径相对进程的当前工作目录。推荐先 `cd` 到工作目录，JSON 里写相对路径。
- Windows Git Bash（MSYS）会转换位置参数和 `--out` 后面的 `/d/...`，不转换 JSON 字符串里的路径：JSON 写 `"/d/data/x.png"` 会报 `系统找不到指定的路径。 (os error 3)`。写相对路径，或用 `cygpath -m` 得到 `D:/...` 形式。
- Windows PowerShell 5.1（Windows 11 自带的版本）传给外部程序时会去掉单引号字符串里的双引号，`--new '{"width":80}'` 报 `error: bad --new JSON: key must be a string at line 1 column 2`；`(Get-Content p.json -Raw)` 也一样。实测可行的写法：
  1. 停止解析标记，后面按 cmd 的规则写引号：`& $pc --% run --new "{\"width\":80,\"height\":60}" --out a.png`。值里有空格也行；`--%` 之后不能再用 PowerShell 变量。
  2. 单引号内转义：`'{\"width\":80,\"height\":60}'`。JSON 字符串值里有空格时会被拆成两个参数，报 `error: run needs exactly one of <file> or --new <json>`。
  3. `((@{width=80;height=60} | ConvertTo-Json -Compress) -replace '"','\"')`，有空格时同样会坏。
  最稳的是从 Python 用参数列表调用（`subprocess.run([cli, "run", "--new", json.dumps(p), ...])`），完全绕开 shell 引号。
- cmd.exe：外层双引号、内层 `\"`：`--new "{\"width\":80,\"height\":60,\"name\":\"a b\"}"`，值里有空格也行。
- JSON 文件（动作文件等）要存成不带 BOM 的 UTF-8。带 BOM 时报 `error: actions JSON: expected value at line 1 column 1`。PowerShell 5.1 的 `Set-Content -Encoding utf8` 会写 BOM；用 `[IO.File]::WriteAllText($path, $text)` 或 Python 写。
- CLI 写文件时自动创建缺失的父目录（`run --out`、`convert`、`batch --out`、`file.saveACopy`、图层与画板导出、`file.export.renderVideo`），已存在的同名文件直接覆盖，所有 CLI 导出都不会因为文件已存在而失败。输出写进新目录，原图只读。

## quality 刻度

| 入口 | 刻度 | 不给时 | 超出范围 |
|---|---|---|---|
| CLI `--quality`（`convert`、`run`、`batch`） | 1..100 | JPEG 用 90（不看源文件原来的质量）；WebP 无损 | 0 或 101 报错，退出码 1 |
| serve `doc.save`、MCP `doc_save` / `doc_export` 的 `quality` | 1..100 | JPEG 90；WebP 无损 | 静默截到 1..100 |
| 引擎命令的 `quality`：`file.saveACopy`、`file.automate.batch`、`file.scripts.imageProcessor`（默认 8）、`file.automate.createDroplet`、`file.export.layersToFiles`、`file.export.layerCompsToFiles`、`file.export.artboardsToFiles`、`file.export.artboardsToPdf`（默认 10）；serve `doc.exportLayers`、MCP `doc_export_layers` 同样 | 0..12（Photoshop 档位） | `file.saveACopy` 沿用源文件的 JPEG 质量和 WebP 有损/无损，新建文档 JPEG 按 90 | 静默截断，大于 12 一律按 12，不报错 |
| `file.export.saveForWebLegacy` 的 `quality` | 0..100 | 60 | — |

0..12 档位换算成 JPEG 质量是 round(q/12×99+1)：0→1、6→51、8→67、10→84、12→100，和 CLI `--quality` 1/51/67/84/100 输出的文件逐字节相同。1400×837 的样图实测体积：q0 20,948 B、q6 106,386 B、q8 208,500 B、q10 244,528 B、q12 670,112 B；CLI `--quality 85` 是 247,302 B。按百分比习惯给引擎命令传 80，实际是最高质量，文件约为 85 的 2.7 倍。

WebP 带质量值就是有损（VP8），不带就是无损（VP8L），源文件原来是有损 WebP 也一样（`file.saveACopy` 例外，见上表）。

## 性能

- 每次调用一个进程，冷启动约 0.3 秒（小文档的 `run`）；1400×837 的 JPEG 转 PNG 约 0.5 秒。能合并的步骤放进同一条 `run`，几十步的交互式编辑用 serve。
- `batch` 每个文件开一个会话；文件很多时可以按文件拆成多个 CLI 进程并行，不要在一个会话里对同一文档并发跑任务。
- 滤镜和大半径模糊吃 CPU。交付尺寸比原图小时先缩小再跑重滤镜。
- `image.imageSize {"resample":"none"}` 只改 ppi，不重采样像素。

## 从源码构建

- 需要 Rust stable 1.95+。`cargo build --release -p photocraft-cli` 产出 `target/release/photocraft-cli(.exe)`；不带 `--target` 时路径里没有目标三元组。图像代码在调试构建里很慢，实际使用一律 `--release`。
- 官方构建带 `--features heif`（读 HEIC）。AVIF 编码在 `photocraft-codecs` 的 `avif` 特性里，官方构建没开，所以写 AVIF 报 `cannot be written in this build`。
- Windows 用 Rust 的 MSVC 工具链，并安装 Visual Studio 或 C++ Build Tools 的"使用 C++ 的桌面开发"工作负载（发行版 docs/development.md）。
- Windows 11 的智能应用控制可能拦截 Cargo 或构建出的程序，报 `An Application Control policy has blocked this file. (os error 4551)`；按微软的说明处理，或改用打包好的发行版。
- 报 `linker link.exe not found` 或 `link: extra operand …`：Git 的 `usr\bin\link.exe` 排在 MSVC 链接器前面。在"x64 Native Tools Command Prompt for VS"里构建，或先运行 `vcvars64.bat`，别让 Git 的 `usr\bin` 排在 MSVC 目录前（未验证：本机没有做源码构建）。
