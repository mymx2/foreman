/**
 * checks-content.ts — 技能内容校验规则库。
 *
 * 独立规则库：不绑定特定仓库布局，任何技能集合都可复用其中的 check_*
 * 函数，或作为编写自有校验链的规则来源。零第三方依赖。
 *
 * 覆盖 SKILL.md 与其 Markdown 引用面的全部内容检查，按防御目标分四组：
 *   元数据契约：frontmatter 解析、description 质量（触发/排除场景、长度）、技能名匹配
 *   可移植性：个人路径、裸相对路径调用、根 SKILL.md、跨技能文件引用
 *   引用完整性：references 存在性、页内锚点、表格管道符
 *   内容红线：分类器敏感字面量、AI 署名泄漏、触发词撞车
 *
 * 每个 check_* 函数成功时打印 `ok:` 行，失败时 fail() 抛出 FailError。
 * 除 stdout/stderr 外无副作用。零第三方依赖（仅 node:fs / node:path）。
 */

import { existsSync, readFileSync, readdirSync, statSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { githubHeadingInventory } from './markdown-fragments.ts'
import {
  fail,
  parseFrontmatter,
  parseWhenToUseKeywords,
  SKILL_REF_RE,
  SKILLS_DIR,
} from './skill-frontmatter.ts'

// ── 规则常量：所有匹配模式、黑名单字面量、契约字段集中在这里 ──────────────

/** prose 中对 references/ agents/ scripts/ 的相对引用（排除前面带 /. 的误配） */
export const REF_PATTERN = /(?<![/.])\b(?:references|agents|scripts)\/[\w/.-]+\b/g

/** `${VAR}/scripts/<file>` 形式的脚本引用（提取文件名部分） */
export const SCRIPT_VAR_PATTERN = /\}\/scripts\/([\w/.-]+)/g

/** Markdown 行内链接目标 */
export const LINK_RE = /\[[^\]]*\]\(([^)]+)\)/g

/** 视为外部链接、跳过存在性检查的协议前缀 */
export const URL_PREFIXES = ['http://', 'https://', 'mailto:', 'ftp://', 'tel:', 'data:']

/** 表格分隔行（--- 与 | 组成） */
export const SEP_RE = /^[\s|:-]+$/

/** 个人主目录绝对路径，prose 中禁止硬编码 */
export const PERSONAL_PATH_PATTERN = /\/(?:Users|home)\/[A-Za-z0-9._-]+\//

/** 私有项目/会话上下文特征：公开技能面禁止出现 */
export const PRIVATE_CONTEXT_RE =
  /(?:\.codex\/(?:sessions|memories)|private[-_/](?:repo|project|tool)|internal[-_/](?:repo|project|tool))/i

/** AI 共同作者署名泄漏黑名单（本模块拥有此清单，扫描时排除自身） */
export const ATTRIBUTION_PATTERNS = [
  'Co-Authored-By: Claude',
  'Co-authored-by: Cursor',
  'noreply@anthropic.com',
  'cursoragent@cursor.com',
]

/**
 * 直接的对抗性指令字面量：常驻模型上下文的 Markdown 里出现会触发提供方分类器。
 * 模式保持词法级，不在本文件中复刻完整触发句。
 */
export const CONTEXT_CLASSIFIER_PATTERNS: Array<[string, RegExp]> = [
  ['instruction-priority override', /\bignore\s+(?:all\s+)?(?:prior|previous)\s+instructions\b/i],
  ['role reassignment', /\byou\s+are\s+now\s+(?:x|an?\s+[a-z][a-z-]*|the\s+[a-z][a-z-]*)\b/i],
  ['false urgency', /\bact\s+now\b/i],
  ['authority appeal', /\bthe\s+(?:ceo|founder|admin)\s+says\b/i],
  ['urgent imperative', /\burgent\s*:\s*do\s+.+?\s+immediately\b/i],
]

/** 裸的仓库相对调用（bash skills/... 之类），安装副本里必然 127 */
export const BARE_INVOCATION_RE = /\b(?:bash|sh|python3)\s+(?:\.\.\/)*(?:skills|scripts)\//

// ── 文件系统小工具：walker 与路径呈现 ─────────────────────────────────────

/** 递归列出目录下全部文件（跳过 .git），结果排序。 */
function walkFiles(dir: string): string[] {
  const out: string[] = []
  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    if (entry.name === '.git') continue
    const full = path.join(dir, entry.name)
    if (entry.isDirectory()) {
      out.push(...walkFiles(full))
    } else if (entry.isFile()) {
      out.push(full)
    }
  }
  return out.sort()
}

