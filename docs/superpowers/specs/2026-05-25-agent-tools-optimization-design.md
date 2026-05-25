# Agent 工具优化设计文档

**日期：** 2026-05-25  
**作者：** Claude  
**状态：** 设计阶段

## 1. 背景与目标

### 1.1 当前状态

pi-investment 项目当前有 **61 个投资工具** 分散在 13 个文件中，总计约 10,000 行代码。工具按功能域组织：

- **投资工具 (invest/)**: 61 个工具，分为 market、stock-query、analysis、financial、screening、sentiment、portfolio、HK-specific
- **Agent 元工具 (agent/)**: 11 个工具（plan、clarify、task、memory 等）
- **交易工具 (trading/)**: 订单管理、挂单检查、交易日志、关注列表
- **分析工具 (analysis/)**: 板块轮动、止损检查、市场情绪
- **数据工具 (data/)**: 股票数据库管理

### 1.2 存在的问题

**A) 工具数量过多**
- Agent 需要从 61 个投资工具中选择，决策负担重
- DeepSeek 模型一次只能调用一个工具，多步骤任务需要多轮对话
- 工具功能有重叠（如 get_stock_info + get_stock_price 经常一起调用）

**B) 可发现性差**
- 工具命名不统一（get_*/analyze_*/check_* 混用）
- 缺少明确的工具分类和优先级指引
- Agent 经常选错工具或遗漏必要的工具调用

**D) 逻辑分组不清晰**
- 当前按数据类型分组（market/stock/financial），而非按业务流程
- 缺少系统架构层次（数据层、因子层、模型层、组合层、执行层、监控层）
- 工具职责边界模糊，难以扩展

### 1.3 优化目标

1. **减少工具数量**：从 61 个降到 30 个左右
2. **改善可发现性**：统一命名规范，按系统架构分层
3. **清晰逻辑分组**：映射量化投资系统的六层架构
4. **保留所有功能**：零破坏性迁移，所有现有功能保留
5. **支持渐进式迁移**：分阶段实施，每个阶段可独立验证

## 2. 设计方案

### 2.1 核心思路

将工具按 **量化投资系统的六层架构** 重新组织：

```
L1: 数据管道 (data_*)     - 行情获取、数据质量、增量更新
L2: 因子工厂 (factor_*)   - 因子计算、IC分析、失效监控
L3: 模型层 (model_*)       - 训练、预测、版本管理、特征监控
L4: 组合构建 (portfolio_*) - 优化、风险预算、压力测试
L5: 执行引擎 (trade_*)     - 订单管理、算法交易、对账
L6: 监控运维 (monitor_*)   - 实时风控、异常检测、绩效归因
```

每层工具有明确的：
- **输入**：上游数据或信号
- **处理**：核心业务逻辑
- **输出**：下游消费的标准格式
- **职责边界**：单一职责原则

### 2.2 六层架构详细设计

#### L1: 数据管道工具 (data_*)

**职责：** 数据获取、清洗、校验、存储、增量更新

**工具列表：**

| 工具名 | 功能 | 输入 | 输出 | 状态 |
|--------|------|------|------|------|
| `data_fetch_kline` | 获取K线数据（tick/分钟/日线） | symbol, period, start_date, end_date | OHLCV时序数据 | ✅ 已有 (get_stock_history) |
| `data_fetch_financial` | 获取财务报表 | symbol, report_type | 财务数据JSON | ✅ 已有 (get_financial_data) |
| `data_fetch_stock` | 获取股票基础信息 | symbol, fields | 股票信息JSON | ✅ 已有 (get_stock_info/price/news) |
| `data_validate` | 数据质量检查 | symbol, data_type | 质量报告（缺失/异常/时间对齐） | ❌ 需新增 |
| `data_sync` | 触发增量更新 | symbols, data_types | 更新状态 | ❌ 需新增 |

**Why:** 数据是量化系统的基础，必须保证质量和时效性。当前缺少数据质量监控和增量更新机制。

**How to apply:** 
- 所有数据获取工具统一前缀 `data_`
- 新增 `data_validate` 检查数据完整性（缺失值、异常值、时间对齐）
- 新增 `data_sync` 触发增量更新（避免每次全量拉取）

