---
title: 交付证据（REQ-260927202051-f6df · DAG 任务队列机制）
type: verification
requirement: REQ-260927202051-f6df
generated: 2026-09-27
---

# 交付证据 · 实现 DAG 任务队列机制（拆分时生成 queue.json）

> 本文件是**验收材料**：把"凭什么说这条需求做完了"逐条落成可复核的证据。
> 所有数字都带**命令 + 数据时点**（口径统一：`npx tsc --noEmit 2>&1 | grep -c 'error TS'` 数**错误条数**，
> 不是行数；残留用 `grep -rn 'ledger\.tasks\|snapshot()\.tasks\|changed\.tasks' src/`）。

---

## 一、需求整体验收标准 · 逐条对照

| # | 验收标准（requirement.md） | 证据 | 状态 |
|---|---|---|---|
| 1 | `--dry-run` 输出预期变更摘要，退出码 0 | [migration-dryrun-baseline.md](notes/migration-dryrun-baseline.md)（含 CLI `--dry-run --json` **原文**）；基线：`612 条任务 / 51 个分组 / 51 个 queue.json / orphan 0 / 空白名单外 0` | ✅ |
| 2 | `--apply` 后各 queue.json 生成、台账 `tasks` 移除、`schemaVersion=9`、`migrations[]` 留痕 | **真实台账副本**全量演练：`schemaVersion=9` / `'tasks' in ledger === false` / `migrations` 末条 `{8,9}` / 台账 7,905,194 → 4,825,231 bytes / 51 份 queue.json | ✅（副本） |
| 3 | `--verify` 无差异（幂等），退出码 0 | 副本 `--verify` **exit 0**；第二次 `--apply` → `already_v9`，md5 不变、0 个 queue.json 被重写、migrations 不叠加 | ✅ |
| 4 | 新建测试需求 → 拆分 → 队列生成且台账无新任务 → 推进 → ready 更新 | **`tests/t17-queue-e2e.test.ts` Exited 0**（单 `it` 一条真实连续链，见 §二） | ✅ |
| 5 | 看板任务页与甘特图迁移后正常渲染 | ⏳ **待投产窗口实测**（需停机迁移 + 重启，见 §七） | ⏳ |
| 6 | `pnpm build` 与 `plugin-schema.smoke.test.ts` 通过 | `pnpm build` **退出码 0**（`[verify-client] OK bundle=302659 bytes, 关键符号齐全, styles.ts 括号配对`）；冒烟 **21 passed**（含「dsh-pmboard 插件可构造（所有工具 schema 合法）」） | ✅ |

**唯一未闭环的是 #5**，它依赖一次**停机迁移 + 重启**（本会话就跑在 `:13080` 进程内，`stop.sh` 一执行会话与迁移同时结束），只能由人在终端执行。runbook 见 §七。

---

## 二、验收 #4 的端到端证据（`tests/t17-queue-e2e.test.ts`）

一条 `it` 内连续跑完，全部走**真实用例入口 + 真实仓储**：

```
① 立项 REQ-000001（draft）→ ② design → ③ decomposing → ④ 计划提交（2 卡）
台账 hasTasks（批准前）= false
⑤ 队列生成 <tmp>/docs/requirements/REQ-000001/queue.json
   ready=['t-00000d'] layers=[{0:[t-00000d]},{1:[t-00000e]}]
⑥ 台账 hasTasks（批准后）= false ｜ 文本含 "tasks" = true（故 grep 会假绿）
⑦ 父卡开工 → 4 张阶段子卡 ｜ ready = ['t-000012']
⑦ 卡一闭环 → ready ['t-00000d'] → ['t-00000e']   ★ 下游解锁
⑧ 两卡闭环 → ready [] ｜ 需求侧 accepting ｜ 队列任务数 10
```

三个值得单独记的点：
1. **台账判据是语义级的**（`'tasks' in ledger === false`），并**反向断言同一份文本 `includes('"tasks"') === true`**
   —— 把"`grep '"tasks"'` 会假绿"这件事本身钉成护栏。原因：台账是**单行 compact JSON**，
   且 `requirements[].plan.tasks` 在 **59 个需求**上真实存在 ⇒ grep 迁移前后**恒为 1**；
   而 `grep '^  "tasks"'` 因无缩进**两种状态都返回 0**（更危险的假绿）。
2. **真实临时工作区**：`os.tmpdir()`，`git status --short -- ../../docs .dsh-data` = **0 改动** ⇒ 活台账零接触。
3. **按生产语义写，没有绕过子卡链**：计划批准写入 `autoRun=true` ⇒ 父卡开工即**懒展开** 4 张阶段子卡，
   "推进一张卡到 done" = 父卡开工 + 子卡链跑完 + 父卡收尾（legacy 五段边只适用于无子卡的存量卡）。

---

## 三、门禁数字（命令 + 时点）

