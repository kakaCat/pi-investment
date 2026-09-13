---
id: wl-2026-08-bug-fix-report
title: Bug 修复报告
type: worklog
status: archived
updated: 2026-08-26
owners: [agent-dh]
tags: [worklog, 2026-08]
---

# Bug 修复报告

**日期**: 2026-08-26
**修复人员**: AI Assistant
**影响范围**: quantsys-v2-client, risk plugin, intelligence plugin

---

## 修复总览

| Bug ID | 状态 | 严重程度 | 影响 |
|--------|------|----------|------|
| Bug 1: /api/risk/metrics 忽略 account_name | ❌ 需后端修复 | 🔴 高 | R-007 熔断误报，R-001 仓位控制被架空 |
| Bug 2: watch_manage 契约错位 | ✅ 已修复 | 🟡 中 | 无法创建盯盘规则 (400 错误) |

---

## Bug 1: /api/risk/metrics 忽略 account_name 参数

### 问题描述
后端 `/api/risk/metrics` 接口忽略 `account_name` 参数，对所有账户返回完全相同的回撤数据。

### 影响分析
- **直接影响**: 三个账户 (agent_virtual, agent_a, agent_b) 获取相同的 `maxDrawdown` 值
- **连锁影响**: 
  - R-007 熔断规则：任何一个账户触发 8% 回撤阈值，所有账户都会被熔断
  - R-001 仓位控制：`regime_position_limit` 工具会对所有账户返回 `circuit_breaker` 状态
  - 实质架空了账户级别的风险控制

### 根本原因
后端实现问题，未按 `account_name` 过滤数据。

### 客户端代码验证
客户端代码是正确的：

**quantsys-v2-client/src/client.ts (Line 667-676)**:
```typescript
async getRiskMetrics(params?: {
  account_name?: string;
  days?: number;
}): Promise<RiskMetrics> {
  const response = await this.client.post('/api/risk/metrics', {
    account_name: params?.account_name || 'agent_virtual',  // ✓ 正确发送
    days: params?.days || 60,
  });
  return this.unwrap<RiskMetrics>(response.data, 'getRiskMetrics');
}
```

**packages/risk/src/index.ts (Line 239)**:
```typescript
const metrics = await this.qv2.getRiskMetrics({ 
  account_name,  // ✓ 正确传递
  days: 60 
});
```

### 需要的后端修复
后端 `/api/risk/metrics` 接口必须：
1. 接受并使用 `account_name` 参数
2. 按账户查询交易历史 (trades 表过滤 account_name)
3. 按账户计算收益率序列
4. 返回该账户的专属风险指标

### 验证方法
修复后，用以下方法验证：
```bash
# 查询不同账户，应返回不同的 maxDrawdown
curl -X POST http://localhost:5001/api/risk/metrics \
  -H "Content-Type: application/json" \
  -d '{"account_name": "agent_virtual", "days": 60}'

curl -X POST http://localhost:5001/api/risk/metrics \
  -H "Content-Type: application/json" \
  -d '{"account_name": "agent_a", "days": 60}'
```

---

## Bug 2: watch_manage 工具契约错位 ✅ 已修复

### 问题描述
`watch_manage` 工具接受 `condition` 字符串参数 (如 "price>100")，但后端期望 `conditions` 数组。

### 影响
创建盯盘规则时总是返回 400 Bad Request，功能完全不可用。

### 根本原因
工具层与后端 API 契约不一致：
- **工具参数**: `condition: string` (如 "price>100")
- **后端期望**: `conditions: Array<{type, params}>` (如 `[{type: "price_threshold", params: {operator: ">", value: 100}}]`)

### 修复方案
在 `quantsys-v2-client` 中添加转换层，将 condition 字符串解析为 conditions 数组。

### 修复内容

#### 1. 新增 `parseCondition()` 私有方法
**文件**: `quantsys-v2-client/src/client.ts`  
**位置**: Line 94-141

```typescript
/**
 * Parse condition string to conditions array for watch rules
 * Examples:
 *   "price>100" -> [{type: "price_threshold", params: {operator: ">", value: 100}}]
 *   "change_pct>5" -> [{type: "change_pct_threshold", params: {operator: ">", value: 5}}]
 *   "volume>1000000" -> [{type: "volume_threshold", params: {operator: ">", value: 1000000}}]
 */
private parseCondition(condition: string): Array<{type: string; params: Record<string, any>}> {
  const match = condition.trim().match(/^([a-z_]+)\s*(>=?|<=?|=)\s*(-?[0-9]+\.?[0-9]*)$/);
  if (!match) {
    throw new Error(
      `Invalid watch condition format: "${condition}". \n` +
      `Expected: "field operator value" (e.g., "price>100", "change_pct>=5")\n` +
      `Supported fields: price, change_pct, volume\n` +
      `Supported operators: >, <, >=, <=, =`
    );
  }
  const [, field, operator, valueStr] = match;
  const value = parseFloat(valueStr);
  
  const typeMap: Record<string, string> = {
    price: 'price_threshold',
    change_pct: 'change_pct_threshold',
    volume: 'volume_threshold',
  };
  
  const type = typeMap[field];
  if (!type) {
    throw new Error(
      `Unknown watch condition field: "${field}".\n` +
      `Supported fields: price, change_pct, volume`
    );
  }
  
  return [{
    type,
    params: { operator, value }
  }];
}
```

