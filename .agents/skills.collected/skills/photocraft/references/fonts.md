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
- `psd_audit.py --installed-fonts` 接受 `type.fonts` 的输出，会从每个条目里收集 `family`、`postscriptName`、`postscript_name`。

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
- [ ] 没有调用 `type.replaceAllMissingFonts`。
- [ ] 交付目录里的字体副本有来源与授权记录；不能再分发时在描述文件里写明原因。
