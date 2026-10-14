"""账户交易服务 —— 手工/代管交易的单事务执行

事务流: 校验 → 委托单 → 成交+费用 → 资金流水(add_trade自动) → 持仓 → 账户 → 快照
"""
import structlog
from collections.abc import Iterable
from datetime import date, datetime, timedelta
from typing import Any, Dict, Optional

from domain.ports import ISimulationRepository
from domain.trading.services.market_session_policy import (
    AFTERNOON_START,
    CONTINUOUS_END,
    CONTINUOUS_START,
    MORNING_END,
    ORDER_CUTOFF_SECONDS,
    MarketSessionPolicy,
)

logger = structlog.get_logger(__name__)

# 2026-10-04（REQ-261004154902-a7cd t4 / FR-7）：挂单撮合的失败与超期必须有出口。
# 该出口自身绝不抛异常（见 application/observability/failure_sink.py）。
from application.observability import SEVERITY_HIGH, report_failure  # noqa: E402


# TradingError 已上移至 domain/trading/exceptions.py（2026-09-10，分层倒置修正）；
# 此处保留别名，存量 import（tests/adapters/simulation_async 等）零改动兼容。
from domain.trading.exceptions import TradingError  # noqa: F401


# ===========================================================================
# FR-10 账本自洽：卖前超卖硬校验（REQ-261004154902-a7cd · t-900179）
# ===========================================================================
# 背景（已取证，2026-10-04）：`v13_simulation` 有 4 只标的**累计卖出 > 累计买入**
# （300045 买1000/卖2000、300561 买700/卖1400、300765 买300/卖600、300469 买200/卖400），
# 合计凭空多出 ≈¥49,425 卖出收入 → 账户显示的 +32.99% 含虚增。
# 成因是**双数据源**：`quant.simulation_positions`（持仓表）与
# `quant.simulation_trades`（流水净额）并存且互相矛盾。
#
# 本卡只做「**不再产生新的虚增**」：真源 = 流水净额（`ΣBUY(shares) - ΣSELL(shares)`，
# 与 `SimulationTrader._rebuild_portfolio_from_trades` 同一口径），卖出前硬校验它。
# 历史虚增的处置（标记为脏并排除统计）是单独一张卡，本模块不碰历史数据、只读不写。
OVERSELL_CHECK_SOURCE = 'account_trading.oversell_check'
#: 受控 reason（design.md §2.1 的 reason 枚举；上层把它映射成 failed）
REASON_OVERSELL_BLOCKED = 'oversell_blocked'


def net_traded_shares(trades, symbol: str) -> int:
    """流水净额口径：``ΣBUY(shares) - ΣSELL(shares)``（唯一真源 = simulation_trades）。

    与 `_rebuild_portfolio_from_trades` 的 SQL 逐条对齐：
    - 只统计该 ``symbol`` 的行；action 大小写不敏感（存量脏数据两套写法并存）；
    - action 既非 BUY 也非 SELL 的行按 0 计（等同 SQL 的 ``ELSE 0``）。

    **类型不对必须抛**（shares/symbol/action 不是可解析的值）：绝不能把"读不懂的行"
    当成 0 —— 那会把一笔正常卖出误判成超卖（误杀）。抛出的异常由
    :func:`read_net_traded_shares` 收敛成"取数失败"，再到 :func:`check_sellable` 里响亮放行。
    """
    net = 0
    for row in trades:
        sym = getattr(row, 'symbol', None)
        if not isinstance(sym, str):
            raise TypeError(f'simulation_trades.symbol 类型不对: {sym!r}')
        if sym != symbol:
            continue
        action = getattr(row, 'action', None)
        if not isinstance(action, str):
            raise TypeError(f'simulation_trades.action 类型不对: {action!r}')
        action = action.strip().upper()
        if action not in ('BUY', 'SELL'):
            continue
        raw = getattr(row, 'shares', None)
        if isinstance(raw, bool) or raw is None:
            raise TypeError(f'simulation_trades.shares 类型不对: {raw!r}')
        try:
            shares = int(raw)
        except (TypeError, ValueError):
            raise TypeError(f'simulation_trades.shares 无法解析为整数: {raw!r}')
        net += shares if action == 'BUY' else -shares
    return net


def read_net_traded_shares(repo, account_name: str, symbol: str) -> Optional[int]:
    """从流水读净持仓。

    Returns:
        ``int`` = 可信的净持仓（流水口径，可为负 = 已超卖）；
        ``None`` = **取数失败 / 不可判定**（抛异常、返回 None、不是流水序列、行类型不对）。
        调用方对 ``None`` 的唯一合法处置见 :func:`check_sellable`（响亮放行）。
    """
    try:
        trades = repo.get_trades_by_account(account_name)
    except Exception as exc:  # noqa: BLE001 - 取数失败不许击穿卖出链路，但必须响亮
        logger.error(
            'oversell_check_trades_unavailable',
            account=account_name, symbol=symbol, error=str(exc)[:200],
        )
        return None

    if trades is None or isinstance(trades, (str, bytes, dict, bool, int, float)) \
            or not isinstance(trades, Iterable):
        logger.error(
            'oversell_check_trades_wrong_type',
            account=account_name, symbol=symbol, got=type(trades).__name__,
        )
        return None

    try:
        return net_traded_shares(trades, symbol)
    except (TypeError, ValueError) as exc:
        logger.error(
            'oversell_check_trades_unparsable',
            account=account_name, symbol=symbol, error=str(exc)[:200],
        )
        return None


