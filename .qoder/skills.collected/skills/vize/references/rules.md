# Vize Patina 规则完整参考

238 条规则，按类别组织。

## 规则分类总览

| 类别 | 数量 | 关键规则示例 |
|------|------|-------------|
| Essential | 48 | `vue/valid-v-for`, `vue/no-mutating-props`, `vue/require-v-for-key` |
| Strongly Recommended | 12 | `vue/attribute-hyphenation`, `vue/v-on-style`, `vue/no-unused-properties` |
| Recommended | 41 | `vue/attribute-order`, `ssr/no-hydration-mismatch`, `vue/require-scoped-style` |
| Accessibility | 31 | `a11y/img-alt`, `a11y/aria-props`, `a11y/click-events-have-key-events` |
| HTML Conformance | 9 | `html/id-duplication`, `html/no-empty-palpable-content` |
| Type Aware | 5 | `type/require-typed-props`, `type/no-floating-promises`, `type/no-reactivity-loss` |
| Vapor | 7 | `vapor/no-vue-lifecycle-events`, `script/no-get-current-instance` |
| Ecosystem | 9 | `ecosystem/nuxt-prefer-nuxt-link`, `ecosystem/pinia-prefer-store-to-refs` |
| CSS | 10 | `css/no-important`, `css/prefer-logical-properties`, `css/prefer-nested-selectors` |
| Musea | 6 | `musea/require-title`, `musea/unique-variant-names` |
| Script | 60 | `script/no-ref-as-operand`, `script/require-typed-ref`, `script/valid-define-props` |

## 自定义规则配置

Vize 的 lint 配置有两个字段：

- `linter.rules` — 控制任意规则严重度（`"error"` / `"warn"` / `"off"`）
- `linter.ruleOptions` — 仅用于 `script/no-restricted-globals` 和 `script/no-restricted-members` 的项目级参数

```ts
// vize.config.ts
export default defineConfig({
  linter: {
    preset: "opinionated",
    // 控制规则严重度：覆盖预设默认值
    rules: {
      "vue/no-v-html": "error",         // 预设默认 warn → 升级为 error
      "vue/no-unsafe-url": "off",       // 关闭不适用的规则
      "css/no-important": "error",
      // 以下两条需配合 ruleOptions 使用
      "script/no-restricted-globals": "error",
      "script/no-restricted-members": "error",
    },
    // 仅这两条规则接受项目级参数
    ruleOptions: {
      "script/no-restricted-globals": {
        globals: [
          { name: "process", message: "Read env via a typed helper." },
          { name: "alert" },
        ],
      },
      "script/no-restricted-members": {
        members: [
          { object: "window", property: "localStorage", message: "Use authStorage." },
        ],
      },
    },
  },
});
```

**注意：** `linter.overrides` 不存在。用 `rules` 直接控制严重度即可。

### incremental 预设（空起点，按需 opt-in）

```ts
export default defineConfig({
  linter: {
    preset: "incremental", // 不继承任何预设
    rules: {
      "vue/require-v-for-key": "error",
      "vue/no-v-html": "warn",
    },
  },
});
```

## Essential (48) — 正确性规则

### Petite-vue (3) — 不在任何预设中，按需 opt-in

| 规则 | 严重度 | 说明 |
|------|--------|------|
| `petite-vue/no-unsupported-directive` | error | 禁止 petite-vue 不支持的指令 |
| `petite-vue/valid-v-effect` | error | v-effect 必须有非空表达式 |
| `petite-vue/valid-v-scope` | error | v-scope 必须绑定对象字面量 |

### Vue 核心 (33)

