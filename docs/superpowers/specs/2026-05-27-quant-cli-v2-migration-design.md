# quant_cli 工具迁移到 quantsys-v2 API 设计文档

**日期**：2026-05-27  
**状态**：设计阶段  
**作者**：Claude (Kiro)

## 1. 背景

### 1.1 问题描述

TypeScript Agent 的 `quant_cli` 工具当前调用 v1 后台系统（`python -m quantsys.cli`），导致以下问题：

1. **命令缺失**：Agent 调用 `strategy.*`、`indicators.*` 命令时报错 "UNKNOWN_COMMAND"
2. **参数不匹配**：`backtest.run` 不接受 `strategy_id` 参数，Agent 重复调用失败
3. **架构不统一**：v1 使用 SQLite，v2 使用 PostgreSQL；v1 功能不完整

### 1.2 错误日志分析

从会话日志 `.pi-invest/sessions/20260527T09331_eacb5997/events.jsonl` 中发现：

- **Turn 10**：`strategy` 命令未知
- **Turn 15**：`backtest.run` 不支持 `strategy_id` 参数（重复 6 次）
- **Turn 42**：`backtest.run` 不支持 `strategy_id` 参数（重复 3 次）
- **Turn 43**：`strategy.get`、`strategy.create` 命令未知
- **Turn 48**：`indicators.run` 命令未知

**总计**：13 次工具调用失败，分布在 5 个回合。

### 1.3 架构决策

**核心决策**（2026-05-27）：TypeScript Agent 统一对接 quantsys-v2 后台系统，完全移除 v1 调用。

**理由**：
1. v2 功能完整（133 命令 vs v1 的 127 命令）
2. v2 架构清晰（分层架构 + PostgreSQL）
3. v2 包含所有 v1 功能 + 6 个新功能
4. 避免维护两套系统

## 2. 当前架构

### 2.1 v1 架构（待移除）

```
TypeScript Agent
    ↓ (spawn process)
quant_cli 工具 → python -m quantsys.cli → v1 CLI → SQLite
```

**特点**：
- 每次调用启动新 Python 进程（性能开销）
- 使用 SQLite 数据库
- 缺少 `strategy.*`、`indicators.*` 命令

### 2.2 v2 架构（目标）

```
TypeScript Agent
    ↓ (HTTP)
quant_cli 工具 → quantsys-v2 HTTP API (port 5001) → PostgreSQL
```

**特点**：
- HTTP 调用，无进程启动开销
- 使用 PostgreSQL 数据库
- 完整的命令支持（133 个命令）

## 3. 设计方案

### 3.1 核心变更

**文件修改**：`src/infrastructure/tools/core/quant-cli-tool.ts`

**变更内容**：
1. 移除 `import { runQuantCli }` from `quant-cli-client.ts`
2. 改为 `import { runQuantV2, V2_COMMAND_LIST }` from `quant-v2-client.ts`
3. 添加 v2 独有命令定义（6 个新命令）
4. 简化 `execute` 函数，直接调用 `runQuantV2()`

### 3.2 命令覆盖情况

**v1 命令**：127 个  
**v2 命令**：133 个

**v2 完全覆盖 v1**，额外提供 6 个新命令：
- `signal.test_run` - 运行信号测试
- `signal.test_record` - 记录测试结果
- `signal.test_verify` - 验证信号准确性
- `signal.test_stats` - 信号测试统计
- `strategy.run` - 实时运行策略（非回测）
- `strategy.status` - 查询策略运行状态

### 3.3 新增命令定义

需要在 `COMMANDS` 对象中添加以下命令定义：

