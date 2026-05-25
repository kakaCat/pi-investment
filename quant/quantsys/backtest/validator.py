"""
回测基线验证器 - Backtest Baseline Validator

参考金策智算的回测基线验证机制，确保策略在实盘前经过充分的历史数据验证。

核心功能:
1. 最小历史年限检查 - 确保有足够的历史数据
2. 市场周期覆盖检查 - 确保经历过牛市、熊市、震荡市
3. 数据质量检查 - 检测数据缺失、异常值
4. 配置文件管理 - 不同策略类型的验证标准
"""

from dataclasses import dataclass
from typing import List, Dict, Optional, Tuple
from datetime import datetime, timedelta
from enum import Enum
import pandas as pd
import numpy as np


class MarketRegime(Enum):
    """市场状态"""
    BULL = "bull"          # 牛市
    BEAR = "bear"          # 熊市
    SIDEWAYS = "sideways"  # 震荡市


class IssueSeverity(Enum):
    """问题严重程度"""
    ERROR = "error"      # 错误 - 必须修复
    WARNING = "warning"  # 警告 - 建议修复
    INFO = "info"        # 信息 - 可选修复


@dataclass
class ValidationIssue:
    """验证问题"""
    severity: IssueSeverity
    category: str
    message: str
    details: Optional[Dict] = None

    def __init__(self, severity: IssueSeverity, category: str, message: str, details: Optional[Dict] = None):
        self.severity = severity
        self.category = category
        self.message = message
        self.details = details or {}


@dataclass
class ValidationResult:
    """验证结果"""
    passed: bool
    issues: List[ValidationIssue]
    summary: Dict

    def __init__(self, passed: bool, issues: List[ValidationIssue], summary: Dict):
        self.passed = passed
        self.issues = issues
        self.summary = summary

    def get_errors(self) -> List[ValidationIssue]:
        """获取所有错误"""
        return [issue for issue in self.issues if issue.severity == IssueSeverity.ERROR]

    def get_warnings(self) -> List[ValidationIssue]:
        """获取所有警告"""
        return [issue for issue in self.issues if issue.severity == IssueSeverity.WARNING]


@dataclass
class ValidatorConfig:
    """验证器配置"""
    min_history_years: float = 5.0
    min_trade_count: int = 100
    max_data_gap_days: int = 10
    max_missing_data_pct: float = 0.05
    require_bull_market: bool = True
    require_bear_market: bool = True
    require_sideways_market: bool = True
    bull_threshold: float = 0.20
    bear_threshold: float = -0.15
    sideways_threshold: float = 0.10
    max_price_jump_pct: float = 0.30
    min_sharpe_ratio: Optional[float] = None
    max_drawdown_threshold: Optional[float] = None


@dataclass
class DataQualityCheck:
    """数据质量检查结果"""
    total_days: int
    missing_days: int
    missing_pct: float
    max_gap_days: int
    price_jumps: List[Tuple[datetime, float]]
    anomalies: List[str]

    def __init__(self, total_days: int, missing_days: int, missing_pct: float,
                 max_gap_days: int, price_jumps: List[Tuple[datetime, float]],
                 anomalies: List[str]):
        self.total_days = total_days
        self.missing_days = missing_days
        self.missing_pct = missing_pct
        self.max_gap_days = max_gap_days
        self.price_jumps = price_jumps
        self.anomalies = anomalies


