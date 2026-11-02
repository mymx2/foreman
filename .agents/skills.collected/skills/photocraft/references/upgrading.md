# 0.18 → 0.19 升级指南

> 上一支持基线 0.18.0，当前核对版本 0.19.0。只收会改变自动化写法或验收的行为；命令/参数计数以 `check_docs.py` 输出为准，正文不写死。每次升级覆盖本文件，旧差异移入 `history/<到达版本>.md`；维护流程见 `maintenance.md`。

## 变化

| 变化 | 说明 |
|---|---|
| 新增 `layer.smartObjects.exportSvg` / `updateSvg` / `updateVectorSource` | 矢量智能对象的外部编辑器交接。`exportSvg` 回 `{document, svg 或 sourceBase64, extension, sourceSize, fingerprint, contentsId}`；两个 update 都要带原 `fingerprint` 和 `contentsId`，`updateSvg` 用新 SVG 源，`updateVectorSource` 存回 `.ai/.pdf/.eps` 原始字节并附 `previewSvg`。三条都 `journal:false`（不进动作录制），也没有菜单入口；`updateSvg` / `updateVectorSource` 仍会各写一步撤销历史（Update SVG Contents / Update Vector Contents），`exportSvg` 不写 |
| 新增 `path.addToSelection` / `path.subtractFromSelection` | `path.toSelection` 的 `mode:"add"` / `"subtract"` 包装，参数与 `path.toSelection` 相同（`name` / `feather` / `antiAlias`） |
| 通道路由名单新增成员 | `routed()` 新增 `edit.cut`、`edit.clear`、`edit.stroke`、`paint.patch`、`paint.contentAwareMove`、`paint.magicEraser`、`paint.backgroundEraser`、`paint.colorReplacement`、`path.fill`、`path.stroke`。**名单不等于行为**：蒙版目标下实测 `edit.clear` / `edit.cut` 改蒙版，`edit.stroke` / `paint.magicEraser` / `paint.backgroundEraser` 仍改图层像素，`path.fill` / `path.stroke` 源码直接写图层 surface；`paint.colorReplacement` / `paint.patch` / `paint.contentAwareMove` 未验。要写通道先小样验落点 |
| `file.print` 的 Scale to Fit Media | 只在 Windows 真实送印（不给 `output`、`dryRun`）时按驱动可打印区算，横放纸张按旋转后的页面算；给 `output` 或 `dryRun` 时仍走固定边距（默认 18pt，带标记 36pt），实测 400×300 的图在 letter 纸上 `imageRect [18,180,576,432]`。出 PDF 时不要断言会填满可打印区 |
| `.atn` 切文档 | 动作里的文档切换按打开顺序，不按拖拽后的标签顺序；多文档重放时 `document.activate {offset}` 的落点可能与屏幕标签顺序不同（上游说明，未实测） |
| `type.edit` 重建 PSD 字体表 | 同名字面在 FontSet 里有多条记录时优先用还没消费过的记录，队列耗尽才回退第一条；保留导入字体元数据从 0.18 起就有，0.19 修的是重复/乱序记录相互串味（上游说明，未实测）。改字后仍以 `type.info` 的 `postscript_name` 和 `type.fonts` 核对 |

0.19 的其余变化（界面、语言包、性能、PSD 内存上限）不改自动化写法，未列入。

本表除命令 id/参数面经 `check_docs.py` 校验外，`exportSvg` / `updateSvg` 的往返与指纹校验已在 0.19 实跑；其余条目来自 0.19 源码与 release notes，没有逐条实跑，首次使用时按下面的重跑清单核对。

## 升级后要重跑

1. `python <skill-dir>/scripts/check_docs.py`：确认文档里的命令 id、参数、方法名与已安装注册表一致；计数以脚本输出的 baseline 为准。
2. `python <skill-dir>/scripts/run_examples.py`：全部案例通过；案例 31 默认跳过，设 `PCX_DESKTOP=1` 才跑桌面窗口。
3. `python <skill-dir>/scripts/probe_gotchas.py`：逐条复核 Gotchas 的实测项；运行结果与文档冲突时以运行结果为准并改文档。
4. `python <skill-dir>/scripts/test_workflow.py` 与 `python <skill-dir>/scripts/test_control.py`：工作流脚本与客户端逻辑的单测。
5. 若新增命令/格式，在 `commands.md`、`formats.md` 补一行；本文件只保留当前迁移表，由维护流程覆盖重写，不再追加。
