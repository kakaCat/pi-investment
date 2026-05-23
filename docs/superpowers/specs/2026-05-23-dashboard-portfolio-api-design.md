# Dashboard Portfolio API 设计文档

**日期**: 2026-05-23  
**作者**: Claude (Kiro)  
**状态**: 设计阶段  
**版本**: 1.0

## 1. 概述

### 1.1 背景

React Dashboard (`quant-web/src/components/dashboard/DashboardOverview.tsx`) 当前缺少投资组合相关的核心数据展示，包括：
- 投资组合总价值
- 持仓数量统计
- 净值走势图
- 持仓明细列表

虽然后端 quantsys-v2 已经具备完整的数据表结构（`portfolio_holdings`、`account_balance`、`trades` 等）和 Repository 层，但缺少对应的 API 端点。

### 1.2 目标

建立完整的投资组合数据管理体系，包括：
1. **数据计算引擎** - 自动计算投资组合指标
2. **定时任务系统** - 每日收盘后自动更新数据
3. **API 端点** - 提供 5 个生产可用的接口
4. **数据回填** - 补充历史数据（最近 90 天）
5. **前端集成** - React Dashboard 展示完整数据

### 1.3 方案选择

采用**方案 C：完整重构方案**，理由：
- 建立稳健的长期架构
- 预计算数据，性能最优
- 支持完整的历史回溯
- 数据一致性有保障

**预计工作量**: 15-20 小时（约 2 天）

---

## 2. 系统架构

### 2.1 整体架构图

```
┌─────────────────────────────────────────────────────────────┐
│                      定时任务调度器                          │
│                   (每日收盘后触发)                           │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│                   资产计算引擎                               │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │
│  │ 持仓数据     │  │ 最新价格     │  │ 交易记录     │     │
│  │ portfolio_   │  │ klines       │  │ trades       │     │
│  │ holdings     │  │              │  │              │     │
│  └──────────────┘  └──────────────┘  └──────────────┘     │
│                     │                                        │
│                     ▼                                        │
│         计算：总资产、盈亏、收益率、持仓统计                │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│                  写入数据表                                  │
│  ┌──────────────────────────────────────────────────────┐  │
│  │ account_balance (账户余额快照)                       │  │
│  │ - balance_date, total_assets, daily_return           │  │
│  │ - cash, market_value, position_count                 │  │
│  └──────────────────────────────────────────────────────┘  │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│                    API 端点                                  │
│  GET /api/portfolio/summary      (读取最新快照)             │
│  GET /api/portfolio/history      (读取历史快照)             │
│  GET /api/portfolio/holdings     (读取持仓快照)             │
│  GET /api/signals/today          (今日信号)                 │
│  GET /api/backtest/recent        (最近回测)                 │
└─────────────────────────────────────────────────────────────┘
```

### 2.2 核心组件

#### 2.2.1 资产计算引擎 (PortfolioCalculator)

**职责**:
- 计算投资组合总资产
- 计算持仓盈亏和收益率
- 统计持仓数量（总数、盈利数、亏损数）
- 计算现金余额
- 处理价格缺失等边界情况

**输入**:
- 持仓数据 (`portfolio_holdings`)
- 最新价格 (`klines`)
- 交易记录 (`trades`)
- 初始资金配置

**输出**:
- 账户余额快照数据（写入 `account_balance` 表）

#### 2.2.2 定时任务 (DailySnapshotJob)

**职责**:
- 每日收盘后自动触发
- 调用资产计算引擎
- 写入 `account_balance` 表
- 记录任务日志
- 错误通知

**执行时间**:
- A股市场: 15:30 (收盘后)
- 港股市场: 16:30 (收盘后)

#### 2.2.3 API 端点

**新增接口** (3个):
1. `GET /api/portfolio/summary` - 投资组合摘要
2. `GET /api/portfolio/history` - 历史净值走势
3. `GET /api/portfolio/holdings` - 持仓列表

**调整接口** (2个):
4. `GET /api/signals` - 添加日期过滤参数
5. `GET /api/backtest/results` - 添加 limit 参数

---

## 3. 数据库设计

### 3.1 现有表结构

#### 3.1.1 portfolio_holdings (持仓表)

已存在，无需修改。

```sql
CREATE TABLE quant.portfolio_holdings (
    id BIGSERIAL PRIMARY KEY,
    symbol TEXT NOT NULL,
    name TEXT NOT NULL,
    quantity INTEGER NOT NULL,
    avg_cost DOUBLE PRECISION NOT NULL,
    total_invested DOUBLE PRECISION NOT NULL,
    market TEXT NOT NULL,
    sector TEXT,
    added_date DATE NOT NULL,
    stop_loss DOUBLE PRECISION,
    target_price DOUBLE PRECISION,
    updated_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE(symbol)
);
```

#### 3.1.2 account_balance (账户余额表)

已存在，无需修改。

```sql
CREATE TABLE quant.account_balance (
    id BIGSERIAL PRIMARY KEY,
    balance_date DATE NOT NULL UNIQUE,
    cash DOUBLE PRECISION NOT NULL,
    market_value DOUBLE PRECISION NOT NULL,
    total_assets DOUBLE PRECISION NOT NULL,
    daily_pnl DOUBLE PRECISION,
    daily_return DOUBLE PRECISION,
    total_pnl DOUBLE PRECISION,
    total_return DOUBLE PRECISION,
    position_count INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_quant_account_balance_date_desc
    ON quant.account_balance(balance_date DESC);
```

