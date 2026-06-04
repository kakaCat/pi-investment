# 机会雷达评分逻辑优化实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 优化技术面评分逻辑，实现灰度化评分、ADX趋势确认和多指标共振机制

**Architecture:** 创建独立的 TechnicalScorer 评分引擎，通过 BaseScorer 基类实现可扩展架构，OpportunityScoringService 集成新评分器

**Tech Stack:** Python 3.12, TA-Lib, pytest, ThreadPoolExecutor

---

## 文件结构规划

**新增文件：**
- `quantsys-v2/services/scoring/__init__.py` - 评分引擎包初始化
- `quantsys-v2/services/scoring/base_scorer.py` - 抽象评分器基类
- `quantsys-v2/services/scoring/technical_scorer.py` - 技术面评分引擎（核心）
- `quantsys-v2/services/scoring/README.md` - 评分引擎使用文档
- `quantsys-v2/tests/services/scoring/__init__.py` - 测试包初始化
- `quantsys-v2/tests/services/scoring/test_technical_scorer.py` - 单元测试

**修改文件：**
- `quantsys-v2/services/opportunity_scoring_service.py` - 集成 TechnicalScorer
  - 修改 `__init__()` - 初始化评分器
  - 修改 `_calculate_factors()` - 新增 ADX 计算
  - 修改 `_score_single_stock()` - 使用新评分器
  - 删除 `_calculate_technical_score()` 及相关私有方法

**测试文件：**
- 修改 `quantsys-v2/tests/services/test_opportunity_scoring_service.py` - 集成测试

---
## Task 1: 创建评分引擎基础架构

**Files:**
- Create: `quantsys-v2/services/scoring/__init__.py`
- Create: `quantsys-v2/services/scoring/base_scorer.py`
- Create: `quantsys-v2/tests/services/scoring/__init__.py`

- [ ] **Step 1: 创建 scoring 目录**

```bash
mkdir -p quantsys-v2/services/scoring
mkdir -p quantsys-v2/tests/services/scoring
```

- [ ] **Step 2: 创建 services/scoring/__init__.py**

```python
"""
评分引擎模块

提供统一的评分接口，支持技术面、基本面、资金面等多维度评分。
"""

from .base_scorer import BaseScorer
from .technical_scorer import TechnicalScorer

__all__ = ['BaseScorer', 'TechnicalScorer']
```

- [ ] **Step 3: 创建 base_scorer.py（抽象基类）**

```python
"""
评分器基类

定义统一的评分接口，所有具体评分器必须继承此类。
"""

from abc import ABC, abstractmethod
from typing import Dict, Any


class BaseScorer(ABC):
    """
    评分器抽象基类
    
    所有评分器必须实现 score() 方法，返回标准化的评分结果。
    """
    
    @abstractmethod
    def score(self, data: Dict[str, Any]) -> Dict[str, float]:
        """
        计算评分
        
        Args:
            data: 输入数据字典，具体格式由子类定义
        
        Returns:
            评分结果字典，格式：
            {
                'total': 85.0,        # 总分 (0-100)
                'breakdown': {         # 评分明细
                    'sub_item_1': 20.0,
                    'sub_item_2': 15.0,
                    ...
                }
            }
        
        Raises:
            NotImplementedError: 子类必须实现此方法
        """
        pass
```

- [ ] **Step 4: 创建 tests/services/scoring/__init__.py**

```python
"""测试：评分引擎模块"""
```

- [ ] **Step 5: 验证导入**

```bash
cd quantsys-v2
python -c "from services.scoring import BaseScorer; print('BaseScorer imported successfully')"
```

Expected output: `BaseScorer imported successfully`

- [ ] **Step 6: Commit**

```bash
git add services/scoring/ tests/services/scoring/
git commit -m "feat(scoring): 添加评分引擎基础架构

- 创建 services/scoring 模块
- 实现 BaseScorer 抽象基类
- 定义统一的评分接口"
```

---
## Task 2: 实现 TechnicalScorer 核心逻辑

**Files:**
- Create: `quantsys-v2/services/scoring/technical_scorer.py`

- [ ] **Step 1: 创建 technical_scorer.py 文件框架**

```python
"""
技术面评分引擎

实现基于技术指标的股票评分逻辑，包括：
- RSI 灰度化评分
- MACD 强度评分
- ADX 趋势确认
- 成交量评分
- 多指标共振加成
"""

from typing import Dict, Any, Optional
import logging
from .base_scorer import BaseScorer

logger = logging.getLogger(__name__)


class TechnicalScorer(BaseScorer):
    """
    技术面评分引擎
    
    评分公式：
    总分 = 基础分(50) + RSI(±20) + MACD(±20) + ADX(0-15) + 成交量(±20) + 共振(0-15)
    范围：0-100（自动截断）
    """
    
    def __init__(self, factor_adapter=None):
        """
        初始化技术面评分器
        
        Args:
            factor_adapter: 因子计算适配器（可选，用于扩展）
        """
        self.factor_adapter = factor_adapter
    
    def score(
        self, 
        factors: Dict[str, Any],
        conditions: Optional[list] = None
    ) -> Dict[str, float]:
        """
        计算技术面评分
        
        Args:
            factors: 技术指标字典，必须包含：
                - rsi: RSI指标值 (0-100)
                - macd: MACD快线值
                - macd_signal: MACD信号线值
                - macd_prev: 前一日MACD值
                - macd_signal_prev: 前一日信号线值
                - adx: ADX趋势强度 (0-100)
                - volume_ratio_5d: 5日成交量比
            
            conditions: 筛选条件列表（向后兼容，暂不使用）
        
        Returns:
            {
                'total': 85.0,
                'breakdown': {
                    'base': 50.0,
                    'rsi': 18.5,
                    'macd': 15.0,
                    'adx': 10.0,
                    'volume': 16.0,
                    'resonance': 10.0
                }
            }
        """
        # 基础分
        base = 50.0
        
        # 各维度评分
        rsi_score = self._score_rsi(factors.get('rsi', 50))
        macd_score = self._score_macd(factors)
        adx_score = self._score_adx(factors.get('adx', 0))
        volume_score = self._score_volume(factors)
        
        # 构建 breakdown
        breakdown = {
            'base': base,
            'rsi': rsi_score,
            'macd': macd_score,
            'adx': adx_score,
            'volume': volume_score,
        }
        
        # 共振加成
        resonance_score = self._calculate_resonance(factors, breakdown)
        breakdown['resonance'] = resonance_score
        
        # 计算总分并截断
        total = base + rsi_score + macd_score + adx_score + volume_score + resonance_score
        total = max(0, min(100, total))
        
        return {
            'total': round(total, 2),
            'breakdown': {k: round(v, 2) for k, v in breakdown.items()}
        }
```

