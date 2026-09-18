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

export interface RouterCtx {
  store: JsonLedgerRepository
  now: () => number
  /**
   * 路由可选依赖：cwd=产物扫描根；injectionLog=注入留痕**只读**端口（看板信息块用）；
   * systemPrompt=系统提示词装配服务（REQ-a33899 t5，读时折算固定提示词成本；缺省 → unavailable）。
   */
  deps: { cwd?: string; injectionLog?: InjectionLogReadPort; systemPrompt?: () => unknown }
  ids: { requirement: () => string; task: () => string; comment: () => string }
  mintId: (kind: 'requirement' | 'task') => Promise<string>
  json: (res: ServerResponse, status: number, body: unknown) => void
  ok: (res: ServerResponse, data: unknown) => void
  fail: (res: ServerResponse, err: unknown) => void
  badInput: (message: string) => never
  notFound: (what: string) => never
  readBody: (req: IncomingMessage) => Promise<Record<string, unknown>>
}
