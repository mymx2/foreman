# PSD 规范化、复刻与交付

> 核对版本：命令 id 与参数按 photocraft-cli 0.14.0 复核；行为记录来自 0.10.0–0.14.0 的实测，0.18.0 的补充实测在文中标注；0.14 未逐条重验的条目保留原文。

规范稿要同时过两道验收：渲染一致（`psd_compare.py`，执行，第 4 节）和结构可维护（`psd_audit.py --strict`，执行，第 3 节）。像素一致只证明输出一样，层树照样可能没法维护。含隐藏历史版本的工作母文件按 2.8 处理，`--strict` 不作为交付门槛。

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

**审计不是目标，规范才是。** 稿子沿用客户既有命名体系（比如按 `00_`–`05_` 编号根组、元素用 `固定_`/`VAR_`/`区域_`）时，做法是写一份对应的项目 profile 让 `--strict` 认识它，**不要为了把审计压到 0 去改客户的层名**。层名一改，下游脚本、模板版本链、历史对比全部失配。profile 每个角色只能配一个前缀（共 11 个角色）；编号根组和多类元素前缀并存时无法全覆盖，剩余条目逐条登记为已知例外并在交付说明里写清原因。

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
2. **冻结视觉基线**。同一引擎把原稿渲染成 PNG（`photocraft-cli convert`，或 serve `doc.save {path}`；`doc.render` 最长边上限 2048，全尺寸基线别用它），存为 `baseline.png` 并记 hash。后续对比都以它为准。
3. **排查怪稿（审计的盲区）**。第 1 步的审计和栅格检查只能查命名、层级、字体、落列——「画面正常但定义怪异」的稿件会全部漏过：渲染两遍都一样，检查器却看不见层里藏了什么。按第 2.5 节逐类过一遍，重点是 inspect 逐层读 `bounds`/`kind`/`hasMask`/`hasVectorMask`/`clipped`/`blend`/`opacity`，再把关键层**单独渲染**出来看（CLI 用 `layer.exportAs {path}` / `layer.quickExportAsPng {path}`；serve 的 `doc.exportLayers` 只出顶层，嵌套层先隐藏兄弟层）。发现的怪异点全部登记进问题清单，和结构问题一起排进重建计划。
4. **设计目标层树**。写旧层 → 新组的映射；标出要拆的合并层、要重打的文字、要转智能对象的素材、无法恢复的项。原稿是平图时注明「只能按视觉复刻」。
5. **另存规范稿**。存成 `<稿名>_规范.psd`：serve 用 `doc.save {path}`，GUI 用 `app.save {path}`（保存语义见 automation.md）。PSD/PSB/.pcraft 另存会让文档指向新文件，平图格式只是副本。确认当前文档已指向规范稿，不要用不带 path 的保存回写原稿。
6. **在副本上重建**。建组、改名（`layer.renameLayer {layer, name}`；`layer.rename` 不存在）、移层、转智能对象（`layer.smartObjects.convertToSmartObject` 会换新 id）、补蒙版和调整层；每批改动后 inspect 复核。PSD 存盘再打开后图层 id 会重排，重开后按名字或重新 inspect 定位。
7. **补字体**。`type.resolveMissingFonts` → 出候选 → 用户确认 → 安装 → 在规范稿上写回 `text.font` → `type.fonts` 复核。获取、安装与授权见 fonts.md。不要调用 `type.replaceAllMissingFonts`：它会把所有缺失字体静默换成 `Inter`。
8. **文字规范化**。逐层核对字体、字号、字距、行距、颜色、对齐、文本框；记录替换字体的理由和视觉差。
9. **视觉验收**。`psd_compare.py <原稿或 baseline.png> <规范稿> --out psd-compare-out > visual-diff.json`，目标 `identical`；有差异就逐像素定位修复；跨工具来源才给 `--fuzz`，并写明原因。再做适合窗口与 100% 双尺度目检。
10. **结构验收**。`psd_audit.py audit <规范稿> --strict --json > audit-after.json` 要求 CRITICAL/HIGH/MEDIUM 全为 0，LOW 逐条有结论；含隐藏版本的母版按 2.8 审可见交付面，剩余条目登记例外。`psd_audit.py compare <原稿> <规范稿> --strict --json > audit-compare.json` 记录前后指标。第 3 步登记的怪异点逐项复核：修掉的写进规范化记录，修不掉的进「未解决项」。
11. **交付**（第 5 节）。原稿与规范稿分开保存，原稿 SHA256 未变。

