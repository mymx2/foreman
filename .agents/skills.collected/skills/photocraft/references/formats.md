# 格式与色彩

> 核对版本：photocraft-cli 0.10.0 (8407d9ccb)。

打开时按文件内容识别格式，保存时按输出扩展名选编码器（CLI 可用 `--format` 覆盖）。导出损失了什么，CLI 写在 stderr 的 `warning:` 里，serve/MCP 写在回复的 `warnings` 里；下文引号里的都是原文。quality 刻度见 cli.md。

## 分层与原生格式

| 格式 | 读 | 写 | 保留什么 | 实测要点 |
|---|---|---|---|---|
| `.psd` / `.psb` | 是 | 是 | 图层、组、蒙版、矢量蒙版、调整与填充层、智能对象、图层样式、文字、形状、路径与剪贴路径、Alpha 通道、笔记、图层复合 | 宽或高超过 30000 px 时，扩展名写 `.psd` 也会存成 PSB：`document exceeds 30000 px; written as PSB`。路径文字存成点文字，没有警告。双色调存成灰度。变量定义和数据组不保存 |
| `.pcraft` | 是 | 是 | 文档模型的全部字段（单个 ZIP 文件） | 唯一保留双色调、变量与数据组、路径文字的格式；重新打开后图层 id 不变。适合做 PhotoCraft 内部母版 |
| `.tif` 加 `--tiff-layers`（引擎命令里是 `tiffLayers:true`） | 是 | 是 | Photoshop 图层数据，文字和形状层仍可编辑，路径与剪贴路径 | 文档只有背景层时不写路径和剪贴路径，先 `layer.new.layerFromBackground`。只写一个透明通道，多余的 Alpha 通道丢弃：`2 alpha channel(s) are not written to TIFF (one transparency channel only)` |
| `.ora`（OpenRaster） | 是 | 是 | 像素层、组、混合模式、不透明度（与 Krita、GIMP、MyPaint 互通） | 丢失项逐条警告：`adjustment layers cannot be saved to OpenRaster and were left out (the merged image keeps their look)`、`layer styles are not saved to OpenRaster`、`OpenRaster has no clipping masks; these layers were saved unclipped`、`layer masks were applied to the layer pixels`、`alpha channels are not saved to OpenRaster`、`metadata (XMP, EXIF, text) is not saved to OpenRaster`；文字和形状写成像素（`type layers are saved to OpenRaster as pixels ("T")`）。CMYK、Lab 拒绝：`unsupported: OpenRaster holds RGB layers; convert the document to RGB or Grayscale first`。灰度存成 RGB：`grayscale layers are saved as RGB` |

## 扁平格式

存扁平格式时多图层文档会警告 `N layer(s) flattened; layers, masks and blend modes are not kept`。交付扁平图的同时保留一份 PSD 或 `.pcraft` 母版。

