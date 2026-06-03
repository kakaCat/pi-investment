# 智能选股系统测试文档

## 测试目标

验证基于因子有效性的动态权重选股系统：
1. 因子分析 API
2. 动态权重计算
3. 带权重的股票筛选
4. 完整工作流

## 测试环境

- quantsys-v2 服务：http://127.0.0.1:5001
- 测试时间：2026-06-02
- 测试数据：最近6个月因子数据

## Test Case 1: 后端动态权重支持

### 1.1 测试不带权重（默认固定权重）

```bash
curl -X POST http://127.0.0.1:5001/api/signals/scan \
  -H "Content-Type: application/json" \
  -d '{
    "stocks": ["600519", "000858", "601318"],
    "min_score": 0
  }' | jq '.opportunities[] | {symbol, score, technical_score, fundamental_score, capital_score}'
```

**预期结果**：
- 返回3只股票的评分
- 使用固定权重（技术50% + 基本面30% + 资金20%）

### 1.2 测试带自定义权重

```bash
curl -X POST http://127.0.0.1:5001/api/signals/scan \
  -H "Content-Type: application/json" \
  -d '{
    "stocks": ["600519", "000858", "601318"],
    "min_score": 0,
    "weights": {
      "technical": 0.7,
      "fundamental": 0.2,
      "capital": 0.1
    }
  }' | jq '.opportunities[] | {symbol, score, technical_score, fundamental_score, capital_score}'
```

**预期结果**：
- 综合评分 = 技术评分×0.7 + 基本面评分×0.2 + 资金评分×0.1
- 与 1.1 相比，综合评分应有差异（偏向技术面）

### 1.3 测试权重归一化

```bash
curl -X POST http://127.0.0.1:5001/api/signals/scan \
  -H "Content-Type: application/json" \
  -d '{
    "stocks": ["600519"],
    "weights": {
      "technical": 2,
      "fundamental": 1,
      "capital": 1
    }
  }' | jq '.opportunities[0].score'
```

**预期结果**：
- 权重自动归一化为 0.5 / 0.25 / 0.25
- 评分计算正确

## Test Case 2: 因子分析 API

### 2.1 分析技术因子

```bash
curl -X POST http://127.0.0.1:5001/api/analysis/factors \
  -H "Content-Type: application/json" \
  -d '{
    "factors": ["rsi", "macd"],
    "start_date": "2025-12-01",
    "end_date": "2026-06-01",
    "universe": ["600519", "000858", "601318"]
  }' | jq '.factors[] | {factor_name, mean_ic, ir, rating}'
```

**预期结果**：
- 返回各因子的 IC、IR、评级
- IR 值合理（一般在 -2 到 2 之间）

### 2.2 分析基本面因子

```bash
curl -X POST http://127.0.0.1:5001/api/analysis/factors \
  -H "Content-Type: application/json" \
  -d '{
    "factors": ["roe", "pe"],
    "start_date": "2025-12-01",
    "end_date": "2026-06-01",
    "universe": ["600519", "000858"]
  }' | jq '.factors'
```

**预期结果**：
- 返回 ROE、PE 因子的有效性分析

## Test Case 3: TypeScript 智能选股工具

### 3.1 完整工作流测试

**在 Agent 中执行**：

```typescript
smart_stock_screener({
  factors: ["rsi", "macd", "roe", "pe"],
  analysis_period: {
    start_date: "2025-12-01",
    end_date: "2026-06-01"
  },
  weight_algorithm: "ir_based",
  screening_params: {
    symbols: ["600519", "000858", "601318", "600036", "000001"],
    min_score: 50,
    limit: 5
  }
})
```

**预期输出**：
```
📊 Step 1: 因子有效性分析
分析期: 2025-12-01 ~ 2026-06-01
因子列表: rsi, macd, roe, pe

✅ 因子分析完成

⚖️ Step 2: 动态权重计算
算法: 基于 IR (Information Ratio) 归一化

计算结果:
- 技术面权重: 45.2%
- 基本面权重: 35.8%
- 资金面权重: 19.0%

📝 对比固定权重（技术50% + 基本面30% + 资金20%）:
- 技术面 ↓ -4.8%
- 基本面 ↑ +5.8%
- 资金面 ↓ -1.0%

🔍 Step 3: 动态权重股票筛选
扫描完成: 5 只股票
评分 ≥ 50: 3 只

📋 筛选结果 (Top 3)

1. **贵州茅台** (600519)
   综合评分: 82 | 风险: low
   技术: 85 | 基本面: 80 | 资金: 75
   行业: 食品饮料

2. **招商银行** (600036)
   综合评分: 76 | 风险: low
   技术: 70 | 基本面: 85 | 资金: 72
   行业: 银行

3. **五粮液** (000858)
   综合评分: 71 | 风险: medium
   技术: 75 | 基本面: 68 | 资金: 65
   行业: 食品饮料
```