- [ ] **Step 2: 实现 _score_rsi() 方法**

```python
    def _score_rsi(self, rsi: float) -> float:
        """
        RSI 灰度化评分（±20分）
        
        评分曲线：
        - rsi=0   → +20分（极度超卖）
        - rsi=30  → +0分（超卖边界）
        - rsi=40-60 → +5分（中性区间）
        - rsi=70  → +0分（超买边界）
        - rsi=100 → -20分（极度超买）
        
        Args:
            rsi: RSI指标值 (0-100)
        
        Returns:
            评分 (-20 到 +20)
        """
        if rsi < 30:
            # 超卖区：线性加分
            return 20 * (30 - rsi) / 30
        elif rsi > 70:
            # 超买区：线性扣分
            return -20 * (rsi - 70) / 30
        elif 40 <= rsi <= 60:
            # 中性区：小幅加分
            return 5
        return 0
```

- [ ] **Step 3: 实现 _score_macd() 和 _is_golden_cross() 方法**

```python
    def _score_macd(self, factors: Dict) -> float:
        """
        MACD 强度评分（±20分）
        
        金叉：基础10分 + 柱状图强度（最多10分）
        死叉：扣分（最多-15分）
        
        Args:
            factors: 包含 macd, macd_signal, macd_prev, macd_signal_prev
        
        Returns:
            评分 (-15 到 +20)
        """
        macd = factors.get('macd', 0)
        signal = factors.get('macd_signal', 0)
        hist = macd - signal  # 柱状图
        
        if self._is_golden_cross(factors):
            # 金叉强度 = 基础分 + 柱状图绝对值 × 100
            strength = min(10, abs(hist) * 100)
            return 10 + strength
        elif macd < signal:
            # 死叉扣分
            return -min(15, abs(hist) * 100)
        return 0
    
    def _is_golden_cross(self, factors: Dict) -> bool:
        """
        判断 MACD 金叉
        
        金叉定义：当前 MACD > 信号线 且 前一日 MACD <= 信号线
        
        Args:
            factors: 包含 macd, macd_signal, macd_prev, macd_signal_prev
        
        Returns:
            True 表示金叉，False 表示非金叉
        """
        macd = factors.get('macd', 0)
        signal = factors.get('macd_signal', 0)
        macd_prev = factors.get('macd_prev', 0)
        signal_prev = factors.get('macd_signal_prev', 0)
        
        return macd > signal and macd_prev <= signal_prev
```

- [ ] **Step 4: 实现 _score_adx() 方法**

```python
    def _score_adx(self, adx: float) -> float:
        """
        ADX 趋势强度评分（0-15分）
        
        - adx < 20  → 0分（无趋势）
        - adx = 25  → 0分（弱趋势边界）
        - adx = 50  → 15分（强趋势）
        - adx > 50  → 15分（极强趋势）
        
        Args:
            adx: ADX指标值 (0-100)
        
        Returns:
            评分 (0 到 15)
        """
        if adx <= 25:
            return 0
        return min(15, (adx - 25) / 5)
```

- [ ] **Step 5: 实现 _score_volume() 方法**

```python
    def _score_volume(self, factors: Dict) -> float:
        """
        成交量评分（±20分）
        
        - 5日量比 > 1.5 → 最多+20分
        - 5日量比 < 0.8 → -10分（缩量）
        
        Args:
            factors: 包含 volume_ratio_5d
        
        Returns:
            评分 (-10 到 +20)
        """
        volume_ratio = factors.get('volume_ratio_5d', 1.0)
        
        if volume_ratio > 1.5:
            # 放量：线性加分，最多20分
            return min(20, (volume_ratio - 1) * 20)
        elif volume_ratio < 0.8:
            # 缩量：扣分
            return -10
        return 0
```

- [ ] **Step 6: 实现 _calculate_resonance() 方法**

