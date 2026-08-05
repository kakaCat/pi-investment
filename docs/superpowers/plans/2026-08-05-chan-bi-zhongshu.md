# 缠论笔中枢重构实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 弃用已证错误的线段层，以笔中枢为核心重写买卖点（含卖点）/背驰/走势判断。

**Architecture:** 复用 KLineProcessor/BiIdentifier（分型+笔质量尚可）；新增 BiZhongShuIdentifier（3 笔重叠）、BiDivergenceDetector（进出笔组 MACD 面积）、BuyPointDetector 重写（6 类买卖点对称）、BiTrendAnalyzer（中枢数量与方向）；ChanAnalyzer 重排流水线，segments 输出 []。外层（scan/蒸馏/service）做最小适配。

**Tech Stack:** Python 3.13 / polars / pytest（quant_test 库自动切换）；部署在主工作区 venv nohup。

**Spec:** `docs/superpowers/specs/2026-08-05-chan-bi-zhongshu-redesign.md`

**关键背景（实现者必读）：**
- 工作目录必须在 worktree（`git worktree add .claude/worktrees/chan-bi-zhongshu -b feat/chan-bi-zhongshu`），建后 `git rebase main`
- venv 在主工作区：`/Users/mac/Documents/ai/pi-investment/quantsys-v2/venv/bin/python -m pytest`
- 既有契约：`Bi` dataclass 字段为 `direction('up'/'down'), start_fenxing, end_fenxing, high, low, length, price_change`；`FenXing` 字段 `type, index, price, date, klines`；`BuyPoint` 字段 `type, index, price, date, confidence, reason, stop_loss, stop_profit, position_ratio`
- `MACDCalculator.calculate_area(klines: List[KLine], start_index: int, end_index: int) -> float` 已存在（复用）
- 单元测试直接构造 `Bi`/`FenXing` 对象，不碰 K 线合成（包含处理不可控）；只有 divergence 测试需要构造 `List[KLine]` 供 MACD 计算
- ChanService/Scan/Distiller 的既有契约见 `memory: chan-memory-loop`（symbol 无后缀、Signal ORM 对象、trade_date 字符串）

---

### Task 1: BiZhongShu 类型 + 笔中枢识别器

**Files:**
- Modify: `quantsys-v2/domain/chan/types.py`（追加 BiZhongShu）
- Create: `quantsys-v2/domain/chan/bi_zhongshu_identifier.py`
- Test: `quantsys-v2/tests/chan/test_bi_zhongshu_identifier.py`（新建）

- [ ] **Step 1: 写失败测试**

新建 `quantsys-v2/tests/chan/test_bi_zhongshu_identifier.py`：

```python
"""笔中枢识别器测试——3 笔重叠成中枢、延续、独立多中枢"""
from datetime import datetime, timedelta
import pytest

from domain.chan.types import Bi, FenXing
from domain.chan.bi_zhongshu_identifier import BiZhongShuIdentifier


def _fx(idx: int, price: float, ftype: str) -> FenXing:
    return FenXing(type=ftype, index=idx, price=price,
                   date=datetime(2026, 1, 1) + timedelta(days=idx), klines=[])


def _bi(direction: str, start_idx: int, end_idx: int,
        low: float, high: float) -> Bi:
    """direction='up': 底→顶；'down': 顶→底"""
    if direction == 'up':
        s, e = _fx(start_idx, low, 'bottom'), _fx(end_idx, high, 'top')
    else:
        s, e = _fx(start_idx, high, 'top'), _fx(end_idx, low, 'bottom')
    return Bi(direction=direction, start_fenxing=s, end_fenxing=e,
              high=high, low=low, length=end_idx - start_idx + 1,
              price_change=(e.price - s.price) / s.price)


class TestBiZhongShuIdentifier:
    def test_three_overlapping_bis_form_zhongshu(self):
        """下上下 3 笔重叠 → 中枢成立，ZG=min(高点), ZD=max(低点)"""
        bis = [
            _bi('down', 0, 5, low=9.0, high=11.0),
            _bi('up', 5, 10, low=9.5, high=10.5),
            _bi('down', 10, 15, low=9.2, high=10.8),
        ]
        result = BiZhongShuIdentifier().identify(bis)
        assert len(result) == 1
        zs = result[0]
        assert zs.zg == pytest.approx(10.5)   # min(11.0, 10.5, 10.8)
        assert zs.zd == pytest.approx(9.5)    # max(9.0, 9.5, 9.2)
        assert zs.gg == pytest.approx(11.0)
        assert zs.dd == pytest.approx(9.0)
        assert zs.bi_count == 3

    def test_no_overlap_no_zhongshu(self):
        """3 笔无重叠（ZD > ZG）→ 不成立"""
        bis = [
            _bi('down', 0, 5, low=9.0, high=10.0),
            _bi('up', 5, 10, low=9.5, high=12.0),
            _bi('down', 10, 15, low=11.0, high=13.0),
        ]
        assert BiZhongShuIdentifier().identify(bis) == []

    def test_extension_merges_overlapping_bis(self):
        """第 4 笔仍与 [ZD, ZG] 重叠 → 并入中枢；第 5 笔完全脱离 → 中枢结束"""
        bis = [
            _bi('down', 0, 5, low=9.0, high=11.0),
            _bi('up', 5, 10, low=9.5, high=10.5),
            _bi('down', 10, 15, low=9.2, high=10.8),
            _bi('up', 15, 20, low=9.6, high=10.4),   # 仍重叠 → 并入
            _bi('down', 20, 25, low=7.0, high=8.0),  # 完全在 ZD 下 → 结束
        ]
        result = BiZhongShuIdentifier().identify(bis)
        assert len(result) == 1
        assert result[0].bi_count == 4
        assert result[0].zg == pytest.approx(10.5)  # ZG/ZD 由前 3 笔锁定，不随延续改变
        assert result[0].zd == pytest.approx(9.5)

    def test_two_independent_zhongshus(self):
        """两组重叠笔 → 两个中枢"""
        bis = [
            _bi('down', 0, 5, low=9.0, high=11.0),
            _bi('up', 5, 10, low=9.5, high=10.5),
            _bi('down', 10, 15, low=9.2, high=10.8),
            _bi('up', 15, 20, low=14.0, high=16.0),   # 脱离中枢1
            _bi('down', 20, 25, low=14.5, high=15.5),
            _bi('up', 25, 30, low=14.2, high=15.8),
            _bi('down', 30, 35, low=14.4, high=15.6),
        ]
        result = BiZhongShuIdentifier().identify(bis)
        assert len(result) == 2
        assert result[1].zg == pytest.approx(15.5)
        assert result[1].zd == pytest.approx(14.4)

    def test_less_than_3_bis(self):
        assert BiZhongShuIdentifier().identify([]) == []
        assert BiZhongShuIdentifier().identify([_bi('up', 0, 5, 9.0, 10.0)]) == []
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd quantsys-v2 && /Users/mac/Documents/ai/pi-investment/quantsys-v2/venv/bin/python -m pytest tests/chan/test_bi_zhongshu_identifier.py -q -p no:cacheprovider --no-cov`
Expected: ERROR（模块不存在）

- [ ] **Step 3: 实现**

