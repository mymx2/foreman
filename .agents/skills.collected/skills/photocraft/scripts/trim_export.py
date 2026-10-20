#!/usr/bin/env python3
"""trim_export.py — 位图裁边、加 padding、多倍率与命名导出（只处理已渲染位图，不读 PSD 图层）。

用法:
  python <skill-dir>/scripts/trim_export.py INPUT... --out DIR
         [--trim none|alpha|bg|bbox] [--bg-color #RRGGBB] [--tolerance 0-255] [--bbox x,y,w,h]
         [--alpha-threshold 0-255] [--padding N|L,T,R,B] [--scales 1,2]
         [--format auto|png|webp|jpeg] [--quality 1-100] [--background #RRGGBB]
         [--name-pattern "{name}@{scale}x{ext}"] [--source-document TEXT] [--note TEXT]
         [--manifest PATH] [--manifest-mode merge|replace] [--prune] [--overwrite] [--recursive]

裁边（默认 none，不裁）:
  alpha  按 alpha 裁掉透明边：alpha <= --alpha-threshold（默认 8）的像素算透明；没有 alpha 时报错。
  bg     按 --bg-color 裁纯色边：与背景色在任一 RGB 通道上相差 > --tolerance 才算内容。
         --tolerance 默认 8，是给引擎渲染的 PNG 用的起点；JPEG 或带噪背景要调高，合成纯色图可以 0。
         没有默认背景色，必须给 --bg-color；输入含透明像素时拒绝（改用 alpha）。
  bbox   按 --bbox x,y,w,h 手动裁。
padding: 默认 0；一个值四边相同，或 L,T,R,B；按源像素计。先缩放内容再补 padding，padding 区不会被重采样。
格式:   auto 跟随源扩展名（tif 输出 png）；JPEG 没有 alpha，源有 alpha 或要 padding 时必须给 --background。
命名:   占位符 {name} {scale} {ext} {index} {w} {h}；必须含 {ext}，且 {ext} 自带前导点
        （写 {name}@{scale}x{ext}，不要写 {name}@{scale}x.{ext}）；倍率含非 1 值时还必须含 {scale}。
        默认：只有 1x 时 {name}{ext}，否则 {name}@{scale}x{ext}。
        --recursive 会把子目录里的文件都写进同一个 --out，同名文件会报"输出重名"。
安全:   只写 --out 内；默认不覆盖已有输出（--overwrite 才覆盖），任何情况下不覆盖输入、manifest 和锁文件；
        先写临时文件再原子替换。16-bit / 浮点源 fail closed（先转 8-bit）；EXIF 方向先应用再导出。
manifest（默认 <out>/assets-manifest.json，合并旧记录并保留 runs；整个运行持锁，可并发）:
  所有框都是 [x, y, w, h]，字段名写明坐标系:
    trimBoxXYWH          裁剪框，EXIF 校正后的源图像素
    sourceAlphaBoxXYWH   源图 alpha>0 的范围，同上坐标系
    contentAlphaBoxXYWH  缩放后、加 padding 前的内容图像素
    outputAlphaBoxXYWH   输出图像素
  sourceHasAlpha / sourceTransparentRatio 描述裁剪前的源图；contentTransparentRatio 只看裁剪后内容
  （硬边裁完常为 0）；比例统计 alpha<255 的像素；paddingOnlyAlpha=true 表示输出的透明只来自 padding。
  geometryOnly=true / semanticCutout=false：本工具只做几何裁切，不产生语义抠图。
  --manifest-mode replace 重建 manifest；--prune 去掉已不存在的旧条目。
退出码: 0 全部成功；1 有文件失败（看 failures）；2 参数、锁或 manifest 错误、缺 Pillow。
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

TOOL = "trim_export.py"
LEGACY_TOOLS = (TOOL, "trim-export.py")
MANIFEST_VERSION = 3
BOX_CONVENTION = ("[x, y, w, h]；trimBoxXYWH/sourceAlphaBoxXYWH 为 EXIF 校正后的源图像素，"
                  "contentAlphaBoxXYWH 为缩放后内容像素，outputAlphaBoxXYWH 为输出图像素")
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
    s = (value or "").strip().lstrip("#")
    if len(s) == 3:
        s = "".join(c * 2 for c in s)
    if not re.fullmatch(r"[0-9a-fA-F]{6}", s):
        raise ValueError(f"颜色格式不对（要 #RRGGBB）: {value}")
    return tuple(int(s[i:i + 2], 16) for i in (0, 2, 4))


def parse_padding(value):
    parts = [x.strip() for x in str(value).split(",")]
    if len(parts) == 1:
        parts = parts * 4
    if len(parts) != 4:
        raise ValueError("--padding 需要 1 个值或 L,T,R,B 四个值")
    nums = [int(x) for x in parts]
    if any(x < 0 for x in nums):
        raise ValueError("--padding 不能为负")
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
    result = []
    for raw in (x.strip() for x in str(value).split(",")):
        if not raw:
            continue
        scale = float(raw)
        if scale <= 0:
            raise ValueError("--scales 必须大于 0")
        if scale not in result:
            result.append(scale)
    if not result:
        raise ValueError("--scales 至少给一个值")
    return result


def sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def norm_key(path):
    return os.path.normcase(os.path.realpath(os.path.abspath(path)))


def is_under(path, directory):
    try:
        return os.path.commonpath([norm_key(path), norm_key(directory)]) == norm_key(directory)
    except ValueError:
        return False


def rel_posix(path, start):
    """(path, absolute): POSIX separators, absolute only across drives."""
    try:
        return os.path.relpath(path, start).replace("\\", "/"), False
    except ValueError:
        return os.path.abspath(path).replace("\\", "/"), True


def expand_inputs(paths, out_dir, recursive):
    files, warnings = [], []
    for raw in paths:
        path = os.path.abspath(raw)
        if os.path.isdir(path):
            walker = os.walk(path) if recursive else [(path, [], os.listdir(path))]
            for root, _dirs, names in walker:
                for name in sorted(names):
                    full = os.path.join(root, name)
                    if not os.path.isfile(full):
                        continue
                    if os.path.splitext(name)[1].lower() not in IMAGE_EXTS:
                        warnings.append(f"跳过非位图: {full}")
                    elif is_under(full, out_dir):
                        warnings.append(f"跳过输出目录内的文件: {full}")
                    else:
                        files.append(full)
        elif os.path.isfile(path):
            if os.path.splitext(path)[1].lower() not in IMAGE_EXTS:
                raise ValueError(f"不支持的输入格式: {path}")
            if is_under(path, out_dir):
                warnings.append(f"显式输入位于输出目录内；输出仍不会覆盖它: {path}")
            files.append(path)
        else:
            raise ValueError(f"输入不存在: {path}")
    unique = []
    for f in files:
        if f not in unique:
            unique.append(f)
    return unique, warnings


def check_source_bit_depth(path, im):
    if im.mode.startswith("I;16") or im.mode in ("I", "F") or "16" in im.mode:
        raise RuntimeError(f"16-bit/浮点源不受支持，先转 8-bit: {path}（mode={im.mode}）")
    if im.format == "PNG":
        with open(path, "rb") as handle:
            head = handle.read(25)
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


def ltrb_to_xywh(box):
    return [box[0], box[1], box[2] - box[0], box[3] - box[1]] if box else None


def trim_box(im, mode, bg_color, tolerance, bbox, alpha_threshold):
    """Crop box as (left, top, right, bottom) in oriented source pixels."""
    from PIL import Image, ImageChops
    width, height = im.size
    if mode == "none":
        return (0, 0, width, height)
    if mode == "alpha":
        if not has_alpha(im):
            raise RuntimeError("输入没有 alpha 通道；改用 --trim bg 或 --trim bbox")
        box = im.convert("RGBA").getchannel("A").point(
            lambda v: 255 if v > alpha_threshold else 0).getbbox()
    elif mode == "bg":
        if has_alpha(im) and im.getchannel("A").getextrema()[0] < 255:
            raise RuntimeError("输入含透明像素；--trim bg 不可靠，改用 --trim alpha 或先压平背景")
        rgb = im.convert("RGB")
        diff = ImageChops.difference(rgb, Image.new("RGB", rgb.size, parse_color(bg_color)))
        r, g, b = diff.split()
        box = ImageChops.lighter(ImageChops.lighter(r, g), b).point(
            lambda v: 255 if v > tolerance else 0).getbbox()
    else:
        x, y, w, h = bbox
        if x < 0 or y < 0 or x + w > width or y + h > height:
            raise RuntimeError(f"--bbox 超出图像范围（{width}x{height}）")
        box = (x, y, x + w, y + h)
    if not box:
        raise RuntimeError("裁边后没有内容；检查 trim 模式、颜色或阈值")
    return box


def scale_image(im, scale):
    from PIL import Image
    if scale == 1:
        return im
    size = (max(1, round(im.width * scale)), max(1, round(im.height * scale)))
    return im.resize(size, getattr(Image, "Resampling", Image).LANCZOS)


def pad_scaled(content, padding_out, background, fmt):
    from PIL import Image
    left, top, right, bottom = padding_out
    width, height = content.width + left + right, content.height + top + bottom
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
        name = pattern.format(name=stem, scale=f"{scale:g}", ext=ext, index=index, w=width, h=height)
    except (KeyError, IndexError, ValueError) as exc:
        raise ValueError(f"命名模板有误（未知占位符或花括号不配对）: {exc}") from exc
    if (not name or os.path.isabs(name) or re.match(r"^[A-Za-z]:", name)
            or re.search(r'[<>:"/\\|?*\x00-\x1f]', name) or ".." in name
            or name != name.rstrip(" .")):
        raise ValueError(f"命名模板会产生非法或越界的文件名: {name!r}")
    if name.split(".")[0].upper() in WINDOWS_RESERVED:
        raise ValueError(f"命名模板产生 Windows 保留名: {name!r}")
    return name


def alpha_stats(im):
    """(has alpha, ratio of alpha<255, [x,y,w,h] of alpha>0 or None)."""
    if "A" not in im.getbands():
        return False, 0.0, None
    alpha = im.getchannel("A")
    total = im.width * im.height
    transparent = sum(alpha.histogram()[:255])
    box = alpha.point(lambda v: 255 if v > 0 else 0).getbbox()
    return True, round(transparent / total, 6) if total else 0.0, ltrb_to_xywh(box)


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
    fd, tmp = tempfile.mkstemp(prefix=".trim-export-", suffix=os.path.splitext(out_path)[1] or ".tmp",
                               dir=parent)
    os.close(fd)
    try:
        save_output(im, tmp, fmt, quality, background, info)
        digest, size = sha256(tmp), os.path.getsize(tmp)
        os.replace(tmp, out_path)
        tmp = None
        return digest, size
    finally:
        if tmp and os.path.exists(tmp):
            try:
                os.remove(tmp)
            except OSError:
                pass


def process_one(source, args, scales, index, out_dir, manifest_dir, run_id, run_at, reserved, seen):
    from PIL import Image, ImageOps
    im = Image.open(source)
    check_source_bit_depth(source, im)
    im.load()
    warnings = []
    if getattr(im, "is_animated", False):
        im.seek(0)
        warnings.append(f"动图只取第一帧: {source}")
    raw_size = [im.width, im.height]
    orientation = im.getexif().get(0x0112, 1)
    transposed = orientation not in (None, 1)
    if transposed:
        im = ImageOps.exif_transpose(im) or im
        warnings.append(f"已应用 EXIF orientation={orientation} 并移除方向信息: {source}")
    oriented_size = [im.width, im.height]
    info = dict(im.info)
    source_mode = im.mode
    if source_mode not in ("RGB", "RGBA") and info.get("icc_profile"):
        warnings.append(f"源模式 {source_mode} 与输出 RGB/RGBA 不同，已丢弃 ICC profile: {source}")
        info.pop("icc_profile", None)
    if source_mode == "CMYK":
        warnings.append(f"CMYK 源已转 RGB/RGBA，印刷用途另做色彩转换: {source}")
    source_alpha = has_alpha(im)
    working = im.convert("RGBA") if source_alpha else im.convert("RGB")
    src_has, src_ratio, src_box = alpha_stats(working)
    box = trim_box(working, args.trim, args.bg_color, args.tolerance, args.bbox, args.alpha_threshold)
    if args.trim == "alpha" and working.getchannel("A").getextrema()[0] == 255:
        warnings.append("alpha 全不透明：trim alpha 没有可裁的透明边")
    if args.trim == "bg" and box == (0, 0, working.width, working.height):
        warnings.append("trim bg 没有裁掉任何边；检查背景色/容差，或改用 bbox")
    if args.trim == "bg" and os.path.splitext(source)[1].lower() in (".jpg", ".jpeg") \
            and args.tolerance <= 8:
        warnings.append("JPEG 背景有压缩噪声；考虑提高 --tolerance 或手动 --bbox")
    fmt = output_format(source, args.format)
    background = args.background
    if fmt == "jpeg" and background is None and (source_alpha or any(args.padding)):
        raise RuntimeError("JPEG 需要 --background（源有 alpha 或要加 padding）")
    content = working.crop(box)
    results, failures = [], []
    source_rel, source_abs = rel_posix(source, manifest_dir)
    source_sha = sha256(source)
    options = {"trim": args.trim, "bgColor": args.bg_color, "tolerance": args.tolerance,
               "alphaThreshold": args.alpha_threshold, "padding": list(args.padding),
               "format": fmt, "quality": args.quality,
               "background": list(background) if background else None,
               "namePattern": args.pattern, "sourceDocument": args.source_document,
               "note": args.note}
    for scale in scales:
        try:
            scaled = scale_image(content, scale)
            padding_out = [round(p * scale) for p in args.padding]
            padded = pad_scaled(scaled, padding_out, background, fmt)
            name = safe_name(source, args.pattern, scale, fmt, index, padded.width, padded.height)
            out_path = os.path.join(out_dir, name)
            if not is_under(out_path, out_dir):
                raise RuntimeError(f"输出越界: {out_path}")
            key = norm_key(out_path)
            if key in reserved:
                raise RuntimeError("输出路径会覆盖输入、manifest 或锁文件，拒绝")
            if key in seen:
                raise RuntimeError(f"输出重名: {out_path}；调整 --name-pattern")
            out_sha, out_size = save_output_atomic(padded, out_path, fmt, args.quality, background,
                                                   info, args.overwrite)
            seen.add(key)
            content_has, content_ratio, content_box = alpha_stats(scaled)
            final_has, final_ratio, final_box = alpha_stats(padded)
            path_rel, path_abs = rel_posix(out_path, manifest_dir)
            results.append({
                "source": source_rel, "sourceAbsolute": source_abs,
                "path": path_rel, "pathAbsolute": path_abs,
                "trim": args.trim, "trimBoxXYWH": ltrb_to_xywh(box),
                "padding": list(args.padding), "paddingOut": padding_out, "scale": scale,
                "width": padded.width, "height": padded.height,
                "sourceSize": raw_size, "orientedSize": oriented_size,
                "outputSize": [padded.width, padded.height], "upscaled": scale > 1,
                "exifTransposed": transposed, "sourceMode": source_mode,
                "outputMode": padded.mode, "format": fmt,
                "sourceHasAlpha": src_has, "sourceTransparentRatio": src_ratio,
                "sourceAlphaBoxXYWH": src_box,
                "alpha": final_has, "transparentRatio": final_ratio,
                "contentAlpha": content_has, "contentTransparentRatio": content_ratio,
                "contentAlphaBoxXYWH": content_box, "outputAlphaBoxXYWH": final_box,
                "paddingOnlyAlpha": bool(final_has and final_ratio > 0 and any(padding_out)
                                         and (not content_has or content_ratio == 0)),
                "geometryOnly": True, "semanticCutout": False,
                "sourceDocument": args.source_document, "note": args.note,
                "options": options, "runId": run_id, "runAt": run_at,
                "sourceSha256": source_sha, "outputSha256": out_sha, "bytes": out_size,
            })
            if scale > 1:
                warnings.append(f"{os.path.basename(source)} 以 {scale:g}x 放大导出；确认源分辨率足够")
        except Exception as exc:
            failures.append({"source": source, "scale": scale, "error": str(exc)})
    return results, failures, warnings


def manifest_entry_abs(entry, manifest_dir):
    path = entry.get("path")
    if not path:
        return None
    if entry.get("pathAbsolute") or os.path.isabs(path):
        return norm_key(path)
    return norm_key(os.path.join(manifest_dir, path))


def manifest_relative(path, base):
    try:
        return os.path.relpath(path, base).replace(os.sep, "/")
    except ValueError:
        return path


def load_manifest(path):
    if not os.path.exists(path):
        return {"outputs": [], "runs": []}
    with open(path, encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict) or data.get("tool") not in LEGACY_TOOLS:
        raise RuntimeError("已有 manifest 不是本工具写的；用 --manifest-mode replace 或换路径")
    outputs, runs = data.get("outputs"), data.get("runs", [])
    if not isinstance(outputs, list) or not isinstance(runs, list):
        raise RuntimeError("已有 manifest 的 outputs/runs 结构不对；用 --manifest-mode replace 或换路径")
    if any(not isinstance(e, dict) or not isinstance(e.get("path"), str) or not e["path"] for e in outputs):
        raise RuntimeError("已有 manifest 有缺 path 的条目；用 --manifest-mode replace 或换路径")
    if any(not isinstance(r, dict) for r in runs):
        raise RuntimeError("已有 manifest 的 runs 条目不对；用 --manifest-mode replace 或换路径")
    data["runs"] = runs
    return data


def _pid_alive(pid):
    if not isinstance(pid, int) or pid <= 0:
        return False
    if os.name == "nt":
        import ctypes
        kernel32 = ctypes.windll.kernel32
        kernel32.OpenProcess.restype = ctypes.c_void_p
        kernel32.OpenProcess.argtypes = [ctypes.c_ulong, ctypes.c_int, ctypes.c_ulong]
        kernel32.GetExitCodeProcess.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_ulong)]
        kernel32.CloseHandle.argtypes = [ctypes.c_void_p]
        handle = kernel32.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
        if not handle:
            return kernel32.GetLastError() == 5  # access denied: the PID is in use
        try:
            code = ctypes.c_ulong()
            if not kernel32.GetExitCodeProcess(handle, ctypes.byref(code)):
                return True
            return code.value == 259  # STILL_ACTIVE
        finally:
            kernel32.CloseHandle(handle)
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return False


def _lock_pid(lock_path):
    try:
        with open(lock_path, encoding="ascii") as handle:
            return int(handle.read().split()[0])
    except (OSError, ValueError, IndexError):
        return None


def acquire_lock(lock_path):
    deadline = time.time() + LOCK_TIMEOUT
    while True:
        try:
            fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_RDWR)
            os.write(fd, f"{os.getpid()} {time.time()}".encode("ascii"))
            return fd
        except FileExistsError:
            pid = _lock_pid(lock_path)
            try:
                age = time.time() - os.path.getmtime(lock_path)
            except OSError:
                age = 0
            # A dead owner's lock is stale; a live owner is never evicted. Locks without a
            # PID fall back to the age check.
            if (pid is not None and not _pid_alive(pid)) or (pid is None and age > STALE_LOCK_SECONDS):
                try:
                    os.remove(lock_path)
                except OSError:
                    pass
                continue
            if time.time() > deadline:
                raise RuntimeError(f"manifest 正被另一个进程写入: {lock_path}；稍后重试，"
                                   "确认没有进程在写时可手动删除锁文件")
            time.sleep(0.2)


def release_lock(fd, lock_path):
    try:
        os.close(fd)
    except OSError:
        pass
    if _lock_pid(lock_path) == os.getpid():
        try:
            os.remove(lock_path)
        except OSError:
            pass


def write_manifest(manifest_path, payload):
    parent = os.path.dirname(manifest_path) or "."
    os.makedirs(parent, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=".assets-manifest-", suffix=".tmp", dir=parent)
    os.close(fd)
    try:
        with open(tmp, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
        os.replace(tmp, manifest_path)
        tmp = None
    finally:
        if tmp and os.path.exists(tmp):
            try:
                os.remove(tmp)
            except OSError:
                pass


def build_payload(args, scales, out_dir, manifest_path, manifest_dir, run_id, run_at,
                  results, failures, warnings):
    existing = load_manifest(manifest_path) if args.manifest_mode == "merge" else {"outputs": [], "runs": []}
    old_outputs = existing.get("outputs", [])
    if args.prune:
        kept = []
        for entry in old_outputs:
            path = manifest_entry_abs(entry, manifest_dir)
            if path and os.path.exists(path):
                kept.append(entry)
            elif path and entry.get("pathAbsolute"):
                drive = os.path.splitdrive(path)[0]
                if not os.path.exists((drive + os.sep) if drive else os.sep):
                    warnings.append(f"保留不可达路径的 manifest 条目: {entry.get('path')}")
                    kept.append(entry)
        old_outputs = kept
    merged = {}
    for entry in old_outputs + results:
        key = manifest_entry_abs(entry, manifest_dir)
        if key:
            merged[key] = entry
    runs = [] if args.manifest_mode == "replace" else list(existing.get("runs", []))
    run_options = {
        "trim": args.trim, "bgColor": args.bg_color, "tolerance": args.tolerance,
        "alphaThreshold": args.alpha_threshold, "padding": list(args.padding), "scales": scales,
        "format": args.format, "quality": args.quality,
        "background": list(args.background) if args.background else None,
        "namePattern": args.pattern, "manifestMode": args.manifest_mode, "prune": args.prune,
        "overwrite": args.overwrite, "recursive": args.recursive,
        "out": manifest_relative(out_dir, manifest_dir),
        "manifest": manifest_relative(manifest_path, manifest_dir),
        "sourceDocument": args.source_document, "note": args.note,
    }
    runs.append({"runId": run_id, "runAt": run_at, "options": run_options,
                 "outputs": [e["path"] for e in results], "failures": failures,
                 "warnings": warnings})
    return {"tool": TOOL, "version": MANIFEST_VERSION, "boxConvention": BOX_CONVENTION,
            "generatedAt": datetime.now(timezone.utc).isoformat(), "latestRunId": run_id,
            "sourceDocument": args.source_document, "note": args.note, "options": run_options,
            "outputs": list(merged.values()), "runs": runs, "failures": failures,
            "warnings": warnings}


def main():
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, OSError):
            pass
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("inputs", nargs="+", help="位图文件或目录")
    ap.add_argument("--out", required=True, help="输出目录（必填）")
    ap.add_argument("--trim", choices=["none", "alpha", "bg", "bbox"], default="none")
    ap.add_argument("--bg-color", default=None, help="trim bg 的背景色，如 #ffffff（无默认值）")
    ap.add_argument("--tolerance", type=int, default=8, help="trim bg 容差 0-255（默认 8）")
    ap.add_argument("--bbox", default=None, help="trim bbox 的 x,y,w,h")
    ap.add_argument("--alpha-threshold", type=int, default=8, help="alpha 裁边阈值 0-255（默认 8）")
    ap.add_argument("--padding", default="0", help="0 / N / L,T,R,B（源像素）")
    ap.add_argument("--scales", default="1", help="倍率列表，如 1,2")
    ap.add_argument("--format", choices=["auto", "png", "webp", "jpeg"], default="auto")
    ap.add_argument("--quality", type=int, default=92, help="JPEG/WebP 质量 1-100（默认 92）")
    ap.add_argument("--background", default=None, help="不透明导出的底色 #RRGGBB")
    ap.add_argument("--name-pattern", default=None, help="命名模板，须含 {ext}")
    ap.add_argument("--source-document", default=None, help="来源 PSD/稿件，写进 manifest")
    ap.add_argument("--note", default=None, help="画心/纸边/投影等决定，写进 manifest")
    ap.add_argument("--overwrite", action="store_true", help="允许覆盖已有输出")
    ap.add_argument("--recursive", action="store_true", help="递归目录（输出不分子目录）")
    ap.add_argument("--manifest", default=None, help=f"manifest 路径（默认 <out>/{MANIFEST_NAME}）")
    ap.add_argument("--manifest-mode", choices=["merge", "replace"], default="merge")
    ap.add_argument("--prune", action="store_true", help="合并时去掉已不存在的旧条目")
    args = ap.parse_args()

    try:
        try:
            from PIL import Image  # noqa: F401
        except ImportError as exc:
            raise RuntimeError("需要 Pillow：pip install pillow") from exc
        if not 0 <= args.tolerance <= 255 or not 0 <= args.alpha_threshold <= 255:
            raise ValueError("--tolerance / --alpha-threshold 必须在 0-255")
        if not 1 <= args.quality <= 100:
            raise ValueError("--quality 必须在 1-100")
        if args.bg_color and args.trim != "bg":
            raise ValueError("--bg-color 只用于 --trim bg")
        if args.trim == "bg" and not args.bg_color:
            raise ValueError("--trim bg 需要 --bg-color")
        if args.bg_color:
            parse_color(args.bg_color)
        args.padding = parse_padding(args.padding)
        args.bbox = parse_bbox(args.bbox) if args.bbox else None
        if args.trim == "bbox" and args.bbox is None:
            raise ValueError("--trim bbox 需要 --bbox")
        if args.bbox is not None and args.trim != "bbox":
            raise ValueError("--bbox 只用于 --trim bbox")
        scales = parse_scales(args.scales)
        if args.name_pattern is None:
            args.pattern = "{name}@{scale}x{ext}" if any(s != 1 for s in scales) else "{name}{ext}"
        else:
            args.pattern = args.name_pattern
        if "{ext" not in args.pattern:
            raise ValueError("--name-pattern 必须包含 {ext}，避免写出非图片文件")
        if any(s != 1 for s in scales) and "{scale" not in args.pattern:
            raise ValueError("多倍率时 --name-pattern 必须包含 {scale}")
        args.background = parse_color(args.background) if args.background else None
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
            raise ValueError("manifest 必须是 .json 路径")
        if norm_key(manifest_path) in protected or norm_key(lock_path) in protected:
            raise ValueError("manifest 或锁文件路径会覆盖输入文件")
        manifest_dir = os.path.dirname(manifest_path) or "."
        os.makedirs(manifest_dir, exist_ok=True)
        if args.manifest_mode == "merge":
            load_manifest(manifest_path)
        run_id = uuid.uuid4().hex[:8]
        run_at = datetime.now(timezone.utc).isoformat()
        reserved = protected | {norm_key(manifest_path), norm_key(lock_path)}
        results, failures, seen = [], [], set()
        lock_fd = acquire_lock(lock_path)
        try:
            for index, source in enumerate(files):
                try:
                    got, failed, warns = process_one(source, args, scales, index, out_dir,
                                                     manifest_dir, run_id, run_at, reserved, seen)
                    results += got
                    failures += failed
                    warnings += warns
                except Exception as exc:
                    failures.append({"source": source, "scale": None, "error": str(exc)})
            write_manifest(manifest_path, build_payload(args, scales, out_dir, manifest_path,
                                                        manifest_dir, run_id, run_at, results,
                                                        failures, warnings))
        finally:
            release_lock(lock_fd, lock_path)
        status = "ok" if not failures else ("failed" if not results else "partial")
        print(json.dumps({"result": status, "outputs": len(results), "failures": failures,
                          "warnings": warnings, "manifest": manifest_path}, ensure_ascii=False))
        return 1 if failures else 0
    except (OSError, ValueError, RuntimeError) as exc:
        print(json.dumps({"result": "error", "error": str(exc)}, ensure_ascii=False))
        return 2


if __name__ == "__main__":
    sys.exit(main())
