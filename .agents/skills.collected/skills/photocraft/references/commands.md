# 命令速查

> 核对版本：命令 id 与参数按 photocraft-cli 0.12.0 (6a2d027ee) 复核；行为描述写于 0.10.0 (8407d9ccb)。参数以运行时注册表为准。

## 怎么查

- 注册表是唯一的权威：0.12.0 有 924 条命令，CLI、serve、MCP、桌面控制通道共用同一份。本文只列常用的，参数以已安装版本的注册表为准。
- 查参数：（执行）`python <skill-dir>/scripts/params.py --exact <id>`；不知道 id 时传关键词（`curves`、`blur`）；也可以 `photocraft-cli commands --json --filter <关键词>`。参数文本的读法、哪些命令校验未知键、拼错的枚举会怎样，见 cli.md。
- 同一条命令在各入口的写法：`run --cmd <id> --params '<json>'`；serve `engine.execute {"command":"<id>","params":{…}}`；MCP `command_run {"id":"<id>","params":{…}}`；动作步骤 `["<id>", {…}]`。哪个入口能用哪些命令见 automation.md。
- "案例"列是 `examples/` 里的脚本编号；32–39 是新增场景。

## 回执形状

区域有两种写法，混用会把位置算飞：

| 写法 | 出现在 |
|---|---|
| `[x,y,w,h]` | `document.inspect`、`photocraft-cli info`、`layer.list` 的 `bounds` 与 `selectionBounds`；`shape.create` / `shape.edit` / `shape.info` 的 `bounds`；`select.subject`、`select.sky` 的 `bounds`；`edit.copy`；`paint.*` 的 `damage`；`image.detectFaces` 的 `rect`；`slice.*` 的 `rect`；`layer.new.artboard` / `layer.artboard.addBeside` 的 `rect`；`layer.new.frame` 的 `frame` |
| `[x0,y0,x1,y1]` | `type.create` / `type.info` 的 `bounds`；`type.createSelection`；`view.newGuidesFromShape`；`file.placeEmbedded` 的 `bounds` |
| 输入 `[x,y,w,h]` | `type.create {box}`、`shape.create {rect}`、`select.object {rect}`、`layer.new.artboard {rect}`、`slice.new {rect}`、`shape.presets.place {rect}` |
| 输入 `[x0,y0,x1,y1]` | `edit.transform`、`select.transformSelection`、`path.transform` 的 `rect`；`pattern.presets.new {rect}` |
| 输入分开的 `x` `y` `width` `height` | `select.rect`、`layer.new.frame` |

- `inspect` / `info` / `layer.list` 的 `bounds` 是像素实际覆盖的范围（文字层是字形墨迹，比文字框小），并且裁在画布之内：完全移出画布的层报 `[0,0,0,0]`，空像素层在 `layer.list` 里是 `null`。文字框本身的位置从 `type.info` 读，见 text-layout.md。
- `paint.*` 的 `damage` 不裁到画布，可能有负数。
- 回 `null` 的命令：`image.adjustments.*`、`select.rect` / `select.all` / `select.deselect`、`edit.stroke`、`layer.setProps`、`layer.renameLayer`、`document.activate`、`view.newGuide`、`path.fill`、`layer.matting.*`、`filter.render.clouds` / `filter.render.differenceClouds`、`image.applyImage`、`tools.swapColors` / `tools.defaultColors`、`layer.arrange.reverse`。`edit.undo` / `edit.redo` / `edit.toggleLastState` 回 `true`。`null` 既不代表失败也不代表生效，用 `document.inspect` 或像素取样核对。
- 多数滤镜回 `{filter:{filter:<名字>, …参数}, layer}`；`filter.liquify`、`filter.cameraRaw`、`filter.lensCorrection` 各有自己的形状（见下文滤镜表）。新建图层类命令回 `{layer:<新 id>}`，新建文档类命令回 `{document:<索引>}`。

## 单位

| 量 | 规则 |
|---|---|
| 不透明度 0..1 | `layer.setProps {opacity, fill}`、`layer.new.layer {opacity}`、`paint.stroke`、`paint.pencil`、`layer.smartFilter.blendingOptions` |
| 不透明度 0..100 | `layer.layerStyle.*`、`layer.layerStyle.blendingOptions {opacity, fillOpacity}`、`edit.fill`、`edit.stroke`、`edit.fade`、`path.fill`、`path.stroke`、`shape.create` 的 `stroke.opacity`、`channel.new`、`image.applyImage`、`image.calculations` |
| 不透明度 1..100 | 修饰类笔刷 `paint.spotHealing`、`paint.healingBrush`、`paint.cloneStamp`、`paint.dodge`、`paint.burn`、`paint.sponge`、`paint.blur`、`paint.sharpen`、`paint.smudge`、`paint.historyBrush`，以及 `paint.bucket`、`paint.gradient` |
| 读回 | 按 0..100 写入的值在 `document.inspect` 里读回 0..1：`channel.new {opacity:40}` → `0.4`，`layer.layerStyle.blendingOptions {opacity:50}` → `0.5` |
| 笔刷硬度、流量 | `paint.stroke` 的 `hardness`、`flow` 是 0..1，`spacing` 0..10；修饰类笔刷 `hardness` 0..100、`flow` 1..100；`path.stroke` 的 `hardness` 0..1 而 `opacity` 0..100 |
| 越界 | 静默截断，不报错：`paint.stroke {opacity:50}` 画成完全不透明，`paint.dodge {opacity:0.5}` 几乎没有效果 |
| 字号、行距 | pt；像素 = pt × ppi / 72（72 ppi 下 1 pt = 1 px，300 ppi 下约 4.17 px） |
| 百分比 | `image.imageSize {percent}`、`edit.transform {scaleX, scaleY}`、`file.placeEmbedded {scale}`、`edit.contentAwareScale {scaleX, scaleY}`、`select.transformSelection {scaleX, scaleY}` |
| 颜色 | 输入 `"#rrggbb"`；`document.pixel` / `document.sampleColor` 回 0..1 的 `[r,g,b,a]`；`view.colorSamplers.add` 回 0..255 的 `rgb` 和 0..100 的 `cmyk` |

## 文档、画布与核对

