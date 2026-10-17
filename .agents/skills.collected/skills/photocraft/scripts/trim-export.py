#!/usr/bin/env python3
"""trim-export.py — 通用裁边/切图导出助手（只处理已渲染位图）。

不读 PSD 图层：先用 PhotoCraft 的 doc.render / doc.exportLayers 或 convert 导出位图，
再对位图做裁边、加 padding、多倍率和命名导出。所有尺寸、颜色、倍率、格式、命名都
来自参数，脚本不绑定具体稿件、目录或资产名。

用法:
  python trim-export.py <文件或目录...> --out DIR
    [--trim none|alpha|bg|bbox] [--bg-color #RRGGBB] [--tolerance 0-255]
    [--bbox x,y,w,h] [--alpha-threshold 0-255]
    [--padding N|L,T,R,B] [--scales 1,2] [--format auto|png|webp|jpeg]
    [--quality 1-100] [--background #RRGGBB]
    [--name-pattern "{name}@{scale}x{ext}"] [--overwrite] [--recursive]
    [--manifest PATH] [--manifest-mode merge|replace] [--prune]

- trim 默认 none（不裁）；需要裁边时显式选 alpha/bg/bbox。
- trim alpha：按 alpha 通道裁掉透明边；没有 alpha 时报错。
- trim bg：按 --bg-color + --tolerance 裁掉纯色背景；有透明像素时拒绝，改用 alpha。
- trim bbox：按用户给的 x,y,w,h 手动裁切。
- padding：默认 0；1 个值四边相同，或 L,T,R,B；按源像素计，先缩放内容再加 padding，
  所以 padding 区始终是干净的透明/背景色，不会被重采样污染。
- 输出格式 auto 跟随源扩展名（tif 等无对应格式时用 png）；JPEG 不支持 alpha，
  源有 alpha 或要 padding 时必须给 --background。
- name-pattern 必须包含 {ext}；占位符：{name} {scale} {ext} {index} {w} {h}。倍率含非 1 值时还必须有 {scale}。
- 输出只写到 --out 内，默认不覆盖已有输出，也不允许覆盖任何输入或 manifest/锁文件。
  输出先写同目录临时文件、算 hash 后再原子替换；中断不会留下截断的最终文件。
- manifest 默认 <out>/assets-manifest.json，默认合并已有记录并保留 runs 历史；manifest
  必须是 .json，已有文件必须是 trim-export.py 的有效 manifest；锁覆盖整个运行；路径相对
  manifest 目录，跨盘时记绝对路径并标记；--manifest-mode replace 可用于重建坏 manifest，
  --prune 清理本机可达但已不存在的旧条目。
- alpha 指标：sourceHasAlpha/sourceTransparentRatio/sourceAlphaBBox 是裁剪前源图；
  contentTransparentRatio 只看裁剪后内容区（硬边裁剪后常为 0）；比例统计 alpha<255（含半透明），
  没有 alpha 记 0.0；alphaBBox 为输出像素坐标；paddingOnlyAlpha=true 表示最终透明只来自
  padding，不能单独否定有源 alpha 的抠图。
- EXIF orientation 会先应用再导出，manifest 同时记 sourceSize/orientedSize；方向信息不保留。
  16-bit/浮点源 fail closed，先转 8-bit。
- 退出码：0 全部成功；1 partial/全部失败（看 failures）；2 参数/锁/manifest 配置错误。
  成功验收要求 failures 为空。--source-document / --note 会写入 manifest。
依赖 Pillow（pip install pillow）。
"""
import argparse
import hashlib
import json
import os
import re
import sys
import tempfile
import time
import uuid
from datetime import datetime, timezone

IMAGE_EXTS = {".png", ".webp", ".jpg", ".jpeg", ".tif", ".tiff"}
FORMAT_BY_EXT = {".png": "png", ".webp": "webp", ".jpg": "jpeg", ".jpeg": "jpeg",
                 ".tif": "png", ".tiff": "png"}
