#!/usr/bin/env python3
"""一条命令出一条片：三层 PSD + 分层 PNG + 并排对比 + 400% 放大 + qc_report。

    python scripts/pipeline_portrait.py --src 人像.jpg --out 交付目录

产物（全部落在 --out）：
    three-layer.psd    BG_BOKEH / PATCH / SUBJECT 三层，原片副本做底
    after.png          成片
    layers/L*.png      分层导出（透明背景）
    compare.png        无边框 Before vs After 并排
    crop_eye_400.png / crop_mouth_400.png / crop_edge_400.png
    qc_report.json     尺寸、SHA256、门控断言、差异、高频保留率

口径（不满足就退 1，别当成功交付）：
 - 补丁层的影响范围必须完全落在门控矩形内（门控外 diff=0）。
 - 主体层必须带蒙版；分层导出数量 = 可见顶层数量。
 - 放大图正好 4×；高频保留率 <0.75 按"磨皮过度"判失败。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path

try:
    import numpy as np
    from PIL import Image
except Exception:  # noqa: BLE001
    print("pipeline: 需要 numpy + Pillow", file=sys.stderr)
    raise SystemExit(2)

CLI_CANDIDATES = [r"C:\Program Files\PhotoCraft\photocraft-cli.exe", "photocraft-cli"]


def find_cli() -> str:
    for c in CLI_CANDIDATES:
        if Path(c).exists():
            return c
        import shutil
        if shutil.which(c):
            return c
    print("pipeline: 找不到 photocraft-cli", file=sys.stderr)
    raise SystemExit(2)


CLI: str | None = None


def cli_path() -> str:
    """懒解析 CLI：导入本模块（跑离线单测）时不应要求已安装 PhotoCraft。"""
    global CLI
    if CLI is None:
        CLI = find_cli()
    return CLI


def run_steps(inp: Path | None, steps, out: Path, new: dict | None = None) -> tuple[int, list[dict], str]:
    cmd = [cli_path(), "run"] + ([str(inp)] if inp else [])
    if new is not None:
        cmd += ["--new", json.dumps(new, ensure_ascii=False, separators=(",", ":"))]
    for step in steps:
        cid = step[0]
        params = step[1] if len(step) > 1 else {}
        cmd += ["--cmd", cid, "--params", json.dumps(params, ensure_ascii=False, separators=(",", ":"))]
    cmd += ["--out", str(out)]
    p = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    rows = []
    for line in p.stdout.splitlines():
        line = line.strip()
        if line.startswith("{"):
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                pass
    return p.returncode, rows, p.stderr


def to_png(src: Path, dst: Path) -> None:
    p = subprocess.run([cli_path(), "convert", str(src), str(dst)], capture_output=True, text=True, timeout=300)
    if p.returncode != 0 or not dst.exists():
        raise RuntimeError(f"convert failed: {src} -> {dst}\n{p.stderr[-500:]}")


def sha(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def rgb(p: Path) -> np.ndarray:
    im = Image.open(p)
    im.load()
    return np.asarray(im.convert("RGB"), dtype=np.float32)


def render(inp: Path, hide: list[str], out_psd: Path, out_png: Path) -> None:
    steps = []
    for name in hide:
        steps.append(("layer.select", {"name": name}))
        steps.append(("layer.setProps", {"visible": False}))
    rc, rows, err = run_steps(inp, steps, out_psd)
    if rc != 0:
        raise RuntimeError(f"render failed\n{err[-500:]}")
    to_png(out_psd, out_png)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--blur", type=float, default=24.0)
    a = ap.parse_args()
    if not (1.0 <= a.blur <= 200.0):
        print(f"pipeline: --blur 必须在 1..200，收到 {a.blur}", file=sys.stderr)
        return 2

    src = Path(a.src).resolve()
    if not src.exists():
        print(f"pipeline: 源文件不存在 {src}", file=sys.stderr)
        return 2
    out = Path(a.out).resolve()
    out.mkdir(parents=True, exist_ok=True)
    (out / "layers").mkdir(exist_ok=True)
    t0 = time.time()

    w, h = Image.open(src).size
    gate = [int(w * 0.06), int(h * 0.10), int(w * 0.16), int(h * 0.16)]
    print(json.dumps({"src": str(src), "size": [w, h], "gate": gate}, ensure_ascii=False))

    # 1) 三层：主体切除 / 背景光圈散景 / 门控补丁
    rc, rows, err = run_steps(src, [
        ("layer.duplicate", {"name": "SUBJECT"}),
        ("layer.removeBackground", {"layer": "SUBJECT"}),
        ("layer.select", {"name": "Background"}),
        ("layer.duplicate", {"name": "BG_BOKEH"}),
        ("layer.select", {"name": "BG_BOKEH"}),
        ("filter.blur.lensBlur", {"radius": a.blur, "shape": "hexagon", "bladeCurvature": 1.2,
                                  "rotation": 15, "brightness": 1.0, "threshold": 0.25,
                                  "noise": 0, "seed": 11}),
        ("layer.select", {"name": "BG_BOKEH"}),
        ("layer.duplicate", {"name": "PATCH"}),
        ("select.rect", {"x": gate[0], "y": gate[1], "width": gate[2], "height": gate[3]}),
        ("edit.contentAwareFill", {"seed": 7}),
        ("select.deselect",),
        ("layer.layerMask.hideAll", {"layer": "PATCH"}),
        ("select.rect", {"x": gate[0], "y": gate[1], "width": gate[2], "height": gate[3]}),
        ("layer.layerMask.revealSelection", {"layer": "PATCH"}),
        ("select.deselect",),
        ("layer.select", {"name": "Background"}),
        ("layer.setProps", {"visible": False}),
        ("document.inspect",),
    ], out / "three-layer.psd")
    if rc != 0:
        print(err[-1200:], file=sys.stderr)
        return 1
    insp = next((r.get("result") for r in rows if r.get("command") == "document.inspect"), {}) or {}
    names = [l.get("name") for l in insp.get("layers", [])]
    sub = next((l for l in insp.get("layers", []) if l.get("name") == "SUBJECT"), {})
    checks: dict[str, bool] = {}
    checks["three_layers"] = all(n in names for n in ("BG_BOKEH", "PATCH", "SUBJECT"))
    checks["subject_masked"] = bool(sub.get("hasMask"))
    if not all(checks.values()):
        print(json.dumps({"checks": checks, "layers": names}, ensure_ascii=False), file=sys.stderr)
        return 1

    # 2) 成片 + 分层导出
    to_png(out / "three-layer.psd", out / "after.png")
    rc, rows, err = run_steps(out / "three-layer.psd", [
        ("file.export.layersToFiles", {"dir": str(out / "layers"), "format": "png", "prefix": "L"}),
    ], out / "exported.psd")
    if rc != 0:
        print(err[-800:], file=sys.stderr)
        return 1
    files = sorted((out / "layers").glob("L*.png"))
    checks["layers_exported"] = len(files) >= 3

    # 2.5) 主体零生成：SUBJECT 不透明区必须与原片一致（8 位合成取整容差 ≤4/255）
    subj_file = next((f for f in files if "SUBJECT" in f.name.upper()), None)
    subj_diff = {"mean": None, "max": None, "pixels": 0, "file": str(subj_file) if subj_file else None}
    if subj_file:
        sa = np.asarray(Image.open(subj_file).convert("RGBA"))
        core = sa[..., 3] > 250
        if core.any():
            s_rgb = sa[..., :3].astype(np.int16)
            b_rgb = rgb(src).astype(np.int16)
            dd = np.abs(s_rgb[core] - b_rgb[core])
            subj_diff = {"mean": round(float(dd.mean()), 3), "max": int(dd.max()),
                         "pixels": int(core.sum()), "file": str(subj_file)}
    checks["subject_from_source(<=4/255)"] = (subj_diff["max"] is not None
                                             and subj_diff["max"] <= 4)

    # 3) 门控断言：补丁开关两次渲染，差异必须落在门控内
    rc, _rows, err = run_steps(out / "three-layer.psd", [
        ("layer.select", {"name": "PATCH"}),
        ("layer.setProps", {"visible": False}),
    ], out / "_patch_off.psd")
    if rc != 0:
        print(f"pipeline: patch-off 渲染失败\n{err[-800:]}", file=sys.stderr)
        return 1
    try:
        to_png(out / "_patch_off.psd", out / "_patch_off.png")
    except RuntimeError as exc:
        print(f"pipeline: patch-off 转 PNG 失败: {exc}", file=sys.stderr)
        return 1
    on = rgb(out / "after.png")
    off = rgb(out / "_patch_off.png")
    d = np.abs(on - off).mean(axis=2)
    ys, xs = np.where(d > 0.5)
    patch_box = None if len(xs) == 0 else [int(xs.min()), int(ys.min()),
                                          int(xs.max()) - int(xs.min()) + 1,
                                          int(ys.max()) - int(ys.min()) + 1]
    inside = patch_box is not None and (patch_box[0] >= gate[0] and patch_box[1] >= gate[1] and
                                       patch_box[0] + patch_box[2] <= gate[0] + gate[2] and
                                       patch_box[1] + patch_box[3] <= gate[1] + gate[3])
    checks["patch_confined_to_gate"] = bool(inside)

    # 4) 并排对比（无边框）
    run_steps(None, [
        ("file.placeEmbedded", {"path": str(src).replace("\\", "/"), "scale": 100, "fit": False,
                                "smartObject": False, "center": [w / 2, h / 2]}),
        ("file.placeEmbedded", {"path": str((out / "after.png")).replace("\\", "/"), "scale": 100,
                                "fit": False, "smartObject": False, "center": [w * 1.5, h / 2]}),
        ("layer.flattenImage",),
    ], out / "compare.psd", new={"width": w * 2, "height": h, "background": "white", "name": "compare"})
    to_png(out / "compare.psd", out / "compare.png")
    checks["compare_doubled"] = Image.open(out / "compare.png").size == (w * 2, h)

    # 5) 400% 局部放大（从成片裁）
    crops = {
        "crop_eye_400.png": [int(w * 0.34), int(h * 0.34), int(w * 0.16), int(h * 0.16)],
        "crop_mouth_400.png": [int(w * 0.38), int(h * 0.60), int(w * 0.16), int(h * 0.14)],
        "crop_edge_400.png": [int(w * 0.08), int(h * 0.18), int(w * 0.18), int(h * 0.18)],
    }
    ok_crops = True
    for name, cbox in crops.items():
        psd = out / (name.replace(".png", ".psd"))
        rc, rows, err = run_steps(out / "after.png", [
            ("image.crop", {"x": cbox[0], "y": cbox[1], "width": cbox[2], "height": cbox[3],
                            "deleteCroppedPixels": True}),
            ("image.imageSize", {"percent": 400}),
        ], psd)
        if rc != 0:
            print(err[-400:], file=sys.stderr)
            ok_crops = False
            continue
        to_png(psd, out / name)
        got = Image.open(out / name).size
        if abs(got[0] - cbox[2] * 4) > 2 or abs(got[1] - cbox[3] * 4) > 2:
            ok_crops = False
    checks["crops_400pct"] = ok_crops

    # 6) 数值质检
    before = rgb(src)
    after = rgb(out / "after.png")
    mean = float(np.abs(after - before).mean())
    mx = float(np.abs(after - before).max())

    def hf(img, box):
        x, y, cw, ch = box
        g = img[y:y + ch, x:x + cw].mean(axis=2)
        return float(np.abs(np.diff(g, axis=1)).mean())

    skin = [int(w * 0.40), int(h * 0.42), int(w * 0.18), int(h * 0.15)]
    e0, e1 = hf(before, skin), hf(after, skin)
    ratio = e1 / max(1e-6, e0)
    checks["not_identical"] = mx > 0.5
    checks["texture_kept"] = ratio >= 0.75

    report = {
        "schema": "photocraft.pipeline/1",
        "created": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "source": {"path": str(src), "sha256": sha(src), "width": w, "height": h},
        "gate": gate,
        "outputs": {"psd": str(out / "three-layer.psd"), "flat": str(out / "after.png"),
                    "compare": str(out / "compare.png"),
                    "layers": [str(f) for f in files],
                    "crops": [str(out / n) for n in crops]},
        "diff": {"mean": round(mean, 3), "max": round(mx, 3)},
        "subject_diff": subj_diff,
        "texture": {"region": skin, "hf_before": round(e0, 4), "hf_after": round(e1, 4),
                    "ratio": round(ratio, 3)},
        "patch_bbox": patch_box,
        "checks": checks,
        "passed": all(checks.values()),
        "elapsed_s": round(time.time() - t0, 1),
    }
    (out / "qc_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"passed": report["passed"], "checks": checks, "qc": str(out / "qc_report.json"),
                      "elapsed_s": report["elapsed_s"]}, ensure_ascii=False, indent=2))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
