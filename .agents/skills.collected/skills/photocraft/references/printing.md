# 打印与打印 PDF

> 核对版本：photocraft-cli 0.14.0；命令参数来自运行时注册表，路由与限制来自 `docs/printing.md`。打印只在 CLI 可用；serve、MCP、桌面控制通道按 `file.*` 规则拒绝。

## 能做什么

`file.print` 把扁平化后的文档渲染到**一页 PDF** 上：纸张、方向、位置、缩放、裁切/套准标记、说明文字、颜色处理都可设；然后交给打印机，或只写 PDF。桌面里的 File › Print 对话框和自动化命令共用同一套 `print_cmds` 排版。

打印不是“导出矢量 PDF”：页面是栅格化的，图层、蒙版、文字都按当前合成结果烘平。要每个画板一页用 `file.export.artboardsToPdf`；要单页扁平 PDF 也可以 `convert in.psd out.pdf`（没有打印版式/标记）。

## 命令

| 命令 | 用途 | 关键回执 |
|---|---|---|
| `file.print` | 打印或写打印 PDF | `{pdf, imageRect, command, sent, spooler, backend}`；`pdf` 只在给了 `output` 时非空 |
| `file.printOneCopy` | 用上一次 Print 设置打印一份；可覆盖任意 Print 参数 | 同 `file.print` |
| `file.printers` | 列系统打印队列 | `{printers:[{name,default}], default}`；0.18 实测每项还带 `server` 字段，别把它当队列名传给 `printer` |
| `file.print.printers` | 同上，带 `supported` 标记（Windows 为 true） | `{supported, printers}` |
| `file.print.page` | Windows：当前打印机的纸张、可打印区、DPI；可转方向 | `{printer, paper, printable, dpi, printerSettings?}`；`printerSettings` 只在传 `orientation` 时回 |

`file.printers` / `file.print.printers` 不打开文档；`file.print.page` 也不需要文档。`file.print` 和 `file.printOneCopy` 需要活动文档。

## 常用参数

参数名以注册表为准；`params.py --exact file.print` 随时可查。

| 参数 | 说明 |
|---|---|
| `printer` | 队列名（Windows/CUPS 都可不分大小写）；不给就用系统默认 |
| `copies` | 1..999，默认 1 |
| `paper` | `letter` `legal` `tabloid` `a3` `a4` `a5` `4x6` `5x7`，或 `[宽,高]`（pt） |
| `orientation` | `portrait` / `landscape` |
| `center` | 默认 true；关掉后用 `top`/`left`（英寸，从纸张左上算） |
| `scale` | 百分比，默认 100；`scaleToFit` 适配可打印区 |
| `printable` | 驱动可打印区 `[x,y,w,h]`（pt，从纸张左上）；Windows 原生打印读驱动自己的 |
| `colorHandling` | `printerManages`（默认）/`photocraftManages`/`noColorManagement`；`photocraftManages` 才用 `printerProfile`、`intent`、`bpc` |
| `cornerCropMarks` / `centerCropMarks` / `registrationMarks` | 裁切/套准标记 |
| `bleed` | 英寸；从图像边缘向内画的裁切线距离 |
| `description` / `labels` | 在页边打印说明/标签 |
| `emulsionDown` | 左右镜像，用于热转印等 |
| `output` | 打印 PDF 的路径；给了它之后 `send` 默认 false |
| `send` | 是否真的送印；`output` + `send:true` 才既写 PDF 又送印 |
| `printServer` | `host[:port]` 或 socket；指定后总走 IPP |
| `dryRun` | 渲染页面、报告等价命令，不 spool；只有给了 `output` 才写 PDF |

`printerSettings` 是 Windows 驱动的十六进制设置串；一般不要手写，用 `file.print.page` 拿。

## 自动化路线

**默认不安全：什么都不给会真的送印。** 实测 0.18：`file.print {}` 不给 `output`、不给 `dryRun` 时直接进打印队列（回 `sent:true, backend:"windows"`），只有在纸张/方向不匹配时才被拦下。要"只出 PDF 不碰打印机"，必须显式给 `output`，或显式 `dryRun:true`。无界面环境的可复现写法：

```sh
photocraft-cli run poster.psd \
  --cmd file.print \
  --params '{"paper":"a4","orientation":"portrait","scaleToFit":true,"cornerCropMarks":true,"bleed":0.125,"output":"proof.pdf","dryRun":true}'
```