### 3.2 索引优化

为提升查询性能，确保以下索引存在：

```sql
-- account_balance 表索引（已存在）
CREATE INDEX IF NOT EXISTS idx_quant_account_balance_date_desc
    ON quant.account_balance(balance_date DESC);

-- portfolio_holdings 表索引（已存在）
CREATE INDEX IF NOT EXISTS idx_quant_portfolio_holdings_market
    ON quant.portfolio_holdings(market);
CREATE INDEX IF NOT EXISTS idx_quant_portfolio_holdings_sector
    ON quant.portfolio_holdings(sector);
```

### 3.3 数据表关系

```
portfolio_holdings (持仓)
    ↓ (关联)
klines (K线价格)
    ↓ (计算)
account_balance (账户余额快照)
    ↓ (读取)
API 端点
```

---

## 4. API 接口设计

### 4.1 GET /api/portfolio/summary

**用途**: 获取投资组合核心指标摘要

**请求参数**: 无

**响应格式**:

```json
{
  "success": true,
  "data": {
    "totalValue": 1258400.00,
    "dailyChange": 29447.68,
    "dailyChangePercent": 2.34,
    "holdingsCount": 8,
    "profitCount": 6,
    "lossCount": 2,
    "availableCash": 50000.00,
    "totalCost": 1200000.00,
    "totalProfit": 58400.00,
    "totalProfitPercent": 4.87,
    "lastUpdated": "2026-05-23T15:30:00Z"
  }
}
```

**数据来源**:
1. 从 `account_balance` 表获取最新一条记录
2. 从 `portfolio_holdings` 表统计持仓数量
3. 关联 `klines` 表获取最新价格，计算盈利/亏损持仓数

**实现逻辑**:

```python
def get_portfolio_summary():
    # 1. 获取最新账户余额
    latest_balance = account_balance_repo.get_latest()
    
    # 2. 获取所有持仓
    holdings = portfolio_repo.get_all_holdings()
    
    # 3. 计算盈利/亏损持仓数
    profit_count = 0
    loss_count = 0
    for holding in holdings:
        current_price = kline_repo.get_latest_price(holding['symbol'])
        if current_price > holding['avg_cost']:
            profit_count += 1
        else:
            loss_count += 1
    
    # 4. 组装响应
    return {
        'totalValue': latest_balance['total_assets'],
        'dailyChange': latest_balance['daily_pnl'],
        'dailyChangePercent': latest_balance['daily_return'],
        'holdingsCount': len(holdings),
        'profitCount': profit_count,
        'lossCount': loss_count,
        'availableCash': latest_balance['cash'],
        # ... 其他字段
    }
```

**错误处理**:
- 如果 `account_balance` 表为空，返回 404 错误，提示需要先运行数据初始化
- 如果价格数据缺失，该持仓不计入盈利/亏损统计

---

### 4.2 GET /api/portfolio/history

**用途**: 获取投资组合历史净值数据（用于绘制走势图）

**请求参数**:
- `days` (可选): 查询天数，默认 30，可选值: 7, 30, 90

**示例请求**:
```
GET /api/portfolio/history?days=30
```

**响应格式**:

```json
{
  "success": true,
  "data": {
    "period": "30d",
    "startDate": "2026-04-23",
    "endDate": "2026-05-23",
    "history": [
      {
        "date": "2026-04-23",
        "totalAssets": 1200000.00,
        "dailyReturn": 0.0,
        "cash": 50000.00,
        "marketValue": 1150000.00
      },
      {
        "date": "2026-04-24",
        "totalAssets": 1205000.00,
        "dailyReturn": 0.42,
        "cash": 50000.00,
        "marketValue": 1155000.00
      },
      // ... 更多数据点
      {
        "date": "2026-05-23",
        "totalAssets": 1258400.00,
        "dailyReturn": 2.34,
        "cash": 50000.00,
        "marketValue": 1208400.00
      }
    ],
    "summary": {
      "totalReturn": 4.87,
      "maxDrawdown": -2.15,
      "volatility": 1.23
    }
  }
}
```

**数据来源**:
- 从 `account_balance` 表查询最近 N 天的记录

**实现逻辑**:

```python
def get_portfolio_history(days=30):
    # 1. 查询历史数据
    history = account_balance_repo.get_history(days)
    
    # 2. 计算汇总指标
    if len(history) > 0:
        first_value = history[0]['total_assets']
        last_value = history[-1]['total_assets']
        total_return = (last_value - first_value) / first_value * 100
        
        # 计算最大回撤
        max_drawdown = calculate_max_drawdown(history)
        
        # 计算波动率
        volatility = calculate_volatility(history)
    
    # 3. 组装响应
    return {
        'period': f'{days}d',
        'history': history,
        'summary': {
            'totalReturn': total_return,
            'maxDrawdown': max_drawdown,
            'volatility': volatility
        }
    }
```

**错误处理**:
- 如果 `account_balance` 表数据不足，返回现有数据并在响应中标注实际天数
- 如果表为空，返回空数组

---

### 4.3 GET /api/portfolio/holdings

**用途**: 获取当前持仓列表（含实时市值和盈亏）

**请求参数**: 无

**响应格式**:

