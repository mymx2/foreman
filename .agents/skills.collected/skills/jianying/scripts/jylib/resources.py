"""剪映本机资源目录：把 ``Cache/ressdk_db/*/rp.db`` 与已下载的资源包对上。

``list/stats/resolve`` 只读；``download`` 只下载免费非商业资源，不登录、不解锁会员。
``cached`` 只表示资源包在本机存在，不代表账号有权益或导出一定会生效。
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import sqlite3
import tempfile
import time
import urllib.error
import uuid
import urllib.request
import zipfile
from pathlib import Path, PurePosixPath

from .errors import SkillError
from . import env as env_mod

DB_ENV = "JY_RESOURCE_DB"
PANEL_LABELS = {
    "fonts": "字体",
    "subtitle-templates": "字幕模板",
    "text": "文字模板",
    "bubble": "气泡",
    "bubble2": "气泡",
    "flower2": "花字",
    "sticker": "贴纸",
    "tool_text_glow": "文字光效",
    "lyrics": "歌词",
    "video": "视频素材/特效",
    "canvas": "模板/画布",
    "tone": "音色",
    "voice-change": "变声",
    "shuziren2408": "数字人",
    "digital_human": "数字人",
    "complex_video_mask": "复杂蒙版",
    "videomask": "视频蒙版",
    "matting": "抠像",
    "matting_stroke": "抠像描边",
    "adjust_collection": "调节",
    "camera-movement": "运镜",
    "camera_tracking": "镜头跟踪",
    "makeup": "美妆",
    "facial_features": "五官",
    "face_shape": "脸型",
    "skin_management": "皮肤",
    "manual-figure": "美体",
    "auto-beauty2": "美颜",
    "auto-beauty3": "美颜",
    "smart-relight": "智能补光",
    "ai_painting": "AI 绘画",
    "gameplay": "玩法",
    "insert": "插入",
    "mix": "混合",
    "curvespeed": "曲线变速",
}


def find_db(cache_root: Path | None = None) -> Path:
    env_path = os.environ.get(DB_ENV, "").strip()
    if env_path:
        path = Path(env_path).expanduser()
        if path.is_file():
            return path
        raise SkillError("资源数据库路径不存在", code="RESOURCE_DB_MISSING",
                         details={"path": str(path)})
    root = cache_root or env_mod.find_cache_root()
    candidates = sorted(
        (root / "ressdk_db").glob("*/rp.db"),
        key=lambda p: p.stat().st_mtime, reverse=True)
    if not candidates:
        raise SkillError("未找到剪映资源数据库 rp.db", code="RESOURCE_DB_MISSING",
                         details={"root": str(root)},
                         fix="先打开剪映素材面板，让它生成本机资源缓存")
    return candidates[0]


def _scan(cache_root: Path, folder: str) -> dict[str, Path]:
    result: dict[str, Path] = {}
    base = cache_root / folder
    if not base.is_dir():
        return result
    for outer in base.iterdir():
        if not outer.is_dir():
            continue
        for inner in outer.iterdir():
            if inner.is_dir():
                result.setdefault(inner.name, inner)
    return result


def cached_packages(cache_root: Path | None = None) -> dict[str, Path]:
    root = cache_root or env_mod.find_cache_root()
    packages = _scan(root, "effect")
    packages.update(_scan(root, "artistEffect"))
    packages.update(_scan(root, "fonts"))
    return packages


def _connect(db_path: Path):
    try:
        connection = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True, timeout=5)
        connection.row_factory = sqlite3.Row
        return connection
    except sqlite3.Error as exc:
        raise SkillError("资源数据库打不开", code="RESOURCE_DB_UNREADABLE",
                         details={"path": str(db_path), "reason": str(exc)}) from exc


def _row(item, packages: dict[str, Path]) -> dict:
    md5 = item["md5"] or ""
    package = packages.get(md5)
    panel = item["panel_name"] or ""
    extra = {}
    try:
        extra = json.loads(item["extra"] or "{}")
    except (TypeError, ValueError):
        extra = {}
    vip = bool(extra.get("is_vip")) or bool(item["is_vip"])
    business = bool(extra.get("is_business"))
    return {
        "id": item["id"],
        "title": item["title"] or "",
        "name": item["name"] or "",
        "panel": panel,
        "panel_label": PANEL_LABELS.get(panel, panel),
        "effect_type": item["effect_type"],
        "vip": vip,
        "business": business,
        "md5": md5,
        "cached": package is not None,
        "package_path": str(package) if package else None,
        "category_id": item["category_id"] or "",
        "category_name": item["category_name"] or "",
    }


def _like_escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _candidate(item) -> dict:
    extra = {}
    try:
        extra = json.loads(item["extra"] or "{}")
    except (TypeError, ValueError):
        extra = {}
    panel = item["panel_name"] or ""
    return {
        "id": item["id"],
        "title": item["title"] or "",
        "name": item["name"] or "",
        "panel": panel,
        "panel_label": PANEL_LABELS.get(panel, panel),
        "vip": bool(extra.get("is_vip")) or bool(item["is_vip"]),
        "business": bool(extra.get("is_business")),
    }


def _select(db_path: Path, where: str = "", params: tuple = (),
            limit: int | None = None):
    sql = ("select id, title, name, panel_name, effect_type, is_vip, md5, "
           "extra, category_id, category_name from effect")
    if where:
        sql += " where " + where
    sql += " order by title, id"
    if limit:
        sql += " limit ?"
        params = (*params, int(limit))
    connection = _connect(db_path)
    try:
        return connection.execute(sql, params).fetchall()
    except sqlite3.Error as exc:
        raise SkillError("资源查询失败", code="RESOURCE_DB_UNREADABLE",
                         details={"path": str(db_path), "reason": str(exc)}) from exc
    finally:
        connection.close()


def list_resources(*, db_path: Path | None = None, cache_root: Path | None = None,
                   panel: str | None = None, keyword: str | None = None,
                   cached_only: bool = False, include_vip: bool = False,
                   limit: int = 50) -> dict:
    if limit < 1 or limit > 2000:
        raise SkillError("limit 必须在 1–2000 之间", code="VALIDATION",
                         details={"limit": limit})
    db_path = db_path or find_db(cache_root)
    packages = cached_packages(cache_root)
    clauses = []
    params: list = []
    if panel:
        clauses.append("panel_name = ?")
        params.append(panel)
    if keyword:
        clauses.append("(title like ? escape '\\' or name like ? escape '\\')")
        pattern = f"%{_like_escape(str(keyword))}%"
        params.extend([pattern, pattern])
    rows = _select(db_path, " and ".join(clauses), tuple(params))
    items = [_row(item, packages) for item in rows]
    if not include_vip:
        items = [item for item in items if not item["vip"]]
    if cached_only:
        items = [item for item in items if item["cached"]]
    total = len(items)
    return {
        "db": str(db_path),
        "cache_root": str(cache_root or env_mod.find_cache_root()),
        "filters": {"panel": panel, "keyword": keyword,
                    "cached_only": cached_only, "include_vip": include_vip},
        "total": total,
        "truncated": total > limit,
        "items": items[:limit],
    }


def stats(*, db_path: Path | None = None, cache_root: Path | None = None) -> dict:
    db_path = db_path or find_db(cache_root)
    packages = cached_packages(cache_root)
    rows = _select(db_path)
    items = [_row(item, packages) for item in rows]
    panels: dict[str, dict] = {}
    for item in items:
        key = item["panel"] or "(unknown)"
        entry = panels.setdefault(key, {
            "panel": key,
            "label": PANEL_LABELS.get(key, key),
            "total": 0,
            "cached": 0,
            "free": 0,
        })
        entry["total"] += 1
        entry["cached"] += 1 if item["cached"] else 0
        entry["free"] += 0 if item["vip"] else 1
    return {
        "db": str(db_path),
        "cache_root": str(cache_root or env_mod.find_cache_root()),
        "packages": len(packages),
        "total": len(items),
        "cached": sum(1 for item in items if item["cached"]),
        "free": sum(1 for item in items if not item["vip"]),
        "panels": sorted(panels.values(), key=lambda x: x["total"], reverse=True),
    }


def _ambiguous(text: str, rows) -> SkillError:
    return SkillError(
        "资源引用匹配到多条记录，不能替你选",
        code="RESOURCE_AMBIGUOUS",
        details={"ref": text, "candidates": [_candidate(item) for item in rows[:10]]},
        fix="改用资源 id、md5 或完整标题；先跑 resource resolve 查看候选。",
    )


def resolve(ref: str, *, db_path: Path | None = None,
            cache_root: Path | None = None, allow_fuzzy: bool = True) -> dict:
    text = str(ref).strip()
    if not text:
        raise SkillError("resolve 需要 id、md5 或标题", code="VALIDATION")
    db_path = db_path or find_db(cache_root)
    packages = cached_packages(cache_root)
    if text.isdigit():
        rows = _select(db_path, "id = ?", (text,), limit=2)
    else:
        rows = _select(db_path, "md5 = ?", (text,), limit=1)
        if not rows:
            rows = _select(db_path, "title = ?", (text,))
        if not rows and allow_fuzzy:
            rows = _select(db_path, "title like ? escape '\\'",
                           (f"%{_like_escape(text)}%",), limit=11)
    if len(rows) > 1:
        raise _ambiguous(text, rows)
    if not rows:
        fix = "改用 id/md5/完整标题；模糊匹配只在 resource resolve 中提供候选。"
        raise SkillError("没有找到资源", code="RESOURCE_NOT_FOUND",
                         details={"ref": text, "fuzzy": allow_fuzzy},
                         fix=fix)
    item = _row(rows[0], packages)
    return {"db": str(db_path), "item": item}


ARTIST_PANELS = {
    "text", "subtitle-templates", "bubble", "bubble2", "flower2",
    "tool_text_glow", "lyrics",
}
FONT_SUFFIXES = {".ttf", ".otf", ".ttc"}


def _parse_urls(raw) -> list[str]:
    try:
        data = json.loads(raw or "[]")
    except (TypeError, ValueError):
        data = re.findall(r'https?://[^\s"\\]+', str(raw or ""))
    if isinstance(data, str):
        data = [data]
    if not isinstance(data, list):
        return []
    return [item for item in data
            if isinstance(item, str) and item.startswith(("http://", "https://"))]


def _expires(url: str):
    match = re.search(r"[?&]x-expires=(\d+)", url)
    return int(match.group(1)) if match else None


def _target_dir(cache_root: Path, panel: str, effect_id: str, md5: str) -> Path:
    md5_text = str(md5).strip()
    id_text = str(effect_id).strip()
    if not md5_text:
        raise SkillError("资源没有 md5，无法定位缓存目录",
                         code="RESOURCE_MD5_MISSING",
                         details={"id": id_text, "panel": panel})
    if not _COMPONENT.fullmatch(md5_text) or not _COMPONENT.fullmatch(id_text):
        raise SkillError("资源 id/md5 含非法字符", code="RESOURCE_PATH_INVALID",
                         details={"id": id_text, "md5": md5_text})
    folder = "fonts" if panel == "fonts" else (
        "artistEffect" if panel in ARTIST_PANELS else "effect")
    root = Path(cache_root)
    target = root / folder / id_text / md5_text
    try:
        if not target.resolve().is_relative_to(root.resolve()):
            raise SkillError("资源缓存路径越界", code="RESOURCE_PATH_INVALID",
                             details={"target": str(target)})
    except OSError as exc:
        raise SkillError("资源缓存路径无法解析", code="RESOURCE_PATH_INVALID",
                         details={"target": str(target), "reason": str(exc)}) from exc
    return target


def verify(ref: str, *, expect_panel: str | None = None,
           db_path: Path | None = None, cache_root: Path | None = None) -> dict:
    resolved = resolve(ref, db_path=db_path, cache_root=cache_root,
                       allow_fuzzy=False)
    item = resolved["item"]
    issues = []
    if item["vip"] or item["business"]:
        issues.append({"issue": "gated",
                       "detail": "会员/商业资源，技能不下载、不解锁"})
    if expect_panel and item["panel"] != expect_panel:
        issues.append({"issue": "panel_mismatch",
                       "detail": f"期望 {expect_panel}，实际 {item['panel']}"})
    if not item["cached"]:
        issues.append({"issue": "not_cached",
                       "detail": "资源包不在本机缓存；导出会 dependency_missing 或被忽略"})
    else:
        package = Path(item["package_path"])
        if not (package / "config.json").is_file():
            issues.append({"issue": "package_invalid",
                           "detail": "缓存目录缺少 config.json"})
        if item["panel"] == "fonts":
            try:
                item["font_path"] = str(font_file(package))
            except SkillError:
                issues.append({"issue": "font_missing",
                               "detail": "字体包没有 ttf/otf/ttc"})
    next_command = None
    if not item["cached"] and not item["vip"] and not item["business"]:
        next_command = f"jy.py resource download {item['id']} --apply"
    return {
        "db": resolved["db"],
        "item": item,
        "expected_panel": expect_panel,
        "usable": not issues,
        "issues": issues,
        "next": next_command,
    }


def font_file(package: str | Path) -> Path:
    root = Path(package)
    fonts = sorted(path for path in root.rglob("*")
                   if path.suffix.lower() in FONT_SUFFIXES)
    if not fonts:
        raise SkillError("字体包没有字体文件", code="PACKAGE_INVALID",
                         details={"path": str(root)})
    return fonts[0]


_MAX_ARCHIVE_ENTRIES = 2000
_MAX_ARCHIVE_BYTES = 512 * 1024 * 1024
_MAX_DOWNLOAD_BYTES = _MAX_ARCHIVE_BYTES
_COMPONENT = re.compile(r"^[0-9A-Za-z_-]{1,64}$")
_RESERVED_NAMES = {"con", "prn", "aux", "nul", *(f"com{i}" for i in range(1, 10)),
                   *(f"lpt{i}" for i in range(1, 10))}


def install_archive(archive: Path, target: Path, *, force: bool = False) -> None:
    if target.exists() and not force:
        raise SkillError("资源包已存在", code="OUTPUT_EXISTS",
                         details={"path": str(target)},
                         fix="确认要覆盖时加 --force")
    target.parent.mkdir(parents=True, exist_ok=True)
    temp = Path(tempfile.mkdtemp(prefix=".jy-resource-", dir=str(target.parent)))
    keep_temp = False
    try:
        try:
            with zipfile.ZipFile(archive) as bundle:
                infos = bundle.infolist()
                if len(infos) > _MAX_ARCHIVE_ENTRIES:
                    raise SkillError("资源包条目过多", code="PACKAGE_INVALID",
                                     details={"entries": len(infos),
                                              "limit": _MAX_ARCHIVE_ENTRIES})
                total = sum(int(info.file_size) for info in infos if not info.is_dir())
                if total > _MAX_ARCHIVE_BYTES:
                    raise SkillError("资源包解压后过大", code="PACKAGE_INVALID",
                                     details={"uncompressed": total,
                                              "limit": _MAX_ARCHIVE_BYTES})
                written_total = 0
                for info in infos:
                    name = info.filename.replace("\\", "/")
                    if not name or name.startswith("__MACOSX/"):
                        continue
                    relative = PurePosixPath(name)
                    if (relative.is_absolute() or ".." in relative.parts
                            or ":" in name
                            or any(part.rstrip(" .").lower() in _RESERVED_NAMES
                                   or part.rstrip(" .") != part
                                   for part in relative.parts)):
                        raise SkillError("资源包包含不安全路径", code="PACKAGE_INVALID",
                                         details={"entry": name})
                    destination = temp.joinpath(*relative.parts)
                    if info.is_dir():
                        destination.mkdir(parents=True, exist_ok=True)
                        continue
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    with bundle.open(info) as source, open(destination, "wb") as sink:
                        while True:
                            chunk = source.read(1024 * 1024)
                            if not chunk:
                                break
                            written_total += len(chunk)
                            if written_total > _MAX_ARCHIVE_BYTES:
                                raise SkillError(
                                    "资源包解压后过大", code="PACKAGE_INVALID",
                                    details={"uncompressed": written_total,
                                             "limit": _MAX_ARCHIVE_BYTES})
                            sink.write(chunk)
        except zipfile.BadZipFile as exc:
            raise SkillError("资源包不是合法 zip", code="PACKAGE_INVALID",
                             details={"path": str(archive)}) from exc
        except OSError as exc:
            raise SkillError("资源包条目写入失败", code="PACKAGE_INVALID",
                             details={"path": str(archive), "reason": str(exc)}) from exc
        if not (temp / "config.json").is_file():
            children = [child for child in temp.iterdir() if child.is_dir()]
            if len(children) == 1 and (children[0] / "config.json").is_file():
                inner = children[0]
                for child in list(inner.iterdir()):
                    shutil.move(str(child), str(temp / child.name))
                inner.rmdir()
            else:
                raise SkillError("资源包缺少 config.json", code="PACKAGE_INVALID",
                                 details={"path": str(archive)})
        previous = None
        if target.exists():
            previous = target.with_name(
                f".{target.name}.{uuid.uuid4().hex[:8]}.bak")
            os.replace(target, previous)
        try:
            os.replace(temp, target)
            keep_temp = True
        except OSError:
            if previous is not None and previous.exists() and not target.exists():
                os.replace(previous, target)
            raise
        if previous is not None:
            shutil.rmtree(previous, ignore_errors=True)
    finally:
        if not keep_temp:
            shutil.rmtree(temp, ignore_errors=True)


def download_resource(ref: str, *, db_path: Path | None = None,
                      cache_root: Path | None = None, apply: bool = False,
                      force: bool = False, timeout: int = 60) -> dict:
    cache_root = cache_root or env_mod.find_cache_root()
    db_path = db_path or find_db(cache_root)
    resolved = resolve(ref, db_path=db_path, cache_root=cache_root,
                       allow_fuzzy=False)
    item = resolved["item"]
    if item["vip"] or item["business"]:
        raise SkillError("会员/商业资源不下载", code="RESOURCE_GATED",
                         details={"id": item["id"], "title": item["title"]},
                         fix="只在剪映客户端正常获取；技能不绕过权益")
    if not item["md5"]:
        raise SkillError(
            "资源没有 md5，无法定位剪映缓存目录",
            code="RESOURCE_MD5_MISSING",
            details={"id": item["id"], "title": item["title"],
                     "panel": item["panel"]},
            fix="换一个资源；这类记录常见于数字人等特殊面板，不能保证剪映能加载。",
        )
    if item["cached"] and not force:
        return {
            "ref": ref, "id": item["id"], "title": item["title"],
            "panel": item["panel"], "applied": False, "already_cached": True,
            "cache_path": item["package_path"],
            "db_md5": item["md5"], "archive_md5": None,
        }
    connection = _connect(db_path)
    try:
        row = connection.execute(
            "select item_urls, sdk_extra from effect where id = ?",
            (item["id"],)).fetchone()
    finally:
        connection.close()
    if not row:
        raise SkillError("资源记录消失", code="RESOURCE_NOT_FOUND",
                         details={"id": item["id"]})
    urls = _parse_urls(row["item_urls"])
    if not urls:
        raise SkillError("资源没有下载地址", code="RESOURCE_URL_MISSING",
                         details={"id": item["id"], "title": item["title"]})
    now = time.time()
    usable = [url for url in urls
              if _expires(url) is None or _expires(url) > now]
    if not usable:
        raise SkillError("资源下载地址已过期", code="RESOURCE_URL_EXPIRED",
                         details={"id": item["id"], "title": item["title"]},
                         fix="在剪映里打开一次素材面板刷新资源；或换一个资源")
    target = _target_dir(cache_root, item["panel"], item["id"], item["md5"])
    dependencies = []
    try:
        sdk_extra = json.loads(row["sdk_extra"] or "{}")
    except (TypeError, ValueError):
        sdk_extra = {}
    for dependency in sdk_extra.get("depend_resource_list") or []:
        if isinstance(dependency, dict):
            dependencies.append({
                "type": dependency.get("type"),
                "resource_id": str(dependency.get("resource_id") or ""),
                "source": dependency.get("source"),
            })
    if not apply:
        return {
            "ref": ref, "id": item["id"], "title": item["title"],
            "panel": item["panel"], "applied": False, "already_cached": False,
            "target": str(target), "url_count": len(usable),
            "dependencies": dependencies,
            "note": "dry-run；加 --apply 才下载到本机缓存",
        }
    if target.exists() and not force:
        raise SkillError("资源包已存在", code="OUTPUT_EXISTS",
                         details={"path": str(target)},
                         fix="确认要覆盖时加 --force")
    handle, temp_name = tempfile.mkstemp(prefix=".jy-resource-", suffix=".zip")
    os.close(handle)
    archive = Path(temp_name)
    archive_md5 = None
    try:
        request = urllib.request.Request(usable[0],
                                         headers={"User-Agent": "Mozilla/5.0"})
        digest = hashlib.md5()
        total = 0
        with urllib.request.urlopen(request, timeout=timeout) as response, \
                open(archive, "wb") as sink:
            while True:
                chunk = response.read(1024 * 1024)
                if not chunk:
                    break
                total += len(chunk)
                if total > _MAX_DOWNLOAD_BYTES:
                    raise SkillError(
                        "资源包下载超过上限", code="PACKAGE_INVALID",
                        details={"limit": _MAX_DOWNLOAD_BYTES})
                digest.update(chunk)
                sink.write(chunk)
        size = total
        archive_md5 = digest.hexdigest()
        install_archive(archive, target, force=force)
    except urllib.error.HTTPError as exc:
        raise SkillError("资源下载被拒绝", code="RESOURCE_DOWNLOAD_FAILED",
                         details={"id": item["id"], "status": exc.code},
                         fix="URL 可能过期或资源已下架；在剪映里刷新资源后再试") from exc
    except urllib.error.URLError as exc:
        raise SkillError("资源下载网络失败", code="RESOURCE_DOWNLOAD_FAILED",
                         details={"id": item["id"], "reason": str(exc.reason)}) from exc
    finally:
        archive.unlink(missing_ok=True)
    result = {
        "ref": ref, "id": item["id"], "title": item["title"],
        "panel": item["panel"], "applied": True, "already_cached": False,
        "cache_path": str(target), "bytes": size,
        "db_md5": item["md5"], "archive_md5": archive_md5,
        "dependencies": dependencies,
    }
    if item["panel"] == "fonts":
        result["font_path"] = str(font_file(target))
    return result
