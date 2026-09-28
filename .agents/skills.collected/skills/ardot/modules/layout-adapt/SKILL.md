---
name: layout-adapt
description: |
  设计稿自动布局文本适配 - 在 Ardot 上对设计稿进行响应式布局适配，
  确保文本内容变化时布局正确响应，不会出现溢出、截断、塌陷等问题。
  当用户需要翻译适配、国际化适配、响应式重排、防溢出修复时使用。
  不适用于：视觉品味审计、新建画板方向锁定、跨文件编排、纯静态
  单语言稿（无文本变化）。
  Triggers: "适配设计稿", "布局适配", "文本适配", "自动布局",
  "响应式布局", "翻译适配", "国际化适配", "防溢出", "layout adaptation".
metadata:
  version: "1.0.0"
  absorbed_from: "layout-adaptation (repros snapshot 2026-09-28)"
---

# 设计稿 - 自动布局文本适配规范

文本内容变化（翻译 / 国际化 / 响应式）时保证布局不溢出、不截断、不塌陷。

## Outcome Contract

- **Outcome**：目标画板内所有溢出的 TEXT 节点按策略分类修复完成，容器链水平宽度与垂直高度复查通过，截图验证无截断/塌陷。
- **Done when**：脚本 `--fetch` 输出的 Phase A（容器）+ Phase B（文本）全部 `batch_edit` 执行完毕；6.1 容器链水平宽度检查与 6.2 垂直高度检查每条路径都有结果；§七 验证流程的分模块截图与基线对比通过。
- **Evidence**：脚本 `output.json` / `report.md` 包含分类表（4.4）+ Gate 校验（4.3）+ 容器链检查（6.1）+ 修复操作；`batch_edit` 每批 ≤25 op；修复后 `capture_screenshot` 与基线对比无回归。
- **Output**：适配报告（修复节点详情 + padding 补偿值 + 跳过节点及原因 + 验证结果）+ 分模块截图。
- **Authorization**：AI 禁止手动推理分类与溢出判定（脚本确定性算法输出）；INSTANCE 容器与普通 FRAME 同等对待，禁止跳过；容器链中间容器仅改宽度，不自动改高度（除非该容器是溢出文本的直接父容器）。

---

### 脚本路径

- `scripts/layout-adaptation.js`（相对于本 SKILL.md 所在目录）— 主脚本，负责分类判定、修复操作生成等确定性算法
- `scripts/ardot-client.js` — Ardot 数据获取客户端，封装两步探活与 batch_read 数据获取

### 脚本处理的章节（确定性算法，禁止 AI 手动推理）

| 章节 | 脚本函数 | 说明 |
| --- | --- | --- |
| 第一章 硬性过滤 | `traverseNodes` / `isNodeHidden` | `visible: false` 整棵子树跳过 |
| 第二章 扫描范围 | `extractAllTexts` | 普通文本 + INSTANCE 内部文本（分号路径） |
| 4.1 策略分类 | `classifyStrategy` | 六策略 Match-First |
| 4.2 溢出分级 | `classifyOverflowGrade` / `checkParentOverflowsGrandparent` / `checkParentContentOverflow` | 多层溢出检测：文本→父容器 + 父容器→祖父容器 + 父容器子内容溢出 |
| 4.2.1 容器级溢出扫描 | `scanFixedContainerOverflow` | 遍历所有 FIXED 容器，检测子内容总宽度溢出（补充文本级检测盲区） |
| 4.3 Gate 校验 | `validateGate` | 四项检查 |
| 4.4 分类表格 | `formatClassificationTable` | Markdown 输出 |
| 5.2/6.2 Height 规则 | `computePaddingCompensation` | padding 补偿公式 |
| 6.1 容器链检查 | `checkContainerChainHorizontal` | parent 链遍历，INSTANCE 同等对待 |
| 第六章 修复操作 | `generateFixOperations` | 外→内拓扑排序，Phase A/B 分离，每批 ≤25 |

### AI 负责部分

