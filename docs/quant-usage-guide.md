# 量化功能使用指南

## 如何判断股票买不买？

量化系统通过**技术指标 + 量化评分 + 策略信号 + 历史经验**四个维度综合判断。

---

## 一、快速上手：一键分析

### 使用 `analyze_stock_quant` 工具

这是最简单的方式，一次调用完成所有分析：

```typescript
import { analyzeStockQuantTool } from './infrastructure/tools/quant-decision-tools';

const result = await analyzeStockQuantTool.execute('call-id', {
  symbol: '000425',  // 股票代码
  days: 60           // 分析天数
});
```

### 输出示例

```
徐工机械(000425) 量化综合分析
=====================================
综合评分: 50/100 (中性)
建议操作: 观察等待
置信度: 50%

技术面信号:
✓ 跌破布林下轨 - 超卖反弹机会

量化策略触发 (0个):
- 暂无策略触发

历史经验:
暂无相关历史经验

当前价格: ¥10.02
技术指标: RSI=44.6 | MACD=0.00 | MA5=10.02
```

---

## 二、判断逻辑详解

### 1. 综合评分（0-100分）

| 分数区间 | 建议操作 | 说明 |
|---------|---------|------|
| 80-100 | 强烈买入 | 多个指标共振，高置信度 |
| 60-79 | 买入 | 技术面偏多，可以建仓 |
| 40-59 | 观察等待 | 信号不明确，保持观望 |
| 20-39 | 卖出 | 技术面偏空，减仓为主 |
| 0-19 | 强烈卖出 | 多个风险信号，清仓 |

### 2. 评分构成（多因子模型）

```
总分 = RSI因子(25分) + MACD因子(20分) + 均线因子(20分) 
     + 布林带因子(15分) + 成交量因子(20分)
```

**各因子判断标准：**

- **RSI因子（25分）**
  - RSI < 30：超卖，20-25分（买入信号）
  - 30 ≤ RSI ≤ 70：中性，10-20分
  - RSI > 70：超买，0-10分（卖出信号）

- **MACD因子（20分）**
  - 金叉（DIF上穿DEA）：15-20分
  - 死叉（DIF下穿DEA）：0-5分
  - 中性：5-15分

- **均线因子（20分）**
  - 多头排列（MA5>MA10>MA20>MA60）：15-20分
  - 空头排列：0-5分
  - 中性：5-15分

- **布林带因子（15分）**
  - 跌破下轨：10-15分（超卖反弹）
  - 突破上轨：0-5分（超买回调）
  - 中轨附近：5-10分

- **成交量因子（20分）**
  - 放量上涨：15-20分
  - 缩量下跌：10-15分
  - 量价背离：0-5分

### 3. 策略信号触发

系统会自动匹配19个预设策略，检查是否触发买卖信号：

```
量化策略触发 (2个):
- RSI超卖反转策略: 买入信号 (置信度85%)
- 均线金叉策略: 买入信号 (置信度72%)
```

### 4. 历史经验参考

查询相似场景的历史表现：

```
历史经验 (1条):
场景: RSI超卖反弹
建议: aggressive
胜率: 100.0%
平均收益: 7.28%
```

---

## 三、分步分析（高级用法）

如果需要更细粒度的控制，可以分步调用：

### Step 1: 获取技术信号

```typescript
import { getTechnicalSignalsTool } from './infrastructure/tools/quant-analysis-tools';

const signals = await getTechnicalSignalsTool.execute('id', {
  symbol: '000425',
  days: 60
});
```

输出：
```
技术指标:
○ RSI中性(44.6)
○ MACD中性
✗ 均线空头排列
✓ 跌破布林下轨 - 超卖反弹
```

### Step 2: 计算量化评分

```typescript
import { getQuantScoreTool } from './infrastructure/tools/quant-analysis-tools';

const score = await getQuantScoreTool.execute('id', {
  symbol: '000425',
  days: 60
});
```

输出：
```
综合评分: 50/100 (中性)

因子得分明细:
- RSI因子: 15/25
- MACD因子: 5/20
- 均线因子: 5/20
- 布林带因子: 15/15
- 成交量因子: 10/20
```

### Step 3: 查询历史经验

```typescript
import { querySimilarCasesTool } from './infrastructure/tools/quant-analysis-tools';

const experience = await querySimilarCasesTool.execute('id', {
  scenario: 'RSI超卖反弹',
  limit: 3
});
```

