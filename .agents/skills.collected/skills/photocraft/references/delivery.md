# 分层稿交付资料

交付单元是一个目录，不是单个 PSD。字体只装在系统、说明只留在会话里，换机或重开项目后就得重新找字体、重新量版式。分层稿旁边必须带齐它自己需要的资料。

## 交付单元布局

```text
<稿目录>/
├── <稿名>.psd / .psb / .pcraft    分层母版（规范稿可命名 <稿名>_规范.psd）
├── <稿名>.md                       描述文件（模板见下）
├── <稿名>.png                      交付平图（按需）
├── fonts/                          （授权允许再分发/嵌入时）
│   └── <家族名>/
│       ├── <字体文件>.ttf|otf
│       └── <授权文件>.txt          OFL / LICENSE 等随包授权
├── audit-before.json               规范化前结构审计（规范化任务）
├── audit-after.json                规范化后结构审计（规范化任务）
├── audit-compare.json              原稿→规范稿结构对比（规范化任务）
├── visual-diff.json                视觉对比报告（规范化任务）
├── assets/                         切图/资产导出（按需）
├── assets-manifest.json            资产清单（按需）
└── psd-compare-out/                验证产物（可选，留证用）
```

`fonts/` 只放该稿实际用到的家族，不整库拷贝。多份稿共用字体时，每份稿各自带副本，交付目录可独立搬走。只有授权明确允许再分发/嵌入时才放字体文件；仅“免费商用”不构成再分发许可。不能复制时，在描述文件记录家族名、授权凭证与获取方式，并写明未随附原因。

## 字体：一处缓存，副本随稿

- 字体获取一次后放用户目录 `fonts\`（`%USERPROFILE%\fonts`）做缓存，后续稿子优先复用现成文件，不重复下载；用户指定了别的位置以用户为准，缓存只是推荐约定。
- 字体根目录有 README 登记表时，来源、商用授权、SHA256 记在登记表里；没走登记表的，至少保留字体包来源 URL、授权文件和 SHA256，和描述文件放在一起。
- 稿内 `fonts/` 的副本用完整字体文件，不用网页字体切片（woff2 分片）；副本 SHA256 必须与来源记录一致。
- 只装系统不带副本的稿子，在换机、重装或交付给他人后会发生字体回落与文字重排；授权允许再分发时必须带副本。授权不允许时，描述文件记录家族名、授权凭证和获取方式，并声明接收方需自行取得授权。

核对命令（execute）：

```bash
sha256sum "<稿目录>/fonts/<家族名>/<字体文件>"
# 与来源记录（字体库登记表或字体包记录）中的 SHA256 比对
```

## 字体依赖检查

描述文件里的字体依赖表以稿内真实记录为准，不以设计备注或记忆为准。

- 家族名：`document.inspect` 的文字层 `text.font`，或 `type.fonts` 的已装清单。
- PSD 字体表记录的 PostScript 名/字重：`psd_tools` 可用时逐层读；不可用时至少在 `type.fonts` 核对家族存在，并在描述文件注明「字重未逐层核验」。

```python
# execute；需要 psd_tools，缺失时跳过并在描述文件注明
from psd_tools import PSDImage

psd = PSDImage.open("<稿名>.psd")
for layer in psd.descendants():
    if layer.kind == "type":
        # font_names 只返回 PostScript 名；家族/字重读 typesetting.fonts
        for font in layer.typesetting.fonts:
            print(layer.name, font.family, font.style, font.postscript_name)
```

字体表记录的字重与本机实际可用的字重不一致时（例如记录 Regular/Bold、系统只装了 Medium），在描述文件写明实际渲染使用的字重和用其他软件打开时的回落行为，不要只写家族名。

## 描述文件模板

按稿填写，未知项写「未验证」，不要省略。

````markdown
# <稿名>.psd 说明

## 文件信息

| 项 | 值 |
|---|---|
| 文件 | <稿名>.psd |
| 用途 | ... |
| 画布 | 宽×高，色彩模式，位深 |
| 大小 | 字节 |
| MD5 | ... |
| 图层数 | ... |
| 基准稿 | ...（若有） |

## 切图/资产导出（按需）

交付含切片/抠图资产时，单独放 `assets/` 并附根级 `assets-manifest.json`；命名、倍率、格式、padding 按用户 spec，不写死。trim 的源位图要放进稿目录再用，不能指向临时目录；验收与边缘检查见 `references/cutout-slicing.md`；不要覆盖原图或母版。

```bash
python "<技能目录>/scripts/trim-export.py" "<源位图或目录>" --out assets \
  --manifest assets-manifest.json --trim <none|alpha|bg|bbox> \
  --bg-color <#RRGGBB> --bbox <x,y,w,h> --alpha-threshold <0-255> \
  --padding <N|L,T,R,B> --scales <1,2> --format <auto|png|webp|jpeg> --quality <1-100> \
  --background <#RRGGBB> --name-pattern "<模板含 {ext}>" \
  --source-document "<PSD/源稿>" --note "<画心/纸边/投影>" \
  [--manifest-mode merge|replace] [--prune] [--overwrite]
