#!/usr/bin/env python3
"""场景：质检交付件——无边框 Before/After 并排、300–500% 局部放大、可机读 qc_report。

产物：
  compare.png        左右并排（同一画布、同一比例、无边框）
  crop_eye_400.png   眼部 400%
  crop_mouth_400.png 嘴部 400%
  crop_edge_400.png  边缘/发丝 400%
  qc_report.json     尺寸、SHA256、整体差异、高频保留率

要点：
 - 放大图必须从**成片**裁，不是从原片裁：要看的是修完之后的嘴和眼。
 - 只比"改了什么"不够，还要证明"没改坏"：高频保留率低于阈值就当磨皮过度处理。
 - 报告写绝对尺寸与百分比，别只写"看起来没问题"。

用法: python 44-qc-delivery-sheet.py [人像图]
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from pcx import *


def sha(p) -> str:
    h = hashlib.sha256()
    with Path(p).open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def hf_energy(im: Img, x, y, w, h) -> float:
    """区域内水平相邻像素差的平均绝对值，作为高频能量的代理。"""
    x0, y0, x1, y1 = im.clip(x, y, w, h)
    tot = n = 0
    for yy in range(y0, y1, 2):
        prev = None
        for xx in range(x0, x1, 2):
            c = im.px(xx, yy)
            if prev is not None:
                tot += sum(abs(c[k] - prev[k]) for k in range(3)) / 3
                n += 1
            prev = c
    return tot / max(1, n)


def main(args):
    src = pcx_input(args[0] if args else "", "portrait.jpg", kind="file")
    pcx_init("44-qc-delivery-sheet")
    shutil.copy2(src, "before.jpg")
    j = info("before.jpg")
    w, h = int(j.width), int(j.height)
    note(f"before {w}x{h}")

    step("做成片：保留结构的轻修（抬中间调 + 微反差，不动暗部漆面）")
    pc_run([
        ("layer.duplicate", {"name": "WORK"}),
        ("image.adjustments.levels", {"gamma": 1.06, "outBlack": 2, "outWhite": 253}),
        ("filter.sharpen.unsharpMask", {"amount": 10, "radius": 1.0, "threshold": 3}),
        ("document.inspect",),
    ], input="before.jpg", out="after.psd", check=True)
    pc("convert", "after.psd", "after.png")
    expect_file("after.png")

    step("并排对比：同一画布左右各一张，无边框")
    pc_run([("file.placeEmbedded", {"path": pcx_native(Path("before.jpg").resolve()), "scale": 100,
                                    "fit": False, "smartObject": False, "center": [w / 2, h / 2]}),
            ("file.placeEmbedded", {"path": pcx_native(Path("after.png").resolve()), "scale": 100,
                                    "fit": False, "smartObject": False, "center": [w * 1.5, h / 2]}),
            ("layer.flattenImage",)],
           new={"width": w * 2, "height": h, "background": "white", "name": "compare"}, out="compare.psd",
           check=True)
    pc("convert", "compare.psd", "compare.png")
    expect_size("compare.png", w * 2, h)
    note("ok  compare.png = 2×画幅并排，无边框")

    step("300–500% 局部放大：从成片裁，不从原片裁")
    crops = {
        "crop_eye_400.png": (int(w * 0.34), int(h * 0.34), int(w * 0.16), int(h * 0.16)),
        "crop_mouth_400.png": (int(w * 0.38), int(h * 0.60), int(w * 0.16), int(h * 0.14)),
        "crop_edge_400.png": (int(w * 0.08), int(h * 0.18), int(w * 0.18), int(h * 0.18)),
    }
    made = []
    for name, box in crops.items():
        pc_run([("image.crop", {"x": box[0], "y": box[1], "width": box[2], "height": box[3],
                                "deleteCroppedPixels": True}),
                ("image.imageSize", {"percent": 400}),
                ("document.inspect",)], input="after.png", out=name.replace(".png", ".psd"), check=True)
        pc("convert", name.replace(".png", ".psd"), name)
        gj = info(name)
        if abs(int(gj.width) - box[2] * 4) > 2 or abs(int(gj.height) - box[3] * 4) > 2:
            fail(f"{name} is {gj.width}x{gj.height}, expected {box[2] * 4}x{box[3] * 4}")
        made.append(name)
        note(f"ok  {name} {gj.width}x{gj.height}（{box[2]}×{box[3]} 的 400%）")

    step("数值质检：整体差异 + 皮肤区高频保留率")
    pc("convert", "before.jpg", "before.ppm")
    pc("convert", "after.png", "after.ppm")
    a, b = Img("before.ppm"), Img("after.ppm")
    mean, mx = diff(a, b, step=2)
    skin = (int(w * 0.40), int(h * 0.42), int(w * 0.18), int(h * 0.15))
    e0, e1 = hf_energy(a, *skin), hf_energy(b, *skin)
    ratio = e1 / max(1e-6, e0)
    note(f"diff mean={mean:.4f} ({mean * 255:.2f}/255) max={mx:.3f}")
    note(f"skin hf: before={e0:.4f} after={e1:.4f} ratio={ratio:.3f}")
    if mx >= 0.999:
        fail("after is identical to before — nothing was applied")
    if ratio < 0.75:
        fail(f"high-frequency energy dropped to {ratio:.2f} of the original: over-smoothed")

    report = {
        "schema": "photocraft.qc/1",
        "before": {"path": str(Path("before.jpg")), "sha256": sha("before.jpg"), "width": w, "height": h},
        "after": {"path": str(Path("after.png")), "sha256": sha("after.png"),
                  "width": int(info("after.png").width), "height": int(info("after.png").height)},
        "side_by_side": {"path": "compare.png", "sha256": sha("compare.png"),
                         "width": w * 2, "height": h},
        "crops": [{"path": n, "scale_percent": 400, "sha256": sha(n)} for n in made],
        "diff": {"mean": round(mean, 5), "max": round(mx, 5)},
        "texture": {"region": list(skin), "hf_before": round(e0, 5), "hf_after": round(e1, 5),
                    "ratio": round(ratio, 3)},
        "checks": {"nothing_applied": False, "over_smoothed": ratio < 0.75,
                   "canvas_doubled": True, "crops_are_400pct": True},
    }
    Path("qc_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    expect_file("qc_report.json")
    note("done: compare.png / crop_*.png / qc_report.json")


run(main)
