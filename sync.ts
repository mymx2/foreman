import { execSync } from "node:child_process";
import { cpSync, existsSync, mkdirSync, readdirSync, statSync } from "node:fs";
import { join, resolve } from "node:path";

const AGENT_DIR = ".qoder";

const ROOT = resolve(import.meta.dirname, ".");
const WORKTREE_DIR = join(ROOT, ".worktrees", "agent-skills");
const REPO_URL = "https://github.com/addyosmani/agent-skills";

const SYNC_MAP: { from: string; to: string; filter?: string[] }[] = [
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
  {
    from: join(WORKTREE_DIR, "docs"),
    to: join(ROOT, "docs"),
    filter: ["agents.md"],
  },
];

// ── 1. Clone or pull repo ───────────────────────────────────────────
function ensureRepo(): void {
  if (existsSync(join(WORKTREE_DIR, ".git"))) {
    console.log(`[init] Pulling latest: ${REPO_URL}`);
    execSync("git pull --ff-only", { cwd: WORKTREE_DIR, stdio: "inherit" });
  } else {
    console.log(`[init] Cloning ${REPO_URL} → ${WORKTREE_DIR}`);
    mkdirSync(join(WORKTREE_DIR, ".."), { recursive: true });
    execSync(`git clone --depth 1 ${REPO_URL} "${WORKTREE_DIR}"`, { stdio: "inherit" });
  }
}

// ── 2. Sync directories ─────────────────────────────────────────────
function syncDir(from: string, to: string, filter?: string[]): void {
  if (!existsSync(from)) {
    console.warn(`[init] Source "${from}" does not exist, skipping.`);
    return;
  }

  if (!existsSync(to)) {
    mkdirSync(to, { recursive: true });
  }

  // Copy files from source to destination
  const entries = filter ? readdirSync(from).filter((e) => filter.includes(e)) : readdirSync(from);
  for (const entry of entries) {
    const srcFile = join(from, entry);
    const destFile = join(to, entry);
    const stat = statSync(srcFile);

    if (stat.isDirectory()) {
      cpSync(srcFile, destFile, { recursive: true });
    } else {
      const shouldCopy =
        !existsSync(destFile) || statSync(srcFile).mtimeMs > statSync(destFile).mtimeMs;
      if (shouldCopy) {
        cpSync(srcFile, destFile);
        console.log(`[init] Synced: ${entry}`);
      }
    }
  }
}

// ── Main ────────────────────────────────────────────────────────────
function main(): void {
  console.log("[init] Starting initialization...\n");

  ensureRepo();

  console.log();

  for (const { from, to, filter } of SYNC_MAP) {
    console.log(`[init] Syncing: ${from} → ${to}`);
    syncDir(from, to, filter);
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
