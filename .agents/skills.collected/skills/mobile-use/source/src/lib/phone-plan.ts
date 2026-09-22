import { cliError, isRecord } from "./types.ts";
import type {
  CliError,
  DeviceSession,
  DeviceTarget,
  JsonRecord,
  Observation,
  Selector,
  UiElement,
} from "./types.ts";

const PLATFORMS = new Set(["android", "harmony", "ios"]);
const SESSION_POLICIES = new Set(["existing", "reuse-or-start"]);
const SCREENSHOT_POLICIES = new Set(["off", "on-failure"]);
const RECORDING_POLICIES = new Set(["off", "native"]);
const MAX_PLAN_STEPS = 64;

type InvokeFn = (command: string, args?: JsonRecord) => Promise<unknown>;

export async function executePhoneInventory(invoke: InvokeFn) {
  const [targetsEnvelope, sessionsEnvelope] = await Promise.all([
    invoke("list_targets", {}),
    invoke("list_sessions", {}),
  ]);
  const targets = arrayValue(targetsEnvelope, "list_targets") as DeviceTarget[];
  const sessions = arrayValue(sessionsEnvelope, "list_sessions") as DeviceSession[];
  const surfaceMap = new Map<
    string,
    {
      surfaceId: string;
      platforms: Set<string>;
      runtimeKinds: Set<string>;
      targetCount: number;
      sessionCount: number;
    }
  >();
  for (const item of [...targets, ...sessions]) {
    if (!item?.surfaceId) continue;
    const surface = surfaceMap.get(item.surfaceId) ?? {
      surfaceId: item.surfaceId,
      platforms: new Set<string>(),
      runtimeKinds: new Set<string>(),
      targetCount: 0,
      sessionCount: 0,
    };
    if (typeof item.platform === "string") surface.platforms.add(item.platform);
    if (typeof item.runtimeKind === "string") surface.runtimeKinds.add(item.runtimeKind);
    if ("sessionId" in item) surface.sessionCount += 1;
    else surface.targetCount += 1;
    surfaceMap.set(item.surfaceId, surface);
  }
  const surfaces = [...surfaceMap.values()]
    .map((surface) =>
      Object.freeze({
        surfaceId: surface.surfaceId,
        platforms: Object.freeze([...surface.platforms].sort()),
        runtimeKinds: Object.freeze([...surface.runtimeKinds].sort()),
        targetCount: surface.targetCount,
        sessionCount: surface.sessionCount,
      }),
    )
    .sort((left, right) => left.surfaceId.localeCompare(right.surfaceId));
  const publishedPlatforms = [
    ...new Set([...targets, ...sessions].map((item) => item?.platform).filter(Boolean)),
  ].sort();
  return Object.freeze({
    schemaVersion: 1 as const,
    scope: "connected_devices",
    summary: Object.freeze({
      surfaceCount: surfaces.length,
      targetCount: targets.length,
      sessionCount: sessions.length,
      publishedPlatforms: Object.freeze(publishedPlatforms),
    }),
    surfaces: Object.freeze(surfaces),
    targets: Object.freeze(targets),
    sessions: Object.freeze(sessions),
    note: "This inventory contains devices reachable through the host toolchain (adb, hdc, simctl). It is not a machine-wide SDK or toolchain scan; run `doctor` for that.",
  });
}

interface PlanStep {
  kind: string;
  mode?: string;
  selector?: Selector | string;
  durationMs?: number;
  condition?: WaitCondition;
  timeoutMs?: number;
  pollIntervalMs?: number;
  state?: "present" | "absent";
  bundleId?: string;
  testTarget?: string;
  testModule?: string;
  testBundleId?: string;
  runner?: string;
}

interface WaitCondition {
  kind: string;
  selector?: Selector;
  durationMs?: number;
}

interface SessionSelection {
  policy: string;
  surfaceId?: string;
  sessionId?: string;
  targetId?: string;
  targetName?: string;
  runtimeKind?: string;
  platform?: string;
}

interface NormalizedPlan {
  session: SessionSelection;
  steps: readonly PlanStep[];
  keepSession: boolean;
  evidence: { screenshots: string; recording: string };
}

