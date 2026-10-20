# PSD 规范化、复刻与交付

> 核对版本：photocraft-cli 0.10.0 (8407d9ccb)。

规范稿要同时过两道验收：渲染一致（`psd_compare.py`，执行，第 4 节）和结构可维护（`psd_audit.py --strict`，执行，第 3 节）。像素一致只证明输出一样，层树照样可能没法维护。

## 1. 命名契约

### 1.1 选 profile

项目 spec 优先。`psd_audit.py` 和 `layout_design.py check`（执行，见 layout.md）都用 `--profile` 选命名前缀：

| 情况 | `--profile` |
| --- | --- |
| 项目有自己的命名规范 | 写成项目 profile JSON，传文件路径 |
| 没有规范 | `zh`（默认） |
| 英文环境、交给引擎或代码仓 | `en`，或项目 JSON |

```json
{"name": "acme", "extends": "en", "prefixes": {"background": "bkg_", "reference": "ref_"}}
```

不写 `extends` 时 11 个角色都要给。未知角色、空前缀、两个角色同一个前缀都会报错（退出码 2）。前缀区分大小写，按开头匹配，最长的前缀优先。目标引擎对层名字符有要求时，以引擎文档为准选 profile（未验证：各引擎规则不同）。

### 1.2 节点树与前缀

```
页面_<名称>          可省：单页稿直接用 区块_
  区块_<名称>        横向分区：头部、首屏、内容、底部
    组件_<名称>      语义单元：卡片_01、按钮_提交
      <元素前缀><语义>
```

| 角色 | `zh` | `en` | 放什么 |
| --- | --- | --- | --- |
| page | `页面_` | `page_` | 多页稿的页面包装 |
| section | `区块_` | `section_` | 区块，可嵌套区块 |
| component | `组件_` | `component_` | 组件，可嵌套子组件 |
| reference | `参考_` | `ref_` | 对照稿、标注；组必须隐藏 |
| version | `版本_` | `version_` | 多版本包装 |
| text | `文字_` | `text_` | 文字层 |
| icon | `图标_` | `icon_` | 小图形、装饰图标 |
| image | `图片_` | `image_` | 位图、照片、插图，也包括栅格化的文字 |
| shape | `形状_` | `shape_` | 矢量形状、分隔线、边框 |
| effect | `效果_` | `effect_` | 光效、阴影、氛围、调整层 |
| background | `背景_` | `bg_` | 组件或区块的底色、底图 |

### 1.3 层级矩阵

| 父组 \ 子层 | 区块 | 组件 | 元素 | 参考 | 页面 | 版本 |
| --- | --- | --- | --- | --- | --- | --- |
| 根层 | ✓（组） | ✗ | ✗ | ✓（组） | ✓（组） | ✓（组） |
| 页面 | ✓ | ✓ | ✓ | ✓ | ✗ | ✗ |
| 区块 | ✓ | ✓ | ✓ | ✓ | ✗ | ✗ |
| 组件 | ✗ | ✓ | ✓ | ✓ | ✗ | ✗ |
| 参考 | ✗ | ✗ | ✓ | ✗ | ✗ | ✗ |
| 版本 | ✓ | ✓ | ✓ | ✓ | ✓ | ✗ |

### 1.4 规则

- 所有内容进组：根层的元素层判 HIGH（`ROOT_LOOSE_LAYER`），根组不是 页面/区块/参考/版本 判 MEDIUM。
- 组内面板顺序就是视觉上下顺序。背景元素必须连续排在组内最下面（inspect 列表的末尾；psd-tools 自下而上，是开头）。
- 不建空组（HIGH）。节点组（页面/区块/组件/参考/版本）只放一个元素是正常的；其他组只有一个子层判冗余（MEDIUM）。
- 隐藏内容只放在 参考 或 版本 组下；参考组必须隐藏，否则会进最终合成。定稿前删掉隐藏的废层。
- 深度不设硬上限，要卡就给 `--max-depth N`。同一组超过 30 个同级层按语义再分组（LOW）。
- 命名模板 `<前缀><语义>[_<状态>]`，如 `文字_主标题`、`组件_卡片_01`、`背景_渐变`；同一父级不重名，用 `_01/_02` 区分。
- 像素层不要用文字前缀（审计报 `POSSIBLE_RASTERIZED_TEXT`）。栅格化的文字能重打就重打，不能重打就用图片前缀放进归属组件，并在描述文件注明不可编辑。
- 层名里的 `\ / : * ? " < > |` 会让导出文件名被改写或拆成子目录（LOW）；Image Assets 的规格名只放在 `_切图` 副本里（见 cutout-export.md）。
- 调整层放进 组件 或 区块 并剪贴到目标，不跨组件误伤；用效果前缀命名。
- 文字层保持可编辑，不栅格化；多行文字用固定尺寸的文本框；行高常取字号的 1.4–1.7 倍（标题紧、正文松，行业惯例）。
- 叠加、滤色、颜色减淡这类混合模式，目标引擎的 UI 材质未必支持；进引擎前确认，必要时和底图一起烘焙（未验证：取决于引擎）。