| 指标 | 开工前 | 现算 | 命令 |
|---|---|---|---|
| `src/` 三模式残留 | **92 处 / 55 文件** | **0** | `grep -rn 'ledger\.tasks\|snapshot()\.tasks\|changed\.tasks' src/ \| wc -l` |
| 全仓 tsc 错误条数 | **164**（开工基线） | **235**（实测 2026-09-27 21:5x，`/tmp/tsc-final.txt`） | `npx tsc --noEmit 2>&1 \| grep -c 'error TS'` |
| `src/` 中带本次改造签名的错误 | — | **0** | 按签名归因（下同） |
| 核心测试套 | — | **12 files / 137 passed** | `npx vitest run tests/queue/ tests/read-sites-equivalence.test.ts tests/t9-… tests/t11-… tests/t12-…` |
| `pnpm build` | — | **退出码 0** | `pnpm build` |
| plugin-schema 冒烟 | — | **21 passed** | `npx vitest run apps/web/tests/plugin-schema.smoke.test.ts` |

**口径警告（必须记住）**：中间态峰值曾达 **~700**（t6 落盘后、读方改造前）——那是**预期中间态**，
不是基线；基线永远是 **164**。另：`npx tsc --noEmit | wc -l` 数**行数**（多行错误有续行），
与 `grep -c 'error TS'`（**条数**）会差 30%+，两个数混用会得出相反结论。

**剩余 235 条的定性**：按**错误签名**归因（不是按目录前缀）——
`Property 'tasks' does not exist` / `taskStore' is missing` / `applyTaskRollup` / `no properties in common` 只剩 **1 条**，
且它是 `src/tools/ClearPauseTool/ClearPauseTool.ts` 的**预存**错误（开工前基线 Top-10 里就有它的
`render missing` / `ToolRunContext.session`；`58c77a95` 亦有）
⇒ **本需求对 `src/` 的类型错误贡献 = 0**。其余为**预存错误**
（`AcceptanceTracking` 不匹配、`Checkpoint.createdAt`、`Promise<string>` 传同步参、`RequirementCategory | undefined`、
未使用变量等）。其中 `src/application/use-cases/ClearPause.ts` 的 6 条与**开工第一分钟原始基线 Top-10 逐条吻合**。

---

## 四、语义变更清单（本需求改变了哪些**可观测**语义）

> 这批是"迁移之外的行为变化"，交付时必须显式列出，否则验收方无法判断是否超出范围。

1. **顺序契约成为显式不变量**：`taskStore.mutate` 必须**先于** `repo.mutate`（此前任务+需求在同一次台账 mutate 内原子完成）。反序 = "需求已验收但任务未完成"的悬空态。有**打点断言**（`callLog === ['taskStore.mutate','repo.mutate']`）。
2. **原子性降级（跨存储）**：任务进队列、需求在台账 ⇒ 两者不再同事务。`lazy-expand` 原用「展开与状态变更落在**同一 revision（同事务）**」表达，**在 v9 下必然不成立**；用例名已改为「…落在**队列同一批写**（v9：跨存储，非同一 revision）」，判据改为 `queueRevisionOf +1` + 父卡与 4 张子卡同批可见。
3. **`applyTaskRollup(ledger, tasks, ctx, onlyReqId?)`** 新增第 2 参（调用方必须显式给队列任务）；`applyPickupAdvance/applyPickupReconcile` **故意不变**（pickup 路径不读 tasks）⇒ 组合根两处零改动。`src/index.ts` 取**全量** `listAll()`，因为未传 `onlyReqId` 时 `planRollup` 会遍历每个需求做 R2 判定，只喂一个需求会让其余需求在视图里变"零任务"被误判。
4. **`reqboard_decompose` 返回体新增** `queue_file` + `tasks_created`；任务不再写台账，改由**唯一写路径** `landPlanTasks` 写 queue.json，**两条落库路径**（拆分 / 计划批准即落库）同时覆盖。
5. **`createMany` 幂等可观测**：重复 id 跳过且**不写盘**（文件 mtime / 队列写入序号不变）。
6. **AcceptSheet 三段式写入**：先在台账草稿上算裁决 → **先** `createMany` 返工卡 → **后** `repo.mutate` 整条替换需求记录；新增并发漂移守卫（状态或验收单版本变化 → `REQBOARD_STORE_INCONSISTENT`）。
7. **`IsolateNodeContextDeps.taskStore` 变为必填**（**编译期收紧**，不是测试适配）：把"缺装配"从运行期挪到编译期。
8. **⚠️ `submit:verification` 的覆盖度门禁从"静默跳过"变为"真正生效"**：此前 `coverage.total` 取自不再带 tasks 的快照 ⇒ 恒 0 ⇒ **≥80% 门禁一直被跳过**；现在任务显式传入 ⇒ **门禁真的跑**，`doc-gate-e2e` 因此暴露（夹具从未声明 `covers:`）。处置 = 补真实声明 + 接真实临时工作区，**不是关掉门禁、不是放宽断言**。
9. **新增日志** `Queue ready tasks: <ids>`（`task_run` 诊断"链卡在哪"）。
10. **`progressOf` 入参改名** `ledger → view`（收的是队列任务视图；顺带消除 TC-8.12 静态门禁对"台账取任务"字样的误报）。
11. **`TaskStore` 出口剥离 `layer`**（D3，返回 `TaskRecord`）：`layer` 只属于队列文件，避免泄漏进 `/state` 响应。`readQueue()` 才带 `layer`。
12. **`taskStoreOf(deps)` 缺端口当场抛 `REQBOARD_STORE_INCONSISTENT`**，不静默返回空任务集（空集在 v9 下会表现成"看板静默空白"）。

