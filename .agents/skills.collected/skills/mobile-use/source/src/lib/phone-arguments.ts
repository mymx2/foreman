import { cliError, isRecord } from "./types.ts";
import type { JsonRecord } from "./types.ts";

const SESSION_PROPERTIES = Object.freeze(["surface_id", "session_id"]);

export const TARGET_OPERATION_COMMANDS: Readonly<
  Record<string, Readonly<{ operation: string; capability: string }>>
> = Object.freeze({
  restart_target: Object.freeze({
    operation: "device.target.restart",
    capability: "device.target.restart",
  }),
});

export const SESSION_OPERATION_COMMANDS: Readonly<
  Record<string, Readonly<{ operation: string; capability: string } | { group: string }>>
> = Object.freeze({
  manage_app: Object.freeze({ group: "app" }),
  read_logs: Object.freeze({ operation: "device.logs.read", capability: "device.logs.read" }),
  run_native_test: Object.freeze({ operation: "device.test.run", capability: "device.test.run" }),
  capture_screenshot: Object.freeze({
    operation: "device.capture.screenshot",
    capability: "device.frame.screenshot",
  }),
  record_screen: Object.freeze({ group: "recording" }),
});

type PhoneParams = JsonRecord;

export function targetAndInput(command: string, params: PhoneParams) {
  const { surfaceId, sessionId } = sessionSelection(params);
  if (command === "observe") {
    return {
      surfaceId,
      sessionId,
      input: { mode: params.mode === "full" ? "full" : "interactive" },
    };
  }
  if (command === "act") {
    if (!Number.isInteger(params.ui_revision) || (params.ui_revision as number) < 1) {
      throw new TypeError("ui_revision must be a positive integer from observe.");
    }
    return {
      surfaceId,
      sessionId,
      input: { uiRevision: params.ui_revision, action: requiredRecord(params.action, "action") },
    };
  }
  if (command === "tap" || command === "long_press") {
    return {
      surfaceId,
      sessionId,
      input: {
        action: {
          kind: command === "tap" ? "tap" : "long-press",
          selector: requiredRecord(params.selector, "selector"),
          ...(command === "long_press" && params.duration_ms !== undefined
            ? { durationMs: boundedInteger(params.duration_ms, "duration_ms", 1, 60_000) }
            : {}),
        },
      },
    };
  }
  if (command === "wait") {
    return {
      surfaceId,
      sessionId,
      input: {
        condition: requiredRecord(params.condition, "condition"),
        ...(typeof params.timeout_ms === "number" ? { timeoutMs: params.timeout_ms } : {}),
        ...(typeof params.poll_interval_ms === "number"
          ? { pollIntervalMs: params.poll_interval_ms }
          : {}),
      },
    };
  }
  if (command === "assert") {
    return {
      surfaceId,
      sessionId,
      input: {
        selector: requiredRecord(params.selector, "selector"),
        state: params.state === "absent" ? "absent" : "present",
      },
    };
  }
  throw commandError("phone.command.unknown", `Unknown Mobile Use command: ${command}`);
}

export function targetSelection(params: PhoneParams) {
  return {
    surfaceId: requiredString(params.surface_id, "surface_id"),
    targetId: requiredString(params.target_id, "target_id"),
  };
}

