# 业务逻辑优化任务清单

**创建时间**: 2026-05-15  
**最后更新**: 2026-05-15  
**状态**: ✅ 全部完成（P0/P1/P2）

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

## ✅ P2 - 并发安全保护（已完成）

**完成时间**: 2026-05-15  
**Commit**: 92db280

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

**选择方案：文件锁**
- 使用 `proper-lockfile` 库
- 创建 `FileLockService` 工具类
- 在所有写操作外层包裹文件锁
- 确保读-修改-写操作的原子性

### 实现内容

1. **FileLockService 工具类**
   - 提供同步锁接口：`withLockSync()`
   - 提供异步锁接口：`withLock()`
   - 自动处理锁超时（10秒）和更新（2秒）

2. **TradeService 并发保护**
   - `add()` 方法：锁保护下读取-修改-写入
   - `save()` 方法：锁保护下写入文件

3. **PortfolioService 并发保护**
   - `add()` 方法：锁保护下加仓/新建持仓
   - `sell()` 方法：锁保护下卖出操作
   - `update()` 方法：锁保护下更新持仓
   - `remove()` 方法：锁保护下删除持仓
   - `replaceHoldings()` 方法：锁保护下批量替换

4. **OrderService 并发保护**
   - `create()` 方法：锁保护下创建挂单
   - `cancel()` 方法：锁保护下撤销挂单
   - `expire()` 方法：锁保护下标记过期
   - `expireOverdue()` 方法：锁保护下批量过期
   - `fill()` 方法：锁保护下标记成交

### 技术细节

- 在锁内重新加载数据，确保读取最新状态
- 直接写入文件，避免重复加锁
- 同步 API 不支持 retries 选项，仅设置 stale 超时
- 所有核心数据文件（trades.json、portfolio.json、orders.json）都有完整保护

### 测试验证

- 所有 25 个测试通过
- TradeService: 5 个测试
- PortfolioService: 10 个测试
- OrderService: 10 个测试

### 防止的并发问题

- ✅ 多个挂单同时成交导致超卖
- ✅ 并发买入导致持仓成本计算错误
- ✅ 并发写入导致数据丢失或覆盖
- ✅ 读-修改-写操作的竞态条件

---

## 验证清单

- [x] 挂单成交的卖出有盈亏记录
- [x] 挂单成交的买入/卖出计算手续费
- [x] 手动卖出和挂单成交卖出逻辑一致
- [x] 交易记录不重复
- [x] 所有测试通过（25个测试用例）
- [x] TypeScript 编译无错误
- [x] 数据格式验证和错误日志
- [x] 并发安全保护

---

## 参考

- 架构重构 Commit: e7b3284
- LLM 反馈优化 Commit: 95fe3c3
- P0 优化 Commit: 3e2986d
- P1 优化 Commit: 6f1957e
- 数据完整性 Commit: 34214cc, cb88d0f
- P2 并发安全 Commit: 92db280

---

## 总结

所有业务逻辑优化任务已完成：

1. **P0 优化**：统一卖出逻辑，添加手续费自动计算
2. **P1 优化**：支持自定义手续费率配置
3. **P2 优化**：添加文件锁保护，防止并发冲突
4. **数据完整性**：格式验证、自动迁移、错误日志
5. **LLM 反馈优化**：增强返回值，减少工具调用次数

系统现在具备：
- ✅ 完整的业务逻辑一致性
- ✅ 准确的手续费计算和盈亏记录
- ✅ 完善的数据完整性保护
- ✅ 可靠的并发安全机制
- ✅ 优秀的 LLM 交互体验