`quantsys-v2/domain/chan/types.py` 追加：

```python
@dataclass
class BiZhongShu:
    """笔中枢（连续 3+ 笔的价格重叠区）

    ZG/ZD 由前 3 笔锁定；延续笔不改变 ZG/ZD。
    """
    zg: float                       # 中枢上沿 = min(前3笔高点)
    zd: float                       # 中枢下沿 = max(前3笔低点)
    gg: float                       # 成员笔极值高
    dd: float                       # 成员笔极值低
    start_bi_idx: int               # 首笔在笔列表中的下标
    end_bi_idx: int                 # 末笔下标
    bis: List[Bi] = field(default_factory=list)
    type: str = '笔中枢'

    @property
    def bi_count(self) -> int:
        return len(self.bis)

    @property
    def start_index(self) -> int:
        """首笔起点 K 线索引"""
        return self.bis[0].start_fenxing.index

    @property
    def end_index(self) -> int:
        """末笔终点 K 线索引"""
        return self.bis[-1].end_fenxing.index
```

新建 `quantsys-v2/domain/chan/bi_zhongshu_identifier.py`：

```python
"""笔中枢识别器——连续 3+ 笔重叠构成中枢（弃用线段层后的核心结构）"""
from typing import List
from .types import Bi, BiZhongShu


class BiZhongShuIdentifier:
    """
    规则：
    - 成立：连续 3 笔重叠，ZG = min(三笔高点) > ZD = max(三笔低点)
    - 延续：后续笔仍与 [ZD, ZG] 有重叠（bi.low < ZG 且 bi.high > ZD）则并入
    - ZG/ZD 由前 3 笔锁定，延续不修改
    """

    def identify(self, bis: List[Bi]) -> List[BiZhongShu]:
        if len(bis) < 3:
            return []

        zhongshus: List[BiZhongShu] = []
        i = 0
        while i <= len(bis) - 3:
            window = bis[i:i + 3]
            zg = min(b.high for b in window)
            zd = max(b.low for b in window)

            if zg > zd:
                members = list(window)
                j = i + 3
                while j < len(bis):
                    b = bis[j]
                    if b.low < zg and b.high > zd:   # 仍有重叠 → 延续
                        members.append(b)
                        j += 1
                    else:
                        break
                zhongshus.append(BiZhongShu(
                    zg=zg, zd=zd,
                    gg=max(b.high for b in members),
                    dd=min(b.low for b in members),
                    start_bi_idx=i, end_bi_idx=j - 1,
                    bis=members,
                ))
                i = j
            else:
                i += 1

        return zhongshus
```

- [ ] **Step 4: 跑测试确认通过**

Run: `... pytest tests/chan/test_bi_zhongshu_identifier.py -q`
Expected: 5 passed

- [ ] **Step 5: Commit**

```bash
git add quantsys-v2/domain/chan/types.py quantsys-v2/domain/chan/bi_zhongshu_identifier.py quantsys-v2/tests/chan/test_bi_zhongshu_identifier.py
git commit -m "feat(chan): BiZhongShu 笔中枢识别器——连续 3 笔重叠+延续，弃线段层核心结构"
```

---

### Task 2: BiDivergenceDetector 进出笔组背驰

**Files:**
- Create: `quantsys-v2/domain/chan/bi_divergence_detector.py`
- Test: `quantsys-v2/tests/chan/test_bi_divergence_detector.py`（新建）

- [ ] **Step 1: 写失败测试**

新建 `quantsys-v2/tests/chan/test_bi_divergence_detector.py`：

```python
"""笔组背驰检测测试——围绕中枢的进入/离开笔组 MACD 面积比较"""
from datetime import datetime, timedelta
import pytest

from domain.chan.types import KLine, Bi, FenXing
from domain.chan.bi_divergence_detector import BiDivergenceDetector


def _klines_from_closes(closes):
    """由收盘价序列构造 KLine 列表（open=昨收，high/low 包络 close）"""
    out = []
    prev = closes[0]
    for i, c in enumerate(closes):
        out.append(KLine(
            date=datetime(2026, 1, 1) + timedelta(days=i),
            open=prev, high=max(prev, c) + 0.01, low=min(prev, c) - 0.01,
            close=c, volume=1000.0, original_indices=[i],
        ))
        prev = c
    return out


def _down_bi(start_idx: int, end_idx: int, high: float, low: float) -> Bi:
    s = FenXing(type='top', index=start_idx, price=high,
                date=datetime(2026, 1, 1) + timedelta(days=start_idx), klines=[])
    e = FenXing(type='bottom', index=end_idx, price=low,
                date=datetime(2026, 1, 1) + timedelta(days=end_idx), klines=[])
    return Bi(direction='down', start_fenxing=s, end_fenxing=e,
              high=high, low=low, length=end_idx - start_idx + 1,
              price_change=(low - high) / high)


class TestBiDivergence:
    def test_bottom_divergence_weaker_second_drop(self):
        """第二段下跌更浅（|MACD 面积|更小）且价格新低 → 底背驰"""
        # 0-19: 急跌 100→70；20-29: 反弹 70→85；30-49: 缓跌 85→68（更慢更长，面积更小，低点更低）
        closes = ([100 - 1.5 * i for i in range(20)]
                  + [70 + 1.5 * i for i in range(10)]
                  + [85 - 0.85 * i for i in range(20)])
        klines = _klines_from_closes(closes)
        enter = _down_bi(0, 19, high=100.0, low=70.0)
        leave = _down_bi(29, 48, high=85.0, low=68.0)

        det = BiDivergenceDetector()
        assert det.is_bottom_divergence(enter, leave, klines) is True

    def test_no_divergence_when_second_drop_stronger(self):
        """第二段下跌更急（面积更大）→ 非背驰"""
        closes = ([100 - 0.5 * i for i in range(20)]   # 缓跌
                  + [90 + 1.5 * i for i in range(10)]  # 反弹
                  + [105 - 3.0 * i for i in range(20)])  # 急跌
        klines = _klines_from_closes(closes)
        enter = _down_bi(0, 19, high=100.0, low=90.5)
        leave = _down_bi(29, 48, high=105.0, low=48.0)

        det = BiDivergenceDetector()
        assert det.is_bottom_divergence(enter, leave, klines) is False


def _up_bi(start_idx: int, end_idx: int, low: float, high: float) -> Bi:
    s = FenXing(type='bottom', index=start_idx, price=low,
                date=datetime(2026, 1, 1) + timedelta(days=start_idx), klines=[])
    e = FenXing(type='top', index=end_idx, price=high,
                date=datetime(2026, 1, 1) + timedelta(days=end_idx), klines=[])
    return Bi(direction='up', start_fenxing=s, end_fenxing=e,
              high=high, low=low, length=end_idx - start_idx + 1,
              price_change=(high - low) / low)


class TestTopDivergence:
    def test_top_divergence_weaker_second_rise(self):
        """第二段上涨更弱（面积更小）且价格新高 → 顶背驰"""
        closes = ([50 + 2.0 * i for i in range(20)]    # 急涨 50→88
                  + [88 - 1.0 * i for i in range(10)]  # 回落 88→79
                  + [79 + 0.6 * i for i in range(20)]) # 缓涨 79→90.4（更慢，新高）
        klines = _klines_from_closes(closes)
        enter = _up_bi(0, 19, low=50.0, high=88.0)
        leave = _up_bi(29, 48, low=79.0, high=90.4)

        det = BiDivergenceDetector()
        assert det.is_top_divergence(enter, leave, klines) is True

    def test_no_top_divergence_when_stronger(self):
        """第二段上涨更急 → 非顶背驰"""
        closes = ([50 + 0.5 * i for i in range(20)]
                  + [60 - 1.0 * i for i in range(10)]
                  + [50 + 3.0 * i for i in range(20)])
        klines = _klines_from_closes(closes)
        enter = _up_bi(0, 19, low=50.0, high=59.5)
        leave = _up_bi(29, 48, low=50.0, high=107.0)

        det = BiDivergenceDetector()
        assert det.is_top_divergence(enter, leave, klines) is False
```

