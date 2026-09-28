# Troubleshooting · 跨模块排障对照表

按症状查，按建议处置。每条目给出**症状 → 可能原因 → 修复步骤**。
模块自己的问题优先看模块自己的 references；本表收录**跨模块都可能遇到**的环境 / MCP / 调用层问题。

---

## MCP 连接

### `NO_ADAPTER: No adapter found for routeKey ...`

- **可能原因**：当前 MCP 命名空间路由失效；工具暴露在另一个命名空间下
- **修复步骤**：
  1. 不要在原命名空间继续重试
  2. 用 `mcp_list({ keyword: "ardot" })` 列出所有可用 ardot 命名空间
  3. 切换到另一个（`ardot` ↔ `ardot-design`），用 `fetch_file_info` 探活
  4. 探活成功后，**后续全程固定用那一个**
  5. 两个命名空间都不通 → 进入「MCP 完全断开」

### MCP 完全断开

- **可能原因**：Ardot 客户端未启动 / MCP server 未运行 / 端口被占用
- **修复步骤**：
  1. 让用户确认 Ardot 客户端已启动并打开目标文件
  2. `curl http://127.0.0.1:50501/api/v1/health` 探活主端口
  3. 不通则 `curl http://127.0.0.1:19501/api/v1/health` 探活沙箱端口
  4. 两个都不通 → 让用户重启 Ardot 客户端
  5. 端口被占用 → `netstat -ano | findstr "50501 19501"`（Windows）找出占用进程

### `fetch_editor_state` 返回空或报错

- **可能原因**：Ardot 文件未打开 / MCP 连接中断
- **修复步骤**：让用户确认 Ardot 已打开目标文件，MCP 已连接后重试

---

## 输入解析

### selection 为空

- **可能原因**：用户没选中画板，也没提供 nodeId
- **修复步骤**：反问一次「请选中要处理的画板，或告诉我 nodeId」；不要瞎猜

### selection 包含非目标类型

- **grid**：只保留 Frame，报告「忽略了 N 个非 Frame 节点」
- **showcase**：只保留画板 / page；其他类型提示用户重新选
- **layout-adapt**：所有类型都可作为入口，但内部只处理 TEXT 节点

### `batch_read` 返回「节点不存在」

- **可能原因**：用了 `batch_edit` 的 binding 名（如 `outer`）而不是真实 nodeId
- **修复步骤**：等 `batch_edit` 返回真实 ID 后再 `batch_read`

### 节点数过多返回不全

- **可能原因**：单次 `batch_read` 超过 500 子节点会压缩
- **修复步骤**：分批读取，参考 `modules/layout-adapt/SKILL.md` §大设计稿分批读取

---

## 写入

### `batch_edit` 部分操作失败

- **可能原因**：单次超过 25 个操作 / binding 顺序错误 / 节点依赖未满足
- **修复步骤**：
  1. 拆成 2 次以上 `batch_edit`
  2. 先外层容器，再内部节点
  3. 失败的批用 `D(binding)` 清理半成品，**不要硬 retry**

### `Insert failed: ref: ID is not a component/component set`

- **可能原因**：`type: "ref"` 只能引用 component / component set；普通 FRAME 用了 ref
- **修复步骤**：改用 `C(sourceNodeId, parent, props)` 复制快照。详见 `shared/mcp-cheatsheet.md` §type:ref vs C

### `VARIABLE_ALIAS validation error`

- **可能原因**：给 `type: "ref"` 插入时传了不支持的属性
- **修复步骤**：先无 props 插入，再用 `U` 更新实例属性

### `Invalid padding value`

- **可能原因**：`padding` 用了 CSS 简写字符串 `"0 200 200 200"`
- **修复步骤**：改数组 `[T, R, B, L]` 或四个独立属性 `paddingTop/Right/Bottom/Left`

### 写入成功但 Ardot 看不到内容

- **可能原因**：客户端视图缓存
- **修复步骤**：让用户按 `Cmd+R`（macOS）/ `Ctrl+R`（Windows）或点击画布空白处刷新

### 坐标与空位返回不一致

