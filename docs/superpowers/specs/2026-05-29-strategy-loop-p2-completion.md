# P2 策略循环闭合 — 知识积累 + 实盘跟踪

**完成时间**: 2026-05-29  
**状态**: ✅ 已完成  
**相关计划**: [strategy-loop-closure-plan.md](../../plans/strategy-loop-closure-plan.md)

---

## 📋 完成概述

P2 实现了"信号 → 执行 → 盈亏 → 统计 → 经验"的完整闭环，解决了以下问题：

| 问题 | 解决方案 | 状态 |
|------|---------|------|
| 信号发了就忘 | 订单关联 signal_id，全程追踪 | ✅ |
| 盈亏无法统计 | 成交时自动计算并写入 strategy_performance | ✅ |
| 纸面和实盘分离 | 统一统计 API，加权合并两者数据 | ✅ |
| 经验无法积累 | 自动从统计生成经验条目 | ✅ |

---

## 🏗️ 架构设计

### 数据流向

```
策略信号
    ↓
┌─────────────────────────────────────────────────┐
│ 1. signal_test_log 记录                         │
│    - 信号元数据（策略、标的、价格、置信度）       │
│    - status: pending                            │
└────────────────┬────────────────────────────────┘
                 ↓
┌─────────────────────────────────────────────────┐
│ 2. 创建订单（带 signal_id）                      │
│    - trade_manage_orders.place()                │
│    - order.signal_id = signal_log.id            │
└────────────────┬────────────────────────────────┘
                 ↓
┌─────────────────────────────────────────────────┐
│ 3. 订单成交（买入）                              │
│    - fill_order() 调用 _update_signal_tracking() │
│    - 更新 signal_test_log.entry_price           │
└────────────────┬────────────────────────────────┘
                 ↓
┌─────────────────────────────────────────────────┐
│ 4. 订单成交（卖出）                              │
│    - 计算盈亏: (exit - entry) / entry * 100     │
│    - 更新 signal_test_log: pnl_pct, status      │
│    - 写入 strategy_performance (source='live')  │
└────────────────┬────────────────────────────────┘
                 ↓
┌─────────────────────────────────────────────────┐
│ 5. 统一统计 API                                  │
│    - GET /api/signal-test/performance           │
│    - 返回: paper + live + combined              │
└────────────────┬────────────────────────────────┘
                 ↓
┌─────────────────────────────────────────────────┐
│ 6. 经验自动积累                                  │
│    - ExperienceAccumulator.accumulate_all()     │
│    - 生成经验条目（样本 ≥ 10）                   │
│    - 推荐等级: aggressive/moderate/cautious/avoid│
└─────────────────────────────────────────────────┘
```

---

## 📦 新增组件

### 1. strategy_performance 表

**位置**: `quantsys-v2/migrations/add_strategy_performance_table.sql`

**字段**:
```sql
CREATE TABLE quant.strategy_performance (
    id SERIAL PRIMARY KEY,
    strategy_name VARCHAR(100) NOT NULL,
    symbol VARCHAR(20) NOT NULL,
    signal_date DATE NOT NULL,
    entry_price DECIMAL(10, 2) NOT NULL,
    exit_price DECIMAL(10, 2),
    pnl_pct DECIMAL(10, 2),
    holding_days INTEGER,
    scenario_tags JSONB DEFAULT '[]',
    params_snapshot JSONB DEFAULT '{}',
    source VARCHAR(20) DEFAULT 'paper',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

**索引**:
- `idx_strategy_performance_strategy` (strategy_name)
- `idx_strategy_performance_symbol` (symbol)
- `idx_strategy_performance_signal_date` (signal_date)
- `idx_strategy_performance_source` (source)
- `idx_strategy_performance_scenario_tags` (scenario_tags) — GIN 索引

### 2. StrategyPerformanceRepository

**位置**: `quantsys-v2/repositories/strategy_performance_repository.py`

**方法**:
- `create()` — 创建实盘记录
- `update_exit()` — 更新出场价和盈亏
- `get_by_strategy_and_symbol()` — 查询策略-标的组合的历史记录
- `get_statistics()` — 获取统计数据（总交易数、胜率、平均盈亏等）

**关键实现**:
```python
def get_statistics(self, strategy_name: str, symbol: Optional[str] = None, source: Optional[str] = None):
    # 查询聚合统计
    query = """
        SELECT
            COUNT(*) as total_trades,
            SUM(CASE WHEN pnl_pct > 0 THEN 1 ELSE 0 END) as win_trades,
            SUM(CASE WHEN pnl_pct <= 0 THEN 1 ELSE 0 END) as loss_trades,
            AVG(pnl_pct) as avg_pnl_pct,
            AVG(holding_days) as avg_holding_days,
            MAX(pnl_pct) as max_pnl_pct,
            MIN(pnl_pct) as min_pnl_pct
        FROM quant.strategy_performance
        WHERE strategy_name = %s
    """
    # 处理 Decimal → float 转换
    # 计算胜率
    return stats
