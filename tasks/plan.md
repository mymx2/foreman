# Plan

一次性计划文件，不被 git 追踪。存放位置：

```
tasks/__<sub>/YYYYMMDD/NN-plan-<kebab-slug>.md
```

- `YYYYMMDD` — 创建当日日期
- `NN` — 当天序号（01、02…），plan 与对应 todo 共享同一序号
- `<kebab-slug>` — 小写英文短横线格式，概括需求的简短标识

示例：`tasks/__example-app/20260115/01-plan-add-dark-mode.md`

## 进度元信息

文件头部必须携带 frontmatter，供不读正文即可判断进度：

```markdown
---
status: draft | approved | done | abandoned
---
```

流转：`draft`（待批准）→ `approved`（已批准）→ `done` / `abandoned`。创建时设置，状态变化时更新。
