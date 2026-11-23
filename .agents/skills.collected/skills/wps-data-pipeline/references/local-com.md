# WPS 表格 COM 动作目录（本地文件）

本文件只列本技能用得到的动作，按用途分组；每条都标了能力状态。

标签只有四类，写成 `来源·结论`：

| 标签 | 含义 | 引用前必须确认 |
|---|---|---|
| `实测·可用` | 本机跑通过或已复现可用 | 能指向可执行复验命令，或指向本文件带复验命令的表行 |
| `实测·不可用` | 本机复现过失败 | 同上；拿不出复验方式的降级为 `推断` |
| `文档·未测` | 官方文档或上游参考实现里有，本机未跑 | 注明文档/代码位置；改关键路径前先小范围试一次 |
| `推断` | 无文档依据，靠机制推理 | 不得作为交付依据 |

「实测」不是修辞：凡出现处都要能指向一条可执行复验命令；**脚本未暴露入口的 action 例外**，须在该行注明「脚本无入口」。

本文件的「本机」= WPS 12.1.0.29690 / Python 3.13 / pywin32。`文档·未测` 可以照着写代码，但不能拿来当「实测能用」报给用户。

**复验锚点**：下表里**脚本入口覆盖的** `实测·可用` 行由这一组命令覆盖，怀疑失效时按顺序跑一遍，不要逐行重测。以下命令在**用户工作目录**执行，脚本走绝对路径 `"$SKILL/scripts/wps_com.py"`（`$SKILL` 指技能安装目录）——在技能目录里跑会把 `data/`、`out/` 造进安装目录：

```bash
python "$SKILL/scripts/wps_com.py" ping                                     # 0 则对象模型通
python "$SKILL/scripts/wps_com.py" sheets --file 报表.xlsx                   # 表名与张数
python "$SKILL/scripts/wps_com.py" read   --file 报表.xlsx --sheet 明细 --range A1:F5 --format tsv
python "$SKILL/scripts/wps_com.py" write  --file 报表.xlsx --sheet 明细 --json '[["x"],[1]]' --apply --force   # --force 覆盖上次的副本；回读应 verified: true
python "$SKILL/scripts/wps_com.py" pivot  --file 报表.xlsx --source "明细!A1:D200" --rows 地区 --values "金额:sum"
python "$SKILL/scripts/wps_com.py" export-pdf --file 报表.xlsx --out 报表.pdf --force   # 查 %PDF- 与文件大小
```

脚本没暴露入口的那几个 action，这六条盖不住：`getFormula` 用上面 `read` 加 `--formulas` 就能看；`setFormula` / `autoFilter` / `setCellStyle` / `createChart` 在 2026-11-23 由直接 COM 调用验证，脚本无子命令入口，复验要自己写 pywin32 调用，别指望这几行命令。

任一命令以非零退出码失败，先看主文件退出码表，再判断是「能力没了」还是「这次参数不对」——后者不算复验失败。

Word / PPT / 云文档相关 action 不在本技能职责内，未列入。

## 动作名不等于命令

下表左侧是 COM 动作名（对象模型里的能力），右侧是 `scripts/wps_com.py` 实际暴露的子命令。**脚本只封装了 6 个子命令**，其余动作需要自己写 COM 调用，没有现成命令行入口——照着 action 名去找命令会找不到。

| 动作 | 脚本入口 |
|---|---|
| getAppInfo / ping | `wps_com.py ping` |
| getSheetList | `wps_com.py sheets` |
| getRangeData / getCellValue | `wps_com.py read` |
| setRangeData / setCellValue | `wps_com.py write` |
| createPivotTable | `wps_com.py pivot` |
| convertToPDF | `wps_com.py export-pdf` |
| cleanData / setCellFormat / setCellStyle / setBorder / copyFormat / createChart / setFormula / autoFilter | **本期脚本未暴露**，需自行调用 COM |

## 对象层级速查

