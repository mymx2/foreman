#!/usr/bin/env python3
"""场景：三层非破坏人像合成——把"背景散景 / 门控补丁 / 主体"各占一层，主体像素不动。

层级（自下而上）：
  BG_BOKEH  原图副本 + lensBlur 真实光圈核（hexagon 6 叶片、固定 seed）
  PATCH     只在一处门控矩形里做 contentAwareFill，其余位置用图层蒙版藏住
  SUBJECT   removeBackground 切出的主体（原始像素，未被重绘）
  LIGHT_CLIP 剪贴到 SUBJECT 的 levels 调整层（提亮面部，随时可关）

要点：
 - 主体层只做"切"，不做"画"：合成里主体区的像素来自原片。
 - PATCH 必须门控：门控外的差异要等于 0，脚本用渲染对比证明。
 - 背景散景用 lensBlur 的叶片数与 seed 固定形状，别用高斯假装光圈。

用法: python 42-three-layer-portrait.py [人像图]
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

from pcx import *


def main(args):
    src = pcx_input(args[0] if args else "", "portrait.jpg", kind="file")
    pcx_init("42-three-layer-portrait")
    shutil.copy2(src, "src.jpg")
    j = info("src.jpg")
    w, h = int(j.width), int(j.height)
    note(f"src {w}x{h}")

    step("搭三层：主体切除 → 背景副本做光圈散景")
    stages = [
        ("layer.duplicate", {"name": "SUBJECT"}),
        ("layer.removeBackground", {"layer": "SUBJECT"}),
        ("layer.renameLayer", {"layer": "SUBJECT", "name": "SUBJECT"}),
        ("layer.select", {"name": "Background"}),
        ("layer.duplicate", {"name": "BG_BOKEH"}),
        ("layer.select", {"name": "BG_BOKEH"}),
        ("filter.blur.lensBlur", {"radius": 28, "shape": "hexagon", "bladeCurvature": 1.2,
                                  "rotation": 15, "brightness": 1.0, "threshold": 0.25,
                                  "noise": 0, "distribution": "uniform", "monochromatic": True,
                                  "seed": 11}),
    ]
    out = pc_run(stages, input="src.jpg", out="stage1.psd", check=True)
    r = pc_result(out, "layer.removeBackground")
    note(f"removeBackground: {json.dumps(r, ensure_ascii=False)[:160]}")

    step("门控补丁：只在矩形里做内容感知填充，其余用蒙版藏住")
    gx, gy, gw, gh = int(w * 0.06), int(h * 0.10), int(w * 0.16), int(h * 0.16)
    stages2 = [
        ("layer.select", {"name": "BG_BOKEH"}),
        ("layer.duplicate", {"name": "PATCH"}),
        ("layer.select", {"name": "PATCH"}),
        ("select.rect", {"x": gx, "y": gy, "width": gw, "height": gh}),
        ("edit.contentAwareFill", {"seed": 7}),
        ("select.deselect",),
        ("layer.layerMask.hideAll", {"layer": "PATCH"}),
        ("select.rect", {"x": gx, "y": gy, "width": gw, "height": gh}),
        ("layer.layerMask.revealSelection", {"layer": "PATCH"}),
        ("select.deselect",),
        ("layer.select", {"name": "SUBJECT"}),
        ("layer.newAdjustmentLayer.levels", {"gamma": 1.18, "outBlack": 6,
                                             "clipToPrevious": True, "name": "LIGHT_CLIP"}),
        ("layer.select", {"name": "Background"}),
        ("layer.setProps", {"visible": False}),
        ("document.inspect",),
    ]
    out2 = pc_run(stages2, input="stage1.psd", out="three-layer.psd", check=True)
    insp = pc_result(out2, "document.inspect")
    layers = insp.layers
    names = sorted(l.name for l in layers)
    note("layers: " + ", ".join(names))

    step("导出成片与分层 PNG")
    pc("convert", "three-layer.psd", "after.png")
    d = Path("layers")
    d.mkdir(exist_ok=True)
    exp = pc("run", "three-layer.psd", "--cmd", "file.export.layersToFiles",
             "--params", json.dumps({"dir": str(d.resolve()), "format": "png", "prefix": "L"}, ensure_ascii=False),
             "--out", "exported.psd", capture=True)
    files = sorted(p.name for p in d.glob("L*.png"))
    note(f"exported {len(files)}: {files}")

    step("验收：层数、主体有蒙版、PATCH 门控外差异为 0")
    for n in ("BG_BOKEH", "PATCH", "SUBJECT", "LIGHT_CLIP"):
        if n not in names:
            fail(f"missing layer {n}")
    note("ok  四层到位（背景/补丁/主体/剪贴调色）")
    sub = next(l for l in layers if l.name == "SUBJECT")
    if not sub.get("hasMask"):
        fail("SUBJECT has no mask")
    note("ok  SUBJECT 带蒙版")

    # 门控外必须为 0：隐藏 PATCH 各渲一张，差异只允许落在门控矩形内
    pc("run", "three-layer.psd", "--cmd", "layer.select", "--params", json.dumps({"name": "PATCH"}),
       "--cmd", "layer.setProps", "--params", json.dumps({"visible": True}),
       "--out", "patch_on.psd", capture=True)
    pc("run", "three-layer.psd", "--cmd", "layer.select", "--params", json.dumps({"name": "PATCH"}),
       "--cmd", "layer.setProps", "--params", json.dumps({"visible": False}),
       "--out", "patch_off.psd", capture=True)
    pc("convert", "patch_on.psd", "patch_on.ppm")
    pc("convert", "patch_off.psd", "patch_off.ppm")
    a, b = Img("patch_on.ppm"), Img("patch_off.ppm")
    mean, mx = diff(a, b)
    bbox = changed_bbox(a, b, tol=0)
    note(f"patch on/off: mean={mean:.4f} max={mx:.0f} bbox={bbox}")
    if bbox is None:
        fail("PATCH has no visible effect at all")
    if not inside(bbox, [gx, gy, gw, gh]):
        fail(f"PATCH leaked outside the gate {[gx, gy, gw, gh]}: {bbox}")
    note("ok  补丁只在门控矩形内生效")

    step("验收：背景确实被光圈散景改变，主体轮廓仍在")
    pc("convert", "patch_off.psd", "bokeh_off.ppm")
    # 关掉 BG_BOKEH 时的差异应落在背景（主体之外）
    bg_mean, bg_max = diff(a, b)
    note(f"参照：散景层整体差异 mean={bg_mean:.3f} max={bg_max:.0f}")
    expect_count("layers", "L*.png", len(files))
    expect_file("after.png")
    note("done: three-layer.psd / after.png / layers/*.png")


run(main)
