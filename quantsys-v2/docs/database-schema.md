# 数据库表结构文档（完整版）

## 概述

QuantSys V2 使用 **PostgreSQL** 数据库，所有表都在 `quant` schema 下。

**数据库配置**：
- Schema: `quant`
- 连接方式: 环境变量 `QUANT_DATABASE_URL` / `DATABASE_URL` / `POSTGRES_DSN`
- 默认数据库名: `quant_investment`

**表结构分层**：
- **核心数据层（6张）**: stocks, daily_klines, minute_klines, factor_values, trading_signals, signal_factors
- **交易执行层（3张）**: portfolio_holdings, trades, orders
- **策略回测层（2张）**: backtest_results, strategy_configs
- **风险管理层（2张）**: account_balance, risk_metrics
- **执行记录层（1张）**: signal_executions

**总计：14张表**

---

## 第一部分：核心数据层

### 1. quant.stocks - 股票基础信息表

存储股票的基本信息和财务指标。

```sql
CREATE TABLE quant.stocks (
    symbol TEXT PRIMARY KEY,                    -- 股票代码（6位数字）
    name TEXT NOT NULL,                         -- 股票名称
    market TEXT NOT NULL,                       -- 市场类型（A/HK）
    industry TEXT,                              -- 行业
    sector TEXT,                                -- 板块
    market_cap DOUBLE PRECISION,                -- 市值
    pe DOUBLE PRECISION,                        -- 市盈率
    pb DOUBLE PRECISION,                        -- 市净率
    total_mv DOUBLE PRECISION,                  -- 总市值
    circulating_mv DOUBLE PRECISION,            -- 流通市值
    is_st BOOLEAN NOT NULL DEFAULT FALSE,       -- 是否ST股票
    is_suspended BOOLEAN NOT NULL DEFAULT FALSE,-- 是否停牌
    list_date DATE,                             -- 上市日期
    roe DOUBLE PRECISION,                       -- 净资产收益率
    net_profit_growth DOUBLE PRECISION,         -- 净利润增长率
    gross_margin DOUBLE PRECISION,              -- 毛利率
    debt_ratio DOUBLE PRECISION,                -- 资产负债率
    avg_turnover_rate DOUBLE PRECISION,         -- 平均换手率
    avg_volume DOUBLE PRECISION,                -- 平均成交量
    avg_amount DOUBLE PRECISION,                -- 平均成交额
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now() -- 更新时间
);

-- 索引
CREATE INDEX idx_quant_stocks_market ON quant.stocks(market);
CREATE INDEX idx_quant_stocks_industry ON quant.stocks(industry);
CREATE INDEX idx_quant_stocks_sector ON quant.stocks(sector);
CREATE INDEX idx_quant_stocks_updated_at ON quant.stocks(updated_at);
```

**字段说明**：
- `symbol`: 6位数字股票代码，如 "600000"
- `market`: "A" 表示A股，"HK" 表示港股
- `is_st`: ST股票标记，用于风险控制
- `is_suspended`: 停牌标记
- 财务指标字段可为NULL，表示数据未获取

---

### 2. quant.daily_klines - 日K线数据表

存储股票的日K线数据（OHLCV）。

```sql
CREATE TABLE quant.daily_klines (
    symbol TEXT NOT NULL REFERENCES quant.stocks(symbol) ON DELETE CASCADE,
    trade_date DATE NOT NULL,                   -- 交易日期
    open DOUBLE PRECISION,                      -- 开盘价
    high DOUBLE PRECISION,                      -- 最高价
    low DOUBLE PRECISION,                       -- 最低价
    close DOUBLE PRECISION,                     -- 收盘价
    volume DOUBLE PRECISION,                    -- 成交量
    amount DOUBLE PRECISION,                    -- 成交额
    turnover_rate DOUBLE PRECISION,             -- 换手率
    PRIMARY KEY (symbol, trade_date)
);

-- 索引
CREATE INDEX idx_quant_daily_klines_symbol_date_desc 
    ON quant.daily_klines(symbol, trade_date DESC);
CREATE INDEX idx_quant_daily_klines_trade_date 
    ON quant.daily_klines(trade_date);
```

**字段说明**：
- `symbol`: 外键关联 `quant.stocks.symbol`，级联删除
- `trade_date`: 交易日期，与symbol组成复合主键
- OHLCV: 标准K线数据

---

### 3. quant.minute_klines - 分钟K线数据表

存储股票的分钟级K线数据，用于日内交易和高频策略。

```sql
CREATE TABLE quant.minute_klines (
    symbol TEXT NOT NULL REFERENCES quant.stocks(symbol) ON DELETE CASCADE,
    ts TIMESTAMPTZ NOT NULL,                    -- 时间戳（精确到分钟）
    open DOUBLE PRECISION,                      -- 开盘价
    high DOUBLE PRECISION,                      -- 最高价
    low DOUBLE PRECISION,                       -- 最低价
    close DOUBLE PRECISION,                     -- 收盘价
    volume DOUBLE PRECISION,                    -- 成交量
    amount DOUBLE PRECISION,                    -- 成交额
    PRIMARY KEY (symbol, ts)
);

-- 索引
CREATE INDEX idx_quant_minute_klines_symbol_ts_desc 
    ON quant.minute_klines(symbol, ts DESC);
CREATE INDEX idx_quant_minute_klines_ts 
    ON quant.minute_klines(ts);

-- 分区建议（数据量大时）
-- CREATE TABLE quant.minute_klines_2026_05 PARTITION OF quant.minute_klines
--     FOR VALUES FROM ('2026-05-01') TO ('2026-06-01');
```

**字段说明**：
- `ts`: 时间戳，精确到分钟，如 "2026-05-20 09:31:00+00"
- 数据量大时建议按月分区
- 用于日内交易、高频策略、实时监控

