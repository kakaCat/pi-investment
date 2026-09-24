/**
 * HTTP 路由共享上下文与信封（REQ-47939a t7）——错误 → HTTP 状态码映射的**唯一一处**。
 *
 * 为什么抽出来：此前每个路由处理器各自 badInput/notFound，状态码语义分散；
 * 现在 fail() 是唯一映射点，routers/* 只调用它。
 *
 * @module dsh-pmboard/http/routers/shared
 */
import type { IncomingMessage, ServerResponse } from 'node:http'
import type { JsonLedgerRepository } from '../../adapters/JsonLedgerRepository.js'
import type { InjectionLogReadPort } from '../../application/internal/injection-log.js'
import type { IsolationLogReadPort } from '../../application/internal/isolation-trace.js'
import type { DocRepository } from '../../application/ports.js'

export interface RouterCtx {
  store: JsonLedgerRepository
  now: () => number
  /**
   * 路由可选依赖：cwd=产物扫描根；injectionLog=注入留痕**只读**端口（看板信息块用）；
   * systemPrompt=系统提示词装配服务（REQ-a33899 t5，读时折算固定提示词成本；缺省 → unavailable）；
   * tokenSnapshot=Token快照提供者（REQ-b545fe t6，HTTP任务操作可结算快照）。
   */
  deps: {
    cwd?: string
    injectionLog?: InjectionLogReadPort
    /** 节点隔离留痕只读端口（REQ-260923134706-e72f t2：看板「执行流程→上下文管理」数据源；缺省 → available=false）。 */
    isolationLog?: IsolationLogReadPort
    systemPrompt?: () => unknown
    tokenSnapshot?: (windowKey: string) => import('../../shared/protocol.js').TokenSnapshot | undefined
    /** 文档仓储（REQ-308b9a AC-7.7：看板裁决后回填 verification.md；缺省 → 跳过）。 */
    docs?: DocRepository
    /**
     * 闸门后置链（REQ-e3b6a0 t9 / FR-9）：看板一键确认后触发 Phase B（推进 + 压缩 + 注入 + 唤醒）。
     * 缺省 → 只落章（行为与改造前完全一致）。
     */
    gateChain?: import('../../application/gate/GatePostChain.js').GateChainPort
    /** 在线 agent 查询（取会话句柄供 H2 用）；缺省 → 视为窗口不在线。 */
    agents?: () => { get?: (id: string) => unknown } | undefined
    /**
     * 推进器（REQ-4842fe FR-12 / t-3be71b）：看板控制面「继续」= 置 autoRun=true **并触发一次推进事件**。
     * 缺省 → 只置开关并如实说明（不伪造"已续跑"）。
     */
    advance?: (requirementId: string) => Promise<{ steps: number; stopped: string }>
  }
  ids: { requirement: () => string; task: () => string; comment: () => string }
  mintId: (kind: 'requirement' | 'task') => Promise<string>
  json: (res: ServerResponse, status: number, body: unknown) => void
  ok: (res: ServerResponse, data: unknown) => void
  fail: (res: ServerResponse, err: unknown) => void
  badInput: (message: string) => never
  notFound: (what: string) => never
  readBody: (req: IncomingMessage) => Promise<Record<string, unknown>>
}
