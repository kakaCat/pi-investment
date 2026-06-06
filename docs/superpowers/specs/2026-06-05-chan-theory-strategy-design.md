# 缠论量化策略设计文档

**版本**: 1.0  
**日期**: 2026-06-05  
**作者**: AI Agent  
**状态**: 设计完成，待实现

---

## 1. 概述

### 1.1 项目背景

缠论（缠中说禅理论）是一套完整的技术分析理论体系，包括笔、线段、中枢、走势类型、背驰、买卖点等核心概念。本项目旨在将缠论理论量化实现，构建一套可回测、可执行的交易策略系统。

### 1.2 设计目标

- **完整性**：实现缠论核心概念（笔、线段、中枢、走势类型、背驰、三类买卖点）
- **准确性**：严格遵循缠论定义，混合严格版和实战简化版
- **可用性**：提供完整交易方案（信号+仓位+止损+止盈）
- **性能**：1000根K线分析耗时 < 2秒
- **可测试**：单元测试覆盖率 > 80%

### 1.3 技术选型

- **编程语言**：Python 3.13
- **数据处理**：Pandas, NumPy（向量化计算）
- **技术指标**：TA-Lib（MACD等）
- **数据源**：日线K线数据（通过akshare）
- **架构模式**：分层架构 + 管道模式

### 1.4 实现范围

**包含**：
- ✅ 日线级别分析
- ✅ 完整缠论结构识别
- ✅ 三类买卖点检测
- ✅ MACD面积背驰判断
- ✅ 完整交易方案输出
- ✅ 策略回测支持

**不包含（未来扩展）**：
- ❌ 多周期联立分析
- ❌ 实时分钟级数据
- ❌ 可视化图表生成
- ❌ WebSocket实时推送

---

## 2. 需求分析

### 2.1 核心需求

| 需求项 | 选择方案 | 说明 |
|--------|---------|------|
| 实现层级 | 完整版（C） | 笔、线段、中枢、走势类型、背驰、买卖点全部实现 |
| 数据粒度 | 单周期日线（A） | 仅日线，不涉及分钟线 |
| 识别标准 | 混合版（C） | 笔严格5K，线段简化，包含关系严格 |
| 中枢定义 | 线段中枢（C） | 3线段重叠，处理扩展和移动 |
| 买卖点 | 可配置（C） | 支持1/2/3类买卖点，MACD面积背驰 |
| 走势类型 | 混合方案（C） | 三类识别，一层分解，不强求完美 |
| 策略输出 | 完整交易方案（B） | 信号+仓位+止损+止盈+理由 |

### 2.2 用户场景

**场景1：分析单只股票**
```python
service = ChanAnalysisService()
result = await service.analyze_stock('600519.SH')
# 输出：当前走势结构、最新买卖点、完整分析结果
```

**场景2：批量扫描股票池**
```python
results = await service.batch_scan(['600519.SH', '000858.SZ'])
# 输出：有信号的股票列表，按置信度排序
```

**场景3：策略回测**
```python
strategy = StrategyChan(enable_buypoints=['1买', '2买'])
backtest_result = await backtest.run(strategy, '600519.SH', '2024-01-01', '2024-12-31')
# 输出：年化收益、最大回撤、夏普比率等
```

---

## 3. 架构设计

### 3.1 模块分层

```
quantsys-v2/
├── chan/                              # 缠论核心库（新增）
│   ├── __init__.py
│   ├── types.py                      # 数据结构定义
│   ├── kline_processor.py            # K线预处理（包含关系）
│   ├── bi_identifier.py              # 笔识别器
│   ├── segment_identifier.py         # 线段识别器
│   ├── zhongshu_identifier.py        # 中枢识别器
│   ├── trend_analyzer.py             # 走势类型分析
│   ├── divergence_detector.py        # 背驰检测器
│   ├── buypoint_detector.py          # 买卖点检测器
│   └── chan_engine.py                # 缠论分析引擎（统一入口）
│
├── strategies/
│   └── strategy_chan.py              # 缠论交易策略
│
├── services/
│   └── chan_analysis_service.py      # 缠论分析服务（API层）
│
├── api/routes/
│   └── chan.py                        # HTTP端点
│
└── tests/chan/
    ├── test_kline_processor.py
    ├── test_bi_identifier.py
    ├── test_segment_identifier.py
    ├── test_zhongshu_identifier.py
    ├── test_trend_analyzer.py
    ├── test_divergence_detector.py
    ├── test_buypoint_detector.py
    ├── test_chan_engine.py
    └── fixtures/
        ├── sample_klines.json
        └── expected_results.json
```

### 3.2 数据流

```
日线K线数据
    ↓
K线预处理（包含关系处理）
    ↓
笔识别（顶底分型 + 5K规则）
    ↓
线段识别（3笔 + 方向一致）
    ↓
中枢识别（3线段重叠）
    ↓
走势类型判断（上涨/下跌/盘整）
    ↓
背驰检测（MACD面积）
    ↓
买卖点识别（1/2/3类）
    ↓
生成交易信号（仓位+止损+止盈）
```

### 3.3 核心原则

1. **分层独立**：每个模块专注单一职责，可独立测试
2. **数据不可变**：识别结果只读，便于调试和回溯
3. **向量化计算**：优先使用Pandas/NumPy，避免Python循环
4. **严格验证**：每步识别都有完整性校验
5. **可追溯性**：所有数据结构记录原始索引

---

## 4. 核心数据结构

### 4.1 类型定义 (`chan/types.py`)