---

### 4. quant.factor_values - 因子值表

存储计算后的技术因子值。

```sql
CREATE TABLE quant.factor_values (
    symbol TEXT NOT NULL REFERENCES quant.stocks(symbol) ON DELETE CASCADE,
    factor_date DATE NOT NULL,                  -- 因子计算日期
    factor_name TEXT NOT NULL,                  -- 因子名称
    factor_value DOUBLE PRECISION,              -- 因子值
    PRIMARY KEY (symbol, factor_date, factor_name)
);

-- 索引
CREATE INDEX idx_quant_factor_values_symbol_date 
    ON quant.factor_values(symbol, factor_date);
CREATE INDEX idx_quant_factor_values_factor_date 
    ON quant.factor_values(factor_date);
CREATE INDEX idx_quant_factor_values_factor_name 
    ON quant.factor_values(factor_name);
```

**常见因子名称**：
- `ma5`, `ma10`, `ma20`: 移动平均线
- `rsi`: 相对强弱指标
- `macd`, `macd_signal`, `macd_hist`: MACD指标
- `boll_upper`, `boll_middle`, `boll_lower`: 布林带
- `atr`: 真实波动幅度
- `volume_ma5`, `volume_ratio`: 成交量指标

---

### 5. quant.trading_signals - 交易信号表

存储策略生成的交易信号。

```sql
CREATE TABLE quant.trading_signals (
    id BIGSERIAL PRIMARY KEY,                   -- 自增主键
    symbol TEXT NOT NULL REFERENCES quant.stocks(symbol) ON DELETE CASCADE,
    signal_date DATE NOT NULL,                  -- 信号日期
    signal_type TEXT NOT NULL CHECK (signal_type IN ('BUY', 'SELL', 'HOLD')),
    strategy_name TEXT NOT NULL,                -- 策略名称
    confidence DOUBLE PRECISION NOT NULL CHECK (confidence >= 0 AND confidence <= 1),
    price DOUBLE PRECISION NOT NULL,            -- 信号价格
    reason TEXT,                                -- 信号原因说明
    metadata JSONB,                             -- 额外元数据
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (symbol, signal_date, strategy_name)
);

-- 索引
CREATE INDEX idx_quant_trading_signals_symbol_date_desc 
    ON quant.trading_signals(symbol, signal_date DESC);
CREATE INDEX idx_quant_trading_signals_signal_date_desc 
    ON quant.trading_signals(signal_date DESC);
CREATE INDEX idx_quant_trading_signals_strategy_name 
    ON quant.trading_signals(strategy_name);
CREATE INDEX idx_quant_trading_signals_signal_type 
    ON quant.trading_signals(signal_type);
```

---

### 6. quant.signal_factors - 信号因子详情表

存储每个交易信号关联的因子详情。

```sql
CREATE TABLE quant.signal_factors (
    id BIGSERIAL PRIMARY KEY,                   -- 自增主键
    signal_id BIGINT NOT NULL REFERENCES quant.trading_signals(id) ON DELETE CASCADE,
    factor_name TEXT NOT NULL,                  -- 因子名称
    factor_value DOUBLE PRECISION NOT NULL,     -- 因子值
    factor_weight DOUBLE PRECISION,             -- 因子权重
    trigger_condition TEXT,                     -- 触发条件描述
    is_primary BOOLEAN NOT NULL DEFAULT FALSE,  -- 是否主要因子
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 索引
CREATE INDEX idx_quant_signal_factors_signal_id 
    ON quant.signal_factors(signal_id);
CREATE INDEX idx_quant_signal_factors_factor_name 
    ON quant.signal_factors(factor_name);
```


---

## 第二部分：交易执行层

### 7. quant.portfolio_holdings - 持仓表

存储当前持仓信息。

```sql
CREATE TABLE quant.portfolio_holdings (
    id BIGSERIAL PRIMARY KEY,
    symbol TEXT NOT NULL REFERENCES quant.stocks(symbol) ON DELETE CASCADE,
    name TEXT NOT NULL,                         -- 股票名称（冗余字段，便于查询）
    quantity INTEGER NOT NULL CHECK (quantity > 0), -- 持仓数量
    avg_cost DOUBLE PRECISION NOT NULL,         -- 平均成本
    original_cost DOUBLE PRECISION,             -- 原始成本
    total_invested DOUBLE PRECISION NOT NULL,   -- 总投入金额
    market TEXT NOT NULL,                       -- 市场（A/HK）
    sector TEXT,                                -- 板块
    added_date DATE NOT NULL,                   -- 建仓日期
    stop_loss DOUBLE PRECISION,                 -- 止损价
    target_price DOUBLE PRECISION,              -- 目标价
    buy_reason TEXT,                            -- 买入理由
    notes TEXT,                                 -- 备注
    updated_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE(symbol)                              -- 每只股票只能有一条持仓记录
);

-- 索引
CREATE INDEX idx_quant_portfolio_holdings_market 
    ON quant.portfolio_holdings(market);
CREATE INDEX idx_quant_portfolio_holdings_sector 
    ON quant.portfolio_holdings(sector);
CREATE INDEX idx_quant_portfolio_holdings_added_date 
    ON quant.portfolio_holdings(added_date);
```

**字段说明**：
- `quantity`: 当前持仓数量，必须大于0
- `avg_cost`: 平均成本价，用于计算浮动盈亏
- `total_invested`: 总投入 = avg_cost × quantity
- `stop_loss`: 止损价，触发后自动卖出
- `target_price`: 目标价，达到后考虑止盈
- 唯一约束：每只股票只能有一条持仓记录

