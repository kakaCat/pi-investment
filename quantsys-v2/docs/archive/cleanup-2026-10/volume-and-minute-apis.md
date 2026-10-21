# quantsys-v2 交易量和实时分钟级数据接口列表

## 📊 提供交易量 (Volume) 的接口

### 1. 实时行情接口 (带交易量)
**端点**: `GET /api/stock/<symbol>/quote`

**参数**:
- `source`: realtime | db | auto (默认: realtime)

**返回数据**:
```json
{
  "symbol": "600519",
  "name": "贵州茅台",
  "price": 1650.0,
  "open": 1640.0,
  "high": 1660.0,
  "low": 1635.0,
  "prev_close": 1645.0,
  "volume": 12345678,      // ✓ 成交量
  "amount": 2034567890.0,  // ✓ 成交额
  "change": 5.0,
  "change_pct": 0.30,
  "source": "sina",
  "timestamp": "2024-01-01T10:30:00"
}
```

**数据源**: sina → eastmoney → akshare → tencent → netease (多数据源自动降级)

---

### 2. K线历史数据接口 (带交易量) ⭐ 新增多数据源支持
**端点**: `GET /api/stock/<symbol>/history`

**参数**:
- `period`: daily | weekly | monthly | 1m | 5m | 15m | 30m | 60m
- `start_date`: YYYY-MM-DD
- `end_date`: YYYY-MM-DD
- `limit`: 数据点数 (默认60, 最大200)
- `source`: auto | db | akshare (默认: auto)

**返回数据**:
```json
{
  "symbol": "600519",
  "period": "daily",
  "count": 10,
  "source": "database",  // 标识实际数据源
  "data": [
    {
      "date": "2024-01-01",
      "open": 1640.0,
      "high": 1660.0,
      "low": 1635.0,
      "close": 1650.0,
      "volume": 12345678,  // ✓ 成交量
      "change_pct": 0.30
    }
  ]
}
```

**数据源**: 
- 日/周/月线: database → akshare (自动降级)
- 分钟线: akshare (实时)

**支持周期**:
- 日线: daily, weekly, monthly
- 分钟线: 1m, 5m, 15m, 30m, 60m ✓

---

### 3. K线数据接口 (旧版，带交易量)
**端点**: `GET /api/stock/<symbol>/klines`

**参数**:
- `period`: daily | 1d | 1m | 5m | 15m | 30m | 60m
- `start_date`: YYYY-MM-DD
- `end_date`: YYYY-MM-DD
- `limit`: 数据点数 (默认100)

**返回数据**:
```json
{
  "symbol": "600519",
  "data": [
    {
      "trade_date": "2024-01-01",
      "open": 1640.0,
      "high": 1660.0,
      "low": 1635.0,
      "close": 1650.0,
      "volume": 12345678,  // ✓ 成交量
      "amount": 2034567890.0  // ✓ 成交额
    }
  ]
}
```

**数据源**: 
- 日线: database (ds.kline.get_daily_klines)
- 分钟线: database (ds.kline.get_minute_klines)

**支持周期**: daily, 1m, 5m, 15m, 30m, 60m ✓

---

### 4. 批量行情接口 (带交易量)
**端点**: `POST /api/stocks/batch-quotes`

**请求体**:
```json
{
  "symbols": ["600519", "000001", "600036"]
}
```

**返回数据**:
```json
{
  "data": {
    "600519": {
      "symbol": "600519",
      "name": "贵州茅台",
      "price": 1650.0,
      "volume": 12345678,  // ✓ 成交量
      "amount": 2034567890.0,  // ✓ 成交额
      ...
    }
  }
}
```

---

## ⏱️ 实时分钟级数据接口

### 1. K线历史数据接口 - 分钟线 ⭐ 推荐
**端点**: `GET /api/stock/<symbol>/history`

**分钟级周期**:
- `period=1m`: 1分钟线
- `period=5m`: 5分钟线
- `period=15m`: 15分钟线
- `period=30m`: 30分钟线
- `period=60m`: 60分钟线

**示例**:
```bash
# 获取最近2天的5分钟K线
curl "http://127.0.0.1:5001/api/stock/600519/history?period=5m&limit=100"
```

**特点**:
- ✅ 支持多数据源降级
- ✅ 返回 source 字段标识数据来源
- ✅ 自动处理日期范围
- ✅ 包含完整的 OHLCV 数据

**数据源**: akshare (实时API)

---

### 2. K线数据接口 - 分钟线 (旧版)
**端点**: `GET /api/stock/<symbol>/klines`

**分钟级周期**: 1m, 5m, 15m, 30m, 60m

**示例**:
```bash
curl "http://127.0.0.1:5001/api/stock/600519/klines?period=5m&limit=100"
```

**数据源**: database (ds.kline.get_minute_klines)

---

## 📋 接口对比总结

| 接口 | 交易量 | 分钟级 | 多数据源 | 推荐 |
|------|--------|--------|----------|------|
| `/api/stock/<symbol>/quote` | ✅ | ❌ | ✅ | ✅ 实时行情 |
| `/api/stock/<symbol>/history` | ✅ | ✅ | ✅ | ⭐ 最推荐 |
| `/api/stock/<symbol>/klines` | ✅ | ✅ | ❌ | ⚠️ 旧版 |
| `/api/stocks/batch-quotes` | ✅ | ❌ | ✅ | ✅ 批量查询 |

---

## 🎯 使用建议

### 获取实时行情 + 交易量
```bash
curl "http://127.0.0.1:5001/api/stock/600519/quote?source=auto"
```

### 获取日K线 + 交易量
```bash
curl "http://127.0.0.1:5001/api/stock/600519/history?period=daily&limit=30"
```

### 获取5分钟K线 + 交易量
```bash
curl "http://127.0.0.1:5001/api/stock/600519/history?period=5m&limit=50"
```

### 批量获取多只股票行情 + 交易量
```bash
curl -X POST "http://127.0.0.1:5001/api/stocks/batch-quotes" \
  -H "Content-Type: application/json" \
  -d '{"symbols": ["600519", "000001"]}'
```

---

## ⚠️ 注意事项

1. **分钟级数据限制**:
   - 通常只提供最近几天的数据（如最近30天）
   - AkShare API 可能有速率限制

2. **交易时间**:
   - 实时数据仅在交易时段有效
   - 非交易时段会自动降级到数据库历史数据

3. **数据源**:
   - `/api/stock/<symbol>/history` 使用多数据源，最可靠 ⭐
   - 返回的 `source` 字段告诉你实际使用的数据源

4. **推荐使用**:
   - **首选**: `/api/stock/<symbol>/history` (支持所有周期 + 多数据源)
   - **备选**: `/api/stock/<symbol>/quote` (仅实时快照)

---

## 🔗 相关文档

- [K线多数据源架构](./multi-source-kline.md)
- [API 完整文档](../README.md)
- TypeScript 集成: `agent-ts/src/infrastructure/tools/data/fetch-kline-tool.ts`
