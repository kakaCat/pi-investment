/**
 * 节点边界 · 同窗口 surface 整段替换执行模型（REQ-422af1 t9 / G7 / D-10 / INV-9）。
 *
 * 做什么：节点结算时在**同一个窗口**里把模型可见的上下文整段遗弃，替换成「下一节点输入包」
 * （路由提示词 + 需求文档投影 + 台账投影）。会话 id 不变、事件日志不丢（回放仍可还原）。
 *
 * 分层（tests/layer-boundary.test.ts 机械门禁）：application 层**禁止** import
 * \`@deepseek-ai/*\`，故 surface 原语（Session.append / surface.nodes / 边界检查）一律经
 * {@link NodeIsolationPort} 端口，实现落在 adapters/NodeIsolationAdapter.ts。
 *
 * ── 已实测的框架不变量（父窗口裁决 D-15，2026-09-17）──────────────────────────
 * dsh-session@0.1.5-rc.1 的 canonical surface contract 拒绝让 user/message 遮蔽 surface 节点 0
 * （系统提示词），错误原文（lib/types/surface.js:338 / lib/index.js:382）：
 *
 *   surface replace: node 0 holds the system prompt and may be rewritten only by a
 *   system/message over exactly that node
 *
 * 故整段替换的合法区间 = **首个非 system 的 surface 节点 → surface 末尾**
 * （sourceEventSeqs = 被遮蔽区间全部节点）。替换后模型可见面 = [系统段, 输入包]——
 * 与 requirement.md §3.6 ③「模型看到的只剩系统段 + 这份输入包」一致；系统段本就是
 * 我们的阶段提示词注入处，保留它是目标而非妥协。（路线 B 的 compactRegion 走同一
 * append replace 契约，同样过不了该不变量，已排除。）
 *
 * ── 三条纪律（design/architecture.md §5）────────────────────────────────────
 *  ① 先落盘再遗弃：调 req.persistArtifacts() 拿到产物写入事件 seq 之后才做替换（T27）。
 *  ② 边界必须配对平衡：不平衡 → 拒绝执行 + 结构化错误，不替换（T25）。
 *  ③ 只在轮次边界执行：agent 忙碌 → 不替换、留痕、不抛异常（T26）。
 *
 * ── D-12 降级链（三条路径都不静默）──────────────────────────────────────────
 *  ① 能触达 Session → 本模块做整段替换；
 *  ② 触达不到（无端口 / reachable()=false）→ 返回「请开新窗口 + 输入包文本」的文字路径（T28）；
 *  ③ 兜底（不替换）：输入包文本仍然完整返回，调用方可做"同窗口文档自足 + 重注入"。
 *
 * ── 给 t10 的硬约束（实测）──────────────────────────────────────────────────
 * Session.append 拒绝"发布中重入"（lib/index.js:1183
 * \`session append cannot reenter while another append is being published\`）——调用方
 * **必须把隔离动作移出 session/event 派发**（如 turn/end 后 queueMicrotask/setImmediate），
 * 否则同步 append 必被拒。本模块只负责时机判定（port.idle()），不负责调度。
 *
 * @module dsh-pmboard/application/use-cases/IsolateNodeContext
 */
import type { Clock, DocRepository, ReqboardRepository } from '../ports.js'
import { openRequirementsFor } from '../internal/window.js'
import {
  buildNodeInputPackage,
  newWindowInstruction,
  requirementDocPath,
} from '../internal/node-input-package.js'
import type { Category, Difficulty, PromptStage } from '../../domain/prompt/index.js'
import { fmt } from '../../domain/text/fmt.js'
import type { RequirementRecord } from '../../shared/protocol.js'

export * from '../internal/node-input-package.js'

// ---------------------------------------------------------------------------
// 端口（实现：adapters/NodeIsolationAdapter.ts）
// ---------------------------------------------------------------------------

/** 模型可见 surface 上的一个节点（会话事件 seq + 事件类型）。 */
export interface SurfaceNode {
  readonly seq: number
  readonly type: string
}

/**
 * 节点隔离会话端口——surface 原语的唯一 I/O 入口。
 * 实现者负责把框架契约（节点 0 保护、sourceEventSeqs 完整覆盖、tool/result 只能改 content）
 * 如实遵守并在违反时**抛出**（本模块捕获后结构化报出，不静默）。
 */