| 规则 | 严重度 | 预设 | 说明 |
|------|--------|------|------|
| `vue/multi-word-component-names` | error | essential, nuxt, opinionated | 组件名必须多词 |
| `vue/no-child-content` | error | essential+ | v-html/v-text 时禁止子内容 |
| `vue/no-dupe-v-else-if` | error | essential+ | v-if/v-else-if 条件不可重复 |
| `vue/no-duplicate-attributes` | error | essential+ | 同元素禁止重复属性 |
| `vue/no-mutating-props` | error | happy-path+ | 禁止直接修改 props |
| `vue/no-reserved-component-names` | error | essential+ | 禁止使用保留名称 |
| `vue/no-template-key` | error | essential+ | `<template>` 禁止 key |
| `vue/no-textarea-mustache` | error | essential+ | `<textarea>` 禁止 mustache |
| `vue/no-unused-components` | warning | happy-path+ | 注册的组件未使用 |
| `vue/no-unused-vars` | warning | essential+ | v-for/v-slot 变量未使用 |
| `vue/no-use-v-if-with-v-for` | warning | essential+ | 同元素禁止 v-if+v-for |
| `vue/no-useless-template-attributes` | error | essential+ | `<template>` 无效属性 |
| `vue/no-v-for-template-key-on-child` | error | essential+ | `<template v-for>` 子元素禁止 key |
| `vue/no-v-html` | warning | essential+ | 警告 v-html XSS 风险 |
| `vue/no-v-text-v-html-on-component` | error | essential+ | 组件禁止 v-text/v-html |
| `vue/permitted-contents` | error | happy-path+ | HTML 内容模型规则 |
| `vue/require-component-is` | error | essential+ | `<component>` 必须有 `:is` |
| `vue/require-toggle-inside-transition` | error | essential+ | `<transition>` 内需切换条件 |
| `vue/require-v-for-key` | error | essential+ | v-for 必须有 :key |
| `vue/use-v-on-exact` | warning | essential, nuxt | 多修饰符时需 .exact |
| `vue/valid-attribute-name` | error | essential+ | 属性名合法 |
| `vue/valid-template-root` | error | essential+ | 模板根元素合法 |
| `vue/valid-v-bind` | error | essential+ | v-bind 合法 |
| `vue/valid-v-cloak` | error | essential+ | v-cloak 合法 |
| `vue/valid-v-else` | error | essential+ | v-else 合法（**可修复**） |
| `vue/valid-v-for` | error | essential+ | v-for 合法 |
| `vue/valid-v-html` | error | essential+ | v-html 合法 |
| `vue/valid-v-if` | error | essential+ | v-if 合法 |
| `vue/valid-v-memo` | error | essential+ | v-memo 合法 |
| `vue/valid-v-model` | error | essential+ | v-model 合法 |
| `vue/valid-v-on` | error | essential+ | v-on 合法 |
| `vue/valid-v-once` | error | essential+ | v-once 合法 |
| `vue/valid-v-show` | error | essential+ | v-show 合法 |
| `vue/valid-v-slot` | error | essential+ | v-slot 合法 |
| `vue/valid-v-text` | error | essential+ | v-text 合法 |

### 废弃 API (12) — 不在预设中，按需 opt-in

| 规则 | 严重度 | 说明 |
|------|--------|------|
| `vue/no-deprecated-filter` | error | 禁止 Vue 2 filter 管道语法 |
| `vue/no-deprecated-functional-template` | error | 禁止 `<template functional>` |
| `vue/no-deprecated-html-element-is` | error | 禁止原生 HTML 元素 `is` 属性 |
| `vue/no-deprecated-router-link-tag-prop` | error | 禁止 `<router-link>` 的 `tag` prop |
| `vue/no-deprecated-scope-attribute` | error | 禁止废弃的 `scope` 属性 |
| `vue/no-deprecated-slot-attribute` | error | 禁止废弃的 `slot` 属性 |
| `vue/no-deprecated-slot-scope-attribute` | error | 禁止废弃的 `slot-scope` 属性 |
| `vue/no-deprecated-v-bind-sync` | error | 禁止 `.sync` 修饰符 |
| `vue/no-deprecated-v-on-native-modifier` | error | 禁止 `.native` 修饰符 |
| `vue/no-deprecated-v-on-number-modifiers` | error | 禁止数字 keyCode 修饰符 |
| `vue/no-unsafe-url` | warning | 不安全 URL 绑定警告（在 happy-path+ 预设中） |

## Strongly Recommended (12) — 强烈建议

