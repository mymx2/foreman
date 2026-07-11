# Project Guide

| File      | Who reads it  | What it defines                               |
| --------- | ------------- | --------------------------------------------- |
| README.md | Humans        | What the project is                           |
| AGENTS.md | Coding agents | How to build the project                      |
| DESIGN.md | Design agents | How the project should look and feel          |
| SPEC.md   | Coding agents | What we're building and why (per sub-project) |

`DESIGN.md` and `SPEC.md` are not placed at the monorepo root. They live in each sub-project's own directory under `projects/`. This is intentional — different targets (admin dashboard, H5 mobile web, tablet, etc.) each have their own visual language, layout conventions, and component patterns, so a single shared design spec would be too coarse to be useful.

# Vite+

This project uses **Vite+** (`vp`) as the unified CLI. Prefer `vp` over pnpm/npm/yarn when available.

- `vp help` to list all commands
- `vp <command> --help` for details on a specific command

```shell
vp run fmt       # format
vp run up        # update dependencies
vp check --fix   # lint & auto-fix
vp dev           # start Vite dev server
vp build         # build project
```

> `vp <cmd>` runs the Vite+ built-in; `vp run <cmd>` runs the package.json script. If a same-named script exists in package.json, always use `vp run`.

# Agent Skills

**Production-grade engineering skills for AI coding agents.**

Skills encode the workflows, quality gates, and best practices that senior engineers use when building software. These ones are packaged so AI agents follow them consistently across every phase of development.

