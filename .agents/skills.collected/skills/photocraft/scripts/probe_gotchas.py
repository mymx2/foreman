#!/usr/bin/env python3
"""逐条复验 SKILL.md 与 references 里的关键结论（headless，不需要 GUI）。维护技能时用。

    python scripts/probe_gotchas.py            # 全部
    python scripts/probe_gotchas.py --list     # 只列出探针
    python scripts/probe_gotchas.py unknown-enum serve-batch-step

每条探针独立建临时文档、跑完即删；输出 ok/skip/FAIL 与证据。GUI 专属项（桌面控制通道的 60 s
回复、ui.screenshot 等）不在 headless 探针范围内，由案例 31 覆盖。
退出码：0 全过；1 有 FAIL，或有 SKIP 而没加 --allow-skip；2 环境错误（CLI 找不到、临时目录不可写）。
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import pclib  # noqa: E402

ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
ap.add_argument("names", nargs="*", help="只跑这些探针")
ap.add_argument("--list", action="store_true", help="只列出探针名")
ap.add_argument("--scan-unknown", action="store_true", help="只跑全量未知键扫描（慢）")
ap.add_argument("--allow-skip", action="store_true", help="SKIP 不导致退出码 1（仍单独计数）")
args = ap.parse_args()

WORK = Path(tempfile.mkdtemp(prefix="photocraft-probes-"))
TMP = WORK.resolve()


def pc_run(cmds, new=None, out=None, extra=(), input=None):
    argv = [str(pclib.find_cli()), "run"]
    if new is not None:
        argv += ["--new", json.dumps(new)]
    else:
        argv.append(str(input or (TMP / "x.png")))
    for cid, params in cmds:
        argv += ["--cmd", cid]
        if params is not None:
            argv += ["--params", json.dumps(params)]
    if out:
        argv += ["--out", str(TMP / out)]
    argv += list(extra)
    return pclib.run_cli(argv[1:], cli=argv[0], cwd=str(TMP), check=False)


def assert_ok(proc, what):
    if proc.returncode != 0:
        raise AssertionError(f"{what}: exit {proc.returncode}\n{proc.stderr[-800:]}")


def json_lines(proc):
    rows = []
    for line in proc.stdout.splitlines():
        line = line.strip()
        if line.startswith("{"):
            rows.append(json.loads(line))
    return rows


PROBES = {}


def probe(fn):
    PROBES[fn.__name__] = fn
    return fn


@probe
def unknown_parameter_ignored():
    """未知键在宽松命令上被静默忽略（image.imageSize 的 widht）"""
    p = pc_run([("image.imageSize", {"widht": 640})], new={"width": 800, "height": 600})
    assert_ok(p, "run")
    size = json_lines(p)[0]["result"]
    assert size["width"] == 800, size


@probe
def unknown_parameter_rejected():
    """严格命令报 unknown parameter（file.new）"""
    p = pclib.run_cli(["run", "--new", json.dumps({"width": 8, "height": 8}), "--cmd", "file.new",
                       "--params", json.dumps({"width": 8, "height": 8, "bogusKey": 1})],
                      cwd=str(TMP), check=False)
    assert p.returncode == 1, p.returncode
    assert "unknown parameter" in (p.stderr + p.stdout).lower(), (p.stderr + p.stdout)[-400:]


@probe
def engine_quality_clamped():
    """引擎 quality 超出 0..12 静默截到 12，不报错"""
    p = pc_run([("filter.noise.addNoise", {"amount": 2}), ("file.saveACopy", {"path": "q80.jpg", "quality": 80}),
                ("file.saveACopy", {"path": "q12.jpg", "quality": 12})], new={"width": 64, "height": 64}, out=None)
    assert_ok(p, "run")
    a, b = (TMP / "q80.jpg").stat().st_size, (TMP / "q12.jpg").stat().st_size
    assert a == b, (a, b)


@probe
def duplicate_stack_order():
    """连续从同一源层复制两次，第二份落在第一份下面（副本贴源层上方）"""
    p = pc_run([("layer.select", {"name": "Background"}),
                ("layer.duplicate", {"name": "first"}),
                ("layer.select", {"name": "Background"}),
                ("layer.duplicate", {"name": "second"}),
                ("layer.list", {"flat": True})], new={"width": 16, "height": 16})
    assert_ok(p, "run")
    order = [l["name"] for l in json_lines(p)[-1]["result"]["layers"]]
    assert order.index("first") < order.index("second"), order


@probe
def frequency_separation_reconstructs():
    """retouch.md 的频率分离配方：隐藏原层后，低频 + Linear Light 高频应还原原图（±2/255）"""
    pts = [(20, 20), (60, 40)]
    with pclib.Serve(read_root=str(TMP), write_root=str(TMP)) as s:
        s.call("doc.new", {"width": 120, "height": 80, "background": "#808080"})
        s.execute("shape.create", {"kind": "rect", "rect": [10, 10, 20, 20], "fill": "#ff0000"})
        s.execute("layer.flattenImage")
        s.execute("layer.select", {"name": "Background"})
        s.execute("layer.setProps", {"name": "orig"})
        orig = [s.execute("document.sampleColor", {"sampleLayer": "current", "x": x, "y": y})
                for x, y in pts]

        s.execute("layer.select", {"name": "orig"})
        s.execute("layer.duplicate", {"name": "low"})
        s.execute("filter.blur.gaussianBlur", {"radius": 6})
        s.execute("layer.select", {"name": "orig"})
        s.execute("layer.duplicate", {"name": "high"})
        s.execute("layer.select", {"name": "high"})
        s.execute("image.applyImage", {"source": {"layer": "low"}, "blending": "subtract",
                                       "scale": 2, "offset": 128})
        s.execute("layer.setProps", {"blend": "LinearLight"})
        s.execute("layer.moveTo", {"layer": "high", "target": "low", "position": "above"})
        s.execute("layer.select", {"name": "orig"})
        s.execute("layer.setProps", {"visible": False})

        got = [s.execute("document.pixel", {"x": x, "y": y}) for x, y in pts]
    for i, (x, y) in enumerate(pts):
        want = [round(c * 255) for c in orig[i][:3]]
        now = [round(c * 255) for c in got[i][:3]]
        assert all(abs(now[c] - want[c]) <= 2 for c in range(3)), f"{(x, y)}: orig={want} composite={now}"


@probe
def strict_quality_scales():
    """1..100 的三个入口都严格报错，不静默截断：CLI --quality 越界退出码 2、
    serve doc.save 越界报错、file.export.presets.save 的 settings.quality 越界报错"""
    src = TMP / "qin.png"
    p = pc_run([], new={"width": 32, "height": 32, "background": "white"}, out=str(src.name))
    assert_ok(p, "seed png")
    bad = pclib.run_cli(["convert", str(src), str(TMP / "q101.jpg"), "--quality", "101"],
                        cwd=str(TMP), check=False)
    assert bad.returncode == 2, f"CLI --quality 101 exit {bad.returncode}: {bad.stderr[-200:]}"
    assert "is not in 1..=100" in (bad.stderr + bad.stdout), (bad.stderr + bad.stdout)[-300:]

    with pclib.Serve(read_root=str(TMP), write_root=str(TMP)) as s:
        s.call("doc.new", {"width": 32, "height": 32, "background": "white"})
        try:
            s.call("doc.save", {"path": "q500.jpg", "quality": 500})
        except Exception as exc:
            assert "1 to 100" in str(exc), str(exc)[:200]
        else:
            raise AssertionError("serve doc.save quality 500 should be rejected")

    presets = pc_run([("file.export.presets.save",
                       {"name": "probe", "settings": {"quality": 500}})],
                     new={"width": 32, "height": 32})
    assert presets.returncode != 0, presets.returncode
    assert "must be within 1..=100" in (presets.stderr + presets.stdout), \
        (presets.stderr + presets.stdout)[-300:]


@probe
def deselect_without_selection_fails_run():
    """无选区的 select.deselect 随入口不同：CLI run 里 0.18 静默通过、后续步骤照跑；
    serve 的 engine.execute 两个版本都报 no selection。两个入口都要验。"""
    out = "deselect-out.png"
    p = pc_run([("select.deselect", {}), ("layer.flattenImage", {})], new={"width": 8, "height": 8}, out=out)
    wrote = (TMP / out).exists()
    if p.returncode == 0:
        # 静默通过的入口：断言"报错才中止"这条规律不成立——后续步骤确实跑了，--out 落盘
        assert "no selection" not in p.stderr.lower(), p.stderr[-400:]
        assert wrote, "run returned 0 but --out was not written; the step order claim broke"
    else:
        assert "no selection" in p.stderr.lower(), p.stderr[-400:]
        assert not wrote, "run failed but --out was still written"

    with pclib.Serve(read_root=str(TMP), write_root=str(TMP)) as s:
        s.call("doc.new", {"width": 8, "height": 8})
        try:
            s.execute("select.deselect")
        except Exception as exc:
            assert "no selection" in str(exc).lower(), exc
        else:
            raise AssertionError("serve select.deselect without a selection should report no selection")


@probe
def rasterize_single_layer_fails_on_plain_pixel():
    """单层栅格化碰到纯像素层是硬错误：后续步骤与 --out 都不执行；allLayers 回计数且可重复"""
    p = pc_run([("layer.rasterize.layer", {"layer": "Background"}), ("layer.flattenImage", {})],
               new={"width": 8, "height": 8}, out="raster-abort.png")
    assert p.returncode == 1, p.returncode
    assert "nothing to rasterize" in p.stderr.lower(), p.stderr[-400:]
    assert not (TMP / "raster-abort.png").exists(), "run wrote --out after a failed step"
    p = pc_run([("type.create", {"x": 2, "y": 10, "text": "A", "size": 8}),
                ("layer.rasterize.allLayers", {}), ("layer.rasterize.allLayers", {})],
               new={"width": 40, "height": 20})
    assert_ok(p, "run")
    counts = [row["result"].get("rasterized") for row in json_lines(p)[1:]]
    assert counts == [1, 0], counts


@probe
def rasterize_layer_style_refuses_groups():
    """组上的图层效果能渲染，但 layer.rasterize.layerStyle 报无效果可栅格化"""
    p = pc_run([("type.create", {"x": 4, "y": 20, "text": "A", "size": 10, "name": "T"}),
                ("layer.groupLayers", {"layer": "T", "name": "G"}),
                ("layer.layerStyle.dropShadow",
                 {"layer": "G", "color": "#000000", "opacity": 50, "distance": 3, "size": 3}),
                ("layer.rasterize.layerStyle", {"layer": "G"})],
               new={"width": 60, "height": 40})
    assert p.returncode == 1, p.returncode
    assert "no selected layer has layer effects to rasterize" in p.stderr.lower(), p.stderr[-400:]


@probe
def selected_is_not_success():
    """select.sky 失败时 changed=false、message 有值；selected 只表示存在选区"""
    p = pc_run([("select.sky", {})], new={"width": 64, "height": 64, "background": "#404040"})
    assert_ok(p, "run")
    r = json_lines(p)[0]["result"]
    assert r.get("changed") is False and r.get("message"), r


@probe
def pixel_ignores_sample_layer():
    """document.pixel 只读合成结果，忽略 sampleLayer"""
    p = pc_run([("image.adjustments.invert", {}), ("document.pixel", {"x": 1, "y": 1, "sampleLayer": "nope"})],
               new={"width": 8, "height": 8, "background": "white"})
    assert_ok(p, "run")
    px = json_lines(p)[-1]["result"]
    assert min(px[:3]) < 0.1, px  # inverted white -> black; a different layer would not exist


@probe
def layer_ids_renumber_on_reopen():
    """serve 里 doc.close 再 doc.open 同一 PSD，图层 id 会重新编号（跨进程按名字寻址）"""
    with pclib.Serve(read_root=str(TMP), write_root=str(TMP)) as s:
        s.call("doc.new", {"width": 16, "height": 16, "name": "ids"})
        s.execute("layer.duplicate", {"name": "A"})
        s.execute("layer.duplicate", {"name": "B"})
        ids1 = [l["id"] for l in s.execute("layer.list", {"flat": True})["layers"]]
        s.call("doc.save", {"path": "ids.psd"})
        s.call("doc.close", {"index": 0})
        s.call("doc.open", {"path": "ids.psd"})
        ids2 = [l["id"] for l in s.execute("layer.list", {"flat": True})["layers"]]
    assert len(ids2) == len(ids1) and sorted(ids1)[0] >= 1, (ids1, ids2)
    assert sorted(ids2) != sorted(ids1), ("ids survived a reopen; update the name-addressing advice", ids1, ids2)


@probe
def new_layer_goes_above_active():
    """选中根层时新层留在根层（各版本一致）；入组的稳妥做法是显式 moveTo into。
    活动层是组本身时的隐含落点随版本变（0.18 进组、早期落组外），文档因此不依赖它。"""
    root = pc_run([("layer.select", {"name": "Background"}),
                   ("layer.new.layer", {"name": "onRoot"}),
                   ("layer.list", {"flat": True})], new={"width": 8, "height": 8})
    assert_ok(root, "run")
    layers = json_lines(root)[-1]["result"]["layers"]
    on_root = next(l for l in layers if l["name"] == "onRoot")
    assert on_root.get("parent") is None and on_root.get("depth") == 0, on_root

    inside = pc_run([("layer.new.group", {"name": "G"}),
                     ("layer.new.layer", {"name": "loose"}),
                     ("layer.select", {"name": "loose"}),
                     ("layer.moveTo", {"target": "G", "position": "into"}),
                     ("layer.list", {"flat": True})], new={"width": 8, "height": 8})
    assert_ok(inside, "run")
    layers = json_lines(inside)[-1]["result"]["layers"]
    group = next(l for l in layers if l["name"] == "G")
    moved = next(l for l in layers if l["name"] == "loose")
    assert moved.get("parent") == group["id"], (group, moved)


@probe
def render_is_png():
    """doc.render 恒出 PNG（扩展名不换格式）"""
    with pclib.Serve(read_root=str(TMP), write_root=str(TMP)) as s:
        s.call("doc.new", {"width": 32, "height": 32, "background": "white"})
        s.call("doc.render", {"path": "r.jpg", "maxSide": 32})
    head = (TMP / "r.jpg").read_bytes()[:8]
    assert head == b"\x89PNG\r\n\x1a\n", head


@probe
def ambient_file_refused_in_serve():
    """serve 里带路径的 file.* 按命令名拒绝"""
    with pclib.Serve(read_root=str(TMP), write_root=str(TMP)) as s:
        try:
            s.execute("file.saveACopy", {"path": "x.png"})
        except pclib.RpcError as exc:
            assert "ambient filesystem paths" in str(exc), exc
        else:
            raise AssertionError("file.saveACopy was not refused")


@probe
def serve_batch_step_shape():
    """serve batch 只认对象步骤；doc.* 步骤要写 method；失败在 result.failed"""
    with pclib.Serve(read_root=str(TMP), write_root=str(TMP)) as s:
        s.call("doc.new", {"width": 8, "height": 8})
        r = s.call("batch", {"steps": [["layer.new.layer", {}]]})
        assert r["failed"] == 1 and "needs `command` or `method`" in json.dumps(r), r
        res = s.call("batch", {"steps": [{"method": "doc.save", "params": {"path": "a.png"}}, {"command": "no.such"}],
                              "stopOnError": False})
        assert res["failed"] == 1, res


@probe
def export_layers_skips_adjustment_and_keeps_number():
    """doc.exportLayers 跳过调整层但保留序号"""
    with pclib.Serve(read_root=str(TMP), write_root=str(TMP)) as s:
        s.call("doc.new", {"width": 20, "height": 10, "background": "white"})
        s.execute("layer.new.layer")
        s.execute("layer.newAdjustmentLayer.curves")
        s.execute("layer.new.layer")
        out = s.call("doc.exportLayers", {"dir": "exp"})
        names = [Path(f).name for f in out["files"]]
        assert len(names) == 3 and any("_0002_" in n for n in names) and not any("_0001_" in n for n in names), names


@probe
def spot_healing_is_one_stroke():
    """paint.spotHealing 的 points 是一笔连续笔画：两点之间的区域也会被修改"""
    p = pc_run([("paint.spotHealing", {"points": [[16, 16], [80, 16]], "size": 6})],
               new={"width": 96, "height": 32, "background": "#ffffff"})
    assert_ok(p, "run")
    r = json_lines(p)[0]["result"]
    d = r.get("damage")
    assert d and d[2] > 40, ("damage spans both points as one stroke", d)


@probe
def crop_angle_same_sign_as_tilt():
    """image.crop.angle 与顺时针倾斜角同号：同号拉直后四角是画面内容"""
    # 铺满 #cc2222 后顺时针转 3°；在旋转后的画布上留 3–4px 余量裁切。
    # 同号：四角（再内缩 2px）应仍是填充色；反号：至少两个角露出白边。
    base = pc_run([("edit.fill", {"contents": "color", "color": "#cc2222"}),
                   ("image.rotation.arbitrary", {"angle": 3, "direction": "cw"}),
                   ("document.inspect", {})],
                  new={"width": 80, "height": 60, "background": "#ffffff"}, out="tilted.psd")
    assert_ok(base, "run")
    state = json_lines(base)[-1]["result"]
    W, H = state["width"], state["height"]
    w, h = W - 6, H - 7
    crop = {"x": (W - w) // 2, "y": (H - h) // 2, "width": w, "height": h}
    corners = ((2, 2), (w - 3, 2), (2, h - 3), (w - 3, h - 3))
    fill = (0.8, 0.1333, 0.1333)                  # #cc2222

    def distance(px):
        return max(abs(px[i] - fill[i]) for i in range(3))

    def cut(angle):
        cmds = [("image.crop", {**crop, "angle": angle})]
        cmds += [("document.pixel", {"x": x, "y": y}) for x, y in corners]
        p = pc_run(cmds, input=str(TMP / "tilted.psd"))
        assert_ok(p, "run")
        return [json_lines(p)[i]["result"] for i in range(1, len(cmds))]

    same = cut(3)
    off = [px for px in same if distance(px) > 0.1]
    if off:
        raise AssertionError(f"same-sign crop is not fill colour at every sampled corner: {same}; "
                             "confirm with examples/20-scan-split-straighten.py")
    opposite = cut(-3)
    blank = [px for px in opposite if distance(px) > 0.25]
    if len(blank) < 2:
        raise AssertionError(f"opposite-sign crop did not expose a blank corner: {opposite}")


@probe
def csv_first_column_naming():
    """CSV 首列表头为 DataSet 时成为数据组名"""
    (TMP / "d.csv").write_text("DataSet,cap\nA,one\nB,two\n", encoding="utf-8")
    with pclib.Serve(read_root=str(TMP), write_root=str(TMP)) as s:
        s.call("doc.new", {"width": 40, "height": 20, "background": "white"})
        s.execute("type.create", {"x": 2, "y": 12, "text": "x", "size": 10, "name": "Cap"})
        layers = s.execute("layer.list", {"flat": True})["layers"]
        cap_id = next(layer["id"] for layer in layers if layer["name"] == "Cap")
        s.execute("image.variables.define", {"defs": [{"name": "cap", "layer": cap_id, "type": "textReplacement"}]})
        s.call("doc.importDataSets", {"path": "d.csv"})
        sets = s.execute("variables.list")["dataSets"]
        assert [d["name"] for d in sets] == ["A", "B"], sets


@probe
def save_identity_on_flat_copy():
    """存成 PNG 只是副本：文档身份和 dirty 不变"""
    with pclib.Serve(read_root=str(TMP), write_root=str(TMP)) as s:
        s.call("doc.new", {"width": 8, "height": 8, "name": "keep"})
        s.call("doc.save", {"path": "copy.png"})
        doc = s.call("session.list")["documents"][0]
        assert doc["name"] == "keep" and doc["path"] is None, doc


@probe
def empty_adjustment_still_adds_history():
    """空操作也进历史：用像素证明效果"""
    p = pc_run([("image.mode.grayscale", {}), ("image.adjustments.hueSaturation", {"hue": 120}),
                ("document.inspect", {})], new={"width": 8, "height": 8, "background": "#808080"})
    assert_ok(p, "run")
    hist = json_lines(p)[-1]["result"]["history"]
    names = [h.get("name") if isinstance(h, dict) else h for h in hist]
    assert any("Hue" in (n or "") for n in names), names


@probe
def misspelt_enum_falls_back():
    """拼错的枚举静默回落（align:\"centre\" 不报错，按 Left 排）"""
    p = pc_run([("type.create", {"x": 10, "y": 30, "text": "centre", "size": 12, "align": "centre", "name": "T"}),
                ("layer.select", {"name": "T"}), ("type.info", {})],
               new={"width": 120, "height": 60, "background": "white"})
    assert_ok(p, "run")
    info = json_lines(p)[-1]["result"]
    para = info.get("paragraph") or {}
    assert (para.get("align") or "").lower() in ("", "left"), info


