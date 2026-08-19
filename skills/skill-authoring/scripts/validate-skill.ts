#!/usr/bin/env node
/**
 * validate-skill.ts — skill-authoring 的配套校验 CLI。
 *
 * 对单个技能执行 SKILL.md Evidence Ladder 的七道质量门：
 *   1. frontmatter 契约：可解析、name 匹配目录、目录名 kebab-case、
 *      description 40–500 且含触发/排除提示
 *   2. 隔离 grep：prose 中零 `skills/<name>/SKILL.md` 跨技能文件引用
 *   3. 可移植 grep：零个人路径、裸仓库相对调用、私有上下文、AI 署名
 *   4. 内容红线：Markdown prose 中零分类器敏感指令字面量
 *   5. 引用完整性：prose 提到的 references/ agents/ scripts/ 路径真实存在
 *   6. 触发词区分度：when_to_use 与兄弟技能 Jaccard < 0.5（不在 skills/ 树中时跳过）
 *   7. 结构完整性：Outcome Contract 在场、至少一个含编号步骤的流程小节、无空标题
 *
 * 门 1–6 的规则在同目录规则库（skill-frontmatter.ts / checks-content.ts，
 * 规则的单一事实源）；本文件只做编排、门 7 与 CLI。全部导入都在技能目录
 * 内部，随技能目录拷贝即可独立运行。仓库级测试在 scripts/tests/。
 *
 * 用法：node validate-skill.ts <技能目录 | SKILL.md 路径>
 * 零第三方依赖，Node >= 23 直接运行（原生 type stripping）。
 */

import { existsSync, readFileSync, readdirSync, statSync } from 'node:fs'
import path from 'node:path'
import { pathToFileURL } from 'node:url'
import {
  checkAttributionLeak,
  checkContextClassifierLiterals,
  checkDescriptionConformance,
  checkPersonalPaths,
  checkPortableInvocations,
  checkPortableSkillSurface,
  checkSkillIsolation,
  checkTriggerOverlap,
  REF_PATTERN,
  SCRIPT_VAR_PATTERN,
} from './checks-content.ts'
import { FailError, fail, parseFrontmatter, parseWhenToUseKeywords } from './skill-frontmatter.ts'

export { FailError }

/** 递归收集目录下的 *.md（目录不存在时返回空）。 */
function rglobMd(dir: string): string[] {
  if (!existsSync(dir) || !statSync(dir).isDirectory()) return []
  const out: string[] = []
  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    if (entry.name === '.git') continue
    const full = path.join(dir, entry.name)
    if (entry.isDirectory()) out.push(...rglobMd(full))
    else if (entry.isFile() && entry.name.endsWith('.md')) out.push(full)
  }
  return out.sort()
}

// ── 门 7：结构完整性（本脚本自有规则） ─────────────────────────────────────

/** 技能目录名必须 lowercase-hyphen-separated。 */
const KEBAB_CASE_RE = /^[a-z0-9]+(-[a-z0-9]+)*$/

interface Heading {
  level: number
  text: string
  /** 1-based 行号 */
  line: number
}

/**
 * 结构完整性契约（Evidence Ladder 第 7 条）：
 *   - `## Outcome Contract` 必须在场
 *   - 至少一个二级小节含编号步骤（流程小节）
 *   - 无空标题（标题后首个非空行不得是另一个标题或 EOF）
 * 代码围栏内的 `#` 行不算标题。
 */
