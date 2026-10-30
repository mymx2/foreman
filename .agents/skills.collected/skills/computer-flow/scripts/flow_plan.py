"""Declarative desktop workflow: YAML/JSON steps, resolved at runtime.

A plan describes *intent* (text, identifiers, business ids), never coordinates.
Each step is resolved against a fresh observation so window size, DPI and layout
can change between runs and between machines.
"""

import json
import re
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


class PlanError(RuntimeError):
    """Plan structure or a step's business assertion is invalid."""


@dataclass
class Target:
    text: str = ""
    match: str = "exact"
    region: tuple = None
    sources: list = field(default_factory=list)
    min_confidence: float = 0.85
    auto_id: str = ""


@dataclass
class Step:
    action: str
    target: Target = None
    value: str = ""
    expect: dict = field(default_factory=dict)
    wait: float = 1.5
    timeout: float = 30.0
    name: str = ""
    optional: bool = False
    # launch-only fields
    app: list = field(default_factory=list)
    path: str = ""
    exe: str = ""
    window: str = ""
    process: str = ""


def load_plan(path):
    path = Path(path)
    raw = path.read_text(encoding="utf-8")
    if path.suffix.lower() in (".yaml", ".yml"):
        try:
            import yaml
        except ImportError as exc:
            raise PlanError("YAML plans require PyYAML: pip install pyyaml") from exc
        data = yaml.safe_load(raw)
    else:
        data = json.loads(raw)
    if not isinstance(data, dict) or not isinstance(data.get("steps"), list):
        raise PlanError("plan must be a mapping with a 'steps' list")
    return data


_PLACEHOLDER = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}")


def substitute(value, variables):
    """Replace ${name} placeholders using plan variables.

    Any placeholder left standing after substitution is an unresolved variable:
    pasting the literal "${record_id}" into the target app is never useful and
    silently poisons downstream assertions, so it fails fast here.
    """
    if not isinstance(value, str):
        return value
    result = value
    for key, replacement in variables.items():
        result = result.replace("${" + key + "}", str(replacement))
    leftover = _PLACEHOLDER.search(result)
    if leftover:
        raise PlanError(
            f"unresolved variable ${{{leftover.group(1)}}} in {value!r}; "
            "pass it with --set name=value"
        )
    return result


def _normalize_target_text(text):
    """Keep plan-side text consistent with observation-side `_normalize`.

    Both sides must apply the same canonicalization, otherwise a plan that
    writes "查询 条件" (CJK with spaces, e.g. copied from an OCR dump) will
    never match the observed element whose label was collapsed to "查询条件".
    Imported lazily to avoid a circular import with desktop_observe.
    """
    from desktop_observe import _normalize

    return _normalize(text)


def parse_target(raw, variables):
    if raw is None:
        return None
    if isinstance(raw, Target):
        return raw
    if isinstance(raw, str):
        return Target(text=_normalize_target_text(substitute(raw, variables)))
    if not isinstance(raw, dict):
        raise PlanError(f"target must be a string or mapping, got {type(raw).__name__}")
    region = raw.get("region")
    if region is not None:
        if not isinstance(region, (list, tuple)) or len(region) != 4:
            raise PlanError(f"target.region must be four fractions: {region}")
        region = tuple(float(v) for v in region)
    if not raw.get("text") and not raw.get("auto_id"):
        raise PlanError("target needs at least one of 'text' or 'auto_id'")
    match = raw.get("match", "exact")
    if match not in ("exact", "suffix", "contains"):
        raise PlanError(f"unsupported match mode: {match}")
    return Target(
        text=_normalize_target_text(substitute(raw.get("text", ""), variables)),
        match=match,
        region=region,
        sources=list(raw.get("sources", raw.get("source", []) or [])),
        min_confidence=float(raw.get("min_confidence", 0.85)),
        auto_id=substitute(str(raw.get("auto_id", "")), variables),
    )


def parse_step(raw, variables):
    if not isinstance(raw, dict) or "action" not in raw:
        raise PlanError(f"each step needs an action: {raw!r}")
    expect = raw.get("expect") or {}
    if not isinstance(expect, dict):
        raise PlanError(f"expect must be a mapping: {expect!r}")
    app = raw.get("app") or []
    if isinstance(app, str):
        app = [app]
    return Step(
        action=raw["action"],
        target=parse_target(raw.get("target"), variables),
        value=substitute(raw.get("value", ""), variables),
        expect=expect,
        wait=float(raw.get("wait", 1.5)),
        timeout=float(raw.get("timeout", 30.0)),
        name=raw.get("name", raw["action"]),
        optional=bool(raw.get("optional", False)),
        app=[substitute(str(token), variables) for token in app],
        path=substitute(raw.get("path", ""), variables),
        exe=substitute(raw.get("exe", ""), variables),
        window=substitute(raw.get("window", ""), variables),
        process=substitute(raw.get("process", ""), variables),
    )


