import type { NativeTestOutcome } from "./types.ts";

// Classify raw `am instrument` output into a semantic outcome. Pure function so
// it can be unit-tested without a device.
//
// Honesty contract:
// - zero tests run, or the runner crashed while loading the class before any
//   assertion, is `runner_mismatch` — never a pass, and not an assertion failure;
// - `assertion_failed` only when the runner actually reached a behavior assertion;
// - `passed` only when at least one test ran and passed.
export function classifyInstrumentationOutcome(output: string): NativeTestOutcome {
  const zeroTests = /OK\s+\(0\s+tests?\)/i.test(output) || /numtests=0/.test(output);
  const classLoadFailed = /ClassNotFoundException|No tests found|Test run failed to complete/i.test(
    output,
  );
  if (zeroTests || classLoadFailed) {
    return "runner_mismatch";
  }
  if (/FAILURES!!!/i.test(output) || /AssertionError|AssertionFailedError/i.test(output)) {
    return "assertion_failed";
  }
  if (/OK\s+\([1-9]\d*\s+tests?\)/i.test(output)) {
    return "passed";
  }
  if (/Unable to find instrumentation|does not exist|No instrumentation/i.test(output)) {
    return "runner_mismatch";
  }
  if (/Process crashed|shortMsg=|INSTRUMENTATION_RESULT:.*shortMsg/i.test(output)) {
    return "crashed_before_assertion";
  }
  if (/INSTRUMENTATION_CODE:\s*-1/.test(output) && /OK\s+\([1-9]\d*\s+test/i.test(output)) {
    return "passed";
  }
  return "runner_mismatch";
}
