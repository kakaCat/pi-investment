// dsh-pmboard · 项目看板（RFC 014）
// host 半：reqboard JSON+SSE API（/dashboard/api/reqboard/*）+ 两级状态机台账 +
// 捕获（用户裁定 · 创建即立项）：确定性消息 hook（session/event user/message 到达 →
// 检查窗口 unbound 且无遗留 pending → 登记待捕获消息）+ systemPrompt 捕获引导段
// （命中待捕获则注入引用消息原文的立项提示，让 LLM 调 pm 专有立项弹框 reqboard_capture）。
// 三问弹框（需求名称 / 需求类型 / 提示词难度）作答 = 立项门；创建即立项，无
// 待归类/建议卡中间态。M2 的自动分类 LLM（SessionSyncService）自 2026-09 起不再装配
// （修正 #1/#3：无第二 LLM、人在 loop）。
// 模块形状与 dashboard-execution 一致（name + apply 具名导出）；无静态 inject 的
// 页面插件一律走 (ctx as any).inject(...) 惰性注入（genome/dashboard 同款模式）。

import { Context } from '@deepseek-ai/cordis';
import * as path from 'node:path';
import { fileURLToPath } from 'node:url';
import { resolveAddressInjection } from './adapters/TemplateRoot.js';
import { JsonLedgerRepository as ReqboardStore } from './adapters/JsonLedgerRepository.js';
import { createReqboardHandler } from './http/routes.js';
import { applyPickupReconcile, applyTaskRollup } from './application/internal/rollup.js';
import { advanceRequirement } from './application/use-cases/AdvanceChain.js';
import { newCommentId } from './shared/protocol.js';
import { dshHomePath, nodeIsolationEnabled, type PluginConfig } from './plugin-config.js';
import { createCaptureRuntime, assembleDiveSessionDriver } from './wiring/pm-capture-root.js';
import {
  defineCreateTool,
  defineCaptureTool,
  defineStatusTool,
  defineTaskExecuteTool,
  defineAdvanceTool,
  defineTaskStatusTool,
  defineTaskReportTool,
  defineDecomposeTool,
  defineSubmitTool,
  defineAskConfirmTool,
  defineConfirmReceiptTool,
  defineAcceptSheetTool,
  defineNoteInterruptionTool,
  defineClearPauseTool,
} from './tools/index.js';
import { FileDocRepository } from './adapters/FileDocRepository.js'
import { InjectionLogFile } from './adapters/InjectionLogFile.js'
import { IsolationTraceFile } from './adapters/IsolationTraceFile.js'
import { NodeIsolationAdapter } from './adapters/NodeIsolationAdapter.js'
import { INJECTION_LOG_REL } from './application/internal/injection-log.js';
import { ISOLATION_TRACE_REL } from './application/internal/isolation-trace.js';
import { CAPTURE_DIAG_REL, captureDiag, initCaptureDiag } from './application/internal/diag-log.js';
import { CaptureRejectionFile } from './adapters/CaptureRejectionFile.js';
import { PendingConfirmRegistry } from './adapters/PendingConfirmRegistry.js';
import { CAPTURE_REJECTION_REL } from './application/internal/capture-rejections.js';
import { createNodeSettlementDispatcher } from './application/internal/node-settlement.js';
import { SystemClock } from './adapters/SystemClock.js';
import { RandomIdFactory } from './adapters/RandomIdFactory.js';
import { UserQuestionsAdapter } from './adapters/UserQuestionsAdapter.js';
import { GateAwareQuestions } from './adapters/GateAwareQuestions.js';
import { assembleGatePostChain, registerCaptureGuidance } from './gate-wiring.js';
import { SessionProbeAdapter } from './adapters/SessionProbeAdapter.js';
import { WorkflowEngineRunner } from './adapters/WorkflowEngineRunner.js';
import { createFailureAlert } from './adapters/FailureAlert.js';
import { scheduleStartupScan } from './application/internal/startup-scan.js';
import type { UseCaseDeps } from './application/ports.js';
import ReqboardDiveManager from './application/dive/ReqboardDiveManager.js';
import { renderDiveRoundText } from './application/dive/round-state.js';
import type { DiveRoundPorts } from './application/dive/round-driver.js';

export const name = 'dsh-pmboard';

/** 台账文件名（DSH 主目录，卸载插件不删除）。 */
export const LEDGER_FILE = 'dsh-reqboard.json';

