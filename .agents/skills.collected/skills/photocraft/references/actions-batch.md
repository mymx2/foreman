# 动作、批处理、Droplet、变量数据组

> 核对版本：命令 id 与参数按 photocraft-cli 0.19.0 实测（`check_docs.py`）；行为描述来自 0.10.0–0.18.0 的实测记录，0.19.0 的复核项见 `upgrading.md`。CLI 子命令的标志和退出码见 `cli.md`；serve、MCP 的传输和方法见 `automation.md`；入口选择见 `entrypoints.md`。

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

- **中间迭代**（试参数、调版式、看效果）：只查 `errors[]` 是否为空、文件数对不对、抽样看尺寸和非空，够用。别在迭代阶段跑全套校验，`info` 每次约 0.3 s 冷启动，100 张就是 100 次进程开销。注意 `errors[]` 空不等于画面对：`image.crop` 越界不报错，会静默产出纯白小图并且计入成功（实测 0.18）；裁剪、缩放这类几何命令要抽样看像素或尺寸。
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

## 成品区固定内容校验

模板批量出图每单都是新产物，没有 before 可 diff：`info`、文件哈希、预览图能证明生成了、没退回旧版，证明不了固定区域里画的是对的；预览图还得靠人看，不能当可重复门禁。全图 diff 对无关变化过敏，也定位不到具体区域。内容由模板决定、每单必须一致的区域（品牌角标、认证字样、固定标语、印章）另做一层墨迹校验，不做全图相似度。

**选区域**：只选不随工单变的固定内容，一两处就够。窗口默认取模板图层 bounds；人工框定必须在标定前冻结并记 `window_source: hand-fixed`，不允许按产物重算窗口——按产物重算会让 `bbox` 检查恒为过。金标墨迹框只在标定时用来记 `ink_bbox_baseline`，不能当窗口。

每条记录固定字段（形状写死）：`name`、`layer`（`{name, type, bounds}`，`type` 用于模板对账）、`bbox`（窗口，`[x,y,w,h]`）、`window_source`（`template-layer | hand-fixed`）、`ink_bbox_baseline`（四边内缩量 `[left,top,right,bottom]`，非负；紧贴墨迹为 `[0,0,0,0]`）、`bbox_tolerance`（默认 1）、`template_tolerance`（默认 1，模板对账用）、`fill_range`（`[low,high]`）、`saturated_above`、`reference_rgb`（`[r,g,b]`）、`color_threshold`、`ink_threshold`、`quadrants`（四象限金标 `[q1,q2,q3,q4]`）、`quadrant_min_ratio`（由金标两向实测取得，不设默认）、`adjacent_layers[]`（`{name, bounds}`）；表级带 `version`、`template_sha256`；每条可选 `canvas`（`[w,h]`，多个非空值必须一致）。失败消息固定前缀 `[<stage>/<status>/<code>]`，并带 `版本=<v> 模板=<sha12> 表内=<sha12>`，才分得清“图错了”和“表过期了”。

`observed` 定义：`[ink_left-win_x, ink_top-win_y, (win_x+win_w)-ink_right, (win_y+win_h)-ink_bottom]`；四边都是内缩量，越大表示墨迹离边越远。

**判定**：先跑自建 `assert_png(png, canvas?)`：`im.load()` + `getcolors(maxcolors=2)`；给了 `canvas` 时再比 `[w,h]` 与 `RGB` 模式。失败直接 `error`，不进墨迹状态机。`canvas` 省略时只做解码与纯色，跳过尺寸与模式；尺寸/模式样本必须带 `canvas`。墨点按亮度掩膜取（`ink_threshold`，通道加权求和低于阈值即算墨，不按精确色相等——抗锯齿和压缩会让边缘变异）。状态闭集合，非 `pass` 即失败，调用方只认一个失败谓词。判定顺序固定：error → missing → saturated → bbox → spread → fill → color → quadrant → pass。对账与像素共用闭集，但 findings 带 `stage: reconcile | pixel`；同一 status 在两阶段含义不同，报告必须带 stage。

