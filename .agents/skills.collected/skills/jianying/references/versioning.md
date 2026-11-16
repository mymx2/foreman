# 版本链：把剪映草稿当 PSD 一样迭代

剪映草稿本身就是可继续编辑的源文件：`draft_info.json` 记录轨道、片段、素材和参数，等价于一份
分层工程。版本链在这个工程旁边保留每一次构建/补丁/快照，目的是**交付不是一次性成片**：

- 改一版文案、换一版 BGM、试一版调色，都能回到上一版；
- 每个版本保留产生它的 plan / ops，下一次可以继续改或从旧版分叉；
- 每个版本可以挂导出回执（MP4 路径、字节数、ffprobe 时长），知道“这版导出过什么”。

## 目录结构

```text
<draft>/
  draft_info.json
  draft_meta_info.json
  .jianying-skill.json                 # 标记文件；含 current / version_count
  .jianying-versions/
    versions.json                      # 版本清单（唯一索引）
    v001/
      draft_info.json                  # 全量快照，恢复不依赖补丁链
      draft_meta_info.json             # 存在时一并快照
      source-plan.json                 # build 的计划副本
    v002/
      draft_info.json
      draft_meta_info.json
      source-ops.json                  # patch 的补丁副本
```

`versions.json` 里每个版本至少包含：

| 字段 | 含义 |
|---|---|
| `id` | `v001` 起的递增编号 |
| `parent` | 父版本；`v001` 为 `null` |
| `kind` | `build` / `patch` / `snapshot` / `import` / `restore` |
| `label` | 人可读标签，如“改文案” |
| `draft_sha256` | 该版 `draft_info.json` 的 SHA256 |
| `meta_snapshot` | 该版 `draft_meta_info.json` 的相对路径；没有 meta 时为 `null` |
| `duration` / `tracks` / `segments` / `materials` / `texts` | 结构摘要 |
| `plan` / `ops` | 计划/补丁副本的相对路径 |
| `exports` | 该版导出回执列表 |

历史目录在草稿目录内部，复制草稿时一起带走。剪映是否会读写 `.jianying-versions` 未经宿主验证；
交付后让用户在剪映里打开确认，不要把“技能期望它不改”当成事实。

## 命令

```bash
# 查看版本
python scripts/jy.py version list <draft>
python scripts/jy.py version show <draft> v002

# 结构差异（不是像素 diff）
python scripts/jy.py version diff <draft> v002
python scripts/jy.py version diff <draft> v002 --against v001

# 给当前草稿存一版（导入的旧草稿也用它建立基线）
python scripts/jy.py version snapshot <draft> --label "调色前" --note "保留原片参数"

# 恢复到新目录；不会覆盖原稿
python scripts/jy.py version restore <draft> v001 --out <新草稿目录> --name "回到第一版"
```

`build` 成功后在暂存目录写 `v001`，随草稿一起原子发布；`patch` 成功后在目标草稿写下一版：

- `patch --out` 写副本：源草稿的版本链会随副本复制；没有历史时，先用补丁前的字节建立 `pre-patch` 基线，再写补丁版；
- `patch --in-place`：在原草稿上追加补丁版，仍保留补丁前基线；
- `build --version-label` / `patch --version-label` 可以给版本命名。

`render` 成功后把 MP4 路径、字节数和 ffprobe 时长挂到当前版本的 `exports`；草稿没有历史时不写，
并给出 warning，提示先 `version snapshot`。

## 语义与边界

- **全量快照，不是补丁链**：每一个版本都保存完整 `draft_info.json`，恢复不依赖中间版本是否完整；
  体积换可靠性。`source-plan.json` / `source-ops.json` 是“怎么改出来的”线索，不参与恢复。
- **恢复是新草稿，不是回滚原稿**：`restore` 生成新 `draft_id`、新目录和新 `v001`（`kind: "restore"`），
  原稿和原版本链不动。需要“在原稿上回退”时，先 `restore` 到新目录，再决定是否用新草稿替换；
  不要手改历史目录。`restore` 只还原草稿结构，**不打包素材**：素材仍指向原绝对路径，原素材移动/删除后
  恢复版会缺媒体或黑帧。恢复目标不能落在源草稿目录内部。
- **多时间线草稿**：快照对象是 `Timelines/project.json` 里 `main_timeline_id` 指向的主时间线
  `draft_info.json`（查找委托 `resolve_draft_info`）；`restore` 输出的是单时间线根布局草稿，
  不再保留 `Timelines/` 多时间线结构。多时间线草稿的 `render` 仍不支持（桥接只接受根
  `draft_info.json`，见 [limits](limits.md) 与 SKILL.md）；需要在剪映客户端导出。
- **并发写入**：`versions.json` 的读-改-写用目录锁串行化；并发快照不会丢更新。锁超时会报
  `VERSION_WRITE_FAILED`，不会留下半写的清单。
- **diff 是结构+材质指纹 diff**：比较画布、时长、轨道/片段数、素材计数、新增/删除文字、片段 id，
  以及每个片段的主/附加材质指纹（动画、字幕模板、高亮、资源路径）。像素、转场、
  滤镜、听感必须分别 `render` 两版后抽帧或 `volumedetect`，不能把 `changes` 为空当成画面没变。
- **外部输入有指纹**：每个版本条目记录 `inputs`（草稿目录外的素材/字体/模板的 path、size、mtime；≤20MB 的文件再记 sha256）；
  草稿目录内部的封面/相对素材不记入 `inputs`，避免暂存目录改名后路径悬空。`restore` 会报告
  `input_issues` 的 `missing` / `size_changed` / `sha256_changed`，但**不打包素材**，仍需保留原文件。
- **SRT 随版本归档**：`add_subtitles` 的 SRT 会复制成版本目录里的 `artifact-NN.srt`，条目记
  `artifacts[].sha256`；`source-ops.json` 仍保留原路径。后续改 SRT 不影响旧版本复现 cue 文本。
- **导出回执不等于验收**：`exports` 只说明这一版导出过；仍要 `verify` 时长/分辨率，并抽帧看关键画面。
- **不手工编辑**：不要手改 `versions.json`、快照 JSON 或 `draft_info.json` 来“造版本”；要改就 `patch`，
  要留档就 `version snapshot`。
- **不自动清理**：旧版本不会被自动删除；需要清理时由用户明确指定删哪些，技能不主动删。
- **加密草稿不支持**：版本链只处理明文草稿；`DRAFT_ENCRYPTED` 时回到剪映另存明文。
- **工作树/压缩包**：`.jianying-versions` 是草稿目录的一部分，交付时保留；如果用户只要一个干净草稿，
  明确说明“历史目录可单独删除，删除后不能 restore”。

## 推荐工作流

1. `build` → `inspect` → `version list` 确认 `v001`；
2. 要改文案/音量/位置 → `patch --out` 写副本，版本自动成 `v002`；
3. 改完 `version diff` 看结构差异，再 `render` 新成片，`verify` + 抽帧；
4. 不满意就 `version restore` 回旧版到新目录，或继续 `patch` 下一版；
5. 交付时给：当前 `version`、`version_count`、历史目录、每个版本挂的成片与未验证项。
