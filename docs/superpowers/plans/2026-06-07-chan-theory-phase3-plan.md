# 缠论策略 Phase 3 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现走势类型分析、完整分析器封装、真实MACD计算，完成缠论策略的完整闭环

**Architecture:** 继续 TDD 驱动开发，基于 Phase 1 & 2 已完成的基础层，封装完整的分析器并优化背驰检测

**Tech Stack:** Python 3.13, Pandas, NumPy, TA-Lib (MACD), pytest, dataclasses

**Phase 3 范围**：
- ✅ 走势类型分析器（上涨/下跌/盘整）
- ✅ 真实 MACD 计算（替换简化版）
- ✅ 完整分析器封装（ChanAnalyzer）
- ✅ 端到端测试（覆盖率 > 85%）

**不包含**：策略引擎集成（留待后续）、实盘对接（留待后续）

---

## Task 1: 真实 MACD 计算

**目标**: 使用 TA-Lib 计算真实 MACD，替换背驰检测器中的简化版

### Step 1.1: 编写测试 - MACD 计算

创建 `tests/chan/test_macd_calculator.py`:

```python
"""MACD 计算器测试"""
import pytest
import numpy as np
from datetime import datetime, timedelta
from chan.macd_calculator import MACDCalculator
from chan.types import KLine


class TestMACDCalculator:
    """MACD 计算器测试类"""

    def test_calculate_macd_basic(self):
        """测试基本 MACD 计算"""
        # 构造测试数据（20根K线，上涨趋势）
        klines = [
            KLine(
                datetime(2024, 1, 1) + timedelta(days=i),
                10.0 + i * 0.5,
                11.0 + i * 0.5,
                9.0 + i * 0.5,
                10.5 + i * 0.5,
                1000,
                [i]
            )
            for i in range(30)
        ]

        calculator = MACDCalculator()
        macd_df = calculator.calculate(klines)

        # 验证返回的 DataFrame
        assert 'macd' in macd_df.columns
        assert 'signal' in macd_df.columns
        assert 'hist' in macd_df.columns
        assert len(macd_df) == len(klines)

        # MACD 柱在上涨趋势中应该主要为正
        positive_hist = (macd_df['hist'] > 0).sum()
        assert positive_hist > len(klines) * 0.5

    def test_calculate_macd_area(self):
        """测试 MACD 面积计算"""
        klines = [
            KLine(
                datetime(2024, 1, 1) + timedelta(days=i),
                10.0 + i * 0.5,
                11.0 + i * 0.5,
                9.0 + i * 0.5,
                10.5 + i * 0.5,
                1000,
                [i]
            )
            for i in range(30)
        ]

        calculator = MACDCalculator()
        area = calculator.calculate_area(klines, 0, 10)

        # 面积应该是正数（上涨趋势）
        assert area > 0
```

### Step 1.2: 运行测试，验证失败

### Step 1.3: 实现 MACD 计算器

创建 `chan/macd_calculator.py`:

