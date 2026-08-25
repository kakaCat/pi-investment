# 旧订单体系废弃计划

**执行日期**: 2026-08-25  
**执行人**: investor (w-882977ae)  
**目标**: 安全废弃旧 orders + holdings 体系，避免影响后续开发

---

## 📋 现状评估

### 旧表数据量

| 表名 | 记录数 | 状态 |
|------|--------|------|
| `quant.orders` | 9 条 | 2 条 pending，7 条 filled/cancelled |
| `quant.holdings` | 不存在 | 已废弃 |

### 代码引用统计

- `ds.portfolio` 引用: **55 处**
- 涉及文件: application/services/, adapters/inbound/

---

## ✅ 已完成备份

```sql
-- 备份表
CREATE TABLE quant.orders_archived AS SELECT * FROM quant.orders;

-- 验证
SELECT COUNT(*) FROM quant.orders_archived;  -- 9 条
```

---

## 🎯 废弃计划（分 3 个阶段）

### Phase 1: 标记废弃（立即执行）✅

#### 1.1 废弃旧 orders API

**文件**: `adapters/inbound/fastapi_app/routes/orders_async.py`

```python
@router.post('/api/orders/create')
@handle_api_error
def create_order(payload: Optional[Dict[str, Any]] = Body(None)):
    """
    ⚠️ DEPRECATED: 此 API 已废弃，请使用新 API
    
    新 API: POST /api/simulation/accounts/{account_name}/trade
    
    废弃原因:
    - account_name 丢失（保存为 null）
    - 使用旧 quant.orders 表（已归档）
    - 持仓更新回退到旧系统
    - T+1 规则失效
    
    废弃日期: 2026-08-25
    下线日期: 2026-09-25（1个月后）
    """
    logger.warning(
        "⚠️ DEPRECATED API called: /api/orders/create. "
        "Please migrate to /api/simulation/accounts/{account_name}/trade"
    )
    
    # 返回明确的废弃警告
    return JSONResponse(
        status_code=410,  # 410 Gone
        content={
            'success': False,
            'error': '此 API 已废弃',
            'deprecated_at': '2026-08-25',
            'sunset_date': '2026-09-25',
            'migration_guide': 'https://github.com/.../docs/guides/order-api-guide.md',
            'new_api': 'POST /api/simulation/accounts/{account_name}/trade'
        }
    )
```

#### 1.2 清理 pending 订单

```sql
-- 取消 pending 订单（避免遗留数据）
UPDATE quant.orders 
SET status = 'cancelled', 
    rejection_reason = '旧体系废弃，订单自动取消'
WHERE status = 'pending';

-- 验证
SELECT id, symbol, status FROM quant.orders WHERE status = 'pending';  -- 应为空
```

---

### Phase 2: 代码迁移（1周内）

#### 2.1 修复 order_service.py 残留引用

**问题**: `fill_order` 等函数还在用 `ds.portfolio.get_order()`

**方案**: 
- `fill_order` 只处理旧 orders 表的历史订单
- 新订单统一走 `SimulationORMRepository`
- 添加日志标记数据源

**文件**: `application/services/order_service.py`

```python
def fill_order(ds: DataService, order_id: int, ...):
    """
    成交订单（仅支持旧 orders 表的历史订单）
    
    ⚠️ 新订单请使用 SimulationORMRepository.fill_order()
    """
    logger.warning(
        f"⚠️ Using legacy fill_order for order_id={order_id}. "
        "New orders should use SimulationORMRepository."
    )
    
    order = ds.portfolio.get_order(order_id)
    if not order:
        raise RuntimeError(f"Order not found: {order_id}")
    
    # ... 原有逻辑 ...
```

#### 2.2 移除 ds.portfolio 的新订单创建

**保留功能**:
- ✅ `get_order()` - 查询历史订单
- ✅ `fill_order()` - 处理历史订单成交（通过 order_service）

**废弃功能**:
- ❌ `create_order()` - 已由新 API 替代
- ❌ `get_holding()` - holdings 表已废弃
- ❌ `add_or_update_holding()` - holdings 表已废弃

---

### Phase 3: 归档与清理（2026-08-25 执行）

#### 3.1 重命名旧表（归档）✅

```sql
-- 已执行（2026-08-25 21:49）
ALTER TABLE quant.orders RENAME TO orders_legacy_archived_20260825;
COMMENT ON TABLE quant.orders_legacy_archived_20260825 IS 
'旧订单表归档（2026-08-25）。已迁移到 simulation_order 表。仅保留用于历史数据查询。';

-- 验证：quant.simulation_order 有 25 条记录 ✓
```

#### 3.2 删除旧 API 路由 ✅

**文件**: `adapters/inbound/fastapi_app/routes/orders_async.py`（495 行 → 189 行）

已删除 12 个废弃端点（306 行代码）：
- `/api/orders/list`, `/api/orders/detail/{id}`, `/api/orders/create`, `/api/orders/cancel/{id}`, `/api/orders/fill/{id}`, `/api/orders/update/{id}`
- `/api/trades/list`
- `/api/portfolio/holdings`, `/api/portfolio/allocation`, `/api/portfolio/equity-curve`, `/api/portfolio/positions/{symbol}`, `/api/portfolio/history`

