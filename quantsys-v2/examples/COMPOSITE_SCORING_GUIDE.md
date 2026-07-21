# 综合评分使用指南

## 概述

综合评分系统整合了技术面评分器（TechnicalScorer）和基本面评分器（FundamentalScorer），提供多维度、多策略的股票评估能力。

---

## 快速开始

### 运行示例

```bash
cd quantsys-v2
python examples/composite_scoring_demo.py
```

示例展示了4个典型场景：
1. 技术面+基本面双优（强烈推荐）
2. 技术面强+基本面弱（短线机会）
3. 基本面强+技术面弱（长线价值）
4. 双重疲弱（建议回避）

---

## 使用方法

### 1. 基本使用

```python
from services.scoring.technical_scorer import TechnicalScorer
from services.scoring.fundamental_scorer import FundamentalScorer

# 初始化评分器
tech_scorer = TechnicalScorer()
fund_scorer = FundamentalScorer()

# 技术面评分
technical_factors = {
    'rsi': 28,
    'macd': 0.5,
    'macd_signal': 0.3,
    'adx': 35,
    'volume_ratio_5d': 2.0
}
tech_result = tech_scorer.score(technical_factors)

# 基本面评分
fundamental_data = {
    'pe': 12,
    'roe': 22,
    'gross_margin': 38,
    'debt_ratio': 25,
    'revenue_growth': 28
}
fund_result = fund_scorer.score(fundamental_data)

# 综合评分（简单平均）
composite_score = (tech_result['total'] + fund_result['total']) / 2
```

### 2. 使用 CompositeScorer（推荐）

```python
from examples.composite_scoring_demo import CompositeScorer

scorer = CompositeScorer()

result = scorer.score(
    technical_factors=technical_factors,
    fundamental_data=fundamental_data,
    strategy='balanced'  # 选择策略
)

print(f"综合评分: {result['composite_score']:.2f}")
print(f"评级: {result['rating']}")
print(f"建议: {result['recommendation']}")
```

---

## 评分策略

### 策略类型

| 策略 | 技术面权重 | 基本面权重 | 适用场景 |
|------|-----------|-----------|---------|
| **balanced** | 50% | 50% | 平衡策略，适合大多数情况 |
| **technical_focus** | 70% | 30% | 技术面为主，适合短线交易 |
| **fundamental_focus** | 30% | 70% | 基本面为主，适合长线投资 |
| **aggressive** | 80% | 20% | 激进策略，适合波段操作 |
| **conservative** | 20% | 80% | 保守策略，适合价值投资 |

### 策略选择建议

**根据投资风格**:
- 短线交易者 → `technical_focus` 或 `aggressive`
- 中线交易者 → `balanced`
- 长线投资者 → `fundamental_focus` 或 `conservative`
- 价值投资者 → `conservative`

**根据市场环境**:
- 牛市/强势市场 → `technical_focus`（捕捉趋势）
- 熊市/弱势市场 → `fundamental_focus`（寻找价值）
- 震荡市场 → `balanced`（均衡配置）

---

## 评分解读

### 评级体系

| 分数范围 | 评级 | 含义 | 建议 |
|---------|------|------|------|
| 85-100 | A+（强烈推荐） | 双重优秀 | 重点关注 |
| 75-84 | A（推荐） | 优秀 | 积极关注 |
| 65-74 | B+（较好） | 较好 | 可以关注 |
| 55-64 | B（中性） | 中性 | 谨慎关注 |
| 45-54 | C（观望） | 一般 | 观望为主 |
| 0-44 | D（回避） | 较差 | 建议回避 |

### 协同性分析

综合评分不仅看分数，还要看技术面和基本面的协同性：

**高度协同**（分差 ≤ 10分）:
- 双重确认，可信度高
- 示例：技术面90分，基本面85分

**较为协同**（分差 10-20分）:
- 基本一致，可接受
- 示例：技术面80分，基本面65分

**不协同**（分差 > 20分）:
- 需要警惕风险
- 技术面强 → 注意基本面风险
- 基本面强 → 等待技术面确认

---

## 实战案例

### 案例 1: 双重优秀（满分案例）

**场景**: 技术面和基本面都非常优秀

**数据**:
```python
technical = {
    'rsi': 28,              # 超卖，底部反转
    'macd': 金叉,           # 趋势转强
    'adx': 35,              # 强趋势
    'volume_ratio_5d': 2.0  # 放量
}

fundamental = {
    'pe': 12,               # 低估
    'roe': 22,              # 高盈利
    'gross_margin': 38,     # 高毛利
    'debt_ratio': 25,       # 低负债
    'revenue_growth': 28    # 高增长
}
```

**评分结果**:
- 技术面: 100分
- 基本面: 100分
- 综合评分: 100分（任何策略）
- 评级: A+（强烈推荐）

**投资建议**: 
- 短线、中线、长线都适合
- 技术面和基本面高度协同
- 强烈建议关注

---

### 案例 2: 技术面强+基本面弱（短线机会）

**场景**: 技术面出现强烈买入信号，但基本面一般

