# 量化工具 AI 对接说明

## 📋 目录
1. [架构概览](#架构概览)
2. [对接方式](#对接方式)
3. [工具分类](#工具分类)
4. [使用示例](#使用示例)
5. [扩展指南](#扩展指南)

---

## 🏗️ 架构概览

### 整体架构

```
┌─────────────────────────────────────────────────────────────┐
│                      AI Agent (Claude)                       │
│  - 飞书机器人                                                 │
│  - Web API                                                   │
│  - 命令行交互                                                 │
└────────────────────┬────────────────────────────────────────┘
                     │
                     │ 调用工具 (Tool Calls)
                     │
┌────────────────────▼────────────────────────────────────────┐
│              TypeScript 工具层 (Tools)                       │
│  - quant-decision-tools.ts (决策分析)                        │
│  - quant-analysis-tools.ts (技术分析)                        │
│  - quant-strategy-tools.ts (策略管理)                        │
│  - quant-tools.ts (旧版，向后兼容)                           │
└────────────────────┬────────────────────────────────────────┘
                     │
        ┌────────────┴────────────┐
        │                         │
        ▼                         ▼
┌───────────────┐         ┌──────────────────┐
│ TypeScript    │         │ Python Bridge    │
│ 量化服务      │         │ (akshare_bridge) │
│               │         │                  │
│ - QuantService│         │ - 数据获取       │
│ - FactorLib   │         │ - ML训练         │
│ - SignalGen   │         │ - 因子计算       │
│ - Backtest    │         │                  │
└───────┬───────┘         └────────┬─────────┘
        │                          │
        │                          │
        ▼                          ▼
┌─────────────────────────────────────────┐
│         Python 量化脚本                  │
│  quant/scripts/                         │
│  - calculate_factors.py (因子计算)      │
│  - generate_signals.py (信号生成)       │
│  - daily_report.py (每日报告)           │
│  - ml_predict.py (ML预测)               │
│  - scheduler.py (定时任务)              │
└─────────────────┬───────────────────────┘
                  │
                  ▼
         ┌────────────────┐
         │  SQLite 数据库  │
         │  stocks.db      │
         │  - daily_klines │
         │  - factor_values│
         └────────────────┘
```

---

## 🔌 对接方式

### 方式 1: TypeScript 工具直接调用

AI Agent 通过 TypeScript 工具直接访问量化功能，适用于**实时分析**。

**流程：**
```
AI Agent → TypeScript Tool → QuantService → 数据库/计算
```

**示例工具：**
- `analyze_stock_quant` - 股票量化综合分析
- `compare_stocks_quant` - 批量对比股票
- `validate_trade_decision` - 验证交易决策

**代码位置：**
- `src/infrastructure/tools/quant-decision-tools.ts`
- `src/infrastructure/tools/quant-analysis-tools.ts`
- `src/infrastructure/tools/quant-strategy-tools.ts`

---

### 方式 2: Python Bridge 调用

AI Agent 通过 Python Bridge 调用 Python 脚本，适用于**批量计算**和**ML训练**。

**流程：**
```
AI Agent → TypeScript Tool → Python Bridge → Python Script → 数据库
```

**示例工具：**
- `train_signal_model` - 训练信号模型（调用 Python ML 脚本）

**代码位置：**
- `python/akshare_bridge.py` - Python 桥接器
- `quant/scripts/*.py` - Python 量化脚本

---

### 方式 3: 定时任务自动执行

Python 调度器定时运行量化脚本，AI Agent 读取结果文件。

**流程：**
```
Scheduler → Python Scripts → 数据库/JSON文件
                                    ↓
AI Agent → Read Files ← signals.json, daily_report.json
```

**定时任务：**
- 每日 16:00 - 数据更新
- 每日 16:30 - 因子计算
- 每日 17:00 - 信号生成
- 每日 18:00 - 每日报告

**代码位置：**
- `quant/scripts/scheduler.py` - 调度器
- `.pi-invest/signals.json` - 信号输出
- `.pi-invest/daily_report.json` - 报告输出

---

## 🛠️ 工具分类

### 1. 决策分析工具 (Decision Tools)

**文件：** `src/infrastructure/tools/quant-decision-tools.ts`

| 工具名称 | 功能 | 使用场景 |
|---------|------|---------|
| `analyze_stock_quant` | 股票量化综合分析 | 分析持仓、评估买入机会 |
| `compare_stocks_quant` | 批量对比股票 | 选股、构建投资组合 |
| `validate_trade_decision` | 验证交易决策 | 买入/卖出前的最后确认 |

**特点：**
- 一次调用获取完整分析
- 包含技术指标、量化信号、历史经验
- 提供综合评分和操作建议

---

### 2. 技术分析工具 (Analysis Tools)

**文件：** `src/infrastructure/tools/quant-analysis-tools.ts`

| 工具名称 | 功能 | 使用场景 |
|---------|------|---------|
| `get_technical_signals` | 获取技术信号 | 查看RSI、MACD、均线等指标 |
| `get_quant_score` | 获取量化评分 | 多因子评分 |
| `query_similar_cases` | 查询相似案例 | 历史经验查询 |
| `backtest_strategy` | 回测策略 | 验证策略有效性 |

**特点：**
- 细粒度的技术分析
- 支持单一指标查询
- 适合深入研究

---

### 3. 策略管理工具 (Strategy Tools)

**文件：** `src/infrastructure/tools/quant-strategy-tools.ts`

| 工具名称 | 功能 | 使用场景 |
|---------|------|---------|
| `list_quant_strategies` | 列出所有策略 | 查看可用策略 |
| `get_strategy_performance` | 获取策略表现 | 评估策略效果 |

**特点：**
- 管理量化策略
- 查看策略历史表现
- 支持策略启用/禁用

---

### 4. 旧版工具 (Legacy Tools)

**文件：** `src/infrastructure/tools/quant-tools.ts`

包含 6 个工具：
1. `manage_quant_strategy` - 管理量化策略
2. `run_backtest` - 运行回测
3. `generate_signals` - 生成交易信号
4. `score_stock` - 股票因子评分
5. `train_signal_model` - 训练信号模型
6. `get_strategy_performance` - 策略表现统计

**状态：** 已弃用，保持向后兼容

---

## 💡 使用示例

### 示例 1: AI 分析单只股票

**用户问：** "帮我分析一下 600036 招商银行"

**AI 调用：**
```typescript
analyze_stock_quant({
  symbol: "600036",
  context: "buy"
})
```

**返回结果：**
```
招商银行(600036) 量化综合分析
=====================================
综合评分: 75/100 (偏多)
建议操作: 强烈建议买入
置信度: 85%

技术面信号:
✓ RSI超卖 - RSI超卖 (10.37 < 30)
✓ MACD金叉 - 趋势转多
✓ 均线多头排列 - 短中期趋势向上

量化策略触发 (2个):
- RSI反转策略: 买入信号 (置信度100%)
- 均线突破策略: 买入信号 (置信度85%)

建议:
可以买入，建议分批建仓
- 首批仓位控制在10%以内
- 止损位: ¥35.60 (-5%)
```

---

### 示例 2: AI 批量对比股票

**用户问：** "对比一下我的持仓股票，哪些值得加仓？"

**AI 调用：**
```typescript
compare_stocks_quant({
  symbols: ["600036", "002025", "601899", "601288"],
  sort_by: "score"
})
```

**返回结果：**
```
量化评分排名 (共4只)
=====================================
1. 600036 - 评分75 - 2个买入信号 - 强烈建议买入
2. 601288 - 评分55 - 0个买入信号 - 观察等待
3. 002025 - 评分45 - 0个买入信号 - 暂不建议买入
4. 601899 - 评分35 - 0个买入信号 - 暂不建议买入
```

---

### 示例 3: AI 验证交易决策

**用户问：** "我想在 37.5 元买入 600036，帮我看看合不合理？"

**AI 调用：**
```typescript
validate_trade_decision({
  symbol: "600036",
  action: "buy",
  price: 37.5,
  quantity: 1000,
  reason: "RSI超卖反弹"
})
```

**返回结果：**
```
交易决策验证 - 买入600036
=====================================
决策评估: ✓ 合理
交易理由: RSI超卖反弹

支持因素:
✓ 综合评分75分，技术面偏多
✓ 2个量化策略触发买入信号
✓ 技术面: RSI超卖、MACD金叉

风险因素:
- 暂无明显风险

建议:
可以买入，建议分批建仓
- 首批仓位控制在10%以内
- 止损位: ¥35.62 (-5%)

当前价格: ¥37.47
计划价格: ¥37.50 (1000股)
```

---

### 示例 4: 定时任务自动生成信号

**定时任务：** 每天 17:00 自动运行

**执行命令：**
```bash
cd quant
python3 scripts/generate_signals.py
```

**输出文件：** `.pi-invest/signals.json`

**AI 读取：**
```typescript
// AI 自动读取信号文件
const signals = JSON.parse(fs.readFileSync('.pi-invest/signals.json'));

// 筛选买入信号
const buySignals = signals.signals.filter(s => s.signal === 'BUY');

// 推送通知
send_notification({
  title: "今日买入信号",
  message: `发现 ${buySignals.length} 个买入机会`,
  signals: buySignals
});
```

---

## 🔧 扩展指南

### 添加新的 TypeScript 工具

**步骤：**

1. **创建工具文件**
```typescript
// src/infrastructure/tools/my-quant-tool.ts
import { Type } from '@sinclair/typebox';
import type { ToolDefinition } from "./index.js";

export const myQuantTool: ToolDefinition = {
  name: 'my_quant_tool',
  label: '我的量化工具',
  description: '工具描述',
  
  parameters: Type.Object({
    symbol: Type.String({ description: '股票代码' })
  }),
  
  execute: async (_toolCallId: string, params: any) => {
    // 实现逻辑
    return {
      content: [{ type: "text", text: "结果" }],
      details: {}
    };
  }
};
```

2. **注册工具**
```typescript
// src/infrastructure/tools/index.ts
import { myQuantTool } from './my-quant-tool.js';

export const allCustomTools = [
  // ... 其他工具
  myQuantTool,  // 添加到这里
];
```

3. **AI 自动可用**
AI Agent 会自动识别新工具并在需要时调用。

---

### 添加新的 Python 脚本

**步骤：**

1. **创建 Python 脚本**
```python
# quant/scripts/my_analysis.py
import sys
import json
from quantsys.data.db import QuantDB

def main():
    db = QuantDB()
    # 实现分析逻辑
    result = {"status": "success", "data": []}
    print(json.dumps(result))

if __name__ == "__main__":
    main()
```

2. **添加到调度器（可选）**
```python
# quant/scripts/scheduler.py
scheduler.add_job(
    run_my_analysis,
    'cron',
    hour=18, minute=30,
    id='my_analysis',
    name='我的分析任务'
)
```

3. **创建 TypeScript 工具调用**
```typescript
export const myAnalysisTool: ToolDefinition = {
  name: 'run_my_analysis',
  execute: async (_toolCallId: string, params: any) => {
    const result = await callPythonResilient(
      'my_analysis',
      params
    );
    return {
      content: [{ type: "text", text: result }],
      details: JSON.parse(result)
    };
  }
};
```

---

## 📊 数据流向

### 实时分析流程
```
用户提问 → AI Agent → TypeScript Tool → QuantService
                                            ↓
                                    计算技术指标
                                            ↓
                                    生成信号/评分
                                            ↓
                                    返回结果 → AI → 用户
```

### 批量计算流程
```
定时触发 → Scheduler → Python Script → 数据库
                                         ↓
                                    写入 JSON
                                         ↓
AI Agent → Read JSON → 分析结果 → 推送通知 → 用户
```

---

## 🎯 最佳实践

### 1. 工具选择原则

- **实时分析** → 使用 TypeScript 工具（`analyze_stock_quant`）
- **批量计算** → 使用 Python 脚本 + 定时任务
- **历史回测** → 使用 `backtest_strategy` 工具
- **策略管理** → 使用 `manage_quant_strategy` 工具

### 2. 性能优化

- **缓存技术指标**：避免重复计算
- **批量查询数据库**：减少 I/O 次数
- **异步并行执行**：多只股票同时分析
- **定时预计算**：提前生成信号和报告

### 3. 错误处理

- **工具层捕获异常**：返回友好错误信息
- **Python 脚本超时控制**：避免长时间阻塞
- **数据验证**：检查输入参数合法性
- **降级策略**：主数据源失败时使用备用源

---

## 📝 总结

### 核心优势

1. **多层架构**：TypeScript + Python 双层设计，灵活高效
2. **工具丰富**：15+ 量化工具，覆盖分析、决策、回测全流程
3. **AI 原生**：工具专为 AI Agent 设计，自然语言交互
4. **自动化**：定时任务自动运行，AI 自动读取结果
5. **可扩展**：新增工具只需 3 步，无需修改核心代码

### 使用建议

- **新手**：使用 `analyze_stock_quant` 一键分析
- **进阶**：组合多个工具进行深度分析
- **专家**：自定义策略 + 回测验证

### 相关文档

- [量化系统完整使用指南](../quant/docs/完整使用指南.md)
- [定时任务系统说明](../quant/scripts/SCHEDULER_README.md)
- [工具开发指南](./工具开发指南.md)

---

**最后更新：** 2026-05-18  
**维护者：** AI Investment Team
