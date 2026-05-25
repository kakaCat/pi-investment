# 实盘监控模块 - Live Monitor

## 📋 概述

实盘监控模块实时监控交易执行情况，检测异常并触发告警，参考了金策智算的LiveCabinet设计。

### 核心功能

1. **信号延迟检测** - 监控从信号生成到执行的时间
2. **价格偏差检测** - 监控预期价格与实际成交价的偏差
3. **策略漂移检测** - 监控策略表现是否偏离历史基线
4. **自动告警动作** - 预警降仓、严重暂停

---

## 🚀 快速开始

### 基础使用

```python
from quantsys.live import LiveMonitor, MonitorConfig
from datetime import datetime

# 创建监控器
config = MonitorConfig(
    signal_delay_warn_seconds=5.0,      # 5秒预警
    signal_delay_critical_seconds=15.0,  # 15秒严重
    price_deviation_warn=0.003,         # 0.3%预警
    price_deviation_critical=0.008      # 0.8%严重
)
monitor = LiveMonitor(config)

# 检查信号延迟
has_alert, severity, alert = monitor.check_signal_delay(
    signal_time=signal_time,
    execution_time=execution_time,
    strategy_id='ma_cross'
)

if has_alert:
    print(f"{severity}: {alert.message}")

# 检查价格偏差
has_alert, severity, alert = monitor.check_price_deviation(
    expected_price=50.0,
    actual_price=50.25,
    symbol='600036.SH',
    strategy_id='ma_cross'
)

# 检查策略漂移
has_alert, severity, alert = monitor.check_strategy_drift(
    strategy_id='ma_cross',
    recent_performance={
        'win_rate': 0.55,
        'profit_loss_ratio': 1.5,
        'max_drawdown': 0.15
    }
)
```

---

## 🔧 监控功能详解

### 1. 信号延迟检测

监控从信号生成到实际执行的时间延迟。

```python
# 配置阈值
config = MonitorConfig(
    signal_delay_warn_seconds=5.0,      # 5秒预警
    signal_delay_critical_seconds=15.0   # 15秒严重
)

# 检查延迟
signal_time = datetime.now()
execution_time = datetime.now() + timedelta(seconds=8)

has_alert, severity, alert = monitor.check_signal_delay(
    signal_time, execution_time, 'ma_cross'
)

# 结果: WARN - 信号延迟 8.0秒 (预警)
```

**告警级别**:
- 正常: < 5秒
- 预警: 5-15秒
- 严重: > 15秒（自动暂停策略）

### 2. 价格偏差检测

监控预期价格与实际成交价的偏差。

```python
# 配置阈值
config = MonitorConfig(
    price_deviation_warn=0.003,      # 0.3%预警
    price_deviation_critical=0.008   # 0.8%严重
)

# 检查偏差
has_alert, severity, alert = monitor.check_price_deviation(
    expected_price=50.0,
    actual_price=50.25,  # 偏差0.5%
    symbol='600036.SH',
    strategy_id='ma_cross'
)

# 结果: WARN - 600036.SH 价格偏差 0.50% (预警)
```

**告警级别**:
- 正常: < 0.3%
- 预警: 0.3%-0.8%
- 严重: > 0.8%（自动暂停策略）

### 3. 策略漂移检测

对比最近表现与历史基线，检测策略是否失效。

```python
# 设置基线
baseline = {
    'win_rate': 0.65,
    'profit_loss_ratio': 2.0,
    'max_drawdown': 0.10
}
monitor.update_strategy_baseline('ma_cross', baseline)

# 检查漂移
recent_performance = {
    'win_rate': 0.50,  # 下降15%
    'profit_loss_ratio': 1.5,
    'max_drawdown': 0.15
}

has_alert, severity, alert = monitor.check_strategy_drift(
    'ma_cross', recent_performance
)

# 结果: WARN - 策略 ma_cross 胜率下降 15.00%
```

**检测指标**:
- 胜率下降 > 8%
- 盈亏比下降 > 20%
- 最大回撤扩大 > 30%

---

## 📊 策略漂移检测器

独立的漂移检测器，自动计算基线和最近表现。

```python
from quantsys.live import DriftDetector

# 创建检测器
detector = DriftDetector(
    rolling_days=20,        # 最近20天
    baseline_days=60,       # 基线60天
    win_rate_threshold=0.08 # 胜率下降8%告警
)

# 记录交易
for trade in trades:
    detector.record_trade('ma_cross', trade)

# 检测漂移
has_drift, metrics = detector.detect_drift('ma_cross')

if has_drift:
    print("检测到策略漂移!")
    print(f"基线胜率: {metrics.baseline['win_rate']:.2%}")
    print(f"当前胜率: {metrics.current['win_rate']:.2%}")
    print(f"漂移原因: {metrics.drift_reasons}")
```

---

## 🎯 自动告警动作

### 配置自动动作

```python
config = MonitorConfig(
    auto_reduce_position_on_warn=True,  # 预警时自动降仓
    auto_pause_on_critical=True,        # 严重时自动暂停
    reduce_position_pct=0.5             # 降仓至50%
)

monitor = LiveMonitor(config)
```

