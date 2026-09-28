# Layout Decision Tree / 智能布局判断

本文是 SKILL.md Step 2 的详细版。先完成 `scene-grouping.md` 的分组确认，再决定每个 group 用 ROW、COLUMN 还是 MATRIX。

## 核心原则

不要只用「整页稿 = 横排」这条单规则。最终布局必须同时满足：

1. **尊重原始排布意图**：用户已手动竖排/分组的内容，除非明显错误，否则优先保留方向。
2. **控制展示区可读尺寸**：横排不能无限变长；纵排不能变成超深长图。
3. **保留业务语义**：不同设备、角色、模块、版本不要被打平成一条超长 row。
4. **减少用户二次手改**：如果横排结果明显需要用户手动改成竖排，说明判断失败。

## Step A — 读取原始排布先验

对入口节点 children 计算原始布局特征：

| 特征 | 判断方式 | 影响 |
|---|---|---|
| 明显横排 | children 的 y 差异小，x 递增明显 | ROW 加分 |
| 明显竖排 | children 的 x 差异小，y 递增明显 | COLUMN 加分 |
| 网格排布 | 同时存在多列多行 | MATRIX 加分 |
| 已有 section/group | 有容器语义 | 优先保留原分组 |

如果用户明确说「我手动改成竖向排布」或原始画布已经竖排，不能再机械改回 ROW。此时 COLUMN/MATRIX 先加权。

## Step B — 生成候选布局并评分

为每个 group 生成候选方案：ROW、COLUMN、MATRIX。用 skeleton-spec §4 的公式预估 outer 尺寸后评分。

### 推荐阈值

| 指标 | 建议阈值 | 超出后的倾向 |
|---|---:|---|
| `outerWidth` | 3200 px | ROW 扣分，考虑 COLUMN / MATRIX |
| `outerHeight` | 2400 px | COLUMN 扣分，考虑 ROW / MATRIX |
| `outerWidth / outerHeight` | 3.2 | 过宽，考虑 COLUMN / MATRIX |
| `outerHeight / outerWidth` | 2.6 | 过高，考虑 ROW / MATRIX |
| 单 row cell 数 | 4 个 | 超过时评估换行或 MATRIX |

这些阈值不是硬编码视觉尺寸，而是评审可读性的默认安全线。用户指定大屏演示或 presentation preset 时，可适度放宽。

### 评分公式

```text
score(layout) = semanticFit + sourceLayoutFit + sizeFit + scanFit - riskPenalty
```

| 项 | 含义 |
|---|---|
| `semanticFit` | 是否符合内容语义：整页状态 / 裸组件 / 多维矩阵 |
| `sourceLayoutFit` | 是否尊重原始画布横排、竖排或网格意图 |
| `sizeFit` | 预估 outer 宽高是否在阈值内 |
| `scanFit` | 评审者是否能一屏扫读，不需要超长横向拖动 |
| `riskPenalty` | 是否会导致超长、超高、分组语义丢失或需要用户手改 |

选择最高分方案。若最高分与第二名差距不明显，向用户确认一次。

## Step C — 常见决策

### 整页多状态

默认 ROW，但必须校验宽度：

- `outerWidth <= 3200` 且 cell 数 ≤ 4：ROW。
- `outerWidth > 3200` 或 cell 数 ≥ 5：优先考虑 COLUMN 或 MATRIX。
- 原始内容已经竖排：优先 COLUMN，除非用户明确要求横向对比。

### 裸组件 / 卡片状态

- 横向条状（宽而矮）：COLUMN。
- 纵向柱状（窄而高）：ROW。
- 数量较多：MATRIX 或按状态分组。

### 多维内容

出现设备 × 状态、角色 × 场景、模块 × 版本时，用 MATRIX。不要打平成超长 ROW。

### 用户已手动排好方向

用户手动调整过的方向是强信号：

- 手动竖排 → COLUMN/MATRIX 优先。
- 手动网格 → MATRIX 优先。
- 手动横排 → ROW 优先，但仍需通过宽度阈值。

## Step D — 需要用户确认的情况

只问一次：

- ROW 与 COLUMN 分数接近。
- 原始排布和内容语义冲突。
- 横排超宽但用户可能想要强对比。
- 改成 MATRIX 会改变用户现有观看顺序。

提问模板：

```text
我检测到横排会形成超长展示区，更适合竖排或矩阵。你希望：
A. 保持横排强对比
B. 改为竖排，更适合阅读
C. 改为矩阵，控制宽度
D. 保持原始排布
```

## 示例

### 示例 1：3 个 desktop 链路画板，原始已竖排

虽然是完整页面，但 desktop 画板横排会明显超宽，且用户已手动竖排 → COLUMN。

### 示例 2：5 个 mobile 状态

若 `outerWidth <= 3200`，ROW；若超过阈值或原始已竖排，改 COLUMN / MATRIX 并确认。

### 示例 3：4 个按钮变体 × 2 个设备

二维结构清晰 → MATRIX。

### 示例 4：通知条 4 状态

横向条状裸组件 → COLUMN。

## Reject signals

- 横排后 outerWidth 明显超长，仍未评估 COLUMN/MATRIX。
- 用户已手动竖排，技能又强行横排且未确认。
- 多维内容被打平成一条 row。
- 只按「整页稿」判断 ROW，没有做尺寸阈值和原始排布检查。
