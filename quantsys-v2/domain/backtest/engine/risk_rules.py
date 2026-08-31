"""
Pre-Trade Risk Rule Engine

Individual risk check functions. Each is a pure function that reads from
DataService but does not mutate state.

Every check returns the same structure:
    {
        passed: bool,    # True if the check passes
        rule: str,       # Rule name identifier
        detail: str,     # Human-readable explanation
        severity: str    # 'error' (block trade) or 'warning' (informational)
    }
"""

from datetime import datetime, timedelta


def _get_kline_repo():
    from adapters.shared.services import get_kline_repo
    return get_kline_repo()


def _get_stock_repo():
    from adapters.shared.services import get_stock_repo
    return get_stock_repo()


def _get_portfolio_repo():
    from adapters.shared.services import get_portfolio_repo
    return get_portfolio_repo()


def _get_risk_repo():
    from adapters.shared.services import get_risk_repo
    return get_risk_repo()


def _get_factor_repo():
    from adapters.shared.services import get_factor_repo
    return get_factor_repo()


def check_position_size(ds, symbol, proposed_quantity, account_balance) -> dict:
    """单只股票仓位不超过总资金20%"""
    latest = _get_kline_repo().get_latest_daily_kline(symbol)

    if not latest or not latest.get("close"):
        return {
            "passed": True,
            "rule": "position_size",
            "detail": "无法获取最新价格，跳过仓位检查",
            "severity": "warning",
        }

    current_price = latest["close"]
    if current_price <= 0:
        return {
            "passed": True,
            "rule": "position_size",
            "detail": "最新价格为0，跳过仓位检查",
            "severity": "warning",
        }

    proposed_value = proposed_quantity * current_price

    if isinstance(account_balance, dict):
        total_assets = account_balance.get("total_assets", 0) or 1000000
    else:
        total_assets = account_balance or 1000000

    if total_assets <= 0:
        total_assets = 1000000

    ratio = proposed_value / total_assets

    if ratio > 0.20:
        return {
            "passed": False,
            "rule": "position_size",
            "detail": f"单只股票仓位{ratio:.1%}超过总资金20%上限",
            "severity": "error",
        }

    return {
        "passed": True,
        "rule": "position_size",
        "detail": f"仓位比例{ratio:.1%}在允许范围内",
        "severity": "warning",
    }


def check_portfolio_concentration(ds, symbol, proposed_value, total_value) -> dict:
    """同行业持仓不超过总仓位40%"""
    stock_info = _get_stock_repo().get_by_symbol(symbol)

    if not stock_info:
        return {
            "passed": True,
            "rule": "portfolio_concentration",
            "detail": "无法获取股票行业信息，跳过集中度检查",
            "severity": "warning",
        }

    sector = stock_info.get("industry") or "未知"

    holdings = _get_portfolio_repo().get_all_holdings()
    sector_value = proposed_value or 0
    for h in holdings:
        if h.get("sector") == sector:
            sector_value += h.get("total_invested", 0) or 0

    if total_value and total_value > 0:
        ratio = sector_value / total_value
    else:
        ratio = 0.0

    if ratio > 0.40:
        return {
            "passed": False,
            "rule": "portfolio_concentration",
            "detail": f"同行业({sector})持仓{ratio:.1%}超过40%上限",
            "severity": "error",
        }

    return {
        "passed": True,
        "rule": "portfolio_concentration",
        "detail": f"行业{sector}持仓{ratio:.1%}在允许范围内",
        "severity": "warning",
    }


def check_stop_loss(ds, symbol, entry_price, current_price) -> dict:
    """当前价跌破止损线（-8%）"""
    if entry_price is None or current_price is None or entry_price <= 0 or current_price <= 0:
        return {
            "passed": True,
            "rule": "stop_loss",
            "detail": "价格数据无效，跳过止损检查",
            "severity": "warning",
        }

    change_pct = (current_price - entry_price) / entry_price

    if change_pct <= -0.08:
        return {
            "passed": False,
            "rule": "stop_loss",
            "detail": f"当前价较入场价下跌{change_pct:.1%}，触发-8%止损线",
            "severity": "error",
        }

    return {
        "passed": True,
        "rule": "stop_loss",
        "detail": f"当前涨跌幅{change_pct:.1%}，未触发止损线",
        "severity": "warning",
    }


