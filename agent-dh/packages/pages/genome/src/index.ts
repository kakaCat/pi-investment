// @pi-investment/dashboard-genome · 自主进化看板（DSH GUI 双半插件 host 半）
// host 半：向同源暴露 /dashboard/api/genome JSON API（client 半 fetch 用）；
// GUI 呈现由 client 半承担（package.json dsh.client + exports["./client"] → lib/client.js，
// 浏览器加载后挂侧栏「自主进化」入口 + 中心栏视图）。
// 数据源：genome 数据目录下 genome.json + candidates.json，host 进程内 fs 直读——浏览器不直连本地文件。
// 目录解析见 ./genome-dir.ts 的 pickGenomeDir()（2026-09-13 REQ-3952b7 重写）：
//   ① 显式 config.genomeDir ② 运行中 genome 插件实际目录（运行时单一事实源）
//   ③ DSH_GENOME_DIR ④ <DSH_DATA_DIR>/genome ⑤ <DSH_HOME>/genome ⑥ ~/.dsh-agent-dh/genome（遗留兜底）
//   ⚠️ 事故背景：原实现把 ⑥ 当默认值硬编码，2026-09-13 DSH_HOME 迁移后 genome 插件改读
//   .dsh-data/genome，本页仍读旧 home → ④候选流水线空、⑤谱系只剩 4 条 g1（真库 g35/14 候选/37 谱系）。
//   现策略：页面运行时跟随 genome 插件（不可能再静默分叉），env 链只作插件缺席时的兜底；
//   生效目录与来源随 API（genomeDir/genomeDirSource）与启动日志对外可见。
// 零工具、零 dsh-tools/core-tool 依赖（模式同 dashboard-execution）。
// 模块形状：name + apply 具名导出；路由经 (ctx as any).inject(['webServer']) 惰性注入 +
// webCtx.effect 包裹注册（disposer 自动注销）。

import { Context } from '@deepseek-ai/cordis'
import { GenomeAggregationService } from './services/genome-aggregation.js'
import { createGenomeHandler, createExplainHandler } from './routes/genome-routes.js'
import { pickGenomeDir, readGenomeServiceDir } from './genome-dir.js'
import type { ResolvedGenomeDir } from './genome-dir.js'

export { pickGenomeDir, readGenomeServiceDir } from './genome-dir.js'
export type { GenomeDirSource, ResolvedGenomeDir } from './genome-dir.js'

export const name = 'dashboard-genome'

interface PluginConfig {
  /** genome 数据目录；显式设置时优先于一切自动解析（默认跟随运行中的 genome 插件） */
  genomeDir?: string
}

export function apply(ctx: Context, config?: PluginConfig): void {
  const logger = ctx.logger(name)
  const configuredDir = config?.genomeDir
  // genome 插件实际目录：惰性注入后填充 → 本页与 agent 真正在用的基因组同源（单一事实源）
  let liveDir = ''

  // genome 服务惰性获取：cordis 中未 inject 声明的服务属性访问会抛错（cannot get property without inject）。
  // ctx.inject(['genome'], cb) 回调收到注入作用域 ctx，取 gctx.genome 才是服务实例。
  ;(ctx as unknown as { inject?: (services: string[], cb: (gctx: any) => void, label?: string) => void }).inject?.( 
    ['genome'],
    (gctx: { genome?: unknown }) => {
      liveDir = readGenomeServiceDir(gctx.genome)
      if (liveDir) logger.info(`genome plugin dir = ${liveDir} (page follows it)`)
      else logger.warn('genome service present but genomeDir unreadable — 退回 config/env 解析链')
    },
    name + ': genome',
  )

  const resolveDir = (): ResolvedGenomeDir => pickGenomeDir(configuredDir, liveDir)
  const initial = resolveDir()
  logger.info(`genome data dir = ${initial.dir} (source: ${initial.source})`)

  // 聚合服务按请求解析目录：genome 服务晚于本插件 apply 注入也能即时生效
  const aggregator = new GenomeAggregationService({
    genomeDir: () => resolveDir().dir,
    genomeDirSource: () => resolveDir().source,
  })

  // agents 服务惰性获取：explain 投递入口（roots()/followup）用
  let agentsService: unknown
  ;(ctx as unknown as { inject?: (services: string[], cb: (agentsCtx: any) => void) => void }).inject?.(
    ['agents'],
    (agentsCtx: { agents?: unknown }) => {
      agentsService = agentsCtx.agents
      logger.info('agents service ready (explain delivery enabled)')
    },
  )

  // 惰性注入 webServer：DSH web 启动后注入，注册即生效（模式同 dashboard-execution）
  ;(ctx as unknown as { inject?: (services: string[], cb: (webCtx: any) => void) => void }).inject?.(
    ['webServer'],
    (webCtx: { effect?: (fn: () => void, label?: string) => void; webServer?: any }) => {
      webCtx.effect?.(() => {
        webCtx.webServer.register({
          kind: 'exact',
          path: '/dashboard/api/genome',
          handler: createGenomeHandler(aggregator),
        })
        // AI 讲解：页面「🤖 讲解」按钮 → 投递给在线 investor agent（agentsService.followup），讲解回复在会话
        webCtx.webServer.register({
          kind: 'exact',
          path: '/dashboard/api/genome/explain',
          handler: createExplainHandler(agentsService, aggregator),
        })
      }, name + ': api')
      logger.info('routes registered: /dashboard/api/genome + /dashboard/api/genome/explain (client half renders GUI)')
    },
  )
}
