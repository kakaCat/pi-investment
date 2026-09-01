# quantsys-v2 路由 404 修复：8101a666 DataService 迁移遗漏（2026-09-01）

## 现象

用户观察到 watch 推送触发的 Agent 会话「没有用工具」，调查发现实际调用了 18 次工具，但 `data_fetch_quote` 与 `risk_controller stop_loss` 全部返回 HTTP 404（接口不存在）。quantsys-v2 健康检查 `/api/health` 始终 200，掩盖了路由缺口。

## 根因链

1. **commit 8101a666**（2026-08-31 "remove DataService god-object"）删除了 `application/services/data_service.py`，迁移了 12 个路由模块，但 **漏掉了 `stock_async.py`**（git show --stat 的迁移清单中无此文件）。
2. `stock_async.py` 首行 `from adapters.inbound.fastapi_app.shared import (ds, ...)` → `ds` 在 fastapi shared.py 中不存在（8101a666 已从 `adapters/shared/__init__.py` 移除）→ **ImportError**。
3. `main.py:641` 用 try/except 包裹 `import stock_async`，失败只 `logger.warning` 不中断 → **整个模块不挂载，`/api/stock/*` 全部 404**，而 health 正常。
4. `ds` 还坏在 3 层：fastapi shared.py 缺 `ds`；`adapters/shared/services.py` 的 `_LazyServiceModule.ds` → `get_data_service()` → `ServiceFactory.get_data_service()` 不存在（AttributeError）。

## 受影响范围（全部同根因）

以下模块 import `ds` 失败 → 路由全部 404，同样被 try/except 静默吞掉：

| 模块 | ds 使用 | 修复 |
|---|---|---|
| `stock_async.py` | 15 处真实调用（kline/stock/factor/portfolio） | 迁移到 `get_stock_repo()/get_kline_repo()/get_factor_repo()/get_portfolio_repo()`，处理 3 个签名差异 |
| `risk_async.py` | import 未使用 | 移除 import |
| `scheduler_async.py` | `_SchedulerService(ds=ds)`（且 SchedulerService `__init__` 无参，传参必 TypeError） | 改 `_SchedulerService()` |
| `watchlist_async.py` / `orders_async.py` / `pipeline_async.py` | import 未使用 | 移除 import |
| `application/services/order_service.py` | `_update_position_on_buy(ds, order, ...)` 调用传 5 参、定义只有 4 参（NameError） | 去掉 `ds` 参数 |

## 关键签名差异（stock_async 迁移时踩坑）

- `get_minute_klines(symbol, start_datetime, end_datetime)` — **无 fields 参数**，需去掉
- `get_latest_daily_kline(symbol)` — 返回 **polars DataFrame 单行**（非 dict），需 `to_dicts()[0]`
- `ds.factor.get_available_factors(symbol)` → `factor_repo.get_factor_names()`（无 per-symbol 参数，返回 List[str]）
- `ds.stock.save(dict)` → 无对应方法；`/api/stocks/add` 改为 get_by_symbol + create/update 手工 upsert
- `_SchedulerService(ds=ds)` → `__init__(self)` 无参

## 验证结果（修复后重启 quantsys-v2，PID 44906）

```
GET  /api/stock/002241/quote?source=realtime → 200  {price:24.25, changePct:3.15, source:tencent}
GET  /api/stock/002241/klines?days=5        → 200
POST /api/stock/002241/risk/position-size   → 200  {recommendedSize:20000}
POST /api/stock/002241/risk/stop-loss       → 200  {stopLoss:22.08, pct:8%}
POST /internal/scheduler/webhook            → 422 (路径存在,缺参)
GET  /api/trades/list                       → 200
POST /api/orders/algo-execute              → 400 (路径存在,参数校验)
```

OpenAPI 中 stock 相关路径 51 个全部恢复（修复前为 0）。启动日志仅剩 3 个预存在失败：`p1_batch_async / p2_batch1_async / p2_batch2_async`（attempted relative import，与本次无关）。

## 教训

1. **try/except 静默吞 import 失败 = 路由黑洞**：main.py 的 optional 路由机制让健康检查 200 掩盖全部 404。任何路由模块 import 失败都应可观测（至少聚合到 `/api/health` 的 degraded 字段）。
2. **大面积重构后必须扫全仓引用**：8101a666 迁移 12 个模块但漏了 2 个路由 + 1 个 service 的调用点，靠的是"迁移清单靠手写"。重构后应 grep 旧符号（如 `\bds\.`）全仓清零。
3. **健康检查应校验 OpenAPI 路由数**：`/api/health` 只查进程存活，不查路由表完整性。建议 health 响应包含关键路径抽样（quote/klines/risk）或路由计数。

## 遗留

- `create_watch_engine` 告警：某处注册表指向 `infrastructure.factories.create_watch_engine`（实际在 `application/services/watch_engine/factory.py`），WatchEngine 功能正常，预存在，待查。
- 3 个 p1/p2_batch 模块 import 失败（relative import），预存在。
- agent-dh 侧 watch 触发会话已可正常使用 data_fetch_quote / risk_controller。