**使用示例**：
```sql
-- 查询当前所有持仓
SELECT 
    symbol, name, quantity, avg_cost, 
    total_invested, sector, buy_reason
FROM quant.portfolio_holdings
ORDER BY total_invested DESC;

-- 计算持仓浮动盈亏（需要关联最新价格）
SELECT 
    h.symbol, h.name, h.quantity, h.avg_cost,
    k.close as current_price,
    (k.close - h.avg_cost) * h.quantity as unrealized_pnl,
    ((k.close - h.avg_cost) / h.avg_cost) * 100 as return_pct
FROM quant.portfolio_holdings h
LEFT JOIN LATERAL (
    SELECT close FROM quant.daily_klines 
    WHERE symbol = h.symbol 
    ORDER BY trade_date DESC 
    LIMIT 1
) k ON TRUE;
```

---

### 8. quant.trades - 交易记录表

存储所有历史交易记录（买入/卖出）。

```sql
CREATE TABLE quant.trades (
    id BIGSERIAL PRIMARY KEY,
    symbol TEXT NOT NULL REFERENCES quant.stocks(symbol) ON DELETE CASCADE,
    name TEXT NOT NULL,                         -- 股票名称
    action TEXT NOT NULL CHECK (action IN ('buy', 'sell')),
    price DOUBLE PRECISION NOT NULL CHECK (price > 0),
    quantity INTEGER NOT NULL CHECK (quantity > 0),
    amount DOUBLE PRECISION NOT NULL,           -- 交易金额 = price × quantity
    fee DOUBLE PRECISION DEFAULT 0,             -- 手续费
    stamp_duty DOUBLE PRECISION DEFAULT 0,      -- 印花税（卖出时）
    trade_date DATE NOT NULL,                   -- 交易日期
    reason TEXT,                                -- 交易原因
    order_id BIGINT,                            -- 关联订单ID（可选）
    created_at TIMESTAMPTZ DEFAULT now()
);

-- 索引
CREATE INDEX idx_quant_trades_symbol 
    ON quant.trades(symbol);
CREATE INDEX idx_quant_trades_trade_date_desc 
    ON quant.trades(trade_date DESC);
CREATE INDEX idx_quant_trades_action 
    ON quant.trades(action);
CREATE INDEX idx_quant_trades_order_id 
    ON quant.trades(order_id);
```

**字段说明**：
- `action`: 'buy' 买入，'sell' 卖出
- `amount`: 交易金额，不含手续费
- `fee`: 手续费（买入和卖出都有）
- `stamp_duty`: 印花税（仅卖出时收取，A股为0.1%）
- `order_id`: 关联订单表（如果交易来自订单系统）

**使用示例**：
```sql
-- 查询某股票的交易历史
SELECT 
    trade_date, action, price, quantity, 
    amount, fee, reason
FROM quant.trades
WHERE symbol = '600000'
ORDER BY trade_date DESC;

-- 计算总交易成本
SELECT 
    SUM(fee) as total_fee,
    SUM(stamp_duty) as total_stamp_duty,
    SUM(fee + stamp_duty) as total_cost
FROM quant.trades
WHERE trade_date >= '2026-01-01';

-- 统计买卖次数
SELECT 
    action,
    COUNT(*) as trade_count,
    SUM(amount) as total_amount
FROM quant.trades
GROUP BY action;
```

---

### 9. quant.orders - 订单表

存储待执行和已执行的订单。

```sql
CREATE TABLE quant.orders (
    id BIGSERIAL PRIMARY KEY,
    symbol TEXT NOT NULL REFERENCES quant.stocks(symbol) ON DELETE CASCADE,
    name TEXT NOT NULL,                         -- 股票名称
    order_type TEXT NOT NULL CHECK (order_type IN ('limit', 'market', 'stop')),
    action TEXT NOT NULL CHECK (action IN ('buy', 'sell')),
    price DOUBLE PRECISION,                     -- 限价单价格（市价单为NULL）
    quantity INTEGER NOT NULL CHECK (quantity > 0),
    status TEXT NOT NULL CHECK (status IN ('pending', 'partial', 'filled', 'cancelled', 'expired')),
    filled_quantity INTEGER DEFAULT 0,          -- 已成交数量
    avg_filled_price DOUBLE PRECISION,          -- 平均成交价
    reason TEXT,                                -- 下单原因
    signal_id BIGINT,                           -- 关联信号ID（可选）
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now(),
    expires_at TIMESTAMPTZ                      -- 订单过期时间
);

-- 索引
CREATE INDEX idx_quant_orders_symbol 
    ON quant.orders(symbol);
CREATE INDEX idx_quant_orders_status 
    ON quant.orders(status);
CREATE INDEX idx_quant_orders_created_at_desc 
    ON quant.orders(created_at DESC);
CREATE INDEX idx_quant_orders_signal_id 
    ON quant.orders(signal_id);
```

**字段说明**：
- `order_type`: 
  - `limit`: 限价单（指定价格）
  - `market`: 市价单（立即成交）
  - `stop`: 止损单（触发价格后转为市价单）
- `status`:
  - `pending`: 待成交
  - `partial`: 部分成交
  - `filled`: 完全成交
  - `cancelled`: 已取消
  - `expired`: 已过期
- `filled_quantity`: 已成交数量，用于部分成交场景
- `signal_id`: 如果订单来自交易信号，关联信号ID

**使用示例**：
```sql
-- 查询待成交订单
SELECT 
    symbol, name, order_type, action, 
    price, quantity, created_at
FROM quant.orders
WHERE status IN ('pending', 'partial')
ORDER BY created_at ASC;

-- 查询今日已成交订单
SELECT 
    symbol, name, action, quantity, 
    avg_filled_price, reason
FROM quant.orders
WHERE status = 'filled' 
  AND DATE(updated_at) = CURRENT_DATE;

-- 订单成交率统计
SELECT 
    status,
    COUNT(*) as order_count,
    SUM(quantity) as total_quantity,
    SUM(filled_quantity) as filled_quantity
FROM quant.orders
GROUP BY status;
```


