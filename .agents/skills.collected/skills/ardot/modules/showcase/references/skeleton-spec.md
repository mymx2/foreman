# Showcase Skeleton / 骨架数值合同

本文是 `ardot-showcase-autolayout` 的核心数值合同。执行 SKILL.md Step 3 前必须读取。默认数值来自 `dark-review` preset；其他 preset 可覆盖字号、颜色和间距，但不改变结构层级。

## 1. Frame 层级

展示区固定为 4 层主骨架，不增不减：

```text
[L0] Outer FRAME — "<team>_<business>·<scene>·衍生展示区"
 ├── [L1] Titlebar FRAME
 │     ├── [L2] Title row (HORIZONTAL, 3 TEXT segments)
 │     └── [L2] Subtitle TEXT
 └── [L1] UI region FRAME
       └── [L2] Group FRAME (one per logical bucket; 1..N)
             ├── [L3] Group label TEXT
             └── [L3] Cell row FRAME
                   ├── [L4] Cell column FRAME (one per cell)
                   │     ├── Mini-title (Style A/B/C/D)
                   │     └── Cell content (ref / FRAME copy / image)
                   └── Optional LINE divider between adjacent cells
```

常见情况是单 group：`状态对照`。多 group 用于二维矩阵，例如设备 × 状态、角色 × 场景。

## 2. 分层规格

### L0 — Outer FRAME

| Property | Value |
|---|---|
| `name` | `<team>_<business>·<scene>·衍生展示区`，必须以 `衍生展示区` 结尾 |
| `layoutMode` | `VERTICAL` |
| `itemSpacing` | `50` |
| `padding` | `0 0 0 0` |
| `primaryAxisSizingMode` | hug，通过 `height: "hug_contents"` 或对应 shorthand 实现 |
| `counterAxisSizingMode` | hug，通过 `width: "hug_contents"` 或对应 shorthand 实现 |
| `fills` | 使用 preset.background；目标文件有 token 时优先绑定 token |
| `cornerRadius` | 默认 `100`，来自 preset `outer.cornerRadius`；不要生成方角外框 |

### 对齐硬契约（标题歪掉的根因，必读）

展示区里所有左对齐元素**必须共享同一条左基准线**：

```text
左基准线 X = uiSidePadding（默认 200）
  ├── Titlebar 的 title row 左边缘
  ├── Titlebar 的 subtitle 左边缘
  ├── 每个 group label 左边缘
  └── 每个 cell row 左边缘
```

要让这条基准线成立，必须同时满足以下三组属性，缺一就会"歪掉"：

1. **Titlebar 左右 padding == UI region 左右 padding**（都用 `uiSidePadding`，默认 200）。两者不一致 → 标题相对内容左移/右移。
2. **Titlebar 自身子节点左对齐**：`counterAxisAlignItems = MIN`。不设或设成 CENTER → title row 与 subtitle 会整体居中，相对下方内容偏移。
3. **Title row 内部文字靠左聚拢**：`primaryAxisAlignItems = MIN` + `layoutAlign = MIN`。不设 → 三段文字可能被拉成两端对齐或居中，日期段跑到右侧。

> 历史教训："标题和内容没按规则排、歪掉"几乎都是上面第 2/3 条缺失导致的。生成后必须用 `batch_read` 复查 title row 与第一个 group label 的 `absoluteBoundingBox.x` 是否一致（容差 ±1px）。

### L1 — Titlebar FRAME

| Property | Value |
|---|---|
| `name` | `Titlebar` |
| `layoutMode` | `VERTICAL` |
| `itemSpacing` | `40` |
| `padding` | `200 200 200 200`（T R B L，左右必须等于 `uiSidePadding`） |
| `primaryAxisSizingMode` | `FIXED`，height = `450` |
| `counterAxisSizingMode` | **`FIXED`，width = computed outerWidth** |
| `counterAxisAlignItems` | **`MIN`（子节点左对齐，保证标题与下方内容同一左基准线）** |
| `layoutAlign` | `INHERIT`，不要写 `STRETCH` |