| 情况 | 处理 |
| --- | --- |
| 平图或合并层 | 按视觉复刻，规范稿结构是新建的，描述文件注明「复刻自平图」 |
| 栅格化文字 | 优先重打；不能重打就用图片前缀放进归属组件，注明不可编辑 |
| 合并的主体或素材 | 有源文件就拆；没有就作为智能对象放进语义组，注明来源缺失 |
| 缺精确字体 | 出候选让用户定；记录替换后的家族、样式、授权和视觉差，不自动换近似字体 |
| 不支持的智能滤镜或效果 | 在副本上烘焙，原效果的隐藏副本放进参考组，注明不可回改 |
| 多页面或多版本 | 用页面或版本组包装，内部仍按节点树组织，不把多页平铺成一层 |

## 2.5 怪稿排查：画面正常但定义怪异

> 核对版本：photocraft-cli 0.14.0 复核；字段来自 `photocraft-cli info --compact` / `document.inspect` 的逐层实测（部分 0.12 记录保留，0.18.0 的补充实测在文中标注）。

「规范」有两层：结构规范（第 1 节，检查器可查）和**定义规范**——层里记录的几何、载体和编辑状态应该和视觉一致，能改参数而不是只能挪像素。后者没有检查器：渲染前后一致证明不了定义正常（`psd_compare` 恰好会放过所有这类问题），要靠第 2 节第 3 步的人工排查。先看清两类信号的区别：

- **机器能查的**（读 inspect JSON 就能判定）：bounds、kind、hasMask、hasVectorMask、clipped、blend、opacity、visible、调整层 params。`layout_design.py check` 的 `ZERO_SIZE` 顺带覆盖「整层出界」。
- **机器查不到的**：智能对象的源尺寸和缩放比例、形状层的定义几何与实际渲染的偏差、蒙版内部的像素分布、非等比自由变换、点文字被压扁——inspect 不暴露定义侧数据，只能把层**单独渲染出来人工看**。

下面按怪异类别列出识别信号和规范化动作。「信号」是 inspect JSON 里可见的线索，「确认」是要补的人工动作。修复动作全部在副本（规范稿）上做，修完走第 9 步渲染比对证明视觉未变。

### A. 定义几何 ≠ 视觉几何（机器查不到，必须人工）

典型：视觉上是正方形，PSD 里其实是长方形素材被拉扁/蒙版裁切/变换压方。画面看不出来，换个引擎或改字重立刻变形。

| 怪异 | 识别信号（inspect） | 确认（人工） | 规范化动作 |
| --- | --- | --- | --- |
| 非等比变换：素材被拉成另一比例 | 无信号（inspect 只有 bounds） | 单层渲染出来量比例，或对智能对象 `layer.smartObjects.editContents` 打开内容文档看原始比例 | 有源文件就回到源里改，重放进规范稿；没有源就接受现状，描述文件登记「定义比例 ≠ 视觉比例，不可恢复」 |
| 蒙版/剪贴路径做视觉裁切：定义的形状大于看到的内容 | `hasMask:true` 或 `hasVectorMask:true`，bounds 比同组件其他元素异常大 | 单层渲染看裁切边界，蒙版用 `select.loadSelection {channel:"mask", layer}` 载入选区看范围 | 属于「用蒙版伪造几何」：能重画形状就用 `shape.create` 重建（同色同位），蒙版只留给真正的语义抠图 |
| 形状层定义矩形，视觉是圆角/带描边 | `kind:"Shape"`，bounds 与视觉不符 | `shape.info {layer:<id>}` 读 `live`（`radii`、`stroke`）核对；只认数字 id，传图层名会被静默忽略（0.12.0 实测），先 `layer.select` 再不带参数调用也行 | 按视觉重建：`shape.create {kind:"roundedRect", radii, rect, stroke}`；圆角、描边进定义，不靠效果凑 |
| 智能对象重复变形：内容文档里还嵌着变换 | `kind:"Smart Object"` + 上游有变换痕迹 | `editContents` 打开看内容文档的画布与变换 | 展平内容里的多余变换，重放为一次变换；能等比就等比 |
| 像素层模仿几何：纯色块用画笔画出来的 | `kind:"Pixel"` + 在组件里承担形状角色（图片/图标/形状前缀） | 单层渲染 + 取样确认是纯色几何 | 用 `shape.create` / `layer.newFillLayer.solidColor` 重建为形状或填充层，位置尺寸按 bounds |
| 点文字被变换压扁/拉宽 | `kind:"Type"` + 墨迹框异常 | `type.info` 的 `transform` 与字号核对（text-layout.md） | 重打文字：`type.create` 同内容同字体，删掉被压扁的旧层 |
| 全图非等比拉伸进画布 | 画布比例与视觉内容比例不符 | 无 | 记录为「按视觉复刻」类：重建时按视觉比例画，不复制错误定义 |