class BacktestValidator:
    """回测基线验证器"""

    def __init__(self, config: Optional[ValidatorConfig] = None):
        self.config = config or ValidatorConfig()

    def validate(
        self,
        equity_curve: pd.Series,
        trades: List[Dict],
        price_data: Optional[pd.DataFrame] = None
    ) -> ValidationResult:
        """
        验证回测结果

        Args:
            equity_curve: 权益曲线 (index=日期, value=权益)
            trades: 交易记录列表
            price_data: 价格数据 (可选，用于数据质量检查)

        Returns:
            ValidationResult
        """
        issues = []

        # 1. 检查历史年限
        history_issues = self._check_history_length(equity_curve)
        issues.extend(history_issues)

        # 2. 检查交易数量
        trade_issues = self._check_trade_count(trades)
        issues.extend(trade_issues)

        # 3. 检查市场周期覆盖
        regime_issues = self._check_market_regimes(equity_curve)
        issues.extend(regime_issues)

        # 4. 检查数据质量
        if price_data is not None:
            quality_issues = self._check_data_quality(price_data)
            issues.extend(quality_issues)

        # 5. 检查性能指标
        performance_issues = self._check_performance_metrics(equity_curve, trades)
        issues.extend(performance_issues)

        # 判断是否通过
        has_errors = any(issue.severity == IssueSeverity.ERROR for issue in issues)
        passed = not has_errors

        # 生成摘要
        summary = self._generate_summary(equity_curve, trades, issues)

        return ValidationResult(passed=passed, issues=issues, summary=summary)

    def _check_history_length(self, equity_curve: pd.Series) -> List[ValidationIssue]:
        """检查历史年限"""
        issues = []

        if len(equity_curve) == 0:
            issues.append(ValidationIssue(
                severity=IssueSeverity.ERROR,
                category="history_length",
                message="权益曲线为空"
            ))
            return issues

        start_date = equity_curve.index[0]
        end_date = equity_curve.index[-1]
        years = (end_date - start_date).days / 365.25

        if years < self.config.min_history_years:
            issues.append(ValidationIssue(
                severity=IssueSeverity.ERROR,
                category="history_length",
                message=f"历史数据不足: {years:.1f}年 < {self.config.min_history_years}年",
                details={
                    'actual_years': years,
                    'required_years': self.config.min_history_years,
                    'start_date': start_date.strftime('%Y-%m-%d'),
                    'end_date': end_date.strftime('%Y-%m-%d')
                }
            ))
        else:
            issues.append(ValidationIssue(
                severity=IssueSeverity.INFO,
                category="history_length",
                message=f"历史数据充足: {years:.1f}年",
                details={'years': years}
            ))

        return issues

    def _check_trade_count(self, trades: List[Dict]) -> List[ValidationIssue]:
        """检查交易数量"""
        issues = []
        trade_count = len(trades)

        if trade_count < self.config.min_trade_count:
            issues.append(ValidationIssue(
                severity=IssueSeverity.WARNING,
                category="trade_count",
                message=f"交易次数较少: {trade_count} < {self.config.min_trade_count}",
                details={
                    'actual_count': trade_count,
                    'required_count': self.config.min_trade_count
                }
            ))
        else:
            issues.append(ValidationIssue(
                severity=IssueSeverity.INFO,
                category="trade_count",
                message=f"交易次数充足: {trade_count}",
                details={'count': trade_count}
            ))

        return issues

    def _check_market_regimes(self, equity_curve: pd.Series) -> List[ValidationIssue]:
        """检查市场周期覆盖"""
        issues = []

        if len(equity_curve) < 2:
            return issues

        # 计算滚动收益率（以年为单位）
        returns = equity_curve.pct_change()

        # 使用252个交易日作为一年
        rolling_window = min(252, len(returns) // 2)
        if rolling_window < 20:
            issues.append(ValidationIssue(
                severity=IssueSeverity.WARNING,
                category="market_regime",
                message="数据点太少，无法准确识别市场周期",
                details={'data_points': len(equity_curve)}
            ))
            return issues

        rolling_returns = returns.rolling(window=rolling_window).sum()

        # 识别市场状态
        regimes_found = set()

        max_return = rolling_returns.max()
        min_return = rolling_returns.min()

        if max_return >= self.config.bull_threshold:
            regimes_found.add(MarketRegime.BULL)

        if min_return <= self.config.bear_threshold:
            regimes_found.add(MarketRegime.BEAR)

        # 震荡市：既不是明显的牛市也不是明显的熊市
        sideways_periods = rolling_returns[
            (rolling_returns > self.config.bear_threshold) &
            (rolling_returns < self.config.sideways_threshold)
        ]
        if len(sideways_periods) > rolling_window // 2:
            regimes_found.add(MarketRegime.SIDEWAYS)

        # 检查是否覆盖所需的市场状态
        required_regimes = []
        if self.config.require_bull_market:
            required_regimes.append(MarketRegime.BULL)
        if self.config.require_bear_market:
            required_regimes.append(MarketRegime.BEAR)
        if self.config.require_sideways_market:
            required_regimes.append(MarketRegime.SIDEWAYS)

        missing_regimes = [r for r in required_regimes if r not in regimes_found]

        if missing_regimes:
            issues.append(ValidationIssue(
                severity=IssueSeverity.WARNING,
                category="market_regime",
                message=f"缺少市场周期: {', '.join(r.value for r in missing_regimes)}",
                details={
                    'found_regimes': [r.value for r in regimes_found],
                    'missing_regimes': [r.value for r in missing_regimes],
                    'max_return': float(max_return),
                    'min_return': float(min_return)
                }
            ))
        else:
            issues.append(ValidationIssue(
                severity=IssueSeverity.INFO,
                category="market_regime",
                message=f"市场周期覆盖完整: {', '.join(r.value for r in regimes_found)}",
                details={'regimes': [r.value for r in regimes_found]}
            ))

        return issues

    def _check_data_quality(self, price_data: pd.DataFrame) -> List[ValidationIssue]:
        """检查数据质量"""
        issues = []

        if price_data.empty:
            issues.append(ValidationIssue(
                severity=IssueSeverity.ERROR,
                category="data_quality",
                message="价格数据为空"
            ))
            return issues

        # 检查数据缺失
        date_range = pd.date_range(
            start=price_data.index[0],
            end=price_data.index[-1],
            freq='D'
        )
        total_days = len(date_range)
        actual_days = len(price_data)
        missing_days = total_days - actual_days
        missing_pct = missing_days / total_days

        if missing_pct > self.config.max_missing_data_pct:
            issues.append(ValidationIssue(
                severity=IssueSeverity.WARNING,
                category="data_quality",
                message=f"数据缺失率过高: {missing_pct:.1%}",
                details={
                    'missing_days': missing_days,
                    'total_days': total_days,
                    'missing_pct': missing_pct
                }
            ))

        # 检查数据间隔
        if len(price_data) > 1:
            date_diffs = price_data.index.to_series().diff()
            max_gap = date_diffs.max().days if len(date_diffs) > 0 else 0

            if max_gap > self.config.max_data_gap_days:
                issues.append(ValidationIssue(
                    severity=IssueSeverity.WARNING,
                    category="data_quality",
                    message=f"存在较大数据间隔: {max_gap}天",
                    details={'max_gap_days': max_gap}
                ))

        # 检查价格异常跳变
        if 'close' in price_data.columns:
            price_changes = price_data['close'].pct_change().abs()
            large_jumps = price_changes[price_changes > self.config.max_price_jump_pct]

            if len(large_jumps) > 0:
                issues.append(ValidationIssue(
                    severity=IssueSeverity.WARNING,
                    category="data_quality",
                    message=f"检测到{len(large_jumps)}个异常价格跳变",
                    details={
                        'jump_count': len(large_jumps),
                        'max_jump': float(large_jumps.max()),
                        'dates': [d.strftime('%Y-%m-%d') for d in large_jumps.index[:5]]
                    }
                ))

        return issues

    def _check_performance_metrics(
        self,
        equity_curve: pd.Series,
        trades: List[Dict]
    ) -> List[ValidationIssue]:
        """检查性能指标"""
        issues = []

        if len(equity_curve) < 2:
            return issues

        # 计算夏普比率
        returns = equity_curve.pct_change().dropna()
        if len(returns) > 0:
            sharpe = returns.mean() / returns.std() * np.sqrt(252) if returns.std() > 0 else 0

            if self.config.min_sharpe_ratio is not None:
                if sharpe < self.config.min_sharpe_ratio:
                    issues.append(ValidationIssue(
                        severity=IssueSeverity.WARNING,
                        category="performance",
                        message=f"夏普比率过低: {sharpe:.2f} < {self.config.min_sharpe_ratio:.2f}",
                        details={'sharpe_ratio': sharpe}
                    ))

        # 计算最大回撤
        cummax = equity_curve.cummax()
        drawdown = (equity_curve - cummax) / cummax
        max_drawdown = abs(drawdown.min())

        if self.config.max_drawdown_threshold is not None:
            if max_drawdown > self.config.max_drawdown_threshold:
                issues.append(ValidationIssue(
                    severity=IssueSeverity.WARNING,
                    category="performance",
                    message=f"最大回撤过大: {max_drawdown:.1%} > {self.config.max_drawdown_threshold:.1%}",
                    details={'max_drawdown': max_drawdown}
                ))

        return issues

    def _generate_summary(
        self,
        equity_curve: pd.Series,
        trades: List[Dict],
        issues: List[ValidationIssue]
    ) -> Dict:
        """生成验证摘要"""
        error_count = sum(1 for i in issues if i.severity == IssueSeverity.ERROR)
        warning_count = sum(1 for i in issues if i.severity == IssueSeverity.WARNING)
        info_count = sum(1 for i in issues if i.severity == IssueSeverity.INFO)

        summary = {
            'total_issues': len(issues),
            'errors': error_count,
            'warnings': warning_count,
            'info': info_count,
            'trade_count': len(trades),
        }

        if len(equity_curve) > 0:
            start_date = equity_curve.index[0]
            end_date = equity_curve.index[-1]
            years = (end_date - start_date).days / 365.25

            summary.update({
                'start_date': start_date.strftime('%Y-%m-%d'),
                'end_date': end_date.strftime('%Y-%m-%d'),
                'history_years': round(years, 1),
                'data_points': len(equity_curve)
            })

        return summary

    def create_profile(self, profile_name: str) -> ValidatorConfig:
        """
        创建预定义的验证配置文件

        Args:
            profile_name: 配置文件名称
                - 'strict': 严格模式（长期策略）
                - 'moderate': 中等模式（中期策略）
                - 'relaxed': 宽松模式（短期策略）

        Returns:
            ValidatorConfig
        """
        if profile_name == 'strict':
            return ValidatorConfig(
                min_history_years=10.0,
                min_trade_count=200,
                max_data_gap_days=5,
                max_missing_data_pct=0.02,
                require_bull_market=True,
                require_bear_market=True,
                require_sideways_market=True,
                min_sharpe_ratio=1.0,
                max_drawdown_threshold=0.20
            )
        elif profile_name == 'moderate':
            return ValidatorConfig(
                min_history_years=5.0,
                min_trade_count=100,
                max_data_gap_days=10,
                max_missing_data_pct=0.05,
                require_bull_market=True,
                require_bear_market=True,
                require_sideways_market=False,
                min_sharpe_ratio=0.5,
                max_drawdown_threshold=0.30
            )
        elif profile_name == 'relaxed':
            return ValidatorConfig(
                min_history_years=3.0,
                min_trade_count=50,
                max_data_gap_days=15,
                max_missing_data_pct=0.10,
                require_bull_market=False,
                require_bear_market=False,
                require_sideways_market=False,
                min_sharpe_ratio=None,
                max_drawdown_threshold=None
            )
        else:
            raise ValueError(f"Unknown profile: {profile_name}")