为什么 titlebar 用 FIXED：outer hug 与子层 STRETCH 同时存在时，部分 Ardot 文件会把 outer 宽度塌成 titlebar 文本宽，而不是 UI region 宽。规则是：先按公式算出 outerWidth，再把 titlebar 宽度显式写成这个值。

### L2 — Title row

| Property | Value |
|---|---|
| `layoutMode` | `HORIZONTAL` |
| `itemSpacing` | `40` |
| `primaryAxisAlignItems` | **`MIN`（三段文字靠左聚拢，日期不要被推到右侧）** |
| `counterAxisAlignItems` | `CENTER`（三段文字垂直居中对齐） |
| `layoutAlign` | **`MIN`（title row 自身在 titlebar 内靠左）** |
| Children | 三个 TEXT，顺序固定为：product / topic / date |

`primaryAxisAlignItems` 必须是 `MIN`，**绝不能用 `SPACE_BETWEEN`**——后者会把日期段甩到最右边，造成"标题三段被拉散、看起来歪"的典型错误。

日期永远放在最后，不要夹在 product 和 topic 之间。不要用 `BASELINE`。中英混排或不同字体度量下，BASELINE 容易让日期段下沉；CENTER 更稳定。

Title TEXT 默认：

| Property | `dark-review` | `presentation` |
|---|---:|---:|
| `fontSize` | `96` | `120` |
| `fontWeight` | `Regular 400` | `Medium 500` |
| `fills` | white-100 token | white-100 token |

### L2 — Subtitle TEXT

| Property | Value |
|---|---|
| Content | `<客户端> · <链路/设计稿说明>` |
| `fontSize` | `36` |
| `fontWeight` | `Regular 400` |
| `fills` | white at 40% opacity；此处允许 raw 透明色 |

`<客户端>` 根据 UI 场景填写，使用英文小写：`mobile` / `desktop` / `web` / `tablet`。多端组合用 ` + ` 连接，例如 `mobile + desktop`、`mobile + web`。

`<链路/设计稿说明>` 写一句短中文，说明这个展示区是什么链路或设计稿。不要写 `3 屏对照` / `5 个状态` 这类数量信息，数量可以从画面本身看出，不要占用标题信息密度。

示例：

```text
desktop · WorkBuddy 中调用网盘链路
web · 官网购买页流程
mobile + desktop · 登录链路设计稿
```

Subtitle 不要全英文，不要使用 `screens` / `cards` / `flows` 作为首段，也不要重复 titlebar 的 `<topic>` 或大标题。

### 日期格式

日期段是 title row 的最后一个 TEXT，使用弱化前景色（例如 white-40），用于标记展示区生成或评审日期。

| 场景 | 格式 | 示例 |
|---|---|---|
| 单日 | `YYYY.M.D` | `2026.5.20` / `2026.12.3` |
| 区间 | `YYYY.M.D – YYYY.M.D` | `2026.5.10 – 2026.5.20` |

不要写旧格式 `5.20`，也不要写 ISO 格式 `2026-05-20`。

### L1 — UI region FRAME

| Property | Value |
|---|---|
| `name` | `UI` |
| `layoutMode` | `VERTICAL` |
| `itemSpacing` | `100` |
| `padding` | `0 200 200 200` |
| `primaryAxisSizingMode` | hug |
| `counterAxisSizingMode` | hug |

### L2 — Group FRAME

| Property | Value |
|---|---|
| `name` | 逻辑分组名，例如 `状态对照`、`Devices`、`Personas` |
| `layoutMode` | `VERTICAL` |
| `itemSpacing` | `40` |
| `padding` | `0 0 0 0` |
| `primaryAxisSizingMode` | hug |
| `counterAxisSizingMode` | hug |
| `counterAxisAlignItems` | `MIN`（group label 与 cell row 左对齐） |

单 group 也要保留 group label，便于与 matrix 展示保持一致。

### L3 — Group label TEXT

| Property | Value |
|---|---|
| `fontSize` | `60` |
| `fontWeight` | `Regular 400` |
| `fills` | 主前景 token（深色背景用 white-100，浅色背景用 black-90，跟随 preset） |
| `textAlignHorizontal` | `LEFT` |

### L3 — Cell row FRAME

