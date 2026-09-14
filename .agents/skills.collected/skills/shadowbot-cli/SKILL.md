---
name: shadowbot-cli
description: "通过 shadowbot-cli（官方 shadowbot.shell-cli）操作本地已安装的影刀RPA 6.3+ 客户端：运行应用、查询任务与日志、管理触发器与消息、在 Studio 中创建或编辑流程、插入并填充可视化指令、保存编译与运行验证。当用户要求运行影刀应用、排查影刀任务、编写或修改影刀流程、管理影刀触发器时使用。不适用于未安装影刀 6.3+ 客户端的机器，不用于影刀云端企业版开放API或旧版社区 MCP Server 场景。"
when_to_use: 运行影刀应用, 影刀任务日志, 影刀流程编辑, 插入影刀指令, shadowbot-cli, 影刀触发器, 影刀studio
---

# ShadowBot CLI

唯一可靠的编程口子是官方 `shadowbot.shell-cli`：它封装了客户端进程内的本地 REST API（127.0.0.1）。**客户端没启动，所有命令都会失败**——先确认影刀在运行，再执行任何业务命令。

## Outcome Contract

- **Outcome**: 在用户机器上通过 `shadowbot-cli` 完成一次影刀操作，并用命令的 JSON 输出作为执行证据。
- **Done when**: 查询类命令 `ok: true`；流程编辑 `state: applied`；运行验证 `run_succeeded: true` 且 `verification.static_error_count` 为 0。
- **Evidence**: 命令原始输出（taskId / run_id / block_id 等关键字段），编辑类操作以 `studio app run` 结果或诊断快照佐证。
- **Authorization**: 查询与列举直接执行；运行应用、修改或删除应用与流程、安装扩展等有副作用的操作先向用户确认。

## When to Use

- 触发或停止影刀应用、查任务历史 / 状态 / 日志
- 在 Studio 中创建应用、编辑流程指令、保存编译、运行验证、诊断报错
- 管理触发器（文件 / 热键 / 邮件 / 计划）、消息中心、自动化扩展
- 查询应用列表与回收站

## Preflight

1. 运行 `shadowbot-cli auth current`，期望 `ok: true` 且 `data.loggedIn: true`。
2. 会话缺失时先让用户启动并登录影刀客户端；已记忆的账号可用 `shadowbot-cli auth login --username <账号>` 免密恢复。
3. `studio` 系列命令要求环境变量 `SWITCH_STUDIO_MCP_CLI_SUPPORT=1`；PATH 中的 `shadowbot-cli` shim 已默认带上，直接调用即可。若 shim 不存在，用全路径调用并在命令前设置该变量。

## Process：运行一个云端应用

1. `shadowbot-cli console app --page-size 50` 找到目标 `<appId>`（`--app-type developed` 或 `subscribed`，默认 developed；`--search` 支持名称筛选）。
2. `shadowbot-cli console task run --app-id <appId> --timeout 60s`；默认 15s 对首次运行偏短，统一显式加大。
3. 从响应取 `<taskId>`；需要细节时依次用 `console task logs --task-id <taskId>`、`console task history`、`console task stop --task-id <taskId>`。
4. `statusName` 为 `faulted` 时读返回的 `error` 字段：若报“应用不存在”或“没有该应用的操作权限”，说明该应用是 6.0.x 时代的本地残留（云端无记录），CLI 管不了，请用户在客户端内处理。

## Process：在 Studio 中创建并编辑流程

1. `shadowbot-cli studio open --name <应用名> --timeout 90s` 新建并保持打开；对已有应用改用 `studio open --app-id <uuid>`。
2. `shadowbot-cli studio flow list` 拿到 `<flow-id>`（默认 main），`studio flow blocks-list --flow-id <flow-id>` 查看现有指令。
3. 查指令原型名与字段契约：执行 `scripts/block-lookup.mjs`（传 `search <关键词>` 找名字、`detail <prototype_name>` 出字段）。服务端的 catalog 查询工具被禁用，必须走本地知识库，禁止凭记忆编造。
4. `shadowbot-cli studio flow edit-blocks --flow-id <flow-id> --op insert --blocks '[{"prototype_name":"<名>","comment":"<注释>"}]' --index -1`，从响应记下 `block_id` 与每个字段的默认形态。
5. 填参数：`shadowbot-cli studio flow fill-blocks --flow-id <flow-id> --fills @fills.json`。值采用 `{"expression":"'<文本>'"}` 形态（文本字面量套单引号）；复杂 JSON 一律走 `@file` 传参，避免 shell 转义事故。
6. `shadowbot-cli studio app save` 保存并编译。
7. `shadowbot-cli studio app run --flow-id <flow-id> --timeout 90s` 运行验证；失败用 `shadowbot-cli studio diagnostics snapshot` 与 `studio app logs` 定位，修复后回到第 5 步。
8. `shadowbot-cli studio current sync` 同步上传并关闭应用。

## Common Rationalizations

- “命令里没报错就是成功了”：只看退出码不够，必须核对 JSON 的 `ok` / `state` / `run_succeeded` 字段才有证据。
- “原型名大概叫 xxx”：禁止猜测；指令名和字段只能来自 block-lookup 脚本或命令响应回显。
- “超时了就重试”：`studio create/open` 超时可能是假超时，应用实际已建，重试前先列表查重。

## Red Flags

- 未确认客户端运行就批量执行 → 先跑 `auth current`。
- 在 bash 里直接内联 `--inputs` / `--fills` 的 JSON → 反斜杠被吞，一律用 `@file.json`。
- 对有副作用操作（运行、回收、发布）不先获得用户确认就开始执行。

## Verification

- 运行类：`console task run` 的 `success` / `statusName`，或 `studio app run` 的 `run_succeeded`。
- 编辑类：`fill-blocks` 返回 `state: applied`；`save` 后 `studio diagnostics snapshot` 的 `static_errors` 为空。
- 清理类：`console app` 与 `console app recycle list` 确认目标已不在列表中。

## Hard Rules

1. 每个会话的第一条业务命令是 `auth current`；客户端未运行则不继续。
2. `prototype_name`、字段名、参数值只能来自 block-lookup 脚本或命令响应，禁止编造；帮助里没有的子命令先用 `-h` 探索再执行。
3. 有副作用的操作先向用户确认后再执行。
4. `studio create/open` 超时后先查重再重试，避免重复建应用。
5. 命令输出中的账号、密钥等敏感字段不写入任何文件。

## Gotchas

| 现象 | 处置 |
| --- | --- |
| `studio` 命令报 studio MCP CLI support is disabled | 环境变量未生效；用 PATH 里的 `shadowbot-cli` shim，或手动设置 `SWITCH_STUDIO_MCP_CLI_SUPPORT=1` |
| `studio create` 超时但应用已建 | 默认 15s 太短；加 `--timeout 60s`，重试前先 `console app` 查重 |
| `catalog.blocks` / `flow blocks-forms` 返回 TOOL_DISABLED | 服务端禁用；改用 `scripts/block-lookup.mjs` 查本地知识库 |
| `fill-blocks` 报 unknown value tag | 值形态错误；文本用 `{"expression":"'文本'"}`，复杂 JSON 用 `@file` |
| 回收或详情报“应用不存在” | 6.0.x 时代的本地残留应用；请用户在客户端内处理 |
| `console task run` 报没有操作权限 | 应用未同步到云端；先在 Studio 里 `save` 再运行 |

## Output

执行后向用户汇报：执行了哪些命令、关键输出字段（taskId / run_id / block_id、状态值）、以及需要人工处理的阻塞点。关键 JSON 字段原样保留，不重述全文。
