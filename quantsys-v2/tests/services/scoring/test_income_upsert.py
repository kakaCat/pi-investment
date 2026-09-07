"""upsert_income_statements 测试"""
import pytest
from adapters.outbound.repositories.financial_repository import FinancialORMRepository


@pytest.fixture
def repo(db_connection):
    r = FinancialORMRepository()
    r.db = db_connection
    cursor = db_connection.cursor()
    cursor.execute("""
        INSERT INTO quant.stocks (symbol, name, market, updated_at)
        VALUES ('TESTUP', '测试upsert', 'SH', NOW())
        ON CONFLICT (symbol) DO NOTHING
    """)
    db_connection.commit()
    cursor.close()
    yield r
    cursor = db_connection.cursor()
    cursor.execute("DELETE FROM quant.income_statements WHERE symbol='TESTUP'")
    cursor.execute("DELETE FROM quant.stocks WHERE symbol='TESTUP'")
    db_connection.commit()
    cursor.close()


def test_upsert_insert_and_update(repo, db_connection):
    """首次插入 + 冲突更新（毛利率改了应覆盖）"""
    records = [
        {'symbol': 'TESTUP', 'report_date': '2026-03-31', 'period_type': 'Q',
         'revenue': 100.0, 'gross_margin': 30.0, 'net_profit': 10.0},
        {'symbol': 'TESTUP', 'report_date': '2025-12-31', 'period_type': 'Y',
         'revenue': 400.0, 'gross_margin': 28.0, 'net_profit': 40.0},
    ]
    n = repo.upsert_income_statements(records)
    assert n == 2

    # 冲突更新
    n = repo.upsert_income_statements([
        {'symbol': 'TESTUP', 'report_date': '2026-03-31', 'period_type': 'Q',
         'revenue': 100.0, 'gross_margin': 35.5, 'net_profit': 10.0},
    ])
    assert n == 1

    rows = repo.get_income_statements('TESTUP', period_type='Q', limit=1)
    assert len(rows) == 1
    assert abs(float(rows[0]['gross_margin']) - 35.5) < 0.01


def test_upsert_empty(repo):
    assert repo.upsert_income_statements([]) == 0
