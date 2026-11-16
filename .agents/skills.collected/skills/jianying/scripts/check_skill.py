#!/usr/bin/env python3
"""Static checks for the jianying skill.

    python scripts/check_skill.py
    python scripts/check_skill.py --json
    python scripts/check_skill.py --self-test

Checks frontmatter, required files, Python syntax, Markdown links, JSON assets,
and accidental credential keys. It does not launch 剪映 and does not execute any
draft, export, or subtitle command.
"""

from __future__ import annotations

import contextlib
import io
import json
import re
import subprocess
import sys
from functools import partial
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

ROOT = Path(__file__).resolve().parent.parent
SKILL = ROOT / "SKILL.md"
REQUIRED = [
    "SKILL.md",
    "assets/audio_material.json",
    "assets/draft_base.json",
    "assets/draft_meta_base.json",
    "assets/text_material.json",
    "assets/video_material.json",
    "references/plan-schema.md",
    "references/draft-format.md",
    "references/bridge-protocol.md",
    "references/troubleshooting.md",
    "references/limits.md",
    "references/upstream.md",
    "references/maintenance.md",
    "references/version.json",
    "scripts/jy.py",
    "scripts/jylib/__init__.py",
    "scripts/jylib/draft.py",
    "scripts/jylib/env.py",
    "scripts/jylib/index.py",
    "scripts/jylib/media.py",
    "scripts/jylib/bridge.py",
    "scripts/jylib/errors.py",
    "scripts/subtitles/cli.py",
    "scripts/subtitles/draft_list.py",
    "scripts/subtitles/jy_common.py",
    "scripts/subtitles/probe.py",
    "scripts/subtitles/srt.py",
    "scripts/subtitles/burn.py",
    "scripts/check_skill.py",
    "scripts/check_docs.py",
    "scripts/probe_gotchas.py",
    "scripts/run_examples.py",
    "scripts/requirements.txt",
    "scripts/test_skill.py",
    "examples/plan_basic.json",
    "examples/plan_vertical.json",
    "examples/ops_example.json",
    "examples/README.md",
    "examples/01-build-text-draft.py",
    "examples/02-srt-build-check.py",
    "examples/03-validate-example-plans.py",
    "examples/04-media-build.py",
]
DANGEROUS_KEYS = {
    "token", "cookie", "cookies", "authorization", "localServerToken",
    "CUSTOM_AGENT_SERVER_TOKEN", "JIANYING_AGENT_RUNTIME_TOKEN", "accountScope",
}
SKIP_PARTS = {"__pycache__", ".ruff_cache", ".git", ".jianying-backups"}
LINK_RE = re.compile(r"\[[^\]]*\]\(([^)]+)\)")
DATE_RE = re.compile(r"^\d{4}-(0[1-9]|1[0-2])-(0[1-9]|[12]\d|3[01])$")
SEMVER_RE = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$")


def parse_frontmatter(text: str) -> dict[str, str]:
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}
    result = {}
    for line in lines[1:]:
        if line.strip() == "---":
            return result
        if ":" not in line or line.lstrip().startswith("#"):
            continue
        key, value = line.split(":", 1)
        result[key.strip()] = value.strip()
    return {}


def strip_fences(text: str) -> str:
    return re.sub(r"```.*?```", "", text, flags=re.S)


def iter_files(pattern: str):
    for path in sorted(ROOT.glob(pattern)):
        if any(part in SKIP_PARTS for part in path.parts):
            continue
        if path.is_file():
            yield path


