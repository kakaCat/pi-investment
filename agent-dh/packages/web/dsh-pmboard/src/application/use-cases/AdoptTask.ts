/**
 * AdoptTask 用例（补救通道）——把**缺父卡归属**的卡挂到指定父卡下（补 parentId + stageKind）。
 *
 * 为什么需要：卡片角色由「名下有没有子卡」派生（protocol.taskRoleIn / MoveTask.roleOf），
 * parentId 是子卡归属的**唯一字段**；而子卡链是父卡**开工那一刻**才懒展开的。于是归属一旦
 * 写丢（或一张卡该是子卡却不是），现场**没有任何可写入的补救入口**——它只能被当成"存量卡"
 * 去硬走五段状态机，报错还会说"存量卡不允许 todo→done"。本用例提供唯一修复入口：
 * 补 parentId（改挂已有归属需显式 force）。
 *
 * 与既有闸门的关系：本用例**不放松任何既有校验**——
 *   ① 挂载后的任务集重新过 `checkSubtaskInvariants`（INV-1..INV-4），**新增违规即拒**
 *      （拒绝 = mutate 回调抛错 = 不写盘，状态逐字节不变）；
 *   ② 状态合法性单点在 domain：目标卡当前状态必须在**子卡表里仍有出边**（todo/in_progress/
 *      done/canceled），否则挂上去立刻是非法状态（integrating/testing/in_review 不可）。
 *
 * 分层：取数、落库、留痕在本用例；"什么算合法归属"复用 domain / shared 的既有纯函数，不另写一份。
 *
 * @module dsh-pmboard/application/use-cases/AdoptTask
 */
import type { UseCaseDeps } from '../ports.js'
import {
  checkSubtaskInvariants,
  isSubtask,
  normalizeText,
  type TaskRecord,
} from '../../shared/protocol.js'
import { SUBTASK_TRANSITIONS } from '../../domain/task/TaskStatus.js'
import { STAGE_KINDS } from '../../domain/task/SubtaskTemplate.js'
import { fmt } from '../../domain/text/fmt.js'
import { reject, agentIdFromExec, requireLiveDriver, mapAgentError } from '../internal/support.js'
import { openRequirementsFor } from '../internal/window.js'
import { syncRTMYaml } from '../internal/rtm-yaml.js'
import { taskStoreOf } from './queue-access.js'

/** 违规指纹（问题清单去重比较用）：inv + 文案即唯一。 */
const fingerprint = (v: { inv: string; message: string }): string => v.inv + '|' + v.message

