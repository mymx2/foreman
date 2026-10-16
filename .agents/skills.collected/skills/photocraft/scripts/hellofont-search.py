#!/usr/bin/env python3
"""hellofont-search.py — 字由（hellofont.cn）字体目录检索。

用法：
  python hellofont-search.py 站酷                 # 关键词搜索
  python hellofont-search.py 黑体 --tags 15,73    # 关键词 + 标签（黑体 & 免费商用）
  python hellofont-search.py --tags 73 --page-size 50   # 只按标签浏览

stdout 输出一行 JSON：
  {"total": N, "fonts": [{"id", "name", "family", "version", "file",
                          "familyCount", "hot", "license", "preview"}, ...]}
license: free=免费商用可直接用 / member=会员商用 / licensed=需单独或商业授权。

只做目录检索。官网不提供 ttf/otf 直链：字体文件由字由桌面客户端按账号授权
下载并激活（网页的"激活/下载"按钮只是唤起客户端），获取路径与授权红线见
references/hellofont.md。禁止绕过授权渠道抓取字体文件。

签名参数内嵌于官网前端 JS（每个访客都能拿到的公开值，非用户凭据），
仅用于复现官网自身的目录查询请求；接口变更时到官网 all.js 的 u.ajax
header 构造处重新核对，也可用 HELLOFONT_APPID / HELLOFONT_SECRET 覆盖。
"""
import argparse
import hashlib
import json
import os
import sys
import time
import urllib.error
import urllib.request

APPID = os.environ.get("HELLOFONT_APPID", "15248D0E-8FAE-4B68-B759-3B7447B8DD3A")
SECRET = os.environ.get("HELLOFONT_SECRET", "047BB327-1200-4F07-95AE-66DC5451263B")
SEARCH_URL = "https://back3.hellofont.cn/FontDistributionManagement/api/FontSearch/GetFontSearchItem"


def _sign(method, timestamp):
    raw = f"{SECRET}appid={APPID}&method={method}&timestamp={timestamp}{SECRET}"
    return hashlib.md5(raw.encode()).hexdigest()


def search(keyword, tags, page, page_size, order):
    method = SEARCH_URL.rsplit("/", 1)[-1]
    timestamp = str(int(time.time() * 1000))
    payload = {
        "pageNum": page,
        "pageSize": page_size,
        "orderTag": order,
        "searchKey": keyword,
        "fontTagIdList": tags,
    }
    req = urllib.request.Request(
        SEARCH_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "appid": APPID,
            "sign": _sign(method, timestamp),
            "timestamp": timestamp,
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0",
            "Referer": "https://www.hellofont.cn/font-list",
        },
    )
    with urllib.request.urlopen(req, timeout=20) as resp:
        data = json.loads(resp.read().decode("utf-8", "replace"))
    raw_list = data.get("FontList") or []
    fonts = []
    for f in raw_list:
        if f.get("IsFree"):
            license_tag = "free"
        elif f.get("IsMemberFont"):
            license_tag = "member"
        else:
            license_tag = "licensed"
        fonts.append({
            "id": f.get("id"),
            "name": f.get("ProductName"),
            "family": f.get("ProductSetName"),
            "version": f.get("Version"),
            "file": f.get("ProductFileName"),
            "familyCount": f.get("FamilyCount"),
            "hot": f.get("ApplyHot"),
            "license": license_tag,
            "preview": f.get("PreviewFileUrl"),
        })
    return {"total": data.get("SearchCount", len(fonts)), "fonts": fonts}


def main():
    ap = argparse.ArgumentParser(description="字由字体目录检索（只查目录，不下载字体文件）")
    ap.add_argument("keyword", nargs="?", default="", help="字体名/关键词，可空")
    ap.add_argument("--tags", default="", help="标签 id，逗号分隔，如 15,73（详见 references/hellofont.md）")
    ap.add_argument("--page", type=int, default=0, help="页码，0 起（默认 0）")
    ap.add_argument("--page-size", type=int, default=20, help="每页条数（默认 20）")
    ap.add_argument("--order", type=int, default=0, help="排序 orderTag（默认 0）")
    args = ap.parse_args()

    tags = [int(t) for t in args.tags.replace("，", ",").split(",") if t.strip()]
    if not args.keyword.strip() and not tags:
        ap.error("关键词与 --tags 至少给一个（都不给服务端只回 TimeStamp）")

    try:
        result = search(args.keyword.strip(), tags, args.page, args.page_size, args.order)
    except urllib.error.HTTPError as e:
        print(json.dumps({"ERROR": f"HTTP {e.code}: {e.read().decode('utf-8', 'replace')[:200]}"}))
        return 1
    except (urllib.error.URLError, OSError, ValueError) as e:
        print(json.dumps({"ERROR": str(e)}))
        return 1
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