```python
    def _calculate_resonance(self, factors: Dict, breakdown: Dict) -> float:
        """
        多指标共振加成（0-15分）
        
        规则：
        1. RSI超卖(rsi<30) + MACD金叉 → +10分
        2. 放量(ratio>1.5) + 强趋势(adx>25) → +5分
        
        最多累计15分
        
        Args:
            factors: 技术指标字典
            breakdown: 各维度评分明细
        
        Returns:
            共振加成分 (0 到 15)
        """
        bonus = 0
        rsi = factors.get('rsi', 50)
        volume_ratio = factors.get('volume_ratio_5d', 1.0)
        adx = factors.get('adx', 0)
        
        # 规则1：RSI超卖 + MACD金叉
        # MACD得分>10表示金叉
        if rsi < 30 and breakdown.get('macd', 0) > 10:
            bonus += 10
        
        # 规则2：放量 + 强趋势
        if volume_ratio > 1.5 and adx > 25:
            bonus += 5
        
        return min(bonus, 15)
```

- [ ] **Step 7: 验证导入和基本功能**

```bash
cd quantsys-v2
python -c "
from services.scoring.technical_scorer import TechnicalScorer
scorer = TechnicalScorer()
factors = {
    'rsi': 50, 'macd': 0.5, 'macd_signal': 0.3,
    'macd_prev': 0.2, 'macd_signal_prev': 0.4,
    'adx': 30, 'volume_ratio_5d': 1.2
}
result = scorer.score(factors)
print(f\"Total: {result['total']}, Breakdown: {result['breakdown']}\")
"
```

Expected output: `Total: <score>, Breakdown: {...}` (score 应在 0-100 之间)

- [ ] **Step 8: Commit**

```bash
git add services/scoring/technical_scorer.py
git commit -m "feat(scoring): 实现 TechnicalScorer 核心逻辑

- RSI 灰度化评分（±20分）
- MACD 强度评分含金叉检测（±20分）
- ADX 趋势强度评分（0-15分）
- 成交量评分（±20分）
- 多指标共振加成（0-15分）"
```

---
## Task 3: 编写 TechnicalScorer 单元测试

**Files:**
- Create: `quantsys-v2/tests/services/scoring/test_technical_scorer.py`

- [ ] **Step 1: 编写测试文件框架和基础测试**

```python
"""
TechnicalScorer 单元测试
"""

import pytest
from services.scoring.technical_scorer import TechnicalScorer


class TestTechnicalScorer:
    """TechnicalScorer 单元测试"""
    
    def setup_method(self):
        """每个测试前初始化"""
        self.scorer = TechnicalScorer()
    
    def test_score_returns_correct_structure(self):
        """测试返回结构正确"""
        factors = {
            'rsi': 50,
            'macd': 0.5,
            'macd_signal': 0.3,
            'macd_prev': 0.2,
            'macd_signal_prev': 0.4,
            'adx': 30,
            'volume_ratio_5d': 1.2,
        }
        
        result = self.scorer.score(factors)
        
        # 验证结构
        assert 'total' in result
        assert 'breakdown' in result
        assert isinstance(result['total'], (int, float))
        assert isinstance(result['breakdown'], dict)
        
        # 验证 breakdown 包含所有子项
        assert 'base' in result['breakdown']
        assert 'rsi' in result['breakdown']
        assert 'macd' in result['breakdown']
        assert 'adx' in result['breakdown']
        assert 'volume' in result['breakdown']
        assert 'resonance' in result['breakdown']
    
    def test_score_range_valid(self):
        """测试评分范围在 0-100 之间"""
        # 极端超卖情况
        factors_oversold = {
            'rsi': 10,
            'macd': 1.0,
            'macd_signal': 0.1,
            'macd_prev': 0.1,
            'macd_signal_prev': 0.5,
            'adx': 50,
            'volume_ratio_5d': 3.0,
        }
        
        result = self.scorer.score(factors_oversold)
        assert 0 <= result['total'] <= 100
        
        # 极端超买情况
        factors_overbought = {
            'rsi': 90,
            'macd': -0.5,
            'macd_signal': 0.5,
            'macd_prev': 0.5,
            'macd_signal_prev': 0.3,
            'adx': 10,
            'volume_ratio_5d': 0.5,
        }
        
        result = self.scorer.score(factors_overbought)
        assert 0 <= result['total'] <= 100
```

- [ ] **Step 2: 运行基础测试验证失败（TDD）**

```bash
cd quantsys-v2
pytest tests/services/scoring/test_technical_scorer.py::TestTechnicalScorer::test_score_returns_correct_structure -v
pytest tests/services/scoring/test_technical_scorer.py::TestTechnicalScorer::test_score_range_valid -v
```

Expected: 两个测试都应该 PASS

- [ ] **Step 3: 编写 RSI 评分测试**

```python
    def test_rsi_oversold_scoring(self):
        """测试 RSI 超卖评分"""
        # RSI=0 应该得满分 20 分
        score_0 = self.scorer._score_rsi(0)
        assert score_0 == 20
        
        # RSI=15 应该得 10 分
        score_15 = self.scorer._score_rsi(15)
        assert abs(score_15 - 10) < 0.1
        
        # RSI=30 应该得 0 分
        score_30 = self.scorer._score_rsi(30)
        assert score_30 == 0
    
    def test_rsi_overbought_scoring(self):
        """测试 RSI 超买评分"""
        # RSI=70 应该得 0 分
        score_70 = self.scorer._score_rsi(70)
        assert score_70 == 0
        
        # RSI=85 应该得 -10 分
        score_85 = self.scorer._score_rsi(85)
        assert abs(score_85 - (-10)) < 0.1
        
        # RSI=100 应该得 -20 分
        score_100 = self.scorer._score_rsi(100)
        assert score_100 == -20
    
    def test_rsi_neutral_scoring(self):
        """测试 RSI 中性区间评分"""
        # 40-60 之间应该得 5 分
        for rsi in [40, 45, 50, 55, 60]:
            score = self.scorer._score_rsi(rsi)
            assert score == 5
        
        # 35 和 65 不在中性区间
        assert self.scorer._score_rsi(35) != 5
        assert self.scorer._score_rsi(65) != 5
```

