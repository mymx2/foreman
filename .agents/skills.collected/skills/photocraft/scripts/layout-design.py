#!/usr/bin/env python3
"""layout-design.py — 按栅格计算 PSD 布局坐标，并对实际 bounds 做合规验收。

两个子命令：

  calc   按 spec 算列网格坐标，输出每层应移动到的目标位置（不碰文档）
  check  把 doc.inspect 的层树按 spec 验收：是否对齐栅格、间距是否合规、
         命名与层级是否合格。退出码 0 = 通过，1 = 有问题。

不连接 PhotoCraft、不修改任何文档。移动坐标请交给 layer.translate
（见 SKILL.md「自动布局模式」）。

用法：
  python layout-design.py calc --width 1200 --margin 80 --gutter 24 --columns 12
  python layout-design.py check --spec spec.json --inspect inspect.json
  python layout-design.py check --spec spec.json --inspect inspect.json --json
"""
import argparse
import json
import math
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import psd_contract  # noqa: E402  契约常量单点定义
from psd_contract import NODE_ROOT_PREFIXES, hidden_allowed  # noqa: E402

SPACING_SCALE = [4, 8, 12, 16, 24, 32, 40, 48, 64]

DEFAULT_NAMES = {
    "图层 1", "图层 2", "组 1", "组 2", "文本 1", "未命名",
    "layer 1", "layer 2", "group 1", "group 2", "copy",
}
BAD_SUFFIX = ("副本", "拷贝", "copy")

# 严重度：CRITICAL/HIGH 视为失败，MEDIUM 应修，LOW 建议。
SEVERITY_FAIL = {"CRITICAL", "HIGH"}


def integer_column_width(width, margin, gutter, columns):
    """列宽取使**步距 (colW + gutter) 为 8 的倍数**的最大值，余数留给右侧。

    真正的约束是步距，不是列宽本身：列起点是 margin + 步距*i，只有步距合规，
    所有列起点才会落在 8pt 上。

    - gutter 是 8 的倍数时，列宽取 8 的倍数即可（1440/120/24/12：78→72，步距 96）
    - gutter 不是 8 的倍数时，列宽要反过来补偿（1200/80/20/12：取 68 让步距 88，
      比只取 8 倍数的 64 更贴画布；gutter=20 时列宽 64 的步距 84 不合规）

    当 gutter 本身不是 8 的倍数且无法补偿时（如 gutter=1），步距不可能合规，
    此时仍返回可容纳的最大列宽，由调用方读 pitch 判断。
    """
    inner = width - margin * 2
    avail = inner - gutter * (columns - 1)
    unit = 8
    if avail < columns:
        raise SystemExit(f"画布太窄：{width}px 放不下 {columns} 列")
    best = None
    for c in range(avail, 0, -1):
        if c * columns > avail:
            continue
        if (c + gutter) % unit == 0:
            best = c
            break
    if best is None:  # 步距无法合规，退化为可容纳的最大列宽
        best = avail // columns
    remainder = avail - best * columns
    return int(best), int(remainder)


def column_x(margin, col_w, gutter, i):
    return margin + (col_w + gutter) * i


def is_scale_value(v, scale=None):
    """列起点/间距/坐标的刻度判定：8pt 的倍数即合法。

    不能用 SPACING_SCALE 枚举判定——240、104、80、168 都是 8 的倍数，
    是合法值，但不在 4/8/12/16/24/32/40/48/64 这张推荐取值表里。
    """
    scale = scale or SPACING_SCALE
    unit = min(s for s in scale if s > 0)
    return v % unit == 0


def snap_to_scale(v, scale=None):
    scale = scale or SPACING_SCALE
    unit = min(s for s in scale if s > 0)
    return int(round(v / unit) * unit)


