"""Make a draft visible on 剪映's home screen.

剪映 has no import command: the home list is ``root_meta_info.json`` under the
draft root. Adding an entry is a write to the user's app state, so this module
defaults to a dry run, backs up the original index, and never touches entries
it did not create.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import time
from pathlib import Path

from .errors import SkillError
from .draft import (MARKER, load_json, resolve_draft_info, uid,
                    _backup_stamp, _write_json, _assert_plain_tree, _is_link)
from .media import local_path

INDEX_NAME = "root_meta_info.json"
BACKUP_DIR = ".jianying-backups"# 38 keys observed in the live index of 剪映 11.6/11.8 (以 ENTRY_TEMPLATE 为准).
ENTRY_TEMPLATE = {
    "cloud_draft_cover": False,
    "cloud_draft_sync": False,
    "draft_cloud_last_action_download": False,
    "draft_cloud_purchase_info": "",
    "draft_cloud_template_id": "",
    "draft_cloud_tutorial_info": "",
    "draft_cloud_videocut_purchase_info": "",
    "draft_cover": "",
    "draft_fold_path": "",
    "draft_id": "",
    "draft_is_ai_shorts": False,
    "draft_is_cloud_temp_draft": False,
    "draft_is_infinite_canvas_draft": False,
    "draft_is_invisible": False,
    "draft_is_pippit_draft": False,
    "draft_is_web_article_video": False,
    "draft_json_file": "",
    "draft_name": "",
    "draft_new_version": "",
    "draft_root_path": "",
    "draft_timeline_materials_size": 0,
    "draft_type": "",
    "draft_web_article_video_enter_from": "",
    "pippit_avatar_url": "",
    "pippit_extra_info": "",
    "pippit_id": "",
    "pippit_user_name": "",
    "streaming_edit_draft_ready": True,
    "tm_draft_cloud_completed": "",
    "tm_draft_cloud_entry_id": -1,
    "tm_draft_cloud_modified": 0,
    "tm_draft_cloud_parent_entry_id": -1,
    "tm_draft_cloud_space_id": -1,
    "tm_draft_cloud_user_id": -1,
    "tm_draft_create": 0,
    "tm_draft_modified": 0,
    "tm_draft_removed": 0,
    "tm_duration": 0,
}

# Update must only touch fields this skill owns. The rest may contain cloud
# entry/space/user identifiers written by 剪映 and must survive a re-register.
ENTRY_OWNED = {
    "draft_fold_path", "draft_json_file", "draft_name", "draft_id",
    "draft_root_path", "draft_cover", "draft_new_version", "draft_type",
    "draft_is_invisible", "streaming_edit_draft_ready", "tm_draft_create",
    "tm_draft_modified", "tm_duration", "draft_timeline_materials_size",
}


def _root_index(explicit=None):
    from .env import find_draft_root

    if explicit:
        root = local_path(explicit, field="草稿根目录").resolve()
    else:
        root = find_draft_root()
    if not root:
        raise SkillError(
            "找不到剪映草稿根目录",
            code="DRAFT_ROOT_NOT_FOUND",
            fix="用 --draft-root 指定包含 root_meta_info.json 的目录。",
        )
    root = local_path(root, field="草稿根目录").resolve()
    index = root / INDEX_NAME
    if _is_link(index):
        raise SkillError(
            "root_meta_info.json 是符号链接或 junction，拒绝写入",
            code="UNSAFE_PATH",
            details={"path": str(index)},
        )
    if not index.is_file():
        raise SkillError(
            "草稿根目录缺少 root_meta_info.json",
            code="INDEX_NOT_FOUND",
            details={"root": str(root)},
            fix="确认路径是剪映的 Projects/com.lveditor.draft 目录；或先在剪映里新建一个草稿。",
        )
    return root, index


def _entry(draft_dir, index_path, root, name=None):
    resolved = resolve_draft_info(draft_dir)
    info_path = resolved["info_path"]
    if not info_path:
        raise SkillError("不是草稿目录", code="DRAFT_NOT_FOUND",
                         details={"draft": str(draft_dir)})
    try:
        document = json.loads(info_path.read_text("utf-8-sig"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise SkillError(
            "草稿是加密的，无法登记",
            code="DRAFT_ENCRYPTED",
            details={"info": str(info_path)},
            fix="只登记本技能生成的明文草稿。",
        ) from exc
    folder = resolved["draft_dir"]
    meta_path = folder / "draft_meta_info.json"
    if not meta_path.is_file() or _is_link(meta_path):
        raise SkillError(
            "草稿缺少可读的 draft_meta_info.json，不能登记到首页",
            code="DRAFT_META_MISSING",
            details={"draft": str(folder), "meta": str(meta_path)},
            fix="先用剪映打开并保存一次草稿，让它生成明文 meta；不要手工伪造目录条目。",
        )
    try:
        meta = load_json(meta_path)
    except SkillError as exc:
        raise SkillError(
            "draft_meta_info.json 不可读或不是明文 JSON",
            code="DRAFT_META_INVALID",
            details={"meta": str(meta_path), "reason": exc.message},
        ) from exc
    if meta.get("draft_is_invisible") is True:
        raise SkillError(
            "草稿在 meta 中被标记为不可见，拒绝登记",
            code="DRAFT_INVISIBLE",
            details={"meta": str(meta_path)},
        )
    try:
        meta_duration = int(meta.get("tm_duration") or 0)
    except (TypeError, ValueError):
        meta_duration = 0
    if meta_duration <= 0:
        raise SkillError(
            "draft_meta_info.json 的 tm_duration 不是正数，拒绝登记",
            code="DRAFT_META_INVALID",
            details={"meta": str(meta_path), "tm_duration": meta.get("tm_duration")},
        )
    meta_id = str(meta.get("draft_id") or "").strip()
    document_id = str(document.get("id") or "").strip()
    if meta_id and document_id and meta_id != document_id:
        raise SkillError(
            "draft_info.json 与 draft_meta_info.json 的 draft_id 不一致，拒绝登记",
            code="DRAFT_META_MISMATCH",
            details={"document_id": document_id, "meta_id": meta_id,
                     "meta": str(meta_path)},
        )
    draft_id = document_id or meta_id
    if not draft_id:
        raise SkillError(
            "草稿没有 draft_id，拒绝写入首页索引",
            code="DRAFT_ID_MISSING",
            details={"draft": str(folder)},
            fix="先在剪映里打开并保存一次，或重新用 build 生成草稿。",
        )
    entry = dict(ENTRY_TEMPLATE)
    entry.update({
        "draft_fold_path": str(folder),
        "draft_json_file": str(info_path),
        "draft_name": str(name or document.get("name") or meta.get("draft_name")
                          or folder.name),
        "draft_id": draft_id,
        "draft_root_path": str(root),
        "draft_cover": str(folder / "draft_cover.jpg")
        if (folder / "draft_cover.jpg").is_file() else "",
        "draft_new_version": str(document.get("new_version") or ""),
        "draft_type": "video",
        "draft_is_invisible": False,
        "streaming_edit_draft_ready": True,
        "tm_draft_create": _micros(document.get("create_time"), folder.stat().st_mtime_ns),
        "tm_draft_modified": _micros(document.get("update_time"), folder.stat().st_mtime_ns),
        "tm_duration": meta_duration,
        "draft_timeline_materials_size": _materials_bytes(document),
    })
    # draft_id 已在 draft_info 中；索引条目不持久化该字段。
    entry["id_persisted"] = True
    return entry


def _micros(value, fallback_ns):
    try:
        number = int(value)
    except (TypeError, ValueError):
        return int(fallback_ns // 1000)
    # 11.x stores seconds in draft_info; anything already larger is micros.
    return number if number > 10**12 else number * 1_000_000


def _materials_bytes(document):
    total = 0
    for bucket in ("videos", "audios"):
        for item in (document.get("materials") or {}).get(bucket) or []:
            try:
                path = local_path(item.get("path") or "", field="素材路径")
                if path.is_file():
                    total += path.stat().st_size
            except (OSError, SkillError):
                continue
    return total


def _load_index(index_path):
    raw = index_path.read_bytes()
    try:
        data = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise SkillError("root_meta_info.json 不是合法 JSON", code="INDEX_INVALID",
                         details={"path": str(index_path)}) from exc
    if not isinstance(data, dict) or not isinstance(data.get("all_draft_store"), list):
        raise SkillError("root_meta_info.json 缺少 all_draft_store 数组",
                         code="INDEX_INVALID", details={"path": str(index_path)})
    return data, raw


def _next_ids(index, entries):
    current = index.get("draft_ids", 0)
    if isinstance(current, bool) or not isinstance(current, int):
        raise SkillError("draft_ids 不是整数，拒绝猜写", code="INDEX_UNSUPPORTED",
                         details={"draft_ids": current})
    return max(current, len(entries)) + 1


def _merge_index(index, entry):
    """Merge one entry into an index snapshot without dropping other writers' data."""
    entries = list(index.get("all_draft_store") or [])
    stored = {key: value for key, value in entry.items() if key != "id_persisted"}
    matches = [i for i, item in enumerate(entries)
               if str(item.get("draft_fold_path") or "") == entry["draft_fold_path"]
               or str(item.get("draft_id") or "") == entry["draft_id"]]
    if matches:
        # 路径或 id 已存在时更新原条目，不新增重复项。
        # 索引 draft_id 必须与草稿当前 id 一致（SKILL.md）：build --force 重建后
        # id 会变化，这里保留 entry 里的真实 id，而不是回填索引旧值造成脱节。
        updated = [dict(item) for item in entries]
        payload = {key: value for key, value in stored.items() if key in ENTRY_OWNED}
        if not payload.get("draft_cover"):
            payload.pop("draft_cover", None)
        for position in matches:
            merged = dict(entries[position])
            merged.update(payload)
            merged.pop("id_persisted", None)
            updated[position] = merged
        action = "update"
    else:
        updated = [stored] + entries
        action = "add"
    new_index = dict(index)
    new_index["all_draft_store"] = updated
    if action == "add":
        new_index["draft_ids"] = _next_ids(index, entries)
    return new_index, len(entries), len(updated), action, stored


