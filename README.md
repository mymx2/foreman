# Project Guide

| File      | Who reads it  | What it defines                               |
| --------- | ------------- | --------------------------------------------- |
| README.md | Humans        | What the project is                           |
| AGENTS.md | Coding agents | How to build the project                      |
| DESIGN.md | Design agents | How the project should look and feel          |
| SPEC.md   | Coding agents | What we're building and why (per sub-project) |

The root `SPEC.md` is an index that points to each sub-project's spec. Sub-project-level `SPEC.md` and `DESIGN.md` live under `projects/`, with each sub-project carrying only the files it needs.

---

# Vite+ (vp): Prefer over raw package managers

This project uses [Vite+](https://vite.plus/). `vp` is a globally installed standalone binary — not an npm package. It must be installed before any project command can run.

**Bootstrap** (if `vp` is not on PATH):

```powershell
irm https://vite.plus/ps1 | iex   # Windows
curl -fsSL https://vite.plus | bash  # macOS/Linux
vp install                          # then install dependencies
```

**Built-in commands** (Vite+ manages these, never call the underlying tools directly):

| Command                            | What it does                                  |
| ---------------------------------- | --------------------------------------------- |
| `vp install`                       | Install dependencies                          |
| `vp add <pkg>` / `vp remove <pkg>` | Add/remove packages                           |
| `vp dev`                           | Start dev server                              |
| `vp build`                         | Production build                              |
| `vp test`                          | Run tests (Vitest)                            |
| `vp lint`                          | Lint (Oxlint)                                 |
| `vp fmt`                           | Format (Oxfmt)                                |
| `vp check`                         | Format + lint + type-check in one pass        |
| `vp exec <tool>`                   | Run a local binary from node_modules          |
| `vp dlx <tool>`                    | Download and run a package without installing |

**Package.json scripts**: use `vp run <script>`. If a same-named script exists in package.json, always use `vp run` — built-in commands take precedence and cannot be overridden (e.g. `vp run up` for dependency updates).

**Rules**:

- Never use `npm`, `pnpm`, `yarn`, `bun`, or `npx` directly in this project.
- Never call `vite`, `vitest`, `oxlint`, `oxfmt`, or `tsdown` directly.
- `vp help` lists all commands. `vp <command> --help` for details.
