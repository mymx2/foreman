# Ardot MCP Cheat Sheet · 伞技能共享速查

本文件覆盖**所有模块共用**的 Ardot MCP 工具用法。每个模块自己的
特定调用模式在各自 SKILL.md / references 里。

> 各模块已带一份更专注的 cheatsheet（如 `modules/showcase/references/ardot-api-cheatsheet.md`），
> 冲突时**以模块自己的为准**，本文件作为兜底。

---

## 占位符约定

| 占位符 | 含义 | 来源 |
|---|---|---|
| `<fileUrl>` | 当前文件 URL | `fetch_file_info` 返回的 `fileUrl`；单文件打开可省略，多文件时必传 |
| `<fileId>` | 文件 ID | `fetch_file_info` 返回；只作标识，MCP 工具参数用 `fileUrl` |
| `<fileKey>` / `<targetFileKey>` | 模块文档里的历史别名 | 等同 `<fileId>`；调用工具时改用 `fileUrl` 或省略 |
| `<nodeId>` | 任意节点 ID，格式 `123:456` | selection / batch_read 返回 |
| `<pageId>` / `<targetPageId>` | 页面节点 ID | `fetch_editor_state` 返回的 `currentPage.id` |
| `<frameId>` / `<outerFrameId>` | Frame 节点 ID | selection / batch_edit 返回 |
| `<gridFrameId>` | grid 模块新建的网格 Frame ID | `batch_edit` Insert 后返回 |
| `<absolute temp dir>` | 本机可写的绝对路径目录 | Windows 用 `D:/tmp` / `C:/Users/<you>/AppData/Local/Temp`；macOS/Linux 用 `/tmp`。**不要写死**，按当前环境选 |

**showcase 模块专用占位符**（在 `modules/showcase/references/` 里出现）：

| 占位符 | 含义 |
|---|---|
| `<computedOuterWidth>` / `<computedOuterHeight>` | 按 `modules/showcase/references/skeleton-spec.md` §4 公式算出的 outer Frame 宽 / 高 |
| `<fromLocateX>` / `<fromLocateY>` | `locate_available_space` 返回的 x / y 坐标 |
| `<existingComponentNodeId>` | 已存在的 component / component set 节点 ID（用 `type:"ref"` 时填） |
| `<existingCanvasNodeId>` | 已存在的普通 FRAME 节点 ID（用 `C` 复制时填） |

**INSTANCE 内部节点**：ID 形如 `instanceId;childId`（分号路径），仅在 `batch_read` 设 `resolveInstances: true` 时出现。

**中文占位符**：`modules/layout-adapt/SKILL.md` 的命令行示例用 `<文件ID>` / `<节点ID1,节点ID2,...>` / `<id>` 等中文占位符，含义与上表 `<fileId>` / `<nodeId>` 一致。

---

## 属性命名：写入侧 vs 读回侧

Ardot 的布局属性有简写和完整名两套。实测 `batch_read` 同时返回两套，写入用简写已验证可用。

| 语义 | 写入（batch_edit） | 读回（batch_read） |
|---|---|---|
| 布局方向 | `layout: "horizontal" \| "vertical" \| "none"` | `layout` 与 `layoutMode`（同值，后者大写） |
| 换行 | `layout: "wrap"` | `layout: "wrap"` + `layoutMode: "HORIZONTAL"` + `layoutWrap: "WRAP"` |
| 子项间距 | `gap: 16` | `gap` 与 `itemSpacing`（同值） |
| 内边距 | `padding: [T,R,B,L]` 或 `paddingTop/...` | `paddingTop/Right/Bottom/Left` |
| 换行行距 | `counterAxisSpacing` | `counterAxisSpacing` |

- 写示例统一用简写；读回断言用哪套都行，不要假定字段缺席。
- `layoutMode` 的取值只有 `NONE` / `HORIZONTAL` / `VERTICAL`；换行状态看 `layoutWrap`。

---

## 调用原则

