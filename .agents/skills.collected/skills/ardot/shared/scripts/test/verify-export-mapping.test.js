'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('fs');
const os = require('os');
const path = require('path');
const crypto = require('crypto');

const { verifyExportMapping } = require('../verify-export-mapping');

function tmpDir() {
  return fs.mkdtempSync(path.join(os.tmpdir(), 'ardot-export-'));
}

function writeFile(dir, name, content) {
  const p = path.join(dir, name);
  fs.mkdirSync(path.dirname(p), { recursive: true });
  fs.writeFileSync(p, content);
  return p;
}

function hash(p) {
  return crypto.createHash('sha256').update(fs.readFileSync(p)).digest('hex');
}

test('passes when every requested node has a non-empty file inside outputDir', () => {
  const dir = tmpDir();
  const a = writeFile(dir, 'a.png', 'a');
  const b = writeFile(dir, 'nested/b.png', 'b');
  const result = verifyExportMapping({
    requestedNodeIds: ['1:2', '1:3'],
    mapping: { '1:2': a, '1:3': b }
  }, { outDir: dir });
  assert.equal(result.ok, true);
  assert.equal(result.stats.requested, 2);
  assert.equal(result.stats.checkedFiles, 2);
});

test('reports missing and extra node ids', () => {
  const dir = tmpDir();
  const a = writeFile(dir, 'a.png', 'a');
  const result = verifyExportMapping({
    requestedNodeIds: ['1:2', '1:3'],
    mapping: { '1:2': a, '9:9': a }
  }, { outDir: dir });
  assert.equal(result.ok, false);
  assert.ok(result.issues.some(i => i.code === 'MISSING_NODE' && i.nodeId === '1:3'));
  assert.ok(result.issues.some(i => i.code === 'EXTRA_NODE' && i.nodeId === '9:9'));
});

test('reports missing, empty and outside files', () => {
  const dir = tmpDir();
  const empty = writeFile(dir, 'empty.png', '');
  const outside = writeFile(path.dirname(dir), `outside-${Date.now()}.png`, 'x');
  const result = verifyExportMapping({
    requestedNodeIds: ['1', '2', '3'],
    mapping: { '1': 'missing.png', '2': empty, '3': outside }
  }, { outDir: dir });
  assert.equal(result.ok, false);
  assert.ok(result.issues.some(i => i.code === 'MISSING_FILE'));
  assert.ok(result.issues.some(i => i.code === 'EMPTY_FILE'));
  assert.ok(result.issues.some(i => i.code === 'OUTSIDE_OUT_DIR'));
});

test('reports duplicate normalized paths and changed files', () => {
  const dir = tmpDir();
  const a = writeFile(dir, 'a.png', 'a');
  const before = { [a.replace(/\\/g, '/')]: hash(a) };
  fs.writeFileSync(a, 'changed');

  const duplicate = verifyExportMapping({
    requestedNodeIds: ['1', '2'],
    mapping: { '1': a, '2': a }
  }, { outDir: dir });
  assert.ok(duplicate.issues.some(i => i.code === 'DUPLICATE_PATH'));

  const changed = verifyExportMapping({
    requestedNodeIds: ['1'],
    mapping: { '1': a }
  }, { outDir: dir, before });
  assert.ok(changed.issues.some(i => i.code === 'CHANGED_FILE'));
});

test('requires a baseline hash for every file when --require-before is set', () => {
  const dir = tmpDir();
  const a = writeFile(dir, 'a.png', 'a');
  const before = { [path.join(dir, 'other.png')]: 'a'.repeat(64) };
  const result = verifyExportMapping({
    requestedNodeIds: ['1'],
    mapping: { '1': a }
  }, { outDir: dir, before, requireBefore: true });
  assert.equal(result.ok, false);
  assert.ok(result.issues.some(i => i.code === 'BEFORE_MISSING'));

  const noBaseline = verifyExportMapping({
    requestedNodeIds: ['1'],
    mapping: { '1': a }
  }, { outDir: dir, requireBefore: true });
  assert.equal(noBaseline.ok, false);
  assert.ok(noBaseline.issues.some(i => i.code === 'BEFORE_MISSING'));

  const emptyBaseline = verifyExportMapping({
    requestedNodeIds: ['1'],
    mapping: { '1': a }
  }, { outDir: dir, before: {}, requireBefore: true });
  assert.equal(emptyBaseline.ok, false);
  assert.ok(emptyBaseline.issues.some(i => i.code === 'BEFORE_MISSING'));

  const noIntersection = verifyExportMapping({
    requestedNodeIds: ['1'],
    mapping: { '1': a }
  }, { outDir: dir, before: { [path.join(dir, 'other.png')]: 'a'.repeat(64) }, requireBefore: true });
  assert.ok(noIntersection.issues.some(i => i.code === 'BEFORE_UNMATCHED' && i.severity === 'error'));
});

test('rejects paths that escape through a symlink', (t) => {
  const dir = tmpDir();
  const outsideDir = tmpDir();
  const outside = writeFile(outsideDir, 'outside.png', 'x');
  const link = path.join(dir, 'link');
  let linked = false;
  for (const type of ['junction', 'dir']) {
    try {
      fs.symlinkSync(outsideDir, link, type);
      linked = true;
      break;
    } catch {
      // try the next type
    }
  }
  if (!linked) {
    t.skip('symlink/junction not permitted on this platform');
    return;
  }
  const result = verifyExportMapping({
    requestedNodeIds: ['1'],
    mapping: { '1': path.join(link, path.basename(outside)) }
  }, { outDir: dir });
  assert.equal(result.ok, false);
  assert.ok(result.issues.some(i => i.code === 'OUTSIDE_OUT_DIR'));
});

test('reports invalid mapping entries', () => {
  const dir = tmpDir();
  const result = verifyExportMapping({
    requestedNodeIds: ['1'],
    mapping: { '1': { path: '' } }
  }, { outDir: dir });
  assert.equal(result.ok, false);
  assert.ok(result.issues.some(i => i.code === 'MAPPING_ENTRY_INVALID'));
});

test('treats empty requested list as invalid', () => {
  const dir = tmpDir();
  const result = verifyExportMapping({ requestedNodeIds: [], mapping: {} }, { outDir: dir });
  assert.equal(result.ok, false);
  assert.ok(result.issues.some(i => i.code === 'MISSING_REQUESTED_IDS'));
});
