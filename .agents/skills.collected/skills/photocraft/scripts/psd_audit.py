#!/usr/bin/env python3
"""psd_audit.py — PSD 结构审计与规范化前后对比（只读，需要 psd-tools）。

用法:
  python <skill-dir>/scripts/psd_audit.py audit PSD [--profile zh|en|FILE.json] [--json] [--strict]
         [--installed-fonts FILE] [--max-depth N]
  python <skill-dir>/scripts/psd_audit.py compare OLD NEW [同上选项]

命名前缀取自 --profile（默认 zh；en 与项目 JSON 的格式见 psd_contract.py）。检查项:
  CRITICAL  EMPTY_PSD 没有图层
  HIGH      ROOT_LOOSE_LAYER 根层散落 · EMPTY_NAME / WHITESPACE_NAME · DEFAULT_NAME 默认名
            （含 "Layer 1 copy" 这类默认名的副本）· DUPLICATE_SIBLING_NAME 同级重名 · EMPTY_GROUP
            · TEXT_NO_FONT / FONT_READ_ERROR · FONT_NOT_INSTALLED（只在给了 --installed-fonts 时）
  MEDIUM    ROOT_UNKNOWN_GROUP · NODE_PREFIX_MISMATCH 层级不符 · REFERENCE_VISIBLE 参考组可见
            · HIDDEN_OUTSIDE_REFERENCE · TEXT_OUTSIDE_NODE_GROUP · BACKGROUND_NOT_BOTTOM
            · SINGLE_CHILD_GROUP（只查非节点组）· COPY_NAME · DEPTH_EXCEEDED（只在给了 --max-depth 时）
            · POSSIBLE_RASTERIZED_TEXT（像素层的名字以 profile 的文字前缀开头；形状、智能对象不报）
  LOW       TOO_MANY_SIBLINGS（>30）· NAME_HAS_PATH_CHAR · FONT_FAMILY_ONLY（只按家族名对上，字重未核）

--installed-fonts FILE: 字体清单，接受 JSON 或 JSON Lines，例如
  photocraft-cli run --new '{"width":8,"height":8}' --cmd type.fonts \\
      --cmd type.fonts --params '{"family":"Inter"}' > fonts.jsonl
  会从任意层级收集字符串和对象里的 family / name / postscriptName / postscript_name。
  PhotoCraft 写的 PSD 只存 PostScript 名（如 Inter-Regular），家族名、样式为空：传 type.fonts {family}
  的 faces 才能精确比对；只给家族清单时按"PostScript 名去掉 -后缀、忽略空格大小写"匹配家族，报 LOW。
  安装状态以应用侧 type.resolveMissingFonts 为准，本参数只做辅助核对。

输出: 默认 Markdown；--json 输出一行 JSON（含 issues、summary、stats、rootGroups、fonts、
readerWarnings = psd-tools 读文件时的告警）。rootGroups 按面板自上而下。
退出码: 0 = 无 CRITICAL/HIGH（--strict 时 MEDIUM 也算失败）；1 = 有；
        2 = 文件读不了、缺 psd-tools、参数或 profile 错误（读不了文件不算 CRITICAL）。
"""
import argparse
import json
import logging
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import psd_contract  # noqa: E402

EXIT_OK, EXIT_BLOCKED, EXIT_ERROR = 0, 1, 2
_FILL_KINDS = ("shape", "solidcolorfill", "gradientfill", "patternfill")


class _Collector(logging.Handler):
    """Keeps psd-tools reader warnings out of stderr and in the report."""

    def __init__(self):
        super().__init__(logging.WARNING)
        self.messages = []

    def emit(self, record):
        message = record.getMessage()
        if message not in self.messages:
            self.messages.append(message)


def _norm_family(text):
    return re.sub(r"[\s_\-]+", "", text or "").casefold()


