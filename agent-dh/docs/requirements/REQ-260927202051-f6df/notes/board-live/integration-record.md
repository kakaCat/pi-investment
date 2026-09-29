# 看板实测回归（真实打开页面）· 接口联调记录

> 卡：t-e77b06（父卡「看板实测回归（真实打开页面）」）/ **t-6df9a0（·联调 子卡）**　需求：REQ-260927202051-f6df
> 阶段凭证形态：**写入族**（落盘产出 = 本记录 + 探针脚本 + 原始 stdout + 结构化证据 + in-process 联调用例）
> 口径：每条数字标了来源命令与采集时点（R-013）；真值一律取**磁盘独立数据源**（台账 + 各需求 `queue.json`），
> 不取被测代码的内存快照——这是「实际返回与预期一致」的可证伪口径。

---

## 0. 被测对象（先钉事实，再谈结论）

| 项 | 取值 | 来源 |
|---|---|---|
| 实例/端口 | `:13080`，pid **9454**，父 67516 | `lsof -ti:13080 -sTCP:LISTEN`（2026-09-27 23:43 +08:00） |
| 启动时刻 | **2026-09-27 23:38:16**（晚于台账迁移 22:55 与 dist 构建 23:03 ⇒ 被测就是"迁移 + 读方改造之后"的进程） | `ps -o pid,lstart -p 9454` |
| 代码版本 | git `HEAD=fb81e517`（工作区含他人未提交改动） | `git rev-parse --short HEAD` |
| 台账 | `.dsh-data/dsh-reqboard.json`：`schemaVersion=9`、**有 `tasks` 键 = false**、requirements=**82**、revision=**5956**（本卡多轮运行为 5955~5956；同目录 ·研发 报告记录 5932→5947 —— 该值随并发窗口与 `/state` 产物自动发现漂移） | 探针读盘（2026-09-27 23:52）；`integration-summary.json` `truth` |
| 队列真值 | `docs/requirements/*/queue.json` = **51** 份、任务合计 **616** 条（其中本需求 29 条） | 探针读盘（23:52） |
| 鉴权 | 全站受 dsh-auth cookie 保护（无 cookie `/` → 401，实测同前） | `route-probe.mjs`（23:41） |

**联调对象** = reqboard HTTP 面（I-12 看板/路由读方，改造后任务全部来自 `TaskStore`/`queue.json`）：
读接口 7 条（`state` / `requirements/summary` / `stages` / `stage/:stage` / `token` / `marks` / `session/:sid/progress`）
+ 路由 2 条（`health` / 未知路由）+ 写接口 4 个（`task/create`、`task/move`、`task/update`、`comment`）。
断言合计 **36 条**（真值 2 + 读接口 23 + 写拒绝路径 8 + 零写证明 3）。

---

## 1. 请求样例 → 期望 → 实测（读接口）

期望值的推导口径：从磁盘真值**独立复算**（不调用被测实现）——
`tasks` = 需求 id 字典序分组 + 组内队列文件顺序，出口剥离 `layer`（TaskStore D3）；
`ready` = 该需求内 `status=todo` 且 `dependsOn` 全为 `done` 者的 id（`protocol.ts:1401` 契约复算）。

