# 版式稿：栅格、摆位与验收

> 核对版本：命令 id 与参数按 photocraft-cli 0.14.0 复核；行为记录来自 0.10.0–0.14.0 的实测，0.14 未逐条重验的条目保留原文。

## 0. 适用范围

| 稿件 | 走不走本文 |
| --- | --- |
| 版式稿：多个文字、图片、装饰元素要按列和间距对齐（界面、海报、传单/展架/横幅、电商详情页/主图/Banner、社媒配图、印刷版式、引擎 UI 稿） | 走 |
| 照片稿（风景、人像、修复、抠图合成）和纯视觉创作（插画、绘画） | 不走：没有落列诉求，跑 `check` 只会得到假问题；按 retouch.md 做 |
| 照片与版式混排（详情页里的实拍图、海报主视觉照片） | 只对版式部分做布局检查 |

判断看稿件本身有没有要对齐分布的多个元素，不看类型标签。项目 spec 优先：用户给了画布、列数、间距、命名，就用用户的值。一个项目定一个画布尺寸，中途改了要重算栅格、间距和切图。

## 1. 间距与栅格

- 间距刻度：4 / 8 / 12 / 16 / 24 / 32 / 40 / 48 / 64，以 4 为单位（`check` 按 4 的倍数查 y 和间距）。常见取值：组件内 padding 8/12/16，模块外边距 16/24/32，gutter 16 或 24。13、19、22 这类孤儿值先回刻度找最近的合法值。
- 列网格：

```
columnWidth = (canvasWidth - margin*2 - gutter*(columns-1)) / columns
第 i 列起点 x = margin + (columnWidth + gutter) * i
跨 n 列宽   = columnWidth*n + gutter*(n-1)
```

- 元素左边落在列起点、右边落在列右边线，宽度自然是跨列宽。只看 x 不够：1200/80/24/12 下宽 344 的元素 x 在列上，右边 424 越过列线 16 px，看上去就是没对齐。
- 列宽取整：`layout_design.py calc`（执行，第 7 节）默认取「步距（列宽 + gutter）为 8 的倍数」的最大整数，余数全留在右侧。这是本工具的取向：列起点全落在 8pt 上，代价是内容区偏左（1440/120/24/12 余 72 px，内容区 120..1248）。不想要这个取向时用 `--snap none`（同一配置得到列宽 78、步距 102、列起点 120/222/324）或 `--column-width N`。

`calc` 实测输出（默认取向）：

| 画布 | margin | gutter | 列数 | 列宽 | 步距 | 列起点 | 右余 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1200 | 80 | 24 | 12 | 64 | 88 | 80/168/256… | 8 |
| 1200 | 80 | 20 | 12 | 68 | 88 | 80/168/256… | 4 |
| 1440 | 120 | 24 | 12 | 72 | 96 | 120/216/312… | 72 |
| 1920 | 80 | 24 | 12 | 120 | 144 | 80/224/368… | 56 |
| 1080 | 16 | 16 | 4 | 248 | 264 | 16/280/544/808 | 8 |
| 750 | 16 | 16 | 4 | 160 | 176 | 16/192/368/544 | 30 |

1200/80/24/12 的合法宽度：64, 152, 240, 328, 416, 504, 592, 680, 768, 856, 944, 1032。常见起点配置：Web 12 列 / margin 80 / gutter 24，移动端 4 列 / margin 16 / gutter 16（社区惯例，不是标准）。

## 2. 摆位基元

| 要做的事 | 命令 | 要点 |
| --- | --- | --- |
| 铺栅格参考线 | `view.newGuideLayout {columns, width, gutter, margin, clearExisting:true}` | `width` 是单列宽，直接用 `calc` 的 `guideLayoutParams`。传画布宽报 `count, size and gutter must fit inside the target margins`；不传 `width` 会均分出小数位参考线（144.656）。回 `{"horizontal":n,"vertical":n}` |
| 单条参考线 | `view.newGuide {orientation, position}` | 回 `null` |
| 读现状 | `photocraft-cli info <稿> --compact`、`document.inspect`、serve `doc.inspect` | 三者层树相同：bounds `[x,y,w,h]`，自上而下，组的 bounds 为 `null`，`kind` 为 `Pixel/Shape/Type/Group/Adjustment/Fill/Smart Object` |
| 相对移动 | `layer.translate {layer, dx, dy}` | `{x, y}` 被静默忽略；没有 `layer.setBounds`，绝对定位靠 `dx = 目标 - 当前`；移动组会带着子层走 |
| 缩放、精确四角 | `edit.transform {rect, quad}` / `{matrix}` / `{scaleX, scaleY, rotate, dx, dy}` | 只传 `rect` 报 ``pass `quad` …``。文字层除外：缩放后 `size_pt` 仍报原值，会变成被压扁的文字；改字号用 `type.setStyle {size}` |
| 对齐 | `layer.align.leftEdges` 等 6 条，`{to:"auto\|layers\|selection\|canvas"}` | 作用于图层选区；`to:"canvas"` 对齐画布 |
| 分布 | `layer.distribute.horizontally` 等 8 条，`{}` | 作用于图层选区 |
| 选层 | `layer.select {layer \| name, mode:"add"}` | 参数是单数 `layer`；传 `{"layers":[…]}` 报 `needs layer or name` |
| 入组 | `layer.groupLayers {name}`、`layer.moveTo {layers:[…], target, position:"into"}` | `groupLayers` 包住当前选中的层；`into` 放到组内最上面 |
| 清像素选区 | `select.deselect` | 先看 inspect 的 `hasSelection`；没有选区时，CLI `run` 回 `null`、退出码 0（实测 0.18），serve 的 `engine.execute` 才报 `not available right now: no selection`；`select.none` 不存在 |

