# signal_cli 工具清理报告

**日期**: 2026-06-02  
**类型**: 工具清理 - 移除已删除工具的文档引用

## 背景

`signal_cli` 工具已在之前被删除（后端未实现 `signal.arbitrate`，其他功能已被更好的 API 替代），但文档中仍有残留引用。

## 执行的清理

### 1. 文档更新
- ✅ `docs/tools/quick-start-guide.md` - 移除 signal_cli 示例代码和引用
- ✅ `docs/tools/tool-selection-guide.md` - 移除 CLI 决策树中的 signal_cli

### 2. 功能替代

| 原功能 | 替代方案 |
|--------|----------|
| `signal_cli({ command: "signal.list" })` | 使用 `quant_cli({ command: "signal.list" })` |
| `signal_cli({ command: "signal.statistics" })` | 使用 `quant_cli({ command: "signal.statistics" })` |
| `signal.generate` | **已废弃** - 使用 `strategy_execute` |
| `signal.arbitrate` | **未实现** - 后端无此功能 |

### 3. 已标记的删除记录

在 `CLAUDE.md` 中已正确标记：
```
**已移除**（2026-06-02）：
- ❌ `signal_cli` 工具（后端未实现 signal.arbitrate，其他功能已被更好的 API 替代）
```

## 验证

- ✅ 工具文档中无残留引用
- ✅ CLAUDE.md 已正确标记为"已移除"
- ✅ 代码中无 signal_cli 工具实现

## 注意事项

1. **signal.list** 和 **signal.statistics** 命令仍可通过 `quant_cli` 使用
2. **signal.generate** 已标记为废弃，推荐使用 `strategy_execute`
3. **signal.arbitrate** 后端未实现，无替代方案

## 相关清理

本次清理是继 `backtest_cli` 清理之后的第二轮工具清理工作，持续优化工具系统的一致性。
