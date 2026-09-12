# 事件查询最佳实践（P1-4）

## 每日盘前例行检查

```typescript
// 1. 查询宏观事件
const macroEvents = await event_calendar_check({ 
  mode: 'upcoming', 
  days: 2 
});

console.log(`未来2天有 ${macroEvents.count} 个宏观事件`);

// 重点关注高重要性事件
const highImportance = macroEvents.events.filter(e => e.importance === 3);
if (highImportance.length > 0) {
  console.log('🔴 高重要性事件：');
  highImportance.forEach(e => {
    console.log(`  - ${e.event_date} ${e.title}`);
  });
}

// 2. 检查持仓股票事件
const positions = await position_list();
for (const pos of positions) {
  const stockEvents = await stock_events({ 
    symbol: pos.symbol 
  });
  
  if (stockEvents.upcoming_count > 0) {
    console.log(`⚠️ ${pos.symbol} ${pos.name}: ${stockEvents.upcoming_count} 个即将发生的事件`);
    
    // 重点关注高风险事件
    const risks = stockEvents.events.filter(e => 
      ['unlock', 'placement', 'regulatory'].includes(e.event_type) &&
      e.event_date >= today
    );
    
    if (risks.length > 0) {
      console.log('  🔴 高风险事件：');
      risks.forEach(e => {
        console.log(`    - ${e.event_date} ${e.title}`);
      });
    }
  }
}
```

---

## 买入前排雷完整流程

```typescript
/**
 * 买入前排雷：确保不踩雷解禁/减持/监管等高风险事件
 */
async function buyWithRiskCheck(symbol: string, quantity: number, price: number) {
  console.log(`📊 开始买入前排雷：${symbol}`);
  
  // Step 1: 查询个股事件
  const events = await stock_events({ symbol });
  
  console.log(`  • 历史+未来事件：${events.count} 个`);
  console.log(`  • 未来事件：${events.upcoming_count} 个`);
  
  // Step 2: 无未来事件，绿灯通过
  if (events.upcoming_count === 0) {
    console.log('  ✅ 无未来事件，可以买入');
    await portfolio_trade({ 
      action: 'BUY', 
      symbol, 
      quantity, 
      price,
      reason: '事件排雷通过：未来无高风险事件'
    });
    return;
  }
  
  // Step 3: 分析未来事件风险
  const today = new Date().toISOString().slice(0, 10);
  const upcomingEvents = events.events.filter(e => 
    (e.event_date || e.effective_date) >= today
  );
  
  // Step 4: 高风险事件检查
  const highRiskTypes = ['unlock', 'placement', 'regulatory', 'insider_sell'];
  const highRisks = upcomingEvents.filter(e => 
    highRiskTypes.includes(e.event_type)
  );
  
  if (highRisks.length > 0) {
    console.log('  🔴 发现高风险事件，建议暂缓买入：');
    highRisks.forEach(e => {
      console.log(`    - ${e.event_date} [${e.event_type}] ${e.title}`);
      if (e.event_type === 'unlock') {
        console.log(`      解禁股数：${e.unlock_amount} 股（${e.unlock_ratio}%）`);
      }
    });
    
    // 记录跳过决策
    await decision_audit({
      action: 'record',
      decision_subtype: 'skip',
      reasoning: `事件排雷：发现 ${highRisks.length} 个高风险事件（${highRisks.map(e => e.event_type).join('、')}），暂缓买入`,
      parameters: { symbol, reason: '高风险事件', checkDays: 10 },
      related_entity_type: 'stock',
      related_entity_id: symbol,
    });
    
    return;
  }
  
  // Step 5: 中风险事件评估
  const mediumRiskTypes = ['earnings', 'shareholder_meeting'];
  const mediumRisks = upcomingEvents.filter(e => 
    mediumRiskTypes.includes(e.event_type)
  );
  
  if (mediumRisks.length > 0) {
    console.log('  🟡 发现中风险事件，谨慎买入：');
    mediumRisks.forEach(e => {
      console.log(`    - ${e.event_date} [${e.event_type}] ${e.title}`);
    });
    
    // 中风险事件：可以买入但降低仓位
    const safeQuantity = Math.floor(quantity * 0.5);
    console.log(`  ⚠️ 降低仓位：${quantity} → ${safeQuantity}`);
    
    await portfolio_trade({ 
      action: 'BUY', 
      symbol, 
      quantity: safeQuantity, 
      price,
      reason: `事件排雷：有 ${mediumRisks.length} 个中风险事件，降低仓位买入`
    });
    return;
  }
  
  // Step 6: 低风险事件，正常买入
  console.log('  ✅ 事件风险可控，正常买入');
  await portfolio_trade({ 
    action: 'BUY', 
    symbol, 
    quantity, 
    price,
    reason: '事件排雷通过：未来事件风险可控'
  });
}

// 使用示例
await buyWithRiskCheck('600519', 100, 1850);
```

