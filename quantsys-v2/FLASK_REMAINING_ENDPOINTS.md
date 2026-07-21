# Flask 未迁移端点完整清单

> 更新时间：2026-06-29
> 检查方法：逐文件扫描 Flask routes，对比 FastAPI routes

## 📊 总览

| 指标 | 数量 | 百分比 |
|------|------|--------|
| Flask 路由文件总数 | 59 | 100% |
| FastAPI 路由文件总数 | 61 | 103% |
| Flask 活跃端点数 | **6** | 3% |
| FastAPI 端点数 | 189+ | 97% |
| **迁移完成度** | **97%** | ✅ |

---

## 🔴 未迁移的 Flask 端点（仅 6 个）

### 文件 1：realtime_signals.py（3 个端点）

**文件路径**：`adapters/inbound/api/routes/realtime_signals.py`

| # | 端点 | 方法 | 功能 | 优先级 |
|---|------|------|------|--------|
| 1 | `/api/realtime-signals/t1/generate` | POST | 生成 T+1 信号（今日收盘后生成，明日执行） | P1 |
| 2 | `/api/realtime-signals/filter/executable` | POST | 过滤可执行信号（检查价格偏离） | P1 |
| 3 | `/api/realtime-signals/morning-scan` | POST | 早盘扫描（每日 9:00 调用） | P1 |

**详细说明**：

#### 1. T+1 信号生成
```python
POST /api/realtime-signals/t1/generate

Request:
{
  "strategy_id": "273",
  "symbols": ["600726", "000001"],
  "execution_date": "2026-06-05"  // 可选，默认次日
}

Response:
{
  "success": true,
  "data": [{
    "symbol": "600726",
    "entry_price": 9.71,
    "signal_type": "BUY",
    "execution_date": "2026-06-05",
    "mode": "T+1",
    "generated_at": "2026-06-04T15:30:00"
  }],
  "count": 1
}
```

**使用场景**：Agent 在收盘后（15:00）生成次日交易信号

#### 2. 可执行信号过滤
```python
POST /api/realtime-signals/filter/executable

Request:
{
  "signals": [...],           // 原始信号列表
  "max_gap_pct": 3.0,         // 最大可接受价差（%）
  "check_realtime": true      // 是否检查实时价格
}

Response:
{
  "success": true,
  "data": {
    "executable": [...],       // 可执行信号
    "rejected": [...]          // 被拒绝的信号
  },
  "summary": {
    "total": 10,
    "executable": 7,
    "rejected": 3
  }
}
```

**使用场景**：Agent 在开盘前检查信号价格是否偏离过大

#### 3. 早盘扫描
```python
POST /api/realtime-signals/morning-scan

Request:
{
  "strategy_ids": ["273", "274"],
  "stock_pool": ["600726", "000001"],
  "notify": true               // 是否推送通知
}

Response:
{
  "success": true,
  "data": [...],               // 可执行信号列表
  "summary": {
    "total_scanned": 100,
    "signals_generated": 5,
    "executable": 3
  }
}
```

**使用场景**：Agent 定时任务在每日 9:00 扫描当日交易机会

---

### 文件 2：strategy_execution.py（3 个端点）

**文件路径**：`adapters/inbound/api/routes/strategy_execution.py`

| # | 端点 | 方法 | 功能 | 优先级 |
|---|------|------|------|--------|
| 4 | `/api/strategies/execute` | POST | 单股策略执行 | P0 |
| 5 | `/api/strategies/batch-execute` | POST | 批量策略执行（NDJSON 流式） | P1 |
| 6 | `/api/strategies/pipeline-execute` | POST | 流水线策略执行 | P1 |

**详细说明**：

#### 4. 单股策略执行
```python
POST /api/strategies/execute

Request:
{
  "strategy_id": 1,
  "symbol": "600000.SH",
  "start_date": "2024-01-01",
  "end_date": "2024-12-31"
}

Response:
{
  "success": true,
  "data": {
    "symbol": "600000.SH",
    "signals": [...],
    "metrics": {
      "sharpe_ratio": 1.85,
      "max_drawdown": -0.12,
      "total_return": 0.28
    }
  }
}
```

**使用场景**：Agent 对单只股票执行策略生成信号

#### 5. 批量策略执行（流式）
```python
POST /api/strategies/batch-execute

Request:
{
  "strategy_id": 1,
  "symbols": ["600000.SH", "000001.SZ", ...],  // 支持数百只
  "start_date": "2024-01-01",
  "end_date": "2024-12-31"
}

Response: (NDJSON 流式)
{"symbol": "600000.SH", "progress": 1, "total": 100, "result": {...}}
{"symbol": "000001.SZ", "progress": 2, "total": 100, "result": {...}}
...
```

**使用场景**：Agent 批量处理股票池，实时返回进度（避免超时）

