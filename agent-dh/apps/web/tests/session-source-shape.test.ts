/**
 * Session v4 source-shape guard.
 *
 * DSH 0.2.1 的 v4 会话格式拒绝旧版 plugin 包装：
 *   source: { kind: 'plugin', plugin: 'xxx' }   // ❌
 *   source: { kind: 'plugin:xxx' }              // ✅
 *
 * 2026-10-20 事故：lifecycle 的 followup 用旧写法，agent-loop kick() 静默吞掉
 * SessionFormatError，表现为「投递成功但会话 turns=0」。本测试扫源码，防止同类
 * 写法再次进入生产路径（测试夹具不参与扫描）。
 */
import { describe, it, expect } from 'vitest'
import { readdirSync, readFileSync, statSync } from 'node:fs'
import { join, relative } from 'node:path'
import { fileURLToPath } from 'node:url'

const PACKAGES_ROOT = fileURLToPath(new URL('../../../packages', import.meta.url))
const LEGACY_SOURCE = /\bkind\s*:\s*['"]plugin['"]/

function walk(dir: string, out: string[] = []): string[] {
  for (const entry of readdirSync(dir)) {
    if (entry === 'node_modules' || entry === 'dist' || entry === 'lib') continue
    const full = join(dir, entry)
    const stat = statSync(full)
    if (stat.isDirectory()) walk(full, out)
    else if (/\.(ts|tsx)$/.test(entry) && !/\.test\.(ts|tsx)$/.test(entry)) out.push(full)
  }
  return out
}

describe('session v4 producer-owned source kind', () => {
  it('生产源码不得使用裸 kind=plugin（v4 会硬拒绝）', () => {
    const offenders = walk(PACKAGES_ROOT)
      .filter((file) => LEGACY_SOURCE.test(readFileSync(file, 'utf8')))
      .map((file) => relative(PACKAGES_ROOT, file))

    expect(offenders).toEqual([])
  })
})
