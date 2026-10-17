# 抠图、切图与资产导出

通用的「从图里取东西」流程：抠主体、裁掉无用边、按规格导出资产。三类任务不要混：

| 任务 | 解决什么 | 不解决什么 |
| --- | --- | --- |
| 语义抠图 | 主体与背景分离，产出蒙版/alpha | 不负责裁边、尺寸、命名 |
| 内容裁切 | 去掉透明/纯色/手动边界外的空白，加 padding | 不负责主体语义 |
| 资产切图/导出 | 按图层、组或区域输出文件，命名/倍率/格式 | 不保证抠图边缘质量 |

先问清目标用途、背景类型、边缘类型、输出规格，再选工具；所有尺寸、边距、倍率、颜色、命名都来自用户 spec。本文的数值只是起点，不是固定规则。

## 输入契约

记录并确认：

- 目标：主体类型（衣物、画作、产品、人物、图标等）与用途（网页、印刷、合成、归档）。
- 背景：透明、纯色、渐变、复杂照片；是否保留投影/倒影。
- 边缘：硬边、软边（毛发/布料毛边/烟雾）、半透明（纱/玻璃/水）、纸边/画框。
- 输出：格式、倍率、目标尺寸或最大边长、padding、命名模板、是否要 alpha、色彩配置。
- 画作/纸本：明确要「画心」还是「含纸边」；纸边/米白留白算不算资产内容。
- 投影/倒影/配件：并入资产还是分开；默认分开并记录，不静默合并。
- 限制：原稿是否可改、是否需要保留可编辑蒙版、是否允许重采样。

原稿只读：先记 SHA256，只写 `<稿名>_切图.psd` 或独立工作目录；结束复核原稿 hash 未变。纯位图任务直接用 `trim-export.py`，不需要 PhotoCraft 会话。

## 语义抠图

1. 保留原图，复制工作层；用选区/蒙版，不擦像素。
2. 边缘策略按类型选：
   - **硬边**（产品、画框、纸张）：精确选区/路径，羽化从 0–1px 起，按 100% 预览调；不要用大羽化糊掉结构。
   - **软边**（衣物毛边、毛发、烟雾）：选区后反向羽化/边缘细化，检查 alpha 过渡；不要用全局锐化压边。
   - **半透明**（纱、玻璃、水）：保留 alpha/透明度，不要二值化；在浅色、深色、棋盘格三种背景上检查。
   - **投影/倒影**：默认与主体分开；是否合并进资产由用户决定，不要静默烘焙。
3. 衣物：注意布料褶皱、蕾丝/网纱、毛边和阴影；不要把衣服和投影一起切成一团，也不要把袖口/下摆切掉。
4. 画作：区分画心内容、纸边/画框、投影和空白留白；保留印章/签名/题跋；透视校正只在用户要求时做。
5. `document.inspect` 复核蒙版/组/图层可见性；导出前在三种背景上看边缘。

## 内容裁切

- 内容边界优先从 alpha 求 bbox；没有 alpha 时用纯色背景 + 容差，或手动 bbox。
- 纯色背景的容差要可调；不要默认写死白色或某个固定阈值。JPEG 压缩噪声可能把 bbox 撑大，必要时提高容差、改手动 bbox，或改用带 alpha 的 PNG。
- `--padding` 由用途决定（0 到需要的留白）；四边可不同。padding 是额外画布，不得切进内容。
- 画作按 spec 处理：默认保留纸边、题跋、印章、签名；只有 spec 明确要「画心」时才裁纸边。不要用 bg trim 去猜纸边与淡墨的边界。
- 衣物/产品按主体边界裁；是否包含投影、吊牌、配件要写明。
- 裁切后检查四条边没有残留空白行/列，也没有切到主体；保持用户要求的比例/锚点。

## 从 PSD 取位图