**迁移方案：**
```typescript
// 保留现有工具，重命名
get_stock_history → data_fetch_kline
get_financial_data → data_fetch_financial
get_stock_info + get_stock_price + get_stock_news → data_fetch_stock (参数: fields)
```

---

#### L2: 因子工厂工具 (factor_*)

**职责：** 因子计算、IC分析、有效性监控、版本管理

**工具列表：**

| 工具名 | 功能 | 输入 | 输出 | 状态 |
|--------|------|------|------|------|
| `factor_calculate` | 批量计算因子 | symbol, factors, date_range | 因子值矩阵 | 🔄 部分实现 (analyze_technical等) |
| `factor_analyze_ic` | IC分析 | factor_name, period | IC值、衰减曲线 | ❌ 需新增 |
| `factor_backtest` | 因子分层回测 | factor_name, groups | 分组收益、多空收益 | ❌ 需新增 |
| `factor_monitor` | 因子失效监控 | factor_name | IC衰减、实盘偏差 | ❌ 需新增 |
| `factor_list` | 查看因子库 | category, status | 因子列表、版本信息 | ❌ 需新增 |

**Why:** 当前有 62 个因子定义，但缺少因子有效性追踪和版本管理。因子失效是量化策略最大的风险。

**How to apply:**
- `factor_calculate` 作为统一入口，内部路由到具体因子计算函数
- `factor_monitor` 监控因子 IC 衰减和实盘偏差，自动报警
- 因子版本管理：每次因子定义修改，记录版本号和变更原因

**迁移方案：**
```typescript
// 现有分析工具整合为因子计算
analyze_technical → factor_calculate(factors=["ma", "macd", "rsi", "boll"])
analyze_price_action → factor_calculate(factors=["trend", "support", "resistance"])
get_valuation → factor_calculate(factors=["pe", "pb", "graham_value"])
get_quality_score → factor_calculate(factors=["quality_score"])
```

---

#### L3: 模型层工具 (model_*)

**职责：** 模型训练、预测、版本管理、特征监控

**工具列表：**

| 工具名 | 功能 | 输入 | 输出 | 状态 |
|--------|------|------|------|------|
| `model_train` | 训练模型 | features, target, params | 模型ID、评估指标 | 🔄 部分实现 (ModelStage) |
| `model_predict` | 预测信号 | model_id, symbols | 预测值、置信度 | 🔄 部分实现 (strategy_engine) |
| `model_evaluate` | 模型评估 | model_id, test_data | 回测结果、AB测试 | ❌ 需新增 |
| `model_monitor` | 特征漂移监控 | model_id | 特征重要性变化、漂移报警 | ❌ 需新增 |
| `model_list` | 模型版本管理 | status | 模型列表、版本信息 | ❌ 需新增 |

**Why:** 当前有 ModelStage 和 XGBoost/LightGBM，但缺少模型版本管理和特征漂移监控。模型在实盘中会因特征分布变化而失效。

**How to apply:**
- 集成 MLflow 或自建模型注册表
- `model_monitor` 监控特征重要性变化，检测特征漂移
- 支持多模型集成（ensemble）

**迁移方案：**
```typescript
// 现有策略引擎拆分为训练和预测
strategy_engine → model_predict (预测部分)
// 新增训练工具
model_train (新增)
```

---

#### L4: 组合构建工具 (portfolio_*)

**职责：** 信号融合、风险预算、组合优化、压力测试

**工具列表：**

| 工具名 | 功能 | 输入 | 输出 | 状态 |
|--------|------|------|------|------|
| `portfolio_optimize` | 组合优化 | signals, constraints | 最优权重 | ❌ 需新增 |
| `portfolio_risk_budget` | 风险预算分配 | portfolio, risk_limit | 风险敞口、VaR/CVaR | ❌ 需新增 |
| `portfolio_rebalance` | 调仓建议 | current_positions, target_weights | 交易清单、换手率 | 🔄 部分实现 (manage_portfolio) |
| `portfolio_stress_test` | 压力测试 | portfolio, scenarios | 极端情况下的损失 | ❌ 需新增 |
| `portfolio_dashboard` | 组合仪表盘 | - | 持仓、收益、风险指标 | ✅ 已有 |

