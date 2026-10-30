---
name: office-pro
description: Office 文档专业工具链：PDF 全能处理（编辑/涂黑/签名/加解密/压缩/OCR/表单/IR）、中文公文合同报告排版规范、Excel 财务建模与公式审计、PDF 排版引擎与质量检查、PPT 模板套用与溢出控制。当需要 PDF 编辑处理、生成 GB/T 9704 公文、做财务模型、审计表格公式、套用 PPT 模板或排查文字溢出时使用。不适用于简单文档生成（用 docx/xlsx/pptx/pdf 基础技能）。
---

# Office Pro — 专业文档工具链

四类文档的专业能力，分两层：

- **PDF 处理**：`pdfkit/` 50+ 命令的纯 Python 工具箱，负责编辑、脱敏、签名、加解密、压缩、OCR、表单、IR 结构操作。
- **专业场景 + 质检**：`references/` 与 `scripts/` 提供中文排版规范、财务建模、排版引擎、质量检查工具。

基础生成仍走 `docx`/`xlsx`/`pptx`/`pdf` 基础技能；本技能补它们没有的专业场景、可执行工具与硬约束。

## Outcome Contract

- **Outcome**: 完成 PDF 处理任务，或产出符合行业规范的文档并附可复现的质检结论。
- **Done when**: pdfkit 命令返回 `{"ok": true}` 且输出文件可打开；或质检脚本返回通过/如实列出不合格项；排版符合对应规范；PPT 文字未超容量预算。
- **Evidence**: pdfkit 的 JSON 输出；`postcheck.py` / `xlsx.py audit` / `pdf_qa.py` 实际输出；未通过项指名写清。
- **Authorization**: 系统工具安装（ghostscript/tesseract/libreoffice）与 pip 包安装须先告知并征得同意；`exec_python` 执行任意代码前须确认；修复文档在工作副本上进行，不覆盖用户原文件。

## 路由表

按需求类型选：PDF 处理走 pdfkit 命令，文档专业场景读对应 reference。

### PDF 处理（pdfkit）

| 需求 | 命令入口 |
|---|---|
| 读文本/页数/图片/表格/结构 | `pdfkit.py extract_text` / `page_count` / `extract_images` / `extract_table` / `layout_analyze` |
| 编辑文字（含扫描件） | `pdfkit.py smart_edit` / `pymupdf_edit` / `edit_scanned` |
| 涂黑脱敏、签名、加解密 | `pdfkit.py redact` / `sign_pdf` / `encrypt` / `decrypt` |
| 合并/拆分/裁剪/旋转/压缩 | `pdfkit.py merge` / `split` / `crop` / `rotate` / `compress` |
| 表单检测与填写 | `pdfkit.py form_detect` / `form_fill` / `form_fill_annotation` |
| 书签、页码、水印、去页眉页脚 | `pdfkit.py bookmarks` / `add_page_numbers` / `watermark` / `remove_headers_footers` |
| 转 Word / 转格式 | `pdfkit.py pdf_to_word` / `convert` |
| IR 级结构修改（导出 JSON 改完再重建） | `pdfkit.py ir_export` / `ir_import` / `ir_inspect` / `ir_modify` / `ir_diff` |
| OCR 定位与搜索 | `pdfkit.py ocr_locate` / `search_text` |

调用方式（先跑 setup 建 venv，之后用 venv 里的 python）：

```bash
# 首次
bash pdfkit/scripts/setup.sh          # macOS/Linux
cmd /c "pdfkit\scripts\setup.bat"     # Windows

# 日常
pdfkit/scripts/venv/bin/python3 pdfkit/scripts/pdfkit.py <command> --input doc.pdf
```

```powershell
# Windows PowerShell 必须用 & 调用运算符
& "pdfkit\scripts\venv\Scripts\python.exe" "pdfkit\scripts\pdfkit.py" split --input doc.pdf --output_dir out --mode ranges --ranges "[[0,2]]"
```

参数不确定时跑 `pdfkit.py <command> help`。**页码从 0 开始**；坐标系原点在左上角、y 轴向下（A4 = 595×842 点），与 PDF 原生坐标系相反，命令内部已处理。