| 命令 | 关键参数 | 回执 / 注意 | 案例 |
|---|---|---|---|
| `file.new` | `width` `height` `mode`（`rgb`/`gray`/`cmyk`/`lab`）`depth` `background`（`white`/`transparent`/`#rrggbb`…）`resolution` `name` | `{document}`，新文档成为活动文档；未知键报错；`run --new` 就是它 | 13 16 39 |
| `file.close` | `document` | 不提示，直接丢弃未保存的修改；不给 `document` 关活动文档 | — |
| `image.duplicate` | `name` `mergedOnly` | `{document}`，副本成为活动文档 | 18 |
| `document.activate` | `document`（索引；写成 `index` 报 `missing \`document\``） | `null` | 19 20 27 |
| `document.inspect` / `layer.list` | `document`；`layer.list {flat:true}` | inspect 含 `history` `hasSelection` `selectionBounds` `snapshots`；`flat` 时每层一行，带 `depth` `parent` | 01 13 16 |
| `session.inspect` | — | `{active, documents}`，所有打开的文档 | — |
| `document.pixel` | `x` `y` | 合成后的 `[r,g,b,a]`（0..1），没有 `sampleLayer` 参数 | 07 08 10 |
| `document.sampleColor` | `x` `y` `size`（1/3/5/11/31/51/101）`sampleLayer`（`current`/`currentAndBelow`/`all`，默认 `all`） | `[r,g,b,a]`；`size` 取方块平均；`current` 读活动层，`currentAndBelow` 读活动层及其下方 | 03 09 10 |
| `view.colorSamplers.add` / `view.colorSamplers.list` / `move` / `delete` / `clear` | `x` `y`；`index` `x` `y` | `{count, index, point:{rgb, cmyk, position…}}`；每个文档最多 10 个 | 11 |
| `image.imageSize` | `width` `height` `percent` `resolution` `keepPrintSize` `resample`（缩小 `bicubicSharper`，放大 `preserveDetails`，只改 ppi 用 `none`） | `{width,height}`；只给一边时保持比例 | 02 06 |
| `image.canvasSize` | `width` `height` `relative` `anchor` `extensionColor`（可为 `transparent`） | `{width,height,offset}`；`offset` 是原内容在新画布里的位移 | 03 06 23 39 |
| `image.crop` | `x` `y` `width` `height` `angle` `targetWidth` `targetHeight` `resample` `contentAware` `deleteCroppedPixels` | `targetWidth`、`targetHeight` 必须同时给，裁完精确缩放到该尺寸；拉直时 `angle` 与 `image.rotation.arbitrary {direction:"cw"}` 的倾斜角同号（顺时针歪了 3° 就传 `angle:3`） | 04 20 |
| `image.perspectiveCrop` | `corners`（左上起顺时针四点）`width` `height` `resolution` | 文字、形状、填充、智能对象层会被栅格化 | 23 |
| `image.trim` | `basedOn`（`transparent`/`topLeft`/`bottomRight`）`top` `bottom` `left` `right` | 只裁掉完全透明（或与角点同色）的整行整列 | 12 22 35 |
| `image.rotation.arbitrary` | `angle` `direction`（`cw`/`ccw`）`interpolation` | 画布自动放大，回新尺寸 | 20 |
| `image.imageRotation.90cw` / `90ccw` / `180` / `flipCanvasHorizontal` / `flipCanvasVertical` | — | 整张画布 | 18 |
| `edit.transform` | `layer` `rect` `quad` `matrix` `scaleX` `scaleY` `rotate` `dx` `dy` `interpolation` `target` | 默认框是图层内容与选区的交集，缩放旋转绕框中心；只给 `rect` 报错；画布不变 | 20 23 |
| `file.automate.fitImage` | `width` `height` `dontEnlarge` `resample` | 按整个画面适配，不看主体占多大 | 03 14 26 |
| `image.revealAll` | — | 画布扩到包住所有像素；回 `{changed}` | — |
| `image.detectFaces` | `minScore`（默认 0.5）`sampleAllLayers` | `{faces:[{score, rect, landmarks}]}`，得分高的在前；`rightEye` 是画面左边那只；没检出时 `faces` 为空 | 04 08 10 |
| `file.fileInfo` | `title` `author` `copyright` `keywords` `description` | 不给参数为读取；元数据规则见 formats.md | 05 06 |
| `history.newSnapshot` / `history.selectSnapshot` | `name` `from`；`snapshot` | `{snapshot, name}`；快照 id 从 1 起，和历史状态索引是两套 | 29 |
| `history.selectState` / `history.deleteState` | `state`（0 = 最早） | `deleteState` 删掉该状态和它之后的全部状态；最早的状态删不掉 | — |
| `history.newDocument` | `state` `name` | 把某个历史状态复制成新文档并激活 | — |
| `edit.undo` / `edit.redo` | — | 回 `true`；能撤销的步数由首选项 `performance.historyStates`（默认 50）决定 | 29 |
| `document.presets.save` / `document.presets.get` | `name` `settings` | `get` 回可以直接传给 `file.new` 的 `params` | 29 |
| `prefs.get` / `prefs.set` | `path`（驼峰写法，如 `general.alwaysCreateSmartObjectsWhenPlacing`）`value` | 写成下划线报 `unknown preference`；CLI 里 `prefs.set` 不写回首选项文件 | 29 |

## 图层

| 命令 | 关键参数 | 回执 / 注意 | 案例 |
|---|---|---|---|
| `layer.select` | `layer`（id 或图层名）`name` `occurrence` `mode`（`replace`/`add`/`remove`/`toggle`/`range`） | 没有数组参数，多选逐个 `mode:"add"`；同名层用 `occurrence`（0 起，按文档遍历顺序） | 12 13 38 |
| `layer.setProps` | `layer` `layers` `name` `visible` `opacity` `fill` `blend` `clipped` `locked` `locks` | `blend` 不分大小写（`Multiply` / `multiply`），拼错报错 | 07 08 |
| `layer.new.layer` | `name` `position`（`above`/`below`）`mode` `opacity` `clipToPrevious` `fillNeutral` | `{layer}`；`below` 也到不了 Background 下面 | 08 17 |
| `layer.duplicate` | `layer` `name` `document`（`"new"` 复制到新文档）`inPlace` | `{layer}`；副本在源层正上方；不给 `layer` 时复制所有选中层 | 08 23 |
| `layer.delete` | `layer` | 文档至少要留一层 | — |
| `layer.renameLayer` | `layer` `name` | 没有 `layer.rename`（不是引擎命令）；改名用 `layer.renameLayer` 或 `layer.setProps {name}` | 07 13 34 |
| `layer.new.layerFromBackground` / `layer.new.backgroundFromLayer` | `ifPresent` `select`；`layer` | 背景层转普通层（加蒙版、写带路径的分层 TIFF 之前要做）；反过来要求文档里还没有 Background | 17 23 |
| `layer.moveTo` | `layer` 或 `layers` `target` `position`（`above`/`below`/`into`）`copy` | 改层序和父级，不改坐标；`into` 放到已有组的最上面 | 34 |
| `layer.groupLayers` / `layer.new.groupFromLayers` | `layer` `name` | `{layer}`，把选中层包进一个新组 | 13 16 34 |
| `layer.translate` | `layer` `dx` `dy` `units`（`px`/`pt`）`target` | 只有相对位移，没有 `x`、`y`；不给 `layer` 时移动所有选中层 | 14 33 |
| `layer.arrange.bringToFront` / `sendToBack` / `bringForward` / `sendBackward` / `reverse` | `layer` | 有 Background 时 `sendToBack` 报 `layer can't move further`；`reverse` 要选中两层以上 | 03 17 |
| `layer.align.leftEdges` / `horizontalCenters` / `rightEdges` / `topEdges` / `verticalCenters` / `bottomEdges` | `to`（`auto`/`layers`/`selection`/`canvas`） | `{moved}`，作用于选中层；`auto` 有选区时对齐选区，没有时单层对齐画布、多层对齐它们的合并范围 | 13 14 32 38 |
| `layer.distribute.leftEdges` / `horizontalCenters` / `horizontally` / `verticalCenters` …（共 8 个） | — | 要选中三层以上 | 33 |
| `layer.mergeDown` / `layer.mergeLayers` / `layer.flattenImage` / `layer.stampVisible` | `layer`；—；—；— | 向下合并保留下层的名字；`stampVisible` 在活动层上方新建盖印层，原层保留 | 03 08 23 |
| `layer.hideLayers` / `layer.showLayers` | `layer` | 校验未知键 | 24 |
| `layer.linkLayers` / `layer.selectLinkedLayers` | — | `linkLayers` 是开关，选中层已是一组时取消链接 | — |
| `layer.copyToDocument` | `document` `layers` `center` `at` `offset` | 复制到另一个已打开的文档 | — |
| `layer.pickAt` / `select.findLayers` | `x` `y` `list`；`name`（不分大小写的子串） | 按位置或名字找层 | — |

