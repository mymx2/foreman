---
name: photocraft
description: |
  通过 control 协议或 headless CLI 操作 PhotoCraft 图像编辑器。当用户要驱动 PhotoCraft 做图像编辑自动化时使用，
  范围：编辑图层、选区、文字与滤镜，查询文档结构与字体，批量转换格式。
  不适用于：普通图片格式转换（直接用 CLI convert 即可，无需加载本技能）、
  Figma/浏览器内设计稿操作（走 chrome 或其他技能）、Python/PIL 纯代码绘图。
---

# PhotoCraft

GUI 桥接端口与 headless 会话是两个方法集不同的世界；文件读写永远走能力域方法，不走含磁盘路径的引擎命令。

## Outcome Contract

- **Outcome**: 用户的 PhotoCraft 编辑意图（编辑、查询、导出、批量）通过正确的会话与命令完成，且结果经过 inspect 验证。
- **Done when**: 目标编辑在 `document.inspect` 中可见（层树/属性/历史），文件输出落盘且 `warnings` 为空或已解释，无遗留测试文档。
- **Evidence**: `document.inspect` 返回的目标字段；`app.save` 回执的 `path` 与空 `warnings`；`jobs.list` 无 running 作业。
- **Authorization**: 连接、查询、新建/关闭会话内测试文档可直接做；保存覆盖用户已有文件、`--in-place` 批量覆盖原件，先确认再执行。

## When to Use

- 用户明说 PhotoCraft / Photocraft，或要求对 PSD/pcraft 文件做图层级编辑自动化。
- 查询 PSD 使用的字体（含缺失字体清单）、图层树、文档元数据。
- 批量转换/处理一个目录的图片且需要引擎命令（旋转、滤镜、调整）参与。

## Process

1. **选会话**。先探测再动手：跑 `scripts/photocraft-bridge.py`（运行它；下称 bridge）的 `session.inspect` 探测 GUI——`documents` 非空即有活会话，编辑用户打开的文档只能在这里做。无 GUI 或要无人值守批处理时，用 `photocraft-cli serve --port <port>` 起 headless 会话，bridge 加 `--port` 连它。两个会话的文档互不可见；headless 的文件方法集更宽（`doc.open/doc.save/doc.render`），GUI 桥接靠 `app.open/app.save`。
   完成标准：bridge 返回了目标会话的文档列表，或 headless 端口已应答 auth。

2. **查命令签名**。任何命令的参数先查注册表再写：bridge 发 `engine.commands`，或终端跑 `photocraft-cli commands --filter <text>`（909 条，`--json` 含完整参数描述）。`params` 必须是 JSON object，传数组/字符串/数字会被整条拒绝。
   完成标准：拿到了目标命令的参数描述原文，而不是凭印象拼参数。

3. **编辑与验证闭环**。用 `engine.execute {command, params}` 执行（不弹对话框，直接用默认值）；要交互对话框时才用 `ui.menu.invoke` + `ui.dialog.*`。每步编辑后立即 `document.inspect` 验证层树/属性/历史符合预期，失败就修，通过才进下一步。层树嵌套在 `children` 字段，文字图层的字体在 `text.font`。
   完成标准：inspect 返回的目标字段与用户意图一致。

4. **文件进出**。引擎命令里凡是带磁盘路径的（`file.open`、`file.save`、`file.saveACopy`、`file.openAs`、`file.export.*`、`layer.exportAs` 等）一律被拒，报 "uses ambient filesystem paths and is disabled"——这不是故障，是能力域隔离。读写改走：GUI 桥接 `app.open {path}` / `app.save {path}`（相对 automation root 的相对路径；`app.save` 不带 path 只回写原 PSD/.pcraft）；headless 用 `doc.open/doc.save`；不走会话的纯转换直接 `photocraft-cli convert/run/batch`。回执里的 `warnings` 要读给用户（如"adjustment layer flattened"）。
   完成标准：`app.save`/`doc.save` 回执含落盘 `path` 且 `warnings` 已解释。

5. **长任务用作业**。所有 `filter.*`、`edit.contentAwareFill`、photomerge 等默认同步等待；要异步就 `engine.execute` 加 `wait: false` 拿 job id，轮询 `jobs.list` 到 done/failed/cancelled 再做后续编辑。作业运行期间它会锁住所属文档，相关命令报 "still running on this document"。超时或断连后先 inspect 文档与历史再决定是否重放——操作可能已完成，盲目重试会双份执行。
   完成标准：`jobs.list` 中无涉及目标文档的 running 作业。

## Common Rationalizations

- "file.save 报错说明安装坏了" — 这是设计行为；能力域方法（app.save/doc.save）才是正道。
- "GUI 端口和文档里 serve 的方法一样" — 不一样；GUI 桥接只有 engine.execute/engine.commands/jobs.list|cancel 和 ui.* / app.* / prefs.* 等，`doc.*` 是 headless 专属，报 unknown method 就换 `engine.execute` 包裹引擎命令。
- "参数差不多直接写" — 参数校验是全有或全无，一处类型错整条拒绝；先查签名。

## Red Flags

- 未经 inspect 验证就声称编辑完成。
- 对用户打开的文档使用 headless 会话（改的是另一个世界的副本，用户窗口毫无变化）。
- 在命令参数里塞绝对路径绕过能力域。
- 批量 `--in-place` 或覆盖保存前未确认。

## Verification

1. 每次编辑后 `document.inspect` 对应字段可见变化（层、属性、历史状态数）。
2. 保存后回执 `path` 存在、`warnings` 为空或已转述。
3. 收尾 `session.inspect` 确认没有遗留的临时测试文档。
4. 修改 `scripts/photocraft-bridge.py` 或怀疑本机环境异常时，跑 `scripts/test-bridge.py`（运行它，自带 fake control server，无需 PhotoCraft）；全绿再继续，任何失败先看 stderr 与对应用例。

## Hard Rules

- 每条 TCP 连接的第一个请求必须是 `auth`（token 64 位 hex）；bridge 脚本已实现，勿手写跳过。
- 端口探测模式会把 token 发给探测区间内第一个 auth 通过的本地监听进程；不信任本机环境时显式 `--port` 或 `PHOTOCRAFT_CONTROL_PORT` 指定。
- `params` 只能是 JSON object、省略或 null。
- 凭据不进命令行参数、不打印、不提交；从 token 文件或环境变量读。
- 批量步数上限 256；headless 预览边长上限 2048px。

## Gotchas

| 现象 | 处理 |
| --- | --- |
| `unknown method 'document.inspect'`（GUI 桥接） | 引擎命令要包一层：`engine.execute {command: "document.inspect"}` |
| 保存/打开报 ambient filesystem paths | 换 `app.open`/`app.save`（GUI）或 `doc.*`（headless），路径相对 automation root |
| 图层树里找不到子层 | 嵌套字段叫 `children` 不是 `layers` |
| 文字图层字体名查不到安装状态 | 用 `engine.execute type.resolveMissingFonts {}` 拿缺失清单，`type.fonts` 拿已装清单 |
| GUI 裸启动不知道端口 | PhotoCraft 自动选端口并把 token 写进其配置目录的 control.token；bridge 会探测 7878–7881 |
| 中文文档名乱码 | 终端编码问题；用 `python -X utf8` 跑 bridge，别用管道转码 |

## Output

- 执行的命令序列与关键回执（inspect 证据、save path、warnings）。
- 会话类型（GUI 桥接 / headless）与端口。
- 遗留事项：未完成的编辑、失败的作业、需要用户决策的覆盖确认。
