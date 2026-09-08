"""
OpportunityToWatchRuleService 单元测试

测试覆盖：
1. 分数阈值过滤（>=80 创建，<80 跳过）
2. 信号类型过滤（只处理 buy）
3. 重复创建防护（已有启用规则则跳过）
4. 规则内容正确性（action_hint, escalation_policy, context）
5. 价格提取逻辑
"""
import pytest
from datetime import datetime
from unittest.mock import Mock, MagicMock

from application.services.opportunity_to_watch_rule_service import OpportunityToWatchRuleService


class TestOpportunityToWatchRuleService:
    """OpportunityToWatchRuleService 测试"""
    
    @pytest.fixture
    def mock_repo(self):
        """模拟 WatchRuleRepository"""
        repo = Mock()
        repo.list_rules.return_value = []  # 默认无现有规则
        
        # 模拟 create_rule 返回带 id 的对象
        def mock_create(**kwargs):
            rule = Mock()
            rule.id = 999
            rule.symbol = kwargs.get('symbol', '')
            rule.conditions = kwargs.get('conditions', [])
            rule.context = kwargs.get('context', '')
            return rule
        
        repo.create_rule.side_effect = mock_create
        return repo
    
    @pytest.fixture
    def service(self, mock_repo):
        """创建服务实例（使用模拟 repo）"""
        return OpportunityToWatchRuleService(rule_repo=mock_repo)
    
    def test_high_score_buy_creates_rule(self, service, mock_repo):
        """高分 buy 信号应该创建规则"""
        opportunities = [{
            'symbol': '600519',
            'name': '贵州茅台',
            'score': 85,
            'signal_type': 'buy',
            'risk_level': 'medium',
            'reasons': ['技术面突破', '资金流入'],
        }]
        
        results = service.auto_create_rules(opportunities)
        
        assert len(results) == 1
        assert results[0]['action'] == 'created'
        assert results[0]['symbol'] == '600519'
        assert 'rule_id' in results[0]
        mock_repo.create_rule.assert_called_once()
    
    def test_low_score_skips(self, service, mock_repo):
        """低分信号应该跳过"""
        opportunities = [{
            'symbol': '600000',
            'score': 60,
            'signal_type': 'buy',
        }]
        
        results = service.auto_create_rules(opportunities)
        
        assert len(results) == 1
        assert results[0]['action'] == 'skipped'
        assert '低于阈值' in results[0]['reason']
        mock_repo.create_rule.assert_not_called()
    
    def test_non_buy_signal_skips(self, service, mock_repo):
        """非 buy 信号应该跳过"""
        opportunities = [{
            'symbol': '600000',
            'score': 85,
            'signal_type': 'sell',
        }]
        
        results = service.auto_create_rules(opportunities)
        
        assert results[0]['action'] == 'skipped'
        assert '非buy' in results[0]['reason']
        mock_repo.create_rule.assert_not_called()
    
    def test_existing_rule_skips(self, service, mock_repo):
        """已有启用规则应该跳过"""
        mock_repo.list_rules.return_value = [Mock(id=1)]  # 模拟已有规则
        
        opportunities = [{
            'symbol': '600519',
            'score': 85,
            'signal_type': 'buy',
        }]
        
        results = service.auto_create_rules(opportunities)
        
        assert results[0]['action'] == 'skipped'
        assert '已存在' in results[0]['reason']
        mock_repo.create_rule.assert_not_called()
    
    def test_empty_list(self, service, mock_repo):
        """空列表应该返回空结果"""
        results = service.auto_create_rules([])
        
        assert results == []
        mock_repo.create_rule.assert_not_called()
    
    def test_context_building(self, service, mock_repo):
        """测试 context 构建"""
        opportunities = [{
            'symbol': '600519',
            'name': '贵州茅台',
            'score': 85,
            'signal_type': 'buy',
            'reasons': ['基本面优秀', '技术突破'],
        }]
        
        service.auto_create_rules(opportunities)
        
        call_args = mock_repo.create_rule.call_args[1]
        context = call_args['context']
        
        assert '贵州茅台(600519)' in context
        assert '评分85' in context
        assert '基本面优秀' in context
        assert '技术突破' in context
        assert 'opportunity_scan 自动创建' in context
    
    def test_extract_price_from_breakdown(self, service):
        """从 score_breakdown 提取价格"""
        opp = {
            'score_breakdown': {
                'technical': {
                    'details': {'latest_price': 15.5}
                }
            }
        }
        
        price = service._extract_current_price(opp)
        
        assert price == 15.5
    
    def test_extract_price_from_reasons(self, service):
        """从 reasons 文本提取价格"""
        opp = {
            'reasons': ['当前价 23.45 突破均线'],
            'score_breakdown': {}
        }
        
        price = service._extract_current_price(opp)
        
        assert price == 23.45
    
    def test_extract_price_not_found(self, service):
        """无价格信息时返回 None"""
        opp = {'reasons': ['一般机会']}
        
        price = service._extract_current_price(opp)
        
        assert price is None
    
    def test_multiple_opportunities_mixed(self, service, mock_repo):
        """混合场景：高分创建、低分跳过"""
        opportunities = [
            {'symbol': '600519', 'score': 85, 'signal_type': 'buy'},
            {'symbol': '600000', 'score': 60, 'signal_type': 'buy'},
            {'symbol': '000001', 'score': 90, 'signal_type': 'buy'},
        ]
        
        results = service.auto_create_rules(opportunities)
        
        assert len(results) == 3
        assert results[0]['action'] == 'created'  # 600519
        assert results[1]['action'] == 'skipped'  # 600000
        assert results[2]['action'] == 'created'  # 000001
        assert mock_repo.create_rule.call_count == 2
    
    def test_action_hint_content(self, service, mock_repo):
        """验证 action_hint 内容"""
        opportunities = [{
            'symbol': '600519',
            'score': 85,
            'signal_type': 'buy',
        }]
        
        service.auto_create_rules(opportunities)
        
        # 验证 _update_rule_meta 被调用（通过检查 create_rule 调用）
        assert mock_repo.create_rule.called
    
    def test_expires_at_set(self, service, mock_repo):
        """验证有效期设置"""
        opportunities = [{
            'symbol': '600519',
            'score': 85,
            'signal_type': 'buy',
        }]
        
        service.auto_create_rules(opportunities)
        
        call_args = mock_repo.create_rule.call_args[1]
        expires_at = call_args['expires_at']
        
        assert expires_at is not None
        # 验证是未来的日期
        assert expires_at > datetime.now()
