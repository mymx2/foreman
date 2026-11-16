# 历史版本归档

这里只存放**已冻结的旧版本差异**：每次升级前把“旧到达版本”的文档差异写成
`<旧到达版本>.md`（例如 `11.8.md`），之后不再维护。

当前为空：技能只有一个支持窗口（剪映 11.8.0 / build 14778），没有历史迁移需要保留。
升级流程见 [版本升级与迁移](../upgrading.md)；数量上限由 `../version.json` 的
`history_max` 决定（当前 3），超出时删最旧的一份。

`python scripts/check_docs.py` 会数本目录下除 `README.md` 以外的 `.md` 文件，
超过 `history_max` 报 `kind: "version"`。
