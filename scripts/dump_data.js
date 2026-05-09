/**
 * One-shot helper: load every existing *-data.js file plus the ETF_DATA
 * embedded in leveraged-etfs.html, and write everything out as one JSON
 * payload for the Python migration script to consume.
 *
 * Run from project root:
 *   node scripts/dump_data.js > scripts/dump_data.json
 */

const fs = require('fs');
const path = require('path');

const ROOT = path.resolve(__dirname, '..');

function loadJs(filename) {
  const content = fs.readFileSync(path.join(ROOT, filename), 'utf-8');
  // Each *-data.js file declares globals via `const HOLDINGS = {}; HOLDINGS[...] = ...;`
  // Eval'ing in a global-ish scope means we have to indirect through a wrapper.
  return content;
}

// Eval the holdings/prices/funds/stock-info bundles in our scope.
// They each declare their globals via `const`, but at the global scope of a
// node script, those `const`s are not exposed. So wrap each in (() => {})()
// and have them attach to a shared `out` object.
const out = {};

function evalAndCapture(filename, names) {
  const src = loadJs(filename);
  // Append a tail that copies the named globals onto `out`.
  const tail = '\n;' + names.map(n => `out["${n}"] = (typeof ${n} !== 'undefined') ? ${n} : null;`).join('');
  // Wrap to keep declarations local but expose `out`.
  const wrapped = `(function(out){\n${src}\n${tail}\n})(out);`;
  eval(wrapped);
}

evalAndCapture('holdings-data.js', ['HOLDINGS']);
evalAndCapture('prices-data.js',   ['PRICES']);
evalAndCapture('funds-data.js',    ['FUNDS', 'FUND_CATEGORIES']);
evalAndCapture('stock-info.js',    ['STOCK_INFO']);

// Pull ETF_DATA out of leveraged-etfs.html
const html = fs.readFileSync(path.join(ROOT, 'leveraged-etfs.html'), 'utf-8');
const start = html.indexOf('const ETF_DATA = {');
if (start === -1) throw new Error('ETF_DATA not found in leveraged-etfs.html');
let depth = 0, end = start;
for (let i = start + 'const ETF_DATA = '.length - 1; i < html.length; i++) {
  const c = html[i];
  if (c === '{') depth++;
  else if (c === '}') { depth--; if (depth === 0) { end = i + 1; break; } }
}
const etfDataSrc = html.slice(start, end + 1);  // include trailing `;`
eval(`(function(out){\n${etfDataSrc}\n;out["ETF_DATA"] = ETF_DATA;\n})(out);`);

process.stdout.write(JSON.stringify(out));
