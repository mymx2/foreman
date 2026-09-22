---
name: mobile-use
description: "Discover, operate, and verify Android, HarmonyOS, and iOS devices through the host toolchain (adb, hdc, simctl) — no vendor IDE plugin required. Use when you need device discovery, semantic UI interaction (tap/swipe/type), screenshots, screen recording, or native-test execution from the command line. Not for ordinary mobile source editing without runtime verification, nor for installing or provisioning SDKs, emulators, or devices."
---

# Mobile Use

The hardest lesson: this skill only drives devices the host toolchain can
already reach. An empty device list means no reachable device — it never means
the SDK is absent. Run `doctor` before concluding anything about the machine.

## Outcome Contract

- **Outcome**: a reachable device is discovered, driven through UI steps, and
  the requested evidence layer is captured and reported.
- **Done when**: the exact device (`surfaceId`/`sessionId`) resolved uniquely
  and the claimed evidence layer (interactive / native-test / repair) was
  actually produced, with artifact URI and SHA-256 digest preserved.
- **Evidence**: structured CLI JSON envelopes; `data.output.outcome ==
  "passed"` for native tests; artifact digest for captured media.
- **Authorization**: `manage-app uninstall` requires explicit `confirm=true`.
  Starting an emulator or rebooting a device changes machine state — ask first
  unless the user already requested runtime execution.

## When to Use

- List devices reachable via adb (Android), hdc (HarmonyOS), or simctl (iOS).
- Tap, long-press, swipe, type, or send keys on a device screen.
- Capture screenshots or screen recordings with integrity digests.
- Run an exact native test (Android instrumentation via `am instrument`).
- Check whether the local toolchain is present (`doctor`).

## Route the task

1. Command schemas, flags, and the run-plan workflow: read
   [CLI](references/cli.md).
2. Evidence layers (captured vs inspected vs verified) and artifact integrity:
   read [Evidence](references/evidence.md).
3. Per-platform backend boundaries and capabilities: read
   [Platforms](references/platforms.md).
4. Symptom routing and clean error recovery: read
   [Troubleshooting](references/troubleshooting.md).

## Automation loop

The launcher is `scripts/mobile-use.mjs` under the directory containing this
`SKILL.md`. Derive that absolute path once and pass it directly to `node`; do
not depend on the workspace cwd.

1. Unsure the toolchain exists? Run `doctor --json`; report each platform's
   `status` (`ready` / `missing` / `unsupported`) and follow its `guidance`.
2. "What devices are available?" Run `inventory` or `list-targets`. Its scope
   is connected devices only — not a machine-wide SDK scan.
3. One semantic interaction: selector-first `tap` or `long-press` so resolution
   and input share one fresh UI snapshot.
4. Multiple steps: one versioned `run-plan`; it binds the uniquely selected
   session and returns bounded step evidence. Request failure screenshots or
   recording in the plan's `evidence` policy when media matters.
5. Explicit lifecycle, coordinates, text, or keys: `observe` → low-level `act`
   → `wait` / `assert`.
6. Installed-app verification: one exact `run-native-test` selector; require
   `data.output.outcome == "passed"`.
7. Invoke an operational command only when the device advertises the capability
   (see [Platforms](references/platforms.md)).

## Match evidence to the claim

- Interactive: the device completed `observe -> act -> assert`.
- Native target test: one exact instrumentation selector returned
  `data.output.outcome == "passed"`.
- Repair: the same frozen plan failed for the intended behavior before the fix
  and passed after it.

Do not substitute a UI `assert` for a native runner result, and never describe
an artifact as visually inspected merely because its path or digest returned.

## Platform boundaries

- **Android**: full backend via adb — discovery, uiautomator semantics, input,
  screenshot, screenrecord, app management, logcat, `am instrument`.
- **HarmonyOS**: via hdc — discovery, uitest semantics, `uiInput` input,
  screenshot, app launch/terminate.
- **iOS**: via simctl + WebDriverAgent (macOS only) — discovery, boot, WDA
  semantics (observe/act/assert via `MOBILE_USE_WDA_URL`, default
  `http://localhost:8100`), screenshot, app lifecycle.

## Safety and reporting

- Do not install SDKs, emulators, or devices as a side effect. `doctor` reports
  what is missing and its setup guidance; provisioning is the user's choice.
- Report build, interactive, native-test, and repair evidence separately, and
  name every unverified platform or layer.
- Captured media can contain account data or notifications; capture only when
  material and keep provenance metadata with the artifact.
