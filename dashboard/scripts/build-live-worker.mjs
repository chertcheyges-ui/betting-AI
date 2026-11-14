import { mkdir, readdir, readFile, rm, writeFile, copyFile } from 'node:fs/promises';
import { dirname, extname, join, relative } from 'node:path';

const root = process.cwd();
const source = join(root, 'site-static');
const output = join(root, 'dist');
const template = await readFile(join(root, 'worker/live-template.mjs'), 'utf8');
const assets = {};

async function collect(folder) {
  for (const entry of await readdir(folder, { withFileTypes: true })) {
    const full = join(folder, entry.name);
    if (entry.isDirectory()) await collect(full);
    else assets['/' + relative(source, full).replaceAll('\\', '/')] = await readFile(full, 'utf8');
  }
}

await collect(source);
await rm(output, { recursive: true, force: true });
await mkdir(join(output, 'server'), { recursive: true });
await mkdir(join(output, '.openai'), { recursive: true });
await writeFile(join(output, 'server', 'index.js'), template.replace('__ASSETS__', () => JSON.stringify(assets)), 'utf8');
await copyFile(join(root, '.openai', 'hosting.json'), join(output, '.openai', 'hosting.json'));
console.log('Built live server with ' + Object.keys(assets).length + ' site files.');
