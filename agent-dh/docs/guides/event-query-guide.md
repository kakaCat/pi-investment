---
id: guides-event-query-guide
title: 事件查询统一指南（P1-4）
summary: 两个事件查询工具怎么选、字段怎么读（统一指南）。
type: guide
status: living
updated: 2026-09-13
owners: [agent-dh]
tags: [guide]
---

# 事件查询统一指南（P1-4）

## 概述

PI Investment 系统提供两个事件查询工具，分别针对不同的使用场景：

- **event_calendar_check** - 宏观/行业事件日历
- **stock_events** - 个股事件排雷

本指南帮助你快速选择正确的工具。

---

## 快速决策树

```
需要查询事件？
│
├─ 查宏观事件（CPI/PMI/央行议息）？
│  └─ ✅ event_calendar_check（默认 mode）
│
├─ 查行业事件（行业政策/产业变化）？
│  └─ ✅ event_calendar_check（scope=industry）
│
└─ 查个股事件（解禁/财报/股东会）？
   └─ ✅ stock_events（传 symbol）
```

---

## 工具 1: event_calendar_check

### 适用场景

1. **盘前例行检查** - 每日检查未来 2 天的重大事件
2. **宏观环境评估** - 查询 CPI/PMI/FOMC 等宏观数据发布日
3. **行业事件监控** - 查询行业政策、产业变化

### 核心参数

| 参数 | 说明 | 示例 |
|------|------|------|
| mode | upcoming（默认）/ range | 'upcoming' |
| days | 未来天数（默认 2） | 2 |
| scope | macro / industry / individual | 'macro' |

### 使用示例

```typescript
// 示例 1: 每日盘前检查（最常用）
event_calendar_check({ mode: 'upcoming', days: 2 })
// 返回：未来 2 天的待处理事件

// 示例 2: 查询本周宏观事件
event_calendar_check({ 
  mode: 'range',
  start: '2026-09-11',
  end: '2026-09-18',
  scope: 'macro'
})

// 示例 3: 查询行业政策事件
event_calendar_check({
  mode: 'range',
  start: '2026-09-01',
  end: '2026-09-30',
  scope: 'industry',
  event_type: 'policy'
})
```

### 返回数据

```typescript
{
  mode: 'upcoming(2天)',
  count: 3,
  events: [
    {
      event_date: '2026-09-12',
      event_time: '09:30',
      event_type: 'cpi_ppi',
      title: 'CPI 数据发布',
      importance: 3,  // 1=低, 2=中, 3=高
      status: 'pending'
    }
  ]
}
```

---

## 工具 2: stock_events

### 适用场景

1. **买入前排雷** - 确认未来有无解禁/减持等供给冲击
2. **财报季查询** - 查持仓股票的财报披露日
3. **事件驱动分析** - 复盘异动的催化剂

### 核心参数

| 参数 | 说明 | 示例 |
|------|------|------|
| symbol | 股票代码（必填） | '600519' |
| days | 回溯/前瞻天数（默认 90） | 90 |

### 使用示例

```typescript
// 示例 1: 买入前排雷（最常用）
stock_events({ symbol: '600519' })
// 返回：未来 90 天的个股事件，重点关注 upcoming_count

// 示例 2: 只看近期事件
stock_events({ symbol: '600519', days: 30 })

// 示例 3: 查看更长周期
stock_events({ symbol: '600519', days: 180 })
```

### 返回数据

```typescript
{
  symbol: '600519',
  count: 5,
  upcoming_count: 2,  // 🔴 重点：未来事件数
  events: [
    {
      event_date: '2026-09-15',
      event_type: 'unlock',  // 解禁
      title: '首发原股东限售股份解禁',
      unlock_amount: 100000000,  // 解禁股数
      unlock_ratio: 5.2,  // 占总股本比例
      importance: 2,
      source: 'cninfo',
      url: 'http://...'
    },
    {
      event_date: '2026-10-20',
      event_type: 'earnings',  // 财报
      title: '2026年三季报',
      importance: 3
    }
  ],
  note: '事件来自多源聚合，逐条带 source/url 可溯源'
}
```

---

## 综合使用场景

### 场景 1: 盘前全面检查

