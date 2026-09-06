#!/usr/bin/env python3
"""storyset.py — Storyset (storyset.com) illustration toolkit.

Zero-dependency (Python 3.8+ stdlib) CLI wrapping the public Freepik Stories API:

  search    Search illustrations via the JSON API
  download  Download an illustration SVG/PNG (by slug+style or direct URL)
  palette   List dominant hex colors of an SVG
  recolor   Rewrite hex colors inside an SVG
  animate   Inject CSS keyframes into an SVG (animated SVG, 100% client-side)
  render    Render an SVG to GIF/MP4 via stories.freepiklabs.com/api/render

All endpoints verified working without auth (2026-09). Respect the rate limits:
keep API pagination to ~1 req / 2s; the render endpoint allows ~30 req / window.
Storyset free tier requires attribution — see https://storyset.com/terms

Security posture (enforced in code, not just docs):
- downloads are restricted to https:// storyset/freepiklabs hosts (redirects re-checked)
- all network reads are size-capped; Retry-After is parsed defensively and clamped
- --bg / --elements are validated so they cannot break out of the <style> block
- recolor/palette skip url(#id) / href="#id" fragment references (ids, not colors)
- render uploads the FULL file to a third party — never render sensitive files
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

API = "https://stories.freepiklabs.com/api"
RENDER_URL = f"{API}/render"
SITE = "https://storyset.com"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")

STYLES = ("amico", "bro", "cuate", "pana", "rafiki")
# Each style has one dominant brand color — the usual recolor target.
STYLE_PRIMARY = {
    "amico": "#BA68C8",
    "bro": "#92E3A9",
    "cuate": "#FFC727",
    "pana": "#FF725E",
    "rafiki": "#407BFF",
}

# Hosts the downloader may talk to. download --url is user/agent-controlled
# input; without this an agent could be talked into fetching file:// or
# intranet/metadata URLs (SSRF) under its own authority.
ALLOWED_HOSTS = {"stories.freepiklabs.com", "storyset.com", "www.storyset.com"}

MAX_RESPONSE_BYTES = 50 * 1024 * 1024  # storyset SVGs run ~100-500 KB
MAX_RETRY_AFTER = 120.0                # clamp server-supplied waits

# Matches EITHER a fragment reference (consumed whole, never treated as a
# color) OR a bare hex color (captured in group 1). Reference forms covered:
#   url(#id)  url('#id')  url( "#id" )   [any case]
#   href="#id"  href = '#id'  xlink:href="#id"   [any quote/space/case]
# These are ids — recoloring them would break gradient/pattern references.
_REF_URL = r"url\(\s*['\"]?#[0-9A-Fa-f]{3}(?:[0-9A-Fa-f]{3})?['\"]?\s*\)"
_REF_HREF = r"[a-z-]*:?href\s*=\s*['\"]#[0-9A-Fa-f]{3}(?:[0-9A-Fa-f]{3})?['\"]"
HEX_RE = re.compile(
    _REF_URL + "|" + _REF_HREF + "|#([0-9A-Fa-f]{3}|[0-9A-Fa-f]{6})\\b",
    re.IGNORECASE,
)

CSS_IDENT_RE = re.compile(r"^[A-Za-z][\w.-]*$")
HEX_COLOR_RE = re.compile(r"#(?:[0-9A-Fa-f]{3}|[0-9A-Fa-f]{6})")
SAFE_STEM_RE = re.compile(r"[^A-Za-z0-9._-]+")

# ---------------------------------------------------------------------------
# HTTP helpers (429-aware; render endpoint is slow, needs a long timeout)
# ---------------------------------------------------------------------------

def check_asset_url(url: str) -> None:
    """Enforce the host allowlist SKILL.md advertises (SSRF guard)."""
    p = urllib.parse.urlparse(url)
    if p.scheme != "https" or (p.hostname or "") not in ALLOWED_HOSTS:
        raise SystemExit(f"refusing URL (only https://{sorted(ALLOWED_HOSTS)} allowed): {url}")


class _CheckedRedirect(urllib.request.HTTPRedirectHandler):
    """Re-validate every redirect hop against the allowlist."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        check_asset_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


