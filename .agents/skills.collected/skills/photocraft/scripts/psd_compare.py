#!/usr/bin/env python3
"""psd_compare.py — 用同一引擎把两份稿件渲染成 PNG 再逐像素比较（重构/规范化后的回归判定）。

用法:
  python <skill-dir>/scripts/psd_compare.py OLD NEW [--out DIR] [--overwrite] [--fuzz 0-255] [--cli PATH]

- 输入是 photocraft-cli convert 能打开的任何格式（psd/psb/pcraft/tif/…）；.png 输入不渲染，直接比较。
- 先比两张渲染图的 SHA256（相同即逐像素相同），不同再逐像素比较并写 diff.png（未变像素压暗、变化像素标红）。
- --fuzz 是每通道容差（默认 0 = 严格相同）。同引擎重渲染预期零差异；跨工具来源才需要容差，并写明原因。
- 比较在 8-bit RGBA 下进行：16-bit 稿件按 8-bit 精度比较。
- --out 下固定写 old.png / new.png / diff.png（PNG 输入复制为 old/new）；已存在时拒绝，确认覆盖加 --overwrite。
  不给 --out 时用临时目录：结果 identical 或出错时删掉，differs 时保留并在报告里给出路径。
- 找 CLI 的顺序：--cli > 环境变量 PHOTOCRAFT_CLI > PATH 里的 photocraft-cli > 默认安装位置。

stdout 输出一行 JSON:
  result            identical | differs | error
  differingPixels / totalPixels / percent / maxChannelDelta / size / diffImage
  reason            "size"（两边画布尺寸不同，此时不出 diff.png）
  warnings          渲染时的真实警告（缺字体、回落、不支持的特性），要转述给用户
  expectedWarnings  convert 写平图必出的 "N layer(s) flattened; …"，属预期，不用转述
  log               convert 的完整输出
退出码: 0 identical；1 differs；2 出错（缺 Pillow、找不到 CLI、渲染失败、参数错误）。
注意: PSD 文件本身的哈希证明不了渲染一致（结构重写后字节必然不同），以渲染结果为准。
"""
import argparse
import hashlib
import json
import os
import re
import shutil
import struct
import subprocess
import sys
import tempfile

EXIT_SAME, EXIT_DIFF, EXIT_ERROR = 0, 1, 2
RENDER_TIMEOUT = 300
EXPECTED_WARNING_RE = re.compile(
    r"^warning: \d+ layer\(s\) flattened; layers, masks and blend modes are not kept$")
WARNING_RE = re.compile(r"warn|flatten|fallback|unsupported|not supported|not installed|警告|回落",
                        re.I)


def find_cli(explicit=None):
    """Return a photocraft-cli path or None (explicit > PHOTOCRAFT_CLI > PATH > install dirs)."""
    for candidate in (explicit, os.environ.get("PHOTOCRAFT_CLI")):
        if candidate:
            if os.path.isfile(candidate):
                return candidate
            raise RuntimeError(f"photocraft-cli 不存在: {candidate}")
    found = shutil.which("photocraft-cli")
    if found:
        return found
    candidates = [os.path.join(os.environ.get(v, ""), *tail) for v, tail in (
        ("ProgramFiles", ("PhotoCraft", "photocraft-cli.exe")),
        ("LOCALAPPDATA", ("Programs", "PhotoCraft", "photocraft-cli.exe")),
    ) if os.environ.get(v)]
    candidates += ["/usr/bin/photocraft-cli", "/usr/local/bin/photocraft-cli",
                   "/opt/homebrew/bin/photocraft-cli"]
    return next((c for c in candidates if os.path.isfile(c)), None)


def sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def png_size(path):
    with open(path, "rb") as handle:
        head = handle.read(24)
    if len(head) < 24 or head[:8] != b"\x89PNG\r\n\x1a\n":
        raise RuntimeError(f"不是 PNG: {path}")
    return list(struct.unpack(">II", head[16:24]))


def render(cli, src, out_png):
    """Render src to a flat PNG with photocraft-cli convert. Returns (warnings, expected, log)."""
    try:
        proc = subprocess.run([cli, "convert", src, out_png], capture_output=True, text=True,
                              encoding="utf-8", errors="replace", timeout=RENDER_TIMEOUT)
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(f"渲染超时（{RENDER_TIMEOUT}s）: {src}") from exc
    except OSError as exc:
        raise RuntimeError(f"无法运行 {cli}: {exc}") from exc
    log = [ln.strip() for ln in (proc.stdout + "\n" + proc.stderr).splitlines() if ln.strip()]
    if proc.returncode != 0 or not os.path.isfile(out_png):
        raise RuntimeError(f"渲染失败 {src}: {' | '.join(log) or f'exit {proc.returncode}'}")
    expected = [ln for ln in log if EXPECTED_WARNING_RE.match(ln)]
    warnings = [ln for ln in log if ln not in expected and WARNING_RE.search(ln)]
    return warnings, expected, log


