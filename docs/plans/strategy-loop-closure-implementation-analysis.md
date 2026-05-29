# 策略循环闭合计划实施分析

**基于项目**: quantsys-v2  
**分析日期**: 2026-05-29  
**计划文档**: [docs/plans/strategy-loop-closure-plan.md](./strategy-loop-closure-plan.md)

---

## 📊 执行摘要

quantsys-v2 项目**已具备 60-70% 的基础设施**，可以直接推进策略循环闭合计划。关键发现：

| 优先级 | 任务 | 当前状态 | 可行性 | 预估工时调整 |
|--------|------|---------|--------|-------------|
| **P0-1** | 参数搜索引擎 | ✅ **已实现 80%** | 🟢 高 | 4.5h → **1.5h** |
| **P1** | 策略类型扩展 | ✅ **已实现 70%** | 🟢 高 | 4.5h → **2h** |
| **P2** | 知识积累+实盘跟踪 | ✅ **已实现 50%** | 🟢 高 | 6.5h → **4h** |
| **P3-1** | 策略熔断 | ❌ 未实现 | 🟢 高 | 2h → **2h** |
| **P3-2** | 市场风格检测 | ⚠️ 部分基础 | 🟡 中 | 3h → **4h** |
| **P3-3** | 策略版本管理 | ❌ 未实现 | 🟢 高 | 3h → **3h** |
| **P4-A** | 回测质量升级 | ⚠️ 部分基础 | 🟢 高 | 4h → **5h** |
| **P4-B** | 策略组合管理 | ⚠️ 部分基础 | 🟡 中 | 5h → **6h** |
| **P4-C** | Agent 自主研发 | ⚠️ 部分基础 | 🟡 中 | 6h → **7h** |
| **P4-D** | 实盘质量监控 | ⚠️ 部分基础 | 🟢 高 | 4h → **5h** |

**总工时**: 原计划 42.5h → **调整后 39.5h**（节省 3h，因已有基础设施）

---

## 🎯 P0-1：参数搜索引擎 — 80% 已完成

### 当前状态 ✅

**已实现**（[api/routes/analysis.py:L223-L350](../quantsys-v2/api/routes/analysis.py)）：

```python
@analysis_bp.route('/api/portfolio/strategy-optimize', methods=['POST'])
def strategy_optimize():
    """
    策略参数网格搜索优化（v2 重写 — 真实回测）
    
    - ✅ 笛卡尔积参数组合生成
    - ✅ ThreadPoolExecutor 并行回测（10 workers）
    - ✅ 真实回测评分（调用 StrategyCodeService.backtest_strategy）
    - ✅ 多指标支持：sharpe / return / win_rate / calmar
    - ✅ Top N 排序输出
    - ✅ 完整的测试覆盖（tests/test_strategy_optimize.py）
    """
```

**核心能力**：
- ✅ 参数网格定义 + 笛卡尔积生成
- ✅ 并行回测执行（ThreadPoolExecutor, 10 workers）
- ✅ 真实回测打分（非假优化器）
- ✅ 多指标优化（sharpe/return/win_rate/calmar）
- ✅ API 端点：`POST /api/portfolio/strategy-optimize`

### 缺失部分 ⚠️

1. **CLI 命令未对接**：`quant_cli strategy.optimize` 仍指向 v1 假优化器
2. **Agent 工具未集成**：TypeScript Agent 无法调用此 API
3. **参数空间建议**：无自动参数范围推荐

### 实施路径（1.5h）

| # | 任务 | 估时 | 文件 |
|---|------|------|------|
| 1 | CLI 命令重写：`strategy.optimize` → v2 API | 0.5h | `quantsys-v2/cli/main.py` |
| 2 | Agent 工具集成：`strategy_optimize` 工具 | 0.5h | `src/infrastructure/tools/invest/` |
| 3 | 端到端测试 + 文档更新 | 0.5h | `tests/`, `CLAUDE.md` |

**验收标准**：
```bash
# CLI 调用
python cli/main.py strategy optimize --id 1 --symbol 600519.SH \
  --param-grid '{"rsi_low": [25,30], "rsi_high": [70,75]}'

# Agent 调用
strategy_optimize({
  strategy_id: 1,
  symbol: "600519.SH",
  param_grid: { rsi_low: [25, 30], rsi_high: [70, 75] }
})
```

---

## 🎯 P1：策略类型扩展 — 70% 已完成

### 当前状态 ✅

