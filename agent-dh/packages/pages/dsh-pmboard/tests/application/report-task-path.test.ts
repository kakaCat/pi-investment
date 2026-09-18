/**
 * reqboard_task_report 产物路径归一单测（REQ-b63a7d t2）。
 *
 * 锁定：写入侧一律经 domain 归一层——仓库根相对（agent-dh/…）剥前缀、工作区内绝对路径
 * 转相对、伪路径（brace 汇总写法）不入产物清单、合规路径原样且去重。
 * 此前原样上浮是本需求 403 刷屏的登记侧根因（台账实测 142 条非合规路径）。
 */
import { describe, it, expect } from 'vitest'
import { executeReportTask } from '../../src/application/use-cases/ReportTask.js'
import { FakeDocs, makeHarness, req, task } from './harness.js'

const W = 'session-w-001'
const ROOT = '/ws/agent-dh'

/** 可指定工作区根的假文档仓储（基类固定返回 '.'，掩盖前缀剥离逻辑）。 */
class RootedFakeDocs extends FakeDocs {
  r: string
  constructor(root: string) {
    super(() => 1000)
    this.r = root
  }
  workspaceRoot(): string { return this.r }
}

function setup() {
  const h = makeHarness({
    requirements: [req({ id: 'REQ-000001', status: 'implementing', sourceSessionId: W, artifacts: [] })],
    tasks: [task({ id: 't-000001', requirementId: 'REQ-000001', status: 'in_progress' })],
  })
  h.deps.docs = new RootedFakeDocs(ROOT)
  return h
}

async function run(h: ReturnType<typeof setup>, files: string[]) {
  await executeReportTask(
    h.deps,
    { task_id: 't-000001', summary: '实现', completed: ['做了事'], files_changed: files },
    { agent: { id: W } },
  )
}

function taskOutputPaths(h: ReturnType<typeof setup>): string[] {
  const req0 = h.repo.ledger.requirements[0] as any
  return (req0.artifacts ?? []).filter((a: any) => a.kind === 'task_output').map((a: any) => a.path)
}

describe('报告产物路径归一（REQ-b63a7d t2）', () => {
  it('仓库根相对（agent-dh/…）→ 剥掉重复工作区名前缀后登记', async () => {
    const h = setup()
    await run(h, ['agent-dh/docs/architecture/documentation-standard.md'])
    const paths = taskOutputPaths(h)
    expect(paths).toContain('docs/architecture/documentation-standard.md')
    expect(paths).not.toContain('agent-dh/docs/architecture/documentation-standard.md')
  })

  it('工作区内绝对路径 → 工作区相对', async () => {
    const h = setup()
    await run(h, [ROOT + '/packages/pages/dsh-pmboard/src/index.ts'])
    expect(taskOutputPaths(h)).toContain('packages/pages/dsh-pmboard/src/index.ts')
  })

  it('伪路径（brace 汇总写法）→ 不入产物清单', async () => {
    const h = setup()
    await run(h, ['quantsys-v2/tests/{a.py,b.py}', 'docs/*.md'])
    expect(taskOutputPaths(h)).toEqual([])
  })

  it('合规路径原样不变、./ 被清洗、同路径去重', async () => {
    const h = setup()
    await run(h, [
      'docs/requirements/REQ-000001/plan.md',
      './docs/a.md',
      'docs/requirements/REQ-000001/plan.md',
    ])
    const paths = taskOutputPaths(h)
    expect(paths).toEqual(['docs/requirements/REQ-000001/plan.md', 'docs/a.md'])
  })

  it('工作区之外的绝对路径（/etc/...）不入产物清单', async () => {
    const h = setup()
    await run(h, ['/etc/passwd', '/tmp/scratch.txt'])
    expect(taskOutputPaths(h)).toEqual([])
  })

  it('跨仓相对路径保持原样登记（是否可服务由文件接口用 fs 判定）', async () => {
    const h = setup()
    await run(h, ['quantsys-v2/application/services/watch_engine/engine.py'])
    expect(taskOutputPaths(h)).toContain('quantsys-v2/application/services/watch_engine/engine.py')
  })
})
