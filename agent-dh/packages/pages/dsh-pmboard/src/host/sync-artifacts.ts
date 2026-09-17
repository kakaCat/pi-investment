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
 * @module dsh-pmboard/host/sync-artifacts
 */
import { readdirSync, statSync } from 'node:fs'
import { join, relative } from 'node:path'
import { newCommentId } from '../shared/protocol.js'
import type { ArtifactKind, RequirementRecord, StageArtifact } from '../shared/protocol.js'
import type { ReqboardStore } from './store.js'

/** 文件名 → 必备产物种类映射（未命中 → notes）。 */
const NAME_TO_KIND: ReadonlyArray<readonly [RegExp, ArtifactKind]> = [
  [/^requirement\.md$/, 'requirement'],
  [/^plan\.md$/, 'plan'],
  [/^decomposition\.md$/, 'decomposition'],
  [/^verification\.md$/, 'verification'],
  [/^archive\.md$/, 'archive'],
  [/^tasks\/t-[a-z0-9]+\.md$/, 'task_detail'],
]

/** 从相对需求目录的路径推断产物种类。 */
export function kindForRelPath(rel: string): ArtifactKind {
  for (const [re, kind] of NAME_TO_KIND) {
    if (re.test(rel)) return kind
  }
  return 'notes'
}

/** 自动发现产物应归属的阶段（必备产物按其阶段；notes 归当前阶段）。 */
function stageForKind(kind: ArtifactKind, currentStage: StageKeyLike): StageKeyLike {
  switch (kind) {
    case 'requirement': return 'brainstorming'
    case 'plan': return 'planning'
    case 'decomposition': return 'decomposing'
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
  const walk = (absDir: string): void => {
    let entries: string[]
    try {
      entries = readdirSync(absDir)
    } catch {
      return // 目录不存在 → 无产物可发现
    }
    for (const name of entries) {
      if (name.startsWith('.')) continue
      const abs = join(absDir, name)
      let st: ReturnType<typeof statSync>
      try {
        st = statSync(abs)
      } catch {
        continue
      }
      if (st.isDirectory()) {
        walk(abs)
        continue
      }
      if (!st.isFile()) continue
      const rel = relative(reqRoot, abs).split(/[\\/]/).join('/')
      const workspacePath = reqRelPrefix + '/' + rel
      if (alreadyRegistered(req, workspacePath)) continue
      const kind = kindForRelPath(rel)
      found.push({
        stage: stageForKind(kind, req.status as StageKeyLike),
        kind,
        path: workspacePath,
        registeredAt: Date.now(),
        registeredBy: { kind: 'system' },
        autoDiscovered: true,
        fileMtime: st.mtimeMs,
        fileSize: st.size,
      })
    }
  }
  walk(reqRoot)
  return found
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
  store: ReqboardStore,
  reqId: string,
  cwd: string = process.cwd(),
): Promise<number> {
  const reqRoot = join(cwd, reqDirRel(reqId))
  const snapshot = store.snapshot()
  const req = snapshot.requirements.find(r => r.id === reqId)
  if (req === undefined) return 0
  const discovered = discoverArtifacts(req, reqRoot, reqDirRel(reqId))
  if (discovered.length === 0) return 0
  const result = await store.mutate('requirement-updated', (ledger) => {
    const r = ledger.requirements.find(x => x.id === reqId)
    if (r === undefined) return undefined
    r.artifacts ??= []
    const added: StageArtifact[] = []
    for (const a of discovered) {
      if (r.artifacts.some(x => x.path === a.path)) continue
      r.artifacts.push(a)
      added.push(a)
    }
    if (added.length === 0) return undefined
    r.comments.push({
      id: newCommentId(),
      body: '[产物自动发现] 扫描需求目录补登 ' + added.length + ' 个过程产物（落进 docs/requirements/'
        + reqId + '/ 即产物）：\n' + added.map(a => '- ' + a.path + '（' + a.kind + '）').join('\n'),
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
  store: ReqboardStore,
  cwd: string = process.cwd(),
): Promise<number> {
  const ids = store.snapshot().requirements.map(r => r.id)
  let total = 0
  for (const id of ids) {
    total += await syncReqArtifacts(store, id, cwd)
  }
  return total
}
