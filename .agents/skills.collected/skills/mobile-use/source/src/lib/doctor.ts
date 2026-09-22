import {
  findAndroidSdk,
  findHdc,
  findXcrun,
  hostPlatform,
  listDirectoryNames,
  runTool,
} from "./exec.ts";
import type { DoctorCheck, DoctorReport, Platform } from "./types.ts";

export async function collectDoctorReport(requested: string = "all"): Promise<DoctorReport> {
  const host = hostPlatform();
  const checks: DoctorCheck[] = [];

  if (requested === "all" || requested === "android") {
    checks.push(await checkAndroid());
  }
  if (requested === "all" || requested === "harmony") {
    checks.push(await checkHarmony());
  }
  if (requested === "all" || requested === "ios") {
    checks.push(await checkIos(host));
  }

  return Object.freeze({
    schemaVersion: 1 as const,
    host,
    platform: requested,
    checks: Object.freeze(checks) as DoctorCheck[],
    summary: Object.freeze({
      total: checks.length,
      ready: checks.filter((check) => check.status === "ready").length,
      missing: checks.filter((check) => check.status === "missing").length,
      unsupported: checks.filter((check) => check.status === "unsupported").length,
    }),
  });
}

async function checkAndroid(): Promise<DoctorCheck> {
  const sdk = await findAndroidSdk();
  if (!sdk) {
    return Object.freeze({
      platform: "android" as Platform,
      status: "missing" as const,
      tools: Object.freeze({ adb: null, emulator: null }),
      guidance:
        "Install Android SDK platform-tools, or set ANDROID_HOME / ANDROID_SDK_ROOT to an existing SDK.",
    });
  }
  const adbVersion = await runTool(sdk.adb, ["version"], { timeoutMs: 15_000 })
    .then(({ stdout }) => stdout.split("\n")[0]?.trim())
    .catch(() => null);
  const avdHome = process.env.ANDROID_AVD_HOME;
  const avds = avdHome ? await listDirectoryNames(avdHome) : [];
  return Object.freeze({
    platform: "android" as Platform,
    status: "ready" as const,
    tools: Object.freeze({
      adb: Object.freeze({ path: sdk.adb, version: adbVersion }),
      emulator: sdk.emulator ? Object.freeze({ path: sdk.emulator }) : null,
      sdkRoot: sdk.root,
    }),
    avds: Object.freeze(avds) as string[],
    guidance: sdk.emulator
      ? null
      : "emulator component not found; install it via sdkmanager to boot virtual devices.",
  });
}

async function checkHarmony(): Promise<DoctorCheck> {
  const hdc = await findHdc();
  if (!hdc) {
    return Object.freeze({
      platform: "harmony" as Platform,
      status: "missing" as const,
      tools: Object.freeze({ hdc: null }),
      guidance:
        "Install DevEco Studio and set DEVECO_SDK_HOME, or add OpenHarmony toolchains (hdc) to PATH.",
    });
  }
  const version = await runTool(hdc, ["-v"], { timeoutMs: 15_000 })
    .then(({ stdout }) => stdout.trim())
    .catch(() => null);
  return Object.freeze({
    platform: "harmony" as Platform,
    status: "ready" as const,
    tools: Object.freeze({ hdc: Object.freeze({ path: hdc, version }) }),
    guidance: null,
  });
}

async function checkIos(host: NodeJS.Platform): Promise<DoctorCheck> {
  if (host !== "darwin") {
    return Object.freeze({
      platform: "ios" as Platform,
      status: "unsupported" as const,
      tools: Object.freeze({ xcrun: null }),
      guidance: "iOS Simulator control requires macOS with Xcode.",
    });
  }
  const xcrun = await findXcrun();
  if (!xcrun) {
    return Object.freeze({
      platform: "ios" as Platform,
      status: "missing" as const,
      tools: Object.freeze({ xcrun: null }),
      guidance: "Install Xcode and run `xcode-select --install` for command-line tools.",
    });
  }
  const version = await runTool(xcrun, ["simctl", "help"], { timeoutMs: 15_000 })
    .then(() => "available")
    .catch(() => null);
  return Object.freeze({
    platform: "ios" as Platform,
    status: (version ? "ready" : "missing") as "ready" | "missing",
    tools: Object.freeze({ xcrun: Object.freeze({ path: xcrun, version }) }),
    guidance: null,
  });
}
