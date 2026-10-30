---
name: ardot
description: |
  当用户在 Ardot 设计工具里要驱动 MCP 做画板生成、自动编排或文本布局适配时使用。
  按用户意图路由到具体子模块（grid / showcase / layout-adapt），
  并共享 MCP 调用规约与排障手册。
  不适用于：UI 视觉品味审计（走 ui 技能）、浏览器证据采集（走
  chrome 技能）、行为异常排查（走 hunt 技能）。
  Triggers: "ardot", "画板", "frame", "网格", "grid",
  "自动编排", "showcase", "评审展示", "布局适配", "文本适配",
  "响应式适配", "翻译适配", "打开 Ardot", "Ardot 文件".
metadata:
  version: "0.1.2"
  author: rbz-one
  modules: [grid, showcase, layout-adapt, design-to-code, ui-design]
---

# Ardot 伞技能

本技能是 Ardot 设计工具 MCP 操作的**总入口**，本身不实现具体功能，
按用户意图路由到子模块，并维护**所有子模块共用**的 MCP 调用底座。

## Outcome Contract

- **Outcome**：用户的 Ardot 意图被路由到正确的子模块，且整个调用过程遵循共享 MCP 规约。
- **Done when**：用户描述的需求命中能力地图中**唯一一个**模块；该模块的 SKILL.md 被加载并执行；执行结果符合本 SKILL.md 的共用硬约束（batch_edit 语法、locate_available_space、读写顺序、命名空间回退、padding 语法、失败处理）。
- **Evidence**：`fetch_editor_state` 成功返回 file + page + selection；`batch_edit` 调用使用 `operations` 字符串；`batch_edit` 后有 `batch_read` 校验；放置新画板前调过 `locate_available_space`。
- **Output**：路由决策说明（命中模块 + 关键词）+ 模块执行结果。
- **Authorization**：只路由，不实现具体画板操作；具体创建/修改由命中的模块自己负责。

## 10 秒上手

1. 在 Ardot 客户端里打开目标文件，确认 MCP server 运行中（`127.0.0.1:50501`）
2. 用户说「加网格」→ 路由 `modules/grid`
3. 用户说「把这几张画板排成展示区」→ 路由 `modules/showcase`
4. 用户说「翻译一下，别溢出」→ 路由 `modules/layout-adapt`

任何模块执行前都先读 `shared/dependencies.md` 确认环境。

## 能力地图（Capability Map）

| 模块 | 一句话用途 | 入口 |
|---|---|---|
| `modules/grid` | 给选中 Frame 加 0.1px 像素对齐网格 | `modules/grid/SKILL.md` |
| `modules/showcase` | 把多张画板自动编排成可交付的衍生展示区 | `modules/showcase/SKILL.md` |
| `modules/layout-adapt` | 响应式 / 多语言下修复文本溢出与塌陷 | `modules/layout-adapt/SKILL.md` |
| `modules/design-to-code` | 设计稿转前端代码，或从网站反向提取设计规范与 token | `modules/design-to-code/SKILL.md` |
| `modules/ui-design` | 按交付类型（Web/移动/落地页/表格）加载 UI 领域设计规范 | `modules/ui-design/SKILL.md` |

**模块边界**：每个模块只解决自己那一类问题，互不调用。组合任务由
本 SKILL.md 路由层调度（先 layout-adapt 修溢出，再 showcase 编排）。

## 路由表

按用户关键词进入对应模块。**只读对应模块的 SKILL.md**，不要预读全部。

| 用户说 | 进入 |
|---|---|
| 加网格 / 对齐参考线 / pixel grid | `modules/grid/SKILL.md` |
| 自动编排 / 评审展示 / 多状态对照 / 衍生展示区 / showcase | `modules/showcase/SKILL.md` |
| 布局适配 / 文本适配 / 翻译适配 / 国际化适配 / 防溢出 / 响应式 | `modules/layout-adapt/SKILL.md` |
| 设计稿转代码 / 转前端代码 / 生成 HTML / 提取 design token / 网站风格提取 | `modules/design-to-code/SKILL.md` |
| 设计页面 / 创建界面 / 做落地页 / 设计后台 / 设计 App / 设计系统 | `modules/ui-design/SKILL.md` |
| 以上都不是，但跟 Ardot 有关 | 先问清楚用户要做什么，再决定 |
| 跨模块组合（先适配后排版） | 按依赖顺序串行调用多个模块 |

**模块间冲突**：不会同时命中两个模块。如果用户意图真的跨模块
（如「先翻译再排版」），按依赖顺序逐模块执行，每个模块内部状态
独立。

## 共用硬约束（所有模块必须遵守）

以下约束适用于本伞技能下的**任何** Ardot MCP 调用。各模块自己的
硬约束在各自 SKILL.md 里定义，不在此重复。

### 1. batch_edit 语法

- 必须用当前 Ardot MCP 的 `operations` **字符串语法**（`I/U/D/C/M`），
  **禁止**用旧版 `edits[]` JSON 数组
