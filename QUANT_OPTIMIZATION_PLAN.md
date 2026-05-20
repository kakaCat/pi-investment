# 量化工具系统优化方案

## 一、现状诊断

### T1 — 文档声明但实际不存在/未注册（4个工具）

TOOLS.md 写了 `predict_stock_signal` / `backtest_strategy` / `evaluate_model` / `train_model`，但：

| 工具名 | TOOLS.md 声明 | 注册到 index.ts | src 中有实现 | 实际可用 |
|:---|---|:---:|:---:|:---:|
| `predict_stock_signal` | ✅ 在 Path C 第4轮必调 | ❌ | ❌ | **不可用** |
| `backtest_strategy` | ✅ Path I + 工具速查 | ❌ | ❌ | **不可用** |
| `evaluate_model` | ✅ Path I + 工具速查 | ❌ | ❌ | **不可用** |
| `train_model` | ✅ 工具速查 | ❌ | ❌ | **不可用** |

**影响**：Path C（A股深度分析）第4轮声明「必须调用 predict_stock_signal」，但实际上我调用就会报错。这直接导致我在做深度分析时**跳过了量化信号环节**——不是不想用，是工具不存在。

### T2 — 存在但未被调用（2个量化模块）

| 模块 | 在 dist/ 中的实现状态 | 注册状态 | 调用情况 |
|:---|---|:---:|:---:|
| `manage_quant_strategy` | ✅ 完整实现（quant-tools.js） | ❌ 未注册到 index.ts | 从未被调用 |
| `run_backtest` | ✅ 完整实现（backtest-engine + quant-tools） | ❌ 未注册到 index.ts | 从未被调用 |
| `generate_signals` | ✅ 完整实现（signal-generator + quant-tools） | ❌ 未注册到 index.ts | 从未被调用 |
| `score_stock` | ✅ 完整实现（factor-library + quant-tools） | ❌ 未注册到 index.ts | 从未被调用 |
| `train_signal_model` | ✅ 完整实现（quant-tools） | ❌ 未注册到 index.ts | 从未被调用 |
| `query_experience` | ✅ 完整实现 + 注册 | ✅ 已注册 | ❌ **从未调用** |

**dist/services/quant/quant-tools.js 导出了 5 个工具，全都没有被 index.ts 导入**。

根因：`quant-tools.js` 是一个独立的 dist 编译产物，而 index.ts 只从 `src/infrastructure/tools/` 下的 .ts 文件导入。量化工具从来没有被作为一个模块集成到工具注册链中。

### T3 — 半成品代码

| 文件 | 状态 |
|:---|---|
| `src/services/quant/types.ts` | ✅ 类型定义完整 |
| `dist/services/quant/quant-service.ts` 的源文件 | ❌ src 中不存在（只在 dist 中） |
| `dist/services/quant/backtest-engine.js` | ✅ 有完整实现，但 src 不存 |
| `dist/services/quant/factor-library.js` | ✅ 同上 |
| `dist/services/quant/signal-generator.js` | ✅ 同上，但 src 不存 |
| `dist/services/quant/kelly-criterion.js` | ✅ src 中存在 |
| `dist/services/quant/quant-tools.js` | ✅ 工具定义完整，但 src 不存 |
| ml-pipeline Python 脚本 | ❌ `ml-pipeline/ml_pipeline.py` 不存在（仅 test 中引用过） |

**结论**：量化模块在开发阶段被编译过一次（dist 中有完整产物），但 src 源文件大部分被清理或丢失了，且从未集成到工具注册系统。

### T4 — 决策链缺失（SOUL.md / TOOLS.md）

**SOUL.md 第6章「A股分析检查清单」**：
- Phase 1-4 全部是基本面/估值/技术面工具
- **Phase 5「信号确认」标注为「可选」**
- 没有任何 `query_experience` 或 `predict_stock_signal` 的强制调用
- **问题**：量化信号被定位为「可选补充」，而非「必须执行」

**TOOLS.md Path C 第4轮**：
- 写了 `predict_stock_signal`，但该工具不存在
- 写了「必须包含量化信号」，但工具不可用导致这条规则自动失效
- **问题**：规则和实现脱节

---

## 二、根因分析

```
TOOLS.md 声明
    ↓
predict_stock_signal / backtest_strategy 不存在
    ↓
Agent 无法调用 → 跳过量化环节 → 养成"不用量化也能分析"的习惯
    ↓
问用户"为什么不用量化"

循环往复
```

**三个致命断点**：

1. **注册断点** — quant-tools.js 的 5 个工具（manage_quant_strategy / run_backtest / generate_signals / score_stock / train_signal_model）从未被 index.ts 导入
2. **文档断点** — TOOLS.md 写的工具名与实际注册的工具名完全不同（`predict_stock_signal` vs `run_backtest`），导致我按文档找工具时找不到
3. **行为断点** — SOUL.md 把量化信号放在「可选」位置，没有强制触发路径，即使工具可用，我也没有被约束调用它

---

## 三、改造方案

### 3.1 注册量化工具（最核心一步）

