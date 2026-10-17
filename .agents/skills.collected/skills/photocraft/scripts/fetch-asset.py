#!/usr/bin/env python3
"""fetch-asset.py — 测试/占位素材按尺寸下载落盘，供实际效果测试用。

来源与红线见 references/test-assets.md：
- 主源 devimg.cn（占位图/照片/头像/骨架/场景/码形，免 Key，--seed 钉结果）
- 备选 picsum.photos（照片）、placehold.co（色块）
- 真图 Pexels（PEXELS_API_KEY）与 Pixabay（PIXABAY_API_KEY，含矢量插画），Key 放环境变量
- 占位类素材只用于测试，不进生产成品；真图可商用，留来源记录。

用法（stdout 输出一行 JSON）：
  python fetch-asset.py placeholder 800 600 [--text Hi] [--bg 409eff] [--fg ffffff] [--seed s]
  python fetch-asset.py photo 800 600 --seed p1 [--scene product] [--grayscale] [--blur 1-10]
  python fetch-asset.py avatar 128 --seed user-1 [--style devimg]
  python fetch-asset.py skeleton 350 120 [--type card]
  python fetch-asset.py scene 800 600 --variant empty
  python fetch-asset.py qr 128 --seed demo
  python fetch-asset.py picsum 200 300 --seed avatar-1
  python fetch-asset.py placehold 600 400 --bg 000000 --fg FFF
  python fetch-asset.py pexels 800 600 --query nature [--variant large2x]
  python fetch-asset.py pixabay 800 600 --query nature [--imagetype photo|illustration|vector]

通用：--out DIR（默认 ./test-assets）、--name 文件名（默认按来源与参数生成）。
位图会按目标尺寸中心裁切（需 Pillow；缺失时保留原图并在报告里注明），SVG 不缩放。
"""
import argparse
import io
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

DEVIMG = "https://cdn.devimg.cn"
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) fetch-asset/1.0"}
LICENSE_NOTE = {
    "devimg": "占位素材，仅测试用；官方条款禁批量抓取，项目规则禁进生产（见 references/test-assets.md）",
    "picsum": "占位照片，仅测试用；备选源（同上）",
    "placehold": "合成色块，仅测试用；备选源（同上）",
    "pexels": "Pexels License：可商用、无需署名；不得原样转售或暗示代言，API 展示面按官方指南给 Pexels 链接",
    "pixabay": "Pixabay Content License：可商用、无需署名；展示搜索结果时标注来源，禁批量抓取与原样转售",
}


MAX_BYTES = 25 * 1024 * 1024


def looks_like_image(data, content_type):
    head = data.lstrip()[:64]
    if head.startswith((b"\x89PNG", b"\xff\xd8", b"GIF8")):
        return True
    if head.startswith(b"RIFF") and data[8:12] == b"WEBP":
        return True
    if ("svg" in content_type or "xml" in content_type) and b"<svg" in data[:512].lower():
        return True
    return False


def fetch(url, headers=None):
    if urllib.parse.urlparse(url).scheme != "https":
        raise RuntimeError(f"只接受 https 图片地址: {url}")
    req = urllib.request.Request(url, headers={**UA, **(headers or {})})
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = resp.read(MAX_BYTES + 1)
        content_type = (resp.headers.get("Content-Type") or "").lower()
        final_url = resp.geturl()
    if urllib.parse.urlparse(final_url).scheme != "https":
        raise RuntimeError(f"重定向到非 https 地址: {final_url}")
    if len(data) < 100:
        raise RuntimeError(f"响应太小（{len(data)}B），可能被限流页/错误页顶替: {url}")
    if len(data) > MAX_BYTES:
        raise RuntimeError(f"响应超过 {MAX_BYTES // (1024 * 1024)}MiB: {url}")
    if not looks_like_image(data, content_type):
        raise RuntimeError(f"响应不是图片（{len(data)}B, {content_type or '无 Content-Type'}），可能被限流页/错误页顶替: {url}")
    return data, content_type


def sniff_ext(data, content_type):
    head = data.lstrip()[:64]
    if head.startswith(b"\x89PNG"):
        return ".png"
    if head.startswith(b"\xff\xd8"):
        return ".jpg"
    if head.startswith(b"GIF8"):
        return ".gif"
    if head.startswith(b"RIFF") and data[8:12] == b"WEBP":
        return ".webp"
    if b"<svg" in data[:512].lower():
        return ".svg"
    raise RuntimeError(f"无法识别图片格式（Content-Type: {content_type or '未知'}）")


