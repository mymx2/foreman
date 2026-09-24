import { describe, expect, it } from "vite-plus/test";
import { parseArguments } from "../src/cli/mobile-use.ts";
import {
  operationAndInput,
  sessionSelection,
  targetAndInput,
  targetSelection,
} from "../src/lib/phone-arguments.ts";

describe("parseArguments", () => {
  it("parses a simple command with no flags", () => {
    const parsed = parseArguments(["inventory"]);
    expect(parsed.command).toBe("inventory");
    expect(parsed.params).toEqual({});
  });

  it("normalizes kebab-case command to underscore", () => {
    const parsed = parseArguments(["list-targets"]);
    expect(parsed.command).toBe("list_targets");
  });

  it("parses string flag values", () => {
    const parsed = parseArguments([
      "start-session",
      "--surface-id",
      "adb-android",
      "--target-id",
      "emulator-5554",
    ]);
    expect(parsed.params.surface_id).toBe("adb-android");
    expect(parsed.params.target_id).toBe("emulator-5554");
  });

  it("parses --flag=value form", () => {
    const parsed = parseArguments(["start-session", "--surface-id=adb-android"]);
    expect(parsed.params.surface_id).toBe("adb-android");
  });

  it("parses JSON flags into objects", () => {
    const parsed = parseArguments(["tap", "--selector-json", '{"identifier":"login"}']);
    expect(parsed.params.selector).toEqual({ identifier: "login" });
  });

  it("parses params-json by merging the object", () => {
    const parsed = parseArguments([
      "assert",
      "--params-json",
      '{"selector":{"label":"x"},"state":"absent"}',
    ]);
    expect(parsed.params.selector).toEqual({ label: "x" });
    expect(parsed.params.state).toBe("absent");
  });

  it("parses number flags as numbers", () => {
    const parsed = parseArguments(["long-press", "--duration-ms", "1500"]);
    expect(parsed.params.duration_ms).toBe(1500);
  });

  it("parses a bare boolean flag as true", () => {
    const parsed = parseArguments(["manage-app", "--action", "uninstall", "--confirm"]);
    expect(parsed.params.confirm).toBe(true);
  });

  it("parses a boolean flag with explicit =true value", () => {
    const parsed = parseArguments(["manage-app", "--action", "uninstall", "--confirm=true"]);
    expect(parsed.params.confirm).toBe(true);
  });

  it("rejects an unknown command with phone.command.unknown", () => {
    try {
      parseArguments(["bogus-command"]);
      expect.unreachable();
    } catch (error) {
      expect((error as { code?: string }).code).toBe("phone.command.unknown");
    }
  });

  it("rejects invalid JSON in a JSON flag", () => {
    try {
      parseArguments(["tap", "--selector-json", "{bad json"]);
      expect.unreachable();
    } catch (error) {
      expect((error as { code?: string }).code).toBe("phone.cli.argument");
    }
  });
});

describe("sessionSelection", () => {
  it("requires surface_id and session_id", () => {
    expect(sessionSelection({ surface_id: "adb-android", session_id: "emulator-5554" })).toEqual({
      surfaceId: "adb-android",
      sessionId: "emulator-5554",
    });
  });

  it("throws when a required value is missing", () => {
    expect(() => sessionSelection({ surface_id: "adb-android" })).toThrow();
  });
});

describe("targetSelection", () => {
  it("maps surface_id and target_id to camelCase", () => {
    expect(targetSelection({ surface_id: "adb-android", target_id: "emulator-5554" })).toEqual({
      surfaceId: "adb-android",
      targetId: "emulator-5554",
    });
  });
});

describe("targetAndInput", () => {
  it("builds observe input with interactive default mode", () => {
    const result = targetAndInput("observe", { surface_id: "s", session_id: "x" });
    expect(result.input).toEqual({ mode: "interactive" });
  });

  it("builds observe full mode", () => {
    const result = targetAndInput("observe", { surface_id: "s", session_id: "x", mode: "full" });
    expect(result.input).toEqual({ mode: "full" });
  });

  it("builds a tap action from selector", () => {
    const result = targetAndInput("tap", {
      surface_id: "s",
      session_id: "x",
      selector: { identifier: "login" },
    });
    expect(result.input.action).toMatchObject({ kind: "tap", selector: { identifier: "login" } });
  });

  it("builds long-press with bounded duration", () => {
    const result = targetAndInput("long_press", {
      surface_id: "s",
      session_id: "x",
      selector: { label: "ok" },
      duration_ms: 800,
    });
    expect(result.input.action).toMatchObject({ kind: "long-press", durationMs: 800 });
  });

  it("rejects act without a positive ui_revision", () => {
    expect(() => targetAndInput("act", { surface_id: "s", session_id: "x", action: {} })).toThrow(
      /ui_revision/,
    );
  });
});

describe("operationAndInput", () => {
  it("resolves capture_screenshot to its operation and capability", () => {
    const result = operationAndInput("capture_screenshot", { surface_id: "s", session_id: "x" });
    expect(result.operation).toBe("device.capture.screenshot");
    expect(result.capability).toBe("device.frame.screenshot");
  });

  it("resolves manage_app uninstall requiring confirm=true", () => {
    const result = operationAndInput("manage_app", {
      surface_id: "s",
      session_id: "x",
      action: "uninstall",
      bundle_id: "com.x",
      confirm: true,
    });
    expect(result.operation).toBe("device.app.uninstall");
    expect(result.input).toMatchObject({ bundleId: "com.x", confirm: true });
  });

  it("rejects manage_app uninstall without confirm", () => {
    expect(() =>
      operationAndInput("manage_app", {
        surface_id: "s",
        session_id: "x",
        action: "uninstall",
        bundle_id: "com.x",
      }),
    ).toThrow(/confirm/);
  });

  it("resolves record_screen actions to operations", () => {
    const start = operationAndInput("record_screen", {
      surface_id: "s",
      session_id: "x",
      action: "start",
    });
    expect(start.operation).toBe("device.recording.start");
    expect(start.capability).toBe("device.recording.native");
  });

  it("rejects an invalid record_screen action", () => {
    expect(() =>
      operationAndInput("record_screen", { surface_id: "s", session_id: "x", action: "pause" }),
    ).toThrow();
  });

  it("resolves run_native_test selector into input", () => {
    const result = operationAndInput("run_native_test", {
      surface_id: "s",
      session_id: "x",
      selector: "com.T#m",
    });
    expect(result.operation).toBe("device.test.run");
    expect(result.input).toMatchObject({ selector: "com.T#m" });
  });
});
