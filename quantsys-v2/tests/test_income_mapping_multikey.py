"""利润表映射键口径回归：英文键 / 中文键双兼容（2026-09-13，w-32314d00）

缺口来源（实测）：provider 键口径不一——
  · eastmoney_direct / tushare 等返回英文键（revenue / total_cost / net_profit / basic_eps …）
  · sina_web / akshare-financial 返回中文键（营业总收入 / 营业收入 / 营业成本 / 净利润 / 基本每股收益 / 报告日）

原 _map_income_rows 只读英文键，中文键的行在 row.get("report_date") 处即被丢弃 →
那些标的被记成 no_data（实测 5 只样本全部 no_data，而 provider 明明返回了 100+ 期数据）。

中文键名取自本机对 provider 的实测返回（financial_data_service_adapter，2026-09-13 抓 600519 的真实行）。
"""
import pytest

from infrastructure.jobs.financial_statement_update_job import (
    _dedup_universe,
    _map_income_rows,
    _normalize_symbol,
)


# 中文键样本（键名与实测一致；数值取 600519 2026 中报量级）
CN_ROW = {
    '报告日': '20260630',
    '营业总收入': 92278072083.21,
    '营业收入': 92278072083.21,
    '营业成本': 9638248235.61,
    '营业利润': 62000000000.0,
    '利润总额': 61800000000.0,
    '净利润': 44516880421.86,
    '归属于母公司所有者的净利润': 44516880421.86,
    '基本每股收益': 35.57,
    '稀释每股收益': 35.55,
}

EN_ROW = {
    'report_date': '2026-06-30',
    'total_revenue': 92278072083.21,
    'operating_revenue': 92278072083.21,
    'total_cost': 9638248235.61,
    'gross_margin': 89.5552,
    'operating_profit': 62000000000.0,
    'total_profit': 61800000000.0,
    'net_profit': 44516880421.86,
    'parent_net_profit': 44516880421.86,
    'basic_eps': 35.57,
}


def test_chinese_keys_are_mapped():
    recs = _map_income_rows('600519', [CN_ROW])
    assert len(recs) == 1
    r = recs[0]
    assert r['symbol'] == '600519'
    assert r['report_date'] == '2026-06-30'
    assert r['period_type'] == 'Q'
    assert r['revenue'] == 92278072083.21
    assert r['operating_revenue'] == 92278072083.21
    assert r['operating_cost'] == 9638248235.61
    assert r['net_profit'] == 44516880421.86
    assert r['net_profit_parent'] == 44516880421.86
    assert r['eps'] == 35.57
    assert r['eps_diluted'] == 35.55


def test_chinese_keys_derive_gross_margin_on_operating_basis():
    """provider 未给毛利率时，按 (营业收入-营业成本)/营业收入×100 推导。"""
    r = _map_income_rows('600519', [CN_ROW])[0]
    expected = round((92278072083.21 - 9638248235.61) / 92278072083.21 * 100, 4)
    assert r['gross_margin'] == expected
    assert r['gross_profit'] == pytest.approx(92278072083.21 - 9638248235.61)


def test_english_keys_still_work():
    """回归：原有英文键路径不能被改坏。"""
    r = _map_income_rows('600519', [EN_ROW])[0]
    assert r['revenue'] == 92278072083.21
    assert r['gross_margin'] == 89.5552      # provider 给了就用它的，不覆盖
    assert r['eps'] == 35.57


def test_row_without_report_date_is_dropped():
    assert _map_income_rows('600519', [{'营业收入': 1.0}]) == []


def test_row_without_revenue_or_margin_is_dropped():
    assert _map_income_rows('600519', [{'报告日': '20260630', '销售费用': 1.0}]) == []


def test_annual_report_period_type():
    row = dict(CN_ROW)
    row['报告日'] = '20251231'
    r = _map_income_rows('600519', [row])[0]
    assert r['report_date'] == '2025-12-31' and r['period_type'] == 'Y'


def test_universe_symbols_are_normalized_to_bare_codes():
    """扫描宇宙里 24/367 带交易所后缀——provider 取不到数、落库撞 FK，必须先归一。"""
    assert _normalize_symbol('000999.SZ') == '000999'
    assert _normalize_symbol('688981.SH') == '688981'
    assert _normalize_symbol('600519') == '600519'
    assert _dedup_universe(['000999.SZ', '000999', '688981.SH', '600519']) == [
        '000999', '688981', '600519']


def test_margin_falls_back_to_total_revenue_when_operating_revenue_missing():
    """没有营业成本口径的收入时回退营业总收入——保住旧契约（revenue - total_cost），
    同时记录口径：同时存在时优先用营业收入。"""
    row = {k: v for k, v in CN_ROW.items() if k != '营业收入'}
    r = _map_income_rows('600519', [row])[0]
    assert r['revenue'] == 92278072083.21
    assert r['gross_profit'] == pytest.approx(92278072083.21 - 9638248235.61)
    assert r['gross_margin'] is not None      # 回退口径下仍推导


def test_operating_basis_wins_when_both_present_and_differ():
    """同时有营业总收入与营业收入（金融股二者不等）时，毛利按营业收入口径算。"""
    row = dict(CN_ROW)
    row['营业总收入'] = 1000.0
    row['营业收入'] = 800.0
    row['营业成本'] = 600.0
    r = _map_income_rows('600519', [row])[0]
    assert r['gross_profit'] == pytest.approx(200.0)      # 800 - 600，而不是 1000 - 600
    assert r['gross_margin'] == pytest.approx(25.0)
    assert r['revenue'] == 1000.0
