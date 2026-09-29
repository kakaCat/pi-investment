# REQ-260927202051-f6df 验收文档

> 自动生成于 reqboard_submit(kind=verification) · 验收单 v1

**交付结论**：DAG 任务队列机制（REQ-260927202051-f6df）已交付并投产。① 投产：台账 v8→v9 已于 22:55 在停机窗口执行（自动备份+manifest），51 份 queue.json / 616 条任务、台账 tasks 字段移除、schemaVersion=9；读方（看板/路由/执行工具/用例层/门禁/Dive）全部改读队列。② 实测：投产后的实例上真实打开页面 15/15 ×3 轮（重启前/重启后/测试阶段独立复跑），联调契约 34~36/36，定向回归套 23 files / 223 tests 全绿（EXIT=0），端到端 t17 Exited 0，启动日志 LEDGER_REQUIRES_MIGRATION=0。③ t-e77b06 链 4 张子卡逐张 ok 并自动滚进验收（advance-log 可复核），流程零卡死。④ 施工期自查修掉 3 处缺陷：陈旧 advance 锁无回收路径（曾阻塞续跑，run_status 报 jobStatus=not_found 却仍拒绝投递）、活台账 migrations 留痕被旧构建进程写丢（--verify 退出码 1）、ensureAgentHandle 新增第 5 参 tasks 后一条旧测试（属 D14）未适配（首跑 22 files/220 tests → 修复后 23/223 全绿；生产调用点 ExecuteTask 已正确传参，无线上缺陷）。⑤ 覆盖声明 29/29 任务卡（tests/test-evidence.md §7，TC-1~TC-18 逐条给命令）。整体验收标准 6/6 闭环，但其中两条属「判据文本」问题、需人工裁决：a) 卡内验收① 字面命令 curl /dashboard 命中 0 —— /dashboard 是客户端 hash 路由（服务端 404），等价口径 GET / → 200 且 pmboard=5；b) 标准#3「--verify 无差异、退出码 0」在活台账永不成立（补回留痕后问题 3→2 项，剩余 2 项全是迁移后运行期漂移），纯净副本口径下实测 exit 0。另：TC-10.2 字面要求「依赖连线」而甘特 SVG 无 edge 图元（依赖由任务表依赖列 + 需求详情 DAG 11 层承载，且 decomposition 明列「本轮不做队列 DAG 图形 UI」），建议改文本不改实现。全部证据与命令见 verification-evidence.md + verification-addendum.md。

## 1. 验收列表

### v1-1 · 定义队列类型与任务契约

**验收内容**：【定义队列类型与任务契约】验收：① 聚焦类型检查退出码 0：`npx tsc --noEmit` 作用于仅含本卡两文件的临时 tsconfig（`src/domain/queue/QueueTypes.ts` + `tests/queue-types.test.ts`），实测退出码 0；② 类型级断言编译通过且**故障注入有效**——故意断言一个不存在的字段时 `tsc` 报 TS2344「Type 'false' does not satisfy the constraint 'true'」退出码 2（证明断言非恒真）；③ 脚本/断言比对 `QueueTask` 键集 − `TaskRecord` 键集恰为 `{layer}`（类型级双向包含 + 运行时样本核对）；④ `grep -c '^export interface' src/domain/queue/QueueTypes.ts` 输出 6（≥5）；⑤ `grep -c "from '../../shared/protocol" src/domain/queue/QueueTypes.ts` 命中 1（≥1，复用 TaskRecord 未重定义）；⑥ `npx vitest run tests/queue-types.test.ts` 4/4 通过；⑦ **增量不恶化**：全仓 `npx tsc --noEmit` 错误数 ≤ 基线 164，且与 `domain/queue` / `queue-types` 相关的错误数为 0。※ 原验收①「全仓 tsc 退出码 0」已按增量口径修订——工作区基线因他人未提交重构存在 164 个错误，非本卡可控。

**操作步骤**：
1. ① 聚焦类型检查退出码 0：`npx tsc --noEmit` 作用于仅含本卡两文件的临时 tsconfig（`src/domain/queue/QueueTypes.ts` + `tests/queue-types.test.ts`），实测退出码 0
2. ② 类型级断言编译通过且**故障注入有效**——故意断言一个不存在的字段时 `tsc` 报 TS2344「Type 'false' does not satisfy the constraint 'true'」退出码 2（证明断言非恒真）
3. ③ 脚本/断言比对 `QueueTask` 键集 − `TaskRecord` 键集恰为 `{layer}`（类型级双向包含 + 运行时样本核对）
4. ④ `grep -c '^export interface' src/domain/queue/QueueTypes.ts` 输出 6（≥5）
5. ⑤ `grep -c "from '../../shared/protocol" src/domain/queue/QueueTypes.ts` 命中 1（≥1，复用 TaskRecord 未重定义）
6. ⑥ `npx vitest run tests/queue-types.test.ts` 4/4 通过
7. ⑦ **增量不恶化**：全仓 `npx tsc --noEmit` 错误数 ≤ 基线 164，且与 `domain/queue` / `queue-types` 相关的错误数为 0。※ 原验收①「全仓 tsc 退出码 0」已按增量口径修订——工作区基线因他人未提交重构存在 164 个错误，非本卡可控。

**预期结果**：按上述步骤执行后满足验收标准：① 聚焦类型检查退出码 0：`npx tsc --noEmit` 作用于仅含本卡两文件的临时 tsconfig（`src/domain/queue/QueueTypes.ts` + `tests/queue-types.test.ts`），实测退出码 0；② 类型级断言编译通过且**故障注入有效**——故意断言一个不存在的字段时 `tsc` 报 TS2344「Type 'false' does not satisfy the constraint 'true'」退出码 2（证明断言非恒真）；③ 脚本/断言比对 `QueueTask` 键集 − `TaskRecord` 键集恰为 `{layer}`（类型级双向包含 + 运行时样本核对）；④ `grep -c '^export interface' src/domain/queue/QueueTypes.ts` 输出 6（≥5）；⑤ `grep -c "from '../../shared/protocol" src/domain/queue/QueueTypes.ts` 命中 1（≥1，复用 TaskRecord 未重定义）；⑥ `npx vitest run tests/queue-types.test.ts` 4/4 通过；⑦ **增量不恶化**：全仓 `npx tsc --noEmit` 错误数 ≤ 基线 164，且与 `domain/queue` / `queue-types` 相关的错误数为 0。※ 原验收①「全仓 tsc 退出码 0」已按增量口径修订——工作区基线因他人未提交重构存在 164 个错误，非本卡可控。

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

### v1-2 · 实现 DAG 拓扑分层与派生视图

**验收内容**：【实现 DAG 拓扑分层与派生视图】验收：① npx vitest run tests/queue/topology.test.ts 全绿（TC-1.1~TC-1.7）；② 菱形 t1→{t2,t3}→t4 断言 layers 等于 [[t1],[t2,t3],[t4]] 且 ready 等于 ['t1']；③ 环输入断言抛错且 message 包含 CIRCULAR；④ 空输入断言返回空三件套且未抛错；⑤ grep -c "node:fs" src/domain/queue/topology.ts 输出 0（纯函数）。※ 原验收①路径 src/domain/queue/topology.test.ts 不可执行（本仓 vitest.config.ts 的 include 为 tests/**/*.test.ts），按开工实测修订为 tests/queue/topology.test.ts，未改 vitest 配置。

**操作步骤**：
1. ① npx vitest run tests/queue/topology.test.ts 全绿（TC-1.1~TC-1.7）
2. ② 菱形 t1→{t2,t3}→t4 断言 layers 等于 [[t1],[t2,t3],[t4]] 且 ready 等于 ['t1']
3. ③ 环输入断言抛错且 message 包含 CIRCULAR
4. ④ 空输入断言返回空三件套且未抛错
5. ⑤ grep -c "node:fs" src/domain/queue/topology.ts 输出 0（纯函数）。※ 原验收①路径 src/domain/queue/topology.test.ts 不可执行（本仓 vitest.config.ts 的 include 为 tests/**/*.test.ts），按开工实测修订为 tests/queue/topology.test.ts，未改 vitest 配置。

**预期结果**：按上述步骤执行后满足验收标准：① npx vitest run tests/queue/topology.test.ts 全绿（TC-1.1~TC-1.7）；② 菱形 t1→{t2,t3}→t4 断言 layers 等于 [[t1],[t2,t3],[t4]] 且 ready 等于 ['t1']；③ 环输入断言抛错且 message 包含 CIRCULAR；④ 空输入断言返回空三件套且未抛错；⑤ grep -c "node:fs" src/domain/queue/topology.ts 输出 0（纯函数）。※ 原验收①路径 src/domain/queue/topology.test.ts 不可执行（本仓 vitest.config.ts 的 include 为 tests/**/*.test.ts），按开工实测修订为 tests/queue/topology.test.ts，未改 vitest 配置。

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

### v1-3 · 实现队列数据校验 V-1~V-6

**验收内容**：【实现队列数据校验 V-1~V-6】验收：① `npx vitest run src/domain/queue/validateQueue.test.ts` 全绿（TC-2.1~TC-2.11）；② 6 条规则各有反例触发，测试汇总输出 6/6 命中；③ 合法队列断言 passed 为 true 且 issues.length 等于 0；④ 全部失败用例断言 passed 为 false 且未 throw；⑤ `grep -c "topology" src/domain/queue/validateQueue.ts` 命中 ≥ 1（复用环检测，未复制）。