/** 捕获引导段名（systemPrompt 全局唯一）与放置序位（identity 5 / genome 10-40 之后）。 */
export const CAPTURE_SECTION = 'reqboard:capture';
export const CAPTURE_SECTION_ORDER = 60;

// 兼容再导出（REQ-260924213231-b1c4 T-12）：既有 import { dshHomePath | nodeIsolationEnabled }
// 仍从 './index.js' 可用（实现在 ./plugin-config.ts），行为不变。
export { dshHomePath, nodeIsolationEnabled };

/**
 * 轮次边界判定（隔离纪律③「只在轮次边界执行」）：用 sessionProjections 的 turnBoundary
 * 投影——openTurnStartSeq 为 null 即"无 open turn"＝ agent 空闲，可安全做 surface 整段替换。
 * 投影/服务不可得（无 agent-loop、测试环境）或探测抛错 → 判不出，**保守返回 false**
 * （不替换 + 留痕 skipped/agent_busy）——活动轮次替换会被框架硬拒（D-15），
 * 宁可跳过也不猜（响亮失败优于静默猜测）。
 */
function turnBoundaryIdle(projectionsSvc: unknown, session: unknown): boolean {
  return turnBoundaryIdleState(projectionsSvc, session) === 'idle';
}

/**
 * 轮次边界**三态**判定（2026-09-26）——给闸门链的"无 open turn"门用。
 *
 * 与 turnBoundaryIdle 同源，但把"判不出"和"明确忙"分开：
 *   idle    = openTurnStartSeq === null（无 open turn，可安全做 surface 替换与唤醒）
 *   busy    = 有 open turn（活动轮次：替换会被硬拒 D-15；唤醒会与 LLM 打架；H2 会 skip）
 *   unknown = 投影/服务不可得（无 agent-loop、测试环境、看板通道无 session）或探测抛错
 *
 * 为什么必须分开：H2 的口径是"判不出就跳过"（保守），而**链**不能这样——
 * 看板确认通道与测试环境都判不出，拿 false 当整链门会把它们全堵死。
 * 所以链只在**明确 busy** 时延后（且不消费待处理闸门，留给下个边界重试）。
 */
function turnBoundaryIdleState(projectionsSvc: unknown, session: unknown): 'idle' | 'busy' | 'unknown' {
  const projections = projectionsSvc as {
    stateOf?: (s: unknown, kind: string) => { openTurnStartSeq?: unknown } | undefined
  } | undefined;
  if (typeof projections?.stateOf !== 'function') return 'unknown';
  if (session === undefined || session === null) return 'unknown';
  try {
    const boundary = projections.stateOf(session, 'turnBoundary');
    if (boundary === undefined) return 'unknown';
    return boundary.openTurnStartSeq === null ? 'idle' : 'busy';
  } catch {
    return 'unknown';
  }
}

