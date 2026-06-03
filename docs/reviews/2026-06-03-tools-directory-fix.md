# src/infrastructure/tools 问题修复报告

**日期**: 2026-06-03  
**状态**: ✅ 已完成

---

## 🔍 发现的问题

### 1. 已弃用工具未清理
- **问题**: `smart-stock-screener-tool` 已于 2026-06-02 弃用，但仍在 `index.ts` 中导入和注册
- **根本原因**: 功能已整合到 `opportunity_scan` 的动态权重模式中
- **影响**: 工具冗余，用户混淆

### 2. TypeScript 编译错误（12个）
#### CLI 工具类型不匹配（6个）
- `analysis-cli-tool.ts`
- `financial-cli-tool.ts`
- `market-cli-tool.ts`
- `sentiment-cli-tool.ts`
- `stock-cli-tool.ts`
- `watchlist-cli-tool.ts`

**错误类型**: `execute` 函数签名不完整，缺少 `signal` 参数

#### 缺失模块引用（6个）
- `src/services/quant/backtest-engine.ts` - 引用 `factor-library.js`, `stock-db-service.js`
- `src/services/quant/signal-generator.ts` - 引用 `factor-library.js`, `python-caller-resilient-adapter.js`

**根本原因**: 这些模块已迁移到 quantsys-v2，但旧服务文件未从编译中排除

#### ToolResult 类型定义问题
- `details` 字段定义为可选，但 SDK 要求必需

---

## 🔧 实施的修复

### 1. 移除已弃用工具
```typescript
// src/infrastructure/tools/index.ts
- import { smartStockScreenerTool } from "./invest/smart-stock-screener-tool.js";
- smartStockScreenerTool,  // smart_stock_screener - 动态因子权重智能选股

// 删除文件
rm src/infrastructure/tools/invest/smart-stock-screener-tool.ts
```

### 2. 修复 CLI 工具类型签名
```bash
# 批量修复所有 CLI 工具
sed -i 's/execute: async (_toolCallId, input: any) => {/execute: async (_toolCallId: string, input: any, _signal?: AbortSignal) => {/' src/infrastructure/tools/cli/*.ts
```

**修复的文件**:
- analysis-cli-tool.ts
- financial-cli-tool.ts
- market-cli-tool.ts
- sentiment-cli-tool.ts
- stock-cli-tool.ts
- watchlist-cli-tool.ts

### 3. 修复 ToolResult 类型定义
```typescript
// src/infrastructure/tools/shared/error-handler.ts
export interface ToolResult {
  content: Array<{ type: "text"; text: string }>;
- details?: any;
+ details: any;  // Required field for SDK compatibility
}
```

### 4. 修复 tool-stats-tool 参数类型
```typescript
// src/infrastructure/tools/agent/tool-stats-tool.ts
- execute: async (_toolCallId, params) => {
-   const { action, tool_name, from_date, top_n = 20, output_path, retention_days = 30 } = params;
+ execute: async (_toolCallId, params: any) => {
+   const { action, tool_name, from_date, top_n = 20, output_path, retention_days = 30 } = params as {
+     action: 'stats' | 'report' | 'export' | 'cleanup';
+     tool_name?: string;
+     from_date?: string;
+     top_n?: number;
+     output_path?: string;
+     retention_days?: number;
+   };
```

### 5. 修复 opportunity-scan-tool 未定义变量
```typescript
// src/infrastructure/tools/invest/opportunity-scan-tool.ts
} else if (rawParams?.weights) {
  outputText += "📊 **自定义权重模式**\n\n";
  finalWeights = rawParams.weights;
+ if (finalWeights) {
    outputText += `  • 技术面权重: ${(finalWeights.technical * 100).toFixed(1)}%\n`;
    outputText += `  • 基本面权重: ${(finalWeights.fundamental * 100).toFixed(1)}%\n`;
    outputText += `  • 资金面权重: ${(finalWeights.capital * 100).toFixed(1)}%\n\n`;
+ }
}
```

### 6. 排除已废弃的服务文件
```json
// tsconfig.build.json
{
  "exclude": [
    "src/index-with-logger.ts",
    "src/api/web/server.ts",
    "src/scripts/portfolio-cli.ts",
    "src/services/operations/job-audit-service.ts",
+   "src/services/quant/backtest-engine.ts",
+   "src/services/quant/signal-generator.ts",
+   "src/services/quant/signal-arbiter-example.ts",
    "**/*.test.ts",
    "**/*.spec.ts"
  ]
}
```

---

## ✅ 验证结果

### 编译状态
```bash
npm run build
# ✅ 编译成功！0 错误
```

### 修复前后对比
| 指标 | 修复前 | 修复后 | 改进 |
|------|--------|--------|------|
| TypeScript 错误 | 12 | 0 | -100% |
| 已弃用工具 | 1 | 0 | -100% |
| 工具总数 | 69 | 68 | -1 |

### 工具目录结构（修复后）
```
src/infrastructure/tools/
├── agent/          16个 - Agent元工具
├── backtest/        1个 - 组合回测
├── cli/             7个 - 领域CLI工具 ✅ 类型已修复
├── core/            1个 - quant_cli核心
├── data/            4个 - 数据管道
├── execution/       1个 - 信号执行
├── factor/          2个 - 因子工厂
├── indicator/       6个 - 指标工具
├── invest/          2个 - 投资工具 ✅ 已移除smart-stock-screener
├── model/           5个 - 模型层
├── monitor/         3个 - 监控运维
├── pool/            2个 - 股票池管理
├── shared/          7个 - 共享工具 ✅ ToolResult已修复
├── strategy/        8个 - 策略工具
└── trade/           2个 - 交易工具
```

---

## 📝 关键决策

### 为什么排除而不是删除 services/quant 文件？
1. **保留历史**: 这些文件包含重要的业务逻辑和算法
2. **测试文件**: 相关的 `.test.ts` 文件仍依赖这些实现
3. **迁移参考**: 可作为 quantsys-v2 迁移的参考文档
4. **最小改动**: 仅排除编译，不破坏现有代码库

### 为什么修改 ToolResult 类型而不是修改 wrapToolExecution？
1. **SDK 兼容性**: pi-agent SDK 要求 `AgentToolResult.details` 必需
2. **一致性**: 所有工具应返回统一的类型
3. **最小改动**: 只需修改一处类型定义

---

## 🎯 后续建议

### 短期（1周内）
- [ ] 运行完整测试套件验证修复
- [ ] 更新工具文档，标注 smart-stock-screener 已弃用
- [ ] 检查是否有其他引用已删除模块的代码

### 中期（1月内）
- [ ] 完全移除 `src/services/quant/` 目录
- [ ] 迁移相关测试到 quantsys-v2
- [ ] 更新 CLAUDE.md 工具列表

### 长期（季度）
- [ ] 建立 TypeScript 类型检查 CI 流程
- [ ] 添加工具弃用机制（deprecation warning）
- [ ] 定期审计未使用的代码

---

## 📚 相关文档

- [工具合并报告](docs/reviews/2026-06-02-tool-merge-opportunity-scan.md)
- [quant_cli拆分报告](docs/reviews/2026-06-02-quant-cli-split-success.md)
- [工具开发指南](docs/tools/tool-development-guide.md)
- [CLAUDE.md - Agent工具系统](CLAUDE.md#agent-工具系统)

---

**修复完成时间**: 2026-06-03 13:10  
**编译状态**: ✅ 成功  
**工具数量**: 68个（已移除1个已弃用工具）
