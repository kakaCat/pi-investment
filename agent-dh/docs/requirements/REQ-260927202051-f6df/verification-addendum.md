---
title: 投产实测与收口（REQ-260927202051-f6df 验收补充材料）
type: verification
requirement: REQ-260927202051-f6df
generated: 2026-09-27
supersedes: verification-evidence.md §一#5、§七
---

# 投产实测与收口 · 补充验收材料

> 本文件接续 [verification-evidence.md](./verification-evidence.md)（写于**投产前**）。
> 那份材料里的「#5 待投产窗口实测」「§七 脆弱窗口」已被下面的事实取代；本文件是**投产之后**的实测与收口证据。
> 口径遵循 R-013：每条数字带来源命令/工具 + 采集时点。

---

## 一、投产动作（已发生，不是计划）

| 时点（+08:00） | 动作 | 证据 |
|---|---|---|
| 22:52 / 22:55 | 停机 → `--apply` 迁移（脚本内置服务运行守卫，自动备份 + manifest） | `.dsh-data/dsh-reqboard.json.pre-v9-20260927-225507`、`…migrate-manifest-1790520911425.json` |
| 23:37:53 | `quick_restart`（第 2 次，setsid 修正版）让新进程 boot 时急切 `load()` 修复后的台账 | `state/quick-restart-request.json`、`state/quick-restart-result.json` |
| 23:38:04 | detached 作业在**旧进程已死、新进程未 load**的窗口内原子修复台账（备份→写→回读校验） | `.dsh-data/dsh-reqboard.json.pre-lock-repair-1790523484239`、[notes/ops-repair/README.md](notes/ops-repair/README.md) |
| 23:38:34 | 投递 workflow 链 `run-1790523514215-xbzxb90`（用户裁定「用 workflow 执行」） | `advance-log.md` |
| 23:42:27 → 24:00:01 | 4 张子卡逐张 `ok` → 父卡 `FINALIZE_PARENT` → `ROLLUP` 滚进验收 | `advance-log.md`（见 §五） |

**投产后台账事实**（python 读盘，2026-09-27 23:39~24:00）：`schemaVersion=9`、**无 `tasks` 键**、
`migrations=[{from:8,to:9,at:1790520911425,by:"migrate-ledger.ts"}]`、`requirements=82`；
`docs/requirements/*/queue.json` = **51 份 / 616 条任务**；需求 `status=accepting`，`advance.runId/lockAt` 已由 `finally` 清空。

---

## 二、验收 #5（看板不回归）的正面证据 —— 真实打开页面

| 轮次 | 产物 | 结果 | 时点 |
|---|---|---|---|
| 重启**前** | [notes/board-live/shots-before-restart/SUMMARY.json](notes/board-live/shots-before-restart/SUMMARY.json) + 4 张 PNG | **15 passed / 0 failed** | 23:19:34 |
| 重启**后**（投产实例） | [notes/board-live/shots-after-restart/SUMMARY.json](notes/board-live/shots-after-restart/SUMMARY.json) + 4 张 PNG | **15 passed / 0 failed** | 23:41:03 |
| 测试阶段独立复跑 | [notes/board-live/test-run/](notes/board-live/test-run/report.md)（`report.md` + 3 份 console log + `shots/`） | **15 passed / 0 failed**（另 探针 4/4、队列单测 131/131） | 23:59~24:00 |
| 联调契约 | [notes/board-live/integration-summary.json](notes/board-live/integration-summary.json)（+ `integration-record.md`） | **34~36 passed / 0 failed** | 23:49 / 23:57 |
| 复核 | `t-f4c9f5` 运行报告（`reqboard_task_status(t-f4c9f5)`）—— 独立复跑主证据 + 自建依赖探针 | 4 处偏离全部定性，**未发现实现层缺陷** | 23:58:27 |

**结构性计数逐项不变**（这是「不回归」的判据，不是单值相等）：
泳道 6 / 需求卡 34 / 列表 10 / 任务总览 **51 组 616 行** / 甘特 SVG 在场 / 需求详情 6 个 Tab / DAG **11 层** /
页面异常 0 / console.error 0 / 失败请求 0 / 接口 `tasks=616 requirements=82`；
漂移项（台账 rev、正文长度、甘特条数、详情任务行）均随**本链自身推进**变化，已逐条解释。

