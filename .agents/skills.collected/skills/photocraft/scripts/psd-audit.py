#!/usr/bin/env python3
"""psd-audit.py — PSD 结构审计与规范化前后对比（只读）。

用法:
  python psd-audit.py audit <psd> [--json] [--strict] [--installed-fonts FILE] [--max-depth 4]
  python psd-audit.py compare <old> <new> [--json] [--strict] [--installed-fonts FILE] [--max-depth 4]

检查：根组分类与顺序、默认/重复名、空组、嵌套深度、根层散落、隐藏层、
文字层与字体、文字组内非文字层、可疑栅格化文字、同级层过多。

--installed-fonts 接受 JSON：字符串数组，或 {"fonts": [...]}；元素可为字符串，
或含 family/name/postscript_name 的对象。PSD 字体表里的 family 常为空，只有
PostScript 名；传家族名清单会误报。安装状态以 PhotoCraft 的
type.resolveMissingFonts/type.fonts 为准，本参数只做辅助核对。

退出码：默认 0 = 无 CRITICAL/HIGH；1 = 有；2 = 错误。
--strict：MEDIUM 也视为失败，用于规范化稿验收。
依赖 psd_tools（pip install psd-tools）。
"""
import argparse
import json
import os
import re
import sys
from collections import Counter

ROOT_CATEGORIES = ["参考", "调整", "装饰", "文字", "主体", "背景"]
DEFAULT_NAME_RE = re.compile(
    r"^(图层|Layer|组|Group|文本|Text|文字图层|形状|Shape|智能对象|Smart Object|"
    r"调整图层|Adjustment Layer|填充|Fill|Color Fill|Gradient Fill|Pattern Fill|"
    r"矩形|Rectangle|椭圆|Ellipse|曲线|Curve|色阶|Levels|亮度/对比度|Brightness/Contrast|"
    r"色相/饱和度|Hue/Saturation|色彩平衡|Color Balance|照片滤镜|Photo Filter|"
    r"渐变映射|Gradient Map|纯色|Solid Color|渐变|Gradient|图案|Pattern|路径|Path|"
    r"新建|Untitled|未命名)([-_ ]?\d+)?$",
    re.I,
)
COPY_RE = re.compile(r"(?:\s*(?:副本|拷贝|copy)(?:\s*\d+)?)$", re.I)
TEXT_NAME_RE = re.compile(r"(文字|标题|正文|文案|按钮|\b(?:title|heading|text)\b)", re.I)
PAGE_GROUP_RE = re.compile(r"^(页面|版本)_")
SEVERITY_ORDER = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}
MAX_SIBLINGS = 30


def load_psd(path):
    try:
        from psd_tools import PSDImage
    except ImportError as e:
        raise RuntimeError("需要 psd-tools（pip install psd-tools）") from e
    try:
        return PSDImage.open(path)
    except Exception as e:
        raise RuntimeError(f"无法打开 PSD: {e}") from e


def load_installed_fonts(path):
    if not path:
        return None
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, dict):
        data = data.get("fonts", data.get("families", list(data.keys())))
    if not isinstance(data, list):
        raise RuntimeError("--installed-fonts 需要 JSON 数组，或含 fonts 数组的对象")
    names = set()
    for item in data:
        if isinstance(item, str):
            name = item
        elif isinstance(item, dict):
            name = item.get("family") or item.get("name") or item.get("postscript_name") or ""
        else:
            name = ""
        if str(name).strip():
            names.add(str(name).strip().casefold())
    return names


def add_issue(issues, severity, code, path, message, suggestion=""):
    issues.append({
        "severity": severity,
        "code": code,
        "path": path,
        "message": message,
        "suggestion": suggestion,
    })


def display_path(ancestors, name):
    parts = list(ancestors) + [name if name.strip() else "<empty>"]
    return "/".join(parts)


def is_page_wrapper(name):
    return bool(PAGE_GROUP_RE.match(name or ""))


def valid_category_position(name, index, ancestors):
    """标准分类只允许在根级，或页面/版本包装组的直接子级。"""
    if name not in ROOT_CATEGORIES:
        return False
    if index == 0:
        return True
    return index == 1 and is_page_wrapper(ancestors[0] if ancestors else "")


