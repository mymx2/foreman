#!/usr/bin/env python3
"""Self-test for the version and history checks in find_cli.py and check_docs.py.

  python <skill-dir>/scripts/test_docs.py

No PhotoCraft install is needed: the tested helpers are pure functions.
Exit codes: 0 all checks passed, 1 one or more checks failed.
"""
from __future__ import annotations

import contextlib
import io
import json
import re
import sys
import tempfile
import types
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import check_docs  # noqa: E402
import find_cli  # noqa: E402


def _report(info, installed):
    saved = find_cli._read_version_file
    find_cli._read_version_file = lambda: info
    try:
        return find_cli._docs_report(installed)
    finally:
        find_cli._read_version_file = saved


def _write_version(root: Path, data) -> None:
    path = root / "references" / "version.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")


def main() -> int:
    checks = []

    def check(name, fn):
        try:
            fn()
        except AssertionError as exc:
            checks.append((name, str(exc)))
        else:
            checks.append((name, None))

    def versions():
        assert find_cli._version_tuple("0.18") == (0, 18, 0)
        assert find_cli._version_tuple("v0.18.0") == (0, 18, 0)
        assert find_cli._version_tuple("0.18.0-beta.1") == (0, 18, 0)
        assert find_cli._version_tuple("beta") is None
        assert find_cli._version_tuple(None) is None

    def range_rules():
        info = {"params_baseline": "0.14.0", "behavior_tested": "0.18.0",
                "supported": {"min": "0.14.0", "max": "0.18.0"}}
        assert _report(info, "photocraft-cli 0.18.1 (x)")[2] is None
        assert _report(info, "photocraft-cli 0.18.0 (x)")[2] is None
        assert _report(info, "photocraft-cli 0.19.0 (x)")[2] == "range"
        assert _report(info, "photocraft-cli 0.13.9 (x)")[2] == "range"

    def config_rules():
        assert _report(None, "photocraft-cli 0.18.0 (x)")[2] == "config"
        assert _report({"supported": ["0.14.0", "0.18.0"]}, "photocraft-cli 0.18.0 (x)")[2] == "config"
        assert _report({"supported": {"min": "0.18.0", "max": "0.14.0"}}, "photocraft-cli 0.18.0 (x)")[2] == "config"
        assert _report({"supported": {"min": "0.14.0", "max": "0.18.0"}}, "not-a-version")[2] == "config"

    def exit_codes():
        assert find_cli._docs_exit(None) == 0
        assert find_cli._docs_exit("config") == 4
        assert find_cli._docs_exit("range") == 3

    def real_version_file():
        info = find_cli._read_version_file()
        assert isinstance(info, dict), info
        for key in ("params_baseline", "behavior_tested", "supported", "history_max"):
            assert key in info, info

    def history_entries():
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            hist = root / "references" / "history"
            hist.mkdir(parents=True)
            for name in ("0.14.md", "0.10.md", "0.9.md", "0.18.md", "0.12.md"):
                (hist / name).write_text("# frozen\n", encoding="utf-8")
            status = check_docs.history_status(root, 5)
            assert status["ok"] is True and status["count"] == 5, status
            assert status["files"][0] == "0.9.md", status["files"]
            (hist / "0.20.md").write_text("# frozen\n", encoding="utf-8")
            assert check_docs.history_status(root, 5)["ok"] is False
            (hist / "notes.md").write_text("# frozen\n", encoding="utf-8")
            (hist / "partial.tmp").write_text("x", encoding="utf-8")
            (hist / "0.99.md").mkdir()
            status = check_docs.history_status(root, 5)
            assert status["bad"] == ["0.99.md", "notes.md", "partial.tmp"], status["bad"]

    def history_limit_file():
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_version(root, {"history_max": 3})
            assert check_docs.history_limit(root) == 3
            _write_version(root, {"history_max": 0})
            assert check_docs.history_limit(root) == 5
            (root / "references" / "version.json").write_text("{", encoding="utf-8")
            assert check_docs.history_limit(root) == 5

    def update_metadata():
        root = Path(__file__).resolve().parent.parent
        data = json.loads((root / "references" / "update.json").read_text(encoding="utf-8"))
        version_data = json.loads((root / "references" / "version.json").read_text(encoding="utf-8"))
        assert data["skill"] == "photocraft"
        assert re.fullmatch(r"\d+\.\d+\.\d+", data["version"]), data["version"]
        assert data["source"] and data["path"] and data["branch"]
        assert isinstance(data.get("check_interval_days"), int) and 3 <= data["check_interval_days"] <= 30
        assert data.get("severity") in ("normal", "security", "breaking")
        assert data.get("cli_supported") == version_data.get("supported"), data.get("cli_supported")
        text = (root / "SKILL.md").read_text(encoding="utf-8")
        front = text.split("---", 2)[1]
        version = re.search(r"^version:\s*(\S+)", front, re.M)
        updated = re.search(r"^updated:\s*(\S+)", front, re.M)
        assert version and version.group(1) == data["version"], (version, data["version"])
        assert updated and updated.group(1) == data["updated"], (updated, data["updated"])

    def version_metadata():
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            hist = root / "references" / "history"
            hist.mkdir(parents=True)
            (hist / "0.14.md").write_text("# 0.12 → 0.14 变更（冻结归档）\n", encoding="utf-8")
            _write_version(root, {"params_baseline": "0.14.0", "behavior_tested": "0.18.0",
                                  "supported": {"min": "0.14.0", "max": "0.18.0"}, "history_max": 5})
            upgrading = root / "references" / "upgrading.md"
            upgrading.write_text("# 0.14 → 0.18 升级指南\n", encoding="utf-8")
            assert check_docs.version_status(root)["ok"] is True, check_docs.version_status(root)
            upgrading.write_text("# 0.14 → 0.20 升级指南\n", encoding="utf-8")
            assert check_docs.version_status(root)["ok"] is False
            upgrading.unlink()
            assert check_docs.version_status(root)["ok"] is False
            _write_version(root, {"params_baseline": "0.14.0", "behavior_tested": "0.18.0",
                                  "supported": {"min": "0.14.0", "max": "0.20.0"}, "history_max": 5})
            upgrading.write_text("# 0.14 → 0.18 升级指南\n", encoding="utf-8")
            assert check_docs.version_status(root)["ok"] is False

    def metadata_edges():
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            hist = root / "references" / "history"
            hist.mkdir(parents=True)
            (hist / "0.14.md").write_text("# 0.12 → 0.14 变更（冻结归档）\n", encoding="utf-8")
            upgrading = root / "references" / "upgrading.md"
            upgrading.write_text("# 0.14 → 0.18 升级指南\n", encoding="utf-8")
            (root / "references" / "version.json").write_text("[]", encoding="utf-8")
            assert check_docs.version_status(root)["ok"] is False
            assert check_docs.history_limit(root) == 5
            _write_version(root, {"params_baseline": "0.18.0", "behavior_tested": "0.14.0",
                                  "supported": {"min": "0.18.0", "max": "0.14.0"}, "history_max": 5})
            assert check_docs.version_status(root)["ok"] is False
            _write_version(root, {"params_baseline": "0.14.0", "behavior_tested": "0.18.0",
                                  "supported": {"min": "0.14.0", "max": "0.18.0"}, "history_max": True})
            assert check_docs.version_status(root)["ok"] is False
            _write_version(root, {"params_baseline": "0.14.0", "behavior_tested": "0.18.0",
                                  "supported": {"min": "0.14.0", "max": "0.18.0"}, "history_max": 5})
            (hist / "0.18.md").write_text("# 0.16 → 0.18 变更（冻结归档）\n", encoding="utf-8")
            assert check_docs.version_status(root)["ok"] is False
            (hist / "0.18.md").unlink()
            (hist / "0.14.md").unlink()
            assert check_docs.version_status(root)["ok"] is False

    def main_flow():
        fake = Path(tempfile.gettempdir()) / "fake-photocraft-cli"
        saved = (find_cli.pclib.find_cli, find_cli.pclib.cli_version, find_cli.pclib.run_cli,
                 find_cli.pclib.cli_candidates, find_cli.pclib.setup_stdio, find_cli._read_version_file)
        info = {"params_baseline": "0.14.0", "behavior_tested": "0.18.0",
                "supported": {"min": "0.14.0", "max": "0.18.0"}, "history_max": 5}
        expected_docs = {"params_baseline": "0.14.0", "behavior_tested": "0.18.0",
                         "supported": {"min": "0.14.0", "max": "0.18.0"}}

        def run_case(version, version_info, *, registry_fail=False, registry_missing=False,
                     check=True, json_mode=True, cli_fail=False):
            find_cli.pclib.find_cli = lambda *a, **k: fake
            find_cli.pclib.cli_candidates = lambda *a, **k: []
            if cli_fail:
                def no_version(*a, **k):
                    raise find_cli.pclib.PcError("no version")
                find_cli.pclib.cli_version = no_version
            else:
                find_cli.pclib.cli_version = lambda *a, **k: version
            find_cli.pclib.setup_stdio = lambda: None
            find_cli._read_version_file = lambda: version_info
            if registry_fail:
                def fail(*a, **k):
                    raise find_cli.pclib.PcError("boom")
                find_cli.pclib.run_cli = fail
            elif registry_missing:
                find_cli.pclib.run_cli = lambda *a, **k: types.SimpleNamespace(stdout='[{"id": "file.open"}]')
            else:
                find_cli.pclib.run_cli = lambda *a, **k: types.SimpleNamespace(stdout='[{"id": "file.new"}]')
            argv = ["--check"] if check else []
            if json_mode:
                argv.append("--json")
            out, err = io.StringIO(), io.StringIO()
            with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                rc = find_cli.main(argv)
            data = json.loads(out.getvalue()) if json_mode else None
            return rc, data, err.getvalue()

        try:
            rc, data, _ = run_case("photocraft-cli 0.19.0", info)
            assert rc == 3 and data["docs_in_range"] is False and "docs_hint" in data, (rc, data)
            assert data["docs"] == expected_docs and set(data["docs"]) == set(expected_docs), data.get("docs")
            rc, _, _ = run_case("photocraft-cli 0.18.0", info, registry_fail=True)
            assert rc == 1, rc
            rc, data, _ = run_case("photocraft-cli 0.18.0", info, registry_missing=True)
            assert rc == 1 and data["registry_ok"] is False, (rc, data)
            rc, data, _ = run_case("photocraft-cli 0.18.0", info, cli_fail=True)
            assert rc == 1 and data.get("docs_unknown") and "docs_config_error" not in data, (rc, data)
            rc, data, _ = run_case("photocraft-cli 0.19.0", info, check=False)
            assert rc == 0 and "docs_in_range" not in data, (rc, data)
            rc, data, _ = run_case("photocraft-cli 0.18.0", None)
            assert rc == 4 and data["docs_in_range"] is False and "docs_config_error" in data, (rc, data)
            assert "docs" not in data, data
            rc, data, _ = run_case("photocraft-cli 0.18.0", info)
            assert rc == 0 and data["docs_in_range"] is True and data["docs"] == expected_docs, (rc, data)
            rc, _, err = run_case("photocraft-cli 0.19.0", info, json_mode=False)
            assert rc == 3 and "docs_in_range: False" in err and "docs hint:" in err, (rc, err)
            rc, _, err = run_case("photocraft-cli 0.18.0", None, json_mode=False)
            assert rc == 4 and "docs config error:" in err, (rc, err)
            bad_supported = {"params_baseline": "0.14.0", "behavior_tested": "0.18.0",
                             "supported": ["0.14.0", "0.18.0"]}
            rc, _, err = run_case("photocraft-cli 0.18.0", bad_supported, json_mode=False)
            assert rc == 4 and "supported invalid" in err, (rc, err)
        finally:
            (find_cli.pclib.find_cli, find_cli.pclib.cli_version, find_cli.pclib.run_cli,
             find_cli.pclib.cli_candidates, find_cli.pclib.setup_stdio, find_cli._read_version_file) = saved

    def history_chain_forward():
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            hist = root / "references" / "history"
            hist.mkdir(parents=True)
            (hist / "0.14.md").write_text("# 0.12 → 0.14 变更（冻结归档）\n", encoding="utf-8")
            (hist / "0.18.md").write_text("# 0.14 → 0.18 变更（冻结归档）\n", encoding="utf-8")
            _write_version(root, {"params_baseline": "0.18.0", "behavior_tested": "0.20.0",
                                  "supported": {"min": "0.18.0", "max": "0.20.0"}, "history_max": 5})
            (root / "references" / "upgrading.md").write_text("# 0.18 → 0.20 升级指南\n", encoding="utf-8")
            assert check_docs.version_status(root)["ok"] is True, check_docs.version_status(root)
            (hist / "0.18.md").write_text("# 0.14 → 0.18.3 变更（冻结归档）\n", encoding="utf-8")
            assert check_docs.version_status(root)["ok"] is False

    def check_docs_gate():
        saved = (check_docs.Baseline.load, check_docs.self_test)
        check_docs.Baseline.load = classmethod(lambda cls, cli=None: check_docs.Baseline([], [], {}))
        check_docs.self_test = lambda base: []

        def run(root):
            out, err = io.StringIO(), io.StringIO()
            with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                rc = check_docs.main(["--root", str(root), "--json"])
            return rc, out.getvalue(), err.getvalue()

        try:
            with tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                (root / "SKILL.md").write_text("plain\n", encoding="utf-8")
                refs = root / "references"
                refs.mkdir()
                _write_version(root, {"params_baseline": "0.14.0", "behavior_tested": "0.18.0",
                                      "supported": {"min": "0.14.0", "max": "0.18.0"}, "history_max": 5})
                (refs / "upgrading.md").write_text("# 0.14 → 0.18 升级指南\n", encoding="utf-8")
                hist = refs / "history"
                hist.mkdir()
                (hist / "0.14.md").write_text("# 0.12 → 0.14 变更（冻结归档）\n", encoding="utf-8")
                rc, out, err = run(root)
                assert rc == 0, (rc, out, err)
                for name, source, target in [
                    ("0.15", "0.14", "0.15"), ("0.16", "0.15", "0.16"), ("0.17", "0.16", "0.17"),
                    ("0.18", "0.17", "0.18"), ("0.19", "0.18", "0.19"),
                ]:
                    (hist / f"{name}.md").write_text(f"# {source} → {target} 变更（冻结归档）\n", encoding="utf-8")
                _write_version(root, {"params_baseline": "0.19.0", "behavior_tested": "0.20.0",
                                      "supported": {"min": "0.19.0", "max": "0.20.0"}, "history_max": 5})
                (refs / "upgrading.md").write_text("# 0.19 → 0.20 升级指南\n", encoding="utf-8")
                rc, _, _ = run(root)
                assert rc == 1, rc
                (hist / "0.14.md").unlink()
                rc, _, _ = run(root)
                assert rc == 0, rc
                (refs / "upgrading.md").write_text("# 0.19 → 0.21 升级指南\n", encoding="utf-8")
                rc, _, _ = run(root)
                assert rc == 1, rc
            with tempfile.TemporaryDirectory() as empty:
                rc, _, _ = run(Path(empty))
                assert rc == 1, rc
            with tempfile.TemporaryDirectory() as only_skill:
                (Path(only_skill) / "SKILL.md").write_text("plain\n", encoding="utf-8")
                rc, _, _ = run(Path(only_skill))
                assert rc == 1, rc
        finally:
            check_docs.Baseline.load, check_docs.self_test = saved

    for name, fn in [
        ("version parsing", versions),
        ("range rules (patch ignored)", range_rules),
        ("config errors", config_rules),
        ("exit codes", exit_codes),
        ("real version file", real_version_file),
        ("update metadata", update_metadata),
        ("main flow 0/1/3/4", main_flow),
        ("history count/order/names", history_entries),
        ("history_max from version.json", history_limit_file),
        ("version metadata consistency", version_metadata),
        ("version metadata edge cases", metadata_edges),
        ("history chain forward", history_chain_forward),
        ("check_docs gate 0/1", check_docs_gate),
    ]:
        check(name, fn)

    failed = [(name, detail) for name, detail in checks if detail]
    for name, detail in checks:
        print(f"{'FAIL' if detail else 'PASS'}  {name}" + (f": {detail}" if detail else ""))
    print(f"\n{len(checks) - len(failed)} passed, {len(failed)} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
