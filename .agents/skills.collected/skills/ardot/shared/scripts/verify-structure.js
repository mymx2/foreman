#!/usr/bin/env node
'use strict';

const fs = require('fs');

const EXIT_OK = 0;
const EXIT_FAIL = 1;
const EXIT_INPUT = 2;

const DEFAULT_NAMES = [
  /^(Frame|Layer|Group|Page|Rectangle|Ellipse|Component( Set)?|Vector|Text|Star|Line|Section|Image|Shape)\s*\d+$/i,
  /^(Untitled|未命名)$/i,
  /^[\d\s._-]+$/,
  /^\d+:\d+$/,
  /(copy|副本|拷贝)$/i
];

function isDefaultName(name) {
  return DEFAULT_NAMES.some(re => re.test(String(name || '').trim()));
}

function normalizeAllowlist(allowlist) {
  if (!allowlist) return { entries: [], provided: false, malformed: false };
  if (Array.isArray(allowlist)) return { entries: allowlist, provided: true, malformed: false };
  if (Array.isArray(allowlist.entries)) return { entries: allowlist.entries, provided: true, malformed: false };
  return { entries: [], provided: true, malformed: true };
}

function isValidDate(value) {
  if (typeof value !== 'string' || !/^\d{4}-\d{2}-\d{2}$/.test(value)) return false;
  const parsed = new Date(`${value}T00:00:00Z`);
  return !Number.isNaN(parsed.getTime()) && parsed.toISOString().slice(0, 10) === value;
}

function validateAllowlist(entries) {
  const valid = [];
  const invalid = [];
  for (const entry of entries) {
    if (!entry || typeof entry !== 'object') { invalid.push({ entry, reason: 'entry is not an object' }); continue; }
    const codes = entry.codes || (entry.code ? [entry.code] : []);
    if (!entry.key || !Array.isArray(codes) || codes.length === 0) {
      invalid.push({ entry, reason: 'key and non-empty codes are required' });
      continue;
    }
    if (!entry.scope) { invalid.push({ entry, reason: 'scope is required' }); continue; }
    if (!entry.owner || !entry.reason) { invalid.push({ entry, reason: 'owner and reason are required' }); continue; }
    if (!isValidDate(entry.expires)) { invalid.push({ entry, reason: 'expires must be a real YYYY-MM-DD date' }); continue; }
    if (!isValidDate(entry.added_at)) { invalid.push({ entry, reason: 'added_at must be a real YYYY-MM-DD date' }); continue; }
    if (entry.added_at > entry.expires) { invalid.push({ entry, reason: 'added_at must not be after expires' }); continue; }
    valid.push({ ...entry, codes });
  }
  return { valid, invalid };
}

function allowlistMatch(entries, key, code, today, scope) {
  let expired = null;
  for (const entry of entries) {
    if (entry.key !== key) continue;
    if (scope ? (entry.scope !== 'all' && entry.scope !== scope) : entry.scope !== 'all') continue;
    if (!entry.codes.includes(code)) continue;
    if (entry.expires < today) {
      expired = entry;
      continue;
    }
    return { entry, expired: null };
  }
  return { entry: null, expired };
}

