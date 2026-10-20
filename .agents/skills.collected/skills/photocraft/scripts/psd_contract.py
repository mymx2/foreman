"""psd_contract.py — PSD 命名与层级契约（库，只被 psd_audit.py / layout_design.py import，不单独运行）。

命名 profile（两个检查器都用 --profile 选，默认 zh）:
  zh    内置默认：页面_ 区块_ 组件_ 参考_ 版本_ + 文字_ 图标_ 图片_ 形状_ 效果_ 背景_
  en    内置：page_ section_ component_ ref_ version_ + text_ icon_ image_ shape_ effect_ bg_
  FILE  项目 profile（JSON），例如
          {"name": "acme", "extends": "en", "prefixes": {"background": "bkg_"}}
        不写 extends 时 11 个角色都要给。角色：page section component reference version
        text icon image shape effect background。前缀区分大小写，按 startswith 匹配，最长者胜。

层级矩阵（按角色，不按字面前缀）:
  根层       只允许 page / section / reference / version 组
  page       section、component、reference、元素
  section    section、component、reference、元素
  component  component、reference、元素
  reference  除 reference 以外的元素（参考组不嵌套）
  version    page、section、component、reference、元素
  元素 = text icon image shape effect background reference

默认名：PhotoCraft 0.10.0 新建层叫 "Layer N"、"Group N"、"Rectangle N"、"Curves N" 等（下表每一种都
实建后用 photocraft-cli info 读回过），复制层叫 "<名> copy" / "<名> copy N"，背景层叫 "Background"
（转普通层后 "Layer 0"）。文字层按内容命名，没有默认文字层名。
"""
import json
import os
import re

ROLES = ("page", "section", "component", "reference", "version",
         "text", "icon", "image", "shape", "effect", "background")
GROUP_ROLES = ("page", "section", "component", "reference", "version")
ELEMENT_ROLES = ("text", "icon", "image", "shape", "effect", "background", "reference")
ROOT_ROLES = ("page", "section", "reference", "version")
_ELEMENTS_NO_REF = tuple(r for r in ELEMENT_ROLES if r != "reference")
ALLOW_NESTED = {
    "page": ("section", "component", "reference") + ELEMENT_ROLES,
    "section": ("section", "component", "reference") + ELEMENT_ROLES,
    "component": ("component", "reference") + ELEMENT_ROLES,
    "reference": _ELEMENTS_NO_REF,
    "version": ("page", "section", "component", "reference") + ELEMENT_ROLES,
}

BUILTIN_PROFILES = {
    "zh": {"page": "页面_", "section": "区块_", "component": "组件_", "reference": "参考_",
           "version": "版本_", "text": "文字_", "icon": "图标_", "image": "图片_",
           "shape": "形状_", "effect": "效果_", "background": "背景_"},
    "en": {"page": "page_", "section": "section_", "component": "component_", "reference": "ref_",
           "version": "version_", "text": "text_", "icon": "icon_", "image": "image_",
           "shape": "shape_", "effect": "effect_", "background": "bg_"},
}

SEVERITIES = ("CRITICAL", "HIGH", "MEDIUM", "LOW")
SEVERITY_ORDER = {s: i for i, s in enumerate(SEVERITIES)}
MAX_SIBLINGS = 30

