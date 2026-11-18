# 能力矩阵（目标工序 × 落点 × 状态）

> 口径：由 `photocraft-cli` 0.23.1 的注册表核对 + `scripts/probe_capabilities.py` 实跑得出。
> **`unverified` 表示命令存在、参数已知，但行为没有实跑过**——可以照做，但不许在交付里当已验证结论写。
> `verified@0.23.1` 表示本条已在本机实跑并给出断言数值（证据在 `--work` 目录的 `probe-report.json`）。
> 落点：L0 原生注册表 / L1 WASM 插件 / L2 Python 侧车 / L3 技能脚本。

## 1. 主表

| # | 目标工序 | 落点 | 命令（0.23.1） | 状态 | 验收断言 |
|---|---|---|---|---|---|
| 1 | 显著性主体分割 | L0（L2 可提升） | `select.subject{sampleAllLayers,mode}`、`layer.removeBackground{layer,sampleAllLayers,refine}` | verified@0.18（经典算法，无置信度） | 看 `changed`/`coverage`，不看 `selected` |
| 2 | 发丝级 alpha | L0 半自动 / L2 | `select.refineEdge{smartRadius,refineStrokes,edits,output}`；L2 `estimate_alpha_cf` | **部分：硬边样张轮廓软边 68.1% 已验证；发丝级仅外部样张（100%/1.50%），样张不在包内，随包无法自查** | 包内只认"轮廓软边覆盖率 ≥0.5"；写"发丝级"必须自带发丝样张并留证据 |
| 3 | 去溢色 | L0 | `layer.matting.colorDecontaminate{amount,radius}`、`removeWhiteMatte`、`removeBlackMatte`、`defringe{width}` | verified@0.18（**alpha 不变**） | 边缘色相偏移 ≤阈值；alpha 逐像素不变 |
| 4 | 局部背景补丁 | L0 经典 / L2 门控侧车 | `edit.contentAwareFill{...,seed}`、`paint.patch`；L2 `sidecar/patch.py`（`opencv-telea`/`opencv-ns`） | **verified@0.23.1（seed 可复现；侧车 gate 外差 0）** | 门控外逐像素 diff=0；`gate ∩ subject alpha = ∅`；生成式引擎未接线 |
| 5 | 亚像素配准 | L0 | `edit.autoAlignLayers{registration:auto\|features\|intensity,interpolation}` | **verified@0.23.1（残差 0.12）** | 对齐后与原图差 ≤6/255；未对齐对照 ≥10 |
| 6 | LAB 曝光对齐 | L0 | `image.adjustments.matchColor{source,sourceLayer,luminance,intensity,neutralize}`、`levels{eyedropper}` | **verified@0.23.1（部分：色差 −37%）** | 统计匹配可缩色差；**精确一致要靠 `levels{eyedropper}`** |
| 7 | 底噪/颗粒匹配 | L0 + L2 估参 | `filter.noise.addNoise{amount,distribution,monochromatic,seed}`、`filter.gallery.grain{...}`、`filter.gallery.filmGrain` | **verified@0.23.1（addNoise seed 可复现；gallery.grain 同参可复现）** | 同 seed SHA 相同、异 seed 不同；σ 与参考区误差 ≤5% |
| 8 | 圆盘光圈景深 | L0 | `filter.blur.lensBlur{radius,shape(hexagon…octagon),bladeCurvature,rotation,depthMap,depthChannel,focalDistance,invert,brightness,threshold,noise,distribution,monochromatic,seed}` | **verified@0.23.1（部分：叶片/参数生效；二值 alpha 当深度图不能选择性对焦）** | 高光圆盘边缘形状与叶片数一致；传错通道名必须报错；**选择性对焦由"背景整层模糊 + 主体层叠回"实现，不靠 depthMap** |
| 9 | 32-bit 线性光 | L0 | `image.mode.bits32` → `edit.assignProfile{profile:"linear-srgb"}` → 滤镜 → **`edit.convertToProfile{profile:"srgb"}`** | **verified@0.23.1（配方级：depth=32；回转换后差 2.64）。交付件仍是 8 位 sRGB，`pipeline_portrait.py` 不调用这条链路** | 五臂对照：位深往返误差 0.00；线性路由差 2.64；漏回转换 40.9 |
| 10 | 保边基底/细节分解 | L0 | `filter.blur.surfaceBlur{radius,threshold}`、`smartBlur{mode}` + 频率分离（`gaussianBlur`→`applyImage{scale:2,offset:128}`→`LinearLight`） | **verified@0.23.1（surfaceBlur 参数敏感，见 §2）** | 重建 ≤1/255；强边保留 ≥0.85（需按阈值调 radius） |
| 11 | LAB 暗部 a*/b* 降彩噪、保 L* | L0 | `image.adjustments.levels{lightness,a,b}`（**已实跑**）；`curves` 分通道**仍 unverified** | **verified@0.23.1（仅 levels：色域内 ΔL=0.41、Δa=30.8、Δb=0.84）** | 三个指标同口径都在色域内掩码上算；`curves` 未实跑，不许按 `verified` 写 |
| 12 | 高光滚降 | L0 | `image.adjustments.shadowsHighlights{highlightAmount,highlightTone,highlightRadius,blackClip,whiteClip}` | **verified@0.23.1（削顶 2467→670，暗部 +35.6）** | 高光像素计数下降；暗部像素均值上升 |
| 13 | 眼位提亮 | L0 | `image.detectFaces{minScore}`（回 `landmarks`）+ 50% 灰中性层 `paint.dodge` | **verified@0.23.1（landmarks 可用）** | 提亮半径 ≤虹膜半径；ΔL 限幅 |
| 14 | 白平衡去杂色 | L0 | `levels{eyedropper:{point:"gray"}}`、`colorBalance`、`matchColor{neutralize}` | verified@0.18 | 参考区 a*/b* ≈0 |
| 15 | 高频微反差 | L0 | `filter.other.highPass{radius}` + Overlay、`unsharpMask{amount,radius,threshold}` | verified@0.18 | acutance 提升且无 halo |
| 16 | 建筑垂直线矫正（不裁切） | L0 | `filter.lensCorrection{vertical,horizontal,angle,straighten,edge:"edgeExtension",scale}`、`image.analysis.straightenLayer{crop:false}` | **verified@0.23.1（尺寸不变、四角有内容）** | 垂直线残余角度 ≤0.2°；画幅未被裁 |
| 17 | 三层非破坏装配 | L0 | 图层 + 蒙版 + 智能对象 + 图层复合/快照 | verified@0.18 | 层序/数量/混合模式与规格一致 |
| 18 | 对比图与分层 PNG | L3 | `doc.exportLayers`、`file.export.layersToFiles{dir,format,prefix,visibleOnly}` | **verified@0.23.1（2 顶层=2 文件）** | 文件数/尺寸/alpha；manifest 哈希 |