### 栅格化

把可编辑载体烘成像素，不可回改。先留底：`layer.duplicate {document:"new"}` 复制到新文档，或 serve 里存快照。

| 命令 | 作用对象 | 回执 | 报错原文 |
|---|---|---|---|
| `layer.rasterize.layer` | 文字、形状、填充、智能对象 | `{layer, layers:[…]}` | 像素层、组：`the layer has nothing to rasterize` |
| `layer.rasterize.allLayers` | 所有可栅格化层，含组内 | `{rasterized:N}` | 不报错；全像素的文档回 `{"rasterized":0}` |
| `layer.rasterize.type` / `type.rasterize` / `type.rasterizeTypeLayer` | 文字层 | 前者 `{layer, layers:[…]}`，后两者 `{layer}` | 三条各不相同：`the layer is not a type layer` / `layer N is not a type layer` / `… the active layer is not a type layer` |
| `layer.rasterize.shape` / `shape.rasterize` | 形状层 | 两者都回 `{layer}` | `shape.rasterize` 对文字层：`layer N is not a shape layer` |
| `layer.rasterize.fillContent` | 填充层 | `{layer, layers:[…]}` | `the layer is not a fill layer` |
| `layer.rasterize.smartObject` / `layer.smartObjects.rasterize` | 智能对象 | `{layer, layers:[…]}`，id 会变 | `the layer is not a smart layer` |
| `layer.rasterize.layerStyle` | 有图层效果的层：文字、形状、填充、像素、智能对象 | `{layer, layers:[…]}` | 组：`no selected layer has layer effects to rasterize`（组的效果会渲染，但烘不了） |
| `layer.rasterize.vectorMask` | 带矢量蒙版的层 | 成功路径未验证 | `layer has no vector mask` |
| `layer.rasterize.video` / `layer.videoLayers.rasterize` | 视频层 | `{}` | — |

- 智能对象栅格化会换 id（实测 7→6，内容文档消失后整层重排），后续按旧 id 的步骤会打空；重新 `document.inspect` 或按名字寻址。
- 组不能整组栅格化（`layer.rasterize.layer` 对组报 `the layer has nothing to rasterize`）；`allLayers` 会进组处理子层，组结构保留。组上的图层效果会渲染，但 `layerStyle` 同样拒绝组。
- `layer.rasterize.layer` 与 `fillContent` 保留图层蒙版（栅格化后 `hasMask` 仍为 true）；`layerStyle` 把效果、填充不透明度和蒙版一起烘进像素。
- 形状层的路径就是它的矢量蒙版：`layer.vectorMask.revealAll` 对它报 `a shape layer's path is already its vector mask`。转像素用 `shape.rasterize` 或 `layer.rasterize.layer`，不要用 `rasterize.vectorMask`。
- 单层命令遇到不适用的对象是硬错误，整条 `run` 的后续步骤和 `--out` 都不执行；批量一律用 `allLayers`。
- 验收：`info --compact` 里该层 `kind` 变成 `Pixel`；`allLayers` 看 `rasterized` 计数，重复执行回 0。

## 蒙版、调整图层、填充图层

| 命令 | 关键参数 | 回执 / 注意 | 案例 |
|---|---|---|---|
| `layer.layerMask.revealSelection` / `hideSelection` / `revealAll` / `hideAll` | `layer` | 由选区生成的蒙版会用掉选区 | 08 36 |
| `layer.layerMask.edit` | `density` `feather` | 至少给一项 | — |
| `layer.layerMask.apply` / `fromTransparency` / `delete` | `layer` | 智能对象上 `apply` 被拒，先栅格化 | — |
| `layer.vectorMask.fromPath` | `layer` `name` | 形状层自带矢量蒙版，再加报错 | 17 |
| `layer.createClippingMask` / `layer.releaseClippingMask` | `layer` | 剪贴到下一层 | 12 |
| `layer.newAdjustmentLayer.<kind>` | 与同名 `image.adjustments.<kind>` 相同，另加 `path` | 有 16 种：blackWhite brightnessContrast channelMixer colorBalance colorLookup curves exposure gradientMap hueSaturation invert levels photoFilter posterize selectiveColor threshold vibrance。建层时有选区就用选区做蒙版（选区外为黑），选区本身留给后面的命令；`hasMask` 恒为 `true` | 07 12 29 |
| `layer.setAdjustment` | `layer` + 该调整的参数，`eyedropper` | 参数合并到现有值；什么都不给就恢复默认 | 07 |
| `layer.newFillLayer.solidColor` / `gradient` / `pattern` | `color`；`from` `to`（两个颜色）`angle` `style` `reverse`；`pattern` `scale` `angle` | 渐变 `angle:90` 时 `from` 在下、`to` 在上；有选区时选区成为蒙版 | 03 17 |
| `gradient.fill.get` | `layer` | 读渐变填充层的设置，这里的 `from`、`to` 是坐标；只读，不改 revision；实际按**活动层**取值，`layer` 参数不够时先 `layer.select` | — |
| `gradient.presets.apply` | `preset`（`Purple 03`、`Blue 01`…）`stops` `angle` `style` | `{layer}`，按预设新建渐变填充层 | 13 |
| `layer.removeBackground` | `layer` `sampleAllLayers` `refine`（默认 `true`） | `{layer, bounds}`；忽略已有选区，自己跑一遍选择主体；Background 变成 `Layer 0` | 03 35 |
| `layer.matting.defringe` / `removeWhiteMatte` / `removeBlackMatte` / `colorDecontaminate` | `width`；—；—；`amount` `radius` | 回 `null`；Alpha 不变，只修边缘颜色；抠图边缘的处理见 cutout-export.md | 35 |

## 图层样式与预设

| 命令 | 关键参数 | 回执 / 注意 | 案例 |
|---|---|---|---|
| `layer.layerStyle.dropShadow` / `innerShadow` / `outerGlow` / `innerGlow` / `stroke` / `colorOverlay` / `gradientOverlay` / `patternOverlay` / `satin` / `bevelEmboss` | `color` `opacity` `blend` `angle` `distance` `size`…，`add:true` 追加而不替换同类效果 | `info` 里列在 `effects.items[].kind`（`Drop Shadow`、`Stroke`…） | 12 14 30 |
| `layer.layerStyle.replace` | `layer` `effects:[{kind, params}]` | 一次替换整套效果 | — |
| `layer.layerStyle.blendingOptions` | `blend` `opacity` `fillOpacity` `blendIf` `knockout` | | — |
| `layer.layerStyle.clear` | `layer` `effect` | 清空后 `effects` 键整个消失 | — |
| `style.presets.apply` / `style.presets.new` | `preset` `layers` `add`；`name` `layer` `includeEffects` | 套样式预设（`Neon Pink`、`Gold`、`Drop Shadow`…），`info` 里看到的是展开后的各个效果；没有 `style.presets.save` | 13 |
| `shape.presets.place` | `preset`（`Burst`、`Arrow Left`、`Heart`…）`rect` `fill` `stroke` | 回 shape.info | 13 28 |

## 智能对象、画板、复合、动画

