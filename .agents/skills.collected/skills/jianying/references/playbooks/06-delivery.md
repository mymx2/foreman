# 交付 Playbook

读此文件时，目标是**把草稿变成可验收的交付**：环境探测、结构核对、原生导出、ffprobe/抽帧、
首页登记、能力边界说明。交付的核心不是“命令返回 ok”，而是“有证据”。

## 1. probe：先确认环境

```bash
python scripts/jy.py probe
```

看：

| 字段 | 说明 |
|---|---|
| `install.version` / `install.build` | 是否 11.8.0.14778 |
| `docs.status` | `verified` / `unverified` / `unsupported` / `unknown`（`unknown` = 版本探测失败或版本文件不可读，不阻断草稿构建） |
| `bridge.reachable` | 能否原生导出 |
| `bridge.health.version/build` | 剪映引擎版本 |
| `draft_root` | 首页草稿根 |
| `ffmpeg` | 外部 ffmpeg 路径与能力 |
| `python.bundled` | 剪映自带解释器 |

`bridge` 不可达时：仍可 `build` 草稿，但不能声称“已真实导出”；交付里写“未验证导出”。

## 2. inspect：结构核对

```bash
python scripts/jy.py inspect <draft>
```

检查：

- `missing_media=[]`；
- `duration` 与计划一致；
- `tracks` 数量/类型正确；
- 文字在 `texts`、图片/画中画在 visual 轨；
- `materials` 计数（mask/sticker/effect/audio_fades 等）。

结构不对就改 plan 重 build，不要手改 `draft_info.json` 补洞。

## 3. render：原生导出

```bash
python scripts/jy.py render <draft> -o <out.mp4> --timeout 300
# 音频/动图：--format mp3|wav|aac|flac|aiff|ogg|mov|gif（输出扩展名与格式一致）

```

- 只对**明文** `draft_info.json` 导出；
- 输出已存在默认拒绝，`--force` 需用户授权；
- 执行前备份草稿文件；回执看 `draft_mutated`、`draft_files_changed`、`draft_sha256_before/after`；
- 草稿含 `chroma`/`beauty`/`mix_mode` 时，bridge 只导出未应用版本；这三项成片必须走剪映界面导出，
  `render` 的 warning 只是在提醒，不代表效果已生效；
- 成功后 MP4 路径、字节数和 ffprobe 时长写入当前版本的 `exports`；没有版本历史时回执带 warning，
  先 `version snapshot` 再导出；
- 错误码按 [bridge-protocol](../bridge-protocol.md) 处理，不并发轰炸。

## 4. verify：ffprobe + 抽帧

```bash
python scripts/jy.py verify out.mp4 --expect-duration 8 --frames 0.5,3.5,7.0
python scripts/jy.py frame out.mp4 --at 3.5 -o frame.png
```

`verify` 返回：

- `duration/width/height/fps/codec`；
- `expect_duration` 差值（>0.25s 要查原因）；
- 帧路径。

必须用 Read 看帧：主轨、画中画、字幕、蒙版、特效、文字背景/阴影。不看帧不算验收。

## 5. publish / register：首页登记

```bash
python scripts/jy.py publish <draft>            # dry-run
python scripts/jy.py publish <draft> --apply    # 真写
python scripts/jy.py register <draft> --apply
```

前置：

1. 用户保存并**退出剪映**；
2. `draft_info.json` 与 `draft_meta_info.json` 的 `draft_id` 一致；
3. `tm_duration` 为正；
4. 写前备份索引；写后回读 `verified`。

剪映运行时可能用内存索引覆盖磁盘；没重启剪映就说明“未验证首页显示”。

## 6. 证据清单

交付回复至少带：

- 草稿绝对路径、名称、时长、画布、轨道/素材计数；
- 版本链：`version`、`version_count`、`history_path`；改稿给 `version diff`，恢复给 `restored_from`；
- 成片路径、字节数、ffprobe 字段；说明该成片挂在哪个版本；
- 抽帧路径 + “看过了”的结论；
- 音频任务 `volumedetect` 数字或听感；
- SRT 的 `lines`/`issues`；
- publish 的 `action/applied/backup/verified`；
- 未验证项/条件项（`adjust`/`freeze`/HSL/色轮/花字/气泡/加密草稿/导出参数；绿幕/美颜/混合模式标注为仅界面导出）。
- 真机探针的可复核证据已移出仓库；
  它不包含源素材/缓存包/登录态；交付时引用仓库外归档编号/日期，不引用本机 `%TEMP%`，不声称“仓库内可复核”或“换机端到端可复现”。

## 7. 错误处理

| `error` | 处理 |
|---|---|
| `film_export_entitlement_denied` | 检查文字素材是否 `subtitle`、会员字体/特效；移除后重试 |
| `film_export_dependency_missing` | 资源包未缓存；先让用户在剪映打开对应效果，或从计划去掉 |
| `film_export_draft_unreadable` | 加密/损坏/路径不对；只导明文根草稿 |
| `film_export_no_audio` | 音频路径/流不可用；检查后重导 |
| `film_export_invalid_state` | 剪映忙；等空闲，不并发重试 |
| `film_export_token_invalid` | 重跑 `probe` 读新 token，不复用旧值 |
| `DRAFT_ID_MISSING` / `DRAFT_META_*` | 缺 meta；不写索引，回草稿修复 |
| `OUTPUT_EXISTS` | 换新路径或用户授权 `--force` |

## 8. 能力边界

```bash
python scripts/capability_probe.py --list
python scripts/capability_probe.py --out capabilities.json
```

它输出 `implemented` / `conditional` / `planned` / `unverified` / `host_only` / `account_gated` /
`missing_resource` / `manual`。交付时把 `unverified`、`planned` 和 `manual` 如实告诉用户，
不把“结构写入”当“效果生效”。

## 9. 案例

- `examples/05-capability-report.py`：能力矩阵；
- `examples/09-publish-dry-run.py`：首页登记 dry-run；
- `examples/18-spoken-piece.py`：口播成片 + 导出验收；
- `examples/19-version-chain.py`：build/patch/diff/restore 版本链。