### 自定义告警回调

```python
def alert_callback(alert):
    print(f"告警: {alert.message}")
    # 发送邮件、短信、钉钉等
    send_notification(alert)

monitor = LiveMonitor(config, alert_callback=alert_callback)
```

---

## 📈 监控统计

```python
# 获取统计
stats = monitor.get_statistics()

print(f"总告警数: {stats['total_alerts']}")
print(f"按类型统计: {stats['alerts_by_type']}")
print(f"按策略统计: {stats['alerts_by_strategy']}")
print(f"暂停的策略: {stats['paused_strategies']}")

# 查询告警
recent_alerts = monitor.get_alerts(
    alert_type='signal_delay',
    strategy_id='ma_cross',
    severity='CRITICAL',
    hours=24
)

for alert in recent_alerts:
    print(f"[{alert.severity}] {alert.message}")
```

---

## 🔗 与金策智算的对比

| 功能 | 金策智算 | 本实现 | 状态 |
|------|----------|--------|------|
| 信号延迟检测 | ✅ | ✅ | ✅ 完全实现 |
| 价格偏差检测 | ✅ | ✅ | ✅ 完全实现 |
| 策略漂移检测 | ✅ | ✅ | ✅ 完全实现 |
| 自动降仓 | ✅ | ✅ | ✅ 完全实现 |
| 自动暂停 | ✅ | ✅ | ✅ 完全实现 |
| 告警回调 | ❌ | ✅ | ✨ 增强功能 |
| 独立漂移检测器 | ❌ | ✅ | ✨ 增强功能 |

---

## 🧪 测试

运行单元测试：

```bash
python -m pytest quant/tests/test_live_monitor.py -v
```

运行示例：

```bash
python quant/examples/live_monitor_example.py
```

---

## 💡 使用建议

### 阈值设置建议

| 指标 | 预警阈值 | 严重阈值 | 说明 |
|------|---------|---------|------|
| 信号延迟 | 5秒 | 15秒 | 根据网络环境调整 |
| 价格偏差 | 0.3% | 0.8% | 根据市场波动调整 |
| 胜率下降 | 8% | - | 根据策略特性调整 |
| 盈亏比下降 | 20% | - | 根据策略特性调整 |

### 集成到实盘系统

```python
# 在实盘交易循环中
monitor = LiveMonitor(config)

for signal in signals:
    # 1. 记录信号时间
    signal_time = datetime.now()
    
    # 2. 执行订单
    order = execute_order(signal)
    execution_time = datetime.now()
    
    # 3. 检查信号延迟
    monitor.check_signal_delay(signal_time, execution_time, signal.strategy_id)
    
    # 4. 检查价格偏差
    if order.filled:
        monitor.check_price_deviation(
            signal.price, order.filled_price, 
            signal.symbol, signal.strategy_id
        )
    
    # 5. 记录交易（用于漂移检测）
    monitor.record_trade(signal.strategy_id, {
        'date': datetime.now(),
        'pnl': order.pnl,
        'return_pct': order.return_pct
    })
    
    # 6. 定期检查策略漂移
    if should_check_drift():
        recent_perf = monitor.calculate_recent_performance(signal.strategy_id)
        monitor.check_strategy_drift(signal.strategy_id, recent_perf)
```

---

## 📚 API参考

### MonitorConfig

```python
@dataclass
class MonitorConfig:
    signal_delay_warn_seconds: float = 5.0
    signal_delay_critical_seconds: float = 15.0
    price_deviation_warn: float = 0.003
    price_deviation_critical: float = 0.008
    drift_rolling_days: int = 20
    win_rate_drop_warn: float = 0.08
    profit_loss_ratio_drop_warn: float = 0.2
    max_drawdown_expansion_warn: float = 0.3
    auto_reduce_position_on_warn: bool = True
    auto_pause_on_critical: bool = True
    reduce_position_pct: float = 0.5
```

### LiveMonitor

```python
# 检查信号延迟
has_alert, severity, alert = monitor.check_signal_delay(signal_time, execution_time, strategy_id)

# 检查价格偏差
has_alert, severity, alert = monitor.check_price_deviation(expected, actual, symbol, strategy_id)

# 检查策略漂移
has_alert, severity, alert = monitor.check_strategy_drift(strategy_id, recent_performance)

# 暂停/恢复策略
monitor.pause_strategy(strategy_id, reason)
monitor.resume_strategy(strategy_id)
monitor.is_strategy_paused(strategy_id)

# 查询告警
alerts = monitor.get_alerts(alert_type, strategy_id, severity, hours)

# 获取统计
stats = monitor.get_statistics()
```

---

## 💡 完整示例

查看完整示例：`examples/live_monitor_example.py`

包含6个场景：
1. 信号延迟检测
2. 价格偏差检测
3. 策略漂移检测
4. 策略漂移检测器
5. 自动告警动作
6. 监控统计
