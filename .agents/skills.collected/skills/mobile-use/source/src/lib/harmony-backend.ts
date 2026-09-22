import { mkdir } from "node:fs/promises";
import path from "node:path";
import { pathToFileURL } from "node:url";
import { createHash } from "node:crypto";
import { defaultArtifactDirectory, findHdc, runTool } from "./exec.ts";
import type { ToolOptions } from "./exec.ts";
import { cliError } from "./types.ts";
import type { DeviceSession, DeviceTarget, JsonRecord, Observation, UiElement } from "./types.ts";

const SURFACE_ID = "hdc-harmony";

let hdcPromise: Promise<string | undefined> | undefined;

async function hdc(args: string[], options: ToolOptions = {}) {
  if (!hdcPromise) hdcPromise = findHdc();
  const binary = await hdcPromise;
  if (!binary) {
    throw cliError(
      "device.toolchain.missing",
      "OpenHarmony hdc not found. Set DEVECO_SDK_HOME or install DevEco Studio. Run `doctor` for guidance.",
    );
  }
  return runTool(binary, args, { errorCode: "device.hdc.failed", ...options });
}

async function hdcOnDevice(connectKey: string, args: string[], options: ToolOptions = {}) {
  return hdc(["-t", connectKey, ...args], options);
}

export async function listLiveTargets(): Promise<DeviceTarget[]> {
  const { stdout } = await hdc(["list", "targets"]);
  const targets: DeviceTarget[] = [];
  for (const line of stdout.split("\n")) {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith("[") || trimmed.toLowerCase().includes("empty")) continue;
    targets.push(
      Object.freeze({
        surfaceId: SURFACE_ID,
        adapterId: "harmony-hdc",
        targetId: trimmed,
        platform: "harmony" as const,
        targetName: trimmed,
        runtimeKind: "remote" as const,
        state: "online",
        targetCapabilities: Object.freeze([
          "device.frame.screenshot",
          "device.app.launch",
          "device.app.terminate",
        ]) as string[],
      }),
    );
  }
  return targets;
}

