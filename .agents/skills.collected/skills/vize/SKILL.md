---
name: vize
description: "Vue.js Rust 原生工具链 Vize 最佳实践：SFC 编译、Patina Lint、Glyph 格式化、Canon 类型检查、Vapor Mode、JSX/TSX、Musea 画廊、Nuxt 集成、unplugin/rspack、WASM、VS Code 配置与决策。当用户提到 vize、patina、glyph、canon、vapor mode、musea、art.vue、defineArt、@vizejs/* 包、vize lint/fmt/check/build/doctor/inspector/lsp、跨文件分析、@vize 注释注解，或从 ESLint/Prettier/vue-tsc/Volar 迁移到 Vize 时使用。不适用于与 Vize 无关的通用 Vue 语法教学或构建问题。"
---

# Vize: Vue.js Rust 原生工具链最佳实践

一次解析、一棵 AST、一份配置 —— 所有配置决策都围绕这个前提展开。

## Outcome Contract

- Outcome: 使用 Vize 工具链的 Vue 项目遵循架构最佳实践，编译/lint/格式化/类型检查全流程配置正确，代码质量高。
- Done when: 项目能正确编译、lint 规则合理配置、Vapor Mode 按需启用、CI 工作流完备、团队能根据本技能做出最佳决策。
- Evidence: 配置文件、CLI 命令输出、lint 报告、编译产物。
- Output: 可直接落地的配置、代码模式、工作流建议。

## Vize 是什么

Vize 是用 Rust 编写的 Vue.js 一体化开发工具链（v0.300.0），统一覆盖 SFC 编译、Lint、格式化、类型检查、LSP、组件画廊。底层使用 OXC 做 JS/TS 解析、LightningCSS 处理 CSS、corsa-bind 提供原生 TypeScript 诊断。

**与传统工具链的对应关系：**

| 传统工具 | Vize 替代 | Crate |
|---------|----------|-------|
| `@vue/compiler-sfc` | `vize compile` | `vize_atelier_dom` / `vize_atelier_vapor` / `vize_atelier_ssr` |
| `eslint-plugin-vue` | `vize lint` | `vize_patina` |
| `prettier` + `@vue/prettier-plugin` | `vize fmt` | `vize_glyph` |
| `vue-tsc` | `vize check` | `vize_canon` |
| Volar / vue-language-server | `vize lsp` | `vize_maestro` |
| Storybook | `vize musea` | `vize_musea` |

**核心优势：** 一次解析、一棵 AST、一份配置。15000 个 SFC 文件编译 ~334ms（多线程），比 `@vue/compiler-sfc` 快 55x，比 eslint-plugin-vue 快 209x，比 Prettier 快 68x。

## 架构速览

Crate 命名采用艺术/雕塑主题。编译管线：

```
Source → Armature(解析器/Tokenizer) → Relief(AST) → Croquis(语义分析) → Atelier(编译器) → Output JS
```

**编译后端三选一：**
- `vize_atelier_dom` — VDOM 渲染（默认，兼容现有 Vue 运行时）
- `vize_atelier_vapor` — Vapor 模式（无虚拟 DOM，细粒度响应式，Vue 3.6+）
- `vize_atelier_ssr` — 服务端渲染

**工具管线：**
- `vize_patina` — Lint 引擎（238 条规则）
- `vize_glyph` — 格式化引擎
- `vize_canon` — 类型检查（基于 corsa-bind/原生 TS 诊断）
- `vize_maestro` — LSP 服务器（tower-lsp）
- `vize_musea` — 组件画廊解析和生成
- `vize_vitrine` — NAPI/WASM 绑定层，供 JS 侧调用

## 项目设置

按安装、Vite 插件、类型声明的顺序完成接入。

### 安装

```bash
vp install -D @vizejs/vite-plugin vize
```

### Vite 插件配置

```ts
// vite.config.ts
import { defineConfig } from "vite";
import vize from "@vizejs/vite-plugin";

export default defineConfig({
  plugins: [vize()],
});
```

插件替代 `@vitejs/plugin-vue`，不需要改业务代码。

### TypeScript Vue Imports

在 `env.d.ts` 顶部用 `/// <reference>` 加载插件类型声明：

