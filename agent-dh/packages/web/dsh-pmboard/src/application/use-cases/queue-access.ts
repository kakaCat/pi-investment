/**
 * 用例层的任务队列入口（REQ-260927202051-f6df t9 / FR-1, FR-2, FR-3）。
 *
 * 为什么需要它：台账 schema v9 起 `LedgerView` / `ReqboardLedger` / `LedgerChange` **不再有
 * `tasks`**（刻意不留，见 ports.ts:32 注释）——任务唯一事实源是 `TaskStore`。用例层有 53 处
 * 历史读点，若各自写 `deps.taskStore!`，装配缺失就会变成隐式 `undefined` 崩溃（栈里看不到原因）。
 * 这里把"取 store"收敛成单一入口：缺端口**当场响亮抛错**，不静默返回空数组（空数组会让看板
 * 静默空白——正是本需求要根治的最坏结果）。
 *
 * ⚠️ 契约现状（D11 同构问题，已报 Lead）：`UseCaseDeps.taskStore` 在 ports.ts 里仍是**可选**
 * （ports.ts 属 queue-core 写域，本卡不得改）。按 D11「可选字段 + 运行期抛错 = 把装配漏洞从
 * 编译期挪到运行期」的口径，它应改必填——届时本文件可用 `deps.taskStore` 直取，调用点零改动。
 *
 * @module dsh-pmboard/application/use-cases/queue-access
 */
import type { TaskRecord } from '../../shared/protocol.js'
import type { TaskStore, UseCaseDeps } from '../ports.js'

/** 取任务队列端口；未装配即抛（不静默降级为空任务集）。 */
export function taskStoreOf(deps: UseCaseDeps): TaskStore {
  const store = deps.taskStore
  if (store === undefined) {
    throw Object.assign(
      new Error('任务队列端口未装配（deps.taskStore 缺失）：用例无法读取任务，请检查组合根装配（REQ-260927202051-f6df）'),
      { code: 'REQBOARD_STORE_INCONSISTENT' },
    )
  }
  return store
}

/**
 * 就绪任务口径（UC-2 / TC-9.2）：日志与父卡取数共用同一个筛选，避免两处漂移。
 *
 * 语义与 `domain/queue/topology.computeReady` 对齐但不依赖队列文件视图：
 * 「自身 todo 且依赖全部 done（已取消视为已了结）」。
 */
export function readyTasksOf(tasks: readonly TaskRecord[]): TaskRecord[] {
  const byId = new Map(tasks.map((t) => [t.id, t]))
  return tasks.filter((t) => {
    if (t.status !== 'todo') return false
    return (t.dependsOn ?? []).every((dep) => {
      const d = byId.get(dep)
      return d === undefined || d.status === 'done' || d.status === 'canceled'
    })
  })
}
