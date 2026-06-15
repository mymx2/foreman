import { execSync } from "node:child_process";
import { cpSync, existsSync, mkdirSync, readFileSync, readdirSync, statSync } from "node:fs";
import { join, resolve } from "node:path";

const AGENT_DIR = ".qoder";

const ROOT = resolve(import.meta.dirname, ".");
const WORKTREE_DIR = join(ROOT, ".worktrees", "agent-skills");
const REPO_URL = "https://github.com/addyosmani/agent-skills";

const SYNC_MAP = [
  {
    from: join(WORKTREE_DIR, ".claude", "commands"),
    to: join(ROOT, AGENT_DIR, "commands"),
  },
  {
    from: join(WORKTREE_DIR, "agents"),
    to: join(ROOT, AGENT_DIR, "agents"),
  },
  {
    from: join(WORKTREE_DIR, "references"),
    to: join(ROOT, "references"),
  },
];

// TODO: https://github.com/addyosmani/agent-skills/pull/260
const RENAME_MAP = new Map<string, string>([
  [join(WORKTREE_DIR, "agents", "README.md"), join(ROOT, "docs", "agents.md")],
]);

// ── 1. Clone repo into .worktrees/agent-skills ──────────────────────
function cloneRepo(): void {
  if (existsSync(WORKTREE_DIR)) {
    console.log(`[init] "${WORKTREE_DIR}" already exists, skipping clone.`);
    return;
  }

  const parentDir = join(WORKTREE_DIR, "..");
  if (!existsSync(parentDir)) {
    mkdirSync(parentDir, { recursive: true });
  }

  console.log(`[init] Cloning ${REPO_URL} → ${WORKTREE_DIR}`);
  execSync(`git clone ${REPO_URL} "${WORKTREE_DIR}"`, { stdio: "inherit" });
}

// ── 2. Sync directories ─────────────────────────────────────────────
function syncDir(from: string, to: string): void {
  if (!existsSync(from)) {
    console.warn(`[init] Source "${from}" does not exist, skipping.`);
    return;
  }

  if (!existsSync(to)) {
    mkdirSync(to, { recursive: true });
  }

  // Copy files from source to destination
  for (const entry of readdirSync(from)) {
    const srcFile = join(from, entry);
    const renamedDest = RENAME_MAP.get(srcFile);
    const destFile = renamedDest ?? join(to, entry);
    const stat = statSync(srcFile);

    if (renamedDest) {
      const destDir = join(destFile, "..");
      if (!existsSync(destDir)) {
        mkdirSync(destDir, { recursive: true });
      }
    }

    if (stat.isDirectory()) {
      cpSync(srcFile, destFile, { recursive: true });
    } else {
      const shouldCopy = renamedDest
        ? !existsSync(destFile) || !readFileSync(srcFile).equals(readFileSync(destFile))
        : !existsSync(destFile) || statSync(srcFile).mtimeMs > statSync(destFile).mtimeMs;
      if (shouldCopy) {
        cpSync(srcFile, destFile);
        console.log(
          renamedDest ? `[init] Renamed: ${entry} → ${destFile}` : `[init] Synced: ${entry}`,
        );
      }
    }
  }
}

// ── Main ────────────────────────────────────────────────────────────
function main(): void {
  console.log("[init] Starting initialization...\n");

  cloneRepo();

  console.log();

  for (const { from, to } of SYNC_MAP) {
    console.log(`[init] Syncing: ${from} → ${to}`);
    syncDir(from, to);
    console.log();
  }

  console.log("[init] Done.");

  // Run formatter if available
  try {
    const checkCmd = process.platform === "win32" ? "where vp 2>nul" : "which vp 2>/dev/null";
    execSync(checkCmd, { stdio: "ignore" });
    console.log("\n[init] Running vp run fmt...");
    execSync("vp run fmt", { stdio: "inherit" });
  } catch {
    console.log("\n[init] vp not found, skipping format.");
  }
}

main();
