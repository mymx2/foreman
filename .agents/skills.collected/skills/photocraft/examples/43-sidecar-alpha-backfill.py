#!/usr/bin/env python3
"""场景：侧车 alpha 回灌 PhotoCraft——把进程外抠的图变成原生通道，并核对契约。

链路（都是已实测的原生命令）：
  sidecar/matte.py 出 cutout.png（RGB + straight alpha）+ manifest.json
  → file.new（透明画布）→ file.placeEmbedded{scale:100, fit:false}
  → select.loadSelection{channel:"transparency", layer}
  → select.saveSelection{name:"ALPHA_SUBJECT", channel:"new"}
  → 回读通道 / 导出分层

要点：
 - manifest 里的 engine 就是交付口径：降级跑出来的 alpha 不许写成神经网络结果。
 - 侧车是**可选**依赖：pymatting 装不上时 matte.py 自己降级，本案例照常通过（会打印 degraded）。
 - 回灌只搬 alpha，不重采样、不改画布：通道与画布必须同尺寸。

用法: python 43-sidecar-alpha-backfill.py [带主体的图]
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

from pcx import *

SIDECAR = SCRIPTS_DIR / "sidecar" / "matte.py"


def main(args):
    src = pcx_input(args[0] if args else "", "portrait.jpg", kind="file")
    if not SIDECAR.exists():
        skip("sidecar/matte.py 不存在")
    pcx_init("43-sidecar-alpha-backfill")
    shutil.copy2(src, "src.jpg")
    j = info("src.jpg")
    w, h = int(j.width), int(j.height)

    step("跑侧车：出 cutout.png + manifest.json")
    outdir = Path("matte")
    proc = subprocess.run([sys.executable, str(SIDECAR), "--src", str(Path("src.jpg").resolve()),
                           "--out", str(outdir.resolve())],
                          capture_output=True, text=True, encoding="utf-8", timeout=600)
    if proc.returncode != 0:
        print(proc.stderr[-1500:], file=sys.stderr)
        fail("sidecar matte.py failed")
    print(proc.stdout.strip())
    man = json.loads((outdir / "manifest.json").read_text(encoding="utf-8"))
    if man.get("schema") != "photocraft.sidecar/1":
        fail("manifest schema mismatch: %r" % man.get("schema"))
    note(f"engine={man['engine']} degraded={man['degraded']} alpha={man['alpha']}")
    if man["source"]["width"] != w or man["source"]["height"] != h:
        fail("manifest source size does not match the input")
    cut = outdir / "cutout.png"
    if not cut.exists():
        fail("cutout.png missing")

    step("回灌：透明画布 → 嵌入 cutout → 取透明度选区 → 存成 ALPHA_SUBJECT 通道")
    cmds = [
        ("file.placeEmbedded", {"path": pcx_native(cut.resolve()), "scale": 100, "fit": False,
                                "smartObject": False}),
        ("document.inspect",),
    ]
    r1 = pc_run(cmds, new={"width": w, "height": h, "background": "transparent",
                           "name": "backfill"}, out="backfill.psd", check=True)
    insp = pc_result(r1, "document.inspect")
    placed = insp.layers[0]
    note(f"placed layer id={placed.id} name={placed.name}")

    r2 = pc_run([
        ("select.loadSelection", {"channel": "transparency", "layer": {"name": placed.name}}),
        ("select.saveSelection", {"name": "ALPHA_SUBJECT", "channel": "new"}),
        ("select.deselect",),
        ("document.inspect",),
    ], input="backfill.psd", out="channel.psd", check=True)
    insp2 = pc_result(r2, "document.inspect")
    alpha_channels = [c.get("name") if isinstance(c, dict) else c for c in (insp2.channels or {}).get("alpha", [])]
    note("alpha channels: " + ", ".join(str(c) for c in alpha_channels))

    step("验收：通道存在且能被按名回读")
    if alpha_channels and "ALPHA_SUBJECT" not in alpha_channels:
        fail(f"ALPHA_SUBJECT not in channels: {alpha_channels}")
    if not alpha_channels:
        # inspect 没暴露 alpha 通道时，用"按名 loadSelection 成功"作为存在性证据
        r3 = pc_run([("select.loadSelection", {"channel": "ALPHA_SUBJECT"}), ("select.deselect",)],
                    input="channel.psd", out="probe.psd")
        if r3.returncode != 0:
            fail("cannot load the saved channel by name")
        note("ok  通道可按名回读（inspect 未列 alpha 通道）")
    else:
        note("ok  通道已建立并出现在 inspect 里")

    step("导出分层并核对画布尺寸")
    d = Path("layers")
    d.mkdir(exist_ok=True)
    pc("run", "channel.psd", "--cmd", "file.export.layersToFiles",
       "--params", json.dumps({"dir": str(d.resolve()), "format": "png", "prefix": "A"}),
       "--out", "exported.psd", capture=True)
    alphas = sorted(d.glob("A*.png"))
    if not alphas:
        fail("no layer exported")
    pc("convert", str(alphas[0]), "layer0.ppm")
    im = Img("layer0.ppm")
    if im.w != w or im.h != h:
        fail(f"exported layer is {im.w}x{im.h}, expected {w}x{h}")
    note(f"ok  导出 {len(alphas)} 个分层，尺寸 {im.w}x{im.h} 与画布一致")
    if im.c == 4:
        box = im.alpha_bbox()
        if not box:
            fail("exported layer has no opaque pixels")
        note(f"ok  alpha bbox={box}")
    note("done: channel.psd / matte/manifest.json / layers/*.png")


run(main)