### 文档专业场景

| 需求 | 加载 |
|---|---|
| 中文公文（GB/T 9704）、红头文件、通知、函 | `references/docx-official-doc.md` |
| 合同、协议 | `references/docx-contract.md` |
| 工作报告、总结、汇报材料 | `references/docx-report.md` |
| 学术论文（GB/T 7713）排版与结构 | `references/docx-gb-t-7713-academic.md` |
| 参考文献著录（GB/T 7714） | `references/docx-gb-t-7714-citation.md` |
| Excel 财务模型、三表、预算 | `references/xlsx-finance.md` |
| Excel 数据分析配方 | `references/xlsx-analyze-recipes.md` |
| **从零建一张业务表**（场景原型、坐标锚点、字段类型、配色） | `references/xlsx-schema-principle.md` |
| 建表范式：计划 / 打卡 / 统计 / 表单打印 / 看板 / 日历 / 计算模型 | `references/xlsx-design-patterns/` |
| **改已有表格**（CSV/XLSX/XLSM/XLS）——文本保真、长字段分页、版本冲突、批次依赖 | `references/xlsx-editing-rules.md` |
| PDF 文字溢出排查 | `references/pdf-overflow.md` |
| PDF 分页与续页控制 | `references/pdf-pagination.md` |
| PDF 表单/模板填充 | `references/pdf-fill-engine.md` |
| PDF 封面设计 | `references/pdf-cover.md` |
| PPT 套用现有模板 | 本文「PPT 模板套用」 |
| **PPT 设计质量判定**（画布几何、间距层级、字号下限、配图分级） | `references/pptx-design-principle.md` |

## 质检工具（可直接运行）

脚本依赖：`postcheck.py` 需 python-docx；`xlsx.py` 需 openpyxl（recalc 另需本机 LibreOffice）；`pdf_qa.py` 需 PyMuPDF。均不需要平台服务。

### scripts/postcheck.py — DOCX 业务规则自检

```bash
python scripts/postcheck.py 文档.docx
python scripts/postcheck.py --json --strict 文档.docx
```

按内置规则集做业务自检，返回非零即有问题；`--json` 输出机器可读结果，`--strict` 从严判定。

### scripts/xlsx.py — Excel 质量与操作

```bash
python scripts/xlsx.py audit  表.xlsx     # 公式错误 + 零值 + 隐式数组
python scripts/xlsx.py scan   表.xlsx     # 引用异常（跨表断裂、区域偏移）
python scripts/xlsx.py recalc 表.xlsx     # LibreOffice 重算并扫错
python scripts/xlsx.py pivot  表.xlsx ... # 透视表
```

`audit`/`scan` 不依赖外部软件；`recalc` 需要本机 LibreOffice（缺软件时返回 `missing_dependency` 结构化提示，不自动安装）。注意：openpyxl 写入的公式只有字符串、无缓存值，预览器或 pandas 读到的是 `None`，这是必须 recalc 的原因。

### scripts/pdf_qa.py — PDF 质量检查

```bash
python scripts/pdf_qa.py <pdf路径> [选项]
```

检查文字溢出、字体缺失、分页异常。参数读脚本头部 `USAGE`，不要臆测。

### scripts/design_engine.py / cover_render.py — PDF 排版与封面

`design_engine.py` 是纯标准库排版引擎（版心计算、字体度量、分页决策）；`cover_render.py` 基于 ReportLab 生成封面。被 PDF 相关 reference 调用，一般不手动跑。

## PPT 模板套用（核心方法）

套用现有模板时**不要从零画新页**——外来页在模板里一眼看得出。

### 容量预算法

```
每个文本形状的容量上限 = 模板原有文字长度 × 1.1
```

超过预算就是真实缺陷，必须改写、加宽或缩字号。这是唯一可靠的溢出防线，不靠目测、不靠渲染截图。

### 模板测绘（生成内容之前）

用 python-pptx 遍历所有文本形状（**递归进 GROUP**），记录位置、尺寸、字体、原文字长度、**页面角色**。