| 命令 | 关键参数 | 回执 / 注意 | 案例 |
|---|---|---|---|
| `layer.smartObjects.convertToSmartObject` / `filter.convertForSmartFilters` | `layer`（不给时把选中层合成一个） | `{layer:<新 id>}`，旧 id 失效 | 19 |
| `layer.smartObjects.convertToLayers` | `layer` | 展开内容，智能滤镜丢弃 | — |
| `layer.smartObjects.editContents` → `layer.smartObjects.saveContents` | `layer` | `editContents` 把内容打开成新文档并激活（`{document, parentLayer}`），之后的命令都落在内容文档上；`saveContents` 写回父文档（`{updated:true}`），再 `document.activate` 回去 | 19 |
| `layer.smartFilter.setParams` / `layer.smartFilter.setVisible` | `layer` `index` `params`（合并）；`visible` | 对智能对象执行的滤镜自动成为智能滤镜，`info` 里列在 `smartFilters` | 19 |
| `layer.smartObjects.stackMode.median` / `mean` / `maximum` / `minimum` … | `layer` | 堆栈模式 | 21 |
| `file.placeEmbedded` / `file.placeLinked` | `path` `scale` `fit` `smartObject` `center` | `{layer, scale, bounds, smartObject}`；默认是否建智能对象、是否缩放看首选项 | 12 14 36 39 |
| `layer.new.artboard` | `rect` 或 `x` `y` `width` `height`，`preset`（`iPhone 14` → 390×844）`name` `background` | `{layer, rect}`；之后新建的图层不会自动进画板 | 24 |
| `layer.new.artboardFromLayers` | `name` `background` | 用选中层生成画板，画板框等于这些层的范围 | 24 |
| `layer.artboard.addBeside` | `layer` `side` `duplicate` | 默认在旁边 100 px 处加一块同尺寸的空画板；`duplicate:true` 才复制内容 | — |
| `layerComp.new` / `layerComp.apply` | `name` `visibility` `position` `appearance`；`comp` | `{comp}`，id 每个文档从 1 起；`apply` 回 `{comp, missingLayers}` | 24 |
| `layer.videoLayers.newBlankVideoLayer` / `layer.videoLayers.insertBlankFrame` / `timeline.nextFrame` | — | 插入空白帧后当前帧不前进，画下一帧前先 `timeline.nextFrame`；时间轴命令都回 `{timeline:{duration, fps, current…}}` | 25 |
| `timeline.create` | `duration` `fps` | | 25 |
| `file.export.renderVideo` | `dir` `format`（`gif`/`png`） | 注册表写的是 `{}`，实际收这两个键；输出 `<文档名>.gif` 或 `<文档名>_0000.png` 序列 | 25 |

## 文字

框内居中、溢出、行距、首行基线、路径文字、竖排等规则见 text-layout.md；缺字体与替换见 fonts.md。

| 命令 | 关键参数 | 回执 / 注意 | 案例 |
|---|---|---|---|
| `type.create` | `x` `y`（点文字的基线位置）或 `box:[x,y,w,h]`（段落文字），`text` `font` `size` `color` `align` `name`，以及 `type.setStyle` 的全部字符属性 | `{bounds, layer}`，字体没装时多 `warnings` | 13 16 32 38 |
| `type.edit` | `layer` `text`（整段替换，保留样式）`replace:{start,end,text}` `runs` `box` `point` `antialias` | | 15 32 38 |
| `type.setStyle` | `layer` / `layers` `range` `font` `fontStyle` `size` `color` `tracking` `leading` `align`… | 不校验未知键 | 13 |
| `type.info` | `layer` | 文字、样式段、`lines`（图层坐标）、`transform`、`bounds` | 32 38 |
| `type.warpText` | `style`（`arc`/`flag`/`wave`…）`bend` | | 13 |
| `type.fonts` | `family` | `{families:[…]}`，不需要打开文档 | 13 |
| `type.resolveMissingFonts` | `map` | 不给 `map` 列出缺失字体，给了就替换 | 15 34 |
| `edit.findAndReplaceText` | `find` `replace` `action:"changeAll"` `caseSensitive`（默认不分大小写）`wholeWord` | `{count}` | 15 |
| `edit.checkSpelling` | `action:"list"` `layer` | 只有英文词典，中文词会被列为拼写错误 | 15 |

## 形状与路径

| 命令 | 关键参数 | 回执 / 注意 | 案例 |
|---|---|---|---|
| `shape.create` | `kind`（`rect`/`roundedRect`/`ellipse`/`polygon`/`star`/`line`/`path`）`rect` `radii` `sides` `starRatio` `from` `to` `weight` `path` `fill`（颜色、`{gradient}`、`{pattern}`、`null`）`stroke`（`width` `color` `opacity` `align` `cap` `join` `dashes` `dashOffset`）`addTo` `op` | 回 shape.info：`{layer, kind, bounds, path, fill, stroke, live}` | 13 24 28 38 |
| `shape.edit` / `shape.info` | `layer`，其余同 `shape.create`；`layer` | `stroke` 合并进现有描边 | — |
| `layer.combineShapes.unite` / `subtractFrontShape` / `intersectShapeAreas` / `excludeOverlappingShapes` / `mergeShapeComponents` | `layer` `subpath` | 选中两个以上形状层时合并进最上面那个 | 13 |
| `path.set` | `name`（默认 `work`）`path:{subpaths:[{closed, op, knots}], fillRule, inverted}` `op` | 锚点写 `[x,y]` 或 `{anchor, in, out, smooth}`；`subpaths` 必须包在 `path` 里，直接写报 `missing \`path\`` | 17 |
| `path.rename` | `name` `to` | 给工作路径改名就是存成命名路径 | 17 |
| `path.toSelection` / `path.fill` / `path.stroke` | `name`（`work`/`layer`/路径名）`feather` `mode`；`color` `opacity`；`tool` `size` `hardness` `opacity` | 有选区时 `fill`、`stroke` 只作用在选区里 | 17 |
| `path.clippingPath.set` | `name` `flatness` | PSD / TIFF 的剪贴路径 | 17 |
| `path.transform` / `path.list` / `path.info` | `name` `matrix` `quad` `translateX` `scaleX`…；—；`name` | | 17 |
| `select.toWorkPath` / `select.convertToShape` | `tolerance` | 选区转工作路径 / 转形状层 | 17 |

## 选区与剪贴板

