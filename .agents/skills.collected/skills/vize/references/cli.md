# Vize CLI 命令完整参考

## 目录

- [npm package scripts 模式（推荐）](#npm-package-scripts-模式推荐)
- [Rust 二进制安装](#rust-二进制安装)
- [命令总览](#命令总览)
- [常用选项](#常用选项)

## npm package scripts 模式（推荐）

应用项目推荐通过 `package.json` scripts 运行：

```bash
vp install -D vize
```

```json
{
  "scripts": {
    "vize:build": "vize build src",
    "vize:fmt": "vize fmt --write src",
    "vize:lint": "vize lint --preset happy-path src",
    "vize:check": "vize check src",
    "vize:ready": "vize ready src"
  }
}
```

## Rust 二进制安装

v1 alpha 使用预构建 GitHub Release 或 Nix：

```bash
nix run github:ubugeeei-prod/vize#vize -- --help
# 或从 GitHub Releases 下载平台特定二进制
# 本地开发：
cargo install --path crates/vize --force --locked
```

## 命令总览

| 命令 | 说明 |
|------|------|
| `build` | 编译 Vue SFC |
| `fmt` | 格式化 |
| `lint` | 代码检查 |
| `check` | 类型检查（.vue/.ts/.tsx/.d.ts） |
| `doctor` | 应用健康诊断 |
| `inspector` | 编译器检查器 |
| `clean` | 清理缓存产物 |
| `ready` | fmt → lint → check → build 流水线 |
| `upgrade` | 更新 CLI |
| `check-server` | Unix JSON-RPC 类型检查服务 |
| `musea` | Musea 画廊脚手架 |
| `lsp` | LSP 服务器 |
| `ide` | 编辑器集成安装/管理 |

## 常用选项

```bash
# build
vize build --ssr                            # SSR 编译
vize build --continue-on-error              # 失败继续，最后汇总
vize build --declaration --declaration-dir dist/types  # 生成 .d.ts
vize build --script-ext preserve            # 保留 TS 输出
vize build --profile src                    # 打印编译耗时
vize build -o dist -f js src                # 指定输出目录和格式
vize build -j 4 src                         # 线程数控制

# fmt
vize fmt --check                            # CI：只检查不修改
vize fmt --single-quote --print-width 120   # 引号 + 行宽
vize fmt --sort-attributes                  # 排序属性
vize fmt --normalize-directive-shorthands   # 规范化指令缩写
vize fmt --tab-width 4 --use-tabs           # 缩进控制
vize fmt --single-attribute-per-line        # 每行一个属性
vize fmt --profile src                      # 打印格式化耗时

# lint
vize lint --cross-file                      # 跨文件分析
vize lint --cross-file-tree                 # 打印 provide/inject 树
vize lint --cross-file-complexity           # 跨文件复杂度报告
vize lint --strict-reactivity               # 响应式丢失检测
vize lint --fix                             # 自动修复
vize lint --max-warnings 0                  # 警告超限则失败
vize lint --format agent                    # AI 友好输出
vize lint --help-level short src            # 简短帮助信息
vize lint --quiet src                       # 仅显示摘要
vize lint --profile --slow-threshold 100 src  # 性能分析 + 慢文件阈值
vize lint --preset opinionated src          # 覆盖预设

# check
vize check --tsconfig tsconfig.app.json     # 指定 tsconfig
vize check --show-virtual-ts src/App.vue    # 查看虚拟 TS
vize check --declaration --declaration-dir dist/types  # 生成 .d.ts
vize check --profile                        # 性能分析
vize check --corsa-path ./node_modules/.bin/tsgo  # 覆盖 Corsa 路径
vize check --quiet src                      # 仅显示摘要
vize check -s /tmp/check.sock src           # 连接 check-server
vize check --servers 1 src                  # Corsa server 数（仅支持 1）

# doctor
vize doctor --format json                   # JSON 健康报告
vize doctor --root ./src                    # 工作区边界
vize doctor --exit-zero                     # 始终返回成功

# clean
vize clean --dry-run                        # 预览清理路径
vize clean --scope node-modules             # 仅清理 node_modules 下
vize clean --scope project                  # 仅清理项目下
vize clean --force                          # 强制移除产物根目录

# ready
vize ready --output dist --ssr              # 指定输出 + SSR
vize ready --script-ext preserve            # 保留 TS

# inspector
vize inspector --format agent --output report.json  # AI 可消费格式
vize inspector --format compare --output compare.json  # Vue vs Vize 对比（本地开发）
vize inspector --format url src/App.vue     # 生成 Playground URL
vize inspector --playground-url https://example.com/play  # 自定义 Playground 地址
vize inspector "src/**/*.vue" --target ssr  # 批量，指定 SSR 目标
vize inspector --max-files 10               # 限制批量文件数
vize inspector --custom-renderer            # 自定义渲染器模式

# ide
vize ide vscode                             # VS Code 集成
vize ide zed                                # Zed 集成
```

### Inspector 选项表

| 选项 | 说明 |
|------|------|
| `--target dom\|ssr` | 对比 VDOM 或 SSR 编译出 |
| `--format url` | 生成 Playground URL（默认） |
| `--format agent` | 生成 AI 可读 JSON（含 payload/Playground URL/摘要/跨文件图） |
| `--format compare` | 本地开发环境直接对比 Vue 官方编译器 |
| `--format json` | 标准 JSON payload |
| `-o, --output` | 将 URL 或 JSON payload 写入文件 |
| `--playground-url` | 覆盖 Playground 基础 URL |
| `--template-syntax` | `standard` \| `strict` \| `quirks` |
| `--max-files <n>` | 限制批量文件数 |
| `--custom-renderer` | Playground 自定义渲染器模式 |
