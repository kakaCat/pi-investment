# 业务逻辑优化任务清单

**创建时间**: 2026-05-15  
**最后更新**: 2026-05-15  
**状态**: P0/P1 已完成，P2 进行中

---

## 优化目标

修复业务逻辑中的不一致性和数据准确性问题，确保：
1. 卖出逻辑统一（手动卖出 vs 挂单成交）
2. 手续费计算准确
3. 盈亏记录完整
4. 数据完整性保护
5. 并发安全

---

## ✅ 已完成

### 1. 卖出盈亏计算扣除手续费
**完成时间**: 2026-05-15  
**Commit**: 95fe3c3

**修复内容**：
- 修改 `PortfolioService.sell()` 盈亏计算公式
- 之前：`pnlAmount = (price - avg_cost) * quantity`
- 现在：`pnlAmount = (price * quantity - commission) - (avg_cost * quantity)`

**影响**：
- 手动卖出的盈亏计算更准确
- 扣除手续费后的实际盈亏

---

### 2. 返回值优化（LLM 反馈优化）
**完成时间**: 2026-05-15  
**Commit**: 95fe3c3

**优化内容**：
- `PortfolioService.add()` 返回 `updatedHolding`
- `PortfolioService.sell()` 返回 `updatedHolding` + `portfolioSnapshot`
- `OrderService.fillOrder()` 返回 `updatedHolding` + `remainingOrders`
- `OrderService.checkAndFillOrders()` 返回 `portfolioSnapshot` + `remainingOrders`

**效果**：
- 减少工具调用次数：3次 → 1次（67% 减少）
- LLM 一次调用获得完整反馈
- 降低延迟和 token 消耗

---

### 3. P0-1: 统一卖出逻辑 ✅
**完成时间**: 2026-05-15  
**Commit**: 3e2986d

**修复内容**：
- `OrderService.fillOrder()` 卖出时统一调用 `PortfolioService.sell()`
- 移除重复的持仓更新和交易记录代码
- 确保挂单成交的卖出有盈亏记录

**影响**：
- 手动卖出和挂单成交卖出逻辑完全一致
- 挂单成交的卖出有完整的盈亏记录
- 交易记录不重复

---

### 4. P0-2: 挂单成交手续费计算 ✅
**完成时间**: 2026-05-15  
**Commit**: 3e2986d

**修复内容**：
- 新增 `OrderService.calculateCommission()` 方法
- A股：万2.5，最低5元
- 港股：万5，最低5港币
- 买入时手续费计入持仓成本
- 卖出时手续费从收益扣除

**测试覆盖**：
- 手续费计算测试（4个测试用例）
- 买入成本验证
- 卖出盈亏验证

---

### 5. P1: 挂单支持自定义手续费率 ✅
**完成时间**: 2026-05-15  
**Commit**: 6f1957e

**实现内容**：
- `PendingOrder` 接口添加 `commission_rate?: number` 字段
- `OrderService.create()` 支持传入自定义手续费率
- `OrderService.calculateCommission()` 优先使用自定义费率
- 工具层暴露 `commission_rate` 参数

**使用示例**：
```typescript
// 创建挂单时指定万3费率
orderService.create({
  symbol: "600519",
  name: "茅台",
  side: "buy",
  type: "limit",
  price: 1800,
  quantity: 100,
  market: "A",
  commission_rate: 0.0003, // 万3
});
```

---

### 6. 数据完整性保护 ✅
**完成时间**: 2026-05-15  
**Commit**: 34214cc, cb88d0f

**修复内容**：
- 修复 `trades.json` 格式错误（数组 → 对象）
- `TradeService.load()` 添加自动迁移机制
- 所有数据服务添加格式验证和错误日志
- 防止静默失败导致数据丢失

**影响**：
- `TradeService`、`PortfolioService`、`OrderService` 都有完整的数据保护
- 格式错误时输出清晰的错误日志
- 自动处理格式兼容性问题

---

## 🔧 P2 - 并发安全保护（进行中）

### 问题描述

**场景**：
- 多个挂单同时触发可能导致超卖
- 文件读写没有锁机制
- 读-修改-写操作不是原子的

**示例**：
```
时间线：
T1: 进程A读取 portfolio.json（持仓100股）
T2: 进程B读取 portfolio.json（持仓100股）
T3: 进程A卖出50股，写入 portfolio.json（持仓50股）
T4: 进程B卖出60股，写入 portfolio.json（持仓40股）❌
结果：实际卖出110股，但持仓显示40股（数据不一致）
```

### 实现方案

**方案1：文件锁（推荐）**
- 使用 `proper-lockfile` 库
- 在所有数据服务的 `save()` 方法中添加锁保护
- 确保读-修改-写操作的原子性

**方案2：乐观锁**
- 在数据文件中添加版本号字段
- 写入前检查版本号是否匹配
- 不匹配则重试

**选择方案1**，因为：
- 实现简单，侵入性小
- 性能开销可接受（本地文件锁）
- 适合单机多进程场景

### 实现计划

1. 安装 `proper-lockfile` 依赖
2. 创建 `FileLockService` 工具类
3. 修改所有数据服务的 `save()` 方法
4. 添加测试验证并发安全
5. 更新文档

---

## 验证清单

- [x] 挂单成交的卖出有盈亏记录
- [x] 挂单成交的买入/卖出计算手续费
- [x] 手动卖出和挂单成交卖出逻辑一致
- [x] 交易记录不重复
- [x] 所有测试通过（22个测试用例）
- [x] TypeScript 编译无错误
- [x] 数据格式验证和错误日志
- [ ] 并发安全保护

---

## 参考

- 架构重构 Commit: e7b3284
- LLM 反馈优化 Commit: 95fe3c3
- P0 优化 Commit: 3e2986d
- P1 优化 Commit: 6f1957e
- 数据完整性 Commit: 34214cc, cb88d0f