```json
{
  "success": true,
  "data": {
    "holdings": [
      {
        "symbol": "600519.SH",
        "name": "贵州茅台",
        "quantity": 100,
        "avgCost": 1650.00,
        "currentPrice": 1680.00,
        "marketValue": 168000.00,
        "totalCost": 165000.00,
        "profit": 3000.00,
        "profitPercent": 1.82,
        "weight": 13.35,
        "market": "SH",
        "sector": "白酒",
        "addedDate": "2026-03-15"
      },
      // ... 更多持仓
    ],
    "totalCount": 8,
    "totalMarketValue": 1208400.00,
    "totalCost": 1150000.00,
    "totalProfit": 58400.00,
    "totalProfitPercent": 5.08
  }
}
```

**数据来源**:
1. 从 `portfolio_holdings` 表获取所有持仓
2. 关联 `klines` 表获取最新价格
3. 计算市值、盈亏、占比

**实现逻辑**:

```python
def get_portfolio_holdings():
    # 1. 获取所有持仓
    holdings = portfolio_repo.get_all_holdings()
    
    # 2. 获取最新价格并计算
    enriched_holdings = []
    total_market_value = 0
    total_cost = 0
    
    for holding in holdings:
        current_price = kline_repo.get_latest_price(holding['symbol'])
        
        if current_price is None:
            # 价格缺失，使用成本价
            current_price = holding['avg_cost']
        
        market_value = holding['quantity'] * current_price
        total_cost_item = holding['quantity'] * holding['avg_cost']
        profit = market_value - total_cost_item
        profit_percent = (profit / total_cost_item) * 100
        
        enriched_holdings.append({
            'symbol': holding['symbol'],
            'name': holding['name'],
            'quantity': holding['quantity'],
            'avgCost': holding['avg_cost'],
            'currentPrice': current_price,
            'marketValue': market_value,
            'totalCost': total_cost_item,
            'profit': profit,
            'profitPercent': profit_percent,
            'market': holding['market'],
            'sector': holding['sector'],
            'addedDate': holding['added_date']
        })
        
        total_market_value += market_value
        total_cost += total_cost_item
    
    # 3. 计算权重
    for holding in enriched_holdings:
        holding['weight'] = (holding['marketValue'] / total_market_value) * 100
    
    # 4. 按市值排序
    enriched_holdings.sort(key=lambda x: x['marketValue'], reverse=True)
    
    # 5. 组装响应
    return {
        'holdings': enriched_holdings,
        'totalCount': len(enriched_holdings),
        'totalMarketValue': total_market_value,
        'totalCost': total_cost,
        'totalProfit': total_market_value - total_cost,
        'totalProfitPercent': ((total_market_value - total_cost) / total_cost) * 100
    }
```

**错误处理**:
- 如果 `portfolio_holdings` 表为空，返回空列表
- 如果某个股票价格缺失，使用成本价作为当前价格，并在日志中记录警告

---


### 4.4 GET /api/signals (调整)

**用途**: 获取信号列表，支持日期过滤

**新增请求参数**:
- `date` (可选): 日期过滤，支持 `today`、`YYYY-MM-DD` 格式
- `limit` (可选): 返回数量限制，默认 100

**示例请求**:
```
GET /api/signals?date=today&limit=5
GET /api/signals?date=2026-05-23&limit=10
GET /api/signals?days=30  # 保持向后兼容
```

**响应格式**: (保持现有格式，无变化)

**实现调整**:

```python
@app.route('/api/signals', methods=['GET'])
def get_signals():
    days = request.args.get('days', type=int)
    date_filter = request.args.get('date')
    limit = request.args.get('limit', 100, type=int)
    
    if date_filter == 'today':
        # 查询今日信号
        signals = signal_repo.get_signals_by_date(
            datetime.now().date(), 
            datetime.now().date()
        )
    elif date_filter:
        # 查询指定日期
        target_date = datetime.strptime(date_filter, '%Y-%m-%d').date()
        signals = signal_repo.get_signals_by_date(target_date, target_date)
    elif days:
        # 保持向后兼容
        signals = signal_repo.get_latest_signals(days=days)
    else:
        signals = signal_repo.get_latest_signals(limit=limit)
    
    return jsonify({
        'success': True,
        'signals': signals,
        'count': len(signals)
    })
```

---

### 4.5 GET /api/backtest/results (调整)

**用途**: 获取回测结果列表

**新增请求参数**:
- `limit` (可选): 返回数量限制，默认 20

**示例请求**:
```
GET /api/backtest/results?limit=5
```

**响应格式**: (保持现有格式，无变化)

**实现调整**:

```python
@app.route('/api/backtest/results', methods=['GET'])
def get_backtest_results():
    limit = request.args.get('limit', 20, type=int)
    
    # 查询最近的回测结果
    results = backtest_repo.get_recent_results(limit=limit)
    
    return jsonify({
        'success': True,
        'summary': results,
        'count': len(results)
    })
```

---

## 5. 资产计算引擎设计

### 5.1 PortfolioCalculator 类

**文件位置**: `quantsys-v2/core/portfolio_calculator.py`

**职责**:
- 计算投资组合总资产
- 计算持仓盈亏和收益率
- 统计持仓数量
- 计算现金余额
- 生成账户余额快照

**类结构**:

```python
class PortfolioCalculator:
    """投资组合计算引擎"""
    
    def __init__(self, initial_cash: float = 1000000.0):
        """
        初始化计算引擎
        
        Args:
            initial_cash: 初始资金，默认 100 万
        """
        self.initial_cash = initial_cash
        self.portfolio_repo = PortfolioRepository()
        self.kline_repo = KlineRepository()
        self.risk_repo = RiskRepository()
    
    def calculate_snapshot(self, snapshot_date: date) -> Dict:
        """
        计算指定日期的账户快照
        
        Args:
            snapshot_date: 快照日期
            
        Returns:
            账户快照数据字典
        """
        pass
    
    def calculate_current_assets(self) -> float:
        """计算当前总资产"""
        pass
    
    def calculate_cash_balance(self, snapshot_date: date) -> float:
        """计算现金余额"""
        pass
    
    def calculate_market_value(self, snapshot_date: date) -> float:
        """计算持仓市值"""
        pass
    
    def calculate_daily_return(
        self, 
        current_assets: float, 
        previous_assets: float
    ) -> float:
        """计算日收益率"""
        pass
    
    def get_position_count(self) -> int:
        """获取持仓数量"""
        pass
```

### 5.2 核心计算逻辑

#### 5.2.1 总资产计算

```python
def calculate_current_assets(self) -> float:
    """
    计算当前总资产
    
    总资产 = 现金余额 + 持仓市值
    """
    cash = self.calculate_cash_balance(date.today())
    market_value = self.calculate_market_value(date.today())
    
    return cash + market_value
```

#### 5.2.2 现金余额计算

```python
def calculate_cash_balance(self, snapshot_date: date) -> float:
    """
    计算现金余额
    
    现金余额 = 初始资金 - 累计买入金额 + 累计卖出金额 - 累计手续费
    """
    # 获取截止到 snapshot_date 的所有交易
    trades = self.portfolio_repo.get_trades_by_date(
        start_date='2020-01-01',  # 从很早开始
        end_date=snapshot_date.strftime('%Y-%m-%d')
    )
    
    cash = self.initial_cash
    
    for trade in trades:
        if trade['action'] == 'buy':
            # 买入：减少现金
            cash -= trade['amount']
            cash -= trade.get('fee', 0)
            cash -= trade.get('stamp_duty', 0)
        elif trade['action'] == 'sell':
            # 卖出：增加现金
            cash += trade['amount']
            cash -= trade.get('fee', 0)
            cash -= trade.get('stamp_duty', 0)
    
    return cash
```

#### 5.2.3 持仓市值计算

```python
def calculate_market_value(self, snapshot_date: date) -> float:
    """
    计算持仓市值
    
    持仓市值 = Σ(持仓数量 × 当日收盘价)
    """
    holdings = self.portfolio_repo.get_all_holdings()
    
    total_market_value = 0.0
    
    for holding in holdings:
        # 获取指定日期的收盘价
        price = self.kline_repo.get_close_price(
            symbol=holding['symbol'],
            trade_date=snapshot_date
        )
        
        if price is None:
            # 价格缺失，使用成本价
            price = holding['avg_cost']
            logger.warning(
                f"Price missing for {holding['symbol']} on {snapshot_date}, "
                f"using avg_cost {price}"
            )
        
        market_value = holding['quantity'] * price
        total_market_value += market_value
    
    return total_market_value
```

#### 5.2.4 日收益率计算

```python
def calculate_daily_return(
    self, 
    current_assets: float, 
    previous_assets: float
) -> float:
    """
    计算日收益率
    
    日收益率 = (当日总资产 - 前日总资产) / 前日总资产 × 100
    """
    if previous_assets == 0:
        return 0.0
    
    return ((current_assets - previous_assets) / previous_assets) * 100
```

#### 5.2.5 完整快照计算

```python
def calculate_snapshot(self, snapshot_date: date) -> Dict:
    """
    计算指定日期的完整账户快照
    
    Args:
        snapshot_date: 快照日期
        
    Returns:
        账户快照数据字典
    """
    # 1. 计算现金和市值
    cash = self.calculate_cash_balance(snapshot_date)
    market_value = self.calculate_market_value(snapshot_date)
    total_assets = cash + market_value
    
    # 2. 获取前一日资产（用于计算日收益）
    previous_date = snapshot_date - timedelta(days=1)
    previous_balance = self.risk_repo.get_balance_by_date(previous_date)
    
    if previous_balance:
        previous_assets = previous_balance['total_assets']
        daily_pnl = total_assets - previous_assets
        daily_return = self.calculate_daily_return(total_assets, previous_assets)
    else:
        daily_pnl = 0.0
        daily_return = 0.0
    
    # 3. 计算总盈亏
    total_pnl = total_assets - self.initial_cash
    total_return = (total_pnl / self.initial_cash) * 100
    
    # 4. 统计持仓数量
    position_count = self.get_position_count()
    
    # 5. 组装快照数据
    snapshot = {
        'balance_date': snapshot_date,
        'cash': cash,
        'market_value': market_value,
        'total_assets': total_assets,
        'daily_pnl': daily_pnl,
        'daily_return': daily_return,
        'total_pnl': total_pnl,
        'total_return': total_return,
        'position_count': position_count
    }
    
    return snapshot
```

### 5.3 边界情况处理

#### 5.3.1 价格缺失

**场景**: 某个股票在指定日期没有 K 线数据（停牌、新股等）