function verifyStructure(input, options = {}) {
  const issues = [];
  const add = (code, severity, message, extra = {}) => issues.push({ code, severity, message, ...extra });

  let nodes;
  let omitted = [];
  let allowlistRaw = options.allowlist || null;
  let omittedInvalid = false;

  if (Array.isArray(input)) nodes = input;
  else if (input && typeof input === 'object') {
    nodes = input.nodes || input.tree;
    if (input.omitted !== undefined && !Array.isArray(input.omitted)) omittedInvalid = true;
    else if (Array.isArray(input.omitted)) omitted = input.omitted;
    // allowlist is accepted only from the explicit option / CLI flag, never from the inspected payload.
  }

  if (!Array.isArray(nodes)) {
    return { ok: false, issues: [{ code: 'INPUT_INVALID', severity: 'error', message: 'input must be an array or { nodes: [...] }' }], stats: {} };
  }
  if (nodes.length === 0) {
    add('EMPTY_TREE', 'error', 'no nodes were read; treat as not executed');
  }
  if (omittedInvalid) {
    add('INPUT_INVALID', 'error', 'omitted must be an array when present');
  }
  if (omitted.length > 0) {
    add('INCOMPLETE_READ', 'error', `batch_read omitted ${omitted.length} parent nodes; re-read them before checking`, { omitted });
  }

  const maxDepth = Number.isFinite(options.maxDepth) ? options.maxDepth : 5;
  const maxChildren = Number.isFinite(options.maxChildren) ? options.maxChildren : 30;
  const scope = options.scope || null;
  const normalizedAllowlist = normalizeAllowlist(allowlistRaw);
  if (normalizedAllowlist.malformed) {
    add('ALLOWLIST_INVALID', 'error', 'allowlist must be an array or { entries: [] }');
  }
  const { valid: entries, invalid } = validateAllowlist(normalizedAllowlist.entries);
  for (const item of invalid) {
    add('ALLOWLIST_INVALID', 'error', item.reason, { entry: item.entry });
  }
  const today = new Date().toISOString().slice(0, 10);
  let visited = 0;

  function walk(list, parentPath, depth, parentType) {
    for (const node of list) {
      if (!node || typeof node !== 'object') {
        add('INVALID_NODE', 'error', 'node is not an object', { parent: parentPath || '<root>' });
        continue;
      }
      visited += 1;
      const name = String(node.name || '').trim();
      const nodePath = parentPath ? `${parentPath}/${name || '<unnamed>'}` : (name || '<unnamed>');
      const type = String(node.type || '').toUpperCase();

      if (!name) add('EMPTY_NAME', 'error', 'node has no name', { path: nodePath, nodeId: node.id });
      else if (isDefaultName(name)) add('DEFAULT_NAME', 'error', `forbidden default/placeholder name: ${name}`, { path: nodePath, nodeId: node.id });

      if (depth > maxDepth) {
        add('DEPTH_EXCEEDED', 'error', `depth ${depth} exceeds ${maxDepth}`, { path: nodePath, nodeId: node.id });
        continue;
      }

      if (parentPath === '' && type === 'TEXT') {
        add('TEXT_AT_ROOT', 'warning', 'text node is a direct child of the page; confirm this is intentional', { path: nodePath, nodeId: node.id });
      }

      if (node.children === '...' || (node.children !== undefined && node.children !== null && !Array.isArray(node.children))) {
        add('TRUNCATED_TREE', 'error', 'children were compressed; re-read with a deeper readDepth before checking', { path: nodePath, nodeId: node.id });
        continue;
      }

      const children = Array.isArray(node.children) ? node.children : [];
      if (children.length > maxChildren) {
        add('TOO_MANY_CHILDREN', 'warning', `${children.length} children exceeds soft limit ${maxChildren}`, { path: nodePath, nodeId: node.id });
      }
      if (depth > 1 && children.length === 1 && type === 'FRAME') {
        const hit = allowlistMatch(entries, nodePath, 'SINGLE_CHILD_FRAME', today, scope);
        if (hit.expired) {
          add('ALLOWLIST_EXPIRED', 'error', `allowlist entry expired for single-child frame`, { path: nodePath, nodeId: node.id, entry: hit.expired });
        } else if (!hit.entry) {
          add('SINGLE_CHILD_FRAME', 'warning', 'single-child frame is not in allowlist; confirm it is a legitimate wrapper', { path: nodePath, nodeId: node.id });
        }
      }

      if (children.length) walk(children, nodePath, depth + 1, type);
    }
  }

  walk(nodes, '', 1, null);
  if (visited === 0 && nodes.length > 0) {
    add('EMPTY_TREE', 'error', 'no valid nodes were read; treat as not executed');
  }

  return {
    ok: !issues.some(i => i.severity === 'error'),
    stats: { nodes: visited, errors: issues.filter(i => i.severity === 'error').length, warnings: issues.filter(i => i.severity === 'warning').length },
    issues
  };
}

function parseArgs(argv) {
  const args = {};
  for (let i = 2; i < argv.length; i++) {
    const arg = argv[i];
    if (arg === '--help' || arg === '-h') args.help = true;
    else if (arg === '--json') args.json = true;
    else if (['--input', '--allowlist'].includes(arg)) args[arg.slice(2)] = argv[++i];
    else if (['--max-depth', '--max-children'].includes(arg)) args[arg.slice(2)] = Number(argv[++i]);
    else if (arg === '--scope') args.scope = argv[++i];
    else throw new Error(`unknown argument: ${arg}`);
  }
  return args;
}

function usage() {
  return [
    'Usage: node verify-structure.js --input <batch-read.json> [--allowlist <allowlist.json>] [--scope <module>] [--max-depth 5] [--max-children 30] [--json]',
    '',
    'Input: batch_read result (array) or { nodes: [...], omitted: [...] }.',
    'Allowlist: { entries: [{ scope, codes, key, owner, reason, added_at, expires }] }.'
  ].join('\n');
}

function main() {
  let args;
  try {
    args = parseArgs(process.argv);
  } catch (e) {
    console.error(e.message);
    console.error(usage());
    process.exit(EXIT_INPUT);
  }
  if (args.help) {
    console.log(usage());
    return;
  }
  if (!args.input) {
    console.error('--input is required');
    console.error(usage());
    process.exit(EXIT_INPUT);
  }

  let input;
  let allowlist = null;
  try {
    input = JSON.parse(fs.readFileSync(args.input, 'utf8'));
    if (args.allowlist) allowlist = JSON.parse(fs.readFileSync(args.allowlist, 'utf8'));
  } catch (e) {
    console.error(`cannot read input: ${e.message}`);
    process.exit(EXIT_INPUT);
  }

  const result = verifyStructure(input, {
    allowlist,
    scope: args.scope,
    maxDepth: args['max-depth'],
    maxChildren: args['max-children']
  });

  if (args.json) console.log(JSON.stringify(result, null, 2));
  else {
    for (const issue of result.issues) console.log(`[${issue.severity}] ${issue.code}: ${issue.message}`);
    console.log(`nodes=${result.stats.nodes} errors=${result.stats.errors} warnings=${result.stats.warnings} ok=${result.ok}`);
  }
  process.exit(result.ok ? EXIT_OK : EXIT_FAIL);
}

if (require.main === module) main();

module.exports = { verifyStructure, isDefaultName };
