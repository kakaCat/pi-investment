# tests/test_financial_repository.py
import pytest
from datetime import date
from adapters.outbound.repositories import FinancialRepository


@pytest.fixture
def financial_repo():
    """创建FinancialRepository实例"""
    repo = FinancialORMRepository()
    yield repo
    if hasattr(repo, 'db') and repo.db:
        repo.db.close()


@pytest.fixture
def sample_income_statement():
    """示例利润表数据"""
    return {
        'symbol': '000001.SH',
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


class TestFinancialRepositoryIncomeStatements:
    """利润表操作测试"""

    def test_save_income_statement(self, financial_repo, sample_income_statement):
        """测试保存单条利润表数据"""
        # 先插入股票基础数据（满足外键约束）
        if financial_repo.db:
            cursor = financial_repo.db.cursor()
            cursor.execute("""
                INSERT INTO quant.stocks (symbol, name, market)
                VALUES ('000001.SH', '浦发银行', 'SH')
                ON CONFLICT (symbol) DO NOTHING
            """)
            financial_repo.db.commit()
            cursor.close()

        # 保存数据
        financial_repo.save_income_statement(sample_income_statement)

        # 查询验证
        result = financial_repo.get_income_statements(
            symbol='000001.SH',
            period_type='Y',
            limit=1
        )

        assert len(result) == 1
        assert result[0]['symbol'] == '000001.SH'
        assert result[0]['revenue'] == 120000000000.0
        assert result[0]['gross_margin'] == 73.33

    def test_batch_get_latest_income_statements(self, financial_repo):
        """测试批量查询最新利润表数据"""
        # 准备测试数据 - 插入多只股票的数据
        symbols = ['000001.SH', '000001.SZ', '600036.SH']

        # 先插入股票基础数据（满足外键约束）
        if financial_repo.db:
            cursor = financial_repo.db.cursor()
            for symbol in symbols:
                market = symbol.split('.')[1]
                name = {'000001.SH': '浦发银行', '000001.SZ': '平安银行', '600036.SH': '招商银行'}[symbol]
                cursor.execute("""
                    INSERT INTO quant.stocks (symbol, name, market)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (symbol) DO NOTHING
                """, (symbol, name, market))
            financial_repo.db.commit()
            cursor.close()

        # 插入多只股票的数据
        for symbol in symbols:
            data = {
                'symbol': symbol,
                'report_date': date(2025, 12, 31),
                'period_type': 'Y',
                'revenue': 100000000000.0,
                'net_profit': 50000000000.0
            }
            financial_repo.save_income_statement(data)

        # 批量查询
        result = financial_repo.batch_get_latest_income_statements(
            symbols=symbols,
            period_type='Y'
        )

        assert len(result) == 3
        assert '000001.SH' in result
        assert '000001.SZ' in result
        assert '600036.SH' in result
        assert result['000001.SH']['revenue'] == 100000000000.0


@pytest.fixture
def sample_balance_sheet():
    """示例资产负债表数据"""
    return {
        'symbol': '000001.SH',
        'report_date': date(2025, 12, 31),
        'period_type': 'Y',
        'total_assets': 300000000000.0,
        'current_assets': 150000000000.0,
        'non_current_assets': 150000000000.0,
        'total_liabilities': 100000000000.0,
        'current_liabilities': 50000000000.0,
        'non_current_liabilities': 50000000000.0,
        'total_equity': 200000000000.0,
        'parent_equity': 195000000000.0,
        'debt_ratio': 33.33,
        'current_ratio': 3.0
    }


@pytest.fixture
def sample_cash_flow():
    """示例现金流量表数据"""
    return {
        'symbol': '000001.SH',
        'report_date': date(2025, 12, 31),
        'period_type': 'Y',
        'operating_cash_flow': 70000000000.0,
        'investing_cash_flow': -20000000000.0,
        'capex': 15000000000.0,
        'financing_cash_flow': -10000000000.0,
        'dividends_paid': 30000000000.0,
        'free_cash_flow': 55000000000.0,
        'cash_end': 100000000000.0
    }


class TestFinancialRepositoryBalanceSheets:
    """资产负债表操作测试"""

    def test_save_balance_sheet(self, financial_repo, sample_balance_sheet):
        """测试保存资产负债表"""
        # 先插入股票基础数据（满足外键约束）
        if financial_repo.db:
            cursor = financial_repo.db.cursor()
            cursor.execute("""
                INSERT INTO quant.stocks (symbol, name, market)
                VALUES ('000001.SH', '浦发银行', 'SH')
                ON CONFLICT (symbol) DO NOTHING
            """)
            financial_repo.db.commit()
            cursor.close()

        financial_repo.save_balance_sheet(sample_balance_sheet)

        result = financial_repo.get_balance_sheets(
            symbol='000001.SH',
            period_type='Y',
            limit=1
        )

        assert len(result) == 1
        assert result[0]['total_assets'] == 300000000000.0
        assert result[0]['debt_ratio'] == 33.33


class TestFinancialRepositoryCashFlows:
    """现金流量表操作测试"""

    def test_save_cash_flow(self, financial_repo, sample_cash_flow):
        """测试保存现金流量表"""
        # 先插入股票基础数据（满足外键约束）
        if financial_repo.db:
            cursor = financial_repo.db.cursor()
            cursor.execute("""
                INSERT INTO quant.stocks (symbol, name, market)
                VALUES ('000001.SH', '浦发银行', 'SH')
                ON CONFLICT (symbol) DO NOTHING
            """)
            financial_repo.db.commit()
            cursor.close()

        financial_repo.save_cash_flow(sample_cash_flow)

        result = financial_repo.get_cash_flows(
            symbol='000001.SH',
            period_type='Y',
            limit=1
        )

        assert len(result) == 1
        assert result[0]['operating_cash_flow'] == 70000000000.0
        assert result[0]['free_cash_flow'] == 55000000000.0