```python
from dataclasses import dataclass
from typing import List, Literal, Optional
from datetime import datetime

@dataclass
class KLine:
    """K线（处理包含关系后）"""
    date: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float
    original_indices: List[int]  # 原始K线索引（用于回溯）

@dataclass
class FenXing:
    """分型（顶分型/底分型）"""
    type: Literal['top', 'bottom']
    index: int              # 在处理后K线中的索引
    price: float            # 顶/底价格
    date: datetime
    klines: List[KLine]     # 构成分型的3根K线

@dataclass
class Bi:
    """笔"""
    direction: Literal['up', 'down']
    start_fenxing: FenXing
    end_fenxing: FenXing
    high: float
    low: float
    length: int             # 包含的K线数量
    price_change: float     # 涨跌幅

@dataclass
class Segment:
    """线段"""
    direction: Literal['up', 'down']
    bis: List[Bi]           # 构成线段的笔
    start_index: int
    end_index: int
    high: float
    low: float
    
@dataclass
class ZhongShu:
    """中枢"""
    segments: List[Segment]  # 构成中枢的线段（至少3个）
    high: float              # 中枢上沿
    low: float               # 中枢下沿
    start_index: int
    end_index: int
    type: Literal['震荡', '扩展', '移动']
    
@dataclass
class Trend:
    """走势类型"""
    type: Literal['上涨', '下跌', '盘整']
    segments: List[Segment]
    zhongshus: List[ZhongShu]
    start_index: int
    end_index: int

@dataclass
class BuyPoint:
    """买卖点"""
    type: Literal['1买', '2买', '3买', '1卖', '2卖', '3卖']
    index: int
    price: float
    date: datetime
    confidence: float        # 0-1，置信度
    reason: str              # 识别理由
    stop_loss: float         # 建议止损价
    stop_profit: float       # 建议止盈价
    position_ratio: float    # 建议仓位比例（0-1）
    
@dataclass
class ChanAnalysisResult:
    """完整分析结果"""
    symbol: str
    klines: List[KLine]
    fenxings: List[FenXing]
    bis: List[Bi]
    segments: List[Segment]
    zhongshus: List[ZhongShu]
    trends: List[Trend]
    buypoints: List[BuyPoint]
    current_trend: Optional[Trend]
    latest_signal: Optional[BuyPoint]
```

### 4.2 设计要点

- **不可变性**：所有 dataclass 默认只读，业务逻辑中不修改
- **可追溯性**：每个结构都记录原始索引，便于可视化和调试
- **完整性**：包含所有缠论核心概念的数据表示
- **类型安全**：使用 Literal 类型限定枚举值


---

## 5. 核心算法模块

### 5.1 K线预处理器 (`chan/kline_processor.py`)

**职责**：处理K线包含关系

**算法规则**：
- 向上走势：高点取高，低点取高
- 向下走势：高点取低，低点取低
- 初始方向：根据前两根K线判断

**核心方法**：
```python
class KLineProcessor:
    """K线预处理器"""
    
    def process(self, raw_klines: pd.DataFrame, direction: Optional[Literal['up', 'down']] = None) -> List[KLine]:
        """
        处理K线包含关系
        
        Args:
            raw_klines: 原始K线DataFrame
            direction: 初始方向（None则自动判断）
        
        Returns:
            处理后的K线列表（无包含关系）
        
        流程：
        1. 确定初始方向
        2. 逐根扫描，检测包含关系
        3. 包含则合并，不包含则保留
        4. 更新方向（如有必要）
        """
    
    def _has_inclusion(self, k1: KLine, k2: KLine) -> bool:
        """判断两根K线是否有包含关系"""
        return (k1.high >= k2.high and k1.low <= k2.low) or \
               (k2.high >= k1.high and k2.low <= k1.low)
    
    def _merge_klines(self, k1: KLine, k2: KLine, direction: str) -> KLine:
        """合并包含的K线"""
        if direction == 'up':
            return KLine(
                date=k2.date,
                open=k1.open,
                high=max(k1.high, k2.high),
                low=max(k1.low, k2.low),  # 向上取高
                close=k2.close,
                volume=k1.volume + k2.volume,
                original_indices=k1.original_indices + k2.original_indices
            )
        else:
            return KLine(
                date=k2.date,
                open=k1.open,
                high=min(k1.high, k2.high),  # 向下取低
                low=min(k1.low, k2.low),
                close=k2.close,
                volume=k1.volume + k2.volume,
                original_indices=k1.original_indices + k2.original_indices
            )
```

**边界处理**：
- 连续多根K线包含：逐个合并
- 方向不明确：看前两根K线的相对位置
- 涨停/跌停：正常处理，不特殊对待

---

### 5.2 笔识别器 (`chan/bi_identifier.py`)

**职责**：识别顶底分型和笔

**分型规则**：
- 顶分型：中间K线高点>左右K线高点 且 中间K线低点>左右K线低点
- 底分型：中间K线高点<左右K线高点 且 中间K线低点<左右K线低点

**笔规则（严格5K）**：
- 顶底分型之间至少5根K线（含分型的3根）
- 方向明确（上笔/下笔）
- 笔不允许被后续笔"破坏"

