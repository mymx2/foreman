---
name: gh-toolkit
description: 处理 GitHub PR 评论、CI 失败排查、提交发布工作流。当需要分析 PR 评论线程、诊断 GitHub Actions 失败、或执行提交推送开 PR 时使用。不适用非 GitHub 平台或纯本地 git 操作。
---

# GitHub 协作工作流

基于 `gh` CLI 的 PR 评论分析、CI 失败诊断、提交发布三合一工作流。

## Outcome Contract

- **Outcome**: 完成 PR 评论分析、CI 失败诊断、或提交发布开 PR 的其中一个工作流。
- **Done when**: 评论已分类并给出处理方案；CI 失败根因已定位并给出修复计划；或分支已推送、PR 已创建。
- **Evidence**: `gh` CLI 命令输出；PR 评论线程 JSON；Actions 日志片段；PR URL。
- **Authorization**: 所有 `gh` 命令需先确认已认证（`gh auth status`）。写操作（stage/commit/push/PR 创建）需用户确认范围。

## When to Use

| 场景 | 触发词 |
|------|--------|
| 分析 PR 评论、处理 review 反馈 | "看看评论"、"处理 review"、"PR 有什么意见" |
| 诊断 CI 失败、查看 Actions 日志 | "CI 挂了"、"检查为什么失败"、"看看日志" |
| 提交代码、推送分支、开 PR | "提交并推送"、"开个 PR"、"发布这些改动" |
| 通用 GitHub 仓库/PR/Issue 查询 | "看看这个 PR"、"仓库状态如何" |

## Process

按场景路由到对应工作流，所有路径共用前置检查。

### 1. 通用前置检查

所有路径必须先执行：

```bash
gh auth status
```

未认证时提示用户运行 `gh auth login`，确认后继续。

### 2. 按场景路由

根据用户意图选择 A/B/C/D 其中一条路径执行。

#### A. PR 评论分析（gh-address-comments 合并）

1. 解析 PR：用户给 PR 号/URL 直接用；否则用 `gh pr view --json number,url` 取当前分支 PR。
2. 拉取评论数据：
   - 轻量总结用 `gh pr view --comments`。
   - 需 thread 级状态（`isResolved`/`isOutdated`/行号锚点）用脚本：
     ```bash
     python "<skill-dir>/scripts/fetch_comments.py" > pr_comments.json
     ```
3. 分类评论：按文件/行为域分组，区分 actionable 变更请求 vs 信息性评论/已解决/重复。
4. 确认范围：呈现编号列表，用户未全选时问清处理哪些；全选时标记歧义项。
5. 实施修改：本地改代码，每条变更可追溯回评论线程。
6. 总结：列出已处理/保留的线程及验证方式。

**写安全**：不擅自回复 GitHub 评论、不 resolve 线程、不提交 review，除非用户明确要求。

#### B. CI 失败诊断（gh-fix-ci 合并）

1. 解析 PR：同 A。
2. 拉取失败检查：
   ```bash
   python "<skill-dir>/scripts/inspect_pr_checks.py" --repo "." --pr "<number-or-url>"
   ```
   加 `--json` 得机器可读输出。
3. 脚本自动处理：
   - `gh pr checks` 字段漂移回退
   - 提取 run ID / job ID
   - 拉取 Actions 日志（含 pending 日志回退到 job 日志）
   - 提取失败片段（默认 160 行，前后 30 行上下文）
4. 分析结果：
   - `external`：非 GitHub Actions（Buildkite 等），只报 URL 不深入。
   - `log_pending`：日志未生成，稍后重试。
   - `log_unavailable`：日志拉取失败，报错误原因。
   - `ok`：有日志片段，定位根因。
5. 总结失败：给检查名、run URL、日志片段；缺失日志明确说明。
6. 提出修复计划，等用户确认后实施。
7. 修复后重跑本地验证，再 `gh pr checks` 复查。

**硬规则**：不暗示 GitHub connector 能替代 `gh` 拉 Actions 日志；非 GitHub Actions 只报 URL。

#### C. 提交发布（yeet 合并）

1. 确认范围：`git status -sb` 看 diff，工作树混杂时不默认 `git add -A`，问清哪些文件进 PR。
2. 分支策略：在 `main`/`master`/默认分支时创建 `codex/{description}`；否则留当前分支。
3. Stage：优先显式路径；用户确认全树才 `git add -A`。
4. 提交：用确认过的描述，简洁。
5. 检查：跑最相关本地测试；失败因缺依赖则装后重跑一次。
6. 推送：`git push -u origin $(git branch --show-current)`。
7. 开 PR：
   - 优先用 `gh pr create --draft --fill --head $(git branch --show-current)`。
   - 分支从 fork 推送或目标仓库不同时，必须用 `gh pr create` fallback（connector 跨仓库 head 语义不干净）。
   - PR body 写临时文件保证 markdown 换行正常。
8. 总结：分支名、commit、PR 目标、验证结果、待确认项。

**写安全**：不擅自 stage 无关变更；混杂工作树不确认不 push；默认开 draft PR；远程不可达时先报阻塞。

#### D. 通用 GitHub 查询（github 合并）

1. 解析上下文：用户给 repo/PR/issue/URL 直接用；否则 `gh pr view` / `gh repo view` 取当前上下文。
2. 分类请求：
   - repo/PR triage → 总结 PRs/issues/patches/comments/labels/reactions
   - review follow-up → 走 A
   - CI debugging → 走 B
   - publish changes → 走 C
3. 路由后立即执行对应流程，不扩大范围。

**输出**：triage 给简洁状态总结；mixed 请求说明路由原因；connector 写操作前重述目标；不暗示 connector 能拉 Actions 日志。

## Scripts

两个脚本均为**执行用**（非参考），自包含可独立运行。

### scripts/fetch_comments.py

拉取当前分支 PR 的全部评论：conversation comments + reviews + review threads（含 resolved/outdated/行号）。

用法：
```bash
python scripts/fetch_comments.py > pr_comments.json
```

要求：已 `gh auth login`；当前分支有关联 PR。

### scripts/inspect_pr_checks.py

拉取 PR 失败检查，取 Actions 日志并提取失败片段。失败时退出码非零，可用于自动化。

用法：
```bash
python scripts/inspect_pr_checks.py --repo "." --pr "123"
python scripts/inspect_pr_checks.py --repo "." --pr "https://github.com/org/repo/pull/123" --json
```

## Red Flags

- 用 connector 拉 Actions 日志 → 日志只能 `gh` 拉，connector 无此能力。
- 把 flat PR comments 当完整 thread 状态 → 必须用 `fetch_comments.py` 拿 `isResolved`/`isOutdated`。
- 混杂工作树直接 `git add -A` → 必须先确认范围。
- 跨仓库 fork PR 用 connector 创建 → 用 `gh pr create` fallback。

## Verification

1. 评论分析：`pr_comments.json` 包含 `review_threads` 数组。
2. CI 诊断：脚本输出含失败检查名、run URL、日志片段；`--json` 输出可解析。
3. 发布：`gh pr view` 能看到新 PR；PR body markdown 渲染正常。

## Hard Rules

- `gh auth status` 失败必须先解决认证，不跳过。
- 写操作（stage/commit/push/PR 创建）前必须确认范围。
- 脚本输出（特别是日志片段）**原样传递**，不总结、不重排、不格式化。
- 非 GitHub Actions 检查只报 URL，不深入排查。