# Created live on photocraft-cli 0.10.0 and read back (layer.new.*, shape.create kinds,
# layer.newAdjustmentLayer.*, layer.newFillLayer.*, layer.new.artboard/frame, Background).
_PHOTOCRAFT_DEFAULTS = (
    "Layer", "Group", "Background", "Shape", "Rectangle", "Rounded Rectangle", "Ellipse",
    "Polygon", "Star", "Line", "Curves", "Levels", "Exposure", "Vibrance", "Invert",
    "Posterize", "Threshold", "Selective Color", "Channel Mixer", "Color Lookup",
    "Black & White", "Brightness/Contrast", "Hue/Saturation", "Color Balance", "Photo Filter",
    "Gradient Map", "Color Fill", "Gradient Fill", "Pattern Fill", "Artboard", "Frame",
)
# Other editors' defaults carried over from the source skill (not reproduced in PhotoCraft).
_OTHER_DEFAULTS = (
    "Text", "Smart Object", "Adjustment Layer", "Fill", "Curve", "Solid Color", "Gradient",
    "Pattern", "Path", "Untitled",
    "图层", "组", "背景", "文本", "文字图层", "形状", "智能对象", "调整图层", "填充", "矩形",
    "圆角矩形", "椭圆", "多边形", "星形", "直线", "曲线", "色阶", "曝光度", "自然饱和度", "反相",
    "色调分离", "阈值", "可选颜色", "通道混合器", "颜色查找", "黑白", "亮度/对比度",
    "色相/饱和度", "色彩平衡", "照片滤镜", "渐变映射", "颜色填充", "渐变填充", "图案填充",
    "纯色", "渐变", "图案", "路径", "画板", "画框", "新建", "未命名",
)
_DEFAULT_BASES = sorted(set(_PHOTOCRAFT_DEFAULTS + _OTHER_DEFAULTS), key=len, reverse=True)
DEFAULT_NAME_RE = re.compile(
    r"^(?:" + "|".join(re.escape(b) for b in _DEFAULT_BASES) + r")(?:\s*\d+)?$", re.I)
# PhotoCraft appends " copy" / " copy 2"; Photoshop zh appends " 拷贝" / "副本".
COPY_RE = re.compile(r"(?:\s+copy(?:\s+\d+)?|\s*(?:副本|拷贝)(?:\s*\d+)?)$", re.I)
PATH_CHAR_RE = re.compile(r'[\\/:*?"<>|\x00-\x1f]')


class ProfileError(ValueError):
    """Raised for an unknown profile name or an invalid profile file."""


class Profile:
    """A naming profile: role -> prefix."""

    def __init__(self, name, prefixes, source="builtin"):
        self.name = name
        self.prefixes = dict(prefixes)
        self.source = source
        self._by_length = sorted(((p, r) for r, p in self.prefixes.items()),
                                 key=lambda item: len(item[0]), reverse=True)

    def role(self, name):
        """Role of a layer name by its prefix (longest match), or None."""
        name = name or ""
        for prefix, role in self._by_length:
            if name.startswith(prefix):
                return role
        return None

    def prefix(self, role):
        return self.prefixes[role]

    def prefixes_for(self, roles):
        return "/".join(self.prefixes[r] for r in roles)

    def is_node_group(self, name):
        return self.role(name) in GROUP_ROLES

    def child_ok(self, parent_name, child_name):
        """Whether child_name may sit directly under parent_name (unknown parents pass)."""
        allowed = ALLOW_NESTED.get(self.role(parent_name))
        if allowed is None:
            return True
        return self.role(child_name) in allowed

    def hidden_allowed(self, ancestors, name):
        """Hidden content is allowed inside reference/version groups (or is one itself)."""
        keep = ("reference", "version")
        return any(self.role(a) in keep for a in ancestors) or self.role(name) in keep

    def to_json(self):
        return {"name": self.name, "source": self.source, "prefixes": self.prefixes}


def load_profile(spec="zh"):
    """Return a Profile for "zh", "en" or a JSON profile path."""
    spec = spec or "zh"
    if spec in BUILTIN_PROFILES:
        return Profile(spec, BUILTIN_PROFILES[spec])
    if not os.path.isfile(spec):
        raise ProfileError(f"未知 profile: {spec}（可选 zh、en，或项目 profile 的 JSON 文件路径）")
    try:
        with open(spec, encoding="utf-8-sig") as handle:
            data = json.load(handle)
    except (OSError, ValueError) as exc:
        raise ProfileError(f"profile 文件读取失败: {spec}: {exc}") from exc
    if not isinstance(data, dict):
        raise ProfileError("profile JSON 顶层必须是对象")
    unknown = sorted(set(data) - {"name", "extends", "prefixes", "description"})
    if unknown:
        raise ProfileError(f"profile 含未知字段: {', '.join(unknown)}")
    base = data.get("extends")
    if base is not None and base not in BUILTIN_PROFILES:
        raise ProfileError(f"extends 只能是 {'/'.join(BUILTIN_PROFILES)}: {base}")
    prefixes = dict(BUILTIN_PROFILES[base]) if base else {}
    given = data.get("prefixes", {})
    if not isinstance(given, dict):
        raise ProfileError("prefixes 必须是 {角色: 前缀} 对象")
    for role, prefix in given.items():
        if role not in ROLES:
            raise ProfileError(f"未知角色 {role}；可用: {', '.join(ROLES)}")
        if not isinstance(prefix, str) or not prefix or prefix != prefix.strip() \
                or PATH_CHAR_RE.search(prefix):
            raise ProfileError(f"角色 {role} 的前缀无效: {prefix!r}")
        prefixes[role] = prefix
    missing = [r for r in ROLES if r not in prefixes]
    if missing:
        raise ProfileError(f"profile 缺少角色: {', '.join(missing)}（或用 extends 继承 zh/en）")
    values = list(prefixes.values())
    dupes = sorted({p for p in values if values.count(p) > 1})
    if dupes:
        raise ProfileError(f"不同角色用了同一个前缀: {', '.join(dupes)}")
    name = data.get("name") or os.path.splitext(os.path.basename(spec))[0]
    return Profile(str(name), prefixes, os.path.abspath(spec))