- 每个 Insert / Copy 必须有 binding 名（如 `outer=I(...)`），便于后续
  操作引用和校验
- 单次 batch_edit 操作数 **≤ 25**，建议 ≤ 20；超过时按「外层容器 →
  内部节点」拆批，提交后用 `batch_read` 验证再继续

### 2. 放置新画板

- **禁止手写坐标**。必须调 `locate_available_space`，且 `padding >= 400`
- `locate_available_space` 失败时，要么换 page，要么跟用户确认改布局，
  **不要**降级为手写坐标

### 3. 读写顺序

```
fetch_editor_state → batch_read → 计算 → batch_edit → batch_read 校验
```

任何一步跳过都可能导致状态漂移。特别是 `batch_edit` 之后的
`batch_read` 校验，**不能省**。

### 4. 命名空间回退（NO_ADAPTER）

Ardot MCP 工具可能暴露在多个命名空间（`mcp__ardot__*` /
`mcp__ardot-design__*`）。某个命名空间连续 3 次报 `NO_ADAPTER` 时，
先切到另一个重试，而不是判定 Ardot 不可用。完整流程见
`shared/dependencies.md` §命名空间回退。

### 5. padding 语法

`batch_edit` 的 `padding` 不接受 CSS 简写字符串（`"0 200 200 200"` 会
报错）。正确写法：数组 `[T, R, B, L]`，或四个独立属性
`paddingTop/Right/Bottom/Left`。四边相等用单个数字。

### 6. 失败处理

- 某批 `batch_edit` 失败：用 `batch_edit` 执行 `D(binding)` 清理半
  成品，告诉用户具体错误，**不要硬 retry**
- 环境排查：先查 `shared/troubleshooting.md` 的对照表
- 任何 MCP 工具连续 3 次报错 → 停下来诊断，不要继续操作

## 共享底座（Shared References）

模块共用，**模块自己的 SKILL.md 会按需引用**：

- `shared/mcp-cheatsheet.md` — Ardot MCP 工具速查（每个工具的用途 / 参数 / 常见坑）
- `shared/dependencies.md` — 环境依赖、命名空间回退、阻塞条件
- `shared/troubleshooting.md` — 常见故障对照表（症状 → 原因 → 处置）

## 模块文档索引

各模块自包含，独立可用。文档结构：

| 模块 | 主文档 | 子文档 |
|---|---|---|
| grid | `modules/grid/SKILL.md` | `modules/grid/references/advanced-grids.md` |
| showcase | `modules/showcase/SKILL.md` | 10 个 references + `assets/preset-config.json` |
| layout-adapt | `modules/layout-adapt/SKILL.md` | `modules/layout-adapt/scripts/layout-adaptation.js` + `modules/layout-adapt/scripts/ardot-client.js` |
| design-to-code | `modules/design-to-code/SKILL.md` | 4 个 references（workflow ×2 + code/tailwind 规则） |
| ui-design | `modules/ui-design/SKILL.md` | 4 个 references（web-app / landing-page / mobile-app / table 规范） |

## 出错时

- **不知道路由到哪个模块** → 列出能力地图问用户，不要瞎猜
- **MCP 连不上** → `shared/troubleshooting.md` §MCP 连接
- **用户要的功能不在能力地图里** → 直接说「这个能力本技能还没有」，
  不要硬塞到现有模块
- **多模块组合出错** → 回滚到上一个稳定状态，从出错的模块单独排查

## Out of scope

- 不做 UI 视觉品味审计 / 设计方向锁定（那是 `ui` 技能的事）
- 不写前端代码（Ardot 画板到代码用 `fetch_guidelines(topic="code")`）
- 不管 Ardot 客户端 UI 操作（点击菜单、拖拽等）
- 不直连云端 Ardot API（所有操作走本地 MCP）

## 与其他技能的边界

- **`ui` 技能**：管 CSS / DOM / Web 前端的视觉品味。本技能管 Ardot 画板
  的节点树操作，**不引用 ui 的规则**
- **`hunt` 技能**：行为异常、回归排查走 hunt；本技能只管「按规约正确
  调用 MCP」
- **`chrome` 技能**：浏览器证据采集走 chrome；本技能不打开浏览器

## 版本历史

按日期倒序，最新版本在前。

### v0.1.2 (2026-09-28)

- 修复 forge 校验问题：description 补 trigger cue、新增 Outcome Contract、scripts 引用路径修正

### v0.1.1 (2026-09-28)

- 新增 Outcome Contract

### v0.1.0 (2026-09-28)

- 初始版本，伞技能骨架
- 吸收 `D:\data\tmp\repros` 下三个子技能：
  - grid-generator v0.3.1 → `modules/grid`
  - ardot-showcase-autolayout v1.0.9 → `modules/showcase`
  - layout-adaptation → `modules/layout-adapt`
- 抽取共享底座：`shared/mcp-cheatsheet.md`、`shared/dependencies.md`、`shared/troubleshooting.md`
