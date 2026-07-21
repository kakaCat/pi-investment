# 评分引擎文档

## 概述

评分引擎是机会雷达系统的核心组件，负责对股票进行多维度的量化评分。采用独立评分器架构，支持技术面、基本面、资金面等多个维度的评分。

## 架构设计

### 核心组件

```
services/scoring/
├── base_scorer.py           # 抽象基类，定义评分器接口
├── technical_scorer.py      # 技术面评分器
├── fundamental_scorer.py    # 基本面评分器 ⭐ 新增
└── README.md               # 本文档
```

### 设计原则

1. **独立性**: 每个评分器独立实现，互不依赖
2. **可扩展**: 基于 `BaseScorer` 抽象基类，易于扩展新的评分器
3. **灰度化**: 所有评分采用 0-100 连续分数，而非二元判断
4. **可解释**: 评分结果包含详细的分项明细

---

## 评分器详解

### 1. TechnicalScorer（技术面评分器）

**评分范围**: 0-100  
**基础分**: 50

#### 评分维度

| 维度 | 权重 | 说明 |
|------|------|------|
| RSI | ±20分 | 超卖超买评估 |
| MACD | ±20分 | 趋势和动能评估 |
| ADX | 0-15分 | 趋势强度确认 |
| 成交量 | ±20分 | 资金活跃度 |
| 共振加成 | 0-15分 | 多指标协同 |

#### 使用示例

```python
from services.scoring.technical_scorer import TechnicalScorer

scorer = TechnicalScorer()
factors = {
    'rsi': 25,
    'macd': 0.5,
    'macd_signal': 0.3,
    'adx': 30,
    'volume_ratio_5d': 1.8
}
result = scorer.score(factors)
```

---

### 2. FundamentalScorer（基本面评分器）⭐ 新增

**评分范围**: 0-100  
**基础分**: 50

#### 评分维度

| 维度 | 权重 | 说明 |
|------|------|------|
| PE（市盈率） | ±20分 | 估值水平评估 |
| ROE（净资产收益率） | ±20分 | 盈利能力评估 |
| 毛利率 | 0-15分 | 经营质量评估 |
| 负债率 | 0-15分 | 财务健康度评估 |
| 营收增长率 | 0-15分 | 成长性评估 |
| 财务共振 | 0-15分 | 多指标协同 |

#### 使用示例

```python
from services.scoring.fundamental_scorer import FundamentalScorer

scorer = FundamentalScorer()
fundamental = {
    'pe': 15,
    'roe': 18,
    'gross_margin': 30,
    'debt_ratio': 35,
    'revenue_growth': 20
}
result = scorer.score(fundamental)
```

---

## 集成使用

评分器已集成到 `OpportunityScoringService` 中：

```python
from services.opportunity_scoring_service import OpportunityScoringService

service = OpportunityScoringService(kline_repo, stock_repo, factor_adapter)

# 技术面评分器
tech_result = service.technical_scorer.score(factors)

# 基本面评分器
fund_result = service.fundamental_scorer.score(fundamental)
```

---

## 测试

### 运行所有评分器测试

```bash
pytest tests/services/scoring/ -v
```

### 测试覆盖率

- **TechnicalScorer**: 15 个测试，100% 通过
- **FundamentalScorer**: 18 个测试，100% 通过 ⭐ 新增
- **集成测试**: 3 个测试，100% 通过

---

## 版本历史

### v2.0 (2026-06-05) ⭐ 当前版本
- ✅ 新增 FundamentalScorer（基本面评分器）
- ✅ 18 个单元测试，100% 通过
- ✅ 集成到 OpportunityScoringService

### v1.0 (2026-06-04)
- ✅ 实现 TechnicalScorer（技术面评分器）
- ✅ 15 个单元测试，100% 通过

---

**更新时间**: 2026-06-05  
**维护者**: Kiro AI
