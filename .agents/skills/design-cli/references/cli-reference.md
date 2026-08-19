# @google/design.md CLI Reference

All commands accept a file path or `-` for stdin. Output defaults to JSON.

## Installation

```bash
npm install @google/design.md
```

On **Windows**, quote the package name if your shell treats `@` specially (PowerShell, some terminals):

```bash
npm install "@google/design.md"
```

Or run directly (always resolves from the public npm registry):

```bash
npx @google/design.md lint DESIGN.md
```

On **Windows/PowerShell**, this direct form can produce no output (or open `DESIGN.md` in your Markdown editor) because the `.md` suffix in the `design.md` bin name collides with the Windows Markdown file association during command resolution. Run the dot-free `designmd` alias instead — point `npx` at the package with `-p`, then invoke `designmd`:

```bash
npx -p @google/design.md designmd lint DESIGN.md
```

The `designmd` shim resolves to the same entrypoint and works identically across all platforms. The same applies when invoking the CLI directly from a `package.json` script: use `designmd`, not `design.md`.

## `npm error ENOVERSIONS` ("No versions available for @google/design.md")

The CLI is published as `@google/design.md` on npm. `ENOVERSIONS` almost always means npm is not querying the public registry (custom `registry=` in `.npmrc`, a corporate mirror that has not synced this package, or a misconfigured `@google:registry` for the `@google` scope).

Check your effective registry:

```bash
npm config get registry
```

For a normal install from the internet it should be `https://registry.npmjs.org/`. After fixing config, retry with `npm cache clean --force` if a stale 404 was cached.

## `lint`

Validate a DESIGN.md file for structural correctness.

```bash
npx @google/design.md lint DESIGN.md
npx @google/design.md lint --format json DESIGN.md
cat DESIGN.md | npx @google/design.md lint -
```

| Option     | Type       | Default  | Description                          |
| :--------- | :--------- | :------- | :----------------------------------- |
| `file`     | positional | required | Path to DESIGN.md (or `-` for stdin) |
| `--format` | `json`     | `json`   | Output format                        |

Exit code `1` if errors are found, `0` otherwise.

## `diff`

Compare two DESIGN.md files and report token-level changes.

```bash
npx @google/design.md diff DESIGN.md DESIGN-v2.md
```

| Option     | Type       | Default  | Description                    |
| :--------- | :--------- | :------- | :----------------------------- |
| `before`   | positional | required | Path to the "before" DESIGN.md |
| `after`    | positional | required | Path to the "after" DESIGN.md  |
| `--format` | `json`     | `json`   | Output format                  |

Exit code `1` if regressions are detected (more errors or warnings in the "after" file).

## `export`

Export DESIGN.md tokens to other formats.

```bash
npx @google/design.md export --format json-tailwind DESIGN.md > tailwind.theme.json
npx @google/design.md export --format css-tailwind DESIGN.md > theme.css
npx @google/design.md export --format dtcg DESIGN.md > tokens.json
```

| Option     | Type                                                      | Default  | Description                          |
| :--------- | :-------------------------------------------------------- | :------- | :----------------------------------- |
| `file`     | positional                                                | required | Path to DESIGN.md (or `-` for stdin) |
| `--format` | `json-tailwind` \| `css-tailwind` \| `tailwind` \| `dtcg` | required | Output format                        |

| Format          | Output | Description                                                   |
| :-------------- | :----- | :------------------------------------------------------------ |
| `json-tailwind` | JSON   | Tailwind v3 `theme.extend` config object                      |
| `css-tailwind`  | CSS    | Tailwind v4 `@theme { ... }` block with CSS custom properties |
| `tailwind`      | JSON   | Alias for `json-tailwind`                                     |
| `dtcg`          | JSON   | W3C Design Tokens Format Module                               |

## `spec`

Output the DESIGN.md format specification (useful for injecting spec context into agent prompts).

```bash
npx @google/design.md spec
npx @google/design.md spec --rules
npx @google/design.md spec --rules-only --format json
```

| Option         | Type                 | Default    | Description                           |
| :------------- | :------------------- | :--------- | :------------------------------------ |
| `--rules`      | boolean              | `false`    | Append the active linting rules table |
| `--rules-only` | boolean              | `false`    | Output only the linting rules table   |
| `--format`     | `markdown` \| `json` | `markdown` | Output format                         |

## Linting Rules

The linter runs nine rules against a parsed DESIGN.md. Each rule produces findings at a fixed severity level.

| Rule                 | Severity | What it checks                                                                                                                |
| :------------------- | :------- | :---------------------------------------------------------------------------------------------------------------------------- |
| `broken-ref`         | error    | Token references (`{colors.primary}`) that don't resolve to any defined token                                                 |
| `missing-primary`    | warning  | Colors are defined but no `primary` color exists — agents will auto-generate one                                              |
| `contrast-ratio`     | warning  | Component `backgroundColor`/`textColor` pairs below WCAG AA minimum (4.5:1)                                                   |
| `orphaned-tokens`    | warning  | Color tokens defined but never referenced by any component                                                                    |
| `token-summary`      | info     | Summary of how many tokens are defined in each section                                                                        |
| `missing-sections`   | info     | Optional sections (spacing, rounded) absent when other tokens exist                                                           |
| `missing-typography` | warning  | Colors are defined but no typography tokens exist — agents will use default fonts                                             |
| `section-order`      | warning  | Sections appear out of the canonical order defined by the spec                                                                |
| `unknown-key`        | warning  | A top-level YAML key looks like a typo of a known schema key (e.g. `colours:` → `colors:`); custom extension keys stay silent |

## Programmatic API

The linter is also available as a library:

```typescript
import { lint } from '@google/design.md/linter'

const report = lint(markdownString)

console.log(report.findings) // Finding[]
console.log(report.summary) // { errors, warnings, info }
console.log(report.designSystem) // Parsed DesignSystemState
```

## Design Token Interoperability

DESIGN.md tokens are inspired by the W3C Design Token Format. The `export` command converts tokens to other formats:

- **Tailwind v3 config (JSON)** — emits a `theme.extend` JSON object for `tailwind.config.js`. `--format tailwind` is a backwards-compatible alias.
- **Tailwind v4 theme (CSS)** — emits a CSS `@theme { ... }` block using Tailwind v4's CSS-variable token namespaces (`--color-*`, `--font-*`, `--text-*`, `--leading-*`, `--tracking-*`, `--font-weight-*`, `--radius-*`, `--spacing-*`).
- **DTCG tokens.json** (W3C Design Tokens Format Module).