def make_issue(severity, code, path, message, suggestion=""):
    return {"severity": severity, "code": code, "path": path,
            "message": message, "suggestion": suggestion}


def display_path(ancestors, name):
    return "/".join(list(ancestors) + [name if (name or "").strip() else "<empty>"])


def strip_copy_suffix(name):
    stripped = name.strip()
    while True:
        shorter = COPY_RE.sub("", stripped).strip()
        if shorter == stripped or not shorter:
            return shorter or stripped
        stripped = shorter


def name_issues(name, path):
    """Naming issues that do not depend on the profile."""
    found = []
    if not (name or "").strip():
        return [make_issue("HIGH", "EMPTY_NAME", path, "图层名为空", "按 profile 前缀命名")]
    if name != name.strip():
        found.append(make_issue("HIGH", "WHITESPACE_NAME", path, "名称含首尾空格", "去掉首尾空格"))
    base = strip_copy_suffix(name)
    if DEFAULT_NAME_RE.match(base):
        found.append(make_issue("HIGH", "DEFAULT_NAME", path, f"使用默认图层名: {name.strip()}",
                                "按 profile 前缀加语义命名"))
    elif COPY_RE.search(name.strip()):
        found.append(make_issue("MEDIUM", "COPY_NAME", path, "名称带 copy/拷贝/副本 后缀",
                                "用语义名或 _01/_02 区分"))
    if PATH_CHAR_RE.search(name):
        found.append(make_issue("LOW", "NAME_HAS_PATH_CHAR", path,
                                "名称含 \\ / : * ? \" < > | 或控制字符；导出文件名会被改写或拆成子目录",
                                "改用 - 或 _（Image Assets 规格名放在 _切图 副本里）"))
    return found


class Node:
    """Layer tree node shared by both checkers. children are in panel order (top first).

    kind: group | type | pixel | shape | smartobject | adjustment | fill | other
    """

    __slots__ = ("name", "kind", "visible", "children", "bounds", "text", "raw")

    def __init__(self, name, kind, visible=True, children=None, bounds=None, text=None, raw=None):
        self.name = name or ""
        self.kind = kind
        self.visible = visible is not False
        self.children = children or []
        self.bounds = bounds
        self.text = text
        self.raw = raw


