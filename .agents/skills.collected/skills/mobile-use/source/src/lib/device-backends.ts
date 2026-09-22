import * as android from "./android-backend.ts";
import * as ios from "./ios-backend.ts";
import * as harmony from "./harmony-backend.ts";
import { cliError } from "./types.ts";
import type { JsonRecord } from "./types.ts";

interface Backend {
  listLiveTargets: () => Promise<unknown[]>;
  listLiveSessions: () => Promise<unknown[]>;
  startPhoneUseSession: (surfaceId: string, targetId: string) => Promise<unknown>;
  stopPhoneUseSession: (surfaceId?: string, sessionId?: string) => Promise<unknown>;
  invokePhoneUse: (
    surfaceId: string,
    sessionId: string,
    method: string,
    input?: JsonRecord,
  ) => Promise<unknown>;
  invokeSessionOperation: (
    surfaceId: string,
    sessionId: string,
    operation: string,
    capability: string,
    input?: JsonRecord,
  ) => Promise<unknown>;
  invokeTargetOperation: (
    surfaceId: string,
    targetId: string,
    operation: string,
    capability?: string,
    input?: JsonRecord,
  ) => Promise<unknown>;
}

const backends = Object.freeze([
  Object.freeze({ platform: "android", impl: android as Backend }),
  Object.freeze({ platform: "harmony", impl: harmony as Backend }),
  Object.freeze({ platform: "ios", impl: ios as Backend }),
]);

async function collect(fnName: "listLiveTargets" | "listLiveSessions"): Promise<unknown[]> {
  const settled = await Promise.all(
    backends.map(async ({ platform: _platform, impl }) => {
      try {
        const values = await impl[fnName]();
        return Array.isArray(values) ? values : [];
      } catch {
        return [];
      }
    }),
  );
  return settled.flat();
}

export async function listLiveTargets(): Promise<unknown[]> {
  return collect("listLiveTargets");
}

export async function listLiveSessions(): Promise<unknown[]> {
  return collect("listLiveSessions");
}

function backendForSurface(surfaceId: string): Backend {
  if (surfaceId === "adb-android") return android as Backend;
  if (surfaceId === "simctl-ios") return ios as Backend;
  if (surfaceId === "hdc-harmony") return harmony as Backend;
  throw cliError(
    "device.surface.stale",
    `Unknown surface ${surfaceId}. Run list-targets to discover live surfaces.`,
  );
}

export async function startPhoneUseSession(surfaceId: string, targetId: string) {
  return backendForSurface(surfaceId).startPhoneUseSession(surfaceId, targetId);
}

export async function stopPhoneUseSession(surfaceId: string, sessionId: string) {
  return backendForSurface(surfaceId).stopPhoneUseSession(surfaceId, sessionId);
}

export async function invokePhoneUse(
  surfaceId: string,
  sessionId: string,
  method: string,
  input?: JsonRecord,
) {
  return backendForSurface(surfaceId).invokePhoneUse(surfaceId, sessionId, method, input);
}

export async function invokeSessionOperation(
  surfaceId: string,
  sessionId: string,
  operation: string,
  capability: string,
  input?: JsonRecord,
) {
  return backendForSurface(surfaceId).invokeSessionOperation(
    surfaceId,
    sessionId,
    operation,
    capability,
    input,
  );
}

export async function invokeTargetOperation(
  surfaceId: string,
  targetId: string,
  operation: string,
  capability: string,
  input?: JsonRecord,
) {
  return backendForSurface(surfaceId).invokeTargetOperation(
    surfaceId,
    targetId,
    operation,
    capability,
    input,
  );
}
