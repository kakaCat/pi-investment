# 看板实测回归（真实打开页面）· 实测运行报告

> 卡：t-e77b06（父卡）/ **t-c130ca（·研发 子卡）**　需求：REQ-260927202051-f6df
> 本卡阶段凭证形态：**写入族**（落盘产出 = 本报告 + SUMMARY.json + 4 张截图 + 探针脚本与日志）
> 数据来源与时点遵循 R-013：每条数字都标了命令/工具与采集时点，无来源的数字不入报告。

---

## 0. 被测对象（先钉事实，再谈结论）

| 项 | 取值 | 来源 |
|---|---|---|
| 端口/实例 | `:13080`，pid **9454**，父进程 67516 | `lsof -ti:13080 -sTCP:LISTEN`、`ps -o pid,ppid,lstart -p 9454`（2026-09-27 23:39 +08:00） |
| 启动时刻 | **2026-09-27 23:38:16 (+08:00)**，由 `quick_restart` 拉起 | `ps` lstart；`.dsh-data/state/quick-restart-request.json`（requestedAt 23:37:53） |
| 启动命令 | `node --import tsx/esm …/@deepseek-ai/dsh/lib/bin.js --profile agent-dh --port 13080` | `ps` |
| 被测插件解析 | `.dsh-data/profiles/agent-dh/node_modules/dsh-pmboard` → symlink → `packages/web/dsh-pmboard`（`main = dist/index.mjs`） | `ls -la`、`node -e require.resolve` |
| 服务端产物 | `dist/index.mjs` 构建于 **23:03**；`find src -newer dist/index.mjs` = **0 个文件** ⇒ 产物不旧于源码 | `ls -la dist/`、`find src -newer dist/index.mjs` |
| client 半 | `lib/client.js`（302,659 B）同为 **23:03** 构建 | `ls -la lib/` |
| 台账 | `.dsh-data/dsh-reqboard.json`：`schemaVersion=9`、`migrations=[{from:8,to:9,at:1790520911425,by:"migrate-ledger.ts"}]`、**无 `tasks` 键**、requirements=**82** | python 读盘（23:39） |
| 陈旧锁 | 已清（repair 备份 `dsh-reqboard.json.pre-lock-repair-1790523484239` @ 23:37）；本卡派发拿到**新** runId `run-1790523514215-xbzxb90` | `ls .dsh-data/`、台账 `requirements[].advance` |
| 代码版本 | git `HEAD=fb81e517`（工作区含他人未提交改动，见 §4 边界 4） | `git rev-parse --short HEAD` |

**关于「重启」这一步**：本卡方案要求「迁移与读方改造完成后重启 :13080，再实开」。被测实例 **23:38:16 的启动已晚于**台账迁移（22:55）、迁移留痕修复（23:37）与 dist 构建（23:03），即**当前实例本身就是"迁移+读方改造之后"的新进程**；因此本轮实测直接落在重启后的实例上，**没有再叠一次重启**（:13080 上的 dsh web 会话即本次验证的执行环境，重复重启会杀掉验证进程本身；且 §3 的对照已跨越一次重启边界：23:19 的 `shots-before-restart` 采于 23:38 重启之前）。

启动日志（`.dsh-data/state/quick-restart.log` 最后一次 `Agent-DH 启动` 段落，28 行）关键行：

```
Queue ready tasks: t-c130ca (requirement REQ-260927202051-f6df)      ← 读方在 boot 即从队列出 ready，非从台账 tasks 字段
[2026-09-27 23:38:08] health ok (HTTP 401)                            ← 401 为鉴权在位（非故障）
```

---

## 1. 执行的命令与输出摘要

### 1.1 真实浏览器实测（headless Chrome + CDP，主证据）

```bash
node docs/requirements/REQ-260927202051-f6df/notes/board-live/cdp-board-check.mjs \
  --port 13080 --out docs/requirements/REQ-260927202051-f6df/notes/board-live/shots-after-restart \
  --req REQ-260927202051-f6df
# → EXIT=0；断言：15 passed / 0 failed
```

原始 stdout 全文：`notes/board-live/run-after-restart.console.log`
结构化证据：`notes/board-live/shots-after-restart/SUMMARY.json`

断言逐条（全部 PASS）：