export function checkStructuralCompleteness(text: string): void {
  const lines = text.split(/\r\n|\r|\n/)

  // 跳过 frontmatter
  let start = 0
  if (lines[0] === '---') {
    const end = lines.indexOf('---', 1)
    if (end !== -1) start = end + 1
  }

  const headings: Heading[] = []
  let inCode = false
  for (let i = start; i < lines.length; i++) {
    const line = lines[i]
    if (line.trimStart().startsWith('```')) {
      inCode = !inCode
      continue
    }
    if (inCode) continue
    const m = line.match(/^(#{1,6})\s+(.+?)\s*$/)
    if (m) headings.push({ level: m[1].length, text: m[2], line: i + 1 })
  }

  const hasOutcomeContract = headings.some(
    h => h.level === 2 && h.text.trim().toLowerCase() === 'outcome contract',
  )
  if (!hasOutcomeContract) {
    fail('MISSING OUTCOME CONTRACT: expected a "## Outcome Contract" section')
  }

  // 二级小节的正文范围：到下一个同级或更高级标题为止
  const hasProcessSection = headings.some((h, i) => {
    if (h.level !== 2) return false
    let end = lines.length
    for (const next of headings.slice(i + 1)) {
      if (next.level <= h.level) {
        end = next.line - 1
        break
      }
    }
    return lines.slice(h.line, end).some(l => /^\s*\d+\.\s/.test(l))
  })
  if (!hasProcessSection) {
    fail('NO PROCESS SECTION: expected at least one section with numbered steps')
  }

  const orphans = headings.filter(h => {
    let i = h.line // h.line 是 1-based；数组下标即下一行
    while (i < lines.length && !lines[i].trim()) i++
    return i >= lines.length || /^#{1,6}\s/.test(lines[i])
  })
  if (orphans.length > 0) {
    fail(
      'ORPHANED HEADING: headings with no content:\n  ' +
        orphans.map(h => `line ${h.line}: '${'#'.repeat(h.level)} ${h.text}'`).join('\n  '),
    )
  }
  console.log('ok: structural completeness')
}

// ── 七道门的编排 ──────────────────────────────────────────────────────────

/**
 * 校验单个技能。传入技能目录或其中的 SKILL.md 路径。
 * 每道门的结果实时打印（ok:/skip: 行），返回全部失败消息（空数组 = 全绿）。
 */
export function validateSkill(input: string): string[] {
  const skillFile = statSync(input).isDirectory() ? path.join(input, 'SKILL.md') : input
  if (!existsSync(skillFile)) {
    fail(`SKILL.md NOT FOUND: ${skillFile}`)
  }
  const skillDir = path.dirname(skillFile)
  const skillName = path.basename(skillDir)
  const skillMdFiles = rglobMd(skillDir)

  const failures: string[] = []
  const gate = (label: string, run: () => void): void => {
    try {
      run()
    } catch (err) {
      if (err instanceof FailError) {
        failures.push(`[${label}] ${err.message}`)
      } else {
        throw err
      }
    }
  }

  gate('frontmatter', () => {
    const fields = parseFrontmatter(skillFile)
    if (fields.name !== skillName) {
      fail(`NAME MISMATCH: ${skillFile} frontmatter name=${fields.name} dir=${skillName}`)
    }
    if (!KEBAB_CASE_RE.test(skillName)) {
      fail(`INVALID DIRECTORY NAME: ${skillName} is not lowercase-hyphen-separated`)
    }
    checkDescriptionConformance({ [skillName]: fields.description })
  })

  gate('isolation', () => checkSkillIsolation(skillDir, [skillFile]))

  gate('portability', () => {
    checkPersonalPaths(skillMdFiles)
    checkPortableInvocations(skillDir, [skillFile])
    checkPortableSkillSurface(skillDir, skillMdFiles)
    checkAttributionLeak(skillDir)
  })

  gate('content-red-lines', () => checkContextClassifierLiterals(skillDir, [skillFile]))

  // 引用目标相对技能目录解析（库里的 checkReferences 按仓库布局解析，
  // 独立安装副本里没有 skills/ 父层，这里改用本地解析以两种布局都成立）
  gate('references', () => {
    const text = readFileSync(skillFile, 'utf8')
    const refs = new Set<string>()
    for (const m of text.matchAll(REF_PATTERN)) refs.add(m[0])
    for (const m of text.matchAll(SCRIPT_VAR_PATTERN)) refs.add(`scripts/${m[1]}`)
    for (const ref of [...refs].sort()) {
      if (!existsSync(path.join(skillDir, ref))) {
        fail(`BROKEN REFERENCE: ${skillFile} references ${ref} but file does not exist`)
      }
      console.log(`ok: reference ${skillName}/${ref}`)
    }
  })

  const parentDir = path.dirname(skillDir)
  if (path.basename(parentDir) === 'skills') {
    gate('trigger-distinctness', () => {
      const keywords: Record<string, Set<string>> = {
        [skillName]: parseWhenToUseKeywords(parseFrontmatter(skillFile).when_to_use),
      }
      for (const entry of readdirSync(parentDir, { withFileTypes: true })) {
        if (!entry.isDirectory() || entry.name === skillName) continue
        const sibling = path.join(parentDir, entry.name, 'SKILL.md')
        if (!existsSync(sibling)) continue
        try {
          keywords[entry.name] = parseWhenToUseKeywords(parseFrontmatter(sibling).when_to_use)
        } catch (err) {
          if (!(err instanceof FailError)) throw err
          console.error(`warn: sibling ${entry.name} frontmatter unparsable, skipped`)
        }
      }
      checkTriggerOverlap(keywords)
    })
  } else {
    console.log('skip: trigger distinctness (skill not inside a skills/ tree)')
  }

  gate('structure', () => checkStructuralCompleteness(readFileSync(skillFile, 'utf8')))

  return failures
}

// ── CLI 入口 ──────────────────────────────────────────────────────────────

const isMain =
  !!process.argv[1] && import.meta.url === pathToFileURL(path.resolve(process.argv[1])).href

if (isMain) {
  const input = process.argv[2]
  if (!input) {
    console.error('usage: node validate-skill.ts <skill-dir | SKILL.md path>')
    process.exit(1)
  }
  try {
    const failures = validateSkill(path.resolve(input))
    if (failures.length > 0) {
      console.error(`\nFAILED: ${failures.length} gate(s) failed`)
      for (const message of failures) console.error(`\n${message}`)
      process.exit(1)
    }
    console.log('\nPASSED: all evidence gates green')
  } catch (err) {
    console.error(err instanceof Error ? err.message : String(err))
    process.exit(1)
  }
}