**核心方法**：
```python
class BiIdentifier:
    """笔识别器"""
    
    def identify_fenxings(self, klines: List[KLine]) -> List[FenXing]:
        """
        识别顶底分型
        
        流程：
        1. 滑动窗口（3根K线）
        2. 检查顶分型条件
        3. 检查底分型条件
        4. 记录分型位置和价格
        """
    
    def identify_bis(self, fenxings: List[FenXing], klines: List[KLine]) -> List[Bi]:
        """
        识别笔
        
        流程：
        1. 遍历相邻分型对
        2. 检查K线数量（>= 5根）
        3. 验证方向一致性
        4. 验证笔不被破坏
        5. 构建笔对象
        
        验证逻辑：
        - 上笔：底分型→顶分型，顶分型价格 > 底分型价格
        - 下笔：顶分型→底分型，底分型价格 < 顶分型价格
        - K线间距：index_diff >= 4（不含分型本身的3根）
        """
    
    def _is_top_fenxing(self, k1: KLine, k2: KLine, k3: KLine) -> bool:
        """判断是否为顶分型"""
        return (k2.high > k1.high and k2.high > k3.high and
                k2.low > k1.low and k2.low > k3.low)
    
    def _is_bottom_fenxing(self, k1: KLine, k2: KLine, k3: KLine) -> bool:
        """判断是否为底分型"""
        return (k2.high < k1.high and k2.high < k3.high and
                k2.low < k1.low and k2.low < k3.low)
```

---

### 5.3 线段识别器 (`chan/segment_identifier.py`)

**职责**：识别线段

**线段规则（简化版）**：
- 至少3笔构成
- 笔的方向交替（上笔→下笔→上笔 或 下笔→上笔→下笔）
- 后一笔突破前一笔的极值

**核心方法**：
```python
class SegmentIdentifier:
    """线段识别器"""
    
    def identify_segments(self, bis: List[Bi]) -> List[Segment]:
        """
        识别线段
        
        流程：
        1. 遍历笔序列
        2. 找到至少3笔构成的有效线段
        3. 验证方向一致性
        4. 计算线段高低点
        
        简化逻辑：
        - 不做严格的"特征序列分型"判断
        - 只要3笔方向交替即可
        - 实战简化版，提高识别效率
        """
    
    def _is_valid_segment(self, bis: List[Bi]) -> bool:
        """验证是否构成有效线段"""
        if len(bis) < 3:
            return False
        
        # 检查方向交替
        for i in range(1, len(bis)):
            if bis[i].direction == bis[i-1].direction:
                return False
        
        return True
```

---

### 5.4 中枢识别器 (`chan/zhongshu_identifier.py`)

**职责**：识别中枢及其动态变化

**中枢规则**：
- 至少3个线段的重叠区间
- 中枢区间 = [max(各线段低点), min(各线段高点)]
- 要求重叠区间 > 0

**中枢类型**：
- 震荡中枢：标准中枢（3个线段）
- 扩展中枢：新线段与中枢重叠但不离开
- 移动中枢：新旧中枢有重叠

**核心方法**：
```python
class ZhongShuIdentifier:
    """中枢识别器"""
    
    def identify_zhongshus(self, segments: List[Segment]) -> List[ZhongShu]:
        """
        识别中枢
        
        流程：
        1. 滑动窗口（3个线段）
        2. 计算重叠区间
        3. 验证重叠有效性
        4. 分类中枢类型
        """
    
    def detect_zhongshu_extension(self, zhongshu: ZhongShu, new_segment: Segment) -> bool:
        """
        检测中枢扩展
        
        规则：新线段与中枢有重叠但未完全离开
        """
        return (new_segment.low <= zhongshu.high and 
                new_segment.high >= zhongshu.low)
    
    def detect_zhongshu_move(self, old_zhongshu: ZhongShu, new_zhongshu: ZhongShu) -> bool:
        """
        检测中枢移动
        
        规则：新旧中枢有重叠
        """
        return not (old_zhongshu.high < new_zhongshu.low or 
                   new_zhongshu.high < old_zhongshu.low)
    
    def _calculate_overlap(self, segments: List[Segment]) -> tuple[float, float]:
        """计算线段重叠区间"""
        overlap_low = max(seg.low for seg in segments)
        overlap_high = min(seg.high for seg in segments)
        return overlap_low, overlap_high
```

---

### 5.5 走势类型分析器 (`chan/trend_analyzer.py`)

**职责**：判断走势类型

**走势类型规则（一层分解）**：
- 上涨：价格在中枢上方运行，后续中枢高于前一个中枢
- 下跌：价格在中枢下方运行，后续中枢低于前一个中枢
- 盘整：价格在中枢区间内震荡，中枢未移动

**核心方法**：
```python
class TrendAnalyzer:
    """走势类型分析器"""
    
    def analyze_trends(self, segments: List[Segment], zhongshus: List[ZhongShu]) -> List[Trend]:
        """
        分析走势类型
        
        流程：
        1. 遍历线段和中枢
        2. 判断价格与中枢的关系
        3. 判断中枢移动方向
        4. 归类走势类型
        
        一层分解：
        - 不做递归次级别分解
        - 保持一层结构即可
        - 实战简化版
        """
    
    def _classify_trend(self, segments: List[Segment], zhongshus: List[ZhongShu]) -> str:
        """分类走势类型"""
        if len(zhongshus) < 2:
            return '盘整'
        
        # 比较相邻中枢的位置
        if zhongshus[-1].low > zhongshus[-2].high:
            return '上涨'
        elif zhongshus[-1].high < zhongshus[-2].low:
            return '下跌'
        else:
            return '盘整'
```

---

### 5.6 背驰检测器 (`chan/divergence_detector.py`)

**职责**：检测背驰（MACD面积法）

**背驰规则**：
- 比较两段同向走势的MACD柱状图面积
- 价格新高/新低，但MACD面积缩小 → 背驰
- MACD面积 = Σ|MACD柱状图| × 时间区间

