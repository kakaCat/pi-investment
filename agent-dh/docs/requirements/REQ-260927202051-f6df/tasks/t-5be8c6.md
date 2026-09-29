# t-5be8c6 实现 DAG 拓扑分层与派生视图·研发

> 需求：REQ-260927202051-f6df 实现 DAG 任务队列机制（拆分时生成 queue.json）

## 在做什么
实现 DAG 拓扑分层与派生视图·研发

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 得到什么结果

落盘拓扑分层实现并可复核：① `cd packages/web/dsh-pmboard && npx tsc --noEmit` 对本卡改动文件无新增类型错误；② `npx vitest run tests/queue/topology.test.ts` 退出码 0、用例全 passed（含畸形输入不抛错的回归用例）。判据：命令退出码 0 + 输出摘要贴进卡文档。

## 汇报 1（2026-09-27T15:10:33.490Z，窗口 2a25a465-67f8-4cac-8e4d-4faccbe3765e）

t-0e7fac/t-5be8c6（dev）：DAG 拓扑分层与派生视图已落盘并独立复核通过——topology.ts 三个纯函数（computeLayers/computeEdges/computeReady）+ tests/queue/topology.test.ts 17 用例全绿，覆盖线性/菱形/多层/环/空/多 ready/依赖已 done 七种形状。本卡产物在本链此前已提交落盘，本窗口为重放窗口，未新造代码，做的是**独立复核**：目标命令、纯函数门禁、computeReady 唯一实现均实测过关。另登记一处跨卡口径漂移线索（readyTasksOf，见下），不在本卡写域，未改。

### 完成项

- topology.ts 落盘（packages/web/dsh-pmboard/src/domain/queue/topology.ts）：computeLayers = Kahn 入度分层（同层=入度 0 波次，layer 从 0 递增），环/自依赖抛 Error 且 message 含 CIRCULAR、code=CIRCULAR_DEPENDENCY；computeEdges = 由 dependsOn 展开（from=前置，重复项去重，悬空依赖仍展开交 V-3 检）；computeReady = 自身 todo 且依赖全 done 者入 ready（悬空依赖保守不放行，返回顺序=入参顺序）
- tests/queue/topology.test.ts 落盘：TC-1.1 线性、TC-1.2 菱形、TC-1.3 环（+自依赖）、TC-1.4 空、TC-1.5 多 ready、TC-1.6 依赖已 done、TC-1.7 纯函数，另加多层/悬空/畸形输入（null/数字/字符串）/dependsOn 非数组等回归形状，共 17 用例全绿
- 菱形锚点实测：t1→{t2,t3}→t4 得 layers=[[t1],[t2,t3],[t4]] 且 ready=['t1']（TC-1.2）
- 环锚点实测：t1→t2→t3→t1 抛错且 message 含 CIRCULAR、code=CIRCULAR_DEPENDENCY（TC-1.3）
- 空输入锚点实测：computeLayers/computeEdges/computeReady 均返回 [] 且不抛错（TC-1.4）
- 纯函数门禁实测：grep -c "node:fs" src/domain/queue/topology.ts = 0；唯一非类型 import 是 './QueueTypes.js'（type-only）；用例「不改动入参」通过
- computeReady 唯一实现复核：唯一写路径 src/repositories/QueueTaskStore.ts:255/261 与校验 src/domain/queue/validateQueue.ts:30/252 均 import 自 topology.ts，全仓无第二份 ready 算法（src/ 内 grep computeReady/computeLayers 仅这些站点）
- 路径口径偏离（显式说明，非静默降级）：父卡得到的锚点写 `npx vitest run src/domain/queue/topology.test.ts`，但本仓 vitest.config.ts 的 include=tests/**/*.test.ts——实测把测试放 src/ 下该命令输出 `No test files found`（exit 1）。故测试落在 tests/queue/topology.test.ts，对应验收命令为 `npx vitest run tests/queue/topology.test.ts`。未改 vitest.config.ts（不在本卡写域）
- 跨卡口径漂移线索（登记，不属本卡写域，未改）：src/application/use-cases/queue-access.ts:37 readyTasksOf 是第二份 ready 判定，且语义比 topology.computeReady 更宽——悬空依赖与 canceled 依赖被当作已满足（d===undefined 或无 done 时返回 true），而 computeReady 与 validateQueue V-5 要求依赖必须 done。写路径未用它，但运行期派活/父卡取数若按它筛，会与队列文件的 ready 分叉；建议 Lead 派单归一到 computeReady 口径

### 改动文件

- `packages/web/dsh-pmboard/src/domain/queue/topology.ts`
- `packages/web/dsh-pmboard/tests/queue/topology.test.ts`

### 下一步

交联调卡 t-315ea1（task-6）：以 tests/queue/topology.test.ts 为接口样例，验证 computeLayers/computeEdges/computeReady 与既有读方（QueueTaskStore.mutate 重算派生视图）联调一致。

---
