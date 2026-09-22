# Troubleshooting

Read this when discovery, interaction, capture, or native-test evidence
disagrees. Locate the first layer whose evidence is missing instead of jumping
from symptom to a toolchain command.

## Triage loop

1. Run `doctor` to learn which platform toolchains are present and their
   `status`. `missing` means the binary was not found; `unsupported` means the
   host OS cannot run that backend.
2. Run `list-targets` and `list-sessions`. Treat the scope as connected
   devices, not a machine-wide SDK scan.
3. Pin the exact `surfaceId`, `targetId`, and `sessionId`; re-run discovery
   instead of reusing identifiers after a reconnect or reboot.
4. Inspect the structured `error.code` before changing anything.
5. Run `observe` before coordinate/ref `act`; re-observe after any UI change.
6. For multi-step work keep one exact session binding and record bounded step
   evidence and cleanup status.
7. Separate app launch from UI readiness: launch, then a bounded `wait`, then
   `assert` or native test.

## Symptom routing

| Symptom or error | Interpretation and next action |
| --- | --- |
| `inventory` / `list-targets` is empty | No device the toolchain can reach. Run `doctor`; connect/boot a device or emulator. Empty is not proof the SDK is absent. |
| `device.toolchain.missing` | The backend's binary (adb/hdc/xcrun) was not found. Follow `doctor` `guidance`; set the documented env root. |
| `device.platform.unsupported` | The host OS cannot run that backend (e.g. iOS off macOS). Report the boundary. |
| `device.adb.failed` / `device.hdc.failed` / `device.simctl.failed` | The tool ran but returned an error. Read the embedded stderr; it names the failing device or command. |
| `device.surface.stale` | Unknown `surfaceId`. Re-run `list-targets` and bind an ID from the same call. |
| `device.target.not-found` | The device went offline between discovery and use. Re-run discovery. |
| `phone.selector.not-found` | Re-observe, confirm the app is foreground and ready, then refine the selector. |
| `phone.selector.ambiguous` | Add a native `identifier`, `role`, `type`, or another constraint. Never pick a match by array position. |
| `device.capability.unsupported` | The backend does not implement that operation (e.g. iOS semantics). Check [Platforms](platforms.md); report the boundary. |
| `phone.wait.timeout` | The condition was not met in time. Keep launch as a completed stage and UI readiness as a separate failure; capture logs or a screenshot. |
| `device.test.runner-unresolved` | No instrumentation matched the test class on the device. Install the androidTest APK first, or pass `--runner <testPackage>/<runnerClass>`. |
| `run_native_test` outcome is `runner_mismatch` | Zero tests ran. The selector matched nothing (wrong class/method) or the runner did not reach it. It is never a pass; fix the selector or the installed test APK. |
| `run_native_test` outcome is not `passed` | Inspect `data.output.outcome`; keep `assertion_failed`, `runner_mismatch`, and infrastructure outcomes distinct. |
| `device.recording.inactive` | `record_screen stop` without a matching `start` on that device. |
| `device.recording.active` | A recording is already active on that device; stop it before starting another. |
| `device.recording.empty` | The recording file was empty after stop; screenrecord likely never started (check device state). |

Retry only after changing the discriminating condition: a newly connected
device, fresh observation, unique selector, exact identifier, restored
capability, or completed readiness condition. Repeating an unchanged command is
not additional evidence.

## Report the strongest proven layer

- **Toolchain**: `doctor` reported the platform `ready`.
- **Discovery**: the device appeared in `list-targets`.
- **Interactive**: the device completed the requested `observe -> act ->
  assert` workflow.
- **Native test**: one exact instrumentation selector returned
  `data.output.outcome == "passed"`.
- **Repair**: the same frozen plan failed before the fix and passed after it.

Name every unverified platform and layer. Infrastructure outcomes (missing
toolchain, offline device, build/install/launch failure, crash, timeout) must
not be reported as behavioral pass or failure.
