# -*- coding: utf-8 -*-
"""utils/symbol_classifier 回归测试（2026-09-10 w-23c70356）。

覆盖：399 族恒为指数；歧义代码经 stocks 表核实；含点/非标准代码视为伪代码；
指数排除清单不含真实个股（000001 平安银行不得被排除，否则其成交额缺失告警被吞）。
"""
import pytest

from utils.symbol_classifier import (
    INDEX_WHITELIST,
    index_symbols_for_exclusion,
    is_index_symbol,
    is_pseudo_symbol,
)


@pytest.mark.parametrize("symbol", ["399300", "399001", "399006", "399005", "399905"])
def test_399_family_always_index(symbol):
    assert is_index_symbol(symbol) is True
    assert is_pseudo_symbol(symbol) is True


@pytest.mark.parametrize("symbol", ["600519", "688008", "300750", "000001"])
def test_real_stocks_are_not_index(symbol):
    # 000001 是歧义代码（上证指数 vs 平安银行）：stocks 表有真实记录应判为个股
    assert is_index_symbol(symbol) is False
    assert is_pseudo_symbol(symbol) is False


@pytest.mark.parametrize("symbol", ["600000.SH", "600000.SZ", "TEST", "abc", ""])
def test_non_standard_codes_are_pseudo(symbol):
    assert is_pseudo_symbol(symbol) is True


def test_exclusion_list_excludes_only_confirmed_indexes():
    exclusion = index_symbols_for_exclusion()
    assert "000300" in exclusion
    # 歧义代码不得被排除（真实个股的缺失成交额告警不能被吞）
    assert "000001" not in exclusion
    assert all(s in INDEX_WHITELIST for s in exclusion)
