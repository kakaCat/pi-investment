# Codex 配置指南

## 问题现象

运行 `/evolution` 时出现错误：

```json
{
  "status": "error",
  "message": "执行失败: Codex 代码生成失败: ENOENT: no such file or directory, open '/tmp/codex-gen-xxx.txt'"
}
```

实际错误原因：
```
ERROR: unexpected status 402 Payment Required: 客户端: cc 渠道: openai_default 余额不足
```

---

## 解决方案

### 方案 1：禁用自动代码生成（临时方案）

已在代码中添加配置开关，默认**已禁用**自动代码生成。

**配置文件**：[src/config/config.ts](../src/config/config.ts)

```typescript
export const evolutionConfig = {
  // 是否启用自动代码生成（需要 Codex 账户余额充足）
  enableCodeGeneration: false,  // 默认关闭
  // Codex 超时时间（毫秒）
  codexTimeout: 120000,
};
```

**效果**：
- 进化分析正常运行
- 补偿器生成优化建议
- 跳过自动代码生成步骤
- 建议保存为手动任务，需要人工实现

**输出示例**：
```
🚀 开始执行工具添加: check_stop_loss_trigger
⚠️  自动代码生成已禁用（Codex 余额不足或配置关闭）
💡 建议：手动实现工具或充值 Codex 账户后启用

状态: skipped
需要手动实现:
  - 工具名称: check_stop_loss_trigger
  - 描述: 检查持仓是否触发止损条件
  - 原因: 缺少止损检查能力，需要自动化风控工具
  - 预期效果: 减少亏损扩大，改善最大回撤
```

---

### 方案 2：充值 Codex 账户（推荐）

#### 步骤 1：检查 Codex 配置

```bash
# 查看 Codex 配置文件
cat ~/.codex/config.json

# 检查当前使用的 API 提供商
codex config list
```

#### 步骤 2：充值账户

根据你的 Codex 配置，联系对应的服务提供商充值：

- 如果使用 OpenAI 官方：登录 [platform.openai.com](https://platform.openai.com) 充值
- 如果使用第三方代理：联系代理商充值（错误信息显示使用 `node-hk.sssaicode.com`）

#### 步骤 3：启用自动代码生成

修改 [src/config/config.ts](../src/config/config.ts)：

```typescript
export const evolutionConfig = {
  enableCodeGeneration: true,  // 改为 true
  codexTimeout: 120000,
};
```

#### 步骤 4：测试 Codex

```bash
# 测试 Codex 是否正常工作
codex exec --ephemeral "console.log('test')"

# 如果成功，应该看到输出而不是 402 错误
```

---

## 手动实现工具（方案 1 的后续步骤）

当自动代码生成禁用时，你需要手动实现建议的工具。

### 示例：实现 check_stop_loss_trigger 工具

#### 1. 创建工具文件

**文件路径**：`src/infrastructure/tools/check-stop-loss-trigger-tool.ts`

```typescript
/**
 * 检查止损触发工具
 * 
 * 检查持仓是否触发止损条件
 */
import type { ToolDefinition } from "./index.js";
import { Type } from "@sinclair/typebox";

export const checkStopLossTriggerTool: ToolDefinition = {
  name: "check_stop_loss_trigger",
  label: "检查止损触发",
  description: "检查持仓是否触发止损条件（价格跌破止损价、亏损超过阈值等）",
  
  parameters: Type.Object({
    symbol: Type.Optional(Type.String({ description: "股票代码（可选，不传则检查所有持仓）" })),
    stopLossPercent: Type.Optional(Type.Number({ 
      description: "止损百分比阈值（默认 -8%）",
      default: -8 
    }))
  }),
  
  async execute(callId, args) {
    try {
      const { symbol, stopLossPercent = -8 } = args;
      
      // TODO: 实现止损检查逻辑
      // 1. 读取持仓数据
      // 2. 获取当前价格
      // 3. 计算盈亏百分比
      // 4. 判断是否触发止损
      
      return {
        content: [{
          type: "text",
          text: `止损检查功能待实现`
        }],
        details: {
          symbol,
          stopLossPercent
        }
      };
    } catch (error: any) {
      return {
        content: [{
          type: "text",
          text: `❌ 止损检查失败: ${error.message}`
        }]
      };
    }
  }
};
```

#### 2. 注册工具

修改 `src/infrastructure/tools/index.ts`，添加：

```typescript
import { checkStopLossTriggerTool } from "./check-stop-loss-trigger-tool.js";

export const allTools: ToolDefinition[] = [
  // ... 其他工具
  checkStopLossTriggerTool,
];
```

#### 3. 编写测试

**文件路径**：`src/infrastructure/tools/check-stop-loss-trigger-tool.test.ts`

```typescript
import { checkStopLossTriggerTool } from "./check-stop-loss-trigger-tool.js";

describe("checkStopLossTriggerTool", () => {
  it("应该正确检查止损触发", async () => {
    const result = await checkStopLossTriggerTool.execute("test-1", {
      symbol: "600519",
      stopLossPercent: -8
    });
    
    expect(result.content).toBeDefined();
    expect(result.content[0].type).toBe("text");
  });
});
```

#### 4. 运行测试

```bash
npm test -- check-stop-loss-trigger
```

---

## 常见问题

### Q1: 为什么不直接使用 OpenAI API？

A: Codex 是一个封装了 GPT-5.4 的 CLI 工具，提供了沙箱、审批流程等额外功能。直接使用 OpenAI API 需要重写代码生成逻辑。

### Q2: 禁用代码生成后，进化系统还有用吗？

A: 有用！补偿器仍然会：
- 分析性能差距
- 识别弱点
- 生成优化建议
- 评估历史效果
- 提供改进方向

只是需要你手动实现建议的工具，而不是自动生成代码。

### Q3: 如何查看进化建议？

A: 运行 `/evolution` 后，查看报告文件：

```bash
# 查看最新报告
cat .pi-invest/evolution/evolution-*.md | tail -100

# 或使用命令
/evolution --view
```

---

## 相关文档

- [Evolution 使用指南](./evolution-usage-guide.md)
- [Evolution 测试指南](./testing-guide.md)
- [架构重构报告](./architecture-refactoring-report.md)
