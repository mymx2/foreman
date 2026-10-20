#!/usr/bin/env python3
"""场景：工单截图和活动照片要发到公开渠道，先脱敏。

 - 文字类个人信息和机密（姓名、邮箱、API key、卡号）一律实心色块覆盖：马赛克和模糊在小字号上可以被逐字比对还原
 - 头像、人脸用马赛克，只需不可辨认；照片里的人脸自动检测，漏检的脸用 face: 区域补上
 - 分享版用 Save for Web 去掉全部元数据（作者、版权、相机信息、GPS 等）

脚本找不到机密在哪：用户截图必须逐个给出区域（坐标从预览图上量），不给就报错退出。交付前看一眼分享版。

用法: python 10-privacy-redaction.py                              演示：内置截图 + 内置人像
      python 10-privacy-redaction.py 截图 区域…                    只处理截图（区域必填）
      python 10-privacy-redaction.py 截图 照片 区域…               截图 + 照片
      python 10-privacy-redaction.py - 照片 [face:x,y,w,h …]       只处理照片
区域写法："x,y,w,h" 实心色块；"mosaic:x,y,w,h" 截图里的马赛克（头像、图片）；"face:x,y,w,h" 照片里补一张脸
"""
from __future__ import annotations

import math
import re
import shutil
from pathlib import Path

from pcx import *

RECT = re.compile(r"^\d+,\d+,\d+,\d+$")