def check_daily_drawdown(ds, today_pnl, account_balance) -> dict:
    """日内回撤不超过5%"""
    if isinstance(account_balance, dict):
        total_assets = account_balance.get("total_assets", 0) or 1000000
    else:
        total_assets = account_balance or 1000000

    if total_assets <= 0:
        total_assets = 1000000

    pnl = today_pnl or 0

    if pnl >= 0:
        return {
            "passed": True,
            "rule": "daily_drawdown",
            "detail": "当日盈利，无回撤风险",
            "severity": "warning",
        }

    drawdown_ratio = abs(pnl) / total_assets

    if drawdown_ratio > 0.05:
        return {
            "passed": False,
            "rule": "daily_drawdown",
            "detail": f"日内回撤{drawdown_ratio:.1%}超过5%上限",
            "severity": "error",
        }

    return {
        "passed": True,
        "rule": "daily_drawdown",
        "detail": f"日内回撤{drawdown_ratio:.1%}在允许范围内",
        "severity": "warning",
    }


def check_max_positions(ds) -> dict:
    """同时持仓不超过10只"""
    holdings = _get_portfolio_repo().get_all_holdings()
    position_count = len(holdings)

    if position_count >= 10:
        return {
            "passed": False,
            "rule": "max_positions",
            "detail": f"当前持仓{position_count}只，已达10只上限",
            "severity": "error",
        }

    return {
        "passed": True,
        "rule": "max_positions",
        "detail": f"当前持仓{position_count}只，未达上限",
        "severity": "warning",
    }


def check_blacklist(ds, symbol) -> dict:
    """ST股票、退市风险股拒绝交易"""
    stock_info = _get_stock_repo().get_by_symbol(symbol)

    if not stock_info:
        return {
            "passed": True,
            "rule": "blacklist",
            "detail": "无法获取股票信息，跳过黑名单检查",
            "severity": "warning",
        }

    if stock_info.get("is_st"):
        return {
            "passed": False,
            "rule": "blacklist",
            "detail": f"ST股票{symbol}禁止交易",
            "severity": "error",
        }

    name = stock_info.get("name", "") or ""
    if "退市" in str(name):
        return {
            "passed": False,
            "rule": "blacklist",
            "detail": f"退市风险股{symbol}({name})禁止交易",
            "severity": "error",
        }

    return {
        "passed": True,
        "rule": "blacklist",
        "detail": f"{symbol}不在黑名单中",
        "severity": "warning",
    }


def check_liquidity(ds, symbol, proposed_quantity) -> dict:
    """日均成交量检查，委托量不超过日均20%"""
    end_date = datetime.now().strftime("%Y-%m-%d")
    start_date = (datetime.now() - timedelta(days=60)).strftime("%Y-%m-%d")

    klines_df = _get_kline_repo().get_daily_klines(symbol, start_date, end_date)

    if klines_df is None or klines_df.is_empty() or len(klines_df) < 5:
        return {
            "passed": True,
            "rule": "liquidity",
            "detail": "流动性数据不足（需要至少5个交易日），跳过检查",
            "severity": "warning",
        }

    klines = klines_df.to_dicts()
    volumes = [k.get("volume", 0) or 0 for k in klines]
    recent_volumes = volumes[-min(20, len(volumes)):]
    avg_volume = sum(recent_volumes) / len(recent_volumes) if recent_volumes else 0

    if avg_volume <= 0:
        return {
            "passed": True,
            "rule": "liquidity",
            "detail": "日均成交量为0，跳过流动性检查",
            "severity": "warning",
        }

    ratio = proposed_quantity / avg_volume

    if ratio > 0.20:
        return {
            "passed": False,
            "rule": "liquidity",
            "detail": f"委托量{proposed_quantity}超过日均成交量{avg_volume:.0f}的20%（{ratio:.1%}）",
            "severity": "error",
        }

    return {
        "passed": True,
        "rule": "liquidity",
        "detail": f"委托量为日均成交量{avg_volume:.0f}的{ratio:.1%}",
        "severity": "warning",
    }


