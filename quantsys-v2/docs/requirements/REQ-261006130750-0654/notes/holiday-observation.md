# 休市日 / 复市首日真实观察（REQ-261006130750-0654 · t4）

**观察目的**：证明「休市日不空转、复市首日照跑」在**真实运行的服务**上成立，而不只是单测绿。
**底线（本文件的自律）**：真实观察与单测证据**分开写**；窗口没取到就写「窗口未到/未取到」+ 原因，
**不得**用单测结果冒充观察（design/test-cases.md §3）。

---

## 0. 部署与生效时点（本次观察的前置）

| 项 | 值 | 证据 |
|---|---|---|
| 代码生效方式 | 随进程重启（两条线程由 FastAPI lifespan 启动） | `adapters/inbound/fastapi_app/orchestrator_bootstrap.py`（`start_orchestrator`） |
| 重启命令 | `launchctl kickstart -k gui/501/com.pi-investment.v2-api` | 2026-10-06 13:21:33 执行 |
| 重启后自检 | `curl -s http://127.0.0.1:5001/health` → `{"status":"ok","framework":"fastapi","version":"2.0.0"}` | 同一次执行 |
| 进程 | `launchctl list` 里 `com.pi-investment.v2-api` PID **61630** | 重启前为 86953（10-05 21:28 起） |

---

## 1. 2026-10-06（**今天·休市·周二**）：改后首日真实观察 ✅

> 说明：t4 卡原文要求的是 `10-07`（休市）与 `10-08`（复市首日）。今天 `10-06` 是**同性质的法定休市日**，
> 因此先落今天这一份完整观察；`10-07 / 10-08` 的窗口**尚未到达**（见 §3），未取到即明写。

### 1.1 改前基线（同一天、同一进程重启之前）

| 项 | 观察值 | 来源 |
|---|---|---|
| 盘中窗口对休市日放行 | `_in_intraday_window(2026-10-06 10:30) = True`、`(13:00) = True` | 本机探针（requirement.md E1） |
| 盘中检查被真的调用 | `IntradayMonitor().check(now=2026-10-06 10:30)` → `{'status': 'no_positions'}`（受监控账户 `rotation_main` 无持仓，止步早退） | 本机探针（E3） |
| 编排线程 | 8:00–17:59 每 60 秒空转调用一次 `daily_orchestrator_tick()`（内层 fail-closed 早退） | `daily_orchestrator.py:133-137` + 进程存活（10:05 起） |
| 台账 | `quant.scheduler_runs` 今日 4 行、`inprocess_job_runs` 0 行、`daily_orchestrator_state` 今日 0 行 | 本机 SQL |

### 1.2 改后实测（重启之后）

**命令**：`grep -o '"path": "[a-z_]*", "day": "[0-9-]*"' logs/api.log | sort | uniq -c`

```
   1 "path": "orchestrator_tick", "day": "2026-10-06"     ← 13:21:44（重启后第一轮 tick）
   1 "path": "intraday_monitor",  "day": "2026-10-06"     ← 13:30:46（盘中 :30 槽位）
```

**原始行（节选）**：
- `logs/api.log:9400`（13:21:44.780113+08:00）
  `{"path": "orchestrator_tick", "day": "2026-10-06", "is_trading_day": false, "source": "trading-calendar-holiday", "degraded": false, "reason": "交易日历判定为非交易日（来源 calendar_table：该日不在交易日历中）", "event": "orchestrator_trading_day_skip"}`
- `logs/api.log:9408`（13:30:46.460965+08:00）
  `{"path": "intraday_monitor", "day": "2026-10-06", "is_trading_day": false, "source": "trading-calendar-holiday", "degraded": false, "reason": "…", "event": "orchestrator_trading_day_skip"}`

**从这两行能直接读出三件事**：
1. **两条路径都真的走了新门**（不是"没跑因为我没在跑"）：`path` 两个取值各出现一次，
   说明循环确实进了两个分支、并各自做了日级判定；
2. **拦它的是日级门而不是时段**：`source=trading-calendar-holiday`（若因时段，`_in_*_window` 会直接 False、不会有这条日志）；
3. **去噪有效**：编排线程在 8:00–17:59 每分钟命中一次（到 13:31 已命中 ~10 次足以刷屏），
   实际只留 **1** 条；`(path, day)` 键一换天才重置。

### 1.3 写库面（"不再写"的证据）

**命令**：
```
psql -c "select max(updated_at) from quant.simulation_positions"
psql -c "select max(updated_at) from quant.simulation_account where account_name='rotation_main'"
psql -c "select count(*) from quant.daily_orchestrator_state where trade_date='2026-10-06'"
```

| 表 | 观察值 | 判读 |
|---|---|---|
| `quant.simulation_positions` | `2026-10-04 16:49:36.640306` | 今日**无**监控刷新（有持仓分支根本没被走到） |
| `quant.simulation_account`（`rotation_main`） | `2026-07-25 14:16:38.457999` | 同上 |
| `quant.daily_orchestrator_state`（`2026-10-06`） | `0` 行 | 编排线程未推进任何阶段（与改前一致：内层本来就早退） |

### 1.4 一个容易误判的节奏细节（留给复跑者）

