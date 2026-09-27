/**
 * 结构守卫：执行记录与 token 字段只有一个写入口
 * （REQ-260927121324-abde t1 · FR-4 / FR-5 / FR-8）。
 *
 * 契约（机械断言，违规时打印「文件:行号」）：
 *   1. src 下（application/internal/token-usage.ts 之外）任何文件不得自行
 *      task.executions.push(...) —— 落执行记录只经 openExecution；
 *   2. 任何文件不得对 tokenUsage 赋值（x.tokenUsage = ...、??=、复合赋值）——
 *      只经 beginExecutionToken / endExecutionToken / accumulateStageDelta。
 *      **读引用不算**：req.tokenUsage?.byStage、e.tokenUsage === undefined、
 *      类型声明 tokenUsage?: ExecutionTokenUsage 都合法；
 *   3. 排除项自身必须仍在且仍承担「落执行 + 写 token」，防止删掉收敛点让守卫空过的假绿。
 *
 * 实现说明：用 TypeScript 词法器剔除注释（保留换行，行号不变），再逐行匹配；
 * 字符串字面量保留（更严格：宁可误报，不可漏报）。
 */
import { describe, it, expect } from 'vitest'
import { existsSync, readFileSync, readdirSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { join, relative } from 'node:path'
import ts from 'typescript'

const PKG_ROOT = fileURLToPath(new URL('..', import.meta.url))
const SRC = join(PKG_ROOT, 'src')
/** 唯一收敛点：只有本文件允许 push 执行记录 / 写 tokenUsage。 */
const CONVERGENCE = join(SRC, 'application', 'internal', 'token-usage.ts')

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

/** 禁用式样（读引用天然不匹配）。 */
const FORBIDDEN: { label: string; re: RegExp }[] = [
  { label: 'executions.push(', re: /executions\s*\.\s*push\s*\(/ },
  { label: 'tokenUsage 赋值', re: /\btokenUsage\s*(?:\?\?=|\+=|-=|\|\|=|&&=|=)(?!=)/ },
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

describe('执行/token 结构守卫 · 唯一写入口', () => {
  const allFiles = collectTs(SRC)
  const scanned = allFiles.filter((f) => f !== CONVERGENCE)

  it('扫描面非空（防扫描器失效/路径写错导致的假绿）', () => {
    expect(allFiles.length, 'src 下 .ts 文件数异常（实际 ' + allFiles.length + '）').toBeGreaterThan(50)
    expect(scanned.length, '排除项应恰好命中一个文件').toBe(allFiles.length - 1)
  })

  it('src 下（token-usage.ts 之外）无 executions.push( 与 tokenUsage 赋值', () => {
    const violations: string[] = []
    for (const file of scanned) {
      const code = stripComments(readFileSync(file, 'utf8'))
      for (const v of findViolations(code)) violations.push(relative(PKG_ROOT, file) + ':' + v)
    }
    expect(
      violations,
      '以下位置绕过唯一写入口（应改经 openExecution / beginExecutionToken / endExecutionToken）：' + '\n' + violations.join('\n'),
    ).toEqual([])
  })

  it('收敛点仍在且仍承担落执行 + 写 token（排除项不可被删除规避）', () => {
    expect(existsSync(CONVERGENCE), '唯一写入口文件缺失：' + relative(PKG_ROOT, CONVERGENCE)).toBe(true)
    const code = readFileSync(CONVERGENCE, 'utf8')
    expect(code).toContain('export function openExecution')
    expect(code).toContain('export function closeExecutions')
    expect(code).toContain('task.executions.push(execution)')
  })

  it('守卫本身可变红：反例被抓，读引用 / 类型声明 / 注释不误报', () => {
    expect(findViolations(stripComments('task.executions.push(execution)'))).toHaveLength(1)
    expect(findViolations(stripComments('execution.tokenUsage = usage'))).toHaveLength(1)
    expect(findViolations(stripComments('execution.tokenUsage ??= {}'))).toHaveLength(1)
    // 读引用 / 类型声明 / 注释里的反例都不得误报
    expect(findViolations(stripComments('const n = req.tokenUsage?.totals ?? 0'))).toEqual([])
    expect(findViolations(stripComments('if (req.tokenUsage === undefined) return undefined'))).toEqual([])
    expect(findViolations(stripComments('interface X { tokenUsage?: ExecutionTokenUsage }'))).toEqual([])
    expect(findViolations(stripComments('// 调用方不得 executions.push(e)，也不得 tokenUsage = x'))).toEqual([])
    expect(findViolations(stripComments('/* tokenUsage = x\nexecutions.push(e) */'))).toEqual([])
  })
})