将 `dist/services/quant/quant-tools.js` 的 5 个工具注入到 `src/infrastructure/tools/index.ts`。

**具体操作**：

1. 在 `src/infrastructure/tools/index.ts` 中导入：

```typescript
// 量化工具（dist 编译产物 — 临时方案）
import { quantTools } from '../../../dist/services/quant/quant-tools.js';
// 或 src 版（需要先恢复源文件）
```

2. 加入 `allCustomTools`：

```typescript
export const allCustomTools = [
  // ... 现有工具 ...
  
  // 量化工具
  ...quantTools,                    // manage_quant_strategy, run_backtest, generate_signals, score_stock, train_signal_model
  
  // ... 其他工具 ...
];
```

**注意**：这是最快落地路径。理想的长期方案是把 `dist/services/quant/` 的相关代码恢复成 `src/services/quant/` 下的 .ts 源文件。

### 3.2 同步文档与实际工具名

将 TOOLS.md 中的过时名称替换为实际注册后的名称：

```
TOOLS.md 中的变更：

❌ predict_stock_signal          → ✅ generate_signals(action="scan")
❌ backtest_strategy()            → ✅ run_backtest()
❌ evaluate_model                 → ✅ score_stock()
❌ train_model                    → ✅ train_signal_model()
```

Path C 第4轮改为：

```
background_run(10, "generate_signals", {symbol})  // 量化信号（强制）
```

### 3.3 修改 SOUL.md 决策链 — 强制量化调用

在 SOUL.md 第6章 Phase 4（技术面）之后，新增 **Phase 4B：量化验证（强制）**：

```
### Phase 4B: 量化验证（强制）
10. `generate_signals(action="scan", symbol)` → 获取当日量化信号
11. `score_stock(symbol)` → 因子评分（PE/RSI/动量/趋势）
12. `query_experience(scenario="相似模式", symbol)` → 历史胜率验证
```

同时将现有 Phase 5 改为 **Phase 5: 信号确认（可选）** 保持不变。

### 3.4 恢复量化服务源文件

从 dist 反推恢复 src 源文件（可选，建议做）：

| 目标 | 源文件位置 |
|:---|---|
| `src/services/quant/backtest-engine.ts` | 从 `dist/services/quant/backtest-engine.js` 反编译 |
| `src/services/quant/factor-library.ts` | 从 `dist/services/quant/factor-library.js` 反编译 |
| `src/services/quant/signal-generator.ts` | 从 `dist/services/quant/signal-generator.js` 反编译 |
| `src/services/quant/quant-tools.ts` | 从 `dist/services/quant/quant-tools.js` 反编译 |
| `src/services/quant/quant-service.ts` | 从 `dist/services/quant/quant-service.js` 反编译 |

恢复后，导入路径从 `dist/` 改为 `src/`。

---

## 四、改造排序和排期

| 优先级 | 任务 | 工作量 | 影响 |
|:---:|---|---|:---:|
| **P0** | 注册 quantTools 到 index.ts | 1 行 import + 1 行 push | **解决核心断点，5个量化工具立即可用** |
| **P0** | 修复 TOOLS.md Path C 第4轮的过时工具名 | 2 行文本替换 | 保证文档和实际工具一致 |
| **P1** | 新增 SOUL.md Phase 4B 量化验证 | 文档修改 | 让我在分析时被强制触发量化调用 |
| **P1** | 验证 `query_experience` 使用路径 | 功能验证 | 已有工具激活使用 |
| **P2** | 恢复量化服务源文件到 src/ | 5 个文件 | 长期维护性，去掉 dist 依赖 |
| **P2** | 增加 `query_experience` 到 SOUL.md Phase 4B | 1 行 | 历史经验库使用 |

---

## 五、执行后效果

改造完成后，分析一只股票将变成：

```
[Phase 1-3] 基本面 + 估值（同现在）
    ↓
[Phase 4] 技术面（同现在）
    ↓
[Phase 4B] 量化验证（新增，强制）
    ├── generate_signals(action="scan", symbol) → 量化信号
    ├── score_stock(symbol) → 因子评分
    └── query_experience(scenario, symbol) → 历史胜率
    ↓
[Phase 5] 信号确认（可选）
    ↓
输出（包含量化评分 + 上涨概率）
```

这样**不可能绕过量化工具**——因为 SOUL.md 的检查清单会强制我调用。

---

## 六、现有量化策略资产

项目中已有 17 个量化策略（`.pi-invest/quant/strategies/`），包括：

1. **低估值反转策略** — PE<15, RSI<30 买入
2. **RSI超卖反转策略** — RSI<30 买入
3. **均线金叉策略** — MA5上穿MA20 买入
4. **MACD策略** — MACD>0 买入
5. **布林带策略** — 价格触及下轨 买入
6. **成交量突破策略** — 放量突破 买入
7. **组合策略** — 多条件复合
8-17. 更多变体...

还有历史回测 20 次（`.pi-invest/quant/backtests-archive.json`），信号文件1份（`.pi-invest/quant/signals/2026-03-25.json`）。

**这些都是已经存在的资产，只是从未通过我暴露给你。**
