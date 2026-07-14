---
name: skills-cli
description: >
  Skills CLI（npx skills）完整使用指南，涵盖技能安装、使用、查找、更新、移除、初始化等全部命令，以及技能创建规范和兼容的智能体列表。
  当用户需要安装/管理技能、了解 Skills CLI 用法、创建自定义技能、查看支持的智能体列表、排查技能相关问题时使用。
license: MIT
metadata:
  origin: https://github.com/vercel-labs/skills
  version: 2026.06.17
  source: https://raw.githubusercontent.com/vercel-labs/skills/refs/heads/main/README.md
---

# Skills CLI 完整指南

Skills CLI（`npx skills`）是开放智能体技能生态系统的命令行工具，支持 **OpenCode**、**Claude Code**、**Codex**、**Cursor**、**Qoder** 等 60+ 智能体。

> 如果项目中存在名为 `skills` 的目录（发生命名冲突），`npx` 可能会报错，此时请使用 `pnpx`。

---

## 何时使用此技能

当用户出现以下情况时，请使用此技能：

- 需要安装、更新、移除或查找技能
- 想了解 Skills CLI 的某个命令用法
- 想创建自定义 SKILL.md 技能文件
- 遇到技能相关的错误或问题
- 想知道支持哪些智能体
- 想在 CI/CD 中自动化技能管理

---

## 核心命令速查

| 命令                         | 说明                         |
| ---------------------------- | ---------------------------- |
| `npx skills add <source>`    | 安装技能                     |
| `npx skills use <source>`    | 使用技能但不安装             |
| `npx skills list`            | 列出已安装技能（别名：`ls`） |
| `npx skills find [query]`    | 搜索技能（交互或关键词）     |
| `npx skills remove [skills]` | 移除已安装技能               |
| `npx skills update [skills]` | 更新已安装技能               |
| `npx skills init [name]`     | 创建新 SKILL.md 模板         |

---

## 安装技能（`skills add`）

### 支持的来源格式

```bash
# GitHub 简写（owner/repo）
npx skills add vercel-labs/agent-skills

# 完整 GitHub URL
npx skills add https://github.com/vercel-labs/agent-skills

# 指向仓库中某个 skill 的路径
npx skills add https://github.com/vercel-labs/agent-skills/tree/main/skills/web-design-guidelines

# GitLab URL
npx skills add https://gitlab.com/org/repo

# 任意 git URL
npx skills add git@github.com:vercel-labs/agent-skills.git

# 本地路径
npx skills add ./my-local-skills
```

### 安装参数

| 参数                      | 说明                                        |
| ------------------------- | ------------------------------------------- |
| `-g, --global`            | 安装到用户目录（而不是项目目录）            |
| `-a, --agent <agents...>` | 指定目标 agent（如 `claude-code`, `codex`） |
| `-s, --skill <skills...>` | 按名称安装指定 skill（使用 `'*'` 表示全部） |
| `-l, --list`              | 仅列出可用 skills，不执行安装               |
| `--copy`                  | 复制文件而不是使用符号链接                  |
| `-y, --yes`               | 跳过所有确认提示                            |
| `--all`                   | 安装所有 skills 到所有 agents（无提示）     |

### 安装示例

```bash
# 查看仓库中的 skills
npx skills add vercel-labs/agent-skills --list

# 安装指定 skills
npx skills add vercel-labs/agent-skills --skill frontend-design --skill skill-creator

# 安装带空格的 skill（需要加引号）
npx skills add owner/repo --skill "Convex Best Practices"

# 安装到指定 agents
npx skills add vercel-labs/agent-skills -a claude-code -a opencode

# 非交互安装（适用于 CI/CD）
npx skills add vercel-labs/agent-skills --skill frontend-design -g -a claude-code -y

# 安装仓库中所有 skills 到所有 agents
npx skills add vercel-labs/agent-skills --all

# 安装所有 skills 到指定 agents
npx skills add vercel-labs/agent-skills --skill '*' -a claude-code

# 安装指定 skills 到所有 agents
npx skills add vercel-labs/agent-skills --agent '*' --skill frontend-design
```