| # | 请求样例 | 期望 | 实测 | 判定 |
|---|---|---|---|---|
| A1-1 | `GET /dashboard/api/reqboard/state`（带 cookie） | 200 `{success:true}` | 200 `success=true` | PASS |
| A1-2 | 同上 → `data.requirements` | = 台账 requirements（id 数量+顺序） | 82 / 82 逐项一致 | PASS |
| A1-3 | 同上 → `data.tasks` | = Σ 各 `queue.json` 任务数（616） | 616（数量） | PASS |
| A1-4 | 同上 → 任务 id 序列 | 需求字典序分组 + 组内队列顺序 | 616 条 id 序列**逐项相同** | PASS |
| A1-5 | 同上 → 每条任务 | 去 `layer` 后与队列文件**键集+值全等** | 616 条逐字段一致（0 条不符） | PASS |
| A1-6 | 同上 → 出口字段 | 无 `layer`（queue 文件有、读方出口剥） | 0 条带 `layer` | PASS |
| A1-7 | 同上 → `data.ready` | 键 = 台账全部需求；值 = 上述 ready 复算结果（顺序=任务数组顺序） | 82 个键；51 个有队列需求全部一致 | PASS |
| A2-1 | `GET /requirements/summary` | 200；本需求 `tasksTotal/tasksDone` = 队列真值 29/25 | 200；29/29、25/25 | PASS |
| A3-1 | `GET /requirements/REQ-260927202051-f6df/stages` | 200；`currentStage=implementing` | 200；7 个节点 | PASS |
| A3-2 | 同上 → `stages[decomposing].body.tasks` | = 队列 29 条（id 顺序 + StageTaskRef 契约字段） | 29 条投影逐字段一致、无契约外键 | PASS |
| A3-3 | 同上 → `stages[implementing].body.tasks` | = 队列 29 条（含 `executions`） | 29 条投影逐字段一致（StageTaskExecution） | PASS |
| A3-4 | 同上 → 响应文本 | 不含 `"layer"` | 不含 | PASS |
| A4-1 | `GET /requirements/<REQ>/stage/implementing` | 200；`body.tasks` = 队列 29 条投影 | 200；tasks=29 逐字段一致 | PASS |
| A4-2 | `GET /requirements/<REQ>/stage/not-a-stage` | 400 `invalid_input` | 400 `invalid_input` | PASS |
| A5-1 | `GET /requirements/<REQ>/token` | 200；`byStage` = 全 7 节点 | 200；byStage=7，totals 四项 | PASS |
| A5-2 | `GET /requirements/<REQ>/marks` | 200；`available=true`；`by` 值域 = 队列任务 id ∪ 计划键 | 200；clauses=8、unreceived=0、越界值 0 | PASS |
| A5-3 | 同上，**全量抽扫** 51 个有队列需求 | 解析出的真实任务 id（`t-xxxxxx`）必须命中该需求 `queue.json` | 51 个扫完；**19 个**出现真实 id 解析；未命中 **0** | PASS |
| A5-4 | `GET /requirements/REQ-does-not-exist-000000/marks` | 404 `not_found` | 404 `not_found` | PASS |
| A6-1 | `GET /session/session-3936d77f-…/progress` | 200；`progress.total/done` = 目标需求队列真值（29/25） | 200；target=本需求、29/29、25/25 | PASS |
| A7-1 | `GET /health` | 200 `{status:'ok'}` | 200 `{"status":"ok"}` | PASS |
| A7-2 | `GET /definitely-not-a-route` | 404 `{success:false, code:'not_found'}` | 404，body 为未知路由信封 | PASS |

**读接口判定：全部 PASS**（A1 8 + A2 2 + A3 4 + A4 2 + A5 4 + A6 1 + A7 2 = 23 条；
表内把 A1-7、A2 等价的多条断言合并成一行展示）。其中 A1-4/A1-5 是最强的一条：616 条任务
**逐字段**与磁盘队列全等，且顺序逐项相同。

---

## 2. 请求样例 → 期望 → 实测（写接口，生产实例只打拒绝路径）

为什么只打拒绝路径：成功路径会真改生产台账/队列，属本卡不应产生副作用；成功路径改在临时工作区用
**真实 handler + 真实文件**联调（§3）。