export async function listLiveSessions(): Promise<DeviceSession[]> {
  const targets = await listLiveTargets();
  return targets.map((target) =>
    Object.freeze({
      surfaceId: SURFACE_ID,
      sessionId: target.targetId,
      targetId: target.targetId,
      platform: "harmony" as const,
      targetName: target.targetName,
      runtimeKind: "remote" as const,
      state: "attached",
      capabilities: Object.freeze([
        { id: "device.frame.screenshot" },
        { id: "device.app.launch" },
        { id: "device.app.terminate" },
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
      `HarmonyOS device ${targetId} is not connected. Run list-targets again.`,
    );
  }
  return session;
}

export async function stopPhoneUseSession(): Promise<{ stopped: boolean; note: string }> {
  return Object.freeze({ stopped: false, note: "HDC targets are not stopped by this skill." });
}

export async function invokePhoneUse(
  surfaceId: string,
  sessionId: string,
  method: string,
  input?: JsonRecord,
): Promise<unknown> {
  if (method === "observe") return observe(sessionId);
  if (method === "perform") return perform(sessionId, input);
  if (method === "act") return act(sessionId, input);
  if (method === "wait") return waitFor(sessionId, input);
  if (method === "assert") return assert(sessionId, input);
  throw cliError("device.capability.unsupported", `HarmonyOS does not support method: ${method}.`);
}

async function dumpUiTree(connectKey: string): Promise<UiElement[]> {
  const remote = "/data/local/tmp/uitest-dump.json";
  await hdcOnDevice(connectKey, ["shell", "uitest", "dumpLayout", "-p", remote]).catch(() => {});
  const { stdout } = await hdcOnDevice(connectKey, ["shell", "cat", remote], {
    timeoutMs: 30_000,
  }).catch(() => ({ stdout: "", stderr: "" }));
  try {
    return flattenUitest(JSON.parse(stdout));
  } catch {
    return [];
  }
}

async function observe(connectKey: string): Promise<Observation> {
  const elements = await dumpUiTree(connectKey);
  return Object.freeze({
    uiRevision: Date.now(),
    snapshotId: `snap-${Date.now()}`,
    platform: "harmony",
    source: "uitest",
    elementCount: elements.length,
    truncated: false,
    elements: Object.freeze(elements) as UiElement[],
  });
}

interface HarmonyElement extends UiElement {
  center?: { x: number; y: number };
}

function resolveHarmonyElement(elements: UiElement[], selector: JsonRecord): HarmonyElement {
  const matches = elements.filter((element) => matchesHarmonySelector(element, selector));
  if (matches.length === 0) {
    throw cliError("phone.selector.not-found", "No HarmonyOS element matched the selector.");
  }
  const withCenter = matches.filter((element) => element.center);
  const pool = withCenter.length > 0 ? withCenter : matches;
  if (pool.length > 1) {
    throw cliError("phone.selector.ambiguous", `Selector matched ${pool.length} elements.`);
  }
  const element = pool[0];
  if (!element.center) {
    throw cliError("device.observe.failed", "Matched element has no bounds to tap.");
  }
  return element;
}

function matchesHarmonySelector(element: UiElement, selector: JsonRecord): boolean {
  if (typeof selector.identifier === "string") {
    if (
      !(
        element.identifier === selector.identifier ||
        element.identifier?.endsWith(`/${selector.identifier}`)
      )
    )
      return false;
  }
  if (typeof selector.label === "string") {
    const needle = selector.label.toLowerCase();
    if (!element.label?.toLowerCase().includes(needle)) return false;
  }
  if (typeof selector.role === "string") {
    if (!element.role?.toLowerCase().includes(selector.role.toLowerCase())) return false;
  }
  if (typeof selector.type === "string") {
    if (!element.type?.toLowerCase().includes(selector.type.toLowerCase())) return false;
  }
  return true;
}

async function perform(connectKey: string, input: JsonRecord = {}) {
  const action = (input?.action ?? {}) as {
    kind?: string;
    selector?: JsonRecord;
    durationMs?: number;
  };
  const elements = await dumpUiTree(connectKey);
  const element = resolveHarmonyElement(elements, action.selector ?? {});
  const { x, y } = element.center as { x: number; y: number };
  if (action.kind === "long-press") {
    await hdcOnDevice(connectKey, [
      "shell",
      "uitest",
      "uiInput",
      "longClick",
      String(x),
      String(y),
    ]);
  } else {
    await hdcOnDevice(connectKey, ["shell", "uitest", "uiInput", "click", String(x), String(y)]);
  }
  const observation = await observe(connectKey);
  return Object.freeze({
    uiChanged: true,
    element: Object.freeze({
      ref: element.ref,
      identifier: element.identifier,
      label: element.label,
      role: element.role,
      type: element.type,
    }),
    observation,
    receipt: Object.freeze({
      operationId: operationId("tap"),
      operation: "uitest.uiInput.click",
      status: "succeeded" as const,
    }),
  });
}

async function act(connectKey: string, input: JsonRecord = {}) {
  const action = (input?.action ?? {}) as {
    kind?: string;
    selector?: JsonRecord;
    from?: { x: number; y: number };
    to?: { x: number; y: number };
    durationMs?: number;
    text?: string;
    key?: string;
  };
  const kind = action.kind;
  if (kind === "tap" || kind === "long-press") return perform(connectKey, input);
  if (kind === "swipe") {
    const from = action.from ?? { x: 0, y: 0 };
    const to = action.to ?? { x: 0, y: 0 };
    const velocity = Math.max(
      200,
      Math.min(40_000, Math.round(((action.durationMs ?? 300) / 300) * 600)),
    );
    await hdcOnDevice(connectKey, [
      "shell",
      "uitest",
      "uiInput",
      "swipe",
      String(requireHarmonyInt(from.x, "from.x")),
      String(requireHarmonyInt(from.y, "from.y")),
      String(requireHarmonyInt(to.x, "to.x")),
      String(requireHarmonyInt(to.y, "to.y")),
      String(velocity),
    ]);
    return Object.freeze({ uiChanged: true, observation: await observe(connectKey) });
  }
  if (kind === "text") {
    const elements = await dumpUiTree(connectKey);
    const element = resolveHarmonyElement(elements, action.selector ?? {});
    const { x, y } = element.center as { x: number; y: number };
    const text = String(action.text ?? "");
    if (!text) throw cliError("phone.cli.argument", "text must be non-empty.");
    await hdcOnDevice(connectKey, [
      "shell",
      "uitest",
      "uiInput",
      "inputText",
      String(x),
      String(y),
      text,
    ]);
    return Object.freeze({ uiChanged: true, observation: await observe(connectKey) });
  }
  if (kind === "key") {
    const key = String(action.key ?? "");
    if (!/^[A-Za-z0-9_]+$/.test(key)) {
      throw cliError(
        "phone.cli.argument",
        `key must be a key name (e.g. Home, Back), got ${JSON.stringify(action.key)}.`,
      );
    }
    await hdcOnDevice(connectKey, ["shell", "uitest", "uiInput", "keyEvent", key]);
    return Object.freeze({ uiChanged: true, observation: await observe(connectKey) });
  }
  throw cliError("device.capability.unsupported", `HarmonyOS does not support act kind: ${kind}.`);
}

function requireHarmonyInt(value: unknown, name: string): number {
  if (!Number.isInteger(value)) {
    throw cliError(
      "phone.cli.argument",
      `${name} must be an integer, got ${JSON.stringify(value)}.`,
    );
  }
  return value as number;
}

async function waitFor(connectKey: string, input: JsonRecord = {}): Promise<Observation> {
  const condition = (input?.condition ?? {}) as { kind?: string; selector?: JsonRecord };
  const timeoutMs = (input?.timeoutMs as number | undefined) ?? 10_000;
  const pollIntervalMs = (input?.pollIntervalMs as number | undefined) ?? 500;
  const deadline = Date.now() + timeoutMs;
  let lastObservation: Observation | undefined;
  while (Date.now() < deadline) {
    lastObservation = await observe(connectKey);
    if (condition.kind === "stable") return lastObservation;
    const found = lastObservation.elements.some((el) =>
      matchesHarmonySelector(el, condition.selector ?? {}),
    );
    if (condition.kind === "present" && found) return lastObservation;
    if (condition.kind === "absent" && !found) return lastObservation;
    await harmonySleep(pollIntervalMs);
  }
  throw cliError(
    "phone.wait.timeout",
    `wait condition ${condition.kind} timed out after ${timeoutMs} ms.`,
  );
}

async function assert(connectKey: string, input: JsonRecord = {}) {
  const observation = await observe(connectKey);
  const elements = observation.elements;
  const selector = (input?.selector as JsonRecord | undefined) ?? {};
  let element: UiElement | undefined;
  try {
    element = resolveHarmonyElement(elements, selector);
  } catch (error) {
    const code = (error as { code?: string }).code;
    if (input?.state === "absent" && code === "phone.selector.not-found") {
      return Object.freeze({ passed: true, observation });
    }
    if (code === "device.observe.failed") {
      return Object.freeze({ passed: false, observation, reason: "phone.selector.not-found" });
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

function harmonySleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

interface UitestNode {
  attributes?: { id?: string; text?: string; type?: string; bounds?: string };
  id?: string;
  text?: string;
  type?: string;
  bounds?: string;
  children?: unknown;
  child?: unknown;
}

function parseHarmonyBounds(bounds: string | undefined): { x: number; y: number } | undefined {
  if (!bounds) return undefined;
  const found = /\[(\d+),(\d+)\]\[(\d+),(\d+)\]/.exec(bounds);
  if (!found) return undefined;
  const [, left, top, right, bottom] = found.map(Number);
  return { x: Math.round((left + right) / 2), y: Math.round((top + bottom) / 2) };
}

function flattenUitest(node: unknown, ordinal: { value: number } = { value: 0 }): UiElement[] {
  const elements: UiElement[] = [];
  if (node && typeof node === "object") {
    const candidate = node as UitestNode;
    const ref = `e${ordinal.value}`;
    ordinal.value += 1;
    const bounds = candidate.attributes?.bounds ?? candidate.bounds;
    elements.push(
      Object.freeze({
        ref,
        identifier: candidate.attributes?.id ?? candidate.id,
        label: candidate.attributes?.text ?? candidate.text,
        role: candidate.attributes?.type ?? candidate.type,
        type: candidate.attributes?.type ?? candidate.type,
        center: parseHarmonyBounds(bounds),
      }),
    );
    const children = candidate.children ?? candidate.child ?? [];
    for (const child of Array.isArray(children) ? children : []) {
      elements.push(...flattenUitest(child, ordinal));
    }
  }
  return elements;
}

export async function invokeSessionOperation(
  surfaceId: string,
  sessionId: string,
  operation: string,
  _capability: string,
  input: JsonRecord = {},
): Promise<unknown> {
  if (operation === "device.capture.screenshot") return captureScreenshot(sessionId);
  if (operation === "device.app.launch") {
    const bundleId = requireHarmonyPackage(input?.bundleId, "bundle_id");
    await hdcOnDevice(sessionId, ["shell", "aa", "start", "-b", bundleId, "-a", "EntryAbility"]);
    return Object.freeze({
      operationId: operationId("app-launch"),
      operation: "device.app.launch",
      status: "succeeded" as const,
      output: Object.freeze({ launched: true, bundleId }),
    });
  }
  if (operation === "device.app.terminate") {
    const bundleId = requireHarmonyPackage(input?.bundleId, "bundle_id");
    await hdcOnDevice(sessionId, ["shell", "aa", "force-stop", bundleId]);
    return Object.freeze({
      operationId: operationId("app-terminate"),
      operation: "device.app.terminate",
      status: "succeeded" as const,
      output: Object.freeze({ terminated: true, bundleId }),
    });
  }
  throw cliError(
    "device.capability.unsupported",
    `HarmonyOS operation not supported by this backend: ${operation}`,
  );
}

function requireHarmonyPackage(value: unknown, name: string): string {
  if (typeof value !== "string" || !/^[A-Za-z0-9._]+$/.test(value)) {
    throw cliError(
      "phone.cli.argument",
      `${name} contains unsafe characters: ${JSON.stringify(value)}.`,
    );
  }
  return value;
}

export async function invokeTargetOperation(): Promise<never> {
  throw cliError(
    "device.capability.unsupported",
    "HarmonyOS target operations are not supported by this backend.",
  );
}

async function captureScreenshot(connectKey: string) {
  const remote = `/data/local/tmp/mobile-use-shot-${Date.now()}.png`;
  await hdcOnDevice(connectKey, ["shell", "snapshot_display", "-f", remote], { timeoutMs: 30_000 });
  const directory = path.join(defaultArtifactDirectory(), connectKey.replace(/[^\w.-]/g, "_"));
  await mkdir(directory, { recursive: true });
  const filePath = path.join(directory, `screenshot-${Date.now()}.png`);
  await hdc(["file", "recv", remote, filePath], { timeoutMs: 60_000 });
  const { readFile } = await import("node:fs/promises");
  const buffer = await readFile(filePath);
  const digest = createHash("sha256").update(buffer).digest("hex");
  return Object.freeze({
    operationId: operationId("screenshot"),
    operation: "device.capture.screenshot",
    status: "succeeded" as const,
    completedAt: new Date().toISOString(),
    output: Object.freeze({
      artifact: Object.freeze({
        artifactId: digest.slice(0, 16),
        createdAt: new Date().toISOString(),
        mediaType: "image/png",
        size: buffer.length,
        algorithm: "sha256",
        digest,
        uri: pathToFileURL(filePath).href,
        source: "screenshot",
        platform: "harmony" as const,
        targetId: connectKey,
      }),
    }),
  });
}

function operationId(prefix: string): string {
  return `${prefix}-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}