1. **先读，再算，再写，再读**：`fetch_editor_state` → `batch_read` → 计算 → `batch_edit` → `batch_read` 校验。
2. `batch_edit` 用当前 **`operations` 字符串语法**，不要再用旧版 `edits[]` JSON 数组。
3. 每个 Insert / Copy 必须有 **binding 名**（`outer=I(...)`），便于后续操作引用和校验。
4. 单次 `batch_edit` 操作数 **≤ 25**，建议 ≤ 20；超过时按「外层容器 → 内部节点」拆批，提交后 `batch_read` 验证再继续。

---

## 工具清单

### 0. `fetch_file_info` / `create_new_page`

文件由 Ardot 客户端打开，MCP 没有 `create_design` / `open_design` 之类的工具。

- 单文件打开时，所有工具都可省略 `fileUrl`；多文件打开时必须传 `fetch_file_info` 返回的 `fileUrl`，不传会返回可选文件列表。
- `fetch_file_info` 返回 `fileName` / `fileUrl` / `fileId` / `permission`。写操作前确认 `permission` 是 `readwrite`。
- 新建页面用 `create_new_page`，返回 `pageId`，作为后续顶层节点的 `parentId`。这不是新建文件。
- 需要文件结构时先 `fetch_editor_state`；它返回 `currentPage` / `pageList` / `currentPageTopLevelNodes` / `selection` / `viewport`，不返回 `fileKey`。
- 空页面的根 PageID 以 `fetch_editor_state` 返回的 `currentPage.id` 为准。

### 1. `fetch_editor_state`

读当前打开的文件、页面和选中对象。所有模块的入口。

```javascript
fetch_editor_state({
  includeSchema: false,
  includeGeneralEditInstructions: false
})
// 返回：{ currentPage: { id, name }, pageList, currentPageTopLevelNodes, selection, viewport }
```

**规则**：

- `selection` 优先作为输入源
- 没有 selection 且用户没显式给 nodeId 时，问一次，不要瞎猜
- 设置 `includeSchema: false` 减少 token 占用（大多数模块用不到 schema）

---

### 2. `batch_read`

读节点属性。创建后校验、状态分析都用它。

```javascript
batch_read({
  nodeIds: ["<nodeId1>", "<nodeId2>"],
  readDepth: 3,
  resolveInstances: true,   // 需要展开 INSTANCE 内部时设 true
  properties: ["width", "height", "absoluteBoundingBox", "layoutMode", ...]
})
```

**关键参数**：

- `fileUrl`：可省略；多文件时必传
- `readDepth`：默认 2，需要看子结构时设 3–5，只看直接子节点设 1；超过整体节点预算会压缩为 ID / name / type，并在 `omitted` 里列出父节点
- `resolveInstances`：`true` 时展开 INSTANCE 子树，返回的文本 ID 形如 `instanceId;childId`（分号路径）
- `properties`：明确列出要哪些字段，不要全读

**常见坑**：

- 用了 `batch_edit` 的 binding 名（如 `outer`）而不是真实 nodeId → 报错「节点不存在」。等 `batch_edit` 返回真实 ID 再读。
- 节点数多时单次返回不全 → 分批（见 `modules/layout-adapt/SKILL.md` §大设计稿分批读取）

---

### 3. `batch_edit`

创建 / 更新 / 删除 / 复制 / 移动节点。**operations 字符串语法**。

#### Insert（I）

```javascript
outer=I(document, {
  type: "frame",
  name: "标题",
  x: 100, y: 100,
  width: "hug_contents",
  height: "hug_contents",
  layout: "vertical",
  gap: 50,
  paddingTop: 0, paddingRight: 0, paddingBottom: 0, paddingLeft: 0,
  fills: [{ type: "SOLID", color: { r: 0, g: 0, b: 0 } }]
})
```

#### Update（U）

```javascript
U("<nodeId>", {
  width: "hug_contents",
  height: "fill_container"
})
```

#### Delete（D）

```javascript
D("<nodeId>")
```

#### Copy（C）

```javascript
cellCopy=C("<sourceNodeId>", <parentBinding>, {
  name: "新名字"
})
```

