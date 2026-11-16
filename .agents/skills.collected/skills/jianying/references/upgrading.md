# 版本升级与迁移

技能当前只有 **一个支持窗口**：剪映专业版 11.8.0，build 14778。`references/version.json` 的
`supported.min` / `supported.max` 都是 `11.8.0`，`build_tested` 是 `14778`。这个窗口内没有
历史版本差异需要迁移，也没有“从旧版升上来”的兼容层——装的是 11.8，就按文档做；不是 11.8，
`jy.py probe` 会报 `unsupported`，先别承诺结果。

## 窗口外的处理

`version_policy`（`scripts/jylib/env.py`）只做四态判定，不给跨版本兼容：

| install 情况 | `docs.status` | 含义 |
|---|---|---|
| 不在 11.8.0 窗口内 | `unsupported` | 文档结论不适用，按未验证处理 |
| 窗口内但与 behavior/build 基线不一致 | `unverified` | 可以试，结论要自己复验 |
| 与基线的版本和 build 都对上 | `verified` | 文档结论直接可用 |
| 探测不到安装版本 | `unknown` | 不阻断建草稿，但结论一律未验证 |

## 未来升级的顺序

1. **先冻结旧版差异**。把“从当前到达版本升到新版本”的行为变化写成
   `references/history/<旧到达版本>.md`，标题形如 `# 11.8 → 11.9 变更（冻结归档）`，
   文件名用旧到达版本（`11.8.md`）。数量上限由 `version.json` 的 `history_max` 控制
   （当前 3），超出时删最旧的一份。
2. **在真实剪映上复验**。按 [维护与更新](maintenance.md) 的必跑自检走，其中 `build → render →
   verify` 要在临时草稿上真跑；没跑过的结论标 `unverified`，不写进 `supported`。
3. **更新基线**。改 `references/version.json` 的 `app_baseline` / `behavior_tested` /
   `build_tested` / `supported.min` / `supported.max`，同步 [能力边界](limits.md) 里受影响的
   条目，再改 `SKILL.md` frontmatter 的 `version`，并同步 `references/version.json` 的 `skill_version`。
4. **记一笔变更**。在 [变更记录](changelog.md) 顶部加一个新版本段落，写清行为变化，
   不要只写“升级到 X”。

`supported.min` 始终等于 `app_baseline`，`supported.max` 始终等于 `behavior_tested`——
`python scripts/check_docs.py` 会断言这条，对不上直接报 `kind: "version"`。

## 相关文档

- [维护与更新](maintenance.md)：自检命令、打包分发、版本一致性
- [变更记录](changelog.md)：技能自身的版本历史
- [历史归档](history/README.md)：冻结的旧版本差异
