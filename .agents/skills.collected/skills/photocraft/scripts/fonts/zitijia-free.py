#!/usr/bin/env python3
"""zitijia-free.py — 字体家（zitijia.com）免费商用字体检索与下载。

只取「免费商用」标签页（/t/免费商用，1146 条，支持 ?page=N）下的字体，
这些条目站点明确说明"下载后可用于商业用途不需要授权"。

用法：
  python zitijia-free.py search 圆体          # 在本地抓取的目录里按名称过滤
  python zitijia-free.py search 圆体 --limit 5
  python zitijia-free.py fetch --pages 1-3    # 抓目录到本地缓存并输出；download 前必须先有缓存
  python zitijia-free.py download <itemId> [--to DIR] [--force]  # 校验免费目录、下载并安全解出字体
  python zitijia-free.py url <itemId>         # 只打印下载直链（需先 fetch）

stdout 输出一行 JSON。目录缓存落在系统临时目录（不进仓库），`--refresh` 强制重抓。
`download` 先核对缓存中的免费商用条目，再限制下载主机并安全解压，拒绝 zip-slip/绝对路径。

授权边界（见 references/hellofont.md 的字体红线一节）：
- 只走免费商用标签；不碰"1元下载""个人版付费""在线授权"的付费条目。
- 站点声明"收集于网络，本站不享有任何版权"，二次销售/变卖不在授权内，
  商用前以字体详情页标注与原作者授权为准。
"""
import argparse
import json
import os
import re
import shutil
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile

BASE = "https://www.zitijia.com"
FREE_TAG_PATH = "/t/" + urllib.parse.quote("免费商用")
CACHE = os.path.join(tempfile.gettempdir(), "zitijia-free-cache.json")
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0"}
MAX_ZIP_BYTES = 200 * 1024 * 1024
MAX_MEMBER_BYTES = 100 * 1024 * 1024
MAX_EXTRACT_BYTES = 300 * 1024 * 1024
EXTRACT_EXTS = {".ttf", ".otf", ".ttc", ".txt", ".md", ".pdf"}


def _get(url, timeout=25):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", "replace")


def _parse_list(html):
    """从列表页抽取 (itemId, name)。名称在 el-col 的 title 上。"""
    out = []
    seen = set()
    for m in re.finditer(r'<div class="el-col[^"]*"\s+title="([^"]*)"[\s\S]{0,600}?/i/(\d+)\.html', html):
        name, item_id = m.group(1), m.group(2)
        if item_id in seen:
            continue
        seen.add(item_id)
        out.append({"id": item_id, "name": name})
    return out


def _total(html):
    m = re.search(r"共\s*(\d+)\s*条", html)
    return int(m.group(1)) if m else None


def fetch(pages, refresh):
    cache = {}
    if not refresh and os.path.isfile(CACHE):
        try:
            cache = json.load(open(CACHE, encoding="utf-8"))
        except (ValueError, OSError):
            cache = {}
    fonts = cache.get("fonts", {})
    total = cache.get("total")
    for p in pages:
        html = _get(BASE + FREE_TAG_PATH + (f"?page={p}" if p > 1 else ""))
        if total is None:
            total = _total(html)
        for f in _parse_list(html):
            fonts.setdefault(f["id"], f)
        time.sleep(0.4)
    payload = {"total": total, "fetched": len(fonts), "pages": list(pages), "fonts": fonts}
    json.dump(payload, open(CACHE, "w", encoding="utf-8"), ensure_ascii=False)
    return {"total": total, "fetched": len(fonts),
            "fonts": sorted(fonts.values(), key=lambda f: f["name"])}


def _load_cache():
    if not os.path.isfile(CACHE):
        return None
    try:
        with open(CACHE, encoding="utf-8") as f:
            return json.load(f)
    except (ValueError, OSError):
        return None


def _assert_free(item_id):
    if not re.fullmatch(r"\d+", item_id):
        raise ValueError(f"itemId 必须是纯数字: {item_id!r}")
    cache = _load_cache()
    if cache is None:
        raise RuntimeError("免费商用目录缓存不存在；先运行 fetch --pages 1-5")
    if item_id not in (cache.get("fonts") or {}):
        raise RuntimeError(f"itemId {item_id} 不在免费商用目录缓存中，拒绝下载")


