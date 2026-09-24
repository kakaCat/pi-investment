/**
 * SubmitDesignArtifacts 用例（T-3，REQ-260924213231-b1c4 / FR-1 / I-1）——
 * `reqboard_submit(kind=design)` 的登记编排：幂等登记 + 逐份登记态投影。
 *
 * 为什么需要它：设计文档此前只能靠 HTTP 渲染路径（ArtifactSync）补登，agent 在
 * run_code 里不打开看板就登记不了（REQ-260924213231 根因）。本用例把「扫需求目录 → 登记」
 * 接进工具面，与 adapters/ArtifactSync 共用同一发现核心 `discoverArtifactsFrom`（T-2），
 * 不再有第二份发现真相。
 *
 * 语义（interfaces.md I-1）：
 *   - `path` 缺省 → 扫 `docs/requirements/<REQ>/design/*.md`（发现核心过滤 kind=design）；
 *   - `path` 给了 → 只登记该份（仍走 `assertArtifactOpenable` 可打开性校验）；
 *   - 幂等：同 path 已登记 → 跳过，`registered_count` 只数**本次新登记**；
 *   - 目录不存在 / 无 .md → `registered_count=0` 且 `success=false` + 如实说明，**不谎报成功**。
 *
 * @module dsh-pmboard/application/use-cases/SubmitDesignArtifacts
 */
import type { UseCaseDeps } from '../ports.js'
import { normalizeText, type StageArtifact } from '../../shared/protocol.js'
import { openRequirementsFor } from '../internal/window.js'
import { registerArtifact } from '../internal/artifact-gates.js'
import { discoverArtifactsFrom } from '../internal/artifact-discovery.js'
import { assertArtifactOpenable } from '../internal/content-gate-wiring.js'
import { designDocPolicyOf, designDocRegistration } from '../internal/design-docs.js'
import { fmt } from '../../domain/text/fmt.js'
import {
  reject,
  agentIdFromExec,
  requireLiveDriver,
  notifyArtifactRegistered,
} from '../internal/support.js'

/** design/ 目录下可作为设计文档登记的文件名（只认 .md，隐藏文件跳过）。 */
function designDocNames(deps: UseCaseDeps, reqId: string): string[] {
  const dir = 'docs/requirements/' + reqId + '/design'
  return deps.docs.list(dir)
    .filter(e => e.isFile !== false && (e.name ?? '').endsWith('.md'))
    .map(e => e.name ?? '')
    .filter(n => n.length > 0)
}

export async function submitDesignArtifacts(deps: UseCaseDeps, args: unknown, exec: any): Promise<unknown> {
  const windowKey = agentIdFromExec(deps, exec)
  requireLiveDriver(deps, exec)
  const a = (args ?? {}) as { requirement_id?: unknown; path?: unknown }
  const explicitId = normalizeText(a.requirement_id, 'requirement_id', 64)
  const explicitPath = normalizeText(a.path, 'path', 400)

  const snapshot = deps.repo.snapshot()
  const bound = openRequirementsFor(snapshot, windowKey)
  if (bound.length === 0) reject('reqboard_submit(kind=design) 未执行：本窗口没有绑定中的需求', 'REQBOARD_NO_BOUND_REQ')
  const target = explicitId.length > 0 ? bound.find(r => r.id === explicitId) : bound[0]
  if (target === undefined) {
    reject(
      fmt('reqboard_submit(kind=design) 未执行：需求 {id} 不是本窗口绑定的进行中需求', { id: explicitId }),
      'REQBOARD_NOT_BOUND_TO_WINDOW',
    )
  }

  const nowTs = deps.clock.now()
  const registeredBy = { kind: 'agent' as const, sessionId: windowKey }
  const designDir = 'docs/requirements/' + target.id + '/design'

  // ── 待登记条目 ─────────────────────────────────────────────────────────
  // 显式 path：单份登记（仍走可打开性校验，形态/存在性当场响亮失败）。
  // 缺省：复用产物发现核心扫需求目录，过滤 kind=design（只认 design/*.md，不登记其他阶段产物）。
  const candidates: StageArtifact[] = []
  if (explicitPath.length > 0) {
    const path = assertArtifactOpenable(deps.docs, explicitPath)
    candidates.push({ stage: 'design', kind: 'design', path, registeredAt: nowTs, registeredBy })
  } else {
    for (const found of discoverArtifactsFrom(deps.docs, target)) {
      if (found.kind !== 'design' || found.path.length === 0) continue
      candidates.push({
        stage: 'design',
        kind: 'design',
        path: found.path,
        registeredAt: nowTs,
        registeredBy,
      })
    }
  }

  // ── 一次 mutate 登记全部新条目（幂等：同 stage+kind+path 已存在 → registerArtifact 返回 false）──
  // 登记前记下已有 design 路径：本次新增 = candidates − priorDesignPaths（与 registerArtifact 返回 true 等价）。
  const priorDesignPaths = new Set(
    (target.artifacts ?? []).filter(x => x.stage === 'design' && x.kind === 'design').map(x => x.path),
  )
  await deps.repo.mutate('requirement-updated', (ledger) => {
    const req = ledger.requirements.find(r => r.id === target.id)
    if (req === undefined) return undefined
    const added: StageArtifact[] = []
    for (const c of candidates) {
      if (registerArtifact(req, c)) added.push(c)
    }
    if (added.length === 0) return undefined
    req.comments.push({
      id: deps.ids.comment(),
      body: '[设计文档] 登记 ' + added.length + ' 份设计产物（kind=design）：\n'
        + added.map(x => '- ' + x.path).join('\n'),
      createdAt: nowTs,
      createdBy: { kind: 'agent', sessionId: windowKey },
    })
    req.version += 1
    req.updatedAt = nowTs
    req.updatedBy = { kind: 'agent', sessionId: windowKey }
    return { requirements: [req] }
  })
  const added = candidates.filter(c => !priorDesignPaths.has(c.path))
  const reqNow = deps.repo.snapshot().requirements.find(r => r.id === target.id) ?? target

  // ── 逐份登记态投影（磁盘 / 产物簿 / 确认章三源，I-1 返回体）────────────────
  const onDisk = designDocNames(deps, target.id)
  const policy = await designDocPolicyOf(deps.docs, reqNow)
  const designDocs = designDocRegistration(reqNow, reqNow.category, policy, onDisk)

  for (const art of added) notifyArtifactRegistered(deps, target.id, art)

  const anyOnDisk = designDocs.some(d => d.on_disk)
  const registeredCount = added.length
  const ok = anyOnDisk || registeredCount > 0
  return {
    success: ok,
    requirement_id: target.id,
    design_docs: designDocs,
    registered_count: registeredCount,
    note: ok
      ? (registeredCount > 0
          ? '已登记 ' + registeredCount + ' 份设计文档（kind=design）。下一步：调 reqboard_ask_confirm（target=artifact, kind=design）弹框请人确认设计——一次确认 = 全部设计文档成组落章，确认后进入拆分'
          : '设计文档此前均已登记（幂等命中，本次新登记 0 份）。下一步：调 reqboard_ask_confirm（target=artifact, kind=design）请人确认设计')
      : '未发现可登记的设计文档：' + designDir + '/ 目录不存在或没有 .md 文件——请先把设计文档落盘，再调 reqboard_submit(kind=design)（本次未登记任何产物，不谎报成功）',
  }
}