export function operationAndInput(
  command: string,
  params: PhoneParams,
): {
  surfaceId: string;
  targetId?: string;
  sessionId?: string;
  operation: string;
  capability: string;
  input: JsonRecord;
} {
  const targetDefinition = (
    TARGET_OPERATION_COMMANDS as Record<
      string,
      { operation: string; capability: string } | undefined
    >
  )[command];
  if (targetDefinition) return { ...targetSelection(params), ...targetDefinition, input: {} };

  const selection = sessionSelection(params);
  if (command === "manage_app") {
    if (params.action === "list")
      return {
        ...selection,
        operation: "device.app.list",
        capability: "device.app.list",
        input: {},
      };
    if (params.action === "install")
      return {
        ...selection,
        operation: "device.app.install",
        capability: "device.app.install",
        input: { path: requiredString(params.path, "path") },
      };
    if (params.action === "launch")
      return {
        ...selection,
        operation: "device.app.launch",
        capability: "device.app.launch",
        input: { bundleId: requiredString(params.bundle_id, "bundle_id") },
      };
    if (params.action === "terminate")
      return {
        ...selection,
        operation: "device.app.terminate",
        capability: "device.app.terminate",
        input: { bundleId: requiredString(params.bundle_id, "bundle_id") },
      };
    if (params.action === "uninstall")
      return {
        ...selection,
        operation: "device.app.uninstall",
        capability: "device.app.uninstall",
        input: {
          bundleId: requiredString(params.bundle_id, "bundle_id"),
          confirm: requireConfirmation(params.confirm),
        },
      };
    throw new TypeError(
      "manage_app action must be list, install, launch, terminate, or uninstall.",
    );
  }
  if (command === "record_screen") {
    const operations: Record<string, string> = {
      start: "device.recording.start",
      status: "device.recording.status",
      stop: "device.recording.stop",
    };
    const operation = operations[params.action as string];
    if (!operation) throw new TypeError("record_screen action must be start, status, or stop.");
    return { ...selection, operation, capability: "device.recording.native", input: {} };
  }

  const sessionDefinition = (
    SESSION_OPERATION_COMMANDS as Record<
      string,
      { operation?: string; capability?: string; group?: string } | undefined
    >
  )[command];
  if (!sessionDefinition?.operation)
    throw commandError("phone.command.unknown", `Unknown Mobile Use command: ${command}`);
  let input: Record<string, unknown> = {};
  if (command === "read_logs") {
    input = {
      ...(params.bundle_id === undefined
        ? {}
        : { bundleId: requiredString(params.bundle_id, "bundle_id") }),
      ...(params.seconds === undefined
        ? {}
        : { seconds: boundedInteger(params.seconds, "seconds", 1, 3_600) }),
      ...(params.limit === undefined
        ? {}
        : { limit: boundedInteger(params.limit, "limit", 1, 5_000) }),
    };
  } else if (command === "run_native_test") {
    input = {
      selector: requiredString(params.selector, "selector"),
      ...(params.timeout_ms === undefined
        ? {}
        : { timeoutMs: boundedInteger(params.timeout_ms, "timeout_ms", 1_000, 20 * 60_000) }),
      ...(params.test_target === undefined
        ? {}
        : { testTarget: requiredString(params.test_target, "test_target") }),
      ...(params.test_module === undefined
        ? {}
        : { testModule: requiredString(params.test_module, "test_module") }),
      ...(params.test_bundle_id === undefined
        ? {}
        : { testBundleId: requiredString(params.test_bundle_id, "test_bundle_id") }),
      ...(params.test_package === undefined
        ? {}
        : { testPackage: requiredString(params.test_package, "test_package") }),
      ...(params.runner === undefined ? {} : { runner: requiredString(params.runner, "runner") }),
    };
  }
  return {
    ...selection,
    ...(sessionDefinition as { operation: string; capability: string }),
    input,
  };
}

export function sessionSelection(params: PhoneParams): { surfaceId: string; sessionId: string } {
  return Object.fromEntries(
    SESSION_PROPERTIES.map((name) => [toCamelCase(name), requiredString(params[name], name)]),
  ) as { surfaceId: string; sessionId: string };
}

function requireConfirmation(value: unknown): true {
  if (value !== true) throw new TypeError("manage_app uninstall requires confirm=true.");
  return true;
}

function requiredString(value: unknown, name: string): string {
  if (typeof value !== "string" || !value.trim()) throw new TypeError(`${name} is required.`);
  return value.trim();
}

function requiredRecord(value: unknown, name: string): JsonRecord {
  if (!isRecord(value)) throw new TypeError(`${name} must be an object.`);
  return value;
}

function boundedInteger(value: unknown, name: string, minimum: number, maximum: number): number {
  if (typeof value !== "number" || !Number.isInteger(value) || value < minimum || value > maximum) {
    throw new TypeError(`${name} must be an integer from ${minimum} through ${maximum}.`);
  }
  return value;
}

function toCamelCase(value: string): string {
  return value.replace(/_([a-z])/gu, (_match, character: string) => character.toUpperCase());
}

function commandError(code: string, message: string) {
  return cliError(code, message);
}
