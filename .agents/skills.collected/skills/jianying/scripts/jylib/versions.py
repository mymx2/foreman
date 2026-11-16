"""Draft version history: snapshot, list, diff, and restore.

A 剪映 draft is already the editable source (the PSD-equivalent).  This module
keeps a monotonic history next to it so a delivery can be iterated instead of
being a single throw-away MP4:

    <draft>/.jianying-versions/versions.json
    <draft>/.jianying-versions/v001/draft_info.json
    <draft>/.jianying-versions/v001/source-plan.json
    <draft>/.jianying-versions/v002/source-ops.json

Every version stores the full plaintext JSON (so restore never depends on a
chain of patches) plus the plan/ops that produced it (so an agent can fork or
re-apply the change).  Snapshots are local files; no token or credential is
read or written.
"""

from __future__ import annotations

import copy
import hashlib
import json
import os
import re
import shutil
import subprocess
import time
import uuid
from contextlib import contextmanager
from pathlib import Path

from .errors import SkillError

VERSION_DIR = ".jianying-versions"
MANIFEST_NAME = "versions.json"
SCHEMA = "jianying-versions/v1"
MARKER = ".jianying-skill.json"
_VERSION_RE = re.compile(r"^v\d{3,}$")


def _now():
    return int(time.time())


def _sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _is_link(path):
    """Symlink/junction check shared with draft.py (lazy: draft imports us)."""
    from .draft import _is_link as draft_is_link
    return draft_is_link(path)


def _safe_local(value, field="草稿目录"):
    """Reject UNC/URL paths, then links/junctions, then resolve.

    Version trees are written next to the draft, so every entry point must obey
    the same hard rule as the rest of the skill: no SMB/UNC target (Windows
    would send NTLM before any validation) and no symlink/junction inside a
    third-party draft.
    """
    from . import media as media_mod

    path = media_mod.local_path(value, field=field)
    if _is_link(path):
        raise SkillError(
            f"{field}是符号链接或 junction，拒绝读写",
            code="UNSAFE_PATH",
            details={"field": field, "path": str(path)},
            fix="把草稿复制到本地普通目录，或先移除链接后重试。",
        )
    return path.resolve()


def _root_info(draft_dir):
    """Return ``(draft root, authoritative draft_info.json)``.

    The version history always lives in ``<draft>/.jianying-versions``; only the
    info file moves. 剪映 11.x keeps it at ``<draft>/Timelines/<id>/draft_info.json``
    and records the active timeline in ``Timelines/project.json``, so the lookup
    is delegated to ``draft.resolve_draft_info`` (imported lazily: draft.py
    imports this module at load time).
    """
    from .draft import resolve_draft_info

    root = _safe_local(draft_dir, field="草稿目录")
    history = root / VERSION_DIR
    if _is_link(history):
        raise SkillError(
            "版本历史目录是符号链接或 junction，拒绝读写",
            code="UNSAFE_PATH",
            details={"path": str(history)},
            fix="移除链接，或把草稿复制到本地普通目录后重试。")
    info = resolve_draft_info(root).get("info_path")
    if info is not None:
        return root, Path(info)
    legacy = root / "draft_content.json"
    if _is_link(legacy):
        raise SkillError(
            "draft_content.json 是符号链接，拒绝读取草稿目录之外的文件",
            code="UNSAFE_PATH",
            details={"path": str(legacy)},
            fix="把草稿复制到本地普通目录，或移除符号链接后重试。",
        )
    if legacy.is_file():
        return root, legacy
    raise SkillError(
        "不是草稿目录：找不到 draft_info.json",
        code="DRAFT_NOT_FOUND",
        details={"draft": str(root),
                 "checked": [str(root / "draft_info.json"),
                             str(root / "Timelines" / "<id>" / "draft_info.json"),
                             str(legacy)]})


def _history_dir(root):
    return root / VERSION_DIR


def _manifest_path(root):
    return _history_dir(root) / MANIFEST_NAME


