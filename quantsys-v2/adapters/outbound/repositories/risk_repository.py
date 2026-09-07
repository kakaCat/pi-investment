"""
风险管理ORM Repository

迁移状态：✅ 已完成ORM迁移
"""
from typing import List, Optional, Dict, Any
from datetime import date, datetime, timedelta
import structlog

from sqlalchemy import desc, func
from infrastructure.persistence.orm import BaseORMRepository, get_session
from sqlalchemy import Column, Integer, String, Float, Date, Text, BigInteger, DateTime
from sqlalchemy.dialects.postgresql import JSONB
from infrastructure.persistence.orm.base import Base

logger = structlog.get_logger(__name__)


class RiskMetric(Base):
    """风险指标 Model —— 与 quant.risk_metrics 真实宽表对齐

    注：8f06ae1 重构曾把本 Model 错建成 EAV 结构（metric_name/metric_value），
    与真实表（volatility/beta/var_95/... 宽列）不符，导致所有风险指标
    查询返回空。此处恢复为真实表结构。
    """
    __tablename__ = 'risk_metrics'
    __table_args__ = {'schema': 'quant'}

    id = Column(BigInteger, primary_key=True)
    metric_date = Column(Date)
    symbol = Column(String(20))
    volatility = Column(Float)
    beta = Column(Float)
    var_95 = Column(Float)
    cvar_95 = Column(Float)
    max_position_ratio = Column(Float)
    concentration_risk = Column(Float)
    sector_exposure = Column(JSONB)
    correlation_matrix = Column(JSONB)
    created_at = Column(DateTime(timezone=True))


class AccountBalance(Base):
    __tablename__ = 'account_balance'
    __table_args__ = {'schema': 'quant'}

    id = Column(BigInteger, primary_key=True)
    balance_date = Column(Date, nullable=False, unique=True)
    cash = Column(Float, nullable=False)
    market_value = Column(Float, nullable=False)
    total_assets = Column(Float, nullable=False)
    daily_pnl = Column(Float)
    daily_return = Column(Float)
    total_pnl = Column(Float)
    total_return = Column(Float)
    position_count = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True))


class StopLossRule(Base):
    __tablename__ = 'stop_loss_rules'
    __table_args__ = {'schema': 'quant'}

    id = Column(String, primary_key=True)
    symbol = Column(String, nullable=False)
    name = Column(String, nullable=False)
    type = Column(String, nullable=False)
    stop_loss_percent = Column(Float)
    trailing_percent = Column(Float)
    atr_multiplier = Column(Float)
    status = Column(String, nullable=False, default='active')
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now())


_STOP_LOSS_TYPES = ('fixed_price', 'fixed_percent', 'trailing_stop')
_STOP_LOSS_STATUSES = ('active', 'inactive', 'triggered')


def _validate_symbol(symbol: str) -> bool:
    """校验股票代码格式（对齐旧 BaseRepository._validate_symbol 行为）"""
    if not symbol:
        raise ValueError("股票代码不能为空")
    if not isinstance(symbol, str):
        raise ValueError("股票代码必须是字符串")

    base = symbol.strip().upper()
    for suffix in (".SZ", ".SH", ".HK"):
        if base.endswith(suffix):
            base = base[: -len(suffix)]
            break

    if not base.isdigit() or not (4 <= len(base) <= 6):
        raise ValueError(f"股票代码格式错误: {symbol}")
    return True


def _validate_date(date_str: str) -> bool:
    """校验日期格式 YYYY-MM-DD（对齐旧 BaseRepository._validate_date 行为）"""
    if not date_str:
        raise ValueError("Date cannot be empty")
    try:
        datetime.strptime(date_str, "%Y-%m-%d")
        return True
    except ValueError:
        raise ValueError(f"Invalid date format: {date_str}, expected YYYY-MM-DD")


def _stop_loss_rule_to_dict(rule: StopLossRule) -> Dict[str, Any]:
    return {
        'id': rule.id,
        'symbol': rule.symbol,
        'name': rule.name,
        'type': rule.type,
        'stop_loss_percent': rule.stop_loss_percent,
        'trailing_percent': rule.trailing_percent,
        'atr_multiplier': rule.atr_multiplier,
        'status': rule.status,
        'created_at': rule.created_at,
        'updated_at': rule.updated_at,
    }

from domain.ports import IRiskRepository

