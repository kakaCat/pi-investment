# 编排器账户通用化（① 只读动作 + ② 幂等键形态）

- 需求：REQ-24e15d（关联修复：**非**裸 SQL 迁移本体，由 B4-c5 复盘时的唤醒路由分析触发）
- 窗口：w-32314d00（投资脑 investor）
- 日期：2026-09-14
- 改动文件：`quantsys-v2/application/services/daily_orchestrator.py`
  与 `quantsys-v2/tests/test_orchestrator_account_generic.py`（由 `test_orchestrator_account_unify.py` git mv + 改写而来）

---

## 1. 为什么账户是写死的（先回答"这是不是疏忽"）

不是疏忽，是一次**主动的产品决定**，有提交与测试为证：

- `1ccbead3`（2026-07-25）"feat: orchestrator 各阶段账户统一为 agent_virtual"
  的 diff 把 `'rotation_main'` 改成 `'agent_virtual'`，共 4 处，并留下注释
  `# 唯一交易账本（2026-07-24 盈利闭环改造）`；
- 同批附带的 `tests/test_orchestrator_account_unify.py` 用 3 个断言把它锁死。

当时合理：目标是让 agent-ts 用虚拟仓证明盈利能力，"唯一账本"让成绩干净（一个账户、一条净值曲线）。
后来变成缺陷：系统此后长出了 agent_brain / v13 / v14 / v15 / chip / user_main 等账户，
而"唯一账本"的假设没跟着变 —— 账户级**维护**动作只覆盖 agent_virtual。
2026-09-05 已先修 T+1 结转（`settle_t1_all`，事故样本：investor 自持 002007 华兰生物 8/26 买入后
10 天"可卖"恒为 0），本批补齐余下三处。

## 2. 本批改了什么

### ① 账户级只读/可控动作改为遍历 active 账户

| 位置 | 改前 | 改后 |
|---|---|---|
| `_phase_market_close` 估值更新 | 只建 `PaperTradingEngine(agent_virtual)` | 逐 active 账户建引擎并重估持仓 |
| `_phase_post_market` 净值快照+绩效 | 同上 | 逐 active 账户 `take_daily_snapshot` + `get_performance_report` |
| `_phase_review` 当日成交取数 | 只取 `TRADING_ACCOUNT` | 逐 active 账户取数 |

账户口径**唯一来源** = `SimulationAccount.status == "active"`（新增常量 `ACCOUNT_STATUS_ACTIVE`），
与 `settle_t1_all` / `list_accounts(status=...)` 同一口径，不另立一套。
取不到清单时回退 `[TRADING_ACCOUNT]` —— 任何异常下都不比通用化之前更差。

顺带去掉三处重复的 "注入优先否则工厂解析" 样板（收敛为 `_sim_repo()`）。

### 刻意不改的边界

- **市场级动作仍然只跑一次**：数据更新 / 风格检测 / 信号生成 / 因子计算。它们是全市场级的，
  跑 N 遍是浪费且可能重复生成信号。**所以正确改法是"在阶段内部把账户级动作改成循环"，
  不是"起 N 个编排器实例"**（`orchestrator_name` 更适合"不同节拍的编排"）。
- **对外事件契约本批不动**：`signals_ready` / `daily_review` 的载荷口径与投递目标保持原样，
  见 §4 的 ②③ 耦合说明。

### ② 复盘唤醒幂等键：全局布尔 → per-account 集合

改前 `context['daily_review_notified'] = True`（2026-09-08 引入，修 9/2 推 3 次 / 8/13 推 4 次），
改后 `{'<account>': True, ...}`，配 `_notified_accounts()` / `_mark_review_notified()` 两个原语，
**并兼容旧布尔状态行**（升级前遗留的 `True` 映射为 `{TRADING_ACCOUNT}`，不会因形态变更重推一次）。

另外把幂等门**提到取数之前**：`resume_from_breakpoint` 每次进程重启都会重跑阶段，
已推送时原来仍会白跑一遍全账户取数。

## 3. 本批顺带修掉的静默缺陷（发现即修，非计划内）

**`daily_review` 载荷里的 `today_trades` 恒为空列表。**

原实现：

    trades = sim_repo.get_trades_by_account(TRADING_ACCOUNT, ...)
    today_trades = [
        {'symbol': t.get('symbol'), 'action': t.get('side'), 'amount': t.get('amount')}
        for t in (trades or [])[:10]
    ]

而 `get_trades_by_account` 返回的是 **`SimulationTrade` ORM 对象**（不是 dict）：

- ORM 对象没有 `.get()` → 第一只元素就 `AttributeError`；
- 且字段名是 `action` 不是 `side`（模型 `simulation.py:255`）；
- 异常被紧随其后的裸 `except Exception: pass` 吞掉 → `today_trades` 恒为 `[]`。

