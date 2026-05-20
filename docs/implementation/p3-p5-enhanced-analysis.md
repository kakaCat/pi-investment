# P3-P5: 工具效能增强、持仓分析、评分优化 - 详细实施方案

## 📋 P3: 工具效能增强

### 目标
从基础的"调用次数+胜率"扩展到多维度的工具效能评估。

### 实施步骤

#### Step 1: 扩展工具效能类型

**文件**: `src/types/evolution.ts`（修改）

```typescript
export interface EnhancedToolEfficiency extends ToolEfficiency {
  // 基础指标（保留）
  tool_name: string;
  call_count: number;
  win_rate: number;
  avg_return: number;
  
  // 新增：时间分布
  timeDistribution: {
    morning: number;      // 9:30-11:30 调用次数
    afternoon: number;    // 13:00-15:00
    afterHours: number;   // 15:00+
    morningWinRate: number;
    afternoonWinRate: number;
    afterHoursWinRate: number;
  };
  
  // 新增：组合效果
  frequentCombinations: Array<{
    tools: string[];      // 常见组合（包含当前工具）
    count: number;        // 出现次数
    winRate: number;      // 组合胜率
    avgReturn: number;    // 组合平均收益
  }>;
  
  // 新增：失败分析
  failures: {
    total: number;
    dataError: number;        // 数据获取失败
    logicError: number;       // 逻辑错误
    timeoutError: number;     // 超时
    retrySuccess: number;     // 重试成功次数
  };
  
  // 新增：性能指标
  performance: {
    avgResponseTime: number;  // 平均响应时间（ms）
    p50ResponseTime: number;  // 中位数
    p95ResponseTime: number;  // 95分位
    errorRate: number;        // 错误率
    timeoutRate: number;      // 超时率
  };
}
```

#### Step 2: 实现工具组合分析器

**文件**: `src/services/intelligence/tool-combination-analyzer.ts`

```typescript
/**
 * 工具组合分析器
 * 
 * 识别常见工具序列和协同效应
 */

import type { SessionAnalysisEnhanced } from '../../types/session-analysis.js';
import type { EnhancedToolEfficiency } from '../../types/evolution.js';

/**
 * 分析工具组合效果
 */
export function analyzeToolCombinations(
  sessions: SessionAnalysisEnhanced[]
): Map<string, EnhancedToolEfficiency['frequentCombinations'][0]> {
  const combinations = new Map<string, {
    tools: string[];
    count: number;
    wins: number;
    totalReturn: number;
  }>();
  
  // 提取 N-gram（2-gram 和 3-gram）
  for (const session of sessions) {
    const sequence = session.decisionPath.toolSequence;
    
    // 2-gram
    for (let i = 0; i < sequence.length - 1; i++) {
      const pair = [sequence[i], sequence[i + 1]].sort().join('->');
      
      if (!combinations.has(pair)) {
        combinations.set(pair, {
          tools: [sequence[i], sequence[i + 1]],
          count: 0,
          wins: 0,
          totalReturn: 0,
        });
      }
      
      const combo = combinations.get(pair)!;
      combo.count++;
      
      if (session.outcome === 'profit') {
        combo.wins++;
        // TODO: 添加实际收益率
      }
    }
    
    // 3-gram
    for (let i = 0; i < sequence.length - 2; i++) {
      const triple = [sequence[i], sequence[i + 1], sequence[i + 2]].sort().join('->');
      
      if (!combinations.has(triple)) {
        combinations.set(triple, {
          tools: [sequence[i], sequence[i + 1], sequence[i + 2]],
          count: 0,
          wins: 0,
          totalReturn: 0,
        });
      }
      
      const combo = combinations.get(triple)!;
      combo.count++;
      
      if (session.outcome === 'profit') {
        combo.wins++;
      }
    }
  }
  
  // 计算胜率和平均收益
  const result = new Map<string, EnhancedToolEfficiency['frequentCombinations'][0]>();
  
  for (const [key, combo] of combinations.entries()) {
    if (combo.count >= 3) { // 至少出现3次才统计
      result.set(key, {
        tools: combo.tools,
        count: combo.count,
        winRate: combo.wins / combo.count,
        avgReturn: combo.totalReturn / combo.count,
      });
    }
  }
  
  return result;
}

/**
 * 为每个工具找到最佳组合
 */
export function findBestCombinationsForTool(
  toolName: string,
  allCombinations: Map<string, EnhancedToolEfficiency['frequentCombinations'][0]>
): EnhancedToolEfficiency['frequentCombinations'] {
  const toolCombos: EnhancedToolEfficiency['frequentCombinations'] = [];
  
  for (const [key, combo] of allCombinations.entries()) {
    if (combo.tools.includes(toolName)) {
      toolCombos.push(combo);
    }
  }
  
  // 按胜率排序，取前5
  toolCombos.sort((a, b) => b.winRate - a.winRate);
  
  return toolCombos.slice(0, 5);
}
```