| # | 请求样例 | 期望 | 实测 | 判定 |
|---|---|---|---|---|
| B-1 | `POST /task/move {"id":"t-deadbeef0001","to":"done"}` | 404 `not_found` | 404 `{"error":"任务 t-deadbeef0001不存在","code":"not_found"}` | PASS |
| B-2 | `POST /task/move {"to":"done"}`（缺 id） | 404 `not_found`（不得误判成功） | 404 `not_found` | PASS |
| B-3 | `POST /task/move {"id":"t-9d53f4","to":"todo","actor":"human"}` | 400 `invalid_transition`（done 非终态但 done→todo 非法） | 400 `invalid_transition`，文案含合法边清单 | PASS |
| B-4 | `POST /task/move {"id":"t-deadbeef0001","to":"不存在的状态"}` | 400 `invalid_input` | 400 `invalid_input` | PASS |
| B-5 | `POST /task/update {"id":"t-deadbeef0001","acceptance":"…"}` | 404 `not_found` | 404 `not_found` | PASS |
| B-6 | `POST /task/create {"requirementId":"REQ-does-not-exist-000000",…}` | 404 `not_found`，**不隐式建档** | 404 `not_found`；需求目录数 69→69 | PASS |
| B-7 | `POST /comment {"requirementId":"REQ-does-not-exist-000000",…}` | 4xx（不静默成功） | 400 `invalid_input`（target 必须是 req/task） | PASS |
| B-8 | `POST /task/move {"id":"t-9d53f4","to":"in_progress","actor":"agent"}`（done 卡重开） | 403 `human_gate`（`HUMAN_ONLY_TASK_TRANSITIONS`：自动链不得重开 done 卡） | 403 `{"error":"该任务转移为人工闸门，仅人可操作","code":"human_gate"}` | PASS |
| B-9 | 只读阶段前后：51 份 `queue.json` 指纹 | 不变（读方不写队列） | `03b38056ee6bab1ce0e320b17a637fb1` → 同值 | PASS |
| B-10 | 拒绝路径前后：51 份 `queue.json` 指纹 + 需求目录数 | 不变（拒绝路径无半写） | 指纹同值；目录 69→69 | PASS |

**写接口（生产）判定：11/11 PASS**（11 = 只读阶段零写 1 + 拒绝路径 8 + 拒绝后零写 2）。
台账 revision 读数：末轮 `5956 → 5956 → 5956`（更早一轮为 `5955 → 5956 → 5956`，只读阶段的跃迁来自
并发窗口 / `/state` 产物自动发现）——该值随并发活动漂移，仅作信息性记录（见下方注记）。

> **关于台账不在零写判据里**：台账会被并发窗口与 `/state` 的产物自动发现（`syncAllReqArtifacts`）写入，
> 把台账纳入前后比对会把"别人在干活"误判成"探针写坏了"（本探针首轮即因此出现一次假 FAIL：指纹里含台账 md5）。
> 故零写判据只取 **`queue.json` 指纹 + 需求目录数**——那才是任务写路径的唯一落点。台账 md5/revision 仅作信息性记录。

---

## 3. 写接口成功路径联调（临时工作区，真实 handler + 真实文件）

生产实例上不写；成功路径联调落在
`packages/web/dsh-pmboard/tests/t16-http-queue-integration.test.ts`（**2 用例全绿**，`os.tmpdir()` 独立工作区，
活台账/队列零接触）：

| 请求样例 | 期望 | 实测 |
|---|---|---|
| `POST /task/create`（A，无依赖） | 200；响应**无 `layer`**；磁盘队列多一条且 `layer=0`、`ready=[A]` | 一致 |
| `POST /task/create`（B，`dependsOn=[A]`） | 200；`layer=1`；`ready=[A]`（下游未解锁）；`edges=[{from:A,to:B}]`；**台账无 `tasks` 键** | 一致 |
| `GET /state` | tasks 与磁盘队列**逐字段相等**（去 `layer`） | 一致 |
| `POST /task/move` A：`in_progress→testing→in_review→done` | 每步 200、状态回显、无 `layer`；A done 后 `ready=[B]`（V-5 派生视图重算），`statusHistory` 含 done | 一致 |
| `POST /task/update`（改 B 的 acceptance） | 200；字段落队列、`version` +1 | 一致 |
| B 也 done 后 | 需求 rollup 由 `system` 推进到 `accepting`；台账仍无 `tasks`；队列两卡全 done | 一致 |
| 错误契约（404/400 各条） | 与生产探针 §2 同款 code | 一致 |
| `GET /requirements/<REQ>/stages` | `implementing.body.tasks` 契约字段与队列逐条一致 | 一致 |
| 队列损坏（先写坏文件再首读） | `/state` 仍 200、该需求任务为 0、坏文件被隔离为 `.corrupt-<ts>` | 一致 |

复现：

```bash
cd packages/web/dsh-pmboard
npx vitest run tests/t16-http-queue-integration.test.ts     # → Test Files 1 passed；Tests 2 passed
npx tsc --noEmit 2>&1 | grep -c t16-http-queue              # → 0（本文件无类型错误）
```

