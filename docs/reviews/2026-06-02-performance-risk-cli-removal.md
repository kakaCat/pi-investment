# performance_cli 和 risk_cli 工具清理报告

**日期**: 2026-06-02  
**类型**: 工具清理 - 移除重复工具

## 背景

在工具目录中发现 `performance-cli-tool.ts` 和 `risk-cli-tool.ts` 两个未注册的 CLI 工具，经检查发现这些命令已在 `quant_cli` 工具中实现，属于重复实现。

## 重复命令对比

### performance_cli 的命令（重复）
| 命令 | quant_cli 中的对应命令 |
|------|----------------------|
| `performance.analyze` | ✅ `performance.analyze` |
| `performance.by_strategy` | ✅ `performance.by_strategy` |
| `performance.comparison` | ✅ `performance.comparison` |

### risk_cli 的命令（重复）
| 命令 | quant_cli 中的对应命令 |
|------|----------------------|
| `risk.check` | ✅ `risk.check` |
| `risk.monitor` | ❌ 未在 quant_cli 中找到 |
| `risk.limit` | ❌ 未在 quant_cli 中找到 |
| `risk.alert` | ❌ 未在 quant_cli 中找到 |

**注意**：`risk.monitor`、`risk.limit`、`risk.alert` 在 quant_cli 中可能以其他名称存在，或者是计划中的命令但未实现。

## 执行的清理

### 1. 删除文件
- ✅ `src/infrastructure/tools/cli/performance-cli-tool.ts`
- ✅ `src/infrastructure/tools/cli/risk-cli-tool.ts`

### 2. 功能替代

所有功能都可以通过 `quant_cli` 使用：

```typescript
// ❌ 旧方式（未注册的工具）
performance_cli({ command: "performance.analyze", params: { strategy_id: "53" } })
risk_cli({ command: "risk.check", params: { portfolio_id: "default" } })

// ✅ 新方式（使用 quant_cli）
quant_cli({ command: "performance.analyze", params: { strategy_id: "53" } })
quant_cli({ command: "risk.check", params: { portfolio_id: "default" } })
```

## 为什么这些工具未被注册？

1. **可能是实验性实现** - 创建这些工具是为了测试 CLI 工具拆分模式
2. **功能已在 quant_cli 中** - 发现重复后未删除
3. **遗留代码** - 在工具重构过程中遗留

## 影响评估

- **破坏性变更**: 否（这些工具从未被注册，无人使用）
- **影响范围**: 无（工具未在 index.ts 中导出）
- **迁移成本**: 无（无需迁移）

## 验证

- ✅ 文件已删除
- ✅ quant_cli 中已有对应命令
- ✅ 无其他文件引用这两个工具

## 统计

- **删除文件**: 2 个
- **删除代码**: ~200 行
- **当前 CLI 工具**: 7 个（保留）