- [ ] **Step 2: 跑测试确认失败**

Run: `... pytest tests/chan/test_bi_divergence_detector.py -q`
Expected: ERROR（模块不存在）

- [ ] **Step 3: 实现**

新建 `quantsys-v2/domain/chan/bi_divergence_detector.py`：

```python
"""笔组背驰检测器——比较进入/离开笔组的 MACD 面积"""
from typing import List
from .types import Bi, KLine
from .macd_calculator import MACDCalculator


class BiDivergenceDetector:
    """
    底背驰：离开下跌笔最低价 < 进入下跌笔最低价 且 |离开面积| < |进入面积|
    顶背驰：离开上涨笔最高价 > 进入上涨笔最高价 且 |离开面积| < |进入面积|
    """

    def __init__(self):
        self._macd = MACDCalculator()

    def _area(self, bi: Bi, klines: List[KLine]) -> float:
        return self._macd.calculate_area(
            klines, bi.start_fenxing.index, bi.end_fenxing.index)

    def is_bottom_divergence(self, enter: Bi, leave: Bi, klines: List[KLine]) -> bool:
        if enter.direction != 'down' or leave.direction != 'down':
            return False
        if leave.low >= enter.low:   # 必须价格新低
            return False
        return abs(self._area(leave, klines)) < abs(self._area(enter, klines))

    def is_top_divergence(self, enter: Bi, leave: Bi, klines: List[KLine]) -> bool:
        if enter.direction != 'up' or leave.direction != 'up':
            return False
        if leave.high <= enter.high:  # 必须价格新高
            return False
        return abs(self._area(leave, klines)) < abs(self._area(enter, klines))
```

- [ ] **Step 4: 跑测试确认通过**

Run: `... pytest tests/chan/test_bi_divergence_detector.py -q`
Expected: 4 passed（若合成序列 MACD 面积关系与预期不符，调整斜率使面积关系成立——判定逻辑本身不变）

- [ ] **Step 5: Commit**

```bash
git add quantsys-v2/domain/chan/bi_divergence_detector.py quantsys-v2/tests/chan/test_bi_divergence_detector.py
git commit -m "feat(chan): BiDivergenceDetector 笔组背驰——进出笔组 MACD 面积+价格极值双条件"
```

---

### Task 3: BuyPointDetector 重写（6 类买卖点）

**Files:**
- Modify: `quantsys-v2/domain/chan/buypoint_detector.py`（整体重写）
- Test: `quantsys-v2/tests/chan/test_buypoint_detector_bi.py`（新建）

- [ ] **Step 1: 写失败测试**

新建 `quantsys-v2/tests/chan/test_buypoint_detector_bi.py`：