| # | 断言 | 实测值 |
|---|---|---|
| 1 | 页面加载（未落到 401） | `title=DeepSeek Harness`、`rev=93a86bdd0e9f`、`__dshReqboardClient=true` |
| 2 | pmboard client 半已接管 | `window.__dshReqboardClient` 存在 |
| 3 | 泳道看板渲染出泳道 | 泳道数 = **6** |
| 4 | 泳道看板有需求卡（非空） | 卡片数 = **34**，空态 = false |
| 5 | 本需求卡片可见 | REQ-260927202051-f6df 卡片命中，文案含「父卡 2/3 · 子卡 8/12」 |
| 6 | 列表视图渲染出行 | 行数 = **10** |
| 7 | 任务总览页渲染（非空） | 需求分组 = **51**，任务行 = **616**（`616 个任务 · 51 个需求`） |
| 8 | 甘特图 SVG 渲染 | `.dsh-pm-gantt` 在场，条形数 = **2906** |
| 9 | 本需求在任务总览可见 | 该需求分组的甘特条 = **122** |
| 10 | 需求详情页渲染 | 正文 169,431 字符、表格 3、任务行 **69**、6 个 Tab（概览/执行/时间线/归档/追溯/Token） |
| 11 | 依赖信息可见（DAG 或依赖列） | `.dsh-pm-dag` = true，DAG 层 = **11**，文本含「依赖」 |
| 12 | 无未捕获页面异常 | **0** 条 |
| 13 | 无 console.error | **0** 条 |
| 14 | 无失败的数据请求 | **0** 条（XHR/Fetch 加载失败） |
| 15 | 接口侧交叉核对（tasks 与 DOM 同源） | 接口 tasks=**616**、requirements=**82**，DOM 卡片=**34** |

### 1.2 页面可达性探针（验收①的可复现口径）

```bash
node docs/requirements/REQ-260927202051-f6df/notes/board-live/route-probe.mjs --port 13080
# → EXIT=0；断言：4 passed / 0 failed
```

原始 stdout：`notes/board-live/route-probe.console.log`

| 断言 | 实测 | 说明 |
|---|---|---|
| `GET /`（带 dsh-auth cookie） | **200**，bytes=32257，`pmboard` 命中 **5** | 看板 shell 可达、client 半已注入 |
| `GET /`（无 cookie） | **401** | 鉴权在位 |
| `GET /dashboard`（带 cookie） | **404**，bytes=0 | **客户端 hash 路由**，服务端无此 path |
| `GET /dashboard/api/reqboard/state`（带 cookie） | **200**，requirements=**82**、tasks=**616**、rev=5950 | 读方在生产实例上出数 |

### 1.3 启动日志核验（验收⑤）

```bash
# 取 quick-restart.log 中最后一次「Agent-DH 启动」段落（28 行）后统计
LEDGER_REQUIRES_MIGRATION  命中 0
UnhandledPromiseRejection  命中 0
uncaughtException          命中 0
TypeError                  命中 0
```

### 1.4 落盘截图（验收⑦）

| 视图 | 路径 | 大小 |
|---|---|---|
| 泳道看板 | `docs/requirements/REQ-260927202051-f6df/notes/board-live/shots-after-restart/01-board-lanes.png` | 258,658 B |
| 列表视图 | `…/shots-after-restart/02-board-list.png` | 261,817 B |
| 任务总览 + 甘特 | `…/shots-after-restart/03-tasks-gantt.png` | 349,328 B |
| 需求详情 | `…/shots-after-restart/04-req-detail.png` | 483,218 B |

每条断言都带 `01–04` 的页面图，**未以 `curl 200` 代替渲染验证**（渲染断言读的是 `document.querySelector` 计数，不是接口 JSON）。

### 1.5 单元非回归（旁证，非本卡主证据）

```bash
cd packages/web/dsh-pmboard && npx vitest run tests/queue
# → Test Files 12 passed (12)；Tests 131 passed (131)；Duration 848ms（2026-09-27 23:41:54）
```

读方/队列相关单测全绿，与 §1.1 的浏览器实开互相独立：单测证明逻辑，浏览器证明渲染链路（R-013 口径：前者 source 级夹具、后者真实实例）。

---

## 2. 七项验收对照

| 验收项 | 结论 | 依据 |
|---|---|---|
| ① 启动后页面可达（`grep -c pmboard ≥ 1`） | **口径修订后成立** | 原命令打 `/dashboard` 命中 0 —— 该 path 是客户端 hash 路由，服务端 404；等价口径 `GET /` → 200 且 `pmboard=5`（§1.2） |
| ② 真实打开任务页，历史与在制任务可见且数量与迁移后一致（TC-10.1） | **成立** | 泳道卡 34 / 列表 10 / 任务总览 616 行 · 51 组；与迁移基准对账见 §2.1 |
| ③ 甘特/阶段视图正常渲染，无空白无 500（TC-10.2） | **成立** | 甘特 SVG 2906 条、本需求 122 条；阶段/DAG 11 层；页面异常 0、失败请求 0 |
| ④ 需求详情任务列表非空且字段完整（TC-10.3） | **成立** | 详情页 3 张表、任务行 69、6 个 Tab 全渲染、正文 169,431 字符 |
| ⑤ 启动日志 `LEDGER_REQUIRES_MIGRATION` = 0 且无未捕获异常（TC-10.4） | **成立** | §1.3：marker 0 / 未处理拒绝 0 / uncaughtException 0 / TypeError 0 |
| ⑥ 本需求自身任务断言可见（TC-10.5） | **成立** | 泳道卡命中本需求；任务总览本需求分组命中（甘特条 122） |
| ⑦ 留页面截图路径作证据 | **成立** | §1.4 四张 PNG + `SUMMARY.json` |

### 2.1 数量对账（「与迁移后一致」怎么算的）

