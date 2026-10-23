# 文字排版：事实与做法

> 核对版本：命令 id 与参数按 photocraft-cli 0.14.0 (ff4738810) 复核；行为记录来自 0.10.0–0.14.0 的实测，0.14 未逐条重验的条目保留原文。文字是本技能最容易踩坑的域：垂直对齐不存在、框改小会静默丢行、两种 bounds 形状混用会让位置算飞。

## 一句话结论

水平 `align` 是真约束，改字后自动重排；垂直方向没有任何对齐字段，只能收缩段落框或事后用图层对齐；判断文字是否完整要看 `type.info` 的 `lines`，不要看 `text`。

## 数据模型

- 段落样式只有水平 `align`（`left`/`center`/`right`/`justify` 一类），**没有垂直对齐**。传 `verticalAlign`、`vAlign` 不报错也不生效，未知键被静默忽略。
- 文字图层保留实时编辑：改字、改样式、改框都不会栅格化，除非显式 `type.rasterize` / `type.convertToShape`。
- 缺失字体只产生 warning，用回退字体渲染；交付前按 `fonts.md` 处理。

## 点文字与段落框

| 类型 | 创建 | 锚点 |
|---|---|---|
| 点文字 | `type.create {x, y, text, …}` | `x`/`y` 是**首行基线锚点**，不是左上角 |
| 段落框 | `type.create {box:[x,y,w,h], …}` | `box` 的 `x`/`y` 是框左上角；文字从框内左上开始排 |

- 段落在框内按 `w` 自动换行；框的存储形状是 `shape.Box {x:0,y:0,w,h}` 加 `transform` 平移。
- `type.convertToParagraphText` 对已是框文字的层报 `already paragraph text`；`type.convertToPointText` 对点文字报 `already point text`。转换不是 no-op，先看 `shape`。
- `type.convertToShape` 原地转换、id 不变，之后 `kind` 变成 `Shape`（不再是可编辑文字）。

## bounds 的三种形状

混用会算出离谱的位置：

| 来源 | 形状 | 含义 |
|---|---|---|
| `type.create` / `type.info` 的 `bounds` | `[x0,y0,x1,y1]` | 墨迹外接框（四角坐标） |
| `document.inspect` / `layer.list` 的 `bounds` | `[x,y,w,h]` | 同一墨迹框，换成左上角 + 宽高；已裁到画布内 |
| `type.create {box}` 的输入 | `[x,y,w,h]` | 排版框，不是墨迹框 |

- 两者描述的是同一个墨迹框，但 `type.info` 给角点、`inspect` 给左上与宽高，换算时别套错公式。
- `inspect` 的 bounds 是字形墨迹框，会因首字侧距比文本框偏右几个像素（字号越大偏得越多）；要对齐画布用 `type.info` 的 `transform` 加 `shape.Box` 还原文本框，别拿墨迹框当框。
- 图层整体移出画布时 `inspect` 显示 `[0,0,0,0]`，不会被裁成负数。

## 单位

- 字号、行距、首行缩进、段前段后都是 **pt**。像素换算：`px = pt × ppi / 72`，72 ppi 时 1 pt = 1 px，144 ppi 时翻倍，300 ppi 时约 4.17 倍。
- 参考线的字符串长度（`"3mm"`、`"50pt"`）默认按 PostScript 点（72 英寸点）换算；只有把 `unitsAndRulers.pointSize` 设成 `traditional` 时才用 72.27。
- `edit.transform` 的缩放是百分比，旋转是角度，锚点是内容中心。

## 行距与首基线

- 自动行距 = 字号 × 1.2；`autoLeading` 传百分比（150 = 1.5 倍）。40 pt 自动行距的基线间距是 48 px（72 ppi）。
- 首基线 = 框顶 + 首行 `'d'` 字高，**不是** hhea ascent。看起来整体偏上是正常的，需要视觉居中就补偏移。
- `spaceBefore` / `spaceAfter` 只影响第 2 段及以后，**推不动第一行**。
- `firstLineIndent` 对每一段的首行生效；测试缩进要用会换行的段落，单行段落分不出缩进和整段位移。

## 溢出：框改小会静默丢行