class RiskORMRepository(BaseORMRepository[RiskMetric], IRiskRepository):
    """风险管理ORM Repository"""
    model = RiskMetric

    @property
    def db(self):
        """向后兼容：返回支持 cursor()/commit()/rollback() 的连接包装器

        恢复的账户资金/风险指标方法沿用旧的 raw SQL 实现（SELECT * 契约），
        cursor 来自 session 绑定的同一事务，commit/rollback 委托给 session。
        """
        class DBWrapper:
            def __init__(self, session):
                self._session = session

            def cursor(self):
                from psycopg2.extras import RealDictCursor
                raw_conn = self._session.connection().connection
                return raw_conn.cursor(cursor_factory=RealDictCursor)

            def commit(self):
                self._session.commit()

            def rollback(self):
                self._session.rollback()

            def close(self):
                """兼容旧测试 teardown；连接由 scoped session 统一管理"""

        return DBWrapper(self.session)

    # ==================== 账户资金 (account_balance) ====================

    def get_balance(self, balance_date: str) -> Optional[Dict]:
        """查询指定日期的账户资金"""
        _validate_date(balance_date)

        query = "SELECT * FROM quant.account_balance WHERE balance_date = %s"

        cursor = self.db.cursor()
        try:
            cursor.execute(query, (balance_date,))
            result = cursor.fetchone()
            return dict(result) if result else None
        finally:
            cursor.close()

    def get_balance_by_date(self, balance_date: str) -> Optional[Dict]:
        """get_balance 别名（兼容旧调用）"""
        return self.get_balance(balance_date)

    def get_balance_history(
        self,
        start_date: str,
        end_date: str
    ) -> List[Dict]:
        """查询账户资金历史（按日期升序）"""
        _validate_date(start_date)
        _validate_date(end_date)

        query = """
            SELECT *
            FROM quant.account_balance
            WHERE balance_date >= %s
              AND balance_date <= %s
            ORDER BY balance_date ASC
        """

        cursor = self.db.cursor()
        try:
            cursor.execute(query, (start_date, end_date))
            results = cursor.fetchall()
            return [dict(row) for row in results]
        finally:
            cursor.close()

    def save_balance(self, balance_data: Dict) -> bool:
        """
        保存账户资金快照（UPSERT）

        必需字段: balance_date, cash, market_value, total_assets
        可选字段: daily_pnl, daily_return, total_pnl, total_return, position_count
        """
        required_fields = ['balance_date', 'cash', 'market_value', 'total_assets']
        for field in required_fields:
            if field not in balance_data:
                raise ValueError(f"缺少必需字段: {field}")

        _validate_date(balance_data['balance_date'])

        query = """
            INSERT INTO quant.account_balance (
                balance_date, cash, market_value, total_assets,
                daily_pnl, daily_return, total_pnl, total_return, position_count
            ) VALUES (
                %(balance_date)s, %(cash)s, %(market_value)s, %(total_assets)s,
                %(daily_pnl)s, %(daily_return)s, %(total_pnl)s, %(total_return)s,
                %(position_count)s
            )
            ON CONFLICT (balance_date)
            DO UPDATE SET
                cash = EXCLUDED.cash,
                market_value = EXCLUDED.market_value,
                total_assets = EXCLUDED.total_assets,
                daily_pnl = EXCLUDED.daily_pnl,
                daily_return = EXCLUDED.daily_return,
                total_pnl = EXCLUDED.total_pnl,
                total_return = EXCLUDED.total_return,
                position_count = EXCLUDED.position_count
        """

        cursor = self.db.cursor()
        try:
            cursor.execute(query, balance_data)
            self.db.commit()
            return True
        except Exception as e:
            self.db.rollback()
            raise Exception(f"保存账户资金失败: {str(e)}") from e
        finally:
            cursor.close()

    def get_balance_stats(self, start_date: str, end_date: str) -> Dict:
        """
        获取账户资金统计信息

        Returns:
            {max_assets, min_assets, total_pnl, asset_range,
             avg_daily_return, std_daily_return, max_drawdown}
        """
        _validate_date(start_date)
        _validate_date(end_date)

        query = """
            SELECT
                MAX(total_assets) as max_assets,
                MIN(total_assets) as min_assets,
                COALESCE(SUM(daily_pnl), 0) as total_pnl,
                MAX(total_assets) - MIN(total_assets) as asset_range,
                AVG(daily_return) as avg_daily_return,
                STDDEV(daily_return) as std_daily_return
            FROM quant.account_balance
            WHERE balance_date >= %s
              AND balance_date <= %s
        """

        cursor = self.db.cursor()
        try:
            cursor.execute(query, (start_date, end_date))
            result = cursor.fetchone()
            stats = dict(result) if result else {}
        finally:
            cursor.close()

        # 计算最大回撤 (从峰值到谷底的最大跌幅)
        cursor = self.db.cursor()
        try:
            cursor.execute("""
                SELECT total_assets
                FROM quant.account_balance
                WHERE balance_date >= %s AND balance_date <= %s
                ORDER BY balance_date ASC
            """, (start_date, end_date))
            assets = [row['total_assets'] for row in cursor.fetchall()]
        finally:
            cursor.close()

        if assets:
            peak = assets[0]
            max_drawdown = 0.0
            for value in assets:
                if value > peak:
                    peak = value
                drawdown = (peak - value) / peak if peak > 0 else 0
                if drawdown > max_drawdown:
                    max_drawdown = drawdown
            stats['max_drawdown'] = max_drawdown

        return stats

    # ==================== 风险指标 (risk_metrics) ====================

    def get_risk_metrics(
        self,
        symbol: str = None,
        metric_date: str = None
    ) -> Optional[Dict]:
        """
        查询风险指标（单条）

        Args:
            symbol: 股票代码 (可选)
            metric_date: 日期 (可选)
            两者至少提供一个

        Returns:
            最新一条匹配记录（dict），无记录返回 None
        """
        if not symbol and not metric_date:
            raise ValueError("symbol和metric_date至少需要提供一个")

        conditions = []
        params = []

        if symbol:
            _validate_symbol(symbol)
            conditions.append("symbol = %s")
            params.append(symbol)
        if metric_date:
            _validate_date(metric_date)
            conditions.append("metric_date = %s")
            params.append(metric_date)

        where_clause = " AND ".join(conditions)

        query = """
            SELECT *
            FROM quant.risk_metrics
            WHERE """ + where_clause + """
            ORDER BY metric_date DESC
            LIMIT 1
        """

        cursor = self.db.cursor()
        try:
            cursor.execute(query, params)
            result = cursor.fetchone()
            return dict(result) if result else None
        finally:
            cursor.close()

    def get_risk_history(
        self,
        symbol: str = None,
        start_date: str = None,
        end_date: str = None
    ) -> List[Dict]:
        """查询风险指标历史（按日期降序）"""
        conditions = []
        params = []

        if symbol:
            _validate_symbol(symbol)
            conditions.append("symbol = %s")
            params.append(symbol)
        if start_date:
            _validate_date(start_date)
            conditions.append("metric_date >= %s")
            params.append(start_date)
        if end_date:
            _validate_date(end_date)
            conditions.append("metric_date <= %s")
            params.append(end_date)

        where_clause = " AND ".join(conditions) if conditions else "1=1"

        query = """
            SELECT *
            FROM quant.risk_metrics
            WHERE """ + where_clause + """
            ORDER BY metric_date DESC, symbol ASC
        """

        cursor = self.db.cursor()
        try:
            cursor.execute(query, params)
            results = cursor.fetchall()
            return [dict(row) for row in results]
        finally:
            cursor.close()

    def get_risk_stats(self, symbol: str = None, start_date: str = None, end_date: str = None) -> Dict:
        """
        获取风险统计信息

        Returns:
            {total_records, avg_volatility, avg_var_95, avg_cvar_95,
             avg_beta, max_concentration}
        """
        conditions = []
        params = []

        if symbol:
            _validate_symbol(symbol)
            conditions.append("symbol = %s")
            params.append(symbol)
        if start_date:
            _validate_date(start_date)
            conditions.append("metric_date >= %s")
            params.append(start_date)
        if end_date:
            _validate_date(end_date)
            conditions.append("metric_date <= %s")
            params.append(end_date)

        where_clause = " AND ".join(conditions) if conditions else "1=1"

        query = """
            SELECT
                COUNT(*) as total_records,
                AVG(volatility) as avg_volatility,
                AVG(var_95) as avg_var_95,
                AVG(cvar_95) as avg_cvar_95,
                AVG(beta) as avg_beta,
                MAX(concentration_risk) as max_concentration
            FROM quant.risk_metrics
            WHERE """ + where_clause

        cursor = self.db.cursor()
        try:
            cursor.execute(query, params)
            result = cursor.fetchone()
            return dict(result) if result else {}
        finally:
            cursor.close()

    def save_risk_metrics(self, metrics_data: Dict) -> bool:
        """
        保存风险指标（UPSERT）

        必需字段: metric_date, symbol
        可选字段: volatility, beta, var_95, cvar_95, max_position_ratio,
                 concentration_risk, sector_exposure, correlation_matrix
        """
        import json as _json

        required_fields = ['metric_date', 'symbol']
        for field in required_fields:
            if field not in metrics_data:
                raise ValueError(f"缺少必需字段: {field}")

        _validate_date(metrics_data['metric_date'])
        _validate_symbol(metrics_data['symbol'])

        # 处理JSONB字段
        for json_field in ['sector_exposure', 'correlation_matrix']:
            if json_field in metrics_data and isinstance(metrics_data[json_field], (dict, list)):
                metrics_data[json_field] = _json.dumps(metrics_data[json_field])

        query = """
            INSERT INTO quant.risk_metrics (
                metric_date, symbol, volatility, beta, var_95, cvar_95,
                max_position_ratio, concentration_risk, sector_exposure, correlation_matrix
            ) VALUES (
                %(metric_date)s, %(symbol)s, %(volatility)s, %(beta)s, %(var_95)s, %(cvar_95)s,
                %(max_position_ratio)s, %(concentration_risk)s, %(sector_exposure)s, %(correlation_matrix)s
            )
            ON CONFLICT (metric_date, symbol)
            DO UPDATE SET
                volatility = EXCLUDED.volatility,
                beta = EXCLUDED.beta,
                var_95 = EXCLUDED.var_95,
                cvar_95 = EXCLUDED.cvar_95,
                max_position_ratio = EXCLUDED.max_position_ratio,
                concentration_risk = EXCLUDED.concentration_risk,
                sector_exposure = EXCLUDED.sector_exposure,
                correlation_matrix = EXCLUDED.correlation_matrix
        """

        cursor = self.db.cursor()
        try:
            cursor.execute(query, metrics_data)
            self.db.commit()
            return True
        except Exception as e:
            self.db.rollback()
            raise Exception(f"保存风险指标失败: {str(e)}") from e
        finally:
            cursor.close()

    def get_history(self, days: int = 30) -> List[Dict[str, Any]]:
        """获取账户余额历史记录

        Args:
            days: 查询的天数，默认30天

        Returns:
            账户余额历史记录列表，按日期升序排列
        """
        try:
            end_date = datetime.now().date()
            start_date = end_date - timedelta(days=days)

            query = self.session.query(AccountBalance).filter(
                AccountBalance.balance_date >= start_date,
                AccountBalance.balance_date <= end_date
            ).order_by(AccountBalance.balance_date.asc())

            balances = query.all()
            return [{
                'balance_date': b.balance_date,
                'cash': b.cash,
                'market_value': b.market_value,
                'total_assets': b.total_assets,
                'daily_pnl': b.daily_pnl,
                'daily_return': b.daily_return,
                'total_pnl': b.total_pnl,
                'total_return': b.total_return,
                'position_count': b.position_count,
            } for b in balances]

        except Exception as e:
            self._safe_rollback()
            logger.error(f"Error getting account balance history: {e}", exc_info=True)
            return []

    def get_latest_balance(self) -> Optional[Dict[str, Any]]:
        """获取最新的账户余额记录

        Returns:
            最新的账户余额记录，如果没有记录则返回None
        """
        try:
            balance = self.session.query(AccountBalance).order_by(
                AccountBalance.balance_date.desc()
            ).first()

            if not balance:
                return None

            return {
                'balance_date': balance.balance_date,
                'cash': balance.cash,
                'market_value': balance.market_value,
                'total_assets': balance.total_assets,
                'daily_pnl': balance.daily_pnl,
                'daily_return': balance.daily_return,
                'total_pnl': balance.total_pnl,
                'total_return': balance.total_return,
                'position_count': balance.position_count,
                'created_at': balance.created_at,
            }

        except Exception as e:
            self._safe_rollback()
            logger.error(f"Error getting latest balance: {e}", exc_info=True)
            return None

    def get_latest_risk_metrics(self, symbol: str) -> Optional[Dict[str, Any]]:
        """获取指定股票的最新风险指标（宽表整行）

        注：8f06ae1 重构期间本方法曾按不存在的 EAV 结构
        （metric_name/metric_value）查询，对真实宽表永远返回空，
        导致 /api/risk/check 的 var_95 恒为 0。此处恢复旧契约。
        """
        _validate_symbol(symbol)

        query = """
            SELECT *
            FROM quant.risk_metrics
            WHERE symbol = %s
            ORDER BY metric_date DESC
            LIMIT 1
        """

        cursor = self.db.cursor()
        try:
            cursor.execute(query, (symbol,))
            result = cursor.fetchone()
            return dict(result) if result else None
        except Exception as e:
            self._safe_rollback()
            logger.error(f"Error getting latest risk metrics for {symbol}: {e}", exc_info=True)
            return None
        finally:
            cursor.close()

    # ==================== 止损规则 (stop_loss_rules) ====================
    # 注：8f06ae1 DDD 重构误删了这组方法，但 routes/risk.py 与
    # fastapi_app/routes/risk_async.py 仍在调用，导致止损规则接口 500。
    # 此处按 ORM 风格恢复，保持原有方法签名与返回形状（dict）。

    def list_stop_loss_rules(
        self,
        symbol: str = None,
        status: str = None
    ) -> List[Dict]:
        """
        查询止损规则列表

        Args:
            symbol: 股票代码 (可选，不传则查所有)
            status: 状态过滤 (active/inactive/triggered，可选)

        Returns:
            止损规则列表（dict）
        """
        if symbol:
            _validate_symbol(symbol)
        if status and status not in _STOP_LOSS_STATUSES:
            raise ValueError(f"无效的状态值: {status}")

        query = self.session.query(StopLossRule)
        if symbol:
            query = query.filter(StopLossRule.symbol == symbol)
        if status:
            query = query.filter(StopLossRule.status == status)

        rules = query.order_by(StopLossRule.created_at.desc()).all()
        return [_stop_loss_rule_to_dict(r) for r in rules]

    def get_stop_loss_rule(self, rule_id: str) -> Optional[Dict]:
        """
        查询单个止损规则

        Args:
            rule_id: 规则ID

        Returns:
            止损规则详情（dict），不存在返回 None
        """
        rule = self.session.query(StopLossRule).get(rule_id)
        return _stop_loss_rule_to_dict(rule) if rule else None

    def create_stop_loss_rule(self, rule_data: Dict) -> str:
        """
        创建止损规则

        Args:
            rule_data: 规则数据
                必需字段: id, symbol, name, type
                可选字段: stop_loss_percent, trailing_percent, atr_multiplier, status

        Returns:
            创建的规则ID
        """
        required_fields = ['id', 'symbol', 'name', 'type']
        for field in required_fields:
            if field not in rule_data:
                raise ValueError(f"缺少必需字段: {field}")

        _validate_symbol(rule_data['symbol'])

        if rule_data['type'] not in _STOP_LOSS_TYPES:
            raise ValueError(f"无效的规则类型: {rule_data['type']}")

        rule = StopLossRule(
            id=rule_data['id'],
            symbol=rule_data['symbol'],
            name=rule_data['name'],
            type=rule_data['type'],
            stop_loss_percent=rule_data.get('stop_loss_percent'),
            trailing_percent=rule_data.get('trailing_percent'),
            atr_multiplier=rule_data.get('atr_multiplier'),
            status=rule_data.get('status') or 'active',
        )

        try:
            self.session.add(rule)
            self.session.commit()
            return rule.id
        except Exception as e:
            self.session.rollback()
            raise Exception(f"创建止损规则失败: {str(e)}") from e

    def update_stop_loss_rule(self, rule_id: str, rule_data: Dict) -> bool:
        """
        更新止损规则

        Args:
            rule_id: 规则ID
            rule_data: 要更新的字段（name/type/stop_loss_percent/
                       trailing_percent/atr_multiplier/status）

        Returns:
            是否成功
        """
        allowed_fields = [
            'name', 'type', 'stop_loss_percent', 'trailing_percent',
            'atr_multiplier', 'status'
        ]

        updates = {f: rule_data[f] for f in allowed_fields if f in rule_data}
        if not updates:
            return True

        rule = self.session.query(StopLossRule).get(rule_id)
        if not rule:
            return False

        for field, value in updates.items():
            setattr(rule, field, value)
        rule.updated_at = datetime.now()

        try:
            self.session.commit()
            return True
        except Exception as e:
            self.session.rollback()
            raise Exception(f"更新止损规则失败: {str(e)}") from e

    def delete_stop_loss_rule(self, rule_id: str) -> bool:
        """
        删除止损规则

        Args:
            rule_id: 规则ID

        Returns:
            是否成功
        """
        rule = self.session.query(StopLossRule).get(rule_id)
        if not rule:
            return False

        try:
            self.session.delete(rule)
            self.session.commit()
            return True
        except Exception as e:
            self.session.rollback()
            raise Exception(f"删除止损规则失败: {str(e)}") from e