**StrategyFactory 已实现**（[quantlib/engine/strategy_factory.py](../quantsys-v2/quantlib/engine/strategy_factory.py)）：

```python
class StrategyFactory:
    _STRATEGY_MODULES = [
        'ma_cross', 'rsi_reversal', 'bollinger_breakout',
        'turtle_strategy', 'donchian_channel_strategy',
        'momentum_strategy', 'breakout_strategy',
        'mean_reversion_strategy', 'volatility_breakout_strategy',
        'pairs_correlation_strategy',
        'multi_factor_strategy', 'ml_prediction_strategy',
        'adx_trend_strategy', 'cci_reversal_strategy',
        'grid_trading_strategy',
        'config_driven_strategy',
        'multi_factor_swing_strategy',
        'ensemble_vote_strategy',
    ]  # 18 种策略
    
    @classmethod
    def auto_discover(cls): ...
    
    @classmethod
    def list_all(cls) -> list[str]: ...
```

**已有能力**：
- ✅ 18 种内置策略自动发现
- ✅ `StrategyFactory.list_all()` 返回所有策略类型
- ✅ `StrategyFactory.create(strategy_type, **kwargs)` 动态创建
- ✅ 策略元数据提取（category, params, schema）

### 缺失部分 ⚠️

1. **Agent 工具硬编码**：`strategy_execute` 仍然只支持 4 种策略
2. **用户模板有限**：只有 `indicator` / `script` 两种，缺少 `trend_following` / `mean_reversion` / `multi_factor`
3. **API 端点缺失**：无 `GET /api/strategies/list` 返回 18 种策略元数据

### 实施路径（2h）

| # | 任务 | 估时 | 文件 |
|---|------|------|------|
| 1 | API 端点：`GET /api/strategies/list` | 0.5h | `quantsys-v2/api/routes/strategies.py` |
| 2 | Agent 工具动态化：`strategy_execute` 读取 API | 0.5h | `src/infrastructure/tools/invest/` |
| 3 | 用户模板扩展：3 种新模板 + 校验器 | 0.5h | `quantsys-v2/services/strategy_code_service.py` |
| 4 | 文档更新 + 测试 | 0.5h | `CLAUDE.md`, `tests/` |

**验收标准**：
```typescript
// Agent 可调用全部 18 种策略
strategy_execute({ 
  symbol: "600519.SH", 
  strategy: "ensemble_vote"  // 之前不可用
})

// 用户可创建趋势跟踪策略
strategy_create({
  name: "双均线趋势",
  code_type: "trend_following",
  params: { fast: 5, slow: 20 }
})
```

---

## 🎯 P2：知识积累+实盘跟踪 — 50% 已完成

### 当前状态 ✅

**SignalTestLog 已实现**（[services/signal_test_log.py](../quantsys-v2/services/signal_test_log.py)）：

```python
class SignalTestLog:
    """信号测试日志管理器
    
    已实现功能：
    - ✅ 信号写入 quant.signal_test_log 表
    - ✅ 回扫验证：T+N 日后计算模拟盈亏
    - ✅ 统计：胜率、平均盈亏、按月/策略分布
    - ✅ API 端点：/api/signal-test/*
    """
    
    def record_signal(self, signal: Dict) -> int: ...
    def verify_pending(self, days_after: int = 5): ...
    def get_statistics(self, strategy_name=None, ...): ...
```

**表结构已完整**：
```sql
CREATE TABLE quant.signal_test_log (
    id, symbol, strategy_name, signal_date, action,
    signal_price, entry_price, stop_loss,
    -- 验证字段
    status, verify_date, current_price, pnl_pct,
    hit_stop_loss, hit_target_1/2/3,
    max_pnl_pct, max_loss_pct, holding_days
);
```

### 缺失部分 ⚠️

1. **实盘订单未关联**：`signal_execution` 创建订单时不写 `signal_test_log`
2. **盈亏追踪断裂**：订单成交/平仓时不回写 `pnl_pct`
3. **经验库未自动更新**：统计结果不写入 `query_experience`
4. **performance DB 表缺失**：无 `quant.strategy_performance` 表

### 实施路径（4h）

| # | 任务 | 估时 | 文件 |
|---|------|------|------|
| 1 | `quant.strategy_performance` 表 + Repository | 1h | `quantsys-v2/repositories/strategy_performance_repository.py` |
| 2 | 订单→盈亏追踪：`fill`/`sell` 回写 | 1h | `quantsys-v2/services/trade_service.py` |
| 3 | 经验自动积累：统计 → `query_experience` | 1h | `quantsys-v2/services/experience_service.py` |
| 4 | API + 测试 | 1h | `api/routes/signal_test.py`, `tests/` |

