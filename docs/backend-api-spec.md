# 后端API技术规范文档

**项目**: pi-investment 量化交易系统  
**版本**: v2.0  
**日期**: 2026-05-22  
**目的**: 支持"领导监督Agent"的Web界面

---

## 📋 目录

1. [Agent操作日志模块](#agent操作日志模块)
2. [持仓管理模块](#持仓管理模块)
3. [订单管理模块](#订单管理模块)
4. [Agent决策与绩效模块](#agent决策与绩效模块)
5. [数据快照模块](#数据快照模块)
6. [审批流程模块](#审批流程模块)

---

## Agent操作日志模块

### 1.1 记录Agent操作

**命令**: `quant agent +log-action`

**参数**:
- `action_type` (required): 操作类型 - `scan` | `analyze` | `signal` | `trade` | `monitor`
- `symbol` (optional): 股票代码
- `details` (optional): 操作详情 (JSON字符串)
- `result` (optional): 操作结果 (JSON字符串)
- `metadata` (optional): 元数据 (JSON字符串)

**返回**:
```json
{
  "status": "success",
  "data": {
    "log_id": "log_20260522_104530_001",
    "timestamp": "2026-05-22 10:45:30",
    "action_type": "analyze",
    "symbol": "600519",
    "status": "success"
  }
}
```

**使用示例**:
```bash
quant agent +log-action \
  --action-type analyze \
  --symbol 600519 \
  --details '{"modules":["technical","fundamental"]}' \
  --result '{"score":80,"decision":"buy"}' \
  --json
```

---

### 1.2 查询Agent操作日志

**命令**: `quant agent +get-logs`

**参数**:
- `date` (optional): 日期过滤 `2026-05-22`
- `action-type` (optional): 操作类型过滤
- `symbol` (optional): 股票代码过滤
- `limit` (optional): 返回数量，默认50

**返回**:
```json
{
  "status": "success",
  "data": {
    "total": 156,
    "logs": [
      {
        "log_id": "log_20260522_104530_001",
        "timestamp": "2026-05-22 10:45:30",
        "action_type": "analyze",
        "symbol": "600519",
        "summary": "分析600519，生成买入信号",
        "status": "success"
      }
    ]
  }
}
```

---

### 1.3 获取单个操作详情

**命令**: `quant agent +get-log-detail`

**参数**:
- `log-id` (required): 日志ID

**返回**:
```json
{
  "status": "success",
  "data": {
    "log_id": "log_20260522_104530_001",
    "timestamp": "2026-05-22 10:45:30",
    "action_type": "analyze",
    "symbol": "600519",
    "details": {
      "modules_used": ["technical", "fundamental", "fund_flow"],
      "api_calls": [
        {"api": "calculate_technical_indicators", "duration_ms": 234},
        {"api": "get_financial_indicators", "duration_ms": 156}
      ]
    },
    "result": {
      "technical_score": 80,
      "fundamental_score": 70,
      "overall_score": 80,
      "decision": "buy",
      "confidence": 0.85,
      "buy_range": [1820, 1840],
      "stop_loss": 1750
    },
    "raw_data": {
      "technical": {},
      "fundamental": {},
      "fund_flow": {}
    }
  }
}
```

---

## 持仓管理模块

### 2.1 获取持仓列表

**命令**: `quant portfolio +get-positions`

**参数**:
- `account-id` (optional): 账户ID，默认 `default`

**返回**:
```json
{
  "status": "success",
  "data": {
    "account_id": "default",
    "total_value": 1250000,
    "cash": 250000,
    "positions": [
      {
        "symbol": "600519",
        "name": "贵州茅台",
        "shares": 100,
        "cost": 1600,
        "current_price": 1850,
        "market_value": 185000,
        "pnl": 25000,
        "pnl_pct": 15.6,
        "weight": 0.20,
        "stop_loss": 1750,
        "target_price": 1950,
        "entry_date": "2026-05-15",
        "entry_reason": "技术面超卖+基本面优质"
      }
    ],
    "summary": {
      "total_pnl": 125000,
      "total_pnl_pct": 12.5,
      "position_count": 8,
      "position_ratio": 0.80
    }
  }
}
```

---

### 2.2 更新持仓

**命令**: `quant portfolio +update-position`

**参数**:
- `symbol` (required): 股票代码
- `action` (required): 操作类型 - `buy` | `sell` | `adjust`
- `shares` (optional): 股数
- `price` (optional): 价格
- `stop-loss` (optional): 止损价
- `target-price` (optional): 目标价
- `reason` (optional): 原因
- `operated-by` (optional): 操作者，默认 `agent`

**返回**:
```json
{
  "status": "success",
  "data": {
    "action": "buy",
    "symbol": "600519",
    "shares": 100,
    "price": 1820,
    "new_position": {
      "symbol": "600519",
      "shares": 100,
      "cost": 1820,
      "market_value": 182000
    }
  }
}
```

---

### 2.3 获取持仓历史

**命令**: `quant portfolio +get-position-history`

**参数**:
- `symbol` (optional): 股票代码
- `start-date` (optional): 开始日期
- `end-date` (optional): 结束日期

**返回**:
```json
{
  "status": "success",
  "data": {
    "history": [
      {
        "date": "2026-05-22",
        "action": "buy",
        "symbol": "600519",
        "shares": 100,
        "price": 1820,
        "operated_by": "agent",
        "reason": "技术面超卖"
      }
    ]
  }
}
```

---

## 订单管理模块

### 3.1 创建订单

**命令**: `quant order +create`

**参数**:
- `symbol` (required): 股票代码
- `action` (required): 操作类型 - `buy` | `sell`
- `price` (required): 价格
- `shares` (required): 股数
- `order-type` (optional): 订单类型，默认 `limit`
- `submitted-by` (optional): 提交者，默认 `agent`
- `reason` (optional): 原因
- `analysis-log-id` (optional): 关联的分析日志ID

**返回**:
```json
{
  "status": "success",
  "data": {
    "order_id": "order_20260522_104530_001",
    "symbol": "600519",
    "action": "buy",
    "price": 1820,
    "shares": 100,
    "amount": 182000,
    "status": "pending",
    "submitted_by": "agent",
    "submitted_at": "2026-05-22 10:45:30",
    "reason": "技术面超卖+基本面优质"
  }
}
```

---

### 3.2 获取待审批订单

**命令**: `quant order +get-pending`

**参数**:
- `account-id` (optional): 账户ID

**返回**:
```json
{
  "status": "success",
  "data": {
    "pending_count": 3,
    "orders": [
      {
        "order_id": "order_20260522_104530_001",
        "symbol": "600519",
        "action": "buy",
        "price": 1820,
        "shares": 100,
        "submitted_by": "agent",
        "submitted_at": "2026-05-22 10:45:30",
        "reason": "技术面超卖+基本面优质"
      }
    ]
  }
}
```

---

### 3.3 审批订单

**命令**: `quant order +approve`

**参数**:
- `order-id` (required): 订单ID
- `approved-by` (required): 审批人
- `action` (required): 审批动作 - `approve` | `reject`
- `feedback` (optional): 反馈意见

**返回**:
```json
{
  "status": "success",
  "data": {
    "order_id": "order_20260522_104530_001",
    "status": "approved",
    "approved_by": "user_zhang",
    "approved_at": "2026-05-22 11:00:00",
    "feedback": "同意，分析合理"
  }
}
```

---

### 3.4 执行订单

**命令**: `quant order +execute`

**参数**:
- `order-id` (required): 订单ID
- `execution-price` (optional): 实际成交价
- `execution-time` (optional): 成交时间

**返回**:
```json
{
  "status": "success",
  "data": {
    "order_id": "order_20260522_104530_001",
    "status": "executed",
    "execution_price": 1825,
    "execution_time": "2026-05-22 11:05:00",
    "slippage": 5,
    "commission": 18.25
  }
}
```

---

### 3.5 获取订单历史

**命令**: `quant order +get-history`

**参数**:
- `symbol` (optional): 股票代码
- `status` (optional): 状态过滤
- `start-date` (optional): 开始日期
- `end-date` (optional): 结束日期
- `limit` (optional): 返回数量

**返回**:
```json
{
  "status": "success",
  "data": {
    "total": 156,
    "orders": []
  }
}
```

---

## Agent决策与绩效模块

### 4.1 记录Agent决策

**命令**: `quant agent +record-decision`

**参数**:
- `symbol` (required): 股票代码
- `decision` (required): 决策 - `buy` | `sell` | `hold`
- `confidence` (required): 置信度 (0-1)
- `analysis-log-id` (required): 分析日志ID
- `reasoning` (optional): 推理过程 (JSON)

**返回**:
```json
{
  "status": "success",
  "data": {
    "decision_id": "decision_20260522_104530_001",
    "symbol": "600519",
    "decision": "buy",
    "confidence": 0.85,
    "timestamp": "2026-05-22 10:45:30"
  }
}
```

---

### 4.2 更新决策反馈

**命令**: `quant agent +update-feedback`

**参数**:
- `decision-id` (required): 决策ID
- `feedback` (required): 反馈 - `correct` | `wrong` | `partial`
- `user-comment` (optional): 用户评论
- `actual-result` (optional): 实际结果 (JSON)

**返回**:
```json
{
  "status": "success",
  "data": {
    "decision_id": "decision_20260522_104530_001",
    "feedback": "correct",
    "updated_at": "2026-05-25 15:00:00"
  }
}
```

---

### 4.3 获取Agent绩效

**命令**: `quant agent +get-performance`

**参数**:
- `days` (optional): 天数，默认30
- `metric` (optional): 指标类型，默认 `all`

**返回**:
```json
{
  "status": "success",
  "data": {
    "period": "2026-04-22 to 2026-05-22",
    "total_decisions": 156,
    "accuracy": {
      "correct": 102,
      "wrong": 38,
      "pending": 16,
      "accuracy_rate": 0.654
    },
    "profit": {
      "total_trades": 45,
      "winning_trades": 31,
      "losing_trades": 14,
      "win_rate": 0.689,
      "total_pnl": 125600,
      "avg_pnl_per_trade": 2791
    },
    "common_errors": [
      {
        "error_type": "over_optimistic",
        "count": 15,
        "description": "技术面评分过于乐观"
      }
    ]
  }
}
```

---

## 数据快照模块

### 5.1 保存数据快照

**命令**: `quant snapshot +save`

**参数**:
- `symbol` (required): 股票代码
- `data-type` (required): 数据类型
- `data` (required): 数据内容 (JSON)
- `timestamp` (optional): 时间戳

**返回**:
```json
{
  "status": "success",
  "data": {
    "snapshot_id": "snapshot_20260522_104530_001",
    "symbol": "600519",
    "data_type": "quote",
    "timestamp": "2026-05-22 10:45:30"
  }
}
```

---

### 5.2 获取历史快照

**命令**: `quant snapshot +get`

**参数**:
- `snapshot-id` (optional): 快照ID
- `symbol` (optional): 股票代码
- `timestamp` (optional): 时间戳
- `data-type` (optional): 数据类型

**返回**:
```json
{
  "status": "success",
  "data": {
    "snapshot_id": "snapshot_20260522_104530_001",
    "symbol": "600519",
    "data_type": "quote",
    "timestamp": "2026-05-22 10:45:30",
    "data": {}
  }
}
```

---

## 审批流程模块

### 6.1 获取审批规则

**命令**: `quant approval +get-rules`

**返回**:
```json
{
  "status": "success",
  "data": {
    "rules": [
      {
        "rule_id": "rule_001",
        "condition": "order_amount > 100000",
        "action": "require_approval",
        "approver": "user"
      }
    ]
  }
}
```

---

### 6.2 更新审批规则

**命令**: `quant approval +update-rules`

**参数**:
- `rules` (required): 规则列表 (JSON)

**返回**:
```json
{
  "status": "success",
  "data": {
    "rules_updated": 3
  }
}
```

---

## 交易信号模块

### 7.1 获取买卖点信号

**命令**: `quantsys signal get-trading-signals`

**参数**:
- `symbol` (required): 股票代码
- `days` (optional): 查询天数，默认90天
- `signal_type` (optional): 信号类型 - `all` | `buy` | `sell` | `hold`
- `operator` (optional): 操作者筛选 - `all` | `agent` | `user`
- `status` (optional): 执行状态 - `all` | `pending` | `executed` | `rejected`

**返回**:
```json
{
  "status": "success",
  "data": {
    "symbol": "600519",
    "signals": [
      {
        "id": "signal_001",
        "date": "2026-05-10",
        "timestamp": 1715328000000,
        "type": "buy",
        "price": 1820,
        "confidence": 85,
        "reasons": [
          "RSI超卖(28)",
          "MACD金叉",
          "布林带下轨支撑"
        ],
        "operator": "Agent-v2",
        "status": "executed",
        "execution": {
          "executed": true,
          "executed_price": 1825,
          "executed_time": "2026-05-10 10:30",
          "position": "10%"
        },
        "pnl": {
          "current": 230,
          "percentage": 12.6
        }
      },
      {
        "id": "signal_002",
        "date": "2026-05-20",
        "timestamp": 1716192000000,
        "type": "sell",
        "price": 2050,
        "confidence": 90,
        "reasons": [
          "达到止盈目标(+12.6%)",
          "RSI超买(75)"
        ],
        "operator": "Agent-v2",
        "status": "executed",
        "execution": {
          "executed": true,
          "executed_price": 2045,
          "executed_time": "2026-05-20 14:15",
          "position": "100%"
        },
        "pnl": {
          "realized": 2200,
          "percentage": 12.6
        }
      }
    ],
    "statistics": {
      "total_signals": 22,
      "buy_signals": 12,
      "sell_signals": 10,
      "buy_accuracy": 68.5,
      "sell_accuracy": 72.3,
      "avg_holding_days": 8.5,
      "avg_return": 8.2,
      "win_rate": 70.5,
      "profit_loss_ratio": 2.3
    }
  }
}
```

**使用示例**:
```bash
# 获取600519最近90天的所有买卖点
quantsys signal get-trading-signals --symbol 600519 --days 90

# 只获取Agent生成的买入信号
quantsys signal get-trading-signals --symbol 600519 --signal-type buy --operator agent

# 只获取已执行的信号
quantsys signal get-trading-signals --symbol 600519 --status executed
```

---

### 7.2 记录买卖点信号

**命令**: `quantsys signal record-signal`

**参数**:
- `symbol` (required): 股票代码
- `signal_type` (required): 信号类型 - `buy` | `sell` | `hold`
- `price` (required): 信号价格
- `confidence` (required): 置信度 (0-100)
- `reasons` (required): 信号原因列表 (JSON数组)
- `operator` (optional): 操作者，默认 `Agent-v2`
- `metadata` (optional): 额外元数据 (JSON字符串)

**返回**:
```json
{
  "status": "success",
  "data": {
    "signal_id": "signal_003",
    "timestamp": "2026-05-22 10:45:30",
    "symbol": "600519",
    "type": "buy",
    "price": 1850,
    "confidence": 82,
    "status": "pending"
  }
}
```

**使用示例**:
```bash
quantsys signal record-signal \
  --symbol 600519 \
  --signal-type buy \
  --price 1850 \
  --confidence 82 \
  --reasons '["RSI超卖(32)", "MACD即将金叉", "成交量放大"]' \
  --operator Agent-v2
```

---

### 7.3 标记信号错误

**命令**: `quantsys signal mark-error`

**参数**:
- `signal_id` (required): 信号ID
- `error_type` (required): 错误类型 - `wrong_timing` | `wrong_price` | `wrong_reason` | `other`
- `feedback` (optional): 反馈说明
- `corrected_by` (optional): 标记人，默认 `User`

**返回**:
```json
{
  "status": "success",
  "data": {
    "signal_id": "signal_001",
    "marked_as_error": true,
    "error_type": "wrong_timing",
    "feedback": "买入时机过早，应该等待MACD完全金叉",
    "marked_time": "2026-05-22 15:30"
  }
}
```

**使用示例**:
```bash
quantsys signal mark-error \
  --signal-id signal_001 \
  --error-type wrong_timing \
  --feedback "买入时机过早，应该等待MACD完全金叉"
```

---

### 7.4 获取信号统计

**命令**: `quantsys signal get-statistics`

**参数**:
- `symbol` (optional): 股票代码，不指定则统计所有股票
- `days` (optional): 统计天数，默认30天
- `operator` (optional): 操作者筛选

**返回**:
```json
{
  "status": "success",
  "data": {
    "period": "30天",
    "total_signals": 156,
    "buy_signals": 85,
    "sell_signals": 71,
    "accuracy": {
      "overall": 67.3,
      "buy": 68.5,
      "sell": 72.3
    },
    "performance": {
      "avg_return": 8.2,
      "win_rate": 70.5,
      "profit_loss_ratio": 2.3,
      "avg_holding_days": 8.5
    },
    "errors": {
      "total": 28,
      "wrong_timing": 15,
      "wrong_price": 8,
      "wrong_reason": 5
    }
  }
}
```

---

## 实现优先级

### P0（必须）
- ✅ `agent.log_action` + `agent.get_logs`
- ✅ `order.create` + `order.get_pending` + `order.approve`
- ✅ `portfolio.get_positions` + `portfolio.update_position`
- ✅ `signal.get_trading_signals` + `signal.record_signal` ⭐ 新增

### P1（重要）
- ✅ `agent.record_decision` + `agent.get_performance`
- ✅ `order.execute` + `order.get_history`
- ✅ `snapshot.save` + `snapshot.get`
- ✅ `signal.mark_error` + `signal.get_statistics` ⭐ 新增

### P2（可选）
- ✅ `approval.get_rules` + `approval.update_rules`
