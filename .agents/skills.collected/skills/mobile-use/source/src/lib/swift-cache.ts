import { readdir, readFile, rm, stat } from "node:fs/promises";
import { execFileSync } from "node:child_process";
import os from "node:os";
import path from "node:path";
import { cliError } from "./types.ts";
import type { JsonRecord } from "./types.ts";

const DEFAULT_MAX_AGE_DAYS = 30;
const DEFAULT_MAX_SIZE_MB = 8 * 1024;
const MAX_CACHE_ENTRIES = 1_024;

export const SWIFT_CACHE_COMMANDS: readonly string[] = Object.freeze([
  "swift_cache_status",
  "swift_cache_prune",
  "swift_cache_clean",
]);

interface CacheActivity {
  active: boolean;
  activePids: number[];
  staleLeaseCount?: number;
  known?: boolean;
}

interface CacheEntry {
  active: boolean;
  activePids: number[];
  activityKnown?: boolean;
  cacheIdentity: string;
  entryRoot: string;
  healthy: boolean;
  lastUsedAt: string;
  legacy?: boolean;
  packageIdentity: string;
  packageSwift?: string;
  packageTarget?: string;
  sizeBytes: number;
  staleLeaseCount: number;
}

interface ProcessRecord {
  pid: number;
  command: string;
}

export async function executeSwiftCacheCommand(command: string, args: JsonRecord = {}) {
  if (!SWIFT_CACHE_COMMANDS.includes(command)) {
    throw cliError("swift.cache.command.unknown", `Unknown Swift cache command: ${command}`);
  }
  const cacheRoot = resolveSwiftCacheRoot(args.cache_root);
  const entries = await scanSwiftCache(cacheRoot);
  if (command === "swift_cache_status") return summarizeCache(cacheRoot, entries);
  if (command === "swift_cache_prune") {
    const maxAgeDays = boundedNumber(
      args.max_age_days,
      "max_age_days",
      1,
      3650,
      DEFAULT_MAX_AGE_DAYS,
    );
    const maxSizeMb = boundedNumber(
      args.max_size_mb,
      "max_size_mb",
      128,
      1024 * 1024,
      DEFAULT_MAX_SIZE_MB,
    );
    const includeLegacy = args.include_legacy === true;
    const selected = selectPrunableEntries(entries, {
      includeLegacy,
      maxAgeDays,
      maxSizeBytes: maxSizeMb * 1024 * 1024,
    });
    const applied = args.apply === true;
    if (applied) await removeCacheEntries(cacheRoot, selected);
    const candidateBytes = selected.reduce((total, entry) => total + entry.sizeBytes, 0);
    return Object.freeze({
      cacheRoot,
      applied,
      policy: { includeLegacy, maxAgeDays, maxSizeMb },
      candidateBytes,
      reclaimedBytes: applied ? candidateBytes : 0,
      candidates: selected.map(publicEntry),
      removed: applied ? selected.map(publicEntry) : [],
      skippedActive: entries.filter((entry) => entry.active).map(publicEntry),
      skippedLegacy: includeLegacy ? [] : entries.filter((entry) => entry.legacy).map(publicEntry),
    });
  }

  if (args.confirm !== true) {
    throw cliError("swift.cache.confirmation.required", "swift_cache_clean requires --confirm.");
  }
  const packageSwift =
    args.package_swift === undefined
      ? undefined
      : optionalAbsolutePath(args.package_swift, "package_swift");
  const cacheIdentity = optionalString(args.cache_identity);
  if (!packageSwift && !cacheIdentity) {
    throw cliError(
      "swift.cache.argument",
      "swift_cache_clean requires --package-swift or --cache-identity.",
    );
  }
  const selected = entries.filter(
    (entry) =>
      (!packageSwift || entry.packageSwift === packageSwift) &&
      (!cacheIdentity || entry.cacheIdentity === cacheIdentity),
  );
  const active = selected.filter((entry) => entry.active);
  if (active.length) {
    throw cliError(
      "swift.cache.active",
      `Refusing to remove ${active.length} active Swift preview cache entr${active.length === 1 ? "y" : "ies"}.`,
    );
  }
  await removeCacheEntries(cacheRoot, selected);
  return Object.freeze({
    cacheRoot,
    removed: selected.map(publicEntry),
    reclaimedBytes: selected.reduce((total, entry) => total + entry.sizeBytes, 0),
  });
}