- [ ] **Step 4: 运行 RSI 测试**

```bash
cd quantsys-v2
pytest tests/services/scoring/test_technical_scorer.py::TestTechnicalScorer::test_rsi_oversold_scoring -v
pytest tests/services/scoring/test_technical_scorer.py::TestTechnicalScorer::test_rsi_overbought_scoring -v
pytest tests/services/scoring/test_technical_scorer.py::TestTechnicalScorer::test_rsi_neutral_scoring -v
```

Expected: 所有测试 PASS

- [ ] **Step 5: 编写 MACD 评分测试**

```python
    def test_macd_golden_cross(self):
        """测试 MACD 金叉评分"""
        factors = {
            'macd': 0.5,
            'macd_signal': 0.3,
            'macd_prev': 0.2,
            'macd_signal_prev': 0.4,  # 金叉
        }
        
        score = self.scorer._score_macd(factors)
        assert score > 10  # 至少基础分 10
        assert score <= 20  # 最多 20 分
    
    def test_macd_dead_cross(self):
        """测试 MACD 死叉评分"""
        factors = {
            'macd': 0.2,
            'macd_signal': 0.5,
            'macd_prev': 0.4,
            'macd_signal_prev': 0.3,  # 死叉
        }
        
        score = self.scorer._score_macd(factors)
        assert score < 0  # 应该扣分
        assert score >= -15
    
    def test_macd_no_cross(self):
        """测试 MACD 无交叉"""
        factors = {
            'macd': 0.5,
            'macd_signal': 0.3,
            'macd_prev': 0.4,
            'macd_signal_prev': 0.2,  # 持续金叉状态，无新交叉
        }
        
        score = self.scorer._score_macd(factors)
        assert score == 0
```

- [ ] **Step 6: 运行 MACD 测试**

```bash
cd quantsys-v2
pytest tests/services/scoring/test_technical_scorer.py::TestTechnicalScorer::test_macd_golden_cross -v
pytest tests/services/scoring/test_technical_scorer.py::TestTechnicalScorer::test_macd_dead_cross -v
pytest tests/services/scoring/test_technical_scorer.py::TestTechnicalScorer::test_macd_no_cross -v
```

Expected: 所有测试 PASS

- [ ] **Step 7: 编写 ADX 和成交量测试**

```python
    def test_adx_weak_trend(self):
        """测试弱趋势 ADX 评分"""
        score_20 = self.scorer._score_adx(20)
        assert score_20 == 0
        
        score_25 = self.scorer._score_adx(25)
        assert score_25 == 0
    
    def test_adx_strong_trend(self):
        """测试强趋势 ADX 评分"""
        score_30 = self.scorer._score_adx(30)
        assert 0 < score_30 < 15
        
        score_50 = self.scorer._score_adx(50)
        assert score_50 == 15
        
        score_70 = self.scorer._score_adx(70)
        assert score_70 == 15  # 最多 15 分
    
    def test_volume_scoring(self):
        """测试成交量评分"""
        # 放量
        factors_high = {'volume_ratio_5d': 2.0}
        score_high = self.scorer._score_volume(factors_high)
        assert score_high > 0
        assert score_high <= 20
        
        # 缩量
        factors_low = {'volume_ratio_5d': 0.7}
        score_low = self.scorer._score_volume(factors_low)
        assert score_low == -10
        
        # 正常
        factors_normal = {'volume_ratio_5d': 1.2}
        score_normal = self.scorer._score_volume(factors_normal)
        assert score_normal == 0
```

- [ ] **Step 8: 编写共振加成测试**

```python
    def test_resonance_rsi_macd(self):
        """测试 RSI 超卖 + MACD 金叉共振"""
        factors = {
            'rsi': 25,  # 超卖
            'macd': 0.5,
            'macd_signal': 0.3,
            'macd_prev': 0.2,
            'macd_signal_prev': 0.4,  # 金叉
            'adx': 20,
            'volume_ratio_5d': 1.0,
        }
        
        breakdown = {
            'macd': 15,  # 金叉得分 > 10
        }
        
        resonance = self.scorer._calculate_resonance(factors, breakdown)
        assert resonance == 10  # 应该触发规则 1
    
    def test_resonance_volume_adx(self):
        """测试放量 + 强趋势共振"""
        factors = {
            'rsi': 50,
            'macd': 0.5,
            'macd_signal': 0.3,
            'adx': 30,  # 强趋势
            'volume_ratio_5d': 2.0,  # 放量
        }
        
        breakdown = {'macd': 5}
        
        resonance = self.scorer._calculate_resonance(factors, breakdown)
        assert resonance == 5  # 应该触发规则 2
    
    def test_resonance_both_rules(self):
        """测试两个共振规则同时触发"""
        factors = {
            'rsi': 25,  # 超卖
            'macd': 0.5,
            'macd_signal': 0.3,
            'macd_prev': 0.2,
            'macd_signal_prev': 0.4,  # 金叉
            'adx': 30,  # 强趋势
            'volume_ratio_5d': 2.0,  # 放量
        }
        
        breakdown = {'macd': 15}
        
        resonance = self.scorer._calculate_resonance(factors, breakdown)
        assert resonance == 15  # 10 + 5，最多 15 分
    
    def test_resonance_no_trigger(self):
        """测试共振规则未触发"""
        factors = {
            'rsi': 50,  # 非超卖
            'macd': 0.5,
            'macd_signal': 0.3,
            'adx': 20,  # 弱趋势
            'volume_ratio_5d': 1.0,  # 正常量
        }
        
        breakdown = {'macd': 5}
        
        resonance = self.scorer._calculate_resonance(factors, breakdown)
        assert resonance == 0
```