| 格式 | 位深 | 透明 | 要点 |
|---|---|---|---|
| PNG | 8 / 16 | 是 | 无损，写入 ICC、XMP、DPI。32 位文档写成 16 位：`32-bit float will be reduced to 16-bit`。调色板 PNG 重新打开是 Indexed |
| JPEG | 8 | 否 | 透明区域合到白底：`transparency composited over white for Jpeg`；高位深降到 8 位：`16-bit will be reduced to 8-bit`；每次都提示 `lossy compression`。CMYK 文档写成 CMYK JPEG |
| WebP | 8 | 是 | 不带 quality 无损，带了有损；不存 DPI：`resolution (DPI) not supported; it will be dropped`；32 位文档：`32-bit float will be reduced to 8-bit`。有损 WebP 的 Alpha 按每像素 1 字节不压缩存储，带透明的图有损反而更大，用无损 WebP 或 PNG |
| GIF | 8，256 色调色板 | 1 位 | `colours will be quantized to a 256-colour palette`；`alpha will be reduced to on/off transparency`。重新打开是 RGB。动图用 `file.export.renderVideo {"dir":…,"format":"gif"}` |
| TIFF（默认扁平） | 8 / 16 / 32 浮点 | 是 | 支持 CMYK、Lab。扁平 TIFF 丢掉额外的 Alpha 通道时不警告 |
| TGA | 8 | 是 | 有透明时写 32 位（带 Alpha），否则 24 位；`--tga-bits` / `tgaBits` 指定。PhotoCraft 自己重新打开 TGA 时不读 Alpha，得到不透明的 Background（其他软件读同一文件 Alpha 正常） |
| DPX | 8 / 10 / 12 / 16 | 是 | 8 位文档写 8，其余写 16；`--dpx-bits` / `dpxBits` 指定 |
| OpenEXR | 16 / 32 浮点 | 是 | HDR 母版，`file.automate.mergeToHdrPro {"mode":"32"}` 之后直接存 `.exr` |
| Radiance HDR | 32 浮点 | 否 | RGBE 编码，提示 `lossy compression` |
| BMP、QOI、PNM（PPM/PGM/PBM/PAM/PFM）、FITS | 视格式 | BMP、QOI 是 | 都不存 DPI |
| ICO | 8 | 是 | 最大 256×256，超过报 `unsupported: image exceeds the format maximum of 256x256` |
| PDF | — | 否 | 只写：单页、扁平，`PDF was saved flattened: layers, masks-as-editable and transparency are not preserved (#3401)`。`convert`、`run --out`、`file.saveACopy`、`doc.save` 都能写；画板逐页用 `file.export.artboardsToPdf` |

读多帧文件（动图 GIF、APNG）只导入第一帧：`only the first of 3 frames was imported`。

## 只读格式

写入时的报错（全部实测）：

| 扩展名 | 读 | 写入报错 |
|---|---|---|
| `.kra` `.krz`（Krita） | 是 | `unsupported: Krita files are import-only; save as .ora to open the layers in Krita, or .pcraft to keep everything` |
| `.pdn`（Paint.NET） | 是 | `unsupported: PDN is import-only; save as .pcraft to preserve all layers and blend modes` |
| `.af` `.afdesign` `.afphoto` `.afpub`（Affinity） | 是，不支持的部分列在 warning 里 | `unsupported: Affinity export is not implemented; save a new PSD, PNG or .pcraft copy` |
| `.dds` | 是 | `unsupported: DDS cannot be written in this build` |
| `.cin`（Cineon） | 是 | `unsupported: Cineon cannot be written in this build` |
| `.heic` `.heif` | 是（官方构建带解码器） | `unsupported: HEIF cannot be written in this build` |
| `.svg` | 是：打开为形状图层，置入为矢量智能对象 | `unknown file format: svg` |
| `.avif` | 否：`codec: Avif: decoding is not available for this format` | `unsupported: AVIF cannot be written in this build` |
| `.jxl` `.jp2` | 否 | `unknown file format: jxl` |
| `.pdf` | 否：`codec: unrecognized image format` | 可写，见上表 |

（未验证：KRA、PDN、Affinity、DDS、Cineon、HEIC 和相机 RAW 的读取没有真实样本可测，读支持来自发行版文档与写入报错的措辞。）

只读格式打开后，文档仍记着原路径（`session.list` 里能看到），但不带 path 的保存会被拒绝，见下一节。另存为 `.pcraft`（KRA 也可以存 `.ora`）。

## 保存身份与写回

适用于 serve `doc.save`、MCP `doc_save` 和桌面通道 `app.save`。CLI 的 `run --out`、`convert`、`file.saveACopy` 每次都是写一个新文件，不涉及文档身份。