**处理策略**:
1. 使用最近一个交易日的收盘价
2. 如果最近 30 天都没有数据，使用持仓成本价
3. 记录警告日志

```python
def get_close_price_with_fallback(
    self, 
    symbol: str, 
    target_date: date
) -> float:
    """获取收盘价，带回退策略"""
    
    # 尝试获取目标日期的价格
    price = self.kline_repo.get_close_price(symbol, target_date)
    
    if price is not None:
        return price
    
    # 回退策略1: 查找最近30天的价格
    for i in range(1, 31):
        fallback_date = target_date - timedelta(days=i)
        price = self.kline_repo.get_close_price(symbol, fallback_date)
        if price is not None:
            logger.warning(
                f"Using fallback price for {symbol}: "
                f"{fallback_date} instead of {target_date}"
            )
            return price
    
    # 回退策略2: 使用持仓成本价
    holding = self.portfolio_repo.get_holding(symbol)
    if holding:
        logger.warning(
            f"No price data for {symbol}, using avg_cost {holding['avg_cost']}"
        )
        return holding['avg_cost']
    
    # 最后的回退: 返回 0（不应该发生）
    logger.error(f"Cannot find any price for {symbol}")
    return 0.0
```

#### 5.3.2 初始资金配置

**场景**: 系统需要知道初始投入的资金量

**处理策略**:
1. 从配置文件读取 `INITIAL_CASH`
2. 如果未配置，默认使用 100 万
3. 支持通过环境变量覆盖

```python
import os

class PortfolioCalculator:
    def __init__(self):
        # 从环境变量或配置文件读取初始资金
        self.initial_cash = float(
            os.getenv('INITIAL_CASH', 1000000.0)
        )
```

#### 5.3.3 交易日判断

**场景**: 周末和节假日不应该生成快照

**处理策略**:
1. 只在交易日生成快照
2. 使用 `is_trading_day()` 函数判断

```python
def is_trading_day(check_date: date) -> bool:
    """判断是否为交易日"""
    # 1. 排除周末
    if check_date.weekday() >= 5:  # 5=周六, 6=周日
        return False
    
    # 2. 排除节假日（可以从配置文件或数据库读取）
    # TODO: 实现节假日判断逻辑
    
    return True
```

---

## 6. 定时任务设计

### 6.1 DailySnapshotJob

**文件位置**: `quantsys-v2/jobs/daily_snapshot_job.py`

**职责**:
- 每日收盘后自动触发
- 调用 PortfolioCalculator 计算快照
- 写入 account_balance 表
- 记录任务日志
- 错误通知

**类结构**:

```python
from core.portfolio_calculator import PortfolioCalculator
from repositories.risk_repository import RiskRepository
from datetime import date, datetime
import logging

logger = logging.getLogger(__name__)

class DailySnapshotJob:
    """每日账户快照任务"""
    
    def __init__(self):
        self.calculator = PortfolioCalculator()
        self.risk_repo = RiskRepository()
    
    def run(self):
        """执行任务"""
        try:
            logger.info("Starting daily snapshot job...")
            
            # 1. 检查是否为交易日
            today = date.today()
            if not self.is_trading_day(today):
                logger.info(f"{today} is not a trading day, skipping...")
                return
            
            # 2. 检查是否已经生成过快照
            existing = self.risk_repo.get_balance_by_date(today)
            if existing:
                logger.warning(f"Snapshot for {today} already exists, skipping...")
                return
            
            # 3. 计算快照
            snapshot = self.calculator.calculate_snapshot(today)
            
            # 4. 写入数据库
            self.risk_repo.save_balance(snapshot)
            
            logger.info(
                f"Daily snapshot completed: "
                f"total_assets={snapshot['total_assets']}, "
                f"daily_return={snapshot['daily_return']}%"
            )
            
        except Exception as e:
            logger.error(f"Daily snapshot job failed: {str(e)}", exc_info=True)
            # TODO: 发送错误通知（邮件、钉钉等）
            raise
    
    def is_trading_day(self, check_date: date) -> bool:
        """判断是否为交易日"""
        # 排除周末
        if check_date.weekday() >= 5:
            return False
        # TODO: 排除节假日
        return True
```

### 6.2 调度器集成

**方式1: 使用现有的 scheduler 系统**

如果 quantsys-v2 已有调度器（如 APScheduler），直接注册任务：

```python
# 在 scheduler 配置文件中添加
from jobs.daily_snapshot_job import DailySnapshotJob

scheduler.add_job(
    func=DailySnapshotJob().run,
    trigger='cron',
    hour=15,
    minute=30,
    id='daily_snapshot_job',
    name='每日账户快照',
    replace_existing=True
)
```

**方式2: 使用 cron**

如果没有调度器，使用系统 cron：

```bash
# 每天 15:30 执行
30 15 * * 1-5 cd /path/to/quantsys-v2 && python -m jobs.daily_snapshot_job
```

### 6.3 任务监控

**日志记录**:

```python
# 任务开始
logger.info("Starting daily snapshot job...")

# 任务完成
logger.info(
    f"Daily snapshot completed: "
    f"total_assets={snapshot['total_assets']}, "
    f"daily_return={snapshot['daily_return']}%"
)

# 任务失败
logger.error(f"Daily snapshot job failed: {str(e)}", exc_info=True)
```

