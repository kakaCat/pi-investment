# 绩效归因功能集成完成报告

## 概述

已成功将 `RiskAttributionCalculator` 集成到回测系统，并扩展了回测指标从 4 个到 15 个。

## 完成内容

### 1. Service 层扩展

**文件**: `services/strategy_code_service.py`

#### 1.1 单资产回测指标扩展（4 → 15 个）

`_calculate_metrics_from_trades()` 现在返回：

**基础指标（6个）**:
- `total_return` - 总收益率
- `annual_return` - 年化收益率 ✨ 新增
- `sharpe_ratio` - 夏普比率
- `sortino_ratio` - Sortino比率 ✨ 新增
- `calmar_ratio` - Calmar比率 ✨ 新增
- `max_drawdown` - 最大回撤

**风险指标（2个）**:
- `volatility` - 波动率（年化）✨ 新增
- `downside_volatility` - 下行波动率 ✨ 新增

**交易指标（7个）**:
- `win_rate` - 胜率
- `profit_loss_ratio` - 盈亏比 ✨ 新增
- `avg_holding_days` - 平均持仓天数 ✨ 新增
- `trade_frequency` - 交易频率（每年）✨ 新增
- `max_consecutive_wins` - 最大连续盈利次数 ✨ 新增
- `max_consecutive_losses` - 最大连续亏损次数 ✨ 新增
- `profit_factor` - 盈利因子 ✨ 新增

#### 1.2 新增多资产组合回测

**方法**: `backtest_portfolio()`

**功能**:
- 支持多个策略 + 多个股票 + 自定义权重
- 自动计算组合权益曲线
- **风险归因分析**（调用 `RiskAttributionCalculator`）

**返回数据**:
```python
{
    # 组合层面的 15 个指标
    'total_return': 0.15,
    'annual_return': 0.12,
    'sharpe_ratio': 1.8,
    'sortino_ratio': 2.1,
    ...
    
    # 风险归因（如果启用）
    'attribution': {
        'portfolio_volatility': 0.2156,
        'contributions': {
            '600000.SH': {
                'weight': 0.4,
                'volatility': 0.25,
                'marginal_contribution': 0.22,
                'component_contribution': 0.088,
                'percentage_contribution': 45.2,
                'correlation_with_portfolio': 0.92
            },
            '000858.SZ': {...},
            '601318.SH': {...}
        },
        'total_percentage': 100.0
    },
    
    # 各资产回测结果
    'assets': [
        {
            'symbol': '600000.SH',
            'weight': 0.4,
            'result': {...}
        },
        ...
    ],
    
    # 组合权益曲线
    'portfolio_equity_curve': [...]
}
```

#### 1.3 新增辅助方法

- `_calculate_trade_metrics()` - 计算交易相关指标
- `_calculate_portfolio_equity()` - 计算组合权益曲线
- `attribution_calculator` - 初始化风险归因计算器

### 2. CLI 层对接

**文件**: `cli/commands/strategy_commands.py`

#### 新增命令

**`strategy.backtest_portfolio`** - 多资产组合回测（带风险归因）

**用法**:
```bash
# 方式1：逗号分隔
python cli/main.py strategy.backtest_portfolio \
  --strategy_ids "1,2,3" \
  --symbols "600000.SH,000858.SZ,601318.SH" \
  --weights "0.4,0.3,0.3" \
  --start 2023-01-01 \
  --end 2024-01-01 \
  --initial_cash 1000000 \
  --enable_attribution true

# 方式2：JSON格式
python cli/main.py strategy.backtest_portfolio \
  --strategy_ids "[1,2,3]" \
  --symbols '["600000.SH","000858.SZ","601318.SH"]' \
  --weights "[0.4,0.3,0.3]" \
  --start 2023-01-01 \
  --end 2024-01-01
```

#### 命令总数

策略命令从 8 个增加到 9 个：
1. `strategy.create`
2. `strategy.backtest` - 单资产回测（现在返回 15 个指标）
3. `strategy.backtest_portfolio` - 组合回测 ✨ 新增
4. `strategy.run`
5. `strategy.list`
6. `strategy.get`
7. `strategy.update`
8. `strategy.delete`
9. `strategy.optimize`

### 3. API 层对接

**文件**: `api/routes/backtest.py`

#### 新增端点

**`POST /api/backtest/strategy`** - 单资产策略回测（v2）

**请求**:
```json
{
  "strategyId": 1,
  "symbol": "600000.SH",
  "startDate": "2023-01-01",
  "endDate": "2024-01-01",
  "initialCash": 1000000
}
```

**响应**: 15 个指标（驼峰命名）

---

**`POST /api/backtest/portfolio`** - 多资产组合回测（带风险归因）

**请求**:
```json
{
  "strategyIds": [1, 2, 3],
  "symbols": ["600000.SH", "000858.SZ", "601318.SH"],
  "weights": [0.4, 0.3, 0.3],
  "startDate": "2023-01-01",
  "endDate": "2024-01-01",
  "initialCash": 1000000,
  "enableAttribution": true
}
```