1. 带 path 存成 PSD、PSB、`.pcraft`，或存成能装下全部内容的 OpenRaster：等于"另存为"。文档的 `name` 和 `path` 改成目标文件，`dirty` 变 `false`。
2. 带 path 存成扁平格式（PNG、JPEG、WebP、扁平 TIFF…），或存成装不下全部内容的 OpenRaster：只写一个副本，`name`、`path` 不变，`dirty` 保持 `true`。
3. 不带 path：只写回文档自己的 PSD、PSB、`.pcraft` 或 OpenRaster 文件，格式不变，而且必须能装下全部内容。
   - 从没保存过的新文档：`document has no path; pass \`path\``。
   - 源文件是其他格式（只读格式、PNG、JPEG…），或 OpenRaster 装不下（例如加了文字层）：`pass \`path\`: without one, only a PSD, PSB, .pcraft or OpenRaster file that holds the whole document is written back, in its own format, so \`v.svg\` was left unchanged`，OpenRaster 的情况后面还附上 `(it can't keep: …)`。原文件不动。
4. 保存不建父目录，目录不存在报 `NotFound`；已存在的同名文件直接覆盖。

## 位深与模式

- `info` / `document.inspect` 的 `mode` 取值：`Rgb` `Grayscale` `Cmyk` `Lab` `Indexed` `Bitmap` `Duotone` `Multichannel`；`depth` 是整数 8、16、32（Bitmap 报 8）。没有 `Gray` 这种写法。
- 转换命令：`image.mode.rgb` / `grayscale` / `cmyk` / `lab`（参数 `profile` `intent` `bpc`）、`image.mode.indexedColor`（会拼合图层）、`image.mode.bitmap`（`method` 如 `threshold`）、`image.mode.duotone`、`image.mode.multichannel`、`image.mode.colorTable`（可带 `table` 换表）、`image.mode.bits8` / `bits16` / `bits32`。`image.trap {width}` 只对 CMYK 文档有效。不存在 `image.mode.gray`；`file.new` 的 `mode` 才接受 `gray`。
- 前置条件（不满足时报错，原文写明要先转成什么）：

| 命令 | 要求 | 报错原文 |
|---|---|---|
| `image.mode.bitmap` | 灰度（16 位灰度也行，结果是 8 位） | `Bitmap needs a Grayscale image (Image › Mode › Grayscale first) (the document is Rgb)` |
| `image.mode.duotone` | 灰度，位深不限 | `Duotone needs a Grayscale image (Image › Mode › Grayscale first) (the document is Rgb)` |
| `image.mode.colorTable` | 索引色 | `Color Table needs an Indexed Color image (the document is Rgb)` |
| `image.trap` | CMYK | `Trap needs a CMYK document (Image › Mode › CMYK Color)` |

- 双色调只有 `.pcraft` 能保留：存 PSD 警告 `Duotone document written as Grayscale`，存扁平格式警告 `Duotone (2 inks) written as RGB`。
- GIF 重新打开是 RGB，`image.mode.colorTable` 在上面会报错；要读调色板，在导出 GIF 之前对索引色文档调用不带参数的 `image.mode.colorTable`。调色板 PNG 重新打开仍是 Indexed。
- 32 位文档存 PNG 写成 16 位，存 JPEG/WebP 降到 8 位，都有警告；TIFF 保留 32 位浮点，OpenEXR 保留浮点。
- 大幅调色和修复前先 `image.mode.bits16`，交付前再 `image.mode.bits8`，减少断层。抽查过的 10 个常用命令（油画、马赛克、高斯模糊、色阶、滤镜库、选择主体、索引色、污点修复、内容识别缩放、HDR 色调）在 16 位和 32 位下都能运行，其余命令没有逐条验证。

## 色彩管理

