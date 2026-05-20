# 策略组合器 - Strategy Combiner

## 📋 概述

策略组合器实现了多策略信号融合功能，支持OR、AND、VOTE三种组合模式，参考了金策智算的策略组合机制。

### 核心功能

1. **OR模式** - 任一策略发出信号即执行
2. **AND模式** - 所有策略必须一致才执行
3. **VOTE模式** - 加权投票，得分高的方向执行
4. **置信度过滤** - 过滤低置信度信号
5. **策略分组** - 支持策略分组管理
6. **动态权重** - 根据历史表现调整权重

---

## 🚀 快速开始

### 基础使用

```python
from quantsys.strategies.combiner import StrategyCombiner, CombinerConfig, Signal
from datetime import datetime

# 创建组合器（VOTE模式）
config = CombinerConfig(
    mode='vote',
    weights={
        'ma_cross': 1.5,      # 均线策略权重1.5
        'rsi_reversal': 1.0,  # RSI策略权重1.0
        'bollinger': 0.8      # 布林带策略权重0.8
    }
)
combiner = StrategyCombiner(config)

# 创建多个策略的信号
signals = [
    Signal(datetime.now(), '600036.SH', 'buy', 50.0, 1000, 'ma_cross', confidence=0.8),
    Signal(datetime.now(), '600036.SH', 'buy', 50.0, 1000, 'rsi_reversal', confidence=0.7),
    Signal(datetime.now(), '600036.SH', 'sell', 50.0, 500, 'bollinger', confidence=0.5)
]

# 组合信号
combined_signals, metadata = combiner.combine_signals(signals)

print(f"买入得分: {metadata['buy_score']}")  # 1.9
print(f"卖出得分: {metadata['sell_score']}")  # 0.4
print(f"胜出方向: {metadata['winner']}")      # buy
print(f"保留信号: {len(combined_signals)}个")  # 2个
```

---

## 🔧 组合模式详解

### 1. OR模式 - 任一策略发出信号即执行

```python
config = CombinerConfig(mode='or')
combiner = StrategyCombiner(config)

signals = [
    Signal(..., action='buy', strategy_id='ma_cross'),
    Signal(..., action='sell', strategy_id='rsi')
]

combined, metadata = combiner.combine_signals(signals)
# 结果: 保留所有信号（2个）
```

**适用场景**: 
- 策略互补，各自捕捉不同机会
- 希望增加交易频率

### 2. AND模式 - 所有策略必须一致

```python
config = CombinerConfig(
    mode='and',
    min_agree_count=2  # 至少2个策略同意
)
combiner = StrategyCombiner(config)

# 场景1: 所有策略一致
signals = [
    Signal(..., action='buy', strategy_id='ma_cross'),
    Signal(..., action='buy', strategy_id='rsi'),
    Signal(..., action='buy', strategy_id='bollinger')
]
combined, metadata = combiner.combine_signals(signals)
# 结果: 保留所有信号（3个）

# 场景2: 策略冲突
signals = [
    Signal(..., action='buy', strategy_id='ma_cross'),
    Signal(..., action='sell', strategy_id='rsi')
]
combined, metadata = combiner.combine_signals(signals)
# 结果: 返回空（0个），reason='direction_conflict'
```

**适用场景**:
- 追求高胜率，宁可错过也不做错
- 策略之间需要相互确认

### 3. VOTE模式 - 加权投票（推荐）

```python
config = CombinerConfig(
    mode='vote',
    weights={'ma_cross': 1.5, 'rsi': 1.0, 'bollinger': 0.8},
    use_confidence_weighting=True,  # 使用置信度加权
    tie_policy='skip'  # 平局时跳过
)
combiner = StrategyCombiner(config)

signals = [
    Signal(..., action='buy', strategy_id='ma_cross', confidence=0.8),
    Signal(..., action='buy', strategy_id='rsi', confidence=0.7),
    Signal(..., action='sell', strategy_id='bollinger', confidence=0.5)
]

combined, metadata = combiner.combine_signals(signals)

# 计算过程:
# 买入得分 = 1.5 * 0.8 + 1.0 * 0.7 = 1.9
# 卖出得分 = 0.8 * 0.5 = 0.4
# 胜出: 买入
```

**适用场景**:
- 平衡收益和风险
- 不同策略有不同重要性
- 最常用的模式

---

## 📊 高级功能

### 置信度阈值过滤