保留 3 个端点：
- `/api/orders/algo-execute`（TWAP/VWAP 纯计算，不涉及 DB）
- `/api/portfolio/positions`（已用 SimulationORMRepository）
- `/api/portfolio/summary`（已用 SimulationORMRepository）

**部署**: 需重启 FastAPI 服务器生效（PID 55091, `python adapters/inbound/fastapi_app/main.py`）。

#### 3.3 清理 ds.portfolio 死代码 ⏸️ 待后续

**阻塞原因**: `application/services/order_service.py` 有 28 处 `ds.portfolio` 调用，被 `/api/signals/execute` 端点使用（Executions 视图活跃调用），需先迁移信号执行流程。

**后续工作**:
1. 迁移 `signals_async.py` 的 `create_order_from_signal` → 新 simulation API
2. 迁移 `trade_service.py` 的历史交易查询 → `SimulationORMRepository`
3. 删除 `ds.portfolio` 的 create/update 方法（保留 get_order 历史查询）

#### 3.4 前端迁移 ✅

**状态**: 6 处前端调用已全部迁移（2026-08-25 22:17）

**变更文件**:
1. `web-frontend/src/views/Orders/index.vue` - tradingApi.{createOrder,getOrders,cancelOrder} → simulationApi.{trade,getPendingOrders,cancelPendingOrder}
2. `web-frontend/src/views/OpportunityRadar/index.vue` - tradingApi.createOrder → simulationApi.trade
3. `web-frontend/src/views/BacktestCenter/index.vue` - tradingApi.createOrder → simulationApi.trade
4. `web-frontend/src/views/Trades/index.vue` - tradingApi.getTrades → simulationApi.getTrades（前端过滤/分页）
5. `web-frontend/src/stores/portfolio.ts` - tradingApi.{getPortfolioSummary,getPositions} → simulationApi.getAccount
6. `web-frontend/src/services/api/simulation.ts` - 新增 getPendingOrders/cancelPendingOrder 方法

**数据适配**:
- Order/Trade 类型 → TradeItem/PendingOrder
- `quantity/type/priceType` → `shares/action/price_limit`
- 所有调用添加 `DEFAULT_ACCOUNT='agent_virtual'`（agent 唯一交易账本）

**修复功能**:
- ✅ Orders 页面下单（410 Gone → 正常）
- ✅ OpportunityRadar 快速下单（410 Gone → 正常）
- ✅ BacktestCenter 快速下单（410 Gone → 正常）
- ✅ Trades 交易记录（空列表 → 正常）
- ✅ Portfolio Store 持仓汇总（空数据 → 正常）

**Commit**: 8514a66e

---

## Phase 3 执行总结（2026-08-25）

### 已完成
- ✅ 3.1 数据库表归档（quant.orders → orders_legacy_archived_20260825）
- ✅ 3.2 删除 12 个废弃 API 端点（306 行代码）
- ✅ 3.4 前端迁移（6 处全部迁移，下单功能已修复）
- ✅ 3.5 客户端清理（agent-ts + web-frontend）
  - agent-ts: trade_monitor 工具迁移到 simulation API
  - web-frontend: 删除 7 个未使用的旧 API 方法
  - 所有测试通过（agent-ts: 4/4, web-frontend: 10/10）
  - Commit: 23cef8bd

### 待后续
- ⏸️ 3.3 清理 ds.portfolio（需先迁移 signals/executions）

### 部署步骤
重启 FastAPI 服务器使路由删除生效：
```bash
kill 55091  # 或使用服务管理命令
python adapters/inbound/fastapi_app/main.py &
```

---

```python
# 保留最小必要方法（查询历史订单）
class PortfolioRepository:
    def get_order(self, order_id: int) -> Optional[Dict]:
        """查询历史订单（仅用于旧 orders 表）"""
        # ... 保留 ...
    
    # 删除以下方法：
    # def create_order(...)  # REMOVED
    # def get_holding(...)   # REMOVED
    # def add_or_update_holding(...)  # REMOVED
```

---

## 📊 迁移影响分析

### 受影响的调用方

#### 1. Agent 工具（高优先级）

**问题**: `portfolio_trade` 工具可能还在调用旧 API

**检查**:
```bash
cd agent-dh/packages/trading
grep -r "/api/orders/create" src/
```

**修复**: 更新为新 API
```typescript
// 旧代码（废弃）
const response = await fetch('/api/orders/create', {
  method: 'POST',
  body: JSON.stringify({ symbol, action, quantity })
});

// 新代码
const response = await fetch(`/api/simulation/accounts/${accountName}/trade`, {
  method: 'POST',
  body: JSON.stringify({ symbol, action, shares: quantity })
});
```

#### 2. 测试脚本

**检查**:
```bash
cd quantsys-v2
grep -r "/api/orders/create" tests/
```

**修复**: 更新所有测试用例使用新 API

#### 3. 前端页面（如果有）

