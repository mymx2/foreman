# Dependencies · 环境与依赖

本文说明伞技能 `ardot` 下**所有模块**共同依赖的 Ardot MCP 工具集与环境排查方式。执行任何模块前先确认 Ardot 已打开目标文件，MCP 已连接。

## 必需工具

| 工具 | 用途 | 最低要求 |
|---|---|---|
| `fetch_editor_state` | 读取当前文件、页面、selection | 能返回 `currentPage.id` 与 `selection` |
| `batch_read` | 读取入口节点、子结构、生成后校验 | 支持 `readDepth >= 2`、`resolveInstances: true`、按 `properties` 过滤 |
| `batch_edit` | 创建 / 更新 / 复制 / 删除 / 移动节点 | 使用 `operations` 字符串语法；不使用旧版 `edits[]` |
| `locate_available_space` | 放置新画板时寻找空位 | 支持 `width` / `height` / `padding` / `direction` 参数 |
| `capture_screenshot` | 生成后截图预览 | 能按 nodeId 截取 |
| `get_available_fonts` | 字体查询与降级 | 返回准确 `family + style` |

## 宿主交互原语（非 MCP 工具）

以下能力**不是 Ardot MCP 工具**，是 Agent 宿主的对话原语。各宿主叫法不同
（`AskUserQuestion` / `ask_followup_question` / 其他等价的选择题工具），
按宿主当前暴露的名字调用，**不要在 MCP 工具列表里找**。

| 用途 | 典型场景 |
|---|---|
| 给用户单选确认（2-4 个选项 + 自定义输入） | 分组歧义、网格密度选择、覆盖确认 |

## 推荐工具（按模块需要）

| 工具 | 用途 |
|---|---|
| `fetch_styles` / `fetch_variables` | 读取 design token，生成时优先绑 token |
| `apply_variables` | 把已有节点属性绑到 token |
| `fetch_guidelines` | 读 Ardot 官方设计 / 编码规范 |
| `create_new_page` | 跨页编排 |
| `html_to_ardot` | 把 HTML 渲染结果导入 Ardot 画板 |
| `register_assets` / `upload_images` | 注册图片资产 |
| `export_nodes` / `export_variables` | 导出节点 / token |
| `fetch_component_lib` | 读组件库 |
| `fetch_file_info` | 读文件元信息，命名空间探测 |

## 版本与语法约束

- `batch_edit` 必须使用当前 Ardot MCP 的 `operations` **字符串语法**
- 每个 Insert / Copy 操作必须有 binding 名
- 单次 batch 操作建议不超过 25 条；超过时先建外层容器，再分批生成内部节点
- **禁止**在 `locate_available_space` 失败后降级为手写坐标
- `padding` 字段用数组 `[T, R, B, L]` 或四个独立属性，**不接受 CSS 简写字符串**

## 环境排查

| 现象 | 检查项 | 下一步 |
|---|---|---|
| 读取不到 selection | 是否在 Ardot 里选中了画板 / page | 让用户选中内容或提供 nodeId |
| 读取不到 currentPage | Ardot 是否打开目标文件 | 让用户打开文件后重试 |
| 找不到空位 | 当前 page 是否空间不足 | 换页、清理画布、改矩阵降低宽度 |
| `batch_edit` 失败 | 是否仍使用旧 `edits[]`；单次操作是否过多 | 改 `operations`，分批写入 |
| 写入成功但看不到 | Ardot 视图未刷新 | `Cmd+R` 或点击画布空白处刷新 |
| 字体缺失 | 目标文件没有指定 `fontName` | 调 `get_available_fonts` 选可用字体 |

完整排障对照表见 `shared/troubleshooting.md`。

## 阻塞条件

以下情况必须停止，不要继续操作：

- Ardot MCP 断开（两个命名空间都不通）。
- 目标文件或页面不可确定。
- 输入画板不可确定且用户未提供 nodeId。
- `locate_available_space` 失败且用户未选择换页 / 清理 / 改布局。
- 任何 MCP 工具连续 3 次返回同一错误。

## 命名空间回退（NO_ADAPTER）

Ardot MCP 工具可能以多个命名空间暴露，例如 `mcp__ardot__*` 与 `mcp__ardot-design__*`。

**实测遇到过**：`mcp__ardot__*` 调用返回 `NO_ADAPTER: No adapter found for routeKey ...`（路由失效），但同一时刻 `mcp__ardot-design__*` 命名空间是活跃可用的。

**处理顺序**：

1. 某个命名空间**持续报 NO_ADAPTER**（连续 3 次重试无效）→ **先切换到另一个 ardot 命名空间重试同一调用**（如 `ardot` ↔ `ardot-design`），而不是立即判定 Ardot 不可用
2. 用 `fetch_file_info` / `fetch_editor_state` 探测哪个命名空间能正常返回，后续**全程固定用那一个**
3. 两个命名空间都不通 → 走 `shared/troubleshooting.md` §MCP 连接诊断

## padding 语法约束

`batch_edit` 的 `padding` 不接受简写字符串（如 `"0 200 200 200"`），会报：

```text
Invalid padding value, expected [number] or [number, number] or [number, number, number, number]
```

正确写法二选一：

- 数组：`padding: [0, 200, 200, 200]`（T R B L）
- 或四个独立属性：`paddingTop: 0, paddingRight: 200, paddingBottom: 200, paddingLeft: 200`

四边相等时可直接用单个数字：`padding: 200`。

## MCP 端口与数据接口

`modules/layout-adapt/scripts/ardot-client.js` 封装了两步探活：

- **第一步**：探活 `http://127.0.0.1:50501/api/v1/health`（GET），通了 → HTTP 数据接口 `http://127.0.0.1:50501/api/v1/mcp`（JSON-RPC `batch_read`）
- **第二步**（第一步不通时）：探活 `http://127.0.0.1:19501/api/v1/health`（GET），通了 → WebSocket 数据接口 `ws://127.0.0.1:19501/ws/adapters`（socket.io `batch_read`）

只有 `modules/layout-adapt` 走脚本数据通道。其他模块全部通过 MCP 工具直连。
