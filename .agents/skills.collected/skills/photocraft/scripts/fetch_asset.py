#!/usr/bin/env python3
"""fetch_asset.py — 按尺寸下载测试用占位图/照片（可选工具，只为测试准备输入）。

用法（stdout 输出一行 JSON）:
  python <skill-dir>/scripts/fetch_asset.py placeholder 800 600 [--text Hi] [--bg 409eff] [--fg ffffff] [--seed s]
  python <skill-dir>/scripts/fetch_asset.py photo 800 600 --seed p1 [--scene product] [--grayscale] [--blur 1-10]
  python <skill-dir>/scripts/fetch_asset.py avatar 128 --seed user-1 [--style devimg]
  python <skill-dir>/scripts/fetch_asset.py skeleton 350 120 [--type card]
  python <skill-dir>/scripts/fetch_asset.py scene 800 600 [--variant empty] [--seed s]
  python <skill-dir>/scripts/fetch_asset.py qr 128 --seed demo
  python <skill-dir>/scripts/fetch_asset.py picsum 200 300 --seed avatar-1
  python <skill-dir>/scripts/fetch_asset.py placehold 600 400 --bg 000000 --fg ffffff [--text Hi]
  python <skill-dir>/scripts/fetch_asset.py pexels 800 600 --query nature [--variant large2x] [--orientation landscape]
  python <skill-dir>/scripts/fetch_asset.py pixabay 800 600 --query nature [--imagetype photo|illustration|vector]
通用参数: --out DIR（默认 ./test-assets）、--name 文件名（只给文件名，不含路径）。

路由:
  placeholder/photo/avatar/skeleton/scene/qr  https://cdn.devimg.cn（免 Key）
  picsum                                      https://picsum.photos（免 Key；纯数字 --seed 走 /id/）
  placehold                                   https://placehold.co（免 Key，纯色块）
  pexels                                      api.pexels.com，Key 放环境变量 PEXELS_API_KEY
  pixabay                                     pixabay.com/api，Key 放环境变量 PIXABAY_API_KEY

规则:
- 下载的图只用于测试和复现。占位图（devimg/picsum/placehold）不进交付物；图库图（Pexels/Pixabay）
  要进交付物，必须先打开报告里的 sourcePage 和 licenseUrl 现场核对授权（人像、商标、转售等限制），
  并把核对结果记进稿件的描述文件。报告里的 licenseSummary 是写死的摘要，licenseVerified 恒为 false。
- 进测试脚本、对比基线的图一律带 --seed（同参数同图）；不带 seed 的随机结果只做一次性调试。
- 位图按目标尺寸居中裁切（需要 Pillow；缺失时保留原图并在报告里写明），SVG 不缩放。
- 各来源限额以其官方文档为准；遇到 HTTP 429 等一会儿再试，不要批量抓取。
退出码: 0 成功；2 参数错误、缺 Key、网络或响应错误。
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
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) fetch_asset/2.0"}
MAX_BYTES = 25 * 1024 * 1024
DEVIMG_KINDS = ("placeholder", "photo", "avatar", "skeleton", "scene", "qr")
LICENSE = {
    "devimg": ("占位素材，只用于测试", "https://devimg.cn/guide/fair-use.html"),
    "picsum": ("占位照片，只用于测试", "https://picsum.photos"),
    "placehold": ("合成色块，只用于测试", "https://placehold.co"),
    "pexels": ("Pexels License 摘要（未核实）：一般可免费使用、无需署名；对可识别人物、商标与原样转售"
               "有限制，不提供肖像/物权授权", "https://www.pexels.com/license/"),
    "pixabay": ("Pixabay Content License 摘要（未核实）：一般可免费使用、无需署名；对可识别人物、商标与原样转售"
                "有限制，不提供肖像/物权授权", "https://pixabay.com/service/license-summary/"),
}


def looks_like_image(data, content_type):
    head = data.lstrip()[:64]
    if head.startswith((b"\x89PNG", b"\xff\xd8", b"GIF8")):
        return True
    if head.startswith(b"RIFF") and data[8:12] == b"WEBP":
        return True
    return ("svg" in content_type or "xml" in content_type) and b"<svg" in data[:512].lower()


def fetch(url, headers=None):
    if urllib.parse.urlparse(url).scheme != "https":
        raise RuntimeError(f"只接受 https 地址: {url}")
    req = urllib.request.Request(url, headers={**UA, **(headers or {})})
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = resp.read(MAX_BYTES + 1)
        content_type = (resp.headers.get("Content-Type") or "").lower()
        final_url = resp.geturl()
    if urllib.parse.urlparse(final_url).scheme != "https":
        raise RuntimeError(f"重定向到了非 https 地址: {final_url}")
    if len(data) > MAX_BYTES:
        raise RuntimeError(f"响应超过 {MAX_BYTES // (1024 * 1024)} MiB: {url}")
    if len(data) < 100 or not looks_like_image(data, content_type):
        raise RuntimeError(f"响应不是图片（{len(data)} B, {content_type or '无 Content-Type'}），"
                           f"可能是限流页或错误页: {url}")
    return data, content_type


def sniff_ext(data):
    head = data.lstrip()[:64]
    for magic, ext in ((b"\x89PNG", ".png"), (b"\xff\xd8", ".jpg"), (b"GIF8", ".gif")):
        if head.startswith(magic):
            return ext
    if head.startswith(b"RIFF") and data[8:12] == b"WEBP":
        return ".webp"
    if b"<svg" in data[:512].lower():
        return ".svg"
    raise RuntimeError("无法识别图片格式")


def fit_to_size(data, width, height, ext):
    """Centre-crop to the target size. Returns (data, note, resized, source_size)."""
    if ext not in (".png", ".jpg", ".webp"):
        return data, None, False, None
    try:
        from PIL import Image, ImageOps
    except ImportError:
        return data, "未安装 Pillow，保留原图尺寸", False, None
    try:
        with Image.open(io.BytesIO(data)) as im:
            size = im.size
            if size == (width, height):
                return data, None, False, size
            fmt = {".png": "PNG", ".jpg": "JPEG", ".webp": "WEBP"}[ext]
            im = im.convert("RGB" if fmt == "JPEG" else "RGBA")
            fitted = ImageOps.fit(im, (width, height), method=getattr(Image, "Resampling", Image).LANCZOS)
            buf = io.BytesIO()
            fitted.save(buf, format=fmt, **({"quality": 92} if fmt == "JPEG" else {}))
            return buf.getvalue(), None, True, size
    except (OSError, ValueError) as exc:
        return data, f"缩放失败，保留原图: {exc}", False, None


def with_query(base, **params):
    query = urllib.parse.urlencode({k: v for k, v in params.items() if v not in (None, "")})
    return f"{base}?{query}" if query else base


def build_url(kind, w, h, p):
    quote = urllib.parse.quote
    if kind == "placeholder":
        path = f"/seed/{quote(p.seed, safe='')}/{w}/{h}.png" if p.seed else f"/{w}/{h}.png"
        return with_query(DEVIMG + path, text=p.text, bg=p.bg, fg=p.fg)
    if kind == "photo":
        return with_query(f"{DEVIMG}/photo/{w}/{h}", scene=p.scene, seed=p.seed, format="png",
                          grayscale=1 if p.grayscale else None, blur=p.blur or None)
    if kind == "avatar":
        return f"{DEVIMG}/avatar/{quote(p.style, safe='')}/{quote(p.seed, safe='')}/{w}.png"
    if kind == "skeleton":
        return with_query(f"{DEVIMG}/skeleton/{w}/{h}.png", type=p.type_)
    if kind == "scene":
        return with_query(f"{DEVIMG}/scene/{quote(p.variant or 'empty', safe='')}", w=w, h=h, seed=p.seed)
    if kind == "qr":
        return f"{DEVIMG}/qr/{quote(p.seed, safe='')}/{w}.png"
    if kind == "picsum":
        seg = f"id/{p.seed}" if p.seed.isdigit() else f"seed/{quote(p.seed or 'asset', safe='')}"
        return f"https://picsum.photos/{seg}/{w}/{h}.jpg"
    if kind == "placehold":
        colors = "/".join(x for x in (p.bg, p.fg) if x)
        return with_query(f"https://placehold.co/{w}x{h}{'/' + colors if colors else ''}.png", text=p.text)
    raise ValueError(kind)


def _api_json(url, headers=None):
    req = urllib.request.Request(url, headers={**UA, **(headers or {})})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def fetch_pexels(w, h, p):
    key = os.environ.get("PEXELS_API_KEY")
    if not key:
        raise RuntimeError("Pexels 需要 API Key：放进环境变量 PEXELS_API_KEY（不要写在命令行里）")
    payload = _api_json(with_query("https://api.pexels.com/v1/search", query=p.query, per_page=1,
                                   orientation=p.orientation), {"Authorization": key})
    photos = payload.get("photos") or []
    if not photos:
        raise RuntimeError(f"Pexels 没有结果: {p.query}")
    ph = photos[0]
    src = ph.get("src") or {}
    url = src.get(p.variant) or src.get("large2x") or src.get("original")
    if not url:
        raise RuntimeError("Pexels 响应里没有可用的 src")
    return url, {"author": ph.get("photographer"), "sourcePage": ph.get("url"),
                 "contentId": ph.get("id"), "apiSize": f"{ph.get('width')}x{ph.get('height')}"}


def fetch_pixabay(w, h, p):
    key = os.environ.get("PIXABAY_API_KEY")
    if not key:
        raise RuntimeError("Pixabay 需要 API Key：放进环境变量 PIXABAY_API_KEY")
    orient = {"landscape": "horizontal", "portrait": "vertical"}.get(p.orientation or "")
    payload = _api_json(with_query("https://pixabay.com/api/", key=key, q=p.query,
                                   image_type=p.imagetype, category=p.category, orientation=orient,
                                   safesearch="true", per_page=3))
    hits = payload.get("hits") or []
    if not hits:
        raise RuntimeError(f"Pixabay 没有结果: {p.query}")
    hit = hits[0]
    extra = {"author": hit.get("user"), "sourcePage": hit.get("pageURL"), "contentId": hit.get("id"),
             "apiSize": f"{hit.get('imageWidth')}x{hit.get('imageHeight')}"}
    url = hit.get("vectorURL") if p.imagetype == "vector" else None
    if p.imagetype == "vector" and not url:
        extra["note"] = "响应里没有 vectorURL（矢量原件需要完整 API 权限），已改用位图"
    url = url or hit.get("largeImageURL") or hit.get("webformatURL")
    if not url:
        raise RuntimeError("Pixabay 响应里没有可用的图片地址")
    return url, extra


def unique_name(out_dir, name):
    base, ext = os.path.splitext(name)
    candidate, i = name, 2
    while os.path.exists(os.path.join(out_dir, candidate)):
        candidate, i = f"{base}-{i}{ext}", i + 1
    return candidate


def main():
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, OSError):
            pass
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("kind", choices=list(DEVIMG_KINDS) + ["picsum", "placehold", "pexels", "pixabay"])
    ap.add_argument("width", type=int)
    ap.add_argument("height", type=int, nargs="?", default=0, help="省略时等于 width")
    ap.add_argument("--out", default="test-assets")
    ap.add_argument("--name", default="")
    ap.add_argument("--seed", default="")
    ap.add_argument("--text", default="")
    ap.add_argument("--bg", default="")
    ap.add_argument("--fg", default="")
    ap.add_argument("--scene", default="")
    ap.add_argument("--style", default="devimg")
    ap.add_argument("--type", dest="type_", default="card")
    ap.add_argument("--variant", default="", help="scene 的变体（默认 empty），或 pexels 的 src 档位")
    ap.add_argument("--query", default="")
    ap.add_argument("--orientation", default="")
    ap.add_argument("--imagetype", default="photo", choices=["all", "photo", "illustration", "vector"])
    ap.add_argument("--category", default="")
    ap.add_argument("--grayscale", action="store_true")
    ap.add_argument("--blur", type=int, default=0)
    args = ap.parse_args()

    def error(message):
        print(json.dumps({"result": "error", "error": message}, ensure_ascii=False))
        return 2

    w, h = args.width, args.height or args.width
    if w <= 0 or h <= 0:
        return error("宽高必须大于 0")
    if args.kind in ("avatar", "qr") and not args.seed:
        return error(f"{args.kind} 需要 --seed")
    if args.kind in ("pexels", "pixabay") and not args.query:
        return error(f"{args.kind} 需要 --query")
    if args.blur and (args.kind != "photo" or not 1 <= args.blur <= 10):
        return error("--blur 只用于 photo，取值 1-10")
    if args.name and os.path.basename(args.name) != args.name:
        return error("--name 只接受文件名，不含路径")
    notes = []
    if args.kind == "photo" and not args.seed:
        notes.append("没给 --seed，结果不可复现（只限一次性调试）")
    if args.seed and args.kind in ("pexels", "pixabay"):
        notes.append("--seed 只用于 devimg/picsum，图库接口不接受")
    report = {"result": "ok", "kind": args.kind, "wanted": f"{w}x{h}"}
    try:
        os.makedirs(args.out, exist_ok=True)
        if args.kind == "pexels":
            url, extra = fetch_pexels(w, h, args)
            source = "pexels"
        elif args.kind == "pixabay":
            url, extra = fetch_pixabay(w, h, args)
            source = "pixabay"
        else:
            url, extra = build_url(args.kind, w, h, args), {}
            source = "devimg" if args.kind in DEVIMG_KINDS else args.kind
        note = extra.pop("note", None)
        if note:
            notes.append(note)
        report.update(extra)
        data, _content_type = fetch(url)
        ext = sniff_ext(data)
        data, resize_note, resized, source_size = fit_to_size(data, w, h, ext)
        if source_size:
            report["sourceSize"] = f"{source_size[0]}x{source_size[1]}"
        report["actual"] = f"{w}x{h}" if resized else report.get("sourceSize", "unknown")
        report["resized"] = resized
        if resize_note:
            notes.append(resize_note)
        if args.name:
            stem, given = os.path.splitext(args.name)
            if given.lower() != ext:
                notes.append(f"扩展名 {given or '(无)'} 与内容 {ext} 不符，已改为 {stem + ext}")
                args.name = stem + ext
        name = unique_name(args.out, args.name or f"{args.kind}-{w}x{h}-{int(time.time() * 1000)}{ext}")
        dest = os.path.join(args.out, name)
        with open(dest, "wb") as handle:
            handle.write(data)
        summary, license_url = LICENSE[source]
        stock = source in ("pexels", "pixabay")
        report.update({"source": source, "url": url, "path": os.path.abspath(dest), "bytes": len(data),
                       "seed": args.seed or None, "licenseSummary": summary, "licenseUrl": license_url,
                       "licenseVerified": False,
                       "use": ("测试/复现专用；进交付物前到 sourcePage 与 licenseUrl 核对授权并记录" if stock
                               else "只用于测试，不进交付物")})
        if notes:
            report["notes"] = notes
    except (urllib.error.HTTPError, urllib.error.URLError, RuntimeError, OSError, ValueError) as exc:
        hint = "（HTTP 429 限流，稍后再试）" if getattr(exc, "code", None) == 429 else ""
        return error(f"{exc}{hint}")
    print(json.dumps(report, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
