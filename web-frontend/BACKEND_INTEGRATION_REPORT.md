# Web-Frontend 后端集成检查报告

**检查日期**: 2026-05-24  
**检查范围**: 回测中心、快速交易页面及所有页面的后端API对接情况

---

## 一、回测中心 (BacktestCenter) 检查

### 1.1 前端实现分析

**文件**: `src/views/BacktestCenter/index.vue`

**功能模块**:
- ✅ 回测配置表单（策略选择、股票代码、时间范围、初始资金、手续费、滑点）
- ✅ 策略参数配置（MA双均线、RSI、MACD等）
- ✅ 快速交易面板（买入/卖出、市价/限价）
- ✅ 回测结果展示（关键指标、净值曲线、交易记录、月度收益）
- ✅ 策略保存功能
- ✅ 报告导出功能

**API调用**:
```typescript
// 回测执行
analysisApi.runBacktest({
  strategy, symbol, startDate, endDate, 
  initialCapital, commission, slippage, parameters
})

// 股票搜索
stockApi.searchStocks(queryString)

// 快速交易
tradingApi.createOrder({
  symbol, type, priceType, price, quantity
})

// 保存策略
strategyApi.createStrategy({
  name, description, type, code, parameters, riskLevel
})
```

### 1.2 后端实现分析

**文件**: `quantsys-v2/api/server.py`

#### 回测端点 `/api/backtest` (POST)
- ✅ **实现状态**: 已实现
- ✅ **必需参数**: strategy_name, symbol, start_date, end_date, initial_capital
- ✅ **支持参数**: strategy_id (作为 strategy_name 的替代)
- ⚠️ **业务逻辑**: 使用简化的MA交叉策略回测

**实现细节**:
```python
def save_simple_backtest(params, klines, initial_capital):
    # 简单的移动平均交叉回测
    short_window = int(params.get('ma_short', 5))
    long_window = int(params.get('ma_long', 20))
    # 买入信号: short_ma > long_ma
    # 卖出信号: short_ma < long_ma
```

**返回数据**:
```python
{
  'strategy_name': str,
  'symbol': str,
  'start_date': str,
  'end_date': str,
  'initial_capital': float,
  'final_capital': float,
  'total_return': float,
  'total_trades': int,
  'trades': [...]
}
```

### 1.3 问题与建议

#### ❌ 问题1: 前后端参数不匹配
**前端发送**:
```typescript
{
  strategy: 'ma_cross',  // 前端字段名
  parameters: {
    fastPeriod: 5,       // 驼峰命名
    slowPeriod: 20,
    rsiPeriod: 14
  }
}
```

**后端期望**:
```python
{
  'strategy_name': 'ma_cross',  // 后端字段名
  'ma_short': 5,                 // 下划线命名
  'ma_long': 20
}
```

**影响**: 前端传递的 `parameters.fastPeriod` 和 `parameters.slowPeriod` 不会被后端识别，后端会使用默认值 (5, 20)。

**建议**: 
1. 前端适配器层转换参数名称
2. 或后端支持 camelCase 参数解析

#### ❌ 问题2: 回测结果字段缺失
**前端期望的字段**:
```typescript
{
  finalCapital, totalReturn, annualReturn, maxDrawdown,
  sharpeRatio, winRate, profitLossRatio, totalTrades,
  winTrades, lossTrades, avgProfit, avgLoss,
  maxProfit, maxLoss, recoveryDays,
  equityCurve: [{date, value}],
  monthlyReturns: [{year, months}],
  trades: [{date, type, price, quantity, amount, commission, profit, balance}]
}
```

**后端实际返回**:
```python
{
  'strategy_name', 'symbol', 'start_date', 'end_date',
  'initial_capital', 'final_capital', 'total_return',
  'total_trades', 'trades'
}
```

**缺失字段**:
- ❌ annualReturn (年化收益)
- ❌ maxDrawdown (最大回撤)
- ❌ sharpeRatio (夏普比率)
- ❌ winRate (胜率)
- ❌ profitLossRatio (盈亏比)
- ❌ winTrades, lossTrades (盈利/亏损次数)
- ❌ avgProfit, avgLoss (平均盈利/亏损)
- ❌ maxProfit, maxLoss (最大单笔盈亏)
- ❌ recoveryDays (回撤恢复天数)
- ❌ equityCurve (净值曲线数据)
- ❌ monthlyReturns (月度收益数据)
- ❌ trades 字段不完整 (缺少 commission, profit, balance)