- `doc.render` 渲染的是整幅 composite，不是单层；默认 `maxSide=1024`，上限 2048px/5MiB，源文档上限 67,108,864 px。0.9.0 实测 3000×1000 源用 `maxSide:0` 会报 `automation preview side exceeds 2048 pixels`；全尺寸只在最长边 ≤2048 时可用。需要全尺寸且落盘时显式 `{index?, maxSide:0, path:"<渲染图>.png"}`；不带 `path` 只回 base64。超过 2048 用 `convert`、分组渲染或分块。
- `doc.exportLayers` 在 0.9.0 实测可用：`{dir:"<输出目录>"}` 会导出顶层图层/组，组导成一个合成 PNG（测试 2 个顶层对象 → 2 个文件），不是逐叶导出；要逐叶就隔离/隐藏或改用 `convert`。`serve --help`/`methods` 不一定列全，按运行时实测；仅 headless，参数/命名 build-dependent。GUI 不能调 `doc.*`，先 `app.save` checkpoint 再转 headless。
- 只取一个资产时，先隐藏兄弟层/不透明底，或用组/层 bbox、手动 bbox 隔离；组节点 bounds 可能为 null，用其可见子层 bounds 并集或选区 bounds，并 clamp 到画布；层 bounds 可能为负。不要用 `layer.exportAs` 的 ambient 路径。
- bbox 必须量在**实际要 trim 的那张位图**上；如果先在 1024 预览上量、再换全尺寸渲染，按 `fullW/renderW` 换算或重新量。manifest 记下源位图和 PSD 来源，便于回溯。

## 资产切图/导出

- 源：已渲染位图。纯位图任务不需要 PhotoCraft；PSD 图层先用能力域方法 `doc.render` / `doc.exportLayers` 导出，不用带 ambient 路径的 `layer.exportAs`。`trim-export.py` 只做几何裁切/背景色去边，不产语义 alpha；没有 alpha 又需要透明时，必须先在 PhotoCraft 做蒙版并导出 RGBA，不能拿 `trim bg` 冒充抠图。
- 命名：模板占位符 `{name}`、`{scale}`、`{ext}`、`{index}`、`{w}`、`{h}`；具体模式由用户给，不写死资产名。
- 倍率：按用户 spec；默认 1x。倍率列表含非 1 值时，所有输出默认都带 `@{scale}x`（包括 1x），避免重名。
- 格式：有 alpha 用 PNG/WebP；不透明照片可用 JPEG；JPEG 不支持 alpha，源有 alpha 或要 padding 时必须给背景色或改用支持 alpha 的格式。
- 重采样：先缩放内容，再加 padding；padding 区不会被重采样污染。缩小时用高质量重采样；放大前确认源分辨率足够；manifest 记 `upscaled`，不默认放大。
- padding 按源像素计，输出侧按倍率记录在 `paddingOut`；manifest 同时记 `padding` 和 `paddingOut`。
- EXIF orientation 会先应用再导出，方向信息不保留；manifest 记 `exifTransposed`。
- 输出目录独立于原图；不允许输出覆盖任何输入、manifest 或锁文件。manifest 默认 `<out>/assets-manifest.json`，默认合并已有记录并保留 `runs` 历史；已有文件必须是 `trim-export.py` 的有效 manifest，写锁 + 唯一临时文件 + 原子替换，锁覆盖整个运行，多个进程不会写坏。`--manifest-mode replace` 替换旧记录（可用于重建坏 manifest），`--prune` 清理本机可达但已不存在的旧条目；跨盘不可达路径会保留并告警。
- manifest 记录完整参数、bbox/box 与 `bboxSpace`、`sourceSize`/`orientedSize`、`outputSize`、`padding`/`paddingOut`、倍率、`sourceHasAlpha`/`sourceTransparentRatio`/`sourceAlphaBBox`/`sourceAlphaBBoxSpace`、`alpha`/`contentTransparentRatio`/`paddingOnlyAlpha`、`alphaBBox`/`alphaBBoxSpace`、`contentAlphaBBox`/`contentAlphaBBoxSpace`、`geometryOnly`、`semanticCutout`、`sourceDocument`/`note`、哈希与 `runs`。没有 alpha 时 `sourceTransparentRatio`/`contentTransparentRatio` 记 0.0，`sourceHasAlpha=false`；`geometryOnly=true`/`semanticCutout=false` 表示只做几何裁切。`path`/`source` 用 `/` 且相对 manifest；跨盘时记绝对路径并带 `Absolute` 标记。
- `contentTransparentRatio` 是裁剪/缩放后内容区的比例，硬边抠图裁掉透明边后通常为 0；判断是否抠图看 `sourceHasAlpha` + `sourceTransparentRatio`（或真实蒙版），不要单看 content 比例。`sourceTransparentRatio`/`contentTransparentRatio` 统计 alpha<255 的占比（含半透明），不只是 alpha=0；没有 alpha 时记 0.0。`paddingOnlyAlpha=true` 只说明最终透明区只来自 padding，不能单独否定一个本来有源 alpha 的抠图。
- 交付时把 manifest 放在 assets 的父目录，用 `--manifest` 指定；写完后不要移动。manifest 里的 `source` 是输入位图，纯位图任务要先把渲染源图放进稿目录再跑，别指向临时目录；PSD 来源用 `--source-document` 记录，画心/纸边/投影决策用 `--note` 记录。
- 图层/组导出按索引或稳定标识选层，不按可能重复的名字。