def has_valid_text_group(ancestors):
    return any(
        name == "文字" and valid_category_position(name, i, ancestors)
        for i, name in enumerate(ancestors)
    )


def hidden_allowed(ancestors, name, is_group):
    """隐藏内容只允许在有效的 参考 组或根级 版本_* 组下。"""
    for i, ancestor in enumerate(ancestors):
        if ancestor == "参考" and valid_category_position(ancestor, i, ancestors):
            return True
        if i == 0 and (ancestor or "").startswith("版本_"):
            return True
    if is_group and name == "参考" and valid_category_position(name, len(ancestors), ancestors):
        return True
    return bool(is_group and not ancestors and (name or "").startswith("版本_"))


def check_reference_and_order(child_groups, children, path_prefix, issues):
    present = [g for g in child_groups if (g.name or "") in ROOT_CATEGORIES]
    indices = [ROOT_CATEGORIES.index(g.name) for g in present]
    # psd_tools 的层列表自下而上；标准顺序自上而下，所以索引应递减。
    if indices != sorted(indices, reverse=True):
        add_issue(
            issues, "MEDIUM", "ROOT_ORDER", path_prefix or "<root>",
            "根分类顺序不符合 参考→调整→装饰→文字→主体→背景（自上而下）",
            "按标准顺序重排根组",
        )
    ref = next((g for g in present if g.name == "参考"), None)
    if ref is not None:
        if not children or children[-1] is not ref:
            add_issue(
                issues, "MEDIUM", "REFERENCE_NOT_TOP", display_path([path_prefix] if path_prefix else [], ref.name),
                "参考组不在最上层", "把参考组移到顶层并保持隐藏",
            )
        if ref.visible is not False:
            add_issue(
                issues, "MEDIUM", "REFERENCE_VISIBLE", display_path([path_prefix] if path_prefix else [], ref.name),
                "参考组没有隐藏", "隐藏参考组，避免进入最终合成",
            )
    return present


