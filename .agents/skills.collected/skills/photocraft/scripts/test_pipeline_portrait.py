#!/usr/bin/env python3
"""Offline contract test for pipeline_portrait.py's pure helpers.

  python <skill-dir>/scripts/test_pipeline_portrait.py

pipeline_portrait resolves the CLI lazily, so importing it (and these checks)
works without a PhotoCraft install. Only the parts that do not need a real
render are exercised: sha/rgb/to_png plus run_steps' command shape and JSON
line filtering.
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
from types import SimpleNamespace
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))

import numpy as np  # noqa: E402
from PIL import Image  # noqa: E402

import pipeline_portrait as pipeline  # noqa: E402

CLI_AT_IMPORT = pipeline.CLI


def check_lazy_cli() -> str | None:
    if CLI_AT_IMPORT is not None:
        return "CLI should still be unresolved at import time"
    return None


def check_sha() -> str | None:
    with tempfile.TemporaryDirectory() as tmp:
        payload = Path(tmp) / "x.bin"
        payload.write_bytes(b"abc" * 1000)
        if pipeline.sha(payload) != hashlib.sha256(b"abc" * 1000).hexdigest():
            return "sha mismatch"
    return None


def check_rgb() -> str | None:
    with tempfile.TemporaryDirectory() as tmp:
        grey = Path(tmp) / "grey.png"
        Image.fromarray(np.full((4, 5), 100, np.uint8)).save(grey)
        array = pipeline.rgb(grey)
        if array.dtype != np.float32 or array.shape != (4, 5, 3):
            return f"dtype/shape={array.dtype}/{array.shape}"
        if not np.allclose(array, 100.0):
            return "grey image did not convert to RGB"
    return None


def check_run_steps() -> str | None:
    fake = SimpleNamespace(returncode=0, stdout='{"ok": 1}\nnot json\n{"step": 2}\n',
                           stderr="")
    with tempfile.TemporaryDirectory() as tmp, \
            mock.patch.object(pipeline, "cli_path", return_value="photocraft-cli"), \
            mock.patch.object(pipeline.subprocess, "run", return_value=fake) as run:
        out = Path(tmp) / "out.psd"
        rc, rows, stderr = pipeline.run_steps(
            Path(tmp) / "in.psd",
            [("layer.select", {"name": "A"}), ("layer.setProps",)],
            out, new={"w": 10})
    if rc != 0 or stderr:
        return f"rc/stderr={rc}/{stderr}"
    if rows != [{"ok": 1}, {"step": 2}]:
        return f"json lines not filtered: {rows}"
    command = run.call_args.args[0]
    if command[:3] != ["photocraft-cli", "run", str(Path(tmp) / "in.psd")]:
        return f"command head={command[:3]}"
    if "--new" not in command or json.loads(command[command.index("--new") + 1]) != {"w": 10}:
        return "--new payload missing"
    if command[-2:] != ["--out", str(out)]:
        return f"steps/out wiring wrong: {command}"
    pairs = []
    for i, token in enumerate(command):
        if token == "--cmd":
            pairs.append((command[i + 1], json.loads(command[i + 3])))
    if pairs != [("layer.select", {"name": "A"}), ("layer.setProps", {})]:
        return f"step params wrong: {pairs}"
    return None


def check_to_png_failure() -> str | None:
    fake = SimpleNamespace(returncode=1, stdout="", stderr="boom")
    with tempfile.TemporaryDirectory() as tmp, \
            mock.patch.object(pipeline, "cli_path", return_value="photocraft-cli"), \
            mock.patch.object(pipeline.subprocess, "run", return_value=fake):
        dst = Path(tmp) / "missing.png"
        try:
            pipeline.to_png(Path(tmp) / "in.psd", dst)
        except RuntimeError as exc:
            if "convert failed" in str(exc):
                return None
            return f"unexpected message: {exc}"
        else:
            return "missing output must raise RuntimeError"
    return None


def check_render_builds_hide_steps() -> str | None:
    with tempfile.TemporaryDirectory() as tmp, \
            mock.patch.object(pipeline, "run_steps", return_value=(0, [], "")) as run, \
            mock.patch.object(pipeline, "to_png") as to_png:
        pipeline.render(Path(tmp) / "in.psd", ["A", "B"],
                        Path(tmp) / "out.psd", Path(tmp) / "out.png")
    steps = run.call_args.args[1]
    if steps != [("layer.select", {"name": "A"}),
                 ("layer.setProps", {"visible": False}),
                 ("layer.select", {"name": "B"}),
                 ("layer.setProps", {"visible": False})]:
        return f"unexpected steps: {steps}"
    to_png.assert_called_once()
    return None


def check_render_propagates_failure() -> str | None:
    with tempfile.TemporaryDirectory() as tmp, \
            mock.patch.object(pipeline, "run_steps",
                              return_value=(1, [], "render boom")):
        try:
            pipeline.render(Path(tmp) / "in.psd", [], Path(tmp) / "o.psd",
                            Path(tmp) / "o.png")
        except RuntimeError as exc:
            if "render failed" in str(exc) and "boom" in str(exc):
                return None
            return f"unexpected message: {exc}"
        else:
            return "failed render must raise RuntimeError"
    return None


def check_help_renders() -> str | None:
    script = Path(__file__).resolve().parent / "pipeline_portrait.py"
    done = subprocess.run([sys.executable, str(script), "--help"],
                          capture_output=True, text=True, encoding="utf-8",
                          errors="replace", env=_child_env())
    if done.returncode != 0 or "usage" not in (done.stdout or "").lower():
        return f"--help rc={done.returncode}"
    return None


def main() -> int:
    checks = [
        ("CLI is resolved lazily, not at import", check_lazy_cli),
        ("sha256 helper", check_sha),
        ("rgb returns float32 HxWx3", check_rgb),
        ("run_steps filters JSON lines and wires args", check_run_steps),
        ("render hides layers through run_steps", check_render_builds_hide_steps),
        ("render propagates run failures", check_render_propagates_failure),
        ("--help renders", check_help_renders),
        ("to_png fails loudly when convert fails", check_to_png_failure),
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
