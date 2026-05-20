# P1: 市场环境数据收集 - 详细实施方案

## 📋 目标

将硬编码的市场参考值（`market: 5`）替换为真实的大盘指数、板块表现和市场情绪数据。

---

## 🎯 核心功能

### 1. 大盘指数数据
- 上证指数（sh000001）
- 深证成指（sz399001）
- 创业板指（sz399006）
- 恒生指数（HSI）

### 2. 板块表现数据
- 行业资金流向排名
- 板块收益率
- 板块动量指标

### 3. 市场情绪指标
- 涨跌家数比
- 成交量比（今日/5日均）
- 市场广度（上涨股票占比）

---

## 📁 文件结构

```
src/services/intelligence/
├── market-data-collector.ts       # 主收集器
├── market-data-collector.test.ts  # 单元测试
└── types/
    └── market-context.ts          # 类型定义
```

---

## 🔧 实施步骤

### Step 1: 创建类型定义

**文件**: `src/types/market-context.ts`

```typescript
/**
 * 市场环境上下文
 */
export interface MarketContext {
  // 大盘指数
  indices: {
    sh000001: IndexMetrics;  // 上证指数
    sz399001: IndexMetrics;  // 深证成指
    sz399006: IndexMetrics;  // 创业板指
    hsi?: IndexMetrics;      // 恒生指数（可选）
  };
  
  // 板块表现
  sectorPerformance: SectorMetrics[];
  
  // 市场情绪
  sentiment: MarketSentiment;
  
  // 时间窗口
  period: {
    start: string;  // ISO date
    end: string;    // ISO date
    days: number;
  };
  
  // 数据质量
  dataQuality: {
    indicesAvailable: number;     // 可用指数数量
    sectorsAvailable: number;     // 可用板块数量
    sentimentComplete: boolean;   // 情绪数据是否完整
    reliability: 'high' | 'medium' | 'low';
  };
}

export interface IndexMetrics {
  code: string;
  name: string;
  return: number;           // 收益率（%）
  volatility: number;       // 波动率（标准差）
  trend: 'up' | 'down' | 'sideways';
  currentPrice: number;
  startPrice: number;
  highPrice: number;
  lowPrice: number;
}

export interface SectorMetrics {
  sector: string;           // 板块名称
  return: number;           // 收益率（%）
  rank: number;             // 排名（1-N）
  momentum: number;         // 动量指标（近5日收益率）
  fundFlow: number;         // 资金流向（亿元）
  leadingStocks: string[];  // 龙头股票
}

export interface MarketSentiment {
  advanceDeclineRatio: number;  // 涨跌家数比（上涨/下跌）
  volumeRatio: number;          // 成交量比（今日/5日均）
  marketBreadth: number;        // 市场广度（上涨股票占比 0-1）
  volatilityIndex: number;      // 波动率指数
  sentiment: 'bullish' | 'bearish' | 'neutral';
}
```

---

### Step 2: 实现市场数据收集器

**文件**: `src/services/intelligence/market-data-collector.ts`