**错误通知**:

```python
def send_error_notification(error_message: str):
    """发送错误通知"""
    # TODO: 实现通知逻辑
    # 1. 邮件通知
    # 2. 钉钉/企业微信通知
    # 3. 短信通知
    pass
```

---


## 7. 数据回填设计

### 7.1 回填脚本

**文件位置**: `quantsys-v2/scripts/backfill_portfolio_history.py`

**用途**: 补充历史账户余额数据（最近 90 天）

**实现逻辑**:

```python
#!/usr/bin/env python3
"""
回填投资组合历史数据

用法:
    python scripts/backfill_portfolio_history.py --days 90
"""

import argparse
from datetime import date, timedelta
from core.portfolio_calculator import PortfolioCalculator
from repositories.risk_repository import RiskRepository
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def backfill_history(days: int = 90):
    """
    回填历史数据
    
    Args:
        days: 回填天数
    """
    calculator = PortfolioCalculator()
    risk_repo = RiskRepository()
    
    end_date = date.today()
    start_date = end_date - timedelta(days=days)
    
    logger.info(f"Backfilling portfolio history from {start_date} to {end_date}")
    
    current_date = start_date
    success_count = 0
    skip_count = 0
    error_count = 0
    
    while current_date <= end_date:
        try:
            # 1. 检查是否为交易日
            if current_date.weekday() >= 5:
                logger.debug(f"Skipping weekend: {current_date}")
                current_date += timedelta(days=1)
                skip_count += 1
                continue
            
            # 2. 检查是否已存在
            existing = risk_repo.get_balance_by_date(current_date)
            if existing:
                logger.debug(f"Snapshot already exists for {current_date}, skipping")
                current_date += timedelta(days=1)
                skip_count += 1
                continue
            
            # 3. 计算快照
            snapshot = calculator.calculate_snapshot(current_date)
            
            # 4. 写入数据库
            risk_repo.save_balance(snapshot)
            
            logger.info(
                f"✓ {current_date}: total_assets={snapshot['total_assets']:.2f}, "
                f"daily_return={snapshot['daily_return']:.2f}%"
            )
            success_count += 1
            
        except Exception as e:
            logger.error(f"✗ Failed to backfill {current_date}: {str(e)}")
            error_count += 1
        
        current_date += timedelta(days=1)
    
    # 5. 输出统计
    logger.info("=" * 60)
    logger.info(f"Backfill completed:")
    logger.info(f"  Success: {success_count}")
    logger.info(f"  Skipped: {skip_count}")
    logger.info(f"  Errors:  {error_count}")
    logger.info("=" * 60)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Backfill portfolio history')
    parser.add_argument('--days', type=int, default=90, help='Number of days to backfill')
    args = parser.parse_args()
    
    backfill_history(args.days)
```

### 7.2 回填策略

**回填顺序**: 从旧到新（时间正序）

**原因**: 
- 日收益率计算依赖前一日的数据
- 按时间顺序回填可以保证数据一致性

**回填范围**: 
- 默认最近 90 天
- 可通过参数调整

**数据验证**:

```python
def validate_backfill_data():
    """验证回填数据的准确性"""
    risk_repo = RiskRepository()
    
    # 1. 检查数据连续性
    history = risk_repo.get_history(days=90)
    
    if len(history) == 0:
        logger.error("No data found after backfill")
        return False
    
    # 2. 检查日收益率计算是否正确
    for i in range(1, len(history)):
        prev_assets = history[i-1]['total_assets']
        curr_assets = history[i]['total_assets']
        expected_return = ((curr_assets - prev_assets) / prev_assets) * 100
        actual_return = history[i]['daily_return']
        
        if abs(expected_return - actual_return) > 0.01:
            logger.warning(
                f"Daily return mismatch on {history[i]['balance_date']}: "
                f"expected={expected_return:.2f}%, actual={actual_return:.2f}%"
            )
    
    logger.info("Data validation completed")
    return True
```

### 7.3 执行步骤

1. **备份数据库** (可选但推荐)
   ```bash
   pg_dump quantsys > backup_before_backfill.sql
   ```

2. **执行回填脚本**
   ```bash
   cd /path/to/quantsys-v2
   python scripts/backfill_portfolio_history.py --days 90
   ```

3. **验证数据**
   ```bash
   python scripts/validate_backfill.py
   ```

4. **检查结果**
   ```sql
   SELECT balance_date, total_assets, daily_return
   FROM quant.account_balance
   ORDER BY balance_date DESC
   LIMIT 10;
   ```

---

## 8. 实施计划

### 8.1 阶段划分

#### 阶段 1: 数据库准备（2-3 小时）

**任务**:
1. 确认 `account_balance` 表结构
2. 确认索引已创建
3. 准备数据库迁移脚本（如需要）

**验收标准**:
- 表结构符合设计
- 索引已创建
- 可以正常插入和查询数据

---

#### 阶段 2: 计算引擎开发（3-4 小时）

**任务**:
1. 创建 `core/portfolio_calculator.py`
2. 实现核心计算逻辑
3. 编写单元测试
4. 测试边界情况处理

**文件清单**:
- `core/portfolio_calculator.py` (新建)
- `tests/test_portfolio_calculator.py` (新建)

**验收标准**:
- 所有单元测试通过
- 边界情况处理正确
- 代码覆盖率 > 80%

---

