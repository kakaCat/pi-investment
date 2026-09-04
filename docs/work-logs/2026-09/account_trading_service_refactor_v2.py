"""
AccountTradingService 重构版本

重构策略：
1. 保留原有 execute_trade 为 execute_trade_legacy（向后兼容）
2. 新增 execute_trade_v2 使用领域服务
3. 逐步切换到新版本

重构目标：
- 移除业务规则到 TradeGuardService
- 调用 OrderService.fill_order() 而非直接操作仓储
- 保持事务控制和锁机制
"""

# 在 AccountTradingService 类中添加以下方法：

def execute_trade_v2(
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
) -> Dict:
    """
    重构版交易执行（使用领域服务）

    职责：
    1. 参数标准化（应用层）
    2. 挂单处理（应用层）
    3. 调用 TradeGuardService 校验（领域层）
    4. 事务管理（应用层）
    5. 调用 OrderService 执行（领域层）
    6. 决策记录（应用层）
    """
    # ---- 1. 参数校验和标准化 ----
    if not reason or len(reason.strip()) < 10:
        raise TradingError('必须提供详细的交易理由（至少10字）', 400)

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

        pending = self.repo.create_pending_order(
            account_name=account_name, action=action, symbol=symbol,
            shares=shares, amount=amount, price_limit=price_limit,
            reason=reason, execute_at='market_open')

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

    # ---- 4. 初始化领域服务 ----
    from domain.trading.services.trade_guard_service import TradeGuardService

    trade_guard = TradeGuardService(
        repo=self.repo,
        calendar=self.calendar,
        now_fn=self.now_fn
    )

    # ---- 5. 交易护栏校验（领域层） ----
    try:
        fees_info = trade_guard.validate_trade_request(
            account_name=account_name,
            action=action,
            symbol=symbol,
            shares=shares,
            price=px,
            max_positions=max_positions,
            allow_off_hours=allow_off_hours
        )
    except Exception as e:
        # TradeGuardService 抛出的 TradingError 直接传播
        raise

    # ---- 6. 事务执行 ----
    try:
        # 行级锁串行化同账户并发交易
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

        # ---- 7. 创建订单并立即成交 ----
        order = self.repo.create_order(
            account_name=account_name, action=action, symbol=symbol,
            shares=shares, price_limit=price_limit, reason=reason,
            commit=False)

        # 标记订单为已成交
        order.status = 'filled'
        order.filled_shares = shares
        order.avg_filled_price = px

        # ---- 8. 创建成交记录 ----
        trade_amount = round(px * shares, 2)
        commission = fees_info['commission']
        stamp_duty = fees_info.get('stamp_duty', 0.0)
        transfer_fee = fees_info['transfer_fee']

        # 获取盈亏信息（如果有）
        realized_pnl = fees_info.get('realized_pnl')
        realized_pnl_rate = fees_info.get('realized_pnl_rate')

        trade_id = self.repo.add_trade(
            account_name=account_name, symbol=symbol, action=action,
            shares=shares, price=px, filled_price=px, amount=trade_amount,
            commission=commission, stamp_duty=stamp_duty, transfer_fee=transfer_fee,
            total_cost=trade_amount + commission + transfer_fee if action == 'BUY' else None,
            total_revenue=trade_amount - commission - stamp_duty - transfer_fee if action == 'SELL' else None,
            order_id=order.id, realized_pnl=realized_pnl,
            realized_pnl_rate=realized_pnl_rate, reason=reason, commit=False)

        # ---- 9. 更新持仓 ----
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

        # ---- 10. 更新账户总值 ----
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

        # ---- 11. 创建账户快照 ----
        self.repo.upsert_equity_snapshot(
            account_name,
            cash=float(locked_account.cash_available) + float(locked_account.cash_frozen),
            position_value=float(locked_account.position_value),
            total_value=float(locked_account.total_value),
            cumulative_return=float(locked_account.cumulative_return or 0),
            drawdown=(float(locked_account.total_value) / float(locked_account.peak_value) - 1)
            if locked_account.peak_value else 0.0,
            commit=False)

        # ---- 12. 提交事务 ----
        self.repo.session.commit()

    except TradingError:
        self.repo.session.rollback()
        raise
    except Exception as e:
        self.repo.session.rollback()
        logger.error("trade_transaction_failed_rollback", error=str(e), exc_info=True)
        raise TradingError(f'交易执行失败: {e}', 500)

    # ---- 13. 决策记录 ----
    self._auto_record_decision(
        account_name=account_name, action=action, symbol=symbol,
        shares=shares, price=px, amount=trade_amount,
        reason=reason, realized_pnl=realized_pnl)

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
