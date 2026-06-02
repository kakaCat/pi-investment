# Opportunity Scan 评分引擎修复报告

**日期**: 2026-06-02  
**优先级**: 🔴 P0  
**状态**: ✅ 已修复并验证

## 问题描述

### 现象
- 334个机会全部显示 `technical_score=50`, `fundamental_score=50`
- 仅 `capital_score` 有变化（100/75/50/25/0 五档）
- 评分完全基于资金面一个维度，技术面和基本面评分失效

### 影响
- 机会扫描结果不可信
- 投资决策依据不完整
- 用户体验严重下降

## 根本原因

**位置**: `quantsys-v2/services/opportunity_scoring_service.py`

**问题代码**:
```python
def _calculate_technical_score(self, factors: Dict, conditions: List[str]) -> float:
    # 如果没有指定条件，返回中性评分
    if not conditions:
        return 50.0  # ❌ 固定返回默认值
    ...

def _calculate_fundamental_score(self, fundamental: Optional[Dict], conditions: List[str]) -> float:
    # 如果没有基本面数据或没有指定条件，返回中性评分
    if not fundamental or not conditions:
        return 50.0  # ❌ 固定返回默认值
    ...
```

**原因分析**:
1. API 端点 `/api/signals/scan` 从请求中提取 `technical` 和 `fundamental` 参数
2. 当前端未传入筛选条件时，这两个参数为空列表 `[]`
3. 评分方法检测到空列表，直接返回固定值 50.0
4. 只有 `_calculate_capital_score` 不依赖筛选条件，始终计算实际分数

## 解决方案

### 设计思路
评分引擎应该**始终计算实际评分**，而不是根据是否有筛选条件来决定是否计算。筛选条件用于过滤，评分用于排序，两者应解耦。

### 实现方案

#### 1. 修改技术面评分方法
```python
def _calculate_technical_score(self, factors: Dict, conditions: List[str]) -> float:
    # 如果没有指定条件，使用默认评分逻辑计算实际分数
    if not conditions:
        return self._calculate_default_technical_score(factors)
    ...
```

#### 2. 修改基本面评分方法
```python
def _calculate_fundamental_score(self, fundamental: Optional[Dict], conditions: List[str]) -> float:
    # 如果没有基本面数据，返回中性评分
    if not fundamental:
        return 50.0
    
    # 如果没有指定条件，使用默认评分逻辑计算实际分数
    if not conditions:
        return self._calculate_default_fundamental_score(fundamental)
    ...
```

#### 3. 实现默认技术面评分
```python
def _calculate_default_technical_score(self, factors: Dict) -> float:
    """综合评估RSI、MACD、布林带、成交量等指标"""
    score = 50.0  # 基础分
    
    # RSI 评分 (±15分)
    if rsi < 30: score += 15       # 超卖
    elif rsi > 70: score -= 15     # 超买
    elif 40 <= rsi <= 60: score += 5  # 中性
    
    # MACD 评分 (±10分)
    if 金叉: score += 10
    elif MACD < 信号线: score -= 10
    
    # 布林带评分 (±10分)
    if 突破上轨: score += 10
    elif 远离上轨: score -= 5
    
    # 成交量评分 (±15分)
    if 放量 > 1.5: score += 15
    elif 缩量 < 0.8: score -= 10
    
    return max(0, min(100, score))
```

#### 4. 实现默认基本面评分
```python
def _calculate_default_fundamental_score(self, fundamental: Dict) -> float:
    """综合评估PE、ROE、毛利率、负债率等指标"""
    score = 50.0  # 基础分
    
    # PE 评分 (±15分)
    if pe < 15: score += 15        # 低估
    elif pe < 30: score += 8       # 合理
    elif pe > 50: score -= 15      # 高估
    
    # ROE 评分 (±15分)
    if roe > 20: score += 15       # 优秀
    elif roe > 15: score += 10     # 良好
    elif roe > 10: score += 5      # 一般
    elif roe < 5: score -= 10      # 较差
    
    # 毛利率评分 (±10分)
    if gross_margin > 40: score += 10
    elif gross_margin > 30: score += 5
    elif gross_margin < 20: score -= 10
    
    # 负债率评分 (±10分)
    if debt_ratio < 30: score += 10
    elif debt_ratio < 50: score += 5
    elif debt_ratio > 70: score -= 10
    
    return max(0, min(100, score))
```

