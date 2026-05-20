# 可下载的股票数据类型

本文档列出了 pi-investment 系统中所有可用的数据类型和接口。

## 📊 数据分类概览

### 1. **实时行情数据**
- ✅ A股实时价格（分钟级）
- ✅ 港股实时价格
- ✅ 批量实时价格查询
- ✅ 指数实时数据

### 2. **历史K线数据**
- ✅ 日K线（daily）
- ✅ 周K线（weekly）
- ✅ 月K线（monthly）
- ✅ **分时数据**（1分钟、5分钟、15分钟、30分钟、60分钟）
- ✅ 复权选项：前复权(qfq)、后复权(hfq)、不复权

### 3. **基本面数据**
- ✅ 财务指标（ROE、PE、PB、毛利率、负债率等）
- ✅ 财务报表（资产负债表、利润表、现金流量表）
- ✅ 公司基本信息
- ✅ 估值数据（PE百分位、历史估值）
- ✅ 质量评分

### 4. **技术指标**
- ✅ RSI（相对强弱指标）
- ✅ MACD（指数平滑异同移动平均线）
- ✅ 均线（MA5/10/20/60）
- ✅ 布林带（Bollinger Bands）
- ✅ ATR（平均真实波幅）
- ✅ 成交量比率

### 5. **市场数据**
- ✅ 板块列表
- ✅ 概念股列表
- ✅ 热门股票排行
- ✅ 北向资金流向
- ✅ 南向资金流向（港股通）
- ✅ 市场概览

### 6. **新闻与资讯**
- ✅ 个股新闻
- ✅ 市场新闻
- ✅ 公告信息

### 7. **宏观经济数据**
- ✅ GDP数据
- ✅ CPI/PPI
- ✅ PMI指数
- ✅ 利率数据
- ✅ 货币供应量

### 8. **港股数据**
- ✅ 港股实时价格
- ✅ 港股历史K线
- ✅ 港股财务数据
- ✅ 港股技术分析
- ✅ 港股市场概览
- ✅ 港股热门排行

---

## 🔧 详细接口说明

### 实时行情

#### `get_stock_realtime_price(symbol)`
获取A股实时价格
```python
# 返回数据
{
  "symbol": "000001",
  "name": "平安银行",
  "price": 12.34,
  "change": 0.12,
  "change_pct": 0.98,
  "volume": 123456789,
  "amount": 1234567890.0,
  "high": 12.50,
  "low": 12.20,
  "open": 12.30,
  "prev_close": 12.22
}
```

#### `get_batch_realtime_prices(symbols)`
批量获取实时价格
```python
symbols = ["000001", "600000", "600036"]
# 返回多只股票的实时数据数组
```

### 历史K线数据

#### `get_stock_history(symbol, period, start_date, end_date, adjust)`
获取历史K线数据（**支持分时数据**）

**参数说明：**
- `symbol`: 股票代码（如 "000001"）
- `period`: 周期类型
  - `"daily"` - 日K线
  - `"weekly"` - 周K线
  - `"monthly"` - 月K线
  - `"1min"` - 1分钟K线 ⭐
  - `"5min"` - 5分钟K线 ⭐
  - `"15min"` - 15分钟K线 ⭐
  - `"30min"` - 30分钟K线 ⭐
  - `"60min"` - 60分钟K线 ⭐
- `start_date`: 开始日期（格式：YYYY-MM-DD）
- `end_date`: 结束日期（格式：YYYY-MM-DD）
- `adjust`: 复权方式
  - `"qfq"` - 前复权（默认）
  - `"hfq"` - 后复权
  - `""` - 不复权

**返回数据结构：**
```python
{
  "symbol": "000001",
  "period": "5min",
  "data": [
    {
      "date": "2026-05-18 09:35:00",
      "open": 12.30,
      "high": 12.35,
      "low": 12.28,
      "close": 12.33,
      "volume": 1234567,
      "amount": 15234567.0
    },
    # ... 更多K线数据
  ]
}
```

**使用示例：**
```python
# 获取最近一天的5分钟K线
get_stock_history("000001", period="5min", start_date="2026-05-17", end_date="2026-05-18")

# 获取最近一周的1分钟K线
get_stock_history("600000", period="1min", start_date="2026-05-11", end_date="2026-05-18")

# 获取日K线（传统方式）
get_stock_history("600036", period="daily", start_date="2026-01-01", end_date="2026-05-18")
```

### 财务数据

#### `get_financial_indicators(symbol)`
获取财务指标
```python
# 返回数据
{
  "symbol": "000001",
  "roe": 12.5,        # 净资产收益率
  "pe": 8.5,          # 市盈率
  "pb": 0.85,         # 市净率
  "gross_margin": 45.2,  # 毛利率
  "debt_ratio": 0.65,    # 资产负债率
  "current_ratio": 1.2,  # 流动比率
  "quick_ratio": 0.9     # 速动比率
}
```

