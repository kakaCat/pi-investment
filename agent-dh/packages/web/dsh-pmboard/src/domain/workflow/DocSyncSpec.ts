/**
 * 文档同步规约（REQ-47939a t3 / INV-7，REQ-2e9473 t19/W8）。
 *
 * 一条规则：上游文档变更 → 下游文档标"待同步"；下游重交后销标；未销标时推进/验收给出警告。
 *   requirement 变更 → plan / decomposition 待同步；
 *   plan        变更 → decomposition 待同步。
 * 从 host/agent-tools.ts 的三处 inline 逻辑收敛到本文件——此前 plan_submit / requirement_submit
 * / decompose 各写一遍 filter+push，规则一改要改三处（D2）。
 *
 * 纯函数 / 就地修改入参记录（调用方已在 store.mutate 的草稿对象上操作）；不碰时间与随机数。
 */

/** 变更源。 */
import { fmt } from '../text/fmt.js'
export type DocSyncSource = 'requirement' | 'plan'
/** 可被标记为待同步的下游产物。 */
export type DocSyncDownstream = 'plan' | 'decomposition'

/** 待同步标记（结构对齐 shared/protocol.ts 的 DocSyncPending）。 */
export interface DocSyncPendingLike {
  source: string
  downstream: string[]
  reason: string
  at: number
}

export interface DocSyncArtifactLike {
  kind: string
}

/** 记录本规约所需的最小投影。 */
export interface DocSyncReqLike {
  docSyncPending?: DocSyncPendingLike[]
  artifacts?: readonly DocSyncArtifactLike[]
}

/**
 * 上游变更 → 下游待同步种类。
 * requirement 变更 → 已登记的 plan / decomposition；plan 变更 → 已登记的 decomposition。
 */
export function docSyncDownstream(changed: DocSyncSource, artifacts: readonly DocSyncArtifactLike[] | undefined): DocSyncDownstream[] {
  const has = (k: string) => (artifacts ?? []).some(x => x.kind === k)
  if (changed === 'plan') return has('decomposition') ? ['decomposition'] : []
  const out: DocSyncDownstream[] = []
  if (has('plan')) out.push('plan')
  if (has('decomposition')) out.push('decomposition')
  return out
}

/** 记录一次上游变更：同源旧标记替换为新标记（下游按当时产物重新计算）。 */
export function applyDocSync(req: DocSyncReqLike, changed: DocSyncSource, reason: string, at: number): void {
  const downstream = docSyncDownstream(changed, req.artifacts)
  req.docSyncPending = [
    ...(req.docSyncPending ?? []).filter(p => p.source !== changed),
    { source: changed, downstream, reason, at },
  ]
}

/** 销标：重交下游产物即完成该方向的同步（清除所有把 downstream 列为待同步的标记）。 */
export function clearDocSync(req: DocSyncReqLike, downstream: DocSyncDownstream): void {
  req.docSyncPending = (req.docSyncPending ?? []).filter(p => !p.downstream.includes(downstream))
}

/** 待同步清单（无标记 → 空数组）。 */
export function docSyncPendingOf(req: DocSyncReqLike): DocSyncPendingLike[] {
  return req.docSyncPending ?? []
}

/** 待同步警告正文（调用方按需追加提示尾巴）。 */
export function docSyncSummary(req: DocSyncReqLike): string {
  const detail = (req.docSyncPending ?? [])
    .map(p => fmt('{source}→{downstream}', { source: p.source, downstream: p.downstream.join('/') || '-' }))
    .join('；')
  return fmt('⏳ 文档待同步：{detail}', { detail })
}
