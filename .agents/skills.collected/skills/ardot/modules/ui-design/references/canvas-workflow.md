# 画布操作流程（UI 交付）

在 Ardot 画布上从零创作或重组界面时的执行顺序。组合式小改走精简路径。

相关文档：

- 工具参数与批处理约束 → `../../../shared/mcp-cheatsheet.md`
- 布局、文本、图标、表格规则 → `../../../shared/design-rules.md`
- 组件实例与变体 → `../../../shared/component-instance.md`
- token / 样式绑定 → `../../../shared/token-binding.md`
- 验证层级与收敛 → `../../../shared/verification.md`

---

## Step 0 — 确认文件

- 文件由 Ardot 客户端打开，MCP 不提供 create/open 文件。
- 单文件可省略 `fileUrl`；多文件时传 `fetch_file_info` 返回的 `fileUrl`。
- `fetch_file_info` 确认 `fileName` / `fileId` / `permission`；写操作需要 `readwrite`。
- 新建页面用 `create_new_page`，返回的 `pageId` 作为顶层节点 `parentId`。

## Step 1 — 读状态

- 新建空文件：根 PageID 通常是 `0:1`，直接作为根容器，跳过 `fetch_editor_state`。
- 打开已有文件：`fetch_editor_state({includeSchema: false})` + `fetch_variables` 并行。
- 修改已有画面：按需加 `batch_read` / 截图。

## Step 2 — 判断创作还是组合

- **创作**（新页面、整页改版、换风格）→ 继续 Step 3。
- **组合**（加按钮、补模块、移动节点）→ 跳到 Step 5，先读 `../../../shared/design-rules.md`；修改前后各做一次结构读取用于对比。

## Step 3 — 加载规范

- 按 `modules/ui-design/SKILL.md` 的优先级加载对应领域规范。
- 涉及组件实例、变体、实例覆盖 → 加载 `../../../shared/component-instance.md`。
- 涉及 token 或 shared styles → 加载 `../../../shared/token-binding.md`。
- 用户给出的风格约束、`DESIGN.md`、设计 token 优先于内置规范；内置规范只补用户没指定的部分。

## Step 4 — 找空位

- 新建顶层画板前调 `locate_available_space`；参数、坐标用法与失败处理见 `../../../shared/mcp-cheatsheet.md` §4 与 `../../../shared/troubleshooting.md`。

## Step 5 — 执行

- 构建顺序：**结构 → 内容 → 样式**。
- 批大小、binding、Copy、实例操作的限制按 `../../../shared/mcp-cheatsheet.md` 与 `../../../shared/component-instance.md` 执行，本文不复述。
- 图标、文本、图片、效果的写法按 `../../../shared/design-rules.md` 执行。
- 画布文案默认跟随用户提示语言；用户指定目标语言时用指定语言。首次生成前用一句话说明本次使用的语言。

## Step 6 — 验证

按 `../../../shared/verification.md` 执行分级选择、末批内容回读、交付边界截图与收敛阈值，本文不复述具体数值。
