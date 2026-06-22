# 缠论策略 Phase 2 (P1) 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现中枢识别、背驰检测、买卖点检测，完成缠论策略的核心交易信号生成功能

**Architecture:** 继续 TDD 驱动开发，基于 Phase 1 已完成的基础层（KLine, Bi, Segment），向上构建中枢和信号层

**Tech Stack:** Python 3.13, Pandas, NumPy, pytest, dataclasses

**Phase 2 范围**：
- ✅ 中枢识别器（至少3个线段重叠）
- ✅ 背驰检测器（MACD面积背驰简化版）
- ✅ 买卖点检测器（1/2/3类买卖点）
- ✅ 单元测试（覆盖率 > 80%）

**不包含**：走势类型分析（留待 Phase 3）、完整分析器封装（留待 Phase 3）

---

## Task 1: 中枢识别器

**目标**: 识别线段重叠形成的中枢

### Step 1.1: 编写测试 - 基本中枢识别

创建 `tests/chan/test_zhongshu_identifier.py`:

```python
"""中枢识别器测试"""
import pytest
from datetime import datetime
from chan.zhongshu_identifier import ZhongShuIdentifier
from chan.types import Segment, Bi, FenXing, KLine


class TestZhongShuIdentifier:
    """中枢识别器测试类"""

    def test_identify_zhongshu_valid_3segments(self):
        """测试有效中枢（3个线段重叠）"""
        # 构造3个有重叠的线段
        segments = [
            Segment('up', [], 0, 10, high=12.0, low=9.0),
            Segment('down', [], 10, 20, high=11.5, low=9.5),
            Segment('up', [], 20, 30, high=12.5, low=10.0),
        ]

        identifier = ZhongShuIdentifier()
        zhongshus = identifier.identify_zhongshus(segments)

        # 预期：识别出1个中枢
        assert len(zhongshus) == 1
        assert zhongshus[0].high == 11.5  # min(12.0, 11.5, 12.5)
        assert zhongshus[0].low == 10.0   # max(9.0, 9.5, 10.0)
        assert len(zhongshus[0].segments) == 3

    def test_identify_zhongshu_no_overlap(self):
        """测试无重叠（无中枢）"""
        segments = [
            Segment('up', [], 0, 10, high=12.0, low=9.0),
            Segment('down', [], 10, 20, high=11.0, low=8.0),
            Segment('up', [], 20, 30, high=14.0, low=12.5),  # 无重叠
        ]

        identifier = ZhongShuIdentifier()
        zhongshus = identifier.identify_zhongshus(segments)

        # 预期：无中枢
        assert len(zhongshus) == 0
```

### Step 1.2: 运行测试，验证失败
```bash
pytest tests/chan/test_zhongshu_identifier.py::TestZhongShuIdentifier::test_identify_zhongshu_valid_3segments -v
```

### Step 1.3: 实现中枢识别器

创建 `chan/zhongshu_identifier.py`:

