#!/usr/bin/env python3
"""layout_design.py — 栅格计算（calc）与层树/几何验收（check），不连 PhotoCraft、不改文档。

用法:
  python <skill-dir>/scripts/layout_design.py calc --width W [--margin 80] [--gutter 24] [--columns 12]
         [--snap pitch8|none | --column-width N] [--json]
  python <skill-dir>/scripts/layout_design.py check --inspect INSPECT.json (--spec SPEC.json | --no-geometry)
         [--profile zh|en|FILE.json] [--strict] [--json]

calc  列宽默认取"使步距 (列宽+gutter) 为 8 的倍数"的最大整数，余数留在右侧——这是本工具的默认取向，
      不是通用规则（内容区会偏左）。--snap none 用精确列宽向下取整；--column-width N 用你给的列宽。
      输出列起点、合法跨列宽度和可直接传给 view.newGuideLayout 的参数（width = 单列宽）。

check 输入直接用 photocraft-cli info --compact 的输出；也接受 run --cmd document.inspect 的输出行、
      serve doc.inspect / engine.execute 的回复（自动取 result）。
      --spec 必填（或显式 --no-geometry 只查命名与结构）。spec.json 字段:
        width height margin gutter columns   必填整数，width/height 必须与 inspect 画布一致
        columnWidth                          可选：固定列宽（等同 calc --column-width）
        snap                                 可选："pitch8"（默认）或 "none"
        spacingScale                         可选：间距刻度，最小值为判定单位（默认 4）
        gridRoles                            可选：查落列的角色，默认 ["section","component"]
        gridLayers                           可选：额外要查落列的层名或路径
      几何规则:
        - 只查 gridRoles 里的组（取可见子层并集）和 gridLayers 指定的层；组件内的内缩元素默认不查。
        - 贴画布左/右/上边的边不查（通栏、出血）。
        - 文字层 bounds 是字形墨迹框，比文本框/锚点偏右一个侧距：x 落在某列起点的
          [-0.05, +0.15] × 字号(px) 区间内就算对齐（字号取 text.sizePt × 分辨率/72）；
          由文字决定的右边和上边不查。
        - inspect 的 bounds 已裁到画布内，不会为负；整层出界或空层显示为宽/高 0，报 ZERO_SIZE。
        - 同级、同角色（图片/图标/形状/组件/区块）的元素重叠报 SAME_KIND_OVERLAP；
          背景、效果、参考、文字不参与。
      命名与结构规则与 psd_audit.py 相同（共用 psd_contract.py）。
      退出码: 0 = 无 CRITICAL/HIGH（--strict 时 MEDIUM 也算失败）；1 = 有；2 = 输入或 spec 错误。
"""
import argparse
import json
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import psd_contract  # noqa: E402

DEFAULT_SCALE = [4, 8, 12, 16, 24, 32, 40, 48, 64]
DEFAULT_GRID_ROLES = ["section", "component"]
OVERLAP_ROLES = ("image", "icon", "shape", "component", "section")
SPEC_KEYS = {"width", "height", "margin", "gutter", "columns", "columnWidth", "snap",
             "spacingScale", "gridRoles", "gridLayers"}
_KIND = {"Group": "group", "Type": "type", "Pixel": "pixel", "Shape": "shape",
         "Smart Object": "smartobject", "Adjustment": "adjustment", "Fill": "fill"}


class InputError(Exception):
    pass


# ---------------------------------------------------------------- grid math