def load_installed_fonts(path):
    """Return (exact names casefolded, normalised family keys)."""
    if not path:
        return None
    with open(path, encoding="utf-8-sig") as handle:
        text = handle.read()
    try:
        documents = [json.loads(text)]
    except ValueError:
        documents = []
        for number, line in enumerate(text.splitlines(), 1):
            if line.strip():
                try:
                    documents.append(json.loads(line))
                except ValueError as exc:
                    raise RuntimeError(f"--installed-fonts 第 {number} 行不是 JSON: {exc}") from exc
    exact, families = set(), set()

    def add(value, is_family):
        value = str(value).strip()
        if value:
            exact.add(value.casefold())
            if is_family:
                families.add(_norm_family(value))

    def collect(obj):
        if isinstance(obj, str):
            add(obj, True)
        elif isinstance(obj, list):
            for item in obj:
                collect(item)
        elif isinstance(obj, dict):
            for key in ("family", "name"):
                if isinstance(obj.get(key), str):
                    add(obj[key], True)
            for key in ("postscriptName", "postscript_name", "fullName"):
                if isinstance(obj.get(key), str):
                    add(obj[key], False)
            for key in ("result", "fonts", "families", "faces"):
                if key in obj:
                    collect(obj[key])

    for doc in documents:
        collect(doc)
    if not exact:
        raise RuntimeError("--installed-fonts 里没找到字体名（需要 type.fonts 的输出或字体名数组）")
    return exact, families


def _kind(layer):
    if layer.is_group():
        return "group"
    kind = getattr(layer, "kind", "") or ""
    if kind in ("type", "pixel", "smartobject"):
        return kind
    if kind in _FILL_KINDS:
        try:
            return "shape" if layer.has_vector_mask() else "fill"
        except Exception:
            return "shape"
    return "adjustment"


def to_nodes(container):
    """psd-tools lists layers bottom-up; Nodes are top-down like the Layers panel."""
    nodes = []
    for layer in reversed(list(container)):
        children = to_nodes(layer) if layer.is_group() else []
        nodes.append(psd_contract.Node(layer.name or "", _kind(layer), layer.visible,
                                       children, raw=layer))
    return nodes


def _layer_fonts(layer, path, issues):
    fonts, failed = [], False
    try:
        for font in layer.typesetting.fonts:
            family, postscript = font.family or "", font.postscript_name or ""
            if family or postscript:
                fonts.append((family, postscript, font.style or ""))
    except Exception as exc:  # psd-tools raises many shapes of errors on odd EngineData
        failed = True
        issues.append(psd_contract.make_issue("HIGH", "FONT_READ_ERROR", path,
                                              f"读取文字字体失败: {exc}", "检查 PSD 文字数据"))
    if not fonts and not failed:
        try:
            fonts = [("", n, "") for n in (layer.font_names or []) if n]
        except Exception:
            fonts = []
    if not fonts and not failed:
        issues.append(psd_contract.make_issue("HIGH", "TEXT_NO_FONT", path, "文字层没有字体记录",
                                              "重新指定字体并用 type.fonts 核对"))
    return fonts


def _check_font(family, postscript, installed, path, issues):
    exact, families = installed
    label = postscript or family
    if any(x.casefold() in exact for x in (family, postscript) if x):
        return
    keys = {_norm_family(family)} if family else set()
    if postscript:
        keys.add(_norm_family(postscript.split("-")[0]))
    if keys & families:
        issues.append(psd_contract.make_issue(
            "LOW", "FONT_FAMILY_ONLY", path,
            f"字体 {label} 只按家族名对上，字重/样式未核对",
            "把 type.fonts {family} 的 faces 也放进 --installed-fonts 可精确比对"))
        return
    issues.append(psd_contract.make_issue(
        "HIGH", "FONT_NOT_INSTALLED", path, f"字体不在传入清单里: {label}",
        "安装后用 type.resolveMissingFonts 复核（应用侧结论为准）"))