### 3.2 测试默认参数

```typescript
smart_stock_screener({})
```

**预期行为**：
- 使用默认因子列表 ['rsi', 'macd', 'roe', 'pe']
- 分析最近6个月数据
- 扫描热门股票池
- 返回 Top 20

### 3.3 测试因子分析失败场景

**模拟场景**：后端服务不可用

**预期行为**：
- 显示因子分析失败提示
- 自动降级为固定权重
- 继续完成筛选

## Test Case 4: 权重计算算法验证

### 4.1 IR-based 算法

**输入**：
```
技术因子: RSI(IR=1.2), MACD(IR=0.8)  → 平均 IR = 1.0
基本面因子: ROE(IR=0.6), PE(IR=0.4)  → 平均 IR = 0.5
资金因子: 固定 IR = 0.2
```

**预期输出**：
```
技术权重 = 1.0 / (1.0 + 0.5 + 0.2) = 0.588 (58.8%)
基本面权重 = 0.5 / 1.7 = 0.294 (29.4%)
资金权重 = 0.2 / 1.7 = 0.118 (11.8%)
```

### 4.2 Rating-based 算法

**输入**：
```
技术因子: RSI(A), MACD(B)  → 平均权重 = (0.4 + 0.3) / 2 = 0.35
基本面因子: ROE(B), PE(C)  → 平均权重 = (0.3 + 0.2) / 2 = 0.25
资金因子: 固定 0.2
```

**预期输出**：
```
技术权重 = 0.35 / 0.8 = 0.438 (43.8%)
基本面权重 = 0.25 / 0.8 = 0.313 (31.3%)
资金权重 = 0.2 / 0.8 = 0.25 (25.0%)
```

## Test Case 5: 性能测试

### 5.1 小规模（10只股票）

```typescript
smart_stock_screener({
  screening_params: {
    symbols: ["600519", "000858", "601318", "600036", "000001", 
              "600276", "000002", "601166", "600887", "600000"]
  }
})
```

**预期耗时**：< 10秒

### 5.2 中等规模（50只股票）

```typescript
smart_stock_screener({
  screening_params: {
    limit: 50
  }
})
```

**预期耗时**：< 30秒

## Test Case 6: 边界条件测试

### 6.1 零权重

```bash
curl -X POST http://127.0.0.1:5001/api/signals/scan \
  -H "Content-Type: application/json" \
  -d '{
    "stocks": ["600519"],
    "weights": {
      "technical": 0,
      "fundamental": 0,
      "capital": 0
    }
  }'
```

**预期行为**：
- 检测到权重和为0
- 降级为默认固定权重

### 6.2 负 IR 值

**输入**：某因子 IR = -0.5（失效因子）

**预期行为**：
- 使用最小权重 0.1 代替负值
- 权重计算继续

### 6.3 空因子列表

```typescript
smart_stock_screener({
  factors: []
})
```

**预期行为**：
- 使用默认因子列表

## 验收标准

- ✅ 后端支持 weights 参数
- ✅ 权重归一化正确
- ✅ 因子分析 API 可用
- ✅ TypeScript 工具集成完整流程
- ✅ 权重计算算法准确
- ✅ 性能满足要求（< 30秒）
- ✅ 边界条件处理正确

## 已知问题

1. **因子分析数据稀疏**：某些股票可能缺少基本面因子数据
2. **IR 不稳定**：短期数据（< 3个月）IR 波动较大
3. **资金面因子缺失**：暂无资金面因子的单独分析

## 后续优化

1. 增加因子分析缓存（TTL=1天）
2. 支持市场风格检测（价值/成长/周期）
3. 支持因子动态入选（低评级因子自动排除）
4. 支持机器学习权重优化