```typescript
// Strategy 管理（v2 独有）
"strategy.run": {
  domain: "strategy",
  action: "run",
  description: "实时运行策略生成信号。",
  params: {
    strategy_id: { required: true, type: "string" },
    symbols: { type: "array" }
  },
  example: { strategy_id: "rsi_strategy", symbols: ["600519.SH"] }
},

"strategy.status": {
  domain: "strategy",
  action: "status",
  description: "查询策略运行状态。",
  params: {},
  example: {}
},

// Signal 测试（v2 独有）
"signal.test_run": {
  domain: "signal",
  action: "test-run",
  description: "运行策略信号测试。",
  params: {
    strategy_id: { required: true, type: "string" },
    symbol: { required: true, type: "string" },
    start_date: { type: "string" },
    end_date: { type: "string" }
  },
  example: { strategy_id: "rsi_strategy", symbol: "600519.SH" }
},

"signal.test_record": {
  domain: "signal",
  action: "test-record",
  description: "记录信号测试结果。",
  params: {
    test_id: { required: true, type: "string" },
    result: { required: true, type: "string" }
  },
  example: { test_id: "test_001", result: "success" }
},

"signal.test_verify": {
  domain: "signal",
  action: "test-verify",
  description: "验证信号准确性。",
  params: {
    test_id: { required: true, type: "string" }
  },
  example: { test_id: "test_001" }
},

"signal.test_stats": {
  domain: "signal",
  action: "test-stats",
  description: "获取信号测试统计数据。",
  params: {
    strategy_id: { type: "string" }
  },
  example: { strategy_id: "rsi_strategy" }
}
```

### 3.4 执行逻辑简化

**当前逻辑**（v1）：
```typescript
async execute(input: QuantCliInput): Promise<QuantCliOutput> {
  const { command, params } = input;
  const rule = COMMANDS[command];
  
  // 验证参数...
  
  // 调用 v1 CLI
  const response = await runQuantCli(rule.domain, rule.action, validatedParams);
  
  return formatOutput(response);
}
```

**新逻辑**（v2）：
```typescript
async execute(input: QuantCliInput): Promise<QuantCliOutput> {
  const { command, params } = input;
  const rule = COMMANDS[command];
  
  // 验证参数...
  
  // 直接调用 v2 API
  const response = await runQuantV2(command, validatedParams);
  
  return formatOutput(response);
}
```

**关键变化**：
1. 移除 `domain` 和 `action` 分离，直接使用 `command`（如 `strategy.list`）
2. `runQuantV2()` 内部处理命令到端点的映射
3. 响应格式已在 `runQuantV2()` 中转换为 `QuantCliResponse<T>`

## 4. 数据格式

### 4.1 响应格式转换

**v2 API 原始响应**：
```json
{
  "success": true,
  "data": { "symbol": "600519", "name": "贵州茅台" },
  "message": "success"
}
```

**转换后（QuantCliResponse）**：
```json
{
  "ok": true,
  "command": "stock.info",
  "params": { "symbol": "600519" },
  "data": { "symbol": "600519", "name": "贵州茅台" },
  "warnings": [],
  "error": null
}
```

**转换位置**：`runQuantV2()` 函数内部（已实现）

### 4.2 错误处理

**v2 服务未启动**：
```typescript
throw new QuantV2Error(
  `quantsys-v2 后端未启动。请先启动后端服务：
  cd quantsys-v2 && python start_all.py
或单独启动 REST API：
  cd quantsys-v2 && python api/server.py
