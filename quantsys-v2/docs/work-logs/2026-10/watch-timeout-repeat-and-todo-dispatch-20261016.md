# 盯盘超时回执复读 + 「待办 → agent」断链（2026-10-16）

**日期**: 2026-10-16
**触发**: 用户提问 —— 「盯盘回执 · 超时回执 是什么情况？」，以及随后的追问
「我理解这个应该交给 agent 来处理才对呀，你现在需要人来处理吗？」
**结论一句话**: 两笔账——① 超时回执每 30 分钟复读一次（当天实发 95 条）是今天新引入的回归；
② 更根本的是**待办从来没有被派给 owner agent**，agent 全程不知情，卡片成了唯一出口。

---

## 一、现场取证（2026-10-16 生产库 + launchd 日志）

| 项 | 实测 |
|---|---|
| 当天 `timeout` 回执实发 | **95 条**（P0 1 / P1 79 / P2 15）；其中归属用户 20、归属 agent 75 |
| 当天 `escalate` 回执 | 30 条，全在 16:10–16:12（20:59 重启**前**的旧代码；重启后 `escalated` 恒 0 ✅） |
| 复读主体 | `watch_todos` #79–91：13 条 P1 `rule_change` 待办，18:05:58 由规则自愈（R6 单日触发≥3 次）一批建出，**建时即 L3** |
| 复读节奏 | 18:36 / 19:06 / 19:36 / 20:06 / 21:00 / 21:06 —— **每 30 分钟一张 13 行聚合卡** |
| 静默的那批 | 另 48 条超期待办每轮 `duplicates=48`（幂等跳过），故只有这 13 条在刷 |
| agent 侧 | 17:00 之后**零条**摘要唤醒（`watch_engine.digest_service`）；建单的三个服务（自愈/元评审/补全）代码里 `notify`/`wake`/`facade` 零命中 |

## 二、根因

### ① 复读：due_at 是幂等键的一部分，却被超时分支顺延

```
payload_digest(kind, todo_id, period)          receipt_service.py:86-114
        period = f'{tag}|{due_at.isoformat()}' ← due_at 进幂等键
WatchSlaJob._escalate_to_user → promote(...)   watch_sla_job.py（超时 bump 复用 promote 只为 +1 计数）
promote(extend_due_minutes=30) → due_at += 30min   watch_todo_repository.py:174,187-188（本日 4f2a 新增）
```
⇒ 每发一次卡，`due_at` 就前移 30 分钟 → 幂等键轮换 → 30 分钟后重新命中 overdue → 再发一张，
**永不收敛**。设计意图是「超时回执每待办 1 张」（`REQ-261016155500-4f2a` §3.1/§5.1），
验收判据也是 `timeout_sent ≤ 10`（`tools/validate_watch_upgrade.py`），当天 95 条必然判红。
旁证：HEAD 版本的 `promote` **没有** `extend_due_minutes` 参数，10:58 的 P0 待办（#63）在旧代码下
只发过 1 张——顺延是今天新引入的行为。

### ② 断链：待办没有送达 owner agent 的通道

- 自愈/元评审/补全三个派单服务建完待办就结束，**不通知 owner**（grep 零命中）；
- agent 的唤醒入口只有两条：L2/escalated 触发的 wake（这些待办 `trigger_id` 为空，不触发）、
  盯盘摘要唤醒（`digest_service.py:90` 只读 `trigger_repo.list_triggers`，**不读待办表**）；
- 唯一在动的出口是「超时回执发给你」——把 agent 的活推给了人，还掩盖了断链本身。

## 三、修复（本次改动）