**Why:** 当前有 RiskStage 和 portfolio 模块，但缺少组合优化器和压力测试。多策略信号融合也需要系统化。

**How to apply:**
- `portfolio_optimize` 实现均值方差优化或 Black-Litterman 模型
- `portfolio_stress_test` 模拟极端市场情况（如 2015 股灾、2020 熔断）
- 支持多策略信号融合（加权、投票、机器学习融合）

**迁移方案：**
```typescript
// 保留现有工具
manage_portfolio → portfolio_rebalance (重命名)
portfolio_dashboard → portfolio_dashboard (保持)
// 新增优化和压力测试
portfolio_optimize (新增)
portfolio_stress_test (新增)
```

---

#### L5: 执行引擎工具 (trade_*)

**职责：** 订单管理、算法交易、成交对账、执行监控

**工具列表：**

| 工具名 | 功能 | 输入 | 输出 | 状态 |
|--------|------|------|------|------|
| `trade_create_order` | 创建订单 | symbol, side, quantity, order_type | 订单ID | 🔄 部分实现 (manageOrdersTool) |
| `trade_manage_orders` | 订单管理 | action, order_id | 订单状态 | ✅ 已有 (manageOrdersTool) |
| `trade_execute_algo` | 算法交易 | symbol, quantity, algo_type | 执行报告 | ❌ 需新增 |
| `trade_reconcile` | 成交对账 | date | 对账报告 | ❌ 需新增 |
| `trade_monitor` | 执行监控 | - | 滑点、延迟统计 | ❌ 需新增 |

**Why:** 当前有基础订单管理，但缺少算法交易（TWAP/VWAP）和成交对账。执行质量直接影响策略收益。

**How to apply:**
- `trade_execute_algo` 实现 TWAP（时间加权）、VWAP（成交量加权）、冰山订单
- `trade_reconcile` 对比订单记录和券商成交回报，检测遗漏或错误
- `trade_monitor` 统计滑点和执行延迟

**迁移方案：**
```typescript
// 保留现有工具
manageOrdersTool → trade_manage_orders (重命名)
checkPendingOrdersTool → trade_check_pending (重命名)
// 新增算法交易和对账
trade_execute_algo (新增)
trade_reconcile (新增)
```

---

#### L6: 监控运维工具 (monitor_*)

**职责：** 实时风控、异常检测、告警、绩效归因

**工具列表：**

| 工具名 | 功能 | 输入 | 输出 | 状态 |
|--------|------|------|------|------|
| `monitor_risk` | 实时风控 | - | 仓位、回撤、熔断状态 | ❌ 需新增 |
| `monitor_signal` | 信号偏离监控 | strategy_id | 信号偏离度、异常报警 | ❌ 需新增 |
| `monitor_execution` | 执行质量监控 | - | 滑点、延迟统计 | ❌ 需新增 |
| `monitor_alert` | 告警管理 | alert_type, message | 推送状态 | ✅ 已有 (notificationTools) |
| `review_attribution` | 绩效归因分析 | date_range | 收益归因、风险归因 | ❌ 需新增 |

**Why:** 当前有消息推送，但缺少实时风控和绩效归因。监控是量化系统的安全网。

**How to apply:**
- `monitor_risk` 实时检查仓位上限、回撤熔断、集中度风险
- `monitor_signal` 检测信号与历史分布的偏离（可能是数据问题或模型失效）
- `review_attribution` 分解收益来源（因子贡献、行业贡献、个股贡献）

**迁移方案：**
```typescript
// 保留现有工具
notificationTools → monitor_alert (重命名)
// 新增风控和归因
monitor_risk (新增)
review_attribution (新增)
```

## 3. 工具总览

### 3.1 工具数量对比

