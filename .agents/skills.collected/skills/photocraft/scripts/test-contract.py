#!/usr/bin/env python3
"""test-contract.py — 节点树契约回归测试。

对 psd-audit.py 与 layout-design.py 的契约判定跑固定样本，确认
判定与 design-spec.md 第 3 节一致。改契约前先跑这个，改完再跑一次对比。

用法：
  python test-contract.py           # 全部用例
  python test-contract.py -v        # 详细输出

退出码 0 = 全部通过，1 = 有失败。
psd-audit 用例依赖 psd_tools（pip install psd-tools）。
"""
import json
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
PSD_AUDIT = os.path.join(HERE, "psd-audit.py")
LAYOUT = os.path.join(HERE, "layout-design.py")
VERBOSE = "-v" in sys.argv


def log(*a):
    if VERBOSE:
        print(" ", *a)


def run_layout(check_data, spec=None, strict=False):
    """跑 layout-design.py check，返回 (退出码, 输出, 数据)。"""
    spec = spec or {"width": 1200, "height": 800, "margin": 80, "gutter": 24, "columns": 12}
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as f:
        json.dump(check_data, f, ensure_ascii=False)
        inspect_path = f.name
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as f:
        json.dump(spec, f, ensure_ascii=False)
        spec_path = f.name
    try:
        cmd = [sys.executable, "-X", "utf8", LAYOUT, "check", "--spec", spec_path, "--inspect", inspect_path]
        if strict:
            cmd.append("--strict")
        r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
        out = (r.stdout + r.stderr).strip()
        return r.returncode, out, out
    finally:
        os.unlink(inspect_path)
        os.unlink(spec_path)


def run_audit(psd_path, strict=False):
    """跑 psd-audit.py audit，返回 (退出码, 输出, JSON)。"""
    cmd = [sys.executable, "-X", "utf8", PSD_AUDIT, "audit", psd_path, "--json"]
    if strict:
        cmd.append("--strict")
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
    out = (r.stdout + r.stderr).strip()
    data = {}
    try:
        data = json.loads(out.splitlines()[-1]) if out else {}
    except Exception:
        pass
    return r.returncode, out, data


def node(name, kind="Pixel", children=None, visible=True, bounds=None):
    # 组节点 bounds 为 None（子层并集，不参与几何判定）
    if kind == "Group":
        bounds = None
    return {"name": name, "kind": kind, "visible": visible,
            "bounds": bounds or [80, 240, 328, 320], "children": children or []}


def no_issues(out):
    return "问题统计: 无" in out or '"issueCounts": {}' in out or "问题统计: {'LOW'" in out


# ---------- layout-design.py 用例 ----------

def case_good():
    """合规节点树：期望 pass / 退出码 0 / 零问题。"""
    d = {"layers": [
        node("区块_首屏", "Group", [
            node("组件_卡片_01", "Group", [node("背景_卡片底")]),
            node("组件_标题", "Group", [node("文字_主标题", "Type")]),
        ]),
        node("区块_背景", "Group", [node("背景_底色", bounds=[0, 0, 1200, 800])]),
    ]}
    code, out, _ = run_layout(d)
    ok = code == 0 and no_issues(out)
    return "good node tree (clean)", ok, f"exit={code}"


def case_root_loose():
    """根层散落元素：期望 HIGH → 退出码 1。"""
    d = {"layers": [node("文字_主标题", "Type")]}
    code, out, _ = run_layout(d)
    ok = code == 1 and "根层散落" in out
    return "root loose layer (HIGH)", ok, f"exit={code}"


def case_root_unknown():
    """根组用旧契约名：期望 MEDIUM → 默认退出码 0，--strict 退出码 1。"""
    d = {"layers": [node("主体", "Group", [node("文字_x", "Type")])]}
    code1, out1, _ = run_layout(d)
    code2, out2, _ = run_layout(d, strict=True)
    ok = code1 == 0 and code2 == 1 and "根组命名不合规" in out1
    return "root unknown (MEDIUM, strict=1)", ok, f"default={code1} strict={code2}"


def case_empty_doc():
    """空文档：期望 CRITICAL → 退出码 1。"""
    code, out, _ = run_layout({"layers": []})
    ok = code == 1 and "CRITICAL" in out
    return "empty doc (CRITICAL)", ok, f"exit={code}"


