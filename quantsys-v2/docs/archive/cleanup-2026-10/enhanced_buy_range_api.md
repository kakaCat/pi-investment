# 增强版买入区间分析 API 文档

## 概述

增强版买入区间分析提供多维度综合评估，包括：
- ✅ **多周期技术分析**（日线、周线、月线布林带）
- ✅ **成交量分析**（量价关系、趋势判断）
- ✅ **基本面分析**（PE/PB/ROE/负债率）
- ✅ **综合推荐**（加权投票 + 置信度）
- ✅ **向后兼容**（保留简化版）

## API 端点

### 基础端点
```
GET /api/stock/{symbol}/buy-range
```

### 参数说明

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `symbol` | string | 必填 | 股票代码（如 000999） |
| `enhanced` | boolean | false | 是否启用增强模式 |
| `periods` | string | daily | 分析周期，逗号分隔：daily,weekly,monthly |
| `volume` | boolean | true | 是否包含成交量分析（仅增强模式） |
| `fundamental` | boolean | true | 是否包含基本面分析（仅增强模式） |

## 使用示例

### 1. 简化版（向后兼容）

```bash
curl "http://127.0.0.1:5001/api/stock/000999/buy-range"
```

**响应示例：**
```json
{
  "success": true,
  "data": {
    "symbol": "000999",
    "currentPrice": 24.58,
    "ma20": 24.42,
    "lowerBound": 23.36,
    "upperBound": 25.48,
    "recommendation": "hold",
    "updateTime": "2026-06-03T13:40:32"
  }
}
```

**适用场景：**
- 快速查询单一时间周期
- 向后兼容旧系统
- 仅需基础买入区间

---

### 2. 增强版 - 多周期分析

```bash
curl "http://127.0.0.1:5001/api/stock/000999/buy-range?enhanced=true&periods=daily,weekly,monthly"
```

**响应示例：**
```json
{
  "success": true,
  "data": {
    "symbol": "000999",
    "综合评分": 40.97,
    "updateTime": "2026-06-03T13:40:32",
    
    "multiPeriodAnalysis": {
      "daily": {
        "currentPrice": 24.58,
        "ma": 24.42,
        "positionPct": 57.6,
        "lowerBound": 23.36,
        "upperBound": 25.48,
        "bandwidth": 8.7,
        "recommendation": "hold",
        "signalStrength": "weak"
      },
      "weekly": {
        "currentPrice": 24.58,
        "ma": 24.1,
        "positionPct": 86.9,
        "lowerBound": 23.44,
        "upperBound": 24.75,
        "bandwidth": 5.45,
        "recommendation": "strong_sell",
        "signalStrength": "strong"
      },
      "monthly": {
        "currentPrice": 24.58,
        "ma": 24.07,
        "positionPct": 87.8,
        "lowerBound": 23.41,
        "upperBound": 24.74,
        "bandwidth": 5.55,
        "recommendation": "strong_sell",
        "signalStrength": "strong"
      }
    },
    
    "volumeAnalysis": {
      "currentVolume": 70866,
      "volumeMa5": 105344,
      "volumeMa20": 90999,
      "volumeRatio": 0.78,
      "volumeSignal": "shrink",
      "volumeTrend": "increasing",
      "volumeScore": 30
    },
    
    "fundamentalAnalysis": {
      "pe": null,
      "pb": null,
      "roe": null,
      "debtRatio": null,
      "fundamentalScore": 50,
      "rating": "fair",
      "positiveFactors": []
    },
    
    "recommendation": {
      "action": "hold",
      "confidence": 45.5,
      "reasons": [],
      "voteDetails": {
        "hold": 0.5,
        "strongSell": 0.5,
        "sell": 0.1
      }
    }
  }
}
```

**适用场景：**
- 需要多时间周期共振判断
- 中长期投资决策
- 全面风险评估

---

### 3. 仅技术面分析

```bash
curl "http://127.0.0.1:5001/api/stock/000999/buy-range?enhanced=true&periods=daily&volume=false&fundamental=false"
```

**适用场景：**
- 日内交易
- 快速技术面判断
- 排除基本面干扰

---

### 4. 仅日线+成交量

```bash
curl "http://127.0.0.1:5001/api/stock/000999/buy-range?enhanced=true&periods=daily&fundamental=false"
```

**适用场景：**
- 短线交易
- 关注量价配合
- 追踪资金流向

---

## 核心指标解读

### 1. 价格分位（positionPct）

表示当前价格在布林带中的位置百分比：

| 分位值 | 位置 | 含义 | 建议 |
|--------|------|------|------|
| 0-20% | 下轨附近 | 超卖 | **强烈买入** 🟢🟢 |
| 20-40% | 偏下 | 相对低估 | 买入 🟢 |
| 40-60% | 中轨附近 | 中性 | 持有 ⚪ |
| 60-80% | 偏上 | 相对高估 | 卖出 🔴 |
| 80-100% | 上轨附近 | 超买 | **强烈卖出** 🔴🔴 |

**示例解读：**
- 日线 57.6%：中性偏上，建议持有
- 周线 86.9%：超买区域，建议卖出
- 月线 87.8%：超买区域，建议卖出

**结论：** 短线中性，中长线偏空

---

### 2. 布林带宽度（bandwidth）

衡量市场波动率：

| 带宽 | 波动率 | 含义 |
|------|--------|------|
| < 5% | 低 | 盘整，可能突破 |
| 5-10% | 中 | 正常波动 |
| > 10% | 高 | 剧烈波动 |

**示例解读：**
- 日线 8.7%：正常波动
- 周线/月线 5-6%：波动收敛，可能酝酿方向性突破

---

### 3. 成交量信号