| 层级 | 当前工具数 | 优化后工具数 | 变化 |
|------|-----------|-------------|------|
| L1 数据管道 | 8 (分散在多处) | 5 | -3 (合并) |
| L2 因子工厂 | 15 (分散在 analysis/) | 5 | -10 (合并) |
| L3 模型层 | 1 (strategy_engine) | 5 | +4 (拆分) |
| L4 组合构建 | 3 (portfolio相关) | 5 | +2 (新增) |
| L5 执行引擎 | 4 (trading/) | 5 | +1 (新增) |
| L6 监控运维 | 2 (notification/monitor) | 5 | +3 (新增) |
| Agent 元工具 | 11 | 11 | 0 (保持) |
| 其他工具 | 17 (screening/sentiment/hk等) | 整合到上述层级 | - |
| **总计** | **61** | **41** | **-20 (-33%)** |

**注：** 41 个工具包含 11 个 Agent 元工具 + 30 个业务工具（6层 × 5工具/层）

### 3.2 命名规范

**统一前缀：**
- `data_*` - 数据管道工具
- `factor_*` - 因子工厂工具
- `model_*` - 模型层工具
- `portfolio_*` - 组合构建工具
- `trade_*` - 执行引擎工具
- `monitor_*` - 监控运维工具

**动词规范：**
- `fetch` - 获取数据
- `calculate` - 计算/分析
- `train` - 训练模型
- `predict` - 预测
- `optimize` - 优化
- `manage` - 管理
- `monitor` - 监控
- `review` - 复盘/归因

### 3.3 工具注册顺序

在 `src/infrastructure/tools/index.ts` 中按层级顺序注册：

```typescript
export const allCustomTools = [
  // Agent 元工具（高频）
  planTool,
  clarifyTool,
  taskCreateTool,
  ...
  
  // L1: 数据管道
  ...dataTools,
  
  // L2: 因子工厂
  ...factorTools,
  
  // L3: 模型层
  ...modelTools,
  
  // L4: 组合构建
  ...portfolioTools,
  
  // L5: 执行引擎
  ...tradeTools,
  
  // L6: 监控运维
  ...monitorTools,
  
  // 低频工具
  compactTool,
  browserTool,
  readTool,
];
```

## 4. 实施计划

### 4.1 分阶段实施

**阶段 0：准备工作（1周）**
- 创建新的目录结构
- 编写工具迁移脚本
- 设置特性开关（feature flag）支持新旧工具并存

**阶段 1：数据层重构（2周）**
- 实现 `data_validate`（数据质量检查）
- 实现 `data_sync`（增量更新）
- 重命名现有数据工具（get_stock_* → data_fetch_*）
- 测试数据层工具

**阶段 2：因子层增强（3周）**
- 实现 `factor_calculate`（批量因子计算）
- 实现 `factor_monitor`（因子监控）
- 迁移现有 62 个因子到新架构
- 实现 `factor_analyze_ic` 和 `factor_backtest`
- 测试因子层工具

**阶段 3：模型层补全（3周）**
- 实现 `model_train`/`model_predict`（拆分 strategy_engine）
- 实现 `model_monitor`（特征漂移）
- 集成 MLflow 或自建版本管理
- 实现 `model_evaluate`（AB测试）
- 测试模型层工具

**阶段 4：组合层优化（2周）**
- 实现 `portfolio_optimize`（组合优化器）
- 实现 `portfolio_stress_test`（压力测试）
- 实现 `portfolio_risk_budget`（风险预算）
- 测试组合层工具

**阶段 5：执行层完善（3周）**
- 实现 `trade_execute_algo`（TWAP/VWAP）
- 实现 `trade_reconcile`（对账）
- 实现 `trade_monitor`（执行监控）
- 测试执行层工具

**阶段 6：监控层建设（2周）**
- 实现 `monitor_risk`（实时风控）
- 实现 `review_attribution`（绩效归因）
- 实现 `monitor_signal` 和 `monitor_execution`
- 测试监控层工具

**阶段 7：清理与文档（1周）**
- 移除旧工具（保留 deprecated 标记 1 个月）
- 更新文档和示例
- 性能测试和优化

**总计：17 周（约 4 个月）**

### 4.2 风险控制

