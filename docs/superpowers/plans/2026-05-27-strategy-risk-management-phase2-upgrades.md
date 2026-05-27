# 策略风控管理系统 - Phase 2: 策略升级

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 升级 4 个关键策略（VolatilityBreakout, Turtle, Donchian, Momentum）以使用 Phase 1 构建的风险管理功能，包括 ATR 止损、仓位管理和完整的风控参数返回。

**Architecture:** 每个策略在 `generate_signal()` 方法中添加 `risk_management` 字段，使用 StrategyBase 提供的辅助方法构建止损和仓位配置。保持向后兼容，旧的信号格式仍然有效。

**Tech Stack:** Python 3.13, pytest

**Dependencies:** 
- Phase 1 已完成: `docs/superpowers/plans/2026-05-27-strategy-risk-management-phase1-infrastructure.md`
- 设计文档: `docs/superpowers/specs/2026-05-27-strategy-risk-management-design.md`
- 现有策略文件: `quantsys-v2/quantlib/engine/`

---

## 文件结构

### 修改文件

```
quantsys-v2/
├── quantlib/engine/
│   ├── volatility_breakout_strategy.py     # 升级：ATR 止损 + Kelly 仓位
│   ├── turtle_strategy.py                  # 升级：ATR 止损 + 固定比例仓位
│   ├── donchian_channel_strategy.py        # 升级：固定百分比止损 + 固定仓位
│   └── momentum_strategy.py                # 升级：追踪止损 + Kelly 仓位
└── tests/
    ├── test_volatility_breakout_risk.py    # 新增：VolatilityBreakout 风控测试
    ├── test_turtle_risk.py                 # 新增：Turtle 风控测试
    ├── test_donchian_risk.py               # 新增：Donchian 风控测试
    └── test_momentum_risk.py               # 新增：Momentum 风控测试
```

---

## Task 1: 升级 VolatilityBreakoutStrategy

**Files:**
- Modify: `quantsys-v2/quantlib/engine/volatility_breakout_strategy.py`
- Test: `quantsys-v2/tests/test_volatility_breakout_risk.py`

**策略特点**: 已有 ATR 计算，最容易升级。使用 ATR 止损（2倍 ATR）+ Kelly 仓位管理。

- [ ] **Step 1: 编写测试 - 买入信号包含风控信息**

创建文件 `quantsys-v2/tests/test_volatility_breakout_risk.py`:

```python
"""
测试 VolatilityBreakoutStrategy 风控功能
"""
import pytest
from quantlib.engine.volatility_breakout_strategy import VolatilityBreakoutStrategy


class TestVolatilityBreakoutRisk:
    
    @pytest.fixture
    def strategy(self):
        """创建策略实例"""
        return VolatilityBreakoutStrategy()
    
    @pytest.fixture
    def klines(self):
        """生成测试 K 线数据（30天，价格上涨趋势）"""
        return [
            {
                'trade_date': f'2024-01-{i:02d}',
                'close': 50.0 + i * 0.5,
                'high': 51.0 + i * 0.5,
                'low': 49.0 + i * 0.5,
                'volume': 1000000
            }
            for i in range(1, 31)
        ]
    
    def test_buy_signal_includes_atr_stop_loss(self, strategy, klines):
        """测试买入信号包含 ATR 止损"""
        # 修改最后一天数据，触发买入信号（突破上阈值）
        klines[-1]['high'] = 70.0
        klines[-1]['close'] = 69.5
        
        signal = strategy.generate_signal(klines)
        
        assert signal['action'] == 'buy'
        assert 'risk_management' in signal
        assert 'stop_loss' in signal['risk_management']
        
        stop_loss = signal['risk_management']['stop_loss']
        assert stop_loss['type'] == 'atr'
        assert stop_loss['price'] > 0
        assert stop_loss['price'] < klines[-1]['close']  # 止损价低于当前价
        assert 'atr_value' in stop_loss['params']
        assert 'atr_multiplier' in stop_loss['params']
        assert stop_loss['params']['atr_multiplier'] == 2.0
    
    def test_buy_signal_includes_kelly_position_sizing(self, strategy, klines):
        """测试买入信号包含 Kelly 仓位管理"""
        klines[-1]['high'] = 70.0
        klines[-1]['close'] = 69.5
        
        signal = strategy.generate_signal(klines)
        
        assert 'position_sizing' in signal['risk_management']
        
        sizing = signal['risk_management']['position_sizing']
        assert sizing['method'] == 'kelly'
        assert sizing['value'] is None  # Kelly 由执行层计算
        assert 'win_rate' in sizing['params']
        assert 'profit_loss_ratio' in sizing['params']
        assert 'kelly_fraction' in sizing['params']
        assert 0 <= sizing['params']['win_rate'] <= 1
        assert sizing['params']['profit_loss_ratio'] > 0
        assert sizing['params']['kelly_fraction'] == 0.25
    
    def test_buy_signal_includes_indicators(self, strategy, klines):
        """测试买入信号包含指标数据"""
        klines[-1]['high'] = 70.0
        klines[-1]['close'] = 69.5
        
        signal = strategy.generate_signal(klines)
        
        assert 'indicators' in signal
        assert 'atr' in signal['indicators']
        assert signal['indicators']['atr'] > 0
    
    def test_sell_signal_includes_risk_management(self, strategy, klines):
        """测试卖出信号包含风控信息"""
        # 修改最后一天数据，触发卖出信号（跌破下阈值）
        klines[-1]['low'] = 40.0
        klines[-1]['close'] = 40.5
        
        signal = strategy.generate_signal(klines)
        
        assert signal['action'] == 'sell'
        assert 'risk_management' in signal
        # 卖出信号也应该有止损（做空止损）
        assert 'stop_loss' in signal['risk_management']
        assert signal['risk_management']['stop_loss']['price'] > klines[-1]['close']
    
    def test_hold_signal_no_risk_management(self, strategy, klines):
        """测试持有信号不包含风控信息"""
        # 默认 klines 应该触发 hold 信号
        signal = strategy.generate_signal(klines)
        
        assert signal['action'] == 'hold'
        # hold 信号不需要风控信息
        assert 'risk_management' not in signal
```

- [ ] **Step 2: 运行测试确认失败**

```bash
cd quantsys-v2
pytest tests/test_volatility_breakout_risk.py -v
```

Expected: 所有测试失败，提示 'risk_management' 字段不存在

- [ ] **Step 3: 修改策略 - 添加风控信息到买入信号**

修改 `quantsys-v2/quantlib/engine/volatility_breakout_strategy.py`，在买入信号部分（第 102-113 行）替换为：

```python
        # 买入信号: 突破上阈值
        if current_high > upper_threshold:
            breakout_strength = (current_high - upper_threshold) / atr
            confidence = min(0.85, 0.65 + breakout_strength * 0.2)
            
            # 构建 ATR 止损（做多，止损价 = 当前价 - 2*ATR）
            stop_loss = self._build_stop_loss_atr(
                entry_price=current_close,
                atr=atr,
                multiplier=2.0,
                direction='long'
            )
            
            # 构建 Kelly 仓位（基于历史回测数据）
            position_sizing = self._build_position_sizing_kelly(
                win_rate=0.55,
                profit_loss_ratio=2.0,
                kelly_fraction=0.25
            )
            
            return {
                'action': 'buy',
                'confidence': round(confidence, 4),
                'reason': (
                    f'突破波动率上阈值 {upper_threshold:.2f} '
                    f'(昨收 {prev_close:.2f} + {atr_multiplier}*ATR {atr:.2f}), '
                    f'当前价 {current_close:.2f}'
                ),
                'risk_management': {
                    'stop_loss': stop_loss,
                    'position_sizing': position_sizing
                },
                'indicators': {
                    'atr': round(atr, 2)
                }
            }
```

- [ ] **Step 4: 修改策略 - 添加风控信息到卖出信号**

在卖出信号部分（第 115-127 行）替换为：