- `type.edit {box}` 把高度改小后，超出的行**不进 layout**（后面的段落也一起停），但模型里的 `text` 仍是全文。
- 判断文字是否完整：看 `type.info` 的 `lines`（按行给了 `start`/`end`/`baseline`/`x0`/`x1`），不要看 `text`。
- 恢复办法：把框改回原高度，或转点文字；已经丢失的排版不会自动回来。
- 超长单词在窄框里会按字符断行；判断依据同样是 `lines`。

## 垂直居中的两种做法

没有 `verticalAlign`。要做垂直居中共两种：

1. **收缩段落框到墨迹高度**：读 `type.info` 的 bounds，把 `box` 高度改成墨迹高度（或用 `type.edit {box}` 直接写）。行数、字号不变时稳定；改字或改字号后要重跑。
2. **选区 + 图层对齐**：`select.rect {x,y,w,h}` 画一个和框等大的选区，`layer.select` 选中文字层，`layer.align.verticalCenters {to:"selection"}`。不要求框高刚好等于墨迹高。

两种都是"一次性几何"，不是活约束：内容变了要重新算。Photoshop 的"段落垂直对齐"在 PhotoCraft 里不存在。

## 对齐与枚举

- `align` 拼错（`centre`、`CENTER`、`middle`）**不报错**，静默回落到 Left。要用合法值。
- `type.setStyle`、`layer.setProps`、`select.rect` 忽略未知键；`file.new`、`ui.set`、`ui.screenshot`、`layer.hideLayers` 会报 `unknown parameter`。参数以 `params.py --exact <id>` 的文本为准。

## 抗锯齿

- 除 `none` 外，`sharp`、`crisp`、`strong`、`smooth` 渲染像素完全一致；`none` 是二值化（两个灰度级）。
- `type.edit {antialias:"windows"}` 会被忽略；要改档位用 `type.antiAlias.*` 系列命令。

## 文字变形与路径文字

- `type.warpText` 只改变字形位置，**不改变行数**；变形后仍按原 `lines` 判断是否溢出。
- `type.attachToPath` 默认挂到工作路径（`shape` 参数可指定形状层）；沿路径排字后 `type.info` 的 `lines` 仍按逻辑行给。
- **PSD 不保存路径文字**：存成 PSD 会静默降级为点文字（`warnings` 为空），`.pcraft` 保留。要保留路径文字就留 `.pcraft` 母版。
- `detachFromPath` 转回点文字，段落框会丢失；之后要重新设框。

## 竖排

- `type.create {orientation:"vertical"}` 走竖排（tategaki）；重复设置同一方向是幂等的。
- 竖排的 `lines` 与行距含义与横排不同，换行判断仍看 `lines`。

## 字符样式与段落样式

- `type.characterStyle.new` / `type.paragraphStyle.new` 创建命名样式；应用样式后，图层上显式设置过的属性（如字号）会保留为本地覆盖。
- OpenType 特性标签：`liga`、`frac`、`onum`、`dlig`、`calt`、`ordn`、`ornm`、`salt`、`swsh`、`titl`，通过 `type.setStyle` 的对应键设置。

## 拼写检查

- `edit.checkSpelling {action:"list"}` 只带英文词典；中文字符会被当成生词并给出英文建议。只看含拉丁字母的结果。

## 栅格化

- `type.rasterize` 把文字层变像素层；`type.convertToShape` 变形状层（id 不变）。
- 栅格化后的层在结构审计里如果还带文字前缀，会被判 `POSSIBLE_RASTERIZED_TEXT`（见 `psd-workflow.md`）。
- 按层或整份文档栅格化、智能对象与图层效果的差别、id 变化和验收方式见 `commands.md` 的「栅格化」。栅格化不保留可编辑性。

## 缺字体时的表现

- `type.create` 在返回里带 `warnings:["font 'X' is not installed; text may render using a fallback face"]`；导出时 stderr 也提示。
- `info` 的 `warnings` 会列出缺字体；PSD 往返后字体表可能重拼家族名。
- 修字体、装字体、授权的完整流程见 `fonts.md`；交付前必须解决，不能拿回退字体当成品。

## 可复跑验证

- 案例 32：`python <skill-dir>/examples/32-text-in-box.py`（水平居中、垂直居中两种做法、溢出、bounds 形状）。
- 案例 38：`python <skill-dir>/examples/38-text-replace-center.py`（区域内替换文字，改字和换行后各重新做一次双轴居中）。
- 案例 13、15：形状与文字海报、模板改稿中的文字编辑。
