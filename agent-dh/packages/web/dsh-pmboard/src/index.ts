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
import * as os from 'node:os';
import * as path from 'node:path';
import { fileURLToPath } from 'node:url';
import { resolveAddressInjection } from './adapters/TemplateRoot.js';
import { JsonLedgerRepository as ReqboardStore } from './adapters/JsonLedgerRepository.js';
import { createReqboardHandler } from './http/routes.js';
import { draftRequirementsFor } from './application/internal/window.js';
import { applyPickupAdvance, applyPickupReconcile, applyTaskRollup } from './application/internal/rollup.js';
import { advanceRequirement } from './application/use-cases/AdvanceChain.js';
import { newCommentId, type RequirementRecord } from './shared/protocol.js';
import { createSessionEventCaptureHook, type CaptureHookDeps } from './adapters/CaptureHook.js';
import type { ToolTraceEntry } from './adapters/SessionProbeAdapter.js';

import {
  defineCreateTool,
  defineCaptureTool,
  defineStatusTool,
  defineMoveTool,
  defineDecomposeTool,
  defineTaskMoveTool,
  defineTaskExecuteTool,
  defineAdvanceTool,
  defineTaskStatusTool,
  defineTaskReportTool,
  defineSubmitTool,
  defineAskConfirmTool,
  defineAcceptSheetTool,
} from './tools/index.js';
import { FileDocRepository } from './adapters/FileDocRepository.js'
import { InjectionLogFile } from './adapters/InjectionLogFile.js'
import { IsolationTraceFile } from './adapters/IsolationTraceFile.js'
import { NodeIsolationAdapter } from './adapters/NodeIsolationAdapter.js'
import { INJECTION_LOG_REL } from './application/internal/injection-log.js';
import { ISOLATION_TRACE_REL } from './application/internal/isolation-trace.js';
import { CAPTURE_DIAG_REL, captureDiag, initCaptureDiag } from './application/internal/diag-log.js';
import { CaptureRejectionFile } from './adapters/CaptureRejectionFile.js';
import { CAPTURE_REJECTION_REL } from './application/internal/capture-rejections.js';
import { createNodeSettlementDispatcher } from './application/internal/node-settlement.js';
import { SystemClock } from './adapters/SystemClock.js';
import { RandomIdFactory } from './adapters/RandomIdFactory.js';
import { UserQuestionsAdapter } from './adapters/UserQuestionsAdapter.js';
import { AgentDeliverer } from './adapters/AgentDeliverer.js';
import { GateAwareQuestions } from './adapters/GateAwareQuestions.js';
import { assembleGatePostChain, registerCaptureGuidance } from './gate-wiring.js';
import { SessionProbeAdapter } from './adapters/SessionProbeAdapter.js';
import { WorkflowEngineRunner } from './adapters/WorkflowEngineRunner.js';
import { createFailureAlert } from './adapters/FailureAlert.js';
import { scheduleStartupScan } from './application/internal/startup-scan.js';
import type { UseCaseDeps } from './application/ports.js';

export const name = 'dsh-pmboard';

/** 台账文件名（DSH 主目录，卸载插件不删除）。 */
export const LEDGER_FILE = 'dsh-reqboard.json';

/** 捕获引导段名（systemPrompt 全局唯一）与放置序位（identity 5 / genome 10-40 之后）。 */
export const CAPTURE_SECTION = 'reqboard:capture';
export const CAPTURE_SECTION_ORDER = 60;

interface PluginConfig {
  /** DSH 主目录（默认 ~/.dsh） */
  dshHome?: string;
  /**
   * 节点隔离开关（REQ-422af1 t10）。**默认关**：关闭时隔离代码路径执行 0 次，
   * 行为完全等同改造前（design/migration.md §3）。显式配置优先于环境变量。
   */
  nodeIsolation?: boolean;
  /** 模板根绝对路径（REQ-260922213356-4a45 T-3）；缺省按包根 templates 解析。 */
  templateRoot?: string;
  /** 地址段开关（T-3；默认 true；false = 完全回退到改造前注入行为）。 */
  addressSectionEnabled?: boolean;
}

