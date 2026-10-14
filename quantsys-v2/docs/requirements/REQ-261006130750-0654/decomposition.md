# REQ-261006130750-0654 · 拆分计划

**需求**：[requirement.md](requirement.md) · **设计**：[design/](design/)（architecture / interfaces / data-model / test-cases / use-cases，均已确认）
**侧**：backend（无 UI，无原型锚点）
**一句话目标 + 做法**：给 v2 剩下的第 ④ 条日级判据路径接上既有唯一真源交易日门——
在编排循环加 **A 层预过滤**（休市日零调用）、在 `IntradayMonitor.check()` 首部加 **B 层权威门**
（旁路调用也拦得住），判据一律 `should_skip('trading-days', now)`（fail-open）；
窗口函数语义、内层钱路 fail-closed、表结构与开关**一律不动**；最后用一次性单测 +
休市日/复市首日真实观察收口。

## 1. 代码层面变更盘点（对照需求 + 设计）

| 动作 | 文件 / 符号 | 说明 |
|---|---|---|
| **修改** | `application/services/intraday_monitor.py` · `IntradayMonitor.check()` | 增可选入参 `now`；时段判定**之后**插权威日级门；新增常量 `SKIP_REASON_NON_TRADING_DAY`；`_is_trading_time` docstring 指向新门（语义不变） |
| **修改** | `adapters/inbound/fastapi_app/orchestrator_bootstrap.py` · `_monitor_loop`（+ 新增模块级 `_should_run_today` / `_LAST_SKIP_LOG`） | 两个分支前各插一次日级预过滤；跳过日志按 `(path, day)` 去噪 |
| **新增** | `tests/api/test_orchestrator_trading_day_gate.py` | 12 条用例 + 假绿防线（test-cases.md T1–T13 的落地） |
| **新增** | `docs/requirements/REQ-261006130750-0654/notes/holiday-observation.md` | 休市日 / 复市首日真实观察留档 |
| **不动** | `application/services/trading_day_gate.py`、`trading_day_guard.py`、`daily_orchestrator.py`、`infrastructure/jobs/monitor_jobs.py`、窗口函数 `_in_orchestrator_window` / `_in_intraday_window` | 唯一真源、钱路 fail-closed、内层阶段机、转发函数、既有契约面 |
| **删除** | —— | 无 |

**无迁移 / 无 DDL / 无开关**（data-model.md §1）：数据侧唯一变化是休市日**少写**
`quant.simulation_positions` / `quant.simulation_account`。

## 2. 批次与依赖

```
批次 1（可并行，二者互相独立）
  t1  intraday_monitor.check() 权威日级门        （application 层）
  t2  编排循环 A 层预过滤 + 跳过日志去噪          （adapters 层）
批次 2
  t3  回归锁与假绿防线（新建用例文件）            depends_on: t1, t2
批次 3
  t4  真实观察（2026-10-07 休市 / 10-08 复市首日）depends_on: t3
```

- 无前向引用：`t3` 引用已定义的 `t1`/`t2`，`t4` 引用 `t3`。
- 契约先行由**设计阶段**满足（interfaces.md §3.2/§3.4 已把签名与返回形状定死），
  故不再单列"契约卡"——避免出现两张卡同时改同一个文件、互相冲突。

## 3. 任务表

> 「关联 D-x」：D-2 = 范围收口到 v2 侧 ④ 路径；D-1 = 「27 次」口径待对齐（不据此扩范围）。
> 「原型锚点」：本需求 `side=backend`，无 UI → 全部不适用。

| key | 标题 | phase / side | depends_on | 关联 D-x | 原型锚点 | footprint（files/anchors/chars） | DU |
|---|---|---|---|---|---|---|---|
| t1 | 给 `IntradayMonitor.check()` 加权威日级门 | implement / backend | — | D-2 | 不适用 | 1 / 5 / 1200 | 4.10 |
| t2 | 编排循环加 A 层日历预过滤与跳过去噪 | implement / backend | — | D-2 | 不适用 | 1 / 5 / 1100 | 4.05 |
| t3 | 回归锁与假绿防线（新建用例文件） | test / backend | t1, t2 | D-2 | 不适用 | 1 / 13 / 2500 | 8.75 |
| t4 | 休市日 / 复市首日真实观察留档 | test / backend | t3 | D-1, D-2 | 不适用 | 1 / 4 / 900 | 3.45 |

### t1 · 给 `IntradayMonitor.check()` 加权威日级门

