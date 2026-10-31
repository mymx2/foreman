# 字体：查缺失、选替代、安装、授权

> 核对版本：命令 id 与参数按 photocraft-cli 0.14.0 (ff4738810) 复核；行为记录来自 0.10.0–0.14.0 的实测，0.14 未逐条重验的条目保留原文。文字排版本身见 `text-layout.md`；随稿交付字体副本的规则见 `psd-workflow.md`。

## 查现状

```sh
photocraft-cli run <文件> --cmd type.fonts                     # 已装家族：{families:[…]}
photocraft-cli run <文件> --cmd type.fonts --params '{"family":"Inter"}'
                                                               # 某家族的字面：{faces:[{family, style, weight, postscriptName, italic, axes}]}
photocraft-cli run <文件> --cmd type.resolveMissingFonts        # 只列缺失：{missing:[…]}
photocraft-cli info <文件> --compact                           # warnings 里也会带缺字体
```

- `type.fonts` 不需要文档也能跑；faces 里的 `postscriptName` 是 PSD 里实际存储的名字。
- PhotoCraft 写的 PSD 只保存 PostScript 名（如 `Inter-Regular`），家族名和样式字段为空。核对字体装没装要按 PostScript 名比对，别拿家族名直接比，否则会对不上。
- **字族没缺不代表字面没缺**：`type.resolveMissingFonts` 按字族判定，返回 `{"missing": []}` 时，实际 PostScript 字面可能仍缺——例如本机只装了 Medium，PSD 要的是 Bold，可能静默回落到 Medium，字宽和排版全变。交付前必须逐文字层从 `type.info` 读实际 PostScript 名（`runs[].style.postscript_name`），对照 `type.fonts` 已装列表里的 `postscriptName`；不只看 `resolveMissingFonts` 的 `missing` 是否为空。注意：`type.info` 用蛇形 `postscript_name`，`type.fonts` 用驼峰 `postscriptName`，比对时要统一大小写。
- **逐层核对必须按 id 或先 select**：`type.info` 的 `layer` 只认数字 id，传图层名会被静默忽略、回落到活动层（实测 0.18，0.14 未复核：查 `T1` 回来的是 `T2` 的 id 和文本）。批量核对时要先 `layer.select {name}` 再不带 `layer` 调 `type.info`，或从 `layer.list` 取 id 后传 id；按名字遍历会全部得到同一层，结果是假通过。
- **按字面名严格比对会误拦可变字体**：实测 103 个已装字族里有 7 个对不上——可变字体通常只登记一个字面（如只有 Thin），稿里写 Regular 就会对不上。字面名查不到时先看该字族的 faces `axes` 是否非空、`style` 是否与实际请求的样式不符，别直接判缺失。家族名本身也要用准确写法（`Noto Sans SC` 带空格，写成 `NotoSansSC` 会回空 faces，见下条）。
- **`type.fonts` 传不存在的 family 也回 `{"faces":[]}`、退出码 0**，和"字族存在但没装"分不出来。字族名先按 `type.fonts {}` 的 `families` 列表核对拼写，再查 faces。
- `psd_audit.py --installed-fonts` 接受 `type.fonts` 的输出，会从每个条目里收集 `family`、`postscriptName`、`postscript_name`。

## 逐层字面核对（可执行）

`type.fonts`、`layer.list`、`type.info` 都是引擎命令，要经 serve 的 `engine.execute` 在同一个会话里跑（用 pclib 时是 Serve 的 execute 方法）；会话方法 `doc.*` 才走 call。这样避免逐层重开 CLI：

```python
# session 即 pclib.Serve 实例（scripts/pclib.py）
faces = set()
for fam in session.execute("type.fonts")["families"]:      # 先核对家族拼写
    for face in session.execute("type.fonts", {"family": fam}).get("faces") or []:
        name = face.get("postscriptName") or face.get("postscript_name")
        if name:
            faces.add(name.casefold())

# flat:true 会把嵌套层一起列出，带 depth / parent
layers = session.execute("layer.list", {"flat": True})["layers"]
missing = []
for layer in layers:
    if layer.get("kind") != "Type":
        continue
    session.execute("layer.select", {"layer": layer["id"]})   # 按 id 选，别传名字
    info = session.execute("type.info")                       # 不带 layer，读当前层
    for run in info.get("runs") or []:
        style = run.get("style") or {}
        ps = style.get("postscript_name")
        fam, sty = style.get("font_family") or "", style.get("font_style") or ""
        if ps:
            if ps.casefold() not in faces:
                missing.append((layer["name"], ps))
        elif f"{fam}-{sty}".casefold() not in faces:
            # postscript_name 为 null：新建/改过样式，或这个 face 根本解析不到
            missing.append((layer["name"], f"{fam}-{sty}" if sty else f"{fam}（face 未解析）"))
```