| 命令 | 关键参数 | 回执 / 注意 | 案例 |
|---|---|---|---|
| `select.rect` | `x` `y` `width` `height` `mode` `ellipse` `line`（`row`/`column`）`antiAlias` `feather` | | 08 10 23 38 |
| `select.lasso` / `select.quick` / `select.magicWand` | `points`；`points` `size` `mode`；`x` `y` `tolerance` `contiguous` `sampleAllLayers` | `magicWand` 只回 `{selected}`，范围看 `selectionBounds` | — |
| `select.subject` / `select.focusArea` | `sampleAllLayers` `mode`；`range` `noise` | 成功回 `{bounds, changed:true, selected}`，失败 `changed:false` 且原选区不动；经典算法，没有置信度 | 12 17 |
| `select.sky` | `threshold` `softness` `mode` | `{selected, changed, coverage, bounds}`；没找到时 `coverage:0` 加 `message:"No sky was detected"` | 07 |
| `select.object` | `rect` 或 `point:[x,y]` `mode` | 启发式分割，结果要看预览 | — |
| `select.colorRange` | `select`（`sampledColors`/`reds`/…/`skinTones`）`color` `colors` `points` `fuzziness` `range` `invert` | `selectionBounds` 只是包围盒，范围可能接近全画布；实际形状导蒙版看像素；`detectFaces:true` 被拒 | — |
| `select.refineEdge` | `radius` `smartRadius` `smooth` `feather` `contrast` `shiftEdge` `decontaminate` `amount` `output` `refineStrokes` | 开了 `decontaminate` 时，`output` 写什么都输出为带蒙版的新图层（`newLayerWithMask`）并隐藏原层；`layerMask`、`newLayer`、`newLayerWithMask` 会用掉选区 | 12 35 |
| `select.modify.feather` / `expand` / `contract` / `smooth` / `border` | `radius` | | 07 08 |
| `select.inverse` / `select.all` / `select.deselect` / `select.reselect` | — | 反选后 `selectionBounds` 恒为整个画布；取消选择用 `select.deselect`，`select.none` 不存在 | 02 10 |
| `select.transformSelection` | `rect` `quad` `scaleX` `scaleY` `rotate` `dx` `dy` `reference` `warp` | 弯曲放在 `warp` 里，没有顶层的 `bend` | — |
| `select.grow` / `select.similar` | `tolerance` `sampleAllLayers` | | — |
| `select.saveSelection` / `select.loadSelection` / `select.loadLuminosity` | `name` `channel`；`channel`（含 `mask`、`transparency`）`layer` `invert` | 存成 Alpha 通道；要读某层蒙版的覆盖范围用 `select.loadSelection {channel:"mask", layer}` | 17 27 |
| `edit.copy` / `edit.copyMerged` / `edit.paste` / `edit.pasteSpecial.pasteInPlace` / `edit.pasteSpecial.pasteInto` / `edit.pasteSpecial.pasteOutside` | `target`；—；`center` `target` | `copy` 回 `{bounds}`；`paste` 回 `{layer, offset}` 并清掉选区，紧接着的 `copyMerged` 会复制整个画布 | — |

## 通道

| 命令 | 关键参数 | 回执 / 注意 | 案例 |
|---|---|---|---|
| `channel.split` | `closeOriginal`（默认 `true`） | `{documents}`：名为 `<文档>_R` / `_G` / `_B` 的灰度文档，最后一个活动 | 27 |
| `channel.merge` | `mode`（`rgb`/`cmyk`/`lab`）`documents` `name` | `{document}` | 27 |
| `channel.new` / `channel.newSpot` | `name` `fill`（`black`/`white`/`selection`）`color` `opacity`；`color` `solidity` `fromSelection` | 专色通道列在 `channel.list` 的 `alpha` 里 | — |
| `image.calculations` | `source1` `source2` `blending` `opacity` `result`（`newChannel`/`newDocument`/`selection`） | | 27 |
| `image.applyImage` | `source:{document, layer, channel, invert}` `blending` `opacity` `mask` | | 27 |

## 调整（直接改像素）

`image.adjustments.*` 作用于活动的像素层（或它的蒙版、选中的通道），有选区时只改选区，回 `null`。模式转换、配置文件、校样命令见 formats.md。

| 命令 | 关键参数 | 回执 / 注意 | 案例 |
|---|---|---|---|
| `image.adjustments.levels` | `inBlack` `gamma` `inWhite` `outBlack` `outWhite`，分通道 `red` `green` `blue`，`eyedropper:{point, at, size}` | 吸管取本该是白、灰、黑的区域（背景布、灰卡）校正色偏，商品图用它 | 03 09 18 |
| `image.adjustments.curves` | `points:[[in,out],…]`（0..255）`red` `green` `blue` `eyedropper` | | — |
| `image.adjustments.hueSaturation` | `hue` `saturation` `lightness` `colorize` `reds` `yellows`… | | — |
| `image.adjustments.colorBalance` | `shadows` `midtones` `highlights`（各为 `[青-红, 品-绿, 黄-蓝]`，-100..100）`preserveLuminosity` | | — |
| `image.adjustments.vibrance` / `exposure` / `brightnessContrast` | `vibrance` `saturation`；`exposure` `offset` `gamma`；`brightness` `contrast` | | 18 19 22 |
| `image.adjustments.blackWhite` / `photoFilter` / `gradientMap` | `reds` `tint` `tintColor`…；`filter` `color` `density`；`stops:[[位置, "#hex"]]` `reverse` | `photoFilter` 的 `filter` 拼错报错 | 09 |
| `image.adjustments.threshold` / `invert` / `posterize` / `channelMixer` / `selectiveColor` | `level`；—；`levels`；… | | 27 |
| `image.adjustments.shadowsHighlights` / `desaturate` / `equalize` / `hdrToning` / `matchColor` / `replaceColor` | 见参数文本 | 这六个没有调整图层版本 | 09 18 |
| `image.autoTone` / `image.autoContrast` / `image.autoColor` | — | `autoTone`、`autoColor` 按通道拉伸，画面里没有真正的中性色时严重偏色（琥珀色瓶子变灰蓝）；只想提反差用 `autoContrast`，它不改色相 | 23 26 |

## 滤镜

所有 `filter.*` 作用于活动图层，有选区时只改选区；对智能对象执行时成为智能滤镜。哪些滤镜校验未知键见 cli.md。

| 命令 | 关键参数 | 回执 / 注意 | 案例 |
|---|---|---|---|
| `filter.blur.gaussianBlur` / `boxBlur` / `surfaceBlur` / `motionBlur` | `radius`；`radius`；`radius` `threshold`；`angle` `distance` | | 08 18 19 |
| `filter.blurGallery.tiltShift` / `irisBlur` / `fieldBlur` / `spinBlur` / `pathBlur` | `blur` `centerX` `centerY` `angle` `focus` `transition`… | | 18 |
| `filter.sharpen.unsharpMask` | `amount` `radius` `threshold` | | 03 19 26 |
| `filter.sharpen.smartSharpen` | `amount` `radius` `reduceNoise` | 没有 `threshold`、`remove`，传了报 `unknown parameter` | 29 |
| `filter.noise.reduceNoise` / `dustAndScratches` / `median` / `addNoise` | `strength` `preserveDetails` `reduceColorNoise` `sharpenDetails`；`radius` `threshold`；`radius`；`amount` `distribution` `monochromatic` `seed` | `addNoise` 给 `seed` 可复现 | 09 21 37 |
| `filter.distort.polarCoordinates` / `wave` / `twirl` … | `mode`（`rectangularToPolar`/`polarToRectangular`）；`generators` `wavelengthMin` `amplitudeMax` `type` `seed`… | | 18 37 |
| `filter.stylize.oilPaint` / `findEdges` / `emboss` | `stylization` `cleanliness` `scale` `bristleDetail`… | | 18 |
| `filter.pixelate.mosaic` / `colorHalftone` | `cellSize`；见参数文本 | | 10 18 |
| `filter.render.clouds` / `differenceClouds` / `lensFlare` / `fibers` | `seed`；`seed`；`brightness` `centerX` `centerY` `lens`；… | `clouds`、`differenceClouds` 回 `null`，不被 `filter.lastFilter` 记住；`lensFlare`、`fibers` 会被记住 | 18 |
| `filter.lastFilter` | — | 重放最近一次被记住的滤镜；还没用过滤镜时报 `no filter applied yet` | — |
| `filter.filterGallery` | `effects:[{filter, params}]`；`{list:true}` 列出全部 47 种 | 回执的 `filter` 是 `filterGallery`，效果名在 `effects[].filter` | 18 |
| `filter.other.highPass` / `offset` / `minimum` / `maximum` / `colorToAlpha` | `radius`；`horizontal` `vertical` `undefinedAreas`（`wrap`/`repeat`/`transparent`）；`radius`；`radius`；`color` `transparencyThreshold` `opacityThreshold` | `offset` 没有 `dx`、`dy`、`wrap`；高反差锐化放在单独的叠加层上做 | 21 23 |
| `filter.lensCorrection` | `distortion` `vignetteAmount` `autoScale` `edge` `vertical` `horizontal` `angle` `scale` | 回 `{params, profile, scale, angle, layer, ms}`；不校验未知键，拼错的键也照样出现在 `params` 里 | 23 |
| `filter.liquify` | `strokes:[{tool, size, density, pressure, rate, points}]` `meshSize` | `tool` 只能是注册表列出的名字（`forwardWarp` `reconstruct` `smooth` `twirlCw` `twirlCcw` `pucker` `bloat` `pushLeft`…），写 `twirl` 报错；回 `{changed, layer, maxDisplacement, ms}`，看 `maxDisplacement` 判断动没动 | — |
| `filter.cameraRaw` | `temperature` `tint` `exposure` `contrast` `highlights` `shadows` `clarity` `dehaze` `vibrance` `saturation`… | `identity:true` 表示这组参数没有产生任何变化 | — |
| `filter.adaptiveWideAngle` / `filter.vanishingPoint` | 见参数文本 | | — |