```ts
// src/env.d.ts
/// <reference types="vite/client" />
/// <reference types="@vizejs/vite-plugin" />
```

> **不要用 `compilerOptions.types`**：`types` 字段会覆盖 `@types/*` 自动发现。`/// <reference>` 是增量加载，无此副作用。

### Vite 插件选项

优先级：直接选项 > inline `config` > `vize.config.*` > 默认值。常见配方：

```ts
vize({ vapor: true });                          // Vapor 构建
vize({ customRenderer: true });                 // TresJS
vize({ templateSyntax: "quirks" });              // 依赖解析器边缘情况
vize({ vueVersion: 2 });                        // Legacy Vue / Nuxt 2 Bridge
vize({ root: import.meta.dirname, scanPatterns: ["src/**/*.vue"] });  // Monorepo
```

完整选项表和详细说明见 [references/config.md](references/config.md)。

## 从传统工具链迁移

1. 装 `@vizejs/vite-plugin`，移除 `@vitejs/plugin-vue`，验证 `vp dev` 正常启动。
2. 移除 ESLint + eslint-plugin-vue，换 `vize lint`，验证无配置跑通 essential。
3. 移除 Prettier，换 `vize fmt`，验证 `vize fmt --check` 格式一致。
4. 移除 vue-tsc，换 `vize check`，验证类型诊断正常。
5. 移除 Volar，配置 `vize lsp`，验证编辑器补全和诊断正常。

迁移期间可保留旧工具做对比验证，逐个替换、逐个验证。

## 注释注解系统

Vize 有两套注解系统。所有 `@vize:` 模板注解**会从构建产物中剥离**。

**模板注解**（`<template>` 中 HTML 注释）：

| 注解 | 效果 |
|------|------|
| `<!-- @vize:expected -->` | 期望下一行产生诊断（类似 `@ts-expect-error`） |
| `<!-- @vize:ignore-start/end -->` | 抑制区域内所有诊断 |
| `<!-- @vize:level(warn\|error\|off) -->` | 覆盖下一行严重度 |
| `<!-- @vize:todo <msg> -->` | TODO 警告 |
| `<!-- @vize:fixme <msg> -->` | FIXME 错误 |
| `<!-- @vize:dev-only -->` | 生产构建中剥离该节点 |

**脚本抑制**（`<script>` 中 JS 注释）：`// @vize forget: <reason>` 抑制跨文件分析，必须提供原因。

Patina 接受已有 ESLint 禁用注释（`eslint-disable`、`eslint-disable-next-line`），迁移期间不需要立即重写。

## 配置文件

优先级：`vize.config.pkl` > `.ts` > `.js` > `.mjs` > `.json`

```ts
// vize.config.ts — 最小示例
import { defineConfig } from "vize";

export default defineConfig({
  compiler: { vapor: false, jsxMode: "vdom", templateSyntax: "standard" },
  vite: { scanPatterns: ["src/**/*.vue"] },
  linter: { preset: "happy-path", crossFile: false, rules: {} },
  typeChecker: { enabled: true, strict: true, tsconfig: "tsconfig.json" },
  formatter: { printWidth: 100, singleQuote: false },
  lsp: { lint: true, typecheck: false },
});
```

支持 PKL/JSON/TS/JS 配置格式、`defineConfig` 函数形式（动态配置）、monorepo entries 扁平配置。

完整配置选项清单和详细说明见 [references/config.md](references/config.md)。

## CLI 命令

| 命令 | 说明 | 命令 | 说明 |
|------|------|------|------|
| `build` | 编译 SFC | `doctor` | 应用健康诊断 |
| `fmt` | 格式化 | `inspector` | 编译器检查器 |
| `lint` | 代码检查 | `clean` | 清理缓存 |
| `check` | 类型检查 | `ready` | fmt→lint→check→build |

常用命令示例：

```bash
vize lint --cross-file src          # CI 跨文件分析
vize lint --fix src                 # 自动修复
vize fmt --check src                # CI 格式检查
vize check --tsconfig tsconfig.app.json src  # 指定 tsconfig
vize ready src                      # 完整流水线
vize doctor                         # 环境诊断
```

完整命令选项和详细说明见 [references/cli.md](references/cli.md)。

## Lint 规则与预设

```
essential → happy-path → opinionated → nuxt
```