def structure_issues(roots, profile, max_depth=0):
    """Profile-driven structure and naming issues for a layer tree (list of root Nodes)."""
    issues = []
    if not roots:
        issues.append(make_issue("CRITICAL", "EMPTY_DOC", "<root>", "文档没有图层",
                                 "确认文件没有损坏，或它只有合成图"))
        return issues
    root_list = profile.prefixes_for(ROOT_ROLES)
    for node in roots:
        path = display_path([], node.name)
        if node.kind != "group":
            issues.append(make_issue("HIGH", "ROOT_LOOSE_LAYER", path, "根层有未进组的图层",
                                     f"移入 {profile.prefix('component')} 或 "
                                     f"{profile.prefix('section')} 组"))
        elif profile.role(node.name) not in ROOT_ROLES:
            issues.append(make_issue("MEDIUM", "ROOT_UNKNOWN_GROUP", path,
                                     f"根组命名不合规（应以 {root_list} 开头）",
                                     "按 profile 的节点前缀改名"))

    def walk(children, ancestors, hidden_above, depth_flagged):
        prefix_path = "/".join(ancestors)
        if len(children) > MAX_SIBLINGS:
            issues.append(make_issue("LOW", "TOO_MANY_SIBLINGS", prefix_path or "<root>",
                                     f"同级图层/组超过 {MAX_SIBLINGS} 个", "按语义再分组"))
        seen = {}
        for node in children:
            name = node.name
            path = display_path(ancestors, name)
            depth = len(ancestors) + 1
            flagged = depth_flagged
            if max_depth > 0 and depth > max_depth and not depth_flagged:
                issues.append(make_issue("MEDIUM", "DEPTH_EXCEEDED", path,
                                         f"嵌套深度 {depth} 超过上限 {max_depth}", "合并或扁平化中间层"))
                flagged = True
            issues.extend(name_issues(name, path))
            key = name.strip().casefold()
            if key in seen:
                issues.append(make_issue("HIGH", "DUPLICATE_SIBLING_NAME", path,
                                         f"同一父级下重名（首次出现: {seen[key]}）", "用 _01/_02 区分"))
            else:
                seen[key] = path
            if ancestors and not profile.child_ok(ancestors[-1], name):
                issues.append(make_issue("MEDIUM", "NODE_PREFIX_MISMATCH", path,
                                         f"层级不符: {name} 不应直接放在 {ancestors[-1]} 下",
                                         "按 profile 的层级矩阵调整"))
            role = profile.role(name)
            if node.kind == "group":
                if role == "reference" and node.visible and not hidden_above:
                    issues.append(make_issue("MEDIUM", "REFERENCE_VISIBLE", path,
                                             "参考组可见（会进入最终合成）", "隐藏参考组"))
                if not node.children:
                    issues.append(make_issue("HIGH", "EMPTY_GROUP", path, "空组", "删除空组"))
                elif len(node.children) == 1 and role not in GROUP_ROLES:
                    issues.append(make_issue("MEDIUM", "SINGLE_CHILD_GROUP", path,
                                             "非节点组只有一个子层（冗余包装）", "确认是否需要，不需要就解组"))
            if not node.visible and not profile.hidden_allowed(ancestors, name):
                issues.append(make_issue("MEDIUM", "HIDDEN_OUTSIDE_REFERENCE", path,
                                         "隐藏层不在参考/版本组下",
                                         f"删除，或移入 {profile.prefix('reference')}/"
                                         f"{profile.prefix('version')} 组并登记"))
            if node.kind == "type" and not any(profile.is_node_group(a) for a in ancestors):
                issues.append(make_issue("MEDIUM", "TEXT_OUTSIDE_NODE_GROUP", path,
                                         "文字层不在任何节点组内", "移入组件/区块组"))
            if node.kind == "group":
                walk(node.children, ancestors + [name], hidden_above or not node.visible, flagged)
        # Background elements must form the bottom run of their container (panel order).
        names = [c.name for c in children]
        bg = [i for i, n in enumerate(names) if profile.role(n) == "background"]
        if bg and bg != list(range(len(names) - len(bg), len(names))):
            issues.append(make_issue("MEDIUM", "BACKGROUND_NOT_BOTTOM", prefix_path or "<root>",
                                     f"{profile.prefix('background')} 层不在组内最底部: {names}",
                                     f"把 {profile.prefix('background')}* 移到组内最下面"))

    walk(roots, [], False, False)
    return issues


def sort_issues(issues):
    issues.sort(key=lambda i: (SEVERITY_ORDER.get(i["severity"], 9), i["path"], i["code"]))
    return issues


def count_issues(issues):
    counts = {s: 0 for s in SEVERITIES}
    for item in issues:
        counts[item["severity"]] = counts.get(item["severity"], 0) + 1
    return counts


def blocking(counts, strict):
    """True when the counts fail the gate: CRITICAL/HIGH, plus MEDIUM under strict."""
    return bool(counts.get("CRITICAL") or counts.get("HIGH") or (strict and counts.get("MEDIUM")))