export function dshHomePath(config: PluginConfig | undefined, file: string): string {
  const home = config?.dshHome || process.env.DSH_HOME || path.join(os.homedir(), '.dsh');
  return path.join(home, file);
}

/**
 * 节点隔离开关（REQ-422af1 t10 / design/migration.md §3）：**默认关**。
 * 优先级：显式配置 nodeIsolation > 环境变量 NODE_ISOLATION(=1/true/on/yes) > 默认 false。
 * 关闭时 createNodeSettlementDispatcher 的 enabled=false 分支直接返回——
 * 不调度、不建端口、不触会话（stats 四项计数全 0 即其可执行证明）。
 */
export function nodeIsolationEnabled(
  config?: PluginConfig,
  env: Record<string, string | undefined> = process.env,
): boolean {
  if (config?.nodeIsolation !== undefined) return config.nodeIsolation;
  const raw = env.NODE_ISOLATION;
  if (raw === undefined) return false;
  return ['1', 'true', 'on', 'yes'].includes(raw.trim().toLowerCase());
}

/**
 * 轮次边界判定（隔离纪律③「只在轮次边界执行」）：用 sessionProjections 的 turnBoundary
 * 投影——openTurnStartSeq 为 null 即"无 open turn"＝ agent 空闲，可安全做 surface 整段替换。
 * 投影/服务不可得（无 agent-loop、测试环境）或探测抛错 → 判不出，**保守返回 false**
 * （不替换 + 留痕 skipped/agent_busy）——活动轮次替换会被框架硬拒（D-15），
 * 宁可跳过也不猜（响亮失败优于静默猜测）。
 */
