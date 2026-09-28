---
name: showcase
metadata:
  version: "1.0.9"
  absorbed_from: "ardot-showcase-autolayout-1.0.9"
agent_created: true
description: |
  在 Ardot 中把多个已有画板自动编排成可交付的衍生展示区。
  当用户需要多状态对照、设计评审看板、流程演示、角色/设备矩阵时使用；
  也作为 AI 设计工作流的收尾节点，把零散画板整理成结构化展示区并输出
  可分享链接。
  不适用于：生成画板内部 UI、导出 PDF/PNG、跨多个 Ardot 文件编排、
  判断业务方案好坏。
---

# 衍生展示区自动编排

把多张零散画板整理成可交付评审的结构化展示区。

## Outcome Contract

- **Outcome**：选中的画板被编排成一个结构化的衍生展示区，含标题栏、分组、单元格小标题，不覆盖已有画布，并输出可分享的 Ardot 链接。
- **Done when**：通过本 SKILL.md §关键门禁 5 项（分组已确认、locate_available_space 已调、布局轴向通过校验、左边缘对齐、命名/日期/圆角合规），以及 `references/skeleton-spec.md` §7 的完整 19 条。
- **Evidence**：`batch_read` 校验尺寸/对齐/token/divider 通过；`capture_screenshot` 预览无错位；返回的 Ardot 链接可打开。
- **Output**：1 个 `衍生展示区` outer frame（100px 圆角）+ 截图预览 + Ardot 链接。
- **Authorization**：只做编排，不改输入画板内部；生成前仅在覆盖旧展示区 / 同名已存在 / 单次大量写入时确认一次。

## 10 秒上手

**前提**：已连接 Ardot MCP，并在 Ardot 里打开目标文件。

**典型用法**：

- 在 Ardot 里选中几个画板或一个 page，说「把选中的画板用这个技能重新排版」。
- agent 刚生成一批 Ardot 画板后，说「顺便用这个技能规范化排版」。
- 直接说「把这几个画板排成评审展示区，发我链接」。

**技能做什么**：自动排版 → 标题栏 + 分组 + 单元格小标题 → 找空位放置（不覆盖已有画板）→ 截图预览 → 返回 Ardot 链接。

想调整时直接说：「白底 / 灰底 / 演示模式」「竖排 / 矩阵」「按设备分组」「日期写 X」。

## 适用与边界

适合多状态页面对照、设计评审看板、流程演示、角色/设备矩阵，以及 AI 设计工作流的收尾整理。

不处理：生成画板内部 UI、导出 PDF/PNG、跨多个 Ardot 文件编排、判断业务方案好坏。

## 四步工作流

```text
Step 1   确定输入画板 + 目标页面
Step 1.5 场景理解与分组确认
Step 2   判断布局轴向
Step 3   生成骨架 + 校验 + 截图 + 返回链接
```

### Step 1 — 确定输入画板 + 目标页面

输入源优先级：

1. 当前 Ardot selection（最常见）。
2. agent 上一步刚生成的 nodeId 列表。
3. 用户显式提供的 nodeId / page。

输出位置默认当前页面。若读取不到文件、页面或 selection，只问一次：「请在 Ardot 里选中要排版的画板，或告诉我 nodeId / 目标页面。」环境依赖见 `references/dependencies.md`。

### Step 1.5 — 场景理解与分组确认

先解决「谁和谁是一组」，再决定「怎么排」。仅凭尺寸、命名或坐标推断分组属于拍脑袋。

满足以下全部条件可直接沿用原结构：用户已明确分组；入口节点已有清晰容器语义；不存在多种合理解释。否则必须给 2-4 个分组选项，并包含「保持原样」和「自定义」。详情见 `references/scene-grouping.md`。

### Step 2 — 判断布局轴向

先看原始画布是否已有明确排布意图，再用尺寸评分选择 ROW / COLUMN / MATRIX：

- 原始内容已明显竖排，或横排会生成超长展示区时，优先 COLUMN / MATRIX。
- 整页多状态默认 ROW，但必须通过宽高阈值校验；超过阈值不继续硬横排。
- 裸组件、组件目录、多维内容按 `references/layout-decision-tree.md` 的评分规则选择。

不要只按内容类型拍板。详细决策树见 `references/layout-decision-tree.md`。

### Step 3 — 生成骨架并放置

1. 先通过 `references/quality-harness.md` 的不可触犯契约：不能超宽/超长、不能覆盖已有画布、不能交付未校验结果。
2. 按 `references/skeleton-spec.md` §4 计算 outer 尺寸。
3. 调用 `locate_available_space`，`padding >= 400`，严禁手写坐标。
4. 使用 `batch_edit({ operations: ... })` 生成结构，不使用旧版 `edits[]`。
5. 生成前仅在以下任一条件满足时确认一次，普通新增展示区不额外确认：
   - 覆盖旧展示区（同名已存在）
   - 单次写入操作数 > 50（即 batch_edit 需要拆 3 批以上，按每批 ≤20 op 估算）
   - 输入画板数量 > 6
