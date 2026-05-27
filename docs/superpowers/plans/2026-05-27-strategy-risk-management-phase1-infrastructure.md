# 策略风控管理系统 - Phase 1: 基础设施

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 搭建策略风控管理的核心框架，包括 SignalProcessor 服务、StrategyBase 扩展、数据库迁移、OrderService 集成和监控系统。

**Architecture:** 采用分层架构，策略层通过扩展的信号结构返回风控信息，SignalProcessor 统一处理和验证，OrderService 创建订单组（主订单 + 止损单 + 止盈单），数据库持久化完整风控参数。向后兼容现有 19 个策略。

**Tech Stack:** Python 3.13, PostgreSQL, Flask, pytest

**Dependencies:** 
- 设计文档: `docs/superpowers/specs/2026-05-27-strategy-risk-management-design.md`
- 现有代码: `quantsys-v2/quantlib/engine/position_sizing.py` (已存在)
- 现有代码: `quantsys-v2/quantlib/engine/risk_rules.py` (已存在)

---

## 文件结构

### 新增文件

```
quantsys-v2/
├── migrations/
│   └── add_risk_management_fields.sql          # 数据库迁移脚本
├── services/
│   ├── signal_processor.py                     # 信号处理服务（核心）
│   └── signal_monitoring.py                    # 信号监控服务
├── api/routes/
│   ├── signals.py                              # 信号执行 API
│   └── monitoring.py                           # 监控 API
└── tests/
    ├── test_signal_processor.py                # SignalProcessor 单元测试
    ├── test_signal_monitoring.py               # SignalMonitor 单元测试
    ├── test_strategy_base_helpers.py           # StrategyBase 辅助方法测试
    └── integration/
        └── test_signal_to_order_flow.py        # 完整流程集成测试
```

### 修改文件

```
quantsys-v2/
├── quantlib/engine/
│   └── strategy_base.py                        # 添加风控辅助方法
├── services/
│   └── order_service.py                        # 添加 create_order_from_signal()
├── repositories/
│   └── portfolio_repository.py                 # 添加 create_order_with_risk_params()
└── api/
    └── server.py                               # 注册新的 Blueprint
```

---

## Task 1: 数据库迁移

**Files:**
- Create: `quantsys-v2/migrations/add_risk_management_fields.sql`
- Test: 手动测试（在测试数据库上执行）

- [ ] **Step 1: 创建迁移脚本**

创建文件 `quantsys-v2/migrations/add_risk_management_fields.sql`:

```sql
-- 策略风控管理系统 - 数据库迁移
-- 添加风控字段到 orders 表

-- 1. 添加新字段
ALTER TABLE orders ADD COLUMN IF NOT EXISTS stop_loss_price DECIMAL(10, 2);
ALTER TABLE orders ADD COLUMN IF NOT EXISTS take_profit_price DECIMAL(10, 2);
ALTER TABLE orders ADD COLUMN IF NOT EXISTS parent_order_id INTEGER;
ALTER TABLE orders ADD COLUMN IF NOT EXISTS order_group VARCHAR(50);
ALTER TABLE orders ADD COLUMN IF NOT EXISTS risk_params JSONB;

-- 2. 添加索引
CREATE INDEX IF NOT EXISTS idx_orders_parent_order_id ON orders(parent_order_id);
CREATE INDEX IF NOT EXISTS idx_orders_order_group ON orders(order_group);

-- 3. 添加外键约束
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'fk_parent_order'
    ) THEN
        ALTER TABLE orders 
        ADD CONSTRAINT fk_parent_order 
        FOREIGN KEY (parent_order_id) 
        REFERENCES orders(id) 
        ON DELETE SET NULL;
    END IF;
END $$;

-- 4. 添加注释
COMMENT ON COLUMN orders.stop_loss_price IS '止损价格';
COMMENT ON COLUMN orders.take_profit_price IS '止盈价格';
COMMENT ON COLUMN orders.parent_order_id IS '关联的主订单ID（用于止损单、止盈单）';
COMMENT ON COLUMN orders.order_group IS '订单组标识（UUID）';
COMMENT ON COLUMN orders.risk_params IS '完整的风控参数（JSON格式）';
```

- [ ] **Step 2: 在测试数据库上执行迁移**

```bash
cd quantsys-v2
psql -d quant_test -f migrations/add_risk_management_fields.sql
```

Expected output: 
```
ALTER TABLE
ALTER TABLE
ALTER TABLE
ALTER TABLE
ALTER TABLE
CREATE INDEX
CREATE INDEX
DO
COMMENT
COMMENT
COMMENT
COMMENT
COMMENT
```

- [ ] **Step 3: 验证迁移成功**

```bash
psql -d quant_test -c "\d orders"
```

Expected: 应该看到新增的 5 个字段：
- stop_loss_price
- take_profit_price
- parent_order_id
- order_group
- risk_params

- [ ] **Step 4: 测试外键约束**

```bash
psql -d quant_test -c "
INSERT INTO orders (symbol, name, action, order_type, quantity, price, status, filled_quantity, created_at)
VALUES ('TEST.SH', 'Test', 'buy', 'limit', 100, 10.0, 'pending', 0, NOW())
RETURNING id;
"
```

记录返回的 ID（假设是 999），然后测试外键：

```bash
psql -d quant_test -c "
INSERT INTO orders (symbol, name, action, order_type, quantity, price, status, filled_quantity, parent_order_id, created_at)
VALUES ('TEST.SH', 'Test Stop', 'sell', 'stop', 100, 9.0, 'pending', 0, 999, NOW());
"
```

Expected: 成功插入（外键有效）

- [ ] **Step 5: 清理测试数据**

```bash
psql -d quant_test -c "DELETE FROM orders WHERE symbol = 'TEST.SH';"
```

- [ ] **Step 6: Commit**

```bash
git add migrations/add_risk_management_fields.sql
git commit -m "feat(db): add risk management fields to orders table

- Add stop_loss_price, take_profit_price columns
- Add parent_order_id for order grouping
- Add order_group UUID for batch operations
- Add risk_params JSONB for full risk parameters
- Add indexes and foreign key constraints"
```

---

## Task 2: StrategyBase 辅助方法

**Files:**
- Modify: `quantsys-v2/quantlib/engine/strategy_base.py`
- Test: `quantsys-v2/tests/test_strategy_base_helpers.py`

- [ ] **Step 1: 编写测试 - ATR 止损构建器**

创建文件 `quantsys-v2/tests/test_strategy_base_helpers.py`:

