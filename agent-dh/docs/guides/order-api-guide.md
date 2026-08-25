# 订单 API 使用指南

**更新日期**: 2026-08-25  
**作者**: investor (w-882977ae)

---

## 📋 重要说明

系统中存在**两套订单 API**，修复后应该使用**新 API**：

| API | 路径 | 订单表 | account_name | 状态 |
|-----|------|--------|--------------|------|
| **旧 API** | `/api/orders/create` | `quant.orders` | ❌ 不支持（account_id 为空）| ⚠️ 已废弃 |
| **新 API** | `/api/simulation/accounts/{account_name}/trade` | `quant.simulation_order` | ✅ 支持 | ✅ 推荐使用 |

---

## ✅ 推荐使用：新 API

### 端点

```
POST /api/simulation/accounts/{account_name}/trade
```

### 特点

1. ✅ **正确保存 account_name**：订单记录包含账户名称
2. ✅ **使用新表**：写入 `quant.simulation_order`
3. ✅ **支持 T+1**：持仓更新正确使用 `SimulationORMRepository`
4. ✅ **交易时段检查**：自动拒绝非交易时段的订单
5. ✅ **完整集成**：与 `simulation_positions` 表完美配合

### 请求示例

#### 买入

```bash
curl -X POST 'http://127.0.0.1:5001/api/simulation/accounts/agent_virtual/trade' \
  -H 'Content-Type: application/json' \
  -d '{
    "action": "buy",
    "symbol": "000001",
    "shares": 200,
    "price_limit": 12.50,
    "reason": "买入平安银行"
  }'
```

#### 卖出

```bash
curl -X POST 'http://127.0.0.1:5001/api/simulation/accounts/agent_virtual/trade' \
  -H 'Content-Type: application/json' \
  -d '{
    "action": "sell",
    "symbol": "002241",
    "shares": 100,
    "price_limit": 23.00,
    "reason": "止盈"
  }'
```

### 参数说明

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `action` | string | ✅ | `buy` 或 `sell` |
| `symbol` | string | ✅ | 股票代码（6位数字） |
| `shares` | integer | ✅ | 数量（必须是 100 的整数倍） |
| `price_limit` | float | ❌ | 限价（不传则市价） |
| `reason` | string | ❌ | 交易理由 |
| `price` | float | ❌ | 当前价格（用于验证） |
| `execute_at` | string | ❌ | 执行时机（如 `market_open` 盘前挂单） |
| `max_positions` | integer | ❌ | 最大持仓数（默认 10） |

### 响应示例

#### 成功

```json
{
  "success": true,
  "data": {
    "order_id": 14,
    "trade_id": 123,
    "action": "buy",
    "symbol": "000001",
    "shares": 200,
    "filled_price": 12.50,
    "status": "filled"
  }
}
```

#### 失败（非交易时段）

```json
{
  "success": false,
  "error": "非交易时段（21:15），A股交易时段为 9:30-11:30 / 13:00-15:00，委托拒绝"
}
```

#### 失败（持仓不足）

```json
{
  "success": false,
  "error": "持仓数量不足: 002241 可用 600 股，委托卖出 1000 股，缺口 400 股 （数据源: simulation，T+1限制：当日买入次日可卖）"
}
```

---

## ⚠️ 已废弃：旧 API

### 端点

```
POST /api/orders/create
```

### 问题

1. ❌ **account_name 丢失**：订单的 `account_id` 字段为 null
2. ❌ **使用旧表**：写入 `quant.orders`（与新系统不一致）
3. ❌ **持仓更新回退**：由于没有 `account_name`，持仓更新会回退到旧 `holdings` 表
4. ❌ **T+1 不生效**：回退到旧系统后，T+1 规则失效

### 迁移建议

**所有使用旧 API 的地方应该迁移到新 API**：

| 调用方 | 旧调用 | 新调用 |
|--------|--------|--------|
| **Agent 工具** | `portfolio_trade` | 需要更新为调用新 API |
| **测试脚本** | `/api/orders/create` | `/api/simulation/accounts/{account_name}/trade` |
| **前端** | `/api/orders/create` | `/api/simulation/accounts/{account_name}/trade` |

---

## 🔧 持仓更新修复说明

修复（808a2f62 + e7641fec）已经让持仓更新逻辑统一使用 `SimulationORMRepository`：

### 工作原理

1. **卖出校验**（`create_order`）：
   ```python
   # 优先使用 SimulationORMRepository
   if account_name:
       position = sim_repo.get_position(account_name, symbol)
       available_quantity = position.shares_available  # T+1 可卖数量
   ```

