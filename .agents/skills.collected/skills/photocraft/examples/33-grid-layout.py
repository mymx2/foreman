#!/usr/bin/env python3
"""场景：按 12 列栅格排一版落地页局部：算列宽 → 铺参考线 → 按列宽和列起点摆放卡片 → 用 check 验收。

要点：
 - 列宽不要手推：layout_design.py calc 会让步距（列宽+gutter）成为 8 的倍数，并给出合法跨列宽度。
 - view.newGuideLayout 的 width 是单列宽，不是画布宽；参考线不出现在 doc.inspect 和 doc.render 里。
 - 元素宽度只能取"跨 n 列"的值：colW*n + gutter*(n-1)，否则右边界越出列线。
 - 新建的图层在活动层上方；要让卡片进区块组，用 layer.moveTo {position:"into"} 或先选中再 groupLayers。

用法: python 33-grid-layout.py
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from pcx import *

W, H, MARGIN, GUTTER, COLUMNS = 1200, 900, 80, 24, 12
LAYOUT = SCRIPTS_DIR / "layout_design.py"


def main(args):
    pcx_init("33-grid-layout")

    step(f"算栅格：{W}×{H}，margin {MARGIN}，gutter {GUTTER}，{COLUMNS} 列")
    calc = subprocess.run([sys.executable, str(LAYOUT), "calc", "--width", str(W), "--margin", str(MARGIN),
                           "--gutter", str(GUTTER), "--columns", str(COLUMNS), "--json"],
                          capture_output=True, text=True, encoding="utf-8", check=True)
    grid = json.loads(calc.stdout)
    note("column width %d, pitch %d, columns at %s" % (grid["columnWidth"], grid["pitch"], grid["columnX"][:4]))
    note("legal widths: " + ", ".join(f"{n}:{w}" for n, w in
                                      sorted(grid["legalColumnSpans"].items(), key=lambda kv: int(kv[0]))))
    if grid["pitch"] % 8 != 0:
        fail("pitch is not a multiple of 8")
    cw, col0 = grid["columnWidth"], grid["columnX"][0]
    span3, span4 = grid["legalColumnSpans"]["3"], grid["legalColumnSpans"]["4"]

    step("铺参考线并建区块组")
    out = pc_run([("view.newGuideLayout", {"columns": COLUMNS, "width": cw, "gutter": GUTTER,
                                           "margin": MARGIN, "clearExisting": True}),
                  ("layer.new.layerFromBackground",),
                  ("layer.renameLayer", {"name": "背景_画布"}),
                  ("layer.new.group", {"name": "区块_首屏"})],
                 new={"width": W, "height": H, "background": "#ffffff", "name": "grid"},
                 out="layout.psd", check=True)
    r = pc_result(out, "view.newGuideLayout")
    print("guides: %d horizontal, %d vertical" % (r["horizontal"], r["vertical"]))

    step("按列摆放：一张 4 列宽的卡片（列 1-4）、一张 3 列宽的卡片（列 6-8），各带一条 4pt 刻度上的说明文字")
    a_x, b_x = col0, grid["columnX"][5]
    pc_run([
        ("shape.create", {"kind": "roundedRect", "rect": [a_x, 240, span4, 320], "radii": 16,
                          "fill": "#e0e7ff", "name": "组件_卡片A"}),
        ("shape.create", {"kind": "roundedRect", "rect": [b_x, 240, span3, 320], "radii": 16,
                          "fill": "#fee2e2", "name": "组件_卡片B"}),
        ("type.create", {"x": a_x, "y": 600, "text": "Left card", "size": 24, "color": "#1e293b",
                         "name": "文字_说明A"}),
    ], input="layout.psd", out="cards.psd", check=True)

    step("把内容层放进区块组（一次 moveTo 传 layers 数组），再导出 inspect 给 check 用")
    layers = {l.name: l.id for l in info("cards.psd").layers}
    move = {"layers": [layers[n] for n in ("背景_画布", "组件_卡片A", "组件_卡片B", "文字_说明A")],
            "target": layers["区块_首屏"], "position": "into"}
    pc_run([("layer.moveTo", move)], input="cards.psd", out="grouped.psd", check=True)

    step("验收：layout_design.py check（命名 + 栅格几何）")
    Path("spec.json").write_text(json.dumps({"width": W, "height": H, "margin": MARGIN,
                                             "gutter": GUTTER, "columns": COLUMNS}), encoding="utf-8")
    pc("info", "grouped.psd", "--compact", capture=True)
    proc = pc("info", "grouped.psd", "--compact", capture=True)
    Path("inspect.json").write_text(proc.stdout, encoding="utf-8")
    check = subprocess.run([sys.executable, str(LAYOUT), "check", "--spec", "spec.json",
                            "--inspect", "inspect.json", "--json"],
                           capture_output=True, text=True, encoding="utf-8")
    Path("check.json").write_text(check.stdout or "{}", encoding="utf-8")
    print((check.stdout or "")[:2000])
    if check.returncode not in (0, 1):
        print(check.stderr, file=sys.stderr)
        fail("check could not read the inputs")
    result = json.loads(check.stdout or "{}")
    counts = result.get("issueCounts") or {}
    if sum(counts.values()):
        fail(f"layout check reports issues: {counts}")
    note("ok  no CRITICAL/HIGH/MEDIUM/LOW issues")
    expect_size("grouped.psd", W, H)

    step("对照：手推列宽（向下取整到 78）会让列起点参差不齐")
    naive = subprocess.run([sys.executable, str(LAYOUT), "calc", "--width", "1440", "--margin", "120",
                            "--gutter", "24", "--columns", "12", "--snap", "none", "--json"],
                           capture_output=True, text=True, encoding="utf-8", check=True)
    g = json.loads(naive.stdout)
    note("naive column width %d, pitch %d (pitch %% 8 = %d)" % (g["columnWidth"], g["pitch"], g["pitch"] % 8))
    if g["pitch"] % 8 == 0:
        fail("the naive layout unexpectedly landed on an 8pt pitch")
    note("ok  the naive width breaks the 8pt pitch, which is why calc compensates")


run(main)