#### `get_financial_statements(symbol, statement, recent_n)`
获取财务报表
- `statement`: "balance" (资产负债表), "income" (利润表), "cashflow" (现金流量表), "all" (全部)
- `recent_n`: 最近N期报表（默认8期）

### 技术指标

#### `calculate_technical_indicators(symbol)`
计算技术指标
```python
# 返回数据
{
  "symbol": "000001",
  "rsi": 65.5,
  "macd": {
    "dif": 0.12,
    "dea": 0.08,
    "macd": 0.04
  },
  "ma5": 12.30,
  "ma10": 12.25,
  "ma20": 12.15,
  "ma60": 12.00,
  "bollinger": {
    "upper": 12.50,
    "middle": 12.30,
    "lower": 12.10
  }
}
```

### 市场数据

#### `get_sector_list()`
获取板块列表
```python
# 返回所有行业板块
{
  "sectors": ["银行", "证券", "保险", "房地产", ...]
}
```

#### `get_concept_list()`
获取概念列表
```python
# 返回所有概念板块
{
  "concepts": ["人工智能", "新能源", "芯片", ...]
}
```

#### `get_hot_stocks(market)`
获取热门股票
- `market`: "A股", "港股", "美股"

#### `get_north_flow()`
获取北向资金流向（沪深港通）

### 新闻数据

#### `get_stock_news(symbol, num)`
获取个股新闻
- `num`: 新闻条数（默认10条）

#### `get_market_news(num)`
获取市场新闻
- `num`: 新闻条数（默认20条）

### 宏观经济数据

#### `get_macro_data(indicators)`
获取宏观经济数据
```python
indicators = ["GDP", "CPI", "PPI", "PMI"]
# 返回指定指标的最新数据
```

### 港股数据

#### `get_hk_stock_price(symbol)`
获取港股实时价格

#### `get_hk_stock_history(symbol, period, start_date, end_date)`
获取港股历史K线（同样支持分时数据）

#### `get_hk_financials(symbol)`
获取港股财务数据

---

## 📈 量化工具（TypeScript层）

系统还提供了高级量化工具，这些工具在 TypeScript 层实现：

### 1. `manage_quant_strategy`
管理量化策略（创建/列表/启用/禁用/删除）

### 2. `run_backtest`
运行策略回测

### 3. `generate_signals`
生成交易信号（基于策略扫描股票）

### 4. `score_stock`
股票多因子评分

### 5. `train_signal_model`
训练机器学习信号模型

### 6. `get_strategy_performance`
获取策略历史表现统计

---

## 🎯 数据获取方式

### 方式1：直接调用 Python 函数
```python
from python.akshare_bridge import get_stock_history

# 获取5分钟K线
data = get_stock_history("000001", period="5min", start_date="2026-05-18", end_date="2026-05-18")
```

### 方式2：通过 TypeScript 工具
```typescript
import { get_stock_history } from './infrastructure/akshare-ts';

// 获取分时数据
const data = await get_stock_history("000001", "5min", "2026-05-18", "2026-05-18");
```

### 方式3：通过 AI Agent 工具
AI Agent 可以直接调用这些工具来获取数据并进行分析。

---

## ⚠️ 数据限制说明

### 分时数据限制
- **数据范围**：通常只能获取最近几个交易日的分时数据
- **数据量**：单次请求建议不超过1000条K线
- **频率限制**：建议请求间隔 > 1秒，避免被限流

### 历史数据限制
- **日K线**：可获取多年历史数据
- **周/月K线**：可获取完整历史数据
- **分时K线**：通常只有最近5-10个交易日

### 实时数据
- **延迟**：实时数据有15分钟左右延迟（免费接口）
- **更新频率**：建议查询间隔 > 3秒

---

## 📝 使用建议

1. **分时数据适用场景**：
   - 日内交易策略
   - 短线技术分析
   - 盘中监控
   - 高频信号生成

2. **日K线适用场景**：
   - 中长期趋势分析
   - 基本面结合技术面
   - 回测历史策略
   - 因子研究

3. **数据存储**：
   - 系统会自动缓存历史数据到本地数据库
   - 分时数据建议定期清理，避免占用过多空间

4. **性能优化**：
   - 批量查询使用 `get_batch_realtime_prices`
   - 避免频繁请求相同数据
   - 利用本地缓存机制

---

## 🔗 相关文档

- [AkShare 官方文档](https://akshare.akfamily.xyz/)
- [项目架构说明](../memory/architecture-services.md)
- [数据层实现](../memory/akshare-ts-data-layer.md)

---

**最后更新**: 2026-05-18
