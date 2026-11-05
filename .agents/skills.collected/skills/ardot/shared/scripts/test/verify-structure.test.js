'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');

const { verifyStructure, isDefaultName } = require('../verify-structure');

function frame(name, children = []) {
  return { id: name, type: 'FRAME', name, children };
}

test('passes a clean tree', () => {
  const tree = [frame('Page', [frame('Section', [frame('Card', [{ id: 't', type: 'TEXT', name: 'Title' }])])])];
  const result = verifyStructure(tree);
  assert.equal(result.ok, true);
  assert.equal(result.stats.nodes, 4);
});

test('fails empty tree and incomplete reads', () => {
  assert.ok(verifyStructure([]).issues.some(i => i.code === 'EMPTY_TREE'));
  assert.ok(verifyStructure({ nodes: [frame('Page')], omitted: ['1:2'] }).issues.some(i => i.code === 'INCOMPLETE_READ'));
});

test('flags default and placeholder names', () => {
  assert.equal(isDefaultName('Frame 12'), true);
  assert.equal(isDefaultName('Frame One'), false);
  assert.equal(isDefaultName('Untitled'), true);
  assert.equal(isDefaultName('123'), true);
  assert.equal(isDefaultName('Product Card'), false);

  const result = verifyStructure([frame('Frame 12')]);
  assert.ok(result.issues.some(i => i.code === 'DEFAULT_NAME'));
});

test('reports single-child frames as warnings and allows suppression', () => {
  const tree = [frame('Page', [frame('Avatar Wrapper', [frame('Image')])])];
  const flagged = verifyStructure(tree);
  assert.ok(flagged.issues.some(i => i.code === 'SINGLE_CHILD_FRAME' && i.path === 'Page/Avatar Wrapper'));
  assert.equal(flagged.ok, true);

  const allowed = verifyStructure(tree, {
    allowlist: { entries: [{ scope: 'all', codes: ['SINGLE_CHILD_FRAME'], key: 'Page/Avatar Wrapper', owner: 'design', reason: 'avatar', added_at: '2026-11-05', expires: '2999-01-01' }] }
  });
  assert.equal(allowed.issues.some(i => i.code === 'SINGLE_CHILD_FRAME'), false);
});

test('fails expired and malformed allowlist entries', () => {
  const tree = [frame('Page', [frame('Avatar Wrapper', [frame('Image')])])];
  const expired = verifyStructure(tree, {
    allowlist: { entries: [{ scope: 'all', codes: ['SINGLE_CHILD_FRAME'], key: 'Page/Avatar Wrapper', owner: 'design', reason: 'avatar', added_at: '1999-01-01', expires: '2000-01-01' }] }
  });
  assert.ok(expired.issues.some(i => i.code === 'ALLOWLIST_EXPIRED'));

  const missingExpiry = verifyStructure(tree, {
    allowlist: { entries: [{ scope: 'all', codes: ['SINGLE_CHILD_FRAME'], key: 'Page/Avatar Wrapper', owner: 'design', reason: 'avatar', added_at: '2026-11-05' }] }
  });
  assert.ok(missingExpiry.issues.some(i => i.code === 'ALLOWLIST_INVALID'));

  const malformed = verifyStructure(tree, { allowlist: { entry: [] } });
  assert.ok(malformed.issues.some(i => i.code === 'ALLOWLIST_INVALID'));
});

test('filters allowlist entries by scope and requires scope when omitted', () => {
  const tree = [frame('Page', [frame('Avatar Wrapper', [frame('Image')])])];
  const entry = { scope: 'showcase', codes: ['SINGLE_CHILD_FRAME'], key: 'Page/Avatar Wrapper', owner: 'design', reason: 'avatar', added_at: '2026-11-05', expires: '2999-01-01' };

  const scoped = verifyStructure(tree, { scope: 'ui-design', allowlist: { entries: [entry] } });
  assert.ok(scoped.issues.some(i => i.code === 'SINGLE_CHILD_FRAME'));

  const unscoped = verifyStructure(tree, { allowlist: { entries: [entry] } });
  assert.ok(unscoped.issues.some(i => i.code === 'SINGLE_CHILD_FRAME'));
});

test('rejects malformed omitted and node entries', () => {
  assert.ok(verifyStructure({ nodes: [frame('Page')], omitted: '1:2' }).issues.some(i => i.code === 'INPUT_INVALID'));
  const invalid = verifyStructure(['Page']);
  assert.ok(invalid.issues.some(i => i.code === 'INVALID_NODE'));
  assert.ok(invalid.issues.some(i => i.code === 'EMPTY_TREE'));
});

test('flags depth and truncated children', () => {
  let node = frame('Leaf');
  for (let i = 0; i < 6; i++) node = frame(`Level ${i}`, [node]);
  assert.ok(verifyStructure([node], { maxDepth: 5 }).issues.some(i => i.code === 'DEPTH_EXCEEDED'));

  const truncated = [{ id: '1', type: 'FRAME', name: 'Page', children: '...' }];
  assert.ok(verifyStructure(truncated).issues.some(i => i.code === 'TRUNCATED_TREE'));
});