6. 生成后用 `batch_read` 校验。校验项 ↔ 字段对照表：

   | 校验项 | 读取字段 | 通过条件 |
   |---|---|---|
   | 尺寸 | `width` / `height` / `absoluteBoundingBox` | 与 `skeleton-spec.md` §4 公式值一致（容差 ±32px） |
   | 对齐 | `absoluteBoundingBox.x` | title row / subtitle / group label / cell row 左边缘一致（容差 ±1px） |
   | token | `fills` / `strokes` 内的 `boundVariables` | 优先使用 preset 绑定的 token；raw 值兜底时与设计 token 语义一致 |
   | divider | divider 节点的 `absoluteBoundingBox.height` | ≥ 相邻 cell 最大高度的 95% |
   | 主题对比度 | titlebar 与 outer 的 `fills` 配对色 | 按 `presets.md` 当前 preset 的 background/foreground 配对，不是任意取色 |
   | sizing | `primaryAxisSizingMode` / `counterAxisSizingMode` | titlebar 是 FIXED width = computedOuterWidth；cell row / UI region 是 hug |

   调用示例：

   ```javascript
   batch_read({
     fileId: "<targetFileKey>",
     nodeIds: [outerFrameId],
     readDepth: 4,
     properties: ["width","height","absoluteBoundingBox","fills","strokes",
                  "primaryAxisSizingMode","counterAxisSizingMode"]
   })
   ```
7. 调用 `capture_screenshot` 展示预览，并返回 Ardot 链接。

骨架数值、对齐硬契约、mini-title、column divider、Reject Signals 统一维护在 `references/skeleton-spec.md`。

## 关键门禁

交付前至少通过以下 5 项；完整 19 条见 `references/skeleton-spec.md` §7。

1. 分组已确认或满足跳过条件，没有打散原始结构。
2. 已调用 `locate_available_space`，且没有覆盖/贴边已有画板。
3. 布局轴向已通过原始排布 + 尺寸阈值 + 语义评分校验，没有生成超长横排。
4. Titlebar / subtitle / group / cell row 左边缘对齐，主题对比度可读。
5. 命名、日期、subtitle、mini-title、outer 100px 圆角符合规范。

出错时不要抛原始 API 报错，要翻译成「发生了什么 + 用户该做什么」。恢复策略见 `references/quality-harness.md`。

## 参考文件

按需读取，不必预读：

- `references/dependencies.md`：Ardot MCP 依赖与环境排查。
- `references/scene-grouping.md`：Step 1.5 分组确认方法。
- `references/layout-decision-tree.md`：ROW / COLUMN / MATRIX 判断。
- `references/skeleton-spec.md`：骨架数值合同、对齐、Reject Signals。
- `references/naming-conventions.md`：outer 名称、titlebar、subtitle、mini-title 文案。
- `references/presets.md`：主题 preset、自然语言切换与对比度。
- `references/ardot-api-cheatsheet.md`：Ardot MCP 调用速查。
- `references/quality-harness.md`：运行恢复与发布前 smoke tests。
- `references/faq.md`：完整常见问题。
- `references/examples.md`：完整示例。
- `assets/preset-config.json`：实际主题数值配置，生成前必须读取。

共享底座（伞技能层）：

- `../../shared/mcp-cheatsheet.md`：覆盖更多 MCP 工具；冲突时以本模块 `references/ardot-api-cheatsheet.md` 为准。
- `../../shared/dependencies.md`：跨模块的依赖与阻塞条件；本模块特有依赖见 `references/dependencies.md`。
- `../../shared/troubleshooting.md`：跨模块的环境排查对照表。

## 版本历史

版本号以本章为单一来源，须与 `assets/preset-config.json` 的 `$version` 保持一致。

### v1.0.9 (2026-06-24)

- 修复 版本号多处不一致问题，统一 frontmatter / preset-config / 发布包 / 发布页为同一版本号
- 新增 不可触犯契约：禁止超宽/超长画布、禁止覆盖已有画布、禁止交付未校验结果
- 优化 发包命名规则为 `skill-name-version.zip`

更早版本历史（v1.0.2 – v1.0.8）已被本伞技能吸收时截断，详见原始技能包。

> 当前版本由伞技能 `ardot` 吸收，保留 1.0.9 版本号以维持与 `assets/preset-config.json.$version` 的一致性。