---

## 第三部分：策略回测层

### 10. quant.backtest_results - 回测结果表

存储策略回测的结果和性能指标。

```sql
CREATE TABLE quant.backtest_results (
    id BIGSERIAL PRIMARY KEY,
    strategy_name TEXT NOT NULL,                -- 策略名称
    symbol TEXT,                                -- 股票代码（NULL表示全市场回测）
    start_date DATE NOT NULL,                   -- 回测开始日期
    end_date DATE NOT NULL,                     -- 回测结束日期
    initial_capital DOUBLE PRECISION NOT NULL,  -- 初始资金
    final_capital DOUBLE PRECISION NOT NULL,    -- 最终资金
    total_return DOUBLE PRECISION,              -- 总收益率（%）
    annual_return DOUBLE PRECISION,             -- 年化收益率（%）
    sharpe_ratio DOUBLE PRECISION,              -- 夏普比率
    max_drawdown DOUBLE PRECISION,              -- 最大回撤（%）
    win_rate DOUBLE PRECISION,                  -- 胜率（%）
    total_trades INTEGER,                       -- 总交易次数
    winning_trades INTEGER,                     -- 盈利交易次数
    losing_trades INTEGER,                      -- 亏损交易次数
    avg_win DOUBLE PRECISION,                   -- 平均盈利
    avg_loss DOUBLE PRECISION,                  -- 平均亏损
    profit_factor DOUBLE PRECISION,             -- 盈亏比
    parameters JSONB,                           -- 策略参数（JSON格式）
    equity_curve JSONB,                         -- 资金曲线数据
    trade_details JSONB,                        -- 交易明细
    created_at TIMESTAMPTZ DEFAULT now()
);

-- 索引
CREATE INDEX idx_quant_backtest_results_strategy_name 
    ON quant.backtest_results(strategy_name);
CREATE INDEX idx_quant_backtest_results_symbol 
    ON quant.backtest_results(symbol);
CREATE INDEX idx_quant_backtest_results_created_at_desc 
    ON quant.backtest_results(created_at DESC);
CREATE INDEX idx_quant_backtest_results_sharpe_ratio 
    ON quant.backtest_results(sharpe_ratio DESC);
```

**字段说明**：
- `symbol`: NULL表示全市场回测，非NULL表示单只股票回测
- `total_return`: 总收益率 = (final_capital - initial_capital) / initial_capital × 100
- `annual_return`: 年化收益率
- `sharpe_ratio`: 夏普比率，衡量风险调整后收益
- `max_drawdown`: 最大回撤，从峰值到谷底的最大跌幅
- `win_rate`: 胜率 = winning_trades / total_trades × 100
- `profit_factor`: 盈亏比 = 总盈利 / 总亏损
- `parameters`: 策略参数，如 {"ma_short": 5, "ma_long": 20}
- `equity_curve`: 资金曲线，如 [{"date": "2026-01-01", "equity": 100000}, ...]

**使用示例**：
```sql
-- 查询最佳回测结果（按夏普比率）
SELECT 
    strategy_name, symbol, 
    total_return, annual_return, sharpe_ratio, 
    max_drawdown, win_rate
FROM quant.backtest_results
WHERE sharpe_ratio IS NOT NULL
ORDER BY sharpe_ratio DESC
LIMIT 10;

-- 比较不同策略的表现
SELECT 
    strategy_name,
    COUNT(*) as backtest_count,
    AVG(total_return) as avg_return,
    AVG(sharpe_ratio) as avg_sharpe,
    AVG(max_drawdown) as avg_drawdown
FROM quant.backtest_results
GROUP BY strategy_name
ORDER BY avg_sharpe DESC;

-- 查询某策略的参数优化结果
SELECT 
    parameters->>'ma_short' as ma_short,
    parameters->>'ma_long' as ma_long,
    total_return,
    sharpe_ratio
FROM quant.backtest_results
WHERE strategy_name = 'ma_crossover'
ORDER BY sharpe_ratio DESC;
```

---

### 11. quant.strategy_configs - 策略配置表

存储策略的配置和参数。

```sql
CREATE TABLE quant.strategy_configs (
    id BIGSERIAL PRIMARY KEY,
    strategy_name TEXT NOT NULL UNIQUE,         -- 策略名称（唯一）
    description TEXT,                           -- 策略描述
    strategy_type TEXT NOT NULL,                -- 策略类型（trend/mean_reversion/arbitrage等）
    parameters JSONB NOT NULL,                  -- 策略参数
    risk_params JSONB,                          -- 风险参数（止损、止盈、仓位等）
    is_active BOOLEAN DEFAULT TRUE,             -- 是否启用
    version TEXT DEFAULT '1.0',                 -- 版本号
    author TEXT,                                -- 作者
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

-- 索引
CREATE INDEX idx_quant_strategy_configs_is_active 
    ON quant.strategy_configs(is_active);
CREATE INDEX idx_quant_strategy_configs_strategy_type 
    ON quant.strategy_configs(strategy_type);
```

**字段说明**：
- `strategy_name`: 策略唯一标识，如 "ma_crossover_v2"
- `strategy_type`: 策略类型
  - `trend`: 趋势跟踪
  - `mean_reversion`: 均值回归
  - `arbitrage`: 套利
  - `momentum`: 动量
  - `value`: 价值投资
- `parameters`: 策略参数，如：
  ```json
  {
    "ma_short": 5,
    "ma_long": 20,
    "rsi_threshold": 70,
    "volume_filter": true
  }
  ```
