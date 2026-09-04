//#region src/client/index.d.ts
declare const name = "@pi-investment/dashboard-holdings/client";
/** Service names this client module requires on ctx (official slot idiom). */
declare const inject: string[];
/** Minimal view of the slots service this module consumes (official shape). */
interface SlotsService {
  /** Queue a registration until the target slot exists (sidebar foot seat). */
  inject(slot: string, thunk: () => unknown): unknown;
  /** Register one occupant (React component) into a declared slot seat. */
  register(options: Record<string, unknown>, occupant: unknown): unknown;
}
interface ApplyContext {
  slots?: SlotsService;
}
/** Window-scoped apply guard so HMR re-apply tears down before re-mounting. */
declare global {
  interface Window {
    __dshHldClient?: {
      dispose(): void;
    };
  }
}
/** Client apply hook — never throws; a throw here fails the whole boot. */
declare function apply(ctx: ApplyContext): void;
//#endregion
export { apply, inject, name };
//# sourceMappingURL=client.d.cts.map