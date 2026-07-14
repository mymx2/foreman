---
name: find-skills
description: 当用户提出诸如“我该如何做 X（即skill）”、“找一个用于 X 的技能”、“有没有可以……的技能”等问题，或表达扩展能力的兴趣时，帮助用户发现和安装智能体技能。当用户寻找可能以可安装技能形式存在的功能时，应使用此技能。
license: MIT
metadata:
  origin: https://github.com/mymx2/skills/skills/find-skills
  author: mymx2 <https://github.com/mymx2>
  version: 2026.05.11
  source: https://skills.sh/vercel-labs/skills/find-skills <MIT>
---

# 查找技能

此技能可帮助你从开放的智能体技能生态系统中发现并安装技能。 技能即skill的中文翻译

## 何时使用此技能

当用户出现以下情况时，请使用此技能：

- 询问“我该如何做X”，其中X可能是一项已有技能对应的常见任务
- 表示“为X找一个技能”或“有没有针对X的技能”
- 询问“你能做 X 吗”，且 X 属于某项专业能力
- 表达出扩展智能体能力的兴趣
- 希望搜索工具、模板或工作流
- 提到希望在设计、测试、部署等特定领域获得帮助

## 什么是 Skills CLI？

Skills CLI（`npx skills`）是开放智能体技能生态系统的包管理器。技能是模块化包，可通过专业知识、工作流和工具来扩展智能体的能力。

**核心命令：**

- `npx skills find [query]` - 以交互方式或通过关键词搜索技能
- `npx skills add <package>` - 从 GitHub 或其他来源安装技能
- `npx skills check` - 检查技能更新
- `npx skills update` - 更新所有已安装的技能

**浏览技能请访问：** https://skills.sh/

## 如何帮助用户查找技能

### 第一步：了解他们的需求

当用户请求帮助时，请明确以下几点：

1. 所属领域（例如：React、测试、设计、部署）
2. 具体任务（例如：编写测试、制作动画、审查 PR）
3. 该任务是否足够常见，以至于很可能已有对应技能

### 第二步：优先查看排行榜

在运行 CLI 搜索之前，请先查看 [skills.sh 排行榜](https://skills.sh/)，确认该领域是否已有知名技能。排行榜按总安装量对技能进行排序，展示最受欢迎且经过实战检验的选项。

例如，Web 开发领域的热门技能包括：

- `vercel-labs/agent-skills` — React、Next.js、Web 设计（每项安装量均超 10 万）
- `anthropics/skills` — 前端设计、文档处理（安装量超 10 万）

### 第三步：搜索技能

如果排行榜未涵盖用户的需求，请运行 find 命令：

```bash
npx skills find [query]
```

例如：

- 用户询问“如何让我的 React 应用更快？” → `npx skills find react performance`
- 用户询问“你能帮我审查 PR 吗？” → `npx skills find pr review`
- 用户表示“我需要生成更新日志” → `npx skills find changelog`

### 第四步：推荐前验证质量

**不要仅凭搜索结果就推荐技能。** 务必核实以下几点：

1. **安装量** — 优先选择安装量 1K+ 的技能。对安装量不足 100 的保持谨慎。
2. **来源信誉** — 官方来源（如 `vercel-labs`、`anthropics`、`microsoft`）比未知作者更可靠。
3. **GitHub Star 数** — 检查源仓库。来自 Star 数不足 100 的仓库的技能应持怀疑态度。

### 第五步：向用户展示选项

找到相关技能后，请向用户提供以下信息：

1. 技能名称及其功能
2. 安装量及来源
3. 用户可运行的安装命令
4. 在 skills.sh 上了解更多详情的链接

示例回复：

```
我找到了一个可能对你有帮助的技能！"react-best-practices" 技能提供了
来自 Vercel 工程团队的 React 和 Next.js 性能优化指南。
（18.5 万次安装）

安装命令：
npx skills add vercel-labs/agent-skills@react-best-practices

了解更多：https://skills.sh/vercel-labs/agent-skills/react-best-practices
```

### 第六步：提供安装协助

如果用户希望继续，你可以代为安装该技能：

```bash
npx skills add <owner/repo@skill> -g -y
```

`-g` 标志表示全局安装（用户级），`-y` 用于跳过确认提示。

## 常见技能类别

搜索时，可参考以下常见类别：

| 类别     | 示例查询关键词                           |
| -------- | ---------------------------------------- |
| Web 开发 | react, nextjs, typescript, css, tailwind |
| 测试     | testing, jest, playwright, e2e           |
| DevOps   | deploy, docker, kubernetes, ci-cd        |
| 文档     | docs, readme, changelog, api-docs        |
| 代码质量 | review, lint, refactor, best-practices   |
| 设计     | ui, ux, design-system, accessibility     |
| 效率工具 | workflow, automation, git                |

## 高效搜索技巧

1. **使用具体关键词**：“react testing” 比单纯的 “testing” 更好
2. **尝试同义/替代词**：如果 “deploy” 没结果，可尝试 “deployment” 或 “ci-cd”
3. **关注热门来源**：许多技能来自 `vercel-labs/agent-skills` 或 `ComposioHQ/awesome-claude-skills`

## 未找到相关技能时

如果不存在相关技能：

1. 说明未找到现有技能
2. 提供利用你的通用能力直接协助完成该任务
3. 建议用户可通过 `npx skills init` 自行创建技能
4. 如果项目中已经存在 `skills` 目录，会导致命名撞车（name collision），造成错误，可使用 `pnpx` 或 `vpx` 运行

示例：

```
我搜索了与 "xyz" 相关的技能，但未找到匹配项。
我仍然可以直接帮你完成这项任务！需要我继续吗？

如果你经常需要处理此类任务，也可以自行创建技能：
npx skills init my-xyz-skill
```