| 步骤 | 说明 |
| --- | --- |
| 决定读取范围 | 确定要读取的节点 ID、`readDepth`、是否需要补充读取 |
| 检测环境 | 运行 `--detect` 判断当前环境是否支持 `--fetch` 模式 |
| 运行脚本 | 使用 `--fetch` 模式（脚本自动两步探活选择接口） |
| `batch_edit` 执行 | 按脚本输出的 Phase A → Phase B 顺序调用 `batch_edit` |
| 组件源锁定补偿 | `U()` 返回空 `updated: {}` 时，在外层包裹 FRAME 补偿（需设计决策） |
| 第七章 截图验证 | 分模块 `capture_screenshot`，对比基线图，判断溢出/截断/塌陷 |

### 执行流程

```
1. AI 调用 batch_read 确定读取范围（仅用于了解结构，不用于脚本输入）

2. AI 运行环境检测（脚本内两步探活）：
   node scripts/layout-adaptation.js --detect

   脚本自动执行两步探活（探活接口与数据接口分离）：
   - 第一步：探活 http://127.0.0.1:50501/api/v1/health（GET）
     通了 → HTTP 数据接口 http://127.0.0.1:50501/api/v1/mcp（JSON-RPC batch_read）
   - 第二步（第一步不通时）：探活 http://127.0.0.1:19501/api/v1/health（GET）
     通了 → WebSocket 数据接口 ws://127.0.0.1:19501/ws/adapters（socket.io batch_read）

3. 根据检测结果使用 --fetch 获取数据（统一模式，脚本自动选择接口）：

   node scripts/layout-adaptation.js \
     --fetch \
     --fileId  <文件ID> \
     --nodeIds <节点ID1,节点ID2,...> \
     --readDepth 5 \
     --output <output.json 的绝对路径> \
     --report <report.md 的绝对路径>

   > 未指定 --mcpUrl 时，--fetch 会自动两步探活选择可用接口。
   > 第一步通了用 50501 HTTP mcp 数据接口；第一步不通则用 19501 WebSocket 沙箱数据接口获取数据。

4. AI 读取 output.json（或 report.md），获取：
   → 分类表（4.4）
   → Gate 校验结果（4.3）
   → 容器链检查结果（6.1）
   → Phase A 容器操作（分批 U() 命令）
   → Phase B 文本操作（分批 U() 命令）

5. AI 按顺序调用 batch_edit 执行修复：
   → 先执行 Phase A 所有批次（容器，外→内）
   → Phase A 全部完成后，执行 Phase B 所有批次（文本）
   → **忽略 `batch_edit` 返回的字体类 `potentialIssues`**（如 "missing font"、"unavailable font"、"fallback font"），不做字体检测和调整

6. AI 按第七章分模块截图验证
```

> **数据获取方式**：
> 脚本内置两步探活，探活接口与数据接口分离：
> - **第一步**：探活 `http://127.0.0.1:50501/api/v1/health`（GET），通了 → HTTP 数据接口 `http://127.0.0.1:50501/api/v1/mcp`（JSON-RPC batch_read）
> - **第二步**（第一步不通时）：探活 `http://127.0.0.1:19501/api/v1/health`（GET），通了 → WebSocket 数据接口 `ws://127.0.0.1:19501/ws/adapters`（socket.io batch_read）
> - 两步均不通 → 报错，提示确认服务是否运行
>
> `--fetch` 模式未指定 `--mcpUrl` 时会自动两步探活选择可用接口。
> 第一步通了用 HTTP mcp 数据接口；第一步不通则用 WebSocket 沙箱数据接口获取数据。

### 大设计稿分批读取

设计稿节点数多时，单次读取可能返回不全（超过 500 子节点会压缩）。处理方式：多次运行，每次指定不同的节点 ID：
```bash
node scripts/layout-adaptation.js --fetch --fileId <id> --nodeIds <id1,id2> --output <output1.json 路径>
node scripts/layout-adaptation.js --fetch --fileId <id> --nodeIds <id3,id4> --output <output2.json 路径>
```

AI 合并多批结果的 Phase A/B 操作后统一执行 `batch_edit`。

### 模块格式兼容

如果运行环境使用 ES 模块（`package.json` 中有 `"type": "module"`），CommonJS 脚本会报错。解决方案：