### B. 定义载体不对（可半机器识别）

「视觉上是形状，载体却是像素」这类。检查器已覆盖一部分（`POSSIBLE_RASTERIZED_TEXT`），其余靠 kind 与语义角色核对：

| 怪异 | 识别信号 | 规范化动作 |
| --- | --- | --- |
| 形状前缀层是像素（`形状_x` 但 `kind:"Pixel"`） | kind ≠ Shape/Fill 但名字有形状前缀 | 按视觉重建为形状层；确实是位图内容（纹理、手绘边框）就改用图片前缀 |
| 图标层是普通像素层 | `icon` 角色 + `kind:"Pixel"` | 有源就重放矢量；没有就留像素，描述文件注明 |
| 文字用图片承载 | `POSSIBLE_RASTERIZED_TEXT`（检查器已查，见第 3 节） | 第 1 节规则：能重打就重打 |
| 纯色块用像素层或带内容的图承载 | 单层渲染 + `document.sampleColor` 多点取样纯色 | 重建为 `layer.newFillLayer.solidColor` 或形状层 |
| 背景是位图却命名成 `背景_纯色` 之类 | 名字与取样结果矛盾 | 按实际载体改名（图片前缀）或重建为填充层 |

### C. 定义数量不对（可机器识别）

| 怪异 | 识别信号 | 规范化动作 |
| --- | --- | --- |
| 同一视觉元素由多层拼成（对不齐的接缝、半透明叠两层同色） | 同级同类 `SAME_KIND_OVERLAP`（`layout_design.py check`，版式稿） | 合并（`layer.mergeLayers`）或重画为单层；合并前留快照 |
| 复制层改一忘一：两份近似内容，一份已过时 | 同名或近名兄弟层、bounds 高度重叠 | 和用户确认哪份是最新，过时的进参考组或删除 |
| 视觉一个按钮 = 图层+样式层+蒙版层三件套拆开 | 剪贴链 `clipped:true` 串起的多层 | 属于正常做法时保留；拆散的补剪贴（`layer.createClippingMask`），修掉跨组件误伤的 |

### D. 定义空间不对（可机器识别）

| 怪异 | 识别信号 | 规范化动作 |
| --- | --- | --- |
| 内容大部分在画布外，只露一角 | bounds 触到画布边缘（0 或 width/height）且单层渲染发现内容被裁 | 有意出血就保留并登记；无意就把内容移回画布（`layer.translate`），画布外部分截掉 |
| 坐标原点漂移：整稿所有层统一偏了半像素/几像素 | 全部层 bounds 的 x/y 有共同余数（如都是 .5） | 版式稿按 `layout_design.py` 重算重摆；照片稿接受现状并记录 |
| 画布内藏着完全看不见的层（透明度 0、不可见、或被上层完全盖住） | `opacity:0`、`visible:false`、或单层渲染 vs 合成渲染比对 | 死层删除；要留底的进参考组（第 1 节规则） |
| 图层堆叠序与视觉层级相反（装饰压着文字却排更上） | inspect 层序 vs 渲染视觉 | 按视觉重排（`layer.moveTo`）；本来就是叠放效果的（叠印、蒙版）除外 |

### E. 导出口径不对（渲染看不见，必须单独查）

切片、参考线、图层复合不进渲染，`psd_compare` 和目检都发现不了，但会决定「切片导出」的范围，换版后最容易残留旧几何。

