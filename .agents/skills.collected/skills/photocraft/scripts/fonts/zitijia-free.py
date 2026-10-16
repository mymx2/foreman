#!/usr/bin/env python3
"""zitijia-free.py — 字体家（zitijia.com）免费商用字体检索与下载。

只取「免费商用」标签页（/t/免费商用，1146 条，支持 ?page=N）下的字体，
这些条目站点明确说明"下载后可用于商业用途不需要授权"。

用法：
  python zitijia-free.py search 圆体          # 在本地抓取的目录里按名称过滤
  python zitijia-free.py search 圆体 --limit 5
  python zitijia-free.py fetch --pages 1-3    # 抓目录到本地缓存并输出
  python zitijia-free.py download <itemId> [--to DIR]   # 取下载直链并存盘
  python zitijia-free.py url <itemId>         # 只打印下载直链

stdout 输出一行 JSON。目录缓存落在系统临时目录（不进仓库），`--refresh` 强制重抓。

授权边界（见 references/hellofont.md 的字体红线一节）：
- 只走免费商用标签；不碰"1元下载""个人版付费""在线授权"的付费条目。
- 站点声明"收集于网络，本站不享有任何版权"，二次销售/变卖不在授权内，
  商用前以字体详情页标注与原作者授权为准。
"""
import argparse
import json
import os
import re
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


def download_url(item_id):
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
    return url, data


def download(item_id, to_dir):
    url, raw = download_url(item_id)
    if not url:
        return {"ERROR": f"no url for {item_id}", "raw": raw}
    os.makedirs(to_dir, exist_ok=True)
    dest = os.path.join(to_dir, f"{item_id}.zip")
    urllib.request.urlretrieve(url, dest)
    try:
        with zipfile.ZipFile(dest) as z:
            names = [_fix_name(n) for n in z.namelist()]
    except zipfile.BadZipFile:
        names = []
    return {"id": item_id, "url": url, "zip": dest,
            "size": os.path.getsize(dest), "contents": names,
            "installable": [n for n in names if n.lower().endswith((".ttf", ".otf", ".ttc"))]}


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

    d = sub.add_parser("download", help="下载单个 itemId 的字体压缩包")
    d.add_argument("item_id")
    d.add_argument("--to", default=os.path.join(tempfile.gettempdir(), "zitijia-downloads"))

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
            print(json.dumps(download(args.item_id, args.to), ensure_ascii=False))
        elif args.cmd == "url":
            url, raw = download_url(args.item_id)
            print(json.dumps({"id": args.item_id, "url": url, "raw": raw}, ensure_ascii=False))
    except urllib.error.HTTPError as e:
        print(json.dumps({"ERROR": f"HTTP {e.code}: {e.read().decode('utf-8', 'replace')[:200]}"}))
        return 1
    except (urllib.error.URLError, OSError, ValueError) as e:
        print(json.dumps({"ERROR": str(e)}))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
