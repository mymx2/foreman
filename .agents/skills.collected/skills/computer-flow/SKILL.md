---
name: computer-flow
description: "Use when the user wants to automate any computer workflow — reading Excel/CSV, processing data, calling APIs, sending emails or IM notifications, filling forms in desktop apps or web pages, simulating keyboard/mouse — then freeze it into a reusable local Python script that runs without AI. Triggers on phrases like \"读 Excel 做某事\", \"固化工作流\", \"本地直接运行\", \"无需 AI 介入\", \"批量处理\". Not for runtime AI agents needing a model in the loop, and not for one-off manual tasks."
---

# Computer Flow

交付物是本地可重复运行的 Python 脚本，运行时零 AI 零 API key。

## Overview

任何电脑自动化工作流都拆成「输入 → 动作 → 输出」三段，纯数据流程可以没有动作段。每段按下面的判断框架选实现方式。没有唯一正确的组合，只有适合当前场景的组合。

## 选型判断框架

**输入段**：数据从哪来、什么格式、多大？
- Excel/CSV/JSON 文件 → 按格式选库，列名映射而非列序
- Excel 文件正被用户打开编辑（锁定读不了）→ `xlwings` 连活动实例读，不用 openpyxl
- 格式不标准（BOM、单引号、尾逗号、JSONL 混注释）→ 先要真实样例文件，写预处理函数归一化，规则写死在脚本里并在样例上验证，不做运行时自适应
- 数据库 → 先确认驱动可用性（`pip list` 查），再选连接方式
- 实时抓取 → 归入动作段，不是输入段
- 读进来后要筛选/去重/排序/合并 → 归入内存数据处理，不是输入段

**内存数据处理**：读进来的数据要怎么变？
- 筛选/去重/排序/列运算 → `pandas.DataFrame`，小数据量用标准库 list/dict 推导式也行
- 多源合并同结构（多个 Excel 纵向拼接）→ `pandas.concat`
- 多源合并按关键列（两个表 join）→ `pandas.merge`
- 行列结构转换（透视/逆透视）→ `pandas.pivot_table` / `melt`
- 行内字段决定走不同动作分支（如某列值为 X 才发邮件）→ 在行级函数里写条件判断，不要拆成多个流程

**文件操作**：要不要碰文件系统？
- 批量遍历/复制/移动/重命名/删除 → 标准库 `pathlib` + `shutil`
- 读写文本文件 → `pathlib.Path.read_text/write_text`，显式指定 `encoding="utf-8"`（Windows 中文环境默认 GBK）
- 监控某个目录的文件变化 → 交给系统定时任务按分钟级调度拉起脚本比对（Windows `schtasks`、mac `launchd`、Linux `cron`），不要写 while True 常驻轮询