![Addy's Agent Skills](https://addyosmani.com/assets/images/addys-agent-skills.jpg)

```
  DEFINE          PLAN           BUILD          VERIFY         REVIEW          SHIP
 ┌──────┐      ┌──────┐      ┌──────┐      ┌──────┐      ┌──────┐      ┌──────┐
 │ Idea │ ───▶ │ Spec │ ───▶ │ Code │ ───▶ │ Test │ ───▶ │  QA  │ ───▶ │  Go  │
 │Refine│      │  PRD │      │ Impl │      │Debug │      │ Gate │      │ Live │
 └──────┘      └──────┘      └──────┘      └──────┘      └──────┘      └──────┘
  /spec          /plan          /build        /test         /review       /ship
```

---

## Commands

8 slash commands that map to the development lifecycle. Each one activates the right skills automatically.

| What you're doing     | Command          | Key principle               |
| --------------------- | ---------------- | --------------------------- |
| Define what to build  | `/spec`          | Spec before code            |
| Plan how to build it  | `/plan`          | Small, atomic tasks         |
| Build incrementally   | `/build`         | One slice at a time         |
| Prove it works        | `/test`          | Tests are proof             |
| Review before merge   | `/review`        | Improve code health         |
| Audit web performance | `/webperf`       | Measure before you optimize |
| Simplify the code     | `/code-simplify` | Clarity over cleverness     |
| Ship to production    | `/ship`          | Faster is safer             |

Want fewer manual steps once the spec exists? **`/build auto`** generates the plan and implements every task in a single approved pass — you approve the plan once, then it runs autonomously. It removes the human stepping _between_ tasks, not the verification: every task is still test-driven and committed individually, and it pauses on failures or risky steps.

Skills also activate automatically based on what you're doing — designing an API triggers `api-and-interface-design`, building UI triggers `frontend-ui-engineering`, and so on.

---

## All 24 Skills

The commands above are entry points. The pack includes 24 skills total — 23 lifecycle skills plus the `using-agent-skills` meta-skill. Each skill is a structured workflow with steps, verification gates, and anti-rationalization tables. You can also reference any skill directly.

### Meta - Discover which skill applies

| Skill                                                            | What It Does                                                                      | Use When                                           |
| ---------------------------------------------------------------- | --------------------------------------------------------------------------------- | -------------------------------------------------- |
| [using-agent-skills](.agents/skills/using-agent-skills/SKILL.md) | Maps incoming work to the right skill workflow and defines shared operating rules | Starting a session or deciding which skill applies |

### Define - Clarify what to build

| Skill                                                                      | What It Does                                                                                                                                   | Use When                                                                   |
| -------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------- |
| [interview-me](.agents/skills/interview-me/SKILL.md)                       | One-question-at-a-time interview that extracts what the user actually wants instead of what they think they should want, until ~95% confidence | The ask is underspecified, or the user invokes "interview me" / "grill me" |
| [idea-refine](.agents/skills/idea-refine/SKILL.md)                         | Structured divergent/convergent thinking to turn vague ideas into concrete proposals                                                           | You have a rough concept that needs exploration                            |
| [spec-driven-development](.agents/skills/spec-driven-development/SKILL.md) | Write a PRD covering objectives, commands, structure, code style, testing, and boundaries before any code                                      | Starting a new project, feature, or significant change                     |

### Plan - Break it down

| Skill                                                                              | What It Does                                                                                  | Use When                                     |
| ---------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------- | -------------------------------------------- |
| [planning-and-task-breakdown](.agents/skills/planning-and-task-breakdown/SKILL.md) | Decompose specs into small, verifiable tasks with acceptance criteria and dependency ordering | You have a spec and need implementable units |

### Build - Write the code

| Skill                                                                            | What It Does                                                                                                                                                                | Use When                                                                                                                                             |
| -------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------- |
| [incremental-implementation](.agents/skills/incremental-implementation/SKILL.md) | Thin vertical slices - implement, test, verify, commit. Feature flags, safe defaults, rollback-friendly changes                                                             | Any change touching more than one file                                                                                                               |
| [test-driven-development](.agents/skills/test-driven-development/SKILL.md)       | Red-Green-Refactor, test pyramid (80/15/5), test sizes, DAMP over DRY, Beyonce Rule, browser testing                                                                        | Implementing logic, fixing bugs, or changing behavior                                                                                                |
| [context-engineering](.agents/skills/context-engineering/SKILL.md)               | Feed agents the right information at the right time - rules files, context packing, MCP integrations                                                                        | Starting a session, switching tasks, or when output quality drops                                                                                    |
| [source-driven-development](.agents/skills/source-driven-development/SKILL.md)   | Ground every framework decision in official documentation - verify, cite sources, flag what's unverified                                                                    | You want authoritative, source-cited code for any framework or library                                                                               |
| [doubt-driven-development](.agents/skills/doubt-driven-development/SKILL.md)     | Adversarial fresh-context review of every non-trivial decision in-flight - CLAIM → EXTRACT → DOUBT → RECONCILE → STOP, with optional user-authorized cross-model escalation | Stakes are high (production, security, irreversible), working in unfamiliar code, or a confident output is cheaper to verify now than to debug later |
| [frontend-ui-engineering](.agents/skills/frontend-ui-engineering/SKILL.md)       | Component architecture, design systems, state management, responsive design, WCAG 2.1 AA accessibility                                                                      | Building or modifying user-facing interfaces                                                                                                         |
| [api-and-interface-design](.agents/skills/api-and-interface-design/SKILL.md)     | Contract-first design, Hyrum's Law, One-Version Rule, error semantics, boundary validation                                                                                  | Designing APIs, module boundaries, or public interfaces                                                                                              |

### Verify - Prove it works

| Skill                                                                                  | What It Does                                                                                                    | Use When                                              |
| -------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------- |
| [browser-testing-with-devtools](.agents/skills/browser-testing-with-devtools/SKILL.md) | Chrome DevTools MCP for live runtime data - DOM inspection, console logs, network traces, performance profiling | Building or debugging anything that runs in a browser |
| [debugging-and-error-recovery](.agents/skills/debugging-and-error-recovery/SKILL.md)   | Five-step triage: reproduce, localize, reduce, fix, guard. Stop-the-line rule, safe fallbacks                   | Tests fail, builds break, or behavior is unexpected   |

### Review - Quality gates before merge

| Skill                                                                        | What It Does                                                                                                               | Use When                                                          |
| ---------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------- |
| [code-review-and-quality](.agents/skills/code-review-and-quality/SKILL.md)   | Five-axis review, change sizing (~100 lines), severity labels (Nit/Optional/FYI), review speed norms, splitting strategies | Before merging any change                                         |
| [code-simplification](.agents/skills/code-simplification/SKILL.md)           | Chesterton's Fence, Rule of 500, reduce complexity while preserving exact behavior                                         | Code works but is harder to read or maintain than it should be    |
| [security-and-hardening](.agents/skills/security-and-hardening/SKILL.md)     | OWASP Top 10 prevention, auth patterns, secrets management, dependency auditing, three-tier boundary system                | Handling user input, auth, data storage, or external integrations |
| [performance-optimization](.agents/skills/performance-optimization/SKILL.md) | Measure-first approach - Core Web Vitals targets, profiling workflows, bundle analysis, anti-pattern detection             | Performance requirements exist or you suspect regressions         |

### Ship - Deploy with confidence

| Skill                                                                                          | What It Does                                                                                             | Use When                                                            |
| ---------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------- |
| [git-workflow-and-versioning](.agents/skills/git-workflow-and-versioning/SKILL.md)             | Trunk-based development, atomic commits, change sizing (~100 lines), the commit-as-save-point pattern    | Making any code change (always)                                     |
| [ci-cd-and-automation](.agents/skills/ci-cd-and-automation/SKILL.md)                           | Shift Left, Faster is Safer, feature flags, quality gate pipelines, failure feedback loops               | Setting up or modifying build and deploy pipelines                  |
| [deprecation-and-migration](.agents/skills/deprecation-and-migration/SKILL.md)                 | Code-as-liability mindset, compulsory vs advisory deprecation, migration patterns, zombie code removal   | Removing old systems, migrating users, or sunsetting features       |
| [documentation-and-adrs](.agents/skills/documentation-and-adrs/SKILL.md)                       | Architecture Decision Records, API docs, inline documentation standards - document the _why_             | Making architectural decisions, changing APIs, or shipping features |
| [observability-and-instrumentation](.agents/skills/observability-and-instrumentation/SKILL.md) | Structured logging, RED metrics, OpenTelemetry tracing, symptom-based alerting - instrument as you build | Adding telemetry, or shipping anything that runs in production      |
| [shipping-and-launch](.agents/skills/shipping-and-launch/SKILL.md)                             | Pre-launch checklists, feature flag lifecycle, staged rollouts, rollback procedures, monitoring setup    | Preparing to deploy to production                                   |

---

## Agent Personas

Pre-configured specialist personas for targeted reviews:

| Agent                                                        | Role                     | Perspective                                                                                  |
| ------------------------------------------------------------ | ------------------------ | -------------------------------------------------------------------------------------------- |
| [code-reviewer](agents/code-reviewer.md)                     | Senior Staff Engineer    | Five-axis code review with "would a staff engineer approve this?" standard                   |
| [test-engineer](agents/test-engineer.md)                     | QA Specialist            | Test strategy, coverage analysis, and the Prove-It pattern                                   |
| [security-auditor](agents/security-auditor.md)               | Security Engineer        | Vulnerability detection, threat modeling, OWASP assessment                                   |
| [web-performance-auditor](agents/web-performance-auditor.md) | Web Performance Engineer | Core Web Vitals audit with Quick/Deep modes and a metric-honesty rule; run it via `/webperf` |

See [docs/agents.md](docs/agents.md) for the decision matrix, orchestration rules, and how personas compose with skills and slash commands.

---

## Reference Checklists

Quick-reference material that skills pull in when needed:

| Reference                                                           | Covers                                                                                                      |
| ------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------- |
| [definition-of-done.md](references/definition-of-done.md)           | Project-wide standing bar every change clears, contrasted with per-task acceptance criteria                 |
| [testing-patterns.md](references/testing-patterns.md)               | Test structure, naming, mocking, React/API/E2E examples, anti-patterns                                      |
| [security-checklist.md](references/security-checklist.md)           | Pre-commit checks, auth, input validation, headers, CORS, OWASP Top 10                                      |
| [performance-checklist.md](references/performance-checklist.md)     | Core Web Vitals targets, frontend/backend checklists, measurement commands                                  |
| [accessibility-checklist.md](references/accessibility-checklist.md) | Keyboard nav, screen readers, visual design, ARIA, testing tools                                            |
| [observability-checklist.md](references/observability-checklist.md) | On-call questions, structured logging, RED/USE metrics, tracing, symptom-based alerting, pre-launch gate    |
| [orchestration-patterns.md](references/orchestration-patterns.md)   | Endorsed multi-persona orchestration patterns, anti-patterns, and the "personas don't invoke personas" rule |

---

## How Skills Work

Every skill follows a consistent anatomy:

```
┌─────────────────────────────────────────────────┐
│  SKILL.md                                       │
│                                                 │
│  ┌─ Frontmatter ─────────────────────────────┐  │
│  │ name: lowercase-hyphen-name               │  │
│  │ description: Guides agents through [task].│  │
│  │              Use when…                    │  │
│  └───────────────────────────────────────────┘  │
│  Overview         → What this skill does        │
│  When to Use      → Triggering conditions       │
│  Process          → Step-by-step workflow       │
│  Rationalizations → Excuses + rebuttals         │
│  Red Flags        → Signs something's wrong     │
│  Verification     → Evidence requirements       │
└─────────────────────────────────────────────────┘
```

**Key design choices:**

- **Process, not prose.** Skills are workflows agents follow, not reference docs they read. Each has steps, checkpoints, and exit criteria.
- **Anti-rationalization.** Every skill includes a table of common excuses agents use to skip steps (e.g., "I'll add tests later") with documented counter-arguments.
- **Verification is non-negotiable.** Every skill ends with evidence requirements - tests passing, build output, runtime data. "Seems right" is never sufficient.
- **Progressive disclosure.** The `SKILL.md` is the entry point. Supporting references load only when needed, keeping token usage minimal.