**影响**: 前端页面无法正确显示关键指标、净值曲线图、月度收益热力图。

**建议**: 后端补充完整的回测指标计算逻辑。

#### ⚠️ 问题3: 策略类型支持不完整
**前端支持的策略**:
- ma_cross (MA双均线)
- rsi_reversal (RSI反转)
- macd_golden (MACD金叉)
- boll_breakout (布林带突破)
- kdj_overbought (KDJ超买超卖)

**后端实现**: 仅实现了 MA 双均线策略

**建议**: 补充其他策略的回测逻辑，或前端暂时只开放已实现的策略。

---

## 二、快速交易 (Quick Trade) 检查

### 2.1 前端实现

**位置**: `BacktestCenter/index.vue` 第122-170行

**功能**:
- ✅ 股票代码输入（带自动完成）
- ✅ 交易方向选择（买入/卖出）
- ✅ 价格类型选择（市价/限价）
- ✅ 价格和数量输入
- ✅ 确认对话框

**API调用**:
```typescript
tradingApi.createOrder({
  symbol: tradeForm.symbol,
  type: tradeForm.direction,        // 'buy' | 'sell'
  priceType: tradeForm.priceType,   // 'market' | 'limit'
  price: tradeForm.price,
  quantity: tradeForm.quantity
})
```

### 2.2 后端实现

**端点**: `/api/orders/create` (POST)  
**文件**: `quantsys-v2/api/server.py:2992-3025`

**实现状态**: ✅ 已实现

**参数映射**:
```python
# 前端 tradingApi.createOrder 发送:
{
  symbol, type, priceType, price, quantity
}

# 后端 create_order 接收:
{
  symbol: data.symbol,
  action: data.type,           # 映射: type -> action
  order_type: data.priceType,  # 映射: priceType -> order_type
  quantity: data.quantity,
  price: data.price
}
```

**业务逻辑**:
```python
order_id = order_service.create_order(
    ds, symbol, action, order_type, quantity, price, reason, signal_id
)
order = ds.portfolio.get_order_by_id(order_id)
return api_response({'order_id': order_id, 'order': order})
```

### 2.3 问题与建议

#### ⚠️ 问题4: 参数映射不一致
**前端发送**: `type: 'buy'`  
**后端期望**: `action: 'buy'`

**前端发送**: `priceType: 'market'`  
**后端期望**: `order_type: 'market'`

**当前状态**: 后端通过 `convert_keys_to_snake` 转换驼峰命名，但字段名不匹配。

**实际情况检查**:
```typescript
// src/services/api/trading.ts:29-37
createOrder(data: CreateOrderRequest) {
  return apiClient.post<Order>('/api/orders/create', {
    symbol: data.symbol,
    action: data.type,           // ✅ 已手动映射
    orderType: data.priceType,   // ✅ 已手动映射
    quantity: data.quantity,
    price: data.price,
    stopPrice: data.stopLoss
  })
}
```

**结论**: ✅ 前端已在 API 层做了字段映射，参数对接正确。

#### ✅ 问题5: 订单服务依赖
后端依赖 `order_service.create_order` 和 `ds.portfolio.get_order_by_id`。

**需要确认**: 这些服务是否已完整实现。

---

## 三、所有页面后端集成检查

### 3.1 页面清单与API使用情况