#### 阶段 3: 定时任务集成（2-3 小时）

**任务**:
1. 创建 `jobs/daily_snapshot_job.py`
2. 集成到调度器
3. 配置执行时间
4. 添加日志和监控

**文件清单**:
- `jobs/daily_snapshot_job.py` (新建)
- `config/scheduler_config.py` (修改)

**验收标准**:
- 任务可以手动触发执行
- 任务日志正常记录
- 错误处理机制有效

---

#### 阶段 4: API 端点实现（2-3 小时）

**任务**:
1. 在 `api/server.py` 添加 3 个新端点
2. 调整 2 个现有端点
3. 添加参数验证
4. 编写 API 文档

**文件清单**:
- `api/server.py` (修改)
- `api/validators.py` (可能需要)
- `docs/api/portfolio-endpoints.md` (新建)

**验收标准**:
- 所有端点返回正确的数据格式
- 参数验证正常工作
- 错误处理完善
- API 文档完整

---

#### 阶段 5: 数据回填（3-4 小时）

**任务**:
1. 编写回填脚本
2. 执行数据回填（90 天）
3. 验证数据准确性
4. 修复发现的问题

**文件清单**:
- `scripts/backfill_portfolio_history.py` (新建)
- `scripts/validate_backfill.py` (新建)

**验收标准**:
- 历史数据完整（90 天）
- 数据验证通过
- 无明显异常值

---

#### 阶段 6: 前端集成与测试（2-3 小时）

**任务**:
1. 更新 React Dashboard 调用新 API
2. 添加投资组合指标卡片
3. 添加净值走势图
4. 端到端测试

**文件清单**:
- `quant-web/src/components/dashboard/DashboardOverview.tsx` (修改)
- `quant-web/src/components/dashboard/PortfolioSummaryCard.tsx` (新建)
- `quant-web/src/components/dashboard/PortfolioHistoryChart.tsx` (新建)

**验收标准**:
- Dashboard 正确展示所有数据
- 图表渲染正常
- 无 API 错误
- 响应时间 < 1 秒

---

### 8.2 时间估算

| 阶段 | 预计时间 | 累计时间 |
|------|---------|---------|
| 1. 数据库准备 | 2-3 小时 | 2-3 小时 |
| 2. 计算引擎开发 | 3-4 小时 | 5-7 小时 |
| 3. 定时任务集成 | 2-3 小时 | 7-10 小时 |
| 4. API 端点实现 | 2-3 小时 | 9-13 小时 |
| 5. 数据回填 | 3-4 小时 | 12-17 小时 |
| 6. 前端集成与测试 | 2-3 小时 | 14-20 小时 |

**总计**: 14-20 小时（约 2 个工作日）

---

### 8.3 风险与应对

#### 风险 1: account_balance 表数据缺失

**影响**: 无法提供历史净值数据

**应对**:
- 执行数据回填脚本
- 如果回填失败，提供实时计算的临时方案

---

#### 风险 2: 价格数据不完整

**影响**: 计算结果不准确

**应对**:
- 实现价格回退策略（使用最近价格或成本价）
- 记录警告日志，便于后续修复

---

#### 风险 3: 初始资金配置不明确

**影响**: 总盈亏和收益率计算不准确

**应对**:
- 从配置文件或环境变量读取
- 提供默认值（100 万）
- 支持后续调整

---

#### 风险 4: 定时任务执行失败

**影响**: 数据不更新

**应对**:
- 添加错误通知机制
- 支持手动触发任务
- 记录详细日志便于排查

---

## 9. 测试策略

### 9.1 单元测试

**测试范围**:
- PortfolioCalculator 的所有计算方法
- 边界情况处理
- 错误处理

**测试用例示例**:

```python
# tests/test_portfolio_calculator.py

import pytest
from datetime import date
from core.portfolio_calculator import PortfolioCalculator

class TestPortfolioCalculator:
    
    def test_calculate_current_assets(self):
        """测试总资产计算"""
        calculator = PortfolioCalculator(initial_cash=1000000)
        
        # Mock 数据
        # ...
        
        assets = calculator.calculate_current_assets()
        assert assets > 0
    
    def test_calculate_cash_balance(self):
        """测试现金余额计算"""
        calculator = PortfolioCalculator(initial_cash=1000000)
        
        cash = calculator.calculate_cash_balance(date.today())
        assert cash >= 0
    
    def test_price_fallback(self):
        """测试价格回退策略"""
        calculator = PortfolioCalculator()
        
        # 测试价格缺失时的回退逻辑
        # ...
    
    def test_daily_return_calculation(self):
        """测试日收益率计算"""
        calculator = PortfolioCalculator()
        
        return_pct = calculator.calculate_daily_return(1050000, 1000000)
        assert abs(return_pct - 5.0) < 0.01
```

### 9.2 集成测试

**测试范围**:
- API 端点的完整请求-响应流程
- 数据库读写
- 错误处理

**测试用例示例**:

```python
# tests/test_portfolio_api.py

import pytest
from api.server import app

class TestPortfolioAPI:
    
    @pytest.fixture
    def client(self):
        app.config['TESTING'] = True
        with app.test_client() as client:
            yield client
    
    def test_get_portfolio_summary(self, client):
        """测试获取投资组合摘要"""
        response = client.get('/api/portfolio/summary')
        
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True
        assert 'totalValue' in data['data']
        assert 'holdingsCount' in data['data']
    
    def test_get_portfolio_history(self, client):
        """测试获取历史净值"""
        response = client.get('/api/portfolio/history?days=30')
        
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True
        assert len(data['data']['history']) > 0
    
    def test_get_portfolio_holdings(self, client):
        """测试获取持仓列表"""
        response = client.get('/api/portfolio/holdings')
        
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True
        assert 'holdings' in data['data']
```

### 9.3 端到端测试

**测试范围**:
- 前端 Dashboard 完整流程
- 数据展示正确性
- 用户交互

**测试步骤**:
1. 启动后端服务
2. 启动前端开发服务器
3. 打开浏览器访问 Dashboard
4. 验证所有数据正确展示
5. 测试刷新功能
6. 测试不同时间范围的切换

---

## 10. 部署与上线

### 10.1 部署前检查清单

- [ ] 所有单元测试通过
- [ ] 所有集成测试通过
- [ ] API 文档已更新
- [ ] 数据库迁移脚本已准备
- [ ] 定时任务已配置
- [ ] 日志和监控已配置
- [ ] 数据回填已完成
- [ ] 前端代码已构建

### 10.2 部署步骤

1. **备份数据库**
   ```bash
   pg_dump quantsys > backup_$(date +%Y%m%d).sql
   ```

2. **部署后端代码**
   ```bash
   cd /path/to/quantsys-v2
   git pull origin main
   pip install -r requirements.txt
   ```

3. **执行数据库迁移** (如需要)
   ```bash
   python migrations/run_migration.py
   ```

4. **执行数据回填**
   ```bash
   python scripts/backfill_portfolio_history.py --days 90
   ```

5. **重启后端服务**
   ```bash
   systemctl restart quantsys-api
   ```

6. **配置定时任务**
   ```bash
   # 添加到 crontab 或调度器配置
   30 15 * * 1-5 cd /path/to/quantsys-v2 && python -m jobs.daily_snapshot_job
   ```

7. **部署前端代码**
   ```bash
   cd /path/to/quant-web
   git pull origin main
   npm install
   npm run build
   ```

8. **验证部署**
   - 访问 Dashboard 页面
   - 检查所有数据正确展示
   - 检查 API 响应时间
   - 检查日志无错误

### 10.3 回滚计划

如果部署后发现问题：

1. **回滚代码**
   ```bash
   git checkout <previous-commit>
   ```

2. **恢复数据库** (如果执行了迁移)
   ```bash
   psql quantsys < backup_$(date +%Y%m%d).sql
   ```

3. **重启服务**
   ```bash
   systemctl restart quantsys-api
   ```

---

## 11. 后续优化

### 11.1 性能优化

1. **添加缓存**
   - 对 `/api/portfolio/summary` 添加 Redis 缓存（TTL 5 分钟）
   - 对 `/api/portfolio/holdings` 添加缓存（TTL 1 分钟）

2. **数据库查询优化**
   - 添加复合索引
   - 使用物化视图

3. **API 响应优化**
   - 启用 gzip 压缩
   - 添加 ETag 支持

### 11.2 功能扩展

1. **持仓快照表**
   - 创建 `portfolio_snapshots` 表
   - 存储每日持仓明细快照
   - 支持持仓历史回溯

2. **更多统计指标**
   - 夏普比率
   - 最大回撤
   - 波动率
   - 行业分布

3. **实时数据推送**
   - 使用 WebSocket 推送实时净值变化
   - 推送持仓盈亏变化

### 11.3 监控告警

1. **任务监控**
   - 监控定时任务执行状态
   - 任务失败时发送告警

2. **数据质量监控**
   - 监控价格数据完整性
   - 监控计算结果异常值

3. **API 性能监控**
   - 监控 API 响应时间
   - 监控 API 错误率

---

## 12. 附录

### 12.1 配置文件示例

**环境变量配置** (`.env`):

```bash
# 初始资金
INITIAL_CASH=1000000.0

# 数据库配置
DB_HOST=localhost
DB_PORT=5432
DB_NAME=quantsys
DB_USER=postgres
DB_PASSWORD=your_password

# 定时任务配置
SNAPSHOT_JOB_HOUR=15
SNAPSHOT_JOB_MINUTE=30
```

### 12.2 API 响应示例

详见第 4 节 API 接口设计。

### 12.3 数据库 Schema

详见第 3 节数据库设计。

---

## 13. 总结

本设计文档详细描述了为 React Dashboard 补充投资组合 API 的完整方案，包括：

1. **系统架构**: 定时任务 + 计算引擎 + API 端点
2. **数据库设计**: 利用现有表结构，无需新增表
3. **API 设计**: 3 个新端点 + 2 个调整
4. **计算引擎**: 完整的资产计算逻辑和边界处理
5. **定时任务**: 每日自动更新数据
6. **数据回填**: 补充历史 90 天数据
7. **实施计划**: 6 个阶段，14-20 小时
8. **测试策略**: 单元测试 + 集成测试 + 端到端测试
9. **部署方案**: 完整的部署和回滚流程

**预期成果**:
- React Dashboard 展示完整的投资组合数据
- 每日自动更新账户余额
- 支持历史净值走势查询
- 性能优秀，响应时间 < 1 秒

**下一步**: 进入实施阶段，按照本文档的计划逐步执行。

