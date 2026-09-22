# Mobile Use CLI

The launcher is `scripts/mobile-use.mjs` under the directory containing the
loaded `SKILL.md`. Derive that absolute path once and pass it directly to
`node`; do not depend on the workspace cwd:

```bash
node "/absolute/loaded-skill/scripts/mobile-use.mjs" inventory --json
```

Every successful command writes one versioned JSON object to stdout; failures
write one to stderr. Inspect structured `error.code`, not human messages:

```json
{"schemaVersion":1,"ok":false,"command":"tap","error":{"code":"phone.selector.ambiguous","message":"..."}}
```

Stable exit classes: `0` success, `2` invalid command/arguments, `3` missing or
stale surface/session/target, `4` selector/revision/assertion failure, `5`
unsupported capability, `6` broker failure, `1` other failure. Command and flag
names accept kebab-case or underscore form.

## Environment check

```bash
node "/absolute/loaded-skill/scripts/mobile-use.mjs" doctor --json
node "/absolute/loaded-skill/scripts/mobile-use.mjs" doctor --platform android --json
```

`doctor` probes the host for adb (Android SDK), hdc (OpenHarmony), and xcrun
simctl (iOS, macOS only) and reports each platform's `status` plus `guidance`.
`--platform all` evaluates every product platform, so iOS reports `unsupported`
off macOS. A `ready` status proves the toolchain binary exists and responds; it
does not prove a device is connected or booted.

## Discovery

- `inventory` — aggregated surfaces, targets, sessions. Scope is
  `connected_devices`: devices the toolchain can already reach. Empty is not
  proof the SDK is absent; run `doctor`.
- `list-targets` — per-device targets with `surfaceId`, `targetId`, `platform`,
  `runtimeKind`, and advertised `targetCapabilities`.
- `list-sessions` — attachable sessions (currently one per online device).

Surface IDs are stable per backend: `adb-android`, `hdc-harmony`, `simctl-ios`.
The `targetId`/`sessionId` is the device serial (Android), connect key
(HarmonyOS), or Simulator UDID (iOS).

## Semantic interaction

Selector-first `tap` / `long-press` resolve the element and act in one call:

```bash
node "/absolute/loaded-skill/scripts/mobile-use.mjs" tap \
  --surface-id adb-android --session-id emulator-5554 \
  --selector-json '{"identifier":"com.example:id/login"}' --json
```

Selectors accept `ref`, `identifier`, `label`, `role`, `type` and must resolve
uniquely. Prefer stable native identifiers (Android `resource-id`), then a
unique semantic label. Native accessibility/UITest nodes are not DOM elements.

Lower-level flow when you need coordinates, text, or keys:

1. `observe` — returns a snapshot with per-element `ref`, `identifier`,
   `label`, `role`, `type`, `center`, plus `elementCount`. Use `--mode full`
   for every node instead of interactive-only.
2. `act` — `--action-json` one of:
   `{"kind":"tap","selector":{...}}`, `{"kind":"long-press","selector":{...},"durationMs":800}`,
   `{"kind":"swipe","from":{"x":540,"y":1800},"to":{"x":540,"y":600},"durationMs":300}`,
   `{"kind":"text","text":"hello"}` (Android input; spaces become `%s`),
   `{"kind":"key","key":"KEYCODE_BACK"}`.
   A swipe whose `from` point lands on a clickable element also triggers that
   element's click on the down event; pick a start point clear of buttons.
3. `wait` — `--condition-json` `{"kind":"present","selector":{...}}`,
   `{"kind":"absent","selector":{...}}`, or `{"kind":"stable"}` with
   `--timeout-ms` / `--poll-interval-ms`.
4. `assert` — `--selector-json` plus optional `state` `present`/`absent`;
   returns `passed`. `state` is a top-level argument, not a selector field, so
   pass it via `--params-json` (a `state` key inside `--selector-json` is
   ignored):

   ```bash
   node "/absolute/loaded-skill/scripts/mobile-use.mjs" assert \
     --surface-id <s> --session-id <id> \
     --params-json '{"selector":{"label":"Welcome"},"state":"present"}' --json
   ```

   An `absent` assert passes only when the selector matches nothing; a
   `present` assert passes only when it resolves uniquely.

