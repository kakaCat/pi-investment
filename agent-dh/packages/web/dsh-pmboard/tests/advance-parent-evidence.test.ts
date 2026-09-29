/**
 * 父卡收尾凭证基准回归（2026-09-28 实机缺陷）。
 *
 * 缺陷：`assertDoneEvidence` 的子卡路径早已改用「不可变出身」（需求/父卡/子卡 createdAt 最小值）
 * 作为新鲜度基准，父卡路径却仍用 `claimedAt ?? createdAt`。轻档手工交付（先干活、后认领）时
 * claimedAt 晚于交付文件的 mtime → 父卡在 FINALIZE_PARENT 恒被判 REQBOARD_NO_EVIDENCE，链卡死。
 * 线上实测：REQ-260928222643-4d34 的 t-dd5ba9 开工 14:59:53 晚于 board-entry.ts 交付 14:58:45，
 * 链推进 9 张子卡后停在父卡收尾，autoRun 被置 false。
 *
 * 本文件锁定两条：① 交付早于认领仍能收尾（根因修复）；② 真「无证据」时仍被拦（门没被放水）。
 */
import { describe, it, expect } from 'vitest'
import { advanceRequirement } from '../src/application/use-cases/AdvanceChain.js'
import type { WorkflowRunner } from '../src/application/ports.js'
import { makeHarness, task, req } from './application/harness.js'
import type { TaskRecord } from '../src/shared/protocol.js'

const FILE = 'src/domain/x.ts'
const MISSING = 'src/domain/nope.ts'

/** 占位 runner：本文件用例的子卡都已 done，链只走收尾/rollup，不应触发任何子卡 run。 */
const noopRunner: WorkflowRunner = {
  async start() { return { ok: false, reason: 'unused: 本用例不应触发子卡 run' } },
}

/** 造一个「交付早于认领」的父卡：交付 mtime=1000，父卡认领 claimedAt=2000，链侧无工具痕迹。 */
function seedDeliveredBeforeClaim(subFiles: string) {
  const h = makeHarness()
  h.docs.put(FILE, 'x', 1000)
  h.repo.ledger.requirements = [req({ id: 'REQ-000001', status: 'implementing', category: 'feature', autoRun: true })]
  const parent = task({
    id: 't-p', requirementId: 'REQ-000001', status: 'in_progress',
    title: '父卡', claimedAt: 2000, claimedBy: 'session-w-001',
  })
  const subs: TaskRecord[] = ['dev', 'integrate', 'review', 'test'].map((stage, i) => task({
    id: 't-s' + String(i + 1), requirementId: 'REQ-000001', parentId: 't-p', stageKind: stage as never,
    status: 'done', createdAt: 500,
    lastReport: { at: 1500, reportIndex: 1, filesChanged: [subFiles], completed: ['完成'] },
  }))
  h.seedTasks('REQ-000001', [parent, ...subs])
  h.deps.workflow = noopRunner
  // 链侧 windowKey='system'：真实环境没有本窗口工具痕迹 → 只能靠文件证据（这正是缺陷现场）。
  h.session.activity = 0
  return h
}

function parentOf(h: ReturnType<typeof makeHarness>): TaskRecord {
  const raw = JSON.parse(h.queueRepo.rawOf('REQ-000001')!) as { tasks: TaskRecord[] }
  const t = raw.tasks.find((x) => x.id === 't-p')
  if (t === undefined) throw new Error('父卡 t-p 不在队列里')
  return t
}

describe('父卡收尾凭证基准（不可变出身，父子同口径）', () => {
  it('交付早于认领（手工交付）：父卡仍能收尾并 rollup 进验收', async () => {
    const h = seedDeliveredBeforeClaim(FILE)
    const out = await advanceRequirement(h.deps, 'REQ-000001')
    const fin = out.steps.find((s) => s.event === 'FINALIZE_PARENT')
    expect(fin?.outcome).toBe('ok')
    expect(out.stopped).toBe('rollup')
    expect(parentOf(h).status).toBe('done')
  })

  it('真无证据（上报文件不存在且无工具痕迹）：父卡仍被拦在 done 之外', async () => {
    const h = seedDeliveredBeforeClaim(MISSING)
    const out = await advanceRequirement(h.deps, 'REQ-000001')
    expect(out.stopped).toBe('paused')
    expect(parentOf(h).status).toBe('in_progress')
  })
})