**核心方法**：
```python
class DivergenceDetector:
    """背驰检测器"""
    
    def detect_divergence(
        self, 
        segments: List[Segment], 
        klines: List[KLine],
        macd_values: pd.Series
    ) -> Dict[int, bool]:
        """
        检测背驰
        
        流程：
        1. 计算每个线段的MACD面积
        2. 找到同向线段对
        3. 比较价格和MACD面积
        4. 判断是否背驰
        
        Returns:
            {segment_index: is_divergence}
        """
    
    def _calculate_macd_area(self, segment: Segment, macd_hist: pd.Series) -> float:
        """计算MACD面积"""
        start = segment.start_index
        end = segment.end_index
        area = macd_hist[start:end+1].abs().sum()
        return area
    
    def _is_divergence(self, seg1: Segment, seg2: Segment, area1: float, area2: float) -> bool:
        """判断是否背驰"""
        # 上涨背驰：价格新高但MACD面积缩小
        if seg2.high > seg1.high and area2 < area1 * 0.8:
            return True
        # 下跌背驰：价格新低但MACD面积缩小
        if seg2.low < seg1.low and area2 < area1 * 0.8:
            return True
        return False
```

---

### 5.7 买卖点检测器 (`chan/buypoint_detector.py`)

**职责**：识别三类买卖点

**买卖点规则**：
- **1买**：下跌趋势背驰后的第一个买点（最安全）
- **2买**：上涨后回调不破中枢的买点（次安全）
- **3买**：上涨突破前高的买点（激进）
- **1卖、2卖、3卖**：对称定义

**仓位建议**：
- 1买/1卖：满仓（position_ratio = 1.0）
- 2买/2卖：半仓（position_ratio = 0.6）
- 3买/3卖：轻仓（position_ratio = 0.3）

**核心方法**：
```python
class BuyPointDetector:
    """买卖点检测器"""
    
    def detect_buypoints(
        self,
        trends: List[Trend],
        segments: List[Segment],
        zhongshus: List[ZhongShu],
        divergences: Dict[int, bool],
        klines: List[KLine]
    ) -> List[BuyPoint]:
        """
        检测买卖点
        
        流程：
        1. 识别1类买卖点（背驰）
        2. 识别2类买卖点（回调不破中枢）
        3. 识别3类买卖点（突破前高）
        4. 计算置信度
        5. 计算止损止盈
        6. 计算建议仓位
        """
    
    def _detect_first_buy(self, trends: List[Trend], divergences: Dict[int, bool]) -> Optional[BuyPoint]:
        """检测1买"""
        # 找到下跌趋势 + 背驰
        for trend in reversed(trends):
            if trend.type == '下跌' and divergences.get(trend.end_index, False):
                return BuyPoint(
                    type='1买',
                    confidence=0.85,
                    position_ratio=1.0,
                    stop_loss=trend.segments[-1].low * 0.98,
                    stop_profit=self._find_next_zhongshu_high(trend),
                    reason='下跌趋势背驰，出现1买信号'
                )
        return None
    
    def _detect_second_buy(self, trends: List[Trend], zhongshus: List[ZhongShu]) -> Optional[BuyPoint]:
        """检测2买"""
        # 上涨后回调不破中枢
        if len(trends) >= 2 and len(zhongshus) >= 1:
            current_trend = trends[-1]
            prev_zhongshu = zhongshus[-1]
            
            if current_trend.type == '盘整' and current_trend.segments[-1].low > prev_zhongshu.low:
                return BuyPoint(
                    type='2买',
                    confidence=0.7,
                    position_ratio=0.6,
                    stop_loss=prev_zhongshu.low,
                    reason='回调不破中枢，出现2买信号'
                )
        return None
    
    def _detect_third_buy(self, segments: List[Segment]) -> Optional[BuyPoint]:
        """检测3买"""
        # 突破前高
        if len(segments) >= 3:
            if segments[-1].high > segments[-3].high:
                return BuyPoint(
                    type='3买',
                    confidence=0.6,
                    position_ratio=0.3,
                    stop_loss=segments[-2].low,
                    reason='突破前高，出现3买信号'
                )
        return None
```


---

## 6. 缠论分析引擎

### 6.1 统一入口 (`chan/chan_engine.py`)

**职责**：协调所有模块，提供一站式分析接口

```python
class ChanEngine:
    """缠论分析引擎"""
    
    def __init__(self):
        self.kline_processor = KLineProcessor()
        self.bi_identifier = BiIdentifier()
        self.segment_identifier = SegmentIdentifier()
        self.zhongshu_identifier = ZhongShuIdentifier()
        self.trend_analyzer = TrendAnalyzer()
        self.divergence_detector = DivergenceDetector()
        self.buypoint_detector = BuyPointDetector()
    
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
            klines_df: 日线K线数据（columns: date, open, high, low, close, volume）
            enable_buypoints: 启用的买卖点类型
        
        Returns:
            完整分析结果
        
        流程：
        1. K线预处理（包含关系）
        2. 识别分型
        3. 识别笔
        4. 识别线段
        5. 识别中枢
        6. 分析走势类型
        7. 检测背驰
        8. 识别买卖点
        9. 组装结果
        """
        
        # 1. 预处理K线
        processed_klines = self.kline_processor.process(klines_df)
        
        # 2. 识别分型
        fenxings = self.bi_identifier.identify_fenxings(processed_klines)
        
        # 3. 识别笔
        bis = self.bi_identifier.identify_bis(fenxings, processed_klines)
        
        # 4. 识别线段
        segments = self.segment_identifier.identify_segments(bis)
        
        # 5. 识别中枢
        zhongshus = self.zhongshu_identifier.identify_zhongshus(segments)
        
        # 6. 分析走势类型
        trends = self.trend_analyzer.analyze_trends(segments, zhongshus)
        
        # 7. 计算MACD并检测背驰
        macd_df = self._calculate_macd(klines_df)
        divergences = self.divergence_detector.detect_divergence(
            segments, processed_klines, macd_df['macd_hist']
        )
        
        # 8. 识别买卖点
        buypoints = self.buypoint_detector.detect_buypoints(
            trends, segments, zhongshus, divergences, processed_klines
        )
        
        # 过滤买卖点
        buypoints = [bp for bp in buypoints if bp.type in enable_buypoints]
        
        # 9. 组装结果
        return ChanAnalysisResult(
            symbol=symbol,
            klines=processed_klines,
            fenxings=fenxings,
            bis=bis,
            segments=segments,
            zhongshus=zhongshus,
            trends=trends,
            buypoints=buypoints,
            current_trend=trends[-1] if trends else None,
            latest_signal=buypoints[-1] if buypoints else None
        )
    
    def _calculate_macd(self, klines_df: pd.DataFrame) -> pd.DataFrame:
        """
        计算MACD指标
        
        复用项目现有的MACD计算（因子库）
        """
        close = klines_df['close']
        
        # 计算EMA
        ema12 = close.ewm(span=12, adjust=False).mean()
        ema26 = close.ewm(span=26, adjust=False).mean()
        
        # MACD线
        macd = ema12 - ema26
        
        # 信号线
        signal = macd.ewm(span=9, adjust=False).mean()
        
        # 柱状图
        hist = macd - signal
        
        return pd.DataFrame({
            'macd': macd,
            'signal': signal,
            'macd_hist': hist
        })
```