层级顺序就是层树顺序，没有 z-index；改上下用 `layer.moveTo {target, position:"above"|"below"|"into"}`。

## 3. 新层落在哪

- 新层插在活动层上方、同一个父级里。活动层是组里的子层时，新层进这个组；活动层是组本身时，**0.18 实测新层落进该组**（`parent` 指向组，`depth` 加一），与早期"落在组外"的记录相反。要在根级建层就先选中一个根层，别停在组上。
- 往组里加层：先 `layer.select` 组里的某个子层再建；或者建完用 `layer.moveTo {layer, target:<组>, position:"into"}`；一批散层用 `layer.select` 选好后 `layer.groupLayers {name}` 一步包起来。
- 组内面板顺序就是视觉上下顺序：先建底层（背景），再往上建。

## 4. 文字的坐标

- 点文字 `type.create {x, y}` 的 y 是基线；段落文字 `type.create {box:[x,y,w,h]}` 的 x/y 是框的左上角。
- inspect 给的文字 bounds 是字形墨迹框，比框或锚点偏右一个首字侧距，字号越大偏得越多：48pt 的 `Hello Layout` 放在 `box` x=80，bounds 是 `[84,104,277,45]`。真实的框看 `type.info`：`transform` 的平移量（`[1,0,0,1,80,104]`）加 `shape.Box {width, height}`。
- 回执的框格式不统一：`type.create` / `type.info` 回 `[x0,y0,x1,y1]`，`shape.create` 回 `[x,y,w,h]`。
- 垂直居中、框高改小会丢行等排版问题见 text-layout.md。

## 5. inspect bounds 的边界

- bounds 已裁到画布内，不会为负，也不会超出画布。部分出界看不出来；整层移出画布或空像素层显示为 `[0,0,0,0]`。
- 参考线不出现在 inspect，也不进 `doc.render` 的图。无头核对参考线：存成 PSD 后读图像资源 1032（位置单位是 1/32 px）：

```python
# 执行；需要 psd-tools
from psd_tools import PSDImage
info = PSDImage.open("<稿>.psd").image_resources.get_data(1032)
print(sorted(loc / 32 for loc, d in info.data if d == 0))  # 竖向参考线 x
print(sorted(loc / 32 for loc, d in info.data if d == 1))  # 横向参考线 y
```

实测 1200×800、`{columns:12, width:64, gutter:24, margin:80}`：竖线 80, 144, 168, … , 1112, 1120（共 25 条），横线 80、720。

## 6. 执行顺序

1. 定 spec：画布、列数、margin、gutter、间距刻度、命名 profile（见 psd-workflow.md）、是否进引擎。
2. 跑 `layout_design.py calc` 拿列宽、列起点、合法宽度，不要手推。
3. 用 `calc` 输出的 `guideLayoutParams` 调 `view.newGuideLayout`。
4. 从底向上建层和组（第 3 节）。只建要用的组：空组会被判 HIGH。
5. 读 bounds（`info --compact` 或 `doc.inspect`），按 `calc` 结果算 dx/dy，`layer.translate` 写回；改尺寸用 `edit.transform`（文字层改 `type.setStyle {size}`，见第 2 节）。
6. 残差用 `layer.align.*` / `layer.distribute.*` 收：先 `layer.select` 选好层；有像素选区时才 `select.deselect`（`edit.fill` 之后选区会留着）。
7. 每批改动后重读 inspect 核对 bounds；跑 `layout_design.py check`（读 inspect JSON）和 `psd_audit.py audit --strict`（执行；读 PSD 文件，见 psd-workflow.md），两者输入不同，不能互相代替。
8. 关键布局做渲染前后对比：`doc.render {maxSide:0, path}` 或 CLI `convert` 出图，交给 `psd_compare.py`（执行，见 psd-workflow.md）。蒙版、混合模式、智能对象会让几何改动看起来生效、实际没落。

