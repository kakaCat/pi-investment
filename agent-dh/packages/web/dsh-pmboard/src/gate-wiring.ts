/**
 * 闸门后置链与捕获引导段的装配辅助（REQ-f0579a t5：index.ts 超 400 行尺寸门禁，抽出两个装配块）。
 * 注释随代码搬（硬约束：不重写、不删"为什么/事故出处"型注释）；本文件是组合根的延伸，
 * 依赖方向与 index.ts 相同（adapters + application 均可引用）。
 */
import type { Context } from '@deepseek-ai/cordis';
import { createGatePostChain } from './application/gate/GatePostChain.js';
import { createPendingGateStore } from './application/gate/PendingGate.js';
import { createH1AdvanceHandler } from './application/gate/handlers/h1-advance.js';
import { createH2CompactHandler } from './application/gate/handlers/h2-compact.js';
import { createH3InjectHandler } from './application/gate/handlers/h3-inject.js';
import { createH4ResumeHandler } from './application/gate/handlers/h4-resume.js';
import { createH5AuditHandler } from './application/gate/handlers/h5-audit.js';
import { NodeIsolationAdapter } from './adapters/NodeIsolationAdapter.js';
import { RandomIdFactory } from './adapters/RandomIdFactory.js';
import type { JsonLedgerRepository } from './adapters/JsonLedgerRepository.js';
import type { FileDocRepository } from './adapters/FileDocRepository.js';
import type { IsolationTraceFile } from './adapters/IsolationTraceFile.js';
import type { InjectionLogFile } from './adapters/InjectionLogFile.js';
import type { SystemClock } from './adapters/SystemClock.js';
import type { AgentDeliverer } from './adapters/AgentDeliverer.js';
import { captureSectionText, boundSectionText } from './application/internal/capture-section.js';
import { windowKeyFromContext } from './application/internal/window.js';
import { captureDiag } from './application/internal/diag-log.js';

export interface GateChainDeps {
  store: JsonLedgerRepository;
  docs: FileDocRepository;
  clock: SystemClock;
  now: () => number;
  isolationTrace: IsolationTraceFile;
  injectionLog: InjectionLogFile;
  deliverer: AgentDeliverer;
  logger: { info: (m: string) => void; warn: (m: string, err?: unknown) => void };
  plugin: string;
  /** H2 压缩开关（= 节点隔离开关求值结果，调用侧单点求值后传入）。 */
  compactionEnabled: boolean;
  /** 模板地址注入（REQ-260922213356-4a45 T-3）：绝对模板根 + 开关；缺省不注入。 */
  address?: { templateRoot?: string; enabled: boolean };
  /** 轮次边界判定（注入 projections 探测结果；判不出时调用侧已保守返回 false）。 */
  idle: (session: unknown) => boolean;
}

/** 装配闸门后置链（REQ-e3b6a0）：Phase A 由装饰器登记，Phase B 在 turn/end 的异步边界执行。 */
export function assembleGatePostChain(deps: GateChainDeps): ReturnType<typeof createGatePostChain> {
  // D1：链默认开；压缩（H2）由 NODE_ISOLATION 独立控制且默认关（高风险动作分两步上）。
  const gateIds = new RandomIdFactory();
  const gateChain = createGatePostChain({
    enabled: true,
    pending: createPendingGateStore(),
    handlers: [
      createH1AdvanceHandler({ repo: deps.store }),
      createH2CompactHandler({
        repo: deps.store,
        docs: deps.docs,
        clock: deps.clock,
        compactionEnabled: deps.compactionEnabled,
        isolationFor: (session) => new NodeIsolationAdapter(session, {
          idle: () => deps.idle(session),
          plugin: deps.plugin,
        }),
        trace: deps.isolationTrace,
      }),
      createH3InjectHandler({
        repo: deps.store,
        injectionLog: deps.injectionLog,
        ...(deps.address === undefined ? {} : { templateRoot: deps.address.templateRoot, addressSectionEnabled: deps.address.enabled }),
      }),
      createH4ResumeHandler({ delivery: deps.deliverer, plugin: deps.plugin }),
      createH5AuditHandler({ repo: deps.store, now: deps.now, newCommentId: () => gateIds.comment() }),
    ],
    warn: (message) => deps.logger.warn(message),
  });
  deps.logger.info(
    'reqboard 闸门后置链已装配（H1 校验 → H2 压缩 → H3 注入 → H4 唤醒 → H5 审计）；'
    + '压缩开关 NODE_ISOLATION=' + String(deps.compactionEnabled),
  );
  return gateChain;
}