实体证据（真实 ORM 实例，非推断）：

    >>> SimulationTrade(id=167, symbol='601600', action='SELL', shares=400, price=9.38)
    >>> hasattr(trade, 'get')  -> False
    >>> hasattr(trade, 'side') -> False

负向对照（把新测试跑在旧实现上）：

    assert payload["today_trades"] == []          # 旧实现，即使当日确实有成交
    AssertionError: assert [] == [{'symbol': '002007', ...}]

## 4. 关键发现：② 与 ③ 耦合，不能单独落地

我原计划是 "① 只读 → ② 幂等键 → ③ 事件载荷+路由" 三步走。**实现时发现 ② 不能单独产生行为价值，
且单独落地会引入新缺陷**：

- 只做 ③（逐账户投递、幂等键仍是全局布尔）：**第一个账户推完就把标志置 True，其余账户永远收不到**；
- 只做 ②（per-account 门位、投递仍是单次）：**同一事件会被推 N 次** —— 正是 2026-09-08 修掉的重复推送。

所以本批的 ② 落地为"**数据形态 + 门位口径**改造，行为等价"，并把"投递恒为 1 次"写成测试固定住
（`test_review_invokes_notifier_once_not_per_account`：3 只账户 → `notify_agent` 仍只调 1 次）。
**它的价值要在 ③ 落地时才显现**：③ 只需把门位那行换成逐账户循环即可，不会踩上述两个坑。

③ 的内容（待裁决，涉及跨系统契约）：`signals_ready` / `daily_review` 逐账户载荷 + 经
已存在的 `WatchDeliveryPolicy.resolve(account, category)` 路由（含 `WATCH_ACCOUNT_AGENT_MAP`）+ 传 `target=`。
现状：`_notify_agent` 不传 target → 全投 agent-dh（日志实证 `{"notify_event": "pre_market_summary", "target": "agent-dh", "url": "http://127.0.0.1:13080"}`），
而信号链是 agent_virtual 的数据、agent-ts 才是预期消费方。

## 5. 实测发现：估值价格滞后（**未改**，仅记录）

收盘阶段取价走 `get_latest_daily_klines_batch`（最近一根日线，非当日实时价）。实测（2026-09-14 12:45 探针）：

    全部持仓 symbol 的最新日线 trade_date = 2026-09-11（上周五）
    （今日 K 线由 evening_pipeline 20:30 落库）

即 **15:00 收盘阶段拿到的是上一交易日收盘价，写进当日快照 = "旧价标新日"**。

两条边界，本批**刻意不动**：

1. 该滞后性**原已存在**于单账户路径（原实现同样用 `get_latest_daily_kline`），本批只是把适用账户从 1 个扩到 7 个，
   **未新增也未消除**；
2. 项目已有明确标准（`EquitySnapshotJob` docstring，2026-09-13）："宁可当日不写，也不写错" ——
   但直接给编排器加同样的 `_has_bar` 跳过门会**改变 agent_virtual 的既有行为**，超出本批授权，
   故仅登记，交裁决。

（另注：`equity_snapshot_daily` 15:35 与编排器 POST_MARKET 15:30 是两条写同一张表的路径，
均为 upsert（同账户同日覆盖写），实际取值可能互相覆盖 —— 同属该待裁决项。）

## 6. 验证证据

1. **单元/契约**：`tests/test_orchestrator_account_generic.py` 14 passed。
2. **编排器测试簇**：14 + 2 + 15 + 6 + 3 + 3 = **37 passed**
   （`test_orchestrator_account_generic / test_orchestrator_signals_ready / e2e/test_daily_orchestrator /` 
   `api/test_orchestrator_bootstrap / services/test_collect_signals_orm_compat / test_scheduled_jobs_account_value`）。
3. **负向对照（关键）**：把新测试原样复制到 `HEAD` 的临时 worktree 上跑 →
   **13 failed / 1 passed**；唯一通过的是**故意要求两版都通过**的向后兼容守卫
   （`test_review_skips_on_legacy_boolean_state_row`）。证明测试有牙齿，不是自证。
4. **真实数据探针（只读）**：

    active accounts: [user_main_simulation, agent_virtual, v15_simulation, chip_simulation,
                      agent_brain, v13_simulation, v14_simulation]
    trades_by_account(2026-09-11):
      user_main_simulation [{symbol: 601600, action: SELL, amount: 3752.0}]
      agent_brain         [{symbol: 601600, action: SELL, amount: 9380.0}]
      v13_simulation      [{symbol: 300889, action: SELL, amount: 8740.0}]
    get_latest_daily_klines_batch: 12/12 持仓 symbol 均有价（close 取自 2026-09-11）

   注意：探针**未调用** `_revalue_positions` 的真实写路径 —— 它会在交易日午间用"上周五收盘价"
   覆盖账户持仓现价。写路径由假引擎（`_FakeEngine`）单测覆盖，真实数据只验证读路径。

