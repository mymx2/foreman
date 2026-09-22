#!/usr/bin/env node
// Build the CLI bundles, injecting the package version as a compile-time
// constant so the output is self-contained (no runtime package.json read).
import { readFileSync } from "node:fs";
import { spawnSync } from "node:child_process";

const { version } = JSON.parse(readFileSync(new URL("./package.json", import.meta.url), "utf8"));

const result = spawnSync("vp", ["pack", `--env.CLI_VERSION=${version}`], {
  stdio: "inherit",
  shell: true,
});
process.exit(result.status ?? 1);
