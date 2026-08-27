# Vize Musea 组件画廊完整参考

## 目录

- [安装与配置](#安装与配置)
- [Art 文件编写](#art-文件编写)
- [文件组织](#文件组织)
- [Inline Art](#inline-art)
- [Shared Config](#shared-config)
- [Design Tokens](#design-tokens)
- [视觉回归测试 (VRT)](#视觉回归测试-vrt)
- [Storybook Output](#storybook-output)

## 安装与配置

```bash
vp install -D @vizejs/vite-plugin-musea
```

```ts
// vite.config.ts
import { musea } from "@vizejs/vite-plugin-musea";

export default defineConfig({
  plugins: [
    vize(),
    musea({
      include: ["**/*.art.vue"],
      basePath: "/__musea__",
      previewCss: ["src/styles/main.css"],
      previewSetup: "musea.preview.ts",
    }),
  ],
});
```

运行 `vp dev` 后访问 `http://localhost:5173/__musea__`。

## Art 文件编写

```vue
<!-- Button.art.vue -->
<script setup lang="ts">
import { ref } from "vue";

defineArt("./Button.vue", {
  title: "Button",
  category: "Components",
  status: "ready",
  tags: ["button", "ui"],
});

const pressed = ref(false);
</script>

<art>
  <variant name="Default" default>
    <Button :pressed="pressed">Click me</Button>
  </variant>
  <variant name="Outlined">
    <Button outlined>Click me</Button>
  </variant>
</art>
```

**关键 API：**
- `defineArt(source, options)` — 编译器宏，声明目标组件和元数据（source 参与路径补全、诊断、go-to-definition）
- `<art>` — 变体根块（兼容属性 `title`/`component` 仍可用，显式属性覆盖 `defineArt`）
- `<variant name="..." default>` — 命名变体，`default` 标记默认。可选属性：`args`、`viewport`、`skip-vrt`
- `<script setup>` — 默认每个 variant 隔离状态；`isolate="false"` 共享

### 变体隔离

Root `<script setup>` 状态默认按 variant 隔离。每个 variant 接收独立的 setup 实例。用 `<script setup isolate="false">` 仅在所有 variant 需要共享状态时。

### 元素与宏速查

| 元素 / 宏 | 用途 |
|-----------|------|
| `defineArt(source, options)` | 目标组件和 art 元数据 |
| `defineArt(...).title` | 显示名称 |
| `defineArt(...).category` | 侧边栏分组 |
| `defineArt(...).status` | 状态徽章 |
| `defineArt(...).tags` | 搜索和过滤标签 |
| `<script setup>` | 默认按 variant 隔离 |
| `<script setup isolate="false">` | 所有 variant 共享 |
| `<art>` | 变体根块 |
| `<variant>` | 命名变体 |
| `default` | 标记默认变体 |
| `args`, `viewport`, `skip-vrt` | 变体配置 |

## 文件组织

```
# 紧邻组件（推荐小项目）
src/components/Button.vue
src/components/Button.art.vue

# 独立目录（推荐 Nuxt 或大项目）
src/components/Button.vue
stories/forms/Button.art.vue
```

Nuxt 项目**必须**将 art 文件放在 components 目录外，避免被 Nuxt 自动发现扫描。启用 Musea 时，`@vizejs/nuxt` 自动排除 `**/*.art.vue` 不参与 Nuxt 组件扫描。

## Inline Art

`inlineArt` 启用后，普通 `.vue` 文件中的 `<art>` 块也可进入画廊。内部用 `<Self>` 渲染宿主组件：

```ts
musea({ inlineArt: true });
```

## Shared Config

`musea()` 选项覆盖共享配置。稳定设置放 `vize.config.ts`，preview-only 设置放 `vite.config.ts`：

```ts
// vize.config.ts
export default defineConfig({
  musea: {
    include: ["src/**/*.art.vue"],
    exclude: ["node_modules/**", "dist/**"],
    basePath: "/__musea__",
    storybookCompat: false,
    inlineArt: false,
  },
});
```

共享配置覆盖：`include`、`exclude`、`basePath`、`storybookCompat`、`inlineArt`。`previewCss`、`previewSetup`、`tokensPath`、`theme`、`storybookOutDir` 直接传给 `musea()`。

## Design Tokens

```ts
musea({ tokensPath: "src/tokens.json" });
```

接收 Style Dictionary 兼容 token 文件，在画廊 UI 中展示颜色、排版、间距等。

## 视觉回归测试 (VRT)

```bash
# 生基线快照
vp exec musea-vrt --base-url http://localhost:5173 --update

# CI 检查
vp exec musea-vrt --base-url http://localhost:5173 --ci --json

# 批准变更
vp exec musea-vrt approve
vp exec musea-vrt approve "Button/*"

# 清理过期快照
vp exec musea-vrt clean

# 生成 art 文件草稿
vp exec musea-vrt generate src/components/Button.vue

# a11y 审计
vp exec musea-vrt --a11y
```

CI 流程：启动 Vite 服务 → `musea-vrt --ci --json` → 检查 `vrt-report.json`/`vrt-report.html`。`--ci` 对视觉 diff 和 preview/capture 错误返回非零退出码。新基线报告为 `new`，先本地 `--update` 再提交。

## Storybook Output

启用 Storybook CSF 兼容输出：

```ts
musea({
  storybookCompat: true,
  storybookOutDir: ".storybook/stories",
});
```