- 将脚本重命名为 `layout-adaptation.cjs`，Node.js 会按 CommonJS 解析
- 或在脚本目录创建不含 `"type": "module"` 的独立 `package.json`

---

## 一、硬性过滤

命中以下任一条件的节点列入 Ignore List，永不参与后续流程：

| 条件 | 处理 |
| --- | --- |
| 文本自身 `visible: false` | 整棵子树跳过 |
| 父容器链上任意节点 `visible: false` | 整棵子树跳过 |

---

## 二、扫描范围

搜索目标节点下所有文本节点时，**必须同时展开 INSTANCE 内部子树**（设置 `resolveInstances: true`），一次性获取普通文本和 INSTANCE 内部文本。

- 普通文本 ID 格式为 `"nodeId"`（如 `"123:456"`），INSTANCE 内部文本 ID 格式为 `"instanceId;childId"`（分号分隔）
- 修复 INSTANCE 内部节点时，使用分号路径格式引用

> **禁止遗漏**：最终分类表格必须同时包含普通文本节点和 INSTANCE 内部文本节点。

---

## 三、全局规则

执行第一章到第七章时必须全程遵守的横向规则，主要是 INSTANCE 节点的同等对待。

### INSTANCE 强制处理规则

> **严禁因节点类型为 INSTANCE 而跳过检测或修复。INSTANCE 容器与普通 FRAME 容器完全同等对待。**

| 场景 | 强制行为 | 禁止行为 |
| --- | --- | --- |
| 属性读取 | `batch_read` 必须包含 INSTANCE 节点，设置 `resolveInstances: true` | 禁止因是 INSTANCE 而跳过读取 |
| 宽度/高度修改 | 直接对 INSTANCE 节点调用 `U(id, {width, height, ...})` | 禁止假设「INSTANCE 不可修改」而跳过 |
| 内部子节点修改 | 使用分号路径 `"instanceId;childId"` 引用内部文本/容器 | 禁止仅修改外部而忽略内部 |
| 组件源锁定 | `U()` 返回空 `updated: {}` → 在外层包裹 FRAME 补偿，而非放弃 | 禁止因锁定而整体跳过该路径 |
| 容器链检查(6.1) | INSTANCE 节点必须纳入沿链检查范围 | 禁止在祖先链遍历中遇到 INSTANCE 就停止 |

---

## 四、分类判定

> **本章由脚本 `scripts/layout-adaptation.js` 的 `classifyStrategy` + `classifyOverflowGrade` + `validateGate` 自动完成。AI 禁止手动推理分类，只需运行脚本读取结果。以下规则供脚本实现参考和结果校验。**

对每个 TEXT 节点按顺序 **Match-First** 分类，strategy 直接映射到修复动作（确定性算法，禁止主观推断篡改结果）。

> **强制数据校验**：分类表中所有父容器属性（`layoutSizingHorizontal`、`layoutMode`、`width` 等）**必须来自 `batch_read` 实际返回值**，禁止推断。未获取到的必须补充读取。
> **INSTANCE 容器和普通 FRAME 容器必须同等对待，不得因为"是 INSTANCE"而跳过属性读取。**

### 4.1 策略分类 + 修复操作（合并表）