/** 递归收集目录下的 *.md（目录不存在时返回空）。 */
function rglobMd(dir: string): string[] {
  if (!existsSync(dir) || !statSync(dir).isDirectory()) return []
  return walkFiles(dir).filter(f => f.endsWith('.md'))
}

/** 相对路径以 POSIX 斜杠呈现（跨平台消息格式一致）。 */
function relPosix(root: string, target: string): string {
  return path.relative(root, target).split(path.sep).join('/')
}

function readText(file: string): string {
  return readFileSync(file, 'utf8')
}

/** 容错版 decodeURIComponent：非法 % 序列时原样返回（与宽松链接处理一致）。 */
function unquoteSafe(s: string): string {
  try {
    return decodeURIComponent(s)
  } catch {
    return s
  }
}

// ── 元数据契约组 ──────────────────────────────────────────────────────────

/** 统计一行中未转义、不在行内代码里的管道符数量。 */
export function pipeCount(s: string): number {
  let n = 0
  let tick = false
  let i = 0
  while (i < s.length) {
    if (s[i] === '\\' && i + 1 < s.length) {
      i += 2
      continue
    }
    if (s[i] === '`') {
      tick = !tick
    } else if (s[i] === '|' && !tick) {
      n++
    }
    i++
  }
  return n
}

export interface SkillInventory {
  skillFiles: string[]
  skillDescriptions: Record<string, string>
  skillKeywords: Record<string, Set<string>>
}

/** 发现并解析 skills/<name>/SKILL.md，校验目录名与 frontmatter，返回技能清单。 */
export function checkSkillFiles(root: string): SkillInventory {
  const skillsDir = path.join(root, SKILLS_DIR)
  const skillFiles = existsSync(skillsDir)
    ? readdirSync(skillsDir, { withFileTypes: true })
        .filter(e => e.isDirectory())
        .map(e => path.join(skillsDir, e.name, 'SKILL.md'))
        .filter(f => existsSync(f))
        .sort()
    : []
  if (skillFiles.length === 0) {
    fail(`NO SKILLS FOUND: expected ${SKILLS_DIR}/*/SKILL.md`)
  }
  const skillDescriptions: Record<string, string> = {}
  const skillKeywords: Record<string, Set<string>> = {}
  for (const file of skillFiles) {
    const skillDir = path.basename(path.dirname(file))
    const fields = parseFrontmatter(file)
    if (fields.name !== skillDir) {
      fail(`NAME MISMATCH: ${file} frontmatter name=${fields.name} dir=${skillDir}`)
    }
    skillDescriptions[skillDir] = fields.description
    skillKeywords[skillDir] = parseWhenToUseKeywords(fields.when_to_use)
    console.log(`ok: ${file.split(path.sep).join('/')}`)
  }
  return { skillFiles, skillDescriptions, skillKeywords }
}

// ── description 质量契约（好 skill 标准） ──────────────────────────────────

/** 触发场景提示：英文 "Use when" 或中文 "当…时" 句式（覆盖"当用户需要…时"）。 */
export const TRIGGER_CUE_RE = /(use when|当[^。；\n]{2,}时)/i

/** 排除场景提示：英文 "Not for" 或中文 "不适用 / 不适合 / 不用于"。 */
export const EXCLUSION_CUE_RE = /(not for|不适用|不适合|不用于)/i

/**
 * description 质量契约：判断技能是否合格的描述标准。
 * 必须说明何时使用（触发场景）与何时不用（排除场景），长度 40-500。
 * 中英文描述都接受；不强制英文短语或特定开头。
 */
export function checkDescriptionConformance(skillDescriptions: Record<string, string>): void {
  for (const [skill, description] of Object.entries(skillDescriptions).sort(([a], [b]) =>
    a.localeCompare(b),
  )) {
    const clean = description.trim().replace(/^"+|"+$/g, '')
    const length = clean.length
    if (length < 40) {
      fail(`DESCRIPTION TOO SHORT: ${skill} (${length} chars); need >=40 to be informative`)
    }
    if (length > 500) {
      fail(`DESCRIPTION TOO LONG: ${skill} (${length} chars); trim to <=500 to stay scannable`)
    }
    if (!TRIGGER_CUE_RE.test(clean)) {
      fail(
        `DESCRIPTION MISSING TRIGGER CUE: ${skill}\n` +
          `  Description must say when the skill applies — English "Use when ..." ` +
          `or Chinese "当…时" phrasing. Got: ${JSON.stringify(clean.slice(0, 120))}`,
      )
    }
    if (!EXCLUSION_CUE_RE.test(clean)) {
      fail(
        `DESCRIPTION MISSING EXCLUSION CUE: ${skill}\n` +
          `  Description must say when NOT to use the skill — "Not for ..." ` +
          `or Chinese "不适用 / 不适合". Got: ${JSON.stringify(clean.slice(0, 120))}`,
      )
    }
    console.log(`ok: description ${skill} (${length} chars)`)
  }
}

