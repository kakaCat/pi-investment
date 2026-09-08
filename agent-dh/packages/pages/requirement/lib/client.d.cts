//#region src/client/index.d.ts
declare const name = "@pi-investment/dashboard-requirement/client";
declare const inject: string[];
interface SlotsService {
  inject(slot: string, thunk: () => unknown): unknown;
  register(options: Record<string, unknown>, occupant: unknown): unknown;
}
interface ApplyContext {
  slots?: SlotsService;
}
declare global {
  interface Window {
    __dshReqboardClient?: {
      dispose(): void;
    };
  }
}
declare function apply(ctx: ApplyContext): void;
//#endregion
export { apply, inject, name };
//# sourceMappingURL=client.d.cts.map