export interface CaptureGuidanceDeps {
  disposers: Array<() => void>;
  store: JsonLedgerRepository;
  pendingCapture: Map<string, { windowKey: string; text: string; capturedAt: number }>;
  injectionLog: InjectionLogFile;
  logger: { info: (m: string) => void };
  plugin: string;
  /** 模板地址注入（T-3）：绝对模板根 + 开关；缺省不注入。 */
  address?: { templateRoot?: string; enabled: boolean };
  /** 捕获引导段名（systemPrompt 全局唯一）与放置序位（identity 5 / genome 10-40 之后）。 */
  sectionName: string;
  sectionOrder: number;
  /** systemPrompt 服务就绪回调（调用侧存起供 tokenSnapshot/路由使用）。 */
  onSystemPrompt: (svc: unknown) => void;
}

/**
 * 捕获引导段（B：按窗口条件注入）：为每个 agent 窗口的 systemPrompt 组装求值，
 * 仅 unbound 的窗口返回引导文本，其余返回 ''（renderPrompt
 * 滤空段 → 零噪音）。text 为函数式：每次组装读取 store.snapshot()（同步）判定当前窗口状态。
 */
export function registerCaptureGuidance(ctx: Context, deps: CaptureGuidanceDeps): void {
  ;(ctx as unknown as { inject?: (services: string[], cb: (c: any) => void) => void }).inject?.(
    ['systemPrompt'],
    (spCtx: { effect?: (fn: () => void, label?: string) => void; systemPrompt?: any }) => {
      deps.onSystemPrompt(spCtx.systemPrompt);
      spCtx.effect?.(() => {
        deps.disposers.push(spCtx.systemPrompt.section({
          name: deps.sectionName,
          order: deps.sectionOrder,
          text: (assembleContext: unknown) => {
            // 命中「本窗口待捕获消息」（hook 登记、turn/end 前）→ 注入针对性立项提示；
            // 否则维持静态引导（bound/有遗留 pending 时两者都返回 ''，零噪音）。
            const windowKey = windowKeyFromContext(
              assembleContext as { agent?: { id?: unknown }; scope?: unknown } | undefined,
            );
            const pending = windowKey ? deps.pendingCapture.get(windowKey) : undefined;
            // 【诊断日志-节点4】systemPrompt 组装时的 windowKey 提取与 pending 查询（文件双写，防 stdout 死管道）
            captureDiag(`reqboard-capture [NODE-4]: systemPrompt assemble (windowKey=${windowKey ? windowKey.slice(0, 16) : 'undefined'}, pending=${pending !== undefined ? 'EXISTS' : 'NONE'}, pendingCapture.size=${deps.pendingCapture.size})`);
            const sectionText = captureSectionText(deps.store.snapshot(), assembleContext, pending);
            if (sectionText.length > 0) return sectionText;
            // 已绑定窗口：注入「推进纪律」（状态由窗口自己维护，不必等人点按钮）
            return boundSectionText(deps.store.snapshot(), assembleContext, deps.injectionLog, deps.address);
          },
        }));
      }, deps.plugin + ': capture');
      deps.logger.info('capture guidance section registered (unbound windows only, per-window eval)');
    },
  );
}
