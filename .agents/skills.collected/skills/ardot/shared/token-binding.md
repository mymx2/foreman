# Token 绑定与样式绑定

适用：读取 design token、把变量或 shared style 绑到节点属性、切换变量模式、创建变量集。

三种机制的分工：

| 机制 | 作用 | 用法 |
|---|---|---|
| 设计变量（variables） | 可复用值，可多模式解析 | `batch_edit` 里用 `$:Set:Var` / `$<id>` 绑定 |
| shared styles | 一组属性的样式集合 | `textStyleId` / `fillStyleId` / `strokeStyleId` / `effectStyleId` |
| `apply_variables` | 创建或更新变量定义本身 | 独立工具调用 |

先把文件里的 token 读出来，再决定绑定方式：

```javascript
fetch_variables({})                    // 单文件可省略 fileUrl；可加 type / scope 过滤
fetch_styles({})                       // 列出全部本地 shared styles
```

有 token 时优先绑定，不要硬编码颜色和尺寸。没有 token 时用设计规范或模块配方里的原始值兜底。

---

## 1. 设计变量

### 引用形式

引用有两个维度：位置（本地 / 团队库）和寻址方式（名字 / GUID）。

| 位置 | 名字寻址 | GUID 寻址 |
|---|---|---|
| 本地 | `$:<SetName>:<VariableName>` | `$<variableId>` |
| 团队库 | `$lib:<libraryKey>:<SetName>:<VariableName>` | `$lib:<libraryKey>:<setId>:<variableId>` |

- 用 `fetch_variables` 返回的名字和 ID；团队库变量需要传 `enabledLibraryKey`。
- 同一处引用只用一种寻址方式，不要混用。名字可能变化时优先 GUID。
- 变量集名和变量名不能含 `$` 或 `:`。

### 可绑定的属性

**FLOAT**：`width`、`height`、`minWidth`、`maxWidth`、`minHeight`、`maxHeight`、`gap`（读回 `itemSpacing`）、`counterAxisSpacing`、`paddingTop/Right/Bottom/Left`、`padding`（四边一起绑）、`cornerRadius`、四个独立圆角、`strokeWeight`、四个独立描边宽度、`opacity`、`gridRowGap`、`gridColumnGap`。

**FLOAT（文本）**：`fontSize`、`letterSpacing`、`lineHeight`、`paragraphSpacing`、`paragraphIndent`。

**STRING**：`content`（也接受 FLOAT，自动转字符串）。

**BOOLEAN**：`visible`。

**COLOR**：`fill`、`stroke`，或 `fills` / `strokes` 数组里的 `color`。

```javascript
// 单色简写
U("nodeId", {fill: "$:Semantic:bg-color", stroke: "$:Semantic:border-color"})

// 数组内绑定
U("nodeId", {fills: [{type: "SOLID", color: "$:Semantic:surface-color"}]})
U("nodeId", {fills: [{
  type: "GRADIENT_LINEAR",
  gradientStops: [
    {color: "$:Brand:brand-start", position: 0},
    {color: "$:Brand:brand-end", position: 1}
  ],
  gradientTransform: [[1, 0, 0], [0, 1, 0]]
}]})
```

### 规则

- 类型必须匹配：数字属性用 FLOAT，填充/描边用 COLOR，可见性用 BOOLEAN，内容/字体族用 STRING。
- `x`、`y`、`rotation` 不支持变量绑定，写入会被跳过并给出警告。
- `padding: "$:Set:var"` 一次绑定四边。
- COLOR 绑定时以变量当前颜色作为回退值；取不到会给出警告。

### 解绑

把属性设为 `null`：

```javascript
U("nodeId", {opacity: null})
U("nodeId", {padding: null})
U("nodeId", {cornerRadius: null, strokeWeight: null, visible: null})
```

### 切换变量模式

变量集可以定义多个模式（Light / Dark、紧凑 / 宽松）。绑定指向变量本身，节点或祖先上的模式覆盖决定解析值。

```javascript
// GUID：variableSetId → modeId
U("frameId", {variableModes: [
  {variableSetId: "222:2", modeId: "345:1"},
  {variableSetId: "225:3", modeId: "612:1"}
]})

// 团队库
U("frameId", {variableModes: [{variableSetId: "412:2", modeId: "35:1", libraryKey: "<LibraryKey>"}]})

// 清除覆盖，回到继承
U("frameId", {variableModes: [{variableSetId: "222:2", modeId: null}]})
```

