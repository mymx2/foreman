import { describe, expect, it } from "vite-plus/test";
import { invokePhoneUse, shellQuoteInputText } from "../src/lib/android-backend.ts";

// Shell-injection guard: user-controlled values must be rejected before they
// reach an `adb shell` string. The validation runs before any device call, so
// malicious input throws a cli.argument error without needing a live device.
describe("act input validation (shell-injection guard)", () => {
  const base = { surfaceId: "adb-android", sessionId: "emulator-5554" };

  it("rejects a swipe with non-integer coordinates", async () => {
    await expect(
      invokePhoneUse(base.surfaceId, base.sessionId, "act", {
        action: { kind: "swipe", from: { x: "0;id;#", y: 0 }, to: { x: 1, y: 1 } },
      }),
    ).rejects.toMatchObject({ code: "phone.cli.argument" });
  });

  it("rejects a key that is not a KEYCODE or number", async () => {
    await expect(
      invokePhoneUse(base.surfaceId, base.sessionId, "act", {
        action: { kind: "key", key: "1;id" },
      }),
    ).rejects.toMatchObject({ code: "phone.cli.argument" });
  });

  it("rejects a swipe with a non-integer duration", async () => {
    await expect(
      invokePhoneUse(base.surfaceId, base.sessionId, "act", {
        action: { kind: "swipe", from: { x: 0, y: 0 }, to: { x: 1, y: 1 }, durationMs: "300;id" },
      }),
    ).rejects.toMatchObject({ code: "phone.cli.argument" });
  });
});

describe("shellQuoteInputText", () => {
  it("wraps plain text in single quotes and escapes spaces as %s", () => {
    expect(shellQuoteInputText("hello world")).toBe("'hello%sworld'");
  });

  it("escapes an embedded single quote with the POSIX close/reopen idiom", () => {
    // A literal `'` must not terminate the surrounding single-quoted string;
    // it is replaced by the sequence: end-quote, escaped-quote, start-quote.
    expect(shellQuoteInputText("it's")).toBe(`'it'\\''s'`);
  });

  it("keeps a quote-only payload from breaking out", () => {
    const out = shellQuoteInputText("'; rm -rf /; '");
    // Spaces become %s; every payload single-quote becomes the close/escape/reopen sequence.
    expect(out).toBe(`''\\'';%srm%s-rf%s/;%s'\\'''`);
  });
});
