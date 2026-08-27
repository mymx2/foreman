# Vize Nuxt 集成完整参考

## 目录

- [基础安装](#基础安装)
- [模块选项](#模块选项)
- [Nuxt Musea 集成](#nuxt-musea-集成)
- [Nuxt 2 兼容](#nuxt-2-兼容)
- [@vizejs/musea-nuxt Preview Setup](#vizejsmusea-nuxt-preview-setup)

## 基础安装

```bash
vp install @vizejs/nuxt
```

```ts
// nuxt.config.ts
export default defineNuxtConfig({
  modules: ["@vizejs/nuxt"],
  vize: {
    compiler: true,
  },
});
```

## 模块选项

| 选项 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `compatibility` | `VizeNuxtCompatibilityOptions` | 自动检测 | 覆盖检测到的 Nuxt/Vue 版本。Nuxt 2 默认 Vue 2 兼容模式 |
| `compiler` | `boolean \| VitePluginOptions` | `true` | 传对象可转发任意 `@vizejs/vite-plugin` 选项 |
| `bridge` | `boolean \| VizeNuxtBridgeOptions` | `true` | 控制 Nuxt 转换桥 |
| `unocss` | `boolean \| VizeNuxtUnoCssOptions` | `true` | UnoCSS 桥接。`originalSource: false` 禁用源 SFC 读取；`maxBytes` 限制内存 |
| `dev.stylesheetLinks` | `boolean` | `true` | 开发模式 SSR 样式链接清理 |
| `musea` | `boolean \| MuseaOptions` | `false` | Musea 画廊集成 |
| `nuxtMusea` | `NuxtMuseaOptions` | `{ route: { path: "/" } }` | Nuxt mock 层配置，供 Musea preview helpers 使用 |

**Bridge 选项**（`bridge` 为对象时可用）：

| 选项 | 默认 | 说明 |
|------|------|------|
| `autoImports` | `true` | Nuxt auto-imports 转换 |
| `components` | `true` | Nuxt 组件导入转换 |
| `i18n` | `true` | i18n helpers 转换 |
| `stableInjectedKeys` | `true` | 稳定 async-data keys |

## Nuxt Musea 集成

```ts
// nuxt.config.ts
export default defineNuxtConfig({
  modules: ["@vizejs/nuxt"],
  vize: {
    compiler: true,
    musea: {
      include: ["**/*.art.vue"],
      tokensPath: "assets/tokens.json",
      previewCss: ["assets/styles/main.css"],
      previewSetup: "musea.preview.ts",
    },
    nuxtMusea: {
      route: { path: "/" },
    },
  },
});
```

## Nuxt 2 兼容

Nuxt 2 自动使用 host-compiler 兼容模式（不替换 Vue 编译器）。如自动检测失败：

```ts
vize: {
  compatibility: { nuxtVersion: 2, vueVersion: 2 },
},
```

## @vizejs/musea-nuxt Preview Setup

Nuxt 项目在 Musea preview 环境中需要 `NuxtLink`、`useRoute` 等 Nuxt 特性时，用 `@vizejs/musea-nuxt`：

```ts
// vite.config.ts（Musea 独立配置）
import { musea } from "@vizejs/vite-plugin-musea";
import { nuxtMusea } from "@vizejs/musea-nuxt";

export default defineConfig({
  plugins: [
    nuxtMusea({
      route: { path: "/preview" },
      runtimeConfig: { public: { apiBase: "/api" } },
      fetchMocks: { "/api/user": { id: 1, name: "Ada" } },
    }),
    musea({ previewSetup: "musea.preview.ts" }),
  ],
});
```

```ts
// musea.preview.ts
import { installNuxtMuseaMocks } from "@vizejs/musea-nuxt";
import type { MuseaPreviewSetup } from "@vizejs/vite-plugin-musea";

export default ((app) => {
  installNuxtMuseaMocks(app, {
    route: { path: "/preview" },
    runtimeConfig: { public: { apiBase: "/api" } },
  });
}) satisfies MuseaPreviewSetup;
```