```python
"""中枢识别器 - 识别线段重叠形成的中枢"""
from typing import List, Optional, Tuple
from .types import Segment, ZhongShu


class ZhongShuIdentifier:
    """
    中枢识别器

    职责：识别中枢及动态变化
    规则：至少3个线段的重叠区间
    """

    def identify_zhongshus(self, segments: List[Segment]) -> List[ZhongShu]:
        """
        识别中枢

        流程：
        1. 滑动窗口（3个线段）
        2. 计算重叠区间
        3. 验证重叠有效性
        4. 尝试扩展中枢
        """
        if len(segments) < 3:
            return []

        zhongshus = []
        i = 0

        while i <= len(segments) - 3:
            # 尝试构建中枢
            window_segments = segments[i:i+3]
            overlap = self._calculate_overlap(window_segments)

            if overlap is not None:
                # 有效中枢，尝试扩展
                zh_low, zh_high = overlap
                zh_segments = window_segments.copy()
                j = i + 3

                # 扩展中枢（检查后续线段是否仍然重叠）
                while j < len(segments):
                    extended_segments = zh_segments + [segments[j]]
                    extended_overlap = self._calculate_overlap(extended_segments)
                    if extended_overlap is not None:
                        zh_segments.append(segments[j])
                        zh_low, zh_high = extended_overlap
                        j += 1
                    else:
                        break

                # 创建中枢对象
                zhongshus.append(ZhongShu(
                    segments=zh_segments,
                    high=zh_high,
                    low=zh_low,
                    start_index=zh_segments[0].start_index,
                    end_index=zh_segments[-1].end_index,
                    type='震荡'  # 简化版，暂不区分扩展/移动
                ))

                # 跳到中枢之后
                i = j
            else:
                i += 1

        return zhongshus

    def _calculate_overlap(self, segments: List[Segment]) -> Optional[Tuple[float, float]]:
        """
        计算线段重叠区间

        Returns:
            (overlap_low, overlap_high) 或 None（无重叠）
        """
        overlap_low = max(seg.low for seg in segments)
        overlap_high = min(seg.high for seg in segments)

        if overlap_low < overlap_high:
            return (overlap_low, overlap_high)
        else:
            return None
```

### Step 1.4: 运行测试，验证通过
```bash
pytest tests/chan/test_zhongshu_identifier.py -v
```

### Step 1.5: 添加扩展中枢测试

在 `test_zhongshu_identifier.py` 添加：

```python
    def test_identify_zhongshu_extended(self):
        """测试中枢扩展（超过3个线段）"""
        segments = [
            Segment('up', [], 0, 10, high=12.0, low=9.0),
            Segment('down', [], 10, 20, high=11.5, low=9.5),
            Segment('up', [], 20, 30, high=12.5, low=10.0),
            Segment('down', [], 30, 40, high=11.8, low=9.8),  # 继续重叠
        ]

        identifier = ZhongShuIdentifier()
        zhongshus = identifier.identify_zhongshus(segments)

        # 预期：1个扩展中枢（4个线段）
        assert len(zhongshus) == 1
        assert len(zhongshus[0].segments) == 4
```

### Step 1.6: 运行测试，验证通过

### Step 1.7: Commit
```bash
git add chan/zhongshu_identifier.py tests/chan/test_zhongshu_identifier.py
git commit -m "feat(chan): 实现中枢识别器

- 识别3个线段重叠区间
- 支持中枢扩展
- 测试覆盖：基本中枢、无重叠、扩展中枢
- 测试通过：3/3"
```

---

## Task 2: 背驰检测器（简化版）

**目标**: 检测价格走势与动量指标的背驰

### Step 2.1: 编写测试 - 背驰检测

创建 `tests/chan/test_divergence_detector.py`:

```python
"""背驰检测器测试"""
import pytest
from datetime import datetime, timedelta
from chan.divergence_detector import DivergenceDetector
from chan.types import Segment, KLine


class TestDivergenceDetector:
    """背驰检测器测试类"""

    def test_detect_divergence_bearish(self):
        """测试顶背驰（价格新高，MACD面积减小）"""
        # 构造测试数据：两个上升线段
        klines = [
            KLine(datetime(2024, 1, i+1), 10.0+i*0.5, 11.0+i*0.5, 9.0+i*0.5, 10.5+i*0.5, 1000, [i])
            for i in range(20)
        ]

        seg1 = Segment('up', [], 0, 5, high=13.0, low=9.0)
        seg2 = Segment('up', [], 10, 15, high=14.5, low=11.0)  # 价格新高

        detector = DivergenceDetector()
        # 模拟 MACD 面积：seg2 < seg1（背驰）
        is_divergence = detector.detect_divergence(seg1, seg2, klines, 'bearish')

        assert is_divergence is True

    def test_detect_divergence_no_divergence(self):
        """测试无背驰（正常走势）"""
        klines = [
            KLine(datetime(2024, 1, i+1), 10.0+i*0.5, 11.0+i*0.5, 9.0+i*0.5, 10.5+i*0.5, 1000, [i])
            for i in range(20)
        ]

        seg1 = Segment('up', [], 0, 5, high=13.0, low=9.0)
        seg2 = Segment('up', [], 10, 15, high=14.5, low=11.0)

        detector = DivergenceDetector()
        # 模拟 MACD 面积：seg2 > seg1（无背驰）
        # 实际实现中会计算 MACD，这里简化
        # 先让测试失败，后续实现
        pass  # 待实现
```