@probe
def mcp_batch_rejects_camel_case():
    """MCP 参数名要 snake_case；camelCase 回 -32602"""
    with pclib.Mcp(read_root=str(TMP), write_root=str(TMP)) as m:
        m.request("initialize", {"protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "p", "version": "1"}})
        m.notify("notifications/initialized")
        try:
            m.request("tools/call", {"name": "command_batch", "arguments": {"steps": [], "stopOnError": True}})
        except pclib.RpcError as exc:
            assert exc.code == -32602 if hasattr(exc, "code") else True
            assert "stopOnError" in str(exc), exc
        else:
            raise AssertionError("camelCase argument was accepted")


@probe
def smart_object_replace_keeps_layer_scale():
    """换智能对象内容保留图层缩放，不按源图 DPI 换算；复制实例共享内容源"""
    assert_ok(pc_run([], new={"width": 64, "height": 32, "resolution": 72, "background": "#ff0000"},
                     out="so-base.png"), "base png")
    assert_ok(pc_run([], new={"width": 128, "height": 64, "resolution": 300, "background": "#00ff00"},
                     out="so-rep.png"), "replacement png")
    p = pc_run([
        ("file.placeEmbedded", {"path": "so-base.png", "smartObject": True, "scale": 100}),
        ("layer.select", {"name": "so-base"}),
        ("edit.transform", {"scaleX": 50, "scaleY": 50}),
        ("layer.list", {"flat": True}),
        ("layer.duplicate", {}),
        ("layer.smartObjects.replaceContents", {"path": "so-rep.png"}),
        ("layer.list", {"flat": True}),
    ], new={"width": 200, "height": 200, "resolution": 72, "background": "#ffffff"}, out="so-out.psd")
    assert_ok(p, "smart object run")
    rows = json_lines(p)
    lists = [r["result"]["layers"] for r in rows if r.get("command") == "layer.list"]
    rep = next(r["result"] for r in rows if r.get("command") == "layer.smartObjects.replaceContents")
    before = [l for l in lists[0] if l["kind"] == "Smart Object"]
    after = [l for l in lists[1] if l["kind"] == "Smart Object"]
    assert len(before) == 1 and before[0]["bounds"][2:] == [32, 16], before
    assert len(after) == 2, after
    assert all(l["bounds"][2:] == [64, 32] for l in after), after
    assert len(rep.get("instances", [])) >= 2, rep


@probe
def scan_unknown_keys():
    """全量扫描：对每条命令传一个未知键，统计报错/静默/前置条件失败（慢，约 2 分钟）"""
    reg = pclib.registry()
    base = json.loads(subprocess.run([str(pclib.find_cli()), "run", "--new",
                                      json.dumps({"width": 64, "height": 64, "background": "white"}),
                                      "--cmd", "type.create",
                                      "--params", json.dumps({"x": 8, "y": 32, "text": "t", "size": 12}),
                                      "--out", str(TMP / "scan-base.psd")],
                                     capture_output=True, text=True, encoding="utf-8", check=False).stdout.splitlines()[-1])["result"]
    del base
    rejected = silent = blocked = 0
    for c in reg:
        proc = pclib.run_cli(["run", str(TMP / "scan-base.psd"), "--cmd", c["id"],
                              "--params", '{"bogusKey":1}'], cwd=str(TMP), check=False)
        text = (proc.stdout + proc.stderr).lower()
        if "unknown parameter" in text:
            rejected += 1
        elif "not available right now" in text or "no layer" in text or "no selection" in text:
            blocked += 1
        elif proc.returncode == 0:
            silent += 1
    print("rejected %d, silent %d, blocked %d of %d" % (rejected, silent, blocked, len(reg)))
    assert rejected > 0 and silent > 0, (rejected, silent)


def main():
    default = [n for n in PROBES if n != "scan_unknown_keys"]
    names = args.names or (["scan_unknown_keys"] if args.scan_unknown else default)
    if args.list:
        for name in names:
            doc = (PROBES[name].__doc__ or "").strip().splitlines()[0]
            print(f"{name:40s} {doc}")
        return 0
    failed = []
    skipped = []
    for name in names:
        if name not in PROBES:
            print(f"FAIL {name}: no such probe")
            failed.append(name)
            continue
        try:
            PROBES[name]()
        except SystemExit as exc:                     # a probe may report SKIP explicitly
            msg = str(exc) or "skipped"
            if msg.startswith("SKIP"):
                print(f"skip {name}: {msg[5:].lstrip(': ').strip()}")
                skipped.append(name)
                continue
            print(f"FAIL {name}: {msg}")
            failed.append(name)
        except Exception as exc:                      # noqa: BLE001 — a probe failure is data
            print(f"FAIL {name}: {type(exc).__name__}: {exc}")
            failed.append(name)
        else:
            print(f"ok   {name}")
    print(f"\n{len(names) - len(failed) - len(skipped)} passed, {len(skipped)} skipped, "
          f"{len(failed)} failed")
    if skipped and not args.allow_skip:
        print("SKIP 不是通过：确认原因后加 --allow-skip，或修正环境后重跑", file=sys.stderr)
    return 1 if failed or (skipped and not args.allow_skip) else 0


if __name__ == "__main__":
    pclib.setup_stdio()
    try:
        raise SystemExit(main())
    finally:
        import shutil
        shutil.rmtree(WORK, ignore_errors=True)
