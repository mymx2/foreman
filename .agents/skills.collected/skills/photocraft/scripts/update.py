#!/usr/bin/env python3
"""Check and update this skill from its GitHub repository.

  python scripts/update.py --check [--refresh|--offline] [--json]
  python scripts/update.py --status [--json]
  python scripts/update.py --apply --yes [--force] [--stage-only] [--method auto|git|zip]
  python scripts/update.py --rollback --yes

The update source is the repository; --apply uses git sparse checkout when
available and falls back to the repository ZIP. No release package is needed.
State lives in <skill>/.state/update.json; replaced packages keep a sibling
backup and the helper writes .state/last_apply.json.

Exit codes for --check: 0 current, 10 stale, 2 unknown/error.
Exit codes for --apply/--rollback: 0 staged/succeeded, 1 failed, 2 usage,
11 backoff/hold (do not retry now). --apply 0 means staged; poll --status until
last_apply is no longer pending.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
import zipfile
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlparse

SKILL_ROOT = Path(__file__).resolve().parent.parent
MANIFEST_PATH = SKILL_ROOT / "references" / "update.json"
STATE_DIR = SKILL_ROOT / ".state"
STATE_PATH = STATE_DIR / "update.json"
LAST_APPLY = STATE_DIR / "last_apply.json"
HOLD_PATH = STATE_DIR / "hold.json"
EXIT_BACKOFF = 11


def _default_work_root() -> Path:
    override = os.environ.get("PHOTOCRAFT_UPDATE_WORK_DIR")
    if override:
        return Path(override)
    if os.name == "nt":
        base = Path(os.environ.get("LOCALAPPDATA") or (Path.home() / "AppData" / "Local"))
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Caches"
    else:
        base = Path(os.environ.get("XDG_CACHE_HOME") or (Path.home() / ".cache"))
    return base / "photocraft-skill"


WORK_ROOT = _default_work_root()
BACKUP_ROOT = WORK_ROOT / "backups"
STAGING_ROOT = WORK_ROOT / "staging"
DEFAULT_CHECK_DAYS = 7
MIN_CHECK_DAYS = 3
MAX_CHECK_DAYS = 30
DEFAULT_RETRY_MINUTES = 30
MAX_RETRY_MINUTES = 24 * 60
USER_AGENT = "photocraft-skill-updater/1"
MANIFEST_KEYS = ("skill", "version", "updated", "source", "path", "branch")
GITHUB_HOSTS = {"github.com", "raw.githubusercontent.com", "codeload.github.com",
                "api.github.com", "objects.githubusercontent.com"}
SEVERITIES = {"normal", "security", "breaking"}


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _parse_time(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _version_key(value: str) -> tuple[int, int, int]:
    match = re.match(r"^v?(\d+)\.(\d+)(?:\.(\d+))?$", str(value).strip())
    if not match:
        raise ValueError(f"not a version: {value!r}")
    return tuple(int(part or 0) for part in match.groups())


def _load_json(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return data


def _github_parts(source: str) -> tuple[str, str]:
    match = re.match(r"https?://github\.com/([^/]+)/([^/]+?)(?:\.git)?/?$", source.strip())
    if not match:
        raise ValueError("manifest needs an explicit manifest URL for non-GitHub sources")
    return match.group(1), match.group(2)


def _github_manifest(source: str, branch: str, path: str) -> str:
    owner, repo = _github_parts(source)
    return f"https://raw.githubusercontent.com/{owner}/{repo}/{branch}/{path.strip('/')}/references/update.json"


def _github_zip(source: str, branch: str) -> str:
    owner, repo = _github_parts(source)
    return f"https://github.com/{owner}/{repo}/archive/refs/heads/{branch}.zip"


def _mirror(url: str, mirror: str) -> str:
    if not mirror or not url.startswith(("http://", "https://")):
        return url
    return mirror.rstrip("/") + "/" + url


def _ttl_seconds(local: dict) -> int:
    value = os.environ.get("PHOTOCRAFT_UPDATE_TTL_DAYS")
    days = local.get("check_interval_days", DEFAULT_CHECK_DAYS) if value is None else value
    try:
        days = int(days)
    except (TypeError, ValueError):
        days = DEFAULT_CHECK_DAYS
    return max(MIN_CHECK_DAYS, min(MAX_CHECK_DAYS, days)) * 24 * 3600


def _retry_after(fail_count: int) -> str:
    minutes = min(DEFAULT_RETRY_MINUTES * (2 ** max(0, fail_count - 1)), MAX_RETRY_MINUTES)
    return (datetime.now(timezone.utc) + timedelta(minutes=minutes)).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _read_hold() -> dict:
    try:
        data = _load_json(HOLD_PATH)
    except (OSError, ValueError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def _last_apply() -> dict:
    try:
        data = _load_json(LAST_APPLY)
    except (OSError, ValueError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def _write_last_apply(data: dict) -> None:
    try:
        STATE_DIR.mkdir(mode=0o700, parents=True, exist_ok=True)
        tmp = STATE_DIR / f".last_apply.{os.getpid()}.tmp"
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        os.replace(tmp, LAST_APPLY)
    except OSError as exc:
        print(f"update: cannot write {LAST_APPLY}: {exc}", file=sys.stderr)


def _prune_backups(keep: int = 3) -> None:
    try:
        backups = sorted(BACKUP_ROOT.glob(f"{SKILL_ROOT.name}.bak-*"),
                         key=lambda path: path.stat().st_mtime, reverse=True)
        for old in backups[keep:]:
            shutil.rmtree(old, ignore_errors=True)
        failed = sorted(BACKUP_ROOT.glob(f"{SKILL_ROOT.name}.failed-*"),
                        key=lambda path: path.stat().st_mtime, reverse=True)
        for old in failed[keep:]:
            shutil.rmtree(old, ignore_errors=True)
    except OSError:
        pass


def _validate_manifest(data: dict, origin: str) -> dict:
    missing = [key for key in MANIFEST_KEYS if not data.get(key)]
    if missing:
        raise ValueError(f"{origin}: missing {', '.join(missing)}")
    if data["skill"] != "photocraft":
        raise ValueError(f"{origin}: skill must be photocraft")
    _version_key(data["version"])
    date.fromisoformat(data["updated"])
    path = str(data["path"]).strip("/")
    if not path or path.startswith("/") or ".." in Path(path).parts:
        raise ValueError(f"{origin}: invalid path")
    days = data.get("check_interval_days", DEFAULT_CHECK_DAYS)
    if isinstance(days, bool) or not isinstance(days, int) or not MIN_CHECK_DAYS <= days <= MAX_CHECK_DAYS:
        raise ValueError(f"{origin}: check_interval_days must be {MIN_CHECK_DAYS}..{MAX_CHECK_DAYS}")
    severity = data.get("severity", "normal")
    if severity not in SEVERITIES:
        raise ValueError(f"{origin}: severity must be one of {sorted(SEVERITIES)}")
    cli = data.get("cli_supported")
    if cli is not None:
        if not isinstance(cli, dict) or not cli.get("min") or not cli.get("max"):
            raise ValueError(f"{origin}: cli_supported needs min/max")
        _version_key(cli["min"])
        _version_key(cli["max"])
    source = str(data["source"]).strip()
    if not data.get("manifest"):
        data = dict(data)
        data["manifest"] = _github_manifest(source, str(data["branch"]), path)
    return data


def _token() -> str | None:
    return os.environ.get("PHOTOCRAFT_UPDATE_TOKEN") or os.environ.get("GITHUB_TOKEN")


def _http_get(url: str, timeout: int) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "*/*"})
    token = _token()
    if token and (urlparse(url).hostname or "") in GITHUB_HOSTS:
        request.add_header("Authorization", f"Bearer {token}")
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read()


def _read_bytes(ref: str, timeout: int) -> bytes:
    path = Path(ref)
    if path.is_file():
        return path.read_bytes()
    return _http_get(ref, timeout)


def _fetch_manifest(local: dict, override: str | None, timeout: int, mirrors=(), preferred: str | None = None):
    ref = override or local["manifest"]
    path = Path(ref)
    if path.is_file():
        return _validate_manifest(_load_json(path), str(path)), str(path)
    candidates = [ref, *(_mirror(ref, mirror) for mirror in mirrors if mirror)]
    budget = max(1, int(timeout))
    per_source = max(1, budget // max(1, len(candidates)))
    deadline = time.monotonic() + budget
    errors = []
    for candidate in candidates:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            break
        try:
            data = json.loads(_http_get(candidate, max(1, min(per_source, int(remaining)))).decode("utf-8"))
            return _validate_manifest(data, candidate), candidate
        except (OSError, ValueError, RuntimeError, urllib.error.URLError, json.JSONDecodeError) as exc:
            errors.append(f"{candidate}: {exc}")
    raise RuntimeError("; ".join(errors) if errors else "no manifest source")


def _fingerprint() -> str:
    try:
        return hashlib.sha256(MANIFEST_PATH.read_bytes()).hexdigest()
    except OSError:
        return ""


def _read_state() -> dict:
    try:
        data = _load_json(STATE_PATH)
    except (OSError, ValueError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def _write_state(data: dict) -> None:
    try:
        STATE_DIR.mkdir(mode=0o700, parents=True, exist_ok=True)
        tmp = STATE_DIR / f".update.{os.getpid()}.tmp"
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        os.chmod(tmp, 0o600)
        os.replace(tmp, STATE_PATH)
    except OSError as exc:
        print(f"update: cannot write state {STATE_PATH}: {exc}", file=sys.stderr)


def _cached(local: dict, state: dict) -> bool:
    if state.get("local_version") != local["version"] or state.get("local_fingerprint") != _fingerprint():
        return False
    result = state.get("result")
    now = datetime.now(timezone.utc)
    try:
        if result == "unknown":
            retry = state.get("retry_after")
            return bool(retry) and now < _parse_time(retry)
        if result in ("current", "stale"):
            return (now - _parse_time(state["checked_at"])).total_seconds() <= _ttl_seconds(local)
    except (KeyError, ValueError, TypeError):
        return False
    return False


def _remote_from_state(state: dict) -> dict | None:
    if not state.get("upstream_version"):
        return None
    return {"version": state.get("upstream_version"),
            "updated": state.get("upstream_updated") or "",
            "severity": state.get("upstream_severity") or "normal",
            "cli_supported": state.get("upstream_cli_supported")}


def _write_check_state(local: dict, remote: dict, result: str, source: str, error: str = "") -> dict:
    state = {"schema": 1, "checked_at": _now(), "local_version": local["version"],
             "local_fingerprint": _fingerprint(), "upstream_version": remote["version"],
             "upstream_updated": remote.get("updated"),
             "upstream_severity": remote.get("severity", "normal"),
             "upstream_cli_supported": remote.get("cli_supported"),
             "result": result, "manifest": remote.get("manifest") or local.get("manifest"),
             "last_source": source, "fail_count": 0, "retry_after": None, "error": error or None}
    _write_state(state)
    return state


def _write_unknown_state(local: dict, previous: dict, error: str) -> dict:
    fail_count = int(previous.get("fail_count") or 0) + 1
    state = dict(previous)
    state.update({"schema": 1, "checked_at": _now(), "local_version": local["version"],
                  "local_fingerprint": _fingerprint(), "result": "unknown", "error": error,
                  "fail_count": fail_count, "retry_after": _retry_after(fail_count)})
    _write_state(state)
    return state


def _print_check(local: dict, remote: dict | None, result: str, cached: bool, state: dict, as_json: bool) -> None:
    upstream = None
    if remote:
        upstream = {"version": remote.get("version"), "updated": remote.get("updated") or "",
                    "severity": remote.get("severity", "normal"),
                    "cli_supported": remote.get("cli_supported")}
    payload = {"local": {"version": local["version"], "updated": local["updated"],
                         "check_interval_days": local.get("check_interval_days", DEFAULT_CHECK_DAYS)},
               "upstream": upstream, "result": result, "cached": cached,
               "checked_at": state.get("checked_at"), "last_source": state.get("last_source"),
               "fail_count": state.get("fail_count", 0), "retry_after": state.get("retry_after"),
               "manifest": local.get("manifest"), "error": state.get("error")}
    if as_json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return
    print(f"local:    {local['version']} ({local['updated']})")
    if upstream:
        note = f" [{upstream['severity']}]" if upstream["severity"] != "normal" else ""
        print(f"upstream: {upstream['version']} ({upstream['updated']}){note}")
    else:
        print("upstream: unknown")
    print(f"result:   {result} ({'cached' if cached else 'checked now'})")
    if state.get("retry_after"):
        print(f"retry after: {state['retry_after']}")
    if state.get("error"):
        print(f"error:    {state['error']}", file=sys.stderr)


def check(args) -> int:
    local = _validate_manifest(_load_json(MANIFEST_PATH), str(MANIFEST_PATH))
    state = _read_state()
    if args.offline:
        if not state:
            _print_check(local, None, "unknown", True, {"error": "offline and no state"}, args.json)
            return 2
        remote = _remote_from_state(state)
        result = state.get("result", "unknown")
        _print_check(local, remote, result, True, state, args.json)
        return 0 if result == "current" else 10 if result == "stale" else 2
    if not args.refresh and _cached(local, state):
        result = state.get("result", "unknown")
        _print_check(local, _remote_from_state(state), result, True, state, args.json)
        return 0 if result == "current" else 10 if result == "stale" else 2
    try:
        remote, source = _fetch_manifest(local, args.manifest, args.check_timeout,
                                         local.get("mirrors") or [], state.get("last_source"))
        result = "stale" if _version_key(remote["version"]) > _version_key(local["version"]) else "current"
        state = _write_check_state(local, remote, result, source)
        _print_check(local, remote, result, False, state, args.json)
        return 0 if result == "current" else 10
    except (OSError, ValueError, RuntimeError, urllib.error.URLError, json.JSONDecodeError) as exc:
        state = _write_unknown_state(local, state, str(exc)[:500])
        _print_check(local, _remote_from_state(state), "unknown", False, state, args.json)
        return 2


def status(args) -> int:
    local = _validate_manifest(_load_json(MANIFEST_PATH), str(MANIFEST_PATH))
    state = _read_state()
    last = _last_apply()
    payload = {"local": {"version": local["version"], "updated": local["updated"],
                         "check_interval_days": local.get("check_interval_days", DEFAULT_CHECK_DAYS)},
               "check": state, "last_apply": last, "hold": _read_hold()}
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0
    print(f"local: {local['version']} ({local['updated']})")
    print(f"check: {state.get('result', 'never')} at {state.get('checked_at', '-')}"
          + (f", retry after {state['retry_after']}" if state.get("retry_after") else ""))
    print(f"apply: {last.get('status', 'never')} at {last.get('finished_at', '-')}"
          + (f", {last.get('message')}" if last.get("message") else ""))
    hold = _read_hold()
    if hold.get("version"):
        print(f"hold: {hold['version']} (rolled back; --force to reinstall)")
    return 0


def _git_checkout(source: str, branch: str, path: str, repo_dir: Path, staging_skill: Path, timeout: int) -> None:
    git = shutil.which("git")
    if not git:
        raise RuntimeError("git is required for --apply; use the skill manager or install git")
    env = dict(os.environ, GIT_TERMINAL_PROMPT="0")
    base = [git, "clone", "--depth", "1", "--filter=blob:none", "--sparse",
            "--branch", branch, source, str(repo_dir)]
    result = subprocess.run(base, capture_output=True, text=True, encoding="utf-8",
                            errors="replace", timeout=timeout, env=env)
    if result.returncode != 0:
        base = [part for part in base if part != "--filter=blob:none"]
        result = subprocess.run(base, capture_output=True, text=True, encoding="utf-8",
                                errors="replace", timeout=timeout, env=env)
    if result.returncode != 0:
        raise RuntimeError("git clone failed: " + (result.stderr or result.stdout)[-800:])
    result = subprocess.run([git, "-C", str(repo_dir), "sparse-checkout", "set", path],
                            capture_output=True, text=True, encoding="utf-8",
                            errors="replace", timeout=timeout, env=env)
    if result.returncode != 0:
        raise RuntimeError("git sparse-checkout failed: " + (result.stderr or result.stdout)[-800:])
    checked_out = repo_dir / path
    if not (checked_out / "SKILL.md").is_file():
        raise RuntimeError(f"checkout does not contain {path}/SKILL.md")
    shutil.copytree(checked_out, staging_skill,
                    ignore=shutil.ignore_patterns(".git", "__pycache__", ".state"))


def _download(ref: str, dest: Path, timeout: int) -> None:
    source = Path(ref)
    if source.is_file():
        shutil.copyfile(source, dest)
        return
    request = urllib.request.Request(ref, headers={"User-Agent": USER_AGENT, "Accept": "*/*"})
    token = _token()
    if token and (urlparse(ref).hostname or "") in GITHUB_HOSTS:
        request.add_header("Authorization", f"Bearer {token}")
    with urllib.request.urlopen(request, timeout=timeout) as response, dest.open("wb") as out:
        shutil.copyfileobj(response, out, length=1024 * 1024)


def _extract_zip(archive: Path, target: Path, skill_path: str) -> None:
    clean = skill_path.strip("/")
    with zipfile.ZipFile(archive) as zf:
        names = zf.namelist()
        marker = f"/{clean}/SKILL.md"
        candidate = next((name for name in names if name.endswith(marker)), None)
        if not candidate:
            raise ValueError(f"archive does not contain {clean}/SKILL.md")
        top = candidate.split("/", 1)[0]
        prefix = f"{top}/{clean}/"
        for info in zf.infolist():
            if info.is_dir() or not info.filename.startswith(prefix):
                continue
            relative = info.filename[len(prefix):]
            if not relative or relative.startswith("/") or ".." in Path(relative).parts:
                raise ValueError(f"unsafe archive member: {info.filename}")
            destination = target / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(zf.read(info))
    if not (target / "SKILL.md").is_file():
        raise ValueError("archive extraction produced no SKILL.md")


def _stage_package(source: str, branch: str, path: str, method: str,
                   staging_root: Path, staging_skill: Path, timeout: int, mirrors=()) -> str:
    errors: list[str] = []
    attempts: list[tuple[str, str | None]] = []
    if method in ("auto", "git") and shutil.which("git"):
        attempts.append(("git", None))
    if method in ("auto", "zip"):
        try:
            direct = _github_zip(source, branch)
            attempts.append(("zip", direct))
            attempts.extend(("zip", _mirror(direct, mirror)) for mirror in mirrors if mirror)
        except ValueError as exc:
            errors.append(f"zip: {exc}")
    for candidate, ref in attempts:
        repo_dir = staging_root / "repo"
        if repo_dir.exists():
            shutil.rmtree(repo_dir, ignore_errors=True)
        if staging_skill.exists():
            shutil.rmtree(staging_skill, ignore_errors=True)
        try:
            if candidate == "git":
                _git_checkout(source, branch, path, repo_dir, staging_skill, timeout)
            else:
                archive = staging_root / "repo.zip"
                _download(ref, archive, timeout)
                _extract_zip(archive, staging_skill, path)
            return f"{candidate}:{ref}" if ref else candidate
        except (OSError, ValueError, RuntimeError, zipfile.BadZipFile,
                urllib.error.URLError, subprocess.SubprocessError) as exc:
            errors.append(f"{candidate}{' ' + ref if ref else ''}: {exc}")
            if staging_skill.exists():
                shutil.rmtree(staging_skill, ignore_errors=True)
    raise RuntimeError("; ".join(errors))


def _validate_staged(staging: Path, remote: dict) -> None:
    staged = _validate_manifest(_load_json(staging / "references" / "update.json"), "staged update.json")
    if staged["version"] != remote["version"]:
        raise ValueError(f"staged version {staged['version']} != upstream {remote['version']}")
    result = subprocess.run([sys.executable, "scripts/test_docs.py"], cwd=staging,
                            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=180)
    if result.returncode != 0:
        tail = (result.stdout + result.stderr).strip().splitlines()[-8:]
        raise ValueError("staged test_docs failed: " + " | ".join(tail))


HELPER = r'''
import argparse, json, os, shutil, subprocess, sys, time
from datetime import datetime, timedelta, timezone
from pathlib import Path

def now():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")

def wait_for(pid):
    if os.name == "nt":
        import ctypes
        handle = ctypes.windll.kernel32.OpenProcess(0x00100000, False, pid)
        if handle:
            ctypes.windll.kernel32.WaitForSingleObject(handle, 60000)
            ctypes.windll.kernel32.CloseHandle(handle)
        else:
            time.sleep(1.5)
        return
    for _ in range(600):
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return
        except OSError:
            return
        time.sleep(0.1)

def installed_version(skill):
    try:
        data = json.loads((Path(skill) / "references" / "update.json").read_text(encoding="utf-8"))
        return data.get("version")
    except Exception:
        return None

def hold_path(skill):
    return Path(skill) / ".state" / "hold.json"

def write_hold(skill, version):
    if not version:
        return
    path = hold_path(skill)
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    path.write_text(json.dumps({"version": version, "since": now()}, ensure_ascii=False) + "\n", encoding="utf-8")

def clear_hold(skill):
    try:
        hold_path(skill).unlink()
    except OSError:
        pass

def write_state(skill, status, message, backup=None, version=None):
    state_dir = Path(skill) / ".state"
    state_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
    path = state_dir / "last_apply.json"
    previous = {}
    try:
        previous = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        pass
    fail_count = 0
    retry_after = None
    if status == "error":
        fail_count = int(previous.get("fail_count") or 0) + 1
        minutes = min(60 * (2 ** (fail_count - 1)), 24 * 60)
        retry_after = (datetime.now(timezone.utc) + timedelta(minutes=minutes)).replace(
            microsecond=0).isoformat().replace("+00:00", "Z")
    state = {"schema": 1, "finished_at": now(), "status": status, "message": message,
             "backup": str(backup) if backup else None, "version": version,
             "fail_count": fail_count, "retry_after": retry_after}
    tmp = state_dir / f".last_apply.{os.getpid()}.tmp"
    tmp.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, path)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--parent", type=int, required=True)
    ap.add_argument("--skill", required=True)
    ap.add_argument("--staging", default="")
    ap.add_argument("--backup", required=True)
    ap.add_argument("--log", required=True)
    ap.add_argument("--mode", choices=("apply", "rollback"), default="apply")
    ap.add_argument("--expected-version", default="")
    args = ap.parse_args()
    skill, staging, backup = Path(args.skill), Path(args.staging or ""), Path(args.backup)
    log = Path(args.log)
    status, message, failed, applied_version = "error", "", None, None
    wait_for(args.parent)
    try:
        if backup.exists() and args.mode == "apply":
            raise RuntimeError("backup target already exists")
        backup.parent.mkdir(parents=True, exist_ok=True)
        bad_version = None
        if args.mode == "apply":
            if not staging.is_dir():
                raise RuntimeError("staging directory is missing")
            shutil.move(str(skill), str(backup))
            try:
                shutil.move(str(staging), str(skill))
            except Exception:
                shutil.move(str(backup), str(skill))
                raise
            result = subprocess.run([sys.executable, "scripts/test_docs.py"], cwd=skill,
                                    capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=180)
            if result.returncode != 0:
                failed = backup.parent / (skill.name + ".failed-" + now().replace(":", "").replace("-", ""))
                shutil.move(str(skill), str(failed))
                shutil.move(str(backup), str(skill))
                raise RuntimeError("staged test_docs failed: " + (result.stdout + result.stderr)[-800:])
            applied_version = installed_version(skill)
            if args.expected_version and applied_version != args.expected_version:
                failed = backup.parent / (skill.name + ".failed-" + now().replace(":", "").replace("-", ""))
                shutil.move(str(skill), str(failed))
                shutil.move(str(backup), str(skill))
                raise RuntimeError(f"installed version {applied_version} != expected {args.expected_version}")
            clear_hold(skill)
        else:
            if not backup.exists():
                raise RuntimeError("no backup to restore")
            bad_version = installed_version(skill)
            failed = backup.parent / (skill.name + ".failed-" + now().replace(":", "").replace("-", ""))
            shutil.move(str(skill), str(failed))
            try:
                shutil.move(str(backup), str(skill))
            except Exception:
                shutil.move(str(failed), str(skill))
                raise
        if args.mode == "rollback":
            applied_version = installed_version(skill)
            write_hold(skill, bad_version)
        status, message = "ok", "applied" if args.mode == "apply" else "rolled back"
    except Exception as exc:
        status, message = "error", f"{type(exc).__name__}: {exc}"
        if backup.exists() and not skill.exists():
            try:
                shutil.move(str(backup), str(skill))
            except Exception:
                pass
        if args.mode == "apply" and args.expected_version:
            try:
                write_hold(skill, args.expected_version)
            except Exception:
                pass
    finally:
        try:
            write_state(skill, status, message, backup, applied_version or args.expected_version)
        except Exception:
            pass
        log.parent.mkdir(parents=True, exist_ok=True)
        log.write_text(json.dumps({"status": status, "message": message, "backup": str(backup),
                                   "version": applied_version or args.expected_version,
                                   "failed": str(failed) if failed else None}, ensure_ascii=False) + "\n",
                       encoding="utf-8")
        if args.mode == "apply":
            shutil.rmtree(staging.parent, ignore_errors=True)
    return 0 if status == "ok" else 1

if __name__ == "__main__":
    raise SystemExit(main())
'''


def _launch_helper(skill: Path, staging: Path, backup: Path, log: Path, mode: str,
                   expected_version: str = "") -> None:
    temp = Path(tempfile.mkdtemp(prefix="photocraft-updater-"))
    helper = temp / "helper.py"
    helper.write_text(HELPER, encoding="utf-8")
    command = [sys.executable, str(helper), "--parent", str(os.getpid()), "--skill", str(skill),
               "--staging", str(staging), "--backup", str(backup), "--log", str(log), "--mode", mode,
               "--expected-version", expected_version]
    kwargs = {"cwd": str(temp), "stdout": subprocess.DEVNULL, "stderr": subprocess.DEVNULL, "close_fds": True}
    if os.name == "nt":
        kwargs["creationflags"] = 0x00000008 | 0x00000200  # DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP
    else:
        kwargs["start_new_session"] = True
    subprocess.Popen(command, **kwargs)


def _apply_backoff(args) -> bool:
    if args.force:
        return False
    last = _last_apply()
    if last.get("status") != "error":
        return False
    retry = last.get("retry_after")
    try:
        if retry and datetime.now(timezone.utc) < _parse_time(retry):
            return True
    except (TypeError, ValueError):
        return False
    return False


def _record_apply_error(local: dict, version: str | None, message: str) -> None:
    previous = _last_apply()
    fail_count = int(previous.get("fail_count") or 0) + 1
    _write_last_apply({"schema": 1, "finished_at": _now(), "status": "error",
                       "message": message[:800], "version": version,
                       "local_version": local["version"], "fail_count": fail_count,
                       "retry_after": _retry_after(fail_count)})


def apply(args) -> int:
    if not args.yes:
        print("update: refusing to modify the skill without --yes", file=sys.stderr)
        return 2
    local = _validate_manifest(_load_json(MANIFEST_PATH), str(MANIFEST_PATH))
    if _apply_backoff(args):
        print(json.dumps({"status": "backoff", "state": str(LAST_APPLY)}, ensure_ascii=False))
        return EXIT_BACKOFF
    mirrors = local.get("mirrors") or []
    state = _read_state()
    try:
        remote, source = _fetch_manifest(local, args.manifest, args.timeout, mirrors, state.get("last_source"))
    except (OSError, ValueError, RuntimeError, urllib.error.URLError, json.JSONDecodeError) as exc:
        _record_apply_error(local, None, f"cannot read upstream manifest: {exc}")
        print(f"update: cannot read upstream manifest: {exc}", file=sys.stderr)
        return 1
    if _version_key(remote["version"]) <= _version_key(local["version"]):
        print(f"update: current ({local['version']})")
        return 0
    hold = _read_hold()
    if hold.get("version") == remote["version"] and not args.force:
        print(json.dumps({"status": "hold", "version": remote["version"], "state": str(HOLD_PATH)},
                         ensure_ascii=False))
        return EXIT_BACKOFF
    _prune_backups()
    staging_root = STAGING_ROOT / f"{remote['version']}-{os.getpid()}"
    staging_skill = staging_root / "skill"
    try:
        if staging_root.exists():
            shutil.rmtree(staging_root)
        staging_root.mkdir(parents=True)
        _stage_package(local["source"], local["branch"], local["path"], args.method,
                       staging_root, staging_skill, max(args.timeout, 60), mirrors)
        _validate_staged(staging_skill, remote)
    except (OSError, ValueError, RuntimeError, urllib.error.URLError, subprocess.SubprocessError) as exc:
        shutil.rmtree(staging_root, ignore_errors=True)
        _record_apply_error(local, remote["version"], f"staging failed: {exc}")
        print(f"update: staging failed: {exc}", file=sys.stderr)
        return 1
    if args.stage_only:
        print(f"staged: {staging_skill}\nversion: {remote['version']}")
        return 0
    try:
        BACKUP_ROOT.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        shutil.rmtree(staging_root, ignore_errors=True)
        _record_apply_error(local, remote["version"], f"cannot create backup directory: {exc}")
        print(f"update: cannot create backup directory: {exc}", file=sys.stderr)
        return 1
    backup = BACKUP_ROOT / f"{SKILL_ROOT.name}.bak-{local['version']}-{datetime.now().strftime('%Y%m%dT%H%M%S')}"
    log = Path(tempfile.gettempdir()) / f"photocraft-update-{os.getpid()}.json"
    _write_last_apply({"schema": 1, "finished_at": _now(), "status": "pending",
                       "message": "staged; helper is applying", "version": remote["version"],
                       "local_version": local["version"], "backup": str(backup), "log": str(log),
                       "fail_count": 0, "retry_after": None})
    try:
        _launch_helper(SKILL_ROOT, staging_skill, backup, log, "apply", remote["version"])
    except OSError as exc:
        shutil.rmtree(staging_root, ignore_errors=True)
        _record_apply_error(local, remote["version"], f"cannot start helper: {exc}")
        print(f"update: cannot start helper: {exc}", file=sys.stderr)
        return 1
    print(json.dumps({"status": "staged", "version": remote["version"], "backup": str(backup),
                      "log": str(log), "state": str(LAST_APPLY)}, ensure_ascii=False))
    return 0


def rollback(args) -> int:
    if not args.yes:
        print("update: refusing to rollback without --yes", file=sys.stderr)
        return 2
    backup = None
    try:
        state = _load_json(LAST_APPLY)
        candidate = state.get("backup")
        if candidate and Path(candidate).is_dir():
            backup = Path(candidate)
    except (OSError, ValueError, json.JSONDecodeError):
        pass
    if backup is None:
        candidates = sorted(BACKUP_ROOT.glob(f"{SKILL_ROOT.name}.bak-*"),
                            key=lambda p: p.stat().st_mtime, reverse=True)
        backup = candidates[0] if candidates else None
    if backup is None:
        print("update: no backup found", file=sys.stderr)
        return 1
    log = Path(tempfile.gettempdir()) / f"photocraft-rollback-{os.getpid()}.json"
    try:
        _launch_helper(SKILL_ROOT, Path(""), backup, log, "rollback")
    except OSError as exc:
        print(f"update: cannot start helper: {exc}", file=sys.stderr)
        return 1
    print(json.dumps({"status": "staged", "backup": str(backup), "log": str(log)}, ensure_ascii=False))
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    mode = ap.add_mutually_exclusive_group()
    mode.add_argument("--check", action="store_true", help="compare local and upstream versions")
    mode.add_argument("--status", action="store_true", help="show check and last-apply state")
    mode.add_argument("--apply", action="store_true", help="download and stage the upstream package")
    mode.add_argument("--rollback", action="store_true", help="restore the most recent backup")
    ap.add_argument("--yes", action="store_true", help="required for --apply/--rollback")
    ap.add_argument("--force", action="store_true", help="ignore the apply backoff")
    ap.add_argument("--refresh", action="store_true", help="ignore the cached check")
    ap.add_argument("--offline", action="store_true", help="use the cached result only")
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    ap.add_argument("--manifest", help="override the manifest URL or local path")
    ap.add_argument("--method", choices=("auto", "git", "zip"), default="auto",
                    help="how to fetch the repository (default: git, fallback to zip)")
    ap.add_argument("--stage-only", action="store_true", help="stage and validate without replacing")
    ap.add_argument("--check-timeout", type=int, default=6, help="total manifest budget in seconds (default 6)")
    ap.add_argument("--timeout", type=int, default=60, help="seconds per download/clone (default 60)")
    args = ap.parse_args(argv)
    if args.status:
        return status(args)
    if args.apply:
        return apply(args)
    if args.rollback:
        return rollback(args)
    return check(args)


if __name__ == "__main__":
    raise SystemExit(main())