- `risk_params`: 风险参数，如：
  ```json
  {
    "stop_loss": 0.05,
    "take_profit": 0.15,
    "max_position_size": 0.1,
    "max_drawdown": 0.2
  }
  ```

**使用示例**：
```sql
-- 查询所有启用的策略
SELECT 
    strategy_name, description, strategy_type, 
    parameters, is_active
FROM quant.strategy_configs
WHERE is_active = TRUE;

-- 更新策略参数
UPDATE quant.strategy_configs
SET parameters = '{"ma_short": 10, "ma_long": 30}'::jsonb,
    updated_at = now()
WHERE strategy_name = 'ma_crossover';

-- 禁用某个策略
UPDATE quant.strategy_configs
SET is_active = FALSE, updated_at = now()
WHERE strategy_name = 'old_strategy';
```


---

## 第四部分：风险管理层

### 12. quant.account_balance - 账户资金表

记录每日账户资金状态和盈亏情况。

```sql
CREATE TABLE quant.account_balance (
    id BIGSERIAL PRIMARY KEY,
    balance_date DATE NOT NULL UNIQUE,          -- 日期（唯一）
    cash DOUBLE PRECISION NOT NULL,             -- 现金余额
    market_value DOUBLE PRECISION NOT NULL,     -- 持仓市值
    total_assets DOUBLE PRECISION NOT NULL,     -- 总资产 = cash + market_value
    daily_pnl DOUBLE PRECISION,                 -- 当日盈亏
    daily_return DOUBLE PRECISION,              -- 当日收益率（%）
    total_pnl DOUBLE PRECISION,                 -- 累计盈亏
    total_return DOUBLE PRECISION,              -- 累计收益率（%）
    position_count INTEGER DEFAULT 0,           -- 持仓股票数量
    created_at TIMESTAMPTZ DEFAULT now()
);

-- 索引
CREATE INDEX idx_quant_account_balance_date_desc 
    ON quant.account_balance(balance_date DESC);
```

**字段说明**：
- `balance_date`: 日期，唯一约束，每天只有一条记录
- `cash`: 可用现金
- `market_value`: 所有持仓的市值总和
- `total_assets`: 总资产 = 现金 + 持仓市值
- `daily_pnl`: 当日盈亏 = 今日总资产 - 昨日总资产
- `daily_return`: 当日收益率 = daily_pnl / 昨日总资产 × 100
- `total_pnl`: 累计盈亏 = 当前总资产 - 初始资金
- `total_return`: 累计收益率 = total_pnl / 初始资金 × 100

**使用示例**：
```sql
-- 查询最近30天的资金曲线
SELECT 
    balance_date, total_assets, daily_pnl, 
    daily_return, total_return
FROM quant.account_balance
ORDER BY balance_date DESC
LIMIT 30;

-- 计算最大回撤
WITH equity AS (
    SELECT 
        balance_date,
        total_assets,
        MAX(total_assets) OVER (ORDER BY balance_date) as peak
    FROM quant.account_balance
)
SELECT 
    MAX((peak - total_assets) / peak * 100) as max_drawdown
FROM equity;

-- 统计月度收益
SELECT 
    DATE_TRUNC('month', balance_date) as month,
    MIN(total_assets) as month_start,
    MAX(total_assets) as month_end,
    (MAX(total_assets) - MIN(total_assets)) / MIN(total_assets) * 100 as monthly_return
FROM quant.account_balance
GROUP BY DATE_TRUNC('month', balance_date)
ORDER BY month DESC;
```

---

### 13. quant.risk_metrics - 风险指标表

记录投资组合的风险指标。

```sql
CREATE TABLE quant.risk_metrics (
    id BIGSERIAL PRIMARY KEY,
    metric_date DATE NOT NULL,                  -- 指标日期
    symbol TEXT,                                -- 股票代码（NULL表示整体组合）
    volatility DOUBLE PRECISION,                -- 波动率（年化）
    beta DOUBLE PRECISION,                      -- Beta值（相对市场）
    var_95 DOUBLE PRECISION,                    -- 95% VaR（风险价值）
    cvar_95 DOUBLE PRECISION,                   -- 95% CVaR（条件风险价值）
    max_position_ratio DOUBLE PRECISION,        -- 最大持仓比例（%）
    concentration_risk DOUBLE PRECISION,        -- 集中度风险（HHI指数）
    sector_exposure JSONB,                      -- 板块暴露度
    correlation_matrix JSONB,                   -- 相关性矩阵
    created_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE(metric_date, symbol)
);

-- 索引
CREATE INDEX idx_quant_risk_metrics_date_desc 
    ON quant.risk_metrics(metric_date DESC);
CREATE INDEX idx_quant_risk_metrics_symbol 
    ON quant.risk_metrics(symbol);
```

**字段说明**：
- `symbol`: NULL表示整体组合风险，非NULL表示单只股票风险
- `volatility`: 波动率（年化），衡量价格波动程度
- `beta`: Beta值，衡量相对市场的系统性风险
  - β > 1: 比市场波动大
  - β = 1: 与市场同步
  - β < 1: 比市场波动小
- `var_95`: 95%置信度下的VaR（Value at Risk），预期最大损失
- `cvar_95`: 95%置信度下的CVaR（Conditional VaR），超过VaR的平均损失
- `max_position_ratio`: 单只股票占总资产的最大比例
- `concentration_risk`: 集中度风险，使用HHI指数（Herfindahl-Hirschman Index）
- `sector_exposure`: 板块暴露度，如：
  ```json
  {
    "金融": 0.25,
    "科技": 0.30,
    "消费": 0.20,
    "医药": 0.15,
    "其他": 0.10
  }
  ```

