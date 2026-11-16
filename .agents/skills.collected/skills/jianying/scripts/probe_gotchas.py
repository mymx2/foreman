#!/usr/bin/env python3
"""可执行的「踩坑探针」：把 SKILL.md / Gotchas 里的关键约束变成离线可跑的检查。

    python scripts/probe_gotchas.py            # 跑全部探针
    python scripts/probe_gotchas.py --list     # 只列名字
    python scripts/probe_gotchas.py unc srt    # 只跑名字含这些词的
    python scripts/probe_gotchas.py --allow-skip  # 允许 skip 不算失败

每个探针独立、离线、不启动剪映、不写用户草稿；临时目录用完即清。
输出 JSON 信封 {schema, command, ok, data:{probes,passed,failed,skipped}, error}。
退出码：0 = 没有 FAIL；1 = 有 FAIL；2 = 用法/环境错误。
"""
from __future__ import annotations

import argparse
import importlib
import json
import os
import subprocess
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
JY = SCRIPTS / "jy.py"
sys.path.insert(0, str(SCRIPTS))

PROBES: list[tuple[str, object]] = []


def probe(name):
    def deco(fn):
        PROBES.append((name, fn))
        return fn
    return deco


def _ok(evidence):
    return {"status": "ok", "evidence": evidence}


def _fail(evidence):
    return {"status": "FAIL", "evidence": evidence}


def _skip(evidence):
    return {"status": "skip", "evidence": evidence}


def _run_build(plan: dict, work: Path) -> tuple[dict, Path]:
    p = work / "plan.json"
    p.write_text(json.dumps(plan, ensure_ascii=False), "utf-8")
    out = work / "draft"
    proc = subprocess.run([sys.executable, str(JY), "build", "--plan", str(p), "--out", str(out)],
                          capture_output=True, text=True, encoding="utf-8", errors="replace")
    try:
        payload = json.loads(proc.stdout)
    except ValueError:
        payload = {"ok": False, "error": {"code": "PARSE_FAIL"}, "raw": proc.stdout[:300]}
    return payload, out


BASE_PLAN = {"schema": "jianying-plan/v1", "name": "probe",
             "canvas": {"width": 640, "height": 360, "fps": 30}}


@probe("utf8-stdout")
def _utf8_stdout():
    """中文 Windows（cp936）下 jy.py 的 JSON 仍必须是合法 UTF-8。"""
    env = dict(os.environ, PYTHONUTF8="0", PYTHONIOENCODING="cp936")
    proc = subprocess.run([sys.executable, str(JY), "inspect", str(SCRIPTS / "_no_such_draft_")],
                          capture_output=True, env=env)
    try:
        text = proc.stdout.decode("utf-8", errors="strict")
        payload = json.loads(text)
    except (UnicodeDecodeError, ValueError) as exc:
        return _fail(f"cp936 环境下输出不是合法 UTF-8 JSON: {exc}")
    code = (payload.get("error") or {}).get("code")
    return _ok({"bytes": len(proc.stdout), "error_code": code, "strict_utf8": True})


@probe("unc-rejected")
def _unc_rejected():
    """素材/字幕路径必须拒绝 UNC，主链路与字幕链路都要拦。"""
    media = importlib.import_module("jylib.media")
    common = importlib.import_module("subtitles.jy_common")
    unc = chr(92) * 2 + "host" + chr(92) + "share" + chr(92) + "a.mp4"
    hits = []
    try:
        media.local_path(unc)
        return _fail("jylib.media.local_path 接受了 UNC")
    except Exception as exc:
        hits.append(getattr(exc, "code", type(exc).__name__))
    try:
        common.local_path(unc)
        return _fail("subtitles.jy_common.local_path 接受了 UNC")
    except Exception as exc:
        hits.append(getattr(exc, "code", type(exc).__name__))
    return _ok({"rejected_by": hits, "unc": unc})