## 2. 首轮探针实测（2026-11-18，720×853 人像样张）

| 探针 | 结果 | 关键数值 |
|---|---|---|
| `lensBlur` | works | `blades`：hexagon→6、octagon→8；非法 `shape:"circle"` 被拒（退出码≠0）；画面确实模糊（均值差 >3） |
| `levelsLab` | works | 色域内像素（35.9%）上 **ΔL=0.41**、**Δa*=30.8**、**Δb*=0.84** —— 三个指标同口径；全量另有 dL 1.23 / da 25.3 / db 2.07（RGB 触边所致，仅作参考） |
| `refineEdge` | works（限棚拍硬边） | 判据改为**轮廓软边覆盖率 68.1%**（旧判据"全图半透明占比 1%"任何 1px 抗锯齿都能过）；全局软边 1.06% |
| `lensCorrection` | works | 输出尺寸不变；四角 40×40 斑块 std>1.5（`edgeExtension` 未裁画幅） |
| `contentAwareFillSeed` | works | 同 seed 两次 SHA256 相同、异 seed 不同 |
| `detectFaces` | works | 检出 ≥1 张脸且 `landmarks` 非空 |
| `bits32` | works | 转 32 位后 `info.depth == 32` |
| `addNoiseSeed` | works | 同 seed 逐像素相同、异 seed 不同 |
| `exportLayers` | works | 两个顶层图层 → 恰好 2 个文件 |
| `surfaceBlur` | works（参数敏感） | r2/thr6：高频降 6.16、**强边保留 91.6%**；r3/thr10：77.9%；r6/thr20：**52.1%**。threshold 必须相对边缘对比度取，别照默认值扫 |
| `shadowsHighlights` | works | 削顶像素 2467 → 670；暗部（L<40）均值 +35.6 |
| `galleryGrain` | works | 同参数两次 SHA256 相同（确定性），画面确实变化 |
| `autoAlign` | works | 副本平移 (5,4)px 后对齐：与原图差 **0.12/255**；不对齐对照 **13.17** |
| `matchColor` | works（部分） | 平均色差 41.6 → 26.0（**−37%**）；`intensity:200` 反向恶化到 **150.8** |
| `depthBokeh` | **fails（选择性对焦做不到）** | 叶片 7 成立；把主体 alpha 存成通道后：`invert:false` 人脸保留 **0.17%**、背景 0.22%（全糊）；`invert:true` **人脸 103.69% / 背景 106.27%**（都清晰）。另做过 24 组 `focalDistance×threshold` 本地扫参（数据未入包，仅作方向性判断）。结论：二值 alpha 当深度图无法选择性对焦 |
| `bits32Linear` | works | 五臂对照：位深往返误差 **0.00**；线性路由差 **2.64**；漏回转换 **40.9**。探针自身执行 `convertToProfile`，2.64 在包内有证据链 |