# ===========================================================================
# 组合风险规则（Portfolio Risk Rules）
# ===========================================================================

def check_sector_concentration(ds, symbol, proposed_value, total_value, threshold=0.40) -> dict:
    """行业集中度检查，单行业持仓不超过阈值（默认40%）"""
    stock_info = _get_stock_repo().get_by_symbol(symbol)

    if not stock_info:
        return {
            "passed": True,
            "rule": "sector_concentration",
            "detail": "无法获取股票行业信息，跳过行业集中度检查",
            "severity": "warning",
        }

    sector = stock_info.get("industry") or "未知"
    holdings = _get_portfolio_repo().get_all_holdings()

    sector_value = proposed_value or 0
    for h in holdings:
        if h.get("sector") == sector:
            sector_value += h.get("total_invested", 0) or 0

    if total_value and total_value > 0:
        ratio = sector_value / total_value
    else:
        ratio = 0.0

    if ratio > threshold:
        return {
            "passed": False,
            "rule": "sector_concentration",
            "detail": f"行业{sector}持仓{ratio:.1%}超过{threshold:.0%}上限",
            "severity": "error",
        }

    return {
        "passed": True,
        "rule": "sector_concentration",
        "detail": f"行业{sector}持仓{ratio:.1%}在允许范围内",
        "severity": "warning",
    }


def check_correlation_risk(ds, symbol, holdings_symbols, threshold=0.80) -> dict:
    """持仓相关性风险检查，高相关持仓预警（相关系数>阈值）"""
    if not holdings_symbols or len(holdings_symbols) == 0:
        return {
            "passed": True,
            "rule": "correlation_risk",
            "detail": "无现有持仓，跳过相关性检查",
            "severity": "warning",
        }

    # 获取目标股票的历史数据
    end_date = datetime.now().strftime("%Y-%m-%d")
    start_date = (datetime.now() - timedelta(days=90)).strftime("%Y-%m-%d")

    target_klines_df = _get_kline_repo().get_daily_klines(symbol, start_date, end_date)
    if target_klines_df is None or target_klines_df.is_empty() or len(target_klines_df) < 20:
        return {
            "passed": True,
            "rule": "correlation_risk",
            "detail": "目标股票历史数据不足，跳过相关性检查",
            "severity": "warning",
        }

    target_klines = target_klines_df.to_dicts()
    target_returns = _calculate_returns([k.get("close", 0) for k in target_klines])

    high_corr_symbols = []
    for holding_symbol in holdings_symbols:
        if holding_symbol == symbol:
            continue

        holding_klines_df = _get_kline_repo().get_daily_klines(holding_symbol, start_date, end_date)
        if holding_klines_df is None or holding_klines_df.is_empty() or len(holding_klines_df) < 20:
            continue

        holding_klines = holding_klines_df.to_dicts()
        holding_returns = _calculate_returns([k.get("close", 0) for k in holding_klines])

        # 计算相关系数
        corr = _calculate_correlation(target_returns, holding_returns)
        if corr is not None and corr > threshold:
            high_corr_symbols.append((holding_symbol, corr))

    if high_corr_symbols:
        symbols_str = ", ".join([f"{s}({c:.2f})" for s, c in high_corr_symbols[:3]])
        return {
            "passed": False,
            "rule": "correlation_risk",
            "detail": f"与现有持仓高度相关（>{threshold:.0%}）: {symbols_str}",
            "severity": "warning",
        }

    return {
        "passed": True,
        "rule": "correlation_risk",
        "detail": "与现有持仓相关性在合理范围内",
        "severity": "warning",
    }


