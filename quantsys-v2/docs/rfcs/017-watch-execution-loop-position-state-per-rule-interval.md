# RFC 017 · 盯盘执行闭环（agent 执行）· 持仓状态显式化 · 分标的盯盘频率

- 日期：2026-10-21
- 状态：已裁定（用户 2026-10-21）· 待实施（Taskmaster 图 `g-mvhmqjb4-28f661`）
- 前置：RFC 014（盯盘体系）、2026-10-20 机会闭环（环境闸/二次核验/止损豁免，commit `ef7625bd2`）
- 关系：本文件是**方案卡**，只定设计、数据口径与边界；代码由本图下各卡实施（卡映射见 §6）

**一页结论**：P0 止损触发后建立**可收敛的三态闭环**（执行 / 不执行 / 超时兜底），
「有无持仓」从 intent 隐含改为 `watch_rules.position_state` 显式字段并驱动 entry/exit 求值分支，
盯盘频率从全局 10s/60s 改为规则级 `interval_sec`。
**本 RFC 不新增任何自动下单**：闭环 = 结构化指令 → agent 执行 → 成交回执 → 超时有人兜底。

---

## 1. 背景与问题

### 1.1 三条差异（对账结论）

| # | 现象 | 现状事实（证据） | 后果 |
|---|------|------------------|------|
| 1 | **执行不闭环** | P0 触发 → 建待办 + 唤醒 agent（`watch_channels.py:178` `wake_todo_assignment`）；但「到底卖没卖」没有任何回写，待办终态只能靠人/agent 主动 `close`（`todo_service`） | 通知发完链路就断：止损喊了没人卖，系统只能等 L3 一轮轮催 |
| 2 | **持仓状态不显式** | 「有无持仓」靠 `intent` 隐含 + `position_lifecycle_service` 日频按标的推断再改规则（`position_lifecycle_service.py:84-140`），tick 级没有持仓真值 | 不能显式分支：空仓时照喊止盈、持仓时照喊建仓；也无法解释「为什么这条规则在响」 |
| 3 | **盯盘频率一刀切** | 全局 `base_interval=60` / `fast_interval=10`（`watch_engine/engine.py:124`），`fast_mode` 由「任一条件临近」全局拉快（`watch_engine/engine.py:644/663/700`） | 无法给不同标的不同节奏，也无法随时按规则调整 |

### 1.2 用户裁定（2026-10-21）

- **止损由 agent 执行**——盯盘与任何后台任务都不自动下单。闭环的含义是
  「盯盘发**结构化执行指令** → agent 执行 → 成交回执同步 → 超时有人兜底」。
- 频率用**规则级 `interval_sec`**。
- 方案落 RFC + Taskmaster 拆卡执行。
- 消息面覆盖（政策/行业词表）**挂后续计划，不进本期**。

### 1.3 事实基线：链路已经有什么、缺什么

不重造已有能力，是本 RFC 的第一条纪律。逐段核对（2026-10-21 工作树）：

| 环节 | 现状 | 证据 | 本 RFC |
|------|------|------|--------|
| 触发判定 / 分级 / 去重 / 处置状态机 | ✅ 已有 | `domain/watch/services/disposition.py:23-31`（pending/auto_observed/deduped/escalated/handled/ignored/expired/meta_review） | 复用，不扩枚举 |
| 待办 L1→L2→L3 升级 + 超时回执 + 超期归档 | ✅ 已有 | `sla_job.py:45`（L3 再催 4h/最多 3 轮）、`:57`（`WATCH_TODO_AUTO_EXPIRE_DAYS` 默认 3 天）、`:284-295` | 复用节奏；**另加**执行收敛期限（§2.1.5） |
| 待办 → owner agent 唤醒（带 instruction） | ✅ 已有 | `watch_channels.py:42`（`_CLOSE_GUIDE`）、`:111`（`_todo_wake_data`）、`:178`、`:209` | 扩展一个 additive 字段（§2.1.2） |
| 待办三态终态 | ✅ 已有 DB CHECK | 迁移 `20260918_watch_todo_loop.py:44`：`terminal IN ('handled','ignored','expired')`；`:54`（trade/rule_change 必须有 `decision_audit_id`）；`:53`（ignored 必须给 `next_condition`） | 直接用；**超时不用 expired**（§2.1.3） |
| 规则变更审计（含 trigger 溯源） | 🟡 表已有、写入未接线 | 迁移 `20260918_watch_todo_loop.py:91`（`watch_rule_changes.trigger_id`）；目前只有自愈服务在写（`noise_self_heal_service.py:211`） | 接线：规则调整路径写审计（§2.1.3 ②） |
| 成交写点 | ✅ 有且唯一 | `AccountTradingService.execute_trade`（`qs_trading/application/services/account_trading_service.py:481` commit，`:491` 起 11b 旁路已有「审计/绩效不影响成交」先例）；挂单撮合也走它（`:531-544`） | 在此挂回执（§2.1.4） |
| 结构化执行指令 | ❌ 缺 | 现有 wake 只有通用 `_CLOSE_GUIDE` 文案 | 新增 `exec_directive` |
| 成交回执 / 终态自动收敛 | ❌ 缺 | 成交后没有任何代码回头收敛 watch 待办 | 新增 `FillSyncService` |
| 持仓真值（tick 可见） | ❌ 缺 | 规则无 `position_state` 列 | 新增列（§2.2） |
| 规则级频率 | ❌ 缺 | 只有全局档 | 新增 `interval_sec`（§2.3） |