**Copy 较重**，每张画板单独一个 `batch_edit`，避免一次失败整批回滚。

#### Move（M）

```javascript
M("<nodeId>", <newParentBinding>, { name: "可选改名" })
```

#### 关于 `type: "ref"` vs `C`（复制）

**硬规则**：`type: "ref"` 只能引用 component / component set，普通 FRAME 用 ref 会报错：

```
Insert failed: ref: ID is not a component/component set: <nodeId>
```

判断流程：

```
输入画板 reusable === true（是组件）？
  ├─ 是 → 用 type: "ref"（可与源同步）
  └─ 否（普通 FRAME，最常见）→ 用 Copy (C) 复制快照
```

**默认用 C**，不要先试 ref。

#### 关于 padding 语法

`padding` **不接受 CSS 简写字符串**（`"0 200 200 200"` 会报错）。

✅ 正确写法（二选一）：

```javascript
// 数组形式 [T, R, B, L]
padding: [0, 200, 200, 200]

// 或四个独立属性
paddingTop: 0, paddingRight: 200, paddingBottom: 200, paddingLeft: 200

// 四边相等时单个数字
padding: 200
```

#### 关于 divider（分割线）

在 auto-layout 行/列里加分隔线：

- ✅ `RECTANGLE + height:"fill_container"`（自动撑满相邻元素）
- ❌ `LINE + rotation + 写死 length`（会出现「只显示上半段」bug）

```javascript
divider=I(cellRow, {
  type: "rectangle",
  name: "分割线",
  width: 1,
  height: "fill_container",
  fills: [{ type: "SOLID", color: { r: 1, g: 1, b: 1 } }]
})
```

#### 关于 line 节点

`type: "line"` 是**矢量描边**，跟 rectangle 行为差异很大：

| 属性 | line 的行为 |
|---|---|
| `width` | 线的"长度"，跟方向无关 |
| `height` | 恒为 0，传了也被忽略 |
| `rotation` | 决定方向：`0` = 水平向右，`90` = 垂直向下 |
| `(x, y)` | 线的起点，不是中心 |
| 颜色 | 用 `strokes` + `strokeWeight`，**不能用 fills** |
| `strokeWeight` | 可以是小数（如 `0.1`） |

详见 `modules/grid/SKILL.md`。

#### binding 与 Copy 的边界

- binding 只在同一次 `batch_edit` 调用内有效；跨调用引用父级要用真实 nodeId。
- 每个 Insert / Copy 都要有 binding 名，即使后续不用。
- Copy 会给被复制节点及其子节点分配新 ID。想改复制出来的子节点，必须在 Copy 操作里用 `descendants`；事后再 `U(oldChildId)` 会失败。
- `U()` 不能改 `id` / `type` / `ref` 三个字段。
- Insert 一次只能插一个节点，子节点用后续 Insert 配合 binding 或父级真实 ID。
- 不能往 INSTANCE 及其子节点里插入新节点（虚拟节点）。

#### 渐变方向矩阵

| 方向 | gradientTransform |
|---|---|
| 左 → 右 | `[[1, 0, 0], [0, 1, 0]]` |
| 右 → 左 | `[[-1, 0, 1], [0, -1, 1]]` |
| 上 → 下 | `[[0, 1, 0], [-1, 0, 1]]` |
| 下 → 上 | `[[0, -1, 1], [1, 0, 0]]` |
| 45° | `[[1, 1, 0], [-1, 1, 0.5]]` |

---

### 4. `locate_available_space`

在目标页面找未占用区域。**放置新画板前必调**。

```javascript
locate_available_space({
  pageId: "<pageId>",
  width: <width>,
  height: <height>,
  padding: 400,
  direction: "right"
})
// 返回：Find empty space at x: 0, y: 0 on Page (...)
```

**硬规则**：

- 页面用 `pageId`；围绕某个节点找空间用 `nodeId`。两者只能传一个，传错或都传会失败。
- `padding >= 400`（工具默认 100，按本技能的间距规则显式传）
- 默认 `direction: "right"`；横向不够时改 `"down"`（要先跟用户确认）
- 返回的 `x/y` **原样**写入 frame，**不要做任何偏移计算**
- 失败后**不要降级为手写坐标**，换 page / 清理画布 / 改 MATRIX 让用户选