```typescript
/**
 * 市场数据收集器
 * 
 * 从 akshare 获取大盘指数、板块表现、市场情绪数据
 */

import { callPython } from '../../infrastructure/tools/shared/python-caller.js';
import type { MarketContext, IndexMetrics, SectorMetrics, MarketSentiment } from '../../types/market-context.js';

// ─── 配置 ────────────────────────────────────────────────────────────────

const INDICES = [
  { code: 'sh000001', name: '上证指数' },
  { code: 'sz399001', name: '深证成指' },
  { code: 'sz399006', name: '创业板指' },
];

const DEFAULT_DAYS = 90; // 默认时间窗口

// ─── 主函数 ──────────────────────────────────────────────────────────────

/**
 * 收集市场环境数据
 */
export async function collectMarketContext(
  startDate?: string,
  endDate?: string,
  days: number = DEFAULT_DAYS
): Promise<MarketContext> {
  // 计算时间窗口
  const period = calculatePeriod(startDate, endDate, days);
  
  console.log(`[市场数据] 收集时间窗口: ${period.start} ~ ${period.end} (${period.days}天)`);
  
  // 并行收集数据
  const [indices, sectorPerformance, sentiment] = await Promise.all([
    collectIndices(period.start, period.end),
    collectSectorPerformance(period.start, period.end),
    collectMarketSentiment(period.end),
  ]);
  
  // 评估数据质量
  const dataQuality = evaluateDataQuality(indices, sectorPerformance, sentiment);
  
  return {
    indices: {
      sh000001: indices.find(i => i.code === 'sh000001')!,
      sz399001: indices.find(i => i.code === 'sz399001')!,
      sz399006: indices.find(i => i.code === 'sz399006')!,
    },
    sectorPerformance,
    sentiment,
    period,
    dataQuality,
  };
}

// ─── 指数数据 ────────────────────────────────────────────────────────────

/**
 * 收集大盘指数数据
 */
async function collectIndices(startDate: string, endDate: string): Promise<IndexMetrics[]> {
  const results: IndexMetrics[] = [];
  
  for (const { code, name } of INDICES) {
    try {
      const data = await getIndexHistory(code, startDate, endDate);
      const metrics = calculateIndexMetrics(code, name, data);
      results.push(metrics);
    } catch (error) {
      console.warn(`[市场数据] 获取指数 ${code} 失败:`, error);
      // 使用降级数据
      results.push(createFallbackIndexMetrics(code, name));
    }
  }
  
  return results;
}

/**
 * 获取指数历史数据
 */
async function getIndexHistory(code: string, startDate: string, endDate: string): Promise<any[]> {
  const result = await callPython('get_index_history', {
    symbol: code,
    start_date: startDate,
    end_date: endDate,
  });
  
  if (!result.success || !result.data) {
    throw new Error(`获取指数 ${code} 历史数据失败`);
  }
  
  return result.data;
}

/**
 * 计算指数指标
 */
function calculateIndexMetrics(code: string, name: string, data: any[]): IndexMetrics {
  if (data.length === 0) {
    return createFallbackIndexMetrics(code, name);
  }
  
  // 按日期排序
  const sorted = data.sort((a, b) => new Date(a.date).getTime() - new Date(b.date).getTime());
  
  const startPrice = sorted[0].close;
  const endPrice = sorted[sorted.length - 1].close;
  const highPrice = Math.max(...sorted.map(d => d.high));
  const lowPrice = Math.min(...sorted.map(d => d.low));
  
  // 收益率
  const returnPct = ((endPrice - startPrice) / startPrice) * 100;
  
  // 波动率（日收益率的标准差）
  const dailyReturns = sorted.slice(1).map((d, i) => 
    ((d.close - sorted[i].close) / sorted[i].close) * 100
  );
  const volatility = calculateStdDev(dailyReturns);
  
  // 趋势判断
  const trend = determineTrend(returnPct, volatility);
  
  return {
    code,
    name,
    return: Math.round(returnPct * 100) / 100,
    volatility: Math.round(volatility * 100) / 100,
    trend,
    currentPrice: endPrice,
    startPrice,
    highPrice,
    lowPrice,
  };
}

/**
 * 判断趋势
 */
function determineTrend(returnPct: number, volatility: number): 'up' | 'down' | 'sideways' {
  // 如果收益率绝对值小于波动率，认为是横盘
  if (Math.abs(returnPct) < volatility) {
    return 'sideways';
  }
  
  return returnPct > 0 ? 'up' : 'down';
}

/**
 * 降级指数数据（数据获取失败时使用）
 */
function createFallbackIndexMetrics(code: string, name: string): IndexMetrics {
  return {
    code,
    name,
    return: 0,
    volatility: 0,
    trend: 'sideways',
    currentPrice: 0,
    startPrice: 0,
    highPrice: 0,
    lowPrice: 0,
  };
}

// ─── 板块数据 ────────────────────────────────────────────────────────────

/**
 * 收集板块表现数据
 */
async function collectSectorPerformance(startDate: string, endDate: string): Promise<SectorMetrics[]> {
  try {
    // 获取板块资金流向
    const fundFlowData = await getSectorFundFlow(endDate);
    
    // 获取板块涨跌幅
    const sectorReturns = await getSectorReturns(startDate, endDate);
    
    // 合并数据
    const sectors = mergeSectorData(fundFlowData, sectorReturns);
    
    // 排序并添加排名
    sectors.sort((a, b) => b.return - a.return);
    sectors.forEach((s, i) => s.rank = i + 1);
    
    return sectors;
  } catch (error) {
    console.warn('[市场数据] 获取板块数据失败:', error);
    return [];
  }
}

/**
 * 获取板块资金流向
 */
async function getSectorFundFlow(date: string): Promise<any[]> {
  const result = await callPython('get_sector_fund_flow', { date });
  
  if (!result.success || !result.data) {
    throw new Error('获取板块资金流向失败');
  }
  
  return result.data;
}

/**
 * 获取板块涨跌幅
 */
async function getSectorReturns(startDate: string, endDate: string): Promise<Map<string, number>> {
  // 这里简化处理，实际可以调用更详细的接口
  // 暂时从资金流向数据中提取涨跌幅
  return new Map();
}

/**
 * 合并板块数据
 */
function mergeSectorData(fundFlowData: any[], sectorReturns: Map<string, number>): SectorMetrics[] {
  return fundFlowData.slice(0, 20).map((item, index) => ({
    sector: item.sector || item.name,
    return: item.change_pct || sectorReturns.get(item.sector) || 0,
    rank: index + 1,
    momentum: item.change_pct || 0,
    fundFlow: item.net_inflow || 0,
    leadingStocks: item.leading_stocks || [],
  }));
}

// ─── 市场情绪 ────────────────────────────────────────────────────────────

/**
 * 收集市场情绪数据
 */
async function collectMarketSentiment(date: string): Promise<MarketSentiment> {
  try {
    // 获取涨跌家数
    const advanceDecline = await getAdvanceDeclineData(date);
    
    // 获取成交量数据
    const volumeData = await getVolumeData(date);
    
    // 计算市场广度
    const marketBreadth = advanceDecline.advance / (advanceDecline.advance + advanceDecline.decline);
    
    // 计算涨跌家数比
    const advanceDeclineRatio = advanceDecline.advance / advanceDecline.decline;
    
    // 计算成交量比
    const volumeRatio = volumeData.today / volumeData.avg5;
    
    // 判断市场情绪
    const sentiment = determineSentiment(marketBreadth, advanceDeclineRatio);
    
    return {
      advanceDeclineRatio: Math.round(advanceDeclineRatio * 100) / 100,
      volumeRatio: Math.round(volumeRatio * 100) / 100,
      marketBreadth: Math.round(marketBreadth * 100) / 100,
      volatilityIndex: 0, // TODO: 实现波动率指数
      sentiment,
    };
  } catch (error) {
    console.warn('[市场数据] 获取市场情绪失败:', error);
    return createFallbackSentiment();
  }
}

/**
 * 获取涨跌家数
 */
async function getAdvanceDeclineData(date: string): Promise<{ advance: number; decline: number }> {
  const result = await callPython('get_market_overview', {});
  
  if (!result.success || !result.data) {
    throw new Error('获取涨跌家数失败');
  }
  
  // 从市场概览中提取涨跌家数
  const data = result.data;
  return {
    advance: data.up_count || 0,
    decline: data.down_count || 0,
  };
}

/**
 * 获取成交量数据
 */
async function getVolumeData(date: string): Promise<{ today: number; avg5: number }> {
  // 简化处理，实际应该获取历史成交量
  return {
    today: 1,
    avg5: 1,
  };
}

/**
 * 判断市场情绪
 */
function determineSentiment(marketBreadth: number, advanceDeclineRatio: number): 'bullish' | 'bearish' | 'neutral' {
  if (marketBreadth > 0.6 && advanceDeclineRatio > 1.5) {
    return 'bullish';
  } else if (marketBreadth < 0.4 && advanceDeclineRatio < 0.67) {
    return 'bearish';
  } else {
    return 'neutral';
  }
}

/**
 * 降级情绪数据
 */
function createFallbackSentiment(): MarketSentiment {
  return {
    advanceDeclineRatio: 1,
    volumeRatio: 1,
    marketBreadth: 0.5,
    volatilityIndex: 0,
    sentiment: 'neutral',
  };
}

// ─── 工具函数 ────────────────────────────────────────────────────────────

/**
 * 计算时间窗口
 */
function calculatePeriod(
  startDate?: string,
  endDate?: string,
  days: number = DEFAULT_DAYS
): { start: string; end: string; days: number } {
  const end = endDate || new Date().toISOString().split('T')[0];
  
  let start: string;
  if (startDate) {
    start = startDate;
  } else {
    const startDateObj = new Date(end);
    startDateObj.setDate(startDateObj.getDate() - days);
    start = startDateObj.toISOString().split('T')[0];
  }
  
  // 计算实际天数
  const actualDays = Math.floor(
    (new Date(end).getTime() - new Date(start).getTime()) / (1000 * 60 * 60 * 24)
  );
  
  return { start, end, days: actualDays };
}

/**
 * 计算标准差
 */
function calculateStdDev(values: number[]): number {
  if (values.length === 0) return 0;
  
  const mean = values.reduce((sum, v) => sum + v, 0) / values.length;
  const variance = values.reduce((sum, v) => sum + Math.pow(v - mean, 2), 0) / values.length;
  
  return Math.sqrt(variance);
}

/**
 * 评估数据质量
 */
function evaluateDataQuality(
  indices: IndexMetrics[],
  sectors: SectorMetrics[],
  sentiment: MarketSentiment
): MarketContext['dataQuality'] {
  const indicesAvailable = indices.filter(i => i.return !== 0).length;
  const sectorsAvailable = sectors.length;
  const sentimentComplete = sentiment.advanceDeclineRatio > 0;
  
  let reliability: 'high' | 'medium' | 'low';
  if (indicesAvailable >= 3 && sectorsAvailable >= 10 && sentimentComplete) {
    reliability = 'high';
  } else if (indicesAvailable >= 2 && sectorsAvailable >= 5) {
    reliability = 'medium';
  } else {
    reliability = 'low';
  }
  
  return {
    indicesAvailable,
    sectorsAvailable,
    sentimentComplete,
    reliability,
  };
}

// ─── 导出 ────────────────────────────────────────────────────────────────

export {
  collectIndices,
  collectSectorPerformance,
  collectMarketSentiment,
};
```

