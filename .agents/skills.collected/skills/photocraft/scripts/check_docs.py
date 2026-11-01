#!/usr/bin/env python3
"""Lint the skill's docs against the installed PhotoCraft (maintainers: execute after editing docs).

  python <skill-dir>/scripts/check_docs.py                 lint this skill
  python <skill-dir>/scripts/check_docs.py --json          machine-readable findings
  python <skill-dir>/scripts/check_docs.py --root DIR --include 'examples/*/README.md'

Scans SKILL.md, references/*.md (top-level), examples/README.md, examples/*.py, examples/actions/*.json,
examples/clients/*.py (string literals and comments) and the docstrings of scripts/*.py
(--include adds globs; .md/.json/.py/.mjs are understood). references/history/ is counted
and filename-checked but not linted; the run fails when it exceeds version.json's
history_max. version.json is checked against the upgrading.md heading and the history chain.
Checks, against live
baselines read from photocraft-cli (`commands --json`, serve `methods`, MCP `tools/list`)
plus the desktop control dispatch set of the release:

  unknown-id      dotted ids that are no engine command, serve method or GUI method.
                  Slash lists (image.mode.rgb/gray checks image.mode.gray), `id` / `sibling`  check-docs: ignore
                  chains, {a,b} and <a|b> groups are expanded; `<kind>` and `*` must match a
                  real family; `<id>.<field>` paths of a real id are accepted; a misspelt domain
                  (layers.setProps) is caught when the corrected id exists.  check-docs: ignore
  negative-used   an id the docs call non-existent (select.none, file.open, …) used without a  check-docs: ignore
                  "does not exist / 不存在 / 不是 / 没有 / unknown command" phrase on its line,
                  the adjacent prose line, or its list/table header.
  negative-exists one of those ids now exists: the "does not exist" sentences are stale.
  unknown-param   a key in `--cmd <id> --params '{…}'`, `--new '{…}'`, action/batch steps
                  ([id, params], {command|id, params}) or Python step literals that the id's
                  registry params text never mentions (allowlist: the deliberate typos
                  widht/radiuss, file.export.renderVideo dir/format; type.create also takes
                  type.setStyle's character keys).
  unknown-tool / unknown-tool-arg   MCP tool names and tools/call arguments vs tools/list.
  unknown-method  "method":"…" values that no serve, GUI or MCP JSON-RPC endpoint has.
  bad-family      a wildcard or template that matches nothing.

A line containing `check-docs: ignore` is skipped. A built-in self-test (bad id, bad
slash-list member, bad group member, negative id, bad key, bad tool, bad method) runs first.
Exit codes: 0 clean, 1 findings, 2 self-test failed or PhotoCraft not available.
"""
from __future__ import annotations

import argparse
import ast
import difflib
import fnmatch
import io
import json
import re
import sys
import tokenize
from dataclasses import asdict, dataclass
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import pclib  # noqa: E402

# Desktop control dispatch set, snapshotted from 0.10.0 (crates/ui-egui/src/control.rs).
# It is NOT read from the runtime: the desktop method list only exists on a live --control
# instance, which needs a window. Treat it as a lower bound, not an authority: a name here
# is not proof the method still exists, and a missing name is not proof it is gone.
GUI_METHODS = {
    "ui.context.choose", "engine.execute", "ui.menu.invoke", "engine.commands", "jobs.list",
    "jobs.cancel", "ui.menu.list", "ui.inspect", "ui.set", "ui.dialog.open", "ui.dialog.set",
    "ui.dialog.confirm", "ui.dialog.apply", "ui.dialog.cancel", "ui.window.open", "ui.window.close",
    "ui.pointer", "ui.click", "ui.move", "ui.key", "ui.type", "ui.resize", "ui.gpu.simulateLoss",
    "ui.focus", "ui.screenshot", "app.open", "app.save", "app.quit", "auth",
}
# Ids the docs state do not exist. Mentioning one needs a negation in context; if one ever
# appears in the registry or a method list, the docs that deny it are wrong.
NEGATIVE = {
    "select.none", "select.background", "layer.rename", "layer.setBounds", "type.registerFonts",
    "file.open", "file.save", "file.saveAs", "document.new", "document.save",
    # also called non-existent by the audited sources
    "layer.bounds", "image.mode.gray", "style.presets.save", "layer.align.left",
}
# Desktop-only menu ids named in the release docs (reached with ui.menu.invoke; not engine
# commands, not verified live).
DESKTOP_MENU = {
    "view.zoomIn", "window.theme.pro", "edit.search", "help.systemInfo", "type.editText",
    "tools.temporary.hand", "tools.temporary.zoomIn", "tools.temporary.zoomOut",
    "file.exit",   # menu item; the control channel refuses it by the `file.` rule
}
# Reply fields that look like ids.
FIELD_PATHS = {
    "session.documents", "session.active", "session.foreground", "session.background",
    "shape.Box", "shape.Path", "text.font", "type.info.lines", "type.info.bounds",
}
# Placeholder names the docs use to show the name-based refusal rule.
PLACEHOLDERS = {"file.bogusX", "file.bogusPathThing"}
PARAM_ALLOW = {
    ("image.imageSize", "widht"),            # deliberate typo: silently ignored (examples 02)
    ("filter.blur.gaussianBlur", "radiuss"),  # deliberate typo: rejected (examples 02)
    ("file.export.renderVideo", "dir"),       # registry text is `{} → {}`; live accepts these
    ("file.export.renderVideo", "format"),
}
EXTRA_KEYS_FROM = {                                  # docs that elide keys documented elsewhere
    "type.create": ("type.setStyle",),               # "…character keys"
    "type.createSelection": ("type.create", "type.setStyle"),   # "type.create's keys"
}
FAMILY_KEYS = {                                      # keys a whole family takes but few docs list
    "layer.layerStyle.": {"layer"},                  # every effect runs set_effect → layer_param
}
OPEN_DOC = re.compile(r"…[^,{}\"]*\b(?:fields|keys|params)\b")   # "…BrushSettings fields": any key
UNQUOTED_KEY = re.compile(r"(?:(?<=[{,|])|(?<=[{,|] ))([A-Za-z_][A-Za-z0-9_]*)\??(?=\s*[:,}|?])")
MCP_RPC = {"initialize", "ping", "notifications/initialized", "notifications/cancelled", "tools/list",
           "tools/call", "resources/list", "resources/read", "resources/templates/list", "prompts/list",
           "logging/setLevel", "completion/complete"}
