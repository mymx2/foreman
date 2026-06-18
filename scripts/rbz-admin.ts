import { execSync } from "node:child_process";
import { cpSync, existsSync, mkdirSync, readdirSync, statSync } from "node:fs";
import { join, relative, resolve } from "node:path";

const ROOT = resolve(import.meta.dirname, "..");
const WORKTREE_DIR = join(ROOT, ".worktrees", "mica-auto-ksp");
const REPO_URL = "https://github.com/mymx2/mica-auto-ksp.git";
const TARGET_DIR = join(ROOT, "projects", "rbz-admin");

// Directories / files to skip when copying (relative to source root).
const EXCLUDE_PATHS = new Set([
  ".git",
  ".github",
  "libraries",
  "README_CN.md",
  "sync.ts",
  // gradle sub-paths
  join("gradle", "depLibs.versions.toml"),
  join("gradle", "configs", "checkstyle"),
  join("gradle", "configs", "openapi"),
  join("gradle", "configs", "pmd"),
  join("gradle", "configs", "rewrite"),
  join("gradle", "configs", "spotbugs"),
]);

// ── 1. Clone or pull repo ───────────────────────────────────────────
function ensureRepo(): void {
  if (existsSync(join(WORKTREE_DIR, ".git"))) {
    console.log(`[init-backend] Pulling latest: ${REPO_URL}`);
    try {
      execSync("git pull --ff-only", { cwd: WORKTREE_DIR, stdio: "inherit" });
    } catch {
      console.warn("[init-backend] git pull failed, using existing local copy.");
    }
  } else {
    console.log(`[init-backend] Cloning ${REPO_URL} → ${WORKTREE_DIR}`);
    mkdirSync(join(WORKTREE_DIR, ".."), { recursive: true });
    execSync(`git clone --depth 1 ${REPO_URL} "${WORKTREE_DIR}"`, { stdio: "inherit" });
  }
}

// ── 2. Copy files with exclusions ────────────────────────────────────
function copyFiltered(srcDir: string, destDir: string, baseDir: string = srcDir): void {
  if (!existsSync(destDir)) {
    mkdirSync(destDir, { recursive: true });
  }

  for (const entry of readdirSync(srcDir)) {
    const srcPath = join(srcDir, entry);
    const destPath = join(destDir, entry);
    const relPath = relative(baseDir, srcPath);

    // Skip excluded paths
    if (EXCLUDE_PATHS.has(relPath) || EXCLUDE_PATHS.has(relPath.replace(/\\/g, "/"))) {
      console.log(`[init-backend] Skipped: ${relPath}`);
      continue;
    }

    const stat = statSync(srcPath);

    if (stat.isDirectory()) {
      copyFiltered(srcPath, destPath, baseDir);
    } else {
      cpSync(srcPath, destPath);
    }
  }
}

// ── 3. Init git ────────────────────────────────────────────────────
function initGit(): void {
  if (existsSync(join(TARGET_DIR, ".git"))) {
    console.log("[init-backend] Git already initialized, skipping.");
    return;
  }
  console.log("[init-backend] Initializing git repository...");
  execSync("git init", { cwd: TARGET_DIR, stdio: "inherit" });
  execSync("git add -A", { cwd: TARGET_DIR, stdio: "inherit" });
  execSync('git commit -m "feat: init"', {
    cwd: TARGET_DIR,
    stdio: "inherit",
  });
}

// ── Main ────────────────────────────────────────────────────────────
function main(): void {
  console.log("[init-backend] Starting backend init...\n");

  // Guard: skip if target already has content
  if (existsSync(TARGET_DIR) && readdirSync(TARGET_DIR).length > 0) {
    console.log(`[init-backend] Target "${TARGET_DIR}" is not empty, skipping init.`);
    return;
  }

  ensureRepo();

  console.log();

  console.log(`[init-backend] Copying files: ${WORKTREE_DIR} → ${TARGET_DIR}`);
  copyFiltered(WORKTREE_DIR, TARGET_DIR);

  console.log();

  initGit();

  console.log("\n[init-backend] Done.");
}

main();
