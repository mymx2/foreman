# Ardot API Cheat Sheet / 调用速查

本文是 `ardot-showcase-autolayout` 使用到的 Ardot MCP 工具速查，不是完整 API 文档。对调用方式不确定时读取。

## 调用原则

- 先读状态，再算尺寸，再找空位，再批量写入，最后读回校验。
- `batch_edit` 使用当前 Ardot MCP 的 **`operations` 字符串语法**，不要再使用旧版 `edits[]` JSON 数组。
- 每个 Insert / Copy 操作必须使用 binding 名，便于后续操作引用新节点。
- 单次 `batch_edit` 控制在 25 个操作以内；超过时按「外层容器 → 内部节点」拆成多次。

---

## 1. `fetch_editor_state`

用途：读取当前打开文件、页面和选中对象。用于 Step 1 确定输入画板和目标页面。

```javascript
fetch_editor_state()
// 返回示例：{ fileKey, currentPage: { id, name }, selection: [...] }
```

规则：

- `currentPage.id` 作为默认目标页面。
- `selection` 优先作为输入源：用户选中若干画板或 page 时，直接使用选中项。
- 若 `selection` 为空且用户没有显式给 nodeId，反问一次：请选中画板或提供 nodeId。
- 如果 `selection` 中包含已有 showcase frame，用户可能想扩展旧展示区，不要直接新建；先确认。

---

## 2. `locate_available_space`

用途：在目标页面寻找未占用区域。Step 3 写入 outer frame 前必须调用。

```javascript
locate_available_space({
  fileId: "<targetFileKey>",
  nodeId: "<targetPageId>",
  width:  <computedOuterWidth>,
  height: <computedOuterHeight>,
  padding: 400,
  direction: "right"
})
// 返回示例：{ x, y }
```

注意：

- `nodeId` 是页面 ID，不是文件 ID。
- `padding` 不低于 400。
- 默认 `direction: "right"`；如果横向空间不足，可在用户确认后改 `down`。
- 删除旧 showcase 后重建，也要重新调用，不复用旧坐标。
- 返回的 `x/y` 原样写入 outer frame，不做额外偏移计算。

---

## 3. `batch_edit`

用途：批量创建、复制、更新、移动节点。使用 `operations` 字符串。

### 最小 outer FRAME 示例

```javascript
batch_edit({
  fileId: "<targetFileKey>",
  operations: `
outer=I(document, {
  type: "frame",
  name: "产品团队_登录流程·新版登录流·衍生展示区",
  x: <fromLocateX>,
  y: <fromLocateY>,
  width: "hug_contents",
  height: "hug_contents",
  layout: "vertical",
  gap: 50,
  padding: 0,
  fill: "#000000"
})
`
})
```

### 创建 TEXT

```javascript
title=I(titleRow, {
  type: "text",
  content: "登录流程",
  fontSize: 96,
  fill: "#FFFFFF",
  fontName: { family: "PingFang SC", style: "Regular" }
})
```

### 把已有画板放进 cell：先判断它是不是 component（关键）

**硬规则**：`type: "ref"` 只能引用 component / component set。普通 FRAME 画板用 ref 会直接失败，报错：

```text
Insert failed: ref: ID is not a component/component set: <nodeId>
```

判断流程：

```text
输入画板 reusable === true（是组件）？
  ├─ 是 → 用 type: "ref"（可与源同步）
  └─ 否（普通 FRAME，最常见）→ 用 Copy (C) 复制快照
```

多数设计稿里的"画板/屏"都是普通 FRAME，不是组件，**默认应当用 Copy (C)**，不要先试 ref。

#### A. 组件 → `type: "ref"`

```javascript
cellRef=I(cellColumn, {
  type: "ref",
  ref: "<existingComponentNodeId>",
  name: "默认态"
})
```

源组件后续更新时，展示区里的 cell 可同步。

#### B. 普通 FRAME → Copy (C)（默认路径）

```javascript
cellCopy=C("<existingCanvasNodeId>", cellColumn, {
  name: "默认态"
})
```

Copy 会重建子树并分配新 ID，原画布不受影响（满足"不要删除/改动已有画布"的诉求）。

注意：Copy 较重，**每张画板单独一个 batch_edit**，避免一次失败导致整批回滚。复制后的节点若带 `layoutAlign: "STRETCH"` + `counterAxisSizingMode: "FIXED"`，在固定宽度的 cell column 里不会变形，无需额外处理；但要在 batch_read 里确认 width 没被拉伸。

### 更新节点属性

```javascript
U("<nodeId>", {
  width: "hug_contents",
  height: "hug_contents"
})
```

### Column divider：用 RECTANGLE + fill_container（不要用 LINE）

分割线插在 cell row（HORIZONTAL）里两个模块的 cell 之间。**必须**用 `RECTANGLE` + `height:"fill_container"`，让它自动撑满行高；禁止用 `LINE + rotation + 写死 length`（会导致「只显示上半段」bug）。