启动日志核验（`quick-restart.log` 最后一次启动段 28 行）：`LEDGER_REQUIRES_MIGRATION=0`、
`UnhandledPromiseRejection=0`、`uncaughtException=0`、`TypeError=0`；关键行
`Queue ready tasks: t-c130ca (requirement REQ-260927202051-f6df)` —— **boot 即从队列出 ready，非读台账 `tasks` 字段**。

**未以 `curl 200` 代替渲染验证**：断言取自 headless Chrome + CDP 真实加载后的 DOM
（`document.querySelector` 计数），并落 4 张真实渲染 PNG（复核另做去空白校验：非白像素 28%~44%）。
**边界**：复核方自陈「模型无图像输入，未做人眼视觉确认」——该残余项**如实保留**，不冒充已看。

---

## 三、施工期修掉的两处台账状态缺陷（均为既有缺陷，与 v9 迁移本身无关）

### 3.1 陈旧 `advance` 锁**没有回收路径** → 实测阻塞本需求续跑

- **现象**：`reqboard_task_run` 返回 `REQBOARD_DISPATCH_FAILED 该需求已有 run 在跑（runId=…）`，
  而同一 run 的 `reqboard_run_status` 报 **`jobStatus=not_found`**（后台 job 根本不存在）。
- **根因**：锁的**唯一**清理点是 `AdvanceChain.ts:365-378` 的 `finally`（进程被 `quick_restart` kill ⇒ 永不执行）；
  重投递判据 `AdvanceChain.ts:416` 只看 `advance.runId` 是否存在、**不看过期时间**
  （`:411` 的 `advanceLockStaleMs=15min` 只对 `lockAt` 提前返回 `locked` 生效，实测陈旧 27 分钟仍不放行）；
  且无第二条路：`ClearPause.ts:53-70` 只清 `dive.*`、`orphan-collector.ts:49` 是 `// TODO` 桩、HTTP `autorun` 走同一个 `deps.advance()`。
- **含义**：「失败即暂停，人工处置后再次调用本工具续跑」这条恢复路径**在进程被 kill 的场景下是死的**。
- **处置**：备份后原子写清 `advance.runId/lockAt`；脚本与原因见 [notes/ops-repair/](notes/ops-repair/README.md)。
  **第一次尝试失败并已留档**：等死作业与 dsh 同进程组被一并回收（日志只留 `armed`）⇒ 改 `start_new_session=True` 独立会话。

### 3.2 活台账**丢失 v8→v9 迁移留痕**

- **现象**：`migrate-ledger.ts --verify` 退出码 **1**，首条问题「migrations 末条不是 {from:8,to:9}：undefined」。
- **根因**：`--apply` 在 22:55 执行（留痕已写），但 22:58 才补上的 `load()` 保留逻辑
  （`JsonLedgerRepository.ts:150-168`）此前不存在 ⇒ 旧构建进程 `load()` 只重建 4 个字段，而**落盘的是整册 draft**
  ⇒ 第一次落盘即永久抹掉留痕。属**预存缺陷**，但会直接卡住本需求验收 #2。
- **处置**：从 `migrate-manifest-1790520911425.json` 补回 `{from:8,to:9,at,by}`；
  现 `dist/index.mjs` 已含保留逻辑 —— **本进程 boot 落盘后留痕仍在，实测证明补回可持续**。

### 3.3 本需求读方改造遗留的**陈旧测试调用点**（自查发现，已修）

- **现象**：定向回归套首跑 **22 files / 220 tests**（原始输出 `notes/board-live/targeted-suite.console.log`），
  3 条红全部在 `packages/web/dsh-pmboard/tests/advance-agent-handle.test.ts`，
  错误 `Cannot read properties of undefined (reading 'find')`。
- **根因**：本需求给 `ensureAgentHandle` 加了第 5 参 `tasks`（任务改从队列取，`LedgerView.tasks` 随 v9 移除），
  该文件（属 D14 / REQ-260927123256-196b）仍按 4 参调用 ⇒ 第 5 参为 `undefined` ⇒ `tasks.find` 抛错。
- **影响面**：**生产无缺陷** —— 唯一生产调用点 `packages/web/dsh-pmboard/src/application/use-cases/ExecuteTask.ts:171`
  已正确传 `queueTasks`；仅测试夹具未适配。