### 1.5 不能用的名字

空名、首尾空格、默认名、带 copy/拷贝/副本 后缀的名字。PhotoCraft 的默认名（逐类新建后读回）：

`Layer N`、`Group N`、`Background`（转成普通层后是 `Layer 0`）、`Shape N`、`Rectangle N`、`Rounded Rectangle N`、`Ellipse N`、`Polygon N`、`Star N`、`Line N`、`Curves N`、`Levels N`、`Exposure N`、`Vibrance N`、`Invert N`、`Posterize N`、`Threshold N`、`Selective Color N`、`Channel Mixer N`、`Color Lookup N`、`Black & White N`、`Brightness/Contrast N`、`Hue/Saturation N`、`Color Balance N`、`Photo Filter N`、`Gradient Map N`、`Color Fill N`、`Gradient Fill N`、`Pattern Fill N`、`Artboard N`、`Frame N`。复制出来的层叫 `<原名> copy`、`<原名> copy 2`。文字层按内容命名，没有默认名。

`psd_audit.py` 也认 Photoshop 中文版的默认名（`图层 1`、`组 1`、`背景`、`拷贝`、`副本` 等，沿用自源技能，未在 PhotoCraft 复现）。默认名加 copy 后缀（`Layer 1 copy`）按默认名判 HIGH。

## 2. 规范化与复刻流程

1. **审计原稿（只读）**。记原稿 SHA256。跑 `psd_audit.py audit <原稿> --json > audit-before.json`；在 PhotoCraft 打开原稿，用 `document.inspect` 和 `type.resolveMissingFonts {}` 核对层树、文字和应用侧真实缺字。先出问题清单和重建计划，确认后再动手。
   - 输入是 Affinity（`.af/.afdesign/.afphoto/.afpub`）、Krita `.kra` 或 Paint.NET `.pdn`：PhotoCraft 只能导入，psd-tools 读不了。先导入，另存 `<稿名>_原稿.psd` 当只读基线再审计；导入警告里列出的不支持项记进问题清单。
2. **冻结视觉基线**。同一引擎把原稿渲染成 PNG（`photocraft-cli convert`，或 serve `doc.render {maxSide:0, path}`，最长边超过 2048 只能用 `convert`），存为 `baseline.png` 并记 hash。后续对比都以它为准。
3. **设计目标层树**。写旧层 → 新组的映射；标出要拆的合并层、要重打的文字、要转智能对象的素材、无法恢复的项。原稿是平图时注明「只能按视觉复刻」。
4. **另存规范稿**。存成 `<稿名>_规范.psd`：serve 用 `doc.save {path}`，GUI 用 `app.save {path}`（保存语义见 automation.md）。PSD/PSB/.pcraft 另存会让文档指向新文件，平图格式只是副本。确认当前文档已指向规范稿，不要用不带 path 的保存回写原稿。
5. **在副本上重建**。建组、改名（`layer.renameLayer {layer, name}`；`layer.rename` 不存在）、移层、转智能对象（`layer.smartObjects.convertToSmartObject` 会换新 id）、补蒙版和调整层；每批改动后 inspect 复核。PSD 存盘再打开后图层 id 会重排，重开后按名字或重新 inspect 定位。
6. **补字体**。`type.resolveMissingFonts` → 出候选 → 用户确认 → 安装 → 在规范稿上写回 `text.font` → `type.fonts` 复核。获取、安装与授权见 fonts.md。不要调用 `type.replaceAllMissingFonts`：它会把所有缺失字体静默换成 `Inter`。
7. **文字规范化**。逐层核对字体、字号、字距、行距、颜色、对齐、文本框；记录替换字体的理由和视觉差。
8. **视觉验收**。`psd_compare.py <原稿或 baseline.png> <规范稿> --out psd-compare-out > visual-diff.json`，目标 `identical`；有差异就逐像素定位修复；跨工具来源才给 `--fuzz`，并写明原因。再做适合窗口与 100% 双尺度目检。
9. **结构验收**。`psd_audit.py audit <规范稿> --strict --json > audit-after.json` 要求 CRITICAL/HIGH/MEDIUM 全为 0，LOW 逐条有结论；`psd_audit.py compare <原稿> <规范稿> --strict --json > audit-compare.json` 记录前后指标。
10. **交付**（第 5 节）。原稿与规范稿分开保存，原稿 SHA256 未变。

