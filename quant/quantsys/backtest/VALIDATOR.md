# 回测基线验证器 - Backtest Baseline Validator

## 📋 概述

回测基线验证器确保策略在实盘前经过充分的历史数据验证，参考了金策智算的回测基线验证机制。

### 核心功能

1. **最小历史年限检查** - 确保有足够的历史数据（默认5年）
2. **市场周期覆盖检查** - 确保经历过牛市、熊市、震荡市
3. **数据质量检查** - 检测数据缺失、异常值、价格跳变
4. **性能指标验证** - 检查夏普比率、最大回撤等指标
5. **配置文件管理** - 不同策略类型的验证标准

---

## 🚀 快速开始

### 基础使用

```python
from quantsys.backtest import BacktestValidator
import pandas as pd

# 创建验证器
validator = BacktestValidator()

# 准备回测数据
equity_curve = pd.Series(...)  # 权益曲线
trades = [...]                  # 交易记录

# 执行验证
result = validator.validate(equity_curve, trades)

if result.passed:
    print("✅ 回测验证通过，可以上线")
else:
    print("❌ 回测验证未通过")
    for error in result.get_errors():
        print(f"  - {error.message}")
```

---

## 🔧 验证功能详解

### 1. 历史年限检查

确保策略经过足够长时间的验证。

```python
from quantsys.backtest import ValidatorConfig

config = ValidatorConfig(
    min_history_years=5.0  # 最少5年历史数据
)
validator = BacktestValidator(config)

result = validator.validate(equity_curve, trades)
```

**检查标准**:
- 默认要求至少5年历史数据
- 不足则返回ERROR，阻止上线
- 充足则返回INFO

### 2. 交易数量检查

确保有足够的交易样本。

```python
config = ValidatorConfig(
    min_trade_count=100  # 最少100笔交易
)
```

**检查标准**:
- 默认要求至少100笔交易
- 不足则返回WARNING
- 充足则返回INFO

### 3. 市场周期覆盖检查

确保策略在不同市场环境下都经过验证。

```python
config = ValidatorConfig(
    require_bull_market=True,      # 要求经历牛市
    require_bear_market=True,      # 要求经历熊市
    require_sideways_market=True,  # 要求经历震荡市
    bull_threshold=0.20,           # 牛市定义：上涨>20%
    bear_threshold=-0.15,          # 熊市定义：下跌>15%
    sideways_threshold=0.10        # 震荡市定义：波动<10%
)
```

**市场状态识别**:
- 使用滚动窗口计算收益率
- 自动识别牛市、熊市、震荡市
- 缺少任何要求的市场状态则返回WARNING

### 4. 数据质量检查

检测数据问题，确保回测结果可靠。

```python
config = ValidatorConfig(
    max_data_gap_days=10,        # 最大数据间隔10天
    max_missing_data_pct=0.05,   # 最大缺失率5%
    max_price_jump_pct=0.30      # 最大价格跳变30%
)

# 需要提供价格数据
result = validator.validate(equity_curve, trades, price_data)
```

**检查项目**:
- 数据缺失率
- 数据间隔
- 价格异常跳变
- 所有问题返回WARNING

### 5. 性能指标验证

确保策略达到最低性能要求。

```python
config = ValidatorConfig(
    min_sharpe_ratio=1.0,          # 最小夏普比率
    max_drawdown_threshold=0.20    # 最大回撤阈值20%
)
```

**检查指标**:
- 夏普比率：年化收益/年化波动率
- 最大回撤：最大资金回撤百分比
- 不达标返回WARNING

---

## 📊 配置文件

提供三种预定义配置文件，适用于不同策略类型。

### Strict（严格模式）- 长期策略

```python
validator = BacktestValidator()
config = validator.create_profile('strict')

# 配置内容:
# - 最小历史年限: 10年
# - 最小交易次数: 200
# - 要求所有市场状态
# - 最小夏普比率: 1.0
# - 最大回撤: 20%
```