| 阶段 | 预设 | 理由 |
|------|------|------|
| CI 门禁 | `essential` | 正确性规则，零容忍 |
| 日常开发 | `happy-path` | 实用卫生检查 |
| 规范成熟 | `opinionated` | 最严格内置预设 |
| Nuxt 项目 | `nuxt` | 含 SSR 和 Nuxt 约定 |

`linter.rules` 控制规则严重度（`"error"` / `"warn"` / `"off"`），`linter.ruleOptions` 传项目级参数。

跨文件分析（`--cross-file`）提供 12 种诊断：provide/inject 匹配、响应式跟踪、竞态条件、循环依赖等。

完整预设说明、跨文件选项表、复杂度报告见 [references/lint.md](references/lint.md)。
完整 238 条规则目录见 [references/rules.md](references/rules.md)。

## Vapor Mode

Vapor Mode 跳过虚拟 DOM，直接生成细粒度 DOM 操作指令。Vue 3.6+ 核心特性。同一项目中 VDOM 和 Vapor 可共存。

启用方式：全局 `compiler.vapor: true`、per-SFC `<script setup vapor>`、JSX `"use vue:vapor"`。

约束：不支持 `getCurrentInstance()`、`nextTick()`、Options API、per-element 生命周期事件。

## JSX/TSX 编写

Props 是第一参数类型，Emits/Slots 是 `Ctx<Emits, Slots>` 第二参数。VDOM/Vapor 用 `"use vue:vdom"` / `"use vue:vapor"` 指令切换。

已知限制：独立 JSX/TSX 文件无 HMR、`v-bind()` CSS 变量不支持、JSX 类型检查需 `jsxTypecheck: true`。

完整编写模式、Scoped Styles、限制说明见 [references/jsx.md](references/jsx.md)。

## Musea 组件画廊

用 `*.art.vue` 文件描述组件变体，`defineArt()` 编译器宏声明目标组件和元数据。支持 VRT 视觉回归测试、Design Tokens、Storybook 输出。

完整安装配置、art 文件编写、VRT 命令见 [references/musea.md](references/musea.md)。

## Nuxt 集成

```bash
vp install @vizejs/nuxt
```

```ts
export default defineNuxtConfig({
  modules: ["@vizejs/nuxt"],
  vize: { compiler: true },
});
```

Nuxt 2 自动 host-compiler 兼容。art 文件需放 components 目录外避免 Nuxt 扫描。

完整模块选项、Bridge 选项、Musea-nuxt 配置见 [references/nuxt.md](references/nuxt.md)。

## 稳定性分层

npm 包与 Rust Crate 各自按稳定性承诺分层，生产选型以 Alpha-supported 为底线。

### npm 包

| 层级 | 包 | 契约 |
|------|---|------|
| Alpha-supported | `vize`, `@vizejs/native`, `@vizejs/vite-plugin` | 早期生产试验 |
| Compatibility preview | `@vizejs/unplugin`, `@vizejs/rspack-plugin`, `@vizejs/nuxt`, `@vizejs/musea-nuxt` | 框架兼容可能快速变动 |
| Experimental | `oxlint-plugin-vize`, `@vizejs/vite-plugin-musea`, `@vizejs/musea-mcp-server`, `@vizejs/wasm` | API 可能变化 |
| Incubating | `@vizejs/fresco`, `@vizejs/fresco-native` | 开发反馈用 |

### Rust Crate

| 层级 | Crate | 说明 |
|------|-------|------|
| Alpha-supported | `vize_carton`, `vize_relief`, `vize_armature`, `vize_atelier_core`, `vize_atelier_dom`, `vize_atelier_sfc` | 核心编译/解析/AST |
| Compatibility preview | `vize_croquis`, `vize_atelier_ssr`, `vize_atelier_jsx`, `vize_canon`, `vize_patina` | 语义分析/SSR/JSX/类型检查/Lint |
| Experimental | `vize_croquis_cf`, `vize_doctor`, `vize_atelier_vapor`, `vize_marquette`, `vize_musea` | 跨文件分析/Doctor/Vapor/画廊 |
| Incubating | `vize_fresco` | TUI 实验 |