def audit_tree(psd, path, installed_fonts, max_depth):
    issues = []
    stats = {
        "total": 0,
        "leaves": 0,
        "groups": 0,
        "text": 0,
        "hidden": 0,
        "smartobjects": 0,
        "masks": 0,
        "maxDepth": 0,
    }
    font_inventory = set()

    root = list(psd)
    if not root:
        add_issue(issues, "CRITICAL", "EMPTY_PSD", "<root>", "PSD 没有图层", "确认文件是否损坏或只有合成图")

    root_groups = [l for l in root if l.is_group()]
    root_loose = [l for l in root if not l.is_group()]
    for layer in root_loose:
        add_issue(
            issues, "HIGH", "ROOT_LOOSE_LAYER", display_path([], layer.name or ""),
            "根层存在未分组的图层", "把内容移入 背景/主体/文字/装饰/调整 组",
        )

    canonical = [g for g in root_groups if (g.name or "") in ROOT_CATEGORIES]
    wrappers = [g for g in root_groups if PAGE_GROUP_RE.match(g.name or "")]
    unknown = [g for g in root_groups if g not in canonical and g not in wrappers]
    for group in unknown:
        add_issue(
            issues, "MEDIUM", "ROOT_UNKNOWN_GROUP", display_path([], group.name or ""),
            "根组不是标准分类，也不是 页面_/版本_ 包装组", "改用标准根分类或页面/版本包装",
        )
    if wrappers and canonical:
        add_issue(
            issues, "MEDIUM", "MIXED_ROOT_LAYOUT", "<root>",
            "同时存在页面/版本包装组和裸根分类", "统一用一种布局",
        )
    if canonical:
        check_reference_and_order(canonical, root, "", issues)
    for wrapper in wrappers:
        children = list(wrapper)
        child_groups = [c for c in children if c.is_group()]
        for child in children:
            if not child.is_group():
                add_issue(
                    issues, "HIGH", "PAGE_LOOSE_LAYER", display_path([wrapper.name], child.name or ""),
                    "页面/版本包装组内存在未分组的图层", "移入该页面的标准分类组",
                )
        page_unknown = [g for g in child_groups if (g.name or "") not in ROOT_CATEGORIES]
        for group in page_unknown:
            add_issue(
                issues, "MEDIUM", "PAGE_UNKNOWN_GROUP", display_path([wrapper.name], group.name or ""),
                "页面/版本包装组内的子组不是标准分类", "改用六个标准分类",
            )
        if not any((g.name or "") in ROOT_CATEGORIES for g in child_groups):
            add_issue(
                issues, "MEDIUM", "PAGE_NO_CATEGORY", display_path([], wrapper.name or ""),
                "页面/版本包装组内没有标准分类组", "按 背景/主体/文字/装饰/调整/参考 分组",
            )
        check_reference_and_order(child_groups, children, wrapper.name or "", issues)

    def walk(container, ancestors, depth_flagged=False):
        children = list(container)
        path_prefix = "/".join(ancestors)
        if len(children) > MAX_SIBLINGS:
            add_issue(
                issues, "LOW", "TOO_MANY_SIBLINGS", path_prefix or "<root>",
                f"同级图层/组超过 {MAX_SIBLINGS} 个", "按语义再分组",
            )
        seen_names = {}
        for layer in children:
            name = layer.name or ""
            path = display_path(ancestors, name)
            depth = len(ancestors) + 1
            stats["total"] += 1
            stats["maxDepth"] = max(stats["maxDepth"], depth)
            current_depth_flagged = depth_flagged
            if depth > max_depth and not depth_flagged:
                add_issue(
                    issues, "MEDIUM", "DEPTH_EXCEEDED", path,
                    f"嵌套深度 {depth} 超过上限 {max_depth}", "合并或扁平化中间层",
                )
                current_depth_flagged = True

            if not name.strip():
                add_issue(issues, "HIGH", "EMPTY_NAME", path, "图层名为空", "按 类别_语义 命名")
            else:
                if name != name.strip():
                    add_issue(issues, "HIGH", "WHITESPACE_NAME", path, "名称含首尾空格", "去掉首尾空格")
                if DEFAULT_NAME_RE.match(name.strip()):
                    add_issue(issues, "HIGH", "DEFAULT_NAME", path, "使用默认图层名", "按 类别_语义 命名")
                elif COPY_RE.search(name.strip()):
                    add_issue(issues, "MEDIUM", "COPY_NAME", path, "名称带副本/拷贝/copy 后缀", "用语义名或 _01/_02 区分")
            if "/" in name:
                add_issue(issues, "LOW", "NAME_HAS_SLASH", path, "图层名包含 /，会破坏路径可读性", "改用 - 或 _")
            key = name.strip().casefold()
            if key in seen_names:
                add_issue(
                    issues, "HIGH", "DUPLICATE_SIBLING_NAME", path,
                    f"同一父级下重复名称（首次出现：{seen_names[key]}）", "重命名并用 _01/_02 区分",
                )
            else:
                seen_names[key] = path

            is_group = layer.is_group()
            if is_group:
                stats["groups"] += 1
                if len(layer) == 0:
                    add_issue(issues, "HIGH", "EMPTY_GROUP", path, "空组", "删除空组")
                elif len(layer) == 1:
                    add_issue(issues, "LOW", "SINGLE_CHILD_GROUP", path, "组内只有一个子层", "确认是否有分组必要")
            else:
                stats["leaves"] += 1
                if getattr(layer, "kind", None) == "smartobject":
                    stats["smartobjects"] += 1
            if getattr(layer, "mask", None) is not None:
                stats["masks"] += 1

            if layer.visible is False:
                stats["hidden"] += 1
                if not hidden_allowed(ancestors, name, is_group):
                    add_issue(
                        issues, "MEDIUM", "HIDDEN_OUTSIDE_REFERENCE", path,
                        "隐藏层不在有效的 参考/版本_ 组下", "删除或移入 参考/版本_ 组并在描述文件登记",
                    )

            if not is_group:
                in_text = has_valid_text_group(ancestors)
                if getattr(layer, "kind", None) == "type":
                    stats["text"] += 1
                    fonts = []
                    font_read_error = False
                    try:
                        for font in layer.typesetting.fonts:
                            family = font.family or ""
                            postscript = font.postscript_name or ""
                            style = font.style or ""
                            if family or postscript:
                                fonts.append((family, postscript, style))
                    except Exception as e:
                        font_read_error = True
                        add_issue(issues, "HIGH", "FONT_READ_ERROR", path, f"读取文字字体失败: {e}", "检查 PSD 文字数据")
                    if not fonts and not font_read_error:
                        try:
                            font_names = layer.font_names or []
                        except Exception:
                            font_names = []
                        fonts = [("", n, "") for n in font_names if n]
                    if not fonts and not font_read_error:
                        add_issue(issues, "HIGH", "TEXT_NO_FONT", path, "文字层没有可用字体记录", "重新指定字体并核对 type.fonts")
                    for family, postscript, style in fonts:
                        label = family or postscript
                        font_inventory.add((label, style))
                        if installed_fonts is not None:
                            candidates = {x.casefold() for x in (family, postscript) if x}
                            if not candidates.intersection(installed_fonts):
                                add_issue(
                                    issues, "HIGH", "FONT_NOT_INSTALLED", path,
                                    f"字体未在传入清单中: {label or postscript}（清单需含 PostScript 或 PSD 家族名；应用侧以 resolveMissingFonts 为准）",
                                    "安装/注册字体后用 type.resolveMissingFonts 复核",
                                )
                    if not in_text:
                        add_issue(
                            issues, "MEDIUM", "TEXT_OUTSIDE_TEXT_GROUP", path,
                            "文字层不在有效的 文字 组下（根级或页面/版本包装组的直接子级）",
                            "移入有效的 文字 组，保持文字可编辑",
                        )
                else:
                    if in_text:
                        severity = "HIGH" if layer.kind in ("pixel", "smartobject") else "MEDIUM"
                        add_issue(
                            issues, severity, "NON_TEXT_IN_TEXT_GROUP", path,
                            "文字组内存在非文字层", "确认是否栅格化文字；是则重打，否则移到 装饰/主体",
                        )
                    if TEXT_NAME_RE.search(name) and not in_text:
                        add_issue(
                            issues, "LOW", "POSSIBLE_RASTERIZED_TEXT", path,
                            "非文字层但名称像文字，可能已栅格化", "确认；能从文案重打就重打",
                        )

            if is_group:
                walk(layer, ancestors + [name], current_depth_flagged)

    walk(psd, [])
    issues.sort(key=lambda x: (SEVERITY_ORDER.get(x["severity"], 9), x["path"], x["code"]))
    summary = Counter(i["severity"] for i in issues)
    result = {
        "file": os.path.abspath(path),
        "size": list(psd.size),
        "colorMode": int(psd.color_mode),
        "depth": int(psd.depth),
        "stats": stats,
        # 面板自上而下的根组顺序；psd_tools 内部列表自下而上。
        "rootGroups": [g.name or "" for g in reversed(root_groups)],
        "fonts": [{"name": n, "style": s} for n, s in sorted(font_inventory)],
        "issues": issues,
        "summary": {sev: summary.get(sev, 0) for sev in ("CRITICAL", "HIGH", "MEDIUM", "LOW")},
    }
    result["summary"]["ok"] = result["summary"]["CRITICAL"] == 0 and result["summary"]["HIGH"] == 0
    result["summary"]["strictOk"] = (
        result["summary"]["CRITICAL"] == 0
        and result["summary"]["HIGH"] == 0
        and result["summary"]["MEDIUM"] == 0
    )
    return result