export async function executeAdoptTask(deps: UseCaseDeps, args: unknown, exec: unknown): Promise<unknown> {
  const windowKey = agentIdFromExec(deps, exec)
  requireLiveDriver(deps, exec)
  const a = (args ?? {}) as Record<string, unknown>
  const taskId = normalizeText(a.task_id, 'task_id', 64)
  const parentId = normalizeText(a.parent_id, 'parent_id', 64)
  const reason = normalizeText(a.reason, 'reason', 500)
  const stageKindArg = normalizeText(a.stage_kind, 'stage_kind', 32)
  const force = a.force === true

  if (taskId.length === 0) reject('reqboard_task_adopt 未执行：task_id 不能为空', 'REQBOARD_INVALID_INPUT')
  if (parentId.length === 0) reject('reqboard_task_adopt 未执行：parent_id 不能为空', 'REQBOARD_INVALID_INPUT')
  if (taskId === parentId) reject('reqboard_task_adopt 未执行：task_id 与 parent_id 不能是同一张卡', 'REQBOARD_INVALID_INPUT')

  const snapshot = deps.repo.snapshot()
  const bound = openRequirementsFor(snapshot, windowKey)
  if (bound.length === 0) reject('reqboard_task_adopt 未执行：本窗口没有绑定中的需求', 'REQBOARD_NO_BOUND_REQ')

  const store = taskStoreOf(deps)
  const child = await store.get(taskId)
  if (child === undefined) reject(fmt('reqboard_task_adopt 未执行：任务 {id} 不存在', { id: taskId }), 'REQBOARD_TASK_NOT_FOUND')
  const parent = await store.get(parentId)
  if (parent === undefined) reject(fmt('reqboard_task_adopt 未执行：父卡 {id} 不存在', { id: parentId }), 'REQBOARD_TASK_NOT_FOUND')

  const reqId = child.requirementId
  if (parent.requirementId !== reqId) {
    reject(fmt('reqboard_task_adopt 未执行：{c} 属 {r1}，{p} 属 {r2}——跨需求挂载会让队列文件分裂', {
      c: taskId, r1: reqId, p: parentId, r2: parent.requirementId,
    }), 'REQBOARD_INVALID_INPUT')
  }
  if (!bound.some(r => r.id === reqId)) {
    reject(fmt('reqboard_task_adopt 未执行：任务 {id} 不属于本窗口绑定的需求', { id: taskId }), 'REQBOARD_NOT_BOUND_TO_WINDOW')
  }
  // 本仓只有"父卡 → 子卡"两层：子卡不能再当父卡（否则出现第三层）
  if (isSubtask(parent)) {
    reject(fmt('reqboard_task_adopt 未执行：{id} 本身是子卡，不能作为父卡（本仓只有父子两层；要挂到它所在的父卡 {g} 下）', {
      id: parentId, g: String(parent.parentId),
    }), 'REQBOARD_ADOPT_PARENT_IS_SUBTASK')
  }

  const tasks = await store.listByRequirement(reqId)
  const previousParentId = child.parentId !== undefined && child.parentId !== '' ? child.parentId : undefined
  if (previousParentId !== undefined && !force) {
    reject(fmt('reqboard_task_adopt 未执行：{id} 已有父卡 {p}（本入口只补**缺失**归属）。确要改挂：传 force=true 并写明 reason', {
      id: taskId, p: previousParentId,
    }), 'REQBOARD_ADOPT_ALREADY')
  }
  const ownChildren = tasks.filter(t => t.parentId === taskId)
  if (ownChildren.length > 0) {
    reject(fmt('reqboard_task_adopt 未执行：{id} 名下有 {n} 张子卡（{ids}）——把它们变成悬空子卡前先处置（改挂或取消）', {
      id: taskId, n: ownChildren.length, ids: ownChildren.map(t => t.id).join('、'),
    }), 'REQBOARD_ADOPT_HAS_CHILDREN')
  }
  if ((child.dependsOn ?? []).includes(parentId)) {
    reject(fmt('reqboard_task_adopt 未执行：{id} 的 dependsOn 含它要挂的父卡 {p}（自指依赖），先去掉这条依赖', {
      id: taskId, p: parentId,
    }), 'REQBOARD_ADOPT_DEPENDENCY')
  }
  if ((parent.dependsOn ?? []).includes(taskId)) {
    reject(fmt('reqboard_task_adopt 未执行：父卡 {p} 的 dependsOn 含 {id}（挂上去会成环），先去掉这条依赖', {
      p: parentId, id: taskId,
    }), 'REQBOARD_ADOPT_DEPENDENCY')
  }

  // stageKind（INV-2）：卡上已有则沿用；缺省必须显式给，且必须在受控枚举内
  const stageKind = stageKindArg.length > 0 ? stageKindArg : (child.stageKind ?? '')
  if (stageKind.length === 0) {
    reject(fmt('reqboard_task_adopt 未执行：子卡必须有 stageKind（INV-2），请传 stage_kind（受控枚举：{k}）', { k: STAGE_KINDS.join('/') }), 'REQBOARD_INVALID_INPUT')
  }
  if (!STAGE_KINDS.includes(stageKind as (typeof STAGE_KINDS)[number])) {
    reject(fmt('reqboard_task_adopt 未执行：非法 stage_kind「{k}」（受控枚举：{allowed}）', { k: stageKind, allowed: STAGE_KINDS.join('/') }), 'REQBOARD_INVALID_INPUT')
  }

  // 状态合法性（单点在 domain）：挂成子卡后，当前状态必须仍在子卡表里有出边
  if (SUBTASK_TRANSITIONS[child.status].length === 0) {
    reject(fmt('reqboard_task_adopt 未执行：{id} 当前状态 {st} 不是子卡可停留的状态（子卡只有 待开始/开发中/已完成/已取消）——先用 reqboard_task_move 把它退回 in_progress 再挂载', {
      id: taskId, st: child.status,
    }), 'REQBOARD_ADOPT_STATUS')
  }

  const before = new Set(checkSubtaskInvariants(tasks, reqId).map(fingerprint))
  const actor = { kind: 'agent' as const, sessionId: windowKey }
  const at = deps.clock.now()

  // ── ① 任务写（队列是任务的唯一事实源）────────────────────────────────────
  const changed = await store.mutate(reqId, (draft) => {
    const t = draft.find(x => x.id === taskId)
    const p = draft.find(x => x.id === parentId)
    if (t === undefined || p === undefined) return undefined
    // 先在**拟改后的集合**上跑不变量：新增违规即拒（抛错 → mutate 回滚，不写盘）
    const proposed = draft.map(x => (x.id === taskId ? { ...x, parentId, stageKind } : x))
    const added = checkSubtaskInvariants(proposed as readonly TaskRecord[], reqId).filter(v => !before.has(fingerprint(v)))
    if (added.length > 0) {
      reject(fmt('reqboard_task_adopt 未执行：挂载会破坏子卡不变量——{why}', {
        why: added.map(v => v.inv + ' ' + v.message).join('；'),
      }), 'REQBOARD_ADOPT_INVARIANT')
    }
    t.parentId = parentId
    t.stageKind = stageKind as TaskRecord['stageKind']
    t.version += 1
    t.updatedAt = at
    t.updatedBy = actor
    t.comments.push({
      id: deps.ids.comment(),
      body: fmt('[归属] {verb}父卡 {p}（stageKind={k}）{prev}{reason}（reqboard_task_adopt）', {
        verb: previousParentId === undefined ? '挂到' : '改挂到',
        p: parentId,
        k: stageKind,
        prev: previousParentId === undefined ? '' : fmt('，原父卡 {p0}', { p0: previousParentId }),
        reason: reason.length > 0 ? '：' + reason : '',
      }),
      createdAt: at,
      createdBy: actor,
    })
    return draft
  }).catch(mapAgentError)

  const moved = changed.find(t => t.id === taskId)
  if (moved === undefined) reject('reqboard_task_adopt 写入失败：队列状态异常', 'REQBOARD_STORE_INCONSISTENT')

  // ── ② 需求写（留痕：需求评论区可见"谁什么时候补的归属"）──────────────────
  await deps.repo.mutate('requirement-updated', (ledger) => {
    const r = ledger.requirements.find(x => x.id === reqId)
    if (r === undefined) return undefined
    r.comments.push({
      id: deps.ids.comment(),
      body: fmt('[归属补救] {id} {verb}父卡 {p}（stageKind={k}）{prev}{reason}（窗口 {w}）', {
        id: taskId,
        verb: previousParentId === undefined ? '挂到' : '改挂到',
        p: parentId,
        k: stageKind,
        prev: previousParentId === undefined ? '' : fmt('，原父卡 {p0}', { p0: previousParentId }),
        reason: reason.length > 0 ? '：' + reason : '',
        w: windowKey,
      }),
      createdAt: at,
      createdBy: actor,
    })
    r.version += 1
    r.updatedAt = at
    r.updatedBy = actor
    return { requirements: [r] }
  }).catch(mapAgentError)

  // RTM 是增强层，失败不阻断（与 task_move 同口径）
  try {
    syncRTMYaml(deps, await store.listByRequirement(reqId), reqId, 'task:status', { taskId })
  } catch { /* 忽略 */ }

  return {
    success: true,
    task_id: taskId,
    requirement_id: reqId,
    parent_id: parentId,
    previous_parent_id: previousParentId ?? '',
    stage_kind: stageKind,
    role: 'subtask',
    status: moved.status,
    version: moved.version,
    note: fmt('{id} 已{verb}父卡 {p}，角色由「{r0}」变为「子卡」（合法边随之收紧为 todo→in_progress→done）', {
      id: taskId,
      verb: previousParentId === undefined ? '挂到' : '改挂到',
      p: parentId,
      r0: previousParentId === undefined && ownChildren.length === 0 ? '存量卡/顶层卡' : '原有归属',
    }),
  }
}