def cmd_calc(a):
    col_w, rem = integer_column_width(a.width, a.margin, a.gutter, a.columns)
    xs = [column_x(a.margin, col_w, a.gutter, i) for i in range(a.columns)]
    out = {
        "canvasWidth": a.width,
        "margin": a.margin,
        "gutter": a.gutter,
        "columns": a.columns,
        "columnWidth": col_w,
        "pitch": col_w + a.gutter,
        "gutterOnScale": a.gutter % 8 == 0,
        "remainderRight": rem,
        "exactColumnWidth": (a.width - a.margin * 2 - a.gutter * (a.columns - 1)) / a.columns,
        "columnX": xs,
        "legalColumnSpans": {str(n): col_w * n + a.gutter * (n - 1) for n in range(1, a.columns + 1)},
        "pitchOn8pt": (col_w + a.gutter) % 8 == 0,
        "allOn8pt": all(x % 8 == 0 for x in xs),
        "contentRight": xs[-1] + col_w,
    }
    if a.json:
        print(json.dumps(out, ensure_ascii=False, indent=2))
        return 0
    print(f"画布 {a.width}px | margin {a.margin} | gutter {a.gutter} | {a.columns} 列")
    print(f"列宽(精确) {out['exactColumnWidth']:.2f} -> 8pt列宽 {col_w}px，右侧余 {rem}px")
    print(f"步距(colW+gutter) = {out['pitch']} {'(8的倍数,列起点合规)' if out['pitchOn8pt'] else '(不是8的倍数)'}")
    print(f"列起点 {xs}")
    print(f"全部落在 8pt 上: {'是' if out['allOn8pt'] else '否'}")
    spans = out["legalColumnSpans"]
    print("合法跨列宽度: " + ", ".join(f"{n}列={w}" for n, w in spans.items()))
    print("  （元素宽度只能取这些值，否则右边界越出列线）")
    if not out["pitchOn8pt"]:
        print(f"警告: 步距 {out['pitch']} 不是 8 的倍数，列起点会参差不齐；"
              f"把 gutter 改成 8 的倍数（如 16/24）即可修复")
    print(f"内容区 {a.margin} .. {out['contentRight']}")
    return 0


def walk(layers, depth=0, path="", parent=""):
    for l in layers or []:
        name = l.get("name", "")
        full = path + "/" + name if path else name
        yield {
            "name": name,
            "id": l.get("id"),
            "bounds": l.get("bounds"),
            "depth": depth,
            "path": full,
            "parent": parent,
            "kind": l.get("kind"),
            "visible": l.get("visible", True),
            "children": l.get("children") or [],
        }
        yield from walk(l.get("children") or [], depth + 1, full, full)


def check_names(nodes, issues):
    """命名检查。

    与 psd-audit.py 共用同一套严重度口径（默认名 HIGH、副本名 MEDIUM、
    根组命名不合规 MEDIUM），避免两个脚本对同一问题给出相反结论。
    """
    seen = {}
    for n in nodes:
        name = n["name"]
        if not name or name.strip() != name:
            issues.append(("HIGH", f"层名空或首尾有空格: {n['path']}"))
            continue
        if name in DEFAULT_NAMES:
            issues.append(("HIGH", f"默认层名未改: {n['path']}"))
        if name.lower().endswith(BAD_SUFFIX):
            issues.append(("MEDIUM", f"层名带副本后缀: {n['path']}"))
        # 重名按 (父级, 名字) 判定：PSD 允许不同组下的同名层
        key = (n["parent"], name.strip().casefold())
        if key in seen:
            issues.append(("HIGH", f"同级重名: {name}（父级 {n['parent'] or '根'}）"))
        seen.setdefault(key, n["path"])
        if not re.fullmatch(r"[A-Za-z0-9_\u4e00-\u9fff ]+", name):
            issues.append(("MEDIUM", f"层名含特殊符号（交付引擎会失败）: {n['path']}"))


def _ancestors(parent_path):
    return [p for p in (parent_path or "").split("/") if p]


