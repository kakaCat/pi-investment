// @pi-investment/dashboard-execution · P1 双线执行确认看板（页面插件）
// 纯页面插件范式：只注册 webServer 路由，零工具、零 dsh-tools/core-tool 依赖。
// 模块形状与旧 page-dashboard 一致（name + apply 具名导出），DSH loader 已验证可加载；
// 路由经 (ctx as any).inject(['webServer']) 惰性注入 + webCtx.effect 包裹注册
// （disposer 自动注销，模式同 packages/lifecycle/src/wake-webhook.ts 已线上验证）。

import { Context } from '@deepseek-ai/cordis';
import * as os from 'node:os';
import * as path from 'node:path';
import { DataAggregationService } from './services/data-aggregation.js';
import { createBoardHandler, createExecutionPageHandler } from './routes/dashboard-routes.js';

export const name = 'dashboard-execution';

interface PluginConfig {
  v2BaseURL?: string;
  osBaseURL?: string;
  genomeDir?: string;
  piInvestDir?: string;
  profileDir?: string;
  requestTimeoutMs?: number;
}

function resolveOptions(config: PluginConfig | undefined) {
  const home = os.homedir();
  const piInvestDir = config?.piInvestDir || process.env.PI_INVEST_DIR || path.join(home, 'pi-investment');
  const profileDir = config?.profileDir || path.join(home, '.dsh', 'profiles', 'investment');
  const v2BaseURL = (config?.v2BaseURL || process.env.QUANTSYS_V2_API_URL || 'http://127.0.0.1:5001').replace(/\/$/, '');
  const osBaseURL = (config?.osBaseURL || 'http://127.0.0.1:8080').replace(/\/$/, '');

  const logFiles = [
    // v2 日志可能极大（78MB）——聚合器 tail 只 seek 末 512KB
    { source: 'v2' as const, file: path.join(piInvestDir, 'quantsys-v2', 'logs', 'launchd-stdout.log') },
    { source: 'v2' as const, file: path.join(piInvestDir, 'quantsys-v2', 'logs', 'launchd-stderr.log') },
    { source: 'os' as const, file: path.join(piInvestDir, 'agent-os', 'logs', 'launchd-stdout.log') },
    { source: 'os' as const, file: path.join(piInvestDir, 'agent-os', 'logs', 'launchd-stderr.log') },
    { source: 'dsh' as const, file: path.join(profileDir, 'state', 'launchd.out.log') },
    { source: 'dsh' as const, file: path.join(profileDir, 'state', 'launchd.err.log') },
  ];

  return {
    v2BaseURL,
    osBaseURL,
    genomeDir: config?.genomeDir || path.join(home, '.dsh-agent-dh', 'genome'),
    profileStateDir: path.join(profileDir, 'state'),
    logFiles,
    requestTimeoutMs: config?.requestTimeoutMs ?? 4000,
  };
}

export function apply(ctx: Context, config?: PluginConfig): void {
  const aggregator = new DataAggregationService(resolveOptions(config));
  const logger = ctx.logger(name);

  // 惰性注入 webServer：DASH 页面生命周期里 dsh web 启动后注入，注册即生效
  (ctx as unknown as { inject?: (services: string[], cb: (webCtx: any) => void) => void }).inject?.(
    ['webServer'],
    (webCtx: { effect?: (fn: () => void, label?: string) => void; webServer?: any }) => {
      // 页面：读自打包资源 execution.html（同 module 相对路径，永不依赖 __dirname）
      webCtx.effect?.(() => {
        webCtx.webServer.register({
          kind: 'exact',
          path: '/dashboard/execution',
          handler: createExecutionPageHandler(),
        });
      }, name + ': page');

      webCtx.effect?.(() => {
        webCtx.webServer.register({
          kind: 'exact',
          path: '/dashboard/api/board',
          handler: createBoardHandler(aggregator),
        });
      }, name + ': api');

      logger.info('routes registered: /dashboard/execution, /dashboard/api/board');
    },
  );
}