| # | 命中条件 | Strategy | Phase A：容器操作 | Phase B：文本操作 |
| --- | --- | --- | --- | --- |
| 0 | 父容器为按钮/标签类组件（HORIZONTAL auto-layout + 有 padding（水平或垂直均可）+ 含 TEXT 子元素 + 子元素≤3） | `BUTTON_TAG` | 父容器：w→hug | 不修改（保留 HUG + WIDTH_AND_HEIGHT） |
| 1 | `textAutoResize: "WIDTH_AND_HEIGHT"` + 父容器 `FIXED` + textW > parentAvailableW | `CONTAINER_OVERFLOW` | 父容器：w→fill, h→hug（+ padding 补偿） | w→fill, textAutoResize→HEIGHT |
| 2 | 父容器 HORIZONTAL + siblingCount=1 + text FIXED width | `SINGLE_LABEL` | 父容器：w→hug | w→fill, textAutoResize 保留原值 |
| 3 | 父容器 FIXED + 所有直接子元素在主轴方向均非纯 FIXED（HUG/FILL/layoutGrow）+ 子内容总宽度 > 父容器宽度 | `HUG_PARENT` | 父容器：w→hug | 不修改 |
| 4 | `textAutoResize: "WIDTH_AND_HEIGHT"` + 父容器 layoutMode ≠ NONE + 父容器 FIXED/FILL | `PREVENTIVE_FILL` | 父容器：w→fill, h→hug | w→fill, textAutoResize→HEIGHT |
| 5 | 含句号(。.) 且 字数>6 | `PARAGRAPH` | 父容器：w→fill, h→hug | w→fill, textAutoResize→HEIGHT |
| 6 | 无上述标点 + 字数≤10 + 父容器 NONE 或 HORIZONTAL；非CJK字符>50% 同样归入 | `TITLE` | 父容器：w→fill, h→hug | w→fill, 保留 WIDTH_AND_HEIGHT |
| 7 | 以上均不匹配 | `FALLBACK` | 父容器：w→fill, h→hug | 不修改 |

**策略说明**：
- **BUTTON_TAG**（优先级最高，0号）：按钮/标签类组件，宽度应跟随内容自适应（hug），不能改为 fill。特征：HORIZONTAL auto-layout + 有 padding + 含 TEXT 子元素 + 子元素数≤3。即使文本溢出父容器，也通过让父容器 hug 内容来适应，而非 fill 撑满上级容器。
- **CONTAINER_OVERFLOW**（优先级 1）：已确认溢出，立即修复。父容器在 auto-layout 中 → 填充式；否则 → 伸缩式。
- **SINGLE_LABEL**：单子文本的标签容器，宽度随文本伸缩。
- **HUG_PARENT**（优先级 3，高于 PREVENTIVE_FILL）：父容器 FIXED 但所有子元素宽度均非纯 FIXED（HUG / FILL / FIXED+layoutGrow），子内容总宽度超出父容器。此时子内容宽度由内容/布局决定而非设计固定值，父容器应 HUG 内容自适应。与 SINGLE_LABEL 逻辑一致，从单子扩展到多子场景。
- **PREVENTIVE_FILL**：文本当前未溢出但翻译后可能溢出，预防性转为 fill（B 原有优势保留）。
- **TITLE**：非CJK字符>50% 同样归入此策略（长英文/数字 title 折行风险高）。

> **溢出前置门槛**：是否需要修复由 4.2 双层溢出检测决定，与策略无关。只有检测到实际溢出（文本溢出父容器 **或** 父容器溢出祖父容器）的节点才进入策略匹配并执行修复。两层均未溢出的节点直接跳过（SAFE），不论命中何种策略。

### 4.2 溢出分级 — 双层溢出检测（前置门槛）

> **本章由脚本 `scripts/layout-adaptation.js` 的 `classifyOverflowGrade` + `checkParentOverflowsGrandparent` 自动完成。AI 禁止手动推理溢出判定，只需运行脚本读取结果。**

对每个 TEXT 节点执行**多层溢出检测**，只有检测到溢出才进入策略匹配（4.1）并执行修复：

| 优先级 | 级别 | 条件 | 是否修复 |
| --- | --- | --- | --- |
| 1 | `OVERFLOW` | 文本溢出父容器：`textW > parentAvailableW` | 是 |
| 2 | `CONTAINER_OVERFLOW` | 文本未溢出父容器，但父容器溢出祖父容器：`parentW > grandparentAvailableW` | 是 |
| 3 | `CONTAINER_HUG_OVERFLOW` | 文本未溢出父容器，但父容器 FIXED + 所有直接子元素主轴宽度均非纯 FIXED + 子内容总宽度 > 父容器宽度 | 是 |
| 4 | `SAFE` | 以上均不满足 | 否 |

**检测逻辑**：