| Property | Value |
|---|---|
| `name` | `Row` |
| `layoutMode` | `HORIZONTAL` |
| `itemSpacing` | `40` |
| `padding` | `0 0 0 0` |
| `primaryAxisSizingMode` | hug |
| `counterAxisSizingMode` | hug |

#### Column dividers

Column divider（垂直 LINE 分隔线）用于**区分同一 group 内属于不同能力/功能模块的 cells**，而不是区分同一能力下的多个状态。

**何时加**：同一个 group 的 cell row 中，有来自**不同能力或不同功能模块**的屏幕并列，且 N≥3，在能力/模块边界处插入分隔线。

示例：
- 同一 group 内展示「模块 A（2 屏）+ 模块 B（2 屏）」两个不同功能 → 在模块 A 最后一个 cell 和模块 B 第一个 cell 之间插 1 条分隔线。
- 同一 group 内只展示「某模块的 3 个状态」（同一链路）→ **不加分隔线**，状态切换是连续流动，视觉上应保持统一节奏。

**何时不加**：
- cells 全部属于同一能力/场景下的多状态（同一链路）→ 不加。
- N=2（只有 2 个 cells 或 2 个模块）→ 不加，左右间距已足够区分。

| Property | Value |
|---|---|
| `type` | **`RECTANGLE`**（不要用 LINE） |
| `width` | `1` |
| `height` | **`"fill_container"`（关键：自动撑满行高，禁止写死数值）** |
| `fills` | `divider-subtle` token；无 token 时 raw white α=0.16 |

divider 作为 cell row 子节点穿插，插在不同模块的 cell 之间：

```text
[模块A_cell, 模块A_cell, divider, 模块B_cell, 模块B_cell]
```

因为 `itemSpacing=40` 同时作用于 cell↔divider 和 divider↔cell，等效模块间距为 `40 + 1 + 40 = 81`，模块内相邻 cell 间距为 `40`。

#### 为什么用 RECTANGLE + fill_container，不用 LINE（bug 根因，必读）

历史 bug：同事调用后反馈「分割线只显示上面一小段，没拉通到底」。根因是旧规格用 `LINE + rotation=90 + length=cell 高度`，而 `length` 需要**手动**算出并写死一个数值。当 cell 因内容自适应高度、或行内多个 cell 高度不一致（如 500/550/600）时，写死的 length 只覆盖到当初估算的那一段，下半段留空。

正确做法（已实测验证）：cell row 是 `layout: HORIZONTAL`，行高由最高 cell 决定。divider 用 `RECTANGLE` 且 `height: "fill_container"`，会自动被拉伸到行的实际高度，**无需读取、无需计算、无需 two-pass**。实测：相邻 cell 高度分别为 600/500/550 时，两条 fill_container 分割线都自动撑到 600，完整拉通到底。

> 禁止再用 `LINE + rotation + 写死 length` 的旧写法。若必须用 LINE 兜底（个别文件不支持 RECTANGLE fill_container），则必须在生成后 `batch_read` 读取相邻 cell 的 `absoluteBoundingBox.height` 取最大值回写为 length，并按 §7 Reject Signal 复验。

### L4 — Cell column FRAME

| Property | Value |
|---|---|
| `name` | 单元格标签，例如 `默认态`、`Error State` |
| `layoutMode` | `VERTICAL` |
| `itemSpacing` | `16` |
| `padding` | `0 0 0 0` |
| `primaryAxisSizingMode` | hug |
| `counterAxisSizingMode` | `FIXED`，width = cell intrinsic width |

如果 mini-title 使用多段 TEXT 并包在一个水平 Frame 中，该 Frame 的 `counterAxisAlignItems` 必须为 `CENTER`。

## 3. Mini-title 样式

### Style A — 纯标题

单 TEXT，适用于普通 cell 标题。

| Property | Value |
|---|---|
| `fontSize` | `24` |
| `lineHeight` | `32 PIXELS` |
| `fontWeight` | `Regular 400` |
| `fills` | white-100 token |

### Style B — 标题 + 灰色后缀

用于弱提示后缀，例如 `·empty`、`·loading`、`·premium`。主段 white-100；后缀 white at 40% opacity。

