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

// 2026-09-16 修复：不再给每行注入 \t\t 缩进——它会污染 bundle 内
// 多行模板字符串（marked 的 HTML 输出模板/缩进判断被注入 tab，
// 导致列表续行被误判为 code block、输出 HTML 带 \t\t）。
const body = cjs

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
