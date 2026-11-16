#!/usr/bin/env python3
"""文档↔代码一致性自检（离线，不启动剪映）。维护技能时跑。

    python scripts/check_docs.py            # 校验，输出 JSON 信封
    python scripts/check_docs.py --self-test  # 只跑内置自检

校验项：
  1. troubleshooting.md 两张错误码表里出现的每个 `error.code` 都能在脚本里找到；
  2. SKILL.md 入口表里写的每个 `jy.py <verb>` / `cli.py <verb>` 都是真实子命令；
  3. references/version.json 结构完整，且 app_baseline 与 limits.md 一致；
  4. SKILL.md Scripts 表引用的每个 scripts/ 文件都存在；
  5. 代码里新增的 UPPER_CODE / film_export_* / `"code": "..."` 字典字面量必须进 troubleshooting.md（反向漂移）；
  6. 版本基线自洽：app_baseline == supported.min、behavior_tested == supported.max、
     supported.min <= supported.max、skill_version == SKILL.md 的 version、
     references/history/ 的归档数 <= history_max。

退出码：0 = 一致；1 = 有 findings；2 = 自检失败或读取错误。
信封与 jy.py 一致：{schema, command, ok, data, error}。
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
import tempfile
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"

CODE_SHAPE = re.compile(r"^(?:[A-Z][A-Z0-9_]*|film_export_[a-z_]+|[a-z][a-z0-9]*(?:-[a-z0-9]+)*)$")
UPPER_CODE = re.compile(r'code="([A-Z][A-Z0-9_]*)"')
FILM_CODE = re.compile(r"film_export_[a-z_]+")
FILM_ANY = re.compile(r"FILM_EXPORT_[A-Z0-9_]+")
HYPHEN_CODE = re.compile(r'"([a-z][a-z0-9]*(?:-[a-z0-9]+)+)"')
DICT_CODE = re.compile(r'"code"\s*:\s*"([A-Za-z][A-Za-z0-9_-]*)"')
LOWER_CODE_CALLS = (
    re.compile(r'(?:SrtError|MediaError)\(\s*"([a-z][a-z0-9]*(?:-[a-z0-9]+)*)"'),
    re.compile(r'_fail\(\s*"([a-z][a-z0-9]*(?:-[a-z0-9]+)*)"'),
    re.compile(r'C\.fail\(\s*[^,]+,\s*"([a-z][a-z0-9]*(?:-[a-z0-9]+)*)"'),
    re.compile(r'code="([a-z][a-z0-9]*(?:-[a-z0-9]+)*)"'),
    # 元组形式 _fail(*problem) 的来源，例如 _capability_error 的 return。
    re.compile(r'return\s*\(\s*"([a-z][a-z0-9]*(?:-[a-z0-9]+)*)"'),
)
VERB_MENTION = re.compile(r"(?:jy\.py|cli\.py)\s+([a-z][a-z0-9.-]*)")
SCRIPT_REF = re.compile(r"`(scripts/[A-Za-z0-9_./-]+)`")
SKILL_VERSION = re.compile(r"^version:\s*(\S+)", re.MULTILINE)

# 兼容旧调用：实际豁免表由 references/version.json 的 undocumented_allow 提供。
UNDOCUMENTED_ALLOW = {"FAILED"}


def _py_files(scripts_dir: Path = SCRIPTS) -> list[Path]:
    return sorted(scripts_dir.rglob("*.py"))


def collect_codes(root: Path = SCRIPTS) -> set[str]:
    """脚本里出现过的所有码形 token（用于 unknown-code 与计数）。"""
    codes: set[str] = set()
    for path in _py_files(root):
        text = path.read_text("utf-8", errors="replace")
        codes.update(UPPER_CODE.findall(text))
        codes.update(FILM_CODE.findall(text))
        codes.update(FILM_ANY.findall(text))
        codes.update(HYPHEN_CODE.findall(text))
        codes.update(DICT_CODE.findall(text))
        for pattern in LOWER_CODE_CALLS:
            codes.update(pattern.findall(text))
    return codes


def collect_declared_codes(root: Path = SCRIPTS) -> set[str]:
    """脚本里实际声明为错误码的 token（反向检查只用这一层）。"""
    codes: set[str] = set()
    for path in _py_files(root):
        text = path.read_text("utf-8", errors="replace")
        codes.update(UPPER_CODE.findall(text))
        codes.update(FILM_CODE.findall(text))
        codes.update(FILM_ANY.findall(text))
        codes.update(DICT_CODE.findall(text))
        for pattern in LOWER_CODE_CALLS:
            codes.update(pattern.findall(text))
    return codes


def collect_verbs(root: Path = ROOT) -> tuple[set[str], set[str]]:
    """返回 (jy 子命令, 字幕 cli 动词)。"""
    scripts = root / "scripts"
    jy_text = (scripts / "jy.py").read_text("utf-8")
    jy_verbs = set(re.findall(r'add_parser\("([a-z][a-z0-9-]*)"', jy_text))
    cli_text = (scripts / "subtitles" / "cli.py").read_text("utf-8")
    block = cli_text.split("VERBS", 1)[1].split("}", 1)[0]
    cli_verbs = set(re.findall(r'"([a-z][a-z0-9.-]*)"\s*:', block))
    return jy_verbs, cli_verbs


def _table_codes(section: str) -> list[str]:
    """取 markdown 表格首列里形如错误码的反引号 token。"""
    out: list[str] = []
    for line in section.splitlines():
        if not line.lstrip().startswith("|"):
            continue
        cells = line.split("|")
        if len(cells) < 2:
            continue
        for token in re.findall(r"`([^`]+)`", cells[1]):
            if CODE_SHAPE.fullmatch(token):
                out.append(token)
    return out


def documented_codes(root: Path = ROOT) -> list[str]:
    text = (root / "references" / "troubleshooting.md").read_text("utf-8")
    main = text.split("| `error.code` |", 1)[-1].split("\n## ", 1)[0]
    sub = text.split("## 字幕工具", 1)[-1].split("\n## ", 1)[0]
    return _table_codes("| `error.code` |" + main) + _table_codes(sub)


def _undocumented_allow(root: Path = ROOT) -> set[str]:
    """豁免列表放在 version.json，避免新增兜底码时只改代码。"""
    try:
        data = json.loads((root / "references" / "version.json").read_text("utf-8"))
    except (OSError, ValueError):
        return set(UNDOCUMENTED_ALLOW)
    return set(data.get("undocumented_allow") or UNDOCUMENTED_ALLOW)


def undocumented_codes(declared: set[str], documented: set[str],
                       allow: set[str] | None = None) -> list[str]:
    """代码里声明的错误码、文档没有的；declared 已是收窄后的错误码集合。"""
    allow = UNDOCUMENTED_ALLOW if allow is None else allow
    return sorted(
        code for code in declared
        if code not in documented and code not in allow
    )


def _version_tuple(text: str) -> tuple[int, ...] | None:
    """`11.8.0` -> (11, 8, 0)。只取数字段，够用来比窗口上下限，不引依赖。"""
    parts = re.findall(r"\d+", str(text or ""))
    return tuple(int(part) for part in parts) if parts else None


def _frontmatter(text: str) -> str:
    match = re.match(r"^---\r?\n(.*?)\r?\n---", text or "", re.S)
    return match.group(1) if match else ""


def version_baseline_findings(version: dict, skill_text: str,
                              history_dir: Path | None = None,
                              root: Path | None = None) -> list[dict]:
    """version.json 内部自洽 + 与 SKILL.md frontmatter 对账。

    输入全部显式传入，self_test 可以喂伪造数据而不碰真实文件。
    """
    out: list[dict] = []
    supported = version.get("supported") or {}
    min_version = str(supported.get("min") or "")
    max_version = str(supported.get("max") or "")
    baseline = str(version.get("app_baseline") or "")
    behavior = str(version.get("behavior_tested") or "")

    if baseline and min_version and baseline != min_version:
        out.append({"kind": "version",
                    "detail": f"app_baseline {baseline} ≠ supported.min {min_version}"})
    if behavior and max_version and behavior != max_version:
        out.append({"kind": "version",
                    "detail": f"behavior_tested {behavior} ≠ supported.max {max_version}"})
    low, high = _version_tuple(min_version), _version_tuple(max_version)
    if low is None or high is None:
        if min_version or max_version:
            out.append({"kind": "version",
                        "detail": f"supported 版本号无法解析: {min_version!r} / {max_version!r}"})
    elif low > high:
        out.append({"kind": "version",
                    "detail": f"supported.min {min_version} 大于 supported.max {max_version}"})

    skill_version = str(version.get("skill_version") or "")
    if not skill_version:
        out.append({"kind": "version", "detail": "version.json 缺 skill_version"})
    else:
        found = SKILL_VERSION.search(_frontmatter(skill_text))
        if not found:
            out.append({"kind": "version", "detail": "SKILL.md frontmatter 缺 version"})
        elif found.group(1) != skill_version:
            out.append({"kind": "version",
                        "detail": f"skill_version {skill_version} ≠ SKILL.md version {found.group(1)}"})

    if not version.get("history_max"):
        out.append({"kind": "version", "detail": "version.json 缺 history_max"})
    if history_dir is not None:
        try:
            history_max = int(version.get("history_max") or 3)
        except (TypeError, ValueError):
            history_max = 3
        if not history_dir.is_dir():
            out.append({"kind": "version",
                        "detail": f"references/history 目录缺失: {history_dir}"})
        else:
            frozen = [p for p in history_dir.glob("*.md") if p.name != "README.md"]
            if len(frozen) > history_max:
                out.append({"kind": "version",
                            "detail": f"references/history 有 {len(frozen)} 份归档，超过 history_max={history_max}"})

    changelog = str(version.get("changelog") or "")
    if not changelog:
        out.append({"kind": "version", "detail": "version.json 缺 changelog"})
    elif root is not None:
        changelog_path = root / changelog
        if not changelog_path.is_file():
            out.append({"kind": "version",
                        "detail": f"changelog 文件不存在: {changelog}"})
        elif skill_version and f"## {skill_version}" not in changelog_path.read_text("utf-8"):
            out.append({"kind": "version",
                        "detail": f"changelog 缺少 {skill_version} 段落"})
    return out


def check(root: Path = ROOT) -> list[dict]:
    findings: list[dict] = []
    scripts = root / "scripts"
    declared = collect_declared_codes(scripts)
    documented = set(documented_codes(root))
    allow = _undocumented_allow(root)
    for code in sorted(documented):
        if code not in declared:
            findings.append({"kind": "unknown-code", "code": code,
                             "where": "references/troubleshooting.md"})

    # 反向漂移：代码里新增的真实错误码必须进文档；两侧都用声明码集，
    # 宽口径只用于展示，不能拿来放过文档里的假码。
    for code in undocumented_codes(declared, documented, allow):
        findings.append({"kind": "undocumented-code", "code": code,
                         "where": "scripts/ (missing from troubleshooting.md)"})

    jy_verbs, cli_verbs = collect_verbs(root)
    known_verbs = jy_verbs | cli_verbs
    skill = (root / "SKILL.md").read_text("utf-8")
    for verb in sorted(set(VERB_MENTION.findall(skill))):
        if verb not in known_verbs:
            findings.append({"kind": "unknown-verb", "verb": verb, "where": "SKILL.md"})

    vpath = root / "references" / "version.json"
    try:
        version = json.loads(vpath.read_text("utf-8"))
    except (OSError, ValueError) as exc:
        findings.append({"kind": "version", "detail": f"version.json 不可读: {exc}"})
        version = {}
    for key in ("app_baseline", "behavior_tested", "build_tested", "draft_format", "bridge"):
        if not version.get(key):
            findings.append({"kind": "version", "detail": f"version.json 缺 {key}"})
    supported = version.get("supported") or {}
    if not supported.get("min") or not supported.get("max"):
        findings.append({"kind": "version", "detail": "version.json supported.min/max 缺失"})
    limits = (root / "references" / "limits.md").read_text("utf-8")
    baseline = version.get("app_baseline", "")
    if baseline and baseline not in limits:
        findings.append({"kind": "version", "detail": f"limits.md 未提及基线 {baseline}"})

    findings.extend(version_baseline_findings(
        version, skill, root / "references" / "history", root=root))

    for rel in sorted(set(SCRIPT_REF.findall(skill))):
        target = root / rel
        exists = target.is_dir() if rel.endswith("/") else target.is_file()
        if not exists:
            findings.append({"kind": "missing-script", "path": rel, "where": "SKILL.md"})
    return findings


def self_test(*, include_live: bool = False) -> bool:
    """用伪造文档喂提取器，确认能抓出假码/假动词、放过真码。"""
    codes = collect_declared_codes()
    if "VALIDATION" not in codes or "film_export_token_invalid" not in codes:
        return False
    # 只认生产脚本里的码；不要用 test/probe 里也持有的字面量做存在性断言。
    production_only = "srt-" + "dropped" + "-blocks"
    if production_only not in codes:
        return False
    fake = "| `error.code` | x | y |\n|---|---|---|\n| `BOGUS_CODE_XYZ` | a | b |\n"
    if "BOGUS_CODE_XYZ" not in _table_codes(fake):
        return False
    if "BOGUS_CODE_XYZ" in codes:
        return False
    if "SELF_TEST_FAILED" not in codes:  # 字典字面量 `"code": "..."` 也要被采集
        return False
    jy_verbs, cli_verbs = collect_verbs()
    if "build" not in jy_verbs or "srt.check" not in cli_verbs:
        return False
    if "no-such-verb" in jy_verbs or "no-such-verb" in cli_verbs:
        return False
    if undocumented_codes({ "BRAND_NEW_" + "HIDDEN_CODE", "VALIDATION"},
                          {"VALIDATION"}) != ["BRAND_NEW_" + "HIDDEN_CODE"]:
        return False

    # 版本基线：喂伪造 version 数据（临时目录装 history），不碰真实文件。
    good = {"app_baseline": "11.8.0", "behavior_tested": "11.8.0",
            "supported": {"min": "11.8.0", "max": "11.8.0"},
            "skill_version": "1.2.0", "history_max": 3,
            "changelog": "references/changelog.md"}
    frontmatter = "---\nname: fake\nversion: 1.2.0\n---\n"
    if version_baseline_findings(good, frontmatter):
        return False
    baseline_drift = json.loads(json.dumps(good))
    baseline_drift["app_baseline"] = "11.7.0"
    if not any("app_baseline" in item.get("detail", "")
               for item in version_baseline_findings(baseline_drift, frontmatter)):
        return False
    behavior_drift = json.loads(json.dumps(good))
    behavior_drift["behavior_tested"] = "11.9.0"
    if not any("behavior_tested" in item.get("detail", "")
               for item in version_baseline_findings(behavior_drift, frontmatter)):
        return False
    body_only = "---\nname: fake\n---\n\n```\nversion: 1.2.0\n```\n"
    if not any("SKILL.md frontmatter 缺 version" == item.get("detail")
               for item in version_baseline_findings(good, body_only)):
        return False
    skill_drift = json.loads(json.dumps(good))
    skill_drift["skill_version"] = "9.9.9"
    if not any("skill_version" in item.get("detail", "")
               for item in version_baseline_findings(skill_drift, frontmatter)):
        return False
    no_version = version_baseline_findings(
        json.loads(json.dumps(good)), "---\nname: fake\n---\n")
    if not any("SKILL.md frontmatter 缺 version" == item.get("detail")
               for item in no_version):
        return False
    inverted = json.loads(json.dumps(good))
    inverted["app_baseline"] = "11.9.0"
    inverted["supported"] = {"min": "11.9.0", "max": "11.8.0"}
    if not any("大于" in item.get("detail", "")
               for item in version_baseline_findings(inverted, frontmatter)):
        return False
    try:
        with tempfile.TemporaryDirectory() as tmp:
            history = Path(tmp)
            for i in range(4):
                (history / f"0.{i}.md").write_text("# frozen\n", "utf-8")
            if not any("history_max" in item.get("detail", "")
                       for item in version_baseline_findings(good, frontmatter, history)):
                return False
            (history / "README.md").write_text("# index\n", "utf-8")
            (history / "0.3.md").unlink()
            if version_baseline_findings(good, frontmatter, history) != []:
                return False
    except OSError:
        return False

    # 活码漂移：在真实脚本副本里注入一个新码，check() 必须能报出来，
    # 而不是只在手写 set 上测纯函数。
    try:
        hidden = "BRAND_NEW_" + "HIDDEN_CODE"
        with tempfile.TemporaryDirectory() as tmp:
            tmp_root = Path(tmp)
            shutil.copytree(ROOT / "scripts", tmp_root / "scripts")
            shutil.copytree(ROOT / "references", tmp_root / "references")
            shutil.copy2(ROOT / "SKILL.md", tmp_root / "SKILL.md")
            injected = tmp_root / "scripts" / "subtitles" / "srt.py"
            injected.write_text(
                injected.read_text("utf-8") + f'\n# code="{hidden}"\n',
                "utf-8")
            findings = check(tmp_root)
            if not any(item.get("kind") == "undocumented-code"
                       and item.get("code") == hidden
                       for item in findings):
                return False
            # 端到端：临时副本里把 app_baseline 改成与 supported.min 不一致，check() 必须报。
            vpath = tmp_root / "references" / "version.json"
            drifted = json.loads(vpath.read_text("utf-8"))
            drifted["app_baseline"] = "11.7.0"
            vpath.write_text(json.dumps(drifted, ensure_ascii=False), "utf-8")
            findings = check(tmp_root)
            if not any(item.get("kind") == "version"
                       and item.get("detail", "").startswith("app_baseline 11.7.0")
                       for item in findings):
                return False
    except (OSError, shutil.Error):
        return False
    # --self-test 也要对真实仓库跑一遍，避免“仓库里的活码漂移只有 plain 模式变红”。
    if include_live and check():
        return False
    return True


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--self-test", action="store_true", help="只跑内置自检")
    args = ap.parse_args()

    if args.self_test:
        ok = self_test(include_live=True)
        print(json.dumps({"schema": "jianying-skill/v1", "command": "check_docs",
                          "ok": ok, "data": {"self_test": ok}, "error": None},
                         ensure_ascii=False))
        return 0 if ok else 2

    if not self_test():
        print(json.dumps({"schema": "jianying-skill/v1", "command": "check_docs",
                          "ok": False, "data": {}, "error": {"code": "SELF_TEST_FAILED"}},
                         ensure_ascii=False))
        return 2

    findings = check()
    payload = {
        "schema": "jianying-skill/v1",
        "command": "check_docs",
        "ok": not findings,
        "data": {
            # declared_codes 只数真实声明码；tokens 是宽口径，不能当错误码读。
            "declared_codes": len(collect_declared_codes()),
            "tokens": len(collect_codes()),
            "documented_codes": len(set(documented_codes())),
            "findings": findings,
        },
        "error": None if not findings else {"code": "DOC_CODE_MISMATCH",
                                            "message": f"{len(findings)} 处文档与代码不一致"},
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if not findings else 1


if __name__ == "__main__":
    raise SystemExit(main())