- **处置**：补齐夹具第 5 参（**测试侧改动，不改生产语义**）；复跑
  **23 files / 223 tests 全 passed，EXIT=0**（`notes/board-live/targeted-suite-after-fix.console.log`）。
- **口径更正（重要）**：`verification-evidence.md` §11.5 曾断言「本需求引入且未修的红 = 0」。
  该断言在其**当时的运行集**内成立，但**漏了本文件**（未纳入那次运行）。以本节为准：
  本需求引入的红是 **3 条**，**已修并留证**，且已补进覆盖声明（`tests/test-evidence.md` §7 的 TC-9）。

---

## 四、⚠️ 待人工裁决的「判据文本」问题（不影响实现，但影响**字面**达标）

| # | 问题 | 实测 | 建议裁决 |
|---|---|---|---|
| 1 | 卡内验收① 字面命令 `curl -s localhost:13080/dashboard \| grep -c pmboard` 命中 **0** | `GET /dashboard` → **404**（dsh web 的**客户端 hash 路由**，服务端无此 path）；等价判据 `GET /` → **200** 且 `pmboard` 命中 **5** | 改验收①文本为 `GET /` 口径（推荐）；或**属新工作**：服务端补 `/dashboard` 路由 |
| 2 | 整体验收标准 #3「`--verify` 无差异（幂等），退出码 0」 | 活台账**永远不为 0**：补回留痕后问题 **3 → 2** 项，剩余 2 项全是**迁移后运行期漂移**（本需求 queue.json 因链推进而变；台账因评论/autoRun/artifact 而变 —— 脚本只归一化 `migrations[].at`）。纯净副本口径下实测 **exit 0**（见 `verification-evidence.md` §一#3） | 按「**apply 后未被运行期改动的纯净副本**」口径取证；或接受活台账的已解释漂移 |
| 3 | 设计文本 TC-10.2 要求「**依赖连线**」 | 甘特 SVG 内**无任何 edge 图元**（只有 grid/mile/bar/now）；依赖实际由**任务表依赖列**（`.dsh-pm-tdeps` 616 格 / 492 非空 / 值为真实依赖 id）与**需求详情 DAG 11 层**承载；且 `decomposition.md:172`「本轮不做」明列「队列 DAG 图形 UI」 | 改设计文本为「依赖信息可见（依赖列 / DAG 分层）」——**不改实现** |

---

## 五、链收尾事实（可直接复核）

```text
$ tail -6 docs/requirements/REQ-260927202051-f6df/advance-log.md
- 2026-09-27T15:42:27.347Z [RUN_SUBTASK] parent=t-e77b06 subtask=t-c130ca  ok：子卡 t-c130ca 执行完成
- 2026-09-27T15:53:42.069Z [RUN_SUBTASK] parent=t-e77b06 subtask=t-6df9a0  ok：子卡 t-6df9a0 执行完成
- 2026-09-27T15:58:27.399Z [RUN_SUBTASK] parent=t-e77b06 subtask=t-f4c9f5  ok：子卡 t-f4c9f5 执行完成
- 2026-09-27T16:00:01.407Z [RUN_SUBTASK] parent=t-e77b06 subtask=t-10122a ok：子卡 t-10122a 执行完成
- 2026-09-27T16:00:01.603Z [FINALIZE_PARENT] parent=t-e77b06 ok：父卡 t-e77b06 汇总子卡产出并收尾
- 2026-09-27T16:00:03.498Z [ROLLUP] ok：需求已全部任务完成，滚进验收
```

---

## 六、观测面记录（如实登记，不属本需求范围）

1. **workflow 路径不写子卡卡文档**：`docs/…/tasks/t-c130ca.md`、`t-6df9a0.md`、`t-f4c9f5.md`、`t-10122a.md` **未生成**；
   报告只落在 run 记录（`reqboard_task_status` 可读）。本次 4 张子卡产出因此改落 `notes/board-live/`（研发/联调/测试）与 run 值（复核）。
2. **boot 自动续跑抢在窗口上线之前**：23:38:07 新进程 boot 时链自动续跑一次，报「绑定窗口不在线」→ 自动暂停（`autoRun=false`）；
   由绑定窗口重新 `reqboard_task_run` 后正常。**报错文本本身写明了处置办法**（设计如此），但该竞态值得后续收敛。