MANIFEST_NAME = "assets-manifest.json"
LOCK_SUFFIX = ".lock"
LOCK_TIMEOUT = 60
STALE_LOCK_SECONDS = 300
WINDOWS_RESERVED = {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10)),
                    *(f"LPT{i}" for i in range(1, 10))}


def parse_color(value):
    if not value:
        raise ValueError("需要颜色值，如 #RRGGBB")
    s = value.strip().lstrip("#")
    if len(s) == 3:
        s = "".join(c * 2 for c in s)
    if len(s) != 6 or not re.fullmatch(r"[0-9a-fA-F]{6}", s):
        raise ValueError(f"颜色格式不对: {value}")
    return tuple(int(s[i:i + 2], 16) for i in (0, 2, 4))


def parse_padding(value):
    parts = [x.strip() for x in str(value).split(",")]
    if len(parts) == 1:
        parts = parts * 4
    if len(parts) != 4:
        raise ValueError("--padding 需要 1 个值或 L,T,R,B 四个值")
    nums = [int(x) for x in parts]
    if any(x < 0 for x in nums):
        raise ValueError("--padding 不能为负数")
    return tuple(nums)


def parse_bbox(value):
    parts = [x.strip() for x in str(value).split(",")]
    if len(parts) != 4:
        raise ValueError("--bbox 需要 x,y,w,h")
    nums = [int(x) for x in parts]
    if nums[2] <= 0 or nums[3] <= 0:
        raise ValueError("--bbox 的宽高必须大于 0")
    return tuple(nums)


def parse_scales(value):
    raw = [x.strip() for x in str(value).split(",") if x.strip()]
    if not raw:
        raise ValueError("--scales 至少给一个值")
    result = []
    for x in raw:
        s = float(x)
        if s <= 0:
            raise ValueError("--scales 必须大于 0")
        if s not in result:
            result.append(s)
    return result


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def norm_key(path):
    return os.path.normcase(os.path.realpath(os.path.abspath(path)))


def is_under(path, directory):
    try:
        return os.path.commonpath([norm_key(path), norm_key(directory)]) == norm_key(directory)
    except ValueError:
        return False


def rel_posix(path, start):
    """Return (path, absolute). POSIX separators; fallback to absolute on cross-drive."""
    try:
        rel = os.path.relpath(path, start)
        return rel.replace("\\", "/"), False
    except ValueError:
        return os.path.abspath(path).replace("\\", "/"), True


def expand_inputs(paths, out_dir, recursive):
    files, warnings = [], []
    for raw in paths:
        p = os.path.abspath(raw)
        if os.path.isdir(p):
            iterator = os.walk(p) if recursive else [(p, [], os.listdir(p))]
            for root, _dirs, names in iterator:
                for name in sorted(names):
                    full = os.path.join(root, name)
                    if not os.path.isfile(full):
                        continue
                    if os.path.splitext(name)[1].lower() not in IMAGE_EXTS:
                        warnings.append(f"跳过非位图: {full}")
                        continue
                    if is_under(full, out_dir):
                        warnings.append(f"跳过输出目录内的文件: {full}")
                        continue
                    files.append(full)
        elif os.path.isfile(p):
            if os.path.splitext(p)[1].lower() not in IMAGE_EXTS:
                raise ValueError(f"不支持的输入格式: {p}")
            if is_under(p, out_dir):
                warnings.append(f"显式输入位于输出目录内；输出仍不会覆盖它: {p}")
            files.append(p)
        else:
            raise ValueError(f"输入不存在: {p}")
    deduped = []
    for f in files:
        if f not in deduped:
            deduped.append(f)
    return deduped, warnings