def _read_lock_owner(lock):
    try:
        data = json.loads((lock / "owner.json").read_text("utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def _write_lock_owner(lock, token):
    payload = {"pid": os.getpid(), "token": token, "created": _now()}
    temp = lock / "owner.tmp"
    try:
        temp.write_text(json.dumps(payload, ensure_ascii=False), "utf-8")
        os.replace(temp, lock / "owner.json")
    except OSError as exc:
        shutil.rmtree(lock, ignore_errors=True)
        raise SkillError("版本历史锁写入失败", code="VERSION_WRITE_FAILED",
                         details={"lock": str(lock), "reason": str(exc)}) from exc


def _pid_alive(pid):
    try:
        pid = int(pid)
    except (TypeError, ValueError):
        return None
    if pid <= 0:
        return None
    if os.name == "nt":
        try:
            proc = subprocess.run(
                ["tasklist", "/FI", f"PID eq {pid}", "/NH"],
                capture_output=True, text=True, timeout=5)
        except (OSError, subprocess.SubprocessError):
            return None
        if proc.returncode != 0:
            return None
        return str(pid) in (proc.stdout or "")
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return None
    return True


def _remove_stale_lock(lock, owner):
    """只清理能确认属主已退出（或超龄且无属主文件）的锁。"""
    try:
        age = time.time() - lock.stat().st_mtime
    except OSError:
        return False
    if owner is None:
        if age <= 60:
            return False
    elif _pid_alive(owner.get("pid")) is not False:
        return False
    current = _read_lock_owner(lock)
    if owner is not None and (current is None
                              or current.get("token") != owner.get("token")):
        return False
    tombstone = lock.with_name(f"{lock.name}.stale-{uuid.uuid4().hex[:8]}")
    try:
        os.replace(lock, tombstone)
    except OSError:
        return False
    if owner is not None:
        moved = _read_lock_owner(tombstone)
        if moved is None or moved.get("token") != owner.get("token"):
            # 竞态中搬走了别人刚建的新锁：原样放回，不清理。
            try:
                os.replace(tombstone, lock)
            except OSError:
                pass
            return False
    shutil.rmtree(tombstone, ignore_errors=True)
    return True


@contextmanager
def _history_lock(root):
    """Cross-process lock (atomic mkdir) for read-modify-write of versions.json."""
    lock = _history_dir(root) / ".lock"
    try:
        lock.parent.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise SkillError("版本历史目录创建失败", code="VERSION_WRITE_FAILED",
                         details={"path": str(lock.parent), "reason": str(exc)}) from exc
    token = uuid.uuid4().hex
    deadline = time.time() + 10.0
    while True:
        try:
            lock.mkdir()
            _write_lock_owner(lock, token)
            break
        except FileExistsError:
            owner = _read_lock_owner(lock)
            try:
                age = time.time() - lock.stat().st_mtime
            except OSError:
                age = 0
            if age > 30 and _remove_stale_lock(lock, owner):
                continue
            if time.time() >= deadline:
                raise SkillError(
                    "版本历史被其他进程占用，等待锁超时",
                    code="VERSION_WRITE_FAILED",
                    details={"lock": str(lock)},
                    fix="确认没有另一个进程正在写版本历史；属主进程已退出仍残留时"
                        "删除遗留的 .lock 目录后重试。")
            time.sleep(0.05)
        except OSError as exc:
            raise SkillError("版本历史锁创建失败", code="VERSION_WRITE_FAILED",
                             details={"lock": str(lock), "reason": str(exc)}) from exc
    try:
        yield
    finally:
        owner = _read_lock_owner(lock)
        if owner is not None and owner.get("token") == token:
            shutil.rmtree(lock, ignore_errors=True)


def _atomic_write_bytes(path, data):
    path = Path(path)
    temp = path.with_name(f".{path.name}.{uuid.uuid4().hex[:6]}.tmp")
    try:
        temp.write_bytes(data)
        temp.replace(path)
    except OSError as exc:
        raise SkillError("版本文件写入失败", code="VERSION_WRITE_FAILED",
                         details={"path": str(path), "reason": str(exc)}) from exc
    finally:
        try:
            temp.unlink(missing_ok=True)
        except OSError:
            pass


def _atomic_write_text(path, text):
    _atomic_write_bytes(path, text.encode("utf-8"))


def _read_manifest(root, required=False):
    path = _manifest_path(root)
    if not path.is_file():
        if required:
            raise SkillError("草稿没有版本历史", code="VERSION_NOT_FOUND",
                             details={"path": str(path)},
                             fix="先运行 `jy.py version snapshot <draft> --label init` 建立基线。")
        return None
    try:
        data = json.loads(path.read_text("utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise SkillError("版本历史损坏，拒绝继续", code="VERSION_CORRUPTED",
                         details={"path": str(path), "reason": str(exc)}) from exc
    if not isinstance(data, dict) or not isinstance(data.get("versions"), list):
        raise SkillError("版本历史格式不正确", code="VERSION_CORRUPTED",
                         details={"path": str(path)})
    return data


def _write_manifest(root, manifest):
    try:
        _history_dir(root).mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise SkillError("版本历史写入失败", code="VERSION_WRITE_FAILED",
                         details={"path": str(_manifest_path(root)),
                                  "reason": str(exc)}) from exc
    target = _manifest_path(root)
    _atomic_write_text(
        target, json.dumps(manifest, ensure_ascii=False, indent=2))


def _update_marker(root, manifest):
    marker = root / MARKER
    try:
        existing = {}
        if marker.is_file():
            existing = json.loads(marker.read_text("utf-8"))
            if not isinstance(existing, dict):
                existing = {}
        existing.update({
            "schema": existing.get("schema") or "jianying-skill/v1",
            "version_id": manifest.get("current"),
            "version_count": len(manifest.get("versions") or []),
            "history": f"{VERSION_DIR}/{MANIFEST_NAME}",
        })
        _atomic_write_text(
            marker, json.dumps(existing, ensure_ascii=False, indent=2))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise SkillError("草稿标记文件写入失败", code="VERSION_WRITE_FAILED",
                         details={"path": str(marker), "reason": str(exc)}) from exc


def _next_id(manifest, root):
    used = {item.get("id") for item in manifest.get("versions") or []}
    number = 1
    while (f"v{number:03d}" in used
           or (_history_dir(root) / f"v{number:03d}").exists()):
        number += 1
    return f"v{number:03d}"


def _summary(info_bytes):
    try:
        document = json.loads(info_bytes.decode("utf-8-sig"))
    except (UnicodeDecodeError, json.JSONDecodeError, AttributeError):
        return {"duration": None, "tracks": None, "segments": None,
                "materials": None, "texts": None}
    tracks = document.get("tracks") or []
    return {
        "duration": round(float(document.get("duration") or 0) / 1_000_000, 3),
        "tracks": len(tracks),
        "segments": sum(len(track.get("segments") or []) for track in tracks),
        "materials": sum(len(value) for value in (document.get("materials") or {}).values()
                        if isinstance(value, list)),
        "texts": len((document.get("materials") or {}).get("texts") or []),
    }


def _snapshot_layout(root):
    """快照来源布局：单时间线、多时间线（含主时间线 id），或旧版裸文件。

    ``draft.resolve_draft_info`` 会反向导入本模块，只能在函数内延迟导入。
    布局迁移（多时间线 <-> 单时间线、换主时间线）不改结构字段，若版本链不记
    布局，``diff`` 只会报结构变化，看不出是搬家。
    """
    from .draft import resolve_draft_info

    resolved = resolve_draft_info(root)
    if resolved.get("layout") == "missing" or resolved.get("info_path") is None:
        # 只有旧版 draft_content.json 时 resolve 返回 missing：没有可判定的布局。
        return {"layout": "legacy-content", "timeline_id": None}
    return {"layout": resolved.get("layout"),
            "timeline_id": resolved.get("timeline_id")}


_SEGMENT_DIFF_FIELDS = (
    "material_id", "target_timerange", "source_timerange", "speed", "volume",
    "clip", "visible", "render_index", "track_render_index", "reverse",
    "common_keyframes", "caption_info", "sound_channel_mapping",
)


def _material_index(document):
    index = {}
    for bucket, items in (document.get("materials") or {}).items():
        if not isinstance(items, list):
            continue
        for item in items:
            if isinstance(item, dict) and item.get("id"):
                index[item["id"]] = {"bucket": bucket, "value": item}
    return index


def _segment_label(segment, index):
    material = index.get(segment.get("material_id")) or {}
    value = material.get("value") or {}
    bucket = material.get("bucket") or "material"
    label = ""
    if bucket == "texts":
        try:
            label = str(json.loads(value.get("content") or "{}").get("text") or "")
        except (TypeError, ValueError):
            label = ""
    if not label:
        label = str(value.get("material_name") or value.get("name") or "")
    if not label:
        path = str(value.get("path") or "")
        if path:
            label = Path(path).name
    if not label:
        label = str(value.get("resource_id") or segment.get("material_id") or "")
    return f"{bucket}:{label}"[:120]


def _segment_fingerprints(document):
    index = _material_index(document)
    result = {}
    for track in document.get("tracks") or []:
        for segment in track.get("segments") or []:
            segment_id = segment.get("id")
            if not segment_id:
                continue
            refs = []
            for ref in [segment.get("material_id"),
                        *(segment.get("extra_material_refs") or [])]:
                if ref and ref in index:
                    refs.append(index[ref])
            payload = {
                "segment": {key: segment.get(key) for key in _SEGMENT_DIFF_FIELDS},
                "materials": refs,
            }
            encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True,
                                 separators=(",", ":"))
            result[segment_id] = {
                "digest": hashlib.sha256(encoded.encode("utf-8")).hexdigest(),
                "label": _segment_label(segment, index),
            }
    return result


def _input_entry(root, raw):
    text = str(raw or "").strip()
    if not text:
        return None
    if text.startswith(("http://", "https://", "file:", "\\\\", "//")):
        return {"path": text, "exists": False, "kind": "remote"}
    path = Path(text).expanduser()
    if not path.is_absolute():
        path = root / path
    try:
        path = path.resolve()
    except OSError:
        pass
    entry = {"path": str(path)}
    try:
        if path.is_file():
            stat = path.stat()
            entry.update({"exists": True, "kind": "file",
                          "size": stat.st_size, "mtime_ns": stat.st_mtime_ns})
            if stat.st_size <= 20 * 1024 * 1024:
                entry["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
        elif path.is_dir():
            entry.update({"exists": True, "kind": "dir"})
        else:
            entry["exists"] = False
    except OSError as exc:
        entry["exists"] = False
        entry["error"] = str(exc)
    return entry


def _collect_inputs(root, info_bytes, meta_bytes):
    try:
        document = json.loads(info_bytes.decode("utf-8-sig"))
    except (UnicodeDecodeError, json.JSONDecodeError, AttributeError):
        return []
    raw_paths = []

    def walk(value):
        if isinstance(value, dict):
            for key in ("path", "font_path", "mask_video_path", "matting_path"):
                if isinstance(value.get(key), str):
                    raw_paths.append(value[key])
            for child in value.values():
                walk(child)
        elif isinstance(value, list):
            for child in value:
                walk(child)

    walk(document.get("materials") or {})
    if meta_bytes:
        try:
            meta = json.loads(meta_bytes.decode("utf-8-sig"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            meta = {}
        cover = meta.get("draft_cover") if isinstance(meta, dict) else None
        if isinstance(cover, str):
            raw_paths.append(cover)
    result = []
    seen = set()
    try:
        resolved_root = root.resolve()
    except OSError:
        resolved_root = root
    for raw in raw_paths:
        entry = _input_entry(root, raw)
        if not entry or entry["path"] in seen:
            continue
        try:
            if Path(entry["path"]).is_relative_to(resolved_root):
                # 草稿目录内部的封面/相对素材不是外部依赖；快照不复制它们，
                # 记暂存绝对路径会在目录改名后悬空。
                continue
        except OSError:
            pass
        seen.add(entry["path"])
        result.append(entry)
    return sorted(result, key=lambda item: item["path"])


def _snapshot_bytes(root, manifest, info_bytes, meta_bytes, *, kind, label,
                    parent=None, plan_path=None, ops_path=None, note=None,
                    artifacts=None):
    version_id = _next_id(manifest, root)
    # 先取布局再建目录：resolve 报错时不留半成品版本目录。
    layout = _snapshot_layout(root)
    folder = _history_dir(root) / version_id
    try:
        folder.mkdir(parents=True, exist_ok=False)
        (folder / "draft_info.json").write_bytes(info_bytes)
        if meta_bytes is not None:
            (folder / "draft_meta_info.json").write_bytes(meta_bytes)
        plan_rel = None
        if plan_path and Path(plan_path).is_file():
            shutil.copy2(Path(plan_path), folder / "source-plan.json")
            plan_rel = f"{VERSION_DIR}/{version_id}/source-plan.json"
        ops_rel = None
        if ops_path and Path(ops_path).is_file():
            shutil.copy2(Path(ops_path), folder / "source-ops.json")
            ops_rel = f"{VERSION_DIR}/{version_id}/source-ops.json"
        artifact_meta = []
        for index, artifact in enumerate(artifacts or [], 1):
            source = Path(artifact)
            if not source.is_file():
                continue
            name = f"artifact-{index:02d}{source.suffix.lower() or '.bin'}"
            shutil.copy2(source, folder / name)
            artifact_meta.append({
                "name": name,
                "source": str(source),
                "sha256": _sha256(source),
            })
    except OSError as exc:
        shutil.rmtree(folder, ignore_errors=True)
        raise SkillError("版本快照写入失败", code="VERSION_WRITE_FAILED",
                         details={"version": version_id, "path": str(folder),
                                  "reason": str(exc)}) from exc
    summary = _summary(info_bytes)
    item = {
        "id": version_id,
        "parent": parent,
        "kind": kind,
        "label": str(label or kind),
        "note": str(note or ""),
        "created": _now(),
        "draft_sha256": hashlib.sha256(info_bytes).hexdigest(),
        "snapshot": f"{VERSION_DIR}/{version_id}/draft_info.json",
        "meta_snapshot": (f"{VERSION_DIR}/{version_id}/draft_meta_info.json"
                          if meta_bytes is not None else None),
        "layout": layout["layout"],
        "timeline_id": layout["timeline_id"],
        "plan": plan_rel,
        "ops": ops_rel,
        "artifacts": artifact_meta,
        "inputs": _collect_inputs(root, info_bytes, meta_bytes),
        "exports": [],
        **summary,
    }
    manifest.setdefault("versions", []).append(item)
    manifest["current"] = version_id
    # 顶层跟着最新快照走，旧清单没有这两个字段时读取端按缺省处理。
    manifest["layout"] = item["layout"]
    manifest["timeline_id"] = item["timeline_id"]
    _write_manifest(root, manifest)
    _update_marker(root, manifest)
    return item


def _new_manifest(root, info_bytes):
    try:
        draft_id = json.loads(info_bytes.decode("utf-8-sig")).get("id")
    except (UnicodeDecodeError, json.JSONDecodeError):
        draft_id = None
    return {
        "schema": SCHEMA,
        "draft_id": draft_id,
        "current": None,
        "versions": [],
    }


def record_initial(draft_dir, info_path=None, meta_path=None, plan_path=None,
                   label="build", note=None, kind="build"):
    """Create v001 for a freshly built draft."""
    root, info = _root_info(draft_dir) if info_path is None else (
        _safe_local(draft_dir, field="草稿目录"), Path(info_path))
    info_bytes = info.read_bytes()
    meta_bytes = Path(meta_path).read_bytes() if meta_path and Path(meta_path).is_file() else None
    with _history_lock(root):
        manifest = _read_manifest(root)
        if manifest is None:
            manifest = _new_manifest(root, info_bytes)
        return _snapshot_bytes(root, manifest, info_bytes, meta_bytes,
                               kind=kind, label=label, parent=None,
                               plan_path=plan_path, note=note)


def record_patch(draft_dir, info_path, ops_path, *, label="patch", note=None,
                 baseline_info=None, baseline_meta=None, artifacts=None):
    """Append a patch version; if there is no history, create pre-patch baseline."""
    root, info = _root_info(draft_dir) if info_path is None else (
        _safe_local(draft_dir, field="草稿目录"), Path(info_path))
    info_bytes = info.read_bytes()
    meta_path = root / "draft_meta_info.json"
    meta_bytes = meta_path.read_bytes() if meta_path.is_file() else None
    with _history_lock(root):
        manifest = _read_manifest(root)
        if manifest is None:
            manifest = _new_manifest(root, baseline_info or info_bytes)
            if baseline_info is not None:
                _snapshot_bytes(root, manifest, baseline_info, baseline_meta,
                                kind="import", label="pre-patch", parent=None)
        parent = manifest.get("current")
        if baseline_info is not None and parent:
            parent_item = next((item for item in manifest.get("versions") or []
                                if item.get("id") == parent), None)
            baseline_sha = hashlib.sha256(baseline_info).hexdigest()
            if (parent_item is not None
                    and parent_item.get("draft_sha256") != baseline_sha):
                _snapshot_bytes(
                    root, manifest, baseline_info, baseline_meta,
                    kind="editor-rewrite", label="jianying-rerender",
                    parent=parent, note="补丁前磁盘草稿与上一快照不一致；先记录剪映回写。")
                parent = manifest.get("current")
        return _snapshot_bytes(root, manifest, info_bytes, meta_bytes,
                               kind="patch", label=label, parent=parent,
                               ops_path=ops_path, note=note, artifacts=artifacts)


def record_snapshot(draft_dir, label="snapshot", note=None):
    """Snapshot the current draft; also initializes history for imported drafts."""
    root, info = _root_info(draft_dir)
    info_bytes = info.read_bytes()
    meta_path = root / "draft_meta_info.json"
    meta_bytes = meta_path.read_bytes() if meta_path.is_file() else None
    with _history_lock(root):
        manifest = _read_manifest(root)
        if manifest is None:
            manifest = _new_manifest(root, info_bytes)
            return _snapshot_bytes(root, manifest, info_bytes, meta_bytes,
                                   kind="import", label=label, parent=None, note=note)
        return _snapshot_bytes(root, manifest, info_bytes, meta_bytes,
                               kind="snapshot", label=label,
                               parent=manifest.get("current"), note=note)


def record_editor_rewrite(draft_dir, note=None):
    """Snapshot a draft after 剪映 rewrote it during export/save.

    Returns ``None`` when there is no history or the bytes still match the
    current snapshot; callers should keep the export receipt on the version
    that was actually exported.
    """
    root, info = _root_info(draft_dir)
    info_bytes = info.read_bytes()
    meta_path = root / "draft_meta_info.json"
    meta_bytes = meta_path.read_bytes() if meta_path.is_file() else None
    with _history_lock(root):
        manifest = _read_manifest(root)
        if manifest is None:
            return None
        current_id = manifest.get("current")
        current = next((item for item in manifest.get("versions") or []
                        if item.get("id") == current_id), None)
        if current is None:
            return None
        if current.get("draft_sha256") == hashlib.sha256(info_bytes).hexdigest():
            return None
        return _snapshot_bytes(
            root, manifest, info_bytes, meta_bytes,
            kind="editor-rewrite", label="jianying-rerender",
            parent=current_id, note=note)


def record_export(draft_dir, export):
    """Attach an export receipt to the current version. Returns False if absent."""
    root, _ = _root_info(draft_dir)
    with _history_lock(root):
        manifest = _read_manifest(root)
        if manifest is None:
            return False
        current = manifest.get("current")
        for item in manifest.get("versions") or []:
            if item.get("id") != current:
                continue
            path = str(export.get("path") or "")
            duration = (export.get("probe") or {}).get("duration") \
                if isinstance(export.get("probe"), dict) else None
            receipt = {
                "path": path,
                "bytes": export.get("bytes"),
                "duration": duration,
                "created": _now(),
            }
            for old in item.get("exports") or []:
                if path and str(old.get("path")) == path:
                    old.update(receipt)
                    _write_manifest(root, manifest)
                    return True
            item.setdefault("exports", []).append(receipt)
            _write_manifest(root, manifest)
            return True
        return False


def list_versions(draft_dir):
    root, _ = _root_info(draft_dir)
    manifest = _read_manifest(root)
    if manifest is None:
        return {"schema": SCHEMA, "draft_id": None, "current": None,
                "versions": [], "history_path": None}
    return dict(manifest, history_path=str(_manifest_path(root)))


def _find(manifest, version_id):
    if not _VERSION_RE.match(str(version_id or "")):
        raise SkillError("版本号必须形如 v001", code="VALIDATION",
                         details={"version": version_id})
    for item in manifest.get("versions") or []:
        if item.get("id") == version_id:
            return item
    raise SkillError("找不到该版本", code="VERSION_NOT_FOUND",
                     details={"version": version_id})


def show_version(draft_dir, version_id):
    root, _ = _root_info(draft_dir)
    manifest = _read_manifest(root, required=True)
    item = dict(_find(manifest, version_id))
    item["history_path"] = str(_manifest_path(root))
    item["snapshot_path"] = str(root / item["snapshot"])
    if not Path(item["snapshot_path"]).is_file():
        raise SkillError("版本快照文件缺失", code="VERSION_CORRUPTED",
                         details={"version": version_id,
                                  "path": item["snapshot_path"]})
    return item


def _doc_at(root, item):
    path = root / item["snapshot"]
    if not path.is_file():
        raise SkillError("版本快照文件缺失", code="VERSION_CORRUPTED",
                         details={"version": item.get("id"), "path": str(path)})
    try:
        raw = path.read_bytes()
        text = raw.decode("utf-8-sig")
    except OSError as exc:
        raise SkillError("版本快照读取失败", code="VERSION_CORRUPTED",
                         details={"version": item.get("id"), "path": str(path),
                                  "reason": str(exc)}) from exc
    except UnicodeDecodeError as exc:
        raise SkillError("版本快照是加密/二进制草稿，不能读取",
                         code="DRAFT_ENCRYPTED",
                         details={"version": item.get("id"), "path": str(path)},
                         fix="在剪映里另存为明文副本后再做版本快照。") from exc
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise SkillError("版本快照损坏", code="VERSION_CORRUPTED",
                         details={"version": item.get("id"), "path": str(path),
                                  "reason": str(exc)}) from exc


def _counts(document):
    materials = document.get("materials") or {}
    return {
        "canvas": document.get("canvas_config") or {},
        "duration": round(float(document.get("duration") or 0) / 1_000_000, 3),
        "name": document.get("name"),
        "tracks": {track.get("type"): len(track.get("segments") or [])
                   for track in document.get("tracks") or []},
        "materials": {key: len(value) for key, value in materials.items()
                      if isinstance(value, list) and value},
        "texts": [str((json.loads(item.get("content") or "{}") or {}).get("text") or "")
                  for item in materials.get("texts") or []],
        "segment_ids": [segment.get("id") for track in document.get("tracks") or []
                        for segment in track.get("segments") or []],
    }


def diff_versions(draft_dir, version_id, against=None):
    root, _ = _root_info(draft_dir)
    manifest = _read_manifest(root, required=True)
    target = _find(manifest, version_id)
    base_id = against or target.get("parent")
    if not base_id:
        raise SkillError("该版本没有父版本，请用 --against 指定基线",
                         code="VALIDATION", details={"version": version_id})
    base = _find(manifest, base_id)
    left_doc = _doc_at(root, base)
    right_doc = _doc_at(root, target)
    left = _counts(left_doc)
    right = _counts(right_doc)
    changes = []
    left_fp = _segment_fingerprints(left_doc)
    right_fp = _segment_fingerprints(right_doc)
    changed_segments = [
        {"id": segment_id,
         "label": right_fp[segment_id]["label"]}
        for segment_id in sorted(set(left_fp) & set(right_fp))
        if left_fp[segment_id]["digest"] != right_fp[segment_id]["digest"]
    ]
    for key in ("canvas", "duration", "name"):
        if left[key] != right[key]:
            changes.append(f"{key}: {left[key]!r} -> {right[key]!r}")
    for key in ("tracks", "materials"):
        keys = set(left[key]) | set(right[key])
        for name in sorted(keys, key=str):
            if left[key].get(name, 0) != right[key].get(name, 0):
                changes.append(f"{key}.{name}: {left[key].get(name, 0)} -> {right[key].get(name, 0)}")
    for text in left["texts"]:
        if text not in right["texts"]:
            changes.append(f"text removed: {text!r}")
    for text in right["texts"]:
        if text not in left["texts"]:
            changes.append(f"text added: {text!r}")
    added = [item for item in right["segment_ids"] if item not in left["segment_ids"]]
    removed = [item for item in left["segment_ids"] if item not in right["segment_ids"]]
    if added:
        changes.append(f"segments added: {len(added)}")
    if removed:
        changes.append(f"segments removed: {len(removed)}")
    if changed_segments:
        labels = ", ".join(item["label"] for item in changed_segments[:5])
        if len(changed_segments) > 5:
            labels += f" 等 {len(changed_segments)} 段"
        changes.append(f"segments changed: {labels}")
    layout_change = None
    from_layout = {"layout": base.get("layout"),
                   "timeline_id": base.get("timeline_id")}
    to_layout = {"layout": target.get("layout"),
                 "timeline_id": target.get("timeline_id")}
    # 旧清单没有 layout 字段：来源未知，不当作一次布局迁移报出来。
    if (from_layout["layout"] is not None and to_layout["layout"] is not None
            and from_layout != to_layout):
        layout_change = {"from": from_layout, "to": to_layout}
    note = ("比较草稿结构、片段字段与主/附加材质指纹；像素/听感差异仍需分别 "
            "render 后抽帧或听音频。")
    if layout_change:
        note = f"{note}两个快照来自不同布局，结构差异可能包含布局迁移。"
    return {
        "from": base["id"],
        "to": target["id"],
        "kind": "structural",
        "note": note,
        "layout_change": layout_change,
        "changed_segments": changed_segments,
        "base": left,
        "target": right,
        "changes": changes or ["结构无变化"],
    }


def _input_issues(item):
    issues = []
    for entry in item.get("inputs") or []:
        if not isinstance(entry, dict):
            continue
        path_text = str(entry.get("path") or "")
        if entry.get("kind") == "remote" or not path_text:
            issues.append({"path": path_text, "reason": "remote_unverified"})
            continue
        path = Path(path_text)
        try:
            if not path.exists():
                issues.append({"path": path_text, "reason": "missing"})
            elif entry.get("size") is not None and path.is_file():
                stat = path.stat()
                if stat.st_size != entry.get("size"):
                    issues.append({"path": path_text, "reason": "size_changed"})
                elif (entry.get("sha256")
                      and hashlib.sha256(path.read_bytes()).hexdigest()
                      != entry["sha256"]):
                    issues.append({"path": path_text, "reason": "sha256_changed"})
        except OSError as exc:
            issues.append({"path": path_text, "reason": "unreadable",
                           "detail": str(exc)})
    return issues


def restore_version(draft_dir, version_id, out_dir, *, name=None):
    root, _ = _root_info(draft_dir)
    manifest = _read_manifest(root, required=True)
    item = _find(manifest, version_id)
    document = copy.deepcopy(_doc_at(root, item))
    out = _safe_local(out_dir, field="恢复目标目录")
    if out == root or out.is_relative_to(root):
        raise SkillError("恢复目标不能位于源草稿目录内部，否则会污染源版本树",
                         code="VALIDATION",
                         details={"source": str(root), "out": str(out)})
    if out.exists():
        raise SkillError("恢复目标已存在；版本恢复只写新目录，不覆盖",
                         code="OUTPUT_EXISTS", details={"path": str(out)})
    staging = out.parent / f".{out.name}.{uuid.uuid4().hex[:8]}.restore-tmp"
    try:
        staging.mkdir(parents=True, exist_ok=False)
    except OSError as exc:
        raise SkillError("创建恢复暂存目录失败", code="OUTPUT_WRITE_FAILED",
                         details={"path": str(staging), "reason": str(exc)}) from exc
    now = _now()
    restored_name = str(name or f"{document.get('name') or 'draft'} ({version_id})")
    document.update({
        "id": str(uuid.uuid4()).upper(),
        "name": restored_name,
        "path": str(out),
        "create_time": now,
        "update_time": now,
    })
    info = staging / "draft_info.json"
    meta_written = staging / "draft_meta_info.json"
    try:
        _atomic_write_text(
            info, json.dumps(document, ensure_ascii=False, separators=(",", ":")))
        meta_rel = item.get("meta_snapshot")
        if meta_rel is None:
            # 兼容旧清单：尝试与 snapshot 同目录的 draft_meta_info.json。
            meta_rel = str(item.get("snapshot") or "").replace(
                "draft_info.json", "draft_meta_info.json")
        source_meta = root / meta_rel
        meta = None
        if source_meta.is_file():
            try:
                meta = json.loads(source_meta.read_text("utf-8-sig"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                meta = None
        if meta is not None:
            meta.update({
                "draft_id": document["id"],
                "draft_name": restored_name,
                "draft_fold_path": str(out),
                "draft_root_path": str(out.parent),
                "tm_draft_create": now * 1_000_000,
                "tm_draft_modified": now * 1_000_000,
                "tm_duration": document.get("duration") or 0,
            })
            _atomic_write_text(
                meta_written,
                json.dumps(meta, ensure_ascii=False, separators=(",", ":")))
        _atomic_write_text((staging / MARKER), json.dumps({
            "schema": "jianying-skill/v1",
            "created": now,
            "plan": f"restored from {draft_dir}@{version_id}",
            "name": restored_name,
        }, ensure_ascii=False, indent=2))
        record_initial(
            staging, label=f"restore {version_id}",
            note=f"restored from {root} at {version_id}", kind="restore",
            meta_path=meta_written if meta_written.is_file() else None)
        try:
            os.replace(staging, out)
        except OSError as exc:
            raise SkillError("恢复目录发布失败", code="OUTPUT_WRITE_FAILED",
                             details={"path": str(out), "stage": str(staging),
                                      "reason": str(exc)}) from exc
    except BaseException:
        shutil.rmtree(staging, ignore_errors=True)
        raise
    input_issues = _input_issues(item)
    return {
        "draft_dir": str(out),
        "info_path": str(out / "draft_info.json"),
        "draft_id": document["id"],
        "name": restored_name,
        "duration": round(float(document.get("duration") or 0) / 1_000_000, 3),
        "restored_from": str(root),
        "version": version_id,
        "input_issues": input_issues,
        "versions": list_versions(out),
    }