### 6.2 设计要点

- **单一职责**：Engine只负责流程编排，不含算法实现
- **可配置性**：通过参数控制启用的买卖点类型
- **性能考虑**：中间结果可缓存，避免重复计算
- **错误处理**：每步都有异常捕获，部分失败不影响整体

---

## 7. 策略层实现

### 7.1 缠论交易策略 (`strategies/strategy_chan.py`)

**职责**：将缠论分析结果转化为交易信号

```python
class StrategyChan:
    """缠论交易策略"""
    
    def __init__(
        self,
        enable_buypoints: List[str] = ['1买', '2买', '3买'],
        enable_sellpoints: List[str] = ['1卖', '2卖', '3卖'],
        min_confidence: float = 0.6,
        risk_per_trade: float = 0.02  # 单笔风险2%
    ):
        self.engine = ChanEngine()
        self.enable_buypoints = enable_buypoints
        self.enable_sellpoints = enable_sellpoints
        self.min_confidence = min_confidence
        self.risk_per_trade = risk_per_trade
    
    def generate_signals(
        self, 
        symbol: str, 
        klines_df: pd.DataFrame
    ) -> Dict:
        """
        生成交易信号
        
        Returns:
            {
                'symbol': str,
                'action': 'buy' | 'sell' | 'hold',
                'buypoint_type': str,
                'price': float,
                'position_ratio': float,
                'stop_loss': float,
                'stop_profit': float,
                'confidence': float,
                'reason': str,
                'analysis': ChanAnalysisResult
            }
        """
        
        # 执行缠论分析
        analysis = self.engine.analyze(
            symbol=symbol,
            klines_df=klines_df,
            enable_buypoints=self.enable_buypoints + self.enable_sellpoints
        )
        
        # 获取最新信号
        latest_signal = analysis.latest_signal
        
        if not latest_signal or latest_signal.confidence < self.min_confidence:
            return self._hold_signal(symbol, analysis)
        
        # 生成买入信号
        if latest_signal.type in self.enable_buypoints:
            return {
                'symbol': symbol,
                'action': 'buy',
                'buypoint_type': latest_signal.type,
                'price': latest_signal.price,
                'position_ratio': self._calculate_position(latest_signal),
                'stop_loss': latest_signal.stop_loss,
                'stop_profit': latest_signal.stop_profit,
                'confidence': latest_signal.confidence,
                'reason': self._format_reason(latest_signal, analysis),
                'analysis': analysis
            }
        
        # 生成卖出信号
        if latest_signal.type in self.enable_sellpoints:
            return {
                'symbol': symbol,
                'action': 'sell',
                'buypoint_type': latest_signal.type,
                'price': latest_signal.price,
                'position_ratio': 1.0,
                'stop_loss': None,
                'stop_profit': None,
                'confidence': latest_signal.confidence,
                'reason': self._format_reason(latest_signal, analysis),
                'analysis': analysis
            }
        
        return self._hold_signal(symbol, analysis)
    
    def _calculate_position(self, buypoint: BuyPoint) -> float:
        """计算建议仓位"""
        base_ratios = {'1买': 1.0, '2买': 0.6, '3买': 0.3}
        base = base_ratios.get(buypoint.type, 0.5)
        return min(base * buypoint.confidence, 1.0)
    
    def _format_reason(self, buypoint: BuyPoint, analysis: ChanAnalysisResult) -> str:
        """格式化交易理由"""
        return (
            f"检测到{buypoint.type}信号：{buypoint.reason}，"
            f"当前价格{buypoint.price:.2f}元，"
            f"止损{buypoint.stop_loss:.2f}元，止盈{buypoint.stop_profit:.2f}元，"
            f"当前走势：{len(analysis.segments)}个线段，{len(analysis.zhongshus)}个中枢，"
            f"置信度{buypoint.confidence*100:.0f}%"
        )
    
    def _hold_signal(self, symbol: str, analysis: ChanAnalysisResult) -> Dict:
        """无信号，持有"""
        return {
            'symbol': symbol,
            'action': 'hold',
            'reason': '无有效缠论信号，继续观察'
        }
```

### 7.2 回测支持