| 规则 | 严重度 | 可修复 | 说明 |
|------|--------|--------|------|
| `vue/attribute-hyphenation` | warning | Yes | 自定义组件属性用 kebab-case |
| `vue/component-definition-name-casing` | warning | No | 组件定义名 PascalCase |
| `vue/html-quotes` | warning | Yes | HTML 属性引号风格 |
| `vue/html-self-closing` | warning | Yes | 自闭合风格 |
| `vue/mustache-interpolation-spacing` | warning | Yes | mustache 间距 |
| `vue/no-multi-spaces` | warning | Yes | 禁止连续空格 |
| `vue/no-template-shadow` | warning | No | 禁止变量遮蔽 |
| `vue/no-unused-properties` | warning | No | defineProps 中未用属性 |
| `vue/prop-name-casing` | warning | No | 模板中 prop 用 kebab-case |
| `vue/v-bind-style` | warning | Yes | v-bind 风格 |
| `vue/v-on-style` | warning | Yes | v-on 风格 |
| `vue/v-slot-style` | warning | Yes | v-slot 风格 |

## Recommended (41) — 实用卫生检查

| 规则 | 严重度 | 预设 | 可修复 | 说明 |
|------|--------|------|--------|------|
| `ssr/no-browser-globals-in-ssr` | warning | happy-path+ | No | SSR 上下文禁止浏览器全局变量 |
| `ssr/no-hydration-mismatch` | warning | happy-path+ | No | 禁止非确定性 hydration 不匹配 |
| `vue/a11y-img-alt` | warning | _none_ | No | 图片需 alt 属性 |
| `vue/attribute-order` | warning | happy-path+ | No | 属性顺序一致 |
| `vue/component-name-in-template-casing` | warning | nuxt+ | Yes | 模板中组件名大小风格 |
| `vue/html-button-has-type` | warning | nuxt+ | No | button 需显式 type |
| `vue/no-array-index-key` | warning | nuxt+ | No | 禁止 v-for 索引作为 :key |
| `vue/no-bare-strings-in-template` | warning | _none_ | No | 模板禁止未国际化文本 |
| `vue/no-boolean-attr-value` | warning | nuxt+ | Yes | 禁止布尔属性显式值 |
| `vue/no-empty-component-block` | warning | nuxt+ | No | 禁止空 SFC 块 |
| `vue/no-inline-style` | warning | nuxt+ | No | 避免内联 style |
| `vue/no-invalid-html-attribute` | warning | happy-path+ | No | 禁止无效 HTML 属性 |
| `vue/no-lone-template` | warning | happy-path+ | No | 禁止不必要的 `<template>` |
| `vue/no-multiple-objects-in-class` | warning | nuxt+ | No | :class 数组禁止多对象 |
| `vue/no-negated-v-if-condition` | warning | nuxt+ | No | 禁止 v-else 链中取反 v-if |
| `vue/no-preprocessor-lang` | warning | nuxt+ | Yes | 避免 CSS 预处理器 |
| `vue/no-root-v-if` | warning | nuxt+ | No | 禁止单根元素 v-if |
| `vue/no-script-non-standard-lang` | warning | nuxt+ | No | 避免非标准 script lang |
| `vue/no-src-attribute` | warning | nuxt+ | No | 避免 SFC 块 src 属性 |
| `vue/no-template-lang` | warning | nuxt+ | Yes | 避免 template lang |
| `vue/no-template-target-blank` | warning | happy-path+ | No | target="_blank" 需 rel="noopener" |
| `vue/no-undefined-refs` | warning | _none_ | No | 禁止未定义模板引用 |
| `vue/no-unsafe-url` | warning | essential+ | No | 不安全 URL 绑定 |
| `vue/no-unsandboxed-iframe` | warning | happy-path+ | No | iframe 需 sandbox |
| `vue/no-unused-refs` | warning | nuxt+ | No | 未使用的 ref 引用 |
| `vue/no-useless-mustaches` | warning | nuxt+ | No | 禁止常量字符串 mustache |
| `vue/no-useless-v-bind` | warning | nuxt+ | No | 禁止纯字符串 v-bind |
| `vue/no-v-text` | warning | nuxt+ | No | 禁止 v-text，用 mustache |
| `vue/prefer-props-shorthand` | warning | nuxt+ | Yes | Vue 3.4+ props 简写 |
| `vue/prefer-true-attribute-shorthand` | warning | nuxt+ | No | true 属性简写 |
| `vue/require-component-registration` | warning | opinionated | No | 组件需显式导入/注册 |
| `vue/require-scoped-style` | warning | happy-path+ | No | style 标签需 scoped |
| `vue/scoped-event-names` | warning | nuxt+ | No | 事件名用 context:event 格式 |
| `vue/sfc-element-order` | warning | happy-path+ | No | SFC 顶层元素顺序一致 |
| `vue/single-style-block` | warning | happy-path+ | No | 单一 style 块 |
| `vue/slot-name-casing` | warning | nuxt+ | No | slot 名 kebab-case |
| `vue/this-in-template` | warning | nuxt+ | No | 模板禁止 this. |
| `vue/v-on-event-hyphenation` | warning | nuxt+ | No | 自定义事件名 kebab-case |
| `vue/v-on-handler-style` | warning | nuxt+ | No | v-on handler 风格 |
| `vue/warn-custom-block` | warning | nuxt+ | No | SFC 自定义块警告 |
| `vue/warn-custom-directive` | warning | nuxt+ | No | 需注册的自定义指令警告 |