def audit_file(path, installed_fonts, max_depth):
    return audit_tree(load_psd(path), path, installed_fonts, max_depth)


def md_escape(text):
    return str(text).replace("|", "\\|").replace("\n", " ")


def format_markdown(result):
    s = result["stats"]
    font_text = ", ".join(
        f"{f['name']} [{f['style']}]" if f["style"] else f["name"]
        for f in result["fonts"]
    ) or "无"
    lines = [
        f"# PSD audit: {result['file']}",
        "",
        f"- 尺寸: {result['size'][0]}x{result['size'][1]}；颜色模式: {result['colorMode']}；位深: {result['depth']}",
        f"- 总层数 {s['total']}；叶子层 {s['leaves']}；组 {s['groups']}；文字层 {s['text']}；隐藏 {s['hidden']}；智能对象 {s['smartobjects']}",
        f"- 最大深度 {s['maxDepth']}；根组: {', '.join(result['rootGroups']) or '无'}",
        f"- 字体: {font_text}",
        "",
    ]
    summary = result["summary"]
    lines.append(
        "问题: CRITICAL {CRITICAL} / HIGH {HIGH} / MEDIUM {MEDIUM} / LOW {LOW}；严格模式: {strict}".format(
            strict="通过" if summary.get("strictOk") else "未通过",
            **summary,
        )
    )
    lines.append("")
    if not result["issues"]:
        lines.append("未发现结构问题。")
    else:
        lines.append("| 级别 | 代码 | 路径 | 说明 | 建议 |")
        lines.append("| --- | --- | --- | --- | --- |")
        for issue in result["issues"]:
            lines.append(
                "| {severity} | {code} | {path} | {message} | {suggestion} |".format(
                    severity=issue["severity"],
                    code=issue["code"],
                    path=md_escape(issue["path"]),
                    message=md_escape(issue["message"]),
                    suggestion=md_escape(issue.get("suggestion", "")),
                )
            )
    return "\n".join(lines)


