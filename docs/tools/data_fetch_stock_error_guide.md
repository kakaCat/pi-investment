# data_fetch_stock 工具错误指南

## 常见错误：HTTP 502 - 无法获取实时行情

### 错误示例

```json
{
  "success": true,
  "info": { /* 基本信息成功获取 */ },
  "price": null,
  "price_error": "HTTP 502: {\"error\":\"无法获取 601633 的实时行情\",\"success\":false}"
}
```

---

## 根本原因

### 1. 实时行情服务架构

后端使用 `RealtimeQuoteService` 多数据源协调器，按优先级依次尝试 5 个数据源：

1. **AkShare** (akshare)
2. **新浪财经** (sina)
3. **东方财富** (eastmoney)
4. **腾讯财经** (tencent)
5. **网易财经** (netease)

当所有数据源都失败或返回无效数据时，服务返回 `None`。

### 2. API 端点行为

`/api/stock/{symbol}/quote` 端点根据 `source` 参数决定失败时的行为：

| source 参数 | 行为 | 失败时 |
|-------------|------|--------|
| `realtime` (默认) | 仅尝试实时数据源 | 返回 **HTTP 502** 错误 |
| `auto` | 实时优先，失败时 fallback | 自动切换到数据库历史数据 |
| `db` | 仅查询数据库 | 无数据时返回 404 |

### 3. 数据源失败的常见原因

- ❌ **外部 API 服务故障或维护**（如新浪财经临时不可用）
- ❌ **网络连接问题**（超时、DNS 解析失败）
- ❌ **API 限流**（请求频率过高）
- ❌ **非交易时段**（某些数据源在非交易时段不提供实时数据）
- ❌ **数据格式验证失败**（price ≤ 0 或缺少必填字段：symbol、name、timestamp、source）

---

## 解决方案

### ✅ 推荐方案：保持 `source: "realtime"` (默认)，失败时使用浏览器查询

```typescript
// 第一步：尝试实时数据（默认）
data_fetch_stock({
  symbol: "601633",
  fields: ["price", "info"]
  // source 默认为 "realtime"
})
```

**如果返回 502 错误：**

```typescript
// 第二步：使用 WebSearch 或 WebFetch 从网页获取实时数据
WebSearch({
  query: "长城汽车 601633 股票实时行情"
})

// 或访问行情网站
WebFetch({
  url: "https://quote.eastmoney.com/sh601633.html",
  prompt: "提取长城汽车（601633）的最新价格、涨跌幅和成交量"
})
```

**为什么不自动 fallback 到数据库：**
- ❌ **实时数据和历史数据有本质区别**：盘中决策需要实时价格
- ❌ **避免误导**：自动使用过期数据可能导致错误决策
- ✅ **透明性**：明确告知数据不可用，让 LLM 选择其他手段
- ✅ **灵活性**：LLM 可以使用浏览器获取最新数据

### 🔧 备选方案：特定场景下的 `source` 参数

**场景 1：仅需历史数据（回测、统计分析）**

```typescript
data_fetch_stock({
  symbol: "601633",
  fields: ["price", "info"],
  source: "db"  // 直接查询数据库，更快
})
```

**场景 2：实时优先，但可接受历史数据**

```typescript
data_fetch_stock({
  symbol: "601633",
  fields: ["price"],
  source: "auto"  // 自动 fallback（谨慎使用）
})

// ⚠️ 注意：需检查 source 字段确认数据时效性
if (result.price.source === "db_fallback") {
  console.log(`⚠️ 使用历史数据：${result.price.tradeDate}`);
}
```

---

## 使用建议

### 场景 1：需要实时价格（盘中决策）⭐ 默认场景

```typescript
// 第一步：尝试实时数据
const result = await data_fetch_stock({
  symbol: "600519",
  fields: ["price"]
  // source 默认为 "realtime"
});

// 第二步：如果失败，使用浏览器查询
if (result.price_error) {
  // 使用 WebSearch 获取最新行情
  const webResult = await WebSearch({
    query: "贵州茅台 600519 股票实时行情"
  });
  
  // 或使用 WebFetch 访问行情网站
  const fetchResult = await WebFetch({
    url: "https://quote.eastmoney.com/sh600519.html",
    prompt: "提取贵州茅台的最新价格、涨跌幅和成交量"
  });
}
```

### 场景 2：仅需历史数据（回测、统计分析）

```typescript
data_fetch_stock({
  symbol: "600519",
  fields: ["price", "info"],
  source: "db"  // 直接查询数据库，速度更快
})
```

### 场景 3：实时优先但可接受历史数据（低优先级查询）

