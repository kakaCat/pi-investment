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
from infrastructure.persistence.orm.base import Base

logger = structlog.get_logger(__name__)

# 临时Model定义
class RiskMetric(Base):
    __tablename__ = 'risk_metrics'
    __table_args__ = {'schema': 'quant'}

    id = Column(BigInteger, primary_key=True)
    symbol = Column(String(20))
    metric_date = Column(Date)
    metric_name = Column(String(50))
    metric_value = Column(Float)


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

    def get_risk_metrics(
        self,
        symbol: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """获取风险指标（IRiskRepository接口实现）"""
        try:
            query = self.session.query(RiskMetric)

            if symbol:
                query = query.filter(RiskMetric.symbol == symbol)
            if start_date:
                query = query.filter(RiskMetric.metric_date >= start_date)
            if end_date:
                query = query.filter(RiskMetric.metric_date <= end_date)

            metrics = query.all()
            return [{
                'id': m.id,
                'symbol': m.symbol,
                'metric_date': m.metric_date.isoformat() if m.metric_date else None,
                'metric_name': m.metric_name,
                'metric_value': m.metric_value,
            } for m in metrics]

        except Exception as e:
            logger.error(f"Error getting risk metrics: {e}")
            return []

    def save_risk_metrics(self, metrics: Dict[str, Any]) -> int:
        """保存风险指标（IRiskRepository接口实现）"""
        try:
            metric = RiskMetric(
                symbol=metrics.get('symbol'),
                metric_date=metrics.get('metric_date'),
                metric_name=metrics.get('metric_name'),
                metric_value=metrics.get('metric_value'),
            )
            self.session.add(metric)
            self.session.commit()
            return metric.id if metric.id else 0

        except Exception as e:
            logger.error(f"Error saving risk metrics: {e}")
            self.session.rollback()
            return 0

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
            logger.error(f"Error getting latest balance: {e}", exc_info=True)
            return None

    def get_latest_risk_metrics(self, symbol: str) -> Optional[Dict[str, Any]]:
        """获取指定股票的最新风险指标

        Args:
            symbol: 股票代码

        Returns:
            最新的风险指标记录，如果没有记录则返回None
        """
        try:
            # 查询该股票最新日期的所有风险指标
            latest_date = self.session.query(RiskMetric.metric_date).filter(
                RiskMetric.symbol == symbol
            ).order_by(RiskMetric.metric_date.desc()).first()

            if not latest_date:
                return None

            # 获取该日期的所有指标
            metrics = self.session.query(RiskMetric).filter(
                RiskMetric.symbol == symbol,
                RiskMetric.metric_date == latest_date[0]
            ).all()

            if not metrics:
                return None

            # 将指标转换为字典格式 {metric_name: metric_value}
            result = {
                'symbol': symbol,
                'metric_date': latest_date[0].isoformat() if latest_date[0] else None,
            }

            for m in metrics:
                result[m.metric_name] = m.metric_value

            return result

        except Exception as e:
            logger.error(f"Error getting latest risk metrics for {symbol}: {e}", exc_info=True)
            return None

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
