# 实时股票数据功能

## 概述

`data_fetch_stock` 工具支持获取实时股票行情数据，通过新浪财经 API 提供延迟 < 3秒的实时价格信息。

## 功能特性

### 1. 实时数据来源

- **主数据源**：新浪财经实时行情 API
  - A股：`https://hq.sinajs.cn/list=` + 股票代码
  - 港股：`https://hq.sinajs.cn/list=hk` + 股票代码
  - 超时时间：8秒
  - 数据延迟：< 3秒

- **降级方案**：数据库最新 K 线收盘价
  - 当新浪 API 失败时自动降级
  - 标记为 `source: "db_fallback"`

### 2. 数据时效性标识

返回数据中的 `source` 字段标识数据来源：

| source 值 | 说明 | 数据时效性 |
|-----------|------|-----------|
| `sina` | 新浪实时 API | 实时数据（延迟 < 3秒） |
| `db_fallback` | 数据库最新收盘价 | 非实时（最新交易日收盘价） |

### 3. 交易时段判断

工具会自动判断当前是否处于交易时段：

**A股交易时段**：
- 上午：9:30 - 11:30
- 下午：13:00 - 15:00
- 交易日：周一至周五（不含节假日）

**港股交易时段**：
- 上午：9:30 - 12:00
- 下午：13:00 - 16:00
- 交易日：周一至周五（不含节假日）

## 使用示例

### 基础用法 - 获取实时价格

```typescript
data_fetch_stock({
  symbol: "600000",
  fields: ["price"]
})
```

**返回示例（交易时段内）**：

```
【实时行情】（新浪财经，延迟 < 3秒）
股票代码: 600000.SH
股票名称: 浦发银行
当前价格: 1,650.50 元
涨跌幅: +2.35%
涨跌额: +37.80 元
今开: 1,645.00 元
最高: 1,680.00 元
最低: 1,640.00 元
昨收: 1,612.70 元
成交量: 123,456 万股
成交额: 20.45 亿元

💡 当前处于交易时段，数据为实时行情
```

**返回示例（非交易时段）**：

```
【实时行情】（新浪财经，延迟 < 3秒）
股票代码: 600000.SH
股票名称: 浦发银行
当前价格: 1,650.50 元
涨跌幅: +2.35%
涨跌额: +37.80 元
今开: 1,645.00 元
最高: 1,680.00 元
最低: 1,640.00 元
昨收: 1,612.70 元
成交量: 123,456 万股
成交额: 20.45 亿元

💡 当前非交易时段，显示最新成交价
```

**返回示例（降级到数据库）**：

```
【最新收盘价】（数据库，非实时）
股票代码: 600000.SH
股票名称: 浦发银行
当前价格: 1,650.50 元
涨跌幅: +2.35%
今开: 1,645.00 元
最高: 1,680.00 元
最低: 1,640.00 元
成交量: 123,456 万股

⚠️ 实时行情获取失败，显示数据库最新收盘价
```

### 组合查询 - 实时价格 + 基本信息

```typescript
data_fetch_stock({
  symbol: "600000",
  fields: ["info", "price"]
})
```

**返回示例**：

```
【实时行情】（新浪财经，延迟 < 3秒）
股票代码: 600000.SH
股票名称: 浦发银行
当前价格: 1,650.50 元
涨跌幅: +2.35%
...

【基本信息】
{
  "symbol": "600000.SH",
  "name": "浦发银行",
  "market": "沪市主板",
  "industry": "白酒",
  ...
}
```

### 完整查询 - 所有字段

```typescript
data_fetch_stock({
  symbol: "600000",
  fields: ["info", "price", "news", "announcements"],
  news_num: 5
})
```

## 数据字段说明

### price 字段（实时行情）

| 字段 | 类型 | 说明 |
|------|------|------|
| symbol | string | 股票代码 |
| name | string | 股票名称 |
| price | number | 当前价格 |
| change_pct | number | 涨跌幅（%） |
| change | number | 涨跌额（元） |
| open | number | 今开价 |
| high | number | 最高价 |
| low | number | 最低价 |
| prev_close | number | 昨收价 |
| volume | number | 成交量（股） |
| amount | number | 成交额（元，仅A股） |
| source | string | 数据来源（sina/db_fallback） |

## 技术实现

### 后端 API

- **端点**：`GET /api/stock/{symbol}/quote`
- **实现**：`quantsys-v2/api/routes/quote_market.py`
- **数据源**：新浪财经 API
- **超时**：8秒
- **降级**：自动降级到数据库最新 K 线

### 前端工具

- **工具定义**：`src/infrastructure/tools/data/fetch-stock-tool.ts`
- **客户端**：`src/infrastructure/quant/quant-v2-client.ts`
- **格式化**：`src/infrastructure/quant/formatters.ts`

### 数据流

```
Agent 调用 data_fetch_stock
    ↓
getStockData() 并行请求
    ↓
GET /api/stock/{symbol}/quote
    ↓
尝试新浪 API (8秒超时)
    ↓
成功 → 返回实时数据 (source: "sina")
失败 → 降级到数据库 (source: "db_fallback")
    ↓
formatStockPrice() 格式化输出
    ↓
返回给 Agent（带时效性标识）
```

## 使用场景

### 1. 盘中监控

```typescript
// 监控持仓股票实时价格
data_fetch_stock({
  symbol: "600000",
  fields: ["price"]
})
```

### 2. 实时决策

```typescript
// 获取实时价格用于买卖决策
data_fetch_stock({
  symbol: "600000",
  fields: ["price"]
})

// 根据 source 字段判断数据时效性
if (result.price.source === 'sina') {
  // 使用实时数据进行决策
} else {
  // 提示用户数据非实时
}
```

### 3. 快速查询

```typescript
// 快速查看股票当前价格和涨跌幅
data_fetch_stock({
  symbol: "600000",
  fields: ["price"]
})
```

## 注意事项

1. **数据延迟**：实时数据延迟 < 3秒，但不保证绝对实时
2. **交易时段**：非交易时段显示最新成交价，不是实时变化的
3. **降级机制**：新浪 API 失败时自动降级到数据库，注意检查 `source` 字段
4. **港股支持**：港股实时数据同样支持，使用方式相同
5. **超时设置**：默认超时 8秒，可通过环境变量 `QUANTSYS_V2_TIMEOUT` 调整

## 相关文档

- [data_fetch_stock 工具文档](../tools/data-fetch-stock.md)
- [quantsys-v2 API 文档](../../quantsys-v2/README.md)
- [新浪财经 API 说明](../references/sina-finance-api.md)