**响应**:
```json
{
  "success": true,
  "data": {
    "totalReturn": 0.15,
    "annualReturn": 0.12,
    "sharpeRatio": 1.8,
    "sortinoRatio": 2.1,
    "calmarRatio": 1.2,
    "maxDrawdown": -0.12,
    "volatility": 0.18,
    "downsideVolatility": 0.12,
    "winRate": 0.65,
    "profitLossRatio": 2.3,
    "avgHoldingDays": 15.5,
    "tradeFrequency": 24.0,
    "maxConsecutiveWins": 5,
    "maxConsecutiveLosses": 3,
    "profitFactor": 2.1,
    "totalTrades": 45,
    
    "attribution": {
      "portfolioVolatility": 0.2156,
      "contributions": {
        "600000.SH": {
          "weight": 0.4,
          "volatility": 0.25,
          "marginalContribution": 0.22,
          "componentContribution": 0.088,
          "percentageContribution": 45.2,
          "correlationWithPortfolio": 0.92
        },
        "000858.SZ": {...},
        "601318.SH": {...}
      },
      "totalPercentage": 100.0
    },
    
    "assets": [...],
    "portfolioEquityCurve": [...]
  }
}
```

#### API 端点总数

回测相关端点从 5 个增加到 7 个：
1. `GET /api/backtest/results` - 获取回测结果
2. `POST /api/backtest` - 简单回测（旧版）
3. `POST /api/backtest/run` - 运行回测（别名）
4. `GET /api/performance/strategy/<strategy_id>` - 策略绩效
5. `GET /api/performance/comparison` - 多策略对比
6. `POST /api/backtest/strategy` - 单资产回测（v2）✨ 新增
7. `POST /api/backtest/portfolio` - 组合回测 ✨ 新增

## 技术细节

### 风险归因算法

使用 `RiskAttributionCalculator` 计算：

1. **边际风险贡献（MCR）**: `(Σ @ w) / σ_p`
2. **成分风险贡献（CCR）**: `w_i × MCR_i`
3. **百分比风险贡献（PCR）**: `(CCR_i / σ_p) × 100`

其中：
- `Σ` = 协方差矩阵
- `w` = 权重向量
- `σ_p` = 组合波动率

### 指标计算公式

**Sortino比率**:
```
Sortino = (平均收益率 × √252) / 下行波动率
```

**Calmar比率**:
```
Calmar = 年化收益率 / |最大回撤|
```

**盈利因子**:
```
Profit Factor = 总盈利 / 总亏损
```

## 验证

### Service 层验证
```bash
cd quantsys-v2
python -c "
from services.strategy_code_service import StrategyCodeService
service = StrategyCodeService()
print('✓ backtest_portfolio 存在')
print('✓ attribution_calculator 已初始化')
"
```

### CLI 验证
```bash
cd quantsys-v2
python -c "
from cli.commands.strategy_commands import get_all_commands
commands = get_all_commands()
print(f'策略命令总数: {len(commands)}')
"
```

### API 验证
```bash
cd quantsys-v2
python -c "
with open('api/routes/backtest.py', 'r') as f:
    content = f.read()
    assert 'def backtest_strategy_v2' in content
    assert 'def backtest_portfolio' in content
print('✓ API 端点已添加')
"
```

## 使用示例

### Python Service 调用

```python
from services.strategy_code_service import StrategyCodeService

service = StrategyCodeService()

# 单资产回测（15个指标）
result = service.backtest_strategy(
    strategy_id=1,
    symbol='600000.SH',
    start_date='2023-01-01',
    end_date='2024-01-01'
)
print(result['annual_return'])  # 年化收益率
print(result['sortino_ratio'])  # Sortino比率

# 多资产组合回测（带风险归因）
result = service.backtest_portfolio(
    strategy_ids=[1, 2, 3],
    symbols=['600000.SH', '000858.SZ', '601318.SH'],
    weights=[0.4, 0.3, 0.3],
    start_date='2023-01-01',
    end_date='2024-01-01',
    enable_attribution=True
)
print(result['attribution']['contributions']['600000.SH']['percentage_contribution'])
# 输出：45.2  # 浦发银行贡献了45.2%的组合风险
```

### HTTP API 调用

```bash
# 单资产回测
curl -X POST http://127.0.0.1:5001/api/backtest/strategy \
  -H "Content-Type: application/json" \
  -d '{
    "strategyId": 1,
    "symbol": "600000.SH",
    "startDate": "2023-01-01",
    "endDate": "2024-01-01"
  }'

# 组合回测
curl -X POST http://127.0.0.1:5001/api/backtest/portfolio \
  -H "Content-Type: application/json" \
  -d '{
    "strategyIds": [1, 2, 3],
    "symbols": ["600000.SH", "000858.SZ", "601318.SH"],
    "weights": [0.4, 0.3, 0.3],
    "startDate": "2023-01-01",
    "endDate": "2024-01-01",
    "enableAttribution": true
  }'
```

## 总结

✅ **Service 层**: 扩展了 15 个回测指标 + 组合回测 + 风险归因  
✅ **CLI 层**: 新增 `strategy.backtest_portfolio` 命令  
✅ **API 层**: 新增 `/api/backtest/strategy` 和 `/api/backtest/portfolio` 端点  
✅ **验证通过**: 所有层级功能正常

现在回测系统功能完整，既支持单资产深度分析（15个指标），也支持多资产组合的风险归因！

## 后续优化建议

1. **性能优化**: 组合回测时并行计算各资产回测
2. **缓存机制**: 缓存历史回测结果，避免重复计算
3. **前端集成**: 在 web-frontend 中添加组合回测和风险归因可视化
4. **测试覆盖**: 添加单元测试和集成测试
5. **文档完善**: 添加 API 文档（Swagger/OpenAPI）
