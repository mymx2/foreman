"""draft.list：列出剪映草稿（读草稿根索引与回收站索引，两者均为明文 JSON）。

只能读索引层字段：草稿名、时长、体积、草稿 ID、版本、时间戳、目录是否存在。
画布尺寸、轨道、素材路径、字幕条数在 draft_content.json 里，该文件加密，本脚本不做解密。

用法：
    python scripts/draft_list.py                 # 全部
    python scripts/draft_list.py --active-only
    python scripts/draft_list.py --name 口播
    python scripts/draft_list.py --format table
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import jy_common as C


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--active-only", action="store_true", help="只看在册草稿，忽略回收站")
    ap.add_argument("--name", help="按草稿名模糊筛选")
    ap.add_argument("--format", choices=["json", "table"], default="json")
    args = ap.parse_args()

    if not C.DRAFT_ROOT.is_dir():
        C.emit(C.fail("draft.list", "draft-root-missing", f"草稿根不存在: {C.DRAFT_ROOT}"))
        return 1

    rows = C.draft_entries()
    rows = [r for r in rows if r.get("name") or r.get("error")]
    if args.active_only:
        rows = [r for r in rows if r.get("bucket") == "active"]
    if args.name:
        needle = args.name.lower()
        rows = [r for r in rows if needle in (r.get("name") or "").lower()]

    if args.format == "table":
        if not rows:
            print("（无草稿）", file=sys.stderr)
        else:
            print(f"{'状态':<8}{'草稿名':<28}{'时长':<14}{'素材体积':<10}{'目录':<6}",
                  file=sys.stderr)
            for r in rows:
                state = "在册" if r.get("bucket") == "active" else "回收站"
                print(f"{state:<8}{(r.get('name') or '-'):<28}"
                      f"{(r.get('duration') or '-'):<14}{(r.get('materials_size') or '-'):<10}"
                      f"{'有' if r.get('folder_exists') else '无':<6}", file=sys.stderr)
        print(file=sys.stderr)

    content_fields = {
        "canvas_size": "索引层不含；明文草稿用 jy.py inspect",
        "tracks": "索引层不含；明文草稿用 jy.py inspect",
        "material_paths": "索引层不含；明文草稿用 jy.py inspect",
        "caption_count": "索引层不含；明文草稿用 jy.py inspect",
    }
    C.emit(C.ok("draft.list", {
        "count": len(rows),
        "items": rows,
        "content_fields_blocked": content_fields,
        "note": "索引层只给草稿名/路径/时长；明文草稿可用 jy.py inspect 读轨道/素材/文字；"
                "加密的 draft_content.json 不解密",
    }, evidence={"index": str(C.ROOT_META)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
