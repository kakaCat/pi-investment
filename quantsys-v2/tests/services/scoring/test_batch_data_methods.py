"""批量取数方法测试（Task 1）"""
import pytest
from datetime import datetime, timedelta
from adapters.outbound.repositories.financial_repository import FinancialORMRepository
from adapters.outbound.repositories.fund_flow_repository import FundFlowORMRepository


TEST_SYMBOLS = ['TEST001.SH', 'TEST002.SH']


def _seed_stocks(db, symbols):
    """income_statements / stock_fund_flow 有 symbol 外键，先建股票档案"""
    cursor = db.cursor()
    for s in symbols:
        cursor.execute("""
            INSERT INTO quant.stocks (symbol, name, market, updated_at)
            VALUES (%s, %s, 'SH', NOW())
            ON CONFLICT (symbol) DO NOTHING
        """, (s, f'测试{s}'))
    db.commit()
    cursor.close()


def _cleanup(db, symbols):
    cursor = db.cursor()
    for s in symbols:
        cursor.execute("DELETE FROM quant.income_statements WHERE symbol=%s", (s,))
        cursor.execute("DELETE FROM quant.stock_fund_flow WHERE symbol=%s", (s,))
        cursor.execute("DELETE FROM quant.stocks WHERE symbol=%s", (s,))
    db.commit()
    cursor.close()


@pytest.fixture
def financial_repo(db_connection):
    _seed_stocks(db_connection, TEST_SYMBOLS)
    repo = FinancialORMRepository()
    repo.db = db_connection
    yield repo
    _cleanup(db_connection, TEST_SYMBOLS)


@pytest.fixture
def fund_flow_repo(db_connection):
    _seed_stocks(db_connection, ['TEST001.SH'])
    repo = FundFlowORMRepository()
    repo.db = db_connection
    yield repo
    _cleanup(db_connection, ['TEST001.SH'])


def _insert_income(db, symbol, report_date, gross_margin, period_type='Q'):
    cursor = db.cursor()
    cursor.execute("""
        INSERT INTO quant.income_statements
        (symbol, report_date, period_type, revenue, gross_margin, net_profit)
        VALUES (%s, %s, %s, 1000000, %s, 100000)
    """, (symbol, report_date, period_type, gross_margin))
    db.commit()
    cursor.close()


def test_batch_get_quarterly_margins(financial_repo, db_connection):
    """批量查询近8个季度毛利率，按报告期倒序、每股最多8期"""
    # TEST001 插 10 个季度（应只返回 8 期），TEST002 插 3 期
    base = datetime(2026, 3, 31)
    for i in range(10):
        d = (base - timedelta(days=90 * i)).strftime('%Y-%m-%d')
        _insert_income(db_connection, 'TEST001.SH', d, 30.0 + i)
    for i in range(3):
        d = (base - timedelta(days=90 * i)).strftime('%Y-%m-%d')
        _insert_income(db_connection, 'TEST002.SH', d, 25.0)

    result = financial_repo.batch_get_quarterly_margins(TEST_SYMBOLS, quarters=8)

    assert set(result.keys()) == set(TEST_SYMBOLS)
    assert len(result['TEST001.SH']) == 8
    assert len(result['TEST002.SH']) == 3
    # 倒序：最新一期在前
    dates = [r['report_date'] for r in result['TEST001.SH']]
    assert dates == sorted(dates, reverse=True)
    # 只查 Q，不混入年报
    for r in result['TEST001.SH']:
        assert r['period_type'] == 'Q'
    # 未知股票返回空列表
    assert result.get('NOTEXIST.SH', []) == [] or 'NOTEXIST.SH' not in result


def test_batch_get_latest_flows(fund_flow_repo, db_connection):
    """批量查询近5日资金流，按交易日倒序、每股最多5条"""
    base = datetime(2026, 7, 29)
    cursor = db_connection.cursor()
    for i in range(7):  # 7 天数据，应只返回 5
        d = (base - timedelta(days=i)).strftime('%Y-%m-%d')
        cursor.execute("""
            INSERT INTO quant.stock_fund_flow
            (symbol, trade_date, close_price, change_pct, main_net_inflow, source)
            VALUES (%s, %s, 10.0, 1.5, %s, 'test')
        """, ('TEST001.SH', d, 1000000 * (i + 1)))
    db_connection.commit()
    cursor.close()

    result = fund_flow_repo.batch_get_latest_flows(['TEST001.SH'], days=5)

    assert len(result['TEST001.SH']) == 5
    dates = [str(r['trade_date']) for r in result['TEST001.SH']]
    assert dates == sorted(dates, reverse=True)
    # 倒序第一条是最新日期的净流入（i=0 → 1000000）
    assert float(result['TEST001.SH'][0]['main_net_inflow']) == 1000000.0
