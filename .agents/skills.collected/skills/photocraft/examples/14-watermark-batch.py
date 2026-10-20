#!/usr/bin/env python3
"""场景：一批作品图发布前加水印，两种规格：图形 Logo（右下角、75% 不透明）和文字版权（带投影，任何底色都看得清）。

动作集（actions/watermark-set.json）里放三个动作，"Fit 2048" 被另外两个用 actions.play 调用；
位置不写死坐标，用"对齐画布右下 + 平移留边"，所以横图竖图大小不一都能放对。
质检的参照是同一张图只跑 "Fit 2048" 的结果（大图会先被缩小，直接和原图比位置就错了）。

用法: python 14-watermark-batch.py [图片目录]     只取目录第一层的文件
"""
from __future__ import annotations

import shutil
from pathlib import Path

from pcx import *


def main(args):
    photos_dir = pcx_input(args[0] if args else "", "", kind="dir")
    pcx_init("14-watermark-batch")
    Path("photos").mkdir(exist_ok=True)
    if user_mode():
        pcx_copy_dir(photos_dir, Path("photos"))
    else:
        for name in ("portrait.jpg", "landscape.jpg", "product.png"):
            shutil.copy2(fixture(name), Path("photos") / name)
    shutil.copy2(EX_DIR / "actions" / "watermark-set.json", "watermark-set.json")

    step("做 Logo：透明底 PNG（圆角底板 + 文字）")
    pc_run([("shape.create", {"kind": "roundedRect", "rect": [0, 0, 260, 72], "radii": 14, "fill": [0, 0, 0, 0.45]}),
            ("type.create", {"x": 130, "y": 47, "text": "STUDIO NORTH", "size": 26, "color": "#ffffff",
                             "align": "center"})],
           new={"width": 260, "height": 72, "background": "transparent", "name": "logo"}, out="logo.png", check=True)

    step("动作集里有 3 个动作，必须用 --action 指定要播放的那个")
    missing = pc("batch", "--actions", "watermark-set.json", "--in", "photos", "--out", "x", capture=True)
    expect_error(missing, "--action", "batch asks for --action on a multi-action set")

    step("批处理两种水印（logo.png 是相对路径，按当前目录解析）")
    for action, out_dir in (("Logo watermark", "marked-logo"), ("Text watermark", "marked-text"),
                            ("Fit 2048", "reference")):
        proc = pc("batch", "--actions", "watermark-set.json", "--action", action, "--in", "photos",
                  "--out", out_dir, "--format", "jpg", "--quality", "88", capture=True)
        if proc.returncode != 0:
            fail(f"batch action {action!r} failed\n{proc.stderr[-1200:]}")

    step("核对：与只缩放的参照图比，右下角水印区有明显变化，左上角不变")
    for out_dir in ("marked-logo", "marked-text"):
        for f in sorted(Path(out_dir).glob("*.jpg")):
            stem = f.stem
            pcx_ppm(f, "mark.ppm")
            pcx_ppm(Path("reference") / f"{stem}.jpg", "ref.ppm")
            a, b = Img("ref.ppm"), Img("mark.ppm")
            W, H = a.w, a.h
            tl = diff(a, b, 0, 0, min(200, W // 3), min(200, H // 3))[0]
            pairs = list(zip(a.pixels(W - 320, H - 110, 300, 100), b.pixels(W - 320, H - 110, 300, 100)))
            marked = sum(1 for p, q in pairs if max(abs(p[k] - q[k]) for k in range(3)) > 0.1) / len(pairs)
            res = "bottom-right: %.1f%% of pixels changed by > 0.1; top-left mean diff %.4f" % (marked * 100, tl)
            if not (marked >= 0.03 and tl <= 0.003):
                fail(f"{f}: watermark missing or the picture changed elsewhere ({res})")
            note(f"ok  {f} {res}")

    for p in Path(".").glob("*.ppm"):
        p.unlink()


run(main)