```python
def execute_strategy(df: pd.DataFrame, params: Dict) -> pd.DataFrame:
    """
    回测入口函数（符合现有框架）
    
    Args:
        df: K线DataFrame
        params: 策略参数
    
    Returns:
        df with 'buy' and 'sell' columns
    """
    strategy = StrategyChan(
        enable_buypoints=params.get('enable_buypoints', ['1买', '2买', '3买']),
        min_confidence=params.get('min_confidence', 0.6)
    )
    
    # 逐日滚动分析（避免未来函数）
    df['buy'] = False
    df['sell'] = False
    
    for i in range(50, len(df)):  # 前50根用于预热
        hist_df = df.iloc[:i+1]
        signal = strategy.generate_signals(params['symbol'], hist_df)
        
        if signal['action'] == 'buy':
            df.loc[i, 'buy'] = True
        elif signal['action'] == 'sell':
            df.loc[i, 'sell'] = True
    
    return df
```

---

## 8. 服务层和API

### 8.1 缠论分析服务 (`services/chan_analysis_service.py`)

```python
class ChanAnalysisService:
    """缠论分析服务"""
    
    def __init__(self):
        self.engine = ChanEngine()
        self.kline_repo = KLineRepository()
    
    async def analyze_stock(
        self,
        symbol: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        enable_buypoints: List[str] = ['1买', '2买', '3买', '1卖', '2卖', '3卖']
    ) -> Dict:
        """
        分析单只股票的缠论结构
        
        Returns:
            {
                'symbol': str,
                'date_range': {...},
                'analysis': {...},
                'current_trend': {...},
                'latest_signal': {...}
            }
        """
        
        # 获取K线数据
        klines_df = await self.kline_repo.get_klines(
            symbol=symbol,
            start_date=start_date,
            end_date=end_date
        )
        
        if klines_df.empty:
            raise ValueError(f"无法获取{symbol}的K线数据")
        
        # 执行分析
        result = self.engine.analyze(symbol, klines_df, enable_buypoints)
        
        # 转换为API友好的格式
        return {
            'symbol': symbol,
            'date_range': {
                'start': klines_df['date'].min().isoformat(),
                'end': klines_df['date'].max().isoformat()
            },
            'analysis': {
                'fenxings_count': len(result.fenxings),
                'bis_count': len(result.bis),
                'segments_count': len(result.segments),
                'zhongshus_count': len(result.zhongshus),
                'trends': [self._trend_to_dict(t) for t in result.trends],
                'buypoints': [self._buypoint_to_dict(bp) for bp in result.buypoints]
            },
            'current_trend': self._trend_to_dict(result.current_trend) if result.current_trend else None,
            'latest_signal': self._buypoint_to_dict(result.latest_signal) if result.latest_signal else None
        }
    
    async def batch_scan(
        self,
        symbols: List[str],
        enable_buypoints: List[str] = ['1买', '2买', '3买']
    ) -> List[Dict]:
        """批量扫描股票池"""
        results = []
        
        for symbol in symbols:
            try:
                analysis = await self.analyze_stock(symbol, enable_buypoints=enable_buypoints)
                if analysis['latest_signal']:
                    results.append({
                        'symbol': symbol,
                        'signal': analysis['latest_signal'],
                        'confidence': analysis['latest_signal']['confidence']
                    })
            except Exception as e:
                logger.warning(f"分析{symbol}失败: {e}")
        
        results.sort(key=lambda x: x['confidence'], reverse=True)
        return results
```

### 8.2 API端点 (`api/routes/chan.py`)

```python
from fastapi import APIRouter, Query

router = APIRouter(prefix="/api/chan", tags=["缠论分析"])

@router.get("/analyze/{symbol}")
async def analyze_stock(
    symbol: str,
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    enable_buypoints: List[str] = Query(['1买', '2买', '3买'])
):
    """分析单只股票的缠论结构"""
    service = ChanAnalysisService()
    return await service.analyze_stock(symbol, start_date, end_date, enable_buypoints)

@router.post("/scan")
async def batch_scan(request: dict):
    """
    批量扫描股票池
    
    Request:
    {
        "symbols": ["600519.SH", "000858.SZ"],
        "enable_buypoints": ["1买", "2买", "3买"],
        "min_confidence": 0.6
    }
    """
    service = ChanAnalysisService()
    results = await service.batch_scan(
        symbols=request['symbols'],
        enable_buypoints=request.get('enable_buypoints', ['1买', '2买', '3买'])
    )
    
    min_confidence = request.get('min_confidence', 0.6)
    return [r for r in results if r['confidence'] >= min_confidence]
```


---

## 9. 测试策略

### 9.1 单元测试结构

```
quantsys-v2/tests/chan/
├── test_kline_processor.py          # K线预处理测试
├── test_bi_identifier.py            # 笔识别测试
├── test_segment_identifier.py       # 线段识别测试
├── test_zhongshu_identifier.py      # 中枢识别测试
├── test_trend_analyzer.py           # 走势分析测试
├── test_divergence_detector.py      # 背驰检测测试
├── test_buypoint_detector.py        # 买卖点检测测试
├── test_chan_engine.py              # 引擎集成测试
└── fixtures/
    ├── sample_klines.json           # 测试数据
    └── expected_results.json        # 预期结果
```

### 9.2 核心测试用例

**K线预处理测试**：
```python
def test_process_inclusion_uptrend():
    """测试向上走势的包含关系处理"""
    raw_klines = [
        {'high': 10, 'low': 8},
        {'high': 9.5, 'low': 8.5},  # 被包含
        {'high': 11, 'low': 9}
    ]
    
    processor = KLineProcessor()
    result = processor.process(raw_klines, direction='up')
    
    assert len(result) == 2
    assert result[1].low == 8.5  # 向上走势，低点取高
```

**笔识别测试**：
```python
def test_identify_bi_strict_5k_rule():
    """测试严格的5K规则"""
    fenxings = [
        FenXing(type='bottom', index=0, price=10.0),
        FenXing(type='top', index=4, price=12.0)  # 只有4根K线
    ]
    
    identifier = BiIdentifier()
    bis = identifier.identify_bis(fenxings, klines)
    
    # 预期：不构成笔（不满足5K规则）
    assert len(bis) == 0
```