FILE_SUFFIXES = tuple(
    ".json .jsonl .md .py .mjs .js .ts .sh .ps1 .bat .cmd .toml .yaml .yml .rs .txt .csv .log .html "
    ".xml .zip .exe .app .dmg .msi .deb .rpm .appimage .pyc .psd .psb .png .jpg .jpeg .tif .tiff .webp "
    ".gif .bmp .tga .exr .hdr .fits .svg .pdf .pcraft .ora .kra .pdn .af .afdesign .afphoto .afpub "
    ".atn .pcdroplet .cube .3dl .look .icc .icm .aco .ase .abr .grd .pat .asl .acv .heic .heif .avif "
    ".ico .qoi .dds .dpx .cin .pbm .pgm .ppm .pfm .pnm .jxl .jp2 .apng .ttf .otf .ttc .otc .woff "
    ".woff2 .token .lock .dng .cr2 .nef .arw .raw .ron".split())
NEGATION = re.compile(
    r"不存在|没有|不是|并非|不在|无此|未知命令|已移除|"
    r"does not exist|doesn't exist|do not exist|don't exist|not exist|nonexistent|non-existent|"
    r"there is no|there are no|no such|not an? (?:engine |registry |real )?(?:command|id|method)|"
    r"not (?:an? )?(?:engine|registry)|not in the registry|isn't an?|is not an?|are not|aren't|"
    r"unknown command|unknown method|absent", re.I)
IGNORE_MARK = re.compile(r"check[-_]docs:\s*ignore")
NEAR = 50                                            # chars between a negative id and its negation
ENVELOPE = re.compile(r'"(?:id|jsonrpc)"\s*:')       # "method" only counts inside a request
SEG = r"(?:[A-Za-z0-9_]+\*?|\*|<[^<>\s`]+>|\{[^{}\s`]+\})"
TOKEN = re.compile(r"(?<![\w/.\\$-])(?P<id>[a-z][A-Za-z0-9]*(?:\." + SEG + r")+)"
                   r"(?P<alts>(?:/[A-Za-z0-9_][A-Za-z0-9_.]*)*)(?!\.[A-Za-z0-9_*<{])(?![\w/\\*-])")
CHAIN = re.compile(r"`(?P<base>[a-z][A-Za-z0-9]*(?:\.[A-Za-z0-9_]+)+)`"
                   r"(?P<rest>(?:\s*/\s*`[A-Za-z0-9_][A-Za-z0-9_.]*`)+)")
TOOL = re.compile(r"(?<![\w.$/-])(?:doc|command|jobs|session|ui|render|control)_[a-z][a-z_]*(?![\w-])(?!\.[A-Za-z])")
METHOD = re.compile(r'"method"\s*:\s*"([^"\\]+)"')
GROUP = re.compile(r"<([^<>]+)>|\{([^{}]+)\}")
CMD_PARAMS = re.compile(r"--cmd\s+([A-Za-z][\w.]*)\s+--params\s+(?:'([^']*)'|\"((?:[^\"\\]|\\.)*)\")")
NEW_PARAMS = re.compile(r"--new\s+(?:'([^']*)'|\"((?:[^\"\\]|\\.)*)\")")
SQUOTED_JSON = re.compile(r"'(\s*[\[{][^']*[\]}]\s*)'")
FENCE = re.compile(r"^\s*(```+|~~~+)\s*([\w+-]*)")
SHELL_LANGS = {"bash", "sh", "shell", "zsh", "console", "powershell", "ps1", "pwsh", "cmd", "bat"}
PY_LANGS = {"python", "py", "python3", "pycon"}
JSON_LANGS = {"json", "jsonl", "json5", "jsonc"}
DEFAULT_GLOBS = ("SKILL.md", "references/*.md", "examples/README.md", "examples/*.py",
                 "examples/actions/*.json", "examples/clients/*.py", "scripts/*.py")
HISTORY_NAME = re.compile(r"\d+\.\d+(?:\.\d+)?\.md$")
HISTORY_HEADING = re.compile(r"#\s*(\d+\.\d+(?:\.\d+)?)\s*→\s*(\d+\.\d+(?:\.\d+)?)")
VERSION_HEADING = re.compile(r"#\s*(\d+\.\d+(?:\.\d+)?)\s*→\s*(\d+\.\d+(?:\.\d+)?)\s*升级指南")
DEFAULT_HISTORY_MAX = 5


def _minor(value) -> tuple[int, int] | None:
    match = re.match(r"(\d+)\.(\d+)", str(value or ""))
    return (int(match.group(1)), int(match.group(2))) if match else None


def _full_version(value) -> tuple[int, int, int] | None:
    match = re.match(r"(\d+)\.(\d+)(?:\.(\d+))?", str(value or ""))
    return tuple(int(part or 0) for part in match.groups()) if match else None


def _history_sort_key(path: Path) -> tuple[int, ...]:
    return tuple(int(x) for x in re.findall(r"\d+", path.stem))


def history_limit(root: Path) -> int:
    path = root / "references" / "version.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return DEFAULT_HISTORY_MAX
        value = int(data.get("history_max", DEFAULT_HISTORY_MAX))
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return DEFAULT_HISTORY_MAX
    return value if value > 0 else DEFAULT_HISTORY_MAX


def history_status(root: Path, limit: int) -> dict:
    history_dir = root / "references" / "history"
    entries = list(history_dir.iterdir()) if history_dir.is_dir() else []
    files = [p for p in entries if p.is_file() and HISTORY_NAME.fullmatch(p.name)]
    files.sort(key=_history_sort_key)
    bad = sorted(p.name for p in entries if not (p.is_file() and HISTORY_NAME.fullmatch(p.name)))
    return {"count": len(files), "limit": limit, "files": [p.name for p in files],
            "bad": bad, "ok": len(files) <= limit and not bad}


