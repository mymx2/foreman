import { mkdir, writeFile, readFile, unlink } from "node:fs/promises";
import path from "node:path";
import { pathToFileURL } from "node:url";
import { createHash } from "node:crypto";
import {
  defaultArtifactDirectory,
  findAndroidSdk,
  runTool,
  runToolRaw,
  runToolBackgroundPid,
  type AndroidSdk,
  type ToolOptions,
} from "./exec.ts";
import { buildObservation, parseUiAutomatorXml, resolveSelector } from "./uiautomator.ts";
import { classifyInstrumentationOutcome } from "./instrumentation.ts";
import { cliError, isRecord } from "./types.ts";
import type {
  Artifact,
  DeviceSession,
  DeviceTarget,
  JsonRecord,
  Observation,
  Selector,
} from "./types.ts";

const SURFACE_ID = "adb-android";
const ADAPTER_ID = "android-adb";

const ANDROID_TARGET_CAPABILITIES = Object.freeze([
  "device.frame.screenshot",
  "device.app.list",
  "device.app.install",
  "device.app.launch",
  "device.app.terminate",
  "device.app.uninstall",
  "device.logs.read",
  "device.test.run",
  "device.recording.native",
]);

interface AndroidDevice {
  serial: string;
  state: string;
  model: string;
  product?: string;
  runtimeKind: "emulator" | "physical";
}

interface InstrumentationInfo {
  package: string;
  runner: string;
  targetPackage: string;
}

interface RecordingState {
  remote: string;
  pid?: number;
  startedAt: string;
}

// ── shell 注入防护：拼进 `adb shell` 的动态值先校验或转义 ──────────────────

/** 校验一个值是安全整数（坐标、时长），否则抛 cli.argument。 */
function requireInt(value: unknown, name: string): number {
  if (!Number.isInteger(value)) {
    throw cliError(
      "phone.cli.argument",
      `${name} must be an integer, got ${JSON.stringify(value)}.`,
    );
  }
  return value as number;
}

/** Android keyevent：仅接受 KEYCODE_ 名（字母数字下划线）或纯数字键码。 */
const KEYCODE_RE = /^(?:KEYCODE_[A-Z0-9_]+|\d+)$/;
function requireKeyCode(value: unknown): string {
  if (typeof value !== "string" || !KEYCODE_RE.test(value)) {
    throw cliError(
      "phone.cli.argument",
      `key must be a KEYCODE_ name or a numeric key code, got ${JSON.stringify(value)}.`,
    );
  }
  return value;
}

/** Android 包名/组件：字母数字、点、下划线、斜杠、$、横线。拒绝 shell 元字符。 */
const PACKAGE_RE = /^[A-Za-z0-9._/$-]+$/;
function requirePackageName(value: unknown, name = "package"): string {
  if (typeof value !== "string" || !PACKAGE_RE.test(value)) {
    throw cliError(
      "phone.cli.argument",
      `${name} contains unsafe characters: ${JSON.stringify(value)}.`,
    );
  }
  return value;
}