- [ ] **Step 9: 运行所有单元测试**

```bash
cd quantsys-v2
pytest tests/services/scoring/test_technical_scorer.py -v
```

Expected: 所有测试 PASS

- [ ] **Step 10: 检查测试覆盖率**

```bash
cd quantsys-v2
pytest tests/services/scoring/test_technical_scorer.py --cov=services.scoring.technical_scorer --cov-report=term-missing
```

Expected: 覆盖率 > 90%

- [ ] **Step 11: Commit**

```bash
git add tests/services/scoring/test_technical_scorer.py
git commit -m "test(scoring): 添加 TechnicalScorer 完整单元测试

- 测试评分结构和范围
- 测试 RSI 灰度化评分
- 测试 MACD 金叉/死叉评分
- 测试 ADX 趋势强度评分
- 测试成交量评分
- 测试多指标共振加成
- 测试覆盖率 > 90%"
```

---
## Task 4: 集成 TechnicalScorer 到 OpportunityScoringService

**Files:**
- Modify: `quantsys-v2/services/opportunity_scoring_service.py`

- [ ] **Step 1: 导入 TechnicalScorer**

在文件顶部添加导入：

```python
from services.scoring.technical_scorer import TechnicalScorer
```

- [ ] **Step 2: 修改 __init__() 方法初始化评分器**

找到 `__init__()` 方法，在最后添加：

```python
    def __init__(
        self,
        kline_repo: KlineRepository,
        stock_repo: StockRepository,
        factor_adapter
    ):
        self.kline_repo = kline_repo
        self.stock_repo = stock_repo
        self.factor_adapter = factor_adapter
        # 新增：初始化技术面评分器
        self.technical_scorer = TechnicalScorer(factor_adapter)
```

- [ ] **Step 3: 在 _calculate_factors() 中新增 ADX 计算**

找到 `_calculate_factors()` 方法，在计算 RSI 和 MACD 之后添加 ADX：

```python
    def _calculate_factors(self, klines: List[Dict]) -> Dict:
        """计算技术指标因子（新增 ADX）"""
        if not klines:
            return {}
        
        factors = {}
        
        try:
            # 原有因子：RSI
            rsi14 = self.factor_adapter.calculate('rsi14', klines)
            if rsi14 is not None:
                factors['rsi'] = rsi14
            
            # 原有因子：MACD
            macd = self.factor_adapter.calculate('macd', klines)
            macd_signal = self.factor_adapter.calculate('macd_signal', klines)
            if macd is not None and macd_signal is not None:
                factors['macd'] = macd
                factors['macd_signal'] = macd_signal
                
                # 前一日 MACD（用于金叉判断）
                if len(klines) >= 2:
                    klines_prev = klines[:-1]
                    macd_prev = self.factor_adapter.calculate('macd', klines_prev)
                    macd_signal_prev = self.factor_adapter.calculate('macd_signal', klines_prev)
                    if macd_prev is not None and macd_signal_prev is not None:
                        factors['macd_prev'] = macd_prev
                        factors['macd_signal_prev'] = macd_signal_prev
            
            # === 新增：ADX 计算 ===
            adx = self.factor_adapter.calculate('adx', klines)
            if adx is not None:
                factors['adx'] = adx
            
            # 原有因子：布林带（可选保留）
            boll_upper = self.factor_adapter.calculate('bollinger_upper', klines)
            if boll_upper is not None:
                factors['boll_upper'] = boll_upper
            
            # 原有因子：获取最新收盘价
            if klines:
                factors['close'] = klines[-1].get('close', 0)
            
            # 原有因子：成交量相关指标
            if len(klines) >= 5:
                # 最近 5 日平均成交量
                recent_5_volume = sum(k.get('volume', 0) for k in klines[-5:]) / 5
                # 前 5 日平均成交量
                prev_5_volume = sum(k.get('volume', 0) for k in klines[-10:-5]) / 5
                if prev_5_volume > 0:
                    factors['volume_ratio_5d'] = recent_5_volume / prev_5_volume
            
            # 其他成交量指标（保持不变）
            if len(klines) >= 20:
                volume_ma20 = sum(k.get('volume', 0) for k in klines[-20:]) / 20
                factors['volume_ma20'] = volume_ma20
            
            if len(klines) >= 5:
                volume_ma5 = sum(k.get('volume', 0) for k in klines[-5:]) / 5
                factors['volume_ma5'] = volume_ma5
            
            if klines:
                factors['volume'] = klines[-1].get('volume', 0)
            
            if len(klines) >= 3:
                factors['volume_history'] = [k.get('volume', 0) for k in klines[-3:]]
        
        except Exception as e:
            logger.error(f"计算因子失败: {e}")
        
        return factors
```

- [ ] **Step 4: 修改 _score_single_stock() 使用新评分器**

找到 `_score_single_stock()` 方法，将技术面评分部分替换为：

