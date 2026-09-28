# Ardot MCP Cheat Sheet · 伞技能共享速查

本文件覆盖**所有模块共用**的 Ardot MCP 工具用法。每个模块自己的
特定调用模式在各自 SKILL.md / references 里。

> 各模块已带一份更专注的 cheatsheet（如 `modules/showcase/references/ardot-api-cheatsheet.md`），
> 冲突时**以模块自己的为准**，本文件作为兜底。

---

## 占位符约定

| 占位符 | 含义 | 来源 |
|---|---|---|
| `<fileKey>` | 当前打开文件的 ID | `fetch_editor_state` 返回的 `fileKey` 字段；下游 `batch_read` / `batch_edit` / `locate_available_space` 等工具的参数名是 `fileId`，**填的就是这个 fileKey**（参数名 ≠ 字段名，注意映射） |
| `<targetFileKey>` | 同 `<fileKey>`，模块文档里的别名 | 同上 |
| `<nodeId>` | 任意节点 ID，格式 `123:456` | selection / batch_read 返回 |
| `<pageId>` / `<targetPageId>` | 页面节点 ID | `fetch_editor_state` 返回的 `currentPage.id` |
| `<frameId>` / `<outerFrameId>` | Frame 节点 ID | selection / batch_edit 返回 |
| `<gridFrameId>` | grid 模块新建的网格 Frame ID | `batch_edit` Insert 后返回 |
| `<absolute temp dir>` | 本机可写的绝对路径目录 | Windows 用 `D:/tmp` / `C:/Users/<you>/AppData/Local/Temp`；macOS/Linux 用 `/tmp`。**不要写死**，按当前环境选 |

**showcase 模块专用占位符**（在 `modules/showcase/references/` 里出现）：

| 占位符 | 含义 |
|---|---|
| `<computedOuterWidth>` / `<computedOuterHeight>` | 按 `skeleton-spec.md` §4 公式算出的 outer Frame 宽 / 高 |
| `<fromLocateX>` / `<fromLocateY>` | `locate_available_space` 返回的 x / y 坐标 |
| `<existingComponentNodeId>` | 已存在的 component / component set 节点 ID（用 `type:"ref"` 时填） |
| `<existingCanvasNodeId>` | 已存在的普通 FRAME 节点 ID（用 `C` 复制时填） |

**INSTANCE 内部节点**：ID 形如 `instanceId;childId`（分号路径），仅在 `batch_read` 设 `resolveInstances: true` 时出现。

**中文占位符**：`modules/layout-adapt/SKILL.md` 的命令行示例用 `<文件ID>` / `<节点ID1,节点ID2,...>` / `<id>` 等中文占位符，含义与上表 `<fileKey>` / `<nodeId>` 一致。

---

## 调用原则

1. **先读，再算，再写，再读**：`fetch_editor_state` → `batch_read` → 计算 → `batch_edit` → `batch_read` 校验。
2. `batch_edit` 用当前 **`operations` 字符串语法**，不要再用旧版 `edits[]` JSON 数组。
3. 每个 Insert / Copy 必须有 **binding 名**（`outer=I(...)`），便于后续操作引用和校验。
4. 单次 `batch_edit` 操作数 **≤ 25**，建议 ≤ 20；超过时按「外层容器 → 内部节点」拆批，提交后 `batch_read` 验证再继续。

---

## 工具清单

### 1. `fetch_editor_state`

读当前打开的文件、页面和选中对象。所有模块的入口。

```javascript
fetch_editor_state({
  includeSchema: false,
  includeGeneralEditInstructions: false
})
// 返回：{ fileKey, currentPage: { id, name }, selection: [...] }
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
  fileId: "<fileKey>",
  nodeIds: ["<nodeId1>", "<nodeId2>"],
  readDepth: 3,
  resolveInstances: true,   // 需要展开 INSTANCE 内部时设 true
  properties: ["width", "height", "absoluteBoundingBox", "layoutMode", ...]
})
```

**关键参数**：

- `readDepth`：默认 1，需要看子结构时设 2–5；超过 500 子节点会压缩
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
  layoutMode: "VERTICAL",
  itemSpacing: 50,
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

---

### 4. `locate_available_space`

在目标页面找未占用区域。**放置新画板前必调**。

```javascript
locate_available_space({
  fileId: "<fileKey>",
  nodeId: "<pageId>",
  width: <width>,
  height: <height>,
  padding: 400,
  direction: "right"
})
// 返回：{ x, y }
```

**硬规则**：

- `nodeId` 是**页面 ID**，不是文件 ID
- `padding >= 400`
- 默认 `direction: "right"`；横向不够时改 `"down"`（要先跟用户确认）
- 返回的 `x/y` **原样**写入 frame，**不要做任何偏移计算**
- 失败后**不要降级为手写坐标**，换 page / 清理画布 / 改 MATRIX 让用户选

---

### 5. `capture_screenshot`

生成后给用户在对话里预览。

```javascript
capture_screenshot({
  fileId: "<fileKey>",
  nodeIds: ["<outerFrameId>"],
  screenShotDir: "<absolute temp dir>"
})
```

**规则**：

- 校验通过后再截图
- 超大节点（> 2000px）按 group 分段截
- 截图是验证手段，不代替 Ardot 链接
- **每个 repair batch 最多 2 次**：一次在全部修复后，一次在二次修复后。禁止「改一处截一次」的循环

---

### 6. `get_available_fonts`

确认目标文件可用字体，避免中文 TEXT 创建失败。

**规则**：

1. 优先查 `PingFang SC`
2. 没有时按目标文件现有中文字体降级
3. **不猜 style 名称**；用工具返回的准确 `family + style`
4. 字体降级后在结果说明里标 TODO，提醒设计师统一

---

### 7. `fetch_styles` / `fetch_variables`

读目标文件的 design token。生成新节点时优先绑 token，不要硬编码颜色。

```javascript
fetch_styles({ fileId: "<fileKey>" })
fetch_variables({ fileId: "<fileKey>" })
```

**规则**：

- 有 token 时通过 `VARIABLE_ALIAS` 绑定
- 没 token 时用 preset / 规则里的 raw 值兜底
- 不确定 token 名时先 `fetch_styles` 列出再选

---

### 8. `apply_variables`

把已有节点的 fills / strokes 等属性绑定到 token。

```javascript
apply_variables({
  fileId: "<fileKey>",
  nodeId: "<nodeId>",
  bindings: [{ field: "fills", variableId: "<varId>" }]
})
```

---

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
