//#region src/client/index.d.ts
declare const name = "@pi-investment/dashboard-holdings/client";
/** No shell services needed — the top sidebar row is plain DOM (taskboard idiom). */
declare const inject: string[];
/** Window-scoped apply guard so HMR re-apply tears down before re-mounting. */
declare global {
  interface Window {
    __dshHldClient?: {
      dispose(): void;
    };
  }
}
/** Client apply hook — never throws; a throw here fails the whole boot. */
declare function apply(): void;
//#endregion
export { apply, inject, name };
//# sourceMappingURL=client.d.cts.map