// @pi-investment/dashboard-holdings · 账户持仓看板（DSH GUI 双半插件 host 半）
// host 半：只向同源暴露 holdings JSON API（/dashboard/api/holdings，client 半 fetch 用）；
// GUI 呈现由 client 半承担（package.json dsh.client + exports["./client"] → lib/client.js，
// 浏览器加载后挂侧栏入口 + 中心栏视图）。零工具、零 dsh-tools/core-tool 依赖。
// 模块形状与 dashboard-execution 一致（name + apply 具名导出）；
// 路由经 (ctx as any).inject(['webServer']) 惰性注入 + webCtx.effect 包裹注册
// （disposer 自动注销，模式同 packages/lifecycle/src/wake-webhook.ts 已线上验证）。
// /dashboard/api/holdings 的唯一所有者——execution 插件不注册该路径（双插件互斥路由契约）。

import { Context } from '@deepseek-ai/cordis';
import { PortfolioAggregationService } from './services/portfolio-aggregation.js';
import { createHoldingsHandler } from './routes/holdings-routes.js';

export const name = 'dashboard-holdings';

interface PluginConfig {
  v2BaseURL?: string;
  requestTimeoutMs?: number;
}

function resolveOptions(config: PluginConfig | undefined) {
  return {
    v2BaseURL: (config?.v2BaseURL || process.env.QUANTSYS_V2_API_URL || 'http://127.0.0.1:5001').replace(/\/$/, ''),
    requestTimeoutMs: config?.requestTimeoutMs ?? 4000,
  };
}

export function apply(ctx: Context, config?: PluginConfig): void {
  const aggregator = new PortfolioAggregationService(resolveOptions(config));
  const logger = ctx.logger(name);
  logger.info('dashboard-holdings plugin loading...');

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
      }, name + ': api');

      logger.info('routes registered: /dashboard/api/holdings (client half renders GUI)');
    },
  );
}
