#!/usr/bin/env python3
"""场景：把"网页优化"这套操作沉淀下来反复用：在样图上录一次动作，导出 Photoshop 动作文件（.atn）给用 Photoshop 的同事，
再做成 Droplet（.pcdroplet）给自己批量处理。

要点：
 - .atn 只保留 Photoshop 有对应事件的步骤：Fit Image 这类脚本步骤在默认情况下会让 actions.save 报错，
   传 skipUnsupported:true 才会跳过并在 skipped 里列出来。
 - Droplet 保存的是 PhotoCraft 自己的步骤，一个不少；手写 droplet 要带 photocraftDroplet 键，用 createDroplet 生成最稳。
 - actions.get 的 steps 里含被 toggle 关掉的步骤，复用到批处理前要删掉（这里没有关掉的步骤）。

用法: python 26-actions-and-droplet.py [图片目录]
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path

from pcx import *


def main(args):
    photos_dir = pcx_input(args[0] if args else "", "", kind="dir")
    pcx_init("26-actions-and-droplet")
    Path("photos").mkdir()
    if user_mode():
        pcx_copy_dir(photos_dir, Path("photos"))
        if not any(Path("photos").iterdir()):
            fail(f"no files in {photos_dir}")
    else:
        for name in ("portrait.jpg", "landscape.jpg", "product.png"):
            shutil.copy2(fixture(name), Path("photos") / name)
    sample = sorted(p for p in Path("photos").iterdir() if p.is_file())[0]

    step("录制：actions.record → 实际操作一遍 → actions.stop；取出步骤并另存 .atn")
    out = pc_run([
        ("actions.record", {"name": "Web optimize"}),
        ("image.autoContrast",),
        ("file.automate.fitImage", {"width": 1200, "height": 1200, "dontEnlarge": True}),
        ("filter.sharpen.unsharpMask", {"amount": 70, "radius": 0.8, "threshold": 2}),
        ("edit.convertToProfile", {"profile": "srgb"}),
        ("actions.stop",),
        ("actions.get", {"action": "Web optimize"}),
        ("actions.save", {"path": "web-optimize.atn", "action": "Web optimize", "skipUnsupported": True}),
    ], input=str(sample), check=True)
    steps = pc_result(out, "actions.get")["steps"]
    print("\n".join("  %d: %s %s" % (i, s[0], json.dumps(s[1])) for i, s in enumerate(steps)))
    skipped = pc_result(out, "actions.save")["skipped"]
    note("skipped in .atn: " + (", ".join(s["id"] for s in skipped) or "none"))
    note("actions.stop reported %s steps (a count, not the list)" % pc_result(out, "actions.stop")["steps"])

    step("同事的 Photoshop 动作文件可以直接批处理")
    proc = pc("batch", "--actions", "web-optimize.atn", "--in", "photos", "--out", "web-atn",
              "--format", "jpg", "--quality", "85", capture=True)
    print(proc.stdout, end="")
    if proc.returncode != 0:
        fail(f"batch with the .atn failed\n{proc.stderr[-1200:]}")

    step("做 Droplet：步骤 + 输出格式打包成一个文件；之后命令行或拖放即可运行")
    pc_run([("file.automate.createDroplet", {"path": "web-optimize.pcdroplet", "name": "Web optimize",
                                              "steps": steps, "format": "jpg", "quality": 10})],
           new={"width": 1, "height": 1}, check=True)
    proc = pc("droplet", "web-optimize.pcdroplet", "photos", "--out", "web-droplet", capture=True)
    print(proc.stdout, end="")
    if proc.returncode != 0:
        fail(f"droplet failed\n{proc.stderr[-1200:]}")

    step("核对：两条路都出了全部文件；Droplet 保留了 Fit Image（长边 <= 1200），.atn 版没有")
    n = len([p for p in Path("photos").iterdir() if p.is_file()])
    expect_count("web-atn", "*.jpg", n)
    expect_count("web-droplet", "*", n)
    for f in sorted(Path("web-droplet").iterdir()):
        expect(f, lambda k: max(k.width, k.height) <= 1200, f"{f} fits 1200")
    maxside = max(max(info(f).width, info(f).height) for f in Path("web-atn").glob("*.jpg"))
    if maxside > 1200:
        note("largest .atn result: %dpx — Fit Image was skipped, as reported" % maxside)
    elif user_mode():
        note("user photos are already <= 1200px, so the skipped Fit Image cannot be observed here")
    else:
        fail(f"the .atn batch unexpectedly applied Fit Image (max side {maxside})")
    if Path("web-optimize.atn").read_bytes()[:4] != b"\x00\x00\x00\x10":
        fail("web-optimize.atn does not start with the Actions file version 16")
    note("ok  web-optimize.atn is a Photoshop Actions file (version 16)")


run(main)