**数据**:
```python
technical = {
    'rsi': 25,
    'macd': 强势金叉,
    'adx': 40,
    'volume_ratio_5d': 2.5
}

fundamental = {
    'pe': 35,               # 略高估
    'roe': 8,               # 一般
    'gross_margin': 18,     # 一般
    'debt_ratio': 55,       # 中等
    'revenue_growth': 5     # 低增长
}
```

**评分结果（不同策略）**:
- `technical_focus`: 91.17分（A+）
- `balanced`: 85.29分（A+）
- `fundamental_focus`: 79.41分（A）

**投资建议**:
- 适合短线交易（technical_focus）
- 技术面强于基本面，注意基本面风险
- 建议设置止损，快进快出

---

### 案例 3: 基本面强+技术面弱（长线价值）

**场景**: 基本面优秀，但技术面尚未确认

**数据**:
```python
technical = {
    'rsi': 65,              # 接近超买
    'macd': 死叉,
    'adx': 20,              # 弱趋势
    'volume_ratio_5d': 0.7  # 缩量
}

fundamental = {
    'pe': 10,               # 低估
    'roe': 25,              # 卓越
    'gross_margin': 40,     # 优秀
    'debt_ratio': 20,       # 低负债
    'revenue_growth': 30    # 高增长
}
```

**评分结果（不同策略）**:
- `fundamental_focus`: 77.50分（A）
- `balanced`: 62.50分（B）
- `technical_focus`: 47.50分（C）

**投资建议**:
- 适合长线价值投资（fundamental_focus）
- 基本面强于技术面，等待技术面确认
- 可以分批建仓，逐步布局

---

### 案例 4: 双重疲弱（回避）

**场景**: 技术面和基本面都不佳

**评分结果**:
- 技术面: 21.67分
- 基本面: 30.00分
- 综合评分: 25.84分
- 评级: D（回避）

**投资建议**: 
- 建议回避
- 双重风险信号

---

## 高级用法

### 1. 自定义权重

```python
# 自定义权重配比
tech_weight = 0.6
fund_weight = 0.4

composite_score = (
    tech_result['total'] * tech_weight +
    fund_result['total'] * fund_weight
)
```

### 2. 分项分析

```python
result = scorer.score(technical_factors, fundamental_data, 'balanced')

# 查看技术面各维度贡献
tech_breakdown = result['breakdown']['technical']['details']
print(f"RSI贡献: {tech_breakdown['rsi']:.2f}")
print(f"MACD贡献: {tech_breakdown['macd']:.2f}")

# 查看基本面各维度贡献
fund_breakdown = result['breakdown']['fundamental']['details']
print(f"PE贡献: {fund_breakdown['pe']:.2f}")
print(f"ROE贡献: {fund_breakdown['roe']:.2f}")
```

### 3. 批量评分

```python
stocks_to_evaluate = [
    {'symbol': '000001.SZ', 'technical': {...}, 'fundamental': {...}},
    {'symbol': '600000.SH', 'technical': {...}, 'fundamental': {...}},
    # ...
]

scorer = CompositeScorer()
results = []

for stock in stocks_to_evaluate:
    result = scorer.score(
        stock['technical'],
        stock['fundamental'],
        strategy='balanced'
    )
    results.append({
        'symbol': stock['symbol'],
        'score': result['composite_score'],
        'rating': result['rating']
    })

# 按评分排序
results.sort(key=lambda x: x['score'], reverse=True)
```

---

## 注意事项

### 1. 数据质量

- 确保技术指标数据完整（RSI、MACD、ADX、成交量）
- 确保基本面数据及时（最新季报/年报）
- 缺失数据会影响评分准确性

### 2. 策略选择

- 不同策略适用于不同场景
- 建议根据投资风格固定使用1-2个策略
- 避免频繁切换策略

### 3. 协同性重要

- 技术面和基本面协同时，信号更可靠
- 分歧较大时，需要谨慎对待
- 建议优先关注高度协同的股票

### 4. 风险控制

- 综合评分只是参考，不是买卖依据
- 需要结合市场环境、仓位管理
- 建议设置止损，控制风险

---

## 常见问题

### Q1: 技术面和基本面分数相差很大怎么办？

**A**: 分析原因并采取相应策略：
- 技术面强+基本面弱 → 适合短线，注意风险
- 基本面强+技术面弱 → 适合长线，等待时机
- 建议避免分差过大（>30分）的股票

### Q2: 所有策略评分都很低怎么办？

**A**: 说明该股票技术面和基本面都不佳，建议回避。

### Q3: 如何选择合适的策略？

**A**: 
1. 根据投资风格（短线/中线/长线）
2. 根据市场环境（牛市/熊市/震荡）
3. 建议先用 `balanced`，再根据实际情况调整

### Q4: 评分高就一定要买吗？

**A**: 不是。评分只是量化参考，还需要考虑：
- 市场整体环境
- 个人仓位管理
- 风险承受能力
- 其他定性因素

---

## 相关文档

- **TechnicalScorer**: `services/scoring/technical_scorer.py`
- **FundamentalScorer**: `services/scoring/fundamental_scorer.py`
- **评分引擎文档**: `services/scoring/README.md`
- **示例代码**: `examples/composite_scoring_demo.py`

---

**更新时间**: 2026-06-05  
**版本**: v2.0
