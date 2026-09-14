#!/usr/bin/env node
/**
 * block-lookup.mjs — 影刀可视化指令目录查询。
 *
 * 服务端的 catalog 查询工具被禁用，本脚本直接读影刀安装目录下的
 * Copilot 知识库（block_catalog.md / block_detail.md）：
 *   search <关键词>         按关键词搜指令名和描述
 *   detail <prototype_name> 输出单条指令的完整字段契约
 *   list                    列出全部原型名
 *
 * 用法：node block-lookup.mjs search "写入文件"
 * 依赖：影刀 6.3+ 客户端已安装（自动探测安装目录，也可用 SHADOWBOT_HOME 覆盖）。
 * 零第三方依赖，Node 18+。
 */

import { existsSync, readFileSync, readdirSync } from 'node:fs'
import path from 'node:path'

const DEFAULT_ROOTS = ['D:\\Program Files\\ShadowBot', 'C:\\Program Files\\ShadowBot']

function findKnowledgeDir() {
  const roots = process.env.SHADOWBOT_HOME ? [process.env.SHADOWBOT_HOME] : DEFAULT_ROOTS
  for (const root of roots) {
    if (!existsSync(root)) continue
    const versions = readdirSync(root, { withFileTypes: true })
      .filter(e => e.isDirectory() && /^shadowbot-\d/.test(e.name))
      .map(e => e.name)
      .sort((a, b) => b.localeCompare(a, undefined, { numeric: true }))
    for (const v of versions) {
      const dir = path.join(root, v, 'Resources', 'Copilot', 'knowledge', 'visual-blocks')
      if (existsSync(path.join(dir, 'block_catalog.md'))) return dir
    }
  }
  return null
}

function loadCatalog(dir) {
  const lines = readFileSync(path.join(dir, 'block_catalog.md'), 'utf8').split(/\r?\n/)
  const entries = []
  for (const line of lines) {
    const idx = line.indexOf(' | ')
    if (idx === -1) continue
    entries.push({ name: line.slice(0, idx).trim(), desc: line.slice(idx + 3).trim() })
  }
  return entries
}

function loadDetails(dir) {
  const text = readFileSync(path.join(dir, 'block_detail.md'), 'utf8')
  const map = new Map()
  const re = /<([\w.]+)>(\{.*?\})<(?:<\/\1>|\1\/)>/gs
  let m
  while ((m = re.exec(text)) !== null) {
    map.set(m[1], m[2])
  }
  return map
}

const [cmd, arg] = process.argv.slice(2)
const dir = findKnowledgeDir()
if (!dir) {
  console.error('ERROR: 未找到影刀知识库。请确认已安装影刀 6.3+，或用 SHADOWBOT_HOME 指定安装根目录。')
  process.exit(1)
}

if (cmd === 'search') {
  const kw = (arg || '').toLowerCase()
  if (!kw) {
    console.error('usage: node block-lookup.mjs search <keyword>')
    process.exit(1)
  }
  for (const e of loadCatalog(dir)) {
    if (e.name.toLowerCase().includes(kw) || e.desc.toLowerCase().includes(kw)) {
      console.log(`${e.name}\t${e.desc}`)
    }
  }
} else if (cmd === 'detail') {
  if (!arg) {
    console.error('usage: node block-lookup.mjs detail <prototype_name>')
    process.exit(1)
  }
  const detail = loadDetails(dir).get(arg)
  if (!detail) {
    console.error(`NOT FOUND: ${arg}（用 search 确认原型名）`)
    process.exit(1)
  }
  console.log(JSON.stringify(JSON.parse(detail), null, 2))
} else if (cmd === 'list') {
  for (const e of loadCatalog(dir)) console.log(`${e.name}\t${e.desc}`)
} else {
  console.error('usage: node block-lookup.mjs search <kw> | detail <name> | list')
  process.exit(1)
}