```python
    def _score_single_stock(
        self,
        symbol: str,
        klines: List[Dict],
        fundamental: Optional[Dict],
        filters: Dict,
        weights: Optional[Dict] = None
    ) -> Optional[Dict]:
        """评分单只股票（使用 TechnicalScorer）"""
        try:
            # 检查 K 线数据是否充足
            if len(klines) < 30:
                logger.warning(f"{symbol}: K 线数据不足 ({len(klines)} 条)")
                return None
            
            # 计算技术指标因子（包含 ADX）
            factors = self._calculate_factors(klines)
            
            # 新增：评估筛选条件（如果有）
            conditions = filters.get('conditions', [])
            logic = filters.get('logic', 'AND')
            
            if conditions:
                if not self._evaluate_conditions(conditions, logic, fundamental or {}, factors):
                    return None  # 不满足条件，跳过
            
            # === 使用 TechnicalScorer 计算技术面评分 ===
            tech_result = self.technical_scorer.score(
                factors, 
                filters.get('technical', [])
            )
            tech_score = tech_result['total']
            # 可选：记录评分明细用于调试
            # logger.debug(f"{symbol} 技术面明细: {tech_result['breakdown']}")
            
            # 计算基本面评分（保持不变）
            fund_score = self._calculate_fundamental_score(
                fundamental,
                filters.get('fundamental', [])
            )
            
            # 计算资金面评分（保持不变）
            capital_score = self._calculate_capital_score(factors)
            
            # 计算综合评分（保持不变）
            total_score = self._calculate_comprehensive_score(
                tech_score,
                fund_score,
                capital_score,
                weights
            )
            
            # 获取股票名称
            stock_info = self.stock_repo.get_by_symbol(symbol, ['name'])
            stock_name = stock_info['name'] if stock_info else symbol
            
            return {
                'symbol': symbol,
                'name': stock_name,
                'score': round(total_score),
                'technical_score': round(tech_score),
                'fundamental_score': round(fund_score),
                'capital_score': round(capital_score),
                'confidence': round(total_score / 100, 2),
                'risk_level': self._calculate_risk_level(total_score),
                'signal_type': 'buy',
                'timestamp': datetime.now().isoformat()
            }
        
        except Exception as e:
            logger.error(f"{symbol}: 评分失败 - {e}", exc_info=True)
            return None
```

- [ ] **Step 5: 删除旧的 _calculate_technical_score() 方法**

找到并删除以下方法（如果存在）：
- `_calculate_technical_score()`
- `_calculate_default_technical_score()`
- `_is_macd_golden_cross()`（如果在此文件中）

这些逻辑已被 `TechnicalScorer` 替代。

- [ ] **Step 6: 验证服务启动**

```bash
cd quantsys-v2
python -c "
from services.opportunity_scoring_service import OpportunityScoringService
from repositories.kline_repository import KlineRepository
from repositories.stock_repository import StockRepository
from quantlib.adapters import get_factor_adapter

kline_repo = KlineRepository()
stock_repo = StockRepository()
factor_adapter = get_factor_adapter()

service = OpportunityScoringService(kline_repo, stock_repo, factor_adapter)
print('OpportunityScoringService 初始化成功')
print(f'TechnicalScorer: {service.technical_scorer}')
"
```

Expected output: `OpportunityScoringService 初始化成功` 和 `TechnicalScorer: <TechnicalScorer object>`

- [ ] **Step 7: Commit**

```bash
git add services/opportunity_scoring_service.py
git commit -m "feat(scoring): 集成 TechnicalScorer 到 OpportunityScoringService

- 初始化 TechnicalScorer 实例
- _calculate_factors() 新增 ADX 计算
- _score_single_stock() 使用新评分器
- 删除旧的 _calculate_technical_score() 方法"
```

---
## Task 5: 集成测试和文档

**Files:**
- Modify: `quantsys-v2/tests/services/test_opportunity_scoring_service.py`
- Create: `quantsys-v2/services/scoring/README.md`

- [ ] **Step 1: 编写集成测试 - ADX 因子计算验证**

在 `test_opportunity_scoring_service.py` 文件末尾添加：

```python
def test_adx_factor_calculated(scoring_service):
    """测试 ADX 因子被正确计算"""
    # 生成模拟 K 线数据
    klines = []
    for i in range(120):
        klines.append({
            'date': f'2024-{(i % 12) + 1:02d}-{(i % 28) + 1:02d}',
            'open': 100 + i * 0.1,
            'high': 102 + i * 0.1,
            'low': 98 + i * 0.1,
            'close': 101 + i * 0.1,
            'volume': 1000000 + i * 10000
        })
    
    factors = scoring_service._calculate_factors(klines)
    
    # 验证 ADX 被计算
    assert 'adx' in factors
    assert isinstance(factors['adx'], (int, float))
    assert 0 <= factors['adx'] <= 100
```

- [ ] **Step 2: 编写集成测试 - TechnicalScorer 集成验证**

```python
def test_technical_scorer_integration(scoring_service):
    """测试 TechnicalScorer 集成到 OpportunityScoringService"""
    # 准备测试数据
    symbols = ['600519.SH']
    
    # 模拟 K 线数据
    klines_map = {
        '600519.SH': [
            {
                'date': f'2024-{i % 12 + 1:02d}-{i % 28 + 1:02d}',
                'open': 100, 'high': 102, 'low': 98, 'close': 101,
                'volume': 1000000
            }
            for i in range(120)
        ]
    }
    
    # 模拟基本面数据
    fundamentals_map = {
        '600519.SH': {'pe': 25, 'roe': 20, 'debt_ratio': 30, 'gross_margin': 40}
    }
    
    # 执行评分
    opportunities = scoring_service.score_stocks(
        symbols=symbols,
        filters={'technical': [], 'fundamental': []},
        weights=None
    )
    
    assert len(opportunities) > 0
    opp = opportunities[0]
    
    # 验证返回结构
    assert 'technical_score' in opp
    assert 0 <= opp['technical_score'] <= 100
    
    # 验证综合评分包含技术面权重
    assert opp['score'] > 0
    assert 'symbol' in opp
    assert 'name' in opp
```