**特性**:
- ✅ 支持字段: `price`, `change_pct`, `volume`
- ✅ 支持操作符: `>`, `<`, `>=`, `<=`, `=`
- ✅ 支持整数和小数
- ✅ 支持负数 (如 change_pct>-5)
- ✅ 容错空格 (如 "price > 100")
- ✅ 友好的错误消息

#### 2. 修改 `manageWatchRule()` 方法
**文件**: `quantsys-v2-client/src/client.ts`  
**位置**: Line 611-620

```typescript
async manageWatchRule(params: WatchRuleManageRequest): Promise<any> {
  const { action, rule_id, condition, ...rest } = params;
  if (action === 'create') {
    // Transform condition string to conditions array (backend contract)
    const conditions = condition ? this.parseCondition(condition) : [];
    const body = { ...rest, conditions };
    const response = await this.client.post('/api/watch/rules', body);
    return this.unwrap(response.data, 'manageWatchRule');
  }
  // ... enable/disable/delete actions unchanged
}
```

### 测试结果

**单元测试**: ✅ 12/12 通过

| 测试用例 | 输入 | 结果 |
|---------|------|------|
| 基本价格条件 | `"price>100"` | ✅ 通过 |
| 带空格 | `"price > 100"` | ✅ 通过 |
| 涨跌幅条件 | `"change_pct>=5"` | ✅ 通过 |
| 成交量条件 | `"volume<1000000"` | ✅ 通过 |
| 小数值 | `"price>99.5"` | ✅ 通过 |
| 负数值 | `"change_pct>-5"` | ✅ 通过 |
| 前后有空格 | `"  price  <=  200  "` | ✅ 通过 |
| 无效格式 | `"price"`, `"price>"`, `">100"` | ✅ 正确抛出错误 |
| 不支持字段 | `"invalid>100"` | ✅ 正确抛出错误 |
| 非数字值 | `"price>abc"` | ✅ 正确抛出错误 |

### 使用示例

修复后，工具可以正常使用：

```typescript
// 创建盯盘规则
await client.manageWatchRule({
  action: 'create',
  name: '茅台价格突破2000',
  symbol: '600519',
  condition: 'price>2000'  // 字符串格式
});

// 后端收到的数据:
{
  name: '茅台价格突破2000',
  symbol: '600519',
  conditions: [{
    type: 'price_threshold',
    params: { operator: '>', value: 2000 }
  }]
}
```

### 测试文件
已创建以下测试文件供后续回归测试：
- `quantsys-v2-client/test/watch-manage.test.ts` - Jest 单元测试
- `quantsys-v2-client/test/manual-test-watch-manage.ts` - 手动集成测试脚本

---

## 修复清单

### 已完成 ✅
- [x] 定位 Bug 2 根本原因
- [x] 实现 parseCondition() 方法
- [x] 改进正则表达式支持空格和负数
- [x] 修改 manageWatchRule() 调用 parseCondition()
- [x] 编写单元测试
- [x] 验证测试通过 (12/12)
- [x] 创建测试文件
- [x] 编写修复文档

### 待处理 ⏳
- [ ] Bug 1: 后端修复 /api/risk/metrics 接口
- [ ] Bug 1: 后端修复后验证熔断功能
- [ ] Bug 2: 集成测试（需要后端运行）
- [ ] 代码 Review
- [ ] 合并到主分支

---

## 回归测试建议

### Bug 2 回归测试
```bash
# 1. 启动后端
cd /path/to/quantsys-backend
python app.py

# 2. 运行集成测试
cd /Users/yunpeng/pi-investment/quantsys-v2-client
npx ts-node test/manual-test-watch-manage.ts
```

### Bug 1 后端修复后测试
```bash
# 测试不同账户返回不同指标
curl -X POST http://localhost:5001/api/risk/metrics \
  -H "Content-Type: application/json" \
  -d '{"account_name": "agent_virtual", "days": 60}'

curl -X POST http://localhost:5001/api/risk/metrics \
  -H "Content-Type: application/json" \
  -d '{"account_name": "agent_a", "days": 60}'

# 使用 regime_position_limit 工具验证
# 应该每个账户返回独立的 circuit_breaker 状态
```

---

## 风险评估

| 风险项 | 严重程度 | 缓解措施 |
|--------|----------|----------|
| Bug 2 修复引入新 bug | 低 | 已通过 12 个单元测试验证 |
| 正则表达式性能 | 极低 | 简单正则，单次调用，无性能影响 |
| 后端不兼容 | 低 | 转换逻辑基于后端 WatchRule 类型定义 |
| Bug 1 持续影响 | 高 | ⚠️ 需立即修复后端，临时建议只用单账户 |

---

## 联系人
- **修复执行**: AI Assistant
- **Code Review**: 待指派
- **后端修复**: 待指派

---

**文档版本**: 1.0  
**最后更新**: 2026-08-26T03:09:44.549Z
