# Vize 配置文件完整参考

## 目录

- [配置优先级](#配置优先级)
- [TypeScript 配置](#typescript-配置)
- [PKL 配置](#pkl-配置)
- [JSON 配置](#json-配置)
- [Vue 方言（dialect）](#vue-方言dialect)
- [defineConfig 函数形式](#defineconfig-函数形式)
- [Monorepo entries（扁平配置）](#monorepo-entries扁平配置)
- [模板语法模式](#模板语法模式)
- [完整配置选项清单](#完整配置选项清单)

## 配置优先级

`vize.config.pkl` > `.ts` > `.js` > `.mjs` > `.json`

## TypeScript 配置

```ts
// vize.config.ts
import { defineConfig } from "vize";

export default defineConfig({
  compiler: {
    sourceMap: true,
    vapor: false,           // .vue SFC 是否启用 Vapor
    jsxMode: "vdom",        // .jsx/.tsx 默认后端："vdom" | "vapor"
    templateSyntax: "standard", // "standard" | "strict" | "quirks"
    hoistStatic: true,
    cacheHandlers: true,
    prefixIdentifiers: true,
    mode: "module",         // "module" | "function"
    customRenderer: false,  // 小写非 HTML 标签视为自定义渲染器元素（如 TresJS）
    scriptExt: "ts",        // "ts" 保留 TS 输出 | "js" 降编译为 JS
    isTs: false,            // 将 script 块解析为 TypeScript
    runtimeModuleName: "",  // 覆盖运行时导入模块名
    runtimeGlobalName: "",  // 覆盖运行时全局名（function/IIFE 模式）
  },
  vite: {
    include: [/\.vue$/],              // 插件编译的文件
    exclude: [/node_modules/],        // 排除的文件
    scanPatterns: ["src/**/*.vue"],   // 启动预编译 glob
    ignorePatterns: ["node_modules/**", "dist/**", ".git/**"],  // 预编译忽略
  },
  linter: {
    preset: "happy-path",   // "essential" | "happy-path" | "opinionated" | "nuxt" | "incremental"
    crossFile: false,       // 跨文件分析需 opt-in
    rules: {},              // 控制规则严重度："error" | "warn" | "off"
    ruleOptions: {},        // 项目级规则参数（仅 no-restricted-globals / no-restricted-members）
  },
  typeChecker: {
    enabled: true,
    strict: true,
    servers: 1,             // 目前仅支持 1
    jsxTypecheck: false,    // JSX 类型检查 opt-in
    corsaPath: "./node_modules/.bin/tsgo",  // Corsa 可执行文件路径（tsgoPath 为废弃别名）
    checkProps: true,       // 检查 prop 类型匹配
    checkEmits: true,       // 检查 emit 事件声明
    checkTemplateBindings: true,  // 检查模板绑定
    optionsApi: true,       // 解析 Options API 模板绑定（默认开，匹配 vue-tsc）
    legacyVue2: false,      // Vue 2.7 / Nuxt 2 支持（legacy 构建 opt-in）
    tsconfig: "tsconfig.json",    // 指定 tsconfig
  },
  formatter: {
    printWidth: 100,        // 最大行宽（默认 100）
    singleQuote: false,     // 字符串引号风格
  },
  lsp: {
    lint: true,             // LSP 启用 lint 诊断
    typecheck: false,       // LSP 启用类型检查（opt-in）
    editor: false,          // LSP 编辑器功能
    formatting: false,      // LSP 格式化
  },
  musea: {
    include: ["src/**/*.art.vue"],
    exclude: ["node_modules/**", "dist/**"],
    basePath: "/__musea__",
    storybookCompat: false,
    inlineArt: false,
  },
});
```

## PKL 配置

```pkl
amends "node_modules/vize/pkl/vize.pkl"

compiler {
  sourceMap = true
  vapor = false
  customRenderer = false
  templateSyntax = "standard"
}

vite {
  scanPatterns = new Listing { "src/**/*.vue" }
}

linter { preset = "happy-path" }

typeChecker {
  enabled = true
  strict = true
}

lsp {
  lint = true
  typecheck = false
  editor = false
  formatting = false
}

entries = new Listing {
  new ConfigEntry {
    name = "web app"
    basePath = "apps/web"
    files = new Listing { "src/**/*.vue" }
    typeChecker {
      tsconfig = "tsconfig.app.json"
    }
  }
}
```

## JSON 配置

```json
{
  "$schema": "./node_modules/vize/schemas/vize.config.schema.json",
  "compiler": {
    "sourceMap": true,
    "vapor": false,
    "customRenderer": false,
    "templateSyntax": "standard"
  },
  "vite": { "scanPatterns": ["src/**/*.vue"] },
  "linter": { "preset": "happy-path" },
  "typeChecker": { "enabled": true, "strict": true },
  "musea": { "include": ["src/**/*.art.vue"], "basePath": "/__musea__" }
}
```

## Vue 方言（dialect）

`dialect` 为独立 HTML 文档（`.html`/`.htm`）选择 Vue 方言配置：

```json
{ "dialect": "petite-vue" }
```

- `"vue"` — 标准 Vue-from-CDN 文档
- `"petite-vue"` — petite-vue 方言（`v-scope`/`v-effect` 补全和 IDE 支持）

未设置时按文档结构自动检测（`<script src>` 指向 petite-vue、`import petite-vue`、`PetiteVue.createApp` 调用）。SFC 始终使用标准 Vue 方言。

## defineConfig 函数形式

根据构建上下文动态配置：

```ts
export default defineConfig(({ command, mode, isSsrBuild }) => ({
  compiler: {
    sourceMap: mode !== "production",
    ssr: isSsrBuild,
    vapor: false,
  },
  linter: {
    enabled: command !== "build",
    preset: "happy-path",
  },
}));
```

> `defineConfig` 也可从 `@vizejs/vite-plugin` 导入（向后兼容），但推荐使用 `import { defineConfig } from "vize"` 统一入口。

## Monorepo entries（扁平配置）

```ts
export default defineConfig({
  formatter: { printWidth: 100 },
  entries: [
    {
      name: "web app",
      basePath: "apps/web",
      files: ["src/**/*.vue"],
      typeChecker: { tsconfig: "tsconfig.app.json" },
    },
    {
      name: "ui package",
      basePath: "packages/ui",
      files: ["src/**/*.vue"],
      formatter: { singleQuote: true },
    },
  ],
});
```

## 模板语法模式

| 模式 | 行为 | 适用场景 |
|------|------|---------|
| `standard` | 容错 + 警告，重写为合法输出（默认） | 大多数项目 |
| `strict` | 报错，不自动重写 | 新项目、团队规范 |
| `quirks` | 保留 Vue 怪癖，无额外警告 | 迁移项目 |

已知差异：
- `v-for` 别名括号不匹配（如 `(item in items`）：standard/strict 报错，quirks 镜像 Vue 行为
- 非 void 元素自闭合（如 `<div />`）：standard 警告并重写为 `<div></div>`，strict 报错，quirks 保留

## 完整配置选项清单

### compiler

| 选项 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `sourceMap` | `boolean` | 开发开、生产关 | 源码映射 |
| `ssr` | `boolean` | `false` | 强制 SSR 编译 |
| `vapor` | `boolean` | `false` | .vue SFC 启用 Vapor |
| `jsxMode` | `"vdom" \| "vapor"` | `"vdom"` | .jsx/.tsx 默认后端 |
| `customRenderer` | `boolean` | `false` | 自定义渲染器（TresJS） |
| `templateSyntax` | `"standard" \| "strict" \| "quirks"` | `"standard"` | 模板语法模式 |
| `hoistStatic` | `boolean` | `true` | 静态提升 |
| `cacheHandlers` | `boolean` | `true` | 缓存事件处理器 |
| `prefixIdentifiers` | `boolean` | `true` | 前缀标识符 |
| `mode` | `"module" \| "function"` | `"module"` | 编译模式 |
| `scriptExt` | `"ts" \| "js"` | `"ts"` | 脚本输出扩展名 |
| `isTs` | `boolean` | `false` | 将 script 块解析为 TypeScript |
| `runtimeModuleName` | `string` | `""` | 覆盖运行时导入模块名 |
| `runtimeGlobalName` | `string` | `""` | 覆盖运行时全局名 |

### formatter

| 选项 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `printWidth` | `number` | `100` | 最大行宽 |
| `singleQuote` | `boolean` | `false` | 字符串引号风格 |

> CLI 还提供 `--tab-width`、`--use-tabs`、`--single-attribute-per-line` 等选项，见 [cli.md](cli.md)。

### linter

| 选项 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `enabled` | `boolean` | `true` | 启用 lint |
| `preset` | `string` | `"happy-path"` | 预设名称 |
| `crossFile` | `boolean` | `false` | 跨文件分析 |
| `rules` | `Record<string, string>` | `{}` | 规则严重度覆盖 |
| `ruleOptions` | `Record<string, any>` | `{}` | 项目级规则参数 |

### typeChecker

| 选项 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `enabled` | `boolean` | `true` | 启用类型检查 |
| `strict` | `boolean` | `true` | 严格模式 |
| `servers` | `number` | `1` | Corsa server 数（仅支持 1） |
| `jsxTypecheck` | `boolean` | `false` | JSX 类型检查 |
| `corsaPath` | `string` | `"./node_modules/.bin/tsgo"` | Corsa 可执行文件路径 |
| `checkProps` | `boolean` | `true` | 检查 prop 类型匹配 |
| `checkEmits` | `boolean` | `true` | 检查 emit 事件声明 |
| `checkTemplateBindings` | `boolean` | `true` | 检查模板绑定 |
| `optionsApi` | `boolean` | `true` | 解析 Options API |
| `legacyVue2` | `boolean` | `false` | Vue 2 / Nuxt 2 支持 |
| `tsconfig` | `string` | `"tsconfig.json"` | 指定 tsconfig |

### lsp

| 选项 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `lint` | `boolean` | `true` | LSP lint 诊断 |
| `typecheck` | `boolean` | `false` | LSP 类型检查 |
| `editor` | `boolean` | `false` | 编辑器辅助功能 |
| `formatting` | `boolean` | `false` | 文档格式化 |