| # | 改动 | 文件 | 可失败性 |
|---|---|---|---|
| ① | 超时 bump 显式 `extend_due_minutes=0`（due_at 不再轮换 → 一条待办一张卡） | `adapters/inbound/fastapi_app/watch_sla_job.py` | `test_l3_timeout_does_not_rotate_due_at_no_repeat_every_30min`（时钟 +31min 必须仍是 duplicates） |
| ②a | 建单即派单：`TodoService.create` 对 **trigger_id 为空 + owner_kind=agent** 的待办唤醒 owner；派单失败不打挂建单 | `application/services/watch_engine/todo_service.py` | `tests/application/test_todo_service.py` 5 条（含 trigger 路径不双唤醒、user 归属不误投） |
| ②b | 超时升级按归属分流：agent 自有 → 唤醒 owner（`watch_todo_timeout`）；wake 未送达时 **P0/P1 折进本轮同一张卡**（绝不静默丢，也不按条炸卡） | `receipt_service.py` / `watch_channels.py` | `tests/application/test_sla_job.py` 6 条 + `tests/watch/test_receipt_grouping.py` 3 条 + `tests/watch/test_todo_owner_wake.py` 6 条 |
| ②c | 公开唤醒入口 `NotificationFacade.wake_agent(event, data, target_agent)`（`_attempt_wake` 支持自定义 event） | `application/notification/notification_facade.py` | `tests/notification/*` 既有 234 条不破 |
| — | 装配接线（`assigner` / `agent_waker` 只在生产装配里注入，缺省 None = 行为与改前一致） | `watch_loop_wiring.py` | 单测全部显式注入，缺省路径单测覆盖 |
| — | 验收工具 ③ 判据改为「**归属用户**的超时实发 ≤10」（agent 自有的 wake 不再误伤门槛） | `tools/validate_watch_upgrade.py` | 直接 SQL 复核（当日用户侧 20 条） |
| — | `group_cards` 改记**实发卡数**（`card_count`）：私信唤醒占满一轮时用户 0 张卡 | `watch_sla_job.py` | 同上 |

**唤醒载荷**（agent-dh 的 `/wake` 只要求 `event` 非空，JSON 原样交给 agent）：
`todo_id / symbol / level / flow_state / action_kind / rule_id / account / owner_ref /
due_at / escalate_count / message / instruction`。
`instruction` 写清收敛契约：先落决策审计拿 `decision_audit_id`，再
`POST /api/watch/todos/{id}/close`（`terminal`/`close_reason`/`action_kind`，
`ignored` 必带 `next_condition`，L3+rule_change 必带审计）——判不动就 `ignored` + NEXT。

## 四、生产验证（2026-10-16 21:26 / 21:40 两次 kickstart 后实测）

**第一次部署（21:26）→ 21:36 那一轮**（13 条工单的 due 21:35:58 到点）：

```
21:36:05-09 watch_channels  待办超时唤醒未送达，退回盯盘群卡片  wake_status=error  ← agent-dh(:13080) 未监听
21:36:10 watch_sla_job  到期巡检完成  scanned=61 timeout=13 duplicates=48
                                    group_cards=1 agent_wakes=10 alerts=13
21:37:05 watch_sla_job  到期巡检完成  scanned=61 timeout=0 duplicates=61 group_cards=0
```
- ✅ ① 生效：21:37 起 61 条全部幂等跳过，**复读停止**；`due_at` 冻结在 21:35:58、`escalate_count` 6→7（只加一次）。
- ❌ 同时暴露一个**新缺陷（当场修掉）**：agent 唤醒失败时按条兜底 → 一轮炸出 10 张单条卡
  （外加 3 条用户卡），比改前更吵。改为**聚合轮内折进同一张卡**（`flush_grouped` 先私信唤醒，
  成功者不进卡、失败者 P0/P1 合并成一行），并加 `group_cards=0` 的"私信占满一轮"用例钉死。

**第二次部署（21:40，含上述收口）**：
```
21:40:21 watch_sla_job  到期巡检完成  scanned=61 timeout=0 duplicates=61 group_cards=0 agent_wakes=0
```
`PID 33058` / `/api/health 200`；此后只要没人关闭或改 due，不会再有任何超时卡。

## 五、追加：wake 候选链互备（2026-10-16 22:00，用户裁定"agent-ts 也可以做"）