**操作步骤**：
1. ① `npx vitest run src/domain/queue/validateQueue.test.ts` 全绿（TC-2.1~TC-2.11）
2. ② 6 条规则各有反例触发，测试汇总输出 6/6 命中
3. ③ 合法队列断言 passed 为 true 且 issues.length 等于 0
4. ④ 全部失败用例断言 passed 为 false 且未 throw
5. ⑤ `grep -c "topology" src/domain/queue/validateQueue.ts` 命中 ≥ 1（复用环检测，未复制）。

**预期结果**：按上述步骤执行后满足验收标准：① `npx vitest run src/domain/queue/validateQueue.test.ts` 全绿（TC-2.1~TC-2.11）；② 6 条规则各有反例触发，测试汇总输出 6/6 命中；③ 合法队列断言 passed 为 true 且 issues.length 等于 0；④ 全部失败用例断言 passed 为 false 且未 throw；⑤ `grep -c "topology" src/domain/queue/validateQueue.ts` 命中 ≥ 1（复用环检测，未复制）。

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

### v1-4 · 实现队列仓储与原子写入

**验收内容**：【实现队列仓储与原子写入】验收：① `npx vitest run src/repositories/QueueRepository.test.ts` 全绿（TC-3.1~TC-3.6）；② save 后 `jq . <queue.json>` 退出码 0，且 `ls <dir> | grep -c tmp` 输出 0（无残留临时文件）；③ load 不存在的需求断言返回 undefined（非抛错）；④ 损坏 JSON 后断言目录下存在 `.corrupt-*` 隔离文件；⑤ 校验失败路径断言 queue.json 不存在；⑥ `grep -c "persistAtomic" src/repositories/QueueRepository.ts` 命中 ≥ 1（复用未自造）。

**操作步骤**：
1. ① `npx vitest run src/repositories/QueueRepository.test.ts` 全绿（TC-3.1~TC-3.6）
2. ② save 后 `jq . <queue.json>` 退出码 0，且 `ls <dir> | grep -c tmp` 输出 0（无残留临时文件）
3. ③ load 不存在的需求断言返回 undefined（非抛错）
4. ④ 损坏 JSON 后断言目录下存在 `.corrupt-*` 隔离文件
5. ⑤ 校验失败路径断言 queue.json 不存在
6. ⑥ `grep -c "persistAtomic" src/repositories/QueueRepository.ts` 命中 ≥ 1（复用未自造）。

**预期结果**：按上述步骤执行后满足验收标准：① `npx vitest run src/repositories/QueueRepository.test.ts` 全绿（TC-3.1~TC-3.6）；② save 后 `jq . <queue.json>` 退出码 0，且 `ls <dir> | grep -c tmp` 输出 0（无残留临时文件）；③ load 不存在的需求断言返回 undefined（非抛错）；④ 损坏 JSON 后断言目录下存在 `.corrupt-*` 隔离文件；⑤ 校验失败路径断言 queue.json 不存在；⑥ `grep -c "persistAtomic" src/repositories/QueueRepository.ts` 命中 ≥ 1（复用未自造）。

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

### v1-5 · 实现 TaskStore 端口与队列实现

**验收内容**：【实现 TaskStore 端口与队列实现】验收：① `npx vitest run src/repositories/QueueTaskStore.test.ts` 全绿（TC-4.1~TC-4.8）；② createMany 5 任务后断言队列 tasks.length 等于 5 且每条 layer 已算；③ 重复 id 断言被幂等跳过（原有字段不变）；④ mutate 改 done 后断言 ready 包含下游 id 且 updated_at 已变；⑤ 无队列需求 mutate 断言拒绝并抛 QUEUE_NOT_FOUND；⑥ 写后 get 返回新值（缓存已失效）。

**操作步骤**：
1. ① `npx vitest run src/repositories/QueueTaskStore.test.ts` 全绿（TC-4.1~TC-4.8）
2. ② createMany 5 任务后断言队列 tasks.length 等于 5 且每条 layer 已算
3. ③ 重复 id 断言被幂等跳过（原有字段不变）
4. ④ mutate 改 done 后断言 ready 包含下游 id 且 updated_at 已变
5. ⑤ 无队列需求 mutate 断言拒绝并抛 QUEUE_NOT_FOUND
6. ⑥ 写后 get 返回新值（缓存已失效）。

**预期结果**：按上述步骤执行后满足验收标准：① `npx vitest run src/repositories/QueueTaskStore.test.ts` 全绿（TC-4.1~TC-4.8）；② createMany 5 任务后断言队列 tasks.length 等于 5 且每条 layer 已算；③ 重复 id 断言被幂等跳过（原有字段不变）；④ mutate 改 done 后断言 ready 包含下游 id 且 updated_at 已变；⑤ 无队列需求 mutate 断言拒绝并抛 QUEUE_NOT_FOUND；⑥ 写后 get 返回新值（缓存已失效）。

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

### v1-6 · 台账 schema v9：移除 tasks

**验收内容**：【台账 schema v9：移除 tasks】验收：① 台账相关测试全绿（TC-5.1~TC-5.6）；② `emptyLedger()` 无 `tasks` 键且 `schemaVersion===9`；③ 加载 v8 台账（含 tasks）抛 `LEDGER_REQUIRES_MIGRATION` 且**未静默丢弃任务**（TC-5.3）；④ **落盘 JSON 无顶层 `tasks` 键**，判据为 `node -e "console.log('tasks' in require('<ledger>'))"` 输出 `false`（或 `jq 'has("tasks")'` 输出 `false`）—— ※ 原判据 `grep -c '"tasks"' <ledger>` **不可用且会假绿**：实测台账是单行 compact JSON（`wc -l` = 0/`wc -c` = 7,891,940），且 `requirements[].plan.tasks` 是真实嵌套字段（59 个需求有此键），故该 grep 迁移前后都 = 1；而 `grep '^  "tasks"'` 因无缩进两种状态都 = 0（假绿）；⑤ `LedgerChange` 无 `tasks` 字段（编译期断言）。

**操作步骤**：
1. ① 台账相关测试全绿（TC-5.1~TC-5.6）
2. ② `emptyLedger()` 无 `tasks` 键且 `schemaVersion===9`
3. ③ 加载 v8 台账（含 tasks）抛 `LEDGER_REQUIRES_MIGRATION` 且**未静默丢弃任务**（TC-5.3）
4. ④ **落盘 JSON 无顶层 `tasks` 键**，判据为 `node -e "console.log('tasks' in require('<ledger>'))"` 输出 `false`（或 `jq 'has("tasks")'` 输出 `false`）—— ※ 原判据 `grep -c '"tasks"' <ledger>` **不可用且会假绿**：实测台账是单行 compact JSON（`wc -l` = 0/`wc -c` = 7,891,940），且 `requirements[].plan.tasks` 是真实嵌套字段（59 个需求有此键），故该 grep 迁移前后都 = 1
5. 而 `grep '^  "tasks"'` 因无缩进两种状态都 = 0（假绿）
6. ⑤ `LedgerChange` 无 `tasks` 字段（编译期断言）。

**预期结果**：按上述步骤执行后满足验收标准：① 台账相关测试全绿（TC-5.1~TC-5.6）；② `emptyLedger()` 无 `tasks` 键且 `schemaVersion===9`；③ 加载 v8 台账（含 tasks）抛 `LEDGER_REQUIRES_MIGRATION` 且**未静默丢弃任务**（TC-5.3）；④ **落盘 JSON 无顶层 `tasks` 键**，判据为 `node -e "console.log('tasks' in require('<ledger>'))"` 输出 `false`（或 `jq 'has("tasks")'` 输出 `false`）—— ※ 原判据 `grep -c '"tasks"' <ledger>` **不可用且会假绿**：实测台账是单行 compact JSON（`wc -l` = 0/`wc -c` = 7,891,940），且 `requirements[].plan.tasks` 是真实嵌套字段（59 个需求有此键），故该 grep 迁移前后都 = 1；而 `grep '^  "tasks"'` 因无缩进两种状态都 = 0（假绿）；⑤ `LedgerChange` 无 `tasks` 字段（编译期断言）。

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

### v1-7 · 读方改造 A：看板与 HTTP 路由

**验收内容**：【读方改造 A：看板与 HTTP 路由】验收：① 四路由改经 taskStore（grep 无 ledger.tasks / snapshot().tasks）；② **等价性判据（D8 分层，取代"整个响应逐字节相等"）**：a) 任务级逐字节——按 id 配对断言 `JSON.stringify` 相等、键集相等，且**不含 `layer` 键**（D3）；b) 需求内顺序——`listByRequirement(r)` 的 id 序列 === 迁移前 `ledger.tasks.filter(t=>t.requirementId===r)` 的 id 序列（51 个含任务需求逐一）；c) 计数——`/state` 任务总数与每需求条数均等于**源台账现算值**（不写死数字）；d) 响应其余字段（requirements / verdicts / byWindow 等）仍逐字节相等；e) **明确不要求**跨需求全局数组顺序——实测不可复现（2 个需求的任务在全局数组中被切断、612 条仅 106 个不同 createdAt 且非严格递增、(createdAt,id) 排序无法还原原序）；③ stages 返回任务数 = 队列内任务数；④ `src/http/routes.ts` 的 mintId 与 `RouterCtx` 注入必须同批改（不同批编不过）；⑤ `handleEvents` 订阅切到 `taskStore.subscribe`（仍订阅台账会让看板实时刷新静默失灵）；⑥ 异步改造后无未 await 的 Promise（类型检查）；⑦ 证据须为**迁移前 /state 快照 vs 迁移后 /state 快照**的真实前后对照，禁止只断言 HTTP 200。

※ 验收②原口径「迁移前后相同请求返回 JSON 逐字节相等（TC-8.1~TC-8.4）」在实测中不可达成：跨需求全局数组顺序在按需求分片后**结构上不可能复现**，且无消费方依赖（看板按需求分组渲染）。按 D8 改为 a~e 五条可证伪断言，回归面不缩小——真正判据是 t16 看板实测。

