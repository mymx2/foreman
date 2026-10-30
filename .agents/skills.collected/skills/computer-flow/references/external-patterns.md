# 外部模式参考（未在我们环境验证）

来源是四个公开仓库/技能，按「探索昂贵、验证廉价」收录：撞墙时先查这里，再自己摸索。**没有一条在我们环境跑过**——用之前当假设，用完标结论。每条带来源与置信度。

置信度分级：
- **高**：代码细节具体到注释级（如"用 `wait_for_process_exit` 而非 `wait_for_process`"），大概率真实磨过
- **中**：模式合理但未见过失败案例描述
- **低**：疑似生成物（来源是 skill 生成器仓库），模式可参考、代码别直接抄

## 1. 来源：ECC windows-desktop-e2e（888 行，pywinauto + pytest）

仓库：github.com/affaan-m/ecc。整体置信度**高**——这是 WPF/Qt 真实应用上磨出来的测试骨架，细节密度骗不了人。

### 1.1 测试沙箱：环境变量重定向（Tier 1）

ECC 每个测试用 `subprocess.Popen` 启动应用，把 `APPDATA` / `LOCALAPPDATA` / `TEMP` 重定向到 pytest `tmp_path`，再用 `Application.connect(process=pid)` 接管。应用写的任何配置、缓存、临时文件都落在测试目录，测试结束自动清理。

对我们的价值：**验证期的隔离手段**。第一次真实跑 plan 前，如果目标应用有写配置/缓存的副作用，用这招把它圈进临时目录，跑砸了不污染用户机器。前提是流程用我们的 `launch` 步骤启动应用（我们自己控制环境变量）——`flow_run.py` 的 launch 目前不带 env 参数，借鉴时需要加。

```python
sandbox_env = os.environ.copy()
sandbox_env["APPDATA"] = str(tmp_path / "AppData" / "Roaming")
sandbox_env["LOCALAPPDATA"] = str(tmp_path / "AppData" / "Local")
sandbox_env["TEMP"] = sandbox_env["TMP"] = str(tmp_path / "Temp")
proc = subprocess.Popen([APP_PATH] + shlex.split(APP_ARGS), env=sandbox_env)
pw_app = Application(backend="uia").connect(process=proc.pid, timeout=...)
```

注意：ECC 是测试上下文，可以随便重启应用；我们的 Outcome Contract 规定「结束/重启目标应用进程前需用户确认」。沙箱模式只用于我们自己 launch 的进程，用户已开的应用不动。

### 1.2 进程遏制：Job Object（Tier 2）

把被测进程挂进 Job Object 并设 `JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE`：句柄被 GC（或测试崩溃）时，进程及其全部子进程自动终止。ECC 特意注明它**不隔离文件系统和网络**，只做进程树遏制。

对我们的价值：launch 的应用如果拉起子进程（更新器、浏览器打开链接），崩溃的流程会把孤儿进程留在用户机器上。挂 Job Object 能兜底。结构体布局注释（"LimitFlags 在 offset +16，不是 +44"）说明作者踩过真实的坑。

```python
JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x00002000
job = kernel32.CreateJobObjectW(None, None)
info.LimitFlags = JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
kernel32.SetInformationJobObject(job, 2, ctypes.byref(info), ctypes.sizeof(info))
kernel32.AssignProcessToJobObject(job, hproc)
# 保持 job 句柄存活；句柄释放即终止整个进程树
```

同上，只用于我们自己 launch 的进程。挂 Job Object 对目标进程是实质行为变更（它再无法脱离本进程生命周期），用户机器上已运行的应用不能挂。

### 1.3 ffmpeg 录屏取证

```python
proc = subprocess.Popen([
    "ffmpeg", "-f", "gdigrab", "-framerate", "10",
    "-i", "desktop", "-y", f"artifacts/videos/{name}.mp4",
], stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
# 结束：proc.stdin.write(b"q"); proc.stdin.flush(); proc.wait(timeout=10)
```

对我们的价值：SKILL.md 已有「双证据截图」要求，但静态截图解释不了「点之前明明是对的」。录屏是时间维度的证据，交付验收、复盘「点了没反应」类问题时价值高。默认不开（含隐私，整屏录制），作为可选开关，与 `--evidence-screenshots` 同级。

### 1.4 Qt 特定坑（与我们的 SKILL.md 互相印证）

- **QComboBox 下拉是独立顶层窗口**，class 为 `Qt5QWindowIcon` / `Qt6QWindowIcon`——与 SKILL.md Gotchas 一致，交叉确认，置信度升高
- **`set_edit_text` 在 Qt 5.x 上抛 NotImplementedError**（ValuePattern 缺失），回退 `click_input` + `^a` + `send_keys(text, with_spaces=True)`——**`with_spaces=True` 是关键细节**：pywinauto 的 `send_keys` 默认吞空格。我们走剪贴板粘贴，对此不敏感，但如果哪天补键入路径（比如目标应用禁用剪贴板），这就是标准回退
- **表格用 `(row, column)` 取 cell**，别全窗口文本搜索——与 SKILL.md「Qt 表格读不到行」一致
- **`pytest-timeout` 的 thread 模式杀不掉 Windows 上的 Qt 子进程**，需要 atexit 兜底收割孤儿——印证我们 DesktopLock 按超时回收的思路，也提醒 launch 子进程需要 Job Object（1.2）