布局是静态结果：没有 HUG/FILL 和约束，内容尺寸变了要重算重摆。

## 7. layout_design.py（执行）

```bash
python "<skill-dir>/scripts/layout_design.py" calc --width 1440 --margin 120 --gutter 24 --columns 12 [--snap none | --column-width 78] [--json]
photocraft-cli info "<稿>.psd" --compact > inspect.json
python "<skill-dir>/scripts/layout_design.py" check --spec spec.json --inspect inspect.json [--profile zh|en|<profile.json>] [--strict] [--json]
```

- `calc` 的 JSON 输出：`columnWidth`、`pitch`、`columnX`、`legalColumnSpans`、`remainderRight`、`pitchOn8pt`、`allOn8pt`（margin 不是 8 的倍数时为 false，此时看 `pitchOn8pt`）、`guideLayoutParams`。
- `check` 的输入直接用 `info --compact` 的输出；`photocraft-cli run … --cmd document.inspect` 的输出行和 serve `doc.inspect` / `engine.execute` 的回复也行（自动取 `result`）。
- `--spec` 必填；只想查命名和结构时显式写 `--no-geometry`。spec 的 `width`/`height` 必须和 inspect 的画布一致，否则退出码 2。

spec.json：

```json
{"width": 1200, "height": 800, "margin": 80, "gutter": 24, "columns": 12,
 "gridRoles": ["section", "component"], "gridLayers": [], "spacingScale": [4, 8, 12, 16, 24, 32, 40, 48, 64]}
```

`width height margin gutter columns` 必填整数；可选 `columnWidth`（固定列宽）、`snap`（`"pitch8"` 默认或 `"none"`）、`spacingScale`（最小值是判定单位）、`gridRoles`（要查落列的角色，默认区块和组件）、`gridLayers`（额外要查的层名或路径）。未知字段会出警告。

几何规则：

| 规则 | 说明 |
| --- | --- |
| 查谁 | `gridRoles` 里的组（取可见子层 bounds 的并集）和 `gridLayers` 点名的层。组件内缩进的图标、文字默认不查，要查就把 `text`、`icon` 等角色加进 `gridRoles` |
| 贴边不查 | 贴画布左、右、上边的边不查（通栏背景、出血图） |
| 文字容差 | 由文字决定的左边：x 落在某列起点的 −0.05 到 +0.15 倍字号（px）之间就算对齐，字号取 `text.sizePt × resolution / 72`；由文字决定的右边和上边不查 |
| 出界层 | bounds 宽或高为 0 报 `ZERO_SIZE` |
| 重叠 | 同一父级下同角色（图片、图标、形状、组件、区块）重叠报 `SAME_KIND_OVERLAP`；背景、效果、参考、文字不参与 |

| 代码 | 级别 | 含义 |
| --- | --- | --- |
| `GRID_X` | MEDIUM | 左边不在列起点（报最近的列） |
| `GRID_RIGHT` | MEDIUM | 右边不在列右边线（报最近的合法宽度） |
| `ZERO_SIZE` | MEDIUM | 空层或整层出界 |
| `SAME_KIND_OVERLAP` | MEDIUM | 同级同类重叠 |
| `SPACING_Y` / `SPACING_GAP` | LOW | y 或相邻间距不是刻度单位的倍数 |

命名与结构规则和 `psd_audit.py` 共用 `psd_contract.py`（阅读：库，不单独运行），但两者输入不同：`check` 读 inspect JSON 并查栅格，不查字体安装与栅格化文字；这些由 `psd_audit.py` 读 PSD 文件检查，不能互相替代。退出码：0 没有 CRITICAL/HIGH（`--strict` 时 MEDIUM 也算失败）；1 有；2 输入、spec 或 profile 错误。

## 8. 验收

| 维度 | 命令 | 通过标准 |
| --- | --- | --- |
| 结构与栅格（inspect JSON） | `layout_design.py check --spec … --inspect …` | 退出码 0；MEDIUM 逐条有结论（`--strict` 时为 0） |
| 结构（PSD 文件） | `psd_audit.py audit <稿> --strict --json` | `strictOk: true` |
| 视觉 | `psd_compare.py <旧渲染> <新渲染>` | `identical`，或差异已定位并解释 |
| 保存 | serve `doc.save {path}` / GUI `app.save {path}` | 回执 `path` 存在，`warnings` 为空或逐条转述 |

脚本只保证几何与结构。对比度、字号层级与行高、文字是否溢出文本框、留白、视觉层级与语义是否一致、混合模式在目标环境是否支持、色彩模式与分辨率是否匹配交付目标，都要人工看。
