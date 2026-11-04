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

## 3. 属性不等于渲染

读到目标值只证明写入意图；截图/像素是终判。两者冲突以渲染为准，并写明冲突。`absoluteBoundingBox` 的语义以探针结果为准；本仓实测为渲染盒（自动宽 TEXT 1279 vs 父 260），可作初筛辅助，截图仍是终判。