def check_source_bit_depth(path, im):
    if im.mode.startswith("I;16") or im.mode in ("I", "F") or "16" in im.mode:
        raise RuntimeError(f"16-bit/浮点源不受支持，先转 8-bit: {path}（mode={im.mode}）")
    if im.format == "PNG":
        with open(path, "rb") as f:
            head = f.read(25)
        if head.startswith(b"\x89PNG\r\n\x1a\n") and len(head) >= 25 and head[24] > 8:
            raise RuntimeError(f"16-bit PNG 不受支持，先转 8-bit: {path}")
    if im.format == "TIFF" and hasattr(im, "tag_v2"):
        bits = im.tag_v2.get(258, ())
        if isinstance(bits, int):
            bits = (bits,)
        if any(int(b) > 8 for b in bits if b):
            raise RuntimeError(f"16-bit TIFF 不受支持，先转 8-bit: {path}")


def has_alpha(im):
    return "A" in im.getbands() or "transparency" in im.info


def trim_bbox(im, mode, bg_color, tolerance, bbox, alpha_threshold):
    from PIL import Image, ImageChops
    width, height = im.size
    if mode == "none":
        return (0, 0, width, height)
    if mode == "alpha":
        if not has_alpha(im):
            raise RuntimeError("输入没有 alpha 通道；改用 --trim bg 或 --trim bbox")
        alpha = im.convert("RGBA").getchannel("A")
        mask = alpha.point(lambda v: 255 if v > alpha_threshold else 0)
        box = mask.getbbox()
    elif mode == "bg":
        if bg_color is None:
            raise RuntimeError("--trim bg 需要 --bg-color")
        if has_alpha(im):
            low, _high = im.getchannel("A").getextrema()
            if low < 255:
                raise RuntimeError("输入含透明像素；--trim bg 不可靠，改用 --trim alpha 或先压平背景")
        rgb = im.convert("RGB")
        bg = parse_color(bg_color)
        diff = ImageChops.difference(rgb, Image.new("RGB", rgb.size, bg))
        r, g, b = diff.split()
        mask = ImageChops.lighter(ImageChops.lighter(r, g), b)
        mask = mask.point(lambda v: 255 if v > tolerance else 0)
        box = mask.getbbox()
    else:
        x, y, w, h = bbox
        if x < 0 or y < 0 or x + w > width or y + h > height:
            raise RuntimeError(f"--bbox 超出图像范围（{width}x{height}）")
        box = (x, y, x + w, y + h)
    if not box:
        raise RuntimeError("裁边后没有内容；检查 trim 模式/颜色/阈值")
    return box


def scale_image(im, scale):
    from PIL import Image
    if scale == 1:
        return im
    size = (max(1, round(im.width * scale)), max(1, round(im.height * scale)))
    resample = getattr(Image, "Resampling", Image).LANCZOS
    return im.resize(size, resample)


def pad_scaled(content, padding_out, background, fmt):
    """Padding is applied after scaling, so it is never resampled."""
    from PIL import Image
    left, top, right, bottom = padding_out
    width = content.width + left + right
    height = content.height + top + bottom
    if width <= 0 or height <= 0:
        raise RuntimeError("padding 后尺寸无效")
    if background is not None:
        canvas = Image.new("RGB", (width, height), background)
        if "A" in content.getbands():
            src = content.convert("RGBA")
            canvas.paste(src, (left, top), src.getchannel("A"))
        else:
            canvas.paste(content.convert("RGB"), (left, top))
        return canvas
    if not any(padding_out):
        return content.convert("RGBA") if has_alpha(content) else content.convert("RGB")
    if fmt == "jpeg":
        raise RuntimeError("JPEG 加 padding 需要 --background")
    canvas = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    canvas.alpha_composite(content.convert("RGBA"), (left, top))
    return canvas


def output_format(source, requested):
    if requested != "auto":
        return requested
    return FORMAT_BY_EXT.get(os.path.splitext(source)[1].lower(), "png")


