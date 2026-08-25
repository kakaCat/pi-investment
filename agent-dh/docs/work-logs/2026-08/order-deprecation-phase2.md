# 旧订单体系废弃 · Phase 2 完成记录

**日期**: 2026-08-25
**执行人**: investor (w-882977ae)
**任务线**: 卖出"无持仓记录"修复 + 旧 orders/holdings 体系废弃

---

## 本轮完成事项（Phase 2 收尾）

### 1. 测试脚本切新 API

| 文件 | 变更 |
|------|------|
| `quantsys-v2/tests/test_api_smoke.py` | `test_order_create_sell_validation` → `test_simulation_trade_sell_validation`，端点 `/api/orders/create` → `/api/simulation/accounts/agent_virtual/trade`，字段 `quantity` → `shares`，显式传 `price` 绕过实时行情依赖 |
| `quantsys-v2/tests/migration/test_orders_parity.py` | 标记 DEPRECATED（原 Flask↔FastAPI 比对已无意义）；移除 2 个 `/api/orders/create` 测试（已 410 Gone）；保留只读端点 `<500` 守卫，Phase 3 随路由一并删除 |

**验证**：冒烟测试 8/8 通过（含新 sell 校验路径，非交易时段返回 422 业务错误而非 500）。

### 2. 前端旧 API 使用检查（发现真实影响）

`web-frontend/src/services/api/trading.ts` 仍引用旧端点，其中 `/api/orders/create` 已 410 Gone（**下单功能已失效**）：

- ❌ **已损坏**（createOrder → 410 Gone）：
  - `Orders/index.vue:437`
  - `OpportunityRadar/index.vue:783`
  - `BacktestCenter/index.vue:1349`
- ⚠️ **读归档空表**（返回空数据）：
  - `Orders/index.vue` getOrders/cancelOrder → `/api/orders/list` `/api/orders/cancel`
  - `Trades/index.vue:282` getTrades → `/api/trades/list`
  - `stores/portfolio.ts` + Dashboard → `/api/portfolio/holdings` `/api/portfolio/allocation` `/api/portfolio/equity-curve`

**新 API 已就绪**：`web-frontend/src/services/api/simulation.ts`（`trade`/`getTrades`/`getAccount`/`getPerformance`），已迁移 4 处（Portfolio / SimulationTrading / Dashboard / AccountSwitcher）。

**结论**：前端迁移是独立工作项，剩余 6 处调用方需切 `simulationApi` 并适配 `TradeItem`/`PositionItem` 数据类型。已列入 `legacy-system-deprecation-plan.md` 的"前端迁移清单"。

### 3. Agent 工具确认

- `portfolio_trade` / `executeAccountTrade` 已走新 API `/api/simulation/accounts/{name}/trade` ✅
- `algo_execute`（`trade_algo_execute`）走 `/api/orders/algo-execute` —— 该端点**未废弃**（纯计算 TWAP/VWAP 拆单，无 DB 持久化），无需迁移 ✅

---

## 数据源统一状态回顾

| 环节 | 状态 |
|------|------|
| 卖出校验（`shares_available`） | ✅ `SimulationORMRepository.get_position()`（808a2f62） |
| 买入持仓更新（T+1 正确） | ✅ 统一数据源（e7641fec） |
| 卖出持仓更新（total+available 同减） | ✅ 统一数据源（e7641fec） |
| `/api/orders/create` | ✅ 410 Gone（ef4b2c69） |
| 测试脚本 | ✅ 本轮切新 API |
| 前端 | ~ 4/10 已迁移，剩余列入清单 |

---

## 后续（Phase 3，2026-09-25）

- 重命名 `quant.orders` → `orders_legacy_archived_20260825`
- 删除旧 `/api/orders/*` 路由 + `ds.portfolio` 死代码（55 处引用）
- 完成前端 6 处旧调用方迁移
- 删除 `test_orders_parity.py`

---

**相关文档**：
- [废弃计划](../architecture/legacy-system-deprecation-plan.md)
- [订单 API 指南](../guides/order-api-guide.md)
- [卖出修复报告](sell-order-fix-report.md)
