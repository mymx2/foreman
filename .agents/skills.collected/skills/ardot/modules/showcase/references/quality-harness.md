# Quality Harness / 质量门禁

本文维护运行恢复策略与发布前 smoke tests。完整问答见 `references/faq.md`。

## Harness 原则

- 能自动修复的，直接修复并复验。
- 必须用户参与的，只问一次选择题。
- 真正阻塞的，停止并给清晰操作指引。
- 发布前用 smoke tests 防止回归。
- 三条验证纪律见 `../../../shared/verification.md`。

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
| 不交付未执行的门禁 | 被检对象非空；新增或改口径的门禁有一次失败记录，报告里能贴出失败断言名与失败消息 | 补齐读取后重验；仍无法验证则停止并请用户确认，报告中单列「未机械校验项」 |

## 运行时恢复策略

| 等级 | 处理方式 | 示例 |
|---|---|---|
| A 自动修复 | agent 自行修复并复验，不打断用户 | sizing 塌陷、标题左对齐、字体降级、主题对比度 |
| B 单次确认 | 给 2-4 个选项，只问一次 | 分组歧义、旧展示区替换/另起、单 row 过宽 |
| C 阻塞停止 | 停止并给清晰操作指引 | MCP 断开、未打开文件、未选中画板且无 nodeId |

## 自动修复清单

- outer 尺寸塌陷：检查 UI region / group / row sizing，改回 hug；titlebar 固定为 computedOuterWidth。
- 标题与内容左边缘不齐：套用 skeleton-spec 的「对齐硬契约」，复验 `absoluteBoundingBox.x`，容差见 `skeleton-spec.md` §6.1。
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

每条 smoke test 必须留下证据：读字段类检查用 nodeId + 字段 + 期望值/实测值（从 `batch_read` 原样贴 JSON 片段）；视觉类用截图路径 + 覆盖 nodeId/bounds + 区域与尺寸；错误路径用错误文本 + 复现步骤。红证另贴失败断言名与失败消息；缺对应形式的证据记「未执行」。读字段类检查是初筛，冲突时以截图复判（`../../../shared/verification.md` 的「属性不等于渲染」）。

| 测试 | 成功标准 |
|---|---|
| 选中 3 个 mobile 整页 | ROW 横排；不覆盖已有画板；返回截图和链接 |
| 选中 page | 正确读取子画板；分组歧义时只问一次 |
| 说「白底」 | 背景白、文字黑，无白底白字 |
| 说「灰底」 | 背景浅灰、文字近黑，对比度可读 |
| 同一链路 5 状态 | 单 group；按智能评分选择 ROW/COLUMN/MATRIX；不插 column divider |
| 不同模块并列 | 只在模块边界插 column divider |
| column divider 拉通 | divider 用 `RECTANGLE + height:"fill_container"`；`batch_read` 高度达到 `skeleton-spec.md` §6.1 的比例下限，无「只显示上半段」 |
| 标题对齐 | title row / subtitle / group label / cell row 左边缘一致（容差见 `skeleton-spec.md` §6.1） |
| outer 圆角 | outer frame 默认 100px 圆角，不是方角 |
| MCP 错误 | 不抛原始 API 错误；给用户下一步操作 |
| 门禁自检 | 自上次发布以来新引入或改口径的门禁有一次失败记录，记录含失败断言名、失败消息、预期失败判据（期望值 vs 实测值）、截图路径或 nodeId + 字段实测值；本版无新增/改口径门禁时记 N/A，并列出上次红证的门禁名与版本 |

## 发包检查命令

在模块根目录（`modules/showcase/`）下运行：

```bash
python3 -m json.tool assets/preset-config.json >/dev/null
find . -name .DS_Store -print
python3 - <<'PY'
import json, re
from pathlib import Path
root = Path('.').resolve()
skill = (root / 'SKILL.md').read_text(encoding='utf-8')
front = re.search(r'^\s*version:\s*"([^"]+)"', skill, re.M).group(1)
history = re.search(r'^### v([0-9.]+) \(', skill, re.M).group(1)
preset = json.loads((root / 'assets/preset-config.json').read_text(encoding='utf-8'))['$version']
assert front == history == preset, (front, history, preset)
layout_path = root.parent / 'layout-adapt' / 'SKILL.md'
if layout_path.exists():
    layout = layout_path.read_text(encoding='utf-8')
    layout_front = re.search(r'^\s*version:\s*"([^"]+)"', layout, re.M).group(1)
    layout_history = re.search(r'^### v([0-9.]+) \(', layout, re.M).group(1)
    assert layout_front == layout_history, (layout_front, layout_history)
    layout_version = layout_front
else:
    layout_version = 'skipped (layout-adapt not found)'
umbrella_path = root.parent.parent / 'SKILL.md'
if umbrella_path.exists():
    umbrella = umbrella_path.read_text(encoding='utf-8')
    umbrella_front = re.search(r'^\s*version:\s*"([^"]+)"', umbrella, re.M).group(1)
    umbrella_history = re.search(r'^### v([0-9.]+) \(', umbrella, re.M).group(1)
    assert umbrella_front == umbrella_history, (umbrella_front, umbrella_history)
    umbrella_version = umbrella_front
else:
    umbrella_version = 'skipped (umbrella not found)'
print('version ok:', front, layout_version, umbrella_version)
PY
```

若第二条有输出，先删除 `.DS_Store` 再打包。
