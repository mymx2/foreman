"""psd_contract.py — PSD 节点树契约常量，供 psd-audit.py 与 layout-design.py 共用。

权威定义见 references/design-spec.md 第 3 节。修改契约只改这里，
两脚本自动同步，避免文档、校验器、常量三处漂移。
"""

# 根组必须以这些前缀之一开头
NODE_ROOT_PREFIXES = ("页面_", "区块_", "参考_", "版本_")

# 所有节点组前缀（含子节点 组件_）：用于判断「语义容器」豁免
NODE_GROUP_PREFIXES = ("页面_", "区块_", "组件_", "参考_", "版本_")

# 元素层命名前缀（强制）
ELEMENT_PREFIXES = ("文字_", "图标_", "图片_", "形状_", "效果_", "背景_", "参考_")

# 页面/版本包装组（内部再按 区块_/组件_ 组织）
PAGE_WRAPPER_PREFIXES = ("页面_", "版本_")

# 组件组可嵌套组件组（子组件）；区块组可嵌套区块组（嵌套布局）；
# 元素层可直接放在区块/组件/参考下（简单内容不需要组件包装）。
# 参考_ 是扁平容器：只放元素，不嵌套 参考_ 子组（矩阵 参考_→参考_ ✗）。
ELEMENT_NO_REF = tuple(p for p in ELEMENT_PREFIXES if p != "参考_")
ALLOW_NESTED = {
    "页面_": ("区块_", "组件_", "参考_") + ELEMENT_PREFIXES,
    "区块_": ("区块_", "组件_", "参考_") + ELEMENT_PREFIXES,
    "组件_": ("组件_", "参考_") + ELEMENT_PREFIXES,
    "参考_": ELEMENT_NO_REF,
    "版本_": ("页面_", "区块_", "组件_", "参考_") + ELEMENT_PREFIXES,
}


def is_node_root(name):
    return bool(name) and name.startswith(NODE_ROOT_PREFIXES)


def is_node_group(name):
    """节点组（语义容器）：页面/区块/组件/参考/版本。单元素是正常的。"""
    return bool(name) and name.startswith(NODE_GROUP_PREFIXES)


def is_page_wrapper(name):
    return bool(name) and name.startswith(PAGE_WRAPPER_PREFIXES)


def is_reference_or_version(name):
    return bool(name) and name.startswith(("参考_", "版本_"))


def hidden_allowed(ancestors, name):
    """隐藏内容允许在 参考_* 组内、或 版本_* 包装下（含根级）。"""
    for a in ancestors or []:
        if is_reference_or_version(a):
            return True
    return bool(is_reference_or_version(name))


def child_prefix_ok(parent_name, child_name):
    """子层前缀是否允许出现在父组下（见 ALLOW_NESTED）。"""
    if not parent_name:
        return True  # 根层由 ROOT_LOOSE_LAYER 单独管
    for prefix, allowed in ALLOW_NESTED.items():
        if parent_name.startswith(prefix):
            return any(child_name.startswith(p) for p in allowed)
    return True  # 未识别的父组前缀不在此拦截，由 ROOT_UNKNOWN_GROUP 管
