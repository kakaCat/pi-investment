//#region src/client/index.d.ts
declare const name = "@pi-investment/dashboard-execution/client";
/** Service names this client module requires on ctx (official slot idiom). */
declare const inject: string[];
/** Minimal view of the slots service this module consumes (official shape). */
interface SlotsService {
  /** Queue a registration until the target slot exists (sidebar foot seat). */
  inject(slot: string, thunk: () => unknown): unknown;
  /** Register one occupant (React component) into a declared slot seat. */
  register(options: Record<string, unknown>, occupant: unknown): unknown;
}
/** sessions 服务的极简投影（宽容读取，缺字段即降级；boot 提供失败也不阻断看板只读） */
interface SessionsFacade {
  list?: {
    getSnapshot?(): {
      items?: Array<{
        id?: string;
        sessionId?: string;
        displayTitle?: string;
        title?: string;
        running?: boolean;
        blank?: boolean;
        origin?: string;
      }>;
      current?: string;
    };
  };
}
interface ApplyContext {
  slots?: SlotsService;
  /** 「我来解决」会话候选（与左栏同源；board-mount 点击时经 __dshExecSessions 懒读） */
  sessions?: SessionsFacade;
  /** workspace 控制器（归档会话集合 archivedSessionIds 来源） */
  workspaces?: {
    list?: {
      getSnapshot?: () => {
        archivedSessionIds?: string[];
      };
    };
  };
}
/** Window-scoped apply guard so HMR re-apply tears down before re-mounting. */
declare global {
  interface Window {
    __dshExecClient?: {
      dispose(): void;
    };
    /** 「我来解决」会话源（与左栏同源；board-mount 点开时懒读） */
    __dshExecSessions?: SessionsFacade;
    /** apply 时的 client ctx（sessions 若未注入完成，点开时经它惰性重取） */
    __dshExecCtx?: {
      sessions?: SessionsFacade;
      workspaces?: unknown;
    };
    /** workspaces 服务快照（归档集合，会话候选过滤用） */
    __dshExecWorkspaces?: {
      list?: {
        getSnapshot?: () => {
          archivedSessionIds?: string[];
        };
      };
    };
  }
}
/** Client apply hook — never throws; a throw here fails the whole boot. */
declare function apply(ctx: ApplyContext): void;
//#endregion
export { SessionsFacade, apply, inject, name };
//# sourceMappingURL=client.d.cts.map