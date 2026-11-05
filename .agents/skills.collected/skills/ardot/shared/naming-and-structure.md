# 命名与结构

适用范围：ui-design / design-to-code。
showcase 的展示区名称、titlebar、subtitle、mini-title 以 `modules/showcase/references/naming-conventions.md` 为准。
grid / layout-adapt 的节点命名与结构沿用各自模块规则（如 grid 的 `h-line@y…` / `v-line@x…`），本文不覆盖。

优先级：模块专名模板 > 本文 > 通用兜底。本文只定义「叫什么、怎么分层」；布局、组件、token 的机制引用现有文档，不复制。

执行方式：

- `[可查]`：现有工具或命令能核对，按给出的方式留回执。
- `[人工]`：需要人工或抽样，按检查清单签核。
- `[待工具]`：尚未实现，不作为当前门禁。

状态词表 v1（2026-11-05）：

```text
default / hover / focus / pressed / selected / disabled / loading / empty / error / success
```

`active` 弃用：瞬时态映射 `pressed`，持久态映射 `selected`。
本文与 Photocraft 各自维护完整词表，不共用文件、不做摘要互校。

---

## 1. 分组层级 `[可查]`

机械项用 `shared/scripts/verify-structure.js` 检查；语义分组仍需人工确认。

Page → 画板 → 区块 → 容器 → 元素。

- 一个 Frame 一个职责；Frame 是布局容器，不是装饰分组。
- 画板直接子级只能是 Frame；背景层放最底，命名 `<Role> BG`。
- 文本与图标放进容器，不直挂画板根或区块根。页面级标题、区块说明可以例外，按 `type` 判断，不按名字判断。
- 单子 Frame 只允许图标包装、头像、纯文本卡；逐个登记 allowlist，字段见 §7。画板根不算单子 Frame，不再往下额外包一层。
- 深度 ≤5；单容器直接子级 ≤30 为软规则，超出时说明原因。
- 不建只包裹一个装饰元素的空 Frame。

检查清单：

1. `batch_read` 回读整棵树，`readDepth` 覆盖目标深度，断言 `omitted` 为空。
2. 画板子级的非 Frame 节点逐项确认是否有意为之。
3. 单子 Frame 全部能在 allowlist 找到。
4. 背景层在所在容器的最底部。

```bash
node shared/scripts/verify-structure.js --input batch-read.json --allowlist allowlist.json
```

校验器覆盖：空树 / `omitted` 非空、默认名与占位名、深度、单子 Frame（warning，可在 allowlist 抑制）、子级压缩。退出码 0/1/2。

布局机制见 `shared/design-rules.md` §自动布局，本文不复述 flex / hug / fill。

---

## 2. 节点命名 `[可查]`

默认名、占位名、纯数字和 copy 后缀由 `verify-structure.js` 检查；语义命名仍需人工。

默认用英文角色名，Title Case 单词，3–48 字符。

正例：`Product Card`、`Hero Cover`、`Nav Header`、`3D Preview`、`iOS Banner`。

禁止：

- 默认名：`Frame N`、`Layer N`、`Group N`、`Page N`；
- 占位名：`未命名`、`Untitled`、纯数字；
- 直接用 nodeId 当名字；
- `copy` / `副本` / `拷贝` 后缀；
- 换词占位，如 `Frame One`、`Group A`。

showcase 展示区不使用本节默认名；它的 outer/titlebar/subtitle/mini-title 按模块自己的规范执行。

检查清单：逐节点看 `name`；搜索默认名和占位名；新增节点由执行人签核。

---

## 3. 组件与状态 `[人工]`

- 属性名沿用现有 `Type` / `Color` / `Size` / `State` / `Tone` / `Has Icon` / `Label` / `Icon` / `Variant`；不强制改写存量组件。
- 新组件的变体值用小写 kebab，且必须包含 `default`。
- 状态值使用状态词表 v1；有状态组件必须有 `State` 属性；无状态组件在组件说明里显式写 `stateless`。
- `shared/component-instance.md` 里的 `Circle` / `Rectangle` / `small` / `big` / `red` / `blue` / `Medium` 都是示例数据，不是本文规则。

