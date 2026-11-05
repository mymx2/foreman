# 设计规则（语义层）

本文是 Ardot 画布编辑的语义规则：节点怎么摆、文本怎么排、图标怎么画、表格怎么搭。

本文不覆盖：

- 工具调用语法与批处理限制 → `shared/mcp-cheatsheet.md`
- 节点属性字段字典 → `shared/ardot-schema.md`
- 复合效果参数配方 → `shared/effects-guide.md`
- 验证流程与分级 → `shared/verification.md`

模块自己的硬约束优先于本文；冲突时以模块文档为准。

---

## 编辑原则

- 属性未定义时按 0 处理，不臆造值。
- 每个新建节点必须有 `name`；命名与分组规则见 `shared/naming-and-structure.md`。
- 优先复制已有内容再修改，而不是从零重画。
- 新画板只能放在空位，放置前必须调 `locate_available_space`，禁止手写坐标。
- 构建顺序固定：**结构 → 内容 → 样式 → 验证**。
- 属性值等于默认值时可省略；颜色浮点保留两位小数。
- 单次 `batch_edit` ≤ 25 个操作，按「外层容器 → 内部节点」拆批。

---

## 坐标

- 所有坐标相对父级左上角，`x` 向右、`y` 向下。
- 子节点坐标永远相对直接父级，不是画布绝对坐标。
- 自动布局容器内的子项，`x` / `y` 被完全忽略；需要脱离布局流时设 `layoutPositioning: "ABSOLUTE"`（默认 `AUTO`）。

---

## 自动布局

- 优先用 flex 布局，而不是手动算坐标。
- **新建 Frame 的默认值（实测）**：
  - 只给 `name` / `fills`，不给 `layout` 和尺寸 → `layout: "none"`、`100×100`、双向 `FIXED`。
  - 显式给 `layout`、不给 `width` / `height` → 双向 `hug_contents`（`HUG`）。
  - 需要固定像素或撑满时，必须在同一次调用里显式写 `width` / `height`。
  - `clipsContent` 实测默认 `true`；子内容需要溢出可见时显式设 `false`。
- `fill_container` 只在父级有布局时有效；`hug_contents` 只在节点自身有布局时有效。
- 父级不能 `hug_contents` 而所有直接子项都是 `fill_container`，会形成循环依赖。
- 父级 padding 统一作用于所有子项，flex 没有 margin。要单独偏移某个子项，给它包一层带 padding 的 frame。
- `layout: "none"` 让所有子项回到绝对定位，非必要不用。
- 对齐只有在布局非 `none` 时生效：
  - 主轴：`primaryAxisAlignItems` = `MIN` / `CENTER` / `MAX` / `SPACE_BETWEEN` / `SPACE_EVENLY`
  - 交叉轴：`counterAxisAlignItems` = `MIN` / `CENTER` / `MAX` / `BASELINE`
- 尺寸值：数字为固定像素；`"fill_container"` 撑满父级；`"fill_container(200)"` 撑满且最小 200；`"hug_contents"` 包裹内容。

### 换行网格

重复卡片（商品栅格、功能卡、指标卡）用 `layout: "wrap"`，不要手算行。

```javascript
grid=I(section, {
  type: "frame", name: "Product Grid",
  layout: "wrap",
  width: "fill_container",
  height: "hug_contents",
  gap: 12,              // 横向间距
  counterAxisSpacing: 12 // 换行后的纵向间距
})
card=I(grid, {
  type: "frame", name: "Product Card",
  width: 165,           // 固定宽度决定列数
  height: "hug_contents",
  layout: "vertical", gap: 8
})
```

- 网格容器：`layout: "wrap"` + `height: "hug_contents"`。
- 卡片：固定 `width` + `height: "hug_contents"`，不要固定高度。
- 卡片内图片：`width: "fill_container"`。
- 列宽公式：`(可用宽度 - gap × (列数 - 1)) / 列数`。

---

## 文本节点

- 文本**没有默认颜色**，必须显式设置 `fill`，否则不可见。
- 需要换行的文本：`width: "fill_container"`（父级有布局）或固定宽度。默认 `hug_contents` 会横向撑开。
- 单行文本用 `hug_contents`，并确认不会溢出。
- `textAlignHorizontal` / `textAlignVertical` 只在有宽度约束时生效，且不改变文本框位置；定位靠布局。
- `lineHeight` 用 `"AUTO"` 或像素整数（如 `36`），不要用倍率。
- 每个文本节点都要显式给 `fontName`。字体族跟随设计系统；创建后如需校验，调 `get_available_fonts` 用准确 `family + style`，不要猜 style 名称。
- 更多文本属性（`textAutoResize`、`maxLines`、`textTruncation`、`textCase`）见 `shared/ardot-schema.md`。

---

## 颜色与渐变

- `fill` / `stroke` 支持 hex 简写（如 `fill: "#18191C"`）；`fills` / `strokes` 数组里的 `SOLID` 颜色对象只认 `r` / `g` / `b`，`GRADIENT_*` 必须提供 `r` / `g` / `b` / `a`。
- `gradientStops` 至少两个；`boundVariables` 可以为空但必须存在。
- 支持 `GRADIENT_LINEAR` / `GRADIENT_RADIAL` / `GRADIENT_ANGULAR` / `GRADIENT_DIAMOND`。
- 文字颜色同样通过 `fill` 设置，不是 `textColor`。
- 颜色浮点保留两位小数。