---

### Step 3: 添加 Python 桥接函数

**文件**: `python/akshare_bridge.py`（添加新函数）

```python
def get_index_history(symbol: str, start_date: str, end_date: str):
    """获取指数历史数据"""
    try:
        # 转换代码格式
        if symbol.startswith('sh'):
            code = symbol[2:]
        elif symbol.startswith('sz'):
            code = symbol[2:]
        else:
            code = symbol
        
        # 获取指数日线数据
        df = ak.stock_zh_index_daily(symbol=code)
        
        # 过滤日期范围
        df = df[(df['date'] >= start_date) & (df['date'] <= end_date)]
        
        # 转换为字典列表
        result = df.to_dict('records')
        
        return {
            'success': True,
            'data': result
        }
    except Exception as e:
        return {
            'success': False,
            'error': str(e)
        }
```

---

### Step 4: 集成到进化服务

**文件**: `src/services/intelligence/evolution-service.ts`（修改）

```typescript
import { collectMarketContext } from './market-data-collector.js';

// 在 runWeeklyEvolution 函数中添加

export async function runWeeklyEvolution(config: EvolutionConfig = {}): Promise<EvolutionResult> {
  // ... 现有代码 ...
  
  // ── 新增：收集市场环境数据 ────────────────────────────────────────────
  console.log('[进化] 收集市场环境数据...');
  const marketContext = await collectMarketContext(
    dataQuality.earliestTradeDate ?? undefined,
    dataQuality.latestTradeDate ?? undefined,
    finalConfig.tradeWindowDays
  );
  
  console.log(`[进化] 市场环境:`);
  console.log(`  - 上证指数: ${marketContext.indices.sh000001.return.toFixed(2)}% (${marketContext.indices.sh000001.trend})`);
  console.log(`  - 深证成指: ${marketContext.indices.sz399001.return.toFixed(2)}% (${marketContext.indices.sz399001.trend})`);
  console.log(`  - 市场情绪: ${marketContext.sentiment.sentiment}`);
  console.log(`  - 数据质量: ${marketContext.dataQuality.reliability}`);
  
  // ── 3. 收益率（使用真实市场数据）────────────────────────────────────────
  const target = finalConfig.targetReturn;
  const actual = realizedReturn;
  const market = marketContext.indices.sh000001.return; // 使用上证指数作为市场基准
  
  // ... 其余代码保持不变 ...
  
  // ── 在报告中添加市场环境 ────────────────────────────────────────────
  const report = generateEvolutionReport({
    // ... 现有字段 ...
    marketContext, // 新增字段
  });
}
```

