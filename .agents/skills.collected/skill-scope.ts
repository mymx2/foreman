/* eslint-disable */
/* prettier-ignore */
/* oxlint-disable */
/* oxfmt-ignore */
// @ts-nocheck
// noinspection JSUnusedGlobalSymbols
import { mkdir, readFile, writeFile } from "node:fs/promises";
import { join, resolve } from "node:path";

// ━━━ Config ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

const SOURCE_DIR = resolve("./skills");
const OUTPUT_DIR = resolve("./skills.local");

interface SkillGroup {
  /** 输出文件名（相对于 OUTPUT_DIR） */
  outputFile: string;
  /** Markdown 一级标题 */
  title: string;
  /** 技能 ID 列表 */
  skills: string[];
}

const GROUPS: SkillGroup[] = [
  {
    outputFile: "rbz-artifact-SKILL.local.md",
    title: "# rbz-artifact — 设计与创意技能清单",
    skills: [
      "docx",
      "xlsx",
      "pptx",
      "pdf",
      "canvas-design",
      "frontend-design",
      "algorithmic-art",
      "theme-factory",
      "brand-guidelines",
      "internal-comms",
      "doc-coauthoring",
      "web-artifacts-builder",
      "webapp-testing",
      "slack-gif-creator",
      "arrow-js",
      "slidev",
    ],
  },
  {
    outputFile: "rbz-client-SKILL.local.md",
    title: "# rbz-client — Vue 3 + Vite 前端技能清单",
    skills: [
      "vue",
      "vue-best-practices",
      "pinia",
      "vite",
      "unocss",
      "vue-router-best-practices",
      "vue-pinia-best-practices",
      "vueuse-functions",
      "vue-jsx-best-practices",
      "vue-debug-guides",
      "vue-testing-best-practices",
      "create-adaptable-composable",
      "vitest",
      "playwright-cli",
      "pnpm",
      "tsdown",
      "turborepo",
      "vitepress",
      "web-design-guidelines",
      "shadcn-vue",
      "valibot",
      "formisch",
      "ai-sdk",
      "vize",
    ],
  },
  {
    outputFile: "app-mini-SKILL.local.md",
    title: "# app-mini — 微信小程序技能清单",
    skills: [
      "wechat-miniprogram",
      "glass-easel",
      "tdesign-miniprogram",
      "skyline-overview",
      "skyline-config",
      "skyline-components",
      "skyline-route",
      "skyline-worklet",
      "skyline-scroll-api",
      "skyline-wxss",
      "wechatide-skill",
    ],
  },
  {
    outputFile: "app-android-SKILL.local.md",
    title: "# app-android — Android 原生技能清单",
    skills: [
      "android-cli",
      "agp-9-upgrade",
      "adaptive",
      "appfunctions",
      "camerax",
      "display-glasses-with-jetpack-compose-glimmer",
      "edge-to-edge",
      "engage-sdk-integration",
      "migrate-xml-views-to-jetpack-compose",
      "navigation-3",
      "perfetto-sql",
      "perfetto-trace-analysis",
      "play-billing-library-version-upgrade",
      "play-policy-insights",
      "android-intent-security",
      "r8-analyzer",
      "styles",
      "testing-setup",
      "verified-email",
      "wear-compose-m3",
    ],
  },
  {
    outputFile: "rbz-admin-SKILL.local.md",
    title: "# rbz-admin — Kotlin + Spring Boot 后端技能清单",
    skills: [
      "gradle-kotlin-dsl-doctor",
      "kotlin-spring-proxy-compatibility",
      "kotlin-idiomatic-refactorer-spring-aware",
      "java-kotlin-migration-assistant",
      "jpa-spring-data-kotlin-mapper",
      "jdbc-dsl",
      "design-postgres-tables",
      "redis-core",
      "schema-migration-planner",
      "transaction-consistency-designer",
      "spring-mvc-webflux-api-builder",
      "jackson-kotlin-serialization-specialist",
      "error-model-validation-architect",
      "domain-decomposition-api-design-advisor",
      "spring-security-configurator-auditor",
      "configuration-properties-profiles-kotlin-safe",
      "spring-context-di-reasoning",
      "observability-integrator",
      "performance-concurrency-advisor",
      "stacktrace-log-triage",
      "production-incident-responder",
      "integration-resilience-engineer",
      "spring-kotlin-code-review",
      "test-suite-builder",
      "dependency-conflict-resolver",
      "project-context-ingestion",
      "upgrade-breaking-change-navigator",
      "ci-cd-containerization-advisor",
      "idea-mcp",
    ],
  },
  {
    outputFile: "misc-SKILL.local.md",
    title: "# 其他技能清单",
    skills: [
      "tencentos-expert",
      "sql-parser-cst",
      "webgpu-threejs-tsl",
    ],
  },
];

