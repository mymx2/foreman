#!/usr/bin/env python3
"""Self-test for the pure math behind probe_capabilities.py and the sidecar helpers.

  python <skill-dir>/scripts/test_probe_math.py

No PhotoCraft install is needed: probe_capabilities resolves the CLI lazily, so
importing it only touches numpy/Pillow. These checks pin the numbers that feed
capability-matrix verdicts (srgb_to_lab / _lapvar / alpha_stats) plus the probe
selection and exit-code contract.

Exit codes: 0 all checks passed, 1 one or more checks failed.
"""
from __future__ import annotations

import contextlib
import io
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from unittest import mock


def _child_env() -> dict[str, str]:
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    return env

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent / "sidecar"))

import numpy as np  # noqa: E402
from PIL import Image  # noqa: E402

import make_trimap  # noqa: E402
import matte  # noqa: E402
import probe_capabilities as probe  # noqa: E402


def check_srgb_to_lab() -> str | None:
    rgb = np.array([[[255, 255, 255], [0, 0, 0], [128, 128, 128],
                     [255, 0, 0]]], dtype=np.float32)
    lab = probe.srgb_to_lab(rgb)
    white, black, gray, red = lab[0]
    if abs(float(white[0]) - 100.0) > 0.05:
        return f"white L={white[0]:.3f}"
    if max(abs(float(white[1])), abs(float(white[2]))) > 0.05:
        return f"white a/b={white[1]:.3f}/{white[2]:.3f}"
    if abs(float(black[0])) > 0.05:
        return f"black L={black[0]:.3f}"
    if abs(float(gray[0]) - 53.585) > 0.6:
        return f"gray L={gray[0]:.3f}"
    if abs(float(red[0]) - 53.24) > 0.6:
        return f"red L={red[0]:.3f}"
    if abs(float(red[1]) - 80.09) > 1.0 or abs(float(red[2]) - 67.20) > 1.0:
        return f"red a/b={red[1]:.3f}/{red[2]:.3f}"
    return None


def check_lapvar() -> str | None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        flat = root / "flat.png"
        Image.fromarray(np.full((32, 32), 128, np.uint8)).save(flat)
        value = probe._lapvar(flat, [0, 0, 32, 32])
        if value != 0.0:
            return f"flat lapvar={value}"
        noisy = root / "noisy.png"
        rng = np.random.default_rng(7)
        Image.fromarray(rng.integers(0, 255, (32, 32), dtype=np.uint8)).save(noisy)
        if not probe._lapvar(noisy, [0, 0, 32, 32]) or probe._lapvar(
                noisy, [0, 0, 32, 32]) <= 0:
            return "noisy lapvar should be > 0"
        if probe._lapvar(root / "missing.png", [0, 0, 32, 32]) is not None:
            return "missing file should return None"
        tiny = root / "tiny.png"
        Image.fromarray(np.zeros((2, 2), np.uint8)).save(tiny)
        if probe._lapvar(tiny, [0, 0, 2, 2]) is not None:
            return "2x2 image should return None"
        # box 超出画布时按实际存在的区域裁，不抛错
        if probe._lapvar(flat, [100, 100, 32, 32]) is not None:
            return "off-canvas box should return None"
    return None


def check_alpha_stats() -> str | None:
    transparent = matte.alpha_stats(np.zeros((4, 4), np.uint8))
    if transparent != {"mean": 0.0, "opaque_ratio": 0.0, "soft_ratio": 0.0,
                       "transparent_ratio": 1.0}:
        return f"transparent={transparent}"
    opaque = matte.alpha_stats(np.full((4, 4), 255, np.uint8))
    if opaque != {"mean": 1.0, "opaque_ratio": 1.0, "soft_ratio": 0.0,
                  "transparent_ratio": 0.0}:
        return f"opaque={opaque}"
    half = np.zeros((4, 4), np.uint8)
    half[:2] = 255
    stats = matte.alpha_stats(half)
    if stats["mean"] != 0.5 or stats["opaque_ratio"] != 0.5 \
            or stats["transparent_ratio"] != 0.5:
        return f"half={stats}"
    soft = matte.alpha_stats(np.full((4, 4), 128, np.uint8))
    if soft["soft_ratio"] != 1.0 or soft["opaque_ratio"] != 0.0:
        return f"soft={soft}"
    return None


def check_probe_selection() -> str | None:
    selected, unknown = probe.select_probes(None)
    if selected != set(probe.PROBES) or unknown:
        return "empty --only should select every probe"
    selected, unknown = probe.select_probes("levelsLab,contentAwareFill")
    if selected != {"levelsLab"} or unknown != ["contentAwareFill"]:
        return f"unknown detection broken: {selected}/{unknown}"
    selected, unknown = probe.select_probes("levelsLab,contentAwareFillSeed")
    if selected != {"levelsLab", "contentAwareFillSeed"} or unknown:
        return f"valid selection broken: {selected}/{unknown}"
    return None


