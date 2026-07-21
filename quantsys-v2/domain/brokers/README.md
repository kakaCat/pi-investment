# Broker Abstraction Layer

券商接口统一抽象层，参考 FinceptTerminal 的设计模式。

## 概述

本模块提供了一个统一的券商接口抽象层，使得系统可以轻松集成多个数据源和交易券商，而无需修改业务逻辑代码。

## 核心组件

### 1. BaseBroker（抽象基类）

所有券商实现必须继承的抽象基类，定义了统一的接口契约。

```python
from brokers import BaseBroker, BrokerProfile, ApiResponse

class MyBroker(BaseBroker):
    def get_id(self) -> str:
        return "my_broker"
    
    def get_name(self) -> str:
        return "My Broker"
    
    def get_profile(self) -> BrokerProfile:
        return BrokerProfile(
            id="my_broker",
            display_name="My Broker",
            region="CN",
            currency="CNY",
            # ...
        )
    
    def get_quotes(self, symbols: List[str]) -> ApiResponse[List[BrokerQuote]]:
        # 实现获取行情逻辑
        pass
```

### 2. BrokerRegistry（注册表）

单例模式的券商注册表，负责管理所有券商实例。

```python
from brokers import BrokerRegistry

# 获取注册表实例
registry = BrokerRegistry.instance()

# 获取特定券商
broker = registry.get('akshare')

# 列举所有券商
all_brokers = registry.list_brokers()

# 获取所有数据源券商
data_brokers = registry.get_data_brokers()
```

### 3. Trading Types（统一类型系统）

定义了跨券商通用的数据结构。

```python
from brokers import (
    OrderSide,
    OrderType,
    UnifiedOrder,
    BrokerQuote,
    BrokerCandle,
)

# 创建订单
order = UnifiedOrder(
    symbol='600000',
    side=OrderSide.BUY,
    order_type=OrderType.LIMIT,
    quantity=100,
    price=1800.0
)
```

## 已实现的券商

### AkShare

免费开源的 A 股数据源，无需 API Key。

```python
from brokers import BrokerRegistry

registry = BrokerRegistry.instance()
akshare = registry.get('akshare')

# 获取实时行情
quotes = akshare.get_quotes(['600000', '000001'])
if quotes.success:
    for quote in quotes.data:
        print(f"{quote.symbol}: {quote.last_price}")

# 获取历史数据
history = akshare.get_history(
    symbol='600000',
    start_date='2024-01-01',
    end_date='2024-01-31',
    frequency='daily'
)

# 搜索股票
results = akshare.search_symbols('平安')
```

## 使用示例

### 基础用法

```python
from brokers import BrokerRegistry

# 1. 获取券商
registry = BrokerRegistry.instance()
broker = registry.get('akshare')

# 2. 获取行情
response = broker.get_quotes(['600000', '000001'])
if response.success:
    for quote in response.data:
        print(f"{quote.symbol}: ¥{quote.last_price} ({quote.change_pct:+.2f}%)")
else:
    print(f"Error: {response.error}")

# 3. 获取历史数据
history = broker.get_history(
    symbol='600000',
    start_date='2024-01-01',
    end_date='2024-12-31'
)
```

### 在 API 中使用

```python
from fastapi import APIRouter, HTTPException
from brokers import BrokerRegistry

router = APIRouter()

@router.get("/quotes/{broker_id}")
async def get_quotes(broker_id: str, symbols: str):
    """获取行情"""
    registry = BrokerRegistry.instance()
    broker = registry.get(broker_id)
    
    if not broker:
        raise HTTPException(status_code=404, detail="Broker not found")
    
    symbol_list = symbols.split(',')
    response = broker.get_quotes(symbol_list)
    
    if not response.success:
        raise HTTPException(status_code=500, detail=response.error)
    
    return {
        'broker': broker_id,
        'quotes': [q.to_dict() for q in response.data]
    }
```

### 在 CLI 中使用

```python
import click
from brokers import BrokerRegistry

@click.command()
@click.option('--broker', default='akshare', help='Broker ID')
@click.argument('symbols', nargs=-1)
def quote(broker, symbols):
    """获取股票行情"""
    registry = BrokerRegistry.instance()
    broker_instance = registry.get(broker)
    
    if not broker_instance:
        click.echo(f"Broker '{broker}' not found")
        return
    
    response = broker_instance.get_quotes(list(symbols))
    
    if response.success:
        for quote in response.data:
            click.echo(f"{quote.symbol}: {quote.last_price}")
    else:
        click.echo(f"Error: {response.error}")
```

## 添加新券商

### 步骤 1: 创建适配器

在 `brokers/adapters/` 下创建新文件：

