# Vize 故障排查完整参考

## 目录

- [故障排查工作流](#故障排查工作流)
- [Doctor 分析能力](#doctor-分析能力)
- [常见问题快速定位](#常见问题快速定位)
- [Vue 类型解析策略](#vue-类型解析策略)

## 故障排查工作流

```bash
# 第一步：环境诊断
vize doctor               # 检查依赖注入、循环导入、SSR 边界、响应式流、ID 唯一性等

# 第二步：定位问题层
vize lint 2>&1 | head -20 # lint 层问题
vize check 2>&1 | head -20 # 类型层问题
vize build 2>&1 | head -20 # 编译层问题

# 第三步：编译器调试
vize inspector src/App.vue                    # 单文件，生成 Playground URL
vize inspector "src/**/*.vue" --target ssr    # 批量，指定 SSR 目标
vize inspector --format agent --output report.json  # AI 工具可消费格式
vize inspector --format compare --output compare.json  # 本地 Vue vs Vize 对比
```

Inspector 选项详见 [cli.md](cli.md)。

## Doctor 分析能力

`vize doctor` 构建确定性应用图，覆盖：

| 分析器 | 检查内容 |
|--------|----------|
| 依赖注入 | provide/inject 匹配、非响应式值、字符串 key |
| ID 唯一性 | 跨组件 DOM ID 冲突、循环中重复 ID |
| 服务器/客户端边界 | 浏览器 API 用法、hydration 风险 |
| 响应式流 | prop 解构、别名、跨组件响应式丢失 |
| 异步变异 | 异步状态更新竞态条件 |
| setup 上下文 | setup-context 所有权问题 |
| 循环导入 | 导入循环和深层导入链 |

退出状态：`0` 通过、`1` 确定错误、`2` 基础架构失败（解析/IO）。`--format json` 输出带版本号的确定性报告。

## 常见问题快速定位

- 编译报错但代码看起来正确 → 检查 `templateSyntax` 模式，`strict` 下某些 Vue 2 写法会报错；`<div />` 等非 void 元素自闭合在 standard 下会警告并重写为 `<div></div>`
- lint 规则不生效 → 确认 preset 层级包含该规则，用 `vize lint --help-level short` 查看实际生效配置
- 类型检查漏报 → `typeChecker.enabled` 是否为 true，JSX 文件需额外开 `jsxTypecheck`
- 类型解析不准 → Vize 从被检查项目解析 `vue`/`@vue/compiler-sfc` 等类型包，项目自身的 Vue 版本优先；异常布局用 `VIZE_VUE_PACKAGE` 环境变量指定

## Vue 类型解析策略

`vize check` 从被检查项目解析 Vue 类型包（不用 Vize 自身的版本）：

1. 项目的 `vue`、`@vue/runtime-dom`、`vite` 版本优先
2. 异常包管理器布局可用环境变量覆盖：`VIZE_VUE_PACKAGE`、`VIZE_VUE_RUNTIME_DOM_PACKAGE`、`VIZE_VITE_PACKAGE`
3. `VIZE_RUNTIME_NODE_MODULES` 指定 `node_modules` 根目录作为回退搜索路径

始终在项目中声明 Vue 版本依赖，不要通过 Vize 内部控制。
