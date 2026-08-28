# M4-2 熔断检查工具 API 调用错误修复（2026-08-28）

## 📋 问题描述

**工具**: `m4_circuit_breaker_check`  
**插件**: `agent-dh/packages/trading`  
**症状**: 工具执行报错 HTTP 405 Method Not Allowed  
**影响**: M4-2 组合回撤熔断每日检查失败（工作日 16:30 任务）

---

## 🔍 问题根因

### 1. 方法名拼写错误

**位置**: `agent-dh/packages/trading/src/index.ts:778`

```typescript
// ❌ 错误：调用不存在的方法
const riskMetrics: any = await qv2.riskMetrics({ account_name: accountName, days: 60 });
```

**问题**：
- `QuantsysV2Client` 类中**没有 `riskMetrics` 方法**
- 正确方法名是 `getRiskMetrics`（定义在 `quantsys-v2-client/src/client.ts:790`）

**调用链路**：
```
m4_circuit_breaker_check 工具
  ↓ 调用 qv2.riskMetrics()  ❌ 方法不存在
  ↓ 应调用 qv2.getRiskMetrics()  ✅ 正确方法
  ↓ POST /api/risk/metrics (后端端点)
```

### 2. 缺少错误兜底

**问题**：
- API 调用失败时直接抛异常，工具崩溃
- 没有降级策略，导致熔断检查任务失败
- 可能触发 Agent 重试循环

---

## ✅ 修复方案

### 修复 1: 纠正方法名

```typescript
// ✅ 修复后
const riskMetrics: any = await qv2.getRiskMetrics({ account_name: accountName, days: 60 });
```

### 修复 2: 添加错误兜底（三层防护）

```typescript
// 1. 计算 60 日最大回撤（错误兜底：API 不可用时降级为 0 不触发熔断）
let maxDrawdown = 0;
try {
  const riskMetrics: any = await qv2.getRiskMetrics({ account_name: accountName, days: 60 });
  maxDrawdown = Number(riskMetrics?.max_drawdown || 0);
} catch (e: any) {
  // API 调用失败：记录错误并降级（返回 0 回撤 = 不触发熔断，避免误杀）
  const errorMsg = e.message || String(e);
  console.error(`[m4_circuit_breaker_check] getRiskMetrics 失败: ${errorMsg}`);

  // 记录故障到 osMemory 供后续排查
  try {
    await this.osMemory.write({
      title: 'M4-2 熔断检查故障',
      content: JSON.stringify({
        error: errorMsg,
        timestamp: now,
        fallback: 'max_drawdown=0（不触发熔断）',
        hint: 'quantsys-v2 后端 /api/risk/metrics 不可用，检查后端日志或用 quantsys_v2_status 诊断',
      }),
      namespace: 'risk',
      tags: ['m4', 'circuit_breaker_error', 'api_failure'],
    });
  } catch { /* 落库失败不再抛出，避免二次错误 */ }

  // 返回降级结果（不触发熔断逻辑）
  return {
    checked_at: now,
    max_drawdown: 0,
    triggered: false,
    unblocked: false,
    error: errorMsg,
    actions: ['检查失败（API 不可用），降级跳过本次熔断判定'],
    circuit_breaker_status: null,
  };
}
```

---

## 🛡️ 防护策略

### 三层防护机制

| 层级 | 策略 | 目的 |
|------|------|------|
| **L1: Try-Catch** | 捕获所有 API 异常 | 防止工具崩溃 |
| **L2: 错误记录** | 落库到 osMemory (risk namespace) | 供后续排查，即使落库失败也不抛错 |
| **L3: 降级返回** | 返回明确的错误状态和提示 | Agent 收到可理解的错误信息，不会重试死循环 |

### 降级原则

**保守策略**：API 不可用时，假设回撤为 0（不触发熔断）

**理由**：
- ✅ 宁可不管也不误杀（避免因后端故障误触发熔断减仓）
- ✅ 错误信息清晰，Agent 知道是暂时性故障
- ✅ 下次任务重试时自动恢复（后端恢复后正常检查）

---

## 📊 修复前后对比

### 修复前

```
Agent 调度任务触发 m4_circuit_breaker_check
  ↓
调用 qv2.riskMetrics() ❌ 方法不存在
  ↓
工具崩溃，Agent 看到堆栈错误
  ↓
Agent 可能重试，陷入死循环
```

### 修复后

```
Agent 调度任务触发 m4_circuit_breaker_check
  ↓
调用 qv2.getRiskMetrics() ✅ 方法正确
  ↓
API 调用失败（后端故障）
  ↓
捕获异常 → 记录到 osMemory → 降级返回清晰错误
  ↓
Agent 看到："检查失败（API 不可用），降级跳过本次熔断判定"
  ↓
不重试，等待下次调度（16:30）
```

---

## 🎯 设计启示

### 关键经验

1. **API 调用必须有兜底**
   - 所有外部调用（后端 API、数据库、第三方服务）都可能失败
   - 工具层必须处理所有异常，返回明确的错误信息

2. **降级策略要合理**
   - 不同场景的降级策略不同：
     - 数据查询失败 → 返回空 + 提示原因
     - 风控检查失败 → 保守策略（不触发风控动作）
     - 交易执行失败 → 明确拒绝 + 引导修正

3. **错误信息要可操作**
   - ❌ 差：`Error: HTTP 405`
   - ✅ 好：`检查失败（API 不可用），降级跳过本次熔断判定。用 quantsys_v2_status 检查后端健康。`

4. **防止错误级联**
   - 主逻辑失败 → 记录错误到 osMemory
   - osMemory 写入失败 → 不再抛错（双重保护）

---

## 🔗 相关文档

- [M4 仓位与风控审计报告](./m4-audit-report.md) - P0 问题清单
- [M4-2 熔断检查调度器配置](./m4-2-circuit-breaker-scheduler.md) - Agent OS 任务配置
- [工具错误处理与路由设计](../TOOL-ERROR-HANDLING-AND-ROUTING.md) - 框架级错误处理方案

---

## ✅ 验收清单

- [x] 修正方法名 `riskMetrics` → `getRiskMetrics`
- [x] 添加 Try-Catch 错误捕获
- [x] 实现降级策略（回撤为 0，不触发熔断）
- [x] 错误记录到 osMemory（双重保护）
- [x] 返回清晰的错误提示信息
- [ ] 重启 agent-dh 加载新代码（待执行）
- [ ] 测试场景 1: 后端正常，工具正常运行
- [ ] 测试场景 2: 后端异常，验证降级逻辑生效

---

## 📝 后续建议

### 立即行动

1. **重启 agent-dh** 加载修复代码
2. **监控下次执行**（工作日 16:30）验证修复生效

### 中期改进

1. **添加单元测试**
   - 测试 API 正常调用
   - 测试 API 失败降级
   - 测试 osMemory 写入失败兜底

2. **统一错误处理模式**
   - 将三层防护模式推广到其他工具
   - 参考 [TOOL-ERROR-HANDLING-AND-ROUTING.md](../TOOL-ERROR-HANDLING-AND-ROUTING.md)

3. **监控告警**
   - osMemory 中 `circuit_breaker_error` 标签累积时，发送飞书告警
   - 连续 3 次失败 → 高优告警（后端可能挂掉）

---

**修复时间**: 2026-08-28  
**修复人**: Claude (based on user investigation)  
**审核**: 待用户验证