检查清单：新增组件逐个核对属性名、变体值、`State` 是否存在；存量组件只登记，不改名。

---

## 4. Token 命名 `[可查]`

- 不设封闭白名单。现有 `Semantic` / `Brand` / `Design Tokens` 是示例，不是强制集名。
- 新变量集建议用 `Primitives` / `Semantic` / `Component`；变量名用小写 kebab 分层，如 `text-primary`、`bg-surface-raised`；模式用 `Light` / `Dark`。
- 存量集与变量不改名；新增集在交接说明里登记。
- 执行方式：`[可查]`。用 `fetch_variables` 取创建前后快照，再跑基线差分：

```bash
node shared/scripts/verify-token-diff.js --input token-diff.json
```

输入：`{"before": <fetch_variables 结果>, "after": <fetch_variables 结果>}`。新增变量名必须是 kebab；新集名不在 `Primitives/Semantic/Component` 只报 warning；存量集被删除或类型变化报 warning。

变量绑定与模式切换的写法见 `shared/token-binding.md`，本文只给命名约定。

---

## 5. 页面与画板 `[可查]`

- 页面名必填；禁止 `Page N`。`create_new_page` 必须显式传 `name`。
- 多断点命名：`<Scene> - mobile` / `<Scene> - tablet` / `<Scene> - desktop`。
- 断点宽度默认：mobile 375、tablet 768、desktop 1440；项目可覆盖，覆盖值写进交接说明。

检查方式：`fetch_editor_state` 的 `pageList` 看页面名；`batch_read` 看画板 `width`。两项都能直接回读。

---

## 6. 导出 `[可查]`

- 不预先改名。使用 `export_nodes` 返回的 `nodeId → path` 映射，保存到 `export-mapping.json` 供复用。
- 导出批次按工具实际限制；未验证前不并发导出。

```bash
node shared/scripts/verify-export-mapping.js --input export-mapping.json --out-dir <目录>
```

输入结构：

```json
{
  "requestedNodeIds": ["1:2", "1:3"],
  "mapping": { "1:2": "a.png", "1:3": "nested/b.png" },
  "outputDir": "<目录>"
}
```

校验：nodeId 集合相等、文件存在且非空、路径在 outputDir 内、归一化路径不重复；`--before hashes.json` 可额外校验导出前已存在的文件未被改写，`--require-before` 要求每个映射文件都有基线条目。退出码 0/1/2。

工具参数与返回格式见 `shared/mcp-cheatsheet.md` §8.5；端到端示例见 `modules/design-to-code/references/design-to-code-workflow.md` 的导出章节。

---

## 7. Allowlist 格式 `[可查]`

```json
{
  "version": 1,
  "entries": [
    {
      "scope": "ui-design",
      "codes": ["SINGLE_CHILD_FRAME"],
      "key": "<父路径>/<节点名>",
      "owner": "<负责人>",
      "reason": "<为什么允许>",
      "added_at": "2026-11-05",
      "expires": "2026-12-31"
    }
  ]
}
```

- 键用「父路径 + 名称」，不用 nodeId；nodeId 在存盘或重开后可能变化。
- `scope` / `codes` / `owner` / `reason` / `added_at` / `expires` 全部必填；`expires` 必须是真实 ISO 日期，过期即失败。
- `scope: "all"` 对所有模块生效；调用校验器时没传 `--scope`，只认 `all` 条目。
- 文件放项目侧，不放进技能包；技能只定义格式。
- `shared/scripts/verify-structure.js` 读取该文件；过期、字段缺失、日期倒挂都会报 `ALLOWLIST_*` 错误。

---

## 8. 校验器自测

```bash
node --test shared/scripts/test/*.test.js
```

三份校验器共用这一条命令；`package.json` 的 `test` 脚本等价。
