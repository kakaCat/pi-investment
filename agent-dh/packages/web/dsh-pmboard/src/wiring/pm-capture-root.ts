/**
 * 捕获根装配（REQ-260924213231-b1c4 T-12：index.ts 超 400 行尺寸门禁，从组合根抽出本块）。
 * 注释随代码搬（硬约束：不重写、不删"为什么/事故出处"型注释）；本文件是组合根的延伸，
 * 依赖方向与 index.ts 相同（adapters + application 均可引用）。
 *
 * 内容：三张共享表（待捕获候选 / 工具痕迹 / 最近用户消息）+ 唯一投递实现（AgentDeliverer）
 * 的构造，以及 Dive 会话驱动器的装配（**订阅由 Dive 服务持有**）。
 */
import { AgentDeliverer } from '../adapters/AgentDeliverer.js';
import { createDiveSessionDriver, type DiveSessionDriverDeps } from '../application/dive/session-driver.js'
import type { DiveRoundDriver } from '../application/dive/round-driver.js';
import type { ToolTraceEntry, RecentUserMsg } from '../adapters/SessionProbeAdapter.js';
import type { JsonLedgerRepository } from '../adapters/JsonLedgerRepository.js';
import type { InjectionLogFile } from '../adapters/InjectionLogFile.js';
import type { AddressInjection } from '../adapters/TemplateRoot.js';
import type { GateChainPort } from '../application/gate/GatePostChain.js';
import type { GatePromptPort, TaskStore, UseCaseDeps } from '../application/ports.js';
import { gatePromptExhaustedComment } from '../application/dive/gate-prompt.js';
import { draftRequirementsFor } from '../application/internal/window.js';
import { isDrivableRequirement } from '../application/dive/round-state.js';
import { applyPickupAdvance } from '../application/internal/rollup.js';
import { snapshotProviderFor } from '../application/internal/token-usage.js';
import { newCommentId, type RequirementRecord } from '../shared/protocol.js';
import { captureDiag } from '../application/internal/diag-log.js';
import { noteInterruptionForWindow } from '../application/use-cases/NoteInterruption.js';

/** 待捕获候选（hook 登记 → capture section 同引用读取）。 */
export interface PendingCaptureMessage {
  windowKey: string;
  text: string;
  capturedAt: number;
}

/** 组合根后续装配（闸门链 / 工具用例 / 路由）共用的运行时对象。 */
export interface CaptureRuntimeDeps {
  plugin: string;
  /** agents 服务惰性读取（inject 回调到达后才有值）。 */
  getAgents: () => unknown;
}

export interface CaptureRuntime {
  pendingCapture: Map<string, PendingCaptureMessage>;
  toolTrace: Map<string, ToolTraceEntry[]>;
  recentUserMsgs: Map<string, RecentUserMsg[]>;
  deliverer: AgentDeliverer;
}

/** 建三张共享表 + 唯一投递实现（顺序无关，均为空容器/无 I/O 构造）。 */
export function createCaptureRuntime(deps: CaptureRuntimeDeps): CaptureRuntime {
  const pendingCapture = new Map<string, PendingCaptureMessage>();
  // 工具痕迹表（REQ-2e9473 t05）：窗口 → tool/call 事件序列，done 凭证门（t06）读取。
  const toolTrace = new Map<string, ToolTraceEntry[]>();
  // 最近用户消息缓冲（REQ-2e9473 t10）：窗口 → 清洗后用户消息，confirm_artifact 文字确认核验读取。
  const recentUserMsgs = new Map<string, RecentUserMsg[]>();
  // 唯一投递实现（REQ-e3b6a0 t4）：状态转移注入、30 分钟催办、后续闸门链 H4 三者共用同一形状。
  const deliverer = new AgentDeliverer(deps.getAgents, { plugin: deps.plugin });
  return { pendingCapture, toolTrace, recentUserMsgs, deliverer };
}

