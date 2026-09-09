"""竞争分析 API 测试"""
import pytest
from fastapi.testclient import TestClient
from adapters.inbound.fastapi_app.main import app

client = TestClient(app)


class TestCompetitionAnalysisAPI:
    """竞争分析 API 测试套件"""

    def test_get_competition_analysis_success(self):
        """测试获取竞争分析（成功）"""
        # 使用白酒行业龙头贵州茅台
        response = client.get("/api/analysis/competition/600519")

        assert response.status_code == 200
        data = response.json()

        assert data["success"] is True
        assert "data" in data

        result = data["data"]
        assert result["symbol"] == "600519"
        assert result["companyName"] == "贵州茅台"
        assert "industry" in result
        assert result["industry"]["level2"] == "制造业-酒、饮料和精制茶制造业"
        assert "marketSize" in result
        assert result["marketSize"]["industryRank"] >= 1
        assert result["marketSize"]["marketShare"] > 0
        assert "competitors" in result
        assert isinstance(result["competitors"], list)
        assert "competitiveAdvantages" in result
        assert "competitiveDisadvantages" in result
        assert "summary" in result
        assert len(result["summary"]) > 0

    def test_get_competition_analysis_without_financial(self):
        """测试获取竞争分析（不包含财务对比）"""
        response = client.get("/api/analysis/competition/600519?include_financial=false")

        assert response.status_code == 200
        data = response.json()
        result = data["data"]

        # 不应该包含 financialComparison 或者为 None
        assert result.get("financialComparison") is None

    def test_get_competition_analysis_with_financial(self):
        """测试获取竞争分析（包含财务对比）"""
        response = client.get("/api/analysis/competition/600519?include_financial=true")

        assert response.status_code == 200
        data = response.json()
        result = data["data"]

        assert "financialComparison" in result
        assert result["financialComparison"] is not None
        assert "metrics" in result["financialComparison"]
        assert "data" in result["financialComparison"]
        assert len(result["financialComparison"]["data"]) > 0

    def test_get_competition_analysis_not_found(self):
        """测试股票不存在"""
        response = client.get("/api/analysis/competition/999999")

        assert response.status_code == 404
        data = response.json()
        assert "error" in data

    def test_get_competition_analysis_invalid_symbol(self):
        """测试无效股票代码"""
        # API 层面不做格式校验，由 service 层处理
        response = client.get("/api/analysis/competition/ABC123")

        # 应该返回 404（股票不存在）
        assert response.status_code == 404

    def test_competition_analysis_response_structure(self):
        """测试响应结构完整性"""
        response = client.get("/api/analysis/competition/000858")  # 五粮液

        assert response.status_code == 200
        data = response.json()
        result = data["data"]

        # 验证所有必填字段
        required_fields = [
            "symbol", "companyName", "industry", "marketSize",
            "competitors", "competitiveAdvantages",
            "competitiveDisadvantages", "summary"
        ]

        for field in required_fields:
            assert field in result, f"Missing required field: {field}"

        # 验证嵌套结构
        assert "level1" in result["industry"]
        assert "level2" in result["industry"]

        assert "totalMarketCap" in result["marketSize"]
        assert "industryRank" in result["marketSize"]
        assert "marketShare" in result["marketSize"]

        # 验证 competitors 数组元素结构
        if result["competitors"]:
            competitor = result["competitors"][0]
            assert "symbol" in competitor
            assert "name" in competitor
            assert "marketCap" in competitor
            assert "marketShare" in competitor
            assert "competitivePosition" in competitor
            assert competitor["competitivePosition"] in ["leader", "second_tier", "follower"]

    def test_competition_analysis_competitors_sorted(self):
        """测试竞争对手按市值排序"""
        response = client.get("/api/analysis/competition/600519")

        assert response.status_code == 200
        data = response.json()
        competitors = data["data"]["competitors"]

        if len(competitors) > 1:
            # 验证市值降序排列
            for i in range(len(competitors) - 1):
                assert competitors[i]["marketCap"] >= competitors[i + 1]["marketCap"]

    def test_competition_analysis_market_share_sum(self):
        """测试市占率计算合理性"""
        response = client.get("/api/analysis/competition/600519")

        assert response.status_code == 200
        data = response.json()
        result = data["data"]

        # 目标公司市占率 + 竞争对手市占率之和应该 <= 100%
        target_share = result["marketSize"]["marketShare"]
        competitors_share = sum(c["marketShare"] for c in result["competitors"])
        total_share = target_share + competitors_share

        assert 0 < total_share <= 100.1  # 允许微小浮点误差