页面角色从形状清单推导，不看图：

| 角色 | 判据 |
|---|---|
| 封面 | 形状少 + 标题 ≥36pt，或有满版背景图 |
| 章节页 | 只有 1–2 个短文本框 |
| 内容页 | 多个正文框 |
| 数据页 | 有 60pt+ 的数字形状 |
| 引用页 | 单个大号居中长文本框 |

### 决定性结构判断

先回答：设计活在 `slideLayouts`（真占位符）里，还是画在 slides 的自由文本框上、layouts 为空？

- 有真占位符 → `add_slide` + 填占位符
- layouts 为空（下载的模板常见）→ **必须在 XML 层克隆 slide**（复制 slide part + `.rels`、重注册 media rId、加进 `sldIdLst` 和 `[Content_Types].xml`）

### 设计真相源

- 幻灯片尺寸读 `presentation.xml`（**不要假设 16:9**）
- 颜色和字体读 `theme1.xml`——slide XML 用 `schemeClr` 间接引用，真实 hex 在主题里（还被 master 的 `clrMap` 重映射）
- 中文文字渲染用 `<a:ea>` 字体

### 输出纪律

默认存成新兄弟文件（`<stem>_updated.pptx`），**不改原文件**。必须原地改时先备份 `<stem>_backup.pptx`（不放 `/tmp`）。

### 交付前程序化校验（不看图也能判定）

1. **页序与页数**——数 `sldIdLst` 是否与计划一致
2. **残留占位符**——slide XML 里搜 `Click to add`、`xxx`、`lorem`、`TODO`、`[insert`
3. **图片断链**——遍历 `slide.part.rels`，每个非 external rel 都要有非空 `target_part.blob`
4. **文件能打开**——重新 `Presentation(path)` 并遍历所有形状；这就是 XML 合法性检查
5. **字体颜色未变**——与原件逐项 diff，不靠肉眼
6. **溢出/碰撞**——重算容量预算 + 比对 `left+width` 与邻接形状

## Common Rationalizations

| 想法 | 纠正 |
|---|---|
| "文字差不多长就行，肉眼看着没溢出" | 容量预算可计算，超了就是缺陷，目测发现不了边缘溢出 |
| "先画个新页补上，风格差不多" | 外来页立刻露馅，必须克隆模板页 |
| "PPT 是 16:9 吧" | 读 `presentation.xml`，4:3 和自定义尺寸很常见 |
| "PDF 直接改就行" | 改用户文件前先复制到新路径；pdfkit 输出也走新文件 |
| "质检跑一条就够了" | PPT 六条、文档按对应脚本全跑；只跑一条等于没检 |

## Red Flags

- 没做模板测绘就填内容 → 必然溢出或页序错乱
- `Presentation.save(用户原路径)` → 直接覆盖用户文件
- 从图片看页面角色 → 应从形状清单推导
- DOCX 质检只看有没有报错 → 不合格项要指名写出
- 带参考图的 PDF 处理失败就降级成纯文本重建 → 丢失原版式

## Verification

1. PDF 处理：pdfkit 返回 `{"ok": true}`，输出文件存在且 `page_count` 符合预期
2. DOCX：`postcheck.py` 退出码 0，或列出具体不合格项
3. XLSX：`xlsx.py audit` + `scan` 均无异常
4. PDF 生成：`pdf_qa.py` 无溢出/缺字体告警
5. PPTX：六条程序化校验全过

## Hard Rules

- 修改用户文件前先复制，输出到新路径。
- pdfkit 的系统工具与 pip 包安装须先告知用户并征得同意（含 OCR 组件）。
- `exec_python` 执行任意代码前须确认代码内容；它只允许白名单模块导入。
- 质检结论必须来自脚本实际输出，不能凭观感断言"看起来没问题"。
- 容量预算（×1.1）是硬上限，超了就改文案或版式。
- 中文公文场景优先遵守 `references/docx-official-doc.md` 的字号/行距/页边距规范。
- PDF 处理失败时不得静默降级为纯文本重建。
