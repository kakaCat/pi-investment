"""
池子健康度追踪服务 - PoolHealthTracker

定期追踪池子的健康状况，识别潜在问题
"""
import structlog
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from domain.ports import IStockPoolRepository
from application.services.enhanced_risk_assessor import EnhancedRiskAssessor

logger = structlog.get_logger(__name__)


class PoolHealthTracker:
    """池子健康度追踪器

    P2-1: 支持依赖注入，保持向后兼容
    """

    def __init__(
        self,
        pool_repo: Optional[IStockPoolRepository] = None,
        risk_assessor: Optional[EnhancedRiskAssessor] = None,
    ):
        """初始化服务

        Args:
            pool_repo: 股票池仓库（可选）
            risk_assessor: 风险评估器（可选）

        P2-1: 推荐通过 ServiceFactory 获取实例
        """
        self.pool_repo = pool_repo
        self.risk_assessor = risk_assessor or EnhancedRiskAssessor()

    def track_pool_health(self, pool_id: int) -> Dict[str, Any]:
        """
        追踪池子健康度

        Args:
            pool_id: 池子ID

        Returns:
            {
                'pool_id': 1,
                'health_score': 75,  # 0-100，越高越健康
                'health_level': 'good',  # excellent/good/fair/poor
                'metrics': {
                    'activity': 80,      # 活跃度
                    'stability': 70,     # 稳定性
                    'risk_control': 60,  # 风险控制
                    'performance': 85    # 业绩表现
                },
                'issues': [...],
                'trend': 'improving'  # improving/stable/declining
            }
        """
        logger.info(f"📊 追踪池子健康度: pool_id={pool_id}")

        try:
            pool = self.pool_repo.get_pool(pool_id)
            if not pool:
                raise ValueError(f"池子不存在: {pool_id}")

            # 1. 评估各项指标
            activity = self._assess_activity(pool)
            stability = self._assess_stability(pool)
            risk_control = self._assess_risk_control(pool)
            performance = self._assess_performance(pool)

            # 2. 计算综合健康度
            metrics = {
                'activity': activity,
                'stability': stability,
                'risk_control': risk_control,
                'performance': performance
            }

            health_score = sum(metrics.values()) / len(metrics)
            health_level = self._determine_health_level(health_score)

            # 3. 识别问题
            issues = self._identify_issues(metrics, pool)

            # 4. 判断趋势（需要历史数据）
            trend = 'stable'  # 简化实现

            result = {
                'pool_id': pool_id,
                'health_score': round(health_score, 1),
                'health_level': health_level,
                'metrics': metrics,
                'issues': issues,
                'trend': trend,
                'tracked_at': datetime.now().isoformat()
            }

            logger.info(f"✅ 健康度追踪完成: score={health_score:.1f}, level={health_level}")
            return result

        except Exception as e:
            logger.error(f"❌ 健康度追踪失败: {e}", exc_info=True)
            raise

    def _assess_activity(self, pool: Dict) -> float:
        """评估活跃度"""
        # 简化实现：基于股票数量
        symbol_count = len(pool.get('symbols', []))
        if symbol_count >= 20:
            return 100
        elif symbol_count >= 10:
            return 80
        elif symbol_count >= 5:
            return 60
        else:
            return 40

    def _assess_stability(self, pool: Dict) -> float:
        """评估稳定性"""
        # 简化实现
        return 70

    def _assess_risk_control(self, pool: Dict) -> float:
        """评估风险控制"""
        try:
            # 使用增强风险评估
            risk_result = self.risk_assessor.assess_pool_risk(pool['id'])
            risk_score = risk_result.get('overall_risk_score', 50)
            # 转换：风险越低，控制越好
            return 100 - risk_score
        except:
            return 50

    def _assess_performance(self, pool: Dict) -> float:
        """评估业绩表现"""
        # 简化实现：需要实际收益数据
        return 75

    def _determine_health_level(self, score: float) -> str:
        """确定健康级别"""
        if score >= 80:
            return 'excellent'
        elif score >= 60:
            return 'good'
        elif score >= 40:
            return 'fair'
        else:
            return 'poor'

    def _identify_issues(self, metrics: Dict, pool: Dict) -> List[str]:
        """识别问题"""
        issues = []

        if metrics['activity'] < 60:
            issues.append('活跃度偏低，建议增加股票数量')

        if metrics['risk_control'] < 50:
            issues.append('风险控制不足，建议减仓或调整持仓')

        if metrics['performance'] < 50:
            issues.append('业绩表现不佳，建议重新评估策略')

        return issues