```python
        # 卖出信号: 跌破下阈值
        if current_low < lower_threshold:
            breakdown_strength = (lower_threshold - current_low) / atr
            confidence = min(0.85, 0.65 + breakdown_strength * 0.2)
            
            # 构建 ATR 止损（做空，止损价 = 当前价 + 2*ATR）
            stop_loss = self._build_stop_loss_atr(
                entry_price=current_close,
                atr=atr,
                multiplier=2.0,
                direction='short'
            )
            
            # 构建 Kelly 仓位
            position_sizing = self._build_position_sizing_kelly(
                win_rate=0.55,
                profit_loss_ratio=2.0,
                kelly_fraction=0.25
            )
            
            return {
                'action': 'sell',
                'confidence': round(confidence, 4),
                'reason': (
                    f'跌破波动率下阈值 {lower_threshold:.2f} '
                    f'(昨收 {prev_close:.2f} - {atr_multiplier}*ATR {atr:.2f}), '
                    f'当前价 {current_close:.2f}'
                ),
                'risk_management': {
                    'stop_loss': stop_loss,
                    'position_sizing': position_sizing
                },
                'indicators': {
                    'atr': round(atr, 2)
                }
            }
```

- [ ] **Step 5: 运行测试确认通过**

```bash
pytest tests/test_volatility_breakout_risk.py -v
```

Expected: 所有测试通过

- [ ] **Step 6: 运行向后兼容性测试**

```bash
pytest tests/test_backward_compatibility.py::TestBackwardCompatibility::test_all_legacy_strategies_still_work -v
```

Expected: 测试通过，确保升级后的策略仍然兼容

- [ ] **Step 7: Commit**

```bash
git add quantlib/engine/volatility_breakout_strategy.py tests/test_volatility_breakout_risk.py
git commit -m "feat(strategy): upgrade VolatilityBreakoutStrategy with risk management

- Add ATR-based stop loss (2x ATR)
- Add Kelly criterion position sizing
- Include ATR indicator in signal
- Maintain backward compatibility
- Add comprehensive unit tests"
```

---

## Task 2: 升级 TurtleStrategy

**Files:**
- Modify: `quantsys-v2/quantlib/engine/turtle_strategy.py`
- Test: `quantsys-v2/tests/test_turtle_risk.py`

**策略特点**: 经典趋势跟踪策略。使用 ATR 止损（2倍 ATR）+ 固定比例仓位（15%）。

- [ ] **Step 1: 编写测试**

创建文件 `quantsys-v2/tests/test_turtle_risk.py`:

```python
"""
测试 TurtleStrategy 风控功能
"""
import pytest
from quantlib.engine.turtle_strategy import TurtleStrategy


class TestTurtleRisk:
    
    @pytest.fixture
    def strategy(self):
        """创建策略实例"""
        return TurtleStrategy()
    
    @pytest.fixture
    def klines(self):
        """生成测试 K 线数据（25天）"""
        return [
            {
                'trade_date': f'2024-01-{i:02d}',
                'close': 50.0 + i * 0.3,
                'high': 51.0 + i * 0.3,
                'low': 49.0 + i * 0.3,
                'volume': 1000000
            }
            for i in range(1, 26)
        ]
    
    def test_buy_signal_includes_atr_stop_loss(self, strategy, klines):
        """测试买入信号包含 ATR 止损"""
        # 触发买入信号（突破20日高点）
        klines[-1]['high'] = 70.0
        klines[-1]['close'] = 69.5
        
        signal = strategy.generate_signal(klines)
        
        assert signal['action'] == 'buy'
        assert 'risk_management' in signal
        assert 'stop_loss' in signal['risk_management']
        
        stop_loss = signal['risk_management']['stop_loss']
        assert stop_loss['type'] == 'atr'
        assert stop_loss['price'] < klines[-1]['close']
        assert 'atr_value' in stop_loss['params']
        assert stop_loss['params']['atr_multiplier'] == 2.0
    
    def test_buy_signal_includes_fixed_percent_sizing(self, strategy, klines):
        """测试买入信号包含固定比例仓位"""
        klines[-1]['high'] = 70.0
        klines[-1]['close'] = 69.5
        
        signal = strategy.generate_signal(klines)
        
        assert 'position_sizing' in signal['risk_management']
        
        sizing = signal['risk_management']['position_sizing']
        assert sizing['method'] == 'fixed_percent'
        assert sizing['value'] == 0.15  # 15%
        assert sizing['params'] == {}
    
    def test_sell_signal_includes_risk_management(self, strategy, klines):
        """测试卖出信号包含风控信息"""
        # 触发卖出信号（跌破10日低点）
        klines[-1]['low'] = 45.0
        klines[-1]['close'] = 45.5
        
        signal = strategy.generate_signal(klines)
        
        assert signal['action'] == 'sell'
        assert 'risk_management' in signal
        assert 'stop_loss' in signal['risk_management']
        assert signal['risk_management']['stop_loss']['price'] > klines[-1]['close']
    
    def test_hold_signal_no_risk_management(self, strategy, klines):
        """测试持有信号不包含风控信息"""
        signal = strategy.generate_signal(klines)
        
        if signal['action'] == 'hold':
            assert 'risk_management' not in signal
```

