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

    @property
    def db(self):
        """向后兼容：返回一个支持 cursor() 方法的数据库连接对象

        用于执行原始 SQL 查询。新代码应使用 session 属性。

        返回一个包装对象，提供 cursor() 方法来获取 psycopg2 DictCursor。
        """
        class DBWrapper:
            def __init__(self, session):
                self._session = session

            def cursor(self):
                """返回一个 psycopg2 DictCursor，支持字典式访问"""
                from psycopg2.extras import RealDictCursor
                # 使用 SQLAlchemy 的 raw connection
                raw_conn = self._session.connection().connection
                return raw_conn.cursor(cursor_factory=RealDictCursor)

            def close(self):
                """兼容旧测试 teardown（self.repo.db.close()）。

                连接生命周期由 scoped session 统一管理，这里无需也不能
                单独关闭底层连接，否则会让 session 持有已关闭的连接。
                """

            def commit(self):
                self._session.commit()

            def rollback(self):
                self._session.rollback()

        return DBWrapper(self.session)

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
            logger.error(f"Error saving portfolio snapshot: {e}")
            return 0

    def _holding_to_dict(self, holding: PortfolioHolding) -> Dict[str, Any]:
        """将PortfolioHolding对象转换为字典（委托给 model.to_dict）"""
        return holding.to_dict()

    # ==================== 查询方法 ====================

    def _get_holding_model(self, symbol: str) -> Optional[PortfolioHolding]:
        """查询持仓 ORM 对象（内部使用：更新/删除场景）"""
        try:
            return self.session.query(PortfolioHolding).filter_by(
                symbol=symbol
            ).first()
        except Exception as e:
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
            logger.error(f"Error getting all holdings: {e}")
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
        query = """
            SELECT
                COUNT(*) as total_positions,
                COALESCE(SUM(total_invested), 0) as total_invested,
                COALESCE(SUM(quantity * avg_cost), 0) as total_cost
            FROM quant.portfolio_holdings
        """

        cursor = self.db.cursor()
        try:
            cursor.execute(query)
            result = cursor.fetchone()
            stats = dict(result) if result else {
                'total_positions': 0, 'total_invested': 0, 'total_cost': 0
            }
        finally:
            cursor.close()

        # 按行业分布
        cursor = self.db.cursor()
        try:
            cursor.execute("""
                SELECT COALESCE(sector, '未知') as sector, COUNT(*) as count,
                       SUM(total_invested) as invested
                FROM quant.portfolio_holdings
                GROUP BY sector
                ORDER BY invested DESC
            """)
            stats['sector_distribution'] = [dict(row) for row in cursor.fetchall()]
        finally:
            cursor.close()

        # 按市场分布
        cursor = self.db.cursor()
        try:
            cursor.execute("""
                SELECT market, COUNT(*) as count, SUM(total_invested) as invested
                FROM quant.portfolio_holdings
                GROUP BY market
                ORDER BY invested DESC
            """)
            stats['market_distribution'] = [dict(row) for row in cursor.fetchall()]
        finally:
            cursor.close()

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
            logger.error(f"Error getting trades by order_id {order_id}: {e}")
            return []

    # ==================== 订单管理 (orders) ====================
    # 注：8f06ae1 重构误删/误改了这组方法（get_orders 懒加载一个不存在的
    # Order model 导致永远返回 []；create_order/get_order/update_order_status
    # /cancel_order/get_pending_orders/get_order_stats 被删），但
    # order_service.py 与 routes/orders.py 仍在调用，下单/撤单功能实际
    # 已损坏。此处按旧契约恢复（raw SQL + dict 返回）。

    _ORDER_VALID_STATUSES = ('pending', 'partial', 'filled', 'cancelled', 'expired')
    _ORDER_VALID_TYPES = ('limit', 'market', 'stop')

    def get_order(self, order_id: int) -> Optional[Dict]:
        """查询单条订单，不存在返回 None"""
        query = "SELECT * FROM quant.orders WHERE id = %s"

        cursor = self.db.cursor()
        try:
            cursor.execute(query, (order_id,))
            result = cursor.fetchone()
            return dict(result) if result else None
        finally:
            cursor.close()

    def get_order_by_id(self, order_id: int) -> Optional[Dict]:
        """get_order 别名（兼容 API 调用）"""
        return self.get_order(order_id)

    def get_orders(
        self,
        symbol: str = None,
        status: str = None,
        limit: int = 100
    ) -> List[Dict]:
        """查询订单列表（按创建时间降序）"""
        conditions = []
        params = []

        if symbol:
            _validate_symbol(symbol)
            conditions.append("symbol = %s")
            params.append(symbol)
        if status:
            if status not in self._ORDER_VALID_STATUSES:
                raise ValueError(
                    f"无效的订单状态: {status}，"
                    f"必须是 {', '.join(self._ORDER_VALID_STATUSES)}"
                )
            conditions.append("status = %s")
            params.append(status)

        where_clause = " AND ".join(conditions) if conditions else "1=1"

        query = f"""
            SELECT *
            FROM quant.orders
            WHERE {where_clause}
            ORDER BY created_at DESC
            LIMIT %s
        """
        params.append(limit)

        cursor = self.db.cursor()
        try:
            cursor.execute(query, params)
            results = cursor.fetchall()
            return [dict(row) for row in results]
        finally:
            cursor.close()

    def get_pending_orders(self) -> List[Dict]:
        """获取所有待处理订单"""
        return self.get_orders(status='pending', limit=1000)

    def create_order(self, order_data: Dict) -> int:
        """
        创建新订单

        必需字段: symbol, name, order_type, action, quantity, status
        可选字段: price, filled_quantity, avg_filled_price, reason,
                 signal_id, expires_at

        Returns:
            新创建的订单ID
        """
        required_fields = ['symbol', 'name', 'order_type', 'action', 'quantity', 'status']
        for field in required_fields:
            if field not in order_data:
                raise ValueError(f"缺少必需字段: {field}")

        if order_data['order_type'] not in self._ORDER_VALID_TYPES:
            raise ValueError(f"无效的订单类型: {order_data['order_type']}")

        if order_data['action'] not in ('buy', 'sell'):
            raise ValueError(f"无效的订单方向: {order_data['action']}")

        if order_data['status'] not in self._ORDER_VALID_STATUSES:
            raise ValueError(f"无效的订单状态: {order_data['status']}")

        _validate_symbol(order_data['symbol'])

        query = """
            INSERT INTO quant.orders (
                symbol, name, order_type, action, price, quantity, status,
                filled_quantity, avg_filled_price, reason, signal_id, expires_at
            ) VALUES (
                %(symbol)s, %(name)s, %(order_type)s, %(action)s, %(price)s, %(quantity)s, %(status)s,
                %(filled_quantity)s, %(avg_filled_price)s, %(reason)s, %(signal_id)s, %(expires_at)s
            )
            RETURNING id
        """

        cursor = self.db.cursor()
        try:
            cursor.execute(query, order_data)
            order_id = cursor.fetchone()['id']
            self.db.commit()
            return order_id
        except Exception as e:
            self.db.rollback()
            raise Exception(f"创建订单失败: {str(e)}")
        finally:
            cursor.close()

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
        创建订单（兼容旧的风控参数签名）

        注意：当前 quant.orders 表已无 stop_loss_price / take_profit_price /
        parent_order_id / order_group / risk_params 列（多账户改造后移除），
        这些参数被接受但不落库。OCO 订单组能力待 schema 迁移恢复。

        Returns:
            订单 ID
        """
        from datetime import datetime, timedelta

        if expires_at is None:
            expires_at = (datetime.now() + timedelta(days=7)).strftime('%Y-%m-%d %H:%M:%S')

        query = """
            INSERT INTO quant.orders (
                symbol, name, action, order_type, quantity, price, status,
                filled_quantity, reason, signal_id, expires_at, created_at
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW()
            ) RETURNING id
        """

        cursor = self.db.cursor()
        try:
            cursor.execute(query, (
                symbol, name, action, order_type, quantity, price, status,
                0, reason, signal_id, expires_at
            ))
            result = cursor.fetchone()
            order_id = result['id'] if result else None
            self.db.commit()
            return order_id
        except Exception as e:
            self.db.rollback()
            raise Exception(f"创建订单失败: {str(e)}")
        finally:
            cursor.close()

    def update_order_status(
        self,
        order_id: int,
        status: str,
        filled_quantity: int = None,
        avg_filled_price: float = None
    ) -> bool:
        """更新订单状态（可选同时更新成交数量/均价）"""
        if status not in self._ORDER_VALID_STATUSES:
            raise ValueError(f"无效的订单状态: {status}")

        set_clauses = ["status = %s", "updated_at = CURRENT_TIMESTAMP"]
        params = [status]

        if filled_quantity is not None:
            set_clauses.append("filled_quantity = %s")
            params.append(filled_quantity)
        if avg_filled_price is not None:
            set_clauses.append("avg_filled_price = %s")
            params.append(avg_filled_price)

        params.append(order_id)

        query = f"""
            UPDATE quant.orders
            SET {', '.join(set_clauses)}
            WHERE id = %s
        """

        cursor = self.db.cursor()
        try:
            cursor.execute(query, params)
            self.db.commit()
            affected = cursor.rowcount
            return affected > 0
        except Exception as e:
            self.db.rollback()
            raise Exception(f"更新订单状态失败: {str(e)}")
        finally:
            cursor.close()

    def cancel_order(self, order_id: int) -> bool:
        """取消订单"""
        return self.update_order_status(order_id, 'cancelled')

    def get_order_stats(self, symbol: str = None) -> Dict:
        """
        获取订单统计信息

        Returns:
            {total_orders, pending, partial, filled, cancelled, expired,
             limit_orders, market_orders, stop_orders}
        """
        conditions = []
        params = []

        if symbol:
            _validate_symbol(symbol)
            conditions.append("symbol = %s")
            params.append(symbol)

        where_clause = " AND ".join(conditions) if conditions else "1=1"

        query = f"""
            SELECT
                COUNT(*) as total_orders,
                COUNT(*) FILTER (WHERE status = 'pending') as pending,
                COUNT(*) FILTER (WHERE status = 'partial') as partial,
                COUNT(*) FILTER (WHERE status = 'filled') as filled,
                COUNT(*) FILTER (WHERE status = 'cancelled') as cancelled,
                COUNT(*) FILTER (WHERE status = 'expired') as expired,
                COUNT(*) FILTER (WHERE order_type = 'limit') as limit_orders,
                COUNT(*) FILTER (WHERE order_type = 'market') as market_orders,
                COUNT(*) FILTER (WHERE order_type = 'stop') as stop_orders
            FROM quant.orders
            WHERE {where_clause}
        """

        cursor = self.db.cursor()
        try:
            cursor.execute(query, params)
            result = cursor.fetchone()
            return dict(result) if result else {}
        finally:
            cursor.close()

    # ==================== 交易记录 (trades，旧契约恢复) ====================

    def get_trade(self, trade_id: int) -> Optional[Dict]:
        """查询单条交易记录，不存在返回 None"""
        query = "SELECT * FROM quant.trades WHERE id = %s"

        cursor = self.db.cursor()
        try:
            cursor.execute(query, (trade_id,))
            result = cursor.fetchone()
            return dict(result) if result else None
        finally:
            cursor.close()

    def get_trades_by_symbol(
        self,
        symbol: str,
        start_date: str = None,
        end_date: str = None
    ) -> List[Dict]:
        """查询指定股票的交易记录（按日期降序）"""
        _validate_symbol(symbol)

        conditions = ["symbol = %s"]
        params = [symbol]

        if start_date:
            _validate_date(start_date)
            conditions.append("trade_date >= %s")
            params.append(start_date)
        if end_date:
            _validate_date(end_date)
            conditions.append("trade_date <= %s")
            params.append(end_date)

        where_clause = " AND ".join(conditions)

        query = f"""
            SELECT *
            FROM quant.trades
            WHERE {where_clause}
            ORDER BY trade_date DESC, created_at DESC
        """

        cursor = self.db.cursor()
        try:
            cursor.execute(query, params)
            results = cursor.fetchall()
            return [dict(row) for row in results]
        finally:
            cursor.close()

    def get_trades_by_date(
        self,
        start_date: str,
        end_date: str,
        action: str = None
    ) -> List[Dict]:
        """按日期范围查询交易记录（可选按 buy/sell 筛选）"""
        _validate_date(start_date)
        _validate_date(end_date)

        conditions = ["trade_date >= %s", "trade_date <= %s"]
        params = [start_date, end_date]

        if action:
            if action not in ('buy', 'sell'):
                raise ValueError(f"无效的交易方向: {action}，必须是 buy 或 sell")
            conditions.append("action = %s")
            params.append(action)

        where_clause = " AND ".join(conditions)

        query = f"""
            SELECT *
            FROM quant.trades
            WHERE {where_clause}
            ORDER BY trade_date DESC, created_at DESC
        """

        cursor = self.db.cursor()
        try:
            cursor.execute(query, params)
            results = cursor.fetchall()
            return [dict(row) for row in results]
        finally:
            cursor.close()

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

        query = """
            INSERT INTO quant.trades (
                symbol, name, action, price, quantity, amount,
                fee, stamp_duty, trade_date, reason, order_id
            ) VALUES (
                %(symbol)s, %(name)s, %(action)s, %(price)s, %(quantity)s, %(amount)s,
                %(fee)s, %(stamp_duty)s, %(trade_date)s, %(reason)s, %(order_id)s
            )
            RETURNING id
        """

        cursor = self.db.cursor()
        try:
            cursor.execute(query, trade_data)
            trade_id = cursor.fetchone()['id']
            self.db.commit()
            return trade_id
        except Exception as e:
            self.db.rollback()
            raise Exception(f"记录交易失败: {str(e)}")
        finally:
            cursor.close()

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
        conditions = []
        params = []

        if symbol:
            _validate_symbol(symbol)
            conditions.append("symbol = %s")
            params.append(symbol)
        if start_date:
            _validate_date(start_date)
            conditions.append("trade_date >= %s")
            params.append(start_date)
        if end_date:
            _validate_date(end_date)
            conditions.append("trade_date <= %s")
            params.append(end_date)

        where_clause = " AND ".join(conditions) if conditions else "1=1"

        query = f"""
            SELECT
                COUNT(*) as total_trades,
                COUNT(*) FILTER (WHERE action = 'buy') as buy_trades,
                COUNT(*) FILTER (WHERE action = 'sell') as sell_trades,
                COALESCE(SUM(amount) FILTER (WHERE action = 'buy'), 0) as total_buy_amount,
                COALESCE(SUM(amount) FILTER (WHERE action = 'sell'), 0) as total_sell_amount,
                COALESCE(SUM(fee + stamp_duty), 0) as total_fee
            FROM quant.trades
            WHERE {where_clause}
        """

        cursor = self.db.cursor()
        try:
            cursor.execute(query, params)
            result = cursor.fetchone()
            return dict(result) if result else {}
        finally:
            cursor.close()

    # ==================== 持仓删除 ====================

    def remove_holding(self, symbol: str) -> bool:
        """删除持仓记录（order_service 清仓时调用）"""
        _validate_symbol(symbol)

        query = "DELETE FROM quant.portfolio_holdings WHERE symbol = %s"

        cursor = self.db.cursor()
        try:
            cursor.execute(query, (symbol,))
            self.db.commit()
            affected = cursor.rowcount
            return affected > 0
        except Exception as e:
            self.db.rollback()
            raise Exception(f"删除持仓失败: {str(e)}")
        finally:
            cursor.close()

