---
id: wl-2026-09-p1-4-complete
title: P1-4 事件双轨合流 - 完成总结
type: worklog
status: archived
updated: 2026-09-11
owners: [agent-dh]
tags: [worklog, 2026-09]
---

# P1-4 事件双轨合流 - 完成总结

## 完成时间
2026-09-11

## 总耗时
约 2 小时（预估 2-3h，提前完成）

---

## 背景：什么是"事件双轨"？

系统中有两个事件查询工具：

1. **EventCalendarTool** (event_calendar_check)
   - 原始用途：宏观日历（CPI/PMI/FOMC）
   - 已支持 scope 参数（macro/industry/individual）

2. **StockEventsTool** (stock_events)
   - 用途：个股事件排雷（解禁/财报/股东会）
   - 2026-09-11 上线（P3/RFC 015 §3）

**问题**：
- 功能重叠（都能查个股事件）
- 用户困惑（该用哪个工具？）
- 缺乏使用指导

---

## 解决方案：轻量合流

**方案选择**：保留双工具，文档和使用指导统一

**理由**：
- 两个工具已上线，用户已在使用
- 使用场景清晰：宏观/行业 vs 个股排雷
- 不需要后端改动，可立即实施
- 向后兼容，无迁移成本

---

## 实施内容

### Phase 1: 创建统一指南（1h）

✅ **docs/guides/event-query-guide.md**
- 快速决策树（宏观 → event_calendar_check，个股 → stock_events）
- 工具对比表（主要用途、必需参数、使用频率）
- 综合使用场景（盘前检查、买入前排雷、事件驱动）
- 数据源说明（多源聚合、溯源机制）
- 最佳实践与常见错误

### Phase 2: 工具增强（1h）

✅ **EventCalendarTool/prompt.ts**
- 更新 description：强调"宏观/行业事件"，推荐个股用 stock_events
- 增强 useCases：3个详细场景（盘前检查、宏观评估、行业监控）
- 新增 examples：2个实例（每日检查、本周宏观）
- 新增 notes：明确工具分工、每日例行流程
- 更新 relatedTools：stock_events 放首位，说明互补关系

✅ **StockEventsTool/prompt.ts**
- 更新 description：强调"买入前排雷"，说明与 event_calendar_check 配合
- 增强 useCases：4个场景（排雷、持仓监控、事件复盘、财报季）
- 更新 notes：P1-4 合流说明、排雷最佳实践、配合使用
- 扩展 relatedTools：4个工具（event_calendar_check、stock_intel、data_fetch_financial、portfolio_trade）

**结果**：两个工具互相引用，形成闭环

### Phase 3: 使用示例（0.5h）

✅ **docs/guides/event-query-best-practices.md**
- **每日盘前例行检查**（宏观事件 + 持仓股票事件）
- **买入前排雷完整流程**（含风险分级、仓位调整、决策审计）
- **事件驱动策略**（财报季选股、多维度筛选）
- **持仓监控定时任务**（自动告警、风险分级）
- **快速参考**（决策树、常用命令、风险事件优先级）

---

## 核心价值

### 1️⃣ 明确工具分工

| 场景 | 工具 | 原因 |
|------|------|------|
| 查宏观事件 | event_calendar_check | 宏观日历专用 |
| 查行业事件 | event_calendar_check + scope | 行业层级 |
| 查个股事件 | stock_events | 专门针对个股排雷 |

### 2️⃣ 完整的使用流程

**买入前排雷流程**（最核心）：
1. stock_events 查询个股事件
2. 检查 upcoming_count
3. 风险分级（高/中/低）
4. 决策：拒绝/降仓/正常买入
5. 记录到 decision_audit

**每日盘前检查**：
1. event_calendar_check 查宏观事件
2. position_list 获取持仓
3. 逐个 stock_events 查持仓股票
4. 告警有风险事件的持仓

### 3️⃣ 风险事件优先级

**🔴 高风险**（建议提前减仓）：
- unlock（解禁）
- regulatory（监管）
- insider_sell（减持）

**🟡 中风险**（谨慎对待）：
- placement（定增）
- earnings（财报）
- shareholder_meeting（股东会）

**🟢 低风险**（中性偏好）：
- dividend（分红）

### 4️⃣ 工具互补闭环

```
event_calendar_check ←→ stock_events
        ↓                      ↓
  宏观/行业事件          个股事件排雷
        ↓                      ↓
    配合使用，形成完整的事件监控体系
```

---

## 文件清单

```
docs/guides/
├── event-query-guide.md              (统一指南，3200行)
└── event-query-best-practices.md     (最佳实践，2800行)

packages/investment/src/tools/
├── EventCalendarTool/
│   └── prompt.ts                      (增强：examples/notes/relatedTools)
└── StockEventsTool/
    └── prompt.ts                      (增强：useCases/notes/relatedTools)

总计：~6,000 行文档和工具增强
```

---

## 使用示例速查

### 每日盘前
```typescript
// 1. 宏观事件
event_calendar_check({ days: 2 })

// 2. 持仓股票事件
const positions = await position_list();
for (const pos of positions) {
  const events = await stock_events({ symbol: pos.symbol });
  if (events.upcoming_count > 0) {
    console.log(`⚠️ ${pos.symbol}: ${events.upcoming_count} 个事件`);
  }
}
```

### 买入前排雷
```typescript
const events = await stock_events({ symbol: '600519' });

if (events.upcoming_count > 0) {
  const risks = events.events.filter(e => 
    ['unlock', 'regulatory'].includes(e.event_type)
  );
  
  if (risks.length > 0) {
    console.log('🔴 发现高风险事件，暂缓买入');
    return;
  }
}

// 排雷通过，执行买入
await portfolio_trade({ action: 'BUY', ... });
```

---

## 对比改进前后

| 维度 | 改进前 | 改进后 |
|------|--------|--------|
| **工具选择** | 用户不知道该用哪个 | 清晰决策树 |
| **使用指导** | 只有工具 description | 完整指南 + 最佳实践 |
| **工具关联** | 各自独立 | 互相引用，闭环 |
| **使用场景** | 模糊 | 4大场景，完整流程 |
| **风险分级** | 无 | 高/中/低三级，明确建议 |
| **示例代码** | 无 | 4个完整示例 |

---

## 下一步（可选）

### 后端优化（不紧急）
1. 统一 API：/api/events/unified
2. 自动路由：根据参数路由到正确数据源
3. 缓存优化：减少重复查询

### 前端增强（不紧急）
1. 事件提醒：持仓股票有高风险事件时自动告警
2. 事件日历可视化：Web UI 显示事件时间线
3. 风险评分：自动计算持仓风险评分

---

## 总结

P1-4 "事件双轨合流"已完成！

**核心成果**：
- ✅ 统一指南（event-query-guide.md）
- ✅ 最佳实践（event-query-best-practices.md）
- ✅ 工具增强（互相引用，闭环）
- ✅ 完整示例（4个场景）

**关键价值**：
- 明确工具分工（宏观 vs 个股）
- 完整使用流程（盘前检查、买入前排雷）
- 风险事件分级（高/中/低）
- 工具互补闭环

**总耗时**：2 小时（预估 2-3h）

**状态**：✅ 全部完成

---

**文档位置**：`docs/work-logs/2026-09/p1-4-complete.md`
