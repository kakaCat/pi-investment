"""stocks.market 推断与回填路径回归（2026-09-11，w-8f2c4cc5）

背景（看板事件 98d2a20f / 60911dd8，共 13 次）：
K 线回填在股票元数据缺失时用 market='unknown' 占位建 stocks 行，而 DB 约束
chk_stocks_market 只允许 'A'/'HK' → CheckViolation → 整批 K 线回填静默失败
（接口仍返回 200，DB 永不落数据，每次请求重复打外网源）。
"""
import re
from pathlib import Path

import pytest

from adapters.shared.market_helpers import infer_market

REPO_ROOT = Path(__file__).resolve().parents[2]

# DB 约束允许的取值（chk_stocks_market: market IN ('A','HK')）
ALLOWED_MARKETS = {'A', 'HK'}


@pytest.mark.parametrize('symbol,expected', [
    ('688825', 'A'),        # 科创板仍是 A 股市场（事件 98d2a20f 的标的）
    ('688825.SH', 'A'),
    ('600519', 'A'),
    ('000001', 'A'),
    ('300677', 'A'),
    ('430047', 'A'),        # 北交所
    ('920001', 'A'),
    ('00700', 'HK'),
    ('09988.HK', 'HK'),
    ('HK00700', 'HK'),
    ('hk00700', 'HK'),
])
def test_infer_market_supported(symbol, expected):
    assert infer_market(symbol) == expected


@pytest.mark.parametrize('symbol', [None, '', '   ', 'abc', '1234567', '123', 'HKABC', '68882A', 123456])
def test_infer_market_unknown_returns_none(symbol):
    """无法判定时必须返回 None —— 调用方据此跳过，而不是写必违反约束的 'unknown'"""
    assert infer_market(symbol) is None


def test_infer_market_never_returns_illegal_value():
    """对任意输入，返回值要么是约束允许值，要么是 None（绝不产生非法 market）"""
    corpus = ['688825', '600519', '00700', 'X', '', '0000000', 'HK', '1.2.3', ' 600519 ', 'abc.HK']
    corpus += [str(i) for i in range(0, 100000, 977)]
    for symbol in corpus:
        assert infer_market(symbol) in ALLOWED_MARKETS or infer_market(symbol) is None


def _source(rel_path: str) -> str:
    return (REPO_ROOT / rel_path).read_text(encoding='utf-8')


@pytest.mark.parametrize('rel_path', [
    'adapters/outbound/datasources/manager.py',
    'adapters/outbound/repositories/kline_repository.py',
])
def test_no_unknown_market_placeholder_left(rel_path):
    """回归护栏：两个自动建 stocks 行的调用点不得再出现 market='unknown'"""
    src = _source(rel_path)
    assert not re.search(r"market\s*=\s*['\"]unknown['\"]", src), (
        f'{rel_path} 仍存在 market=\'unknown\' 占位（必然违反 chk_stocks_market）')


def test_backfill_uses_infer_market():
    """回归护栏：回填路径必须调用 infer_market，且无法推断时显式跳过"""
    src = _source('adapters/outbound/datasources/manager.py')
    assert 'infer_market' in src
    assert '无法从代码推断 market' in src


def test_db_constraint_matches_allowlist():
    """模型层约束与推断器允许集必须一致（跨层契约）"""
    src = _source('infrastructure/persistence/orm/models/stock.py')
    m = re.search(r"CheckConstraint\((.*?)name='chk_stocks_market'", src, re.S)
    assert m, 'chk_stocks_market 约束未找到'
    allowed = set(re.findall(r"'([A-Z]{1,4})'", m.group(1)))
    assert allowed == ALLOWED_MARKETS, f'DB 约束允许集变化：{allowed}，请同步 infer_market'
