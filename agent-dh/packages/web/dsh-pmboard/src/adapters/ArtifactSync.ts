/**
 * 需求目录产物自动发现（**适配器薄壳**；REQ-2e9473 t11/W4 / REQ-260924213231-b1c4 T-2）。
 *
 * 铁律：docs/requirements/<REQ-id>/ 就是过程文件的唯一容器——**落进目录即成为产物**。
 * 本模块在详情页/概览/看板渲染前触发扫描，把核心返回的待登记条目**落库**（补登 + 回填过期种类 + 写评论）。
 *
 * 设计动机（REQ-6f39b5 事故 E）：agent 用 write 直接写的原型 html 不进"文档记录"，
 * 用户在 01:57 喊"没有把html放到文档中"才手工补——清单靠手工维护必漏。
 *
 * 分层（REQ-260924213231-b1c4 T-2）：发现逻辑（目录→条目）已下沉为
 * `application/internal/artifact-discovery.ts` 的 `discoverArtifactsFrom(docs, req)` 纯函数，
 * 本层只剩「构造 DocRepository → 调核心 → 落库」。**行为零变更**：既有路径/幂等/评论逐字保持，
 * 只是不再有第二份发现真相（工具入口 T-3 复用同一核心）。
 *
 * 幂等：同 path 已登记（无论来源）→ 跳过；重复扫描不产生重复条目。
 *
 * @module dsh-pmboard/adapters/ArtifactSync
 */
import { newCommentId } from '../shared/protocol.js'
import type { RequirementRecord, StageArtifact } from '../shared/protocol.js'
import { fmt } from '../domain/text/fmt.js'
import { FileDocRepository } from '../adapters/FileDocRepository.js'
import {
  discoverArtifactsFrom,
  reqDirRel,
  stageForKind,
  staleAutoKind,
} from '../application/internal/artifact-discovery.js'
import type { JsonLedgerRepository } from './JsonLedgerRepository.js'

// 需求目录相对前缀与分类规则的真身已迁至 application/internal/artifact-discovery.ts 与
// domain/artifact/ArtifactSpec.ts——这里只再导出，保持既有 import 点不变。
export { reqDirRel }

type StageKeyLike = StageArtifact['stage']

/**
 * 由旧签名（绝对 reqRoot + 工作区相对前缀）反推工作区根，使
 * `docs.list(工作区相对前缀)` 解析出的绝对目录恰为 reqRoot。
 * 仅兼容 `discoverArtifacts` 的既有调用点（生产路径 `syncReqArtifacts` 直接传 cwd）。
 */
function workspaceRootOf(reqRoot: string, reqRelPrefix: string): string {
  const suffix = '/' + reqRelPrefix.replace(/\\/g, '/')
  const normalized = reqRoot.replace(/\\/g, '/').replace(/\/+$/, '')
  return normalized.endsWith(suffix)
    ? normalized.slice(0, normalized.length - suffix.length) || '/'
    : reqRoot
}

/**
 * 兼容入口：扫描需求目录，返回缺失的产物条目（纯函数，不写盘；调用方决定落库）。
 * @param reqRoot 工作区绝对路径下的 docs/requirements/<REQ-id> 目录绝对路径
 * @param reqRelPrefix 该目录的工作区相对前缀（如 docs/requirements/REQ-xxxxxx）
 */
export function discoverArtifacts(
  req: RequirementRecord,
  reqRoot: string,
  reqRelPrefix: string,
): StageArtifact[] {
  const docs = new FileDocRepository({ workspaceRoot: workspaceRootOf(reqRoot, reqRelPrefix) })
  return discoverArtifactsFrom(docs, req, reqRelPrefix)
}

/**
 * 同步单个需求的目录产物（写入台账）。幂等：已在登记表的 path 不再补登。
 * @returns 本次新登记的产物条数
 */
export async function syncReqArtifacts(
  store: JsonLedgerRepository,
  reqId: string,
  cwd: string = process.cwd(),
): Promise<number> {
  const docs = new FileDocRepository({ workspaceRoot: cwd })
  const reqRel = reqDirRel(reqId)
  const snapshot = store.snapshot()
  const req = snapshot.requirements.find(r => r.id === reqId)
  if (req === undefined) return 0
  const discovered = discoverArtifactsFrom(docs, req)
  const stale = (req.artifacts ?? []).some(a => staleAutoKind(a, reqRel) !== undefined)
  if (discovered.length === 0 && !stale) return 0
  const result = await store.mutate('requirement-updated', (ledger) => {
    const r = ledger.requirements.find(x => x.id === reqId)
    if (r === undefined) return undefined
    r.artifacts ??= []
    let reclassified = 0
    for (const a of r.artifacts) {
      const kind = staleAutoKind(a, reqRel)
      if (kind === undefined) continue
      a.kind = kind
      a.stage = stageForKind(kind, r.status as StageKeyLike)
      reclassified += 1
    }
    const added: StageArtifact[] = []
    for (const a of discovered) {
      if (r.artifacts.some(x => x.path === a.path)) continue
      r.artifacts.push(a)
      added.push(a)
    }
    if (added.length === 0 && !stale) return undefined
    r.comments.push({
      id: newCommentId(),
      body: fmt(
        '[产物自动发现] 扫描需求目录：补登 {n} 个过程产物、回填 {m} 个过期种类（落进 docs/requirements/{id}/ 即产物）：\n{list}',
        {
          n: added.length,
          m: reclassified,
          id: reqId,
          list: added.map(a => '- ' + a.path + '（' + a.kind + '）').join('\n'),
        },
      ),
      createdAt: Date.now(),
      createdBy: { kind: 'system' },
    })
    r.version += 1
    r.updatedAt = Date.now()
    return { requirements: [r] }
  })
  return result.changed.requirements.length > 0 ? discovered.length : 0
}

/** 同步全部需求的目录产物（board 状态端点调用；每个需求目录不存在则跳过）。 */
export async function syncAllReqArtifacts(
  store: JsonLedgerRepository,
  cwd: string = process.cwd(),
): Promise<number> {
  const ids = store.snapshot().requirements.map(r => r.id)
  let total = 0
  for (const id of ids) {
    total += await syncReqArtifacts(store, id, cwd)
  }
  return total
}
