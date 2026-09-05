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
}
declare global {
  interface Window {
    __dshBbdClient?: {
      dispose(): void;
    };
    /** 认领/转交用的会话源（与左栏同源；mount 层点击时懒读） */
    __dshBbdSessions?: SessionsFacade;
  }
}
declare function apply(ctx: ApplyContext): void;
//#endregion
export { SessionsFacade, apply, inject, name };
//# sourceMappingURL=client.d.cts.map