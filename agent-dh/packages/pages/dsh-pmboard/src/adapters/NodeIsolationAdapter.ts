/**
 * 节点隔离会话适配器（REQ-422af1 t9 端口实现）——surface 原语在这里落地。
 *
 * 为什么在 adapters：application 层禁止 import \`@deepseek-ai/*\`（tests/layer-boundary.test.ts
 * 机械门禁），故 Session 调用只出现在本文件。本文件用**结构类型**接住宿主传进来的 Session
 * （不 import 框架类型），因此不新增依赖声明，也不受"本仓多数包 dist 加载"影响。
 *
 * ── tool 配对边界检查：等价移植，不是复用 ──────────────────────────────────
 * 原实现来自 \`@deepseek-ai/dsh-compaction\` 的 toolPairingBalancedBefore / toolPairingBalancedAfter
 * （dsh-compaction@0.1.5-rc.2 lib/types/tool-pairing.js）。本包依赖树中**不可解析**该包：
 *   \$ cd packages/pages/dsh-pmboard && node -e "import('@deepseek-ai/dsh-compaction')"
 *   → ERR_MODULE_NOT_FOUND
 * （根 node_modules/@deepseek-ai/ 无该条目；且 REQ-422af1 plan.md §不做 明写"不新增第三方依赖"。）
 * 故按语义**等价移植**，语义（配对定义）逐条照抄：
 *   - 在 surface **可见顺序**上折叠，不看 step 标记（替换会让 surface 位置非数值单调）；
 *   - 折叠增量 eventDelta：assistant/message → 其 content 里 type==='tool-call' 的块数；
 *     tool/result → -1；其余 → 0；
 *   - 每条路径维护 inProgress（未配对 tool 调用数），<0 即"结果无对应调用"（腐坏，抛错）；
 *   - cutBalanced[i] = 处理完第 i 个 surface 节点后 inProgress === 0；空 surface 的前沿切为 true；
 *   - before(seq) = 该 seq 所在位置**之前**那条切线；after(seq) = **之后**那条切线。
 * 与上游的差异只有一处：不做 per-replaceGeneration 缓存（t9 在节点边界低频调用，正确性优先）。
 *
 * ── 必须遵守的框架契约（实测）──────────────────────────────────────────────
 * dsh-session@0.1.5-rc.1：
 *  - surface 节点 0（系统提示词）只能被 system/message 且恰为单节点改写，否则抛
 *    "surface replace: node 0 holds the system prompt and may be rewritten only by a
 *     system/message over exactly that node"（lib/types/surface.js:338）；本适配器与
 *    用例都保证区间**从首个非 system 节点起**。
 *  - sourceEventSeqs 必须**完整覆盖**被遮蔽的全部 surface 节点，否则抛
 *    "surface replace: sourceEventSeqs must include every shadowed surface node; missing …"。
 *  - append 会拒绝"发布中重入"：\`session append cannot reenter while another append is
 *    being published\`（lib/index.js:1183）。**调用方（t10 结算点）必须把隔离动作移出
 *    session/event 派发**（例如 turn/end 后 queueMicrotask/setImmediate 再执行），
 *    否则同步 append 必被拒。本文件不负责调度，只如实抛错。
 *
 * @module dsh-pmboard/adapters/NodeIsolationAdapter
 */

import type { NodeIsolationPort, SurfaceNode } from '../application/use-cases/IsolateNodeContext.js'
import { fmt } from '../domain/text/fmt.js'

/** 结构化的会话事件（只取边界检查需要的字段）。 */
interface SessionEventLike {
  readonly type?: unknown
  readonly seq?: unknown
  readonly data?: { readonly message?: { readonly content?: readonly { readonly type?: unknown }[] } }
}

/** 结构化的 Session（宿主传入真实 Session；本文件不 import 框架类型）。 */
interface SessionLike {
  readonly surface?: { readonly nodes?: readonly number[] }
  eventAt?(seq: number): SessionEventLike | undefined
  append?(type: string, data: unknown, opts: unknown): { readonly seq?: unknown }
}

export interface NodeIsolationAdapterOptions {
  /** agent 是否空闲（轮次边界）。抛错按"不空闲"处理（保守）。 */
  idle: () => boolean
  /** 输入包消息的 plugin 来源标记（写进 message.source.plugin）。 */
  plugin?: string
}

/** 输入包消息的 notice 摘要（≤120 字符，见 dsh-llm boundContextSummary）。 */
const PACKAGE_NOTICE_SUMMARY = '节点边界输入包（路由提示词 + 需求文档 + 台账投影）'