```
Application  (ProgID: Ket.Application，回退 ET.Application)
├─ Version / Name / Visible / DisplayAlerts / ScreenUpdating / EnableEvents
├─ Workbooks
│  ├─ .Count / .Item(i) / .Open(path, UpdateLinks, ReadOnly) / .Add()
│  └─ Workbook
│     ├─ .Name / .FullName / .Save() / .Close(SaveChanges) / .SaveAs(path, format)
│     ├─ .ExportAsFixedFormat(0, pdfPath)        ← 整簿导 PDF
│     ├─ .Worksheets
│     │  ├─ .Count / .Item(i) / .Item("表名") / .Add(After:=...)
│     │  └─ Worksheet
│     │     ├─ .Name / .Visible / .UsedRange / .Range("A1:D10") / .Cells(r, c)
│     │     ├─ .PivotTables() / .ChartObjects()
│     │     └─ .ExportAsFixedFormat(0, pdfPath) ← 单表导 PDF
│     └─ .PivotCaches()
│        ├─ .Create(xlDatabase=1, sourceRange)
│        └─ PivotTable
│           ├─ .Name / .TableRange1 / .RefreshTable()
│           ├─ .PivotFields("字段名") → .Orientation(1 行 / 2 列 / 3 筛选) / .Position
│           └─ .AddDataField(field, caption, func)
└─ Range（由 Worksheet.Range / Cells 得到）
   ├─ .Value2 / .Formula / .Text / .NumberFormat
   ├─ .Font / .Interior / .Borders / .HorizontalAlignment / .VerticalAlignment
   ├─ .Rows / .Columns / .Cells(r, c) / .Address
   └─ .AutoFilter() / .Sort(key, order) / .RemoveDuplicates(cols, header)
```

`Value2` 与 `Formula` 是两条通道：前者拿计算结果（日期是序列号），后者拿公式原文。`Text` 是显示文本，受列宽影响，可能被截成 `####`。

常用常量：

| 名称 | 值 | 用途 |
|---|---|---|
| xlDatabase | 1 | 透视缓存源类型（`PivotCaches().Create` 的第一个参数） |
| xlPDF | 0 | 导出 PDF 的固定格式 |
| 行 / 列 / 筛选 | 1 / 2 / 3 | `PivotField.Orientation` |
| sum / count / average / max / min | -4157 / -4112 / -4106 / -4136 / -4139 | `AddDataField` 聚合函数，对应 `--values` 的聚合后缀 |
| xlUp | -4162 | 定位最后一行 |
| xlContinuous | 1 | 边框线型 |
| xlCenter | -4108 | 水平/垂直居中 |

透视聚合常量与 `--values` 后缀的对照（`--values "字段:sum"` 里的 `sum` 就是从这列翻译过去的）：

| `--values` 后缀 | 常量名 | 值 |
|---|---|---|
| `sum` | `xlSum` | -4157 |
| `count` | `xlCount` | -4112 |
| `average` | `xlAverage` | -4106 |
| `max` | `xlMax` | -4136 |
| `min` | `xlMin` | -4139 |

这几个数字与调用顺序转自 `wps-skills` 仓库的 `wps-office-mcp/scripts/wps-com.ps1:696`、`:719`（`$cache = $wb.PivotCaches().Create(1, $sourceRange)`，随后 `$table = $cache.CreatePivotTable($destCell, $pivotName)`；聚合在 `AddDataField($field, $caption, $func)` 上落值）——`文档·未测`，跨仓库实现，没在本机复跑过。`wps_com.py pivot` 的落点应自行 `read` 一次核对，不要只看常量对不对。

## 连接与文件

| action | 作用 | 标签 | 备注 |
|---|---|---|---|
| ping | 探测 COM 是否可用 | 实测·可用 | `DispatchEx` 自报 Version 12.0、Name 为 "Microsoft Excel"，属对象模型兼容 |
| getAppInfo | 返回版本与应用名 | 实测·可用 | 与 ping 同源 |
| wireCheck | 检查对象模型连通性 | 文档·未测 | — |
| openFile / openWorkbook | 打开本地文件 | 实测·可用 | `Workbooks.Open(path, 0, ReadOnly)` |
| closeWorkbook | 关闭工作簿 | 实测·可用 | `Close(SaveChanges)` |
| save | 保存 | 实测·可用 | 写副本后 `Save()` 再 `Close(True)` |
| saveAs | 另存为 | 文档·未测 | 需要时用 `SaveAs(path, format)` |
| convertFormat | 转 xlsx/csv 等格式 | 文档·未测 | 受目标格式常量影响 |
| createWorkbook | 新建工作簿 | 文档·未测 | 本技能默认不新建空簿 |
| getOpenWorkbooks | 列出已打开工作簿 | 文档·未测 | 新实例下通常为空 |
| switchWorkbook | 切换工作簿 | 文档·未测 | 静默实例不需要 |

