export type Platform = "android" | "harmony" | "ios";
export type RuntimeKind = "emulator" | "physical" | "previewer" | "remote" | "simulator";

export interface DeviceTarget {
  surfaceId: string;
  adapterId: string;
  targetId: string;
  platform: Platform;
  targetName: string;
  runtimeKind: RuntimeKind;
  state: string;
  targetCapabilities: string[];
  runtime?: string;
}

export interface DeviceSession {
  surfaceId: string;
  sessionId: string;
  targetId: string;
  platform: Platform;
  targetName: string;
  runtimeKind: RuntimeKind;
  state: string;
  capabilities: Array<{ id: string }>;
}

export interface UiElement {
  ref: string;
  identifier?: string;
  label?: string;
  contentDesc?: string;
  text?: string;
  role?: string;
  type?: string;
  clickable?: boolean;
  enabled?: boolean;
  center?: { x: number; y: number };
  interactive?: boolean;
}

export interface Observation {
  uiRevision: number;
  snapshotId: string;
  platform: string;
  source: string;
  elementCount: number;
  truncated: boolean;
  elements: UiElement[];
}

export interface Selector {
  ref?: string;
  identifier?: string;
  label?: string;
  role?: string;
  type?: string;
}

export interface Artifact {
  artifactId: string;
  createdAt: string;
  mediaType: string;
  size: number;
  algorithm: string;
  digest: string;
  uri: string;
  source: string;
  platform: Platform;
  targetId: string;
}

export interface OperationReceipt<T = unknown> {
  operationId: string;
  operation: string;
  status: "succeeded" | "failed";
  completedAt?: string;
  output?: T;
}

export type NativeTestOutcome =
  | "passed"
  | "assertion_failed"
  | "runner_mismatch"
  | "crashed_before_assertion"
  | "target_offline"
  | "timeout"
  | "build_failed"
  | "install_failed"
  | "launch_failed";

export interface CliError extends Error {
  code?: string;
  details?: Record<string, unknown>;
}

export type JsonRecord = Record<string, unknown>;

export interface DoctorCheck {
  platform: Platform;
  status: "ready" | "missing" | "unsupported";
  tools: Record<string, unknown>;
  guidance: string | null;
  avds?: string[];
}

export interface DoctorReport {
  schemaVersion: 1;
  host: string;
  platform: string;
  checks: DoctorCheck[];
  summary: { total: number; ready: number; missing: number; unsupported: number };
}

export function cliError(code: string, message: string): CliError {
  const error: CliError = new Error(message);
  error.code = code;
  return error;
}

export function isRecord(value: unknown): value is JsonRecord {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}