```

### 3. 订单盈亏追踪

**位置**: `quantsys-v2/services/order_service.py`

**函数**: `_update_signal_tracking(signal_id, action, fill_price, symbol)`

**逻辑**:
```python
if action == 'buy':
    # 只在第一次成交时更新 entry_price
    if signal['entry_price'] is None:
        UPDATE signal_test_log SET entry_price = fill_price

elif action == 'sell':
    # 计算盈亏
    pnl_pct = (fill_price - entry_price) / entry_price * 100
    
    # 更新 signal_test_log
    UPDATE signal_test_log SET 
        current_price = fill_price,
        pnl_pct = pnl_pct,
        status = 'verified'
    
    # 写入 strategy_performance
    perf_repo.create(
        strategy_name=...,
        entry_price=entry_price,
        exit_price=fill_price,
        pnl_pct=pnl_pct,
        source='live'
    )
```

### 4. 统一统计 API

**位置**: `quantsys-v2/api/routes/signal_test.py`

**端点**: `GET /api/signal-test/performance`

**参数**:
- `strategy` (必需) — 策略名称
- `symbol` (可选) — 股票代码
- `start_date` (可选) — 开始日期
- `end_date` (可选) — 结束日期

**返回**:
```json
{
  "success": true,
  "data": {
    "strategy_name": "ma_cross",
    "symbol": "600519.SH",
    "paper": {
      "total_trades": 10,
      "verified_trades": 8,
      "pending_trades": 2,
      "avg_pnl_pct": 3.5,
      "win_rate": 62.5,
      "max_pnl_pct": 15.2,
      "min_pnl_pct": -5.3
    },
    "live": {
      "total_trades": 5,
      "win_trades": 3,
      "loss_trades": 2,
      "avg_pnl_pct": 4.2,
      "win_rate": 60.0,
      "avg_holding_days": 5.2
    },
    "combined": {
      "total_trades": 13,
      "avg_pnl_pct": 3.8,
      "win_rate": 61.5
    }
  }
}
```

**综合统计算法**:
```python
# 加权平均盈亏
avg_pnl_pct = (
    paper_stats['avg_pnl_pct'] * paper_stats['verified_trades'] +
    live_stats['avg_pnl_pct'] * live_stats['total_trades']
) / (paper_stats['verified_trades'] + live_stats['total_trades'])

# 综合胜率
paper_win_trades = paper_stats['verified_trades'] * paper_stats['win_rate'] / 100
live_win_trades = live_stats['win_trades']
win_rate = (paper_win_trades + live_win_trades) / total_trades * 100
```

### 5. ExperienceAccumulator

**位置**: `quantsys-v2/services/experience_accumulator.py`

**方法**:
- `accumulate_from_performance()` — 单个策略-标的组合
- `accumulate_all()` — 批量处理所有策略

**经验条目格式**:
```json
{
  "id": "uuid",
  "scenario": "使用 ma_cross 策略交易 600519.SH",
  "pattern": {
    "conditions": ["策略: ma_cross", "标的: 600519.SH"],
    "action": "buy"
  },
  "outcomes": {
    "total_cases": 15,
    "win_rate": 61.5,
    "avg_return": 3.8,
    "max_gain": 15.2,
    "max_loss": -5.3
  },
  "recommendation": "moderate",
  "reason": "基于 15 个历史案例，胜率 61.5%，平均收益 3.80%",
  "examples": []
}
```

**推荐等级规则**:
```python
def _generate_recommendation(win_rate, avg_return):
    if win_rate >= 70 and avg_return >= 3:
        return 'aggressive'
    elif win_rate >= 60 and avg_return >= 2:
        return 'moderate'
    elif win_rate >= 50 and avg_return >= 1:
        return 'cautious'
    else:
        return 'avoid'
