# L4/L5/L6 层工具文档

## 概述

本次重构创建了三个新的工具层，统一命名规范并保持现有功能不变。

## 工具列表

### L4 组合构建层

#### `portfolio_rebalance`
- **位置**: `src/infrastructure/tools/portfolio/rebalance-tool.ts`
- **功能**: 组合再平衡和持仓管理
- **包装**: `manage_portfolio` 工具
- **操作**:
  - `get` - 查看持仓
  - `get_with_pnl` - 查看持仓和盈亏
  - `add` - 添加持仓
  - `sell` - 卖出持仓
  - `update` - 更新持仓
  - `remove` - 删除持仓

### L5 执行引擎层

#### `trade_manage_orders`
- **位置**: `src/infrastructure/tools/trade/manage-orders-tool.ts`
- **功能**: 交易订单管理
- **包装**: `manage_orders` 工具
- **操作**:
  - `place` - 创建挂单
  - `cancel` - 撤销挂单
  - `list` - 查看挂单列表
  - `fill` - 手动标记成交
  - `check` - 检查触发条件并自动成交

### L6 监控运维层

#### `monitor_alert`
- **位置**: `src/infrastructure/tools/monitor/alert-tool.ts`
- **功能**: 监控告警通知
- **整合**: 4 个通知工具
- **类型**:
  - `general` - 通用消息通知
  - `trade_signal` - 交易信号（买入/卖出）
  - `market_brief` - 市场简报
  - `risk_warning` - 风险警告

## 使用示例

### portfolio_rebalance

```typescript
// 查看持仓和盈亏
await portfolioRebalanceTool.execute(toolCallId, {
  action: "get_with_pnl"
});

// 添加持仓
await portfolioRebalanceTool.execute(toolCallId, {
  action: "add",
  symbol: "600519",
  quantity: 100,
  avg_cost: 1800.50,
  notes: "长期持有"
});
```

### trade_manage_orders

```typescript
// 创建限价买入挂单
await tradeManageOrdersTool.execute(toolCallId, {
  action: "place",
  symbol: "600519",
  name: "贵州茅台",
  side: "buy",
  type: "limit",
  price: 1750.00,
  quantity: 100,
  market: "A"
});

// 检查挂单触发
await tradeManageOrdersTool.execute(toolCallId, {
  action: "check"
});
```

### monitor_alert

```typescript
// 发送交易信号
await monitorAlertTool.execute(toolCallId, {
  type: "trade_signal",
  action: "buy",
  symbol: "600519",
  name: "贵州茅台",
  price: 1750.00,
  reason: "技术面突破，基本面良好",
  confidence: 0.85,
  position_pct: 10
});

// 发送风险警告
await monitorAlertTool.execute(toolCallId, {
  type: "risk_warning",
  warning: "持仓集中度过高",
  severity: "high",
  details: "前三大持仓占比超过 60%",
  suggestion: "建议分散投资，降低单一股票风险"
});
```

## 测试覆盖

所有工具都包含完整的测试覆盖：

- `portfolio/rebalance-tool.test.ts` - 6 个测试
- `trade/manage-orders-tool.test.ts` - 6 个测试
- `monitor/alert-tool.test.ts` - 10 个测试

运行测试：
```bash
npm test -- src/infrastructure/tools/portfolio/rebalance-tool.test.ts
npm test -- src/infrastructure/tools/trade/manage-orders-tool.test.ts
npm test -- src/infrastructure/tools/monitor/alert-tool.test.ts
```

## 设计原则

1. **包装模式**: 新工具包装现有工具，保持功能不变
2. **统一命名**: 遵循 `layer_action` 命名规范
3. **向后兼容**: 原有工具继续可用，不破坏现有代码
4. **测试优先**: 每个工具都有完整的测试覆盖
5. **渐进迁移**: 可以逐步将调用迁移到新工具

## 下一步

这些工具已经创建并测试通过，但尚未集成到工具注册表中。后续步骤：

1. 将新工具添加到 `src/infrastructure/tools/index.ts`
2. 更新系统提示词，引导 Agent 使用新工具
3. 逐步迁移现有调用到新工具
4. 在稳定后考虑废弃旧工具名称

## 文件清单

```
src/infrastructure/tools/
├── portfolio/
│   ├── index.ts                    # 导出
│   ├── rebalance-tool.ts           # 工具实现
│   └── rebalance-tool.test.ts      # 测试
├── trade/
│   ├── index.ts                    # 导出
│   ├── manage-orders-tool.ts       # 工具实现
│   └── manage-orders-tool.test.ts  # 测试
└── monitor/
    ├── index.ts                    # 导出
    ├── alert-tool.ts               # 工具实现
    └── alert-tool.test.ts          # 测试
```