**使用示例**：
```sql
-- 查询最新的组合风险指标
SELECT 
    metric_date, volatility, beta, var_95, 
    max_position_ratio, concentration_risk
FROM quant.risk_metrics
WHERE symbol IS NULL
ORDER BY metric_date DESC
LIMIT 1;

-- 查询高风险股票（波动率 > 30%）
SELECT 
    r.symbol, s.name, r.volatility, r.beta
FROM quant.risk_metrics r
LEFT JOIN quant.stocks s ON r.symbol = s.symbol
WHERE r.symbol IS NOT NULL 
  AND r.volatility > 0.30
  AND r.metric_date = (SELECT MAX(metric_date) FROM quant.risk_metrics)
ORDER BY r.volatility DESC;

-- 板块暴露度分析
SELECT 
    metric_date,
    sector_exposure
FROM quant.risk_metrics
WHERE symbol IS NULL
ORDER BY metric_date DESC
LIMIT 1;
```

---

## 第五部分：执行记录层

### 14. quant.signal_executions - 信号执行记录表

存储交易信号的执行情况和盈亏。

```sql
CREATE TABLE quant.signal_executions (
    id BIGSERIAL PRIMARY KEY,
    signal_id BIGINT NOT NULL REFERENCES quant.trading_signals(id) ON DELETE CASCADE,
    execution_date DATE NOT NULL,               -- 执行日期
    execution_price DOUBLE PRECISION NOT NULL,  -- 执行价格
    quantity INTEGER NOT NULL,                  -- 数量
    commission DOUBLE PRECISION,                -- 手续费
    status TEXT NOT NULL CHECK (status IN ('pending', 'executed', 'cancelled', 'expired')),
    pnl DOUBLE PRECISION,                       -- 盈亏
    pnl_pct DOUBLE PRECISION,                   -- 盈亏比例（%）
    close_date DATE,                            -- 平仓日期
    close_price DOUBLE PRECISION,               -- 平仓价格
    holding_days INTEGER,                       -- 持有天数
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

-- 索引
CREATE INDEX idx_quant_signal_executions_signal_id 
    ON quant.signal_executions(signal_id);
CREATE INDEX idx_quant_signal_executions_execution_date_desc 
    ON quant.signal_executions(execution_date DESC);
CREATE INDEX idx_quant_signal_executions_status 
    ON quant.signal_executions(status);
```

**字段说明**：
- `status`: 执行状态
  - `pending`: 待执行
  - `executed`: 已执行
  - `cancelled`: 已取消
  - `expired`: 已过期
- `pnl`: 盈亏金额（平仓后计算）
- `pnl_pct`: 盈亏比例 = (close_price - execution_price) / execution_price × 100
- `holding_days`: 持有天数 = close_date - execution_date

**使用示例**：
```sql
-- 查询已平仓的交易及盈亏
SELECT 
    s.symbol, st.name, 
    e.execution_date, e.execution_price,
    e.close_date, e.close_price,
    e.holding_days, e.pnl, e.pnl_pct
FROM quant.signal_executions e
LEFT JOIN quant.trading_signals s ON e.signal_id = s.id
LEFT JOIN quant.stocks st ON s.symbol = st.symbol
WHERE e.status = 'executed' AND e.pnl IS NOT NULL
ORDER BY e.close_date DESC;

-- 计算胜率和盈亏比
SELECT 
    COUNT(*) as total_trades,
    SUM(CASE WHEN pnl > 0 THEN 1 ELSE 0 END) as winning_trades,
    SUM(CASE WHEN pnl > 0 THEN 1 ELSE 0 END)::FLOAT / COUNT(*) as win_rate,
    AVG(CASE WHEN pnl > 0 THEN pnl END) as avg_win,
    AVG(CASE WHEN pnl < 0 THEN pnl END) as avg_loss,
    SUM(pnl) as total_pnl
FROM quant.signal_executions
WHERE status = 'executed' AND pnl IS NOT NULL;
```


---

## 完整表关系图

```
┌─────────────────────────────────────────────────────────────────────────┐
│                          核心数据层（6张表）                              │
└─────────────────────────────────────────────────────────────────────────┘

                        quant.stocks (股票基础信息)
                               │
                ┌──────────────┼──────────────┬──────────────┐
                │              │              │              │
                ↓              ↓              ↓              ↓
    quant.daily_klines  quant.minute_klines  quant.factor_values  quant.trading_signals
    (日K线数据)         (分钟K线数据)         (因子值)              (交易信号)
                                                                    │
                                                    ┌───────────────┼───────────────┐
                                                    ↓               ↓               ↓
                                            quant.signal_factors  quant.signal_executions
                                            (信号因子详情)         (信号执行记录)

┌─────────────────────────────────────────────────────────────────────────┐
│                          交易执行层（3张表）                              │
└─────────────────────────────────────────────────────────────────────────┘

                        quant.stocks (股票基础信息)
                               │
                ┌──────────────┼──────────────┐
                │              │              │
                ↓              ↓              ↓
    quant.portfolio_holdings  quant.trades  quant.orders
    (持仓表)                  (交易记录)     (订单表)
                                   ↑
                                   │ (关联)
                              quant.orders.order_id

┌─────────────────────────────────────────────────────────────────────────┐
│                          策略回测层（2张表）                              │
└─────────────────────────────────────────────────────────────────────────┘

    quant.strategy_configs ──→ quant.backtest_results
    (策略配置)                  (回测结果)
         │                           │
         └───────────────────────────┘
              (strategy_name关联)

┌─────────────────────────────────────────────────────────────────────────┐
│                          风险管理层（2张表）                              │
└─────────────────────────────────────────────────────────────────────────┘

    quant.account_balance          quant.risk_metrics
    (账户资金)                      (风险指标)
         │                               │
         └───────────────┬───────────────┘
                         │
                    (按日期关联)
```