```python
"""买卖点检测器（笔中枢版）测试——6 类买卖点触发与不触发"""
from datetime import datetime, timedelta
from unittest.mock import patch
import pytest

from domain.chan.types import Bi, FenXing, BiZhongShu
from domain.chan.buypoint_detector import BuyPointDetector


def _fx(idx, price, ftype):
    return FenXing(type=ftype, index=idx, price=price,
                   date=datetime(2026, 1, 1) + timedelta(days=idx), klines=[])


def _bi(direction, start_idx, end_idx, low, high):
    if direction == 'up':
        s, e = _fx(start_idx, low, 'bottom'), _fx(end_idx, high, 'top')
    else:
        s, e = _fx(start_idx, high, 'top'), _fx(end_idx, low, 'bottom')
    return Bi(direction=direction, start_fenxing=s, end_fenxing=e,
              high=high, low=low, length=end_idx - start_idx + 1,
              price_change=(e.price - s.price) / s.price)


def _zs(zg, zd, start_bi_idx, end_bi_idx, bis):
    return BiZhongShu(
        zg=zg, zd=zd,
        gg=max(b.high for b in bis[start_bi_idx:end_bi_idx + 1]),
        dd=min(b.low for b in bis[start_bi_idx:end_bi_idx + 1]),
        start_bi_idx=start_bi_idx, end_bi_idx=end_bi_idx,
        bis=bis[start_bi_idx:end_bi_idx + 1],
    )


def _klines(n=60):
    from domain.chan.types import KLine
    return [KLine(date=datetime(2026, 1, 1) + timedelta(days=i),
                  open=10.0, high=10.1, low=9.9, close=10.0,
                  volume=1000.0, original_indices=[i]) for i in range(n)]


class TestFirstBuySell:
    def test_first_buy_on_bottom_divergence(self):
        """中枢后离开下跌笔背驰 → 1买"""
        bis = [
            _bi('down', 0, 5, low=8.0, high=12.0),    # 0: 进入下跌笔
            _bi('up', 5, 10, low=9.0, high=11.0),     # 1: 中枢3笔
            _bi('down', 10, 15, low=9.5, high=10.5),  # 2
            _bi('up', 15, 20, low=9.8, high=10.2),    # 3
            _bi('down', 20, 25, low=7.5, high=10.0),  # 4: 离开下跌笔（新低）
        ]
        zs = [_zs(zg=10.5, zd=9.8, start_bi_idx=1, end_bi_idx=3, bis=bis)]
        with patch.object(BuyPointDetector, '_is_bottom_div', return_value=True):
            pts = BuyPointDetector().detect(bis, zs, _klines())
        first_buys = [p for p in pts if p.type == '1买']
        assert len(first_buys) == 1
        assert first_buys[0].price == pytest.approx(7.5)
        assert first_buys[0].confidence == 0.9

    def test_no_first_buy_without_divergence(self):
        """背驰不成立 → 无 1买"""
        bis = [
            _bi('down', 0, 5, low=8.0, high=12.0),
            _bi('up', 5, 10, low=9.0, high=11.0),
            _bi('down', 10, 15, low=9.5, high=10.5),
            _bi('up', 15, 20, low=9.8, high=10.2),
            _bi('down', 20, 25, low=7.5, high=10.0),
        ]
        zs = [_zs(zg=10.5, zd=9.8, start_bi_idx=1, end_bi_idx=3, bis=bis)]
        with patch.object(BuyPointDetector, '_is_bottom_div', return_value=False):
            pts = BuyPointDetector().detect(bis, zs, _klines())
        assert [p for p in pts if p.type == '1买'] == []

    def test_first_buy_fallback_without_zhongshu(self):
        """无中枢：最近两条下跌笔比较，背驰 → 1买"""
        bis = [
            _bi('down', 0, 5, low=8.0, high=12.0),
            _bi('up', 5, 10, low=9.0, high=11.0),
            _bi('down', 10, 15, low=7.5, high=10.5),
        ]
        with patch.object(BuyPointDetector, '_is_bottom_div', return_value=True):
            pts = BuyPointDetector().detect(bis, [], _klines())
        assert len([p for p in pts if p.type == '1买']) == 1

    def test_first_sell_symmetric(self):
        """中枢后离开上涨笔顶背驰 → 1卖"""
        bis = [
            _bi('up', 0, 5, low=8.0, high=12.0),
            _bi('down', 5, 10, low=9.0, high=11.0),
            _bi('up', 10, 15, low=9.5, high=10.5),
            _bi('down', 15, 20, low=9.8, high=10.2),
            _bi('up', 20, 25, low=10.0, high=13.0),   # 离开上涨笔（新高）
        ]
        zs = [_zs(zg=10.2, zd=9.5, start_bi_idx=1, end_bi_idx=3, bis=bis)]
        with patch.object(BuyPointDetector, '_is_top_div', return_value=True):
            pts = BuyPointDetector().detect(bis, zs, _klines())
        sells = [p for p in pts if p.type == '1卖']
        assert len(sells) == 1
        assert sells[0].price == pytest.approx(13.0)


class TestSecondPoints:
    def test_second_buy_holds_above_first_low(self):
        """1买后回抽不破前低 → 2买"""
        bis = [
            _bi('down', 0, 5, low=8.0, high=12.0),
            _bi('down', 5, 10, low=7.0, high=10.0),   # 假设 1买在此末端（低 7.0）
            _bi('up', 10, 15, low=7.2, high=9.5),     # 反弹笔
            _bi('down', 15, 20, low=7.3, high=9.0),   # 回抽，低点 7.3 > 7.0
        ]
        with patch.object(BuyPointDetector, '_is_bottom_div', return_value=True):
            pts = BuyPointDetector().detect(bis, [], _klines())
        second = [p for p in pts if p.type == '2买']
        assert len(second) == 1
        assert second[0].price == pytest.approx(7.3)
        assert second[0].confidence == 0.7

    def test_no_second_buy_when_breaks_first_low(self):
        """回抽跌破 1买低点 → 无 2买"""
        bis = [
            _bi('down', 0, 5, low=8.0, high=12.0),
            _bi('down', 5, 10, low=7.0, high=10.0),
            _bi('up', 10, 15, low=7.2, high=9.5),
            _bi('down', 15, 20, low=6.8, high=9.0),   # 6.8 < 7.0 破前低
        ]
        with patch.object(BuyPointDetector, '_is_bottom_div', return_value=True):
            pts = BuyPointDetector().detect(bis, [], _klines())
        assert [p for p in pts if p.type == '2买'] == []


class TestThirdPoints:
    def test_third_buy_pullback_stays_above_zg(self):
        """上笔离开中枢（>ZG），回抽低点 > ZG → 3买"""
        bis = [
            _bi('down', 0, 5, low=9.0, high=11.0),    # 0-2: 中枢
            _bi('up', 5, 10, low=9.5, high=10.5),
            _bi('down', 10, 15, low=9.2, high=10.8),
            _bi('up', 15, 20, low=10.0, high=12.5),   # 3: 离开（12.5 > ZG 10.5）
            _bi('down', 20, 25, low=10.6, high=12.0), # 4: 回抽 10.6 > ZG 10.5
        ]
        zs = [_zs(zg=10.5, zd=9.5, start_bi_idx=0, end_bi_idx=2, bis=bis)]
        with patch.object(BuyPointDetector, '_is_bottom_div', return_value=False), \
             patch.object(BuyPointDetector, '_is_top_div', return_value=False):
            pts = BuyPointDetector().detect(bis, zs, _klines())
        third = [p for p in pts if p.type == '3买']
        assert len(third) == 1
        assert third[0].price == pytest.approx(10.6)
        assert third[0].confidence == 0.5

    def test_no_third_buy_when_pullback_enters_zhongshu(self):
        """回抽落入中枢（低点 ≤ ZG）→ 无 3买"""
        bis = [
            _bi('down', 0, 5, low=9.0, high=11.0),
            _bi('up', 5, 10, low=9.5, high=10.5),
            _bi('down', 10, 15, low=9.2, high=10.8),
            _bi('up', 15, 20, low=10.0, high=12.5),
            _bi('down', 20, 25, low=10.2, high=12.0),  # 10.2 < ZG 10.5 落入
        ]
        zs = [_zs(zg=10.5, zd=9.5, start_bi_idx=0, end_bi_idx=2, bis=bis)]
        with patch.object(BuyPointDetector, '_is_bottom_div', return_value=False), \
             patch.object(BuyPointDetector, '_is_top_div', return_value=False):
            pts = BuyPointDetector().detect(bis, zs, _klines())
        assert [p for p in pts if p.type == '3买'] == []

    def test_third_sell_symmetric(self):
        """下笔跌破中枢（<ZD），回拉高点 < ZD → 3卖"""
        bis = [
            _bi('up', 0, 5, low=9.0, high=11.0),
            _bi('down', 5, 10, low=9.5, high=10.5),
            _bi('up', 10, 15, low=9.2, high=10.8),
            _bi('down', 15, 20, low=8.0, high=10.0),   # 跌破（8.0 < ZD 9.2）
            _bi('up', 20, 25, low=8.5, high=9.0),      # 回拉 9.0 < ZD 9.2
        ]
        zs = [_zs(zg=10.8, zd=9.2, start_bi_idx=0, end_bi_idx=2, bis=bis)]
        with patch.object(BuyPointDetector, '_is_bottom_div', return_value=False), \
             patch.object(BuyPointDetector, '_is_top_div', return_value=False):
            pts = BuyPointDetector().detect(bis, zs, _klines())
        sells = [p for p in pts if p.type == '3卖']
        assert len(sells) == 1
        assert sells[0].price == pytest.approx(9.0)


class TestEnableFilter:
    def test_enable_types_filter(self):
        """enable_types 过滤生效"""
        bis = [
            _bi('down', 0, 5, low=8.0, high=12.0),
            _bi('up', 5, 10, low=9.0, high=11.0),
            _bi('down', 10, 15, low=7.5, high=10.5),
        ]
        with patch.object(BuyPointDetector, '_is_bottom_div', return_value=True):
            pts = BuyPointDetector().detect(bis, [], _klines(), enable_types=['2买'])
        assert pts == []
```

- [ ] **Step 2: 跑测试确认失败**

Run: `... pytest tests/chan/test_buypoint_detector_bi.py -q`
Expected: FAIL（detect 签名/行为不符）

- [ ] **Step 3: 重写 buypoint_detector.py**