### 1.5 分步 trace（opt-in，含隐私开关）

ECC 的 per-step trace 默认关闭，开启时截图 + JSONL，且**键入文本默认 `<redacted>`**，`E2E_TRACE_INCLUDE_TEXT=1` 才记录明文，并警告勿在登录/支付流程开。

对我们的价值：我们的 log.jsonl + before/after JSON 已经覆盖大部分；可借鉴的是「文本默认脱敏、显式开关才放开」的设计——与我们 fill 掩码一致，方向互证。

### 1.6 明确不抄的部分

- Page Object Model：ECC 是测试代码组织形态，我们是交付脚本形态，不匹配
- 三层 CI 集成、pytest-html 报告：我们的产物是给使用者本地跑的脚本，没有 CI 面
- `win.close() → wait_for_process_exit(5) → kill()` 收尾链：杀进程时机被我们的授权契约挡住，只在沙箱验证期用

## 2. 来源：martinholovsky windows-ui-automation（comtypes 直调 UIA）

置信度**低**——来源仓库名叫 `claude-skills-generator`，生成物嫌疑重。模式可参考，代码别直接抄。

### 2.1 唯一值得现在搬的：目标进程黑名单

它的 `SecureUIAutomation` 在任何操作前检查目标窗口进程：keepass、1password、regedit、powershell、procexp 等进黑名单直接拒绝。触发场景对我们是真实的：`--app` 按标题子串匹配，一旦误匹配密码管理器，`fill` 会把业务值（可能含凭据）粘进密码管理器的输入框，或者把剪贴板备份恢复到错误的地方。

考虑加进 `blocker_at` 同层：发现目标窗口进程名命中黑名单时直接失败并列出命中项。约 20 行，不需要 comtypes。

### 2.2 其余模式与我们的威胁模型不匹配

SHA256 可执行文件校验、输入限速、危险组合键屏蔽（Ctrl+Alt+Del / Win+R）、权限分级——这些解的是「执行不可信流程」的问题。我们跑的是用户自己的流程、用户自己的机器，攻击者是我们自己写的脚本 bug，不是恶意流程。为不存在的威胁加防御是负资产。

它对 CVE-2023-28218（UIA 提权）等的罗列可作为安全背景知识留在参考里，不进执行路径。

## 3. 来源：midscene desktop-computer-automation（AI 在环，双层架构）

置信度**中**——产品文档质量高，但模式是为 AI 在环设计的，搬过来要转换。

### 3.1 golden image 断言（我们真实的能力缺口）

midscene 的 `assert --image <基准图>` 按命名基准图对比，支持多图按序配对。我们现在只能断言 OCR 文本，没有视觉基线：图标状态（勾选/未勾选）、颜色语义（成功绿/失败红）、布局塌陷这类「文字断不出来」的验收，只能靠人看截图。

值得进 backlog：给 `expect` 加 `image` 字段（命名基准图 + 容差），验证期之后再做。注意 ECC 1.7 节的 DPI 警告同样适用于此（截图匹配对缩放极其敏感，基准图必须与目标机同缩放录制）。

### 3.2 可以白拿的工程细节

- **健康检查前置**：截图 + 鼠标移动双验证通过才继续，环境问题前置失败——我们 `scene.py` 已经在做，互证
- **分档延迟预算**：截图 ~5s、act/assert 8–20s 按操作类型分档显式超时——与 SKILL.md 超时分级表同构
- **命令命名事故**：`list_displays`（本地）与 `listdisplays`（RDP）一字之差语义不同。我们 CLI 面小，新命令命名先 grep 一遍现有命令
- **"只最小化不关闭"**：保护环境可恢复性，与我们「非预期弹窗不得默认确认或丢弃」同方向
- **HTML/Markdown/JSON 三格式报告**：交付脚本的人读面（HTML 回放）值得考虑，机器读面我们已有 log.jsonl

## 4. 来源：trycua/cua-driver

置信度**中**。它的设计目标（AI agent 实时驱动）与我们（固化离线流程）不同，快照 token 机制、effect 三态、升级阶梯是为「agent 在环的探索」设计的。按需参考其快照失效处理的语义设计即可，无直接可搬代码。定位与我们的分工：**探索陌生应用用 cua，固化每天跑的流程用我们**。

## 使用规则

1. 撞墙时先按症状查本文档（Qt 编辑框、进程孤儿、DPI 截图、密码管理器误匹配）
2. 采纳任何条目前，在本环境做最小验证；验证结论回写本文档对应条目，升级置信度
3. 与我们行为契约冲突的（杀用户进程、绕过授权闸门），验证期沙箱内可用，交付路径禁用
4. 文档只进 `references/`，不进执行路径；执行代码借鉴需先进单测再进 `scripts/`