export async function scanSwiftCache(cacheRoot: string): Promise<CacheEntry[]> {
  const packagesRoot = path.join(cacheRoot, "packages");
  const packageEntries = await readDirectories(packagesRoot);
  const cacheEntries: CacheEntry[] = [];
  for (const packageEntry of packageEntries) {
    const entriesRoot = path.join(packagesRoot, packageEntry.name, "entries");
    for (const entry of await readDirectories(entriesRoot)) {
      if (cacheEntries.length >= MAX_CACHE_ENTRIES) {
        throw cliError(
          "swift.cache.too-many-entries",
          `Swift preview cache exceeds ${MAX_CACHE_ENTRIES} entries; clean it with an exact cache path before retrying.`,
        );
      }
      const entryRoot = path.join(entriesRoot, entry.name);
      const [metadata, entryStat, activity, sizeBytes] = await Promise.all([
        readJsonIfExists(path.join(entryRoot, "cache-metadata.json")),
        stat(entryRoot),
        inspectActivity(entryRoot),
        directorySize(entryRoot),
      ]);
      const lastUsedAt =
        validDate(metadata?.lastUsedAt) ??
        validDate(metadata?.createdAt) ??
        entryStat.mtime.toISOString();
      cacheEntries.push(
        Object.freeze({
          active: activity.active,
          activePids: activity.activePids,
          cacheIdentity:
            typeof metadata?.cacheIdentity === "string" ? metadata.cacheIdentity : entry.name,
          entryRoot,
          healthy: metadata?.schemaVersion === 1 && metadata?.kind === "swiftui-package-preview",
          lastUsedAt,
          packageIdentity:
            typeof metadata?.packageIdentity === "string"
              ? metadata.packageIdentity
              : packageEntry.name,
          packageSwift:
            typeof metadata?.packageSwift === "string"
              ? path.resolve(metadata.packageSwift)
              : undefined,
          packageTarget:
            typeof metadata?.packageTarget === "string" ? metadata.packageTarget : undefined,
          sizeBytes,
          staleLeaseCount: activity.staleLeaseCount ?? 0,
        }),
      );
    }
  }
  const processTable = readProcessTable();
  for (const legacyEntry of await readDirectories(cacheRoot)) {
    if (legacyEntry.name === "packages") continue;
    const entryRoot = path.join(cacheRoot, legacyEntry.name);
    const childDirectories = new Set((await readDirectories(entryRoot)).map((entry) => entry.name));
    if (
      !childDirectories.has("GeneratedPreviewHost") ||
      (!childDirectories.has("Build") && !childDirectories.has("sessions"))
    )
      continue;
    if (cacheEntries.length >= MAX_CACHE_ENTRIES) {
      throw cliError(
        "swift.cache.too-many-entries",
        `Swift preview cache exceeds ${MAX_CACHE_ENTRIES} entries; clean it with an exact cache path before retrying.`,
      );
    }
    const [entryStat, sizeBytes] = await Promise.all([stat(entryRoot), directorySize(entryRoot)]);
    const activity = inspectLegacyActivity(cacheRoot, entryRoot, processTable);
    cacheEntries.push(
      Object.freeze({
        active: activity.active,
        activePids: activity.activePids,
        activityKnown: activity.known,
        cacheIdentity: `legacy:${legacyEntry.name}`,
        entryRoot,
        healthy: true,
        lastUsedAt: entryStat.mtime.toISOString(),
        legacy: true,
        packageIdentity: legacyEntry.name,
        sizeBytes,
        staleLeaseCount: 0,
      }),
    );
  }
  return Object.freeze(
    cacheEntries.sort(
      (left, right) =>
        Date.parse(right.lastUsedAt) - Date.parse(left.lastUsedAt) ||
        left.cacheIdentity.localeCompare(right.cacheIdentity),
    ),
  ) as CacheEntry[];
}

function summarizeCache(cacheRoot: string, entries: CacheEntry[]) {
  const legacyEntries = entries.filter((entry) => entry.legacy);
  return Object.freeze({
    cacheRoot,
    entryCount: entries.length,
    activeCount: entries.filter((entry) => entry.active).length,
    totalBytes: entries.reduce((total, entry) => total + entry.sizeBytes, 0),
    legacyEntryCount: legacyEntries.length,
    legacyBytes: legacyEntries.reduce((total, entry) => total + entry.sizeBytes, 0),
    entries: entries.map(publicEntry),
  });
}

