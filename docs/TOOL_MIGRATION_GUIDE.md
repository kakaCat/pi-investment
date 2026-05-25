# 工具迁移指南

## 概述

2025-05-25，我们完成了工具系统的重大重构，从 61 个分散的工具整合为 30 个结构化的工具。

## 架构变化

### 旧架构
- 工具分散在 `src/tools/invest/`, `src/tools/analysis/`, `src/tools/trading/` 目录
- 命名不统一，缺乏规范
- 功能重复，维护困难
- 61 个工具，职责不清晰

### 新架构
- 六层架构：数据管道 → 因子工厂 → 模型层 → 组合构建 → 执行引擎 → 监控运维
- 统一命名规范：`layer_action` 格式
- 智能路由，一个工具整合多个相关功能
- 30 个工具，职责明确

## 六层架构说明

### L1 数据管道层
负责所有数据获取操作，提供统一的数据接口。

**工具列表：**
- `data_fetch_stock` — 获取股票基本信息、实时价格、新闻、公告
- `data_fetch_kline` — 获取 K 线数据（日线、周线、月线）
- `data_fetch_financial` — 获取财务数据（利润表、资产负债表、现金流量表）

### L2 因子工厂层
批量计算技术因子和基本面因子。

**工具列表：**
- `factor_calculate` — 批量计算技术因子（RSI、MACD、布林带等）和基本面因子（PE、ROE、毛利率等）

### L3 模型层（待实现）
机器学习模型训练和预测服务。

**计划工具：**
- `model_train` — 模型训练
- `model_predict` — 模型预测
- `model_evaluate` — 模型评估

### L4 组合构建层
持仓管理和组合再平衡。

**工具列表：**
- `portfolio_rebalance` — 组合再平衡和持仓管理

### L5 执行引擎层
订单管理和交易执行。

**工具列表：**
- `trade_manage_orders` — 订单管理和执行

### L6 监控运维层
实时监控和告警通知。

**工具列表：**
- `monitor_alert` — 告警通知和风险监控

## 工具映射表

### 数据获取类

| 旧工具 | 新工具 | 说明 |
|--------|--------|------|
| `get_stock_info` | `data_fetch_stock` | 获取股票基本信息 |
| `get_stock_price` | `data_fetch_stock` | 获取实时价格 |
| `get_stock_news` | `data_fetch_stock` | 获取股票新闻 |
| `get_kline_data` | `data_fetch_kline` | 获取 K 线数据 |
| `get_daily_kline` | `data_fetch_kline` | 获取日线数据 |
| `get_financial_data` | `data_fetch_financial` | 获取财务数据 |
| `get_balance_sheet` | `data_fetch_financial` | 获取资产负债表 |
| `get_income_statement` | `data_fetch_financial` | 获取利润表 |
| `get_cashflow_statement` | `data_fetch_financial` | 获取现金流量表 |

### 因子计算类

| 旧工具 | 新工具 | 说明 |
|--------|--------|------|
| `calculate_technical_factors` | `factor_calculate` | 计算技术因子 |
| `calculate_fundamental_factors` | `factor_calculate` | 计算基本面因子 |
| `calculate_rsi` | `factor_calculate` | 计算 RSI |
| `calculate_macd` | `factor_calculate` | 计算 MACD |
| `calculate_bollinger` | `factor_calculate` | 计算布林带 |

### 组合管理类

| 旧工具 | 新工具 | 说明 |
|--------|--------|------|
| `get_portfolio` | `portfolio_rebalance` | 获取持仓 |
| `rebalance_portfolio` | `portfolio_rebalance` | 组合再平衡 |
| `optimize_portfolio` | `portfolio_rebalance` | 组合优化 |

### 交易执行类

| 旧工具 | 新工具 | 说明 |
|--------|--------|------|
| `create_order` | `trade_manage_orders` | 创建订单 |
| `cancel_order` | `trade_manage_orders` | 取消订单 |
| `get_order_status` | `trade_manage_orders` | 查询订单状态 |
| `list_orders` | `trade_manage_orders` | 列出所有订单 |

