#!/usr/bin/env python3
"""场景：一张照片要发多个平台：1:1 方图、4:5 竖图、9:16 快拍、1200x630 链接预览图。
做法：人脸检测找到主体 → 每个比例取"能放下的最大窗口"并以人脸为中心 → image.crop 一步裁切并缩放到目标像素。
源图不够大时用 preserveDetails 放大并提示，避免默默输出糊图。

用法: python 04-social-media-crops.py [人像] [横幅风景]
"""
from __future__ import annotations

import math
import shutil

from pcx import *


def crop_params(path, tw, th, fx=None, fy=None):
    """能放下的最大同比例窗口，以焦点为中心；小于目标尺寸时用 preserveDetails 放大。"""
    j = info(path)
    fx = j.width / 2 if fx is None else fx
    fy = j.height / 2 if fy is None else fy
    s = min(j.width / tw, j.height / th)
    w, h = math.floor(tw * s), math.floor(th * s)
    x = round(min(max(fx - w / 2, 0), j.width - w))
    y = round(min(max(fy - h / 2, 0), j.height - h))
    if w < tw:
        print(f"note: source window {w}x{h} is smaller than {tw}x{th}; upscaling with preserveDetails",
              file=sys.stderr)
    return {"x": x, "y": y, "width": w, "height": h, "targetWidth": tw, "targetHeight": th,
            "resample": "preserveDetails" if w < tw else "bicubic"}


def main(args):
    portrait = pcx_input(args[0] if args else "", "portrait.jpg", kind="file")
    landscape = pcx_input(args[1] if len(args) > 1 else "", "landscape.jpg", kind="file")
    pcx_init("04-social-media-crops")
    shutil.copy2(portrait, "portrait.jpg")
    shutil.copy2(landscape, "landscape.jpg")

    step("找人脸：取置信度最高的一张脸的中心作为焦点")
    faces = pc_result(pc_run([("image.detectFaces", {"minScore": 0.6})], input="portrait.jpg"),
                      "image.detectFaces")["faces"]
    if not faces:
        fail("no face found; pass a focus point or crop centred")
    fx, fy, fw, fh = (round(v) for v in faces[0]["rect"])
    cx, cy = fx + fw // 2, fy + fh // 2
    note(f"face rect: {fx},{fy} {fw}x{fh}  -> focus ({cx}, {cy})")

    step("竖图三种比例，以人脸为中心")
    for name, tw, th in (("ig-square.jpg", 1080, 1080), ("ig-portrait.jpg", 1080, 1350), ("story.jpg", 1080, 1920)):
        pc_run([("image.crop", crop_params("portrait.jpg", tw, th, cx, cy))], input="portrait.jpg",
               out=name, extra=("--quality", "85"))

    step("链接预览图 1200x630：横图居中裁切，WebP 更小")
    pc_run([("image.crop", crop_params("landscape.jpg", 1200, 630))], input="landscape.jpg",
           out="og-image.webp", extra=("--quality", "80"))

    step("核对尺寸")
    expect_size("ig-square.jpg", 1080, 1080)
    expect_size("ig-portrait.jpg", 1080, 1350)
    expect_size("story.jpg", 1080, 1920)
    expect_size("og-image.webp", 1200, 630)

    step("核对构图：在成品上重新找脸，脸的中心要落在画面中线附近（窗口撑满原图的那个方向无法居中，不检查）")
    for name, axis in (("ig-square.jpg", "y"), ("story.jpg", "x")):
        j = info(name)
        found = pc_result(pc_run([("image.detectFaces", {"minScore": 0.6})], input=name),
                          "image.detectFaces")["faces"]
        if not found:
            continue
        x, y, w, h = found[0]["rect"]
        off = (abs(x + w / 2 - j.width / 2) / j.width if axis == "x"
               else abs(y + h / 2 - j.height / 2) / j.height)
        if off > 0.12:
            fail(f"{name}: face not centred on the {axis} axis (off {off:.3f})")
        note(f"ok  {name} face centred on the {axis} axis (offset {off:.3f})")


run(main)