## 工作表与结构

| action | 作用 | 标签 | 备注 |
|---|---|---|---|
| getSheetList | 列出工作表 | 实测·可用 | 对应脚本的 `sheets` 子命令 |
| createSheet | 新建工作表 | 实测·可用 | 建透视表时自动新建目标表 |
| deleteSheet | 删除工作表 | 文档·未测 | 需 `DisplayAlerts=False` |
| renameSheet | 重命名 | 文档·未测 | — |
| copySheet / moveSheet / switchSheet | 复制 / 移动 / 切换 | 文档·未测 | 静默场景少用 |
| mergeCells / unmergeCells | 合并 / 取消合并 | 文档·未测 | — |
| setColumnWidth / setRowHeight | 列宽 / 行高 | 文档·未测 | — |
| autoFitColumn / autoFitRow / autoFitAll | 自动适应 | 文档·未测 | 写完宽表建议调用，避免 `#####` |
| freezePanes / unfreezePanes | 冻结窗格 | 文档·未测 | — |
| hideRows / hideColumns / showRows / showColumns | 隐藏 / 显示 | 文档·未测 | — |
| groupRows / groupColumns | 分级显示 | 文档·未测 | — |
| protectSheet / unprotectSheet / protectWorkbook / lockCells | 保护 | 文档·未测 | 保护后写入会被拒 |

## 读

| action | 作用 | 标签 | 备注 |
|---|---|---|---|
| getCellValue | 读单格 | 实测·可用 | 返回 Value2 / Text / Formula |
| getRangeData | 读区域 | 实测·可用 | 一次性取 `Value2`，比逐格快两个数量级 |
| getFormula | 读公式 | 实测·可用 | `--formulas` 即此通道 |
| getCellInfo | 读格式、批注等综合信息 | 文档·未测 | — |
| getSelection | 读当前选区 | 文档·未测 | 需要真实 UI 焦点，静默实例不适用 |
| findInSheet | 区域内查找 | 文档·未测 | — |
| getNamedRanges | 命名区域 | 文档·未测 | — |
| getCellComments | 批注 | 文档·未测 | — |
| getExcelContext / getContext | 上下文摘要 | 文档·未测 | 依赖 ActiveSheet |

## 写

| action | 作用 | 标签 | 备注 |
|---|---|---|---|
| setCellValue | 写单格 | 实测·可用 | 1×1 走标量赋值 |
| setRangeData | 批量写区域 | 实测·可用 | 必须传 SAFEARRAY：`VARIANT(VT_ARRAY \| VT_VARIANT, 二维列表)` |
| setFormula | 写公式 | 实测·可用 | 写 `=SUM(C2:C7)` 后回读得到计算值 7800（脚本无入口，见复验锚点节） |
| setArrayFormula | 数组公式 | 文档·未测 | — |
| copyRange / pasteRange | 复制 / 粘贴 | 文档·未测 | 依赖剪贴板，易与用户冲突 |
| fillSeries | 填充序列 | 文档·未测 | — |
| transpose | 转置 | 文档·未测 | — |
| textToColumns | 分列 | 文档·未测 | — |
| insertRows / insertColumns / deleteRows / deleteColumns | 增删行列 | 文档·未测 | 会移动引用，先备份 |
| clearRange | 清除内容/格式 | 文档·未测 | — |
| setHyperlink | 超链接 | 文档·未测 | — |
| insertExcelImage | 插图 | 文档·未测 | — |

### 写入时的日期保护（本技能净新增）

`write` 落盘前会给这些形态的值加前导单引号，强制成文本：

- `YYYY-MM-DD`、`YYYY/M/D`、`YYYY.M.D`，以及 `1-2-3` 这类短分段（`^\d{1,4}[-/.]\d{1,2}([-/.]\d{1,2})?$`）
- 带时分的形态（如 `2021-12-16 08:30:00`），以及 `16:30` 这类纯时刻（`^\d{1,2}:\d{2}(:\d{2})?$`）
- 纯数字、科学计数（如 `20211216`、`1.23E+08`）
- 百分比（如 `12%`）与带货币符号的金额（如 `¥1280.00`、`$99`）
- 布尔字面量 `TRUE` / `FALSE`——不加这层，布尔列会被 WPS 静默改型成布尔值