---

## 4. 判定与诚实边界

**判定**：接口联调**通过**——真实 `:13080` 实例上 **36/36** 断言成立
（真值 2 + 读接口 23 + 写接口拒绝路径 8 + 零写证明 3），写成功路径在临时工作区 2/2 用例成立；
请求样例、期望、实测三者逐条对齐，且期望值均由磁盘真值独立复算。

**边界（不做过度声明）**：

1. **不覆盖渲染层**：本卡是接口联调，不是浏览器渲染验收。页面可达/泳道/甘特/详情截图由父卡其它凭证承载
   （同目录 `run-report-after-restart.md` + `shots-after-restart/`，15/15 浏览器断言，23:39）；
   本卡**没有**用 `curl 200` 代替渲染验证，也**不宣称**人眼已复核视觉。
2. **生产实例未做写成功路径**：见 §2 理由；成功路径的联调环境是临时工作区（真实 handler、真实仓储/文件），
   与生产实例共用同一份源码，但**不是**同一个进程。
3. **两个探针口径坑（记录以免后来者重复踩）**：
   ① `StageDetail` 是**判别联合**，节点任务在 `stage.body.tasks`（不在节点顶层）——按顶层取会得到空数组，
   与"读方没读到队列"看起来一模一样；本探针首轮就因此误报 **3 条 FAIL**，修正取值路径后才拿到真值。
   ② `marks` 的 `by` 在本需求是**计划键**（`t1..t16`，requirement.md 的写法）：`content-trace.ts:272-289`
   明确"解析不到台账 id 时保留原文，宁可不标红"。故值域判据 = 队列 id ∪ 计划键；单看本需求
   **无法**证明 marks 从队列出数，故补了 §A5-3 的 51 需求全量抽扫（19 个解析出真实 id、0 越界）。
   （首轮另有 1 条 FAIL 源于未把计划键纳入值域，属判据过严，非接口缺陷。）
4. **并发写入者存在**：本窗口不是唯一写者（另一窗口在推进同一需求）。零写判据因此只取 `queue.json`；
   探针首轮曾把台账纳入指纹，被并发写入扰动成假 FAIL，已按 §2 注记收窄。
5. **未验证**：队列文件跨进程并发的 last-write-wins（UC-4）只在单进程内联调；`/stages` 的 RTM 追溯字段、
   `token` 的 sharePct 数值口径未逐项复核（非本卡范围）。
6. **一处无样本（显式登记，不冒充通过）**：`canceled→todo`（复活仅人）分支**本次未验证**——
   当前 616 条队列任务里 `status=canceled` 为 **0 条**（探针打 INFO 而非 PASS）。同一 `human_gate`
   断言族已由 `done→in_progress（actor=agent）→ 403` 覆盖（§B-8）。

---

## 5. 复现命令与落盘产出

```bash
# 联调探针（只读 + 写接口拒绝路径；零副作用，退出码 0 = 36/36）
cd agent-dh
node docs/requirements/REQ-260927202051-f6df/notes/board-live/integration-probe.mjs --port 13080
# → 断言：36 passed / 0 failed；结构化证据写同目录 integration-summary.json

# 页面可达性（父卡口径 ①，同实例）
node docs/requirements/REQ-260927202051-f6df/notes/board-live/route-probe.mjs --port 13080   # → 4 passed / 0 failed
```

| 文件 | 说明 |
|---|---|
| `docs/requirements/REQ-260927202051-f6df/notes/board-live/integration-record.md` | 本记录 |
| `…/notes/board-live/integration-probe.mjs` | 联调探针（读接口 + 写接口拒绝路径 + 零写证明） |
| `…/notes/board-live/integration-console.log` | 探针原始 stdout（36 PASS / 0 FAIL + 2 条 INFO） |
| `…/notes/board-live/integration-summary.json` | 36 条断言结构化证据 + 真值快照 + 51 份队列 md5 |
| `packages/web/dsh-pmboard/tests/t16-http-queue-integration.test.ts` | 写成功路径联调用例（2 用例，真实 handler + 真实文件） |
