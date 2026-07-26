# Vize Lint 规则与预设完整参考

## 目录

- [预设分层（渐进式采用）](#预设分层渐进式采用)
- [自定义规则与 ruleOptions](#自定义规则与-ruleoptions)
- [跨文件分析](#跨文件分析)
- [跨文件复杂度报告](#跨文件复杂度报告)
- [渐进式 Lint 采用](#渐进式-lint-采用)

## 预设分层（渐进式采用）

```
essential (48 rules) → happy-path (+recommended) → opinionated (+更多) → nuxt (+nuxt专属)
                                                                              ↑
incremental (空，按需 opt-in)                                    ecosystem (含 Router/Pinia/i18n/Nuxt)
```

**推荐采用路径：**

| 阶段 | 预设 | 理由 |
|------|------|------|
| CI 门禁 | `essential` | 正确性规则，零容忍 |
| 日常开发 | `happy-path` | 实用卫生检查，噪音低 |
| 规范成熟 | `opinionated` | 最严格内置预设 |
| Nuxt 项目 | `nuxt` | 含 SSR 和 Nuxt 约定 |

## 自定义规则与 ruleOptions

`rules` 控制严重度，`ruleOptions` 传项目级参数。两个规则支持项目配置：

```json
{
  "linter": {
    "rules": {
      "script/no-restricted-globals": "error",
      "script/no-restricted-members": "error"
    },
    "ruleOptions": {
      "script/no-restricted-globals": {
        "globals": [
          { "name": "process", "message": "用 typed env helper 读取环境变量" },
          { "name": "alert" }
        ]
      },
      "script/no-restricted-members": {
        "members": [
          { "object": "window", "property": "localStorage", "message": "用 authStorage" }
        ]
      }
    }
  }
}
```

- `script/no-restricted-globals`：默认拒绝 `process`/`localStorage`/`sessionStorage`，配置后**替换**默认列表
- `script/no-restricted-members`：默认关闭，配置后标记 `<object>.<property>` 访问

完整规则目录、自定义配置示例见 [rules.md](rules.md)。

## 跨文件分析

`vize lint --cross-file` 启用项目图分析，诊断码前缀 `vize:croquis/cf/*`。跨文件引擎完整选项表：

| 跨文件选项 | 诊断内容 |
|------------|----------|
| `provide_inject` | 未匹配的 inject、未使用的 provide、字符串 key、非响应式流 |
| `unique_ids` | 重复 ID、循环中非唯一 ID |
| `reactivity_tracking` | prop 解构、别名、跨组件响应式丢失 |
| `race_conditions` | 异步状态更新竞态 |
| `fallthrough_attrs` | `$attrs`、`inheritAttrs`、多根节点透传风险 |
| `component_emits` | 未声明的 emit、未使用的 emit、无生产者的监听 |
| `event_bubbling` | 事件跨越组件边界未被处理 |
| `server_client_boundary` | SSR/客户端边界的浏览器 API 和 hydration 风险 |
| `error_suspense_boundary` | 异步组件缺少 Suspense 或错误边界 |
| `circular_dependencies` | 导入循环和深层导入链 |
| `component_resolution` | 未注册或未解析的组件使用 |
| `props_validation` | 缺失必需 prop、子组件 prop 类型不匹配 |

**最佳实践：** CI 中 essential 预设跑 `--cross-file`，开发环境不开启（性能考虑）。

跨文件诊断示例：
```
error[vize:croquis/cf/unmatched-inject]: inject("theme") has no matching provide
  --> src/components/DeepChild.vue:8:15
  |
8 | const theme = inject("theme");
  |               ^^^^^^^^^^^^^^^ no provide("theme") found in project graph
```

## 跨文件复杂度报告

Croquis 还生成项目复杂度报告（WASM API 可通过 `CrossFileResult.complexityReport` 获取）：

| 分数 | 含义 |
|--------|------|
| `cyclomaticScore` | 组件数 + `v-if` + `v-for` + 布尔运算符 |
| `cognitiveScore` | 组件树模板嵌套深度（含跨组件 scoped slot） |
| `totalScore` | 维度总分：模板流/slot/prop 钻取/全局状态/DI/响应式图 |
| `band` | 分级：`low` / `moderate` / `high` / `extreme` |

原始信号（6 个维度）：模板控制流、slot 转发、prop 钻取深度、全局状态依赖、DI 图深度、响应式图复杂度。

复杂度跨组件边界计算：父组件 `v-if` 包裹子组件、scoped slot 转发、prop 钻取都计入同一条路径。报告还包含热点排名（`complexityHotspots`），每个热点携带 `dominantDimension`（主导维度）和 `input`（输入类型）。当前仅做探索性信号，CLI 不会基于分数失败。

## 渐进式 Lint 采用

```ts
// 第一阶段：CI 用 essential
{ linter: { preset: "essential" } }

// 第二阶段：开发用 happy-path
{ linter: { preset: "happy-path" } }

// 第三阶段：全面 opinionated
{ linter: { preset: "opinionated" } }

// 特殊需求：incremental + 用 rules 逐条 opt-in
{ linter: { preset: "incremental", rules: {
  "vue/require-v-for-key": "error",
  "vue/no-v-html": "warn",
} } }
```