**动作段**：操作发生在哪个载体上？
- 纯 API 能做 → 优先 API 而非 GUI（更稳、更快、不受界面状态影响）
- 桌面 GUI：先探测技术栈。Windows 用 `pywinauto` UIA 枚举控件树（项目维护放缓但 API 已稳定，可放心用），控件丰富 → 语义定位；控件极少且有大块自绘区 → 坐标 + 剪贴板混合；UIA 连窗口都找不到 → Win32 `EnumWindows` + 纯坐标/截图。macOS/Linux 没有等价于 UIA 的成熟语义定位库，直接走 `pyautogui` 坐标 + 键鼠 + 截图比对（`pyautogui.locateOnScreen`），窗口管理 mac 用 AppleScript、Linux 用 `xdotool`。所有平台都在交付说明中标注自动化稳定性等级
- 桌面 GUI 遇到系统对话框（文件选择框、打印框）→ Windows 用 pywinauto `Desktop(backend="uia").windows()` 找独立窗口；mac 用 AppleScript `tell application "System Events"`；Linux 用 `xdotool search --name` 找窗口后 `key`/`type`
- Excel 应用本身（执行 VBA、刷新图表/透视表、导出 PDF、写数据后要公式重算）→ `xlwings`，不用 openpyxl；大批量写入时先关自动重算，写完手动 `calculate()`，再恢复。xlwings 不支持 WPS——没装 Office 但装了 WPS（Windows）时改用 `win32com.client.Dispatch` 直接驱动（先试 `KET.Application`，失败回退 `ET.Application`，再失败查注册表；注意 WPS 12.1.0.22529/22525 两个版本 COM 接口整体失效，需回退 WPS 版本）。WPS 个人版无 VBA 支持，透视表/宏/公式重算做不了，退回 openpyxl 操作文件并声明放弃这些能力。mac/Linux 上 WPS 无稳定自动化接口，退回 openpyxl
- 网页：Playwright，但需要登录态复用时优先 `launch_persistent_context` 而非每次登录
- 纯 API：requests，会话保持用 Session
- 发布/上线类动作（发邮件、发 webhook、写数据库、调 API 写操作）→ 默认先演算（dry-run 或测试记录），显式确认后再执行
- 混合载体（如读 Excel 后既填网页又发 API）：按行级粒度拆成独立动作函数，每个函数只操作一个载体
- 同一载体上的连续操作合进一个函数（如填表单的所有字段在一个 `fill_form` 里完成），不要每个字段一个函数来回切换焦点
- 目标是列表类（表格行、相似按钮、商品卡片）→ 先拿相似元素列表再遍历，不要逐个定位
- 自绘控件要读文字（老软件截图取数）→ OCR 例外分支：`paddleocr`（`pip install paddleocr`，中文准；注意 3.x 后模型需单独下载，Python 3.14 不支持 paddlepaddle）或 `rapidocr`（`pip install rapidocr`，轻量约 80MB，CPU 快），不要用 `pytesseract`（中文效果差）

**输出段**：结果给谁看、什么形态？
- 人看 → 追加写 CSV（中断不丢）或格式化 xlsx
- 系统消费 → 写数据库或调 webhook
- 通知 → 邮件用 465 SSL（国内场景更稳），IM 用钉钉/企微 webhook；钉钉发图需走图文/markdown 消息，不能裸发 webhook text

**任务队列与断点续跑**：流程长、可能中断、要续跑？
- 任务来源是文件 → 处理完一行就在结果 CSV 追加一行并记录输入行号，重跑时跳过已处理行
- 任务来源是动态队列（API 拉取、消息订阅）→ 本地 SQLite 存任务状态（`sqlite3` 标准库），字段至少含 `id/status/retry_count/last_error`
- 失败重试 → 行级 try/except，失败行标记状态后继续下一行；重试上限按场景定（网络超时 3 次、应用未响应 2 次），超过标记为永久失败
- 失败分类 → 数据问题（输入行缺列、格式错）不重试直接标记；系统问题（网络超时、应用未响应）才重试
- 破坏性批量操作（批量删除、批量覆盖、大批量写）→ 先演算（dry-run 只统计不写），给用户确认后再执行
- 需要可回放 → 每次演算/执行都在本地落一条记录（时间、动作、行数、结果），GUI 关键节点截图落盘作为留证

**触发方式**：固化后怎么让它跑起来？
- 手动跑 → 技术用户给 `python script.py`，非技术用户附启动脚本（Windows `.bat`、mac `.command`、Linux `.sh`）或打包可执行文件
- 定时跑 → 系统定时任务（Windows `schtasks /create`、mac `launchd`、Linux `cron`/`systemd timer`），不要写 while True + sleep 的常驻脚本
- 文件变化触发 → 交给定时任务按分钟级调度拉起比对，不要上 watchdog

## Outcome Contract

- **Outcome**: 本地可重复运行的 Python 脚本，完成规定动作，运行时零 AI 零 API key。
- **Done when**: 涉及 GUI 时脚本在目标应用各种初始状态下都能跑通（未启动/最小化/弹窗遮蔽/非最大化），连续运行两次结果一致；纯数据/API 流程连续两次退出码 0 且输出一致。交付时不残留 `# TODO` 标记，或 TODO 在交付说明中显式列出。
- **Evidence**: 逐行执行结果 + 状态校验（HTTP 状态码、表单提交成功提示、发送结果）；两次完整运行的退出码。
- **Authorization**: 探测、写脚本、跑脚本可直接做；结束/重启目标应用进程前需用户确认；破坏性批量操作和花钱/不可逆操作执行前需用户确认（确认 = 用户在对话中显式回复，且记录进审计日志）。

