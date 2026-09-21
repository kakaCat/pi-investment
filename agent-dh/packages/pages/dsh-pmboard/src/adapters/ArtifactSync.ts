/**
 * 需求目录产物自动发现（REQ-2e9473 t11/W4）。
 *
 * 铁律：docs/requirements/<REQ-id>/ 就是过程文件的唯一容器——**落进目录即成为产物**。
 * 本模块在详情页渲染前扫描目录，把未登记的文件以 kind=notes（或按文件名归入必备种类）
 * 自动补登到 req.artifacts，带 autoDiscovered 标记 + mtime + size。
 *
 * 设计动机（REQ-6f39b5 事故 E）：agent 用 write 直接写的原型 html 不进"文档记录"，
 * 用户在 01:57 喊"没有把html放到文档中"才手工补——清单靠手工维护必漏。自动推导后
 * 结构上不可能再漏：文件在目录里 = 文档记录区可见。
 *
 * 幂等：同 path 已登记（无论来源）→ 跳过；重复扫描不产生重复条目。
 *
 * REQ-47939a t9：由 host/sync-artifacts.ts **逐字搬入** adapters（fs 扫描=I/O，唯一入口在此层；
 * 分类规则 kindForRelPath 仍在 domain/artifact/ArtifactSpec.ts）。行为零改动。
 *
 * @module dsh-pmboard/adapters/ArtifactSync
 */
import { join, relative } from 'node:path'
import { newCommentId } from '../shared/protocol.js'
import type { ArtifactKind, RequirementRecord, StageArtifact } from '../shared/protocol.js'
import { kindForRelPath } from '../domain/artifact/ArtifactSpec.js'
import { normalizeArtifactPath } from '../domain/artifact/ArtifactPath.js'
import { fmt } from '../domain/text/fmt.js'
import { FileDocRepository } from '../adapters/FileDocRepository.js'
import type { JsonLedgerRepository } from './JsonLedgerRepository.js'

// 产物分类规则（kindForRelPath）在 domain/artifact/ArtifactSpec.ts（REQ-47939a t2）——本模块只负责
// fs 扫描（INV-7）。t9 起不再从这里再导出：调用方直接从 domain 取（单点实现）。

/** 自动发现产物应归属的阶段（必备产物按其阶段；notes 归当前阶段）。 */
function stageForKind(kind: ArtifactKind, currentStage: StageKeyLike): StageKeyLike {
  switch (kind) {
    case 'requirement': return 'brainstorming'
    case 'plan': return 'design'
    case 'decomposition': return 'decomposing'
    case 'design': return 'design'
    case 'task_detail': return 'implementing'
    case 'verification': return 'accepting'
    case 'archive': return 'archived'
    default: return currentStage
  }
}

type StageKeyLike = StageArtifact['stage']

/** 单个已登记产物的最小标识（幂等判定用）。 */
function alreadyRegistered(req: RequirementRecord, path: string): boolean {
  return (req.artifacts ?? []).some(a => a.path === path)
}

/**
 * 扫描需求目录，返回缺失的产物条目（纯函数，不写盘；调用方决定落库）。
 * @param reqRoot 工作区绝对路径下的 docs/requirements/<REQ-id> 目录绝对路径
 * @param reqRelPrefix 该目录的工作区相对前缀（如 docs/requirements/REQ-xxxxxx）
 */
export function discoverArtifacts(
  req: RequirementRecord,
  reqRoot: string,
  reqRelPrefix: string,
): StageArtifact[] {
  const found: StageArtifact[] = []
  // 目录扫描经 adapters/FileDocRepository（REQ-47939a t5）——list 已吞掉"目录不存在/条目消失"
  // （返回 [] / 跳过），语义与搬迁前的 try/catch 等价。reqRoot 为绝对路径，故 root 用 '/'。
  const docs = new FileDocRepository({ workspaceRoot: '/' })
  const walk = (absDir: string): void => {
    for (const entry of docs.list(absDir)) {
      if (entry.name.startsWith('.')) continue
      const abs = join(absDir, entry.name)
      if (!entry.isFile) {
        walk(abs)
        continue
      }
      const rel = relative(reqRoot, abs).split(/[\\/]/).join('/')
      const workspacePath = reqRelPrefix + '/' + rel
      // REQ-2d1c74 FR-5：防御性形态过滤——扫描来源本身保证文件存在，但 brace/越界形态
      // （如文件名带 {}*）不登记，与 submit 入口的 assertArtifactOpenable 同口径。
      if (normalizeArtifactPath(workspacePath, '/').form !== 'workspace') continue
      if (alreadyRegistered(req, workspacePath)) continue
      const kind = kindForRelPath(rel)
      found.push({
        stage: stageForKind(kind, req.status as StageKeyLike),
        kind,
        path: workspacePath,
        registeredAt: Date.now(),
        registeredBy: { kind: 'system' },
        autoDiscovered: true,
        fileMtime: entry.mtimeMs,
        fileSize: entry.size,
      })
    }
  }
  walk(reqRoot)
  return found
}

/**
 * 已登记自动发现产物里"种类已过期"的条目（REQ-81aabd FR-3）：产物种类由路径推导，
 * 分类规则升级后（如 design/*.md 从 notes 改归 design）旧条目要跟着回填，
 * 否则同一份文件在新旧需求上显示两种种类。仅回填 autoDiscovered 条目——
 * 手工/Agent 登记的产物其 kind 是显式声明，不覆盖。
 */
function staleAutoKind(a: StageArtifact, reqRelPrefix: string): ArtifactKind | undefined {
  if (a.autoDiscovered !== true) return undefined
  const prefix = reqRelPrefix + '/'
  if (!a.path.startsWith(prefix)) return undefined
  const kind = kindForRelPath(a.path.slice(prefix.length))
  return kind === a.kind ? undefined : kind
}

/** 需求目录相对前缀（工作区相对路径）。 */
export function reqDirRel(reqId: string): string {
  return 'docs/requirements/' + reqId
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
  const reqRoot = join(cwd, reqDirRel(reqId))
  const snapshot = store.snapshot()
  const req = snapshot.requirements.find(r => r.id === reqId)
  if (req === undefined) return 0
  const discovered = discoverArtifacts(req, reqRoot, reqDirRel(reqId))
  const stale = (req.artifacts ?? []).some(a => staleAutoKind(a, reqDirRel(reqId)) !== undefined)
  if (discovered.length === 0 && !stale) return 0
  const result = await store.mutate('requirement-updated', (ledger) => {
    const r = ledger.requirements.find(x => x.id === reqId)
    if (r === undefined) return undefined
    r.artifacts ??= []
    let reclassified = 0
    for (const a of r.artifacts) {
      const kind = staleAutoKind(a, reqDirRel(reqId))
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
