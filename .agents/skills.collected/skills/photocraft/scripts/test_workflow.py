#!/usr/bin/env python3
"""test_workflow.py — psd_audit / layout_design / psd_compare / trim_export / fetch_asset 的自测。

自己用 photocraft-cli 造样本 PSD/PNG（不需要任何 PHOTOCRAFT_TEST_* 环境变量），在临时目录里跑完即删。

用法:
  python <skill-dir>/scripts/test_workflow.py [-v] [--allow-skip] [--keep] [--cli PATH] [-k 关键词]

覆盖:
  psd_audit      合规稿 --strict、栅格文字（只报文字前缀的像素层，不报形状/图片前缀）、--max-depth、
                 PhotoCraft 默认名、compare、--installed-fonts（家族清单 / faces / 缺字体）、en profile、
                 读不了的文件 = 退出码 2、psd-tools 告警不污染 stdout
  layout_design  calc（1440/1200/1920/1080/750、--snap none、--column-width）；check（合规稿、背景与内缩元素、
                 通栏、文字墨迹偏移、出界层、run 输出包裹、根组命名默认/--strict、空文档、同名、
                 同类重叠、缺 spec 字段、画布不符、--no-geometry、项目 profile）
  psd_compare    相同 / 改动 / 尺寸不同 / --fuzz / PNG 直比 / 真警告与预期警告分开 / 出错时清理临时目录
  trim_export    alpha / bg+容差 / padding / 多倍率 / 命名模板 / 拒绝情形 / 16-bit / manifest 字段
  fetch_asset    离线参数检查（不联网）
  所有脚本       --help 以 UTF-8 正常输出
退出码: 0 全部 PASS；1 有 FAIL，或有 SKIP 而没加 --allow-skip；2 找不到 photocraft-cli 或样本造不出来。
SKIP 只在缺 Pillow（psd_compare、trim_export 用例）或缺 psd-tools（psd_audit 用例）时出现。
子进程会去掉 PHOTOCRAFT_CONTROL_* 与 PHOTOCRAFT_AUTOMATION_*_ROOT，并把 PHOTOCRAFT_CONFIG_DIR 指到临时目录。
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from psd_compare import find_cli  # noqa: E402

SCRIPTS = ("psd_audit", "layout_design", "psd_compare", "trim_export", "fetch_asset")
STRIP_ENV = ("PHOTOCRAFT_CONTROL_PORT", "PHOTOCRAFT_CONTROL_TOKEN", "PHOTOCRAFT_CONTROL_TOKEN_FILE",
             "PHOTOCRAFT_AUTOMATION_READ_ROOT", "PHOTOCRAFT_AUTOMATION_WRITE_ROOT",
             "PEXELS_API_KEY", "PIXABAY_API_KEY")
SPEC = {"width": 1200, "height": 800, "margin": 80, "gutter": 24, "columns": 12}
ZH = {"section": "区块_首屏", "card": "组件_卡片_01", "title_c": "组件_标题", "bg_section": "背景_首屏",
      "bg_card": "背景_卡片底", "icon": "图标_箭头", "card_text": "文字_卡片标题", "title": "文字_主标题"}
EN = {"section": "section_hero", "card": "component_card_01", "title_c": "component_title",
      "bg_section": "bg_hero", "bg_card": "bg_card", "icon": "icon_arrow",
      "card_text": "text_card_title", "title": "text_headline"}


class Skip(Exception):
    pass


class SetupError(Exception):
    pass


def need(module, label):
    try:
        __import__(module)
    except ImportError as exc:
        raise Skip(f"缺 {label}") from exc


class Result:
    def __init__(self, proc):
        self.code, self.out, self.err = proc.returncode, proc.stdout, proc.stderr
        self.data = None
        try:
            self.data = json.loads(self.out)
        except ValueError:
            lines = [ln for ln in self.out.splitlines() if ln.strip()]
            if lines:
                try:
                    self.data = json.loads(lines[-1])
                except ValueError:
                    pass

    def issues(self, code=None):
        items = (self.data or {}).get("issues", []) if isinstance(self.data, dict) else []
        return [i for i in items if code is None or i.get("code") == code]

    def __str__(self):
        tail = (self.err or "").strip().splitlines()[-1:] if self.err else []
        return f"exit={self.code} stdout={self.out.strip()[:160]!r} stderr={tail}"


class Env:
    def __init__(self, cli, root, verbose):
        self.cli, self.root, self.verbose = cli, root, verbose
        self.env = {k: v for k, v in os.environ.items() if k not in STRIP_ENV}
        self.env["PHOTOCRAFT_CONFIG_DIR"] = self.path("cfg")
        self.env["PYTHONIOENCODING"] = "utf-8"
        os.makedirs(self.path("cfg"), exist_ok=True)
        self._built = {}

    def path(self, *parts):
        return os.path.join(self.root, *parts)

    def pc(self, *args):
        proc = subprocess.run([self.cli, *args], capture_output=True, text=True, encoding="utf-8",
                              errors="replace", env=self.env, timeout=300)
        if proc.returncode != 0:
            raise SetupError(f"photocraft-cli {' '.join(args[:2])} 失败: {proc.stderr.strip()[-300:]}")
        return proc

    def script(self, name, *args, env=None):
        proc = subprocess.run([sys.executable, os.path.join(HERE, f"{name}.py"), *map(str, args)],
                              capture_output=True, text=True, encoding="utf-8", errors="replace",
                              env=env or self.env, timeout=600)
        result = Result(proc)
        if self.verbose:
            print(f"      {name} {' '.join(map(str, args))[:120]} -> {result}")
        return result

    def write_json(self, name, data):
        path = self.path(name)
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(data, handle, ensure_ascii=False)
        return path

    def sample(self, name):
        if name not in self._built:
            self._built[name] = SAMPLES[name](self)
        return self._built[name]

    def build(self, out_name, new, steps):
        out = self.path(out_name)
        args = ["run", "--new", json.dumps(new)]
        for cmd, params in steps:
            args += ["--cmd", cmd]
            if params is not None:
                args += ["--params", json.dumps(params, ensure_ascii=False)]
        self.pc(*args, "--out", out)
        return out

    def info(self, psd, name=None):
        out = self.path(name or os.path.basename(psd) + ".info.json")
        if out not in self._built.values():
            proc = self.pc("info", psd, "--compact")
            with open(out, "w", encoding="utf-8") as handle:
                handle.write(proc.stdout)
            self._built["info:" + out] = out
        return out


# ------------------------------------------------------------------ samples

def select(names):
    steps = []
    for i, name in enumerate(names):
        steps.append(("layer.select", {"name": name} if i == 0 else {"name": name, "mode": "add"}))
    return steps


def page_steps(n, card_extra=(), card_extra_names=(), section_extra=(), section_extra_names=(),
               before_delete=()):
    return [
        ("shape.create", {"kind": "rect", "rect": [0, 0, 1200, 800], "fill": "#f1f5f9",
                          "name": n["bg_section"]}),
        ("shape.create", {"kind": "rect", "rect": [80, 240, 328, 320], "fill": "#ffffff",
                          "name": n["bg_card"]}),
        ("shape.create", {"kind": "rect", "rect": [96, 256, 64, 64], "fill": "#2563eb",
                          "name": n["icon"]}),
        ("type.create", {"box": [96, 344, 296, 64], "text": "Card title", "size": 24,
                         "name": n["card_text"]}),
        *card_extra,
        *select([n["bg_card"], n["icon"], n["card_text"], *card_extra_names]),
        ("layer.groupLayers", {"name": n["card"]}),
        ("type.create", {"box": [80, 104, 600, 80], "text": "Hello Layout", "size": 48,
                         "name": n["title"]}),
        ("layer.groupLayers", {"name": n["title_c"]}),
        *section_extra,
        *select([n["title_c"], n["card"], *section_extra_names, n["bg_section"]]),
        ("layer.groupLayers", {"name": n["section"]}),
        *before_delete,
        ("layer.delete", {"layer": "Background"}),
    ]


PAGE = {"width": 1200, "height": 800}
RASTER_EXTRA = [
    ("shape.create", {"kind": "rect", "rect": [80, 600, 1032, 96], "fill": "#e2e8f0",
                      "name": "背景_标题栏"}),
    ("layer.new.layer", {"name": "图片_栅格文字"}),
    ("paint.stroke", {"points": [[120, 640], [300, 640]], "size": 8, "color": "#334155"}),
    ("layer.new.layer", {"name": "文字_栅格"}),
    ("paint.stroke", {"points": [[120, 670], [300, 670]], "size": 8, "color": "#334155"}),
    *select(["背景_标题栏", "图片_栅格文字", "文字_栅格"]),
    ("layer.groupLayers", {"name": "组件_标题栏"}),
]
SAMPLES = {
    "compliant": lambda e: e.build("compliant.psd", PAGE, page_steps(ZH)),
    "compliant_copy": lambda e: (e.pc("run", e.sample("compliant"), "--out", e.path("compliant_copy.pcraft")),
                                 e.path("compliant_copy.pcraft"))[1],
    "en": lambda e: e.build("en.psd", PAGE, page_steps(EN)),
    "raster": lambda e: e.build("raster.psd", PAGE, page_steps(
        ZH, section_extra=RASTER_EXTRA, section_extra_names=["组件_标题栏"])),
    "curves": lambda e: e.build("curves.psd", PAGE, page_steps(
        ZH, card_extra=[("layer.newAdjustmentLayer.curves", {"points": [[0, 0], [128, 150], [255, 255]]}),
                        ("layer.renameLayer", {"name": "效果_曲线"})],
        card_extra_names=["效果_曲线"])),
    "badroot": lambda e: e.build("badroot.psd", PAGE, page_steps(
        ZH, before_delete=[("layer.renameLayer", {"layer": ZH["section"], "name": "主体"})])),
    "defaults": lambda e: e.build("defaults.psd", {"width": 400, "height": 300}, [
        ("layer.new.layer", None), ("layer.new.group", None),
        ("shape.create", {"kind": "rect", "rect": [10, 10, 50, 50]}),
        ("layer.newAdjustmentLayer.curves", None), ("layer.duplicate", None),
        ("shape.create", {"kind": "rect", "rect": [70, 10, 50, 50], "name": "图标_箭头 拷贝"}),
    ]),
    "size801": lambda e: e.build("size801.psd", {"width": 1200, "height": 801}, []),
    "grey80": lambda e: e.build("grey80.psd", {"width": 64, "height": 64, "background": "#808080"}, []),
    "grey83": lambda e: e.build("grey83.psd", {"width": 64, "height": 64, "background": "#838383"}, []),
    "nofont": lambda e: e.build("nofont.psd", {"width": 120, "height": 40}, [
        ("type.create", {"x": 4, "y": 30, "text": "Hi", "size": 20, "font": "NoSuchFontXYZ",
                         "name": "文字_缺字体"})]),
    "nofont_copy": lambda e: (e.pc("run", e.sample("nofont"), "--out", e.path("nofont_copy.pcraft")),
                              e.path("nofont_copy.pcraft"))[1],
    "alpha_png": lambda e: e.build("alpha.png", {"width": 200, "height": 160, "background": "transparent"}, [
        ("shape.create", {"kind": "rect", "rect": [50, 40, 80, 60], "fill": "#2563eb"})]),
    "bg_png": lambda e: e.build("bg.png", {"width": 200, "height": 150, "background": "white"}, [
        ("shape.create", {"kind": "rect", "rect": [30, 20, 140, 110], "fill": "#fbfbfb"}),
        ("shape.create", {"kind": "rect", "rect": [75, 55, 50, 40], "fill": "#333333"})]),
    "deep16_png": lambda e: e.build("deep16.png", {"width": 32, "height": 32, "depth": 16}, []),
}


def info_of(env, sample):
    return env.info(env.sample(sample))


def spec_file(env, **extra):
    return env.write_json(f"spec_{abs(hash(json.dumps(extra, sort_keys=True)))}.json", dict(SPEC, **extra))


def manifest_outputs(directory):
    with open(os.path.join(directory, "assets-manifest.json"), encoding="utf-8") as handle:
        return json.load(handle)["outputs"]


def image_size(path):
    from PIL import Image
    with Image.open(path) as im:
        return im.size


# ------------------------------------------------------------------ psd_audit

def t_audit_compliant(env):
    need("psd_tools", "psd-tools")
    r = env.script("psd_audit", "audit", env.sample("compliant"), "--strict", "--json")
    s = (r.data or {}).get("summary", {})
    return r.code == 0 and s.get("strictOk") is True and not r.issues(), str(r)


def t_audit_raster(env):
    need("psd_tools", "psd-tools")
    r = env.script("psd_audit", "audit", env.sample("raster"), "--json")
    paths = [i["path"] for i in r.issues("POSSIBLE_RASTERIZED_TEXT")]
    strict = env.script("psd_audit", "audit", env.sample("raster"), "--json", "--strict")
    ok = paths == ["区块_首屏/组件_标题栏/文字_栅格"] and r.code == 0 and strict.code == 1
    return ok, f"flagged={paths} default={r.code} strict={strict.code}"


def t_audit_depth(env):
    need("psd_tools", "psd-tools")
    r = env.script("psd_audit", "audit", env.sample("compliant"), "--json", "--max-depth", "1", "--strict")
    plain = env.script("psd_audit", "audit", env.sample("compliant"), "--json")
    ok = bool(r.issues("DEPTH_EXCEEDED")) and r.code == 1 and not plain.issues("DEPTH_EXCEEDED")
    return ok, f"depth issues={len(r.issues('DEPTH_EXCEEDED'))} strict={r.code}"


def t_audit_defaults(env):
    need("psd_tools", "psd-tools")
    r = env.script("psd_audit", "audit", env.sample("defaults"), "--json")
    flagged = sorted(i["path"].split("/")[-1] for i in r.issues("DEFAULT_NAME"))
    want = sorted(["Background", "Layer 1", "Group 1", "Rectangle 1", "Curves 1", "Curves 1 copy"])
    copies = [i["path"] for i in r.issues("COPY_NAME")]
    ok = flagged == want and copies == ["图标_箭头 拷贝"] and r.code == 1
    return ok, f"default={flagged} copy={copies} exit={r.code}"


def t_audit_compare(env):
    need("psd_tools", "psd-tools")
    r = env.script("psd_audit", "compare", env.sample("defaults"), env.sample("compliant"), "--json", "--strict")
    d = r.data or {}
    ok = r.code == 0 and d.get("new", {}).get("summary", {}).get("strictOk") is True \
        and d.get("old", {}).get("summary", {}).get("HIGH", 0) > 0
    back = env.script("psd_audit", "compare", env.sample("compliant"), env.sample("raster"), "--json", "--strict")
    return ok and back.code == 1, f"forward={r.code} backward={back.code}"


def t_audit_fonts(env):
    need("psd_tools", "psd-tools")
    fams = env.path("families.jsonl")
    with open(fams, "w", encoding="utf-8") as handle:
        handle.write(env.pc("run", "--new", '{"width":8,"height":8}', "--cmd", "type.fonts").stdout)
    faces = env.path("faces.jsonl")
    with open(faces, "w", encoding="utf-8") as handle:
        handle.write(env.pc("run", "--new", '{"width":8,"height":8}', "--cmd", "type.fonts",
                            "--params", '{"family":"Inter"}').stdout)
    missing = env.write_json("otherfont.json", ["SomeOtherFont"])
    a = env.script("psd_audit", "audit", env.sample("compliant"), "--json", "--installed-fonts", fams)
    b = env.script("psd_audit", "audit", env.sample("compliant"), "--json", "--installed-fonts", faces)
    c = env.script("psd_audit", "audit", env.sample("compliant"), "--json", "--installed-fonts", missing)
    ok = (a.code == 0 and not a.issues("FONT_NOT_INSTALLED") and len(a.issues("FONT_FAMILY_ONLY")) == 2
          and b.code == 0 and not b.issues()
          and c.code == 1 and len(c.issues("FONT_NOT_INSTALLED")) == 2)
    return ok, (f"families: exit {a.code} lows {len(a.issues('FONT_FAMILY_ONLY'))}; faces: exit {b.code} "
                f"issues {len(b.issues())}; other: exit {c.code} highs {len(c.issues('FONT_NOT_INSTALLED'))}")


def t_audit_profiles(env):
    need("psd_tools", "psd-tools")
    en = env.script("psd_audit", "audit", env.sample("en"), "--json", "--strict", "--profile", "en")
    zh = env.script("psd_audit", "audit", env.sample("en"), "--json")
    bad = env.write_json("bad_profile.json", {"extends": "en", "prefixes": {"bogus": "x_"}})
    err = env.script("psd_audit", "audit", env.sample("en"), "--json", "--profile", bad)
    ok = en.code == 0 and not en.issues() and bool(zh.issues("ROOT_UNKNOWN_GROUP")) and err.code == 2
    return ok, f"en={en.code}/{len(en.issues())} zh-root={len(zh.issues('ROOT_UNKNOWN_GROUP'))} badprofile={err.code}"


def t_audit_unreadable(env):
    need("psd_tools", "psd-tools")
    fake = env.path("not_a.psd")
    with open(fake, "w", encoding="utf-8") as handle:
        handle.write("not a psd")
    r = env.script("psd_audit", "audit", fake, "--json")
    return r.code == 2 and "error" in (r.data or {}), str(r)


def t_audit_reader_warnings(env):
    need("psd_tools", "psd-tools")
    r = env.script("psd_audit", "audit", env.sample("curves"), "--json", "--strict")
    d = r.data or {}
    ok = r.code == 0 and d.get("summary", {}).get("strictOk") is True and "CurvesExtraMarker" not in r.err
    return ok, f"exit={r.code} readerWarnings={d.get('readerWarnings')} stderr-clean={'CurvesExtraMarker' not in r.err}"


# ------------------------------------------------------------------ layout_design: calc

def t_calc_rows(env):
    rows = [((1440, 120, 24, 12), 72, 96, 72), ((1200, 80, 24, 12), 64, 88, 8),
            ((1920, 80, 24, 12), 120, 144, 56), ((1080, 16, 16, 4), 248, 264, 8),
            ((750, 16, 16, 4), 160, 176, 30), ((1200, 80, 20, 12), 68, 88, 4)]
    bad = []
    for (w, m, g, c), col, pitch, rem in rows:
        r = env.script("layout_design", "calc", "--width", w, "--margin", m, "--gutter", g, "--columns", c, "--json")
        d = r.data or {}
        if (d.get("columnWidth"), d.get("pitch"), d.get("remainderRight")) != (col, pitch, rem) \
                or not d.get("pitchOn8pt"):
            bad.append((w, m, g, c, d.get("columnWidth"), d.get("pitch"), d.get("remainderRight")))
    r = env.script("layout_design", "calc", "--width", 1440, "--margin", 120, "--gutter", 24, "--columns", 12, "--json")
    d = r.data or {}
    ok8 = d.get("allOn8pt") is True and d.get("columnX", [None, None])[1] == 216 \
        and d.get("guideLayoutParams") == {"columns": 12, "width": 72, "gutter": 24, "margin": 120}
    spans = env.script("layout_design", "calc", "--width", 1200, "--json").data or {}
    ok_spans = list((spans.get("legalColumnSpans") or {}).values())[:4] == [64, 152, 240, 328]
    return not bad and ok8 and ok_spans, f"bad={bad} 1440-on8pt={ok8} spans={ok_spans}"


def t_calc_modes(env):
    a = env.script("layout_design", "calc", "--width", 1440, "--margin", 120, "--gutter", 24,
                   "--columns", 12, "--snap", "none", "--json").data or {}
    b = env.script("layout_design", "calc", "--width", 1200, "--column-width", 60, "--json").data or {}
    c = env.script("layout_design", "calc", "--width", 1200, "--column-width", 90)
    d = env.script("layout_design", "calc", "--width", 100, "--margin", 10, "--gutter", 10, "--columns", 12)
    text = env.script("layout_design", "calc", "--width", 1440, "--margin", 120, "--gutter", 24, "--columns", 12)
    ok = (a.get("columnWidth") == 78 and a.get("pitch") == 102 and a.get("pitchOn8pt") is False
          and b.get("columnWidth") == 60 and b.get("snap") == "explicit" and c.code == 2 and d.code == 2
          and "--snap none" in text.out)
    return ok, f"none={a.get('columnWidth')}/{a.get('pitch')} explicit={b.get('columnWidth')} too-wide={c.code} narrow={d.code}"


# ------------------------------------------------------------------ layout_design: check

def check(env, inspect, *extra, spec=None):
    args = ["check", "--inspect", inspect, "--json"]
    args += ["--spec", spec] if spec else []
    return env.script("layout_design", *args, *extra)


def t_check_compliant(env):
    r = check(env, info_of(env, "compliant"), "--strict", spec=spec_file(env))
    return r.code == 0 and not r.issues() and (r.data or {}).get("geometryChecked") is True, str(r)


def t_check_opt_in(env):
    spec = spec_file(env, gridRoles=["section", "component", "text", "icon"])
    r = check(env, info_of(env, "compliant"), spec=spec)
    flagged = sorted({i["path"].split("/")[-1] for i in r.issues("GRID_X")})
    ok = flagged == ["图标_箭头", "文字_卡片标题"] and r.code == 0
    return ok, f"GRID_X on {flagged} (文字_主标题 x=84 at 48pt must pass)"


def t_check_moved(env):
    moved = env.path("moved.jsonl")
    proc = env.pc("run", env.sample("compliant"),
                  "--cmd", "layer.translate", "--params", json.dumps({"layer": ZH["card"], "dx": 5, "dy": 0}),
                  "--cmd", "layer.translate", "--params", json.dumps({"layer": ZH["icon"], "dx": 3000, "dy": 0}),
                  "--cmd", "document.inspect")
    with open(moved, "w", encoding="utf-8") as handle:
        handle.write(proc.stdout)
    r = check(env, moved, spec=spec_file(env))
    strict = check(env, moved, "--strict", spec=spec_file(env))
    codes = sorted(i["code"] for i in r.issues())
    ok = r.code == 0 and strict.code == 1 and "ZERO_SIZE" in codes and "GRID_X" in codes \
        and not any(i["severity"] in ("HIGH", "CRITICAL") for i in r.issues())
    return ok, f"codes={codes} default={r.code} strict={strict.code}"


def t_check_envelope(env):
    raw = env.path("raw_inspect.jsonl")
    with open(raw, "w", encoding="utf-8") as handle:
        handle.write(env.pc("run", env.sample("compliant"), "--cmd", "document.inspect").stdout)
    serve_like = env.path("serve_reply.json")
    with open(info_of(env, "compliant"), encoding="utf-8") as handle:
        doc = json.load(handle)
    env.write_json("serve_reply.json", {"id": 3, "ok": True, "result": doc})
    a = check(env, raw, spec=spec_file(env))
    b = check(env, serve_like, spec=spec_file(env))
    ok = a.code == 0 and b.code == 0 and (a.data or {}).get("layerCount") == 8 == (b.data or {}).get("layerCount")
    return ok, f"run-line={a.code}/{(a.data or {}).get('layerCount')} serve={b.code}/{(b.data or {}).get('layerCount')}"


def t_check_badroot(env):
    inspect = info_of(env, "badroot")
    a = check(env, inspect, spec=spec_file(env))
    b = check(env, inspect, "--strict", spec=spec_file(env))
    return a.code == 0 and b.code == 1 and bool(a.issues("ROOT_UNKNOWN_GROUP")), f"default={a.code} strict={b.code}"


def node(name, kind="Pixel", children=None, bounds=None, visible=True):
    return {"name": name, "kind": kind, "visible": visible,
            "bounds": None if kind == "Group" else (bounds or [80, 240, 328, 320]),
            "children": children or []}


def t_check_synthetic(env):
    spec = spec_file(env)
    cases = {
        "empty": ({"layers": []}, lambda r: r.code == 1 and bool(r.issues("EMPTY_DOC"))),
        "cross-parent": ({"layers": [node("区块_甲", "Group", [node("图标_x", bounds=[80, 0, 64, 64])]),
                                     node("区块_乙", "Group", [node("图标_x", bounds=[80, 100, 64, 64])])]},
                         lambda r: r.code == 0 and not r.issues("DUPLICATE_SIBLING_NAME")),
        "same-parent": ({"layers": [node("区块_甲", "Group", [node("图标_x"), node("图标_x")])]},
                        lambda r: r.code == 1 and bool(r.issues("DUPLICATE_SIBLING_NAME"))),
        "overlap": ({"layers": [node("区块_甲", "Group", [
            node("图片_a", bounds=[80, 240, 328, 320]), node("图片_b", bounds=[256, 300, 328, 320])])]},
            lambda r: r.code == 0 and len(r.issues("SAME_KIND_OVERLAP")) == 1),
        "bg-not-bottom": ({"layers": [node("区块_甲", "Group", [
            node("背景_底", bounds=[0, 0, 1200, 800]), node("图标_x", bounds=[80, 80, 64, 64])])]},
            lambda r: bool(r.issues("BACKGROUND_NOT_BOTTOM"))),
        "nested-ok": ({"layers": [node("页面_A", "Group", [node("区块_主", "Group", [
            node("组件_弹窗", "Group", [node("组件_表单", "Group", [node("图标_y", bounds=[80, 80, 64, 64])])])])])]},
            lambda r: r.code == 0 and not r.issues()),
        "ref-nesting": ({"layers": [node("参考_外", "Group", [node("参考_内", "Group", [node("图片_x")])])]},
                        lambda r: len(r.issues("NODE_PREFIX_MISMATCH")) == 1 and len(r.issues("REFERENCE_VISIBLE")) == 2),
        "defaults": ({"layers": [node("区块_甲", "Group", [node("图层 3"), node("Layer 3"), node("组 3", "Group", [node("图片_q")]),
                                                         node("Rounded Rectangle 2"), node("Black & White 1", "Adjustment")])]},
                     lambda r: r.code == 1 and len(r.issues("DEFAULT_NAME")) == 5),
    }
    bad = []
    for label, (doc, judge) in cases.items():
        r = check(env, env.write_json(f"syn_{label}.json", doc), spec=spec)
        if not judge(r):
            bad.append(f"{label}: {r}")
    return not bad, "; ".join(bad) or f"{len(cases)} synthetic cases"


def t_check_spec_errors(env):
    inspect = info_of(env, "compliant")
    no_height = env.write_json("spec_noh.json", {k: v for k, v in SPEC.items() if k != "height"})
    narrow = env.write_json("spec_narrow.json", {"width": 1200, "height": 800, "margin": 590, "gutter": 10, "columns": 12})
    other = env.write_json("spec_other.json", dict(SPEC, width=1440))
    a = check(env, inspect, spec=no_height)
    b = check(env, inspect, spec=narrow)
    c = check(env, inspect, spec=other)
    d = env.script("layout_design", "check", "--inspect", inspect)
    e = env.script("layout_design", "check", "--inspect", inspect, "--no-geometry", "--json")
    ok = (a.code == 2 and "height" in (a.data or {}).get("error", "") and b.code == 2 and c.code == 2
          and d.code == 2 and e.code == 0 and (e.data or {}).get("geometryChecked") is False)
    return ok, f"no-height={a.code} narrow={b.code} canvas-mismatch={c.code} no-spec={d.code} no-geometry={e.code}"


def t_check_profiles(env):
    inspect = info_of(env, "en")
    en = check(env, inspect, "--profile", "en", "--strict", spec=spec_file(env))
    zh = check(env, inspect, spec=spec_file(env))
    with open(inspect, encoding="utf-8") as handle:
        doc = json.loads(handle.read().replace('"bg_', '"bkg_'))
    custom_inspect = env.write_json("custom.info.json", doc)
    profile = env.write_json("acme_profile.json", {"name": "acme", "extends": "en", "prefixes": {"background": "bkg_"}})
    custom = check(env, custom_inspect, "--profile", profile, "--strict", spec=spec_file(env))
    en_on_custom = check(env, custom_inspect, "--profile", "en", spec=spec_file(env))
    ok = (en.code == 0 and not en.issues() and bool(zh.issues("ROOT_UNKNOWN_GROUP")) and custom.code == 0
          and not custom.issues() and bool(en_on_custom.issues("NODE_PREFIX_MISMATCH")))
    return ok, f"en={en.code} zh-root={len(zh.issues('ROOT_UNKNOWN_GROUP'))} custom={custom.code} en-on-custom={len(en_on_custom.issues())}"


# ------------------------------------------------------------------ psd_compare

def t_compare_identical(env):
    need("PIL", "Pillow")
    r = env.script("psd_compare", env.sample("compliant"), env.sample("compliant_copy"), "--cli", env.cli)
    d = r.data or {}
    ok = (r.code == 0 and d.get("result") == "identical" and d.get("warnings") == []
          and len(d.get("expectedWarnings", [])) == 2 and d.get("tempCleaned") is True)
    return ok, f"{r} expected={d.get('expectedWarnings')}"


def t_compare_changed(env):
    need("PIL", "Pillow")
    out = env.path("cmp_changed")
    r = env.script("psd_compare", env.sample("compliant"), env.sample("raster"), "--out", out, "--cli", env.cli)
    d = r.data or {}
    ok = r.code == 1 and d.get("result") == "differs" and d.get("differingPixels", 0) > 0 \
        and os.path.isfile(d.get("diffImage") or "")
    again = env.script("psd_compare", env.sample("compliant"), env.sample("raster"), "--out", out, "--cli", env.cli)
    over = env.script("psd_compare", env.sample("compliant"), env.sample("raster"), "--out", out,
                      "--overwrite", "--cli", env.cli)
    return ok and again.code == 2 and over.code == 1, f"{r}; reuse={again.code} overwrite={over.code}"


def t_compare_size(env):
    need("PIL", "Pillow")
    r = env.script("psd_compare", env.sample("compliant"), env.sample("size801"), "--cli", env.cli)
    d = r.data or {}
    ok = r.code == 1 and d.get("reason") == "size" and "diffImage" not in d and d.get("tempKept") is True
    if d.get("out"):
        shutil.rmtree(d["out"], ignore_errors=True)
    return ok, str(r)


def t_compare_fuzz(env):
    need("PIL", "Pillow")
    a, b = env.sample("grey80"), env.sample("grey83")
    results = {f: env.script("psd_compare", a, b, "--fuzz", f, "--cli", env.cli) for f in (0, 2, 3)}
    for r in results.values():
        if (r.data or {}).get("tempKept"):
            shutil.rmtree(r.data["out"], ignore_errors=True)
    codes = {f: r.code for f, r in results.items()}
    delta = (results[2].data or {}).get("maxChannelDelta")
    return codes == {0: 1, 2: 1, 3: 0} and delta == 3, f"codes={codes} maxChannelDelta={delta}"


def t_compare_png(env):
    need("PIL", "Pillow")
    p1, p2, p3 = env.path("c1.png"), env.path("c2.png"), env.path("c3.png")
    env.pc("convert", env.sample("compliant"), p1)
    env.pc("convert", env.sample("compliant_copy"), p2)
    env.pc("convert", env.sample("raster"), p3)
    same = env.script("psd_compare", p1, p2)
    diff = env.script("psd_compare", p1, p3, "--out", env.path("cmp_png"))
    old, new = env.path("cmp_png", "old.png"), env.path("cmp_png", "new.png")

    def read(path):
        with open(path, "rb") as fh:
            return fh.read()

    copied = (os.path.exists(old) and os.path.exists(new)
              and read(old) == read(p1) and read(new) == read(p3))
    ok = same.code == 0 and (same.data or {}).get("log") == [] and diff.code == 1 and copied
    return ok, f"same={same.code} differs={diff.code} copied={copied}"


def t_compare_warnings(env):
    need("PIL", "Pillow")
    r = env.script("psd_compare", env.sample("nofont"), env.sample("nofont_copy"), "--cli", env.cli)
    d = r.data or {}
    real = d.get("warnings", [])
    ok = r.code == 0 and len(real) == 1 and "not installed" in real[0] and len(d.get("expectedWarnings", [])) == 2
    return ok, f"warnings={real} expected={len(d.get('expectedWarnings', []))}"


def t_compare_guards(env):
    need("PIL", "Pillow")
    same = env.script("psd_compare", env.sample("compliant"), env.sample("compliant"))
    fuzz = env.script("psd_compare", env.sample("compliant"), env.sample("raster"), "--fuzz", 300)
    probe = env.path("tmp_probe")
    os.makedirs(probe, exist_ok=True)
    child = dict(env.env, TMP=probe, TEMP=probe, TMPDIR=probe)
    broken = env.script("psd_compare", env.sample("compliant"), env.sample("raster"), "--cli", sys.executable,
                        env=child)
    leftovers = os.listdir(probe)
    ok = same.code == 2 and fuzz.code == 2 and broken.code == 2 and \
        (broken.data or {}).get("result") == "error" and leftovers == []
    return ok, f"same-file={same.code} fuzz300={fuzz.code} broken-cli={broken.code} leftovers={leftovers}"


# ------------------------------------------------------------------ trim_export

def trim(env, *args):
    return env.script("trim_export", *args)


def t_trim_alpha(env):
    need("PIL", "Pillow")
    out = env.path("t_alpha")
    r = trim(env, env.sample("alpha_png"), "--out", out, "--trim", "alpha")
    entry = manifest_outputs(out)[0] if r.code == 0 else {}
    ok = (r.code == 0 and image_size(os.path.join(out, "alpha.png")) == (80, 60)
          and entry.get("trimBoxXYWH") == [50, 40, 80, 60] and entry.get("sourceHasAlpha") is True
          and entry.get("sourceAlphaBoxXYWH") == [50, 40, 80, 60] and entry.get("contentTransparentRatio") == 0.0)
    again = trim(env, env.sample("alpha_png"), "--out", out, "--trim", "alpha")
    forced = trim(env, env.sample("alpha_png"), "--out", out, "--trim", "alpha", "--overwrite")
    return ok and again.code == 1 and forced.code == 0, f"{r}; rerun={again.code} overwrite={forced.code}"


def t_trim_bg(env):
    need("PIL", "Pillow")
    sizes = {}
    for tol in (8, 2):
        out = env.path(f"t_bg{tol}")
        r = trim(env, env.sample("bg_png"), "--out", out, "--trim", "bg", "--bg-color", "#ffffff",
                 "--tolerance", tol)
        sizes[tol] = image_size(os.path.join(out, "bg.png")) if r.code == 0 else r.code
    return sizes == {8: (50, 40), 2: (140, 110)}, f"sizes={sizes}"


def t_trim_padding_scales(env):
    need("PIL", "Pillow")
    src = env.sample("alpha_png")
    one = env.path("t_pad")
    r1 = trim(env, src, "--out", one, "--trim", "alpha", "--padding", 10)
    e1 = manifest_outputs(one)[0] if r1.code == 0 else {}
    ltrb = env.path("t_pad4")
    r2 = trim(env, src, "--out", ltrb, "--trim", "alpha", "--padding", "4,8,12,16")
    multi = env.path("t_scales")
    r3 = trim(env, src, "--out", multi, "--trim", "alpha", "--padding", 10, "--scales", "1,2")
    e3 = {e["path"]: e for e in manifest_outputs(multi)} if r3.code == 0 else {}
    ok = (image_size(os.path.join(one, "alpha.png")) == (100, 80)
          and e1.get("outputAlphaBoxXYWH") == [10, 10, 80, 60] and e1.get("paddingOnlyAlpha") is True
          and image_size(os.path.join(ltrb, "alpha.png")) == (96, 84)
          and image_size(os.path.join(multi, "alpha@1x.png")) == (100, 80)
          and image_size(os.path.join(multi, "alpha@2x.png")) == (200, 160)
          and e3.get("alpha@2x.png", {}).get("paddingOut") == [20, 20, 20, 20])
    return ok, f"codes={r1.code},{r2.code},{r3.code} box={e1.get('outputAlphaBoxXYWH')}"


def t_trim_names(env):
    need("PIL", "Pillow")
    src = env.sample("alpha_png")
    good = trim(env, src, "--out", env.path("t_name"), "--trim", "alpha", "--name-pattern", "{name}_{w}x{h}{ext}")
    dotted = trim(env, src, "--out", env.path("t_dot"), "--trim", "alpha", "--name-pattern", "{name}@{scale}x.{ext}")
    no_ext = trim(env, src, "--out", env.path("t_noext"), "--name-pattern", "{name}")
    no_scale = trim(env, src, "--out", env.path("t_noscale"), "--scales", "1,2", "--name-pattern", "{name}{ext}")
    reserved = trim(env, src, "--out", env.path("t_con"), "--name-pattern", "CON{ext}")
    ok = (good.code == 0 and os.path.isfile(env.path("t_name", "alpha_80x60.png"))
          and dotted.code == 1 and no_ext.code == 2 and no_scale.code == 2 and reserved.code == 1)
    return ok, f"good={good.code} dotted={dotted.code} no-ext={no_ext.code} no-scale={no_scale.code} CON={reserved.code}"


def t_trim_refusals(env):
    need("PIL", "Pillow")
    bg_on_alpha = trim(env, env.sample("alpha_png"), "--out", env.path("t_r1"), "--trim", "bg", "--bg-color", "#ffffff")
    jpeg = trim(env, env.sample("alpha_png"), "--out", env.path("t_r2"), "--trim", "alpha", "--format", "jpeg")
    stray = trim(env, env.sample("alpha_png"), "--out", env.path("t_r3"), "--bg-color", "#ffffff")
    deep = trim(env, env.sample("deep16_png"), "--out", env.path("t_r4"))
    fails = [f.get("error", "") for f in (bg_on_alpha.data or {}).get("failures", [])]
    deep_err = " ".join(f.get("error", "") for f in (deep.data or {}).get("failures", []))
    ok = (bg_on_alpha.code == 1 and any("透明" in e for e in fails) and jpeg.code == 1
          and stray.code == 2 and deep.code == 1 and "16-bit" in deep_err)
    return ok, f"bg-on-alpha={bg_on_alpha.code} jpeg-no-bg={jpeg.code} stray-bg-color={stray.code} 16bit={deep.code}"


# ------------------------------------------------------------------ fetch_asset (offline) and --help

def t_fetch_offline(env):
    a = env.script("fetch_asset", "placeholder", 10, 10, "--name", "../x", "--out", env.path("fa"))
    b = env.script("fetch_asset", "avatar", 64, "--out", env.path("fa"))
    c = env.script("fetch_asset", "pexels", 10, 10, "--query", "x", "--out", env.path("fa"))
    ok = a.code == b.code == c.code == 2 and "PEXELS_API_KEY" in (c.data or {}).get("error", "")
    return ok, f"bad-name={a.code} avatar-no-seed={b.code} pexels-no-key={c.code}"


def t_help(env):
    bad = []
    for name in SCRIPTS:
        r = env.script(name, "--help")
        if r.code != 0 or "用法" not in r.out or "<skill-dir>/scripts/" not in r.out:
            bad.append(name)
    sub = env.script("layout_design", "check", "--help")
    if sub.code != 0 or "spec.json" not in sub.out:
        bad.append("layout_design check")
    fetch = env.script("fetch_asset", "--help")
    if "cdn.devimg.cn" not in fetch.out:
        bad.append("fetch_asset routes")
    return not bad, f"bad={bad}"


CASES = [
    ("psd_audit", "compliant --strict", t_audit_compliant),
    ("psd_audit", "rasterized text only for text-prefixed pixel layers", t_audit_raster),
    ("psd_audit", "--max-depth", t_audit_depth),
    ("psd_audit", "PhotoCraft default names", t_audit_defaults),
    ("psd_audit", "compare", t_audit_compare),
    ("psd_audit", "--installed-fonts", t_audit_fonts),
    ("psd_audit", "profiles en / bad file", t_audit_profiles),
    ("psd_audit", "unreadable file exits 2", t_audit_unreadable),
    ("psd_audit", "psd-tools warnings kept off stderr", t_audit_reader_warnings),
    ("layout_design", "calc table rows", t_calc_rows),
    ("layout_design", "calc --snap none / --column-width", t_calc_modes),
    ("layout_design", "check compliant (bg overlap, inset, full-bleed)", t_check_compliant),
    ("layout_design", "check opt-in text/icon with ink tolerance", t_check_opt_in),
    ("layout_design", "check moved + off-canvas layer", t_check_moved),
    ("layout_design", "check run/serve envelopes", t_check_envelope),
    ("layout_design", "check bad root default vs --strict", t_check_badroot),
    ("layout_design", "check synthetic trees", t_check_synthetic),
    ("layout_design", "check spec errors / --no-geometry", t_check_spec_errors),
    ("layout_design", "check profiles en / project JSON", t_check_profiles),
    ("psd_compare", "identical (psd vs pcraft)", t_compare_identical),
    ("psd_compare", "changed + --out reuse", t_compare_changed),
    ("psd_compare", "canvas size mismatch", t_compare_size),
    ("psd_compare", "--fuzz", t_compare_fuzz),
    ("psd_compare", "PNG inputs", t_compare_png),
    ("psd_compare", "real vs expected warnings", t_compare_warnings),
    ("psd_compare", "guards + temp cleanup on error", t_compare_guards),
    ("trim_export", "alpha + manifest + overwrite", t_trim_alpha),
    ("trim_export", "bg + tolerance", t_trim_bg),
    ("trim_export", "padding + scales", t_trim_padding_scales),
    ("trim_export", "name patterns", t_trim_names),
    ("trim_export", "refusals + 16-bit", t_trim_refusals),
    ("fetch_asset", "offline argument checks", t_fetch_offline),
    ("all", "--help renders UTF-8", t_help),
]


def main():
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, OSError):
            pass
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("-v", "--verbose", action="store_true", help="打印每次子进程调用")
    ap.add_argument("--allow-skip", action="store_true", help="接受因缺依赖而 SKIP 的用例")
    ap.add_argument("--keep", action="store_true", help="保留临时目录（排查用）")
    ap.add_argument("--cli", default=None, help="photocraft-cli 路径")
    ap.add_argument("-k", dest="keyword", default=None, help="只跑名字含该关键词的用例")
    args = ap.parse_args()
    try:
        cli = find_cli(args.cli)
    except RuntimeError as exc:
        print(f"ERROR: {exc}")
        return 2
    if not cli:
        print("ERROR: 找不到 photocraft-cli；用 --cli 或 PHOTOCRAFT_CLI 指定")
        return 2
    root = tempfile.mkdtemp(prefix="pc-test-workflow-")
    env = Env(cli, root, args.verbose)
    tally = {"PASS": 0, "FAIL": 0, "SKIP": 0}
    started = time.time()
    try:
        try:
            print(f"photocraft-cli: {cli} ({env.pc('--version').stdout.strip()})")
        except (SetupError, OSError) as exc:
            print(f"ERROR: photocraft-cli 无法运行: {exc}")
            return 2
        for group, name, func in CASES:
            label = f"{group}: {name}"
            if args.keyword and args.keyword not in label:
                continue
            try:
                ok, detail = func(env)
                mark = "PASS" if ok else "FAIL"
            except Skip as exc:
                mark, detail = "SKIP", str(exc)
            except SetupError as exc:
                print(f" [ERROR] {label}: {exc}")
                return 2
            except Exception as exc:  # a crashing case is a failure, not a harness abort
                mark, detail = "FAIL", f"{type(exc).__name__}: {exc}"
            tally[mark] += 1
            print(f" [{mark}] {label}" + (f"  ({detail})" if mark != "PASS" or args.verbose else ""))
    finally:
        if args.keep:
            print(f"临时目录保留在: {root}")
        else:
            shutil.rmtree(root, ignore_errors=True)
    total = sum(tally.values())
    print(f"\n{tally['PASS']}/{total} PASS, {tally['FAIL']} FAIL, {tally['SKIP']} SKIP "
          f"({time.time() - started:.1f}s)")
    if tally["SKIP"] and not args.allow_skip:
        print("有 SKIP：装上缺的依赖再跑，或明确接受未覆盖的用例时加 --allow-skip。")
    return 1 if tally["FAIL"] or (tally["SKIP"] and not args.allow_skip) else 0


if __name__ == "__main__":
    sys.exit(main())
