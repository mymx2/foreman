# Vize 编辑器集成完整参考

## 目录

- [VS Code](#vs-code)
- [Neovim](#neovim)
- [Zed / Helix / Emacs](#zed--helix--emacs)

## VS Code

```bash
code --install-extension ubugeeei.vize        # Vize LSP 扩展
code --install-extension vize.vize-art        # *.art.vue 语法高亮
```

推荐起步配置（仅 lint，导航/补全留给现有 Vue 工具）：

```json
{
  "vize.enable": true,
  "vize.lint.enable": true,
  "vize.typecheck.enable": false,
  "vize.editor.enable": false,
  "vize.formatting.enable": false
}
```

### 设置表

| 设置 | 说明 |
|------|------|
| `vize.enable` | 启用扩展和语言服务器 |
| `vize.serverPath` | 覆盖 `vize` 可执行文件路径 |
| `vize.lint.enable` | Lint 诊断 |
| `vize.typecheck.enable` | 类型感知诊断 |
| `vize.editor.enable` | 编辑器辅助（hover/补全/跳转/引用/符号） |
| `vize.formatting.enable` | 文档格式化 |
| `vize.codeActions.enable` | Lint 快速修复 |
| `vize.semanticTokens.enable` | 语义高亮 |
| `vize.trace.server` | LSP 通信追踪 |

### 编辑器辅助细粒度控制

`vize.editor.enable` 开启后可进一步控制：

| 设置 | 说明 |
|------|------|
| `vize.completion.enable` | 补全建议 |
| `vize.definition.enable` | 跳转定义 |
| `vize.references.enable` | 查找引用 |
| `vize.hover.enable` | Hover 信息 |

### 常用命令

- `Vize: Show Status` — 状态/配置中枢
- `Vize: Enable Recommended Profile` — 推荐配置
- `Vize: Restart Language Server` — 重启 LSP

## Neovim

```lua
require("lspconfig").vize.setup({
  cmd = { "vize", "lsp" },
  filetypes = { "vue" },
  init_options = {
    lint = true,
    typecheck = false,  -- 如已有 tsgo 则关闭
    editor = true,
  },
})
```

## Zed / Helix / Emacs

配置 `vize lsp` 作为语言服务器，`init_options` 同 Neovim。
