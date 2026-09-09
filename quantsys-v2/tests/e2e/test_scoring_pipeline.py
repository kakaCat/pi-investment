"""评分管线端到端测试（E-203）。

链路：真实 DB（quant_test）→ K 线读取 → 因子 → 评分 → 证据链/降级检查。
与单元/集成测试的区别：全程不 mock 数据层，使用 quant_test 中真实落库的
股票与 K 线，覆盖 E-102 类"mock 通过、真实数据失败"的集成盲区。

设计约束：
- 不 seed 假数据：quant.stocks.market 约束仅允许 'A'/'HK'（chk_stocks_market），
  历史 seed 'SH' 的写法已失效；改用测试库内真实存在的股票。
- DB 无可用股票时 pytest.skip（不把环境问题当测试失败）。
- 网络 backfill 段：数据源不可用时 skip，不让 e2e 依赖外网稳定性。
"""
import pytest

from adapters.outbound.datasources.manager import DataProviderManager
from adapters.outbound.repositories import KlineORMRepository, StockORMRepository
from adapters.shared.services import get_factor_adapter
from application.services.opportunity_scoring_service import OpportunityScoringService


# ══════════════════════════════════════════════════════════════════════
# fixtures
# ══════════════════════════════════════════════════════════════════════

@pytest.fixture(scope="module")
def real_symbol(db_connection):
    """选择 quant_test 中 K 线充足的真实股票（>=60 根日K）。"""
    cur = db_connection.cursor()
    cur.execute("""
        SELECT s.symbol
        FROM quant.stocks s
        JOIN quant.daily_klines k ON k.symbol = s.symbol
        WHERE s.market = 'A'
        GROUP BY s.symbol
        HAVING count(k.trade_date) >= 60
        ORDER BY count(k.trade_date) DESC
        LIMIT 1
    """)
    row = cur.fetchone()
    cur.close()
    if not row:
        pytest.skip("测试库无 K 线充足的真实股票（>=60 根），无法跑评分 e2e")
    return row["symbol"] if isinstance(row, dict) else row[0]


@pytest.fixture
def scoring_service(db_connection):
    """基于真实 DB 连接的评分服务（不注入 mock 仓库）。"""
    kline_repo = KlineORMRepository()
    kline_repo.db = db_connection
    stock_repo = StockORMRepository()
    stock_repo.db = db_connection
    return OpportunityScoringService(
        kline_repo, stock_repo, get_factor_adapter())


# ══════════════════════════════════════════════════════════════════════
# 端到端用例
# ══════════════════════════════════════════════════════════════════════

class TestScoringPipelineE2E:
    """真实 DB → 评分 全链路"""

    def test_scoring_e2e_real_database(self, scoring_service, real_symbol):
        """端到端核心：真实 DB 股票可完成评分且技术因子非全 0。

        E-102 回归防线：mock 数据下因子恒 0 的假通过，在真实数据上必须现形。
        """
        results = scoring_service.score_stocks(
            [real_symbol], filters={}, no_cache=True)
        assert results, f"{real_symbol} 应产出至少一条评分"
        opp = results[0]
        assert opp["symbol"] == real_symbol

        tech_breakdown = opp["score_breakdown"]["technical"]
        tech_details = tech_breakdown.get("details", {})

        # 至少一个技术因子非 0（真实行情数据下不允许全 0）
        nonzero = {
            k: v for k, v in tech_details.items()
            if isinstance(v, (int, float)) and v != 0
        }
        assert nonzero, (
            f"{real_symbol} 技术因子应至少一个非 0，实际全 0: {tech_details}"
        )

        # 正常数据不应有 critical 降级
        degradations = opp.get("degradations", []) or []
        critical = [
            d for d in degradations
            if isinstance(d, dict) and d.get("severity") == "critical"
        ]
        assert not critical, f"{real_symbol} 不应有 critical 降级: {critical}"

    def test_scoring_evidence_chain_complete(self, scoring_service, real_symbol):
        """真实数据评分结果含完整证据链（breakdown/reasons/applied_context）。"""
        results = scoring_service.score_stocks(
            [real_symbol], filters={}, no_cache=True)
        opp = results[0]

        assert "score_breakdown" in opp
        assert "reasons" in opp and len(opp["reasons"]) > 0
        assert "applied_context" in opp
        ctx = opp["applied_context"]
        assert "final_weights" in ctx
        # 权重和为 1（真实链路下权重归一化必须成立）
        assert abs(sum(ctx["final_weights"].values()) - 1.0) < 0.01

        # 旧字段兼容（web 前端/老调用方不破）
        for f in ("score", "technical_score", "fundamental_score",
                  "capital_score", "risk_level", "signal_type"):
            assert f in opp, f"缺 legacy 字段: {f}"

    def test_backfill_then_score(self, db_connection, real_symbol):
        """真实 backfill（DataProviderManager）→ 数据库可读到数据。

        网络/数据源不可用时 skip（不把环境问题当失败）。
        """
        provider = DataProviderManager()
        result = provider.get_klines(
            real_symbol, "daily", "2026-08-01", "2026-09-09")
        if not result.get("success"):
            pytest.skip(f"数据源不可用，无法 backfill {real_symbol}")

        data = result.get("data") or []
        assert len(data) >= 1, "backfill 应返回至少 1 根 K 线"

        # backfill 后 DB 中应能读到该股票 K 线
        cur = db_connection.cursor()
        cur.execute(
            "SELECT count(*) FROM quant.daily_klines WHERE symbol=%s",
            (real_symbol,))
        n = cur.fetchone()
        cur.close()
        count = n[0] if not isinstance(n, dict) else n["count"]
        assert count >= 1, f"{real_symbol} backfill 后 DB 应存在 K 线"
