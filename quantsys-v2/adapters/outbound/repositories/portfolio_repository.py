"""
持仓ORM Repository

使用SQLAlchemy ORM重构的持仓数据访问层

支持：
1. 持仓查询（单只/批量）
2. 持仓添加和更新
3. 持仓统计
4. 历史持仓重建

迁移状态：✅ 已完成ORM迁移
"""
from typing import List, Dict, Optional, Any
from datetime import date
import structlog

from sqlalchemy import func, and_, or_, case
from infrastructure.persistence.orm import BaseORMRepository
from domain.ports import IPortfolioRepository
from infrastructure.persistence.orm.models import PortfolioHolding, Trade
from adapters.outbound.repositories.risk_repository import _validate_symbol, _validate_date

logger = structlog.get_logger(__name__)

__all__ = ['PortfolioORMRepository']


class PortfolioORMRepository(BaseORMRepository[PortfolioHolding], IPortfolioRepository):
    """持仓ORM Repository

    示例用法：
        repo = PortfolioORMRepository()

        # 查询单个持仓
        holding = repo.get_holding('000001')

        # 查询所有持仓
        holdings = repo.get_all_holdings()

        # 添加或更新持仓
        success = repo.add_or_update_holding({
            'symbol': '000001',
            'name': '平安银行',
            'quantity': 1000,
            'avg_cost': 10.5,
            'total_invested': 10500,
            'market': 'A',
            'added_date': '2026-01-01'
        })
    """

    model = PortfolioHolding

    # ==================== IPortfolioRepository接口实现 ====================

    def get_portfolio_history(
        self,
        portfolio_name: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """获取组合历史（IPortfolioRepository接口实现）

        Args:
            portfolio_name: 组合名称
            start_date: 开始日期
            end_date: 结束日期

        Returns:
            历史记录列表
        """
        try:
            query = self.session.query(PortfolioHolding).filter(
                PortfolioHolding.portfolio_name == portfolio_name
            )

            if start_date:
                query = query.filter(PortfolioHolding.added_date >= start_date)
            if end_date:
                query = query.filter(PortfolioHolding.added_date <= end_date)

            holdings = query.all()
            return [self._holding_to_dict(h) for h in holdings]

        except Exception as e:
            self._safe_rollback()
            logger.error(f"Error getting portfolio history: {e}")
            return []

    def save_portfolio_snapshot(
        self,
        portfolio_name: str,
        snapshot_data: Dict[str, Any]
    ) -> int:
        """保存组合快照（IPortfolioRepository接口实现）

        Args:
            portfolio_name: 组合名称
            snapshot_data: 快照数据

        Returns:
            快照ID
        """
        try:
            # 保存为持仓记录
            holding = PortfolioHolding(
                portfolio_name=portfolio_name,
                symbol=snapshot_data.get('symbol'),
                name=snapshot_data.get('name'),
                quantity=snapshot_data.get('quantity'),
                available_quantity=snapshot_data.get('available_quantity'),
                avg_cost=snapshot_data.get('avg_cost'),
                total_invested=snapshot_data.get('total_invested'),
                market=snapshot_data.get('market'),
                added_date=snapshot_data.get('added_date'),
            )
            created = self.create(holding)
            return created.id if created else 0

        except Exception as e:
            self._safe_rollback()
            logger.error(f"Error saving portfolio snapshot: {e}")
            return 0

    def _holding_to_dict(self, holding: PortfolioHolding) -> Dict[str, Any]:
        """将PortfolioHolding对象转换为字典（委托给 model.to_dict）"""
        return holding.to_dict()

    def _trade_to_raw_dict(self, trade: Trade) -> Dict[str, Any]:
        """将 Trade 对象转为**原始列类型**的字典。

        ⚠️ 刻意不复用 Trade.to_dict()：to_dict() 会把 trade_date/created_at
        字符串化（isoformat），而本文件这几处读取的旧契约是 psycopg2 DictCursor
        的 dict(row)——日期保持 date/datetime 对象。裸 SQL 迁 ORM 时不得顺手
        改变返回类型（历史教训：日期被无条件字符串化后，下游 date 运算直接炸）。
        """
        return {
            'id': trade.id,
            'symbol': trade.symbol,
            'name': trade.name,
            'action': trade.action,
            'price': trade.price,
            'quantity': trade.quantity,
            'amount': trade.amount,
            'fee': trade.fee,
            'stamp_duty': trade.stamp_duty,
            'trade_date': trade.trade_date,
            'order_id': trade.order_id,
            'created_at': trade.created_at,
            'pnl': trade.pnl,
            'pnl_percent': trade.pnl_percent,
            'reason': trade.reason,
        }

    # ==================== 查询方法 ====================

    def _get_holding_model(self, symbol: str) -> Optional[PortfolioHolding]:
        """查询持仓 ORM 对象（内部使用：更新/删除场景）"""
        try:
            return self.session.query(PortfolioHolding).filter_by(
                symbol=symbol
            ).first()
        except Exception as e:
            self._safe_rollback()
            logger.error(f"Error getting holding for {symbol}: {e}")
            return None

    def get_holding(self, symbol: str) -> Optional[Dict]:
        """查询指定股票的持仓

        注：旧契约为 Dict（order_service/risk_check_service 均按
        holding.get('quantity') 使用），8f06ae1 重构误改为返回 ORM
        对象导致下游 AttributeError。此处恢复 dict 契约；
        需要 ORM 对象的内部调用方改用 _get_holding_model。

        Args:
            symbol: 股票代码

        Returns:
            持仓字典，不存在返回None
        """
        _validate_symbol(symbol)

        holding = self._get_holding_model(symbol)
        return holding.to_dict() if holding else None

    def get_all_holdings(
        self,
        market: Optional[str] = None,
        sector: Optional[str] = None
    ) -> List[Dict]:
        """查询所有持仓

        注：8f06ae1 DDD 重构把返回类型从 List[Dict] 改成了
        List[PortfolioHolding]，但路由层（risk/orders/stock）与
        risk_rules/stress_test/risk_check_service 等存量调用方全部
        按 dict 使用（h['symbol'] / h.get(...)），导致
        'PortfolioHolding' object is not subscriptable。
        此处恢复旧的 List[Dict] 契约。

        Args:
            market: 市场筛选 (A/HK)
            sector: 行业筛选

        Returns:
            持仓字典列表
        """
        try:
            query = self.session.query(PortfolioHolding)

            if market:
                query = query.filter(PortfolioHolding.market == market)
            if sector:
                query = query.filter(PortfolioHolding.sector == sector)

            holdings = query.order_by(PortfolioHolding.total_invested.desc()).all()
            return [h.to_dict() for h in holdings]

        except Exception as e:
            self._safe_rollback()
            logger.error(f"Error getting all holdings: {e}")
            return []

    def get_holdings_as_of(self, as_of_date: str) -> List[Dict]:
        """按交易历史重建指定日期的持仓（窗口函数契约）

        旧 BaseRepository 时代契约，ORM 重构（8f06ae1）时丢失，
        2026-08-06 恢复——domain/quantlib/core/portfolio_calculator.py
        （calculate_market_value/get_position_count）在调用，
        缺失即 AttributeError。

        语义对齐归档实现（quantsys-v2.git.archive 8f06ae1^）：
        聚合 as_of_date 之前全部 trades（buy 加 / sell 减）得到净持仓，
        只返回净数量 > 0 的股票；name 取该 symbol 最新一笔交易的名称。
        实现从 psycopg2 原生 SQL 改为 ORM（GROUP BY + DISTINCT ON 子查询）。

        Args:
            as_of_date: 截止日期 (YYYY-MM-DD)

        Returns:
            [{symbol, name, quantity}]，quantity 为净持仓（> 0）
        """
        _validate_date(as_of_date)

        try:
            net_quantity = func.sum(
                case((Trade.action.upper() == 'BUY', Trade.quantity), else_=-Trade.quantity)
            )

            position_summary = self.session.query(
                Trade.symbol.label('symbol'),
                net_quantity.label('quantity'),
            ).filter(
                Trade.trade_date <= as_of_date
            ).group_by(
                Trade.symbol
            ).having(
                net_quantity > 0
            ).subquery()

            # 每个 symbol 最新一笔交易的名称（DISTINCT ON，等价归档窗口函数实现）
            latest_names = self.session.query(
                Trade.symbol.label('symbol'),
                Trade.name.label('name'),
            ).filter(
                Trade.trade_date <= as_of_date
            ).order_by(
                Trade.symbol, Trade.trade_date.desc()
            ).distinct(
                Trade.symbol
            ).subquery()

            rows = self.session.query(
                position_summary.c.symbol,
                latest_names.c.name,
                position_summary.c.quantity,
            ).outerjoin(
                latest_names, latest_names.c.symbol == position_summary.c.symbol
            ).all()

            return [
                {'symbol': row.symbol, 'name': row.name, 'quantity': row.quantity}
                for row in rows
            ]

        except Exception as e:
            self._safe_rollback()
            logger.error(f"Error reconstructing holdings as of {as_of_date}: {e}")
            return []

    def get_holdings_by_date_range(
        self,
        start_date: str,
        end_date: str
    ) -> List[PortfolioHolding]:
        """查询指定日期范围内建仓的持仓

        Args:
            start_date: 开始日期
            end_date: 结束日期

        Returns:
            PortfolioHolding对象列表
        """
        try:
            return self.session.query(PortfolioHolding).filter(
                PortfolioHolding.added_date >= start_date,
                PortfolioHolding.added_date <= end_date
            ).order_by(PortfolioHolding.added_date.desc()).all()

        except Exception as e:
            self._safe_rollback()
            logger.error(f"Error getting holdings by date range: {e}")
            return []

    # ==================== 创建和更新 ====================

    def add_or_update_holding(self, holding_data: Dict) -> bool:
        """添加或更新持仓（UPSERT）

        Args:
            holding_data: 持仓数据
                必需字段: symbol, name, quantity, avg_cost, total_invested, market, added_date
                可选字段: original_cost, sector, stop_loss, target_price, buy_reason, notes

        Returns:
            是否成功
        """
        required_fields = ['symbol', 'name', 'quantity', 'avg_cost', 'total_invested', 'market', 'added_date']

        # 验证必需字段（旧契约：缺字段/格式错误抛 ValueError）
        for field in required_fields:
            if field not in holding_data:
                raise ValueError(f"缺少必需字段: {field}")

        _validate_symbol(holding_data['symbol'])
        _validate_date(holding_data['added_date'])

        try:
            # 查找现有持仓
            holding = self._get_holding_model(holding_data['symbol'])

            if holding:
                # 更新现有持仓
                for key, value in holding_data.items():
                    if hasattr(holding, key):
                        setattr(holding, key, value)
            else:
                # 创建新持仓
                holding = PortfolioHolding(**holding_data)
                self.session.add(holding)

            self.session.commit()
            return True

        except Exception as e:
            logger.error(f"Error adding/updating holding: {e}")
            self.session.rollback()
            return False

    def update_holding(self, symbol: str, **kwargs) -> bool:
        """更新持仓字段

        Args:
            symbol: 股票代码
            **kwargs: 要更新的字段

        Returns:
            成功返回True
        """
        try:
            holding = self._get_holding_model(symbol)
            if not holding:
                logger.warning(f"Holding {symbol} not found")
                return False

            for key, value in kwargs.items():
                if hasattr(holding, key):
                    setattr(holding, key, value)

            self.session.commit()
            return True

        except Exception as e:
            logger.error(f"Error updating holding {symbol}: {e}")
            self.session.rollback()
            return False

    def delete_holding(self, symbol: str) -> bool:
        """删除持仓

        Args:
            symbol: 股票代码

        Returns:
            成功返回True
        """
        try:
            holding = self._get_holding_model(symbol)
            if holding:
                self.session.delete(holding)
                self.session.commit()
                return True
            return False

        except Exception as e:
            logger.error(f"Error deleting holding {symbol}: {e}")
            self.session.rollback()
            return False

    # ==================== 统计方法 ====================

    def count_holdings(self, market: Optional[str] = None) -> int:
        """统计持仓数量

        Args:
            market: 市场筛选

        Returns:
            持仓数量
        """
        try:
            query = self.session.query(PortfolioHolding)
            if market:
                query = query.filter(PortfolioHolding.market == market)
            return query.count()

        except Exception as e:
            self._safe_rollback()
            logger.error(f"Error counting holdings: {e}")
            return 0

    def get_total_invested(self, market: Optional[str] = None) -> float:
        """获取总投入金额

        Args:
            market: 市场筛选

        Returns:
            总投入金额
        """
        try:
            query = self.session.query(
                func.sum(PortfolioHolding.total_invested)
            )

            if market:
                query = query.filter(PortfolioHolding.market == market)

            result = query.scalar()
            return float(result or 0)

        except Exception as e:
            self._safe_rollback()
            logger.error(f"Error getting total invested: {e}")
            return 0.0

    def get_holdings_summary(self) -> Dict:
        """获取持仓汇总

        Returns:
            汇总信息字典
        """
        try:
            holdings = self.get_all_holdings()

            total_count = len(holdings)
            total_invested = sum(float(h['total_invested']) for h in holdings)
            total_quantity = sum(h['quantity'] for h in holdings)

            # 按市场分组
            market_stats = {}
            for holding in holdings:
                market = holding['market']
                if market not in market_stats:
                    market_stats[market] = {
                        'count': 0,
                        'total_invested': 0,
                        'total_quantity': 0
                    }
                market_stats[market]['count'] += 1
                market_stats[market]['total_invested'] += float(holding['total_invested'])
                market_stats[market]['total_quantity'] += holding['quantity']

            # 按行业分组
            sector_stats = {}
            for holding in holdings:
                sector = holding.get('sector') or '未分类'
                if sector not in sector_stats:
                    sector_stats[sector] = {
                        'count': 0,
                        'total_invested': 0
                    }
                sector_stats[sector]['count'] += 1
                sector_stats[sector]['total_invested'] += float(holding['total_invested'])

            return {
                'total_count': total_count,
                'total_invested': total_invested,
                'total_quantity': total_quantity,
                'market_stats': market_stats,
                'sector_stats': sector_stats
            }

        except Exception as e:
            self._safe_rollback()
            logger.error(f"Error getting holdings summary: {e}")
            return {}

    def get_holdings_stats(self) -> Dict:
        """
        获取持仓统计信息

        注：8f06ae1 DDD 重构误删了本方法，但 routes/risk.py 的
        /api/risk/check 与 fastapi_app/routes/risk_async.py 仍在调用，
        导致风险检查接口 500。此处恢复原有实现与返回形状。

        Returns:
            统计信息 {total_positions, total_invested, total_cost,
                      sector_distribution, market_distribution}
        """
        totals = self.session.query(
            func.count().label('total_positions'),
            func.coalesce(func.sum(PortfolioHolding.total_invested), 0).label('total_invested'),
            func.coalesce(
                func.sum(PortfolioHolding.quantity * PortfolioHolding.avg_cost), 0
            ).label('total_cost'),
        ).one()

        stats = {
            'total_positions': int(totals.total_positions or 0),
            'total_invested': float(totals.total_invested or 0),
            'total_cost': float(totals.total_cost or 0),
        }

        # 按行业分布（保持原口径：invested 不做 COALESCE，全 NULL 时为 None）
        sector_expr = func.coalesce(PortfolioHolding.sector, '未知')
        sector_rows = self.session.query(
            sector_expr.label('sector'),
            func.count().label('count'),
            func.sum(PortfolioHolding.total_invested).label('invested'),
        ).group_by(sector_expr).order_by(
            func.sum(PortfolioHolding.total_invested).desc()
        ).all()
        stats['sector_distribution'] = [
            {'sector': r.sector, 'count': int(r.count), 'invested': r.invested}
            for r in sector_rows
        ]

        # 按市场分布
        market_rows = self.session.query(
            PortfolioHolding.market.label('market'),
            func.count().label('count'),
            func.sum(PortfolioHolding.total_invested).label('invested'),
        ).group_by(PortfolioHolding.market).order_by(
            func.sum(PortfolioHolding.total_invested).desc()
        ).all()
        stats['market_distribution'] = [
            {'market': r.market, 'count': int(r.count), 'invested': r.invested}
            for r in market_rows
        ]

        return stats

    def get_top_holdings(self, limit: int = 10) -> List[PortfolioHolding]:
        """获取投入金额最大的前N个持仓

        Args:
            limit: 返回数量

        Returns:
            PortfolioHolding对象列表
        """
        try:
            return self.session.query(PortfolioHolding).order_by(
                PortfolioHolding.total_invested.desc()
            ).limit(limit).all()

        except Exception as e:
            self._safe_rollback()
            logger.error(f"Error getting top holdings: {e}")
            return []

    def get_sectors(self) -> List[str]:
        """获取所有行业列表

        Returns:
            行业名称列表
        """
        try:
            result = self.session.query(PortfolioHolding.sector).distinct().filter(
                PortfolioHolding.sector.isnot(None)
            ).all()
            return [r[0] for r in result]

        except Exception as e:
            self._safe_rollback()
            logger.error(f"Error getting sectors: {e}")
            return []

    # ==================== 批量操作 ====================

    def batch_create_holdings(self, holdings: List[Dict]) -> int:
        """批量创建持仓

        Args:
            holdings: 持仓数据字典列表

        Returns:
            成功创建的数量
        """
        success_count = 0

        try:
            for holding_data in holdings:
                holding = PortfolioHolding(**holding_data)
                self.session.add(holding)
                success_count += 1

            self.session.commit()
            return success_count

        except Exception as e:
            logger.error(f"Error batch creating holdings: {e}")
            self.session.rollback()
            return success_count

    def batch_update_holdings(self, updates: List[Dict]) -> int:
        """批量更新持仓

        Args:
            updates: 更新数据列表，每项包含symbol和要更新的字段

        Returns:
            成功更新的数量
        """
        success_count = 0

        try:
            for update_data in updates:
                symbol = update_data.get('symbol')
                if not symbol:
                    continue

                holding = self._get_holding_model(symbol)
                if holding:
                    for key, value in update_data.items():
                        if key != 'symbol' and hasattr(holding, key):
                            setattr(holding, key, value)
                    success_count += 1

            self.session.commit()
            return success_count

        except Exception as e:
            logger.error(f"Error batch updating holdings: {e}")
            self.session.rollback()
            return success_count

    # ==================== 交易记录方法 ====================

    def get_trades(self, limit: int = 100, symbol: Optional[str] = None) -> List[Dict]:
        """获取交易记录列表

        Args:
            limit: 返回记录数量限制
            symbol: 可选的股票代码过滤

        Returns:
            交易记录字典列表
        """
        try:
            query = self.session.query(Trade).order_by(Trade.trade_date.desc(), Trade.id.desc())

            if symbol:
                query = query.filter(Trade.symbol == symbol)

            trades = query.limit(limit).all()
            return [trade.to_dict() for trade in trades]

        except Exception as e:
            self._safe_rollback()
            logger.error(f"Error getting trades: {e}")
            return []

    def get_trade_by_id(self, trade_id: int) -> Optional[Dict]:
        """根据ID获取交易记录

        Args:
            trade_id: 交易记录ID

        Returns:
            交易记录字典，不存在返回None
        """
        try:
            trade = self.session.query(Trade).filter_by(id=trade_id).first()
            return trade.to_dict() if trade else None

        except Exception as e:
            self._safe_rollback()
            logger.error(f"Error getting trade by id {trade_id}: {e}")
            return None

    def create_trade(self, trade_data: Dict) -> Optional[int]:
        """创建交易记录

        Args:
            trade_data: 交易数据字典

        Returns:
            创建成功返回交易ID，失败返回None
        """
        try:
            trade = Trade(**trade_data)
            self.session.add(trade)
            self.session.commit()
            return trade.id

        except Exception as e:
            logger.error(f"Error creating trade: {e}")
            self.session.rollback()
            return None

    def get_trades_by_order_id(self, order_id: int) -> List[Dict]:
        """根据订单ID获取交易记录

        Args:
            order_id: 订单ID

        Returns:
            交易记录字典列表
        """
        try:
            trades = self.session.query(Trade).filter_by(order_id=order_id).all()
            return [trade.to_dict() for trade in trades]

        except Exception as e:
            self._safe_rollback()
            logger.error(f"Error getting trades by order_id {order_id}: {e}")
            return []

    # ==================== 交易记录 (trades，旧契约恢复) ====================

    def get_trade(self, trade_id: int) -> Optional[Dict]:
        """查询单条交易记录，不存在返回 None"""
        trade = self.session.query(Trade).filter_by(id=trade_id).first()
        return self._trade_to_raw_dict(trade) if trade else None

    def get_trades_by_symbol(
        self,
        symbol: str,
        start_date: str = None,
        end_date: str = None
    ) -> List[Dict]:
        """查询指定股票的交易记录（按日期降序）"""
        _validate_symbol(symbol)

        query = self.session.query(Trade).filter(Trade.symbol == symbol)

        if start_date:
            _validate_date(start_date)
            query = query.filter(Trade.trade_date >= start_date)
        if end_date:
            _validate_date(end_date)
            query = query.filter(Trade.trade_date <= end_date)

        trades = query.order_by(
            Trade.trade_date.desc(), Trade.created_at.desc()
        ).all()
        return [self._trade_to_raw_dict(t) for t in trades]

    def get_trades_by_date(
        self,
        start_date: str,
        end_date: str,
        action: str = None
    ) -> List[Dict]:
        """按日期范围查询交易记录（可选按 buy/sell 筛选）"""
        _validate_date(start_date)
        _validate_date(end_date)

        query = self.session.query(Trade).filter(
            Trade.trade_date >= start_date, Trade.trade_date <= end_date
        )

        if action:
            if action not in ('buy', 'sell'):
                raise ValueError(f"无效的交易方向: {action}，必须是 buy 或 sell")
            query = query.filter(Trade.action == action)

        trades = query.order_by(
            Trade.trade_date.desc(), Trade.created_at.desc()
        ).all()
        return [self._trade_to_raw_dict(t) for t in trades]

    def get_trades_by_date_and_symbol(self, trade_date: date, symbol: str) -> List[Dict[str, Any]]:
        """按「交易日 + 标的」查交易记录（走 PostgreSQL 函数 quant.get_trades_by_date_and_symbol）。

        2026-09-14（REQ-24e15d）：原实现是 application/services/risk_check_service.py 里
        self.portfolio_repo._get_cursor() 拿裸 psycopg2 游标执行
        SELECT * FROM quant.get_trades_by_date_and_symbol(%s, %s)。该函数是 plpgsql
        （RETURNS TABLE(id, symbol, action, quantity, price, trade_date, created_at)，
        内部 WHERE trade_date = p_date AND symbol = p_symbol ORDER BY created_at DESC），
        **无法用 ORM 表达**，故按仓储契约在这里用 session.execute(text(...)) —— 仓储是放 SQL 的地方。
        取值一律绑定参数，不做任何插值。

        Args:
            trade_date: 交易日（datetime.date；与函数签名 p_date date 对齐）
            symbol: 标的代码（与 p_symbol varchar 对齐）

        Returns:
            行字典列表（键 = 函数的 RETURNS TABLE 列），顺序与函数内 ORDER BY 一致。
            无记录返回空列表（**不是 None**），调用方用 len() 计数。
        """
        from sqlalchemy import text

        rows = self.session.execute(
            text("SELECT * FROM quant.get_trades_by_date_and_symbol(:trade_date, :symbol)"),
            {"trade_date": trade_date, "symbol": symbol},
        ).fetchall()
        return [dict(row._mapping) for row in rows]

    def record_trade(self, trade_data: Dict) -> int:
        """
        记录一笔交易

        必需字段: symbol, name, action, price, quantity, amount, trade_date
        可选字段: fee, stamp_duty, reason, order_id

        Returns:
            新创建的交易ID
        """
        required_fields = ['symbol', 'name', 'action', 'price', 'quantity', 'amount', 'trade_date']
        for field in required_fields:
            if field not in trade_data:
                raise ValueError(f"缺少必需字段: {field}")

        if trade_data['action'] not in ('buy', 'sell'):
            raise ValueError(f"无效的交易方向: {trade_data['action']}")

        _validate_symbol(trade_data['symbol'])
        _validate_date(trade_data['trade_date'])

        # 只取模型已知列：旧裸 SQL 也只写这 11 列，多余键必须被忽略而不是 TypeError
        allowed = {c.name for c in Trade.__table__.columns} - {'id'}
        payload = {k: v for k, v in trade_data.items() if k in allowed}

        try:
            trade = Trade(**payload)
            self.session.add(trade)
            self.session.commit()
            return trade.id
        except Exception as e:
            self.session.rollback()
            raise Exception(f"记录交易失败: {str(e)}")

    def get_trade_stats(
        self,
        symbol: str = None,
        start_date: str = None,
        end_date: str = None
    ) -> Dict:
        """
        获取交易统计信息

        Returns:
            {total_trades, buy_trades, sell_trades, total_buy_amount,
             total_sell_amount, total_fee}
        """
        # ⚠️ 大小写修复：原 SQL 用 action = 'BUY'/'SELL'（大写）过滤，而
        # quant.trades 的 DB CHECK 约束强制小写，36 行存量数据全为 'buy'/'sell'
        # —— 导致本方法长期把 36 笔交易统计成「0 买 0 卖、买卖金额均为 0」
        # 且不报错（2026-09-14 实测复现）。此处按真库契约用小写。
        query = self.session.query(
            func.count().label('total_trades'),
            func.count().filter(Trade.action == 'buy').label('buy_trades'),
            func.count().filter(Trade.action == 'sell').label('sell_trades'),
            func.coalesce(
                func.sum(Trade.amount).filter(Trade.action == 'buy'), 0
            ).label('total_buy_amount'),
            func.coalesce(
                func.sum(Trade.amount).filter(Trade.action == 'sell'), 0
            ).label('total_sell_amount'),
            func.coalesce(func.sum(Trade.fee + Trade.stamp_duty), 0).label('total_fee'),
        )

        if symbol:
            _validate_symbol(symbol)
            query = query.filter(Trade.symbol == symbol)
        if start_date:
            _validate_date(start_date)
            query = query.filter(Trade.trade_date >= start_date)
        if end_date:
            _validate_date(end_date)
            query = query.filter(Trade.trade_date <= end_date)

        row = query.one()
        return {
            'total_trades': int(row.total_trades or 0),
            'buy_trades': int(row.buy_trades or 0),
            'sell_trades': int(row.sell_trades or 0),
            'total_buy_amount': float(row.total_buy_amount or 0),
            'total_sell_amount': float(row.total_sell_amount or 0),
            'total_fee': float(row.total_fee or 0),
        }

    # ==================== 持仓删除 ====================

    def remove_holding(self, symbol: str) -> bool:
        """删除持仓记录（order_service 清仓时调用）"""
        _validate_symbol(symbol)

        try:
            affected = self.session.query(PortfolioHolding).filter(
                PortfolioHolding.symbol == symbol
            ).delete(synchronize_session=False)
            self.session.commit()
            return affected > 0
        except Exception as e:
            self.session.rollback()
            raise Exception(f"删除持仓失败: {str(e)}")

