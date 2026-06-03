# 评分工具功能对比

**日期**: 2026-06-03  
**目的**: 澄清各评分工具的定位，避免功能混淆  

---

## 工具矩阵

| 工具 | 用途 | 评分维度 | 批量支持 | 主要场景 |
|------|------|---------|---------|---------|
| **stock.score** | 单股综合评分 | 技术(40%) + 基本面(30%) + 动量(20%) + 质量(10%) | ❌ 单只 | 深度分析单只股票 |
| **opportunity_scan** | 机会扫描 | 技术 + 基本面 + 资金面（权重可调） | ✅ 批量 | 从池中筛选机会 |
| **analysis.quality** | 质量评分 | 盈利能力(40%) + 财务健康(30%) + 成长性(20%) + 稳定性(10%) | ❌ 单只 | 评估公司基本面质量 |

---

## 详细对比

### 1. stock.score (stock_cli)

**定位**: 单只股票的全方位评估工具

#### 核心特性
- **四维评分**: 技术面 + 基本面 + 动量 + 质量
- **权重固定**: 40%/30%/20%/10%（不可调整）
- **数据完整性检查**: ✅ 显示缺失数据和完整度百分比
- **信号生成**: 买入/卖出/观望建议

#### 评分算法

```
总分 = 技术面 × 0.40 + 基本面 × 0.30 + 动量 × 0.20 + 质量 × 0.10

技术面 (0-100):
  - RSI (30%): 超买超卖判断
  - MACD (30%): 趋势方向
  - 均线 (25%): 多空排列
  - 布林带 (15%): 波动率位置

基本面 (0-100):
  - PE (30%): 估值水平
  - ROE (30%): 盈利能力
  - 负债率 (25%): 财务健康
  - PB (15%): 市净率

动量 (0-100):
  - 价格涨跌幅 (50%): 短期趋势
  - 成交量变化 (30%): 资金关注度
  - 连续上涨天数 (20%): 趋势强度

质量 (0-100):
  - 毛利率 (40%): 产品竞争力
  - 净利率 (40%): 经营效率
  - 现金流 (20%): 造血能力
```

#### 适用场景

✅ **推荐使用**:
- 深度分析单只股票（如持仓标的定期检查）
- 需要了解数据完整性（哪些指标缺失）
- 需要详细的各维度得分
- 需要交易信号（RSI超买超卖、MACD金叉死叉）

❌ **不推荐使用**:
- 批量筛选股票（效率低）
- 需要自定义权重（固定权重不可调）
- 仅关注某一维度（如只看基本面）

#### 调用示例

```typescript
stock_cli({ 
  command: "stock.score", 
  params: { symbol: "600519" } 
})
```

#### 返回示例

```json
{
  "symbol": "600519",
  "name": "贵州茅台",
  "totalScore": 78.5,
  "grade": "B+",
  "technicalScore": 82.0,
  "fundamentalScore": 75.0,
  "momentumScore": 70.0,
  "qualityScore": 85.0,
  "signals": [
    {"type": "buy", "message": "综合评分良好，可考虑买入"}
  ],
  "missingData": {
    "momentum": ["change_pct_5d"]
  },
  "dataCompleteness": {
    "overall": 0.95,
    "technical": 1.0,
    "fundamental": 1.0,
    "momentum": 0.67,
    "quality": 1.0
  }
}
```

---

### 2. opportunity_scan

**定位**: 批量机会扫描与智能选股

#### 核心特性
- **三维评分**: 技术面 + 基本面 + 资金面
- **权重灵活**: 支持固定/自定义/动态三种模式
- **批量高效**: 一次扫描数百只股票
- **筛选条件**: RSI超卖、MACD金叉、PE<20、ROE>15% 等
- **行业轮动**: 自动识别强势行业

#### 三种权重模式

**模式1: 固定权重（默认）**
```typescript
opportunity_scan({
  symbols: ["600519", "000858", "002714"],
  limit: 20
})
// 权重: 技术50% + 基本面30% + 资金20%
```

**模式2: 自定义权重**
```typescript
opportunity_scan({
  symbols: ["600519", "000858"],
  weights: {
    technical: 0.7,    // 70%
    fundamental: 0.2,  // 20%
    capital: 0.1       // 10%
  }
})
```

