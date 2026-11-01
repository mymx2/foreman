# 动作、批处理、Droplet、变量数据组

> 核对版本：命令 id 与参数按 photocraft-cli 0.14.0 复核；行为描述写于 0.14.0。CLI 子命令的标志和退出码见 `cli.md`；serve、MCP 的传输和方法见 `automation.md`；入口选择见 `entrypoints.md`。

## 先选对自动化形态

| 需求 | 用 | 关键点 |
|---|---|---|
| 同一个会话里重复一组步骤，或把动作交给 Photoshop 同事 | 动作 / `.atn` | `actions.record`/`play`；`.atn` 无对应步骤要 `skipUnsupported` 或 `actions.toggle` 跳过 |
| 双击分发到同事机器 | Droplet | 先用 `file.automate.createDroplet` 生成；嵌套 action 会写入 `calledActions` |
| 一个目录顶层、同一组步骤、CI | CLI `batch` | 不递归、无命名模板；部分失败退出码 1 |
| 递归、命名模板、序号、显式路径数组 | `file.automate.batch` | 在 CLI `run` 里调；失败进 `errors[]`，整条 `run` 仍退出 0 |
| 已经在 serve 里打开文档，要逐步试 | serve `batch` | 只能经 `engine.execute` 和会话方法；`failed` 看 `result.failed` |
| 单文件一次性执行 | `run` | 每步一个 `--cmd`；能合并就别开新进程 |

## 步骤形状

动作、批处理、Droplet 共用一种步骤形状：

```json
[["image.adjustments.invert", {}], ["image.imageSize", {"width": 1200}]]
```

`actions.get` 回的 `steps`、CLI `batch --actions` 的输入、`.pcdroplet` 里的 `action.steps`、`file.automate.batch` 和 `file.automate.createDroplet` 的 `steps` 都是这个形状，可以直接互相搬。其他写法各处接受的情况：

| 写法 | CLI `batch --actions` | `file.automate.batch`、`createDroplet` | serve `batch` | MCP `command_batch` |
|---|---|---|---|---|
| `["<id>", {…}]` | 可以 | 可以 | ``step 0 needs `command` or `method` `` | 可以（实测，schema 里没写） |
| 裸 id `"image.adjustments.invert"` | 可以 | 可以 | 同上 | `-32602` |
| `{"command": "<id>", "params": {…}}` | 可以 | 可以 | 可以 | `-32602 unknown field` |
| `{"id": "<id>", "params": {…}}` | 可以 | 可以 | ``step 0 needs `command` or `method` `` | 可以（schema 的写法） |
| `{"method": "doc.save", "params": {…}}` | — | — | 可以，只有 serve 能在批里调会话方法 | — |

`createDroplet` 会把对象和裸 id 规范成 `[id, params]` 写进文件。CLI `batch --actions` 另外接受 `{"steps":[…]}`、`{"actions":[{name, steps}…]}`（动作集，多于一个动作时用 `--action` 选）、`.pcdroplet` 文件和 Photoshop `.atn` 文件。

同一输入下，手动逐条执行、`actions.play`、CLI `batch`、`droplet` 的产出逐像素相同（实测一例 invert + blur，RGBA sha256 一致）。

## 五种批处理对比