### 安装范围

| 范围       | 参数 | 位置                | 使用场景             |
| ---------- | ---- | ------------------- | -------------------- |
| **项目级** | 默认 | `./<agent>/skills/` | 随项目提交，团队共享 |
| **全局**   | `-g` | `~/<agent>/skills/` | 所有项目可用         |

### 安装方式

交互式安装时可选择：

| 方式                 | 说明                                             |
| -------------------- | ------------------------------------------------ |
| **符号链接（推荐）** | 每个 agent 指向统一源，便于更新                  |
| **复制（Copy）**     | 每个 agent 独立副本，适用于不支持 symlink 的环境 |

---

## 使用技能但不安装（`skills use`）

生成提示词用于某个技能，或以交互方式启动支持的编码 agent：

```bash
npx skills use vercel-labs/agent-skills@web-design-guidelines | claude
npx skills use vercel-labs/agent-skills --skill web-design-guidelines --agent claude-code
```

`skills use` 与 `skills add` 使用相同的来源解析方式，将选中的技能文件写入临时目录，仅将生成的提示词输出到 stdout（除非提供了 `--agent`）。

---

## 列出已安装技能（`skills list`）

```bash
# 列出全部（项目 + 全局）
npx skills list

# 仅全局
npx skills ls -g

# 按 agent 过滤
npx skills ls -a claude-code -a cursor
```

---

## 搜索技能（`skills find`）

```bash
# 交互式搜索（类似 fzf）
npx skills find

# 按关键词搜索
npx skills find typescript
```

浏览技能排行榜：**https://skills.sh/**

---

## 更新技能（`skills update`）

```bash
# 更新所有 skills（交互选择范围）
npx skills update

# 更新单个
npx skills update my-skill

# 更新多个
npx skills update frontend-design web-design-guidelines

# 只更新全局或项目
npx skills update -g
npx skills update -p

# 非交互模式（自动判断范围）
npx skills update -y
```

| 参数            | 说明                 |
| --------------- | -------------------- |
| `-g, --global`  | 仅更新全局           |
| `-p, --project` | 仅更新项目           |
| `-y, --yes`     | 跳过选择（自动判断） |
| `[skills...]`   | 指定更新某些 skills  |

---

## 移除技能（`skills remove`）

```bash
# 交互式删除
npx skills remove

# 删除指定 skill
npx skills remove web-design-guidelines

# 删除多个
npx skills remove frontend-design web-design-guidelines

# 删除全局
npx skills remove --global web-design-guidelines

# 从指定 agents 删除
npx skills remove --agent claude-code cursor my-skill

# 删除全部（无确认）
npx skills remove --all

# 从某 agent 删除所有 skill
npx skills remove --skill '*' -a cursor

# 从所有 agent 删除某 skill
npx skills remove my-skill --agent '*'

# 使用别名
npx skills rm my-skill
```

| 参数           | 说明                         |
| -------------- | ---------------------------- |
| `-g, --global` | 从全局删除                   |
| `-a, --agent`  | 指定 agent（`'*'` 表示全部） |
| `-s, --skill`  | 指定 skill                   |
| `-y, --yes`    | 跳过确认                     |
| `--all`        | 等价于删除全部               |

---

## 创建技能（`skills init`）

```bash
# 当前目录创建 SKILL.md
npx skills init

# 子目录创建
npx skills init my-skill
```

### SKILL.md 文件格式

技能是一个目录，包含 `SKILL.md` 文件，带有 YAML 头部：

```markdown
---
name: my-skill
description: 这个 skill 做什么、何时使用
---

# My Skill

Agent 执行该 skill 时的指令

## 使用场景

说明何时触发

## 步骤

1. 第一步
2. 第二步
```

**必填字段：**

- `name`：唯一标识（小写 + 连字符）
- `description`：简要说明

**可选字段：**

- `metadata.internal`：设为 `true` 时隐藏 skill（仅在 `INSTALL_INTERNAL_SKILLS=1` 时可见）