**操作步骤**：
1. ① 四路由改经 taskStore（grep 无 ledger.tasks / snapshot().tasks）
2. ② **等价性判据（D8 分层，取代"整个响应逐字节相等"）**：a) 任务级逐字节——按 id 配对断言 `JSON.stringify` 相等、键集相等，且**不含 `layer` 键**（D3）
3. b) 需求内顺序——`listByRequirement(r)` 的 id 序列 === 迁移前 `ledger.tasks.filter(t=>t.requirementId===r)` 的 id 序列（51 个含任务需求逐一）
4. c) 计数——`/state` 任务总数与每需求条数均等于**源台账现算值**（不写死数字）
5. d) 响应其余字段（requirements / verdicts / byWindow 等）仍逐字节相等
6. e) **明确不要求**跨需求全局数组顺序——实测不可复现（2 个需求的任务在全局数组中被切断、612 条仅 106 个不同 createdAt 且非严格递增、(createdAt,id) 排序无法还原原序）
7. ③ stages 返回任务数 = 队列内任务数
8. ④ `src/http/routes.ts` 的 mintId 与 `RouterCtx` 注入必须同批改（不同批编不过）
9. ⑤ `handleEvents` 订阅切到 `taskStore.subscribe`（仍订阅台账会让看板实时刷新静默失灵）
10. ⑥ 异步改造后无未 await 的 Promise（类型检查）
11. ⑦ 证据须为**迁移前 /state 快照 vs 迁移后 /state 快照**的真实前后对照，禁止只断言 HTTP 200。
12. ※ 验收②原口径「迁移前后相同请求返回 JSON 逐字节相等（TC-8.1~TC-8.4）」在实测中不可达成：跨需求全局数组顺序在按需求分片后**结构上不可能复现**，且无消费方依赖（看板按需求分组渲染）。按 D8 改为 a~e 五条可证伪断言，回归面不缩小——真正判据是 t16 看板实测。

**预期结果**：按上述步骤执行后满足验收标准：① 四路由改经 taskStore（grep 无 ledger.tasks / snapshot().tasks）；② **等价性判据（D8 分层，取代"整个响应逐字节相等"）**：a) 任务级逐字节——按 id 配对断言 `JSON.stringify` 相等、键集相等，且**不含 `layer` 键**（D3）；b) 需求内顺序——`listByRequirement(r)` 的 id 序列 === 迁移前 `ledger.tasks.filter(t=>t.requirementId===r)` 的 id 序列（51 个含任务需求逐一）；c) 计数——`/state` 任务总数与每需求条数均等于**源台账现算值**（不写死数字）；d) 响应其余字段（requirements / verdicts / byWindow 等）仍逐字节相等；e) **明确不要求**跨需求全局数组顺序——实测不可复现（2 个需求的任务在全局数组中被切断、612 条仅 106 个不同 createdAt 且非严格递增、(createdAt,id) 排序无法还原原序）；③ stages 返回任务数 = 队列内任务数；④ `src/http/routes.ts` 的 mintId 与 `RouterCtx` 注入必须同批改（不同批编不过）；⑤ `handleEvents` 订阅切到 `taskStore.subscribe`（仍订阅台账会让看板实时刷新静默失灵）；⑥ 异步改造后无未 await 的 Promise（类型检查）；⑦ 证据须为**迁移前 /state 快照 vs 迁移后 /state 快照**的真实前后对照，禁止只断言 HTTP 200。

※ 验收②原口径「迁移前后相同请求返回 JSON 逐字节相等（TC-8.1~TC-8.4）」在实测中不可达成：跨需求全局数组顺序在按需求分片后**结构上不可能复现**，且无消费方依赖（看板按需求分组渲染）。按 D8 改为 a~e 五条可证伪断言，回归面不缩小——真正判据是 t16 看板实测。

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

### v1-8 · 读方改造 B：执行工具

**验收内容**：【读方改造 B：执行工具】验收：① 四工具改经 taskStore（grep 无 ledger.tasks / snapshot().tasks）；② **等价性判据（D8 分层，同 t-66797c）**：a) 按 id 配对断言任务字段 `JSON.stringify` 逐字节相等、键集相等且不含 `layer`；b) 需求内顺序一致；c) 计数等于源台账现算值；d) **明确不要求**跨需求全局数组顺序（实测不可复现）；③ `TaskReportTool` 写回落到队列且 `lastReport` 已写；④ `AdvanceTool` 的 ready 选择结果与迁移前一致（按需求内 ready 集合比对，不比对全局顺序）；⑤ 证据须为迁移前 vs 迁移后的真实输出对照，禁止只断言 200。

**操作步骤**：
1. ① 四工具改经 taskStore（grep 无 ledger.tasks / snapshot().tasks）
2. ② **等价性判据（D8 分层，同 t-66797c）**：a) 按 id 配对断言任务字段 `JSON.stringify` 逐字节相等、键集相等且不含 `layer`
3. b) 需求内顺序一致
4. c) 计数等于源台账现算值
5. d) **明确不要求**跨需求全局数组顺序（实测不可复现）
6. ③ `TaskReportTool` 写回落到队列且 `lastReport` 已写
7. ④ `AdvanceTool` 的 ready 选择结果与迁移前一致（按需求内 ready 集合比对，不比对全局顺序）
8. ⑤ 证据须为迁移前 vs 迁移后的真实输出对照，禁止只断言 200。

**预期结果**：按上述步骤执行后满足验收标准：① 四工具改经 taskStore（grep 无 ledger.tasks / snapshot().tasks）；② **等价性判据（D8 分层，同 t-66797c）**：a) 按 id 配对断言任务字段 `JSON.stringify` 逐字节相等、键集相等且不含 `layer`；b) 需求内顺序一致；c) 计数等于源台账现算值；d) **明确不要求**跨需求全局数组顺序（实测不可复现）；③ `TaskReportTool` 写回落到队列且 `lastReport` 已写；④ `AdvanceTool` 的 ready 选择结果与迁移前一致（按需求内 ready 集合比对，不比对全局顺序）；⑤ 证据须为迁移前 vs 迁移后的真实输出对照，禁止只断言 200。

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

### v1-9 · 读方改造 C：用例层

**验收内容**：【读方改造 C：用例层】验收：① `npx vitest run src/application/use-cases/` 全绿；② TaskTree 父子结构断言一致（TC-8.10）；③ MoveTask 打点断言 taskStore.mutate 先于 repo.mutate（TC-8.11）；④ rollup 推导结果断言一致（TC-8.8）；⑤ `npx tsc --noEmit` 退出码 0。

**操作步骤**：
1. ① `npx vitest run src/application/use-cases/` 全绿
2. ② TaskTree 父子结构断言一致（TC-8.10）
3. ③ MoveTask 打点断言 taskStore.mutate 先于 repo.mutate（TC-8.11）
4. ④ rollup 推导结果断言一致（TC-8.8）
5. ⑤ `npx tsc --noEmit` 退出码 0。

**预期结果**：按上述步骤执行后满足验收标准：① `npx vitest run src/application/use-cases/` 全绿；② TaskTree 父子结构断言一致（TC-8.10）；③ MoveTask 打点断言 taskStore.mutate 先于 repo.mutate（TC-8.11）；④ rollup 推导结果断言一致（TC-8.8）；⑤ `npx tsc --noEmit` 退出码 0。

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

### v1-10 · 读方改造 D：门禁、查询与 Dive

**验收内容**：【读方改造 D：门禁、查询与 Dive】验收：① `npx vitest run src/application/internal/` 全绿；② RTM/覆盖门禁读到的任务键集断言一致（TC-8.9）；③ 全仓残留静态检查：`grep -rn 'ledger\.tasks\|snapshot()\.tasks\|changed\.tasks' src/` 命中数为 0（TC-8.12）；④ `npx tsc --noEmit` 退出码 0。

**操作步骤**：
1. ① `npx vitest run src/application/internal/` 全绿
2. ② RTM/覆盖门禁读到的任务键集断言一致（TC-8.9）
3. ③ 全仓残留静态检查：`grep -rn 'ledger\.tasks\|snapshot()\.tasks\|changed\.tasks' src/` 命中数为 0（TC-8.12）
4. ④ `npx tsc --noEmit` 退出码 0。

**预期结果**：按上述步骤执行后满足验收标准：① `npx vitest run src/application/internal/` 全绿；② RTM/覆盖门禁读到的任务键集断言一致（TC-8.9）；③ 全仓残留静态检查：`grep -rn 'ledger\.tasks\|snapshot()\.tasks\|changed\.tasks' src/` 命中数为 0（TC-8.12）；④ `npx tsc --noEmit` 退出码 0。

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

### v1-11 · 接线 Decompose：任务写入队列

**验收内容**：【接线 Decompose：任务写入队列】验收：① `npx vitest run src/application/use-cases/Decompose.test.ts` 全绿；② 拆分后 `ls docs/requirements/<REQ>/queue.json` 文件存在且 `jq .` 退出码 0；③ 返回体断言 queue_file 为非空字符串；④ 台账中 `grep -c '"tasks"' <ledger>` 输出 0（未新增任务）；⑤ 重复调用后断言文件 mtime 不变（幂等）。

**操作步骤**：
1. ① `npx vitest run src/application/use-cases/Decompose.test.ts` 全绿
2. ② 拆分后 `ls docs/requirements/<REQ>/queue.json` 文件存在且 `jq .` 退出码 0
3. ③ 返回体断言 queue_file 为非空字符串
4. ④ 台账中 `grep -c '"tasks"' <ledger>` 输出 0（未新增任务）
5. ⑤ 重复调用后断言文件 mtime 不变（幂等）。