```javascript
// cell row 是 layout:"horizontal"，行高由最高 cell 决定
divider=I(cellRow, {
  type: "rectangle",
  name: "分割线",
  width: 1,
  height: "fill_container",   // 关键：自动跟随行内最大 cell 高度，无需 two-pass
  fill: "#FFFFFF"             // 有 divider-subtle token 时优先绑 token；raw 兜底用 white α=0.16
})
```

实测：相邻 cell 高度 600/500/550 时，fill_container 分割线自动撑到 600，完整拉通。生成后仍应 `batch_read` 读 divider `absoluteBoundingBox.height`，确认 ≥ 相邻 cell 最大高度的 95%。

---

## 4. `batch_read`

用途：创建后读取节点属性，用于验证尺寸、对齐和 sizing。

```javascript
batch_read({
  fileId: "<targetFileKey>",
  nodeIds: ["<outerFrameId>"],
  properties: ["width", "height", "absoluteBoundingBox", "primaryAxisSizingMode", "counterAxisSizingMode"]
})
```

校验重点：

- outer width / height 是否符合公式（允许 ±32px）。
- title row / subtitle / group label / cell row 左边缘是否一致（`absoluteBoundingBox.x` 容差 ±1px）。
- titlebar 是否是 FIXED width = computedOuterWidth。
- cell row / UI region 是否保持 hug。

---

## 5. `get_available_fonts`

用途：确认目标文件可用字体，避免中文 TEXT 创建失败。

规则：

1. 优先查 `PingFang SC`。
2. 若没有，按目标文件现有中文字体降级。
3. 不猜字体 style 名称；使用工具返回的准确 family + style。
4. 字体降级后，在结果说明里标 TODO，提醒设计师后续统一字体。

---

## 6. `capture_screenshot`

用途：生成后截取 outer frame，给用户在对话里预览。

```javascript
capture_screenshot({
  fileId: "<targetFileKey>",
  nodeIds: ["<outerFrameId>"],
  screenShotDir: "<absolute temp dir>"
})
```

规则：

- 校验通过后再截图。
- oversized 节点可按 group 分段截图，不要一次截超大图导致失败。
- 截图用于确认视觉结果，不代替 Ardot 链接。

---

## 常见错误与详细诊断

| 现象 | 可能原因 | 修复步骤 |
|---|---|---|
| `fetch_editor_state` 返回空或报错 | Ardot 文件未打开，或 MCP 连接中断 | 让用户确认 Ardot 已打开目标文件；MCP 已连接后重试 |
| selection 为空 | 用户没选中画板，也没提供 nodeId | 反问一次：请选中要排版的画板，或告诉我 nodeId |
| `VARIABLE_ALIAS validation error` | 给 `type: "ref"` 插入时传了不支持的属性 | 先无 props 插入，再用 `U` 更新实例属性 |
| outer width = 402，而不是公式值 | 某个 inner FRAME 的 counterAxisSizingMode 是 FIXED | 改成 hug / `width: "hug_contents"` |
| titlebar 宽度塌成文字宽度 | titlebar 用了 hug 或 STRETCH | 改为 FIXED，width = computedOuterWidth |
| 标题和内容左边缘不齐 | titlebar 未设 `counterAxisAlignItems: MIN` 或 title row 误用 SPACE_BETWEEN | 按 skeleton-spec「对齐硬契约」修复 |
| `batch_edit` 部分操作失败 | 单次超过 25 个操作，或 binding 顺序错误 | 拆成 2 次以上 batch_edit；先外层，再内层 |
| `batch_read` 返回节点不存在 | 用了 binding 名而不是真实 nodeId | 等 batch_edit 返回真实 id 后再 batch_read |
| `locate_available_space` 失败 | 页面空间不足或输入尺寸过大 | 提示用户换页/清理空间，或改 MATRIX/向下找位 |
| 生成后 Ardot 看不到内容 | 客户端视图缓存 | 让用户按 Cmd+R 或点击画布空白处刷新 |
| 坐标与空位返回不一致 | batch_edit 中手写或偏移了 x/y | 原样使用 locate 返回的 x/y |
| 字体缺失 | 目标文件没有指定 fontName | 调 `get_available_fonts` 后选择可用字体 |
| 分割线只显示上半段、没拉通到底 | divider 用了 `LINE + 写死 length`，length 小于实际行高 | 改用 `RECTANGLE + height:"fill_container"`；生成后 `batch_read` 确认高度 ≥ 相邻 cell 最大高度 95% |

---

## 调用顺序回顾

```text
Step 1 → fetch_editor_state      // 读当前 page + selection
Step 1 → batch_read              // 读取输入画板结构
Step 2 → locate_available_space  // 找空位
Step 3 → batch_edit              // operations 字符串，创建骨架
Step 4 → batch_read              // 校验尺寸和对齐
Step 5 → capture_screenshot      // 截图预览
```

正常路径 5-6 次工具调用即可。调用次数过多通常说明骨架被拆碎创建，应合并为更清晰的批量操作。