def check_structure(nodes, roots, issues):
    if not roots:
        issues.append(("CRITICAL", "文档没有图层"))
        return
    for r in roots:
        name = r.get("name") or ""
        if (r.get("children") or []) == [] and r.get("kind") != "Group":
            issues.append(("HIGH", f"根层散落（未进组）: {name}"))
        # 节点树契约：根组必须以 页面_/区块_/参考_/版本_ 开头
        if r.get("kind") == "Group" and not name.startswith(NODE_ROOT_PREFIXES):
            issues.append(("MEDIUM", f"根组命名不合规（应以 页面_/区块_/参考_/版本_ 开头）: {name}"))
    for n in nodes:
        # 空组：组节点没有任何子层。规范要求清理，与 psd-audit.py 同判 HIGH
        if n["kind"] == "Group" and not n["children"]:
            issues.append(("HIGH", f"空组: {n['path']}"))
        # 隐藏层只允许在 参考_* 组或 版本_* 包装下（与 psd-audit.hidden_allowed 同语义，
        # 按祖先链判定而非路径前缀，否则页面包装下的 参考_ 组会被误报）
        if not n["visible"] and not hidden_allowed(_ancestors(n["parent"]), n["name"]):
            issues.append(("MEDIUM", f"隐藏层不在参考/版本组下: {n['path']}"))
        # 节点树边界：子层前缀必须符合父组允许的子前缀（见 psd_contract.ALLOW_NESTED）
        if n["parent"] and not psd_contract.child_prefix_ok(n["parent"].split("/")[-1], n["name"]):
            issues.append(("MEDIUM", f"层级不符：{n['name']} 不应出现在 {n['parent'].split('/')[-1]} 下"))
    # 视觉层序：同组内 背景_* 元素必须在最底层（doc.inspect 自上而下，故在末尾）。
    # 这里不区分类型：背景压在文字上也是层序错误，与 psd-audit 的覆盖面一致。
    siblings = {}
    for n in nodes:
        if n["name"] == "":
            continue
        siblings.setdefault(n["parent"], []).append(n)
    for parent, group in siblings.items():
        names = [x["name"] for x in group]
        bg_idx = [i for i, nm in enumerate(names) if nm.startswith("背景_")]
        if bg_idx and max(bg_idx) != len(names) - 1:
            issues.append((
                "MEDIUM",
                f"背景层不在最底层（组 {parent or '根'}）: {names}（背景_ 应在末尾）",
            ))


def check_layout(nodes, spec, issues):
    """几何验收：x/y 是否落在栅格列上，间距是否在刻度内。"""
    if not spec:
        return
    margin = spec.get("margin", 0)
    gutter = spec.get("gutter", 0)
    columns = spec.get("columns", 0)
    width = spec.get("width")
    if not (columns and width):
        return
    col_w, _ = integer_column_width(width, margin, gutter, columns)
    xs = [column_x(margin, col_w, gutter, i) for i in range(columns)]
    valid_x = set(xs)
    # 合法跨列宽度：跨 n 列占 n*colW + (n-1)*gutter。宽度不在此列 = 右边界必然越线
    legal_w = {col_w * n + gutter * (n - 1): n for n in range(1, columns + 1)}
    valid_right = {x + col_w for x in xs}
    scale = spec.get("spacingScale", SPACING_SCALE)
    doc_h = spec.get("height") or 0
    placed = []
    for n in nodes:
        b = n["bounds"]
        if not b or len(b) < 4:
            continue
        # 铺满画布的底图层不参与栅格判定：它的职责是铺底，不是对齐列
        if b[0] == 0 and b[1] == 0 and b[2] >= width and (not doc_h or b[3] >= doc_h):
            continue
        placed.append(n)
    for n in placed:
        x, y, w = n["bounds"][0], n["bounds"][1], n["bounds"][2]
        if x not in valid_x:
            near = snap_to_scale(min(valid_x, key=lambda v: abs(v - x)) if valid_x else x)
            issues.append(("MEDIUM", f"x={x} 不在栅格列上（最近列 {near}）: {n['name']}"))
        # 文字层按内容定宽，不参与跨列宽度判定；但起点仍要对齐列
        if n["kind"] != "Type":
            if w not in legal_w:
                best = min(legal_w, key=lambda v: abs(v - w))
                issues.append((
                    "MEDIUM",
                    f"宽 {w} 不是合法跨列宽度（跨 {legal_w[best]} 列应为 {best}）: {n['name']}",
                ))
            elif x in valid_x and (x + w) not in valid_right:
                issues.append(("MEDIUM", f"右边界 {x + w} 未落在列边界上: {n['name']}"))
        if not is_scale_value(y, scale):
            issues.append(("LOW", f"y={y} 不在间距刻度上（最近 {snap_to_scale(y, scale)}）: {n['name']}"))
    # 间距只在同父级兄弟之间衡量，跨组相邻没有排版意义
    gaps = []
    for a, b in zip(placed, placed[1:]):
        if a["parent"] != b["parent"]:
            continue
        gaps.append(abs(b["bounds"][0] - (a["bounds"][0] + a["bounds"][2])))
    for g in gaps:
        if g and not is_scale_value(g, scale):
            issues.append(("LOW", f"相邻间距 {g}px 不在刻度上（最近 {snap_to_scale(g, scale)}）"))
    # 越界与重叠：x/w/y 都对也可能整体跑出画布，或元素互相压住
    for n in placed:
        x, y, w, h = n["bounds"][0], n["bounds"][1], n["bounds"][2], n["bounds"][3]
        if x < 0 or y < 0:
            issues.append(("HIGH", f"坐标为负 ({x},{y}): {n['name']}"))
        if x + w > width:
            issues.append(("HIGH", f"水平越界：右边界 {x + w} > 画布宽 {width}: {n['name']}"))
        if doc_h and y + h > doc_h:
            issues.append(("HIGH", f"垂直越界：下边界 {y + h} > 画布高 {doc_h}: {n['name']}"))
    siblings = {}
    for n in placed:
        # Type 与 Group 不参与重叠判定：文字按内容定框，组 bounds 是子层并集
        if n["kind"] in ("Type", "Group"):
            continue
        siblings.setdefault(n["parent"], []).append(n)
    for parent, group in siblings.items():
        for i in range(len(group)):
            for j in range(i + 1, len(group)):
                ax, ay, aw, ah = group[i]["bounds"][:4]
                bx, by, bw, bh = group[j]["bounds"][:4]
                if ax + aw <= bx or bx + bw <= ax or ay + ah <= by or by + bh <= ay:
                    continue
                issues.append((
                    "HIGH",
                    f"同级重叠: {group[i]['name']} 与 {group[j]['name']}（父级 {parent or '根'}）",
                ))