def column_width(width, margin, gutter, columns, snap="pitch8", explicit=None):
    """Return (column width, remainder on the right)."""
    avail = width - margin * 2 - gutter * (columns - 1)
    if avail < columns:
        raise InputError(f"画布太窄：{width}px 放不下 {columns} 列（margin {margin}, gutter {gutter}）")
    if explicit is not None:
        if explicit < 1 or explicit * columns > avail:
            raise InputError(f"列宽 {explicit} 放不下：{columns} 列最多 {avail // columns}px")
        best = explicit
    elif snap == "none":
        best = avail // columns
    else:
        best = next((c for c in range(avail // columns, 0, -1) if (c + gutter) % 8 == 0),
                    avail // columns)
    return best, avail - best * columns


class Grid:
    def __init__(self, width, margin, gutter, columns, snap="pitch8", explicit=None):
        self.width, self.margin, self.gutter, self.columns = width, margin, gutter, columns
        self.snap = "explicit" if explicit is not None else snap
        self.col_w, self.remainder = column_width(width, margin, gutter, columns, snap, explicit)
        self.pitch = self.col_w + gutter
        self.xs = [margin + self.pitch * i for i in range(columns)]
        self.rights = [x + self.col_w for x in self.xs]
        self.spans = {n: self.col_w * n + gutter * (n - 1) for n in range(1, columns + 1)}

    def nearest(self, values, v):
        return min(values, key=lambda c: abs(c - v))


def cmd_calc(args):
    if args.columns < 1 or args.width <= 0 or args.margin < 0 or args.gutter < 0:
        raise InputError("--columns >= 1，--width > 0，--margin/--gutter 不能为负")
    g = Grid(args.width, args.margin, args.gutter, args.columns, args.snap, args.column_width)
    out = {
        "canvasWidth": g.width, "margin": g.margin, "gutter": g.gutter, "columns": g.columns,
        "snap": g.snap,
        "exactColumnWidth": (g.width - g.margin * 2 - g.gutter * (g.columns - 1)) / g.columns,
        "columnWidth": g.col_w, "pitch": g.pitch, "remainderRight": g.remainder,
        "columnX": g.xs, "contentRight": g.rights[-1],
        "legalColumnSpans": {str(n): w for n, w in g.spans.items()},
        "pitchOn8pt": g.pitch % 8 == 0, "gutterOnScale": g.gutter % 8 == 0,
        "allOn8pt": all(x % 8 == 0 for x in g.xs),
        "guideLayoutParams": {"columns": g.columns, "width": g.col_w, "gutter": g.gutter,
                              "margin": g.margin},
    }
    if args.json:
        print(json.dumps(out, ensure_ascii=False, indent=2))
        return 0
    rule = {"pitch8": "步距取 8 的倍数（本工具默认）", "none": "精确列宽向下取整（--snap none）",
            "explicit": "按 --column-width"}[g.snap]
    print(f"画布 {g.width}px | margin {g.margin} | gutter {g.gutter} | {g.columns} 列 | 列宽规则: {rule}")
    print(f"列宽(精确) {out['exactColumnWidth']:.2f} -> {g.col_w}px，右侧余 {g.remainder}px")
    print(f"步距 {g.pitch}{'（8 的倍数）' if out['pitchOn8pt'] else '（不是 8 的倍数，列起点会参差）'}")
    print(f"列起点 {g.xs}")
    print(f"列起点全在 8pt 上: {'是' if out['allOn8pt'] else '否'}")
    print("合法跨列宽度: " + ", ".join(f"{n}列={w}" for n, w in g.spans.items()))
    print(f"内容区 {g.margin}..{g.rights[-1]}")
    print("view.newGuideLayout 参数: " + json.dumps(out["guideLayoutParams"]))
    if g.snap == "pitch8" and g.remainder:
        print(f"注意: 余数 {g.remainder}px 全在右侧，内容区偏左；要保留精确列宽用 --snap none 或 --column-width")
    return 0


# ---------------------------------------------------------------- inspect input

def _unwrap(obj):
    for _ in range(5):
        if isinstance(obj, dict) and "layers" not in obj and isinstance(obj.get("result"), (dict, list)):
            obj = obj["result"]
        else:
            break
    return obj


def load_inspect(path):
    try:
        with open(path, encoding="utf-8-sig") as handle:
            text = handle.read()
    except OSError as exc:
        raise InputError(f"inspect 读取失败: {exc}") from exc
    try:
        candidates = [json.loads(text)]
    except ValueError:
        candidates = []
        for number, line in enumerate(text.splitlines(), 1):
            if line.strip():
                try:
                    candidates.append(json.loads(line))
                except ValueError as exc:
                    raise InputError(f"inspect 第 {number} 行不是 JSON: {exc}") from exc
    doc = None
    for cand in candidates:
        cand = _unwrap(cand)
        if isinstance(cand, list) and cand and isinstance(cand[-1], dict) and "layers" in cand[-1]:
            cand = cand[-1]
        if isinstance(cand, dict) and isinstance(cand.get("layers"), list):
            doc = cand
    if doc is None and len(candidates) == 1 and isinstance(_unwrap(candidates[0]), list):
        doc = {"layers": _unwrap(candidates[0])}
    if doc is None:
        raise InputError("inspect 里没有 layers：传 photocraft-cli info --compact 的输出，"
                         "或 document.inspect / doc.inspect 的结果")
    return doc


def to_nodes(layers):
    nodes = []
    for raw in layers or []:
        if not isinstance(raw, dict):
            raise InputError("layers 里有非对象条目")
        kind = _KIND.get(raw.get("kind"), "group" if raw.get("children") else "other")
        nodes.append(psd_contract.Node(raw.get("name", ""), kind, raw.get("visible", True),
                                       to_nodes(raw.get("children")), raw.get("bounds"),
                                       raw.get("text"), raw))
    return nodes


def load_spec(path):
    try:
        with open(path, encoding="utf-8-sig") as handle:
            spec = json.load(handle)
    except (OSError, ValueError) as exc:
        raise InputError(f"spec 读取失败: {exc}") from exc
    if not isinstance(spec, dict):
        raise InputError("spec.json 顶层必须是对象")
    required = ("width", "height", "margin", "gutter", "columns")
    missing = [k for k in required if k not in spec]
    if missing:
        raise InputError(f"spec.json 缺少字段: {', '.join(missing)}")
    for key in required + (("columnWidth",) if "columnWidth" in spec else ()):
        if isinstance(spec[key], bool) or not isinstance(spec[key], int):
            raise InputError(f"spec.json 的 {key} 必须是整数")
    if spec["width"] <= 0 or spec["height"] <= 0 or spec["columns"] < 1:
        raise InputError("spec.json 的 width/height 必须 > 0，columns 必须 >= 1")
    if spec["margin"] < 0 or spec["gutter"] < 0:
        raise InputError("spec.json 的 margin/gutter 不能为负")
    if spec.get("snap", "pitch8") not in ("pitch8", "none"):
        raise InputError('spec.json 的 snap 只能是 "pitch8" 或 "none"')
    scale = spec.get("spacingScale", DEFAULT_SCALE)
    if not (isinstance(scale, list) and scale and all(isinstance(v, int) and v > 0 for v in scale)):
        raise InputError("spec.json 的 spacingScale 必须是正整数数组")
    roles = spec.get("gridRoles", DEFAULT_GRID_ROLES)
    if not isinstance(roles, list) or any(r not in psd_contract.ROLES for r in roles):
        raise InputError(f"spec.json 的 gridRoles 只能取: {', '.join(psd_contract.ROLES)}")
    layers = spec.get("gridLayers", [])
    if not isinstance(layers, list) or any(not isinstance(v, str) for v in layers):
        raise InputError("spec.json 的 gridLayers 必须是字符串数组")
    warnings = [f"spec.json 有未知字段，已忽略: {k}" for k in sorted(set(spec) - SPEC_KEYS)]
    return spec, warnings


# ---------------------------------------------------------------- geometry

class Box:
    """x, y, w, h plus where each edge came from (text ink boxes are tolerated)."""

    __slots__ = ("x", "y", "w", "h", "left_tol", "top_text", "right_text", "bottom_text")

    def __init__(self, x, y, w, h, left_tol=None, text=False):
        self.x, self.y, self.w, self.h = x, y, w, h
        self.left_tol = left_tol
        self.top_text = self.right_text = self.bottom_text = text

    @property
    def right(self):
        return self.x + self.w

    @property
    def bottom(self):
        return self.y + self.h


def _text_tolerance(node, resolution):
    size = None
    if isinstance(node.text, dict) and isinstance(node.text.get("sizePt"), (int, float)):
        size = node.text["sizePt"] * resolution / 72.0
    if not size:
        size = node.bounds[3] if node.bounds else 0
    return (max(1, math.ceil(0.05 * size)), max(2, math.ceil(0.15 * size)))


def leaf_box(node, resolution):
    b = node.bounds
    if not node.visible or node.kind in ("group", "adjustment", "fill"):
        return None
    if not (isinstance(b, list) and len(b) >= 4 and all(isinstance(v, (int, float)) for v in b[:4])):
        return None
    if b[2] <= 0 or b[3] <= 0:
        return None
    if node.kind == "type":
        return Box(b[0], b[1], b[2], b[3], _text_tolerance(node, resolution), True)
    return Box(b[0], b[1], b[2], b[3])


def union_box(boxes):
    boxes = [b for b in boxes if b is not None]
    if not boxes:
        return None
    x = min(b.x for b in boxes)
    y = min(b.y for b in boxes)
    right = max(b.right for b in boxes)
    bottom = max(b.bottom for b in boxes)
    out = Box(x, y, right - x, bottom - y)
    at_left = [b for b in boxes if b.x == x]
    out.left_tol = None if any(b.left_tol is None for b in at_left) else \
        max((b.left_tol for b in at_left), key=lambda t: t[1])
    out.top_text = all(b.top_text for b in boxes if b.y == y)
    out.right_text = all(b.right_text for b in boxes if b.right == right)
    out.bottom_text = all(b.bottom_text for b in boxes if b.bottom == bottom)
    return out


def compute_boxes(nodes, resolution, table):
    """Fill table[id(node)] with a Box (groups: union of visible descendants)."""
    result = []
    for node in nodes:
        if node.kind == "group":
            box = union_box(compute_boxes(node.children, resolution, table)) if node.visible else None
        else:
            box = leaf_box(node, resolution)
        table[id(node)] = box
        result.append(box)
    return result


def _overlap(a, b):
    return a.x < b.right and b.x < a.right and a.y < b.bottom and b.y < a.bottom


def check_geometry(roots, spec, profile, canvas_width, resolution, issues):
    width = canvas_width
    g = Grid(spec["width"], spec["margin"], spec["gutter"], spec["columns"],
             spec.get("snap", "pitch8"), spec.get("columnWidth"))
    unit = min(spec.get("spacingScale", DEFAULT_SCALE))
    grid_roles = set(spec.get("gridRoles", DEFAULT_GRID_ROLES))
    grid_layers = set(spec.get("gridLayers", []))
    boxes = {}
    compute_boxes(roots, resolution, boxes)
    xs, rights = set(g.xs), set(g.rights)
    mk = psd_contract.make_issue

    def check_box(path, box):
        left_ok = True
        if box.x > 0:
            if box.left_tol:
                lo, hi = box.left_tol
                left_ok = any(-lo <= box.x - c <= hi for c in g.xs)
            else:
                left_ok = box.x in xs
            if not left_ok:
                issues.append(mk("MEDIUM", "GRID_X", path,
                                 f"x={box.x} 不在列起点上（最近列 {g.nearest(g.xs, box.x)}）",
                                 "用 layer.translate 移到列起点"))
        if box.right < width and not box.right_text and box.right not in rights:
            near = g.nearest(g.rights, box.right)
            hint = ""
            if left_ok and box.x in xs:
                legal = [w for w in g.spans.values() if box.x + w <= g.rights[-1]]
                if legal:
                    hint = f"；从 x={box.x} 起最近的合法宽度 {g.nearest(legal, box.w)}"
            issues.append(mk("MEDIUM", "GRID_RIGHT", path,
                             f"右边界 {box.right}（宽 {box.w}）不在列右边线上（最近 {near}）{hint}",
                             "宽度取 calc 列出的跨列宽度"))
        if box.y > 0 and not box.top_text and box.y % unit:
            issues.append(mk("LOW", "SPACING_Y", path, f"y={box.y} 不是 {unit} 的倍数", ""))

    def walk(nodes, ancestors):
        siblings = []
        for node in nodes:
            if not node.visible:
                continue
            path = psd_contract.display_path(ancestors, node.name)
            box = boxes.get(id(node))
            role = profile.role(node.name)
            raw = node.bounds
            if node.kind not in ("group", "adjustment", "fill") and isinstance(raw, list) \
                    and len(raw) >= 4 and (raw[2] == 0 or raw[3] == 0):
                issues.append(mk("MEDIUM", "ZERO_SIZE", path,
                                 f"bounds {raw}: 空层或整层在画布外（inspect 会把 bounds 裁到画布内）",
                                 "删除空层，或把内容移回画布"))
            if box is not None:
                selected = role in grid_roles or node.name in grid_layers or path in grid_layers
                if selected:
                    check_box(path, box)
                    siblings.append((path, box))
            if node.kind == "group":
                walk(node.children, ancestors + [node.name])
        # spacing between grid-checked siblings (LOW)
        ordered = sorted(siblings, key=lambda item: (item[1].y, item[1].x))
        for i, (pa, a) in enumerate(ordered):
            for pb, b in ordered[i + 1:]:
                if _overlap(a, b):
                    continue
                if a.x < b.right and b.x < a.right and b.y >= a.bottom and not a.bottom_text \
                        and not b.top_text:
                    gap = b.y - a.bottom
                elif a.y < b.bottom and b.y < a.bottom and b.x >= a.right and not a.right_text \
                        and b.left_tol is None:
                    gap = b.x - a.right
                else:
                    continue
                if gap % unit:
                    issues.append(mk("LOW", "SPACING_GAP", pb,
                                     f"与 {pa} 的间距 {gap}px 不是 {unit} 的倍数", ""))
                break
        # same-kind overlap among visible siblings
        tagged = []
        for node in nodes:
            role = profile.role(node.name)
            box = boxes.get(id(node))
            if node.visible and box is not None and role in OVERLAP_ROLES and node.kind != "type":
                tagged.append((psd_contract.display_path(ancestors, node.name), role, box))
        for i, (pa, ra, a) in enumerate(tagged):
            for pb, rb, b in tagged[i + 1:]:
                if ra == rb and _overlap(a, b):
                    issues.append(mk("MEDIUM", "SAME_KIND_OVERLAP", pa,
                                     f"与同级同类的 {pb} 重叠", "确认是有意叠放，否则重新摆位"))

    walk(roots, [])
    return {"columnWidth": g.col_w, "pitch": g.pitch, "columnX": g.xs, "snap": g.snap,
            "spacingUnit": unit, "gridRoles": sorted(grid_roles)}


def cmd_check(args):
    warnings = []
    spec = None
    if args.spec:
        spec, warnings = load_spec(args.spec)
    profile = psd_contract.load_profile(args.profile)
    doc = load_inspect(args.inspect)
    canvas = (doc.get("width"), doc.get("height"))
    if spec:
        if all(isinstance(v, int) for v in canvas) and canvas != (spec["width"], spec["height"]):
            raise InputError(f"inspect 画布 {canvas[0]}x{canvas[1]} 与 spec "
                             f"{spec['width']}x{spec['height']} 不一致；换 spec 或重取 inspect")
        canvas = (spec["width"], spec["height"])
    resolution = doc.get("resolution") if isinstance(doc.get("resolution"), (int, float)) else 72.0
    roots = to_nodes(doc["layers"])
    issues = psd_contract.structure_issues(roots, profile)
    grid = None
    if spec:
        grid = check_geometry(roots, spec, profile, canvas[0], resolution, issues)
    psd_contract.sort_issues(issues)
    counts = psd_contract.count_issues(issues)
    failed = psd_contract.blocking(counts, args.strict)
    count = sum(1 for _ in _iter(roots))
    result = {"result": "fail" if failed else "pass", "profile": profile.name,
              "geometryChecked": spec is not None, "grid": grid, "layerCount": count,
              "rootCount": len(roots), "issueCounts": counts, "issues": issues,
              "warnings": warnings}
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"结果: {result['result']} | profile {profile.name} | 层数 {count} | 根 {len(roots)}"
              f" | 几何{'已查' if spec else '未查（--no-geometry）'}")
        print("问题统计: " + " / ".join(f"{k} {v}" for k, v in counts.items()))
        for i in issues:
            print(f"  [{i['severity']}] {i['code']} {i['path']}: {i['message']}")
        for w in warnings:
            print(f"  警告: {w}")
    return 1 if failed else 0


def _iter(nodes):
    for node in nodes:
        yield node
        yield from _iter(node.children)


def main():
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, OSError):
            pass
    fmt = argparse.RawDescriptionHelpFormatter
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=fmt)
    sub = parser.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("calc", help="计算列网格", description=__doc__, formatter_class=fmt)
    c.add_argument("--width", type=int, required=True, help="画布宽 px")
    c.add_argument("--margin", type=int, default=80, help="左右页边距（默认 80）")
    c.add_argument("--gutter", type=int, default=24, help="列间距（默认 24）")
    c.add_argument("--columns", type=int, default=12, help="列数（默认 12）")
    mode = c.add_mutually_exclusive_group()
    mode.add_argument("--snap", choices=["pitch8", "none"], default="pitch8",
                      help="pitch8 = 步距取 8 的倍数（默认）；none = 精确列宽向下取整")
    mode.add_argument("--column-width", type=int, default=None, help="指定列宽，不再推算")
    c.add_argument("--json", action="store_true")
    c.set_defaults(fn=cmd_calc)
    k = sub.add_parser("check", help="验收层树与栅格", description=__doc__, formatter_class=fmt)
    k.add_argument("--inspect", required=True, help="info --compact / document.inspect 的 JSON")
    geo = k.add_mutually_exclusive_group(required=True)
    geo.add_argument("--spec", help="spec.json（width height margin gutter columns 必填）")
    geo.add_argument("--no-geometry", action="store_true", help="只查命名与结构，不查栅格")
    k.add_argument("--profile", default="zh", help="命名 profile: zh（默认）、en 或项目 JSON 路径")
    k.add_argument("--strict", action="store_true", help="MEDIUM 也算失败")
    k.add_argument("--json", action="store_true")
    k.set_defaults(fn=cmd_check)
    args = parser.parse_args()
    try:
        return args.fn(args)
    except (InputError, psd_contract.ProfileError) as exc:
        if getattr(args, "json", False):
            print(json.dumps({"result": "error", "error": str(exc)}, ensure_ascii=False))
        else:
            print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