```python
"""
测试 StrategyBase 风控辅助方法
"""
import pytest
from quantlib.engine.strategy_base import StrategyBase


class ConcreteStrategy(StrategyBase):
    """用于测试的具体策略类"""
    def generate_signal(self, klines, params=None):
        return {'action': 'hold', 'confidence': 0.5, 'reason': 'test'}


class TestStrategyBaseHelpers:
    
    def test_build_stop_loss_atr_long(self):
        """测试构建 ATR 止损（做多）"""
        strategy = ConcreteStrategy()
        
        result = strategy._build_stop_loss_atr(
            entry_price=100.0,
            atr=2.5,
            multiplier=2.0,
            direction='long'
        )
        
        assert result['type'] == 'atr'
        assert result['price'] == 95.0  # 100 - 2.5 * 2
        assert result['params']['atr_value'] == 2.5
        assert result['params']['atr_multiplier'] == 2.0
        assert result['params']['entry_price'] == 100.0
    
    def test_build_stop_loss_atr_short(self):
        """测试构建 ATR 止损（做空）"""
        strategy = ConcreteStrategy()
        
        result = strategy._build_stop_loss_atr(
            entry_price=100.0,
            atr=2.5,
            multiplier=2.0,
            direction='short'
        )
        
        assert result['type'] == 'atr'
        assert result['price'] == 105.0  # 100 + 2.5 * 2
    
    def test_build_stop_loss_percent_long(self):
        """测试构建固定百分比止损（做多）"""
        strategy = ConcreteStrategy()
        
        result = strategy._build_stop_loss_percent(
            entry_price=100.0,
            percent=0.08,
            direction='long'
        )
        
        assert result['type'] == 'fixed_percent'
        assert result['price'] == 92.0  # 100 * (1 - 0.08)
        assert result['params']['percent'] == 0.08
        assert result['params']['entry_price'] == 100.0
    
    def test_build_stop_loss_trailing(self):
        """测试构建追踪止损"""
        strategy = ConcreteStrategy()
        
        result = strategy._build_stop_loss_trailing(
            entry_price=100.0,
            trailing_percent=0.05,
            direction='long'
        )
        
        assert result['type'] == 'trailing'
        assert result['price'] == 95.0  # 100 * (1 - 0.05)
        assert result['params']['trailing_percent'] == 0.05
    
    def test_build_position_sizing_kelly(self):
        """测试构建 Kelly 仓位参数"""
        strategy = ConcreteStrategy()
        
        result = strategy._build_position_sizing_kelly(
            win_rate=0.60,
            profit_loss_ratio=2.5,
            kelly_fraction=0.25
        )
        
        assert result['method'] == 'kelly'
        assert result['value'] is None
        assert result['params']['win_rate'] == 0.60
        assert result['params']['profit_loss_ratio'] == 2.5
        assert result['params']['kelly_fraction'] == 0.25
    
    def test_build_position_sizing_percent(self):
        """测试构建固定比例仓位"""
        strategy = ConcreteStrategy()
        
        result = strategy._build_position_sizing_percent(0.15)
        
        assert result['method'] == 'fixed_percent'
        assert result['value'] == 0.15
        assert result['params'] == {}
    
    def test_build_position_sizing_shares(self):
        """测试构建固定股数仓位"""
        strategy = ConcreteStrategy()
        
        result = strategy._build_position_sizing_shares(2000)
        
        assert result['method'] == 'fixed_shares'
        assert result['value'] == 2000
        assert result['params'] == {}
```

- [ ] **Step 2: 运行测试确认失败**

```bash
cd quantsys-v2
pytest tests/test_strategy_base_helpers.py -v
```

Expected: 所有测试失败，提示方法不存在

- [ ] **Step 3: 实现 StrategyBase 辅助方法**

修改 `quantsys-v2/quantlib/engine/strategy_base.py`，在类的末尾添加：

```python
    # ==================== 风控辅助方法 ====================
    
    def _build_stop_loss_atr(
        self, 
        entry_price: float, 
        atr: float, 
        multiplier: float = 2.0,
        direction: str = 'long'
    ) -> dict:
        """
        构建 ATR 止损
        
        Args:
            entry_price: 入场价格
            atr: ATR 值
            multiplier: ATR 倍数
            direction: 'long' 做多 | 'short' 做空
            
        Returns:
            止损配置字典
        """
        if direction == 'long':
            stop_price = entry_price - atr * multiplier
        else:
            stop_price = entry_price + atr * multiplier
            
        return {
            'type': 'atr',
            'price': round(stop_price, 2),
            'params': {
                'atr_value': atr,
                'atr_multiplier': multiplier,
                'entry_price': entry_price
            }
        }
    
    def _build_stop_loss_percent(
        self,
        entry_price: float,
        percent: float = 0.08,
        direction: str = 'long'
    ) -> dict:
        """
        构建固定百分比止损
        
        Args:
            entry_price: 入场价格
            percent: 止损百分比（如 0.08 表示 -8%）
            direction: 'long' 做多 | 'short' 做空
            
        Returns:
            止损配置字典
        """
        if direction == 'long':
            stop_price = entry_price * (1 - percent)
        else:
            stop_price = entry_price * (1 + percent)
            
        return {
            'type': 'fixed_percent',
            'price': round(stop_price, 2),
            'params': {
                'percent': percent,
                'entry_price': entry_price
            }
        }
    
    def _build_stop_loss_trailing(
        self,
        entry_price: float,
        trailing_percent: float = None,
        trailing_atr_multiplier: float = None,
        atr: float = None,
        direction: str = 'long'
    ) -> dict:
        """
        构建追踪止损
        
        Args:
            entry_price: 入场价格
            trailing_percent: 追踪百分比（如 0.05 表示追踪 5%）
            trailing_atr_multiplier: 追踪 ATR 倍数
            atr: ATR 值（使用 ATR 追踪时需要）
            direction: 'long' 做多 | 'short' 做空
            
        Returns:
            止损配置字典
        """
        params = {}
        
        if trailing_percent is not None:
            params['trailing_percent'] = trailing_percent
            if direction == 'long':
                stop_price = entry_price * (1 - trailing_percent)
            else:
                stop_price = entry_price * (1 + trailing_percent)
        elif trailing_atr_multiplier is not None and atr is not None:
            params['trailing_atr_multiplier'] = trailing_atr_multiplier
            if direction == 'long':
                stop_price = entry_price - atr * trailing_atr_multiplier
            else:
                stop_price = entry_price + atr * trailing_atr_multiplier
        else:
            raise ValueError("Must provide either trailing_percent or (trailing_atr_multiplier + atr)")
            
        return {
            'type': 'trailing',
            'price': round(stop_price, 2),
            'params': params
        }
    
    def _build_position_sizing_kelly(
        self,
        win_rate: float,
        profit_loss_ratio: float,
        kelly_fraction: float = 0.25
    ) -> dict:
        """
        构建 Kelly 仓位参数
        
        Args:
            win_rate: 胜率（0-1）
            profit_loss_ratio: 盈亏比（平均盈利/平均亏损）
            kelly_fraction: Kelly 分数（通常使用 1/4 Kelly）
            
        Returns:
            仓位配置字典
        """
        return {
            'method': 'kelly',
            'value': None,  # 由执行层计算
            'params': {
                'win_rate': win_rate,
                'profit_loss_ratio': profit_loss_ratio,
                'kelly_fraction': kelly_fraction
            }
        }
    
    def _build_position_sizing_percent(self, percent: float) -> dict:
        """
        构建固定比例仓位
        
        Args:
            percent: 仓位比例（如 0.15 表示 15%）
            
        Returns:
            仓位配置字典
        """
        return {
            'method': 'fixed_percent',
            'value': percent,
            'params': {}
        }
    
    def _build_position_sizing_shares(self, shares: int) -> dict:
        """
        构建固定股数仓位
        
        Args:
            shares: 股数
            
        Returns:
            仓位配置字典
        """
        return {
            'method': 'fixed_shares',
            'value': shares,
            'params': {}
        }
```

