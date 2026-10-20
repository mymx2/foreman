#!/usr/bin/env python3
"""场景：头像精修，交付分层 PSD。柔肤只作用在脸上、修掉面部斑点、提亮眼睛，三步各占一个图层，客户不满意可以单独关掉。

 - 柔肤：复制背景 → 表面模糊（保边）→ 羽化椭圆选区变蒙版（选区随之用掉）→ 不透明度 55%
 - 斑点：空白图层上逐点 paint.spotHealing（sampleAllLayers 取下面的合成）。points 是一笔连续笔画，
   几个斑点放进同一次调用会连成一条涂抹带，所以每个斑点单独调用一次。
 - 提亮眼睛：在中性灰的"叠加"图层（layer.new.layer fillNeutral）上减淡，不碰下面任何一层；
   不要在盖印图层上减淡：盖印层是全图合并副本，它可见时关掉下面的层看不出任何变化。

用法: python 08-portrait-retouch.py [人像 ["x,y" ...]]     用户模式不给斑点坐标时不建修斑点层
"""
from __future__ import annotations

import math
import shutil
from pathlib import Path

from pcx import *


def main(args):
    src = pcx_input(args[0] if args else "", "portrait.jpg", kind="file")
    spots = []
    for p in args[1:]:
        if not (p and all(part.isdigit() for part in p.split(",")) and len(p.split(",")) == 2):
            fail(f"blemish point must be x,y (got '{p}')")
        spots.append(p)
    pcx_init("08-portrait-retouch")
    shutil.copy2(src, "original.jpg")

    step("人脸与五官定位")
    faces = pc_result(pc_run([("image.detectFaces", {"minScore": 0.6})], input="original.jpg"),
                      "image.detectFaces")["faces"]
    if not faces:
        fail("no face found")
    face = faces[0]
    fx, fy, fw, fh = (round(v) for v in face["rect"])
    rex, rey = (round(v) for v in face["landmarks"]["rightEye"])
    lex, ley = (round(v) for v in face["landmarks"]["leftEye"])
    note(f"face {fx},{fy} {fw}x{fh}; eyes ({rex},{rey}) ({lex},{ley})")

    if user_mode():
        shutil.copy2("original.jpg", "source.jpg")
    else:
        step("演示素材：在面颊、额头点 5 个深色斑点（相对人脸框的位置）")
        ratios = [(0.50, 0.52), (0.68, 0.63), (0.57, 0.80), (0.82, 0.50), (0.35, 0.20)]
        spots = ["%d,%d" % (round(fx + u * fw), round(fy + v * fh)) for u, v in ratios]
        dots = [("paint.stroke", {"points": [[int(p.split(",")[0]), int(p.split(",")[1]), 1]],
                                  "size": 7, "hardness": 0.8, "color": "#5a3a2a"}) for p in spots]
        pc_run(dots, input="original.jpg", out="source.jpg", extra=("--quality", "92"), check=True)
    note("blemish points: " + (" ".join(spots) if spots else "none"))

    step("三个修图图层：柔肤（带蒙版）→ 修斑点（每个斑点一次 spotHealing）→ 提亮眼睛（中性灰叠加层上减淡）")
    heal = []
    if spots:
        heal.append(("layer.new.layer", {"name": "Spot heal"}))
        for p in spots:
            x, y = map(int, p.split(","))
            heal.append(("paint.spotHealing", {"points": [[x, y, 1]], "size": 16, "type": "contentAware",
                                               "sampleAllLayers": True}))
    cmds = [
        ("layer.duplicate", {"name": "Skin smooth"}),
        ("filter.blur.surfaceBlur", {"radius": 8, "threshold": 18}),
        ("select.rect", {"x": fx, "y": fy, "width": fw, "height": fh, "ellipse": True}),
        ("select.modify.feather", {"radius": 24}),
        ("layer.layerMask.revealSelection",),
        ("layer.setProps", {"opacity": 0.55}),
        *heal,
        ("layer.new.layer", {"name": "Eyes", "mode": "Overlay", "fillNeutral": True}),
        ("paint.dodge", {"points": [[rex - 8, rey, 1], [rex + 8, rey, 1]], "size": 22,
                         "range": "midtones", "exposure": 30}),
        ("paint.dodge", {"points": [[lex - 8, ley, 1], [lex + 8, ley, 1]], "size": 22,
                         "range": "midtones", "exposure": 30}),
    ]
    pc_run(cmds, input="source.jpg", out="retouched.psd", check=True)
    pc("convert", "retouched.psd", "retouched.jpg", "--quality", "92")

    step("核对：图层齐全；关掉任意一层，变化只出现在它负责的区域；脸以外的像素和原片一致")
    for l in info("retouched.psd").layers:
        print("  %s (%s, %s)%s opacity=%.2f" % (l.name, l.kind, l.blend, " mask" if l.hasMask else "", l.opacity))
    want = 3 + (1 if spots else 0)
    layers = info("retouched.psd").layers
    ok = (len(layers) == want
          and next(l for l in layers if l.name == "Skin smooth").hasMask
          and next(l for l in layers if l.name == "Eyes").blend == "Overlay")
    if not ok:
        fail("layer stack is not the expected three retouch layers")
    note(f"ok  {want} layers: Eyes (Overlay), " + ("Spot heal, " if spots else "") + "Skin smooth (masked), Background")

    pcx_ppm("source.jpg", "source.ppm")
    pcx_ppm("retouched.psd", "full.ppm")
    names = ["Skin smooth", "Eyes"] + (["Spot heal"] if spots else [])
    for name in names:
        pc_run([("layer.setProps", {"layer": name, "visible": False})], input="retouched.psd",
               out=f"without-{name.replace(' ', '-')}.psd")
        pc("convert", f"without-{name.replace(' ', '-')}.psd", f"without-{name.replace(' ', '-')}.ppm")

    full, source = Img("full.ppm"), Img("source.ppm")

    def union(boxes):
        x0, y0 = min(b[0] for b in boxes), min(b[1] for b in boxes)
        return [x0, y0, max(b[0] + b[2] for b in boxes) - x0, max(b[1] + b[3] for b in boxes) - y0]

    face_area = [fx - 48, fy - 48, fw + 96, fh + 96]
    eyes_area = union([[ex - 23, ey - 15, 46, 30] for ex, ey in ((rex, rey), (lex, ley))])
    spot_area = union([[x - 14, y - 14, 28, 28] for x, y in
                       (map(int, p.split(",")) for p in spots)]) if spots else None
    areas = {"Skin smooth": face_area, "Eyes": eyes_area, "Spot heal": spot_area}
    bad = 0
    for name, area in areas.items():
        if area is None:
            continue
        box = changed_bbox(full, Img(f"without-{name.replace(' ', '-')}.ppm"), tol=1)
        good = box is not None and inside(box, area)
        note(("ok  " if good else "BAD ") + "hiding %-11s changes %s (allowed area %s)" % (name, box, area))
        bad += not good
    box = changed_bbox(full, source, tol=1)
    good = box is not None and inside(box, face_area)
    note(("ok  " if good else "BAD ") + "retouch vs source differs only inside %s (face area %s)"
         % (box, face_area))
    bad += not good
    if bad:
        fail("a retouch layer is not independent or leaks outside its area")

    if spots:
        step("核对斑点：每个点的中心与周围一圈的亮度差（斑点对比度）要明显下降")

        def contrast(im, x, y):
            centre = [luma(im.px(xx, yy)) for yy in range(y - 1, y + 2) for xx in range(x - 1, x + 2)]
            ring = [luma(im.px(xx, yy)) for yy in range(y - 12, y + 13) for xx in range(x - 12, x + 13)
                    if 8 <= math.hypot(xx - x, yy - y) <= 12 and 0 <= xx < im.w and 0 <= yy < im.h]
            return sum(ring) / len(ring) - sum(centre) / len(centre)

        demo = not user_mode()
        for p in spots:
            x, y = map(int, p.split(","))
            a, b = contrast(source, x, y), contrast(full, x, y)
            if demo:
                # 演示斑点是我们画的，修复后对比度必须明显下降
                good = b < a * 0.35
                msg = "spot (%d,%d): contrast %.3f -> %.3f" % (x, y, a, b)
            else:
                # 用户给的坐标不一定是瑕疵；只验证这一带确实被处理过（像素有变化）
                box = changed_bbox(source, full, tol=2)
                good = box is not None and box[0] <= x < box[0] + box[2] and box[1] <= y < box[1] + box[3]
                msg = "spot (%d,%d): inside the retouched area %s" % (x, y, box)
            note(("ok  " if good else "BAD ") + msg)
            bad += not good
        if bad:
            fail("a blemish is still visible")
    for p in Path(".").glob("*.ppm"):
        p.unlink()


run(main)
