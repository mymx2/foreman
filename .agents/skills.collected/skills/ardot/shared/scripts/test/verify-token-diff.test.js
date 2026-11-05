'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');

const { verifyTokenDiff, normalizeSnapshot, hasKnownShape } = require('../verify-token-diff');

test('passes new kebab variables in an existing set', () => {
  const result = verifyTokenDiff({
    before: { sets: [{ name: 'Semantic', variables: [{ name: 'text-primary', type: 'COLOR' }] }] },
    after: { sets: [{ name: 'Semantic', variables: [{ name: 'text-primary', type: 'COLOR' }, { name: 'bg-surface', type: 'COLOR' }] }] }
  });
  assert.equal(result.ok, true);
  assert.equal(result.stats.addedVars, 1);
});

test('flags non-kebab new variables and empty snapshots', () => {
  const result = verifyTokenDiff({
    before: { sets: [] },
    after: { sets: [{ name: 'Component', variables: [{ name: 'ButtonBg', type: 'COLOR' }] }] }
  });
  assert.equal(result.ok, false);
  assert.ok(result.issues.some(i => i.code === 'NEW_VAR_NAME'));

  const empty = verifyTokenDiff({ before: {}, after: {} });
  assert.ok(empty.issues.some(i => i.code === 'EMPTY_SNAPSHOT'));
});

test('warns on new set names outside the preferred list', () => {
  const result = verifyTokenDiff({
    before: { sets: [] },
    after: { sets: [{ name: 'Foo', variables: [{ name: 'bar', type: 'FLOAT' }] }] }
  });
  assert.equal(result.ok, true);
  assert.ok(result.issues.some(i => i.code === 'NEW_SET_NAME' && i.severity === 'warning'));
});

test('reports removed sets, removed variables and type changes', () => {
  const result = verifyTokenDiff({
    before: { sets: [{ name: 'Semantic', variables: [{ name: 'text-primary', type: 'COLOR' }, { name: 'old-token', type: 'FLOAT' }] }] },
    after: { sets: [{ name: 'Semantic', variables: [{ name: 'text-primary', type: 'STRING' }] }] }
  });
  assert.ok(result.issues.some(i => i.code === 'VAR_REMOVED'));
  assert.ok(result.issues.some(i => i.code === 'VAR_TYPE_CHANGED'));
});

test('rejects unknown top-level shapes instead of treating them as sets', () => {
  assert.equal(hasKnownShape({ variableCollections: [] }), true);
  assert.equal(hasKnownShape({ someRandomKey: { a: 1 } }), false);
  const result = verifyTokenDiff({
    before: { someRandomKey: { a: 1 } },
    after: { anotherRandomKey: { b: 2 } }
  });
  assert.equal(result.ok, false);
  assert.ok(result.issues.some(i => i.code === 'INPUT_INVALID'));
});

test('warns on unknown keys mixed with a known shape', () => {
  const result = verifyTokenDiff({
    before: { sets: [] },
    after: { sets: [{ name: 'Semantic', variables: [{ name: 'text-primary', type: 'COLOR' }] }], junk: { a: 1 } }
  });
  assert.equal(result.ok, true);
  assert.ok(result.issues.some(i => i.code === 'UNKNOWN_KEY' && i.severity === 'warning'));
});

test('normalizes set maps and flat variable lists', () => {
  const map = normalizeSnapshot({ Semantic: { variables: { 'text-primary': { type: 'COLOR' } } } });
  assert.equal(map.get('Semantic').get('text-primary'), 'COLOR');

  const flat = normalizeSnapshot({ variables: [{ name: 'bg-surface', variableSetName: 'Semantic', type: 'COLOR' }] });
  assert.equal(flat.get('Semantic').get('bg-surface'), 'COLOR');
});
