//#region src/client/index.d.ts
declare const name = "@pi-investment/dashboard-bulletin/client";
declare const inject: string[];
declare global {
  interface Window {
    __dshBbdClient?: {
      dispose(): void;
    };
  }
}
declare function apply(): void;
//#endregion
export { apply, inject, name };
//# sourceMappingURL=client.d.cts.map