# 机会雷达评分逻辑优化设计 - Phase 1

**日期**: 2026-06-04  
**作者**: Claude (Opus 4.6)  
**状态**: 设计阶段

---

## 1. 背景与目标

### 1.1 当前问题

机会雷达（`OpportunityScoringService`）的技术面评分存在以下问题：

1. **二元化严重**：条件满足/不满足只有 0 或 25 分，缺乏灰度
   - 例如：RSI=29（超卖）和 RSI=10（极度超卖）得分相同
   
2. **固定阈值**：RSI 30/70 阈值在不同市场环境下不合理
   - 例如：牛市中 RSI>70 是常态，不应大幅扣分

3. **指标孤立**：各指标独立加分，未考虑共振效应
   - 例如：RSI 超卖 + MACD 金叉应有额外加成

4. **缺乏趋势强度**：未使用 ADX/AROON 等趋势强度指标
   - 无法区分强趋势突破和弱趋势震荡

### 1.2 优化目标

**Phase 1 目标**（本次）：
- ✅ 技术面评分灰度化（从二元改为连续评分）
- ✅ 引入趋势强度指标（ADX）
- ✅ 实现多指标共振机制
- ✅ 保持 0-100 分范围，易于理解

**Phase 1.5 目标**（验证）：
- 使用 `factor_analyze` 验证新评分的 IC/IR
- 对比新旧评分的因子有效性

**Phase 2 目标**（后续）：
- 基于新评分构建选股策略
- 完整回测验证（夏普/胜率/回撤）
- 行业归一化、基本面趋势评分

---

## 2. 架构设计

### 2.1 组件架构

```
quantsys-v2/
├── services/
│   ├── scoring/                          # 新增：评分引擎目录
│   │   ├── __init__.py
│   │   ├── base_scorer.py                # 新增：评分器基类
│   │   ├── technical_scorer.py           # 新增：技术面评分引擎
│   │   └── README.md                     # 新增：评分引擎文档
│   └── opportunity_scoring_service.py    # 修改：集成 TechnicalScorer
└── tests/
    └── services/
        └── scoring/
            └── test_technical_scorer.py  # 新增：单元测试
```

### 2.2 核心类设计

#### BaseScorer（抽象基类）

```python
from abc import ABC, abstractmethod
from typing import Dict, Any

class BaseScorer(ABC):
    """评分器基类"""
    
    @abstractmethod
    def score(self, data: Dict[str, Any]) -> Dict[str, float]:
        """
        计算评分
        
        Returns:
            {
                'total': 85.0,      # 总分 (0-100)
                'breakdown': {       # 评分明细
                    'sub_item_1': 20.0,
                    'sub_item_2': 15.0,
                    ...
                }
            }
        """
        pass
```

#### TechnicalScorer（技术面评分器）

```python
class TechnicalScorer(BaseScorer):
    """
    技术面评分引擎
    
    特性：
    - 灰度化评分（替代二元判断）
    - 多指标共振加成
    - 趋势强度确认（ADX）
    - 返回评分明细便于调试
    """
    
    def __init__(self, factor_adapter=None):
        self.factor_adapter = factor_adapter
    
    def score(self, factors: Dict[str, Any], conditions=None) -> Dict[str, float]:
        """计算技术面评分"""
        pass
```

### 2.3 数据流

```
OpportunityScoringService.score_stocks()
  ↓
批量查询 K 线 (kline_repo.batch_get_recent_klines)
  ↓
并行处理每只股票 (ThreadPoolExecutor, 10 workers)
  ↓
_score_single_stock(symbol, klines, fundamental)
  ↓
_calculate_factors(klines)  # 计算 RSI/MACD/ADX/成交量
  ↓
TechnicalScorer.score(factors)  # 返回 {total: 85, breakdown: {...}}
  ↓
_calculate_fundamental_score(fundamental)
  ↓
_calculate_capital_score(factors)
  ↓
_calculate_comprehensive_score(tech, fund, capital, weights)
  ↓
返回 opportunity 对象
```

---

## 3. 评分算法设计

### 3.1 评分公式

```
技术面总分 = 基础分(50) 
           + RSI评分(±20) 
           + MACD评分(±20) 
           + ADX评分(0-15) 
           + 成交量评分(±20) 
           + 共振加成(0-15)

范围：0-100 分（自动截断）
```

### 3.2 各子项评分逻辑

#### 3.2.1 RSI 灰度化评分（±20 分）

**旧逻辑（二元）：**
```python
if rsi < 30: score += 15
elif rsi > 70: score -= 15
```