写完之后那一列是**文本，不是日期序列**：`read` 回来是字符串，`Value2` 也不再是 `44546` 这种数字。这是有意的——数据管道要的是「原样搬过去」，不是让 WPS 猜格式。

复验（跑完 `write --apply` 立刻做）：`wps_com.py read --file ... --sheet ... --range <写入区首行>`，看值是 `2021-12-16` 还是 `44546`；前者是文本，后者说明被当成日期吃掉了。

上游 `wps-skills` 的 `setRangeData` 是直接 `$range.Cells.Item($r+1,$c+1).Value2 = $p.data[$r][$c]`（`wps-office-mcp/scripts/wps-com.ps1:588-595`），没有这层保护——「写完日期变 44546」那个坑就是从这儿来的（`推断`：成因按 Value2 的日期解析推的，没单独做对照实验）。本技能的引号保护是净新增，不是照抄上游。

## 清洗

| action | 作用 | 标签 | 备注 |
|---|---|---|---|
| cleanData(trim) | 去前后空格 | 文档·未测 | 逐格改 `Value2`，大表慢；小表可用 |
| cleanData(remove_duplicates) | 去重 | 文档·未测 | 底层 `Range.RemoveDuplicates(cols, hasHeader)` |
| cleanData(unify_date) | 统一日期 | 文档·未测 | 依赖 `FromOADate`，只对序列值有效 |
| cleanData(remove_empty_rows) | 删空行 | 文档·未测 | 倒序删除，避免行号漂移 |
| removeDuplicates | 去重 | 文档·未测 | 会返回删除行数 |
| sortRange | 排序 | 文档·未测 | `Range.Sort(keyRange, 1/2)` |
| autoFilter | 自动筛选 | 实测·可用 | 本机跑通；带条件时传 field + criteria（脚本无入口，见复验锚点节） |
| subtotal | 分类汇总 | 文档·未测 | — |
| consolidate | 合并计算 | 文档·未测 | — |
| replaceInSheet | 批量替换 | 文档·未测 | — |

四条 `cleanData` 本机都没跑过，主文件也没把它们当可用能力暴露成子命令。`wps-skills` 仓库的 `wps-office-mcp/scripts/wps-com.ps1:649`、`:663-665`、`:675` 有实现，不等于本机能跑——清洗前先拿小表试一次，别在交付路径上直接调。

## 透视表

| action | 作用 | 标签 | 备注 |
|---|---|---|---|
| createPivotTable | 建透视表 | 实测·可用 | 源区首行必须是表头；`PivotCaches().Create(1, rng)` → `CreatePivotTable(dest, name)` |
| updatePivotTable | 增删字段、改聚合、刷新 | 文档·未测 | 同一套 Orientation / AddDataField |

建表后按表名找回新表，且 `TableRange1.Address` 非空，两条都满足才算「表真的建成了」。脚本**不记建表前计数**，不要按「`PivotTables()` 计数 +1」判——簿里本来就有透视表时，这个判法会给你假阴性。取不到 `tableRange` 时代码以**退出码 5** 失败，别把这个失败当成功。`TableRange1.Address` 在 WPS 里可能是属性而不是方法，取值时两种都兼容。

## 图表

| action | 作用 | 标签 | 备注 |
|---|---|---|---|
| createChart | 插入图表 | 实测·可用 | `ChartObjects().Add(l,t,w,h)` + `SetSourceData`；类型常量按 Excel 传（脚本无入口，见复验锚点节） |
| updateChart | 改标题/类型/数据源/配色 | 文档·未测 | — |
| exportChartAsImage | 图表导图片 | 文档·未测 | — |
| exportRangeAsImage | 区域导图片 | 文档·未测 | 走剪贴板 + 临时图表，易失败 |

## 格式

