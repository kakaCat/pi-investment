"""竞争分析服务测试"""
import pytest
from unittest.mock import Mock
from domain.competition.service import CompetitionAnalysisService


@pytest.fixture
def mock_repo():
    """Mock repository"""
    repo = Mock()
    return repo


@pytest.fixture
def service(mock_repo):
    """竞争分析服务实例"""
    return CompetitionAnalysisService(mock_repo)


class TestCompetitionAnalysisService:
    """竞争分析服务测试套件"""

    def test_analyze_normal_case(self, service, mock_repo):
        """测试正常流程：贵州茅台"""
        # Mock 数据
        mock_repo.get_stock_info.return_value = {
            "symbol": "600519",
            "name": "贵州茅台",
            "industry": "制造业-酒、饮料和精制茶制造业",
            "market_cap": 17732.40,
            "roe": 32.53,
            "gross_margin": 89.76,
            "net_profit_growth": 1.47,
            "revenue_growth": -0.012
        }

        mock_repo.get_competitors.return_value = [
            {
                "symbol": "600519",
                "name": "贵州茅台",
                "market_cap": 17732.40,
                "roe": 32.53,
                "gross_margin": 89.76,
                "net_profit_growth": 1.47,
                "revenue_growth": -0.012
            },
            {
                "symbol": "000858",
                "name": "五粮液",
                "market_cap": 3984.47,
                "roe": 6.89,
                "gross_margin": 81.43,
                "net_profit_growth": 82.57,
                "revenue_growth": -0.5455
            },
            {
                "symbol": "600809",
                "name": "山西汾酒",
                "market_cap": 1811.16,
                "roe": 33.48,
                "gross_margin": 75.05,
                "net_profit_growth": -19.03,
                "revenue_growth": 0.0752
            }
        ]

        mock_repo.get_industry_totals.return_value = {
            "total_market_cap": 25000.0,
            "company_count": 10,
            "avg_roe": 15.2,
            "avg_gross_margin": 67.3,
            "avg_net_profit_growth": 8.5,
            "avg_revenue_growth": 5.0
        }

        # 执行分析
        result = service.analyze("600519", include_financial=True)

        # 验证结果结构
        assert result["symbol"] == "600519"
        assert result["company_name"] == "贵州茅台"
        assert result["industry"]["level2"] == "制造业-酒、饮料和精制茶制造业"
        assert result["market_size"]["industry_rank"] == 1
        assert result["market_size"]["market_share"] > 70  # 约 71%
        assert len(result["competitors"]) == 2  # 排除自己
        assert result["competitors"][0]["symbol"] == "000858"  # 五粮液
        assert "financial_comparison" in result
        assert len(result["competitive_advantages"]) > 0
        assert "summary" in result

    def test_analyze_stock_not_found(self, service, mock_repo):
        """测试股票不存在"""
        mock_repo.get_stock_info.return_value = None

        result = service.analyze("999999")

        assert "error" in result
        assert result["symbol"] == "999999"
        assert "不存在" in result["error"]

    def test_analyze_missing_industry(self, service, mock_repo):
        """测试缺少行业分类"""
        mock_repo.get_stock_info.return_value = {
            "symbol": "600519",
            "name": "贵州茅台",
            "industry": None,  # 缺少行业
            "market_cap": 17732.40
        }

        result = service.analyze("600519")

        assert "error" in result
        assert "行业分类" in result["error"]

    def test_analyze_no_competitors(self, service, mock_repo):
        """测试行业无其他公司"""
        mock_repo.get_stock_info.return_value = {
            "symbol": "600519",
            "name": "测试公司",
            "industry": "测试行业",
            "market_cap": 100.0
        }
        mock_repo.get_competitors.return_value = []

        result = service.analyze("600519")

        assert "error" in result
        assert "未找到" in result["error"]

    def test_analyze_without_financial(self, service, mock_repo):
        """测试不包含财务对比"""
        mock_repo.get_stock_info.return_value = {
            "symbol": "600519",
            "name": "贵州茅台",
            "industry": "制造业-酒、饮料和精制茶制造业",
            "market_cap": 17732.40,
            "roe": 32.53,
            "gross_margin": 89.76
        }

        mock_repo.get_competitors.return_value = [
            {"symbol": "600519", "name": "贵州茅台", "market_cap": 17732.40}
        ]

        mock_repo.get_industry_totals.return_value = {
            "total_market_cap": 20000.0,
            "avg_roe": 15.0
        }

        result = service.analyze("600519", include_financial=False)

        assert "financial_comparison" not in result or result["financial_comparison"] is None

    def test_classify_position(self, service):
        """测试竞争地位分级"""
        assert service._classify_position(35.0, 1) == "leader"  # 市占率 > 30%
        assert service._classify_position(25.0, 1) == "leader"  # 排名第 1
        assert service._classify_position(10.0, 3) == "second_tier"  # 排名 2-5
        assert service._classify_position(20.0, 2) == "second_tier"  # 市占率 5-30%
        assert service._classify_position(3.0, 7) == "follower"  # 排名 6+
        assert service._classify_position(2.0, 8) == "follower"  # 市占率 < 5%

    def test_extract_competitive_edges(self, service):
        """测试优劣势提取"""
        stock_info = {
            "roe": 32.0,
            "gross_margin": 85.0,
            "net_profit_growth": 10.0,
            "revenue_growth": -5.0,
            "market_cap": 3000.0
        }

        industry_totals = {
            "avg_roe": 15.0,
            "avg_gross_margin": 50.0,
            "avg_net_profit_growth": 8.0,
            "avg_revenue_growth": 5.0,
            "total_market_cap": 10000.0
        }

        advantages, disadvantages = service._extract_competitive_edges(
            stock_info, industry_totals
        )

        # ROE 高于行业 20% 以上应该是优势
        assert any("ROE" in adv for adv in advantages)
        # 毛利率高于行业 20% 以上应该是优势
        assert any("毛利率" in adv for adv in advantages)
        # 营收增长为负应该是劣势
        assert any("营收" in dis for dis in disadvantages)
