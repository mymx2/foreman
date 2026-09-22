import { execFile } from "node:child_process";
import { access, readdir } from "node:fs/promises";
import { constants } from "node:fs";
import { homedir, platform, tmpdir } from "node:os";
import path from "node:path";
import { cliError } from "./types.ts";

const isWindows = platform() === "win32";
const exeSuffix = isWindows ? ".exe" : "";

export interface ToolResult {
  stdout: string;
  stderr: string;
}

export interface ToolRawResult {
  stdout: Buffer;
  stderr: Buffer;
}

export interface ToolOptions {
  timeoutMs?: number;
  maxBuffer?: number;
  errorCode?: string;
  input?: string;
}

export interface AndroidSdk {
  root: string;
  adb: string;
  emulator?: string;
}

export function hostPlatform(): NodeJS.Platform {
  return platform();
}

export async function runTool(
  file: string,
  args: string[] = [],
  options: ToolOptions = {},
): Promise<ToolResult> {
  const timeoutMs = options.timeoutMs ?? 60_000;
  return new Promise((resolvePromise, rejectPromise) => {
    execFile(
      file,
      args,
      { timeout: timeoutMs, maxBuffer: options.maxBuffer ?? 16 * 1024 * 1024, windowsHide: true },
      (error, stdout, stderr) => {
        if (error) {
          const toolError = cliError(
            options.errorCode ?? "device.tool.failed",
            `${path.basename(file)} ${args.join(" ")} failed: ${stderr?.trim() || error.message}`,
          );
          rejectPromise(toolError);
          return;
        }
        resolvePromise({ stdout, stderr });
      },
    );
  });
}

export async function runToolRaw(
  file: string,
  args: string[] = [],
  options: ToolOptions = {},
): Promise<ToolRawResult> {
  const timeoutMs = options.timeoutMs ?? 60_000;
  return new Promise((resolvePromise, rejectPromise) => {
    execFile(
      file,
      args,
      {
        timeout: timeoutMs,
        maxBuffer: options.maxBuffer ?? 64 * 1024 * 1024,
        windowsHide: true,
        encoding: "buffer",
      },
      (error, stdout, stderr) => {
        if (error) {
          const toolError = cliError(
            options.errorCode ?? "device.tool.failed",
            `${path.basename(file)} failed: ${stderr?.toString()?.trim() || error.message}`,
          );
          rejectPromise(toolError);
          return;
        }
        resolvePromise({ stdout, stderr });
      },
    );
  });
}

export interface BackgroundPidResult {
  pid?: number;
  stdout: string;
  stderr: string;
}

// Run a device shell command detached via nohup so it survives after adb
// returns. `nohup cmd & echo $!` prints the background pid, captured for
// precise later cleanup.
export async function runToolBackgroundPid(
  file: string,
  args: string[],
  options: ToolOptions = {},
): Promise<BackgroundPidResult> {
  return new Promise((resolvePromise, rejectPromise) => {
    execFile(
      file,
      args,
      { timeout: options.timeoutMs ?? 15_000, maxBuffer: 4 * 1024 * 1024, windowsHide: true },
      (error, stdout, stderr) => {
        if (error) {
          const toolError = cliError(
            options.errorCode ?? "device.tool.failed",
            `${path.basename(file)} failed: ${stderr?.toString()?.trim() || error.message}`,
          );
          rejectPromise(toolError);
          return;
        }
        const pid = Number.parseInt(String(stdout).trim().split(/\s+/).pop() ?? "", 10);
        resolvePromise({ pid: Number.isInteger(pid) ? pid : undefined, stdout, stderr });
      },
    );
  });
}

async function fileExists(candidate: string): Promise<boolean> {
  try {
    await access(candidate, constants.X_OK);
    return true;
  } catch {
    return false;
  }
}

async function firstExisting(candidates: Array<string | undefined>): Promise<string | undefined> {
  for (const candidate of candidates) {
    if (candidate && (await fileExists(candidate))) return candidate;
  }
  return undefined;
}

function sdkRoots(env: NodeJS.ProcessEnv = process.env): string[] {
  const roots: string[] = [];
  if (env.ANDROID_HOME?.trim()) roots.push(env.ANDROID_HOME.trim());
  if (env.ANDROID_SDK_ROOT?.trim()) roots.push(env.ANDROID_SDK_ROOT.trim());
  const home = homedir();
  if (isWindows) {
    roots.push(path.join(home, "AppData", "Local", "Android", "Sdk"));
    roots.push(path.join("C:\\", "Android", "Sdk"));
    roots.push(path.join("D:\\", "Android", "Sdk"));
  } else if (platform() === "darwin") {
    roots.push(path.join(home, "Library", "Android", "sdk"));
  } else {
    roots.push(path.join(home, "Android", "Sdk"));
  }
  return [...new Set(roots)];
}

export async function findAndroidSdk(
  env: NodeJS.ProcessEnv = process.env,
): Promise<AndroidSdk | undefined> {
  for (const root of sdkRoots(env)) {
    const adb = path.join(root, "platform-tools", `adb${exeSuffix}`);
    if (await fileExists(adb)) {
      const emulatorPath = path.join(root, "emulator", `emulator${exeSuffix}`);
      return Object.freeze({
        root,
        adb,
        emulator: (await fileExists(emulatorPath)) ? emulatorPath : undefined,
      });
    }
  }
  return undefined;
}

export async function findHdc(env: NodeJS.ProcessEnv = process.env): Promise<string | undefined> {
  const home = homedir();
  const candidates: string[] = [];
  if (env.DEVECO_SDK_HOME?.trim()) {
    candidates.push(
      path.join(
        env.DEVECO_SDK_HOME.trim(),
        "sdk",
        "default",
        "openharmony",
        "toolchains",
        `hdc${exeSuffix}`,
      ),
    );
    candidates.push(path.join(env.DEVECO_SDK_HOME.trim(), "toolchains", `hdc${exeSuffix}`));
  }
  if (env.HARMONYOS_SDK_HOME?.trim()) {
    candidates.push(path.join(env.HARMONYOS_SDK_HOME.trim(), "toolchains", `hdc${exeSuffix}`));
  }
  candidates.push(
    path.join(home, "AppData", "Local", "OpenHarmony", "Sdk", "toolchains", `hdc${exeSuffix}`),
  );
  return firstExisting(candidates);
}

export async function findXcrun(): Promise<string | undefined> {
  if (platform() !== "darwin") return undefined;
  return firstExisting(["/usr/bin/xcrun"]);
}

export function defaultArtifactDirectory(env: NodeJS.ProcessEnv = process.env): string {
  return path.join(env.MOBILE_USE_ARTIFACT_DIR?.trim() || tmpdir(), "mobile-use-artifacts");
}

export async function listDirectoryNames(directory: string): Promise<string[]> {
  try {
    const entries = await readdir(directory, { withFileTypes: true });
    return entries.filter((entry) => entry.isDirectory()).map((entry) => entry.name);
  } catch {
    return [];
  }
}