export class NodeIsolationAdapter implements NodeIsolationPort {
  private readonly session: SessionLike | undefined
  private readonly opts: NodeIsolationAdapterOptions
  private messageSeq = 0

  constructor(session: unknown, options: NodeIsolationAdapterOptions) {
    this.session = (typeof session === 'object' && session !== null ? session : undefined) as SessionLike | undefined
    this.opts = options
  }

  reachable(): boolean {
    const s = this.session
    return s !== undefined
      && typeof s.append === 'function'
      && typeof s.eventAt === 'function'
      && Array.isArray(s.surface?.nodes)
  }

  idle(): boolean {
    try {
      return this.opts.idle()
    } catch {
      return false
    }
  }

  /** surface 节点（顺序）。取不到事件（腐坏 surface）→ 抛错，不静默当未知类型。 */
  surface(): readonly SurfaceNode[] {
    const s = this.requireSession()
    const nodes = s.surface?.nodes ?? []
    return nodes.map((seq) => {
      const event = s.eventAt!(seq)
      if (event === undefined) {
        throw new Error(fmt('tool-pairing balance: surface seq {seq} has no matching session event (corrupt surface)', { seq }))
      }
      return { seq, type: typeof event.type === 'string' ? event.type : 'unknown' }
    })
  }

  balancedBefore(seq: number): boolean {
    const { cuts, index } = this.balance()
    return cuts[this.cutIndex(cuts, index, seq)]!
  }

  balancedAfter(seq: number): boolean {
    const { cuts, index } = this.balance()
    return cuts[this.cutIndex(cuts, index, seq) + 1]!
  }

  /**
   * 执行 append('user/message', 输入包) + surfaceOp replace(start..end)。
   * 消息用结构对象构造（source.kind='plugin' + form='notice'——不是 direct human，
   * 因此不会被 reqboard 的立项捕获 hook 当成用户消息二次触发）。
   */
  replace(input: { start: number; end: number; text: string; shadowed: readonly number[] }): number {
    const s = this.requireSession()
    const message = {
      id: 'pmboard-node-input-' + String(this.messageSeq += 1),
      role: 'user',
      content: [{ type: 'text', text: input.text }],
      source: {
        kind: 'plugin',
        plugin: this.opts.plugin ?? 'dsh-pmboard',
        form: 'notice',
        summary: PACKAGE_NOTICE_SUMMARY,
      },
    }
    const event = s.append!('user/message', message, {
      surfaceOp: { op: 'replace', startSeq: input.start, endSeq: input.end },
      sourceEventSeqs: [...input.shadowed],
    })
    const seq = event?.seq
    if (typeof seq !== 'number' || !Number.isFinite(seq)) {
      throw new Error(fmt('surface replace 未返回有效事件 seq：{seq}', { seq: String(seq) }))
    }
    return seq
  }

  private requireSession(): SessionLike {
    if (!this.reachable()) {
      throw new Error('NodeIsolationAdapter: 会话不可触达（reachable()=false）')
    }
    return this.session!
  }

  /** 折叠出每条切线是否平衡 + seq→surface 下标。语义见文件头（等价移植 dsh-compaction）。 */
  private balance(): { cuts: boolean[]; index: Map<number, number> } {
    const nodes = this.surface()
    const cuts: boolean[] = [true]
    const index = new Map<number, number>()
    let inProgress = 0
    nodes.forEach((node, i) => {
      const event = this.session!.eventAt!(node.seq)
      inProgress += eventDelta(event)
      if (inProgress < 0) {
        throw new Error(fmt('tool-pairing balance: tool/result at surface seq {seq} has no matching tool-call (corrupt surface)', { seq: node.seq }))
      }
      cuts.push(inProgress === 0)
      index.set(node.seq, i)
    })
    return { cuts, index }
  }

  private cutIndex(cuts: readonly boolean[], index: ReadonlyMap<number, number>, seq: number): number {
    const i = index.get(seq)
    if (i === undefined || cuts[i] === undefined) {
      throw new Error(fmt('tool-pairing balance: surface seq {seq} not found', { seq }))
    }
    return i
  }
}

/** 单节点对未配对 tool 调用数的增量（等价移植 dsh-compaction eventDelta）。 */
function eventDelta(event: SessionEventLike | undefined): number {
  if (event === undefined) return 0
  if (event.type === 'assistant/message') {
    const blocks = event.data?.message?.content ?? []
    return blocks.filter(b => b?.type === 'tool-call').length
  }
  if (event.type === 'tool/result') return -1
  return 0
}
