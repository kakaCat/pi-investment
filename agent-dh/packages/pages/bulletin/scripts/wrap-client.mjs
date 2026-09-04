// Wrap the compiled CJS client bundle into a browser module loader registration.
// Mirrors dsh-taskboard's scripts/wrap-client.mjs: reads package.json + the
// tsdown CJS output, emits lib/client.js as window.__ModuleLoader__.load({
//   id: pkg.name, factory: (require) => module.exports }) — the exact shape
// the DSH web shell's client-modules host serves at /plugins/??<pkg>/client.js.
import { readFileSync, writeFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

const here = dirname(fileURLToPath(import.meta.url))
const root = join(here, '..')
const pkg = JSON.parse(readFileSync(join(root, 'package.json'), 'utf8'))
const cjs = readFileSync(join(root, 'lib', 'client.cjs'), 'utf8')

const body = cjs
  .split('\n')
  .map((line) => '\t\t' + line)
  .join('\n')

const out = `window.__ModuleLoader__.load({
\t\tid: ${JSON.stringify(pkg.name)},
\t\tfactory: (require) => {
\t\t\tvar module = { exports: {} };
\t\t\tvar exports = module.exports;
\t\t\tObject.defineProperty(exports, Symbol.toStringTag, { value: "Module" });
${body}
\t\t\treturn module.exports;
\t\t}
\t});
\n`

writeFileSync(join(root, 'lib', 'client.js'), out)
console.log('wrapped', pkg.name, '->', 'lib/client.js', out.length, 'bytes')
