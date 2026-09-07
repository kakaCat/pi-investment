# tests/test_financial_repository.py
# 2026-08-04 重写：对齐 FinancialORMRepository 当前 API
# （upsert_income_statements/get_income_statements/get_balance_sheets/
#   get_financial_data/batch_get_quarterly_margins，生产调用方见
#   financial_analysis_service/financial_statement_update_job/opportunity_scoring_service）。
# 旧 save_*/get_cash_flows/batch_get_latest_income_statements 已无生产调用方，删除。
import pytest
from datetime import date
from adapters.outbound.repositories import FinancialORMRepository

TEST_SYMBOL = '000001.SH'


@pytest.fixture
def financial_repo():
    """创建 FinancialORMRepository 实例"""
    return FinancialORMRepository()


@pytest.fixture(autouse=True)
def clean_test_data(financial_repo):
    """清理测试数据（利润表 upsert 按 symbol+report_date+period_type 去重，可重入）"""
    yield
    from adapters.outbound.repositories.financial_repository import IncomeStatement
    financial_repo.session.query(IncomeStatement).filter(
        IncomeStatement.symbol == TEST_SYMBOL,
        IncomeStatement.report_date == date(2025, 12, 31),
    ).delete()
    financial_repo.session.commit()


@pytest.fixture
def sample_income_statement():
    """示例利润表数据"""
    return {
        'symbol': TEST_SYMBOL,
        'report_date': date(2025, 12, 31),
        'period_type': 'Y',
        'revenue': 120000000000.0,
        'operating_revenue': 118000000000.0,
        'operating_cost': 30000000000.0,
        'gross_profit': 88000000000.0,
        'gross_margin': 73.33,
        'operating_profit': 70000000000.0,
        'total_profit': 72000000000.0,
        'net_profit': 60000000000.0,
        'net_profit_parent': 59000000000.0,
        'eps': 50.0,
        'eps_diluted': 49.5
    }


class TestIncomeStatements:
    """利润表 upsert + 查询（生产链路：financial_statement_update_job 写，analysis_service 读）"""

    def test_upsert_and_get_income_statements(self, financial_repo, sample_income_statement):
        """upsert 写入后可按 symbol+period_type 查询"""
        written = financial_repo.upsert_income_statements([sample_income_statement])
        assert written == 1

        result = financial_repo.get_income_statements(symbol=TEST_SYMBOL, period_type='Y', limit=1)

        assert len(result) >= 1
        assert result[0]['symbol'] == TEST_SYMBOL
        assert float(result[0]['revenue']) == 120000000000.0
        assert float(result[0]['gross_margin']) == pytest.approx(73.33)

    def test_upsert_is_idempotent(self, financial_repo, sample_income_statement):
        """重复 upsert 更新而非报错（on_conflict_do_update）"""
        financial_repo.upsert_income_statements([sample_income_statement])
        updated = {**sample_income_statement, 'revenue': 999.0}
        written = financial_repo.upsert_income_statements([updated])
        assert written == 1

        result = financial_repo.get_income_statements(symbol=TEST_SYMBOL, period_type='Y', limit=1)
        assert float(result[0]['revenue']) == 999.0

    def test_upsert_empty_returns_zero(self, financial_repo):
        assert financial_repo.upsert_income_statements([]) == 0


class TestQueries:
    """查询类方法契约"""

    def test_get_balance_sheets_returns_list(self, financial_repo):
        """查不到返回空列表而非 None（生产按 List[Dict] 消费）"""
        result = financial_repo.get_balance_sheets(symbol='999999.XX', period_type='Y')
        assert result == []

    def test_get_financial_data_none_for_unknown(self, financial_repo):
        """利润表和资产负债表都没有时返回 None"""
        assert financial_repo.get_financial_data('999999.XX') is None

    def test_get_financial_data_merges_income(self, financial_repo, sample_income_statement):
        """有利润表时合并返回 income 键"""
        financial_repo.upsert_income_statements([sample_income_statement])
        data = financial_repo.get_financial_data(TEST_SYMBOL)
        assert data is not None
        assert data['income']['symbol'] == TEST_SYMBOL

    def test_batch_get_quarterly_margins_shape(self, financial_repo):
        """批量查询返回 {symbol: […]} 字典，未知 symbol 给空列表"""
        result = financial_repo.batch_get_quarterly_margins(['999999.XX'], quarters=8)
        assert result == {'999999.XX': []}

    def test_batch_get_quarterly_margins_empty_input(self, financial_repo):
        assert financial_repo.batch_get_quarterly_margins([]) == {}