**新逻辑（灰度）：**
```python
def _score_rsi(self, rsi: float) -> float:
    """
    RSI 灰度化评分
    
    评分曲线：
    - rsi=0   → +20 分（极度超卖）
    - rsi=30  → +0 分（超卖边界）
    - rsi=40-60 → +5 分（中性区间）
    - rsi=70  → +0 分（超买边界）
    - rsi=100 → -20 分（极度超买）
    """
    if rsi < 30:
        return 20 * (30 - rsi) / 30
    elif rsi > 70:
        return -20 * (rsi - 70) / 30
    elif 40 <= rsi <= 60:
        return 5
    return 0
```

**改进点：**
- 超卖程度越深，得分越高（线性关系）
- 中性区间（40-60）小幅加分，鼓励稳健
- 超买扣分也按程度递减

#### 3.2.2 MACD 强度评分（±20 分）

**旧逻辑：**
```python
if is_golden_cross: score += 10
elif macd < signal: score -= 10
```

**新逻辑（考虑柱状图强度）：**
```python
def _score_macd(self, factors: Dict) -> float:
    """
    MACD 强度评分
    
    金叉：基础 10 分 + 柱状图强度（最多 10 分）
    死叉：扣分（最多 -15 分）
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
```

**改进点：**
- 柱状图越大 = 趋势越强 = 得分越高
- 区分弱金叉（柱状图小）和强金叉（柱状图大）

#### 3.2.3 ADX 趋势强度评分（0-15 分）

**新增逻辑：**
```python
def _score_adx(self, adx: float) -> float:
    """
    ADX 趋势强度评分
    
    - adx < 20  → 0 分（无趋势）
    - adx = 25  → 0 分（弱趋势边界）
    - adx = 50  → 15 分（强趋势）
    - adx > 50  → 15 分（极强趋势）
    """
    if adx <= 25:
        return 0
    return min(15, (adx - 25) / 5)
```

**新增原因：**
- 区分震荡市和趋势市
- 趋势确认可以提高突破信号的可靠性

#### 3.2.4 成交量评分（±20 分）

**保持现有逻辑，微调权重：**
```python
def _score_volume(self, factors: Dict) -> float:
    """
    成交量评分
    
    - 5 日量比 > 1.5 → 最多 +20 分
    - 5 日量比 < 0.8 → -10 分（缩量）
    """
    volume_ratio = factors.get('volume_ratio_5d', 1.0)
    
    if volume_ratio > 1.5:
        # 放量：线性加分，最多 20 分
        return min(20, (volume_ratio - 1) * 20)
    elif volume_ratio < 0.8:
        return -10
    return 0
```

#### 3.2.5 多指标共振加成（0-15 分）

**核心创新：**
```python
def _calculate_resonance(self, factors: Dict, breakdown: Dict) -> float:
    """
    多指标共振加成
    
    规则：
    1. RSI 超卖 (rsi<30) + MACD 金叉 → +10 分
    2. 放量 (ratio>1.5) + 强趋势 (adx>25) → +5 分
    
    最多累计 15 分
    """
    bonus = 0
    rsi = factors.get('rsi', 50)
    volume_ratio = factors.get('volume_ratio_5d', 1.0)
    adx = factors.get('adx', 0)
    
    # 规则 1：超卖反弹 + 金叉确认
    if rsi < 30 and breakdown.get('macd', 0) > 10:
        bonus += 10
    
    # 规则 2：放量突破 + 趋势确认
    if volume_ratio > 1.5 and adx > 25:
        bonus += 5
    
    return min(bonus, 15)
```

**设计理念：**
- 单一指标可能误判，多指标共振提高准确率
- 共振加成不超过 15 分，避免过度放大

### 3.3 完整评分示例

**输入：**
```python
factors = {
    'rsi': 25,           # 超卖
    'macd': 0.5,
    'macd_signal': 0.3,
    'macd_prev': 0.2,
    'macd_signal_prev': 0.4,  # 金叉
    'adx': 30,           # 强趋势
    'volume_ratio_5d': 1.8,  # 放量
}
```

**计算过程：**
```
基础分: 50
RSI 评分: 20 * (30-25)/30 = 3.33
MACD 评分: 10 + min(10, 0.2*100) = 20
ADX 评分: (30-25)/5 = 1
成交量评分: min(20, (1.8-1)*20) = 16
共振加成: 10 (RSI+MACD) + 5 (放量+ADX) = 15

总分 = 50 + 3.33 + 20 + 1 + 16 + 15 = 105.33 → 截断为 100
```

**输出：**
```python
{
    'total': 100,
    'breakdown': {
        'base': 50,
        'rsi': 3.33,
        'macd': 20,
        'adx': 1,
        'volume': 16,
        'resonance': 15
    }
}
```

---

## 4. 代码实现接口