function selectPrunableEntries(
  entries: CacheEntry[],
  {
    includeLegacy,
    maxAgeDays,
    maxSizeBytes,
  }: { includeLegacy: boolean; maxAgeDays: number; maxSizeBytes: number },
): CacheEntry[] {
  const cutoff = Date.now() - maxAgeDays * 24 * 60 * 60 * 1000;
  const selected = new Map<string, CacheEntry>();
  for (const entry of entries) {
    if (!entry.active && (includeLegacy || !entry.legacy) && Date.parse(entry.lastUsedAt) < cutoff)
      selected.set(entry.entryRoot, entry);
  }
  let retainedBytes =
    entries.reduce((total, entry) => total + entry.sizeBytes, 0) -
    [...selected.values()].reduce((total, entry) => total + entry.sizeBytes, 0);
  const oldestInactive = entries
    .filter(
      (entry) =>
        !entry.active && (includeLegacy || !entry.legacy) && !selected.has(entry.entryRoot),
    )
    .sort((left, right) => Date.parse(left.lastUsedAt) - Date.parse(right.lastUsedAt));
  for (const entry of oldestInactive) {
    if (retainedBytes <= maxSizeBytes) break;
    selected.set(entry.entryRoot, entry);
    retainedBytes -= entry.sizeBytes;
  }
  return [...selected.values()].sort(
    (left, right) => Date.parse(left.lastUsedAt) - Date.parse(right.lastUsedAt),
  );
}

async function removeCacheEntries(cacheRoot: string, entries: CacheEntry[]): Promise<void> {
  for (const entry of entries) {
    assertContainedEntry(cacheRoot, entry);
    await rm(entry.entryRoot, { recursive: true, force: true });
  }
}

function inspectLegacyActivity(
  cacheRoot: string,
  entryRoot: string,
  processTable: ProcessRecord[] | undefined,
): CacheActivity {
  if (!processTable) return Object.freeze({ active: false, activePids: [], known: false });
  const matches = processTable.filter(
    (record) =>
      record.command.includes(entryRoot) ||
      (record.command.includes(cacheRoot) && record.command.includes("swift-package-preview.mjs")),
  );
  const activePids = [...new Set(matches.map((record) => record.pid))].sort(
    (left, right) => left - right,
  );
  return Object.freeze({ active: activePids.length > 0, activePids, known: true });
}

function readProcessTable(): ProcessRecord[] | undefined {
  if (process.platform !== "darwin") return undefined;
  try {
    const output = execFileSync("/bin/ps", ["-ax", "-o", "pid=,command="], {
      encoding: "utf8",
      stdio: ["ignore", "pipe", "ignore"],
    });
    return output.split("\n").flatMap((line) => {
      const match = /^\s*(\d+)\s+(.+)$/u.exec(line);
      return match ? [{ pid: Number(match[1]), command: match[2] }] : [];
    });
  } catch {
    return undefined;
  }
}

async function inspectActivity(entryRoot: string): Promise<CacheActivity> {
  const records: number[] = [];
  for (const entry of await readFiles(path.join(entryRoot, "sessions"))) {
    const record = await readJsonIfExists(path.join(entryRoot, "sessions", entry.name));
    const pid = record?.pid;
    if (Number.isInteger(pid) && (pid as number) > 0) records.push(pid as number);
  }
  for (const deviceEntry of await readDirectories(path.join(entryRoot, "DerivedData"))) {
    const buildLock = await readJsonIfExists(
      path.join(entryRoot, "DerivedData", deviceEntry.name, ".build.lock"),
    );
    const buildLockPid = buildLock?.pid;
    if (Number.isInteger(buildLockPid) && (buildLockPid as number) > 0)
      records.push(buildLockPid as number);
  }
  const activeRecords = records.filter(processIsAlive);
  const activePids = [...new Set(activeRecords)].sort((left, right) => left - right);
  return Object.freeze({
    active: activePids.length > 0,
    activePids,
    staleLeaseCount: records.length - activeRecords.length,
  });
}

async function directorySize(directory: string): Promise<number> {
  let total = 0;
  let entries;
  try {
    entries = await readdir(directory, { withFileTypes: true });
  } catch (error) {
    if ((error as NodeJS.ErrnoException)?.code === "ENOENT") return 0;
    throw error;
  }
  for (const entry of entries) {
    const child = path.join(directory, entry.name);
    if (entry.isDirectory()) total += await directorySize(child);
    else if (entry.isFile()) total += (await stat(child)).size;
  }
  return total;
}