def check_beta_exposure(ds, symbol, portfolio_beta_range=(0.5, 1.5)) -> dict:
    """Beta暴露检查，组合Beta应在合理范围内"""
    # 获取股票的Beta值（从因子数据或风险指标）
    try:
        risk_metrics = _get_risk_repo().get_latest_risk_metrics(symbol)
        if risk_metrics and risk_metrics.get("beta") is not None:
            beta = risk_metrics["beta"]
        else:
            # 如果没有风险指标，尝试从因子获取
            factors = _get_factor_repo().get_latest_factors(symbol)
            beta = factors.get("beta") if factors else None
    except Exception:
        beta = None

    if beta is None:
        return {
            "passed": True,
            "rule": "beta_exposure",
            "detail": "无法获取Beta数据，跳过Beta暴露检查",
            "severity": "warning",
        }

    min_beta, max_beta = portfolio_beta_range

    if beta < min_beta or beta > max_beta:
        return {
            "passed": False,
            "rule": "beta_exposure",
            "detail": f"股票Beta={beta:.2f}超出组合范围[{min_beta:.2f}, {max_beta:.2f}]",
            "severity": "warning",
        }

    return {
        "passed": True,
        "rule": "beta_exposure",
        "detail": f"股票Beta={beta:.2f}在合理范围内",
        "severity": "warning",
    }


def check_portfolio_volatility(ds, symbol, max_volatility=0.30) -> dict:
    """组合波动率检查，单只股票波动率不超过阈值"""
    end_date = datetime.now().strftime("%Y-%m-%d")
    start_date = (datetime.now() - timedelta(days=60)).strftime("%Y-%m-%d")

    klines = _get_kline_repo().get_daily_klines(symbol, start_date, end_date)

    if not klines or len(klines) < 20:
        return {
            "passed": True,
            "rule": "portfolio_volatility",
            "detail": "历史数据不足，跳过波动率检查",
            "severity": "warning",
        }

    prices = [k.get("close", 0) for k in klines if k.get("close", 0) > 0]
    if len(prices) < 20:
        return {
            "passed": True,
            "rule": "portfolio_volatility",
            "detail": "有效价格数据不足，跳过波动率检查",
            "severity": "warning",
        }

    returns = _calculate_returns(prices)
    volatility = _calculate_volatility(returns)

    if volatility is None:
        return {
            "passed": True,
            "rule": "portfolio_volatility",
            "detail": "无法计算波动率，跳过检查",
            "severity": "warning",
        }

    if volatility > max_volatility:
        return {
            "passed": False,
            "rule": "portfolio_volatility",
            "detail": f"股票波动率{volatility:.1%}超过{max_volatility:.0%}上限",
            "severity": "warning",
        }

    return {
        "passed": True,
        "rule": "portfolio_volatility",
        "detail": f"股票波动率{volatility:.1%}在允许范围内",
        "severity": "warning",
    }


# ===========================================================================
# 市场风险规则（Market Risk Rules）
# ===========================================================================

def check_market_regime(ds, index_symbol="000001.SH", lookback_days=60) -> dict:
    """市场状态检查（牛市/熊市/震荡），熊市时限制开仓"""
    end_date = datetime.now().strftime("%Y-%m-%d")
    start_date = (datetime.now() - timedelta(days=lookback_days)).strftime("%Y-%m-%d")

    klines = _get_kline_repo().get_daily_klines(index_symbol, start_date, end_date)

    if not klines or len(klines) < 20:
        return {
            "passed": True,
            "rule": "market_regime",
            "detail": "市场数据不足，跳过市场状态检查",
            "severity": "warning",
        }

    prices = [k.get("close", 0) for k in klines if k.get("close", 0) > 0]
    if len(prices) < 20:
        return {
            "passed": True,
            "rule": "market_regime",
            "detail": "有效市场数据不足，跳过检查",
            "severity": "warning",
        }

    # 计算短期和长期均线
    ma_short = sum(prices[-20:]) / 20
    ma_long = sum(prices[-min(60, len(prices)):]) / min(60, len(prices))
    current_price = prices[-1]

    # 判断市场状态
    if current_price > ma_short > ma_long:
        regime = "牛市"
        passed = True
    elif current_price < ma_short < ma_long:
        regime = "熊市"
        passed = False
    else:
        regime = "震荡"
        passed = True

    return {
        "passed": passed,
        "rule": "market_regime",
        "detail": f"当前市场状态: {regime}（指数{index_symbol}）",
        "severity": "warning" if passed else "error",
    }