预期端口：http://127.0.0.1:5001`,
  503,
  url
);
```

**命令不存在**：
```typescript
throw new QuantV2Error(
  `命令 ${command} 没有 v2 端点映射`,
  404,
  command
);
```

## 5. 实施计划

### 5.1 修改清单

| 文件 | 修改类型 | 说明 |
|------|---------|------|
| `src/infrastructure/tools/core/quant-cli-tool.ts` | 修改 | 切换到 v2 API，添加新命令定义 |
| `src/infrastructure/quant/quant-cli-client.ts` | 保留 | 暂时保留，供其他模块使用（如果有） |
| `src/infrastructure/quant/quant-v2-client.ts` | 无需修改 | 已完整实现 |

### 5.2 实施步骤

1. **修改 quant-cli-tool.ts**
   - 更新 import 语句
   - 添加 6 个新命令定义
   - 修改 execute 函数调用 `runQuantV2()`

2. **测试验证**
   - 测试原有命令（如 `stock.info`）
   - 测试新命令（如 `strategy.list`）
   - 测试错误场景（v2 服务未启动）

3. **文档更新**
   - 更新 CLAUDE.md，说明 Agent 统一使用 v2
   - 更新工具文档，添加新命令说明

4. **清理工作**（可选，后续进行）
   - 检查是否有其他模块使用 `runQuantCli()`
   - 如果没有，可以移除 `quant-cli-client.ts`

### 5.3 回滚方案

如果 v2 迁移出现问题，可以快速回滚：

1. 恢复 `quant-cli-tool.ts` 的 import 语句
2. 恢复 execute 函数调用 `runQuantCli()`
3. 移除新增的 6 个命令定义

**回滚成本**：低（单文件修改）

## 6. 风险评估

### 6.1 技术风险

| 风险 | 影响 | 概率 | 缓解措施 |
|------|------|------|---------|
| v2 服务不稳定 | 高 | 低 | v2 已在生产使用，稳定性验证 |
| 命令映射错误 | 中 | 低 | v2 映射表已完整实现并测试 |
| 响应格式不兼容 | 中 | 极低 | 已有转换逻辑，格式统一 |
| 性能下降 | 低 | 极低 | HTTP 调用比进程启动更快 |

### 6.2 业务风险

| 风险 | 影响 | 概率 | 缓解措施 |
|------|------|------|---------|
| Agent 功能中断 | 高 | 低 | 充分测试 + 快速回滚方案 |
| 用户体验下降 | 中 | 极低 | v2 功能更完整，体验提升 |

## 7. 成功标准

### 7.1 功能验证

- ✅ 所有 v1 命令在 v2 中正常工作
- ✅ 新命令（`strategy.*`, `indicators.*`）可用
- ✅ 错误日志中的 13 个失败调用全部修复
- ✅ 响应格式与 v1 兼容

### 7.2 性能指标

- ✅ 命令执行时间 < v1（无进程启动开销）
- ✅ 并发调用支持（HTTP 连接池）

### 7.3 稳定性指标

- ✅ v2 服务健康检查通过
- ✅ 错误提示清晰（服务未启动、命令不存在）

## 8. 后续优化

### 8.1 短期优化（1-2 周）

1. 监控 v2 API 调用性能
2. 收集 Agent 使用反馈
3. 优化错误提示信息

### 8.2 长期优化（1-3 月）

1. 移除 v1 CLI 代码（`quant/quantsys/cli/`）
2. v2 内部逐步移除对 v1 模块的依赖
3. 统一数据库到 PostgreSQL

## 9. 参考资料

- [Agent Backend Integration Memory](../../.claude/projects/-Users-mac-Documents-ai-pi-investment/memory/agent-backend-integration.md)
- [quantsys-v2 CLAUDE.md](../../../quantsys-v2/CLAUDE.md)
- [quant-v2-client.ts](../../../src/infrastructure/quant/quant-v2-client.ts)
- [Session Error Log](.pi-invest/sessions/20260527T09331_eacb5997/events.jsonl)

## 10. 附录

### 10.1 命令对比表

| 命令类别 | v1 数量 | v2 数量 | 差异 |
|---------|---------|---------|------|
| stock.* | 12 | 12 | 完全覆盖 |
| market.* | 11 | 11 | 完全覆盖 |
| analysis.* | 10 | 10 | 完全覆盖 |
| financial.* | 8 | 8 | 完全覆盖 |
| signal.* | 5 | 9 | +4 测试命令 |
| strategy.* | 4 | 6 | +2 运行命令 |
| backtest.* | 2 | 2 | 完全覆盖 |
| 其他 | 75 | 75 | 完全覆盖 |
| **总计** | **127** | **133** | **+6 新命令** |

### 10.2 v2 新增命令详情

| 命令 | 端点 | 方法 | 说明 |
|------|------|------|------|
| `signal.test_run` | `/api/signal-test/run-strategy` | POST | 运行策略信号测试 |
| `signal.test_record` | `/api/signal-test/record` | POST | 记录测试结果 |
| `signal.test_verify` | `/api/signal-test/verify` | POST | 验证信号准确性 |
| `signal.test_stats` | `/api/signal-test/stats` | GET | 获取测试统计 |
| `strategy.run` | `/api/strategy/run` | POST | 实时运行策略 |
| `strategy.status` | `/api/strategy/status` | GET | 查询策略状态 |
