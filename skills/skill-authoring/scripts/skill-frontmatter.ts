/**
 * skill-frontmatter.ts — 技能 SKILL.md frontmatter 的唯一解析入口。
 *
 * 所有需要技能元数据的脚本都通过本模块读取 frontmatter，而不是各自
 * 解析 YAML，使字段契约与非法字段黑名单保持单一事实源。
 *
 * 契约：
 *   - 顶层标量字段：name / description / when_to_use
 *   - description 支持 YAML 块标量（`>` 折叠 / `|` 字面）
 *   - dispatch_intent 不属于契约：出现时显式拒绝，让错误原因一目了然
 *   - 其他字段（license、metadata、triggers、tip 等）及任意缩进内容
 *     静默忽略，不校验
 *   - 解析失败统一走 fail() 抛出 FailError（调用方捕获后转 stderr + exit 1）
 *
 * 零第三方依赖（仅 node:fs），首次运行无需安装任何东西。
 */

import { readFileSync } from 'node:fs'

// ── 契约常量：认可什么字段、拒绝什么字段、按什么格式切分，改契约只动这一块 ──

/**
 * 技能目录所在段名（相对技能树根）。全部校验/生成脚本通过它拼技能路径，
 * 是布局的唯一接缝：技能树根下技能目录都在这一段里。
 */
export const SKILLS_DIR = 'skills'

/** 匹配 `skills/<name>/SKILL.md` 形式的技能文件引用（跨技能耦合检验）。 */
export const SKILL_REF_RE = new RegExp(`${SKILLS_DIR}/([a-z][a-z0-9_-]*)/SKILL\\.md`, 'g')

/** frontmatter 块的起止分隔线。 */
const DELIMITER = '---'

/** 三种换行都接受：\n / \r\n / \r */
const LINE_SPLIT_RE = /\r\n|\r|\n/

/** 合法的顶层标量字段；其余顶层键静默忽略。 */
const KNOWN_FIELDS = ['name', 'description', 'when_to_use'] as const
type KnownField = (typeof KNOWN_FIELDS)[number]

/** 不属于契约、出现时显式拒绝的顶层字段（报错文案按字段名自动生成）。 */
const STALE_TOP_LEVEL_FIELDS = new Set(['dispatch_intent'])

function isKnownField(key: string): key is KnownField {
  return (KNOWN_FIELDS as readonly string[]).includes(key)
}

/** 解析后的 frontmatter 字段集。when_to_use 缺省时为空串。 */
export interface FrontmatterFields {
  name: string
  description: string
  when_to_use: string
}

/**
 * 契约违例错误。命令行入口应捕获它并转成"stderr 输出 + exit 1"；
 * 测试可直接断言其 message。库代码一律抛出而不是自行退出进程，
 * 否则会把宿主进程（如测试运行器）一起带走。
 */
export class FailError extends Error {
  constructor(message: string) {
    super(message)
    this.name = 'FailError'
  }
}

/**
 * 统一失败出口：抛出 FailError，所有校验脚本共享同一失败模式。
 */
export function fail(message: string): never {
  throw new FailError(message)
}

/**
 * 扫描文本中的技能文件引用，与期望技能集对比。
 * 返回 [missing, stale]：期望但没被引用的技能、被引用但不存在的技能。
 * 技能相互独立解耦，引用出现即违规；本函数供检验调用方判定报错。
 */
export function skillRefDiff(text: string, expected: ReadonlySet<string>): [string[], string[]] {
  const referenced = new Set<string>()
  // 正则带 g 标志，逐次 exec 收集全部引用；每次调用重置 lastIndex 避免跨调用串扰
  SKILL_REF_RE.lastIndex = 0
  let match: RegExpExecArray | null
  while ((match = SKILL_REF_RE.exec(text)) !== null) {
    referenced.add(match[1])
  }
  const missing = [...expected].filter(name => !referenced.has(name)).sort()
  const stale = [...referenced].filter(name => !expected.has(name)).sort()
  return [missing, stale]
}

/**
 * 解析单个标量值。frontmatter 的值约定为简单字符串：
 * 双引号按 JSON 字符串解析（覆盖 \n \" \\ 等转义）；
 * 单引号做最小化处理（仅 \\ 和 \' 转义）。
 */
