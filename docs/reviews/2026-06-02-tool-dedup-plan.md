# 工具去重方案文档

**日期**: 2026-06-02  
**项目**: pi-investment  
**目标**: 消除工具功能重叠，精简工具集，降低维护成本

---

## 一、重叠分析总结

### 1.1 高重叠（必须合并）

#### 1. `strategy_create` ↔ `strategy_write`

**代码分析**:
- **strategy_create**: 调用 `runQuantV2("strategy.create", params)`，创建策略
- **strategy_write**: 
  - 不传 `indicator_id` → 调用 `createIndicator()` 创建新策略
  - 传 `indicator_id` → 调用 `updateIndicator()` 更新已有策略

**重叠点**:
- 两者都能创建新策略
- strategy_write 的文档明确说"不提供 indicator_id = 创建新策略"
- 实际上 strategy_write 是 strategy_create 的超集（还能更新）

**使用情况**:
- 在 `src/infrastructure/tools/index.ts` 中两者都被导出并注册
- 无法找到直接引用（说明主要通过 Agent 调用）

**结论**: **高度重叠**，strategy_create 功能完全被 strategy_write 包含

---

#### 2. `strategy_execute` ↔ `strategy_run`

**代码分析**:
- **strategy_execute**: 
  - 支持三种模式：single（单股）、batch（批量）、pipeline（完整流水线）
  - 调用 `runQuantV2("strategy.execute", params)`
  - 包含市场风格检测、格式化输出
  - 支持风控检查、订单创建
  - 240 行代码，功能丰富

- **strategy_run**:
  - 仅支持实时运行策略生成信号
  - 调用 `runQuantV2("strategy.run", params)`
  - 57 行代码，功能单一

**重叠点**:
- 两者都能运行策略生成信号
- strategy_run 的功能是 strategy_execute 的 single 模式的子集

**结论**: **高度重叠**，strategy_run 功能完全被 strategy_execute 包含

---

### 1.2 中重叠（需明确分工）

#### 3. `factor_calculate` ↔ `analysis_cli analysis.technical` ↔ `stock_cli stock.technical`

**代码分析**:
- **factor_calculate**:
  - 调用 `computeFactors()` → `/api/factors/compute`
  - 批量计算多个因子（技术+基本面）
  - 返回格式化的因子结果
  - 定位：L2 因子工厂层

- **analysis_cli analysis.technical**:
  - 调用 `runQuantV2("analysis.technical")` → `/api/stock/{symbol}/technical`
  - 技术分析（RSI、MACD、布林带、均线、KDJ）
  - 定位：股票分析工具

- **stock_cli stock.technical**:
  - 调用 `runQuantV2("stock.technical")` → `/api/stock/{symbol}/technical`
  - 技术指标计算（RSI、MACD、布林带等）
  - 定位：个股数据查询

**重叠点**:
- 三者都能计算技术指标（RSI、MACD、布林带等）
- analysis_cli 和 stock_cli 实际上都调用同一个后端端点 `/api/stock/{symbol}/technical`

**后端实现**:
- `quant-v2-client.ts` 中 `analysis.technical` 和 `stock.technical` 映射到相同端点
- factor_calculate 走单独的 `/api/factors/compute` 端点，但底层计算逻辑可能相同

**结论**: **中度重叠**，三条路径可达相似终点，但定位不同：
- `factor_calculate`: 批量、工厂模式、多因子
- `analysis_cli`: 单股分析、完整技术分析报告
- `stock_cli`: 单股查询、快速技术指标

---

#### 4. `opportunity_scan` ↔ `stock_cli stock.score`

**代码分析**:
- **opportunity_scan**:
  - 调用 `scanOpportunities()` → `/api/signals/scan`
  - 批量扫描股票池，三维评分（技术面50% + 基本面30% + 资金面20%）
  - 支持筛选条件（RSI超卖、MACD金叉、PE、ROE等）
  - 支持行业轮动筛选
  - 返回评分 + 风险等级 + 信号理由
  - 定位：机会雷达（L2.5）

- **stock_cli stock.score**:
  - 调用 `runQuantV2("stock.score")` → `/api/stock/{symbol}/score`
  - 综合评分（技术+基本面+动量+质量+估值）
  - 单股评分
  - 定位：个股数据查询

**后端实现**:
- opportunity_scan 使用 `OpportunityScoringServiceV2`（批量并行处理）
- stock.score 调用 `/api/stock/{symbol}/score` 端点（单股评分）
- 评分算法可能相同，但调用方式不同