- [ ] **Step 4: 运行测试确认通过**

```bash
pytest tests/test_strategy_base_helpers.py -v
```

Expected: 所有测试通过

- [ ] **Step 5: Commit**

```bash
git add quantlib/engine/strategy_base.py tests/test_strategy_base_helpers.py
git commit -m "feat(strategy): add risk management helper methods to StrategyBase

- Add _build_stop_loss_atr() for ATR-based stop loss
- Add _build_stop_loss_percent() for fixed percentage stop loss
- Add _build_stop_loss_trailing() for trailing stop loss
- Add _build_position_sizing_kelly() for Kelly criterion
- Add _build_position_sizing_percent() for fixed percentage position
- Add _build_position_sizing_shares() for fixed shares position
- Add comprehensive unit tests"
```


---

## Task 3: SignalProcessor 服务 - 核心处理逻辑

**Files:**
- Create: `quantsys-v2/services/signal_processor.py`
- Test: `quantsys-v2/tests/test_signal_processor.py`

- [ ] **Step 1: 编写测试 - 处理旧格式信号（向后兼容）**

创建文件 `quantsys-v2/tests/test_signal_processor.py`:

```python
"""
测试 SignalProcessor 服务
"""
import pytest
from services.signal_processor import SignalProcessor, SignalProcessingError
from services.data_service import DataService


class TestSignalProcessor:
    
    @pytest.fixture
    def processor(self):
        """创建 SignalProcessor 实例"""
        return SignalProcessor(DataService())
    
    @pytest.fixture
    def account_balance(self):
        """模拟账户余额"""
        return {
            'total_assets': 1000000,
            'cash': 500000
        }
    
    def test_process_legacy_signal(self, processor, account_balance):
        """测试处理旧格式信号（向后兼容）"""
        signal = {
            'action': 'buy',
            'confidence': 0.85,
            'reason': 'MA cross'
        }
        
        result = processor.process_signal(
            signal, 
            '600519.SH', 
            52.30,
            account_balance
        )
        
        assert result['action'] == 'buy'
        assert result['price'] == 52.30
        assert result['quantity'] > 0
        assert result['quantity'] % 100 == 0  # 手数检查
        assert result['stop_loss_price'] == pytest.approx(52.30 * 0.92)  # 默认 -8%
        assert result['take_profit_price'] is None
        assert 'warnings' in result
    
    def test_process_signal_with_atr_stop_loss(self, processor, account_balance):
        """测试 ATR 止损"""
        signal = {
            'action': 'buy',
            'confidence': 0.85,
            'reason': 'Volatility breakout',
            'risk_management': {
                'stop_loss': {
                    'type': 'atr',
                    'price': 48.50,
                    'params': {'atr_value': 2.35, 'atr_multiplier': 2.0}
                }
            }
        }
        
        result = processor.process_signal(
            signal, 
            '600519.SH', 
            52.30,
            account_balance
        )
        
        assert result['stop_loss_price'] == 48.50
        assert result['risk_params']['stop_loss']['type'] == 'atr'
    
    def test_process_signal_with_fixed_percent_sizing(self, processor, account_balance):
        """测试固定比例仓位"""
        signal = {
            'action': 'buy',
            'confidence': 0.85,
            'reason': 'Test',
            'risk_management': {
                'position_sizing': {
                    'method': 'fixed_percent',
                    'value': 0.15,  # 15%
                    'params': {}
                }
            }
        }
        
        result = processor.process_signal(
            signal, 
            '600519.SH', 
            52.30,
            account_balance
        )
        
        expected_qty = int((1000000 * 0.15) / 52.30 / 100) * 100
        assert result['quantity'] == expected_qty
    
    def test_invalid_signal_structure(self, processor, account_balance):
        """测试无效信号结构"""
        signal = {
            'action': 'buy'
            # 缺少 confidence 和 reason
        }
        
        with pytest.raises(ValueError, match="Missing required field"):
            processor.process_signal(signal, '600519.SH', 52.30, account_balance)
```

- [ ] **Step 2: 运行测试确认失败**

```bash
cd quantsys-v2
pytest tests/test_signal_processor.py -v
```

Expected: 测试失败，提示模块不存在

- [ ] **Step 3: 实现 SignalProcessor - 基础结构**

创建文件 `quantsys-v2/services/signal_processor.py`:

```python
"""
信号处理服务

统一处理策略信号，提取和计算风控参数。
"""
import logging
from typing import Dict, Any, List

from services.data_service import DataService

logger = logging.getLogger(__name__)


class SignalProcessingError(Exception):
    """信号处理错误基类"""
    pass


class InvalidStopLossError(SignalProcessingError):
    """止损价格无效"""
    pass


class InvalidPositionSizeError(SignalProcessingError):
    """仓位计算错误"""
    pass


class SignalProcessor:
    """信号处理器"""
    
    def __init__(self, ds: DataService):
        """
        初始化信号处理器
        
        Args:
            ds: DataService 实例
        """
        self.ds = ds
    
    def process_signal(
        self, 
        signal: Dict[str, Any], 
        symbol: str,
        current_price: float,
        account_balance: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        处理信号，返回完整的交易参数
        
        Args:
            signal: 策略信号
            symbol: 股票代码
            current_price: 当前价格
            account_balance: 账户余额
            
        Returns:
            {
                'action': str,
                'quantity': int,
                'price': float,
                'stop_loss_price': float,
                'take_profit_price': float,
                'reason': str,
                'risk_params': dict,
                'warnings': list
            }
        """
        logger.info(
            f"Processing signal: symbol={symbol}, action={signal.get('action')}, "
            f"confidence={signal.get('confidence'):.2f}, price={current_price}"
        )
        
        # 验证信号结构
        self._validate_signal_structure(signal)
        
        # 验证价格有效性
        if current_price <= 0:
            raise ValueError(f"Invalid current price: {current_price}")
        
        result = {
            'action': signal['action'],
            'price': current_price,
            'reason': signal.get('reason', ''),
            'stop_loss_price': None,
            'take_profit_price': None,
            'quantity': 0,
            'risk_params': {},
            'warnings': []
        }
        
        risk_mgmt = signal.get('risk_management', {})
        
        # 处理止损
        try:
            result['stop_loss_price'] = self._process_stop_loss(
                risk_mgmt.get('stop_loss'),
                current_price,
                signal['action']
            )
            if risk_mgmt.get('stop_loss'):
                result['risk_params']['stop_loss'] = risk_mgmt['stop_loss']
        except InvalidStopLossError as e:
            logger.warning(f"Invalid stop loss, using default: {e}")
            result['warnings'].append(f"止损价格无效，使用默认值: {str(e)}")
            result['stop_loss_price'] = self._get_default_stop_loss(
                current_price, signal['action']
            )
        
        # 处理止盈
        try:
            result['take_profit_price'] = self._process_take_profit(
                risk_mgmt.get('take_profit'),
                current_price,
                signal['action']
            )
            if risk_mgmt.get('take_profit'):
                result['risk_params']['take_profit'] = risk_mgmt['take_profit']
        except Exception as e:
            logger.warning(f"Invalid take profit: {e}")
            result['warnings'].append(f"止盈价格无效: {str(e)}")
        
        # 处理仓位计算
        try:
            result['quantity'] = self._calculate_position_size(
                risk_mgmt.get('position_sizing'),
                current_price,
                account_balance,
                signal.get('indicators', {})
            )
            if risk_mgmt.get('position_sizing'):
                result['risk_params']['position_sizing'] = risk_mgmt['position_sizing']
        except InvalidPositionSizeError as e:
            logger.warning(f"Invalid position size, using default: {e}")
            result['warnings'].append(f"仓位计算失败，使用默认值: {str(e)}")
            result['quantity'] = self._calculate_default_position(
                current_price, account_balance
            )
        
        logger.info(
            f"Signal processed: symbol={symbol}, quantity={result['quantity']}, "
            f"stop_loss={result['stop_loss_price']}, warnings={len(result['warnings'])}"
        )
        
        return result
    
    def _validate_signal_structure(self, signal: Dict[str, Any]):
        """验证信号基础结构"""
        required_fields = ['action', 'confidence', 'reason']
        for field in required_fields:
            if field not in signal:
                raise ValueError(f"Missing required field: {field}")
        
        if signal['action'] not in ('buy', 'sell', 'hold'):
            raise ValueError(f"Invalid action: {signal['action']}")
        
        if not 0 <= signal['confidence'] <= 1:
            raise ValueError(f"Invalid confidence: {signal['confidence']}")
    
    def _process_stop_loss(
        self, 
        stop_loss_config: Dict[str, Any], 
        current_price: float, 
        action: str
    ) -> float:
        """处理止损配置"""
        if not stop_loss_config:
            return self._get_default_stop_loss(current_price, action)
        
        stop_price = stop_loss_config.get('price')
        
        if stop_price is None or stop_price <= 0:
            raise InvalidStopLossError(f"Invalid stop loss price: {stop_price}")
        
        # 验证止损价格合理性
        if action == 'buy':
            if stop_price >= current_price:
                raise InvalidStopLossError(
                    f"Buy stop loss {stop_price} must be below current price {current_price}"
                )
        elif action == 'sell':
            if stop_price <= current_price:
                raise InvalidStopLossError(
                    f"Sell stop loss {stop_price} must be above current price {current_price}"
                )
        
        return stop_price
    
    def _process_take_profit(
        self, 
        take_profit_config: Dict[str, Any], 
        current_price: float, 
        action: str
    ) -> float:
        """处理止盈配置"""
        if not take_profit_config:
            return None
        
        tp_price = take_profit_config.get('price')
        
        if tp_price is None or tp_price <= 0:
            return None
        
        # 验证止盈价格合理性
        if action == 'buy':
            if tp_price <= current_price:
                logger.warning(
                    f"Buy take profit {tp_price} should be above current price {current_price}"
                )
        elif action == 'sell':
            if tp_price >= current_price:
                logger.warning(
                    f"Sell take profit {tp_price} should be below current price {current_price}"
                )
        
        return tp_price
    
    def _calculate_position_size(
        self,
        sizing_config: Dict[str, Any],
        price: float,
        account_balance: Dict[str, Any],
        indicators: Dict[str, Any]
    ) -> int:
        """根据配置计算仓位"""
        if not sizing_config:
            return self._calculate_default_position(price, account_balance)
        
        method = sizing_config['method']
        value = sizing_config.get('value')
        params = sizing_config.get('params', {})
        
        total_equity = account_balance.get('total_assets', 1000000)
        available_cash = account_balance.get('cash', total_equity * 0.5)
        
        if method == 'fixed_shares':
            return int(value)
        
        elif method == 'fixed_percent':
            target_amount = total_equity * value
            shares = int(target_amount / price)
            return self._round_to_lot(shares)
        
        elif method == 'kelly':
            from quantlib.engine.position_sizing import KellyPositionSizer
            sizer = KellyPositionSizer(
                win_rate=params['win_rate'],
                profit_loss_ratio=params['profit_loss_ratio'],
                kelly_fraction=params.get('kelly_fraction', 0.25)
            )
            return sizer.calculate_position_size(
                price, available_cash, total_equity
            )
        
        else:
            raise ValueError(f"Unknown position sizing method: {method}")
    
    def _calculate_default_position(
        self,
        price: float,
        account_balance: Dict[str, Any],
        percent: float = 0.10
    ) -> int:
        """默认仓位计算（10%）"""
        total_equity = account_balance.get('total_assets', 1000000)
        target_amount = total_equity * percent
        shares = int(target_amount / price)
        return self._round_to_lot(shares)
    
    def _get_default_stop_loss(self, current_price: float, action: str) -> float:
        """获取默认止损价格（-8%）"""
        if action == 'buy':
            return round(current_price * 0.92, 2)
        elif action == 'sell':
            return round(current_price * 1.08, 2)
        return None
    
    @staticmethod
    def _round_to_lot(shares: int, lot_size: int = 100) -> int:
        """向下取整到手数"""
        return (shares // lot_size) * lot_size
```

- [ ] **Step 4: 运行测试确认通过**

```bash
pytest tests/test_signal_processor.py::TestSignalProcessor::test_process_legacy_signal -v
pytest tests/test_signal_processor.py::TestSignalProcessor::test_process_signal_with_atr_stop_loss -v
pytest tests/test_signal_processor.py::TestSignalProcessor::test_process_signal_with_fixed_percent_sizing -v
pytest tests/test_signal_processor.py::TestSignalProcessor::test_invalid_signal_structure -v
```