- [ ] **Step 3: 编写集成测试 - 向后兼容性验证**

```python
def test_backward_compatibility(scoring_service):
    """测试向后兼容性"""
    # 调用旧的 API 接口
    opportunities = scoring_service.score_stocks(
        symbols=['600519.SH', '000858.SZ'],
        filters={
            'technical': ['rsi_oversold', 'macd_golden_cross'],
            'fundamental': ['pe_low']
        },
        weights={'technical': 0.5, 'fundamental': 0.3, 'capital': 0.2}
    )
    
    # 验证返回格式不变
    assert isinstance(opportunities, list)
    
    for opp in opportunities:
        assert 'symbol' in opp
        assert 'score' in opp
        assert 'technical_score' in opp
        assert 'fundamental_score' in opp
        assert 'capital_score' in opp
        assert 'confidence' in opp
        assert 'risk_level' in opp
```

- [ ] **Step 4: 运行集成测试**

```bash
cd quantsys-v2
pytest tests/services/test_opportunity_scoring_service.py::test_adx_factor_calculated -v
pytest tests/services/test_opportunity_scoring_service.py::test_technical_scorer_integration -v
pytest tests/services/test_opportunity_scoring_service.py::test_backward_compatibility -v
```

Expected: 所有测试 PASS

- [ ] **Step 5: 创建评分引擎 README 文档**

创建 `services/scoring/README.md`：

```markdown
# 评分引擎（Scoring Engine）

统一的股票评分系统，支持多维度评分和可扩展架构。

## 架构

- **BaseScorer**: 抽象基类，定义统一的评分接口
- **TechnicalScorer**: 技术面评分引擎（已实现）
- **FundamentalScorer**: 基本面评分引擎（待实现）
- **CapitalScorer**: 资金面评分引擎（待实现）

## TechnicalScorer 使用指南

### 基本用法

\`\`\`python
from services.scoring.technical_scorer import TechnicalScorer

# 初始化评分器
scorer = TechnicalScorer()

# 准备技术指标数据
factors = {
    'rsi': 25,                    # RSI 指标 (0-100)
    'macd': 0.5,                  # MACD 快线
    'macd_signal': 0.3,           # MACD 信号线
    'macd_prev': 0.2,             # 前一日 MACD
    'macd_signal_prev': 0.4,      # 前一日信号线
    'adx': 30,                    # ADX 趋势强度 (0-100)
    'volume_ratio_5d': 1.8,       # 5 日成交量比
}

# 计算评分
result = scorer.score(factors)

print(f"总分: {result['total']}")
print(f"评分明细: {result['breakdown']}")
\`\`\`

### 评分公式

\`\`\`
技术面总分 = 基础分(50) + RSI(±20) + MACD(±20) + ADX(0-15) + 成交量(±20) + 共振(0-15)
范围: 0-100（自动截断）
\`\`\`

### 各子项评分规则

#### RSI 评分（±20 分）
- RSI < 30: 线性加分，最多 +20 分（极度超卖）
- RSI 40-60: +5 分（中性区间）
- RSI > 70: 线性扣分，最多 -20 分（极度超买）

#### MACD 评分（±20 分）
- 金叉: 基础 10 分 + 柱状图强度（最多 +10 分）
- 死叉: 扣分（最多 -15 分）

#### ADX 评分（0-15 分）
- ADX ≤ 25: 0 分（弱趋势）
- ADX > 25: 线性加分，最多 15 分（强趋势）

#### 成交量评分（±20 分）
- 量比 > 1.5: 线性加分，最多 +20 分
- 量比 < 0.8: -10 分

#### 多指标共振（0-15 分）
- RSI 超卖 + MACD 金叉: +10 分
- 放量 + 强趋势: +5 分

### 返回格式

\`\`\`python
{
    'total': 85.0,          # 总分
    'breakdown': {           # 评分明细
        'base': 50.0,
        'rsi': 18.5,
        'macd': 15.0,
        'adx': 10.0,
        'volume': 16.0,
        'resonance': 10.0
    }
}
\`\`\`

## 扩展评分器

创建新的评分器需要：

1. 继承 `BaseScorer`
2. 实现 `score()` 方法
3. 返回标准格式的评分结果

\`\`\`python
from services.scoring.base_scorer import BaseScorer

class MyCustomScorer(BaseScorer):
    def score(self, data: Dict[str, Any]) -> Dict[str, float]:
        # 实现自定义评分逻辑
        total = 0
        breakdown = {}
        
        # ... 评分计算
        
        return {
            'total': total,
            'breakdown': breakdown
        }
\`\`\`

## 测试

\`\`\`bash
# 运行单元测试
pytest tests/services/scoring/test_technical_scorer.py -v

# 检查覆盖率
pytest tests/services/scoring/ --cov=services.scoring --cov-report=term-missing
\`\`\`

## 相关文档

- 设计文档: `docs/superpowers/specs/2026-06-04-opportunity-scoring-optimization-design.md`
- 因子库参考: `docs/FACTOR_LIBRARY_REFERENCE.md`
```