// ── 内容红线组（prose 级） ────────────────────────────────────────────────

/** 常驻上下文的 Markdown 里不得出现会被提供方分类器命中的指令字面量。 */
export function checkContextClassifierLiterals(root: string, skillFiles: string[]): void {
  const paths = new Set<string>()
  for (const f of rglobMd(path.join(root, 'rules'))) paths.add(f)
  for (const skillFile of skillFiles) {
    for (const f of rglobMd(path.dirname(skillFile))) paths.add(f)
  }

  const offenders: string[] = []
  for (const file of [...paths].sort()) {
    readText(file)
      .split(/\r\n|\r|\n/)
      .forEach((line, idx) => {
        for (const [label, pattern] of CONTEXT_CLASSIFIER_PATTERNS) {
          if (pattern.test(line)) {
            offenders.push(`${relPosix(root, file)}:${idx + 1}: ${label}`)
          }
        }
      })
  }
  if (offenders.length > 0) {
    fail(
      'PROVIDER-SENSITIVE INSTRUCTION LITERAL IN MODEL CONTEXT:\n  ' +
        offenders.join('\n  ') +
        '\n  Describe adversarial behavior by semantic category; do not quote ' +
        'the executable instruction in always-loaded rules or skill prose.',
    )
  }
  console.log(`ok: context classifier literals (${paths.size} Markdown files)`)
}

/** 技能文档禁止硬编码个人主目录路径。 */
export function checkPersonalPaths(skillFiles: string[]): void {
  for (const file of skillFiles) {
    if (PERSONAL_PATH_PATTERN.test(readText(file))) {
      fail(
        `PERSONAL ABSOLUTE PATH IN SKILL: ${file}\n` +
          `  Skill docs must not hard-code personal home-directory paths. ` +
          `Use user-provided paths, project-relative paths, or resolver commands instead.`,
      )
    }
  }
  console.log(`ok: no personal absolute paths (${skillFiles.length} skills)`)
}

/**
 * 公共技能面防私有化漂移：个人默认路径、强制平台工具、私有上下文为 fail。
 */
export function checkPortableSkillSurface(root: string, markdownPaths: string[]): void {
  const scanPaths = [...markdownPaths]
  scanPaths.push(...rglobMd(path.join(root, 'rules')))
  const agents = path.join(root, 'AGENTS.md')
  if (existsSync(agents)) scanPaths.push(agents)

  const seen = new Set<string>()
  for (const file of scanPaths) {
    if (seen.has(file) || !existsSync(file)) continue
    seen.add(file)
    const rel = relPosix(root, file)
    const text = readText(file)
    if (text.includes('~/Downloads')) {
      fail(
        `NON-PORTABLE DEFAULT SAVE PATH: ${rel}\n` +
          `  Use a user-specified directory, project scratch path, or session temp directory.`,
      )
    }
    if (PRIVATE_CONTEXT_RE.test(text)) {
      fail(
        `PRIVATE PROJECT OR SESSION CONTEXT IN PORTABLE SURFACE: ${rel}\n` +
          `  Public skills and rules must not copy private project names, session paths, ` +
          `memory paths, or thread identifiers.`,
      )
    }
  }
  console.log('ok: portable skill surface')
}

// ── 引用完整性组 ──────────────────────────────────────────────────────────

/** SKILL.md 提到的 references/agents/scripts 文件必须真实存在。 */
export function checkReferences(root: string, skillFiles: string[]): void {
  for (const file of skillFiles) {
    const skillDir = path.basename(path.dirname(file))
    const text = readText(file)
    const refs = new Set<string>()
    for (const m of text.matchAll(REF_PATTERN)) refs.add(m[0])
    for (const m of text.matchAll(SCRIPT_VAR_PATTERN)) refs.add(`scripts/${m[1]}`)
    for (const ref of [...refs].sort()) {
      const expected = path.join(root, SKILLS_DIR, skillDir, ref)
      if (!existsSync(expected)) {
        fail(`BROKEN REFERENCE: ${file} references ${ref} but file does not exist`)
      }
      console.log(`ok: reference ${skillDir}/${ref}`)
    }
  }
}

