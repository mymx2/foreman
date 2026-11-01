# 下游更新

> 受众：下游运营 AI。只更新整个技能包，不维护技能；维护见 `maintenance.md`（上游专用）。

## 什么时候查

- 任务开始先跑 `python scripts/update.py --status`，看上次检查/更新结果；缓存未过期且本地版本没变就不联网。
- 需要检查时跑 `python scripts/update.py --check`；周期由 `references/update.json` 的 `check_interval_days` 决定（默认 7，范围 3–30），`--refresh` 强制刷新。
- `find_cli.py --check` 报版本不匹配只说明 CLI 比文档新，先标 `unverified` 继续，不要因此刷新技能。只有用户明确要求查新版，或管理器提示技能版本更新时，才用 `--refresh`。

## 命令

```sh
python scripts/update.py --status         # 本地版本、上次 check、上次 apply、hold
python scripts/update.py --check          # 当前 / 过期 / 未知；退出 0 / 10 / 2
python scripts/update.py --apply --yes    # 下载、校验、整包替换（auto：git → 直连 ZIP → 镜像 ZIP）
python scripts/update.py --rollback --yes # 恢复最近一次备份
```

`--apply` 默认 `--method auto`：有 git 时用 sparse checkout，没有 git 时用 GitHub 仓库 ZIP；直连失败走 `mirrors`（默认 ghfast.top）。校验 `test_docs.py` 和版本号后交给独立 helper 在进程退出后整包替换，结果写 `.state/last_apply.json`。`--apply` 退 0 只代表 staged，用 `--status` 轮询到 `last_apply` 不是 `pending` 才算完成；退 11 表示 backoff/hold，不要立刻重试。`--rollback` 会给回滚掉的坏版本留 hold，除 `--force` 外不再装回。

## 更新级别

- `normal`：任务结束后更新；失败不影响当前任务。
- `security` / `breaking`：任务开始前更新；更新失败时保留本地，明确标 `unverified`，只在任务确实受影响时提示运营。
- 普通 CLI 版本升级不触发技能更新；只有技能自身 `version` 变新才整包替换。

## 规则

- 状态在 `.state/update.json`、`.state/last_apply.json`、`.state/hold.json`；不存 token、账号或 header。
- 检查失败会进入负缓存/退避（首次约 30 分钟，之后递增到 24 小时），不会每个任务重复联网；apply 失败也会退避，`--force` 可跳过。
- `--check` 总预算约 6 秒（直连/镜像分摊）；`--apply` 每个下载/git 最多 60 秒。超时就放弃，不在任务中途等。
- 直连 GitHub 失败会自动试 `references/update.json` 的 `mirrors`；镜像只用于公开仓库，私有仓库不要走镜像，也不要把 token 发给第三方。
- 只读安装：`--check`/`--status` 可用；`--apply` 报权限，交给技能管理器或管理员。
- 无网络/上游不可达：继续用本地版本；版本不匹配时结论标 `unverified`。同一任务里不要反复重试，下次任务再查。
- 私有 GitHub：直连时用 `GITHUB_TOKEN` 或 `PHOTOCRAFT_UPDATE_TOKEN` 环境变量，令牌不写进文件、日志或缓存。
- 备份和 staging 放在用户缓存（Windows `%LOCALAPPDATA%`、macOS `~/Library/Caches`、Linux `$XDG_CACHE_HOME` 下的 `photocraft-skill/`），不污染技能目录；`--rollback` 用它恢复。
- 更新后至少跑 `scripts/test_docs.py`；`find_cli.py --check` 只在需要确认 PhotoCraft 兼容性时跑。
- 更新在任务开始前或结束后做，不要在任务中途替换技能目录。
