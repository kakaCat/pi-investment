# quantsys-v2 API 文档

**版本**: v2.0  
**基础URL**: `http://localhost:5001`  
**更新时间**: 2026-06-02

---

## 📋 目录

- [认证](#认证)
- [通用响应格式](#通用响应格式)
- [错误码](#错误码)
- [API端点](#api端点)
  - [股票分析](#股票分析)
  - [市场情绪](#市场情绪)
  - [财务分析](#财务分析)
  - [股东分析](#股东分析)

---

## 认证

当前版本暂不需要认证。

---

## 通用响应格式

所有API响应采用统一格式：

### 成功响应

```json
{
  "success": true,
  "data": {
    // 具体数据
  }
}
```

### 错误响应

```json
{
  "success": false,
  "error": "错误信息"
}
```

---

## 错误码

| HTTP状态码 | 说明 |
|-----------|------|
| 200 | 成功 |
| 400 | 请求参数错误 |
| 404 | 资源不存在 |
| 500 | 服务器内部错误 |
| 503 | 服务不可用 |

---

## API端点

### 股票分析

#### 1. 股票综合评分

**端点**: `GET /api/stock/{symbol}/score`

**描述**: 获取股票的综合评分，包括技术面、基本面、动量和质量四个维度。

**路径参数**:
- `symbol` (required): 股票代码，如 `600036`

**响应示例**:
```json
{
  "success": true,
  "data": {
    "symbol": "600036",
    "name": "招商银行",
    "market": "A",
    "totalScore": 23.0,
    "technicalScore": 20.0,
    "fundamentalScore": 0.0,
    "momentumScore": 50.0,
    "qualityScore": 50.0,
    "grade": "D",
    "signals": [
      {
        "type": "avoid",
        "message": "综合评分较低，建议回避",
        "priority": "high"
      }
    ],
    "configVersion": "v2_configurable",
    "weights": {
      "technical": 0.4,
      "fundamental": 0.3,
      "momentum": 0.2,
      "quality": 0.1
    },
    "timestamp": "2026-06-02T10:28:00"
  }
}
```

**评分等级**:
- A+ (≥90): 优秀
- A (≥80): 良好
- B+ (≥70): 可考虑
- B (≥60): 中等
- C (≥50): 一般
- D (<50): 较差

---

#### 2. 股票筛选

**端点**: `GET /api/stocks/screen`

**描述**: 根据多个条件筛选股票。

**查询参数**:
- `min_score` (optional): 最低评分
- `max_pe` (optional): 最高PE
- `min_roe` (optional): 最低ROE (0-1)
- `max_debt_ratio` (optional): 最高负债率 (0-1)
- `min_market_cap` (optional): 最低市值(亿)
- `exclude_st` (optional): 排除ST股票 (true/false)
- `sort_by` (optional): 排序字段 (score/pe/roe/market_cap)
- `limit` (optional): 返回数量，默认50

**请求示例**:
```
GET /api/stocks/screen?max_pe=20&min_roe=0.15&limit=10
```

**响应示例**:
```json
{
  "success": true,
  "data": {
    "total": 5533,
    "matched": 10,
    "stocks": [
      {
        "symbol": "002818",
        "name": "富森美",
        "market": "A",
        "industry": "批发零售",
        "score": 0,
        "pe": 13.21,
        "pb": 2.5,
        "roe": 6.7,
        "debtRatio": 25.3,
        "marketCap": 84.1,
        "reason": "低PE(13.2), 高ROE(670.0%)"
      }
    ],
    "criteria": {
      "max_pe": 20,
      "min_roe": 0.15,
      "limit": 10
    },
    "timestamp": "2026-06-02T12:30:00"
  }
}
```

---

### 市场情绪

#### 3. 市场情绪分析

**端点**: `GET /api/market/sentiment`

**描述**: 分析整体市场情绪，包括恐惧贪婪指数和市场阶段判断。

**响应示例**:
```json
{
  "success": true,
  "data": {
    "sentimentScore": 60.0,
    "sentimentLevel": "neutral_positive",
    "fearGreedIndex": 60.0,
    "marketPhase": "recovery",
    "recommendation": "市场偏乐观，可适量参与",
    "indicators": {
      "advanceDecline": {
        "upCount": 50,
        "downCount": 30,
        "ratio": 1.67,
        "strength": "positive"
      },
      "volume": {
        "volumeRatio": 0.91,
        "status": "normal"
      },
      "indexPerformance": {
        "positiveCount": 0,
        "totalCount": 3,
        "marketTrend": "strong_down"
      }
    },
    "timestamp": "2026-06-02T11:30:00"
  }
}
```

**情绪等级**:
- extreme_greed: 极度贪婪
- greed: 贪婪
- neutral_positive: 偏乐观
- neutral: 中性
- neutral_negative: 偏悲观
- fear: 恐慌
- extreme_fear: 极度恐慌

**市场阶段**:
- bull_market: 牛市
- recovery: 复苏
- consolidation: 整固
- correction: 调整
- bear_market: 熊市

---

#### 4. 个股资金流向

**端点**: `GET /api/stock/{symbol}/fund-flow`

**描述**: 获取个股的主力资金流向数据。

**路径参数**:
- `symbol` (required): 股票代码

**查询参数**:
- `days` (optional): 查询天数，默认5

**请求示例**:
```
GET /api/stock/600036/fund-flow?days=5
```

**响应示例**:
```json
{
  "success": true,
  "data": {
    "symbol": "600036",
    "days": 5,
    "source": "akshare_fallback",
    "data": [
      {
        "date": "2026-06-02",
        "closePrice": 43.14,
        "changePct": -2.44,
        "mainNetInflow": -4566.76,
        "mainNetInflowRate": 0.24,
        "largeNetInflow": -2740.06,
        "largeNetInflowRate": 0.14,
        "bigNetInflow": -1826.70,
        "bigNetInflowRate": 0.10,
        "mediumNetInflow": 2283.38,
        "mediumNetInflowRate": -0.12,
        "smallNetInflow": 2283.38,
        "smallNetInflowRate": -0.12
      }
    ],
    "summary": {
      "totalMainNetInflow": -5.98,
      "avgMainNetInflowRate": -3.67,
      "consecutiveInflowDays": 1,
      "trend": "inflow"
    },
    "analysis": {
      "mainBehavior": {
        "description": "主力净流出，资金观望",
        "strength": "negative"
      },
      "capitalStructure": {
        "description": "超大单和大单同步流入，机构主导",
        "type": "institutional"
      }
    },
    "signals": [],
    "timestamp": "2026-06-02T10:40:00"
  }
}
```

---

#### 5. 融资融券数据

**端点**: `GET /api/stock/{symbol}/margin`

**描述**: 获取个股的融资融券数据。

**路径参数**:
- `symbol` (required): 股票代码

**查询参数**:
- `days` (optional): 查询天数，默认5

**响应示例**:
```json
{
  "success": true,
  "data": {
    "symbol": "600036",
    "days": 5,
    "source": "simulated",
    "data": [
      {
        "date": "2026-06-02",
        "financingBalance": 47504.61,
        "financingBuy": 2375.23,
        "financingRepay": 1900.18,
        "marginBalance": 5433.08,
        "marginSell": 815.0,
        "marginRepay": 652.0,
        "totalBalance": 52937.69
      }
    ],
    "summary": {
      "financingTrend": "stable",
      "marginTrend": "stable",
      "financingChangeRate": -2.93,
      "activityLevel": "low"
    },
    "timestamp": "2026-06-02T12:00:00"
  }
}
```

---

### 财务分析

#### 6. PE历史分位数

**端点**: `GET /api/stock/{symbol}/pe-percentile`

**描述**: 计算股票PE在历史上的分位数位置。

**路径参数**:
- `symbol` (required): 股票代码

**查询参数**:
- `years` (optional): 统计年数，默认3

**响应示例**:
```json
{
  "success": true,
  "data": {
    "symbol": "600036",
    "name": "招商银行",
    "currentPe": 6.62,
    "percentile": 45.12,
    "years": 3,
    "peStats": {
      "min": 4.69,
      "max": 7.84,
      "mean": 6.44,
      "median": 6.72,
      "std": 0.86
    },
    "valuationLevel": "average",
    "valuationDesc": "当前PE处于历史中等水平（45.1分位），估值合理",
    "dataPoints": 523,
    "historicalData": [
      {
        "date": "2026-06-01",
        "pe": 6.65
      }
    ],
    "timestamp": "2026-06-02T10:48:00"
  }
}
```

**估值等级**:
- extremely_low (0-10%): 极度低估
- low (10-25%): 低估
- below_average (25-40%): 偏低
- average (40-60%): 合理
- above_average (60-75%): 偏高
- high (75-90%): 高估
- extremely_high (90-100%): 极度高估

---

### 股东分析

#### 7. 内部交易

**端点**: `GET /api/stock/{symbol}/insider-trades`

**描述**: 获取公司内部人员（高管、董事等）的交易记录。

**路径参数**:
- `symbol` (required): 股票代码

**查询参数**:
- `days` (optional): 查询天数，默认30

**响应示例**:
```json
{
  "success": true,
  "data": {
    "symbol": "600036",
    "trades": [
      {
        "date": "2026-06-02",
        "holderName": "张三",
        "holderType": "董事",
        "changeType": "增持",
        "changeShares": 150.5,
        "changeRatio": 1.2,
        "avgPrice": 35.5,
        "reason": "个人资金安排"
      }
    ],
    "summary": {
      "totalBuy": 450.0,
      "totalSell": 200.0,
      "netChange": 250.0,
      "sentiment": "positive"
    },
    "timestamp": "2026-06-02T13:00:00"
  }
}
```

---

#### 8. 基金持仓

**端点**: `GET /api/stock/{symbol}/fund-holdings`

**描述**: 获取持有该股票的基金列表。

**路径参数**:
- `symbol` (required): 股票代码

**查询参数**:
- `quarter` (optional): 季度，如 2024Q1

**响应示例**:
```json
{
  "success": true,
  "data": {
    "symbol": "600036",
    "quarter": "2024Q4",
    "holdings": [
      {
        "fundCode": "000001",
        "fundName": "易方达蓝筹",
        "shares": 5000.0,
        "ratio": 2.5,
        "marketValue": 25000.0,
        "rank": 1
      }
    ],
    "summary": {
      "totalFunds": 5,
      "totalShares": 15000.0,
      "totalRatio": 7.5,
      "changeFromLast": 2.3
    },
    "timestamp": "2026-06-02T13:00:00"
  }
}
```

---

#### 9. 十大股东

**端点**: `GET /api/stock/{symbol}/top-holders`

**描述**: 获取公司十大股东信息。

**路径参数**:
- `symbol` (required): 股票代码

**查询参数**:
- `holder_type` (optional): 股东类型 (all/circulation)

**响应示例**:
```json
{
  "success": true,
  "data": {
    "symbol": "600036",
    "reportDate": "2024-12-31",
    "holderType": "all",
    "holders": [
      {
        "rank": 1,
        "holderName": "某某基金",
        "holderType": "基金",
        "shares": 35000.0,
        "ratio": 8.5,
        "change": 500.0
      }
    ],
    "summary": {
      "totalTop10Ratio": 55.2,
      "institutionalRatio": 42.3
    },
    "timestamp": "2026-06-02T13:00:00"
  }
}
```

---

#### 10. 股东变化趋势

**端点**: `GET /api/stock/{symbol}/holder-changes`

**描述**: 获取股东户数变化趋势。

**路径参数**:
- `symbol` (required): 股票代码

**查询参数**:
- `periods` (optional): 查询期数，默认4

**响应示例**:
```json
{
  "success": true,
  "data": {
    "symbol": "600036",
    "periods": [
      {
        "period": "2024Q4",
        "holderCount": 98500,
        "avgShares": 12500.0,
        "changeRatio": -3.5
      }
    ],
    "trend": "decreasing",
    "timestamp": "2026-06-02T13:00:00"
  }
}
```

**趋势说明**:
- decreasing: 股东户数减少，筹码集中
- stable: 股东户数稳定
- increasing: 股东户数增加，筹码分散

---

#### 11. 基金重仓股

**端点**: `GET /api/sentiment/top-fund-stocks`

**描述**: 获取被基金重仓持有的股票排行。

**查询参数**:
- `fund_type` (optional): 基金类型 (all/equity/hybrid)
- `limit` (optional): 返回数量，默认50

**响应示例**:
```json
{
  "success": true,
  "data": {
    "fundType": "all",
    "stocks": [
      {
        "symbol": "600519",
        "name": "贵州茅台",
        "fundCount": 350,
        "totalShares": 85000.0,
        "totalValue": 850000.0,
        "avgRatio": 3.5
      }
    ],
    "timestamp": "2026-06-02T13:00:00"
  }
}
```

---

## 📝 使用示例

### Python示例

```python
import requests

# 基础URL
BASE_URL = "http://localhost:5001"

# 1. 获取股票评分
def get_stock_score(symbol):
    url = f"{BASE_URL}/api/stock/{symbol}/score"
    response = requests.get(url)
    return response.json()

# 2. 筛选股票
def screen_stocks(max_pe=20, min_roe=0.15, limit=10):
    url = f"{BASE_URL}/api/stocks/screen"
    params = {
        'max_pe': max_pe,
        'min_roe': min_roe,
        'limit': limit
    }
    response = requests.get(url, params=params)
    return response.json()

# 3. 获取市场情绪
def get_market_sentiment():
    url = f"{BASE_URL}/api/market/sentiment"
    response = requests.get(url)
    return response.json()

# 使用示例
if __name__ == "__main__":
    # 获取招商银行评分
    score = get_stock_score("600036")
    print(f"评分: {score['data']['totalScore']}")
    
    # 筛选优质股票
    stocks = screen_stocks(max_pe=15, min_roe=0.20)
    print(f"找到 {stocks['data']['matched']} 只股票")
    
    # 查看市场情绪
    sentiment = get_market_sentiment()
    print(f"市场情绪: {sentiment['data']['sentimentLevel']}")
```

### JavaScript示例

```javascript
const BASE_URL = "http://localhost:5001";

// 获取股票评分
async function getStockScore(symbol) {
  const response = await fetch(`${BASE_URL}/api/stock/${symbol}/score`);
  return await response.json();
}

// 筛选股票
async function screenStocks(maxPe, minRoe, limit) {
  const params = new URLSearchParams({
    max_pe: maxPe,
    min_roe: minRoe,
    limit: limit
  });
  const response = await fetch(`${BASE_URL}/api/stocks/screen?${params}`);
  return await response.json();
}

// 使用示例
(async () => {
  const score = await getStockScore("600036");
  console.log(`评分: ${score.data.totalScore}`);
  
  const stocks = await screenStocks(15, 0.20, 10);
  console.log(`找到 ${stocks.data.matched} 只股票`);
})();
```

---

## 🔧 开发调试

### 健康检查

**端点**: `GET /api/health`

**响应**:
```json
{
  "status": "ok",
  "version": "2.0"
}
```

---

## 📞 联系支持

- 项目仓库: `pi-investment`
- 文档位置: `docs/api/API文档.md`
- 更新日期: 2026-06-02

---

**版本历史**:
- v2.0 (2026-06-02): 完整实现所有11个功能
- v1.0 (2026-06-01): 初始版本