#### Step 3: 增强 Session 分析器

**文件**: `src/services/intelligence/session-analyzer.ts`（修改）

```typescript
import { analyzeToolCombinations, findBestCombinationsForTool } from './tool-combination-analyzer.js';

export function analyzeSessionsAndCalculateEfficiency(
  piDir: string,
  trades: Trade[],
  windowDays?: number
): EnhancedToolEfficiency[] {
  // ... 解析 session 日志 ...
  
  // 分析工具组合
  const allCombinations = analyzeToolCombinations(enhancedSessions);
  
  // 为每个工具计算增强指标
  const enhancedStats: EnhancedToolEfficiency[] = [];
  
  for (const [toolName, basicStats] of toolStatsMap.entries()) {
    // 时间分布
    const timeDistribution = calculateTimeDistribution(toolName, enhancedSessions);
    
    // 组合效果
    const frequentCombinations = findBestCombinationsForTool(toolName, allCombinations);
    
    // 失败分析
    const failures = calculateFailures(toolName, enhancedSessions);
    
    // 性能指标
    const performance = calculatePerformance(toolName, enhancedSessions);
    
    enhancedStats.push({
      ...basicStats,
      timeDistribution,
      frequentCombinations,
      failures,
      performance,
    });
  }
  
  return enhancedStats;
}

function calculateTimeDistribution(
  toolName: string,
  sessions: SessionAnalysisEnhanced[]
): EnhancedToolEfficiency['timeDistribution'] {
  let morning = 0, afternoon = 0, afterHours = 0;
  let morningWins = 0, afternoonWins = 0, afterHoursWins = 0;
  
  for (const session of sessions) {
    if (!session.decisionPath.toolSequence.includes(toolName)) continue;
    
    const timeOfDay = session.timing.timeOfDay;
    const isWin = session.outcome === 'profit';
    
    if (timeOfDay === 'morning') {
      morning++;
      if (isWin) morningWins++;
    } else if (timeOfDay === 'afternoon') {
      afternoon++;
      if (isWin) afternoonWins++;
    } else {
      afterHours++;
      if (isWin) afterHoursWins++;
    }
  }
  
  return {
    morning,
    afternoon,
    afterHours,
    morningWinRate: morning > 0 ? morningWins / morning : 0,
    afternoonWinRate: afternoon > 0 ? afternoonWins / afternoon : 0,
    afterHoursWinRate: afterHours > 0 ? afterHoursWins / afterHours : 0,
  };
}

function calculateFailures(
  toolName: string,
  sessions: SessionAnalysisEnhanced[]
): EnhancedToolEfficiency['failures'] {
  let total = 0, dataError = 0, logicError = 0, timeoutError = 0, retrySuccess = 0;
  
  for (const session of sessions) {
    const failedTools = session.decisionPath.failedTools.filter(f => f.name === toolName);
    
    for (const failed of failedTools) {
      total++;
      
      if (failed.errorType === 'data') dataError++;
      else if (failed.errorType === 'logic') logicError++;
      else if (failed.errorType === 'timeout') timeoutError++;
      
      if (failed.retried && failed.retrySuccess) retrySuccess++;
    }
  }
  
  return { total, dataError, logicError, timeoutError, retrySuccess };
}

function calculatePerformance(
  toolName: string,
  sessions: SessionAnalysisEnhanced[]
): EnhancedToolEfficiency['performance'] {
  const responseTimes: number[] = [];
  let errorCount = 0;
  let timeoutCount = 0;
  let totalCalls = 0;
  
  for (const session of sessions) {
    const toolPerf = session.toolPerformance.find(t => t.toolName === toolName);
    
    if (toolPerf) {
      totalCalls += toolPerf.callCount;
      errorCount += toolPerf.failureCount;
      
      if (toolPerf.avgResponseTime > 0) {
        responseTimes.push(toolPerf.avgResponseTime);
      }
    }
    
    // 统计超时
    const timeouts = session.decisionPath.failedTools.filter(
      f => f.name === toolName && f.errorType === 'timeout'
    );
    timeoutCount += timeouts.length;
  }
  
  // 计算百分位
  responseTimes.sort((a, b) => a - b);
  const p50 = responseTimes[Math.floor(responseTimes.length * 0.5)] || 0;
  const p95 = responseTimes[Math.floor(responseTimes.length * 0.95)] || 0;
  const avg = responseTimes.length > 0
    ? responseTimes.reduce((sum, t) => sum + t, 0) / responseTimes.length
    : 0;
  
  return {
    avgResponseTime: Math.round(avg),
    p50ResponseTime: Math.round(p50),
    p95ResponseTime: Math.round(p95),
    errorRate: totalCalls > 0 ? errorCount / totalCalls : 0,
    timeoutRate: totalCalls > 0 ? timeoutCount / totalCalls : 0,
  };
}
```

