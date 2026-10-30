---
name: design-to-code
description: |
  当用户在 Ardot 里要把设计稿转成前端代码（HTML/CSS/JS、Vue、React、Tailwind），或从现有网站反向提取设计规范与 token 时使用。
  不适用于纯画板编辑（走 grid / showcase 模块）、UI 视觉品味审计（走 ui 技能）。
  Triggers: "设计稿转代码", "转前端代码", "生成HTML", "导出网页", "一比一还原",
  "设计稿出码", "提取设计 token", "网站风格转设计稿", "提取设计风格", "design to code".
metadata:
  source: 本仓
---

# 设计稿转代码 / 网站风格提取

把 Ardot 画布上的设计转成可运行的前端代码，或从网站反向抽取设计系统。

## Outcome Contract

- **Outcome**：产出与设计稿一致的前端代码，或一份可用的设计规范/token。
- **Done when**：代码在目标工程里可运行、样式编译无错、视觉与设计稿的关键结构一致；提取规范时 token 完整且可用。
- **Evidence**：编译通过；关键元素（文字、图标、间距、圆角）与设计稿逐项对照；提取时给出 token 清单。
- **Authorization**：只生成代码，不改动无关文件；不产出变更说明文档。

## 硬规则（转代码前必读）

- **跟随工程既有技术栈**：项目用 Vue 就写 Vue，用 React 就写 React。不确定就看工作区。
- **复用既有样式体系**：项目用 Tailwind 就用 Tailwind；用 CSS 变量就继续用。
- **先确认版本**：用 CSS 框架前确认已安装版本，只用该版本支持的 API。
- **复用而非新建**：设计元素在代码库中已存在就更新它，不要新生成一份。
- **不改坏既有功能**：修改现有组件时保证功能不被破坏。
- **不写文档**：转码任务只产出代码，不生成 Markdown 变更说明。
- **忠实还原**：文字标签、图标、间距、字体、圆角都要与设计稿一致。

## 工作流选择

| 任务 | 读哪份 |
|---|---|
| 设计稿 → HTML/CSS/JS、生成 Application、响应式缩放 | `references/design-to-code-workflow.md` |
| 网站 → 设计规范 / design token 提取 | `references/extract-style-guide-from-web.md` |
| 实现细节规则（组件拆分、样式组织） | `references/guidelines-code.md` |
| Tailwind v4 实现细节 | `references/guidelines-tailwind.md` |

生成代码时同时读 `guidelines-code.md` +（用 Tailwind 时）`guidelines-tailwind.md`。

## 前置检查

动手前确认：

1. 已识别前端框架与语言（Vue / React / Svelte 等）
2. 已识别样式方案（Tailwind / CSS Modules / styled-components 等）
3. 样式能编译通过
4. CSS 变量（若使用）可访问
5. 样式系统已正确配置并加载

## 组件实现要点

- 只处理当前设计稿 frame 里出现的组件
- 统计每个组件的实例数，便于事后核对有无遗漏
- 设计稿里的 ref 组件要映射到工程里已有的组件，不要重复造

## 协作边界

本模块假设调用方已在 Ardot 里打开目标文件、MCP 可连通。画布读取与编辑的具体调用见 `shared/mcp-cheatsheet.md`。
