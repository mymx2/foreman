# 相机 RAW 开发

> 核对版本：photocraft-cli 0.14.0 (ff4738810)。格式支持来自 `crates/raw`、`docs/file-format-parity.md` 的 Camera raw 表；Camera Raw 交互见 `docs/control-protocol.md`。RAW 图库管理（Lightroom 式目录、XMP sidecar、批量挑选）仍不在范围内；这里只讲单张/批量的 RAW 显影与自动化。

## 支持范围

| 相机格式 | 读取 | 说明 |
|---|---|---|
| DNG | 是 | 含 LJPEG、lossy JPEG、JPEG XL 瓦片；按存储样本做 BlackLevel/WhiteLevel/LinearizationTable |
| Canon CR2 | 是 | |
| Canon CR3 | 检测到但不支持 | 会回退内嵌预览 |
| Nikon NEF/NRW | 是 | 无损/有损；“lossy after split” 不支持；D4/D5100 等有图像区域与色彩拟合验证 |
| Sony ARW/SR2/SRF | 是 | 含压缩 |
| Panasonic RW2、Pentax PEF | 是 | |
| Olympus ORF | 仅未压缩 | |
| Fujifilm RAF | 仅未压缩 | 无富士色彩校准 |
| 其他（CRW、3FR、IIQ、X3F、SRW、MRW、ERF…） | 只读内嵌预览 | 不是传感器数据，别当完整显影 |

RAW 由 magic 识别，不只是扩展名。打开后得到 **16 位 RGB、ProPhoto 兼容工作空间** 的 “Background” 图层；不支持或有问题的 RAW 用相机内嵌 JPEG 预览回退，并带 warning。

## 打开路径

- CLI：`run`、`convert`、`info`、`batch` 都可以直接吃 RAW（例如 `photocraft-cli info shot.nef --compact`、`convert shot.nef shot.tif`）。
- serve/MCP：`doc.open` / `doc_open`（只传 `path`）。
- 桌面：`app.open`（不弹 Camera Raw 对话框）。
- 交互式 File › Open / 拖入 / 最近文件：如果该 RAW 是从传感器数据开发的，会先弹 “Camera Raw (name)” 对话框，Open 才真正打开，Cancel 关闭文档。

自动化打开**不会**弹 Camera Raw 对话框；CLI/serve/MCP 用默认 AHD 去马赛克、300 ppi（可被 `rawDefaults.resolution` 改）、16 位 ProPhoto 兼容色彩空间、不自动影调。桌面交互式打开按 `rawDefaults`，可以选择先弹 Camera Raw。

## Camera Raw 对话框与智能滤镜

- 桌面控制通道可以用 `ui.menu.invoke {"id":"filter.cameraRaw","params":{}}` 在活动 RGB/灰度像素层上打开；`params.ui` 可设 `set`（滤镜参数）、`before`、`scope`、`view`、`commit`、`cancel`。打开 RAW 时还可带 `demosaic`（`ahd`/`mhc`/`bilinear`）。
- 已打开 RAW 的 dialog 状态在 `ui.inspect.cameraRaw`：`openingRaw:{name,path,demosaic}`；提交后重新显影并派发一次 `filter.cameraRaw`。
- `filter.cameraRaw` 也可直接作为引擎命令用在普通 RGB/灰度层上；参数包括 `temperature` `tint` `exposure` `contrast` `highlights` `shadows` `clarity` `dehaze` `vibrance` `saturation` 等。`identity:true` 表示没有产生变化。
- 对智能对象使用滤镜后成为智能滤镜；PSD 的 Camera Raw 智能滤镜只映射已验证的 WB/Light/Curves/HSL/Detail 等子集，其余设置可能无法在 PhotoCraft 里完整还原。双击智能滤镜可重新打开 Camera Raw。

## 改去马赛克/分辨率/打开方式

这些是**打开时**的 `rawDefaults` 首选项。0.14 的导入管线实际接入的是 `resolution`（CLI/serve/MCP 也生效）、`demosaic`/`openInCameraRaw`（只影响交互式/桌面打开），输出固定为 **16 位 ProPhoto RGB**。`bitDepth`、`colorSpace`、`sharpenFor`、`openAsSmartObject`、`applyAutoTone` 这些键在首选项里存在，但在 0.14 的导入路径里没有生效；不要向用户承诺改它们会改变 RAW 的位深或色彩空间。