## HTML Conformance (9) — HTML 合规性

| 规则 | 严重度 | 预设 | 说明 |
|------|--------|------|------|
| `html/deprecated-attr` | warning | happy-path+ | 禁止废弃 HTML 属性 |
| `html/deprecated-element` | warning | happy-path+ | 禁止废弃 HTML 元素 |
| `html/id-duplication` | error | essential+ | 禁止重复元素 ID |
| `html/no-consecutive-br` | warning | happy-path+ | 禁止连续 `<br>` |
| `html/no-dupe-style-properties` | warning | nuxt+ | 禁止内联 style 重复属性 |
| `html/no-duplicate-class` | warning | nuxt+ | 禁止静态 class 重复类名 |
| `html/no-duplicate-dt` | warning | happy-path+ | `<dl>` 中禁止重复 `<dt>` |
| `html/no-empty-palpable-content` | warning | happy-path+ | 禁止空可感知内容元素 |
| `html/require-datetime` | warning | happy-path+ | `<time>` 需 datetime 属性 |

## Accessibility (31) — 无障碍

核心规则：
- `a11y/img-alt` / `a11y/alt-text` — 图片/媒体需替代文本
- `a11y/aria-props` / `a11y/aria-role` — ARIA 属性/角色合法
- `a11y/click-events-have-key-events` — click 事件配键盘事件
- `a11y/form-control-has-label` / `a11y/label-has-for` — 表单控件需标签
- `a11y/no-aria-hidden-on-focusable` — 可聚焦元素禁止 aria-hidden
- `a11y/no-static-element-interactions` — 静态元素禁止交互
- `a11y/tabindex-no-positive` — 禁止正 tabindex
- `a11y/anchor-is-valid` — 链接 href 合法
- `a11y/interactive-supports-focus` — 交互角色可聚焦
- `a11y/role-has-required-aria-props` — 角色必需 ARIA 属性

补充规则：
- `a11y/anchor-has-content` — 锚元素需可访问内容
- `a11y/aria-unsupported-elements` — 不支持 ARIA 的元素禁止 ARIA 属性
- `a11y/heading-has-content` — 标题元素需内容
- `a11y/heading-levels` — 禁止跳过标题级别（opinionated）
- `a11y/iframe-has-title` — iframe 需 title
- `a11y/landmark-roles` — landmark role 放置和唯一性（opinionated）
- `a11y/media-has-caption` — 媒体元素需字幕
- `a11y/mouse-events-have-key-events` — 鼠标事件配焦点事件
- `a11y/no-access-key` — 禁止 accesskey
- `a11y/no-autofocus` — 禁止 autofocus
- `a11y/no-distracting-elements` — 禁止 marquee/blink
- `a11y/no-i-for-icon` — 禁止 `<i>` 做图标
- `a11y/no-redundant-roles` — 禁止冗余 ARIA role（**可修复**）
- `a11y/no-refer-to-non-existent-id` — 禁止引用不存在的 ID
- `a11y/no-role-presentation-on-focusable` — 可聚焦元素禁止 role=presentation
- `a11y/placeholder-label-option` — select 占位符需 disabled/hidden（opinionated）
- `a11y/use-list` — 列表样式文本用列表元素（opinionated）
- `vue/use-unique-element-ids` — 用 useId() 代替静态 ID（opinionated）