**适用场景**: 长期持有策略、低频策略

### Moderate（中等模式）- 中期策略

```python
config = validator.create_profile('moderate')

# 配置内容:
# - 最小历史年限: 5年
# - 最小交易次数: 100
# - 要求牛市和熊市
# - 最小夏普比率: 0.5
# - 最大回撤: 30%
```

**适用场景**: 中期趋势策略、标准量化策略

### Relaxed（宽松模式）- 短期策略

```python
config = validator.create_profile('relaxed')

# 配置内容:
# - 最小历史年限: 3年
# - 最小交易次数: 50
# - 不要求特定市场状态
# - 无性能指标要求
```

**适用场景**: 短期交易策略、高频策略

---

## 🎯 验证结果

### ValidationResult

```python
result = validator.validate(equity_curve, trades)

# 属性
result.passed          # bool: 是否通过验证
result.issues          # List[ValidationIssue]: 所有问题
result.summary         # Dict: 验证摘要

# 方法
result.get_errors()    # 获取所有错误
result.get_warnings()  # 获取所有警告
```

### ValidationIssue

```python
for issue in result.issues:
    print(f"{issue.severity.value}: {issue.message}")
    print(f"Category: {issue.category}")
    print(f"Details: {issue.details}")
```

**严重程度**:
- `ERROR`: 必须修复，阻止上线
- `WARNING`: 建议修复，可以上线但有风险
- `INFO`: 信息提示，无需修复

**类别**:
- `history_length`: 历史年限
- `trade_count`: 交易数量
- `market_regime`: 市场周期
- `data_quality`: 数据质量
- `performance`: 性能指标

---

## 💡 使用场景

### 场景1: 策略上线前验证

```python
# 策略开发完成，准备上线
validator = BacktestValidator()
config = validator.create_profile('moderate')
validator.config = config

result = validator.validate(equity_curve, trades, price_data)

if result.passed:
    print("✅ 验证通过，可以上线")
    deploy_strategy()
else:
    print("❌ 验证未通过，需要修复以下问题:")
    for error in result.get_errors():
        print(f"  - {error.message}")
```

### 场景2: 持续监控回测质量

```python
# 定期检查回测质量
validator = BacktestValidator()

for strategy_id in strategies:
    equity = load_equity_curve(strategy_id)
    trades = load_trades(strategy_id)
    
    result = validator.validate(equity, trades)
    
    if not result.passed:
        alert(f"策略 {strategy_id} 回测质量下降")
```

### 场景3: 不同策略类型使用不同标准

```python
def validate_strategy(strategy_type, equity, trades):
    validator = BacktestValidator()
    
    if strategy_type == 'long_term':
        config = validator.create_profile('strict')
    elif strategy_type == 'medium_term':
        config = validator.create_profile('moderate')
    else:
        config = validator.create_profile('relaxed')
    
    validator.config = config
    return validator.validate(equity, trades)
```

---

## 🔗 与金策智算的对比

| 功能 | 金策智算 | 本实现 | 状态 |
|------|----------|--------|------|
| 最小历史年限 | ✅ | ✅ | ✅ 完全实现 |
| 市场周期覆盖 | ✅ | ✅ | ✅ 完全实现 |
| 数据质量检查 | ✅ | ✅ | ✅ 完全实现 |
| 配置文件管理 | ✅ | ✅ | ✅ 完全实现 |
| 性能指标验证 | 部分 | ✅ | ✨ 增强功能 |
| 三级严重程度 | ❌ | ✅ | ✨ 增强功能 |

---

## 🧪 测试

运行单元测试：

```bash
python -m pytest quant/tests/test_backtest_validator.py -v
```

运行示例：

```bash
python quant/examples/backtest_validator_example.py
```

---

## 📈 完整示例