## 验证结果

### 修复前
```
技术面评分: 全部 50
基本面评分: 全部 50
资金面评分: 100/75/50/25/0 五档
```

### 修复后
```
总样本数: 334只

技术面评分分布:
  最小=25, 最大=85, 平均=45.7
  85分: 1只
  75分: 5只
  70分: 6只
  65分: 22只
  60分: 28只
  ... (多样化分布)

基本面评分分布:
  最小=20, 最大=80, 平均=42.4
  80分: 1只
  75分: 5只
  70分: 23只
  65分: 8只
  60分: 37只
  ... (多样化分布)

资金面评分分布:
  最小=0, 最大=100, 平均=43.7
  100分: 5只
  75分: 76只
  50分: 144只
  25分: 48只
  0分: 61只
```

### 验证样本
```
1. 600809 山西汾酒
   综合分: 72, 技术面: 70, 基本面: 75, 资金面: 75

2. 000895 双汇发展
   综合分: 71, 技术面: 85, 基本面: 45, 资金面: 75

3. 000999 华润三九
   综合分: 69, 技术面: 75, 基本面: 55, 资金面: 75
```

## 修改文件

- `quantsys-v2/services/opportunity_scoring_service.py`
  - 修改 `_calculate_technical_score()` 方法
  - 修改 `_calculate_fundamental_score()` 方法
  - 新增 `_calculate_default_technical_score()` 方法
  - 新增 `_calculate_default_fundamental_score()` 方法

## 影响范围

### API 端点
- `POST /api/signals/scan` - 机会雷达扫描

### Agent 工具
- `invest_opportunity_scan` - 投资机会扫描工具

### 前端组件
- Opportunity Radar 组件

## 测试建议

### 1. 单元测试
```python
def test_default_technical_score():
    """测试无筛选条件时的技术面评分"""
    factors = {
        'rsi': 25,  # 超卖
        'macd': 0.5,
        'macd_signal': 0.3,
        'volume_ratio_5d': 2.0  # 放量
    }
    score = service._calculate_default_technical_score(factors)
    assert score > 50  # 应该高于基础分

def test_default_fundamental_score():
    """测试无筛选条件时的基本面评分"""
    fundamental = {
        'pe': 12,  # 低估
        'roe': 22,  # 优秀
        'gross_margin': 45,  # 优秀
        'debt_ratio': 25  # 低负债
    }
    score = service._calculate_default_fundamental_score(fundamental)
    assert score > 70  # 优秀指标应该高分
```

### 2. 集成测试
- 调用 `/api/signals/scan` 不传筛选条件，验证评分多样化
- 传入筛选条件，验证筛选逻辑仍然有效

### 3. 回归测试
- 验证带筛选条件的扫描仍然正常工作
- 验证策略扫描模式不受影响

## 经验总结

### 设计原则
1. **评分与筛选解耦**: 评分用于排序，筛选用于过滤，不应混淆
2. **默认行为合理**: 缺少条件时应计算实际值，而非返回魔法数字
3. **渐进式评分**: 基于多个指标的综合评分更准确

### 代码质量
1. **避免魔法数字**: 50.0 的硬编码值掩盖了问题
2. **明确方法职责**: 一个方法应该只做一件事
3. **完善的日志**: 帮助快速定位问题

### 测试覆盖
1. **边界条件**: 测试空列表、None 等边界情况
2. **实际场景**: 使用真实数据验证评分合理性
3. **分布验证**: 检查评分分布是否符合预期

## 后续优化建议

### 1. 评分权重可配置
```python
# 当前是硬编码权重
score = tech * 0.5 + fund * 0.3 + capital * 0.2

# 建议改为可配置
weights = config.get('scoring_weights', {
    'technical': 0.5,
    'fundamental': 0.3,
    'capital': 0.2
})
```

### 2. 更多技术指标
- 添加 KDJ、BOLL 宽度、均线系统等指标
- 考虑趋势强度和波动率

### 3. 基本面增强
- 添加现金流、营收增长率等指标
- 考虑行业对比评分

### 4. 机器学习优化
- 使用历史数据训练评分模型
- 动态调整评分权重

## 参考文档

- CLAUDE.md - Opportunity Radar Feature 章节
- `quantsys-v2/services/opportunity_scoring_service.py` - 评分引擎实现
- `quantsys-v2/api/routes/signals.py` - API 端点实现