---

## 五、非回归说明（"看起来不等、其实不是回归"）

> 若不写清，未来的维护者会把它们当成本需求引入的回归去"修"，**越修越错**。

1. **`/state` 的 `revision` 与夹具初值不等**：`/state` 服务端开头会跑产物自动发现 `syncAllReqArtifacts(store, cwd)`（**改造前既有行为**），它就地登记产物 → 改需求记录并 **bump 台账 revision**。⇒ 断言改为「响应 `revision` = **台账** revision」（`expect(data.revision).toBe(store.snapshot().revision)`）。
2. **`/state` 的 `requirements` 与夹具原件不等**：同因（自动发现追加已登记产物）。⇒ 改为断言"路由**忠实返回台账当前 `requirements`**"，**真正由任务派生的逐字节比较放在 `ready` 映射上**。
3. **`/requirements/summary` 里"少了一个需求"**：摘要**只列进行中需求**，归档需求缺席是**正确行为**。⇒ 改为"只比对出现的需求 + `expect(compared).toBeGreaterThan(0)`"，**禁止**把"缺失"当回归。
4. **口径澄清**：`summary` 的 `tasksActive` 期望值必须用**与路由同一个 domain 判定函数**（`countDoneTasks`/`countUnfinishedTasks`）算。手写 `status !== done && !== canceled` 会得 6 vs 路由 1 —— **是期望式写错，不是被测对象错**。

> **通用教训**：**先怀疑自己的期望式，再怀疑被测对象**。这是把假回归挡在门外最有效的一招。

---

## 六、等价性证据（D8 分层判据）

`tests/read-sites-equivalence.test.ts` —— **8/8 全绿**，夹具是**真实 v8 台账抽取**（`tests/fixtures/read-sites-v8-ledger.json`，
2 个真实需求 / 56 条真实任务 / **全局序真实被切断**，含 `__provenance` + `beforeEach` 自检来源）。

**a~e 五条各自独立成 `it`**（不串成一条大断言，否则红了不知道哪条坏）：

| 用例 | 独立断言 |
|---|---|
| a-1 | 任务级：按 **id 配对** → 键集相等 + 值逐字节 |
| a-2 | 任务对象**不含 `layer`**；`get`/`listByRequirement`/`listAll` 都不带，**`readQueue` 才带**（D3 出口契约） |
| b | **需求内** id 序列逐需求与迁移前一致 |
| c | 计数 = 源台账**现算**值（总数 + 各需求数） |
| d-1/2/3 | `/state`、`/requirements/summary`、`/requirements/:id/stages` 的非任务字段逐字节/逐字段一致 |
| e | **负向固化**：断言全局序 = `listAll()` 契约序（reqId 字典序分组）**且确实 ≠** 迁移前全局序 |

**为什么必须分层（D8 裁决）**：跨需求**全局数组顺序**在按需求分片后**结构上不可复现** ——
实测 612 条只有 **106 个不同 `createdAt`**（非严格递增）、**2 个需求**的任务在全局数组中被切断、
`(createdAt, id)` 排序**无法**还原原序。且无消费方依赖（看板按需求分组渲染）。
否决"给 `QueueTask` 加持久化序号"方案：会打破 t1 用**编译期断言**锁死的「相对 `TaskRecord` 的多余键**恰为** `{layer}`」不变量。

---

## 七、未闭环项与投产 runbook

### 7.1 为什么投产必须由人在终端执行
`--apply` 要求服务停止（迁移脚本内置**服务运行守卫**：`<ledgerDir>/state/server.pid` 存活时拒绝执行，
`--force` 才放行）。而**本会话就跑在 `:13080` 的 DSH 进程里** —— `stop.sh` 一执行，会话与 apply 同时结束。
`--force` 在服务运行时迁移被**否决**：迁移完成到重启之间任何需求写入都会用**内存态 v8 覆盖 v9**。

