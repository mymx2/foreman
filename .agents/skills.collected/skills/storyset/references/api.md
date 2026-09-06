# Storyset / Freepik Stories API Reference

Reverse-engineered 2026-09 from the live site (JS bundles + network capture).
Undocumented but stable for years; no auth, no cookies required. Hosts:

- `storyset.com` — Nuxt SPA, detail pages `/illustration/{slug}/{style}`
- `stories.freepiklabs.com` — JSON API + asset storage (SVG/PNG)

## 1. Search/list API

```
GET https://stories.freepiklabs.com/api/vectors?query={q}&style={style}&page={n}&order=recent
Headers: Accept: application/json, Referer: https://storyset.com/, User-Agent: <browser UA>
```

Params: `query` (keyword), `style` (`amico|bro|cuate|pana|rafiki`), `page`
(30/page), `order`. Without `query` it lists everything (`style`-filtered or not).

Response envelope: `data: [...]`, `links.next` (follow to paginate; `null` at
the end), `meta.current_page/per_page`. Single-item endpoint
(`/api/vectors/{id}`) is **404** — resolve items via search + exact slug match.

Each `data` item:

| field | meaning |
|---|---|
| `id` | numeric vector id |
| `src` | **direct SVG URL** (`.../storage/{id}/....svg`) — the download |
| `preview` / `preview_no_bg` | PNG with / without background |
| `slug` | `{illustration-slug}/{style}` combined |
| `illustration.slug` / `illustration.name` | canonical slug + display name |
| `url` | detail page `https://storyset.com/illustration/{slug}/{style}` |
| `style` | one of the 5 styles |
| `tags[]` | `{name, slug, ...}` |
| `published_at`, `total_downloads` | metadata for sorting |
| `freepik_page` / `freepik_id` | source PSD on freepik.com |
| `type` | always `"storyset"` (observed) |

## 2. Animation mechanism (client-side, no server)

Storyset "animated SVG" = static SVG + injected CSS. Structure (mirrors the
editor's own download):

```html
<svg id="freepik_stories-{slug}" ...>
  <style>
    svg#ID:not(.animated) #Elem {opacity: 0;}              /* entrance: pre-hide */
    body { background: #FFFFFF}                            /* picked bg color */
    svg#ID.animated #Elem {animation: 1s 1 forwards
      cubic-bezier(.36,-0.01,.5,1.38) fadeIn;
      transform-box: fill-box; transform-origin: center;}
    @keyframes fadeIn { 0% {opacity:0} 100% {opacity:1} }
  </style>
  ...original svg content (elements keep their ids)...
</svg>
```

- `<style>` MUST be the first child of `<svg>`.
- The `.animated` class on `<svg>` is the trigger. Autoplay = class baked in;
  editor's "delay" variant ships a tiny script adding it later.
- Loop presets use `animation: 1.5s Infinite linear <name>;` and skip the
  pre-hide rule.
- No JavaScript, no SMIL — pure CSS. Plays in `<img>`, inline, and the render
  endpoint below.

## 3. Render API (GIF/MP4 export)

```
POST https://stories.freepiklabs.com/api/render
Content-Type: application/json

{
  "animation": "<!DOCTYPE html>...",   // complete self-contained HTML doc
  "format": "gif",                     // "gif" | "mp4" (both verified)
  "length": 2,                         // seconds (fractions OK) — recording window
  "width": 500, "height": 500,         // px (editor UI offers 50–800)
  "looped": false                      // false = entrance preset, true = loop
}
```

The HTML doc template (verified against live capture; synthetic rebuilds also
render successfully):

```html
<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8"><title>Freepik Stories</title></head>
<body onload="setTimeout(function() {document.querySelector('svg').classList.add('animated')}, 1000)">
  <!-- the animated <svg> from section 2, WITHOUT the .animated class -->
</body></html>
```

Notes:

- Zero external URLs allowed/needed in the doc — the renderer fetches nothing.
- Response: binary blob, `content-disposition: attachment`. `image/gif` /
  `video/mp4` content-type. Server takes 5–60s (headless recording) — use a
  120s+ timeout.
- Failure mode: HTTP 500 + `text/html` body after ~25s = payload contract
  mismatch (or endpoint change). Do not blind-retry.
- Rate headers observed: `x-ratelimit-limit: 30`. CORS: `access-control-allow-origin: *`.
- The onload trigger delay (1000ms) is inside the recording window; the
  editor's own `length` accounts for it. Script default: delay + one cycle.

## 4. Rate limits & politeness (observed + battle-tested defaults)

| surface | guidance |
|---|---|
| JSON API pagination | ~1 req / 2s serial; 429 → whole-host cooldown, honor `Retry-After` (script falls back to 20s, clamped to 120s, when the header is absent; observed site cooldown ~60s) |
| Asset downloads (storage) | more tolerant; small parallelism (≤10) OK |
| `/api/render` | ~30/window; each render costs 5–60s server-side — never batch |

## 5. License

Free tier: attribution link to storyset.com required. Paid Storyset/Freepik
license removes it. Details: https://storyset.com/terms