2. **买入持仓更新**（`_update_position_on_buy`）：
   ```python
   # 优先使用 SimulationORMRepository
   if account_name:
       # 新买入 shares_available=0（T+1 当日不可卖）
       sim_repo.upsert_position(
           account_name=account_name,
           symbol=symbol,
           shares_total=total_qty,
           shares_available=0,  # T+1
           ...
       )
   ```

3. **卖出持仓更新**（`_update_position_on_sell`）：
   ```python
   # 优先使用 SimulationORMRepository
   if account_name:
       # 同时减少 shares_total 和 shares_available
       new_available = max(0, old_available - fill_quantity)
       sim_repo.upsert_position(
           account_name=account_name,
           symbol=symbol,
           shares_total=new_qty,
           shares_available=new_available,  # T+1
           ...
       )
   ```

### 关键依赖

**持仓更新能否使用新系统，取决于订单是否有 `account_name`**：

| 订单来源 | account_name | 持仓更新路径 | T+1 支持 |
|----------|--------------|--------------|----------|
| 新 API | ✅ 有 | SimulationORMRepository | ✅ 正确 |
| 旧 API | ❌ 无（null） | 回退到旧 holdings 表 | ❌ 失效 |

---

## 📊 数据表对比

### 订单表

| 字段 | `quant.orders` (旧) | `quant.simulation_order` (新) |
|------|---------------------|-------------------------------|
| 账户字段 | `account_id` (可为空) | `account_name` (NOT NULL) ✅ |
| 操作字段 | `action` (小写) | `action` (大写契约 BUY/SELL) ✅ |
| 数量字段 | `quantity` | `shares` |
| 成交数量 | `filled_quantity` | `filled_shares` |
| 状态 | pending/filled/cancelled | submitted/filled/cancelled ✅ |

### 持仓表

| 字段 | `quant.holdings` (旧) | `quant.simulation_positions` (新) |
|------|-----------------------|-----------------------------------|
| 账户字段 | ❌ 无 | `account_name` ✅ |
| 总持仓 | `quantity` | `shares_total` ✅ |
| T+1 可卖 | ❌ 不支持 | `shares_available` ✅ |
| 成本 | `avg_cost` | `avg_cost` + `cost` ✅ |
| 市值 | ❌ 需计算 | `market_value` ✅ |
| 盈亏 | ❌ 需计算 | `profit_total` + `profit_total_rate` ✅ |

---

## ✅ 最佳实践

### 1. 使用新 API

**所有新代码都应该使用新 API**：
```python
# ❌ 错误
response = requests.post(
    'http://127.0.0.1:5001/api/orders/create',
    json={'symbol': '000001', 'action': 'buy', 'quantity': 200}
)

# ✅ 正确
response = requests.post(
    'http://127.0.0.1:5001/api/simulation/accounts/agent_virtual/trade',
    json={'symbol': '000001', 'action': 'buy', 'shares': 200}
)
```

### 2. 查询持仓

```python
# ✅ 使用新 API
response = requests.get(
    'http://127.0.0.1:5001/api/portfolio/positions?account_name=agent_virtual'
)
# 返回: shares_total, sharesAvailable (T+1 可卖数量)
```

### 3. 卖出前检查

```python
# 获取持仓
position = get_position('agent_virtual', '002241')

# 检查 T+1 可卖数量
if position['sharesAvailable'] >= sell_quantity:
    # ✅ 可以卖出
    trade('agent_virtual', 'sell', '002241', sell_quantity)
else:
    # ❌ 可卖数量不足（可能当日刚买入）
    print(f"T+1 限制：可卖 {position['sharesAvailable']} 股，尝试卖 {sell_quantity} 股")
```

---

## 🔄 迁移计划

### Phase 1: API 层迁移（推荐）

1. ✅ **新 API 已可用**：`/api/simulation/accounts/{account_name}/trade`
2. **迁移调用方**：
   - Agent 工具（`portfolio_trade`）
   - 测试脚本
   - 前端页面

### Phase 2: 废弃旧 API

1. 标记旧 API 为 deprecated
2. 添加警告日志
3. 设置下线时间

### Phase 3: 数据迁移

1. 迁移旧 `orders` 表到 `simulation_order`
2. 迁移旧 `holdings` 表到 `simulation_positions`
3. 归档旧表

---

## 📝 相关 Commits

- `808a2f62` - 卖出校验修复（使用 SimulationORMRepository）
- `e7641fec` - 持仓更新统一（支持 T+1）
- 本文档 - 订单 API 使用指南

---

**更新时间**: 2026-08-25 21:20  
**作者**: investor (w-882977ae)
