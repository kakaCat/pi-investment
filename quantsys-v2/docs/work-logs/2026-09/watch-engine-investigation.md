# 盯盘引擎（WatchEngine）现状调研报告

- 调研人：investor / w-9b2b54f3（agent-dh 投资脑窗口）
- 调研时间：2026-09-18 00:14（数据截至 2026-09-17 收盘后的库内实况）
- 调研对象：quantsys-v2 的盯盘引擎（WatchEngine）全链路
- 方式：只读代码审计 + 只读数据库取数 + 缺陷复现（未修改任何文件、未下单）
- 结论一句话：**架构分层是清晰的，但"触发→用户/agent 收到东西"这条主链是断的、且升级判定有确定性 bug——引擎当前主要在产生噪声，而不是在盯盘。**

---

## 0. 结论速览（先看这 8 条）

| # | 结论 | 证据 |
|---|------|------|
| 1 | **唤醒 agent 这条路当前完全没生效**：摘要门以影子模式运行，只写日志、不唤醒、不写状态 | .env:53 WATCH_DIGEST_DRY_RUN=true；quant.watch_digest_state 从建表（2026-09-11）至今 wake_count=0 |
| 2 | **升级判定有确定性 bug**：量能异常路径把"现价"当"量比"读，任何 >3 元的股票都会被判成"量能异常 N 倍" | 复现输出：量能异常（388.5x vs 阈值1.5x）；watch_triggers.detail.value=388.5 实为现价 |
| 3 | 触发大量积压无人消费 | 未处置 172 条（escalated 50 / pending 19 / meta_review 103） |
| 4 | 用户每天确实被打扰，但内容多为噪声 | 近 14 日"已通知"触发 388 条（09-17 单日 39 条） |
| 5 | 持仓生命周期联动只读 agent_virtual 一个账户，会误退役其它账户的卖出规则 | position_lifecycle_service.py:19 DEFAULT_ACCOUNTS；实证规则 #129（user_main_simulation）被判"已清仓收摊" |
| 6 | 规则"创建入口"装不下引擎的语义：agent 侧工具建不出带 intent/action_hint/escalation_policy 的规则 | WatchManageTool.ts 只透传 condition/account 等；库内 36 条启用规则里 26 条 intent 为空 |
| 7 | 引擎状态基本在内存，重启即丢；且无单例锁，多 worker 会重复触发 | state_manager.py:31-56；factory.py:147 无锁 |
| 8 | 没有可用的观测面：引擎指标 get_metrics() 无任何 HTTP 出口，web 前端与 agent-dh 都没有盯盘控制台页面 | engine.py:121 无人调用；pages/ 下无 watch 插件 |

---

## 1. 调研范围与方法

**代码范围**（quantsys-v2，非测试代码）：

