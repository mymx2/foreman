#!/usr/bin/env python3
"""Offline contract test for sidecar/patch.py (gate-bounded inpainting).

  python <skill-dir>/scripts/test_sidecar_patch.py

The hard promise of patch.py is "gate 外与源逐像素相同" plus an honest manifest.
These checks drive the real CLI on synthetic images, so no PhotoCraft install is
needed. cv2-dependent checks are reported SKIP (exit stays 0) when opencv is not
installed, matching the sidecar's documented degradation.
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path


def _child_env() -> dict[str, str]:
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    return env

sys.path.insert(0, str(Path(__file__).resolve().parent / "sidecar"))

import numpy as np  # noqa: E402
from PIL import Image  # noqa: E402

import patch  # noqa: E402

PATCH = Path(__file__).resolve().parent / "sidecar" / "patch.py"


def check_load_gate() -> str | None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        grey = root / "gate.png"
        mask = np.zeros((10, 10), np.uint8)
        mask[2:6, 3:7] = 255
        mask[8, 8] = 127
        Image.fromarray(mask).save(grey)
        gate = patch.load_gate(grey, (10, 10))
        if gate.dtype != np.uint8 or gate.sum() != 16:
            return f"threshold/area wrong: {gate.sum()}"
        if gate[8, 8] != 0:
            return "127 must not pass the >127 gate"
        try:
            patch.load_gate(grey, (12, 10))
        except RuntimeError:
            pass
        else:
            return "size mismatch must raise RuntimeError"
    return None


def check_sha() -> str | None:
    with tempfile.TemporaryDirectory() as tmp:
        payload = Path(tmp) / "x.bin"
        payload.write_bytes(b"abc" * 1000)
        if patch.sha(payload) != hashlib.sha256(b"abc" * 1000).hexdigest():
            return "sha mismatch"
    return None


def _run(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(PATCH), *args],
                          capture_output=True, text=True, encoding="utf-8",
                          errors="replace", env=_child_env())


def check_cli_contract() -> str | None:
    if patch.cv2 is None:
        return "SKIP"
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        rng = np.random.default_rng(11)
        image = rng.integers(0, 255, (48, 48, 3), dtype=np.uint8)
        src = root / "src.png"
        Image.fromarray(image).save(src)
        mask = np.zeros((48, 48), np.uint8)
        mask[18:30, 18:30] = 255
        gate = root / "gate.png"
        Image.fromarray(mask).save(gate)
        out = root / "out"
        done = _run("--src", str(src), "--gate", str(gate), "--out", str(out))
        if done.returncode != 0:
            return f"exit={done.returncode}: {done.stderr[-300:]}"
        manifest = json.loads((out / "manifest.json").read_text("utf-8"))
        if not manifest["passed"] or not manifest["checks"]["outside_untouched"]:
            return f"checks failed: {manifest['checks']}"
        if manifest["gate"]["area"] != 144:
            return f"gate area={manifest['gate']['area']}"
        if manifest["changed_inside_pixels"] <= 0:
            return "inpaint changed nothing inside the gate"
        patched = np.asarray(Image.open(out / "patched.png").convert("RGB"), np.uint8)
        keep = mask == 0
        if np.abs(patched[keep].astype(np.int16) - image[keep].astype(np.int16)).max() != 0:
            return "pixels outside the gate changed"
        if patched.shape != image.shape:
            return f"shape drift: {patched.shape}"
    return None


def check_alpha_overlap_is_failure() -> str | None:
    if patch.cv2 is None:
        return "SKIP"
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        image = np.full((32, 32, 3), 200, np.uint8)
        src = root / "src.png"
        Image.fromarray(image).save(src)
        mask = np.zeros((32, 32), np.uint8)
        mask[12:20, 12:20] = 255
        gate = root / "gate.png"
        Image.fromarray(mask).save(gate)
        alpha = np.zeros((32, 32), np.uint8)
        alpha[12:20, 12:20] = 255
        alpha_path = root / "alpha.png"
        Image.fromarray(alpha).save(alpha_path)
        out = root / "out"
        done = _run("--src", str(src), "--gate", str(gate), "--out", str(out),
                    "--alpha", str(alpha_path))
        if done.returncode != 1:
            return f"overlap must exit 1, got {done.returncode}"
        manifest = json.loads((out / "manifest.json").read_text("utf-8"))
        if manifest["checks"]["gate_disjoint_from_subject"]:
            return "manifest claims disjoint despite overlap"
        if manifest["passed"]:
            return "manifest passed despite overlap"
    return None


def check_lama_is_refused() -> str | None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        src = root / "src.png"
        Image.fromarray(np.zeros((8, 8, 3), np.uint8)).save(src)
        gate = root / "gate.png"
        mask = np.zeros((8, 8), np.uint8)
        mask[2:5, 2:5] = 255
        Image.fromarray(mask).save(gate)
        done = _run("--src", str(src), "--gate", str(gate),
                    "--out", str(root / "out"), "--engine", "lama-onnx")
        if done.returncode != 1 or "未接线" not in done.stderr:
            return f"lama-onnx should fail honestly: rc={done.returncode}"
    return None


def main() -> int:
    checks = [
        ("load_gate threshold and size guard", check_load_gate),
        ("sha256 helper", check_sha),
        ("cli keeps pixels outside the gate intact", check_cli_contract),
        ("gate/alpha overlap is a hard failure", check_alpha_overlap_is_failure),
        ("lama-onnx is refused, not simulated", check_lama_is_refused),
    ]
    failed, skipped = [], 0
    for name, fn in checks:
        detail = fn()
        if detail == "SKIP":
            skipped += 1
            print(f"SKIP  {name}")
            continue
        print(f"{'FAIL' if detail else 'PASS'}  {name}" + (f": {detail}" if detail else ""))
        if detail:
            failed.append(name)
    print(f"\n{len(checks) - len(failed) - skipped} passed, {len(failed)} failed, "
          f"{skipped} skipped")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