class _IndexLock:
    """Advisory lock for this skill's writers; CAS still guards external writers."""

    def __init__(self, root):
        self.path = root / ".root_meta_info.lock"
        self.token = f"{os.getpid()}:{time.time_ns()}"
        self.held = False

    def __enter__(self):
        for attempt in range(2):
            try:
                fd = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            except FileExistsError:
                try:
                    age = time.time() - self.path.stat().st_mtime
                except OSError:
                    age = 0
                if attempt == 0 and age > 120:
                    try:
                        self.path.unlink()
                    except OSError:
                        pass
                    continue
                raise SkillError(
                    "另一个进程正在写剪映首页索引，稍后重试",
                    code="INDEX_BUSY",
                    details={"lock": str(self.path)},
                    retriable=True,
                ) from None
            try:
                os.write(fd, self.token.encode("ascii"))
            finally:
                os.close(fd)
            self.held = True
            return self
        raise SkillError("无法获得首页索引写锁", code="INDEX_BUSY",
                         details={"lock": str(self.path)}, retriable=True)

    def __exit__(self, *_exc):
        if not self.held:
            return
        try:
            if self.path.read_text("ascii") == self.token:
                self.path.unlink()
        except OSError:
            pass
        self.held = False


def _result(index_path, root, index, entry, *, before, after, action,
            applied, backup=None, verified=False, dry_run=False):
    result = {
        "action": action,
        "index": str(index_path),
        "draft": entry["draft_fold_path"],
        "name": entry["draft_name"],
        "draft_id": entry["draft_id"],
        "id_persisted": entry.get("id_persisted", True),
        "before": before,
        "after": after,
        "draft_ids": {"before": index.get("draft_ids")},
        "applied": applied,
        "verified": verified,
    }
    if Path(entry["draft_fold_path"]).parent != root:
        result["warning"] = (
            "草稿目录不在草稿根下；剪映首页可能不显示该条目。"
            "用 publish 复制进草稿根，或把草稿建在草稿根内。"
        )
    if backup:
        result["backup"] = str(backup)
    if dry_run:
        result["dry_run"] = True
    return result


