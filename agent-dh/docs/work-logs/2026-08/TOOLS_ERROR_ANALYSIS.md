---
id: wl-2026-08-tools-error-analysis
title: Agent-DH 工具错误原因评估报告
type: worklog
status: archived
updated: 2026-08-29
owners: [agent-dh]
tags: [worklog, 2026-08]
---

# Agent-DH 工具错误原因评估报告

生成时间: 2026-08-29
评估范围: 14 个工具问题

---

## 评估方法论

1. **代码检查**: 读取工具实现和注册代码
2. **接口测试**: 实际调用后端 API 验证返回格式
3. **对比分析**: 比较期望 Schema 与实际返回数据
4. **根因定位**: 识别是前端问题、后端问题还是契约不一致

---

## 一、工具注册问题评估（3个）

### 1.1 memory_search - "osMemory 未注入"

**错误现象**: 工具期望 `osMemory` 但找不到

**代码检查**:
- ✅ `MemorySearchTool` 已正确迁移到 `MemoryClient`
- ✅ `memory/src/index.ts` 已使用 `aos.memory` (MemoryClient 实例)
- ✅ 注册代码：`ctx.tools.register(createMemorySearchTool(aos.memory))`

**根本原因**: **测试代码问题或缓存问题**
- 代码已完成迁移
- 可能是测试脚本使用了旧的注入名称
- 或者测试环境未重新加载新代码

**修复方案**: 
- 不需要修改代码（代码已正确）
- 检查测试脚本中的依赖注入配置
- 确保测试环境使用最新构建

**优先级**: P2（低）- 代码正确，可能是测试环境问题

---

### 1.2 data_quality_report - ".run is not a function"

**错误现象**: 工具实例没有 `.run()` 方法

**代码检查** (`data-manager/src/index.ts:92`):
```typescript
const result = await dataQualityReportTool.run(args, {});
```

**根本原因**: **注册方式不一致**
- 其他包使用 `tool.toDSHToolDefinition()` 方法
- data-manager 包手动构建 defineTool 并在 execute 中调用 `.run()`
- 这是**合法的两种注册方式**，并非错误

**实际问题**: 
1. 如果 `.run()` 不存在，说明 `DataQualityReportTool` 未正确继承 `BaseTool`
2. 需要检查 `DataQualityReportTool.ts` 实现

**修复方案**:
- 检查 `DataQualityReportTool` 是否 `extends BaseTool`
- 确认构造函数正确调用 `super()`

**优先级**: P1（高）- 如果确实缺少 `.run()` 方法

---

### 1.3 data_manager - ".run is not a function"

**根本原因**: 同 1.2

**修复方案**: 同 1.2

**优先级**: P1（高）

---

## 二、后端接口问题评估（5个）

### 2.1 data_fetch_financial - 404 Not Found

**接口测试**:
```bash
curl "http://localhost:5001/api/market/financial?symbol=600519"
→ 404 Not Found
```

**代码检查**:
- ✅ 实际端点: `/api/v2/stock/{symbol}/financials` (在 `financials_async.py`)
- ❌ 工具调用: `/api/market/financial?symbol=...`

**根本原因**: **API 路径不匹配**
- 后端路由: `/api/v2/stock/{symbol}/financials`
- 工具期望: `/api/market/financial?symbol=...`

**影响范围**: 
- `DataFetchFinancialTool` 需要更新 API 路径
- 或者后端需要添加兼容路由

**修复方案**:
1. 检查 `QuantsysV2Client.getFinancialData()` 使用的路径
2. 更新为 `/api/v2/stock/${symbol}/financials`
3. 测试返回数据格式是否匹配 Schema

**优先级**: P0（最高）- 核心功能，路径错误

---

### 2.2 data_fetch_north_flow - 503 + NorthHoldingsCCASSSource 未定义

**错误信息**: `name 'NorthHoldingsCCASSSource' is not defined`

**根本原因**: **Python 后端代码错误**
- 后端代码引用了未导入的类
- 明确的代码缺陷

**修复方案**:
1. 在后端代码中找到引用 `NorthHoldingsCCASSSource` 的位置
2. 添加正确的 import 语句
3. 或者注释掉该数据源，使用备用方案

**优先级**: P0（最高）- 明确的代码错误

---

### 2.3 trade_monitor - success: false, error: null

**接口测试**: 返回 `{success: false, error: null}`

**根本原因**: **空数据或业务逻辑问题**
- 不是 404（接口存在）
- 不是 500（没有错误信息）
- 可能是账户没有交易活动

**修复方案**:
- 查看后端日志确认原因
- 确认工具的 wrap() 是否正确处理空数据场景
- 可能需要模拟一些交易数据

**优先级**: P2（低）- 业务逻辑问题，非技术错误

---

