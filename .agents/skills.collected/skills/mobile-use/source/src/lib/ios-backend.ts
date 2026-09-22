import { mkdir } from "node:fs/promises";
import path from "node:path";
import { pathToFileURL } from "node:url";
import { createHash } from "node:crypto";
import { defaultArtifactDirectory, findXcrun, hostPlatform, runTool } from "./exec.ts";
import type { ToolOptions } from "./exec.ts";
import { cliError } from "./types.ts";
import type { DeviceSession, DeviceTarget, JsonRecord, Observation, UiElement } from "./types.ts";

const SURFACE_ID = "simctl-ios";

async function requireDarwin(): Promise<string> {
  if (hostPlatform() !== "darwin") {
    throw cliError(
      "device.platform.unsupported",
      "iOS Simulator control requires macOS with xcrun. This host is not supported.",
    );
  }
  const xcrun = await findXcrun();
  if (!xcrun) {
    throw cliError(
      "device.toolchain.missing",
      "xcrun not found. Install Xcode and its command-line tools.",
    );
  }
  return xcrun;
}

async function simctl(args: string[], options: ToolOptions = {}) {
  const xcrun = await requireDarwin();
  return runTool(xcrun, ["simctl", ...args], { errorCode: "device.simctl.failed", ...options });
}

interface SimctlDevice {
  udid: string;
  name: string;
  state: string;
}

export async function listLiveTargets(): Promise<DeviceTarget[]> {
  const { stdout } = await simctl(["list", "devices", "-j", "available"]);
  const parsed = JSON.parse(stdout) as { devices?: Record<string, SimctlDevice[]> };
  const targets: DeviceTarget[] = [];
  for (const [runtime, devices] of Object.entries(parsed.devices ?? {})) {
    for (const device of devices) {
      targets.push(
        Object.freeze({
          surfaceId: SURFACE_ID,
          adapterId: "ios-simctl",
          targetId: device.udid,
          platform: "ios" as const,
          targetName: device.name,
          runtimeKind: "simulator" as const,
          state: device.state === "Booted" ? "online" : "shutdown",
          targetCapabilities: Object.freeze([
            "device.frame.screenshot",
            "device.app.launch",
            "device.app.terminate",
            "device.app.uninstall",
          ]) as string[],
          runtime,
        }),
      );
    }
  }
  return targets;
}

export async function listLiveSessions(): Promise<DeviceSession[]> {
  const targets = await listLiveTargets();
  return targets
    .filter((target) => target.state === "online")
    .map((target) =>
      Object.freeze({
        surfaceId: SURFACE_ID,
        sessionId: target.targetId,
        targetId: target.targetId,
        platform: "ios" as const,
        targetName: target.targetName,
        runtimeKind: "simulator" as const,
        state: "attached",
        capabilities: Object.freeze([
          { id: "device.frame.screenshot" },
          { id: "device.app.launch" },
          { id: "device.app.terminate" },
          { id: "device.app.uninstall" },
        ]) as Array<{ id: string }>,
      }),
    );
}

export async function startPhoneUseSession(
  surfaceId: string,
  targetId: string,
): Promise<DeviceSession> {
  await simctl(["boot", targetId]).catch(() => {});
  const sessions = await listLiveSessions();
  const session = sessions.find((candidate) => candidate.sessionId === targetId);
  if (!session) {
    throw cliError("device.target.not-found", `iOS Simulator ${targetId} did not boot.`);
  }
  return session;
}

export async function stopPhoneUseSession(surfaceId: string, sessionId: string) {
  await simctl(["shutdown", sessionId]).catch(() => {});
  return Object.freeze({ stopped: true });
}

export async function invokePhoneUse(
  surfaceId: string,
  sessionId: string,
  method: string,
  input?: JsonRecord,
): Promise<unknown> {
  if (method === "observe") return wdaObserve(sessionId);
  if (method === "perform") return wdaPerform(sessionId, input);
  if (method === "act") return wdaAct(sessionId, input);
  if (method === "wait") return wdaWait(sessionId, input);
  if (method === "assert") return wdaAssert(sessionId, input);
  throw cliError("device.capability.unsupported", `iOS does not support method: ${method}.`);
}