```python
"""买卖点检测器（笔中枢版）——1/2/3 买 + 1/2/3 卖对称

定义（spec: 2026-08-05-chan-bi-zhongshu-redesign.md）：
- 1买：最后中枢后离开下跌笔底背驰；无中枢退化为最近两下跌笔比较
- 2买：1买后反弹笔成立，回抽下跌笔低点 > 1买低点
- 3买：上笔离开中枢（高 > ZG）后，回抽下跌笔低点 > ZG
- 1卖/2卖/3卖完全对称
"""
from typing import List, Optional
from datetime import datetime
from .types import Bi, BiZhongShu, BuyPoint, KLine
from .bi_divergence_detector import BiDivergenceDetector


class BuyPointDetector:
    def __init__(self):
        self._divergence = BiDivergenceDetector()

    # 供测试 patch 的薄封装
    def _is_bottom_div(self, enter: Bi, leave: Bi, klines: List[KLine]) -> bool:
        return self._divergence.is_bottom_divergence(enter, leave, klines)

    def _is_top_div(self, enter: Bi, leave: Bi, klines: List[KLine]) -> bool:
        return self._divergence.is_top_divergence(enter, leave, klines)

    def detect(
        self,
        bis: List[Bi],
        zhongshus: List[BiZhongShu],
        klines: List[KLine],
        enable_types: Optional[List[str]] = None,
    ) -> List[BuyPoint]:
        points: List[BuyPoint] = []
        points += self._detect_first_buy(bis, zhongshus, klines)
        points += self._detect_first_sell(bis, zhongshus, klines)
        points += self._detect_second_buy(bis, points)
        points += self._detect_second_sell(bis, points)
        points += self._detect_third_buy(bis, zhongshus)
        points += self._detect_third_sell(bis, zhongshus)
        if enable_types:
            points = [p for p in points if p.type in enable_types]
        return points

    # ---------- 1买/1卖 ----------

    def _enter_leave_pairs(self, bis, zhongshus, direction):
        """(进入笔, 离开笔) 候选对：围绕每个中枢；无中枢时退化为最近两同向笔"""
        same = [b for b in bis if b.direction == direction]
        pairs = []
        if zhongshus:
            for zs in zhongshus:
                enter_candidates = [b for b in bis[:zs.start_bi_idx] if b.direction == direction]
                leave_candidates = [b for b in bis[zs.end_bi_idx + 1:] if b.direction == direction]
                if enter_candidates and leave_candidates:
                    pairs.append((enter_candidates[-1], leave_candidates[0]))
        if not pairs and len(same) >= 2:
            pairs.append((same[-2], same[-1]))
        return pairs

    def _detect_first_buy(self, bis, zhongshus, klines) -> List[BuyPoint]:
        out = []
        for enter, leave in self._enter_leave_pairs(bis, zhongshus, 'down'):
            if self._is_bottom_div(enter, leave, klines):
                out.append(BuyPoint(
                    type='1买', index=leave.end_fenxing.index, price=leave.low,
                    date=leave.end_fenxing.date, confidence=0.9,
                    reason='下跌笔组底背驰', position_ratio=1.0,
                ))
        return out

    def _detect_first_sell(self, bis, zhongshus, klines) -> List[BuyPoint]:
        out = []
        for enter, leave in self._enter_leave_pairs(bis, zhongshus, 'up'):
            if self._is_top_div(enter, leave, klines):
                out.append(BuyPoint(
                    type='1卖', index=leave.end_fenxing.index, price=leave.high,
                    date=leave.end_fenxing.date, confidence=0.9,
                    reason='上涨笔组顶背驰', position_ratio=1.0,
                ))
        return out

    # ---------- 2买/2卖 ----------

    def _bi_after(self, bis, kline_index: int, direction: str) -> Optional[Bi]:
        """起点 K 线索引在 kline_index 之后的第一条 direction 笔"""
        for b in bis:
            if b.direction == direction and b.start_fenxing.index >= kline_index:
                return b
        return None

    def _detect_second_buy(self, bis, points) -> List[BuyPoint]:
        out = []
        for p in [p for p in points if p.type == '1买']:
            rebound = self._bi_after(bis, p.index, 'up')       # 反弹笔
            if not rebound:
                continue
            pullback = self._bi_after(bis, rebound.end_fenxing.index, 'down')
            if pullback and pullback.low > p.price:            # 不破 1买低点
                out.append(BuyPoint(
                    type='2买', index=pullback.end_fenxing.index, price=pullback.low,
                    date=pullback.end_fenxing.date, confidence=0.7,
                    reason='回抽不破1买低点', position_ratio=0.6,
                ))
        return out

    def _detect_second_sell(self, bis, points) -> List[BuyPoint]:
        out = []
        for p in [p for p in points if p.type == '1卖']:
            retreat = self._bi_after(bis, p.index, 'down')
            if not retreat:
                continue
            rally = self._bi_after(bis, retreat.end_fenxing.index, 'up')
            if rally and rally.high < p.price:                 # 不破 1卖高点
                out.append(BuyPoint(
                    type='2卖', index=rally.end_fenxing.index, price=rally.high,
                    date=rally.end_fenxing.date, confidence=0.7,
                    reason='回拉不破1卖高点', position_ratio=0.6,
                ))
        return out

    # ---------- 3买/3卖 ----------

    def _detect_third_buy(self, bis, zhongshus) -> List[BuyPoint]:
        out = []
        for zs in zhongshus:
            leave = self._bi_after(bis, bis[zs.end_bi_idx].end_fenxing.index, 'up')
            if not leave or leave.high <= zs.zg:               # 未离开中枢
                continue
            pullback = self._bi_after(bis, leave.end_fenxing.index, 'down')
            if pullback and pullback.low > zs.zg:              # 回抽不入中枢
                out.append(BuyPoint(
                    type='3买', index=pullback.end_fenxing.index, price=pullback.low,
                    date=pullback.end_fenxing.date, confidence=0.5,
                    reason='离开中枢回抽不入', position_ratio=0.3,
                ))
        return out

    def _detect_third_sell(self, bis, zhongshus) -> List[BuyPoint]:
        out = []
        for zs in zhongshus:
            leave = self._bi_after(bis, bis[zs.end_bi_idx].end_fenxing.index, 'down')
            if not leave or leave.low >= zs.zd:
                continue
            rally = self._bi_after(bis, leave.end_fenxing.index, 'up')
            if rally and rally.high < zs.zd:                   # 回拉不入中枢
                out.append(BuyPoint(
                    type='3卖', index=rally.end_fenxing.index, price=rally.high,
                    date=rally.end_fenxing.date, confidence=0.5,
                    reason='跌破中枢回拉不入', position_ratio=0.3,
                ))
        return out
```

- [ ] **Step 4: 跑测试确认通过**

Run: `... pytest tests/chan/test_buypoint_detector_bi.py -q`
Expected: 10 passed

- [ ] **Step 5: Commit**

```bash
git add quantsys-v2/domain/chan/buypoint_detector.py quantsys-v2/tests/chan/test_buypoint_detector_bi.py
git commit -m "feat(chan): BuyPointDetector 笔中枢重写——1/2/3买+1/2/3卖对称，3买改回抽不入中枢（修追顶）"
```

---

### Task 4: BiTrendAnalyzer 走势类型

**Files:**
- Create: `quantsys-v2/domain/chan/bi_trend_analyzer.py`
- Test: `quantsys-v2/tests/chan/test_bi_trend_analyzer.py`（新建）

- [ ] **Step 1: 写失败测试**

