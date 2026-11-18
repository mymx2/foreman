#!/usr/bin/env python3
"""门控补丁侧车：只改掩码内的像素，掩码外逐像素不变，并给出可核的 manifest。

    python scripts/sidecar/patch.py --src 图.png --gate gate.png --out DIR [--alpha subject.png]

契约：
- patched.png：与源同尺寸同模式；**gate 外与源逐像素相同**（脚本自己断言，不是口头保证）。
- manifest.json：schema=photocraft.sidecar.patch/1，记录实际引擎、参数、gate 面积与 bbox、
  源与产物的 SHA256，以及两条硬断言的结果。
- gate ∩ subject-alpha = ∅：给了 --alpha 就必须成立，重叠即失败（防止把补丁打进主体边缘）。

引擎阶梯（降级必须如实写进 manifest.engine）：
    opencv-telea   默认，确定、无模型
    opencv-ns      纹理更细但慢
    lama-onnx      需 models.lock.json 里有条目且权重就位；当前未接线，指定它会明确报错而不是假装跑了
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from pathlib import Path

try:
    import numpy as np
    from PIL import Image
except Exception:  # noqa: BLE001
    print("patch: 需要 numpy + Pillow", file=sys.stderr)
    raise SystemExit(2)

try:
    import cv2
except Exception:  # noqa: BLE001
    cv2 = None


def sha(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def load_gate(path: Path, size: tuple[int, int]) -> np.ndarray:
    g = np.asarray(Image.open(path).convert("L"), dtype=np.uint8)
    if (g.shape[1], g.shape[0]) != size:
        raise RuntimeError(f"gate 尺寸 {g.shape[1]}x{g.shape[0]} 与源 {size[0]}x{size[1]} 不一致")
    return (g > 127).astype(np.uint8)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", required=True)
    ap.add_argument("--gate", required=True, help="掩码图：白=要修的区域")
    ap.add_argument("--out", required=True)
    ap.add_argument("--alpha", default=None, help="主体 alpha；给了就断言 gate 与它不相交")
    ap.add_argument("--engine", choices=["auto", "opencv-telea", "opencv-ns", "lama-onnx"], default="auto")
    ap.add_argument("--radius", type=int, default=5)
    a = ap.parse_args()

    src = Path(a.src)
    if not src.exists():
        print(f"patch: 源不存在 {src}", file=sys.stderr)
        return 2
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)

    img = np.asarray(Image.open(src).convert("RGB"), dtype=np.uint8)
    h, w = img.shape[:2]
    gate = load_gate(Path(a.gate), (w, h))
    area = int(gate.sum())
    if area == 0:
        print("patch: gate 是空的", file=sys.stderr)
        return 2
    ys, xs = np.where(gate > 0)
    gate_box = [int(xs.min()), int(ys.min()), int(xs.max() - xs.min() + 1), int(ys.max() - ys.min() + 1)]

    checks: dict[str, bool] = {}
    notes: list[str] = []

    if a.alpha:
        aim = Image.open(a.alpha)
        if aim.mode in ("RGBA", "LA"):
            alpha = np.asarray(aim.getchannel("A"), dtype=np.uint8)  # 读 alpha 通道，不是亮度
        else:
            alpha = np.asarray(aim.convert("L"), dtype=np.uint8)
        if (alpha.shape[1], alpha.shape[0]) != (w, h):
            print("patch: alpha 尺寸与源不一致", file=sys.stderr)
            return 2
        overlap = int(((alpha > 0) & (gate > 0)).sum())
        checks["gate_disjoint_from_subject"] = overlap == 0
        if overlap:
            notes.append(f"gate 与主体 alpha 重叠 {overlap} 像素")
    else:
        notes.append("未提供 --alpha，跳过 gate∩subject 断言")

    engine = a.engine
    if engine in ("auto", "lama-onnx"):
        if engine == "lama-onnx":
            print("patch: lama-onnx 未接线（models.lock.json 里没有可用权重）", file=sys.stderr)
            return 1
        engine = "opencv-telea"
    if cv2 is None:
        checks["engine_available"] = False
        print("patch: 需要 opencv-python-headless（pip install -r scripts/sidecar/requirements-sidecar.txt）",
              file=sys.stderr)
        return 2

    method = cv2.INPAINT_TELEA if engine == "opencv-telea" else cv2.INPAINT_NS
    bgr = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)
    filled = cv2.inpaint(bgr, gate, a.radius, method)
    patched = cv2.cvtColor(filled, cv2.COLOR_BGR2RGB)

    # 硬断言：gate 外逐像素与源相同（不让算法顺手改动别处）
    keep = gate == 0
    outside_diff = int(np.abs(patched[keep].astype(np.int16) - img[keep].astype(np.int16)).max()) if keep.any() else 0
    checks["outside_untouched"] = outside_diff == 0
    changed_inside = int((np.abs(patched.astype(np.int16) - img.astype(np.int16)).max(axis=2) > 0)[gate > 0].sum())

    png = out / "patched.png"
    Image.fromarray(patched).save(png)
    manifest = {
        "schema": "photocraft.sidecar.patch/1",
        "source": {"path": str(src), "sha256": sha(src), "width": w, "height": h},
        "gate": {"path": str(a.gate), "sha256": sha(Path(a.gate)), "area": area, "bbox": gate_box},
        "engine": engine,
        "engine_params": {"radius": a.radius},
        "output": {"path": str(png), "sha256": sha(png)},
        "changed_inside_pixels": changed_inside,
        "outside_max_diff": outside_diff,
        "checks": checks,
        "passed": all(checks.values()),
        "notes": notes,
        "created": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
    }
    (out / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"patched": str(png), "engine": engine, "gate_area": area,
                      "changed_inside": changed_inside, "outside_max_diff": outside_diff,
                      "checks": checks, "passed": manifest["passed"],
                      "notes": notes}, ensure_ascii=False, indent=2))
    return 0 if manifest["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
