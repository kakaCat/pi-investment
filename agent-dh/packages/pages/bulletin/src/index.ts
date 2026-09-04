// @pi-investment/dashboard-bulletin · 公告板（DSH GUI 双半插件 host 半，RFC 013）
// host 半：phase2 起向同源暴露 bulletin JSON API（/dashboard/api/bulletin/posts），
// 与 execution 的 /dashboard/api/board、holdings 的 /dashboard/api/holdings 互斥（路由契约）。
// GUI 呈现由 client 半承担（package.json dsh.client + exports ./client → lib/client.js）。
//
// phase1+probe（2026-09-05）：apply 占位 + 诊断探针 /dashboard/api/bulletin-probe
// （返回自身是否应用 + loader 条目清单；定位侧栏按钮不显示的根因后 phase2 移除）。

import { Context } from '@deepseek-ai/cordis'

export const name = 'dashboard-bulletin'

export function apply(ctx: Context, _config?: unknown): void {
  const logger = ctx.logger(name)
  logger.info('bulletin host applied (phase1 probe build)')

  const anyCtx = ctx as unknown as {
    inject?: (services: string[], cb: (webCtx: any) => void) => void
  }
  anyCtx.inject?.(
    ['webServer'],
    (webCtx: { effect?: (fn: () => void, label?: string) => void; webServer?: any; ctx?: any }) => {
      webCtx.effect?.(() => {
        webCtx.webServer.register({
          kind: 'exact',
          path: '/dashboard/api/bulletin-probe',
          handler: async () => {
            let entries: string[] = []
            try {
              const loader = (webCtx.ctx ?? ctx) as any
              if (loader?.loader?.entries) {
                entries = [...loader.loader.entries()].map((e: any) => e.options?.name).filter(Boolean)
              }
            } catch (err: unknown) {
              return { ok: true, applied: true, loaderError: String(err) }
            }
            return { ok: true, applied: true, loaderAvailable: entries.length > 0, entries }
          },
        })
        logger.info('bulletin probe registered: /dashboard/api/bulletin-probe')
      }, name + ': probe')
    },
  )
}