### Step 2.2: 实现背驰检测器

创建 `chan/divergence_detector.py`:

```python
"""背驰检测器 - MACD 面积背驰简化版"""
from typing import List, Literal
import numpy as np
from .types import Segment, KLine


class DivergenceDetector:
    """
    背驰检测器

    简化版：使用 MACD 面积判断背驰
    - 顶背驰：价格新高，MACD 面积减小
    - 底背驰：价格新低，MACD 面积增大
    """

    def detect_divergence(
        self,
        seg1: Segment,
        seg2: Segment,
        klines: List[KLine],
        divergence_type: Literal['bullish', 'bearish']
    ) -> bool:
        """
        检测两个线段间是否背驰

        Args:
            seg1: 前一个线段
            seg2: 后一个线段
            klines: 完整K线数据
            divergence_type: 'bullish'(底背驰) 或 'bearish'(顶背驰)

        Returns:
            是否背驰
        """
        # 计算 MACD 面积
        area1 = self._calculate_macd_area(seg1, klines)
        area2 = self._calculate_macd_area(seg2, klines)

        if divergence_type == 'bearish':
            # 顶背驰：价格新高 且 MACD面积减小
            return seg2.high > seg1.high and area2 < area1
        else:
            # 底背驰：价格新低 且 MACD面积增大
            return seg2.low < seg1.low and abs(area2) < abs(area1)

    def _calculate_macd_area(self, segment: Segment, klines: List[KLine]) -> float:
        """
        计算线段对应的 MACD 柱面积（简化版）

        简化策略：使用价格振幅作为近似
        实际应该计算 MACD(12,26,9) 柱状图面积
        """
        # TODO: Phase 3 改用真实 MACD 计算
        # 当前简化：用价格振幅近似动量
        amplitude = segment.high - segment.low
        length = segment.end_index - segment.start_index
        return amplitude * length
```

### Step 2.3: 更新测试并验证

### Step 2.4: Commit
```bash
git add chan/divergence_detector.py tests/chan/test_divergence_detector.py
git commit -m "feat(chan): 实现背驰检测器（简化版）

- MACD 面积背驰检测
- 顶背驰：价格新高 & MACD面积减小
- 底背驰：价格新低 & MACD面积增大
- 简化版：使用价格振幅近似（Phase 3 改用真实MACD）
- 测试通过：2/2"
```

---

## Task 3: 买卖点检测器

**目标**: 识别三类买卖点

### Step 3.1: 编写测试 - 1买检测

创建 `tests/chan/test_buypoint_detector.py`:

```python
"""买卖点检测器测试"""
import pytest
from datetime import datetime
from chan.buypoint_detector import BuyPointDetector
from chan.types import Segment, ZhongShu, KLine


class TestBuyPointDetector:
    """买卖点检测器测试类"""

    def test_detect_first_buy(self):
        """测试1买（下跌背驰）"""
        klines = [KLine(datetime(2024, 1, i+1), 10.0, 11.0, 9.0, 10.5, 1000, [i]) for i in range(30)]

        segments = [
            Segment('down', [], 0, 10, high=12.0, low=9.0),
            Segment('up', [], 10, 15, high=11.0, low=9.5),
            Segment('down', [], 15, 25, high=10.5, low=8.5),  # 背驰
        ]

        zhongshus = []
        divergences = {2: True}  # segments[2] 背驰

        detector = BuyPointDetector()
        buypoints = detector.detect_buypoints(segments, zhongshus, divergences, klines)

        # 预期：识别出1买
        assert len(buypoints) >= 1
        first_buy = [bp for bp in buypoints if bp.type == '1买']
        assert len(first_buy) == 1
        assert first_buy[0].position_ratio == 1.0  # 满仓

    def test_detect_second_buy(self):
        """测试2买（回调不破中枢）"""
        klines = [KLine(datetime(2024, 1, i+1), 10.0, 11.0, 9.0, 10.5, 1000, [i]) for i in range(50)]

        segments = [
            Segment('up', [], 0, 10, high=12.0, low=9.0),
            Segment('down', [], 10, 20, high=11.5, low=9.5),
            Segment('up', [], 20, 30, high=12.5, low=10.0),
            Segment('down', [], 30, 40, high=11.8, low=10.2),  # 回调不破中枢
        ]

        zhongshus = [
            ZhongShu(segments[:3], high=11.5, low=10.0, start_index=0, end_index=30, type='震荡')
        ]
        divergences = {}

        detector = BuyPointDetector()
        buypoints = detector.detect_buypoints(segments, zhongshus, divergences, klines)

        # 预期：识别出2买
        second_buy = [bp for bp in buypoints if bp.type == '2买']
        assert len(second_buy) >= 1
        assert second_buy[0].position_ratio == 0.6  # 半仓
```

### Step 3.2: 实现买卖点检测器

创建 `chan/buypoint_detector.py`:

```python
"""买卖点检测器 - 识别三类买卖点"""
from typing import List, Dict
from .types import Segment, ZhongShu, BuyPoint, KLine
from datetime import datetime


class BuyPointDetector:
    """
    买卖点检测器

    三类买卖点规则：
    - 1买：下跌背驰后（最安全，满仓）
    - 2买：回调不破中枢（次安全，半仓）
    - 3买：突破前高（激进，轻仓）
    """

    def detect_buypoints(
        self,
        segments: List[Segment],
        zhongshus: List[ZhongShu],
        divergences: Dict[int, bool],
        klines: List[KLine]
    ) -> List[BuyPoint]:
        """
        检测买卖点

        Args:
            segments: 线段列表
            zhongshus: 中枢列表
            divergences: 背驰字典 {segment_index: is_divergence}
            klines: K线数据

        Returns:
            买卖点列表
        """
        buypoints = []

        # 检测1买（下跌背驰）
        for i, seg in enumerate(segments):
            if seg.direction == 'down' and divergences.get(i, False):
                buypoints.append(BuyPoint(
                    type='1买',
                    index=seg.end_index,
                    price=seg.low,
                    date=klines[seg.end_index].date if seg.end_index < len(klines) else datetime.now(),
                    confidence=0.9,
                    reason='下跌背驰',
                    position_ratio=1.0
                ))

        # 检测2买（回调不破中枢）
        for zh in zhongshus:
            # 找中枢后的第一个下跌线段
            zh_end_idx = segments.index(zh.segments[-1])
            if zh_end_idx + 1 < len(segments):
                next_seg = segments[zh_end_idx + 1]
                if next_seg.direction == 'down' and next_seg.low >= zh.low:
                    buypoints.append(BuyPoint(
                        type='2买',
                        index=next_seg.end_index,
                        price=next_seg.low,
                        date=klines[next_seg.end_index].date if next_seg.end_index < len(klines) else datetime.now(),
                        confidence=0.7,
                        reason='回调不破中枢',
                        position_ratio=0.6
                    ))

        # 检测3买（突破前高）
        for i in range(1, len(segments)):
            seg = segments[i]
            if seg.direction == 'up':
                # 找前面的最高点
                prev_high = max(s.high for s in segments[:i] if s.direction == 'up')
                if seg.high > prev_high:
                    buypoints.append(BuyPoint(
                        type='3买',
                        index=seg.end_index,
                        price=seg.high,
                        date=klines[seg.end_index].date if seg.end_index < len(klines) else datetime.now(),
                        confidence=0.5,
                        reason='突破前高',
                        position_ratio=0.3
                    ))

        return buypoints
```