// ── WebDriverAgent 语义层（W3C WebDriver 协议，默认 localhost:8100）──────────

function wdaBaseUrl(): string {
  return (process.env.MOBILE_USE_WDA_URL?.trim() || "http://localhost:8100").replace(/\/$/, "");
}

async function wdaRequest(
  sessionId: string,
  method: "GET" | "POST" | "DELETE",
  pathSuffix: string,
  body?: unknown,
): Promise<JsonRecord> {
  const url = `${wdaBaseUrl()}${pathSuffix}`;
  let response: Response;
  try {
    response = await fetch(url, {
      method,
      headers: body === undefined ? {} : { "content-type": "application/json" },
      ...(body === undefined ? {} : { body: JSON.stringify(body) }),
      signal: AbortSignal.timeout(15_000),
    });
  } catch (error) {
    throw cliError(
      "device.driver.unavailable",
      `WebDriverAgent is not reachable at ${wdaBaseUrl()}. Start WebDriverAgent on the Simulator (or set MOBILE_USE_WDA_URL), then retry. (${error instanceof Error ? error.message : String(error)})`,
    );
  }
  const payload = (await response.json().catch(() => ({}))) as JsonRecord & { value?: unknown };
  if (!response.ok) {
    const message =
      typeof payload?.value === "object" && payload.value !== null && "message" in payload.value
        ? String((payload.value as { message?: unknown }).message)
        : `HTTP ${response.status}`;
    throw cliError(
      "device.driver.failed",
      `WebDriverAgent ${method} ${pathSuffix} failed: ${message}`,
    );
  }
  return payload;
}

let wdaSessionId: string | undefined;

async function wdaSession(): Promise<string> {
  if (wdaSessionId) return wdaSessionId;
  const result = await wdaRequest("", "POST", "/session", {
    capabilities: { alwaysMatch: { platformName: "iOS" } },
  });
  const value = result.value as { sessionId?: string } | undefined;
  if (!value?.sessionId) {
    throw cliError("device.driver.failed", "WebDriverAgent did not return a sessionId.");
  }
  wdaSessionId = value.sessionId;
  return wdaSessionId;
}

interface WdaSourceNode {
  type?: string;
  name?: string;
  label?: string;
  value?: string;
  rect?: { x?: number; y?: number; width?: number; height?: number };
  children?: WdaSourceNode[];
}

function flattenWdaSource(node: WdaSourceNode, ordinal: { value: number }): UiElement[] {
  const elements: UiElement[] = [];
  if (!node || typeof node !== "object") return elements;
  const ref = `e${ordinal.value}`;
  ordinal.value += 1;
  const rect = node.rect ?? {};
  const hasRect = Number.isFinite(rect.x) && Number.isFinite(rect.width);
  const center = hasRect
    ? {
        x: Math.round((rect.x as number) + ((rect.width as number) || 0) / 2),
        y: Math.round((rect.y as number) + ((rect.height as number) || 0) / 2),
      }
    : undefined;
  const label = node.label ?? node.value ?? node.name;
  const identifier = node.name !== label ? node.name : undefined;
  elements.push(
    Object.freeze({
      ref,
      identifier,
      label,
      role: node.type,
      type: node.type,
      center,
    }),
  );
  for (const child of node.children ?? []) {
    elements.push(...flattenWdaSource(child, ordinal));
  }
  return elements;
}

async function wdaObserve(sessionId: string): Promise<Observation> {
  const sid = await wdaSession();
  const result = await wdaRequest(sessionId, "GET", `/session/${sid}/source`);
  const value = result.value as WdaSourceNode | undefined;
  const elements = value ? flattenWdaSource(value, { value: 0 }) : [];
  return Object.freeze({
    uiRevision: Date.now(),
    snapshotId: `snap-${Date.now()}`,
    platform: "ios",
    source: "webdriveragent",
    elementCount: elements.length,
    truncated: false,
    elements: Object.freeze(elements) as UiElement[],
  });
}