**预期结果**：按上述步骤执行后满足验收标准：① `npx vitest run src/application/use-cases/Decompose.test.ts` 全绿；② 拆分后 `ls docs/requirements/<REQ>/queue.json` 文件存在且 `jq .` 退出码 0；③ 返回体断言 queue_file 为非空字符串；④ 台账中 `grep -c '"tasks"' <ledger>` 输出 0（未新增任务）；⑤ 重复调用后断言文件 mtime 不变（幂等）。

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

### v1-12 · 接线 ExecuteTask/MoveTask：读队列与顺序契约

**验收内容**：【接线 ExecuteTask/MoveTask：读队列与顺序契约】验收：① `npx vitest run src/application/use-cases/MoveTask.test.ts` 全绿；② task_run 日志断言包含 `Queue ready tasks:` 且父卡字段取自队列（TC-9.2）；③ `reqboard_task_move(to=done)` 后 `jq -e '.ready|index("<下游id>")' <queue.json>` 命中（TC-9.3）；④ 打点断言 taskStore.mutate 先于 repo.mutate（TC-8.11）；⑤ task_run 前后 `md5 <queue.json>` 输出不变（只读）；⑥ 删除队列后 task_move 仍返回 success（TC-9.4）。

**操作步骤**：
1. ① `npx vitest run src/application/use-cases/MoveTask.test.ts` 全绿
2. ② task_run 日志断言包含 `Queue ready tasks:` 且父卡字段取自队列（TC-9.2）
3. ③ `reqboard_task_move(to=done)` 后 `jq -e '.ready|index("<下游id>")' <queue.json>` 命中（TC-9.3）
4. ④ 打点断言 taskStore.mutate 先于 repo.mutate（TC-8.11）
5. ⑤ task_run 前后 `md5 <queue.json>` 输出不变（只读）
6. ⑥ 删除队列后 task_move 仍返回 success（TC-9.4）。

**预期结果**：按上述步骤执行后满足验收标准：① `npx vitest run src/application/use-cases/MoveTask.test.ts` 全绿；② task_run 日志断言包含 `Queue ready tasks:` 且父卡字段取自队列（TC-9.2）；③ `reqboard_task_move(to=done)` 后 `jq -e '.ready|index("<下游id>")' <queue.json>` 命中（TC-9.3）；④ 打点断言 taskStore.mutate 先于 repo.mutate（TC-8.11）；⑤ task_run 前后 `md5 <queue.json>` 输出不变（只读）；⑥ 删除队列后 task_move 仍返回 success（TC-9.4）。

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

### v1-13 · 实现 v8→v9 迁移变换与 CLI

**验收内容**：【实现 v8→v9 迁移变换与 CLI】验收：① `--dry-run` 台账 md5/mtime **不变**且无 queue.json 生成（TC-6.1/6.2）；② `--apply` 后台账 `schemaVersion===9`、**顶层无 `tasks` 键**（判据：`node -e "console.log('tasks' in require('<ledger>'))"` → `false`；※ 不用 `grep '"tasks"'`——台账为单行 compact JSON 且 `requirements[].plan.tasks` 真实存在，该 grep 迁移前后恒为 1）、`migrations` 末条 `{8,9}`（TC-6.3/6.4）；③ `--verify` 无差异退出码 0（TC-6.6）；④ `--rollback` 还原 v8 并清理本次生成的 queue.json（TC-6.8）；⑤ **顺序断言**：日志/打点证明先写全部 queue.json 再改台账（D-7 先于 D-8）；⑥ **无任务遗留**：迁移报告 `unmigrated` 必须为 0，且报告列出每一个未迁移项与原因；⑦ 迁移报告须含「源台账现算」的条数与数据时点（不写死数字）。

**操作步骤**：
1. ① `--dry-run` 台账 md5/mtime **不变**且无 queue.json 生成（TC-6.1/6.2）
2. ② `--apply` 后台账 `schemaVersion===9`、**顶层无 `tasks` 键**（判据：`node -e "console.log('tasks' in require('<ledger>'))"` → `false`
3. ※ 不用 `grep '"tasks"'`——台账为单行 compact JSON 且 `requirements[].plan.tasks` 真实存在，该 grep 迁移前后恒为 1）、`migrations` 末条 `{8,9}`（TC-6.3/6.4）
4. ③ `--verify` 无差异退出码 0（TC-6.6）
5. ④ `--rollback` 还原 v8 并清理本次生成的 queue.json（TC-6.8）
6. ⑤ **顺序断言**：日志/打点证明先写全部 queue.json 再改台账（D-7 先于 D-8）
7. ⑥ **无任务遗留**：迁移报告 `unmigrated` 必须为 0，且报告列出每一个未迁移项与原因
8. ⑦ 迁移报告须含「源台账现算」的条数与数据时点（不写死数字）。

**预期结果**：按上述步骤执行后满足验收标准：① `--dry-run` 台账 md5/mtime **不变**且无 queue.json 生成（TC-6.1/6.2）；② `--apply` 后台账 `schemaVersion===9`、**顶层无 `tasks` 键**（判据：`node -e "console.log('tasks' in require('<ledger>'))"` → `false`；※ 不用 `grep '"tasks"'`——台账为单行 compact JSON 且 `requirements[].plan.tasks` 真实存在，该 grep 迁移前后恒为 1）、`migrations` 末条 `{8,9}`（TC-6.3/6.4）；③ `--verify` 无差异退出码 0（TC-6.6）；④ `--rollback` 还原 v8 并清理本次生成的 queue.json（TC-6.8）；⑤ **顺序断言**：日志/打点证明先写全部 queue.json 再改台账（D-7 先于 D-8）；⑥ **无任务遗留**：迁移报告 `unmigrated` 必须为 0，且报告列出每一个未迁移项与原因；⑦ 迁移报告须含「源台账现算」的条数与数据时点（不写死数字）。

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

### v1-14 · 迁移安全：白名单、幂等与 orphan

**验收内容**：【迁移安全：白名单、幂等与 orphan】验收：① 注入白名单外字段改动后断言中止、`echo $?` 退出码 1、且台账 md5 与执行前一致（TC-6.7）；② 连续两次 `--apply`，第二次输出断言包含 `already_v9` 且所有文件 mtime 不变（TC-6.5）；③ orphan 任务计入报告且断言未被迁移（不串档，TC-6.9）；④ 环依赖需求中止迁移但其余需求 queue.json 照常生成，报告列出（TC-6.10）。

**操作步骤**：
1. ① 注入白名单外字段改动后断言中止、`echo $?` 退出码 1、且台账 md5 与执行前一致（TC-6.7）
2. ② 连续两次 `--apply`，第二次输出断言包含 `already_v9` 且所有文件 mtime 不变（TC-6.5）
3. ③ orphan 任务计入报告且断言未被迁移（不串档，TC-6.9）
4. ④ 环依赖需求中止迁移但其余需求 queue.json 照常生成，报告列出（TC-6.10）。

**预期结果**：按上述步骤执行后满足验收标准：① 注入白名单外字段改动后断言中止、`echo $?` 退出码 1、且台账 md5 与执行前一致（TC-6.7）；② 连续两次 `--apply`，第二次输出断言包含 `already_v9` 且所有文件 mtime 不变（TC-6.5）；③ orphan 任务计入报告且断言未被迁移（不串档，TC-6.9）；④ 环依赖需求中止迁移但其余需求 queue.json 照常生成，报告列出（TC-6.10）。

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

### v1-15 · 迁移契约比对：587 条零字段丢失

**验收内容**：【迁移契约比对：587 条零字段丢失】验收：① 逐字段深比对：`queue.tasks[i]` 去 `layer` 后与源 `ledger.tasks` 按 **id 配对** `deepEqual`（不是按下标）；② **键集相等**断言 —— 覆盖全部 18 个可选字段，含 `executorHint`/`cardDoc`/`requirementRefs`/`skipIntegration`/`blockedReason`/`claimedBy`/`claimedAt` 共 7 个原设计文档漏列字段（TC-7.2）；③ 全部 `dependsOn` 可解析（TC-7.3，条数**由源台账现算**，不写死）；④ 状态分布**迁移前后逐一相等**（分布由源台账现算）（TC-7.4）；⑤ 每份 queue.json 的 `requirement_id` 与所在目录一致（TC-7.5）；⑥ 覆盖计数、条数一律由源台账现算并注明数据时点与来源，**禁止任何硬编码计数**（裁决 D7）。

※ 测试文件路径修订：原定 `scripts/__tests__/migrate-contract.test.ts` 不被 vitest 收集（`vitest.config.ts` include = `tests/**/*.test.ts`，实测 "No test files found"），实施落在 `tests/migrate-contract.test.ts`，验收命令相应为 `npx vitest run tests/migrate-contract.test.ts`；未改 vitest 配置。

**操作步骤**：
1. ① 逐字段深比对：`queue.tasks[i]` 去 `layer` 后与源 `ledger.tasks` 按 **id 配对** `deepEqual`（不是按下标）
2. ② **键集相等**断言 —— 覆盖全部 18 个可选字段，含 `executorHint`/`cardDoc`/`requirementRefs`/`skipIntegration`/`blockedReason`/`claimedBy`/`claimedAt` 共 7 个原设计文档漏列字段（TC-7.2）
3. ③ 全部 `dependsOn` 可解析（TC-7.3，条数**由源台账现算**，不写死）
4. ④ 状态分布**迁移前后逐一相等**（分布由源台账现算）（TC-7.4）
5. ⑤ 每份 queue.json 的 `requirement_id` 与所在目录一致（TC-7.5）
6. ⑥ 覆盖计数、条数一律由源台账现算并注明数据时点与来源，**禁止任何硬编码计数**（裁决 D7）。
7. ※ 测试文件路径修订：原定 `scripts/__tests__/migrate-contract.test.ts` 不被 vitest 收集（`vitest.config.ts` include = `tests/**/*.test.ts`，实测 "No test files found"），实施落在 `tests/migrate-contract.test.ts`，验收命令相应为 `npx vitest run tests/migrate-contract.test.ts`
8. 未改 vitest 配置。