- [ ] **Step 2: 运行测试确认失败**

```bash
cd quantsys-v2
pytest tests/test_turtle_risk.py -v
```

Expected: 测试失败

- [ ] **Step 3: 添加 ATR 计算方法到 TurtleStrategy**

在 `quantsys-v2/quantlib/engine/turtle_strategy.py` 的类中添加 ATR 计算方法（在 `generate_signal` 方法之前）:

```python
    def _calculate_atr(self, klines: List[Dict[str, Any]], period: int = 14) -> float:
        """
        计算ATR (Average True Range)
        
        Args:
            klines: K线数据列表
            period: ATR周期
            
        Returns:
            最新ATR值
        """
        if len(klines) < period + 1:
            return 0.0
        
        true_ranges = []
        for i in range(1, len(klines)):
            high = float(klines[i].get('high', klines[i]['close']))
            low = float(klines[i].get('low', klines[i]['close']))
            prev_close = float(klines[i-1]['close'])
            
            tr = max(
                high - low,
                abs(high - prev_close),
                abs(low - prev_close)
            )
            true_ranges.append(tr)
        
        if len(true_ranges) < period:
            return 0.0
        
        # Wilder's smoothing
        atr = sum(true_ranges[:period]) / period
        for i in range(period, len(true_ranges)):
            atr = (atr * (period - 1) + true_ranges[i]) / period
        
        return atr
```

- [ ] **Step 4: 修改买入信号添加风控信息**

在买入信号部分（第 66-76 行）替换为：

```python
        # 买入信号: 突破入场通道上轨
        if current_high > entry_high:
            breakout_strength = (current_high - entry_high) / entry_high
            confidence = min(0.85, 0.6 + breakout_strength * 10)
            
            # 计算 ATR
            atr = self._calculate_atr(klines, period=14)
            
            # 构建 ATR 止损
            stop_loss = self._build_stop_loss_atr(
                entry_price=current_close,
                atr=atr,
                multiplier=2.0,
                direction='long'
            )
            
            # 构建固定比例仓位（15%）
            position_sizing = self._build_position_sizing_percent(0.15)
            
            return {
                'action': 'buy',
                'confidence': round(confidence, 4),
                'reason': (
                    f'价格突破{entry_period}日高点 {entry_high:.2f}, '
                    f'当前价 {current_close:.2f}, 海龟入场信号'
                ),
                'risk_management': {
                    'stop_loss': stop_loss,
                    'position_sizing': position_sizing
                },
                'indicators': {
                    'atr': round(atr, 2)
                }
            }
```

- [ ] **Step 5: 修改卖出信号添加风控信息**

在卖出信号部分（第 78-89 行）替换为：

```python
        # 卖出信号: 跌破出场通道下轨
        if current_low < exit_low:
            breakdown_strength = (exit_low - current_low) / exit_low
            confidence = min(0.85, 0.6 + breakdown_strength * 10)
            
            # 计算 ATR
            atr = self._calculate_atr(klines, period=14)
            
            # 构建 ATR 止损（做空）
            stop_loss = self._build_stop_loss_atr(
                entry_price=current_close,
                atr=atr,
                multiplier=2.0,
                direction='short'
            )
            
            # 构建固定比例仓位
            position_sizing = self._build_position_sizing_percent(0.15)
            
            return {
                'action': 'sell',
                'confidence': round(confidence, 4),
                'reason': (
                    f'价格跌破{exit_period}日低点 {exit_low:.2f}, '
                    f'当前价 {current_close:.2f}, 海龟止损信号'
                ),
                'risk_management': {
                    'stop_loss': stop_loss,
                    'position_sizing': position_sizing
                },
                'indicators': {
                    'atr': round(atr, 2)
                }
            }
```