---

## 数据流转全景图

```
┌─────────────────────────────────────────────────────────────────────────┐
│ 1. 数据采集阶段                                                          │
└─────────────────────────────────────────────────────────────────────────┘

外部数据源 (Tushare/AKShare)
    │
    ├─→ 股票基础信息 → quant.stocks
    ├─→ 日K线数据 → quant.daily_klines
    └─→ 分钟K线数据 → quant.minute_klines

┌─────────────────────────────────────────────────────────────────────────┐
│ 2. 因子计算阶段                                                          │
└─────────────────────────────────────────────────────────────────────────┘

quant.daily_klines
    │
    ↓ (FactorStage)
quant.factor_values (MA, RSI, MACD, Bollinger, ATR等)

┌─────────────────────────────────────────────────────────────────────────┐
│ 3. 信号生成阶段                                                          │
└─────────────────────────────────────────────────────────────────────────┘

quant.factor_values + quant.strategy_configs
    │
    ↓ (ModelStage)
quant.trading_signals + quant.signal_factors

┌─────────────────────────────────────────────────────────────────────────┐
│ 4. 交易执行阶段                                                          │
└─────────────────────────────────────────────────────────────────────────┘

quant.trading_signals
    │
    ↓ (订单生成)
quant.orders
    │
    ↓ (订单执行)
quant.trades + quant.portfolio_holdings
    │
    ↓ (执行记录)
quant.signal_executions

┌─────────────────────────────────────────────────────────────────────────┐
│ 5. 风险监控阶段                                                          │
└─────────────────────────────────────────────────────────────────────────┘

quant.portfolio_holdings + quant.daily_klines
    │
    ↓ (每日结算)
quant.account_balance
    │
    ↓ (风险计算)
quant.risk_metrics

┌─────────────────────────────────────────────────────────────────────────┐
│ 6. 回测分析阶段                                                          │
└─────────────────────────────────────────────────────────────────────────┘

quant.strategy_configs + 历史数据
    │
    ↓ (回测引擎)
quant.backtest_results
```

---

## 数据库初始化脚本

```sql
-- 创建schema
CREATE SCHEMA IF NOT EXISTS quant;

-- 按顺序创建所有表（考虑外键依赖）

-- 1. 核心表：stocks（无依赖）
CREATE TABLE quant.stocks (...);

-- 2. 依赖stocks的表
CREATE TABLE quant.daily_klines (...);
CREATE TABLE quant.minute_klines (...);
CREATE TABLE quant.factor_values (...);
CREATE TABLE quant.portfolio_holdings (...);
CREATE TABLE quant.trades (...);
CREATE TABLE quant.orders (...);

-- 3. 信号相关表
CREATE TABLE quant.trading_signals (...);
CREATE TABLE quant.signal_factors (...);
CREATE TABLE quant.signal_executions (...);

-- 4. 策略和回测表（无依赖）
CREATE TABLE quant.strategy_configs (...);
CREATE TABLE quant.backtest_results (...);

-- 5. 风险管理表（无依赖）
CREATE TABLE quant.account_balance (...);
CREATE TABLE quant.risk_metrics (...);

-- 创建所有索引
-- （见各表定义中的索引部分）
```

---

## 常用联合查询示例

### 1. 持仓盈亏分析（实时）

```sql
SELECT 
    h.symbol,
    h.name,
    h.quantity,
    h.avg_cost,
    k.close as current_price,
    (k.close - h.avg_cost) * h.quantity as unrealized_pnl,
    ((k.close - h.avg_cost) / h.avg_cost) * 100 as return_pct,
    h.sector,
    h.buy_reason
FROM quant.portfolio_holdings h
LEFT JOIN LATERAL (
    SELECT close FROM quant.daily_klines 
    WHERE symbol = h.symbol 
    ORDER BY trade_date DESC 
    LIMIT 1
) k ON TRUE
ORDER BY unrealized_pnl DESC;
```

### 2. 信号执行效果分析

```sql
SELECT 
    s.strategy_name,
    s.signal_type,
    COUNT(*) as signal_count,
    COUNT(e.id) as executed_count,
    AVG(e.pnl) as avg_pnl,
    SUM(CASE WHEN e.pnl > 0 THEN 1 ELSE 0 END)::FLOAT / COUNT(e.id) as win_rate
FROM quant.trading_signals s
LEFT JOIN quant.signal_executions e ON s.id = e.signal_id
WHERE e.status = 'executed' AND e.pnl IS NOT NULL
GROUP BY s.strategy_name, s.signal_type
ORDER BY avg_pnl DESC;
```

### 3. 板块配置与风险暴露

```sql
SELECT 
    h.sector,
    COUNT(*) as stock_count,
    SUM(h.quantity * k.close) as sector_value,
    SUM(h.quantity * k.close) / (SELECT SUM(quantity * close) 
        FROM quant.portfolio_holdings ph
        LEFT JOIN LATERAL (
            SELECT close FROM quant.daily_klines 
            WHERE symbol = ph.symbol 
            ORDER BY trade_date DESC LIMIT 1
        ) kk ON TRUE
    ) * 100 as sector_ratio
FROM quant.portfolio_holdings h
LEFT JOIN LATERAL (
    SELECT close FROM quant.daily_klines 
    WHERE symbol = h.symbol 
    ORDER BY trade_date DESC 
    LIMIT 1
) k ON TRUE
GROUP BY h.sector
ORDER BY sector_value DESC;
```

### 4. 策略回测对比

```sql
SELECT 
    strategy_name,
    COUNT(*) as backtest_count,
    AVG(total_return) as avg_return,
    AVG(annual_return) as avg_annual_return,
    AVG(sharpe_ratio) as avg_sharpe,
    AVG(max_drawdown) as avg_drawdown,
    AVG(win_rate) as avg_win_rate
FROM quant.backtest_results
GROUP BY strategy_name
ORDER BY avg_sharpe DESC;
```