**预期结果**：按上述步骤执行后满足验收标准：① 逐字段深比对：`queue.tasks[i]` 去 `layer` 后与源 `ledger.tasks` 按 **id 配对** `deepEqual`（不是按下标）；② **键集相等**断言 —— 覆盖全部 18 个可选字段，含 `executorHint`/`cardDoc`/`requirementRefs`/`skipIntegration`/`blockedReason`/`claimedBy`/`claimedAt` 共 7 个原设计文档漏列字段（TC-7.2）；③ 全部 `dependsOn` 可解析（TC-7.3，条数**由源台账现算**，不写死）；④ 状态分布**迁移前后逐一相等**（分布由源台账现算）（TC-7.4）；⑤ 每份 queue.json 的 `requirement_id` 与所在目录一致（TC-7.5）；⑥ 覆盖计数、条数一律由源台账现算并注明数据时点与来源，**禁止任何硬编码计数**（裁决 D7）。

※ 测试文件路径修订：原定 `scripts/__tests__/migrate-contract.test.ts` 不被 vitest 收集（`vitest.config.ts` include = `tests/**/*.test.ts`，实测 "No test files found"），实施落在 `tests/migrate-contract.test.ts`，验收命令相应为 `npx vitest run tests/migrate-contract.test.ts`；未改 vitest 配置。

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

### v1-16 · 看板实测回归（真实打开页面）

**验收内容**：【看板实测回归（真实打开页面）】验收：① 启动 :13080 后 `curl -s localhost:13080/dashboard | grep -c pmboard` 命中 ≥ 1（页面可达）；② 真实打开任务页，历史与在制任务断言可见且数量与迁移后一致（TC-10.1）；③ 甘特/阶段视图断言正常渲染，无空白无 500（TC-10.2）；④ 需求详情任务列表断言非空且字段完整（TC-10.3）；⑤ 启动日志 `grep -c LEDGER_REQUIRES_MIGRATION` 输出 0 且无未捕获异常（TC-10.4）；⑥ 本需求自身任务断言可见（TC-10.5）；⑦ 留页面截图路径作证据，禁止以 curl 200 代替渲染验证。

**操作步骤**：
1. ① 启动 :13080 后 `curl -s localhost:13080/dashboard | grep -c pmboard` 命中 ≥ 1（页面可达）
2. ② 真实打开任务页，历史与在制任务断言可见且数量与迁移后一致（TC-10.1）
3. ③ 甘特/阶段视图断言正常渲染，无空白无 500（TC-10.2）
4. ④ 需求详情任务列表断言非空且字段完整（TC-10.3）
5. ⑤ 启动日志 `grep -c LEDGER_REQUIRES_MIGRATION` 输出 0 且无未捕获异常（TC-10.4）
6. ⑥ 本需求自身任务断言可见（TC-10.5）
7. ⑦ 留页面截图路径作证据，禁止以 curl 200 代替渲染验证。

**预期结果**：按上述步骤执行后满足验收标准：① 启动 :13080 后 `curl -s localhost:13080/dashboard | grep -c pmboard` 命中 ≥ 1（页面可达）；② 真实打开任务页，历史与在制任务断言可见且数量与迁移后一致（TC-10.1）；③ 甘特/阶段视图断言正常渲染，无空白无 500（TC-10.2）；④ 需求详情任务列表断言非空且字段完整（TC-10.3）；⑤ 启动日志 `grep -c LEDGER_REQUIRES_MIGRATION` 输出 0 且无未捕获异常（TC-10.4）；⑥ 本需求自身任务断言可见（TC-10.5）；⑦ 留页面截图路径作证据，禁止以 curl 200 代替渲染验证。

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

### v1-17 · 端到端验收与文档同步

**验收内容**：【端到端验收与文档同步】验收：① 端到端脚本退出码 0：`tests/t17-queue-e2e.test.ts`（单 `it` 一条真实连续链：新建需求 → 拆分 → 队列生成 → **台账零新增任务** → 推进 → 队列 ready 更新）② `pnpm build` 退出码 0 ③ `npx vitest run apps/web/tests/plugin-schema.smoke.test.ts` 通过 ④ 归档申报的 `manual_updates` 已实际写入（`project-manual.md`「最近更新」一行 + 「关键概念·任务队列（queue.json）」一条），且 **wiki_probe 死链数不新增**（实测 30，与改动前逐条一致；该 30 条为 `docs/README.md`→`packages/pages/*` 等**预存**陈旧路径，见交付证据 §八，**不属本需求范围**）⑤ 提交可复核证据清单（`verification-evidence.md` 十节）。

※ 验收④原口径「`wiki_probe.py` 死链 **0**」不可达成且非本需求所致：整库 30 条死链全部为预存（pages→web 重构后的陈旧路径、work-logs 指向已删文件），本需求新增文档**未新增任何死链**。按「新增 0」口径修订；整库归零需另立清理工作。

**操作步骤**：
1. ① 端到端脚本退出码 0：`tests/t17-queue-e2e.test.ts`（单 `it` 一条真实连续链：新建需求 → 拆分 → 队列生成 → **台账零新增任务** → 推进 → 队列 ready 更新）② `pnpm build` 退出码 0 ③ `npx vitest run apps/web/tests/plugin-schema.smoke.test.ts` 通过 ④ 归档申报的 `manual_updates` 已实际写入（`project-manual.md`「最近更新」一行 + 「关键概念·任务队列（queue.json）」一条），且 **wiki_probe 死链数不新增**（实测 30，与改动前逐条一致
2. 该 30 条为 `docs/README.md`→`packages/pages/*` 等**预存**陈旧路径，见交付证据 §八，**不属本需求范围**）⑤ 提交可复核证据清单（`verification-evidence.md` 十节）。
3. ※ 验收④原口径「`wiki_probe.py` 死链 **0**」不可达成且非本需求所致：整库 30 条死链全部为预存（pages→web 重构后的陈旧路径、work-logs 指向已删文件），本需求新增文档**未新增任何死链**。按「新增 0」口径修订
4. 整库归零需另立清理工作。

**预期结果**：按上述步骤执行后满足验收标准：① 端到端脚本退出码 0：`tests/t17-queue-e2e.test.ts`（单 `it` 一条真实连续链：新建需求 → 拆分 → 队列生成 → **台账零新增任务** → 推进 → 队列 ready 更新）② `pnpm build` 退出码 0 ③ `npx vitest run apps/web/tests/plugin-schema.smoke.test.ts` 通过 ④ 归档申报的 `manual_updates` 已实际写入（`project-manual.md`「最近更新」一行 + 「关键概念·任务队列（queue.json）」一条），且 **wiki_probe 死链数不新增**（实测 30，与改动前逐条一致；该 30 条为 `docs/README.md`→`packages/pages/*` 等**预存**陈旧路径，见交付证据 §八，**不属本需求范围**）⑤ 提交可复核证据清单（`verification-evidence.md` 十节）。

※ 验收④原口径「`wiki_probe.py` 死链 **0**」不可达成且非本需求所致：整库 30 条死链全部为预存（pages→web 重构后的陈旧路径、work-logs 指向已删文件），本需求新增文档**未新增任何死链**。按「新增 0」口径修订；整库归零需另立清理工作。

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

### v1-18 · 定义队列类型与任务契约·研发

**验收内容**：【定义队列类型与任务契约·研发】验收：落盘 QueueTypes 类型契约并可复核：① `cd packages/web/dsh-pmboard && npx tsc --noEmit` 对本卡改动文件无新增类型错误；② `npx vitest run tests/queue-types.test.ts` 退出码 0、用例全 passed；③ `git status --short` 列出本卡新增/改动文件。判据：命令退出码 0 且输出摘要贴进卡文档。

**操作步骤**：
1. 落盘 QueueTypes 类型契约并可复核：① `cd packages/web/dsh-pmboard && npx tsc --noEmit` 对本卡改动文件无新增类型错误
2. ② `npx vitest run tests/queue-types.test.ts` 退出码 0、用例全 passed
3. ③ `git status --short` 列出本卡新增/改动文件。判据：命令退出码 0 且输出摘要贴进卡文档。

**预期结果**：按上述步骤执行后满足验收标准：落盘 QueueTypes 类型契约并可复核：① `cd packages/web/dsh-pmboard && npx tsc --noEmit` 对本卡改动文件无新增类型错误；② `npx vitest run tests/queue-types.test.ts` 退出码 0、用例全 passed；③ `git status --short` 列出本卡新增/改动文件。判据：命令退出码 0 且输出摘要贴进卡文档。

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

### v1-19 · 定义队列类型与任务契约·联调

**验收内容**：【定义队列类型与任务契约·联调】验收：给出调用样例与期望一致性的可复核证据：`cd packages/web/dsh-pmboard && npx vitest run tests/queue-types-integration.test.ts` 退出码 0；用例须断言与既有真实接口（`src/shared/protocol.ts` 的 readyTasks）对接后的实际返回与期望一致，不得只造 mock。判据：命令退出码 0 + 贴输出摘要。

