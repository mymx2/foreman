# Examples / 使用示例

## 示例 A：场景明确，可跳过分组确认

用户：

```text
我刚画完登录流程的 5 屏：默认态 / 输入态 / 校验失败 / 加载中 / 成功。
帮我在 Ardot 上排成一个 review board，链接发给产品。
```

执行：

1. `fetch_editor_state` 返回当前页面，确定目标页面。
2. Step 1.5：用户已显式给出分组语义，5 个状态属于同一场景「登录流程状态对照」，单 group，可跳过确认。
3. Step 2：5 个带完整页面框架的整页稿，多状态对照 → 先评估 ROW；若 outerWidth 超过阈值或原始已竖排，则改 COLUMN/MATRIX 并确认。
4. `locate_available_space` 找空位，`padding >= 400`。
5. `batch_edit(operations)` 生成：
   - outer：`产品团队_登录流程·新版登录流·衍生展示区`
   - titlebar：`Product Mobile` / `登录流程` / `2026.5.20`
   - subtitle：`mobile · 登录链路设计稿`
   - group：`状态对照`
   - 5 个 cell columns，同一链路多状态不加 column dividers。
   - outer frame 默认 100px 圆角。
6. `batch_read` 校验尺寸和对齐。
7. `capture_screenshot` 截图预览，返回 Ardot 链接。

## 示例 B：场景模糊，必须先确认分组

用户：

```text
https://ardot.tencent.com/file/xxx?node_id=70%3A30 帮我把这个画布里的内容排版一下
```

执行：

1. `fetch_editor_state` + `batch_read` 读取入口节点，发现 6 个整页 frame，3 列 × 2 行摆放，命名有重复。
2. Step 1.5：分组方式存在多种合理解释，且存在内容重复 frame，不能直接拍板。
3. 调用选择题工具提交方案：
   - A. 按页面类型分组。
   - B. 按版本分组。
   - C. 不分组，保持原平铺。
   - D. 自定义。
4. 用户选择后再进入 Step 2。
5. 后续生成、校验、截图、返回链接。

## 示例 C：多端组件对照（MATRIX 场景）

用户：

```text
我有 4 个按钮变体：primary / secondary / ghost / destructive，分别有 mobile 和 desktop 两个尺寸，帮我排成一个对照展示区。
```

执行：

1. `fetch_editor_state` 定位当前页面。
2. Step 1.5：用户已显式给出两个维度（按钮类型 × 设备尺寸），可直接用 MATRIX。
3. Step 2：裸组件多类型目录 → 每个 group 内 ROW；两端对照 → MATRIX。
4. 生成：
   - outer：`设计团队_按钮组件·变体对照·衍生展示区`
   - group 1：`mobile`，4 cells。
   - group 2：`desktop`，4 cells。
5. `batch_read` 校验，`capture_screenshot` 预览，返回链接。

## 示例 D：写入前需要确认

以下场景必须在 `batch_edit` 前向用户确认一次：

- 页面已有同名旧展示区，需要选择替换 / 另起 / 取消。
- 单次写入节点很多，可能明显改变页面结构。
- 用户明确要求「覆盖原来的展示区」。

普通新增展示区不需要额外确认，避免降低效率。