| | CLI `batch` | `file.automate.batch` | serve `batch` | MCP `command_batch` | `droplet` |
|---|---|---|---|---|---|
| 在哪跑 | CLI 子命令 | 只在 CLI `run` 里（serve、MCP、桌面按命令名拒绝） | serve 方法 | MCP 工具 | CLI 子命令 |
| 输入 | `--in` 目录顶层的可读图片，按文件名排序，非图片跳过 | `input`：目录或路径数组（数组保持原顺序） | 当前会话的活动文档 | 同 serve | 文件和目录，可混着传 |
| 子目录 | 不递归 | `includeSubfolders:true`：最多 32 层、100000 个文件，结果保留子目录结构 | — | — | 目录只取顶层 |
| 输出命名 | `<原文件名>.<扩展名>`，格式由 `--format` 或输入决定 | `naming` 模板（`{name}`、`{serial}`、`{date}`），留空保留原名 | — | — | `<原文件名>.<扩展名>` |
| 质量刻度 | `--quality` 1..100 | `quality` 0..12，超出静默截到 12 | 由各命令决定 | 同 serve | 生成时 `createDroplet` 的 `quality` 0..12 |
| 嵌套 `actions.play` | 动作集 JSON 整套加载；`.pcdroplet` 里的 `calledActions` 不加载 | 同一条 `run` 里录的动作，或 `calledActions` | 会话里的动作 | 会话里的动作 | 文件里的 `calledActions` |
| 失败报告 | stderr `FAIL  <输入>: <错误>`，stdout `N succeeded, M failed`，任一失败退出码 1 | `errors:[{file, error}]`，退出码仍是 0 | 顶层 `ok:true`，看 `result.failed`、`results[i].error` | `isError:false`，看文本里的 `failed` | 每个文件 `ok    <输出>` 或 `FAIL  <输入>: <错误>`，任一失败退出码 1 |
| 停不停 | 坏文件跳过，其余照跑 | 同左 | `stopOnError` 默认 true | `stop_on_error` 默认 true | 同 CLI `batch` |
| 步数上限 | — | — | 256 | 256 | — |
| 事务 | 否，先写出的文件留着 | 否 | 否，成功的步骤不回滚 | 否 | 否 |
| 已有输出 | 覆盖上次的同名文件；同一轮两个输入产出同名文件时后者 `FAIL … not written: … already holds the result of … from this run (same output name)` | 同名结果保留第一个，其余进 `errors`；模板解析到某个输入文件本身时整批拒绝 | — | — | 同 CLI `batch` |

- CLI `batch` 的 `--in` 与 `--out` 是同一目录时被拒，除非加 `--in-place`；它没有 `--naming`、`--startingSerial`，要命名模板就在 `run` 里调 `file.automate.batch`。标志细节见 `cli.md`。
- 按尺寸和格式转一批图还可以用 `file.scripts.imageProcessor`（只在 CLI `run`，`quality` 0..12，默认 8）。
- serve `batch` 和 MCP `command_batch` 不遍历目录，规则细节见 `automation.md`。

## 批次交付纪律

PhotoCraft 的各种批处理都不是事务：失败的文件、步骤留在目录里，部分成功容易被当成整批成功。按阶段分两档：

- **中间迭代**（试参数、调版式、看效果）：只查 `errors[]` 是否为空、文件数对不对、抽样看尺寸和非空，够用。别在迭代阶段跑全套校验，`info` 每次约 0.3 s 冷启动，100 张就是 100 次进程开销。注意 `errors[]` 空不等于画面对：`image.crop` 越界不报错，会静默产出纯白小图并且计入成功（实测 0.18，0.14 未复核）；裁剪、缩放这类几何命令要抽样看像素或尺寸。
- **最终交付**（模板出图、电商主图、印刷文件）：走下面四条完整纪律。

1. **冻结输入快照**。开始前记录工单、配置、模板、源图的 SHA256（用系统 `sha256sum` / `Get-FileHash` 或 Python `hashlib.sha256`）；执行前复核源文件未变，变更即拒绝启动。复制输入到工作目录时核对复制前后哈希一致，不一致即视为复制失败重来。
2. **先 stage 后整组发布**。stage 目录必须是本次新建、且与交付目录分开（不要复用用户已有目录）；逐个产物校验（路径、尺寸、模式、SHA256）通过后整组搬进交付目录，发布前先查同名冲突，不静默覆盖既有文件；任一失败即整体回滚，回滚只清空本次新建的 stage 目录，交付目录里既有的其他文件不动。
   - CLI `batch --out <stage>` 和 `file.automate.batch` 的 `output:<stage>` 都会自建缺失目录，可以直接指过去。
   - serve 出图要自己建目录：`doc.save` 不建父目录，serve 也没有 mkdir 方法；stage 及各级子目录由调用方 `os.makedirs` 建好（`doc.exportLayers`、`doc.exportDataSets` 除外，它们会自建）。
   - 发布本身没有现成脚本，用 `shutil.move` 之类整组搬；搬之前逐个 `os.path.exists` 检查目标，任一重名就先停下问用户。
3. **manifest 与实际文件比对**。批次记录或 manifest 里声明的路径和 SHA256 必须与落盘文件逐一核对；只信回执不够。`trim_export.py` 的 manifest 是切图语义（trimBox、倍率、`sourceSha256`），不能直接拿来验收模板出图，要自建一份最小记录，字段够用即可：

