#!/usr/bin/env node

import { realpathSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { PHONE_COMMANDS, executePhoneCommand } from "../lib/phone-command.ts";
import { SWIFT_CACHE_COMMANDS, executeSwiftCacheCommand } from "../lib/swift-cache.ts";
import { collectDoctorReport } from "../lib/doctor.ts";
import { cliError, isRecord } from "../lib/types.ts";
import type { CliError, JsonRecord } from "../lib/types.ts";

const SCHEMA_VERSION = 1;
// Injected at build time via `vp pack --env.CLI_VERSION`; falls back for local dev.
const CLI_VERSION: string = process.env.CLI_VERSION ?? "0.7.5";
const JSON_FLAGS = new Map<string, string | undefined>([
  ["action_json", "action"],
  ["condition_json", "condition"],
  ["params_json", undefined],
  ["plan_json", "plan"],
  ["selector_json", "selector"],
]);
const NUMBER_FLAGS = new Set([
  "duration_ms",
  "limit",
  "max_age_days",
  "max_size_mb",
  "poll_interval_ms",
  "seconds",
  "timeout_ms",
  "ui_revision",
]);
const BOOLEAN_FLAGS = new Set(["apply", "confirm", "include_legacy"]);
const LOCAL_COMMANDS = ["doctor"];

export interface RunCliOptions {
  stdout?: NodeJS.WritableStream;
  stderr?: NodeJS.WritableStream;
  platform?: NodeJS.Platform;
  dependencies?: Record<string, unknown>;
}

export interface ParsedArguments {
  command?: string;
  help?: boolean;
  version?: boolean;
  params: Record<string, unknown>;
  pretty: boolean;
}

export async function runCli(argv: string[], options: RunCliOptions = {}): Promise<number> {
  const stdout = options.stdout ?? process.stdout;
  const stderr = options.stderr ?? process.stderr;
  let command: string | undefined;
  try {
    const parsed = parseArguments(argv);
    command = parsed.command;
    if (parsed.help) {
      stdout.write(`${helpText()}\n`);
      return 0;
    }
    if (parsed.version) {
      stdout.write(`${CLI_VERSION}\n`);
      return 0;
    }
    let data: unknown;
    if (command === "doctor") {
      const platform = typeof parsed.params.platform === "string" ? parsed.params.platform : "all";
      data = await collectDoctorReport(platform);
    } else if (command && SWIFT_CACHE_COMMANDS.includes(command)) {
      if ((options.platform ?? process.platform) !== "darwin") {
        throw cliError(
          "swift.cache.host.unsupported",
          "Swift preview cache commands are supported only on macOS hosts that can run iOS previews.",
        );
      }
      data = await executeSwiftCacheCommand(command, parsed.params);
    } else if (command) {
      data = await executePhoneCommand(command, parsed.params, options.dependencies);
    }
    const envelope = { schemaVersion: SCHEMA_VERSION, ok: true, command, data };
    stdout.write(`${JSON.stringify(envelope, null, parsed.pretty ? 2 : 0)}\n`);
    return 0;
  } catch (error) {
    const normalized = normalizeError(error);
    const envelope = {
      schemaVersion: SCHEMA_VERSION,
      ok: false,
      ...(command ? { command } : {}),
      error: normalized,
    };
    stderr.write(`${JSON.stringify(envelope)}\n`);
    return exitCodeFor(normalized.code);
  }
}

export function parseArguments(argv: string[]): ParsedArguments {
  const tokens = [...argv];
  if (tokens.length === 0 || tokens[0] === "--help" || tokens[0] === "-h" || tokens[0] === "help") {
    return { help: true, params: {}, pretty: true };
  }
  if (tokens[0] === "--version" || tokens[0] === "-v") {
    return { version: true, params: {}, pretty: false };
  }

  const rawCommand = tokens.shift() as string;
  const command = rawCommand.replaceAll("-", "_");
  const knownCommands = [...PHONE_COMMANDS, ...SWIFT_CACHE_COMMANDS, ...LOCAL_COMMANDS];
  if (!knownCommands.includes(command)) {
    throw cliError(
      "phone.command.unknown",
      `Unknown command: ${rawCommand}. Run mobile-use --help.`,
    );
  }

  let params: Record<string, unknown> = {};
  let pretty = false;
  for (let index = 0; index < tokens.length; index += 1) {
    const token = tokens[index];
    if (token === "--json") continue;
    if (token === "--pretty") {
      pretty = true;
      continue;
    }
    if (!token.startsWith("--"))
      throw cliError("phone.cli.argument", `Unexpected argument: ${token}`);

    const separator = token.indexOf("=");
    const rawName = separator === -1 ? token.slice(2) : token.slice(2, separator);
    const name = rawName.replaceAll("-", "_");
    let value: string | undefined = separator === -1 ? undefined : token.slice(separator + 1);
    if (BOOLEAN_FLAGS.has(name) && value === undefined) {
      params[name] = true;
      continue;
    }
    if (value === undefined) {
      index += 1;
      value = tokens[index];
    }
    if (value === undefined || value.startsWith("--")) {
      throw cliError("phone.cli.argument", `--${rawName} requires a value.`);
    }

    if (JSON_FLAGS.has(name)) {
      const parsed = parseJson(value, rawName);
      const target = JSON_FLAGS.get(name);
      if (target === undefined) {
        if (!isRecord(parsed))
          throw cliError("phone.cli.argument", `--${rawName} must contain a JSON object.`);
        params = { ...params, ...parsed };
      } else {
        params[target] = parsed;
      }
      continue;
    }
    if (NUMBER_FLAGS.has(name)) {
      const number = Number(value);
      if (!Number.isFinite(number))
        throw cliError("phone.cli.argument", `--${rawName} must be a number.`);
      params[name] = number;
      continue;
    }
    if (BOOLEAN_FLAGS.has(name)) {
      if (value !== "true" && value !== "false")
        throw cliError("phone.cli.argument", `--${rawName} must be true or false.`);
      params[name] = value === "true";
      continue;
    }
    params[name] = value;
  }
  return { command, params, pretty };
}

function parseJson(value: string, name: string): unknown {
  if (Buffer.byteLength(value) > 1024 * 1024)
    throw cliError("phone.cli.argument", `--${name} exceeds the 1 MiB limit.`);
  try {
    return JSON.parse(value);
  } catch (error) {
    throw cliError(
      "phone.cli.argument",
      `--${name} is not valid JSON: ${error instanceof Error ? error.message : String(error)}`,
    );
  }
}

interface NormalizedError {
  code: string;
  message: string;
  retry?: string;
  details?: JsonRecord;
}

function normalizeError(error: unknown): NormalizedError {
  const message = error instanceof Error ? error.message : String(error);
  const explicitCode =
    typeof (error as CliError | undefined)?.code === "string"
      ? (error as CliError).code
      : undefined;
  let code =
    explicitCode ?? (error instanceof TypeError ? "phone.cli.argument" : "phone.command.failed");
  if (
    !explicitCode &&
    !(error instanceof TypeError) &&
    /stale|not found|does not belong|no live session/iu.test(message)
  )
    code = "phone.session.unavailable";
  if (!explicitCode && !(error instanceof TypeError) && /revision|assert/iu.test(message))
    code = "phone.revision.failed";
  return {
    code,
    message,
    ...(code.includes("revision") ? { retry: "observe" } : {}),
    ...(isRecord((error as CliError | undefined)?.details)
      ? { details: (error as CliError).details }
      : {}),
  };
}

function exitCodeFor(code: string): number {
  if (
    code === "swift.cache.argument" ||
    code === "swift.cache.command.unknown" ||
    code === "swift.cache.confirmation.required"
  )
    return 2;
  if (code === "swift.cache.active") return 3;
  if (
    code === "phone.cli.argument" ||
    code === "phone.command.unknown" ||
    code === "phone.plan.invalid" ||
    code === "phone.plan.step-invalid"
  )
    return 2;
  if (code.includes("surface") || code.includes("session") || code.includes("target")) return 3;
  if (code.includes("revision") || code.includes("assert") || code.includes("selector")) return 4;
  if (code.includes("capability")) return 5;
  if (code.includes("broker")) return 6;
  return 1;
}

function helpText(): string {
  return [
    `Mobile Use CLI ${CLI_VERSION}`,
    "",
    "Usage:",
    "  mobile-use <command> [options] [--json]",
    "",
    "Environment:",
    "  doctor [--platform <android|harmony|ios|all>]",
    "",
    "Core commands:",
    "  inventory, list_targets, start_session, stop_session, list_sessions",
    "  observe, tap, long_press, act, wait, assert, run_plan",
    "",
    "Operational commands (CLI only):",
    "  restart_target, manage_app, read_logs, run_native_test, capture_screenshot, record_screen",
    "",
    "Local Swift build cache (macOS only):",
    "  swift_cache_status",
    "  swift_cache_prune [--max-age-days <days>] [--max-size-mb <MiB>] [--include-legacy] [--apply]",
    "  swift_cache_clean (--package-swift <absolute-path> | --cache-identity <id>) --confirm",
    "",
    "Common options:",
    "  --surface-id <id>        Surface returned by list_targets/list_sessions",
    "  --target-id <id>         Target returned by list_targets",
    "  --session-id <id>        Session returned by start_session/list_sessions",
    "  --platform <name>        doctor platform filter",
    "  --params-json <object>   Merge a complete JSON argument object",
    "  --action-json <object>   act action payload",
    "  --plan-json <object>     versioned run_plan workflow",
    "  --duration-ms <number>   long_press duration in milliseconds",
    "  --condition-json <object> wait condition payload",
    "  --selector-json <object> tap/long_press/assert selector payload",
    "  --selector <id>          Exact native test selector for run_native_test",
    "  --test-target <name>     Optional platform test target override",
    "  --test-module <name>     Optional HarmonyOS test module override",
    "  --test-bundle-id <id>    Optional HarmonyOS test bundle override",
    "  --runner <name>          Optional platform runner override",
    "  --pretty                 Pretty-print the JSON envelope",
    "",
    "Drives devices through the host toolchain (adb, hdc, simctl); no vendor plugin or broker required.",
  ].join("\n");
}

const isEntrypoint =
  process.argv[1] && realpathSync(process.argv[1]) === realpathSync(fileURLToPath(import.meta.url));
if (isEntrypoint) {
  const exitCode = await runCli(process.argv.slice(2));
  process.exitCode = exitCode;
}