@probe("init-present")
def _init_present():
    """jylib 必须是真包（__init__.py 存在），否则干净安装会缺模块。"""
    init = SCRIPTS / "jylib" / "__init__.py"
    if not init.is_file():
        return _fail("缺少 scripts/jylib/__init__.py")
    return _ok({"path": str(init.relative_to(ROOT))})


@probe("burn-whole-name")
def _burn_whole_name():
    """烧录白名单校验整个文件名（含扩展名），扩展名里的 : ; ' [ 也要触发临时复制。"""
    burn = importlib.import_module("subtitles.burn")
    cases = {"clean.srt": False, "x.srt:evil": True, "a'b.srt": True,
             "a[1].srt": True, "with space.srt": True,
             "x.srt;evil": True, "x.srt=evil": True, "x.srt\\evil": True,
             "x.srt\"evil": True, "x.srt,evil": True}
    bad = {n: burn.needs_temp_copy(n) for n, want in cases.items()
           if burn.needs_temp_copy(n) != want}
    if bad:
        return _fail(f"白名单判定不符: {bad}")
    checked = list(cases)
    extension_chars_covered = all(
        burn.needs_temp_copy(n) for n in checked if n != "clean.srt")
    return _ok({"checked": checked, "extension_chars_covered": extension_chars_covered})


@probe("srt-zero-cue")
def _srt_zero_cue():
    """总时长平摊不足 1ms 时必须报 total-too-small，不能产出零时长字幕。"""
    srt = importlib.import_module("subtitles.srt")
    try:
        srt.allocate(["短"], 0.0005, gap=0.0)
    except srt.SrtError as exc:
        if exc.code == "total-too-small":
            return _ok({"code": exc.code})
        return _fail(f"期望 total-too-small，实际 {exc.code}")
    return _fail("过短总时长未被拒绝")


@probe("keyframe-negative")
def _keyframe_negative():
    """负关键帧时间必须是 VALIDATION，而不是 INTERNAL 或静默通过。"""
    plan = dict(BASE_PLAN, tracks=[{"type": "text", "segments": [
        {"text": "hi", "start": 0, "duration": 1,
         "keyframes": {"scale": [[-1, 1.0], [0, 1.0]]}}]}])
    with tempfile.TemporaryDirectory() as td:
        payload, _ = _run_build(plan, Path(td))
    error = payload.get("error") or {}
    code = error.get("code")
    field = (error.get("details") or {}).get("field")
    if code == "VALIDATION" and field == "time":
        return _ok({"code": code, "field": field})
    return _fail(f"期望 VALIDATION/time，实际 {code}/{field}")


@probe("validation-not-internal")
def _validation_not_internal():
    """非数字 duration 必须落到 VALIDATION，不能掉进 INTERNAL 兜底。"""
    plan = dict(BASE_PLAN, tracks=[{"type": "text", "segments": [
        {"text": "hi", "start": 0, "duration": "abc"}]}])
    with tempfile.TemporaryDirectory() as td:
        payload, _ = _run_build(plan, Path(td))
    code = (payload.get("error") or {}).get("code")
    if code == "VALIDATION":
        return _ok({"code": code})
    return _fail(f"期望 VALIDATION，实际 {code}")


@probe("staging-cleanup")
def _staging_cleanup():
    """build 失败后不留 .tmp-build-* 暂存目录，也不留半成品草稿。"""
    plan = dict(BASE_PLAN, tracks=[{"type": "image", "segments": [
        {"path": "_no_such_media_.png", "start": 0, "duration": 1}]}])
    with tempfile.TemporaryDirectory() as td:
        work = Path(td)
        payload, out = _run_build(plan, work)
        leftovers = [p.name for p in work.iterdir() if p.name.startswith(".tmp-build-")]
        if leftovers:
            return _fail(f"失败后残留暂存: {leftovers}")
        if out.exists():
            return _fail("失败后仍留下半成品草稿目录")
    return _ok({"error_code": (payload.get("error") or {}).get("code"), "leftovers": []})


