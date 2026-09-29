import { askConfirm } from './src/application/use-cases/AskConfirm.js'
import { advanceRequirement } from './src/application/use-cases/AdvanceChain.js'
import { DEFAULT_CONFIRM_OPTIONS } from './src/domain/text/labels.js'
import { makeHarness, req } from './tests/application/harness.js'

const FILE = 'src/domain/x.ts'
const exec = { agent: { id: 'session-w-001' } }
const OK = { ok: true, value: { ok: true, output: JSON.stringify({ filesChanged: [FILE], completed: ['子卡完成'] }) } }

function seed() {
  const h = makeHarness()
  h.docs.put(FILE, 'x')
  h.repo.ledger.requirements = [req({
    id: 'REQ-000001', status: 'decomposing', category: 'feature', sourceSessionId: 'session-w-001',
    artifacts: [{ stage: 'decomposing', kind: 'decomposition', path: 'docs/requirements/REQ-000001/decomposition.md', registeredAt: 1, registeredBy: { kind: 'agent', sessionId: 'session-w-001' } }],
    plan: { path: 'docs/requirements/REQ-000001/decomposition.md', summary: 's', tasks: [{ key: 't1', title: '实现', phase: 'implement', side: 'backend', dependsOn: [], acceptance: 'a', implementation: 'i' }], submittedAt: h.clock.t, submittedBy: { kind: 'agent', sessionId: 'session-w-001' } },
  })]
  h.repo.ledger.tasks = []
  h.deps.workflow = { start: async () => OK } as never
  h.questions.answers = [{ selected: [DEFAULT_CONFIRM_OPTIONS[0] as string] }]
  return h
}

async function main() {
  const h = seed()
  await askConfirm(h.deps, { requirement_id: 'REQ-000001', target: 'plan', question: '批准？' }, exec)
  console.log('after approve: status=', h.repo.ledger.requirements[0]!.status, 'tasks=', h.repo.ledger.tasks.length)
  const out = await advanceRequirement(h.deps, 'REQ-000001', exec)
  console.log('advance stopped=', out.stopped, 'steps=', JSON.stringify(out.steps.map(s => ({e: s.event, o: s.outcome, d: s.detail}))))
  const r = h.repo.ledger.requirements[0]!
  console.log('final status=', r.status, 'autoRun=', r.autoRun, 'pausedReason=', r.advance?.pausedReason)
  for (const t of h.repo.ledger.tasks) console.log('TASK', t.id, 'parent=', t.parentId, 'stage=', t.stageKind, 'status=', t.status, 'exec=', JSON.stringify(t.executions.map(e => ({ outcome: e.outcome, sessionId: e.sessionId, startSrc: e.tokenUsage?.start?.source, endSrc: e.tokenUsage?.end?.source, delta: e.tokenUsage?.delta !== undefined }))))
}
main().catch(e => { console.error('ERR', e) })
