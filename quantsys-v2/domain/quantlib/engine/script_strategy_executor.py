"""
ScriptStrategy 执行引擎

事件驱动的策略执行引擎，支持：
- 逐 bar 处理（on_bar 回调）
- 策略初始化（on_init 回调）
- 状态管理（ctx.state）
- 交易操作（ctx.buy/sell/close_position）
- 权益曲线记录
"""

from dataclasses import dataclass
from typing import Dict, List, Any, Optional
import pandas as pd

from .code_validator import CodeValidator
from .param_parser import ParamParser


@dataclass
class Bar:
    """K 线数据对象"""
    date: str
    open: float
    high: float
    low: float
    close: float
    volume: float


@dataclass
class Trade:
    """交易记录"""
    date: str
    action: str  # 'buy' or 'sell'
    price: float
    size: float
    reason: str


class StrategyContext:
    """
    策略上下文对象（ctx）

    提供给用户策略代码的 API 接口
    """

    def __init__(self, params: Dict, initial_cash: float):
        """
        初始化策略上下文

        Args:
            params: 策略参数
            initial_cash: 初始资金
        """
        self.params = params
        self.state = {}  # 用户自定义状态
        self.cash = initial_cash
        self.position = 0.0  # 当前持仓数量

        # 内部状态
        self._trades: List[Trade] = []
        self._logs: List[str] = []
        self._current_bar: Optional[Bar] = None

    @property
    def equity(self) -> float:
        """
        当前权益 = 现金 + 持仓市值

        Returns:
            当前权益
        """
        if self._current_bar is None:
            return self.cash
        return self.cash + self.position * self._current_bar.close

    def buy(self, size: float, price: Optional[float] = None, reason: str = "") -> None:
        """
        买入操作

        Args:
            size: 买入数量
            price: 买入价格（None 则使用当前 bar 的收盘价）
            reason: 买入原因（用于日志）

        Raises:
            ValueError: 资金不足或参数无效
        """
        if self._current_bar is None:
            raise ValueError("buy() 只能在 on_bar() 中调用")

        if size <= 0:
            raise ValueError(f"买入数量必须大于 0，当前值: {size}")

        # 使用当前 bar 的收盘价
        actual_price = price if price is not None else self._current_bar.close

        # 检查资金是否足够
        cost = size * actual_price
        if cost > self.cash:
            raise ValueError(
                f"资金不足: 需要 {cost:.2f}，可用 {self.cash:.2f}"
            )

        # 执行买入
        self.cash -= cost
        self.position += size

        # 记录交易
        trade = Trade(
            date=self._current_bar.date,
            action='buy',
            price=actual_price,
            size=size,
            reason=reason
        )
        self._trades.append(trade)

        # 记录日志
        self.log(f"买入: {size:.2f} @ {actual_price:.2f} | {reason}")

    def sell(self, size: float, price: Optional[float] = None, reason: str = "") -> None:
        """
        卖出操作

        Args:
            size: 卖出数量
            price: 卖出价格（None 则使用当前 bar 的收盘价）
            reason: 卖出原因（用于日志）

        Raises:
            ValueError: 持仓不足或参数无效
        """
        if self._current_bar is None:
            raise ValueError("sell() 只能在 on_bar() 中调用")

        if size <= 0:
            raise ValueError(f"卖出数量必须大于 0，当前值: {size}")

        # 检查持仓是否足够
        if size > self.position:
            raise ValueError(
                f"持仓不足: 需要 {size:.2f}，可用 {self.position:.2f}"
            )

        # 使用当前 bar 的收盘价
        actual_price = price if price is not None else self._current_bar.close

        # 执行卖出
        self.cash += size * actual_price
        self.position -= size

        # 记录交易
        trade = Trade(
            date=self._current_bar.date,
            action='sell',
            price=actual_price,
            size=size,
            reason=reason
        )
        self._trades.append(trade)

        # 记录日志
        self.log(f"卖出: {size:.2f} @ {actual_price:.2f} | {reason}")

    def close_position(self, reason: str = "") -> None:
        """
        平仓（卖出所有持仓）

        Args:
            reason: 平仓原因（用于日志）
        """
        if self.position > 0:
            self.sell(size=self.position, reason=reason or "平仓")

    def log(self, message: str) -> None:
        """
        记录日志

        Args:
            message: 日志消息
        """
        if self._current_bar:
            log_entry = f"[{self._current_bar.date}] {message}"
        else:
            log_entry = f"[INIT] {message}"
        self._logs.append(log_entry)

    def _set_current_bar(self, bar: Bar) -> None:
        """
        设置当前 bar（内部方法）

        Args:
            bar: 当前 K 线数据
        """
        self._current_bar = bar