**结论**: **中度重叠**，功能相似但侧重点不同：
- `opportunity_scan`: 批量扫描、筛选、排序、行业轮动
- `stock_cli stock.score`: 单股评分、快速查询

---

### 1.3 低重叠（保持现状）

#### 5. `data_fetch_financial` ↔ `financial_cli financial.income_statement`

**分析**: 
- `data_fetch_financial`: 专用数据获取工具，返回结构化数据
- `financial_cli`: CLI 命令包装，支持多种财务查询
- **侧重点不同**，一个是数据管道（L1），一个是业务查询

**结论**: **保持现状**

---

#### 6. `indicator_backtest` ↔ `quant_cli backtest.run`

**分析**:
- `indicator_backtest`: 针对 indicator 类型策略的回测
- `quant_cli backtest.run`: 通用回测命令
- **面向对象不同**，一个专注 indicator，一个是通用入口

**结论**: **保持现状**

---

#### 7. `sentiment_cli sentiment.margin_data` ↔ `market_cli market.margin`

**分析**:
- `sentiment_cli sentiment.margin_data`: 个股融资融券数据
- `market_cli market.margin`: 全市场融资融券概况
- **粒度不同**，个股 vs 全市场，交集有限

**结论**: **保持现状**

---

## 二、去重方案

### 2.1 高优先级合并（P0）

#### 方案 1: 删除 `strategy_create`，保留 `strategy_write`

**理由**:
- `strategy_write` 功能更完整（创建+更新）
- `strategy_create` 是 `strategy_write` 的子集
- `strategy_write` 工作流更清晰："写→测→迭代"

**实施步骤**:
1. **删除工具定义**:
   - 删除 `src/infrastructure/tools/strategy/create-tool.ts`
   - 从 `src/infrastructure/tools/index.ts` 移除 `strategyCreateTool` 导入和注册

2. **更新系统提示词**:
   - 在 `CLAUDE.md` 中移除 `strategy_create` 的描述
   - 强调 `strategy_write` 的双重功能（创建+更新）

3. **更新文档**:
   - 在用户文档中说明使用 `strategy_write` 创建新策略

**风险点**:
- ❌ **低风险**：两者调用不同后端接口（`strategy.create` vs `indicators.create`），但功能相同
- ⚠️ 需要确认后端 `strategy.create` 和 `indicators.create` 是否有差异

**迁移路径**:
```typescript
// 旧方式
strategy_create({ name: "策略A", code: "..." })

// 新方式
strategy_write({ name: "策略A", code: "..." })  // 不传 indicator_id 即创建
```

---

#### 方案 2: 删除 `strategy_run`，保留 `strategy_execute`

**理由**:
- `strategy_execute` 功能更强大（三种模式：single/batch/pipeline）
- `strategy_run` 功能完全被 `strategy_execute` 的 single 模式覆盖
- `strategy_execute` 还集成了市场风格检测、格式化输出

**实施步骤**:
1. **删除工具定义**:
   - 删除 `src/infrastructure/tools/strategy/run-tool.ts`
   - 从 `src/infrastructure/tools/index.ts` 移除 `strategyRunTool` 导入和注册

2. **更新系统提示词**:
   - 在 `CLAUDE.md` 中移除 `strategy_run` 的描述
   - 强调 `strategy_execute` 的三种模式用法

3. **更新文档**:
   - 在用户文档中说明使用 `strategy_execute` 的 single 模式替代 `strategy_run`

**风险点**:
- ❌ **低风险**：两者调用不同后端接口（`strategy.run` vs `strategy.execute`），需确认兼容性
- ⚠️ 如果用户习惯用 `strategy_run` 的简单接口，可能需要适应

**迁移路径**:
```typescript
// 旧方式
strategy_run({ strategy_id: "123", symbols: ["600000"] })

// 新方式
strategy_execute({ 
  action: "single",          // 或 "batch"
  strategy: "123", 
  symbols: ["600000"]         // batch 模式
})
```

---

### 2.2 中优先级明确分工（P1）

#### 方案 3: 明确技术指标工具的分工

**分析**:
- `factor_calculate`: **保留**，定位为 L2 因子工厂，批量计算多因子
- `analysis_cli analysis.technical`: **保留**，定位为完整技术分析报告（含图表、趋势判断）
- `stock_cli stock.technical`: **合并到 analysis_cli** 或 **明确为快速查询**

**推荐方案**: **保留三者，但明确分工**

**实施步骤**:
1. **更新工具描述**:
   - `factor_calculate`: "L2 因子工厂：批量计算多个技术+基本面因子，适用于因子研究和多股对比"
   - `analysis_cli analysis.technical`: "完整技术分析：RSI、MACD、KDJ、布林带、均线系统，含趋势判断和图表"
   - `stock_cli stock.technical`: "快速技术指标查询：单股 RSI、MACD、布林带等关键指标"