| action | 作用 | 标签 | 备注 |
|---|---|---|---|
| setCellStyle | 字体、填充、对齐 | 实测·可用 | `Font.Size/Bold/Name`、`Interior.Color`、`HorizontalAlignment`（脚本无入口，见复验锚点节） |
| setCellFormat | 数字格式 | 文档·未测 | 等价 `Range.NumberFormat = "0.00"` |
| setBorder | 边框 | 文档·未测 | `Borders.Item(i)`，7–10 外框、11–12 内线 |
| copyFormat | 格式刷 | 文档·未测 | `PasteSpecial(-4122)` |
| clearFormats | 清格式 | 文档·未测 | — |
| setNumberFormat / wrapText | 数字格式 / 自动换行 | 文档·未测 | 格式码用 US 写法（`,` 千分位、`.` 小数） |
| addConditionalFormat / removeConditionalFormat / getConditionalFormats | 条件格式 | 文档·未测 | — |
| addDataValidation / removeDataValidation / getDataValidations | 数据验证 | 文档·未测 | — |
| setPrintArea | 打印区域 | 文档·未测 | 影响导 PDF 的分页 |

## 导出

| action | 作用 | 标签 | 备注 |
|---|---|---|---|
| convertToPDF | 导 PDF | 实测·可用 | 整簿 `Workbook.ExportAsFixedFormat(0, path)` 已跑通且有回归；单表 `Worksheet.ExportAsFixedFormat(0, path)` 只单次冒烟通过、无回归测试——重要交付先用整簿验一次；产物以 `%PDF-` 开头 |
| saveAs | 另存副本 | 文档·未测 | — |
| convertFormat | 转格式 | 文档·未测 | — |
| exportChartAsImage / exportRangeAsImage | 导图片 | 文档·未测 | 见「图表」 |

导 PDF 后必须查文件头与大小，不能以「方法没抛异常」当成功：路径写错时 WPS 可能静默返回。

## 计算与诊断

| action | 作用 | 标签 | 备注 |
|---|---|---|---|
| calculateSheet | 重算 | 文档·未测 | 写入后 WPS 通常自动重算，公式读回已是结果 |
| diagnoseFormula | 公式错误诊断 | 文档·未测 | 依赖 `DirectPrecedents`，部分版本可能不可用 |
| refreshLinks | 刷新外部链接 | 文档·未测 | 会触发弹窗，静默实例慎用 |

## VBA 相关能力（本节全部为 `实测·不可用`）

| 能力 | 标签 | 依据 |
|---|---|---|
| `Application.VBE`、VBE 工程读写 | 实测·不可用 | 实测抛 `com_error`，此版本不带 VBA 引擎 |
| 运行宏（`Application.Run`、按钮绑定的宏） | 实测·不可用 | 同上，没有可执行宏的运行时 |
| 自定义函数（UDF）、加载项函数 | 实测·不可用 | 公式能算内置函数，UDF 无法注册 |
| `ThisWorkbook`/`Worksheet` 事件代码 | 实测·不可用 | 无代码模块 |
| 录制宏生成脚本 | 实测·不可用 | 无录制器 |
| 依赖宏的清洗模板（.xlsm） | 实测·不可用 | 文件能打开，宏不执行；结果按静态值处理 |

替代路径：把宏里的逻辑搬到 Python（pandas / 本脚本的读写接口），把结果写回副本。不要试图「先打开宏再继续」，那一步永远不会成功，只会浪费一轮排查。

## 云文档与其它平台

| 场景 | 标签 | 依据 |
|---|---|---|
| WPS 云文档读数据 | 实测·不可用 | 云文档由 CEF 渲染，不注册 COM（进程级细节以 `cloud-channel.md` 测试环境那行为准）；当时 et.exe 存在但 `Workbooks.Count = 0`（复验命令见 `cloud-channel.md` 的「已封死的通道（可复验清单）」一节第 3 行） |
| `Workbooks.Open("https://...")` | 实测·不可用 | 只拿到登录页 HTML，不是工作簿（脚本无入口）。复验：在 `ping` 拿到的实例上执行 `Workbooks.Open(url)`，看返回值是否为 HTML 文本 |
| macOS / Linux 上的 WPS | `推断` | 本目录只覆盖 Windows COM；其它平台没有稳定自动化接口，本机也没跑过——要用先自己验 |
| CSV | `推断` | 能开，但编码与分隔符行为不稳定；纯 CSV 转换用标准库更快，本技能不做 |
