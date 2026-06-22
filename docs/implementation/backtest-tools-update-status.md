# 回测工具分批功能支持状态

## ✅ 已更新的工具

### 1. indicator_backtest - 指标回测工具
**文件**: `src/infrastructure/tools/indicator/backtest-tool.ts`

**更新内容**:
- ✅ 添加了分批信号说明（简单信号 vs 分批信号）
- ✅ 说明支持最多3级买入和3级卖出
- ✅ 解释交易记录中的 `tiers` 字段

**使用场景**: 单策略回测（最常用）

### 2. strategy_write - 策略编写工具
**文件**: `src/infrastructure/tools/strategy/write-tool.ts`

**更新内容**:
- ✅ 详细的分批信号格式说明
- ✅ 简单信号 vs 分批信号对比
- ✅ 代码示例（简单和分批两种）
- ✅ 完整的参数说明（_pct列）

**使用场景**: 创建/更新策略代码

### 3. strategy_combo_backtest - 组合策略回测工具
**文件**: `src/infrastructure/tools/backtest/combo-backtest-tool.ts`

**更新内容**:
- ✅ 添加策略信号支持说明
- ✅ 说明组合中每个策略可独立使用简单或分批信号

**使用场景**: 多策略组合回测（portfolio/ensemble/pipeline模式）

---

## 不需要更新的工具

### 1. factor_layering_backtest - 因子分层回测
**原因**: 测试因子有效性，不涉及策略信号

### 2. factor_batch_layering_backtest - 批量因子分层回测
**原因**: 批量测试多个因子，不涉及策略信号

---

## 核心更新要点

### 对于 Agent 的说明

当 Agent 使用策略相关工具时，现在可以：

1. **编写简单策略**（全仓模式）:
```python
df['buy'] = condition
df['sell'] = condition
```

2. **编写分批策略**（分步建仓/止盈）:
```python
# 分批买入
df['buy_tier1'] = condition1
df['buy_tier1_pct'] = 0.3  # 30%

df['buy_tier2'] = condition2
df['buy_tier2_pct'] = 0.3  # 30%

df['buy_tier3'] = condition3
df['buy_tier3_pct'] = 0.4  # 40%

# 分批卖出
df['sell_tier1'] = condition4
df['sell_tier1_pct'] = 0.5  # 减半仓

df['sell_tier2'] = condition5
df['sell_tier2_pct'] = 0.3  # 再减30%

df['sell_tier3'] = condition6
df['sell_tier3_pct'] = 1.0  # 全清
```

3. **回测结果解读**:
- 简单策略：交易记录不含 `tiers` 字段
- 分批策略：交易记录包含 `tiers` 数组，显示每个批次的明细

---

## 工具调用示例

### 创建分批策略

```typescript
// Agent 调用
strategy_write({
  name: "分批建仓策略示例",
  code: `
my_indicator_name = "趋势跟踪分批建仓"

df['buy_tier1'] = (df['rsi14'] < 30)
df['buy_tier1_pct'] = 0.3

df['buy_tier2'] = (df['rsi14'] < 40) & (df['close'] < df['ma20'])
df['buy_tier2_pct'] = 0.3

df['buy_tier3'] = (df['close'] > df['ma20']) & (df['adx'] > 25)
df['buy_tier3_pct'] = 0.4

df['sell_tier1'] = df['rsi14'] > 70
df['sell_tier1_pct'] = 1.0
  `
})
```

### 回测验证

```typescript
// Agent 调用
indicator_backtest({
  indicator_id: 405,
  symbol: "600519",
  start_date: "2024-01-01",
  end_date: "2024-12-31"
})
```

### 查看分批明细

回测返回结果：
```json
{
  "data": {
    "totalTrades": 5,
    "trades": [
      {
        "entryDate": "2024-01-15",
        "exitDate": "2024-02-10",
        "entryPrice": 73.67,  // 加权平均
        "exitPrice": 76.0,
        "pnl": 2330,
        "tiers": [  // 分批明细
          {
            "tier": 1,
            "entryDate": "2024-01-15",
            "entryPrice": 72.5,
            "shares": 300,
            "exitDate": "2024-02-10",
            "exitPrice": 76.0,
            "pnl": 1050
          },
          {
            "tier": 2,
            "entryDate": "2024-01-20",
            "entryPrice": 74.0,
            "shares": 300,
            "pnl": 600
          },
          {
            "tier": 3,
            "entryDate": "2024-01-25",
            "entryPrice": 75.0,
            "shares": 400,
            "pnl": 680
          }
        ]
      }
    ]
  }
}
```

---

## 更新总结

| 工具 | 状态 | 说明 |
|------|------|------|
| strategy_write | ✅ 已更新 | 详细的分批信号格式说明 |
| indicator_backtest | ✅ 已更新 | 分批回测结果说明 |
| strategy_combo_backtest | ✅ 已更新 | 组合策略支持说明 |
| factor_layering_backtest | ⚪ 无需更新 | 因子测试工具 |
| factor_batch_layering_backtest | ⚪ 无需更新 | 批量因子测试 |

---

## 验证状态

- ✅ 核心回测引擎已实现分批功能
- ✅ 代码验证器支持分批信号
- ✅ E2E测试全部通过
- ✅ Agent工具文档已更新
- ✅ 服务已重启并加载新代码

**结论**: 所有需要更新的回测工具文档都已完成 ✅
