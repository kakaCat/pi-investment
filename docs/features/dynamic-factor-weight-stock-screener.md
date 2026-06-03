# 动态因子权重智能选股系统

## 概述

基于因子有效性分析（IC/IR）动态调整权重，构建高质量股票池。

## 当前问题

`OpportunityScoringService` 使用**固定权重**：
```python
# 硬编码权重
综合评分 = 技术面×0.5 + 基本面×0.3 + 资金面×0.2
```

**问题**：
- 忽略市场环境变化（牛市、熊市、震荡市）
- 忽略因子有效性差异（某些因子在特定时期失效）
- 无法根据历史表现优化权重

## 解决方案

### 核心流程

```
1. 因子有效性分析 (factor_analyze)
   ↓ 返回 IC、IR、评级
2. 权重计算算法
   ↓ 根据 IC/IR 动态分配权重
3. 动态权重筛选 (opportunity_scan)
   ↓ 使用计算出的权重
4. 股票池构建 (pool_manage)
   ↓ 保存筛选结果
```

### 权重计算算法

#### 方案 A：基于 IR 归一化（推荐）

**公式**：
```
weight_i = IR_i / sum(IR_j)
```

**特点**：
- 简单有效
- IR 高的因子权重大
- 自动归一化（权重和=1）

**示例**：
```python
技术面 IR = 1.2
基本面 IR = 0.8
资金面 IR = 0.4
总 IR = 2.4

技术面权重 = 1.2 / 2.4 = 0.50
基本面权重 = 0.8 / 2.4 = 0.33
资金面权重 = 0.4 / 2.4 = 0.17
```

#### 方案 B：基于评级映射

| 评级 | 基础权重 |
|------|---------|
| A    | 0.40    |
| B    | 0.30    |
| C    | 0.20    |
| D    | 0.10    |

归一化后使用。

#### 方案 C：组合算法（IR + IC）

```python
score_i = IR_i * 0.7 + IC_i * 0.3
weight_i = score_i / sum(score_j)
```

### 实现步骤

#### Phase 1: 后端增强

1. **修改 OpportunityScoringService**
   - 添加 `weights` 参数到 `score_stocks()`
   - 修改 `_calculate_comprehensive_score()` 支持动态权重
   - 默认保持固定权重（向后兼容）

2. **修改 API 端点**
   - `/api/signals/scan` 接受 `weights` 参数
   ```json
   {
     "symbols": [...],
     "filters": {...},
     "weights": {
       "technical": 0.5,
       "fundamental": 0.3,
       "capital": 0.2
     }
   }
   ```

#### Phase 2: 因子分析 API

1. **新增端点 `/api/factors/analyze`**
   - 接受因子列表和时间范围
   - 返回 IC/IR/评级

2. **或复用现有端点**
   - 检查 `/api/analysis/factors` 是否已实现

#### Phase 3: TypeScript 工具

1. **创建 `smart_stock_screener` 工具**
   - 封装完整流程
   - 支持自定义因子列表
   - 支持权重算法选择

#### Phase 4: 工作流示例

```typescript
// 1. 分析因子有效性
const factorAnalysis = await factor_analyze({
  factors: ['rsi', 'macd', 'roe', 'pe'],
  start_date: '2024-01-01',
  end_date: '2024-12-31'
});

// 2. 计算动态权重
const weights = calculateWeightsFromAnalysis(factorAnalysis);

// 3. 动态权重筛选
const opportunities = await opportunity_scan({
  symbols: [...],
  weights: weights
});

// 4. 创建股票池
await pool_manage({
  action: 'create',
  name: '高质量池',
  stocks: opportunities.map(o => o.symbol)
});
```

## 关键优势

1. **自适应**：根据市场环境自动调整
2. **数据驱动**：基于历史表现而非主观判断
3. **可解释**：权重来源于量化指标（IC/IR）
4. **灵活**：支持多种权重算法

## 性能指标

- 因子分析：< 30s（1年数据，400只股票）
- 权重计算：< 1s
- 股票筛选：< 5s（400只股票）
- 总耗时：< 40s

## 测试策略

1. **单元测试**
   - 权重计算算法
   - 边界条件（IR=0、负IR）

2. **集成测试**
   - 完整流程测试
   - 对比固定权重 vs 动态权重

3. **回测验证**
   - 历史数据验证
   - 收益率对比

## 风险考虑

1. **过拟合**：短期数据可能导致权重不稳定
   - 解决：使用足够长的分析期（≥6个月）
   
2. **因子失效**：历史表现不代表未来
   - 解决：定期重新分析，设置权重上下限

3. **计算开销**：每次筛选前都分析因子？
   - 解决：缓存因子分析结果（TTL=1天）

## 扩展方向

1. **市场风格检测**：根据市场风格（价值/成长/周期）自动选择因子
2. **因子动态入选**：低评级因子自动排除
3. **机器学习权重**：使用 ML 模型优化权重组合
4. **行业中性**：分行业计算权重

## 参考文献

- Grinold & Kahn (2000): Active Portfolio Management
- 《量化投资：策略与技术》- 多因子模型章节