---

## 事件驱动策略

```typescript
/**
 * 事件驱动策略：财报季选股
 */
async function earningsSeasonStrategy() {
  console.log('📊 财报季选股策略');
  
  // Step 1: 查询本周有财报的股票
  const calendar = await event_calendar_check({
    mode: 'range',
    start: '2026-09-11',
    end: '2026-09-18',
    scope: 'individual',  // 也可以用 macro，但 individual 更精确
    event_type: 'earnings'
  });
  
  console.log(`本周有 ${calendar.count} 只股票发布财报`);
  
  // Step 2: 对每只股票进行分析
  const candidates = [];
  
  for (const event of calendar.events) {
    if (!event.symbol) continue;
    
    console.log(`\n分析：${event.symbol} ${event.title}`);
    
    // 2.1 查询详细的个股事件
    const details = await stock_events({ symbol: event.symbol });
    
    // 2.2 检查是否有其他风险事件
    const risks = details.events.filter(e => 
      ['unlock', 'regulatory'].includes(e.event_type) &&
      e.event_date >= today
    );
    
    if (risks.length > 0) {
      console.log(`  ❌ 跳过：有 ${risks.length} 个风险事件`);
      continue;
    }
    
    // 2.3 查询基本面
    const financial = await data_fetch_financial({ symbol: event.symbol });
    
    if (!financial || financial.roe < 10) {
      console.log('  ❌ 跳过：ROE < 10%');
      continue;
    }
    
    // 2.4 查询技术面
    const quote = await data_fetch_quote({ symbol: event.symbol });
    
    if (quote.changePct > 5) {
      console.log('  ❌ 跳过：近期涨幅过大');
      continue;
    }
    
    // 2.5 通过筛选
    candidates.push({
      symbol: event.symbol,
      name: financial.name,
      earnings_date: event.event_date,
      roe: financial.roe,
      price: quote.price,
    });
    
    console.log(`  ✅ 入选：ROE=${financial.roe}%, 现价=${quote.price}`);
  }
  
  // Step 3: 汇总结果
  console.log(`\n📋 财报季候选股票：${candidates.length} 只`);
  candidates.forEach(c => {
    console.log(`  • ${c.symbol} ${c.name}: 财报日=${c.earnings_date}, ROE=${c.roe}%`);
  });
  
  return candidates;
}

await earningsSeasonStrategy();
```

---

## 持仓监控定时任务