| 怪异 | 识别信号 | 规范化动作 |
| --- | --- | --- |
| 切片边界停在旧版画布上：删章或改高后没重切 | `slice.list` 里 `origin:"user"` 的切片，矩形起点与章节或内容对不上；末片只剩几十像素 | 没有切片导出需求就 `slice.delete {slices:[id…]}` 全删（`origin:"auto"` 的整画布切片保留）；要做切片导出就用 `slice.fromGuides` 按当前参考线重切，边界落在章节间隙 |
| 参考线与版面不符 | 之前用 `view.newGuideLayout` 铺过，后续版式又改了 | 按 `layout_design.py` 的 `guideLayoutParams` 重铺 |
| 图层复合记着旧版本 | `document.inspect` 的 `layerComps` 与当前可见性组合不一致 | 逐个复核，过时的删掉 |

实测例子：原稿 11 条切片铺满 11480 高的画布，删章后画布变 9298，前 9 条边界原样保留，最后一条被截成 19px。渲染完全正常，只有 `slice.list` 能看出来。

**删章前先确认背景归属**：章节背景层常同时盖到下一章，直接删会让下一章底色变化（实测删 `绘画真迹` 后，作品细节章从 #F4F4F4 变成白底）。删前单独隐藏背景层、对比相邻章节的渲染；只属于被删章节的才删，跨章的保留，或给下一章补同色背景。

### 方法的三个限制

- **组没有 bounds**：`document.inspect` 和 `info` 的组层 `bounds:null`。算章节范围要按叶子层算，别对组取 bounds。
- **剪切层的 bounds 是未裁切范围**：`clipped:true` 的层报整个内容框（实测 790×1644），可见区只有下面的框（370×360）。按 bounds 算章节范围会把相邻章节算成重叠，属假阳性；要按可见框算。
- **智能对象要核源比例，但别只看比例**：`layer.smartObjects.exportContents {layer, path}` 拿到源图，比对源图宽高比与图层框宽高比。比例不一致只说明「缩放或裁切」，不能直接判变形：取消剪切后单独渲染（`layer.setProps {clipped:false}` 再 `layer.exportAs`），整幅源内容都在框里、比例又不对，才是拉/压；只出现局部就是裁切。实测两个方向：详情 4 张 3368×5000 塞进 790×1644，整幅可见，纵向拉 1.40 倍；主图 468×468 的方图放进 249×468，是裁掉左右留白，不是变形。

### 排查顺序与登记

排查按「先机器后人工」：

1. 跑 `psd_audit.py` + `layout_design.py check`（版式稿）拿结构/几何问题——这些是「定义错误」的子集；再跑 `slice.list` 看切片、参考线、图层复合是否还对着当前版面。两者的输入不同：`psd_audit.py` 读 PSD 文件、出命名/字体/层级问题，**不产出 bounds**（它的组树只有 name/kind/visible/children）；几何一律看 `layout_design.py check` 或 `info`/`document.inspect`。
2. 写个一次性脚本（或手工）扫 inspect JSON：B/C/D 三类信号全部可编程判定。A 类机器查不到，逐层单渲核对。
3. 每个怪异点登记：路径、信号、人工确认结果、处置（修复/接受/待用户决定）。处置为「接受」的项写进描述文件「未解决项」。

修这些不改变视觉：全部动作做完后走第 9 步 `psd_compare` 应得 `identical`——如果变了，说明修复改动了视觉，先修回归再交付。

## 2.6 模板版本链的选区与占位

做模板批量出图（模板 PSD + 变量数据）时，版本链推进遵循下面的选区与占位规则。版本角色：v1 = 规范母版（结构、命名、字体、初版样例），v2 = 变量标记（`VAR_` 前缀、字段拆分），v3 = 占位版（纯色 Shape 标出变量槽位），v4 = 生产版（真实数据替换）。「槽位」= 变量区域（文字区域、图片框等）。

