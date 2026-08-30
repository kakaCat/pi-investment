# API 到数据源调用流程图

## 整体架构

```
┌─────────────────────────────────────────────────────────────────────┐
│                        HTTP Client (Agent/前端)                      │
└─────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    FastAPI Routes (/api/provider/*)                  │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐              │
│  │ data_provider│  │ market_data  │  │  dividends   │  ...其他路由   │
│  │   _async.py  │  │  _async.py   │  │  _async.py   │              │
│  └──────────────┘  └──────────────┘  └──────────────┘              │
└─────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      DataProviderManager                            │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │  _try_providers(providers, method, *args, **kwargs)         │  │
│  │  按优先级依次尝试 provider，返回第一个成功的结果               │  │
│  └──────────────────────────────────────────────────────────────┘  │
│                                                                      │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐    │
│  │  Quote Providers │  │  Kline Providers │  │ Financial Providers│  │
│  │  (行情数据)       │  │  (K线数据)       │  │  (财务数据)        │  │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘    │
└─────────────────────────────────────────────────────────────────────┘
                                    │
          ┌─────────────────────────┼─────────────────────────┐
          │                         │                         │
          ▼                         ▼                         ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│ TencentProvider  │    │  SinaProvider   │    │EastmoneyProvider│
│ (腾讯财经qt.gtimg)│    │  (新浪财经)     │    │  (东方财富)      │
└─────────────────┘    └─────────────────┘    └─────────────────┘
          │                         │                         │
          ▼                         ▼                         ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│  腾讯财经API     │    │  新浪财经API     │    │  东方财富API     │
│  qt.gtimg.cn    │    │   (HTTP请求)      │    │  (HTTP请求)      │
└─────────────────┘    └─────────────────┘    └─────────────────┘
          │                         │                         │
          └─────────────────────────┼─────────────────────────┘
                                    ▼
┌─────────────────────────────────────────────────────────────────────┐
│                         外部数据源                                    │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐              │
│  │  腾讯财经      │  │   新浪财经    │  │   东方财富     │              │
│  │  (tencent)    │  │   (sina)     │  │  (eastmoney)  │              │
│  └──────────────┘  └──────────────┘  └──────────────┘              │
└─────────────────────────────────────────────────────────────────────┘
```

## 详细调用流程

### 1. 行情数据 (Quote) 流程

```
GET /api/provider/quote/{symbol}
        │
        ▼
DataProviderManager.get_quote(symbol)
        │
        ▼
_try_providers(quote_providers, 'get_quote', symbol)
        │
        ├─── 尝试1: TencentQuoteProvider.get_quote(symbol) ⭐ 优先
        │           │
        │           ▼
        │    HTTP请求腾讯财经 → qt.gtimg.cn/q={tencent_code}
        │           │
        │           ├── 成功 → 返回 QuoteData
        │           └── 失败 → 尝试下一个
        │
        ├─── 尝试2: SinaQuoteProvider.get_quote(symbol)
        │           │
        │           ▼
        │    HTTP请求新浪财经API → 实时行情
        │           │
        │           ├── 成功 → 返回 QuoteData
        │           └── 失败 → 尝试下一个
        │
        ├─── 尝试3: EastmoneyQuoteProvider.get_quote(symbol)
        │           │
        │           ▼
        │    HTTP请求东方财富 → 实时行情
        │           │
        │           ├── 成功 → 返回 QuoteData
        │           └── 失败 → 尝试下一个
        │
        └─── 尝试4: AkshareQuoteProvider.get_quote(symbol)
                    │
                    ▼
             akshare.stock_zh_a_spot_em() → 东方财富实时行情
                    │
                    ├── 成功 → 返回 QuoteData
                    └── 失败 → 所有源失败，返回错误
```

### 2. K线数据 (Kline) 流程

```
GET /api/provider/kline/{symbol}
        │
        ▼
DataProviderManager.get_klines(symbol, period, start_date, end_date)
        │
        ▼
┌─────────────────────────────────────────────────────────────┐
│  1. 先查数据库 (DatabaseKlineProvider)                        │
│     └── SELECT * FROM daily_klines WHERE symbol = ?          │
│         AND trade_date BETWEEN ? AND ?                       │
│                                                              │
│  2. 检查数据完整性 (Gap Detection)                            │
│     └── if 缺失天数 > 50%:                                   │
│           继续尝试网络源                                      │
│                                                              │
│  3. 网络源获取 (按优先级)                                      │
│     ├── BaostockKlineProvider (BaoStock)                     │
│     ├── TencentKlineProvider (腾讯 ifzq.gtimg.cn) ⭐         │
│     └── AkshareKlineProvider (东方财富)                       │
│                                                              │
│  4. 回写数据库 (Backfill)                                     │
│     └── INSERT INTO daily_klines (...) ON CONFLICT DO UPDATE │
└─────────────────────────────────────────────────────────────┘
        │
        ▼
返回 KlineData (包含 source 字段标识数据来源)
```

### 3. 财务数据 (Financial) 流程

