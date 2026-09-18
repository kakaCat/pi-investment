/**
 * 产物路径归一层单测（REQ-b63a7d t1）。
 *
 * 锁定四种实测形态的归一结果 + 合规路径原样不变 + 逃逸路径判 outside。
 * 口径说明：字符串层无法区分「工作区内的 quantsys-v2 目录」与「仓库根下的兄弟仓库」，
 * 故形如 quantsys-v2/x.py 的**相对**路径保持原样（form=workspace），由 fs 端点决定
 * 是否 outside_workspace（见 tests/http/file-route.test.ts）。
 */
import { describe, it, expect } from 'vitest'
import { normalizeArtifactPath } from '../../src/domain/artifact/ArtifactPath.js'

const ROOT = '/Users/yunpeng/pi-investment/agent-dh'

describe('normalizeArtifactPath：四种实测形态', () => {
  it('① 工作区名前缀（仓库根相对）→ 剥掉重复的工作区目录名', () => {
    const r = normalizeArtifactPath('agent-dh/docs/architecture/documentation-standard.md', ROOT)
    expect(r.form).toBe('workspace')
    expect(r.path).toBe('docs/architecture/documentation-standard.md')
  })

  it('①b 工作区名前缀 + 源码路径', () => {
    const r = normalizeArtifactPath('agent-dh/packages/pages/dsh-pmboard/src/index.ts', ROOT)
    expect(r.form).toBe('workspace')
    expect(r.path).toBe('packages/pages/dsh-pmboard/src/index.ts')
  })

  it('② 绝对路径（工作区内）→ 剥掉工作区根', () => {
    const r = normalizeArtifactPath(ROOT + '/packages/pages/dsh-pmboard/lib/client.js', ROOT)
    expect(r.form).toBe('workspace')
    expect(r.path).toBe('packages/pages/dsh-pmboard/lib/client.js')
  })

  it('②b 绝对路径（工作区外）→ outside', () => {
    const r = normalizeArtifactPath('/etc/passwd', ROOT)
    expect(r.form).toBe('outside')
  })

  it('②c 绝对路径（仓库根下但不在本工作区）→ outside，剥掉仓库根', () => {
    const r = normalizeArtifactPath('/Users/yunpeng/pi-investment/quantsys-v2/main.py', ROOT)
    expect(r.form).toBe('outside')
    expect(r.path).toBe('quantsys-v2/main.py')
  })

  it('③ 跨仓相对路径 → 字符串层保持原样（fs 端点判 outside_workspace）', () => {
    const r = normalizeArtifactPath('quantsys-v2/adapters/inbound/fastapi_app/main.py', ROOT)
    expect(r.form).toBe('workspace')
    expect(r.path).toBe('quantsys-v2/adapters/inbound/fastapi_app/main.py')
  })

  it('④ 伪路径（brace-glob 汇总写法）→ pseudo', () => {
    const r = normalizeArtifactPath('quantsys-v2/tests/{a.py,b.py}', ROOT)
    expect(r.form).toBe('pseudo')
    expect(r.path).toBe('quantsys-v2/tests/{a.py,b.py}')
  })

  it('④b 通配符与空串也是 pseudo', () => {
    expect(normalizeArtifactPath('docs/*.md', ROOT).form).toBe('pseudo')
    expect(normalizeArtifactPath('', ROOT).form).toBe('pseudo')
    expect(normalizeArtifactPath('   ', ROOT).form).toBe('pseudo')
  })
})

describe('normalizeArtifactPath：合规路径原样不变', () => {
  const compliant = [
    'docs/architecture/workflow-stages.md',
    'docs/requirements/REQ-b63a7d/plan.md',
    'packages/pages/dsh-pmboard/src/index.ts',
    'packages/pages/dsh-pmboard/scripts/migrate-ledger.ts',
    'tests/domain/artifact-path.test.ts',
  ]
  for (const p of compliant) {
    it(p, () => {
      const r = normalizeArtifactPath(p, ROOT)
      expect(r.form).toBe('workspace')
      expect(r.path).toBe(p)
    })
  }

  it('./ 前缀与反斜杠被清洗', () => {
    expect(normalizeArtifactPath('./docs/a.md', ROOT).path).toBe('docs/a.md')
    expect(normalizeArtifactPath('agent-dh\\docs\\a.md', ROOT).path).toBe('docs/a.md')
    expect(normalizeArtifactPath('docs/a.md', ROOT).path).toBe('docs/a.md')
  })
})

describe('normalizeArtifactPath：逃逸判定', () => {
  it('.. 逃逸 → outside', () => {
    expect(normalizeArtifactPath('../secrets.md', ROOT).form).toBe('outside')
    expect(normalizeArtifactPath('docs/../../x.md', ROOT).form).toBe('outside')
  })

  it('工作区根自身 → 空路径 + workspace（无文件可读）', () => {
    const r = normalizeArtifactPath(ROOT, ROOT)
    expect(r.path).toBe('')
    expect(r.form).toBe('workspace')
  })
})
