/**
 * 产物发现核心（REQ-260924213231-b1c4 T-2 / FR-1）——「需求目录 → 待登记产物」的**唯一**实现。
 *
 * 铁律：docs/requirements/<REQ-id>/ 就是过程文件的唯一容器——**落进目录即成为产物**。
 * 本模块在详情页渲染前/工具登记前扫描目录，把未登记的文件以 kind=notes（或按文件名归入必备种类）
 * 作为待登记条目产出，带 autoDiscovered 标记 + mtime + size。
 *
 * 为什么下沉到 application：此前发现逻辑只长在 adapters/ArtifactSync.ts（I/O 适配层），
 * 于是只有 HTTP 渲染能触发补登——agent 用工具路径走不通（REQ-260924213231 根因）。
 * 现在核心是**纯逻辑**（零 I/O、零 node: 依赖），目录读取一律经 `DocRepository` 端口
 * （application 层禁 import node:，见 tests/layer-boundary.test.ts）。
 *
 * 幂等：同 path 已登记（无论来源）→ 跳过；重复扫描不产生重复条目。
 *
 * @module dsh-pmboard/application/internal/artifact-discovery
 */
import type { DocRepository } from '../ports.js'
import type { ArtifactKind, RequirementRecord, StageArtifact } from '../../shared/protocol.js'
import { kindForRelPath } from '../../domain/artifact/ArtifactSpec.js'
import { normalizeArtifactPath } from '../../domain/artifact/ArtifactPath.js'

// 产物分类规则（kindForRelPath）在 domain/artifact/ArtifactSpec.ts——本模块只负责遍历 + 组装，
// 不在 application 层另立一份分类真相（INV-7）。

type StageKeyLike = StageArtifact['stage']

/** 需求目录相对前缀（工作区相对路径）。 */
export function reqDirRel(reqId: string): string {
  return 'docs/requirements/' + reqId
}

/** 自动发现产物应归属的阶段（必备产物按其阶段；notes 归当前阶段）。 */
export function stageForKind(kind: ArtifactKind, currentStage: StageKeyLike): StageKeyLike {
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

/** 单个已登记产物的最小标识（幂等判定用）。 */
function alreadyRegistered(req: RequirementRecord, path: string): boolean {
  return (req.artifacts ?? []).some(a => a.path === path)
}

/**
 * 已登记自动发现产物里"种类已过期"的条目（REQ-81aabd FR-3）：产物种类由路径推导，
 * 分类规则升级后（如 design/*.md 从 notes 改归 design）旧条目要跟着回填，
 * 否则同一份文件在新旧需求上显示两种种类。仅回填 autoDiscovered 条目——
 * 手工/Agent 登记的产物其 kind 是显式声明，不覆盖。
 *
 * 交由调用方（ArtifactSync 落库回调）复用：判定是纯的，落库不是。
 */
export function staleAutoKind(a: StageArtifact, reqRelPrefix: string): ArtifactKind | undefined {
  if (a.autoDiscovered !== true) return undefined
  const prefix = reqRelPrefix + '/'
  if (!a.path.startsWith(prefix)) return undefined
  const kind = kindForRelPath(a.path.slice(prefix.length))
  return kind === a.kind ? undefined : kind
}

/**
 * 扫描需求目录，返回缺失的产物条目（纯函数，不写盘；调用方决定落库）。
 *
 * 目录遍历全程经 `docs.list(相对目录)`——由实现按自己的 `workspaceRoot` 解析；
 * 目录不存在/条目消失时 list 返回 [] / 跳过（不抛），语义与搬迁前的 try/catch 等价。
 *
 * @param docs         文档仓储端口（唯一 I/O 入口；application 不碰 fs）
 * @param req          需求记录（已登记产物用于幂等跳过；status 决定 notes 归属阶段）
 * @param reqRelPrefix 需求目录的工作区相对前缀（缺省 = reqDirRel(req.id)；兼容旧调用签名）
 */
export function discoverArtifactsFrom(
  docs: DocRepository,
  req: RequirementRecord,
  reqRelPrefix: string = reqDirRel(req.id),
): StageArtifact[] {
  const found: StageArtifact[] = []
  const walk = (relDir: string): void => {
    for (const entry of docs.list(relDir)) {
      if (entry.name.startsWith('.')) continue
      const entryRel = relDir === '' ? entry.name : relDir + '/' + entry.name
      if (!entry.isFile) {
        walk(entryRel)
        continue
      }
      const rel = entryRel.startsWith(reqRelPrefix + '/')
        ? entryRel.slice(reqRelPrefix.length + 1)
        : entryRel
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
  walk(reqRelPrefix)
  return found
}