## 验收

- **抠图**：有 alpha/蒙版；主体覆盖完整；100% 下浅色/深色/棋盘格都无白边、halo、锯齿墙；半透明和投影没有被误二值化。判断语义抠图看 `sourceHasAlpha` 与 `sourceTransparentRatio`（或真实蒙版），不能只看 trim 后的 `contentTransparentRatio`；后者为 0 是硬边裁剪的正常结果。`paddingOnlyAlpha=true` 只说明最终透明只来自 padding，若源本来有 alpha，仍可成立。`alphaBBox` 是输出像素坐标，应与主体相符；圆角/软边在 2x 后仍应干净，padding 内 alpha 应为 0。
- **裁切**：bbox 正确；padding 与 spec 一致；四边没有整行/整列纯背景残留；主体/印章/签名/纸边策略符合 spec；比例和锚点符合要求。矩形裁切不等于语义抠图。
- **导出**：文件数、命名、尺寸、倍率、格式、alpha 与 spec 一致；`assets-manifest.json` 的路径/哈希/bbox/参数可对账；没有覆盖任何输入；关键资产可重跑。
- **整体**：合成/整幅用 `psd-compare.py` 复核；资产要先贴回原画布再比整幅。单资产再人工看边缘，像素一致不能代替 alpha 边缘检查。

## 参数化工具

`scripts/trim-export.py`（运行它）只处理已渲染位图，参数全部显式：

```bash
python scripts/trim-export.py <输入...> --out <输出目录> \
  --trim none|alpha|bg|bbox \
  --bg-color <#RRGGBB> --tolerance <0-255> --alpha-threshold <0-255> \
  --bbox <x,y,w,h> --padding <N|L,T,R,B> \
  --scales <1,2> --format auto|png|webp|jpeg --quality <1-100> \
  --name-pattern "<模板含 {ext}>" --background <#RRGGBB> \
  --source-document "<PSD/源稿>" --note "<画心/纸边/投影>" \
  --manifest <稿目录>/assets-manifest.json [--manifest-mode merge|replace] [--prune] \
  [--overwrite] [--recursive]
```

- 退出码：0 = 全部成功；1 = partial/全部失败（看 `failures`）；2 = 参数/锁/manifest 配置错误。成功验收要求 `failures` 为空。重跑已有输出要加 `--overwrite`。
- 命名模板必须含 `{ext}`；16-bit/浮点源会 fail closed，先转 8-bit。`--manifest` 相对路径按当前工作目录解析，建议在稿目录运行或用绝对路径。manifest 写入后不要移动。
- `--trim` 默认 `none`，裁边必须显式选择；`--alpha-threshold` 默认 8（alpha≤8 会被裁掉，软边可调低或 0），`--quality` 默认 92。`trim bg` 遇到透明像素会拒绝，改用 alpha。没有默认资产名、固定尺寸、固定倍率或固定背景色，默认值只是起点。输入是目录时可用 `--recursive`，目录内的输出目录文件会被跳过；显式输入允许位于输出目录，但任何输出都不会覆盖输入/manifest/锁。多倍率时命名模板必须含 `{scale}`；倍率列表含非 1 值时，所有输出默认带 `@{scale}x`。
- 没有 alpha 又要透明时，先在 PhotoCraft 做蒙版并导出 RGBA，不能拿矩形裁切冒充抠图。art 纸边、framed 外投影按 `--note`/spec 决策。

## 例外

- 源是平图/合并层：只能按视觉重建边缘，记录“复刻自平图”。
- 背景不是纯色：用 alpha 或手动 bbox，不要用固定颜色硬抠。
- 没有 alpha 又要透明：先做语义抠图，不能只靠背景色裁切。
- 画心是米白/白色纸本：`trim bg` 只能去掉纯白卡纸，不能安全区分纸边与淡墨；用 alpha、手动 bbox，或明确接受纸边。
- 主体与投影/配件的关系不明：先出候选方案让用户选，不静默合并。
- 用户只要裁边不要抠图：用 `--trim bbox/bg` 或 PhotoCraft 裁剪，不强行生成 alpha；矩形裁切不要标成“背景已去除”。