export async function executePhonePlan(source: unknown, invoke: InvokeFn) {
  const plan = normalizePlan(source);
  const selection = await selectSession(plan.session, invoke);
  const steps: JsonRecord[] = [];
  const evidenceErrors: JsonRecord[] = [];
  let primaryError: CliError | undefined;
  let failureScreenshot: unknown;
  let recordingStarted = false;
  let recording: unknown;
  let cleanup: unknown;
  try {
    if (plan.evidence.recording === "native") {
      const started = await invoke("record_screen", {
        surface_id: selection.session.surfaceId,
        session_id: selection.session.sessionId,
        action: "start",
      });
      requireSucceededReceipt(started, "record_screen start");
      recordingStarted = true;
    }
    for (let index = 0; index < plan.steps.length; index += 1) {
      const step = plan.steps[index];
      try {
        const data = await executeStep(step, selection.session, invoke);
        steps.push(
          Object.freeze({
            index,
            kind: step.kind,
            status: "succeeded",
            data: summarizeStep(step.kind, data),
          }),
        );
      } catch (error) {
        primaryError = annotateStepError(error, index, step.kind);
        break;
      }
    }
  } catch (error) {
    primaryError = annotateEvidencePhase(error, "recording-start");
  } finally {
    if (primaryError && plan.evidence.screenshots === "on-failure") {
      try {
        const captured = await invoke("capture_screenshot", {
          surface_id: selection.session.surfaceId,
          session_id: selection.session.sessionId,
        });
        requireSucceededReceipt(captured, "capture_screenshot on failure");
        failureScreenshot = summarizeVisualReceipt(captured);
      } catch (error) {
        evidenceErrors.push(summarizeEvidenceError(error, "failure-screenshot"));
      }
    }
    if (recordingStarted) {
      try {
        const stopped = await invoke("record_screen", {
          surface_id: selection.session.surfaceId,
          session_id: selection.session.sessionId,
          action: "stop",
        });
        requireSucceededReceipt(stopped, "record_screen stop");
        recording = summarizeVisualReceipt(stopped);
      } catch (error) {
        if (!primaryError) primaryError = annotateEvidencePhase(error, "recording-stop");
        else evidenceErrors.push(summarizeEvidenceError(error, "recording-stop"));
      }
    }
    if (selection.startedSession && !plan.keepSession) {
      try {
        cleanup = await invoke("stop_session", {
          surface_id: selection.session.surfaceId,
          session_id: selection.session.sessionId,
        });
      } catch (error) {
        if (!primaryError)
          primaryError = annotateStepError(error, plan.steps.length, "stop_session");
      }
    }
  }
  const evidence = summarizePlanEvidence(failureScreenshot, recording, evidenceErrors);
  if (primaryError) {
    if (evidence) attachPlanEvidence(primaryError, evidence);
    throw primaryError;
  }
  return Object.freeze({
    schemaVersion: 1 as const,
    session: selection.session,
    ...(selection.target ? { target: selection.target } : {}),
    startedSession: selection.startedSession,
    keptSession: selection.startedSession ? plan.keepSession : true,
    steps: Object.freeze(steps),
    ...(evidence ? { evidence } : {}),
    ...(cleanup ? { cleanup: summarizeStep("stop_session", cleanup) } : {}),
  });
}

interface SelectedSession {
  session: DeviceSession;
  target?: DeviceTarget;
  startedSession: boolean;
}