export interface NodeIsolationPort {
  /** 是否触达得到 Session/agent 句柄（D-12 ①/② 判定）。 */
  reachable(): boolean
  /** agent 是否空闲（轮次边界）；活动轮次 → false。 */
  idle(): boolean
  /** 当前 surface 节点（模型可见顺序）。读不到事件类型 → 抛错（响亮）。 */
  surface(): readonly SurfaceNode[]
  /** 切在 seq **之前**是否 tool 调用/结果配对平衡。 */
  balancedBefore(seq: number): boolean
  /** 切在 seq **之后**是否 tool 调用/结果配对平衡。 */
  balancedAfter(seq: number): boolean
  /**
   * 执行 append('user/message', 输入包) + surfaceOp replace(start..end)，
   * sourceEventSeqs = shadowed；返回新事件 seq。框架拒绝必须抛出（不得吞）。
   */
  replace(input: { start: number; end: number; text: string; shadowed: readonly number[] }): number
}

/** 一次隔离尝试的留痕（T25/T26/T28 的"留痕"；成功也记）。 */
export interface IsolationTraceEntry {
  at: number
  windowKey: string
  stage: string
  /** replaced / skipped / rejected / fallback */
  status: IsolationStatus
  code?: string
  reason: string
  routeKey: string
  packageChars: number
  range?: { start: number; end: number }
  artifactSeq?: number
  replacementSeq?: number
}

/** 留痕端口（t10 接到 logger / 注入留痕；未注入 = 本模块不落痕，但结果体仍带 trace）。 */
export interface IsolationTracePort {
  record(entry: IsolationTraceEntry): void
}

// ---------------------------------------------------------------------------
// 请求 / 结果
// ---------------------------------------------------------------------------

export interface IsolateNodeContextRequest {
  windowKey: string
  /** 下一节点（要注入其提示词并作为新起点）。 */
  stage: PromptStage
  difficulty?: Difficulty
  category?: Category
  budget?: number
  /** 归属需求 id；缺省取本窗口最近的进行中需求。 */
  requirementId?: string
  /**
   * 先落盘再遗弃（纪律 ①）：调用方在此写入当前节点产物（文档 / 台账），
   * 返回该**产物写入事件**的 seq。返回值非有限数 → 视为未落盘，不执行替换。
   */
  persistArtifacts: () => number | Promise<number>
}

export type IsolationStatus = 'replaced' | 'skipped' | 'rejected' | 'fallback'

export interface IsolateNodeContextResult {
  status: IsolationStatus
  /** 是否真的执行了整段替换。 */
  replaced: boolean
  /** 结构化错误码（非 replaced 时必有）。 */
  code?: string
  /** 人类可读说明（非 replaced 时必有）。 */
  message?: string
  routeKey: string
  fragmentIds: readonly string[]
  /** 节点输入包文本——**任何路径都返回**（D-12 ②/③ 都要靠它）。 */
  packageText: string
  /** 被替换的 surface 区间（仅 replaced）。 */
  range?: { start: number; end: number }
  /** 产物写入事件 seq（先落盘）。 */
  artifactSeq?: number
  /** 替换事件 seq（后遗弃）。 */
  replacementSeq?: number
  /** D-12 ②：请开新窗口并粘贴输入包的完整指引（仅 fallback）。 */
  fallbackInstruction?: string
  /** 本次尝试的留痕条目（与 trace 端口收到的一致）。 */
  trace: IsolationTraceEntry
}

// ---------------------------------------------------------------------------
// 用例
// ---------------------------------------------------------------------------

export interface IsolateNodeContextDeps {
  repo: ReqboardRepository
  docs: DocRepository
  clock: Clock
  /** 触达能力端口；未注入 = 触达不到（走 D-12 ②）。 */
  isolation?: NodeIsolationPort
  /** 留痕端口；未注入 = 只在结果体里留痕。 */
  trace?: IsolationTracePort
}

function pickRequirement(
  repo: ReqboardRepository,
  windowKey: string,
  explicitId: string | undefined,
): RequirementRecord | undefined {
  const ledger = repo.snapshot()
  if (explicitId !== undefined && explicitId.length > 0) {
    const byId = ledger.requirements.find(r => r.id === explicitId)
    if (byId !== undefined) return byId
  }
  const open = openRequirementsFor(ledger, windowKey)
  return [...open].sort((a, b) => b.updatedAt - a.updatedAt)[0]
}

