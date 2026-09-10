// dsh-pmboard · 项目看板（RFC 014）
// host 半：reqboard JSON+SSE API（/dashboard/api/reqboard/*）+ 两级状态机台账 +
// 捕获（用户裁定 · 创建即立项）：确定性消息 hook（session/event user/message 到达 →
// 检查窗口 unbound 且无遗留 pending → 登记待捕获消息）+ systemPrompt 捕获引导段
// （命中待捕获则注入引用消息原文的立项提示，让 LLM 弹「两问确认」获用户确认后调
// reqboard_create 直接建 REQ）+ 两个 agent 工具（reqboard_create / reqboard_status）。
// 两问弹框（ask_user_question：需求名称 + 需求类型）作答 = 立项门；创建即立项，无
// 待归类/建议卡中间态。M2 的自动分类 LLM（SessionSyncService）自 2026-09 起不再装配
// （修正 #1/#3：无第二 LLM、人在 loop）。
// 模块形状与 dashboard-execution 一致（name + apply 具名导出）；无静态 inject 的
// 页面插件一律走 (ctx as any).inject(...) 惰性注入（genome/dashboard 同款模式）。

import { Context } from '@deepseek-ai/cordis';
import * as os from 'node:os';
import * as path from 'node:path';
import { ReqboardStore } from './host/store.js';
import { createReqboardHandler } from './host/routes.js';
import { captureSectionText, windowKeyFromContext, draftRequirementsFor } from './host/capture.js';
import { applyPickupAdvance } from './host/rollup.js';
import { newCommentId, type RequirementRecord } from './shared/protocol.js';
import { createSessionEventCaptureHook, type CaptureHookDeps } from './host/capture-hook.js';
import { defineCreateTool, defineStatusTool, defineMoveTool } from './host/agent-tools.js';

export const name = 'dsh-pmboard';

/** 台账文件名（DSH 主目录，卸载插件不删除）。 */
export const LEDGER_FILE = 'dsh-reqboard.json';

/** 捕获引导段名（systemPrompt 全局唯一）与放置序位（identity 5 / genome 10-40 之后）。 */
export const CAPTURE_SECTION = 'reqboard:capture';
export const CAPTURE_SECTION_ORDER = 60;

interface PluginConfig {
  /** DSH 主目录（默认 ~/.dsh） */
  dshHome?: string;
}

export function dshHomePath(config: PluginConfig | undefined, file: string): string {
  const home = config?.dshHome || process.env.DSH_HOME || path.join(os.homedir(), '.dsh');
  return path.join(home, file);
}