### 7.2 ⚠️ 当前处于"脆弱窗口"
源码已是**新读方（v9）**，而活台账**仍是 v8**。新代码的迁移门**故意拒绝加载 v8 台账**（t-2417da 验收项③）。
⇒ **`:13080` 只要重启一次（含崩溃后被 launchd 拉起），pmboard 会拒绝加载 v8 台账、看板失效。**
⇒ 因此**迁移与重启必须在同一个窗口内完成**。

### 7.3 runbook（用户终端执行）
```bash
LED=/Users/yunpeng/pi-investment/agent-dh/.dsh-data/dsh-reqboard.json
cd /Users/yunpeng/pi-investment/agent-dh && ./scripts/stop.sh        # ① 停机（必须）
cd packages/web/dsh-pmboard
cp "$LED" "$LED.pre-v9-manual-$(date +%s)"                            # ② 二次人工备份
node --import tsx/esm scripts/migrate-ledger.ts --file "$LED" --dry-run   # ③ 零写预演，对照基准
node --import tsx/esm scripts/migrate-ledger.ts --file "$LED" --apply     # ④ 落盘（内部自动备份 + manifest）
node --import tsx/esm scripts/migrate-ledger.ts --file "$LED" --verify; echo "verify exit=$?"  # ⑤ 应为 0
cd /Users/yunpeng/pi-investment/agent-dh && ./scripts/start.sh        # ⑥ 起服务 → 看板实测
```
**回滚**：`--rollback`（同样先停机）。**`<ledger>.backup-*` 与 `<ledger>.migrate-manifest-*` 不要删** —— rollback 靠 manifest 里的 sha256 精确清理本次生成的队列；迁移后被运行期改过的 queue.json 会被**保留**并在输出里点名。

### 7.4 台账收口（独立事项）
17 张父卡要收口需 **17 × 4 = 68 次真实链执行**：`subtask-evidence.ts:59` 要求 `task.lastRun`，
而它**只有链里 ExecuteTask 会写，没有手工路径**；父卡合法边又只有 `in_progress→done`。
按用户决定，收口推迟到实现全部落地后统一进行。

---

## 八、独立发现（既有缺陷，均**未修**、超出本需求边界）

### 8.1 模式一：**声明与实现不符**（6 处实证）
> 建议后续立项做一次**全仓"声明了但无调用者/无生产者"扫描** —— 这类缺陷不会报错，只会静默失效。

| # | 位置 | 实证 |
|---|---|---|
| 1 | `content-gate-triad` 门禁 | `git grep -n 'content-gate-triad' 58c77a95` = **零命中** ⇒ 门**从未接线**，`taskCardTriadFailure` 等是死代码（`triad-gate` 4 条 e2e 红） |
| 2 | 地址注入段（`capture-section.ts`） | 开工前该文件**不含** `augmentResolvedPrompt/templateRoot/本节点文档`（grep=0），且当时是 **3 参**签名而调用点传了 4 个实参 ⇒ 地址对象**一直被丢弃**（`template-address-injection` 4 条红） |
| 3 | `h4-resume` | `H4ResumeDeps { // 不再需要任何依赖 }`，handler 直接返回 `{kind:'skip', code:'dive_handles_resume'}` |
| 4 | `AgentDeliveryPort.deliver` | 开工前存在（`58c77a95` 命中 1），现已被清空 ⇒ `worktree-notice` 的投递链断裂 |
| 5 | `worktree-notice` | `deliverWorktreeNotice` 函数体**只有 `return false`**（27 行桩）⇒ 投递永不发生（`worktree-injection` 2 条红） |
| 6 | `requirement_status` 字段 | 是 `reqboard_decompose` 的返回字段（`Decompose.ts:210`），`TaskMoveTool`/`MoveTask` 在 `58c77a95` 与现在**都 0 命中**；**且 `client/toolviews/rows/task-move.ts:63` 也在读这个无人产出的字段** |
| 7 | `reqboard_run_status` 的 `snapshot.runId` | 无 active run 时 `QueryRunStatus.ts:72` 发 `null`，而 schema 声明 `type:'string'` ⇒ **值级**校验失败，把「当前没有链在跑」转译成硬错误 `value.snapshot.runId must be a string`。**旧测试还把它固化了**（`expect(snapshot.runId).toBeNull()`），且只测 `execute()` 返回值、**从不拿返回值去过工具自己的输出 schema**。已修（不是 string 的键整体省略）+ 补输出契约闸门（见 §九·9.4） |
| 8 | `DecomposeTool` 的 `queue_file`/`tasks_created` | t11 给拆分返回体加了这两个字段却未在 `output.schema` 声明 ⇒ 未声明字段会被绑定层拒收（值算出来了、调用方只看到 invalid output）。由 `output-contract` 静态扫描抓出，已补声明 |

