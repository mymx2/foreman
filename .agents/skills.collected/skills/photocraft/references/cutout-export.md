# 抠图、裁边与资产导出

> 核对版本：命令 id 与参数按 photocraft-cli 0.14.0 (ff4738810) 复核；行为记录来自 0.10.0–0.14.0 的实测，0.14 未逐条重验的条目保留原文。

三类任务分开做，各自验收：

| 任务 | 产出 | 不负责 |
| --- | --- | --- |
| 语义抠图 | 主体与背景分离的蒙版或 alpha | 裁边、尺寸、命名 |
| 内容裁边 | 去掉透明、纯色或指定框外的空白，加 padding | 主体语义 |
| 资产导出 | 按层、组或区域出文件，带命名、倍率、格式 | 抠图边缘质量 |

尺寸、边距、倍率、颜色、命名都来自用户 spec，本文的数值只是起点。

## 1. 输入契约

动手前逐项记下并和用户确认：

- 主体与用途：衣物、画作、产品、人物、图标；网页、印刷、合成、归档。
- 背景：透明、纯色、渐变、复杂照片。
- 边缘：硬边、软边（毛发、布料毛边、烟雾）、半透明（纱、玻璃、水）、纸边或画框。
- 输出：格式、倍率、目标尺寸或最长边、padding、命名模板、要不要 alpha、色彩配置。
- 画作与纸本：要「画心」还是「含纸边」。
- 投影、倒影、配件：并入资产还是分开。默认分开并记录，不静默合并。
- 限制：原稿能不能改、要不要保留可编辑蒙版、允不允许重采样。

原稿只读：开工前记 SHA256，只写 `<稿名>_切图.psd` 或独立目录，结束时复核 hash 未变。纯位图任务直接用 `trim_export.py`（执行，第 5 节），不需要 PhotoCraft 会话。

## 2. 语义抠图

| 做法 | 命令 | 要点 |
| --- | --- | --- |
| 选主体，直接转蒙版 | `select.subject` → `layer.layerMask.revealSelection` | `select.subject` 之后不要再反选，否则蒙版保留背景、遮掉主体 |
| 选背景，反选，转蒙版 | 选背景 → `select.inverse` → `layer.layerMask.revealSelection` | 先说清选区里是主体还是背景 |
| 一步加蒙版 | `layer.removeBackground {refine}` | 忽略已有选区；Background 会变成普通层 `Layer 0` 并带蒙版 |
| 边缘细化 | `select.refineEdge {radius, smartRadius, decontaminate, output:"layerMask"}` | 在 Background 上执行时回报 `output:"newLayerWithMask"`：新建带蒙版的 `Background copy`，原层隐藏，选区被用掉 |
| 去白边、黑边 | `layer.matting.removeWhiteMatte` / `layer.matting.removeBlackMatte` | 只改边缘颜色，alpha 不变 |
| 收窄杂边 | `layer.matting.defringe {width}` | alpha 不变 |
| 去背景色污染 | `layer.matting.colorDecontaminate {amount, radius}` | 重新着色边缘，alpha 不变 |

`layer.layerMask.revealSelection` 会用掉选区。四个 `layer.matting.*` 都改像素、回 `null`：先复制工作层或留历史快照，做完回到三种底色上复核，不要拿它们代替精确蒙版。

| 边缘类型 | 做法 |
| --- | --- |
| 硬边（产品、画框、纸张） | 精确选区或路径，羽化从 0–1 px 起，按 100% 预览调 |
| 软边（毛发、布料毛边、烟雾） | `select.refineEdge` 细化后看 alpha 过渡，不要用全局锐化压边 |
| 半透明（纱、玻璃、水） | 保留 alpha，不二值化 |
| 投影、倒影 | 默认与主体分开 |

- 衣物：注意褶皱、蕾丝网纱、毛边和阴影；袖口、下摆不能切掉，衣服和投影不切成一团。
- 画作：区分画心、纸边或画框、投影和留白；保留印章、签名、题跋；透视校正只在用户要求时做。
- `select.subject` 会漏掉主体里和背景接近的部分（实测漏掉了人像下方的白色针织衣，留下一块透明缺口）。导出前用 `document.inspect` 确认 `hasMask`，并在浅色、深色、棋盘格三种底上 100% 看完整个主体。

## 3. 内容裁边