**不要接的死路（已核实零生产调用）**：`trade_service.create_trade_from_order`（`qs_trading/application/services/trade_service.py:22`，
全仓无调用方）与 `OrderService.record_fill`（`qs_trading/domain/trading/services/order_service.py:267`，`OrderService` 生产零实例化）。
在这两处挂回执等于挂在一个永远不会发生的成交上。

---

## 2. 设计

目标（可核验，逐条对应 §5）：① 每个 P0 止损触发都有明确收敛结局（执行/不执行/超时兜底）；
② 持仓状态成为规则的一等字段且不掩盖止损；③ 规则可设独立频率并即时生效；
④ 成交回执自动收敛，不靠人记得关单；⑤ 全部改动对旧库/缺列/未知状态向后兼容（行为等价降级）。

### 2.1 执行闭环（三态闭环）

#### 2.1.1 适用面与幂等

只对**宪法级止损**生效：`level=P0` 且 `intent=exit_stop`
（`CONSTITUTIONAL_INTENTS=('exit_stop',)`，`disposition.py:65`）。止盈/减仓/入场维持现有待办流程。

- **一单一目标**：同一 `(账户, 归一键标的)` 只保留一条未收敛执行待办；已有未收敛执行待办时
  **不重复建单**（复用 `list_open_by_rule` / `list_pending`），只刷新指令卡与到期时间。
- 归一键用 `normalize_symbol`（`disposition.py:95`，去掉交易所后缀），账户取
  `linked_account or account`（引擎既有口径，`watch_engine/engine.py:1114`）。
- 无账户归属是**数据缺陷不是静默条件**：照常建单并唤醒 agent，指令里把补
  `linked_account` 列为第一优先（与 `digest_service.py:26/342` 的「未归属桶」口径一致）。

#### 2.1.2 指令构造（`exec_directive.py`，纯函数可单测）

从触发上下文构造结构化 payload，作为 `_todo_wake_data` 的 additive 字段
`exec_directive` 随 wake 下发（`watch_channels.py:111`），同时渲染进 P0 卡片
（`risk_stop` 群，路由已存在：`watch_channels.py:88`）。

| 字段 | 来源 | 缺省 / 语义 |
|------|------|-------------|
| `action` | 常量 | `execute_stop_loss` |
| `rule_id` / `trigger_id` / `todo_id` | 规则、触发、待办 | 溯源三件套 |
| `symbol` | `normalize_symbol(rule.symbol)` | 归一码 |
| `account` | `linked_account or account` | 为空 → `executable=false, reason=account_unknown`（仍唤醒去定性） |
| `side` | 常量 | `sell` |
| `qty` | `simulation_positions.shares_available` | **T+1 可卖量，不是 `shares_total`**；`0` → `executable=false, reason=t1_locked` |
| `ref_price` | `rule.cost_price` → 否则 `position.avg_cost` | 都没有 → `null`（不臆造） |
| `trigger_price` | 触发时报价 | 触发价 |
| `pnl_pct` | `(trigger_price-ref_price)/ref_price` | `ref_price` 缺失 → `null` |
| `executable` / `not_executable_reason` | 上述事实推导 | `no_position` / `t1_locked` / `account_unknown` |
| `deadline_at` | 触发时间 + `WATCH_EXEC_SLA_MIN` | 见 §2.1.5 |
| `evidence` | `{condition, distance_ratio, level, intent}` | 判定依据，供复核 |