async function readDirectories(directory: string) {
  return (await readEntries(directory)).filter((entry) => entry.isDirectory());
}

async function readFiles(directory: string) {
  return (await readEntries(directory)).filter(
    (entry) => entry.isFile() && entry.name.endsWith(".json"),
  );
}

async function readEntries(directory: string) {
  try {
    return await readdir(directory, { withFileTypes: true });
  } catch (error) {
    if ((error as NodeJS.ErrnoException)?.code === "ENOENT") return [];
    throw error;
  }
}

async function readJsonIfExists(filePath: string): Promise<JsonRecord | undefined> {
  try {
    const value = JSON.parse(await readFile(filePath, "utf8"));
    return value && typeof value === "object" && !Array.isArray(value)
      ? (value as JsonRecord)
      : undefined;
  } catch (error) {
    if ((error as NodeJS.ErrnoException)?.code === "ENOENT" || error instanceof SyntaxError)
      return undefined;
    throw error;
  }
}

function publicEntry(entry: CacheEntry) {
  return Object.freeze({
    active: entry.active,
    ...(entry.activityKnown === false ? { activityKnown: false } : {}),
    cacheIdentity: entry.cacheIdentity,
    healthy: entry.healthy,
    lastUsedAt: entry.lastUsedAt,
    ...(entry.legacy ? { legacy: true } : {}),
    packageIdentity: entry.packageIdentity,
    ...(entry.packageSwift ? { packageSwift: entry.packageSwift } : {}),
    ...(entry.packageTarget ? { packageTarget: entry.packageTarget } : {}),
    sizeBytes: entry.sizeBytes,
    staleLeaseCount: entry.staleLeaseCount,
  });
}

function resolveSwiftCacheRoot(value: unknown): string {
  if (value !== undefined) return optionalAbsolutePath(value, "cache_root");
  const dataRoot =
    process.env.AICODING_HOME || process.env.QODER_HOME || path.join(os.homedir(), ".qoder");
  return path.resolve(dataRoot, "canvas", "swiftui-package-preview");
}

function optionalAbsolutePath(value: unknown, name: string): string {
  if (typeof value !== "string" || !value.trim())
    throw cliError("swift.cache.argument", `${name} must be an absolute path.`);
  const resolved = path.resolve(value.trim());
  if (!path.isAbsolute(value.trim()))
    throw cliError("swift.cache.argument", `${name} must be an absolute path.`);
  return resolved;
}

function optionalString(value: unknown): string | undefined {
  return typeof value === "string" && value.trim() ? value.trim() : undefined;
}

function boundedNumber(
  value: unknown,
  name: string,
  minimum: number,
  maximum: number,
  fallback: number,
): number {
  if (value === undefined) return fallback;
  if (typeof value !== "number" || !Number.isFinite(value) || value < minimum || value > maximum) {
    throw cliError("swift.cache.argument", `${name} must be from ${minimum} through ${maximum}.`);
  }
  return value;
}

function validDate(value: unknown): string | undefined {
  return typeof value === "string" && Number.isFinite(Date.parse(value))
    ? new Date(value).toISOString()
    : undefined;
}

function assertContainedEntry(cacheRoot: string, entry: CacheEntry): void {
  const entryRoot = entry.entryRoot;
  if (entry.legacy) {
    const relative = path.relative(path.resolve(cacheRoot), path.resolve(entryRoot));
    if (
      !relative ||
      relative === "packages" ||
      relative.includes(path.sep) ||
      relative.startsWith("..") ||
      path.isAbsolute(relative)
    ) {
      throw cliError(
        "swift.cache.path",
        `Refusing to remove a path outside the Swift preview cache: ${entryRoot}`,
      );
    }
    return;
  }
  const entriesRoot = path.resolve(cacheRoot, "packages");
  const relative = path.relative(entriesRoot, path.resolve(entryRoot));
  if (!relative || relative.startsWith("..") || path.isAbsolute(relative)) {
    throw cliError(
      "swift.cache.path",
      `Refusing to remove a path outside the Swift preview cache: ${entryRoot}`,
    );
  }
}

function processIsAlive(pid: number): boolean {
  if (!Number.isInteger(pid) || pid <= 0) return false;
  try {
    process.kill(pid, 0);
    return true;
  } catch (error) {
    return (error as NodeJS.ErrnoException)?.code === "EPERM";
  }
}