def download_url(item_id):
    _assert_free(item_id)
    req = urllib.request.Request(
        BASE + "/downloadCheck",
        data=json.dumps({"itemId": item_id}).encode(),
        headers={**UA, "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=20) as resp:
        data = json.loads(resp.read().decode("utf-8", "replace"))
    url = data.get("url") or ""
    if url.startswith("//"):
        url = "https:" + url
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme != "https" or parsed.hostname != "static.zitijia.com":
        raise RuntimeError(f"下载直链不是 https://static.zitijia.com: {url!r}")
    return url, data


def _safe_part(part):
    part = re.sub(r'[<>:"|?*\x00-\x1f]', "_", part).strip().rstrip(".")
    if part in ("", ".", ".."):
        raise RuntimeError("zip 内含非法路径")
    return part


def _safe_extract(zip_path, out_dir):
    out_root = os.path.abspath(out_dir)
    os.makedirs(out_root, exist_ok=True)
    extracted = []
    total = 0
    with zipfile.ZipFile(zip_path) as z:
        for info in z.infolist():
            if info.is_dir():
                continue
            if info.file_size > MAX_MEMBER_BYTES:
                raise RuntimeError(f"zip 内单文件超过 {MAX_MEMBER_BYTES // (1024 * 1024)}MiB: {info.filename}")
            name = _fix_name(info.filename).replace("\\", "/")
            if name.startswith("/") or re.match(r"^[A-Za-z]:", name):
                raise RuntimeError(f"zip 内含绝对路径: {info.filename}")
            parts = [p for p in name.split("/") if p and p != "."]
            if not parts or any(p == ".." for p in parts):
                raise RuntimeError(f"zip 内含路径穿越: {info.filename}")
            parts = [_safe_part(p) for p in parts]
            if os.path.splitext(parts[-1])[1].lower() not in EXTRACT_EXTS:
                continue
            dest = os.path.abspath(os.path.join(out_root, *parts))
            if os.path.commonpath([out_root, dest]) != out_root:
                raise RuntimeError(f"zip 解压目标越界: {info.filename}")
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            read = 0
            with z.open(info) as src, open(dest, "wb") as dst:
                while True:
                    chunk = src.read(1 << 20)
                    if not chunk:
                        break
                    read += len(chunk)
                    if read > MAX_MEMBER_BYTES or total + read > MAX_EXTRACT_BYTES:
                        raise RuntimeError(f"zip 解压超过大小上限: {info.filename}")
                    dst.write(chunk)
            total += read
            extracted.append(os.path.relpath(dest, out_root))
    return extracted


def download(item_id, to_dir, force=False):
    url, _ = download_url(item_id)
    os.makedirs(to_dir, exist_ok=True)
    dest = os.path.join(to_dir, f"{item_id}.zip")
    if os.path.exists(dest) and not force:
        raise RuntimeError(f"zip 已存在: {dest}；确认覆盖加 --force")
    tmp = dest + ".part"
    total = 0
    try:
        with urllib.request.urlopen(url, timeout=30) as resp:
            final = urllib.parse.urlparse(resp.geturl())
            if final.scheme != "https" or final.hostname != "static.zitijia.com":
                raise RuntimeError(f"下载重定向到非白名单地址: {resp.geturl()}")
            with open(tmp, "wb") as f:
                while True:
                    chunk = resp.read(1 << 20)
                    if not chunk:
                        break
                    total += len(chunk)
                    if total > MAX_ZIP_BYTES:
                        raise RuntimeError(f"zip 超过 {MAX_ZIP_BYTES // (1024 * 1024)}MiB")
                    f.write(chunk)
        os.replace(tmp, dest)
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)
    extract_dir = os.path.join(to_dir, item_id)
    extracted = _safe_extract(dest, extract_dir)
    fonts = [n for n in extracted if n.lower().endswith((".ttf", ".otf", ".ttc"))]
    return {"id": item_id, "url": url, "zip": dest, "size": os.path.getsize(dest),
            "extractDir": extract_dir, "extracted": extracted, "fonts": fonts,
            "installable": fonts, "freeListChecked": True}


def _fix_name(name):
    """zip 内文件名多为 GBK 编码，尝试还原。"""
    try:
        raw = name.encode("cp437")
        for enc in ("gbk", "utf-8"):
            try:
                return raw.decode(enc)
            except UnicodeDecodeError:
                continue
    except (UnicodeEncodeError, UnicodeDecodeError):
        pass
    return name


def main():
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, OSError):
            pass
    ap = argparse.ArgumentParser(description="字体家免费商用字体检索与下载")
    sub = ap.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("search", help="在已抓取缓存里按名称过滤")
    s.add_argument("keyword")
    s.add_argument("--limit", type=int, default=20)
    s.add_argument("--refresh", action="store_true", help="先重抓第 1 页再搜")
    s.add_argument("--pages", default="1-5", help="缓存缺失时抓的页范围，如 1-5")

    f = sub.add_parser("fetch", help="抓免费商用目录到本地缓存")
    f.add_argument("--pages", default="1-5")
    f.add_argument("--refresh", action="store_true")

    d = sub.add_parser("download", help="下载单个 itemId 的字体压缩包并安全解压")
    d.add_argument("item_id")
    d.add_argument("--to", default=os.path.join(tempfile.gettempdir(), "zitijia-downloads"))
    d.add_argument("--force", action="store_true", help="覆盖已存在的 zip")

    u = sub.add_parser("url", help="只打印下载直链")
    u.add_argument("item_id")
    args = ap.parse_args()

    def pages(spec):
        if "-" in spec:
            a, b = spec.split("-", 1)
            return list(range(int(a), int(b) + 1))
        return [int(x) for x in spec.split(",")]

    try:
        if args.cmd == "fetch":
            print(json.dumps(fetch(pages(args.pages), args.refresh), ensure_ascii=False))
        elif args.cmd == "search":
            if args.refresh or not os.path.isfile(CACHE):
                fetch(pages(args.pages), args.refresh)
            cache = json.load(open(CACHE, encoding="utf-8"))
            hits = [f for f in cache["fonts"].values() if args.keyword in f["name"]]
            print(json.dumps({"keyword": args.keyword, "total": cache.get("total"),
                              "cached": len(cache["fonts"]), "hits": hits[:args.limit]},
                             ensure_ascii=False))
        elif args.cmd == "download":
            print(json.dumps(download(args.item_id, args.to, args.force), ensure_ascii=False))
        elif args.cmd == "url":
            url, raw = download_url(args.item_id)
            print(json.dumps({"id": args.item_id, "url": url, "raw": raw}, ensure_ascii=False))
    except urllib.error.HTTPError as e:
        print(json.dumps({"ERROR": f"HTTP {e.code}: {e.read().decode('utf-8', 'replace')[:200]}"}))
        return 1
    except (urllib.error.URLError, OSError, ValueError, RuntimeError, zipfile.BadZipFile) as e:
        print(json.dumps({"ERROR": str(e)}))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
