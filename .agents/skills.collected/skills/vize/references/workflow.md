# Vize 工作流最佳实践

## 目录

- [开发环境](#开发环境)
- [CI/CD](#cicd)
- [常见陷阱](#常见陷阱)

## 开发环境

```bash
# 启动开发服务器（Vize 通过 Vite 插件自动接管编译）
vp dev

# 独立 lint（开发期间偶尔跑）
vize lint src

# 独立类型检查
vize check src
```

## CI/CD

```yaml
# 推荐 CI 流水线
- run: vize fmt --check          # 格式检查（不修改）
- run: vize lint                 # Lint 检查
- run: vize lint --cross-file    # 跨文件分析
- run: vize check                # 类型检查
- run: vize build                # 编译验证
```

或使用聚合命令：
```bash
vize ready    # fmt → lint → check → build
```

## 常见陷阱

| 问题 | 原因 | 解法 |
|------|------|------|
| 模板中 `v-if` 和 `v-for` 同时出现 | 优先级歧义 | 用 `computed` 过滤后再 `v-for` |
| Props 被直接修改 | 违反单向数据流 | 用 `emit("update:x", value)` |
| `<textarea>` 中用 mustache | 无效 | 用 `v-model` |
| 跨文件 ID 冲突 | 静态 ID 在多实例/SSR 中重复 | 用 `useId()` |
| SSR hydration mismatch | `new Date()` / `Math.random()` | 用 `useState` 或 `onMounted` 延迟 |
| `provide` 用字符串 key | 跨文件可能意外匹配 | 用 `Symbol` + `InjectionKey<T>` |
| 展开 reactive 对象 | 丢失响应性 | 用 `toRef` / `toRefs` |
| Vapor 组件用 `getCurrentInstance` | 返回 null | 避免使用，改用 Composition API |
| JSX 文件 HMR 不生效 | 已知限制 | 手动刷新页面 |
| Nuxt 项目 art.vue 文件被扫描 | Nuxt 自动发现机制 | art 文件放 components 目录外 |
| `compilerOptions.types` 覆盖 `@types/*` | TS 的 `types` 字段会覆盖自动发现 | 用 `/// <reference types="..." />` 替代 |
