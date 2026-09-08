//#region src/client/index.d.ts
declare const name = "dsh-pmboard/client";
declare const inject: string[];
interface SlotsService {
  inject(slot: string, thunk: () => unknown): unknown;
  register(options: Record<string, unknown>, occupant: unknown): unknown;
}
interface ApplyContext {
  slots?: SlotsService;
  sessions?: unknown;
  workspaces?: unknown;
}
declare global {
  interface Window {
    __dshReqboardClient?: {
      dispose(): void;
    };
    __dshPmSessions?: unknown;
    __dshPmWorkspaces?: unknown;
    __dshPmCtx?: ApplyContext;
  }
}
declare function apply(ctx: ApplyContext): void;
//#endregion
export { apply, inject, name };
//# sourceMappingURL=client.d.cts.map