**模式3: 动态权重（推荐）**
```typescript
opportunity_scan({
  symbols: ["600519", "000858"],
  enable_dynamic_weights: true,
  dynamic_weights_config: {
    factors: ["rsi", "macd", "roe", "pe"],
    analysis_period: {
      start_date: "2025-12-01",
      end_date: "2026-06-01"
    }
  }
})
// 根据因子有效性（IC/IR）自动计算最优权重
```

#### 适用场景

✅ **推荐使用**:
- 从股票池筛选交易机会
- 策略开发前的选股
- 市场扫描找热点
- 需要自适应市场环境（动态权重）
- 批量评估多只股票

❌ **不推荐使用**:
- 深度分析单只股票（不如 stock.score 详细）
- 需要数据完整性报告
- 需要质量维度的深度评估

#### 返回示例

```json
{
  "opportunities": [
    {
      "symbol": "600519",
      "name": "贵州茅台",
      "score": 85,
      "technical_score": 90,
      "fundamental_score": 80,
      "capital_score": 75,
      "confidence": 0.85,
      "risk_level": "low",
      "signal_type": "buy"
    }
  ],
  "total": 1,
  "scanned": 400
}
```

---

### 3. analysis.quality

**定位**: 公司基本面质量深度评估

#### 核心特性
- **四维质量评分**: 盈利能力 + 财务健康 + 成长性 + 稳定性
- **趋势分析**: 近3年指标变化趋势
- **框架可选**: 自动/ROE优先/资产负债表/盈利能力
- **单只深度**: 专注基本面，不考虑技术面

#### 评分维度

```
质量总分 = 盈利能力 × 0.40 + 财务健康 × 0.30 + 成长性 × 0.20 + 稳定性 × 0.10

盈利能力 (40%):
  - ROE (50%): 净资产收益率
  - 净利率 (30%): 利润率水平
  - 毛利率 (20%): 产品竞争力

财务健康 (30%):
  - 负债率 (50%): 债务水平
  - 流动比率 (30%): 短期偿债能力
  - 速动比率 (20%): 流动性

成长性 (20%):
  - 营收增长率 (50%): 收入扩张
  - 净利润增长率 (50%): 利润增长

稳定性 (10%):
  - ROE 波动率 (50%): 盈利稳定性
  - 营收波动率 (50%): 收入稳定性
```

#### 适用场景

✅ **推荐使用**:
- 价值投资选股（关注基本面质量）
- 长期持仓标的评估
- 需要趋势分析（质量改善/恶化）
- 过滤财务造假风险

❌ **不推荐使用**:
- 短线交易（不考虑技术面和动量）
- 批量筛选（单只处理）
- 需要综合评分（只看基本面）

#### 调用示例

```typescript
analysis_cli({ 
  command: "analysis.quality", 
  params: { symbol: "600519" } 
})
```

#### 返回示例

```json
{
  "symbol": "600519",
  "name": "贵州茅台",
  "quality_score": 92.5,
  "grade": "A+",
  "dimensions": {
    "profitability": {
      "score": 95,
      "roe": 0.31,
      "net_margin": 0.52,
      "gross_margin": 0.91
    },
    "financial_health": {
      "score": 88,
      "debt_ratio": 0.18,
      "current_ratio": 5.2
    },
    "growth": {
      "score": 85,
      "revenue_growth": 0.18,
      "profit_growth": 0.17
    },
    "stability": {
      "score": 90,
      "roe_volatility": 0.05
    }
  },
  "trend": "improving",
  "warnings": []
}
```

---

## 功能重叠分析

### 重叠部分

| 维度 | stock.score | opportunity_scan | analysis.quality |
|------|-------------|------------------|------------------|
| 技术面 | ✅ 40% | ✅ 可调 | ❌ |
| 基本面 | ✅ 30% | ✅ 可调 | ✅ 100% (深度) |
| 动量 | ✅ 20% | ❌ | ❌ |
| 质量 | ✅ 10% (简化) | ❌ | ✅ 100% (深度) |
| 资金面 | ❌ | ✅ 可调 | ❌ |

### 是否重复？

**结论**: ❌ **不重复，各有侧重**