2. **更新系统提示词**:
   - 在 `CLAUDE.md` 中明确使用场景：
     - 因子研究 → `factor_calculate`
     - 完整分析 → `analysis_cli`
     - 快速查询 → `stock_cli`

**风险点**:
- ❌ **无风险**：只是明确分工，不删除功能

**替代方案**（更激进）:
- 删除 `stock_cli stock.technical`，只保留 `analysis_cli analysis.technical` 和 `factor_calculate`
- 理由：`stock_cli` 和 `analysis_cli` 调用相同后端端点，功能完全重复

---

#### 方案 4: 明确评分工具的分工

**分析**:
- `opportunity_scan`: 批量扫描+筛选+排序，适用于市场扫描找机会
- `stock_cli stock.score`: 单股评分，适用于快速查看个股综合得分

**推荐方案**: **保留两者，明确分工**

**实施步骤**:
1. **更新工具描述**:
   - `opportunity_scan`: "机会雷达：批量扫描股票池，三维评分（技术50%+基本面30%+资金20%），支持筛选条件和行业轮动，适用于市场扫描、多股对比、策略信号确认"
   - `stock_cli stock.score`: "单股综合评分：快速查看个股的技术面、基本面、动量、质量、估值综合得分"

2. **更新系统提示词**:
   - 在 `CLAUDE.md` 中明确使用场景：
     - 市场扫描找机会 → `opportunity_scan`
     - 单股快速评分 → `stock_cli stock.score`

**风险点**:
- ❌ **无风险**：只是明确分工，不删除功能

---

## 三、系统提示词修改（CLAUDE.md）

### 3.1 删除工具相关描述

需要从 `CLAUDE.md` 中移除以下工具的描述：

1. **strategy_create**: 删除该工具的使用说明，在 `strategy_write` 中强调"不传 indicator_id 即创建新策略"
2. **strategy_run**: 删除该工具的使用说明，在 `strategy_execute` 中强调"支持三种模式，single 模式可替代 strategy_run"

### 3.2 增强工具描述

在 `CLAUDE.md` 的工具列表部分，增强以下工具的描述：

```markdown
#### L3.5 策略工具

**strategy_write** — 策略编写（创建+更新）
- 不传 indicator_id → 创建新策略
- 传 indicator_id → 更新已有策略
- 典型工作流：strategy_write → indicator_backtest → 调整参数 → strategy_write → ...

**strategy_execute** — 统一策略执行
- single 模式：单股票执行，返回详细信号和风险参数
- batch 模式：批量执行，返回汇总统计
- pipeline 模式：完整流水线（信号生成 → 风控筛选 → 订单创建）
- 自动集成市场风格检测

#### L2 因子工厂 vs 技术分析

- **factor_calculate**: 批量计算多因子，适用于因子研究和多股对比
- **analysis_cli analysis.technical**: 完整技术分析报告，含趋势判断
- **stock_cli stock.technical**: 快速技术指标查询

#### 机会扫描 vs 单股评分

- **opportunity_scan**: 批量扫描股票池，三维评分，支持筛选和行业轮动
- **stock_cli stock.score**: 单股综合评分，快速查询
```

---

## 四、实施计划

### Phase 1: P0 去重（高优先级）

**目标**: 删除高度重叠的工具

**任务清单**:
- [ ] 删除 `strategy_create` 工具
  - [ ] 删除 `src/infrastructure/tools/strategy/create-tool.ts`
  - [ ] 从 `src/infrastructure/tools/index.ts` 移除导入和注册
  - [ ] 更新 `CLAUDE.md` 系统提示词
  - [ ] 添加迁移说明文档

- [ ] 删除 `strategy_run` 工具
  - [ ] 删除 `src/infrastructure/tools/strategy/run-tool.ts`
  - [ ] 从 `src/infrastructure/tools/index.ts` 移除导入和注册
  - [ ] 更新 `CLAUDE.md` 系统提示词
  - [ ] 添加迁移说明文档

**验证**:
- [ ] 运行 `npm run build` 确保编译通过
- [ ] 启动 Agent，确认工具列表中不再出现删除的工具
- [ ] 测试 `strategy_write` 创建新策略功能
- [ ] 测试 `strategy_execute` 的 single 模式

**预计影响**:
- 工具数量：从 240 减少到 238
- 系统提示词 token 数：减少约 500 tokens

---