| 信号 | 含义 | 评分 |
|------|------|------|
| strong_surge | 巨量放大（≥2倍） | 90 |
| surge | 明显放量（≥1.5倍） | 70 |
| moderate_increase | 温和放量（≥1.2倍） | 60 |
| normal | 正常（0.8-1.2倍） | 50 |
| shrink | 缩量（<0.8倍） | 30 |

**示例解读：**
- 量比 0.78（shrink）：成交量萎缩
- 趋势 increasing：5日均量 > 20日均量，短期回升
- 评分 30/100：整体偏弱

---

### 4. 综合评分算法

```
综合评分 = 基础分50 + 技术面权重40% + 成交量权重30% + 基本面权重30%

技术面得分 = 100 - positionPct（位置越低得分越高）
成交量得分 = volumeScore（0-100）
基本面得分 = fundamentalScore（0-100）
```

**评级标准：**
- 80-100分：优秀（excellent）
- 65-79分：良好（good）
- 50-64分：一般（fair）
- 0-49分：较差（poor）

**示例：**
- 综合评分 40.97：偏低，不建议追高

---

### 5. 推荐置信度

基于多维度投票计算：

```
置信度 = 主推荐得票数 / 总票数 × 100%

权重分配：
- 日线：50%
- 周线：30%
- 月线：20%
- 成交量加权：±10-20%
- 基本面加权：±10-15%
```

**示例：**
- 置信度 45.5%：信号分歧，建议观望

---

## 交易策略建议

### 多周期共振策略

| 日线 | 周线 | 月线 | 建议操作 |
|------|------|------|---------|
| 买入 | 买入 | 买入 | **强烈买入**（三周期共振） |
| 买入 | 买入 | 持有 | 买入（短中期看涨） |
| 买入 | 持有 | 卖出 | 观望（信号冲突） |
| 卖出 | 卖出 | 卖出 | **强烈卖出**（三周期共振） |

### 量价配合策略

| 价格信号 | 成交量信号 | 建议操作 |
|---------|-----------|---------|
| 买入 | 放量 | **强烈买入**（量价齐升） |
| 买入 | 缩量 | 谨慎买入（动能不足） |
| 卖出 | 放量 | **强烈卖出**（量价齐跌） |
| 卖出 | 缩量 | 观望（可能反弹） |

### 基本面辅助策略

| 技术信号 | 基本面评级 | 建议操作 |
|---------|-----------|---------|
| 买入 | excellent/good | **强烈买入** |
| 买入 | fair | 买入 |
| 买入 | poor | 观望（估值陷阱） |
| 卖出 | excellent | 减仓（不清仓） |
| 卖出 | poor | **强烈卖出** |

---

## TypeScript 工具集成

```typescript
// 简化版
analysis_cli({
  command: "analysis.buy_range",
  params: { symbol: "000999" }
})

// 增强版（需要扩展 analysis_cli）
analysis_cli({
  command: "analysis.buy_range_enhanced",
  params: {
    symbol: "000999",
    periods: ["daily", "weekly", "monthly"],
    include_volume: true,
    include_fundamental: true
  }
})
```

---

## Python 代码示例

```python
import requests

# 简化版
response = requests.get(
    "http://127.0.0.1:5001/api/stock/000999/buy-range"
)
data = response.json()

# 增强版
response = requests.get(
    "http://127.0.0.1:5001/api/stock/000999/buy-range",
    params={
        "enhanced": "true",
        "periods": "daily,weekly,monthly",
        "volume": "true",
        "fundamental": "true"
    }
)
data = response.json()
```

---

## 实战案例分析

### 案例：000999 当前分析

**技术面：**
- 日线中性（57.6%），周线/月线超买（87%）
- 结论：短期震荡，中长期调整压力大

**成交量：**
- 缩量（0.78倍），评分30/100
- 结论：资金流入不足，上涨动能弱

**综合判断：**
- 综合评分 40.97（偏低）
- 推荐：持有观望，不建议追高
- 风险：周线/月线超买，回调风险较大

**操作建议：**
1. 持仓者：设置止盈止损，防范回调
2. 空仓者：等待日线回踩23.36（下轨）再考虑买入
3. 激进者：日内可博弈，但需严格止损

---

## 性能指标

| 模式 | 响应时间 | 数据源 | 缓存 |
|------|---------|--------|------|
| 简化版 | < 500ms | 单一数据源 | 60秒 |
| 增强版（日线） | < 1s | 多数据源 failover | 60秒 |
| 增强版（三周期） | < 3s | 多数据源 failover | 60秒 |

---

## 后续优化方向

1. **✅ 已完成：**
   - 多周期技术分析
   - 成交量分析
   - 基本面集成
   - 综合推荐算法

2. **🚧 待优化：**
   - 机器学习评分模型
   - 历史准确率回测
   - 个性化风险偏好
   - WebSocket 实时推送
   - 止盈止损建议

3. **💡 扩展方向：**
   - MACD、RSI 等更多技术指标
   - 行业板块轮动分析
   - 资金流向追踪
   - 机构持仓变化

---

## 文件位置

- **服务实现：** `quantsys-v2/services/enhanced_buy_range_service.py`
- **API 路由：** `quantsys-v2/api/routes/analysis.py`
- **测试脚本：** `quantsys-v2/test_enhanced_buy_range.py`
- **文档：** `quantsys-v2/docs/enhanced_buy_range_api.md`

---

## 更新日志

### 2026-06-03
- ✅ 实现增强版买入区间分析
- ✅ 集成多数据源 failover
- ✅ 添加多周期技术分析
- ✅ 添加成交量分析
- ✅ 添加基本面分析
- ✅ 实现综合推荐算法
- ✅ 保持向后兼容性