def safe_name(source, pattern, scale, fmt, index, width, height):
    stem = os.path.splitext(os.path.basename(source))[0]
    stem = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", stem).strip() or "asset"
    ext = {"png": ".png", "webp": ".webp", "jpeg": ".jpg"}[fmt]
    try:
        name = pattern.format(name=stem, scale=f"{scale:g}", ext=ext,
                              index=index, w=width, h=height)
    except KeyError as e:
        raise ValueError(f"命名模板含未知占位符: {e}")
    if (not name or os.path.isabs(name) or re.match(r"^[A-Za-z]:", name)
            or re.search(r'[<>:"/\\|?*\x00-\x1f]', name) or ".." in name
            or name != name.rstrip(" .")):
        raise ValueError(f"命名模板会产生非法/越界文件名: {name!r}")
    if name.split(".")[0].upper() in WINDOWS_RESERVED:
        raise ValueError(f"命名模板产生 Windows 保留名: {name!r}")
    return name


def alpha_stats(im):
    if "A" not in im.getbands():
        return False, 0.0, None
    alpha = im.getchannel("A")
    total = im.width * im.height
    hist = alpha.histogram()
    transparent = sum(hist[:255])
    bbox = alpha.point(lambda v: 255 if v > 0 else 0).getbbox()
    return True, round(transparent / total, 6) if total else 0.0, list(bbox) if bbox else None


def save_output(im, path, fmt, quality, background, info):
    from PIL import Image
    if background is not None:
        if "A" in im.getbands():
            base = Image.new("RGB", im.size, background)
            base.paste(im, mask=im.getchannel("A"))
            im = base
        else:
            im = im.convert("RGB")
    elif fmt == "jpeg" and "A" in im.getbands():
        raise RuntimeError("JPEG 不支持 alpha；给 --background 或改用 png/webp")
    kwargs = {}
    if fmt in ("jpeg", "webp"):
        kwargs["quality"] = quality
    if info.get("icc_profile"):
        kwargs["icc_profile"] = info["icc_profile"]
    if info.get("dpi"):
        kwargs["dpi"] = info["dpi"]
    im.save(path, format=fmt.upper(), **kwargs)


def save_output_atomic(im, out_path, fmt, quality, background, info, overwrite):
    if os.path.isdir(out_path):
        raise RuntimeError(f"输出路径是目录: {out_path}")
    if os.path.exists(out_path) and not overwrite:
        raise RuntimeError(f"输出已存在: {out_path}；确认覆盖加 --overwrite")
    parent = os.path.dirname(out_path) or "."
    os.makedirs(parent, exist_ok=True)
    suffix = os.path.splitext(out_path)[1] or ".tmp"
    fd, tmp = tempfile.mkstemp(prefix=".trim-export-", suffix=suffix, dir=parent)
    os.close(fd)
    try:
        save_output(im, tmp, fmt, quality, background, info)
        out_sha = sha256(tmp)
        size = os.path.getsize(tmp)
        os.replace(tmp, out_path)
        tmp = None
        return out_sha, size
    finally:
        if tmp and os.path.exists(tmp):
            try:
                os.remove(tmp)
            except OSError:
                pass