## 7. 风险与回滚

- 回滚 = 单文件 revert + 测试文件还原。无数据迁移、无 schema 变更。
- 幂等性：`take_daily_snapshot` 走 `upsert_equity_snapshot`（同账户同日覆盖写），
  `update_position_prices` 只覆盖传入的 symbol，重跑不产生重复行。
- 单点放大：估值/快照由 1 只账户扩到 7 只，DB 写次数上升；取价已收敛为**一次批量查询**
  （原实现是"每账户每持仓一次"）。

## 8. 全量回归（广度验证，2026-09-14 13:06–13:51）

脚本 `/tmp/regress_orch.sh`：先跑 `HEAD~` 的临时 worktree（`/tmp/wt-orch-nc`，detached at `44567fec`，**本批改动之前**），
再跑主树；两边同一命令 `pytest tests/ -q --ignore=tests/test_ml -p no:cacheprovider`，各自抽 `^(FAILED|ERROR)` 行、`sort -u`，最后 `comm`。

**先修了比对口径本身**：第一版把 pytest 日志捕获行（`ERROR    logger:file:line {...}`）也当结果行收进来，
而这类行含**绝对路径**（`/private/tmp/wt-orch-nc/...` vs `/Users/yunpeng/pi-investment/...`）与**时间戳**，
于是两边天然全不相等 → `comm` 输出 40 + 48 条噪声。加过滤 `^(FAILED|ERROR) [^ ]` 后干净：
基线 384 条、本批 376 条。

### 8.1 差异（按**失败集合逐条 diff**，不比数量）

**消失 13 条 —— 全部是新增测试文件 `test_orchestrator_account_generic.py`：**

    GONE = 该文件的 13 个用例，在基线（旧实现）上 13 failed，在本批上 13 passed

即**负向对照在整套回归里复现**：这些测试在旧实现上确实会挂，不是自证。

**新增 5 条：**

    FAILED tests/infrastructure/data_providers/providers/test_sector_providers.py::TestSectorStocks::test_no_proxy_bypass
    FAILED tests/test_api_smoke.py::test_backtest_run
    FAILED tests/test_api_smoke.py::test_portfolio_positions
    FAILED tests/test_api_smoke.py::test_risk_metrics
    FAILED tests/test_api_smoke.py::test_simulation_trade_sell_validation

### 8.2 对新增 5 条的归因：**判为环境/瞬时，不判为本批引入**

证据（按强度排序）：

1. **在本批代码上复跑 5 条 → 全过**；再整文件复跑 `test_sector_providers.py` + `test_api_smoke.py` → **15 passed / 5.94s**（同库、同 `:5001`）。同一个二进制不可能既引入又自愈；
2. **`test_api_smoke.py` 测的是 `:5001` 上的活服务**（`BASE_URL = http://localhost:5001`，走 HTTP），
   而该进程在**本轮跑到一半时被重启过**（实测 13:52 时 uptime 仅 9 分钟 ⇒ 约 13:43 起的新进程），
   基线那一轮（13:06–13:26）跑的是**另一个进程**。两轮**不是同一个被测对象**，本就不可直接比；
3. `test_no_proxy_bypass` 是**纯单测**（`patch('requests.get')`，只断言 `proxies == {'http': None, 'https': None}`），
   且当前**无任何 proxy 环境变量**；它不 import 编排器，与本批唯一源码改动
   （`application/services/daily_orchestrator.py`）无调用关系；
4. 本批改动面 = 1 个服务文件 + 1 个测试文件，5 条失败用例**无一**触及账户/编排路径。

**诚实标注**：无法给出"失败原因"的原文 —— 见 §8.3。故此为**高置信度归因，不是证明**。

### 8.3 本比对方法的两个缺陷（下次必须改）

1. **脚本把失败原因删掉了**：`sed "s/ - .*//"` 让 `FAILED tests/x.py::y - AssertionError: ...` 只剩用例名，
   于是**新增失败无法从产物里诊断**，只能靠事后复跑。应保留原因到**单独一份**文件（只存新增项的原因即可）。
2. **把活服务依赖的用例混进了 worktree-vs-主树 的比对**：`test_api_smoke.py` 这类用例测的是
   `:5001` 上跑的**主树代码**，对 worktree 侧而言两边被测对象相同、且与"本批源码"无关；
   一旦服务在比对期间重启，结论随机翻转。此类用例应**排除**或改用固定 server 实例。