def walk_keys(value, path="$"):
    if isinstance(value, dict):
        for key, child in value.items():
            yield key, f"{path}.{key}"
            yield from walk_keys(child, f"{path}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from walk_keys(child, f"{path}[{index}]")


def _record(checks: list[tuple[str, bool, str]], failures: list[str],
            name: str, ok: bool, detail: str = "") -> None:
    checks.append((name, ok, detail))
    if not ok:
        failures.append(f"{name}: {detail}" if detail else name)


def _make_record(checks: list[tuple[str, bool, str]], failures: list[str]):
    """main 与 self-test 共用同一条绑定；变异掉它时必须让自检变红。"""
    return partial(_record, checks, failures)


def _summary(checks: list[tuple[str, bool, str]], failures: list[str],
             as_json: bool) -> int:
    if as_json:
        print(json.dumps({
            "ok": not failures,
            "checks": len(checks),
            "failed": len(failures),
            "failed_checks": failures,
        }, ensure_ascii=False, indent=2))
    else:
        for name, ok, detail in checks:
            if not ok:
                print(f"FAIL  {name}: {detail}")
        print(f"{len(checks) - len(failures)} passed, {len(failures)} failed")
        if failures:
            print("检查失败：")
            for failure in failures:
                print(f"- {failure}")
    return exit_code(not failures)


def exit_code(ok: bool) -> int:
    """自测分支和汇总共用同一条布尔→退出码映射。"""
    return 0 if ok else 1


def self_test() -> tuple[bool, int, list[str]]:
    """校准检查器自身：frontmatter / 正则 / 链接 / 敏感键遍历 / 失败接线。"""
    checks = []

    def check(name: str, condition: bool) -> None:
        checks.append((name, condition))

    front = parse_frontmatter("---\nname: self-test\ndescription: sample\n---\n")
    check("frontmatter", front.get("name") == "self-test")
    check("semver", bool(SEMVER_RE.fullmatch("1.2.3")))
    check("semver_negative",
          not bool(SEMVER_RE.fullmatch("1.2")) and
          not bool(SEMVER_RE.fullmatch("1.2.3.4")) and
          not bool(SEMVER_RE.fullmatch("v1.2.3")) and
          not bool(SEMVER_RE.fullmatch("1.2.3-beta")) and
          not bool(SEMVER_RE.fullmatch("1.2.3+build1")) and
          not bool(SEMVER_RE.fullmatch("01.2.3")))
    check("date", bool(DATE_RE.fullmatch("2026-11-14")) and
          not bool(DATE_RE.fullmatch("2026-13-40")))
    check("link", LINK_RE.findall("[x](a.md)") == ["a.md"])
    check("sensitive-key", any(key == "token" for key, _ in
                               walk_keys({"a": {"token": 1}})))

    # 失败汇总与退出码接线：binding 走 _make_record，退出码在子进程里验，
    # 避免 exit_code 自己坏掉时只得到“信封 ok:false 但进程 exit 0”。
    fake_checks: list[tuple[str, bool, str]] = []
    fake_failures: list[str] = []
    record = _make_record(fake_checks, fake_failures)
    record("fake-failure", False, "known")
    check("record-binding", bool(fake_checks) and bool(fake_failures))
    with contextlib.redirect_stdout(io.StringIO()) as captured:
        code = _summary(fake_checks, fake_failures, True)
    payload = json.loads(captured.getvalue())
    check("summary-envelope", payload.get("ok") is False and payload.get("failed") == 1)
    check("failure-exit-code", code == 1)

    script = (
        f"import sys; sys.path.insert(0, {str(Path(__file__).resolve().parent)!r}); "
        "import check_skill; "
        "sys.exit(0 if (check_skill.exit_code(True) == 0 and "
        "check_skill.exit_code(False) == 1) else 1)"
    )
    try:
        child = subprocess.run([sys.executable, "-c", script], capture_output=True,
                               text=True, encoding="utf-8", errors="replace", timeout=30)
        exit_ok = child.returncode == 0
    except (OSError, subprocess.SubprocessError):
        # 受限环境可能禁止创建子进程；自检应报告失败而不是抛 traceback。
        exit_ok = False
    check("exit-code-subprocess", exit_ok)
    failed = [name for name, ok in checks if not ok]
    return all(ok for _, ok in checks), len(checks), failed


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if "--self-test" in argv:
        ok, count, failed = self_test()
        print(json.dumps({"ok": ok, "checks": count, "self_test": True,
                          "failed": len(failed), "failed_checks": failed},
                         ensure_ascii=False, indent=2))
        # 自检分支不经过 exit_code：exit_code 自己坏掉时仍要能用进程退出码报警。
        return 0 if ok else 1
    as_json = "--json" in argv
    failures: list[str] = []
    checks: list[tuple[str, bool, str]] = []

    record = _make_record(checks, failures)

    for relative in REQUIRED:
        path = ROOT / relative
        record(f"required:{relative}", path.is_file(), "missing")

    # 案例清单不能只锁 01–04：磁盘、README、runner 三处必须同集合。
    example_dir = ROOT / "examples"
    example_files = sorted(path.name for path in example_dir.glob("[0-9][0-9]-*.py"))
    readme = example_dir / "README.md"
    listed = []
    if readme.is_file():
        listed = re.findall(r"^\|\s*`([0-9][0-9]-[^`]+\.py)`",
                            readme.read_text("utf-8"), re.MULTILINE)
    record("examples:files-vs-README",
           sorted(listed) == example_files,
           f"disk={example_files} readme={sorted(listed)}")
    record("examples:non-empty", bool(example_files), "no numbered example")

    if SKILL.is_file():
        text = SKILL.read_text("utf-8")
        front = parse_frontmatter(text)
        record("frontmatter", bool(front), "missing frontmatter")
        for key in ("name", "description", "when_to_use", "version", "updated"):
            record(f"frontmatter:{key}", bool(front.get(key)), "missing or empty")
        record("name matches directory", front.get("name") == ROOT.name,
               f"{front.get('name')!r} != {ROOT.name!r}")
        record("version semver", bool(SEMVER_RE.fullmatch(front.get("version", ""))),
               front.get("version", ""))
        record("updated date", bool(DATE_RE.fullmatch(front.get("updated", ""))),
               front.get("updated", ""))
        record("description length", len(front.get("description", "")) >= 40,
               "too short to route reliably")

    for path in iter_files("**/*.md"):
        text = strip_fences(path.read_text("utf-8"))
        for raw in LINK_RE.findall(text):
            target = raw.strip()
            if target.startswith(("http://", "https://", "mailto:", "#")):
                continue
            target = target.split("#", 1)[0].strip()
            if not target:
                continue
            resolved = (path.parent / target).resolve()
            record(f"link:{path.relative_to(ROOT)} -> {target}", resolved.exists(), "missing")

    if SKILL.is_file():
        skill_text = SKILL.read_text("utf-8")
        for path in sorted((ROOT / "references").glob("*.md")):
            relative = path.relative_to(ROOT).as_posix()
            record(f"reference linked:{relative}", relative in skill_text,
                   "not linked from SKILL.md")

    for path in iter_files("**/*.py"):
        try:
            compile(path.read_text("utf-8"), str(path), "exec")
        except (OSError, SyntaxError, UnicodeDecodeError) as exc:
            record(f"python:{path.relative_to(ROOT)}", False, str(exc))
        else:
            record(f"python:{path.relative_to(ROOT)}", True)

    for path in iter_files("**/*.json"):
        try:
            data = json.loads(path.read_text("utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            record(f"json:{path.relative_to(ROOT)}", False, str(exc))
            continue
        record(f"json:{path.relative_to(ROOT)}", True)
        bad = [(key, where) for key, where in walk_keys(data)
               if key in DANGEROUS_KEYS]
        record(f"no credential keys:{path.relative_to(ROOT)}", not bad,
               ", ".join(f"{key} at {where}" for key, where in bad))

    for relative in ("examples/plan_basic.json", "examples/plan_vertical.json"):
        path = ROOT / relative
        if not path.is_file():
            continue
        try:
            data = json.loads(path.read_text("utf-8"))
        except json.JSONDecodeError:
            continue
        record(f"plan schema:{relative}", data.get("schema") == "jianying-plan/v1",
               f"schema={data.get('schema')!r}")
        record(f"plan tracks:{relative}", isinstance(data.get("tracks"), list) and
               bool(data["tracks"]), "tracks must be a non-empty array")

    ops_path = ROOT / "examples/ops_example.json"
    if ops_path.is_file():
        try:
            ops = json.loads(ops_path.read_text("utf-8")).get("ops")
        except json.JSONDecodeError:
            ops = None
        record("ops example", isinstance(ops, list) and bool(ops),
               "ops must be a non-empty array")

    subtitle_help = (ROOT / "scripts" / "subtitles" / "cli.py")
    if subtitle_help.is_file():
        text = subtitle_help.read_text("utf-8")
        record("subtitle entry naming", "剪映字幕与草稿辅助入口" in text,
               "USAGE does not describe the auxiliary entry")

    return _summary(checks, failures, as_json)


if __name__ == "__main__":
    raise SystemExit(main())