**操作步骤**：
1. 给出调用样例与期望一致性的可复核证据：`cd packages/web/dsh-pmboard && npx vitest run tests/queue-types-integration.test.ts` 退出码 0
2. 用例须断言与既有真实接口（`src/shared/protocol.ts` 的 readyTasks）对接后的实际返回与期望一致，不得只造 mock。判据：命令退出码 0 + 贴输出摘要。

**预期结果**：按上述步骤执行后满足验收标准：给出调用样例与期望一致性的可复核证据：`cd packages/web/dsh-pmboard && npx vitest run tests/queue-types-integration.test.ts` 退出码 0；用例须断言与既有真实接口（`src/shared/protocol.ts` 的 readyTasks）对接后的实际返回与期望一致，不得只造 mock。判据：命令退出码 0 + 贴输出摘要。

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

### v1-20 · 定义队列类型与任务契约·复核

**验收内容**：【定义队列类型与任务契约·复核】验收：对设计与实现的偏离逐条给出结论；无偏离时显式写明「无偏离」及依据

**操作步骤**：
1. 对设计与实现的偏离逐条给出结论
2. 无偏离时显式写明「无偏离」及依据

**预期结果**：按上述步骤执行后满足验收标准：对设计与实现的偏离逐条给出结论；无偏离时显式写明「无偏离」及依据

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

### v1-21 · 定义队列类型与任务契约·测试

**验收内容**：【定义队列类型与任务契约·测试】验收：目标命令全绿并贴原文：`cd packages/web/dsh-pmboard && npx vitest run tests/queue-types.test.ts tests/queue-types-integration.test.ts` → 退出码 0，Files/Tests 全 passed。判据：命令 + 结果摘要（断言数）贴进卡文档。

**操作步骤**：
1. 目标命令全绿并贴原文：`cd packages/web/dsh-pmboard && npx vitest run tests/queue-types.test.ts tests/queue-types-integration.test.ts` → 退出码 0，Files/Tests 全 passed。判据：命令 + 结果摘要（断言数）贴进卡文档。

**预期结果**：按上述步骤执行后满足验收标准：目标命令全绿并贴原文：`cd packages/web/dsh-pmboard && npx vitest run tests/queue-types.test.ts tests/queue-types-integration.test.ts` → 退出码 0，Files/Tests 全 passed。判据：命令 + 结果摘要（断言数）贴进卡文档。

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

### v1-22 · 实现 DAG 拓扑分层与派生视图·研发

**验收内容**：【实现 DAG 拓扑分层与派生视图·研发】验收：落盘拓扑分层实现并可复核：① `cd packages/web/dsh-pmboard && npx tsc --noEmit` 对本卡改动文件无新增类型错误；② `npx vitest run tests/queue/topology.test.ts` 退出码 0、用例全 passed（含畸形输入不抛错的回归用例）。判据：命令退出码 0 + 输出摘要贴进卡文档。

**操作步骤**：
1. 落盘拓扑分层实现并可复核：① `cd packages/web/dsh-pmboard && npx tsc --noEmit` 对本卡改动文件无新增类型错误
2. ② `npx vitest run tests/queue/topology.test.ts` 退出码 0、用例全 passed（含畸形输入不抛错的回归用例）。判据：命令退出码 0 + 输出摘要贴进卡文档。

**预期结果**：按上述步骤执行后满足验收标准：落盘拓扑分层实现并可复核：① `cd packages/web/dsh-pmboard && npx tsc --noEmit` 对本卡改动文件无新增类型错误；② `npx vitest run tests/queue/topology.test.ts` 退出码 0、用例全 passed（含畸形输入不抛错的回归用例）。判据：命令退出码 0 + 输出摘要贴进卡文档。

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

### v1-23 · 实现 DAG 拓扑分层与派生视图·联调

**验收内容**：【实现 DAG 拓扑分层与派生视图·联调】验收：给出与真实仓储联调的可复核证据：`cd packages/web/dsh-pmboard && npx vitest run tests/queue/topology-integration.test.ts` 退出码 0；用例须走真实 JsonQueueRepository 落盘再读回，不得只造 mock。判据：命令退出码 0 + 贴输出摘要。

**操作步骤**：
1. 给出与真实仓储联调的可复核证据：`cd packages/web/dsh-pmboard && npx vitest run tests/queue/topology-integration.test.ts` 退出码 0
2. 用例须走真实 JsonQueueRepository 落盘再读回，不得只造 mock。判据：命令退出码 0 + 贴输出摘要。

**预期结果**：按上述步骤执行后满足验收标准：给出与真实仓储联调的可复核证据：`cd packages/web/dsh-pmboard && npx vitest run tests/queue/topology-integration.test.ts` 退出码 0；用例须走真实 JsonQueueRepository 落盘再读回，不得只造 mock。判据：命令退出码 0 + 贴输出摘要。

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

### v1-24 · 实现 DAG 拓扑分层与派生视图·复核

**验收内容**：【实现 DAG 拓扑分层与派生视图·复核】验收：对设计与实现的偏离逐条给出结论；无偏离时显式写明「无偏离」及依据

**操作步骤**：
1. 对设计与实现的偏离逐条给出结论
2. 无偏离时显式写明「无偏离」及依据

**预期结果**：按上述步骤执行后满足验收标准：对设计与实现的偏离逐条给出结论；无偏离时显式写明「无偏离」及依据

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

### v1-25 · 实现 DAG 拓扑分层与派生视图·测试

**验收内容**：【实现 DAG 拓扑分层与派生视图·测试】验收：目标命令全绿并贴原文：`cd packages/web/dsh-pmboard && npx vitest run tests/queue/topology.test.ts tests/queue/topology-integration.test.ts` → 退出码 0，Files/Tests 全 passed。判据：命令 + 结果摘要（断言数）贴进卡文档。

**操作步骤**：
1. 目标命令全绿并贴原文：`cd packages/web/dsh-pmboard && npx vitest run tests/queue/topology.test.ts tests/queue/topology-integration.test.ts` → 退出码 0，Files/Tests 全 passed。判据：命令 + 结果摘要（断言数）贴进卡文档。

**预期结果**：按上述步骤执行后满足验收标准：目标命令全绿并贴原文：`cd packages/web/dsh-pmboard && npx vitest run tests/queue/topology.test.ts tests/queue/topology-integration.test.ts` → 退出码 0，Files/Tests 全 passed。判据：命令 + 结果摘要（断言数）贴进卡文档。

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

### v1-26 · 看板实测回归（真实打开页面）·研发

**验收内容**：【看板实测回归（真实打开页面）·研发】验收：真实打开页面并可复核：`cd agent-dh && node docs/requirements/REQ-260927202051-f6df/notes/board-live/cdp-board-check.mjs --port 13080 --req REQ-260927202051-f6df --out docs/requirements/REQ-260927202051-f6df/notes/board-live/shots-after-restart` → 退出码 0、15 passed / 0 failed；产出 shots-after-restart/SUMMARY.json + 4 张 PNG。判据：命令 + 断言数 + 截图路径贴进卡文档（禁止以 curl 200 代替渲染验证）。

**操作步骤**：
1. 真实打开页面并可复核：`cd agent-dh && node docs/requirements/REQ-260927202051-f6df/notes/board-live/cdp-board-check.mjs --port 13080 --req REQ-260927202051-f6df --out docs/requirements/REQ-260927202051-f6df/notes/board-live/shots-after-restart` → 退出码 0、15 passed / 0 failed
2. 产出 shots-after-restart/SUMMARY.json + 4 张 PNG。判据：命令 + 断言数 + 截图路径贴进卡文档（禁止以 curl 200 代替渲染验证）。

**预期结果**：按上述步骤执行后满足验收标准：真实打开页面并可复核：`cd agent-dh && node docs/requirements/REQ-260927202051-f6df/notes/board-live/cdp-board-check.mjs --port 13080 --req REQ-260927202051-f6df --out docs/requirements/REQ-260927202051-f6df/notes/board-live/shots-after-restart` → 退出码 0、15 passed / 0 failed；产出 shots-after-restart/SUMMARY.json + 4 张 PNG。判据：命令 + 断言数 + 截图路径贴进卡文档（禁止以 curl 200 代替渲染验证）。

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

### v1-27 · 看板实测回归（真实打开页面）·联调

**验收内容**：【看板实测回归（真实打开页面）·联调】验收：接口出数与磁盘真值逐项一致并可复核：① `cd agent-dh && node docs/requirements/REQ-260927202051-f6df/notes/board-live/integration-probe.mjs --port 13080` → 退出码 0、全 passed；② `curl -s localhost:13080/dashboard/api/reqboard/state` 返回 requirements=82 / tasks=616，与 `docs/requirements/*/queue.json` 逐项一致。判据：两条命令 + 结果摘要贴进卡文档。

**操作步骤**：
1. 接口出数与磁盘真值逐项一致并可复核：① `cd agent-dh && node docs/requirements/REQ-260927202051-f6df/notes/board-live/integration-probe.mjs --port 13080` → 退出码 0、全 passed
2. ② `curl -s localhost:13080/dashboard/api/reqboard/state` 返回 requirements=82 / tasks=616，与 `docs/requirements/*/queue.json` 逐项一致。判据：两条命令 + 结果摘要贴进卡文档。

**预期结果**：按上述步骤执行后满足验收标准：接口出数与磁盘真值逐项一致并可复核：① `cd agent-dh && node docs/requirements/REQ-260927202051-f6df/notes/board-live/integration-probe.mjs --port 13080` → 退出码 0、全 passed；② `curl -s localhost:13080/dashboard/api/reqboard/state` 返回 requirements=82 / tasks=616，与 `docs/requirements/*/queue.json` 逐项一致。判据：两条命令 + 结果摘要贴进卡文档。

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

### v1-28 · 看板实测回归（真实打开页面）·复核

