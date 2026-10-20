#!/usr/bin/env python3
"""场景：收到一个结构混乱的 PSD（默认名、根层散落、空组、重名），要把它整理成可维护的规范稿，并证明渲染没变。

流程：记 SHA256 → 结构审计（原稿）→ 冻结渲染基线 → 另存规范稿 → 改名/建组/入组 → 结构审计（规范稿）→ 渲染比对。

要点：
 - 原稿只读：另存为 <稿名>_规范.psd，全程不碰原文件，结束重算哈希。
 - 两份证据缺一不可：psd_audit.py 读 PSD 文件查结构；psd_compare.py 比渲染（PSD 字节变了不代表画面变了）。
 - 命名与结构规则来自 profile（默认 zh 的页面_/区块_/组件_ + 元素前缀），项目有自己的规范时传 --profile。

用法: python 34-psd-normalize.py
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

from pcx import *

AUDIT = SCRIPTS_DIR / "psd_audit.py"
COMPARE = SCRIPTS_DIR / "psd_compare.py"


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def audit(path, *extra):
    proc = subprocess.run([sys.executable, str(AUDIT), "audit", str(path), "--json", *extra],
                          capture_output=True, text=True, encoding="utf-8")
    data = json.loads(proc.stdout) if proc.stdout.strip() else {}
    if proc.returncode >= 2 or data.get("error"):
        fail(f"psd_audit failed ({proc.returncode}): "
             f"{data.get('error') or proc.stderr.strip() or 'no output'}")
    return proc, data


def main(args):
    pcx_init("34-psd-normalize")

    step('造一份"乱"稿：默认名、根层散落、空组、同级重名')
    pc_run([("layer.new.group", {"name": "Group 1"}),
            ("layer.duplicate", {"name": "Layer 1"}),
            ("layer.duplicate", {"name": "Layer 1"}),
            ("shape.create", {"kind": "rect", "rect": [80, 80, 300, 160], "fill": "#93c5fd",
                              "name": "Rectangle 1"}),
            ("type.create", {"x": 120, "y": 400, "text": "Hero headline", "size": 40, "color": "#111827",
                             "name": "Type 1"}),
            ("layer.new.group", {"name": "Empty bits"})],
           new={"width": 800, "height": 600, "background": "#ffffff", "name": "messy"},
           out="messy.psd", check=True)
    orig_sha = sha256("messy.psd")
    note("original sha256: " + orig_sha)

    step("结构审计（原稿，只读）")
    proc, before = audit("messy.psd")
    counts = before.get("summary", {})
    note("before: " + " ".join("%s %s" % (k, v) for k, v in counts.items() if isinstance(v, int)))
    for issue in before.get("issues", [])[:8]:
        note("  %s %s %s" % (issue["severity"], issue["code"], issue.get("path", "")))
    if not before.get("issues"):
        fail("the messy draft produced no audit findings")

    step("冻结渲染基线")
    pc("convert", "messy.psd", "baseline.png")

    step("另存规范稿：背景转普通层、按 profile 改名、建页面/区块组、用 moveTo into 入组")
    pc_run([("layer.new.layerFromBackground",),
            ("layer.select", {"name": "Layer 0"}),
            ("layer.renameLayer", {"name": "背景_画布"}),
            ("layer.select", {"name": "Rectangle 1"}),
            ("layer.renameLayer", {"name": "形状_色块"}),
            ("layer.select", {"name": "Type 1"}),
            ("layer.renameLayer", {"name": "文字_标题"}),
            ("layer.new.group", {"name": "页面_首页"})],
           input="messy.psd", out="step1.psd", check=True)

    # 删掉空组、重复的默认组、多余的默认层：按 id 删（同名会歧义）
    layers = info("step1.psd").layers
    kill = [l.id for l in layers if l.name in ("Empty bits", "Group 1", "Layer 1")]
    for lid in kill:
        pc_run([("layer.delete", {"layer": lid})], input="step1.psd", out="step1.psd", check=True)

    # 把元素放进页面组；背景也放进去（契约允许背景在根，这里统一收进页面便于验收）
    by_name = {l.name: l.id for l in info("step1.psd").layers}
    kids = [by_name[n] for n in ("背景_画布", "形状_色块", "文字_标题") if n in by_name]
    pc_run([("layer.moveTo", {"layers": kids, "target": by_name["页面_首页"], "position": "into"})],
           input="step1.psd", out="normalized.psd", check=True)

    step("结构审计（规范稿，strict）")
    proc, after = audit("normalized.psd", "--strict")
    counts = after.get("summary", {})
    note("after: " + " ".join("%s %s" % (k, v) for k, v in counts.items() if isinstance(v, int)))
    for issue in after.get("issues", [])[:8]:
        note("  %s %s %s" % (issue["severity"], issue["code"], issue.get("path", "")))
    if after.get("summary", {}).get("strictOk") is not True:
        fail("normalized.psd still has CRITICAL/HIGH/MEDIUM issues; fix them before delivery")
    note("audit exit code: %d (0 = no CRITICAL/HIGH/MEDIUM)" % proc.returncode)

    step("渲染比对：结构重写后 PSD 字节必然不同，一致以渲染为准")
    pc("convert", "normalized.psd", "normalized.png")
    cmp = subprocess.run([sys.executable, str(COMPARE), "baseline.png", "normalized.png", "--out", "compare"],
                         capture_output=True, text=True, encoding="utf-8")
    print(cmp.stdout, end="")
    report = json.loads(cmp.stdout.strip().splitlines()[-1])
    if report.get("result") != "identical":
        fail(f"normalized.psd renders differently from the original ({report.get('result')})")
    note("ok  renders identical")

    step("原稿未变")
    if sha256("messy.psd") != orig_sha:
        fail("the original PSD changed")
    note("ok  messy.psd sha256 unchanged")


run(main)