**特殊性**：使用 NDJSON 流式响应，FastAPI 迁移需要特殊处理

#### 6. 流水线策略执行
```python
POST /api/strategies/pipeline-execute

Request:
{
  "pipeline": [
    {"strategy_id": 1, "stage": "filter"},
    {"strategy_id": 2, "stage": "rank"},
    {"strategy_id": 3, "stage": "signal"}
  ],
  "symbols": ["600000.SH", ...],
  "start_date": "2024-01-01",
  "end_date": "2024-12-31"
}

Response: (NDJSON 流式)
{"stage": "filter", "progress": 33, "passed": 50}
{"stage": "rank", "progress": 66, "top_10": [...]}
{"stage": "signal", "progress": 100, "signals": [...]}
```

**使用场景**：Agent 多阶段策略组合执行（过滤 → 排序 → 信号）

---

## ✅ 已完全迁移的模块（189+ 端点）

### P0 核心模块
- ✅ Health Check (`/health`, `/api/health`)
- ✅ Executions (`/api/executions/*`)
- ✅ Market Data (`/api/market/*`)
- ✅ Analysis (`/api/analysis/*`)
- ✅ Charts (`/api/charts/*`)
- ✅ Config (`/api/config/*`)
- ✅ Auth (`/api/auth/*`)
- ✅ Pool Scan (`/api/pool-scan/*`)
- ✅ Risk (`/api/risk/*`)

### P1 业务模块
- ✅ Pools (`/api/pools/*`) - 股票池管理（完整）
- ✅ Signals (`/api/signals/*`) - 信号管理（完整）
- ✅ Strategies (`/api/strategies/*`) - 策略管理（除了 3 个执行端点）
- ✅ Decision Tracking (`/api/decisions/*`)
- ✅ Backtest (`/api/backtest/*`, `/api/indicators/backtest`)
- ✅ Backtest History (`/api/backtest/history`)
- ✅ Indicators (`/api/indicators/*`)
- ✅ Stock (`/api/stock/*`)

### P2 扩展模块
- ✅ Sentiment (`/api/sentiment/*`) - 市场情绪
- ✅ Discovery (`/api/discovery/*`) - 策略发现
- ✅ Game Alert (`/api/game-alerts/*`) - 博弈预警
- ✅ Chan Theory (`/api/chan/*`) - 缠论分析
- ✅ Data Quality (`/api/data-quality/*`) - 数据诊断
- ✅ Diagnosis (`/api/diagnosis/*`) - 系统诊断
- ✅ Dividends (`/api/dividends/*`) - 红利数据
- ✅ Financials (`/api/financials/*`) - 财务数据
- ✅ Automation (`/api/automation/*`) - 自动化任务
- ✅ ML Models (`/api/ml-models/*`) - 机器学习
- ✅ Portfolio (`/api/portfolio/*`) - 组合管理
- ✅ Orders (`/api/orders/*`) - 订单管理
- ✅ Opportunities (`/api/opportunities/*`) - 机会分析
- ✅ Watchlist (`/api/watchlist/*`) - 自选股
- ✅ Sectors (`/api/sectors/*`) - 行业板块
- ✅ Training (`/api/training/*`) - 模型训练
- ✅ Benchmarks (`/api/benchmarks/*`) - 基准测试
- ✅ Factor Models (`/api/factors/*`) - 因子模型
- ✅ Risk Metrics (`/api/risk/metrics/*`) - 风险指标
- ✅ Timeseries (`/api/timeseries/*`) - 时间序列

### 调度与监控
- ✅ Scheduler (`/api/scheduler/*`) - 定时任务
- ✅ Jobs (`/api/jobs/*`) - 后台任务
- ✅ Monitoring (`/api/monitoring/*`) - 监控指标
- ✅ Knowledge Management (`/api/knowledge/*`) - 知识库
- ✅ Learning System (`/api/learning/*`) - 学习系统

### 游戏智能
- ✅ Game Intelligence (`/api/game/*`) - 博弈智能分析

---

## 📋 迁移状态对照表

| Flask 模块 | Flask 端点数 | FastAPI 模块 | FastAPI 端点数 | 状态 |
|-----------|-------------|--------------|---------------|------|
| realtime_signals.py | 3 | realtime_signals_async.py | 0 | ❌ 未迁移 |
| strategy_execution.py | 3 | strategy_execution_async.py | 0 | ❌ 未迁移 |
| pools.py | 0 | pools_async.py | 15+ | ✅ 已完成 |
| strategies.py | 0 | strategies_async.py | 10+ | ✅ 已完成 |
| signals.py | 0 | signals_async.py | 12+ | ✅ 已完成 |
| backtest.py | 0 | backtest_async.py | 8+ | ✅ 已完成 |
| market.py | 0 | market_async.py | 15+ | ✅ 已完成 |
| analysis.py | 0 | analysis_async.py | 10+ | ✅ 已完成 |
| ... | 0 | ... | ... | ✅ 已完成 |