```text
[ "登录页" ][ "·校验失败" ]
   white-100      white-40 raw
```

### Style C — 标题 + 状态色后缀

用于同场景多状态对照。主段 white-100；后缀使用状态色 token，opacity=1。

| 状态语义 | 后缀文字 | token |
|---|---|---|
| 新增 / 主推 / 进行中 | `·新增`、`·进行中` | `state-info` |
| 修改 / 调整 | `·修改`、`·调整` | `state-warning` |
| 废弃 / 移除 | `·废弃`、`·移除` | `state-error` |
| 灰度 / 实验 | `·灰度` | `state-info` |

```text
[ "页面首页" ][ "·新增" ]
   white-100       state-info
```

### Style D — 标题 + 状态色后缀 + 灰色补充

用于需要额外说明来源、版本、备注的状态标题。

```text
[ "页面首页" ][ "·新增" ][ " · v2.0" ]
   white-100       state-info     white-40 raw
```

### 样式选择

```text
mini-title 是否有状态修饰词（新增/修改/废弃/灰度/...）？
  ├─ 否 → Style A
  └─ 是 → 是否需要颜色高亮？
          ├─ 否 → Style B
          └─ 是 → 是否需要补充信息？
                  ├─ 否 → Style C
                  └─ 是 → Style D
```

默认：同场景多状态展示使用 Style C。

## 4. Outer 尺寸公式

调用 `locate_available_space` 前必须先算 outer 尺寸。

### 单 group ROW：无 column dividers

适用：N=2，或 cells 不是同一场景多状态。

```text
outerWidth  = 2 × 200 + N × cellWidth + (N − 1) × 40

outerHeight = 450       // titlebar fixed
            + 50        // outer itemSpacing
            + 60        // group label height
            + 40        // group itemSpacing
            + 16        // mini-title 和 cell 之间的 spacing
            + cellHeight
            + 200       // UI bottom padding
```

### 单 group ROW：含 column dividers

适用：同一 group 内存在不同能力/模块边界，且 N≥3。

```text
outerWidth  = 2 × 200 + N × cellWidth + (N − 1) × 81
outerHeight = 同上
```

5 屏移动端示例（cellWidth=402，cellHeight=874）：

- 无 dividers：outerWidth = 400 + 5×402 + 4×40 = **2570**；outerHeight = **1690**。
- 有 dividers：outerWidth = 400 + 5×402 + 4×81 = **2734**；outerHeight = **1690**。

允许向上取整 32px，给不同字体渲染留余量。

### 多 group MATRIX

```text
outerHeight = 450 + 50 + Σ groupHeight + (groupCount − 1) × 100 + 200
outerWidth  = max(each group width)
```

### 单列 COLUMN

适用：裸组件纵向堆叠。

```text
outerWidth  = 2 × 200 + cellWidth
outerHeight = 450 + 50 + 60 + 40
            + N × cellHeight
            + (N − 1) × 16
            + 200
```

## 5. 颜色与 token 绑定

原则：能用 preset token 的颜色不要 inline。

| Token Slot | 语义 | 用于 |
|---|---|---|
| `white-100` | 深色背景主前景 | 标题、group label、mini-title 主段 |
| `black-90` | 浅色背景主前景 | light-review preset |
| `state-info` | 信息 / 新增 | Style C/D 后缀 |
| `state-warning` | 警告 / 修改 | Style C/D 后缀 |
| `state-error` | 错误 / 废弃 | Style C/D 后缀 |
| `state-success` | 成功（备用） | 预留 |
| `divider-subtle` | 弱分隔线 | column dividers |

允许 raw 的两类透明色：

1. white at 40% opacity：subtitle、Style B/D 灰色补充段。
2. black at 40% opacity：light-review subtitle。

其他颜色应走 token。目标文件没有 token 时，用 preset raw color 兜底并标 TODO。

## 6. Responsive Backbone

必须保持以下 sizing 规则：