循环按**线程启动时刻对齐**的 60 秒节拍判定窗口（本轮重启于 `13:21:33`，tick 落在 `:44` 秒），
所以 `13:30` 这个"整点槽位"实际在 **13:30:46** 才被判定。
**复跑时不要在 `:00:05` 就 grep 然后判"没生效"**——首轮探针就踩过这个坑（13:30:15 查为空，13:31:16 查有值）。

---

## 2. 与改前的对照（同一休市日，前后各一次）

| 面 | 改前（今日 13:21 之前） | 改后（今日 13:21 之后） |
|---|---|---|
| 编排线程 | 每 60 秒空转调用一次（内层早退） | 休市日**零调用**，只留 1 条跳过日志 |
| 盘中监控 | 每 :00/:30 被调用，`check()` 返回 `no_positions`（有持仓则会判止损止盈并写市值） | 休市日**不被调用**；旁路直调则返回 `non-trading-day` |
| 可见性 | 无留痕（"空转"无法从日志区分"没跑"） | 每条路径每天 1 条 `orchestrator_trading_day_skip`，五键齐 |
| 钱路完整性 | 交易日/降级日照跑 | **不变**（外层 fail-open；内层 fail-closed 一行未改） |

---

## 3. 未取到的窗口（如实登记，不用单测顶替）

| 窗口 | 状态 | 原因 |
|---|---|---|
| `2026-10-07`（休市·周三） | **窗口未到** | 观察当天为 `2026-10-06`，10-07 尚未到来 |
| `2026-10-08`（复市首日·周四） | **窗口未到** | 同上 |

**复跑清单（到日子直接跑，无需再改代码）**：
```bash
# ① 当天是否为休市（当天口径）
./venv/bin/python -c "from application.services.trading_day_guard import TradingDayGuard; v=TradingDayGuard.check(); print(v.is_trading_day, v.source, v.degraded)"

# ② 10-07（休市）：两条路径各应各留 1 条跳过留痕
grep -o '"path": "[a-z_]*", "day": "2026-10-07"' logs/api.log | sort | uniq -c   # 期望 2 条（orchestrator_tick / intraday_monitor）

# ③ 10-07（休市）：写库面不得被监控刷新
psql -h 127.0.0.1 -U mac -d quant_investment -c \
  "select max(updated_at) from quant.simulation_positions"                        # 期望 < 2026-10-07

# ④ 10-08（复市首日）：**不得**出现跳过留痕
grep -c '"day": "2026-10-08".*orchestrator_trading_day_skip' logs/api.log          # 期望 0
#    并确认盘中路径恢复真实执行（status != skipped）
```

**纪律**：以上四条必须在**当天**跑；跑不到就继续标「窗口未到」，
不得把 `tests/api/test_orchestrator_trading_day_gate.py` 的 12 passed 当作替代证据（那是单测面）。

---

## 4. 窗口处理与部署的两条人工裁定（2026-10-06）

| 编号 | 原话来源 | 裁定 | 影响 |
|---|---|---|---|
| W-1 | 本窗口会话消息（2026-10-06，用户回答双问弹框）原话：「等窗口：保留 t4 未完成，10-07、10-08 各跑一次复跑清单后再收口（推荐）」 | **保留 t4 未完成**；不拿 10-06 观察或单测顶替 10-07 / 10-08 的窗口；需求停在 implementing，待两天窗口跑完再收口 | t4 不收尾；需求不进入 accepting |
| W-2 | 本窗口会话消息（2026-10-06，同一次弹框）原话：「认可，休市日重启影响最小就这样（推荐）」 | 认可 13:21:33 的 `launchctl kickstart -k`（PID 86953 → 61630）——选在休市日重启，影响最小 | 本次部署动作获批；后续涉生产重启仍按此口径先征询 |

> 这两条是**实施阶段的窗口/部署裁定**，不改已确认的需求文档（不改 FR、不改边界），
> 故记在本观察档与卡片汇报里，不回写 requirement.md 的 D-x 表（避免让已确认产物反复重提）。

---

## 5. 收口裁定（2026-10-06 · 用户改主意）

| 编号 | 原话来源 | 裁定 | 影响 |
|---|---|---|---|
| **W-3** | 本窗口会话消息（2026-10-06，用户直接消息）原话：「先完成这个项目」 | **就地收口**：以 10-06（同性质法定休市日）的完整观察作为休市日证据；**10-07 / 10-08 两个窗口如实标注「窗口未取到」**，不用单测顶替、也不假装取到过 | t4 收尾；需求进入验收；复跑清单（§3）保留在案，日后可补 |

**因此本节的口径变化一句话**：W-1（等窗口）被 **W-3（就地收口）取代**；W-1 的原话与理由仍保留在 §4，便于追溯"为什么中途换了口径"。

**收口时点的事实（不美化）**：
- 已有证据：10-06 当天两条真实跳过留痕（13:21:44 `orchestrator_tick`、13:30:46 `intraday_monitor`，
  均 `source=trading-calendar-holiday` / `degraded=false`）、写库面零变化、12 条用例 + 3 次注入证红。
- **缺的证据**：10-07 休市日的第二次独立观察、10-08 **复市首日不跳**的实证
  （后者尤其关键：门最怕的就是把复市首日误跳）。
- 该缺口**不因收口而消失**——它被显式写在验收材料与本节里，属已知未取窗口，不是"已验证通过"。