| status | 判据 | 抓什么 |
|---|---|---|
| error | 解码失败、画布不符、锚点窗口越出画布、表为空或缺字段、整幅纯色 | 半截文件、配错模板 |
| missing | 像素阶段：窗口内墨点为 0；对账阶段：层/相邻层缺失（`stage=reconcile`） | 漏层、被整块盖住 |
| saturated | 墨点占比高于 `saturated_above` | 只剩色块、内容被顶掉 |
| bbox | 墨迹四边内缩量与 `ink_bbox_baseline` 的逐边差 > `bbox_tolerance` | 整体位移、缩放 |
| spread | 窗口外 1px 带三面以上有墨，且每面至少 2 个墨点 | 外发光、描边漂移、遮罩错位 |
| fill | 墨点占比不在 `fill_range`；高于上限但未到 `saturated_above` 也算 fill | 描边变细、内容被部分擦掉、墨块变厚 |
| color | 墨点平均色与参考色的欧氏距离超阈值 | 换色、滤镜、模式错 |
| quadrant | 2×2 象限墨点低于金标 × `quadrant_min_ratio` | 角部被裁、被遮一角 |
| pass | 以上都不命中 | 成品通过 |

表加载校验：`fill_range` 下限 < 上限 < `saturated_above`，违反即 `error` / `config`；`window_source=template-layer` 时 `bbox` 必须等于 `layer` 的 `bounds`，否则 `error` / `config`；表内 `layer` 的 `type` 与当前层 kind 不一致即 `error` / `kind-changed`。`saturated_above < 实心块 fill` 在标定阶段确认，不在加载期。

code 词表（status 内的细分，不扩 status）：missing = ink-missing | layer-missing | adjacent-missing；saturated = ink-saturated；bbox = bbox-shift | bounds-drift | adjacent-drift | overlap；spread = effect-spread；fill = fill-out-of-range；color = color-drift；quadrant = quadrant-crop；error = config | decode | size | image-blank | bbox-range | kind-changed | sha-mismatch；pass = ok。

外侧带按四边分别统计，只有三面以上有墨、且每面至少 2 个墨点才判 `spread`——整体平移 1px 只沾两侧，单像素抗锯齿不算一面，与 `bbox` 容差互补。带内排除已冻结的相邻层 bounds（`adjacent_layers`），按冻结值排除，不靠放宽窗口解决。

**标定**（表里的数一律来自实测）：拿一份人工确认合格的产物当金标，记下每处 fill、墨点平均色、四象限与四边带墨数、四边 `ink_bbox_baseline` → `ink_threshold` 取背景亮度与墨色亮度的中点并记录 → 参考色取实测均值，不用设计稿名义色（名义色与实测色可能差出可观色距，按名义色定阈值余量很容易一次吃完）→ 色距阈值取“实测 + 余量”，同时拿一份明显偏色的坏样本反证仍能判失败 → `saturated_above` 定在 `fill_range` 上限之上、实心块 fill 之下（建议留 0.02 间隔；与 `saturated_above < 实心块 fill` 冲突时以后者优先），并确认 `saturated_above < 实心块 fill`；`quadrant_min_ratio` 由“1px 抖动不误报、裁掉一角必报”两向实测取得，不设默认值 → `bbox_tolerance` / `template_tolerance` 默认 1，记录实测取整误差 → 逐条造样本验红。

**测试矩阵分两栏**：