**向后兼容策略：**
1. 新旧工具并存 1 个月，通过特性开关控制
2. 旧工具标记为 `@deprecated`，返回提示信息引导使用新工具
3. 保留旧工具的别名映射（alias）

**回滚方案：**
1. 每个阶段独立部署，可单独回滚
2. 保留旧工具代码在 `src/infrastructure/tools/legacy/`
3. 数据库 schema 变更使用 migration，可回滚

**测试策略：**
1. 单元测试覆盖率 > 80%
2. 集成测试覆盖核心工作流
3. 回测对比新旧工具的输出一致性
4. 灰度发布：先在 quantsys-v2 测试，再迁移到主系统

### 4.3 成功指标

**量化指标：**
- 工具数量：从 61 降到 41（-33%）
- Agent 工具选择准确率：从 ~70% 提升到 >85%
- 平均任务完成轮次：从 5-7 轮降到 3-5 轮
- 工具调用延迟：保持在 <2s（P95）

**质量指标：**
- 代码覆盖率：>80%
- 文档完整性：每个工具有完整的 description、parameters、examples
- 用户满意度：通过 Agent 对话日志分析，减少"工具选择错误"的情况

## 5. 技术细节

### 5.1 工具实现模式

**智能路由模式（用于合并工具）：**

```typescript
// 示例：data_fetch_stock 整合多个数据源
export const dataFetchStockTool: ToolDefinition = {
  name: "data_fetch_stock",
  description: "获取股票数据（信息/价格/新闻/公告）",
  parameters: Type.Object({
    symbol: Type.String(),
    fields: Type.Array(Type.String(), { 
      description: "需要的字段：info, price, news, announcements" 
    }),
  }),
  execute: async (_toolCallId, params: any) => {
    const results: any = {};
    
    // 根据 fields 参数路由到具体实现
    if (params.fields.includes('info')) {
      results.info = await getStockInfo(params.symbol);
    }
    if (params.fields.includes('price')) {
      results.price = await getStockPrice(params.symbol);
    }
    if (params.fields.includes('news')) {
      results.news = await getStockNews(params.symbol);
    }
    
    return { content: [{ type: "text", text: JSON.stringify(results) }] };
  },
};
```

**批量计算模式（用于因子工具）：**

```typescript
// 示例：factor_calculate 批量计算因子
export const factorCalculateTool: ToolDefinition = {
  name: "factor_calculate",
  description: "批量计算因子",
  parameters: Type.Object({
    symbol: Type.String(),
    factors: Type.Array(Type.String(), {
      description: "因子列表：technical, valuation, quality, momentum 等"
    }),
  }),
  execute: async (_toolCallId, params: any) => {
    const factorRegistry = {
      technical: calculateTechnicalFactors,
      valuation: calculateValuationFactors,
      quality: calculateQualityFactors,
      momentum: calculateMomentumFactors,
    };
    
    const results: any = {};
    for (const factor of params.factors) {
      const calculator = factorRegistry[factor];
      if (calculator) {
        results[factor] = await calculator(params.symbol);
      }
    }
    
    return { content: [{ type: "text", text: JSON.stringify(results) }] };
  },
};
```

### 5.2 数据流设计

**层级数据流：**

```
用户请求
  ↓
Agent 选择工具
  ↓
L1: data_fetch_* → 原始数据
  ↓
L2: factor_calculate → 因子值
  ↓
L3: model_predict → 预测信号
  ↓
L4: portfolio_optimize → 最优权重
  ↓
L5: trade_create_order → 订单执行
  ↓
L6: monitor_risk → 风控检查
  ↓
返回结果给用户
```

**缓存策略：**
- L1 数据层：日线数据缓存 1 天，分钟数据缓存 5 分钟
- L2 因子层：因子值缓存到当日收盘
- L3 模型层：预测结果缓存 1 小时
- L4-L6：不缓存（实时计算）

### 5.3 错误处理

**统一错误格式：**

```typescript
interface ToolError {
  error: string;           // 错误信息
  error_code: string;      // 错误代码（DATA_UNAVAILABLE, INVALID_PARAM 等）
  layer: string;           // 所属层级（L1-L6）
  recoverable: boolean;    // 是否可恢复
  suggestion?: string;     // 修复建议
}
```