### 2.4 risk_barra_decomposition - success: false, error: null

**根本原因**: 同 2.3 - **空数据或业务逻辑问题**

**修复方案**: 同 2.3

**优先级**: P2（低）- 复杂功能，可能需要数据准备

---

### 2.5 opportunity_scan - success: false, error: null

**根本原因**: **需要查看后端日志**
- POST 请求
- 可能参数校验失败
- 或者业务逻辑异常

**修复方案**:
1. 查看 quantsys-v2 后端日志
2. 确认请求参数格式
3. 根据日志修复

**优先级**: P1（中）- 策略核心功能

---

## 三、Schema 不匹配问题评估（6个）

### 3.1 data_fetch_financial

**问题**: 
1. API 路径 404（见 2.1）
2. Schema 可能不匹配

**评估计划**:
1. 先修复 API 路径问题
2. 获取实际返回数据
3. 对比 `DataFetchFinancialResult` 接口定义
4. 调整不匹配的字段

**优先级**: P0（最高）- 依赖 API 路径修复

---

### 3.2 strategy_list

**接口测试**:
```bash
curl "http://localhost:5001/api/strategies"
→ {success: true, error: null}
```

**初步判断**: 接口正常，返回了数据

**评估需要**:
1. 读取完整返回数据
2. 对比 `StrategyListResult` Schema
3. 找出不匹配字段

**优先级**: P1（高）

---

### 3.3 risk_controller

**评估需要**: 同 3.2

**优先级**: P1（高）

---

### 3.4 quantsys_v2_status

**评估需要**: 
1. 找到正确的 API 端点
2. 测试返回格式
3. 对比 Schema

**优先级**: P2（中）

---

### 3.5 quantsys_v2_logs

**评估需要**: 同 3.4

**优先级**: P2（中）

---

### 3.6 agent_os_status

**评估需要**: 同 3.4

**优先级**: P2（中）

---

## 四、问题分类统计

| 问题类型 | 数量 | 根因 | 修复复杂度 |
|---------|------|------|-----------|
| API 路径错误 | 1 | data_fetch_financial - 路径不匹配 | 简单 |
| 后端代码错误 | 1 | data_fetch_north_flow - 类未导入 | 简单 |
| 空数据/业务逻辑 | 3 | trade_monitor, risk_barra, opportunity_scan | 中等 |
| Schema 需验证 | 6 | 需要逐个对比实际返回格式 | 中等 |
| 测试环境问题 | 1 | memory_search - 代码已正确 | 简单 |
| 工具继承问题 | 2 | data_quality_report, data_manager - 需验证 | 简单 |
| **总计** | **14** | | |

---

## 五、修复优先级重排（基于根因）

### Phase 0: 明确的代码错误（立即修复）
1. ✅ **data_fetch_north_flow** - 后端类未导入（5分钟）
2. ✅ **data_fetch_financial** - API 路径错误（10分钟）

### Phase 1: 工具结构验证（需要代码检查）
3. **data_quality_report** - 验证是否继承 BaseTool（10分钟）
4. **data_manager** - 验证是否继承 BaseTool（5分钟）

### Phase 2: Schema 对齐（需要逐个测试）
5. **strategy_list** - 接口正常，对比 Schema（15分钟）
6. **risk_controller** - 测试 + Schema 对比（15分钟）
7. **data_fetch_financial** - API 修复后对齐 Schema（15分钟）
8. **quantsys_v2_status** - 找端点 + Schema（15分钟）
9. **quantsys_v2_logs** - 找端点 + Schema（15分钟）
10. **agent_os_status** - 找端点 + Schema（15分钟）

### Phase 3: 业务逻辑问题（需要深入调查）
11. **opportunity_scan** - 查日志定位原因（30分钟）
12. **trade_monitor** - 业务逻辑或数据准备（30分钟）
13. **risk_barra_decomposition** - 复杂功能，需数据（30分钟）

### Phase 4: 测试环境问题（最后处理）
14. **memory_search** - 测试脚本修复（10分钟）

---

## 六、下一步行动建议

### 立即执行（Phase 0）：
1. 修复 `data_fetch_north_flow` 后端导入错误
2. 修复 `data_fetch_financial` API 路径

### 快速验证（Phase 1）：
3. 检查 `DataQualityReportTool` 和 `DataManagerTool` 是否正确继承

### 系统对齐（Phase 2）：
4. 逐个测试接口，对比 Schema，修复不匹配

### 深度调查（Phase 3+4）：
5. 根据日志和业务需求处理剩余问题

---

**总预估工作量**: 3-4 小时
**可立即修复**: Phase 0 + Phase 1 (30分钟)
**核心修复**: Phase 0 + Phase 1 + Phase 2 (2.5小时)

开始执行 Phase 0？
