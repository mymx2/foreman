# 0.12 → 0.14 变更与升级检查

> 用途：技能文档的基线核对。0.12.0 = 924 条命令；0.14.0 = 935 条（本机 ff4738810 实测）。这里只收会影响自动化写法或验收的变化，不替代上游 release notes。

## 命令与参数

| 变化 | 影响 |
|---|---|
| 新增 `layer.layerStyle.contours.list/new/delete/load/save` | 用户轮廓库；`.shc` 可 `load`/`save`；自动化里 `path` 被拒，用 `data`（base64） |
| 新增 `layer.xmpMetadata` | 读写/删除图层 XMP；`rawData` 是完整 XML 包；`inspect` 的 `hasXmp` 可验证 |
| 新增 `tools.firstBrush/lastBrush/nextBrush/previousBrush`、`layer.layerStyle.innerGlow`、`layerComp.reorder` | 画笔导航、内发光、图层复合排序 |
| `file.new` 增 `profile` | 新建时打 ICC 标签；自动化里传路径可能被 ambient 规则拒绝，内置 id/`working` 可用 |
| `document.activate` 增 `offset`，回执改为 `{document}` | 动作里切换相邻标签用 `offset`；越界报错，不回绕 |
| `layer.translate` 增 `selection` | 移动图层时把选区一起移动，同一历史步 |
| `channel.options` 支持 `"mask"` | Layer Mask Display Options（rubylith 颜色/不透明度），不产生历史步 |
| `file.saveACopy` 增 `jpegFormat`、`tiffCompression`、DDS 选项 | 仍保留 `overwrite`；它只控制“替换文档自己的文件”，其他同名文件本来就覆盖 |
| `file.automate.batch`、`file.export.layersToFiles` 增 `jpegFormat`/`tiffCompression`/DDS | 批量导出也能设这些格式选项 |
| `image.applyDataSet` 的路径检查收紧 | 0.14 起读像素替换路径按 ambient 规则判定；serve/MCP 里旧“可读根外图片”的缺口已关闭，不要再按旧警告设计 |

## 格式

| 变化 | 说明 |
|---|---|
| XCF 读取 | `.xcf/.xcf.gz`，图层/组/蒙版/通道/选区，8/16-bit，32-bit int→16、float→32；文字/矢量像素化；只读 |
| DICOM、Amiga IFF 读取 | 只读；DICOM 含患者信息，分享前处理 |
| Cineon 可写 | 10-bit log 灰度/RGB；`formats.md` 旧版“不能写”已过时 |
| DPX/DDS | DPX 8/10/12/16 位；DDS 可读顶层 mip、可写 BC1–BC3/mipmap |
| JPEG 扫描格式 | CLI `--jpeg-format baseline\|optimized\|progressive`；`file.saveACopy` 的 `jpegFormat` |
| TIFF 压缩 | CLI `--tiff-compression none\|lzw\|zip`；引擎命令的 `tiffCompression` |
| PSB 自动切换 | 超过 30000 px 或估算编码 >2 GB 时写 PSB；旧版 `formats.md` 只写了 30000 px |
| `.pcraft` | 可以是单个 ZIP，也可以是目录 bundle；保存/打开的两者都以实际文档 path 为准 |
| 双色调 | 0.14 实测 PSD 重开仍显示 `mode:Duotone`；完全可编辑母版仍优先 `.pcraft` |
| TGA Alpha | 重新打开时导入为 “Alpha 1” 通道，不自动变成图层透明；要透明需自己转蒙版/选区 |
| 只读格式 path | Affinity 明确“没有源保存路径”；KRA 实测 `path:null`；不要假设只读格式都能不带 path 回写，保存前看 `info`/`session.list` |
| RAW 默认值 | 输出固定 16 位 ProPhoto；0.14 导入路径实际接入 `rawDefaults.resolution`（headless 也生效），`demosaic`/`openInCameraRaw` 只影响交互式/桌面打开；`bitDepth`/`colorSpace`/`sharpenFor` 等键存在但未接入，别向用户承诺 |

## 自动化入口

| 变化 | 影响 |
|---|---|
| 打印命令可用 | `file.print`、`file.printOneCopy`、`file.printers`、`file.print.printers`、`file.print.page`；只在 CLI 可用，可 `output` PDF |
| `doc.save`/MCP `quality` 严格 1..100 | 0/500 直接报错，不再“静默截断”；引擎导出命令仍是 0..12 静默截断 |
| 桌面 `app.save` 参数扩展 | `quality` 0..12、`jpegFormat`、`ddsCompression`、`ddsMipmaps`；没有 `dpxBits/tiffLayers/format/index` |
| bridge 保存限制 | `doc_save`/`doc_export` 只透传 `path/tgaBits/dds*`；`format/quality/tiffLayers/dpxBits/index` 报 `need headless mode` |
| `ui.gpu.simulateLoss` 增 `destroy` | 真销毁窗口 GPU，保存 Recovery 后关闭应用；只用于测试，不要在生产会话里试 |
| Camera Raw | 交互式打开 RAW 才有对话框；自动化打开固定 AHD（`rawDefaults.resolution` 可调），交互式按 `rawDefaults` 的 `demosaic`/`openInCameraRaw`；`openingRaw.demosaic` 可读；`filter.cameraRaw` 可作智能滤镜 |
| MCP | 2026-07-28 请求可使用，但 initialize 仍回 2025-11-25；list/read 可能带 `resultType/ttlMs/cacheScope`；1 MiB 超限仍会杀进程 |

## 升级后要重跑

1. `python <skill-dir>/scripts/check_docs.py`：确认文档里的命令 id、参数、方法名与已安装注册表一致（0.14 基线 935 条、18 serve 方法、29 桌面方法、25 MCP 工具）。
2. `PHOTOCRAFT_CLI=<路径> python <skill-dir>/scripts/run_examples.py`：本技能 41 个案例在 0.14.0 上实测 40 PASS、0 FAIL、1 SKIP（案例 31 需要窗口）。
3. `python <skill-dir>/scripts/probe_gotchas.py`：逐条复核 Gotchas 的实测项；运行结果与文档冲突时以运行结果为准并改文档。
4. 若新增命令/格式，在 `references/commands.md`、`formats.md` 和本文件各补一行，再跑 `check_docs.py`。

## 仍在范围外/仍不完整

- 生成式 AI、Photoshop 原生插件（`.8BF`/CEP/UXP）、RAW 图库/XMP sidecar、PDF 读取、多页 PDF、AVIF 解码、JPEG XL、Camera Raw 全部蒙版/校准功能。
- Web/WASM 只有 UI，没有 CLI/serve/MCP/控制通道；不要承诺自动化。
- 打印的实际出纸、色彩管理和每台打印机驱动仍要按环境验收。
