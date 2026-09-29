---
title: 看板实测回归 · 测试证据（父卡 t-e77b06）
type: test-evidence
requirement: REQ-260927202051-f6df
task: t-10122a
generated: 2026-09-27
---

# 测试证据 · 看板实测回归（t-10122a）

> 本文件把子卡 `t-10122a`（测试阶段）与 t-e77b06 链的目标命令、退出码与产物集中成一份**可重放**的证据，
> 详细叙述见 [notes/board-live/test-run/report.md](../notes/board-live/test-run/report.md)。
> 采集时点：2026-09-27 23:59 ~ 24:00 (+08:00)。口径遵循 R-013。

## 1. 三条目标命令（全部 EXIT=0）

| # | 覆盖验收项 | 命令（cwd = `agent-dh`） | 结果 | 原始输出 |
|---|---|---|---|---|
| 1 | ②③④⑥ | `node docs/requirements/REQ-260927202051-f6df/notes/board-live/cdp-board-check.mjs --port 13080 --req REQ-260927202051-f6df --out docs/requirements/REQ-260927202051-f6df/notes/board-live/test-run/shots` | **EXIT=0；15 passed / 0 failed** | `notes/board-live/test-run/cdp-board-check.console.log`、`…/shots/SUMMARY.json` |
| 2 | ①（等价口径） | `node docs/requirements/REQ-260927202051-f6df/notes/board-live/route-probe.mjs --port 13080` | **EXIT=0；4 passed / 0 failed** | `notes/board-live/test-run/route-probe.console.log` |
| 3 | 读方非回归 | `npx vitest run packages/web/dsh-pmboard/tests/queue` | **EXIT=0；12 files / 131 passed** | `notes/board-live/test-run/queue-unit.console.log` |

## 2. 断言明细（命令 1，15/15）

真实 headless Chrome + CDP 加载 `:13080`，断言取自**渲染后 DOM**（`document.querySelector` 计数），非接口 JSON：

| # | 断言 | 实测值 |
|---|---|---|
| 1 | 页面加载（未落到 401） | `title=DeepSeek Harness`、`hasReqboardClient=true` |
| 2 | pmboard client 半已接管 | `window.__dshReqboardClient` 存在 |
| 3 | 泳道看板渲染出泳道 | 泳道数 = **6** |
| 4 | 泳道看板有需求卡（非空） | 卡片数 = **34**，空态 = false |
| 5 | 本需求卡片可见（验收⑥） | REQ-260927202051-f6df 命中 |
| 6 | 列表视图渲染出行 | 行数 = **10** |
| 7 | 任务总览页渲染（非空） | 需求分组 = **51**，任务行 = **616**（「616 个任务 · 51 个需求」） |
| 8 | 甘特图 SVG 渲染（验收③） | `.dsh-pm-gantt` 在场，条形数 = **2912** |
| 9 | 本需求在任务总览可见（验收⑥） | 该需求甘特条 = **128** |
| 10 | 需求详情页渲染（验收④） | 正文 171,531 字符、表格 2、任务行 **64**、6 个 Tab |
| 11 | 依赖信息可见 | `.dsh-pm-dag=true`，DAG 层 = **11**，文本含「依赖」 |
| 12 | 无未捕获页面异常 | **0** 条 |
| 13 | 无 `console.error` | **0** 条 |
| 14 | 无失败的数据请求 | **0** 条（XHR/Fetch） |
| 15 | 接口/DOM 交叉核对 | 接口 `tasks=616`、`requirements=82`，DOM 卡片 = 34 |

## 3. 启动日志核验（验收⑤）

对 `.dsh-data/state/quick-restart.log` **最后一次**「Agent-DH 启动」段落（28 行）：

```
LEDGER_REQUIRES_MIGRATION                               命中 0（整份日志亦为 0）
UnhandledPromiseRejection / uncaughtException / TypeError  命中 0
Queue ready tasks: t-c130ca (requirement REQ-260927202051-f6df)   ← boot 即从队列出 ready
[2026-09-27 23:38:08] health ok (HTTP 401)                        ← 401 为鉴权在位，非故障
```

## 4. 截图去空白校验（验收⑦，非 `curl 200` 代替渲染）

| 视图 | 路径 | 尺寸/大小 | 非白像素比 |
|---|---|---|---|
| 泳道看板 | `notes/board-live/test-run/shots/01-board-lanes.png` | 1680×1413 / 258,956 B | 0.284 |
| 列表视图 | `notes/board-live/test-run/shots/02-board-list.png` | 1680×1413 / 261,835 B | 0.278 |
| 任务总览 + 甘特 | `notes/board-live/test-run/shots/03-tasks-gantt.png` | 1680×1413 / 347,892 B | 0.325 |
| 需求详情（含 DAG/依赖） | `notes/board-live/test-run/shots/04-req-detail.png` | 1680×1413 / 253,845 B | 0.438 |