| 页面 | 文件 | 主要API调用 | 集成状态 |
|------|------|------------|---------|
| 回测中心 | BacktestCenter/index.vue | analysisApi.runBacktest, tradingApi.createOrder, strategyApi.createStrategy | ⚠️ 部分 |
| 每日报告 | DailyReport/index.vue | 需检查 | 🔍 待查 |
| 仪表盘 | Dashboard/index.vue | 需检查 | 🔍 待查 |
| 数据更新 | DataUpdate/index.vue | 需检查 | 🔍 待查 |
| 执行记录 | Executions/index.vue | tradingApi.getExecutions | 🔍 待查 |
| 因子分析 | FactorAnalysis/index.vue | analysisApi.getFactorAnalysis | 🔍 待查 |
| 指标IDE | IndicatorIDE/index.vue | 需检查 | 🔍 待查 |
| ML引擎 | MLEngine/index.vue | 需检查 | 🔍 待查 |
| 机会雷达 | OpportunityRadar/index.vue | analysisApi.scanOpportunities | 🔍 待查 |
| 订单管理 | Orders/index.vue | tradingApi.getOrders | ✅ 已对接 |
| 投资组合 | Portfolio/index.vue | tradingApi.getPortfolioSummary | ✅ 已对接 |
| 量化流水线 | QuantPipeline/index.vue | 需检查 | 🔍 待查 |
| 风险检查 | RiskCheck/index.vue | 需检查 | 🔍 待查 |
| 调度器 | Scheduler/index.vue | 需检查 | 🔍 待查 |
| 信号列表 | SignalList/index.vue | 需检查 | 🔍 待查 |
| 股票详情 | StockDetail/index.vue | stockApi.getStockDetail | ✅ 已对接 |
| 股票列表 | StockList/index.vue | stockApi.getStocks | ✅ 已对接 |
| 策略中心 | StrategyCenter/index.vue | strategyApi.getStrategies | ✅ 已对接 |
| 策略配置 | StrategyConfig/index.vue | strategyApi.createStrategy | ✅ 已对接 |
| 交易记录 | Trades/index.vue | tradingApi.getTrades | ✅ 已对接 |

### 3.2 后端端点覆盖情况

#### ✅ 已实现的端点

**股票相关**:
- GET `/api/stocks/search` - 股票搜索
- GET `/api/stocks/list` - 股票列表（带分页）
- POST `/api/stocks/resolve` - 股票代码解析
- GET `/api/stock/<symbol>/klines` - K线数据
- GET `/api/stocks/<symbol>` - 股票详情
- GET `/api/stock/<symbol>/factors` - 因子分析
- GET `/api/stock/<symbol>/technical` - 技术分析

**信号相关**:
- GET `/api/signals` - 信号列表（带分页、筛选）
- POST `/api/signals/scan` - 机会扫描
- GET `/api/signals/detail/<signal_id>` - 信号详情
- POST `/api/signals/approve/<signal_id>` - 批准信号
- POST `/api/signals/reject/<signal_id>` - 拒绝信号

**订单相关**:
- GET `/api/orders/list` - 订单列表
- GET `/api/orders/detail/<order_id>` - 订单详情
- POST `/api/orders/create` - 创建订单 ✅
- POST `/api/orders/cancel/<order_id>` - 取消订单
- POST `/api/orders/update/<order_id>` - 修改订单

**交易相关**:
- GET `/api/trades/list` - 交易历史（带分页）

**投资组合相关**:
- GET `/api/portfolio/positions` - 持仓列表
- GET `/api/portfolio/holdings` - 持仓明细
- GET `/api/portfolio/summary` - 投资组合汇总
- GET `/api/portfolio/allocation` - 持仓分布
- GET `/api/portfolio/equity-curve` - 资产曲线

**策略相关**:
- GET `/api/strategies/list` - 策略列表（带分页）
- GET `/api/strategies/detail/<strategy_id>` - 策略详情
- POST `/api/strategies/create` - 创建策略 ✅
- POST `/api/strategies/update/<strategy_id>` - 更新策略
- POST `/api/strategies/delete/<strategy_id>` - 删除策略
- POST `/api/strategies/start/<strategy_id>` - 启动策略
- POST `/api/strategies/stop/<strategy_id>` - 停止策略

**回测相关**:
- POST `/api/backtest` - 运行回测 ⚠️
- GET `/api/backtest/results` - 获取回测结果

**执行记录相关**:
- GET `/api/executions` - 执行记录列表
- GET `/api/executions/<execution_id>` - 执行记录详情
- GET `/api/executions/stats` - 执行统计
- PUT `/api/executions/<execution_id>/cancel` - 取消执行
- PUT `/api/executions/<execution_id>/close` - 平仓执行

#### ❌ 未实现的端点

**分析相关** (标记为 TODO):
- GET `/api/analysis/fundamental/<symbol>` - 基本面分析
- GET `/api/analysis/sentiment/<symbol>` - 情绪分析
- POST `/api/analysis/correlation` - 相关性分析
- GET `/api/analysis/industry/<industry>` - 行业分析

---

## 四、后端业务逻辑检查

### 4.1 回测业务逻辑

**当前实现**: 简化的MA双均线策略

