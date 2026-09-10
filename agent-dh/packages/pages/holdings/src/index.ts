// @pi-investment/dashboard-holdings · 账户持仓看板（DSH GUI 双半插件 host 半）
// host 半：向同源暴露 holdings JSON API（/dashboard/api/holdings，client 半 fetch 用）
// + 「我来解决」投递路由（/dashboard/api/holdings/solve，经 @pi-investment/solve-kit 公用工厂，
//   2026-09-08 w-752decf5 抽象复用自 execution；GUI 由 client 半承担）。
// 零工具、零 dsh-tools/core-tool 依赖。模块形状与 dashboard-execution 一致（name + apply 具名导出）；
// 路由经 (ctx as any).inject(['webServer']) 惰性注入 + webCtx.effect 包裹注册。
// /dashboard/api/holdings 的唯一所有者——execution 插件不注册该路径（双插件互斥路由契约）。

import { Context } from '@deepseek-ai/cordis';
import { PortfolioAggregationService } from './services/portfolio-aggregation.js';
import { createHoldingsHandler } from './routes/holdings-routes.js';
import { createSolveHandler, type ActionTarget } from '@pi-investment/solve-kit';

export const name = 'dashboard-holdings';

interface PluginConfig {
  v2BaseURL?: string;
  /** Agent OS 调度器地址（agent 类账户执行者任务数据源，默认 http://127.0.0.1:8080） */
  agentOsBaseURL?: string;
  requestTimeoutMs?: number;
  /** 本实例身份 id（默认取 process.env.AGENT_ID ?? 'investor'），主 root 匹配用（solve 投递） */
  agentId?: string;
}

function resolveOptions(config: PluginConfig | undefined) {
  return {
    v2BaseURL: (config?.v2BaseURL || process.env.QUANTSYS_V2_API_URL || 'http://127.0.0.1:5001').replace(/\/$/, ''),
    agentOsBaseURL: (config?.agentOsBaseURL || process.env.AGENT_OS_BASE_URL || 'http://127.0.0.1:8080').replace(/\/$/, ''),
    requestTimeoutMs: config?.requestTimeoutMs ?? 4000,
    agentId: config?.agentId || process.env.AGENT_ID || 'investor',
  };
}

export function apply(ctx: Context, config?: PluginConfig): void {
  const options = resolveOptions(config);
  const aggregator = new PortfolioAggregationService(options);
  const logger = ctx.logger(name);
  logger.info('dashboard-holdings plugin loading...');

  // 「我来解决」目标会话解析：惰性注入 agents 服务（同 dashboard-execution 模式，2026-09-08 接入）。
  let agentsSvc: any;
  (ctx as unknown as { inject?: (services: string[], cb: (actx: any) => void, label?: string) => void }).inject?.(
    ['agents'],
    (actx: { agents?: any }) => { agentsSvc = actx.agents },
    name + ': agents',
  );
  // 会话 id → 展示窗口标签（与 bulletin/lifecycle windowCode 同口径：session- 前缀取中段 8 位）
  const windowCode = (id: string): string => id.startsWith('session-') ? 'w-' + id.slice(8, 16) : id;
  // resolve(sessionId?, exactOnly?) → 在线 agent root；exactOnly=false 时回退身份主 root（id 前缀 agentId），再兜底 roots[0]
  const resolveAgent = (sessionId?: string, exactOnly = false): ActionTarget | null => {
    const agents = agentsSvc as any;
    if (!agents) return null;
    let list: any[] = [];
    try { list = agents.roots?.() ?? [] } catch { list = [] }
    let agent: any;
    if (sessionId) {
      agent = list.find((r: any) => String(r.id) === sessionId);
      if (!agent && typeof agents.get === 'function') {
        try { agent = agents.get(sessionId) } catch { /* not found */ }
      }
    }
    if (!agent && !exactOnly) agent = list.find((r: any) => String(r.id).startsWith(options.agentId)) ?? list[0];
    if (!agent) return null;
    const id = String(agent.id);
    return { agent, sessionId: id, window: windowCode(id) };
  };

  // 惰性注入 webServer：DASH 页面生命周期里 dsh web 启动后注入，注册即生效
  (ctx as unknown as { inject?: (services: string[], cb: (webCtx: any) => void) => void }).inject?.(
    ['webServer'],
    (webCtx: { effect?: (fn: () => void, label?: string) => void; webServer?: any }) => {
      webCtx.effect?.(() => {
        webCtx.webServer.register({
          kind: 'exact',
          path: '/dashboard/api/holdings',
          handler: createHoldingsHandler(aggregator),
        });
        // 「我来解决」：automation 失败任务行投递窗口处置（solve-kit 公用工厂，只投递不建帖）
        webCtx.webServer.register({
          kind: 'exact',
          path: '/dashboard/api/holdings/solve',
          handler: createSolveHandler({ resolveAgent }, { panel: '持仓看板', panelFull: '账户持仓看板', plugin: 'dashboard-holdings', osBaseURL: 'http://127.0.0.1:8080' }),
        });
      }, name + ': api');

      logger.info('routes registered: /dashboard/api/holdings + /dashboard/api/holdings/solve (client half renders GUI)');
    },
  );
}