```

---

## 🧪 测试覆盖

### 单元测试

| 测试文件 | 测试数量 | 状态 |
|---------|---------|------|
| `test_strategy_performance_repository.py` | 4 | ✅ |
| `test_signal_tracking.py` | 4 | ✅ |
| `test_performance_api.py` | 8 | ✅ |
| `test_experience_accumulator.py` | 6 | ✅ |
| **合计** | **22** | **✅** |

### 端到端测试

见 `docs/testing/strategy-loop-p2-e2e-test.md`

---

## 📊 使用示例

### 1. 查询策略表现

```bash
# 查询单个策略的综合表现
curl "http://127.0.0.1:5001/api/signal-test/performance?strategy=ma_cross"

# 查询策略在特定标的上的表现
curl "http://127.0.0.1:5001/api/signal-test/performance?strategy=ma_cross&symbol=600519.SH"

# 查询特定时间范围
curl "http://127.0.0.1:5001/api/signal-test/performance?strategy=ma_cross&start_date=2026-01-01&end_date=2026-05-29"
```

### 2. 积累经验

```python
from services.experience_accumulator import ExperienceAccumulator

accumulator = ExperienceAccumulator()

# 单个策略-标的组合
result = accumulator.accumulate_from_performance(
    strategy_name='ma_cross',
    symbol='600519.SH',
    min_samples=10,
    output_file='experiences.json'
)

# 批量处理所有策略
result = accumulator.accumulate_all(
    min_samples=10,
    output_file='all_experiences.json'
)
```

### 3. Agent 工具集成

Agent 的 `query_experience` 工具现在可以查询到真实的策略表现数据：

```typescript
// Agent 查询经验
query_experience({
  query: "ma_cross 策略在贵州茅台上的表现如何？"
})

// 返回
{
  "experiences": [
    {
      "scenario": "使用 ma_cross 策略交易 600519.SH",
      "recommendation": "moderate",
      "reason": "基于 15 个历史案例，胜率 61.5%，平均收益 3.80%"
    }
  ]
}
```

---

## 🔄 完整闭环验证

### 闭环流程

```
1. 策略生成信号
   ↓
2. signal_test_log 记录 (status=pending)
   ↓
3. 创建订单 (signal_id=xxx)
   ↓
4. 订单成交（买入）→ entry_price 更新
   ↓
5. 订单成交（卖出）→ pnl_pct 计算 → strategy_performance 写入
   ↓
6. 统计 API 查询 → 返回纸面+实盘综合数据
   ↓
7. 经验积累 → 生成经验条目
   ↓
8. Agent 查询经验 → 决策时参考历史表现
```

### 验证标准

- [x] 信号可追踪：每笔订单都能关联到原始信号
- [x] 盈亏可计算：卖出时自动计算并记录盈亏
- [x] 统计可查询：API 返回纸面+实盘综合统计
- [x] 经验可积累：样本 ≥ 10 时自动生成经验条目
- [x] 决策可反馈：Agent 查询经验时返回真实历史数据

---

## 🎯 下一步

P2 完成后，可以继续：

- **P3**: 策略运维（熔断、风格检测、版本管理）
- **P4**: 能力升级（回测质量、组合管理、自主研发、实盘监控）

或者先完成 **P0-1**（参数搜索引擎），让优化器使用真实回测打分。

---

## 📝 相关文件

### 数据库
- `quantsys-v2/migrations/add_strategy_performance_table.sql`

### 服务层
- `quantsys-v2/repositories/strategy_performance_repository.py`
- `quantsys-v2/services/order_service.py` (_update_signal_tracking)
- `quantsys-v2/services/experience_accumulator.py`

### API 层
- `quantsys-v2/api/routes/signal_test.py` (GET /api/signal-test/performance)

### 测试
- `quantsys-v2/tests/test_strategy_performance_repository.py`
- `quantsys-v2/tests/test_signal_tracking.py`
- `quantsys-v2/tests/test_performance_api.py`
- `quantsys-v2/tests/test_experience_accumulator.py`

### 文档
- `docs/plans/strategy-loop-closure-plan.md`
- `docs/testing/strategy-loop-p2-e2e-test.md`