```python
config = CombinerConfig(
    mode='vote',
    confidence_threshold=0.6  # 只保留置信度>=0.6的信号
)
combiner = StrategyCombiner(config)

signals = [
    Signal(..., confidence=0.8),  # ✅ 保留
    Signal(..., confidence=0.5),  # ❌ 过滤
    Signal(..., confidence=0.4)   # ❌ 过滤
]
```

### 创建组合信号

```python
# 将多个信号合并为一个
combined_signal = combiner.create_combined_signal(signals, metadata)

print(combined_signal.strategy_id)  # 'combined'
print(combined_signal.quantity)     # 所有信号数量之和
print(combined_signal.confidence)   # 平均置信度
```

### 策略分组

```python
from quantsys.strategies.combiner import MultiStrategyCombiner

multi_combiner = MultiStrategyCombiner()

# 定义策略分组
multi_combiner.add_strategy_group('trend_following', ['ma_cross', 'macd'])
multi_combiner.add_strategy_group('mean_reversion', ['rsi_reversal', 'bollinger'])

# 按组组合
trend_signals, metadata = multi_combiner.combine_by_group(
    all_signals, 
    'trend_following', 
    combiner
)
```

### 动态权重调整

```python
multi_combiner = MultiStrategyCombiner()

# 更新策略表现
multi_combiner.update_strategy_performance('ma_cross', is_correct=True)
multi_combiner.update_strategy_performance('ma_cross', is_correct=True)
multi_combiner.update_strategy_performance('ma_cross', is_correct=False)

# 获取动态权重（根据准确率调整）
weight = multi_combiner.get_dynamic_weight('ma_cross', base_weight=1.0)
# 准确率66.7% -> 权重约1.17
```

---

## 🧪 测试

运行单元测试：

```bash
python -m pytest quant/tests/test_strategy_combiner.py -v
```

运行示例：

```bash
python quant/examples/strategy_combiner_example.py
```

---

## 📈 使用建议

### 权重设置建议

| 策略类型 | 建议权重 | 说明 |
|---------|---------|------|
| 趋势跟踪 | 1.2-1.5 | 趋势明确时可靠性高 |
| 均值回归 | 0.8-1.0 | 震荡市有效 |
| 动量策略 | 1.0-1.2 | 中等权重 |
| 形态识别 | 0.6-0.8 | 辅助参考 |

### 模式选择建议

| 市场环境 | 推荐模式 | 配置 |
|---------|---------|------|
| 趋势明显 | VOTE | 趋势策略高权重 |
| 震荡市 | AND | 要求多策略确认 |
| 单边市 | OR | 捕捉更多机会 |
| 不确定 | VOTE | 平衡配置 |

---

## 🔗 与金策智算的对比

| 功能 | 金策智算 | 本实现 | 说明 |
|------|----------|--------|------|
| OR组合 | ✅ | ✅ | 完全实现 |
| AND组合 | ✅ | ✅ | 完全实现 |
| VOTE组合 | ✅ | ✅ | 完全实现 |
| 权重配置 | ✅ | ✅ | 完全实现 |
| 平局处理 | ✅ | ✅ | 完全实现 |
| 置信度过滤 | ❌ | ✅ | 增强功能 |
| 策略分组 | ❌ | ✅ | 增强功能 |
| 动态权重 | ❌ | ✅ | 增强功能 |

---

## 📚 API参考

### CombinerConfig

```python
@dataclass
class CombinerConfig:
    mode: str = 'vote'                      # 组合模式
    weights: Dict[str, float] = None        # 策略权重
    min_agree_count: int = 1                # 最小同意数量
    tie_policy: str = 'skip'                # 平局处理
    confidence_threshold: float = 0.0       # 置信度阈值
    require_all_strategies: bool = False    # AND模式是否要求所有策略
    use_confidence_weighting: bool = True   # 是否使用置信度加权
```

### StrategyCombiner

```python
# 组合信号
combined_signals, metadata = combiner.combine_signals(signals, strategy_ids)

# 创建组合信号
combined_signal = combiner.create_combined_signal(signals, metadata)

# 获取统计
stats = combiner.get_statistics()

# 重置统计
combiner.reset_statistics()
```

---

## 💡 完整示例

查看完整示例：`examples/strategy_combiner_example.py`

包含7个场景：
1. OR模式示例
2. AND模式示例
3. VOTE模式示例
4. 置信度过滤示例
5. 创建组合信号示例
6. 策略分组示例
7. 统计信息示例