- bbox 优先从 alpha 求；没有 alpha 时用纯色背景加容差，或手动 bbox。
- bbox 要量在实际要裁的那张位图上。在 1024 预览上量过、再换全尺寸渲染时，按 `全尺寸宽 / 预览宽` 换算或重量。
- `image.trim {"basedOn":"transparent"}` 只去掉整行、整列完全透明的边。全景拼接的透明锯齿边会留下来，导出 JPEG 时透明区合成到白底（警告 `transparency composited over white for Jpeg`），变成白条。处理：裁到内接矩形，或拼接时用 `file.automate.photomerge {contentAwareFill:true}` 补边。
- 白底产品图先裁到主体再缩放：`layer.removeBackground` → `image.trim {"basedOn":"transparent"}` → `file.automate.fitImage`。漏掉 trim 时 `fitImage` 量的是整张画布，实测主体长边只有 769–959 px（2000 px 方图的 38–48%）。
- padding 由用途决定，四边可以不同；padding 是额外画布，不能切进内容。
- 画作默认保留纸边、题跋、印章、签名，spec 明确要画心才裁纸边。米白或白色纸本靠背景色裁不出纸边与淡墨的边界。
- 衣物、产品按主体边界裁，是否包含投影、吊牌、配件写进 `--note`。
- 裁完检查四边没有整行、整列的残留背景，也没有切到主体；比例和锚点符合要求。

## 4. 从 PSD 取位图：各出口在哪能用

GUI 控制通道和 serve/MCP 拒绝会碰本机任意路径的命令：`file.*` 前缀除少数安全命令外按名字整类拒绝（不存在的 `file.bogusX` 也得到同样报错），`layer.exportAs` 这类带 `path` 参数的命令按参数拒绝。报错 ``automation command `…` uses ambient filesystem paths and is disabled; use capability-scoped document methods``。CLI `run` 是本机信任环境，这些命令都能用，也不受根目录限制。

| 出口 | CLI | serve / MCP | GUI 控制通道 | 产物 |
| --- | --- | --- | --- | --- |
| `photocraft-cli convert <稿> <out>` | 可用，没有 2048 上限 | — | — | 整幅平图，格式看扩展名 |
| `doc.render {index?, maxSide?, path?}` | — | serve 方法；MCP `doc_render_preview` / `render_preview` 只回图像，不落盘 | 没有 `doc.*` | 整幅，恒为 PNG |
| `doc.exportLayers {dir, prefix?, format?, visibleOnly?, quality?, index?}` | — | serve 方法；MCP `doc_export_layers`（参数 `visible_only`） | 没有 | 顶层层/组，画布尺寸 |
| `doc.save {path}` / MCP `doc_save`、`doc_export` | — | 可用，格式看扩展名 | `app.save {path}`（见 automation.md） | 整幅或分层文件 |
| `file.generate.imageAssets` | 可用 | 拒绝 | 拒绝 | 按层名规格，裁到层像素 |
| `file.export.layersToFiles` 及其他 `file.export.*` | 可用 | 拒绝 | 拒绝 | 顶层层，`<prefix>_<NNNN>_<层名>.<ext>` |
| `layer.exportAs {path}` / `layer.quickExportAsPng {path}` | 可用 | 拒绝 | 拒绝 | 单层 |
| `file.package` | 可用 | 拒绝 | 拒绝 | 稿件加链接素材，见 psd-workflow.md |

### doc.render

- 默认 `maxSide` 1024（1200×800 → 1024×683），小图不放大。`maxSide` 最大 2048；`maxSide:0` 只在源最长边 ≤ 2048 时等于全尺寸，否则报 `automation preview side exceeds 2048 pixels`。
- PNG 超过 5 MiB 报 `automation PNG exceeds 5242880 bytes`；源图超过 67,108,864 像素报 `automation preview source exceeds 67108864 pixels`。
- 恒为 PNG：`path` 写 `.jpg`、`.webp` 得到的也是 PNG 字节。要别的格式用 `doc.save` 或 CLI `convert`。
- 不给 `path` 回 `{mime, base64}`；`path` 的父目录必须已存在（否则 `NotFound`）；根目录外的绝对路径被拒。
- 没有图层或区域参数：只要一层就先隐藏其他层，或在副本上裁剪；超过 2048 用 CLI `convert`。
- 全尺寸渲染与 `convert` 输出逐像素一致。

### doc.exportLayers