def audit_psd(psd, path, profile, installed, max_depth, reader_warnings):
    roots = to_nodes(psd)
    issues = psd_contract.structure_issues(roots, profile, max_depth)
    if not roots:
        issues = [dict(i, code="EMPTY_PSD") if i["code"] == "EMPTY_DOC" else i for i in issues]
    stats = {"total": 0, "leaves": 0, "groups": 0, "text": 0, "hidden": 0,
             "smartobjects": 0, "masks": 0, "maxDepth": 0}
    inventory = set()
    text_prefix = profile.prefix("text")

    def walk(nodes, ancestors):
        for node in nodes:
            layer = node.raw
            node_path = psd_contract.display_path(ancestors, node.name)
            depth = len(ancestors) + 1
            stats["total"] += 1
            stats["maxDepth"] = max(stats["maxDepth"], depth)
            if not node.visible:
                stats["hidden"] += 1
            try:
                if layer.has_mask():
                    stats["masks"] += 1
            except Exception:
                pass
            if node.kind == "group":
                stats["groups"] += 1
                walk(node.children, ancestors + [node.name])
                continue
            stats["leaves"] += 1
            if node.kind == "smartobject":
                stats["smartobjects"] += 1
            elif node.kind == "type":
                stats["text"] += 1
                for family, postscript, style in _layer_fonts(layer, node_path, issues):
                    inventory.add((family, postscript, style))
                    if installed is not None:
                        _check_font(family, postscript, installed, node_path, issues)
            elif node.kind == "pixel" and node.name.startswith(text_prefix):
                issues.append(psd_contract.make_issue(
                    "MEDIUM", "POSSIBLE_RASTERIZED_TEXT", node_path,
                    f"像素层用了文字前缀 {text_prefix}，可能是栅格化的文字",
                    "能重打就重打成文字层；确实是位图就改用图片前缀并在描述文件注明"))

    walk(roots, [])
    psd_contract.sort_issues(issues)
    counts = psd_contract.count_issues(issues)
    summary = dict(counts)
    summary["ok"] = not psd_contract.blocking(counts, False)
    summary["strictOk"] = not psd_contract.blocking(counts, True)
    return {
        "file": os.path.abspath(path),
        "profile": profile.to_json(),
        "size": list(psd.size),
        "colorMode": int(psd.color_mode),
        "depth": int(psd.depth),
        "stats": stats,
        "rootGroups": [n.name for n in roots if n.kind == "group"],
        "fonts": [{"family": f, "postscriptName": p, "style": s} for f, p, s in sorted(inventory)],
        "issues": issues,
        "summary": summary,
        "readerWarnings": list(reader_warnings),
    }


def audit_file(path, profile, installed, max_depth):
    from psd_tools import PSDImage
    collector = _Collector()
    logger = logging.getLogger("psd_tools")
    logger.addHandler(collector)
    propagate, logger.propagate = logger.propagate, False
    try:
        try:
            psd = PSDImage.open(path)
        except Exception as exc:
            raise RuntimeError(f"无法打开 PSD: {path}: {exc}") from exc
        return audit_psd(psd, path, profile, installed, max_depth, collector.messages)
    finally:
        logger.removeHandler(collector)
        logger.propagate = propagate


def _md(text):
    return str(text).replace("|", "\\|").replace("\n", " ")