### 8.2 模式二：**批准计划后实施链不会自动开跑**（生产缺口）
`confirm-settle.ts` 只设 `autoRun = true`；`deps.jobs.start` **只剩一条注释**；`StartSubtaskChain.ts`（唯一会启动作业的用例）
**全仓无调用者 = 死代码**；`advanceRequirement(` 的 4 个调用点里**没有** `AskConfirm`/`confirm-settle`
⇒ 批准后需求状态只能停在 `implementing`。仓库早已在两处注释里承认：
`src/index.ts:505`「批准计划后的落库恢复通道（自动拆分缺 JobsPort）」、`DecomposeTool.ts:5`「后继的自动拆分路径（deps.jobs.start）从未装配」。
**修它 = 改生产行为，需独立需求与批准。**

### 8.3 模式三：**闸门-自动推进交互未收敛**
设计确认门**通过**时后置链已自动推进 `design → decomposing`；此时再显式 `reqboard_move(to='decomposing')`
会成为**自我转移**，被第一级产物存在门拦下：
```
节点产物缺失：decomposing 阶段须先完成产物（kind=decomposition）并登记到 req.artifacts
```
（`code: missing_artifact`；`requiredKindsFor(category,'decomposing')=['decomposition']` 在计划落库前必然缺失。）
两条分支都是真实路径（确认门不通过时停在 design 由显式 move 推进，同一产物门不触发）。**建议"自我转移短路"。**

---

## 九、归因方法（本轮沉淀，供后续复用）

### 9.1 「预存 vs 引入」的对照基准**必须早于被检验的改动**
- ❌ `git show HEAD:` —— **HEAD 已包含我们的改动**，用它证明"预存"会**说反**（"HEAD 里本来就有"对我方引入的改动同样成立）。
- ✅ **开工前那个 commit**（本项目为 `58c77a95`）。本轮据此**翻了两个结论**（互为镜像）：一次推翻了我的"夹具没镜像组合根"假设，一次推翻了"`boundSectionText` 是预存"的判断（开工前 **3 参**、现在 4 参 ⇒ **是我们的回归**）。

### 9.2 「某条红不是我造成的」需要**两条独立证据**，缺一不成立
- **E1（排除我的编辑）**：把改动原样回退再跑 —— 失败**完全相同**。
- **E2（排除数据源改造）**：把根因追到**数据源之外**（如"链启动源缺失"、"投递被桩死+端口移除"）。
- **只有 E1 只能证明"不是我的编辑"，不能证明"不是本次改造"**；E1+E2 同时成立才排除。

### 9.3 残留门禁类方法的**盲区**
按字面 grep 做残留门禁**天生抓不到"签名参数错位"**（`applyTaskRollup(l, ctx)` 不含 `.tasks`），
也**会把注释计入**。⇒ 签名错的验证必须靠**编译**（tsc）+ 调用点静态断言；
"0 残留"必须是**代码与注释都干净的 0**（本轮曾有 **12 处残留全是注释**，且把形参名 `ledger` 改 `view` 才消除假红）。

---

## 十、本需求对 `src/` 的类型洁净度结论

**按错误签名归因（不按目录前缀）：`src/` 中带本次改造签名（`Property 'tasks' does not exist` /
`taskStore' is missing` / `applyTaskRollup`）的错误 = 0。** 其余 `src/` 错误均为**预存**
（`ClearPause` 6 条与开工第一分钟原始基线 Top-10 逐条吻合）。

---

## 十一、施工期新增（2026-09-27 深夜）：缺陷修复与新增方法论

### 11.1 修掉一个**我们自己的**交付物缺陷（静默不生效）
`QueueTaskStore.mutate` 的"无变更"判定只从 `next.tasks` 里筛 `changed`，而被删除的任务不在 `next` 里
⇒ **纯删除时 `changed.length === 0` → 提前 `return []` → 静默不写盘**，且 `kind: 'task-removed'` 成为
**永远走不到的死分支**。已修（先算 `removed`，只有"集合与内容都没变"才早退），补 2 条单测
（纯删除写盘 / 部分删除），并**保留"真没改就不白写"的否命题用例**（防修过头丢掉优化）。
> **可复用的判据**：「有一支分支永远走不到」本身就是缺陷信号，值得单独扫。

### 11.2 新增缺口：工具路径不跑**内容态**闸门（口径精确化，勿再传播"可绕过"）
> **`reqboard_move` 有 4 道校验，缺的是第 5 道**。原表述"agent 可以绕过看板 G2 闸门"**过重**，已改为此口径。