### Phase 2: P1 明确分工（中优先级）

**目标**: 明确工具定位，避免混淆

**任务清单**:
- [ ] 更新技术指标工具描述
  - [ ] 修改 `factor_calculate` 工具描述
  - [ ] 修改 `analysis_cli` 工具描述
  - [ ] 修改 `stock_cli` 工具描述
  - [ ] 更新 `CLAUDE.md` 使用场景说明

- [ ] 更新评分工具描述
  - [ ] 修改 `opportunity_scan` 工具描述
  - [ ] 修改 `stock_cli stock.score` 工具描述
  - [ ] 更新 `CLAUDE.md` 使用场景说明

**验证**:
- [ ] 人工 review 工具描述是否清晰
- [ ] 测试 Agent 是否能正确选择工具

**预计影响**:
- 工具数量：不变
- 用户体验：提升（工具定位更清晰）

---

## 五、风险评估与回滚计划

### 5.1 风险点

1. **后端接口差异**:
   - `strategy.create` vs `indicators.create` 可能有细微差异
   - `strategy.run` vs `strategy.execute` 可能返回格式不同
   - **缓解措施**: 仔细阅读后端代码，做兼容性测试

2. **用户习惯**:
   - 用户可能习惯使用 `strategy_create` 和 `strategy_run`
   - **缓解措施**: 在文档中提供清晰的迁移指南

3. **历史对话**:
   - 历史对话中可能引用了删除的工具
   - **缓解措施**: 只影响新对话，历史对话不受影响

### 5.2 回滚计划

如果删除后发现问题：

1. **恢复文件**:
   ```bash
   git checkout HEAD -- src/infrastructure/tools/strategy/create-tool.ts
   git checkout HEAD -- src/infrastructure/tools/strategy/run-tool.ts
   git checkout HEAD -- src/infrastructure/tools/index.ts
   git checkout HEAD -- CLAUDE.md
   ```

2. **重新注册工具**:
   - 在 `index.ts` 中重新导入和注册
   - 在 `CLAUDE.md` 中恢复工具描述

3. **验证回滚**:
   - 运行 `npm run build`
   - 启动 Agent 确认工具恢复

---

## 六、后续优化建议

### 6.1 后端统一

建议在 quantsys-v2 后端统一策略创建接口：

```python
# 统一入口：POST /api/strategies
{
  "action": "create",      # 或 "update"
  "name": "策略名称",
  "code": "策略代码",
  "indicator_id": 123     # 可选，传则更新
}
```

### 6.2 技术指标工具合并

如果后续发现 `stock_cli stock.technical` 和 `analysis_cli analysis.technical` 确实调用相同端点且返回相同数据，可以考虑：

- 删除 `stock_cli stock.technical`
- 只保留 `analysis_cli analysis.technical` 和 `factor_calculate`

### 6.3 工具使用统计

建议启用工具使用统计（已有 `tool_stats_query` 工具），监控：
- 哪些工具使用频率低
- 哪些工具经常出错
- 哪些工具被同时使用（可能重叠）

---

## 七、总结

### 7.1 去重成果

| 类别 | 工具对 | 方案 | 预期效果 |
|------|--------|------|---------|
| 高重叠 | strategy_create ↔ strategy_write | 删除 strategy_create | 减少1个工具 |
| 高重叠 | strategy_execute ↔ strategy_run | 删除 strategy_run | 减少1个工具 |
| 中重叠 | factor_calculate ↔ analysis_cli ↔ stock_cli | 明确分工 | 提升清晰度 |
| 中重叠 | opportunity_scan ↔ stock_cli score | 明确分工 | 提升清晰度 |
| 低重叠 | 其他5组 | 保持现状 | 无变更 |

**总计**: 
- 删除工具数：2
- 明确分工工具数：5
- 工具总数：240 → 238
- 系统提示词 token 减少：约 500 tokens

### 7.2 关键要点

1. **策略创建**: 统一使用 `strategy_write`（支持创建+更新）
2. **策略执行**: 统一使用 `strategy_execute`（支持 single/batch/pipeline）
3. **技术指标**: 明确三层分工（因子研究、完整分析、快速查询）
4. **机会扫描**: 明确两种场景（批量扫描、单股评分）

### 7.3 下一步行动

1. **立即执行**: Phase 1 P0 去重（删除 strategy_create 和 strategy_run）
2. **短期执行**: Phase 2 P1 明确分工（更新工具描述）
3. **长期优化**: 监控工具使用情况，持续优化工具集

---

**文档版本**: v1.0  
**作者**: Claude Code  
**审核**: 待用户确认