def version_status(root: Path) -> dict:
    errors: list[str] = []
    path = root / "references" / "version.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
        return {"ok": False, "errors": [f"references/version.json unreadable: {exc}"]}
    if not isinstance(data, dict):
        return {"ok": False, "errors": ["references/version.json must be an object"]}
    baseline = data.get("params_baseline")
    tested = data.get("behavior_tested")
    supported = data.get("supported")
    if not isinstance(supported, dict):
        errors.append("references/version.json: supported must be an object")
    else:
        low, high = supported.get("min"), supported.get("max")
        low_minor, high_minor = _minor(low), _minor(high)
        if low_minor is None or high_minor is None:
            errors.append("references/version.json: supported.min/max must be versions")
        elif low_minor > high_minor:
            errors.append("references/version.json: supported.min must be <= supported.max")
        if _minor(baseline) != low_minor:
            errors.append(f"params_baseline {baseline!r} != supported.min {low!r}")
        if _minor(tested) != high_minor:
            errors.append(f"behavior_tested {tested!r} != supported.max {high!r}")
    history_max = data.get("history_max")
    if history_max is not None and (isinstance(history_max, bool) or not isinstance(history_max, int) or history_max <= 0):
        errors.append("references/version.json: history_max must be a positive integer")
    upgrading = root / "references" / "upgrading.md"
    try:
        text = upgrading.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        errors.append(f"references/upgrading.md unreadable: {exc}")
    else:
        match = VERSION_HEADING.search(text)
        if not match:
            errors.append("references/upgrading.md: heading must be '# X → Y 升级指南'")
        else:
            if _minor(match.group(1)) != _minor(baseline):
                errors.append(f"upgrading.md starts at {match.group(1)}, params_baseline is {baseline}")
            if _minor(match.group(2)) != _minor(tested):
                errors.append(f"upgrading.md ends at {match.group(2)}, behavior_tested is {tested}")
    history = history_status(root, history_limit(root))
    if not history["files"]:
        errors.append("references/history is empty; keep at least one frozen transition")
    chain: list[tuple[str, str, str]] = []
    for name in history["files"]:
        try:
            frozen = (root / "references" / "history" / name).read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            errors.append(f"references/history/{name} unreadable: {exc}")
            continue
        match = HISTORY_HEADING.search(frozen)
        if not match:
            errors.append(f"references/history/{name}: heading must be '# X → Y ...'")
            continue
        source, target = match.group(1), match.group(2)
        if _full_version(target) != _full_version(Path(name).stem):
            errors.append(f"references/history/{name}: filename target != heading target {target}")
        chain.append((name, source, target))
    for previous, current in zip(chain, chain[1:]):
        if _minor(current[1]) != _minor(previous[2]):
            errors.append(f"history chain break: {previous[0]} ends at {previous[2]}, {current[0]} starts at {current[1]}")
    if chain and _minor(chain[-1][2]) != _minor(baseline):
        errors.append(f"history ends at {chain[-1][2]}, params_baseline is {baseline}")
    return {"ok": not errors, "errors": errors}
STEP_CALLS = {"step", "execute", "exec", "maybe_exec"}
TOOL_CALLS = {"call_tool", "call_json"}


@dataclass
class Finding:
    file: str
    line: int
    kind: str
    token: str
    detail: str = ""


def _lev(a: str, b: str) -> int:
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


class Baseline:
    def __init__(self, commands: list[dict], serve_methods: list[str], tools: dict[str, set]):
        self.reg = {c["id"]: c for c in commands}
        self.serve = set(serve_methods)
        self.gui = set(GUI_METHODS)
        self.tools = tools
        self.methods = self.serve | self.gui
        self.ids = set(self.reg) | self.methods
        self.families = {".".join(i.split(".")[:n]) for i in self.ids for n in range(1, i.count(".") + 1)}
        self.domains = {i.split(".")[0] for i in self.ids}
        self.bare = {m for m in self.methods if "." not in m} | {"methods", "batch"}
        self._keys: dict[str, set] = {}

    @classmethod
    def load(cls, cli=None) -> "Baseline":
        commands = pclib.registry(cli)
        with pclib.Serve(cli=cli, timeout=60) as serve:
            methods = serve.methods()
        with pclib.Mcp(cli=cli, timeout=60) as mcp:
            tools = {t["name"]: set(((t.get("inputSchema") or {}).get("properties") or {}).keys()) for t in mcp.tools()}
        return cls(commands, methods, tools)

    def param_keys(self, cid: str) -> set | None:
        """Keys the registry params text names (input part only); None = open-ended doc."""
        if cid not in self._keys:
            texts = [(self.reg.get(cid) or {}).get("params") or ""]
            texts += [(self.reg.get(o) or {}).get("params") or "" for o in EXTRA_KEYS_FROM.get(cid, ())]
            keys: set | None = set()
            for n, text in enumerate(texts):
                head = re.split(r"\s*→", text, maxsplit=1)[0]
                if n == 0 and cid not in EXTRA_KEYS_FROM and OPEN_DOC.search(head):
                    keys = None
                    break
                keys |= set(re.findall(r'"([A-Za-z_][A-Za-z0-9_]*)"', head))
                keys |= set(UNQUOTED_KEY.findall(head))
            if keys is not None:
                for prefix, extra in FAMILY_KEYS.items():
                    if cid.startswith(prefix):
                        keys |= extra
            self._keys[cid] = keys
        return self._keys[cid]

    def classify(self, tok: str) -> tuple[str, str]:
        """('ok'|'negative'|'unknown'|'bad-family'|'skip', suggestion)."""
        parts = tok.split(".")
        if parts[0] not in self.domains:
            if len(parts[0]) >= 3 and "*" not in tok:
                for dom in sorted(self.domains):
                    if 0 < _lev(parts[0], dom) <= 2:
                        fixed = ".".join([dom, *parts[1:]])
                        if fixed in self.ids:
                            return "unknown", fixed
            return "skip", ""
        if "*" in tok:
            pool = self.ids | self.families
            return ("ok", "") if any(fnmatch.fnmatchcase(x, tok) for x in pool) else ("bad-family", "")
        if tok in NEGATIVE:
            return "negative", ""
        if tok in self.ids or tok in self.families or tok in FIELD_PATHS or tok in DESKTOP_MENU or tok in PLACEHOLDERS:
            return "ok", ""
        if tok.lower().endswith(FILE_SUFFIXES):
            return "skip", ""   # actions.json, file.psd: file names
        if any(".".join(parts[:n]) in self.ids for n in range(2, len(parts))):
            return "ok", ""   # <id>.<field>, e.g. document.inspect.hasSelection
        same = [i for i in self.ids if i.split(".")[0] == parts[0]]
        close = difflib.get_close_matches(tok, same, n=1, cutoff=0.75)
        return "unknown", close[0] if close else ""