def check_sellable(
    repo, account_name: str, symbol: str, shares: int, *, context: Optional[Dict[str, Any]] = None
) -> None:
    """卖前硬校验：``ΣBUY(shares) - ΣSELL(shares) >= 本次卖出量``，否则拒绝。

    **唯一实现**——`AccountTradingService.assert_sellable` 与
    `SimulationTrader._assert_sellable` 都走这里（两套口径正是本次虚增现金的成因）。
    只读：只发 SELECT（经 ``repo.get_trades_by_account``），不改任何写路径语义。

    三种结果，**没有第四种**（本卡不加新的静默分支）：

    1. 净持仓足够 → 正常返回（放行）；
    2. 净持仓不足 → ``logger.error`` + :func:`report_failure` + 抛
       ``TradingError(422)``（拒绝下单，details 带 ``reason='oversell_blocked'``）；
    3. **取数失败**（异常 / 返回 None / 不是流水序列 / 行类型不对）→ ``logger.error``
       + :func:`report_failure` 外发一次，然后**放行**。

    第 3 条为什么放行：判定不了 ≠ 超卖。静默拒绝会把正常卖出**全部误杀**（比虚增更危险——
    账户从此卖不出去），静默放行则等于这条护栏根本不存在。所以只做"**响亮地放行**"：
    日志 + 外发到位，让"这笔没被护栏覆盖"本身成为一条可见事实。
    """
    ctx: Dict[str, Any] = {
        'account': account_name,
        'symbol': symbol,
        'requested_shares': int(shares),
        **(context or {}),
    }
    net = read_net_traded_shares(repo, account_name, symbol)

    if net is None:
        # 取数失败：放行但留痕（source/reason 与本卡的拦截口径相同，靠 context 区分）
        report_failure(
            OVERSELL_CHECK_SOURCE,
            REASON_OVERSELL_BLOCKED,
            f'卖前超卖校验取数失败：{account_name} {symbol} 本次卖出 {shares} 股，'
            f'无法判定净持仓 → 放行（不误杀正常卖出），但本笔未被护栏覆盖',
            severity=SEVERITY_HIGH,
            context={**ctx, 'decision': 'passed_through_unchecked'},
        )
        return

    if net < int(shares):
        message = (
            f'超卖拦截：账户净持仓 {net} 股，本次卖出 {shares} 股'
            f'（流水口径 ΣBUY-ΣSELL，真源 = simulation_trades）'
        )
        logger.error('oversell_blocked', net_shares=net, **ctx)
        report_failure(
            OVERSELL_CHECK_SOURCE,
            REASON_OVERSELL_BLOCKED,
            message,
            severity=SEVERITY_HIGH,
            context={**ctx, 'net_shares': net, 'decision': 'rejected'},
        )
        raise TradingError(
            message, 422,
            details={
                'reason': REASON_OVERSELL_BLOCKED,
                'symbol': symbol,
                'net_shares': net,
                'requested_shares': int(shares),
            },
        )