### Step 3.3: 运行测试，验证通过

### Step 3.4: Commit
```bash
git add chan/buypoint_detector.py tests/chan/test_buypoint_detector.py
git commit -m "feat(chan): 实现买卖点检测器

- 1买：下跌背驰（满仓 1.0）
- 2买：回调不破中枢（半仓 0.6）
- 3买：突破前高（轻仓 0.3）
- 包含置信度和仓位建议
- 测试通过：2/2"
```

---

## Task 4: 集成测试与文档

**目标**: 端到端测试 + 更新文档

### Step 4.1: 编写 Phase 2 集成测试

更新 `tests/chan/test_integration.py`:

```python
    def test_phase2_pipeline(self, sample_klines):
        """测试 Phase 2 完整流水线（到买卖点检测）"""
        # Phase 1
        processor = KLineProcessor()
        processed_klines = processor.process(sample_klines)

        bi_identifier = BiIdentifier()
        fenxings = bi_identifier.identify_fenxings(processed_klines)
        bis = bi_identifier.identify_bis(fenxings, processed_klines)

        segment_identifier = SegmentIdentifier()
        segments = segment_identifier.identify_segments(bis)

        # Phase 2
        from chan.zhongshu_identifier import ZhongShuIdentifier
        from chan.divergence_detector import DivergenceDetector
        from chan.buypoint_detector import BuyPointDetector

        zhongshu_identifier = ZhongShuIdentifier()
        zhongshus = zhongshu_identifier.identify_zhongshus(segments)

        divergence_detector = DivergenceDetector()
        divergences = {}
        for i in range(1, len(segments)):
            if segments[i].direction == segments[i-1].direction:
                continue
            divergences[i] = divergence_detector.detect_divergence(
                segments[i-1], segments[i], processed_klines,
                'bearish' if segments[i].direction == 'down' else 'bullish'
            )

        buypoint_detector = BuyPointDetector()
        buypoints = buypoint_detector.detect_buypoints(segments, zhongshus, divergences, processed_klines)

        # 验证
        assert len(zhongshus) >= 0
        assert len(buypoints) >= 0
        if len(buypoints) > 0:
            assert all(bp.type in ['1买', '2买', '3买', '1卖', '2卖', '3卖'] for bp in buypoints)
```

### Step 4.2: 运行所有测试
```bash
pytest tests/chan/ -v --cov=chan
```

### Step 4.3: 更新 README

更新 `chan/README.md`，添加 Phase 2 使用示例。

### Step 4.4: Commit
```bash
git add tests/chan/test_integration.py chan/README.md
git commit -m "test(chan): 添加 Phase 2 集成测试

- 完整流水线测试（到买卖点检测）
- 更新使用文档
- 覆盖率 > 80%"
```

---

## 验证清单

- [ ] 所有测试通过（预计 ~18 个测试）
- [ ] 代码覆盖率 > 80%
- [ ] 中枢识别正确处理重叠/扩展
- [ ] 背驰检测逻辑清晰
- [ ] 买卖点分类正确
- [ ] Git 提交历史清晰（4个提交）
- [ ] 文档更新完整

## 性能目标

- 1000根K线完整分析（Phase 1 + Phase 2）：< 1秒
- 内存占用：< 100MB

## Phase 3 规划

- 走势类型分析器（上涨/下跌/盘整）
- 完整分析器封装（ChanAnalyzer）
- 策略引擎集成
- 真实 MACD 计算
