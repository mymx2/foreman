# Draft

一次性审计清单，不被 git 追踪。存放位置：

```
tasks/__<sub>/YYYYMMDD/NN-audit-<kebab-slug>.md
```

- `YYYYMMDD` — 创建当日日期
- `NN` — 当天序号（01、02…），plan 与对应 audit 共享同一序号
- `<kebab-slug>` — 小写英文短横线格式，概括需求的简短标识

示例：`tasks/__example-app/20260115/01-audit-add-dark-mode.md`

## 进度元信息

文件头部必须携带 frontmatter，供不读正文即可判断进度：

```markdown
---
status: in-progress | done
---
```

流转：`in-progress` → `done`。创建时设置，状态变化时更新。
