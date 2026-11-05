#!/usr/bin/env node
'use strict';

const fs = require('fs');

const EXIT_OK = 0;
const EXIT_FAIL = 1;
const EXIT_INPUT = 2;

const KEBAB = /^[a-z][a-z0-9]*(-[a-z0-9]+)*$/;
const PREFERRED_SETS = new Set(['Primitives', 'Semantic', 'Component']);
const SET_ALIASES = ['sets', 'variableSets', 'collections', 'variableCollections'];

function hasKnownShape(snapshot) {
  if (Array.isArray(snapshot)) return true;
  if (!snapshot || typeof snapshot !== 'object') return false;
  if (Object.keys(snapshot).length === 0) return true;
  if (SET_ALIASES.some(key => snapshot[key] !== undefined)) return true;
  if (Array.isArray(snapshot.variables)) return true;
  return Object.keys(snapshot).some(key => /^[A-Z][A-Za-z0-9 _-]*$/.test(key) && snapshot[key] && typeof snapshot[key] === 'object');
}

function normalizeSnapshot(snapshot) {
  const sets = new Map();
  const addVar = (setName, varName, type) => {
    if (!setName || !varName) return;
    if (!sets.has(setName)) sets.set(setName, new Map());
    sets.get(setName).set(String(varName), String(type || ''));
  };

  const readVariables = (setName, variables) => {
    if (Array.isArray(variables)) {
      for (const item of variables) {
        if (typeof item === 'string') addVar(setName, item, '');
        else if (item && typeof item === 'object') addVar(setName, item.name || item.varName || item.id, item.type);
      }
    } else if (variables && typeof variables === 'object') {
      for (const [name, item] of Object.entries(variables)) {
        addVar(setName, name, item && typeof item === 'object' ? item.type : '');
      }
    }
  };

  const readSet = (name, value) => {
    if (!name || !value || typeof value !== 'object') return;
    if (value.variables || value.vars) {
      readVariables(name, value.variables || value.vars);
      return;
    }
    const vars = {};
    for (const [key, item] of Object.entries(value)) {
      if (['name', 'setName', 'variableSetName', 'type', 'id'].includes(key)) continue;
      vars[key] = item;
    }
    readVariables(name, vars);
  };

  if (Array.isArray(snapshot)) {
    for (const item of snapshot) {
      if (item && typeof item === 'object') {
        const setName = item.variableSetName || item.setName || item.set || item.variableSet;
        if (setName) addVar(setName, item.name || item.varName, item.type);
        else if (item.name && (item.variables || item.vars)) readSet(item.name, item);
      }
    }
    return sets;
  }

  if (!snapshot || typeof snapshot !== 'object') return sets;

  for (const alias of SET_ALIASES) {
    const value = snapshot[alias];
    if (Array.isArray(value)) {
      for (const item of value) {
        if (item && typeof item === 'object') readSet(item.name || item.setName, item);
      }
    } else if (value && typeof value === 'object') {
      for (const [name, item] of Object.entries(value)) readSet(name, item);
    }
  }

  if (Array.isArray(snapshot.variables)) {
    for (const item of snapshot.variables) {
      if (!item || typeof item !== 'object') continue;
      addVar(item.variableSetName || item.setName || item.set, item.name || item.varName, item.type);
    }
  }

  const known = new Set([...SET_ALIASES, 'variables']);
  for (const [name, value] of Object.entries(snapshot)) {
    if (!known.has(name) && /^[A-Z][A-Za-z0-9 _-]*$/.test(name) && value && typeof value === 'object') {
      readSet(name, value);
    }
  }

  return sets;
}