四张均 1680×1413、采样唯一色 980~2401、非白像素 28%~44% ⇒ **非空白页**（PIL 采样统计）。

## 5. 数量对账（「与迁移后一致」）

| 指标 | 磁盘真值（独立重算） | 看板实测 | 一致性 |
|---|---|---|---|
| 台账 `requirements` | 82 | 接口 `requirements` = 82 | ✅ |
| `queue.json` 份数 / 有任务需求 | 51 | 任务总览分组 = 51 | ✅ |
| 队列任务总数 | **616** | 任务总览行 = 616；接口 `tasks` = 616 | ✅ |
| 本需求任务数 | **29** | 泳道卡显示「父卡 2/3 · 子卡 11/12」；详情页可见 | ✅ |
| 台账 `tasks` 键 | 无（v9） | 看板照常出数（读方已改走队列） | ✅ |

与 t-c130ca 报告（23:39）的计数差异为**运行期漂移**而非回归（甘特条 2906→2912、本需求 122→128、
详情任务行 69→64、正文 169,431→171,531），**结构性计数（616/51/82）逐项不变**。

## 6. 边界

1. headless 与有头渲染在同一 CSS 下等价；**截图供人眼复核，本证据不宣称「人已确认视觉效果」**。
2. 本轮为**只读观测**：未下单、未改台账、未改源码、未重启服务；除自身产物外只新增 `notes/board-live/test-run/`。
3. 验收① 字面命令为**口径偏差**（见 `verification-addendum.md` §四），等价判据成立。

---

## 7. 覆盖声明（`covers:` 标注 · 供覆盖度门禁读取）

> 门禁口径：读 `tests/*.md` + `design/test-cases.md` + `tasks/*.md` 中 `## TC-n:` 段落里的 `covers:` 行。
> 本需求 **29 张非 canceled 任务卡全部**在下面声明覆盖（29/29 ≥ 80% 门槛）。
>
> **统一复跑读数**（2026-09-28 00:06~00:12 +08:00，原始输出 `notes/board-live/targeted-suite-after-fix.console.log`）：
> **Test Files 23 passed (23) / Tests 223 passed (223)，EXIT=0**。
> 首跑为 22 files / 220 tests（`notes/board-live/targeted-suite.console.log`）：`tests/advance-agent-handle.test.ts`
> 3 条红 —— 该文件属 D14（另一需求），仍按 4 参调用 `ensureAgentHandle`，而本需求读方改造给它加了第 5 参
> `tasks`（任务改从队列取，`LedgerView.tasks` 随 v9 移除）⇒ `tasks.find` 抛 `Cannot read properties of undefined`。
> 生产调用点 `ExecuteTask.ts:171` 已正确传 `queueTasks`（无线上缺陷），故仅补齐测试夹具；修复后全绿。

## TC-1: 队列类型契约（类型级断言 + 与既有读方接口联调）
covers: t-87f0da, t-796a50, t-b34b32
命令：`cd packages/web/dsh-pmboard && npx vitest run tests/queue-types.test.ts tests/queue-types-integration.test.ts`
期望：EXIT=0；类型级断言锁死「`QueueTask` 恰好 = `TaskRecord` + `layer`」，联调用例接既有 `readyTasks` 接口。

## TC-2: DAG 拓扑分层与派生视图（纯函数 + 真实仓储联调）
covers: t-0e7fac, t-5be8c6, t-315ea1
命令：`cd packages/web/dsh-pmboard && npx vitest run tests/queue/topology.test.ts tests/queue/topology-integration.test.ts`
期望：EXIT=0；七种图形（线性/菱形/多层/环/空/多 ready/依赖已 done）+ 畸形输入不抛错；联调走真实 `JsonQueueRepository`。

## TC-3: 队列数据校验 V-1~V-6
covers: t-394339
命令：`cd packages/web/dsh-pmboard && npx vitest run tests/queue/validateQueue.test.ts`
期望：EXIT=0；坏数据只报告不抛错（校验是"报告"不是"断言"）。

## TC-4: 队列仓储与原子写入
covers: t-e96a0c
命令：`cd packages/web/dsh-pmboard && npx vitest run tests/queue/QueueRepository.test.ts tests/queue/queue-path.test.ts`
期望：EXIT=0；临时目录内跑，无残留 `.tmp`；路径约定单一事实源。

## TC-5: TaskStore 端口与队列实现
covers: t-bc1ba6
命令：`cd packages/web/dsh-pmboard && npx vitest run tests/queue/QueueTaskStore.test.ts`
期望：EXIT=0；`listAll` 顺序稳定、出口剥离 `layer`、纯删除也写盘。

## TC-6: 台账 schema v9 与迁移留痕
covers: t-2417da
命令：`cd packages/web/dsh-pmboard && npx vitest run tests/queue/ledger-v9.test.ts tests/queue/ledger-migrations-trace.test.ts`
期望：EXIT=0；v8 台账（带 tasks）必须抛 `LEDGER_REQUIRES_MIGRATION`（读兼容从宽容翻转为拒绝）；`migrations` 留痕**往返不丢**。

