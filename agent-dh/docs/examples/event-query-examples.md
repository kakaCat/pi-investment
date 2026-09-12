# 事件查询使用示例（P1-4）

本文档提供事件查询的实战示例，帮助快速上手 `event_calendar_check` 和 `stock_events` 两个工具。

---

## 示例 1: 每日盘前例行检查 ⭐

**目标**: 每天开盘前了解重大事件

```typescript
// 步骤 1: 查宏观事件（未来 2 天）
const macroEvents = await event_calendar_check({ 
  mode: 'upcoming', 
  days: 2 
});

console.log(`未来 2 天有 ${macroEvents.count} 个宏观事件`);

// 重点关注高重要性事件
const highImportance = macroEvents.events.filter(e => e.importance === 3);
if (highImportance.length > 0) {
  console.log('🔴 高重要性事件：');
  highImportance.forEach(e => {
    console.log(`  - ${e.event_date} ${e.title}`);
  });
}

// 步骤 2: 查持仓股票事件
const positions = await position_list();
for (const pos of positions) {
  const stockEvents = await stock_events({ symbol: pos.symbol });
  
  if (stockEvents.upcoming_count > 0) {
    console.log(`⚠️ ${pos.name}(${pos.symbol}) 有 ${stockEvents.upcoming_count} 个即将发生的事件`);
    
    // 展示未来事件
    const today = new Date().toISOString().slice(0, 10);
    const upcoming = stockEvents.events.filter(e => e.event_date >= today);
    upcoming.forEach(e => {
      console.log(`  - ${e.event_date} [${e.event_type}] ${e.title}`);
    });
  }
}
```

---

## 示例 2: 买入前排雷流程 🛡️

**目标**: 买入前确认无重大风险事件

```typescript
async function buyWithEventCheck(symbol: string, quantity: number, price: number) {
  console.log(`准备买入 ${symbol}，先进行事件排雷...`);
  
  // 步骤 1: 查询个股事件
  const events = await stock_events({ symbol });
  
  console.log(`找到 ${events.count} 条事件记录，其中 ${events.upcoming_count} 条即将发生`);
  
  // 步骤 2: 分析未来事件
  if (events.upcoming_count === 0) {
    console.log('✅ 未来无重大事件，可以买入');
    return await portfolio_trade({ 
      action: 'BUY', 
      symbol, 
      quantity, 
      price,
      reason: '事件排雷通过，无重大风险事件'
    });
  }
  
  // 步骤 3: 重点检查高风险事件
  const today = new Date().toISOString().slice(0, 10);
  const upcoming = events.events.filter(e => e.event_date >= today);
  
  const highRiskTypes = ['unlock', 'placement', 'regulatory', 'shareholder_meeting'];
  const highRiskEvents = upcoming.filter(e => highRiskTypes.includes(e.event_type));
  
  if (highRiskEvents.length > 0) {
    console.log('🔴 发现高风险事件：');
    highRiskEvents.forEach(e => {
      console.log(`  - ${e.event_date} [${e.event_type}] ${e.title}`);
      if (e.event_type === 'unlock' && e.unlock_ratio) {
        console.log(`    解禁占比: ${e.unlock_ratio}%`);
      }
    });
    
    // 决策：解禁占比 > 5% 则暂缓
    const bigUnlock = highRiskEvents.find(e => 
      e.event_type === 'unlock' && e.unlock_ratio > 5
    );
    
    if (bigUnlock) {
      console.log('❌ 发现大额解禁（>5%），建议暂缓买入');
      return { success: false, reason: '大额解禁风险' };
    }
  }
  
  // 步骤 4: 中低风险事件，记录后买入
  console.log('⚠️ 有事件但风险可控，记录后买入');
  
  await decision_audit({
    action: 'record',
    decision_subtype: 'trade',
    reasoning: `事件排雷：upcoming_count=${events.upcoming_count}，无重大风险`,
    parameters: { symbol, action: 'BUY', quantity, price }
  });
  
  return await portfolio_trade({ 
    action: 'BUY', 
    symbol, 
    quantity, 
    price,
    reason: `事件排雷通过，${events.upcoming_count}个事件但风险可控`
  });
}

// 使用示例
await buyWithEventCheck('600519', 100, 1850);
```

---

## 示例 3: 事件驱动策略 📊

**目标**: 基于事件日历制定交易策略