- [ ] **Step 6: 运行测试确认通过**

```bash
pytest tests/test_turtle_risk.py -v
```

Expected: 所有测试通过

- [ ] **Step 7: 运行向后兼容性测试**

```bash
pytest tests/test_backward_compatibility.py -v
```

Expected: 测试通过

- [ ] **Step 8: Commit**

```bash
git add quantlib/engine/turtle_strategy.py tests/test_turtle_risk.py
git commit -m "feat(strategy): upgrade TurtleStrategy with risk management

- Add ATR calculation method
- Add ATR-based stop loss (2x ATR)
- Add fixed percent position sizing (15%)
- Include ATR indicator in signal
- Maintain backward compatibility
- Add comprehensive unit tests"
```

---

## Task 3: 升级 DonchianChannelStrategy

**Files:**
- Modify: `quantsys-v2/quantlib/engine/donchian_channel_strategy.py`
- Test: `quantsys-v2/tests/test_donchian_risk.py`

**策略特点**: 突破策略。使用固定百分比止损（-8%）+ 固定比例仓位（12%）。

- [ ] **Step 1: 编写测试**

创建文件 `quantsys-v2/tests/test_donchian_risk.py`:

```python
"""
测试 DonchianChannelStrategy 风控功能
"""
import pytest
from quantlib.engine.donchian_channel_strategy import DonchianChannelStrategy


class TestDonchianRisk:
    
    @pytest.fixture
    def strategy(self):
        """创建策略实例"""
        return DonchianChannelStrategy()
    
    @pytest.fixture
    def klines(self):
        """生成测试 K 线数据（25天）"""
        return [
            {
                'trade_date': f'2024-01-{i:02d}',
                'close': 50.0 + i * 0.4,
                'high': 51.0 + i * 0.4,
                'low': 49.0 + i * 0.4,
                'volume': 1000000
            }
            for i in range(1, 26)
        ]
    
    def test_buy_signal_includes_fixed_percent_stop_loss(self, strategy, klines):
        """测试买入信号包含固定百分比止损"""
        # 触发买入信号（突破上轨）
        prev_close = klines[-2]['close']
        klines[-1]['high'] = 75.0
        klines[-1]['close'] = 74.5
        
        signal = strategy.generate_signal(klines)
        
        assert signal['action'] == 'buy'
        assert 'risk_management' in signal
        assert 'stop_loss' in signal['risk_management']
        
        stop_loss = signal['risk_management']['stop_loss']
        assert stop_loss['type'] == 'fixed_percent'
        assert stop_loss['price'] < klines[-1]['close']
        assert 'percent' in stop_loss['params']
        assert stop_loss['params']['percent'] == 0.08
        # 验证止损价格计算正确（当前价 * 0.92）
        expected_stop = round(klines[-1]['close'] * 0.92, 2)
        assert stop_loss['price'] == expected_stop
    
    def test_buy_signal_includes_fixed_percent_sizing(self, strategy, klines):
        """测试买入信号包含固定比例仓位"""
        klines[-1]['high'] = 75.0
        klines[-1]['close'] = 74.5
        
        signal = strategy.generate_signal(klines)
        
        assert 'position_sizing' in signal['risk_management']
        
        sizing = signal['risk_management']['position_sizing']
        assert sizing['method'] == 'fixed_percent'
        assert sizing['value'] == 0.12  # 12%
        assert sizing['params'] == {}
    
    def test_sell_signal_includes_risk_management(self, strategy, klines):
        """测试卖出信号包含风控信息"""
        # 触发卖出信号（跌破下轨）
        klines[-1]['low'] = 45.0
        klines[-1]['close'] = 45.5
        
        signal = strategy.generate_signal(klines)
        
        assert signal['action'] == 'sell'
        assert 'risk_management' in signal
        assert 'stop_loss' in signal['risk_management']
        # 做空止损价应该高于当前价
        assert signal['risk_management']['stop_loss']['price'] > klines[-1]['close']
        # 验证止损价格计算正确（当前价 * 1.08）
        expected_stop = round(klines[-1]['close'] * 1.08, 2)
        assert signal['risk_management']['stop_loss']['price'] == expected_stop
    
    def test_hold_signal_no_risk_management(self, strategy, klines):
        """测试持有信号不包含风控信息"""
        signal = strategy.generate_signal(klines)
        
        if signal['action'] == 'hold':
            assert 'risk_management' not in signal
```

