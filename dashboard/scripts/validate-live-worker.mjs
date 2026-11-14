import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
const source = await readFile('dist/server/index.js', 'utf8');
const moduleUrl = 'data:text/javascript;base64,' + Buffer.from(source).toString('base64');
const worker = await import(moduleUrl);
assert.equal(typeof worker.default?.fetch, 'function');
console.log('Live server artifact is valid.');