def check_vix_level(ds, vix_threshold=30.0) -> dict:
    """波动率指数检查，VIX过高时预警（使用A股波动率代理）"""
    # A股没有VIX，使用上证指数近期波动率作为代理
    end_date = datetime.now().strftime("%Y-%m-%d")
    start_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")

    index_symbol = "000001.SH"
    klines = _get_kline_repo().get_daily_klines(index_symbol, start_date, end_date)

    if not klines or len(klines) < 10:
        return {
            "passed": True,
            "rule": "vix_level",
            "detail": "市场波动率数据不足，跳过VIX检查",
            "severity": "warning",
        }

    prices = [k.get("close", 0) for k in klines if k.get("close", 0) > 0]
    if len(prices) < 10:
        return {
            "passed": True,
            "rule": "vix_level",
            "detail": "有效价格数据不足，跳过VIX检查",
            "severity": "warning",
        }

    returns = _calculate_returns(prices)
    volatility = _calculate_volatility(returns)

    if volatility is None:
        return {
            "passed": True,
            "rule": "vix_level",
            "detail": "无法计算市场波动率，跳过检查",
            "severity": "warning",
        }

    # 将年化波动率转换为VIX等效值（百分比）
    vix_proxy = volatility * 100

    if vix_proxy > vix_threshold:
        return {
            "passed": False,
            "rule": "vix_level",
            "detail": f"市场波动率{vix_proxy:.1f}超过{vix_threshold:.0f}阈值，市场恐慌",
            "severity": "warning",
        }

    return {
        "passed": True,
        "rule": "vix_level",
        "detail": f"市场波动率{vix_proxy:.1f}在正常范围内",
        "severity": "warning",
    }


def check_market_breadth(ds, advance_decline_threshold=0.30) -> dict:
    """市场广度检查，涨跌家数比例（需要市场宽度数据）"""
    # 由于缺少实时市场宽度数据，这里使用简化实现
    # 实际应用中应从市场数据源获取涨跌家数

    # 获取样本股票的涨跌情况作为代理
    try:
        # 获取主要指数成分股的涨跌情况
        sample_symbols = _get_sample_symbols(ds)
        if not sample_symbols or len(sample_symbols) < 10:
            return {
                "passed": True,
                "rule": "market_breadth",
                "detail": "样本数据不足，跳过市场广度检查",
                "severity": "warning",
            }

        today = datetime.now().strftime("%Y-%m-%d")
        yesterday = (datetime.now() - timedelta(days=3)).strftime("%Y-%m-%d")

        advancing = 0
        declining = 0

        for symbol in sample_symbols[:50]:  # 限制样本数量
            klines_df = _get_kline_repo().get_daily_klines(symbol, yesterday, today)
            if klines_df is not None and not klines_df.is_empty() and len(klines_df) >= 2:
                klines = klines_df.to_dicts()
                prev_close = klines[-2].get("close", 0)
                curr_close = klines[-1].get("close", 0)
                if prev_close > 0 and curr_close > 0:
                    if curr_close > prev_close:
                        advancing += 1
                    elif curr_close < prev_close:
                        declining += 1

        total = advancing + declining
        if total == 0:
            return {
                "passed": True,
                "rule": "market_breadth",
                "detail": "无法获取市场广度数据，跳过检查",
                "severity": "warning",
            }

        advance_ratio = advancing / total

        if advance_ratio < advance_decline_threshold:
            return {
                "passed": False,
                "rule": "market_breadth",
                "detail": f"市场广度不佳，上涨比例{advance_ratio:.1%}<{advance_decline_threshold:.0%}",
                "severity": "warning",
            }

        return {
            "passed": True,
            "rule": "market_breadth",
            "detail": f"市场广度良好，上涨比例{advance_ratio:.1%}",
            "severity": "warning",
        }
    except Exception:
        return {
            "passed": True,
            "rule": "market_breadth",
            "detail": "市场广度检查异常，跳过",
            "severity": "warning",
        }


