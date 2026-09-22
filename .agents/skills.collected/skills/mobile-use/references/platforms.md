# Platform backends

One CLI, three platform backends. Each maps the same command contract onto the
host toolchain. Capabilities differ per platform — check `targetCapabilities`
in `list-targets` before invoking an operational command.

## Android — adb (full backend)

Surface `adb-android`. Requires Android SDK platform-tools (adb); emulator is
optional for virtual devices. Resolution order: `ANDROID_HOME`,
`ANDROID_SDK_ROOT`, then standard per-OS SDK paths.

- Discovery: `adb devices -l`. Runtime kind is inferred (`emulator` vs
  `physical`).
- Semantics: `uiautomator dump` parsed into elements (`resource-id`, `text`,
  `content-desc`, class, bounds). `observe` defaults to interactive-only nodes;
  `--mode full` returns all.
- Input: `input tap/swipe/text/keyevent`. Selector-first `tap` resolves the
  element center then taps.
- Screenshot: `screencap -p` → PNG. Recording: `screenrecord` → MP4.
- Apps: `pm list packages`, `pm install`, `monkey`/`am start` launch,
  `am force-stop` terminate, `pm uninstall`. Logs: `logcat`.
- Native test: `am instrument -w -r -e class <pkg.Class[#method]> <testPkg>/<runner>`.
  The runner component is auto-resolved from `pm list instrumentation` (matching
  the test class prefix against each instrumentation's target package); pass
  `--runner <pkg>/<runner>` or `--test-package <pkg>` to override. The test APK
  must already be installed. Outcomes: `passed` (≥1 test ran and passed),
  `assertion_failed` (reached the behavior assertion and failed),
  `runner_mismatch` (zero tests ran — empty/wrong selector or missing runner,
  never a pass), `crashed_before_assertion`.
- Recording state persists on disk (per-device under the artifact dir), so
  `record_screen start` / `stop` work across separate CLI invocations and across
  a `run-plan`'s `evidence.recording: "native"`.

## HarmonyOS — hdc

Surface `hdc-harmony`. Requires OpenHarmony `hdc` (from DevEco Studio, via
`DEVECO_SDK_HOME`, `HARMONYOS_SDK_HOME`, or PATH).

- Discovery: `hdc list targets`.
- Semantics: `uitest dumpLayout` parsed into elements (id, text, type, bounds).
  Selectors resolve against this tree; `--mode` has no effect on this backend.
- Input: `uitest uiInput click/longClick/swipe/inputText/keyEvent`.
- Screenshot: `snapshot_display` → PNG (via `hdc file recv`).
- Apps: `aa start -b <bundle> -a EntryAbility` launch, `aa force-stop` terminate.

## iOS — simctl + WebDriverAgent (macOS only)

Surface `simctl-ios`. Requires macOS with Xcode (`xcrun simctl`). Semantic UI
runs through WebDriverAgent (W3C WebDriver, default `http://localhost:8100`;
override with `MOBILE_USE_WDA_URL`).

- Discovery: `simctl list devices -j available`. `start_session` boots the
  Simulator; `stop_session` shuts it down.
- Semantics: WebDriverAgent `/source` parsed into elements (name, label, type,
  rect); selectors resolve against it.
- Input: WebDriverAgent `/actions` pointer gestures (tap, long-press, swipe) and
  key input for text.
- Screenshot: `simctl io <udid> screenshot` → PNG.
- Apps: `simctl launch/terminate/uninstall` by bundle id.
- When WebDriverAgent is not reachable, semantic commands return
  `device.driver.unavailable` naming the expected driver URL.

## Boundary rule

A missing capability is a hard boundary, not permission to improvise. If the
selected backend returns `device.capability.unsupported` or
`device.platform.unsupported`, report that boundary instead of substituting an
arbitrary shell command or claiming success.
