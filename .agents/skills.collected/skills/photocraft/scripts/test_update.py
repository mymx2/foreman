#!/usr/bin/env python3
"""Self-test for update.py helpers (no network, no git clone).

  python <skill-dir>/scripts/test_update.py

Exit codes: 0 all checks passed, 1 one or more checks failed.
"""
from __future__ import annotations

import contextlib
import io
import json
import subprocess
import sys
import tempfile
import types
import zipfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import update  # noqa: E402

VALID = {"skill": "photocraft", "version": "1.0.0", "updated": "2026-11-01",
         "source": "https://github.com/mymx2/foreman", "branch": "master",
         "path": ".agents/skills.collected/skills/photocraft"}


def main() -> int:
    checks = []

    def check(name, fn):
        try:
            fn()
        except Exception as exc:
            checks.append((name, f"{type(exc).__name__}: {exc}"))
        else:
            checks.append((name, None))

    def versions():
        assert update._version_key("1.0.0") < update._version_key("1.1.0")
        assert update._version_key("v1.2") == (1, 2, 0)
        try:
            update._version_key("beta")
        except ValueError:
            pass
        else:
            raise AssertionError("invalid version accepted")

    def manifest():
        data = update._validate_manifest(dict(VALID), "test")
        assert data["manifest"].endswith("/references/update.json")
        for bad in (dict(VALID, version="1"), dict(VALID, path="../x"),
                    dict(VALID, source="https://example.com/repo")):
            try:
                update._validate_manifest(dict(bad), "test")
            except ValueError:
                pass
            else:
                raise AssertionError(f"invalid manifest accepted: {bad}")

    def urls():
        assert update._github_manifest(VALID["source"], "master", VALID["path"]).startswith(
            "https://raw.githubusercontent.com/mymx2/foreman/master/")
        assert update._github_zip(VALID["source"], "master").endswith(
            "/mymx2/foreman/archive/refs/heads/master.zip")

    def mirrors():
        assert update._mirror("https://github.com/a/b", "https://ghfast.top/") == \
            "https://ghfast.top/https://github.com/a/b"
        assert update._mirror("C:/local/path", "https://ghfast.top/") == "C:/local/path"

    def ttl():
        assert update._ttl_seconds({"check_interval_days": 7}) == 7 * 24 * 3600
        assert update._ttl_seconds({"check_interval_days": 1}) == 3 * 24 * 3600
        assert update._ttl_seconds({"check_interval_days": 99}) == 30 * 24 * 3600

    def unknown_cache():
        now = datetime.now(timezone.utc)
        state = {"local_version": VALID["version"], "local_fingerprint": update._fingerprint(),
                 "result": "unknown", "retry_after": (now + timedelta(minutes=30)).isoformat()}
        assert update._cached(dict(VALID), state) is True
        state["retry_after"] = (now - timedelta(minutes=1)).isoformat()
        assert update._cached(dict(VALID), state) is False

    def unknown_write():
        saved = (update.STATE_DIR, update.STATE_PATH)
        with tempfile.TemporaryDirectory() as tmp:
            update.STATE_DIR = Path(tmp)
            update.STATE_PATH = Path(tmp) / "update.json"
            try:
                first = update._write_unknown_state(dict(VALID), {}, "offline")
                second = update._write_unknown_state(dict(VALID), first, "offline")
                assert first["fail_count"] == 1 and second["fail_count"] == 2, (first, second)
                assert update._parse_time(second["retry_after"]) > update._parse_time(first["retry_after"])
                capped = update._retry_after(99)
                delta = update._parse_time(capped) - datetime.now(timezone.utc)
                assert delta <= timedelta(hours=24, minutes=1), delta
            finally:
                update.STATE_DIR, update.STATE_PATH = saved

    def fetch_local():
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "update.json"
            path.write_text(json.dumps(VALID), encoding="utf-8")
            data, source = update._fetch_manifest(dict(VALID), str(path), 1, [])
            assert data["version"] == VALID["version"] and source == str(path)

    def fallback_order():
        saved = (update._git_checkout, update._download, update._extract_zip)
        calls = []

        def no_git(*a, **k):
            raise RuntimeError("git failed")

        def download(ref, dest, timeout):
            calls.append(ref)
            if "ghfast" not in ref:
                raise RuntimeError("direct failed")
            Path(dest).write_bytes(b"zip")

        try:
            update._git_checkout = no_git
            update._download = download
            update._extract_zip = lambda archive, target, path: None
            with tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                result = update._stage_package("https://github.com/a/b", "master", VALID["path"],
                                               "auto", root, root / "skill", 1, ["https://ghfast.top/"])
                assert result.startswith("zip:https://ghfast.top/"), result
                assert len(calls) == 2, calls
        finally:
            update._git_checkout, update._download, update._extract_zip = saved

    def backoff():
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "last_apply.json"
            path.write_text(json.dumps({"status": "error", "retry_after": (datetime.now(timezone.utc) +
                             timedelta(minutes=30)).isoformat()}), encoding="utf-8")
            saved = update.LAST_APPLY
            update.LAST_APPLY = path
            try:
                assert update._apply_backoff(types.SimpleNamespace(force=False)) is True
                assert update._apply_backoff(types.SimpleNamespace(force=True)) is False
            finally:
                update.LAST_APPLY = saved

    def status_json():
        saved = (update.MANIFEST_PATH, update.STATE_PATH, update.LAST_APPLY, update.HOLD_PATH)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest = root / "update.json"
            manifest.write_text(json.dumps(VALID), encoding="utf-8")
            state = root / "state.json"
            state.write_text(json.dumps({"result": "current", "checked_at": "2026-11-01T00:00:00Z"}),
                             encoding="utf-8")
            last = root / "last_apply.json"
            last.write_text(json.dumps({"status": "ok", "version": "1.0.0"}), encoding="utf-8")
            hold = root / "hold.json"
            hold.write_text(json.dumps({"version": "1.1.0"}), encoding="utf-8")
            update.MANIFEST_PATH, update.STATE_PATH, update.LAST_APPLY, update.HOLD_PATH = manifest, state, last, hold
            try:
                out = io.StringIO()
                with contextlib.redirect_stdout(out):
                    assert update.status(types.SimpleNamespace(json=True)) == 0
                data = json.loads(out.getvalue())
                assert {"local", "check", "last_apply", "hold"} <= set(data), data
                assert data["hold"]["version"] == "1.1.0"
            finally:
                update.MANIFEST_PATH, update.STATE_PATH, update.LAST_APPLY, update.HOLD_PATH = saved

    def helper_flow():
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            helper = root / "helper.py"
            helper.write_text(update.HELPER, encoding="utf-8")

            def make_skill(path, version, rc=0):
                (path / "references").mkdir(parents=True)
                (path / "references" / "update.json").write_text(json.dumps({"version": version}),
                                                                 encoding="utf-8")
                (path / "scripts").mkdir(parents=True)
                (path / "scripts" / "test_docs.py").write_text(f"raise SystemExit({rc})\n", encoding="utf-8")

            def run(skill, staging, backup, expected, mode="apply"):
                child = subprocess.Popen([sys.executable, "-c", "pass"])
                child.wait()
                log = root / f"log-{mode}-{expected or 'none'}.json"
                command = [sys.executable, str(helper), "--parent", str(child.pid), "--skill", str(skill),
                           "--staging", str(staging), "--backup", str(backup), "--log", str(log),
                           "--mode", mode, "--expected-version", expected]
                proc = subprocess.run(command, capture_output=True, text=True, encoding="utf-8",
                                      errors="replace", timeout=30)
                return proc.returncode, json.loads(log.read_text(encoding="utf-8")) if log.exists() else {}

            # success
            skill = root / "skill-ok"; staging = root / "staging-ok" / "skill"
            make_skill(skill, "1.0.0"); make_skill(staging, "1.1.0")
            backup = root / "backups" / "skill.bak-ok"
            rc, result = run(skill, staging, backup, "1.1.0")
            assert rc == 0 and result.get("status") == "ok", (rc, result)
            assert json.loads((skill / "references" / "update.json").read_text(encoding="utf-8"))["version"] == "1.1.0"
            assert backup.is_dir() and not (skill / ".state" / "hold.json").exists()
            last = json.loads((skill / ".state" / "last_apply.json").read_text(encoding="utf-8"))
            assert last["status"] == "ok" and last["version"] == "1.1.0"

            # test_docs failure -> restore + hold
            skill = root / "skill-fail"; staging = root / "staging-fail" / "skill"
            make_skill(skill, "1.0.0"); make_skill(staging, "1.1.0", rc=1)
            backup = root / "backups" / "skill.bak-fail"
            rc, result = run(skill, staging, backup, "1.1.0")
            assert rc == 1 and result.get("status") == "error", (rc, result)
            assert json.loads((skill / "references" / "update.json").read_text(encoding="utf-8"))["version"] == "1.0.0"
            hold = json.loads((skill / ".state" / "hold.json").read_text(encoding="utf-8"))
            assert hold["version"] == "1.1.0", hold

            # expected version mismatch -> restore + hold
            skill = root / "skill-mismatch"; staging = root / "staging-mismatch" / "skill"
            make_skill(skill, "1.0.0"); make_skill(staging, "1.1.0")
            backup = root / "backups" / "skill.bak-mismatch"
            rc, result = run(skill, staging, backup, "1.2.0")
            assert rc == 1 and result.get("status") == "error", (rc, result)
            assert json.loads((skill / "references" / "update.json").read_text(encoding="utf-8"))["version"] == "1.0.0"

            # rollback restores backup and holds the bad version
            skill = root / "skill-rollback"; staging = root / "staging-rollback" / "skill"
            make_skill(skill, "1.0.0"); make_skill(staging, "1.1.0")
            backup = root / "backups" / "skill.bak-rollback"
            rc, result = run(skill, staging, backup, "1.1.0")
            assert rc == 0 and result.get("status") == "ok", (rc, result)
            rc, result = run(skill, Path(""), backup, "", mode="rollback")
            assert rc == 0 and result.get("status") == "ok", (rc, result)
            assert json.loads((skill / "references" / "update.json").read_text(encoding="utf-8"))["version"] == "1.0.0"
            hold = json.loads((skill / ".state" / "hold.json").read_text(encoding="utf-8"))
            assert hold["version"] == "1.1.0", hold

    def zip_extract():
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            archive = root / "repo.zip"
            with zipfile.ZipFile(archive, "w") as zf:
                top = "foreman-master/"
                zf.writestr(top + VALID["path"] + "/SKILL.md", "---\nname: photocraft\n---\n")
                zf.writestr(top + VALID["path"] + "/references/update.json", "{}")
            target = root / "staging"
            update._extract_zip(archive, target, VALID["path"])
            assert (target / "SKILL.md").is_file()
            assert (target / "references" / "update.json").is_file()

    def cache():
        state = {"checked_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
                 "local_version": VALID["version"], "local_fingerprint": update._fingerprint(), "result": "current"}
        assert update._cached(dict(VALID), state) is True
        assert update._cached(dict(VALID, version="9.9.9"), state) is False

    for name, fn in [
        ("version keys", versions),
        ("manifest validation", manifest),
        ("GitHub URLs", urls),
        ("mirror URLs", mirrors),
        ("TTL bounds", ttl),
        ("unknown negative cache", unknown_cache),
        ("unknown state backoff", unknown_write),
        ("local manifest fetch", fetch_local),
        ("fallback order", fallback_order),
        ("apply backoff", backoff),
        ("status json", status_json),
        ("helper success/failure/rollback", helper_flow),
        ("ZIP extraction", zip_extract),
        ("cache freshness", cache),
    ]:
        check(name, fn)

    failed = [(name, detail) for name, detail in checks if detail]
    for name, detail in checks:
        print(f"{'FAIL' if detail else 'PASS'}  {name}" + (f": {detail}" if detail else ""))
    print(f"\n{len(checks) - len(failed)} passed, {len(failed)} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