---

## 📋 P4: 持仓维度分析

### 目标
从总体指标深入到行业、市场、个股维度的细粒度分析。

### 实施步骤

#### Step 1: 创建持仓分析器

**文件**: `src/services/intelligence/portfolio-analyzer.ts`

```typescript
/**
 * 持仓分析器
 * 
 * 按行业、市场、个股维度分析持仓表现
 */

import type { Holding, Trade } from '../portfolio/portfolio-service.js';

export interface PortfolioAnalysis {
  // 按行业分析
  bySector: Map<string, SectorAnalysis>;
  
  // 按市场分析
  byMarket: {
    A: MarketAnalysis;
    HK: MarketAnalysis;
    US: MarketAnalysis;
  };
  
  // 风险指标
  risk: RiskMetrics;
  
  // 个股表现排名
  topPerformers: StockPerformance[];
  worstPerformers: StockPerformance[];
}

export interface SectorAnalysis {
  sector: string;
  count: number;              // 持仓数量
  totalValue: number;         // 总市值
  weight: number;             // 占比
  return: number;             // 收益率
  winRate: number;            // 胜率
  contribution: number;       // 对总收益的贡献
}

export interface MarketAnalysis {
  count: number;
  value: number;
  return: number;
  winRate: number;
}

export interface RiskMetrics {
  concentration: number;        // HHI 集中度指数（0-10000）
  topHoldingWeight: number;     // 最大持仓占比
  turnoverRate: number;         // 换手率（月度）
  avgHoldingDays: number;       // 平均持仓天数
  sectorConcentration: number;  // 行业集中度
}

export interface StockPerformance {
  symbol: string;
  name: string;
  return: number;
  contribution: number;
}

/**
 * 分析持仓结构
 */
export function analyzePortfolio(
  holdings: Holding[],
  trades: Trade[]
): PortfolioAnalysis {
  // 按行业分组
  const bySector = analyzeBySector(holdings, trades);
  
  // 按市场分组
  const byMarket = analyzeByMarket(holdings, trades);
  
  // 计算风险指标
  const risk = calculateRiskMetrics(holdings, trades);
  
  // 排名
  const { topPerformers, worstPerformers } = rankStocks(holdings, trades);
  
  return {
    bySector,
    byMarket,
    risk,
    topPerformers,
    worstPerformers,
  };
}

function analyzeBySector(holdings: Holding[], trades: Trade[]): Map<string, SectorAnalysis> {
  const sectorMap = new Map<string, {
    holdings: Holding[];
    trades: Trade[];
  }>();
  
  // 分组
  for (const holding of holdings) {
    const sector = holding.sector || '未分类';
    
    if (!sectorMap.has(sector)) {
      sectorMap.set(sector, { holdings: [], trades: [] });
    }
    
    sectorMap.get(sector)!.holdings.push(holding);
  }
  
  // 关联交易
  for (const trade of trades) {
    const holding = holdings.find(h => h.symbol === trade.symbol);
    if (holding) {
      const sector = holding.sector || '未分类';
      sectorMap.get(sector)?.trades.push(trade);
    }
  }
  
  // 计算指标
  const result = new Map<string, SectorAnalysis>();
  const totalValue = holdings.reduce((sum, h) => sum + h.total_invested, 0);
  
  for (const [sector, data] of sectorMap.entries()) {
    const sectorValue = data.holdings.reduce((sum, h) => sum + h.total_invested, 0);
    const sectorReturn = calculateSectorReturn(data.holdings, data.trades);
    const winRate = calculateWinRate(data.trades);
    
    result.set(sector, {
      sector,
      count: data.holdings.length,
      totalValue: sectorValue,
      weight: sectorValue / totalValue,
      return: sectorReturn,
      winRate,
      contribution: sectorReturn * (sectorValue / totalValue),
    });
  }
  
  return result;
}

function analyzeByMarket(holdings: Holding[], trades: Trade[]): PortfolioAnalysis['byMarket'] {
  const markets = { A: [], HK: [], US: [] } as any;
  
  for (const holding of holdings) {
    if (holding.market === 'A') markets.A.push(holding);
    else if (holding.market === 'HK') markets.HK.push(holding);
    else if (holding.market === 'US') markets.US.push(holding);
  }
  
  return {
    A: calculateMarketMetrics(markets.A, trades.filter(t => t.market === 'A')),
    HK: calculateMarketMetrics(markets.HK, trades.filter(t => t.market === 'HK')),
    US: calculateMarketMetrics(markets.US, trades.filter(t => t.market === 'US')),
  };
}

function calculateMarketMetrics(holdings: Holding[], trades: Trade[]): MarketAnalysis {
  const value = holdings.reduce((sum, h) => sum + h.total_invested, 0);
  const returnPct = calculateSectorReturn(holdings, trades);
  const winRate = calculateWinRate(trades);
  
  return {
    count: holdings.length,
    value,
    return: returnPct,
    winRate,
  };
}

function calculateRiskMetrics(holdings: Holding[], trades: Trade[]): RiskMetrics {
  const totalValue = holdings.reduce((sum, h) => sum + h.total_invested, 0);
  
  // HHI 集中度（Herfindahl-Hirschman Index）
  let hhi = 0;
  for (const holding of holdings) {
    const weight = holding.total_invested / totalValue;
    hhi += weight * weight * 10000; // 转换为 0-10000 范围
  }
  
  // 最大持仓占比
  const topHoldingWeight = Math.max(...holdings.map(h => h.total_invested / totalValue));
  
  // 换手率（简化：卖出金额 / 平均持仓市值）
  const sellAmount = trades.filter(t => t.action === 'sell').reduce((sum, t) => sum + t.amount, 0);
  const turnoverRate = totalValue > 0 ? sellAmount / totalValue : 0;
  
  // 平均持仓天数
  const holdingDays = holdings.map(h => {
    const addedDate = new Date(h.added_date);
    const now = new Date();
    return (now.getTime() - addedDate.getTime()) / (1000 * 60 * 60 * 24);
  });
  const avgHoldingDays = holdingDays.length > 0
    ? holdingDays.reduce((sum, d) => sum + d, 0) / holdingDays.length
    : 0;
  
  // 行业集中度（按行业计算 HHI）
  const sectorWeights = new Map<string, number>();
  for (const holding of holdings) {
    const sector = holding.sector || '未分类';
    const weight = holding.total_invested / totalValue;
    sectorWeights.set(sector, (sectorWeights.get(sector) || 0) + weight);
  }
  
  let sectorHHI = 0;
  for (const weight of sectorWeights.values()) {
    sectorHHI += weight * weight * 10000;
  }
  
  return {
    concentration: Math.round(hhi),
    topHoldingWeight: Math.round(topHoldingWeight * 10000) / 100,
    turnoverRate: Math.round(turnoverRate * 100) / 100,
    avgHoldingDays: Math.round(avgHoldingDays),
    sectorConcentration: Math.round(sectorHHI),
  };
}

function rankStocks(holdings: Holding[], trades: Trade[]): {
  topPerformers: StockPerformance[];
  worstPerformers: StockPerformance[];
} {
  const stockPerformance: StockPerformance[] = [];
  
  for (const holding of holdings) {
    const stockTrades = trades.filter(t => t.symbol === holding.symbol);
    const returnPct = calculateStockReturn(holding, stockTrades);
    const contribution = returnPct * (holding.total_invested / holdings.reduce((sum, h) => sum + h.total_invested, 0));
    
    stockPerformance.push({
      symbol: holding.symbol,
      name: holding.name,
      return: returnPct,
      contribution,
    });
  }
  
  stockPerformance.sort((a, b) => b.return - a.return);
  
  return {
    topPerformers: stockPerformance.slice(0, 5),
    worstPerformers: stockPerformance.slice(-5).reverse(),
  };
}

// 辅助函数
function calculateSectorReturn(holdings: Holding[], trades: Trade[]): number {
  // 简化：使用加权平均
  let totalInvested = 0;
  let totalReturn = 0;
  
  for (const holding of holdings) {
    const stockTrades = trades.filter(t => t.symbol === holding.symbol);
    const returnPct = calculateStockReturn(holding, stockTrades);
    
    totalInvested += holding.total_invested;
    totalReturn += returnPct * holding.total_invested;
  }
  
  return totalInvested > 0 ? totalReturn / totalInvested : 0;
}

function calculateStockReturn(holding: Holding, trades: Trade[]): number {
  // TODO: 实现完整的收益率计算
  return 0;
}

function calculateWinRate(trades: Trade[]): number {
  const sellTrades = trades.filter(t => t.action === 'sell');
  if (sellTrades.length === 0) return 0;
  
  // TODO: 实现完整的胜率计算
  return 0.5;
}
```