```
第一层：textW > parentAvailableW → OVERFLOW（文本自身溢出）
第二层：parentW > grandparentAvailableW → CONTAINER_OVERFLOW（父容器溢出祖父）
第三层：父容器 FIXED + 所有子元素非纯 FIXED(HUG/FILL/layoutGrow) + 子内容总宽 > 父容器宽 → CONTAINER_HUG_OVERFLOW
三层都没溢出 → SAFE（跳过，不处理）
```

> **第三层检测说明**（CONTAINER_HUG_OVERFLOW）：
> - 子元素「纯 FIXED」：`sizingH === 'FIXED'` 且 `layoutGrow` 不为 1（即宽度是设计固定值）
> - 非纯 FIXED 包括：HUG、FILL、FIXED+layoutGrow:1（本质是弹性填充，宽度由父容器决定）
> - 子内容总宽度 = Σ(每个子元素当前宽度) + itemSpacing × (子元素数 - 1)
> - 示例：父容器 124px FIXED，子1 HUG 104px，子2 FIXED+layoutGrow:1 4px，但子2 内容需要 65px → 子内容总宽 = 104 + 16 + 65 = 185 > 124 → 溢出

> **关键规则**：
> - 溢出检测是**前置门槛**，先于策略匹配。只有溢出的节点才进行策略匹配（4.1）确定**如何**修复。
> - SAFE 节点不论命中何种策略（TITLE / PARAGRAPH / SINGLE_LABEL 等），均不修复。
> - `parentAvailableW` = 父容器宽度 - paddingLeft - paddingRight
> - `grandparentAvailableW` = 祖父容器宽度 - paddingLeft - paddingRight
> - 检测含 1px 容差，避免浮点精度误判。

### 4.2.1 容器级溢出扫描（补充检测）

> **本章由脚本 `scripts/layout-adaptation.js` 的 `scanFixedContainerOverflow` 自动完成。AI 禁止手动推理，只需运行脚本读取结果。**

文本级检测（4.2）从 TEXT 节点出发，沿直接父容器链检测。但当 **FIXED 容器的直接子元素都是 HUG** 时，每个 HUG 子容器各自不溢出 FIXED 容器，文本也不溢出 HUG 父容器，导致文本级检测盲区。

**盲区场景**：

```
FIXED 容器 (124px)
├─ 子1 HUG (104px)     ← 104 < 124，不溢出
└─ 子2 HUG (65px)      ← 65 < 124，不溢出
   子内容总宽 = 104 + 16 + 65 = 185 > 124 → 实际溢出！
```

**扫描逻辑**：遍历所有 FIXED + auto-layout 容器（不依赖文本节点），检测：

| # | 检查项 |
| --- | --- |
| 1 | 容器 `layoutSizingHorizontal === 'FIXED'` |
| 2 | 容器 `layoutMode` 为 HORIZONTAL 或 VERTICAL（有 auto-layout） |
| 3 | 所有直接子元素在主轴方向均非纯 FIXED（HUG / FILL / FIXED+layoutGrow:1） |
| 4 | 子内容总宽度 > 容器宽度 + 1px（含容差） |

命中后生成修复操作：**容器 width → `hug_contents`**（与 HUG_PARENT 策略一致，不修改子元素和文本）。

> **与 4.2 第三层的区别**：
> - 第三层从文本出发，检测文本的**直接父容器**是否 FIXED + 子内容溢出
> - 容器级扫描从**所有 FIXED 容器**出发，不依赖文本节点，能检测到祖父层的溢出
> - 两者互补：第三层覆盖直接父容器，容器级扫描覆盖祖先容器

### 4.3 分类阶段 Gate（全部通过方可进入修复）

| # | 检查项 |
| --- | --- |
| 1 | `strategy` + `overflowGrade` 已输出 |
| 2 | `siblingCount` + 父容器 `layoutMode` 已从 batch_read 获取 |
| 3 | 双层溢出检测已完成（每个文本节点检测文本→父容器、父容器→祖父容器） |
| 4 | 所有属性值均来自 batch_read 实际返回值，无推断值 |

### 4.4 分类输出格式

| TEXT ID | 内容（前20字） | 父容器名称 | Strategy | 父容器宽(实际值) | 文本宽 | 溢出级别 | 来源 |
|---------|--------------|-----------|----------|----------------|-------|---------|------|