```python
"""走势类型分析（笔中枢版）测试"""
from datetime import datetime, timedelta
import pytest

from domain.chan.types import Bi, FenXing, BiZhongShu
from domain.chan.bi_trend_analyzer import BiTrendAnalyzer


def _fx(idx, price, ftype):
    return FenXing(type=ftype, index=idx, price=price,
                   date=datetime(2026, 1, 1) + timedelta(days=idx), klines=[])


def _bi(direction, start_idx, end_idx, low, high):
    if direction == 'up':
        s, e = _fx(start_idx, low, 'bottom'), _fx(end_idx, high, 'top')
    else:
        s, e = _fx(start_idx, high, 'top'), _fx(end_idx, low, 'bottom')
    return Bi(direction=direction, start_fenxing=s, end_fenxing=e,
              high=high, low=low, length=1, price_change=0.0)


def _zs(zg, zd, bis):
    return BiZhongShu(zg=zg, zd=zd, gg=zg, dd=zd,
                      start_bi_idx=0, end_bi_idx=2, bis=bis)


class TestBiTrend:
    def test_two_rising_zhongshus_is_uptrend(self):
        bis = [_bi('up', 0, 5, 9, 10)] * 3
        zs = [_zs(10.5, 9.5, bis), _zs(13.0, 12.0, bis)]
        assert BiTrendAnalyzer().analyze(bis, zs) == '上涨'

    def test_two_falling_zhongshus_is_downtrend(self):
        bis = [_bi('down', 0, 5, 9, 10)] * 3
        zs = [_zs(13.0, 12.0, bis), _zs(10.5, 9.5, bis)]
        assert BiTrendAnalyzer().analyze(bis, zs) == '下跌'

    def test_single_zhongshu_is_consolidation(self):
        bis = [_bi('up', 0, 5, 9, 10)] * 3
        assert BiTrendAnalyzer().analyze(bis, [_zs(10.5, 9.5, bis)]) == '盘整'

    def test_no_zhongshu_fallback_to_bi_extremes(self):
        up_bis = [_bi('up', 0, 5, 9.0, 10.0), _bi('up', 10, 15, 10.5, 12.0)]
        assert BiTrendAnalyzer().analyze(up_bis, []) == '上涨'
        down_bis = [_bi('down', 0, 5, 9.0, 12.0), _bi('down', 10, 15, 7.0, 10.0)]
        assert BiTrendAnalyzer().analyze(down_bis, []) == '下跌'
```

- [ ] **Step 2: 跑测试确认失败**

Run: `... pytest tests/chan/test_bi_trend_analyzer.py -q`
Expected: ERROR

- [ ] **Step 3: 实现**

```python
"""走势类型分析（笔中枢版）"""
from typing import List, Literal
from .types import Bi, BiZhongShu


class BiTrendAnalyzer:
    """
    - ≥2 中枢依次上移（后 ZD > 前 ZD 且后 ZG > 前 ZG）→ 上涨；依次下移 → 下跌
    - 1 中枢 → 盘整
    - 0 中枢 → 退化为首尾同向笔高低点比较
    """

    def analyze(
        self,
        bis: List[Bi],
        zhongshus: List[BiZhongShu],
    ) -> Literal['上涨', '下跌', '盘整']:
        if len(zhongshus) >= 2:
            last, prev = zhongshus[-1], zhongshus[-2]
            if last.zd > prev.zd and last.zg > prev.zg:
                return '上涨'
            if last.zd < prev.zd and last.zg < prev.zg:
                return '下跌'
            return '盘整'

        if len(zhongshus) == 1:
            return '盘整'

        # 无中枢退化：比较首笔与末笔高低点
        if len(bis) < 2:
            return '盘整'
        first, last_b = bis[0], bis[-1]
        high_up = last_b.high > first.high
        low_up = last_b.low > first.low
        if high_up and low_up:
            return '上涨'
        if not high_up and not low_up:
            return '下跌'
        return '盘整'
```

- [ ] **Step 4: 跑测试确认通过**

Run: `... pytest tests/chan/test_bi_trend_analyzer.py -q`
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add quantsys-v2/domain/chan/bi_trend_analyzer.py quantsys-v2/tests/chan/test_bi_trend_analyzer.py
git commit -m "feat(chan): BiTrendAnalyzer——双中枢方向定趋势，单中枢盘整，无中枢退化首尾笔比较"
```

---

### Task 5: ChanAnalyzer 重排流水线 + Service 适配

**Files:**
- Modify: `quantsys-v2/domain/chan/chan_analyzer.py`（重排）
- Modify: `quantsys-v2/domain/chan/segment_identifier.py`（deprecated 标注）
- Modify: `quantsys-v2/application/services/chan_service.py`（zhongshu 格式化 + segments=[]）
- Test: `quantsys-v2/tests/chan/test_chan_analyzer.py`（更新契约）
- Test: `quantsys-v2/tests/services/test_chan_service.py`（更新 zhongshu 断言）

- [ ] **Step 1: 更新测试（先红）**

`quantsys-v2/tests/chan/test_chan_analyzer.py` 整体替换为：

```python
"""缠论完整分析器测试（笔中枢版流水线）"""
import pytest
import pandas as pd
from datetime import datetime, timedelta
from domain.chan.chan_analyzer import ChanAnalyzer


class TestChanAnalyzer:
    @pytest.fixture
    def sample_klines(self):
        data = []
        for i in range(100):
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
        analyzer = ChanAnalyzer()
        result = analyzer.analyze('600519.SH', sample_klines)

        assert result.symbol == '600519.SH'
        assert result.klines is not None
        assert result.fenxings is not None
        assert result.bis is not None
        assert result.segments == []            # 线段层已弃用，契约返回空
        assert result.zhongshus is not None     # 笔中枢列表（BiZhongShu）
        assert result.buypoints is not None
        assert result.trend_type in ['上涨', '下跌', '盘整']

    def test_analyze_with_buypoint_filter(self, sample_klines):
        analyzer = ChanAnalyzer()
        result = analyzer.analyze('600519.SH', sample_klines,
                                  enable_buypoints=['1买', '2买'])
        if len(result.buypoints) > 0:
            assert all(bp.type in ['1买', '2买'] for bp in result.buypoints)
```

`quantsys-v2/tests/services/test_chan_service.py` 中 `_mock_analyzer_with_buypoints` 的 `result.zhongshus` 已经是 `[]`，无需改；但 service 的 `_format_zhongshu` 要适配 BiZhongShu——追加契约测试：

```python
    @patch('application.services.chan_service.AgentKnowledgeORMRepository')
    @patch('application.services.chan_service.KlineORMRepository')
    def test_format_bi_zhongshu(self, mock_repo_cls, mock_know_cls):
        """BiZhongShu 格式化：high=ZG, low=ZD, type='笔中枢', bi_count"""
        from unittest.mock import MagicMock
        from domain.chan.types import BiZhongShu, Bi, FenXing
        from datetime import datetime as _dt

        mock_repo_cls.return_value.get_daily_klines.return_value = _make_klines()
        mock_know_cls.return_value.get_by_domain.return_value = []

        fx = lambda i, p, t: FenXing(type=t, index=i, price=p, date=_dt(2026, 1, 1), klines=[])
        bi = Bi(direction='up', start_fenxing=fx(0, 9.0, 'bottom'),
                end_fenxing=fx(5, 10.0, 'top'), high=10.0, low=9.0, length=6, price_change=0.1)
        zs = BiZhongShu(zg=10.5, zd=9.5, gg=11.0, dd=9.0,
                        start_bi_idx=0, end_bi_idx=2, bis=[bi, bi, bi])

        result_mock = MagicMock()
        result_mock.trend_type, result_mock.bis, result_mock.segments = '盘整', [], []
        result_mock.zhongshus, result_mock.buypoints, result_mock.klines = [zs], [], []

        service = ChanService()
        service.analyzer = MagicMock()
        service.analyzer.analyze.return_value = result_mock

        out = service.analyze('600519.SH')
        assert out['segments'] == []
        z = out['zhongshus'][0]
        assert z['high'] == 10.5 and z['low'] == 9.5
        assert z['type'] == '笔中枢'
        assert z['bi_count'] == 3