```markdown
---
name: my-internal-skill
description: 内部使用 skill
metadata:
  internal: true
---
```

### 技能发现路径

CLI 会在仓库中以下位置搜索技能：

- 根目录（如果包含 `SKILL.md`）
- `skills/`
- `skills/.curated/`、`skills/.experimental/`、`skills/.system/`
- 各智能体专属目录（如 `.claude/skills/`、`.agents/skills/`、`.qoder/skills/` 等）

---

## 主要智能体路径对照

| 智能体                   | `--agent` 值                 | 项目路径            | 全局路径                                 |
| ------------------------ | ---------------------------- | ------------------- | ---------------------------------------- |
| Claude Code              | `claude-code`                | `.claude/skills/`   | `~/.claude/skills/`                      |
| Codex                    | `codex`                      | `.agents/skills/`   | `~/.codex/skills/`                       |
| Cursor                   | `cursor`                     | `.agents/skills/`   | `~/.cursor/skills/`                      |
| Qoder                    | `qoder`                      | `.qoder/skills/`    | `~/.qoder/skills/`                       |
| Qoder CN                 | `qoder-cn`                   | `.qoder/skills/`    | `~/.qoder-cn/skills/`                    |
| Gemini CLI               | `gemini-cli`                 | `.agents/skills/`   | `~/.gemini/skills/`                      |
| GitHub Copilot           | `github-copilot`             | `.agents/skills/`   | `~/.copilot/skills/`                     |
| Windsurf                 | `windsurf`                   | `.windsurf/skills/` | `~/.codeium/windsurf/skills/`            |
| Amp / Replit / Universal | `amp`, `replit`, `universal` | `.agents/skills/`   | `~/.config/agents/skills/`               |
| Trae / Trae CN           | `trae`, `trae-cn`            | `.trae/skills/`     | `~/.trae/skills/` / `~/.trae-cn/skills/` |
| Kiro CLI                 | `kiro-cli`                   | `.kiro/skills/`     | `~/.kiro/skills/`                        |

完整列表包含 60+ 智能体，详见 https://github.com/vercel-labs/skills

---

## 环境变量

| 变量                      | 说明                                                    |
| ------------------------- | ------------------------------------------------------- |
| `INSTALL_INTERNAL_SKILLS` | 设为 `1` 或 `true` 以显示和安装标记为 `internal` 的技能 |
| `DISABLE_TELEMETRY`       | 禁用匿名使用遥测                                        |
| `DO_NOT_TRACK`            | 禁用遥测的替代方式                                      |

---

## 兼容性

技能遵循 [Agent Skills 规范](https://agentskills.io)，大部分智能体通用。部分特性可能仅限特定 agent：

| 特性            | 说明                                 |
| --------------- | ------------------------------------ |
| Basic skills    | 所有主流智能体均支持                 |
| `allowed-tools` | 大多数智能体支持（Kiro CLI 除外）    |
| `context: fork` | 仅 Claude Code 支持                  |
| Hooks           | 仅 Claude Code、Cline、Kiro CLI 支持 |

---

## 故障排查

| 问题                | 解决方案                                                                  |
| ------------------- | ------------------------------------------------------------------------- |
| "No skills found"   | 确保仓库包含有效的 `SKILL.md`（frontmatter 需有 `name` 和 `description`） |
| 技能未在 agent 加载 | 检查安装路径是否正确、frontmatter 是否为有效 YAML                         |
| 权限错误            | 确保对目标目录有写入权限                                                  |
| `npx` 命令报错      | 如果项目中有 `skills` 目录导致命名冲突，改用 `pnpx` 或 `vpx`              |

---

## 相关链接

- [Agent Skills 规范](https://agentskills.io)
- [技能目录](https://skills.sh)
- [Vercel Agent Skills 仓库](https://github.com/vercel-labs/agent-skills)
- [Claude Code Skills 文档](https://code.claude.com/docs/en/skills)
- [Qoder Skills 文档](https://docs.qoder.com/cli/Skills)
- [Cursor Skills 文档](https://cursor.com/docs/context/skills)

---

## 许可证

MIT
