# 维护与更新

`jianying` 由本仓（rbz-one）维护，不走 skills.sh 一键安装；技能里**不内置自替换更新器**，
下游按本仓的分发方式自行 git 同步整包。本文件里的“升级”指**剪映版本基线迁移**，不是技能包自更新；
不要在技能内伪造 `update.py` / 远程清单，避免和仓库分发形成两条不可核对的链路。

## 修改前

1. `git status --short --branch`，确认没有别人的未提交改动；
2. 读 [能力边界](limits.md) 与 [来源取舍](upstream.md)，确认改动没有越过已测范围；
3. 改 `scripts/` 时同步看 `test_skill.py` 是否有对应防复发测试。

## 必跑自检

```bash
python scripts/check_skill.py
python scripts/check_skill.py --self-test
python scripts/check_docs.py
python scripts/check_docs.py --self-test
python scripts/test_skill.py
python scripts/probe_gotchas.py --allow-skip
python scripts/capability_probe.py --list
python scripts/run_examples.py
```

`check_skill.py` 只做静态检查；`check_docs.py` 校验文档里的错误码/动词/版本基线，
并反向检查脚本里新增的错误码是否已进 `troubleshooting.md`（findings 里的
`undocumented-code` 就是这一类；文档里有、代码里没有则是 `unknown-code`；两侧都按声明码集比较）。
它的输出字段 `declared_codes` 是真实声明码，`tokens` 是宽口径词元，`tokens` 不能当错误码数量读；
`references/version.json` 的 `undocumented_allow` 是显式豁免表（当前含 `FAILED` 和 4 个脚本内部信封码），
新增真实业务码不应直接丢进豁免表，而应进 `troubleshooting.md`。
`test_skill.py` 是离线行为测试；`probe_gotchas.py` 把关键约束变成可跑探针，
其中 `ffmpeg-honesty` 会独立运行所选 ffmpeg 的 `-filters`，只取滤镜名列与
`resolve_ffmpeg` 的口径比对，而不是只比较同一字段的两个别名；
没有可用 ffmpeg 时该探针只记 skip，不代表诚实性已通过；
`capability_probe.py` 只读检查多类状态（implemented / conditional / planned / unverified /
missing_resource / host_only / account_gated / manual，见脚本 legend）；
`run_examples.py` 跑 `examples/NN-*.py`。真实 `render` / `publish --apply` 需要剪映运行，
属于交付集成验证，不在离线测试里伪造。

## 版本基线

- `references/version.json` 是机器可读基线：`app_baseline`、`behavior_tested`、
  `build_tested`、`supported.min/max`、`skill_version`、`changelog`、`history_max`。
- `python scripts/jy.py probe` 的 `docs.status` 只有四个值，来自
  `scripts/jylib/env.py` 的 `version_policy`：`verified`（窗口内且与 behavior/build 一致）、
  `unverified`（窗口内但不完全一致）、`unsupported`（超出窗口）、`unknown`（没有安装信息，或 version.json 不可读）。
  文档里不要写别的状态词。
- 换剪映版本后，先在临时草稿上跑 `build → render → verify`，再把新结论写进
  `version.json` 和 [能力边界](limits.md)；没跑过就不要改 `supported`。完整流程见
  [版本升级与迁移](upgrading.md)。

## 剪映升级时

1. 升级前留基线：`python scripts/upgrade_check.py --save <baseline.json>`；
   只读、不访问外网（会查本机回环 bridge health），能力探测约 5–8 秒，`--save` 才写文件。
   基线放仓库外本地路径，例如 `<仓库同级>/rbz-one-evidence/jianying/upgrade-baselines/<日期>.json`；
   不要写进技能包或 `scripts/`。
2. 升级后对比：`python scripts/upgrade_check.py --baseline <baseline.json>`；
   `exit_code=10` 表示窗口外/未对齐/能力漂移/探测失败，按输出 checklist 处理。
   在真机复验并更新 `version.json` 之前，10 属预期，不要为了消红提前改窗口。
3. 真机复验后再改 `version.json` / `limits.md`，流程见 [版本升级与迁移](upgrading.md)。

## 版本一致性

`SKILL.md` frontmatter 的 `version` 是技能版本号，`references/version.json` 的
`skill_version` 必须与它逐字相同；改一处就要改另一处，并在 [变更记录](changelog.md)
顶部记一段。三个地方要保持同步：

1. `SKILL.md` 的 `version:` 与 `updated:`；
2. `references/version.json` 的 `skill_version`，以及 `app_baseline` / `behavior_tested` /
   `supported.min` / `supported.max`（后四者还受 `limits.md` 与真机复验约束）；
3. `references/changelog.md` 的版本段落，链接指向 `version.json` 的 `changelog` 字段。

`python scripts/check_docs.py` 会校验：`app_baseline == supported.min`、
`behavior_tested == supported.max`、`supported.min <= supported.max`、
`skill_version` 等于 `SKILL.md` 的 `version`、`references/history/` 下除 `README.md`
之外的 `.md` 数量不超过 `history_max`。任何一条不符都会出现在 findings 里（`kind: "version"`）。

## 打包与分发

分发时排除以下内容，技能包不带证据文件：

- `evidence/`、`_evidence/`：原始证据统一归档在仓库外，不随包分发；
- `__pycache__/`、`.pytest_cache/`：本机缓存；
- 本机绝对路径：plan 里的 `path` 是 2026-11-15 本机路径，分发前改成相对路径或写明需替换。

包内只保留文本结论（`limits.md`、`verification-gaps.md` 与 changelog 的数字），
不保留 plan、截图、成片或复算脚本。

## 不承诺

- 不做自动更新、回滚、历史快照；`version.json` 不保留已废弃字段；
- 不把“结构写进去了”当成“效果生效”，转场/滤镜/文字动画仍按 [能力边界](limits.md) 标未验证；
- 不碰会员校验、DLL 哈希、官方 CLI 宿主令牌，也不解密加密草稿。