def fit_to_size(data, width, height, ext):
    """按目标尺寸中心裁切；Pillow 缺失或格式不支持时保留原图。"""
    if ext not in (".png", ".jpg", ".webp"):
        return data, ext, None, False
    try:
        from PIL import Image, ImageOps
    except ImportError:
        return data, ext, "未安装 Pillow，保留原图尺寸", False
    try:
        with Image.open(io.BytesIO(data)) as im:
            if im.size == (width, height):
                return data, ext, None, False
            fmt = {".png": "PNG", ".jpg": "JPEG", ".webp": "WEBP"}[ext]
            im = im.convert("RGB" if fmt == "JPEG" else "RGBA")
            resample = getattr(Image, "Resampling", Image).LANCZOS
            fitted = ImageOps.fit(im, (width, height), method=resample)
            buf = io.BytesIO()
            if fmt == "JPEG":
                fitted.save(buf, format=fmt, quality=92)
            else:
                fitted.save(buf, format=fmt)
            return buf.getvalue(), ext, None, True
    except (OSError, ValueError) as e:
        return data, ext, f"缩放失败，保留原图: {e}", False


def q(**kw):
    return urllib.parse.urlencode({k: v for k, v in kw.items() if v not in (None, "")})


def build_url(kind, a, b, p):
    if kind == "placeholder":
        path = f"/seed/{urllib.parse.quote(p.seed, safe='')}/{a}/{b}.png" if p.seed else f"/{a}/{b}.png"
        return f"{DEVIMG}{path}?" + q(text=p.text, bg=p.bg, fg=p.fg)
    if kind == "photo":
        return f"{DEVIMG}/photo/{a}/{b}?" + q(scene=p.scene, seed=p.seed, format="png",
                                              grayscale=1 if p.grayscale else None,
                                              blur=p.blur if p.blur else None)
    if kind == "avatar":
        return f"{DEVIMG}/avatar/{p.style}/{urllib.parse.quote(p.seed)}/{a}.png"
    if kind == "skeleton":
        return f"{DEVIMG}/skeleton/{a}/{b}.png?" + q(type=p.type_)
    if kind == "scene":
        return f"{DEVIMG}/scene/{p.variant}?" + q(w=a, h=b, seed=p.seed)
    if kind == "qr":
        return f"{DEVIMG}/qr/{urllib.parse.quote(p.seed)}/{a}.png"
    if kind == "picsum":
        seed = urllib.parse.quote(p.seed or "asset", safe="")
        seg = f"id/{p.seed}" if p.seed and p.seed.isdigit() else f"seed/{seed}"
        return f"https://picsum.photos/{seg}/{a}/{b}.jpg"
    if kind == "placehold":
        colors = "/".join(x for x in (p.bg, p.fg) if x)
        tail = f"/{colors}" if colors else ""
        return f"https://placehold.co/{a}x{b}{tail}.png?" + q(text=p.text)
    raise ValueError(kind)


def fetch_pexels(a, b, p):
    key = os.environ.get("PEXELS_API_KEY")
    if not key:
        raise RuntimeError("Pexels 需要 API Key：pexels.com/api 免费注册，放进环境变量 PEXELS_API_KEY")
    api = "https://api.pexels.com/v1/search?" + q(query=p.query, per_page=1, orientation=p.orientation)
    req = urllib.request.Request(api, headers={**UA, "Authorization": key})
    with urllib.request.urlopen(req, timeout=30) as resp:
        payload = json.loads(resp.read().decode("utf-8"))
    photos = payload.get("photos") or []
    if not photos:
        raise RuntimeError(f"Pexels 没有命中: {p.query}")
    ph = photos[0]
    src = ph.get("src") or {}
    url = src.get(p.variant) or src.get("large2x") or src.get("original")
    if not url:
        raise RuntimeError("Pexels 响应里没有可用的 src")
    return url, {"photographer": ph.get("photographer"), "source_page": ph.get("url"),
                 "content_id": ph.get("id"), "wanted": f"{a}x{b}",
                 "actual": f"{ph.get('width')}x{ph.get('height')}"}


def fetch_pixabay(a, b, p):
    key = os.environ.get("PIXABAY_API_KEY")
    if not key:
        raise RuntimeError("Pixabay 需要 API Key：pixabay.com/api/docs 登录后获取，放进环境变量 PIXABAY_API_KEY")
    orient = {"landscape": "horizontal", "portrait": "vertical"}.get(p.orientation or "")
    api = "https://pixabay.com/api/?" + q(key=key, q=p.query, image_type=p.imagetype,
                                          category=p.category or None, orientation=orient,
                                          safesearch="true", per_page=3)
    req = urllib.request.Request(api, headers={**UA})
    with urllib.request.urlopen(req, timeout=30) as resp:
        payload = json.loads(resp.read().decode("utf-8"))
    hits = payload.get("hits") or []
    if not hits:
        raise RuntimeError(f"Pixabay 没有命中: {p.query}")
    hit = hits[0]
    url = (hit.get("vectorURL") if p.imagetype == "vector" else None) \
        or hit.get("largeImageURL") or hit.get("webformatURL")
    if not url:
        raise RuntimeError("Pixabay 响应里没有可用的图片 URL")
    return url, {"photographer": hit.get("user"), "source_page": hit.get("pageURL"),
                 "content_id": hit.get("id"), "wanted": f"{a}x{b}",
                 "actual": f"{hit.get('imageWidth')}x{hit.get('imageHeight')}"}


