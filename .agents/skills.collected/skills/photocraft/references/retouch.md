# 修图与合成

> 核对版本：命令 id 与参数按 photocraft-cli 0.14.0 (ff4738810) 复核；行为记录来自 0.10.0–0.14.0 的实测，0.14 未逐条重验的条目保留原文。

## 1. 顺序

- 修复稿（老照片、损伤稿）按 修结构（去尘、划痕、撕痕、扫描边框）→ 恢复对比度与色调 → 上色和增强 的顺序走，上色不放在修复之前。
- 调整从全局到局部：方向、裁剪、拉直 → 白平衡 → 曝光与黑白点 → 曲线 → 全局色 → 局部蒙版 → 修补 → 输出锐化。
- 去噪在最终锐化之前；只锐化重要边缘，不锐化色度噪声和压缩块；提亮阴影后再补一次降噪。
- 每一步只改一件事，复杂编辑拆成多轮。

## 2. 动手前

- 先出诊断清单（曝光、色偏、细节、构图、损伤分项），写清能修什么、不能改什么。
- 硬锚不动：人脸身份、解剖结构、文字、logo、产品设计、地标。软锚可动：光照、裁剪、背景杂物、非关键色。修补只在软锚区域做；硬锚确实要改，先出方案让用户定。
- 缺失区域的重建、考证不了的上色，交付时声明「推断补全」。

## 3. 非破坏做法

| 做法 | 命令 | 要点 |
| --- | --- | --- |
| 滤镜可回改 | `filter.convertForSmartFilters`，或 `layer.smartObjects.convertToSmartObject` 后再跑滤镜 | 转换后图层 id 会变；参数用 `layer.smartFilter.setParams {index, params}` 改 |
| 副本兜底 | `layer.duplicate` | 做不了智能滤镜时在副本上做 |
| 高反差锐化 | 复制层 → `filter.other.highPass {radius}` → `layer.setProps {"blend":"Overlay","opacity":0.7}` | 锐化单独成层，可关可调 |
| 减淡与加深 | `layer.new.layer {"name":"效果_减淡加深","mode":"Overlay","fillNeutral":true}` 建 50% 灰中性层，在它上面画 `paint.dodge` / `paint.burn` | 实测：中性层建好时合成不变，减淡处变亮、加深处变暗，隐藏这层后像素完全还原 |
| 蒙版代替擦除 | `layer.layerMask.revealSelection` | 会用掉选区 |
| 选区 | 先 `select.modify.expand` / `select.modify.contract` 改形状，最后 `select.modify.feather` | 危险编辑前把选区存成通道或蒙版 |
| 版本 | 每轮另存 `_v2`、`_v3` | 不在旧版本文件上续改 |

不要在 `layer.stampVisible` 生成的盖印层上做减淡加深。盖印层是全部可见层合并出的整图副本，它可见时，关掉下面的柔肤、修补层，合成完全不变（实测最大差 16，平均 0.70，只是 JPEG 噪声）。「每步独立成层、可单独关掉」只在没有盖印层压在上面时成立。

## 4. 笔刷参数单位

| 命令 | hardness | opacity | flow | spacing |
| --- | --- | --- | --- | --- |
| `paint.stroke` | 0..1 | 0..1 | 0..1 | 0..10 |
| `paint.pencil` | 不支持 | 0..1 | 不支持 | 不支持 |
| `paint.backgroundEraser` | 0..1 | — | — | — |
| `paint.spotHealing`、`paint.healingBrush`、`paint.cloneStamp`、`paint.patternStamp`、`paint.dodge`、`paint.burn`、`paint.sponge`、`paint.blur`、`paint.sharpen`、`paint.smudge`、`paint.historyBrush`、`paint.remove` | 0..100 | 1..100 | 1..100 | 1..1000（笔刷直径的 %） |
| `paint.mixerBrush` | — | — | 0..100（另有 `wet`/`load`/`mix` 0..100） | — |

