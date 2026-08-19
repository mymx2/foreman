/**
 * markdown-fragments.ts — 按 GitHub 渲染规则计算 Markdown 标题锚点（fragment）。
 *
 * 用途：校验 `[文字](#some-heading)` 这类页内跳转是否指向真实存在的锚点。
 * 标题到锚点不是简单小写化——需要先剥掉行内标记（链接 / code / HTML 标签 /
 * 自动链接），做 HTML 实体反转义，小写，去掉标点（保留中日韩等字母），
 * 空格转 `-`，重名标题再追加 -1 / -2 后缀。本模块把这套规则实现成唯一事实源，
 * 让锚点判断与 GitHub 实际渲染一致。
 *
 * 零第三方依赖，输入一段 Markdown 文本即可使用，与具体项目无关。
 */

// ── 规则常量：标题识别、行内标记、slug 字符集、实体表，四组一眼看全 ──

// 标题与块结构的行级匹配
const ATX_HEADING_RE = /^ {0,3}#{1,6}\s+(.+?)\s*#*\s*$/
const SETEXT_RE = /^ {0,3}(?:=+|-+)\s*$/
const FENCE_RE = /^ {0,3}(`{3,}|~{3})(.*)$/
const BLOCKQUOTE_RE = /^ {0,3}> ?/

// 行内标记：渲染为纯文本时分别保留可见文字或整体剥除
const INLINE_LINK_RE = /!?\[([^\]]*)\]\([^)]*\)/g
const REFERENCE_LINK_RE = /!?\[([^\]]*)\]\[[^\]]*\]/g
const CODE_SPAN_RE = /`+([^`]+?)`+/g
const AUTOLINK_RE = /<((?:https?:\/\/|mailto:)[^ >]+|[^ <>@]+@[^ <>]+)>/gi
const HTML_TAG_RE = /<[^>]+>/g

// GitHub slug（对齐 github-slugger）：小写后删除标点（\p{P}，排除 _ 连字符连接号）、
// 符号（\p{S}，emoji 等）与控制字符；保留字母/数字/组合标记/格式字符
// （\p{Cf}，如 emoji 变体选择符 U+FE0F —— GitHub 锚点里会保留它）。
// eslint-disable-next-line no-control-regex
const NON_SLUG_CHAR_RE = /(?![-_])[\p{P}\p{S}\u0000-\u001F\u007F]/gu
const WHITESPACE_RE = /\s/g

// 常用命名实体表 + 数字实体，覆盖文档中实际出现的写法
const NAMED_ENTITIES: Record<string, string> = {
  amp: '&',
  lt: '<',
  gt: '>',
  quot: '"',
  apos: "'",
  nbsp: ' ',
}
const ENTITY_RE = /&(#x[0-9a-fA-F]+|#\d+|[a-zA-Z]+);/g

/** 还原 HTML 实体：数字实体按码点解码，命名实体查表，未知名称原样保留。 */
function unescapeEntities(text: string): string {
  return text.replace(ENTITY_RE, (whole, body: string) => {
    if (body.startsWith('#x') || body.startsWith('#X')) {
      return String.fromCodePoint(parseInt(body.slice(2), 16))
    }
    if (body.startsWith('#')) {
      return String.fromCodePoint(parseInt(body.slice(1), 10))
    }
    return NAMED_ENTITIES[body] ?? whole
  })
}

/** 近似 GitHub 生成锚点前使用的渲染文本：剥行内标记、反转义实体。 */
function renderedHeadingText(source: string): string {
  let text = source
  text = text.replace(INLINE_LINK_RE, '$1')
  text = text.replace(REFERENCE_LINK_RE, '$1')
  text = text.replace(CODE_SPAN_RE, '$1')
  text = text.replace(AUTOLINK_RE, '$1')
  text = text.replace(HTML_TAG_RE, '')
  return unescapeEntities(text)
}

/** 单个标题文本 → 基础锚点（不含重名后缀）。空结果表示不产生锚点。 */
function baseFragment(source: string): string {
  const rendered = renderedHeadingText(source).toLowerCase().trim()
  return rendered.replace(NON_SLUG_CHAR_RE, '').replace(WHITESPACE_RE, '-')
}

interface HeadingSource {
  text: string
  line: number
}

/**
 * 逐行扫描，提取"真标题"。必须跳过：
 * 代码围栏（含嵌套：收尾围栏需同字符、长度 >= 开围栏、且无 info string）、
 * 四空格缩进代码块、块引用层级边界（引用深度变化即新段落）。
 * 否则代码示例里的 `# comment` 会被误判成标题，锚点清单就失真。
 */
function headingSources(markdown: string): HeadingSource[] {
  const sources: HeadingSource[] = []
  let paragraph: HeadingSource[] = []
  let paragraphQuoteDepth = 0
  let fenceChar = ''
  let fenceLength = 0
  let fenceQuoteDepth = 0

  const lines = markdown.split(/\r\n|\r|\n/)
  for (let lineNumber = 1; lineNumber <= lines.length; lineNumber++) {
    let line = lines[lineNumber - 1]

    // 先剥块引用前缀，记录引用深度
    let quoteDepth = 0
    let quote: RegExpMatchArray | null
    while ((quote = line.match(BLOCKQUOTE_RE)) !== null) {
      quoteDepth++
      line = line.slice(quote[0].length)
    }

    const fence = line.match(FENCE_RE)
    if (fenceChar) {
      // 围栏内部：只认合法的收尾围栏，其余内容一概忽略
      if (fence) {
        const marker = fence[1]
        if (
          quoteDepth === fenceQuoteDepth &&
          marker[0] === fenceChar &&
          marker.length >= fenceLength &&
          !fence[2].trim()
        ) {
          fenceChar = ''
          fenceLength = 0
          fenceQuoteDepth = 0
        }
      }
      paragraph = []
      continue
    }
    if (fence) {
      const marker = fence[1]
      fenceChar = marker[0]
      fenceLength = marker.length
      fenceQuoteDepth = quoteDepth
      paragraph = []
      continue
    }
    // 四空格缩进代码块
    if (line.startsWith('    ')) {
      paragraph = []
      continue
    }

    const atx = line.match(ATX_HEADING_RE)
    if (atx) {
      sources.push({ text: atx[1], line: lineNumber })
      paragraph = []
      continue
    }

    // Setext 标题：`===`/`---` 下划线 + 紧邻其上、同引用深度的段落
    if (SETEXT_RE.test(line) && paragraph.length > 0 && quoteDepth === paragraphQuoteDepth) {
      sources.push({
        text: paragraph.map(part => part.text.trim()).join(''),
        line: paragraph[0].line,
      })
      paragraph = []
      continue
    }

    if (!line.trim()) {
      paragraph = []
      continue
    }
    if (paragraph.length > 0 && quoteDepth !== paragraphQuoteDepth) {
      paragraph = []
    }
    if (paragraph.length === 0) {
      paragraphQuoteDepth = quoteDepth
    }
    paragraph.push({ text: line, line: lineNumber })
  }

  return sources
}

/**
 * 返回全部标题的锚点记录（含重名加 -1 后缀的碰撞处理）与来源行号。
 * 锚点为空的标题（纯标点标题）不产生记录。
 */
export function githubHeadingRecords(markdown: string): Array<[string, number]> {
  const records: Array<[string, number]> = []
  const anchors = new Set<string>()
  for (const { text, line } of headingSources(markdown)) {
    const base = baseFragment(text)
    if (!base) continue
    let anchor = base
    let suffix = 1
    while (anchors.has(anchor)) {
      anchor = `${base}-${suffix}`
      suffix++
    }
    anchors.add(anchor)
    records.push([anchor, line])
  }
  return records
}

export interface HeadingInventory {
  /** 碰撞处理后的全部有效锚点 */
  anchors: Set<string>
  /** 每个基础锚点出现的次数（用于判断 `#foo-1` 这类后缀锚点是否真实存在） */
  baseCounts: Map<string, number>
}

/** 一次性返回渲染锚点集合与碰撞前 base 计数。 */
export function githubHeadingInventory(markdown: string): HeadingInventory {
  const baseCounts = new Map<string, number>()
  for (const { text } of headingSources(markdown)) {
    const base = baseFragment(text)
    if (!base) continue
    baseCounts.set(base, (baseCounts.get(base) ?? 0) + 1)
  }
  const anchors = new Set(githubHeadingRecords(markdown).map(([anchor]) => anchor))
  return { anchors, baseCounts }
}