两条硬约束写进 instruction（给 agent 的操作口径）：

1. `executable=false` 时**不要重试下单**——执行 API 会用同样的理由拒绝
   （`qs_trading/application/services/account_trading_service.py:389-392` 的 T+1/无持仓 422），改为：定性数据缺陷或报
   「今日不可执行」并给 NEXT 条件（`ignored` + `next_condition`）；
2. 成交后**不要手动关单**——`FillSyncService` 会自动收敛（§2.1.4）；重复关单只会得到幂等拒绝。

持仓事实读不到（DB 异常）时**不得默认"没有持仓"**：`executable` 保持 `true`，
`evidence.position_read='degraded'`，让 agent 去核实——读失败就静默不喊卖，等于把数据故障
伪装成"无需动作"。（同一条纪律的两面：对账侧读失败选择**什么都不做**、不误退役止损规则；
执行侧读失败选择**照喊**、交给人/agent 核实。）

#### 2.1.3 三态闭环（核心）

三种收敛结局，全部映射到**已有**的 `todo.terminal` 与 `trigger.disposition`，不新增枚举：

| 态 | 入口条件 | todo 落库 | trigger | 规则 / 持仓状态副作用 | 谁负责 |
|----|----------|-----------|---------|----------------------|--------|
| **① 执行 executed** | 卖出成交（该标的剩余持仓为 0） | `handled` + `action_kind='trade'` + `decision_audit_id` | `handled` + `detail.exec={trade_id,price,latency_sec}` | 该标的 exit 族规则退役；`position_state→'none'` | `FillSyncService`（自动） |
| **② 不执行 declined** | agent/用户显式 `close` 为 `ignored` | `ignored` + `close_reason` + `next_condition`（DB CHECK 强制） | `ignored` + reason | 按 `change_kind` 改规则（`threshold`/`cooldown`/`retire`/`suppress`）+ `watch_rule_changes.trigger_id` 溯源 | agent（经现有 close API） |
| **③ 超时 unresolved** | `now > deadline_at` 且未收敛 | **保持未收敛**（不写终态） | 保持 `escalated` | 无 | `sla_job`（超时回执 + 唤醒 + L3） |

关键约定：

- **③ 是状态不是终态**：超时不等于放弃。收敛仍靠 ①/②；若期间持仓已被别处清掉，
  对账路径按「成交为准」收敛为 ①（`close_reason` 标 `reconciled`，并在 `detail` 记来源）。
- **绝不把超时写成 `expired`**：`expired` 的既有语义是「超期未处置，系统自动归档（进台账，
  非判定）」（`sla_job.py:42/291-295`）。对止损持仓用它，等于把「钱还敞着」记成「已处理」。
- **部分成交不算执行**：卖出后仍有持仓（`shares_total>0`）→ 待办保持未收敛，只记 progress，
  继续走 ③ 升级。指令要求的是清仓，半仓不构成闭环。
- **②必须有结构化动作**：不让 agent 用自由文本描述「我已调整规则」；`change_kind` 走白名单
  （`noise_policy.CHANGE_KINDS`，`noise_policy.py:62`），`reason` 必填，`trigger_id` 落
  `watch_rule_changes`（端口 `record(..., trigger_id=...)`，`ports.py`）。
  现状缺口：规则 `PUT/PATCH` 路由不写审计（`watch_async.py:175-193`），由
  `rule-change-linkage` 卡补齐。

#### 2.1.4 成交回执（`FillSyncService`）

**依赖方向**：`qs_watch → qs_trading` 是已声明的单向依赖（`packages/qs_watch/pyproject.toml:18`），
反向不存在。因此**不能**让 trading import watch，用端口 + 注册装配：

- trading 侧新增薄端口（`qs_trading/domain/trading/ports/`）：`IFillListener.on_fill(event)` +
  模块级 `register_fill_listener()/get_fill_listener()`，缺省 no-op。
- **唯一填报点**：`AccountTradingService.execute_trade` 提交之后（`qs_trading/application/services/account_trading_service.py:481`
  commit；紧邻 `:491` 的 11b 旁路）。调用包在 `try/except` 里，**失败只记日志，绝不影响成交**
  （沿用 `_auto_record_decision` 的既有纪律，`:694-704`）。
