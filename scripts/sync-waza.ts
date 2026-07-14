import { execSync } from "node:child_process";
import {
  cpSync,
  existsSync,
  mkdirSync,
  readFileSync,
  readdirSync,
  statSync,
  writeFileSync,
} from "node:fs";
import { join, resolve } from "node:path";

const AGENT_DIR = ".qoder";

const ROOT = resolve(import.meta.dirname, "..");
const WORKTREE_DIR = join(ROOT, ".worktrees", "Waza");
const REPO_URL = "https://github.com/tw93/Waza";

const RULES_FROM = join(WORKTREE_DIR, "rules");
const RULES_TO = join(ROOT, AGENT_DIR, "rules");

// ── helpers ─────────────────────────────────────────────────────────

/**
 * Extract YAML frontmatter block (including the surrounding `---` fences)
 * from the beginning of a string.  Returns "" when no frontmatter is found.
 */
function extractFrontmatter(content: string): string {
  if (!content.startsWith("---")) return "";
  const endIndex = content.indexOf("---", 3);
  if (endIndex < 0) return "";
  // Include the closing `---` and the newline that follows it.
  return content.slice(0, endIndex + 3) + "\n";
}

// ── 1. Clone or pull repo ───────────────────────────────────────────
function ensureRepo(): void {
  if (existsSync(join(WORKTREE_DIR, ".git"))) {
    console.log(`[waza] Pulling latest: ${REPO_URL}`);
    execSync("git pull --ff-only", { cwd: WORKTREE_DIR, stdio: "inherit" });
  } else {
    console.log(`[waza] Cloning ${REPO_URL} → ${WORKTREE_DIR}`);
    mkdirSync(join(WORKTREE_DIR, ".."), { recursive: true });
    execSync(`git clone --depth 1 ${REPO_URL} "${WORKTREE_DIR}"`, { stdio: "inherit" });
  }
}

// ── 2. Sync rules directory ──────────────────────────────────────────
function syncRules(): void {
  if (!existsSync(RULES_FROM)) {
    console.warn(`[waza] Source "${RULES_FROM}" does not exist, skipping.`);
    return;
  }

  if (!existsSync(RULES_TO)) {
    mkdirSync(RULES_TO, { recursive: true });
  }

  for (const entry of readdirSync(RULES_FROM)) {
    if (entry === "waza-routing.md") continue;

    const srcFile = join(RULES_FROM, entry);
    const destFile = join(RULES_TO, entry);
    const stat = statSync(srcFile);

    if (stat.isDirectory()) {
      cpSync(srcFile, destFile, { recursive: true });
      console.log(`[waza] Synced dir: ${entry}`);
      continue;
    }

    const needsCopy = !existsSync(destFile) || stat.mtimeMs > statSync(destFile).mtimeMs;
    if (needsCopy) {
      // Preserve any YAML frontmatter already present in the destination.
      if (existsSync(destFile)) {
        const destContent = readFileSync(destFile, "utf-8");
        const fm = extractFrontmatter(destContent);
        if (fm) {
          const srcBody = readFileSync(srcFile, "utf-8");
          writeFileSync(destFile, fm + "\n" + srcBody, "utf-8");
          console.log(`[waza] Synced (frontmatter preserved): ${entry}`);
        } else {
          cpSync(srcFile, destFile);
          console.log(`[waza] Synced: ${entry}`);
        }
      } else {
        cpSync(srcFile, destFile);
        console.log(`[waza] Synced: ${entry}`);
      }
    }
  }
}

// ── Main ────────────────────────────────────────────────────────────
function main(): void {
  console.log("[waza] Starting Waza sync...\n");

  ensureRepo();

  console.log();

  console.log(`[waza] Syncing rules: ${RULES_FROM} → ${RULES_TO}`);
  syncRules();

  console.log();

  console.log("\n[waza] Done.");

  // Run formatter if available
  try {
    const checkCmd = process.platform === "win32" ? "where vp 2>nul" : "which vp 2>/dev/null";
    execSync(checkCmd, { stdio: "ignore" });
    console.log("\n[waza] Running vp fmt...");
    execSync("vp fmt", { stdio: "inherit" });
  } catch {
    console.log("\n[waza] vp not found, skipping format.");
  }
}

main();