```typescript
// 步骤 1: 查宏观事件
const macroEvents = await event_calendar_check({ 
  mode: 'upcoming', 
  days: 2 
});

// 步骤 2: 查持仓股票事件
const positions = await position_list();
for (const pos of positions) {
  const stockEvents = await stock_events({ 
    symbol: pos.symbol 
  });
  
  // 关注 upcoming_count > 0 的持仓
  if (stockEvents.upcoming_count > 0) {
    console.log(`${pos.symbol} 有 ${stockEvents.upcoming_count} 个即将发生的事件`);
  }
}
```

### 场景 2: 买入前排雷流程

```typescript
// 步骤 1: 技术分析通过，准备买入
const symbol = '600519';

// 步骤 2: 事件排雷
const events = await stock_events({ symbol });

// 步骤 3: 检查未来事件
if (events.upcoming_count > 0) {
  console.log(`⚠️ 注意：未来有 ${events.upcoming_count} 个事件`);
  
  // 重点关注：解禁、减持、监管
  const risks = events.events.filter(e => 
    ['unlock', 'placement', 'regulatory'].includes(e.event_type) &&
    e.event_date >= today
  );
  
  if (risks.length > 0) {
    console.log('🔴 发现高风险事件，建议暂缓买入');
    return;
  }
}

// 步骤 4: 确认无重大风险，执行买入
await portfolio_trade({ action: 'BUY', symbol, quantity: 100 });
```

### 场景 3: 事件驱动策略

```typescript
// 步骤 1: 查询本周有财报的股票
const calendar = await event_calendar_check({
  mode: 'range',
  start: '2026-09-11',
  end: '2026-09-18',
  event_type: 'earnings'
});

// 步骤 2: 对每只股票进行深入分析
for (const event of calendar.events) {
  if (!event.symbol) continue;
  
  // 查询详细的个股事件
  const details = await stock_events({ symbol: event.symbol });
  
  // 查询基本面
  const financial = await data_fetch_financial({ symbol: event.symbol });
  
  // 综合判断：财报 + 基本面 + 技术面
  // ...
}
```

---

## 工具对比

| 维度 | event_calendar_check | stock_events |
|------|---------------------|--------------|
| **主要用途** | 宏观/行业事件监控 | 个股事件排雷 |
| **必需参数** | 无（默认 upcoming） | symbol（必填） |
| **事件范围** | 宏观/行业/个股（通过 scope） | 仅个股 |
| **使用频率** | 每日盘前 1 次 | 买入前每次 |
| **返回重点** | 事件列表 | upcoming_count |
| **数据来源** | event_calendar 表 + 多源事件流 | 多源聚合（巨潮/东财/akshare） |

---

## 最佳实践

### ✅ 推荐做法

1. **每日盘前** - 调用 `event_calendar_check({ days: 2 })` 检查宏观事件
2. **买入前** - 必须调用 `stock_events({ symbol })` 排雷
3. **持仓监控** - 定期检查持仓股票的 upcoming_count
4. **事件驱动** - 结合两个工具，发现事件→分析影响→执行交易

### ❌ 常见错误

1. ❌ 买入前不查个股事件（可能踩雷解禁/减持）
2. ❌ 只查宏观事件，忽略个股事件
3. ❌ 混淆两个工具的使用场景
4. ❌ 忽略 upcoming_count（未来事件才是重点）

---

## 数据源说明

### event_calendar_check
- 宏观事件：手工维护的事件日历表（quant.event_calendar）
- 行业/个股：多源事件流（/api/events/feed）

### stock_events
- 多源聚合：巨潮（cninfo）、东财（eastmoney）、akshare
- 每条事件带 source 和 url，可溯源
- 全源失败时显式报错，不返回空清单

---

## 相关工具

- **stock_intel** - 查询个股公告/新闻/内部人交易（原文）
- **decision_audit** - 记录事件驱动决策
- **memory_search** - 检索历史事件分析

---

## 更新记录

- 2026-09-11: P1-4 事件双轨合流，创建统一指南
- 2026-09-11: stock_events 工具上线（P3/RFC 015 §3）
- 2026-XX-XX: event_calendar_check 支持 scope 参数

---

**文档位置**: `docs/guides/event-query-guide.md`

---

## 相关页面

- [事件查询最佳实践](event-query-best-practices.md)
- [事件查询示例](../examples/event-query-examples.md)
