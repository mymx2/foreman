import { execSync } from "node:child_process";
import { cpSync, existsSync, mkdirSync, readdirSync, statSync } from "node:fs";
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
];

const IGNORE_FILES = new Set(["README.md"]);

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

// ── 2. Sync directories (ignore README.md) ──────────────────────────
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
    if (IGNORE_FILES.has(entry)) {
      console.log(`[init] Ignoring: ${entry}`);
      continue;
    }

    const srcFile = join(from, entry);
    const destFile = join(to, entry);
    const stat = statSync(srcFile);

    if (stat.isDirectory()) {
      cpSync(srcFile, destFile, { recursive: true });
    } else {
      // Only copy if source is newer or destination doesn't exist
      if (!existsSync(destFile) || statSync(srcFile).mtimeMs > statSync(destFile).mtimeMs) {
        cpSync(srcFile, destFile);
        console.log(`[init] Synced: ${entry}`);
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
}

main();