def process_one(source, args, scales, index, out_dir, manifest_dir, run_id, run_at,
                reserved, seen):
    from PIL import Image, ImageOps
    im = Image.open(source)
    check_source_bit_depth(source, im)
    im.load()
    warnings = []
    if getattr(im, "is_animated", False):
        im.seek(0)
        warnings.append(f"动图只取第一帧: {source}")
    raw_size = [im.width, im.height]
    exif = im.getexif()
    orientation = exif.get(0x0112, 1)
    exif_transposed = orientation not in (None, 1)
    if exif_transposed:
        transposed = ImageOps.exif_transpose(im)
        if transposed is not None:
            im = transposed
        warnings.append(f"已应用 EXIF orientation={orientation} 并移除方向信息: {source}")
    oriented_size = [im.width, im.height]
    info = dict(im.info)
    source_mode = im.mode
    if source_mode not in ("RGB", "RGBA") and info.get("icc_profile"):
        warnings.append(f"源模式 {source_mode} 与输出 RGB/RGBA 不同，已丢弃 ICC profile: {source}")
        info.pop("icc_profile", None)
    if source_mode == "CMYK":
        warnings.append(f"CMYK 源已转 RGB/RGBA，印刷用请另行做色彩转换: {source}")
    source_alpha = has_alpha(im)
    working = im.convert("RGBA") if source_alpha else im.convert("RGB")
    source_has_alpha, source_transparent_ratio, source_alpha_bbox = alpha_stats(working)
    box = trim_bbox(working, args.trim, args.bg_color, args.tolerance,
                    args.bbox, args.alpha_threshold)
    full_box = (0, 0, working.width, working.height)
    if args.trim == "alpha":
        low, _high = working.getchannel("A").getextrema()
        if low == 255:
            warnings.append("alpha 全不透明：trim alpha 没有可裁的透明边")
    if args.trim == "bg" and box == full_box:
        warnings.append("trim bg 没有裁掉任何边；检查背景色/容差或改用 bbox")
    if (args.trim == "bg" and os.path.splitext(source)[1].lower() in (".jpg", ".jpeg")
            and args.tolerance <= 8):
        warnings.append("JPEG 背景有压缩噪声；建议提高 --tolerance 或手动 bbox")
    fmt = output_format(source, args.format)
    background = args.background
    if fmt == "jpeg" and background is None and (source_alpha or any(args.padding)):
        raise RuntimeError("JPEG 需要 --background（源有 alpha 或要加 padding）")
    content = working.crop(box)
    results, failures = [], []
    source_rel, source_abs = rel_posix(source, manifest_dir)
    source_sha = sha256(source)
    common_options = {
        "trim": args.trim,
        "bgColor": args.bg_color,
        "tolerance": args.tolerance,
        "alphaThreshold": args.alpha_threshold,
        "padding": list(args.padding),
        "format": fmt,
        "quality": args.quality,
        "background": list(background) if background else None,
        "namePattern": args.pattern,
        "sourceDocument": args.source_document,
        "note": args.note,
    }
    for scale in scales:
        try:
            scaled_content = scale_image(content, scale)
            padding_out = [round(p * scale) for p in args.padding]
            padded = pad_scaled(scaled_content, padding_out, background, fmt)
            name = safe_name(source, args.pattern, scale, fmt, index, padded.width, padded.height)
            out_path = os.path.join(out_dir, name)
            if not is_under(out_path, out_dir):
                raise RuntimeError(f"输出越界: {out_path}")
            key = norm_key(out_path)
            if key in reserved:
                raise RuntimeError("输出路径会覆盖输入、manifest 或锁文件，拒绝")
            if key in seen:
                raise RuntimeError(f"输出重名: {out_path}；调整 --name-pattern")
            out_sha, out_size = save_output_atomic(
                padded, out_path, fmt, args.quality, background, info, args.overwrite)
            seen.add(key)
            content_has, content_ratio, content_bbox = alpha_stats(scaled_content)
            final_has, final_ratio, final_bbox = alpha_stats(padded)
            padding_only = bool(
                final_has and (final_ratio or 0) > 0 and any(padding_out)
                and (not content_has or (content_ratio or 0) == 0)
            )
            path_rel, path_abs = rel_posix(out_path, manifest_dir)
            results.append({
                "source": source_rel,
                "sourceAbsolute": source_abs,
                "path": path_rel,
                "pathAbsolute": path_abs,
                "trim": args.trim,
                "bbox": [box[0], box[1], box[2] - box[0], box[3] - box[1]],
                "box": list(box),
                "bboxSpace": "oriented-source-pixels",
                "padding": list(args.padding),
                "paddingOut": padding_out,
                "scale": scale,
                "width": padded.width,
                "height": padded.height,
                "sourceSize": raw_size,
                "orientedSize": oriented_size,
                "outputSize": [padded.width, padded.height],
                "upscaled": scale > 1,
                "exifTransposed": exif_transposed,
                "sourceMode": source_mode,
                "outputMode": padded.mode,
                "format": fmt,
                "sourceHasAlpha": source_has_alpha,
                "sourceTransparentRatio": source_transparent_ratio,
                "sourceAlphaBBox": source_alpha_bbox,
                "sourceAlphaBBoxSpace": "oriented-source-pixels",
                "alpha": final_has,
                "transparentRatio": final_ratio,
                "contentAlpha": content_has,
                "contentTransparentRatio": content_ratio,
                "alphaBBox": final_bbox,
                "contentAlphaBBox": content_bbox,
                "alphaBBoxSpace": "output-pixels",
                "contentAlphaBBoxSpace": "scaled-content-pixels",
                "paddingOnlyAlpha": padding_only,
                "geometryOnly": True,
                "semanticCutout": False,
                "sourceDocument": args.source_document,
                "note": args.note,
                "options": common_options,
                "runId": run_id,
                "runAt": run_at,
                "sourceSha256": source_sha,
                "outputSha256": out_sha,
                "bytes": out_size,
            })
            if scale > 1:
                warnings.append(f"{os.path.basename(source)} 以 {scale:g}x 放大导出；确认源分辨率足够")
        except Exception as e:
            failures.append({"source": source, "scale": scale, "error": str(e)})
    return results, failures, warnings


