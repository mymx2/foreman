#!/usr/bin/env node
'use strict';

const fs = require('fs');
const path = require('path');
const crypto = require('crypto');

const EXIT_OK = 0;
const EXIT_FAIL = 1;
const EXIT_INPUT = 2;

function sha256File(filePath) {
  const fd = fs.openSync(filePath, 'r');
  const hash = crypto.createHash('sha256');
  const buffer = Buffer.alloc(1024 * 1024);
  try {
    let read;
    while ((read = fs.readSync(fd, buffer, 0, buffer.length, null)) > 0) {
      hash.update(buffer.subarray(0, read));
    }
  } finally {
    fs.closeSync(fd);
  }
  return hash.digest('hex');
}

function realOrResolved(filePath) {
  try {
    return fs.realpathSync(filePath);
  } catch {
    return path.resolve(filePath);
  }
}

function isInside(parent, child) {
  const rel = path.relative(parent, child);
  return rel !== '' && !rel.startsWith('..') && !path.isAbsolute(rel);
}

function normalizePath(p) {
  const resolved = path.resolve(p);
  return process.platform === 'win32' ? resolved.toLowerCase() : resolved;
}

function normalizeMapping(mapping) {
  const result = new Map();
  for (const [nodeId, value] of Object.entries(mapping || {})) {
    const filePath = typeof value === 'string' ? value : value && value.path;
    if (typeof filePath === 'string' && filePath) result.set(String(nodeId), filePath);
  }
  return result;
}

function verifyExportMapping(input, options = {}) {
  const issues = [];
  const add = (code, severity, message, extra = {}) => issues.push({ code, severity, message, ...extra });

  if (!input || typeof input !== 'object') {
    return { ok: false, issues: [{ code: 'INPUT_INVALID', severity: 'error', message: 'input must be an object' }], stats: {} };
  }

  const requested = input.requestedNodeIds || input.nodeIds;
  if (!Array.isArray(requested) || requested.length === 0) {
    add('MISSING_REQUESTED_IDS', 'error', 'requestedNodeIds must be a non-empty array');
  }

  if (!input.mapping || typeof input.mapping !== 'object' || Array.isArray(input.mapping)) {
    add('MAPPING_INVALID', 'error', 'mapping must be an object of nodeId -> path');
  } else {
    for (const [nodeId, value] of Object.entries(input.mapping)) {
      const filePath = typeof value === 'string' ? value : value && value.path;
      if (typeof filePath !== 'string' || !filePath) {
        add('MAPPING_ENTRY_INVALID', 'error', `mapping entry has no usable path`, { nodeId });
      }
    }
  }

  const mapping = normalizeMapping(input.mapping);
  const outDirRaw = options.outDir || input.outputDir;
  if (!outDirRaw) add('MISSING_OUT_DIR', 'error', 'outputDir or --out-dir is required');
  const outDir = outDirRaw ? path.resolve(outDirRaw) : null;

  const requestedSet = new Set((requested || []).map(String));
  const mappedSet = new Set(mapping.keys());

  for (const nodeId of requestedSet) {
    if (!mappedSet.has(nodeId)) add('MISSING_NODE', 'error', `no exported file for nodeId ${nodeId}`, { nodeId });
  }
  for (const nodeId of mappedSet) {
    if (!requestedSet.has(nodeId)) add('EXTRA_NODE', 'error', `mapping contains unrequested nodeId ${nodeId}`, { nodeId });
  }

  const seenPaths = new Map();
  const before = options.before || null;
  const beforeMap = new Map();
  if (before && typeof before === 'object') {
    for (const [key, value] of Object.entries(before)) {
      if (typeof value !== 'string' || !/^[0-9a-f]{64}$/i.test(value)) {
        add('BEFORE_INVALID', 'error', 'before entries must be SHA-256 hex strings', { path: key });
        continue;
      }
      beforeMap.set(normalizePath(realOrResolved(key)), value);
    }
  }
  let beforeMatched = 0;
  const outDirReal = outDir ? realOrResolved(outDir) : null;
  let checkedFiles = 0;

  for (const [nodeId, filePath] of mapping) {
    if (!outDir) break;
    const absolute = path.isAbsolute(filePath) ? path.resolve(filePath) : path.resolve(outDir, filePath);
    const realFile = realOrResolved(absolute);
    const normalized = normalizePath(realFile);

    if (!isInside(outDirReal, realFile)) {
      add('OUTSIDE_OUT_DIR', 'error', `file is outside outputDir: ${absolute}`, { nodeId, path: absolute });
      continue;
    }
    if (seenPaths.has(normalized)) {
      add('DUPLICATE_PATH', 'error', `multiple nodeIds map to ${absolute}`, {
        nodeId,
        path: absolute,
        otherNodeId: seenPaths.get(normalized)
      });
      continue;
    }
    seenPaths.set(normalized, nodeId);

    let stat;
    try {
      stat = fs.statSync(absolute);
    } catch (e) {
      add('MISSING_FILE', 'error', `file does not exist: ${absolute}`, { nodeId, path: absolute });
      continue;
    }
    if (!stat.isFile()) {
      add('NOT_A_FILE', 'error', `path is not a file: ${absolute}`, { nodeId, path: absolute });
      continue;
    }
    if (stat.size <= 0) {
      add('EMPTY_FILE', 'error', `file is empty: ${absolute}`, { nodeId, path: absolute });
      continue;
    }
    checkedFiles += 1;

    if (beforeMap.size) {
      const beforeHash = beforeMap.get(normalized);
      if (beforeHash) {
        beforeMatched += 1;
        if (beforeHash !== sha256File(realFile)) {
          add('CHANGED_FILE', 'error', `file changed during export: ${absolute}`, { nodeId, path: absolute });
        }
      } else if (options.requireBefore) {
        add('BEFORE_MISSING', 'error', `no baseline hash for ${absolute}`, { nodeId, path: absolute });
      }
    }
  }

  if (options.requireBefore && beforeMap.size === 0) {
    add('BEFORE_MISSING', 'error', '--require-before needs a non-empty --before snapshot');
  } else if (beforeMap.size && beforeMatched === 0) {
    add('BEFORE_UNMATCHED', options.requireBefore ? 'error' : 'warning',
      'none of the before keys matched an exported file; check the snapshot paths');
  }

  return {
    ok: !issues.some(i => i.severity === 'error'),
    stats: {
      requested: requestedSet.size,
      mapped: mappedSet.size,
      checkedFiles,
      beforeMatched
    },
    issues
  };
}

