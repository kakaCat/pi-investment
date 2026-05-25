# 熔断机制与风险事件记录

## 📋 概述

新增的熔断机制和风险事件记录系统为量化交易提供了关键的风险保护层，参考了金策智算的"门下省"和"刑部"设计理念。

### 核心功能

1. **熔断机制 (CircuitBreaker)** - 在极端情况下自动暂停交易
2. **风险事件记录 (RiskEventLogger)** - 记录所有风控相关事件

---

## 🚀 快速开始

### 基础使用

```python
from quantsys.risk import CircuitBreaker, RiskEventLogger
from quantsys.backtest.portfolio import Portfolio

# 创建熔断器
breaker = CircuitBreaker()

# 创建风险记录器
risk_logger = RiskEventLogger()

# 在回测循环中检查熔断
for date in trading_dates:
    # ... 执行交易 ...
    
    # 检查熔断条件
    should_halt, level, reason = breaker.check(
        portfolio=portfolio,
        recent_trades=recent_trades,
        current_date=date
    )
    
    if should_halt:
        # 记录熔断事件
        risk_logger.record_circuit_break(
            strategy_id='my_strategy',
            reason=reason,
            trigger_type='consecutive_loss',
            trigger_value=breaker.consecutive_losses,
            threshold=breaker.config.consecutive_loss_limit
        )
        
        print(f"🚨 熔断触发: {reason}")
        break  # 停止交易
    
    if level == 'WARN':
        print(f"⚠️  风控预警: {reason}")
```

---

## 🔧 熔断机制详解

### 熔断条件

| 条件 | 默认阈值 | 预警阈值 | 说明 |
|------|----------|----------|------|
| 单日亏损 | 5% | 3% | 单日亏损超过阈值触发熔断 |
| 连续亏损 | 3次 | 2次 | 连续亏损次数超限触发熔断 |
| 最大回撤 | 20% | 15% | 从峰值回撤超过阈值触发熔断 |
| 策略连续失败 | 5次 | - | 单个策略连续失败次数超限 |

### 自定义配置

```python
from quantsys.risk import CircuitBreaker, CircuitBreakerConfig

# 创建自定义配置
config = CircuitBreakerConfig(
    daily_loss_limit=0.03,           # 单日亏损3%熔断
    daily_loss_warn=0.02,            # 单日亏损2%预警
    consecutive_loss_limit=2,        # 连续2次亏损熔断
    consecutive_loss_warn=1,         # 连续1次预警
    max_drawdown_limit=0.15,         # 最大回撤15%熔断
    max_drawdown_warn=0.10,          # 最大回撤10%预警
    strategy_consecutive_loss_limit=3,  # 单策略连续3次失败
    auto_resume_enabled=True,        # 启用自动恢复
    auto_resume_delay_minutes=30,    # 30分钟后自动恢复
    reduce_position_on_warn=True,    # 预警时降仓
    reduce_position_pct=0.5          # 降至50%
)

breaker = CircuitBreaker(config=config)
```

---

## 🧪 测试

运行单元测试：

```bash
# 测试熔断机制
python -m pytest quant/tests/test_circuit_breaker.py -v

# 测试风险记录器
python -m pytest quant/tests/test_risk_logger.py -v
```

运行示例：

```bash
# 运行集成示例
python quant/examples/circuit_breaker_example.py
```

---

## 📚 完整文档

详细使用说明请参考示例文件：
- `examples/circuit_breaker_example.py` - 完整使用示例
- `tests/test_circuit_breaker.py` - 单元测试
- `tests/test_risk_logger.py` - 风险记录器测试
