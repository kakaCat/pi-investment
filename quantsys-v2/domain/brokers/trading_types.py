"""
Trading Types - Unified type system for broker abstraction

Defines common data structures used across all broker implementations.
Inspired by FinceptTerminal's TradingTypes.h
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, List, Dict, Any, Generic, TypeVar
from datetime import datetime


# ============================================================================
# Enums
# ============================================================================

class OrderSide(Enum):
    """订单方向"""
    BUY = "BUY"
    SELL = "SELL"


class OrderType(Enum):
    """订单类型"""
    MARKET = "market"          # 市价单
    LIMIT = "limit"            # 限价单
    STOP_LOSS = "stop_loss"    # 止损单
    STOP_LIMIT = "stop_limit"  # 止损限价单


class ProductType(Enum):
    """产品类型"""
    INTRADAY = "intraday"      # 日内交易
    DELIVERY = "delivery"      # 交割
    MARGIN = "margin"          # 融资融券
    COVER_ORDER = "cover"      # 备兑订单
    BRACKET_ORDER = "bracket"  # 括号订单


class CredentialField(Enum):
    """凭证字段类型"""
    API_KEY = "api_key"
    API_SECRET = "api_secret"
    AUTH_CODE = "auth_code"
    ACCESS_TOKEN = "access_token"
    USER_ID = "user_id"
    PASSWORD = "password"


# ============================================================================
# Response Types
# ============================================================================

T = TypeVar('T')


@dataclass
class ApiResponse(Generic[T]):
    """统一的 API 响应格式"""
    success: bool
    data: Optional[T] = None
    error: Optional[str] = None
    timestamp: Optional[datetime] = None

    @classmethod
    def ok(cls, data: T) -> 'ApiResponse[T]':
        """创建成功响应"""
        return cls(success=True, data=data, timestamp=datetime.now())

    @classmethod
    def fail(cls, error: str) -> 'ApiResponse[T]':
        """创建失败响应"""
        return cls(success=False, error=error, timestamp=datetime.now())


# ============================================================================
# Broker Configuration
# ============================================================================

@dataclass
class CredentialFieldDef:
    """凭证字段定义"""
    field: CredentialField
    label: str                    # 显示标签，如 "API Key"
    placeholder: str              # 输入提示
    secret: bool = False          # 是否为密码字段
    required: bool = True         # 是否必填


@dataclass
class ProductTypeDef:
    """产品类型定义"""
    label: str                    # 显示标签，如 "日内交易 (MIS)"
    value: ProductType


@dataclass
class BrokerProfile:
    """券商配置元数据

    UI 层根据此配置动态生成表单和选项
    """
    id: str                                      # 券商 ID，如 "akshare"
    display_name: str                            # 显示名称，如 "AkShare"
    region: str                                  # 地区：CN/HK/US
    currency: str                                # 货币：CNY/HKD/USD

    # 凭证配置
    credential_fields: List[CredentialFieldDef] = field(default_factory=list)

    # 交易能力
    supported_exchanges: List[str] = field(default_factory=list)
    product_types: List[ProductTypeDef] = field(default_factory=list)
    supports_intraday: bool = True
    supports_margin: bool = False
    supports_options: bool = False

    # 模拟交易
    has_native_paper: bool = False
    default_paper_balance: float = 1000000.0

    # 默认配置
    default_watchlist: List[str] = field(default_factory=list)
    default_symbol: str = ""
    default_exchange: str = ""

    # 费率信息（仅供显示）
    brokerage_info: str = ""


# ============================================================================
# Trading Data Structures
# ============================================================================

@dataclass
class UnifiedOrder:
    """统一订单结构

    所有跨券商代码使用此结构，券商适配器负责转换为各自的格式
    """
    symbol: str                          # 股票代码
    side: OrderSide                      # 买卖方向
    order_type: OrderType                # 订单类型
    quantity: float                      # 数量
    exchange: str = "SSE"                # 交易所
    product_type: ProductType = ProductType.DELIVERY
    price: Optional[float] = None        # 限价单价格
    stop_price: Optional[float] = None   # 止损价格

    # 可选字段
    order_id: Optional[str] = None
    client_order_id: Optional[str] = None
    time_in_force: str = "DAY"           # DAY/GTC/IOC/FOK

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'symbol': self.symbol,
            'side': self.side.value,
            'order_type': self.order_type.value,
            'quantity': self.quantity,
            'exchange': self.exchange,
            'product_type': self.product_type.value,
            'price': self.price,
            'stop_price': self.stop_price,
            'order_id': self.order_id,
            'time_in_force': self.time_in_force,
        }


@dataclass
class BrokerQuote:
    """行情报价"""
    symbol: str
    last_price: float
    open_price: Optional[float] = None
    high_price: Optional[float] = None
    low_price: Optional[float] = None
    close_price: Optional[float] = None
    volume: Optional[float] = None
    turnover: Optional[float] = None
    change: Optional[float] = None
    change_pct: Optional[float] = None
    bid_price: Optional[float] = None
    ask_price: Optional[float] = None
    timestamp: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'symbol': self.symbol,
            'last_price': self.last_price,
            'open_price': self.open_price,
            'high_price': self.high_price,
            'low_price': self.low_price,
            'close_price': self.close_price,
            'volume': self.volume,
            'turnover': self.turnover,
            'change': self.change,
            'change_pct': self.change_pct,
            'bid_price': self.bid_price,
            'ask_price': self.ask_price,
            'timestamp': self.timestamp.isoformat() if self.timestamp else None,
        }


@dataclass
class BrokerCandle:
    """K线数据"""
    symbol: str
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float
    turnover: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'symbol': self.symbol,
            'timestamp': self.timestamp.isoformat(),
            'open': self.open,
            'high': self.high,
            'low': self.low,
            'close': self.close,
            'volume': self.volume,
            'turnover': self.turnover,
        }


@dataclass
class BrokerPosition:
    """持仓信息"""
    symbol: str
    quantity: float                      # 持仓数量
    available_quantity: float            # 可用数量
    avg_price: float                     # 平均成本
    current_price: float                 # 当前价格
    unrealized_pnl: float                # 浮动盈亏
    realized_pnl: float = 0.0            # 已实现盈亏
    side: str = "long"                   # long/short
    exchange: str = ""
    product_type: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'symbol': self.symbol,
            'quantity': self.quantity,
            'available_quantity': self.available_quantity,
            'avg_price': self.avg_price,
            'current_price': self.current_price,
            'unrealized_pnl': self.unrealized_pnl,
            'realized_pnl': self.realized_pnl,
            'side': self.side,
            'exchange': self.exchange,
            'product_type': self.product_type,
        }


@dataclass
class BrokerHolding:
    """持股信息（长期持仓）"""
    symbol: str
    quantity: float
    avg_price: float
    current_price: float
    market_value: float
    pnl: float
    pnl_pct: float
    exchange: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'symbol': self.symbol,
            'quantity': self.quantity,
            'avg_price': self.avg_price,
            'current_price': self.current_price,
            'market_value': self.market_value,
            'pnl': self.pnl,
            'pnl_pct': self.pnl_pct,
            'exchange': self.exchange,
        }


@dataclass
class BrokerFunds:
    """资金信息"""
    available_cash: float                # 可用资金
    total_assets: float                  # 总资产
    market_value: float                  # 持仓市值
    frozen_cash: float = 0.0             # 冻结资金
    margin_used: float = 0.0             # 已用保证金
    margin_available: float = 0.0        # 可用保证金

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'available_cash': self.available_cash,
            'total_assets': self.total_assets,
            'market_value': self.market_value,
            'frozen_cash': self.frozen_cash,
            'margin_used': self.margin_used,
            'margin_available': self.margin_available,
        }


@dataclass
class OrderPlaceResponse:
    """下单响应"""
    success: bool
    order_id: Optional[str] = None
    error: Optional[str] = None

    @classmethod
    def ok(cls, order_id: str) -> 'OrderPlaceResponse':
        """创建成功响应"""
        return cls(success=True, order_id=order_id)

    @classmethod
    def fail(cls, error: str) -> 'OrderPlaceResponse':
        """创建失败响应"""
        return cls(success=False, error=error)


@dataclass
class BrokerCredentials:
    """券商凭证"""
    broker_id: str
    api_key: Optional[str] = None
    api_secret: Optional[str] = None
    access_token: Optional[str] = None
    refresh_token: Optional[str] = None
    user_id: Optional[str] = None
    additional_data: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'broker_id': self.broker_id,
            'api_key': self.api_key,
            'api_secret': self.api_secret,
            'access_token': self.access_token,
            'refresh_token': self.refresh_token,
            'user_id': self.user_id,
            'additional_data': self.additional_data,
        }