**用户提问**：「是不是 agent-dh 没有处理他们的工具？这个不只是给 agent-dh，agent-ts 也可以做。」

**核实结论（三个独立缺口，本次只补第 2 个）**：

| # | 缺口 | 取证 |
|---|---|---|
| 1 | **能力缺口：两个 agent 都没有"处置待办"的工具** | 共享客户端 `quantsys-v2-client` 只有 `listWatchRules`/`listWatchTriggers`（client.ts:877/893），**无任何 todo 方法**；agent-dh 工具集只有 `watch_list`/`watch_manage`/`market_alert`；agent-ts 的 `monitor/` 只有 `alert-tool`/`watch-manage-tool`。故 wake 载荷里的「POST /api/watch/todos/{id}/close」目前对两侧都是空话 |
| 2 | **路由缺口：只认 agent-dh，agent-ts 在线也用不上** | `DEFAULT_AGENT_BY_ACCOUNT` 四账户全 → agent-dh；`.env` 只覆盖 `user_main_simulation→agent-ts`；旧回退 `if status == 'error' and key != DEFAULT_TARGET` —— **目标就是默认 agent 时没有回退**（agent_notification_service.py 旧版） |
| 3 | **在线缺口：两个 agent 都没监听** | 21:36 实测 13080/3002 均无 LISTEN（只有 agent-os 8080、v2 5001）→ 任何路由都投不出去 |

**本次改动（缺口 2，v2 内完成）**：
`AgentNotificationService.candidate_chain()` + `_deliver_chain()` —— 按候选链依次尝试，
默认 **agent-dh ⇄ agent-ts 互为备份**（可配 `WATCH_AGENT_FALLBACKS='agent-ts,agent-dh'`），
回退成功时在 payload 标注 `delivery_target / delivery_fallback_from /
delivery_fallback_reason / delivery_fallback_hops`；**首个候选 'timeout' 不换人**
（"大概率已送达"，换人 = 重复处置风险）；全链失败记 `attempts` 台账并如实返回 error。

**生产实测（21:54，两 agent 都离线）**：
```
候选链候选不可达，尝试下一个  target=agent-dh status=error remaining=['agent-ts']
候选链候选不可达，尝试下一个  target=agent-ts status=error remaining=[]      ← 互备链在跑
候选链全部候选失败（事件未送达） attempts=[dh:error, ts:error]
```
（agent-ts 一旦起来，同一路径即改为送达 agent-ts，无需再改代码。）

测试：`tests/application/test_agent_wake_fallback_chain.py` 7 条（含"默认 agent 挂 → 送到
agent-ts"的事故回归、"超时不换人"、"全败如实报 error"）；相关 235 条全绿。

## 六、追加：watch_todo 工具（agent-dh 试点，2026-10-16 深夜）

**用户裁定**：「先只给 agent-dh 试点」——补齐"接单→处置→收敛"这段（即下面遗留清单里的缺口 1）。

### 交付物（跨两仓，各一处）

| 仓 | 文件 | 内容 |
|---|---|---|
| `quantsys-v2-client` | `src/types.ts` | `WatchTodo` / `WatchTodoListParams` / `WatchTodoCloseRequest`（close 的两条硬约束写进注释） |
| `quantsys-v2-client` | `src/client.ts` | `listWatchTodos`（GET /api/watch/todos）/ `claimWatchTodo`（POST …/claim）/ `closeWatchTodo`（POST …/close） |
| `agent-dh` | `packages/tools/intelligence/src/tools/WatchTodoTool/{prompt,WatchTodoTool,index}.ts` | `watch_todo` 工具：`action=list/claim/close`；prompt 写明何时用（收到 `watch_todo_assigned`/`watch_todo_timeout` 必须处置）与 close 硬约束 |
| `agent-dh` | `packages/tools/intelligence/src/index.ts` | 注册 `createWatchTodoTool(qv2)` |
| 测试 | `agent-dh/.../tests/watch-todo-tool.test.ts`（12 条）、`quantsys-v2-client/test/watch-todo.test.ts`（6 条） | 校验拦截（ignored 缺 NEXT / rule_change 缺审计 ID）、三动作契约、DSH 定义冒烟、错误不静默 |