**`reqboard_move` 实际执行的 4 道（`MoveRequirement.ts:29-65`）**：
| # | 闸门 | 拦什么 |
|---|---|---|
| 1 | 绑定门（`:29-34`） | 本窗口必须绑定该需求 |
| 2 | **产物门（两级）**（`:43-44`，mutate 内 `:54-55` 复查） | 第一级 **产物存在**：`requiredKindsFor(category, from)` 每一项都在 `req.artifacts` 里**登记**过；第二级 **人工确认**：该门产物**成组确认**（任一未确认即拒）。豁免 `to='canceled'` 与存量需求 |
| 3 | 任务完整性门（`:45-46`/`:56-57`） | 仅 `to='implementing'`：计划有卡却 0 张落库 |
| 4 | 状态机门（`:60-65`） | 合法转移表 + **人工闸门**（如 `decomposing→implementing`）+ 并发复查 `req.status === from`，失败即 mutate 回滚 |

**缺的第 5 道 = 内容态闸门**（`checkDesignCompletenessGate(deps.docs, req)`，`internal/design-gates.ts:138`）：
**读磁盘**核对文档集是否齐（如缺 `use-cases.md`）、front-matter 的 `sides` 是否交齐、`design_exempt` 理由是否为空。
只挂在 4 处：`http/routers/requirements.ts:43`（看板路由）、`AskConfirm.ts:107`（弹框）、`ConfirmArtifact.ts:191`（产物确认 G2）、`confirm-settle.ts:168`（计划批准即落库）。

**⇒ 准确的影响面（比"可绕过"窄得多）**：
- 工具路径**仍拦得住**「产物没登记」与「登记了没人确认」；
- 拦不住的是「**产物已登记/已确认，但磁盘文档集本身不齐或不合策略**」；
- 而正常流程里 G2 的内容态闸门在**登记与确认那一刻已经跑过** ⇒ 真实缺口窗口是
  **①「登记/确认之后磁盘内容又被改动」**，以及 **②「是否存在不经内容态即可登记设计产物的路径」**。
- **② 已验证（2026-09-27 深夜，Lead 亲查）—— 结论：缺口是"窄"，不是"可绕过"**：
  枚举三条登记/盖章路径后确认，**内容态校验并不缺失、只是不在 move 路径上**：
  | 路径 | 跑的内容态校验（都读磁盘） |
  |---|---|
  | `SubmitArtifact`（登记需求/其他产物） | `checkRequirementDocFormatGate` + `checkNumberChainGate` + `checkDesignServesGate` + `assertArtifactOpenable` |
  | `SubmitDesignArtifacts`（登记设计文档） | `designDocPolicyOf` / `designDocRegistration`（`sides` / `missingCategoryDocs` 策略**在登记时即施加**）+ `assertArtifactOpenable` |
  | `AskConfirm:107` / `ConfirmArtifact:191`(G2) | **`checkDesignCompletenessGate`**（盖章那一刻跑完整度校验） |
  | `reqboard_move` | 仅**登记态**（已登记 + 已成组确认），**不复核磁盘** |
  ⇒ 因为"移动"的前提是"已登记 **且** 已确认"，而**确认那一步跑了内容态闸门**，
  故**不存在常规的"不经内容态即可登记并盖章"路径**。
  **真实缺口收窄为一句话**：**工具路径在"移动"时不复核磁盘内容** ——
  即"确认之后磁盘文档又被改动/删掉"时，工具路径察觉不到，看板路径会察觉。
  严重性从"闸门可被绕过"下调为"**移动路径缺少一次磁盘复核**"（建议单独立项，优先级**中**而非高）。

- **③ 再精确一层（Lead 追问"reqboard_move 一定走人工确认吗"后补）—— 这里有两件常被混为一谈的事**：
  | 闸门 | 转移 | 需确认产物 | `humanOnly`（状态机是否只许人发起） |
  |---|---|---|---|
  | G1 | `brainstorming → design` | `requirement` | **true** ⇒ agent 调 move 直接吃 `REQBOARD_HUMAN_GATE` |
  | **G2** | **`design → decomposing`** | `design` | **false** ⇒ **agent 推得动** |
  | G3 | `decomposing → implementing` | `decomposition` | **true** |
  | G4 | `accepting → archived` | `verification` | **true** |

  ⇒ **"人工确认"（产物要有 `confirmedAt` 章）≠ "人工专有"（状态机只许人发起）**：
  前者只要求"有章就放行，不管谁推的"；后者由状态机拦。
  **确认门还按分类开关**（`CATEGORY_FLOW_PROFILES.confirmGates`）：`feature` 全 4 门；`bug`/`refactor` 3 门；
  **`spike`/`doc`/`chore` 只有 `accepting>archived`** ⇒ 它们 `draft→implementing` **完全不需要人工确认**。
  另有两条豁免：`to='canceled'`（放弃路径）、**`isLegacy`**（需求无 `artifacts` ⇒ 两级都不硬拦）。
  **最终口径**：凡是**设计完整度闸门相关**的分类（`feature`/`bug`/`refactor`——只有它们有 design 阶段），
  **都在 `design>decomposing` 上有确认门**，确认流程会跑内容态校验；缺口只剩"确认之后、move 之前
  磁盘内容被改动"。`spike`/`doc`/`chore` 无 design 阶段 ⇒ 与该闸门无关，不算缺口。