---

## 📋 P5: 评分算法优化

### 目标
结合新增数据调整进化评分权重，增加市场环境因素。

### 实施步骤

#### Step 1: 重构评分函数

**文件**: `src/services/intelligence/evolution-history.ts`（修改）

```typescript
import type { MarketContext } from '../../types/market-context.js';
import type { PortfolioAnalysis } from './portfolio-analyzer.js';

/**
 * 计算进化总评分（0-100）- 优化版
 */
function calculateEvolutionScoreEnhanced(
  baseline: PerformanceMetrics,
  outcome: PerformanceMetrics,
  marketContext?: MarketContext,
  portfolioAnalysis?: PortfolioAnalysis
): number {
  // 1. 基础分（60%）
  const baseScore = calculateBaseScore(baseline, outcome);
  
  // 2. 市场调整分（20%）
  const marketScore = marketContext
    ? calculateMarketAdjustedScore(baseline, outcome, marketContext)
    : 50;
  
  // 3. 能力提升分（20%）
  const capabilityScore = calculateCapabilityScore(baseline, outcome, portfolioAnalysis);
  
  // 加权平均
  const totalScore = baseScore * 0.6 + marketScore * 0.2 + capabilityScore * 0.2;
  
  return Math.round(totalScore);
}

function calculateBaseScore(
  baseline: PerformanceMetrics,
  outcome: PerformanceMetrics
): number {
  // 收益率改善（25%）
  const returnImprovement = baseline.return !== 0
    ? (outcome.return - baseline.return) / Math.abs(baseline.return)
    : 0;
  const returnScore = Math.min(100, Math.max(0, 50 + returnImprovement * 100));
  
  // 胜率改善（20%）
  const winRateImprovement = outcome.winRate - baseline.winRate;
  const winRateScore = Math.min(100, Math.max(0, 50 + winRateImprovement * 200));
  
  // 回撤控制（15%）
  const drawdownImprovement = outcome.maxDrawdown - baseline.maxDrawdown;
  const drawdownScore = Math.min(100, Math.max(0, 50 + drawdownImprovement * 100));
  
  return (returnScore * 0.417 + winRateScore * 0.333 + drawdownScore * 0.25);
}

function calculateMarketAdjustedScore(
  baseline: PerformanceMetrics,
  outcome: PerformanceMetrics,
  marketContext: MarketContext
): number {
  // Alpha 生成能力（10%）
  const marketReturn = marketContext.indices.sh000001.return;
  const baselineAlpha = baseline.return - marketReturn;
  const outcomeAlpha = outcome.return - marketReturn;
  const alphaImprovement = outcomeAlpha - baselineAlpha;
  const alphaScore = Math.min(100, Math.max(0, 50 + alphaImprovement * 10));
  
  // 板块轮动踏准度（5%）
  // TODO: 实现板块踏准度计算
  const sectorTimingScore = 50;
  
  // 市场适应性（5%）
  const marketTrend = marketContext.indices.sh000001.trend;
  const adaptationScore = calculateAdaptationScore(outcome, marketTrend);
  
  return alphaScore * 0.5 + sectorTimingScore * 0.25 + adaptationScore * 0.25;
}

function calculateCapabilityScore(
  baseline: PerformanceMetrics,
  outcome: PerformanceMetrics,
  portfolioAnalysis?: PortfolioAnalysis
): number {
  // 工具效能提升（10%）
  const toolScore = calculateToolQualityScore(outcome.toolStats);
  
  // 决策质量提升（5%）
  // TODO: 从 session 分析中提取决策质量指标
  const decisionScore = 50;
  
  // 错误率降低（5%）
  // TODO: 从 session 分析中提取错误率
  const errorScore = 50;
  
  return toolScore * 0.5 + decisionScore * 0.25 + errorScore * 0.25;
}

function calculateAdaptationScore(
  outcome: PerformanceMetrics,
  marketTrend: 'up' | 'down' | 'sideways'
): number {
  // 牛市：收益率应该高
  if (marketTrend === 'up') {
    return outcome.return > 5 ? 80 : 50;
  }
  // 熊市：回撤控制更重要
  else if (marketTrend === 'down') {
    return outcome.maxDrawdown < 10 ? 80 : 50;
  }
  // 震荡市：胜率更重要
  else {
    return outcome.winRate > 0.5 ? 80 : 50;
  }
}
```

---

## ✅ 总体验收标准

### P3: 工具效能增强
- [ ] 时间分布统计准确
- [ ] 工具组合识别率 > 80%
- [ ] 性能指标计算正确

### P4: 持仓维度分析
- [ ] 行业分组准确
- [ ] HHI 集中度计算正确
- [ ] 风险指标合理

### P5: 评分算法优化
- [ ] Alpha 计算正确
- [ ] 市场调整分合理
- [ ] 动态权重生效

---

## 🚀 执行顺序

```bash
# 1. P3: 工具效能增强
touch src/services/intelligence/tool-combination-analyzer.ts
# 修改 session-analyzer.ts

# 2. P4: 持仓维度分析
touch src/services/intelligence/portfolio-analyzer.ts
# 集成到 evolution-service.ts

# 3. P5: 评分算法优化
# 修改 evolution-history.ts

# 4. 运行完整测试
npx tsx src/scripts/test-evolution-session.ts
```

---

## 📝 总结

完成 P3-P5 后，进化系统将具备：
- ✅ 多维度工具效能评估
- ✅ 细粒度持仓分析
- ✅ 市场环境感知的评分算法
- ✅ 更准确的归因分析
- ✅ 更公平的进化效果评估
