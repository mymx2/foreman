# Agent Standards

Research first, build second. Test before shipping. Deliver a finished product, not a proposal.

- Include tests, include documentation, do it thoroughly
- Never leave things unresolved if wrapping up takes just five more minutes
- Never use a band-aid fix when the proper solution is within reach

---

# Project Guide

| File       | Who reads it  | What it defines                                     |
| ---------- | ------------- | --------------------------------------------------- |
| README.md  | Humans        | What the project is                                 |
| AGENTS.md  | Coding agents | How to build the project                            |
| DESIGN.md  | Design agents | How the project should look and feel                |
| tasks/*.md | Coding agents | Naming conventions for disposable working artifacts |

Sub-project-level `AGENTS.md` and `DESIGN.md` live under `projects/`, with each sub-project carrying only the files it needs.

---

# Working Artifacts

Two tiers of planning documents:

| Tier       | Location                                           | Lifecycle                                          |
| ---------- | -------------------------------------------------- | -------------------------------------------------- |
| Durable    | `projects/<sub>/AGENTS.md`                         | Living guide, git-tracked                          |
| Disposable | `tasks/__<sub>/YYYYMMDD/NN-<type>-<kebab-slug>.md` | One-shot, NOT git-tracked (`**/__*` is gitignored) |

Disposable types and naming rules are defined by the templates in `tasks/`: `plan.md`, `todo.md`, `draft.md`, `audit.md`. `NN` is a per-day sequence shared across artifacts of one request - a plan and its todo/draft/audit share the same `NN`.

## Who Produces What

| Moment                                        | Artifact                                                                   |
| --------------------------------------------- | -------------------------------------------------------------------------- |
| Planning a feature (e.g. via `/think`)        | `NN-plan-<slug>.md` - approval gate; do NOT implement before user approves |
| Plan approved, ready to build                 | `NN-todo-<slug>.md` - checklist, update as tasks complete                  |
| Early exploration, unshaped idea              | `NN-draft-<slug>.md`                                                       |
| Pre-merge review or audit (e.g. via `/check`) | `NN-audit-<slug>.md` - same `NN` as the plan it audits                     |

## Rules

- Before building in a sub-project, read its `projects/<sub>/AGENTS.md` plus the latest plan/todo pair under `tasks/__<sub>/`.
- Progress lives in todo; decisions that outlive the task get promoted back into `AGENTS.md` / `DESIGN.md`, never left rotting in `tasks/__*`.
- `tasks/*.md` (root level) are convention docs - edit them only to change the convention itself.