# ===========================================================================
# 交易风险规则（Trading Risk Rules）
# ===========================================================================

def check_order_size_vs_adv(ds, symbol, proposed_quantity, adv_threshold=0.20) -> dict:
    """订单量vs日均成交量检查（与liquidity类似但更严格）"""
    end_date = datetime.now().strftime("%Y-%m-%d")
    start_date = (datetime.now() - timedelta(days=60)).strftime("%Y-%m-%d")

    klines = _get_kline_repo().get_daily_klines(symbol, start_date, end_date)

    if not klines or len(klines) < 5:
        return {
            "passed": True,
            "rule": "order_size_vs_adv",
            "detail": "成交量数据不足，跳过订单量检查",
            "severity": "warning",
        }

    volumes = [k.get("volume", 0) or 0 for k in klines]
    recent_volumes = volumes[-min(20, len(volumes)):]
    avg_daily_volume = sum(recent_volumes) / len(recent_volumes) if recent_volumes else 0

    if avg_daily_volume <= 0:
        return {
            "passed": True,
            "rule": "order_size_vs_adv",
            "detail": "日均成交量为0，跳过检查",
            "severity": "warning",
        }

    ratio = proposed_quantity / avg_daily_volume

    if ratio > adv_threshold:
        return {
            "passed": False,
            "rule": "order_size_vs_adv",
            "detail": f"订单量{proposed_quantity}占日均成交量{ratio:.1%}，超过{adv_threshold:.0%}阈值",
            "severity": "error",
        }

    return {
        "passed": True,
        "rule": "order_size_vs_adv",
        "detail": f"订单量占日均成交量{ratio:.1%}，在合理范围内",
        "severity": "warning",
    }


def check_price_impact(ds, symbol, proposed_quantity, impact_threshold=0.02) -> dict:
    """价格冲击估算，大单可能造成的价格影响"""
    end_date = datetime.now().strftime("%Y-%m-%d")
    start_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")

    klines = _get_kline_repo().get_daily_klines(symbol, start_date, end_date)

    if not klines or len(klines) < 10:
        return {
            "passed": True,
            "rule": "price_impact",
            "detail": "历史数据不足，跳过价格冲击估算",
            "severity": "warning",
        }

    # 计算平均成交量和波动率
    volumes = [k.get("volume", 0) or 0 for k in klines]
    avg_volume = sum(volumes) / len(volumes) if volumes else 0

    if avg_volume <= 0:
        return {
            "passed": True,
            "rule": "price_impact",
            "detail": "成交量数据无效，跳过价格冲击估算",
            "severity": "warning",
        }

    prices = [k.get("close", 0) for k in klines if k.get("close", 0) > 0]
    if len(prices) < 10:
        return {
            "passed": True,
            "rule": "price_impact",
            "detail": "价格数据不足，跳过价格冲击估算",
            "severity": "warning",
        }

    returns = _calculate_returns(prices)
    volatility = _calculate_volatility(returns)

    if volatility is None or volatility <= 0:
        volatility = 0.02  # 默认2%日波动率

    # 简化的价格冲击模型: impact = volatility * sqrt(order_size / avg_volume)
    import math
    order_ratio = proposed_quantity / avg_volume
    estimated_impact = volatility * math.sqrt(order_ratio)

    if estimated_impact > impact_threshold:
        return {
            "passed": False,
            "rule": "price_impact",
            "detail": f"预估价格冲击{estimated_impact:.2%}超过{impact_threshold:.0%}阈值",
            "severity": "warning",
        }

    return {
        "passed": True,
        "rule": "price_impact",
        "detail": f"预估价格冲击{estimated_impact:.2%}在可接受范围内",
        "severity": "warning",
    }


