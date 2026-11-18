#!/usr/bin/env python3
"""从已有 alpha 派生 CFM 需要的三值图（0/128/255）。

典型用法：先用 photocraft 的 select.subject+refineEdge 出一版粗 alpha，
再据此派生 trimap，交给 pymatting 做闭式抠像精修。

    python scripts/sidecar/make_trimap.py --alpha cutout.png --out tri.png [--band 6]
"""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
from PIL import Image

try:
    import cv2
except Exception:  # noqa: BLE001
    cv2 = None


def erode_dilate(mask: np.ndarray, k: int, grow: bool) -> np.ndarray:
    if cv2 is None:
        return mask  # 没 cv2 就不动边界，交给调用方决定
    kernel = np.ones((k, k), np.uint8)
    return cv2.dilate(mask, kernel) if grow else cv2.erode(mask, kernel)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--alpha", required=True, help="带 alpha 的 PNG（cutout.png）")
    ap.add_argument("--out", required=True)
    ap.add_argument("--band", type=int, default=6, help="过渡带半径（像素），越大越贵")
    a = ap.parse_args()

    alpha = np.asarray(Image.open(a.alpha).convert("RGBA"))[..., 3]
    fg = erode_dilate((alpha > 235).astype(np.uint8), a.band * 2 + 1, grow=False)
    bg = erode_dilate((alpha < 20).astype(np.uint8), a.band * 2 + 1, grow=True)
    tri = np.full(alpha.shape, 128, np.uint8)
    tri[fg > 0] = 255
    tri[bg > 0] = 0
    if not np.isin(np.unique(tri), [0, 128, 255]).all():
        print("make_trimap: 三值图非法", flush=True)
        return 1
    Image.fromarray(tri).save(Path(a.out))
    counts = {int(k): int(v) for k, v in zip(*[x.tolist() for x in np.unique(tri, return_counts=True)])}
    print({"trimap": str(a.out), "counts": counts, "band": a.band})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
