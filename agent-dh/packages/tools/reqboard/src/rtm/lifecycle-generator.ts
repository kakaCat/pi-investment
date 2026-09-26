/**
 * rtm-lifecycle.yml 生成（REQ-260926140539-457b FR-2 触发点 1）。
 *
 * 全局节点状态快照：当前阶段 + 七个阶段的状态/时间/已确认产物。
 *
 * @module @pi-investment/reqboard/rtm/lifecycle-generator
 */
import { dirname, resolve } from 'node:path'
import { getRTMPath, readRTM, writeRTM } from './file-io.js'
import type { RTMContext } from './context.js'
import { RTM_STAGE_ORDER, type LifecycleArtifact, type LifecycleStageEntry, type RTMLifecycle, type RTMStageName } from './types.js'

/** 台账状态 → 流水线阶段（archived 归到 done）。 */
export function stageOfStatus(status: string): RTMStageName {
  if (status === 'archived' || status === 'done') return 'done'
  return (RTM_STAGE_ORDER as readonly string[]).includes(status) ? (status as RTMStageName) : 'draft'
}

/** 产物 kind → 它属于哪个阶段的产出。 */
function stageOfArtifact(kind: string, stage?: string): RTMStageName {
  if (stage !== undefined && (RTM_STAGE_ORDER as readonly string[]).includes(stage)) return stage as RTMStageName
  switch (kind) {
    case 'requirement':
      return 'brainstorming'
    case 'design':
      return 'design'
    case 'plan':
    case 'decomposition':
      return 'decomposing'
    case 'task_detail':
    case 'task_output':
      return 'implementing'
    case 'verification':
      return 'accepting'
    case 'archive':
      return 'done'
    default:
      return 'draft'
  }
}

/** 生成/更新 rtm-lifecycle.yml。 */
export function generateLifecycleRTM(ctx: RTMContext, reqId: string): RTMLifecycle {
  const filePath = getRTMPath(ctx.reqDir(reqId), 'rtm-lifecycle.yml')
  const existing = readRTM<RTMLifecycle>(filePath)
  const req = ctx.requirement(reqId)
  const currentStage = stageOfStatus(req?.status ?? 'draft')
  const currentIdx = RTM_STAGE_ORDER.indexOf(currentStage)
  // "这个需求有多少个节点"：分类档案启用的节点（缺省 = 全流水线）。
  const enabledStages = ctx.enabledStages(reqId)
  const enabledSet = new Set<string>(enabledStages)

  const byStage = new Map<RTMStageName, LifecycleArtifact[]>()
  for (const a of req?.artifacts ?? []) {
    const st = stageOfArtifact(a.kind, a.stage)
    const list = byStage.get(st) ?? []
    list.push({
      kind: a.kind,
      ...(a.path.length > 0 ? { path: a.path } : {}),
      ...(a.confirmedAt !== undefined ? { confirmed_at: ctx.iso(a.confirmedAt) } : {}),
      ...(a.approvedAt !== undefined ? { approved_at: ctx.iso(a.approvedAt) } : {}),
    })
    byStage.set(st, list)
  }

  const stages: LifecycleStageEntry[] = RTM_STAGE_ORDER.map((stage, idx) => {
    const status = idx < currentIdx ? 'completed' : idx === currentIdx ? 'in_progress' : 'pending'
    const entry: LifecycleStageEntry = { stage, status, enabled: enabledSet.has(stage) }
    if (status !== 'pending') entry.entered_at = ctx.iso(req?.createdAt ?? ctx.now())
    else delete entry.entered_at
    if (status === 'completed') entry.completed_at = ctx.iso(req?.updatedAt ?? ctx.now())
    const artifacts = byStage.get(stage)
    if (artifacts !== undefined && artifacts.length > 0) entry.artifacts = artifacts
    return entry
  })

  const data: RTMLifecycle = {
    requirement: {
      id: reqId,
      title: req?.title ?? '',
      category: req?.category ?? '',
      created_at: ctx.iso(req?.createdAt ?? ctx.now()),
      // 绑定窗口（台账投影）：未绑定时**不写空串**——缺省即"未绑定"，不伪造。
      ...(typeof req?.sourceSessionId === 'string' && req.sourceSessionId.length > 0
        ? { source_session: req.sourceSessionId }
        : {}),
      // 绝对路径自定位：filePath 是**实际写入的那个路径**再 resolve——相对根下也指向同一处。
      dir: dirname(resolve(filePath)),
    },
    lifecycle: {
      current_stage: currentStage,
      stage_count: enabledStages.length,
      stage_list: [...enabledStages],
      stages,
    },
    metadata: ctx.metadata('lifecycle', reqId, existing, {
      rtm_version: '1.0',
      file_path: resolve(filePath),
    }),
  }
  writeRTM(filePath, data)
  return data
}
