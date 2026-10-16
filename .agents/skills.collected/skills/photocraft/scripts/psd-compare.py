#!/usr/bin/env python3
"""psd-compare.py — 两个设计稿的渲染一致性校验（重写/重组后的回归判定）。

同一引擎（photocraft-cli convert）把两边渲染成 PNG，再逐像素对比：
先比渲染 PNG 的哈希（一致即逐像素一致，最快），不一致再算差异像素、出差异图。

用法：
  python psd-compare.py 旧.psd 新.psd
  python psd-compare.py 旧.psd 新.psd --out DIR [--fuzz 0] [--cli PATH]

- 输入支持 photocraft-cli convert 能开的格式（psd/psb/pcraft/png/…）；
  输入本身是 .png 时跳过渲染直接对比。
- --fuzz 是每通道容差（0-255，默认 0 = 严格逐像素一致）。同引擎渲染预期零噪声，
  跨工具来的稿子（如 Photoshop 直接导出）才需要容差。
- 对比在 8-bit RGBA 空间进行。
- stdout 输出一行 JSON 报告。退出码：0 一致，1 不一致，2 出错。

注意：PSD 文件级哈希判不了重写前后一致（结构重写后字节必不同），
一致性以渲染出的 PNG 为准。
"""
import argparse
import hashlib
import json
import os
import shutil
import struct
import subprocess
import sys
import tempfile

EXIT_SAME = 0
EXIT_DIFF = 1
EXIT_ERROR = 2

DEFAULT_CLI_PATH = r"C:\Program Files\PhotoCraft\photocraft-cli.exe"


def find_cli():
    env = os.environ.get("PHOTOCRAFT_CLI")
    if env:
        return env
    found = shutil.which("photocraft-cli")
    if found:
        return found
    if os.path.isfile(DEFAULT_CLI_PATH):
        return DEFAULT_CLI_PATH
    return None


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def png_size(path):
    with open(path, "rb") as f:
        head = f.read(24)
    if len(head) < 24 or head[:8] != b"\x89PNG\r\n\x1a\n":
        raise RuntimeError(f"不是 PNG: {path}")
    return struct.unpack(">II", head[16:24])


def render(cli, src, out_png):
    """用 photocraft-cli convert 渲染（平图 PNG）。返回警告文本列表。"""
    r = subprocess.run([cli, "convert", src, out_png],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    warns = [ln.strip() for ln in (r.stdout + "\n" + r.stderr).splitlines() if ln.strip()]
    if r.returncode != 0 or not os.path.isfile(out_png):
        raise RuntimeError(f"渲染失败 {src}: {' | '.join(warns) or f'exit {r.returncode}'}")
    return warns


def compare_pixels(old_png, new_png, fuzz):
    try:
        from PIL import Image, ImageChops
    except ImportError:
        raise RuntimeError("需要 Pillow（pip install pillow）才能做像素对比")

    a = Image.open(old_png).convert("RGBA")
    b = Image.open(new_png).convert("RGBA")
    if a.size != b.size:
        return {"result": "differs", "reason": "size",
                "oldSize": list(a.size), "newSize": list(b.size), "size": None,
                "differingPixels": None, "totalPixels": None,
                "percent": None, "maxChannelDelta": None}

    diff = ImageChops.difference(a, b)
    extrema = diff.getextrema()
    max_delta = max(e[1] for e in extrema)

    mask = None
    for band in diff.split():
        m = band.point(lambda v: 255 if v > fuzz else 0)
        mask = m if mask is None else ImageChops.lighter(mask, m)

    hist = mask.histogram()
    diff_pixels = hist[255]
    total = a.size[0] * a.size[1]

    # 差异图：未变像素压暗为灰，变化像素标红
    dim = a.convert("L").point(lambda v: v // 3).convert("RGB")
    red = Image.new("RGB", a.size, (255, 0, 0))
    vis = Image.composite(red, dim, mask)

    return {"result": "differs" if diff_pixels else "identical",
            "differingPixels": diff_pixels, "totalPixels": total,
            "percent": round(diff_pixels * 100.0 / total, 4),
            "maxChannelDelta": max_delta,
            "diffImage": vis, "size": list(a.size)}


def main():
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, OSError):
            pass

    ap = argparse.ArgumentParser(description="两个设计稿的渲染一致性校验")
    ap.add_argument("old")
    ap.add_argument("new")
    ap.add_argument("--out", default=None, help="输出目录（默认建临时目录）")
    ap.add_argument("--fuzz", type=int, default=0, help="每通道容差 0-255，默认 0（严格一致）")
    ap.add_argument("--cli", default=None, help="photocraft-cli 路径")
    args = ap.parse_args()

    if not (0 <= args.fuzz <= 255):
        print(json.dumps({"result": "error", "error": "--fuzz 取值 0-255"}, ensure_ascii=False))
        return EXIT_ERROR
    for p in (args.old, args.new):
        if not os.path.isfile(p):
            print(json.dumps({"result": "error", "error": f"文件不存在: {p}"}, ensure_ascii=False))
            return EXIT_ERROR

    out_dir = args.out or tempfile.mkdtemp(prefix="psd-compare-")
    os.makedirs(out_dir, exist_ok=True)

    report = {"result": "error", "fuzz": args.fuzz, "out": out_dir, "warnings": []}
    try:
        cli = args.cli or find_cli()
        sides = {}
        for name, src in (("old", args.old), ("new", args.new)):
            if src.lower().endswith(".png"):
                png, warns = src, []
            else:
                if not cli:
                    raise RuntimeError("找不到 photocraft-cli（--cli 指定，或装到 PATH / 默认目录）")
                png = os.path.join(out_dir, f"{name}.png")
                warns = render(cli, src, png)
            sides[name] = {"input": os.path.abspath(src), "render": os.path.abspath(png),
                           "sha256": sha256(png)}
            report["warnings"].extend(warns)

        report["old"], report["new"] = sides["old"], sides["new"]

        if sides["old"]["sha256"] == sides["new"]["sha256"]:
            w, h = png_size(sides["old"]["render"])
            report.update({"result": "identical", "differingPixels": 0,
                           "totalPixels": w * h, "percent": 0.0,
                           "maxChannelDelta": 0, "size": [w, h]})
        else:
            cmp = compare_pixels(sides["old"]["render"], sides["new"]["render"], args.fuzz)
            report.update({k: v for k, v in cmp.items() if k != "diffImage"})
            if cmp.get("diffImage") is not None and cmp.get("differingPixels"):
                diff_path = os.path.join(out_dir, "diff.png")
                cmp["diffImage"].save(diff_path)
                report["diffImage"] = os.path.abspath(diff_path)
    except Exception as e:
        report = {"result": "error", "error": str(e), "fuzz": args.fuzz,
                  "out": out_dir, "warnings": report.get("warnings", [])}

    print(json.dumps(report, ensure_ascii=False))
    return {"identical": EXIT_SAME, "differs": EXIT_DIFF}.get(report["result"], EXIT_ERROR)


if __name__ == "__main__":
    sys.exit(main())
