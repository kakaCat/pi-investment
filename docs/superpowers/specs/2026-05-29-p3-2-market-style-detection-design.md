# P3-2 市场风格检测系统设计文档

**创建时间**: 2026-05-29  
**状态**: 设计阶段  
**预估工时**: ~3h

---

## 一、概述

### 1.1 目标

实现市场风格自动检测系统，识别当前市场状态（动量、震荡、低波、价值），并根据策略历史表现动态调整策略权重，使 Agent 在推荐策略时能够考虑市场环境。

### 1.2 核心功能

- **市场风格检测**：每日收盘后聚合股票池技术指标，识别主导市场风格
- **策略权重调整**：静态权重表（冷启动）+ 动态权重计算（成熟策略）
- **Agent 集成**：`strategy_execute` 工具输出附加市场风格和权重建议

### 1.3 设计原则

- **混合方案**：轻量级技术指标聚合（快速实现），预留升级到 Fama-French/Barra 因子的接口
- **渐进式优化**：新策略使用静态权重，样本 ≥ 30 笔后自动切换到动态权重
- **日线级别**：每日收盘后更新，适配当前系统定位

---

## 二、架构设计

### 2.1 系统分层

```
┌─────────────────────────────────────────────────────────┐
│ Agent 层 (TypeScript)                                   │
│ - strategy_execute 工具输出附加 market_style 字段       │
└────────────────────┬────────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────────┐
│ API 层 (Flask)                                          │
│ - GET /api/market/style                                 │
│ - GET /api/strategies/{name}/weight                     │
└────────────────────┬────────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────────┐
│ 服务层 (Services)                                       │
│ ┌─────────────────────────┐  ┌──────────────────────┐  │
│ │ MarketStyleDetector     │  │ StrategyWeightAdjuster│ │
│ │ - 聚合技术指标          │  │ - 静态权重查询        │ │
│ │ - 计算风格得分          │  │ - 动态权重计算        │ │
│ │ - 选择主导风格          │  │ - 模式切换            │ │
│ └─────────────────────────┘  └──────────────────────┘  │
└────────────────────┬────────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────────┐
│ 仓储层 (Repositories)                                   │
│ - MarketStyleRepository                                 │
│ - StrategyWeightRepository                              │
│ - StrategyPerformanceRepository (已存在)                │
└────────────────────┬────────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────────┐
│ 数据层 (PostgreSQL)                                     │
│ - market_style_state (风格状态表)                       │
│ - strategy_weight_config (权重配置表)                   │
│ - strategy_performance (策略表现表，扩展 market_style)  │
└─────────────────────────────────────────────────────────┘
```

### 2.2 定时任务

```
每日 15:30 (收盘后 30 分钟)
    ↓
MarketStyleDetector.detect()
    ↓
计算风格得分 → 选择主导风格 → 写入 market_style_state
    ↓
缓存更新 (Redis)
```

---

## 三、数据模型设计

### 3.1 市场风格状态表

```sql
CREATE TABLE quant.market_style_state (
    id SERIAL PRIMARY KEY,
    trade_date DATE NOT NULL UNIQUE,
    style VARCHAR(50) NOT NULL,  -- 'momentum', 'oscillation', 'low_volatility', 'value'
    confidence FLOAT NOT NULL,   -- 0.0-1.0，置信度
    metrics JSONB,               -- 详细指标：{rsi_avg, macd_ratio, atr_percentile, ...}
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_market_style_date ON quant.market_style_state(trade_date DESC);
```

### 3.2 策略权重配置表

```sql
CREATE TABLE quant.strategy_weight_config (
    id SERIAL PRIMARY KEY,
    strategy_type VARCHAR(50) NOT NULL,  -- 'trend_following', 'mean_reversion', 'multi_factor'
    market_style VARCHAR(50) NOT NULL,   -- 'momentum', 'oscillation', 'low_volatility', 'value'
    static_weight FLOAT NOT NULL,        -- 静态权重调整（-1.0 到 +1.0）
    is_active BOOLEAN DEFAULT TRUE,
    updated_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(strategy_type, market_style)
);
```

**初始静态权重数据**：