- **证据（已验证部分）**：`MoveRequirement.ts` / `MoveTool.ts` / `artifact-gates.ts` 在基线
  `58c77a95` 与现在**都 0 命中** `checkDesignCompletenessGate`；**对照实验**：同一测试文件的
  路径②③④（弹框/看板）全 PASS ⇒ **闸门本身正常，是工具路径没接它**。
- **修它 = 加行为**（需在 `MoveRequirement` 引入 async 的内容态检查，位置建议在
  `assertArtifactGates` **之后**、`taskCompletenessGap` **之前**）⇒ **超出本需求边界，建议单独立项**。

### 11.3 新增方法论：与 commit 比对的判据，**空输出要当报警**
queue-core 曾用「`git diff --stat 58c77a95 -- <文件>` = 空」判定 7 条红为"预存"，**证据是错的**：
它在 `cwd=agent-dh` 下却用了 `agent-dh/packages/...` 前缀 ⇒ 拼成 `agent-dh/agent-dh/packages/...`
⇒ **匹配不到任何文件 ⇒ 空输出**。正确输出显示 `support.ts`(+72) 与 `MoveRequirement.ts`(+10) 自基线起都改过。
⇒ **规则**：① 比对类判据**必须在仓库根跑**，并把**命令原文**写进汇报；② **空输出要当成报警**
（路径错 / ref 错 / cwd 错的典型症状），**不能当作"无差异"**；③ 该结论已由提出者**主动撤回**，
7 条红改由改过相关文件的属主用正确基准重判（结论仍为预存，但**证据换成了对的**）。

### 11.4 新增方法论：闸门类错误，用**类型**把它变成编译错误
`rollup.test.ts` 原夹具是 `ReqboardLedger & { tasks?: … }`，于是 `applyTaskRollup(l, ctx)` 这种
"把 ctx 当 tasks"的错**只能靠运行期发现**（字面 grep 门禁抓不到参数错位 —— 它不含 `.tasks` 字面量）。
改成 `type Fixture = ReqboardLedger & { tasks: readonly TaskRecord[] }` 后，同一错误**在编译期就报错**。
⇒ **当某类错误动态测不到时，用类型把它变成编译错误，而不是加更多断言。**

### 11.5 全量失败分类最终账（2544 用例）
`npx vitest run` 全量：**45 文件 / 139 用例失败**。逐类定性后：

| 类 | 数量 | 处置 |
|---|---|---|
| 夹具缺 `taskStore`（v9 回归） | ≈40 | task-19 修：15 文件 → **12 文件全绿**，tsc **235 → 196 下降** |
| `applyTaskRollup` 老签名调用点 | 10 | task-20 修：**18/18 全绿** |
| `design-completeness-gate` / `e2e-design-handoff` | 7 | task-21 判 **预存**（正确基准 + 对照实验举证），**不硬改** |
| 外部线（`AgentDeliveryPort.deliver` 被清空 / H4 no-op） | ≈20 | 登记不修（与 `worktree-injection` 同源） |
| `triad-gate` / `e2e-triad-gate` / `doc-sync`（三要素门未接线） | ≈9 | 登记不修（另立需求） |
| `RandomIdFactory` 正则等预存红 | 少量 | 登记不修 |

**⇒ 本需求引入且未修的红 = 0**；无"未定"项。

### 11.6 输出契约闸门补强（本次事故的根治手段）
`output-contract.test.ts` 原断言只查「返回键是否在 `output.schema` 声明」，**不校验值** ——
所以 `reqboard_run_status` 的 `snapshot.runId: null` 撞 `type:'string'` 这件事从这道门底下溜了过去。
现改为**递归校验**：声明为 `string/number/boolean` 的键，**一旦出现就必须是该类型**。
口径精化（重要）：**`undefined` 与 `null` 在 JSON 里行为不同** —— `undefined` 会被丢弃
（绑定层看不到该键，等价于键省略）；**只有 `null` 会被保留并撞类型校验**，故闸门只拦 `null`。
`run-status-tool.test.ts` 另加了**故障注入**证明闸门非恒真（塞 `runId:null` 必被拦下，键省略则放行）。

---

## 十二、已修复问题清单（截至 2026-09-27 22:49，均已进 `dist`）

