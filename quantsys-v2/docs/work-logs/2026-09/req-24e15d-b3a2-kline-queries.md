# REQ-24e15d 批次 B3-a2 —— daily_klines 查询收敛（4 处）

- **执行窗口**：w-32314d00（investor / 投资脑）
- **日期**：2026-09-14
- **范围**：3 个服务文件，4 处对 `quant.daily_klines` 的裸 SQL

---

## 1. 共同病灶：私有游标 + 双形态兼容分支

这 4 处的写法是同一套模板：

```python
cursor = self.kline_repo._get_cursor()      # 摸仓储的私有方法拿游标
cursor.execute(query, params)               # 裸 SQL 写在服务层
results = cursor.fetchall()
cursor.close()                              # 手工生命周期管理
if results and isinstance(results[0], dict): ...   # 还要兼容 dict / tuple 两种形态
elif results: ...
```

**服务层不该摸仓储的私有游标**，也不该为"结果可能是 dict 也可能是 tuple"写分支——
那是"这条路径到底走的哪个实现"没有定论的信号（实测：同一份代码里两种分支都留着，
说明历史上换过驱动/游标类型而没人敢删另一支）。

## 2. 改动

`KlineORMRepository` 新增 3 个方法：

| 新方法 | 替代 | 用在哪 |
|---|---|---|
| `has_bar_on_date(day)` | `SELECT EXISTS(... WHERE trade_date=%s)` | trading_day_guard |
| `get_trade_dates_map(symbols, start, end)` | `array_agg` 批量 + 逐只回退两段 SQL | data_gap_detector |
| `find_duplicate_trade_dates(symbol, start, end)` | `GROUP BY … HAVING COUNT(*)>1` | data_validator |

复用既有的 `get_latest_trade_date()`（trading_day_guard 的第二个子查询）。

关键取舍：`get_trade_dates_map` 把原来"批量 array_agg + 失败逐只回退"的两段 SQL 合成
**一次 ORM 查询 + Python 侧分组**，语义等价（无数据的标的仍得到空集合），
但不再需要两套兼容分支，也不再有手工游标。

## 3. 验证证据（真库）

- `TradingDayGuard._kline_stats(2026-09-11)` → `(True, '2026-09-11')`；
  `(2026-09-14)` → `(False, '2026-09-11')`（今天尚无日K，最近交易日正确）
- `DataGapDetector._batch_get_actual_days(['600519','000001','999999'], 09-01, 09-11)`
  → `{600519: 9, 000001: 9, 999999: 0}`（不存在的标的得到空集合 ✓）
- `DataValidator.detect_duplicates('600519', …)` → `{'has_duplicates': False, 'duplicate_dates': [], 'duplicate_count': 0}`
- **回归**：175 passed / 3 skipped / 1 failed
  （失败者是 `test_agent_sessions_parity::test_ai_diagnosis`，已用 HEAD worktree 复现确认为
  环境问题：测试环境无 LLM，路由返回 503 而断言 `<500`）
- `--gate` 退出码 0

## 4. 指标变化

| 指标 | B3-a 后 | B3-a2 后 | 变化 |
|---|---|---|---|
| cursor_execute | 87 | **83** | −4 |

三个文件全部 CLEAN。

## 5. 下一步

`signal_test_log.py`（9，需新建仓储）、`signals_async.py`（5+1）、`order_service.py`（3+2）、
`experience_accumulator` / `data_pipeline_service` / `portfolio_breaker_service`（各 2）、
`weekly_report_service` / `risk_check_service` / `strategy_weight_adjuster`（各 1，各自对应
signal_tracking / portfolio / strategy_performance 仓储）等。
