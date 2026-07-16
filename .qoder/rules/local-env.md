---
name: local-env
description: Use locally installed dedicated tools when applicable; prefer these tools over raw package managers or generic CLIs for matching projects. Fall back to alternative native commands only when the preferred tool lacks required functionality.
trigger: always_on
alwaysApply: true
---

Globally installed tools on this machine. When a project matches a tool's detection criteria, use that tool instead of raw package managers or generic CLIs. Each section below is one tool.

## Vite+ (vp)

Globally installed. Detection: `package.json` (root or workspace) lists `vite-plus` in `dependencies` or `devDependencies`. When in doubt, check before choosing a command.

### Bootstrap

`vp` is a globally installed standalone binary, not an npm package. It is required before any project command can run. If `vp` is not found on PATH:

1. **Windows**: `irm https://vite.plus/ps1 | iex`
2. **macOS/Linux**: `curl -fsSL https://vite.plus | bash`
3. Then run `vp install` to install project dependencies.

Do not fall back to `npm install` or `pnpm install` — the `prepare` script requires `vp` and will fail without it.

### Command Priority

`vp <cmd>` = Vite+ built-in; `vp run <cmd>` = package.json script. Built-in commands (`dev`, `build`, `test`, `lint`, `fmt`, `check`) take precedence and cannot be overridden — if a same-named script exists in package.json, always use `vp run`.

### Command Mapping

Use this table to override package-manager instincts:

| Instead of | Use |
|---|---|
| `npm install` / `pnpm install` / `yarn` / `bun install` | `vp install` |
| `npm add <pkg>` / `pnpm add <pkg>` | `vp add <pkg>` |
| `npm remove <pkg>` / `pnpm remove <pkg>` | `vp remove <pkg>` |
| `npm update` / `pnpm update` | `vp update` |
| `npm run dev` / `pnpm dev` / `vite` | `vp dev` |
| `npm run build` / `pnpm build` / `vite build` | `vp build` |
| `npm test` / `vitest` / `vitest run` | `vp test` |
| `eslint` / `oxlint` | `vp lint` |
| `prettier` / `oxfmt` | `vp fmt` |
| `npm run check` / `tsc --noEmit` | `vp check` |
| `npm run <script>` / `pnpm run <script>` | `vp run <script>` |
| `npx <tool>` | `vp exec <tool>` (local) or `vp dlx <tool>` (download & run once) |
| `npm create vite` / `create-vite` / `npx create-vite` | `vp create` |
| `npm run preview` / `serve dist` / `npx serve` | `vp preview` |
| `tsdown` | `vp pack` |
| `lint-staged` | `vp staged` |

### Hard Rules

- **Never use `npx`** in a Vite+ project. Use `vp exec <tool>` for local binaries or `vp dlx <tool>` to download and run without installing. Prefer `vp` forms over standalone shorthands (`vpx`, `vpr`) for consistency.
- **Never invoke `npm`, `pnpm`, `yarn`, or `bun` directly** for dependency management, scripts, or dev commands. Always go through `vp`.
- **Never call `vite`, `vitest`, `oxlint`, `oxfmt`, or `tsdown` directly.** These are managed by Vite+ and accessed via `vp <subcommand>`.
- `vp help` lists all commands. `vp <command> --help` shows details.

## ripgrep (rg)

Globally installed. Detection: always available — `rg` is a general-purpose search tool, not tied to any project type.

### Bootstrap

If `rg` is not found on PATH:

1. **Windows**: `winget install BurntSushi.ripgrep.MSVC`
2. **macOS**: `brew install ripgrep`
3. **Linux**: `apt install ripgrep` (Debian/Ubuntu) or `dnf install ripgrep` (Fedora)

### Usage

Prefer `rg` over `grep`, `findstr`, or `Select-String` for all text search needs. Key flags:

- `rg <pattern>` — recursive search in current directory (respects `.gitignore`)
- `rg -l <pattern>` — list files only
- `rg -i <pattern>` — case-insensitive
- `rg -t <type> <pattern>` — filter by file type (e.g., `-t py`, `-t js`)
- `rg --no-ignore` — search all files, ignore `.gitignore`
- `rg -C 3 <pattern>` — 3 lines of context around each match
- `rg -g '<glob>' <pattern>` — include/exclude files by glob

### Hard Rules

- Default to `rg` for text searches in files; prefer it over `grep`, `findstr`, `Select-String`, or `find`.
- `rg --help` for full option reference.

## fd

Globally installed. Detection: always available — `fd` is a general-purpose file search tool, not tied to any project type.

### Bootstrap

If `fd` is not found on PATH:

1. **Windows**: `winget install sharkdp.fd`
2. **macOS**: `brew install fd`
3. **Linux**: `apt install fd-find` (Debian/Ubuntu) or `dnf install fd-find` (Fedora)

### Usage

Prefer `fd` over `find`, `Get-ChildItem -Recurse`, or `dir /s` for filename searches. Key flags:

- `fd <pattern>` — recursive search by filename (regex by default, respects `.gitignore`)
- `fd -g '<glob>'` — glob-based search (e.g., `fd -g '*.ts'`)
- `fd -e <ext>` — filter by extension (e.g., `fd -e py`)
- `fd -t d` — directories only; `fd -t f` — files only
- `fd --no-ignore` — search all files, ignore `.gitignore`
- `fd -x <command>` — execute command on each result

### Hard Rules

- Default to `fd` for filename searches; prefer it over `find`, `Get-ChildItem`, or `dir /s`.
- `fd --help` for full option reference.
