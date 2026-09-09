"""
测试降级信息追踪

验证评分过程中的降级信息是否正确记录和传递
"""
import pytest
from unittest.mock import Mock, patch
from application.services.opportunity_scoring_service import OpportunityScoringService
from application.services.scoring.degradation_tracker import DegradationTracker, Severity


class TestDegradationTracker:
    """测试降级追踪器"""
    
    def test_record_single_degradation(self):
        """测试记录单个降级"""
        tracker = DegradationTracker()
        
        tracker.record(
            component='technical_factors',
            factor='rsi14',
            reason='TA-Lib not available',
            fallback='excluded from score',
            severity='warning'
        )
        
        degradations = tracker.get_degradations()
        assert len(degradations) == 1
        assert degradations[0]['component'] == 'technical_factors'
        assert degradations[0]['factor'] == 'rsi14'
        assert degradations[0]['severity'] == 'warning'
    
    def test_confidence_penalty_warning(self):
        """测试 warning 级别的置信度惩罚（-10%）"""
        tracker = DegradationTracker()
        tracker.record('test', 'reason', 'fallback', 'warning')
        
        penalty = tracker.get_confidence_penalty()
        assert penalty == 0.9  # 1 warning = -10%
    
    def test_confidence_penalty_error(self):
        """测试 error 级别的置信度惩罚（-30%）"""
        tracker = DegradationTracker()
        tracker.record('test', 'reason', 'fallback', 'error')
        
        penalty = tracker.get_confidence_penalty()
        assert penalty == 0.7  # 1 error = -30%
    
    def test_confidence_penalty_multiple(self):
        """测试多个降级的累积惩罚"""
        tracker = DegradationTracker()
        tracker.record('test1', 'reason1', 'fallback1', 'warning')  # -10%
        tracker.record('test2', 'reason2', 'fallback2', 'warning')  # -10%
        tracker.record('test3', 'reason3', 'fallback3', 'error')    # -30%
        
        penalty = tracker.get_confidence_penalty()
        assert penalty == 0.5  # 2 warnings + 1 error = -50%
    
    def test_confidence_penalty_critical(self):
        """测试 critical 级别直接归零"""
        tracker = DegradationTracker()
        tracker.record('test', 'reason', 'fallback', 'critical')
        
        penalty = tracker.get_confidence_penalty()
        assert penalty == 0.0
    
    def test_summary(self):
        """测试降级摘要"""
        tracker = DegradationTracker()
        tracker.record('technical_factors', 'reason1', 'fallback1', 'warning')
        tracker.record('technical_factors', 'reason2', 'fallback2', 'warning')
        tracker.record('kline_data', 'reason3', 'fallback3', 'error')
        
        summary = tracker.get_summary()
        assert summary['total'] == 3
        assert summary['by_severity'] == {'warning': 2, 'error': 1}
        assert summary['by_component'] == {'technical_factors': 2, 'kline_data': 1}
        assert summary['confidence_penalty'] == 0.5  # -50%


class TestScoringServiceDegradation:
    """测试评分服务的降级追踪"""
    
    @pytest.fixture
    def scoring_service(self):
        """创建评分服务实例"""
        kline_repo = Mock()
        stock_repo = Mock()
        factor_adapter = Mock()
        
        return OpportunityScoringService(
            kline_repo=kline_repo,
            stock_repo=stock_repo,
            factor_adapter=factor_adapter,
        )
    
    def test_factor_calculation_degradation(self, scoring_service):
        """测试因子计算失败时记录降级"""
        # Mock factor_adapter 返回 None（模拟 TA-Lib 缺失）
        scoring_service.factor_adapter.calculate = Mock(return_value=None)
        
        from application.services.scoring.degradation_tracker import DegradationTracker
        tracker = DegradationTracker()
        
        klines = [
            {'date': '2026-09-01', 'close': 100, 'volume': 1000, 'open': 99, 'high': 101, 'low': 98},
            {'date': '2026-09-02', 'close': 102, 'volume': 1200, 'open': 100, 'high': 103, 'low': 99},
        ]
        
        factors = scoring_service._calculate_factors(klines, tracker)
        
        # 应该记录了降级
        degradations = tracker.get_degradations()
        assert len(degradations) > 0
        
        # 检查是否记录了 RSI 降级
        rsi_degradations = [d for d in degradations if d.get('factor') == 'rsi14']
        assert len(rsi_degradations) == 1
        assert rsi_degradations[0]['component'] == 'technical_factors'
        assert rsi_degradations[0]['severity'] == 'warning'
    
    def test_score_includes_degradation_info(self, scoring_service):
        """测试评分结果包含降级信息"""
        # Mock 依赖
        scoring_service.factor_adapter.calculate = Mock(return_value=None)
        scoring_service.stock_repo.get_by_symbol = Mock(return_value={
            'symbol': '688981',
            'name': '中芯国际',
            'industry': '半导体'
        })
        
        klines = [
            {'date': '2026-09-01', 'close': 100, 'volume': 1000, 'open': 99, 'high': 101, 'low': 98},
        ] * 60  # 足够的数据点
        
        fundamental = {
            'pe_ratio': 20,
            'roe': 15,
            'revenue_growth': 10,
        }
        
        result = scoring_service._score_single_stock(
            symbol='688981',
            klines=klines,
            fundamental=fundamental,
            filters={'technical': [], 'fundamental': []},
        )
        
        # 检查返回结果包含降级字段
        assert 'degradations' in result
        assert 'degradation_summary' in result
        assert isinstance(result['degradations'], list)
        assert isinstance(result['degradation_summary'], dict)
        
        # 检查置信度是否调整
        assert 'confidence' in result
        summary = result['degradation_summary']
        if summary['total'] > 0:
            # 有降级时置信度应该被惩罚
            assert summary['confidence_penalty'] < 1.0


class TestDegradationIntegration:
    """端到端测试：降级信息从服务到 API"""
    
    def test_degradation_visible_in_api_response(self):
        """测试降级信息在 API 响应中可见"""
        # 这个测试需要完整的 API 集成
        # TODO: 在 API 路由中添加降级信息传递后补充
        pass


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
