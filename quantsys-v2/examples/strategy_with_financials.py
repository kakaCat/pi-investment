"""
示例策略：基本面 + 技术面共振

使用财务指标过滤优质股票，结合技术指标生成交易信号。

注意：所有财务指标和技术指标都已自动注入到 df 中，可以直接使用。
"""

# 策略代码（indicator 类型）
STRATEGY_CODE = """
# 1. 基本面过滤：优质股票
df['quality_stock'] = (
    (df['roe_y'] >= 15) &              # 年度ROE >= 15%
    (df['debt_ratio_y'] < 60) &        # 负债率 < 60%
    (df['gross_margin_q'] > 30) &      # 季度毛利率 > 30%
    (df['ocf_to_profit_q'] > 0.8) &    # 现金流质量好
    (df['current_ratio_q'] > 1.2)      # 流动比率健康
)

# 2. 技术面信号
# 注意：rsi, macd, macd_signal 等技术指标已自动注入，可直接使用
df['oversold'] = df['rsi'] < 30
df['macd_golden'] = (df['macd'] > df['macd_signal']) & (df['macd'].shift(1) <= df['macd_signal'].shift(1))
df['ma_cross'] = (df['ma5'] > df['ma20']) & (df['ma5'].shift(1) <= df['ma20'].shift(1))

# 3. 买入信号：基本面 + 技术面共振
df['buy'] = df['quality_stock'] & (df['oversold'] | df['macd_golden'] | df['ma_cross'])

# 4. 卖出信号：技术面超买
df['sell'] = df['rsi'] > 70
"""

# 使用说明
"""
## 可用的指标列

### 财务指标（18个）
季度指标（_q 后缀）：
- roe_q, gross_margin_q, net_profit_margin_q, debt_ratio_q
- revenue_growth_q, ocf_to_profit_q, current_ratio_q, roa_q, operating_margin_q

年度指标（_y 后缀）：
- roe_y, gross_margin_y, net_profit_margin_y, debt_ratio_y
- revenue_growth_y, ocf_to_profit_y, current_ratio_y, roa_y, operating_margin_y

### 技术指标（11个）
趋势指标：
- rsi (14周期)
- macd, macd_signal, macd_hist

波动率指标：
- bollinger_upper, bollinger_middle, bollinger_lower (20周期, 2σ)

移动平均线：
- ma5, ma10, ma20, ma60

### 资金流指标（6个）
- main_net_inflow, main_net_pct
- super_large_net, super_large_pct
- large_net, large_pct

## API 使用示例

1. 创建策略：
   POST /api/strategies/user
   {
       "name": "基本面+技术面共振策略",
       "code": "<STRATEGY_CODE>",
       "code_type": "indicator",
       "description": "优质股票 + 技术面超卖时买入"
   }

2. 回测策略：
   POST /api/strategies/{strategy_id}/backtest
   {
       "symbol": "600000",
       "start_date": "2025-01-01",
       "end_date": "2026-05-27",
       "initial_cash": 100000
   }

3. 实时运行策略：
   POST /api/strategies/{strategy_id}/run
   {
       "symbol": "600000",
       "limit": 100
   }

4. 查看结果：
   - 策略会自动使用所有注入的指标列
   - 回测结果包含收益率、夏普比率、最大回撤等
   - 实时运行返回最新信号和指标值
"""
