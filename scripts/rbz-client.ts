import { execSync } from "node:child_process";
import {
  cpSync,
  existsSync,
  mkdirSync,
  mkdtempSync,
  readFileSync,
  readdirSync,
  rmSync,
  statSync,
  writeFileSync,
} from "node:fs";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";

const ROOT = resolve(import.meta.dirname, "..");

// ── Config (tweak these for a new sub-project) ─────────────────────
const SUB_NAME = "rbz-client"; // 子项目目录名 (projects/<SUB_NAME>)
const APP_NAME = "web"; // app 目录名 (apps/<APP_NAME>)
const APP_TEMPLATE = "vue-ts"; // create-vite 模板

const TARGET_DIR = join(ROOT, "projects", SUB_NAME);

// vp create vite:monorepo refuses to run inside an existing monorepo
// (root has pnpm-workspace.yaml). Scaffold in the system temp
// dir — which is outside any workspace — then copy the result into
// projects/<sub>. The default app (apps/website) is vanilla TS;
// we replace it with a Vue TS app via create-vite.

// ── 1. Ensure vp is available ──────────────────────────────────────
function ensureVp(): void {
  try {
    execSync("vp --version", { stdio: "ignore" });
  } catch {
    throw new Error("[init-client] vp not found on PATH. Install: https://vite.plus/");
  }
}

// ── 2. Scaffold monorepo in temp dir, then copy to target ──────────
function scaffoldMonorepo(): void {
  const tmpRoot = mkdtempSync(join(tmpdir(), `${SUB_NAME}-`));
  const tmpTarget = join(tmpRoot, SUB_NAME);
  try {
    const cmd = [
      "vp create vite:monorepo",
      `--directory ${SUB_NAME}`,
      "--no-git",
      "--no-hooks",
      "--package-manager pnpm",
      "--no-interactive",
    ].join(" ");
    console.log(`[init-client] Scaffold monorepo in ${tmpRoot}:\n  ${cmd}\n`);
    execSync(cmd, { cwd: tmpRoot, stdio: "inherit" });

    console.log(`\n[init-client] Copying → ${TARGET_DIR}`);
    cpSync(tmpTarget, TARGET_DIR, {
      recursive: true,
      filter: (src) => !src.includes("node_modules"),
    });
  } finally {
    rmSync(tmpRoot, { recursive: true, force: true });
  }
}

// ── 3. Replace default app with Vue TS app ─────────────────────────
function replaceWithVueApp(): void {
  const defaultApp = join(TARGET_DIR, "apps", "website");
  if (existsSync(defaultApp)) {
    console.log("[init-client] Removing default apps/website");
    rmSync(defaultApp, { recursive: true, force: true });
  }

  // vp create vite (create-vite shorthand) doesn't support --directory.
  // Pass the project name as a positional arg after --; vp detects the
  // monorepo and places the app under apps/ automatically.
  const cmd = `vp create vite --no-interactive -- ${APP_NAME} --template ${APP_TEMPLATE}`;
  console.log(`[init-client] Creating Vue app:\n  ${cmd}\n`);
  execSync(cmd, { cwd: TARGET_DIR, stdio: "inherit" });
}

// ── 4. Fix root package.json dev script ────────────────────────────
// vp create vite:monorepo writes "vp run website#dev" (the default app
// name). After replacing with our app, sync the script to match.
function fixRootScripts(): void {
  const pkgPath = join(TARGET_DIR, "package.json");
  if (!existsSync(pkgPath)) return;
  const pkg = JSON.parse(readFileSync(pkgPath, "utf-8"));
  if (pkg.scripts?.dev) {
    pkg.scripts.dev = `vp run ${APP_NAME}#dev`;
    writeFileSync(pkgPath, JSON.stringify(pkg, null, 2) + "\n", "utf-8");
    console.log(`[init-client] Fixed dev script → vp run ${APP_NAME}#dev`);
  }
}

// ── 5. Fix vue app vite.config.ts imports ──────────────────────────
// create-vite imports defineConfig from "vite", but Vite+ lint requires
// "vite-plus". Merge the two vite-plus imports into one.
function fixVueAppConfig(): void {
  const cfg = join(TARGET_DIR, "apps", APP_NAME, "vite.config.ts");
  if (!existsSync(cfg)) return;
  let content = readFileSync(cfg, "utf-8");
  content = content.replace(
    /import\s*\{\s*defineConfig\s*\}\s*from\s*"vite";\nimport\s+vue\s+from\s*"@vitejs\/plugin-vue";\nimport\s*\{\s*lazyPlugins\s*\}\s*from\s*"vite-plus";/,
    'import { defineConfig, lazyPlugins } from "vite-plus";\nimport vue from "@vitejs/plugin-vue";',
  );
  writeFileSync(cfg, content, "utf-8");
  console.log(`[init-client] Fixed apps/${APP_NAME}/vite.config.ts imports`);
}

// ── 6. Write .vscode/launch.json ───────────────────────────────────
// vp create's --editor doesn't fire in non-interactive mode, so write
// a minimal launch.json manually.
function writeEditorConfig(): void {
  const vscodeDir = join(TARGET_DIR, ".vscode");
  if (!existsSync(vscodeDir)) {
    mkdirSync(vscodeDir, { recursive: true });
  }
  const launch = {
    version: "0.2.0",
    configurations: [
      {
        type: "node-terminal",
        name: "JavaScript Debug Terminal",
        request: "launch",
      },
    ],
  };
  writeFileSync(join(vscodeDir, "launch.json"), JSON.stringify(launch, null, 2) + "\n", "utf-8");
  console.log("[init-client] Wrote .vscode/launch.json");
}

// ── 7. Print generated tree (depth 3) ──────────────────────────────
function printTree(): void {
  function walk(dir: string, prefix: string, depth: number): void {
    if (depth <= 0) return;
    const entries = readdirSync(dir).sort();
    for (const entry of entries) {
      const path = join(dir, entry);
      const isDir = statSync(path).isDirectory();
      console.log(`${prefix}${entry}${isDir ? "/" : ""}`);
      if (isDir && entry !== "node_modules") {
        walk(path, prefix + "  ", depth - 1);
      }
    }
  }
  if (existsSync(TARGET_DIR)) {
    console.log("\n[init-client] Generated tree:");
    walk(TARGET_DIR, "", 3);
  }
}

// ── Main ────────────────────────────────────────────────────────────
function main(): void {
  console.log("[init-client] Starting client init...\n");

  if (existsSync(TARGET_DIR) && readdirSync(TARGET_DIR).length > 0) {
    console.log(`[init-client] Target "${TARGET_DIR}" is not empty, skipping init.`);
    return;
  }

  ensureVp();
  scaffoldMonorepo();
  replaceWithVueApp();
  fixRootScripts();
  fixVueAppConfig();
  writeEditorConfig();
  printTree();

  console.log("\n[init-client] Done.");
}

main();