Expected: 所有测试通过

- [ ] **Step 5: Commit**

```bash
git add services/signal_processor.py tests/test_signal_processor.py
git commit -m "feat(services): add SignalProcessor for unified signal processing

- Implement core signal processing logic
- Support legacy signals (backward compatible)
- Process stop loss, take profit, and position sizing
- Add validation and error handling
- Add comprehensive unit tests"
```

---

## Task 4: SignalMonitor 监控服务

**Files:**
- Create: `quantsys-v2/services/signal_monitoring.py`
- Test: `quantsys-v2/tests/test_signal_monitoring.py`

- [ ] **Step 1: 编写测试**

创建文件 `quantsys-v2/tests/test_signal_monitoring.py`:

```python
"""
测试 SignalMonitor 服务
"""
import pytest
from services.signal_monitoring import SignalMonitor


class TestSignalMonitor:
    
    @pytest.fixture
    def monitor(self):
        """创建 SignalMonitor 实例"""
        return SignalMonitor()
    
    def test_record_signal_processing_success(self, monitor):
        """测试记录成功的信号处理"""
        monitor.record_signal_processing(
            strategy_name='TestStrategy',
            symbol='600519.SH',
            success=True,
            duration=0.025,
            warnings=['test warning']
        )
        
        metrics = monitor.get_metrics('TestStrategy')
        assert len(metrics) == 1
        
        key = 'TestStrategy:600519.SH'
        assert metrics[key]['count'] == 1
        assert metrics[key]['success'] == 1
        assert metrics[key]['failure'] == 0
        assert metrics[key]['warnings'] == 1
        assert metrics[key]['total_time'] == 0.025
    
    def test_record_signal_processing_failure(self, monitor):
        """测试记录失败的信号处理"""
        monitor.record_signal_processing(
            strategy_name='TestStrategy',
            symbol='600519.SH',
            success=False,
            duration=0.015,
            error='Test error'
        )
        
        metrics = monitor.get_metrics('TestStrategy')
        key = 'TestStrategy:600519.SH'
        
        assert metrics[key]['failure'] == 1
        assert len(metrics[key]['errors']) == 1
        assert metrics[key]['errors'][0]['error'] == 'Test error'
    
    def test_get_summary(self, monitor):
        """测试获取汇总统计"""
        # 记录多个信号
        monitor.record_signal_processing('S1', 'A', True, 0.01)
        monitor.record_signal_processing('S1', 'B', True, 0.02)
        monitor.record_signal_processing('S2', 'A', False, 0.03, error='err')
        
        summary = monitor.get_summary()
        
        assert summary['total_signals'] == 3
        assert summary['success_rate'] == pytest.approx(2/3)
        assert summary['failure_count'] == 1
        assert summary['avg_processing_time'] == pytest.approx(0.02)
        assert summary['strategies_monitored'] == 3  # S1:A, S1:B, S2:A
```

- [ ] **Step 2: 运行测试确认失败**

```bash
pytest tests/test_signal_monitoring.py -v
```

Expected: 测试失败，模块不存在

- [ ] **Step 3: 实现 SignalMonitor**

创建文件 `quantsys-v2/services/signal_monitoring.py`:

```python
"""
信号监控服务

监控信号处理性能和质量。
"""
from typing import Dict, Any
from collections import defaultdict
from datetime import datetime


class SignalMonitor:
    """监控信号处理性能和质量"""
    
    def __init__(self):
        self.metrics = defaultdict(lambda: {
            'count': 0,
            'success': 0,
            'failure': 0,
            'warnings': 0,
            'total_time': 0.0,
            'errors': []
        })
    
    def record_signal_processing(
        self,
        strategy_name: str,
        symbol: str,
        success: bool,
        duration: float,
        warnings: list = None,
        error: str = None
    ):
        """
        记录信号处理结果
        
        Args:
            strategy_name: 策略名称
            symbol: 股票代码
            success: 是否成功
            duration: 处理时间（秒）
            warnings: 警告列表
            error: 错误信息
        """
        key = f"{strategy_name}:{symbol}"
        m = self.metrics[key]
        
        m['count'] += 1
        m['total_time'] += duration
        
        if success:
            m['success'] += 1
        else:
            m['failure'] += 1
            if error:
                m['errors'].append({
                    'timestamp': datetime.now().isoformat(),
                    'error': error
                })
        
        if warnings:
            m['warnings'] += len(warnings)
    
    def get_metrics(self, strategy_name: str = None) -> Dict[str, Any]:
        """
        获取监控指标
        
        Args:
            strategy_name: 策略名称（可选，不传则返回所有）
            
        Returns:
            指标字典
        """
        if strategy_name:
            return {k: v for k, v in self.metrics.items() if k.startswith(strategy_name)}
        return dict(self.metrics)
    
    def get_summary(self) -> Dict[str, Any]:
        """
        获取汇总统计
        
        Returns:
            汇总统计字典
        """
        total_count = sum(m['count'] for m in self.metrics.values())
        total_success = sum(m['success'] for m in self.metrics.values())
        total_failure = sum(m['failure'] for m in self.metrics.values())
        total_warnings = sum(m['warnings'] for m in self.metrics.values())
        total_time = sum(m['total_time'] for m in self.metrics.values())
        
        return {
            'total_signals': total_count,
            'success_rate': total_success / total_count if total_count > 0 else 0,
            'failure_count': total_failure,
            'warning_count': total_warnings,
            'avg_processing_time': total_time / total_count if total_count > 0 else 0,
            'strategies_monitored': len(self.metrics)
        }


# 全局监控实例
signal_monitor = SignalMonitor()
```

- [ ] **Step 4: 运行测试确认通过**

```bash
pytest tests/test_signal_monitoring.py -v
```

Expected: 所有测试通过

- [ ] **Step 5: 集成监控到 SignalProcessor**

修改 `quantsys-v2/services/signal_processor.py`，在文件开头添加导入：

```python
import time
from services.signal_monitoring import signal_monitor
```

修改 `process_signal` 方法，在开头添加：

```python
    def process_signal(self, signal, symbol, current_price, account_balance):
        start_time = time.time()
        strategy_name = signal.get('strategy_name', 'unknown')
        
        try:
            # ... 原有处理逻辑 ...
            
            duration = time.time() - start_time
            signal_monitor.record_signal_processing(
                strategy_name=strategy_name,
                symbol=symbol,
                success=True,
                duration=duration,
                warnings=result.get('warnings', [])
            )
            
            return result
            
        except Exception as e:
            duration = time.time() - start_time
            signal_monitor.record_signal_processing(
                strategy_name=strategy_name,
                symbol=symbol,
                success=False,
                duration=duration,
                error=str(e)
            )
            raise
```

- [ ] **Step 6: 测试集成**