export function apply(ctx: Context, config?: PluginConfig): void {
  // 【REQ-f6307c T3】文件化诊断通道初始化（stdout 可能进死管道，文件才是可靠观测面）
  initCaptureDiag(dshHomePath(config, CAPTURE_DIAG_REL));
  captureDiag('reqboard-capture [EARLY]: apply function STARTED');
  const logger = ctx.logger(name);
  logger.info('reqboard-capture [EARLY]: apply function STARTED');
  const store = new ReqboardStore({ file: dshHomePath(config, LEDGER_FILE) });
  // 急加载：fresh boot 时让首个 GET /state 见到台账而非空板（load 永不抛——损坏即隔离）
  void store.load();
  const now = () => Date.now()
  
  // Dive 服务实例化已下移到 createCaptureRuntime 之后（T-5：round 半的投递端口 = deliverer）。
  
  // 桥接 store 订阅到 Cordis 事件系统（优化：支持 Dive 事件驱动续跑）
  store.subscribe((change) => {
    // 发出 Cordis 事件，供 Dive 管理器监听
    if (change.kind === 'requirement-moved' && change.requirements.length > 0) {
      // 为每个变更的需求发出事件
      for (const req of change.requirements) {
        // 从状态历史推断 from → to（如果有历史记录）
        const history = req.statusHistory ?? []
        const lastTwo = history.slice(-2)
        const from = lastTwo.length >= 2 ? lastTwo[0].status : req.status
        const to = req.status
        
        ctx.emit('reqboard/requirement-moved', {
          requirementId: req.id,
          from,
          to,
        })
      }
    }
  })
  logger.info('Store subscription bridge initialized (Cordis events enabled)')
  
  // 注入留痕（REQ-422af1 t6，INV-6）：<dshHome>/state/prompt-injection-log.json（ring buffer 500 条，原子写）。
  const injectionLog = new InjectionLogFile(
    dshHomePath(config, INJECTION_LOG_REL),
    now,
    (err) => logger.warn('reqboard 注入留痕写入失败:', err),
  );

  // 启动对账（R0 + R2）：让升级前积压的 draft 需求立刻进入评审，并结算已完成的需求。
  void store
    .load()
    .then(() =>
      store.mutate('requirement-moved', (ledger) => {
        const ctx = { now: now(), commentId: () => newCommentId() };
        const advanced = [...applyPickupReconcile(ledger, ctx), ...applyTaskRollup(ledger, ctx)];
        return advanced.length > 0 ? { requirements: advanced } : undefined;
      }),
    )
    .then((result) => {
      if (result.changed.requirements.length > 0) {
        logger.info(
          `reqboard 启动对账：${result.changed.requirements.length} 条需求自动推进（${result.changed.requirements.map((r) => r.id).join(', ')}）`,
        );
      }
    })
    .catch((err) => logger.warn('reqboard 启动对账失败（不影响服务）:', err));

  // 乙流程依赖的运行时服务（惰性获取，未就绪/缺失时相关能力降级放行）：
  //   agents             → requireLiveDriver（服务可得则校验 live driver，缺失放行）
  //   sessionProjections → requireDirectHuman（扫描 user 消息 / 执行窗口状态，缺失放行）
  let agentsSvc: unknown;
  let projectionsSvc: unknown;
  let userQuestionsSvc: unknown;
  /** REQ-a33899 t5：系统提示词装配服务（读时折算固定提示词成本）。 */
  let systemPromptSvc: unknown;
  ;(ctx as unknown as { inject?: (services: string[], cb: (c: any) => void) => void }).inject?.(
    ['userQuestions'],
    (uqCtx: { userQuestions?: unknown } | undefined) => {
      userQuestionsSvc = uqCtx?.userQuestions;
      if (userQuestionsSvc !== undefined) {
        logger.debug('userQuestions service ready (reqboard_ask_confirm 弹框通道可用)');
      }
    },
  );
  ;(ctx as unknown as { inject?: (services: string[], cb: (c: any) => void) => void }).inject?.(
    ['agents'],
    (agentsCtx: { agents?: unknown }) => {
      agentsSvc = agentsCtx.agents;
      logger.debug('agents service ready (reqboard tools live-driver check enabled)');
    },
  );
  // REQ-4842fe t4：子卡执行引擎（workflow-worker-thread provider，已在位）。缺失时
  // runner 返回 engine_unavailable → 子卡显式失败，不静默成功。
  let workflowEngineSvc: unknown;
  ;(ctx as unknown as { inject?: (services: string[], cb: (c: any) => void) => void }).inject?.(
    ['workflowEngine'],
    (wfCtx: { workflowEngine?: unknown }) => {
      workflowEngineSvc = wfCtx?.workflowEngine;
      logger.debug(workflowEngineSvc === undefined
        ? 'workflowEngine service 不可用（子卡执行将显式失败）'
        : 'workflowEngine service ready (reqboard_task_run 子卡执行可用)');
    },
  );
  ;(ctx as unknown as { inject?: (services: string[], cb: (c: any) => void) => void }).inject?.(
    ['sessionProjections'],
    (spCtx: { sessionProjections?: unknown }) => {
      projectionsSvc = spCtx.sessionProjections;
      logger.debug('sessionProjections service ready (reqboard tools direct-human check enabled)');
    },
  );

  // ── 节点结算 → 隔离执行分发（REQ-422af1 t10，默认关）───────────────────────
  // 开关优先级：config.nodeIsolation > env NODE_ISOLATION > 默认 false。关时隔离代码路径
  // 执行 0 次。两个端口的唯一 I/O 实现都在 adapters（application 层禁 import @deepseek-ai/*）：
  //   isolation → NodeIsolationAdapter（surface 原语 + tool 配对边界检查，t9）
  //   trace     → IsolationTraceFile（state/node-isolation-log.json，ring buffer 原子写）
  const nodeIsolation = nodeIsolationEnabled(config);
  // REQ-260922213356-4a45 T-3：模板地址注入——绝对模板根（配置优先，否则包根 ../templates）+ 开关。
  const address = resolveAddressInjection(config, path.dirname(fileURLToPath(import.meta.url)), (m) => logger.warn(m));
  const docs = new FileDocRepository();
  const clock = new SystemClock();
  // REQ-260924213231-b1c4 T-6（FR-3）：挂起确认注册表（内存 ticket → 状态）——弹框超宽限时
  // 登记 ticket，人作答后由后台落章并回填，agent 用 reqboard_confirm_receipt 取回执。
  const pendingConfirms = new PendingConfirmRegistry();
  const isolationTrace = new IsolationTraceFile(
    dshHomePath(config, ISOLATION_TRACE_REL),
    (err) => logger.warn('reqboard 隔离留痕写入失败（只告警，不影响流水线）:', err),
  );
  // REQ-260922012924-2e29 FR-5：立项拒绝留痕（state/capture-rejections.json，ring buffer 原子写）。
  const captureRejections = new CaptureRejectionFile(
    dshHomePath(config, CAPTURE_REJECTION_REL),
    (err) => logger.warn('reqboard 立项拒绝留痕写入失败（只告警，不影响立项路径）:', err),
  );
  const settlement = createNodeSettlementDispatcher({
    enabled: nodeIsolation,
    isolationFor: (session, _settle) => new NodeIsolationAdapter(session, {
      idle: () => turnBoundaryIdle(projectionsSvc, session),
      plugin: name,
    }),
    trace: isolationTrace,
    repo: store,
    docs,
    clock,
    address,
    // 纪律①「先落盘再遗弃」：先把写队列排空（read 走同一条串行队列）再取持久化 revision
    // （JsonLedgerRepository 在 persistAtomic 成功后才 bump，故 revision 即"已落盘"证据指针）。
    persistArtifacts: async () => {
      await store.read(() => undefined);
      return store.snapshot().revision;
    },
    warn: (message) => logger.warn(message),
  });
  logger.info(
    nodeIsolation
      ? 'reqboard 节点隔离已开启（NODE_ISOLATION）：节点结算点经 setImmediate 异步边界执行 surface 整段替换'
      : 'reqboard 节点隔离关闭（默认）：结算点只发信号，隔离代码路径执行 0 次',
  );

  const disposers: Array<() => void> = [];

  // 捕获根运行时（REQ-260924213231-b1c4 T-12：三张共享表 + 唯一投递实现抽到
  // ./wiring/pm-capture-root.js，组合根只留装配顺序；driver 装配见下方 assembleDiveSessionDriver）。
  const { pendingCapture, toolTrace, recentUserMsgs, deliverer } = createCaptureRuntime({
    plugin: name,
    getAgents: () => agentsSvc,
  });

  // ── Dive 服务（REQ-260926215013-1568 T-5）：订阅持有者 + round 端口提供者 ──────────
  // 必须在 createCaptureRuntime 之后（round 半的投递端口 = deliverer）；agentsSvc 经闭包惰性读取。
  const diveRoundPorts: DiveRoundPorts = {
    repo: store,
    agents: {
      get: (id: string) => (agentsSvc as { get?: (id: string) => unknown } | undefined)?.get?.(id),
      withoutInitiator: <T,>(op: () => T): T => {
        const a = agentsSvc as { withoutInitiator?: <U>(f: () => U) => U } | undefined
        return typeof a?.withoutInitiator === 'function' ? a.withoutInitiator(op) : op()
      },
    },
    // 插件 fiber 处于 ACTIVE(2) 才算可驱动；读不到（测试/降级）→ 放行，避免静默停摆。
    fiberActive: () => {
      const state = (ctx as unknown as { fiber?: { state?: number } }).fiber?.state
      return state === undefined ? true : state === 2
    },
    delivery: deliverer,
    cancel: (agent, cause) => (agent as { cancel?: (c: string) => void } | undefined)?.cancel?.(cause),
    whenIdle: (agent) => {
      const p = (agent as { whenIdle?: () => Promise<void> } | undefined)?.whenIdle?.()
      return p === undefined ? Promise.resolve() : p
    },
    // FR-3 耐久检查点：兑现台账写队列排空（与 persistArtifacts 同口径）。
    checkpoint: async () => { await store.read(() => undefined) },
    renderRoundText: renderDiveRoundText,
    now,
    logger: { info: (m) => logger.info(m), debug: (m) => logger.debug(m), warn: (m, e) => logger.warn(m, e) },
  }
  const diveManager = new ReqboardDiveManager(ctx, diveRoundPorts)
  logger.info('ReqboardDiveManager initialized (round 半已接线)')
  disposers.push(() => { void diveManager.teardown() })

  // 闸门后置链装配（REQ-e3b6a0）：抽到 ./gate-wiring.js（REQ-f0579a t5 尺寸门禁）。
  const gateChain = assembleGatePostChain({
    store, docs, clock, now, isolationTrace, injectionLog, deliverer, logger, plugin: name,
    compactionEnabled: nodeIsolationEnabled(config),
    idle: (session: unknown) => turnBoundaryIdle(projectionsSvc, session),
    // 三态门（2026-09-26）：明确 busy → 链延后且不消费待处理闸门（修"静默丢压缩"）
    idleState: (session: unknown) => turnBoundaryIdleState(projectionsSvc, session),
    address,
  });

  // Dive 会话驱动器装配（原 CaptureHook，2026-09-26 废弃并迁入 application/dive）：
  // 抽到 ./wiring/pm-capture-root.js；**两路订阅都由 Dive 服务持有**：
  //   · session/event（采集/簿记）→ attachSessionDriver
  //   · agent/status === idle（驱动点，对齐 dsh-goal-round-driver）→ attachAgentStatus
  // useCaseDeps 尚未构造 → 以惰性 getter 传入（driver 只在异步边界取用）。
  const unsubscribeSessionEvents = assembleDiveSessionDriver({
    store, runtime: { pendingCapture, toolTrace, recentUserMsgs, deliverer },
    now, address, injectionLog, gateChain,
    onNodeSettled: (settle, session) => settlement.onSettle(settle, session),
    useCaseDeps: () => useCaseDeps,
    logger, plugin: name,
    round: diveManager.roundDriver(),
    attachSessionDriver: (handler) => diveManager.attachSessionDriver(handler),
    attachAgentStatus: (handler) => diveManager.attachAgentStatus(handler),
  });
  if (unsubscribeSessionEvents) disposers.push(unsubscribeSessionEvents);

  // 捕获引导段装配（按窗口条件注入）：抽到 ./gate-wiring.js（REQ-f0579a t5 尺寸门禁）。
  registerCaptureGuidance(ctx, {
    disposers, store, pendingCapture, injectionLog, logger, plugin: name, address,
    sectionName: CAPTURE_SECTION, sectionOrder: CAPTURE_SECTION_ORDER,
    onSystemPrompt: (svc) => { systemPromptSvc = svc; },
  });

  // agent 工具：reqboard_capture（三问弹框 + 创建即立项）/ reqboard_create（手工路径）/
  // reqboard_status（自查）。用例依赖 = 组合根装配 adapters → application 用例。
  const useCaseDeps: UseCaseDeps = {
    repo: store,
    docs,
    clock,
    ids: new RandomIdFactory(),
    session: new SessionProbeAdapter({
      toolTrace,
      recentUserMsgs,
      agents: () => agentsSvc,
      sessionProjections: () => projectionsSvc,
      now,
    }),
    // 能力的唯一织入点（REQ-e3b6a0 t7）：包装后，任何带 opts.gate 的弹框自动进入后置链。
    questions: new GateAwareQuestions(new UserQuestionsAdapter(() => userQuestionsSvc), gateChain, { now }),
    rejections: captureRejections,
    workflow: new WorkflowEngineRunner(() => workflowEngineSvc as never),
    // REQ-260923222557-d3b0 FR-2/FR-3：事件型 worktree 提示词复用同一投递实现。
    delivery: deliverer,
    // REQ-260924213231-b1c4 T-6（FR-3）：装配非阻塞弹框能力（缺省 = 保持旧阻塞语义）。
    pendingConfirms,
    alert: createFailureAlert({ log: (m) => logger.error(m), deliver: (wk, text) => { deliverer.deliver(wk, { text }); }, windowFor: (id) => store.snapshot().requirements.find((x) => x.id === id)?.sourceSessionId }),
  };

  // REQ-4842fe t7：启动恢复扫描（崩溃不丢链）。
  scheduleStartupScan({ load: () => store.load(), deps: useCaseDeps, info: (m) => logger.info(m), warn: (m, err) => logger.warn(m, err) });
  ;(ctx as unknown as { inject?: (services: string[], cb: (c: any) => void) => void }).inject?.(
    ['tools'],
    (toolsCtx: { effect?: (fn: () => void, label?: string) => void; tools?: any }) => {
      toolsCtx.effect?.(() => {
        // 工具面（REQ-47939a t8：13→9 收敛；REQ-327bdf 增 task_execute/task_status；REQ-e3b6a0 t8 增 reqboard_capture）
        disposers.push(toolsCtx.tools.register(defineCreateTool(useCaseDeps)));
        disposers.push(toolsCtx.tools.register(defineCaptureTool(useCaseDeps)));
        disposers.push(toolsCtx.tools.register(defineStatusTool(useCaseDeps)));
        disposers.push(toolsCtx.tools.register(defineTaskReportTool(useCaseDeps)));
        // 恢复：批准计划后的拆分落库入口（自动拆分路径缺 JobsPort，见 DecomposeTool 文件头）
        disposers.push(toolsCtx.tools.register(defineDecomposeTool(useCaseDeps)));
        disposers.push(toolsCtx.tools.register(defineSubmitTool(useCaseDeps)));
        disposers.push(toolsCtx.tools.register(defineAskConfirmTool(useCaseDeps)));
        disposers.push(toolsCtx.tools.register(defineConfirmReceiptTool(useCaseDeps)));
        disposers.push(toolsCtx.tools.register(defineAcceptSheetTool(useCaseDeps)));
        disposers.push(toolsCtx.tools.register(defineTaskExecuteTool(useCaseDeps)));
        disposers.push(toolsCtx.tools.register(defineAdvanceTool(useCaseDeps)));
        disposers.push(toolsCtx.tools.register(defineTaskStatusTool(useCaseDeps)));
        // REQ-260924213231-b1c4 T-9（FR-6 / I-8）：断点显式兜底（B′ 入口）。
        disposers.push(toolsCtx.tools.register(defineNoteInterruptionTool(useCaseDeps)));
        disposers.push(toolsCtx.tools.register(defineClearPauseTool(useCaseDeps)));
      }, name + ': tools');
      logger.info(
        'agent tools registered (13): reqboard_create / reqboard_capture / reqboard_status / reqboard_task_run / reqboard_task_execute / reqboard_task_status / '
        + 'reqboard_task_report / reqboard_submit(kind) / reqboard_ask_confirm / reqboard_confirm_receipt / reqboard_accept_sheet / reqboard_note_interruption / reqboard_clear_pause',
      );
    },
  );

  // Client 资产：纯声明式（package.json dsh.client + exports["./client"] → lib/client.js），
  // 宿主 dsh-client-modules 自动扫描已启用 Loader 条目组合启动图，无需逐插件接线。

  // 看板 REST/SSE API（经 webServer 惰性注入，注册即生效）
  ;(ctx as unknown as { inject?: (services: string[], cb: (webCtx: any) => void) => void }).inject?.(
    ['webServer'],
    (webCtx: { effect?: (fn: () => void, label?: string) => void; webServer?: any }) => {
      webCtx.effect?.(() => {
        webCtx.webServer.register({
          kind: 'prefix',
          path: '/dashboard/api/reqboard',
          // injectionLog 只以**只读端口**身份进入路由（t11）：看板能读「本次注入了什么」，不能写。
          handler: createReqboardHandler({
            store,
            now,
            docs,
            injectionLog,
            // REQ-260923134706-e72f t2：isolationTrace 只读进路由（看板「执行流程→上下文管理」数据源），不能写。
            isolationLog: isolationTrace,
            // REQ-e3b6a0 t9 / FR-9：看板「确认产物」纳入切面——确认即推进 + 链侧投递（H2 需要会话句柄）。
            gateChain,
            agents: () => agentsSvc as { get?: (id: string) => unknown } | undefined,
            systemPrompt: () => systemPromptSvc,
            tokenSnapshot: (wk) => { // REQ-b545fe t6: 注入快照提供者
              try {
                return useCaseDeps.session.tokenTotals(wk);
              } catch {
                return undefined;
              }
            }, advance: (reqId: string) => advanceRequirement(useCaseDeps, reqId).then(o => ({ steps: o.steps.length, stopped: o.stopped as string })),
            // 看板「拆分」入口（2026-09-26）：批准计划后的落库恢复通道（自动拆分缺 JobsPort）。
            applicationDeps: useCaseDeps,
          }),
        });
      }, name + ': api');
      logger.info('routes registered: /dashboard/api/reqboard/* (state/events/req/task CRUD + 人工确认立项)');
    },
  );

  // teardown：注销 section / 工具 / 事件订阅（重复 dispose 幂等，cordis effect wrapper 自带 epoch 守卫）
  ;(ctx as any).on('dispose', () => {
    for (const dispose of disposers.splice(0).reverse()) {
      try { dispose(); } catch (err) { logger.warn('disposer failed:', err); }
    }
  });
}