复跑：`python scripts/probe_capabilities.py --work <目录> [--only id1,id2]`

侧车两引擎（同一张硬边样张）：`photocraft.select.subject+refineEdge` → `soft_ratio 1.06%`、`degraded:true`；`pymatting.cfm+estimate_foreground_ml` → `soft_ratio 0.92%`、`degraded:false`。两者都未达 3% 门槛，原因是样张硬边，不是算子问题。

**发丝样张复测（2026-11-18，1024² 逆光飞发散，样张不在包内）**：`refineEdge` 轮廓软边覆盖率 **100%**、全局软边 **1.50%**；`matte.png` 目视细发丝完整保留。**这组数只能算外部观察，不进包内证据**：包内可复现的只有硬边样张的 68.1%。因此发丝级状态保持 **部分**，不标 `verified`；要对外写"发丝级"，交付时必须自带该样张并重跑入库。已知副作用：逆光边缘会留一圈极淡的光晕，需 `select.refineEdge{decontaminate:true}` 或手工收边。

**强散景下的"亮边"不等于抠图残留**：用 720×853 样张把主体蒙版向内收 3px 后重渲，外观**完全没变** → 说明那圈光来自原片亮部在 radius 28 下的扩散，属散景本身，不是 alpha 边缘带出的底色。判定方法：收边后外观若不变，就是光源扩散。

## 3. 明确做不了的（不要承诺）

| 事项 | 原因 |
|---|---|
| 生成式主体重绘 / 全图扩散 | 应用内无生成模型；插件沙箱无文件无网络，模型体积也放不进 |
| 任意尺寸/浮点卷积核 | `filter.other.custom` 只有 25 元 5×5 **整数**核 |
| 神经分割器 / 学习型 alpha（IS-Net/U2-Net） | 需 L2 侧车接模型权重，`models.lock.json` 为空；侧车现有的是**闭式 CFM（pymatting）与经典引擎**，不是神经网络抠像 |
| 单帧物理正确的深度/散景 | 只能估计；`lensBlur` 的景深图是引导，不是测量 |
| 插件做全帧邻域算子 | 24MP f32 RGBA 双缓冲 732 MiB > 512 MiB 上限；60 s 墙钟按 ~1e9 instr/s 只有约 2500 指令/像素 |

## 4. 未决项（验证前保持 unverified）

1. **插件 ABI 空白**：文档只指向外部 `docs/plugins.md`，本地与上游仓库都没有该文件；位深、能否回传指标都不明。
2. **指令预算读法**：文档原文是"每次调用 5000 万条指令加每样本 4000 条"，若为调用总量而非按像素，24MP 全图邻域算子全灭。
3. **`aces-cg`**：`formats.md` 列为内置 id，但 0.23.1 四个 profile 命令的内联枚举里没有它。
4. **发丝级 alpha 的包内复现**：硬边棚拍样张能证明"轮廓有连续软边"（68.1%）；发丝样张不在包内，100%/1.50% 那组数来自外部样张，随包无法自查。要写"发丝级"，交付前必须自带发丝样张重跑 `refineEdge` 并入报告。

## 5. 怎么把 unverified 变 verified