async function selectSession(
  criteria: SessionSelection,
  invoke: InvokeFn,
): Promise<SelectedSession> {
  const sessions = arrayValue(
    await invoke("list_sessions", {}),
    "list_sessions",
  ) as DeviceSession[];
  const matchingSessions = sessions.filter((session) => matchesSelection(session, criteria));
  if (matchingSessions.length === 1) {
    return Object.freeze({ session: matchingSessions[0], startedSession: false });
  }
  if (matchingSessions.length > 1) {
    throw selectionError(
      "phone.plan.session-ambiguous",
      "Plan session selector matched multiple live sessions.",
      matchingSessions,
    );
  }
  if (criteria.policy === "existing") {
    throw selectionError(
      "phone.plan.session-not-found",
      "Plan session selector did not match a live session.",
      sessions,
    );
  }

  const targets = arrayValue(await invoke("list_targets", {}), "list_targets") as DeviceTarget[];
  const matchingTargets = targets.filter((target) => matchesSelection(target, criteria));
  if (matchingTargets.length !== 1) {
    throw selectionError(
      matchingTargets.length === 0 ? "phone.plan.target-not-found" : "phone.plan.target-ambiguous",
      matchingTargets.length === 0
        ? "Plan session selector did not match a live target to start."
        : "Plan session selector matched multiple live targets.",
      matchingTargets.length === 0 ? targets : matchingTargets,
    );
  }
  const target = matchingTargets[0];
  const session = (await invoke("start_session", {
    surface_id: target.surfaceId,
    target_id: target.targetId,
  })) as DeviceSession;
  return Object.freeze({ session, target, startedSession: true });
}

async function executeStep(
  step: PlanStep,
  session: DeviceSession,
  invoke: InvokeFn,
): Promise<unknown> {
  const selected = { surface_id: session.surfaceId, session_id: session.sessionId };
  if (step.kind === "observe") return invoke("observe", { ...selected, mode: step.mode });
  if (step.kind === "tap") return invoke("tap", { ...selected, selector: step.selector });
  if (step.kind === "long_press") {
    return invoke("long_press", {
      ...selected,
      selector: step.selector,
      duration_ms: step.durationMs,
    });
  }
  if (step.kind === "wait") {
    return invoke("wait", {
      ...selected,
      condition: step.condition,
      ...(step.timeoutMs === undefined ? {} : { timeout_ms: step.timeoutMs }),
      ...(step.pollIntervalMs === undefined ? {} : { poll_interval_ms: step.pollIntervalMs }),
    });
  }
  if (step.kind === "assert")
    return invoke("assert", { ...selected, selector: step.selector, state: step.state });
  if (step.kind === "launch_app") {
    const receipt = (await invoke("manage_app", {
      ...selected,
      action: "launch",
      bundle_id: step.bundleId,
    })) as {
      status?: string;
      output?: { launched?: boolean };
    };
    if (receipt?.status !== "succeeded" || receipt?.output?.launched !== true) {
      throw planError(
        "phone.plan.app-launch-failed",
        "Plan app launch did not report a successful launch.",
        {
          status: receipt?.status,
          launched: receipt?.output?.launched === true,
        },
      );
    }
    return receipt;
  }
  if (step.kind === "capture_screenshot") {
    const receipt = await invoke("capture_screenshot", selected);
    requireSucceededReceipt(receipt, "capture_screenshot");
    return receipt;
  }
  if (step.kind === "run_native_test") {
    const receipt = (await invoke("run_native_test", {
      ...selected,
      selector: step.selector,
      ...(step.timeoutMs === undefined ? {} : { timeout_ms: step.timeoutMs }),
      ...(step.testTarget === undefined ? {} : { test_target: step.testTarget }),
      ...(step.testModule === undefined ? {} : { test_module: step.testModule }),
      ...(step.testBundleId === undefined ? {} : { test_bundle_id: step.testBundleId }),
      ...(step.runner === undefined ? {} : { runner: step.runner }),
    })) as { status?: string; output?: { outcome?: string } };
    requireSucceededReceipt(receipt, "run_native_test");
    if (receipt?.output?.outcome !== "passed") {
      throw planError(
        "phone.plan.native-test-not-passed",
        `Native test outcome is ${receipt?.output?.outcome ?? "missing"}, expected passed.`,
        { outcome: receipt?.output?.outcome ?? "missing" },
      );
    }
    return receipt;
  }
  throw planError("phone.plan.step-invalid", `Unsupported plan step: ${step.kind}`);
}

