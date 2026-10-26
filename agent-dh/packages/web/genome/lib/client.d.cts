//#region src/client/index.d.ts
declare const name = "@pi-investment/dashboard-genome/client";
/** 顶部侧栏入口行 + 右栏 tab：需要官方右栏服务与 slot 注册表。 */
declare const inject: string[];
interface ApplyContext {
  sidebarRight?: unknown;
  sidebarRightTabs?: unknown;
  slots?: unknown;
  effect?: (fn: () => unknown, label?: string) => unknown;
}
declare function apply(ctx: ApplyContext): void;
//#endregion
export { apply, inject, name };
//# sourceMappingURL=client.d.cts.map