def format_markdown(result):
    s, summary = result["stats"], result["summary"]
    fonts = ", ".join(f["postscriptName"] or f["family"] for f in result["fonts"]) or "无"
    lines = [
        f"# PSD audit: {result['file']}",
        "",
        f"- profile: {result['profile']['name']}；尺寸 {result['size'][0]}x{result['size'][1]}；"
        f"颜色模式 {result['colorMode']}；位深 {result['depth']}",
        f"- 总层数 {s['total']}；叶子 {s['leaves']}；组 {s['groups']}；文字 {s['text']}；"
        f"隐藏 {s['hidden']}；智能对象 {s['smartobjects']}；最大深度 {s['maxDepth']}",
        f"- 根组（面板自上而下）: {', '.join(result['rootGroups']) or '无'}",
        f"- 字体: {fonts}",
        "",
        "问题: CRITICAL {CRITICAL} / HIGH {HIGH} / MEDIUM {MEDIUM} / LOW {LOW}；严格模式: {s}".format(
            s="通过" if summary["strictOk"] else "未通过", **summary),
        "",
    ]
    if result["readerWarnings"]:
        lines += ["psd-tools 告警: " + "; ".join(result["readerWarnings"]), ""]
    if not result["issues"]:
        lines.append("未发现结构问题。")
    else:
        lines += ["| 级别 | 代码 | 路径 | 说明 | 建议 |", "| --- | --- | --- | --- | --- |"]
        for i in result["issues"]:
            lines.append(f"| {i['severity']} | {i['code']} | {_md(i['path'])} | "
                         f"{_md(i['message'])} | {_md(i['suggestion'])} |")
    return "\n".join(lines)


def compare_markdown(old, new):
    lines = [f"# PSD compare: {old['file']} -> {new['file']}", "",
             "| 指标 | 原稿 | 新稿 |", "| --- | --- | --- |"]
    for key in ("total", "leaves", "groups", "text", "hidden", "smartobjects", "maxDepth"):
        lines.append(f"| {key} | {old['stats'][key]} | {new['stats'][key]} |")
    for sev in psd_contract.SEVERITIES:
        lines.append(f"| {sev} | {old['summary'][sev]} | {new['summary'][sev]} |")
    lines += ["", f"原稿根组: {', '.join(old['rootGroups']) or '无'}",
              f"新稿根组: {', '.join(new['rootGroups']) or '无'}", "", "## 新稿审计", "",
              format_markdown(new)]
    return "\n".join(lines)


def main():
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, OSError):
            pass
    fmt = argparse.RawDescriptionHelpFormatter
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=fmt)
    sub = parser.add_subparsers(dest="cmd", required=True)

    def common(p):
        p.add_argument("--profile", default="zh", help="命名 profile: zh（默认）、en 或项目 JSON 路径")
        p.add_argument("--json", action="store_true", help="输出一行 JSON")
        p.add_argument("--strict", action="store_true", help="MEDIUM 也算失败（规范稿验收用）")
        p.add_argument("--installed-fonts", default=None, help="字体清单 JSON/JSONL（见上）")
        p.add_argument("--max-depth", type=int, default=0, help="嵌套深度上限；0 = 不限（默认）")

    a = sub.add_parser("audit", help="审计一个 PSD", description=__doc__, formatter_class=fmt)
    a.add_argument("psd")
    common(a)
    c = sub.add_parser("compare", help="审计并对比原稿与新稿（退出码看新稿）",
                       description=__doc__, formatter_class=fmt)
    c.add_argument("old")
    c.add_argument("new")
    common(c)
    args = parser.parse_args()

    def fail(message):
        if args.json:
            print(json.dumps({"error": message}, ensure_ascii=False))
        else:
            print(f"ERROR: {message}", file=sys.stderr)
        return EXIT_ERROR

    try:
        import psd_tools  # noqa: F401
    except ImportError:
        return fail("需要 psd-tools：pip install psd-tools")
    try:
        profile = psd_contract.load_profile(args.profile)
        installed = load_installed_fonts(args.installed_fonts)
        if args.cmd == "audit":
            result = audit_file(args.psd, profile, installed, args.max_depth)
            print(json.dumps(result, ensure_ascii=False) if args.json else format_markdown(result))
            gate = result["summary"]
        else:
            old = audit_file(args.old, profile, installed, args.max_depth)
            new = audit_file(args.new, profile, installed, args.max_depth)
            print(json.dumps({"old": old, "new": new}, ensure_ascii=False) if args.json
                  else compare_markdown(old, new))
            gate = new["summary"]
    except (OSError, RuntimeError, ValueError) as exc:
        return fail(str(exc))
    return EXIT_BLOCKED if psd_contract.blocking(gate, args.strict) else EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