---

### 5. `capture_screenshot`

生成后给用户在对话里预览。

```javascript
capture_screenshot({
  nodeIds: ["<outerFrameId>"],
  screenShotDir: "<absolute temp dir>"
})
```

**规则**：

- `screenShotDir` 必须是已存在的本地目录
- 一次传齐要验证的 nodeIds，少于 10 个
- 校验通过后再截图
- 超大节点（> 2000px）按 group 分段截
- 截图是验证手段，不代替 Ardot 链接
- **每个 repair batch 最多 2 次**：一次在全部修复后，一次在二次修复后。禁止「改一处截一次」的循环

---

### 5.5 `capture_layout`

检查容器布局问题（间距、重叠、裁切、溢出、大块空白）。

```javascript
capture_layout({ parentId: "<frameId>", maxDepth: 2, problemsOnly: true })
```

**规则**：

- `parentId` 必须是容器节点。传 Page 会报 `Root node must be a container, not a page`，需要对每个顶层 frame 分别调用。
- `problemsOnly` 默认 `true`；返回 `problems` / `problemDetails`，`LARGE_EMPTY_AREA` 这类 warning 是候选问题，要结合截图和设计意图判断。
- 结果大时会写入 JSONL 文件，用 nodeId grep 单节点详情。
- 结构检查优先用它，截图留给视觉终判。

---

### 6. `get_available_fonts`

确认目标文件可用字体，避免中文 TEXT 创建失败。

```javascript
get_available_fonts({ keywords: ["PingFang SC"] })
// 返回：{ fonts: [{ family, styles: [...] }], totalFamilies, truncated }
```

**规则**：

1. 优先查 `PingFang SC`
2. 没有时按目标文件现有中文字体降级
3. **不猜 style 名称**；用工具返回的准确 `family + style`
4. `keywords` 是最多 20 项的数组，不是字符串
5. 字体降级后在结果说明里标 TODO，提醒设计师统一

---

### 7. `fetch_styles` / `fetch_variables`

读目标文件的 design token。生成新节点时优先绑 token，不要硬编码颜色。

```javascript
fetch_styles({})                      // 单文件可省略 fileUrl
fetch_variables({})                   // 可加 type / scope 过滤
fetch_variables({ nodeId: "<nodeId>" })  // 读该节点可切换的 variableModes
```

**规则**：

- 有 token 时通过 `VARIABLE_ALIAS` 绑定
- 没 token 时用 preset / 规则里的 raw 值兜底
- 不确定 token 名时先 `fetch_styles` 列出再选

---

### 8. `apply_variables`

用于**创建或更新变量集与变量**。默认 merge 模式，只新增或更新传入的变量；`replace: true` 会删除未传入的变量集和变量。

