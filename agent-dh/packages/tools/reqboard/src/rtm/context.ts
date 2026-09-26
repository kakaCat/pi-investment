/**
 * RTM 生成上下文（REQ-260926140539-457b FR-2 / FR-3）。
 *
 * 把"数据从哪来"收敛到一个只读端口：台账（需求/任务/产物）+ 需求目录文档。
 * 生成器只依赖本上下文，不直接读 dsh-reqboard.json、不 import dsh-pmboard，
 * 因此可以脱离运行实例用临时目录单测（t1-t20 的可测性基础）。
 *
 * @module @pi-investment/reqboard/rtm/context
 */
import { existsSync, readFileSync, readdirSync, statSync } from 'node:fs'
import { join } from 'node:path'
import { requirementsDir } from './file-io.js'
import { parseDecompositionServes, parseRequirementFRs, type ParseFile } from './parser.js'
import { RTM_STAGE_ORDER, type FR, type RTMMetadata, type RTMStageName, type RTMTaskLike } from './types.js'

/** 测试策略类文档名（不计入设计章节覆盖度）。 */
const TEST_DOC_NAMES = new Set(['test-cases.md', 'verification.md', 'test.md'])

/** 台账产物的最小投影。 */
export interface LedgerArtifactLike {
  kind: string
  path: string
  /** 产物所属节点（dsh-pmboard StageArtifact.stage）。 */
  stage?: string
  confirmedAt?: number
  registeredAt?: number
  approvedAt?: number
}

/** 台账需求的最小投影。 */
export interface LedgerRequirementLike {
  id: string
  title: string
  category: string
  status: string
  createdAt?: number
  updatedAt?: number
  /** 立项绑定窗口（窗口↔需求的需求侧锚点）；缺省 = 未绑定窗口。 */
  sourceSessionId?: string
  artifacts?: LedgerArtifactLike[]
}

/** 只读台账端口（真实实现见 dsh-pmboard 的适配器）。 */
export interface LedgerReader {
  requirement(reqId: string): LedgerRequirementLike | undefined
  tasksOf(reqId: string): RTMTaskLike[]
}

/** 生成器配置。 */
export interface RTMGeneratorConfig {
  /** 工作区根（docs/requirements 的父目录）。 */
  workspaceRoot: string
  /**
   * 本需求启用哪些节点（分类流程档案的投影）——"这个需求有多少个节点"的唯一来源。
   * 缺省 = 全流水线（RTM_STAGE_ORDER）。**由调用方注入**：档案住在 dsh-pmboard
   * （CATEGORY_FLOW_PROFILES），本包不反向依赖它。
   */
  enabledStagesOf?: (category: string | undefined) => readonly string[]
  ledger: LedgerReader
  /** 时钟（测试可注入固定时间）。 */
  clock?: () => number
  generatedBy?: string
}

/** 生成上下文：路径、时钟、文档读取、台账投影。 */
export class RTMContext {
  private readonly decompositionCache = new Map<string, Record<string, string[]>>()

  constructor(readonly config: RTMGeneratorConfig) {}

  /** 需求目录绝对路径。 */
  reqDir(reqId: string): string {
    return requirementsDir(this.config.workspaceRoot, reqId)
  }

  /** 当前毫秒时间戳。 */
  now(): number {
    return this.config.clock ? this.config.clock() : Date.now()
  }

  /** ISO 8601 时间串。 */
  iso(ts?: number): string {
    return new Date(ts ?? this.now()).toISOString()
  }

  generatedBy(): string {
    return this.config.generatedBy ?? 'rtm-generator'
  }

  requirement(reqId: string): LedgerRequirementLike | undefined {
    return this.config.ledger.requirement(reqId)
  }

  /** 本需求任务；serves 缺失时用 decomposition.md §1 对照表补齐。 */
  tasks(reqId: string): RTMTaskLike[] {
    const raw = this.config.ledger.tasksOf(reqId) ?? []
    const fromPlan = this.decompositionServes(reqId)
    return raw.map(t => {
      const serves = [...new Set([...(t.serves ?? []), ...(fromPlan[t.id] ?? [])])]
      return { ...t, serves }
    })
  }