function normalizePlan(source: unknown): NormalizedPlan {
  if (!isRecord(source) || source.schemaVersion !== 1) {
    throw planError("phone.plan.invalid", "Plan must be an object with schemaVersion: 1.");
  }
  const session = normalizeSessionSelection(source.session);
  if (
    !Array.isArray(source.steps) ||
    source.steps.length === 0 ||
    source.steps.length > MAX_PLAN_STEPS
  ) {
    throw planError(
      "phone.plan.invalid",
      `Plan steps must contain 1 through ${MAX_PLAN_STEPS} entries.`,
    );
  }
  if (source.keepSession !== undefined && typeof source.keepSession !== "boolean") {
    throw planError("phone.plan.invalid", "Plan keepSession must be a boolean.");
  }
  return Object.freeze({
    session,
    steps: Object.freeze(source.steps.map((step, index) => normalizeStep(step, index))),
    keepSession: source.keepSession === true,
    evidence: normalizeEvidence(source.evidence),
  });
}

function normalizeEvidence(source: unknown): { screenshots: string; recording: string } {
  if (source === undefined) return Object.freeze({ screenshots: "off", recording: "off" });
  if (!isRecord(source)) throw planError("phone.plan.invalid", "Plan evidence must be an object.");
  const screenshots = (source.screenshots as string | undefined) ?? "off";
  const recording = (source.recording as string | undefined) ?? "off";
  if (!SCREENSHOT_POLICIES.has(screenshots)) {
    throw planError("phone.plan.invalid", "Plan evidence.screenshots must be off or on-failure.");
  }
  if (!RECORDING_POLICIES.has(recording)) {
    throw planError("phone.plan.invalid", "Plan evidence.recording must be off or native.");
  }
  return Object.freeze({ screenshots, recording });
}

function normalizeSessionSelection(source: unknown): SessionSelection {
  if (!isRecord(source)) throw planError("phone.plan.invalid", "Plan session must be an object.");
  const policy = (source.policy as string | undefined) ?? "existing";
  if (!SESSION_POLICIES.has(policy))
    throw planError(
      "phone.plan.invalid",
      "Plan session policy must be existing or reuse-or-start.",
    );
  const selection: SessionSelection = Object.freeze({
    policy,
    ...optionalString(source.surfaceId, "session.surfaceId"),
    ...optionalString(source.sessionId, "session.sessionId"),
    ...optionalString(source.targetId, "session.targetId"),
    ...optionalString(source.targetName, "session.targetName"),
    ...optionalString(source.runtimeKind, "session.runtimeKind"),
    ...optionalString(source.platform, "session.platform"),
  });
  if (
    (selection.surfaceId === undefined) !== (selection.sessionId === undefined) &&
    selection.sessionId !== undefined
  ) {
    throw planError("phone.plan.invalid", "session.sessionId requires session.surfaceId.");
  }
  if (selection.sessionId === undefined && selection.platform === undefined) {
    throw planError(
      "phone.plan.invalid",
      "Plan session requires exact surfaceId/sessionId or a platform selector.",
    );
  }
  if (selection.platform !== undefined && !PLATFORMS.has(selection.platform)) {
    throw planError("phone.plan.invalid", "session.platform must be android, harmony, or ios.");
  }
  return selection;
}

