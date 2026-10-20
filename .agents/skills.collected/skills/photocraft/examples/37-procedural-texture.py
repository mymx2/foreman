#!/usr/bin/env python3
"""场景：没有素材也要一张"手绘纸纹"背景：画笔笔触打底、渐变铺色、滤镜做纹理、噪点收尾、叠标题。

要点：
 - paint.stroke 的 hardness/opacity/flow 是 0..1（和修复类画笔的 0..100 不同，超出会被静默截断）。
 - 滤镜是破坏性的：拿不准的步骤复制图层或先转智能对象，改参数时还能回头。
 - 每次加滤镜后看一次预览；效果过头的往回退一档。

用法: python 37-procedural-texture.py
"""
from __future__ import annotations

from pathlib import Path

from pcx import *


def main(args):
    pcx_init("37-procedural-texture")

    step("底色：米白到浅灰的线性渐变")
    pc_run([("layer.newFillLayer.gradient", {"from": "#f7f3ea", "to": "#e2dccd", "angle": 90})],
           new={"width": 1600, "height": 1000, "background": "#f7f3ea", "name": "paper"},
           out="base.psd", check=True)

    step("底纹笔触：若干条半透明粗笔触，模拟纸浆纤维")
    pc_run([("layer.new.layer", {"name": "Fibres"})] + [
        ("paint.stroke", {"points": [[80, y + (i % 3) * 8], [500, y - 20], [900, y + 14], [1520, y - 6]],
                          "size": 90, "hardness": 0.15, "opacity": 0.06, "flow": 0.5,
                          "color": "#b9a98f" if i % 2 == 0 else "#cfc3ad", "smoothing": 0.8})
        for i, y in enumerate(90 + i * 100 for i in range(9))],
        input="base.psd", out="fibres.psd", check=True)

    step("纹理：波浪扭曲 + 高斯模糊软化 + 杂色收尾")
    pc_run([("filter.distort.wave", {"generators": 2, "wavelengthMin": 120, "wavelengthMax": 220,
                                     "amplitudeMin": 4, "amplitudeMax": 10, "type": "sine",
                                     "undefinedAreas": "repeat", "seed": 11}),
            ("filter.blur.gaussianBlur", {"radius": 1.2}),
            ("layer.new.layer", {"name": "Grain"}),
            ("edit.fill", {"contents": "color", "color": "#808080"}),
            ("filter.noise.addNoise", {"amount": 6, "distribution": "gaussian", "monochromatic": True, "seed": 11}),
            ("layer.setProps", {"blend": "Overlay", "opacity": 0.35})],
           input="fibres.psd", out="texture.psd", check=True)

    step("叠标题和副标题（文字层保持可编辑）")
    pc_run([("type.create", {"x": 800, "y": 430, "text": "HANDMADE", "size": 120, "color": "#3b3226",
                             "align": "center", "tracking": 30, "name": "Title"}),
            ("type.create", {"x": 800, "y": 500, "text": "paper texture · generated in PhotoCraft",
                             "size": 32, "color": "#6b604e", "align": "center", "name": "Subtitle"}),
            ("layer.layerStyle.dropShadow", {"color": "#ffffff", "opacity": 35, "distance": 1, "size": 2,
                                              "angle": 90})],
           input="texture.psd", out="paper-texture.psd", check=True)
    pc("convert", "paper-texture.psd", "paper-texture.jpg", "--quality", "90")

    step("核对")
    expect_size("paper-texture.jpg", 1600, 1000)
    expect("paper-texture.psd", lambda k: any(l.name == "Title" and l.kind == "Type" for l in k.layers),
           "title stays a live type layer")
    expect("paper-texture.psd", lambda k: any(l.name == "Grain" and l.blend == "Overlay" for l in k.layers),
           "grain layer kept separate with Overlay")

    # 纹理要"有变化但不脏"：整图亮度标准差在合理区间，四个角落不是纯色
    pcx_ppm("paper-texture.jpg", "tex.ppm")
    im = Img("tex.ppm")
    mean, sd = im.stats(0, 0, im.w, im.h, step=7)
    lum_sd = sum(sd) / 3
    note("mean luminance %.3f, spread %.3f" % (sum(mean) / 3, lum_sd))
    corners = []
    for x, y in ((0, 0), (im.w - 120, 0), (0, im.h - 120), (im.w - 120, im.h - 120)):
        rows = [im.data[yy * im.stride + x * im.c:yy * im.stride + (x + 120) * im.c]
                for yy in range(y, y + 120, 7)]
        corners.append(len(set(rows)))
    note("distinct corner rows: %s" % corners)
    Path("tex.ppm").unlink(missing_ok=True)
    if not (0.02 < lum_sd < 0.25 and min(corners) > 1):
        fail("the texture is either flat or too noisy")
    note("ok  visible grain, no flat corners")


run(main)