超出范围不报错，静默截断：`paint.stroke {opacity:50}` 画出不透明的实色，`paint.dodge {opacity:0.5}` 几乎看不出效果。`paint.pencil` 传 hardness/flow/spacing 也不报错，直接忽略。图层不透明度（`layer.new.layer`、`layer.setProps`）是 0..1。

## 5. 修补

- `paint.spotHealing {points, size, type, sampleAllLayers}`：`points` 是**一笔**连续笔画（折线）。把几个斑点的坐标一次传进去，会连成一条带子，把别处的颜色拖过整片皮肤。一个斑点调用一次，每次只给这个点或一小段笔画。`type:"contentAware"` 从周围取样，实测把衣服的颜色带到了脸颊上，修完必须看结果。
- `paint.healingBrush {points, source | offset}`：带取样点的修复，适合有纹理的区域；`paint.cloneStamp {points, source | offset, aligned}`：原样复制。
- 修补画在新建的空层上，原图层不动：`paint.spotHealing {sampleAllLayers:true}` 已实测可用；`paint.healingBrush` / `paint.cloneStamp` 用 `sampleLayer:"all"` 也可跨层取样（已在 GUI 会话实测）。
- `edit.contentAwareFill` 要先有选区（否则报 `make a selection around what to remove`），填完同样要看结果。
- 大面积细尘用 `filter.noise.dustAndScratches {radius, threshold}`，用 `threshold` 保住细节；划痕用 `paint.spotHealing` 沿划痕画一笔。
- 红眼：`paint.redEye {x, y, pupilSize, darken}`，会把附近偏红的皮肤也压暗，用后检查。

## 6. 拉直、裁剪与尺寸

- 拉直：`image.crop {x, y, width, height, angle}` 的 `angle` 与 `image.rotation.arbitrary {angle, direction:"ccw"}` 同号——**和 `direction:"cw"` 反号**（实测 0.18：`crop angle:15` 的内容主轴是 −15°，`rotation cw:15` 是 +15°）。照片顺时针歪了 3°，用 `angle:3` 拉回；写成 `-3` 会再多转 3°。`angle` 必须同时给 `x`/`y`/`width`/`height`，缺一项报 ``an `angle` needs an explicit `x`, `y`, `width` and `height```。验收看四个角都没有空白楔形，不要只看一个角。
- 旋转或扩展裁剪露出的空白可以用 `image.crop {contentAware:true}` 补（注册表说明，未实测）。
- `image.canvasSize`（改画布，不重采样）和 `image.imageSize`（重采样）分开用，缩放保持宽高比。
- 构图：给出几种备选（原比例修正、主体放大、表达性画幅、留负空间），保留原构图时说明理由；不切关节、指尖、文字、产品轮廓。

## 6.5 频率分离（纹理与色调分开修）

磨皮、去噪、保纹理的调色都用这套：低频层管颜色和明暗，高频层管毛孔、织物纹理。

```
orig（合并成一层像素层）
├─ high   原始 − low 的残差，blend = Linear Light
└─ low    orig 的高斯模糊
```

配方（实测 0.18，重建差 ≤1/255）：

```bash
photocraft-cli run <稿>.psd \
  --cmd layer.flattenImage \
  --cmd layer.setProps --params '{"name":"orig"}' \
  --cmd layer.duplicate --params '{"name":"low"}' \
  --cmd filter.blur.gaussianBlur --params '{"radius":6}' \
  --cmd layer.select --params '{"name":"orig"}' \
  --cmd layer.duplicate --params '{"name":"high"}' \
  --cmd layer.select --params '{"name":"high"}' \
  --cmd image.applyImage --params '{"source":{"layer":"low"},"blending":"subtract","scale":2,"offset":128}' \
  --cmd layer.setProps --params '{"blend":"LinearLight"}' \
  --cmd layer.moveTo --params '{"layer":"high","target":"low","position":"above"}' \
  --cmd layer.select --params '{"name":"orig"}' \
  --cmd layer.setProps --params '{"visible":false}' \
  --out <稿>_fs.psd
```