**问题**:
1. ❌ 未计算年化收益率
2. ❌ 未计算最大回撤
3. ❌ 未计算夏普比率
4. ❌ 未计算胜率和盈亏比
5. ❌ 未生成净值曲线数据
6. ❌ 未生成月度收益数据
7. ❌ 交易记录缺少手续费、盈亏、余额字段

**建议**: 参考标准回测框架（如 backtrader、zipline）补充完整的性能指标计算。

### 4.2 订单创建业务逻辑

**实现**: 调用 `order_service.create_order`

**需要验证**:
1. ✅ 订单参数验证（symbol, action, order_type, quantity）
2. 🔍 价格验证（市价单是否需要价格？）
3. 🔍 数量验证（是否符合交易规则，如100股整数倍？）
4. 🔍 资金检查（是否有足够资金？）
5. 🔍 持仓检查（卖出时是否有足够持仓？）
6. 🔍 风险检查（是否触发风控规则？）

**建议**: 补充完整的订单前置检查逻辑。

### 4.3 API响应格式

**后端统一格式**:
```python
{
  'success': bool,
  'data': {...},      # 自动转换为驼峰命名
  'message': str      # 可选
}
```

**前端解析**:
```typescript
// client.ts:74-82
if (data && typeof data === 'object' && 'success' in data && 'data' in data) {
  return (data as any).data  // 直接返回 data 字段
}
```

**结论**: ✅ 前后端响应格式对接正确。

---

## 五、总结与建议

### 5.1 关键问题汇总

| 问题 | 严重程度 | 影响范围 | 建议优先级 |
|------|---------|---------|-----------|
| 回测结果字段缺失 | 🔴 高 | 回测中心页面无法正常显示 | P0 |
| 回测策略类型不完整 | 🟡 中 | 用户只能使用MA策略 | P1 |
| 回测参数映射问题 | 🟡 中 | 策略参数无法自定义 | P1 |
| 订单业务逻辑不完整 | 🟡 中 | 可能产生无效订单 | P1 |
| 分析端点未实现 | 🟢 低 | 部分高级功能不可用 | P2 |

### 5.2 修复建议

#### 优先级 P0: 回测结果完整性

**文件**: `quantsys-v2/api/server.py`

**需要补充的计算**:
```python
def calculate_backtest_metrics(trades, klines, initial_capital):
    """计算完整的回测指标"""
    # 1. 年化收益率
    days = (end_date - start_date).days
    annual_return = (total_return + 1) ** (365 / days) - 1
    
    # 2. 最大回撤
    equity_curve = calculate_equity_curve(trades, klines, initial_capital)
    max_drawdown = calculate_max_drawdown(equity_curve)
    
    # 3. 夏普比率
    returns = calculate_daily_returns(equity_curve)
    sharpe_ratio = (returns.mean() / returns.std()) * sqrt(252)
    
    # 4. 胜率和盈亏比
    winning_trades = [t for t in trades if t['profit'] > 0]
    losing_trades = [t for t in trades if t['profit'] < 0]
    win_rate = len(winning_trades) / len(trades)
    avg_profit = mean([t['profit'] for t in winning_trades])
    avg_loss = mean([abs(t['profit']) for t in losing_trades])
    profit_loss_ratio = avg_profit / avg_loss
    
    # 5. 月度收益
    monthly_returns = calculate_monthly_returns(equity_curve)
    
    return {
        'annualReturn': annual_return,
        'maxDrawdown': max_drawdown,
        'sharpeRatio': sharpe_ratio,
        'winRate': win_rate,
        'profitLossRatio': profit_loss_ratio,
        'equityCurve': equity_curve,
        'monthlyReturns': monthly_returns,
        ...
    }
```

#### 优先级 P1: 参数映射适配

**方案1**: 前端适配（推荐）

**文件**: `web-frontend/src/services/api/analysis.ts`

```typescript
runBacktest(data: BacktestRequest) {
  // 转换参数格式
  const params = {
    strategy_name: data.strategy,  // 映射字段名
    symbol: data.symbol,
    start_date: data.startDate,
    end_date: data.endDate,
    initial_capital: data.initialCapital,
    commission: data.commission,
    slippage: data.slippage,
    // 展开策略参数
    ma_short: data.parameters?.fastPeriod,
    ma_long: data.parameters?.slowPeriod,
    rsi_period: data.parameters?.rsiPeriod
  }
  return apiClient.post<BacktestResponse>('/api/backtest', params)
}
```

**方案2**: 后端适配

**文件**: `quantsys-v2/api/server.py`