- `FillEvent` 字段：`account_name, symbol, action, shares, price, trade_id, order_id,
  decision_audit_id, filled_at`。`decision_audit_id` 取 `_auto_record_decision` 的返回 id
  （需把该方法的返回值带出；拿不到时退化为 `trade:<trade_id>` 并在 detail 标 `audit_degraded`，
  不虚报审计）。
- 消费侧 `FillSyncService`（qs_watch，装配在 `watch_bootstrap` 这个组合根）：
  1. **状态**：读库真值（`simulation_positions.shares_total`）→ `>0` 写 `holding`、`=0` 写 `none`；
     经仓储写入口 `set_position_state`（`watch_rule_repository.py` 已落地），作用于该
     `(account, symbol)` 的**全部**规则。
  2. **收敛**：sell 且该标的剩余为 0 → 该 (账户,标的) 未收敛 P0 执行待办 `close(handled,
     action_kind='trade', decision_audit_id)`；剩余 >0 只记 progress。
  3. **触发**：`update_disposition('handled', reason=...)`，并把 `{trade_id, price, latency_sec}`
     合并进 `watch_triggers.detail`（现签名只有 `reason/by`，需加可选 `detail_patch`，
     `watch_rule_repository.py:398`）。
  4. **退役**：复用 `PositionLifecycleService._retire` 语义（`enabled=False` +
     `lifecycle_stage='closed'` + banner，`position_lifecycle_service.py:232`），只退役 exit 族。
- **幂等**：`close` 对已终态返回 `None`（端口契约 I3，`domain/watch/ports.py:304-310`）；重复 fill 不二次收敛；
  `detail.exec` 已存在则跳过（latency 只写一次）。
- **覆盖**：`execute_pending_orders` 也走 `execute_trade`（`:531-544`），挂单成交自动覆盖。

#### 2.1.5 超时兜底：两个时钟，互不改写

| 时钟 | 现状 / 新设 | 作用 | 落点 |
|------|-------------|------|------|
| 提醒升级节奏（既有） | P0 `due_at=now+300s`（`level_resolver.py:52`、`watch_engine/engine.py:1344`）；L1→L2→L3；L3 每 4h 最多 3 轮 | 「提醒得够不够快」 | `sla_job`（不改） |
| 执行收敛期限（新增） | `WATCH_EXEC_SLA_MIN`，默认 30 分钟 | 「执行到底发生没有」 | `sla_job` 巡检增量分支 |

到点动作（仅 `level=P0 AND action_kind='trade' AND 未收敛`）：发 `kind='timeout'` 回执
（含「已等待 N 分钟仍未执行」与执行指令摘要）→ `wake_todo_owner`（事件已存在：
`WAKE_EVENT_TODO_TIMEOUT='watch_todo_timeout'`，`watch_channels.py:39/190`）→ `flow_state=L3`
→ `escalate_count+1`（复用 `promote` 语义，`extend_due_minutes=0` 防幂等键轮换）。

**为什么不把 `due_at` 直接改成 30 分钟**：那会把既有 P0 首催从 5 分钟推迟到 30 分钟，
削弱存量升级契约（对止损尤其危险）。两个时钟正交，各管一件事。

**与 `auto_expire_days`（默认 3 天，`sla_job.py:57`）的关系**：那是最后兜底归档（非判定），
本闭环要求 30 分钟就有人被顶上，不等 3 天。

**执行期限只适用于 `executable=true` 的待办**：`executable=false`（`no_position` / `t1_locked` /
`account_unknown`）不是「没执行」，而是「无可执行」——按普通 P0 提醒升级即可，不判执行超时。
其中 `no_position` 若经核实持仓确为 0（状态滞后），按 ① 的对账口径收敛
（`close_reason` 标 `reconciled:no_position`）。

#### 2.1.6 闭环统计

- 数据来自已有台账，不新建表：`watch_triggers.detail.exec`（时延/成交）、
  `watch_todos.terminal`（三态计数）、`watch_receipts.kind='timeout'`（超时次数）。
- 新增 `GET /api/watch/exec/stats`（additive，P2 可后置）：executed / declined / timeout 计数、
  执行时延 p50/p95、超时率、`state_mismatch` 计数。
