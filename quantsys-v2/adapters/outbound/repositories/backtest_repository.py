"""
回测ORM Repository

使用SQLAlchemy ORM重构的回测数据访问层

支持：
1. 回测结果查询
2. 回测结果保存
3. 回测统计和排名

迁移状态：✅ 已完成ORM迁移
"""
from typing import List, Dict, Optional, Any
from datetime import date
import structlog

from sqlalchemy import func, desc, and_
from infrastructure.persistence.orm import BaseORMRepository
from infrastructure.persistence.orm.models import BacktestResult
from domain.ports import IBacktestRepository

logger = structlog.get_logger(__name__)

__all__ = ['BacktestORMRepository']


class BacktestORMRepository(BaseORMRepository[BacktestResult], IBacktestRepository):
    """回测ORM Repository

    示例用法：
        repo = BacktestORMRepository()

        # 查询单个回测结果
        result = repo.get_backtest(123)

        # 查询策略的所有回测
        results = repo.get_backtests_by_strategy('均值回归v1')

        # 保存回测结果
        result_id = repo.create_backtest({
            'strategy_name': '均值回归v1',
            'start_date': '2025-01-01',
            'end_date': '2026-06-30',
            'initial_capital': 1000000,
            'final_capital': 1150000,
            'total_return': 0.15,
            'sharpe_ratio': 1.8
        })
    """

    model = BacktestResult

    # ==================== IBacktestRepository接口实现 ====================

    def save_backtest_result(self, result: Dict[str, Any]) -> int:
        """保存回测结果（IBacktestRepository接口实现）"""
        try:
            backtest = BacktestResult(
                strategy_name=result.get('strategy_name'),
                start_date=result.get('start_date'),
                end_date=result.get('end_date'),
                initial_capital=result.get('initial_capital'),
                final_capital=result.get('final_capital'),
                total_return=result.get('total_return'),
                annual_return=result.get('annual_return'),
                sharpe_ratio=result.get('sharpe_ratio'),
                max_drawdown=result.get('max_drawdown'),
                win_rate=result.get('win_rate'),
                total_trades=result.get('total_trades'),
                config=result.get('config'),
                metrics=result.get('metrics'),
            )
            created = self.create(backtest)
            return created.id if created else 0

        except Exception as e:
            self._safe_rollback()
            logger.error(f"Error saving backtest result: {e}")
            return 0

    # ==================== 查询方法 ====================

    def get_backtest(self, backtest_id: int) -> Optional[BacktestResult]:
        """根据ID查询回测结果

        Args:
            backtest_id: 回测ID

        Returns:
            BacktestResult对象
        """
        return self.get_by_id(backtest_id)

    def get_backtests_by_strategy(
        self,
        strategy_name: str,
        symbol: Optional[str] = None,
        limit: int = 100
    ) -> List[BacktestResult]:
        """查询指定策略的回测结果

        Args:
            strategy_name: 策略名称
            symbol: 股票代码（可选）
            limit: 返回数量限制

        Returns:
            BacktestResult对象列表
        """
        try:
            query = self.session.query(BacktestResult).filter(
                BacktestResult.strategy_name == strategy_name
            )

            if symbol:
                query = query.filter(BacktestResult.symbol == symbol)

            return query.order_by(
                BacktestResult.created_at.desc()
            ).limit(limit).all()

        except Exception as e:
            self._safe_rollback()
            logger.error(f"Error getting backtests for strategy {strategy_name}: {e}")
            return []

    def get_backtests_by_symbol(
        self,
        symbol: str,
        limit: int = 100
    ) -> List[BacktestResult]:
        """查询指定股票的回测结果

        Args:
            symbol: 股票代码
            limit: 返回数量限制

        Returns:
            BacktestResult对象列表
        """
        try:
            return self.session.query(BacktestResult).filter(
                BacktestResult.symbol == symbol
            ).order_by(
                BacktestResult.created_at.desc()
            ).limit(limit).all()

        except Exception as e:
            self._safe_rollback()
            logger.error(f"Error getting backtests for {symbol}: {e}")
            return []

    def get_recent_backtests(self, limit: int = 50) -> List[BacktestResult]:
        """获取最近的回测结果

        Args:
            limit: 返回数量限制

        Returns:
            BacktestResult对象列表
        """
        try:
            return self.session.query(BacktestResult).order_by(
                BacktestResult.created_at.desc()
            ).limit(limit).all()

        except Exception as e:
            self._safe_rollback()
            logger.error(f"Error getting recent backtests: {e}")
            return []

    def get_all_backtests(
        self,
        strategy_name: Optional[str] = None,
        symbol: Optional[str] = None,
        limit: int = 100
    ) -> List[BacktestResult]:
        """获取所有回测结果（兼容方法名）

        Args:
            strategy_name: 策略名称（可选）
            symbol: 股票代码（可选）
            limit: 返回数量限制

        Returns:
            BacktestResult对象列表
        """
        try:
            query = self.session.query(BacktestResult)

            if strategy_name:
                query = query.filter(BacktestResult.strategy_name == strategy_name)
            if symbol:
                query = query.filter(BacktestResult.symbol == symbol)

            return query.order_by(
                BacktestResult.created_at.desc()
            ).limit(limit).all()

        except Exception as e:
            self._safe_rollback()
            logger.error(f"Error getting all backtests: {e}")
            return []

    def get_best_backtests(
        self,
        metric: str = 'sharpe_ratio',
        limit: int = 10,
        strategy_name: Optional[str] = None
    ) -> List[BacktestResult]:
        """获取表现最好的回测结果

        Args:
            metric: 排序指标 (sharpe_ratio/total_return/win_rate)
            limit: 返回数量限制
            strategy_name: 策略名称筛选（可选）

        Returns:
            BacktestResult对象列表
        """
        try:
            query = self.session.query(BacktestResult)

            if strategy_name:
                query = query.filter(BacktestResult.strategy_name == strategy_name)

            # 根据指标排序
            if metric == 'sharpe_ratio':
                query = query.filter(BacktestResult.sharpe_ratio.isnot(None))
                query = query.order_by(BacktestResult.sharpe_ratio.desc())
            elif metric == 'total_return':
                query = query.filter(BacktestResult.total_return.isnot(None))
                query = query.order_by(BacktestResult.total_return.desc())
            elif metric == 'win_rate':
                query = query.filter(BacktestResult.win_rate.isnot(None))
                query = query.order_by(BacktestResult.win_rate.desc())
            else:
                logger.warning(f"Unknown metric: {metric}, using sharpe_ratio")
                query = query.order_by(BacktestResult.sharpe_ratio.desc())

            return query.limit(limit).all()

        except Exception as e:
            self._safe_rollback()
            logger.error(f"Error getting best backtests: {e}")
            return []

    def get_backtests_by_date_range(
        self,
        start_date: str,
        end_date: str
    ) -> List[BacktestResult]:
        """查询指定回测时间范围的结果

        Args:
            start_date: 回测开始日期
            end_date: 回测结束日期

        Returns:
            BacktestResult对象列表
        """
        try:
            return self.session.query(BacktestResult).filter(
                BacktestResult.start_date >= start_date,
                BacktestResult.end_date <= end_date
            ).order_by(BacktestResult.created_at.desc()).all()

        except Exception as e:
            self._safe_rollback()
            logger.error(f"Error getting backtests by date range: {e}")
            return []

    # ==================== 创建和更新 ====================

    def create_backtest(self, backtest_data: Dict) -> Optional[int]:
        """创建回测结果

        Args:
            backtest_data: 回测数据字典
                必需字段: strategy_name, start_date, end_date, initial_capital, final_capital
                可选字段: symbol, total_return, sharpe_ratio, max_drawdown等

        Returns:
            创建的回测ID
        """
        required_fields = ['strategy_name', 'start_date', 'end_date', 'initial_capital', 'final_capital']

        # 验证必需字段
        for field in required_fields:
            if field not in backtest_data:
                logger.error(f"Missing required field: {field}")
                return None

        try:
            backtest = BacktestResult(**backtest_data)
            created = self.create(backtest, commit=True)

            if created:
                return created.id
            return None

        except Exception as e:
            self._safe_rollback()
            logger.error(f"Error creating backtest: {e}")
            return None

    def update_backtest(self, backtest_id: int, **kwargs) -> bool:
        """更新回测结果

        Args:
            backtest_id: 回测ID
            **kwargs: 要更新的字段

        Returns:
            成功返回True
        """
        try:
            backtest = self.get_by_id(backtest_id)
            if not backtest:
                logger.warning(f"Backtest {backtest_id} not found")
                return False

            for key, value in kwargs.items():
                if hasattr(backtest, key):
                    setattr(backtest, key, value)

            self.session.commit()
            return True

        except Exception as e:
            logger.error(f"Error updating backtest {backtest_id}: {e}")
            self.session.rollback()
            return False

    # ==================== 删除方法 ====================

    def delete_backtest(self, backtest_id: int) -> bool:
        """删除回测结果

        Args:
            backtest_id: 回测ID

        Returns:
            成功返回True
        """
        return self.delete_by_id(backtest_id, commit=True)

    def delete_backtests_by_strategy(self, strategy_name: str) -> int:
        """删除指定策略的所有回测结果

        Args:
            strategy_name: 策略名称

        Returns:
            删除的数量
        """
        try:
            count = self.session.query(BacktestResult).filter(
                BacktestResult.strategy_name == strategy_name
            ).delete()

            self.session.commit()
            return count

        except Exception as e:
            logger.error(f"Error deleting backtests for strategy {strategy_name}: {e}")
            self.session.rollback()
            return 0

    # ==================== 统计方法 ====================

    def count_backtests(self, strategy_name: Optional[str] = None) -> int:
        """统计回测数量

        Args:
            strategy_name: 策略名称（可选）

        Returns:
            回测数量
        """
        try:
            query = self.session.query(BacktestResult)

            if strategy_name:
                query = query.filter(BacktestResult.strategy_name == strategy_name)

            return query.count()

        except Exception as e:
            self._safe_rollback()
            logger.error(f"Error counting backtests: {e}")
            return 0

    def get_strategy_stats(self, strategy_name: str) -> Dict:
        """获取策略的回测统计

        Args:
            strategy_name: 策略名称

        Returns:
            统计信息字典
        """
        try:
            result = self.session.query(
                func.count(BacktestResult.id),
                func.avg(BacktestResult.total_return),
                func.avg(BacktestResult.sharpe_ratio),
                func.avg(BacktestResult.max_drawdown),
                func.avg(BacktestResult.win_rate),
                func.max(BacktestResult.total_return),
                func.min(BacktestResult.max_drawdown)
            ).filter(
                BacktestResult.strategy_name == strategy_name
            ).first()

            if result and result[0] > 0:
                return {
                    'count': result[0],
                    'avg_return': float(result[1] or 0),
                    'avg_sharpe': float(result[2] or 0),
                    'avg_drawdown': float(result[3] or 0),
                    'avg_win_rate': float(result[4] or 0),
                    'max_return': float(result[5] or 0),
                    'min_drawdown': float(result[6] or 0)
                }

            return {}

        except Exception as e:
            self._safe_rollback()
            logger.error(f"Error getting strategy stats: {e}")
            return {}

    def get_all_strategies(self) -> List[str]:
        """获取所有策略名称

        Returns:
            策略名称列表
        """
        try:
            result = self.session.query(BacktestResult.strategy_name).distinct().all()
            return [r[0] for r in result]

        except Exception as e:
            self._safe_rollback()
            logger.error(f"Error getting strategies: {e}")
            return []

    def get_backtest_stats(self, strategy_name: Optional[str] = None) -> Dict:
        """获取回测统计信息（兼容方法名）

        Args:
            strategy_name: 策略名称（可选）

        Returns:
            统计信息字典
        """
        if strategy_name:
            return self.get_strategy_stats(strategy_name)

        # 如果没有指定策略，返回所有回测的汇总统计
        try:
            result = self.session.query(
                func.count(BacktestResult.id),
                func.avg(BacktestResult.total_return),
                func.avg(BacktestResult.sharpe_ratio),
                func.avg(BacktestResult.max_drawdown),
                func.avg(BacktestResult.win_rate)
            ).first()

            if result and result[0] > 0:
                return {
                    'total_count': result[0],
                    'avg_return': float(result[1] or 0),
                    'avg_sharpe': float(result[2] or 0),
                    'avg_drawdown': float(result[3] or 0),
                    'avg_win_rate': float(result[4] or 0)
                }

            return {}

        except Exception as e:
            self._safe_rollback()
            logger.error(f"Error getting backtest stats: {e}")
            return {}

    def compare_strategies(
        self,
        strategy_names: List[str],
        metric: str = 'sharpe_ratio'
    ) -> List[Dict]:
        """比较多个策略的表现

        Args:
            strategy_names: 策略名称列表
            metric: 比较指标

        Returns:
            比较结果列表
        """
        try:
            results = []

            for strategy_name in strategy_names:
                stats = self.get_strategy_stats(strategy_name)
                if stats:
                    stats['strategy_name'] = strategy_name
                    results.append(stats)

            # 按指标排序
            if metric == 'avg_sharpe':
                results.sort(key=lambda x: x.get('avg_sharpe', 0), reverse=True)
            elif metric == 'avg_return':
                results.sort(key=lambda x: x.get('avg_return', 0), reverse=True)
            elif metric == 'avg_win_rate':
                results.sort(key=lambda x: x.get('avg_win_rate', 0), reverse=True)

            return results

        except Exception as e:
            self._safe_rollback()
            logger.error(f"Error comparing strategies: {e}")
            return []

    def get_strategy_evidence_since(self, since) -> List[Dict[str, Any]]:
        """按 strategy_name 聚合 since 之后落库的批量回测证据（一条策略一行）。

        2026-09-14（REQ-24e15d）：原实现是
        application/services/strategy_validation_service.py 里的
        session.execute(text(<聚合 SQL>), {'since': since}).fetchall() ——
        SQL 原文见下方「口径逐值对齐原 SQL」段（不在 docstring 里内联三引号，
        否则会提前终止 docstring 并把后面几行变成代码，2026-09-14 实测踩过）。现收口到此 ——
        下游原先按属性名取值（r.strategy_name），改为按同名键取字典值，数值逐值不变。

        口径逐值对齐原 SQL：
            SELECT br.strategy_name, MAX(br.created_at) AS evidence_at,
                   AVG(br.annual_return) AS annual_return, AVG(br.sharpe_ratio) AS sharpe_ratio,
                   AVG(br.max_drawdown) AS max_drawdown, AVG(br.win_rate) AS win_rate,
                   AVG(br.profit_factor) AS profit_factor, COUNT(*) AS backtest_count,
                   MIN(br.start_date) AS win_start, MAX(br.end_date) AS win_end
            FROM quant.backtest_results br
            WHERE br.created_at >= :since GROUP BY br.strategy_name ORDER BY br.strategy_name
        · 保留 ORDER BY strategy_name（下游据此建 dict 的键序，虽有 sorted() 兜底也不改）；
        · COUNT(*) 用 func.count()（不带列名），避免把 NULL 行漏计成「COUNT(列)」口径。

        Args:
            since: 时间下界（与 created_at 比较，通常为 datetime.now() - timedelta(days=N)）

        Returns:
            行字典列表，键与原 Core Row 的 label 一致：
            strategy_name / evidence_at / annual_return / sharpe_ratio / max_drawdown /
            win_rate / profit_factor / backtest_count / win_start / win_end。无匹配返回空列表。
        """
        stmt = (
            self.session.query(
                BacktestResult.strategy_name.label('strategy_name'),
                func.max(BacktestResult.created_at).label('evidence_at'),
                func.avg(BacktestResult.annual_return).label('annual_return'),
                func.avg(BacktestResult.sharpe_ratio).label('sharpe_ratio'),
                func.avg(BacktestResult.max_drawdown).label('max_drawdown'),
                func.avg(BacktestResult.win_rate).label('win_rate'),
                func.avg(BacktestResult.profit_factor).label('profit_factor'),
                func.count().label('backtest_count'),
                func.min(BacktestResult.start_date).label('win_start'),
                func.max(BacktestResult.end_date).label('win_end'),
            )
            .filter(BacktestResult.created_at >= since)
            .group_by(BacktestResult.strategy_name)
            .order_by(BacktestResult.strategy_name)
        )
        return [dict(row._mapping) for row in stmt.all()]