```typescript
/**
 * 持仓事件监控：每日检查持仓股票的未来事件
 * 适合放在定时任务中（如每日 9:00 执行）
 */
async function monitorHoldingsEvents() {
  console.log('📊 持仓事件监控（每日例行）');
  
  // 1. 获取持仓
  const positions = await position_list();
  console.log(`当前持仓：${positions.length} 只`);
  
  const alerts = [];
  
  // 2. 逐个检查
  for (const pos of positions) {
    const events = await stock_events({ 
      symbol: pos.symbol,
      days: 60  // 未来60天
    });
    
    if (events.upcoming_count === 0) continue;
    
    // 3. 分析未来事件
    const today = new Date().toISOString().slice(0, 10);
    const upcoming = events.events.filter(e => 
      (e.event_date || e.effective_date) >= today
    );
    
    // 4. 高风险事件告警
    const highRisks = upcoming.filter(e => 
      ['unlock', 'regulatory', 'insider_sell'].includes(e.event_type)
    );
    
    if (highRisks.length > 0) {
      alerts.push({
        symbol: pos.symbol,
        name: pos.name,
        quantity: pos.quantity,
        currentPrice: pos.currentPrice,
        events: highRisks,
        severity: 'high'
      });
    }
    
    // 5. 中风险事件提醒
    const mediumRisks = upcoming.filter(e => 
      ['earnings', 'shareholder_meeting'].includes(e.event_type)
    );
    
    if (mediumRisks.length > 0) {
      alerts.push({
        symbol: pos.symbol,
        name: pos.name,
        quantity: pos.quantity,
        currentPrice: pos.currentPrice,
        events: mediumRisks,
        severity: 'medium'
      });
    }
  }
  
  // 6. 生成报告
  if (alerts.length === 0) {
    console.log('✅ 所有持仓无风险事件');
    return;
  }
  
  console.log(`\n⚠️ 发现 ${alerts.length} 只持仓股票有事件`);
  
  // 高风险告警
  const highAlerts = alerts.filter(a => a.severity === 'high');
  if (highAlerts.length > 0) {
    console.log('\n🔴 高风险事件告警：');
    for (const alert of highAlerts) {
      console.log(`\n  ${alert.symbol} ${alert.name}`);
      console.log(`  持仓：${alert.quantity} 股，现价：${alert.currentPrice}`);
      alert.events.forEach(e => {
        console.log(`    - ${e.event_date} [${e.event_type}] ${e.title}`);
      });
      console.log('  💡 建议：考虑提前减仓或止损');
    }
  }
  
  // 中风险提醒
  const mediumAlerts = alerts.filter(a => a.severity === 'medium');
  if (mediumAlerts.length > 0) {
    console.log('\n🟡 中风险事件提醒：');
    for (const alert of mediumAlerts) {
      console.log(`\n  ${alert.symbol} ${alert.name}`);
      alert.events.forEach(e => {
        console.log(`    - ${e.event_date} [${e.event_type}] ${e.title}`);
      });
      console.log('  💡 建议：关注事件进展，做好应对准备');
    }
  }
  
  // 7. 发送通知
  await feishu_notify({
    title: '📊 持仓事件监控报告',
    content: `高风险：${highAlerts.length} 只，中风险：${mediumAlerts.length} 只`,
    urgency: highAlerts.length > 0 ? 'high' : 'normal',
    channel: 'alerts'
  });
}

// 定时任务调用
await monitorHoldingsEvents();
```

---

## 快速参考

### 工具选择决策树

```
需要查询事件？
│
├─ 宏观事件（CPI/PMI/央行）？ → event_calendar_check()
├─ 行业事件（政策/产业）？   → event_calendar_check({ scope: 'industry' })
└─ 个股事件（解禁/财报）？   → stock_events({ symbol })
```

### 常用命令速查

```typescript
// 每日盘前检查
event_calendar_check({ days: 2 })

// 买入前排雷
stock_events({ symbol: '600519' })

// 查本周财报
event_calendar_check({ 
  mode: 'range', 
  start: '2026-09-11', 
  end: '2026-09-18', 
  event_type: 'earnings' 
})

// 查持仓股票事件
position_list() 然后逐个 stock_events()
```

### 风险事件优先级

| 事件类型 | 风险等级 | 建议 |
|---------|---------|------|
| unlock（解禁） | 🔴 高 | 提前减仓或止损 |
| regulatory（监管） | 🔴 高 | 立即评估影响 |
| insider_sell（减持） | 🔴 高 | 警惕内部人信号 |
| placement（定增） | 🟡 中 | 评估稀释影响 |
| earnings（财报） | 🟡 中 | 关注业绩预告 |
| shareholder_meeting | 🟡 中 | 关注重大决议 |
| dividend（分红） | 🟢 低 | 中性偏好 |

---

**文档位置**: `docs/guides/event-query-best-practices.md`