**错误传播：**
- L1 数据错误：立即返回，不继续执行
- L2-L3 计算错误：返回部分结果 + 错误信息
- L4-L6 业务错误：返回错误 + 降级方案

## 6. 附录

### 6.1 完整工具映射表

| 旧工具名 | 新工具名 | 变化类型 | 所属层级 |
|---------|---------|---------|---------|
| get_stock_info | data_fetch_stock | 合并 | L1 |
| get_stock_price | data_fetch_stock | 合并 | L1 |
| get_stock_news | data_fetch_stock | 合并 | L1 |
| get_announcements | data_fetch_stock | 合并 | L1 |
| get_stock_history | data_fetch_kline | 重命名 | L1 |
| get_financial_data | data_fetch_financial | 重命名 | L1 |
| analyze_technical | factor_calculate | 合并 | L2 |
| analyze_price_action | factor_calculate | 合并 | L2 |
| analyze_candlestick | factor_calculate | 合并 | L2 |
| get_valuation | factor_calculate | 合并 | L2 |
| get_pe_percentile | factor_calculate | 合并 | L2 |
| get_quality_score | factor_calculate | 合并 | L2 |
| get_buy_range | portfolio_optimize | 整合 | L4 |
| compare_peers | factor_calculate | 合并 | L2 |
| strategy_engine | model_predict | 拆分 | L3 |
| manage_portfolio | portfolio_rebalance | 重命名 | L4 |
| portfolio_dashboard | portfolio_dashboard | 保持 | L4 |
| manageOrdersTool | trade_manage_orders | 重命名 | L5 |
| checkPendingOrdersTool | trade_check_pending | 重命名 | L5 |
| notificationTools | monitor_alert | 重命名 | L6 |

### 6.2 目录结构

```
src/infrastructure/tools/
├── index.ts                    # 工具注册中心
├── skill-guard.ts              # Skill 权限守卫
├── agent/                      # Agent 元工具（保持不变）
│   ├── plan-tool.ts
│   ├── clarify-tool.ts
│   └── ...
├── data/                       # L1: 数据管道工具
│   ├── fetch-kline-tool.ts
│   ├── fetch-financial-tool.ts
│   ├── fetch-stock-tool.ts
│   ├── validate-tool.ts
│   └── sync-tool.ts
├── factor/                     # L2: 因子工厂工具
│   ├── calculate-tool.ts
│   ├── analyze-ic-tool.ts
│   ├── backtest-tool.ts
│   ├── monitor-tool.ts
│   └── list-tool.ts
├── model/                      # L3: 模型层工具
│   ├── train-tool.ts
│   ├── predict-tool.ts
│   ├── evaluate-tool.ts
│   ├── monitor-tool.ts
│   └── list-tool.ts
├── portfolio/                  # L4: 组合构建工具
│   ├── optimize-tool.ts
│   ├── risk-budget-tool.ts
│   ├── rebalance-tool.ts
│   ├── stress-test-tool.ts
│   └── dashboard-tool.ts
├── trade/                      # L5: 执行引擎工具
│   ├── create-order-tool.ts
│   ├── manage-orders-tool.ts
│   ├── execute-algo-tool.ts
│   ├── reconcile-tool.ts
│   └── monitor-tool.ts
├── monitor/                    # L6: 监控运维工具
│   ├── risk-tool.ts
│   ├── signal-tool.ts
│   ├── execution-tool.ts
│   ├── alert-tool.ts
│   └── attribution-tool.ts
├── shared/                     # 共享工具函数
│   ├── python-caller.ts
│   ├── validators.ts
│   └── cache.ts
└── legacy/                     # 旧工具（待移除）
    └── invest/
        └── ...
```

### 6.3 参考资料

- [量化投资系统架构设计](https://example.com)
- [因子有效性分析方法](https://example.com)
- [组合优化算法对比](https://example.com)
- [算法交易实现指南](https://example.com)

---

**文档版本：** v1.0  
**最后更新：** 2026-05-25  
**审核状态：** 待审核