```python
"""MACD 计算器 - 使用 TA-Lib 计算真实 MACD"""
from typing import List
import pandas as pd
import numpy as np
try:
    import talib
    TALIB_AVAILABLE = True
except ImportError:
    TALIB_AVAILABLE = False
from .types import KLine


class MACDCalculator:
    """
    MACD 计算器

    使用 TA-Lib 计算 MACD(12, 26, 9)
    """

    def __init__(self, fast_period: int = 12, slow_period: int = 26, signal_period: int = 9):
        """
        初始化 MACD 计算器

        Args:
            fast_period: 快线周期（默认12）
            slow_period: 慢线周期（默认26）
            signal_period: 信号线周期（默认9）
        """
        self.fast_period = fast_period
        self.slow_period = slow_period
        self.signal_period = signal_period

    def calculate(self, klines: List[KLine]) -> pd.DataFrame:
        """
        计算 MACD 指标

        Args:
            klines: K线列表

        Returns:
            DataFrame with columns: ['macd', 'signal', 'hist']
        """
        if not TALIB_AVAILABLE:
            # Fallback: 简化计算
            return self._calculate_simple(klines)

        # 提取收盘价
        closes = np.array([k.close for k in klines])

        # 使用 TA-Lib 计算 MACD
        macd, signal, hist = talib.MACD(
            closes,
            fastperiod=self.fast_period,
            slowperiod=self.slow_period,
            signalperiod=self.signal_period
        )

        return pd.DataFrame({
            'macd': macd,
            'signal': signal,
            'hist': hist
        })

    def calculate_area(self, klines: List[KLine], start_idx: int, end_idx: int) -> float:
        """
        计算线段对应的 MACD 柱面积

        Args:
            klines: K线列表
            start_idx: 起始索引
            end_idx: 结束索引

        Returns:
            MACD 柱面积（可能为负）
        """
        macd_df = self.calculate(klines)
        
        # 取指定区间的柱状图值
        hist_values = macd_df['hist'].iloc[start_idx:end_idx+1]
        
        # 计算面积（梯形积分）
        area = np.trapz(hist_values.fillna(0))
        
        return area

    def _calculate_simple(self, klines: List[KLine]) -> pd.DataFrame:
        """
        简化版 MACD 计算（TA-Lib 不可用时使用）

        使用 EMA 手动计算
        """
        closes = pd.Series([k.close for k in klines])

        # 计算快慢 EMA
        ema_fast = closes.ewm(span=self.fast_period, adjust=False).mean()
        ema_slow = closes.ewm(span=self.slow_period, adjust=False).mean()

        # MACD = 快线 - 慢线
        macd = ema_fast - ema_slow

        # 信号线 = MACD 的 EMA
        signal = macd.ewm(span=self.signal_period, adjust=False).mean()

        # 柱状图 = MACD - 信号线
        hist = macd - signal

        return pd.DataFrame({
            'macd': macd,
            'signal': signal,
            'hist': hist
        })
```

### Step 1.4: 运行测试，验证通过

### Step 1.5: 更新背驰检测器

修改 `chan/divergence_detector.py` 使用真实 MACD：

```python
from .macd_calculator import MACDCalculator

class DivergenceDetector:
    def __init__(self):
        self.macd_calculator = MACDCalculator()

    def _calculate_macd_area(self, segment: Segment, klines: List[KLine]) -> float:
        """使用真实 MACD 计算面积"""
        return self.macd_calculator.calculate_area(
            klines,
            segment.start_index,
            segment.end_index
        )
```

### Step 1.6: 运行背驰检测器测试，验证仍然通过

### Step 1.7: Commit
```bash
git add chan/macd_calculator.py tests/chan/test_macd_calculator.py chan/divergence_detector.py
git commit -m "feat(chan): 实现真实 MACD 计算器

- 使用 TA-Lib 计算 MACD(12,26,9)
- 支持 MACD 面积计算（梯形积分）
- Fallback 到简化 EMA 计算（TA-Lib 不可用时）
- 更新背驰检测器使用真实 MACD
- 测试通过：2/2"
```

---

## Task 2: 走势类型分析器

**目标**: 分析走势类型（上涨/下跌/盘整）

### Step 2.1: 编写测试 - 走势类型分析

创建 `tests/chan/test_trend_analyzer.py`:

```python
"""走势类型分析器测试"""
import pytest
from chan.trend_analyzer import TrendAnalyzer
from chan.types import Segment, ZhongShu


class TestTrendAnalyzer:
    """走势类型分析器测试类"""

    def test_analyze_uptrend(self):
        """测试上涨走势识别"""
        segments = [
            Segment('up', [], 0, 10, high=12.0, low=9.0),
            Segment('down', [], 10, 15, high=11.0, low=10.0),
            Segment('up', [], 15, 25, high=14.0, low=11.0),  # 高点抬升
        ]

        zhongshus = []

        analyzer = TrendAnalyzer()
        trend_type = analyzer.analyze(segments, zhongshus)

        assert trend_type == '上涨'

    def test_analyze_downtrend(self):
        """测试下跌走势识别"""
        segments = [
            Segment('down', [], 0, 10, high=12.0, low=9.0),
            Segment('up', [], 10, 15, high=11.0, low=10.0),
            Segment('down', [], 15, 25, high=10.0, low=7.0),  # 低点下降
        ]

        zhongshus = []

        analyzer = TrendAnalyzer()
        trend_type = analyzer.analyze(segments, zhongshus)

        assert trend_type == '下跌'

    def test_analyze_consolidation(self):
        """测试盘整走势识别"""
        segments = [
            Segment('up', [], 0, 10, high=12.0, low=9.0),
            Segment('down', [], 10, 20, high=11.5, low=9.5),
            Segment('up', [], 20, 30, high=12.5, low=10.0),
        ]

        # 有中枢 = 盘整
        zhongshus = [
            ZhongShu(segments, high=11.5, low=10.0, start_index=0, end_index=30, type='震荡')
        ]

        analyzer = TrendAnalyzer()
        trend_type = analyzer.analyze(segments, zhongshus)

        assert trend_type == '盘整'
```