/** instrumentation selector `pkg.Outer$Inner[#method]`：包名字符集加 `#`。 */
const TEST_SELECTOR_RE = /^[A-Za-z0-9._/$-]+(#[A-Za-z0-9_$-]+)?$/;
function requireTestSelector(value: unknown): string {
  if (typeof value !== "string" || !TEST_SELECTOR_RE.test(value)) {
    throw cliError(
      "phone.cli.argument",
      `test selector contains unsafe characters: ${JSON.stringify(value)}.`,
    );
  }
  return value;
}

/**
 * 把任意文本安全嵌入 `adb shell` 的单引号字符串。
 * POSIX 单引号内无转义；正确形式是闭合引号 + `\'` + 重开引号（'\''）。
 * 同时把空格转为 Android `input text` 要求的 `%s`。
 */
export function shellQuoteInputText(text: string): string {
  return `'${text.replace(/ /g, "%s").replace(/'/g, `'\\''`)}'`;
}

let sdkPromise: Promise<AndroidSdk | undefined> | undefined;

async function sdk(): Promise<AndroidSdk> {
  if (!sdkPromise) sdkPromise = findAndroidSdk();
  const resolved = await sdkPromise;
  if (!resolved) {
    throw cliError(
      "device.toolchain.missing",
      "Android SDK not found. Set ANDROID_HOME or install Android SDK platform-tools. Run `doctor` for setup guidance.",
    );
  }
  return resolved;
}

async function adb(args: string[], options: ToolOptions = {}) {
  const { adb: adbPath } = await sdk();
  return runTool(adbPath, args, { errorCode: "device.adb.failed", ...options });
}

async function adbOnDevice(serial: string, args: string[], options: ToolOptions = {}) {
  return adb(["-s", serial, ...args], options);
}

async function adbShell(serial: string, shellCommand: string, options: ToolOptions = {}) {
  return adbOnDevice(serial, ["shell", shellCommand], options);
}

export async function listAndroidDevices(): Promise<AndroidDevice[]> {
  const { stdout } = await adb(["devices", "-l"]);
  const devices: AndroidDevice[] = [];
  for (const line of stdout.split("\n").slice(1)) {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith("*")) continue;
    const [serial, state, ...rest] = trimmed.split(/\s+/);
    if (!serial || state !== "device") continue;
    const props = Object.fromEntries(
      rest.map((token) => {
        const splitAt = token.indexOf(":");
        return splitAt === -1 ? [token, ""] : [token.slice(0, splitAt), token.slice(splitAt + 1)];
      }),
    );
    devices.push(
      Object.freeze({
        serial,
        state,
        model: props.model ?? serial,
        product: props.product,
        runtimeKind: /emulator|sdk_gphone|generic/i.test(props.model ?? serial)
          ? "emulator"
          : "physical",
      }),
    );
  }
  return devices;
}

export async function listLiveTargets(): Promise<DeviceTarget[]> {
  const devices = await listAndroidDevices();
  return devices.map((device) =>
    Object.freeze({
      surfaceId: SURFACE_ID,
      adapterId: ADAPTER_ID,
      targetId: device.serial,
      platform: "android" as const,
      targetName: device.model,
      runtimeKind: device.runtimeKind,
      state: "online",
      targetCapabilities: [...ANDROID_TARGET_CAPABILITIES],
    }),
  );
}

export async function listLiveSessions(): Promise<DeviceSession[]> {
  const devices = await listAndroidDevices();
  return devices.map((device) =>
    Object.freeze({
      surfaceId: SURFACE_ID,
      sessionId: device.serial,
      targetId: device.serial,
      platform: "android" as const,
      targetName: device.model,
      runtimeKind: device.runtimeKind,
      state: "attached",
      capabilities: Object.freeze([
        Object.freeze({ id: "device.frame.screenshot" }),
        Object.freeze({ id: "device.logs.read" }),
        Object.freeze({ id: "device.test.run" }),
        Object.freeze({ id: "device.recording.native" }),
      ]) as Array<{ id: string }>,
    }),
  );
}

export async function startPhoneUseSession(
  surfaceId: string,
  targetId: string,
): Promise<DeviceSession> {
  const sessions = await listLiveSessions();
  const session = sessions.find((candidate) => candidate.sessionId === targetId);
  if (!session) {
    throw cliError(
      "device.target.not-found",
      `Android device ${targetId} is not online. Run list-targets again.`,
    );
  }
  return session;
}

export async function stopPhoneUseSession(): Promise<{ stopped: boolean; note: string }> {
  return Object.freeze({ stopped: false, note: "ADB devices are not stopped by this skill." });
}

export async function invokePhoneUse(
  surfaceId: string,
  sessionId: string,
  method: string,
  input?: JsonRecord,
): Promise<unknown> {
  if (method === "observe") return observe(sessionId, input);
  if (method === "perform") return perform(sessionId, input);
  if (method === "act") return act(sessionId, input);
  if (method === "wait") return waitFor(sessionId, input);
  if (method === "assert") return assert(sessionId, input);
  throw new TypeError(`Unsupported method: ${method}`);
}

async function dumpUi(serial: string): Promise<string> {
  const remote = `/sdcard/window_dump.xml`;
  await adbShell(serial, `uiautomator dump ${remote}`).catch(() => {});
  const { stdout } = await adbShell(serial, `cat ${remote}`, { timeoutMs: 30_000 });
  if (!stdout.includes("<hierarchy")) {
    throw cliError(
      "device.observe.failed",
      "uiautomator dump returned no hierarchy. The screen may be off or a secure surface is shown.",
    );
  }
  return stdout;
}

async function observe(serial: string, input: JsonRecord = {}): Promise<Observation> {
  const xml = await dumpUi(serial);
  const all = parseUiAutomatorXml(xml);
  const elements = input?.mode === "full" ? all : all.filter((element) => element.interactive);
  return buildObservation(elements, "android", "uiautomator");
}

async function perform(serial: string, input: JsonRecord = {}) {
  const action = (input?.action ?? {}) as {
    kind?: string;
    selector?: Selector;
    durationMs?: number;
  };
  const xml = await dumpUi(serial);
  const elements = parseUiAutomatorXml(xml);
  const element = resolveSelector(elements, action.selector ?? {});
  const { x, y } = element.center;
  if (action.kind === "long-press") {
    const durationMs = requireInt(action.durationMs ?? 1_000, "long-press durationMs");
    await adbShell(serial, `input swipe ${x} ${y} ${x} ${y} ${durationMs}`);
  } else {
    await adbShell(serial, `input tap ${x} ${y}`);
  }
  const after = await observe(serial, {});
  return Object.freeze({
    uiChanged: true,
    element: Object.freeze({
      ref: element.ref,
      identifier: element.identifier,
      label: element.label,
      role: element.role,
      type: element.type,
    }),
    observation: after,
    receipt: Object.freeze({
      operationId: operationId("tap"),
      operation: "input.tap",
      status: "succeeded" as const,
    }),
  });
}

async function act(serial: string, input: JsonRecord = {}) {
  const action = (input?.action ?? {}) as {
    kind?: string;
    from?: { x: number; y: number };
    to?: { x: number; y: number };
    durationMs?: number;
    text?: string;
    key?: string;
  };
  const kind = action.kind;
  if (kind === "tap" || kind === "long-press") return perform(serial, input);
  if (kind === "swipe") {
    const from = action.from ?? ({ x: 0, y: 0 } as { x: number; y: number });
    const to = action.to ?? ({ x: 0, y: 0 } as { x: number; y: number });
    const fx = requireInt(from.x, "swipe from.x");
    const fy = requireInt(from.y, "swipe from.y");
    const tx = requireInt(to.x, "swipe to.x");
    const ty = requireInt(to.y, "swipe to.y");
    const durationMs = requireInt(action.durationMs ?? 300, "swipe durationMs");
    await adbShell(serial, `input swipe ${fx} ${fy} ${tx} ${ty} ${durationMs}`);
    return Object.freeze({ uiChanged: true, observation: await observe(serial, {}) });
  }
  if (kind === "text") {
    const text = String(action.text ?? "");
    await adbShell(serial, `input text ${shellQuoteInputText(text)}`);
    return Object.freeze({ uiChanged: true, observation: await observe(serial, {}) });
  }
  if (kind === "key") {
    await adbShell(serial, `input keyevent ${requireKeyCode(action.key)}`);
    return Object.freeze({ uiChanged: true, observation: await observe(serial, {}) });
  }
  throw new TypeError(`Unsupported act kind: ${kind}`);
}

async function waitFor(serial: string, input: JsonRecord = {}): Promise<Observation> {
  const condition = (input?.condition ?? {}) as { kind?: string; selector?: Selector };
  const timeoutMs = (input?.timeoutMs as number | undefined) ?? 10_000;
  const pollIntervalMs = (input?.pollIntervalMs as number | undefined) ?? 500;
  const deadline = Date.now() + timeoutMs;
  let lastObservation: Observation | undefined;
  while (Date.now() < deadline) {
    lastObservation = await observe(serial, {});
    if (condition.kind === "stable") return lastObservation;
    const found = findQuietly(lastObservation, condition.selector);
    if (condition.kind === "present" && found) return lastObservation;
    if (condition.kind === "absent" && !found) return lastObservation;
    await sleep(pollIntervalMs);
  }
  throw cliError(
    "phone.wait.timeout",
    `wait condition ${condition.kind} timed out after ${timeoutMs} ms.`,
  );
}

interface AssertResult {
  passed: boolean;
  reason?: string;
  element?: Partial<ReturnType<typeof resolveSelector>>;
  observation: Observation;
}

async function assert(serial: string, input: JsonRecord = {}): Promise<AssertResult> {
  // Single dump: build the observation and resolve the selector from the same
  // UI snapshot, so the two never observe different states.
  const xml = await dumpUi(serial);
  const all = parseUiAutomatorXml(xml);
  const elements = all.filter((element) => element.interactive);
  const observation = buildObservation(elements, "android", "uiautomator");
  let element: ReturnType<typeof resolveSelector> | undefined;
  try {
    element = resolveSelector(all, (input?.selector as Selector | undefined) ?? {});
  } catch (error) {
    const code = (error as { code?: string }).code;
    if (input?.state === "absent" && code === "phone.selector.not-found") {
      return Object.freeze({ passed: true, observation });
    }
    if (code?.startsWith("phone.selector")) {
      return Object.freeze({ passed: false, observation, reason: code });
    }
    throw error;
  }
  const passed = input?.state === "absent" ? false : true;
  return Object.freeze({
    passed,
    element: Object.freeze({
      ref: element.ref,
      identifier: element.identifier,
      label: element.label,
      role: element.role,
      type: element.type,
    }),
    observation,
  });
}

function findQuietly(observation: Observation, selector: Selector = {}): boolean {
  if (!selector || !observation?.elements) return false;
  return observation.elements.some((element) => {
    if (
      selector.identifier &&
      !(
        element.identifier === selector.identifier ||
        element.identifier?.endsWith(`/${selector.identifier}`)
      )
    )
      return false;
    if (selector.label) {
      const needle = selector.label.toLowerCase();
      if (!element.label?.toLowerCase().includes(needle)) return false;
    }
    if (selector.role && !element.role?.toLowerCase().includes(selector.role.toLowerCase()))
      return false;
    if (selector.type && !element.type?.toLowerCase().includes(selector.type.toLowerCase()))
      return false;
    return true;
  });
}

export async function invokeSessionOperation(
  surfaceId: string,
  sessionId: string,
  operation: string,
  capability: string,
  input: JsonRecord = {},
): Promise<unknown> {
  switch (operation) {
    case "device.capture.screenshot":
      return captureScreenshot(sessionId);
    case "device.logs.read":
      return readLogs(sessionId, input);
    case "device.test.run":
      return runNativeTest(sessionId, input);
    case "device.app.list":
      return manageApp(sessionId, "list", input);
    case "device.app.install":
      return manageApp(sessionId, "install", input);
    case "device.app.launch":
      return manageApp(sessionId, "launch", input);
    case "device.app.terminate":
      return manageApp(sessionId, "terminate", input);
    case "device.app.uninstall":
      return manageApp(sessionId, "uninstall", input);
    case "device.recording.start":
      return recordScreen(sessionId, "start");
    case "device.recording.status":
      return recordScreen(sessionId, "status");
    case "device.recording.stop":
      return recordScreen(sessionId, "stop");
    default:
      throw new TypeError(`Unsupported session operation: ${operation}`);
  }
}

export async function invokeTargetOperation(
  surfaceId: string,
  targetId: string,
  operation: string,
): Promise<unknown> {
  if (operation === "device.target.restart") {
    await adb(["-s", targetId, "reboot"]);
    return Object.freeze({ status: "succeeded", operation });
  }
  throw new TypeError(`Unsupported target operation: ${operation}`);
}

async function captureScreenshot(serial: string) {
  const { adb: adbPath } = await sdk();
  const { stdout } = await runToolRaw(adbPath, ["-s", serial, "exec-out", "screencap", "-p"], {
    timeoutMs: 30_000,
  });
  const buffer = Buffer.from(stdout);
  const artifact = await writeArtifact(serial, buffer, "png", "image/png", "screenshot");
  return Object.freeze({
    operationId: operationId("screenshot"),
    operation: "device.capture.screenshot",
    status: "succeeded" as const,
    completedAt: new Date().toISOString(),
    output: Object.freeze({ artifact }),
  });
}

async function readLogs(serial: string, input: JsonRecord = {}) {
  const seconds = requireInt((input?.seconds as number | undefined) ?? 5, "seconds");
  const limit = requireInt((input?.limit as number | undefined) ?? 500, "limit");
  await adbShell(serial, "logcat -c").catch(() => {});
  await sleep(Math.min(seconds, 3) * 1000);
  const { stdout } = await adbOnDevice(serial, ["logcat", "-d", "-t", String(limit)]);
  return Object.freeze({
    operationId: operationId("logs"),
    operation: "device.logs.read",
    status: "succeeded" as const,
    output: Object.freeze({ lines: stdout.split("\n").filter(Boolean).slice(-limit) }),
  });
}

async function runNativeTest(serial: string, input: JsonRecord = {}) {
  const rawSelector = input?.selector as string | undefined;
  if (!rawSelector)
    throw new TypeError(
      "run_native_test requires a selector like com.example.TestClass#testMethod.",
    );
  const selector = requireTestSelector(rawSelector);

  const component = requirePackageName(
    await resolveInstrumentation(serial, input, selector),
    "runner",
  );
  const instrumentArgs = ["shell", "am", "instrument", "-w", "-r"];
  if (selector.includes("#") || selector.includes(".")) {
    instrumentArgs.push("-e", "class", selector);
  }
  instrumentArgs.push(component);

  const { stdout, stderr } = await adbOnDevice(serial, instrumentArgs, {
    timeoutMs: (input?.timeoutMs as number | undefined) ?? 600_000,
  }).catch((error: Error) => {
    const failed = cliError("device.test.failed", `instrumentation failed: ${error.message}`);
    throw failed;
  });
  const output = `${stdout}\n${stderr}`;
  const outcome = classifyInstrumentationOutcome(output);

  return Object.freeze({
    operationId: operationId("native-test"),
    operation: "device.test.run",
    status: "succeeded" as const,
    output: Object.freeze({
      outcome,
      selector,
      component,
      tail: output.split("\n").filter(Boolean).slice(-40),
    }),
  });
}

async function resolveInstrumentation(
  serial: string,
  input: JsonRecord,
  selector: string,
): Promise<string> {
  if (typeof input?.runner === "string" && input.runner.includes("/")) return input.runner;
  if (typeof input?.testPackage === "string") {
    const runner = await findRunnerForPackage(serial, input.testPackage);
    return `${input.testPackage}/${runner ?? "androidx.test.runner.AndroidJUnitRunner"}`;
  }
  // Derive the app package from the selector's class prefix, then look for a
  // matching `<pkg>.test` instrumentation on the device.
  const className = selector.split("#")[0];
  const instrumentations = await listInstrumentations(serial);
  const match = instrumentations.find(
    (entry) =>
      className.startsWith(entry.targetPackage) ||
      className.startsWith(entry.package.replace(/\.test$/, "")),
  );
  if (match) return `${match.package}/${match.runner}`;
  if (instrumentations.length === 1)
    return `${instrumentations[0].package}/${instrumentations[0].runner}`;
  throw cliError(
    "device.test.runner-unresolved",
    `Could not resolve an instrumentation runner for ${className}. Install the androidTest APK or pass --runner <pkg>/<runner>. Found: ${instrumentations.map((i) => i.package).join(", ") || "none"}.`,
  );
}

async function listInstrumentations(serial: string): Promise<InstrumentationInfo[]> {
  const { stdout } = await adbShell(serial, "pm list instrumentation");
  const entries: InstrumentationInfo[] = [];
  const pattern = /instrumentation:([^\s]+)\/([^\s]+)\s+\(target=([^)]+)\)/g;
  let match: RegExpExecArray | null;
  while ((match = pattern.exec(stdout)) !== null) {
    entries.push(Object.freeze({ package: match[1], runner: match[2], targetPackage: match[3] }));
  }
  return entries;
}

async function findRunnerForPackage(
  serial: string,
  testPackage: string,
): Promise<string | undefined> {
  const instrumentations = await listInstrumentations(serial);
  return instrumentations.find((entry) => entry.package === testPackage)?.runner;
}

async function manageApp(serial: string, action: string, input: JsonRecord = {}) {
  const rawBundleId = input?.bundleId as string | undefined;
  const bundleId =
    rawBundleId === undefined ? undefined : requirePackageName(rawBundleId, "bundle_id");
  switch (action) {
    case "list": {
      const { stdout } = await adbShell(serial, "pm list packages");
      const packages = stdout
        .split("\n")
        .map((line) => line.replace("package:", "").trim())
        .filter(Boolean);
      return Object.freeze({
        operationId: operationId("app-list"),
        operation: "device.app.list",
        status: "succeeded" as const,
        output: Object.freeze({ packages }),
      });
    }
    case "install": {
      if (!input?.path) throw new TypeError("manage_app install requires a path.");
      await adbOnDevice(serial, ["install", "-r", input.path as string], { timeoutMs: 300_000 });
      return Object.freeze({
        operationId: operationId("app-install"),
        operation: "device.app.install",
        status: "succeeded" as const,
        output: Object.freeze({ installed: true, path: input.path }),
      });
    }
    case "launch": {
      if (!bundleId) throw new TypeError("manage_app launch requires bundle_id.");
      await adbShell(serial, `monkey -p ${bundleId} -c android.intent.category.LAUNCHER 1`).catch(
        async () => {
          await adbShell(serial, `am start -n ${bundleId}/.MainActivity`);
        },
      );
      return Object.freeze({
        operationId: operationId("app-launch"),
        operation: "device.app.launch",
        status: "succeeded" as const,
        output: Object.freeze({ launched: true, bundleId }),
      });
    }
    case "terminate": {
      if (!bundleId) throw new TypeError("manage_app terminate requires bundle_id.");
      await adbShell(serial, `am force-stop ${bundleId}`);
      return Object.freeze({
        operationId: operationId("app-terminate"),
        operation: "device.app.terminate",
        status: "succeeded" as const,
        output: Object.freeze({ terminated: true, bundleId }),
      });
    }
    case "uninstall": {
      if (!bundleId) throw new TypeError("manage_app uninstall requires bundle_id.");
      if (input?.confirm !== true)
        throw new TypeError("manage_app uninstall requires confirm=true.");
      await adbOnDevice(serial, ["uninstall", bundleId], { timeoutMs: 120_000 });
      return Object.freeze({
        operationId: operationId("app-uninstall"),
        operation: "device.app.uninstall",
        status: "succeeded" as const,
        output: Object.freeze({ uninstalled: true, bundleId }),
      });
    }
    default:
      throw new TypeError(`Unsupported manage_app action: ${action}`);
  }
}

function recordingStatePath(serial: string): string {
  return path.join(
    defaultArtifactDirectory(),
    serial.replace(/[^\w.-]/g, "_"),
    "active-recording.json",
  );
}

async function saveRecordingState(serial: string, state: RecordingState): Promise<void> {
  const filePath = recordingStatePath(serial);
  await mkdir(path.dirname(filePath), { recursive: true });
  await writeFile(filePath, JSON.stringify(state));
}

async function loadRecordingState(serial: string): Promise<RecordingState | undefined> {
  try {
    const raw = await readFile(recordingStatePath(serial), "utf8");
    const parsed = JSON.parse(raw) as RecordingState;
    if (typeof parsed?.remote === "string") return parsed;
  } catch {}
  return undefined;
}

async function clearRecordingState(serial: string): Promise<void> {
  await unlink(recordingStatePath(serial)).catch(() => {});
}

async function recordScreen(serial: string, action: string) {
  if (action === "start") {
    const existing = await loadRecordingState(serial);
    if (existing) {
      throw cliError(
        "device.recording.active",
        "A recording is already active for this device. Stop it before starting another.",
      );
    }
    const remote = `/sdcard/mobile-use-recording-${Date.now()}.mp4`;
    const { adb: adbPath } = await sdk();
    const { pid } = await runToolBackgroundPid(
      adbPath,
      ["-s", serial, "shell", `nohup screenrecord ${remote} >/dev/null 2>&1 & echo $!`],
      { timeoutMs: 15_000 },
    );
    const startedAt = new Date().toISOString();
    await saveRecordingState(serial, { remote, pid, startedAt });
    await sleep(500);
    return Object.freeze({
      operationId: operationId("record-start"),
      operation: "device.recording.start",
      status: "succeeded" as const,
      output: Object.freeze({ active: true, startedAt }),
    });
  }
  if (action === "status") {
    const record = await loadRecordingState(serial);
    return Object.freeze({
      operationId: operationId("record-status"),
      operation: "device.recording.status",
      status: "succeeded" as const,
      output: Object.freeze({
        active: Boolean(record),
        ...(record ? { startedAt: record.startedAt } : {}),
      }),
    });
  }
  if (action === "stop") {
    const record = await loadRecordingState(serial);
    if (!record) {
      throw cliError("device.recording.inactive", "No active recording for this device.");
    }
    if (Number.isInteger(record.pid)) {
      await adbShell(serial, `kill -INT ${record.pid}`)
        .catch(() => adbShell(serial, `kill ${record.pid}`))
        .catch(() => {});
    } else {
      await adbShell(serial, "pkill -INT screenrecord")
        .catch(() => adbShell(serial, "killall -INT screenrecord"))
        .catch(() => {});
    }
    await sleep(1500);
    const { adb: adbPath } = await sdk();
    const { stdout } = await runToolRaw(adbPath, ["-s", serial, "exec-out", "cat", record.remote], {
      timeoutMs: 60_000,
    });
    const buffer = Buffer.from(stdout);
    if (buffer.length === 0) {
      // Keep the state file so the user can retry stop; the recording may still
      // be recoverable once the device finishes flushing.
      throw cliError(
        "device.recording.empty",
        "Recording file was empty after stop. screenrecord may not have started.",
      );
    }
    const artifact = await writeArtifact(serial, buffer, "mp4", "video/mp4", "recording");
    // Only after a successful pull: clear local state and remove the on-device
    // file so repeated recordings do not accumulate on /sdcard.
    await clearRecordingState(serial);
    await adbShell(serial, `rm -f ${record.remote}`).catch(() => {});
    return Object.freeze({
      operationId: operationId("record-stop"),
      operation: "device.recording.stop",
      status: "succeeded" as const,
      completedAt: new Date().toISOString(),
      output: Object.freeze({ active: false, startedAt: record.startedAt, artifact }),
    });
  }
  throw new TypeError(`Unsupported record_screen action: ${action}`);
}

async function writeArtifact(
  serial: string,
  buffer: Buffer,
  extension: string,
  mediaType: string,
  kind: string,
): Promise<Artifact> {
  const directory = path.join(defaultArtifactDirectory(), serial.replace(/[^\w.-]/g, "_"));
  await mkdir(directory, { recursive: true });
  const digest = createHash("sha256").update(buffer).digest("hex");
  const fileName = `${kind}-${Date.now()}.${extension}`;
  const filePath = path.join(directory, fileName);
  await writeFile(filePath, buffer);
  return Object.freeze({
    artifactId: digest.slice(0, 16),
    createdAt: new Date().toISOString(),
    mediaType,
    size: buffer.length,
    algorithm: "sha256",
    digest,
    uri: pathToFileURL(filePath).href,
    source: kind,
    platform: "android",
    targetId: serial,
  });
}

function operationId(prefix: string): string {
  return `${prefix}-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

function sleep(ms: number): Promise<void> {
  return new Promise((resolvePromise) => setTimeout(resolvePromise, ms));
}

// Re-export for modules that build on the android backend contract.
export { isRecord };
