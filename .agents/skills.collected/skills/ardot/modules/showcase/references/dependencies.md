# Dependencies / showcase 模块特有依赖

共享的 Ardot MCP 工具集、环境排查、命名空间回退、padding 语法约束、
阻塞条件统一维护在 `../../../shared/dependencies.md`，本文件**不再重复**，
仅列出 showcase 模块**特有**的依赖。

执行前先读 `../../../shared/dependencies.md`。

## showcase 特有的必需工具

| 工具 | 用途 | 最低要求 |
|---|---|---|
| `locate_available_space` | 寻找展示区空位，避免覆盖已有画布 | 支持 `width` / `height` / `padding` / `direction` 参数；padding >= 400 |
| `capture_screenshot` | 生成后截图预览 | 能按 nodeId 截取 outer frame |

其他必需工具（`fetch_editor_state` / `batch_read` / `batch_edit`）见共享 dependencies。

## showcase 特有的推荐工具

| 工具 | 用途 |
|---|---|
| `get_available_fonts` | 字体不可用时查询目标文件可用字体，做可解释降级 |

## 宿主交互原语（非 MCP 工具）

各宿主叫法不同（`AskUserQuestion` / `ask_followup_question` / 其他等价
的选择题工具），按宿主当前暴露的名字调用。详见共享 dependencies
§宿主交互原语。

| 用途 | 典型场景 |
|---|---|
| 分组歧义时给用户单选确认 | Step 1.5 场景理解与分组确认 |

## showcase 特有的阻塞条件

共享阻塞条件之外，showcase 还有以下情况必须停止：

- 输入画板不可确定且用户未提供 nodeId
- `locate_available_space` 失败且用户未选择换页 / 清理 / 改布局
- 主题 preset 文件（`../assets/preset-config.json`）读取失败或 `$version` 与
  本 SKILL.md `metadata.version` 不一致

## showcase 特有的环境排查

| 现象 | 检查项 | 下一步 |
|---|---|---|
| 找不到空位 | 当前 page 是否空间不足 | 换页、清理画布、改矩阵降低宽度 |

其他排查（selection / currentPage / batch_edit 失败 / 视图未刷新）见共享
dependencies 与 `../../../shared/troubleshooting.md`。
