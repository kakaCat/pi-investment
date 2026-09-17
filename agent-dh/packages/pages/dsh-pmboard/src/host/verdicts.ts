/**
 * 验收单逐项裁决（REQ-2e9473 W6 补充）：路由（看板勾选）与会话工具（弹框答复）
 * 共用的**单一实现**——避免两条通道逻辑漂移。
 *
 * 语义：逐项 passed/failed（不通过必填意见）→ 有不通过项则需求打回 implementing +
 * 为每个未过项自动生成关联返工任务（承接原任务 phase/side/scope + 意见）。
 *
 * @module dsh-pmboard/host/verdicts
 */
import {
  asScope, newTaskId, recordStatus,
  type ActorRef, type ReqboardLedger, type RequirementRecord, type TaskRecord,
} from '../shared/protocol.js'

export interface VerdictInput {
  itemId: string
  status: 'passed' | 'failed'
  opinion?: string
}

export interface ApplyVerdictsResult {
  requirement: RequirementRecord
  reworkTasks: TaskRecord[]
  pending: number
  passed: number
  failed: number
}

export class VerdictError extends Error {
  readonly code: string
  constructor(message: string, code: string) {
    super(message)
    this.code = code
  }
}

/**
 * 在 mutate 内应用逐项裁决（就地修改 ledger）。
 * @param actor 裁决人（看板=human / 会话弹框=human+sessionId）
 * @param commentId 评论 id 生成器
 */
export function applyVerdicts(
  ledger: ReqboardLedger,
  reqId: string,
  version: number,
  verdicts: readonly VerdictInput[],
  actor: ActorRef,
  nowTs: number,
  commentId: () => string,
): ApplyVerdictsResult {
  const r = ledger.requirements.find(x => x.id === reqId)
  if (r === undefined) throw new VerdictError('需求 ' + reqId + ' 不存在', 'not_found')
  if (r.status !== 'accepting' && r.status !== 'implementing') {
    throw new VerdictError('需求 ' + reqId + ' 当前处于 ' + r.status + '，不在验收/返工态（先提交验收单）', 'bad_status')
  }
  const v = r.verification
  if (v === undefined || v.sheet === undefined) {
    throw new VerdictError('需求 ' + reqId + ' 还没有验收单（先 reqboard_verify_submit）', 'no_sheet')
  }
  const sheet = v.sheet
  if (sheet.version !== version) {
    throw new VerdictError('验收单版本不匹配：当前 v' + sheet.version + '，收到 v' + version + '（防并发错版）', 'version_mismatch')
  }
  const failedItems: { item: (typeof sheet.items)[number] }[] = []
  for (const verdict of verdicts) {
    const item = sheet.items.find(i => i.id === verdict.itemId)
    if (item === undefined) throw new VerdictError('验收项 ' + verdict.itemId + ' 不存在', 'item_not_found')
    if (verdict.status === 'failed' && (verdict.opinion ?? '').length === 0) {
      throw new VerdictError('不通过的验收项必须写意见（' + item.id + '）', 'opinion_required')
    }
    item.status = verdict.status
    if ((verdict.opinion ?? '').length > 0) item.opinion = verdict.opinion
    item.decidedAt = nowTs
    item.decidedBy = actor
    if (verdict.status === 'failed') failedItems.push({ item })
  }
  const pending = sheet.items.filter(i => i.status === 'pending').length
  const reworkTasks: TaskRecord[] = []
  if (failedItems.length > 0 && r.status === 'accepting') {
    for (const { item } of failedItems) {
      const orig = ledger.tasks.find(t => t.id === item.source)
      let tid = newTaskId()
      for (let g = 0; g < 50 && ledger.tasks.some(t => t.id === tid); g++) tid = newTaskId()
      const task: TaskRecord = {
        id: tid,
        requirementId: r.id,
        title: '返工：' + (orig?.title ?? item.criterion).slice(0, 60),
        description: '验收不通过项返工（v' + sheet.version + ' 项 ' + item.id + '）：' + item.criterion,
        phase: (orig?.phase ?? 'implement') as TaskRecord['phase'],
        side: (orig?.side ?? 'fullstack') as TaskRecord['side'],
        dependsOn: [],
        scope: orig?.scope ?? asScope({}),
        acceptance: item.criterion,
        implementation: '按验收意见修复：' + (item.opinion ?? '（见验收单）'),
        context: '承接自 ' + (item.source === 'requirement' ? '需求级验收项' : '任务 ' + item.source) + '；验收意见：' + (item.opinion ?? ''),
        status: 'todo',
        blocked: false,
        executions: [],
        comments: [],
        version: 1,
        createdAt: nowTs,
        updatedAt: nowTs,
        createdBy: actor,
        updatedBy: actor,
      }
      recordStatus(task, 'todo', nowTs, actor, '验收不通过 → 自动生成返工任务（W6）')
      ledger.tasks.push(task)
      reworkTasks.push(task)
    }
    r.status = 'implementing'
    r.version += 1
    r.updatedAt = nowTs
    r.updatedBy = actor
    recordStatus(r, 'implementing', nowTs, actor, '验收单 ' + failedItems.length + ' 项不通过 → 打回返工（自动生成 ' + reworkTasks.length + ' 个返工任务）')
    r.comments.push({
      id: commentId(),
      body: '[验收单] v' + sheet.version + ' 逐项裁决：' + failedItems.length + ' 项不通过 → 打回实施。\n'
        + failedItems.map(f => '- ✗ ' + f.item.criterion + '：' + (f.item.opinion ?? '')).join('\n')
        + '\n返工任务：' + reworkTasks.map(t => t.id).join('、'),
      createdAt: nowTs,
      createdBy: actor,
    })
  } else {
    r.version += 1
    r.updatedAt = nowTs
    r.updatedBy = actor
    const passed = sheet.items.filter(i => i.status === 'passed').length
    r.comments.push({
      id: commentId(),
      body: '[验收单] v' + sheet.version + ' 逐项裁决：通过 ' + passed + ' 项，待验 ' + pending + ' 项'
        + (pending === 0 ? '（全部通过 → 可点「验收通过」归档）' : '（挂起，稍后从断点续验）'),
      createdAt: nowTs,
      createdBy: actor,
    })
  }
  return {
    requirement: r,
    reworkTasks,
    pending,
    passed: sheet.items.filter(i => i.status === 'passed').length,
    failed: sheet.items.filter(i => i.status === 'failed').length,
  }
}