/**
 * 节点边界隔离：构造输入包 → 判时机/边界 → 先落盘 → 整段替换。
 * **任何失败都只结构化返回，不抛未捕获异常**（节点结算点不得中断流水线）。
 */
export async function isolateNodeContext(
  deps: IsolateNodeContextDeps,
  request: IsolateNodeContextRequest,
): Promise<IsolateNodeContextResult> {
  const stage = request.stage
  const requirement = pickRequirement(deps.repo, request.windowKey, request.requirementId)
  const docPath = requirementDocPath(requirement)
  const docText = docPath.length > 0 ? await safeReadDoc(deps.docs, docPath) : ''
  const pkg = buildNodeInputPackage({
    stage,
    ...(request.difficulty === undefined ? {} : { difficulty: request.difficulty }),
    ...(request.category === undefined ? {} : { category: request.category }),
    ...(request.budget === undefined ? {} : { budget: request.budget }),
    ...(requirement === undefined ? {} : { requirement }),
    requirementDoc: docText,
    requirementDocPath: docPath,
  })

  const base = {
    at: deps.clock.now(),
    windowKey: request.windowKey,
    stage,
    routeKey: pkg.resolved.routeKey,
    packageChars: pkg.text.length,
  }
  const finish = (
    status: IsolationStatus,
    extra: Partial<IsolateNodeContextResult> & { code?: string; message?: string; reason: string },
  ): IsolateNodeContextResult => {
    const { reason, ...rest } = extra
    const trace: IsolationTraceEntry = {
      ...base,
      status,
      reason,
      ...(rest.code === undefined ? {} : { code: rest.code }),
      ...(rest.range === undefined ? {} : { range: rest.range }),
      ...(rest.artifactSeq === undefined ? {} : { artifactSeq: rest.artifactSeq }),
      ...(rest.replacementSeq === undefined ? {} : { replacementSeq: rest.replacementSeq }),
    }
    try { deps.trace?.record(trace) } catch { /* 留痕失败不得中断流水线 */ }
    return {
      status,
      replaced: status === 'replaced',
      routeKey: pkg.resolved.routeKey,
      fragmentIds: pkg.resolved.fragmentIds,
      packageText: pkg.text,
      trace,
      ...(rest.code === undefined ? {} : { code: rest.code }),
      ...(rest.message === undefined ? {} : { message: rest.message }),
      ...(rest.range === undefined ? {} : { range: rest.range }),
      ...(rest.artifactSeq === undefined ? {} : { artifactSeq: rest.artifactSeq }),
      ...(rest.replacementSeq === undefined ? {} : { replacementSeq: rest.replacementSeq }),
      ...(rest.fallbackInstruction === undefined ? {} : { fallbackInstruction: rest.fallbackInstruction }),
    }
  }

  try {
    // ── D-12 ①：触达能力探测 ──────────────────────────────────────────────
    const port = deps.isolation
    if (port === undefined || !port.reachable()) {
      return finish('fallback', {
        code: 'isolation_unreachable',
        reason: '会话 surface 触达不到（D-12 ②）',
        message: fmt('节点隔离未执行：触达不到会话 surface，已降级为「请开新窗口 + 输入包」（路由键 {routeKey}）', { routeKey: pkg.resolved.routeKey }),
        fallbackInstruction: newWindowInstruction(pkg.text),
      })
    }

    // ── 纪律 ③：只在轮次边界（agent 空闲）执行 ────────────────────────────
    if (!port.idle()) {
      return finish('skipped', {
        code: 'agent_busy',
        reason: 'agent 忙碌（活动轮次），跳过替换',
        message: '节点隔离未执行：agent 忙碌（活动轮次），不替换；留痕已记录。',
      })
    }

    // ── 合法替换区间：跳过受保护的系统首节点（D-15）───────────────────────
    const nodes = port.surface()
    const startIdx = nodes.findIndex(n => n.type !== 'system/message')
    if (startIdx < 0 || nodes.length === 0) {
      return finish('skipped', {
        code: 'no_replaceable_range',
        reason: 'surface 上没有可遗弃的历史节点（只有系统段或空）',
        message: '节点隔离未执行：surface 上没有可遗弃的历史节点（只有系统段/空），无需替换。',
      })
    }
    const start = nodes[startIdx]!.seq
    const end = nodes[nodes.length - 1]!.seq
    const range = { start, end }

    // ── 纪律 ②：边界配对平衡（不平衡 → 拒绝执行 + 结构化错误）─────────────
    let balanced: boolean
    try {
      balanced = port.balancedBefore(start) && port.balancedAfter(end)
    } catch (error) {
      return finish('rejected', {
        code: 'boundary_check_failed',
        reason: fmt('边界检查抛错：{err}', { err: errorMessage(error) }),
        message: fmt('节点隔离未执行：边界检查无法完成（{err}）', { err: errorMessage(error) }),
      })
    }
    if (!balanced) {
      return finish('rejected', {
        code: 'boundary_unbalanced',
        reason: '起止边界存在未配对的 tool 调用/结果',
        message: fmt(
          '节点隔离未执行：surface 区间 [{start}, {end}] 边界 tool 配对不平衡（存在未配对的 tool 调用/结果），按纪律拒绝替换。',
          { start, end },
        ),
        range,
      })
    }

    // ── 纪律 ①：先落盘再遗弃（产物写入必须先于替换）───────────────────────
    let artifactSeq: number
    try {
      artifactSeq = await request.persistArtifacts()
    } catch (error) {
      return finish('skipped', {
        code: 'artifact_persist_failed',
        reason: fmt('产物落盘失败：{err}', { err: errorMessage(error) }),
        message: fmt('节点隔离未执行：产物落盘失败（{err}），先落盘后遗弃，不可先遗弃。', { err: errorMessage(error) }),
      })
    }
    if (!Number.isFinite(artifactSeq)) {
      return finish('skipped', {
        code: 'artifact_seq_invalid',
        reason: fmt('产物写入事件 seq 无效：{seq}', { seq: String(artifactSeq) }),
        message: fmt('节点隔离未执行：产物写入事件 seq 无效（{seq}）。', { seq: String(artifactSeq) }),
      })
    }

    // ── 执行整段替换（框架拒绝 → 结构化报出）──────────────────────────────
    let replacementSeq: number
    try {
      replacementSeq = port.replace({
        start,
        end,
        text: pkg.text,
        shadowed: nodes.slice(startIdx).map(n => n.seq),
      })
    } catch (error) {
      return finish('rejected', {
        code: 'framework_rejected',
        reason: fmt('框架拒绝 surface 替换：{err}', { err: errorMessage(error) }),
        message: fmt('节点隔离未执行：框架拒绝 surface 替换（{err}）。', { err: errorMessage(error) }),
        range,
        artifactSeq,
      })
    }
    if (!Number.isFinite(replacementSeq)) {
      return finish('rejected', {
        code: 'replacement_seq_invalid',
        reason: fmt('替换事件 seq 无效：{seq}', { seq: String(replacementSeq) }),
        message: fmt('节点隔离未执行：替换事件 seq 无效（{seq}）。', { seq: String(replacementSeq) }),
        range,
        artifactSeq,
      })
    }

    return finish('replaced', {
      reason: fmt('已整段替换 surface[{start}, {end}] 为节点输入包', { start, end }),
      message: fmt('节点隔离完成：surface 区间 [{start}, {end}] 已替换为节点输入包。', { start, end }),
      range,
      artifactSeq,
      replacementSeq,
      // 供调用方核对"先落盘后遗弃"（T27 的运行时断言）
      ...(replacementSeq <= artifactSeq ? { code: 'replace_before_persist' } : {}),
    })
  } catch (error) {
    // 兜底：任何未预期异常都结构化返回，绝不冒泡到节点结算点。
    return finish('skipped', {
      code: 'isolation_internal_error',
      reason: fmt('隔离执行内部异常：{err}', { err: errorMessage(error) }),
      message: fmt('节点隔离未执行：内部异常（{err}）。', { err: errorMessage(error) }),
    })
  }
}

async function safeReadDoc(docs: DocRepository, relPath: string): Promise<string> {
  try {
    return await docs.read(relPath)
  } catch {
    return ''
  }
}

function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : String(error)
}