- 内置配置文件 id：`srgb` `display-p3` `adobe-rgb-compat` `prophoto-compat` `linear-srgb` `aces-cg` `rec2020` `gray-gamma-2.2` `sgray` `dot-gain-20-compat` `lab-d50` `coated-cmyk`，另有 `working`（工作空间），也可以传 `.icc` 文件路径。`view.proofSetup` 还接受 `working-cmyk`，`edit.assignProfile` 还接受 `none`。传错 id 时报错会列出全部内置 id：`unknown profile \`bogus\` (built-ins: srgb, …, or a path to an .icc file)`。
- 工作空间：RGB 是 sRGB IEC61966-2.1，CMYK 是 PhotoCraft Coated CMYK，Lab 是 D50。`image.mode.*` 的 `profile` 默认就是 `working`。
- `coated-cmyk` 的全名是 `PhotoCraft Coated CMYK (synthetic, 300% TAC, medium GCR)`，PhotoCraft 自己合成的通用胶印配置，不是 FOGRA 或 SWOP 标准文件。正式印刷传印厂给的 `.icc` 路径。
- `edit.convertToProfile {profile, intent, bpc}` 转换像素（`intent`：`perceptual` `relative` `saturation` `absolute`）；`edit.assignProfile {profile}` 只改标签不动像素，且配置文件的颜色模型必须和文档一致，否则报 `profile \`sGray (sRGB tone curve, PhotoCraft)\` is Gray; the document is Rgb`。
- `edit.installedProfiles` 只列操作系统里的 ICC 文件：`{dirs, profiles:[{path, description, class, colorSpace}]}`，不含内置 id。要用其中某个，把它的 `path` 传给 `profile`。
- CMYK 文档导出：JPEG 和 TIFF 保持 CMYK 并嵌入 CMYK 配置文件；PNG、WebP 只有 RGB，会经文档的配置文件转换到 sRGB 并嵌入 sRGB ICC，警告 `CMYK converted to sRGB for Png through the document's colour profile`。要一份屏幕校样，明确转 RGB 或导出 PNG。
- 转 CMYK 前量超色域：`view.gamutWarning {"on":true,"profile":"coated-cmyk"}` 在无界面模式下也返回 `{on, outOfGamut, fraction, threshold, profile}`（样图 1400×837：79,889 像素，6.8%，`threshold` 默认 ΔE 4）。占比偏高时先在 RGB 里收饱和度。
- `view.proofSetup`、`view.proofColors {on}` 在无界面模式下能设置并返回状态，但导出永远不做软打样：打开校样后导出的像素与关闭时完全相同。
- 网页交付统一转 `srgb`；`file.scripts.imageProcessor` 和 `file.export.saveForWebLegacy` 有 `convertToSrgb` 选项。

## 元数据

- `file.fileInfo` 不给参数时读取；给 `title` `author` `authorTitle` `description` `keywords` `copyright` `copyrightStatus` `copyrightUrl` 时写入 XMP。读取结果另含只读的 `camera`（来自 EXIF 的相机、镜头、曝光信息）。写入的 XMP 能随 PNG、JPEG、TIFF、WebP 导出。
- 普通导出（`convert`、`run --out`）保留 EXIF，包括 GPS 坐标；JPEG、PNG、WebP、TIFF 都实测过。
- 对外分享要去掉相机和位置信息，用 `file.export.saveForWebLegacy {"path":…,"metadata":"none"}`：EXIF 和 XMP 都去掉。默认的 `copyright` 只留一小段含版权的 XMP；`all` 保留 XMP，但 EXIF 照样丢掉。
- `file.export.saveForWebLegacy` 给 `path` 输出整张图；给 `dir` 按切片输出到 `images/` 下；只有 `html:true` 才写 HTML 页面。

## 导出选择

| 目的 | 格式 |
|---|---|
| 网页照片 | JPEG（`--quality` 80–90）或有损 WebP，先转 sRGB |
| 带透明的网页图形 | PNG 或无损 WebP |
| 社交平台发图 | JPEG，sRGB，质量 88–92 |
| 改稿母版、交给其他软件 | PSD；只在 PhotoCraft 里继续改用 `.pcraft`（保留最全） |
| 印刷，保留图层 | PSD / PSB，或分层 TIFF |
| 印刷，扁平 | CMYK TIFF（8 或 16 位） |
| 合成、VFX、HDR | OpenEXR（16/32 位浮点）或 PSD |
| 只要一个 PDF | `convert x.psd x.pdf`（单页扁平）；每个画板一页用 `file.export.artboardsToPdf` |
| 逐层、逐数据组导出 | PNG 或 JPEG |
| 去掉元数据外发 | `file.export.saveForWebLegacy {"metadata":"none"}` |
| JPEG XL、JPEG 2000、AVIF、HEIC | 写不了，换上面的格式 |