def validate_step(step, variables):
    """Reject a step whose assertions cannot prove anything, before it acts.

    Everything here runs *before* the first real input: a plan that can only
    fail after the click has already fired is a plan that clicks first and
    asks questions later.
    """
    if step.expect.get("target"):
        expected = parse_target(step.expect["target"], variables)
        if step.action in ("click", "double_click", "right_click") and step.target is not None:
            same = (
                expected.text == step.target.text
                and expected.auto_id == step.target.auto_id
                and expected.match == step.target.match
            )
            if same:
                raise PlanError(
                    f"step {step.name}: expect.target duplicates the click target; "
                    "assert a post-state element (a toast, a dialog title, a row) instead"
                )


def assert_file(path, expect, variables, max_mb=64, not_before=None):
    """Verify a produced artifact: existence, size, magic bytes, and required text.

    Every field goes through variable substitution so plans never hard-code values.

    `not_before` (epoch seconds) rejects a file left over from an earlier run.
    Without it, a skipped optional download step followed by `expect_file`
    happily verifies yesterday's file at the same path.
    """
    path = Path(substitute(str(path), variables))
    if not path.exists():
        raise PlanError(f"expected file was not produced: {path}")
    if not_before is not None and not expect.get("allow_existing"):
        mtime = path.stat().st_mtime
        # Filesystem timestamps are coarse; a 2s grace avoids rejecting a file
        # written moments before this process started.
        if mtime < float(not_before) - 2.0:
            raise PlanError(
                f"file {path} predates this run (mtime {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(mtime))}); "
                "it is a leftover, not a fresh product. Set expect.allow_existing: true to accept it"
            )
    size = path.stat().st_size
    min_size = int(substitute(str(expect.get("min_bytes", 1)), variables))
    if size < min_size:
        raise PlanError(f"file {path} is only {size} bytes, expected >= {min_size}")
    limit = int(expect.get("max_mb", max_mb)) * 1024 * 1024
    if size > limit:
        raise PlanError(f"file {path} is {size} bytes, exceeding the {limit} byte inspection limit")
    magic = substitute(str(expect.get("magic") or ""), variables)
    if magic:
        with path.open("rb") as handle:
            head = handle.read(len(magic))
        if head != magic.encode("latin-1"):
            raise PlanError(f"file {path} does not start with {magic!r}")
    contains = expect.get("contains")
    if contains:
        text = _read_text(path, expect)
        for required in contains if isinstance(contains, list) else [contains]:
            needle = substitute(str(required), variables)
            if needle not in text:
                raise PlanError(f"file {path} is missing required text: {needle!r}")
    return {"path": str(path), "bytes": size}


def wait_for_file(path, expect, variables, timeout=30.0, interval=1.0, not_before=None):
    """Poll for an artifact that a download produces asynchronously."""
    deadline = time.monotonic() + timeout
    last = None
    while True:
        try:
            return assert_file(path, expect, variables, not_before=not_before)
        except PlanError as exc:
            last = exc
            if time.monotonic() >= deadline:
                raise PlanError(f"timeout after {timeout}s waiting for {path}: {last}") from last
            time.sleep(interval)


def _read_text(path, expect):
    if path.suffix.lower() == ".pdf":
        try:
            import pymupdf
        except ImportError as exc:
            raise PlanError("verifying PDF content requires pymupdf") from exc
        with pymupdf.open(path) as doc:
            return "".join(page.get_text() for page in doc)
    return path.read_text(encoding=expect.get("encoding", "utf-8"), errors="replace")


def validate_plan(data):
    if not data["steps"]:
        raise PlanError("plan has no steps")
    supported = {
        "launch", "click", "double_click", "right_click", "fill", "key",
        "wait_text", "wait", "assert_text", "expect_file",
    }
    for index, raw in enumerate(data["steps"]):
        if not isinstance(raw, dict):
            raise PlanError(f"step {index} must be a mapping")
        if raw.get("action") not in supported:
            raise PlanError(f"step {index}: unsupported action {raw.get('action')!r}")
        if raw.get("action") == "launch":
            # Launching changes machine state, so the plan must name the app and
            # be explicitly allowed by --allow-launch at run time.
            if not raw.get("app") and not raw.get("path"):
                raise PlanError(f"step {index}: launch requires 'app' (name tokens) or 'path'")