def _ensure_editor_closed():
    """写索引前确认剪映没在运行。

    剪映运行时把首页索引放在内存里，退出时会覆盖磁盘；此时登记会被静默冲掉。
    CAS 只防写前并发，防不了这种事后覆盖，所以这里做进程级守卫。
    返回 ``closed`` / ``unknown``：tasklist 不可用或异常时无法确认，交调用方标注。
    """
    try:
        proc = subprocess.run(
            ["tasklist", "/FI", "IMAGENAME eq JianyingPro.exe", "/NH"],
            capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.SubprocessError):
        return "unknown"
    if "JianyingPro.exe" in (proc.stdout or ""):
        raise SkillError(
            "剪映正在运行：退出剪映后再登记，否则首页索引会被其内存状态覆盖",
            code="EDITOR_RUNNING",
            fix="先保存工作并退出剪映，再重试 register/publish --apply。",
            retriable=True,
        )
    return "closed" if proc.returncode == 0 else "unknown"


def register(draft_dir, *, apply=False, draft_root=None, name=None):
    root, index_path = _root_index(draft_root)

    if not apply:
        index, _raw = _load_index(index_path)
        entry = _entry(draft_dir, index_path, root, name=name)
        new_index, before, after, action, stored = _merge_index(index, entry)
        result = _result(index_path, root, index, stored, before=before, after=after,
                         action=action, applied=False, dry_run=True)
        result["draft_ids"]["after"] = new_index.get("draft_ids")
        return result

    editor = _ensure_editor_closed()
    with _IndexLock(root):
        for attempt in range(2):
            index, raw = _load_index(index_path)
            entry = _entry(draft_dir, index_path, root, name=name)
            new_index, before, after, action, stored = _merge_index(index, entry)
            try:
                current = index_path.read_bytes()
            except OSError as exc:
                raise SkillError("索引读取失败", code="INDEX_INVALID",
                                 details={"index": str(index_path),
                                          "reason": str(exc)}) from exc
            if current != raw:
                if attempt == 0:
                    continue
                raise SkillError(
                    "剪映首页索引在写入前被其他进程修改，已拒绝覆盖",
                    code="INDEX_CONFLICT",
                    details={"index": str(index_path)},
                    fix="退出剪映后重试；不要并发登记或手改索引。",
                )

            backup_dir = root / BACKUP_DIR
            backup = None
            temp = None
            try:
                backup_dir.mkdir(parents=True, exist_ok=True)
                backup = backup_dir / f"root_meta_info.{_backup_stamp()}.json"
                backup.write_bytes(raw)
                temp = index_path.with_name(
                    f".root_meta_info.{os.getpid()}.{uid()}.tmp")
                temp.write_text(
                    json.dumps(new_index, ensure_ascii=False,
                               separators=(",", ":")), "utf-8")
                os.replace(temp, index_path)
            except OSError as exc:
                if backup and backup.exists():
                    # 保持现场：备份可人工恢复，错误里给出路径
                    details = {"index": str(index_path), "backup": str(backup),
                               "reason": str(exc)}
                else:
                    details = {"index": str(index_path), "reason": str(exc)}
                raise SkillError("索引写入失败", code="OUTPUT_WRITE_FAILED",
                                 details=details) from exc
            finally:
                if temp is not None and temp.exists():
                    try:
                        temp.unlink()
                    except OSError:
                        pass

            after_index, _ = _load_index(index_path)
            if not any(str(item.get("draft_id")) == stored["draft_id"]
                       for item in after_index.get("all_draft_store") or []):
                raise SkillError(
                    "写入后回读不到登记条目",
                    code="INDEX_VERIFY_FAILED",
                    details={"index": str(index_path), "backup": str(backup)},
                )
            result = _result(index_path, root, index, stored, before=before,
                             after=after, action=action, applied=True,
                             backup=backup, verified=True)
            result["draft_ids"]["after"] = new_index.get("draft_ids")
            result["editor_check"] = editor
            return result
    raise SkillError("索引写入重试耗尽", code="INDEX_CONFLICT",
                     details={"index": str(index_path)}, retriable=True)


