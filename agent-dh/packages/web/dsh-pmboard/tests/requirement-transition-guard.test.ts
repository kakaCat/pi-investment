/**
 * 结构守卫：需求状态迁移只有一个写入口
 * （REQ-b545fe t1 / 2026-09-27 补）。
 *
 * 背景事故：transitionRequirement 原先直接 req.status = to 且无任何校验，
 * 于是「批准计划」分支漏检即可让需求在计划未落库时进入 implementing，
 * 造成 DAG / 泳道 / 实施覆盖度全空且零告警。
 *
 * 契约（机械断言，违规时打印「文件:行号」）：
 *   1. src/application 与 src/http 内不得出现 req.status / r.status 直接赋值
 *      （业务路径一律经 transitionRequirement）；
 *   2. 唯一允许的直接写入是收敛点 application/internal/token-usage.ts 内部
 *      （transitionRequirement 的 req.status = to）——本测试排除该文件，
 *      同时断言它仍存在且仍是唯一迁移入口（防止删除收敛点让守卫空过）。
 *
 * 实现说明：用 TypeScript 词法器剔除注释（保留换行，行号不变），再逐行匹配；
 * 比较式（req.status === x / !== / 读取）天然不匹配。
 */
import { describe, it, expect } from 'vitest'
import { existsSync, readFileSync, readdirSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { join, relative } from 'node:path'
import ts from 'typescript'

const PKG_ROOT = fileURLToPath(new URL('..', import.meta.url))
const APP = join(PKG_ROOT, 'src', 'application')
const HTTP = join(PKG_ROOT, 'src', 'http')
/** 唯一收敛点：本文件内部的 req.status = to 是唯一允许的直接赋值。 */
const CONVERGENCE = join(APP, 'internal', 'token-usage.ts')

/** 递归收集目录下全部 .ts 文件（绝对路径）。 */
function collectTs(dir: string, out: string[] = []): string[] {
  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    const p = join(dir, entry.name)
    if (entry.isDirectory()) collectTs(p, out)
    else if (entry.isFile() && entry.name.endsWith('.ts')) out.push(p)
  }
  return out
}

/** 用 TS 词法器把注释内容替换为空格（换行保留 → 行号不变）。 */
function stripComments(src: string): string {
  const chars = src.split('')
  const scanner = ts.createScanner(ts.ScriptTarget.Latest, false, ts.LanguageVariant.Standard, src)
  for (let token = scanner.scan(); token !== ts.SyntaxKind.EndOfFileToken; token = scanner.scan()) {
    if (token !== ts.SyntaxKind.SingleLineCommentTrivia && token !== ts.SyntaxKind.MultiLineCommentTrivia) continue
    for (let i = scanner.getTokenPos(); i < scanner.getTextPos(); i += 1) {
      if (chars[i] !== '\n' && chars[i] !== '\r') chars[i] = ' '
    }
  }
  return chars.join('')
}

/** 禁用式样：直接赋值（= 而非 ==/===/!=）。 */
const FORBIDDEN: { label: string; re: RegExp }[] = [
  { label: 'req.status 直接赋值', re: /\breq\.status\s*=(?!=)/ },
  { label: 'r.status 直接赋值', re: /\br\.status\s*=(?!=)/ },
]

/** 找违规，返回「第 N 行 · 式样 → 原文」。 */
function findViolations(code: string): string[] {
  const bad: string[] = []
  code.split('\n').forEach((line, idx) => {
    for (const { label, re } of FORBIDDEN) {
      if (re.test(line)) bad.push('第 ' + (idx + 1) + ' 行 · ' + label + ' → ' + line.trim())
    }
  })
  return bad
}

describe('需求状态迁移结构守卫 · 唯一收敛点', () => {
  const allFiles = [...collectTs(APP), ...collectTs(HTTP)]
  const scanned = allFiles.filter((f) => f !== CONVERGENCE)

  it('扫描面非空（防扫描器失效/路径写错导致的假绿）', () => {
    expect(allFiles.length, 'application + http 下 .ts 文件数异常（实际 ' + allFiles.length + '）').toBeGreaterThan(50)
    expect(scanned.length, '排除项应恰好命中一个文件').toBe(allFiles.length - 1)
  })

  it('src/application 与 src/http 内无 req.status / r.status 直接赋值', () => {
    const violations: string[] = []
    for (const file of scanned) {
      const code = stripComments(readFileSync(file, 'utf8'))
      for (const v of findViolations(code)) violations.push(relative(PKG_ROOT, file) + ':' + v)
    }
    expect(
      violations,
      '以下位置绕过唯一迁移入口（应改经 transitionRequirement）：' + '\n' + violations.join('\n'),
    ).toEqual([])
  })

  it('收敛点仍在且仍是唯一迁移入口（排除项不可被删除规避）', () => {
    expect(existsSync(CONVERGENCE), '唯一迁移入口文件缺失：' + relative(PKG_ROOT, CONVERGENCE)).toBe(true)
    const code = readFileSync(CONVERGENCE, 'utf8')
    expect(code).toContain('export function transitionRequirement')
    expect(code).toContain('req.status = to')
  })

  it('守卫本身可变红：反例被抓，读取 / 比较 / 注释不误报', () => {
    expect(findViolations(stripComments('req.status = to'))).toHaveLength(1)
    expect(findViolations(stripComments('r.status = to'))).toHaveLength(1)
    expect(findViolations(stripComments('const s = req.status'))).toEqual([])
    expect(findViolations(stripComments("if (r.status !== 'done') return"))).toEqual([])
    expect(findViolations(stripComments("const ok = req.status === 'implementing'"))).toEqual([])
    expect(findViolations(stripComments('const status = r.status'))).toEqual([])
    expect(findViolations(stripComments('// 不得直接 req.status = to'))).toEqual([])
    expect(findViolations(stripComments('/* r.status = to\nreq.status = to */'))).toEqual([])
  })
})