---

## 五、修复执行约束

各策略的具体操作已在 4.1 合并表中定义，以下为通用执行约束和特殊场景。

### 5.1 通用约束

- **容器布局校验**：修复前通过 `batch_read` 验证实际值。水平已是目标值 → 跳过水平修复；垂直已是 HUG → 跳过高度修复。为 FIXED → 必须修复。
- **INSTANCE 内部节点**：使用分号路径引用（如 `"instanceId;childId"`）。若 `U()` 返回空 `updated: {}`（组件源锁定）→ 在外层包裹 FRAME 补偿。

### 5.2 高度规则（仅限溢出节点）

> **适用条件**：仅当文本节点溢出级别为 `OVERFLOW` 或 `CONTAINER_OVERFLOW` 时，才对其容器执行高度规则。`SAFE` 级别节点不执行任何高度修改。
>
> **禁止**：容器链检查（6.1）中发现的中间容器，若仅因宽度需改为 fill 而非溢出文本的直接父容器，**不得自动执行高度修改**。仅当该容器是溢出文本的直接父容器时，才适用本规则。

对命中条件的容器，将 `height` 设置为 `hug_contents`。若容器原为 FIXED 高度（`layoutSizingVertical: "FIXED"`），改为 `hug_contents` 时必须添加 padding 补偿：

```
paddingTop = paddingBottom = (容器原 FIXED 高度 - hug 后内容高度) / 2
```

- 单文本容器：hug 后内容高度 ≈ 文本 lineHeight
- 多子元素容器：累加子元素高度和间距
- 容器原本已有 padding（paddingTop > 0）→ 保留不变，不覆盖
- 容器原本已是 `HUG`（`layoutSizingVertical: "HUG"`）→ 无需修改

**操作模板**：
```javascript
// 容器原 FIXED 高度 40px，文本 lineHeight 22px，原无 padding
U("containerId", {height: "hug_contents", paddingTop: 9, paddingBottom: 9})
```

**SPACE_BETWEEN 保护**：
```javascript
// 容器原 FIXED 高度，primaryAxisAlignItems 为 SPACE_BETWEEN
U("containerId", {
  height: "hug_contents",
  paddingTop: 9, paddingBottom: 9,
  primaryAxisAlignItems: "SPACE_BETWEEN",  // 显式保留，防止 Ardot 副作用
  layoutGrow: 0                              // 显式保留原始值
})
```

此规则由脚本 `protectSpaceBetween` 函数自动处理，AI 在手动执行 `batch_edit` 时也必须遵守。

### 5.3 策略特殊约束

- **HUG_PARENT**：仅改父容器为 hug，文本不修改（父容器 HUG 后子内容自然展开，无需改文本属性）。注意 HUG_PARENT 的 Phase B 为空，不需要后续的迭代验证。
- **TITLE**：保留 `WIDTH_AND_HEIGHT`（标题通常短小，无需折行）。
- **PREVENTIVE_FILL**：textAutoResize 从 WIDTH_AND_HEIGHT 转 HEIGHT（仅在溢出检测通过后执行）。
- **FALLBACK**：仅改容器，文本不改（兜底策略，避免过度修复）。

### 5.4 容器布局校验

必须通过 `batch_read` 验证，避免重复修改：
- 水平已是目标值（HUG/FILL）→ 无需修复水平
- 垂直已是 HUG → 无需修复高度
- 为 FIXED → 必须修复，否则翻译后溢出

---

## 六、修复流程

> **执行顺序原则：从外向内，先容器后文本。**
>
> `fill_container` 的宽度由上级容器约束，必须从最外层逐步向内设置，否则内层会被尚未扩大的外容器压窄。
>
> **错误示例**：
> ```
> 文本(HUG) → 父容器(HUG) → 祖父容器(FILL)
> 先改文本为 fill → 文本撑满父容器当前窄宽 → 再改父为 fill → 文本已定死，换行
> ```
> **正确顺序**：
> ```
> 先祖父 → 再父 → 最后文本（从外向内）
> ```