- **订正**：不要挂到 `GET /api/watch/outcomes/stats`——那是「触发后 5/10/20 交易日预判命中率」
  （`watch_async.py:28-43`），口径完全不同，混在一起会把两个指标都做坏。

### 2.2 持仓状态显式化

**字段**：`watch_rules.position_state varchar(16) NOT NULL DEFAULT 'none'`，值域 `none` / `holding`。

**读口径（fail-open，已落地于仓储）**：`rule_position_state(rule)` → `'none'` / `'holding'` / `None`。
**`None` 是「状态不可知」，不等于 `'none'`**（`'none'` 是「确认无持仓」）——
消费方拿到 `None` 必须退回旧行为，绝不按「确认空仓」处理（`watch_rule_repository.py:83-101`）。

**写口径（已落地）**：`set_position_state` / `update_fields` 归一（`None → 'none'`，非法值抛错）；
列缺失时 `update_fields` 丢弃新字段并 warn（fail-open 旧行为），
`_new_columns_available()` 做列预检。两个通道：
a) **fill 实时**（§2.1.4）；b) **日频对账兜底**：现役 `position_lifecycle_service` 从「唯一同步」
降为「对账纠偏」，读失败仍 `degraded=True` fail-closed（`:52-60`）。

**引擎显式分支**（插在活性过滤之后、按 symbol 取价之前；`watch_engine/engine.py:575-598`）：

| `position_state` | entry / add_position | t_trade / exit_* | 观察类（trend_observe 等） |
|---|---|---|---|
| `'none'`（确认空仓） | 求值 | 跳过 | 求值 |
| `'holding'`（确认持仓） | 跳过 | 求值 | 求值 |
| `None`（未知/缺列/NULL/非法） | 求值 | 求值 | 求值 |

即：**只有确认相反才跳过，不确定一律求值**（宁可多喊一次，不可漏喊止损）。

**订正原草稿一处归类**：`t_trade` 不是 entry 族。A股 T+1 下没有底仓无法做 T（先卖后买需要
可卖底仓），所以 t_trade 与 exit 族同属 `holding` 分支。

**状态与持仓矛盾的检测**：只在 fill / 日频对账时发现（tick 不额外查库）。发现时**只记 warn 日志
+ 计数**，不写 `watch_rule_changes`——`change_kind` 是白名单枚举（`noise_policy.py:62`），
为「状态纠偏」发明一个 kind 会污染审计语义；也不新增表（宁可少一条记录，不造假审计）。

**兼容**：旧库缺列 → 全部规则读出 `None` → 分支表退化为「全部求值」，行为与今天**完全等价**。

### 2.3 规则级盯盘频率

**字段**：`watch_rules.interval_sec integer NULL`。`NULL` = 跟随全局档（base 60s / fast 10s），
**不设默认值**——存量规则节奏一秒都不该被本 RFC 改变。

**生效路径**：规则 CRUD 写入 → 引擎每 tick `rule_repo.list_enabled()` 重载（`watch_engine/engine.py:575`，已有）
→ 下一拍自然生效。无需热重载、无需重启（`set_interval_sec` 已落地于仓储）。

**调度口径**（本 RFC 的定义，供 `per-rule-interval` 卡实施）：

- 每规则记 `last_eval_at`（**进程内存**）：`effective_interval = interval_sec，若为 None 则
  (fast_mode ? fast_interval : base_interval)`；`now - last_eval_at >= effective_interval` 才求值。
- 未到期 → **不取价、不评估、不动闩锁/冷却**（同 symbol 多规则共享一次取价的既有合并逻辑不变，
  `watch_engine/engine.py:598`；某 symbol 全部规则未到期 → 本 tick 不取该 symbol）。
- **tick 间 sleep 必须看最早到期时间**：`sleep = clamp(min(档位间隔, 最早到期剩余秒数), 1, 档位间隔)`。
  否则主循环睡 60s，`interval_sec=30` 永远等不到第二拍。
- 内存态可接受：重启后全部规则首拍求值一次（闩锁/冷却仍由运行态 store 恢复，
  `watch_engine/engine.py:504-509`），只是「早一拍」，不会重复触发。
  **订正原草稿**：不为此新增运行态列（`watch_runtime_state` 的 (rule_id, cond_idx) 结构装不下
  规则级到期时间，为一个可丢的调度缓存加迁移不划算）。