```typescript
// 场景：财报季前布局
async function earningsSeasonStrategy() {
  console.log('📊 财报季事件驱动策略');
  
  // 步骤 1: 查询本月有财报的股票
  const startDate = '2026-09-01';
  const endDate = '2026-09-30';
  
  const calendar = await event_calendar_check({
    mode: 'range',
    start: startDate,
    end: endDate,
    event_type: 'earnings',
    scope: 'individual'  // 个股财报
  });
  
  console.log(`本月有 ${calendar.count} 只股票披露财报`);
  
  // 步骤 2: 筛选符合条件的股票
  const candidates = [];
  
  for (const event of calendar.events) {
    if (!event.symbol) continue;
    
    // 查询详细事件
    const stockEvents = await stock_events({ symbol: event.symbol });
    
    // 查询基本面
    const financial = await data_fetch_financial({ symbol: event.symbol });
    
    // 筛选逻辑：
    // 1. ROE > 15%
    // 2. PE < 30
    // 3. 无重大解禁
    const hasUnlock = stockEvents.events.some(e => 
      e.event_type === 'unlock' && 
      e.event_date >= event.event_date &&
      e.unlock_ratio > 3
    );
    
    if (financial.roe > 15 && financial.pe_ttm < 30 && !hasUnlock) {
      candidates.push({
        symbol: event.symbol,
        name: financial.name,
        earningsDate: event.event_date,
        roe: financial.roe,
        pe: financial.pe_ttm
      });
    }
  }
  
  console.log(`筛选出 ${candidates.length} 只候选股票`);
  candidates.forEach(c => {
    console.log(`  - ${c.name}(${c.symbol}): 财报日 ${c.earningsDate}, ROE ${c.roe}%, PE ${c.pe}`);
  });
  
  return candidates;
}

await earningsSeasonStrategy();
```

---

## 示例 4: 宏观事件影响评估 🌍

**目标**: 评估宏观事件对持仓的影响

```typescript
async function assessMacroImpact() {
  // 步骤 1: 查询近期宏观事件
  const macroEvents = await event_calendar_check({
    mode: 'range',
    start: '2026-09-11',
    end: '2026-09-18',
    scope: 'macro'
  });
  
  console.log(`本周有 ${macroEvents.count} 个宏观事件`);
  
  // 步骤 2: 识别高影响事件
  const highImpact = macroEvents.events.filter(e => 
    e.importance === 3 &&
    ['cpi_ppi', 'pmi', 'fomc', 'lpr'].includes(e.event_type)
  );
  
  if (highImpact.length === 0) {
    console.log('✅ 本周无高影响宏观事件');
    return;
  }
  
  console.log(`⚠️ 本周有 ${highImpact.length} 个高影响事件：`);
  highImpact.forEach(e => {
    console.log(`  - ${e.event_date} ${e.title}`);
  });
  
  // 步骤 3: 评估持仓风险
  const positions = await position_list();
  const regime = await regime_position_limit();
  
  console.log(`当前 regime: ${regime.regime}，持仓: ${regime.current_position_pct}%`);
  
  // 决策：高影响事件期间降低仓位
  if (highImpact.length > 0 && regime.current_position_pct > 60) {
    console.log('💡 建议：高影响事件期间降低仓位至 50%');
    
    // 记录决策
    await decision_audit({
      action: 'record',
      decision_subtype: 'risk_control',
      reasoning: `宏观事件风险管理：${highImpact.length}个高影响事件，降低仓位`,
      context: { macroEvents: highImpact.map(e => e.title) }
    });
  }
}

await assessMacroImpact();
```

---

## 示例 5: 行业政策监控 📜

**目标**: 监控行业政策变化

```typescript
async function monitorIndustryPolicy() {
  // 查询本月行业政策事件
  const policyEvents = await event_calendar_check({
    mode: 'range',
    start: '2026-09-01',
    end: '2026-09-30',
    scope: 'industry',
    event_type: 'policy'
  });
  
  console.log(`本月有 ${policyEvents.count} 条行业政策`);
  
  if (policyEvents.count === 0) {
    console.log('本月无重大行业政策');
    return;
  }
  
  // 分析政策影响
  policyEvents.events.forEach(e => {
    console.log(`${e.event_date} ${e.title}`);
    if (e.description) {
      console.log(`  描述: ${e.description}`);
    }
    if (e.affected_industry) {
      console.log(`  影响行业: ${e.affected_industry}`);
    }
  });
  
  // 检查持仓中是否有受影响的行业
  const positions = await position_list();
  // ... 进一步分析
}

await monitorIndustryPolicy();
```

---

## 最佳实践总结

### ✅ 推荐做法

1. **每日盘前** - 必须调用 `event_calendar_check({ days: 2 })`
2. **买入前必查** - 必须调用 `stock_events({ symbol })` 并检查 `upcoming_count`
3. **重点关注** - 解禁（unlock）、定增（placement）、监管（regulatory）
4. **记录决策** - 事件驱动决策后调用 `decision_audit` 记录
5. **组合使用** - 宏观 + 个股事件综合分析

### ❌ 常见错误

1. ❌ 买入前不查个股事件
2. ❌ 忽略 `upcoming_count`（未来事件才是重点）
3. ❌ 只看事件不评估影响
4. ❌ 混淆两个工具的使用场景

---

**文档位置**: `docs/examples/event-query-examples.md`