| Frame | primaryAxisSizingMode | counterAxisSizingMode |
|---|---|---|
| L0 outer | hug | hug |
| L1 titlebar | FIXED (450) | **FIXED (= computed outerWidth)** |
| L1 UI region | hug | hug |
| L2 group | hug | hug |
| L3 cell row | hug | hug |
| L4 cell column | hug | FIXED (cell width) |

Ardot API 不接受 `primaryAxisSizingMode: "AUTO"`。需要 hug 时，用 `width: "hug_contents"` / `height: "hug_contents"` shorthand。

若 `batch_read` 发现 outer 宽度异常变小，优先检查：

1. Cell row 的 counterAxisSizingMode 是否误写成 FIXED。
2. UI region 是否写死 width，而不是 hug。
3. Titlebar 是否没有按 computed outerWidth 写 FIXED。

## 7. Reject Signals

出现以下任一情况，修复后再交付。Reject signal 是可修复问题，不要把半成品报成完成。尺寸类硬约束同时见 `quality-harness.md`「不可触犯契约」。

1. **未做场景分组确认**：存在多种合理分组方式，但直接拍板分组生成展示区，未向用户确认（除非满足 Step 1.5 的全部跳过条件）。
2. **打散原始画布既有结构**：入口节点已有 Section / 命名前缀 / 容器分组等明确语义，但生成时被重新洗牌。
3. **把重复画板当成版本差异**：两个 cell 内容完全一致，应提醒用户合并或确认意图，不能虚构状态语义。
4. **轴向错误**：只按内容类型拍板，没有评估原始排布、候选尺寸和超长风险；或用户已手动竖排仍强行 ROW；或最终 `outerWidth > 3200` / `outerHeight > 2400` 却未重排或确认。
5. **未调用 `locate_available_space`**：手写坐标放置 outer frame，必须改为自动寻位。
6. **颜色未走 preset**：可绑定 token 的颜色被直接写成 `#000000` / `rgba(...)`。
7. **尺寸塌陷**：outer 宽高与 §4 公式偏差超过 ±32，通常是某层 sizing 错用了 FIXED。
8. **缺 mini-title**：cell 裸放，没有顶部小标题。
9. **titlebar 日期位置或格式错误**：标题栏必须按 product / topic / date 排列，日期放最后，格式为 `YYYY.M.D`。
10. **展示区互相贴边或重叠**：`locate_available_space` 的 padding 低于 400，或没有使用返回坐标。
11. **outer 命名或外观错误**：不符合 `<team>_<business>·<scene>·衍生展示区`，或末尾不是 `衍生展示区`；outer 未设置 100px 圆角。
12. **mini-title 样式错误**：含 `新增` / `修改` / `废弃` / `灰度` 等状态词，但没有用状态色 Style C/D。
13. **column divider 使用错误**：同一链路/场景多状态间加了分隔线；或同一 group 内不同能力/模块并列（N≥3）却没在模块边界加线；或 divider 用了 `LINE + 写死 length` 旧写法而非 `RECTANGLE + height:"fill_container"`。
    - **divider 高度未拉通**：生成后 `batch_read` 读 divider 的 `absoluteBoundingBox.height`，若低于相邻 cell 最大高度的 95%，即为「只显示上半段」bug，必须改用 `fill_container` 重生成。
14. **subtitle 首段错误**：仍使用 `screens` / `cards` / `flows` 等类型词，而不是 `mobile` / `desktop` / `web` / 多端组合。
15. **subtitle 信息密度错误**：写了 `3 屏对照` / `5 个状态` 等数量信息，或全英文，未写链路/设计稿说明。
16. **subtitle 重复标题**：说明段与 `<topic>` / 大标题重复，应省略或换成更具体的链路说明。
17. **日期仍写旧格式**：不要写 `5.20` 或 `2026-05-20`，应写 `2026.5.20`。
18. **标题与内容左边缘不齐**：title row / subtitle / group label / cell row 的左边缘 `absoluteBoundingBox.x` 不一致（容差 ±1px）。常见根因是 titlebar 未设 `counterAxisAlignItems: MIN` 或 title row 误用 `SPACE_BETWEEN`。
19. **主题对比度不达标**：切换主题后只改背景没改文字，或主前景色与背景明度差不足以阅读。背景与主前景必须成对取色。