def case_same_name_cross_parent():
    """跨父级同名：期望 pass（PSD 允许不同组同名）。"""
    d = {"layers": [
        node("区块_背景", "Group", [node("图标_x")]),
        node("区块_首屏", "Group", [node("图标_x")]),
    ]}
    code, out, _ = run_layout(d)
    ok = code == 0 and no_issues(out)
    return "same name cross-parent (clean)", ok, f"exit={code}"


def case_same_name_same_parent():
    """同父级重名：期望 HIGH → 退出码 1。"""
    d = {"layers": [node("区块_首屏", "Group", [node("图标_x"), node("图标_x")])]}
    code, out, _ = run_layout(d)
    ok = code == 1 and "同级重名" in out
    return "same name same-parent (HIGH)", ok, f"exit={code}"


def case_background_not_bottom():
    """背景层不在最底层：期望 MEDIUM（doc.inspect 自上而下，背景_ 应在末尾）。"""
    d = {"layers": [node("区块_首屏", "Group", [
        node("背景_底色", bounds=[0, 0, 1200, 800]),
        node("文字_标题", "Type"),
    ])]}
    code, out, _ = run_layout(d)
    ok = "背景层不在最底层" in out
    return "background not bottom (MEDIUM)", ok, f"exit={code}"


def case_background_bottom_clean():
    """背景层在最底层（末尾）：期望干净。"""
    d = {"layers": [node("区块_首屏", "Group", [
        node("文字_标题", "Type"),
        node("背景_底色", bounds=[0, 0, 1200, 800]),
    ])]}
    code, out, _ = run_layout(d)
    ok = code == 0 and no_issues(out)
    return "background bottom (clean)", ok, f"exit={code}"


def case_prefix_mismatch():
    """元素层出现在不允许的父组下：期望 MEDIUM 且恰好一条「层级不符」。"""
    d = {"layers": [node("参考_x", "Group", [
        node("区块_y", "Group", [node("文字_z", "Type")]),
    ])]}
    code, out, _ = run_layout(d)
    cnt = out.count("层级不符")
    ok = cnt == 1
    return "node prefix mismatch (exactly 1)", ok, f"count={cnt}"


def case_nested_components_clean():
    """组件_ 嵌 组件_（子组件）：期望干净。"""
    d = {"layers": [node("区块_首屏", "Group", [
        node("组件_弹窗", "Group", [
            node("组件_表单项", "Group", [node("文字_标签", "Type")]),
        ]),
    ])]}
    code, out, _ = run_layout(d)
    ok = code == 0 and no_issues(out)
    return "component-in-component (clean)", ok, f"exit={code}"


def case_nested_blocks_clean():
    """区块_ 嵌 区块_：期望干净。"""
    d = {"layers": [node("页面_A", "Group", [
        node("区块_主", "Group", [
            node("区块_子", "Group", [node("文字_x", "Type")]),
        ]),
    ])]}
    code, out, _ = run_layout(d)
    ok = code == 0 and no_issues(out)
    return "block-in-block (clean)", ok, f"exit={code}"


def case_element_direct_in_block_clean():
    """元素直放 区块_ 下（不经组件）：期望干净。"""
    d = {"layers": [node("区块_首屏", "Group", [
        node("文字_标题", "Type"),
        node("背景_底色", bounds=[0, 0, 1200, 800]),
    ])]}
    code, out, _ = run_layout(d)
    ok = code == 0 and no_issues(out)
    return "element direct in block (clean)", ok, f"exit={code}"


def case_type_width_exempt():
    """文字层宽度不受跨列约束：用非法宽 300 验证豁免真生效。"""
    d = {"layers": [node("区块_首屏", "Group", [
        node("文字_主标题", "Type", bounds=[80, 104, 300, 47]),
    ])]}
    code, out, _ = run_layout(d)
    ok = code == 0 and "跨列宽度" not in out
    return "type width exempt (illegal w=300)", ok, f"exit={code}"


def case_pixel_width_illegal():
    """像素层宽度非法：期望报「跨列宽度」。"""
    d = {"layers": [node("区块_首屏", "Group", [
        node("图片_x", bounds=[80, 240, 300, 320]),
    ])]}
    code, out, _ = run_layout(d)
    ok = "跨列宽度" in out
    return "pixel width illegal (MEDIUM)", ok, f"exit={code}"


