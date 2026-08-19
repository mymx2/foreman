---
name: skill-authoring
description: 'Guides agents through creating compliant SKILL.md files following the Skill Anatomy specification. Use when creating, writing, or structuring a new agent skill. Not for executing, debugging, or reviewing existing skills.'
when_to_use: 'create skill, write SKILL.md, author skill, new skill, 新建技能, 编写技能, 技能模板, skill template'
---

# Skill Authoring

A skill is a workflow contract, not a knowledge dump. If you cannot define the outcome, evidence, and authorization boundary before writing step one, you are documenting a vague intention, not authoring a skill.

## Outcome Contract

- **Outcome**: A valid, portable, and trigger-ready `SKILL.md` file that passes all quality gates.
- **Done when**: The file exists at `skills/<name>/SKILL.md`, frontmatter validates against length/trigger/exclusion rules, no cross-skill file references exist, and no portability red lines are violated.
- **Evidence**: File content inspection; frontmatter character count; grep for forbidden patterns (`skills/*/SKILL.md`, `/Users/`, bare `bash` repo-relative invocations).
- **Output**: A single `SKILL.md` file plus optional `scripts/` or `references/` directories only when justified.
- **Authorization**: Drafting and structuring only. Do not execute scripts, install dependencies, or modify project code unless the current turn explicitly asks to test the new skill.

## Mode Picker