### 5. 每日资金与风险监控

```sql
SELECT 
    ab.balance_date,
    ab.total_assets,
    ab.daily_return,
    ab.total_return,
    rm.volatility,
    rm.var_95,
    rm.max_position_ratio,
    rm.concentration_risk
FROM quant.account_balance ab
LEFT JOIN quant.risk_metrics rm 
    ON ab.balance_date = rm.metric_date 
    AND rm.symbol IS NULL
ORDER BY ab.balance_date DESC
LIMIT 30;
```

---

## 数据维护策略

### 1. 数据清理

```sql
-- 清理1年前的分钟K线数据（数据量大）
DELETE FROM quant.minute_klines 
WHERE ts < CURRENT_DATE - INTERVAL '1 year';

-- 清理6个月前的交易信号
DELETE FROM quant.trading_signals 
WHERE signal_date < CURRENT_DATE - INTERVAL '6 months';

-- 清理已取消/过期的订单（保留3个月）
DELETE FROM quant.orders 
WHERE status IN ('cancelled', 'expired')
  AND updated_at < CURRENT_DATE - INTERVAL '3 months';
```

### 2. 数据归档

```sql
-- 归档历史交易记录到归档表
CREATE TABLE quant.trades_archive (LIKE quant.trades INCLUDING ALL);

INSERT INTO quant.trades_archive
SELECT * FROM quant.trades
WHERE trade_date < CURRENT_DATE - INTERVAL '2 years';

DELETE FROM quant.trades
WHERE trade_date < CURRENT_DATE - INTERVAL '2 years';
```

### 3. 定期维护

```sql
-- 每日执行
VACUUM ANALYZE quant.daily_klines;
VACUUM ANALYZE quant.factor_values;
VACUUM ANALYZE quant.trading_signals;

-- 每周执行
REINDEX TABLE quant.daily_klines;
REINDEX TABLE quant.factor_values;

-- 每月执行
VACUUM FULL quant.minute_klines;  -- 回收空间
```

---

## 性能优化建议

### 1. 分区表（大数据量时）

```sql
-- 按月分区minute_klines
CREATE TABLE quant.minute_klines (
    symbol TEXT NOT NULL,
    ts TIMESTAMPTZ NOT NULL,
    ...
) PARTITION BY RANGE (ts);

CREATE TABLE quant.minute_klines_2026_05 
    PARTITION OF quant.minute_klines
    FOR VALUES FROM ('2026-05-01') TO ('2026-06-01');

-- 按年分区daily_klines
CREATE TABLE quant.daily_klines_2026 
    PARTITION OF quant.daily_klines
    FOR VALUES FROM ('2026-01-01') TO ('2027-01-01');
```

### 2. 物化视图（常用查询）

```sql
-- 持仓实时盈亏视图
CREATE MATERIALIZED VIEW quant.mv_portfolio_pnl AS
SELECT 
    h.symbol, h.name, h.quantity, h.avg_cost,
    k.close as current_price,
    (k.close - h.avg_cost) * h.quantity as unrealized_pnl
FROM quant.portfolio_holdings h
LEFT JOIN LATERAL (
    SELECT close FROM quant.daily_klines 
    WHERE symbol = h.symbol 
    ORDER BY trade_date DESC LIMIT 1
) k ON TRUE;

-- 每日刷新
REFRESH MATERIALIZED VIEW quant.mv_portfolio_pnl;
```

### 3. 连接池配置

```python
# 使用pgbouncer或连接池
import psycopg2.pool

connection_pool = psycopg2.pool.SimpleConnectionPool(
    minconn=1,
    maxconn=20,
    dsn=os.environ['QUANT_DATABASE_URL']
)
```

---

## 备份与恢复

### 备份策略

```bash
# 每日全量备份
pg_dump -h localhost -U postgres -Fc quant_investment > backup_$(date +%Y%m%d).dump

# 只备份quant schema
pg_dump -h localhost -U postgres -n quant -Fc quant_investment > quant_$(date +%Y%m%d).dump

# 备份到远程
pg_dump -h localhost -U postgres quant_investment | gzip | ssh backup-server "cat > /backups/quant_$(date +%Y%m%d).sql.gz"
```

### 恢复策略

```bash
# 恢复全量备份
pg_restore -h localhost -U postgres -d quant_investment backup_20260520.dump

# 恢复指定schema
pg_restore -h localhost -U postgres -d quant_investment -n quant quant_20260520.dump

# 恢复指定表
pg_restore -h localhost -U postgres -d quant_investment -t quant.stocks backup_20260520.dump
```

---

## 注意事项

1. **外键约束**：所有子表都有外键约束，删除股票会级联删除相关数据
2. **时区处理**：所有 `TIMESTAMPTZ` 字段使用UTC时区，应用层需要转换
3. **NULL值处理**：财务指标、技术指标可能为NULL，查询时需要处理
4. **事务一致性**：涉及多表操作时使用事务确保数据一致性
5. **索引维护**：定期检查索引使用情况，删除无用索引
6. **数据备份**：建议每日备份，保留至少7天的备份
7. **权限控制**：生产环境应设置合理的用户权限
8. **监控告警**：监控数据库性能指标（连接数、慢查询、磁盘空间）

---

## 相关文档

- [README.md](../README.md) - 项目总览
- [Phase 1 总结](phase1-summary.md) - Phase 1完成情况
- [架构设计](2026-05-20-quant-system-architecture-design.md) - 详细架构设计

---

**文档版本**: v2.0  
**最后更新**: 2026-05-20  
**维护者**: QuantSys Team