```

- [ ] **Step 2: 跑测试确认失败**

Run: `... pytest tests/chan/test_chan_analyzer.py tests/services/test_chan_service.py -q`
Expected: FAIL（segments 非 [] / zhongshu 格式化缺 bi_count）

- [ ] **Step 3: 重排 ChanAnalyzer**

`quantsys-v2/domain/chan/chan_analyzer.py` 整体替换为：

```python
"""缠论完整分析器 - 一站式分析接口（笔中枢版流水线，2026-08-05 重构）"""
from typing import List
import pandas as pd
from dataclasses import dataclass, field
from .types import KLine, FenXing, Bi, Segment, BiZhongShu, BuyPoint
from .kline_processor import KLineProcessor
from .bi_identifier import BiIdentifier
from .bi_zhongshu_identifier import BiZhongShuIdentifier
from .buypoint_detector import BuyPointDetector
from .bi_trend_analyzer import BiTrendAnalyzer


@dataclass
class ChanAnalysisResult:
    """缠论分析结果"""
    symbol: str
    klines: List[KLine]
    fenxings: List[FenXing]
    bis: List[Bi]
    segments: List[Segment]          # 契约保留，恒为空（线段层已弃用）
    zhongshus: List[BiZhongShu]
    buypoints: List[BuyPoint]
    trend_type: str
    divergences: dict = field(default_factory=dict)


class ChanAnalyzer:
    """缠论完整分析器（笔中枢版）"""

    def __init__(self):
        self.kline_processor = KLineProcessor()
        self.bi_identifier = BiIdentifier()
        self.zhongshu_identifier = BiZhongShuIdentifier()
        self.buypoint_detector = BuyPointDetector()
        self.trend_analyzer = BiTrendAnalyzer()

    def analyze(
        self,
        symbol: str,
        klines_df: pd.DataFrame,
        enable_buypoints: List[str] = None,
    ) -> ChanAnalysisResult:
        if enable_buypoints is None:
            enable_buypoints = ['1买', '2买', '3买', '1卖', '2卖', '3卖']

        processed_klines = self.kline_processor.process(klines_df)
        fenxings = self.bi_identifier.identify_fenxings(processed_klines)
        bis = self.bi_identifier.identify_bis(fenxings, processed_klines)

        zhongshus = self.zhongshu_identifier.identify(bis)
        buypoints = self.buypoint_detector.detect(
            bis, zhongshus, processed_klines, enable_types=enable_buypoints)
        trend_type = self.trend_analyzer.analyze(bis, zhongshus)

        return ChanAnalysisResult(
            symbol=symbol,
            klines=processed_klines,
            fenxings=fenxings,
            bis=bis,
            segments=[],               # 线段层已弃用（2026-08-05，原算法退化）
            zhongshus=zhongshus,
            buypoints=buypoints,
            trend_type=trend_type,
            divergences={},
        )
```

`quantsys-v2/domain/chan/segment_identifier.py` 头部 docstring 改为：

```python
"""线段识别器 - 识别线段

⚠️ DEPRECATED（2026-08-05）：该"3笔交替"简化规则已证退化——笔天然交替，
整年笔序列连成 1-2 个"线段"，致中枢全灭/买卖点失真。
流水线已切换笔中枢（bi_zhongshu_identifier），本文件仅为历史参考保留，勿用于新代码。
"""
```

`quantsys-v2/application/services/chan_service.py` 的 `_format_zhongshu` 改为：

```python
    def _format_zhongshu(self, zhongshu) -> Dict[str, Any]:
        """格式化笔中枢（BiZhongShu）"""
        return {
            "high": float(zhongshu.zg),
            "low": float(zhongshu.zd),
            "start_index": zhongshu.start_index,
            "end_index": zhongshu.end_index,
            "type": zhongshu.type,
            "bi_count": zhongshu.bi_count
        }
```

（删除旧 `"segment_count": len(zhongshu.segments)` 字段。）

- [ ] **Step 4: 跑测试确认通过**

Run: `... pytest tests/chan/ tests/services/test_chan_service.py -q`
Expected: 全部 PASS

- [ ] **Step 5: Commit**

```bash
git add quantsys-v2/domain/chan/chan_analyzer.py quantsys-v2/domain/chan/segment_identifier.py quantsys-v2/application/services/chan_service.py quantsys-v2/tests/chan/test_chan_analyzer.py quantsys-v2/tests/services/test_chan_service.py
git commit -m "feat(chan): ChanAnalyzer 切笔中枢流水线——segments 契约置空，zhongshu 格式化适配 BiZhongShu，旧线段算法标 deprecated"
```

---

### Task 6: Scan 落库支持卖点

**Files:**
- Modify: `quantsys-v2/application/services/chan_scan_service.py`
- Test: `quantsys-v2/tests/services/test_chan_scan_service.py`（追加）

- [ ] **Step 1: 追加失败测试**

```python
    @patch('application.services.chan_scan_service.SignalORMRepository')
    @patch('application.services.chan_scan_service.StockPoolORMRepository')
    @patch('application.services.chan_scan_service.ChanService')
    def test_sell_buypoint_written_as_sell(self, mock_chan, mock_pool, mock_sig):
        """卖点落库：action='sell'，strategy_id='chan_1卖'"""
        mock_pool.return_value.get_all.return_value = _pools()[:1]
        mock_pool.return_value.get_all.return_value[0]['members'] = [{'symbol': '600519.SH', 'name': '贵州茅台'}]
        mock_chan.return_value.analyze.return_value = _analyze_result(bp_type='1卖')
        mock_sig.return_value.create_signal.return_value = 102

        result = ChanScanService().scan()
        assert result['signals_written'] == 1
        call = mock_sig.return_value.create_signal.call_args[0][0]
        assert call['action'] == 'sell'
        assert call['strategy_id'] == 'chan_1卖'