def _expand_groups(tok: str) -> list[str]:
    m = GROUP.search(tok)
    if not m:
        return [tok]
    angle = m.group(1) is not None
    inner = m.group(1) if angle else m.group(2)
    sep = "|" if angle else ","
    parts = [p.strip() for p in inner.split(sep)] if sep in inner else ["*"]
    out: list[str] = []
    for part in parts:
        if not part or part in ("…", "...") or not re.fullmatch(r"[A-Za-z0-9_*.]+", part):
            part = "*"
        out += _expand_groups(tok[:m.start()] + part + tok[m.end():])
    return out


def _is_table(line: str) -> bool:
    return line.lstrip().startswith("|")


def _needle(source: str, tok: str) -> list[str]:
    """Strings that locate a token on its line: the id itself, else its slash list's head."""
    out = [tok]
    if source:
        out.append(source.strip("`").split("/")[0].strip("` "))
    return out


def _is_item(line: str) -> bool:
    return bool(re.match(r"\s*(?:[-*+]\s|\d+[.)]\s)", line))


class Linter:
    def __init__(self, base: Baseline, stems: set | None = None):
        self.base = base
        self.stems = stems or set()     # file names in the skill: doc_ops_export.py is no MCP tool
        self.findings: list[Finding] = []
        self.tokens = 0
        self.param_sets = 0

    # ----------------------------------------------------------------- context
    def _negated(self, lines: list[str], lineno: int, needles: list[str] | None = None) -> bool:
        """A negation phrase near the token: within NEAR chars on its line, at the facing
        end of the adjacent prose line, or in the header of its list/table."""
        cur = lines[lineno - 1] if 0 < lineno <= len(lines) else ""
        window = cur
        for needle in needles or []:
            pos = cur.find(needle) if needle else -1
            if pos >= 0:
                window = cur[max(0, pos - NEAR):pos + len(needle) + NEAR]
                break
        if NEGATION.search(window):
            return True
        if _is_table(cur) or _is_item(cur):
            i = lineno - 1
            table = _is_table(cur)
            kind = _is_table if table else (lambda s: _is_item(s) or s.startswith((" ", "\t")))
            while i > 0 and lines[i - 1].strip() and kind(lines[i - 1]):
                i -= 1
            head = [lines[i]] if table and i < len(lines) else []   # a table's header row
            j = i - 1
            while j >= 0 and not lines[j].strip():
                j -= 1
            if j >= 0 and lines[j].rstrip().endswith((":", "：")):    # "以下 id 不存在：" intro
                head.append(lines[j])
            return any(NEGATION.search(h) for h in head)
        for j, edge in ((lineno - 2, "tail"), (lineno, "head")):
            if 0 <= j < len(lines):
                other = lines[j]
                if other.strip() and not _is_table(other) and not _is_item(other):
                    part = other[-NEAR:] if edge == "tail" else other[:NEAR]
                    if NEGATION.search(part):
                        return True
        return False

    def add(self, rel: str, lineno: int, lines: list[str], kind: str, token: str, detail: str = "") -> None:
        if 0 < lineno <= len(lines) and IGNORE_MARK.search(lines[lineno - 1]):
            return
        self.findings.append(Finding(rel, lineno, kind, token, detail))

    # ----------------------------------------------------------------- ids
    def check_ids(self, rel: str, lineno: int, text: str, lines: list[str], *, tools: bool = True) -> None:
        text = text.replace("\\|", "|")
        candidates: list[tuple[str, str]] = []
        for m in CHAIN.finditer(text):
            base = m.group("base")
            parent = base.rsplit(".", 1)[0]
            for alt in re.findall(r"`([^`]+)`", m.group("rest")):
                alt = alt.rstrip(".")
                if "." in alt and alt.split(".")[0] in self.base.domains:
                    continue          # a full id; the main pass sees it
                rel_id = f"{parent}.{alt}"
                if (alt in self.base.bare or alt in self.base.tools) and self.base.classify(rel_id)[0] != "ok":
                    continue          # `session.list`/`methods`: a standalone name, not a sibling
                candidates.append((rel_id, f"`{base}` / `{alt}`"))
        plain = text.replace("`", " ")
        for m in TOKEN.finditer(plain):
            if plain[m.end():m.end() + 1] == "(":
                continue                # engine.pick_font(): a Python call in prose, not an id
            first = m.group("id")
            alts = [a.rstrip(".") for a in m.group("alts").split("/")[1:] if a.rstrip(".")]
            source = m.group(0)
            candidates.append((first, source if alts else ""))
            parent = first.rsplit(".", 1)[0]
            for alt in alts:
                full = alt if ("." in alt and alt.split(".")[0] in self.base.domains) else f"{parent}.{alt}"
                if full != alt and alt in self.base.bare and self.base.classify(full)[0] != "ok":
                    continue          # doc.select/batch: `batch` is a method of its own
                candidates.append((full, source))
        for raw, source in candidates:
            for tok in _expand_groups(raw):
                status, hint = self.base.classify(tok)
                if status == "skip":
                    continue
                self.tokens += 1
                where = f"in `{source}`" if source else ""
                if status == "unknown":
                    detail = "; ".join(x for x in (where, f"did you mean {hint}?" if hint else "") if x)
                    self.add(rel, lineno, lines, "unknown-id", tok, detail)
                elif status == "bad-family":
                    self.add(rel, lineno, lines, "bad-family", tok, where)
                elif status == "negative" and not self._negated(lines, lineno, _needle(source, tok)):
                    self.add(rel, lineno, lines, "negative-used", tok,
                             "documented as non-existent; say so next to it (不存在/不是引擎命令/does not exist)")
        if tools:
            for m in TOOL.finditer(text):
                self.check_tool(rel, lineno, lines, m.group(0))
        if ENVELOPE.search(text):
            for m in METHOD.finditer(text):
                self.check_method(rel, lineno, lines, m.group(1))

    def check_tool(self, rel: str, lineno: int, lines: list[str], name: str) -> None:
        if name not in self.base.tools and name not in self.stems:
            close = difflib.get_close_matches(name, list(self.base.tools), n=1, cutoff=0.75)
            self.add(rel, lineno, lines, "unknown-tool", name, f"did you mean {close[0]}?" if close else "")

    def check_method(self, rel: str, lineno: int, lines: list[str], name: str) -> None:
        if "/" in name or name in ("initialize", "ping"):
            if name not in MCP_RPC:
                self.add(rel, lineno, lines, "unknown-method", name, "not an MCP JSON-RPC method")
        elif "." not in name and name not in self.base.bare:
            self.add(rel, lineno, lines, "unknown-method", name, "not a serve/GUI method")

    # ----------------------------------------------------------------- params
    def check_params(self, rel: str, lineno: int, lines: list[str], cid, params, via: str = "") -> None:
        if not isinstance(cid, str) or cid not in self.base.reg or not isinstance(params, dict):
            return
        self.param_sets += 1
        keys = self.base.param_keys(cid)
        if keys is None:
            return
        for key in params:
            if not isinstance(key, str) or key in keys or (cid, key) in PARAM_ALLOW:
                continue
            close = difflib.get_close_matches(key, sorted(keys), n=1, cutoff=0.6)
            detail = f"not in the registry params text of {cid}" + (f"; did you mean {close[0]}?" if close else "")
            self.add(rel, lineno, lines, "unknown-param", f"{cid} {key}", detail + (f" ({via})" if via else ""))

    def check_tool_args(self, rel: str, lineno: int, lines: list[str], name, arguments) -> None:
        if not isinstance(name, str):
            return
        if name not in self.base.tools:
            self.check_tool(rel, lineno, lines, name)
            return
        if isinstance(arguments, dict):
            allowed = self.base.tools[name]
            for key in arguments:
                if isinstance(key, str) and key not in allowed:
                    close = difflib.get_close_matches(key, sorted(allowed), n=1, cutoff=0.5)
                    self.add(rel, lineno, lines, "unknown-tool-arg", f"{name} {key}",
                             "MCP arguments are snake_case" + (f"; did you mean {close[0]}?" if close else ""))

    def walk_json(self, rel: str, lineno: int, lines: list[str], obj, depth: int = 0) -> None:
        if depth > 40:
            return
        if isinstance(obj, dict):
            if isinstance(obj.get("command"), str) and isinstance(obj.get("params"), dict):
                self.check_params(rel, lineno, lines, obj["command"], obj["params"], "command step")
            if isinstance(obj.get("id"), str) and isinstance(obj.get("params"), dict):
                self.check_params(rel, lineno, lines, obj["id"], obj["params"], "id step")
            if obj.get("method") == "tools/call" and isinstance(obj.get("params"), dict):
                self.check_tool_args(rel, lineno, lines, obj["params"].get("name"), obj["params"].get("arguments"))
            for value in obj.values():
                self.walk_json(rel, lineno, lines, value, depth + 1)
        elif isinstance(obj, list):
            if len(obj) == 2 and isinstance(obj[0], str) and isinstance(obj[1], dict):
                self.check_params(rel, lineno, lines, obj[0], obj[1], "[id, params] step")
            for value in obj:
                self.walk_json(rel, lineno, lines, value, depth + 1)

    def shell_params(self, rel: str, lineno: int, text: str, lines: list[str]) -> None:
        for m in CMD_PARAMS.finditer(text):
            raw = m.group(2) if m.group(2) is not None else m.group(3).replace('\\"', '"')
            if "$" in raw:
                continue
            try:
                params = json.loads(raw)
            except json.JSONDecodeError:
                continue
            self.check_params(rel, lineno, lines, m.group(1), params, "--params")
        for m in NEW_PARAMS.finditer(text):
            raw = m.group(1) if m.group(1) is not None else m.group(2).replace('\\"', '"')
            try:
                params = json.loads(raw)
            except json.JSONDecodeError:
                continue
            self.check_params(rel, lineno, lines, "file.new", params, "--new")
        for m in SQUOTED_JSON.finditer(text):
            try:
                obj = json.loads(m.group(1))
            except json.JSONDecodeError:
                continue
            self.walk_json(rel, lineno, lines, obj)

    # ----------------------------------------------------------------- file kinds
    def scan_text(self, rel: str, text: str, kind: str) -> None:
        lines = text.splitlines()
        if kind == "md":
            self._scan_markdown(rel, lines)
        elif kind == "sh":
            self._scan_shell(rel, lines, 0, lines)
        elif kind == "json":
            self._scan_json_file(rel, text, lines)
        elif kind == "py-doc":
            self._scan_python(rel, text, lines, docstrings_only=True)
        elif kind == "py":
            self._scan_python(rel, text, lines, docstrings_only=False)
        elif kind == "js":
            self._scan_js(rel, text, lines)

    def _scan_markdown(self, rel: str, lines: list[str]) -> None:
        i = 0
        while i < len(lines):
            fence = FENCE.match(lines[i])
            if fence:
                marker, lang = fence.group(1), fence.group(2).lower()
                j = i + 1
                while j < len(lines) and not lines[j].lstrip().startswith(marker[:3]):
                    j += 1
                body = lines[i + 1:j]
                if lang in PY_LANGS:
                    self._scan_python(rel, "\n".join(body), lines, docstrings_only=False, offset=i + 1)
                elif lang in JSON_LANGS:
                    self._scan_json_block(rel, body, i + 1, lines)
                elif lang in SHELL_LANGS:
                    self._scan_shell(rel, body, i + 1, lines)
                else:
                    for k, line in enumerate(body, i + 2):
                        self.check_ids(rel, k, line, lines)
                        self.shell_params(rel, k, line, lines)
                i = j + 1
                continue
            self.check_ids(rel, i + 1, lines[i], lines)
            self.shell_params(rel, i + 1, lines[i], lines)
            for span in re.findall(r"`([\[{][^`]*[\]}])`", lines[i]):
                try:
                    self.walk_json(rel, i + 1, lines, json.loads(span.replace("\\|", "|")))
                except json.JSONDecodeError:
                    pass
            i += 1

    def _scan_json_block(self, rel: str, body: list[str], offset: int, lines: list[str]) -> None:
        for k, line in enumerate(body, offset + 1):
            self.check_ids(rel, k, line, lines)
        try:
            self.walk_json(rel, offset + 1, lines, json.loads("\n".join(body)))
        except json.JSONDecodeError:
            for k, line in enumerate(body, offset + 1):     # JSON lines
                try:
                    self.walk_json(rel, k, lines, json.loads(line))
                except json.JSONDecodeError:
                    pass

    def _scan_shell(self, rel: str, body: list[str], offset: int, lines: list[str]) -> None:
        k = 0
        while k < len(body):
            start = k
            joined = body[k]
            heredoc = re.search(r"<<-?\s*['\"]?(\w+)['\"]?", joined)
            while joined.rstrip().endswith("\\") and k + 1 < len(body):
                k += 1
                joined = joined.rstrip()[:-1] + " " + body[k].strip()
            lineno = offset + start + 1
            comment_only = joined.lstrip().startswith("#")
            self.check_ids(rel, lineno, joined, lines, tools=comment_only)
            for m in re.finditer(r'"name"\s*:\s*"([^"]+)"', joined):
                if TOOL.fullmatch(m.group(1)):
                    self.check_tool(rel, lineno, lines, m.group(1))
            self.shell_params(rel, lineno, joined, lines)
            k += 1
            if heredoc:
                end = heredoc.group(1)
                doc_start = k
                while k < len(body) and body[k].strip() != end:
                    k += 1
                chunk = body[doc_start:k]
                for n, line in enumerate(chunk, offset + doc_start + 1):
                    self.check_ids(rel, n, line, lines, tools=False)
                    self.shell_params(rel, n, line, lines)
                try:
                    self.walk_json(rel, offset + doc_start + 1, lines, json.loads("\n".join(chunk)))
                except json.JSONDecodeError:
                    for n, line in enumerate(chunk, offset + doc_start + 1):
                        try:
                            self.walk_json(rel, n, lines, json.loads(line))
                        except json.JSONDecodeError:
                            pass
                k += 1

    def _scan_json_file(self, rel: str, text: str, lines: list[str]) -> None:
        for k, line in enumerate(lines, 1):
            self.check_ids(rel, k, line, lines)
        try:
            obj = json.loads(text)
        except json.JSONDecodeError as exc:
            self.add(rel, exc.lineno, lines, "bad-json", rel, str(exc))
            return
        before = len(self.findings)
        self.walk_json(rel, 0, lines, obj)
        for finding in self.findings[before:]:          # point at the line that names the key
            cid, _, key = finding.token.partition(" ")
            hits = [k for k, line in enumerate(lines, 1) if f'"{key}"' in line]
            both = [k for k in hits if f'"{cid}"' in lines[k - 1]]
            finding.line = (both or hits or [1])[0]

    def _scan_js(self, rel: str, text: str, lines: list[str]) -> None:
        pattern = re.compile(r"//[^\n]*|/\*.*?\*/|'(?:[^'\\\n]|\\.)*'|\"(?:[^\"\\\n]|\\.)*\"|`(?:[^`\\]|\\.)*`", re.S)
        for m in pattern.finditer(text):
            first = text.count("\n", 0, m.start()) + 1
            body = m.group(0)
            if body.startswith("`"):
                body = re.sub(r"\$\{[^{}]*\}", " ", body)     # template expressions are code
            for n, part in enumerate(body.split("\n")):
                self.check_ids(rel, first + n, part, lines)
                self.shell_params(rel, first + n, part, lines)

    def _scan_python(self, rel: str, text: str, lines: list[str], *, docstrings_only: bool, offset: int = 0) -> None:
        try:
            tree = ast.parse(text)
        except SyntaxError:
            tree = None
        if docstrings_only:
            if tree is None:
                return
            for node in [tree, *ast.walk(tree)]:
                if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                    body = getattr(node, "body", [])
                    if body and isinstance(body[0], ast.Expr) and isinstance(getattr(body[0], "value", None), ast.Constant) \
                            and isinstance(body[0].value.value, str):
                        start = body[0].lineno
                        for n, part in enumerate(body[0].value.value.split("\n")):
                            self.check_ids(rel, offset + start + n, part, lines)
                            self.shell_params(rel, offset + start + n, part, lines)
            return
        try:
            toks = list(tokenize.generate_tokens(io.StringIO(text).readline))
        except (tokenize.TokenError, IndentationError, SyntaxError):
            for n, line in enumerate(text.splitlines(), offset + 1):
                self.check_ids(rel, n, line, lines, tools=False)
            return
        kinds = {tokenize.STRING, tokenize.COMMENT}
        fstring_middle = getattr(tokenize, "FSTRING_MIDDLE", None)
        if fstring_middle is not None:
            kinds.add(fstring_middle)
        for tok in toks:
            if tok.type not in kinds:
                continue
            value = tok.string
            if tok.type == tokenize.STRING:
                try:
                    decoded = ast.literal_eval(tok.string)
                except (ValueError, SyntaxError):
                    decoded = None
                if isinstance(decoded, str):
                    value = decoded
                elif re.match(r"(?i)[rbu]*f", tok.string):     # f-string before 3.12: drop {expr}
                    value = re.sub(r"\{[^{}]*\}", " ", tok.string)
            for n, part in enumerate(value.split("\n")):
                lineno = offset + tok.start[0] + n
                bare = part.strip().strip("'\"")
                is_tool = tok.type != tokenize.COMMENT and bool(TOOL.fullmatch(bare))
                self.check_ids(rel, lineno, part, lines, tools=tok.type == tokenize.COMMENT)
                if is_tool:
                    self.check_tool(rel, lineno, lines, bare)
                self.shell_params(rel, lineno, part, lines)
        if tree is not None:
            self._python_literals(rel, tree, lines, offset)

    def _python_literals(self, rel: str, tree, lines: list[str], offset: int) -> None:
        def text(node):
            return node.value if isinstance(node, ast.Constant) and isinstance(node.value, str) else None

        def keys(node):
            if not isinstance(node, ast.Dict):
                return None
            return {text(k): v for k, v in zip(node.keys, node.values) if text(k) is not None}

        for node in ast.walk(tree):
            line = offset + getattr(node, "lineno", 0)
            if isinstance(node, ast.Call):
                func = node.func.attr if isinstance(node.func, ast.Attribute) else getattr(node.func, "id", "")
                if func in STEP_CALLS and len(node.args) >= 2 and text(node.args[0]) and keys(node.args[1]) is not None:
                    self.check_params(rel, line, lines, text(node.args[0]), keys(node.args[1]), f"{func}()")
                if func in TOOL_CALLS and node.args and text(node.args[0]):
                    args = keys(node.args[1]) if len(node.args) > 1 else {}
                    self.check_tool_args(rel, line, lines, text(node.args[0]), args if args is not None else {})
                for kw in node.keywords:
                    if kw.arg == "new" and keys(kw.value) is not None:
                        self.check_params(rel, line, lines, "file.new", keys(kw.value), "new=")
            elif isinstance(node, (ast.Tuple, ast.List)) and len(node.elts) == 2:
                cid, params = text(node.elts[0]), keys(node.elts[1])
                if cid and params is not None:
                    self.check_params(rel, line, lines, cid, params, "(id, params)")
            elif isinstance(node, ast.Dict):
                d = keys(node) or {}
                for key in ("command", "id"):
                    if key in d and text(d[key]) and keys(d.get("params")) is not None:
                        self.check_params(rel, line, lines, text(d[key]), keys(d["params"]), f"{{{key}, params}}")
                if text(d.get("name")) and "arguments" in d and keys(d["arguments"]) is not None:
                    self.check_tool_args(rel, line, lines, text(d["name"]), keys(d["arguments"]))
                if text(d.get("method")) and {"id", "jsonrpc", "params"} & set(d):
                    self.check_method(rel, line, lines, text(d["method"]))

    def negative_exists(self) -> None:
        for cid in sorted(NEGATIVE & (set(self.base.reg) | self.base.methods)):
            self.findings.append(Finding("-", 0, "negative-exists", cid,
                                         "now exists; fix every sentence that says it does not"))

    def unique_findings(self) -> list[Finding]:
        seen, out = set(), []
        for f in self.findings:
            key = (f.file, f.line, f.kind, f.token)
            if key not in seen:
                seen.add(key)
                out.append(f)
        return out