```json
{"items": [{"path": "out/A1.png", "sha256": "…", "bytes": 12345,
            "width": 800, "height": 800, "mode": "RGB"}]}
```
4. **失败目录写拦截标记**。第 2 条管的是发布前就失败（stage 未提交）。发布中途失败（一部分已搬进交付目录）时，先把已搬的文件按第 2 条回滚移除，再走本条的标记流程；如果产物已发布完、事后才发现某场景失败，不要再删已发布文件，改为写显眼的失败标记（如 `DO_NOT_UPLOAD.txt`），列出失败项与原因。
   - 一商品一子目录时写两层：批次根目录一份汇总（列相对路径），每个受影响子目录各一份。
   - 标记只列失败项，不改动目录里既有的其他文件；同名标记直接覆盖为最新一次结果。
   - 重跑通过后删掉标记；没删就当作仍不可交付。

批次开跑前和失败时的两条纪律：

- **开工先清上一批的遗留**：上一批的验收拼图、批次汇总、临时 stage 目录都要先处理掉，旧汇总先备份再删——留着会让"这次成功"和"上次成功"混在一起，运营分不清哪些是本批产物。
- **清之前先确认清的不是源**：待清理的目录里不能有原图、模板、工单。一旦源图恰好落在输出目录里，清目录就等于删源，而且不可逆。判断依据看目录内容而不是路径猜：有本工具写的标记（批次记录、结果文件）才认定是自己建的目录；同名但没有标记的，先挪到垃圾目录再说，不要直接删。输出目录也别选在模板目录或源图目录下面。
- **失败默认即停**：一个商品失败就取消还没开始的作业，写完整批次记录（成功/失败/跳过各几项、原因）、退出码非 0、不出验收拼图；不要产出一张"看起来全绿"的拼图。要跑完再汇总就显式开关（如 `--continue-on-error`），并在记录里标明这次是"跑完汇总"模式。
- **同一输出目录不要并发写**：多个 agent 或多次启动同时往一个交付目录搬产物，会互相覆盖或抢锁。要并发就按目标目录或商品分片，每个分片一个进程；需要防重复启动时用独占锁文件（`O_CREAT|O_EXCL` + 写入自己的 PID/随机 token），释放时只删自己创建的那个锁——别按"存在就删"，那是删别人的锁。

以上四条是包装层纪律，不改变引擎行为：PhotoCraft 的批处理本身仍会静默覆盖同名文件、失败文件仍留在目录里；纪律的价值是让这些行为在交付前被拦住。

## 动作录制与回放

| 命令 | 参数 | 回复 |
|---|---|---|
| `actions.record` | `{name?}` 新建（默认名 `Action N`），或 `{action}` 追加到已有动作 | `{action, index}` |
| `actions.stop` | `{}` | `{action, steps:<步数>}`，只是计数 |
| `actions.get` | `{action}`（名字或序号） | `{name, steps:[[id, params]…], disabled, dialogs, set, color}` |
| `actions.list` | `{}` | `{actions:[{name, steps:<步数>, set}], recording}` |
| `actions.play` | `{action, from?}` | `{action, ran, failed?:{step, id, error}}` |
| `actions.insert` | `{action, id, params?, at?}` | `{action, step, id, steps}` |
| `actions.toggle` | `{action, step?, enabled?}` | `{action, disabled:[…]}` |
| `actions.delete` | `{action, step?}` | `{deleted}`，或带 `step` 时 `{action, deletedStep, steps}` |
| `actions.move`、`actions.rename`、`actions.setColor`、`actions.assignSet`、`actions.dialog` | 用 `photocraft-cli commands --json --filter actions.` 查 | 调整步骤顺序、改名、按钮颜色、所属集合、对话框开关 |
| `actions.conditional` | `{if, then, else}` | `{if, holds, played, action?, ran?, failed?}` |
| `actions.stopMessage` | `{message, allowContinue?}` | 作为步骤使用，见下 |
| `actions.save` | `{path?, set?, action?, skipUnsupported?}` | `{set, actions, steps, bytes, skipped, path 或 data}` |
| `actions.load` | `{path? 或 data?, set?, replace?}` | `{set, actions, steps, unsupported, functionKeys, warnings}` |