## 绘画与修饰

具体修图工序与验收见 retouch.md。

| 命令 | 关键参数 | 回执 / 注意 | 案例 |
|---|---|---|---|
| `paint.stroke` | `points:[[x,y,压力?],…]` `size` `hardness` `opacity` `flow` `spacing` `color` `mode` `erase` `smoothing` `seed` `target`（可画进 `mask`） | `{damage}`；只有一个点就是一个圆点 | 09 25 28 37 |
| `paint.pencil` | `points` `size` `opacity` `color` `block` | 没有 `hardness`、`flow`、`spacing`，传了静默忽略 | — |
| `paint.spotHealing` | `points` `size` `hardness` `type`（`contentAware`/`createTexture`/`proximityMatch`）`sampleAllLayers` | `points` 是一笔连续的笔画，修几个斑点就调用几次；`sampleAllLayers:true` 时可以画在空图层上 | 08 09 |
| `paint.healingBrush` / `paint.cloneStamp` | `points` `size` `source:[x,y]` 或 `offset:[dx,dy]` `aligned` `sampleLayer`（`current`/`all`） | `{damage, offset, aligned, nextSource}`；`healingBrush` 是 Poisson 无缝克隆：平坦目标 + 有纹理源保色调并带入纹理，反过来的组合只保证纹理塌陷，色调会随边界漂移 | — |
| `paint.patch` / `paint.contentAwareMove` | `offset` `mode`（`source`/`destination`；`move`/`extend`）`contentAware`；`offset` `scaleX` `scaleY` | `paint.patch` 要有选区；`contentAwareMove` 总是按内容感知移动 | — |
| `paint.colorReplacement` / `paint.smudge` / `paint.sharpen` / `paint.blur` / `paint.sponge` / `paint.patternStamp` | `points` `size` `strength`/`ratio`；`color` `tolerance`；`mode` | 回 `{damage}` 或 `{pattern}`；修饰类笔刷的 hardness 是 0..100 | — |
| `paint.setSymmetry` / `paint.symmetryFromPath` / `paint.symmetryDisable` | `mode`（`vertical`/`horizontal`/…）`center`；`name` | 对称绘图；`symmetryFromPath` 用命名路径当对称轴，回 `{segments}` | — |
| `edit.copy` / `edit.copyMerged` / `edit.cut` / `edit.paste` / `edit.pasteSpecial.pasteInPlace` / `edit.pasteSpecial.pasteInto` / `edit.pasteSpecial.pasteOutside` | `target`；`center` `target` | `copy`/`cut` 回 `{bounds}`；`paste` 回 `{layer, offset}` 并清掉选区；`edit.pasteSpecial.pasteInto` 要有选区 | — |
| `edit.fillForeground` / `edit.fillBackground` / `edit.fillHistory` | `state` | 用前景色/背景色/历史状态填充选区；`edit.fillHistory` 回 `{contents:"history"}` | — |
| `edit.fade` / `edit.toggleLastState` / `edit.deleteAndFillSelection` | `opacity` `mode`；—；— | `fade` 回 `{faded:<上一步名称>}`；`deleteAndFillSelection` 回 `{filled}` | — |
| `edit.puppetWarp` / `edit.perspectiveWarp` | `pins:[{src,dst}]`；`planes:[{src,dst}]`（各四角） | `puppetWarp` 看 `changed`；`perspectiveWarp` 的退化输入可能不报错，要自己校验四边形 | — |
| `paint.dodge` / `paint.burn` / `paint.sponge` | `points` `size` `range`（`shadows`/`midtones`/`highlights`）`exposure` `protectTones` | | 08 |
| `paint.redEye` | `x` `y` 或 `points`，`pupilSize`（默认 50）`darken` | `{damage, pixels}`；`pupilSize:50` 会在约 139 px 的窗口里搜索，附近偏红的皮肤也被压暗；用小值或先建选区 | — |
| `paint.historyBrush` | `points` `size` `state` | 只能画回目标层在那个状态下已有的像素，不恢复透明；状态里目标层还没有像素时，回执照样带 `damage` 但画面不变 | — |
| `paint.bucket` | `x` `y` `tolerance` `contiguous` `color` `contents`（`foreground`/`pattern`）`opacity` | | 37 |
| `paint.gradient` | `from:[x,y]` `to:[x,y]` `style` `colors` `stops` `transparency` `opacity` `target`（`mask` 画进蒙版） | 这里的 `from`、`to` 是坐标 | 36 |
| `edit.fill` | `contents`（`color`/`foreground`/`contentAware`/`pattern`/`history`…）`color` `opacity` `mode` `preserveTransparency` | `{contents}`；有选区只填选区，没有就填满整层；没有 `x`/`y`/`width`/`height` | 10 23 |
| `edit.stroke` | `width` `color` `location`（`inside`/`center`/`outside`）`opacity` | 描选区的边 | 28 |
| `edit.contentAwareFill` | `sampling` `area` `colorAdaptation` `output` `seed` | 必须先有选区；`{layer, filled, window}` | — |
| `edit.contentAwareScale` | `width` `height` `scaleX` `scaleY` `x` `y` `protect` `protectSkinTones` | 不给 `x`、`y` 时锚在图层原来的位置，画布加宽后会留一条空白 | 23 |
| `edit.fade` | `opacity` `mode` | 淡化上一步，回 `{faded}` | — |
| `tools.setColors` | `foreground` `background` | 很多命令的默认颜色取前景色 | — |
| `notes.add` / `notes.list` / `notes.set` / `notes.delete` | `x` `y` `text` `author` `color`；`index` | 审阅批注，随 PSD 保存 | 28 |
| `view.newGuide` / `view.newGuideLayout` / `view.newGuidesFromShape` | `orientation` `position`（px，或 `3mm`、`50%`）`color`；`columns` `width`（单列宽度）`gutter` `rows` `margin`；`layer` | `newGuide` 回 `null`，`newGuideLayout` 回 `{horizontal, vertical}`，`newGuidesFromShape` 回 `{bounds:[x0,y0,x1,y1]}`；参考线不出现在 `document.inspect` 和渲染结果里；栅格计算见 layout.md | 06 33 |
| `view.setRulerOrigin` | `x` `y` | 回 `{x,y}`，不是 `null` | — |