/** 收集全部待检 Markdown：RESOLVER + 每个技能的 SKILL.md 与 references/agents。 */
export function collectAllMd(
  root: string,
  skillNames: Set<string>,
  resolverPath: string,
): string[] {
  const allMd: string[] = [resolverPath]
  for (const skill of [...skillNames].sort()) {
    const skillRoot = path.join(root, SKILLS_DIR, skill)
    allMd.push(path.join(skillRoot, 'SKILL.md'))
    for (const sub of ['references', 'agents']) {
      allMd.push(...rglobMd(path.join(skillRoot, sub)))
    }
  }
  return allMd
}

/** Markdown 链接与页内锚点校验（锚点按 GitHub 渲染规则判定）。 */
export function checkMarkdownLinks(root: string, allMd: string[]): void {
  for (const file of allMd) {
    if (!existsSync(file)) continue
    let inCode = false
    const lines = readText(file).split(/\r\n|\r|\n/)
    for (let lineno = 1; lineno <= lines.length; lineno++) {
      const line = lines[lineno - 1]
      if (line.trimStart().startsWith('```')) {
        inCode = !inCode
        continue
      }
      if (inCode) continue
      for (const m of line.matchAll(LINK_RE)) {
        const raw = m[1].trim()
        if (!raw || raw.startsWith('/')) continue
        if (URL_PREFIXES.some(prefix => raw.startsWith(prefix)) || raw.includes('://')) continue
        const hashIdx = raw.indexOf('#')
        const targetRaw = hashIdx === -1 ? raw : raw.slice(0, hashIdx)
        const fragment = hashIdx === -1 ? '' : raw.slice(hashIdx + 1)
        const target = targetRaw.split('?')[0]
        const targetPath = target === '' ? file : path.resolve(path.dirname(file), target)
        if (!existsSync(targetPath)) {
          fail(`BROKEN MARKDOWN LINK: ${file}:${lineno} -> ${raw}`)
        }
        if (fragment && statSync(targetPath).isFile() && targetPath.toLowerCase().endsWith('.md')) {
          const { anchors } = githubHeadingInventory(readText(targetPath))
          if (!anchors.has(unquoteSafe(fragment))) {
            fail(`BROKEN MARKDOWN FRAGMENT: ${file}:${lineno} -> ${raw}`)
          }
        }
      }
    }
    console.log(`ok: markdown links ${relPosix(root, file)}`)
  }
}

/** 表格数据行的未转义管道符会破坏 GitHub 渲染。 */
export function checkTablePipes(root: string, allMd: string[]): void {
  for (const file of allMd) {
    if (!existsSync(file)) continue
    let inFence = false
    let sepPipes: number | null = null
    const lines = readText(file).split(/\r\n|\r|\n/)
    for (let lineno = 1; lineno <= lines.length; lineno++) {
      const stripped = lines[lineno - 1].trim()
      if (stripped.startsWith('```')) {
        inFence = !inFence
        sepPipes = null
        continue
      }
      if (inFence) {
        sepPipes = null
        continue
      }
      if (SEP_RE.test(stripped) && stripped.includes('---') && stripped.includes('|')) {
        sepPipes = pipeCount(stripped)
        continue
      }
      if (sepPipes !== null && stripped.startsWith('|')) {
        if (pipeCount(stripped) > sepPipes) {
          fail(
            `UNESCAPED PIPE IN TABLE: ${file}:${lineno}\n  Use '\\|' or wrap the cell text in backticks.`,
          )
        }
        continue
      }
      sepPipes = null
    }
    console.log(`ok: table pipes ${relPosix(root, file)}`)
  }
}

// ── 可移植性组（仓库级） ──────────────────────────────────────────────────

/** 根 SKILL.md 会让技能发现停在第一层，阻断嵌套技能安装。 */
export function checkNoRootSkill(root: string): void {
  if (existsSync(path.join(root, 'SKILL.md'))) {
    fail('ROOT SKILL DISALLOWED: a root SKILL.md blocks nested skill discovery')
  }
  console.log('ok: no root SKILL.md')
}