```python
@app.route('/api/backtest', methods=['POST'])
def run_backtest():
    data = request.get_json() or {}
    params = convert_keys_to_snake(data)
    
    # 支持嵌套的 parameters 对象
    if 'parameters' in params:
        p = params['parameters']
        params['ma_short'] = p.get('fast_period', 5)
        params['ma_long'] = p.get('slow_period', 20)
        params['rsi_period'] = p.get('rsi_period', 14)
    
    # 支持 strategy 作为 strategy_name 的别名
    if 'strategy' in params and 'strategy_name' not in params:
        params['strategy_name'] = params['strategy']
    
    ...
```

#### 优先级 P1: 订单前置检查

**文件**: `quantsys-v2/services/order_service.py`

```python
def create_order(ds, symbol, action, order_type, quantity, price, reason, signal_id):
    # 1. 参数验证
    if action not in ['buy', 'sell']:
        raise ValueError(f'无效的交易方向: {action}')
    
    if order_type not in ['market', 'limit']:
        raise ValueError(f'无效的订单类型: {order_type}')
    
    if quantity <= 0 or quantity % 100 != 0:
        raise ValueError('数量必须是100的整数倍')
    
    # 2. 价格验证
    if order_type == 'limit' and not price:
        raise ValueError('限价单必须指定价格')
    
    # 3. 资金检查（买入）
    if action == 'buy':
        account = ds.portfolio.get_account_summary()
        required_cash = quantity * price * 1.0003  # 含手续费
        if account['available_cash'] < required_cash:
            raise ValueError(f'资金不足: 需要 {required_cash}, 可用 {account["available_cash"]}')
    
    # 4. 持仓检查（卖出）
    if action == 'sell':
        position = ds.portfolio.get_position(symbol)
        if not position or position['available_quantity'] < quantity:
            raise ValueError(f'持仓不足: 需要 {quantity}, 可用 {position.get("available_quantity", 0)}')
    
    # 5. 风险检查
    risk_result = ds.risk.check_order(symbol, action, quantity, price)
    if not risk_result['passed']:
        raise ValueError(f'风控拒绝: {risk_result["reason"]}')
    
    # 6. 创建订单
    order_id = ds.portfolio.insert_order(...)
    return order_id
```

### 5.3 测试建议

#### 单元测试
```python
# tests/test_backtest_api.py
def test_backtest_returns_complete_metrics():
    response = client.post('/api/backtest', json={
        'strategy_name': 'ma_cross',
        'symbol': '600519.SH',
        'start_date': '2023-01-01',
        'end_date': '2023-12-31',
        'initial_capital': 1000000
    })
    
    assert response.status_code == 200
    data = response.json()['data']
    
    # 验证必需字段
    assert 'finalCapital' in data
    assert 'totalReturn' in data
    assert 'annualReturn' in data
    assert 'maxDrawdown' in data
    assert 'sharpeRatio' in data
    assert 'winRate' in data
    assert 'equityCurve' in data
    assert 'monthlyReturns' in data
```

#### 集成测试
```typescript
// web-frontend/tests/integration/backtest.test.ts
describe('Backtest Integration', () => {
  it('should run backtest and display results', async () => {
    const result = await analysisApi.runBacktest({
      strategy: 'ma_cross',
      symbol: '600519.SH',
      startDate: '2023-01-01',
      endDate: '2023-12-31',
      initialCapital: 1000000,
      commission: 0.0003,
      slippage: 0.001,
      parameters: {
        fastPeriod: 5,
        slowPeriod: 20
      }
    })
    
    expect(result.finalCapital).toBeGreaterThan(0)
    expect(result.equityCurve).toHaveLength(greaterThan(0))
    expect(result.trades).toBeInstanceOf(Array)
  })
})
```

---

## 六、下一步行动

### 立即执行 (本周)
1. ✅ 补充回测指标计算逻辑
2. ✅ 修复参数映射问题
3. ✅ 添加订单前置检查

### 短期计划 (2周内)
1. 🔍 完成所有页面的后端集成检查
2. 🔍 补充缺失的分析端点
3. 🔍 编写集成测试用例

### 中期计划 (1个月内)
1. 📝 实现完整的回测策略库
2. 📝 优化回测性能（并行计算、缓存）
3. 📝 添加回测报告生成功能

---

**报告生成**: Claude Code  
**审核状态**: 待人工审核
