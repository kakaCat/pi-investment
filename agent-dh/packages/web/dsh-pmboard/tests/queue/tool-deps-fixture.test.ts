/**
 * `tests/helpers/tool-deps.ts` 装配口径契约测试（REQ-260927202051-f6df task-17 / Lead 裁决）。
 *
 * 这个夹具是 **30 个测试文件**的公共入口，且每个测试会拿**同一个 `deps` 对象**分别喂给多个
 * 工具工厂（`definePlanSubmitTool(deps)` / `defineDecomposeTool(deps)` / `defineVerifySubmitTool(deps)`…）。
 * 因此有两条必须钉死的不变量：
 *
 * 1. **同一 `deps` → 同一 `TaskStore`**（WeakMap 记忆化）。不记忆化就会出现
 *    "工具读 A store、断言读 B store"的**假红**——看起来像真 bug，根因在夹具。
 * 2. **`toUseCaseDeps` 真的把那个 store 装进 `deps.taskStore`**（不是另建一个）。
 *
 * 另：显式注入优先（测试想用自己的 store / 文件底座时不被覆盖）。
 */

import { describe, expect, it } from 'vitest'
import { taskStoreOf, toUseCaseDeps, type ReqboardToolDeps } from '../helpers/tool-deps.js'
import { QueueTaskStore } from '../../src/repositories/QueueTaskStore.js'
import { JsonLedgerRepository } from '../../src/adapters/JsonLedgerRepository.js'
import { tmpdir } from 'node:os'
import { join } from 'node:path'

function deps(over: Partial<ReqboardToolDeps> = {}): ReqboardToolDeps {
  return {
    store: new JsonLedgerRepository({ file: join(tmpdir(), `pmboard-tool-deps-${Math.random().toString(36).slice(2)}.json`) }),
    now: () => 1_000_000,
    ...over,
  }
}

describe('tool-deps 装配口径（task-17）', () => {
  it('同一 deps 对象两次取 store：**同一实例**（弱表记忆化，防"工具读 A 断言读 B"假红）', () => {
    const d = deps()

    const a = taskStoreOf(d)
    const b = taskStoreOf(d)

    expect(a).toBe(b)
    expect(a).toBeInstanceOf(QueueTaskStore)
  })

  it('不同 deps 对象 → 不同 store（每测试一份队列，不跨测试串档）', () => {
    const d1 = deps()
    const d2 = deps()

    expect(taskStoreOf(d1)).not.toBe(taskStoreOf(d2))
  })

  it('多个工具工厂共用一个 deps：装配出的 store 恒为同一实例', () => {
    const d = deps()

    // 模拟现有测试的用法：同一 deps 分喂多个工厂 → 每次都过 toUseCaseDeps
    const u1 = toUseCaseDeps(d)
    const u2 = toUseCaseDeps(d)

    expect(u1.taskStore).toBe(taskStoreOf(d))
    expect(u2.taskStore).toBe(taskStoreOf(d))
    expect(u1.taskStore).toBe(u2.taskStore)
  })

  it('显式注入的 taskStore 优先（不会被自动装配覆盖）', () => {
    const injected = new QueueTaskStore({
      repo: new (class { async load() { return undefined } async save() { /* noop */ } pathOf() { return '' } relativePathOf() { return '' } workspaceRoot() { return '/' } async listRequirementIds() { return [] } })() as never,
      now: () => 0,
    })
    const d = deps({ taskStore: injected })

    expect(taskStoreOf(d)).toBe(injected)
    expect(toUseCaseDeps(d).taskStore).toBe(injected)
  })
})