function turnBoundaryIdle(projectionsSvc: unknown, session: unknown): boolean {
  const projections = projectionsSvc as {
    stateOf?: (s: unknown, kind: string) => { openTurnStartSeq?: unknown } | undefined
  } | undefined;
  if (typeof projections?.stateOf !== 'function') return false;
  try {
    const boundary = projections.stateOf(session, 'turnBoundary');
    if (boundary === undefined) return false;
    return boundary.openTurnStartSeq === null;
  } catch {
    return false;
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

  // ── 确定性消息捕获 hook（用户裁定 #2/#3）─────────────────────────────
  // 订阅 session/event：用户消息到达（user/message，direct human）→ 若该窗口
  // unbound 且无遗留 pending 建议卡（旧流程 triage 产物）→ 登记「待捕获消息」到
  // pendingCapture；turn/end 清除（该回合 LLM 已消费本次立项评估）。capture section
  // 组装时同引用读取并注入针对性立项提示——hook 只保证确定性触发，立项判定与内容
  // 留给 LLM + 人工（reqboard_capture 三问弹框作答 = 确认，同一次调用内直接建 REQ）。
  const pendingCapture = new Map<string, { windowKey: string; text: string; capturedAt: number }>();
  // 工具痕迹表（REQ-2e9473 t05）：窗口 → tool/call 事件序列，done 凭证门（t06）读取。
  const toolTrace = new Map<string, ToolTraceEntry[]>();
  // 最近用户消息缓冲（REQ-2e9473 t10）：窗口 → 清洗后用户消息，confirm_artifact 文字确认核验读取。
  const recentUserMsgs = new Map<string, import('./adapters/SessionProbeAdapter.js').RecentUserMsg[]>();
  // 唯一投递实现（REQ-e3b6a0 t4）：状态转移注入、30 分钟催办、后续闸门链 H4 三者共用同一形状。
  const deliverer = new AgentDeliverer(() => agentsSvc, { plugin: name });

  // 闸门后置链装配（REQ-e3b6a0）：抽到 ./gate-wiring.js（REQ-f0579a t5 尺寸门禁）。
  const gateChain = assembleGatePostChain({
    store, docs, clock, now, isolationTrace, injectionLog, deliverer, logger, plugin: name,
    compactionEnabled: nodeIsolationEnabled(config),
    idle: (session: unknown) => turnBoundaryIdle(projectionsSvc, session),
    address,
  });

  const captureHookDeps: CaptureHookDeps = {
    snapshot: () => store.snapshot(),
    pending: pendingCapture,
    now,
    address,
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
    // REQ-31e11f t5 + REQ-e3b6a0 t4：状态转移纪律与产物催办文案向绑定会话投递。
    // 投递形状统一走 AgentDeliverer（唯一实现）——此前 `agents.followup(id, msg)` 把
    // AgentRegistry 当 Agent 用，typeof 守卫恒 false，于是"状态转移注入"与"30 分钟催办"
    // 自诞生起从未投递过（同一根因的另两个受害者）。
    onStagePrompt: (windowKey, prompt) => {
      const result = deliverer.deliver(windowKey, { text: prompt });
      if (result.delivered) {
        logger.debug(`reqboard stage-prompt injected → ${windowKey.slice(0, 16)}`);
      } else {
        logger.warn(`reqboard stage-prompt 未投递（${windowKey.slice(0, 16)}）：${result.reason ?? '未知原因'}`);
      }
    },
    toolTrace,
    recentUserMsgs,
    injectionLog,
    // REQ-422af1 t10：节点结算信号 → 隔离分发（开关关时 dispatcher 一次都不执行）。
    onNodeSettled: (settle, session) => settlement.onSettle(settle, session),
    // REQ-e3b6a0 t7：**闸门后置链 Phase B 的唯一时机**。闸门作答不一定伴随用户消息，
    // 故不能只靠 onNodeSettled；且监听器内不得做会话写操作（D-17）→ 放到异步边界。
    // （链按 (windowKey, gate, decidedAt) 幂等，与结算路径重复触发也只跑一轮。）
    onTurnEnd: (windowKey, session) => {
      setImmediate(() => {
        void gateChain.runPending(windowKey, session).catch((err) => {
          logger.warn('reqboard gate-chain run failed:', err);
        });
      });
    },
    logger: { info: (m) => logger.info(m), debug: (m) => logger.debug(m) },
  };
  const captureHandler = createSessionEventCaptureHook(captureHookDeps);
  const sessionEventCtx = ctx as unknown as {
    on?: (event: string, listener: (session: unknown, event: unknown) => void) => (() => void) | void;
  };
  const unsubscribeSessionEvents = sessionEventCtx.on?.('session/event', captureHandler);
  if (unsubscribeSessionEvents) disposers.push(unsubscribeSessionEvents);
  // 【诊断日志-节点1】Hook 订阅状态（文件双写，防 stdout 死管道）
  captureDiag(`reqboard-capture [NODE-1]: Hook subscription ${unsubscribeSessionEvents ? 'SUCCESS' : 'FAILED'} (unsubscribe=${typeof unsubscribeSessionEvents})`);
  logger.info(`reqboard-capture [NODE-1]: Hook subscription ${unsubscribeSessionEvents ? 'SUCCESS' : 'FAILED'} (unsubscribe=${typeof unsubscribeSessionEvents})`);
  logger.info('reqboard capture hook registered: session/event user/message → 登记待立项评估（unbound 窗口）');

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
        disposers.push(toolsCtx.tools.register(defineMoveTool(useCaseDeps)));
        disposers.push(toolsCtx.tools.register(defineDecomposeTool(useCaseDeps)));
        disposers.push(toolsCtx.tools.register(defineTaskMoveTool(useCaseDeps)));
        disposers.push(toolsCtx.tools.register(defineTaskReportTool(useCaseDeps)));
        disposers.push(toolsCtx.tools.register(defineSubmitTool(useCaseDeps)));
        disposers.push(toolsCtx.tools.register(defineAskConfirmTool(useCaseDeps)));
        disposers.push(toolsCtx.tools.register(defineAcceptSheetTool(useCaseDeps)));
        disposers.push(toolsCtx.tools.register(defineTaskExecuteTool(useCaseDeps)));
        disposers.push(toolsCtx.tools.register(defineAdvanceTool(useCaseDeps)));
        disposers.push(toolsCtx.tools.register(defineTaskStatusTool(useCaseDeps)));
      }, name + ': tools');
      logger.info(
        'agent tools registered (13): reqboard_create / reqboard_capture / reqboard_status / reqboard_move / reqboard_decompose / reqboard_task_move / reqboard_task_run / reqboard_task_execute / reqboard_task_status / '
        + 'reqboard_task_report / reqboard_submit(kind) / reqboard_ask_confirm / reqboard_accept_sheet',
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