## Process

1. **拆解场景**。把需求拆成「输入 → 动作 → 输出」三段（纯数据流程可以没有动作段），按上面的判断框架写出每段的实现方式和理由。完成标准：明确每段用什么库、操作哪个载体、为什么这样选
2. **探测目标**。桌面应用 Windows 用 pywinauto UIA 枚举控件树判断技术栈，mac/Linux 用 `pyautogui.screenshot()` + 人工判断；网页用 Playwright 打开确认定位器可用；API 试一个最小请求确认认证方式；数据库确认驱动和连接串。探测不到真实控件时（应用未装、界面未开放），生成带 `# TODO: 确认定位器` 标记的真实动作函数，不要写 print 假存根——假存根会让脚本跑通了却什么都没做。完成标准：每个动作有明确的定位/调用方式或 TODO 标记
3. **搭建动作链**。按输入数据的粒度（通常是一行）组合动作，每个函数只做一件事。涉及破坏性批量操作或花钱/不可逆动作时，先实现 dry-run 版本（只统计不写），和用户确认后再接真实执行。完成标准：单行数据能完整跑通并读到预期结果，dry-run 输出合理
4. **固化入口**。主脚本读输入、逐行执行、记录结果。入口形态按用户使用方式定：技术用户给 `python script.py`，非技术用户附启动脚本（Windows `.bat`、mac `.command`、Linux `.sh`）或打包可执行文件。完成标准：连续两次运行输出一致
5. **回归验证**。涉及 GUI 时模拟各种初始状态（应用关闭/最小化/弹窗/非最大化）；纯数据流程验证异常输入（文件缺失、空文件、列缺失）。完成标准：正常场景全过，异常场景有明确报错而非静默失败

## 关键技术决策

| 场景 | 做法 | 原因 |
|---|---|---|
| 输入列顺序可能变化 | 按表头名映射 | 用户加列/调列序不影响脚本 |
| 输入文件的关键约束（列名、编码、分隔符） | 搭建期和用户确认后写死在脚本里，不做「猜列名」兜底 | 猜错了静默跑出垃圾结果比直接报错更糟 |
| 结果落盘/webhook 通知 | 正式跑之前先发一条测试记录 | 验证路径/凭据/格式都对，不要跑到一半才发现写不进去 |
| 凭据（密码/授权码/token/webhook key） | 环境变量或 `.env`，且 `.env` 必须进 `.gitignore`，交付前 `git check-ignore .env` 验证 | 「写在 .env 但 .env 被提交了」是最高频事故 |
| 非凭据环境值（URL/路径/阈值/开关） | 集中到一个 Config 文件（`.env` 或 `config.ini`），不散落在代码里 | 环境迁移时改一个文件，不用翻代码 |
| 等待元素出现/消失/属性变化 | 显式等待（Playwright `wait_for_selector`、pywinauto `wait_until_passes`、自绘界面轮询截图比对），任何等待循环必须有超时上限并抛错；超时上限用秒（等待类）或次数（重试类），按场景选；轮询间隔 ≥ 单次轮询操作耗时（轻量属性读取 0.2s、截图比对 0.5s、OCR 2s）；确知节拍必须用 sleep 时注释 why；窗口级等待（等弹窗关闭、等主窗激活）同样适用 | 轮询状态而非假设时间，无界轮询是偷懒实现 |
| Flutter/Qt 编辑器不接受语义定位键入 | Windows `clip.exe` / mac `pbcopy` / Linux `xclip` 写剪贴板 + Ctrl+V，备选平台原生 API | 自绘控件不实现 TextPattern/ValuePattern，剪贴板是绕过该接口的 workaround |
| 窗口最小化时连不上 | Windows `findwindows.find_elements(class_name=...)` 兜底；mac AppleScript `tell application ... to activate`；Linux `xdotool search --name ... windowactivate` | 各平台默认都不枚举最小化窗口 |
| 自绘编辑区无语义定位节点 | 窗口客户区相对坐标 + 脚本启动时断言窗口尺寸固定且已知（优先最大化；不可最大化时 resize 到校准尺寸或显式报错） | 相对坐标在窗口移动后仍有效，尺寸变化会失效 |
| UIA 拿到元素矩形但元素不可点击 | 用元素矩形内相对位置锚点 + 偏移：`rect = elem.rectangle()`，锚点选角/边中点/中心（容器型元素不用中心，中心常命中错误子元素），偏移为相对锚点的像素值；点击前重新取矩形（列表滚动后旧矩形失效） | 中心点在容器型元素上常点到错误子元素；矩形随布局变化 |
| 每次运行前 | 新建干净标签/表单 | 上次填写的数据、焦点位置、弹窗等残留状态会让脚本行为不确定 |
| 批量发邮件/webhook | 按服务商限额定间隔，个人 SMTP 注意日限额 | 避免触发频率限制 |
| HTTP 请求 | 必设 timeout，默认 10s | requests 默认无限等待，脚本挂死 |
| 结果落盘 | 追加写而非一次性写 | 中断后已处理行不丢 |

