---
name: design-cli
description: 'Guides creating, validating, diffing, and exporting DESIGN.md design-system files. Use when the user needs to create or edit a DESIGN.md, lint design tokens with the @google/design.md CLI, compare two versions, or export tokens to Tailwind/DTCG formats. Not for general UI design, typography review, or screenshot polish tasks without a DESIGN.md artifact.'
when_to_use: 'DESIGN.md, design tokens, 设计系统文件, 设计 token 校验, designmd, tailwind token 导出'
license: MIT
metadata:
  origin: https://github.com/mymx2/skills/skills/design-cli
  author: mymx2 <https://github.com/mymx2>
  version: 2026.08.19
---

# DESIGN.md

DESIGN.md 把设计系统写成 agent 可读的契约：YAML token 给出精确值，prose 解释为什么。只写 prose 不写 token 的"设计规范"对 agent 是装饰品——lint 过的 token 才是事实源。

## Outcome Contract

- **Outcome**: 一份通过 `lint` 校验（exit 0）的 DESIGN.md，或一次有 JSON 证据的 diff/export 操作。
- **Done when**: CLI 输出 JSON 中 `summary.errors` 为 0；改动后的 token 值全部来自用户输入或既有 token 引用，没有凭空编造。
- **Evidence**: `lint` / `diff` / `export` 的 JSON 输出与退出码。
- **Output**: 修改后的 DESIGN.md，加上 lint 结果摘要。
- **Authorization**: 可以创建和编辑 DESIGN.md、运行 CLI。不要安装全局依赖、不要修改项目构建配置，除非用户明确要求。

## Mode Picker

| Ask                         | Mode                                  |
| --------------------------- | ------------------------------------- |
| 新建或修改 DESIGN.md        | [Create or Edit](#create-or-edit)     |
| 校验现有文件                | [Validate](#validate)                 |
| 对比两个版本                | [Compare Versions](#compare-versions) |
| 导出 token 到 Tailwind/DTCG | [Export Tokens](#export-tokens)       |

## Create or Edit

1. 已有 DESIGN.md 就先读，保留用户的 token 命名与 prose 语气；没有则按 references/format-spec.md 的结构新建。
2. token 值必须来自用户或既有引用（`{colors.primary}` 形式），禁止编造色值、字号。
3. prose 节解释设计意图（为什么选这个值、怎么用），不重复 token 值本身。
4. 完成后必须走 [Validate](#validate)，把 lint JSON 摘要贴给用户。

## Validate

1. 运行 `npx @google/design.md lint DESIGN.md`（Windows 上用 `designmd` 别名，见 Gotchas）。
2. error 级 findings 必须修完再交付；warning 级逐条判断，不修的在交付说明里列出。
3. 完整命令与选项表见 references/cli-reference.md。

## Compare Versions

1. 运行 `npx @google/design.md diff <before> <after>`。
2. 退出码 1 表示 after 引入回归（更多 error/warning），先把回归清零再谈 token 变更本身。
3. 向用户汇报 `tokens` 里的 added/removed/modified，而不是贴整段 JSON。

## Export Tokens

1. 确认目标格式：Tailwind v3 用 `json-tailwind`，Tailwind v4 用 `css-tailwind`，跨工具流通用 `dtcg`。
2. 运行 `npx @google/design.md export --format <fmt> DESIGN.md` 并重定向到目标文件。
3. 导出后提醒用户：DESIGN.md 是源头，导出产物不要手改，改完重新导出。

## Hard Rules

- **先 lint 再交付。** 任何创建/编辑以 lint exit 0 为完成标准，没有例外。
- **token 是规范值，prose 是理由。** 两者冲突时改 prose，不改 token 迎合文字。
- **不编造设计值。** 颜色、字号、间距要么用户给，要么从既有 token 引用派生。
- **Windows 用 `designmd`。** 任何平台不确定时都优先 `designmd` 别名，行为完全一致。

## Rationalization Smells

- "改动很小，不用跑 lint"——broken-ref 和 contrast-ratio 都是小改动引入的；lint 只要一秒。
- "prose 写详细点就等于设计系统"——没有 token 的 prose 无法被 lint，也无法被导出，对 agent 不可执行。
- "warning 可以忽略"——warning 里藏着 missing-primary 和 missing-typography，agent 会因此自动编造主色和字体。

## Gotchas

| What happened                                                      | Rule                                                                    |
| ------------------------------------------------------------------ | ----------------------------------------------------------------------- |
| Windows/PowerShell 上 `npx @google/design.md` 无输出或打开了编辑器 | `.md` 后缀撞上 Windows 文件关联，用 `npx -p @google/design.md designmd` |
| 安装报 `ENOVERSIONS`                                               | 几乎总是 registry 配置问题，`npm config get registry` 应指向公共源      |
| `colours:` 被标 `unknown-key`                                      | linter 会识别已知 schema 键的拼写变体，按提示改正                       |
| 组件写了 textColor 但没过 contrast-ratio                           | 该规则按 WCAG AA 4.5:1 判定，换色值而不是降标准                         |

## Output

- 修改后的 DESIGN.md（或 diff/export 结果）。
- lint JSON 的 `summary` 行与未处理 warning 清单。
- 引用的参考文件：references/format-spec.md（格式规范）、references/cli-reference.md（CLI 完整参考）。

## Non-goals

- 不做没有 DESIGN.md 载体的通用 UI 设计或排版评审。
- 不替代用户做设计决策（风格、品牌色由用户定，本技能保证其被结构化表达）。
- 不维护导出产物的手动修改——源头改动后一律重新导出。