| strategy_type | market_style | static_weight | 说明 |
|---------------|--------------|---------------|------|
| trend_following | momentum | +0.30 | 动量市趋势策略加成 30% |
| trend_following | oscillation | -0.40 | 震荡市趋势策略减成 40% |
| mean_reversion | oscillation | +0.30 | 震荡市均值回归加成 30% |
| mean_reversion | momentum | -0.20 | 动量市均值回归减成 20% |
| multi_factor | value | +0.20 | 价值市多因子加成 20% |
| multi_factor | low_volatility | +0.10 | 低波市多因子加成 10% |

### 3.3 扩展 strategy_performance 表

```sql
ALTER TABLE quant.strategy_performance 
ADD COLUMN market_style VARCHAR(50);

CREATE INDEX idx_strategy_performance_style 
ON quant.strategy_performance(strategy_name, market_style);
```

---

## 四、核心算法设计

### 4.1 MarketStyleDetector 风格检测算法

**输入**：最近 20 个交易日的股票池数据（沪深300 + 创业板50 + 科创50，约 400 只股票）

**计算步骤**：

```python
# Step 1: 聚合技术指标
rsi_avg = mean(all_stocks.rsi[-1])           # 最新 RSI 均值
macd_golden_ratio = count(macd > signal) / total  # MACD 金叉占比
atr_percentile = percentile(atr_avg, historical_30d)  # ATR 历史分位数
volume_growth = mean(volume[-5:] / volume[-20:-5])  # 成交量增长率

# Step 2: 计算风格得分（0-100）
momentum_score = (
    (rsi_avg - 50) * 2 +                    # RSI 偏离中性
    macd_golden_ratio * 50 +                # 金叉占比
    (volume_growth - 1) * 30                # 成交量放大
)

oscillation_score = (
    100 - abs(rsi_avg - 50) * 4 +           # RSI 接近中性
    (1 - abs(price_to_ma20 - 1)) * 50       # 价格接近均线
)

low_volatility_score = (
    (100 - atr_percentile) +                # ATR 低分位
    (1 - volatility_ratio) * 50             # 波动率收缩
)

value_score = (
    small_cap_excess_return * 10 +          # 小盘超额收益
    (1 - pe_ratio_percentile) * 30          # 低估值占比
)

# Step 3: 选择主导风格
scores = {
    'momentum': momentum_score,
    'oscillation': oscillation_score,
    'low_volatility': low_volatility_score,
    'value': value_score
}
dominant_style = max(scores, key=scores.get)
confidence = scores[dominant_style] / sum(scores.values())
```

**风格定义**：

- **动量市 (momentum)**：RSI 均值 > 55，MACD 金叉占比 > 60%，成交量放大
- **震荡市 (oscillation)**：RSI 均值 45-55，价格在布林带中轨附近波动
- **低波市 (low_volatility)**：ATR 均值 < 历史 30 分位数，波动率收缩
- **价值市 (value)**：小盘股相对大盘股超额收益 > 2%

### 4.2 StrategyWeightAdjuster 权重调整算法

**冷启动模式**（样本 < 30）：

```python
# 直接查静态权重表
static_weight = query_static_weight(strategy_type, market_style)
final_weight = 1.0 + static_weight  # 基准 1.0，调整 ±0.4
```

**动态模式**（样本 ≥ 30）：

```python
# 从 strategy_performance 统计历史表现
perf_by_style = query_performance(strategy_name, group_by='market_style')

# 计算各风格下的夏普比率
sharpe_momentum = perf_by_style['momentum'].sharpe
sharpe_oscillation = perf_by_style['oscillation'].sharpe

# 归一化权重
total_sharpe = sum(all_sharpe_values)
dynamic_weight = sharpe_current_style / total_sharpe * 2.0  # 归一化到 0-2 范围

# 平滑过渡：70% 动态 + 30% 静态
final_weight = dynamic_weight * 0.7 + (1.0 + static_weight) * 0.3
```

**模式切换逻辑**：

```python
sample_count = count_trades(strategy_name)

if sample_count < 30:
    mode = 'static'
    weight = get_static_weight(strategy_type, market_style)
else:
    mode = 'dynamic'
    weight = calculate_dynamic_weight(strategy_name, market_style)
```

---

## 五、API 设计

### 5.1 GET /api/market/style

获取当前市场风格。

**请求**：
```
GET /api/market/style
```

