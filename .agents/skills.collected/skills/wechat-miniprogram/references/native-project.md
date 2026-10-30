# 原生小程序工程约束

新建项目默认使用原生微信小程序结构：

```text
project.config.json
app.json
app.js
app.wxss
pages/<name>/<name>.wxml
pages/<name>/<name>.js
pages/<name>/<name>.wxss
```

- `project.config.json` 的 `miniprogramRoot` 必须指向包含 `app.json` 的源码根。
- `app.json.pages` 必须非空；每个页面必须有对应的 `.wxml` 和 `.js`。
- `app.json` 顶层必须包含 `"lazyCodeLoading": "requiredComponents"`。
- JSON 必须严格：不含注释和尾逗号。
- 使用 `<view>`、`<text>`、`<image>` 等小程序组件；不要写 HTML 标签、React Router、`document`、`window`、`localStorage` 或浏览器 `fetch`。
- WXML 表达式不支持 `?.`、`??`、箭头函数、函数调用和复杂对象字面量。复杂计算应放入页面 JS 的 data。
- `tabBar.list` 的每个 `pagePath` 必须在 `pages` 中声明；图标路径必须真实存在。
- `usingComponents`、WXML `include`/`import`、WXS `src` 和 WXSS `@import` 必须指向已保存的本地文件，并保持大小写一致。
- 本地图片不要通过 WXSS `background-image: url(...)` 引用，改用 `<image>`。

已有项目保持其已有工程布局和技术栈。不要因为本 Skill 强制重写或迁移工程。