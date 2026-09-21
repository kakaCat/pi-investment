//#region src/client/index.d.ts
declare const name = "@pi-investment/web-liveness/client";
declare const inject: string[];
declare global {
  interface Window {
    /** HMR / 重复 apply 的清理句柄（各插件惯例：__dshXxxClient）。 */
    __dshWlvClient?: {
      dispose(): void;
    };
  }
}
declare function apply(ctx: {
  logger?: (name: string) => {
    info(msg: string): void;
    warn(msg: string): void;
  };
}): void;
//#endregion
export { apply, inject, name };
//# sourceMappingURL=client.d.cts.map