def kind_of(path: Path, rel: str) -> str | None:
    suffix = path.suffix.lower()
    if suffix == ".md":
        return "md"
    if suffix == ".sh":
        return "sh"
    if suffix == ".json":
        return "json"
    if suffix in (".mjs", ".js"):
        return "js"
    if suffix == ".py":
        return "py-doc" if rel.replace("\\", "/").startswith("scripts/") else "py"
    return None


SELF_TEST_MD = """\
`image.noSuchCommand123` must be flagged.
`image.mode.rgb/bogusMode` flags its second member; `image.mode.rgb` alone is fine.
Groups: `layer.newAdjustmentLayer.<curves|bogusKind>` and `ui.dialog.{open,bogusVerb}`.
`layer.mergeDown` / `bogusSibling` is a sibling chain; `doc.*`/`session.list`/`methods` is not.
`select.none` 不存在：取消选区用 `select.deselect`。

---

Use `select.none` to clear the selection.

| id | note |
|---|---|
| `layer.rename` | 不存在，用 `layer.renameLayer` |
| `file.save` | 在 serve 里被拒 |

这些 id 不存在：
- `layer.setBounds`
- `type.registerFonts`

没有选区时，先建选区再继续
1. 用 `file.open` 打开文件

`doc_export_layer` is a typo of the tool `doc_export_layers`.
`ui.menu.invok` is a typo of `ui.menu.invoke`; `layers.setProps` has a domain typo.
`image.modes.*` matches nothing; `image.mode.*` and `layer.newAdjustmentLayer.<kind>` do.
`type.info.lines` is a field path; `doc.save` and `engine.execute` are methods.
"""
SELF_TEST_SH = """\
pc run in.jpg --cmd filter.blur.gaussianBlur --params '{"radius":2,"bogusKey":1}'
pc run in.jpg --cmd image.imageSize --params '{"widht":600}' --out x.png
printf '%s\\n' '{"id":1,"method":"bach"}' '{"id":2,"method":"batch","params":{"steps":[{"command":"select.rect","params":{"x":0,"wdth":3}}]}}'
"""
SELF_TEST_PY = """\
mcp.call_tool("doc_export_layers", {"dir": "out", "visibleOnly": True})
steps = [("image.adjustments.levels", {"inBlack": 4, "gama": 1.2})]
"""
SELF_TEST_EXPECT = {
    ("unknown-id", "image.noSuchCommand123"), ("unknown-id", "image.mode.bogusMode"),
    ("unknown-id", "layer.newAdjustmentLayer.bogusKind"), ("unknown-id", "ui.dialog.bogusVerb"),
    ("unknown-id", "layer.bogusSibling"), ("negative-used", "select.none"), ("negative-used", "file.save"),
    ("negative-used", "file.open"),
    ("unknown-tool", "doc_export_layer"), ("unknown-id", "ui.menu.invok"), ("unknown-id", "layers.setProps"),
    ("bad-family", "image.modes.*"), ("unknown-param", "filter.blur.gaussianBlur bogusKey"),
    ("unknown-method", "bach"), ("unknown-param", "select.rect wdth"),
    ("unknown-tool-arg", "doc_export_layers visibleOnly"), ("unknown-param", "image.adjustments.levels gama"),
}