def compare_pixels(old_png, new_png, fuzz):
    from PIL import Image, ImageChops
    with Image.open(old_png) as a_file, Image.open(new_png) as b_file:
        a, b = a_file.convert("RGBA"), b_file.convert("RGBA")
    if a.size != b.size:
        return {"result": "differs", "reason": "size", "oldSize": list(a.size),
                "newSize": list(b.size)}, None
    diff = ImageChops.difference(a, b)
    max_delta = max(high for _low, high in diff.getextrema())
    mask = None
    for band in diff.split():
        m = band.point(lambda v: 255 if v > fuzz else 0)
        mask = m if mask is None else ImageChops.lighter(mask, m)
    differing = mask.histogram()[255]
    total = a.size[0] * a.size[1]
    report = {"result": "differs" if differing else "identical", "differingPixels": differing,
              "totalPixels": total, "percent": round(differing * 100.0 / total, 4),
              "maxChannelDelta": max_delta, "size": list(a.size)}
    if not differing:
        return report, None
    dim = a.convert("L").point(lambda v: v // 3).convert("RGB")
    return report, Image.composite(Image.new("RGB", a.size, (255, 0, 0)), dim, mask)


def _same(path, other):
    try:
        return os.path.exists(path) and os.path.samefile(path, other)
    except OSError:
        return False


def main():
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, OSError):
            pass
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("old", help="基线稿（或基线 PNG）")
    parser.add_argument("new", help="新稿（或新 PNG）")
    parser.add_argument("--out", default=None, help="输出目录（默认临时目录）")
    parser.add_argument("--overwrite", action="store_true", help="允许覆盖 --out 里的 old/new/diff.png")
    parser.add_argument("--fuzz", type=int, default=0, help="每通道容差 0-255（默认 0）")
    parser.add_argument("--cli", default=None, help="photocraft-cli 路径")
    args = parser.parse_args()

    def emit(report, code):
        print(json.dumps(report, ensure_ascii=False))
        return code

    def error(message, **extra):
        return emit(dict({"result": "error", "error": message}, **extra), EXIT_ERROR)

    if not 0 <= args.fuzz <= 255:
        return error("--fuzz 取值 0-255")
    for path in (args.old, args.new):
        if not os.path.isfile(path):
            return error(f"文件不存在: {path}")
    if os.path.samefile(args.old, args.new):
        return error("old 与 new 是同一个文件；回归比较需要两份不同的稿件")
    try:
        from PIL import Image  # noqa: F401
    except ImportError:
        return error("需要 Pillow：pip install pillow")
    if args.out and os.path.exists(args.out) and not os.path.isdir(args.out):
        return error(f"--out 不是目录: {args.out}")

    sides = [("old", args.old), ("new", args.new)]
    to_render = [(name, src) for name, src in sides if not src.lower().endswith(".png")]
    if args.out:
        targets = [os.path.join(args.out, f"{name}.png") for name, _src in sides]
        targets.append(os.path.join(args.out, "diff.png"))
        for target in targets:
            for _name, src in sides:
                if _same(target, src):
                    return error(f"输出 {target} 会覆盖输入 {src}；换 --out 目录")
        existing = [t for t in targets if os.path.exists(t)]
        if existing and not args.overwrite:
            return error(f"输出已存在: {existing}；确认覆盖加 --overwrite，或换目录")
        os.makedirs(args.out, exist_ok=True)
        out_dir, temp = args.out, False
    else:
        out_dir, temp = tempfile.mkdtemp(prefix="psd-compare-"), True

    report = {"result": "error", "fuzz": args.fuzz, "out": os.path.abspath(out_dir),
              "warnings": [], "expectedWarnings": [], "log": []}
    code = EXIT_ERROR
    try:
        cli = find_cli(args.cli) if to_render else None
        if to_render and not cli:
            raise RuntimeError("找不到 photocraft-cli：用 --cli 或 PHOTOCRAFT_CLI 指定")
        info = {}
        for name, src in sides:
            if src.lower().endswith(".png"):
                png = src
                if args.out:
                    png = os.path.join(out_dir, f"{name}.png")
                    shutil.copyfile(src, png)
            else:
                png = os.path.join(out_dir, f"{name}.png")
                warns, expected, log = render(cli, src, png)
                report["warnings"] += [w for w in warns if w not in report["warnings"]]
                report["expectedWarnings"] += expected
                report["log"] += log
            info[name] = {"input": os.path.abspath(src), "render": os.path.abspath(png),
                          "sha256": sha256(png)}
        report["old"], report["new"] = info["old"], info["new"]
        if info["old"]["sha256"] == info["new"]["sha256"]:
            w, h = png_size(info["old"]["render"])
            report.update({"result": "identical", "differingPixels": 0, "totalPixels": w * h,
                           "percent": 0.0, "maxChannelDelta": 0, "size": [w, h]})
        else:
            pixels, image = compare_pixels(info["old"]["render"], info["new"]["render"], args.fuzz)
            report.update(pixels)
            if image is not None:
                diff_path = os.path.join(out_dir, "diff.png")
                image.save(diff_path)
                report["diffImage"] = os.path.abspath(diff_path)
        code = EXIT_SAME if report["result"] == "identical" else EXIT_DIFF
    except Exception as exc:  # report every failure as JSON, never a traceback
        report.update({"result": "error", "error": str(exc)})
        code = EXIT_ERROR
    if temp and code != EXIT_DIFF:
        shutil.rmtree(out_dir, ignore_errors=True)
        report["out"] = None
        report["tempCleaned"] = True
        for side in ("old", "new"):
            if isinstance(report.get(side), dict) and not report[side]["input"].lower().endswith(".png"):
                report[side]["render"] = None
    elif temp:
        report["tempKept"] = True
    return emit(report, code)


if __name__ == "__main__":
    sys.exit(main())