def check_trading_hours(ds, avoid_open_minutes=30, avoid_close_minutes=30) -> dict:
    """交易时段检查，避免开盘和收盘时段（9:30-10:00, 14:30-15:00）"""
    now = datetime.now()
    current_time = now.time()

    # A股交易时间: 9:30-11:30, 13:00-15:00
    from datetime import time

    morning_open = time(9, 30)
    # 计算避让结束时间（分钟数可能超过59）
    avoid_end_hour = 9
    avoid_end_minute = 30 + avoid_open_minutes
    if avoid_end_minute >= 60:
        avoid_end_hour += avoid_end_minute // 60
        avoid_end_minute = avoid_end_minute % 60
    morning_avoid_end = time(avoid_end_hour, avoid_end_minute)

    afternoon_close = time(15, 0)
    # 计算避让开始时间
    avoid_start_hour = 14
    avoid_start_minute = 60 - avoid_close_minutes
    if avoid_start_minute < 0:
        avoid_start_hour -= 1
        avoid_start_minute = 60 + avoid_start_minute
    afternoon_avoid_start = time(avoid_start_hour, avoid_start_minute)

    # 检查是否在避免时段
    in_morning_avoid = morning_open <= current_time <= morning_avoid_end
    in_afternoon_avoid = afternoon_avoid_start <= current_time <= afternoon_close

    if in_morning_avoid:
        return {
            "passed": False,
            "rule": "trading_hours",
            "detail": f"当前时间{current_time.strftime('%H:%M')}在开盘避让时段（9:30-{morning_avoid_end.strftime('%H:%M')}）",
            "severity": "warning",
        }

    if in_afternoon_avoid:
        return {
            "passed": False,
            "rule": "trading_hours",
            "detail": f"当前时间{current_time.strftime('%H:%M')}在收盘避让时段（{afternoon_avoid_start.strftime('%H:%M')}-15:00）",
            "severity": "warning",
        }

    return {
        "passed": True,
        "rule": "trading_hours",
        "detail": f"当前时间{current_time.strftime('%H:%M')}适合交易",
        "severity": "warning",
    }


# ===========================================================================
# 辅助函数（Helper Functions）
# ===========================================================================

def _calculate_returns(prices):
    """计算收益率序列"""
    if not prices or len(prices) < 2:
        return []

    returns = []
    for i in range(1, len(prices)):
        if prices[i-1] > 0:
            ret = (prices[i] - prices[i-1]) / prices[i-1]
            returns.append(ret)
    return returns


def _calculate_volatility(returns):
    """计算年化波动率"""
    if not returns or len(returns) < 2:
        return None

    import math

    mean_return = sum(returns) / len(returns)
    variance = sum((r - mean_return) ** 2 for r in returns) / (len(returns) - 1)
    daily_vol = math.sqrt(variance)

    # 年化（假设252个交易日）
    annual_vol = daily_vol * math.sqrt(252)
    return annual_vol


def _calculate_correlation(returns1, returns2):
    """计算两个收益率序列的相关系数"""
    if not returns1 or not returns2:
        return None

    # 对齐长度
    min_len = min(len(returns1), len(returns2))
    if min_len < 10:
        return None

    r1 = returns1[-min_len:]
    r2 = returns2[-min_len:]

    mean1 = sum(r1) / len(r1)
    mean2 = sum(r2) / len(r2)

    numerator = sum((r1[i] - mean1) * (r2[i] - mean2) for i in range(len(r1)))

    import math
    denom1 = math.sqrt(sum((r - mean1) ** 2 for r in r1))
    denom2 = math.sqrt(sum((r - mean2) ** 2 for r in r2))

    if denom1 == 0 or denom2 == 0:
        return None

    correlation = numerator / (denom1 * denom2)
    return correlation


def _get_sample_symbols(ds):
    """获取样本股票列表（用于市场广度计算）"""
    try:
        # 尝试获取所有股票，取前100只作为样本
        stocks = _get_stock_repo().get_all_stocks()
        if stocks:
            return [s.get("symbol") for s in stocks[:100] if s.get("symbol")]
    except Exception:
        pass

    # 回退：使用硬编码的主要股票
    return [
        "000001.SZ", "000002.SZ", "000333.SZ", "000651.SZ", "000858.SZ",
        "600000.SH", "600036.SH", "600000.SH", "600887.SH", "601318.SH",
    ]