- **临期提速**：本拍求值观察到 `distance_ratio <= buffer_ratio`（默认 0.2，`watch_engine/engine.py:125`）→
  下一拍该规则 `effective_interval = min(interval_sec, fast_interval)`，即最多 10s。
- **全局 `fast_mode` 语义不变**（任一被求值条件临近即全局提速，`watch_engine/engine.py:644/663/700`）；
  interval 规则参与把它挑快，自己的 10s 加速与全局一致。
- **下限 5s**：引擎侧 clamp（保护行情源）。仓储只拒绝无法解释的值（`<1`/负数/布尔，
  `normalize_interval_sec`）；写入 1–4s 的值引擎按 5s 执行并 warn（不静默失真）。
- **排除**：市场级规则（`scope ∈ MARKET_SCOPES`，`watch_engine/engine.py:588`）不参与规则级频率，
  沿用自身扫描节奏。
- **可观察性**：把 `last_eval_at` / 每规则 `next_due_in` 汇总进 `get_metrics`
  （`watch_engine/engine.py:283`），排障时能一眼看出「哪些规则被频率门挡住」。

### 2.4 非目标（明确不做）

1. **不自动下单**（硬约束）：盯盘与任何后台任务都不因本 RFC 产生订单。闭环 = 指令 → agent 执行
   → 回执 → 兜底。包括：超时**不改用 `expired`** 放弃保护；不新增券商直连；不改 trading 的下单入口；
   不给 watch 包任何下单能力。
2. **消息面覆盖不进本期**（用户 2026-10-21 裁定）：政策/行业词表、新闻触发的盯盘扩面挂后续计划，
   本 RFC 不设计、不预留半成品开关。
3. 不做入场信号自动化（入场永远是通知制，不是「检测到就买」）。
4. 不改 `account_type` 门禁，不改 `IntradayMonitor` 的既有行为（张力见 §4 第 4 条）。
5. 不重构引擎调度骨架：tick 的过滤链分区属 `pipeline-refactor` 卡，本 RFC 只定**分区与顺序**
   （活性 → 状态门 → 到期门 → 取价 → 评估），不规定具体重构手法。

---

## 3. 数据迁移

实现：`infrastructure/persistence/migrations/20261021_watch_rules_position_interval.py`
（默认 dry-run；`--apply` 写库；`--dsn` 显式指定；生产库与 `*_test` 各执行一次）。

```sql
-- 1) 两列（幂等）
ALTER TABLE quant.watch_rules ADD COLUMN IF NOT EXISTS position_state varchar(16) NOT NULL DEFAULT 'none';
ALTER TABLE quant.watch_rules ADD COLUMN IF NOT EXISTS interval_sec   integer;

-- 2) 回填：有正持仓的规则晋升 holding（真实列名：simulation_positions.account_name / shares_total）
UPDATE quant.watch_rules r SET position_state = 'holding'
WHERE r.position_state IS DISTINCT FROM 'holding'
  AND EXISTS (
    SELECT 1 FROM quant.simulation_positions p
     WHERE coalesce(p.shares_total, 0) > 0
       AND split_part(p.symbol, '.', 1) = split_part(r.symbol, '.', 1)
       -- 两端都带后缀时必须后缀一致：000001.SH（指数）≠ 000001.SZ（平安银行）
       AND (strpos(r.symbol, '.') = 0 OR strpos(p.symbol, '.') = 0
            OR upper(split_part(r.symbol, '.', 2)) = upper(split_part(p.symbol, '.', 2)))
       -- 账户匹配：空 linked_account 视为通用规则（任意账户持仓都算）；两端 btrim
       AND (NULLIF(btrim(r.linked_account), '') IS NULL
            OR btrim(p.account_name) = btrim(r.linked_account))
  );
```

口径与约束：

- **值域靠应用层**：不加 `CHECK` 约束——值域由 `normalize_position_state` /
  `normalize_interval_sec` 把守（非法值在 API 层 400，而不是到 DB 才炸），也给未来扩枚举留余地。
- **回填是单向晋升**（只 `none→holding`）且 `IS DISTINCT FROM` 幂等：重跑更新 0 行，
  且**不会**把已被 fill 事件写成 holding、但持仓表尚未同步的规则刷回去。
  `holding→none` 由 fill 事件与日频对账负责，迁移不做对账器。
- **无持仓表的新环境**：回填返回 0、不失败（保持 DB 默认 `none`）。
- **回滚**：列保留无害。引擎/仓储对缺列、`NULL`、非法值一律按旧行为 fail-open
  （`_new_columns_available` + `rule_position_state` 的 `None` 语义）。