function normalizeStep(source: unknown, index: number): PlanStep {
  if (!isRecord(source) || typeof source.kind !== "string") {
    throw planError("phone.plan.invalid", `Plan step ${index} requires a kind.`);
  }
  if (source.kind === "observe") {
    if (source.mode !== undefined && source.mode !== "interactive" && source.mode !== "full") {
      throw planError("phone.plan.invalid", `steps[${index}].mode must be interactive or full.`);
    }
    return Object.freeze({
      kind: source.kind,
      mode: source.mode === "full" ? "full" : "interactive",
    });
  }
  if (source.kind === "tap" || source.kind === "long_press") {
    return Object.freeze({
      kind: source.kind,
      selector: requiredSelector(source.selector, index),
      ...(source.kind === "long_press" && source.durationMs !== undefined
        ? { durationMs: boundedInteger(source.durationMs, `steps[${index}].durationMs`, 1, 60_000) }
        : {}),
    });
  }
  if (source.kind === "wait") {
    return Object.freeze({
      kind: source.kind,
      condition: normalizeWaitCondition(source.condition, index),
      ...(source.timeoutMs === undefined
        ? {}
        : {
            timeoutMs: boundedInteger(
              source.timeoutMs,
              `steps[${index}].timeoutMs`,
              1,
              20 * 60_000,
            ),
          }),
      ...(source.pollIntervalMs === undefined
        ? {}
        : {
            pollIntervalMs: boundedInteger(
              source.pollIntervalMs,
              `steps[${index}].pollIntervalMs`,
              1,
              60_000,
            ),
          }),
    });
  }
  if (source.kind === "assert") {
    if (source.state !== undefined && source.state !== "present" && source.state !== "absent") {
      throw planError("phone.plan.invalid", `steps[${index}].state must be present or absent.`);
    }
    const state = source.state === "absent" ? ("absent" as const) : ("present" as const);
    return Object.freeze({
      kind: source.kind,
      selector: requiredSelector(source.selector, index),
      state,
    });
  }
  if (source.kind === "launch_app") {
    return Object.freeze({
      kind: source.kind,
      bundleId: requiredString(source.bundleId, `steps[${index}].bundleId`),
    });
  }
  if (source.kind === "capture_screenshot") return Object.freeze({ kind: source.kind });
  if (source.kind === "run_native_test") {
    return Object.freeze({
      kind: source.kind,
      selector: requiredString(source.selector, `steps[${index}].selector`),
      ...(source.timeoutMs === undefined
        ? {}
        : {
            timeoutMs: boundedInteger(
              source.timeoutMs,
              `steps[${index}].timeoutMs`,
              1_000,
              20 * 60_000,
            ),
          }),
      ...optionalNamedString(source.testTarget, "testTarget", `steps[${index}].testTarget`),
      ...optionalNamedString(source.testModule, "testModule", `steps[${index}].testModule`),
      ...optionalNamedString(source.testBundleId, "testBundleId", `steps[${index}].testBundleId`),
      ...optionalNamedString(source.runner, "runner", `steps[${index}].runner`),
    });
  }
  throw planError(
    "phone.plan.invalid",
    `Unsupported plan step kind at index ${index}: ${source.kind}`,
  );
}

function normalizeWaitCondition(source: unknown, index: number): WaitCondition {
  if (!isRecord(source) || typeof source.kind !== "string") {
    throw planError(
      "phone.plan.invalid",
      `steps[${index}].condition must be an object with a kind.`,
    );
  }
  if (source.kind === "stable") {
    return Object.freeze({
      kind: source.kind,
      ...(source.durationMs === undefined
        ? {}
        : {
            durationMs: boundedInteger(
              source.durationMs,
              `steps[${index}].condition.durationMs`,
              1,
              20 * 60_000,
            ),
          }),
    });
  }
  if (source.kind === "present" || source.kind === "absent") {
    return Object.freeze({ kind: source.kind, selector: requiredSelector(source.selector, index) });
  }
  throw planError(
    "phone.plan.invalid",
    `Unsupported wait condition at step ${index}: ${source.kind}`,
  );
}

function matchesSelection(
  item: DeviceSession | DeviceTarget | undefined,
  selection: SessionSelection,
): boolean {
  const record = item as unknown as JsonRecord | undefined;
  return (
    ["surfaceId", "sessionId", "targetId", "targetName", "runtimeKind", "platform"] as const
  ).every((key) => selection[key] === undefined || record?.[key] === selection[key]);
}

function summarizeStep(kind: string, value: unknown): unknown {
  if (kind === "observe" || kind === "wait") return summarizeObservation(value);
  if (kind === "tap" || kind === "long_press") {
    const v = (value ?? {}) as {
      uiChanged?: boolean;
      element?: UiElement;
      observation?: unknown;
      receipt?: unknown;
    };
    return Object.freeze({
      uiChanged: v.uiChanged === true,
      element: summarizeElement(v.element),
      observation: summarizeObservation(v.observation),
      receipt: summarizeReceipt(v.receipt),
    });
  }
  if (kind === "assert") {
    const v = (value ?? {}) as {
      passed?: boolean;
      reason?: string;
      element?: UiElement;
      observation?: unknown;
    };
    return Object.freeze({
      passed: v.passed === true,
      ...(typeof v.reason === "string" ? { reason: v.reason } : {}),
      ...(v.element ? { element: summarizeElement(v.element) } : {}),
      observation: summarizeObservation(v.observation),
    });
  }
  if (kind === "capture_screenshot" || kind === "record_screen")
    return summarizeVisualReceipt(value);
  return value;
}