**验收内容**：【看板实测回归（真实打开页面）·复核】验收：对设计与实现的偏离逐条给出结论；无偏离时显式写明「无偏离」及依据

**操作步骤**：
1. 对设计与实现的偏离逐条给出结论
2. 无偏离时显式写明「无偏离」及依据

**预期结果**：按上述步骤执行后满足验收标准：对设计与实现的偏离逐条给出结论；无偏离时显式写明「无偏离」及依据

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

### v1-29 · 看板实测回归（真实打开页面）·测试

**验收内容**：【看板实测回归（真实打开页面）·测试】验收：三条目标命令全绿并贴原文：① `cd packages/web/dsh-pmboard && npx vitest run tests/queue`（12 files / 131 passed）；② `node docs/requirements/REQ-260927202051-f6df/notes/board-live/cdp-board-check.mjs --port 13080 --req REQ-260927202051-f6df`（15 passed）；③ `node docs/requirements/REQ-260927202051-f6df/notes/board-live/route-probe.mjs --port 13080`（4 passed）。判据：三条命令均退出码 0 + 结果摘要贴进卡文档。

**操作步骤**：
1. 三条目标命令全绿并贴原文：① `cd packages/web/dsh-pmboard && npx vitest run tests/queue`（12 files / 131 passed）
2. ② `node docs/requirements/REQ-260927202051-f6df/notes/board-live/cdp-board-check.mjs --port 13080 --req REQ-260927202051-f6df`（15 passed）
3. ③ `node docs/requirements/REQ-260927202051-f6df/notes/board-live/route-probe.mjs --port 13080`（4 passed）。判据：三条命令均退出码 0 + 结果摘要贴进卡文档。

**预期结果**：按上述步骤执行后满足验收标准：三条目标命令全绿并贴原文：① `cd packages/web/dsh-pmboard && npx vitest run tests/queue`（12 files / 131 passed）；② `node docs/requirements/REQ-260927202051-f6df/notes/board-live/cdp-board-check.mjs --port 13080 --req REQ-260927202051-f6df`（15 passed）；③ `node docs/requirements/REQ-260927202051-f6df/notes/board-live/route-probe.mjs --port 13080`（4 passed）。判据：三条命令均退出码 0 + 结果摘要贴进卡文档。

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

### v1-30 · 需求级验收

**验收内容**：需求级：交付结论可复核（证据齐全、与设计一致、无范围蔓延）

**操作步骤**：
1. 需求级：交付结论可复核（证据齐全、与设计一致、无范围蔓延）

**预期结果**：按上述步骤执行后满足验收标准：需求级：交付结论可复核（证据齐全、与设计一致、无范围蔓延）

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

### v1-32 · 需求级验收

**验收内容**：验收项不可照着验（历史数据）：以下验收项没写「怎么验」——验收项 定义队列类型与任务契约·复核 缺「怎么验」（"对设计与实现的偏离逐条给出结论；无偏离时显式写明「无偏离」及依据"）——只写断言词不算，必须给**可执行操作**：命令（npx/vitest/curl/pytest…）、可查数据（SQL/字段名）、或可达界面路径（打开某页→看什么）。否则验收只能靠相信，等于没验。；验收项 实现 DAG 拓扑分层与派生视图·复核 缺「怎么验」（"对设计与实现的偏离逐条给出结论；无偏离时显式写明「无偏离」及依据"）——只写断言词不算，必须给**可执行操作**：命令（npx/vitest/curl/pytest…）、可查数据（SQL/字段名）、或可达界面路径（打开某页→看什么）。否则验收只能靠相信，等于没验。；验收项 看板实测回归（真实打开页面）·复核 缺「怎么验」（"对设计与实现的偏离逐条给出结论；无偏离时显式写明「无偏离」及依据"）——只写断言词不算，必须给**可执行操作**：命令（npx/vitest/curl/pytest…）、可查数据（SQL/字段名）、或可达界面路径（打开某页→看什么）。否则验收只能靠相信，等于没验。。请补可执行操作（命令/可查数据/界面路径）；本条不阻断验收，但必须有人看过并决定。

**操作步骤**：
1. 验收项不可照着验（历史数据）：以下验收项没写「怎么验」——验收项 定义队列类型与任务契约·复核 缺「怎么验」（"对设计与实现的偏离逐条给出结论
2. 无偏离时显式写明「无偏离」及依据"）——只写断言词不算，必须给**可执行操作**：命令（npx/vitest/curl/pytest…）、可查数据（SQL/字段名）、或可达界面路径（打开某页→看什么）。否则验收只能靠相信，等于没验。
3. 验收项 实现 DAG 拓扑分层与派生视图·复核 缺「怎么验」（"对设计与实现的偏离逐条给出结论
4. 无偏离时显式写明「无偏离」及依据"）——只写断言词不算，必须给**可执行操作**：命令（npx/vitest/curl/pytest…）、可查数据（SQL/字段名）、或可达界面路径（打开某页→看什么）。否则验收只能靠相信，等于没验。
5. 验收项 看板实测回归（真实打开页面）·复核 缺「怎么验」（"对设计与实现的偏离逐条给出结论
6. 无偏离时显式写明「无偏离」及依据"）——只写断言词不算，必须给**可执行操作**：命令（npx/vitest/curl/pytest…）、可查数据（SQL/字段名）、或可达界面路径（打开某页→看什么）。否则验收只能靠相信，等于没验。。请补可执行操作（命令/可查数据/界面路径）
7. 本条不阻断验收，但必须有人看过并决定。

**预期结果**：按上述步骤执行后满足验收标准：验收项不可照着验（历史数据）：以下验收项没写「怎么验」——验收项 定义队列类型与任务契约·复核 缺「怎么验」（"对设计与实现的偏离逐条给出结论；无偏离时显式写明「无偏离」及依据"）——只写断言词不算，必须给**可执行操作**：命令（npx/vitest/curl/pytest…）、可查数据（SQL/字段名）、或可达界面路径（打开某页→看什么）。否则验收只能靠相信，等于没验。；验收项 实现 DAG 拓扑分层与派生视图·复核 缺「怎么验」（"对设计与实现的偏离逐条给出结论；无偏离时显式写明「无偏离」及依据"）——只写断言词不算，必须给**可执行操作**：命令（npx/vitest/curl/pytest…）、可查数据（SQL/字段名）、或可达界面路径（打开某页→看什么）。否则验收只能靠相信，等于没验。；验收项 看板实测回归（真实打开页面）·复核 缺「怎么验」（"对设计与实现的偏离逐条给出结论；无偏离时显式写明「无偏离」及依据"）——只写断言词不算，必须给**可执行操作**：命令（npx/vitest/curl/pytest…）、可查数据（SQL/字段名）、或可达界面路径（打开某页→看什么）。否则验收只能靠相信，等于没验。。请补可执行操作（命令/可查数据/界面路径）；本条不阻断验收，但必须有人看过并决定。

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

### v1-33 · 需求级验收

**验收内容**：E2E 覆盖：**无（缺口）**——本需求交付涉及多组件串联，但只交了单元/集成测试。请补一条端到端场景用例（断言可观察终态）。

**操作步骤**：
1. E2E 覆盖：**无（缺口）**——本需求交付涉及多组件串联，但只交了单元/集成测试。请补一条端到端场景用例（断言可观察终态）。

**预期结果**：按上述步骤执行后满足验收标准：E2E 覆盖：**无（缺口）**——本需求交付涉及多组件串联，但只交了单元/集成测试。请补一条端到端场景用例（断言可观察终态）。

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

## 2. 测试报告