def self_test(base: Baseline) -> list[str]:
    lint = Linter(base)
    lint.scan_text("self-test.md", SELF_TEST_MD, "md")
    lint.scan_text("self-test.sh", SELF_TEST_SH, "sh")
    lint.scan_text("self-test.py", SELF_TEST_PY, "py")
    got = {(f.kind, f.token) for f in lint.unique_findings()}
    problems = [f"missed {k} {t}" for k, t in sorted(SELF_TEST_EXPECT - got)]
    problems += [f"false positive {k} {t}" for k, t in sorted(got - SELF_TEST_EXPECT)]
    lines = [(f.line, f.token) for f in lint.findings if f.token == "select.none"]
    expected_line = SELF_TEST_MD.splitlines().index("Use `select.none` to clear the selection.") + 1
    if lines != [(expected_line, "select.none")]:
        problems.append(f"negation context wrong for select.none: {lines}")
    return problems


def collect(root: Path, includes: list[str]) -> list[Path]:
    seen: list[Path] = []
    for pattern in (*DEFAULT_GLOBS, *includes):
        for path in sorted(root.glob(pattern)):
            if path.is_file() and path not in seen and "__pycache__" not in path.parts:
                seen.append(path)
    return seen


def main(argv: list[str] | None = None) -> int:
    pclib.setup_stdio()
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", default=str(HERE.parent), help="skill directory to lint (default: this skill)")
    ap.add_argument("--include", action="append", default=[], help="extra glob relative to --root (repeatable)")
    ap.add_argument("--json", action="store_true", help="print findings as JSON")
    ap.add_argument("--cli", help="photocraft-cli path (default: find_cli order)")
    args = ap.parse_args(argv)
    root = Path(args.root).resolve()
    if not root.is_dir():
        print(f"check_docs: --root {root} is not a directory", file=sys.stderr)
        return 2
    try:
        base = Baseline.load(args.cli)
    except pclib.PcError as exc:
        print(f"check_docs: cannot read the PhotoCraft baselines: {exc}", file=sys.stderr)
        return 2
    problems = self_test(base)
    if problems:
        print("check_docs: SELF-TEST FAILED: " + "; ".join(problems), file=sys.stderr)
        return 2

    lint = Linter(base, {p.stem for p in root.rglob("*") if p.is_file()})
    files = collect(root, args.include)
    if not files:
        print(f"check_docs: no files to lint under {root}", file=sys.stderr)
        return 1
    for path in files:
        rel = path.relative_to(root).as_posix()
        kind = kind_of(path, rel)
        if kind is None:
            continue
        lint.scan_text(rel, path.read_text(encoding="utf-8-sig", errors="replace"), kind)
    lint.negative_exists()
    findings = lint.unique_findings()
    counts: dict[str, int] = {}
    for f in findings:
        counts[f.kind] = counts.get(f.kind, 0) + 1
    skill_root = Path(__file__).resolve().parent.parent
    has_version = (root / "references" / "version.json").is_file()
    has_version_docs = ((root / "references" / "upgrading.md").is_file()
                        or (root / "references" / "history").is_dir()
                        or (root / "SKILL.md").is_file())
    if root == skill_root or has_version or has_version_docs:
        history = history_status(root, history_limit(root))
        version = version_status(root)
    else:
        history = {"count": 0, "limit": 0, "files": [], "bad": [], "ok": True, "skipped": True}
        version = {"ok": True, "errors": [], "skipped": True}
    history_ok = history["ok"]
    version_ok = version["ok"]
    summary = {"root": str(root), "files": len(files), "id_tokens": lint.tokens, "param_sets": lint.param_sets,
               "baseline": {"commands": len(base.reg), "serve_methods": len(base.serve),
                            "gui_methods": len(base.gui), "mcp_tools": len(base.tools),
                            "gui_methods_source": "static snapshot (0.10.0), not runtime-verified"},
               "version": version, "history": history,
               "counts": counts, "findings": [asdict(f) for f in findings]}
    if args.json:
        print(json.dumps(summary, indent=2, ensure_ascii=False))
    else:
        print(f"check_docs: {root}: {len(files)} files, {lint.tokens} id tokens, {lint.param_sets} param sets; "
              f"baseline {len(base.reg)} commands, {len(base.serve)} serve methods, {len(base.tools)} MCP tools; "
              f"{len(base.gui)} GUI methods (static 0.10 snapshot, not runtime-verified)")
        for f in findings:
            print(f"{f.file}:{f.line}: {f.kind} `{f.token}`" + (f" ({f.detail})" if f.detail else ""))
        if findings:
            print("FAIL: " + ", ".join(f"{k} {v}" for k, v in sorted(counts.items())))
        if history.get("skipped"):
            print("history check skipped (no references/version.json)")
        else:
            if history["bad"]:
                print(f"FAIL: unexpected history filenames: {', '.join(history['bad'])}")
            if history["count"] > history["limit"]:
                print(f"FAIL: references/history has {history['count']} files; keep at most {history['limit']} "
                      f"(delete the oldest): {', '.join(history['files'])}")
        if not version_ok:
            for error in version["errors"]:
                print(f"FAIL: {error}")
        elif version.get("skipped"):
            print("version metadata skipped (no references/version.json)")
        if not findings and history_ok and version_ok:
            history_text = "history skipped" if history.get("skipped") else f"history {history['count']}/{history['limit']}"
            version_text = "version metadata skipped" if version.get("skipped") else "version metadata consistent"
            print(f"OK: no findings; {history_text}; {version_text}")
    return 1 if findings or not history_ok or not version_ok else 0


if __name__ == "__main__":
    raise SystemExit(main())
