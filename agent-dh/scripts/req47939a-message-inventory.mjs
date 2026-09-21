/**
 * 用户可见消息文本账（REQ-47939a 行为等价辅助核验）。
 * 用途：搬迁期间以"旧实现还在"为判据，抽取两侧的中文消息字面量做集合比对；
 * t9 删除 host/ 后重跑，用来证明"搬迁没丢用户可见消息"。
 * 注意：只作辅助信号——消息可能被拆成模板拼接，故按"整条字面量"比对必然有假阳性，
 * 报告里要按需人工判读。
 */
import { readFileSync } from 'node:fs'
import { readdirSync, statSync } from 'node:fs'
import { join } from 'node:path'

const ROOT = '/Users/yunpeng/pi-investment/agent-dh/packages/web/dsh-pmboard'

function walk(dir, out = []) {
  let es = []
  try { es = readdirSync(dir, { withFileTypes: true }) } catch { return out }
  for (const e of es) {
    const p = join(dir, e.name)
    if (e.isDirectory()) walk(p, out)
    else if (e.name.endsWith('.ts')) out.push(p)
  }
  return out
}

/** 抽取单引号/双引号/模板字符串里的字面量（**排除换行**，避免跨行误匹配）。 */
function literalsOf(file) {
  let s = ''
  try { s = readFileSync(file, 'utf8') } catch { return [] }
  const out = []
  const re = /(['"\`])((?:\\[\s\S]|(?!\1)[^\n])*?)\1/g
  let m
  while ((m = re.exec(s)) !== null) {
    const lit = m[2].replace(/\\n/g, ' ').trim()
    if (lit.length >= 8 && /[\u4e00-\u9fff]/.test(lit)) out.push(lit)
  }
  return out
}

const oldFiles = [join(ROOT, 'src/host/agent-tools.ts')]
const newFiles = [...walk(join(ROOT, 'src/application')), ...walk(join(ROOT, 'src/domain')), ...walk(join(ROOT, 'src/adapters'))]
const oldLits = new Set(oldFiles.flatMap(literalsOf))
const newLits = new Set(newFiles.flatMap(literalsOf))
const missing = [...oldLits].filter(x => !newLits.has(x)).sort()

console.log('旧 host/agent-tools.ts 中文消息字面量 :', oldLits.size)
console.log('新分层(application+domain+adapters):', newLits.size)
console.log('旧有新无（尚未搬迁，t7/t8 后应趋 0） :', missing.length)
console.log('--- 前 10 条:')
for (const x of missing.slice(0, 10)) console.log('  -', x.slice(0, 100))