class ScriptStrategyExecutor:
    """ScriptStrategy 执行引擎"""

    def __init__(self):
        self.code_validator = CodeValidator()
        self.param_parser = ParamParser()

    def execute(
        self,
        code: str,
        klines: List[Dict],
        params: Optional[Dict] = None,
        initial_cash: float = 1000000.0
    ) -> Dict[str, Any]:
        """
        执行 ScriptStrategy 代码

        Args:
            code: 策略代码字符串
            klines: K 线数据列表，每个元素包含 date, open, high, low, close, volume
            params: 用户传入的参数（覆盖代码中的默认值）
            initial_cash: 初始资金

        Returns:
            执行结果字典，包含：
            - trades: 交易记录列表
            - equity_curve: 权益曲线 [{date, equity, cash, position}]
            - final_cash: 最终现金
            - final_position: 最终持仓
            - final_equity: 最终权益
            - logs: 日志列表
            - state: 最终状态
            - risk_config: 风控配置

        Raises:
            ValueError: 代码验证失败或执行错误
        """
        # 1. 验证代码安全性
        self.code_validator.validate(code, code_type='script')

        # 2. 解析参数和配置
        parsed_params = self.param_parser.parse_params(code)
        risk_config = self.param_parser.parse_strategy_config(code)

        # 3. 合并参数（用户传入覆盖默认值）
        final_params = {}
        for param_def in parsed_params:
            final_params[param_def['name']] = param_def['default']

        if params:
            final_params.update(params)

        # 4. 创建策略上下文
        ctx = StrategyContext(params=final_params, initial_cash=initial_cash)

        # 5. 创建沙箱环境并执行代码
        namespace = self._create_sandbox_namespace()

        try:
            exec(code, namespace)
        except Exception as e:
            raise ValueError(f"策略代码执行失败: {str(e)}")

        # 6. 提取 on_init 和 on_bar 函数
        on_init = namespace.get('on_init')
        on_bar = namespace.get('on_bar')

        if on_init is None:
            raise ValueError("未找到 on_init 函数")
        if on_bar is None:
            raise ValueError("未找到 on_bar 函数")

        # 7. 执行 on_init
        try:
            on_init(ctx)
        except Exception as e:
            raise ValueError(f"on_init 执行失败: {str(e)}")

        # 8. 转换 K 线数据为 Bar 对象
        bars = self._convert_klines_to_bars(klines)

        # 9. 逐 bar 执行 on_bar
        equity_curve = []

        for bar in bars:
            # 设置当前 bar
            ctx._set_current_bar(bar)

            # 执行 on_bar
            try:
                on_bar(ctx, bar)
            except Exception as e:
                raise ValueError(
                    f"on_bar 执行失败 (日期: {bar.date}): {str(e)}"
                )

            # 记录权益曲线
            equity_curve.append({
                'date': bar.date,
                'equity': ctx.equity,
                'cash': ctx.cash,
                'position': ctx.position,
                'price': bar.close
            })

        # 10. 返回结果
        return {
            'trades': [
                {
                    'date': t.date,
                    'action': t.action,
                    'price': t.price,
                    'size': t.size,
                    'reason': t.reason
                }
                for t in ctx._trades
            ],
            'equity_curve': equity_curve,
            'final_cash': ctx.cash,
            'final_position': ctx.position,
            'final_equity': ctx.equity,
            'logs': ctx._logs,
            'state': ctx.state,
            'risk_config': risk_config
        }

    def _create_sandbox_namespace(self) -> Dict[str, Any]:
        """
        创建沙箱执行环境

        Returns:
            受限的命名空间字典
        """
        # 只允许安全的内置函数
        safe_builtins = {
            'len': len,
            'range': range,
            'enumerate': enumerate,
            'zip': zip,
            'sum': sum,
            'max': max,
            'min': min,
            'abs': abs,
            'round': round,
            'int': int,
            'float': float,
            'str': str,
            'bool': bool,
            'list': list,
            'dict': dict,
            'tuple': tuple,
            'set': set,
            'sorted': sorted,
            'reversed': reversed,
            'any': any,
            'all': all,
            'print': print,  # 允许 print 用于调试
            # 对象属性访问函数（可能在用户代码中需要）
            'getattr': getattr,
            'setattr': setattr,
            'hasattr': hasattr,
        }

        return {
            '__builtins__': safe_builtins,
            # 不提供 pandas/numpy，ScriptStrategy 不需要
        }

    def _convert_klines_to_bars(self, klines: List[Dict]) -> List[Bar]:
        """
        转换 K 线数据为 Bar 对象列表

        Args:
            klines: K 线数据列表

        Returns:
            Bar 对象列表

        Raises:
            ValueError: K 线数据格式错误
        """
        bars = []

        for i, kline in enumerate(klines):
            try:
                bar = Bar(
                    date=str(kline['date']),
                    open=float(kline['open']),
                    high=float(kline['high']),
                    low=float(kline['low']),
                    close=float(kline['close']),
                    volume=float(kline['volume'])
                )
                bars.append(bar)
            except (KeyError, ValueError, TypeError) as e:
                raise ValueError(
                    f"K 线数据格式错误 (索引 {i}): {str(e)}\n"
                    f"期望字段: date, open, high, low, close, volume"
                )

        return bars
