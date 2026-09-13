---
id: wl-2026-08-tools-fix-plan
title: Agent-DH 工具修复方案
type: worklog
status: archived
updated: 2026-08-29
owners: [agent-dh]
tags: [worklog, 2026-08]
---

# Agent-DH 工具修复方案

生成时间: 2026-08-29
任务: 修复工具测试中发现的 14 个问题

---

## 问题总览

| 类型 | 数量 | 问题工具 |
|------|------|----------|
| 后端接口问题 | 5 | trade_monitor, risk_barra_decomposition, opportunity_scan, data_fetch_north_flow, data_fetch_financial |
| Schema 不匹配 | 6 | data_fetch_financial, strategy_list, risk_controller, quantsys_v2_status, quantsys_v2_logs, agent_os_status |
| 工具注册问题 | 3 | memory_search, data_quality_report, data_manager |
| **总计** | **14** | |

---

## 一、后端接口问题（5个）

### 1.1 trade_monitor - 返回空数据

**问题**: 接口返回 `{success: false, error: null}` - 表示没有监控数据

**根因分析**:
- 接口正常响应，不是 404
- 可能是账户没有交易活动
- 需要确认是否需要模拟数据

**修复方案**:
- [ ] 检查 trade_monitor 工具的 wrap() 阶段是否正确处理空数据情况
- [ ] 确认后端是否应该返回空数组而不是 success: false

**优先级**: P2（低） - 功能逻辑问题，不影响工具结构

---

### 1.2 risk_barra_decomposition - 返回空数据

**问题**: 接口返回 `{success: false, error: null}`

**根因分析**:
- Barra 风险分解需要持仓数据和因子数据
- 可能缺少必要的数据或计算失败

**修复方案**:
- [ ] 检查后端是否实现了 Barra 分解逻辑
- [ ] 确认工具是否能正确处理"暂无数据"的情况

**优先级**: P2（低） - 复杂功能，可能需要后端完善

---

### 1.3 opportunity_scan - 500 错误

**问题**: 接口返回 `{success: false, error: null}`

**根因分析**:
- POST 请求，可能参数校验失败
- 需要检查后端日志

**修复方案**:
- [ ] 查看 quantsys-v2 后端日志
- [ ] 检查工具发送的参数格式是否正确
- [ ] 确认后端 API 实现状态

**优先级**: P1（中） - 策略相关核心功能

---

### 1.4 data_fetch_north_flow - 503 错误

**问题**: `北向资金估算失败: name 'NorthHoldingsCCASSSource' is not defined`

**根因分析**:
- Python 类未导入或未定义
- 后端代码问题

**修复方案**:
- [x] 已识别：后端缺少 `NorthHoldingsCCASSSource` 类的导入
- [ ] 在 quantsys-v2 中查找该类并修复导入
- [ ] 或者暂时禁用该数据源，使用备用方案

**优先级**: P1（高） - 明确的代码错误

**修复代码位置**: `quantsys-v2/adapters/inbound/fastapi_app/routes/*.py`

---

### 1.5 data_fetch_financial - 返回空数据

**问题**: 接口返回 `{success: false, error: null}`

**根因分析**:
- 财务数据可能需要特定的数据源配置
- 可能是数据未同步

**修复方案**:
- [ ] 检查后端数据源配置
- [ ] 确认是否需要先同步财务数据
- [ ] 工具的 Schema 也有不匹配问题（见 Schema 部分）

**优先级**: P1（中） - 投资分析核心功能

---

## 二、Schema 不匹配（6个）

### 2.1 data_fetch_financial

**问题**: Schema 验证失败

**修复方案**:
- [ ] 读取工具的 prompt.ts 查看期望的返回格式
- [ ] 对比后端实际返回的数据结构
- [ ] 调整工具的 Schema 或后端返回格式

**优先级**: P1（高）

---

### 2.2 strategy_list

**问题**: Schema 验证失败

**修复方案**:
- [ ] 读取 StrategyListTool 的 prompt.ts
- [ ] 测试后端 `/api/strategies` 返回格式
- [ ] 对齐 Schema

**优先级**: P1（高）

---

### 2.3 risk_controller

**问题**: Schema 验证失败

