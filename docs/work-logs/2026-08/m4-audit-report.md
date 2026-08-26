# M4 仓位与风控实施审计报告（2026-08-26）

## 📋 审计范围

**审计对象**：RFC 008 M4 仓位与风控实施方案（2026-08-26 实施完成）  
**审计内容**：M4-1 regime 仓位映射表、M4-2 回撤熔断、M4-3 风控工具校准  
**审计标准**：RFC 008 设计规格、RFC 005 验收标准、交易宪法、代码质量

---

## 🔴 严重问题（P0 - 阻断性）

### 问题 1: M4-1 使用不存在的方法 `qv2.getAccountInfo()`

**位置**：`agent-dh/packages/trading/src/index.ts:273`  
**代码**：
```typescript
const accountInfo: any = await qv2.getAccountInfo(accountName);
```

**问题**：
- `QuantsysV2Client` 没有 `getAccountInfo()` 方法
- 正确方法应该是 `getPortfolioSummary()`（client.ts:497）

**影响**：
- portfolio_trade 运行时崩溃（Method not found）
- **M4-1 仓位映射校验完全失效**

**修复**：
```typescript
const accountInfo: any = await qv2.getPortfolioSummary(accountName);
```

**严重等级**：🔴 **P0（必须立即修复）**

---

### 问题 2: M4-3 risk_level 参数未传递到后端

**位置**：`quantsys-v2-client/src/client.ts:riskControl()`  
**代码**：
```typescript
if (command === 'stop_loss') {
  const response = await this.client.post(`/api/stock/${symbol}/risk/stop-loss`, { account_name });
  // ❌ 没有传 risk_level
}
```

**问题**：
- agent-dh risk 插件添加了 risk_level 参数（透传给 client）
- 但 client.riskControl() 方法**没有接收 risk_level 参数**
- quantsys-v2 后端虽然实现了 risk_level 逻辑，但永远收不到

**影响**：
- **M4-3 stop_loss 校准未生效**
- 止损价格仍然是固定 -8%，不会按 risk_level 分级

**修复**（2 处）：

1. **quantsys-v2-client/src/types.ts**：RiskControlRequest 接口添加 risk_level
```typescript
export interface RiskControlRequest {
  command: 'position_size' | 'stop_loss' | 'portfolio_risk';
  symbol?: string;
  account_name?: string;
  risk_level?: 'large_cap' | 'growth' | 'small_cap_theme';  // 新增
}
```

2. **quantsys-v2-client/src/client.ts**：riskControl() 传递 risk_level
```typescript
if (command === 'stop_loss') {
  const response = await this.client.post(`/api/stock/${symbol}/risk/stop-loss`, {
    account_name,
    risk_level: params.risk_level || 'large_cap',  // 新增
  });
}
```

**严重等级**：🔴 **P0（必须立即修复）**

---

## 🟡 重要问题（P1 - 需补充改进）

### 问题 3: 缺少单元测试

**位置**：`agent-dh/packages/trading/`  
**问题**：
- 没有任何 .test.ts / .spec.ts 文件
- RFC 008 §8.3 要求"单元测试覆盖率 ≥80%"

**影响**：
- 无法验证 M4-1/M4-2 逻辑正确性
- 回归风险高（未来修改可能破坏现有逻辑）

**修复**：
- 创建 `packages/trading/tests/portfolio_trade.test.ts`
- 测试场景：
  - M4-1: regime 突破拦截、降级到 sideways、通过留痕
  - M4-2: 熔断激活拦截、读取失败允许
  - M4-1+M4-2 组合：熔断激活时不检查仓位映射

**严重等级**：🟡 **P1（重要，本周内补充）**

---

### 问题 4: M4-2 减仓逻辑缺少日志

**位置**：`agent-dh/packages/trading/src/index.ts:690`  
**代码**：
```typescript
const sellQty = Math.floor(Number(pos.shares_available || 0) / 2 / 100) * 100;
if (sellQty >= 100) {
  // 执行卖出
}
// ⚠️ sellQty = 0 时静默跳过，无日志
```

**问题**：
- T+1 限制下，当日买入的股票 shares_available = 0
- 减仓一半时 sellQty = 0，会被静默跳过
- 缺少日志说明为什么跳过（无法排查）

**修复**：
```typescript
if (sellQty >= 100) {
  // 执行卖出
} else {
  sellActions.push(`跳过 ${pos.symbol}：可卖数量 ${pos.shares_available} 股，减仓一半不足 100 股`);
}
```

**严重等级**：🟡 **P1（重要，下次迭代补充）**

---

### 问题 5: M4-2 飞书告警未集成