function matchesWdaSelector(element: UiElement, selector: JsonRecord): boolean {
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

async function wdaFindElement(sessionId: string, selector: JsonRecord): Promise<UiElement> {
  const observation = await wdaObserve(sessionId);
  const matches = observation.elements.filter(
    (el) => matchesWdaSelector(el, selector) && el.center,
  );
  if (matches.length === 0) {
    throw cliError("phone.selector.not-found", "No iOS element matched the selector.");
  }
  if (matches.length > 1) {
    throw cliError("phone.selector.ambiguous", `Selector matched ${matches.length} elements.`);
  }
  return matches[0];
}

async function wdaTap(sessionId: string, point: { x: number; y: number }): Promise<void> {
  const sid = await wdaSession();
  await wdaRequest(sessionId, "POST", `/session/${sid}/actions`, {
    actions: [
      {
        type: "pointer",
        id: "finger1",
        parameters: { pointerType: "touch" },
        actions: [
          { type: "pointerMove", duration: 0, x: point.x, y: point.y },
          { type: "pointerDown", button: 0 },
          { type: "pause", duration: 50 },
          { type: "pointerUp", button: 0 },
        ],
      },
    ],
  });
}

async function wdaPerform(sessionId: string, input: JsonRecord = {}) {
  const action = (input?.action ?? {}) as {
    kind?: string;
    selector?: JsonRecord;
    durationMs?: number;
  };
  const element = await wdaFindElement(sessionId, action.selector ?? {});
  if (action.kind === "long-press") {
    const sid = await wdaSession();
    await wdaRequest(sessionId, "POST", `/session/${sid}/actions`, {
      actions: [
        {
          type: "pointer",
          id: "finger1",
          parameters: { pointerType: "touch" },
          actions: [
            {
              type: "pointerMove",
              duration: 0,
              x: element.center?.x ?? 0,
              y: element.center?.y ?? 0,
            },
            { type: "pointerDown", button: 0 },
            { type: "pause", duration: action.durationMs ?? 1_000 },
            { type: "pointerUp", button: 0 },
          ],
        },
      ],
    });
  } else {
    await wdaTap(sessionId, element.center as { x: number; y: number });
  }
  const observation = await wdaObserve(sessionId);
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
      operation: "wda.actions.tap",
      status: "succeeded" as const,
    }),
  });
}

async function wdaAct(sessionId: string, input: JsonRecord = {}) {
  const action = (input?.action ?? {}) as {
    kind?: string;
    selector?: JsonRecord;
    from?: { x: number; y: number };
    to?: { x: number; y: number };
    durationMs?: number;
    text?: string;
  };
  const kind = action.kind;
  if (kind === "tap" || kind === "long-press") return wdaPerform(sessionId, input);
  if (kind === "swipe") {
    const sid = await wdaSession();
    const from = action.from ?? { x: 0, y: 0 };
    const to = action.to ?? { x: 0, y: 0 };
    const durationMs = Number.isInteger(action.durationMs) ? (action.durationMs as number) : 300;
    await wdaRequest(sessionId, "POST", `/session/${sid}/actions`, {
      actions: [
        {
          type: "pointer",
          id: "finger1",
          parameters: { pointerType: "touch" },
          actions: [
            { type: "pointerMove", duration: 0, x: from.x, y: from.y },
            { type: "pointerDown", button: 0 },
            { type: "pointerMove", duration: durationMs, x: to.x, y: to.y },
            { type: "pointerUp", button: 0 },
          ],
        },
      ],
    });
    return Object.freeze({ uiChanged: true, observation: await wdaObserve(sessionId) });
  }
  if (kind === "text") {
    const element = await wdaFindElement(sessionId, action.selector ?? {});
    const text = String(action.text ?? "");
    if (!text) throw cliError("phone.cli.argument", "text must be non-empty.");
    const sid = await wdaSession();
    await wdaRequest(sessionId, "POST", `/session/${sid}/actions`, {
      actions: [
        {
          type: "key",
          id: "keyboard",
          actions: [
            { type: "keyDown", value: text },
            { type: "keyUp", value: text },
          ],
        },
      ],
    }).catch(async () => {
      await wdaTap(sessionId, element.center as { x: number; y: number });
    });
    return Object.freeze({ uiChanged: true, observation: await wdaObserve(sessionId) });
  }
  throw cliError("device.capability.unsupported", `iOS does not support act kind: ${kind}.`);
}