**中枢识别测试**：
```python
def test_identify_zhongshu_overlap():
    """测试中枢重叠区间计算"""
    segments = [
        Segment(high=12, low=10),
        Segment(high=11.5, low=9.5),
        Segment(high=12.5, low=10.5)
    ]
    
    identifier = ZhongShuIdentifier()
    zhongshus = identifier.identify_zhongshus(segments)
    
    # 预期：中枢区间 = [max(10, 9.5, 10.5), min(12, 11.5, 12.5)]
    assert len(zhongshus) == 1
    assert zhongshus[0].low == 10.5
    assert zhongshus[0].high == 11.5
```

**背驰检测测试**：
```python
def test_detect_macd_divergence():
    """测试MACD面积背驰"""
    segments = [
        Segment(high=10, low=8, macd_area=100),
        Segment(high=12, low=10, macd_area=80)  # 价格更高但MACD面积更小
    ]
    
    detector = DivergenceDetector()
    divergences = detector.detect_divergence(segments, klines, macd_values)
    
    assert divergences[1] == True
```

**买卖点识别测试**：
```python
def test_detect_1_buy_point():
    """测试1买识别"""
    trends = [Trend(type='下跌', ...)]
    divergences = {segment_index: True}
    
    detector = BuyPointDetector()
    buypoints = detector.detect_buypoints(trends, segments, zhongshus, divergences, klines)
    
    assert len(buypoints) == 1
    assert buypoints[0].type == '1买'
    assert buypoints[0].confidence > 0.7
    assert buypoints[0].position_ratio == 1.0
```

### 9.3 集成测试

**真实数据回测测试**：
```python
@pytest.mark.integration
async def test_real_stock_analysis():
    """使用真实股票数据测试完整流程"""
    service = ChanAnalysisService()
    
    result = await service.analyze_stock(
        symbol='600519.SH',
        start_date='2024-01-01',
        end_date='2024-12-31'
    )
    
    assert 'analysis' in result
    assert result['analysis']['bis_count'] > 0
    assert result['analysis']['segments_count'] > 0
    
    if result['latest_signal']:
        signal = result['latest_signal']
        assert signal['confidence'] > 0
        assert signal['stop_loss'] < signal['price']
        assert signal['stop_profit'] > signal['price']
```

**性能测试**：
```python
@pytest.mark.performance
def test_performance_1000_klines():
    """测试1000根K线的分析性能"""
    import time
    
    klines_df = generate_test_klines(1000)
    engine = ChanEngine()
    
    start = time.time()
    result = engine.analyze('TEST', klines_df)
    elapsed = time.time() - start
    
    assert elapsed < 2.0  # 预期：1000根K线在2秒内完成
    assert len(result.bis) > 0
```

### 9.4 测试数据准备

使用真实历史数据作为测试基准：
- 贵州茅台（600519.SH）2024年数据 - 上涨趋势
- 平安银行（000001.SZ）2024年数据 - 震荡趋势
- 中国中车（601766.SH）2024年数据 - 下跌趋势

覆盖不同市场状态，验证算法鲁棒性。

---

## 10. 性能优化与边界条件

### 10.1 性能优化策略

**向量化计算**：
```python
# ❌ 避免：Python循环
for i in range(len(df)):
    df.loc[i, 'ma5'] = df['close'][i-5:i].mean()

# ✅ 推荐：Pandas向量化
df['ma5'] = df['close'].rolling(window=5).mean()
```

**增量计算**：
```python
def analyze_incremental(
    self, 
    symbol: str, 
    new_klines: pd.DataFrame,
    previous_result: Optional[ChanAnalysisResult] = None
) -> ChanAnalysisResult:
    """
    增量分析（仅处理新K线）
    
    适用场景：实时监控，每日更新
    策略：复用前N-10根K线，只重新计算最近10根
    """
    if previous_result is None:
        return self.analyze(symbol, new_klines)
    
    # 取最近100根K线重新分析（保证准确性）
    recent_klines = new_klines.tail(100)
    return self.analyze(symbol, recent_klines)
```

**并行处理**：
```python
from concurrent.futures import ThreadPoolExecutor

async def batch_scan_parallel(symbols: List[str]) -> List[Dict]:
    """并行扫描多只股票"""
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(analyze_stock, symbol) for symbol in symbols]
        results = [f.result(timeout=30) for f in futures if f.result()]
        return results
```

### 10.2 边界条件处理

**数据不足**：
```python
def analyze(self, symbol: str, klines_df: pd.DataFrame) -> ChanAnalysisResult:
    # 最少需要30根K线
    if len(klines_df) < 30:
        raise ValueError(f"K线数量不足：需要至少30根，实际{len(klines_df)}根")
    
    # 数据完整性检查
    required_columns = ['date', 'open', 'high', 'low', 'close', 'volume']
    missing = set(required_columns) - set(klines_df.columns)
    if missing:
        raise ValueError(f"缺少必要字段：{missing}")
```

**极端市场**：
```python
def identify_bis(self, fenxings: List[FenXing], klines: List[KLine]) -> List[Bi]:
    if len(fenxings) < 2:
        logger.warning("分型数量不足，无法识别笔")
        return []
    
    # 涨停/跌停处理：连续一字板可能导致无分型
    # 策略：放宽分型识别条件或跳过此类股票
```

