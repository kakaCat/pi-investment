# backtest_cli 工具清理报告

**日期**: 2026-06-02  
**类型**: 工具重构 - 移除重复工具

## 背景

`backtest_cli` 工具与 `indicator_backtest` 工具存在功能重叠：
- `backtest_cli` 包含 3 个命令：`backtest.run`, `backtest.results`, `backtest.strategy`
- `indicator_backtest` 专门用于指标回测，调用 `/api/indicators/backtest` API
- 两者底层都调用 `strategy_service.backtest_strategy()` 方法

## 决策

**保留**: `indicator_backtest` 工具
- 专用工具，语义清晰
- 专门针对指标回测（code_type='indicator'）
- 符合项目工具模块化趋势

**移除**: `backtest_cli` 工具
- 功能与 `indicator_backtest` 重叠
- 其他命令可通过其他方式替代

## 执行的修改

### 1. 删除工具文件
- ✅ 删除 `src/infrastructure/tools/cli/backtest-cli-tool.ts`

### 2. 更新工具注册
- ✅ 从 `src/infrastructure/tools/cli/index.ts` 移除导出
- ✅ 从 `src/infrastructure/tools/index.ts` 移除导入
- ✅ 从 `allCustomTools` 数组移除注册

### 3. 更新文档
- ✅ 从 CLAUDE.md 移除所有 `backtest_cli` 相关说明
- ✅ 更新使用示例，改用 `indicator_backtest`

## 替代方案

原 `backtest_cli` 命令的替代方式：

| 原命令 | 替代方式 |
|--------|----------|
| `backtest.run` | 使用 `strategy_execute` 或直接调用 API |
| `backtest.strategy` | 使用 `indicator_backtest`（指标回测）|
| `backtest.results` | 直接调用 API 或整合到其他工具 |

## 影响评估

- **破坏性变更**: 是（移除了公开工具）
- **影响范围**: 仅限直接调用 `backtest_cli` 的代码
- **迁移成本**: 低（替代工具已存在）

## 后续建议

1. 如果需要策略回测（非指标），可以考虑创建独立的 `strategy_backtest` 工具
2. 考虑将 `backtest.results` 功能独立为查询工具

## 验证

- ✅ 源代码中无残留引用
- ✅ CLAUDE.md 文档已更新
- ✅ 工具注册已清理