---

## 四、批量对比（多股票）

对比多只股票，找出最优标的：

```typescript
import { compareStocksQuantTool } from './infrastructure/tools/quant-decision-tools';

const comparison = await compareStocksQuantTool.execute('id', {
  symbols: ['000425', '600036', '601088'],
  days: 60
});
```

输出会按评分排序，推荐最优股票。

---

## 五、决策验证

验证你的买卖决策是否合理：

```typescript
import { validateTradeDecisionTool } from './infrastructure/tools/quant-decision-tools';

const validation = await validateTradeDecisionTool.execute('id', {
  symbol: '000425',
  action: 'BUY',  // 或 'SELL'
  days: 60
});
```

输出会告诉你：
- 决策是否合理
- 支持/反对的理由
- 风险提示
- 建议仓位

---

## 六、实战案例

### 案例1：寻找超卖反弹机会

```typescript
// 1. 分析股票
const result = await analyzeStockQuantTool.execute('id', {
  symbol: '600036',
  days: 60
});

// 判断逻辑：
// - 综合评分 > 60 ✓
// - RSI < 30（超卖）✓
// - 跌破布林下轨 ✓
// - 策略触发"RSI超卖反转" ✓
// → 结论：可以买入
```

### 案例2：持仓股票要不要卖

```typescript
// 1. 验证卖出决策
const validation = await validateTradeDecisionTool.execute('id', {
  symbol: '000425',
  action: 'SELL',
  days: 60
});

// 判断逻辑：
// - 综合评分 < 40（偏空）✓
// - RSI > 70（超买）✓
// - MACD死叉 ✓
// - 均线空头排列 ✓
// → 结论：建议卖出
```

### 案例3：多只股票选哪个

```typescript
// 1. 批量对比
const comparison = await compareStocksQuantTool.execute('id', {
  symbols: ['000425', '600036', '601088', '600900'],
  days: 60
});

// 输出会按评分排序：
// 1. 601088 (85分) - 强烈买入
// 2. 600036 (75分) - 买入
// 3. 000425 (50分) - 观察
// 4. 600900 (30分) - 卖出
// → 结论：优先买入 601088
```

---

## 七、注意事项

### 1. 量化不是万能的

- 量化只是辅助决策工具，不能替代基本面分析
- 需要结合公司财务、行业趋势、市场环境综合判断
- 历史表现不代表未来收益

### 2. 评分的局限性

- 评分基于技术指标，不考虑突发消息
- 不同市场环境下，同样评分的含义不同
- 建议结合多个时间周期（日线、周线）分析

### 3. 风险控制

- 即使评分很高，也要设置止损（建议8-10%）
- 分批建仓，不要一次性满仓
- 关注成交量，避免流动性风险

### 4. 最佳实践

- **买入时机**：评分 > 60 + 策略触发 + 历史经验支持
- **卖出时机**：评分 < 40 或 达到止盈/止损位
- **观望时机**：评分 40-60，等待更明确信号
- **仓位管理**：
  - 80-100分：可考虑重仓（30-50%）
  - 60-79分：中等仓位（10-30%）
  - 40-59分：轻仓或观望（0-10%）

---

## 八、集成到投资流程

量化系统已集成到 SOUL.md 的 Phase 4B：

```
Phase 4B: 量化验证（强制）
1. 调用 analyze_stock_quant 获取量化评分
2. 如果评分 < 60，需要额外说明理由
3. 如果评分 > 80，可以提高置信度
```

在做投资决策时，系统会自动调用量化工具进行验证。

---

## 九、常见问题

**Q: 评分50分，到底买不买？**
A: 50分是中性，建议观望。等评分上升到60+或有明确策略触发再买入。

**Q: 为什么有时候没有策略触发？**
A: 19个策略都有特定条件，当前技术形态可能不符合任何策略的入场条件。

**Q: 历史经验为空怎么办？**
A: 说明当前场景比较新，没有历史案例。这时更要谨慎，降低仓位。

**Q: 多个策略触发，听哪个？**
A: 看置信度。置信度高的策略优先，或者多个策略共振时信号更强。

**Q: 评分和实际走势不符？**
A: 量化是概率游戏，不是100%准确。建议：
  - 结合基本面分析
  - 设置止损保护
  - 多次验证后再决策