function summarizeVisualReceipt(value: unknown): unknown {
  if (!isRecord(value)) return value;
  const artifact = summarizeArtifact((value.output as JsonRecord | undefined)?.artifact);
  return Object.freeze({
    operationId: value.operationId,
    operation: value.operation,
    status: value.status,
    ...(value.startedAt ? { startedAt: value.startedAt } : {}),
    ...(value.completedAt ? { completedAt: value.completedAt } : {}),
    ...(value.sessionId ? { sessionId: value.sessionId } : {}),
    ...(value.revision ? { revision: value.revision } : {}),
    ...(isRecord(value.output)
      ? {
          output: Object.freeze({
            ...(typeof (value.output as JsonRecord).active === "boolean"
              ? { active: (value.output as JsonRecord).active }
              : {}),
            ...(typeof (value.output as JsonRecord).startedAt === "string"
              ? { startedAt: (value.output as JsonRecord).startedAt }
              : {}),
            ...(artifact ? { artifact } : {}),
          }),
        }
      : {}),
    ...(Array.isArray(value.evidence)
      ? {
          evidence: Object.freeze(
            (value.evidence as unknown[]).map(summarizeEvidenceRef).filter(Boolean),
          ),
        }
      : {}),
  });
}

function summarizeArtifact(value: unknown): JsonRecord | undefined {
  if (!isRecord(value)) return undefined;
  const keys = [
    "artifactId",
    "createdAt",
    "mediaType",
    "size",
    "algorithm",
    "digest",
    "uri",
    "source",
    "platform",
    "targetId",
    "sessionId",
    "revision",
  ];
  return Object.freeze(
    Object.fromEntries(
      keys.flatMap((key) => (value[key] === undefined ? [] : [[key, value[key]]])),
    ),
  );
}

function summarizeEvidenceRef(value: unknown): JsonRecord | undefined {
  if (!isRecord(value)) return undefined;
  const keys = ["algorithm", "digest", "mediaType", "size", "uri"];
  return Object.freeze(
    Object.fromEntries(
      keys.flatMap((key) => (value[key] === undefined ? [] : [[key, value[key]]])),
    ),
  );
}

function summarizePlanEvidence(
  failureScreenshot: unknown,
  recording: unknown,
  errors: JsonRecord[],
): JsonRecord | undefined {
  if (!failureScreenshot && !recording && errors.length === 0) return undefined;
  return Object.freeze({
    ...(failureScreenshot ? { failureScreenshot } : {}),
    ...(recording ? { recording } : {}),
    ...(errors.length ? { errors: Object.freeze([...errors]) } : {}),
  });
}

function summarizeEvidenceError(error: unknown, phase: string): JsonRecord {
  const e = error as CliError;
  return Object.freeze({
    phase,
    code: typeof e?.code === "string" ? e.code : "phone.plan.evidence-failed",
    message: error instanceof Error ? error.message : String(error),
  });
}

function summarizeObservation(value: unknown): JsonRecord {
  const v = (value ?? {}) as Partial<Observation> & { screen?: unknown };
  return Object.freeze({
    uiRevision: v.uiRevision,
    snapshotId: v.snapshotId,
    platform: v.platform,
    source: v.source,
    screen: v.screen,
    truncated: v.truncated === true,
    elementCount: Number.isInteger(v.elementCount)
      ? v.elementCount
      : Array.isArray(v.elements)
        ? v.elements.length
        : 0,
  });
}

function summarizeElement(value: unknown): JsonRecord | undefined {
  if (!isRecord(value)) return undefined;
  return Object.freeze({
    ...(typeof value.ref === "string" ? { ref: value.ref } : {}),
    ...(typeof value.identifier === "string" ? { identifier: value.identifier } : {}),
    ...(typeof value.label === "string" ? { label: value.label } : {}),
    ...(typeof value.role === "string" ? { role: value.role } : {}),
    ...(typeof value.type === "string" ? { type: value.type } : {}),
  });
}