def unique_name(out_dir, name):
    base, ext = os.path.splitext(name)
    candidate = name
    i = 2
    while os.path.exists(os.path.join(out_dir, candidate)):
        candidate = f"{base}-{i}{ext}"
        i += 1
    return candidate


def main():
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, OSError):
            pass

    ap = argparse.ArgumentParser(description="测试/占位素材按尺寸下载")
    ap.add_argument("kind", choices=["placeholder", "photo", "avatar", "skeleton", "scene", "qr",
                                     "picsum", "placehold", "pexels", "pixabay"])
    ap.add_argument("width", type=int)
    ap.add_argument("height", type=int, nargs="?", default=0)
    ap.add_argument("--out", default="test-assets")
    ap.add_argument("--name", default="")
    ap.add_argument("--seed", default="")
    ap.add_argument("--text", default="")
    ap.add_argument("--bg", default="")
    ap.add_argument("--fg", default="")
    ap.add_argument("--scene", default="")
    ap.add_argument("--style", default="devimg")
    ap.add_argument("--type", dest="type_", default="card")
    ap.add_argument("--variant", default="scene", help="scene 的 variant 或 pexels 的 src 档位")
    ap.add_argument("--query", default="")
    ap.add_argument("--orientation", default="")
    ap.add_argument("--imagetype", default="photo", choices=["all", "photo", "illustration", "vector"])
    ap.add_argument("--category", default="")
    ap.add_argument("--grayscale", action="store_true")
    ap.add_argument("--blur", type=int, default=0)
    args = ap.parse_args()

    a = args.width
    b = args.height or a
    note = ""
    if args.kind == "photo" and not args.seed:
        note = "未给 --seed，photo 结果不可复现（仅限一次性调试）"
    if args.seed and args.kind in ("pexels", "pixabay"):
        note = (note + "；" if note else "") + "--seed 仅用于 devimg/picsum，Pexels/Pixabay 不接受 seed"
    if args.kind == "photo" and not (10 <= a <= 4000 and 10 <= b <= 4000):
        print(json.dumps({"result": "error", "error": "尺寸范围 10-4000"}, ensure_ascii=False))
        return 2
    if args.blur and (args.kind != "photo" or not 1 <= args.blur <= 10):
        print(json.dumps({"result": "error", "error": "--blur 仅 photo 支持，取值 1-10"}, ensure_ascii=False))
        return 2
    if args.name and os.path.basename(args.name) != args.name:
        print(json.dumps({"result": "error", "error": "--name 只接受纯文件名（不含路径）"}, ensure_ascii=False))
        return 2

    os.makedirs(args.out, exist_ok=True)
    report = {"result": "ok", "kind": args.kind, "wanted": f"{a}x{b}"}
    if note:
        report["note"] = note
    try:
        if args.kind == "pexels":
            url, extra = fetch_pexels(a, b, args)
            report.update(extra)
            source = "pexels"
        elif args.kind == "pixabay":
            url, extra = fetch_pixabay(a, b, args)
            report.update(extra)
            source = "pixabay"
        else:
            url = build_url(args.kind, a, b, args)
            source = ("devimg" if args.kind in ("placeholder", "photo", "avatar", "skeleton", "scene", "qr")
                      else args.kind)
        data, content_type = fetch(url)
        ext = sniff_ext(data, content_type)
        source_size = report.get("actual")
        data, ext, resize_note, resized = fit_to_size(data, a, b, ext)
        if resized:
            if source_size:
                report["sourceSize"] = source_size
            report["actual"] = f"{a}x{b}"
            report["resized"] = True
        if resize_note:
            report["resizeNote"] = resize_note
        name = args.name or f"{args.kind}-{a}x{b}-{int(time.time() * 1000)}{ext}"
        name = unique_name(args.out, name)
        dest = os.path.join(args.out, name)
        with open(dest, "wb") as f:
            f.write(data)
        size = len(data)
        report.update({"source": source, "url": url, "path": dest, "bytes": size,
                       "license": LICENSE_NOTE[source], "seed": args.seed or None})
    except (urllib.error.HTTPError, urllib.error.URLError, RuntimeError, OSError, ValueError) as e:
        code = getattr(e, "code", None)
        hint = ""
        if code == 429:
            hint = "（触发限流，稍后再试；devimg 限 60-1000 次/分/IP，Pexels 限 200 次/时）"
        print(json.dumps({"result": "error", "error": f"{e}{hint}"}, ensure_ascii=False))
        return 2
    print(json.dumps(report, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