- **对原草稿的三处订正**（以真实 schema 为准，`infrastructure/persistence/orm/models/simulation.py:141-175`）：
  ① 表名是 `quant.simulation_positions`（复数，不是 `simulation_position`）；
  ② 列是 `account_name` / `shares_total`（不是 `account` / `quantity`）；
  ③ 标的匹配必须处理「一端带后缀一端不带」并校验后缀一致，否则指数/个股会串。

---

## 4. 边界与不变量

1. **watch 不直连 broker、不产生订单**（包边界见 `packages/qs_watch/CLAUDE.md`）；trading 只做
   「成交后通知 watch」的单向回调。
2. **依赖方向不可倒**：`qs_watch → qs_trading` 已在 `pyproject.toml:18` 声明，反向 import 会被
   import-linter 拦下。回执走**端口 + 组合根注册**，不走进程内 EventBus
   （`qs_kernel/.../event_bus.py` 目前只服务一个调试路由，为一条业务回调引入 pub/sub
   会多出异步/顺序/丢失三类语义，收益为零）。
3. **`account_type` 门禁语义不变**（agent/user/NULL→alert-only）：本 RFC 的「指令投给 agent」
   不等于放开 user 账户自动动作。
4. **`IntradayMonitor` 的存量自动止损存在口径张力（已裁定：保留作兜底）**：
   `qs_trading/application/services/intraday_monitor.py:8-10` 对 `account_type='agent'` 的 active 账户，每 30 分钟按百分比止损
   **自动卖出**——它是后台任务，与本 RFC「不自动下单」的字面口径冲突。**2026-10-21 用户裁定：
   保留作为兜底（最后防线）**，处理口径：
   - **不关它**（关掉等于此刻起没有百分比止损保护，属行为变更）；
   - 承认同一持仓可能被两条路径处理，收敛口径 = **以成交为准**：任一来源（watch 指令 /
     IntradayMonitor / 人工）的卖出成交 → `FillSyncService` 都收敛执行待办为 `handled`
     （`close_reason` 记来源）；
   - watch 侧点位止损是更快的那一层（秒级 vs 30 分钟），闭环不依赖 IntradayMonitor；
   - 待 agent 执行闭环稳定运行、样本充分后，再复核「是否收归单一下单者」。
5. **不新增 `disposition` / `terminal` 枚举**：`handled` / `ignored` / `expired` 已够用；
   执行超时是**状态**不是终态。
6. **未知永远 fail-open**：`position_state=None`（缺列/NULL/非法）必须照常求值；只有
   「确认相反」才跳过。
7. **审计纪律**：规则变更必须经 `watch_rule_changes`（`reason` 非空、`trigger_id` 溯源、
   `change_kind` 走白名单）；自动化路径不得用自由文本代替结构化动作，也不得为「状态纠偏」
   发明新的 `change_kind`。

---

## 5. 验收

**本卡（文档）**

- 三节齐全且各自可执行：三态闭环（§2.1）/ 持仓状态显式化（§2.2）/ 规则级频率（§2.3）；
- 边界（§4）与非目标（§2.4）明确，非目标含「不自动下单」「消息面后续」两条硬项；
- 无未决占位符；与真实 schema / 已落地的仓储实现一致（订正项见 §3 与附录）。

**图内其余卡（供交卷证据引用）**

| 验收点 | 判据 |
|--------|------|
| 迁移 | dry-run 报告列增量；`--apply` 重跑 0 行；带后缀/账户空格的样例回填正确；缺列库不报错 |
| 仓储 | 缺列时读写不炸且 `position_state` 读出 `None`；写归一（`None→'none'`、`interval_sec<1` 抛错） |
| 引擎分支 | §2.2 分支表逐格（none/holding/None × entry/t_trade+exit/观察类） |
| 频率 | 未到期不取价；`interval_sec=30` 在 30s 内不重复求值；临期提速到 10s；市场级规则不受影响 |
| 回执 | 成交 → todo `handled` + exit 规则退役 + 状态翻转 + 时延落 detail；部分成交不收敛；重复事件幂等；trading 侧回执异常不影响成交 |
| 超时 | 到 `deadline_at` → timeout 回执 + L3 + **未写 expired**；已收敛后不再发 |
| 统计 | `/api/watch/exec/stats` 三态计数与 p50/p95 与台账一致 |
| 回归 | watch 全量（场景矩阵 + application + bootstrap）绿；trading 成交路径测试绿 |