- `scale` 必须是 **2**，`offset` 128：把残差压缩一半再存到 128 两侧，Linear Light 展开回来正好还原。写 1 时合成结果变成 `2×原始 − 低频`，超出 0..255 的部分被截断——实测同一样张有 1812 个像素与正确配方不同，最大差 54，边缘处偏成青色（`scale:2` 得 129 灰，`scale:1` 得 `75,183,183`）。纯色块或全灰图看不出这个错，必须用带边缘的样张验。
- 混合模式写 `LinearLight` 或 `linear light` 都行（大小写与空格不敏感），存盘后读回是 `Linear Light`。拼错的模式名会直接报 `unknown blend mode`，这点和多数参数不同。
- **`layer.duplicate` 插入在被复制层的正上方**。连续从同一层复制两次，第二次会落在第一次**下面**——层序变成 low 压着 high，高频根本叠不到低频上，渲染结果等于只有低频。必须显式 `layer.moveTo {target:"low", position:"above"}` 把 high 提上去。这个错不会报错，只能靠下面的验收发现。
- `layer.list` 不返回 `blend` 字段，回读混合模式要用 `document.inspect`。
- 半径按输出尺寸取：屏幕图 2–4 px，印刷 300 ppi 的皮肤 6–12 px。半径越大分得越粗，纹理越完整、色调越块。

验收（缺一不可）：

1. **重建校验**：隐藏 orig 前后各渲一张，逐像素差应 ≤1/255。差得多先查层序和 `scale`/`offset`。
2. **职责校验**：只改 high（比如 `filter.blur.gaussianBlur` 小半径）后，低频区域的颜色和明暗不应移动；只改 low（调色、`edit.fill`）后，纹理的锐度不应变化。

修纹理改 high，修色斑改 low，改完两张都可单独回退——比一次性磨皮更可控。合并前留 PSD 母版。

## 7. 人像与上色

- 只修临时瑕疵（红眼、油光、短期痘斑），保留毛孔、细纹、不对称和疤痣。优先用减淡加深和色调均匀，不大面积磨皮。
- 上色克制：低到中饱和；肤色分区变化，不平涂；白、黑、金属、石材、纸张默认不上色。
- 默认保留颗粒与年代痕迹，用户明确要「现代翻新」才去掉。

## 8. 合成

- 抠图、去边、导出见 cutout-export.md。
- 合成目标用空间方位描述（「左上角的桌子」），并说明哪些区域保持不变。
- 光影一致：先定视线落点和阴影深度，不要全局平提亮；肤色不偏灰、橙、品红、绿。混合光源先校主体白平衡，背景可以留一点冷暖。
- 让主体融进场景：在主体上方建调整层，`layer.createClippingMask` 剪贴到主体。新建调整层会把当前选区当蒙版，建之前先确认有没有选区。

## 9. 验收

- 双尺度看图：适合窗口看构图与色彩，100% 看修补伪影（重复的克隆纹理、halo、蜡皮、死黑、剪白、色带）。
- 用像素证明效果：属性回显和历史记录增加都不算数（在灰图上调色相也会多一条历史）。取改动区域的像素：`document.pixel` 读合成结果（会忽略 `sampleLayer`），`document.sampleColor {sampleLayer:"current"}` 读单层；或者改动层隐藏前后各渲染一次，交给 `psd_compare.py`（执行，用法见 psd-workflow.md）。
- 探针改了文档状态要复原，复原不了要报出来。
- 每项改动的结论只有三种：有效、无效、测不到。「测不到」单独列出，不算通过。
- 批量修复逐张列结果（成功、失败、没有变化）；静默跳过的文件当作失败处理。

## 10. 导出与交付

- 合并、拼合只在最后一步、在副本上做；先存分层母版（PSD/PSB/.pcraft）。
- 默认交付平图（PNG/JPEG）加可编辑母版，用户明确只要其一时例外。
- 单层导出要铺回整幅画布才能保持对齐；`doc.exportLayers` 的输出本来就是画布尺寸（见 cutout-export.md）。
- 图层按 id 寻址；PSD 存盘再打开后 id 会重排，重开后重新 inspect 解析；重名层用 `layer.select {name, occurrence}`。