- `variableSetId` / `modeId` 用 `fetch_variables({ nodeId })` 返回的 `availableVariableModes` 里的真实值，不要编造。
- `libraryKey` 只在团队库变量集上出现。
- 模式沿树向下解析：子节点的显式模式优先于祖先，Auto 表示继承。
- 切换模式不改变绑定关系，只改变解析出来的值。
- 整个页面或主题切换时，优先在 page 或顶层 frame 上切一次，不要每个叶子重复设置。

---

## 2. Shared Styles

`<StyleId>` 就是样式节点的 nodeId。绑定方式：

| 位置 | 写法 |
|---|---|
| 本地 | `xxxStyleId: "<StyleId>"` |
| 团队库 | `xxxStyleId: "<StyleId>", libraryKey: "<LibraryKey>"` |

```javascript
title=I(parent, {type: "text", content: "Heading", textStyleId: "<StyleId>"})
card=I(parent, {type: "frame", fillStyleId: "<StyleId>"})
U("nodeId", {strokeStyleId: "<StyleId>"})
U("nodeId", {effectStyleId: "<StyleId>"})
libraryCard=I(parent, {type: "frame", fillStyleId: "<StyleId>", libraryKey: "<LibraryKey>"})
```

规则：

- ID 用裸 nodeId，不要加 `$`；`$` 是变量引用的前缀。
- `textStyleId` 只适用于 TEXT；其余三个适用于任何有对应属性的节点。
- 样式在渲染时优先于内联的 `fontName` / `fills` / `strokes` / `effects`。绑定样式时省略对应的内联值，除非要针对单个实例覆盖。
- 团队库样式需要同时给 `styleId` 和 `libraryKey`。
- 解绑设为 `null`：`U("nodeId", {textStyleId: null, fillStyleId: null})`。

---

## 3. `apply_variables`

用于创建或更新变量集与变量。默认 merge：只处理传入的变量，未提及的保持不变。`replace: true` 会删除未传入的变量集和变量，谨慎使用。

输入是「变量集名 → 定义」的映射：

```json
{
  "<SetName>": {
    "modes": ["<Mode1>", "<Mode2>"],
    "variables": {
      "<varName>": {
        "type": "FLOAT | BOOLEAN | STRING | COLOR",
        "valuesByMode": { "<Mode1>": "<value>", "<Mode2>": "<value>" },
        "scopes": ["ALL_FILLS"]
      }
    }
  }
}
```

- `modes` 省略时保留默认的 `Mode 1`；指定后第一个模式会替换 `Mode 1`。
- `valuesByMode` 按模式给值；也可以写 `"value"` 让所有模式共用同一个值。
- COLOR 值是 `{r, g, b, a}`（0–1），不是 hex 字符串。
- 常用 `scopes`：`ALL_SCOPES`、`ALL_FILLS`、`FRAME_FILL`、`SHAPE_FILL`、`TEXT_FILL`、`STROKE`、`STROKE_FLOAT`、`EFFECT_FLOAT`、`EFFECT_COLOR`、`OPACITY`、`WIDTH_HEIGHT`、`GAP`、`CORNER_RADIUS`、`TEXT_CONTENT`、`FONT_FAMILY`、`FONT_STYLE`、`FONT_SIZE`、`LINE_HEIGHT`、`LETTER_SPACING`、`PARAGRAPH_SPACING`、`PARAGRAPH_INDENT`。

> 下面 `Design Tokens` 以及前文的 `Semantic` / `Brand` 都是示例集名，不是白名单。命名规则见 `shared/naming-and-structure.md` §4。

```javascript
apply_variables({
  variables: {
    "Design Tokens": {
      modes: ["Light", "Dark"],
      variables: {
        bgColor: {
          type: "COLOR",
          valuesByMode: {
            Light: {r: 1, g: 1, b: 1, a: 1},
            Dark: {r: 0.1, g: 0.1, b: 0.1, a: 1}
          },
          scopes: ["ALL_FILLS"]
        },
        borderRadius: {type: "FLOAT", value: 8}
      }
    }
  }
})
```

`apply_variables` 负责定义变量；绑定仍走 `batch_edit` 的 `$` 语法。当前 schema 只有 `variables` + `replace`，不存在 `bindings` 参数。

---

## 验证

- 绑定后 `batch_read` 回读目标字段，确认不是 `null`，且等于写入的样式 / 变量 ID。
- 只回读到颜色值相同不足以证明绑定成功——变量解析值和硬编码值可能相同。
- `apply_variables` 之后调 `fetch_variables`，断言变量集名、模式列表、目标变量的 `scopes` 与写入一致。
- 切换模式后重新截图，确认主题确实变化。
- 解绑场景的期望值是 `null` 或字段缺席，不能套用「非空才算通过」。