def cmd_check(a):
    spec = json.load(open(a.spec, encoding="utf-8")) if a.spec else {}
    data = json.load(open(a.inspect, encoding="utf-8"))
    if isinstance(data, list):
        data = data[0] if data else {}
    roots = data.get("layers") or []
    nodes = list(walk(roots))
    issues = []
    check_structure(nodes, roots, issues)
    check_names(nodes, issues)
    check_layout(nodes, spec, issues)

    counts = {}
    for sev, _ in issues:
        counts[sev] = counts.get(sev, 0) + 1
    # 与 psd-audit.py 同口径：默认只把 CRITICAL/HIGH 当失败，--strict 时 MEDIUM 也算
    fail_sev = set(SEVERITY_FAIL)
    if a.strict:
        fail_sev.add("MEDIUM")
    failed = [i for i in issues if i[0] in fail_sev]
    result = {
        "result": "pass" if not failed else "fail",
        "layerCount": len(nodes),
        "rootCount": len(roots),
        "issueCounts": counts,
        "issues": [{"severity": s, "message": m} for s, m in issues],
    }
    if a.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"结果: {result['result']} | 层数 {len(nodes)} | 根组 {len(roots)}")
        print(f"问题统计: {counts or '无'}")
        for s, m in issues:
            print(f"  [{s}] {m}")
    return 1 if failed else 0


def main():
    p = argparse.ArgumentParser(description="PSD 栅格布局计算与合规验收")
    sub = p.add_subparsers(dest="cmd", required=True)

    c = sub.add_parser("calc", help="按 spec 计算列网格坐标")
    c.add_argument("--width", type=int, required=True)
    c.add_argument("--margin", type=int, default=80)
    c.add_argument("--gutter", type=int, default=24)
    c.add_argument("--columns", type=int, default=12)
    c.add_argument("--json", action="store_true")
    c.set_defaults(fn=cmd_calc)

    k = sub.add_parser("check", help="验收层树是否符合规范")
    k.add_argument("--spec", help="spec.json（含 width/margin/gutter/columns）")
    k.add_argument("--inspect", required=True, help="doc.inspect 输出的 JSON")
    k.add_argument("--strict", action="store_true", help="MEDIUM 也算失败（与 psd-audit.py 同口径）")
    k.add_argument("--json", action="store_true")
    k.set_defaults(fn=cmd_check)

    a = p.parse_args()
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, OSError):
            pass
    sys.exit(a.fn(a))


if __name__ == "__main__":
    main()