function parseScalar(path: string, field: string, raw: string): string {
  const value = raw.trim()
  if (!value) {
    fail(`EMPTY FRONTMATTER VALUE: ${path} field ${field}`)
  }
  const quote = value[0]
  if (quote === '"' || quote === "'") {
    if (quote === '"') {
      try {
        const parsed: unknown = JSON.parse(value)
        if (typeof parsed !== 'string') {
          fail(`INVALID FRONTMATTER VALUE: ${path} field ${field} must be a string`)
        }
        return parsed
      } catch (exc) {
        const reason = exc instanceof Error ? exc.message : String(exc)
        fail(`INVALID FRONTMATTER QUOTE: ${path} field ${field}: ${reason}`)
      }
    }
    // 单引号路径：必须有配对收尾，再还原最小转义集
    if (value.length < 2 || !value.endsWith("'")) {
      fail(`INVALID FRONTMATTER QUOTE: ${path} field ${field}: unterminated string`)
    }
    return value.slice(1, -1).replace(/\\([\\'])/g, '$1')
  }
  // 未加引号的值里出现 ": " 会让 key/value 边界产生歧义，契约要求加引号
  if (value.includes(': ')) {
    fail(
      `UNQUOTED FRONTMATTER COLON: ${path} field ${field}\n` +
        `  Quote values containing ': ' so the metadata contract stays unambiguous.`,
    )
  }
  return value
}

/**
 * 解析 SKILL.md 的 frontmatter 块（文件首行 --- 到下一个 --- 之间）。
 * 任何契约违例都直接 fail()，调用方拿到的必然是合法结果。
 */
export function parseFrontmatter(path: string): FrontmatterFields {
  const text = readFileSync(path, 'utf8')
  const lines = text.split(LINE_SPLIT_RE)
  if (lines.length === 0 || lines[0] !== DELIMITER) {
    fail(`INVALID FRONTMATTER: ${path} must start with ---`)
  }
  const end = lines.indexOf(DELIMITER, 1)
  if (end === -1) {
    fail(`INVALID FRONTMATTER: ${path} missing closing ---`)
  }

  const fields: Partial<Record<KnownField, string>> = {}
  const bodyLines = lines.slice(1, end)

  for (let i = 0; i < bodyLines.length; i++) {
    const rawLine = bodyLines[i]
    if (!rawLine.trim()) continue

    // 缩进内容（列表项、嵌套映射等）不属于契约字段，静默忽略
    if (rawLine.startsWith('  ')) continue

    // 块标量：`key: >` 折叠 / `key: |` 字面（含 -/+ 修饰），值在后续缩进行
    const block = rawLine.match(/^([A-Za-z_][A-Za-z0-9_-]*):\s*(>[+-]?|\|[+-]?)\s*$/)
    if (block) {
      const key = block[1]
      const style = block[2]
      const parts: string[] = []
      while (i + 1 < bodyLines.length && bodyLines[i + 1].startsWith('  ')) {
        const next = bodyLines[++i].trim()
        if (next) parts.push(next)
      }
      const value = style.startsWith('>') ? parts.join(' ') : parts.join('\n')
      if (isKnownField(key)) {
        fields[key] = value
      }
      // 未知键的块标量静默忽略
      continue
    }

    const idx = rawLine.indexOf(':')
    if (idx === -1) {
      fail(`INVALID FRONTMATTER LINE: ${path}: ${JSON.stringify(rawLine)}`)
    }
    const key = rawLine.slice(0, idx)
    const rawValue = rawLine.slice(idx + 1)

    if (STALE_TOP_LEVEL_FIELDS.has(key)) {
      // 不属于契约的字段：显式拒绝，让错误原因一目了然
      fail(
        `STALE ${key}: ${path} still declares ${key}. ` +
          `The field is not part of the frontmatter contract; delete it.`,
      )
    } else if (isKnownField(key)) {
      fields[key] = parseScalar(path, key, rawValue)
    }
    // 其他顶层键（license、metadata、triggers 等）静默忽略
  }

  const name = fields.name
  const description = fields.description
  const whenToUse = fields.when_to_use ?? ''

  if (!name || !name.trim()) {
    fail(`MISSING name: in ${path}`)
  }
  if (!description || !description.trim()) {
    fail(`MISSING description: in ${path}`)
  }

  return {
    name: name.trim(),
    description: description.trim(),
    when_to_use: whenToUse.trim(),
  }
}

/** 把 when_to_use 逗号串拆成小写去重触发词集合。 */
export function parseWhenToUseKeywords(whenToUse: string): Set<string> {
  return new Set(
    whenToUse
      .split(',')
      .map(kw => kw.trim().toLowerCase())
      .filter(kw => kw.length > 0),
  )
}