- **v1 不是一次冻结**：先出 v1 结构和初版样例，v2/v3 确定最终选区（变量区域）后，回到 v1 按选区修正样例文字、文本框、对齐，再重跑 v2/v3/v4。不要只改 v3 占位而不改 v1 样例——占位与样例必须自洽。v1 样例若来自用户素材，回改前征得同意或另存新版本号。
- **满版变量不做占位**：占位色块只服务有边界的变量槽位（文字区域、图片框），让人看到可选区间；槽位就是整张画布时（如全画布智能对象替换），占位只会遮住画面，v3 直接跳过，v1/v2 标记 `VAR_` 即可，v4 替换。
- **固定内容用 Box 文本框，可变内容用点文字**：固定说明（标语、品牌信息）用 Box 文本框保持自动换行；可变标题、姓名用点文字，换字后用 `type.info` 重读墨迹 `bounds`（会随缩放即时刷新），按 `min(区域宽/墨迹宽, 区域高/墨迹高)` 改 `size` 再复验，反复到落入区域。不要用 `edit.transform` 缩放文字层——缩完 `size_pt` 仍报原值，且与「点文字被压扁要重打」的规范冲突。多字段一行不塞一个框，拆成独立文字层各自固定选区。
- **每版留同引擎对比**：画布一致时用 `psd_compare.py`（第 4 节）逐像素比对，并确认差异只在变量区域；画布尺寸变化时用 `doc.save` 或 CLI `convert` 出全尺寸图（`doc.render` 有 2048 上限，长图会失败）拼并排图 + `info --compact` 存尺寸表。
- **构建脚本要幂等、产物要原子落盘**：源哈希固定，同一输入重跑得到同一结果；输出先写成同目录的 `.tmp`（`.psd`、`.json` 都算），过了 `info` 断言 + `psd_audit --strict` + `warnings` 检查再 `os.replace` 成正式名。中断只会留下 tmp，不会留下半截正式产物。Windows 上 `os.replace` 撞到读者占用会抛 `PermissionError`（WinError 5），做几次短退避重试再放弃，不要吞掉这个错。

## 2.7 槽位放图与落位验收

模板槽位（`VAR_作品图` 这类智能对象）换图时，**换完不会自动适配原来的放置框**：实测 0.18 下 `layer.smartObjects.replaceContents` 与 serve 的 `doc.replaceSmartObject` 都保留图层既有的 transform/缩放，新内容的 bounds = 新源像素 × 图层缩放，不会按旧框裁切或缩放；左上角沿用旧原点。72ppi 文档里，600×300 @300dpi 的源图替换后仍回读 600×300（同一图层先缩到 50% 再替换则回 300×150），不是按 DPI 换算的 144×72。直接换会得到一张尺寸不对的图，必须重读 bounds 再按目标矩形缩放。

还有一个更隐蔽的连带：**复制出来的智能对象共享同一份内容源**，替换其中一个会把所有共享实例一起改掉（`layer.smartObjects.replaceContents` / `doc.replaceSmartObject` 的回执里 `instances` 列出的层全部受影响）。模板里首屏图和场景图常常是同一张图的复制品，只想换首屏时直接 `replaceContents`，场景图会跟着变。要先确认目标层有没有兄弟实例：回执里 `instances` 多于一项就说明共享了。只改其中一个时，改用 `doc.place` / `file.placeEmbedded` 新建一个独立对象，再把原层隐藏，不要动共享源。新对象默认落在最上层；要放回画框、被画框裁剪时，用 `layer.moveTo {layer, target:<原层>, position:"above"}` 移到原位置，再 `layer.setProps {layer, clipped:true}` 建立剪贴（实测 0.18）；漏掉这两步，图会盖住画框或叠层。

要把素材精确塞进目标矩形：

1. 换图，然后读新 bounds（`layer.list {flat:true}` 或 `document.inspect`）。
2. 算缩放 `s = min(目标宽/新宽, 目标高/新高)`，等比不拉伸。
3. 居中：`x2 = 目标x + (目标宽 - 新宽×s)/2`，`y2` 同理；`w2 = 新宽×s`，`h2 = 新高×s`。
4. `edit.transform {layer, quad: [[x2,y2],[x2+w2,y2],[x2+w2,y2+h2],[x2,y2+h2]]}`，四角顺序 左上→右上→右下→左下，坐标用画布绝对值。
5. 复核：`bounds` 落在目标矩形内，允许 1px 取整差。

```python
# 执行：把 layer 塞进 rect=(x, y, w, h)
b = next(l for l in session.execute("layer.list", {"flat": True})["layers"] if l["id"] == layer)["bounds"]
bx, by, bw, bh = b
s = min(w / bw, h / bh)
w2, h2 = bw * s, bh * s
x2, y2 = x + (w - w2) / 2, y + (h - h2) / 2
session.execute("edit.transform", {"layer": layer,
    "quad": [[x2, y2], [x2 + w2, y2], [x2 + w2, y2 + h2], [x2, y2 + h2]]})
```

