// @pi-investment/dashboard-execution · P1 双线执行确认看板（DSH GUI 双半插件 host 半）
// host 半：只向同源暴露 board JSON API（/dashboard/api/board，client 半 fetch 用）；
// GUI 呈现由 client 半承担（package.json dsh.client + exports["./client"] → lib/client.js，
// 浏览器加载后挂侧栏入口 + 中心栏视图）。零工具、零 dsh-tools/core-tool 依赖。
// 模块形状与旧 page-dashboard 一致（name + apply 具名导出），DSH loader 已验证可加载；
// 路由经 (ctx as any).inject(['webServer']) 惰性注入 + webCtx.effect 包裹注册
// （disposer 自动注销，模式同 packages/lifecycle/src/wake-webhook.ts 已线上验证）。

import { Context } from '@deepseek-ai/cordis';
import * as os from 'node:os';
import * as path from 'node:path';
import { DataAggregationService } from './services/data-aggregation.js';
import { createBoardHandler } from './routes/dashboard-routes.js';
import { createSolveHandler, type ActionTarget } from '@pi-investment/solve-kit';

export const name = 'dashboard-execution';

interface PluginConfig {
  v2BaseURL?: string;
  osBaseURL?: string;
  genomeDir?: string;
  piInvestDir?: string;
  profileDir?: string;
  requestTimeoutMs?: number;
  /** 本实例身份 id（默认取 process.env.AGENT_ID ?? 'investor'），主 root 匹配用 */
  agentId?: string;
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
    agentId: config?.agentId || process.env.AGENT_ID || 'investor',
  };
}

export function apply(ctx: Context, config?: PluginConfig): void {
  const options = resolveOptions(config);
  const aggregator = new DataAggregationService(options);
  const logger = ctx.logger(name);

  // 「我来解决」目标会话解析：惰性注入 agents 服务（同 bulletin/agent-self 模式）。
  // agents 服务非本插件声明注入，直接读 (ctx as any).agents 触发 cordis 门禁，故同款捕获。
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
    // 显式指定窗口（to_session）须精确命中防误投；默认当前窗口/主 root 允许回退
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
        // 注册 execution board 路由
        webCtx.webServer.register({
          kind: 'exact',
          path: '/dashboard/api/board',
          handler: createBoardHandler(aggregator),
        });
        // 「我来解决」：失败任务/错误事件投递窗口处置（只投递不建帖）
        webCtx.webServer.register({
          kind: 'exact',
          path: '/dashboard/api/board/solve',
          handler: createSolveHandler({ resolveAgent }, { panel: '执行看板', panelFull: '双线执行确认看板', plugin: 'dashboard-execution' }),
        });

      }, name + ': api');

      logger.info('routes registered: /dashboard/api/board + /dashboard/api/board/solve (client half renders GUI); /dashboard/api/holdings owned by dashboard-holdings');
    },
  );
}