function parseArgs(argv) {
  const args = {};
  for (let i = 2; i < argv.length; i++) {
    const arg = argv[i];
    if (arg === '--help' || arg === '-h') args.help = true;
    else if (arg === '--json') args.json = true;
    else if (arg === '--require-before') args.requireBefore = true;
    else if (['--input', '--out-dir', '--before'].includes(arg)) args[arg.slice(2)] = argv[++i];
    else throw new Error(`unknown argument: ${arg}`);
  }
  return args;
}

function usage() {
  return [
    'Usage: node verify-export-mapping.js --input <mapping.json> --out-dir <dir> [--before <hashes.json>] [--require-before] [--json]',
    '',
    'Input:',
    '  { "requestedNodeIds": ["1:2"], "mapping": { "1:2": "a.png" }, "outputDir": "out" }',
    '  mapping values may also be { "path": "a.png" }.',
    '  --before is an optional { "<absolute path>": "<sha256>" } snapshot; mapped files must keep the same hash.'
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
  try {
    input = JSON.parse(fs.readFileSync(args.input, 'utf8'));
  } catch (e) {
    console.error(`cannot read input: ${e.message}`);
    process.exit(EXIT_INPUT);
  }
  let before = null;
  if (args.before) {
    try {
      before = JSON.parse(fs.readFileSync(args.before, 'utf8'));
    } catch (e) {
      console.error(`cannot read --before: ${e.message}`);
      process.exit(EXIT_INPUT);
    }
  }

  const result = verifyExportMapping(input, { outDir: args['out-dir'], before, requireBefore: args.requireBefore });
  if (args.json) console.log(JSON.stringify(result, null, 2));
  else {
    for (const issue of result.issues) console.log(`[${issue.severity}] ${issue.code}: ${issue.message}`);
    console.log(`requested=${result.stats.requested} mapped=${result.stats.mapped} files=${result.stats.checkedFiles} ok=${result.ok}`);
  }
  process.exit(result.ok ? EXIT_OK : EXIT_FAIL);
}

if (require.main === module) main();

module.exports = { verifyExportMapping, normalizeMapping, isInside };