```typescript
data_fetch_stock({
  symbol: "600519",
  fields: ["price"],
  source: "auto"  // 自动 fallback
})

// ⚠️ 注意：必须检查 source 字段
if (result.price.source === "db_fallback") {
  console.warn(`使用历史数据：${result.price.tradeDate}`);
}
```

---

## 数据时效性说明

| 数据来源 | 延迟 | 数据时间标识 | 适用场景 |
|---------|------|-------------|---------|
| 实时数据源 | < 3秒 | `timestamp` (ISO 8601) | 盘中交易决策 |
| 数据库 | 最近交易日收盘 | `tradeDate` (YYYY-MM-DD) | 历史分析、回测 |

---

## 错误处理示例

### Python 后端日志

```
[WARNING] RealtimeQuoteService: Provider akshare failed for 601633: ConnectionError
[WARNING] RealtimeQuoteService: Provider sina failed for 601633: Timeout
[WARNING] RealtimeQuoteService: Provider eastmoney returned invalid data for 601633: None
[WARNING] RealtimeQuoteService: Provider tencent failed for 601633: HTTPError: 503
[WARNING] RealtimeQuoteService: Provider netease returned invalid data for 601633: price=0
[ERROR] RealtimeQuoteService: All providers failed for 601633
```

### TypeScript 工具返回

```json
{
  "success": true,
  "info": { /* 基本信息 */ },
  "price": null,
  "price_error": "HTTP 502: {\"error\":\"无法获取 601633 的实时行情\",\"success\":false}"
}
```

### 正确的处理方式

**❌ 错误做法：**
```typescript
// 遇到 502 错误后直接放弃
if (result.price_error) {
  throw new Error("无法获取价格数据");
}
```

**✅ 正确做法：**
```typescript
// 第一步：使用默认 realtime 模式
const result = await data_fetch_stock({
  symbol: "601633",
  fields: ["price"]
  // source 默认为 "realtime"
});

// 第二步：如果返回 502 错误，使用浏览器查询
if (result.price_error && result.price_error.includes("502")) {
  console.log("⚠️ 实时数据源不可用，尝试使用浏览器查询最新行情...");
  
  // 方案 A：使用 WebSearch 搜索实时行情
  const searchResult = await WebSearch({
    query: "长城汽车 601633 实时股价 最新"
  });
  
  // 方案 B：使用 WebFetch 访问行情网站
  const quoteResult = await WebFetch({
    url: "https://quote.eastmoney.com/sh601633.html",
    prompt: "提取长城汽车（601633）的最新价格、涨跌幅、成交量和更新时间"
  });
  
  // 推荐网站：
  // - 东方财富: https://quote.eastmoney.com/
  // - 新浪财经: https://finance.sina.com.cn/realstock/
  // - 雪球: https://xueqiu.com/
}
```

---

## 技术细节

### 数据源验证规则

`RealtimeQuoteService._is_valid_quote()` 验证标准：

```python
def _is_valid_quote(self, quote: QuoteData) -> bool:
    return (
        quote.price > 0 and           # 价格必须 > 0
        quote.symbol and              # 必须有股票代码
        quote.name and                # 必须有股票名称
        quote.timestamp and           # 必须有时间戳
        quote.source                  # 必须有数据源标识
    )
```

### 数据库 Fallback 逻辑

```python
# auto 模式：实时数据源全部失败后
if source == 'auto':
    db_result = _get_db_quote(clean_symbol)  # 查询最近交易日收盘价
    if db_result:
        db_result['source'] = 'db_fallback'
        return api_response(db_result)
```

---

## 总结

**给 LLM 的核心建议：**

1. **保持默认 `source: "realtime"`**：除非明确只需历史数据，否则使用默认模式获取实时行情
2. **遇到 502 错误时使用浏览器查询**：通过 WebSearch 或 WebFetch 从行情网站获取最新数据
3. **不要自动 fallback 到历史数据**：实时数据和历史数据有本质区别，避免误导决策
4. **理解错误含义**：502 不是工具故障，而是所有实时数据源暂时不可用
5. **透明性优先**：明确告知用户数据来源和时效性

**核心原则：透明性 > 便利性**

实时数据不可用时，明确告知并建议替代方案（浏览器查询）比自动使用过期数据更安全。这样可以：
- ✅ 避免使用过期数据做出错误决策
- ✅ 让用户了解当前数据状态
- ✅ 提供灵活的替代方案（WebSearch/WebFetch）
- ✅ 保持数据时效性的透明度

**推荐的错误处理流程：**

```
1. 尝试 data_fetch_stock (默认 realtime)
   ↓
2. 成功 → 使用实时数据
   ↓
3. 失败 (502) → 提示用户 + 使用 WebSearch/WebFetch
   ↓
4. 网页查询成功 → 返回最新数据
   ↓
5. 网页也失败 → 考虑使用 source: "db" 获取历史数据（需明确说明）
```