> 与绑定区分：把变量绑到节点属性用 `batch_edit` 的 `$:Set:Var` / `$<id>` 语法，`apply_variables` 负责定义变量。
> 当前 schema 只有 `variables` + `replace`，不存在 `bindings` 参数。

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
        }
      }
    }
  }
})
```

变量名和变量集名不能含 `$` 或 `:`。完整输入格式与 scopes 枚举见 `shared/token-binding.md`。

---

### 8.5 `export_nodes`

把节点导出为文件。

```javascript
export_nodes({
  nodeIds: ["<nodeId1>", "<nodeId2>"],
  outputDir: "<绝对或项目内目录>",
  format: "png",        // png / jpeg / webp / svg
  scale: 1              // svg 固定 1x
})
```

规则：

- 图片格式单批建议 ≤5 个节点；SVG 不限。
- 文件名由工具生成，形如 `{safeFileName}-{timestamp}.{ext}`；**必须使用返回的 `nodeId → path` 映射**，不要按 nodeId 推导文件名。
- 保存返回映射为 `{ "requestedNodeIds": [...], "mapping": {...}, "outputDir": "..." }`，交给 `shared/scripts/verify-export-mapping.js` 校验。
- 只导出 `scan_exportable_resources` 返回的可导出节点；不要整页/整画板导出。

### 9. `fetch_guidelines`

读 Ardot 官方设计 / 编码规范。生成代码或大型布局前调用。

```javascript
fetch_guidelines({ topic: "code" })       // 画板 → 代码
fetch_guidelines({ topic: "landing-page" })
fetch_guidelines({ topic: "mobile-app" })
fetch_guidelines({ topic: "slides" })
fetch_guidelines({ topic: "posters" })
fetch_guidelines({ topic: "web-app" })
fetch_guidelines({ topic: "table" })
fetch_guidelines({ topic: "tailwind" })
```

**适用**：本伞技能主要操作节点树；当任务超出节点操作、涉及「该做成什么样」时调。

---

## 属性速查与常见写错

| ❌ 无效写法 | ✅ 正确写法 | 说明 |
|---|---|---|
| `textColor` | `fill` | 文本颜色也走 fill |
| `backgroundColor` / `color` / `fillColor` | `fill` | 背景就是 frame 的 fill |
| `borderRadius` | `cornerRadius` | |
| `alignItems: "center"` | `counterAxisAlignItems: "CENTER"` | 交叉轴 |
| `justifyContent: "center"` | `primaryAxisAlignItems: "CENTER"` | 主轴 |
| `verticalAlign` | `counterAxisAlignItems` | 垂直对齐 |
| `fontWeight: "bold"` / `"semibold"` | `"700"` / `"600"` | 只用数字字符串 |

字重：`"100"` Thin、`"200"` Extra Light、`"300"` Light、`"400"` Regular、`"500"` Medium、`"600"` Semi Bold、`"700"` Bold、`"800"` Extra Bold、`"900"` Black。

字重优先用 `fontName.style`（如 `"Bold"`）；`fontWeight` 只用数字字符串。回读断言看 `fontName.style`，不看 `fontWeight`。

尺寸：数字 = 固定像素；`"fill_container"` = 撑满父级；`"fill_container(200)"` = 撑满且最小 200；`"hug_contents"` = 包裹内容。

文本默认没有颜色，必须设 `fill`。字体用 `fontName: {family, style}`，`style` 取自 `get_available_fonts` 的准确值。

---

## 调用顺序回顾（通用）

```text
1. fetch_editor_state      // 拿 file + page + selection
2. batch_read              // 读输入节点结构
3. (可选) locate_available_space  // 放置新画板前
4. batch_edit              // operations 字符串，≤25 op
5. batch_read              // 校验
6. capture_screenshot      // 截图
```

正常路径 5–6 次工具调用。超过 10 次通常意味着骨架被拆碎创建，应合并为更清晰的批量操作。

---

## 弱事务风险

`batch_edit` 单次失败会回滚**当前 block**，但**跨 block 没有原子性**：
第 3 批失败时，前 2 批已经画进画布了。

**对策**：

- 拆批时按「外层 → 内层」顺序
- 每批提交后立即 `batch_read` 验证
- 失败时用 `batch_edit` 执行 `D(binding)` 清理半成品，**不要硬 retry**

---

## 命名空间回退（NO_ADAPTER）

Ardot MCP 工具可能暴露在多个命名空间（`mcp__ardot__*` / `mcp__ardot-design__*`）。

**实测案例**：`mcp__ardot__*` 调用返回 `NO_ADAPTER: No adapter found for routeKey ...`，同时刻 `mcp__ardot-design__*` 是活跃可用的。

**处理顺序**：

1. 某命名空间**连续 3 次**报 `NO_ADAPTER` → 切到另一个重试同一调用（`ardot` ↔ `ardot-design`）
2. 用 `fetch_file_info` / `fetch_editor_state` 探测哪个命名空间能正常返回，后续**全程固定用那一个**
3. 两个命名空间都不通 → 走 `shared/troubleshooting.md` §MCP 连接

详细依赖与阻塞条件见 `shared/dependencies.md`。