def main(args):
    files, solid, mosaic, faces = [], [], [], []
    for a in args:
        if RECT.match(a):
            solid.append(a)
        elif a.startswith("mosaic:") and RECT.match(a[7:]):
            mosaic.append(a[7:])
        elif a.startswith("face:") and RECT.match(a[5:]):
            faces.append(a[5:])
        else:
            files.append(a)
    if len(files) > 2:
        fail("at most two files (screenshot, photo); regions look like x,y,w,h, mosaic:x,y,w,h or face:x,y,w,h")

    shot = photo = None
    if not files:
        if solid or mosaic or faces:
            fail("regions need the file they belong to")
        shot, photo = fixture("screenshot.png"), fixture("portrait.jpg")
        # 内置截图的敏感区域（与 pcx.py 的 _fx_screenshot 布局一致）：姓名、邮箱、API key、卡号；头像打马赛克
        solid = ["436,140,140,38", "436,180,262,32", "466,334,300,30", "466,398,236,30"]
        mosaic = ["306,122,108,108"]
    else:
        if files[0] != "-":
            shot = pcx_input(files[0], "", kind="file")
        if len(files) > 1:
            photo = pcx_input(files[1], "", kind="file")
        if shot and not solid and not mosaic:
            fail("a screenshot of your own needs explicit regions: x,y,w,h for every secret or piece of "
                 "personal text, mosaic:x,y,w,h for avatars (the script cannot find them by itself)")
        if not shot and (solid or mosaic):
            fail("x,y,w,h and mosaic: regions belong to a screenshot, but none was given")
        if not photo and faces:
            fail("face: regions belong to a photo, but none was given")

    if shot is None and photo is None:
        fail("nothing to redact: pass a screenshot, a photo, or '-' plus a photo")

    pcx_init("10-privacy-redaction")

    if shot:
        shutil.copy2(shot, "shot.png")
        step("截图：文字类区域合并成一个选区 → 实心填充 #111827；头像区域 → 马赛克")
        cmds, mode = [], "replace"
        for r in solid:
            cmds.append(("select.rect", _sel(r, mode)))
            mode = "add"
        if solid:
            cmds.append(("edit.fill", {"contents": "color", "color": "#111827"}))
        if mosaic:
            mode = "replace"
            for r in mosaic:
                cmds.append(("select.rect", _sel(r, mode)))
                mode = "add"
            cell = max(8, max(round(max(rect(r)[2:]) / 8) for r in mosaic))
            cmds.append(("filter.pixelate.mosaic", {"cellSize": cell}))
        cmds.append(("select.deselect",))
        pc_run(cmds, input="shot.png", out="shot-redacted.png", check=True)
        note("%d solid box(es), %d mosaic area(s)" % (len(solid), len(mosaic)))
        # 分享版：PNG-24 保持文字清晰，metadata none 去掉全部元数据
        pc_run([("file.export.saveForWebLegacy", {"format": "png24", "metadata": "none",
                                                  "path": "shot-share.png"})],
               input="shot-redacted.png", check=True)

    if photo:
        shutil.copy2(photo, "photo.jpg")
        if not user_mode():
            # 演示：先写入作者、版权、地点等元数据，后面核对分享版确实去掉了
            pc_run([("file.fileInfo", {"author": "Event Photographer",
                                       "copyright": "(c) 2026 Example Events",
                                       "description": "Riverside Plaza, GPS 31.23N 121.47E"})],
                   input="photo.jpg", out="photo.jpg", extra=("--quality", "95"))
        step("照片：自动检测所有人脸（再加上手动补的 face: 区域），各自外扩 15% 后打马赛克（格子随脸大小变化）")
        found = pc_result(pc_run([("image.detectFaces", {"minScore": 0.5})], input="photo.jpg"),
                          "image.detectFaces")["faces"]
        all_faces = [[round(v) for v in f["rect"]] for f in found] + [rect(r) for r in faces]
        if not all_faces:
            fail("no faces detected; check the photo and pass face:x,y,w,h for each face")
        cmds = []
        for i, (x, y, w, h) in enumerate(all_faces):
            cmds.append(("select.rect", {"x": round(x - w * 0.15), "y": round(y - h * 0.15),
                                         "width": round(w * 1.3), "height": round(h * 1.3),
                                         "ellipse": True, "mode": "add" if i else "replace"}))
        cell = max(8, round(max(f[2] for f in all_faces) / 10))
        cmds += [("filter.pixelate.mosaic", {"cellSize": cell}), ("select.deselect",)]
        pc_run(cmds, input="photo.jpg", out="photo-redacted.png", check=True)
        note("%d face(s), mosaic cell %dpx" % (len(all_faces), cell))
        # saveForWebLegacy 的 quality 是 0..100（多数引擎导出命令是 0..12，这里是例外）
        pc_run([("file.export.saveForWebLegacy", {"format": "jpeg", "quality": 80, "metadata": "none",
                                                  "convertToSrgb": True, "path": "photo-share.jpg"})],
               input="photo-redacted.png", check=True)

    step("核对")

    def meta_clean(path):
        r = pc_result(pc_run([("file.fileInfo",)], input=path), "file.fileInfo")
        keys = ("author", "authorTitle", "copyright", "copyrightUrl", "description", "title", "keywords")
        return not any(r.get(k) for k in keys) and not r.get("camera")

    if shot:
        pcx_ppm("shot.png", "shot.ppm")
        pcx_ppm("shot-redacted.png", "shot-redacted.ppm")
        pcx_ppm("shot-share.png", "shot-share.ppm")
        src, red, share = Img("shot.ppm"), Img("shot-redacted.ppm"), Img("shot-share.ppm")
        bad = 0
        for r in solid:
            x, y, w, h = rect(r)
            total = 0
            left = 0
            for p in red.pixels(x, y, w, h):
                total += 1
                left += rgb255(p) != "17,24,39"
            note(("ok  " if left == 0 else "BAD ") +
                 "solid %d,%d,%d,%d: %d of %d pixels not #111827" % (x, y, w, h, left, total))
            bad += left > 0
        for r in mosaic:
            x, y, w, h = rect(r)
            cells = (math.ceil(w / cell) + 1) * (math.ceil(h / cell) + 1)
            a, b = colours(src, x, y, w, h), colours(red, x, y, w, h)
            note(("ok  " if b <= cells else "BAD ") +
                 "mosaic %d,%d,%d,%d: %d distinct colours -> %d (at most %d cells)" % (x, y, w, h, a, b, cells))
            bad += b > cells
        # 区域外一个像素都不许变
        regions = [rect(r) for r in solid + mosaic]
        stray = 0
        for yy in range(src.h):
            ra, rb = src.data[yy * src.stride:(yy + 1) * src.stride], red.data[yy * red.stride:(yy + 1) * red.stride]
            if ra == rb:
                continue
            for i in range(0, src.stride, src.c):
                if ra[i:i + src.c] != rb[i:i + src.c]:
                    xx = i // src.c
                    if not any(x <= xx < x + w and y <= yy < y + h for x, y, w, h in regions):
                        stray += 1
        note(("ok  " if stray == 0 else "BAD ") + "%d changed pixels outside the regions" % stray)
        bad += stray > 0
        box = changed_bbox(red, share)
        note(("ok  " if box is None else "BAD ") +
             ("share PNG has the same pixels as the redacted master" if box is None else "share PNG differs in %s" % box))
        bad += box is not None
        if bad:
            fail("screenshot redaction check failed")
        if not meta_clean("shot-share.png"):
            fail("shot-share.png still carries metadata")
        note("ok  shot-share.png carries no metadata")
        if demo_only("fixture secrets (name, email, API key, card) lie inside the solid boxes"):
            # 内置截图里这些文字的实际墨迹范围（量自 fixture）：必须完全落在实心框里
            ink = {"name": [441, 146, 128, 26], "email": [441, 189, 240, 20],
                   "API key": [471, 341, 275, 15], "card": [471, 405, 214, 15]}
            boxes = [rect(r) for r in solid]
            missing = [k for k, b in ink.items() if not any(inside(b, s) for s in boxes)]
            note(("ok  " if not missing else "BAD ") +
                 "secrets covered: " + ", ".join(k for k in ink if k not in missing))
            if missing:
                fail("a fixture secret is not inside a solid box")

    if photo:
        pcx_ppm("photo.jpg", "photo.ppm")
        pcx_ppm("photo-redacted.png", "photo-redacted.ppm")
        pcx_ppm("photo-share.jpg", "photo-share.ppm")
        src, red, share = Img("photo.ppm"), Img("photo-redacted.ppm"), Img("photo-share.ppm")
        bad = 0
        for x, y, w, h in all_faces:
            inner = [round(x + w * 0.2), round(y + h * 0.2), round(w * 0.6), round(h * 0.6)]
            cells = (math.ceil(inner[2] / cell) + 1) * (math.ceil(inner[3] / cell) + 1)
            a, b = colours(src, *inner), colours(red, *inner)
            sa, sb = src.stats(*inner)[1], red.stats(*inner)[1]
            good = b <= cells < a
            note(("ok  " if good else "BAD ") +
                 "face %d,%d,%d,%d: %d distinct colours -> %d (at most %d cells); overall spread %.3f -> %.3f"
                 % (x, y, w, h, a, b, cells, sum(sa) / 3, sum(sb) / 3))
            bad += not good
        boxes = [[round(x - w * 0.15) - 1, round(y - h * 0.15) - 1, round(w * 1.3) + 2, round(h * 1.3) + 2]
                 for x, y, w, h in all_faces]
        stray = 0
        for yy in range(src.h):
            ra, rb = src.data[yy * src.stride:(yy + 1) * src.stride], red.data[yy * red.stride:(yy + 1) * red.stride]
            if ra == rb:
                continue
            for i in range(0, src.stride, src.c):
                if ra[i:i + src.c] != rb[i:i + src.c]:
                    xx = i // src.c
                    if not any(bx <= xx < bx + bw and by <= yy < by + bh for bx, by, bw, bh in boxes):
                        stray += 1
        note(("ok  " if stray == 0 else "BAD ") + "%d changed pixels outside the face boxes" % stray)
        bad += stray > 0
        m, mx = diff(red, share, step=2)
        note(("ok  " if m <= 0.02 else "BAD ") + "share JPEG vs redacted master: mean diff %.4f (JPEG only)" % m)
        bad += m > 0.02
        if bad:
            fail("photo redaction check failed")
        if not meta_clean("photo-share.jpg"):
            fail("photo-share.jpg still carries metadata")
        note("ok  photo-share.jpg carries no metadata")

    for p in Path(".").glob("*.ppm"):
        p.unlink()
    note("look at the share files before posting: the script only proves the given regions were covered")


def _sel(spec, mode):
    x, y, w, h = rect(spec)
    return {"x": x, "y": y, "width": w, "height": h, "mode": mode}


run(main)
