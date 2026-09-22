import { describe, expect, it } from "vite-plus/test";
import { classifyInstrumentationOutcome } from "../src/lib/instrumentation.ts";

describe("classifyInstrumentationOutcome", () => {
  it("marks a real pass as passed", () => {
    const output = `INSTRUMENTATION_STATUS: numtests=3
INSTRUMENTATION_STATUS_CODE: 0
Time: 4.952
OK (3 tests)
INSTRUMENTATION_CODE: -1`;
    expect(classifyInstrumentationOutcome(output)).toBe("passed");
  });

  it("marks a single passing test as passed", () => {
    expect(classifyInstrumentationOutcome("OK (1 test)\nINSTRUMENTATION_CODE: -1")).toBe("passed");
  });

  it("marks zero tests as runner_mismatch, never a pass", () => {
    expect(classifyInstrumentationOutcome("OK (0 tests)\nINSTRUMENTATION_CODE: -1")).toBe(
      "runner_mismatch",
    );
    expect(classifyInstrumentationOutcome("INSTRUMENTATION_STATUS: numtests=0")).toBe(
      "runner_mismatch",
    );
  });

  it("marks class-load failure as runner_mismatch, not assertion_failed", () => {
    const output = `Caused by: java.lang.ClassNotFoundException: com.ghost.Test
FAILURES!!!
Tests run: 1,  Failures: 1
INSTRUMENTATION_CODE: -1`;
    expect(classifyInstrumentationOutcome(output)).toBe("runner_mismatch");
  });

  it("marks a reached-but-failed assertion as assertion_failed", () => {
    const output = `java.lang.AssertionError: expected:<1> but was:<0>
at com.example.HomeScreenTest.counter_increments(HomeScreenTest.kt:20)
FAILURES!!!
Tests run: 1,  Failures: 1`;
    expect(classifyInstrumentationOutcome(output)).toBe("assertion_failed");
  });

  it("marks a crash before assertion as crashed_before_assertion", () => {
    const output = "INSTRUMENTATION_RESULT: shortMsg=Process crashed.\nINSTRUMENTATION_CODE: 0";
    expect(classifyInstrumentationOutcome(output)).toBe("crashed_before_assertion");
  });

  it("marks a missing instrumentation as runner_mismatch", () => {
    const output =
      "Unable to find instrumentation info for: ComponentInfo{com.x/androidx.test.runner.AndroidJUnitRunner}";
    expect(classifyInstrumentationOutcome(output)).toBe("runner_mismatch");
  });

  it("defaults unknown output to runner_mismatch", () => {
    expect(classifyInstrumentationOutcome("some unrecognized output")).toBe("runner_mismatch");
  });
});