class AccountTradingService:
    COMMISSION_RATE = 0.00025      # 佣金万2.5
    COMMISSION_MIN = 5.0           # 最低5元
    STAMP_DUTY_RATE = 0.0005       # 印花税(卖出)
    TRANSFER_FEE_RATE = 0.00001    # 过户费
    MAX_SINGLE_POSITION_RATIO = 0.30
    MAX_TOTAL_POSITION_RATIO = 0.80
    MAX_DAILY_BUY_COUNT = 5              # 单日买入笔数上限
    MAX_DAILY_BUY_AMOUNT_RATIO = 0.50    # 单日买入金额占总资产上限
    # 交易时段判定：一律 `MarketSessionPolicy`（RFC 016 §8.1）。
    # 原 TRADING_SESSIONS 常量已删除——收敛后它零引用，留着只会成为与真判据相矛盾的"第二个真相"。

    def __init__(self, repo: Optional[ISimulationRepository] = None, calendar=None,
                 now_fn=None):
        # 2026-10-02（REQ-261001145152-3982 审查）：**repo 改为懒解析**（见下面的 property）。
        # 本文件早已记录过同类事故（daily_orchestrator._match_pending_orders 的注释：
        # 「AccountTradingService() 无参构造时 repo=None，… 必炸 NoneType ——
        #   该路径只在交易日 9:31 真实触发才暴露；教训：实例化依赖必须显式注入」），
        # 但当时只在**那一个调用点**补了注入。实测仍有空构造的路径：
        # tests/test_trade_cash_race.py 直接 `AccountTradingService()` → 并发买入全部失败
        # （`'NoneType' object has no attribute 'get_account'`）。
        # 按仓内 DI 口径（取服务走 ServiceFactory）统一懒解析，保护**所有**调用点。
        self._repo = repo
        if calendar is None:
            from application.services.trading_calendar_service import TradingCalendarService
            calendar = TradingCalendarService()
        self.calendar = calendar
        # 时间源可注入（测试用固定时间）；默认真实时钟
        self.now_fn = now_fn or datetime.now

    @property
    def repo(self):
        """持仓/账户仓储（未注入则按端口懒解析）。见 `__init__` 里的说明。"""
        if self._repo is None:
            from domain.ports import ISimulationRepository
            from infrastructure.services.service_factory import ServiceFactory

            self._repo = ServiceFactory.resolve(ISimulationRepository)
        return self._repo

    @repo.setter
    def repo(self, value):
        """允许**显式注入**（`svc.repo = repo`）—— 同 StrategyCodeService：注入优先，未注入才懒解析。"""
        self._repo = value

    def _get_price(self, symbol: str) -> float:
        from application.services.realtime_quote_service import RealtimeQuoteService
        quote = RealtimeQuoteService().get_realtime_quote(symbol)
        if not quote or not quote.price or quote.price <= 0:
            raise TradingError(f'无法获取 {symbol} 实时价格', 502)
        return float(quote.price)

    @staticmethod
    def _as_int(value, field: str):
        """入参规整为 int；类型非法抛 TradingError(400)（2026-09-11，w-8f2c4cc5）"""
        if value is None:
            return None
        if isinstance(value, bool):
            raise TradingError(f'{field} 类型非法（bool），需为整数', 400)
        if isinstance(value, int):
            return value
        if isinstance(value, float):
            if value != int(value):
                raise TradingError(f'{field} 必须为整数，收到 {value}', 400)
            return int(value)
        if isinstance(value, str):
            try:
                return int(float(value.strip()))
            except ValueError:
                raise TradingError(f'{field} 无法解析为整数: {value!r}', 400)
        raise TradingError(
            f'{field} 类型非法（{type(value).__name__}），需为整数', 400)

    @staticmethod
    def _as_float(value, field: str):
        """入参规整为 float；类型非法抛 TradingError(400)（2026-09-11，w-8f2c4cc5）"""
        if value is None:
            return None
        if isinstance(value, bool):
            raise TradingError(f'{field} 类型非法（bool），需为数值', 400)
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str):
            try:
                return float(value.strip())
            except ValueError:
                raise TradingError(f'{field} 无法解析为数值: {value!r}', 400)
        raise TradingError(
            f'{field} 类型非法（{type(value).__name__}），需为数值', 400)

    def _check_trading_window(self, now: datetime) -> None:
        """A股下单闸门：交易日 + 连续竞价时段 + **未进入收盘截止窗口**。

        时段判定与截止规则**唯一**在 `MarketSessionPolicy`（RFC 016 §8.1；
        2026-09-12 裁定 B）。相比旧的精确时刻比较，每段末尾 `ORDER_CUTOFF_SECONDS`
        秒内不再接受新委托（有意收紧，防尾盘误下单）。
        三种拒绝原因分别抛 TradingError(422)，供 agent 记录后等待下一时段。
        """
        day_str = now.date().isoformat()
        if not self.calendar.is_trading_day(day_str):
            raise TradingError(f'非交易日（{day_str}），A股不开市，委托拒绝', 422)
        t = now.time()
        if not MarketSessionPolicy.is_market_open(
                MarketSessionPolicy.phase_for(t, is_trading_day=True)):
            raise TradingError(
                f'非交易时段（{t.strftime("%H:%M")}），'
                f'A股交易时段为 9:30-11:30 / 13:00-15:00，委托拒绝', 422)
        if not MarketSessionPolicy.accepts_new_orders(t, is_trading_day=True):
            raise TradingError(
                f'临近休市（{t.strftime("%H:%M")}），距本段结束不足 '
                f'{ORDER_CUTOFF_SECONDS} 秒，不再接受新委托', 422)

    def _is_in_trading_window(self, now: datetime) -> bool:
        """**会话是否开市**（布尔，不抛异常）——供「立即成交 vs 挂单」的决策使用。

        ⚠️ 刻意**不含**收盘截止规则：它回答的是"现在能不能立刻成交"，而不是
        "现在接不接受新委托"。若复用 `_check_trading_window`（含截止规则），
        14:59 的 `execute_at='market_open'` 会被误判为"非开市"而静默顺延到次日开盘
        （2026-09-12 审查指出）。
        """
        if not self.calendar.is_trading_day(now.date().isoformat()):
            return False
        return MarketSessionPolicy.is_market_open(
            MarketSessionPolicy.phase_for(now.time(), is_trading_day=True))

    def _check_daily_buy_limits(
        self, account_name: str, trade_amount: float, total_value: float
    ) -> None:
        """账户级日买入限额（服务端硬护栏，防 LLM 失控）。

        超限抛 TradingError，拒绝原因会返回给调用方（agent 记录后不再重试）。
        """
        today = date.today().isoformat()
        trades = self.repo.get_trades_by_account(
            account_name, start_date=today, end_date=today)
        # 2026-10-02（REQ-261001145152-3982 审查）：**兼容两种大小写写法**。
        # 原为 `t.action == 'BUY'`（注释："action 大写契约（08-13 统一）"），
        # 但本仓实际两套并存（策略/部分写入方给小写 'buy'）——按大写硬比会**静默漏掉这些持仓/成交**，
        # 后果正是本护栏失效：限额不触发（实测 tests/test_account_daily_limits.py 三条全失败）。
        buys = [t for t in trades if str(t.action).upper() == 'BUY']
        if len(buys) >= self.MAX_DAILY_BUY_COUNT:
            raise TradingError(
                f'单日买入笔数超限: 今日已买 {len(buys)} 笔，'
                f'上限 {self.MAX_DAILY_BUY_COUNT} 笔', 422)
        bought_amount = sum(float(t.amount or 0) for t in buys)
        if (bought_amount + trade_amount) / total_value > self.MAX_DAILY_BUY_AMOUNT_RATIO:
            raise TradingError(
                f'单日买入金额超限: 今日已买 ¥{bought_amount:,.0f}，'
                f'本次 ¥{trade_amount:,.0f}，'
                f'超过总资产 {self.MAX_DAILY_BUY_AMOUNT_RATIO:.0%}', 422)

    def assert_sellable(
        self, account_name: str, symbol: str, shares: int,
        *, context: Optional[Dict[str, Any]] = None,
    ) -> None:
        """卖前超卖硬校验（FR-10）。

        判定**唯一实现**在模块级 :func:`check_sellable`（本方法只是把它接到服务上，
        供调用方按服务取用）；净持仓不足时抛 ``TradingError(422)``，
        details 带 ``reason='oversell_blocked'``。
        只读校验：不写库、不改任何既有写路径语义。
        """
        check_sellable(self.repo, account_name, symbol, shares, context=context)

    def execute_trade(
        self,
        account_name: str,
        action: str,
        symbol: str,
        shares: Optional[int] = None,
        amount: Optional[float] = None,
        price_limit: Optional[float] = None,
        reason: Optional[str] = None,
        max_positions: int = 10,
        price: Optional[float] = None,
        allow_off_hours: bool = False,
        execute_at: Optional[str] = None,
        allow_duplicate: bool = False,
        submitted_by: Optional[str] = None,
    ) -> Dict:
        """
        重构版交易执行（使用 TradeGuardService）

        重构说明（2026-09-01）:
            引入 TradeGuardService 进行锁外预检查，所有业务规则集中在领域层。
            保留应用层事务管理、行级锁和锁内复核（防 TOCTOU）。

            参考文档: docs/work-logs/2026-09/account-trading-service-refactor-final-report.md

        职责划分:
            - 领域层 (TradeGuardService): 所有业务规则校验
            - 应用层 (本方法): 事务管理、行级锁、锁内复核

        Args:
            account_name: 账户名
            action: 交易方向 ('buy'/'sell')
            symbol: 股票代码
            shares: 股数（与 amount 二选一）
            amount: 金额（与 shares 二选一）
            price_limit: 限价
            reason: 交易理由（必填，至少10字）
            max_positions: 持仓数量上限
            price: 指定价格（None 则获取实时价）
            allow_off_hours: 是否允许盘后交易
            execute_at: 执行时机 ('market_open' = 挂单)
            allow_duplicate: 重复挂单确认标记（2026-09-03）。默认 False：
                挂单时若已存在同标的同方向的 pending 单 → 409 拦截，
                调用方确认无误后设 True 重发才放行。

        Returns:
            交易结果字典
        """
        # ---- 1. 参数校验和标准化 ----
        if not reason or len(reason.strip()) < 10:
            raise TradingError('必须提供详细的交易理由（至少10字）', 400)

        # 入参类型护栏（2026-09-11，w-8f2c4cc5｜看板事件 56dab403 根因）：
        # 客户端把 shares 传成 JSON 字符串时，下游 shares % 100 退化为字符串格式化，
        # 抛 TypeError("not all arguments converted during string formatting")
        # 冒泡成 500（路由 except Exception 分支当时也没记日志 → 静默 500）。
        # 这里显式校验/转换：非法类型/取值一律 400，不再落到 500。
        if not isinstance(symbol, str) or not symbol.strip():
            raise TradingError(f'symbol 必填且需为字符串，收到 {symbol!r}', 400)
        shares = self._as_int(shares, 'shares')
        amount = self._as_float(amount, 'amount')
        price = self._as_float(price, 'price')
        price_limit = self._as_float(price_limit, 'price_limit')
        max_positions = self._as_int(max_positions, 'max_positions')
        if max_positions is None:
            max_positions = 10
        if shares is not None and shares <= 0:
            raise TradingError(f'shares 必须为正整数，收到 {shares}', 400)
        if amount is not None and amount <= 0:
            raise TradingError(f'amount 必须为正数，收到 {amount}', 400)

        from infrastructure.persistence.orm.models.action_norm import normalize_action
        try:
            action = normalize_action(action)
        except ValueError:
            raise TradingError("action 必须是 'buy' 或 'sell'", 400)

        if execute_at is not None and execute_at != 'market_open':
            raise TradingError("execute_at 仅支持 'market_open'", 400)

        now = self.now_fn()

        # ---- 2. 挂单处理 ----
        if execute_at == 'market_open' and not self._is_in_trading_window(now):
            account = self.repo.get_account(account_name)
            if not account:
                raise TradingError(f'账户不存在: {account_name}', 404)
            if account.status != 'active':
                raise TradingError(f'账户已归档，拒绝写操作: {account_name}', 409)

            # ---- 2.1 重复挂单拦截（2026-09-03，防双重成交）----
            # 背景：002241 曾出现凌晨限价单+盘前市价单两笔相同 SELL 300 股 pending，
            # 若双双撮合 = 意外清仓。同标的同方向已有 pending 单时默认拦截，
            # 调用方（agent）确认后设 allow_duplicate=True 重发才放行。
            if not allow_duplicate:
                existing = self.repo.get_pending_orders(
                    account_name=account_name, status='pending') or []
                conflicts = [
                    o for o in existing
                    if getattr(o, 'symbol', None) == symbol
                    and str(getattr(o, 'action', '')).upper() == action
                ]
                if conflicts:
                    desc = '；'.join(
                        f"id={o.id} {o.action} {o.symbol} "
                        f"{o.shares if o.shares is not None else '-'}"
                        f"股{'/金额' + str(o.amount) if o.amount else ''}"
                        f"{'(限价' + str(o.price_limit) + ')' if o.price_limit is not None else '(市价)'}"
                        for o in conflicts)
                    raise TradingError(
                        f'检测到 {len(conflicts)} 笔同标的同方向 pending 挂单：{desc}。'
                        f'如确认仍要重复挂单，请设 allow_duplicate=true 重发；'
                        f'如要替换原单，请先调用 cancel 撤销后再挂。',
                        409,
                        details={
                            'conflicts': [
                                o.to_dict() if hasattr(o, 'to_dict') else {
                                    'id': getattr(o, 'id', None),
                                    'symbol': getattr(o, 'symbol', None),
                                    'action': getattr(o, 'action', None),
                                    'shares': getattr(o, 'shares', None),
                                    'price_limit': getattr(o, 'price_limit', None),
                                }
                                for o in conflicts
                            ],
                            'hint': 'allow_duplicate=true 放行；或先 cancel 原挂单再挂新单',
                        })

            # 决策价（2026-09-13 M5 执行质量闭环）：记录下单那刻看到的价格，供事后算滑点。
            # 取不到**不阻断下单**：滑点算不出来是「缺数据」而不是「没滑点」，
            # 但来源要如实标注（R-013），否则报表会把 N/A 当成 0。
            decision_price, price_source = None, None
            try:
                decision_price = self._get_price(symbol)
                price_source = 'RealtimeQuoteService@下单时刻'
            except Exception as exc:  # noqa: BLE001
                price_source = 'unavailable:%s' % type(exc).__name__
                logger.warning('pending_order_decision_price_unavailable',
                               symbol=symbol, error=str(exc)[:120])

            pending = self.repo.create_pending_order(
                account_name=account_name, action=action, symbol=symbol,
                shares=shares, amount=amount, price_limit=price_limit,
                reason=reason, execute_at='market_open',
                decision_price=decision_price, price_source=price_source,
                submitted_by=submitted_by)

            logger.info("pending_order_placed",
                        account=account_name, action=action, symbol=symbol,
                        pending_order_id=pending.id)

            return {
                'status': 'pending',
                'pending_order_id': pending.id,
                'message': '已挂单，开盘后 9:31 起自动撮合',
            }

        # ---- 3. 获取价格 ----
        px = price if price is not None else self._get_price(symbol)

        # 价格限制校验
        if price_limit is not None:
            if action == 'BUY' and px > price_limit:
                raise TradingError(f'现价 {px} 高于限价 {price_limit}，委托拒绝', 422)
            if action == 'SELL' and px < price_limit:
                raise TradingError(f'现价 {px} 低于限价 {price_limit}，委托拒绝', 422)

        # 计算股数
        if shares is None:
            if not amount:
                raise TradingError('shares 与 amount 必须提供一个', 400)
            shares = int(amount // (px * 100)) * 100
            if shares <= 0:
                raise TradingError('金额不足一手（100股）', 422)

        if shares % 100 != 0:
            raise TradingError('股数必须为 100 的整数倍', 422)

        # ---- 4. 交易护栏 - 锁外预检查（领域层）----
        from domain.trading.services.trade_guard_service import TradeGuardService
        from application.services.portfolio_breaker_service import is_active as portfolio_breaker_active

        trade_guard = TradeGuardService(
            repo=self.repo,
            calendar=self.calendar,
            now_fn=self.now_fn,
            breaker_active_fn=portfolio_breaker_active
        )

        # 所有业务规则在这里校验：交易时段、限额、资金、持仓、仓位
        fees_info = trade_guard.validate_trade_request(
            account_name=account_name,
            action=action,
            symbol=symbol,
            shares=shares,
            price=px,
            max_positions=max_positions,
            allow_off_hours=allow_off_hours
        )

        # 提取费用信息
        trade_amount = fees_info['trade_amount']
        commission = fees_info['commission']
        stamp_duty = fees_info.get('stamp_duty', 0.0)
        transfer_fee = fees_info['transfer_fee']
        realized_pnl = fees_info.get('realized_pnl')
        realized_pnl_rate = fees_info.get('realized_pnl_rate')

        # ---- 5. 事务执行 ----
        try:
            # 行级锁串行化同账户并发交易，防 lost update
            locked_account = self.repo.get_account_for_update(account_name)
            if not locked_account:
                raise TradingError(f'账户不存在: {account_name}', 404)

            # 锁内复核资金（防 TOCTOU）
            if action == 'BUY':
                total_cost = fees_info['total_cost']
                if total_cost > float(locked_account.cash_available):
                    raise TradingError(
                        f'可用资金不足(锁内复核): 需要 ¥{total_cost:,.2f}'
                        f'，可用 ¥{float(locked_account.cash_available):,.2f}', 422)

            # 锁内重读持仓（防并发）
            self.repo.session.expire_all()
            positions = self.repo.get_all_positions(account_name)
            pos = next((p for p in positions if p.symbol == symbol), None)

            # 锁内复核持仓（防 TOCTOU）
            if action == 'SELL':
                if pos is None or pos.shares_total <= 0:
                    raise TradingError(f'无 {symbol} 持仓，无法卖出', 422)
                if shares > pos.shares_available:
                    raise TradingError(
                        f'T+1 可卖数量不足: 可卖 {pos.shares_available} 股，委托 {shares} 股', 422,
                        details={'sellable_shares': pos.shares_available, 'symbol': symbol})

            # FR-10（t-900179）：卖前超卖硬校验——账本真源是**流水净额**，
            # 持仓表只是它的派生物（双源并存正是历史虚增 ≈¥49,425 的成因）。
            # 刻意放在 T+1 复核**之后**：先答"这单能不能卖"（持仓/可卖数），
            # 再答"卖了会不会凭空多出现金"（累计买卖净额）；顺序反了会把既有拒绝原因
            # 换成超卖原因，增大既有调用方的判读成本。
            if action == 'SELL':
                self.assert_sellable(
                    account_name, symbol, shares,
                    context={'phase': 'execute_trade', 'at': now.isoformat()})

            # ---- 6. 创建订单并标记已成交 ----
            order = self.repo.create_order(
                account_name=account_name, action=action, symbol=symbol,
                shares=shares, price_limit=price_limit, reason=reason,
                submitted_by=submitted_by,
                commit=False)

            order.status = 'filled'
            order.filled_shares = shares
            order.avg_filled_price = px

            # ---- 7. 创建成交记录 ----
            trade_id = self.repo.add_trade(
                account_name=account_name, symbol=symbol, action=action,
                shares=shares, price=px, filled_price=px, amount=trade_amount,
                commission=commission, stamp_duty=stamp_duty, transfer_fee=transfer_fee,
                total_cost=trade_amount + commission + transfer_fee if action == 'BUY' else None,
                total_revenue=trade_amount - commission - stamp_duty - transfer_fee if action == 'SELL' else None,
                order_id=order.id, realized_pnl=realized_pnl,
                realized_pnl_rate=realized_pnl_rate, reason=reason, commit=False)

            # ---- 8. 更新持仓 ----
            if action == 'BUY':
                old_total = pos.shares_total if pos else 0
                old_cost = float(pos.avg_cost) * old_total if pos else 0.0
                new_total = old_total + shares
                new_avg = round((old_cost + trade_amount + commission + transfer_fee) / new_total, 4)

                self.repo.upsert_position(
                    account_name, symbol, shares_total=new_total, avg_cost=new_avg,
                    shares_available=pos.shares_available if pos else 0,  # T+1
                    current_price=px, commit=False)

                # 扣减资金
                locked_account.cash_available = float(locked_account.cash_available) - (
                    trade_amount + commission + transfer_fee)
            else:  # SELL
                remaining = pos.shares_total - shares
                if remaining == 0:
                    self.repo.delete_position(account_name, symbol, commit=False)
                else:
                    self.repo.upsert_position(
                        account_name, symbol, shares_total=remaining,
                        avg_cost=float(pos.avg_cost),
                        shares_available=pos.shares_available - shares,
                        current_price=px, commit=False)

                # 增加资金
                locked_account.cash_available = float(locked_account.cash_available) + (
                    trade_amount - commission - stamp_duty - transfer_fee)

            # ---- 9. 更新账户总值 ----
            position_value = sum(
                float(p.market_value or 0) or float(p.shares_total) * float(p.current_price or p.avg_cost)
                for p in positions
            )

            locked_account.position_value = position_value + (
                trade_amount if action == 'BUY' else -trade_amount)
            locked_account.total_value = (
                float(locked_account.cash_available) + float(locked_account.cash_frozen)
                + float(locked_account.position_value))

            if locked_account.initial_capital:
                locked_account.cumulative_return = (
                    float(locked_account.total_value) / float(locked_account.initial_capital) - 1)

            if locked_account.peak_value and float(locked_account.total_value) > float(locked_account.peak_value):
                locked_account.peak_value = locked_account.total_value

            # ---- 10. 创建账户快照 ----
            self.repo.upsert_equity_snapshot(
                account_name,
                cash=float(locked_account.cash_available) + float(locked_account.cash_frozen),
                position_value=float(locked_account.position_value),
                total_value=float(locked_account.total_value),
                cumulative_return=float(locked_account.cumulative_return or 0),
                drawdown=(float(locked_account.total_value) / float(locked_account.peak_value) - 1)
                if locked_account.peak_value else 0.0,
                commit=False)

            # ---- 11. 提交事务 ----
            self.repo.session.commit()

        except TradingError:
            self.repo.session.rollback()
            raise
        except Exception as e:
            self.repo.session.rollback()
            logger.error("trade_transaction_failed_rollback", error=str(e), exc_info=True)
            raise TradingError(f'交易执行失败: {e}', 500)

        # ---- 12. 决策记录 ----
        self._auto_record_decision(
            account_name=account_name, action=action, symbol=symbol,
            shares=shares, price=px, amount=trade_amount,
            reason=reason, realized_pnl=realized_pnl)

        logger.info(
            "trade_executed_v2",
            account=account_name, action=action, symbol=symbol,
            shares=shares, price=px, trade_id=trade_id
        )

        return {
            'order_id': order.id,
            'order_status': 'filled',
            'trade_id': trade_id,
            'symbol': symbol,
            'action': action.lower(),
            'shares': shares,
            'price': px,
            'amount': trade_amount,
            'commission': commission,
            'stamp_duty': stamp_duty,
            'transfer_fee': transfer_fee,
            'realized_pnl': realized_pnl,
            'realized_pnl_rate': realized_pnl_rate,
        }

    #: 挂单「超期」判定（REQ-261004154902-a7cd t4 / FR-7）：
    #: 一个 ``execute_at='market_open'`` 的挂单本意是**下一个开盘**成交，
    #: 因此「已经错过至少 1 个开盘机会仍未成交」即判超期（作废 + 告警）。
    #: 刻意不用「创建满 N 个自然日」——后者会把昨晚下的单在今晚就误杀。
    PENDING_ORDER_MAX_MISSED_OPENS = 1

    def _trading_days_between(self, start: date, end: date, cap: int = 10):
        """``(start, end]`` 之间的交易日数；超过 ``cap`` 提前返回。

        取数失败返回 ``None``（**判定不了 ≠ 已超期**）：宁可留痕后不动这单，
        也不要用猜测去作废一笔本来正确的委托。
        """
        if end <= start:
            return 0
        count = 0
        cursor = start
        while cursor < end and count < cap:
            cursor = cursor + timedelta(days=1)
            try:
                if self.calendar.is_trading_day(cursor.isoformat()):
                    count += 1
            except Exception as exc:  # noqa: BLE001 - 判定不了必须响亮且保守
                logger.warning(
                    "pending_order_expiry_calendar_unavailable",
                    day=cursor.isoformat(), error=str(exc),
                )
                return None
        return count

    def _pending_order_is_stale(self, pending_order, now: datetime):
        """True=已超期；False=还没到；None=判定不了（已留痕）。"""
        created = getattr(pending_order, "created_at", None)
        if created is None:
            return False
        if isinstance(created, datetime):
            created_date = created.date()
        elif isinstance(created, date):
            created_date = created
        else:
            # 创建时刻不可信（不是日期类型）→ **只跳过超期判定，不影响本次撮合**。
            # 为什么不留痕外发：这是对象形状问题（生产库里该列是 timestamp，必然是 datetime），
            # 报成业务告警只会制造噪音；但必须留 ERROR 日志，免得悄悄少了一道护栏。
            logger.error(
                "pending_order_created_at_unusable",
                pending_order_id=getattr(pending_order, "id", None),
                value=repr(created)[:80],
                note="跳过超期判定（不影响本次撮合）",
            )
            return False
        days = self._trading_days_between(created_date, now.date())
        if days is None:
            return None
        # days 含"今天"这一天：昨晚下的单在今天的开盘被撮合时 days=1 → 不算超期
        return (days - 1) >= self.PENDING_ORDER_MAX_MISSED_OPENS

    def execute_pending_orders(
        self, now: Optional[datetime] = None, *, expire_stale: bool = True
    ) -> Dict:
        """撮合所有 pending 挂单（由 orchestrator 在开盘后 9:31 起调用）。

        每个挂单走完整 execute_trade 护栏（不带 execute_at）：
        - 成功 → status='executed' + executed_trade_id
        - 护栏拒绝（TradingError）→ status='failed' + fail_reason
        - **内部异常**（非护栏拒绝）→ 该单标 failed 并**继续处理下一单**
        - **非交易时段调用** → 全部跳过、状态保持 pending（不误杀）
        - **超期未成交** → status='expired' + fail_reason + 主动外发

        幂等：已处理的订单不再是 pending，重复调用无副作用。

        2026-10-04（REQ-261004154902-a7cd t4 / FR-7）三处修正，均出自实证：
        1. 原实现只 catch ``TradingError``，其它异常会掀翻整个循环——剩下的挂单
           永远不被尝试、也没有任何留痕。实证：`agent_virtual` 两笔挂单自
           2026-08-24 起 `updated_at == created_at`，**41 天无人碰**。
        2. 原实现没有时段护栏：盘后被调用时每笔都被 execute_trade 拒成 failed
           （实证 2026-08-21 16:41 两笔「非交易时段…委托拒绝」），从此永久丢弃。
        3. 原实现没有超期概念：链路一断，挂单就无限期躺在 pending 里，无人知。
        """
        now = now or self.now_fn()

        # ① 时段护栏：非开市只跳过、不改状态（严禁把挂单批量打成 failed）
        # 2026-10-04（t4）：日历取数失败时**保守跳过**——判定不了"现在能不能成交"，
        # 就不要在不知道开没开市的情况下下单；但必须留痕外发，否则又变成
        # "没人知道这些挂单为什么没成交"。
        try:
            in_window = self._is_in_trading_window(now)
        except Exception as exc:  # noqa: BLE001 - 判定不了必须响亮且保守
            reason = (
                f'交易日历不可用（{type(exc).__name__}: {exc}）→ '
                '无法判定开市状态，本次不撮合任何挂单'
            )
            logger.error("pending_orders_window_check_failed", at=now.isoformat(), error=reason)
            report_failure(
                'pending_orders.window_check',
                'match_failed',
                reason,
                severity=SEVERITY_HIGH,
                context={'at': now.isoformat()},
            )
            return {
                'executed': 0, 'failed': 0, 'errored': 0, 'expired': 0,
                'skipped_off_hours': 0,
                'details': [{'status': 'skipped_calendar_unavailable', 'reason': reason}],
            }

        if not in_window:
            still_pending = list(self.repo.get_pending_orders(status='pending') or [])
            reason = (
                f'非交易时段或非交易日（{now.strftime("%Y-%m-%d %H:%M")}），'
                '挂单保持 pending，等下一个开盘再接'
            )
            logger.info(
                "pending_orders_match_skipped_off_hours",
                at=now.isoformat(), pending=len(still_pending), reason=reason,
            )
            return {
                'executed': 0, 'failed': 0, 'errored': 0, 'expired': 0,
                'skipped_off_hours': len(still_pending),
                'details': [{'status': 'skipped_off_hours', 'reason': reason}],
            }

        pending = self.repo.get_pending_orders(status='pending')
        executed = 0
        failed = 0
        errored = 0
        expired = 0
        details = []

        for po in list(pending or []):
            # ② 超期作废：错过的开盘机会数够了就收口，并主动外发（不再无声搁浅）
            if expire_stale:
                stale = self._pending_order_is_stale(po, now)
                if stale is None:
                    report_failure(
                        'pending_orders.expiry_check',
                        'match_failed',
                        f'无法判定挂单 {po.id} 是否超期（交易日历取数失败）→ 本次不动它',
                        severity=SEVERITY_HIGH,
                        context={'pending_order_id': po.id, 'account': po.account_name},
                    )
                elif stale:
                    reason = (
                        'expired: 已错过至少 '
                        f'{self.PENDING_ORDER_MAX_MISSED_OPENS} 个开盘机会仍未成交'
                    )
                    self.repo.update_pending_order_status(
                        po.id, 'expired', fail_reason=reason
                    )
                    expired += 1
                    details.append({
                        'pending_order_id': po.id,
                        'status': 'expired',
                        'fail_reason': reason,
                    })
                    report_failure(
                        'pending_orders.expired',
                        'pending_expired',
                        f'挂单 {po.id}（{po.account_name} {po.symbol} {po.action}）超期作废：{reason}',
                        severity=SEVERITY_HIGH,
                        context={
                            'pending_order_id': po.id,
                            'account': po.account_name,
                            'symbol': po.symbol,
                            'created_at': str(getattr(po, 'created_at', None)),
                        },
                    )
                    continue

            try:
                result = self.execute_trade(
                    account_name=po.account_name,
                    action=po.action,
                    symbol=po.symbol,
                    shares=po.shares,
                    amount=float(po.amount) if po.amount is not None else None,
                    price_limit=float(po.price_limit) if po.price_limit is not None else None,
                    reason=po.reason,
                )
                # 滑点（M5 闭环）：方向归一——正数 = 买贵/卖便宜 = 成本。
                # 无决策价（下单时取不到）则留 None，绝不拿成交价自比冒充 0 滑点。
                fill_px = result.get('price')
                dp = float(po.decision_price) if po.decision_price is not None else None
                slip = None
                if dp and fill_px:
                    sign = 1.0 if str(po.action).upper() == 'BUY' else -1.0
                    slip = round(sign * (float(fill_px) - dp) / dp * 10000, 2)
                self.repo.update_pending_order_status(
                    po.id, 'executed', executed_trade_id=result['trade_id'],
                    fill_price=fill_px, slippage_bps=slip)
                executed += 1
                details.append({
                    'pending_order_id': po.id,
                    'status': 'executed',
                    'trade_id': result['trade_id'],
                    'decision_price': dp,
                    'fill_price': float(fill_px) if fill_px else None,
                    'slippage_bps': slip,
                })
            except TradingError as e:
                # 护栏拒绝：是"这单不该成交"，如实记 failed（既有语义不变）
                self.repo.update_pending_order_status(
                    po.id, 'failed', fail_reason=str(e))
                failed += 1
                details.append({
                    'pending_order_id': po.id,
                    'status': 'failed',
                    'fail_reason': str(e),
                })
            except Exception as e:  # noqa: BLE001 - 单笔内部异常不得中断整批
                reason = f'internal_error: {type(e).__name__}: {e}'
                logger.error("pending_order_internal_error", pending_order_id=po.id, error=reason)
                try:
                    self.repo.update_pending_order_status(
                        po.id, 'failed', fail_reason=reason)
                except Exception as inner:  # noqa: BLE001 - 连留痕都失败，也要继续
                    logger.error(
                        "pending_order_mark_failed_also_failed",
                        pending_order_id=po.id, error=str(inner),
                    )
                errored += 1
                details.append({
                    'pending_order_id': po.id,
                    'status': 'failed',
                    'fail_reason': reason,
                    'error': str(e),
                })
                report_failure(
                    'pending_orders.match',
                    'match_failed',
                    f'挂单 {po.id}（{po.account_name} {po.symbol} {po.action}）撮合抛内部异常：{reason}',
                    severity=SEVERITY_HIGH,
                    context={'pending_order_id': po.id, 'account': po.account_name},
                )

        if executed or failed or errored or expired:
            logger.info(
                "pending_orders_matched",
                executed=executed, failed=failed, errored=errored,
                expired=expired, at=now.isoformat(),
            )
        return {
            'executed': executed,
            'failed': failed,
            'errored': errored,
            'expired': expired,
            'skipped_off_hours': 0,
            'details': details,
        }

    def _auto_record_decision(
        self, account_name: str, action: str, symbol: str,
        shares: int, price: float, amount: float,
        reason: Optional[str], realized_pnl: Optional[float],
    ) -> None:
        """成交后自动写 agent_decisions 审计记录。

        失败只记日志不影响交易结果（审计不能拖垮主链路）。
        Agent 只需在"放弃信号/不交易"时显式 decision_record——
        成交类记录由本方法保证。
        """
        try:
            from infrastructure.services.service_factory import ServiceFactory
            ServiceFactory.get_decision_service().record_decision({
                # 2026-09-13（w-c8cae280）：action 是 'BUY'/'SELL' 大写，原样拼进
                # decision_type 会落库成 trade_BUY / trade_SELL，与打分器的小写口径
                # （SCORABLE_TYPES）不匹配 ⇒ 成交决策永远进不了评分。统一小写。
                'decision_type': f'trade_{str(action).lower()}',
                'reasoning': reason or '',
                'context': {'account': account_name, 'auto_recorded': True},
                'parameters': {
                    'symbol': symbol,
                    'shares': shares,
                    'price': price,
                    'amount': amount,
                    'realized_pnl': realized_pnl,
                },
                'related_entity_type': 'stock',
                'related_entity_id': symbol,
            })
        except Exception as e:
            logger.warning(f"auto_record_decision_failed（不影响成交）: {e}")

    def cancel_pending_order(self, account_name: str, order_id: int) -> Dict:
        """取消挂单（仅 pending 状态可取消）"""
        order = self.repo.get_pending_order(order_id)
        if not order or order.account_name != account_name:
            raise TradingError(f'挂单不存在: {order_id}', 404)
        if order.status != 'pending':
            raise TradingError(
                f'仅 pending 状态可取消，当前状态: {order.status}', 409)
        self.repo.update_pending_order_status(order_id, 'cancelled')
        logger.info("pending_order_cancelled",
                    account=account_name, pending_order_id=order_id)
        return {'status': 'cancelled', 'pending_order_id': order_id}