`step`、`from`、`failed.step` 都从 0 数。

录制：

1. 先有文档（`doc.open`、`doc.new` 或 CLI 的输入文件），再 `actions.record {"name":"…"}`。
2. 执行要录的命令。查询（`document.inspect`、`actions.get` 等）和动作编辑命令不会进步骤。
3. `actions.stop` 只回步数，用 `actions.get` 取步骤。

- 选择图层按名字记：`["layer.select",{"name":"dup","occurrence":0}]`。重名时带从 0 开始的 `occurrence`，按文档遍历顺序（实测两个同名图层里靠下的是 0，而 `document.inspect` 是从上往下列的）；用 id 选的也记成名字。回放时名字或 occurrence 对不上就中止，跨文档复用要保持层名和层序一致。旧录制里按 id 记的步骤要重录。
- 录制中播放另一个动作，只记一步命名调用 `["actions.play",{"action":"<名字>"}]`，回放时按名字重新查找。

回放：

- `actions.play` 有步骤失败时仍回成功，失败写在 `failed` 里，后面的步骤不跑，已跑的每步留一个历史步。CLI `run` 把它变成 ``error: `actions.play`: action `F` step 1 failed: …``，退出码 1（这句里的步号从 1 数）；serve `batch` 里这一步算 completed（`failed:0`）。serve 和 MCP 里每次 play 都要检查 `result.failed`。
- 嵌套 `actions.play` 最多 16 层（实测第 17 层报 `action nesting exceeds 16 levels`）；自己调自己报 ``recursive action call to `S` ``；找不到被调的动作报 ``no action named `X` ``；子动作失败会停掉父动作。
- `actions.toggle` 关掉的步骤 `actions.play` 会跳过；但 `actions.get` 的 `steps` 里仍有它们（序号另列在 `disabled`），把步骤交给 `file.automate.batch`、CLI `batch` 或 `createDroplet` 之前自己删掉。
- `actions.stopMessage {message, allowContinue:false}` 作为步骤时停下整个动作，play 回 `failed:{error:"stopped by the action: <message>", …}`；`allowContinue:true` 在无界面回放里直接继续。单独执行它也报这句。
- `actions.photoshopStep` 是 `.atn` 里 PhotoCraft 没有对应命令的步骤的占位，回放必定失败：``Photoshop step "<name>" (<event>) has no PhotoCraft equivalent yet; switch it off in the Actions panel to skip it``。用 `actions.toggle` 关掉即可跳过；`actions.save` 会原样写回。
- `actions.dialog` 只打标记，无界面回放用录制的参数。
- `actions.conditional` 按当时的文档和活动图层求值，播放对应的动作；条件名写错时报错并列出全部可用条件（`always`、`landscape`、`modeIsRGB`、`hasSelection`、`isSmartObject` 等）。

动作名与持久化：

- 动作名在会话里全局唯一。`actions.load` 遇到重名把新动作改名为 `<名字> 2`、`<名字> 3`；`set` 参数改集合名。
- CLI、serve、MCP 的动作列表只在本进程内有效；桌面存进配置目录的 `Presets/actions.json`，所以试验时用临时 `PHOTOCRAFT_CONFIG_DIR`。

### .atn

- `actions.save {}` 把所有动作存成集合 "PhotoCraft Actions"，不带 `path` 时回 base64 `data`（就是 `.atn` 文件的字节）；`{action}`、`{set}` 只存一个动作或集合。会话里没有动作时报 `there are no actions to save`。
- 有步骤在 Photoshop 里没有对应事件（例如 `file.automate.fitImage`）时默认失败：``step 1 of `Fit` (`file.automate.fitImage`) has no Photoshop equivalent; pass "skipUnsupported": true to leave it out``。加 `skipUnsupported:true` 会去掉这些步骤，回复的 `skipped` 列出 `{action, id, step}`。
- serve、MCP、桌面里 `actions.save {path}`、`actions.load {path}` 按命令名拒绝，用 `data` 往返，自己解码 base64 落盘；CLI `run` 里 `path` 可用。
- `actions.load` 把 PhotoCraft 无法执行的 Photoshop 步骤变成 `actions.photoshopStep`，没有文档效果的步骤（切换工具等）导入后是关闭状态。
- `.atn` 也能直接交给 CLI `batch --actions`：不支持的步骤先在 stderr 警告，然后每个文件都 FAIL。