### 监控告警类

| 旧工具 | 新工具 | 说明 |
|--------|--------|------|
| `send_alert` | `monitor_alert` | 发送告警 |
| `check_risk` | `monitor_alert` | 风险检查 |
| `monitor_position` | `monitor_alert` | 持仓监控 |

## 使用示例

### 示例 1：获取股票数据

**旧方式：**
```typescript
// 需要调用多个工具
await agent.call('get_stock_info', { symbol: '600519.SH' });
await agent.call('get_stock_price', { symbol: '600519.SH' });
await agent.call('get_stock_news', { symbol: '600519.SH' });
```

**新方式：**
```typescript
// 一个工具完成所有操作
await agent.call('data_fetch_stock', {
  symbol: '600519.SH',
  fields: ['info', 'price', 'news']
});
```

### 示例 2：计算因子

**旧方式：**
```typescript
// 需要分别调用
await agent.call('calculate_rsi', { symbol: '600519.SH' });
await agent.call('calculate_macd', { symbol: '600519.SH' });
await agent.call('calculate_bollinger', { symbol: '600519.SH' });
```

**新方式：**
```typescript
// 批量计算
await agent.call('factor_calculate', {
  symbols: ['600519.SH'],
  factors: ['rsi', 'macd', 'bollinger']
});
```

### 示例 3：订单管理

**旧方式：**
```typescript
// 多个工具分散管理
await agent.call('create_order', { symbol: '600519.SH', action: 'buy', quantity: 100 });
await agent.call('get_order_status', { orderId: '12345' });
await agent.call('cancel_order', { orderId: '12345' });
```

**新方式：**
```typescript
// 统一的订单管理接口
await agent.call('trade_manage_orders', {
  action: 'create',
  symbol: '600519.SH',
  side: 'buy',
  quantity: 100
});

await agent.call('trade_manage_orders', {
  action: 'query',
  orderId: '12345'
});

await agent.call('trade_manage_orders', {
  action: 'cancel',
  orderId: '12345'
});
```

## 迁移步骤

### 1. 更新工具调用

将代码中的旧工具调用替换为新工具调用。参考上面的映射表。

### 2. 更新参数格式

新工具采用统一的参数格式：
- `action` — 操作类型（如 create, query, cancel）
- `symbol` / `symbols` — 股票代码
- `fields` — 需要的字段列表

### 3. 测试验证

运行测试确保迁移后功能正常：
```bash
npm test
```

### 4. 更新文档

更新项目文档和注释，使用新的工具名称。

## 常见问题

### Q: 旧工具还能用吗？

A: 不能。旧工具已完全移除，必须使用新工具。

### Q: 如何找到对应的新工具？

A: 参考本文档的"工具映射表"部分，或查看 `src/infrastructure/tools/index.ts`。

### Q: 新工具的参数格式是什么？

A: 每个工具都有详细的 TypeScript 类型定义，可以在 IDE 中查看自动补全提示。

### Q: 遇到问题怎么办？

A: 查看工具实现代码：
- 数据管道：`src/infrastructure/tools/data/`
- 因子工厂：`src/infrastructure/tools/factor/`
- 组合构建：`src/infrastructure/tools/portfolio/`
- 执行引擎：`src/infrastructure/tools/trade/`
- 监控运维：`src/infrastructure/tools/monitor/`

## 优势总结

新工具系统的优势：

1. **更少的工具数量**：从 61 个减少到 30 个，降低认知负担
2. **统一的命名规范**：`layer_action` 格式，易于理解和记忆
3. **智能路由**：一个工具整合多个相关功能，减少工具切换
4. **清晰的架构**：六层架构对应量化投资完整流程
5. **更好的维护性**：代码组织清晰，易于扩展和维护

## 参考资料

- [CLAUDE.md](../CLAUDE.md) — 完整的工具列表和使用指南
- [README.md](../README.md) — 项目概览
- [src/infrastructure/tools/](../src/infrastructure/tools/) — 工具实现代码