def check_matrix_probe_names() -> str | None:
    """capability-matrix 的探针名必须与 PROBES 一一对应（同名陷阱曾让报告空转）。"""
    matrix = Path(__file__).resolve().parent.parent / "references" / "capability-matrix.md"
    rows = []
    in_section = False
    for line in matrix.read_text("utf-8").splitlines():
        if line.startswith("## 2."):
            in_section = True
            continue
        if in_section and line.startswith("## "):
            break
        if in_section and line.startswith("| `"):
            rows.append(line.split("`")[1])
    if len(rows) != len(probe.PROBES):
        return f"{len(rows)} matrix rows vs {len(probe.PROBES)} probes"
    missing = sorted(set(probe.PROBES) - set(rows))
    extra = sorted(set(rows) - set(probe.PROBES))
    if missing or extra:
        return f"missing={missing} extra={extra}"
    return None


def check_exit_codes() -> str | None:
    cases = [
        ({"a": "works", "b": "works"}, None, 0),
        ({"a": "works", "b": "degrades"}, None, 3),
        ({"a": "works", "b": "untested"}, None, 3),
        ({"a": "works", "b": "untested"}, {"a"}, 0),
        ({"a": "works", "b": "fails"}, {"b"}, 1),
        ({"a": "works", "b": "degrades"}, {"a"}, 0),
        ({}, None, 3),
    ]
    for summary, only, expected in cases:
        got = probe.exit_code(summary, only)
        if got != expected:
            return f"exit_code({summary}, {only})={got}, expected {expected}"
    return None


def check_erode_dilate() -> str | None:
    mask = np.zeros((9, 9), np.uint8)
    mask[4, 4] = 1
    grown = make_trimap.erode_dilate(mask, 3, grow=True)
    eroded = make_trimap.erode_dilate(mask, 3, grow=False)
    if make_trimap.cv2 is None:
        # 没 cv2 时按契约原样返回，由调用方决定
        if grown.sum() != 1 or eroded.sum() != 1:
            return "without cv2 erode_dilate must be identity"
        return None
    if grown.sum() <= 1:
        return f"dilate did not grow: {grown.sum()}"
    if eroded.sum() != 0:
        return f"erode did not shrink: {eroded.sum()}"
    return None


PROBE_SCRIPT = Path(__file__).resolve().parent / "probe_capabilities.py"
TRIMAP_SCRIPT = Path(__file__).resolve().parent / "sidecar" / "make_trimap.py"


def check_main_rejects_unknown_only() -> str | None:
    """``--only`` 写错名字必须在 main() 里退 2，而不是空报告退 0。"""
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        src = root / "src.png"
        Image.fromarray(np.zeros((8, 8, 3), np.uint8)).save(src)
        done = subprocess.run(
            [sys.executable, str(PROBE_SCRIPT), "--work", str(root / "work"),
             "--src", str(src), "--only", "nope"],
            capture_output=True, text=True, encoding="utf-8",
            errors="replace", env=_child_env())
        if done.returncode != 2:
            return f"unknown --only exit={done.returncode}"
        if "nope" not in done.stderr or "可用" not in done.stderr:
            return "stderr should name the bad probe and list available ones"
    return None


def check_make_trimap_main() -> str | None:
    """侧车主流程跑通，且输出严格是三值图。"""
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        alpha = np.zeros((64, 64), np.uint8)
        alpha[8:56, 8:56] = 128   # 过渡带：既不 >235 也不 <20，应保留 128
        alpha[20:44, 20:44] = 255
        cutout = root / "cutout.png"
        rgba = np.dstack([np.full((64, 64), 90, np.uint8)] * 3 + [alpha])
        Image.fromarray(rgba, "RGBA").save(cutout)
        out = root / "tri.png"
        done = subprocess.run(
            [sys.executable, str(TRIMAP_SCRIPT), "--alpha", str(cutout),
             "--out", str(out), "--band", "2"],
            capture_output=True, text=True, encoding="utf-8",
            errors="replace", env=_child_env())
        if done.returncode != 0 or not out.exists():
            return f"make_trimap rc={done.returncode}: {done.stderr[-300:]}"
        tri = np.asarray(Image.open(out))
        values = set(np.unique(tri).tolist())
        if not values <= {0, 128, 255}:
            return f"non-trimap values: {sorted(values)}"
        if not {0, 128, 255} <= values:
            return f"missing one of the three levels: {sorted(values)}"
    return None