### 4.1 TechnicalScorer 完整接口

```python
# services/scoring/technical_scorer.py

from typing import Dict, Any, Optional
import logging
from .base_scorer import BaseScorer

logger = logging.getLogger(__name__)


class TechnicalScorer(BaseScorer):
    """技术面评分引擎"""
    
    def __init__(self, factor_adapter=None):
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
                - rsi: RSI 指标值 (0-100)
                - macd: MACD 快线值
                - macd_signal: MACD 信号线值
                - macd_prev: 前一日 MACD 值（用于判断金叉）
                - macd_signal_prev: 前一日信号线值
                - adx: ADX 趋势强度指标 (0-100)
                - volume_ratio_5d: 5 日成交量比
            
            conditions: 可选的筛选条件列表（向后兼容，暂不使用）
        
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
        # 实现略（见完整代码）
        pass
    
    # 私有方法
    def _score_rsi(self, rsi: float) -> float: pass
    def _score_macd(self, factors: Dict) -> float: pass
    def _score_adx(self, adx: float) -> float: pass
    def _score_volume(self, factors: Dict) -> float: pass
    def _calculate_resonance(self, factors: Dict, breakdown: Dict) -> float: pass
    def _is_golden_cross(self, factors: Dict) -> bool: pass
```

### 4.2 OpportunityScoringService 集成

```python
# services/opportunity_scoring_service.py

from services.scoring.technical_scorer import TechnicalScorer

class OpportunityScoringService:
    
    def __init__(self, kline_repo, stock_repo, factor_adapter):
        self.kline_repo = kline_repo
        self.stock_repo = stock_repo
        self.factor_adapter = factor_adapter
        # 新增：初始化技术面评分器
        self.technical_scorer = TechnicalScorer(factor_adapter)
    
    def _score_single_stock(self, symbol, klines, fundamental, filters, weights):
        """评分单只股票"""
        # 计算技术指标因子（新增 ADX）
        factors = self._calculate_factors(klines)
        
        # 使用 TechnicalScorer 计算技术面评分
        tech_result = self.technical_scorer.score(
            factors, 
            filters.get('technical', [])
        )
        tech_score = tech_result['total']
        
        # 基本面评分（保持不变）
        fund_score = self._calculate_fundamental_score(fundamental, ...)
        
        # 资金面评分（保持不变）
        capital_score = self._calculate_capital_score(factors)
        
        # 综合评分
        total_score = self._calculate_comprehensive_score(
            tech_score, fund_score, capital_score, weights
        )
        
        return {...}
```

### 4.3 _calculate_factors() 修改

```python
def _calculate_factors(self, klines: List[Dict]) -> Dict:
    """计算技术指标因子（新增 ADX）"""
    factors = {}
    
    # 原有因子（保持不变）
    factors['rsi'] = self.factor_adapter.calculate('rsi14', klines)
    factors['macd'] = self.factor_adapter.calculate('macd', klines)
    factors['macd_signal'] = self.factor_adapter.calculate('macd_signal', klines)
    # ... 前一日 MACD
    
    # === 新增：ADX 计算 ===
    adx = self.factor_adapter.calculate('adx', klines)
    if adx is not None:
        factors['adx'] = adx
    
    # 成交量相关（保持不变）
    # ...
    
    return factors
```

---

## 5. 测试策略

### 5.1 单元测试设计

**测试文件**: `tests/services/scoring/test_technical_scorer.py`

**测试覆盖：**

```python
class TestTechnicalScorer:
    # 基础功能测试
    def test_score_returns_correct_structure(self): pass
    def test_score_range_valid(self): pass
    
    # RSI 评分测试
    def test_rsi_oversold_scoring(self): pass
    def test_rsi_overbought_scoring(self): pass
    def test_rsi_neutral_scoring(self): pass
    
    # MACD 评分测试
    def test_macd_golden_cross(self): pass
    def test_macd_dead_cross(self): pass
    
    # ADX 评分测试
    def test_adx_weak_trend(self): pass
    def test_adx_strong_trend(self): pass
    
    # 共振加成测试
    def test_resonance_rsi_macd(self): pass
    def test_resonance_volume_adx(self): pass
    def test_resonance_both_rules(self): pass
```

**目标覆盖率**: > 90%

### 5.2 集成测试

```python
# tests/services/test_opportunity_scoring_service.py

def test_technical_scorer_integration(self): pass
def test_adx_factor_calculated(self): pass
def test_backward_compatibility(self): pass
```

### 5.3 性能基准

| 指标 | 旧实现 | 新实现（预期） |
|------|--------|---------------|
| 单股评分耗时 | ~5ms | ~6ms |
| 400 股批量评分 | ~0.2s | ~0.24s |
| 内存占用 | ~50MB | ~55MB |

