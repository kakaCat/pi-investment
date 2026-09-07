"""financial_statement_update_job 单元测试（映射与 universe 逻辑，不碰网络）"""
import pytest
from infrastructure.jobs.financial_statement_update_job import (
    _map_income_rows, _dedup_universe,
)


class TestMapIncomeRows:
    def test_quarter_and_year_split(self):
        """12-31 → Y，其他 → Q"""
        rows = [
            {'report_date': '2026-03-31', 'revenue': 100, 'gross_margin': 30.0,
             'net_profit': None, 'parent_net_profit': 10, 'total_cost': 70},
            {'report_date': '2025-12-31', 'revenue': 400, 'gross_margin': 28.0,
             'net_profit': 40, 'total_cost': 288},
        ]
        out = _map_income_rows('600519', rows)
        assert len(out) == 2
        q = [r for r in out if r['period_type'] == 'Q'][0]
        y = [r for r in out if r['period_type'] == 'Y'][0]
        assert q['report_date'] == '2026-03-31'
        assert y['report_date'] == '2025-12-31'
        # net_profit 为空回退 parent_net_profit
        assert q['net_profit'] == 10
        # operating_cost ← total_cost；gross_profit = revenue - total_cost
        assert q['operating_cost'] == 70
        assert q['gross_profit'] == 30

    def test_skips_rows_without_date_or_data(self):
        rows = [
            {'report_date': None, 'revenue': 100},
            {'report_date': '2026-03-31'},  # 无 revenue/gross_margin
            {'report_date': '2026-06-30', 'gross_margin': 25.0},
        ]
        out = _map_income_rows('600519', rows)
        assert len(out) == 1
        assert out[0]['report_date'] == '2026-06-30'

    def test_symbol_format_passthrough(self):
        out = _map_income_rows('600519', [
            {'report_date': '2026-03-31', 'gross_margin': 30.0}])
        assert out[0]['symbol'] == '600519'


class TestDedupUniverse:
    def test_dedup_preserves_order(self):
        assert _dedup_universe(['a', 'b', 'a', 'c', 'b']) == ['a', 'b', 'c']

    def test_empty(self):
        assert _dedup_universe([]) == []