export interface DiveDriverAssemblyDeps {
  store: JsonLedgerRepository;
  runtime: CaptureRuntime;
  now: () => number;
  /** 模板地址注入（REQ-260922213356-4a45 T-3）：绝对模板根 + 开关；缺省不注入。 */
  address?: AddressInjection;
  injectionLog: InjectionLogFile;
  gateChain: GateChainPort;
  /** 节点结算信号入口（隔离端口由组合根按会话构造）。 */
  onNodeSettled: NonNullable<DiveSessionDriverDeps['onNodeSettled']>;
  /**
   * 用例依赖**惰性**读取：组合根在 hook 装配之后才建 useCaseDeps，而该依赖只在
   * turn/end 的异步边界被取用（与原闭包直引 useCaseDeps 的时序语义逐字等价）。
   */
  useCaseDeps: () => UseCaseDeps;
  /**
   * 任务队列端口（REQ-260927202051-f6df）：驱动注入「当前任务」需从队列取（v9 台账已无 tasks）。
   * 直接传**实例**（非 `useCaseDeps()`——那个 getter 约定只在异步边界调用，而本函数是构造期）。
   */
  taskStore: TaskStore;
  logger: {
    info: (m: string) => void;
    debug: (m: string) => void;
    warn: (m: string, err?: unknown) => void;
  };
  plugin: string;
  /**
   * 会话事件订阅的**持有者**（Dive 服务）：driver 只提供处理函数，订阅生命周期归 Dive。
   * 为什么不让装配函数直接 ctx.on：用户裁定"CaptureHook 废弃、能力归 Dive"——
   * 谁拥有会话事件这件事要在调用方看得见，而不是藏在装配函数里。
   */
  attachSessionDriver: (handler: (session: unknown, event: unknown) => void) => (() => void) | undefined;
  /**
   * **驱动点**订阅的持有人（Dive 服务）：`agent/status` —— 整 agent 空闲（idle）时跑批。
   * 对齐 `@deepseek-ai/dsh-goal-round-driver`（lib/index.js:213 用 agent/status 作唯一驱动点，
   * session/event 只做簿记）。谁拥有这条订阅要在调用方看得见，不藏在装配函数里。
   */
  attachAgentStatus: (handler: (agent: unknown, status: unknown) => void) => (() => void) | undefined;
  /**
   * round 半句柄（REQ-260926215013-1568 T-5）：idle 拍定序 + session/event 回合簿记经它。
   * 缺省 = 纯采集/簿记（与改动前逐字一致，向后兼容）。
   */
  round?: DiveRoundDriver;
  /**
   * **FR-14 受信人工门弹框端口**（design I-10）：**只在有弹框通道处装配**——组合根须同时具备
   * ① `userQuestions` 服务（`UseCaseDeps.questions.available()`）与 ② 一条活窗口的 agent
   * 句柄（`questions.ask` 的 `agent` 参数）才注入。参考实现 =
   * `application/dive/gate-prompt.ts` 的 `createGatePromptPort`（由调用方按需组装）。
   * **缺省 = Dive 行为与 FR-14 之前逐字一致**（不弹框、不留痕、零新投递）。
   */
  gatePrompt?: GatePromptPort;
}

/**
 * ── Dive 会话驱动器（用户裁定 #2/#3；原 CaptureHook，2026-09-26 迁入 application/dive）─────────────────────────────
 * **采集点对齐 DSH Goal round driver**（用户裁定 2026-09-26）：两路订阅，各司其职。
 *   · session/event（采集/簿记）：user/message 落证据缓冲 + 本回合直接人类消息；
 *     tool/call 落工具痕迹；turn/end 做闸门链 Phase B 与断点补写。
 *   · agent/status === idle（**驱动点**）：整 agent 空闲时跑批——unbound 窗口登记
 *     「待捕获消息」到 pendingCapture（下一回合 capture section 取词组装时注入针对性立项
 *     提示）、bound 窗口做接手推进 / 阶段纪律注入 / 节点结算 / 里程碑催办。
 * 立项判定与内容仍留给 LLM + 人工（reqboard_capture 三问弹框作答 = 确认，同一次调用内直接建 REQ）。
 *
 * 返回解除两路订阅的合并函数（两路都没成立时 undefined），由调用方登记进 disposers。
 */