---

## 6. 验证计划

### 6.1 单元测试验证（实现后立即执行）

```bash
pytest tests/services/scoring/ -v --cov=services.scoring
```

**目标**:
- ✅ 所有测试通过
- ✅ 覆盖率 > 90%

### 6.2 因子有效性验证（Phase 1.5）

使用 `factor_analyze` 工具验证新评分的 IC/IR：

```typescript
factor_analyze({
  factors: ['technical_score', 'rsi14', 'macd', 'adx'],
  start_date: '2024-01-01',
  end_date: '2025-12-31',
  symbols: ['沪深300成分股'],
  forward_returns: [5, 10, 20]
})
```

**验证指标**:
- **IC (信息系数)**: 评分与未来收益的相关性
  - 目标: IC > 0.05
  - 对比: 新评分 IC > 旧评分 IC
  
- **IR (信息比率)**: IC / IC 标准差
  - 目标: IR > 0.5
  
- **覆盖率**: 有效数据比例
  - 目标: > 90%
  
- **单调性**: 评分分层收益单调递增
  - 目标: > 80%

**决策规则**:
```
IF 新评分 IC > 旧评分 IC + 0.02 AND IR > 0.5:
    → 进入 Phase 2（策略回测）
ELIF 新评分 IC 略有改善 (+0.01):
    → 调整权重后重新验证
ELSE:
    → 回滚并重新设计
```

### 6.3 手动验证（抽样检查）

```bash
curl -X POST http://127.0.0.1:5001/api/signals/scan \
  -d '{"stocks": ["600519.SH", "000858.SZ", "000001.SZ"]}'
```

**检查项**:
1. 高分股票是否符合"超卖+金叉+强趋势+放量"特征
2. 同一股票多次调用评分是否一致
3. 响应时间是否在可接受范围（< 5s/400 股票）

---

## 7. 部署计划

### 7.1 实施步骤

**Step 1**: 创建基础架构
- 创建 `services/scoring/` 目录
- 实现 `base_scorer.py`
- 实现 `technical_scorer.py`

**Step 2**: 修改现有服务
- 修改 `opportunity_scoring_service.py`
- 在 `_calculate_factors()` 中新增 ADX
- 在 `_score_single_stock()` 中集成 TechnicalScorer

**Step 3**: 编写测试
- 单元测试（`test_technical_scorer.py`）
- 集成测试（修改 `test_opportunity_scoring_service.py`）

**Step 4**: 文档编写
- `services/scoring/README.md`

**预计工期**: 1-2 天

### 7.2 回滚策略

**触发条件**:
- 单元测试失败率 > 10%
- 集成测试出现阻塞性错误
- 因子有效性验证 IC 下降超过 0.03
- 生产环境响应时间 > 10s

**回滚步骤**:
```bash
git checkout main
git revert <commit-hash>
python start_all.py
```

---

## 8. 后续计划

### Phase 2: 策略回测验证（后续）

1. 基于新评分构建选股策略
2. 使用 `strategy_combo_backtest` 完整回测
3. 对比夏普/胜率/回撤等指标

### Phase 3: 高级优化（后续）

1. **基本面评分优化**
   - 行业归一化（PE/PB 按行业分位数评分）
   - 财务指标趋势（ROE 改善/恶化）
   - 盈利质量（OCF/净利润）

2. **资金面评分优化**
   - 北向资金流向
   - 换手率分析
   - 大单净流入

3. **动态权重优化**
   - 市场风格检测（牛市/熊市/震荡市）
   - 因子衰减监控
   - 因子相关性处理

4. **风险等级细化**
   - 引入波动率、Beta
   - 五级风险分类（very_low/low/medium/high/very_high）

---

## 9. 附录

### 9.1 技术栈

- Python 3.12
- TA-Lib（因子计算）
- pytest（单元测试）
- ThreadPoolExecutor（并行处理）

### 9.2 因子库支持

项目已实现 104 个技术因子，包括：
- ✅ ADX（趋势强度）
- ✅ CCI（商品通道）
- ✅ Aroon（阿隆指标）
- ✅ RSI/MACD/布林带等常用指标

所有因子通过 `factor_adapter.calculate()` 统一调用。

### 9.3 参考文档

- 因子库完整参考：`docs/FACTOR_LIBRARY_REFERENCE.md`
- 机会雷达 API：`quantsys-v2/api/routes/signals.py`
- 现有评分服务：`quantsys-v2/services/opportunity_scoring_service.py`

---

**设计完成日期**: 2026-06-04  
**下一步**: 编写实施计划（invoke writing-plans skill）