Refs and snapshots go stale after UI change; re-run `observe` and use fresh
refs rather than silently retrying a stale action.

## Run one versioned plan

`run-plan` binds one session and runs bounded steps. An exact
`surfaceId`/`sessionId` or a `platform` selector is required;
`policy: "existing"` is the default, `reuse-or-start` may start one uniquely
matched device.

```bash
node "/absolute/loaded-skill/scripts/mobile-use.mjs" run-plan --plan-json '{
  "schemaVersion": 1,
  "session": { "platform": "android", "policy": "reuse-or-start" },
  "keepSession": true,
  "evidence": { "screenshots": "on-failure", "recording": "off" },
  "steps": [
    {"kind":"launch_app","bundleId":"com.example.app"},
    {"kind":"tap","selector":{"identifier":"com.example:id/login"}},
    {"kind":"wait","condition":{"kind":"present","selector":{"label":"Welcome"}},"timeoutMs":5000},
    {"kind":"assert","selector":{"label":"Welcome"}},
    {"kind":"capture_screenshot"}
  ]
}' --json
```

Step kinds: `observe`, `tap`, `long_press`, `wait`, `assert`, `launch_app`,
`capture_screenshot`, `run_native_test`. Selection ambiguity, unknown steps,
invalid selectors, and unsupported capabilities fail closed. Step errors carry
`details.stepIndex` and `details.stepKind`.

Evidence defaults to off. `screenshots` is `off` or `on-failure` (best-effort,
never masks the step error). `recording` is `off` or `native` (Android
`screenrecord`); a plan that starts it stops it before session cleanup.

## Operational commands

- `capture-screenshot --surface-id ... --session-id ...` — PNG artifact with
  SHA-256 digest and `file:` URI (Android `screencap`, iOS `simctl io
  screenshot`, HarmonyOS `snapshot_display`).
- `record-screen --action start|status|stop` — MP4 via Android `screenrecord`.
  Recording state is persisted per device, so `start` and `stop` may be separate
  CLI invocations (and a `run-plan` can start/stop recording via
  `evidence.recording: "native"`). `stop` without a matching `start` returns
  `device.recording.inactive`; a second `start` while one is active returns
  `device.recording.active`.
- `manage-app --action list|install|launch|terminate|uninstall` — `install`
  needs `--path`, launch/terminate/uninstall need `--bundle-id`, and
  `uninstall` additionally needs `--confirm true`.
- `restart-target --surface-id ... --target-id ...` — reboot the device
  (Android `adb reboot`).
- `read-logs [--seconds N] [--limit N]` — Android `logcat`.
- `run-native-test --selector <id>` — Android instrumentation
  `com.example.TestClass#testMethod` via `am instrument`. Require
  `data.output.outcome == "passed"`; `assertion_failed` and `runner_mismatch`
  are distinct non-pass outcomes. The androidTest APK must already be installed
  on the device; this command runs the test, it does not build or install the
  test APK. The instrumentation runner is auto-resolved from `pm list
  instrumentation` by matching the test-class prefix against each
  instrumentation's target package. If resolution fails
  (`device.test.runner-unresolved`), install the test APK first, or pass
  `--runner <testPackage>/<runnerClass>` (or `--test-package <pkg>`) explicitly.
  A selector that matches zero tests yields `runner_mismatch`, never a pass.

## Swift Package preview cache (macOS only)

For iOS SwiftUI package previews, the cache is content-addressed. These commands
are macOS-only; other hosts report the platform as unsupported.

- `swift-cache-status` — report cache usage, including legacy entries.
- `swift-cache-prune [--max-age-days N] [--max-size-mb N] [--apply]` — dry run
  unless `--apply` is explicit.
- `swift-cache-clean (--package-swift <abs-path> | --cache-identity <id>) --confirm`
  — remove one exact broken-package cache entry.

Preserve artifact `uri`, `digest`, `mediaType`, `size`, `source`, and target.
Never inline media bytes into CLI JSON. Capturing an artifact and inspecting
its content are separate operations; see [Evidence](evidence.md).