- 只导出顶层可见层和组；组合成一张；每张都是画布尺寸。
- 命名 `<prefix 或文档名>_<四位序号>_<层名>.<ext>`，序号从 `0000` 起；回执 `{files, count}`。
- 顶层调整层跳过但占序号（文件名出现缺号）；隐藏层默认跳过，不占序号；`visibleOnly:false` 连隐藏层一起导出。
- serve 方法要写 `visibleOnly`，写成 `visible_only` 会被静默忽略；MCP `doc_export_layers` 反过来只认 `visible_only`。
- 没有取子集的参数，`layers:[…]` 被静默忽略。只要某一层或组时先隐藏其他顶层。
- 目标文件已存在时报 `AlreadyExists`，这次调用已写出的文件会被删掉；缺的子目录会自动创建。

### Image Assets（`file.generate.imageAssets`，只在 CLI）

```bash
photocraft-cli run "<稿名>_切图.psd" --cmd file.generate.imageAssets \
  --params '{"on":true,"dir":"<资产目录>"}'
```

| 层名 | 输出 |
| --- | --- |
| `logo.png` | `logo.png`，裁到层像素 |
| `50% small/logo.gif` | `small/logo.gif`，缩到 50% |
| `logo.jpg80%` | `logo.jpg`，质量 80 |
| `48x48 icons/a.png8` | `icons/a.png`，48×48 调色板 PNG |
| `btn.png, 200% btn@2x.png` | 逗号分隔的多个规格各出一个文件 |

- 名字里没有合法图片扩展名的层（`logo`、`notes.txt`）跳过，调整层跳过；隐藏层照样导出（`doc.exportLayers` 默认不导隐藏层）。
- 任意一个名为 `default …` 的层（不限于组）给出整套变体规格，自身不导出（源码确认）。
- 同名冲突时层序靠上的保留，其余进 `errors`（`another layer already writes this file`）。
- 回执 `{dir, enabled, files, errors}`。不传 `on` 是开关切换；开启后每次保存都会重导到 `<文档名>-assets`（源码确认，未实测）。
- 规格名含 `%`、`/`、扩展名，和命名 profile 冲突（`psd_audit.py`（执行）报 `NODE_PREFIX_MISMATCH` / `NAME_HAS_PATH_CHAR`）。规范稿保持 profile 命名，在 `<稿名>_切图.psd` 副本上改成规格名再导。

### file.export.layersToFiles（只在 CLI）

只导顶层（组的子层不单独出文件，空组也会出一个文件）；层名本身以 `.png` 结尾时得到双扩展名（`main_0001_hidden.png.png`）；CLI 重跑直接覆盖旧文件。

## 5. trim_export.py（执行）

只处理已经渲染好的位图（PNG/WebP/JPEG/TIFF），不读 PSD 图层。参数都要显式给：

```bash
python "<skill-dir>/scripts/trim_export.py" <位图或目录...> --out <输出目录> \
  --trim alpha --padding 16 --scales 1,2 \
  --manifest "<稿目录>/assets-manifest.json" \
  --source-document "<稿名>.psd" --note "画心，不含纸边；投影分开"
```

| 参数 | 含义与默认值 |
| --- | --- |
| `--trim none\|alpha\|bg\|bbox` | 默认 `none`，不裁。`alpha` 要求有 alpha；`bg` 遇到透明像素拒绝；`bbox` 配 `--bbox x,y,w,h` |
| `--alpha-threshold` | 默认 8：alpha ≤ 8 算透明。软边可调低或设 0 |
| `--bg-color` / `--tolerance` | 只给 `--trim bg` 用，没有默认背景色。容差默认 8（任一 RGB 通道差 > 8 算内容），适合引擎渲染的 PNG；JPEG 或带噪背景调高，合成纯色图可以 0 |
| `--padding N\|L,T,R,B` | 默认 0，按源像素；先缩放内容再补 padding，padding 区不被重采样 |
| `--scales 1,2` | 默认 1；放大时报告里有警告，先确认源分辨率够 |
| `--format auto\|png\|webp\|jpeg` / `--quality` | `auto` 跟随源扩展名（TIFF 输出 PNG）；质量默认 92。JPEG 没有 alpha：源有 alpha 或要 padding 时必须给 `--background #RRGGBB` |
| `--name-pattern` | 占位符 `{name} {scale} {ext} {index} {w} {h}`；必须含 `{ext}`，它自带前导点（写 `{name}@{scale}x{ext}`；写成 `{name}@{scale}x.{ext}` 会得到 `alpha@1x..png` 并被拒）。倍率含非 1 值时必须含 `{scale}`，默认模板此时自动变成 `{name}@{scale}x{ext}` |
| `--overwrite` | 默认不覆盖已有输出；任何情况下都不覆盖输入、manifest 和锁文件 |
| `--recursive` | 子目录里的文件全部写进同一个 `--out`，同名文件报「输出重名」 |
| `--manifest` / `--manifest-mode merge\|replace` / `--prune` | 默认 `<out>/assets-manifest.json`、合并旧记录并保留 `runs`；`replace` 重建；`--prune` 去掉已不存在的旧条目。相对路径按当前目录解析，写完不要移动 |
| `--source-document` / `--note` | 记来源稿件和画心、纸边、投影等决定 |