## file.automate.batch

只能在 CLI `run` 里调，`run` 需要一个文档，给一个 1×1 的就行：

```sh
photocraft-cli run --new '{"width":1,"height":1}' --cmd file.automate.batch --params '{
  "input": "in", "output": "out", "steps": [["image.adjustments.invert", {}]],
  "format": "png", "naming": "{name}_{serial}", "startingSerial": 7}'
```

| 参数 | 说明 |
|---|---|
| `input` | 目录或路径数组；目录里的非图片被跳过 |
| `output` | 输出目录，不存在会建 |
| `steps` | 步骤，形状见开头 |
| `format` | `same`（默认）、`png`、`jpg`、`psd`、`tiff` 等 |
| `quality` | 0..12，超出静默截到 12（传 80 等于传 12） |
| `includeSubfolders` | 见对比表 |
| `naming`、`startingSerial` | 见下 |
| `tiffLayers`、`tiffCompression`、`jpegFormat`、`tgaBits`、`dpxBits`、`ddsCompression`、`ddsMipmaps` | 格式选项；JPEG 扫描、TIFF 压缩、DDS 压缩/mip 链都在这里传 |
| `calledActions` | `[{name, steps}…]`：`steps` 里 `actions.play` 调用的动作；默认用会话里的动作 |

- 回复 `{files, errors}`。单个输入失败进 `errors:[{file, error}]`，整条 `run` 退出码仍是 0，要检查 `errors`。
- 嵌套动作：同一条 `run` 里先录的动作可以直接被 `actions.play` 调用；新进程里没有就每个文件都报 ``invalid parameters for `actions.play`: no action named `Inv` ``，这时用 `calledActions` 把动作一起传进去。

命名模板（扩展名自动加）：

| 占位符 | 值 |
|---|---|
| `{name}` | 输入文件名去掉最后一个扩展名 |
| `{serial}` | 输入顺序加 `startingSerial`（默认 1），至少补到三位；999 之后是 1000，不回绕 |
| `{date}` | 批处理开始时的 UTC 日期，`YYYY-MM-DD`（本地已是次日时仍是 UTC 当天） |

- 失败的输入也占一个序号，后面的名字不前移。
- 输入文件名里的花括号按字面处理。
- 下列错误都在写任何文件之前报出，什么都不写：未知占位符 `naming: unknown token {bogus}; use {name}, {serial} or {date}`；花括号不配对（`unclosed token`）；路径分隔符或保留字符、超过 255 个 UTF-8 字节；`startingSerial` 不在 1..4294967295，或加上输入数后溢出（`startingSerial plus the input count exceeds 4294967295`）；模板会覆盖某个输入文件（`naming would replace an input file: in/a.png; choose a different destination or template`）。
- 两个结果同名（包括只差大小写）时保留第一个成功的，其余进 `errors`。

## Droplet

1. 在 CLI `run` 里生成（其他入口按命令名拒绝）：

```sh
photocraft-cli run --new '{"width":1,"height":1}' --cmd file.automate.createDroplet \
  --params '{"path":"web.pcdroplet","steps":[["image.imageSize",{"width":1200}]],"format":"jpg","quality":10}'
```

   参数：`path`（`.pcdroplet`）、`steps`、`name?`、`output?`、`format?`、`quality?`（0..12）、`shim?`。回复 `{path, shim, steps}`；Windows 上 `shim` 是 `null`，Unix 上默认另写一个调用 `photocraft-cli droplet` 的 `<name>.command`。
2. 运行：`photocraft-cli droplet <file.pcdroplet> <文件或目录>… [--out <dir>]`。

- 文件是 JSON：`{"photocraftDroplet":1, "name", "action":{"name","steps"}, "options":{"format"?, "output"?, "quality"?}, "calledActions"?}`。缺 `photocraftDroplet` 键报 ``invalid parameters for `file.automate.runDroplet`: <文件> is not a PhotoCraft droplet``，所以用 `createDroplet` 生成，别手写。
- `steps` 里有 `actions.play` 时，`createDroplet` 把会话里被调用的动作写进 `calledActions`，droplet 单独运行也找得到。手写的 droplet 漏了这个键，运行时报 ``no action named `Inv` ``。
- 输出目录优先级：`--out` > 文件里的 `options.output`（相对当前目录）> `<输入目录>/droplet-output`。
- 目录输入只取顶层文件；传进来的文件不管来自哪个目录都平铺到同一个输出目录。
- CLI `batch --actions <droplet>` 只读 `action.steps`，不加载 `calledActions`，嵌套的 `actions.play` 会失败。这种 droplet 用 `droplet` 子命令跑。