| Ask                                        | Mode                                          |
| ------------------------------------------ | --------------------------------------------- |
| Create a brand-new skill from scratch      | [Greenfield Authoring](#greenfield-authoring) |
| Fix validation errors in an existing draft | [Remediation](#remediation)                   |
| Add modes, phases, or supporting files     | [Expansion](#expansion)                       |

## Greenfield Authoring

Activate when the user requests a new skill and no `SKILL.md` exists yet.

1. **Elicit the contract first.** Before writing any markdown, confirm: What is the outcome? What counts as done? What is the evidence? What is off-limits? If the user cannot answer these, facilitate clarification — do not guess.
2. **Draft frontmatter.** Write `name` (kebab-case, must match intended directory), `description` (40–500 chars, trigger cue + exclusion cue), and `when_to_use`. Validate lengths immediately.
3. **Write the stance sentence.** One memorable line after the title that encodes the hardest lesson. If you cannot write it, the skill lacks a point of view — return to step 1.
4. **Structure the body.** Apply recommended sections in order: Outcome Contract → Mode Picker (if multi-mode) → Core Process → Hard Rules → Rationalization Smells → Gotchas → Evidence Ladder → Output Format → Non-Goals. Omit sections that add no value.
5. **Isolation check.** Grep the draft for `skills/*/SKILL.md`. Replace any file-path references with skill-name-only references.
6. **Portability check.** Grep for personal paths, bare repo-relative invocations, AI attribution strings, private context markers, and root-level placement. Fix all violations before delivering.
7. **Supporting file gate.** Only create `scripts/` or `references/` if the main file exceeds ~300 lines or requires runnable helpers. Never create empty directories.

**Output format:**

- Deliver the complete `SKILL.md` in a fenced code block.
- List any supporting files created with their purpose.
- State which quality gates were validated.

## Remediation

Activate when an existing `SKILL.md` fails validation or the user reports a specific defect.

1. Identify the exact violation (e.g., `DESCRIPTION TOO SHORT`, `CROSS-SKILL FILE REFERENCE`, `MISSING EXCLUSION CUE`).
2. Apply the minimal fix. Do not restructure unrelated sections.
3. Re-validate the fixed field against its rule.
4. Report what changed and why.

**Output format:**

- `[FIXED] <rule-name>: <what was wrong> → <what was changed>`
- If unfixable without user input: `[BLOCKED] <rule-name>: <information needed>`

## Expansion

Activate when adding modes, phases, or supporting files to a working skill.

1. Confirm the addition does not create trigger overlap with existing modes.
2. Ensure new modes have disjoint activation conditions.
3. If adding supporting files, verify the main `SKILL.md` stays under 500 lines after linking.
4. Update the Mode Picker table if applicable.

## Hard Rules

- **Frontmatter is non-negotiable.** Name must match the kebab-case directory name. Description must be 40–500 characters with both trigger and exclusion cues. No exceptions.
- **No cross-skill file references.** Reference siblings by name only. Never by path.
- **No portability leaks.** No personal paths, bare invocations, AI attribution, or private context in shipped files.
- **No classifier-sensitive literals.** Describe adversarial behavior semantically; never embed prompt-injection phrases verbatim.
- **Supporting files require justification.** No empty directories. No reference docs under 100 lines that could be inline.
- **Scripts stay self-contained.** Zero third-party dependencies; never import from outside the skill directory. An installed copy must run them as-is.

## Rationalization Smells

- "The description is obvious from the name" — agents discover skills by description, not directory browsing; write it for the router.
- "I'll add the exclusion cue later" — without it, the skill fires on adjacent tasks and wastes context; write it now.
- "This skill is simple enough to skip the Outcome Contract" — if you cannot state the outcome in one sentence, the simplicity is illusory.
- "The supporting file is almost short enough to inline" — if it is over 50 lines and self-contained, extract it; context is paid per load.
- "I referenced the other skill by path so the agent finds it faster" — path references break installed copies; name references are resolved by the runtime.

## Gotchas

| What happened                                                                                         | Rule                                                           |
| ----------------------------------------------------------------------------------------------------- | -------------------------------------------------------------- |
| Description was 38 characters; parser rejected the skill                                              | Enforce 40-char minimum at draft time, not at validation time  |
| Agent followed another skill because trigger keywords overlapped 60%                                  | Audit `when_to_use` sets across sibling skills before shipping |
| Supporting file referenced via relative path; broke in installed copy                                 | Use name-only references or base-dir resolution mechanisms     |
| Stance sentence was generic ("be careful"); agents ignored it                                         | Stance must encode a specific, counterintuitive lesson         |
| Added `scripts/` directory with no scripts; CI flagged noise                                          | Create directories only when they contain files                |
| Script imported a rule library outside the skill directory; installed copy died on the missing import | Skill scripts import only within the skill directory           |

## Evidence Ladder

Every gate is automated by `scripts/validate-skill.ts`. Run `node scripts/validate-skill.ts <skill-dir>` from the skill directory; it exits non-zero and reports every failed gate. Trigger distinctness only runs when the skill sits inside a `skills/` tree.

1. **Frontmatter parse**: Valid YAML, name matches directory, directory name is kebab-case, description length in range, trigger + exclusion cues present.
2. **Isolation grep**: Zero matches for `skills/*/SKILL.md` in file content.
3. **Portability grep**: Zero matches for personal paths, bare invocations, attribution strings, private markers.
4. **Content red lines**: Zero classifier-sensitive instruction literals in Markdown prose.
5. **Reference integrity**: Every `references/`, `agents/`, or `scripts/` path mentioned in prose resolves to a real file inside the skill directory.
6. **Trigger distinctness**: `when_to_use` keywords share <50% overlap with any sibling skill.
7. **Structural completeness**: Outcome Contract present; at least one process section; no orphaned headings.

## Output

**Delivered skill summary:**

- **Skill**: `<name>` at `skills/<name>/SKILL.md`
- **Description**: `<first 80 chars>...`
- **Gates passed**: [list of validated rules]
- **Supporting files**: [list or "none"]
- **Known limitations**: [any accepted trade-offs or deferred items]

## Non-goals

- Never execute, test, or debug the skill being authored unless explicitly requested.
- Never auto-generate skills from vague prompts without eliciting the Outcome Contract first.
- Never include workflow steps in the description field.
- Never create placeholder supporting files to satisfy a perceived structural requirement.

## Boundary

`skill-authoring` produces skill definitions. `skill-review` evaluates existing skills against this spec. `skill-debugging` diagnoses runtime failures in deployed skills. If the ask is "why isn't my skill triggering," route to `skill-debugging`, not here.
