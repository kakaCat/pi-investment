//#region src/client/index.d.ts
declare const name = "@pi-investment/dashboard-holdings/client";
/**
 * Shell services: sessions/workspaces feed the solve-kit window picker
 * session candidates (2026-09-08); slots mirrors the taskboard entry idiom
 * kept by sibling pages. Board body itself stays plain DOM.
 */
declare const inject: string[];
/** apply 收到的 client ctx 极简投影（宽容读取，缺字段即降级） */
type ApplyContext = {
  slots?: unknown;
  sessions?: unknown;
  workspaces?: unknown;
};
/** Window-scoped apply guard so HMR re-apply tears down before re-mounting. */
declare global {
  interface Window {
    __dshHldClient?: {
      dispose(): void;
    };
    __dshHldCtx?: {
      sessions?: unknown;
      workspaces?: unknown;
    };
    __dshHldSessions?: unknown;
    __dshHldWorkspaces?: {
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
export { apply, inject, name };
//# sourceMappingURL=client.d.cts.map