**位置**：`agent-dh/packages/trading/src/index.ts:726`  
**代码**：
```typescript
// 飞书高优告警（假设有 feishu_notify 工具，这里记录到 osMemory）
await this.osMemory.write({
  title: 'M4-2 熔断触发告警',
  namespace: 'notification',
  ...
});
```

**问题**：
- 注释说"假设有 feishu_notify 工具"
- 但没有真正调用 feishu_notify，只是写 osMemory
- 用户不会收到实时告警（需要后续轮询 notification 信箱）

**修复**（P1 后续迭代）：
- 集成 notification 插件的飞书推送
- 或创建 Agent OS 任务轮询 notification 信箱 → 推送飞书

**严重等级**：🟡 **P1（重要，下次迭代补充）**

---

### 问题 6: M4-2 osMemory.write 缺少错误处理

**位置**：`agent-dh/packages/trading/src/index.ts:717`  
**代码**：
```typescript
await this.osMemory.write({
  title: 'M4-2 熔断状态',
  content: JSON.stringify(breakerStatus),
  namespace: 'risk',
  tags: ['m4', 'circuit_breaker_status', 'active'],
});
```

**问题**：
- 没有 try-catch，osMemory 写入失败会导致整个熔断检查失败
- 熔断状态无法持久化，下次检查无法识别已激活

**修复**：
```typescript
try {
  await this.osMemory.write({...});
} catch (e) {
  console.error('熔断状态持久化失败:', e);
  // 继续执行，但记录错误
}
```

**严重等级**：🟡 **P1（重要，下次迭代补充）**

---

## ✅ 正确实现（无问题）

### M4-1 仓位映射表逻辑
- ✅ regime 获取失败降级到 sideways（保守）
- ✅ R-006 映射表正确（panic 100%/risk_on 80%/sideways 60%/risk_off 40%/euphoria 30%）
- ✅ 突破上限拒绝交易 + osMemory 留痕
- ✅ 校验通过记录留痕

### M4-2 熔断检查逻辑
- ✅ 熔断激活时拒绝交易（blocked=true + circuit_breaker 状态）
- ✅ 检查优先级高于 M4-1（先熔断后仓位映射）
- ✅ 读取失败不阻塞交易（保守原则）
- ✅ m4_circuit_breaker_check 工具逻辑完整（触发/解除/减仓）
- ✅ Agent OS 任务已创建（工作日 16:30）

### M4-3 风控工具校准（后端）
- ✅ position_size max_position 从 0.3 改为 0.2（宪法对齐）
- ✅ stop_loss 增加 risk_level 参数（分级止损）
- ✅ quantsys-v2 RiskService 实现正确

### Agent OS 任务配置
- ✅ m4_circuit_breaker_daily_check 任务存在（ID f59fb4af）
- ✅ cron 正确（0 30 16 * * 1-5，工作日 16:30）
- ✅ 投递链路清晰（bridge → 信箱 → lifecycle → investor）

---

## 📊 审计总结

### 问题统计

| 等级 | 数量 | 说明 |
|---|---|---|
| 🔴 P0 | 2 | 阻断性问题（必须立即修复） |
| 🟡 P1 | 4 | 重要改进（本周内/下次迭代补充） |
| ✅ 正确 | 4 | 无问题（符合设计） |

### 核心风险

**M4-1 完全失效**（问题 1）：
- `qv2.getAccountInfo()` 不存在 → portfolio_trade 崩溃
- 影响所有 BUY 交易（100% 失败率）

**M4-3 stop_loss 校准未生效**（问题 2）：
- risk_level 参数未传递 → 后端永远用默认值
- 止损价格固定 -8%（不会按风险分级）

### 修复优先级

**立即修复（今日）**：
1. ✅ 问题 1: `getAccountInfo()` → `getPortfolioSummary()`
2. ✅ 问题 2: client.riskControl() 传递 risk_level

**本周内补充**：
3. 🟡 问题 3: 单元测试（trading 插件）
4. 🟡 问题 6: osMemory.write 错误处理

**下次迭代**：
5. 🟡 问题 4: M4-2 减仓日志
6. 🟡 问题 5: 飞书告警集成

---

## 🎯 结论

**M4 实施存在 2 个 P0 阻断性问题，必须立即修复后才能投入使用**：
1. M4-1 使用不存在的方法导致运行时崩溃
2. M4-3 risk_level 参数未传递到后端导致校准失效

**其他实现质量良好**：
- M4-2 熔断逻辑完整
- Agent OS 任务配置正确
- 代码架构清晰（检查顺序合理）

**建议**：
1. 立即修复 P0 问题（预计 30 分钟）
2. 本周内补充单元测试
3. 下次迭代补充日志和飞书告警

**修复后才能合并到 main**（当前 main 已有问题代码，需 hotfix）。