`missing` 非空才判缺字面；可变字体查不到时先看 faces 的 `axes`。CLI 单次场景把 `layer.select {name}` 和 `type.info` 放在同一条 `run` 里（`--cmd layer.select --params '{"name":"…"}' --cmd type.info`）。

这段循环会把活动层挪到最后一个被检查的文字层上。如果后面还要 `doc.place` / 新建层 / 依赖"活动层"的命令，核对完先显式 `layer.select` 回目标层，否则新层落点会跟着变。

**`postscript_name` 为 null 有两种成因**（实测 0.18，0.14 未复核）：会话内新建或改过样式，序列化时还没解析出字面；或者这个 face 压根解析不到（缺字体、缺字重）。实测 `font:"NoSuchFontXYZ"` 的层回 `postscript_name:null`、`font_style:""`，`type.create` 的 `warnings` 里会写 `font 'X' is not installed; text may render using a fallback face`。所以不能见到 null 就跳过——`font_style` 为空时至少记一条"face 未解析"，再配合 `type.create` / `info --compact` 的 `warnings` 交叉确认。存盘重开后 `postscript_name` 可能会补成回退字体的名字，那时候的通过也不算数。

**`type.edit`、`type.setStyle` 的 layer 参数也认 id 不认名字**：传图层名同样静默回落到活动层，会改错层。按名操作先 `layer.select {name}`，后续命令省略 layer。

## 替换的规矩

1. 缺失字体阻止交付。先列候选（同风格、同字重的已装字体），把候选交给用户选，不自动换近似字体。
2. 用户确认后用 `type.resolveMissingFonts {"map":{"旧家族":"新家族"}}` 替换，回执是 `{missing, replaced}`。
3. 记录替换：原字体、实际字体、授权、视觉差（字宽、行高变化可能让排版跑位）。
4. **禁用 `type.replaceAllMissingFonts`**：它把所有缺失字体无提示地映射到 Inter，绕过逐族确认，是有损操作。它可用，但不要用。

## PhotoCraft 从哪里找字体

- **Windows**：扫描 `%WINDIR%\Fonts` 和 `%LOCALAPPDATA%\Microsoft\Windows\Fonts`，递归（最多 8 层），只认 `.ttf`、`.otf`、`.ttc`、`.otc`；woff/woff2 不扫。
- 扫描在**进程启动时做一次**：往目录里加字体后要重启 PhotoCraft / serve 进程，运行中的会话看不到新字体。
- Windows 的 Fonts 注册表键**不读**：只把文件放进被扫描的目录就够了，不需要写注册表。
- macOS / Linux 的用户字体目录（`~/Library/Fonts`、`~/.local/share/fonts` 等）与系统字体目录同样会被扫描（这部分仅源码核对）。
- 0.10.0 没有 `--font-dir` 参数，也没有 `type.registerFonts` 命令；`PHOTOCRAFT_NO_SYSTEM_FONTS` 可以关掉扫描（主要用于测试）。

## 安装一个字体（Windows）

1. 征得用户同意（这会改动系统里所有程序可见的字体）。
2. 关闭正在用这个字体的 PhotoCraft 进程：运行中的进程占用字体文件时，覆盖同名文件会失败。
3. 把 `.ttf`/`.otf` 复制到 `%LOCALAPPDATA%\Microsoft\Windows\Fonts\`（当前用户，不需要管理员权限）。macOS 放 `~/Library/Fonts`，Linux 放 `~/.local/share/fonts`。
4. 重启 PhotoCraft / serve，用 `type.fonts` 确认家族和 PostScript 名都出现。
5. 在稿里把 `text.font` 写成 `type.fonts` 返回的家族名，不要写文件名。

## 去哪里拿字体

- 正规渠道：字体厂商官网、开源字体项目（OFL 等）、用户自己在用的授权字体管理器（如字由客户端，由用户操作授权）。
- 不抓取聚合站、不绕过登录或验证码、不把第三方 API 密钥写进脚本。自动化抓取字体站不在本技能范围内。
- 免费商用 ≠ 允许再分发或嵌入。随稿交付字体副本前，确认授权条款允许再分发/嵌入（OFL 允许随附授权文本一起分发）。
- 保留来源记录：家族名、文件名、SHA256、来源 URL、授权类型、获取日期。交付时与稿一起归档。

## 快速核对清单

- [ ] `type.resolveMissingFonts` 的 `missing` 为空，或每个替换都经用户确认并记录。
- [ ] `type.fonts` 里能看到实际使用的家族和 PostScript 名。
- [ ] 文字层实际使用的 PostScript 字面（`type.info` 的 `runs[].style.postscript_name`）都在已装列表里；`missing` 为空不代表字面没缺。
- [ ] 没有调用 `type.replaceAllMissingFonts`。
- [ ] 交付目录里的字体副本有来源与授权记录；不能再分发时在描述文件里写明原因。
