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

const DOCS_DIR = join(ROOT, "docs");

const RESOLVER_PATH = join(WORKTREE_DIR, "skills", "RESOLVER.md");
const ROUTING_SRC = join(RULES_FROM, "waza-routing.md");
const ROUTING_PATH = join(DOCS_DIR, "__waza-routing.md");

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
    // waza-routing.md is output separately to docs/__waza-routing.md
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

// ── 3. Append RESOLVER.md to waza-routing.md ────────────────────────
function appendResolver(): void {
  if (!existsSync(RESOLVER_PATH)) {
    console.warn(`[waza] "${RESOLVER_PATH}" does not exist, skipping.`);
    return;
  }

  if (!existsSync(ROUTING_SRC)) {
    console.warn(`[waza] "${ROUTING_SRC}" does not exist, skipping append.`);
    return;
  }

  // Use the source file as the authoritative body — no fragile text matching needed.
  const srcBody = readFileSync(ROUTING_SRC, "utf-8").replace(/\r\n/g, "\n").trimEnd();
  const resolverContent = readFileSync(RESOLVER_PATH, "utf-8").replace(/\r\n/g, "\n");

  if (!existsSync(DOCS_DIR)) {
    mkdirSync(DOCS_DIR, { recursive: true });
  }

  // Preserve any custom YAML frontmatter already present in the destination.
  let frontmatter = "";
  if (existsSync(ROUTING_PATH)) {
    const destContent = readFileSync(ROUTING_PATH, "utf-8").replace(/\r\n/g, "\n");
    frontmatter = extractFrontmatter(destContent);
  }

  const SEPARATOR = "\n\n<!-- ── RESOLVER.md (auto-appended by sync-waza.ts) ── -->";
  const combined =
    (frontmatter ? frontmatter + "\n" : "") +
    srcBody +
    SEPARATOR +
    "\n\n" +
    resolverContent.trimEnd() +
    "\n";

  writeFileSync(ROUTING_PATH, combined, "utf-8");
  console.log(`[waza] Appended RESOLVER.md → ${ROUTING_PATH}`);
}

// ── Main ────────────────────────────────────────────────────────────
function main(): void {
  console.log("[waza] Starting Waza sync...\n");

  ensureRepo();

  console.log();

  console.log(`[waza] Syncing rules: ${RULES_FROM} → ${RULES_TO}`);
  syncRules();

  console.log();

  appendResolver();

  console.log("\n[waza] Done.");

  // Run formatter if available
  try {
    const checkCmd = process.platform === "win32" ? "where vp 2>nul" : "which vp 2>/dev/null";
    execSync(checkCmd, { stdio: "ignore" });
    console.log("\n[waza] Running vp run fmt...");
    execSync("vp run fmt", { stdio: "inherit" });
  } catch {
    console.log("\n[waza] vp not found, skipping format.");
  }
}

main();