| 情况 | 处理 |
| --- | --- |
| 平图或合并层 | 按视觉复刻，规范稿结构是新建的，描述文件注明「复刻自平图」 |
| 栅格化文字 | 优先重打；不能重打就用图片前缀放进归属组件，注明不可编辑 |
| 合并的主体或素材 | 有源文件就拆；没有就作为智能对象放进语义组，注明来源缺失 |
| 缺精确字体 | 出候选让用户定；记录替换后的家族、样式、授权和视觉差，不自动换近似字体 |
| 不支持的智能滤镜或效果 | 在副本上烘焙，原效果的隐藏副本放进参考组，注明不可回改 |
| 多页面或多版本 | 用页面或版本组包装，内部仍按节点树组织，不把多页平铺成一层 |

## 3. psd_audit.py（执行）

只读 PSD/PSB，需要 psd-tools（`pip install psd-tools`；缺失时打印一行说明并退出 2）。

```bash
python "<skill-dir>/scripts/psd_audit.py" audit "<稿>.psd" [--profile zh|en|<profile.json>] [--strict] [--json] [--installed-fonts fonts.jsonl] [--max-depth N]
python "<skill-dir>/scripts/psd_audit.py" compare "<原稿>.psd" "<规范稿>.psd" --strict --json
```

| 级别 | 代码 |
| --- | --- |
| CRITICAL | `EMPTY_PSD` 没有图层 |
| HIGH | `ROOT_LOOSE_LAYER`、`EMPTY_NAME`、`WHITESPACE_NAME`、`DEFAULT_NAME`、`DUPLICATE_SIBLING_NAME`、`EMPTY_GROUP`、`TEXT_NO_FONT`、`FONT_READ_ERROR`、`FONT_NOT_INSTALLED`（只在给了 `--installed-fonts` 时） |
| MEDIUM | `ROOT_UNKNOWN_GROUP`、`NODE_PREFIX_MISMATCH`、`REFERENCE_VISIBLE`、`HIDDEN_OUTSIDE_REFERENCE`、`TEXT_OUTSIDE_NODE_GROUP`、`BACKGROUND_NOT_BOTTOM`、`SINGLE_CHILD_GROUP`、`COPY_NAME`、`POSSIBLE_RASTERIZED_TEXT`（像素层名字以文字前缀开头；形状、智能对象、图片前缀不报）、`DEPTH_EXCEEDED`（只在给了 `--max-depth` 时） |
| LOW | `TOO_MANY_SIBLINGS`、`NAME_HAS_PATH_CHAR`、`FONT_FAMILY_ONLY` |

- 退出码：0 没有 CRITICAL/HIGH（`--strict` 时 MEDIUM 也算失败）；1 有；2 文件读不了、缺 psd-tools、参数或 profile 错误。读不了的文件是退出码 2，不是 CRITICAL。`compare` 的退出码看新稿。
- 输出默认 Markdown；`--json` 一行，含 `summary.strictOk`、`issues`、`stats`、`rootGroups`（面板自上而下）、`fonts`、`readerWarnings`。`readerWarnings` 收集 psd-tools 读文件时的告警（例如 PhotoCraft 写的曲线调整层会触发 `Failed to read CurvesExtraMarker`），它们不进 stderr，也不影响判级。
- 字体：PhotoCraft 写的 PSD 只存 PostScript 名（`Inter-Regular`），家族名和样式为空。`--installed-fonts` 接受 JSON 或 JSON Lines，从任意层级收集 `family`、`name`、`postscriptName`、`postscript_name`。只给家族清单时按「PostScript 名去掉 `-样式` 后忽略空格大小写」对家族，报 LOW `FONT_FAMILY_ONLY`；要精确比对就把 faces 也放进去：

```bash
photocraft-cli run --new '{"width":8,"height":8}' --cmd type.fonts \
  --cmd type.fonts --params '{"family":"Inter"}' > fonts.jsonl
```

  字体装没装以应用侧 `type.resolveMissingFonts` 为准，这个参数只做辅助核对。