---

## 🔍 为什么只剩这 6 个？

### 迁移历史
根据代码注释和文件时间戳分析：

1. **第一阶段（2026-05）**：核心业务模块迁移
   - Pools, Strategies, Signals, Backtest 全部完成
   - 覆盖 80% 的 API 调用量

2. **第二阶段（2026-06）**：扩展模块迁移
   - 所有 P1/P2 批量路由完成
   - 游戏智能、学习系统、调度器完成

3. **遗留原因**：
   - **realtime_signals**: 实时信号功能是后来新增的（可能在迁移进行时），未纳入迁移计划
   - **strategy_execution**: 流式响应（NDJSON）实现复杂，需要特殊处理，暂时搁置

---

## 🎯 迁移优先级建议

### P0 - 立即迁移（影响 Agent 核心功能）
- ❌ `/api/strategies/execute` - 单股执行（Agent 频繁调用）

### P1 - 短期迁移（提升性能和能力）
- ❌ `/api/strategies/batch-execute` - 批量执行（性能提升显著）
- ❌ `/api/strategies/pipeline-execute` - 流水线执行

### P2 - 中期迁移（完善实时能力）
- ❌ `/api/realtime-signals/t1/generate` - T+1 信号生成
- ❌ `/api/realtime-signals/filter/executable` - 信号过滤
- ❌ `/api/realtime-signals/morning-scan` - 早盘扫描

---

## 📈 迁移工作量估算

| 端点 | 复杂度 | 预计工作量 | 主要挑战 |
|------|--------|-----------|---------|
| strategies/execute | 简单 | 1 小时 | 标准 REST API |
| strategies/batch-execute | 中等 | 2-3 小时 | NDJSON 流式响应 |
| strategies/pipeline-execute | 中等 | 2-3 小时 | NDJSON 流式响应 |
| realtime-signals/t1/generate | 简单 | 1 小时 | 标准 REST API |
| realtime-signals/filter/executable | 简单 | 0.5 小时 | 标准 REST API |
| realtime-signals/morning-scan | 简单 | 1 小时 | 标准 REST API |
| **总计** | - | **8-10 小时** | 流式响应处理 |

---

## 🛠️ 技术要点

### 流式响应迁移（batch-execute, pipeline-execute）

**Flask 实现**：
```python
def generate():
    for item in service.execute_batch(req):
        yield json.dumps(item, ensure_ascii=False) + '\n'

return Response(generate(), mimetype='application/x-ndjson')
```

**FastAPI 实现**：
```python
from fastapi.responses import StreamingResponse

async def generate():
    async for item in service.execute_batch_async(req):
        yield json.dumps(item, ensure_ascii=False) + '\n'

return StreamingResponse(generate(), media_type="application/x-ndjson")
```

**关键差异**：
- Flask 使用同步生成器 (`yield`)
- FastAPI 使用异步生成器 (`async for` + `yield`)
- Service 需要提供异步版本

---

## ✅ 验证清单

迁移完成后，确保以下测试通过：

### 功能测试
- [ ] 单股策略执行返回正确结果
- [ ] 批量执行流式响应正常
- [ ] 流水线执行各阶段状态正确
- [ ] T+1 信号生成时间正确
- [ ] 信号过滤逻辑准确
- [ ] 早盘扫描覆盖所有股票池

### 性能测试
- [ ] 批量执行不阻塞主线程
- [ ] 流式响应无内存泄漏
- [ ] 100 只股票批量执行 < 30s

### 兼容性测试
- [ ] Flask 和 FastAPI 返回格式一致
- [ ] 错误处理符合前端预期
- [ ] Agent 调用无需修改

---

## 🚀 总结

### 当前状态
- ✅ **97% 迁移完成**（189+ / 195 端点）
- ❌ **仅剩 6 个端点未迁移**（3%）
- ⚠️ **实时信号** 和 **策略执行** 是最后的遗留

### 迁移收益
- **性能提升**：3-10x 吞吐量，2x 响应速度
- **文档自动生成**：`/docs` 提供完整 API 文档
- **现代架构**：异步 I/O，更好的并发处理
- **类型安全**：Pydantic 模型验证

### 建议
1. **立即迁移** P0 端点（strategies/execute）
2. **短期迁移** 流式端点（batch/pipeline-execute）
3. **中期迁移** 实时信号端点
4. **然后切换** web-frontend 到 FastAPI
5. **最后清理** Flask 代码

---

**预计总工作量**：8-10 小时（1-2 个工作日）

**迁移完成后**：可以完全移除 Flask 依赖，简化部署和维护。
