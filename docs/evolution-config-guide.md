# 进化系统配置指南

## 📊 数据扫描范围配置

进化系统支持灵活的数据扫描范围配置，平衡数据完整性和相关性。

---

## 配置参数

### 1. `targetReturn` - 目标收益率
- **类型**: `number`
- **默认值**: `10` (10%)
- **说明**: 期望的收益率目标，用于减法器计算差距

**示例**:
```typescript
{ targetReturn: 15 }  // 目标 15% 收益
```

---

### 2. `tradeWindowDays` - 交易记录时间窗口
- **类型**: `number | undefined`
- **默认值**: `90` (最近 90 天)
- **说明**: 
  - 设置数字：只分析最近 N 天的交易
  - 设置 `undefined`：分析全部交易记录

**为什么需要时间窗口？**
- ✅ **相关性**: 最近的交易更能反映当前策略和市场环境
- ✅ **性能**: 减少数据处理量，加快分析速度
- ✅ **适应性**: 避免过时数据干扰当前决策

**推荐配置**:
```typescript
// 短期策略（日内/短线）
{ tradeWindowDays: 30 }

// 中期策略（波段）
{ tradeWindowDays: 90 }  // 默认

// 长期策略（价值投资）
{ tradeWindowDays: 180 }

// 全历史分析
{ tradeWindowDays: undefined }
```

---

### 3. `reviewWindowCount` - 复盘报告数量
- **类型**: `number`
- **默认值**: `10`
- **说明**: 扫描最近 N 份复盘报告，用于评估止损执行率

**示例**:
```typescript
{ reviewWindowCount: 20 }  // 分析最近 20 份复盘
```

---

### 4. `evolutionWindowRecent` - 进化历史（决策参考）
- **类型**: `number`
- **默认值**: `3`
- **说明**: 加载最近 N 次进化记录，用于：
  - 避免重复建议
  - 过滤无效工具
  - 评估上次进化效果

**示例**:
```typescript
{ evolutionWindowRecent: 5 }  // 参考最近 5 次进化
```

---

### 5. `evolutionWindowLearning` - 进化历史（经验学习）
- **类型**: `number`
- **默认值**: `100`
- **说明**: 加载最近 N 次进化记录，用于：
  - 生成工具效果排行榜
  - 识别反模式
  - 提取经验规律

**示例**:
```typescript
{ evolutionWindowLearning: 200 }  // 从最近 200 次进化中学习
```

---

## 使用方式

### 方式 1: CLI 参数（推荐）

```bash
# 只分析最近 30 天交易
npm run evolution -- --days 30

# 分析全部交易记录
npm run evolution -- --all

# 设置目标收益率 15%
npm run evolution -- --target 15

# 分析最近 20 份复盘报告
npm run evolution -- --reviews 20

# 组合使用
npm run evolution -- --days 60 --target 12 --reviews 15
```

### 方式 2: 代码调用

```typescript
import { runWeeklyEvolution } from './services/intelligence/evolution-service.js';

// 使用默认配置
await runWeeklyEvolution();

// 自定义配置
await runWeeklyEvolution({
  targetReturn: 15,
  tradeWindowDays: 60,
  reviewWindowCount: 15,
  evolutionWindowRecent: 5,
  evolutionWindowLearning: 150,
});

// 分析全部交易
await runWeeklyEvolution({
  tradeWindowDays: undefined,  // 全部
});
```

---

## 预设配置

### 保守模式
```typescript
{
  targetReturn: 5,
  tradeWindowDays: 30,
  reviewWindowCount: 5,
  evolutionWindowRecent: 2,
  evolutionWindowLearning: 50
}
```
**适用场景**: 新手、小资金、高波动市场

---

### 正常模式（默认）
```typescript
{
  targetReturn: 10,
  tradeWindowDays: 90,
  reviewWindowCount: 10,
  evolutionWindowRecent: 3,
  evolutionWindowLearning: 100
}
```
**适用场景**: 大多数情况

---

### 激进模式
```typescript
{
  targetReturn: 20,
  tradeWindowDays: 180,
  reviewWindowCount: 20,
  evolutionWindowRecent: 5,
  evolutionWindowLearning: 200
}
```
**适用场景**: 经验丰富、大资金、牛市

---

### 全历史模式
```typescript
{
  targetReturn: 10,
  tradeWindowDays: undefined,  // 全部
  reviewWindowCount: 50,
  evolutionWindowRecent: 5,
  evolutionWindowLearning: 500
}
```
**适用场景**: 年度总结、策略回测

---

## 配置建议

### 根据交易频率选择

| 交易频率 | tradeWindowDays | 说明 |
|---------|----------------|------|
| 日内交易 | 7-14 | 只看最近 1-2 周 |
| 短线交易 | 30 | 最近 1 个月 |
| 波段交易 | 90 | 最近 3 个月（默认） |
| 中长线 | 180 | 最近 6 个月 |
| 价值投资 | undefined | 全部历史 |

### 根据市场环境调整

**震荡市/熊市**:
- 缩短时间窗口（30-60 天）
- 降低目标收益率（5-8%）
- 更频繁的进化（每周）

**牛市**:
- 延长时间窗口（90-180 天）
- 提高目标收益率（15-20%）
- 适度放宽评估标准

---

## 输出日志示例

```
[进化] 配置参数:
  - 目标收益率: 10%
  - 交易窗口: 90 天
  - 复盘报告: 最近 10 份
  - 进化历史（决策）: 最近 3 次
  - 进化历史（学习）: 最近 100 次

[进化] 交易记录过滤: 156 → 48 (最近 90 天)
[进化] 复盘报告扫描: 23 份，分析最近 10 份
[进化] 加载进化历史: 3 次（决策参考）
[进化] 已更新经验总结，共 87 次进化（学习窗口）

[进化] 本次进化完成:
  - 分析交易: 48 笔 (最近 90 天)
  - 已实现收益: 8.5% (目标: 10%)
  - 胜率: 65% (31胜 17负)
  - 归因: 能力需优化
  - 建议: 3 条，已应用 2 条
  - 报告: .pi-invest/evolution/evolution-2026-05-15.md
```

---

## 常见问题

### Q1: 为什么默认只看 90 天？
**A**: 平衡相关性和数据量。90 天（约 3 个月）能覆盖一个完整的市场周期，同时避免过时数据干扰。

### Q2: 什么时候应该用全历史模式？
**A**: 
- 年度总结
- 策略回测
- 交易记录较少（< 50 笔）
- 需要长期趋势分析

### Q3: 时间窗口会影响持仓分析吗？
**A**: 不会。持仓数据始终使用当前全部持仓，时间窗口只影响已平仓交易的分析。

### Q4: 如何判断时间窗口设置是否合理？
**A**: 观察输出日志中的"交易记录过滤"，确保：
- 至少有 20 笔交易用于分析
- 覆盖至少 2-3 个完整的交易周期

---

## 最佳实践

1. **初次使用**: 使用默认配置（90 天）
2. **定期调整**: 根据市场环境每月调整一次
3. **季度回顾**: 每季度用全历史模式做一次完整分析
4. **策略变更**: 改变交易策略后，重置时间窗口（只看新策略的数据）

---

**更新时间**: 2026-05-15  
**版本**: v1.0