```python
# brokers/adapters/my_broker.py
from ..base_broker import BaseBroker
from ..trading_types import BrokerProfile, ApiResponse, BrokerQuote

class MyBroker(BaseBroker):
    def get_id(self) -> str:
        return "my_broker"
    
    def get_name(self) -> str:
        return "My Broker"
    
    def get_profile(self) -> BrokerProfile:
        return BrokerProfile(
            id="my_broker",
            display_name="My Broker",
            region="CN",
            currency="CNY",
            supported_exchanges=["SSE", "SZSE"],
        )
    
    def get_quotes(self, symbols: List[str]) -> ApiResponse[List[BrokerQuote]]:
        # 实现获取行情的逻辑
        try:
            quotes = []
            for symbol in symbols:
                # 调用第三方 API
                data = self._fetch_quote(symbol)
                quote = BrokerQuote(
                    symbol=symbol,
                    last_price=data['price'],
                    # ...
                )
                quotes.append(quote)
            return ApiResponse.ok(quotes)
        except Exception as e:
            return ApiResponse.fail(str(e))
    
    def get_history(self, symbol, start_date, end_date, frequency='daily'):
        # 实现获取历史数据的逻辑
        pass
```

### 步骤 2: 注册券商

在 `brokers/broker_registry.py` 的 `_register_all()` 方法中添加：

```python
def _register_all(self):
    # ... 现有代码 ...
    
    try:
        from .adapters.my_broker import MyBroker
        self.register(MyBroker())
        logger.info("Registered: MyBroker")
    except ImportError as e:
        logger.warning(f"Failed to register MyBroker: {e}")
```

### 步骤 3: 更新 __init__.py

在 `brokers/adapters/__init__.py` 中导出：

```python
from .my_broker import MyBroker

__all__ = [
    'AkshareBroker',
    'MyBroker',
]
```

### 步骤 4: 编写测试

在 `tests/test_brokers.py` 中添加测试：

```python
class TestMyBroker:
    @pytest.fixture
    def broker(self):
        return MyBroker()
    
    def test_get_quotes(self, broker):
        response = broker.get_quotes(['600000'])
        assert response.success is True
```

## 设计原则

### 1. 接口隔离

- **必需方法**：核心功能（行情、历史数据）= 抽象方法，强制实现
- **可选方法**：高级功能（交易、保证金）= 带默认实现，返回 "Not supported"

### 2. 统一类型

- 所有跨券商代码使用 `UnifiedOrder`、`BrokerQuote` 等统一类型
- 券商适配器负责转换为各自的 wire format
- UI 层完全不感知券商差异

### 3. 关注点分离

- **UI 层**：只知道 `BaseBroker` 接口
- **业务层**：使用统一类型
- **适配层**：各券商独立实现，互不干扰

### 4. 错误处理

- 使用 `ApiResponse[T]` 统一返回类型
- 成功：`ApiResponse.ok(data)`
- 失败：`ApiResponse.fail(error_message)`

## 架构图

```
┌─────────────────────────────────────────┐
│  API / CLI / Services                   │
│  (使用 BrokerRegistry 获取券商)          │
├─────────────────────────────────────────┤
│  BrokerRegistry (单例)                  │
│  - get(broker_id)                       │
│  - list_brokers()                       │
├─────────────────────────────────────────┤
│  BaseBroker (抽象基类)                  │
│  - get_quotes()                         │
│  - get_history()                        │
│  - place_order() [可选]                │
├─────────────────────────────────────────┤
│  Broker Adapters (具体实现)             │
│  ├─ AkshareBroker                       │
│  ├─ EastmoneyBroker (待实现)            │
│  └─ TushareBroker (待实现)              │
└─────────────────────────────────────────┘
```

## 测试

运行测试：

```bash
# 运行所有测试
pytest tests/test_brokers.py -v

# 运行特定测试
pytest tests/test_brokers.py::TestBrokerRegistry -v

# 跳过需要网络的测试
pytest tests/test_brokers.py -v -m "not skip"
```

## 未来扩展

### 计划支持的券商

1. **东方财富** - Choice 数据接口
2. **Tushare Pro** - 专业金融数据
3. **华泰证券** - 真实交易接口
4. **富途证券** - 港美股交易

### 计划功能

1. **异步支持** - 添加 async/await 版本的接口
2. **缓存层** - 集成 Redis 缓存行情数据
3. **WebSocket** - 实时行情推送
4. **回测模式** - 模拟交易环境

## 参考

- [FinceptTerminal Architecture](https://github.com/Fincept-Corporation/FinceptTerminal/blob/main/docs/ARCHITECTURE.md)
- [FinceptTerminal BrokerInterface.h](https://github.com/Fincept-Corporation/FinceptTerminal/blob/main/fincept-qt/src/trading/BrokerInterface.h)
- [pi-investment 对比分析文档](../../docs/FinceptTerminal_Broker_Abstraction_Analysis.md)