**响应**：
```json
{
  "success": true,
  "data": {
    "trade_date": "2026-05-29",
    "style": "momentum",
    "confidence": 0.68,
    "metrics": {
      "rsi_avg": 58.3,
      "macd_golden_ratio": 0.65,
      "atr_percentile": 72,
      "volume_growth": 1.15
    },
    "scores": {
      "momentum": 75,
      "oscillation": 42,
      "low_volatility": 28,
      "value": 35
    }
  }
}
```

### 5.2 GET /api/strategies/{strategy_name}/weight

获取策略在当前市场风格下的权重调整。

**请求**：
```
GET /api/strategies/my_ma_cross/weight?market_style=momentum
```

**响应**：
```json
{
  "success": true,
  "data": {
    "strategy_name": "my_ma_cross",
    "strategy_type": "trend_following",
    "market_style": "momentum",
    "weight_adjustment": 1.30,
    "mode": "dynamic",
    "sample_size": 45,
    "historical_performance": {
      "momentum": {"sharpe": 1.8, "win_rate": 0.65},
      "oscillation": {"sharpe": 0.6, "win_rate": 0.42}
    }
  }
}
```

---

## 六、Agent 集成

### 6.1 strategy_execute 工具输出扩展

**原输出**：
```json
{
  "signal": "buy",
  "confidence": 0.75,
  "entry_price": 150.0
}
```

**新增字段**：
```json
{
  "signal": "buy",
  "confidence": 0.75,
  "entry_price": 150.0,
  "market_style": "momentum",
  "weight_adjustment": 1.30,
  "style_recommendation": "当前为动量市，趋势策略加成30%"
}
```

### 6.2 定时任务

在 `quantsys-v2/runtime/scheduler/` 中添加：

```python
from runtime.scheduler import scheduler
from services.market_style_detector import MarketStyleDetector

@scheduler.scheduled_job('cron', hour=15, minute=30)
def update_market_style():
    """每日收盘后 30 分钟更新市场风格"""
    detector = MarketStyleDetector()
    style_data = detector.detect()
    detector.save_to_db(style_data)
    logger.info(f"市场风格更新: {style_data['style']}, 置信度: {style_data['confidence']}")
```

---

## 七、错误处理和边界情况

### 7.1 数据不足处理

**场景**：股票池数据不完整（新上市股票、停牌股票）

**策略**：
- 最少需要 200 只股票有完整 20 日数据才执行检测
- 不足时返回 `style: 'unknown'`，权重调整回退到 1.0
- 记录警告日志但不中断服务

### 7.2 风格置信度过低

**场景**：四种风格得分接近，无明显主导风格

**策略**：
- 置信度 < 0.4 时标记为 `mixed_market`
- 权重调整减半（如原本 +30% 变为 +15%）
- Agent 收到提示："当前市场风格不明确，建议谨慎操作"

### 7.3 历史数据缺失

**场景**：新策略无历史表现数据

**策略**：
- 自动回退到静态权重模式
- 响应中标记 `mode: 'static'` 和 `reason: '样本不足'`
- 每次交易后更新样本计数，达到阈值自动切换

### 7.4 数据库连接失败

**场景**：无法读取 `market_style_state` 或 `strategy_weight_config`

**策略**：
- 使用内存缓存的上一次结果（最多缓存 3 天）
- 超过 3 天则返回默认风格 `'neutral'`，权重 1.0
- 触发告警通知运维

### 7.5 计算超时

**场景**：400 只股票 × 20 天数据计算超过 10 秒

**策略**：
- 设置 10 秒超时限制
- 超时则使用昨日风格结果
- 异步重试计算，成功后更新缓存

---

## 八、测试策略

### 8.1 单元测试

**MarketStyleDetector 测试**：
- 测试动量市识别：构造 RSI > 55、MACD 金叉 > 60% 的数据
- 测试震荡市识别：构造 RSI 45-55、价格围绕 MA20 波动的数据
- 测试边界情况：空数据、单只股票、全部停牌
- 测试置信度计算：验证得分归一化逻辑

**StrategyWeightAdjuster 测试**：
- 测试静态权重查询：验证预定义矩阵正确返回
- 测试动态权重计算：mock `strategy_performance` 数据
- 测试模式切换：样本 29 → 30 时验证切换
- 测试平滑过渡：验证 70/30 混合权重计算

### 8.2 集成测试

