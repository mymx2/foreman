#!/usr/bin/env python3
"""psd-audit.py — PSD 结构审计与规范化前后对比（只读）。

用法:
  python psd-audit.py audit <psd> [--json] [--strict] [--installed-fonts FILE] [--max-depth N]
  python psd-audit.py compare <old> <new> [--json] [--strict] [--installed-fonts FILE] [--max-depth N]

检查：根组节点树前缀、默认/重复名、空组、嵌套深度（仅在显式设 --max-depth 时）、根层散落、隐藏层、
文字层与字体、可疑栅格化文字、同级层过多。

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

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import psd_contract  # noqa: E402  契约常量单点定义
from psd_contract import (  # noqa: E402
    NODE_ROOT_PREFIXES,
    is_page_wrapper,
    is_node_root,
    is_node_group,
    hidden_allowed as contract_hidden_allowed,
)
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


def text_layer_in_node(ancestors):
    """节点树下文字层应在节点组内（组件_/区块_/页面_/参考_/版本_），而不是散落在根层。"""
    return any(psd_contract.is_node_group(name) for name in ancestors)


def hidden_allowed(ancestors, name, is_group=True):
    """隐藏内容允许在 参考_* 组或 版本_* 包装下（与 psd_contract / layout-design 同语义）。"""
    return contract_hidden_allowed(ancestors, name)


def check_reference_and_order(child_groups, children, path_prefix, issues):
    """节点树下不再固定根组顺序；只检查 参考_* 组必须隐藏。"""
    ref = next((g for g in child_groups if (g.name or "").startswith("参考_")), None)
    if ref is not None:
        if ref.visible is not False:
            add_issue(
                issues, "MEDIUM", "REFERENCE_VISIBLE", display_path([path_prefix] if path_prefix else [], ref.name),
                "参考组没有隐藏", "隐藏参考组，避免进入最终合成",
            )
    return child_groups


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
            "根层存在未分组的图层", "把内容移入 组件_ 或 区块_ 组",
        )

    # 节点树契约：根组必须以 页面_/区块_/参考_/版本_ 开头
    valid_root = [g for g in root_groups if (g.name or "").startswith(NODE_ROOT_PREFIXES)]
    unknown = [g for g in root_groups if g not in valid_root]
    for group in unknown:
        add_issue(
            issues, "MEDIUM", "ROOT_UNKNOWN_GROUP", display_path([], group.name or ""),
            "根组命名不合规（应以 页面_/区块_/参考_/版本_ 开头）",
            "改用节点树前缀命名",
        )
    if valid_root:
        check_reference_and_order(valid_root, root, "", issues)
    # 页面/版本包装组：内部应以 区块_/组件_/参考_ 组织，不允许散落图层
    wrappers = [g for g in valid_root if is_page_wrapper(g.name or "")]
    for wrapper in wrappers:
        children = list(wrapper)
        child_groups = [c for c in children if c.is_group()]
        # 元素层可直放 页面_/版本_ 下（见 ALLOW_NESTED），由 NODE_PREFIX_MISMATCH 管前缀合规
        page_unknown = [g for g in child_groups if not psd_contract.is_node_group(g.name or "")]
        for group in page_unknown:
            add_issue(
                issues, "MEDIUM", "PAGE_UNKNOWN_GROUP", display_path([wrapper.name], group.name or ""),
                "页面/版本包装组内的子组命名不合规（应为 节点组前缀）",
                "改用节点树前缀命名（design-spec.md 第 3 节）",
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
            # max_depth 为 0/负数时不限制深度：组件内部多层嵌套是正常的，
            # 深度只作参考统计（stats.maxDepth），不作判级依据
            if max_depth > 0 and depth > max_depth and not depth_flagged:
                add_issue(
                    issues, "MEDIUM", "DEPTH_EXCEEDED", path,
                    f"嵌套深度 {depth} 超过设定上限 {max_depth}", "合并或扁平化中间层",
                )
                current_depth_flagged = True

            if not name.strip():
                add_issue(issues, "HIGH", "EMPTY_NAME", path, "图层名为空", "按元素类型前缀命名（design-spec.md）")
            else:
                if name != name.strip():
                    add_issue(issues, "HIGH", "WHITESPACE_NAME", path, "名称含首尾空格", "去掉首尾空格")
                if DEFAULT_NAME_RE.match(name.strip()):
                    add_issue(issues, "HIGH", "DEFAULT_NAME", path, "使用默认图层名", "按元素类型前缀命名（design-spec.md）")
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

            # 节点树边界：子层前缀必须符合父组允许的子前缀
            if ancestors and not psd_contract.child_prefix_ok(ancestors[-1], name):
                add_issue(
                    issues, "MEDIUM", "NODE_PREFIX_MISMATCH", path,
                    f"层级不符：{name} 不应出现在 {ancestors[-1]} 下",
                    "见 psd_contract.ALLOW_NESTED / design-spec.md 第 3 节",
                )

            is_group = layer.is_group()
            if is_group:
                stats["groups"] += 1
                if len(layer) == 0:
                    add_issue(issues, "HIGH", "EMPTY_GROUP", path, "空组", "删除空组")
                elif len(layer) == 1 and not psd_contract.is_node_group(name):
                    # 节点组（页面_/区块_/组件_/参考_/版本_）是语义容器，单元素正常；
                    # 其他组只有一个子层才是冗余包装
                    add_issue(issues, "MEDIUM", "SINGLE_CHILD_GROUP", path, "组内只有一个子层（冗余组）", "确认是否有分组必要，无则合并到父级")
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
                in_text = text_layer_in_node(ancestors)
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
                            "文字层不在组件/区块组内（节点树契约）",
                            "移入 区块_ 下的 组件_ 组，保持文字可编辑",
                        )
                else:
                    # 节点树下元素类型混杂正常，但「命名像文字却是像素层」是栅格化嫌疑，
                    # 无论在组件内还是根层都要报（否则组件内栅格化文字静默过验收）
                    if TEXT_NAME_RE.search(name):
                        add_issue(
                            issues, "MEDIUM", "POSSIBLE_RASTERIZED_TEXT", path,
                            "非文字层但名称像文字，可能已栅格化", "确认；能从文案重打就重打",
                        )

            if is_group:
                walk(layer, ancestors + [name], current_depth_flagged)

        # 视觉层序：psd_tools 自下而上，背景_* 元素应在 children 开头（最底）
        child_names = [(c.name or "") for c in children]
        bg_idx = [i for i, nm in enumerate(child_names) if nm.startswith("背景_")]
        if bg_idx and min(bg_idx) != 0:
            add_issue(
                issues, "MEDIUM", "BACKGROUND_NOT_BOTTOM", path_prefix or "<root>",
                f"背景层不在最底层: {child_names}（背景_ 应在最前，psd_tools 自下而上）",
                "把 背景_* 移到组内最底",
            )

    walk(psd, [])
    issues.sort(key=lambda x: (SEVERITY_ORDER.get(x["severity"], 9), x["path"], x["code"]))
    summary = Counter(i["severity"] for i in issues)
    result = {
        "file": os.path.abspath(path),
        "size": list(psd.size),
        "colorMode": int(psd.color_mode),
        "depth": int(psd.depth),
        "stats": stats,
        # 层树顺序；psd_tools 内部列表自下而上。
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
        parser.add_argument("--max-depth", type=int, default=0, help="允许的最大嵌套深度；0 或负数表示不限制（默认 0）")

    a = sub.add_parser("audit", help="审计单个 PSD")
    a.add_argument("psd")
    common(a)

    c = sub.add_parser("compare", help="审计并对比原稿与规范稿")
    c.add_argument("old")
    c.add_argument("new")
    common(c)

    args = ap.parse_args()
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