## Type Aware (5) — 类型感知

| 规则 | 说明 |
|------|------|
| `type/require-typed-props` | defineProps 必须类型定义 |
| `type/require-typed-emits` | defineEmits 必须类型定义 |
| `type/no-floating-promises` | 禁止未处理的 Promise |
| `type/no-reactivity-loss` | 禁止响应式值丢失响应性 |
| `type/no-unsafe-template-binding` | 模板绑定不可为 unsafe 类型 |

## Vapor (7) — Vapor 模式专属

| 规则 | 严重度 | 说明 |
|------|--------|------|
| `script/no-get-current-instance` | error | Vapor 中 getCurrentInstance 返回 null |
| `script/no-next-tick` | error | Vapor 组件禁止 nextTick |
| `script/no-options-api` | error | Vapor 禁止 Options API |
| `vapor/no-inline-template` | error | 废弃的 inline-template |
| `vapor/no-vue-lifecycle-events` | error | 不支持 @vue:mounted 等 |
| `vapor/prefer-static-class` | warning | 优先静态 class |
| `vapor/require-vapor-attribute` | warning | script setup 建议加 vapor 属性 |

## Ecosystem (9) — 生态规则

| 规则 | 说明 |
|------|------|
| `ecosystem/nuxt-prefer-nuxt-link` | 优先 NuxtLink |
| `ecosystem/pinia-prefer-store-to-refs` | Pinia store 用 storeToRefs |
| `ecosystem/router-link-require-to` | RouterLink 必须有 `to` |
| `ecosystem/void-link-require-href` | Void Vue Link 需 href |
| `ecosystem/vue-i18n-no-missing-key` | i18n key 必须存在 |
| `ecosystem/vue-router-prefer-named-link` | RouterLink 优先命名路由 |
| `ecosystem/vue-router-prefer-named-push` | push/replace 优先命名路由 |
| `ecosystem/vue-test-utils-no-html-snapshot` | 避免 html() 快照 |
| `ecosystem/void-link-valid-method` | Void Vue Link method 合法 |

## CSS (10) — 样式规则

| 规则 | 说明 |
|------|------|
| `css/no-display-none` | 建议 v-show 替代 |
| `css/no-hardcoded-values` | 建议 CSS 变量 |
| `css/no-id-selectors` | 禁止 ID 选择器 |
| `css/no-important` | 禁止 !important |
| `css/no-utility-classes` | 组件样式中禁止 utility class |
| `css/no-v-bind-performance` | CSS v-bind() 性能警告 |
| `css/prefer-logical-properties` | 建议逻辑属性 |
| `css/prefer-nested-selectors` | 建议 CSS 嵌套 |
| `css/prefer-slotted` | 建议 ::v-slotted() |
| `css/require-font-display` | @font-face 需 font-display |

## Musea (6) — Art 文件规则

| 规则 | 说明 |
|------|------|
| `musea/require-title` | `<art>` 必须有 title |
| `musea/require-component` | `<art>` 必须有 component |
| `musea/unique-variant-names` | variant 名称唯一 |
| `musea/valid-variant` | variant 必须有 name |
| `musea/no-empty-variant` | variant 不可为空 |
| `musea/prefer-design-tokens` | 优先 design token |

## Script (60) — 脚本规则精选

**宏与定义：**
- `script/valid-define-props` / `valid-define-emits` / `valid-define-options` — 宏调用合法
- `script/define-macros-order` — 宏顺序一致
- `script/define-props-declaration` — 类型声明优先于运行时
- `script/define-emits-declaration` — 类型声明优先
- `script/define-props-destructuring` — 禁止解构 defineProps 返回值（Vue 3.5+ 除外）