// ━━━ Implementation ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

function extractFrontmatter(content: string): string {
  // SKILL.md starts with --- ... --- frontmatter
  const match = content.match(/^---\r?\n([\s\S]*?)\r?\n---/);
  return match ? match[1].trimEnd() : "(no frontmatter)";
}

async function processGroup(group: SkillGroup): Promise<{ file: string; total: number; ok: number; fail: number }> {
  const lines: string[] = [];

  lines.push(group.title);
  lines.push("");
  lines.push(`> 来源: \`${SOURCE_DIR}\``);
  lines.push(`> 生成时间: ${new Date().toISOString()}`);
  lines.push(`> 技能数量: ${group.skills.length}`);
  lines.push("");
  lines.push("---");
  lines.push("");

  let ok = 0;
  let fail = 0;
  for (let i = 0; i < group.skills.length; i++) {
    const name = group.skills[i];
    const num = i + 1;
    const skillDir = join(SOURCE_DIR, name);
    const skillFile = join(skillDir, "SKILL.md");

    try {
      const content = await readFile(skillFile, "utf-8");
      const frontmatter = extractFrontmatter(content);
      const localPath = resolve(skillDir).replace(/\\/g, "/");

      ok++;
      lines.push(`## ${num}. ${name}`);
      lines.push("");
      lines.push(`**本地路径**: \`${localPath}\``);
      lines.push("");
      lines.push("### Frontmatter");
      lines.push("");
      lines.push("```yaml");
      lines.push(frontmatter);
      lines.push("```");
      lines.push("");
      lines.push("---");
      lines.push("");
    } catch (err: any) {
      fail++;
      lines.push(`## ${num}. ${name}`);
      lines.push("");
      lines.push(`**状态**: ❌ 读取失败 — ${err.message}`);
      lines.push("");
      lines.push("---");
      lines.push("");
    }
  }

  const outputFile = join(OUTPUT_DIR, group.outputFile);
  await writeFile(outputFile, lines.join("\n"), "utf-8");
  return { file: group.outputFile, total: group.skills.length, ok, fail };
}

async function main() {
  console.log(`Processing ${GROUPS.length} groups...\n`);

  await mkdir(OUTPUT_DIR, { recursive: true });
  const results = await Promise.all(GROUPS.map(processGroup));

  for (const r of results) {
    const status = r.fail === 0 ? "✅" : "⚠️";
    console.log(`${status} ${r.file}: ${r.ok}/${r.total} ok${r.fail > 0 ? `, ${r.fail} failed` : ""}`);
  }

  const totalOk = results.reduce((s, r) => s + r.ok, 0);
  const totalFail = results.reduce((s, r) => s + r.fail, 0);
  const totalAll = results.reduce((s, r) => s + r.total, 0);
  console.log(`\nDone: ${results.length} files, ${totalOk}/${totalAll} skills ok${totalFail > 0 ? `, ${totalFail} failed` : ""}`);
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
