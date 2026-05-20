# 🚀 快速开始 - 熔断机制

## 5分钟上手

### 1. 基础使用

```python
from quantsys.risk import CircuitBreaker, RiskEventLogger

# 创建熔断器（使用默认配置）
breaker = CircuitBreaker()

# 创建风险记录器
risk_logger = RiskEventLogger()

# 在交易循环中检查
should_halt, level, reason = breaker.check(
    portfolio=portfolio,
    recent_trades=recent_trades
)

if should_halt:
    print(f"🚨 熔断: {reason}")
    # 停止交易
elif level == 'WARN':
    print(f"⚠️  预警: {reason}")
    # 降低仓位
```

### 2. 运行示例

```bash
# 查看完整示例
python quant/examples/circuit_breaker_example.py
```

### 3. 自定义配置

```python
from quantsys.risk import CircuitBreakerConfig

config = CircuitBreakerConfig(
    daily_loss_limit=0.03,      # 3%熔断
    consecutive_loss_limit=2,   # 2次熔断
    auto_resume_enabled=True    # 自动恢复
)

breaker = CircuitBreaker(config)
```

## 默认熔断条件

| 条件 | 阈值 | 说明 |
|------|------|------|
| 单日亏损 | 5% | 单日亏损超过5%触发熔断 |
| 连续亏损 | 3次 | 连续亏损3次触发熔断 |
| 最大回撤 | 20% | 从峰值回撤超过20%触发熔断 |
| 策略失败 | 5次 | 单策略连续失败5次触发熔断 |

## 完整文档

- 📖 [使用文档](quantsys/risk/CIRCUIT_BREAKER.md)
- 📊 [对比分析](OPTIMIZATION_ANALYSIS.md)
- ✅ [实现报告](IMPLEMENTATION_REPORT.md)
- 💻 [示例代码](examples/circuit_breaker_example.py)

## 下一步

查看完整的优化分析报告了解更多功能：
```bash
cat quant/OPTIMIZATION_ANALYSIS.md
```