---

### Step 5: 更新报告生成器

**文件**: `src/services/intelligence/evolution-reporter.ts`（修改）

在报告中添加市场环境章节：

```typescript
function formatReportAsMarkdown(
  report: EvolutionReport,
  recentEvolutions: EvolutionHistory[],
  experienceSummary: ExperienceSummary | undefined,
  comparison: ComparisonResult,
  marketContext?: MarketContext // 新增参数
): string {
  // ... 现有代码 ...
  
  // 新增：市场环境章节
  if (marketContext) {
    md += '\n## 📊 市场环境\n\n';
    md += '### 大盘指数\n\n';
    md += '| 指数 | 收益率 | 趋势 | 波动率 |\n';
    md += '|------|--------|------|--------|\n';
    
    for (const [key, index] of Object.entries(marketContext.indices)) {
      const trendEmoji = index.trend === 'up' ? '📈' : index.trend === 'down' ? '📉' : '➡️';
      md += `| ${index.name} | ${index.return.toFixed(2)}% | ${trendEmoji} ${index.trend} | ${index.volatility.toFixed(2)}% |\n`;
    }
    
    md += '\n### 板块表现 Top 10\n\n';
    md += '| 排名 | 板块 | 收益率 | 资金流向 |\n';
    md += '|------|------|--------|----------|\n';
    
    marketContext.sectorPerformance.slice(0, 10).forEach(sector => {
      md += `| ${sector.rank} | ${sector.sector} | ${sector.return.toFixed(2)}% | ${sector.fundFlow.toFixed(2)}亿 |\n`;
    });
    
    md += '\n### 市场情绪\n\n';
    const sentimentEmoji = marketContext.sentiment.sentiment === 'bullish' ? '🐂' : 
                          marketContext.sentiment.sentiment === 'bearish' ? '🐻' : '😐';
    md += `- **情绪**: ${sentimentEmoji} ${marketContext.sentiment.sentiment}\n`;
    md += `- **涨跌家数比**: ${marketContext.sentiment.advanceDeclineRatio.toFixed(2)}\n`;
    md += `- **市场广度**: ${(marketContext.sentiment.marketBreadth * 100).toFixed(1)}%\n`;
    md += `- **成交量比**: ${marketContext.sentiment.volumeRatio.toFixed(2)}x\n\n`;
  }
  
  // ... 其余代码 ...
}
```

