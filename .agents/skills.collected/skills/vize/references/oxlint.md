# Oxlint 插件完整参考

> **⚠️ 实验性：** `oxlint-plugin-vize` 属于 Experimental 稳定性层级。API 和输出格式可能变化。

## 目录

- [安装](#安装)
- [基本配置](#基本配置)
- [Preset 导出](#preset-导出)
- [Settings 选项](#settings-选项)
- [oxlint-vize CLI 包装器](#oxlint-vize-cli-包装器)
- [性能模型](#性能模型)
- [Preset 别名](#preset-别名)
- [已知限制](#已知限制)

## 安装

```bash
vp install -D oxlint oxlint-plugin-vize
```

`oxlint-plugin-vize` 通过平台特定的 optional dependencies 自动解析匹配的 Vize 原生绑定，大多数用户不需要单独安装 `@vizejs/native`。目标 Node 22+ / 24+。

## 基本配置

### JSON 配置（`.oxlintrc.json`）

```json
{
  "plugins": ["vue"],
  "jsPlugins": ["oxlint-plugin-vize"],
  "settings": {
    "vize": {
      "helpLevel": "short"
    }
  },
  "rules": {
    "eqeqeq": "error",
    "vize/vue/require-v-for-key": "error",
    "vize/vue/no-v-html": "warn",
    "no-console": "warn"
  }
}
```

关键点：
- `plugins: ["vue"]` 启用 Oxlint 内置 Vue 插件（Oxlint 原生 `vue/*` 规则）
- `jsPlugins: ["oxlint-plugin-vize"]` 加载 Vize Patina 诊断（`vize/*` 规则）
- 两者共存：Oxlint 核心规则（`eqeqeq`、`no-console`）和内置 `vue/*` 规则照常运行

### JS/TS 配置（preset 规则映射）

```js
import { configs } from "oxlint-plugin-vize";

export default {
  plugins: ["vue"],
  jsPlugins: ["oxlint-plugin-vize"],
  settings: {
    vize: {
      helpLevel: "short",
      preset: "opinionated",
      typeAware: true,
    },
  },
  rules: configs.opinionatedWithTypeAware,
};
```

## Preset 导出

`oxlint-plugin-vize` 导出以下预设规则映射（源码 `configs.ts`）：

| 导出 | 预设 | Type-Aware | 说明 |
|------|------|-----------|------|
| `configs.recommended` | `general-recommended` | 否 | 通用推荐，默认预设 |
| `configs.recommendedWithTypeAware` | `general-recommended` | 是 | 含实验性类型规则 |
| `configs.essential` | `essential` | 否 | 正确性规则，CI 门禁 |
| `configs.ecosystem` | `ecosystem` | 否 | Vue Router / I18n / Pinia / VTU / Nuxt / Void Vue |
| `configs.ecosystemWithTypeAware` | `ecosystem` | 是 | 含实验性类型规则 |
| `configs.opinionated` | `opinionated` | 否 | 最严格内置预设，含脚本规则（如 `no-options-api`） |
| `configs.opinionatedWithTypeAware` | `opinionated` | 是 | 含实验性类型规则 |
| `configs.nuxt` | `nuxt` | 否 | Nuxt 约定，允许 Options API |
| `configs.all` | `all` | 否 | 所有规则 |

Type-aware 规则（`vize/type/*` 前缀）默认从所有预设中排除——它们仍处于实验阶段。要启用：

```js
// 方式 1：用 *WithTypeAware 导出
rules: configs.opinionatedWithTypeAware

// 方式 2：createVizeRuleConfig 自定义
import { createVizeRuleConfig } from "oxlint-plugin-vize";
rules: createVizeRuleConfig({ preset: "opinionated", includeTypeAware: true })
```

同时需要在 settings 中设置 `typeAware: true` 以在共享全文件 Patina pass 中运行 Corsa。

### 预设差异示例

| 规则 | `essential` | `recommended` | `opinionated` | `nuxt` | `ecosystem` |
|------|:-----------:|:-------------:|:-------------:|:------:|:-----------:|
| `vize/vue/require-v-for-key` | error | error | error | error | error |
| `vize/vue/require-scoped-style` | — | warn | warn | warn | — |
| `vize/script/no-options-api` | — | — | error | — | — |
| `vize/ecosystem/router-link-require-to` | — | — | — | — | error |
| `vize/type/require-typed-props` | — | — | — | — | — |

`nuxt` 预设允许 Options API（`no-options-api` 不启用），而 `opinionated` 强制 Composition API。

## Settings 选项

通过 `settings.vize` 传递（源码 `settings.ts`）：

| 选项 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `preset` | `string` | `"general-recommended"` | 预设名称，见[别名表](#preset-别名) |
| `locale` | `string` | — | 诊断语言（如 `"ja"`、`"en"`、`"zh-CN"`） |
| `helpLevel` | `"full" \| "short" \| "none"` | — | 修复建议详细度。`"full"` 展开 Patina 修复文本但不恢复原始 SFC 锚点 |
| `typeAware` | `boolean` | `false` | 启用 Corsa 支持的 `vize/type/*` 规则（共享全文件 pass） |
| `corsaPath` | `string` | — | Corsa / `tsgo` 可执行文件路径。省略则用 Vize 正常解析器 |
| `showHelp` | `boolean` | — | 已废弃，向后兼容。`true` → `"full"`，`false` → `"none"`。优先使用 `helpLevel` |

`settings.patina` 也被接受（向后兼容），但 `settings.vize` 优先。

### 渐进式采用

```json
{
  "settings": {
    "vize": {
      "preset": "incremental",
      "helpLevel": "short"
    }
  },
  "rules": {
    "vize/vue/require-v-for-key": "error"
  }
}
```

`"incremental"` 预设跳过预设门控，只运行你在 `rules` 中显式配置的 Vize 规则。适合逐条引入规则。

### Preset 门控行为

Bundle presets（非 `incremental`）会抑制不属于该预设的规则——即使你在 `rules` 中列出也不会执行。例如 `preset: "essential"` 时，`vize/vue/require-scoped-style`（属于 `general-recommended`）会被静默忽略。

## oxlint-vize CLI 包装器

```bash
vp exec oxlint-vize -c .oxlintrc.json -f stylish src
```

`oxlint-vize` 是 `oxlint` 的薄包装，解决无 `<script>` / `<script setup>` 的 `.vue` 文件的 JS 插件管线问题：为这些文件生成临时 `<script setup>` 块，调用 `oxlint`，然后将报告路径重写回原始 `.vue` 文件。

推荐格式器：`-f stylish` 是目前混合 Oxlint + Vize 输出的最佳人类可读格式。Patina 摘要可以内联原始 SFC 位置，即使 Oxlint 仍将 JS 插件诊断锚定在提取的脚本程序上。

## 性能模型

桥接层针对 Oxlint 的 per-rule 执行模型优化：

- 文件的第一个 Patina 规则触发时，仅对该规则运行原生 lint
- 同一文件遇到第二个 Patina 规则时，升级为一次共享全文件 Patina pass，后续规则复用结果
- 精确源修订和规则结果缓存最多 128 个最近使用的文件/settings 对

## Preset 别名

`settings.preset` 接受以下别名（大小写不敏感，忽略 `-`、`_`、空格）：

| 输入 | 解析为 |
|------|--------|
| `"general-recommended"`, `"recommended"`, `"happy-path"`, `"happy"`, `"default"` | `general-recommended` |
| `"essential"` | `essential` |
| `"ecosystem"`, `"eco"` | `ecosystem` |
| `"incremental"` | `incremental` |
| `"opinionated"`, `"strict"`, `"all"` | `opinionated` |
| `"nuxt"` | `nuxt` |

## 已知限制

- 原始 `oxlint` 会遗漏无 `<script>` / `<script setup>` 的 `.vue` 文件。用 `oxlint-vize` 包装器解决。
- Oxlint JS 插件只接受提取的 Vue 脚本程序内的范围。模板/样式诊断尚未在所有格式器中保留原始 SFC 范围。
- `stylish` 是目前推荐的人类可读格式器。JSON 等机器可读格式对原始模板/样式位置应视为 best-effort。
- `vize/type/*` 规则为实验性，默认从导出 configs 中排除。
- Oxlint 核心规则中需要 Vue 模板 JS 绑定的功能（如模板感知的未使用变量检查）仍依赖上游 OXC 进展。
- `helpLevel: "full"` 只扩展 Patina 修复文本，不恢复原始 SFC 格式器锚点或机器可读范围保真度。
