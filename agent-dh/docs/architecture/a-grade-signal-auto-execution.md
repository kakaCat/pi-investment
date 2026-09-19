# A级信号自动执行闭环

**版本**: v1.0  
**生效日期**: 2026-09-20  
**制定人**: investor (w-982cac2c)  
**状态**: 已设计，待实施

## 目标

解决当前"信号产生但不执行"的问题，建立A级信号到交易执行的自动化闭环，提高信号转化率从<2%到>50%。

## 触发条件

- **信号级别**: A级（≥3维共振：主线+技术+资金+基本面）
- **市场时段**: 交易时段（9:30-11:30, 13:00-15:00）
- **账户状态**: 现金≥10%、持仓<10只、未触发熔断
- **日限额**: 每日最多执行2笔A级信号

## 执行流程

### 步骤1：A级信号触发
- **动作**: signal_track 记录信号
- **参数**: 
  - grade=A
  - source=manual/opportunity_scan/strategy_execute
  - symbol, price, reason
- **输出**: signal_id

### 步骤2：风控检查
```typescript
// 伪代码示例
const account = await account_info({ account_name: 'agent_brain' });
const positions = await position_list({ account_name: 'agent_brain' });
const regimeLimit = await regime_position_limit({ account_name: 'agent_brain' });

// 检查条件
const checks = {
  cashRatio: account.cash / account.totalValue >= 0.1,
  positionCount: positions.length < 10,
  regimeCompliant: regimeLimit.verdict === 'compliant',
  circuitBreaker: !regimeLimit.circuit_breaker
};

if (!Object.values(checks).every(v => v)) {
  // 风控不通过，降级为观察
  return { execute: false, reason: '风控检查未通过' };
}
```

### 步骤3：计算建议仓位
```typescript
const positionSize = await risk_controller({
  command: 'position_size',
  symbol: signal.symbol,
  price: signal.price,
  account_name: 'agent_brain'
});

// A级信号：总资产的20%
const targetAmount = account.totalValue * 0.2;
const shares = Math.floor(targetAmount / signal.price / 100) * 100;
```

### 步骤4：发送确认通知
```typescript
await feishu_notify({
  title: '🔔 A级信号确认',
  content: `
【A级信号】${signal.symbol}
当前价: ${signal.price}元
建议仓位: ${shares}股 (${targetAmount}元, 20%)
止损价: ${(signal.price * 0.92).toFixed(2)}元 (-8%)

理由: ${signal.reason}

请在30分钟内确认是否执行
  `,
  urgency: 'high',
  channel: 'alerts'
});
```

### 步骤5：等待确认（30分钟）
- **选项A**: 人工确认 → 执行交易
- **选项B**: 拒绝 → 降级为观察
- **选项C**: 30分钟无响应 → 自动降级为观察

### 步骤6：执行交易
```typescript
const order = await portfolio_trade({
  action: 'BUY',
  symbol: signal.symbol,
  quantity: shares,
  price: signal.price,
  reason: `A级信号自动执行 signal_id=${signal.id} R-001+R-009`,
  account_name: 'agent_brain'
});

// 记录决策
await decision_audit({
  action: 'record',
  decision_type: 'trade_buy',
  reasoning: `A级信号自动执行: ${signal.reason}`,
  parameters: {
    symbol: signal.symbol,
    quantity: shares,
    price: signal.price,
    signal_id: signal.id
  }
});
```

### 步骤7：设置止损监控
```typescript
await watch_manage({
  action: 'create',
  name: `${signal.symbol}止损-8%`,
  symbol: signal.symbol,
  condition: 'pnl_pct<-8',
  reason: `A级信号建仓后自动止损监控`,
  cost_price: signal.price,
  account: 'agent_brain'
});
```

## 熔断机制

### 日执行限制
- 每日最多执行2笔A级信号
- 使用内存计数器（daily_execution_count）
- 每日00:00重置

### 单日亏损限制
- 单日总亏损 > 3% 暂停当日交易
- 检查方式：account_info 的 dailyChange

### 连续止损限制
- 连续3次止损触发后暂停7天
- 记录在 memory (namespace=risk_control)

### 仓位上限
- 遵循 regime_position_limit 的 verdict
- verdict !== 'compliant' 时禁止新开仓

## 监控指标

### 信号转化率
```
转化率 = A级信号执行数 / A级信号产生数
目标: >50%（当前<2%）
```

### 执行时效
```
平均时效 = Σ(交易时间 - 信号时间) / 执行数
目标: <10分钟
```

### 执行质量
```
通过 signal_track 的 5/10/20 日回填
目标: 5日胜率>60%, 平均超额>5%
```

## 实施步骤

### Phase 1: 手动模拟（1-2天）
1. 下次A级信号产生时，手动执行上述流程
2. 验证每个步骤的工具调用是否正常
3. 记录执行时间、遇到的问题

### Phase 2: 半自动执行（3-5天）
1. 创建定时任务检查 signal_track 中的A级信号
2. 自动发送通知，等待人工确认
3. 确认后自动执行交易和止损设置

### Phase 3: 全自动执行（7天后）
1. 完善熔断机制
2. 建立监控看板
3. 根据执行质量数据优化流程

## 回退计划

如果自动执行出现问题（如错误交易、频繁止损），可立即回退到手动模式：
1. 关闭自动执行定时任务
2. 保留信号记录功能
3. 人工复盘问题原因

## 附录：定时任务配置

```yaml
# 添加到 scheduler_manage
name: "A级信号自动执行检查"
cron: "*/5 9-11,13-15 * * 1-5"  # 交易时段每5分钟检查
command: "check_a_grade_signals_and_execute"
description: "检查新的A级信号并执行自动交易流程"
agent_line: "profit_engine"
```

---

**下一步**: 需要创建实际的执行脚本并注册定时任务