模板侧的三个坑：

- **目标矩形从隐藏的区域层取**：模板里通常有 `区域_*` 层，`bounds` 就是槽位范围。比按视觉目测可靠。
- **有多个区域层时按源图长宽比选**：竖幅槽和方槽各有一个，按原图比例挑最接近的那个，选错会把图裁掉或留大片空白。
- **样例层可能压在槽位上面**：模板自带的样例图/装饰如果排在 `VAR_` 层之上，换图后它会继续挡着。换完检查同组里有没有样例层，隐藏后重新渲染确认差异区域确实变了。

## 2.8 工作母文件与隐藏版本

设计直接给的工作母文件常把多个历史版本堆在一个文档里：当前只显示一组，其余组 `visible:false`。这份稿子的交付物包含隐藏版本，不能按普通单版稿整理。

- 先按可见性分组：`document.inspect` 取每组的 `visible` 和父子关系，找出「可见祖先链」上的层。只重命名、删除、改字这条链上的层。
- 隐藏组的名称、可见性、文字和图片内容原样保留；不要整份 `layer.list {flat:true}` 直接批量改名——隐藏版本里有大量同名层（`正方形2`、`LOGO`、`1`），按名字或全量 id 映射会误伤。
- 改完做隐藏版本前后比对：组名与可见性清单、隐藏组内文字层的 `text`、字号、字面、bounds 和智能对象来源逐项比对。实测一份 240 层母文件里有 66 个隐藏组，批量改名时误改了两层隐藏版本，靠前后比对才查出来。
- 可见与隐藏版本可能共享同一份智能对象内容（实测可见层与 3 个隐藏实例同源）。换图不要替换共享源；新建独立智能对象、隐藏旧可见层，隐藏实例才不会跟着变。
- 母版 `info` 的缺字体警告可能来自保留的隐藏版本。验收按可见交付面：可见文字层字面全部已装；警告逐条归到隐藏层并在交付说明写明，不为消警告去改历史版本。不要用不带层的全文档 `type.resolveMissingFonts`（它没有 layer 参数，会改到隐藏层）；只对可见层逐层 `type.setStyle` 指定字面。
- 含隐藏版本的母版，`psd_audit --strict` 不作为交付门槛；按项目 profile 审可见设计，剩余条目登记例外（隐藏版本本身会贡献大量默认名和根层项）。
- 交付母版保留隐藏版本；是否另存一份只含可见版本的轻量稿，按客户需要决定，不要擅自删除历史版本。

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

  字体核对分两层：`type.resolveMissingFonts` 只做字族级辅助，字面是否装齐要逐文字层比对 `type.info` 的 `runs[].style.postscript_name` 与 `type.fonts` 的 `postscriptName`（见 fonts.md）；只把 faces 交给 `--installed-fonts` 做精确比对。`type.fonts` 传错 family 也回 `{"faces":[]}`，先核对家族拼写。
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
- 长图（高远大于宽，如详情页、滚动页）差异复核：逐像素统计之外，自行把差异像素按 y 坐标聚成区段（`psd_compare.py` 目前不输出 bands），方便只复核变化区域；低亮度通道差异（如 `0,0,1`）不能漏掉——脚本按任一 RGBA 通道非零判定，不要先转灰度再统计。

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
| 怪稿排查 | 逐条：路径、信号、人工确认结果、处置（修复/接受/待用户决定）；「接受」项同时写进未解决项 |
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
- [ ] `type.resolveMissingFonts` 没有缺失，且逐文字层核对过 `postscript_name` 都在 `type.fonts` 已装列表里（字族通过不代表字面通过；含隐藏版本的母版按 2.8 只查可见交付面）
- [ ] 规范化任务：原稿与规范稿 SHA256、audit-before/after、audit-compare、visual-diff、旧层 → 新组映射齐全；原稿 SHA256 未变
- [ ] 规范稿 `psd_audit.py --strict` 通过，LOW 逐条有结论（含隐藏版本的母版按 2.8 例外口径）
- [ ] 切图任务：`assets/` 与 `assets-manifest.json` 的命名、尺寸、倍率、格式、alpha 与 spec 对得上，`failures` 为空
- [ ] 有链接智能对象时已用 `file.package` 打包，`missing` 为空或已告诉用户
- [ ] 图库素材的授权已在来源页核对并记录；占位图没有进交付物