**为什么 `owner_ref` 由工具写入**：claim 把它写进 `watch_todos.owner_ref`——既是"谁在做"的事实源，
也是 v2 判断"升级去向"的依据（`owner_kind=agent` 的待办只催 agent，不再占用用户卡）。
工具默认取本实例（`DSH_AGENT_REF`，默认 `agent-dh`）；agent-ts 将来复用同一工具只需设
`DSH_AGENT_REF=agent-ts`，不必改代码。

### 验证

- 构建：两包 tsdown 均通过，`intelligence/dist/index.mjs` 内含 `watch_todo`。
- 单测：client 16 条（15 passed / 1 skipped）、intelligence 新增 12 条全绿。同目录另 1 条
  `integration.test.ts > evaluateDecision > observation` 失败与本改动无关（只 import 决策评估域，
  domain/application 单跑均通过）。
- **真库只读实测**（新客户端 → 生产 5001）：
  `listWatchTodos({limit:5})` 返回真实工单 `#27 601888 P1/L3 trade owner=agent` …；
  `closeWatchTodo(91, {terminal:'ignored'})` 被服务端以 `HTTP 400 watch_todo_missing_next_condition`
  拒绝——错误码按预期透传，**且未写任何数据**（校验在落库前）。

### 生效前提

1. **agent 进程要起来**：agent-dh（:13080）当前未监听，工具再全也没人调用；起来后加载新 dist 即生效。
2. **唤醒载荷已带 instruction**（§三 ②b）：事件 `watch_todo_assigned` / `watch_todo_timeout`，
   指令写明 close 契约（含 L3+rule_change 必带审计 ID）。
3. **一周后看四个数字**决定是否复制到 agent-ts：`kind='result'` 回执数（基线 1）／
   agent 自有未收敛待办数（基线 48）／`suppressed` 规则数（基线 8）／用户侧 timeout 实发（基线 20）。

## 七、遗留（未做，需另立卡）

1. **待办催办的节流/退避**：当前"一条待办一张卡 / 一次唤醒"。若希望长期未处置持续施压，
   应显式设计 backoff + 次数上限 + 日终汇总点名（尤其 **P2 逾期未处置**目前只在文档里，
   代码没有日终汇总实现）。
2. **agent 离线时的可达性**：21:36 实测 agent-dh（:13080）**未监听**，wake 走 `error`
   → 落到用户卡兜底。是否需要"离线建窗代执行"之外的补偿（如运维群告警）另议。
3. **存量 13 条工单**（#79–91）仍在 L3：修复后不再复读；其中 10 条该由 agent-dh 收口，
   3 条（#79/#80/#81，用户账户规则）按 `owner_router` 归属用户，需用户给处置结论。
4. **本轮测试边界**：`tests/application/services/test_event_feed_service.py` 的 1 条失败
   与本改动无关（事件采集任务清单，改前即红）；`tests/api` 的 data_provider / lhb /
   scheduler-contract 失败同为存量。
5. **缺口 1（能力）已做一半**：agent-dh 已有 `watch_todo`（见 §六）；**agent-ts 未做**（按用户裁定
   先试点），复用方式为同一套命令 + `DSH_AGENT_REF=agent-ts`。
6. **缺口 3（在线）未做**：agent-dh 无 launchd 守护（`launchctl list` 里只有 v2-api 与
   agent-os），窗口不开就没有 wake 端点；是否要为 :13080 / :3002 加守护或探活告警另议。
7. **fan-out 前提**：`claim` 目前不排他（只判 `terminal IS NULL`，不看 `claimed_at`），
   要"同时投两个 agent、谁先认领谁做"必须先把认领改成原子条件，否则会双干。