## Common Rationalizations

- 「UIA 枚举不到控件就是应用不支持自动化」——先检查窗口是否最小化，再确认是不是 Flutter/Qt 自绘
- 「直接在用户当前标签页操作更省事」——残留状态让脚本行为不确定
- 「中心点最直觉所以用中心」——容器型元素的中心常命中错误子元素，该用角或边中点

## Red Flags

- 整批操作共用一个 try/except，一行失败全批中断
- 屏幕绝对坐标而非窗口客户区相对坐标
- 无界等待循环（无超时上限的 while True 轮询）

## Verification

每个动作函数写完后立即在真实目标上验证一次。最终交付前跑两遍完整流程，第二遍用于发现状态残留问题。

**交付前整体验证**覆盖三个维度：
- 功能：每行输入都产出了预期结果（HTTP status、响应 JSON 里的业务 code、表单提交成功提示）
- 韧性：中断后重跑能续上，已处理行不重复
- 边界：输入文件缺失/空文件/列缺失时有明确报错

**结果判定纪律**：判定成功只看结构化字段（HTTP status、响应 JSON 里的 code、返回的行数），不看 stdout 日志级别或「没报错就是成功」。

## Hard Rules

- **优先语义定位，坐标兜底**：UIA/Playwright 定位器能用就不用坐标
- **GUI 脚本启动时断言窗口尺寸固定且已知**：自绘区坐标依赖窗口尺寸；优先最大化，不可最大化时 resize 到校准尺寸或显式报错
- **输入按表头名映射**：不假设列顺序
- **动作函数单一职责**
- **凭据不进版本库**：`.env` 必须进 `.gitignore`，交付前 `git check-ignore .env` 验证

## Gotchas

| What happened | Rule |
|---|---|
| `send_keys` 输入没进编辑框 | 窗口未聚焦；先 `set_focus()` 再点击目标控件 |
| 粘贴后内容没变 | 自绘编辑器要先点击获得焦点，Ctrl+A/Ctrl+V 之间留 100ms |
| 应用已打开但连不上 | 窗口最小化；Windows 用 `findwindows.find_elements` 兜底，mac AppleScript `activate`，Linux `xdotool windowactivate` |
| Playwright 定位器偶尔失败 | `wait_until="domcontentloaded"` 后再操作 |
| 批量邮件发到一半被限流 | 加大间隔；个人 SMTP 有日限额 |
| 钉钉 webhook 返回 310000 | 关键词或加签校验失败 |
| 写 Excel 后列宽全是 `#####` | 写完必须 `auto-fit-columns`；格式码用 US notation（`,` 分组 `.` 小数，Excel 自动本地化） |
| 脚本跑完 Excel 文件还被锁 | `xlwings` 写完必须 `close + save`；WPS COM 路径同样 `Close(SaveChanges:=True)`；不关会留进程锁文件 |
| 点了按钮应用没反应 | 上一个动作还没被处理；GUI 动作完成后默认 delay 一拍（0.5-1s）再发下一个，不要连续瞬发 |
| 关闭标签/窗口时卡住 | 弹了确认框（保存API/未保存更改）；关闭后检查是否有「不保存/Discard」按钮，有则点掉 |