## 变量与数据组

链路：

1. 定义变量：`image.variables.define {defs:[{name, layer, type, method?, align?, clip?}]}`。`type` 是 `visibility`、`textReplacement`、`pixelReplacement`；像素替换的 `method` 是 `fit`（默认）、`fill`、`asIs`、`conform`，`align` 默认 `center`，`clip` 默认 false。回 `{defs, dataSets, active}`，`variables.list {}` 回同样的结构。
2. 填数据组，二选一：
   - `image.variables.dataSets {dataSets:[{name, values:[{variable, kind, value}]}], append?}`，`kind` 是 `visibility`、`text`、`pixels`。
   - 导入 CSV：CLI 用 `file.import.variableDataSets {path, delimiter?}`，serve 用 `doc.importDataSets`，MCP 用 `doc_import_data_sets`，都回 `{imported:<套数>}`。
3. 单独应用一套：`image.applyDataSet {name 或 index}` → `{applied, index}`，一个历史步。
4. 逐套导出扁平图：CLI 用 `file.export.dataSetsAsFiles {dir, format?, dataSets?, naming?}`，serve 用 `doc.exportDataSets`，MCP 用 `doc_export_data_sets`（参数 `data_sets`），都回 `{files, count}`。

CSV 规则：

- 表头是变量名，必须和 `defs[].name` 完全一致（区分大小写）。对不上的列被静默丢掉：表头写 `Caption` 而变量叫 `caption` 时，导入照样成功，但这套数据的 `values` 是空的。
- 第一列只有在表头为空或是 `DataSet`（不分大小写，`dataset` 也行）时才当作数据组名；否则各套叫 `Data Set 1`、`Data Set 2`…，那一列（比如 `Name`）被当作变量列，没有同名变量就被丢掉。
- 每次导入替换全部数据组，不追加；要追加用 `image.variables.dataSets {append:true}`。
- 可见性的值写 `true` / `false`；别的字符串（如 `yes`）实测被读成 true。
- 像素替换的值是图片路径，规则见下。

导出命名：

- `naming` 的占位符：`{name}`（数据组名，空格变下划线：`Data Set 1` → `Data_Set_1.png`）、`{index}`（从 1 起补三位：`001`）、`{document}`（文档名去扩展名）。不传 `naming` 等于 `{name}`；扩展名来自 `format`，默认 png。
- 两套数据解析到同一个文件名时在写盘前整批拒绝：``data sets `Data Set 1` and `Data Set 2` resolve to the same output `same.png`; include {index} in `naming` to use distinct filenames``。
- 目标文件已存在：serve、MCP 报 `AlreadyExists` 不覆盖；CLI 静默覆盖。

像素替换：

- 加 `clip:true` 才会把图片裁在图层原来的框里；默认 `clip:false` 时 `method:"fill"` 的图片会溢出画框，盖住旁边的文字。
- 路径解析：CLI 里相对路径相对"已保存文档所在的目录"，文档没存过就报 `the image <路径> is not opened: the path is relative and the document has not been saved`。serve、MCP 里相对路径一律报这句，文档是从根目录打开的或刚存过盘也一样。
- 0.14 起 `image.applyDataSet` 和 `doc.exportDataSets` 的像素路径按 ambient 规则判定：serve/MCP 里连绝对路径也会被拒，旧版“读根外图片”的缺口已关闭；像素替换导出要在 CLI 里跑，或先把图片放进可信工作流。CLI 仍是本地可信模式，不可信 CSV 仍可能让进程读到你给它的文件。
- serve、MCP、桌面里 `image.applyDataSet` 应用含像素替换的数据组会被按命令名/参数拒绝；只有文字、可见性的数据组可以单独 apply。CLI 里都可以。

保存：`.pcraft` 保存变量定义和数据组；PSD 不保存，重开后 `variables.list` 为空。