16-bit 和浮点源直接失败（Pillow 会把 16-bit PNG 静默读成 8-bit，脚本查文件头拦下），先转 8-bit；EXIF 方向先应用再导出，manifest 里记 `exifTransposed`。整个运行持有 manifest 锁，多个进程并发写不会写坏。

manifest 里所有框都是 `[x, y, w, h]`，字段名写明坐标系（文件顶层 `boxConvention` 也写了一遍）：

| 字段 | 含义 |
| --- | --- |
| `trimBoxXYWH` | 裁剪框，EXIF 校正后的源图像素 |
| `sourceAlphaBoxXYWH` | 源图 alpha > 0 的范围，同上坐标系 |
| `contentAlphaBoxXYWH` | 缩放后、补 padding 前的内容图像素 |
| `outputAlphaBoxXYWH` | 输出图像素 |
| `sourceHasAlpha` / `sourceTransparentRatio` | 裁剪前的源图有没有 alpha、alpha < 255 的占比 |
| `contentTransparentRatio` | 裁剪后内容区的占比，硬边裁完通常为 0 |
| `paddingOnlyAlpha` | 输出的透明只来自 padding |
| `geometryOnly` / `semanticCutout` | 恒为 `true` / `false`：本工具只做几何裁切 |
| `padding` / `paddingOut` / `scale` / `outputSize` / `sourceSha256` / `outputSha256` | 对账用 |

旧版 `trim-export.py` 写的 manifest 可以合并进来，旧条目保留旧字段名；要统一就用 `--manifest-mode replace` 重跑。

退出码：0 全部成功；1 有文件失败（看 stdout JSON 的 `failures`）；2 参数、锁、manifest 错误或缺 Pillow。验收要求 `failures` 为空。

## 6. 验收

- 抠图：有 alpha 或蒙版；主体完整；100% 下浅色、深色、棋盘格三种底上没有白边、halo、锯齿；半透明和投影没有被二值化。判断是不是真抠过，看 `sourceHasAlpha` + `sourceTransparentRatio` 或真实蒙版；`contentTransparentRatio` 为 0 是硬边裁完的正常结果；`paddingOnlyAlpha=true` 只说明输出的透明来自 padding，源图本来有 alpha 时抠图仍然成立。
- 裁边：bbox、padding 与 spec 一致；四边没有整行、整列的残留背景；主体、印章、签名、纸边的取舍符合 spec。取样点放在主体边缘旁边：四角落在 padding 里，永远是纯色，查不出问题。
- 导出：文件数、命名、尺寸、倍率、格式、alpha 与 spec 一致；manifest `failures` 为空，路径、哈希、框能和实际文件对上；没有覆盖任何输入；Image Assets 回执 `errors` 为空、`files` 数量与层名规格一致。
- 整幅：资产贴回原画布后用 `psd_compare.py`（执行，用法见 psd-workflow.md）比整幅；像素一致代替不了逐个资产的边缘检查。

## 7. 例外

- 源是平图或合并层：只能按视觉重建边缘，记录「复刻自平图」。
- 背景不是纯色：用 alpha 或手动 bbox，不用固定颜色硬裁。
- 没有 alpha 又要透明：先在 PhotoCraft 做语义抠图并导出 RGBA；`--trim bg` 不产生 alpha。
- 米白或白色纸本画心：背景色裁不出纸边与淡墨的边界，用 alpha、手动 bbox，或明确接受纸边。
- 主体与投影、配件关系不明：出候选让用户选。
- 用户只要裁边不要抠图：用 `--trim bbox`/`--trim bg` 或 `image.crop`，结果不要标成「背景已去除」。