/** 技能 prose 不得指示 agent 运行裸的仓库相对命令（安装副本里必然 127）。 */
export function checkPortableInvocations(root: string, skillFiles: string[]): void {
  const offenders: string[] = []
  for (const skillMd of skillFiles) {
    const refsDir = path.join(path.dirname(skillMd), 'references')
    const scan = [skillMd, ...rglobMd(refsDir)]
    for (const file of scan) {
      readText(file)
        .split(/\r\n|\r|\n/)
        .forEach((line, idx) => {
          if (BARE_INVOCATION_RE.test(line)) {
            offenders.push(`${relPosix(root, file)}:${idx + 1}: ${line.trim().slice(0, 120)}`)
          }
        })
    }
  }
  if (offenders.length > 0) {
    fail(
      'NON-PORTABLE INVOCATION IN SKILL PROSE:\n  ' +
        offenders.join('\n  ') +
        '\n  Installed copies contain only the skill directory; resolve ' +
        'commands via <skill-base-dir>, a resolved variable, or a ' +
        'candidate cascade instead of a bare repo-relative path.',
    )
  }
  console.log(`ok: skill invocations portable (${skillFiles.length} skills)`)
}

/**
 * 技能必须相互独立、解耦：任何技能文件不得以文件路径引用其他技能的
 * SKILL.md（`skills/<name>/SKILL.md` 形态，由 SKILL_REF_RE 匹配）。
 * 需要协作时按名字提及技能，不引用文件。代码围栏内的示例不算违规
 * （可能是教学展示）。
 */
export function checkSkillIsolation(root: string, skillFiles: string[]): void {
  const offenders: string[] = []
  for (const skillMd of skillFiles) {
    const skillDir = path.dirname(skillMd)
    for (const file of rglobMd(skillDir)) {
      let inCode = false
      readText(file)
        .split(/\r\n|\r|\n/)
        .forEach((line, idx) => {
          if (line.trimStart().startsWith('```')) {
            inCode = !inCode
            return
          }
          if (inCode) return
          SKILL_REF_RE.lastIndex = 0
          let m: RegExpExecArray | null
          while ((m = SKILL_REF_RE.exec(line)) !== null) {
            offenders.push(`${relPosix(root, file)}:${idx + 1}: ${m[0]}`)
          }
        })
    }
  }
  if (offenders.length > 0) {
    fail(
      'CROSS-SKILL FILE REFERENCE: skills must stay independent and decoupled.\n  ' +
        offenders.join('\n  ') +
        '\n  Do not reference another skill by file path; mention it by name instead.',
    )
  }
  console.log(`ok: no cross-skill file references (${skillFiles.length} skills)`)
}

/**
 * 扫描 .sh / .json 中的 AI 署名泄漏。本模块自身持有黑名单故排除自身；
 * Markdown 不扫（规则文档可能合法引用这些字符串作为反面模式）。
 */
export function checkAttributionLeak(root: string): void {
  const selfPath = fileURLToPath(import.meta.url)
  for (const suffix of ['.sh', '.json']) {
    for (const file of walkFiles(root)) {
      if (!file.endsWith(suffix)) continue
      if (path.resolve(file) === selfPath) continue
      let text: string
      try {
        text = readText(file)
      } catch {
        continue
      }
      for (const pat of ATTRIBUTION_PATTERNS) {
        if (text.includes(pat)) {
          fail(`ATTRIBUTION LEAK: ${relPosix(root, file)} contains ${JSON.stringify(pat)}`)
        }
      }
    }
  }
  console.log('ok: no attribution leak')
}

/** 技能间触发词两两 Jaccard >= 0.5 视为撞车（一半以上关键词共享）。 */
export function checkTriggerOverlap(skillKeywords: Record<string, Set<string>>): void {
  const names = Object.keys(skillKeywords).sort()
  let foundOverlap = false
  for (let i = 0; i < names.length; i++) {
    for (const b of names.slice(i + 1)) {
      const a = names[i]
      const shared = new Set([...skillKeywords[a]].filter(kw => skillKeywords[b].has(kw)))
      const union = new Set([...skillKeywords[a], ...skillKeywords[b]])
      if (union.size === 0) continue
      const jaccard = shared.size / union.size
      if (jaccard >= 0.5) {
        console.error(
          `TRIGGER OVERLAP: ${a} vs ${b} jaccard=${jaccard.toFixed(2)} shared=${[...shared].sort().join(',')}`,
        )
        foundOverlap = true
      }
    }
  }
  if (foundOverlap) {
    fail('trigger keyword overlap above threshold')
  }
  console.log('ok: trigger keyword overlap below threshold')
}
