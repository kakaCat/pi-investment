"""
策略验证服务

负责策略批量验证、综合评分计算、无效策略标记
"""
from domain.ports import IStockRepository, IStrategyRepository
from typing import Dict, List, Optional
import structlog
import requests
import time
from datetime import datetime


logger = structlog.get_logger(__name__)


class StrategyValidationService:
    """策略验证服务"""

    def __init__(self, strategy_repo=None, stock_repo=None):
        self._strategy_repo = strategy_repo
        from application.services.stock_pool_service import StockPoolService
        if stock_repo is None:
            from infrastructure.services.enhanced_service_factory import EnhancedServiceFactory
            stock_repo = EnhancedServiceFactory.resolve(IStockRepository)
        self.stock_pool_service = StockPoolService(stock_repo)

    @property
    def strategy_repo(self):
        """延迟加载 strategy_repo"""
        if self._strategy_repo is None:
            from infrastructure.services.enhanced_service_factory import EnhancedServiceFactory
            self._strategy_repo = EnhancedServiceFactory.resolve(IStrategyRepository)
        return self._strategy_repo

    def normalize(
        self,
        value: float,
        min_val: float,
        max_val: float,
        reverse: bool = False
    ) -> float:
        """
        将指标值归一化到 [0, 100]

        Args:
            value: 原始值
            min_val: 最小值（数值范围的下界）
            max_val: 最大值（数值范围的上界）
            reverse: 是否为反向指标（如回撤、波动率等，数值上越接近max_val越好）
                    注意：对于回撤等负值指标，调用时应确保max_val是"好"的一端（如0.0）

        Returns:
            归一化后的分数 (0-100)

        Examples:
            # 正向指标（收益率：越大越好）
            normalize(0.15, 0.0, 0.3)  # 15%收益 → 50分

            # 反向指标（回撤：越接近0越好）
            normalize(-0.1, -0.5, 0.0, reverse=True)  # -10%回撤 → 80分
            normalize(-0.4, -0.5, 0.0, reverse=True)  # -40%回撤 → 20分
        """
        # Clip value to range
        value = max(min_val, min(max_val, value))

        # Normalize to [0, 1]
        if max_val == min_val:
            normalized = 0.5
        else:
            normalized = (value - min_val) / (max_val - min_val)

        # Reverse if needed (for metrics where lower is better)
        if reverse:
            normalized = 1.0 - normalized

        # Scale to [0, 100]
        return normalized * 100.0

    def calculate_comprehensive_score(
        self,
        annual_return: float,
        sharpe_ratio: float,
        max_drawdown: float,
        win_rate: float,
        profit_factor: float
    ) -> float:
        """
        计算综合评分（0-100分）

        公式:
        score = normalize(annual_return, -0.5, 0.5) * 0.40 +
                normalize(sharpe_ratio, -2, 3) * 0.20 +
                normalize(max_drawdown, -0.5, 0, reverse=True) * 0.15 +
                normalize(win_rate, 0, 1) * 0.15 +
                normalize(profit_factor, 0, 3) * 0.10

        Args:
            annual_return: 年化收益率 (e.g., 0.15 for 15%)
            sharpe_ratio: Sharpe比率
            max_drawdown: 最大回撤 (e.g., -0.20 for -20%)
            win_rate: 胜率 (e.g., 0.60 for 60%)
            profit_factor: 盈亏比

        Returns:
            综合评分 (0-100)
        """
        # Normalize each metric
        return_score = self.normalize(annual_return, -0.5, 0.5)
        sharpe_score = self.normalize(sharpe_ratio, -2, 3)
        drawdown_score = self.normalize(max_drawdown, -0.5, 0.0, reverse=True)
        winrate_score = self.normalize(win_rate, 0.0, 1.0)
        profit_score = self.normalize(profit_factor, 0.0, 3.0)

        # Weighted sum (revenue-priority)
        score = (
            return_score * 0.40 +
            sharpe_score * 0.20 +
            drawdown_score * 0.15 +
            winrate_score * 0.15 +
            profit_score * 0.10
        )

        return score

    def _aggregate_by_strategy(self, results: List[Dict]) -> Dict[int, Dict]:
        """
        按策略聚合回测结果

        Args:
            results: 回测结果列表，每个元素包含 strategy_id 和指标

        Returns:
            {
                strategy_id: {
                    'annual_return': float,
                    'sharpe_ratio': float,
                    'max_drawdown': float,
                    'win_rate': float,
                    'profit_factor': float,
                    'backtest_count': int,
                    'error_count': int
                }
            }
        """
        from collections import defaultdict

        # Group by strategy_id
        grouped = defaultdict(list)
        for result in results:
            strategy_id = result['strategy_id']
            grouped[strategy_id].append(result)

        # Calculate averages
        aggregated = {}
        for strategy_id, strategy_results in grouped.items():
            # Calculate mean for each metric
            annual_returns = [r['annual_return'] for r in strategy_results if r.get('annual_return') is not None]
            sharpe_ratios = [r['sharpe_ratio'] for r in strategy_results if r.get('sharpe_ratio') is not None]
            max_drawdowns = [r['max_drawdown'] for r in strategy_results if r.get('max_drawdown') is not None]
            win_rates = [r['win_rate'] for r in strategy_results if r.get('win_rate') is not None]
            profit_factors = [r['profit_factor'] for r in strategy_results if r.get('profit_factor') is not None]

            aggregated[strategy_id] = {
                'annual_return': sum(annual_returns) / len(annual_returns) if annual_returns else 0.0,
                'sharpe_ratio': sum(sharpe_ratios) / len(sharpe_ratios) if sharpe_ratios else 0.0,
                'max_drawdown': sum(max_drawdowns) / len(max_drawdowns) if max_drawdowns else 0.0,
                'win_rate': sum(win_rates) / len(win_rates) if win_rates else 0.0,
                'profit_factor': sum(profit_factors) / len(profit_factors) if profit_factors else 0.0,
                'backtest_count': len(strategy_results),
                'error_count': 0  # Will be populated from errors array
            }

        return aggregated

    def _call_batch_backtest(
        self,
        jobs: List[Dict],
        start_date: str,
        end_date: str
    ) -> Dict:
        """
        调用批量回测 API

        Args:
            jobs: 回测任务列表 [{'strategy_id': int, 'symbol': str}, ...]
            start_date: 开始日期 (YYYY-MM-DD)
            end_date: 结束日期 (YYYY-MM-DD)

        Returns:
            {
                'results': [
                    {
                        'strategy_id': int,
                        'symbol': str,
                        'annual_return': float,
                        'sharpe_ratio': float,
                        'max_drawdown': float,
                        'win_rate': float,
                        'profit_factor': float
                    },
                    ...
                ],
                'errors': [
                    {
                        'strategy_id': int,
                        'symbol': str,
                        'error': str
                    },
                    ...
                ]
            }
        """
        url = "http://127.0.0.1:5001/api/backtest/batch"
        payload = {
            "jobs": jobs,
            "start_date": start_date,
            "end_date": end_date,
            "initial_capital": 100000.0
        }

        try:
            response = requests.post(url, json=payload, timeout=300)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"Batch backtest API call failed: {e}")
            raise

    def validate_all_strategies(
        self,
        start_date: str,
        end_date: str,
        threshold: float = 60.0,
        dry_run: bool = False
    ) -> Dict:
        """
        验证所有策略

        Args:
            start_date: 回测开始日期 (YYYY-MM-DD)
            end_date: 回测结束日期 (YYYY-MM-DD)
            threshold: 综合评分阈值 (0-100)
            dry_run: 是否为试运行（不更新数据库）

        Returns:
            {
                'total': int,           # 总策略数
                'passed': int,          # 通过数
                'failed': int,          # 失败数
                'details': [
                    {
                        'strategy_id': int,
                        'strategy_name': str,
                        'score': float,
                        'passed': bool,
                        'metrics': {
                            'annual_return': float,
                            'sharpe_ratio': float,
                            'max_drawdown': float,
                            'win_rate': float,
                            'profit_factor': float
                        },
                        'backtest_count': int,
                        'error_count': int
                    },
                    ...
                ]
            }
        """
        logger.info(f"Starting validation for all strategies (dry_run={dry_run})")
        start_time = time.time()

        # 1. Get all strategies
        strategies = self.strategy_repo.get_all()
        if not strategies:
            logger.warning("No strategies found")
            return {
                'total': 0,
                'passed': 0,
                'failed': 0,
                'details': []
            }

        # 2. Get core stock pool (hot stocks)
        core_stock_symbols = self.stock_pool_service.get_hot_stocks()
        if not core_stock_symbols:
            logger.warning("No core stocks found")
            return {
                'total': len(strategies),
                'passed': 0,
                'failed': len(strategies),
                'details': []
            }

        # 3. Generate jobs (strategy × stock)
        jobs = []
        for strategy in strategies:
            for symbol in core_stock_symbols:
                jobs.append({
                    'strategy_id': strategy['id'],
                    'symbol': symbol
                })

        logger.info(f"Generated {len(jobs)} backtest jobs for {len(strategies)} strategies × {len(core_stock_symbols)} stocks")

        # 4. Call batch backtest API
        batch_result = self._call_batch_backtest(jobs, start_date, end_date)
        results = batch_result.get('results', [])
        errors = batch_result.get('errors', [])

        # 5. Aggregate by strategy
        aggregated = self._aggregate_by_strategy(results)

        # Count errors per strategy
        error_counts = {}
        for error in errors:
            strategy_id = error['strategy_id']
            error_counts[strategy_id] = error_counts.get(strategy_id, 0) + 1

        # Update error counts
        for strategy_id, count in error_counts.items():
            if strategy_id in aggregated:
                aggregated[strategy_id]['error_count'] = count

        # 6. Calculate scores and determine pass/fail
        details = []
        passed_count = 0
        failed_count = 0

        for strategy in strategies:
            strategy_id = strategy['id']
            strategy_name = strategy['strategy_name']

            if strategy_id not in aggregated:
                # All backtests failed for this strategy
                details.append({
                    'strategy_id': strategy_id,
                    'strategy_name': strategy_name,
                    'score': 0.0,
                    'status': 'failed',
                    'passed': False,
                    'metrics': {},
                    'backtest_count': 0,
                    'error_count': error_counts.get(strategy_id, 0)
                })
                failed_count += 1
                continue

            metrics = aggregated[strategy_id]
            score = self.calculate_comprehensive_score(
                annual_return=metrics['annual_return'],
                sharpe_ratio=metrics['sharpe_ratio'],
                max_drawdown=metrics['max_drawdown'],
                win_rate=metrics['win_rate'],
                profit_factor=metrics['profit_factor']
            )

            passed = score >= threshold

            details.append({
                'strategy_id': strategy_id,
                'strategy_name': strategy_name,
                'score': score,
                'status': 'passed' if passed else 'failed',
                'passed': passed,
                'metrics': {
                    'annual_return': metrics['annual_return'],
                    'sharpe_ratio': metrics['sharpe_ratio'],
                    'max_drawdown': metrics['max_drawdown'],
                    'win_rate': metrics['win_rate'],
                    'profit_factor': metrics['profit_factor']
                },
                'backtest_count': metrics['backtest_count'],
                'error_count': metrics['error_count']
            })

            if passed:
                passed_count += 1
            else:
                failed_count += 1

        # 7. Update database if not dry_run
        if not dry_run:
            for detail in details:
                status = 'valid' if detail['passed'] else 'invalid'
                errors = None if detail['passed'] else f"Score {detail['score']:.2f} below threshold"
                self.strategy_repo.update_validation_status(
                    strategy_id=detail['strategy_id'],
                    status=status,
                    errors=errors
                )
            logger.info(f"Updated validation results in database")

        # Calculate duration
        end_time = time.time()
        duration = end_time - start_time

        result = {
            'total': len(strategies),
            'passed': passed_count,
            'failed': failed_count,
            'duration': duration,
            'details': details
        }

        logger.info(f"Validation complete: {passed_count}/{len(strategies)} passed (threshold={threshold})")
        return result


    # ------------------------------------------------------------------
    # Fix④: 基于最近落库批量回测证据的报告性验证
    # 背景：/api/backtest/batch（Flask）已被 commit 54851df0 删除且未在
    # FastAPI 层重建 → validate_all_strategies() 的 HTTP 批量回测必然失败。
    # 每日验证改为：读取 quant.backtest_results 中最近的真实批量回测证据，
    # 按 strategy_name 匹配 strategy_configs → 聚合 → 复用同一评分公式 →
    # 写独立列 validation_status + strategy_validation_reports。
    # 报告性验证：无证据策略显式跳过（不判 0 分 invalid，避免历史 mass-invalidate 重演）；
    # invalid 不自动停用策略（deactivate_if_invalid=False），停用由人工决策。
    # ------------------------------------------------------------------
    def validate_from_recent_backtests(
        self,
        lookback_days: int = 30,
        threshold: float = 60.0,
        dry_run: bool = True,
    ) -> Dict:
        """基于最近落库的真实批量回测证据（quant.backtest_results）做报告性验证。

        Args:
            lookback_days: 只考虑最近 N 天内产生的回测证据（默认 30 天）
            threshold: 综合评分阈值（默认 60）
            dry_run: True=只计算不写库（默认，用于预览）

        Returns:
            {
                'total': 匹配到配置的策略数,
                'with_evidence': 有最近回测证据的策略数,
                'passed': 分数达标数, 'failed': 不达标数,
                'no_evidence': 无最近证据被跳过的策略数,
                'evidence_sources': [...],  # 每策略证据批次信息
                'duration': 秒,
                'dry_run': bool,
            }
        """
        from sqlalchemy import text
        from adapters.outbound.repositories.strategy_repository import StrategyORMRepository
        from datetime import datetime, timedelta

        start = time.time()
        repo = StrategyORMRepository()
        session = repo.session

        # 1) 拉取最近 N 天每个策略的批量回测证据（聚合指标：每年化收益/夏普/回撤/胜率/盈亏比）
        since = datetime.now() - timedelta(days=lookback_days)
        rows = session.execute(text("""
            SELECT br.strategy_name,
                   MAX(br.created_at) AS evidence_at,
                   AVG(br.annual_return)  AS annual_return,
                   AVG(br.sharpe_ratio)   AS sharpe_ratio,
                   AVG(br.max_drawdown)   AS max_drawdown,
                   AVG(br.win_rate)       AS win_rate,
                   AVG(br.profit_factor)  AS profit_factor,
                   COUNT(*)               AS backtest_count,
                   MIN(br.start_date)     AS win_start,
                   MAX(br.end_date)       AS win_end
            FROM quant.backtest_results br
            WHERE br.created_at >= :since
            GROUP BY br.strategy_name
            ORDER BY br.strategy_name
        """), {'since': since}).fetchall()
        evidence = {r.strategy_name: {
            'annual_return': float(r.annual_return or 0.0),
            'sharpe_ratio': float(r.sharpe_ratio or 0.0),
            'max_drawdown': float(r.max_drawdown or 0.0),
            'win_rate': float(r.win_rate or 0.0),
            'profit_factor': float(r.profit_factor or 0.0),
            'backtest_count': int(r.backtest_count or 0),
            'evidence_at': r.evidence_at.isoformat() if r.evidence_at else None,
            'win_start': r.win_start.isoformat() if r.win_start else None,
            'win_end': r.win_end.isoformat() if r.win_end else None,
        } for r in rows}

        # 2) 获取全部策略配置（匹配 strategy_configs）
        configs = repo.get_user_strategies()
        config_by_name = {c['strategy_name']: c for c in configs if c.get('strategy_name')}

        # 3) 逐策略评分：有证据 → 计算分；无证据 → 跳过（no_evidence）
        details = []
        matched = []
        for name, ev in sorted(evidence.items()):
            cfg = config_by_name.get(name)
            if cfg is None:
                continue  # 回测证据属于已删除/未登记策略，跳过
            score = self.calculate_comprehensive_score(
                ev['annual_return'], ev['sharpe_ratio'],
                ev['max_drawdown'], ev['win_rate'], ev['profit_factor'],
            )
            passed = score >= threshold
            status = 'valid' if passed else 'invalid'
            errors = None if passed else f"Score {score:.2f} below threshold {threshold}"
            matched.append(cfg)
            details.append({
                'strategy_id': cfg['id'],
                'strategy_name': name,
                'score': round(score, 2),
                'passed': passed,
                'status': status,
                'errors': errors,
                'metrics': {
                    'annual_return': round(ev['annual_return'], 4),
                    'sharpe_ratio': round(ev['sharpe_ratio'], 4),
                    'max_drawdown': round(ev['max_drawdown'], 4),
                    'win_rate': round(ev['win_rate'], 4),
                    'profit_factor': round(ev['profit_factor'], 4),
                },
                'backtest_count': ev['backtest_count'],
                'evidence_at': ev['evidence_at'],
                'win_start': ev['win_start'],
                'win_end': ev['win_end'],
            })

        no_evidence_count = sum(
            1 for c in configs if c['strategy_name'] not in evidence and c.get('is_active')
        )

        # 4) 落库（仅非 dry_run）：独立列状态 + validation_reports
        #    幂等保护：同一策略当天已写过验证报告则跳过，防止每日 Job 重复触发膨胀 reports 表
        written = 0
        skipped_duplicate = 0
        if not dry_run and details:
            today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            for d in details:
                exists = session.execute(text("""
                    SELECT COUNT(*) FROM quant.strategy_validation_reports
                    WHERE strategy_id = :sid AND validation_date >= :today
                """), {'sid': d['strategy_id'], 'today': today}).scalar()
                if exists:
                    skipped_duplicate += 1
                    continue
                repo.update_validation_status(
                    strategy_id=d['strategy_id'],
                    status=d['status'],
                    errors=d['errors'],
                    deactivate_if_invalid=False,  # 报告性验证：不停用
                )
                # 只为"有证据"的策略写报告（评分有真实数据支撑）
                repo.save_validation_report({
                    'strategy_id': d['strategy_id'],
                    'score': d['score'],
                    'status': d['status'],
                    'annual_return': d['metrics']['annual_return'],
                    'sharpe_ratio': d['metrics']['sharpe_ratio'],
                    'max_drawdown': d['metrics']['max_drawdown'],
                    'win_rate': d['metrics']['win_rate'],
                    'profit_factor': d['metrics']['profit_factor'],
                    'backtest_count': d['backtest_count'],
                    'error_count': 0,
                    'start_date': d.get('win_start'),
                    'end_date': d.get('win_end'),
                })
                written += 1
            logger.info(
                f"Persisted validation status for {written} strategies "
                f"(dry_run=False, skipped_duplicate={skipped_duplicate})"
            )

        passed_count = sum(1 for d in details if d['passed'])
        failed_count = len(details) - passed_count

        result = {
            'total': len(details) + no_evidence_count,
            'with_evidence': len(details),
            'passed': passed_count,
            'failed': failed_count,
            'no_evidence': no_evidence_count,
            'reports_written': written,
            'reports_skipped_duplicate': skipped_duplicate,
            'duration': round(time.time() - start, 2),
            'dry_run': dry_run,
            'threshold': threshold,
            'evidence_window_days': lookback_days,
            'details': details,
        }
        logger.info(
            f"Recent-backtest validation preview: {passed_count}/{len(details)} passed "
            f"(threshold={threshold}, no_evidence_skipped={no_evidence_count}, dry_run={dry_run})"
        )
        return result
