# Quality Harness / 质量门禁

本文维护运行恢复策略与发布前 smoke tests。完整问答见 `references/faq.md`。

## Harness 原则

- 能自动修复的，直接修复并复验。
- 必须用户参与的，只问一次选择题。
- 真正阻塞的，停止并给清晰操作指引。
- 发布前用 smoke tests 防止回归。

## 不可触犯契约

以下契约优先级高于默认布局偏好。违反任一条，不能报告完成，必须重排、修复或停止询问用户。

| 契约 | 硬性要求 | 失败处理 |
|---|---|---|
| 不生成超宽画布 | `outerWidth <= 3200` 或 `outerWidth / outerHeight <= 3.2` | 改 COLUMN/MATRIX；若语义冲突则让用户确认 |
| 不生成超长画布 | `outerHeight <= 2400` 或 `outerHeight / outerWidth <= 2.6` | 改 ROW/MATRIX 或拆分展示区 |
| 不覆盖已有内容 | 必须使用 `locate_available_space`，padding 不低于 400 | 失败则停止，不准手写坐标降级 |
| 不打散用户原结构 | 用户手动竖排/网格/分组是强信号 | 保持原结构或提问确认 |
| 不交付未校验结果 | 必须 `batch_read` 复验尺寸、对齐、圆角、主题、divider，并截图预览 | 失败自动修复；修不了则说明原因 |
| 不交付不可读标题 | subtitle 使用「客户端 · 链路/设计稿说明」，不写数量信息 | 重新生成标题文案 |

## 运行时恢复策略

| 等级 | 处理方式 | 示例 |
|---|---|---|
| A 自动修复 | agent 自行修复并复验，不打断用户 | sizing 塌陷、标题左对齐、字体降级、主题对比度 |
| B 单次确认 | 给 2-4 个选项，只问一次 | 分组歧义、旧展示区替换/另起、单 row 过宽 |
| C 阻塞停止 | 停止并给清晰操作指引 | MCP 断开、未打开文件、未选中画板且无 nodeId |

## 自动修复清单

- outer 尺寸塌陷：检查 UI region / group / row sizing，改回 hug；titlebar 固定为 computedOuterWidth。
- 标题与内容左边缘不齐：套用 skeleton-spec 的「对齐硬契约」，复验 `absoluteBoundingBox.x`，容差 ±1px。
- 字体不可用：调用 `get_available_fonts`，按目标文件可用中文字体降级，并在结果说明中标 TODO。
- 主题对比度不达标：重新应用 preset，背景与主前景色成对切换。

## 需要用户确认的情况

- 分组存在多种合理解释。
- 页面已有同名旧展示区，需要选择替换 / 另起 / 取消。
- 单 row 过宽，需要选择改 MATRIX / 向下找位 / 拆分展示区。
- 单次写入大量节点，可能明显改变页面结构。

普通新增展示区不需要额外确认，避免降低效率。

## 阻塞提示模板

```text
和 Ardot 的连接断了。请确认 Ardot 已打开、MCP 已连接，然后让我重试。
```

```text
没检测到选中的画板。请在 Ardot 里选中要排版的画板，或直接告诉我画板 nodeId。
```

```text
当前页面没有足够空位放展示区。可以换一个页面、清理画布，或让我改成多行矩阵减少宽度。
```

## 发布前 Smoke Tests

| 测试 | 成功标准 |
|---|---|
| 选中 3 个 mobile 整页 | ROW 横排；不覆盖已有画板；返回截图和链接 |
| 选中 page | 正确读取子画板；分组歧义时只问一次 |
| 说「白底」 | 背景白、文字黑，无白底白字 |
| 说「灰底」 | 背景浅灰、文字近黑，对比度可读 |
| 同一链路 5 状态 | 单 group；按智能评分选择 ROW/COLUMN/MATRIX；不插 column divider |
| 不同模块并列 | 只在模块边界插 column divider |
| column divider 拉通 | divider 用 `RECTANGLE + height:"fill_container"`；`batch_read` 高度 ≥ 相邻 cell 最大高度 95%，无「只显示上半段」 |
| 标题对齐 | title row / subtitle / group label / cell row 左边缘一致（±1px） |
| outer 圆角 | outer frame 默认 100px 圆角，不是方角 |
| MCP 错误 | 不抛原始 API 错误；给用户下一步操作 |

## 发包检查命令

在模块根目录（`modules/showcase/`）下运行：

```bash
python3 -m json.tool assets/preset-config.json >/dev/null
find . -name .DS_Store -print
```

若第二条有输出，先删除 `.DS_Store` 再打包。