- **implementation**：改 `application/services/intraday_monitor.py`。
  ① 模块级新增 `SKIP_REASON_NON_TRADING_DAY = 'non-trading-day'`；
  ② `check()` 签名改为 `def check(self, now: Optional[datetime] = None) -> Dict[str, Any]`（缺省 `datetime.now()`，向后兼容）；
  ③ **在既有时段判定之后**插日级门：`skip, info = should_skip('trading-days', now)`，`if skip:` 立即返回
  `{'status': 'skipped', 'reason': SKIP_REASON_NON_TRADING_DAY, 'timestamp': now.isoformat(), 'trading_day': info}`，
  **不得**构造 `PaperTradingEngine`、不得读持仓/价格、不得写市值；导入用
  `from application.services.trading_day_gate import should_skip`（同层，合法）；
  ④ 顺带把 `_is_trading_time` docstring 里"日级仍由外层节拍闸门把关"改为指向本门（**逻辑一行不改**）。
  顺序不可调：日级门放时段**之后**，保证新分支只覆盖"原本会真干活"的时刻（严格增量，interfaces.md §3.3）。
- **acceptance**（可执行、可证伪）：
  1. `./venv/bin/python -m pytest tests/api/test_orchestrator_trading_day_gate.py -q -k "intraday_holiday or intraday_trading_day"` → 全过；
  2. 直调探针：`./venv/bin/python -c "from application.services.intraday_monitor import IntradayMonitor; from datetime import datetime; m=IntradayMonitor(); print(m.check(now=datetime(2026,10,6,10,30)))"`
     → 输出含 `'status': 'skipped'`、`'reason': 'non-trading-day'`、`trading_day.source == 'trading-calendar-holiday'`；
  3. 反证：`m.check(now=datetime(2026,10,6,20,0))` → `reason == 'not trading time'`（**不是** `non-trading-day`）；
  4. `./venv/bin/python -m pytest tests/test_market_session_policy.py -q` → 全过（`_is_trading_time` 语义未变）；
  5. `grep -c "force" application/services/intraday_monitor.py` → 0（不做人工旁路参数，use-cases.md §7）。

### t2 · 编排循环加 A 层日历预过滤与跳过去噪

- **implementation**：改 `adapters/inbound/fastapi_app/orchestrator_bootstrap.py`。
  ① 模块级新增 `_LAST_SKIP_LOG: Dict[str, str] = {}` 与
  `_should_run_today(now: datetime, *, path: str) -> Tuple[bool, Dict[str, Any]]`：
  内部**只调** `from application.services.trading_day_gate import should_skip`（`'trading-days'`），
  返回 `(not skip, info)`；`skip` 为真时按 `(path, day)` 去噪记一条
  `logger.info('orchestrator_trading_day_skip', path=..., day=..., is_trading_day=..., source=..., degraded=..., reason=...)`；
  **函数内不得出现 `weekday()`、不得直查 `trading_calendar`、不得抛异常**；
  ② `_monitor_loop` 两个分支内各插一行判定（`path` 取 `'orchestrator_tick'` / `'intraday_monitor'`），
  仅当 `run` 为真才调用对应 `monitor_jobs.*`；既有 `try/except` 与 `finally: close_session()` **保持原样**；
  ③ 窗口函数 `_in_orchestrator_window` / `_in_intraday_window` **一字不改**。
- **acceptance**：
  1. `./venv/bin/python -m pytest tests/api/test_orchestrator_bootstrap.py -q` → 全过（契约不变）；
  2. `./venv/bin/python -m pytest tests/api/test_orchestrator_trading_day_gate.py -q -k "orchestrator"` → 全过（休市日零调用 / 交易日照调）；
  3. 静态：`grep -c "should_skip" adapters/inbound/fastapi_app/orchestrator_bootstrap.py` → ≥2；
     `grep -cE "weekday\(|SELECT|trading_calendar" adapters/inbound/fastapi_app/orchestrator_bootstrap.py` → 仅命中 `_in_orchestrator_window` / `_in_intraday_window` 里**既有**那 1 处 `weekday()`（新增逻辑零命中）；
  4. 去噪：同一 `path`+`day` 连调两次 `_should_run_today` → 日志仅 1 条（用例断言）；
  5. 通知零外发：`notify-guard intercepted=N egress=0`（跑 t3 用例时一并见证）。

### t3 · 回归锁与假绿防线（新建用例文件）

- **implementation**：新建 `tests/api/test_orchestrator_trading_day_gate.py`，实现 test-cases.md 的
  T1–T13：桩**打在 `application.services.trading_day_gate.TradingDayGuard`**（本仓打桩点规则），
  覆盖休市日跳过（含 `PaperTradingEngine` 未被构造）、交易日对照、降级 fail-open、门自身异常照跑、
  未来日反例锁（`check('2026-10-07').source == 'future'`）、编排 tick 休市日零调用 / 交易日照调、
  静态对账、打桩点证伪、日志去噪、窗口语义回归（复用既有断言口径）、时段优先、通知零外发。
  另按 test-cases.md §4 做**反向注入演练**（至少 ③ 降级跳过与 ⑤ 未来日误判两处），
  证明门会红后再复原（注入过程写进卡片汇报，不留在仓库）。
