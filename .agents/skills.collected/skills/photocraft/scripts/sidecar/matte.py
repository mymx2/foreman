#!/usr/bin/env python3
"""侧车抠像入口：产出一份符合交接契约的 cutout.png + manifest.json。

契约（配套 references/capability-matrix.md）：
- cutout.png：RGB + **straight alpha（非预乘）**，画布与原片完全一致（不裁边），8 或 16 bit。
- manifest.json：schema=photocraft.sidecar/1，记录**实际跑的引擎**、运行时版本、源文件哈希。
- 铁律：降级必须如实写进 manifest.engine。跑了 select.subject 就写 photocraft.select.subject，
  不许写成 pymatting / IS-Net。

用法：
    python scripts/sidecar/matte.py --src 人像.jpg --out DIR
    python scripts/sidecar/matte.py --src 人像.jpg --out DIR --trimap tri.png   # 走 pymatting CFM

引擎：
    pymatting   需要 --trimap（0/128/255 三值图）且已装 pymatting + opencv
    photocraft  回退：select.subject → select.refineEdge{output:"layerMask"} → 导出 RGBA
    auto        有 trimap 且依赖齐 → pymatting；否则 photocraft

退出码：0 成功；1 失败；2 依赖缺失且无法降级。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

try:
    import numpy as np
    from PIL import Image
except Exception:  # noqa: BLE001
    print("matte: 需要 numpy + Pillow（pip install -r scripts/requirements.txt）", file=sys.stderr)
    raise SystemExit(2)

CLI_CANDIDATES = [r"C:\Program Files\PhotoCraft\photocraft-cli.exe", "photocraft-cli"]


def find_cli() -> str | None:
    for c in CLI_CANDIDATES:
        if Path(c).exists() or shutil.which(c):
            return c
    return None


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def alpha_stats(alpha: np.ndarray) -> dict:
    a = alpha.astype(np.float32) / 255.0
    solid = a > 0
    return {
        "mean": round(float(a.mean()), 4),
        "opaque_ratio": round(float((a > 0.97).mean()), 4),
        "soft_ratio": round(float(((a > 0.04) & (a < 0.96)).sum() / max(1, solid.sum())), 4),
        "transparent_ratio": round(float((a < 0.02).mean()), 4),
    }


def run_photocraft(cli: str, src: Path, outdir: Path) -> tuple[Path, dict]:
    psd = outdir / "matte.psd"
    png = outdir / "cutout.png"
    params = {"radius": 2, "smartRadius": True, "smooth": 30, "feather": 1,
              "contrast": 10, "shiftEdge": 0, "decontaminate": True,
              "amount": 100, "output": "layerMask"}
    cmd = [cli, "run", str(src),
           "--cmd", "select.subject", "--params", "{}",
           "--cmd", "select.refineEdge", "--params", json.dumps(params, separators=(",", ":")),
           "--out", str(psd)]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    if r.returncode != 0 or not psd.exists():
        raise RuntimeError(f"photocraft 抠像失败: rc={r.returncode} {r.stderr[:300]}")
    c = subprocess.run([cli, "convert", str(psd), str(png)], capture_output=True, text=True, timeout=300)
    if c.returncode != 0 or not png.exists():
        raise RuntimeError(f"导出 PNG 失败: {c.stderr[:300]}")
    return png, {"engine": "photocraft.select.subject+refineEdge", "params": params}


def run_pymatting(src: Path, trimap: Path, outdir: Path) -> tuple[Path, dict]:
    try:
        from pymatting import estimate_alpha_cf, estimate_foreground_ml
    except Exception as e:  # noqa: BLE001
        raise RuntimeError(f"pymatting 不可用: {e}") from e

    img = np.asarray(Image.open(src).convert("RGB"), dtype=np.float64) / 255.0
    tri = np.asarray(Image.open(trimap).convert("L"), dtype=np.uint8)
    if tri.shape != img.shape[:2]:
        raise RuntimeError(f"trimap 尺寸 {tri.shape} 与原片 {img.shape[:2]} 不一致")
    if not np.isin(np.unique(tri), [0, 128, 255]).all():
        raise RuntimeError("trimap 必须是 0/128/255 三值图")
    tri_f = tri.astype(np.float64) / 255.0  # pymatting 要 0 / 0.5 / 1
    alpha = estimate_alpha_cf(img, tri_f)
    fg = estimate_foreground_ml(img, alpha)
    rgba = np.dstack([np.clip(fg, 0, 1), np.clip(alpha, 0, 1)])
    png = outdir / "cutout.png"
    Image.fromarray((rgba * 255).round().astype(np.uint8), mode="RGBA").save(png)
    return png, {"engine": "pymatting.cfm+estimate_foreground_ml",
                 "params": {"trimap": str(trimap)}}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--engine", choices=["auto", "pymatting", "photocraft"], default="auto")
    ap.add_argument("--trimap", default=None)
    a = ap.parse_args()

    src = Path(a.src)
    if not src.exists():
        print(f"matte: 源文件不存在 {src}", file=sys.stderr)
        return 2
    outdir = Path(a.out)
    outdir.mkdir(parents=True, exist_ok=True)

    notes: list[str] = []
    engine = a.engine
    if engine in ("auto", "pymatting") and a.trimap:
        try:
            png, meta = run_pymatting(src, Path(a.trimap), outdir)
        except Exception as e:  # noqa: BLE001
            if engine == "pymatting":
                print(f"matte: {e}", file=sys.stderr)
                return 1
            notes.append(f"pymatting 失败，降级 photocraft：{e}")
            engine = "photocraft"
    else:
        if engine in ("auto", "pymatting"):
            notes.append("未提供 --trimap，CFM 无三值图可用，按契约降级 photocraft")
        engine = "photocraft"

    if engine == "photocraft":
        cli = find_cli()
        if cli is None:
            print("matte: 找不到 photocraft-cli，且无 pymatting 路径", file=sys.stderr)
            return 2
        try:
            png, meta = run_photocraft(cli, src, outdir)
        except Exception as e:  # noqa: BLE001
            print(f"matte: {e}", file=sys.stderr)
            return 1

    alpha = np.asarray(Image.open(png).convert("RGBA"))[..., 3]
    stats = alpha_stats(alpha)
    manifest = {
        "schema": "photocraft.sidecar/1",
        "source": {"path": str(src), "sha256": sha256(src),
                   "width": Image.open(src).size[0], "height": Image.open(src).size[1]},
        "runtime": {"python": sys.version.split()[0], "numpy": np.__version__,
                    "pillow": Image.__version__},
        "engine": meta["engine"],
        "engine_params": meta.get("params", {}),
        "alpha": stats,
        "degraded": engine == "photocraft" and a.engine != "photocraft",
        "notes": notes,
        "created": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
    }
    (outdir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"cutout": str(png), "manifest": str(outdir / "manifest.json"),
                      "engine": manifest["engine"], "alpha": stats,
                      "degraded": manifest["degraded"], "notes": notes}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
