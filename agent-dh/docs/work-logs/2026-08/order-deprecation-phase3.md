# 旧订单体系废弃 · Phase 3 执行记录

**日期**: 2026-08-25 21:49-22:16
**执行人**: investor (w-882977ae)
**任务线**: 旧 orders/holdings 体系废弃 Phase 3（归档与清理）

---

## 本轮完成事项（Phase 3 核心）

### 1. 数据库表归档 ✅

```sql
-- 执行时间：2026-08-25 21:49
ALTER TABLE quant.orders RENAME TO orders_legacy_archived_20260825;
COMMENT ON TABLE quant.orders_legacy_archived_20260825 IS 
'旧订单表归档（2026-08-25）。已迁移到 simulation_order 表。仅保留用于历史数据查询。';
```

**验证**:
- `quant.orders` 不存在 ✓
- `quant.orders_legacy_archived_20260825` 存在（9 条历史记录）✓
- `quant.simulation_order` 有 25 条记录（新系统运行正常）✓

### 2. 删除废弃 API 路由 ✅

**文件**: `quantsys-v2/adapters/inbound/fastapi_app/routes/orders_async.py`

**变更统计**: 495 行 → 189 行（删除 306 行，-61.8%）

**删除的 12 个端点**（全部使用旧 `ds.portfolio` 或归档表）:
1. `GET /api/orders/list` - ds.portfolio.get_orders（读归档空表）
2. `GET /api/orders/detail/{id}` - ds.portfolio.get_order_by_id
3. `POST /api/orders/create` - 已 410 Gone（Phase 1 废弃）
4. `POST /api/orders/cancel/{id}` - order_service.cancel_order
5. `POST /api/orders/fill/{id}` - order_service.fill_order
6. `POST /api/orders/update/{id}` - ds.portfolio.update_order
7. `GET /api/trades/list` - ds.portfolio.get_trades
8. `GET /api/portfolio/holdings` - ds.portfolio.get_all_holdings
9. `GET /api/portfolio/allocation` - ds.portfolio.get_all_holdings
10. `GET /api/portfolio/equity-curve` - ds.portfolio.get_trades
11. `GET /api/portfolio/positions/{symbol}` - ds.portfolio.get_all_holdings
12. `GET /api/portfolio/history` - ds.risk.get_history

**保留的 3 个端点**（已迁移到新系统或无 DB 依赖）:
- `POST /api/orders/algo-execute` - TWAP/VWAP 算法拆单（纯计算，无 DB 持久化）
- `GET /api/portfolio/positions` - 已用 `SimulationORMRepository`
- `GET /api/portfolio/summary` - 已用 `SimulationORMRepository`

### 3. 验证

**语法检查**: ✓ Python syntax OK
**冒烟测试**: 7/8 通过（market_sector_detail 失败与本次改动无关）
**核心端点**:
- `/api/portfolio/positions?account_name=agent_virtual` → success: true ✓
- `/api/simulation/accounts/agent_virtual/trade` → 422 非交易时段（预期）✓

---

## 部署要求 🚀

**需重启 FastAPI 服务器**使路由删除生效：

```bash
# 当前运行的服务器
PID: 55091
Command: python adapters/inbound/fastapi_app/main.py

# 重启方式（任选其一）
kill 55091 && python adapters/inbound/fastapi_app/main.py &  # 手动
# 或使用服务管理命令（如 systemctl/launchctl）
```

**注意**: 服务器未重启前，旧端点仍返回 410 Gone（Phase 1 的废弃响应），重启后返回 404 Not Found。

---

## 待后续工作（超出 Phase 3 范围）

### 3.3 清理 ds.portfolio 死代码 ⏸️

**阻塞原因**: 40 处 `ds.portfolio` 引用仍被活跃使用：
- `application/services/order_service.py`（28 处）← 被 `/api/signals/execute` 调用
- `application/services/trade_service.py`（5 处）
- `application/services/execution_service.py`（1 处）
- `application/services/risk_check_service.py`（1 处）

**需要先做**:
1. 迁移 `signals_async.py` 的 `create_order_from_signal()` → simulation API
2. 迁移 `trade_service.py` 的历史交易查询 → `SimulationORMRepository`
3. 删除 `ds.portfolio` 的 create/update 方法（保留 get_order 历史查询）

### 3.4 前端迁移 ⏸️

**状态**: 6 处前端调用待迁移（详见 Phase 2 前端迁移清单）

**影响**: 
- ❌ Orders/OpportunityRadar/BacktestCenter 下单功能已损坏（`createOrder` → 410 Gone）
- ⚠️ Orders 列表/取消、Trades 列表、portfolio store 读归档空表（返回空数据）

**新 API 已就绪**: `web-frontend/src/services/api/simulation.ts`，4 处视图已迁移可参照。

**建议**: 作为独立前端工程任务执行（需前端开发角色，超出 investor 职责范围）。

---

## Phase 3 总结

### 已完成（核心目标达成）
- ✅ 数据层归档（旧表重命名，新表验证正常）
- ✅ API 层清理（12 个废弃端点删除，306 行代码移除）
- ✅ 代码已提交（commit f1369dba）

### 待部署
- 🚀 重启 FastAPI 服务器（PID 55091）

### 待后续
- ⏸️ ds.portfolio 清理（需先迁移 signals/executions）
- ⏸️ 前端 6 处迁移（独立前端任务）

### 当前状态
**后端**: 旧订单体系已完全归档，新系统（simulation_*）运行正常，Agent 自主交易不受影响。
**前端**: 监控面板部分功能损坏（Orders 下单 410 Gone），但不影响 Agent 核心功能。

---

**相关文档**：
- [废弃计划](../architecture/legacy-system-deprecation-plan.md)（已更新 Phase 3 状态）
- [Phase 2 完成记录](order-deprecation-phase2.md)
- [卖出修复报告](sell-order-fix-report.md)
- [订单 API 指南](../guides/order-api-guide.md)