@probe("index-id-consistent")
def _index_id_consistent():
    """合并索引时保留草稿当前 draft_id，不回填索引旧值。"""
    index_mod = importlib.import_module("jylib.index")
    index = {"all_draft_store": [{"draft_fold_path": "P", "draft_id": "OLD", "draft_name": "x"}],
             "draft_ids": 1}
    entry = {"draft_fold_path": "P", "draft_id": "NEW", "draft_name": "x"}
    new_index, _, _, action, _ = index_mod._merge_index(index, entry)
    merged_id = new_index["all_draft_store"][0]["draft_id"]
    if action == "update" and merged_id == "NEW":
        return _ok({"action": action, "draft_id": merged_id})
    return _fail(f"action={action} draft_id={merged_id}（期望 update/NEW）")


@probe("ffmpeg-honesty")
def _ffmpeg_honesty():
    """ffmpeg 能力探测要诚实：自带 ffmpeg 不能烧字幕时必须标 burn_in_available=False。"""
    common = importlib.import_module("subtitles.jy_common")
    try:
        result = common.resolve_ffmpeg()
    except Exception as exc:
        return _skip(
            f"无可用 ffmpeg: {getattr(exc, 'code', type(exc).__name__)}；"
            "本环境不覆盖 burn_in_available 断言")
    chosen = result.get("chosen") or {}
    if not chosen.get("path"):
        return _skip("环境没有 ffmpeg；本环境不覆盖 burn_in_available 断言")
    reported = result.get("burn_in_available")
    expected = bool(chosen.get("subtitle_burn_in"))
    try:
        filters = subprocess.run(
            [str(chosen["path"]), "-hide_banner", "-filters"],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=20,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return _fail(f"无法运行所选 ffmpeg 的 -filters：{type(exc).__name__}: {exc}")
    if filters.returncode != 0:
        return _fail(f"所选 ffmpeg -filters 退出 {filters.returncode}")
    names = common.filter_names((filters.stdout or "") + "\n" + (filters.stderr or ""))
    measured = "subtitles" in names
    mismatches = []
    if expected != measured:
        mismatches.append("recorded")
    if bool(reported) != measured:
        mismatches.append("reported")
    if mismatches:
        return _fail(
            f"独立 -filters 实测不一致（{'、'.join(mismatches)}）："
            f"recorded={expected!r}, reported={reported!r}, measured={measured!r}")
    return _ok({"source": chosen.get("source"),
                "burn_in_available": reported,
                "expected_from_libass": expected,
                "measured_subtitles_filter": measured})


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("filters", nargs="*", help="只跑名字含这些词的探针")
    ap.add_argument("--list", action="store_true", help="只列探针名字")
    ap.add_argument("--allow-skip", action="store_true", help="skip 不计入失败")
    args = ap.parse_args()

    if args.list:
        for name, _ in PROBES:
            print(name)
        return 0

    selected = [(n, f) for n, f in PROBES
                if not args.filters or any(w in n for w in args.filters)]
    if not selected:
        print(json.dumps({"schema": "jianying-skill/v1", "command": "probe_gotchas",
                          "ok": False, "data": {}, "error": {"code": "NO_MATCH"}},
                         ensure_ascii=False))
        return 2

    results = []
    passed = failed = skipped = 0
    for name, fn in selected:
        try:
            res = fn()
        except Exception as exc:  # 探针自身异常也算 FAIL，保留现场
            res = _fail(f"{type(exc).__name__}: {exc}")
        res = {"name": name, **res}
        results.append(res)
        if res["status"] == "ok":
            passed += 1
        elif res["status"] == "skip":
            skipped += 1
        else:
            failed += 1

    ok = failed == 0 and (skipped == 0 or args.allow_skip)
    payload = {
        "schema": "jianying-skill/v1",
        "command": "probe_gotchas",
        "ok": ok,
        "data": {"probes": results, "passed": passed, "failed": failed, "skipped": skipped},
        "error": None if ok else {"code": "PROBE_FAILED",
                                  "message": f"{failed} failed, {skipped} skipped"},
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())