export function assembleDiveSessionDriver(deps: DiveDriverAssemblyDeps): (() => void) | undefined {
  const { pendingCapture, toolTrace, recentUserMsgs } = deps.runtime;
  const driverDeps: DiveSessionDriverDeps = {
    snapshot: () => deps.store.snapshot(),
    // 任务队列端口（REQ-260927202051-f6df）：v9 台账已无 tasks，注入「当前任务」需从队列取。
    // 直接传实例（**不**走 `useCaseDeps()`——那个 getter 约定只在异步边界调用，此处是构造期）。
    taskStore: deps.taskStore,
    pending: pendingCapture,
    now: deps.now,
    address: deps.address,
    // R1 接手推进：已绑定窗口出现直接人类消息 = 该窗口仍在推进其需求 → 其 draft 需求
    // 自动进评审（人工闸门仍在：方案确认/拆分确认/验收均为人工，代码级不可越过）。
    onBoundWindowActivity: (windowKey) => {
      const drafts = draftRequirementsFor(deps.store.snapshot(), windowKey);
      if (drafts.length === 0) return;
      void deps.store.mutate('requirement-moved', (ledger) => {
        // FR-6：接手推进属派生推进，带写时快照提供者（显式窗口码优先，退回 req.sourceSessionId，
        // 都无 → 诚实不写，不伪造）。windowKey 即本窗口（onBoundWindowActivity 的参数）。
        const snapshot = snapshotProviderFor(deps.useCaseDeps(), windowKey);
        const advanced = drafts
          .map((d) => applyPickupAdvance(ledger, d.id, { now: deps.now(), commentId: () => newCommentId(), snapshot }))
          .filter((r): r is RequirementRecord => r !== undefined);
        return advanced.length > 0 ? { requirements: advanced } : undefined;
      }).catch((err) => deps.logger.warn('reqboard rollup (pickup advance) failed:', err));
    },
    // ── 投递白名单（REQ-260927100007-b8ba FR-11）────────────────────────────────────
    // 通用 plugin 投递路径 `deliverer.deliver()`（→ agent.followup，**会新起一轮 agent loop**）
    // 只允许"人点头后的收尾/交接/唤醒"三项：
    //   1. pending-confirm wake（application/internal/pending-confirm.ts）
    //   2. 闸门链 H4 resume（application/gate/handlers/h4-resume.ts）
    //   3. 失败告警 FailureAlert（adapters/FailureAlert.ts）
    //   4. FR-14 人工门弹框的**降级**投递（gate-prompt.ts：弹框通道不可用时保留"提醒 agent"）
    //      —— 仅当组合根注入了 gatePrompt 才可能出现；采集半的零投递纪律不受影响。
    // 其余一切"进会话"的投递必须走 round 半的 `createRoundMessage`（source.kind='dive'，带
    // armed+active / 预留 / 准入计数 / 内容不变量）。据此：
    //   · **阶段纪律**不再投递——它本就在每次请求的 system prompt（capture-section.ts），
    //     旧的 onStagePrompt 投递是纯冗余且会额外起轮（FR-11 实测根因），故不再提供该 dep；
    //   · **里程碑催办**只在此登记——armed+active 转 round 半 queueReminder，其余只写 comment。
    onMilestoneNotice: (input) => {
      const req = deps.store.snapshot().requirements.find((r) => r.id === input.requirementId)
      if (req === undefined) {
        deps.logger.warn(`reqboard milestone notice 无法登记：需求不存在（${input.requirementId}）`)
        return
      }
      if (isDrivableRequirement(req)) {
        if (deps.round === undefined) {
          // 未接线不得静默丢（armed+active 的催办必须经 round 半投递）。
          deps.logger.warn(
            `reqboard milestone notice 未投递：round 半未装配（需求=${input.requirementId}，产物=${input.artifactKey}）`,
          )
          return
        }
        deps.round.queueReminder(input.requirementId, input.text)
        return
      }
      // 非 armed+active（全仓现状：0 个需求开过 armed）：只写台账 comment，绝不投递会话——
      // 留下"催办到期"与可用的下一步，不静默。
      void deps.store.mutate('dive-milestone-comment', (ledger) => {
        const r = ledger.requirements.find((x) => x.id === input.requirementId)
        if (r === undefined) return undefined
        r.comments.push({
          id: newCommentId(),
          body: '[里程碑催办] ' + input.text
            + ' 当前需求未 armed+active（dive.activation=' + (r.dive?.activation ?? 'undefined')
            + '，phase=' + (r.dive?.phase ?? 'undefined') + '）→ 本轮不投递会话。'
            + '下一步：人工调 reqboard_ask_confirm 弹框请人确认，或需求 armed 后由 round 半投递。',
          createdAt: deps.now(),
          createdBy: { kind: 'system' },
        })
        r.version += 1
        r.updatedAt = deps.now()
        return { requirements: [r] }
      }).catch((err) => deps.logger.warn('reqboard milestone comment 写失败：', err))
    },
    toolTrace,
    recentUserMsgs,
    injectionLog: deps.injectionLog,
    // REQ-422af1 t10：节点结算信号 → 隔离分发（开关关时 dispatcher 一次都不执行）。
    onNodeSettled: deps.onNodeSettled,
    // REQ-e3b6a0 t7：**闸门后置链 Phase B 的唯一时机**。闸门作答不一定伴随用户消息，
    // 故不能只靠 onNodeSettled；且监听器内不得做会话写操作（D-17）→ 放到异步边界。
    // （链按 (windowKey, gate, decidedAt) 幂等，与结算路径重复触发也只跑一轮。）
    onTurnEnd: (windowKey, session) => {
      setImmediate(() => {
        void deps.gateChain.runPending(windowKey, session).catch((err) => {
          deps.logger.warn('reqboard gate-chain run failed:', err);
        });
      });
    },
    // REQ-260924213231-b1c4 T-9（FR-6 写入器 B）：回合异常收尾（aborted/error/interrupted）
    // → 用异常原因**补新**断点。同样只发信号，写台账放到异步边界（D-17：监听器内禁会话写；
    // 这里虽只写本地台账，但保持与闸门链一致的时序纪律，不阻塞事件循环）。
    // noteInterruptionForWindow 永不抛、窗口无绑定需求即静默跳过（事件路径不打扰流水线）。
    onTurnFinished: (windowKey, outcome) => {
      if (!outcome.abnormal) return;
      setImmediate(() => {
        void noteInterruptionForWindow(deps.useCaseDeps(), windowKey, outcome.reason, 'turn/end').catch((err) => {
          deps.logger.warn('reqboard interruption note failed:', err);
        });
      });
    },
    // FR-14：弹框到上限 → 写台账 comment（响亮，不静默；此后停手不再重弹）。
    onGatePromptExhausted: (info) => {
      void deps.store.mutate('dive-gate-prompt-exhausted', (ledger) => {
        const r = ledger.requirements.find((x) => x.id === info.requirementId);
        if (r === undefined) return undefined;
        r.comments.push({
          id: newCommentId(),
          body: gatePromptExhaustedComment(info),
          createdAt: deps.now(),
          createdBy: { kind: 'system' },
        });
        r.version += 1;
        r.updatedAt = deps.now();
        return { requirements: [r] };
      }).catch((err) => deps.logger.warn('reqboard gate-prompt exhausted comment 写失败：', err));
    },
    logger: { info: (m) => deps.logger.info(m), debug: (m) => deps.logger.debug(m) },
    ...(deps.round !== undefined ? { round: deps.round } : {}),
    // FR-14：受信人工门弹框端口**按注入装配**（缺省 = 零行为，见 DiveDriverAssemblyDeps.gatePrompt）。
    ...(deps.gatePrompt !== undefined ? { gatePrompt: deps.gatePrompt } : {}),
  };
  const driver = createDiveSessionDriver(driverDeps);
  // Dive 服务持有两路订阅（driver 只提供处理函数）——"谁拥有会话事件与驱动点"归 Dive，
  // 不藏在装配函数里。采集（session/event）与驱动（agent/status idle）各一路。
  const unsubscribeSessionEvents = deps.attachSessionDriver((session, event) => driver(session, event));
  const unsubscribeAgentStatus = deps.attachAgentStatus((agent, status) => driver.onAgentStatus(agent, status));
  const attached = unsubscribeSessionEvents !== undefined || unsubscribeAgentStatus !== undefined;
  // 【诊断日志-节点1】Hook 订阅状态（文件双写，防 stdout 死管道）
  captureDiag(
    `reqboard-capture [NODE-1]: Hook subscription session/event=${unsubscribeSessionEvents ? 'SUCCESS' : 'FAILED'} agent/status=${unsubscribeAgentStatus ? 'SUCCESS' : 'FAILED'}`,
  );
  deps.logger.info(
    `reqboard-capture [NODE-1]: Hook subscription session/event=${unsubscribeSessionEvents ? 'SUCCESS' : 'FAILED'} agent/status=${unsubscribeAgentStatus ? 'SUCCESS' : 'FAILED'}`,
  );
  deps.logger.info('reqboard dive session driver registered: session/event 采集 + agent/status(idle) 驱动');
  // 【失败要响亮】两路订阅是整套事件驱动的总开关：采集路挂不上 = 证据缓冲/工具痕迹断源；
  // 驱动路挂不上 = 立项登记 / 接手推进 / 阶段纪律注入 / 节点结算 / 里程碑催办全静默停摆。
  // 此前只有一行 info 级 FAILED（可选链 + 不抛）——界面看起来一切正常，没人会知道。
  if (!attached) {
    deps.logger.warn(
      'reqboard dive session driver 订阅未成立（session/event 与 agent/status 均无监听）：'
      + '立项引导、待立项登记、阶段纪律注入、节点结算、里程碑催办、闸门链 Phase B、断点补写全部不会发生——'
      + '请检查宿主是否提供 ctx.on，或 attachSessionDriver / attachAgentStatus 端口是否装配。',
    );
  } else if (unsubscribeSessionEvents === undefined || unsubscribeAgentStatus === undefined) {
    deps.logger.warn(
      `reqboard dive session driver 仅装配了一路订阅（session/event=${unsubscribeSessionEvents ? 'ok' : 'MISSING'}, `
      + `agent/status=${unsubscribeAgentStatus ? 'ok' : 'MISSING'}）：缺驱动路则采集到的人类消息永不驱动，`
      + '缺采集路则证据缓冲/工具痕迹断源——请检查 attachSessionDriver / attachAgentStatus 端口。',
    );
  }
  if (!attached) return undefined;
  return () => {
    unsubscribeSessionEvents?.();
    unsubscribeAgentStatus?.();
  };
}
