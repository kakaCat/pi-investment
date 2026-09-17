/**
 * 注入留痕只读路由（REQ-422af1 t11）—— 看板「本次注入了什么」的数据源。
 *
 * 只做协议转换：读留痕（只读端口）→ 过滤窗口 → 取最近 k 条 → JSON 信封。
 * **只读**：本模块不写任何东西（不 record、不落盘），端口类型也是只读的
 * InjectionLogReadPort——看板永远不可能借这条路径改动留痕。
 *
 * @module dsh-pmboard/http/routers/Injection
 */
import type { ServerResponse } from 'node:http'
import { queryInjectionLog } from '../../application/internal/injection-log.js'
import type { RouterCtx } from './shared.js'

/** 默认返回条数（看板只读块一次拉这么多）。 */
export const INJECTION_QUERY_DEFAULT = 20
/** 单次上限（防一条 URL 把 ring buffer 全拉进浏览器）。 */
export const INJECTION_QUERY_MAX = 200

export function createInjectionRouter(ctx: RouterCtx) {
  const { ok, deps, badInput } = ctx

  /**
   * GET /dashboard/api/reqboard/injection-log?window=<sessionId>&k=<1..200>
   * 返回最近 k 条注入留痕（写入顺序，旧→新）。window 缺省 = 全量最近 k 条。
   * 留痕端口未装配时返回空清单（available=false）而不是报错——看板不因此变红。
   */
  async function handleInjectionLog(res: ServerResponse, url: URL): Promise<void> {
    const rawK = url.searchParams.get('k')
    const k = rawK === null || rawK.length === 0 ? INJECTION_QUERY_DEFAULT : Number(rawK)
    if (!Number.isInteger(k) || k < 1 || k > INJECTION_QUERY_MAX) {
      badInput(`k 必须是 1..${INJECTION_QUERY_MAX} 的整数`)
    }
    const window = url.searchParams.get('window')
    const log = deps.injectionLog
    if (log === undefined) {
      ok(res, { entries: [], total: 0, available: false, window: window ?? null })
      return
    }
    const all = await log.readAll()
    const scoped = window !== null && window.length > 0 ? all.filter(e => e.windowKey === window) : all
    ok(res, {
      entries: queryInjectionLog(scoped, k),
      total: scoped.length,
      available: true,
      window: window ?? null,
    })
  }

  return { handleInjectionLog }
}
