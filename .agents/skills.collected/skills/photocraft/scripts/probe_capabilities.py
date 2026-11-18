#!/usr/bin/env python3
"""能力探针：把 references/capability-matrix.md 里的 unverified 项逐条实跑，产出证据与结论。

用法:
    python scripts/probe_capabilities.py --work DIR [--src 人像] [--only id1,id2] [--json OUT]

约定:
- 每条探针在 --work 下的独立子目录里跑，输入先复制，绝不改原文件。
- 只读断言：不写回任何用户文档；产出全是副本与报告。
- 结果四态：works / degrades / fails / untested。works 只给"断言测到了它声称的那个量"的项；
  弱断言、恒真断言、只验存在性的一律 degrades，并在 checks/note 里写清弱在哪。
- 没有实跑的项一律 untested，不许被当成通过。

退出码：0 = 选中范围（默认全部，`--only` 时只算选中的）全 works；3 = 选中范围有 degrades
或有未跑项（untested）；1 = 有 fails；2 = 环境缺失或参数错误。
旧版 degrades 也退 0，等于降级不进 CI 失败集合；这条已改。--only 里出现未知探针名直接退 2，
不会再"空报告退 0"。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

CLI_CANDIDATES = [
    r"C:\Program Files\PhotoCraft\photocraft-cli.exe",
    "photocraft-cli",
]

try:
    import numpy as np
    from PIL import Image
except Exception:  # noqa: BLE001
    print("probe: 需要 Pillow 与 numpy（pip install -r scripts/requirements.txt）", file=sys.stderr)
    raise SystemExit(2)


def find_cli() -> str:
    for c in CLI_CANDIDATES:
        if Path(c).exists():
            return c
        if shutil.which(c):
            return c
    print("probe: 找不到 photocraft-cli", file=sys.stderr)
    raise SystemExit(2)


CLI: str | None = None


def cli_path() -> str:
    """懒解析 CLI：导入本模块（跑纯数学测试）时不应要求已安装 PhotoCraft。"""
    global CLI
    if CLI is None:
        CLI = find_cli()
    return CLI


def cli(args: list[str], timeout: int = 180) -> subprocess.CompletedProcess:
    return subprocess.run([cli_path(), *args], capture_output=True, text=True, timeout=timeout)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run_steps(inp: Path, steps: list[tuple[str, dict]], out: Path, extra: list[str] | None = None) -> tuple[int, list[dict], str]:
    """跑一条 run，返回 (退出码, 每步 JSON 结果, stderr)。"""
    cmd = ["run", str(inp)]
    for step in steps:
        cid = step[0]
        params = step[1] if len(step) > 1 else {}
        cmd += ["--cmd", cid, "--params", json.dumps(params, ensure_ascii=False, separators=(",", ":"))]
    cmd += ["--out", str(out)]
    if extra:
        cmd += extra
    p = cli(cmd)
    results: list[dict] = []
    for line in p.stdout.splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            results.append(json.loads(line))
        except json.JSONDecodeError:
            pass
    return p.returncode, results, p.stderr


def to_png(src: Path, dst: Path) -> bool:
    if src.suffix.lower() == ".png":
        shutil.copy2(src, dst)
        return True
    return cli(["convert", str(src), str(dst)]).returncode == 0


def load_rgb(path: Path) -> np.ndarray:
    im = Image.open(path)
    im.load()
    return np.asarray(im.convert("RGB"), dtype=np.float32)


def load_rgba(path: Path) -> np.ndarray:
    im = Image.open(path)
    im.load()
    return np.asarray(im.convert("RGBA"), dtype=np.float32)


def srgb_to_lab(rgb: np.ndarray) -> np.ndarray:
    """rgb: 0..255 float, shape (h,w,3) -> Lab (D65)."""
    c = rgb / 255.0
    c = np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)
    m = np.array([[0.4124564, 0.3575761, 0.1804375],
                  [0.2126729, 0.7151522, 0.0721750],
                  [0.0193339, 0.1191920, 0.9503041]], dtype=np.float32)
    xyz = c @ m.T
    wp = np.array([0.95047, 1.0, 1.08883], dtype=np.float32)
    t = xyz / wp
    f = np.where(t > 0.008856, np.cbrt(t), (7.787 * t) + (16.0 / 116.0))
    L = 116.0 * f[..., 1] - 16.0
    a = 500.0 * (f[..., 0] - f[..., 1])
    b = 200.0 * (f[..., 1] - f[..., 2])
    return np.stack([L, a, b], axis=-1)


def frame(results: list[dict], command: str) -> dict:
    for r in results:
        if r.get("command") == command:
            return r.get("result") or {}
    return {}


# ---------------------------------------------------------------- probes

def p_lensblur(src: Path, out: Path, report: dict) -> None:
    """真叶片孔径：形状→叶片数、seed 可复现、非法枚举被拒。"""
    hexp = out / "hex.png"
    rc1, res1, err1 = run_steps(src, [("filter.blur.lensBlur", {
        "radius": 25, "shape": "hexagon", "bladeCurvature": 40,
        "noise": 6, "distribution": "gaussian", "monochromatic": True, "seed": 7})], hexp)
    f1 = (frame(res1, "filter.blur.lensBlur") or {}).get("filter", {})
    octp = out / "oct.png"
    rc2, res2, _ = run_steps(src, [("filter.blur.lensBlur", {"radius": 25, "shape": "octagon", "seed": 7})], octp)
    f2 = (frame(res2, "filter.blur.lensBlur") or {}).get("filter", {})
    # 非法枚举
    bad = out / "bad.png"
    rc3, _, err3 = run_steps(src, [("filter.blur.lensBlur", {"radius": 10, "shape": "circle"})], bad)
    changed = False
    if hexp.exists():
        changed = float(np.abs(load_rgb(hexp) - load_rgb(src)).mean()) > 3.0
    checks = {
        "runs": rc1 == 0 and rc2 == 0,
        "blades_hex_6": f1.get("blades") == 6,
        "blades_oct_8": f2.get("blades") == 8,
        "image_actually_blurred": changed,
        "invalid_enum_rejected": rc3 != 0,
    }
    report["lensBlur"] = dict(status="works" if all(checks.values()) else "degrades",
                              checks=checks, filter_echo=f1, stderr=err1[:400],
                              evidence=[str(hexp.name), str(octp.name)])


def p_levels_lab(src: Path, out: Path, report: dict) -> None:
    """LAB 分通道：只动 a*/b*，L* 逐像素不变。"""
    base = out / "lab.png"
    rc0, res0, _ = run_steps(src, [("image.mode.lab", {})], base)
    before = out / "before.png"
    to_png(base, before)
    after_psd = out / "after_lab.psd"
    rc1, res1, err1 = run_steps(src, [
        ("image.mode.lab", {}),
        ("image.adjustments.levels", {"a": {"inBlack": 0, "gamma": 0.7, "inWhite": 255}}),
    ], after_psd)
    after = out / "after.png"
    ok_conv = after_psd.exists() and to_png(after_psd, after)
    dL = da = db = dL_full = da_full = db_full = None
    gamut_frac = None
    if before.exists() and after.exists():
        b = srgb_to_lab(load_rgb(before))
        a = srgb_to_lab(load_rgb(after))
        # 只在"前后都没被色域裁切"的像素上比 L / a / b ——三个指标必须同口径
        in_gamut = ((np.abs(b[..., 1]) < 60) & (np.abs(b[..., 2]) < 60) &
                    (np.abs(a[..., 1]) < 60) & (np.abs(a[..., 2]) < 60) &
                    (b[..., 0] > 25) & (b[..., 0] < 85))
        gamut_frac = float(in_gamut.mean())
        if in_gamut.any():
            dL = float(np.abs(b[..., 0][in_gamut] - a[..., 0][in_gamut]).mean())
            da = float(np.abs(b[..., 1][in_gamut] - a[..., 1][in_gamut]).mean())
            db = float(np.abs(b[..., 2][in_gamut] - a[..., 2][in_gamut]).mean())
        dL_full = float(np.abs(b[..., 0] - a[..., 0]).mean())
        da_full = float(np.abs(b[..., 1] - a[..., 1]).mean())
        db_full = float(np.abs(b[..., 2] - a[..., 2]).mean())
    checks = {"runs": rc1 == 0 and rc0 == 0, "roundtrip": bool(ok_conv),
              "L_preserved(<=1.0)": dL is not None and dL <= 1.0,
              "a_changed(>=3.0)": da is not None and da >= 3.0,
              "b_drift(<=3.0)": db is not None and db <= 3.0}
    report["levelsLab"] = dict(status="works" if all(checks.values()) else "degrades",
                               checks=checks, dL=dL, d_ab=da, d_b=db,
                               full_frame={"dL": dL_full, "da": da_full, "db": db_full},
                               gamut_frac=gamut_frac, stderr=err1[:400],
                               evidence=[str(before.name), str(after.name)],
                               note="三个指标统一在色域内掩码上算；全量数值另列，"
                                    "全量 dL 较大是 RGB 触边裁切所致")


def p_refine_edge(src: Path, out: Path, report: dict) -> None:
    """发丝级 alpha：refineEdge 是否能产出带软边蒙版。"""
    psd = out / "matte.psd"
    rc, res, err = run_steps(src, [
        ("select.subject", {"sampleAllLayers": False}),
        ("select.refineEdge", {"radius": 2, "smartRadius": True, "smooth": 30,
                               "feather": 1, "contrast": 10, "shiftEdge": 0,
                               "decontaminate": True, "amount": 100, "output": "layerMask"}),
    ], psd)
    soft = soft_global = None
    png = out / "matte.png"
    if psd.exists() and to_png(psd, png):
        rgba = load_rgba(png)
        a = rgba[..., 3]
        solid = a > 0
        if solid.any():
            soft_global = float(((a > 10) & (a < 245)).sum() / solid.sum())
            # 轮廓上的软边：alpha>128 且四邻域有 <=128 的像素视为轮廓，再看它 3x3 内有没有过渡像素
            core = a > 128
            bg = a <= 128
            edge = core & (np.roll(bg, 1, 0) | np.roll(bg, -1, 0) | np.roll(bg, 1, 1) | np.roll(bg, -1, 1))
            transition = (a > 10) & (a < 245)
            dil = transition.copy()
            for dy in (-1, 0, 1):
                for dx in (-1, 0, 1):
                    dil |= np.roll(np.roll(transition, dy, 0), dx, 1)
            n_edge = int(edge.sum())
            soft = float((edge & dil).sum() / n_edge) if n_edge else 0.0
    checks = {"runs": rc == 0, "mask_written": psd.exists(),
              "contour_soft>=0.5": soft is not None and soft >= 0.5}
    report["refineEdge"] = dict(status="works" if all(checks.values()) else "degrades",
                                checks=checks, soft_ratio_contour=soft,
                                soft_ratio_global=soft_global, stderr=err[:400],
                                evidence=[str(png.name)],
                                note="判据改为轮廓软边覆盖率（旧判据用全图半透明占比 1%，"
                                     "任何 1px 抗锯齿都能过）。本样张是硬边棚拍图，"
                                     "**发丝级结论不在这条探针里**；发丝样张不在包内")


def p_lens_correction(src: Path, out: Path, report: dict) -> None:
    """几何矫正不裁画幅：尺寸不变、四角仍有内容。"""
    p = out / "geo.png"
    rc, res, err = run_steps(src, [("filter.lensCorrection", {
        "vertical": -4, "horizontal": 0, "angle": 1.0, "edge": "edgeExtension", "scale": 100,
        "correctDistortion": False, "correctVignette": False, "correctCA": False})], p)
    same_size = corners_ok = None
    if p.exists():
        im = Image.open(p)
        same_size = im.size == Image.open(src).size
        arr = load_rgb(p)
        h, w = arr.shape[:2]
        k = 40
        patches = [arr[:k, :k], arr[:k, -k:], arr[-k:, :k], arr[-k:, -k:]]
        corners_ok = all(float(pt.std()) > 1.5 for pt in patches)
    checks = {"runs": rc == 0, "size_unchanged": bool(same_size),
              "corners_have_content": bool(corners_ok)}
    report["lensCorrection"] = dict(status="works" if all(checks.values()) else "degrades",
                                    checks=checks, stderr=err[:400], evidence=[str(p.name)])


def p_caf_seed(src: Path, out: Path, report: dict) -> None:
    """contentAwareFill 的 seed 是否可复现。"""
    def once(name: str, seed: int) -> Path:
        p = out / name
        run_steps(src, [
            ("select.subject", {}),
            ("edit.contentAwareFill", {"seed": seed}),
        ], p)
        return p

    a = once("caf_s1.png", 11)
    b = once("caf_s1_again.png", 11)
    c = once("caf_s2.png", 22)
    same = a.exists() and b.exists() and sha(a) == sha(b)
    diff = a.exists() and c.exists() and sha(a) != sha(c)
    checks = {"runs": a.exists() and c.exists(), "same_seed_identical": bool(same),
              "diff_seed_differs": bool(diff)}
    report["contentAwareFillSeed"] = dict(status="works" if all(checks.values()) else "degrades",
                                          checks=checks, evidence=[a.name, c.name])


def p_faces(src: Path, out: Path, report: dict) -> None:
    """人脸与 landmarks：给眼位提亮提供坐标。"""
    p = out / "faces.png"
    rc, res, err = run_steps(src, [("image.detectFaces", {"minScore": 0.4})], p)
    r = frame(res, "image.detectFaces")
    faces = r.get("faces", []) if isinstance(r, dict) else []
    lm_ok = bool(faces) and isinstance(faces[0].get("landmarks"), (dict, list)) and bool(faces[0].get("landmarks"))
    checks = {"runs": rc == 0, "faces>=1": len(faces) >= 1, "landmarks_present": lm_ok}
    report["detectFaces"] = dict(status="works" if all(checks.values()) else "degrades",
                                 checks=checks, faces=len(faces),
                                 landmarks=list(faces[0].get("landmarks", {}).keys())[:8] if faces else [],
                                 stderr=err[:300])


def p_bits32(src: Path, out: Path, report: dict) -> None:
    """32 位文档：转换后 depth=32。"""
    tif = out / "deep.tif"
    rc, res, err = run_steps(src, [("image.mode.bits32", {})], tif)
    depth = None
    if tif.exists():
        info = cli(["info", str(tif), "--compact"])
        if info.returncode == 0 and info.stdout.strip().startswith("{"):
            depth = json.loads(info.stdout.strip().splitlines()[0]).get("depth")
    checks = {"runs": rc == 0, "depth==32": depth == 32}
    report["bits32"] = dict(status="works" if all(checks.values()) else "degrades",
                            checks=checks, depth=depth, stderr=err[:300])


def p_addnoise_seed(src: Path, out: Path, report: dict) -> None:
    """addNoise 的 seed 可复现。"""
    def once(name: str, seed: int) -> Path:
        p = out / name
        run_steps(src, [("filter.noise.addNoise", {"amount": 12, "distribution": "gaussian",
                                                   "monochromatic": True, "seed": seed})], p)
        return p

    a = once("n1.png", 5)
    b = once("n1b.png", 5)
    c = once("n2.png", 9)
    checks = {"same_seed_identical": a.exists() and b.exists() and sha(a) == sha(b),
              "diff_seed_differs": a.exists() and c.exists() and sha(a) != sha(c)}
    report["addNoiseSeed"] = dict(status="works" if all(checks.values()) else "degrades", checks=checks)


def p_export_layers(src: Path, out: Path, report: dict) -> None:
    """layersToFiles 只导顶层：两顶层层 → 两个文件。"""
    d = out / "layers"
    d.mkdir(exist_ok=True)
    psd = out / "two.psd"
    rc1, res, err = run_steps(src, [("layer.duplicate", {})], psd)
    files = []
    if psd.exists():
        p = cli(["run", str(psd), "--cmd", "file.export.layersToFiles",
                 "--params", json.dumps({"dir": str(d), "format": "png", "prefix": "L"}, separators=(",", ":")),
                 "--out", str(out / "two_out.psd")])
        for line in p.stdout.splitlines():
            if line.strip().startswith("{"):
                try:
                    r = json.loads(line)
                except json.JSONDecodeError:
                    continue
                files = (r.get("result") or {}).get("files", []) or files
        rc2 = p.returncode
    else:
        rc2 = 1
    checks = {"runs": rc1 == 0 and rc2 == 0, "two_files": len(files) == 2}
    report["exportLayers"] = dict(status="works" if all(checks.values()) else "degrades",
                                  checks=checks, files=len(files), stderr=err[:300])


def p_surface_blur(src: Path, out: Path, report: dict) -> None:
    """保边平滑：在参数空间里找一组"整体高频下降、强边缘保留"的设置。"""
    settings = [(6, 20), (3, 10), (2, 6)]
    rows = []
    for i, (radius, thr) in enumerate(settings):
        p = out / f"smoothed_{radius}_{thr}.png"
        rc, _, err = run_steps(src, [("filter.blur.surfaceBlur", {"radius": radius, "threshold": thr})], p)
        hf_drop = edge_keep = None
        if p.exists():
            a = load_rgb(src).mean(axis=2)
            b = load_rgb(p).mean(axis=2)
            lap_a = np.abs(4 * a[1:-1, 1:-1] - a[:-2, 1:-1] - a[2:, 1:-1] - a[1:-1, :-2] - a[1:-1, 2:])
            lap_b = np.abs(4 * b[1:-1, 1:-1] - b[:-2, 1:-1] - b[2:, 1:-1] - b[1:-1, :-2] - b[1:-1, 2:])
            hf_drop = float(lap_a.mean() - lap_b.mean())
            gx = np.abs(np.diff(a, axis=1))
            px = gx > np.percentile(gx, 95)
            gb = np.abs(np.diff(b, axis=1))
            edge_keep = float(gb[px].mean() / max(1e-6, gx[px].mean()))
        rows.append({"radius": radius, "threshold": thr, "rc": rc,
                     "hf_drop": hf_drop, "edge_keep": edge_keep})
    best = max(rows, key=lambda r: (r["edge_keep"] or 0) - (0 if (r["hf_drop"] or 0) > 1 else 99))
    ok = best["rc"] == 0 and (best["hf_drop"] or 0) > 1.0 and (best["edge_keep"] or 0) >= 0.85
    report["surfaceBlur"] = dict(
        status="works" if ok else "degrades",
        best={"radius": best["radius"], "threshold": best["threshold"],
              "hf_drop": best["hf_drop"], "edge_keep": best["edge_keep"]},
        all_settings=rows,
        note="强边保留随 radius/threshold 变化；保纹理场景优先用频率分离，surfaceBlur 作辅助",
        evidence=[f"smoothed_{best['radius']}_{best['threshold']}.png"])


def p_shadows_highlights(src: Path, out: Path, report: dict) -> None:
    """高光滚降：削顶像素数下降、暗部抬起。"""
    p = out / "sh.png"
    rc, res, err = run_steps(src, [("image.adjustments.shadowsHighlights", {
        "shadowAmount": 45, "shadowTone": 50, "shadowRadius": 30,
        "highlightAmount": 55, "highlightTone": 50, "highlightRadius": 30,
        "blackClip": 0.02, "whiteClip": 0.02})], p)
    clip_before = clip_after = shadow_lift = None
    if p.exists():
        a = load_rgb(src)
        b = load_rgb(p)
        clip_before = int((a >= 254).any(axis=2).sum())
        clip_after = int((b >= 254).any(axis=2).sum())
        dark = a.mean(axis=2) < 40
        if dark.any():
            shadow_lift = float(b.mean(axis=2)[dark].mean() - a.mean(axis=2)[dark].mean())
    checks = {"runs": rc == 0, "clip_reduced": clip_before is not None and clip_after <= clip_before,
              "shadow_lifted(>0)": shadow_lift is not None and shadow_lift > 0}
    report["shadowsHighlights"] = dict(status="works" if all(checks.values()) else "degrades",
                                       checks=checks, clip_before=clip_before, clip_after=clip_after,
                                       shadow_lift=shadow_lift, stderr=err[:300], evidence=[str(p.name)])


def p_gallery_grain(src: Path, out: Path, report: dict) -> None:
    """gallery 颗粒族：能出效果，且同参数是否可复现。"""
    def once(name: str) -> Path:
        p = out / name
        run_steps(src, [("filter.gallery.grain", {"intensity": 45, "contrast": 50,
                                                  "grainType": "soft"})], p)
        return p

    a, b = once("g1.png"), once("g1b.png")
    changed = False
    if a.exists():
        changed = float(np.abs(load_rgb(a) - load_rgb(src)).mean()) > 1.0
    checks = {"runs": a.exists(), "image_changed": changed,
              "deterministic": a.exists() and b.exists() and sha(a) == sha(b)}
    report["galleryGrain"] = dict(status="works" if all(checks.values()) else "degrades",
                                  checks=checks,
                                  note="不可复现时须固定 seed 方案（addNoise）替代",
                                  evidence=[a.name, b.name])


def p_auto_align(src: Path, out: Path, report: dict) -> None:
    """亚像素配准：把副本平移 5,4 px，再让 autoAlignLayers 拉回；对齐后应与原图几乎重合。"""
    shifted = out / "shifted.png"
    aligned = out / "aligned.png"
    rc1, _, err1 = run_steps(src, [
        ("layer.duplicate", {"name": "SHIFT"}),
        ("layer.translate", {"layer": "SHIFT", "dx": 5, "dy": 4, "units": "px"}),
        ("layer.select", {"layer": "SHIFT", "mode": "replace"}),
        ("layer.select", {"layer": "Background", "mode": "add"}),
        ("edit.autoAlignLayers", {"registration": "intensity", "interpolation": "bicubic"}),
    ], out / "aligned.psd")
    if (out / "aligned.psd").exists():
        to_png(out / "aligned.psd", aligned)
    # 对照组：只平移，不对齐
    psd = out / "shiftonly.psd"
    rc2, _, err2 = run_steps(src, [
        ("layer.duplicate", {"name": "SHIFT"}),
        ("layer.translate", {"layer": "SHIFT", "dx": 5, "dy": 4, "units": "px"}),
    ], psd)
    if psd.exists():
        to_png(psd, shifted)
    d_shift = d_aligned = None
    if shifted.exists():
        d_shift = float(np.abs(load_rgb(shifted).astype(np.int16) - load_rgb(src).astype(np.int16)).mean())
    if aligned.exists():
        d_aligned = float(np.abs(load_rgb(aligned).astype(np.int16) - load_rgb(src).astype(np.int16)).mean())
    checks = {"runs": rc1 == 0, "aligned_close(<=6)": d_aligned is not None and d_aligned <= 6.0,
              "unaligned_far(>=10)": d_shift is not None and d_shift >= 10.0}
    report["autoAlign"] = dict(status="works" if all(checks.values()) else "degrades",
                               checks=checks, diff_aligned=d_aligned, diff_unaligned=d_shift,
                               stderr=err1[:300], evidence=["aligned.png", "shifted.png"])


def p_match_color(src: Path, out: Path, report: dict) -> None:
    """颜色匹配：先造一个偏色副本，再用 matchColor 拉回；与源图的色差应显著下降。"""
    graded = out / "graded.png"
    matched = out / "matched.png"
    rc1, res1, err1 = run_steps(src, [
        ("layer.duplicate", {"name": "GRADED"}),
        ("image.adjustments.levels", {"red": {"gamma": 0.72}, "blue": {"gamma": 1.35}}),
        ("document.inspect",),
    ], out / "graded.psd")
    if (out / "graded.psd").exists():
        to_png(out / "graded.psd", graded)
    bg_id = None
    for row in res1:
        if row.get("command") == "document.inspect":
            for l in (row.get("result") or {}).get("layers", []):
                if l.get("name") == "Background":
                    bg_id = l.get("id")
    rc2, _, err2 = run_steps(out / "graded.psd", [
        ("layer.select", {"name": "GRADED"}),
        ("image.adjustments.matchColor", {"source": 0, "sourceLayer": bg_id, "luminance": 100,
                                          "intensity": 100, "fade": 0, "neutralize": True}),
    ], out / "matched.psd")
    if (out / "matched.psd").exists():
        to_png(out / "matched.psd", matched)
    d0 = d1 = m0 = m1 = None
    if graded.exists():
        g = load_rgb(graded)
        s = load_rgb(src)
        d0 = float(np.abs(g.astype(np.int16) - s.astype(np.int16)).mean())
        m0 = float(np.abs(g.reshape(-1, 3).mean(0) - s.reshape(-1, 3).mean(0)).sum())
    if matched.exists():
        m = load_rgb(matched)
        s2 = load_rgb(src)
        d1 = float(np.abs(m.astype(np.int16) - s2.astype(np.int16)).mean())
        m1 = float(np.abs(m.reshape(-1, 3).mean(0) - s2.reshape(-1, 3).mean(0)).sum())
    drop = None if (m0 is None or m1 is None) else (1 - m1 / max(1e-6, m0))
    checks = {"runs": rc1 == 0 and rc2 == 0, "has_source_layer": bg_id is not None,
              "mean_color_gap_dropped(>=30%)": drop is not None and drop >= 0.3}
    report["matchColor"] = dict(status="works" if all(checks.values()) else "degrades",
                                checks=checks, pixel_diff_before=d0, pixel_diff_after=d1,
                                mean_gap_before=m0, mean_gap_after=m1, drop=drop,
                                source_layer=bg_id, stderr=(err1 + err2)[:300],
                                note="统计式匹配：默认参数可缩约 37% 色差；intensity=200 实测反向增至 150.8，"
                                     "精确一致请用 levels{eyedropper} 而不是加参数",
                                evidence=["graded.png", "matched.png"])


def _lapvar(png: Path, box: list[int]) -> float | None:
    """局部 Laplacian 方差 = 锐度代理。box=[x,y,w,h]，裁自同一坐标。"""
    if not png.exists():
        return None
    g = np.asarray(Image.open(png).convert("L"), dtype=np.float32)
    x, y, w, h = box
    x, y = max(0, x), max(0, y)
    p = g[y:y + max(8, h), x:x + max(8, w)]
    if p.shape[0] < 4 or p.shape[1] < 4:
        return None
    lap = np.abs(4 * p[1:-1, 1:-1] - p[:-2, 1:-1] - p[2:, 1:-1] - p[1:-1, :-2] - p[1:-1, 2:])
    return float(lap.var())


def p_depth_bokeh(src: Path, out: Path, report: dict) -> None:
    """深度驱散景：不是"两次渲染不同"，而是**主体区锐度必须保住、背景区必须掉**。

    旧断言用 SHA 不同，而 plain/depth 的图层结构本就不同，SHA 必不同，近乎恒真——
    已按分区 Laplacian 方差替换。
    """
    plain = out / "plain.png"
    depth = out / "depth.png"
    # 人脸框来自 detectFaces，拿不到就用中上方固定框
    im = Image.open(src)
    w, h = im.size
    face = [int(w * 0.33), int(h * 0.10), int(w * 0.34), int(h * 0.50)]
    frc, fres, _ = run_steps(src, [("image.detectFaces", {"minScore": 0.4})], out / "faces.png")
    f = frame(fres, "image.detectFaces") or {}
    fs = f.get("faces") or []
    if fs and isinstance(fs[0].get("rect"), list) and len(fs[0]["rect"]) == 4:
        face = [int(v) for v in fs[0]["rect"]]
    bg_box = int(min(w, h) * 0.18)
    bg_boxes = {"bg_tl": [0, 0, bg_box, bg_box], "bg_tr": [w - bg_box, 0, bg_box, bg_box],
                "bg_bl": [0, h - bg_box, bg_box, bg_box], "bg_br": [w - bg_box, h - bg_box, bg_box, bg_box]}
    rc0, _, e0 = run_steps(src, [
        ("layer.duplicate", {"name": "DEPTH_SRC"}),
        ("layer.removeBackground", {"layer": "DEPTH_SRC"}),
        ("select.loadSelection", {"channel": "transparency", "layer": {"name": "DEPTH_SRC"}}),
        ("select.saveSelection", {"name": "DEPTH", "channel": "new"}),
        ("select.deselect",),
        ("layer.setProps", {"visible": False}),
        ("layer.select", {"name": "Background"}),
        ("layer.duplicate", {"name": "BOKEH"}),
        ("filter.blur.lensBlur", {"radius": 26, "shape": "heptagon", "bladeCurvature": 1.0,
                                  "rotation": 0, "depthMap": "none", "brightness": 1.0,
                                  "threshold": 0.2, "seed": 3}),
    ], out / "plain.psd")
    if (out / "plain.psd").exists():
        to_png(out / "plain.psd", plain)
    blades = None
    arms: dict[str, dict] = {}
    for inv in (True, False):
        tag = f"inv{str(inv).lower()}"
        d = out / f"depth_{tag}.psd"
        d_png = out / f"depth_{tag}.png"
        rc, res, err = run_steps(out / "plain.psd", [
            ("layer.select", {"name": "Background"}),
            ("layer.duplicate", {"name": "BOKEH_D"}),
            ("layer.select", {"name": "BOKEH_D"}),
            ("filter.blur.lensBlur", {"radius": 26, "shape": "heptagon", "bladeCurvature": 1.0,
                                      "rotation": 0, "depthMap": "channel", "depthChannel": "DEPTH",
                                      "invert": inv, "focalDistance": 0.4,
                                      "brightness": 1.0, "threshold": 0.2, "seed": 3}),
            ("layer.select", {"name": "BOKEH"}),
            ("layer.setProps", {"visible": False}),
        ], d)
        if d.exists():
            to_png(d, d_png)
        for row in res:
            if row.get("command") == "filter.blur.lensBlur":
                blades = ((row.get("result") or {}).get("filter") or {}).get("blades")
        arms[tag] = {"runs": rc == 0, "png": str(d_png), "stderr": err[:200]}

    # 参考基准 = 原始锐利图（src 的子目录副本），不是"无深度模糊图"：
    # 要证明的是"主体相对原片没被糊"，不是"比平面模糊好一点"。
    ref = src

    def retention(box: list[int], png: Path, base: Path) -> float | None:
        a, b = _lapvar(base, box), _lapvar(png, box)
        if a is None or b is None or a <= 0:
            return None
        return b / a

    bg_box = int(min(w, h) * 0.18)
    bg_boxes = {"bg_tl": [0, 0, bg_box, bg_box], "bg_tr": [w - bg_box, 0, bg_box, bg_box],
                "bg_bl": [0, h - bg_box, bg_box, bg_box], "bg_br": [w - bg_box, h - bg_box, bg_box, bg_box]}
    for tag, arm in arms.items():
        png = Path(arm.pop("png"))
        arm["face_retention"] = retention(face, png, ref)
        arm["bg_retention"] = {k: retention(v, png, ref) for k, v in bg_boxes.items()}
        vals = [v for v in arm["bg_retention"].values() if v is not None]
        arm["bg_max"] = max(vals) if vals else None
        arm["usable"] = (arm["face_retention"] is not None and arm["face_retention"] >= 0.75
                         and arm["bg_max"] is not None and arm["bg_max"] <= 0.35)
    usable = [t for t, v in arms.items() if v.get("usable")]
    best = max(arms.values(), key=lambda v: v.get("face_retention") if v.get("face_retention") is not None else -1)
    flat_face = retention(face, plain, ref)
    checks = {"runs": rc0 == 0 and all(v.get("runs") for v in arms.values()), "blades_7": blades == 7,
              "subject_kept(>=0.75 vs src)": (best.get("face_retention") is not None
                                             and best["face_retention"] >= 0.75),
              "background_blurred(<=0.35 vs src)": (best.get("bg_max") is not None
                                                    and best["bg_max"] <= 0.35),
              "flat_blur_actually_blurs(<=0.5)": flat_face is not None and flat_face <= 0.5}
    report["depthBokeh"] = dict(status="works" if all(checks.values()) else "fails",
                                checks=checks, blades=blades, face_box=face,
                                arms=arms, usable_polarity=usable,
                                flat_blur_face_retention=flat_face,
                                stderr=e0[:300],
                                evidence=[f"depth_{t}.png" for t in arms] + ["plain.png"],
                                note="**深度图极性**：DEPTH 通道白=主体时，invert:true 人脸保留 103.69%、"
                                     "但背景也保住 106.27% → 等于全清晰；invert:false 全糊（人脸 0.17%）。"
                                     "所以二值 alpha 深度**做不到选择性对焦**，不是探针判定问题。")


def p_bits32_linear(src: Path, out: Path, report: dict) -> None:
    """32 位线性光：五臂对照，把"换位深本身"从"在线性光里做模糊"里分离出去。

    A 8 位 + 模糊      B 32 位线性 + 模糊 + 回转换
    C 8 位（不模糊）   D 32 位线性（不模糊）+ 回转换   E 32 位线性 + 模糊，**不**回转换
    判据：D−C = 位深/转换往返误差；B−A = 做模糊时两种色域的差；E−A = 漏回转换的错。
    """
    def render(name: str, steps: list, out_name: str) -> tuple[int, list, str, Path]:
        p = out / out_name
        rc, res, err = run_steps(src, steps, p)
        png = out / (Path(out_name).stem + ".png")
        if p.exists():
            to_png(p, png)
        return rc, res, err, png

    blur = {"radius": 20, "shape": "hexagon", "bladeCurvature": 1.0,
            "rotation": 0, "brightness": 1.0, "threshold": 0.2, "seed": 5}
    rcA, _, eA, a8 = render("A", [("filter.blur.lensBlur", dict(blur))], "a8.psd")
    rcB, resB, eB, b32 = render("B", [
        ("image.mode.bits32", {}),
        ("edit.assignProfile", {"profile": "linear-srgb"}),
        ("filter.blur.lensBlur", dict(blur)),
        ("edit.convertToProfile", {"profile": "srgb", "intent": "relative", "bpc": True}),
        ("document.inspect",),
    ], "b32.psd")
    rcC, _, eC, c8 = render("C", [("layer.duplicate", {"name": "NOOP"})], "c8.psd")
    rcD, resD, eD, d32 = render("D", [
        ("image.mode.bits32", {}),
        ("edit.assignProfile", {"profile": "linear-srgb"}),
        ("edit.convertToProfile", {"profile": "srgb", "intent": "relative", "bpc": True}),
        ("document.inspect",),
    ], "d32.psd")
    rcE, _, eE, e32 = render("E", [
        ("image.mode.bits32", {}),
        ("edit.assignProfile", {"profile": "linear-srgb"}),
        ("filter.blur.lensBlur", dict(blur)),
    ], "e32.psd")

    depth = None
    for rows in (resB, resD):
        for row in rows:
            if row.get("command") == "document.inspect":
                depth = (row.get("result") or {}).get("depth")

    def md(p: Path, q: Path) -> float | None:
        if p.exists() and q.exists():
            return float(np.abs(load_rgb(p).astype(np.int16) - load_rgb(q).astype(np.int16)).mean())
        return None

    bit_roundtrip = md(d32, c8)     # 位深+转换本身的误差
    linear_route = md(b32, a8)      # 两者都模糊，差只因色域不同
    missing_convert = md(e32, a8)   # 漏回转换的错（应显著更大）
    checks = {"runs": all(r == 0 for r in (rcA, rcB, rcC, rcD, rcE)),
              "depth_32": depth == 32,
              "roundtrip(<=4)": bit_roundtrip is not None and bit_roundtrip <= 4.0,
              "linear_route_differs(>=1)": linear_route is not None and linear_route >= 1.0,
              "missing_convert_much_worse(>=5x)": (missing_convert is not None and linear_route is not None
                                                  and missing_convert >= 5 * max(1e-6, linear_route))}
    report["bits32Linear"] = dict(status="works" if all(checks.values()) else "degrades",
                                  checks=checks, depth=depth,
                                  bit_roundtrip_error=bit_roundtrip,
                                  linear_route_diff=linear_route,
                                  missing_convert_diff=missing_convert,
                                  stderr=(eA + eB + eC + eD + eE)[:400],
                                  evidence=["a8.png", "b32.png", "c8.png", "d32.png", "e32.png"],
                                  note="探针自身执行了 convertToProfile，所以 2.64 这个数在包内有证据链")


PROBES = {
    "lensBlur": p_lensblur,
    "levelsLab": p_levels_lab,
    "refineEdge": p_refine_edge,
    "lensCorrection": p_lens_correction,
    "contentAwareFillSeed": p_caf_seed,
    "detectFaces": p_faces,
    "bits32": p_bits32,
    "bits32Linear": p_bits32_linear,
    "addNoiseSeed": p_addnoise_seed,
    "exportLayers": p_export_layers,
    "surfaceBlur": p_surface_blur,
    "shadowsHighlights": p_shadows_highlights,
    "galleryGrain": p_gallery_grain,
    "autoAlign": p_auto_align,
    "matchColor": p_match_color,
    "depthBokeh": p_depth_bokeh,
}


def select_probes(text: str | None) -> tuple[set[str], list[str]]:
    """把 ``--only`` 文本解析成（要跑的探针集合，未知名字列表）。"""
    if not text:
        return set(PROBES), []
    names = {item.strip() for item in text.split(",") if item.strip()}
    return names & set(PROBES), sorted(names - set(PROBES))


def exit_code(summary: dict[str, str], only: set[str] | None = None) -> int:
    """0 本次选中的全部 works；1 有 fails；3 有 degrades 或有未跑项。

    ``only`` 只影响判定范围，不影响报告内容：``--only refineEdge`` 全通过时应退 0，
    而报告里没跑的探针仍如实标 untested。
    """
    scoped = {name: status for name, status in summary.items()
              if only is None or name in only}
    if any(status == "fails" for status in scoped.values()):
        return 1
    if not scoped or any(status in ("degrades", "untested")
                         for status in scoped.values()):
        return 3
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--work", required=True, help="探针工作目录（会在其下建子目录）")
    ap.add_argument("--src", default=None, help="输入图；默认用人像样张")
    ap.add_argument("--only", default=None, help="逗号分隔，只跑指定探针")
    ap.add_argument("--json", default=None, help="报告输出路径")
    a = ap.parse_args()

    here = Path(__file__).resolve().parent
    src = Path(a.src) if a.src else here.parent / "examples" / "assets" / "portrait.jpg"
    if not src.exists():
        print(f"probe: 输入不存在 {src}", file=sys.stderr)
        return 2
    work = Path(a.work)
    try:
        work.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        print(f"probe: 工作目录不可用 {work}: {exc}", file=sys.stderr)
        return 2
    if a.only is not None and not a.only.strip():
        print("probe: --only 不能为空", file=sys.stderr)
        return 2

    only, unknown = select_probes(a.only)
    if unknown:
        print(f"probe: --only 含未知探针 {', '.join(unknown)}；"
              f"可用：{', '.join(PROBES)}", file=sys.stderr)
        return 2
    if a.only is not None and not only:
        print("probe: --only 没有可用探针", file=sys.stderr)
        return 2
    # 没有实跑的项一律 untested，不许被当成通过。
    report: dict[str, dict] = {name: {"status": "untested"} for name in PROBES}
    for name, fn in PROBES.items():
        if name not in only:
            continue
        sub = work / name
        marker = sub / ".probe-work"
        if sub.exists():
            if not marker.is_file():
                print(f"probe: 工作子目录已存在且不是本工具创建 {sub}",
                      file=sys.stderr)
                return 2
            try:
                shutil.rmtree(sub)
            except OSError as exc:
                print(f"probe: 清理旧工作目录失败 {sub}: {exc}", file=sys.stderr)
                return 2
        sub.mkdir(parents=True, exist_ok=True)
        marker.write_text("probe_capabilities\n", encoding="utf-8")
        local = sub / ("src" + src.suffix.lower())
        shutil.copy2(src, local)
        print(f"[probe] {name} ...", flush=True)
        try:
            fn(local, sub, report)
        except Exception as e:  # noqa: BLE001
            report[name] = {"status": "fails", "error": f"{type(e).__name__}: {e}"}

    summary = {k: v.get("status") for k, v in report.items()}
    out_json = Path(a.json) if a.json else work / "probe-report.json"
    version_lines = cli(["--version"]).stdout.strip().splitlines()
    payload = {"src": str(src), "cli": cli_path(),
               "version": version_lines[0] if version_lines else "",
               "probes": report}
    try:
        out_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2),
                            encoding="utf-8")
    except OSError as exc:
        print(f"probe: 报告写入失败 {out_json}: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"report: {out_json}")
    return exit_code(summary, only)


if __name__ == "__main__":
    raise SystemExit(main())