**验收标准**：
```python
# 信号 → 订单 → 成交 → 盈亏全程可追踪
signal = strategy.run(symbol="600519.SH")
order = signal_execution.create_order(signal)
# ... 成交后 ...
performance = strategy_performance.get(strategy_name="rsi_reversal")
# {win_rate: 0.68, avg_pnl: 0.032, sample_size: 45}

# Agent 查询经验
experience = query_experience("rsi_reversal 在震荡市表现如何")
# "该策略在震荡市胜率 68%，平均收益 +3.2%（样本 45 笔）"
```

---

## 🎯 P3：策略运维与自适应

### P3-1：策略熔断 — 未实现 ❌

**状态**：无熔断机制，需从零实现。

**实施路径（2h）**：

| # | 任务 | 估时 |
|---|------|------|
| 1 | `StrategyCircuitBreaker` service + 状态机 | 1h |
| 2 | `signal_execution` 集成熔断检查 | 0.5h |
| 3 | 告警通知 + 测试 | 0.5h |

### P3-2：市场风格检测 — 部分基础 ⚠️

**已有基础**：
- ✅ `factor_calculate` 工具可计算因子
- ✅ 因子数据存储在 `quant.factors` 表

**缺失**：
- ❌ 因子日收益截面计算
- ❌ 风格归因逻辑
- ❌ 策略权重调整器

**实施路径（4h）**：需要实现完整的因子收益计算和风格检测逻辑。

### P3-3：策略版本管理 — 未实现 ❌

**状态**：`StrategyCodeService.update()` 直接覆盖，无版本历史。

**实施路径（3h）**：标准的版本控制实现，无技术难点。

---

## 🎯 P4：能力升级

### P4-A：回测质量升级 — 部分基础 ⚠️

**已有基础**：
- ✅ 回测引擎已实现（`StrategyCodeService.backtest_strategy`）
- ✅ 基础的成交逻辑

**缺失**：
- ❌ 手续费模型（零成本）
- ❌ 滑点模型（零滑点）
- ❌ 流动性约束（无限流动性）
- ❌ 涨跌停检查

**实施路径（5h）**：需要实现三层成本模型。

### P4-B：策略组合管理 — 部分基础 ⚠️

**已有基础**：
- ✅ `SignalArbiter` 存在（信号冲突裁决）
- ✅ Portfolio 相关 API

**缺失**：
- ❌ 风险预算计算
- ❌ 策略相关性矩阵
- ❌ 组合级硬约束

**实施路径（6h）**：需要实现完整的组合管理逻辑。

### P4-C：Agent 自主研发 — 部分基础 ⚠️

**已有基础**：
- ✅ P0-1 参数搜索引擎
- ✅ P3-2 市场风格检测（待实现）
- ✅ `StrategyCodeService.create_strategy`

**缺失**：
- ❌ 市场状态 → 策略类型匹配器
- ❌ 自动策略发现管线
- ❌ Agent 工具集成

**实施路径（7h）**：需要串联多个模块。

### P4-D：实盘质量监控 — 部分基础 ⚠️

**已有基础**：
- ✅ P2 的 `signal_test_log` 和 `strategy_performance`
- ✅ 监控相关 API（`api/routes/monitoring.py`）

**缺失**：
- ❌ 回测 vs 实盘偏离度计算
- ❌ 执行质量采集
- ❌ 异常检测器

**实施路径（5h）**：需要实现质量监控面板。

---

## 📅 推荐执行顺序（调整版）

### 阶段 1：快速闭环（1 周，~7.5h）

**目标**：让策略循环的核心流程跑通。

```
批次 1.1（并行）: P0-1 (1.5h) + P1 (2h)          = 3.5h
批次 1.2:         P2 步骤 1-2 (2h)                = 2h
批次 1.3:         P2 步骤 3-4 (2h)                = 2h
──────────────────────────────────────────────────
阶段 1 总计:                                      = 7.5h
```

**验收标准**：
- ✅ Agent 可调用 18 种策略
- ✅ 参数优化返回真实回测结果
- ✅ 信号 → 订单 → 盈亏全程可追踪
- ✅ 经验库自动积累

### 阶段 2：运维保障（1 周，~9h）

**目标**：确保闭环运转的质量和韧性。