**响应性与状态：**
- `script/no-ref-as-operand` — ref 变量需 .value
- `script/no-reactive-destructure` — 禁止解构 reactive 对象
- `script/prefer-ref-over-reactive` — 优先 ref()
- `script/no-top-level-ref-in-script` — SSR 顶层禁止 ref/reactive
- `script/prefer-computed` — 派生状态用 computed
- `script/no-with-defaults` — 避免 withDefaults，用解构默认值（Vue 3.5+）
- `script/prefer-use-template-ref` — 用 useTemplateRef 替代 ref(null)（Vue 3.5+）
- `script/prefer-use-id` — 用 useId() 生成唯一 ID（Vue 3.5+）
- `script/prefer-use-attrs` / `prefer-use-slots` — 用 useAttrs()/useSlots() 替代 context.attrs/slots

**Props & Emits：**
- `script/require-prop-types` — prop 必须声明类型
- `script/require-default-prop` — 可选 prop 需默认值
- `script/require-typed-ref` — ref() 无初始值需泛型
- `script/no-required-prop-with-default` — required + default 矛盾
- `script/require-explicit-emits` — emit 事件需声明
- `script/no-unused-emit-declarations` — 声明的 emit 未使用
- `script/require-explicit-slots` — useSlots() 消费的 slot 需 defineSlots
- `script/require-typed-object-prop` — Object/Array 类型 prop 需显式类型
- `script/require-valid-default-prop` — prop 默认值需符合声明类型
- `script/require-prop-type-constructor` — prop type 需构造函数而非字符串
- `script/no-reserved-props` — 禁止保留名作为 prop
- `script/no-boolean-default` — Boolean prop 禁止默认值

**废弃 API：**
- `script/no-deprecated-data-object-declaration` — data 必须函数
- `script/no-deprecated-dollar-listeners-api` — $listeners 已移除
- `script/no-deprecated-dollar-scopedslots-api` — $scopedSlots 已移除
- `script/no-deprecated-events-api` — $on/$off/$once 已移除
- `script/no-deprecated-props-default-this` — prop default/validator 禁止 this
- `script/no-import-compiler-macros` — 宏自动导入，禁止手动 import
- `script/no-internal-imports` — 禁止导入 Vue 内部模块

**代码质量：**
- `script/no-async-in-computed` — computed 禁止异步
- `script/no-side-effects-in-computed-properties` — computed 禁止副作用
- `script/no-unstable-nested-components` — 禁止嵌套定义组件
- `script/valid-next-tick` — nextTick 必须 await/链式/回调
- `script/no-export-in-script-setup` — script setup 禁止 export
- `script/no-arrow-functions-in-watch` — watch handler 禁止箭头函数
- `script/no-dupe-keys` — Options API 禁止重复 key
- `script/no-reserved-keys` — 禁止 Vue 保留名作为 key
- `script/no-reserved-identifiers` — 禁止编译器保留标识符
- `script/no-potential-component-option-typo` — Options API 选项名拼写检查
- `script/no-use-computed-property-like-method` — 禁止像方法一样调用 computed
- `script/return-in-computed-property` — computed getter 必须 return
- `script/return-in-emits-validator` — emits validator 必须 return
- `script/component-options-name-casing` — name 选项 PascalCase
- `script/custom-event-name-casing` — emit 事件名 camelCase
- `script/no-duplicate-attr-inheritance` — inheritAttrs: true 冗余
- `script/no-multiple-slot-args` — scoped slot 禁止多参数
- `script/no-deep-destructure-in-props` — defineProps 禁止深层解构
- `script/prefer-define-options` — 优先 defineOptions()
- `script/prefer-import-from-vue` — 优先从 'vue' 导入（**可修复**）
- `script/require-function-return-type` — 函数需返回类型注解
- `script/require-symbol-provide` — provide 用 Symbol 作为 injection key
- `script/no-restricted-globals` / `no-restricted-members` — 需配合 ruleOptions 使用
