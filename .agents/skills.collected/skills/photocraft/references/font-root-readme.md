# 字体根目录登记表（模板）

把本文件复制到字体根目录，命名为 `README.md`。`scripts/fontctl.ps1` 会读取同目录 README 的「登记表」一节；没有登记表的字体默认不安装。

## 目录结构

```text
<字体根目录>\
├── README.md            ← 本文件
├── <家族名>\
│   ├── <字体文件>.ttf
│   └── <授权文件>.txt   ← 随字体保存的授权说明（如有）
```

## 规则

1. 字体只从正规渠道获取：官方下载、字由客户端激活或明确的开源授权。
2. 每个字体文件登记来源、商用授权和（可选）SHA256；未登记的字体默认不走 fontctl 安装。
3. 授权拿不准时写「需授权」，不要写「免费商用」；fontctl 会拦截非白名单授权，确认后再用 `-Force`。
4. 字体根目录与登记表由用户维护；不要用脚本自动改写登记表。

## 登记表

字段值不要包含 `|`。

| 字体文件 | 家族名 | 样式 | 来源 | 商用授权 | 授权文件 | SHA256 | 备注 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| <家族名>/<字体文件>.ttf | <PhotoCraft type.fonts 返回的家族名> | Regular | <来源 URL 或获取方式> | 免费商用 / 需授权 / 仅限本稿 / 不可商用 | <相对路径，可空> | <Get-FileHash 值，可空> | <用途或限制> |

字段说明：

- **字体文件**：相对字体根目录的路径，例如 `站酷酷黑/站酷酷黑.ttf`。
- **家族名**：以 PhotoCraft `type.fonts` 返回的字体名为准，不是文件名。PSD 字体表常用 PostScript 名；如果两者不同，在备注里同时记录，避免 `text.font` 写入后回落。
- **样式**：`Regular`、`Bold` 等；未知留空。
- **来源**：获取渠道和地址，例如 `字由客户端激活（hellofont.cn fontid=123456）`。
- **授权文件**：包内授权说明的相对路径；没有留空。字由字体建议把详情页授权文本存成 `<家族>/版权说明.txt`。
- **SHA256**：可选；留空则安装时不校验。

## fontctl 用法

```powershell
# 默认字体根目录为 %USERPROFILE%\fonts；自定义目录用 -FontRoot 指定
powershell -NoProfile -ExecutionPolicy Bypass -File <技能目录>\scripts\fontctl.ps1 status -FontRoot <字体根目录>
powershell -NoProfile -ExecutionPolicy Bypass -File <技能目录>\scripts\fontctl.ps1 install "家族名" -FontRoot <字体根目录>
powershell -NoProfile -ExecutionPolicy Bypass -File <技能目录>\scripts\fontctl.ps1 remove "家族名" -FontRoot <字体根目录>
```

安装前先跑 `status`。如果字体已由 Windows 设置或字由客户端安装，`fontctl status` 可能显示「未安装」；先核对注册表和 `type.fonts`，不要直接 `install`/`-Overwrite`，否则可能产生重复注册表项。`remove` 只清理 fontctl 自己记账的安装，不会动别人装的字体。

`install` 把字体复制到 `%LOCALAPPDATA%\Microsoft\Windows\Fonts` 并写当前用户注册表，不需要管理员；装完要重启 PhotoCraft 才可见。登记为「不可商用」的条目拒绝安装；「需授权」等非白名单授权要 `-Force` 并会提示。

## 授权与再分发

「免费商用」只表示可用于商业产出，不代表允许把字体文件复制进交付稿或再授权。随稿交付 `fonts/` 前，确认授权明确允许再分发/嵌入；否则在描述文件中记录家族名、授权凭证和获取方式，并写明未随附原因。OFL 字体要随副本附 OFL.txt；字由字体的授权以详情页和客户端条款为准。
