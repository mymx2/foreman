---
name: photocraft
description: |
  通过 PhotoCraft 做 PSD/pcraft 分层稿的图层级编辑自动化：新建规范稿与制图规范（画布尺寸、栅格间距、层级契约、命名层树），
  不规范 PSD 的结构规范化与视觉复刻，图层、选区、文字、滤镜编辑，栅格布局与自动对齐分布，
  文档结构与字体现状查询，缺失字体检索与替换，需要引擎命令参与的目录批量处理，两稿渲染一致性校验（像素级回归），
  分层稿交付归档，以及老照片修复、去物修补、抠图合成、抠图切图与资产导出。当用户要驱动 PhotoCraft、对 PSD 做上述操作，或对已渲染位图做抠图/裁边/资产导出时使用。
  不适用于：普通图片格式转换（直接用 CLI convert 即可，无需加载本技能）、
  Figma/浏览器内设计稿操作（走 chrome 或其他技能）、Python/PIL 纯代码绘图。
when_to_use: 'photocraft, PhotoCraft, PSD 制图规范, 新建规范稿, 怎么设计好一个 PSD, 画布尺寸, 栅格布局, grid 布局, 自动布局, 对齐分布, 参考线, 列网格, 间距摆放, 画布对齐, 层级契约, 图层命名规范, PSD 图层编辑, PSD 规范化, PSD 复刻, pcraft, 图层树查询, 层树整理, PSD 结构审计, 缺失字体, 字体替换, 字体补齐, 渲染一致性, 像素级回归, 分层稿交付, 老照片修复, 去物修补, 抠图合成, 抠图, 切图, 裁白边, 去白边, 资产导出, 图层导出, 多倍图, PhotoCraft 批量处理'
---

# PhotoCraft

GUI 桥接端口与 headless 会话是两个方法集不同的世界；文件读写永远走能力域方法，不走含磁盘路径的引擎命令。

## 环境定位（任何命令前先确认）

`photocraft-cli` **默认不在 PATH**，直接敲会报 `command not found`——这不是没装，是没加路径。按序定位：

