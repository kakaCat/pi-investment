# analysis_swing_points 工具 undefined 问题修复

**日期**: 2026-06-02  
**优先级**: 🔴 P0  
**状态**: ✅ 已修复并验证

## 问题描述

### 现象
`analysis_swing_points` 工具输出的交易配对全部显示 `undefined`：
```
💰 交易配对（共 3 笔）：
  1. ✅ 买 undefined ¥undefined → 卖 undefined ¥undefined  +12.18%  持仓undefined天
```

### 影响
- 波段分析功能完全不可用
- 用户无法看到具体的买卖日期和价格
- 影响投资决策

## 根本原因

**字段命名不一致**：前端格式化代码使用下划线命名访问字段，但后端 API 返回驼峰命名。

### 数据流转链路

```
Python 后端
  SwingPointService._pair_trades()
    ↓ 返回下划线命名
    {
      "buy_date": "2025-06-16",
      "buy_price": 1349.62,
      "sell_date": "2025-09-12",
      "sell_price": 1514.06,
      "profit_pct": 12.18,
      "holding_days": 88
    }

Flask API 层
  api_response() → convert_keys_to_camel()
    ↓ 转换为驼峰命名
    {
      "buyDate": "2025-06-16",
      "buyPrice": 1349.62,
      "sellDate": "2025-09-12",
      "sellPrice": 1514.06,
      "profitPct": 12.18,
      "holdingDays": 88
    }

TypeScript 前端
  formatSwingResult()
    ✗ 仍使用 t.buy_date, t.buy_price... 访问
    → 全部返回 undefined
```

## 修复方案

修改 `src/infrastructure/tools/invest/swing-points-tool.ts` 的 `formatSwingResult()` 函数，将所有字段访问从**下划线命名**改为**驼峰命名**。

### 修复的字段映射

| 旧字段名（下划线） | 新字段名（驼峰） | 说明 |
|-------------------|-----------------|------|
| `min_change` | `minChange` | 最小波动阈值 |
| `kline_count` | `klineCount` | K线数量 |
| `swing_points` | `swingPoints` | 拐点列表 |
| `change_pct` | `changePct` | 变化百分比 |
| `buy_date` | `buyDate` | 买入日期 |
| `buy_price` | `buyPrice` | 买入价格 |
| `sell_date` | `sellDate` | 卖出日期 |
| `sell_price` | `sellPrice` | 卖出价格 |
| `profit_pct` | `profitPct` | 盈亏百分比 |
| `holding_days` | `holdingDays` | 持仓天数 |
| `total_trades` | `totalTrades` | 总交易次数 |
| `win_count` | `winCount` | 盈利次数 |
| `loss_count` | `lossCount` | 亏损次数 |
| `win_rate` | `winRate` | 胜率 |
| `total_return` | `totalReturn` | 累计收益 |
| `avg_return` | `avgReturn` | 平均收益 |
| `max_return` | `maxReturn` | 最大盈利 |
| `max_loss` | `maxLoss` | 最大亏损 |
| `avg_holding_days` | `avgHoldingDays` | 平均持仓天数 |

## 验证结果

### 单元测试
使用模拟数据验证格式化函数：
```bash
$ npx tsx /tmp/test-swing-points.ts
✅ 没有 undefined，修复成功！
```

### 端到端测试
调用真实 API 验证完整流程：
```bash
$ node /tmp/test-swing-e2e.js
📡 调用 API: POST /api/analysis/swing-points
   参数: symbol=600519, min_change=8

💰 交易配对（共 3 笔）：
  1. ✅ 买 2025-06-16 ¥1349.62 → 卖 2025-09-12 ¥1514.06  +12.18%  持仓88天
  2. ✅ 买 2026-01-28 ¥1322.01 → 卖 2026-02-06 ¥1568  +18.61%  持仓9天
  3. ✅ 买 2026-03-09 ¥1383.2 → 卖 2026-03-17 ¥1498.07  +8.3%  持仓8天

✅ 没有 undefined
✅ 所有交易配对正确显示
✅ 修复验证通过！
```

## 修复后的输出示例

```
📊 600519 ZigZag 波段分析
📅 2025-06-02 ~ 2026-06-02（242 根K线）
📐 最小波动阈值: 8%

🔄 拐点列表（共 8 个）：
  🔴卖 2025-06-03  ¥1498.07  
  🟢买 2025-06-16  ¥1349.62  -9.91%
  🔴卖 2025-09-12  ¥1514.06  +12.18%
  🟢买 2026-01-28  ¥1322.01  -12.68%
  🔴卖 2026-02-06  ¥1568  +18.61%
  🟢买 2026-03-09  ¥1383.2  -11.79%
  🔴卖 2026-03-17  ¥1498.07  +8.3%
  🟢买 2026-05-27  ¥1250.1  -16.55%

💰 交易配对（共 3 笔）：
  1. ✅ 买 2025-06-16 ¥1349.62 → 卖 2025-09-12 ¥1514.06  +12.18%  持仓88天
  2. ✅ 买 2026-01-28 ¥1322.01 → 卖 2026-02-06 ¥1568  +18.61%  持仓9天
  3. ✅ 买 2026-03-09 ¥1383.2 → 卖 2026-03-17 ¥1498.07  +8.3%  持仓8天

📈 统计摘要：
  交易次数: 3（盈3/亏0）
  胜率: 100%
  累计收益: +44.1%
  平均收益: +13.03%
  最大盈利: +18.61%
  最大亏损: 8.3%
  平均持仓: 31.7 天
```

## 相关文件

- **修复文件**: `src/infrastructure/tools/invest/swing-points-tool.ts`
- **后端服务**: `quantsys-v2/services/swing_point_service.py`
- **API 路由**: `quantsys-v2/api/routes/analysis.py` (第 1018-1051 行)
- **数据转换**: `quantsys-v2/api/shared.py` (`convert_keys_to_camel()`)

## 经验教训

1. **命名规范一致性**：前后端字段命名应保持一致，或在接口层明确转换规则
2. **API 层数据转换**：`api_response()` 统一将所有数据转换为驼峰命名，前端工具必须使用驼峰访问
3. **测试覆盖**：应对数据转换链路编写端到端测试，捕获此类问题
4. **TypeScript 类型安全**：考虑为 API 响应定义严格的 TypeScript 接口，避免运行时字段访问错误

## 后续改进建议

1. 为所有 quantsys-v2 API 响应定义 TypeScript 接口
2. 在 `quant-v2-client.ts` 中添加响应类型声明
3. 编写格式化函数的单元测试
4. 添加 API 响应结构验证中间件