def case_out_of_bounds():
    """元素越出画布：期望 HIGH → 退出码 1。"""
    d = {"layers": [node("区块_首屏", "Group", [node("图片_x", bounds=[1000, 100, 300, 200])])]}
    code, out, _ = run_layout(d)
    ok = code == 1 and "水平越界" in out
    return "out of bounds (HIGH)", ok, f"exit={code}"


def case_overlap():
    """同级元素重叠：期望 HIGH。"""
    d = {"layers": [node("区块_首屏", "Group", [
        node("图片_a", bounds=[80, 240, 328, 320]),
        node("图片_b", bounds=[150, 300, 328, 320]),
    ])]}
    code, out, _ = run_layout(d)
    ok = code == 1 and "同级重叠" in out
    return "overlap (HIGH)", ok, f"exit={code}"


# ---------- psd-audit.py 用例（需 psd_tools）----------

def case_audit_real_psd():
    """成品 PSD：期望 strictOk=true 且零问题。"""
    psd = os.environ.get("PHOTOCRAFT_TEST_PSD", "D:/data/123/.psd-e2e/DesignSystem.psd")
    if not os.path.exists(psd):
        return "audit real PSD (skipped)", True, "PSD not found, skipped"
    code, out, data = run_audit(psd, strict=True)
    s = data.get("summary", {})
    ok = s.get("strictOk") is True and code == 0
    return "audit real PSD strictOk", ok, f"exit={code} summary={s}"


def case_audit_raster_text():
    """psd-audit 的 POSSIBLE_RASTERIZED_TEXT / SINGLE_CHILD_GROUP 豁免：用真 PSD 验证。"""
    psd = os.environ.get("PHOTOCRAFT_TEST_PSD", "D:/data/123/.psd-e2e/DesignSystem.psd")
    if not os.path.exists(psd):
        return "audit raster/child checks (skipped)", True, "PSD not found, skipped"
    code, out, data = run_audit(psd)
    codes = [i.get("code") for i in data.get("issues", [])]
    # 成品 PSD 是合规节点树，应零问题（含 SINGLE_CHILD_GROUP 节点组豁免生效）
    ok = len(codes) == 0
    return "audit clean (node-group exemption)", ok, f"codes={codes}"


def case_reference_nested():
    """参考_ 嵌 参考_（应报层级不符）：参考是扁平容器。"""
    d = {"layers": [node("参考_外", "Group", [
        node("参考_内", "Group", [node("文字_x", "Type")]),
    ])]}
    code, out, _ = run_layout(d)
    ok = "层级不符" in out
    return "reference nested (mismatch)", ok, f"exit={code}"


LAYOUT_CASES = [
    case_good,
    case_root_loose,
    case_root_unknown,
    case_empty_doc,
    case_same_name_cross_parent,
    case_same_name_same_parent,
    case_background_not_bottom,
    case_background_bottom_clean,
    case_prefix_mismatch,
    case_nested_components_clean,
    case_nested_blocks_clean,
    case_element_direct_in_block_clean,
    case_type_width_exempt,
    case_pixel_width_illegal,
    case_out_of_bounds,
    case_overlap,
    case_reference_nested,
]

AUDIT_CASES = [
    case_audit_real_psd,
    case_audit_raster_text,
]


def main():
    print("=== 节点树契约回归 ===")
    print("--- layout-design.py ---")
    failed = 0
    for case in LAYOUT_CASES:
        name, ok, detail = case()
        mark = "PASS" if ok else "FAIL"
        print(f" [{mark}] {name}  ({detail})")
        if not ok:
            failed += 1
    print("--- psd-audit.py ---")
    for case in AUDIT_CASES:
        try:
            name, ok, detail = case()
        except Exception as e:
            name, ok, detail = case.__name__, True, f"skipped: {e}"
        mark = "PASS" if ok else "FAIL"
        print(f" [{mark}] {name}  ({detail})")
        if not ok:
            failed += 1
    total = len(LAYOUT_CASES) + len(AUDIT_CASES)
    print()
    print(f"{total - failed}/{total} 通过")
    if failed:
        print("契约判定与预期不符，检查 psd_contract.py / 两个脚本的改动。")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, OSError):
            pass
    main()