- **可能原因**：`batch_edit` 中手写或偏移了 x/y
- **修复步骤**：原样使用 `locate_available_space` 返回的 x/y，不做任何偏移

### `locate_available_space` 失败

- **可能原因**：页面空间不足 / 输入尺寸过大
- **修复步骤**：提示用户换页 / 清理空间 / 改 MATRIX / 改向下找位，**不要降级为手写坐标**

---

## 渲染与视觉

### outer width 塌成 402（或类似小值）而不是公式值

- **可能原因**：某个 inner FRAME 的 `counterAxisSizingMode` 是 `FIXED`
- **修复步骤**：改成 hug / `width: "hug_contents"`

### titlebar 宽度塌成文字宽度

- **可能原因**：titlebar 用了 hug 或 STRETCH
- **修复步骤**：改为 `FIXED`，width = computedOuterWidth（参考 `modules/showcase/references/skeleton-spec.md`）

### 标题和内容左边缘不齐

- **可能原因**：titlebar 未设 `counterAxisAlignItems: MIN` 或 title row 误用 `SPACE_BETWEEN`
- **修复步骤**：按 `modules/showcase/references/skeleton-spec.md` §对齐硬契约 修复

### 分割线只显示上半段、没拉通到底

- **可能原因**：divider 用了 `LINE + 写死 length`，length 小于实际行高
- **修复步骤**：改用 `RECTANGLE + height:"fill_container"`；生成后 `batch_read` 确认高度 ≥ 相邻 cell 最大高度 95%

### 网格线看不到

- **可能原因 1**：用了 rectangle 模拟细线，0.1px 被 Ardot 子像素消除
- **修复**：改用 `type: "line"` + `strokeWeight: 0.1`（详见 `modules/grid/SKILL.md`）
- **可能原因 2**：给 line 节点写了 `fills`
- **修复**：line 的颜色用 `strokes`，`fills` 在 line 上无效

### 字体缺失

- **可能原因**：目标文件没有指定 `fontName`
- **修复步骤**：调 `get_available_fonts` 后选择可用字体；**不要猜 style 名称**

---

## 截图

### `capture_screenshot` 超时 / 返回失败

- **可能原因**：单次截图节点过大（> 2000px）
- **修复步骤**：按 group 分段截图；不要在一次调用里截超大图

### 截图与画布实际不一致

- **可能原因**：客户端视图缓存
- **修复步骤**：让用户刷新 Ardot 视图后重试

---

## 脚本（layout-adapt 专用）

### `node modules/layout-adapt/scripts/layout-adaptation.js` 报错 `Cannot use import statement outside a module`

> 在技能根目录 `ardot/` 下运行；如果已经 `cd` 到 `modules/layout-adapt/`，对应路径是 `node scripts/layout-adaptation.js`。

- **可能原因**：运行环境的 `package.json` 含 `"type": "module"`，CommonJS 脚本被当 ESM 解析
- **修复步骤**：
  - 把脚本改名为 `layout-adaptation.cjs`（Node 按扩展名识别 CJS）
  - 或在脚本目录创建不含 `"type": "module"` 的独立 `package.json`

### `--fetch` 两步探活都不通

- **可能原因**：Ardot MCP server 和沙箱都没运行
- **修复步骤**：
  1. `curl http://127.0.0.1:50501/api/v1/health`
  2. `curl http://127.0.0.1:19501/api/v1/health`
  3. 两个都不通 → 让用户重启 Ardot 客户端

### `U()` 返回空 `updated: {}`

- **可能原因**：INSTANCE 节点组件源锁定
- **修复步骤**：在外层包裹 FRAME 做补偿（详见 `modules/layout-adapt/SKILL.md` §三、全局规则）

---

## 仍未解决？

- 查 `shared/dependencies.md` §阻塞条件，看是否命中必须停止的场景
- 模块专属问题查模块自己的 `references/`：
  - `modules/showcase/references/quality-harness.md`
  - `modules/showcase/references/faq.md`
  - `modules/grid/references/advanced-grids.md`
- 把**完整错误信息 + 最近 3 次工具调用**贴给用户，不要硬编一个看似合理的解释