### Step 2.2: 实现走势类型分析器

创建 `chan/trend_analyzer.py`:

```python
"""走势类型分析器 - 判断上涨/下跌/盘整"""
from typing import List, Literal
from .types import Segment, ZhongShu


class TrendAnalyzer:
    """
    走势类型分析器

    规则：
    - 有中枢 = 盘整
    - 高点抬升 + 低点抬升 = 上涨
    - 高点下降 + 低点下降 = 下跌
    """

    def analyze(
        self,
        segments: List[Segment],
        zhongshus: List[ZhongShu]
    ) -> Literal['上涨', '下跌', '盘整']:
        """
        分析走势类型

        Args:
            segments: 线段列表
            zhongshus: 中枢列表

        Returns:
            '上涨' / '下跌' / '盘整'
        """
        # 规则1：有中枢 = 盘整
        if len(zhongshus) > 0:
            return '盘整'

        # 规则2：少于2个线段，无法判断
        if len(segments) < 2:
            return '盘整'

        # 规则3：比较首尾线段的高低点
        first_seg = segments[0]
        last_seg = segments[-1]

        high_up = last_seg.high > first_seg.high
        low_up = last_seg.low > first_seg.low

        if high_up and low_up:
            return '上涨'
        elif not high_up and not low_up:
            return '下跌'
        else:
            return '盘整'
```

### Step 2.3: 运行测试，验证通过

### Step 2.4: Commit

---

## Task 3: 完整分析器封装

**目标**: 封装 ChanAnalyzer，提供一站式分析接口

### Step 3.1: 编写测试 - 完整分析器

创建 `tests/chan/test_chan_analyzer.py`:

```python
"""缠论完整分析器测试"""
import pytest
import pandas as pd
from datetime import datetime, timedelta
from chan.chan_analyzer import ChanAnalyzer


class TestChanAnalyzer:
    """缠论完整分析器测试类"""

    @pytest.fixture
    def sample_klines(self):
        """构造测试数据"""
        data = []
        for i in range(50):
            data.append({
                'date': datetime(2024, 1, 1) + timedelta(days=i),
                'open': 10.0 + i * 0.1,
                'high': 11.0 + i * 0.1,
                'low': 9.0 + i * 0.1,
                'close': 10.5 + i * 0.1,
                'volume': 1000
            })
        return pd.DataFrame(data)

    def test_analyze_full_pipeline(self, sample_klines):
        """测试完整分析流程"""
        analyzer = ChanAnalyzer()
        result = analyzer.analyze('600519.SH', sample_klines)

        # 验证返回结构
        assert result.symbol == '600519.SH'
        assert result.klines is not None
        assert result.fenxings is not None
        assert result.bis is not None
        assert result.segments is not None
        assert result.zhongshus is not None
        assert result.buypoints is not None
        assert result.trend_type in ['上涨', '下跌', '盘整']

    def test_analyze_with_buypoint_filter(self, sample_klines):
        """测试买卖点过滤"""
        analyzer = ChanAnalyzer()
        result = analyzer.analyze(
            '600519.SH',
            sample_klines,
            enable_buypoints=['1买', '2买']  # 只启用1买和2买
        )

        # 验证只有1买和2买
        if len(result.buypoints) > 0:
            assert all(bp.type in ['1买', '2买'] for bp in result.buypoints)
```

### Step 3.2: 实现完整分析器

创建 `chan/chan_analyzer.py`:

```python
"""缠论完整分析器 - 一站式分析接口"""
from typing import List
import pandas as pd
from dataclasses import dataclass
from .types import KLine, FenXing, Bi, Segment, ZhongShu, BuyPoint
from .kline_processor import KLineProcessor
from .bi_identifier import BiIdentifier
from .segment_identifier import SegmentIdentifier
from .zhongshu_identifier import ZhongShuIdentifier
from .divergence_detector import DivergenceDetector
from .buypoint_detector import BuyPointDetector
from .trend_analyzer import TrendAnalyzer


@dataclass
class ChanAnalysisResult:
    """缠论分析结果"""
    symbol: str
    klines: List[KLine]
    fenxings: List[FenXing]
    bis: List[Bi]
    segments: List[Segment]
    zhongshus: List[ZhongShu]
    buypoints: List[BuyPoint]
    trend_type: str
    divergences: dict


class ChanAnalyzer:
    """
    缠论完整分析器

    封装 Phase 1 & 2 & 3 所有功能
    提供一站式分析接口
    """

    def __init__(self):
        self.kline_processor = KLineProcessor()
        self.bi_identifier = BiIdentifier()
        self.segment_identifier = SegmentIdentifier()
        self.zhongshu_identifier = ZhongShuIdentifier()
        self.divergence_detector = DivergenceDetector()
        self.buypoint_detector = BuyPointDetector()
        self.trend_analyzer = TrendAnalyzer()

    def analyze(
        self,
        symbol: str,
        klines_df: pd.DataFrame,
        enable_buypoints: List[str] = ['1买', '2买', '3买', '1卖', '2卖', '3卖']
    ) -> ChanAnalysisResult:
        """
        完整缠论分析流程

        Args:
            symbol: 股票代码
            klines_df: K线 DataFrame
            enable_buypoints: 启用的买卖点类型

        Returns:
            ChanAnalysisResult
        """
        # Phase 1: 基础结构识别
        processed_klines = self.kline_processor.process(klines_df)
        fenxings = self.bi_identifier.identify_fenxings(processed_klines)
        bis = self.bi_identifier.identify_bis(fenxings, processed_klines)
        segments = self.segment_identifier.identify_segments(bis)

        # Phase 2: 中枢和背驰
        zhongshus = self.zhongshu_identifier.identify_zhongshus(segments)

        divergences = {}
        for i in range(1, len(segments)):
            if i > 0 and segments[i].direction == segments[i-1].direction:
                divergences[i] = self.divergence_detector.detect_divergence(
                    segments[i-1], segments[i], processed_klines,
                    'bearish' if segments[i].direction == 'down' else 'bullish'
                )

        buypoints = self.buypoint_detector.detect_buypoints(
            segments, zhongshus, divergences, processed_klines
        )

        # 过滤买卖点
        buypoints = [bp for bp in buypoints if bp.type in enable_buypoints]

        # Phase 3: 走势类型分析
        trend_type = self.trend_analyzer.analyze(segments, zhongshus)

        return ChanAnalysisResult(
            symbol=symbol,
            klines=processed_klines,
            fenxings=fenxings,
            bis=bis,
            segments=segments,
            zhongshus=zhongshus,
            buypoints=buypoints,
            trend_type=trend_type,
            divergences=divergences
        )
```

### Step 3.3: 运行测试，验证通过

### Step 3.4: Commit

---

## Task 4: 端到端测试与文档

**目标**: 完整端到端测试 + 更新文档

### Step 4.1: 编写端到端测试

更新 `tests/chan/test_integration.py` 添加 Phase 3 测试

### Step 4.2: 运行所有测试

```bash
pytest tests/chan/ -v --cov=chan --cov-report=term
```

### Step 4.3: 更新 README

更新 `chan/README.md`，添加 Phase 3 使用示例

### Step 4.4: Commit

---

## 验证清单

- [ ] 所有测试通过（预计 ~30 个测试）
- [ ] 代码覆盖率 > 85%
- [ ] MACD 计算准确
- [ ] 走势类型分类正确
- [ ] 完整分析器接口简洁
- [ ] Git 提交历史清晰（4个提交）
- [ ] 文档更新完整

## 性能目标

- 1000根K线完整分析（Phase 1 + 2 + 3）：< 2秒
- 内存占用：< 150MB

## 后续规划

- 策略引擎集成
- 回测系统对接
- 实盘信号推送
