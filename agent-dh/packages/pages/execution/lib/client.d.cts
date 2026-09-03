//#region src/client/index.d.ts
declare const name = "@pi-investment/dashboard-execution/client";
declare const inject: string[];
/** Client apply hook — never throws; registers a disposer via ctx.effect. */
declare function apply(ctx: {
  get?(name: string): unknown;
  effect?(fn: () => unknown, label?: string): void;
}): void;
//#endregion
export { apply, inject, name };
//# sourceMappingURL=client.d.cts.map