- **acceptance**：
  1. `./venv/bin/python -m pytest tests/api/test_orchestrator_trading_day_gate.py -q` → 全过（≥12 条）；
  2. `./venv/bin/python -m pytest tests/api/test_orchestrator_bootstrap.py tests/test_market_session_policy.py tests/test_trading_window_guard.py tests/test_scheduler_trading_day_gate.py tests/test_daily_jobs_trading_day_gate.py -q` → 全过（同族三条路径不被带坏）；
  3. 反向注入 ③：把门改成 `degraded` 也跳过 → 至少 1 条用例变红；复原后全绿；
  4. 反向注入 ⑤：把休市日用例改成用 `check('2026-10-07')` 当判据 → 变红；复原后全绿；
  5. `notify-guard` 会话末输出 `egress=0`。

### t4 · 休市日 / 复市首日真实观察留档

- **implementation**：新建 `docs/requirements/REQ-261006130750-0654/notes/holiday-observation.md`，记录
  ① `2026-10-07`（休市）当天：`grep -c "orchestrator_trading_day_skip" logs/api.log`、事件里的
  `source` / `degraded`、`quant.simulation_positions` 与 `quant.simulation_account` 的 `updated_at`
  是否被刷新、盘中返回是 `non-trading-day`（对照 `2026-10-06` 的 `no_positions` 基线）；
  ② `2026-10-08`（复市首日）：两条路径恢复（无跳过留痕、`status != 'skipped'`）；
  ③ 如实登记窗口未取到的情况（若实施晚于 `10-08`，写明"窗口未取到"，
  **不得**用单测冒充观察 —— test-cases.md §3）。
- **acceptance**：
  1. 观察文件存在，且含上述三条（各带命令 + 原始输出摘要）；
  2. `2026-10-07` 的 `orchestrator_trading_day_skip` 计数 ≥1 且 `source='trading-calendar-holiday'`；
  3. `2026-10-08` 当日日志该事件计数 = 0；
  4. 若窗口缺失：文件里出现明确的"窗口未取到"与原因，且**不**出现把单测结果写成观察结论的句子。

## 4. 容量纪律（一轮装多少：先算，再切）

- 口径：`detailUnits = files×1 + anchors×0.5 + chars/2000`，容量缺省 **16 DU**
  （权重与容量只在 `src/domain/limits.ts` 定义一次，本计划不另抄一套）。
- 核算：t1 = 4.10 / t2 = 4.05 / t3 = 8.75 / t4 = 3.45 —— **全部 ≤ 16 DU，无超容量卡**
  （故本计划不含任何「⚠️超容量」标记）。
- 拆卡依据：**按文件与层切**（`application` 卡、`adapters` 卡各自独立可验、可单独回滚），
  而不是把两个文件塞进一张卡——t1/t2 因此可并行且互不冲突（architecture.md §8 的部分回滚即依赖此切法）。

## 5. 边界校验（不超范围、卡可独立验收）

- 每张卡只凭卡片即可开工：implementation 点到了**具体文件 + 符号 + 插入位置**，
  acceptance 全是可跑命令 + 期望输出；**零会话历史**的新窗口也能执行。
- 不二次创作设计：本计划的插入位置、签名、返回形状、日志事件名**逐字来自** interfaces.md；
  若实施中发现设计有误（例如 `check()` 的调用方比 R3 记载的多），**回设计阶段**改设计后重新提交计划，
  不在拆分/实施阶段私改。
- 范围外事项**不建卡**（requirement.md「后续线」）：agent-ts 盘中决策任务、交易日历自动补刷、
  今日 `data_validator` 报错、②③ 既有门的任何改动。

## 6. 不做什么（照抄设计边界，防范围蔓延）

1. 不改窗口函数语义与签名；不改 `tests/api/test_orchestrator_bootstrap.py` 既有断言。
2. 不改 `TradingDayGuard` / `should_skip` 的判定语义与三值策略；`trading_day_gate.py` 零改动。
3. 不改 `daily_orchestrator` 的内层 fail-closed 守卫与阶段机。
4. 不新增表/列/迁移/开关/环境变量；不新增对外接口；不新增第三方依赖。
5. 不加"休市日人工强制"后门（use-cases.md §7）。
