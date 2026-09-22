import {
  invokePhoneUse,
  invokeSessionOperation,
  invokeTargetOperation,
  listLiveSessions,
  listLiveTargets,
  startPhoneUseSession,
  stopPhoneUseSession,
} from "./device-backends.ts";
import {
  SESSION_OPERATION_COMMANDS,
  TARGET_OPERATION_COMMANDS,
  operationAndInput,
  sessionSelection,
  targetAndInput,
  targetSelection,
} from "./phone-arguments.ts";
import { executePhoneInventory, executePhonePlan } from "./phone-plan.ts";
import { cliError } from "./types.ts";
import type { JsonRecord } from "./types.ts";

export const CORE_PHONE_COMMANDS = Object.freeze([
  "inventory",
  "list_targets",
  "start_session",
  "stop_session",
  "list_sessions",
  "observe",
  "tap",
  "long_press",
  "act",
  "wait",
  "assert",
  "run_plan",
]);

export const OPERATIONAL_PHONE_COMMANDS = Object.freeze([
  "restart_target",
  "manage_app",
  "read_logs",
  "run_native_test",
  "capture_screenshot",
  "record_screen",
]);

export const PHONE_COMMANDS = Object.freeze([
  ...CORE_PHONE_COMMANDS,
  ...OPERATIONAL_PHONE_COMMANDS,
]);

export interface PhoneDependencies {
  listLiveSessions?: typeof listLiveSessions;
  listLiveTargets?: typeof listLiveTargets;
  startPhoneUseSession?: typeof startPhoneUseSession;
  stopPhoneUseSession?: typeof stopPhoneUseSession;
  invokePhoneUse?: typeof invokePhoneUse;
  invokeSessionOperation?: typeof invokeSessionOperation;
  invokeTargetOperation?: typeof invokeTargetOperation;
}

export async function executePhoneCommand(
  command: string,
  args: JsonRecord = {},
  dependencies: PhoneDependencies = {},
): Promise<unknown> {
  if (!PHONE_COMMANDS.includes(command)) {
    throw cliError("phone.command.unknown", `Unknown Mobile Use command: ${command}`);
  }

  const listSessions = dependencies.listLiveSessions ?? listLiveSessions;
  const listTargets = dependencies.listLiveTargets ?? listLiveTargets;
  const startSession = dependencies.startPhoneUseSession ?? startPhoneUseSession;
  const stopSession = dependencies.stopPhoneUseSession ?? stopPhoneUseSession;
  const invoke = dependencies.invokePhoneUse ?? invokePhoneUse;
  const invokeSession = dependencies.invokeSessionOperation ?? invokeSessionOperation;
  const invokeTarget = dependencies.invokeTargetOperation ?? invokeTargetOperation;

  const invokeCommand = (nextCommand: string, nextArgs: JsonRecord = {}) =>
    executePhoneCommand(nextCommand, nextArgs, dependencies);

  if (command === "inventory") return executePhoneInventory(invokeCommand);
  if (command === "run_plan") return executePhonePlan(args.plan, invokeCommand);

  if (command === "list_targets") return listTargets();
  if (command === "start_session") {
    const target = targetSelection(args);
    return startSession(target.surfaceId, target.targetId);
  }
  if (command === "stop_session") {
    const target = sessionSelection(args);
    return stopSession(target.surfaceId, target.sessionId);
  }
  if (command === "list_sessions") return listSessions();
  if (TARGET_OPERATION_COMMANDS[command]) {
    const target = operationAndInput(command, args);
    return invokeTarget(
      target.surfaceId,
      (target as { targetId: string }).targetId,
      target.operation,
      target.capability,
      target.input,
    );
  }
  if (SESSION_OPERATION_COMMANDS[command]) {
    const target = operationAndInput(command, args);
    return invokeSession(
      target.surfaceId,
      (target as { sessionId: string }).sessionId,
      target.operation,
      target.capability,
      target.input,
    );
  }

  const target = targetAndInput(command, args);
  if (command === "tap" || command === "long_press") {
    return summarizePerformResult(
      await invoke(target.surfaceId, target.sessionId, "perform", target.input),
    );
  }
  return invoke(target.surfaceId, target.sessionId, command, target.input);
}

interface PerformValue {
  uiChanged?: boolean;
  element?: { ref?: string; identifier?: string; label?: string; role?: string; type?: string };
  observation?: {
    uiRevision?: number;
    snapshotId?: string;
    platform?: string;
    source?: string;
    screen?: unknown;
    truncated?: boolean;
    elements?: unknown[];
  };
  receipt?: { operationId?: string; operation?: string; status?: string; output?: unknown };
}

function summarizePerformResult(value: unknown) {
  const v = (value ?? {}) as PerformValue;
  const observation = v.observation;
  const element = v.element;
  const receipt = v.receipt;
  return Object.freeze({
    uiChanged: v.uiChanged === true,
    ...(element && typeof element === "object"
      ? {
          element: Object.freeze({
            ...(typeof element.ref === "string" ? { ref: element.ref } : {}),
            ...(typeof element.identifier === "string" ? { identifier: element.identifier } : {}),
            ...(typeof element.label === "string" ? { label: element.label } : {}),
            ...(typeof element.role === "string" ? { role: element.role } : {}),
            ...(typeof element.type === "string" ? { type: element.type } : {}),
          }),
        }
      : {}),
    observation: Object.freeze({
      uiRevision: observation?.uiRevision,
      snapshotId: observation?.snapshotId,
      platform: observation?.platform,
      source: observation?.source,
      screen: observation?.screen,
      truncated: observation?.truncated === true,
      elementCount: Array.isArray(observation?.elements) ? observation.elements.length : 0,
    }),
    ...(receipt && typeof receipt === "object"
      ? {
          receipt: Object.freeze({
            operationId: receipt.operationId,
            operation: receipt.operation,
            status: receipt.status,
            ...(receipt.output === undefined ? {} : { output: receipt.output }),
          }),
        }
      : {}),
  });
}
