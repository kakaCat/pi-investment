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
import { createBoardHandler, createErrorActionHandler, createErrorEventsHandler, createOrphanedTaskCleanupHandler } from './routes/dashboard-routes.js';
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
  const profileDir = config?.profileDir || path.join(home, '.dsh', 'profiles', 'investment');
  const v2BaseURL = (config?.v2BaseURL || process.env.QUANTSYS_V2_API_URL || 'http://127.0.0.1:5001').replace(/\/$/, '');
  const osBaseURL = (config?.osBaseURL || 'http://127.0.0.1:8080').replace(/\/$/, '');
  // 错误事件数据源=Agent OS error_events DB（2026-09-09 起单一事实源，不再 tail 本地日志）

  return {
    v2BaseURL,
    osBaseURL,
    genomeDir: config?.genomeDir || path.join(home, '.dsh-agent-dh', 'genome'),
    profileStateDir: path.join(profileDir, 'state'),
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
          handler: createSolveHandler({ resolveAgent }, { panel: '执行看板', panelFull: '双线执行确认看板', plugin: 'dashboard-execution', osBaseURL: 'http://127.0.0.1:8080' }),
        });
        // 在线窗口列表（picker 离线防护数据源：会话列表含离线会话，投递要求在线 agent）
        webCtx.webServer.register({
          kind: 'exact',
          path: '/dashboard/api/board/online-windows',
          handler: (_req: unknown, res: { writeHead: (n: number, h: Record<string, string>) => void; end: (s: string) => void }) => {
            let ids: string[] = [];
            try { ids = (((agentsSvc as { roots?: () => { id: unknown }[] })?.roots?.() ?? [])).map((r) => String(r.id)); } catch { ids = []; }
            res.writeHead(200, { 'Content-Type': 'application/json' });
            res.end(JSON.stringify({ success: true, data: { online: ids } }));
          },
        });
        // 错误事件分页浏览：status/page/pageSize → Agent OS error-events（offset/total）
        webCtx.webServer.register({
          kind: 'exact',
          path: '/dashboard/api/board/error-events',
          handler: createErrorEventsHandler({ osBaseURL: options.osBaseURL }),
        });
        // 错误事件处置：claim/resolve/ignore/reopen → Agent OS error_events 状态机（actor=from_session 窗口）
        webCtx.webServer.register({
          kind: 'exact',
          path: '/dashboard/api/board/error-action',
          handler: createErrorActionHandler({ osBaseURL: options.osBaseURL, windowCode }),
        });
        // 清理僵尸任务：POST /dashboard/api/board/orphaned-task-cleanup (body: {id})
        webCtx.webServer.register({
          kind: 'exact',
          path: '/dashboard/api/board/orphaned-task-cleanup',
          handler: createOrphanedTaskCleanupHandler({ osBaseURL: options.osBaseURL }),
        });

      }, name + ': api');

      logger.info('routes registered: /dashboard/api/board + /solve + /error-action (client half renders GUI); /dashboard/api/holdings owned by dashboard-holdings');
    },
  );
}