function verifyTokenDiff(input) {
  const issues = [];
  const add = (code, severity, message, extra = {}) => issues.push({ code, severity, message, ...extra });

  if (!input || typeof input !== 'object' || !input.after) {
    return { ok: false, issues: [{ code: 'INPUT_INVALID', severity: 'error', message: 'input must be { before, after }' }], stats: {} };
  }

  if (!hasKnownShape(input.after)) {
    add('INPUT_INVALID', 'error', 'after snapshot shape is not recognized');
  }
  if (input.before && Object.keys(input.before).length > 0 && !hasKnownShape(input.before)) {
    add('INPUT_INVALID', 'error', 'before snapshot shape is not recognized');
  }
  const metadataKeys = new Set([...SET_ALIASES, 'variables', 'schemaVersion', 'version', 'revision', 'mode', 'modes']);
  for (const key of Object.keys(input.after || {})) {
    if (!metadataKeys.has(key) && !/^[A-Z][A-Za-z0-9 _-]*$/.test(key)) {
      add('UNKNOWN_KEY', 'warning', `unknown top-level key ignored: ${key}`, { key });
    }
  }

  const before = normalizeSnapshot(input.before || {});
  const after = normalizeSnapshot(input.after);
  if (after.size === 0) {
    add('EMPTY_SNAPSHOT', 'error', 'after snapshot has no variable sets; treat as not executed');
  }

  const addedSets = [...after.keys()].filter(n => !before.has(n));
  const removedSets = [...before.keys()].filter(n => !after.has(n));
  const addedVars = [];
  const removedVars = [];
  const changedType = [];

  for (const [setName, vars] of after) {
    const oldVars = before.get(setName) || new Map();
    for (const [varName, type] of vars) {
      if (!oldVars.has(varName)) {
        addedVars.push({ set: setName, name: varName, type });
        if (!KEBAB.test(varName)) {
          add('NEW_VAR_NAME', 'error', `new variable is not lowercase kebab: ${setName}/${varName}`, { set: setName, name: varName });
        }
      } else if (oldVars.get(varName) !== type) {
        changedType.push({ set: setName, name: varName, before: oldVars.get(varName), after: type });
      }
    }
    for (const [varName, type] of oldVars) {
      if (!vars.has(varName)) removedVars.push({ set: setName, name: varName, type });
    }
  }

  for (const setName of addedSets) {
    if (!PREFERRED_SETS.has(setName)) {
      add('NEW_SET_NAME', 'warning', `new set is outside the preferred set names: ${setName}`, { set: setName });
    }
    if ((after.get(setName) || new Map()).size === 0) {
      add('EMPTY_NEW_SET', 'warning', `new set has no variables: ${setName}`, { set: setName });
    }
  }
  for (const setName of removedSets) {
    add('SET_REMOVED', 'warning', `set disappeared: ${setName}`, { set: setName });
  }
  for (const item of removedVars) {
    add('VAR_REMOVED', 'warning', `variable disappeared: ${item.set}/${item.name}`, item);
  }
  for (const item of changedType) {
    add('VAR_TYPE_CHANGED', 'warning', `variable type changed: ${item.set}/${item.name}`, item);
  }

  return {
    ok: !issues.some(i => i.severity === 'error'),
    stats: {
      beforeSets: before.size,
      afterSets: after.size,
      addedSets: addedSets.length,
      removedSets: removedSets.length,
      addedVars: addedVars.length,
      removedVars: removedVars.length,
      changedType: changedType.length
    },
    diff: { addedSets, removedSets, addedVars, removedVars, changedType },
    issues
  };
}

function parseArgs(argv) {
  const args = {};
  for (let i = 2; i < argv.length; i++) {
    const arg = argv[i];
    if (arg === '--help' || arg === '-h') args.help = true;
    else if (arg === '--json') args.json = true;
    else if (arg === '--input') args.input = argv[++i];
    else throw new Error(`unknown argument: ${arg}`);
  }
  return args;
}

function usage() {
  return [
    'Usage: node verify-token-diff.js --input <diff.json> [--json]',
    '',
    'Input: { "before": <fetch_variables result>, "after": <fetch_variables result> }.',
    'Accepts { sets: [...] }, { variables: [...] }, or a { setName: {...} } map.'
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

  const result = verifyTokenDiff(input);
  if (args.json) console.log(JSON.stringify(result, null, 2));
  else {
    for (const issue of result.issues) console.log(`[${issue.severity}] ${issue.code}: ${issue.message}`);
    console.log(`beforeSets=${result.stats.beforeSets} afterSets=${result.stats.afterSets} addedVars=${result.stats.addedVars} ok=${result.ok}`);
  }
  process.exit(result.ok ? EXIT_OK : EXIT_FAIL);
}

if (require.main === module) main();

module.exports = { verifyTokenDiff, normalizeSnapshot, hasKnownShape };