## 自动化与导出

带文件路径的命令在 serve、MCP、桌面通道里会被拒（入口对照见 automation.md）。动作、批处理、Droplet、变量数据组的规则见 actions-batch.md；导出路线、切图、Image Assets 见 cutout-export.md；打包交付见 psd-workflow.md。

| 命令 | 关键参数 | 回执 / 注意 | 案例 |
|---|---|---|---|
| `file.saveACopy` | `path` `quality` `layers` `tiffLayers` `tgaBits` `dpxBits` | `{path, warnings}`；没有 `overwrite` 参数，同名文件直接覆盖 | 20 29 |
| `file.automate.batch` | `steps` `input` `output` `includeSubfolders` `format` `quality` `naming` `startingSerial` | `{files, errors}`；见 actions-batch.md | 03 |
| `file.scripts.imageProcessor` | `input` `output` `format` `quality` `width` `height`（只缩不放）`convertToSrgb` | `{files, errors}` | 05 |
| `file.automate.contactSheetII` | `input` `units`（`pixels`…）`width` `height` `columns` `rows` `caption` `flatten` | 新建文档 | 05 18 |
| `file.automate.conditionalModeChange` | `from` `to` | | 05 |
| `file.automate.cropAndStraightenPhotos` | — | 扫描件里每张照片一个新文档，回 `photos:[{document, width, height, angle, center}]` | 20 |
| `file.scripts.loadFilesIntoStack` | `paths` `align` `createSmartObject` | 新文档，每个文件一层 | 21 |
| `file.automate.photomerge` | `paths` `layout` `blend` `contentAwareFill` | 新文档，每张图一个带蒙版的层 | 22 |
| `file.automate.mergeToHdrPro` | `paths` `exposures` `mode`（`32`/`16`/`8`）`method` | 新文档 | 22 |
| `actions.record` / `actions.stop` / `actions.get` / `actions.play` / `actions.save` | 见 actions-batch.md | `stop` 回步数，步骤列表要 `get` | 26 |
| `file.automate.createDroplet` | `path` `steps` `name` `output` `format` `quality` | `{path, shim, steps}` | 26 |
| `image.variables.define` / `image.variables.dataSets` / `image.applyDataSet` / `file.import.variableDataSets` / `file.export.dataSetsAsFiles` | 见 actions-batch.md | | 16 |
| `file.export.layersToFiles` | `dir` `format` `prefix` `visibleOnly` `quality` | `{files}`，文件名 `<prefix>_<NNNN>_<图层名>.<ext>`，从上往下编号；只导顶层，组导成一张合成图；`prefix:""` 时前缀变成 `layer` | 24 35 |
| `file.export.layerCompsToFiles` / `file.export.artboardsToFiles` / `file.export.artboardsToPdf` | `dir` `prefix` `comps`；`dir` `prefix`（`""` 表示不加前缀）`artboards`；`path` `artboards` `quality` | 文件名以回执的 `files` 为准（如 `0000_Mobile.png`）；PDF 每个画板一页，回 `{path, pages}` | 24 |
| `file.generate.imageAssets` | `on` `dir` | 按图层名导出（`logo.png`、`50% small/logo.gif`、`48x48 icons/a.png8`），隐藏层也导 | 24 35 |
| `file.package` | `dir` `format`（`pcraft`/`psd`/`psb`） | `{folder, document, links, missing, warnings}` | 34 |
| `layer.quickExportAsPng` / `layer.exportAs` | `layer` `path`；`scale` | 单层导出 | 24 |
| `slice.new` / `slice.set` / `slice.promote` / `slice.delete` / `slice.list` | `rect` `name` `url`…；`slice`（id）或 `number` | 编号随切片增删变化，后续操作用 `slice` id；对已经是用户切片的 `promote` 原样回它的 id | 24 |
| `file.export.saveForWebLegacy` | `path` 或 `dir`，`format` `quality` `metadata` `html` `slices` `convertToSrgb` | 元数据与 HTML 的规则见 formats.md | 10 24 |
| `file.export.colorLookupTables` | `path` `size` `scope` `layers` | 把调整图层烘焙成 `.cube`，蒙版不进 LUT | 07 |
| `layer.newAdjustmentLayer.colorLookup` | `lut`（内置名）`file` `data` | 套用 `.cube` / `.3dl` / `.look` | 07 |
| `swatches.add` / `swatches.export` / `swatches.import` | `color` `name` `group`；`format`（`ase`/`aco`）`path` `group` | `export` 不给 `path` 时回 base64 `data` | 11 |
| `image.mode.indexedColor` / `image.mode.colorTable` | `palette` `colors` `dither`；不给参数 | 不给参数的 `colorTable` 回当前颜色表，可以用来取主色 | 11 |
| `measurementLog.export` | `path` `rows` | 不给 `path` 时回 `{csv, rows}` | — |
| `plugin.install` / `plugin.run` / `plugin.list` | `path` 或 `data`（base64 的 `.wasm`）`replace`；`id` `params` | 装好的插件只在当前进程里有效 | — |
| `edit.autoAlignLayers` / `edit.autoBlendLayers` | `projection` `reference`；`method`（`panorama`/`stack`） | | — |

## 深水命令索引

上面各表是常用命令；下面这些是注册表里确实存在、但日常脚本不一定用到的域。参数仍以 `params.py --exact <id>` 为准，这里只给入口和关键语义。

### 文字深水

| 命令 | 语义 |
|---|---|
| `type.insertText` / `type.navigate` / `type.caret` / `type.hitTest` | 按字符偏移插入；光标按词/行/首尾移动；字符索引→文档像素段；点→字符/行命中。`insertText` 回 `{caret}`，`hitTest` 回 `{inside,index,line}` |
| `type.pasteLoremIpsum` / `type.updateAllTextLayers` | 填入占位文案；刷新全文档文字层，回 `{updated}` |
| `type.createWorkPath` / `type.createSelection` / `type.convertToShape` | 文字转工作路径；文字转选区（`bounds` 是 `[x0,y0,x1,y1]`）；文字转形状层 |
| `type.attachToPath` / `type.detachFromPath` / `type.orientation.vertical` | 路径文字、脱离路径、竖排；路径文字存 PSD 会退化成点文字 |
| `type.openType.<feature>` | `standardLigatures` `contextualAlternates` `discretionaryLigatures` `fractions` `oldstyle` `ordinals` `ornaments` `stylisticAlternates` `swash` `titlingAlternates`，参数 `{layer,on}` |
| `type.characterStyle.*` | `new`（`name` `attrs` `fromSelection` `apply` `layer`）、`apply`（`id` `layer` `range`）、`list` `redefine` `duplicate` `clearOverride` `delete` |
| `type.paragraphStyle.*` | `new`（`name` `attrs` `apply` `layer`）、`apply` `list` `clearOverride` `delete` |
| `type.antiAlias.none` / `sharp` / `crisp` / `strong` / `smooth` | 改抗锯齿档位；除 `none` 外渲染像素一致 |

### 路径与形状深水