1. **stock.score** = 综合体检（四维平衡）
   - 适合：单只股票全方位评估
   - 特色：数据完整性检查

2. **opportunity_scan** = 批量筛选（三维可调）
   - 适合：从池中找机会
   - 特色：动态权重、批量高效

3. **analysis.quality** = 基本面专家（质量深度）
   - 适合：价值投资深度评估
   - 特色：趋势分析、框架可选

---

## 使用决策树

```
需要评估股票？
├─ 批量筛选（10+只）？
│  ├─ Yes → opportunity_scan
│  └─ No → 继续
│
├─ 只关注基本面质量？
│  ├─ Yes → analysis.quality
│  └─ No → 继续
│
├─ 需要综合评分（技术+基本面+动量+质量）？
│  ├─ Yes → stock.score
│  └─ No → 根据需求组合使用
│
└─ 需要自定义权重？
   ├─ Yes → opportunity_scan (自定义/动态权重)
   └─ No → stock.score (固定权重)
```

---

## 典型工作流

### 工作流1: 市场扫描 → 深度分析

```typescript
// 步骤1: 批量扫描沪深300，找出高分股票
const opportunities = await opportunity_scan({
  symbols: [...hs300],
  enable_dynamic_weights: true,
  limit: 20
});

// 步骤2: 对top 5进行综合评分
for (const opp of opportunities.slice(0, 5)) {
  const score = await stock_cli({
    command: "stock.score",
    params: { symbol: opp.symbol }
  });
  
  // 步骤3: 如果评分 > 70，深度评估质量
  if (score.totalScore > 70) {
    const quality = await analysis_cli({
      command: "analysis.quality",
      params: { symbol: opp.symbol }
    });
  }
}
```

### 工作流2: 价值投资选股

```typescript
// 步骤1: 质量筛选
const qualityStocks = [];
for (const symbol of stockPool) {
  const quality = await analysis_cli({
    command: "analysis.quality",
    params: { symbol }
  });
  
  if (quality.quality_score > 80) {
    qualityStocks.push(symbol);
  }
}

// 步骤2: 综合评分找买点
for (const symbol of qualityStocks) {
  const score = await stock_cli({
    command: "stock.score",
    params: { symbol }
  });
  
  // 质量好 + 技术面超卖 = 买入机会
  if (score.technicalScore < 40 && score.signals.includes("oversold")) {
    console.log(`买入机会: ${symbol}`);
  }
}
```

### 工作流3: 持仓定期体检

```typescript
// 每周对持仓股票全面评估
for (const position of portfolio) {
  const score = await stock_cli({
    command: "stock.score",
    params: { symbol: position.symbol }
  });
  
  // 检查数据完整性
  if (score.dataCompleteness.overall < 0.7) {
    console.warn(`${position.symbol} 数据不完整，需补充`);
  }
  
  // 评分下降 → 深度检查质量是否恶化
  if (score.totalScore < 50) {
    const quality = await analysis_cli({
      command: "analysis.quality",
      params: { symbol: position.symbol }
    });
    
    if (quality.trend === "deteriorating") {
      console.warn(`${position.symbol} 质量恶化，考虑减仓`);
    }
  }
}
```

---

## 总结

### 何时使用 stock.score？
- ✅ 需要单只股票的**全方位评估**
- ✅ 需要**数据完整性**报告
- ✅ 需要**交易信号**（RSI/MACD）
- ✅ 四维平衡评分（技术+基本面+动量+质量）

### 何时使用 opportunity_scan？
- ✅ 需要**批量筛选**股票
- ✅ 需要**自定义权重**或**动态权重**
- ✅ 从股票池**找机会**
- ✅ 策略开发前的**选股**

### 何时使用 analysis.quality？
- ✅ **价值投资**选股
- ✅ 需要**基本面深度评估**
- ✅ 需要**趋势分析**（质量改善/恶化）
- ✅ 长期持仓标的**质量检查**

### 三者配合使用
推荐组合使用以获得最佳效果：
1. **opportunity_scan** → 从池中筛选候选
2. **stock.score** → 综合评估候选股票
3. **analysis.quality** → 深度评估基本面质量

这样既高效（批量筛选），又全面（综合评分），还深度（质量分析）。