_OPENER = urllib.request.build_opener(_CheckedRedirect)


def _read_capped(r, limit: int = MAX_RESPONSE_BYTES) -> bytes:
    data = r.read(limit + 1)
    if len(data) > limit:
        raise SystemExit(f"response too large (> {limit // 2**20} MB), aborted")
    return data


def _retry_after_seconds(e: urllib.error.HTTPError) -> float:
    """Parse Retry-After defensively: RFC 7231 allows HTTP-dates (unparseable
    here) and a hostile/buggy server could send garbage or negatives."""
    raw = e.headers.get("Retry-After")
    if not raw:
        return 20.0
    try:
        return min(max(float(raw), 0.0), MAX_RETRY_AFTER)
    except ValueError:
        return 20.0  # HTTP-date form or garbage: fall back to the default


def _req(url: str, data: bytes | None = None, accept: str = "application/json",
         timeout: int = 30) -> urllib.request.addinfourl:
    headers = {
        "User-Agent": UA,
        "Accept": accept,
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": f"{SITE}/",
    }
    if data is not None:
        headers["Content-Type"] = "application/json"
    return urllib.request.urlopen(
        urllib.request.Request(url, data=data, headers=headers), timeout=timeout)


def _get_json(url: str, retries: int = 2) -> dict:
    for attempt in range(retries + 1):
        try:
            with _req(url) as r:
                return json.loads(_read_capped(r).decode("utf-8"))
        except urllib.error.HTTPError as e:
            if e.code == 429 and attempt < retries:
                wait = _retry_after_seconds(e)
                print(f"429 rate-limited, waiting {wait:.0f}s...", file=sys.stderr)
                time.sleep(wait)
                continue
            raise SystemExit(f"HTTP {e.code} for {url}: {e.read(4096)[:200]!r}")
        except urllib.error.URLError as e:
            if attempt < retries:
                time.sleep(2 ** attempt)
                continue
            raise SystemExit(f"Network error for {url}: {e}")


def _get_bytes(url: str) -> bytes:
    check_asset_url(url)
    req = urllib.request.Request(url, headers={
        "User-Agent": UA,
        "Accept": "image/svg+xml,image/*,*/*;q=0.8",
        "Referer": f"{SITE}/",
    })
    try:
        with _OPENER.open(req, timeout=30) as r:
            return _read_capped(r)
    except urllib.error.HTTPError as e:
        raise SystemExit(f"HTTP {e.code} downloading {url}")
    except urllib.error.URLError as e:
        raise SystemExit(f"Network error downloading {url}: {e}")