def compare_markdown(old, new):
    lines = [
        f"# PSD compare: {old['file']} → {new['file']}",
        "",
        "| 指标 | 原稿 | 规范稿 |",
        "| --- | --- | --- |",
    ]
    for key in ("total", "leaves", "groups", "text", "hidden", "smartobjects", "maxDepth"):
        lines.append(f"| {key} | {old['stats'][key]} | {new['stats'][key]} |")
    for sev in ("CRITICAL", "HIGH", "MEDIUM", "LOW"):
        lines.append(f"| {sev} | {old['summary'][sev]} | {new['summary'][sev]} |")
    lines.extend([
        "",
        f"原稿根组: {', '.join(old['rootGroups']) or '无'}",
        f"规范稿根组: {', '.join(new['rootGroups']) or '无'}",
        "",
        "## 规范稿审计",
        "",
        format_markdown(new),
    ])
    return "\n".join(lines)


def exit_code(result, strict=False):
    blocked = result["summary"]["CRITICAL"] or result["summary"]["HIGH"]
    if strict:
        blocked = blocked or result["summary"]["MEDIUM"]
    return 1 if blocked else 0


def main():
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, OSError):
            pass

    ap = argparse.ArgumentParser(description="PSD 结构审计与规范化前后对比（只读）")
    sub = ap.add_subparsers(dest="cmd", required=True)

    def common(parser):
        parser.add_argument("--json", action="store_true", help="输出一行 JSON")
        parser.add_argument("--strict", action="store_true", help="MEDIUM 也视为失败（规范化验收）")
        parser.add_argument("--installed-fonts", default=None, help="辅助字体清单 JSON（需含 PostScript 或 PSD 家族名）")
        parser.add_argument("--max-depth", type=int, default=4, help="允许的最大嵌套深度（默认 4）")

    a = sub.add_parser("audit", help="审计单个 PSD")
    a.add_argument("psd")
    common(a)

    c = sub.add_parser("compare", help="审计并对比原稿与规范稿")
    c.add_argument("old")
    c.add_argument("new")
    common(c)

    args = ap.parse_args()
    if args.max_depth < 1:
        print("ERROR: --max-depth 必须 >= 1", file=sys.stderr)
        return 2
    try:
        installed = load_installed_fonts(args.installed_fonts)
        if args.cmd == "audit":
            result = audit_file(args.psd, installed, args.max_depth)
            if args.json:
                print(json.dumps(result, ensure_ascii=False))
            else:
                print(format_markdown(result))
            return exit_code(result, args.strict)
        old = audit_file(args.old, installed, args.max_depth)
        new = audit_file(args.new, installed, args.max_depth)
        if args.json:
            print(json.dumps({"old": old, "new": new}, ensure_ascii=False))
        else:
            print(compare_markdown(old, new))
        return exit_code(new, args.strict)
    except Exception as e:
        if args.json:
            print(json.dumps({"error": str(e)}, ensure_ascii=False))
        else:
            print(f"ERROR: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