```

`--bg-color`/`--bbox`/`--background` 按模式补；脚本默认 `trim none`、manifest 合并已有记录；manifest 默认写在 `--out` 内，交付时用上面的 `--manifest assets-manifest.json`（相对当前稿目录）放到资产根目录，写完不要移动。多倍率时命名模板必须含 `{scale}`；成功交付要求 manifest 的 `failures` 为空。描述文件里同时记录画心/含纸边、投影/配件和命名/倍率 spec。

## 规范化记录

规范化/复刻任务填写；非规范化稿件写「不适用」。

| 项 | 值 |
|---|---|
| 原稿 | 文件名 + SHA256 |
| 原稿审计 | audit-before.json 摘要（层/组/深度/CRITICAL/HIGH 数） |
| 规范稿 | 文件名 + SHA256 |
| 规范稿审计 | audit-after.json 摘要 |
| 分组/命名 | 六类根组（参考/调整/装饰/文字/主体/背景）+ `类别_语义[_状态]`；未用类别与例外在此说明 |
| 旧层→新组 | 映射表或映射文件路径 |
| 字体替换 | 原字体 → 实际字体、理由、授权与视觉差 |
| 视觉对比 | psd-compare 结果、diff 图、fuzz 与原因 |
| 未解决项 | 无法恢复的层、已知差异、用户待决 |

## 目录结构

（目录树，标出字体副本与验证产物）

## 图层结构

（树形，标出组、文字层、形状层、智能对象、可变量）

## 文字规格

（逐层：字体、字号、字距、颜色、bounds、抗锯齿、kerning、transform）

## 字体依赖

| 图层 | 家族名 | PSD 字体表记录 | fonts/ 文件 | 商用授权 |
|---|---|---|---|---|

（字重不一致、回落行为、字体安装/注册方式写在这里）

## 可变量

（变量图层与替换方式；PS 原生变量失效时说明改走编程合成）

## 验证

（对齐基准、MAD/差异像素、残差来源、复验命令、产物路径）

## 已知限制

（容器比例、横竖版、未持久化项等）

## 校验与渲染

（MD5、convert、一致性校验命令）

规范化任务用以下命令落盘报告：

```bash
python "<技能目录>/scripts/psd-audit.py" audit "<规范稿>" --strict --json > audit-after.json
python "<技能目录>/scripts/psd-audit.py" compare "<原稿>" "<规范稿>" --strict --json > audit-compare.json
python "<技能目录>/scripts/psd-compare.py" "<原稿渲染>" "<规范稿渲染>" --out psd-compare-out > visual-diff.json
```

## 素材与授权

（字体授权、图片素材来源、发布前需确认的事项）
````

## 交付自检

- [ ] 每份分层稿有同名 `.md`，模板字段无省略
- [ ] 授权允许再分发时，`fonts/` 覆盖稿内全部字体家族且没有多余家族；不允许时已写明未随附原因
- [ ] 每个字体文件的 SHA256 与来源记录一致
- [ ] 字体来源、商用授权与再分发/嵌入许可可追溯；不允许再分发的字体未随附且已写明原因
- [ ] 描述文件里的 MD5、验证数据和复验命令可复跑
- [ ] 平图与母版同版本
- [ ] 规范化任务含原稿/规范稿 SHA256、audit-before/after、audit-compare、visual-diff 与旧层→新组映射
- [ ] 规范稿 `psd-audit.py --strict` 无 CRITICAL/HIGH/MEDIUM，LOW 已逐条说明
- [ ] `type.resolveMissingFonts` 无缺失，`type.fonts` 能看到交付所需字体
- [ ] 切图任务：`assets/` 与 `assets-manifest.json` 的命名/尺寸/倍率/格式/alpha 与 spec 对账
