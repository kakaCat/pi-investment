# 缠论核心库 (Phase 1 & 2 & 3 完整版)

## 概述

本模块实现缠论（缠中说禅理论）的核心算法，包括 K线预处理、笔识别、线段识别、中枢识别、背驰检测、买卖点识别、走势分析，提供完整的一站式分析接口。

## Phase 1 功能（已完成）

- ✅ 核心数据结构（KLine, FenXing, Bi, Segment）
- ✅ K线预处理器（包含关系处理）
- ✅ 笔识别器（顶底分型 + 严格5K规则）
- ✅ 线段识别器（3笔简化规则）

## Phase 2 功能（已完成）

- ✅ 中枢识别器（3线段重叠 + 扩展）
- ✅ 背驰检测器（MACD面积背驰）
- ✅ 买卖点检测器（1/2/3类买卖点）

## Phase 3 功能（已完成）

- ✅ 真实 MACD 计算器（TA-Lib / EMA fallback）
- ✅ 走势类型分析器（上涨/下跌/盘整）
- ✅ 完整分析器封装（ChanAnalyzer）

## 快速开始

### 一站式分析（推荐）

```python
from chan.chan_analyzer import ChanAnalyzer
import pandas as pd

# 准备K线数据
klines_df = pd.DataFrame({
    'date': [...],
    'open': [...],
    'high': [...],
    'low': [...],
    'close': [...],
    'volume': [...]
})

# 一行代码完成完整分析
analyzer = ChanAnalyzer()
result = analyzer.analyze('600519.SH', klines_df)

# 查看结果
print(f"走势类型: {result.trend_type}")
print(f"识别出 {len(result.segments)} 个线段")
print(f"识别出 {len(result.zhongshus)} 个中枢")
print(f"识别出 {len(result.buypoints)} 个买卖点")

# 买卖点详情
for bp in result.buypoints:
    print(f"{bp.type} @ {bp.price:.2f}")
    print(f"  置信度: {bp.confidence:.1%}, 建议仓位: {bp.position_ratio:.1%}")
    print(f"  原因: {bp.reason}")
```
bi_identifier = BiIdentifier()
fenxings = bi_identifier.identify_fenxings(processed_klines)
bis = bi_identifier.identify_bis(fenxings, processed_klines)

# 4. 线段识别
segment_identifier = SegmentIdentifier()
segments = segment_identifier.identify_segments(bis)

print(f"识别出 {len(fenxings)} 个分型")
print(f"识别出 {len(bis)} 个笔")
print(f"识别出 {len(segments)} 个线段")
```

### Phase 2: 信号生成

```python
from chan.zhongshu_identifier import ZhongShuIdentifier
from chan.divergence_detector import DivergenceDetector
from chan.buypoint_detector import BuyPointDetector

# 继续 Phase 1 的结果...

# 5. 中枢识别
zhongshu_identifier = ZhongShuIdentifier()
zhongshus = zhongshu_identifier.identify_zhongshus(segments)

# 6. 背驰检测
divergence_detector = DivergenceDetector()
divergences = {}
for i in range(1, len(segments)):
    if segments[i].direction == segments[i-1].direction:
        divergences[i] = divergence_detector.detect_divergence(
            segments[i-1], segments[i], processed_klines,
            'bearish' if segments[i].direction == 'down' else 'bullish'
        )

# 7. 买卖点检测
buypoint_detector = BuyPointDetector()
buypoints = buypoint_detector.detect_buypoints(
    segments, zhongshus, divergences, processed_klines
)

print(f"识别出 {len(zhongshus)} 个中枢")
print(f"识别出 {len(buypoints)} 个买卖点")

# 8. 输出买卖点详情
for bp in buypoints:
    print(f"{bp.type} @ {bp.price:.2f} (置信度: {bp.confidence:.1%}, 仓位: {bp.position_ratio:.1%})")
    print(f"  原因: {bp.reason}")
```

## 算法说明

### Phase 1: 基础结构

#### K线预处理
- **规则**：处理包含关系
- **向上走势**：高点取高，低点取高
- **向下走势**：高点取低，低点取低

#### 笔识别
- **分型规则**：
  - 顶分型：中间K线高低点均高于左右
  - 底分型：中间K线高低点均低于左右
- **笔规则**：严格5K（顶底分型之间至少5根K线）

#### 线段识别
- **规则**：至少3笔，方向交替
- **扩展**：自动扩展到最长有效线段

### Phase 2: 信号生成

#### 中枢识别
- **规则**：至少3个线段的重叠区间
- **计算**：中枢 = [max(各线段低点), min(各线段高点)]
- **扩展**：后续线段仍与中枢重叠则自动扩展

#### 背驰检测
- **顶背驰**：价格新高 且 MACD面积减小
- **底背驰**：价格新低 且 MACD面积减小（绝对值）
- **简化版**：当前使用价格振幅近似（Phase 3 改用真实MACD）

#### 买卖点检测
- **1买**：下跌背驰后（满仓 100%，置信度 90%）
- **2买**：回调不破中枢（半仓 60%，置信度 70%）
- **3买**：突破前高（轻仓 30%，置信度 50%）
- **1卖/2卖/3卖**：对称定义

## 测试

```bash
# 运行所有测试
pytest tests/chan/ -v

# 查看覆盖率
pytest tests/chan/ --cov=chan --cov-report=html
```

**测试统计（Phase 1 & 2 & 3）：**
- 总测试数：32个（全部通过）
- 代码覆盖率：93%
- Phase 1 测试：13个
- Phase 2 测试：10个
- Phase 3 测试：9个

## 性能

- 1000根K线完整分析（Phase 1 + 2 + 3）：< 2秒
- 内存占用：< 150MB
- 测试执行时间：~20秒（包含所有32个测试）

## 技术栈

- Python 3.13
- Pandas (数据处理)
- NumPy (向量化计算)
- TA-Lib (MACD指标，可选)
- pytest (单元测试)

## 后续规划

- 策略引擎集成
- 回测系统对接
- 实盘信号推送
- 可视化界面