- `dryRun:true` + `output` 会写出 PDF，`sent:false`，`backend:null`；适合 CI、评审、交付前的版式检查。
- 去掉 `dryRun`、保留 `output` 且不写 `send`：仍只写 PDF（`send` 默认 false）。
- 真的送印：`output` 可省，`send:true`，并显式给 `printer`；回执看 `sent`、`backend`（`lp`/`windows`/`ipp`/`portal`）、`spooler`。
- **什么都不给（`{}`）不是安全默认**：既没有 `output` 也没有 `dryRun` 时按 `send:true` 处理，实测 0.18 会真的进队列。脚本里凡是可能收到空参数的调用点，都要兜底补 `dryRun:true`。
- Windows 想确认纸张/可打印区：先 `file.print.page`，再按它的 `paper`/`printable` 传 `file.print`。
- `PHOTOCRAFT_NO_PRINT` 非 0 时 `file.print`/`file.printOneCopy` 拒绝 spool，`dryRun` 仍可写 PDF；CI 建议设置，避免误打。

**授权**：打印会真的出纸/占用打印机。未得到用户明确同意，只做 `dryRun` 或 `output` PDF；不要用 `file.printOneCopy` 复用用户上一次的打印机设置，也不要对用户的文档直接送印。

## 路由（桌面/CLI 的打印后端）

| 路线 | 条件 | 结果 |
|---|---|---|
| `craft-print`（`lp` / Windows spooler） | `lp` 在 PATH（macOS、非沙盒 Linux）或 Windows | 正常的系统打印 |
| CUPS over IPP | 没有 `lp`（如 Flatpak），或显式 `printServer` | 纯 Rust IPP 直接 `Print-Job` |
| Print portal | 没有打印服务器/没有打印机，或 `PHOTOCRAFT_PRINT_PORTAL=1` | 系统打印对话框 |
| Print to PDF | 给了 `output` | 写 PDF；只有 `send:true` 才继续 spool |

没有打印机/队列不可用时，错误会说明是加打印机还是改用 PDF。`file.printers` 无服务器时回空列表加 `note`。

## 与其它导出的区别

| 需求 | 用 |
|---|---|
| 打印预览、纸张/方向/标记/出血 | `file.print {"output":…,"dryRun":true}` |
| 单页扁平 PDF，不要打印版式 | `convert in.psd out.pdf` |
| 每个画板一页 | `file.export.artboardsToPdf` |
| 分层/可编辑母版 | PSD/PSB/`.pcraft`，不要打印 |
| 网页/屏幕交付 | PNG/JPEG/WebP，不要打印 |

## 验收

- `file.print` 回执：`pdf` 是否为你给的路径；`sent` 是否符合预期；`imageRect` 是否落在纸张内；`backend`/`spooler` 是否正确。
- PDF：文件存在、非空，以 `%PDF` 开头；用阅读器检查页数、纸张、方向、标记、出血位置、颜色是否符合预期（没有 PDF 页数解析器时至少看文件大小和打开结果）。
- 真打印：先 `dryRun` 看参数，再送一张；检查 `sent:true` 和队列回执。不要用“命令退出 0”代替“纸出来了”。
- 颜色：`colorHandling:"photocraftManages"` 才检查 `printerProfile`/`intent`/`bpc`；`printerManages` 由驱动负责，PDF 与纸面可能不同。

## 常见问题

| 现象 | 原因 | 做法 |
|---|---|---|
| `file.print` 在 serve/MCP/桌面报 ambient 拒绝 | 打印按 `file.*` 规则禁用 | 改用 CLI `run`；桌面只能人工 File › Print 或经 UI 对话框 |
| 没有 `output` 却期待 PDF | `pdf` 只在显式 `output` 时写出 | 加 `"output":"proof.pdf"` |
| `send` 默认 true 导致误打 | 只有 `output` 会把 `send` 默认成 false；只给 `printer`、或什么都不给（`file.print {}`）都会真的送印 | 自动化一律显式 `dryRun` 或 `output`+`send:false` |
| 纸张/方向不对 | Windows 驱动设置与参数不一致 | 用 `file.print.page` 读驱动纸张，再传 `paper`/`orientation` |
| 图像位置偏移 | `center` 与 `top`/`left` 混用，或 `scaleToFit` 与 `scale` 同时给 | 选一种定位方式；先看 `imageRect` |
| 打印颜色和屏幕不同 | 驱动色彩管理 | 需要可控时用 `photocraftManages` + 打印机 ICC，并做打样 |
| 没有打印机 | 系统队列为空 | 用 `output` 出 PDF，或让用户先安装打印机 |