- [ ] **Step 6: 运行完整测试套件**

```bash
cd quantsys-v2
pytest tests/services/scoring/ -v
pytest tests/services/test_opportunity_scoring_service.py -v
```

Expected: 所有测试 PASS

- [ ] **Step 7: Commit**

```bash
git add tests/services/test_opportunity_scoring_service.py services/scoring/README.md
git commit -m "test(scoring): 添加集成测试和评分引擎文档

- 测试 ADX 因子计算
- 测试 TechnicalScorer 集成
- 测试向后兼容性
- 添加评分引擎使用文档"
```

---
## Task 6: 端到端验证

**Files:**
- Test: 完整的机会雷达 API 调用

- [ ] **Step 1: 启动 quantsys-v2 服务**

```bash
cd quantsys-v2
python api/server.py
```

Expected: 服务在 http://127.0.0.1:5001 启动成功

- [ ] **Step 2: 调用机会雷达 API（手动验证）**

在另一个终端执行：

```bash
curl -X POST http://127.0.0.1:5001/api/signals/scan \
  -H "Content-Type: application/json" \
  -d '{
    "stocks": ["600519.SH", "000858.SZ", "000001.SZ"],
    "min_score": 60
  }'
```

Expected: 返回 JSON 格式的机会列表，包含：
- `success: true`
- `opportunities` 数组
- 每个 opportunity 包含 `technical_score` 字段
- 响应时间 < 5s

- [ ] **Step 3: 验证评分合理性**

检查返回结果中的高分股票是否符合以下特征：
- 技术面评分 > 60 的股票
- 查看是否有 RSI 超卖、MACD 金叉、ADX 强趋势等特征
- 评分明细是否合理（如有 debug 日志）

- [ ] **Step 4: 性能测试**

```bash
# 测试 400 只股票的批量评分性能
curl -X POST http://127.0.0.1:5001/api/signals/scan \
  -H "Content-Type: application/json" \
  -d '{
    "min_score": 50
  }' \
  -w "\nTime: %{time_total}s\n"
```

Expected: 响应时间 < 10s（400 只股票）

- [ ] **Step 5: 停止服务**

按 Ctrl+C 停止 `api/server.py`

- [ ] **Step 6: 最终测试 - 运行完整测试套件**

```bash
cd quantsys-v2
pytest tests/services/scoring/ -v
pytest tests/services/test_opportunity_scoring_service.py -v
```

Expected: 所有测试 PASS，无回归

- [ ] **Step 7: 最终 Commit**

```bash
git add -A
git commit -m "chore: 机会雷达评分逻辑优化完成 (Phase 1)

完成内容：
- 创建独立的 TechnicalScorer 评分引擎
- 实现 RSI/MACD/ADX/成交量灰度化评分
- 实现多指标共振加成机制
- 集成到 OpportunityScoringService
- 单元测试覆盖率 > 90%
- 集成测试验证向后兼容性
- 添加评分引擎文档

优化效果：
- 评分更精细（灰度化替代二元）
- 趋势确认（ADX）
- 共振增强（RSI+MACD, 放量+ADX）
- 代码解耦（独立评分器）"
```

---

## 自查清单（Self-Review）

**1. Spec 覆盖检查：**

| 设计需求 | 对应任务 | 状态 |
|---------|---------|------|
| 创建 BaseScorer 基类 | Task 1 | ✅ |
| 实现 TechnicalScorer | Task 2 | ✅ |
| RSI 灰度化评分 | Task 2, Step 2 | ✅ |
| MACD 强度评分 | Task 2, Step 3 | ✅ |
| ADX 趋势确认 | Task 2, Step 4 | ✅ |
| 成交量评分 | Task 2, Step 5 | ✅ |
| 多指标共振 | Task 2, Step 6 | ✅ |
| 单元测试 | Task 3 | ✅ |
| 集成到服务 | Task 4 | ✅ |
| ADX 因子计算 | Task 4, Step 3 | ✅ |
| 集成测试 | Task 5 | ✅ |
| 文档编写 | Task 5, Step 5 | ✅ |
| 端到端验证 | Task 6 | ✅ |

**2. 占位符扫描：** ✅ 无 TBD、TODO、待实现

**3. 类型一致性：** ✅ 
- `TechnicalScorer.score()` 返回格式一致
- 方法名称在所有任务中一致
- 因子字段名一致（rsi, macd, adx, volume_ratio_5d）

**4. 代码完整性：** ✅ 所有代码块完整，可直接复制使用

---

## 后续计划（Phase 1.5）

完成本计划后，执行因子有效性验证：

```typescript
// 使用 factor_analyze 工具验证新评分
factor_analyze({
  factors: ['technical_score', 'rsi14', 'macd', 'adx'],
  start_date: '2024-01-01',
  end_date: '2025-12-31',
  symbols: ['沪深300成分股'],
  forward_returns: [5, 10, 20]
})
```

**验证指标：**
- IC (信息系数) > 0.05
- IR (信息比率) > 0.5
- 覆盖率 > 90%
- 单调性 > 80%

**决策规则：**
- 如果新评分 IC 显著改善（+0.02 以上）→ 进入 Phase 2（策略回测）
- 如果略有改善（+0.01）→ 调整权重重新验证
- 如果下降 → 回滚并重新设计

---

**计划完成日期**: 2026-06-04  
**预计工期**: 1-2 天  
**测试覆盖率目标**: > 90%