```python
from quantsys.backtest import BacktestValidator, ValidatorConfig
import pandas as pd
import numpy as np

# 1. 创建验证器
config = ValidatorConfig(
    min_history_years=5.0,
    min_trade_count=100,
    require_bull_market=True,
    require_bear_market=True,
    min_sharpe_ratio=0.5,
    max_drawdown_threshold=0.30
)
validator = BacktestValidator(config)

# 2. 准备回测数据
dates = pd.date_range(start='2018-01-01', periods=252*6, freq='D')
equity = pd.Series(np.linspace(100000, 180000, len(dates)), index=dates)

trades = [
    {'date': dates[i*10], 'pnl': 500, 'return_pct': 0.02}
    for i in range(150)
]

price_data = pd.DataFrame({
    'close': np.linspace(50, 60, len(dates))
}, index=dates)

# 3. 执行验证
result = validator.validate(equity, trades, price_data)

# 4. 处理结果
print(f"验证结果: {'通过' if result.passed else '未通过'}")
print(f"\n摘要:")
for key, value in result.summary.items():
    print(f"  {key}: {value}")

if not result.passed:
    print(f"\n错误:")
    for error in result.get_errors():
        print(f"  ❌ {error.message}")

if result.get_warnings():
    print(f"\n警告:")
    for warning in result.get_warnings():
        print(f"  ⚠️ {warning.message}")
```

---

## 📚 API参考

### ValidatorConfig

```python
@dataclass
class ValidatorConfig:
    min_history_years: float = 5.0
    min_trade_count: int = 100
    max_data_gap_days: int = 10
    max_missing_data_pct: float = 0.05
    require_bull_market: bool = True
    require_bear_market: bool = True
    require_sideways_market: bool = True
    bull_threshold: float = 0.20
    bear_threshold: float = -0.15
    sideways_threshold: float = 0.10
    max_price_jump_pct: float = 0.30
    min_sharpe_ratio: Optional[float] = None
    max_drawdown_threshold: Optional[float] = None
```

### BacktestValidator

```python
# 创建验证器
validator = BacktestValidator(config)

# 执行验证
result = validator.validate(equity_curve, trades, price_data)

# 创建配置文件
config = validator.create_profile('strict')  # 'strict', 'moderate', 'relaxed'
```

### ValidationResult

```python
result.passed          # 是否通过
result.issues          # 所有问题列表
result.summary         # 验证摘要
result.get_errors()    # 获取错误
result.get_warnings()  # 获取警告
```

---

## 💡 使用建议

### 1. 选择合适的配置文件

- **长期策略**（持仓周期>1个月）：使用 `strict` 配置
- **中期策略**（持仓周期1周-1个月）：使用 `moderate` 配置
- **短期策略**（持仓周期<1周）：使用 `relaxed` 配置

### 2. 数据质量优先

数据质量问题会严重影响回测结果的可靠性，建议：
- 始终提供 `price_data` 参数进行数据质量检查
- 修复所有数据质量WARNING
- 确保数据来源可靠

### 3. 市场周期覆盖

确保策略在不同市场环境下都经过验证：
- 至少经历一次完整的牛熊周期
- 对于长期策略，建议经历2-3个完整周期
- 震荡市验证对于均值回归策略尤为重要

### 4. 性能指标设置

根据策略类型设置合理的性能指标：
- 趋势策略：夏普比率 > 1.0，回撤 < 20%
- 均值回归策略：夏普比率 > 0.8，回撤 < 25%
- 高频策略：夏普比率 > 2.0，回撤 < 10%

---

## 🎓 最佳实践

1. **策略开发流程**
   ```
   策略开发 → 回测 → 基线验证 → 修复问题 → 再次验证 → 上线
   ```

2. **持续验证**
   - 定期重新验证已上线策略
   - 市场环境变化时重新验证
   - 策略参数调整后重新验证

3. **问题处理优先级**
   - ERROR：必须立即修复
   - WARNING：评估风险后决定是否修复
   - INFO：仅供参考

4. **文档记录**
   - 保存每次验证结果
   - 记录问题修复过程
   - 建立策略验证档案
