/**
 * Dashboard-execution client half — the board's GUI face.
 *
 * Mirrors the dsh-taskboard dual-half contract: package.json declares
 * dsh.client + exports["./client"]; the DSH web shell's client-modules host
 * composes a boot-graph entry for this package, serves the wrapped bundle at
 * /plugins/??@pi-investment/dashboard-execution/client.js&rev=…, and the
 * shell runs this module in the browser. Exports mirror the taskboard
 * client-entry shape: name / inject / apply.
 *
 * Board data needs NO service injection — it fetches the same-origin
 * (auth-free) JSON endpoint /dashboard/api/board the host half exposes, so
 * inject is empty.
 *
 * @module dashboard-execution/client
 */
import { injectStyles } from './styles.ts'
import { createBoardController, mountBoard } from './board-mount.ts'
import { mountSidebarEntry } from './sidebar-entry.ts'

export const name = '@pi-investment/dashboard-execution/client'
export const inject: string[] = []

/** Client apply hook — never throws; registers a disposer via ctx.effect. */
export function apply(ctx: { get?(name: string): unknown; effect?(fn: () => unknown, label?: string): void }): void {
  try {
    injectStyles()
    const controller = createBoardController()
    const disposers: Array<() => void> = []
    try {
      disposers.push(mountSidebarEntry(controller))
      disposers.push(mountBoard(controller))
    } catch (e) {
      console.error('[dashboard-execution] mount failed:', e)
    }
    // cordis effect semantics（taskboard 同款）：回调立即执行，返回值即 disposer
    ctx.effect?.(() => () => {
      for (const d of disposers.splice(0)) { try { d() } catch { /* ignore */ } }
    }, 'dashboard-execution: client mount')
  } catch (e) {
    console.error('[dashboard-execution] client half failed to start:', e)
  }
}
