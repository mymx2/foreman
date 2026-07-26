# Vize WASM 绑定完整参考

## 目录

- [安装](#安装)
- [初始化](#初始化)
- [API](#api)
- [Compiler Option 兼容性](#compiler-option-兼容性)
- [国际化与懒加载](#国际化与懒加载)
- [从源码构建](#从源码构建)

`@vizejs/wasm` 提供浏览器内 SFC 编译/lint/格式化的 WebAssembly 绑定（~1.5MB gzip）。与 CLI/NAPI 共享同一 Rust 代码库，编译结果一致。

## 安装

```bash
vp install @vizejs/wasm
```

## 初始化

```js
import init from "@vizejs/wasm";

// 基本初始化
await init();

// 自定义 WASM URL（CDN 或打包器场景）
await init("https://cdn.example.com/vize_vitrine_bg.wasm");
```

## API

```js
import init, { compileSfc, lintSfc, formatSfc } from "@vizejs/wasm";
await init();

const result = compileSfc(source, { filename: "App.vue" });
// result.script.code / result.template?.code / result.css

const lint = lintSfc(source, { filename: "App.vue", locale: "zh" });
// lint.diagnostics[].severity / message / location

const formatted = formatSfc(source, { printWidth: 80 });
```

## Compiler Option 兼容性

`CompilerOptions` 类型是 `compile`、`compileVapor`、`parseTemplate`、`compileSfc` 支持的选项集合。未知 key 在 JS 边界被静默忽略。`vueParserQuirks` 是 `templateSyntax: "quirks"` 的废弃别名，显式 `templateSyntax` 始终优先。`experimentalServerScript` 保留未暴露。各 facade 忽略不适用的字段：`bindingMetadata` 仅用于直接模板编译；`outputMode` 和 `scriptExt` 仅用于 SFC 编译。

## 国际化与懒加载

诊断消息支持国际化：`locale: "en" | "ja" | "zh"`。

```js
// 生产建议懒加载
const compiler = await import("@vizejs/wasm");
await compiler.default(); // init()
const result = compiler.compileSfc(source, opts);
```

适用场景：Playground、文档实时示例、教育工具、无原生二进制的 CI 环境。

## 从源码构建

```bash
cargo install wasm-bindgen-cli
cargo build --release -p vize_vitrine --no-default-features --features wasm --target wasm32-unknown-unknown
wasm-bindgen target/wasm32-unknown-unknown/release/vize_vitrine.wasm --out-dir npm/wasm --target web
```