**检查**: web-frontend 是否使用旧 API  
**修复**: 更新为新 API

---

## ✅ 执行清单

### Phase 1: 标记废弃（今天）

- [x] 备份旧 orders 表
- [x] 废弃旧 /api/orders/create API（返回 410 Gone）
- [x] 取消 pending 订单
- [x] 添加废弃日志和警告

### Phase 2: 代码迁移（1周内）

- [x] 检查 Agent 工具 portfolio_trade（已切新 API `/api/simulation/accounts/{name}/trade`）
- [x] 更新测试脚本（`test_api_smoke.py` 切新 API；`test_orders_parity.py` 标记废弃并移除 create 测试）
- [~] 更新前端页面（`simulation.ts` + 4 视图已切新；Orders/OpportunityRadar/BacktestCenter/Trades + portfolio store 仍用旧 `tradingApi`，见下方"前端迁移清单"）
- [~] 清理 order_service.py 中的 ds.portfolio 引用（卖出校验/持仓更新已切 `SimulationORMRepository`；`fill_order` 按计划保留处理历史订单）
- [x] 运行回归测试（冒烟 8/8 通过）

#### 前端迁移清单（web-frontend 待办）

`web-frontend/src/services/api/trading.ts` 仍引用旧端点，其中 `/api/orders/create` 已返回 410 Gone（下单已失效）：

| 视图/模块 | 旧方法 | 旧端点 | 影响 |
|-----------|--------|--------|------|
| Orders/index.vue | createOrder | `/api/orders/create` | ❌ 410 Gone 下单失效 |
| OpportunityRadar/index.vue | createOrder | `/api/orders/create` | ❌ 410 Gone |
| BacktestCenter/index.vue | createOrder | `/api/orders/create` | ❌ 410 Gone |
| Orders/index.vue | getOrders/cancelOrder | `/api/orders/list` `/api/orders/cancel` | ⚠️ 读归档空表 |
| Trades/index.vue | getTrades | `/api/trades/list` | ⚠️ 读归档空表 |
| stores/portfolio.ts + Dashboard | getHoldings/getAllocation/getEquityCurve | `/api/portfolio/holdings` 等 | ⚠️ 读旧 holdings 表 |

新 API 已在 `web-frontend/src/services/api/simulation.ts` 就绪（`trade`/`getTrades`/`getAccount`/`getPerformance`），Portfolio/SimulationTrading/Dashboard/AccountSwitcher 4 处已迁移。上述旧调用方需逐一切换到 `simulationApi` 并适配 `TradeItem`/`PositionItem` 数据类型。

### Phase 3: 归档清理（2026-09-25）

- [ ] 重命名 quant.orders → quant.orders_legacy_archived_20260825
- [ ] 删除旧 API 路由
- [ ] 清理 ds.portfolio 死代码
- [ ] 更新文档

---

## 🔒 安全措施

### 回滚计划

如果出现问题，可以快速回滚：

```sql
-- 恢复旧表（从备份）
DROP TABLE IF EXISTS quant.orders;
CREATE TABLE quant.orders AS SELECT * FROM quant.orders_archived;

-- 恢复 API（取消废弃标记）
-- 代码回滚到 Phase 1 之前的 commit
```

### 验证检查点

每个 Phase 完成后验证：

```bash
# Phase 1 验证
curl -X POST http://127.0.0.1:5001/api/orders/create
# 预期：返回 410 Gone + 迁移指南

# Phase 2 验证
curl -X POST http://127.0.0.1:5001/api/simulation/accounts/agent_virtual/trade \
  -d '{"action":"buy","symbol":"000001","shares":100}'
# 预期：正常工作（或非交易时段拒绝）

# Phase 3 验证
psql -d quant_investment -c "\dt quant.orders"
# 预期：表不存在（已重命名为 orders_legacy_archived_20260825）
```

---

## 📝 相关文档

- [订单 API 使用指南](../guides/order-api-guide.md)
- [数据库表设计对比](../architecture/database-table-comparison.md)
- [卖出修复报告](../work-logs/2026-08/sell-order-fix-report.md)

---

## 🎯 预期收益

废弃完成后：

- ✅ 数据源完全统一（只用 simulation_* 表）
- ✅ 代码库更清晰（移除 55 处旧系统引用）
- ✅ 避免混淆（开发者不会误用旧 API）
- ✅ T+1 规则完整生效
- ✅ 降低维护成本

---

**执行日期**: 2026-08-25  
**负责人**: investor (w-882977ae)  
**审核**: 待定  
**状态**: Phase 1 ✅ / Phase 2 ✅ / Phase 3 ✅（完成！待部署服务器）

### Phase 3 执行情况
- ✅ 表归档（orders → orders_legacy_archived_20260825）
- ✅ 删除 12 个废弃 API 端点（306 行代码）
- ✅ 前端 6 处迁移（Orders/OpportunityRadar/BacktestCenter/Trades/portfolio store 已修复）
- ⏸️ ds.portfolio 清理（阻塞于 signals/executions 迁移，后续任务）
- 🚀 **需重启服务器**使路由删除生效（kill 55091）