def manifest_entry_abs(entry, manifest_dir):
    p = entry.get("path")
    if not p:
        return None
    if entry.get("pathAbsolute") or os.path.isabs(p):
        return norm_key(p)
    return norm_key(os.path.join(manifest_dir, p))


def load_manifest(path):
    if not os.path.exists(path):
        return {"outputs": [], "runs": []}
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict) or data.get("tool") != "trim-export.py":
        raise RuntimeError("已有 manifest 不是 trim-export.py 产物；用 --manifest-mode replace 或换路径")
    outputs = data.get("outputs")
    runs = data.get("runs", [])
    if not isinstance(outputs, list) or not isinstance(runs, list):
        raise RuntimeError("已有 manifest 的 outputs/runs 结构不合法；用 --manifest-mode replace 或换路径")
    for entry in outputs:
        if not isinstance(entry, dict) or not isinstance(entry.get("path"), str) or not entry["path"]:
            raise RuntimeError("已有 manifest 含无 path 或非法条目；用 --manifest-mode replace 或换路径")
    if any(not isinstance(run, dict) for run in runs):
        raise RuntimeError("已有 manifest 的 runs 条目不合法；用 --manifest-mode replace 或换路径")
    data["runs"] = runs
    return data


def acquire_lock(lock_path):
    deadline = time.time() + LOCK_TIMEOUT
    while True:
        try:
            fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_RDWR)
            os.write(fd, f"{os.getpid()} {time.time()}".encode("ascii"))
            return fd
        except FileExistsError:
            try:
                age = time.time() - os.path.getmtime(lock_path)
                if age > STALE_LOCK_SECONDS:
                    os.remove(lock_path)
                    continue
            except OSError:
                pass
            if time.time() > deadline:
                raise RuntimeError(f"manifest 正被另一个进程写入: {lock_path}；稍后重试或删除锁文件")
            time.sleep(0.2)


def release_lock(fd, lock_path):
    try:
        os.close(fd)
    except OSError:
        pass
    try:
        os.remove(lock_path)
    except OSError:
        pass


def write_manifest_payload(manifest_path, make_payload):
    parent = os.path.dirname(manifest_path) or "."
    os.makedirs(parent, exist_ok=True)
    tmp_path = None
    try:
        payload = make_payload()
        fd, tmp_path = tempfile.mkstemp(prefix=".assets-manifest-", suffix=".tmp", dir=parent)
        os.close(fd)
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        os.replace(tmp_path, manifest_path)
        tmp_path = None
    finally:
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except OSError:
                pass