| 首选项 | 值 | 0.14 是否影响导入 |
|---|---|---|
| `rawDefaults.resolution` | 1..10000（默认 300） | 是；CLI/serve/MCP 也应用，影响文档 ppi，不重采样传感器数据 |
| `rawDefaults.demosaic` | `ahd`（默认）/`mhc`/`bilinear` | 只影响交互式/桌面打开；CLI/serve/MCP 的 `doc.open` 固定 AHD，没有按调用传 demosaic 的参数 |
| `rawDefaults.openInCameraRaw` | bool（默认 true） | 只影响交互式打开是否先弹 Camera Raw |
| `rawDefaults.bitDepth` / `colorSpace` / `sharpenFor` / `openAsSmartObject` / `applyAutoTone` | — | 0.14 未接入导入路径；输出仍 16 位 ProPhoto |

自动化里要改 `resolution`，可以在 **打开之前** 执行 `prefs.set`（serve/MCP 的 `engine.execute`），或使用带临时配置目录的桌面实例。`demosaic` 在 CLI/serve/MCP 里没有 per-open 参数；要换只能在桌面的交互式 Camera Raw/Preferences 里选，或接受默认 AHD。CLI `run` 是先打开文件再执行命令，改 `rawDefaults` 对当前文件已经太晚。`prefs.set` 属于需要用户同意的操作。Camera Raw 对话框里的 `demosaic` 只对当前这次打开有效，且在提交时重新显影。

## 常用流水线

```sh
# 先看文档：位深、模式、warnings、EXIF
photocraft-cli info shot.nef --compact

# 单张：显影 + 镜头校正 + 转 8 位 sRGB JPEG（母版另存 TIFF/PSD）
photocraft-cli run shot.nef \
  --cmd filter.lensCorrection --params '{"distortion":-8,"vignetteAmount":15}' \
  --cmd edit.convertToProfile --params '{"profile":"srgb","intent":"relative"}' \
  --cmd image.mode.bits8 \
  --out shot.jpg

# 保留 16 位的交付母版
photocraft-cli convert shot.nef shot.tif
```

- 修图顺序：RAW 显影 → 镜头/透视 → 降噪/锐化 → 局部调整 → 转交付色彩空间 → 位深/格式。重滤镜尽量在 16 位里做，最后再降 8 位。
- 批量：CLI `batch` 可以按同一动作处理目录；要命名模板/递归用 `file.automate.batch`。RAW 的打开成本高，先小样本验证再跑全量。
- 网页/社交交付：`edit.convertToProfile {"profile":"srgb"}` + `image.mode.bits8`，再存 JPEG/PNG/WebP；不要直接把 ProPhoto 16 位当网页图。
- 印刷/归档：分层 TIFF 或 PSD/PSB 保留 16 位；HDR 合成用 OpenEXR。
- 元数据：普通导出保留 EXIF（含 GPS）。对外分享前用 `file.export.saveForWebLegacy {"metadata":"none"}` 去掉 EXIF/XMP；`file.fileInfo` 可读相机/镜头/曝光。

## 不能做/限制

- 没有 RAW 图库、星级/旗标、非破坏性目录、XMP sidecar 同步、相机/镜头配置文件库；这些不要承诺。
- CR3、压缩 RAF、部分 NEF 变体只能回退预览；不是所有相机都能拿到传感器级结果。
- Camera Raw 的蒙版作者、完整 Adobe 色彩渲染、所有 PSD Camera Raw 设置尚未完整支持；PSD 智能滤镜只映射已验证子集。
- 没有生成式填充/超分辨率；`select.subject` 等是经典算法。
- Camera Raw 对话框是桌面独立窗口；主窗口截图 `ui.screenshot` 拍不到它，最小化/遮挡时还会超时。

## 验收

- `info` 的 `mode` 应为 `Rgb`、`depth` 为 16（默认）；`warnings` 里若出现 preview fallback，说明没用上传感器数据，不能声称完整显影。
- 取样高光/阴影/肤色，确认没有明显偏色；ProPhoto→sRGB 后检查高光和饱和色是否被裁切。
- 与相机内嵌 JPEG 或参考显影对比（构图、色彩、边缘）；不要只看“文件生成了”。
- 批量抽查首张/中间/末张，失败文件逐个列出，不以“命令退出 0”代替。
