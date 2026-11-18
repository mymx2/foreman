# 侧车（L2）：只在 L0 做不了的两件事上出手

进程外的 Python 侧车，负责 **闭式抠像（pymatting CFM；无 trimap 时如实降级经典引擎）** 与 **门控内经典补丁（生成式 `lama-onnx` 未接线）**。它不替代 PhotoCraft 的任何原生能力；凡是 L0 能做的（图层装配、暗房、导出、断言）都不许搬到这里。

## 文件

| 文件 | 作用 |
|---|---|
| `matte.py` | 抠像入口：产出 `cutout.png`（RGB + straight alpha）+ `manifest.json` |
| `make_trimap.py` | 从粗 alpha 派生 CFM 需要的 0/128/255 三值图 |
| `patch.py` | 门控补丁：只改掩码内像素，掩码外逐像素不变，产出 `patched.png` + manifest |
| `requirements-sidecar.txt` | 重依赖（pymatting / opencv / onnxruntime），与主依赖分开 |
| `models.lock.json` | 模型元数据登记（名称、sha256、许可证来源）；权重不入库 |

## 引擎与降级（硬规则）

| engine | 触发 | manifest.engine |
|---|---|---|
| `pymatting` | 传了 `--trimap`（0/128/255）且依赖可导入 | `pymatting.cfm+estimate_foreground_ml` |
| `photocraft` | 无 trimap、或 pymatting 装不上 | `photocraft.select.subject+refineEdge` |

- **降级必须写进 `manifest.degraded: true` 与 `notes`**，交付报告里的 `engine_provenance` 也要照抄。以"跑了 CFM"的名义交付实际由 `select.subject` 产出的 alpha，按失败处理。
- CFM 需要三值图。当前没有学习型分割器时，trimap 只能来自 `select.subject` 结果（膨胀/腐蚀出确定前景/背景）或人工描边——这一步属于 P3，尚未接线。

## 用法

```powershell
# 回退路径（今天就能跑）
python scripts/sidecar/matte.py --src 人像.jpg --out out\matte

# CFM 路径（需要 trimap + pymatting/opencv）
python scripts/sidecar/matte.py --src 人像.jpg --out out\matte --trimap tri.png --engine pymatting
```

输出示例：

```json
{"cutout": "out\\matte\\cutout.png", "engine": "photocraft.select.subject+refineEdge",
 "alpha": {"mean": 0.61, "opaque_ratio": 0.52, "soft_ratio": 0.011, "transparent_ratio": 0.38},
 "degraded": true, "notes": ["未提供 --trimap，CFM 无三值图可用，按契约降级 photocraft"]}
```

## 门控补丁（patch.py）

```powershell
python scripts/sidecar/patch.py --src 图.png --gate gate.png --alpha subject.png --out out\patch
```

| engine | 说明 |
|---|---|
| `opencv-telea` | 默认；确定、无模型，实测 gate 外 `outside_max_diff = 0` |
| `opencv-ns` | 纹理更细、更慢 |
| `lama-onnx` | **未接线**：`models.lock.json` 没有可用权重，指定它会明确报错，不会假装跑过 |

两条硬断言（不满足退 1）：
1. `outside_untouched`：gate 外与源逐像素相同（脚本自己重算，不是口头保证）。
2. `gate_disjoint_from_subject`：给了 `--alpha` 就必须与主体 alpha 零重叠。

> 踩坑记录：`--alpha` 一度用 `Image.convert("L")`，读的是**亮度**而不是透明度——抠像图的 RGB
> 全不透明，于是断言误报"重叠 100%"。现在读 `getchannel("A")`。这条正是断言存在的意义：它抓的是
> 脚本自己的错，不是模型的错。

## 回灌 PhotoCraft

```
file.placeEmbedded{path:"cutout.png", scale:100, fit:false}
→ select.loadSelection{channel:"transparency", layer:"cutout.png"}
→ select.saveSelection{name:"ALPHA_SUBJECT", channel:"new"}
```

`file.*` 在 serve/MCP 里会被拒，这一步只能在 CLI `run` 里做。

## 尚未接线（不许当已完成）

1. 学习型分割器（IS-Net / U2-Net / BiRefNet）：`models.lock.json` 为空，`fetch_models.py` 未写。**当前所有 alpha 都来自经典算法或人工 trimap**，别写成"神经网络抠像"。
2. trimap 目前靠 `make_trimap.py` 从粗 alpha 派生（半自动），不是学习型分割器直出。
3. 生成补丁（门控内 inpainting）与 `gate ∩ alpha = ∅` 的硬断言。
4. 亚像素配准（`cv2.phaseCorrelate`）与 `registration.json`。
5. 回灌成片链（`file.placeEmbedded`→`select.loadSelection`→`select.saveSelection`）只验证过命令存在，未在完整交付里跑过。

## 已实测的环境

`pymatting 1.1.16 / numba 0.68.1 / scipy 1.18.1 / opencv-python-headless 5.1.0.95`（Python 3.13.18, Windows）——两条引擎都能出 `cutout.png` + `manifest.json`，`degraded` 字段随实际引擎变化。