> `vize_vitrine` 和 `vize` CLI 属于 Alpha-supported npm 包层。`vize_glyph` 和 `vize_maestro` 随 Alpha-supported 包发布。Node 22 为默认底线，MSRV 1.95.0。

## MCP 集成

`@vizejs/musea-mcp-server` 让 AI 助手通过 MCP 协议理解 Vue 组件（Component Discovery/API、Story Info、Design Tokens）。

```json
{ "mcpServers": { "vize-musea": { "command": "vp", "args": ["dlx", "@vizejs/musea-mcp-server"] } } }
```

## Oxlint 插件

`oxlint-plugin-vize` 让 Oxlint 执行 Vize Patina 诊断。用 `oxlint-vize`（薄包装）处理无 `<script>` 的 `.vue` 文件。

```bash
vp install -D oxlint oxlint-plugin-vize
vp exec oxlint-vize -c .oxlintrc.json -f stylish src
```

完整配置、preset 导出、settings 说明见 [references/oxlint.md](references/oxlint.md)。

## 故障排查

```bash
vize doctor               # 环境诊断
vize lint 2>&1 | head -20 # lint 层
vize check 2>&1 | head -20 # 类型层
vize inspector src/App.vue  # 编译器调试
```

完整排查工作流、Doctor 分析能力、Vue 类型解析策略见 [references/troubleshooting.md](references/troubleshooting.md)。

## 参考文档索引

按需加载，仅在涉及对应主题时读取：

| 文件 | 内容 | 何时读取 |
|------|------|---------|
| [references/config.md](references/config.md) | 完整配置选项、PKL/JSON/TS、defineConfig、monorepo entries、模板语法、compiler/formatter/linter/typeChecker/lsp 选项表 | 配置 vize.config 或需要特定选项时 |
| [references/cli.md](references/cli.md) | 全命令选项、Inspector 选项表、npm scripts 模式 | 需要 CLI 参数细节时 |
| [references/lint.md](references/lint.md) | 预设分层、自定义 rules/ruleOptions、跨文件分析 12 选项、复杂度报告、渐进式采用 | 配置 lint 规则或跨文件分析时 |
| [references/rules.md](references/rules.md) | 238 条 Patina 规则完整目录和分类 | 需要查找特定规则时 |
| [references/jsx.md](references/jsx.md) | JSX 编写模式、VDOM/Vapor 切换、Scoped Styles、已知限制 | 编写 JSX/TSX 组件时 |
| [references/musea.md](references/musea.md) | Art 文件编写、VRT 命令、Design Tokens、Storybook 输出 | 使用组件画廊时 |
| [references/nuxt.md](references/nuxt.md) | 模块选项、Bridge 选项、Nuxt Musea、Nuxt 2 兼容、musea-nuxt Preview | Nuxt 项目配置时 |
| [references/editors.md](references/editors.md) | VS Code/Neovim/Zed 设置表和细粒度控制 | 配置编辑器集成时 |
| [references/troubleshooting.md](references/troubleshooting.md) | Doctor 分析能力、Inspector 调试、常见问题定位、Vue 类型解析 | 排查编译/lint/类型问题时 |
| [references/workflow.md](references/workflow.md) | 开发环境、CI/CD 流水线、常见陷阱表 | 设置工作流或 CI 时 |
| [references/oxlint.md](references/oxlint.md) | Oxlint 插件完整配置、preset 导出、settings 选项、oxlint-vize CLI、性能模型、已知限制 | 配置 Oxlint + Vize 集成时 |
| [references/bundlers.md](references/bundlers.md) | unplugin (rollup/webpack/esbuild) 和 rspack 配置 | 非 Vite 打包器时 |
| [references/wasm.md](references/wasm.md) | WASM 初始化、API、Compiler Option 兼容性、国际化、从源码构建 | 浏览器内编译场景时 |

## 进一步阅读

- [Vize 官方文档](https://github.com/ubugeeei-prod/vize) — 架构和 API 的权威来源
- [Vue 3.6 Vapor Mode](https://blog.vuejs.org/posts/vue-vapor) — Vapor 运行时原理
- [OXC 项目](https://github.com/oxc-project/oxc) — Vize 底层 JS/TS 解析器
- [Vue Fes Japan 2026](https://vuefes.jp/2026) — 使用 Vize + Nuxt 4 的真实案例
