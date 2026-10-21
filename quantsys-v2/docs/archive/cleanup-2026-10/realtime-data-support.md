# quantsys-v2 实时数据支持说明

## ✅ 是的，v2 项目完全支持实时数据

---

## 📊 实时数据架构

### 核心服务
```
RealtimeQuoteService
    ↓
DataProviderManager
    ↓
多个实时数据源 Provider (自动降级)
```

### 实时数据源列表

quantsys-v2 支持 **5个实时数据源**，按优先级排序：

1. **Sina (新浪财经)** - `sina.py`
   - API: `https://hq.sinajs.cn/list={symbol}`
   - 延迟: < 3秒
   - 支持: A股 + 港股

2. **Eastmoney (东方财富)** - `eastmoney.py`
   - API: 东方财富网实时行情接口
   - 延迟: < 3秒
   - 支持: A股

3. **AkShare** - `akshare.py`
   - API: AkShare Python库
   - 延迟: 3-5秒
   - 支持: A股 + 港股

4. **Tencent (腾讯财经)** - `tencent.py`
   - API: 腾讯财经实时行情接口
   - 延迟: < 3秒
   - 支持: A股

5. **Netease (网易财经)** - `netease.py`
   - API: 网易财经实时行情接口
   - 延迟: < 5秒
   - 支持: A股

---

## 🔄 自动降级机制

当一个数据源失败时，自动尝试下一个：

```
Sina 失败
  ↓
Eastmoney 失败
  ↓
AkShare 失败
  ↓
Tencent 失败
  ↓
Netease 失败
  ↓
返回错误 (或 auto 模式下降级到数据库)
```

---

## 📡 实时数据 API

### 1. 实时行情快照
**端点**: `GET /api/stock/<symbol>/quote`

**参数**:
- `source`: 
  - `realtime` - 仅实时数据，失败返回错误
  - `db` - 仅数据库历史数据
  - `auto` - 实时优先，失败降级到数据库 (默认)

**示例**:
```bash
# 获取实时行情
curl "http://127.0.0.1:5001/api/stock/600519/quote?source=realtime"
```

**返回**:
```json
{
  "symbol": "600519",
  "name": "贵州茅台",
  "price": 1650.0,           // 实时价格
  "open": 1640.0,
  "high": 1660.0,
  "low": 1635.0,
  "prev_close": 1645.0,
  "volume": 12345678,        // 实时成交量
  "amount": 2034567890.0,    // 实时成交额
  "change": 5.0,
  "change_pct": 0.30,
  "source": "sina",          // 标识实际数据源
  "timestamp": "2024-01-01T14:30:15"  // 实时时间戳
}
```

---

### 2. 实时分钟K线
**端点**: `GET /api/stock/<symbol>/history`

**参数**:
- `period`: 1m, 5m, 15m, 30m, 60m
- `limit`: 数据点数

**示例**:
```bash
# 获取最近的5分钟K线（实时更新）
curl "http://127.0.0.1:5001/api/stock/600519/history?period=5m&limit=50"
```

**数据源**: AkShare (实时API)

---

## ⏰ 实时性说明

### 延迟级别

| 数据源 | 延迟 | 更新频率 |
|--------|------|----------|
| Sina | < 3秒 | 3秒/次 |
| Eastmoney | < 3秒 | 3秒/次 |
| Tencent | < 3秒 | 3秒/次 |
| Netease | < 5秒 | 5秒/次 |
| AkShare | 3-5秒 | 5秒/次 |

### 交易时间范围

**A股交易时间** (所有实时数据源仅在此时段有效):
- 周一至周五
- 上午: 9:30 - 11:30
- 下午: 13:00 - 15:00
- 节假日休市

**非交易时段行为**:
- `source=realtime`: 返回错误或空数据
- `source=auto`: 自动降级到数据库最近收盘价
- `source=db`: 直接返回数据库数据

---

## 🎯 使用场景

### 1. 获取当前实时价格
```bash
# 推荐：auto 模式（交易时段返回实时，非交易时段返回收盘价）
curl "http://127.0.0.1:5001/api/stock/600519/quote?source=auto"
```

### 2. 仅获取实时数据（不要历史数据）
```bash
# realtime 模式（非交易时段会返回错误）
curl "http://127.0.0.1:5001/api/stock/600519/quote?source=realtime"
```

### 3. 批量获取实时行情
```bash
curl -X POST "http://127.0.0.1:5001/api/stocks/batch-quotes" \
  -H "Content-Type: application/json" \
  -d '{"symbols": ["600519", "000001", "600036"]}'
```

### 4. 实时分钟级监控
```bash
# 持续获取最新5分钟K线
while true; do
  curl "http://127.0.0.1:5001/api/stock/600519/history?period=5m&limit=1"
  sleep 300  # 每5分钟刷新
done
```

---

## 🔍 健康监控

### 查看数据源健康状态

```python
from application.services.realtime_quote_service import RealtimeQuoteService

service = RealtimeQuoteService()
health = service.get_provider_health()

# 返回示例:
# {
#   "sina": {"success": 150, "failure": 5},
#   "eastmoney": {"success": 10, "failure": 2},
#   "akshare": {"success": 5, "failure": 1},
#   "tencent": {"success": 3, "failure": 0},
#   "netease": {"success": 2, "failure": 1}
# }
```

---

## 🆚 实时 vs 数据库

| 特性 | 实时数据 | 数据库数据 |
|------|----------|-----------|
| 延迟 | 3-5秒 | 静态（最近收盘） |
| 可用时间 | 交易时段 | 7x24 |
| 数据源 | 5个网络API | PostgreSQL |
| 可靠性 | 中（网络依赖） | 高 |
| 成本 | API调用 | 存储 |
| 适用场景 | 实时监控、下单 | 历史分析、回测 |

---

## ⚠️ 注意事项

1. **速率限制**:
   - 新浪财经、东方财富等有隐式的速率限制
   - 建议不要在1秒内请求超过10次

2. **网络波动**:
   - 实时数据依赖外部API，可能因网络问题失败
   - 使用 `source=auto` 模式自动降级

3. **数据准确性**:
   - 免费实时数据可能有延迟或不准确
   - 对精度要求高的场景建议使用付费数据源

4. **交易时段判断**:
   - API 端点会自动判断是否在交易时段
   - 非交易时段 `source=realtime` 会失败

---

## 🚀 TypeScript Agent 集成

TypeScript Agent 端通过工具自动使用实时数据：

```typescript
// agent-ts/src/infrastructure/tools/data/fetch-stock-tool.ts
// 自动使用实时数据（交易时段）或数据库数据（非交易时段）

const result = await getStockData(symbol, ['price'], 10, 'auto');
// 返回的 result.price.source 会告诉你是 "sina" (实时) 还是 "db_fallback" (数据库)
```

---

## 📋 总结

**quantsys-v2 完全支持实时数据**：

✅ 5个实时数据源  
✅ 自动降级机制  
✅ 交易时段自动判断  
✅ 实时行情 + 分钟K线  
✅ 健康状态监控  
✅ TypeScript 透明集成  

**推荐配置**: 使用 `source=auto` 模式，自动在实时和历史数据间切换。
