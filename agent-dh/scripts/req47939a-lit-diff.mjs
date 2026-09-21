import { readFileSync, readdirSync } from 'node:fs'
import { join } from 'node:path'
const R = '/Users/yunpeng/pi-investment/agent-dh/packages/web/dsh-pmboard'
function walk(dir, out = []) {
  let es = []; try { es = readdirSync(dir, { withFileTypes: true }) } catch { return out }
  for (const e of es) { const p = join(dir, e.name); if (e.isDirectory()) walk(p, out); else if (e.name.endsWith('.ts')) out.push(p) }
  return out
}
function lits(file) {
  let s = ''; try { s = readFileSync(file, 'utf8') } catch { return [] }
  const out = []; const re = /(['"\`])((?:\\[\s\S]|(?!\1)[^\n])*?)\1/g; let m
  while ((m = re.exec(s)) !== null) { const t = m[2].replace(/\\n/g, ' ').trim(); if (t.length >= 8 && /[\u4e00-\u9fff]/.test(t)) out.push(t) }
  return out
}
const [oldFile, newDir] = process.argv.slice(2)
const oldS = new Set(lits(oldFile))
const newS = new Set(walk(newDir).flatMap(lits))
const missing = [...oldS].filter(x => !newS.has(x)).sort()
console.log('旧文件中文消息字面量 :', oldS.size)
console.log('新目录(递归)         :', newS.size)
console.log('旧有新无             :', missing.length)
for (const x of missing.slice(0, 12)) console.log('  - ' + x.slice(0, 96))