def _safe_name(value):
    cleaned = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", str(value)).strip(" .")
    return cleaned or "jianying-draft"


def publish(draft_dir, *, apply=False, draft_root=None, name=None):
    """Copy a draft into the draft root and register it (dry run by default)."""
    root, index_path = _root_index(draft_root)
    resolved = resolve_draft_info(draft_dir)
    source = resolved["draft_dir"]
    if not resolved["info_path"]:
        raise SkillError("不是草稿目录", code="DRAFT_NOT_FOUND")
    try:
        document = json.loads(resolved["info_path"].read_text("utf-8-sig"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise SkillError("草稿是加密的，无法复制/登记", code="DRAFT_ENCRYPTED") from exc
    source_draft_id = str(document.get("id") or "").strip()

    source_entry = _entry(source, index_path, root, name=name)
    source_entry["draft_id"] = source_entry["draft_id"] or source_draft_id
    existing = list(_load_index(index_path)[0].get("all_draft_store") or [])
    already = [item for item in existing
               if str(item.get("draft_id") or "") == source_entry["draft_id"]]
    if not already:
        for item in existing:
            marker = Path(str(item.get("draft_fold_path") or "")) / MARKER
            if not marker.is_file():
                continue
            try:
                marker_data = json.loads(marker.read_text("utf-8"))
            except (OSError, UnicodeDecodeError, json.JSONDecodeError):
                continue
            if str(marker_data.get("source_draft_id") or "") == source_entry["draft_id"]:
                already = [item]
                break
    if already:
        return {
            "action": "already-registered",
            "reason": "这个源草稿已经复制并登记过，未创建第二份副本",
            "index": str(index_path),
            "target": str(already[0].get("draft_fold_path") or ""),
            "draft_id": source_entry["draft_id"],
            "applied": False,
            "dry_run": not apply,
        }

    if source.parent == root:
        if not apply:
            return {"action": "register-only", "target": str(source),
                    "dry_run": True, "entry": source_entry}
        return register(source, apply=True, draft_root=str(root), name=name)

    base = _safe_name(name or document.get("name") or source.name)
    target = root / base
    suffix = 2
    while target.exists():
        target = root / f"{base}-{suffix}"
        suffix += 1

    # 复制之前先查索引冲突，避免半成品目录落进草稿根
    existing = list(_load_index(index_path)[0].get("all_draft_store") or [])
    if any(str(item.get("draft_fold_path")) == str(target) for item in existing):
        raise SkillError("列表里已存在同路径条目，拒绝复制", code="INDEX_CONFLICT",
                         details={"target": str(target)})

    if not apply:
        return {"action": "copy+register", "source": str(source),
                "target": str(target), "dry_run": True}

    editor = _ensure_editor_closed()
    tmp = root / f".tmp-{uid()}"
    info_relative = resolved["info_path"].relative_to(source)
    try:
        _assert_plain_tree(source)
        shutil.copytree(source, tmp, symlinks=True)
        new_id = uid()
        document["id"] = new_id
        document["name"] = target.name
        document["path"] = str(target)
        document["update_time"] = int(time.time())
        (tmp / info_relative).write_text(
            json.dumps(document, ensure_ascii=False, separators=(",", ":")), "utf-8")
        meta_path = tmp / "draft_meta_info.json"
        if meta_path.is_file():
            meta = load_json(meta_path)
            meta.update(draft_id=new_id, draft_name=target.name,
                        draft_fold_path=str(target), draft_root_path=str(root),
                        draft_removable_storage_device=target.drive or "")
            meta_path.write_text(json.dumps(meta, ensure_ascii=False,
                                            separators=(",", ":")), "utf-8")
        marker = tmp / MARKER
        marker_data = {}
        if marker.is_file():
            try:
                marker_data = load_json(marker)
            except SkillError:
                marker_data = {}
        marker_data.update({
            "schema": "jianying-skill/v1",
            "source_draft_id": source_draft_id,
            "source_path": str(source),
            "registered_name": target.name,
        })
        _write_json(marker, marker_data)
        os.replace(tmp, target)
    except SkillError:
        if tmp.exists():
            shutil.rmtree(tmp, ignore_errors=True)
        raise
    except (OSError, shutil.Error) as exc:
        if tmp.exists():
            shutil.rmtree(tmp, ignore_errors=True)
        raise SkillError("复制草稿到草稿根失败", code="COPY_FAILED",
                         details={"source": str(source), "target": str(target),
                                  "reason": str(exc)}) from exc

    try:
        result = register(target, apply=True, draft_root=str(root), name=target.name)
    except Exception:
        # 复制已 os.replace 提交；登记失败时回滚已复制目录，避免草稿根滞留孤儿。
        shutil.rmtree(target, ignore_errors=True)
        raise
    result.update({"action": "copied+registered", "source": str(source),
                   "target": str(target)})
    result["editor_check"] = result.get("editor_check") or editor
    return result
