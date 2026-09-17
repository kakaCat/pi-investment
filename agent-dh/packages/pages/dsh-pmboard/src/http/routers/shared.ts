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

export interface RouterCtx {
  store: JsonLedgerRepository
  now: () => number
  deps: { cwd?: string }
  ids: { requirement: () => string; task: () => string; comment: () => string }
  mintId: (kind: 'requirement' | 'task') => Promise<string>
  json: (res: ServerResponse, status: number, body: unknown) => void
  ok: (res: ServerResponse, data: unknown) => void
  fail: (res: ServerResponse, err: unknown) => void
  badInput: (message: string) => never
  notFound: (what: string) => never
  readBody: (req: IncomingMessage) => Promise<Record<string, unknown>>
}