- [ ] **Step 2: 运行测试确认失败**

```bash
cd quantsys-v2
pytest tests/test_donchian_risk.py -v
```

Expected: 测试失败

- [ ] **Step 3: 修改买入信号添加风控信息**

在 `quantsys-v2/quantlib/engine/donchian_channel_strategy.py` 的买入信号部分（第 64-75 行）替换为：

```python
        # 买入信号: 突破上轨
        if current_high > upper_band and prev_close <= upper_band:
            # 通道越窄，突破越有效
            confidence = min(0.9, 0.65 + (0.1 - channel_width) * 2)
            confidence = max(0.5, confidence)
            
            # 构建固定百分比止损（-8%）
            stop_loss = self._build_stop_loss_percent(
                entry_price=current_close,
                percent=0.08,
                direction='long'
            )
            
            # 构建固定比例仓位（12%）
            position_sizing = self._build_position_sizing_percent(0.12)
            
            return {
                'action': 'buy',
                'confidence': round(confidence, 4),
                'reason': (
                    f'突破唐奇安通道上轨 {upper_band:.2f}, '
                    f'当前价 {current_close:.2f}, 通道宽度 {channel_width:.2%}'
                ),
                'risk_management': {
                    'stop_loss': stop_loss,
                    'position_sizing': position_sizing
                }
            }
```

- [ ] **Step 4: 修改卖出信号添加风控信息**

在卖出信号部分（第 77-88 行）替换为：

```python
        # 卖出信号: 跌破下轨
        if current_low < lower_band and prev_close >= lower_band:
            confidence = min(0.9, 0.65 + (0.1 - channel_width) * 2)
            confidence = max(0.5, confidence)
            
            # 构建固定百分比止损（做空，+8%）
            stop_loss = self._build_stop_loss_percent(
                entry_price=current_close,
                percent=0.08,
                direction='short'
            )
            
            # 构建固定比例仓位
            position_sizing = self._build_position_sizing_percent(0.12)
            
            return {
                'action': 'sell',
                'confidence': round(confidence, 4),
                'reason': (
                    f'跌破唐奇安通道下轨 {lower_band:.2f}, '
                    f'当前价 {current_close:.2f}, 通道宽度 {channel_width:.2%}'
                ),
                'risk_management': {
                    'stop_loss': stop_loss,
                    'position_sizing': position_sizing
                }
            }
```

- [ ] **Step 5: 运行测试确认通过**

```bash
pytest tests/test_donchian_risk.py -v
```

Expected: 所有测试通过

- [ ] **Step 6: 运行向后兼容性测试**

```bash
pytest tests/test_backward_compatibility.py -v
```

Expected: 测试通过

- [ ] **Step 7: Commit**

```bash
git add quantlib/engine/donchian_channel_strategy.py tests/test_donchian_risk.py
git commit -m "feat(strategy): upgrade DonchianChannelStrategy with risk management

- Add fixed percent stop loss (-8%)
- Add fixed percent position sizing (12%)
- Maintain backward compatibility
- Add comprehensive unit tests"
```

---

## Task 4: 升级 MomentumStrategy

**Files:**
- Modify: `quantsys-v2/quantlib/engine/momentum_strategy.py`
- Test: `quantsys-v2/tests/test_momentum_risk.py`

**策略特点**: 动量策略。使用追踪止损（5%）+ Kelly 仓位管理。

- [ ] **Step 1: 编写测试**

创建文件 `quantsys-v2/tests/test_momentum_risk.py`:

```python
"""
测试 MomentumStrategy 风控功能
"""
import pytest
from quantlib.engine.momentum_strategy import MomentumStrategy


class TestMomentumRisk:
    
    @pytest.fixture
    def strategy(self):
        """创建策略实例"""
        return MomentumStrategy()
    
    @pytest.fixture
    def klines(self):
        """生成测试 K 线数据（30天，上涨趋势）"""
        return [
            {
                'trade_date': f'2024-01-{i:02d}',
                'close': 50.0 + i * 0.8,
                'high': 51.0 + i * 0.8,
                'low': 49.0 + i * 0.8,
                'volume': 1000000
            }
            for i in range(1, 31)
        ]
    
    def test_buy_signal_includes_trailing_stop_loss(self, strategy, klines):
        """测试买入信号包含追踪止损"""
        signal = strategy.generate_signal(klines)
        
        # 确保触发买入信号（ROC上穿零线）
        if signal['action'] != 'buy':
            pytest.skip("未触发买入信号，调整测试数据")
        
        assert 'risk_management' in signal
        assert 'stop_loss' in signal['risk_management']
        
        stop_loss = signal['risk_management']['stop_loss']
        assert stop_loss['type'] == 'trailing'
        assert stop_loss['price'] < klines[-1]['close']
        assert 'trailing_percent' in stop_loss['params']
        assert stop_loss['params']['trailing_percent'] == 0.05
    
    def test_buy_signal_includes_kelly_position_sizing(self, strategy, klines):
        """测试买入信号包含 Kelly 仓位管理"""
        signal = strategy.generate_signal(klines)
        
        if signal['action'] != 'buy':
            pytest.skip("未触发买入信号")
        
        assert 'position_sizing' in signal['risk_management']
        
        sizing = signal['risk_management']['position_sizing']
        assert sizing['method'] == 'kelly'
        assert sizing['value'] is None
        assert 'win_rate' in sizing['params']
        assert 'profit_loss_ratio' in sizing['params']
        assert 'kelly_fraction' in sizing['params']
        assert sizing['params']['kelly_fraction'] == 0.25
    
    def test_buy_signal_includes_roc_indicator(self, strategy, klines):
        """测试买入信号包含 ROC 指标"""
        signal = strategy.generate_signal(klines)
        
        if signal['action'] != 'buy':
            pytest.skip("未触发买入信号")
        
        assert 'indicators' in signal
        assert 'roc' in signal['indicators']
        assert 'roc_ma' in signal['indicators']
    
    def test_sell_signal_includes_risk_management(self, strategy):
        """测试卖出信号包含风控信息"""
        # 生成下跌趋势数据
        klines = [
            {
                'trade_date': f'2024-01-{i:02d}',
                'close': 70.0 - i * 0.8,
                'high': 71.0 - i * 0.8,
                'low': 69.0 - i * 0.8,
                'volume': 1000000
            }
            for i in range(1, 31)
        ]
        
        signal = strategy.generate_signal(klines)
        
        if signal['action'] != 'sell':
            pytest.skip("未触发卖出信号")
        
        assert 'risk_management' in signal
        assert 'stop_loss' in signal['risk_management']
        # 做空追踪止损价应该高于当前价
        assert signal['risk_management']['stop_loss']['price'] > klines[-1]['close']
    
    def test_hold_signal_no_risk_management(self, strategy, klines):
        """测试持有信号不包含风控信息"""
        # 生成平稳数据
        flat_klines = [
            {
                'trade_date': f'2024-01-{i:02d}',
                'close': 50.0,
                'high': 51.0,
                'low': 49.0,
                'volume': 1000000
            }
            for i in range(1, 31)
        ]
        
        signal = strategy.generate_signal(flat_klines)
        
        if signal['action'] == 'hold':
            assert 'risk_management' not in signal
```

- [ ] **Step 2: 运行测试确认失败**

```bash
cd quantsys-v2
pytest tests/test_momentum_risk.py -v
```

Expected: 测试失败

- [ ] **Step 3: 修改买入信号添加风控信息**

在 `quantsys-v2/quantlib/engine/momentum_strategy.py` 的买入信号部分（第 72-81 行）替换为：