- application/services/watch_engine/*.py —— 18 个文件，2,609 行（引擎主体 engine.py 413 行、digest_service.py 372、notifier.py 319、conditions.py 252…）
- domain/watch/** —— 领域模型 / 端口 / 4 个领域服务
- domain/notification/policies/watch_channel_policy.py、watch_delivery_policy.py
- adapters/inbound/fastapi_app/routes/watch_async.py、watch_bootstrap.py、daily_jobs_bootstrap.py 的 watch_rule_health
- adapters/outbound/repositories/watch_rule_repository.py、watch_state_repository.py
- agent-dh 侧：packages/intelligence 的 watch_list / watch_manage 工具

**取数范围**（PostgreSQL quant_investment，只读）：watch_rules / watch_triggers / watch_digest_state / watch_interventions / notification_logs / daily_klines / simulation_positions。

**复现**：直接 import domain.watch.services.escalation_checker.EscalationChecker，用线上规则 #162 的真实配置回放判定，得到与库内完全一致的错误结论。

---

## 2. 它是怎么运行的（现状架构）

```
FastAPI 进程（:5001, main.py:281-289 lifespan）
  └─ watch_bootstrap.start_watch_engine
       └─ factory.create_watch_engine()   ← 唯一装配点 factory.py:123
            └─ daemon 线程 watch-engine  ── engine.run_forever()  engine.py:137
                 └─ 仅交易日 9:30-11:30 / 13:00-15:00 循环 tick()（60s；接近触发位升 10s 快档）
                      tick(): 遍历全部启用规则
                        ├─ quote_service.get_realtime_quote(rule.symbol)   ← 逐规则取价（无批量）
                        ├─ evaluate(cond, quote, ctx)                      ← conditions.py 6 类条件
                        ├─ TriggerJudge.should_emit  闩锁/冷却(默认300s)
                        ├─ EscalationCoordinator.check  L0/L1 → 5 类升级判定
                        ├─ DispositionEngine.decide    预算/意图/金额/增量/经济 五道门
                        ├─ DeduplicationManager.check  同标的同向合并 + 跨规则重叠转治理
                        ├─ notifier.notify → NotificationFacade → 飞书（L0/L1 直发；L2 走 agent 通道失败降级飞书）
                        └─ 落库 quant.watch_triggers（含 disposition）
                      ├─ 每次 tick 末尾：digest_service.maybe_wake(now)   ← 唯一的"叫 agent"门
                      ├─ 每日一次：meta_review_service.scan（规则健康/元触发）
                      ├─ 每日一次：position_lifecycle_service.reconcile（持仓联动）
                      └─ 每次 tick 末尾：market_watch_service.scan_market_rules（市场级）
```

要点：**引擎不是一个独立服务，而是后端进程内的一条 daemon 线程**。摘要门/元触发/持仓联动/市场扫描这四件事全部内嵌在这条线程里——线程一死（异常退出、进程重启未拉起、DISABLE_WATCH_ENGINE=true），它们同时静默消失，没有任何独立告警。

---

## 3. 当前能力清单（能做到什么）

| 维度 | 现状 |
|------|------|
| 条件类型 | 6 类：price_break / pct_change / pnl_pct / velocity / volume_surge / combined(AND,OR，最多 3 层)。**无均线/指标类、无时间窗、无事件类条件** |
| 触发语义 | 电平+闩锁（持续成立不重复推）+ 冷却（默认 300s，可按条件覆写）+ 同标的同向去重窗 60s |
| 分层 | L0 消息 / L1 观察 / L2 行动；无 action_hint 的规则默认 L1 |
| 升级（L0/L1→L2） | 5 类：触发频率、价格偏差、核心区域、量能异常、多规则共振 |
| 介入五道门 | 宪法豁免 → 预算 → 引擎升级 → L2 分级 → 意图/金额/增量/经济/节点 |
| 降噪 | 去重合并（落库但不通知）+ 跨规则重叠转治理项 |
| 规则生命周期 | expires_at 自动禁用、价格偏差 >20% 判 STALE、预案文本里日期过期判 OUTDATED、30 天不触发判 INACTIVE |
| 账本 | 每日介入预算 8 次、介入记账落库、规则价值账本字段（valuable_actions 等） |
| 观测/交互 | HTTP：规则 CRUD、触发查询/统计/未闭环、触发处置、digest 载荷、批量重配。**无引擎指标、无启停、无手动补跑、无控制台页面** |

---

## 4. 运行态事实（截至 2026-09-17）

来源：quant.watch_* 只读 SQL，2026-09-18 00:14 取数。

| 指标 | 数值 |
|------|------|
| 规则总数 / 启用 | 86 / 36 |
| 启用规则中无 trigger_level（默认 L1） | 24 |
| 启用规则中 intent 为空（→ trend_observe，意图门直接归档） | 26 |
| 启用规则中无账户归属 | 8 |
| 触发总量 | 658（2026-07-29 起） |
| 近 14 日处置分布 | escalated 50 / meta_review 103 / auto_observed 101 / deduped 49 / pending 19 |
| 未处置积压 | **172** |
| watch_digest_state | last_wake_at 为空、wake_count=0、updated_at 停在 2026-09-11（建表日） |
| watch_interventions | 33 条，每天恰好 8 条（= daily_budget 上限），outcome 全为 escalated |
| 近 14 日已通知触发 | 388 条（09-17 单日 39 条、09-10 单日 100 条） |
| 真实投递 | 2 个飞书渠道：171 sent + 85 sent，1 failed |

两条最刺眼的事实：

1. **wake_count=0 且 interventions 每天正好卡在 8** —— 预算门确实在跑并在第 8 次后把其余触发全部降级为 auto_observed，但"唤醒"从未真正发生。机器每天都在记"我该叫 agent 8 次"，然后一次都没叫。
2. 单日 39-100 条飞书通知里，近 14 日 escalated 的原因有 **19 条是"量能异常"**——而下面的复现证明那 19 条全是误读。

---

## 5. 缺陷清单

### P0-1 升级判定把"现价"当"量比"——L1 规则几乎无条件被升级（确定性 bug，已复现）

- **位置**：domain/watch/services/escalation_checker.py 的 _check_volume_anomaly（约 133-152 行）
- **机理**：该方法直接拿 result.value 当量比用，**不看条件类型**。对 price_break 条件，result.value 就是现价；对 pct_change，是涨跌幅百分数。工程上默认阈值 threshold = params.get(multiple, 1.5) = 1.5，乘 volume_ratio_multiplier(2.0) = 3.0 → **任何价格 > 3 元的 A 股都必然命中"量能异常"**。
- **复现（2026-09-18，真实类）**：

```
A 线上复刻（规则#162, 002916, price_break 388.75, 现价388.5） -> 量能异常（388.5x vs 阈值1.5x），可能主力异动
B 低价股（2.5 元）                                            -> None
C 涨跌幅条件（3.2%）                                          -> 量能异常（3.2x vs 阈值1.5x）
D 真正的 volume_surge（量比1.6x）                              -> None   ← 真信号反而不升级
```

- **线上印证**：quant.watch_triggers 里 escalated 记录的 detail 值是 {"value": 388.5, "message": "现价 388.5 ≤ 阈值 388.75（下破）"}，同一行的 disposition_reason 却是"量能异常（388.5x vs 阈值1.5x）"。规则 #137/#162 每天重复出现，量值 62x / 300x / 388x 全部是股价。
- **影响**：① 升级原因不可信，"量能异常"这个本该最有价值的信号被稀释成噪声；② 升级后 notifier 强制 trigger_level=L2 → 走 L2/agent 通道、按高优先级推送，用户收到的"L2 行动层"里混着一堆假信号；③ 每次误升级消耗一次每日预算（8 次/天），把真实信号挤掉；④ D 场景说明**真放量反而不会升级**——判据方向是反的。
- **为何测试没拦住**：tests/services/test_escalation_checker.py:89 的用例把 result.value 直接构造成量比，绕过了"条件类型与 value 语义"的绑定，所以单元测试全绿。
- **修法建议**：把升级判据与条件类型绑定（仅 volume_surge 的结果可进入量能路径），或让 EvalResult 显式带 metric 名称/单位（volume_ratio vs price vs pct），升级器按 metric 取数；并为"price_break 触发不得因价格数值升级"补一条故障注入用例。

### P0-2 唤醒链失效：触发积压 172 条，agent 永远不会被叫起来

- **位置**：factory.py:106-121（WATCH_DIGEST_ENABLED 默认 false）、:115（WATCH_DIGEST_DRY_RUN 默认 true）；digest_service.py:259-302（影子分支只记日志）
- **现状**：.env:52-53 = ENABLED=true + DRY_RUN=true → 摘要门构造出来了，但走影子分支：不算预算、不写 watch_digest_state、不 POST /wake。
- **后果**：escalated 50 + pending 19 + meta_review 103 = **172 条待处置触发没有任何消费者**。规则被触发、结论被落库、通知发出去，然后就没有然后了——没有任何角色会去读这个队列并按预案行动。用户"不满意"的最可能根源就在这里：引擎看起来很忙，实际不产生决策。
- **附带风险**：影子模式的设计初衷是"真开前先观察 24h"，但它已经挂了 7 天（2026-09-11 起），期间没有任何"该开了"的提示——影子模式没有到期自检，是个可以无限期挂着的暗开关。
- **修法建议**：把"影子模式运行时长"纳入元触发/系统运维频道（超 48h 必须提请裁决，二选一：真开或关掉并说明），消除永久暗开关；真开前先用 digest 端点离线核对一份摘要样本。

### P0-3 持仓生命周期联动读错账户，会静默退役别的账户的卖出规则

- **位置**：position_lifecycle_service.py:19 DEFAULT_ACCOUNTS = ("agent_virtual",)；factory.py:138-141 实例化时**没有传 accounts**
- **后果**：联动只拿 agent_virtual 的持仓判断 held；对其它账户的 exit_* 规则，held 恒为 False → 被判"已清仓"→ 退役（且带一条"收摊"横幅）。同时其它账户的 entry 规则也永远不会被自动补挂止损（宪法第 4 条要求持仓必须有止损盯盘）。
- **实证**：规则 #129（601600，exit_reduce，linked_account=user_main_simulation）已于 2026-09-14 被退役，横幅写"已清仓，卖出规则族收摊"。它归属的账户 user_main_simulation 当前有 5 个持仓，而 agent_virtual 只有 2 个——误判来源就是账户范围。
- **影响面**：当前仅 1 条已受害（启用中的 exit_* 规则本就少：2 条），但这是"静默拆除风控"的路径，属宪法级风险；且账户一多必然放大。
- **修法建议**：accounts 从账户清单动态解析（account_list），或按规则 linked_account 逐账户判定持有；无论如何，退役动作必须走"fail-closed + 明确留痕 + 通知"。

### P1-1 频道金额门是死代码，"大额动作进风控频道"不生效

- watch_channel_policy.py:_over_amount_threshold 依赖 self.account_total_yuan，而唯一调用点 notification_facade.py:93 用无参构造 WatchChannelPolicy() → account_total_yuan 恒为 None → 金额门恒 False。
- 后果：风险提示频道（risk_stop）实际上只能靠 exit_stop 意图进入，金额维度的自动升级（单笔 ≥ 账户 5%）完全不工作。

### P1-2 "账户 → 处置 agent"的路由在 L2 通知链上是空转

- notification_facade.py:100/132 计算了 target_agent 并放进 notification.variables，但 agent 通道只读 os_channel、飞书通道只认单一 webhook_url → 这个字段没有消费者（digest_service 那条路才有）。
- 后果：L2 触发无法按账户投给对应处置 agent；"10 个逻辑频道可分别静默"对 L0/L1 直发路径也不成立（直发只看 webhook）。

### P1-3 规则健康度是"两份真相"，领域服务是死代码

- domain/watch/services/rule_health_checker.py（206 行）只被 __init__.py 导出和它自己的测试引用；线上 16:30 的 watch_rule_health 作业在 adapters 层内联重实现了一遍。
- 后果：任何健康度口径修改都要改两处，且改错了不会有人发现（另一份在跑）。

### P1-4 引擎状态在内存 + 无单例锁

- state_manager.py:31-56：闩锁 / 冷却 / 价格历史 / 去重窗 / 触发事件日志全在进程内存。重启即丢 → 重启后同一条件可能重复推送；velocity 条件需要 30 分钟价格历史，重启后有一段冷启动盲区。注释自认"为状态可序列化/多实例恢复留单一改造面"——改造面留了，改造没做。
- factory.py:147 start_watch_engine_in_thread 无跨进程单例锁，main.py 起线程也无幂等。当前恰好单 worker 所以没炸；一旦 uvicorn --workers N / 双进程，就是 N 份引擎重复触发、重复发飞书。

### P1-5 触发统计与未闭环清单口径错误

- watch_async.py:187-189 / 213-214：先 limit=200 取触发、再按日期过滤 → 当日触发 >200 条时统计少计、未闭环清单漏项。
- watch_rule_repository.get_rule_trigger_stats 的 docstring 自认 int(None) 会吃掉部分结果；watch_async.py:42 更是把 watch_triggers 全表 rule_id 拉回来自己数。

### P2 若干（不展开，均有 file:line 证据）

- 市场级盯盘：market_watch_service._record 只落库不调 notifier（145 行文件，约 89-100 行），且 decide() 传 daily_wake_count=0（约 86 行）绕过预算门 → 市场级触发目前"不可见"。
- 元触发：落库后 _mark_reviewed 失败被吞 → 同日重复复核；expires_at 与 now 时区不一致时抛 TypeError 且不在 try 内，可能中断整轮 scan；统计失败返回 {} 会让全部规则被当"今日 0 触发"而误报 idle。
- 介入记账：repo 为 None 时 count_today 返 0 → 预算门静默失效；record 无异常保护，抛错会冒泡中断当前 tick。
- notifier：facade 抛错把 notified 置 False，但 engine 仍按 escalated 计预算/记账（engine.py:282-293）→ 通知失败也消耗当日额度；_broadcast_ws 直连 requests.post 绕过通知架构且 debug 级吞异常；max_retries/retry_interval 两个构造参数全仓无人使用。
- disposition.py:decide 内部用 datetime.now() 而不是调用方注入的 now（时间源不统一，增量门与经济门难以确定性测试）。
- 经济门形同虚设：wake_cost_yuan=1.0、k_economic=3.0 → 期望收益 ≥3 元即通过；而 expected_value 是"动作金额×3%~5%"，任何有点仓位的动作都远超。
- 指令文本 digest_service.py:248-249 硬编码四个账户名（违反 R-019 账户单一事实源）。
- daily_klines 量能数据在 2026-09-15 前后出现 30-100 倍断崖（002916：4,649,900 → 191,100）；均量基线因此失真，volume_surge 条件不可用（独立的数据质量问题，需数据侧另案）。
- 全仓 watch 相关 10 个文件里 TODO/FIXME/HACK = 0 处，但异常处理以"日志 + 返回 None/空"为主，缺陷表现为静默降级而非显式失败。

---

## 6. 与设计文档的偏差

| 文档 | 设计 | 现状 |
|------|------|------|
| RFC 011（分层提醒，状态：设计提案待评审） | L0/L1 直发飞书零 token；L2 唤醒 agent；5 类升级；规则生命周期 | 分层与升级已实现，但**升级判据有 bug**、L2 唤醒链处于影子模式 |
| RFC 013（触发处置状态机） | disposition 状态机（pending/escalated/handled/ignored/deduped/auto_observed/meta_review/expired） | 状态机已实现且落库；但终态收敛依赖 agent 处置，而 agent 没被调用 → 172 条卡在非终态 |
| RFC 014（价值生命周期闭环） | 摘要门、介入预算、持仓联动、市场级盯盘、元触发复核 | 组件齐全（P2-P8 都在），但 P0-2/P0-3 让闭环的两端断掉 |
| RFC 011 计划把 conditions 迁到 domain（condition_evaluator.py） | 领域层持有条件判定 | 未迁，判定仍在 application/services/watch_engine/conditions.py（分层与计划不一致，非功能缺陷） |

---

## 7. 建议的修复顺序

**第一梯队（先止血，改动小、影响大）**

1. 修 P0-1 升级判据：升级器绑定条件类型/metric；补一条"price_break 不得触发量能升级"的故障注入用例；顺带清掉库内 19 条已产生的假"量能异常"记录的语义标注（不改历史，只加说明或忽略）。
2. 给影子模式加到期自检：超过 48h 的影子运行提请裁决；同时决定摘要门真开还是关掉——**当前"挂着不生效"是最差状态**。
3. 修 P0-3 positions accounts：按账户清单/规则归属逐账户判定，退役动作 fail-closed + 告警。

**第二梯队（补齐断链与观测）**

4. 引擎指标出口（get_metrics 上 HTTP）+ 引擎存活告警（线程死/未启动/DISABLE 必须飞书告警，而不是只 log）。
5. 清 172 条积压：先用 /api/watch/triggers/digest 离线核对一份摘要样本，再决定真开摘要门——真开必须同步解决预算被假升级挤占的问题（依赖第 1 条）。
6. 规则创建入口补齐语义：watch_manage 支持 intent/action_hint/escalation_policy（或后端按 condition 推导合理默认值），否则 26 条无 intent 规则永远只能"观察"。

**第三梯队（结构治理）**

7. 状态可序列化 / 单例锁（消除多 worker 重复触发与重启丢闩锁）。
8. 规则健康度两份真相合并到 domain；清死代码。
9. 统计口径（limit 先过滤后分页、去掉全表拉取）。
10. 数据质量另案：daily_klines 量能断崖导致 volume_surge 不可用。

**可考虑的产品级问题**（超出"修 bug"，需用户拍板）

- 条件表达能力太弱（无均线/指标/事件/时段条件），与"盯盘引擎"的期望可能有量级差距；
- 通知是"每条触发都发"，靠 agent 后期治理规则来降噪——在 agent 未被唤醒的当下，等于只发不治；
- 缺控制台：用户无法在一个页面上看到"哪些规则在盯、哪条最吵、哪条该退役"。

---

## 8. 附录：可复核的证据命令

```sql
-- 规则画像
select coalesce(action_hint->>'trigger_level','(none)') lvl, count(*) from quant.watch_rules where enabled group by 1;
select coalesce(nullif(intent,''),'(empty)') intent, count(*) from quant.watch_rules where enabled group by 1;
-- 唤醒链是否活过
select * from quant.watch_digest_state;
-- 未处置积压
select disposition, count(*) from quant.watch_triggers where disposition in ('pending','escalated','meta_review') group by 1;
-- 误升级实证（detail.value 是现价，reason 却说量能异常）
select id, symbol, detail, disposition_reason from quant.watch_triggers where disposition='escalated' order by triggered_at desc limit 12;
```

```python
# 升级判据复现（venv 激活后在 quantsys-v2 根目录执行）
from domain.watch.models import WatchRule, QuoteData
from domain.watch.services.escalation_checker import EscalationChecker
import types
policy = {"auto_escalate": True, "price_deviation_pct": 5.0, "volume_ratio_multiplier": 2.0,
          "multi_rule_confluence": {"enabled": True, "window_seconds": 60},
          "max_triggers_per_window": {"count": 3, "window_minutes": 10}}
cond = {"type": "price_break", "params": {"price": 388.75, "direction": "below"}}
rule = WatchRule(id=162, symbol="002916", enabled=True, conditions=[cond], escalation_policy=policy)
print(EscalationChecker().should_escalate(rule, cond, QuoteData(symbol="002916", price=388.5),
      types.SimpleNamespace(value=388.5), recent_trigger_count=1, concurrent_trigger_count=1))
# -> 量能异常（388.5x vs 阈值1.5x），可能主力异动   ← 388.5 是股价，不是量比
```

---

*本报告为只读调研产物，未修改任何代码与数据，未产生任何委托。署名：investor / w-9b2b54f3。*