**端到端流程**：
```python
# 1. 准备测试数据（400 只股票 × 20 天）
setup_test_kline_data()

# 2. 执行风格检测
response = client.get('/api/market/style')
assert response['data']['style'] in ['momentum', 'oscillation', 'low_volatility', 'value']

# 3. 查询策略权重
response = client.get('/api/strategies/my_strategy/weight?market_style=momentum')
assert 0.6 <= response['data']['weight_adjustment'] <= 2.0

# 4. 验证定时任务
trigger_scheduler_job('update_market_style')
assert db.query('SELECT * FROM market_style_state WHERE trade_date = today()').count() == 1
```

### 8.3 性能测试

**目标**：
- 风格检测计算时间 < 5 秒（400 只股票）
- API 响应时间 < 200ms
- 数据库查询 < 50ms

**压力测试**：
- 并发 50 个请求 `/api/market/style`
- 验证缓存机制有效（第二次请求 < 10ms）

---

## 九、实施计划

### 9.1 分步实施（总计约 3 小时）

**Step 1: 数据模型和仓储层（30 分钟）**
- 创建 `market_style_state` 表
- 创建 `strategy_weight_config` 表并插入初始静态权重数据
- ALTER `strategy_performance` 表添加 `market_style` 字段
- 实现 `MarketStyleRepository` 和 `StrategyWeightRepository`

**Step 2: MarketStyleDetector 服务（1 小时）**
- 实现风格检测算法（4 种风格得分计算）
- 实现置信度计算和主导风格选择
- 添加数据不足、置信度过低等边界处理
- 单元测试覆盖

**Step 3: StrategyWeightAdjuster 服务（45 分钟）**
- 实现静态权重查询
- 实现动态权重计算（从 `strategy_performance` 统计）
- 实现模式切换逻辑（样本阈值 30）
- 实现 70/30 平滑过渡

**Step 4: API 端点和集成（30 分钟）**
- 实现 `GET /api/market/style`
- 实现 `GET /api/strategies/{name}/weight`
- 添加定时任务（每日 15:30 更新）
- 修改 TypeScript Agent 的 `strategy_execute` 工具输出

**Step 5: 测试和文档（15 分钟）**
- 端到端测试
- 性能验证
- 更新 API 文档

### 9.2 依赖检查

**已就绪**：
- ✅ `StockPoolService`（股票池管理）
- ✅ `KlineRepository`（K 线数据查询）
- ✅ `StrategyPerformanceRepository`（策略表现统计，P2 完成）
- ✅ `runtime/scheduler/`（定时任务框架）

**需要确认**：
- `strategy_performance` 表是否已在生产环境创建？（P2 完成时应该已创建）

### 9.3 验收标准

**功能验收**：
- [ ] 每日自动更新市场风格，数据写入 `market_style_state` 表
- [ ] API 返回当前市场风格和置信度
- [ ] 策略权重根据市场风格正确调整（±40% 范围内）
- [ ] 样本 ≥ 30 的策略自动切换到动态权重模式
- [ ] Agent 调用 `strategy_execute` 时输出包含风格建议

**性能验收**：
- [ ] 风格检测计算时间 < 5 秒
- [ ] API 响应时间 < 200ms
- [ ] 缓存命中率 > 95%（同一天重复查询）

---

## 十、未来扩展

### 10.1 升级到学术因子模型

当前使用技术指标聚合，未来可升级到：
- **Fama-French 三因子**：市场、规模、价值
- **Barra 风格因子**：动量、价值、规模、波动率、流动性、成长

**接口预留**：
```python
class MarketStyleDetector:
    def __init__(self, factor_model='technical'):
        # factor_model: 'technical', 'fama_french', 'barra'
        self.factor_model = factor_model
```

### 10.2 实时风格检测

当前每日更新，未来可支持：
- 盘中每分钟更新（高频策略需求）
- WebSocket 推送风格变化事件

### 10.3 多市场支持

当前仅支持 A 股，未来可扩展：
- 港股市场风格检测
- 跨市场风格对比

---

## 十一、参考资料

- 策略循环闭合计划：`docs/plans/strategy-loop-closure-plan.md`
- P2 知识积累完成文档：`docs/superpowers/specs/2026-05-29-strategy-loop-p2-completion.md`
- 策略熔断器实现：`quantsys-v2/services/strategy_circuit_breaker.py`