```bash
pytest tests/test_signal_processor.py -v
```

Expected: 所有测试仍然通过

- [ ] **Step 7: Commit**

```bash
git add services/signal_monitoring.py tests/test_signal_monitoring.py services/signal_processor.py
git commit -m "feat(services): add SignalMonitor for performance tracking

- Implement signal processing monitoring
- Track success rate, failure count, processing time
- Integrate with SignalProcessor
- Add comprehensive unit tests"
```


---

## Task 5: OrderService 扩展

**Files:**
- Modify: `quantsys-v2/services/order_service.py`
- Modify: `quantsys-v2/repositories/portfolio_repository.py`
- Test: `quantsys-v2/tests/integration/test_signal_to_order_flow.py`

- [ ] **Step 1: 扩展 PortfolioRepository**

修改 `quantsys-v2/repositories/portfolio_repository.py`，添加新方法（在类的末尾）：

```python
    def create_order_with_risk_params(
        self,
        symbol: str,
        name: str,
        action: str,
        order_type: str,
        quantity: int,
        price: float,
        status: str = 'pending',
        stop_loss_price: float = None,
        take_profit_price: float = None,
        parent_order_id: int = None,
        order_group: str = None,
        risk_params: dict = None,
        reason: str = None,
        signal_id: int = None,
        expires_at: str = None
    ) -> int:
        """
        创建订单（支持风控参数）
        
        Returns:
            订单 ID
        """
        import json
        from datetime import datetime, timedelta
        
        if expires_at is None:
            expires_at = (datetime.now() + timedelta(days=7)).strftime('%Y-%m-%d %H:%M:%S')
        
        risk_params_json = json.dumps(risk_params) if risk_params else None
        
        query = """
            INSERT INTO orders (
                symbol, name, action, order_type, quantity, price, status,
                filled_quantity, stop_loss_price, take_profit_price,
                parent_order_id, order_group, risk_params,
                reason, signal_id, expires_at, created_at
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW()
            ) RETURNING id
        """
        
        result = self.db.execute_query(query, (
            symbol, name, action, order_type, quantity, price, status,
            0, stop_loss_price, take_profit_price,
            parent_order_id, order_group, risk_params_json,
            reason, signal_id, expires_at
        ))
        
        return result[0]['id'] if result else None
```

- [ ] **Step 2: 添加 create_order_from_signal 到 OrderService**

修改 `quantsys-v2/services/order_service.py`，在文件末尾添加：

```python
def create_order_from_signal(
    ds: DataService,
    signal: dict,
    symbol: str,
    order_type: str = 'limit'
) -> dict:
    """
    从策略信号创建订单
    
    Args:
        ds: DataService 实例
        signal: 策略信号
        symbol: 股票代码
        order_type: 订单类型
        
    Returns:
        {
            'order_id': int,
            'stop_loss_order_id': int,
            'take_profit_order_id': int,
            'trade_params': dict
        }
    """
    from services.signal_processor import SignalProcessor
    import uuid
    
    # 1. 获取当前价格和账户信息
    latest = ds.kline.get_latest_daily_kline(symbol)
    current_price = latest['close'] if latest else 0
    account = ds.risk.get_latest_balance()
    
    # 2. 处理信号
    processor = SignalProcessor(ds)
    trade_params = processor.process_signal(
        signal, symbol, current_price, account
    )
    
    # 3. 获取股票信息
    stock = ds.stock.get_by_symbol(symbol)
    if not stock:
        raise RuntimeError(f"股票不存在: {symbol}")
    
    stock_name = stock.get('name', symbol)
    
    # 4. 生成订单组 ID
    order_group = str(uuid.uuid4())
    
    # 5. 创建主订单
    order_id = ds.portfolio.create_order_with_risk_params(
        symbol=symbol,
        name=stock_name,
        action=trade_params['action'],
        order_type=order_type,
        quantity=trade_params['quantity'],
        price=trade_params['price'],
        stop_loss_price=trade_params['stop_loss_price'],
        take_profit_price=trade_params['take_profit_price'],
        order_group=order_group,
        risk_params=trade_params.get('risk_params'),
        reason=trade_params['reason']
    )
    
    result = {
        'order_id': order_id,
        'trade_params': trade_params
    }
    
    # 6. 创建止损单（如果有）
    if trade_params['stop_loss_price'] and trade_params['action'] == 'buy':
        stop_loss_order_id = ds.portfolio.create_order_with_risk_params(
            symbol=symbol,
            name=stock_name,
            action='sell',
            order_type='stop',
            quantity=trade_params['quantity'],
            price=trade_params['stop_loss_price'],
            parent_order_id=order_id,
            order_group=order_group,
            reason=f"止损单（关联订单 {order_id}）"
        )
        result['stop_loss_order_id'] = stop_loss_order_id
    
    # 7. 创建止盈单（如果有）
    if trade_params['take_profit_price'] and trade_params['action'] == 'buy':
        take_profit_order_id = ds.portfolio.create_order_with_risk_params(
            symbol=symbol,
            name=stock_name,
            action='sell',
            order_type='limit',
            quantity=trade_params['quantity'],
            price=trade_params['take_profit_price'],
            parent_order_id=order_id,
            order_group=order_group,
            reason=f"止盈单（关联订单 {order_id}）"
        )
        result['take_profit_order_id'] = take_profit_order_id
    
    logger.info(
        f"Order group created: order_id={order_id}, "
        f"stop_loss={result.get('stop_loss_order_id')}, "
        f"take_profit={result.get('take_profit_order_id')}"
    )
    
    return result
```

- [ ] **Step 3: 编写集成测试**

创建文件 `quantsys-v2/tests/integration/test_signal_to_order_flow.py`:

```python
"""
测试信号到订单的完整流程
"""
import pytest
from services.order_service import create_order_from_signal
from services.data_service import DataService


class TestSignalToOrderFlow:
    
    @pytest.fixture
    def ds(self):
        """创建 DataService 实例"""
        return DataService()
    
    def test_create_order_from_legacy_signal(self, ds):
        """测试从旧格式信号创建订单"""
        signal = {
            'action': 'buy',
            'confidence': 0.85,
            'reason': 'Test signal'
        }
        
        result = create_order_from_signal(ds, signal, '600519.SH')
        
        assert 'order_id' in result
        assert result['order_id'] > 0
        assert 'trade_params' in result
        
        # 验证订单创建
        order = ds.portfolio.get_order_by_id(result['order_id'])
        assert order is not None
        assert order['action'] == 'buy'
        assert order['quantity'] > 0
        assert order['stop_loss_price'] is not None  # 应该有默认止损
    
    def test_create_order_with_risk_management(self, ds):
        """测试从新格式信号创建订单组"""
        signal = {
            'action': 'buy',
            'confidence': 0.85,
            'reason': 'ATR breakout',
            'risk_management': {
                'stop_loss': {
                    'type': 'atr',
                    'price': 48.50,
                    'params': {'atr_value': 2.35, 'atr_multiplier': 2.0}
                },
                'take_profit': {
                    'type': 'atr',
                    'price': 55.20,
                    'params': {'atr_multiplier': 3.0}
                },
                'position_sizing': {
                    'method': 'fixed_percent',
                    'value': 0.15,
                    'params': {}
                }
            }
        }
        
        result = create_order_from_signal(ds, signal, '600519.SH')
        
        # 验证主订单
        assert 'order_id' in result
        main_order = ds.portfolio.get_order_by_id(result['order_id'])
        assert main_order['action'] == 'buy'
        assert main_order['stop_loss_price'] == 48.50
        assert main_order['take_profit_price'] == 55.20
        
        # 验证止损单
        if 'stop_loss_order_id' in result:
            stop_order = ds.portfolio.get_order_by_id(result['stop_loss_order_id'])
            assert stop_order['action'] == 'sell'
            assert stop_order['order_type'] == 'stop'
            assert stop_order['price'] == 48.50
            assert stop_order['parent_order_id'] == result['order_id']
        
        # 验证止盈单
        if 'take_profit_order_id' in result:
            tp_order = ds.portfolio.get_order_by_id(result['take_profit_order_id'])
            assert tp_order['action'] == 'sell'
            assert tp_order['price'] == 55.20
            assert tp_order['parent_order_id'] == result['order_id']
```

- [ ] **Step 4: 运行集成测试**

```bash
cd quantsys-v2
pytest tests/integration/test_signal_to_order_flow.py -v
```

Expected: 测试通过

- [ ] **Step 5: Commit**

```bash
git add services/order_service.py repositories/portfolio_repository.py tests/integration/test_signal_to_order_flow.py
git commit -m "feat(services): add create_order_from_signal for order group creation

- Extend PortfolioRepository with create_order_with_risk_params()
- Add create_order_from_signal() to OrderService
- Support creating order groups (main + stop loss + take profit)
- Add integration tests for complete flow"
```

---

## Task 6: API 端点

**Files:**
- Create: `quantsys-v2/api/routes/signals.py`
- Create: `quantsys-v2/api/routes/monitoring.py`
- Modify: `quantsys-v2/api/server.py`

- [ ] **Step 1: 创建信号执行 API**

创建文件 `quantsys-v2/api/routes/signals.py`:

```python
"""
信号执行 API
"""
from flask import Blueprint, request, jsonify
import logging

logger = logging.getLogger(__name__)

bp = Blueprint('signals', __name__, url_prefix='/api/signals')


@bp.route('/execute', methods=['POST'])
def execute_signal():
    """
    执行策略信号，创建订单
    
    POST /api/signals/execute
    {
        "symbol": "600519.SH",
        "signal": {
            "action": "buy",
            "confidence": 0.85,
            "reason": "...",
            "risk_management": { ... }
        },
        "order_type": "limit"
    }
    """
    data = request.get_json()
    symbol = data.get('symbol')
    signal = data.get('signal')
    order_type = data.get('order_type', 'limit')
    
    if not symbol or not signal:
        return jsonify({'success': False, 'error': 'Missing symbol or signal'}), 400
    
    try:
        from services.order_service import create_order_from_signal
        from services.data_service import DataService
        
        ds = DataService()
        result = create_order_from_signal(ds, signal, symbol, order_type)
        
        return jsonify({
            'success': True,
            **result
        })
    
    except Exception as e:
        logger.error(f"Failed to execute signal: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500


@bp.route('/backtest-signal', methods=['POST'])
def backtest_signal():
    """
    回测单个信号（不创建真实订单）
    
    POST /api/signals/backtest-signal
    {
        "symbol": "600519.SH",
        "signal": { ... },
        "account_balance": {
            "total_assets": 1000000,
            "cash": 500000
        }
    }
    """
    data = request.get_json()
    symbol = data.get('symbol')
    signal = data.get('signal')
    account_balance = data.get('account_balance', {
        'total_assets': 1000000,
        'cash': 500000
    })
    
    try:
        from services.signal_processor import SignalProcessor
        from services.data_service import DataService
        
        ds = DataService()
        latest = ds.kline.get_latest_daily_kline(symbol)
        current_price = latest['close'] if latest else 0
        
        processor = SignalProcessor(ds)
        trade_params = processor.process_signal(
            signal, symbol, current_price, account_balance
        )
        
        # 计算风险指标
        position_value = trade_params['quantity'] * trade_params['price']
        risk_amount = abs(
            trade_params['quantity'] * 
            (trade_params['price'] - trade_params['stop_loss_price'])
        ) if trade_params['stop_loss_price'] else 0
        
        trade_params['position_value'] = round(position_value, 2)
        trade_params['position_percent'] = round(
            position_value / account_balance['total_assets'], 4
        )
        trade_params['risk_amount'] = round(risk_amount, 2)
        trade_params['risk_percent'] = round(
            risk_amount / account_balance['total_assets'], 4
        )
        
        return jsonify({
            'success': True,
            'trade_params': trade_params
        })
    
    except Exception as e:
        logger.error(f"Failed to backtest signal: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500
```

- [ ] **Step 2: 创建监控 API**

创建文件 `quantsys-v2/api/routes/monitoring.py`:

```python
"""
监控 API
"""
from flask import Blueprint, request, jsonify
from services.signal_monitoring import signal_monitor

bp = Blueprint('monitoring', __name__, url_prefix='/api/monitoring')


@bp.route('/signals/metrics', methods=['GET'])
def get_signal_metrics():
    """
    获取信号处理监控指标
    
    GET /api/monitoring/signals/metrics?strategy=VolatilityBreakoutStrategy
    """
    strategy_name = request.args.get('strategy')
    
    summary = signal_monitor.get_summary()
    metrics = signal_monitor.get_metrics(strategy_name)
    
    # 计算平均时间
    by_strategy = {}
    for key, m in metrics.items():
        by_strategy[key] = {
            **m,
            'avg_time': m['total_time'] / m['count'] if m['count'] > 0 else 0
        }
    
    return jsonify({
        'summary': summary,
        'by_strategy': by_strategy
    })


@bp.route('/signals/health', methods=['GET'])
def get_signal_health():
    """
    信号处理健康检查
    
    GET /api/monitoring/signals/health
    """
    summary = signal_monitor.get_summary()
    
    checks = {
        'success_rate': {
            'status': 'pass' if summary['success_rate'] >= 0.95 else 'fail',
            'value': summary['success_rate'],
            'threshold': 0.95
        },
        'avg_processing_time': {
            'status': 'pass' if summary['avg_processing_time'] <= 0.1 else 'fail',
            'value': summary['avg_processing_time'],
            'threshold': 0.1
        },
        'recent_failures': {
            'status': 'pass' if summary['failure_count'] <= 10 else 'fail',
            'value': summary['failure_count'],
            'threshold': 10
        }
    }
    
    # 判断整体状态
    failed_checks = sum(1 for c in checks.values() if c['status'] == 'fail')
    if failed_checks == 0:
        status = 'healthy'
    elif failed_checks <= 1:
        status = 'degraded'
    else:
        status = 'unhealthy'
    
    return jsonify({
        'status': status,
        'checks': checks
    })
```