- 命名与结构规则和 `layout_design.py check` 共用 `psd_contract.py`（阅读：库，不单独运行），两者不会给出相反结论；`check` 读 inspect JSON、还查栅格，`psd_audit.py` 读 PSD 文件、还查字体，互不替代。

## 4. psd_compare.py（执行）

```bash
python "<skill-dir>/scripts/psd_compare.py" <旧稿或PNG> <新稿或PNG> [--out DIR] [--overwrite] [--fuzz 0-255] [--cli PATH]
```

- 用同一个 `photocraft-cli convert` 把两边渲染成 PNG（`.png` 输入直接比），先比 SHA256，不同再逐像素比较并写 `diff.png`（未变像素压暗、变化像素标红）。
- `--fuzz` 是每通道容差，默认 0。同引擎重渲染预期零差异。比较在 8-bit RGBA 下进行，16-bit 稿件按 8-bit 精度比。
- stdout 一行 JSON：`result`（`identical`/`differs`/`error`）、`differingPixels`、`percent`、`maxChannelDelta`、`size`、`diffImage`；画布尺寸不同时 `reason:"size"`，不出 diff 图。
- `warnings` 是真警告（缺字体回落等），要转述给用户；`expectedWarnings` 是写平图必出的 `N layer(s) flattened; layers, masks and blend modes are not kept`，不用转述。
- `--out` 下固定写 `old.png`、`new.png`、`diff.png`，已存在时拒绝（`--overwrite` 才覆盖）。不给 `--out` 时用临时目录：`identical` 或出错时删掉，`differs` 时保留并在 `out` 里给路径。
- 退出码：0 identical；1 differs；2 出错（缺 Pillow、找不到 CLI、渲染失败、参数错误、两边是同一个文件）。
- PSD 文件本身的哈希证明不了渲染一致：结构重写后字节必然不同，以渲染结果为准。

## 5. 交付

### 5.1 交付单元是一个目录

```text
<稿目录>/
├── <稿名>.psd / .psb / .pcraft    分层母版（规范化任务可叫 <稿名>_规范.psd）
├── <稿名>.md                       描述文件（5.5）
├── <稿名>.png                      交付平图（按需）
├── fonts/<家族名>/                 字体文件 + 授权文件（只在授权允许再分发时）
├── audit-before.json / audit-after.json / audit-compare.json / visual-diff.json   规范化任务
├── assets/ + assets-manifest.json  切图（按需，见 cutout-export.md）
└── psd-compare-out/                验证产物（可选）
```

### 5.2 file.package（只在 CLI）

稿内有链接智能对象时，只拷 PSD 会断链。`file.package` 把文档和链接素材一起收进可搬走的目录：

```bash
photocraft-cli run "<稿名>.psd" --cmd file.package --params '{"dir":"<交付目录>","format":"pcraft"}'
```

- 产物 `<交付目录>/<稿名>/<稿名>.<ext>` 加 `Links/`，文档里的链接重新指向副本；回执 `{document, folder, links, missing, warnings}`，`missing` 列出找不到的链接（打包照常完成）。
- `format` 只有 `pcraft`（默认）、`psd`、`psb`，其他值报 `unknown package format (pcraft|psd|psb)`。PSD 存不了外部链接，链接素材会被嵌入并给出警告 `the linked smart object … was embedded (PSD export keeps no external links)`（PSB 未实测）；要保留链接用 `pcraft`。
- serve、MCP 和 GUI 控制通道都拒绝它。
- 打包不代替描述文件和 `fonts/`。

### 5.3 字体随稿

- 免费商用不等于允许再分发或嵌入。只有授权明确允许再分发时才把字体文件放进 `fonts/`；不允许时在描述文件记下家族名、授权凭证、获取方式和未随附的原因，并写明接收方要自己取得授权。
- 只放这份稿实际用到的家族，用完整字体文件（不用 woff2 之类的网页切片），授权文件放在旁边，每个文件的 SHA256 与来源记录一致。多份稿共用字体时各自带副本，交付目录可以独立搬走。
- 字体从哪来、装在哪、怎么登记见 fonts.md。

### 5.4 字体依赖核对

描述文件的字体依赖表以稿内真实记录为准：

- 层用的家族：`document.inspect` 里文字层的 `text.font`。
- PSD 字体表：psd-tools 对 PhotoCraft 写的 PSD 只能读到 PostScript 名，`family`/`style` 为空：

```python
# 执行；需要 psd-tools
from psd_tools import PSDImage
for layer in PSDImage.open("<稿名>.psd").descendants():
    if layer.kind == "type":
        print(layer.name, [f.postscript_name for f in layer.typesetting.fonts])
```