- 迁移投产：node --import tsx/esm packages/web/dsh-pmboard/scripts/migrate-ledger.ts --file .dsh-data/dsh-reqboard.json --root /Users/yunpeng/pi-investment/agent-dh --apply（22:55，内部自动备份 + manifest）；投产后 python 读盘：schemaVersion=9 / 'tasks' in ledger=false / migrations=[{from:8,to:9,by:migrate-ledger.ts}] / requirements=82 / docs/requirements/*/queue.json=51 份 616 条
- 看板实测（主证据）：node docs/requirements/REQ-260927202051-f6df/notes/board-live/cdp-board-check.mjs --port 13080 --req REQ-260927202051-f6df → EXIT=0，15 passed / 0 failed（真实 headless Chrome + CDP，断言取自渲染后 DOM）；结构化证据 docs/requirements/REQ-260927202051-f6df/notes/board-live/shots-after-restart/SUMMARY.json + 4 张 PNG（1680×1413）
- 可达性探针（验收① 等价口径）：node docs/requirements/REQ-260927202051-f6df/notes/board-live/route-probe.mjs --port 13080 → EXIT=0，4 passed / 0 failed：GET /(带 cookie)→200 bytes=32257 pmboard=5；无 cookie→401；/dashboard→404 bytes=0（客户端 hash 路由）；/dashboard/api/reqboard/state→200 requirements=82 tasks=616
- 联调契约：node docs/requirements/REQ-260927202051-f6df/notes/board-live/integration-probe.mjs --port 13080 → EXIT=0，34~36 passed / 0 failed（/state 出口 vs 磁盘真值逐项：616 任务 id 顺序、layer 剥离、零写证明 queue.json 指纹 before=after）；证据 docs/requirements/REQ-260927202051-f6df/notes/board-live/integration-summary.json
- 定向回归套（14 个测试文件：队列域 10 个 + 类型契约/类型联调/读方等价性/用例层/拆分写队列/执行顺序/HTTP 联调/端到端/迁移两套/run-status/输出契约/agent 句柄；逐条命令见 docs/requirements/REQ-260927202051-f6df/tests/test-evidence.md §7）：cd packages/web/dsh-pmboard && npx vitest run（文件集同上）→ Test Files 23 passed (23) / Tests 223 passed (223)，EXIT=0；原始输出 docs/requirements/REQ-260927202051-f6df/notes/board-live/targeted-suite-after-fix.console.log；首跑 22 files / 220 tests 的原始输出同目录 targeted-suite.console.log
- 测试阶段（独立复跑）：报告 docs/requirements/REQ-260927202051-f6df/notes/board-live/test-run/report.md → CDP 15/15 + 探针 4/4 + npx vitest run packages/web/dsh-pmboard/tests/queue → 12 files / 131 passed，三条命令均 EXIT=0
- 端到端验收链：npx vitest run packages/web/dsh-pmboard/tests/t17-queue-e2e.test.ts → Exited 0（单 it 连续链：建需求→design→拆分批准→queue.json 生成且台账 hasTasks=false→父卡懒展开 4 子卡→逐张闭环→ready 解锁→rollup 进 accepting）
- 迁移三态与幂等：--dry-run 零写预演（基准 docs/requirements/REQ-260927202051-f6df/notes/migration-dryrun-baseline.md，612 条/51 组/orphan 0）；纯净副本 --verify exit 0；重复 --apply → already_v9，md5 不变
- 链收尾原文：docs/requirements/REQ-260927202051-f6df/advance-log.md 末 6 行 = RUN_SUBTASK t-c130ca/t-6df9a0/t-f4c9f5/t-10122a 全 ok + FINALIZE_PARENT t-e77b06 ok + ROLLUP ok（23:42:27→24:00:03）；台账 advance.runId/lockAt 已清空，需求 status=accepting
- 覆盖声明（29/29 任务卡 covers 标注，供覆盖度门禁读取）：docs/requirements/REQ-260927202051-f6df/tests/test-evidence.md §7（TC-1~TC-18 逐条给命令与期望）；修复记录：packages/web/dsh-pmboard/tests/advance-agent-handle.test.ts 补齐 ensureAgentHandle 第 5 参 tasks（该文件属 D14，仍按 4 参调用；生产调用点 packages/web/dsh-pmboard/src/application/use-cases/ExecuteTask.ts 已正确传 queueTasks，无线上缺陷）
- 运维修复留档：docs/requirements/REQ-260927202051-f6df/notes/ops-repair/README.md + docs/requirements/REQ-260927202051-f6df/notes/ops-repair/req-lock-repair.py（含副本实测：首跑修复、重跑真 no-op、v8 台账拒写 exit 2；备份 dsh-reqboard.json.pre-lock-repair-1790523484239）
- 评审报告（落盘）：docs/requirements/REQ-260927202051-f6df/reviews/board-live-review.md —— 独立复跑主证据 + 自建依赖探针，4 处偏离全部定性、未发现实现层缺陷
- 待裁决口径清单：docs/requirements/REQ-260927202051-f6df/verification-addendum.md §四（验收① 字面命令口径、标准#3 verify 可达性、TC-10.2 依赖连线文本三处）；同文件 §三 记录施工期修的 3 处缺陷（陈旧 advance 锁 / migrations 留痕 / 陈旧测试调用点）

## 3. 文档完整性检查

✓ 9 类文档齐全

## 4. 验收结果

| 编号 | 验收项 | 状态 | 验收人 | 验收时间 |
|---|---|---|---|---|
| v1-1 | 定义队列类型与任务契约 | ✓ 通过 | human/session-3936d77f-2391-4042-8305-9b0fb5e9d2b8 | 2026-09-28 00:08 |
| v1-2 | 实现 DAG 拓扑分层与派生视图 | ✓ 通过 | human/session-3936d77f-2391-4042-8305-9b0fb5e9d2b8 | 2026-09-28 00:08 |
| v1-3 | 实现队列数据校验 V-1~V-6 | ✓ 通过 | human/session-3936d77f-2391-4042-8305-9b0fb5e9d2b8 | 2026-09-28 00:08 |
| v1-4 | 实现队列仓储与原子写入 | ✓ 通过 | human/session-3936d77f-2391-4042-8305-9b0fb5e9d2b8 | 2026-09-28 00:08 |
| v1-5 | 实现 TaskStore 端口与队列实现 | ✓ 通过 | human/session-3936d77f-2391-4042-8305-9b0fb5e9d2b8 | 2026-09-28 00:08 |
| v1-6 | 台账 schema v9：移除 tasks | ✓ 通过 | human/session-3936d77f-2391-4042-8305-9b0fb5e9d2b8 | 2026-09-28 00:08 |
| v1-7 | 读方改造 A：看板与 HTTP 路由 | ✓ 通过 | human/session-3936d77f-2391-4042-8305-9b0fb5e9d2b8 | 2026-09-28 00:08 |
| v1-8 | 读方改造 B：执行工具 | ✓ 通过 | human/session-3936d77f-2391-4042-8305-9b0fb5e9d2b8 | 2026-09-28 00:08 |
| v1-9 | 读方改造 C：用例层 | ✓ 通过 | human/session-3936d77f-2391-4042-8305-9b0fb5e9d2b8 | 2026-09-28 00:08 |
| v1-10 | 读方改造 D：门禁、查询与 Dive | ✓ 通过 | human/session-3936d77f-2391-4042-8305-9b0fb5e9d2b8 | 2026-09-28 00:08 |
| v1-11 | 接线 Decompose：任务写入队列 | ✓ 通过 | human/session-3936d77f-2391-4042-8305-9b0fb5e9d2b8 | 2026-09-28 00:08 |
| v1-12 | 接线 ExecuteTask/MoveTask：读队列与顺序契约 | ✓ 通过 | human/session-3936d77f-2391-4042-8305-9b0fb5e9d2b8 | 2026-09-28 00:08 |
| v1-13 | 实现 v8→v9 迁移变换与 CLI | ✓ 通过 | human/session-3936d77f-2391-4042-8305-9b0fb5e9d2b8 | 2026-09-28 00:08 |
| v1-14 | 迁移安全：白名单、幂等与 orphan | ✓ 通过 | human/session-3936d77f-2391-4042-8305-9b0fb5e9d2b8 | 2026-09-28 00:08 |
| v1-15 | 迁移契约比对：587 条零字段丢失 | ✓ 通过 | human/session-3936d77f-2391-4042-8305-9b0fb5e9d2b8 | 2026-09-28 00:08 |
| v1-16 | 看板实测回归（真实打开页面） | ✓ 通过 | human/session-3936d77f-2391-4042-8305-9b0fb5e9d2b8 | 2026-09-28 00:08 |
| v1-17 | 端到端验收与文档同步 | ✓ 通过 | human/session-3936d77f-2391-4042-8305-9b0fb5e9d2b8 | 2026-09-28 00:08 |
| v1-18 | 定义队列类型与任务契约·研发 | ✓ 通过 | human/session-3936d77f-2391-4042-8305-9b0fb5e9d2b8 | 2026-09-28 00:08 |
| v1-19 | 定义队列类型与任务契约·联调 | ✓ 通过 | human/session-3936d77f-2391-4042-8305-9b0fb5e9d2b8 | 2026-09-28 00:08 |
| v1-20 | 定义队列类型与任务契约·复核 | ✓ 通过 | human/session-3936d77f-2391-4042-8305-9b0fb5e9d2b8 | 2026-09-28 00:08 |
| v1-21 | 定义队列类型与任务契约·测试 | ✓ 通过 | human/session-3936d77f-2391-4042-8305-9b0fb5e9d2b8 | 2026-09-28 00:08 |
| v1-22 | 实现 DAG 拓扑分层与派生视图·研发 | ✓ 通过 | human/session-3936d77f-2391-4042-8305-9b0fb5e9d2b8 | 2026-09-28 00:08 |
| v1-23 | 实现 DAG 拓扑分层与派生视图·联调 | ✓ 通过 | human/session-3936d77f-2391-4042-8305-9b0fb5e9d2b8 | 2026-09-28 00:08 |
| v1-24 | 实现 DAG 拓扑分层与派生视图·复核 | ✓ 通过 | human/session-3936d77f-2391-4042-8305-9b0fb5e9d2b8 | 2026-09-28 00:08 |
| v1-25 | 实现 DAG 拓扑分层与派生视图·测试 | ✓ 通过 | human/session-3936d77f-2391-4042-8305-9b0fb5e9d2b8 | 2026-09-28 00:08 |
| v1-26 | 看板实测回归（真实打开页面）·研发 | ✓ 通过 | human/session-3936d77f-2391-4042-8305-9b0fb5e9d2b8 | 2026-09-28 00:08 |
| v1-27 | 看板实测回归（真实打开页面）·联调 | ✓ 通过 | human/session-3936d77f-2391-4042-8305-9b0fb5e9d2b8 | 2026-09-28 00:08 |
| v1-28 | 看板实测回归（真实打开页面）·复核 | ✓ 通过 | human/session-3936d77f-2391-4042-8305-9b0fb5e9d2b8 | 2026-09-28 00:08 |
| v1-29 | 看板实测回归（真实打开页面）·测试 | ✓ 通过 | human/session-3936d77f-2391-4042-8305-9b0fb5e9d2b8 | 2026-09-28 00:08 |
| v1-30 | 需求级验收 | ✓ 通过 | human/session-3936d77f-2391-4042-8305-9b0fb5e9d2b8 | 2026-09-28 00:08 |
| v1-32 | 需求级验收 | ✓ 通过 | human/session-3936d77f-2391-4042-8305-9b0fb5e9d2b8 | 2026-09-28 00:08 |
| v1-33 | 需求级验收 | ✓ 通过 | human/session-3936d77f-2391-4042-8305-9b0fb5e9d2b8 | 2026-09-28 00:08 |
