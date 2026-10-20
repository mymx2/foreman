#!/usr/bin/env python3
"""场景一：转着身子拍了三张有重叠的照片，拼成一张全景，裁掉拼接后的透明边。
场景二：逆光风景包围曝光 -2/0/+2 EV，合成 HDR：交付 16 位色调映射 TIFF + 8 位 JPG，另存 32 位 EXR 母版留后期。

要点：
 - photomerge 的 contentAwareFill:true 让边缘露出的空白按周围内容补上，比只做 image.trim 干净；
   image.trim 只删"整行/整列全透明"，斜接的全景边缘会留下锯齿状白边。
 - mergeToHdrPro 的 mode 是字符串 "16"/"32"；EXR 母版保存 32 位浮点。

用法: python 22-panorama-and-hdr.py [全景素材目录] [包围曝光目录]
"""
from __future__ import annotations

import json
import re
import shutil
from pathlib import Path

from pcx import *


def main(args):
    tiles_dir = pcx_input(args[0] if args else "", "", kind="dir")
    brackets_dir = pcx_input(args[1] if len(args) > 1 else "", "", kind="dir")
    pcx_init("22-panorama-and-hdr")
    Path("tiles").mkdir()
    Path("brackets").mkdir()
    shutil.copy2(fixture("landscape.jpg"), "scene.jpg")

    if tiles_dir is not None:
        pcx_copy_dir(tiles_dir, Path("tiles"))
        if not any(Path("tiles").iterdir()):
            fail(f"no files in {tiles_dir}")
    else:
        step("模拟三张重叠约 35% 的照片")
        for x in (0, 390, 780):
            pc_run([("image.crop", {"x": x, "y": 0, "width": 620, "height": 837})], input="scene.jpg",
                   out=f"tiles/pano-{x}.jpg", extra=("--quality", "92"), check=True)

    step("全景拼接：自动版式、融合接缝、内容识别补边 → 再清一次透明边")
    out = pc_run([("file.automate.photomerge", {"paths": "tiles", "layout": "auto", "blend": True,
                                                "vignetteRemoval": True, "contentAwareFill": True}),
                  ("image.trim", {"basedOn": "transparent"})],
                 new={"width": 1, "height": 1}, out="panorama.psd", check=True)
    r = pc_result(out, "file.automate.photomerge")
    print("(layout %s, %d images, %d failed)" % (r["layout"], len(r["placed"]), len(r["failed"])))
    pc("convert", "panorama.psd", "panorama.jpg", "--quality", "90")

    if brackets_dir is not None:
        pcx_copy_dir(brackets_dir, Path("brackets"))
        if not any(Path("brackets").iterdir()):
            fail(f"no files in {brackets_dir}")
    else:
        step("模拟包围曝光")
        pc_run([("image.adjustments.exposure", {"exposure": -2})], input="scene.jpg",
               out="brackets/ev-2.jpg", extra=("--quality", "95"), check=True)
        shutil.copy2("scene.jpg", "brackets/ev0.jpg")
        pc_run([("image.adjustments.exposure", {"exposure": 2})], input="scene.jpg",
               out="brackets/ev+2.jpg", extra=("--quality", "95"), check=True)

    step("HDR 合成：16 位局部适应色调映射 + 32 位线性母版")
    files = sorted(Path("brackets").iterdir())
    paths, exposures = [], []
    for f in files:
        m = re.search(r"ev([+-]?\d+)", f.name)
        if m:
            paths.append(str(f))
            exposures.append(float(m.group(1)))
    order = sorted(range(len(paths)), key=lambda i: exposures[i])
    base = {"paths": [paths[i] for i in order], "exposures": [exposures[i] for i in order]}

    hdr16 = dict(base, mode="16", method="localAdaptation", radius=60, strength=0.8, detail=40, vibrance=15)
    hdr32 = dict(base, mode="32")
    pc_run([("file.automate.mergeToHdrPro", hdr16)], new={"width": 1, "height": 1}, out="hdr-16bit.tif", check=True)
    pc_run([("file.automate.mergeToHdrPro", hdr32)], new={"width": 1, "height": 1}, out="hdr-linear.exr", check=True)
    # 降位深再导出 JPG：这是交付版，保留 EXR 作为母版
    pc_run([("image.mode.bits8",)], input="hdr-16bit.tif", out="hdr.jpg", extra=("--quality", "92"), check=True)

    step("核对")
    if demo_only("fixture panorama restores the 1400x837 original"):
        expect("panorama.jpg", lambda k: abs(k.width - 1400) <= 40 and abs(k.height - 837) <= 40,
               "panorama is about 1400x837 (the original before splitting)")
    else:
        expect("panorama.jpg", lambda k: k.width > 0 and k.height > 0, "panorama exists")
    expect("hdr-16bit.tif", lambda k: k.depth == 16, "tone-mapped HDR is 16-bit")
    expect("hdr-linear.exr", lambda k: k.depth == 32, "linear HDR master is 32-bit float")

    # 全景边缘：白边检测（内容识别补边后不应有整片纯白）
    pcx_ppm("panorama.jpg", "pano.ppm")
    im = Img("pano.ppm")
    band, bad = 6, 0
    for box in ((0, 0, im.w, band), (0, im.h - band, im.w, band), (0, 0, band, im.h), (im.w - band, 0, band, im.h)):
        x0, y0, x1, y1 = im.clip(*box)
        bad += sum(1 for p in im.pixels(x0, y0, x1 - x0, y1 - y0, 2) if min(p[:3]) > 0.97)
    note(("ok  " if bad == 0 else "BAD ") + "%d near-white pixels in the panorama border bands" % bad)
    Path("pano.ppm").unlink(missing_ok=True)
    if bad:
        fail("panorama still has white edge strips")
    note("ok  panorama edges are filled")

    def lum(path, x, y):
        r = pc_result(pc_run([("document.sampleColor", {"x": x, "y": y, "size": 31})], input=path),
                      "document.sampleColor")
        return (r[0] + r[1] + r[2]) / 3

    s_dark, s_hdr = lum("brackets/ev-2.jpg", 150, 720), lum("hdr.jpg", 150, 720)
    h_bright, h_hdr = lum("brackets/ev+2.jpg", 700, 120), lum("hdr.jpg", 700, 120)
    note("shadow: ev-2 %.3f -> hdr %.3f; highlight: ev+2 %.3f -> hdr %.3f" % (s_dark, s_hdr, h_bright, h_hdr))
    if not (s_hdr > s_dark and h_hdr < h_bright):
        fail("HDR did not lift shadows and hold highlights")
    note("ok  shadows lifted and highlights held")

    # 色彩：HDR 的暗部不应偏色（A26 的品红偏色回归检查）
    r = pc_result(pc_run([("document.sampleColor", {"x": 150, "y": 720, "size": 31})], input="hdr.jpg"),
                  "document.sampleColor")
    h = hue_sat(r[:3])[0]
    if 330 <= h or h <= 30:
        note("ok  HDR shadows stay neutral")
    else:
        note("note: HDR shadows carry a slight hue (tinted-hue-%d); check before delivery" % round(h))


run(main)