---

## ✅ 验收标准

### 功能测试
- [ ] 能成功获取上证、深证、创业板指数数据
- [ ] 能成功获取板块资金流向数据
- [ ] 能成功获取市场情绪数据
- [ ] 数据获取失败时有降级策略
- [ ] 数据质量评估准确

### 性能测试
- [ ] 数据收集耗时 < 30s
- [ ] 并行请求正常工作
- [ ] 内存占用合理（< 50MB）

### 集成测试
- [ ] 进化报告中正确显示市场环境
- [ ] 归因分析使用真实市场数据
- [ ] Alpha 计算正确（实际收益 - 市场收益）

---

## 🚀 执行命令

```bash
# 1. 创建类型定义
touch src/types/market-context.ts

# 2. 创建市场数据收集器
touch src/services/intelligence/market-data-collector.ts

# 3. 添加 Python 函数
# 编辑 python/akshare_bridge.py

# 4. 运行测试
npm run test:market-data

# 5. 集成到进化服务
# 编辑 src/services/intelligence/evolution-service.ts

# 6. 运行完整进化测试
npx tsx src/scripts/test-evolution-session.ts
```

---

## 📝 注意事项

1. **数据缓存**: 市场数据可以按日期缓存，避免重复请求
2. **错误处理**: 每个数据源都要有降级策略
3. **性能优化**: 使用 Promise.all 并行请求
4. **数据验证**: 检查返回数据的合理性（如收益率不应超过 ±50%）
5. **日志记录**: 记录数据获取的成功/失败情况

---

## 🔗 下一步

完成 P1 后，继续实施 **P2: Session 日志解析**。