- [ ] **Step 3: 注册 Blueprint**

修改 `quantsys-v2/api/server.py`，在注册其他 Blueprint 的地方添加：

```python
# 注册信号和监控路由
from api.routes import signals, monitoring
app.register_blueprint(signals.bp)
app.register_blueprint(monitoring.bp)
```

- [ ] **Step 4: 测试 API 端点**

启动服务器：

```bash
cd quantsys-v2
python api/server.py
```

测试执行信号：

```bash
curl -X POST http://127.0.0.1:5001/api/signals/backtest-signal \
  -H "Content-Type: application/json" \
  -d '{
    "symbol": "600519.SH",
    "signal": {
      "action": "buy",
      "confidence": 0.85,
      "reason": "Test"
    }
  }'
```

Expected: 返回 JSON 包含 trade_params

测试监控端点：

```bash
curl http://127.0.0.1:5001/api/monitoring/signals/health
```

Expected: 返回健康状态

- [ ] **Step 5: Commit**

```bash
git add api/routes/signals.py api/routes/monitoring.py api/server.py
git commit -m "feat(api): add signal execution and monitoring endpoints

- Add /api/signals/execute for creating orders from signals
- Add /api/signals/backtest-signal for signal simulation
- Add /api/monitoring/signals/metrics for performance metrics
- Add /api/monitoring/signals/health for health checks
- Register new blueprints in server.py"
```

---

## Task 7: 向后兼容性测试

**Files:**
- Create: `quantsys-v2/tests/test_backward_compatibility.py`

- [ ] **Step 1: 编写向后兼容性测试**

创建文件 `quantsys-v2/tests/test_backward_compatibility.py`:

```python
"""
测试向后兼容性

确保现有策略仍然可以正常工作。
"""
import pytest
from quantlib.engine.strategy_runner import StrategyRunner


class TestBackwardCompatibility:
    
    @pytest.fixture
    def klines(self):
        """生成测试 K 线数据"""
        return [
            {'trade_date': f'2024-01-{i:02d}', 'close': 50.0 + i * 0.5, 
             'high': 51.0 + i * 0.5, 'low': 49.0 + i * 0.5, 'volume': 1000000}
            for i in range(1, 31)
        ]
    
    def test_all_legacy_strategies_still_work(self, klines):
        """确保所有旧策略仍然可以运行"""
        runner = StrategyRunner()
        
        # 运行所有策略
        signals = runner.run(klines, symbol='600519.SH')
        
        # 所有信号都应该有基础字段
        for signal in signals:
            assert 'action' in signal
            assert 'confidence' in signal
            assert 'reason' in signal
            assert signal['action'] in ('buy', 'sell', 'hold')
            assert 0 <= signal['confidence'] <= 1
            
            # risk_management 是可选的
            if 'risk_management' in signal:
                self._validate_risk_management(signal['risk_management'])
    
    def _validate_risk_management(self, risk_mgmt):
        """验证风控信息格式"""
        if 'stop_loss' in risk_mgmt:
            assert 'type' in risk_mgmt['stop_loss']
            assert 'price' in risk_mgmt['stop_loss']
            assert 'params' in risk_mgmt['stop_loss']
        
        if 'take_profit' in risk_mgmt:
            assert 'type' in risk_mgmt['take_profit']
            assert 'price' in risk_mgmt['take_profit']
        
        if 'position_sizing' in risk_mgmt:
            assert 'method' in risk_mgmt['position_sizing']
            assert 'params' in risk_mgmt['position_sizing']
    
    def test_signal_processor_handles_legacy_signals(self, klines):
        """测试 SignalProcessor 处理旧格式信号"""
        from services.signal_processor import SignalProcessor
        from services.data_service import DataService
        
        # 模拟旧策略返回的信号
        legacy_signal = {
            'action': 'buy',
            'confidence': 0.75,
            'reason': 'Legacy strategy signal'
        }
        
        processor = SignalProcessor(DataService())
        result = processor.process_signal(
            legacy_signal,
            '600519.SH',
            52.30,
            {'total_assets': 1000000, 'cash': 500000}
        )
        
        # 应该成功处理并添加默认风控参数
        assert result['action'] == 'buy'
        assert result['quantity'] > 0
        assert result['stop_loss_price'] is not None
        assert len(result['warnings']) == 0  # 使用默认值不应该产生警告
```

- [ ] **Step 2: 运行向后兼容性测试**

```bash
cd quantsys-v2
pytest tests/test_backward_compatibility.py -v
```

Expected: 所有测试通过

- [ ] **Step 3: Commit**

```bash
git add tests/test_backward_compatibility.py
git commit -m "test: add backward compatibility tests

- Ensure all legacy strategies still work
- Verify SignalProcessor handles old signal format
- Validate risk management structure when present"
```

---

## 验收标准

完成所有任务后，验证以下标准：

- [ ] **数据库迁移成功**
  - 测试数据库包含新字段
  - 外键约束正常工作

- [ ] **单元测试全部通过**
  ```bash
  pytest tests/test_strategy_base_helpers.py -v
  pytest tests/test_signal_processor.py -v
  pytest tests/test_signal_monitoring.py -v
  pytest tests/test_backward_compatibility.py -v
  ```

- [ ] **集成测试通过**
  ```bash
  pytest tests/integration/test_signal_to_order_flow.py -v
  ```

- [ ] **API 端点可用**
  - `/api/signals/execute` 正常工作
  - `/api/signals/backtest-signal` 正常工作
  - `/api/monitoring/signals/metrics` 返回指标
  - `/api/monitoring/signals/health` 返回健康状态

- [ ] **向后兼容性验证**
  - 现有 19 个策略仍然正常工作
  - 旧格式信号被正确处理

- [ ] **代码质量**
  - 所有代码已提交到 git
  - Commit 消息清晰
  - 无 TODO 或 placeholder

---

## 下一步

完成 Phase 1 后，可以继续：

1. **Phase 2: 策略升级** - 升级 4 个关键策略（VolatilityBreakout, Turtle, Donchian, Momentum）
2. **Phase 3: TypeScript 集成** - 更新 TypeScript Agent 工具
3. **Phase 4: 文档和示例** - 编写迁移指南和示例代码

