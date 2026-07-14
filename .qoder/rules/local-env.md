---
name: local-env
description: Declares locally installed tools and enforces their use over raw equivalents. AI must prefer these tools in matching projects instead of falling back to default package managers or generic CLIs.
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