**中枢退化**：
```python
def identify_zhongshus(self, segments: List[Segment]) -> List[ZhongShu]:
    for i in range(len(segments) - 2):
        seg1, seg2, seg3 = segments[i:i+3]
        
        overlap_high = min(seg1.high, seg2.high, seg3.high)
        overlap_low = max(seg1.low, seg2.low, seg3.low)
        
        # 容差处理：允许1%的误差
        if overlap_high < overlap_low * 0.99:
            continue  # 无重叠，不构成中枢
```

**信号冲突**：
```python
def detect_buypoints(self, ...) -> List[BuyPoint]:
    # 去重：同一位置只保留最强信号
    priority = {'1买': 6, '2买': 5, '3买': 4, '1卖': 3, '2卖': 2, '3卖': 1}
    
    signals_by_index = {}
    for signal in all_signals:
        idx = signal.index
        if idx not in signals_by_index or priority[signal.type] > priority[signals_by_index[idx].type]:
            signals_by_index[idx] = signal
    
    return list(signals_by_index.values())
```

### 10.3 监控与日志

**性能监控**：
```python
@monitor_performance
def analyze(self, symbol: str, klines_df: pd.DataFrame) -> ChanAnalysisResult:
    logger.info(f"开始缠论分析: {symbol}, K线数量: {len(klines_df)}")
    
    processed_klines = self.kline_processor.process(klines_df)
    logger.debug(f"K线预处理完成: {len(processed_klines)}根")
    
    fenxings = self.bi_identifier.identify_fenxings(processed_klines)
    logger.debug(f"分型识别完成: {len(fenxings)}个")
    
    logger.info(f"缠论分析完成: {symbol}, 识别出{len(buypoints)}个买卖点")
    return result
```

---

## 11. 实现优先级

### P0 - 核心基础（第1周）
- [ ] 数据结构定义 (`types.py`)
- [ ] K线预处理器 (`kline_processor.py`)
- [ ] 笔识别器 (`bi_identifier.py`)
- [ ] 线段识别器 (`segment_identifier.py`)
- [ ] 单元测试（覆盖率 > 60%）

### P1 - 核心算法（第2周）
- [ ] 中枢识别器 (`zhongshu_identifier.py`)
- [ ] 背驰检测器 (`divergence_detector.py`)
- [ ] 买卖点检测器 (`buypoint_detector.py`)
- [ ] 单元测试（覆盖率 > 70%）

### P2 - 引擎和策略（第3周）
- [ ] 走势类型分析器 (`trend_analyzer.py`)
- [ ] 缠论分析引擎 (`chan_engine.py`)
- [ ] 缠论交易策略 (`strategy_chan.py`)
- [ ] 集成测试

### P3 - 服务层和API（第4周）
- [ ] 缠论分析服务 (`chan_analysis_service.py`)
- [ ] API端点 (`api/routes/chan.py`)
- [ ] 性能优化
- [ ] 文档完善
- [ ] 真实数据回测验证

---

## 12. 风险与挑战

### 12.1 技术风险

| 风险项 | 影响 | 缓解措施 |
|--------|------|---------|
| 算法复杂度高 | 开发周期长 | 分阶段实现，P0先保证核心功能 |
| 性能瓶颈 | 批量扫描慢 | 向量化计算 + 并行处理 |
| 边界情况多 | 识别准确率低 | 充分测试 + 容错处理 |
| 参数敏感性 | 不同股票效果差异大 | 提供可配置参数 + 自适应优化 |

### 12.2 业务风险

| 风险项 | 影响 | 缓解措施 |
|--------|------|---------|
| 理论理解偏差 | 实现与原理不符 | 对比开源实现，邀请缠论专家审核 |
| 信号滞后性 | 错过最佳买点 | 明确告知用户，结合其他指标 |
| 假信号过多 | 胜率低 | 提高置信度阈值，只做1买2买 |
| 回测过拟合 | 实盘效果差 | 使用多只股票验证，避免针对单股调优 |

---

## 13. 交付物清单

### 13.1 代码交付

- [ ] `quantsys-v2/chan/` 完整模块（8个文件）
- [ ] `quantsys-v2/strategies/strategy_chan.py`
- [ ] `quantsys-v2/services/chan_analysis_service.py`
- [ ] `quantsys-v2/api/routes/chan.py`
- [ ] `quantsys-v2/tests/chan/` 完整测试（8个测试文件）

### 13.2 文档交付

- [ ] 用户使用指南 (`docs/chan/user-guide.md`)
- [ ] 算法原理文档 (`docs/chan/algorithm-details.md`)
- [ ] API文档（接口说明、请求响应示例）
- [ ] 代码注释（所有核心函数）

### 13.3 验收标准

- [ ] 所有单元测试通过（覆盖率 > 80%）
- [ ] 集成测试通过（3只真实股票）
- [ ] 性能测试达标（1000K线 < 2秒）
- [ ] 代码review通过（无明显bug）
- [ ] 文档完整（用户可独立使用）

---

## 14. 总结

本设计文档完整定义了缠论量化策略的实现方案，包括：

1. **9层完整架构**：数据结构 → 7个算法模块 → 引擎 → 策略 → 服务 → API → 测试 → 优化 → 文档
2. **混合实现标准**：笔严格5K，线段简化，中枢线段级，走势一层分解
3. **完整交易方案**：信号 + 仓位 + 止损 + 止盈 + 理由
4. **全面测试覆盖**：单元 + 集成 + 性能 + 真实数据
5. **清晰实现路径**：P0-P3分阶段，4周完成

**核心优势**：
- ✅ 理论完整（缠论全部核心概念）
- ✅ 实战可用（可配置 + 容错 + 性能优化）
- ✅ 易于维护（分层清晰 + 文档完善）
- ✅ 可扩展（预留多周期、可视化接口）

**下一步**：执行 `writing-plans` skill，生成详细实现计划。