- 家族、样式、字重：`type.fonts {"family":"<家族>"}` 回 faces（`postscriptName`、`style`、`weight`），用 PostScript 名对上。
- 记录的字重和本机能用的不一致时（例如稿里是 Bold、本机只有 Medium），在描述文件写明实际渲染用的字重和换到别的软件打开时的回落行为。

### 5.5 描述文件模板

按稿填写，未知项写「未验证」，不要删字段。

````markdown
# <稿名>.psd 说明

## 文件信息
| 项 | 值 |
|---|---|
| 文件 | <稿名>.psd |
| 用途 | |
| 画布 | 宽×高，色彩模式，位深 |
| 大小 | 字节 |
| SHA256 | |
| 图层数 | |
| 基准稿 | （若有） |

## 规范化记录（非规范化任务写「不适用」）
| 项 | 值 |
|---|---|
| 原稿 | 文件名 + SHA256 |
| 原稿审计 | audit-before.json 摘要（层数、组数、深度、CRITICAL/HIGH 数） |
| 规范稿 | 文件名 + SHA256 |
| 规范稿审计 | audit-after.json 摘要 |
| 命名 profile | zh / en / 项目 profile 文件，例外项说明 |
| 旧层 → 新组 | 映射表或映射文件路径 |
| 字体替换 | 原字体 → 实际字体、理由、授权、视觉差 |
| 视觉对比 | psd_compare 结果、diff 图、fuzz 与原因 |
| 未解决项 | 无法恢复的层、已知差异、待用户决定的事 |

## 图层结构
（树形，标出组、文字层、形状层、智能对象、变量层）

## 文字规格
（逐层：字体、字号、字距、颜色、bounds、抗锯齿、transform）

## 字体依赖
| 图层 | 家族 | PSD 字体表（PostScript 名） | fonts/ 文件 | 授权（能否再分发） |
|---|---|---|---|---|

## 切图与资产（按需）
（命名、倍率、格式、padding、画心/含纸边、投影/配件的决定；assets-manifest.json 的位置）

## 可变量
（变量层与替换方式）

## 验证与复验命令
（psd_compare / psd_audit 的命令、结果、产物路径）

## 已知限制

## 素材与授权
（字体授权、图片素材来源与核对记录、发布前要确认的事项）
````

切图的复验命令（`trim_export.py`，执行，参数见 cutout-export.md）按实际用到的模式写，不要把所有参数一次堆上（`--bg-color` 只能配 `--trim bg`，`--bbox` 只能配 `--trim bbox`），例如：

```bash
python "<skill-dir>/scripts/trim_export.py" "<渲染图目录>" --out assets --trim alpha --padding 8 \
  --scales 1,2 --manifest assets-manifest.json --source-document "<稿名>.psd" --note "<画心/投影决定>"
```

### 5.6 素材授权

- `fetch_asset.py`（执行，可选）下载的占位图只用于测试和复现，不进交付物。
- 图库图（Pexels、Pixabay）进交付物之前，打开报告里的 `sourcePage` 和 `licenseUrl` 现场核对授权（可识别人物、商标、原样转售等限制），把核对结果写进描述文件的「素材与授权」。报告里的 `licenseSummary` 是写死的摘要，`licenseVerified` 恒为 `false`。

### 5.7 交付自检

- [ ] 每份分层稿有同名 `.md`，模板字段没有删减
- [ ] 描述文件里的 SHA256、验证数据和复验命令能复跑
- [ ] 平图与母版是同一版本
- [ ] 授权允许再分发时，`fonts/` 覆盖稿内全部字体家族、没有多余家族，SHA256 与来源记录一致；不允许时已写明未随附的原因
- [ ] `type.resolveMissingFonts` 没有缺失，`type.fonts` 能看到交付需要的字体
- [ ] 规范化任务：原稿与规范稿 SHA256、audit-before/after、audit-compare、visual-diff、旧层 → 新组映射齐全；原稿 SHA256 未变
- [ ] 规范稿 `psd_audit.py --strict` 通过，LOW 逐条有结论
- [ ] 切图任务：`assets/` 与 `assets-manifest.json` 的命名、尺寸、倍率、格式、alpha 与 spec 对得上，`failures` 为空
- [ ] 有链接智能对象时已用 `file.package` 打包，`missing` 为空或已告诉用户
- [ ] 图库素材的授权已在来源页核对并记录；占位图没有进交付物