def read_text_or_exit(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        raise SystemExit(f"file not found or unreadable: {path}")


def write_or_exit(path: Path, data, binary: bool = False) -> None:
    """Uniform writer: creates parent dirs, fails clean (no tracebacks)."""
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        if binary:
            path.write_bytes(data)
        else:
            path.write_text(data, encoding="utf-8")
    except OSError as e:
        raise SystemExit(f"cannot write {path}: {e}")


# ---------------------------------------------------------------------------
# search / download
# ---------------------------------------------------------------------------

def api_search(query: str, style: str | None, limit: int,
               max_pages: int = 0) -> list[dict]:
    """Paginate the JSON API until `limit` items (30/page).

    max_pages=0 means "keep going until links.next is null"; resolve_item
    passes an explicit cap because a wrong slug would otherwise crawl forever.
    """
    out: list[dict] = []
    page = 1
    while len(out) < limit:
        q = urllib.parse.urlencode({
            "query": query, "page": page,
            **({"style": style} if style else {}),
        })
        data = _get_json(f"{API}/vectors?{q}")
        items = data.get("data") or []
        if not items:
            break
        for it in items:
            ill = it.get("illustration") or {}
            out.append({
                "slug": ill.get("slug") or (it.get("slug") or "").split("/")[0],
                "style": it.get("style"),
                "name": ill.get("name"),
                "svg": it.get("src"),
                "png": it.get("preview"),
                "png_transparent": it.get("preview_no_bg"),
                "page": it.get("url"),
                "tags": [t.get("name") for t in (it.get("tags") or []) if t.get("name")],
                "downloads": it.get("total_downloads"),
            })
        if not (data.get("links") or {}).get("next"):
            break
        page += 1
        if max_pages and page > max_pages:
            break
        time.sleep(2)  # politeness: API paginates at ~1 req / 2s
    return out[:limit]


def resolve_item(slug: str, style: str) -> dict:
    """Find one API item matching slug+style exactly (search by slug words)."""
    matches = api_search(slug.replace("-", " "), style, 500, max_pages=5)
    for m in matches:
        if m["slug"] == slug and m["style"] == style:
            return m
    near = ", ".join(f"{m['slug']}/{m['style']}" for m in matches[:8])
    raise SystemExit(
        f"Not found: {slug}/{style} in first {len(matches)} result(s) "
        f"(capped at 5 pages). Near matches: {near or 'none'}")


def cmd_search(a: argparse.Namespace) -> None:
    if a.style and a.style not in STYLES:
        raise SystemExit(f"style must be one of {STYLES}")
    results = api_search(a.query, a.style, a.limit)
    if a.json:
        print(json.dumps(results, ensure_ascii=False, indent=2))
        return
    for r in results:
        tags = ",".join(r["tags"][:3])
        print(f"{r['slug']}/{r['style']:<7} {r['name'] or '':<35} "
              f"dl={r['downloads'] or 0:<6} {tags}\n    {r['svg']}")
    print(f"-- {len(results)} result(s)")


def safe_stem(stem: str, fallback: str = "storyset") -> str:
    """Server/URL-derived names must never become a path traversal."""
    stem = SAFE_STEM_RE.sub("_", stem).strip(".")
    return stem or fallback


def cmd_download(a: argparse.Namespace) -> None:
    # validate cheap things BEFORE spending a network call
    mapping = parse_color_map(a.recolor)
    if mapping and a.format != "svg":
        raise SystemExit("--recolor only works for SVG")
    if a.url:
        svg_url, png_url = a.url, None
        stem = safe_stem(Path(urllib.parse.urlparse(a.url).path).stem)
        if a.transparent:
            raise SystemExit("--transparent only works with --slug (URL mode has no bg info)")
    else:
        if not a.slug:
            raise SystemExit("download needs --slug (with --style) or --url")
        item = resolve_item(a.slug, a.style)
        svg_url = item["svg"]
        png_url = item["png_transparent"] if a.transparent else item["png"]
        stem = safe_stem(f"{item['slug']}-{item['style']}")
    url = png_url if a.format == "png" else svg_url
    if not url:
        raise SystemExit(f"No {a.format.upper()} URL for this item (only available via --slug)")
    data = _get_bytes(url)
    if mapping:
        text, stats = apply_recolor(data.decode("utf-8"), mapping)
        data = text.encode("utf-8")
        print(f"recolored: {stats}")
    path = Path(a.out) / f"{stem}.{a.format}"
    write_or_exit(path, data, binary=True)
    print(f"saved {path} ({len(data)} bytes)")


# ---------------------------------------------------------------------------
# palette / recolor
# ---------------------------------------------------------------------------

def norm_hex(h: str) -> str:
    h = h.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    return "#" + h.lower()


def parse_color_map(spec: str | None) -> dict[str, str]:
    """Parse '#BA68C8=#2196F3,#fff=#000' or 'amico=#2196F3' (style primary)."""
    if not spec:
        return {}
    out = {}
    for pair in spec.split(","):
        src, _, dst = pair.partition("=")
        src, dst = src.strip(), dst.strip()
        if not dst:
            raise SystemExit(f"bad --map pair: {pair!r} (want old=new)")
        if src.lower() in STYLE_PRIMARY:
            src = STYLE_PRIMARY[src.lower()]
        for side, val in (("src", src), ("dst", dst)):
            cand = val if val.startswith("#") else "#" + val
            if not HEX_COLOR_RE.fullmatch(cand):
                raise SystemExit(f"bad --map {side} color: {val!r} "
                                 f"(want #rgb or #rrggbb)")
        out[norm_hex(src)] = norm_hex(dst)
    return out


def apply_recolor(svg: str, mapping: dict[str, str]) -> tuple[str, dict[str, int]]:
    stats = {k: 0 for k in mapping}

    def repl(m: re.Match) -> str:
        if m.group(1) is None:      # matched a url()/href fragment ref — keep
            return m.group(0)
        n = norm_hex(m.group(0))
        if n in mapping:
            stats[n] += 1
            return mapping[n]
        return m.group(0)

    return HEX_RE.sub(repl, svg), stats


def iter_colors(svg: str):
    """Yield normalized hex colors, skipping fragment references."""
    for m in HEX_RE.finditer(svg):
        if m.group(1) is not None:
            yield norm_hex(m.group(0))


def cmd_palette(a: argparse.Namespace) -> None:
    svg = read_text_or_exit(Path(a.file))
    counts: dict[str, int] = {}
    for n in iter_colors(svg):
        counts[n] = counts.get(n, 0) + 1
    top = sorted(counts.items(), key=lambda kv: -kv[1])[: a.top]
    for color, n in top:
        print(f"{color}  {n}")
    if top and a.style_hint:
        # storyset palettes are usually topped by neutral stroke/background
        # colors, so flag any style primary anywhere in the top list.
        present = {c for c, _ in top}
        for style, primary in STYLE_PRIMARY.items():
            p = norm_hex(primary)
            if p in present:
                print(f"(style '{style}' primary {p} is in the list — "
                      f"the usual recolor target)")


def cmd_recolor(a: argparse.Namespace) -> None:
    mapping = parse_color_map(a.map)
    if not mapping:
        raise SystemExit("--map required, e.g. --map '#BA68C8=#2196F3' or --map 'amico=#2196F3'")
    src = Path(a.file)
    text, stats = apply_recolor(read_text_or_exit(src), mapping)
    if not any(stats.values()):
        print(f"warning: no occurrences of {list(mapping)} found — file unchanged",
              file=sys.stderr)
    out = Path(a.out) if a.out else src.with_name(src.stem + "_recolored.svg")
    write_or_exit(out, text)
    print(f"saved {out} | recolored: {stats}")


# ---------------------------------------------------------------------------
# animate (client-side CSS injection — the same mechanism storyset's editor uses)
# ---------------------------------------------------------------------------

# preset name -> (keyframes_css, animation_shorthand, duration_s, is_loop)
PRESETS = {
    "fadeIn": ("@keyframes fadeIn{0%{opacity:0}100%{opacity:1}}",
               "1s 1 forwards cubic-bezier(.36,-0.01,.5,1.38) fadeIn", 1.0, False),
    "fadeInUp": ("@keyframes fadeInUp{0%{opacity:0;transform:translateY(30px)}"
                 "100%{opacity:1;transform:translateY(0)}}",
                 "1s 1 forwards cubic-bezier(.36,-0.01,.5,1.38) fadeInUp", 1.0, False),
    "zoomIn": ("@keyframes zoomIn{0%{opacity:0;transform:scale(.5)}"
               "100%{opacity:1;transform:scale(1)}}",
               "1s 1 forwards cubic-bezier(.36,-0.01,.5,1.38) zoomIn", 1.0, False),
    "spin": ("@keyframes spin{0%{transform:rotate(0)}100%{transform:rotate(360deg)}}",
             "1.5s Infinite linear spin", 1.5, True),
    "pulse": ("@keyframes pulse{0%,100%{transform:scale(1)}50%{transform:scale(1.05)}}",
              "1.5s Infinite ease-in-out pulse", 1.5, True),
    "float": ("@keyframes float{0%,100%{transform:translateY(0)}"
              "50%{transform:translateY(-10px)}}",
              "2s Infinite ease-in-out float", 2.0, True),
}

SVG_OPEN_RE = re.compile(r"<svg\b[^>]*>")
COMMENT_RE = re.compile(r"<!--.*?-->", re.S)
ATTR_ID_RE = re.compile(r"""\bid\s*=\s*["']([^"']+)["']""")
ATTR_CLASS_RE = re.compile(r"""\bclass\s*=\s*["']([^"']*)["']""")
SVG_ID_SAFE_RE = re.compile(r"^[\w.-]+$")


def _svg_open(svg: str) -> re.Match | None:
    """First <svg> tag NOT inside an XML comment — a commented-out fake tag
    would otherwise swallow the id/style/class injection."""
    comments = [m.span() for m in COMMENT_RE.finditer(svg)]
    for m in SVG_OPEN_RE.finditer(svg):
        if not any(s <= m.start() < e for s, e in comments):
            return m
    return None


def validate_elements(spec: str | None) -> list[str]:
    """Element ids land inside a <style> block — reject anything that could
    break out of it (e.g. contain `</style>`), and drop empty segments."""
    if not spec:
        return []
    out = []
    for e in spec.split(","):
        e = e.strip()
        if not e:
            continue
        if not CSS_IDENT_RE.match(e):
            raise SystemExit(f"bad element id: {e!r} "
                             f"(letters/digits/_/-/. only, must start with a letter)")
        out.append(e)
    return out


def validate_bg(bg: str | None) -> str | None:
    if bg is None:
        return None
    if not HEX_COLOR_RE.fullmatch(bg):
        raise SystemExit(f"--bg must be a hex color like '#FFFFFF', got {bg!r}")
    return bg


def warn_missing_ids(svg: str, elements: list[str]) -> None:
    if not elements:
        return
    ids = set(ATTR_ID_RE.findall(svg))
    missing = [e for e in elements if e not in ids]
    if missing:
        print(f"warning: element id(s) not found in SVG: {', '.join(missing)}",
              file=sys.stderr)


def ensure_svg_id(svg: str, fallback: str) -> tuple[str, str]:
    """Return (svg_with_id, id). Add id= to <svg> if missing."""
    m = _svg_open(svg)
    if not m:
        raise SystemExit("not an SVG file (no <svg> tag found)")
    idm = ATTR_ID_RE.search(m.group(0))
    if idm:
        if not SVG_ID_SAFE_RE.match(idm.group(1)):
            raise SystemExit(f"svg root id {idm.group(1)!r} is unsafe for CSS selectors")
        return svg, idm.group(1)
    fallback = SAFE_STEM_RE.sub("-", fallback).strip("-") or "freepik_stories-svg"
    new_tag = m.group(0).replace("<svg", f'<svg id="{fallback}"', 1)
    return svg[: m.start()] + new_tag + svg[m.end():], fallback


def _scoped(prefix: str, elements: list[str]) -> str:
    """Qualify EVERY selector with the svg prefix — a bare `, #id2` would be a
    page-global selector that leaks outside the svg and ignores .animated."""
    if not elements:
        return prefix
    return ", ".join(f"{prefix} #{e}" for e in elements)


def build_animation_style(svg_id: str, elements: list[str], preset: str,
                          bg: str | None) -> str:
    """Mirror storyset's editor output: <style> as first child of <svg>.

    - pre-hide:  svg#ID:not(.animated) SEL {opacity: 0}   (entrance presets)
    - run:       svg#ID.animated SEL {animation: ...}
    The `.animated` class is what starts the show; without it elements stay
    hidden (entrance) so nothing flashes before the trigger fires.
    """
    keyframes, shorthand, _, is_loop = PRESETS[preset]
    rules = ""
    if not is_loop:
        rules += _scoped(f"svg#{svg_id}:not(.animated)", elements) + " {opacity: 0;}"
    if bg:
        rules += f"body {{ background: {bg}}}"
    rules += (f"{_scoped(f'svg#{svg_id}.animated', elements)} "
              f"{{animation: {shorthand};"
              f"transform-box: fill-box;transform-origin: center;}}")
    return rules + keyframes


def inject_style(svg: str, style: str) -> str:
    m = _svg_open(svg)
    if not m:
        raise SystemExit("not an SVG file (no <svg> tag found)")
    return svg[: m.end()] + f"<style>{style}</style>" + svg[m.end():]


def set_svg_class(svg: str, cls: str) -> str:
    m = _svg_open(svg)
    if not m:
        raise SystemExit("not an SVG file (no <svg> tag found)")
    tag = m.group(0)
    cm = ATTR_CLASS_RE.search(tag)
    if cm:
        new = tag.replace(cm.group(0), f'class="{cm.group(1)} {cls}"', 1)
    elif tag.endswith("/>"):  # self-closing root
        new = tag[:-2] + f' class="{cls}"/>'
    else:
        new = tag[:-1] + f' class="{cls}">'
    return svg[: m.start()] + new + svg[m.end():]


HTML_WRAPPER = """<!DOCTYPE html>
<html lang="en">
    <head>
        <meta charset="UTF-8">
        <title>Freepik Stories</title>
    </head>
    <body onload="setTimeout(function() {{document.querySelector('svg').classList.add('animated')}}, {delay})">
{svg}
    </body>
</html>"""


def cmd_animate(a: argparse.Namespace) -> None:
    src = Path(a.file)
    svg = read_text_or_exit(src)
    elements = validate_elements(a.elements)
    bg = validate_bg(a.bg)
    svg, svg_id = ensure_svg_id(svg, f"freepik_stories-{src.stem}")
    warn_missing_ids(svg, elements)
    style = build_animation_style(svg_id, elements, a.preset, bg)
    svg = inject_style(svg, style)
    if a.mode == "autoplay":
        svg = set_svg_class(svg, "animated")
    # mode "manual": class stays off — the page adds it via its own JS trigger.
    out = Path(a.out) if a.out else src.with_name(src.stem + "_animated.svg")
    write_or_exit(out, svg)
    print(f"saved {out} | preset={a.preset} mode={a.mode} id=#{svg_id}")


# ---------------------------------------------------------------------------
# render (server-side GIF/MP4 via the undocumented but open api/render)
# ---------------------------------------------------------------------------

def validate_render_blob(ctype: str, blob: bytes, fmt: str) -> None:
    """Fail closed: only write bytes that are actually the requested media.
    A 200 + JSON/text error body must not be saved as x.gif."""
    if not blob or "text/html" in ctype:
        raise SystemExit(f"render failed: server returned {ctype!r} instead of media")
    ok = blob.startswith((b"GIF87a", b"GIF89a")) if fmt == "gif" else blob[4:8] == b"ftyp"
    if not ok:
        raise SystemExit(f"render failed: unexpected payload "
                         f"({ctype!r}, magic={blob[:16]!r}) — endpoint contract may have changed")


def cmd_render(a: argparse.Namespace) -> None:
    src = Path(a.file)
    if src.suffix.lower() == ".html":
        html = read_text_or_exit(src)
        duration, is_loop = 1.0, False
        print("note: .html input — --preset/--elements/--bg ignored, sent as looped=false",
              file=sys.stderr)
    else:
        svg = read_text_or_exit(src)
        elements = validate_elements(a.elements)
        bg = validate_bg(a.bg)
        svg, svg_id = ensure_svg_id(svg, f"freepik_stories-{src.stem}")
        warn_missing_ids(svg, elements)
        style = build_animation_style(svg_id, elements, a.preset, bg)
        svg = inject_style(svg, style)
        _, _, duration, is_loop = PRESETS[a.preset]
        html = HTML_WRAPPER.format(delay=a.delay, svg=svg)
    # `length` is the recording window in seconds. The onload trigger fires at
    # a.delay ms, so default = trigger delay + one animation cycle. Shorten
    # --length if a frozen lead-in second is unwanted.
    length = a.length if a.length else round(a.delay / 1000 + duration, 2)
    payload = json.dumps({
        "animation": html,
        "format": a.format,
        "length": length,
        "width": a.width,
        "height": a.height,
        "looped": is_loop,
    }).encode("utf-8")
    print(f"rendering {a.format} {a.width}x{a.height} length={length}s "
          f"(server-side, may take 5-60s)...", file=sys.stderr)
    try:
        with _req(RENDER_URL, data=payload, accept="*/*", timeout=180) as r:
            ctype = r.headers.get("Content-Type", "")
            blob = _read_capped(r)
    except urllib.error.HTTPError as e:
        raise SystemExit(f"render failed: HTTP {e.code} — {e.read(4096)[:300]!r}\n"
                         f"(endpoint is undocumented; payload structure may have changed)")
    validate_render_blob(ctype, blob, a.format)
    out = Path(a.out) if a.out else src.with_suffix(f".{a.format}")
    write_or_exit(out, blob, binary=True)
    print(f"saved {out} ({len(blob)} bytes, {ctype})")


# ---------------------------------------------------------------------------

def main() -> None:
    try:
        sys.stdout.reconfigure(errors="replace")  # GBK consoles: never crash on --json
    except (AttributeError, ValueError):
        pass
    p = argparse.ArgumentParser(prog="storyset", description=__doc__.splitlines()[0])
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("search", help="search illustrations")
    s.add_argument("query")
    s.add_argument("--style", choices=STYLES, default=None)
    s.add_argument("--limit", type=int, default=10)
    s.add_argument("--json", action="store_true", help="machine-readable output")
    s.set_defaults(fn=cmd_search)

    d = sub.add_parser("download", help="download SVG/PNG")
    d.add_argument("--slug", help="illustration slug, e.g. developer-activity")
    d.add_argument("--style", choices=STYLES, default="amico")
    d.add_argument("--url", help="direct stories.freepiklabs.com asset URL")
    d.add_argument("--format", choices=["svg", "png"], default="svg")
    d.add_argument("--transparent", action="store_true",
                   help="PNG without background (slug mode only)")
    d.add_argument("--recolor", metavar="OLD=NEW,...",
                   help="recolor SVG while saving; 'amico=#2196F3' targets the style primary")
    d.add_argument("-o", "--out", default=".")
    d.set_defaults(fn=cmd_download)

    pl = sub.add_parser("palette", help="list dominant SVG colors")
    pl.add_argument("file")
    pl.add_argument("--top", type=int, default=12)
    pl.add_argument("--style-hint", action="store_true",
                    help="flag style primaries present in the top list")
    pl.set_defaults(fn=cmd_palette)

    rc = sub.add_parser("recolor", help="rewrite hex colors in an SVG")
    rc.add_argument("file")
    rc.add_argument("--map", required=True, metavar="OLD=NEW,...")
    rc.add_argument("-o", "--out")
    rc.set_defaults(fn=cmd_recolor)

    an = sub.add_parser("animate", help="make an animated SVG (CSS keyframes)")
    an.add_argument("file")
    an.add_argument("--preset", choices=list(PRESETS), default="fadeIn")
    an.add_argument("--elements", help="comma-separated element ids; default = whole svg")
    an.add_argument("--mode", choices=["autoplay", "manual"], default="autoplay",
                    help="autoplay (default) starts immediately — required for "
                         "<img> embedding; manual waits for your JS to add the "
                         ".animated class (inline svg only)")
    an.add_argument("--bg", help="background hex, e.g. '#FFFFFF'")
    an.add_argument("-o", "--out")
    an.set_defaults(fn=cmd_animate)

    rn = sub.add_parser("render", help="render SVG to GIF/MP4 (server-side; uploads the file!)")
    rn.add_argument("file", help="SVG file (or pre-built animation .html)")
    rn.add_argument("--preset", choices=list(PRESETS), default="fadeIn")
    rn.add_argument("--elements", help="comma-separated element ids")
    rn.add_argument("--format", choices=["gif", "mp4"], default="gif")
    rn.add_argument("--length", type=float, help="recording seconds "
                    "(default: trigger delay + one animation cycle)")
    rn.add_argument("--width", type=int, default=500)
    rn.add_argument("--height", type=int, default=500)
    rn.add_argument("--delay", type=int, default=1000,
                    help="ms before animation starts (matches storyset editor)")
    rn.add_argument("--bg", default="#FFFFFF")
    rn.add_argument("-o", "--out")
    rn.set_defaults(fn=cmd_render)

    args = p.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