```powershell
# 1 取参数原文（别凭记忆写）
python <skill-dir>/scripts/params.py --exact layer.removeBackground
# 2 跑探针（自动带断言与证据）
python <skill-dir>/scripts/probe_capabilities.py --work <目录> --only refineEdge
# 3 断言通过后把本表状态改成 verified@0.23.x，并把数值写进第 2 节
```

## 6. 已实测的行为偏差（写代码前先看这三条）

| 现象 | 实测事实 | 应对 |
|---|---|---|
| `select.refineEdge{output:"layerMask"}` 想原地换蒙版 | 实际返回 `output:"newLayerWithMask"`，**新建一层带蒙版**；返回值里的层号与 `document.inspect` 里实际新建的层不一致（报 7、实际 6） | 别用它改已有图层的蒙版；要"新层+蒙版"就直接用它并删掉旧层，别按返回值去 `layer.select` |
| 三层合成后主体外圈有亮边 | 收边 3px 重渲外观不变 → 来自原片亮部在强散景下的扩散，**不是 alpha 残留** | 先做这个收边对照再下结论，别急着改抠像参数 |
| `surfaceBlur` 照默认值扫 | r6/thr20 强边只保 52%；r2/thr6 保 92% | threshold 按边缘对比度取；保纹理优先用频率分离 |
| 测深度驱散景"没变化" | 在**已经模糊过**的层上再叠深度模糊，输出几乎不变（探针首跑就踩了） | 深度探针必须从干净副本重做；`depthChannel` 传错名时 CLI 会报 `no alpha channel`，可用来确认通道真被读到 |
| 用主体 alpha 当深度图，主体被糊平或整图不动 | `invert:false` 全糊（人脸保留 0.17%）；`invert:true` 人脸 103.69% / 背景 106.27%（都清晰）。另做过 24 组 `focalDistance×threshold` 本地扫参（数据未入包，仅作方向性判断，不作为证据） | 二值 alpha 不是深度图。选择性对焦靠**分层**：背景副本整层模糊，主体层叠回；`depthMap` 只适合连续深度图（如真深度相机输出） |
| `matchColor` 加参数想更准 | `intensity:200` 把色差从 26.0 反向推到 150.8 | 它是统计式转移，默认值附近最优；要逐像素一致改用 `levels{eyedropper:{point:"gray"}}` |
| 32-bit 线性光导出后颜色明显不对 | `assignProfile linear-srgb` 后直接 `convert` 成 PNG，与 8 位渲染差 **40.9/255** | 必须成对：做完滤镜先 `edit.convertToProfile{profile:"srgb","intent":"relative","bpc":true}` 再导出；转换时会有 `32-bit float will be reduced to 16-bit` 警告，属正常 |
| 侧车 `--alpha` 传 RGBA 图做门控断言 | `Image.convert("L")` 读的是**亮度**，抠像图的 RGB 全不透明 → 误报"重叠 100%" | 读 `getchannel("A")`；`patch.py` 已改，断言因此才真正有效 |

## 7. 端到端案例（examples 42–44，均已跑通）

| 案例 | 做的事 | 关键断言 |
|---|---|---|
| `scripts/pipeline_portrait.py`（**一条命令**） | 三层 PSD + 分层 PNG + 并排对比 + 3 张 400% 放大 + `qc_report.json` | **9 项**：三层齐 / 主体有蒙版 / 分层导出 / **主体不透明区与原片 ≤4/255** / **补丁 bbox 完全落在 gate 内** / 并排 2×画幅 / 放大正好 4× / 非同一图 / 高频保留 ≥0.75；任一不过退 1。退出码：**0=通过、1=断言失败、2=输入或参数错误**（`--blur` 限 1..200） |
| `42-three-layer-portrait.py` | 背景散景层 + 门控补丁层 + 主体层 + 剪贴调色层 | 门控补丁的差异 bbox 必须落在门控矩形内（`inside()`）；主体层有蒙版；四层齐 |
| `43-sidecar-alpha-backfill.py` | 侧车出 alpha → 嵌入透明画布 → 存 `ALPHA_SUBJECT` 通道 → 导出分层 | manifest `schema/engine/degraded` 如实；通道可按名回读；导出层尺寸等于画布 |
| `44-qc-delivery-sheet.py` | 并排对比 + 400% 眼部/嘴部/边缘放大 + `qc_report.json` | 并排画布 = 2×画幅；放大图正好 4×；高频保留率 ≥0.75（低了按磨皮过度处理） |