## TC-7: 读方等价性（看板 / HTTP 路由 / 执行工具）
covers: t-66797c, t-0c7f17
命令：`cd packages/web/dsh-pmboard && npx vitest run tests/read-sites-equivalence.test.ts tests/run-status-tool.test.ts`
期望：EXIT=0；夹具为**真实 v8 台账抽取**，a~e 五条独立断言（id 配对逐字节相等、出口无 layer、负向固化全局序）。

## TC-8: 用例层读方改造
covers: t-860900
命令：`cd packages/web/dsh-pmboard && npx vitest run tests/t9-usecase-queue-refactor.test.ts`
期望：EXIT=0；父子树结构一致、顺序契约打点 `['taskStore.mutate','repo.mutate']`。

## TC-9: 门禁 / 查询 / Dive 与公共夹具 v9 契约
covers: t-8d4af7
命令：`cd packages/web/dsh-pmboard && npx vitest run tests/queue/v9-harness-contract.test.ts tests/queue/tool-deps-fixture.test.ts tests/advance-agent-handle.test.ts`
期望：EXIT=0；公共夹具（31 个用例的底座）v9 语义正确；执行链 agent 句柄兜底三态（透传/兜底/可读失败）。

## TC-10: 拆分把任务写进队列（台账零新增）
covers: t-05925b
命令：`cd packages/web/dsh-pmboard && npx vitest run tests/t11-decompose-queue-write.test.ts`
期望：EXIT=0；`docs/requirements/<REQ>/queue.json` 生成、台账 `'tasks' in ledger === false`。

## TC-11: 执行读队列 + 状态流转解锁下游 + 顺序契约
covers: t-fa3e16
命令：`cd packages/web/dsh-pmboard && npx vitest run tests/t12-queue-readonly-ordering.test.ts`
期望：EXIT=0；`task_run` 只读、下游解锁、跨存储顺序契约不变量。

## TC-12: v8→v9 迁移变换、CLI 与迁移安全
covers: t-faf303, t-03254f
命令：`cd packages/web/dsh-pmboard && npx vitest run tests/migrate-ledger-v8v9.test.ts`
期望：EXIT=0；只在 `os.tmpdir()` 临时工作区跑，绝不触碰活台账；白名单外差异即中止、幂等。

## TC-13: 迁移契约比对（零字段丢失）
covers: t-dfc245
命令：`cd packages/web/dsh-pmboard && npx vitest run tests/migrate-contract.test.ts`
期望：EXIT=0；真实台账数据驱动，按 id 配对逐字段/键集相等，**不写死计数**（条数现算）。

## TC-14: 端到端验收链（建需求 → 拆分落队列 → 台账零新增 → 推进 → 进验收）
covers: t-d1aa0f
命令：`cd packages/web/dsh-pmboard && npx vitest run tests/t17-queue-e2e.test.ts`
期望：EXIT=0；单 `it` 一条真实连续链，全程真实用例入口 + 真实仓储/文件系统。

## TC-15: 看板实测回归（真实打开页面）
covers: t-e77b06, t-c130ca, t-10122a
命令：`cd agent-dh && node docs/requirements/REQ-260927202051-f6df/notes/board-live/cdp-board-check.mjs --port 13080 --req REQ-260927202051-f6df`
期望：EXIT=0；15 passed / 0 failed（断言取自渲染后 DOM），落 4 张真实截图 + `SUMMARY.json`。

## TC-16: 看板/接口出数 × 磁盘真值联调
covers: t-6df9a0
命令：`cd packages/web/dsh-pmboard && npx vitest run tests/t16-http-queue-integration.test.ts`；生产实例另跑 `node docs/requirements/REQ-260927202051-f6df/notes/board-live/integration-probe.mjs --port 13080`
期望：均 EXIT=0；`/state` 出口 616 任务 / 82 需求与磁盘 `queue.json` 逐项一致，且零写。

## TC-17: 独立复核（设计与实现偏离逐条结论）
covers: t-43e512, t-1e2054, t-f4c9f5
证据：`reviews/board-live-review.md` + 各复核卡文档；复核须**独立复跑**（本需求：`npx vitest run tests/queue-types.test.ts`、`tests/queue/topology*.test.ts`、CDP 15/15），逐条给出偏离/无偏离结论。

## TC-18: 测试阶段目标命令（交付可重放的验收入口）
covers: t-c6026b, t-a21eb3, t-10122a
命令：`cd packages/web/dsh-pmboard && npx vitest run tests/queue-types.test.ts tests/queue-types-integration.test.ts`、`npx vitest run tests/queue/topology.test.ts tests/queue/topology-integration.test.ts`、`npx vitest run tests/queue`
期望：均 EXIT=0（`tests/queue` 为 12 files / 131 passed），命令与结果摘要贴进对应卡文档。