def check_main_scopes_only_and_seeds_untested() -> str | None:
    """``main()`` 必须把 ``--only`` 传给 exit_code，未选中项恒为 untested。"""
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        src = root / "src.png"
        Image.fromarray(np.zeros((8, 8, 3), np.uint8)).save(src)
        report_path = root / "report.json"
        state = {"status": "works"}

        def fake_probe(local, work, report):
            report["fake"] = {"status": state["status"]}

        def idle_probe(local, work, report):  # pragma: no cover - never selected
            report["idle"] = {"status": "works"}

        class Done:
            stdout = "photocraft-cli 0.0.0\n"

        def run() -> tuple[int, dict]:
            argv = ["probe_capabilities.py", "--work", str(root / "work"),
                    "--src", str(src), "--json", str(report_path),
                    "--only", "fake"]
            with mock.patch.object(
                    probe, "PROBES", {"fake": fake_probe, "idle": idle_probe}), \
                    mock.patch.object(probe, "cli_path", return_value="fake-cli"), \
                    mock.patch.object(probe, "cli", return_value=Done()), \
                    mock.patch.object(sys, "argv", argv), \
                    contextlib.redirect_stdout(io.StringIO()):
                rc = probe.main()
            data = json.loads(report_path.read_text(encoding="utf-8"))
            return rc, data["probes"]

        rc, probes = run()
        if rc != 0:
            return f"works-only exit={rc}, expected 0"
        if probes.get("fake", {}).get("status") != "works":
            return f"fake status={probes.get('fake')}"
        if probes.get("idle", {}).get("status") != "untested":
            return f"unselected probe must stay untested: {probes.get('idle')}"
        state["status"] = "degrades"
        rc, probes = run()
        if rc != 3:
            return f"degrades-only exit={rc}, expected 3"
        if probes.get("fake", {}).get("status") != "degrades":
            return f"fake status={probes.get('fake')}"
    return None


def check_main_refuses_foreign_work_subdir() -> str | None:
    """``--work`` 下同名子目录不是本工具建的时拒绝删除，不能碰用户数据。"""
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        src = root / "src.png"
        Image.fromarray(np.zeros((8, 8, 3), np.uint8)).save(src)
        work = root / "work"
        (work / "fake").mkdir(parents=True)
        keep = work / "fake" / "user.txt"
        keep.write_text("keep", encoding="utf-8")

        class Done:
            stdout = "photocraft-cli 0.0.0\n"

        argv = ["probe_capabilities.py", "--work", str(work), "--src", str(src),
                "--json", str(root / "r.json"), "--only", "fake"]
        with mock.patch.object(probe, "PROBES",
                               {"fake": lambda *args: None}), \
                mock.patch.object(probe, "cli_path", return_value="fake-cli"), \
                mock.patch.object(probe, "cli", return_value=Done()), \
                mock.patch.object(sys, "argv", argv), \
                contextlib.redirect_stdout(io.StringIO()), \
                contextlib.redirect_stderr(io.StringIO()):
            rc = probe.main()
        if rc != 2:
            return f"foreign work subdir exit={rc}, expected 2"
        if not keep.is_file():
            return "user file was deleted"
    return None


def check_main_rejects_empty_only() -> str | None:
    """``--only`` 传空值或纯分隔符必须退 2，不能静默跑全量或空报告退 3。"""
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        src = root / "src.png"
        Image.fromarray(np.zeros((8, 8, 3), np.uint8)).save(src)
        done = subprocess.run(
            [sys.executable, str(PROBE_SCRIPT), "--work", str(root / "work"),
             "--src", str(src), "--only", ","],
            capture_output=True, text=True, encoding="utf-8",
            errors="replace", env=_child_env())
        if done.returncode != 2:
            return f"empty --only exit={done.returncode}"
        if "不能为空" not in (done.stderr or "") and "没有可用探针" not in (done.stderr or ""):
            return "stderr should explain the empty --only"
    return None


def main() -> int:
    checks = [
        ("srgb_to_lab matches Lab(D65) reference values", check_srgb_to_lab),
        ("_lapvar sharpness proxy", check_lapvar),
        ("alpha_stats ratios", check_alpha_stats),
        ("select_probes rejects unknown --only names", check_probe_selection),
        ("capability-matrix names match PROBES", check_matrix_probe_names),
        ("exit_code contract includes untested", check_exit_codes),
        ("main rejects unknown --only with exit 2", check_main_rejects_unknown_only),
        ("main scopes --only and seeds untested", check_main_scopes_only_and_seeds_untested),
        ("main refuses foreign work subdir", check_main_refuses_foreign_work_subdir),
        ("main rejects empty --only with exit 2", check_main_rejects_empty_only),
        ("make_trimap main emits a three-level trimap", check_make_trimap_main),
        ("make_trimap.erode_dilate", check_erode_dilate),
    ]
    failed = []
    for name, fn in checks:
        detail = fn()
        print(f"{'FAIL' if detail else 'PASS'}  {name}" + (f": {detail}" if detail else ""))
        if detail:
            failed.append(name)
    print(f"\n{len(checks) - len(failed)} passed, {len(failed)} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
