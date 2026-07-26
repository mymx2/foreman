# Vize 实验性打包器集成

> **⚠️ 实验性：** `@vizejs/vite-plugin` 仍是推荐且测试最充分的集成。

`@vizejs/unplugin` 支持 rollup/webpack/esbuild，`@vizejs/rspack-plugin` 专门支持 Rspack（Rspack 不走 unplugin 通道，其 loader 链/HMR 需要专属处理）。

```bash
vp install @vizejs/unplugin                # rollup/webpack/esbuild
vp install -D @vizejs/rspack-plugin @rspack/core  # Rspack
```

## Rollup

```js
// rollup.config.mjs
import vize from "@vizejs/unplugin/rollup";
export default { plugins: [vize()] };
```

## Webpack

```js
// webpack.config.mjs
import Vize from "@vizejs/unplugin/webpack";
export default { plugins: [Vize()] };
```

## Rspack

```js
// rspack.config.mjs
import { VizePlugin } from "@vizejs/rspack-plugin";
export default {
  experiments: { css: true },
  module: { rules: [{ test: /\.vue$/, loader: "@vizejs/rspack-plugin/loader" }] },
  plugins: [new VizePlugin()],
};
```

注意：CSS Modules 和预处理器在非 Vite 打包器中依赖宿主 CSS 管线，变动风险更高。
