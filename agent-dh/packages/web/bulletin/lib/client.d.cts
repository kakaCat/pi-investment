//#region src/client/index.d.ts
declare const name = "@pi-investment/dashboard-bulletin/client";
declare const inject: string[];
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
      }>;
      current?: string;
    };
  };
}
interface ApplyContext {
  sessions?: SessionsFacade;
  /** workspace 控制器（归档集合 archivedSessionIds 来源） */
  workspaces?: {
    list?: {
      getSnapshot?: () => {
        archivedSessionIds?: string[];
      };
    };
  };
}
declare global {
  interface Window {
    __dshBbdClient?: {
      dispose(): void;
    };
    /** 认领/转交用的会话源（与左栏同源；mount 层点击时懒读） */
    __dshBbdSessions?: SessionsFacade;
    /** apply 时的 client ctx（sessions 若未注入完成，点开转交时经它惰性重取） */
    __dshBbdCtx?: {
      sessions?: SessionsFacade;
      workspaces?: unknown;
    };
    /** workspaces 服务快照（归档集合，转交候选过滤用） */
    __dshBbdWorkspaces?: {
      list?: {
        getSnapshot?: () => {
          archivedSessionIds?: string[];
        };
      };
    };
  }
}
declare function apply(ctx: ApplyContext): void;
//#endregion
export { SessionsFacade, apply, inject, name };
//# sourceMappingURL=client.d.cts.map