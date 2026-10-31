#!/usr/bin/env python3
"""场景：风景照调出"胶片感"，客户可能反复改，所以全部用调整图层，原图像素不动；天空单独压暗加饱和（选区作蒙版）。
交付分层 PSD 母版 + JPG，并把全局调色导出成 .cube LUT，套到另一张照片上统一风格。

用法: python 07-nondestructive-grade.py [风景照] [要套用风格的照片]
"""
from __future__ import annotations

import shutil
from pathlib import Path

from pcx import *


def main(args):
    src = pcx_input(args[0] if args else "", "landscape.jpg", kind="file")
    other = pcx_input(args[1] if len(args) > 1 else "", "portrait.jpg", kind="file")
    pcx_init("07-nondestructive-grade")
    shutil.copy2(src, "source.jpg")
    shutil.copy2(other, "other.jpg")

    step("调整图层叠加：S 曲线抬黑位 → 自然饱和度 → 色彩平衡（暗部偏蓝、亮部偏暖）→ 天空蒙版色相/饱和度")
    pc_run([
        ("layer.newAdjustmentLayer.curves", {"points": [[0, 14], [64, 56], [128, 130], [192, 206], [255, 246]]}),
        ("layer.renameLayer", {"name": "Film curve"}),
        ("layer.newAdjustmentLayer.vibrance", {"vibrance": 30, "saturation": -6}),
        ("layer.newAdjustmentLayer.colorBalance", {"shadows": [-10, 0, 14], "highlights": [12, 0, -12]}),
        ("layer.renameLayer", {"name": "Split tone"}),
        ("select.sky",),
        ("select.modify.feather", {"radius": 12}),
        ("layer.newAdjustmentLayer.hueSaturation", {"saturation": 18, "lightness": -10}),
        ("layer.renameLayer", {"name": "Sky"}),
    ], input="source.jpg", out="graded.psd", check=True)
    for l in info("graded.psd").layers:
        print("  #%s %s %s%s" % (l.id, l.kind, l.name, " (mask)" if l.hasMask else ""))

    step("客户说曲线太重：只改那一层的参数（layer.setAdjustment），别的层不受影响")
    curve_id = next(l.id for l in info("graded.psd").layers if l.name == "Film curve")
    # 0.18 起 run 也拒绝 out==input，覆盖原稿必须显式 --in-place
    pc_run([("layer.setAdjustment", {"layer": curve_id,
                                     "points": [[0, 8], [64, 60], [128, 130], [192, 200], [255, 250]]})],
           input="graded.psd", out="graded.psd", extra=("--in-place",), check=True)
    pc("convert", "graded.psd", "graded.jpg", "--quality", "90")

    step("导出 LUT：只取全局调整层（蒙版是空间信息，LUT 表达不了，天空层要排除）")
    # 调整图层自带一张白色蒙版，hasMask 恒为 true，不能据此判断是否局部调整：按名字挑。
    ids = [l.id for l in info("graded.psd").layers if l.kind == "Adjustment" and l.name != "Sky"]
    out = pc_run([("file.export.colorLookupTables", {"path": "film-look.cube", "size": 33,
                                                     "title": "Film look", "layers": ids})], input="graded.psd")
    r = pc_result(out, "file.export.colorLookupTables")
    print("LUT %s^3 from %s layers" % (r["size"], r["layerCount"]))
    print("\n".join(Path("film-look.cube").read_text(encoding="utf-8").splitlines()[:3]))

    step("把 LUT 作为颜色查找调整图层套到另一张照片（仍可关掉或改不透明度）")
    pc_run([("layer.newAdjustmentLayer.colorLookup", {"file": "film-look.cube"}),
            ("layer.setProps", {"opacity": 0.85})], input="other.jpg", out="other-film.psd", check=True)
    pc("convert", "other-film.psd", "other-film.jpg", "--quality", "90")

    step("核对：原图像素一个都没变；调色的差异明显大于单纯重新编码 JPEG 的误差")
    adj = [l.id for l in info("graded.psd").layers if l.kind == "Adjustment"]
    pc_run([("layer.setProps", {"layers": adj, "visible": False})], input="graded.psd", out="base.psd")
    pc("convert", "base.psd", "base.ppm")
    pcx_ppm("source.jpg", "source.ppm")
    pc("convert", "source.jpg", "source-q90.jpg", "--quality", "90")
    pcx_ppm("source-q90.jpg", "source-q90.ppm")
    pcx_ppm("graded.jpg", "graded.ppm")

    src_img, base, q90, graded = (Img(f) for f in ("source.ppm", "base.ppm", "source-q90.ppm", "graded.ppm"))
    d_base = diff(src_img, base)[1]
    d_noise = diff(src_img, q90, step=2)[0]
    d_grade = diff(q90, graded, step=2)[0]
    note("background vs source: max diff %.4f" % d_base)
    note("re-encode only: mean diff %.4f; graded vs re-encode: mean diff %.4f" % (d_noise, d_grade))
    if d_base > 1 / 255:
        fail("background pixels changed")
    if not (d_grade >= 0.015 and d_grade >= 5 * d_noise):
        fail("grade is not clearly visible above JPEG noise")
    note("ok  original pixels untouched; grade clearly visible")
    for p in Path(".").glob("*.ppm"):
        p.unlink()

    expect("graded.psd", lambda k: len([l for l in k.layers if l.kind == "Adjustment"]) == 4
           and any(l.name == "Sky" and l.hasMask for l in k.layers), "4 adjustment layers, sky one masked")
    if "LUT_3D_SIZE 33" not in Path("film-look.cube").read_text(encoding="utf-8").splitlines():
        fail("not a 33-point .cube")
    note("ok  film-look.cube is a 33-point 3D LUT")
    expect("other-film.psd", lambda k: any(l.kind == "Adjustment" for l in k.layers),
           "LUT applied as an adjustment layer")


run(main)