async function wdaWait(sessionId: string, input: JsonRecord = {}): Promise<Observation> {
  const condition = (input?.condition ?? {}) as { kind?: string; selector?: JsonRecord };
  const timeoutMs = (input?.timeoutMs as number | undefined) ?? 10_000;
  const pollIntervalMs = (input?.pollIntervalMs as number | undefined) ?? 500;
  const deadline = Date.now() + timeoutMs;
  let lastObservation: Observation | undefined;
  while (Date.now() < deadline) {
    lastObservation = await wdaObserve(sessionId);
    if (condition.kind === "stable") return lastObservation;
    const found = lastObservation.elements.some((el) =>
      matchesWdaSelector(el, condition.selector ?? {}),
    );
    if (condition.kind === "present" && found) return lastObservation;
    if (condition.kind === "absent" && !found) return lastObservation;
    await iosSleep(pollIntervalMs);
  }
  throw cliError(
    "phone.wait.timeout",
    `wait condition ${condition.kind} timed out after ${timeoutMs} ms.`,
  );
}

async function wdaAssert(sessionId: string, input: JsonRecord = {}) {
  const observation = await wdaObserve(sessionId);
  const selector = (input?.selector as JsonRecord | undefined) ?? {};
  const matches = observation.elements.filter((el) => matchesWdaSelector(el, selector));
  const element = matches[0];
  if (matches.length === 0) {
    if (input?.state === "absent") return Object.freeze({ passed: true, observation });
    return Object.freeze({ passed: false, observation, reason: "phone.selector.not-found" });
  }
  if (matches.length > 1) {
    return Object.freeze({ passed: false, observation, reason: "phone.selector.ambiguous" });
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

function iosSleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
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
    case "device.app.launch":
      await simctl(["launch", sessionId, (input?.bundleId as string | undefined) ?? ""]);
      return Object.freeze({
        operationId: operationId("launch"),
        operation,
        status: "succeeded" as const,
        output: Object.freeze({ launched: true }),
      });
    case "device.app.terminate":
      await simctl(["terminate", sessionId, (input?.bundleId as string | undefined) ?? ""]);
      return Object.freeze({
        operationId: operationId("terminate"),
        operation,
        status: "succeeded" as const,
        output: Object.freeze({ terminated: true }),
      });
    case "device.app.uninstall":
      if (input?.confirm !== true)
        throw new TypeError("manage_app uninstall requires confirm=true.");
      await simctl(["uninstall", sessionId, (input?.bundleId as string | undefined) ?? ""]);
      return Object.freeze({
        operationId: operationId("uninstall"),
        operation,
        status: "succeeded" as const,
        output: Object.freeze({ uninstalled: true }),
      });
    default:
      throw cliError(
        "device.capability.unsupported",
        `iOS operation not supported by this backend: ${operation}`,
      );
  }
}

export async function invokeTargetOperation(): Promise<never> {
  throw cliError(
    "device.capability.unsupported",
    "iOS target operations are not supported by this backend.",
  );
}

async function captureScreenshot(udid: string) {
  const directory = path.join(defaultArtifactDirectory(), udid.replace(/[^\w.-]/g, "_"));
  await mkdir(directory, { recursive: true });
  const filePath = path.join(directory, `screenshot-${Date.now()}.png`);
  await simctl(["io", udid, "screenshot", filePath], { timeoutMs: 30_000 });
  const buffer = await import("node:fs/promises").then(({ readFile }) => readFile(filePath));
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
        platform: "ios" as const,
        targetId: udid,
      }),
    }),
  });
}

function operationId(prefix: string): string {
  return `${prefix}-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}