**e2e（`exec-loop-e2e` 卡）**：P0 触发 → 指令卡 → 模拟成交回灌 → 三态各自收敛（执行/放弃/超时）
→ 统计可读。

---

## 6. 实施切分（与图内卡一一对应）

| 卡 | 落点 | 依据 |
|----|------|------|
| `rule-columns-migration` | 迁移 + 仓储读写/归一/缺列兼容 | §3、§2.2、§2.3（已并行落地） |
| `pipeline-refactor` | **`_process_condition` 15 步 → Pipeline/Chain 阶段注册表**（context/stage/registry/trace + 维护指南）。tick 过滤链（活性→状态门→到期门→取价→评估）不在此卡：到期门归 `per-rule-interval`、状态门归 `position-state-branch`，tick 骨架保持不动 | 2026-10-21 实施裁定（订正原表） |
| `per-rule-interval` | `last_eval_at` / `effective_interval` / sleep 取最早到期 / 到期门跳过取价 | §2.3 |
| `position-state-branch` | **状态门在 tick 层**（活性过滤后、到期门前，规则级过滤；非 pipeline 阶段）+ 分支表 + 日志/计数 | §2.2、2026-10-21 实施裁定 |
| `exec-directive-card` | `exec_directive.py` + wake 字段 + P0 卡片 | §2.1.2、§2.1.1 |
| `fill-event-sync` | `IFillListener` 端口 + `FillSyncService` + bootstrap 注册 | §2.1.4 |
| `rule-change-linkage` | 规则 `PUT/PATCH` 写 `watch_rule_changes`（`trigger_id` 溯源） | §2.1.3 ② |
| `exec-loop-e2e` | 端到端三态 + 统计 | §5 |

---

## 附：本文档的复核记录（2026-10-21）

**已逐条核实的事实**（均在 `quantsys-v2/` 工作树；新列的迁移/仓储实现以并行卡
`rule-columns-migration` 的产出为准，本文件与其口径一致）：

- 三态终态枚举与约束：`20260918_watch_todo_loop.py:44/53/54`；
- 待办→agent 唤醒与 instruction：`watch_channels.py:39/42/111/178/190/209`，
  卡片路由 P0/timeout→`risk_stop`：`:88/95`；
- P0 SLA 300s 与超期归档 3 天：`level_resolver.py:52`、`watch_engine/engine.py:1344`、`sla_job.py:45/57`；
- 全局频率与临期加速：`watch_engine/engine.py:124-125`、`:644/663/700`；每 tick 重载规则：`:575`；
  同标的只取一次价：`:598`；市场级排除：`:588`；
- 成交唯一写点：`qs_trading/application/services/account_trading_service.py:481/491/531/694`；死路 `qs_trading/application/services/trade_service.py:22`、
  `qs_trading/domain/trading/services/order_service.py:267`（零生产调用）；
- 持仓表真实 schema：`orm/models/simulation.py:141-175`（`simulation_positions` /
  `account_name` / `shares_total` / `shares_available`）；
- 仓储新列读口径与写入口：`watch_rule_repository.py:46-117`、`:83-101`、`set_position_state` /
  `set_interval_sec` / `update_fields` 白名单；
- `watch_rule_changes` 已有 `trigger_id` 列（`:91`）但规则路由未写审计（`watch_async.py:175-193`）；
- `change_kind` 白名单：`noise_policy.py:49/62`。

**对原草稿的订正**：① 迁移表名/列名（§3）；② 闭环统计不挂 `outcomes/stats`（§2.1.6）；
③ 执行期限与 P0 提醒拆成两个时钟（§2.1.5）；④ `t_trade` 归 holding 分支（§2.2）；
⑤ 规则级到期时间用进程内存、不加运行态列（§2.3）；⑥ 三态显式映射到已有
`handled/ignored`，超时**不写** `expired`（§2.1.3）。

**待裁定（不在本 RFC 内拍板）**：`IntradayMonitor` 对 `agent` 账户的百分比自动止损是否停用
（§4 第 4 条）；是否给 `watch_todos` 增独立 `exec_deadline_at` 列（当前用 `created_at + SLA` 计算，
不改 schema）。