function summarizeReceipt(value: unknown): JsonRecord | undefined {
  if (!isRecord(value)) return undefined;
  return Object.freeze({
    operationId: value.operationId,
    operation: value.operation,
    status: value.status,
    ...(value.output === undefined ? {} : { output: value.output }),
  });
}

function arrayValue(value: unknown, command: string): unknown[] {
  if (!Array.isArray(value))
    throw planError("phone.plan.command-invalid", `${command} did not return an array.`);
  return value;
}

function requiredSelector(value: unknown, index: number): Selector {
  if (!isRecord(value))
    throw planError("phone.plan.invalid", `steps[${index}].selector must be an object.`);
  const keys = ["ref", "identifier", "label", "role", "type"] as const;
  if (!keys.some((key) => typeof value[key] === "string" && (value[key] as string).trim())) {
    throw planError(
      "phone.plan.invalid",
      `steps[${index}].selector requires ref, identifier, label, role, or type.`,
    );
  }
  return Object.freeze(
    Object.fromEntries(
      keys.flatMap((key) =>
        typeof value[key] === "string" && (value[key] as string).trim()
          ? [[key, (value[key] as string).trim()]]
          : [],
      ),
    ),
  ) as Selector;
}

function optionalString(value: unknown, name: string): Record<string, string> {
  if (value === undefined) return {};
  const key = name.slice(name.lastIndexOf(".") + 1);
  return { [key]: requiredString(value, name) };
}

function optionalNamedString(value: unknown, key: string, name: string): Record<string, string> {
  return value === undefined ? {} : { [key]: requiredString(value, name) };
}

function requiredString(value: unknown, name: string): string {
  if (typeof value !== "string" || !value.trim())
    throw planError("phone.plan.invalid", `${name} must be a non-empty string.`);
  return value.trim();
}

function boundedInteger(value: unknown, name: string, minimum: number, maximum: number): number {
  if (!Number.isInteger(value) || (value as number) < minimum || (value as number) > maximum) {
    throw planError(
      "phone.plan.invalid",
      `${name} must be an integer from ${minimum} through ${maximum}.`,
    );
  }
  return value as number;
}

function requireSucceededReceipt(receipt: unknown, stepKind: string): void {
  const r = receipt as { status?: string };
  if (r?.status !== "succeeded") {
    throw planError(
      "phone.plan.operation-failed",
      `${stepKind} did not return a succeeded operation receipt.`,
      {
        stepKind,
        status: r?.status ?? "missing",
      },
    );
  }
}

function selectionError(
  code: string,
  message: string,
  candidates: Array<DeviceSession | DeviceTarget>,
): CliError {
  return planError(code, message, {
    candidates: candidates.slice(0, 20).map((item) => ({
      surfaceId: item?.surfaceId,
      ...("sessionId" in item && item.sessionId ? { sessionId: item.sessionId } : {}),
      ...("targetId" in item && item.targetId ? { targetId: item.targetId } : {}),
      platform: item?.platform,
      targetName: item?.targetName,
      runtimeKind: item?.runtimeKind,
      state: item?.state,
    })),
  });
}

function annotateStepError(error: unknown, stepIndex: number, stepKind: string): CliError {
  const normalized = (error instanceof Error ? error : new Error(String(error))) as CliError;
  normalized.details = Object.freeze({
    ...(isRecord(normalized.details) ? normalized.details : {}),
    stepIndex,
    stepKind,
  });
  return normalized;
}

function annotateEvidencePhase(error: unknown, evidencePhase: string): CliError {
  const normalized = (error instanceof Error ? error : new Error(String(error))) as CliError;
  normalized.details = Object.freeze({
    ...(isRecord(normalized.details) ? normalized.details : {}),
    evidencePhase,
  });
  return normalized;
}

function attachPlanEvidence(error: CliError, evidence: JsonRecord): void {
  error.details = Object.freeze({
    ...(isRecord(error.details) ? error.details : {}),
    evidence,
  });
}

function planError(code: string, message: string, details?: JsonRecord): CliError {
  const error = cliError(code, message);
  if (details !== undefined) error.details = Object.freeze(details);
  return error;
}
