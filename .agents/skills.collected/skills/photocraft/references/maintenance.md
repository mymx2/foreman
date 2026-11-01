# 维护与升级

> 上游维护者专用。下游运营 AI 不要运行本文件，更新整个技能见 `references/update.md` / `scripts/update.py`。
> 只在用户明确要求升级/核对文档、`find_cli.py --check` 返回退出码 3 或 4（`docs_in_range: false` / `docs_config_error`）、或文档与实跑连续两次不符时加载。普通任务不需要读本文件。

## 触发条件

- `python scripts/find_cli.py --check` 退出码 3 或 4，或 JSON 里 `docs_in_range: false` / `docs_config_error` 有值。
- 用户要升级 PhotoCraft，或要求核对文档与当前版本。
- 同一断言两次实跑与文档不符：直接改正文并标 `unverified`，同时在 `upgrading.md` 的变化表补一行；以运行结果为准。

## 升级流程

1. 记录当前状态：`python scripts/find_cli.py --check --json`；安装版本、`version.json` 的 `params_baseline` / `behavior_tested` / `supported`。
2. 取上游源码（可选）：从技能来源记录取上游地址，先 `git ls-remote --tags` 确认 tag 写法（`v0.18.0` 或 `0.18.0`），再 `git clone --depth 1 --branch <tag> <repo> <ignored-temp-dir>`；用完删除临时目录。离线时只读 release notes。
3. 对比变化：上游 `docs/CHANGELOG` → 注册表 id/参数 → serve `methods` 与 MCP `tools/list` → 现有探针覆盖的行为。只收会改变自动化写法或验收的条目。
4. 跑快闸：`check_docs.py`、`probe_gotchas.py`、`test_docs.py`、`test_update.py`。通过判据：全部退出 0，`check_docs` 的 `history` 计数不超过 `history_max`，且 version.json 与 upgrading 头一致。
5. 跑慢闸：跨 minor、升级说明里有行为变化、或快闸失败时跑 `run_examples.py`、`test_workflow.py`、`test_control.py`；全部通过后再继续。
6. 归档与改写：
   - 先把现有 `upgrading.md` 重命名为 `history/<它的到达版本>.md`（当前 0.14→0.18 归档为 `history/0.18.md`）；目标已存在时停止，不要覆盖；
   - 归档即提升基线：`params_baseline = supported.min = 归档目标 Y`；新的 `upgrading.md` 从 Y 写到新核对版本（先写 `.tmp` 再替换，覆盖重写，不追加）；
   - 当前行为写进对应 reference，旧版本标注改成陈述句或 `unverified`；按住 `version.json` 的 `supported.min` 改写正文的可用性标记；
   - 同步各 reference 头部的核对版本（不写构建 hash），更新 `version.json` 的 `params_baseline` / `behavior_tested` / `supported`；同步 `SKILL.md` frontmatter 与 `references/update.json` 的 `version` / `updated` / `check_interval_days` / `severity` / `cli_supported`（`cli_supported` 与 `version.json` 的 `supported` 一致），下游 updater 按 `update.json` 比较新版。安全或破坏性修复把 `severity` 标成 `security` / `breaking`，下游会在任务前更新。
7. 维护 `history/`：数量上限由 `version.json` 的 `history_max` 决定（当前 5）；新增超过上限时删除版本最旧的一份。`supported.min` 保持当前基线（最新归档的到达版本），不因删除旧档再上调。历史是技能的一部分，随技能分发，不要加入 `.gitignore`。
8. 重跑快闸；`find_cli.py --check` 退出 0 且无 `docs_hint` 才算收尾。

## 写入规则

- 当前文档只写当前行为；一个事实只出现一处。
- PhotoCraft 发布频率高于技能维护频率；`supported` 范围落后是正常的，不为每个 CLI 版本发技能。下游遇到范围外版本标 `unverified`，按技能自己的节奏检查新版。
- 命令数、探针数、案例通过率、构建 hash 不写进正文，以脚本输出为准。
- 版本标注：可用性用 `(supported.min+)`（以 `version.json` 为准），未复核用 `unverified`；行为反转的完整版本对比写进 `upgrading.md` / `history/`，当前文档保留一句当前行为和指向升级表的提示。
- 支持窗口下限等于 `params_baseline`，也就是最新归档的到达版本；删除最旧归档不改它。`history/` 上限由 `version.json` 的 `history_max` 决定，超出删最旧。

## 文件

- `version.json`：唯一版本清单；`params_baseline` 是命令/参数面，`behavior_tested` 是最近核对版本，`supported` 是支持窗口。`supported` 的 `min` 只表示命令/参数面下限；行为是否在旧版成立，看正文的 `unverified` 标记和 `upgrading.md`。
- `upgrading.md`：当前窗口的迁移指南，每次覆盖。
- `history/<到达版本>.md`：冻结归档，数量上限见 `version.json` 的 `history_max`，只追加、不 lint。文件头必须是 `# X → Y ...`，文件名是到达版本 Y；相邻文件首尾相接，最后一份的 Y 等于 `params_baseline`。`check_docs` 会校验这条链。
