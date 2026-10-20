#!/usr/bin/env python3
"""场景：活动工牌按名单批量出图：姓名、职位、部门是文字变量，照片是像素替换变量，VIP 角标是可见性变量。

两种数据来源：CSV（输出名只能用序号）和 JSON 数据组（每组自带名字，输出按人名命名）。

要点：
 - 变量定义不随 PSD 保存，define、导入、导出必须放在同一条 run 里；PSD 重开后 variables 为空。
 - 像素替换要 clip:true 才裁在图层框里；默认 false 时 method:"fill" 会溢出画框盖住文字。
 - 相对图片路径按"已保存文档所在目录"解析；文档没存过就报错。这里全部写绝对路径（C:/… 形式）。

用法: python 16-data-driven-badges.py [名单.csv]     列：set,name,title,dept,vip,photo
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path

from pcx import *


def main(args):
    csv = pcx_input(args[0] if args else "", "", kind="file")
    if csv is None:
        csv = EX_DIR / "data" / "badges.csv"
    pcx_init("16-data-driven-badges")
    shutil.copy2(csv, "badges.csv")
    shutil.copy2(fixture("portrait.jpg"), "portrait.jpg")
    shutil.copy2(fixture("landscape.jpg"), "landscape.jpg")
    portrait = pcx_native(Path("portrait.jpg").resolve())
    landscape = pcx_native(Path("landscape.jpg").resolve())

    step("模板：1050x600 工牌，图层名就是变量要绑定的对象")
    pc_run([
        ("shape.create", {"kind": "rect", "rect": [0, 0, 1050, 120], "fill": "#0f766e", "name": "Header"}),
        ("type.create", {"x": 48, "y": 78, "text": "RIVERSIDE SUMMIT 2026", "size": 34, "color": "#ffffff"}),
        ("shape.create", {"kind": "rect", "rect": [48, 170, 300, 380], "fill": "#d1d5db", "name": "PHOTO"}),
        ("layer.rasterize.shape",),
        ("type.create", {"x": 400, "y": 270, "text": "Name", "size": 64, "color": "#111827", "name": "NAME"}),
        ("type.create", {"x": 400, "y": 340, "text": "Title", "size": 32, "color": "#374151", "name": "TITLE"}),
        ("type.create", {"x": 400, "y": 395, "text": "Dept", "size": 28, "color": "#0f766e", "name": "DEPT"}),
        ("shape.create", {"kind": "roundedRect", "rect": [860, 470, 150, 70], "radii": 35,
                          "fill": "#f59e0b", "name": "VIP"}),
        ("type.create", {"x": 935, "y": 516, "text": "VIP", "size": 30, "color": "#ffffff",
                         "align": "center", "name": "VIP label"}),
        ("layer.select", {"name": "VIP"}),
        ("layer.select", {"name": "VIP label", "mode": "add"}),
        ("layer.groupLayers", {"name": "VIP badge"}),
    ], new={"width": 1050, "height": 600, "background": "#ffffff", "name": "badge"},
        out="badge-template.psd", check=True)

    rows = pc_result(pc_run([("layer.list", {"flat": True})], input="badge-template.psd"),
                     "layer.list")["layers"]
    ids = {l["name"]: l["id"] for l in rows}
    defs = {"defs": [
        {"name": "name", "layer": ids["NAME"], "type": "textReplacement"},
        {"name": "title", "layer": ids["TITLE"], "type": "textReplacement"},
        {"name": "dept", "layer": ids["DEPT"], "type": "textReplacement"},
        {"name": "vip", "layer": ids["VIP badge"], "type": "visibility"},
        {"name": "photo", "layer": ids["PHOTO"], "type": "pixelReplacement", "method": "fill", "clip": True},
    ]}

    step("方式一：CSV 导入 → 每行一个数据组 → 导出（文件名用序号）")
    out = pc_run([("image.variables.define", defs),
                  ("file.import.variableDataSets", {"path": "badges.csv"}),
                  ("file.export.dataSetsAsFiles", {"dir": "badges-csv", "format": "png",
                                                   "naming": "badge-{index}"})], input="badge-template.psd", check=True)
    print("\n".join(pc_result(out, "file.export.dataSetsAsFiles")["files"]))

    step("方式二：JSON 数据组，名字取 CSV 首列，输出按人名命名")
    lines = Path("badges.csv").read_text(encoding="utf-8").strip().splitlines()
    head, *body = [line.split(",") for line in lines]
    kind = {"name": "text", "title": "text", "dept": "text", "vip": "visibility", "photo": "pixels"}
    photo = {"portrait.jpg": portrait, "landscape.jpg": landscape}
    data_sets = []
    for row in body:
        values = []
        for header, cell in zip(head[1:], row[1:]):
            value = cell
            if header == "vip":
                value = cell.strip().lower() == "true"
            elif header == "photo":
                # 只允许 CSV 里写内置图片的文件名并映射到本目录的绝对路径；
                # 其它值一律拒绝——像素替换在 serve/MCP 里会绕过读根目录，不能把任意路径传进去。
                if cell not in photo:
                    fail("badges.csv: photo %r is not one of the bundled images (%s)" % (cell, ", ".join(photo)))
                value = photo[cell]
            values.append({"variable": header, "kind": kind[header], "value": value})
        data_sets.append({"name": row[0], "values": values})
    sets = {"dataSets": data_sets}
    out = pc_run([("image.variables.define", defs),
                  ("image.variables.dataSets", sets),
                  ("file.export.dataSetsAsFiles", {"dir": "badges", "format": "jpg",
                                                   "naming": "{name}"})], input="badge-template.psd", check=True)
    print("\n".join(pc_result(out, "file.export.dataSetsAsFiles")["files"]))

    step("抽查：套用第一组数据后，文字、可见性和照片都落在框里")
    pc_run([("image.variables.define", defs), ("image.variables.dataSets", sets),
            ("image.applyDataSet", {"name": "li-na"})], input="badge-template.psd", out="check-li-na.psd", check=True)
    expect("check-li-na.psd", lambda k: next(l for l in k.layers if l.name == "NAME").text.text == "Li Na",
           "NAME = Li Na")
    expect("check-li-na.psd", lambda k: next(l for l in k.layers if l.name == "VIP badge").visible is False,
           "VIP badge hidden for li-na")
    expect_count("badges-csv", "badge-*.png", 3)
    expect_count("badges", "*.jpg", 3)
    expect_size("badges/li-na.jpg", 1050, 600)

    # 照片必须只出现在 PHOTO 框里：框外两侧（框左 40px、框右 40px 的条带）不能有照片的颜色
    pcx_ppm("badges/li-na.jpg", "badge.ppm")
    im = Img("badge.ppm")
    x, y, w, h = 48, 170, 300, 380
    bad = 0
    for strip in [(x - 40, y, 40, h), (x + w, y, 40, h), (x, y - 30, w, 30), (x, y + h, w, 30)]:
        x0, y0, x1, y1 = im.clip(*strip)
        for yy in range(y0, y1, 2):
            for xx in range(x0, x1, 2):
                r, g, b = im.px(xx, yy)[:3]
                bad += (max(r, g, b) - min(r, g, b)) > 0.08
    note(("ok  " if bad == 0 else "BAD ") + "%d photo-coloured pixels outside the PHOTO frame" % bad)
    Path("badge.ppm").unlink(missing_ok=True)
    if bad:
        fail("the photo spills outside the PHOTO layer bounds (clip:true missing?)")

    step("注意：CSV 首列是数据组名只在表头为空或叫 DataSet 时成立；本文件表头是 set，所以 CSV 方式得到的是序号名")
    note("missing 'DataSet' header -> sets become 'Data Set N'; the JSON route above names them by person")


run(main)