```
批次 2.1（并行）: P3-1 (2h) + P3-3 (3h)          = 5h
批次 2.2:         P3-2 (4h)                       = 4h
──────────────────────────────────────────────────
阶段 2 总计:                                      = 9h
```

**验收标准**：
- ✅ 策略连亏 5 次自动熔断
- ✅ 市场风格检测 + 策略权重调整
- ✅ 策略版本历史 + 回滚

### 阶段 3：质量提升（2 周，~23h）

**目标**：从"能跑"到"跑得好"。

```
批次 3.1:         P4-A (5h)                       = 5h
批次 3.2:         P4-D (5h)                       = 5h
批次 3.3:         P4-B (6h)                       = 6h
批次 3.4:         P4-C (7h)                       = 7h
──────────────────────────────────────────────────
阶段 3 总计:                                      = 23h
```

**验收标准**：
- ✅ 回测收益与实盘偏差 ≤ 5%
- ✅ 实盘偏离超阈值自动告警
- ✅ 多策略组合级决策
- ✅ Agent 自主研发策略

---

## 🚀 立即可启动的任务

### 高优先级（本周可完成）

1. **P0-1 CLI 对接**（0.5h）
   - 文件：`quantsys-v2/cli/main.py`
   - 改动：`strategy optimize` 命令指向 v2 API
   - 风险：低

2. **P1 API 端点**（0.5h）
   - 文件：`quantsys-v2/api/routes/strategies.py`
   - 新增：`GET /api/strategies/list`
   - 风险：低

3. **P2 performance 表**（1h）
   - 文件：`quantsys-v2/repositories/strategy_performance_repository.py`
   - 新增：表结构 + CRUD
   - 风险：低

### 中优先级（下周启动）

4. **P3-1 熔断机制**（2h）
   - 文件：`quantsys-v2/services/strategy_circuit_breaker.py`
   - 新增：状态机 + 熔断逻辑
   - 风险：中

5. **P3-3 版本管理**（3h）
   - 文件：`quantsys-v2/services/strategy_version_service.py`
   - 新增：版本表 + 版本控制
   - 风险：低

---

## ⚠️ 风险与依赖

### 技术风险

| 风险 | 影响 | 缓解措施 |
|------|------|---------|
| P3-2 因子收益计算复杂 | 🟡 中 | 先实现简化版（单因子），后续扩展 |
| P4-A 成本模型参数调优 | 🟡 中 | 参考行业标准参数，后续根据实盘调整 |
| P4-C Agent 自主研发稳定性 | 🟡 中 | 初期人工审核，逐步放开 |

### 依赖关系

```
P0-1 ──┐
       ├──→ P4-C (Agent 自主研发)
P3-2 ──┘

P2 ────→ P4-D (实盘监控)

P3-1 ──→ P4-D (告警 → 熔断)

P4-A ──→ P4-B (准确回测 → 组合决策)
```

### 数据库变更

**新增表**：
1. `quant.strategy_performance` — P2 步骤 1
2. `quant.strategy_versions` — P3-3 步骤 1
3. `quant.circuit_breaker_state` — P3-1 步骤 1

**表结构变更**：
- `quant.signal_test_log` — 新增 `order_id`, `source` 字段（P2 步骤 2）

---

## 📝 总结

### 关键发现

1. **基础设施完善**：quantsys-v2 已实现 60-70% 的必要基础设施，大幅降低实施难度。

2. **P0-1 几乎完成**：参数搜索引擎已实现核心逻辑，只需对接 CLI 和 Agent。

3. **P2 表结构完整**：`signal_test_log` 表设计完善，只需补充订单关联和经验积累逻辑。

4. **P3/P4 需新建**：运维和质量提升模块大部分需从零实现，但无技术难点。

### 工时节省

- **原计划**：42.5h
- **调整后**：39.5h
- **节省**：3h（因已有基础设施）

### 建议

1. **优先阶段 1**：7.5h 即可让核心循环跑通，快速验证价值。

2. **并行推进**：P0-1 + P1 可并行，P3-1 + P3-3 可并行。

3. **渐进式实施**：P3-2 和 P4 系列可根据实际需求调整优先级。

4. **测试先行**：每个模块实施前先写测试，确保质量。

---

**下一步行动**：
1. 确认阶段 1 的 7.5h 工时预算
2. 启动 P0-1 CLI 对接（0.5h，立即可做）
3. 启动 P1 API 端点（0.5h，立即可做）
