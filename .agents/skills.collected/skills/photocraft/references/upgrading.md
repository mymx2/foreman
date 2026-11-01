# 0.14 → 0.18 升级指南

> 上一支持基线 0.14.0，当前核对版本 0.18.0。只收会改变自动化写法或验收的行为；命令/参数计数以 `check_docs.py` 输出为准，正文不写死。每次升级覆盖本文件，旧差异移入 `history/<到达版本>.md`；维护流程见 `maintenance.md`。

## 变化

| 变化 | 说明 |
|---|---|
| serve 新增 `doc.replaceSmartObject` | `{path, layer?, index?}` → `{layer, instances, warnings}`；MCP 对应 `doc_replace_smart_object` |
| 智能对象换图 | `layer.smartObjects.replaceContents` / `doc.replaceSmartObject` 保留图层既有 transform/缩放，bounds = 新源像素 × 图层缩放，不按源图 DPI 换算；复制实例共享内容源，`instances` 列出全部受影响的层 |
| `layer.renameLayer` | 省略 `layer` 时改的是活动层；批量改名务必显式给 `layer` |
| `type.resolveMissingFonts` | `map` 只换家族名，不保证目标家族有同名字面；母版含隐藏版本时不要用全文档映射 |
| `type.setStyle` | 回执是完整 `type.info`（`runs`/`lines`/`bounds`），改完可当场核对 |
| 文字层 `postscript_name` | 新建或改样式后，字面未解析（缺字体/缺字重）时为 `null`；已装且能解析的字面会立即回填 |
| WebP DPI | 有损 WebP 也保留 DPI；300 ppi 往返一致，旧记录“不存 DPI”失效 |
| `file.print` 默认 | 不给 `output`、`dryRun` 或 `send` 会直接走真实打印队列；自动化显式给 `output` + `dryRun` |
| `image.crop` 越界 | 不报错，静默产出纯白小图并计入成功 |
| 无选区 `select.deselect` | **行为反转**：0.12–0.14 的 CLI `run` 里报 `no selection` 并中止整条 run；0.18 改成回 `null`、退出码 0、继续执行。serve 两个版本都报错 |
| 选中组后新建层 | **行为反转**：0.12–0.14 落在组外，0.18 落进组内（`parent` 指向组）。要精确入组就用 `layer.moveTo {position:"into"}` |

0.14→0.18 的其余变化（格式、打印、RAW、GUI）尚未系统复核；遇到与文档不符时以运行结果为准，并在本表补一行。

## 升级后要重跑

1. `python <skill-dir>/scripts/check_docs.py`：确认文档里的命令 id、参数、方法名与已安装注册表一致；计数以脚本输出的 baseline 为准。
2. `python <skill-dir>/scripts/run_examples.py`：全部案例通过；案例 31 默认跳过，设 `PCX_DESKTOP=1` 才跑桌面窗口。
3. `python <skill-dir>/scripts/probe_gotchas.py`：逐条复核 Gotchas 的实测项；运行结果与文档冲突时以运行结果为准并改文档。
4. `python <skill-dir>/scripts/test_workflow.py` 与 `python <skill-dir>/scripts/test_control.py`：工作流脚本与客户端逻辑的单测。
5. 若新增命令/格式，在 `references/commands.md`、`formats.md` 补一行；本文件只保留当前迁移表，由维护流程覆盖重写，不再追加。