| 指标 | 迁移前基准 | 现算（重启后） | 差值解释 |
|---|---|---|---|
| requirements | 82 | **82** | 不变 |
| requirementsWithTasks | 51 | **51** | 不变（任务总览 51 组） |
| tasks | 612 | **616** | **612 + 4**：本父卡 `OPEN_PARENT` 于 23:12:43 落下的 4 张子卡（`t-c130ca` 研发 / `t-6df9a0` 联调 / `t-f4c9f5` 复核 / `t-10122a` 测试），非丢失/重复 |
| 台账 `tasks` 字段 | 有（v8） | **无**（v9 已迁出） | 迁移按契约把任务搬进各需求 `queue.json` |

基准来源：`notes/migration-dryrun-baseline.json` `_meta.data_point.source_tasks=612`、`source_requirements=82`（2026-09-27 21:26，活台账副本 dry-run，`live_ledger_touched=false`）。4 张新卡的 `createdAt=1790521963022`（=23:12:43）取自 `docs/requirements/REQ-260927202051-f6df/queue.json`。

---

## 3. 重启前后逐项对照（本次实测的核心：单测绿之外的非回归证据）

| 维度 | 重启前（`shots-before-restart`，23:19:34，15 passed/0 failed） | 重启后（`shots-after-restart`，23:39:55，15 passed/0 failed） | 判定 |
|---|---|---|---|
| 泳道数 | 6 | 6 | 一致 |
| 泳道卡片数 | 34 | 34 | 一致 |
| 列表行数 | 10 | 10 | 一致 |
| 任务总览分组 | 51 | 51 | 一致 |
| 任务总览行数 | 616 | 616 | 一致 |
| 甘特条数 | 2906 | 2906 | 一致 |
| 本需求甘特条 | 122 | 122 | 一致 |
| 需求详情表格 / 任务行 | 3 / 69 | 3 / 69 | 一致 |
| DAG 层数 | 11 | 11 | 一致 |
| 接口 tasks / requirements | 616 / 82 | 616 / 82 | 一致 |
| 页面异常 / console.error / 失败请求 | 0 / 0 / 0 | 0 / 0 / 0 | 一致 |
| 台账 rev | 5932 | 5947 | 漂移（运行期评论/产物写入，非结构变化） |
| 详情正文长度 | 165,621 | 169,431 | 漂移（本卡与小卡活动产生的正文增长） |
| shell rev | b65da56e3f77 | 93a86bdd0e9f | 漂移（前端资源版本） |

**结论**：全部**结构性计数逐项相同**，仅 rev/正文长度随运行期活动漂移 —— 即重启 + v8→v9 迁移 + 读方改造**未造成看板回归**。

---

## 4. 判定与边界

- **判定**：本卡（·研发）完成的实测工作通过 —— 真实浏览器 15/15、可达性探针 4/4、读方单测 131/131、启动日志 0 异常、截图齐备、数量与迁移基准逐项对账可解释。
- **边界（不做过度声明）**：
  1. headless 与有头渲染在同一 CSS 下等价，但**截图只供人眼复核，不代替人看**；本报告不宣称「人已确认视觉效果」。
  2. 本轮为**只读观测**：未下单、未改台账、未重启服务（观测动作对生产实例零写，除 dsh web 自身的 rev 增长）。
  3. 验收① 属于**口径偏差**而非失败：`/dashboard` 服务端 404 是 dsh web 的 hash 路由形态；若评审要求保留字面命令，需先在服务端加 `/dashboard` 路由（属新工作，不属本卡）。
  4. 工作区另有他人未提交改动（`config/cordis.yml`、多份 `docs/requirements/**` 等）；本卡**只新增**下节 5 个文件，未触碰他人改动。

## 5. 本卡落盘产出

| 文件 | 说明 |
|---|---|
| `docs/requirements/REQ-260927202051-f6df/notes/board-live/run-report-after-restart.md` | 本报告 |
| `docs/requirements/REQ-260927202051-f6df/notes/board-live/shots-after-restart/SUMMARY.json` | 15 项断言结构化证据 + 截图路径 |
| `…/shots-after-restart/01-board-lanes.png` | 泳道看板截图 |
| `…/shots-after-restart/02-board-list.png` | 列表视图截图 |
| `…/shots-after-restart/03-tasks-gantt.png` | 任务总览 + 甘特截图 |
| `…/shots-after-restart/04-req-detail.png` | 需求详情（含 DAG）截图 |
| `docs/requirements/REQ-260927202051-f6df/notes/board-live/run-after-restart.console.log` | CDP 实测原始 stdout |
| `docs/requirements/REQ-260927202051-f6df/notes/board-live/route-probe.mjs` | 可达性探针脚本（验收①的可复现口径） |
| `docs/requirements/REQ-260927202051-f6df/notes/board-live/route-probe.console.log` | 探针原始 stdout |

> 复用方式（cwd = `agent-dh`）：§1.1 / §1.2 两条命令可直接重放，退出码与断言数应与本报告一致。