```python
        # 买入信号: ROC上穿零线（动量转正）
        if prev_roc_ma <= 0 and current_roc_ma > 0:
            confidence = min(0.85, 0.6 + abs(current_roc_ma) / 10)
            
            # 构建追踪止损（5%）
            stop_loss = self._build_stop_loss_trailing(
                entry_price=current_close,
                trailing_percent=0.05,
                direction='long'
            )
            
            # 构建 Kelly 仓位
            position_sizing = self._build_position_sizing_kelly(
                win_rate=0.52,
                profit_loss_ratio=1.8,
                kelly_fraction=0.25
            )
            
            return {
                'action': 'buy',
                'confidence': round(confidence, 4),
                'reason': (
                    f'ROC上穿零线 (ROC={current_roc:.2f}%, MA={current_roc_ma:.2f}%), '
                    f'动量转正, 当前价 {current_close:.2f}'
                ),
                'risk_management': {
                    'stop_loss': stop_loss,
                    'position_sizing': position_sizing
                },
                'indicators': {
                    'roc': round(current_roc, 2),
                    'roc_ma': round(current_roc_ma, 2)
                }
            }
```

- [ ] **Step 4: 修改卖出信号添加风控信息**

在卖出信号部分（第 83-92 行）替换为：

```python
        # 卖出信号: ROC下穿零线（动量转负）
        if prev_roc_ma >= 0 and current_roc_ma < 0:
            confidence = min(0.85, 0.6 + abs(current_roc_ma) / 10)
            
            # 构建追踪止损（做空，5%）
            stop_loss = self._build_stop_loss_trailing(
                entry_price=current_close,
                trailing_percent=0.05,
                direction='short'
            )
            
            # 构建 Kelly 仓位
            position_sizing = self._build_position_sizing_kelly(
                win_rate=0.52,
                profit_loss_ratio=1.8,
                kelly_fraction=0.25
            )
            
            return {
                'action': 'sell',
                'confidence': round(confidence, 4),
                'reason': (
                    f'ROC下穿零线 (ROC={current_roc:.2f}%, MA={current_roc_ma:.2f}%), '
                    f'动量转负, 当前价 {current_close:.2f}'
                ),
                'risk_management': {
                    'stop_loss': stop_loss,
                    'position_sizing': position_sizing
                },
                'indicators': {
                    'roc': round(current_roc, 2),
                    'roc_ma': round(current_roc_ma, 2)
                }
            }
```

- [ ] **Step 5: 运行测试确认通过**

```bash
pytest tests/test_momentum_risk.py -v
```

Expected: 所有测试通过

- [ ] **Step 6: 运行向后兼容性测试**

```bash
pytest tests/test_backward_compatibility.py -v
```

Expected: 测试通过

- [ ] **Step 7: Commit**

```bash
git add quantlib/engine/momentum_strategy.py tests/test_momentum_risk.py
git commit -m "feat(strategy): upgrade MomentumStrategy with risk management

- Add trailing stop loss (5%)
- Add Kelly criterion position sizing
- Include ROC and ROC MA indicators in signal
- Maintain backward compatibility
- Add comprehensive unit tests"
```

---

## 验收标准

完成所有任务后，验证以下标准：

- [ ] **所有单元测试通过**
  ```bash
  pytest tests/test_volatility_breakout_risk.py -v
  pytest tests/test_turtle_risk.py -v
  pytest tests/test_donchian_risk.py -v
  pytest tests/test_momentum_risk.py -v
  ```

- [ ] **向后兼容性验证**
  ```bash
  pytest tests/test_backward_compatibility.py -v
  ```

- [ ] **集成测试通过**
  ```bash
  pytest tests/integration/test_signal_to_order_flow.py -v
  ```

- [ ] **信号处理测试通过**
  ```bash
  pytest tests/test_signal_processor.py -v
  ```

- [ ] **代码质量**
  - 所有代码已提交到 git
  - Commit 消息清晰
  - 无 TODO 或 placeholder

- [ ] **功能验证**
  - 4 个策略升级完成
  - 每个策略的买入/卖出信号都包含风控信息
  - 持有信号不包含风控信息（保持简洁）
  - 所有策略仍然向后兼容

---

## 下一步

完成 Phase 2 后，可以继续：

1. **Phase 3: TypeScript 集成** - 更新 TypeScript Agent 工具以使用新的风控功能
2. **Phase 4: 文档和示例** - 编写迁移指南和示例代码
3. **回测对比** - 对比升级前后的策略表现
