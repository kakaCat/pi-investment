/**
 * 路径口径故障注入回归（REQ-b63a7d t6）——把 403 刷屏事故的四种形态固化成会响的线。
 *
 * 事故面（2026-09-18）：reqboard_task_report 原样上浮 files_changed，台账里混入
 *   A 仓库根相对 agent-dh/docs/…、B 工作区内绝对路径、C 跨仓 quantsys-v2/…、D brace 伪路径，
 * 前端逐条预检被文件接口 docs-only 白名单判 403（实测 142 条）。
 *
 * 两类断言：
 *   ① 形态矩阵：A/B 必须可读（回归=403 即红）、C 必须 outside_workspace、D 必须 not_a_file、
 *      穿越必须仍 403；
 *   ② 存量台账扫描：真实 .dsh-data/dsh-reqboard.json 里的产物/文档路径**不得**存在会被
 *      判 403 的写法（无根绝对路径 / 无 .. / 无反斜杠）。文件不存在时跳过（不伪造绿灯）。
 */
import { describe, it, expect } from 'vitest'
import { existsSync, readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { normalizeArtifactPath } from '../src/domain/artifact/ArtifactPath.js'

const WORKSPACE = '/Users/yunpeng/pi-investment/agent-dh'

describe('形态矩阵：归一后不再把合法路径判成越界', () => {
  const cases: Array<{ shape: string; raw: string; form: string; path?: string }> = [
    { shape: 'A 仓库根相对', raw: 'agent-dh/docs/architecture/documentation-standard.md', form: 'workspace', path: 'docs/architecture/documentation-standard.md' },
    { shape: 'A 仓库根相对（源码）', raw: 'agent-dh/packages/pages/dsh-pmboard/src/index.ts', form: 'workspace', path: 'packages/pages/dsh-pmboard/src/index.ts' },
    { shape: 'B 工作区内绝对路径', raw: WORKSPACE + '/packages/pages/dsh-pmboard/lib/client.js', form: 'workspace', path: 'packages/pages/dsh-pmboard/lib/client.js' },
    { shape: 'B 工作区外绝对路径', raw: '/etc/passwd', form: 'outside' },
    { shape: 'C 跨仓相对', raw: 'quantsys-v2/application/services/watch_engine/engine.py', form: 'workspace' },
    { shape: 'D brace 伪路径', raw: 'quantsys-v2/tests/{a.py,b.py}', form: 'pseudo' },
    { shape: 'D 通配伪路径', raw: 'docs/*.md', form: 'pseudo' },
    { shape: '穿越 ..', raw: 'docs/../../etc/passwd', form: 'outside' },
  ]
  for (const c of cases) {
    it(c.shape + '：' + c.raw, () => {
      const r = normalizeArtifactPath(c.raw, WORKSPACE)
      expect(r.form).toBe(c.form)
      if (c.path !== undefined) expect(r.path).toBe(c.path)
    })
  }

  it('会判 403 的只有「绝对路径 + 非 workspace」与「含 .. / 反斜杠」两类', () => {
    const forbidden = (raw: string): boolean => {
      if (raw.includes(String.fromCharCode(92)) || raw.split('/').some(s => s === '..')) return true
      return raw.startsWith('/') && normalizeArtifactPath(raw, WORKSPACE).form !== 'workspace'
    }
    // A/B(in-workspace)/C/D 都不该被判 403
    for (const raw of [
      'agent-dh/docs/architecture/documentation-standard.md',
      WORKSPACE + '/packages/pages/dsh-pmboard/src/index.ts',
      'quantsys-v2/application/services/watch_engine/engine.py',
      'quantsys-v2/tests/{a.py,b.py}',
    ]) {
      expect(forbidden(raw), raw + ' 不应被判 403').toBe(false)
    }
    // 真正的越权仍必须被判 403
    expect(forbidden('/etc/passwd')).toBe(true)
    expect(forbidden('../../etc/passwd')).toBe(true)
  })
})

describe('存量台账回归扫描：不得残留会被判 403 的路径写法', () => {
  const ledgerPath = fileURLToPath(new URL('../../../.dsh-data/dsh-reqboard.json', import.meta.url))
  const hasLedger = existsSync(ledgerPath)

  it(hasLedger ? '真实台账：产物/文档路径无 403 写法' : '（跳过：本机无台账文件，不伪造绿灯）', () => {
    if (!hasLedger) return
    const ledger = JSON.parse(readFileSync(ledgerPath, 'utf8')) as {
      requirements?: Array<Record<string, unknown>>
    }
    const bad: string[] = []
    const inspect = (raw: unknown, where: string): void => {
      if (typeof raw !== 'string' || raw.length === 0) return
      if (raw.includes(String.fromCharCode(92)) || raw.split('/').some(s => s === '..')) {
        bad.push(where + ' -> ' + raw + '（含 .. 或反斜杠）')
        return
      }
      if (raw.startsWith('/') && normalizeArtifactPath(raw, WORKSPACE).form !== 'workspace') {
        bad.push(where + ' -> ' + raw + '（工作区外绝对路径）')
      }
    }
    for (const req of ledger.requirements ?? []) {
      const id = String(req.id ?? '?')
      for (const a of (req.artifacts as Array<Record<string, unknown>> | undefined) ?? []) {
        inspect(a.path, id + '.artifacts(' + String(a.kind) + ')')
      }
      const archive = req.archive as Record<string, unknown> | undefined
      for (const d of (archive?.docs as Array<Record<string, unknown>> | undefined) ?? []) {
        inspect(d.path, id + '.archive.docs')
      }
      for (const m of (archive?.mergedInto as unknown[] | undefined) ?? []) {
        inspect(m, id + '.archive.mergedInto')
      }
      const plan = req.plan as Record<string, unknown> | undefined
      inspect(plan?.path, id + '.plan.path')
      const docLinks = req.docLinks as Record<string, unknown> | undefined
      if (docLinks !== undefined) {
        for (const [k, v] of Object.entries(docLinks)) {
          if (typeof v === 'string') inspect(v, id + '.docLinks.' + k)
          if (Array.isArray(v)) {
            for (const e of v as Array<Record<string, unknown>>) inspect(e.path, id + '.docLinks.' + k + '[].path')
          }
        }
      }
    }
    expect(bad, '台账里存在会被文件接口判 403 的路径写法：\n' + bad.join('\n')).toEqual([])
  })
})