1. `photocraft-cli --version`（在 PATH 时直接用）。
2. 不在 PATH 时按平台找安装目录的 `photocraft-cli.exe` / `photocraft-cli`：
   - Windows：`C:\Program Files\PhotoCraft\`、`%LOCALAPPDATA%\Programs\PhotoCraft\`；装过就有 `%APPDATA%\Photocraft\control.token` 与 `preferences.json`，这两个文件存在即证明装过。
   - macOS：`/Applications/PhotoCraft.app/Contents/MacOS/`、`/usr/local/bin/`。
3. 还找不到就用系统能力查（`list_apps`、`where`/`which`、`Get-ChildItem -Recurse -Filter photocraft*`），别靠记忆猜路径。
4. 找到后用**带路径的绝对路径**调用（如 `"C:\Program Files\PhotoCraft\photocraft-cli.exe" commands`），或把目录加进 PATH 再敲裸命令。

无法定位时才降级：GUI 会话靠 `scripts/photocraft-bridge.py` 的 `engine.commands`，headless 会话靠 `photocraft-cli mcp`。`--version` 只在 PATH 可用时才能敲，别拿它当安装证明。

完成标准：拿到了一个能执行的 CLI 路径，`photocraft-cli --version` 或绝对路径调用有版本输出（0.9.0 = `photocraft-cli 0.9.0 (c699e3cda, 2026-10-14)`）。

## Outcome Contract

- **Outcome**: 用户的 PhotoCraft 编辑意图（编辑、查询、导出、批量）或已渲染位图的抠图/裁边/资产导出完成，结果经过 inspect、文件、manifest 或退出码验证。
- **Done when**: 查询类任务的目标字段在 `document.inspect` 中可见；PSD 会话产出类任务的文件已落盘且 `app.save`/`doc.save` 的 `warnings` 为空或逐条解释；纯位图任务按下方纯位图例外以文件/hash/manifest/退出码为准；分层稿交付时另有同名描述文件、`fonts/` 副本（仅在授权允许再分发时）及哈希核对结果；无遗留测试文档。
- **Evidence**: PSD 会话任务看 `document.inspect` 目标字段、`app.save`/`doc.save` 的 `path` 与空 `warnings`、`jobs.list`；纯位图任务看输出文件、SHA256、`assets-manifest.json` 与退出码；交付目录另看描述文件、字体副本 SHA256 与来源比对结果；规范化任务另有 `audit-before/after.json`、`psd-compare` 报告与规范化记录。
- **Authorization**: 连接、查询、新建/关闭会话内测试文档可直接做。保存覆盖用户已有文件、`--in-place` 批量覆盖原件、`prefs.reset`、`prefs.set`（语言/主题/工具选项）、`app.quit`、`file.close*` 关闭用户文档、`ui.window.close`、应答未保存提示（`ui.dialog.confirm`）、`actions.play` 批量重放，先确认再执行；覆盖前备份目标文件。`type.replaceAllMissingFonts` 禁用。
- **纯位图例外**: 抠图/切图/裁边只处理已渲染位图时不需要 PhotoCraft 会话，Done 以文件落盘、hash、manifest 和退出码为准；`app.save`/`doc.save` 只约束 PSD 会话任务。

## When to Use

- 用户明说 PhotoCraft / Photocraft，或要求对 PSD/pcraft 文件做图层级编辑自动化。
- 查询 PSD 使用的字体（含缺失字体清单）、图层树、文档元数据。
- 文字图层缺字体、要找字体或换字体：`type.fonts` + `type.resolveMissingFonts` 定位，`scripts/fonts/hellofont-search.py` 检索字由目录。
- 批量转换/处理一个目录的图片且需要引擎命令（旋转、滤镜、调整）参与。
- 重写/重组后的渲染一致性校验（两个稿子逐像素比对）：`scripts/psd-compare.py`。
- 老照片修复、去物修补、抠图合成、版式制图：固定顺序与验收标准见 `references/retouch-composite.md`。
- 实际效果测试要不同尺寸图片：`scripts/fetch-asset.py` 按需下载落目录，来源与红线见 `references/test-assets.md`。
- 分层稿交付与归档：给稿目录补齐随稿字体副本（授权允许时）与 `<稿名>.md` 描述文件，规则见 `references/delivery.md`。
- 抠主体、去透明/纯色边、按图层或区域导出多倍图：规则见 `references/cutout-slicing.md`，裁边/命名/倍率用 `scripts/trim-export.py`。
- 收到不规范/单文件 PSD，要补字体、整理分组与命名、做规范复刻并证明视觉一致：按「规范化/复刻模式」走，规范见 `references/psd-normalization.md`，结构审计用 `scripts/psd-audit.py`。
- 按栅格/间距摆放元素、批量对齐分布、建参考线：按「自动布局模式」走（`layer.translate` / `edit.transform` / `layer.align.*` / `layer.distribute.*` / `view.newGuideLayout`）。

## Process

按任务取步，不要每次都走完 10 步：

| 任务 | 必走步骤 |
| --- | --- |
| 查询图层/文档/字体现状 | 1 → 2 → 3（只读） |
| 图层编辑、文字、滤镜、选区 | 1 → 2 → 3 → 4 |
| 字体缺失或替换 | 1 → 2 → 6 → 4 |
| 渲染一致性校验 | 2（查 convert 签名）→ 7 |
| 老照片修复、去物、抠图、制图 | 1 → 2 → 3 → 8 → 4（需要归档再走 10） |
| 分层稿交付归档 | 1 → 2 → 3 → 4 → 10 |
| 不规范 PSD 规范化/复刻 | 走下方「规范化/复刻模式」 |
| 纯位图裁切/切图导出 | 直接走「切图与资产导出」，不需要 PhotoCraft 会话 |
- PSD 图层/组抠图导出 | 1 → 2 → 3 → 8（语义抠图）→ 切图模式 |
| 纯批量转换（无编辑验证） | 2 → 4（CLI）或 1 → 2 → 5 |
| 栅格布局、对齐分布、建参考线 | 走「自动布局模式」 |
| 新建规范稿（从零起稿） | 走「设计制作规范」，规范见 `references/design-spec.md` |

1. **选会话**。先探测再动手：GUI 会话跑 `scripts/photocraft-bridge.py`（运行它；下称 bridge）的 `ui.inspect`，看返回的文档/窗口列表；headless 会话用 `session.list` 拿文档列表。编辑用户打开的文档只能在 GUI 会话做。无 GUI 或要无人值守批处理时，用 `photocraft-cli serve --port <port> --control-token-file <tokenfile> --automation-read-root <workdir> --automation-write-root <workdir>` 起 headless 会话（token/root 缺一不可，否则 auth 或文件访问 fail closed），bridge 加 `--port` 连它。两个会话的文档互不可见；headless 的文件方法集更宽（`doc.open/doc.save/doc.render`），GUI 桥接靠 `app.open/app.save`。
   完成标准：GUI `ui.inspect` 返回了目标文档/窗口，或 headless `session.list` 返回了文档列表且端口已应答 auth。

2. **查命令签名**。任何命令的参数先查注册表再写：bridge 发 `engine.commands`，或终端跑 `photocraft-cli commands --filter <text>`（909 条，`--json` 含完整参数描述）；按业务意图过滤（用功能词搜，不猜命令 id），细节先翻 `references/control-protocol.md` 对应小节。CLI 子命令与 flags 以 `photocraft-cli --help` / 子命令 `--help` 为准。`params` 必须是 JSON object，传数组/字符串/数字会被整条拒绝。
   完成标准：拿到了目标命令的参数描述原文，以原文为准拼参数。

3. **编辑与验证闭环**。用 `engine.execute {command, params}` 执行（不弹对话框，直接用默认值）；要交互对话框时才用 `ui.menu.invoke` + `ui.dialog.*`。每步编辑后立即 `document.inspect` 验证层树/属性/历史符合预期，失败就修，通过才进下一步；同一修法第二次仍失败就换方案的形状，不再微调参数。层树嵌套在 `children` 字段，文字图层的字体在 `text.font`。属性回显≠生效——混合模式、透明度、蒙版能让改动数学上无声消失；关键改动做渲染前后像素差探针：GUI 会话先 `app.save` 一个 checkpoint，再转 headless 用 `doc.open/doc.render`；headless 会话直接用 `doc.render`，渲染图交给 `scripts/psd-compare.py`。不要用 `ui.screenshot` 的窗口截图当像素级证据。验收双尺度：fit 看构图色彩、100% 看修补伪影。
   完成标准：inspect 返回的目标字段与用户意图一致。

4. **文件进出**。引擎命令里凡是带磁盘路径的（`file.open`、`file.save`、`file.saveACopy`、`file.openAs`、`file.export.*`、`layer.exportAs` 等）一律被拒，报 "uses ambient filesystem paths and is disabled"——报错是设计行为：能力域隔离。读写改走：GUI 桥接 `app.open {path}` / `app.save {path}`（相对 automation root 的相对路径；`app.save` 不带 path 只回写原 PSD/PSB/.pcraft）；headless 用 `doc.open/doc.save`；不走会话的纯转换直接 `photocraft-cli convert/run/batch`。回执里的 `warnings` 要读给用户（如"adjustment layer flattened"）。输出父目录须已存在；分层编辑先落可编辑母版（PSD/PSB/.pcraft）再导出平图。
   完成标准：`app.save`/`doc.save` 回执含落盘 `path` 且 `warnings` 已解释。

5. **长任务用作业**。所有 `filter.*`、`edit.contentAwareFill`、photomerge 等默认同步等待；要异步就 `engine.execute` 加 `wait: false` 拿 job id，轮询 `jobs.list` 到 done/failed/cancelled 再做后续编辑。作业运行期间它会锁住所属文档，相关命令报 "still running on this document"。超时或断连后先 inspect 文档与历史再决定是否重放——操作可能已完成，盲目重试会双份执行。批量不是事务：中途失败时前序步骤已进历史，先 inspect 现状再续做，不整体重放。
   完成标准：`jobs.list` 中无涉及目标文档的 running 作业。

6. **字体获取**。定字体先看现状：`engine.execute type.fonts {}` 拿已装清单、`type.resolveMissingFonts {}` 拿缺失清单。缺了或要换字体，先跑 `scripts/fonts/zitijia-free.py`（运行它）走免费商用直链——`fetch` 抓目录（download 前必须先有缓存）、`search` 过滤、`download <itemId>` 校验免费条目后落 zip 并安全解出 ttf 到 `<to>/<itemId>/`；要更大目录或字由生态时用 `scripts/fonts/hellofont-search.py`（运行它，关键词加标签 id，如 `73` 免费商用、`15` 黑体，完整表在 `references/hellofont.md`），但字由字体只给候选与授权类型，文件得经客户端按账号授权落地。两条路都只碰免费/开源授权，付费条目不下载；落地路径与红线见 `references/hellofont.md`。字体存放位置以用户指定为准；用户没指定时推荐放字体根目录（用户目录下的 `fonts\`，即 `%USERPROFILE%\fonts`，目录形式、登记表字段与红线见其 README），先登记再装——这是推荐约定，不强制。启用看 CLI 能力：终端跑 `photocraft-cli --help`。0.9.0 当前没有 `--font-dir`，`engine.commands` 也没有 `type.registerFonts`；没有时用随包 `scripts/fontctl.ps1 -FontRoot <字体根目录>` 按登记表做系统级临时安装/卸载（仅 Windows；GUI 与 headless 都走它），装完重启 PhotoCraft 才可见。将来 `--help` 出现 `--font-dir` 时，headless 直接 `--font-dir <字体根目录>` 或会话内 `type.registerFonts {path}`（以 `engine.commands` 是否列出为准），进程退出即失效、不落系统。fontctl 需要字体根目录有 `README.md` 登记表（格式见 `references/font-root-readme.md`），登记表里的家族名要与 `type.fonts` 返回一致；先 `fontctl status`，已由系统安装的字体不要重复 `install`。缺登记表或工具时不要假装安装成功：GUI 会话明确告知无法临时安装，或让用户提供工具，headless 也只能走 fontctl/系统安装。禁用 `type.replaceAllMissingFonts`：它会批量替换，绕过逐字确认。下载的字体文件默认落临时目录，安装前用 `--to <字体根目录>/<家族名>` 或手动搬到字体根目录并登记。装好/注册后回 `type.fonts` 确认字体名可见，再往 `text.font` 写。缺失字体阻止交付，不自动替换近似字体——要换先出候选让用户定。已获取的字体优先复用用户目录 `fonts\` 里的现成文件，不重复下载；稿目录的 `fonts/` 副本按第 10 步在授权允许时随稿交付。
   完成标准：目标字体在 `type.fonts` 中可见且名字一致，或已交付候选清单与授权状态等用户决策。

7. **一致性校验**。重写、重组过的稿件要证明渲染没变，跑 `scripts/psd-compare.py`（运行它）`<旧稿> <新稿>`（依赖 Pillow）：同一引擎（`photocraft-cli convert`）把两边渲染成 PNG，先比渲染 PNG 的哈希（一致即逐像素一致），不一致再逐像素 diff 并出差异图，报告一行 JSON。`--fuzz` 是每通道容差，默认 0（严格一致），对比在 8-bit RGBA 空间；输入直接给 PNG 时跳过渲染。同引擎重写预期零噪声、严格一致，只有跨工具的稿子（如 Photoshop 直接导出）才给容差。
   完成标准：报告 `result` 为 `identical` 且 `warnings` 为空或已转述；`differs` 时已交付 `diffImage` 与差异像素比例并定位到差异区域；画布尺寸不同直接判 `differs`，不出像素差图。

8. **修复与制图**。修复稿按固定顺序走：先修结构（去尘/划痕/撕痕）→ 色调对比 → 最后才是上色增强；调整一律全局→局部，去噪在最终锐化前（完整顺序见 `references/retouch-composite.md`）。动手前先出诊断清单、划定硬锚（人脸、解剖结构、文字、logo、产品设计、地标禁动）与软锚，修补只碰软锚；烘焙类滤镜优先 `filter.convertForSmartFilters` 或转智能对象留回改余地，做不到就复制图层在副本上做。抠图走取选区→反选→转蒙版，不擦像素；羽化按边缘类型和输出尺寸调（2px 只是通用起点），细则见 `references/cutout-slicing.md`。人像自然度、上色克制、构图与导出细则见 `references/retouch-composite.md`。
   完成标准：双尺度验收通过（fit 构图色彩、100% 无修补伪影），硬锚未被擅动或已获确认，产物为分层母版+平图双件（除非用户只要其一）；保存按第 4 步，交付归档按第 10 步。

9. **测试素材**。实际效果测试要图就跑 `scripts/fetch-asset.py`（运行它）按尺寸落目录：占位、照片（`photo` 路由）、头像、骨架、场景、码形走 devimg.cn，照片备选 picsum、色块备选 placehold.co，真图质感走 Pexels（`PEXELS_API_KEY`，限 200 次/时）或 Pixabay（`PIXABAY_API_KEY`，约 100 次/分，含矢量插画）。进复现案例与对比基线的图一律带 `--seed` 钉结果；占位类只用于测试不进成品。来源、限额与授权红线见 `references/test-assets.md`。
   完成标准：目标尺寸图片落盘（位图中心裁切；SVG 保持原尺寸），报告含来源与授权状态，seed/参数可复现。

10. **交付归档**。分层稿目录是交付单元：`<稿名>.psd` + `<稿名>.md` + `fonts/`（授权允许时）。描述文件按 `references/delivery.md` 模板写全：文件信息与 MD5、图层结构、逐层文字规格、字体依赖（图层→家族名→PSD 字体表记录→字体文件→授权）、可变量、渲染/对齐证据、已知限制、复验命令。字体副本只放该稿实际使用的家族，逐个核对 SHA256 与来源记录；来源或商用授权不明的字体不进交付。只有授权明确允许再分发/嵌入时才复制字体文件；仅“免费商用”不构成再分发许可。不能复制时，在描述文件记录家族名、授权凭证与获取方式，并写明未随附原因。
   完成标准：每份分层稿都有同名描述文件；授权允许时 `fonts/` 覆盖全部字体家族且哈希全绿，不允许时已写明未随附原因。

## 规范化/复刻模式

输入是不规范的单个 PSD，目标是一份结构可维护、渲染一致的规范稿时走这条分支；细则见 `references/psd-normalization.md`。

1. **审计原稿**。原稿只读，先记 SHA256；跑 `scripts/psd-audit.py audit <原稿> --json > <稿目录>/audit-before.json`（运行它），再在 PhotoCraft 打开，用 `document.inspect` 与 `type.resolveMissingFonts` 核对层树、文字和真实缺失字体。完成标准：问题清单与重建计划已出，原稿未被修改。
2. **冻结视觉基线**。用同一引擎把原稿渲染成 PNG（headless `photocraft-cli convert` 或 `doc.render`），保存到 `<稿目录>/baseline.png` 并记 hash。完成标准：基线图可复跑，后续对比都以它为准。
3. **设计目标层树**。按 `references/design-spec.md` 的节点树（`页面_`/`区块_`/`组件_` + 元素前缀）写旧层→新组映射；标出合并层、栅格化文字、缺源素材、无法恢复项。完成标准：每个原层都有归属或例外说明。
4. **另存并重建**。用 `app.save {path: "<稿目录>/<稿名>_规范.psd"}` 另存规范稿，确认当前文档已指向它，记录原稿/规范稿 SHA256；建组、改名、移动层、转智能对象、补蒙版/调整层，每批改动后 `document.inspect` 复核。完成标准：层树符合规范，文字仍可编辑，原稿 SHA256 未变。
5. **补字体并回写**。`type.resolveMissingFonts` → 候选 → 用户确认 → 安装/注册 → 在规范稿上写 `text.font` → `type.fonts` 复核；记录原字体、实际字体、授权和视觉差。禁用 `type.replaceAllMissingFonts`。完成标准：文字层无缺失字体，或替换已获用户确认并记录。
6. **视觉验收**。`python scripts/psd-compare.py <原稿渲染> <规范稿渲染> --out <稿目录>/psd-compare-out > <稿目录>/visual-diff.json`，目标 `identical`；有差异逐像素定位并修复；跨工具来源才给 `--fuzz` 并写明原因。另做 fit/100% 双尺度目检。完成标准：一致，或差异已解释并被接受。
7. **结构验收**。`python scripts/psd-audit.py audit <规范稿> --strict --json > <稿目录>/audit-after.json`，要求无 CRITICAL/HIGH/MEDIUM；再跑 `compare <原稿> <规范稿> --strict` 记录前后指标。完成标准：strict 通过，LOW 逐条有结论。
8. **交付**。按 `references/delivery.md` 输出规范稿、描述文件、`fonts/`（授权允许时）、audit-before/after、视觉对比 JSON/diff 与规范化记录；原稿与规范稿分开保存。完成标准：交付目录可独立复验。

## 切图与资产导出

先判断是语义抠图、内容裁切还是资产导出；可以串联，验收不同。细则见 `references/cutout-slicing.md`。

1. **确认 spec**。记录用途、背景、边缘类型、输出格式/倍率/padding/命名/alpha/色彩，以及「画心还是含纸边」、投影/配件是否并入。资产名、尺寸、倍率、颜色、格式都来自用户 spec，不写死。纯位图任务不需要 PhotoCraft 会话；PSD 任务先记源 SHA256，只写 `<稿名>_切图.psd` 或独立目录。
2. **语义抠图**。复制工作层，选区→蒙版，不擦像素；硬边/软边/半透明/投影按边缘类型选羽化和边缘策略（数值是起点，不是固定值），`document.inspect` 复核蒙版。完成标准：alpha/蒙版存在，主体完整，浅色/深色/棋盘格三种背景看边缘无白边/halo；透明占比不能只来自 padding。
3. **内容裁切**。有 alpha 用 alpha bbox；无 alpha 用用户给的背景色+容差或手动 bbox；`scripts/trim-export.py`（运行它）做裁边、padding、多倍率、命名和格式，或 PhotoCraft 手动裁剪。`trim bg` 遇到透明像素会拒绝，改用 alpha；米白/白色纸本的纸边不能只靠背景色分离。完成标准：bbox 正确、padding 符合 spec、四边没有整行/整列纯背景残留，且不切主体/印章/签名。
4. **资产导出**。纯位图直接 `trim-export.py`；PSD 先区分整幅还是单层/组：整幅用 `doc.render {index?, maxSide:0, path:"<稿目录>/<渲染图>.png"}`（默认 1024、上限 2048px/5MiB；0.9.0 实测源最长边 >2048 时 `maxSide:0` 会报 preview side exceeds 2048，超限用 convert/分组；不带 path 只回 base64），单层/组用 headless `doc.exportLayers {dir:"<目录>"}`（0.9.0 实测可用，组导出为一个合成 PNG，要逐叶需隔离/隐藏或 convert；运行时 `methods` 为准，serve --help 可能只列方法名；先用 `app.save` checkpoint 再转 headless，不用 `layer.exportAs` 的 ambient 路径）。命名/倍率/格式按 spec，输出目录独立，不覆盖输入。manifest 默认在 `--out` 内；交付时用 `--manifest <稿目录>/assets-manifest.json` 放到根目录，写完不要移动；用 `--source-document` 记 PSD/源稿，用 `--note` 记画心/纸边/投影决策。完成标准：文件数/命名/尺寸/alpha/格式可对账，manifest 可复跑且 `failures` 为空。
5. **验收**。抠图边缘 100% 看浅/深/棋盘格，并看 `sourceHasAlpha`/`sourceTransparentRatio`/`sourceAlphaBBox` 与 `alphaBBox`；`contentTransparentRatio` 为 0 是硬边裁剪的正常结果，`paddingOnlyAlpha` 只说明最终透明来自 padding，不能单独否定有源 alpha 的抠图。裁切看 bbox/padding 和纸边策略；导出看尺寸/命名/alpha/manifest 与 `failures` 为空；整幅合成用 `psd-compare.py`，资产先贴回原画布再比。完成标准：spec 全对，边缘无白边/halo，原稿和母版保留。
6. **交付**。切图/资产放 `assets/`，清单放 assets 的父目录 `assets-manifest.json`（用 `--manifest` 指定），原稿、母版、中间图分开保存，不覆盖。完成标准：`assets-manifest.json` 的路径/哈希/bbox/参数与实际文件对账、`failures` 为空，画心/含纸边与投影策略已写入描述文件。

## 设计制作规范模式

**从零新建规范稿**时走这条分支，规范见 `references/design-spec.md`（画布尺寸表、栅格与间距刻度、层级契约、命名、层树、文字、布局执行、验收）。

路由边界：`design-spec.md` 回答**做成什么样**，`psd-normalization.md` 回答**怎么把烂稿修成规范稿**。已有稿子的质量判定属于规范化/复刻模式（先审计再修），不重复走本模式。两者目标结构一致，冲突处以 design-spec.md 为准。

1. **先拿 spec**。画布尺寸、列数、margin、gutter、命名模板、交付目标（是否进引擎）都要问清。**项目 spec 优先于规范默认值**，不要拿规范覆盖用户给的数值。
2. **算栅格**。`python scripts/layout-design.py calc --width <W> --margin <M> --gutter <G> --columns <C>`（运行它）出列宽、步距、列起点与右余量。列宽取 8 的倍数让步距合规，别自己凑。
   完成标准：报告 `pitchOn8pt` 为 true，`allOn8pt` 为 true。
3. **建组（从底向上）**。按节点树建组（`区块_` → `组件_` → 元素）。建层时新建层默认落在当前层上方，所以底层（背景、底色）先建，上层（卡片、标题）后建。
   **只用实际要用的组**：空组会被 `psd-audit.py` 判 HIGH（`EMPTY_GROUP`），未使用的类别直接不建。
4. **建内容层，然后必须 `moveTo into`**。这是最容易漏的一步：**新建层默认落在当前选中层的同级，不会自动进入组**。即使先 `layer.select` 选中组再 `layer.new.layer`/`type.create`，新层也是与组平级。每建一层都要补一条
   `layer.moveTo {layer:<新层id>, target:<组id>, position:"into"}`，
   否则根层散落，`psd-audit.py` 和 `check` 都判 HIGH。
   `type.create` 的 `x`/`y` 是基线锚点，实际 bounds 的 x 会偏几像素，摆位前以 `doc.inspect` 的 bounds 为准。
5. **验收**。`doc.inspect` 存成 JSON，跑 `python scripts/layout-design.py check --spec <spec.json> --inspect <inspect.json>`（运行它）。它查根组命名（应以 `页面_`/`区块_`/`参考_`/`版本_` 开头）、命名（默认名/同级重名 = HIGH，副本后缀 = MEDIUM）、空组（HIGH）、根层散落（HIGH）、隐藏层位置、x 是否落在栅格列、y 与间距是否为 8pt 倍数。
   **spec.json 要带 `height`**：铺满画布的底图层（`[0,0,W,H]`）靠它识别并豁免栅格检查，否则底色会被误判「x=0 不在栅格列上」。
   完成标准：退出码 0，或 MEDIUM/LOW 逐条有结论。
6. **收尾**。结构另过 `scripts/psd-audit.py audit --strict`（读 PSD 文件，与 check 的输入源不同、不能互相替代），视觉过 `psd-compare.py`。保存用 `doc.save {path}`，`warnings` 必须为空或逐条解释。

## 自动布局模式

需要按栅格/间距摆放元素，或让一批元素自动对齐分布时走这条分支。PhotoCraft 没有 Figma Auto Layout 那种「容器自动重排」，但**几何基元齐备**：能算坐标、能写回、能对齐分布、能建参考线。布局是「算 + 写 + 验」，不是靠容器。

### 基元

`doc.*`（`doc.new`/`doc.inspect`/`doc.render`/`doc.save`）是 **headless `serve` 的会话方法**，不是引擎命令 —— 喂给 `engine.execute` 会报 unknown command。引擎命令里对应的那个叫 `document.inspect`（要在 GUI 或经 `engine.execute` 包裹使用），`doc.new`/`doc.render`/`doc.save` 则只有会话方法。

| 命令 / 会话方法 | 参数 | 用途 |
| --- | --- | --- |
| `layer.translate` | `{layer, dx, dy, units:"px"\|"pt", target:"pixels"\|"mask"}` | 相对位移。**绝对定位的主力**：`dx = 目标x - 当前x` |
| `edit.transform` | `{layer, rect:[x0,y0,x1,y1]（源框，不单独使用）, quad:[[x,y]×4]（目标四角）, matrix:[a,b,c,d,e,f], scaleX%, scaleY%, rotate, dx, dy}` | 精确摆位、缩放、旋转。**`rect` 只是源框，必须配 `quad`/`matrix`/`scaleX` 之一**，单传 `rect` 报 "pass `quad` …, `matrix`, or `scaleX`…" |
| `layer.align.topEdges` 等 6 条 | `{to:"auto"\|"layers"\|"selection"\|"canvas"}` | 6 向对齐。`to:"canvas"` 对齐画布，做页边距用这个 |
| `layer.distribute.*` 共 8 条 | `{}` | 等距分布（水平/垂直/六向边缘与中心） |
| `view.newGuide` | `{orientation, position}` | 单条参考线 |
| `view.newGuideLayout` | 布局参数 | **批量建栅格参考线**，做列网格用这个 |
| `document.inspect` / `doc.inspect` | — | 读层树与 bounds，布局前必须先读现状 |

`layer.moveTo` 是层序（父子/上下），不是几何坐标；改几何用 `layer.translate` / `edit.transform`。
**但 `moveTo` 的 `into` 也是唯一能把层放进组的命令**——新建层不会自动进组，见「设计制作规范模式」第 4 步。

### 流程

1. **定栅格**。向用户确认：画布尺寸、列数、margin、gutter、间距刻度（推荐 8pt 体系 4/8/12/16/24/32/40/48/64）。未指定时按 8pt 体系给建议值，不得写死——spec 来自用户。
   先 `view.newGuideLayout {columns, width, gutter, margin, clearExisting:true}` 铺参考线。
   **`width` 是单列宽，不是画布宽**。传画布宽会报 "count, size and gutter must fit inside the target margins"。
   返回 `{"horizontal":n,"vertical":n}`。参考线**不出现在 `doc.inspect`，也不出现在 `doc.render`**，headless 下无法用渲染验收，只能信返回的条数。
2. **读现状**。`doc.inspect` 拿每层的 bounds，**格式是 `[x, y, w, h]`**（嵌套在 `children`）。没有 bounds 就没有布局，先确认字段存在。
3. **算坐标**。**必须跑 `scripts/layout-design.py calc`**，不要手推公式。列宽要让**步距 `(colW+gutter)` 是 8 的倍数**；只做向下取整会在 1440/120/24/12 这类配置上产出 120/222/324 的参差列起点，`check` 会判不合格且报错不指向根因。
   公式（脚本已实现，此处仅作说明）：
   - `columnWidth = (frameWidth - margin*2 - gutter*(columnCount-1)) / columnCount`
   - 第 i 列 `x = margin + (columnWidth + gutter) * i`
   - **元素宽度只能取「跨 n 列」的值**：`width = columnWidth*n + gutter*(n-1)`。`calc` 会列出全部合法宽度。宽度不符时 x 仍可能对齐，但右边界会越出列线。
   - gutter 不是 8 的倍数时脚本会反向补偿列宽让步距合规（1200/80/20/12 → 列宽 68、步距 88）。步距实在无法合规时脚本会警告，此时应把 gutter 改成 8 的倍数。
4. **写回**。`layer.translate {layer, dx: 目标x-当前x, dy: 目标y-当前y}`；要改尺寸或精确摆四角时用 `edit.transform {rect/quad/matrix}`。语义相关的元素先打组再摆，别散着移动。
5. **选区与对齐兜底**。`layer.align.*` / `layer.distribute.*` 作用于**图层选区**：用 `layer.select {layer:id}` 起选、`mode:"add"` 逐个累加（参数名是 `layer` 单数，传 `layers` 数组报 missing `layer`）。算完后用 `{to:"canvas"\|"layers"\|"selection"}` 校正残余误差——算法算的是理论值，对齐命令过的是实际 bounds。操作前先 `select.deselect` 清掉像素选区（`edit.fill` 后选区会残留；`select.none` 不存在，正确命令是 `select.deselect`），残留选区会让几何命令行为异常。
6. **验收**。每批改动后 `doc.inspect` 复核 bounds 与目标一致；关键布局做渲染前后像素差探针（`doc.render {maxSide:0, path}` 落盘后交 `scripts/psd-compare.py`）。**属性回显≠生效**：蒙版、混合模式、智能对象会让几何改动看起来生效实际没落，必须 inspect 复核。

完成标准：每层 bounds 与目标值误差为 0（或已对齐命令校正），spec 全对，原稿 hash 未变。

### 尺度与限制

- **布局是静态结果，不是活容器**。PhotoCraft 没有 Figma 的 HUG/FILL、没有响应式约束、没有 `layer.setBounds` 这类直接写 bounds 的命令——坐标只能靠 `translate` 的相对量或 `transform` 的变换推算。改了内容尺寸，布局不会自动重排，得重算重摆。
- **没有 z-index 数值体系**。层级就是层树顺序，改层级用 `layer.moveTo {target, position:"above"|"below"|"into"}`，只能用相对位置表达顺序。
- `layer.align.*` 与 `layer.distribute.*` 作用于**当前图层选区**，摆位前先确认选中的是要摆的那些层。
- 批量布局超过 256 步要分批（批量步数上限 256）。

## Common Rationalizations

- "file.save 报错说明安装坏了" — 这是设计行为；能力域方法（app.save/doc.save）才是正道。
- "GUI 端口和文档里 serve 的方法一样" — 不一样；GUI 桥接只有 engine.execute/engine.commands/jobs.list|cancel 和 ui.* / app.* / prefs.* 等，`doc.*` 是 headless 专属，报 unknown method 就换 `engine.execute` 包裹引擎命令。
- "参数差不多直接写" — 参数校验是全有或全无，一处类型错整条拒绝；先查签名。
- "工具名对上了就是对的后端" — 后端身份靠 `ui.inspect`/`session.list` 与实测状态判定，工具名不作数。
- "视觉一致就说明 PSD 没问题" — 像素一致只证明输出一致；层树可能仍然不可维护，规范化必须同时过结构审计。
- "原稿太乱，直接在原稿上改" — 原稿只读，另存规范稿；否则无法对照和回退。
- "`photocraft-cli` 敲不出就是没装" — 默认不在 PATH，不是没装；先按「环境定位」找安装目录。
- "PhotoCraft 没有 Auto Layout 所以做不了栅格" — 容器自动重排确实没有，但 `layer.translate` + `edit.transform` 能精确写坐标，`layer.align.*`/`layer.distribute.*` 能对齐分布，几何基元是齐的。
- "布局摆完就完事" — 静态结果不等于活容器；内容尺寸一变就得重算重摆，别承诺响应式。
- "对齐完了不用复核" — 蒙版、混合模式、智能对象能让几何改动静默失效，必须 `document.inspect` 复核 bounds。
- "规范是通用真理，照抄就行" — 默认值来源多为行业通行做法，不是官方标准；项目 spec 优先。
- "列宽向下取整就够了" — 不够；要让**步距**(colW+gutter) 是 8 的倍数，否则列起点参差不齐。
- "结构审计过了就不用查布局" — 审计查层树，布局要查 bounds 是否落在栅格列上，两码事。
- "布局摆完就是成品" — 还得过结构审计、视觉比对、交付归档，缺一项不算完成。
- "选中组再建层，层就进组了" — 不会；归属和插入位置是两回事，必须 `moveTo into`。
- "按节点树把所有层级都建上更保险" — 空组是 HIGH，未用到的层级不建。
- "`layout-design.py check` 过了就行" — 它读 inspect JSON，`psd-audit.py` 读 PSD 文件，维度不同；两者都要过。
- "x 对齐了就是对齐了" — 还要看宽度；宽度不合法时右边界越线，视觉上照样没对齐。
- "改尺寸用 transform 微调更省事" — quad 有插值误差（会冒出 329/330）；尺寸要求精确时重画更可靠。

## Red Flags

- 未经 inspect 验证就声称编辑完成。
- 对用户打开的文档使用 headless 会话（改的是另一个世界的副本，用户窗口毫无变化）。
- 在命令参数里塞绝对路径绕过能力域。
- 批量 `--in-place` 或覆盖保存前未确认。
- 缺字体时擅自换近似字体交付。
- 用像素一致代替结构审计，或规范稿仍有默认名/空组/根层散落。
- 在客户原稿上直接重建、覆盖原稿，或用无 path 的 `app.save` 回写原稿。
- 用 `type.replaceAllMissingFonts` 批量替换缺失字体。
- 切图时写死尺寸/倍率/命名/背景色，或把投影/配件静默合并。
- 导出资产覆盖原图或母版。
- 擅动硬锚区域（人脸、文字、logo、产品轮廓），或对上色/补全不作推断声明。

## Verification

1. 每次编辑后 `document.inspect` 对应字段可见变化（层、属性、历史状态数）；修复/制图另做双尺度看图（fit 构图色彩、100% 伪影）与像素探针复核，探针改过状态的已复原或已报出。
2. 保存后回执 `path` 存在、`warnings` 为空或已转述。
3. 收尾 GUI `ui.inspect` / headless `session.list` 确认没有遗留的临时测试文档。
4. 修改 `scripts/photocraft-bridge.py` 或怀疑本机环境异常时，跑 `scripts/test-bridge.py`（运行它，自带 fake control server，无需 PhotoCraft）；全绿再继续，任何失败先看 stderr 与对应用例。
5. 改过 CLI 用法后做小画布往返自检：`run --new` 起小图执行目标命令 → `convert` 出 PNG → `info` 核对（子命令与 flags 以 `photocraft-cli --help` 为准，不凭记忆拼）。
6. 改过 `scripts/psd-compare.py` 后用 `run --new` 造一对相同稿、一对改动稿自检：相同对报 `identical` 且退出码 0，改动对报 `differs`、出 `diffImage` 且退出码 1。
7. 改过 `scripts/layout-design.py` 后自检：`calc --width 1440 --margin 120 --gutter 24 --columns 12` 必须输出列宽 72、步距 96、列起点全落在 8pt（该配置若向下取整成 78，步距 102，列起点会参差不齐）；`calc --width 1200 --margin 80 --gutter 20 --columns 12` 需输出步距 88 的补偿结果或明确警告。`check` 对三份样本分别给出：只有 LOW 问题 → 退出码 0、根组命名不合规 → 默认退出码 0（MEDIUM 不算失败）、`--strict` 退出码 1、空文档 → CRITICAL 且退出码 1。跨父级同名层不得误报。
8. 改过 `scripts/psd-audit.py` 后自检：对成品 PSD 跑 `--strict --json` 应 `strictOk: true`；`--max-depth 1 --json` 应报 `DEPTH_EXCEEDED`，不传 `--max-depth` 不应报；`POSSIBLE_RASTERIZED_TEXT` 对「组件内像素层命名带 `文字_`」样本必须触发。
9. 改过契约（`psd_contract.py` / 两脚本的层级判定）后跑 `python scripts/test-contract.py`（在技能目录下运行它）：18/18 通过才继续；有 FAIL 先修契约判定。
10. 交付目录自检：每份分层稿有同名 `.md`，`fonts/` 覆盖稿内全部字体家族且 SHA256 与来源记录一致；不能证明允许再分发的字体不复制并在描述文件写明；描述文件里的 MD5 与验证数据可复跑。
11. 规范化/复刻后：`scripts/psd-audit.py audit --strict` 规范稿无 CRITICAL/HIGH/MEDIUM，LOW 已逐条解释；`compare --strict` 记录原稿→规范稿的前后指标；`psd-compare.py` 原稿渲染与规范稿渲染 `identical`，或差异已解释；交付含 audit-before/after、visual-diff 与规范化记录，原稿 SHA256 未变。
12. 切图/资产导出：dimensions/命名/alpha/格式符合 spec；100% 看边缘无白边/halo；bbox/padding 正确；`sourceHasAlpha`/`sourceTransparentRatio` 或真实蒙版证明是抠图，`contentTransparentRatio` 为 0 属正常；`assets-manifest.json` 的 `failures` 为空、哈希/bbox 与实际文件对账；原稿/母版 SHA 未变。

## Hard Rules

- 每条 TCP 连接的第一个请求必须是 `auth`（token 64 位 hex）；bridge 脚本已实现，勿手写跳过。
- 端口探测模式会依次向 7878–7881 尝试，并把 token 发给每一个被尝试的监听进程，直到 auth 成功；不信任本机环境时显式 `--port` 或 `PHOTOCRAFT_CONTROL_PORT` 指定；多实例并行各给独立端口，不共用探测。
- `params` 只能是 JSON object、省略或 null。
- 凭据不进命令行参数、不打印、不提交；从 token 文件或环境变量读。
- 字体文件获取只走正规渠道（字由客户端激活、官方下载或明确开源授权）；不写、不跑绕过授权的字体抓取。
- 随稿字体副本必须能追溯到来源与商用授权，且授权允许再分发/嵌入；来源不明、授权不明或哈希不符的副本不进交付。
- `prefs.reset`、`app.quit`、`file.close*`、应答未保存提示和 `actions.play` 按破坏性操作处理，先确认。
- 批量步数上限 256；headless 预览边长上限 2048px。
- 规范化时原稿只读，规范稿另存为 `<稿名>_规范.psd`；不覆盖、不删除原稿，结束重算原稿 SHA256。
- 像素一致不等于结构规范；规范化稿必须过 `scripts/psd-audit.py --strict`，CRITICAL/HIGH/MEDIUM 为 0。
- 节点树下元素用类型前缀命名（`文字_`/`图标_`/`背景_` 等）；平图/合并层按”复刻自平图”记录，不冒充原始层。
- `type.replaceAllMissingFonts` 禁用；要换字体逐层写 `text.font` 并让用户确认。
- 字体安装前先 `fontctl status`；已由系统安装、但不在 fontctl 状态里的字体不要重复 `install`，先核对注册表/`type.fonts`。
- 切图/裁边不得切到主体、印章、签名、文字或产品轮廓；padding、尺寸、倍率、格式、命名都按用户 spec，不写死。16-bit/浮点源先转 8-bit，不允许静默截断。
- 切图命名模板必须含 `{ext}`；manifest 锁覆盖整个运行，`failures` 非空不得当成功；`--manifest` 相对路径按当前工作目录解析，交付时在稿目录运行或用绝对路径。
- `doc.render` 全尺寸受 2048px/5MiB、源文档 67,108,864 px 上限；超过就分块/转 convert/分组，不要硬套 `maxSide:0`。
- PSD 切图源只读，先记 SHA256；只写 `<稿名>_切图.psd` 或独立目录，结束复核原稿 hash 未变。
- PSD 图层导出走 `doc.render`/`doc.exportLayers` 等能力域方法；不用带 ambient 路径的 `layer.exportAs`。`doc.render` 默认 1024、上限 2048px/5MiB，源最长边 >2048 时 `maxSide:0` 会失败；`doc.exportLayers {dir}` 仅 headless，0.9.0 实测组导出为一个合成 PNG，逐叶需隔离或 convert。
- 投影/倒影/配件是否并入资产由用户决定，不静默合并或丢弃。
- 切图 manifest 默认 `assets-manifest.json`，路径/哈希/bbox/参数要与实际文件对账；不覆盖任何输入。

## Gotchas

| 现象 | 处理 |
| --- | --- |
| `unknown method 'document.inspect'`（GUI 桥接） | 引擎命令要包一层：`engine.execute {command: "document.inspect"}` |
| GUI 报 `unknown method 'session.inspect'` | GUI 没有 `session.inspect`：会话/窗口列表用 `ui.inspect`，headless 文档列表用 `session.list` |
| 保存/打开报 ambient filesystem paths | 换 `app.open`/`app.save`（GUI）或 `doc.*`（headless），路径相对 automation root |
| 图层树里找不到子层 | 嵌套字段叫 `children` 不是 `layers` |
| 文字图层字体名查不到安装状态 | 用 `engine.execute type.resolveMissingFonts {}` 拿缺失清单，`type.fonts` 拿已装清单 |
| `hellofont-search.py` 只回 `{"TimeStamp": ...}` | 关键词和 `--tags` 都没给；脚本会直接报错。只给关键词时不要传空 `--tags`，脚本会省略标签字段 |
| 要能直接落地的字体文件 | 用 `zitijia-free.py`（免费商用 zip 直链）；hellofont 只给候选，文件要经客户端授权 |
| 中文文件名解压后乱码 | zip 内是 GBK 编码；用 `zitijia-free.py download` 的安全解压，别用系统解压工具直接解 |
| hellofont 字体卡片有"下载"却拿不到 ttf | 网页只唤起字由客户端（`localhost:59527` / `hellofont://`），字体文件由客户端按账号授权落地，见 `references/hellofont.md` |
| 把目录里的 `ProductFileName` 写进 `text.font` 不生效 | 那是落盘文件名不是家族名；以 `type.fonts` 返回的字体名为准 |
| 0.9.0 用 `--font-dir`/`type.registerFonts` | 0.9.0 两者都没有；用 `fontctl.ps1 -FontRoot` 做系统级安装/卸载，重启 PhotoCraft |
| 字体根目录没有 README/fontctl | 不要假装安装成功；先补登记表/工具，或明确告知无法安装；0.9.0 没有无落盘的 headless 字体路径 |
| `type.replaceAllMissingFonts` 看起来能一键补齐 | 禁用：会批量替换，绕过逐字确认；逐层写 `text.font` |
| `fontctl status` 显示未安装，但注册表/应用里已有 | 系统或字由客户端装过；不要重复 `install`/`overwrite`，先核对 `type.fonts` |
| 规范化时用无 path 的 `app.save` | 会回写原稿；必须 `app.save {path: "<稿目录>/<稿名>_规范.psd"}` 并记录原稿 SHA256 |
| 像素工具点在文字/形状/智能对象/填充层上 | 弹"栅格化?"框：confirm = 栅格化+绘制两个历史步，cancel 不动手 |
| bridge 预览像窗口截图 | GUI 桥接的预览是应用窗口截图（`ui.screenshot`），文档渲染走 headless `doc.render` |
| 需要渲染/导出但 GUI 桥接缺对应方法 | 存分层 checkpoint，转 headless（`doc.save`/`doc.render`）继续 |
| 图层数/元素数对得上就当无损 | 数量相等不能证明无损；`warnings` 之外抽查关键属性 |
| 把 `filter.*` 结果当可编辑智能滤镜交付 | 可编辑性核验不了就按烘焙对待 |
| 笔刷参数单位拿不准 | hardness/opacity/flow 多为 0..1，仿制图章/修复画笔 hardness 为 0..100；以 `engine.commands` 参数描述为准 |
| 崩溃后想直接改文档数据目录 | 只用 `Recovery` 恢复，不手改 `tiles/`/`blobs/` |
| GUI 裸启动不知道端口 | PhotoCraft 自动选端口并把 token 写进其配置目录的 control.token；bridge 会探测 7878–7881。可用 `PHOTOCRAFT_CONTROL_TOKEN_FILE`/`PHOTOCRAFT_CONFIG_DIR` 或显式 `--port` 固定连接 |
| 中文文档名乱码 | 终端编码问题；用 `python -X utf8` 跑 bridge，别用管道转码 |
| 拿 PSD 文件哈希判重写前后一致 | 结构重写后 PSD 字节必不同；一致性以渲染出的 PNG 为准（`psd-compare.py` 的做法） |
| 两个稿子画布尺寸不同还硬比 | 尺寸不同直接判不一致，先统一画布再比 |
| 跨工具稿子报零星像素差异 | 跨引擎导出的 PNG 有合法抗锯齿噪声，给 `--fuzz`；同引擎渲染不该有噪声，有差异就是真差异 |
| 属性改完不验证就交付 | 混合/透明度/蒙版可让改动静默无效，关键改动做渲染前后像素差探针 |
| 修复/调整顺序倒置（先上色后修结构、先锐化后去噪） | 顺序固定：结构→色调→上色增强；去噪→最终锐化；全局→局部 |
| 烘焙滤镜直接上原图 | 优先 `convertForSmartFilters`/转智能对象留回改余地，做不到才复制图层在副本上做 |
| 抠图靠擦像素 | 取选区→反选→转蒙版，交付的是蒙版；羽化按边缘类型调（2px 只是起点） |
| 画作周边留白切不干净 | 有 alpha 用 alpha bbox；无 alpha 用用户给的背景色+容差或手动 bbox；`trim-export.py` 参数化处理 |
| JPEG 去背景后 bbox 偏大 | JPEG 压缩噪声；提高容差或改手动 bbox，或改用带 alpha 的 PNG |
| `doc.render` 导出的资产尺寸变小 | 默认 `maxSide=1024`；全尺寸显式 `maxSide:0`，并注意 2048px/5MiB 上限 |
| GUI 调 `doc.exportLayers` 报 unknown method | `doc.exportLayers` 只在 headless；先 `app.save` checkpoint，再转 headless。是否出现以运行时 `methods` 为准，`serve --help` 可能只列方法名；参数 build-dependent |
| 组节点 bounds 为 null 或负数 | 用可见子层 bounds 并集或选区 bounds，clamp 到画布；bbox 必须量在实际要 trim 的位图上 |
| 16-bit/浮点图裁切后全黑或过曝 | 脚本 fail closed；先转 8-bit 再做 trim/切图 |
| 纯位图没有 alpha，却想用 trim bg 抠图 | trim-export 只做几何裁切；先在 PhotoCraft 做蒙版并导出 RGBA，背景复杂时尤其不能靠颜色去边 |
| manifest 有 `failures` 还当成功 | 退出码 1 表示 partial/失败；验收必须 `failures` 为空，失败项逐条处理 |
| 重跑已有输出报“输出已存在” | 确认要覆盖时加 `--overwrite`；默认不覆盖 |
| `trim bg` 对透明图不裁 | 有透明像素时脚本会拒绝；改用 `--trim alpha` 或先压平背景 |
| 画心纸边/米白留白切不干净 | bg trim 只去纯色背景；纸边用 alpha/手动 bbox，或明确接受纸边 |
| 切图 manifest 对不上 | 默认 `assets-manifest.json`；用 `--manifest` 指定稿目录，`--manifest-mode` 控制合并/替换 |
| 衣物边缘发白/halo | 蒙版+边缘过渡检查，浅色/深色/棋盘格三种背景看 100%；不要用固定阈值硬抠 |
| 衣服投影/配件被一起切掉 | 投影、吊牌、配件是否并入资产由用户定，默认分开并记录 |
| 导出尺寸/命名不对 | 用 `--name-pattern`、`--scales`、`--format` 按 spec；批量看 manifest 对账 |
| PSD 多图层不知道怎么切 | 先用 `doc.render`/`doc.exportLayers` 导出位图，再交给 `trim-export.py`；不用 `layer.exportAs` 的 ambient 路径 |
| 批量修复跑完只抽查 | 逐张出 no_op/inconclusive/unrestored 清单，静默跳过算失败 |
| 测试占位图混进交付成品 | devimg/picsum/placehold 仅供测试；成品素材走 Pexels 等真实图库并留来源记录 |
| 只交 PSD 不带字体与说明 | 换机字体回落、文字重排；交付单元必须含描述文件；字体副本在授权允许时随附，否则写明未随附原因 |
| 字体表记录的字重与本机已装不一致 | 描述文件写明实际可用字重与回落行为，不只写家族名 |
| 视觉一致就认为 PSD 规范 | 像素一致只证明渲染；结构要过 `psd-audit.py`，HIGH/CRITICAL 为 0 |
| 直接在原稿上重建 | 原稿只读，另存规范稿；保留原稿 hash 与参考组 |
| 组件组里元素类型混杂 | 节点树下正常（组件内可以有文字/图标/背景）；只在元素层命名前缀体现类型 |
| 平图/合并层想恢复原层 | 恢复不了；按视觉复刻并记录“复刻自平图” |
| 补字体只装系统不回写 | 还要逐层写 `text.font` 并回 `type.fonts` 确认；缺字体未确认不交付 |
| `psd-audit` 报 FONT_NOT_INSTALLED 但应用里能看到 | 脚本读 PSD 字体表；安装状态以 `type.fonts`/`type.resolveMissingFonts` 为准。`--installed-fonts` 清单需含 PostScript 或 PSD 家族名，传普通家族名会误报 |
| `photocraft-cli: command not found` | 不在 PATH，不是没装；按「环境定位」找 `C:\Program Files\PhotoCraft\photocraft-cli.exe` 或用绝对路径调用 |
| `layer.moveTo` 挪不动位置 | 它改的是层序（父子/上下），不是几何坐标；改位置用 `layer.translate` 或 `edit.transform` |
| 想直接写 `layer.bounds`/`layer.setBounds` | 没有这两个命令；坐标靠 `layer.translate` 的相对量或 `edit.transform` 的 `rect`/`quad`/`matrix` 推算 |
| `layer.align.*` 对齐结果不对 | 它作用于当前选区；先确认选中的是要摆的层，`to:"canvas"` 才对齐画布 |
| 栅格摆完元素位置差几像素 | 算法算的是理论值；用 `layer.align.*` / `layer.distribute.*` 按实际 bounds 校正残余误差 |
| 改了内容尺寸布局乱了 | 没有活容器，布局是静态结果；改尺寸后必须重算重摆 |
| `layer.select {layers:[…]}` 报 missing `layer` | 参数是单数 `layer:id`；多选用 `mode:"add"` 逐个累加 |
| `select.none` 报 unknown command | 不存在；取消选区用 `select.deselect` |
| `layer.align.*` 返回 `{"moved":0}` | 多半是没选中层（或残留像素选区）；先 `select.deselect` 再 `layer.select` |
| 建完参考线 `doc.inspect` 里找不到 | guides 不回显在 inspect，也不出现在 render；只信 `view.newGuideLayout` 返回的条数 |
| 按 8pt 就近吸附后所有列挤在一起 | 列宽可能是小数；先整数化列宽（向下取整）再算列起点，不要逐值吸附 |
| headless 没有 `document.inspect` | 引擎命令要用 `engine.execute {command:"document.inspect"}` 包一层；headless 还有 `doc.inspect` 直接方法 |
| headless 调 `document.new`/`document.save` | 这两个不是引擎命令；headless 用 `doc.new` / `doc.save`，无 GUI 窗口 |
| `layout-design.py calc` 报 allOn8pt 为 false | gutter 不是 8 的倍数，步距无法合规；改 gutter 或接受提示 |
| `layout-design.py check` 判 pass 但报了 MEDIUM | MEDIUM 不算失败，但 MEDIUM 问题（如根组命名不合规）仍需修复后再交付 |
| 列起点参差不齐（120/222/324） | 列宽没取 8 的倍数；用 `layout-design.py calc` 重算，别手改 |
| 不知道画布该多大 | 查 `references/design-spec.md` 第 1 节的尺寸表；项目 spec 优先 |
| 交付引擎后混合模式效果丢失 | 引擎 UI 材质不支持叠加/滤色；交付前和底图一起烘焙合并成单图 |
| 新建的层不在组里，跑到组外面成了平级层 | 新建层不会自动进组；每层建完补 `layer.moveTo {layer, target:组id, position:"into"}` |
| 先 `layer.select` 选中组再建层，层还是跑出去了 | 选组只影响"建在哪一层"，不影响归属；仍要 `moveTo into` |
| `psd-audit` 报 EMPTY_GROUP | 空组要删；未使用的类别不建。`layout-design.py check` 同判 HIGH |
| `check` 报「x=0 不在栅格列上」但那是铺底图层 | spec.json 缺 `height`；补上后铺满画布的层会自动豁免 |
| 建六个根组后审计全是空组 HIGH | 只用实际要用的组；空组一律不建 |
| `type.create` 摆位差几像素 | 它的 x/y 是基线锚点不是 bounds 左上角；以 `doc.inspect` 的 bounds 为准，再 `translate` 补差 |
| `check` 报「y=240 不在间距刻度上（最近 240）」 | 刻度判定应为 8 的倍数，不是命中推荐值枚举表；240 合法 |
| 元素 x 对齐了但视觉上还是没对齐 | 宽度不是合法跨列值，右边界越出列线；宽度只能取 `colW*n+gutter*(n-1)`，跑 `calc` 看 `legalColumnSpans` |
| `edit.transform` 传 `rect` 报 "pass `quad` …, `matrix`, or `scaleX`…" | `rect` 只是源框，必须配 `quad`/`matrix`/`scaleX` 指定目标 |
| 用 `quad` 缩放后出现 329/330、偏移 1px | quad 有插值误差；尺寸要求精确时重画（删层→`select.rect`→`edit.fill`），比变换可靠 |
| 删层后再操作，后面的步骤全错位 | 删层会让层 id 变化/后续命令落到别的层；删完立即 `doc.inspect` 重新确认 id 与 active 层 |

## Output

- 执行的命令序列与关键回执（inspect 证据、save path、warnings）。
- 交付目录清单：分层稿、同名描述文件、`fonts/` 副本（家族、文件、SHA256 核对结果；未随附时写明原因）、平图。
- 规范化任务：原稿/规范稿 SHA256、audit-before/after.json、`psd-audit compare` 结果、visual-diff.json 与 diff 图、旧层→新组映射、字体替换记录。
- 切图/资产导出：源文件 SHA、trim 模式/bbox/padding、倍率/格式/命名、`assets-manifest.json`、`alphaBBox`/透明占比、边缘检查结论、与用户 spec 的对账。
- 会话类型（GUI 桥接 / headless）与端口。
- 结果附 `photocraft --version`；重要交付记导出路径与文件 hash。
- 遗留事项：未完成的编辑、失败的作业、需要用户决策的覆盖确认。
