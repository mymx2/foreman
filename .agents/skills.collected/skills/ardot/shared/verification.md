# 验证纪律

适用产出视觉交付物的模块：showcase / layout-adapt / ui-design；grid / design-to-code 用各自的自验证。单模块分发时必须随包携带本文件。路径基准与 `shared/` 其他文档一致：按技能根解析；单模块分发保持 `<skill>/shared/` + `<skill>/modules/<name>/` 结构。

- showcase / layout-adapt（有脚本或批量门禁）：第 1、2、3 条全部适用。
- ui-design（设计规范类）：适用「0. 设计时配方」与「命中非空」「属性不等于渲染」；不要求红证。

## 0. 设计时配方（ui-design）

按 `modules/ui-design/references/guidelines-table.md` 与 `modules/ui-design/references/guidelines-mobile-additions.md` 的配方留 `batch_read` 实测值；landing-page / web-app 本轮无补充配方。

## 1. 红证

新增或修改门禁时，先在已知坏样本或修复前基线上跑一次，确认它会失败并留下失败输出。跑不红的检查只是日志。可用临时探针（x+2 的标题行、LINE 版 divider、FIXED cell row、固定宽容器 + 超长文本），跑完删除。

## 2. 命中非空

检查前确认对象存在——`batch_read` 返回目标 nodeId、被检字段不是 `null` / `undefined` / 空值、截图覆盖目标区域并绑定 node bounds 与同尺寸。命中 0 按「未执行」处理，不得判通过。

例外：验证目标是**解绑**时，字段为 `null` 或缺失才算通过。先确认本次操作意图是解绑，再套用该分支。

## 3. 属性不等于渲染

读到目标值只证明写入意图；截图/像素是终判。两者冲突以渲染为准，并写明冲突。`absoluteBoundingBox` 的语义以探针结果为准；本仓实测为渲染盒（自动宽 TEXT 1279 vs 父 260），可作初筛辅助，截图仍是终判。

## 4. 分级验证

适用 ui-design 及按此接入的画布交付模块。showcase / layout-adapt 继续用各自的门禁，不混用本节层级。

不是每一批修改都跑完整验证。按本批改了什么，选最轻的检查。

| 层级 | 本批改了什么 | 检查 |
|---|---|---|
| T1 结构 | 新建 frame、布局模式、padding、层级 | `batch_read` 回读：`layoutMode`、`layoutWrap`、`layoutSizingHorizontal/Vertical`、`width`、`height`、`itemSpacing`、四边 `padding`、`children` 的 ID 顺序；确认非空且符合预期 |
| T2 内容 | 文本内容、实例属性 | 跳过，积累到下一次样式或阶段批一起验。token / 样式绑定除外，按 `shared/token-binding.md` §验证回读 |
| T3 视觉 | fill、字体、效果、圆角、描边 | 截图（`capture_screenshot`） |
| T4 区块完成 | 一个逻辑区块（hero / features / footer） | `batch_read` + 截图各一次 |
| T5 整页完成 | 所有区块合并 | 整页截图一次 |

- `capture_layout` 在当前 Ardot MCP 中可用，但 `parentId` 必须是容器节点，传 Page 会报 `Root node must be a container, not a page`；对每个顶层 frame 分别调用。其它宿主没有该工具时按可选处理；返回空按「未执行」处理，不得判通过。
- 连续两批都是 T2 / T3 时，合并到本阶段末尾验一次，不要逐批截图。
- **任务最后一次 `batch_edit` 之后必须做一次内容回读**：`characters` / `content` 非空且不是占位文案。末批是内容批时不能因为「没有下一次」而跳过。
- **交付时至少有一次覆盖交付边界的截图**，与最后一批属于哪个层级无关。
- 截图目标超过 2000px 高时按区块分段截。
- 每轮验证要真正读取返回的图片；只拿到路径不算验证。

### 收敛阈值

- 每个区块最多 2 轮修复；准备开始第 3 轮时停下，记录遗留问题。
- 忽略 ≤ 4px 的间距偏差、< 1px 的亚像素错位、装饰或背景节点的非关键溢出。
- 区块已经符合规范且无结构问题时，不再为了「再确认」加截图或做主观润色。
- 缺失请求内容、重复的主操作或导航、数据不可读、空模块、组件语义错误属于阻塞项，不得当作成功交付。

### 修复协议

1. 一次验证里的问题全部收集。
2. 用一个 `batch_edit` 一起修。
3. 只重跑同一层级的验证，不因为修过就升级为全量检查。
4. 第 2 轮仍失败 → 停止，记录问题，继续后续工作。
