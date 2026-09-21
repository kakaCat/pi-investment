/**
 * 验收结果表回填（REQ-308b9a FR-7 / AC-7.7、7.8）。
 *
 * 裁决落库后重渲染 verification.md（把「验收结果」表按最新裁决回填）。
 * 两条通道（弹框 / 看板）共用本单点，避免各写一份渲染逻辑漂移。
 *
 * 无 docs 端口（测试/降级）→ 静默跳过（返回 false），不阻断裁决主流程。
 *
 * @module dsh-pmboard/application/internal/verification-doc-writer
 */
import type { DocRepository, LedgerView } from '../ports.js'
import { renderVerificationDoc } from '../../domain/workflow/VerificationDoc.js'
import { checkDocCompleteness } from '../../domain/workflow/DocCompleteness.js'

export interface VerificationDocPorts {
  /** 台账仓储（只读快照） */
  repo: { snapshot(): LedgerView }
  /** 缺省 → 跳过（不阻断） */
  docs?: DocRepository
}

/** 重写 docs/requirements/<reqId>/verification.md；返回是否真的写了。 */
export async function rewriteVerificationDoc(ports: VerificationDocPorts, reqId: string): Promise<boolean> {
  const docs = ports.docs
  if (docs === undefined) return false
  const snap = ports.repo.snapshot()
  const req = snap.requirements.find(r => r.id === reqId)
  const sheet = req?.verification?.sheet
  if (req === undefined || sheet === undefined) return false

  const reqDir = 'docs/requirements/' + reqId
  const collect = (sub: string): string[] => docs.list(sub.length > 0 ? reqDir + '/' + sub : reqDir)
    .filter(e => e.isFile)
    .map(e => (sub.length > 0 ? sub + '/' + e.name : e.name))
  const files = new Set<string>([
    ...collect(''), ...collect('design'), ...collect('tasks'), ...collect('reviews'), ...collect('tests'),
  ])
  const tasks = snap.tasks.filter(t => t.requirementId === reqId && t.status !== 'canceled')
  const taskById = new Map(tasks.map(t => [t.id, t]))
  const items = sheet.items.map(it => {
    const src = it.source
    const t = src.kind === 'task' ? taskById.get(src.taskId) : undefined
    const who = it.decidedBy === undefined
      ? undefined
      : [it.decidedBy.kind, it.decidedBy.sessionId].filter(v => v !== undefined && v !== '').join('/')
    return {
      id: it.id,
      title: src.kind === 'task' ? (t?.title ?? src.taskId) : '需求级验收',
      criterion: it.criterion,
      howToVerify: src.kind === 'task' ? (t?.acceptance ?? it.criterion) : it.criterion,
      status: it.status,
      ...(it.opinion !== undefined ? { opinion: it.opinion } : {}),
      ...(who !== undefined ? { decidedBy: who } : {}),
      ...(it.decidedAt !== undefined ? { decidedAt: it.decidedAt } : {}),
    }
  })
  await docs.write(reqDir + '/verification.md', renderVerificationDoc({
    reqId,
    title: req.title,
    summary: req.verification?.summary ?? '',
    sheetVersion: sheet.version,
    items: items as never,
    testReport: req.verification?.evidence ?? [],
    docCheck: checkDocCompleteness({ files, taskIds: tasks.map(t => t.id) }),
  }))
  return true
}