```

- [ ] **Step 2: 跑测试确认失败**

Run: `... pytest tests/services/test_chan_scan_service.py -q`
Expected: FAIL（1卖被 _BUY_TYPES 过滤，signals_written=0）

- [ ] **Step 3: 实现**

`chan_scan_service.py`：

```python
# 全部 6 类买卖点（笔中枢重构后卖点已对称实现）
_SIGNAL_TYPE_ACTION = {
    '1买': 'buy', '2买': 'buy', '3买': 'buy',
    '1卖': 'sell', '2卖': 'sell', '3卖': 'sell',
}
```

scan 循环内替换过滤与落库：

```python
                for bp in result.get('buypoints') or []:
                    action = _SIGNAL_TYPE_ACTION.get(bp['type'])
                    if not action or bp['date'] != latest_date:
                        continue
                    signal_id = self._signal_repo.create_signal({
                        'signal_date': bp['date'],
                        'symbol': symbol,
                        'name': name,
                        'action': action,
                        'strategy_id': f"chan_{bp['type']}",
                        'price': bp['price'],
                        'confidence': round(bp['confidence'] * 100, 1),
                        'reason': f"缠论{bp['type']}：{bp['reason']}",
                        'status': 'pending',
                    })
```

（删除 `_BUY_TYPES`。）

- [ ] **Step 4: 跑测试确认通过 + Commit**

Run: `... pytest tests/services/test_chan_scan_service.py -q` → 5 passed

```bash
git add quantsys-v2/application/services/chan_scan_service.py quantsys-v2/tests/services/test_chan_scan_service.py
git commit -m "feat(chan): scan 落库支持卖点——action 按类型映射 buy/sell，strategy_id=chan_1卖 等"
```

---

### Task 7: 蒸馏器支持 sell 判定

**Files:**
- Modify: `quantsys-v2/application/services/chan_knowledge_distiller.py`
- Test: `quantsys-v2/tests/services/test_chan_knowledge_distiller.py`（追加）

- [ ] **Step 1: 追加失败测试**

```python
    @patch('application.services.chan_knowledge_distiller.AgentKnowledgeORMRepository')
    @patch('application.services.chan_knowledge_distiller.KlineORMRepository')
    @patch('application.services.chan_knowledge_distiller.SignalORMRepository')
    def test_sell_signal_wins_when_price_falls(self, mock_sig, mock_kline, mock_know):
        """sell 信号：跌=胜（与 verify_judgments 对称）"""
        base = date(2026, 6, 1)
        mock_sig.return_value.get_signals_by_date_range.return_value = [
            {'symbol': '600519', 'signal_date': base, 'strategy_id': 'chan_1卖', 'action': 'sell'},
            {'symbol': '000858', 'signal_date': base, 'strategy_id': 'chan_1卖', 'action': 'sell'},
        ]
        # 600519 跌（胜）、000858 涨（负）
        mock_kline.return_value.get_daily_klines.side_effect = [
            _klines(100.0, 90.0), _klines(100.0, 110.0),
        ]
        upserts = []
        mock_know.return_value.upsert_knowledge.side_effect = lambda **kw: upserts.append(kw)

        result = ChanKnowledgeDistiller(window_days=20, lookback_days=90).distill()
        assert result['strategies_distilled'] == 1
        assert upserts[0]['validation_count'] == 2
        assert upserts[0]['success_count'] == 1
```

- [ ] **Step 2: 跑测试确认失败**

Run: `... pytest tests/services/test_chan_knowledge_distiller.py -q`
Expected: FAIL（sell 被 action='buy' 过滤，distilled=0）

- [ ] **Step 3: 实现**

`chan_knowledge_distiller.py` 的过滤与判定改为：

```python
        all_signals = self._signal_repo.get_signals_by_date_range(start, end)
        chan_signals = [s for s in all_signals
                        if str(_sig_get(s, 'strategy_id') or '').startswith('chan_')
                        and _sig_get(s, 'action') in ('buy', 'sell')]

        stats: Dict[str, Dict[str, Any]] = {}
        excluded = 0
        for s in chan_signals:
            sig_date = _sig_get(s, 'signal_date')
            if isinstance(sig_date, str):
                sig_date = datetime.strptime(sig_date[:10], '%Y-%m-%d').date()
            ret = self._future_return(_sig_get(s, 'symbol'), sig_date)
            if ret is None:
                excluded += 1
                continue
            action = _sig_get(s, 'action')
            win = (ret > 0) if action == 'buy' else (ret < 0)  # sell & 跌 = 胜
            st = stats.setdefault(_sig_get(s, 'strategy_id'), {'wins': 0, 'returns': []})
            st['returns'].append(ret)
            if win:
                st['wins'] += 1
```

- [ ] **Step 4: 跑测试确认通过 + Commit**

Run: `... pytest tests/services/test_chan_knowledge_distiller.py -q` → 4 passed

```bash
git add quantsys-v2/application/services/chan_knowledge_distiller.py quantsys-v2/tests/services/test_chan_knowledge_distiller.py
git commit -m "feat(chan): 蒸馏器支持 sell 信号——sell & 跌 = 胜，与 verify_judgments 判定对称"
```

---

### Task 8: 回归 + 合并 + 部署 + 新旧胜率对比

**Files:** 无新增（流程任务）

- [ ] **Step 1: 全量 chan 回归**

Run: `... pytest tests/chan tests/services/test_chan_service.py tests/services/test_chan_scan_service.py tests/services/test_chan_scan_task.py tests/services/test_chan_knowledge_distiller.py -q`
Expected: 全 PASS

- [ ] **Step 2: 真实数据 sanity**

```bash
PYTHONPATH=. venv/bin/python -c "
from application.services.chan_scan_service import ChanScanService
from application.services.chan_service import ChanService
svc, chan = ChanScanService(), ChanService()
import collections
c = collections.Counter()
for s in svc._pool_symbols()[:12]:
    r = chan.analyze(s['symbol'])
    c['zhongshus>0'] += bool(r['zhongshus'])
    for bp in r['buypoints']: c[bp['type']] += 1
print(dict(c))
"
```
Expected: 多数股票 zhongshus>0；2买/3买/卖点出现（旧实现一年 0 个 2买）

- [ ] **Step 3: 合并回 main 并推送**（merge-back 模式：update-ref + cp + git add）

- [ ] **Step 4: 重启 5001 + daemon**

- [ ] **Step 5: 清旧信号重跑回填 + 蒸馏，对比新旧胜率**

```sql
DELETE FROM quant.signals WHERE strategy_id LIKE 'chan_%';
DELETE FROM quant.agent_knowledge WHERE domain='chan_theory';
```
然后重跑回填脚本与 `ChanKnowledgeDistiller(...).distill()`，记录新旧胜率对比写入最终报告

---

## Self-Review 记录

**Spec 覆盖对照：**
- 笔中枢定义/延续/锁定 → Task 1 ✅
- 进出笔组背驰（含无中枢退化）→ Task 2 + Task 3 `_enter_leave_pairs` ✅
- 6 类买卖点定义/confidence/仓位 → Task 3 ✅
- 走势类型 → Task 4 ✅
- segments=[] / zhongshu 格式化 / deprecated → Task 5 ✅
- scan sell 落库 → Task 6 ✅
- 蒸馏 sell 判定 → Task 7 ✅
- 部署后新旧胜率对比 → Task 8 ✅

**类型一致性：** BiZhongShu(zg/zd/gg/dd/start_bi_idx/end_bi_idx/bis/type/bi_count/start_index/end_index) 在 Task 1 定义，Task 3/4/5 全部对齐；`_is_bottom_div`/`_is_top_div` patch 点在 Task 3 定义与测试一致；BuyPoint 字段与既有 dataclass 一致。