```
GET /api/provider/financial/{symbol}
        │
        ▼
DataProviderManager.get_financial(symbol, report_type)
        │
        ▼
_try_providers(financial_providers, 'get_financial', symbol)
        │
        ├─── 尝试1: SinaFinancialProvider.get_financial(symbol)
        │           │
        │           ▼
        │    SinaWebFinancialProvider.get_financial_statements()
        │           │
        │           ▼
        │    HTTP请求新浪财经 → 三大报表 (利润表/资产负债表/现金流量表)
        │           │
        │           ├── 成功 → 返回 FinancialData
        │           └── 失败 → 尝试下一个
        │
        ├─── 尝试2: EastmoneyFinancialProvider.get_financial(symbol)
        │           │
        │           ▼
        │    EastmoneyDirectProvider.get_financial_statements()
        │           │
        │           ▼
        │    HTTP请求东方财富 → 三大报表
        │           │
        │           ├── 成功 → 返回 FinancialData
        │           └── 失败 → 尝试下一个
        │
        └─── 尝试3: AkshareFinancialStatementProvider.get_financial(symbol)
                    │
                    ▼
             akshare.stock_financial_report_sina() → 三大报表
                    │
                    ├── 成功 → 返回 FinancialData
                    └── 失败 → 返回错误
```

### 4. 板块数据 (Sector) 流程

```
GET /api/provider/sector/{sector}/stocks
        │
        ▼
DataProviderManager.get_sector_stocks(sector)
        │
        ▼
_try_providers(sector_providers, 'get_sector_stocks', sector)
        │
        ├─── 尝试1: EastmoneySectorProvider.get_sector_stocks(sector)
        │           │
        │           ▼
        │    HTTP请求东方财富 → 板块成分股列表
        │           │
        │           ├── 成功 → 返回 MarketData
        │           └── 失败 → 尝试下一个
        │
        └─── 尝试2: AkshareSectorProvider.get_sector_stocks(sector)
                    │
                    ▼
             akshare.stock_board_industry_cons_em() → 行业板块成分股
                    │
                    ├── 成功 → 返回 MarketData
                    └── 失败 → 返回错误
```

### 5. 港股数据 (HK) 流程

```
GET /api/provider/hk/{symbol}/daily
        │
        ▼
DataProviderManager.get_hk_daily(symbol)
        │
        ▼
_try_providers(hk_providers, 'get_hk_daily', symbol)
        │
        ├─── 尝试1: AkshareHKProvider.get_hk_daily(symbol)
        │           │
        │           ▼
        │    akshare.stock_hk_hist() → 港股历史K线
        │           │
        │           ├── 成功 → 返回 KlineData
        │           └── 失败 → 尝试下一个
        │
        └─── 尝试2: SinaHKProvider.get_hk_daily(symbol)
                    │
                    ▼
             HTTP请求新浪财经港股API → 港股K线
                    │
                    ├── 成功 → 返回 KlineData
                    └── 失败 → 返回错误
```

## 数据源优先级配置

```python
# adapters/outbound/datasources/manager.py

# 行情数据源优先级
quote_providers = [
    TencentQuoteProvider(),      # 腾讯财经 (优先, 快速稳定)
    SinaQuoteProvider(),         # 新浪财经 (稳定, 略有延迟)
    EastmoneyQuoteProvider(),    # 东方财富 (不稳定, 连接问题)
    AkshareQuoteProvider(),      # Akshare (很慢, 最后备选)
]

# K线数据源优先级
kline_providers = [
    DatabaseKlineProvider(),     # 数据库 (优先)
    BaostockKlineProvider(),     # BaoStock
    TencentKlineProvider(),      # 腾讯K线
    AkshareKlineProvider(),      # Akshare
]

# 财务数据源优先级
financial_providers = [
    SinaFinancialProvider(),       # 新浪财经网页 (优先)
    EastmoneyFinancialProvider(),  # 东方财富 (备选)
    AkshareFinancialStatementProvider(),  # Akshare (备选)
]

# 板块数据源优先级
sector_providers = [
    EastmoneySectorProvider(),    # 东方财富 (优先)
    AkshareSectorProvider(),      # Akshare (备选)
]
```

## 错误处理流程

```
外部数据源请求失败
        │
        ▼
┌─────────────────────────────────────┐
│  记录错误日志                         │
│  logger.warning(f"Provider failed")  │
└─────────────────────────────────────┘
        │
        ▼
┌─────────────────────────────────────┐
│  尝试下一个 Provider                  │
│  _try_providers() 继续循环           │
└─────────────────────────────────────┘
        │
        ├── 有下一个 → 返回顶部继续尝试
        │
        └── 所有失败 → 返回错误响应
                    │
                    ▼
             {"success": false, 
              "error": "All providers failed",
              "attempted_sources": ["akshare", "sina"]}
```

## 数据库写入流程 (Kline Backfill)

```
网络源获取数据成功
        │
        ▼
┌─────────────────────────────────────┐
│  检查是否需要回写数据库               │
│  _backfill_klines_to_db()           │
└─────────────────────────────────────┘
        │
        ▼
┌─────────────────────────────────────┐
│  转换数据格式                         │
│  KlineData → DailyKline ORM对象      │
│  添加 source 字段标识来源             │
└─────────────────────────────────────┘
        │
        ▼
┌─────────────────────────────────────┐
│  批量插入数据库                       │
│  INSERT INTO daily_klines            │
│  ON CONFLICT (symbol, trade_date)    │
│  DO UPDATE SET ...                   │
└─────────────────────────────────────┘
        │
        ▼
┌─────────────────────────────────────┐
│  返回结果 (包含 source 字段)          │
│  {"source": "akshare", ...}         │
└─────────────────────────────────────┘
```