def main():
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, OSError):
            pass

    ap = argparse.ArgumentParser(description="通用裁边/切图导出（只处理已渲染位图）")
    ap.add_argument("inputs", nargs="+", help="位图文件或目录")
    ap.add_argument("--out", required=True, help="输出目录（必填）")
    ap.add_argument("--trim", choices=["none", "alpha", "bg", "bbox"], default="none")
    ap.add_argument("--bg-color", default=None, help="trim bg 的背景色，如 #ffffff")
    ap.add_argument("--tolerance", type=int, default=8, help="trim bg 容差 0-255")
    ap.add_argument("--bbox", default=None, help="trim bbox 的 x,y,w,h")
    ap.add_argument("--alpha-threshold", type=int, default=8, help="alpha 裁边阈值 0-255")
    ap.add_argument("--padding", default="0", help="0 / N / L,T,R,B（按源像素）")
    ap.add_argument("--scales", default="1", help="倍率列表，如 1,2")
    ap.add_argument("--format", choices=["auto", "png", "webp", "jpeg"], default="auto")
    ap.add_argument("--quality", type=int, default=92, help="JPEG/WebP 质量 1-100")
    ap.add_argument("--background", default=None, help="JPEG/不透明导出的背景色")
    ap.add_argument("--name-pattern", default=None, help="命名模板，默认按倍率自动选择")
    ap.add_argument("--source-document", default=None, help="PSD/源稿路径或标识，写入 manifest")
    ap.add_argument("--note", default=None, help="画心/纸边/投影等 spec 备注，写入 manifest")
    ap.add_argument("--overwrite", action="store_true", help="允许覆盖已有输出")
    ap.add_argument("--recursive", action="store_true", help="递归目录")
    ap.add_argument("--manifest", default=None, help=f"manifest 路径，默认 <out>/{MANIFEST_NAME}")
    ap.add_argument("--manifest-mode", choices=["merge", "replace"], default="merge",
                    help="已有 manifest 合并（默认）或替换")
    ap.add_argument("--prune", action="store_true", help="合并时移除已不存在的旧输出条目")
    args = ap.parse_args()

    try:
        try:
            from PIL import Image, ImageChops  # noqa: F401
        except ImportError as e:
            raise RuntimeError("需要 Pillow（pip install pillow）") from e
        if not 0 <= args.tolerance <= 255 or not 0 <= args.alpha_threshold <= 255:
            raise ValueError("容差/阈值必须在 0-255")
        if not 1 <= args.quality <= 100:
            raise ValueError("--quality 必须在 1-100")
        if args.bg_color and args.trim != "bg":
            raise ValueError("--bg-color 只用于 --trim bg")
        args.padding = parse_padding(args.padding)
        args.bbox = parse_bbox(args.bbox) if args.bbox else None
        if args.trim == "bbox" and args.bbox is None:
            raise ValueError("--trim bbox 需要 --bbox")
        if args.bbox is not None and args.trim != "bbox":
            raise ValueError("--bbox 只用于 --trim bbox")
        if args.trim == "bg" and not args.bg_color:
            raise ValueError("--trim bg 需要 --bg-color")
        scales = parse_scales(args.scales)
        out_dir = os.path.abspath(args.out)
        os.makedirs(out_dir, exist_ok=True)
        files, warnings = expand_inputs(args.inputs, out_dir, args.recursive)
        if not files:
            raise ValueError("没有可处理的位图")
        protected = {norm_key(f) for f in files}
        manifest_path = os.path.abspath(args.manifest or os.path.join(out_dir, MANIFEST_NAME))
        lock_path = manifest_path + LOCK_SUFFIX
        if os.path.isdir(manifest_path):
            raise ValueError(f"manifest 路径是目录: {manifest_path}")
        if not manifest_path.lower().endswith(".json"):
            raise ValueError("manifest 必须使用 .json 路径")
        if norm_key(manifest_path) in protected:
            raise ValueError("manifest 路径会覆盖输入文件")
        if norm_key(lock_path) in protected:
            raise ValueError("manifest 锁文件路径会覆盖输入文件")
        manifest_dir = os.path.dirname(manifest_path) or "."
        os.makedirs(manifest_dir, exist_ok=True)
        if args.manifest_mode == "merge" and os.path.exists(manifest_path):
            load_manifest(manifest_path)
        if args.name_pattern is None:
            args.pattern = "{name}@{scale}x{ext}" if any(s != 1 for s in scales) else "{name}{ext}"
        else:
            args.pattern = args.name_pattern
        if "{ext" not in args.pattern:
            raise ValueError("--name-pattern 必须包含 {ext}，避免写出非图片文件")
        if any(s != 1 for s in scales) and "{scale" not in args.pattern:
            raise ValueError("多倍率时 --name-pattern 必须包含 {scale}")
        args.background = parse_color(args.background) if args.background else None
        run_id = uuid.uuid4().hex[:8]
        run_at = datetime.now(timezone.utc).isoformat()
        reserved = set(protected)
        reserved.add(norm_key(manifest_path))
        reserved.add(norm_key(lock_path))
        results, failures = [], []
        seen = set()
        lock_fd = acquire_lock(lock_path)
        try:
            for i, source in enumerate(files):
                try:
                    got, failed, warns = process_one(source, args, scales, i, out_dir,
                                                     manifest_dir, run_id, run_at, reserved, seen)
                    results.extend(got)
                    failures.extend(failed)
                    warnings.extend(warns)
                except Exception as e:
                    failures.append({"source": source, "scale": None, "error": str(e)})

            def make_payload():
                existing = {"outputs": [], "runs": []}
                if args.manifest_mode == "merge":
                    existing = load_manifest(manifest_path)
                existing_outputs = existing.get("outputs", [])
                if args.prune:
                    kept = []
                    for e in existing_outputs:
                        p = manifest_entry_abs(e, manifest_dir)
                        if p and os.path.exists(p):
                            kept.append(e)
                            continue
                        if p and e.get("pathAbsolute"):
                            drive = os.path.splitdrive(p)[0]
                            root = (drive + os.sep) if drive else os.sep
                            if not os.path.exists(root):
                                warnings.append(f"保留不可达路径的 manifest 条目: {e.get('path')}")
                                kept.append(e)
                                continue
                    existing_outputs = kept
                merged = {}
                for entry in existing_outputs:
                    key = manifest_entry_abs(entry, manifest_dir)
                    if key:
                        merged[key] = entry
                for entry in results:
                    key = manifest_entry_abs(entry, manifest_dir)
                    merged[key] = entry
                runs = [] if args.manifest_mode == "replace" else list(existing.get("runs", []))
                runs.append({
                    "runId": run_id,
                    "runAt": run_at,
                    "options": {
                        "trim": args.trim,
                        "bgColor": args.bg_color,
                        "tolerance": args.tolerance,
                        "alphaThreshold": args.alpha_threshold,
                        "padding": list(args.padding),
                        "scales": scales,
                        "format": args.format,
                        "quality": args.quality,
                        "background": list(args.background) if args.background else None,
                        "namePattern": args.pattern,
                        "manifestMode": args.manifest_mode,
                        "prune": args.prune,
                        "overwrite": args.overwrite,
                        "recursive": args.recursive,
                        "out": out_dir,
                        "manifest": manifest_path,
                        "sourceDocument": args.source_document,
                        "note": args.note,
                    },
                    "outputs": [e["path"] for e in results],
                    "failures": failures,
                    "warnings": warnings,
                })
                return {
                    "tool": "trim-export.py",
                    "version": 2,
                    "generatedAt": datetime.now(timezone.utc).isoformat(),
                    "latestRunId": run_id,
                    "sourceDocument": args.source_document,
                    "note": args.note,
                    "options": runs[-1]["options"],
                    "outputs": list(merged.values()),
                    "runs": runs,
                    "failures": failures,
                    "warnings": warnings,
                }

            write_manifest_payload(manifest_path, make_payload)
        finally:
            release_lock(lock_fd, lock_path)
        result = "ok" if not failures else ("failed" if not results else "partial")
        print(json.dumps({
            "result": result,
            "outputs": len(results),
            "failures": failures,
            "warnings": warnings,
            "manifest": manifest_path,
        }, ensure_ascii=False))
        return 1 if failures else 0
    except (OSError, ValueError, RuntimeError) as e:
        print(json.dumps({"result": "error", "error": str(e)}, ensure_ascii=False))
        return 2


if __name__ == "__main__":
    sys.exit(main())