1. **修复前截图**：按节点区域分模块 `capture_screenshot`（每批 ≤10 个 nodeId，单节点宽高 > 2000px 需再拆分），保存基线图
2. **Phase A — 容器操作**（外→内拓扑排序，每批 ≤25 个操作）：
   - 对所有待修复文本，先沿 parent 链找到最外层需修改的容器
   - 按外层→内层顺序依次设 `width → fill/hug`；高度修改仅对溢出文本的直接父容器执行（参见 5.2 高度规则）
   - 同一层级的容器可并行，但必须等上层全部完成再处理下层
3. **Phase B — 文本操作**（Phase A 全部完成后执行）：
   - 此时所有父容器已就位，再设文本 `width → fill_container` 和 `textAutoResize`
4. **容器链水平宽度复查**（6.1）
5. **容器链垂直高度复查**（6.2）

### 6.3 失败处理（Phase A / Phase B 某批失败时）

Phase A / Phase B 的 `batch_edit` 分批执行，某批失败时的处置规则：

| 失败位置 | 处置 |
|---|---|
| **Phase A 某批**（容器操作） | **整体停止**。容器宽度/高度是后续所有操作的基础，半成品状态下 Phase B 会基于错误的容器尺寸计算，继续只会放大偏差。不要跳到 Phase B，也不要跳过该批继续后续 Phase A。 |
| **Phase B 某批**（文本操作） | **跳过该批，继续下一批**。Phase B 各批之间相对独立（改的都是文本属性），某一批失败不影响其他批。记录失败的 TEXT ID 列表，最后统一报告给用户。 |
| **任何批次连续 2 次失败** | **整体停止**，把已成功的批次数、失败的批次位置、原始错误信息报告给用户，由用户决定是修复环境后从头再来，还是接受半成品。 |

**禁止行为**：

- ❌ Phase A 某批失败后硬 retry 同一批（Ardot 已回滚该批，但 retry 多半还是同样的错）
- ❌ Phase A 失败仍继续 Phase B（把错误层叠下去）
- ❌ 用 `D()` 删掉已修改的容器（容器尺寸改动没法用删除回滚，且会误删原始节点）

**半成品状态清理**：

Phase A 失败的批次本身已被 Ardot 回滚，但**之前成功的批次已经生效**。这种半成品状态下：

1. 先 `batch_read` 读取所有已修改容器，记录当前实际尺寸
2. 在最终报告里**明确告知用户**：「Phase A 已完成 X/N 批，第 Y 批失败；已生效的修改是 …；失败的节点 ID 是 …」
3. 由用户选择：（a）修复环境后重新跑脚本生成新一批操作，（b）接受当前半成品状态，（c）手动在 Ardot 里撤销

**验证步骤补救**：第六章 6.1 / 6.2 容器链检查只跑在 Phase A 全部成功的前提下；如果 Phase A 半成品，**不要跑 6.1 / 6.2**，直接跳到第七章分模块截图，把当前实际状态呈现出来给用户看。

### 6.1 容器链水平宽度检查（强制执行，不可跳过）

> **本章由脚本 `scripts/layout-adaptation.js` 的 `checkContainerChainHorizontal` 自动完成，结果包含在 `--output` 输出的 `chainCheck` 字段中。AI 禁止手动遍历 parent 链。**

文本 `width: fill_container` 后，若 parent 链上存在 `layoutSizingHorizontal: "FIXED"` 的中间容器，文本 fill 空间会被该容器限制，导致不必要的折行。

> **这是最容易遗漏的问题来源**。INSTANCE 组件内部常有多层嵌套，中间容器可能是 FIXED 宽度（如侧导航组件内的 Frame 80px），即使文本和直接父容器都已设为 fill，中间层的 FIXED 宽度仍会成为瓶颈。

**强制操作步骤**：