export function apply(ctx: Context, config?: PluginConfig): void {
  const logger = ctx.logger(name);
  const store = new ReqboardStore({ file: dshHomePath(config, LEDGER_FILE) });
  // 急加载：fresh boot 时让首个 GET /state 见到台账而非空板（load 永不抛——损坏即隔离）
  void store.load();
  const now = () => Date.now();

  // 乙流程依赖的运行时服务（惰性获取，未就绪/缺失时相关能力降级放行）：
  //   agents             → requireLiveDriver（服务可得则校验 live driver，缺失放行）
  //   sessionProjections → requireDirectHuman（扫描 user 消息 / 执行窗口状态，缺失放行）
  let agentsSvc: unknown;
  let projectionsSvc: unknown;
  ;(ctx as unknown as { inject?: (services: string[], cb: (c: any) => void) => void }).inject?.(
    ['agents'],
    (agentsCtx: { agents?: unknown }) => {
      agentsSvc = agentsCtx.agents;
      logger.debug('agents service ready (reqboard tools live-driver check enabled)');
    },
  );
  ;(ctx as unknown as { inject?: (services: string[], cb: (c: any) => void) => void }).inject?.(
    ['sessionProjections'],
    (spCtx: { sessionProjections?: unknown }) => {
      projectionsSvc = spCtx.sessionProjections;
      logger.debug('sessionProjections service ready (reqboard tools direct-human check enabled)');
    },
  );

  const disposers: Array<() => void> = [];

  // ── 确定性消息捕获 hook（用户裁定 #2/#3）─────────────────────────────
  // 订阅 session/event：用户消息到达（user/message，direct human）→ 若该窗口
  // unbound 且无遗留 pending 建议卡（旧流程 triage 产物）→ 登记「待捕获消息」到
  // pendingCapture；turn/end 清除（该回合 LLM 已消费本次立项评估）。capture section
  // 组装时同引用读取并注入针对性立项提示——hook 只保证确定性触发，立项判定与内容
  // 留给 LLM + 人工（两问弹框作答 = 确认，调 reqboard_create 直接建 REQ）。
  const pendingCapture = new Map<string, { windowKey: string; text: string; capturedAt: number }>();
  const captureHookDeps: CaptureHookDeps = {
    snapshot: () => store.snapshot(),
    pending: pendingCapture,
    now,
    // R1 接手推进：已绑定窗口出现直接人类消息 = 该窗口仍在推进其需求 → 其 draft 需求
    // 自动进评审（人工闸门仍在：方案确认/拆分确认/验收均为人工，代码级不可越过）。
    onBoundWindowActivity: (windowKey) => {
      const drafts = draftRequirementsFor(store.snapshot(), windowKey);
      if (drafts.length === 0) return;
      void store.mutate('requirement-moved', (ledger) => {
        const advanced = drafts
          .map((d) => applyPickupAdvance(ledger, d.id, { now: now(), commentId: () => newCommentId() }))
          .filter((r): r is RequirementRecord => r !== undefined);
        return advanced.length > 0 ? { requirements: advanced } : undefined;
      }).catch((err) => logger.warn('reqboard rollup (pickup advance) failed:', err));
    },
    logger: { info: (m) => logger.info(m), debug: (m) => logger.debug(m) },
  };
  const captureHandler = createSessionEventCaptureHook(captureHookDeps);
  const sessionEventCtx = ctx as unknown as {
    on?: (event: string, listener: (session: unknown, event: unknown) => void) => (() => void) | void;
  };
  const unsubscribeSessionEvents = sessionEventCtx.on?.('session/event', captureHandler);
  if (unsubscribeSessionEvents) disposers.push(unsubscribeSessionEvents);
  logger.info('reqboard capture hook registered: session/event user/message → 登记待立项评估（unbound 窗口）');

  // 捕获引导段（B：按窗口条件注入）：为每个 agent 窗口的 systemPrompt 组装求值，
  // 仅 unbound 且无遗留 pending 建议卡的窗口返回引导文本，其余返回 ''（renderPrompt
  // 滤空段 → 零噪音）。text 为函数式：每次组装读取 store.snapshot()（同步）判定当前窗口状态。
  ;(ctx as unknown as { inject?: (services: string[], cb: (c: any) => void) => void }).inject?.(
    ['systemPrompt'],
    (spCtx: { effect?: (fn: () => void, label?: string) => void; systemPrompt?: any }) => {
      spCtx.effect?.(() => {
        disposers.push(spCtx.systemPrompt.section({
          name: CAPTURE_SECTION,
          order: CAPTURE_SECTION_ORDER,
          text: (assembleContext: unknown) => {
            // 命中「本窗口待捕获消息」（hook 登记、turn/end 前）→ 注入针对性立项提示；
            // 否则维持静态引导（bound/有遗留 pending 时两者都返回 ''，零噪音）。
            const windowKey = windowKeyFromContext(
              assembleContext as { agent?: { id?: unknown }; scope?: unknown } | undefined,
            );
            const pending = windowKey ? pendingCapture.get(windowKey) : undefined;
            return captureSectionText(store.snapshot(), assembleContext, pending);
          },
        }));
      }, name + ': capture');
      logger.info('capture guidance section registered (unbound windows only, per-window eval)');
    },
  );

  // agent 工具：reqboard_create（先两问弹框确认、用户作答即立项 → 直接建 REQ）/
  // reqboard_status（窗口绑定状态，立项前自查）。direct-human 门在工具内认证。
  const toolDeps = {
    store,
    now,
    agents: () => agentsSvc,
    sessionProjections: () => projectionsSvc,
  };
  ;(ctx as unknown as { inject?: (services: string[], cb: (c: any) => void) => void }).inject?.(
    ['tools'],
    (toolsCtx: { effect?: (fn: () => void, label?: string) => void; tools?: any }) => {
      toolsCtx.effect?.(() => {
        disposers.push(toolsCtx.tools.register(defineCreateTool(toolDeps)));
        disposers.push(toolsCtx.tools.register(defineStatusTool(toolDeps)));
        disposers.push(toolsCtx.tools.register(defineMoveTool(toolDeps)));
      }, name + ': tools');
      logger.info('agent tools registered: reqboard_create / reqboard_status / reqboard_move');
    },
  );

  // 看板 REST/SSE API（经 webServer 惰性注入，注册即生效）
  ;(ctx as unknown as { inject?: (services: string[], cb: (webCtx: any) => void) => void }).inject?.(
    ['webServer'],
    (webCtx: { effect?: (fn: () => void, label?: string) => void; webServer?: any }) => {
      webCtx.effect?.(() => {
        webCtx.webServer.register({
          kind: 'prefix',
          path: '/dashboard/api/reqboard',
          handler: createReqboardHandler({ store, now }),
        });
      }, name + ': api');
      logger.info('routes registered: /dashboard/api/reqboard/* (state/events/req/task/triage CRUD + 人工确认立项)');
    },
  );

  // teardown：注销 section / 工具 / 事件订阅（重复 dispose 幂等，cordis effect wrapper 自带 epoch 守卫）
  ;(ctx as any).on('dispose', () => {
    for (const dispose of disposers.splice(0).reverse()) {
      try { dispose(); } catch (err) { logger.warn('disposer failed:', err); }
    }
  });
}
