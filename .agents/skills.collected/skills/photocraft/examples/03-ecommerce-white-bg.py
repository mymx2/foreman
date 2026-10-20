#!/usr/bin/env python3
"""场景：电商平台要求主图纯白底（RGB 255）、正方形 2000px、商品长边约占 90%（1800px）、sRGB JPEG。
一批棚拍原片偏暖、背景发灰、比例各异，商品在画面里大小不一。
流程：动作文件定义一次步骤 → batch 跑整个文件夹 → 逐张质检 → 不合格的列出来人工复查。

要点：
 - 去色偏用"背景角落作白点"的色阶吸管：棚拍背景本该是白的，以它为参照只去掉灯光色偏。
   不用 image.autoColor：画面里没有真正的中性色时它会把整张图推偏（实测琥珀色瓶子变成灰蓝）。
 - 抠图后先 image.trim 裁到主体（removeBackground 加的蒙版也按透明算），fitImage 才按商品而不是按原画面缩放。
 - 质检：在原片上单独跑一遍"白点 + 抠图"拿到商品框，推算它在成品里应占的位置。

用法: python 03-ecommerce-white-bg.py [原片目录]     原片背景角落（24,24）应是白色或浅灰背景布
"""
from __future__ import annotations

import json
import re
import shutil
from pathlib import Path

from pcx import *


def main(args):
    src_dir = pcx_input(args[0] if args else "", "products", kind="dir")
    pcx_init("03-ecommerce-white-bg")
    pcx_copy_dir(src_dir, Path("in"))
    actions = EX_DIR / "actions" / "ecommerce-white-bg.json"

    step("批处理：背景白点去色偏 → 抠主体 → 裁到主体 → 长边 1800 → 透明扩到 2000 方形 → 垫白底 → 拼合 → USM 锐化 → 转 sRGB")
    proc = pc("batch", "--actions", str(actions), "--in", "in", "--out", "white", "--format", "jpg",
              "--quality", "85", capture=True)
    print(proc.stdout, end="")
    if proc.returncode != 0:
        fail(f"batch failed\n{proc.stderr[-1200:]}")

    step("质检：尺寸 2000x2000；商品框位置与大小；框外纯白；商品中心的色相与原片相差不超过 25°、饱和度在原片的 0.6~1.5 倍")
    review = []
    for f in sorted(Path("white").glob("*.jpg")):
        stem = f.stem
        src = next(Path("in").glob(stem + ".*"))
        expect_size(f, 2000, 2000)
        box = pc_result(pc_run([("layer.removeBackground", {"refine": True})], input=str(src)),
                        "layer.removeBackground")["bounds"]
        pcx_ppm(f, f"white/{stem}.ppm")
        verdict = _product_check(f"white/{stem}.ppm", box)
        if verdict.startswith("ok"):
            note(f"ok  {f} {verdict[3:]}")
        else:
            review.append(f"{f} ({verdict})")
        Path(f"white/{stem}.ppm").unlink(missing_ok=True)

        # 商品中心：原片取商品框中心，成品取画面中心
        cx, cy = round(box[0] + box[2] / 2), round(box[1] + box[3] / 2)
        a = pc_result(pc_run([("document.sampleColor", {"x": cx, "y": cy, "size": 31})], input=str(src)),
                      "document.sampleColor")
        b = pc_result(pc_run([("document.sampleColor", {"x": 1000, "y": 1000, "size": 31})], input=str(f)),
                      "document.sampleColor")
        h1, s1 = hue_sat(a)
        h2, s2 = hue_sat(b)
        dh = hue_diff(h1, h2)
        colour = "hue %.0f -> %.0f (diff %.0f), saturation %.2f -> %.2f" % (h1, h2, dh, s1, s2)
        if dh <= 25 and s1 * 0.6 <= s2 <= s1 * 1.5:
            note(f"ok  {f} {colour}")
        else:
            review.append(f"{f} ({colour})")
    if review:
        fail("needs manual review: " + "; ".join(review))

    step("上架命名：file.automate.batch 支持命名模板与序号（CLI batch 只保留原文件名）")
    steps = json.loads(actions.read_text(encoding="utf-8"))["steps"]
    params = {"input": "in", "output": "upload", "steps": steps, "format": "jpg", "quality": 10,
              "naming": "SKU-{serial}_{name}", "startingSerial": 101}
    out = pc_run([("file.automate.batch", params)], new={"width": 1, "height": 1})
    r = pc_result(out, "file.automate.batch")
    print("files: %d, errors: %d\n" % (len(r["files"]), len(r["errors"])) + "\n".join(r["files"]))
    if len(r["errors"]):
        fail("file.automate.batch reported errors")
    n_in = len([p for p in Path("in").iterdir() if p.is_file()])
    expect_count("upload", "SKU-1??_*.jpg", n_in)


def _product_check(ppm, box):
    x, y, w, h = box
    s = 1800 / max(w, h)
    ew, eh = w * s, h * s
    ex, ey = (2000 - ew) / 2, (2000 - eh) / 2
    im = Img(ppm)
    got = im.ink_bbox(0.98)
    if got is None:
        return "no product found (all white)"
    gx, gy, gw, gh = got
    err = max(abs(gx - ex), abs(gy - ey), abs(gx + gw - ex - ew), abs(gy + gh - ey - eh))
    stray = im.count_ink(254 / 255) - im.count_ink(254 / 255, ex - 16, ey - 16, ew + 32, eh + 32)
    msg = ("product %dx%d at (%d,%d), expected %.0fx%.0f at (%.0f,%.0f), upscaled x%.2f; %d non-white samples outside"
           % (gw, gh, gx, gy, ew, eh, ex, ey, s, stray))
    return ("ok  " if err <= 16 and stray == 0 else "") + msg


run(main)