```javascript
// 线性渐变
U("nodeId", {fills: [{
  type: "GRADIENT_LINEAR",
  gradientStops: [
    {color: {r: 0.2, g: 0.4, b: 1.0, a: 1}, position: 0, boundVariables: {}},
    {color: {r: 1.0, g: 0.4, b: 0.3, a: 1}, position: 1, boundVariables: {}}
  ],
  gradientTransform: [[1, 0, 0], [0, 1, 0]],
  opacity: 1, visible: true, blendMode: "NORMAL"
}]})
```

---

## 表格

严格层级：**Table（frame）→ Row（frame）→ Cell（frame）→ Content**。

每个单元格必须是 frame，文本不能直接挂在 Row 下。

```javascript
row=I("tableId", {type: "frame", name: "Row", layout: "horizontal", width: "fill_container"})
cell=I(row, {type: "frame", name: "Cell", width: "fill_container"})
text=I(cell, {type: "text", name: "Name", content: "John", fill: "#18191C"})
```

---

## 图片

- Ardot 没有独立的 image 节点类型，图片是 frame / rectangle 的 `fills`。
- 草稿与线框用渐变占位，不同卡片换配色以示区分。
- 正式图片用宿主提供的图片生成或上传能力；不要编造图片 URL，也不要手写不存在的 `IMAGE` 填充。
- 每个图片节点最多生成一次；生成失败只允许重试一次，之后用占位或裁切解决，不要反复消耗。

```javascript
U("imageFrame", {fills: [{
  type: "GRADIENT_LINEAR",
  gradientStops: [
    {color: {r: 0.29, g: 0.73, b: 0.56, a: 1}, position: 0, boundVariables: {}},
    {color: {r: 0.16, g: 0.50, b: 0.73, a: 1}, position: 1, boundVariables: {}}
  ],
  gradientTransform: [[0.7, 0.7, 0], [-0.7, 0.7, 0.3]],
  opacity: 1, visible: true, blendMode: "NORMAL"
}]})
```

---

## 图标与 SVG

- 图标必须是 SVG 节点：`type: "frame"` + `svg` 属性，并设 `layout: "none"`。
- **禁止**用 emoji、Unicode 图形字符、单字母圆形作为图标。文本节点的 `content` 里也不能出现这些字符，无论是作为独立图标、标题前缀、标签装饰还是按钮后缀。禁止码段：U+2300–U+27BF、U+2600–U+27BF、U+1F300–U+1FAFF。
- 文本节点只放纯文本。图标与文字并排时，用横向 flex frame 装 `[图标 frame, 文本节点]`，不要拼成一个字符串。
- 重复使用的图标先做成组件，再用 `type: "ref"` 插入。
- 图标创建后截图确认渲染正确。

```javascript
icon=I("parent", {
  type: "frame",
  name: "Search Icon",
  layout: "none",
  svg: "<svg width=\"24\" height=\"24\" viewBox=\"0 0 24 24\" fill=\"none\" xmlns=\"http://www.w3.org/2000/svg\"><circle cx=\"11\" cy=\"11\" r=\"7\" stroke=\"#333\" stroke-width=\"2\"/><path d=\"M16 16L20 20\" stroke=\"#333\" stroke-width=\"2\" stroke-linecap=\"round\"/></svg>",
  width: 24,
  height: 24
})
```

---

## 效果

支持 `DROP_SHADOW` / `INNER_SHADOW` / `LAYER_BLUR` / `BACKGROUND_BLUR`。

- `showShadowBehindNode`：半透明填充（opacity < 1）设 `false`，否则阴影会透过来；完全不透明设 `true`，否则外阴影不渲染。
- `BACKGROUND_BLUR` 需要 `blurType`。
- 多层阴影按「近层紧、远层散」分层，模拟真实高度。
- 毛玻璃、金属、新拟态等复合配方见 `shared/effects-guide.md`。

```javascript
U("cardId", {effects: [
  {type: "DROP_SHADOW", color: {r: 0, g: 0, b: 0, a: 0.3}, offset: {x: 0, y: 20}, radius: 40, spread: -8, visible: true, blendMode: "NORMAL", showShadowBehindNode: true, boundVariables: {}},
  {type: "DROP_SHADOW", color: {r: 0, g: 0, b: 0, a: 0.6}, offset: {x: 0, y: 8}, radius: 24, spread: -4, visible: true, blendMode: "NORMAL", showShadowBehindNode: true, boundVariables: {}},
  {type: "DROP_SHADOW", color: {r: 0, g: 0, b: 0, a: 0.9}, offset: {x: 0, y: 4}, radius: 4, spread: 0, visible: true, blendMode: "NORMAL", showShadowBehindNode: false, boundVariables: {}}
]})
```

---

## 组件、变量与样式

- 组件实例、变体切换、`componentProperties`、`descendants` 覆盖 → `shared/component-instance.md`。
- token 绑定（`$:Set:Var`、`$lib:`）、`variableModes`、shared styles → `shared/token-binding.md`。
- 实例内部是虚拟节点，不能向实例或实例子节点插入新节点。
- 复制节点后子节点 ID 会重建，不能用旧 ID 去 `U()`，覆盖要写在 Copy 操作的 `descendants` 里。

---

## 生成后的最小自检

1. `batch_read` 回读：确认 `layoutMode` / `width` / `height` / `itemSpacing` 不是 `null`，且与预期一致。
2. 结构性修改后截图确认没有重叠、裁切、空模块。
3. 文本节点确认 `fill` 非空、宽度约束正确。
4. 分级验证与收敛阈值见 `shared/verification.md`。
