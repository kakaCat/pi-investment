/**
 * 路由/工具壳测试的 **v9 装配助手**（REQ-260927202051-f6df task-19）。
 *
 * ## 为什么需要它
 *
 * v9 把任务从台账搬到队列后，`TaskStore` 成为**必需端口**：工具壳/路由在缺它时按端口语义
 * **显式失败**（`任务队列端口未装配` / 路由抛错 → HTTP 500）。一批测试文件仍在用
 * `createReqboardHandler({ store, now })` 这种"台账世界"的 deps 字面量，于是整片红。
 *
 * 这些红的根因是**同一套装配口径**。与其让每个文件各写一遍（必然出现"有人补真 store、
 * 有人补 mock、有人忘补"），不如收敛成这一处：**用真实 `QueueTaskStore`**（生产实现，
 * 底座 = 真实 `JsonQueueRepository` 落临时目录），**不造 mock 端口**。
 *
 * 需要 harness 那套内存底座时用 `makeHarness`（`tests/application/harness.ts`）；
 * 这里服务的是**自建 deps 字面量**（直接 `createReqboardHandler({...})` / `const deps = {...}`）
 * 的文件——它们已有自己的临时工作区根，只需补一句 `taskStore`。
 *
 * @module dsh-pmboard/tests/queue/route-deps
 */
import { JsonQueueRepository } from '../../src/repositories/QueueRepository.js'
import { QueueTaskStore } from '../../src/repositories/QueueTaskStore.js'

/**
 * 以 `root`（测试的临时工作区根）为队列落点的**真实** TaskStore。
 *
 * 队列文件落点 = `<root>/docs/requirements/<REQ>/queue.json`，与 `FileDocRepository({ workspaceRoot: root })`
 * 的文档根同源——这样"文档根"与"队列根"不会分家（分家会造成"用例建了文档、路由找不到队列"的假红）。
 *
 * @param root 临时工作区根（测试里通常是 `mkdtempSync(...)` 出来的那个变量）
 * @param now  时钟（缺省 `Date.now`；需要确定性时间戳时注入）
 */
export function taskStoreAt(root: string, now: () => number = () => Date.now()): QueueTaskStore {
  return new QueueTaskStore({ repo: new JsonQueueRepository({ workspaceRoot: root }), now })
}