| 命令 | 语义 |
|---|---|
| `path.addAnchor` / `path.deleteAnchor` / `path.moveAnchors` / `path.moveHandle` / `path.bendSegment` / `path.convertPoint` | 锚点级编辑：在 `{subpath,knot,t}` 处加点；删点；`{anchors:[[subpath,knot]],move:[dx,dy]}` 平移；`{handle:"in\|"out",to:[x,y]}`；弯曲线段；转平滑点 |
| `path.style.copyFill` / `pasteFill` / `copyStroke` / `pasteStroke` | 在形状层之间复制填充/描边；复制命令回 `null` |
| `path.clippingPath.clear` | 清除剪贴路径 |
| `shape.rasterize` / `shape.presets.list` | 形状转像素；列出预设形状组 |
| `shape.presets.place` | 放置预设形状；`rect` 是 `[x,y,w,h]` |
| `layer.combineShapes.*` | `unite` `subtractFrontShape` `intersectShapeAreas` `excludeOverlappingShapes` `mergeShapeComponents`；选中两层以上，结果并入最上层 |

### 图层、通道、复合与帧

| 命令 | 语义 |
|---|---|
| `layer.setEffectsVisible` | 开关整层图层效果，参数 `{layer,visible}` |
| `layer.newFillLayer.solidColor` / `gradient` / `pattern` | 填充层；建后改内容用 `layer.fill.solidColor.set` / `layer.fill.pattern.set` |
| `layer.ungroupLayers` / `layer.new.layerViaCopy` | 解组；用选区在当前层上复制出新层 |
| `layer.new.frame` / `layer.new.frameFromLayers` | 建空帧 / 用选中层建帧；`frame` 是 `[x,y,w,h]` |
| `layer.artboard.set` | 改画板位置与尺寸；`addBeside` 默认在原画板右侧 100 px |
| `layerComp.new` / `apply` / `list` / `duplicate` / `update` / `delete` / `restoreLastDocumentState` | 图层复合完整生命周期；`restoreLastDocumentState` 回 `null` |
| `channel.new` / `duplicate` / `newSpot` / `options` / `setVisible` / `mergeSpot` | Alpha 与专色通道；专色 `newSpot {color,solidity,fromSelection}`；`mergeSpot` 合并进图像 |
| `history.newSnapshot` / `selectSnapshot` / `renameSnapshot` / `deleteSnapshot` / `selectState` / `deleteState` / `newDocument` | 快照与历史状态；状态索引 0 = 最早，删除会丢掉该状态之后的历史 |
| `image.revealAll` / `image.applyImage` / `image.calculations` | 画布扩到包住像素；应用图像/计算通道，`calculations` 的 `result` 可为 `newChannel`/`newDocument`/`selection` |

### 选区深水

| 命令 | 语义 |
|---|---|
| `select.lasso` / `select.magneticLasso` / `select.quick` / `select.colorRange` | 套索、磁性套索、快速选择、色彩范围；磁性套索 `{points,trace}` |
| `select.modify.expand` / `contract` / `feather` / `smooth` / `border` | 选区几何修改；`radius` |
| `select.grow` / `select.similar` / `select.transformSelection` | 扩选/相似/变换选区；`transformSelection` 用 `scaleX` `scaleY` `rotate` `dx` `dy` `corners` |
| `select.toWorkPath` / `select.convertToShape` / `select.loadLuminosity` | 选区转路径/形状/亮度选区 |
| `select.editInQuickMaskMode` | `{on}` 进出快速蒙版，回 `{quickMask}` |
| `select.findLayers` / `select.allLayers` / `select.isolateLayers` / `select.deselectLayers` | 按名找层、全选层、隔离、取消层选择 |
| `layer.selectInRect` / `layer.pickAt` | 框内选层；点选层（`list:true` 回候选列表） |

### 绘画、修饰与工具

| 命令 | 语义 |
|---|---|
| `paint.magicEraser` / `paint.backgroundEraser` | 魔棒擦除；背景橡皮擦 `{limits}` |
| `paint.patternStamp` / `brush.defineFromSelection` | 图案图章；用选区定义画笔 |
| `brush.presets.save` / `setCurrent` / `list` / `delete` | 画笔预设生命周期 |
| `brush.texturePattern` | 设置画笔纹理 `{pattern,scale,enabled}` |
| `tools.setBrush` / `tools.swapColors` / `tools.defaultColors` | 设置画笔；交换/恢复前景背景色 |
| `filter.gallery.<effect>` | 滤镜库单项（`watercolor` `posterEdges` `glowingEdges` 等）；也可用 `filter.filterGallery {effects:[…]}` 叠加 |
| `filter.blurGallery.fieldBlur` / `irisBlur` / `pathBlur` / `spinBlur` | 模糊画廊；参数按注册表 |
| `filter.adaptiveWideAngle` / `filter.lensCorrection` | 广角/镜头校正；`lensCorrection` 同时接受 `distortion`/`vignetteAmount` 与 `correctDistortion`/`correctVignette`/`correctCA` 两种写法 |
| `filter.lastFilter` | 重放最近一次被记录的滤镜 |

### 预设与资源

| 命令族 | 语义 |
|---|---|
| `gradient.presets.new` / `edit` / `list` / `select` / `stop` / `apply` | 渐变预设完整生命周期；`edit` 的 `action` 有 `newGroup`/`rename`/`delete`/`deleteGroup` |
| `pattern.presets.new` / `edit` / `list` / `select` / `apply` | 图案预设；`new` 可用选区或 `rect` |
| `swatches.newGroup` / `add` / `list` / `use` / `rename` / `move` / `delete` / `deleteGroup` | 色板组与色板条目 |
| `style.presets.new` / `edit` / `apply` | 图层样式预设；`new` 可 `includeEffects` |
| `document.presets.save` / `list` / `get` / `delete` | 新建文档预设 |
| `tool.presets.new` / `list` / `select` / `edit` | 工具预设 |
| `brush.presets.*` / `pattern.presets.*` | 画笔与图案预设；`list {full:false}` 只回摘要 |

### 评审、测量、切片与时间轴

| 命令 | 语义 |
|---|---|
| `count.newGroup` / `add` / `setGroup` / `move` / `remove` / `clear` / `deleteGroup` | 计数工具分组与打点 |
| `image.analysis.countTool` / `rulerTool` / `recordMeasurements` / `info` | 计数、标尺、记录测量、分析汇总 |
| `measurementLog.list` / `delete` / `export` | 测量日志；`export` 在自动化会话里被 ambient 禁令拒绝 |
| `slice.new` / `list` / `set` / `promote` / `divide` / `fromGuides` / `delete` | 网页切片；编号随增删变化，后续用 `slice` id |
| `timeline.create` / `info` / `setFrame` / `nextFrame` / `previousFrame` / `setProps` / `delete` | 时间轴；`setProps` 可改 `fps` `duration` `workStart` `workEnd` |

### 文档与色彩补充

| 命令 | 语义 |
|---|---|
| `image.mode.colorTable` | 不给参数读当前颜色表；`{table:"grayscale"}` 等可换表 |
| `image.mode.bitmap` | 需先转灰度；`{method:"threshold"}` 等 |
| `image.mode.multichannel` | 转多通道 |
| `image.trap` | 需 CMYK；`{width}`，回 `{trapped}` |
| `edit.transform.flipHorizontal` / `flipVertical` / `rotate90Cw` / `rotate90Ccw` / `rotate180` | 作用于当前图层，`target:"pixels"`；画布尺寸不变 |