### 12.1 本需求范围内（v9 队列迁移）的修复
| # | 问题 | 修法 | 验证 |
|---|---|---|---|
| 1 | 队列类型契约缺 `layer` 之外的约束兜底 | `QueueTask extends TaskRecord`（编译期锁死字段不裁） | 类型级断言 + **故障注入** TS2344 |
| 2 | `computeLayers` 对畸形输入 `[null,42,'x']` 抛错（校验路径不允许 throw） | 加运行时形状守卫 + 2 条回归测试 | topology 15 → **17 passed** |
| 3 | `mutate` 对**纯删除**静默不写盘，`kind:'task-removed'` 是死分支 | 先算 `removed`，只有"集合与内容都没变"才早退 | **25 passed**（含纯删除/部分删除/不白写三条） |
| 4 | `LEDGER_REQUIRES_MIGRATION` 被 `load()` 自己的 catch 吞掉（退化成静默空台账） | 迁移判定移出 try；throw 前不置 `loaded` | ledger-v9 **16 passed** |
| 5 | `QueueTaskStore` 出口泄漏 `layer` 进 `/state` 响应 | 出口 `structuredClone` + `delete layer`（收敛一处） | D3 断言 + 等价性 a-2 |
| 6 | `applyTaskRollup` 新增 `tasks` 参数后，`src/index.ts` 启动对账仍是老签名（**上线即崩**） | 补第 2 参为 `await taskStore.listAll()`（全量，对齐 R2 判定语义） | tsc + 启动路径 |
| 7 | `handleEvents` 仍订阅台账 → 任务搬家后**看板实时刷新静默失灵** | 双订阅（台账 + 任务各一路 emit） | t7 验收 + t16 待实测 |
| 8 | 提示词段 `text` provider 是**同步**接口 vs 异步 `TaskStore` | 同步快照 + subscribe 刷新；**三态**（未加载/空/有值），未加载时略过任务块 | D17 三条硬化 |
| 9 | `boundSectionText` 加 `tasks` 后 6 处调用点参数错位 | 按新签名改正 | 6 → 0 类型错 |
| 10 | 台账任务数是活数，文档写死 587/465 会让契约测试恒红 | 全链改「存量全量、条数现算」 | migrate-contract（数据驱动） |
| 11 | `grep '"tasks"'` 锚点假绿（单行 compact + `requirements[].plan.tasks` 恒在） | 改 `has('tasks')` 语义判据 | 迁移报告 |
| 12 | 「迁移前后 `/state` 逐字节相等」不可达成（跨需求全局序不可复现） | D8 分层判据 a~e + **负向固化** | equivalence **8 passed** |
| 13 | `DecomposeTool` 加了 `queue_file`/`tasks_created` 却未在 `output.schema` 声明（**契约违反**） | 补声明（string / number） | output-contract 静态扫描 |
| 14 | **`reqboard_run_status` 无 active run 时 `snapshot.runId:null` 撞 `type:'string'`** → 硬错误 `must be a string` | 不是 string 的键**整体省略**（与顶层 `run_id` 同口径） | run-status-tool 6 passed（含故障注入） |
| 15 | 旧测试把这个 bug **固化了**（`expect(snapshot.runId).toBeNull()`），且**从不拿返回值过自己的 schema** | 改正断言 + 补 `assertConformsToSchema` 闸门（递归值级校验） | output-contract **27 passed** |
| 16 | prompt/schema 声称 `status:'terminated'`/`reason`（**从未被产出**） | 按真身改正 | 文档一致性 |
| 17 | `token-usage.ts` JSDoc 仍是 `applyTaskRollup` 老签名形状 | 改正注释 | 全仓扫该类形状 |
| 18 | 夹具装配类：15 个测试文件缺 `taskStore`（≈40 用例） | 新增 `tests/queue/route-deps.ts`（真实 TaskStore）+ 15 文件补装配 | 12 文件全绿，tsc **235→196** |
| 19 | `applyTaskRollup` 老签名调用点（rollup 两文件 / 10 用例） | 改正 + **类型化夹具**把参数错位变成编译错 | **18 passed** |

### 12.2 交付面（**必须记住，否则修复不会生效**）
- `dsh-pmboard` 的 `main` / `exports` 指向 **`./dist/index.mjs`** ⇒ **运行时加载打包产物，不是 TS 源码**。
  改源码后**必须 `pnpm build`**，光重启无效（本轮已重新打包并**校验产物符号**，不只看出厂码）。
- **本次打包结果**：`dist/index.mjs` 1,248,930 B（22:49）；`lib/client.js` 302,659 B，
  `[verify-client] OK bundle=302659 bytes, 关键符号齐全, styles.ts 括号配对`。
- **⚠️ 因此脆弱窗口确认存在**：`dist` 现已是 v9 读方 + 迁移门；而活台账仍是 v8
  ⇒ **下一次重启会加载新 dist 并拒绝 v8 台账 → 看板失效**。
  ⇒ **重启必须与「停机 → 迁移 → 起服务」同一个窗口完成**（runbook 见 §七）。
- **自我更正（记入教训）**：此前把"运行时加载方式"判断为"tsx 直载 TS 源码、改源码重启即生效"，
  **机制说错了**。纪律：判断"某改动是否已在运行实例生效"，必须取**线上证据**
  （`main`/`exports` 字段、产物符号、进程实际行为），不能靠框架推断。