  /** decomposition.md §1「根编号 ↔ 任务卡」对照表。 */
  decompositionServes(reqId: string): Record<string, string[]> {
    const hit = this.decompositionCache.get(reqId)
    if (hit !== undefined) return hit
    const content = this.readDoc(reqId, 'decomposition.md')
    const parsed = content === null ? {} : parseDecompositionServes(content)
    this.decompositionCache.set(reqId, parsed)
    return parsed
  }

  /** 读取需求目录内文档；不存在返回 null。 */
  readDoc(reqId: string, rel: string): string | null {
    const p = join(this.reqDir(reqId), rel)
    try {
      if (!existsSync(p) || !statSync(p).isFile()) return null
      return readFileSync(p, 'utf-8')
    } catch {
      return null
    }
  }

  /**
   * 本需求启用的节点清单（按分类档案过滤 RTM_STAGE_ORDER，保持流水线顺序）。
   * 档案缺失/空集 → 回落全流水线（宁多不少，不静默把节点藏掉）。
   */
  enabledStages(reqId: string): readonly RTMStageName[] {
    const profile = this.config.enabledStagesOf?.(this.requirement(reqId)?.category)
    if (profile === undefined || profile.length === 0) return RTM_STAGE_ORDER
    const kept = RTM_STAGE_ORDER.filter(s => profile.includes(s))
    return kept.length > 0 ? kept : RTM_STAGE_ORDER
  }

  /** requirement.md 里的 FR 列表（缺失时返回空）。 */
  requirementFRs(reqId: string): FR[] {
    const content = this.readDoc(reqId, 'requirement.md')
    if (content === null) return []
    return parseRequirementFRs(content, 'requirement.md')
  }

  /** design/ 下所有 markdown 文件（路径为需求目录内相对路径）。
   *  测试策略类文档（test-cases.md）不是可实施的设计单元，排除在设计覆盖度之外。 */
  designFiles(reqId: string): ParseFile[] {
    return this.markdownIn(reqId, 'design').filter(f => !TEST_DOC_NAMES.has(f.path.split('/').pop() ?? ''))
  }

  /** 列某个子目录下的 markdown（相对路径前缀保留）。 */
  markdownIn(reqId: string, sub: string): ParseFile[] {
    const dir = join(this.reqDir(reqId), sub)
    if (!existsSync(dir)) return []
    const out: ParseFile[] = []
    let entries: string[]
    try {
      entries = readdirSync(dir)
    } catch {
      return []
    }
    for (const name of entries.sort()) {
      if (!name.endsWith('.md')) continue
      const rel = `${sub}/${name}`
      const content = this.readDoc(reqId, rel)
      if (content !== null) out.push({ path: rel, content })
    }
    return out
  }

  /** 测试类文档：verification.md + design/test-cases.md + tasks/*.md + tests/*.md。
   *  test-evidence.md 这类**测试证据**按本仓约定落在 tests/ 下（covers:/validates: 标注在那里），
   *  不扫它会让测试覆盖度恒为 0——FR-4 Level 3 / FR-5 的口径。 */
  testFiles(reqId: string): ParseFile[] {
    const out: ParseFile[] = []
    for (const rel of ['verification.md', 'design/test-cases.md', 'test-cases.md']) {
      const content = this.readDoc(reqId, rel)
      if (content !== null) out.push({ path: rel, content })
    }
    out.push(...this.markdownIn(reqId, 'tasks'))
    out.push(...this.markdownIn(reqId, 'tests'))
    return out
  }

  /** 组装元数据块（保留首版 generated_at）。 */
  metadata(
    stage: string,
    reqId: string,
    existing: { metadata?: RTMMetadata } | null,
    extra?: Partial<RTMMetadata>,
  ): RTMMetadata {
    const prevGeneratedAt = existing?.metadata?.generated_at
    return {
      stage,
      requirement_id: reqId,
      generated_at: typeof prevGeneratedAt === 'string' ? prevGeneratedAt : this.iso(),
      version: 0,
      generated_by: this.generatedBy(),
      ...(extra ?? {}),
    }
  }
}