- 必须通过（假阳性哨兵）：基线（含非零 `ink_bbox_baseline` `[3,4,3,4]`）、dx=1、dy=1、1px 抖动、相邻层墨迹落在窗口外 1px 带内（排除后 pass）、外侧带 2 面有墨、3 面各 1 个孤立墨点、空白相邻区、全部省略 `canvas`。
- 必须失败（每条写期望 status / code）：dx = `bbox_tolerance` + 1、dy = `bbox_tolerance` + 1、负 dx/dy、只移一处、缺墨、明显偏色、色距 = 阈值 + 2、fill 略低于下限、fill 略高于上限、fill = `saturated_above` + 0.01、空锚点表、缺 `version` / `template_sha256`、画布尺寸少 1px（带 `canvas`）、锚点间 `canvas` 不一致、半截 PNG（有效 IHDR + 截断 IDAT，`open` 成功、`load` 失败）、纯色 PNG、四角内侧挖除（保持墨迹外接框不动，挖除量小于 fill 下限余量）、外侧带 3 面 / 4 面有墨、shift=1 + halo、非零 `ink_bbox_baseline` + dx=2。
- 边界样本留在套件里：色距 = 阈值 ± 2（分别断言 color / pass）；fill = 下限 ± 0.01（下方 fill、上方 pass）、上限 ± 0.01（下方 pass、上方 fill，前提是未到 `saturated_above`）；`saturated_above` ± 0.01（上方 saturated、下方 fill）；`quadrant_min_ratio` ± 0.01（让 ±0.01 至少对应 1 个墨点，即金标该象限 ≥ 100；下方 quadrant、上方 pass）；`bbox_tolerance`：容差 pass、容差 + 1 fail；`ink_threshold` 掩膜单测：同一窗口，阈值 `T+1` 时 ink 计数 1，`T-1` 时 0；锚点级 pass/missing 另用 2×2 合成窗口，配套给出 `fill_range`、`reference_rgb`、`quadrants`。只放“明显偏色”“实心块”钉不住阈值，阈值放宽后仍然全绿。

| 样本 | 期望 status | 期望 code |
|---|---|---|
| 基线（含非零 baseline）、dx=1、dy=1、1px 抖动、相邻层带内排除后、外侧带 2 面、3 面各 1 个孤立墨点、空白相邻区、全部省略 `canvas` | pass | ok |
| 缺墨 | missing | ink-missing |
| fill = `saturated_above` + 0.01 | saturated | ink-saturated |
| dx/dy = `bbox_tolerance` + 1、负向、只移一处、非零 baseline + dx=2 | bbox | bbox-shift |
| 外侧带 3 面 / 4 面有墨、shift=1 + halo | spread | effect-spread |
| fill 低于下限、fill = 上限 + 0.01（未到 `saturated_above`） | fill | fill-out-of-range |
| 色距 = 阈值 + 2 | color | color-drift |
| 四角内侧挖除 | quadrant | quadrant-crop |
| 空锚点表、缺字段 | error | config |
| 缺 `version` / `template_sha256` | error | config（消息用 `版本=? 模板=? 表内=?`） |
| 画布少 1px、模式不是 RGB（均带 `canvas`） | error | size |
| 锚点窗口越出画布（带 `canvas`） | error | bbox-range |
| `canvas` 不一致 | error | config |
| 半截 PNG、纯色 PNG | error | decode / image-blank |

这套矩阵是技能文档里的验收口径；落地第一处实现时必须逐条转成用例，只留在文档里会被跳过。

**断言口径**：`fill` 落在 `fill_range`、色距 ≤ `color_threshold`、`|observed_inset - ink_bbox_baseline| ≤ bbox_tolerance`，不只断言“无失败项”。失败文本固定前缀 `[<stage>/<status>/<code>]`，并带 `版本=<v> 模板=<sha12> 表内=<sha12>`；接线测试断言这些片段。`sha-mismatch` 样本用两个不同的已知 SHA，断言完整字面且两者不相等；缺字段时用 `版本=? 模板=? 表内=?`。

**插在哪**：在 stage 文件上验过再搬进交付目录（第 2 条），坏图不落成品路径、不进验收拼图；校验挂在产出成品的那个函数上，不要只挂某个入口的预检——同一模板常有预检、单张、场景子命令几套入口，绕过预检的照样产成品。通用接线纪律见 `psd-workflow.md` 2.6 的「验收断言要接线，并且先见红」；本检查额外要求：每条产出路径一条用例、`assert not out.exists()`、非空锚点表 + 真实坏图、`match` 到具体 status/code；模板对账同理。逐张跑，不抽样；耗时不可接受时先优化实现，不改判定频率。

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
