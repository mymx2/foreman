#!/usr/bin/env python3
"""场景：要做的事不知道对应哪个命令、参数怎么写。先查已安装版本的命令注册表，再动手。

用法: python 02-find-command-params.py
"""
from __future__ import annotations

import json
import shutil

from pcx import *


def main(args):
    pcx_init("02-find-command-params")
    shutil.copy2(fixture("landscape.jpg"), "in.jpg")
    w0 = info("in.jpg").width

    step("按关键字找命令：匹配 id、菜单标签和别名")
    pc("commands", "--filter", "curves")

    step("取参数文档：--json 的 params 字段（a..b 范围，=x 默认值，? 可选）")
    proc = pc("commands", "--json", "--filter", "image.crop", capture=True)
    for c in json.loads(proc.stdout):
        print(c["id"], "\n    ", c["params"])

    step("按 id 前缀列出一组命令及菜单位置（技能的 <skill-dir>/scripts/params.py 做同样的查询）")
    proc = pc("commands", "--json", capture=True)
    for c in json.loads(proc.stdout):
        if c["id"].startswith("filter.sharpen"):
            print("%s  [%s]  %s\n    %s" % (c["id"], " > ".join(c.get("menu") or []), c["label"], c["params"]))

    step("规模与可用性：不打开文档就能运行的命令（needsDocument=false）")
    reg = json.loads(proc.stdout)
    print("%d commands, %d usable without an open document" % (len(reg), sum(1 for c in reg if not c["needsDocument"])))

    step("参数拼错时：滤镜会报错退出……")
    misspelt = pc("run", "in.jpg", "--cmd", "filter.blur.gaussianBlur", "--params", '{"radiuss":4}',
                  "--out", "typo.png", capture=True)
    expect_error(misspelt, "unknown parameter", "misspelled key is rejected")

    step("……但很多命令会静默忽略未知键，按默认值执行：必须核对返回值")
    out = pc_run([("image.imageSize", {"widht": 600})], input="in.jpg")
    w = pc_result(out, "image.imageSize")["width"]
    note(f'image.imageSize {{"widht":600}} -> width={w} (unchanged)')
    if w != w0:
        fail("expected the typo to be ignored")

    out = pc_run([("image.imageSize", {"width": 600})], input="in.jpg")
    w = pc_result(out, "image.imageSize")["width"]
    note(f'image.imageSize {{"width":600}}  -> width={w}')
    if w != 600:
        fail("resize did not apply")

    step("当前状态不可用的命令直接报错并中止整条 run（例如给没有蒙版的层应用蒙版）")
    # 注意：0.18 起 CLI run 里无选区的 select.deselect 静默通过、退出码 0，不能再用它演示报错；
    # 同一个调用走 serve 的 engine.execute 仍报 no selection。
    apply_mask = pc("run", "in.jpg", "--cmd", "layer.layerMask.apply", capture=True)
    expect_error(apply_mask, "layer mask", "layer.layerMask.apply without a mask fails")


run(main)