**修复方案**:
- [ ] 读取 RiskControllerTool 的 prompt.ts
- [ ] 测试后端 `/api/risk/controller` 返回格式
- [ ] 对齐 Schema

**优先级**: P1（高）

---

### 2.4 quantsys_v2_status

**问题**: Schema 验证失败

**修复方案**:
- [ ] 读取 QuantsysV2StatusTool 的 prompt.ts
- [ ] 测试后端 `/api/system/status` 返回格式
- [ ] 对齐 Schema

**优先级**: P2（中）

---

### 2.5 quantsys_v2_logs

**问题**: Schema 验证失败

**修复方案**:
- [ ] 读取 QuantsysV2LogsTool 的 prompt.ts
- [ ] 测试后端日志 API 返回格式
- [ ] 对齐 Schema

**优先级**: P2（中）

---

### 2.6 agent_os_status

**问题**: Schema 验证失败

**修复方案**:
- [ ] 读取 AgentOSStatusTool 的 prompt.ts
- [ ] 测试 Agent OS `/api/system/status` 返回格式
- [ ] 对齐 Schema

**优先级**: P2（中）

---

## 三、工具注册问题（3个）

### 3.1 memory_search - osMemory 未注入

**问题**: 工具期望 `osMemory` 但实际传入的是 `MemoryClient`

**根因分析**:
- 已完成迁移到 agent-os-client，但可能有遗漏
- 需要确认是否所有引用都已更新

**修复方案**:
- [ ] 检查 MemorySearchTool 构造函数参数
- [ ] 确认 memory/src/index.ts 中的注册代码
- [ ] 验证是否所有对 osMemory 的引用都已更新

**优先级**: P0（最高） - 已迁移但未完全生效

---

### 3.2 data_quality_report - .run is not a function

**问题**: 工具实例没有 `.run()` 方法

**根因分析**:
- 可能未继承 BaseTool
- 可能注册方式错误

**修复方案**:
- [ ] 读取 DataQualityReportTool 实现
- [ ] 确认是否正确继承 BaseTool
- [ ] 检查 data-manager/src/index.ts 注册代码

**优先级**: P1（高） - 结构性问题

---

### 3.3 data_manager - .run is not a function

**问题**: 工具实例没有 `.run()` 方法

**根因分析**:
- 与 data_quality_report 同样的问题
- data-manager 包可能有通用问题

**修复方案**:
- [ ] 读取 DataManagerTool 实现
- [ ] 确认是否正确继承 BaseTool
- [ ] 检查 data-manager/src/index.ts 注册代码

**优先级**: P1（高） - 结构性问题

---

## 修复顺序建议

### Phase 1: 结构性问题（阻塞性）
1. **memory_search** - osMemory 注入问题
2. **data_quality_report** - .run is not a function
3. **data_manager** - .run is not a function

### Phase 2: Schema 对齐（高优先级）
4. **data_fetch_financial** - Schema + 接口
5. **strategy_list** - Schema
6. **risk_controller** - Schema

### Phase 3: 后端代码错误
7. **data_fetch_north_flow** - NorthHoldingsCCASSSource 未定义

### Phase 4: Schema 对齐（中优先级）
8. **quantsys_v2_status** - Schema
9. **quantsys_v2_logs** - Schema
10. **agent_os_status** - Schema

### Phase 5: 功能逻辑问题（低优先级）
11. **opportunity_scan** - 500 错误调查
12. **trade_monitor** - 空数据处理
13. **risk_barra_decomposition** - 空数据处理

---

## 预期工作量

| Phase | 问题数 | 预估时间 | 复杂度 |
|-------|--------|----------|--------|
| Phase 1 | 3 | 30min | 简单（代码检查+修复） |
| Phase 2 | 3 | 1h | 中等（Schema 对齐） |
| Phase 3 | 1 | 20min | 简单（导入修复） |
| Phase 4 | 3 | 1h | 中等（Schema 对齐） |
| Phase 5 | 3 | 1-2h | 复杂（需调查） |
| **总计** | **13** | **3.5-4.5h** | |

---

## 下一步行动

1. **立即开始 Phase 1** - 修复 3 个结构性问题
2. **依次完成 Phase 2-4** - Schema 对齐和后端修复
3. **Phase 5 可延后** - 功能逻辑问题可在后续迭代中完善

开始修复？