1. **遍历每个已修复的文本节点**，从文本的祖父容器开始，沿 parent 链逐层向上检查，直到遇到 `layoutSizingHorizontal: "FILL"` 或到达设计稿根节点
2. **对路径上每个容器**，检查 `layoutSizingHorizontal` 的实际值：
   - 若为 `"FIXED"` 且该容器的父级有 auto-layout（`layoutMode` 为 `HORIZONTAL` 或 `VERTICAL`）→ **必须改为 `width: "fill_container"`**
   - 若为 `"FIXED"` 但该容器的父级无 auto-layout（`layoutMode: "NONE"`）→ 跳过（绝对定位场景）
   - 若为 `"HUG"` 且该容器的父级有 auto-layout → **也必须改为 `width: "fill_container"`**（HUG 容器会被文本撑大，可能超出父级空间）
   - 若为 `"FILL"` → 停止向上遍历，该路径检查完成
3. **高度修改条件**：容器链检查中发现的中间容器，**仅修改宽度**（FIXED/HUG → fill_container）。**不自动执行高度修改**，除非该容器是溢出文本的直接父容器或在 CASCADED 路径上（参见 5.2 高度规则）
4. **INSTANCE 实例节点**：INSTANCE 本身也可能是 FIXED 高度/宽度，必须同等检查和修复，不得跳过

**输出格式**（每条路径的检查结果）：

| 文本 ID | 路径上的容器 ID | 容器类型 | 原宽度模式 | 修复动作 |
|---------|---------------|---------|-----------|---------|

> **示例**（通用结构）：
> ```
> 文本 "Translated Text" (instanceId;textId)
>   → 直接父容器 Frame (instanceId;frameId) — FIXED 80px → fill_container
>   → INSTANCE 组件实例 (instanceId) — FILL, FIXED h40 → 宽度已是 FILL 跳过；高度不自动修改（非直接父容器，参见 5.2）
>   → 外层列表容器 (listId) — FILL → 停止
> ```
> 常见于：侧导航菜单、表格行组件、卡片内嵌组件等 INSTANCE 内部有多层 Frame 包裹的结构。
>
> ```javascript
> U("instanceId;frameId", {width: "fill_container"})
> // instanceId 宽度已是 FILL，无需修改；高度不自动修改（非直接父容器，参见 5.2 高度规则）
> ```

**跳过条件**（以下情况跳过，不改 fill_container）：

- 容器已是 `FILL` 模式
- **父级为 `SPACE_BETWEEN` / `SPACE_EVENLY` 分布模式 + 本容器 `layoutGrow: 0`**：此类容器靠父级分布算法定位到两端（如顶栏左 logo 区 + 右账号区），改 fill 会撑满父级导致内容错位。保持 `HUG` 不动，停止向上遍历。

> **典型场景**：顶栏 `primaryAxisAlignItems: "SPACE_BETWEEN"`，左侧 logo 容器和右侧账号容器都是 HUG + layoutGrow:0。这两者必须保持 HUG，靠 SPACE_BETWEEN 自然分布到两端。

### 6.2 容器链垂直高度检查

> **适用条件**：仅对 5.2 高度规则适用的容器执行。容器链检查中仅修改宽度的中间容器，不执行高度检查。

**padding 补偿计算**：
```
paddingTop = paddingBottom = (容器原 FIXED 高度 - hug 后内容高度) / 2
```

---

## 七、验证流程

1. **修复后分模块截图**：禁止单张全页截图（大尺寸超时 + 细节丢失）。按受影响节点区域分模块 `capture_screenshot`，每批 ≤10 个 nodeId
2. **逐区域对比**：对比基线图，检查截断、溢出、塌陷
3. **问题修正**（最多 2 轮）：定位问题节点 → 重新修复 → 再截图验证
4. **输出适配报告**：修复节点详情 + padding 补偿值 + 跳过节点及原因 + 验证结果

---

## 共享底座（伞技能层）

- `../../shared/mcp-cheatsheet.md` — Ardot MCP 工具速查
- `../../shared/dependencies.md` — 环境依赖与命名空间回退
- `../../shared/troubleshooting.md` — 跨模块排障对照表

---

## 版本历史

按时间倒序。

### absorbed (2026-09-28)

- 从独立技能 `layout-adaptation` 吸收为伞技能 `ardot` 的 `modules/layout-adapt`
- 保留全部规约内容与脚本不变，仅更新文档头部的技能归属
