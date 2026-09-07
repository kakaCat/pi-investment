"""
Stress Test Framework

压力测试框架，用于评估投资组合在极端市场情景下的表现。
支持场景压力测试和历史情景回放。
"""

from datetime import datetime, timedelta
from typing import Dict, List, Optional


def _get_kline_repo():
    from adapters.shared.services import get_kline_repo
    return get_kline_repo()


def _get_portfolio_repo():
    from adapters.shared.services import get_portfolio_repo
    return get_portfolio_repo()


class StressTestScenario:
    """压力测试场景定义"""

    def __init__(self, name: str, description: str, market_shock: float, sector_shocks: Dict[str, float] = None):
        """
        初始化压力测试场景

        Args:
            name: 场景名称
            description: 场景描述
            market_shock: 市场整体冲击（-0.10表示下跌10%）
            sector_shocks: 行业特定冲击 {行业名: 冲击比例}
        """
        self.name = name
        self.description = description
        self.market_shock = market_shock
        self.sector_shocks = sector_shocks or {}


# ===========================================================================
# 预定义压力测试场景
# ===========================================================================

SCENARIO_MARKET_DROP_10 = StressTestScenario(
    name="市场下跌10%",
    description="市场整体下跌10%的温和调整",
    market_shock=-0.10,
)

SCENARIO_MARKET_DROP_20 = StressTestScenario(
    name="市场下跌20%",
    description="市场整体下跌20%的严重调整",
    market_shock=-0.20,
)

SCENARIO_MARKET_DROP_30 = StressTestScenario(
    name="市场下跌30%",
    description="市场整体下跌30%的极端熊市",
    market_shock=-0.30,
)

SCENARIO_2015_CRASH = StressTestScenario(
    name="2015股灾",
    description="2015年6-8月A股股灾情景（市场-40%，科技-50%）",
    market_shock=-0.40,
    sector_shocks={
        "科技": -0.50,
        "互联网": -0.50,
        "券商": -0.45,
        "银行": -0.30,
        "地产": -0.35,
    }
)

SCENARIO_2020_COVID = StressTestScenario(
    name="2020疫情",
    description="2020年2-3月新冠疫情冲击（市场-15%，消费-25%）",
    market_shock=-0.15,
    sector_shocks={
        "餐饮": -0.30,
        "旅游": -0.35,
        "航空": -0.40,
        "消费": -0.25,
        "医药": 0.10,  # 医药逆势上涨
        "科技": -0.05,
    }
)

SCENARIO_SECTOR_ROTATION = StressTestScenario(
    name="行业轮动",
    description="周期性行业轮动（周期+20%，成长-15%）",
    market_shock=0.0,
    sector_shocks={
        "钢铁": 0.20,
        "煤炭": 0.25,
        "有色": 0.18,
        "化工": 0.15,
        "科技": -0.15,
        "医药": -0.12,
        "消费": -0.10,
    }
)

# 所有预定义场景
PREDEFINED_SCENARIOS = [
    SCENARIO_MARKET_DROP_10,
    SCENARIO_MARKET_DROP_20,
    SCENARIO_MARKET_DROP_30,
    SCENARIO_2015_CRASH,
    SCENARIO_2020_COVID,
    SCENARIO_SECTOR_ROTATION,
]


class StressTestEngine:
    """压力测试引擎"""

    def __init__(self, ds):
        """
        初始化压力测试引擎

        Args:
            ds: DataService实例
        """
        self.ds = ds

    def run_scenario(self, scenario: StressTestScenario) -> Dict:
        """
        运行单个压力测试场景

        Args:
            scenario: 压力测试场景

        Returns:
            {
                scenario_name, scenario_description,
                current_portfolio_value, stressed_portfolio_value,
                total_loss, loss_percentage,
                position_impacts: [{symbol, sector, current_value, stressed_value, loss, loss_pct}],
                risk_metrics: {...}
            }
        """
        # 获取当前持仓
        holdings = _get_portfolio_repo().get_all_holdings()
        if not holdings:
            return {
                "scenario_name": scenario.name,
                "scenario_description": scenario.description,
                "current_portfolio_value": 0.0,
                "stressed_portfolio_value": 0.0,
                "total_loss": 0.0,
                "loss_percentage": 0.0,
                "position_impacts": [],
                "risk_metrics": {},
            }

        # 计算当前组合价值
        current_value = 0.0
        stressed_value = 0.0
        position_impacts = []

        for holding in holdings:
            symbol = holding.get("symbol")
            sector = holding.get("sector") or "未知"
            quantity = holding.get("quantity", 0) or 0
            avg_cost = holding.get("avg_cost", 0) or 0

            # 获取当前价格
            latest = _get_kline_repo().get_latest_daily_kline(symbol)
            current_price = latest.get("close") if latest else avg_cost

            position_current_value = quantity * current_price
            current_value += position_current_value

            # 计算压力后价格
            shock = scenario.sector_shocks.get(sector, scenario.market_shock)
            stressed_price = current_price * (1 + shock)
            position_stressed_value = quantity * stressed_price
            stressed_value += position_stressed_value

            position_loss = position_stressed_value - position_current_value
            position_loss_pct = position_loss / position_current_value if position_current_value > 0 else 0.0

            position_impacts.append({
                "symbol": symbol,
                "name": holding.get("name", ""),
                "sector": sector,
                "quantity": quantity,
                "current_price": round(current_price, 2),
                "stressed_price": round(stressed_price, 2),
                "current_value": round(position_current_value, 2),
                "stressed_value": round(position_stressed_value, 2),
                "loss": round(position_loss, 2),
                "loss_pct": round(position_loss_pct, 4),
                "shock_applied": round(shock, 4),
            })

        total_loss = stressed_value - current_value
        loss_percentage = total_loss / current_value if current_value > 0 else 0.0

        # 按损失排序
        position_impacts.sort(key=lambda x: x["loss"])

        # 计算风险指标
        risk_metrics = self._calculate_stress_risk_metrics(position_impacts, current_value)

        return {
            "scenario_name": scenario.name,
            "scenario_description": scenario.description,
            "current_portfolio_value": round(current_value, 2),
            "stressed_portfolio_value": round(stressed_value, 2),
            "total_loss": round(total_loss, 2),
            "loss_percentage": round(loss_percentage, 4),
            "position_impacts": position_impacts,
            "risk_metrics": risk_metrics,
        }

    def run_all_scenarios(self) -> Dict:
        """
        运行所有预定义压力测试场景

        Returns:
            {
                timestamp,
                scenarios: [scenario_result, ...],
                summary: {worst_scenario, best_scenario, avg_loss, ...}
            }
        """
        results = []
        for scenario in PREDEFINED_SCENARIOS:
            result = self.run_scenario(scenario)
            results.append(result)

        # 汇总统计
        summary = self._summarize_scenarios(results)

        return {
            "timestamp": datetime.now().isoformat(),
            "scenarios": results,
            "summary": summary,
        }

    def run_historical_replay(self, start_date: str, end_date: str, index_symbol: str = "000001.SH") -> Dict:
        """
        历史情景回放：基于历史市场数据回放组合表现

        Args:
            start_date: 开始日期
            end_date: 结束日期
            index_symbol: 参考指数代码

        Returns:
            {
                period, index_return, portfolio_return,
                daily_returns: [{date, index_return, portfolio_return}],
                max_drawdown, volatility, sharpe_ratio
            }
        """
        # 获取指数历史数据
        index_klines = _get_kline_repo().get_daily_klines(index_symbol, start_date, end_date)
        if not index_klines or len(index_klines) < 2:
            return {
                "error": "指数历史数据不足",
                "period": f"{start_date} to {end_date}",
            }

        # 获取当前持仓
        holdings = _get_portfolio_repo().get_all_holdings()
        if not holdings:
            return {
                "error": "无持仓数据",
                "period": f"{start_date} to {end_date}",
            }

        # 获取每只持仓的历史数据
        holdings_history = {}
        for holding in holdings:
            symbol = holding.get("symbol")
            klines = _get_kline_repo().get_daily_klines(symbol, start_date, end_date)
            if klines and len(klines) >= 2:
                holdings_history[symbol] = {
                    "klines": klines,
                    "weight": holding.get("total_invested", 0) or 0,
                }

        if not holdings_history:
            return {
                "error": "持仓历史数据不足",
                "period": f"{start_date} to {end_date}",
            }

        # 计算权重
        total_invested = sum(h["weight"] for h in holdings_history.values())
        for symbol in holdings_history:
            holdings_history[symbol]["weight"] /= total_invested if total_invested > 0 else 1

        # 计算每日收益率
        daily_returns = []
        for i in range(1, len(index_klines)):
            date = index_klines[i].get("trade_date")

            # 指数收益率
            index_prev = index_klines[i-1].get("close", 0)
            index_curr = index_klines[i].get("close", 0)
            index_return = (index_curr - index_prev) / index_prev if index_prev > 0 else 0.0

            # 组合收益率（加权平均）
            portfolio_return = 0.0
            for symbol, data in holdings_history.items():
                klines = data["klines"]
                weight = data["weight"]

                # 找到对应日期的K线
                symbol_return = 0.0
                for j in range(1, len(klines)):
                    if klines[j].get("trade_date") == date:
                        prev_close = klines[j-1].get("close", 0)
                        curr_close = klines[j].get("close", 0)
                        if prev_close > 0:
                            symbol_return = (curr_close - prev_close) / prev_close
                        break

                portfolio_return += symbol_return * weight

            daily_returns.append({
                "date": date,
                "index_return": round(index_return, 6),
                "portfolio_return": round(portfolio_return, 6),
            })

        # 计算累计收益率
        index_cumulative = 1.0
        portfolio_cumulative = 1.0
        for dr in daily_returns:
            index_cumulative *= (1 + dr["index_return"])
            portfolio_cumulative *= (1 + dr["portfolio_return"])

        index_total_return = index_cumulative - 1.0
        portfolio_total_return = portfolio_cumulative - 1.0

        # 计算最大回撤
        portfolio_returns = [dr["portfolio_return"] for dr in daily_returns]
        max_drawdown = self._calculate_max_drawdown(portfolio_returns)

        # 计算波动率
        volatility = self._calculate_volatility(portfolio_returns)

        # 计算夏普比率（假设无风险利率3%）
        risk_free_rate = 0.03
        avg_return = sum(portfolio_returns) / len(portfolio_returns) if portfolio_returns else 0
        sharpe_ratio = (avg_return * 252 - risk_free_rate) / volatility if volatility > 0 else 0.0

        return {
            "period": f"{start_date} to {end_date}",
            "trading_days": len(daily_returns),
            "index_symbol": index_symbol,
            "index_return": round(index_total_return, 4),
            "portfolio_return": round(portfolio_total_return, 4),
            "outperformance": round(portfolio_total_return - index_total_return, 4),
            "max_drawdown": round(max_drawdown, 4),
            "volatility": round(volatility, 4),
            "sharpe_ratio": round(sharpe_ratio, 4),
            "daily_returns": daily_returns,
        }

    def _calculate_stress_risk_metrics(self, position_impacts: List[Dict], current_value: float) -> Dict:
        """计算压力测试风险指标"""
        if not position_impacts or current_value <= 0:
            return {}

        # 最大单只损失
        max_position_loss = min(p["loss"] for p in position_impacts)
        max_position_loss_pct = min(p["loss_pct"] for p in position_impacts)

        # 行业损失分布
        sector_losses = {}
        for p in position_impacts:
            sector = p["sector"]
            if sector not in sector_losses:
                sector_losses[sector] = 0.0
            sector_losses[sector] += p["loss"]

        # 损失集中度（前3大损失占比）
        sorted_losses = sorted([p["loss"] for p in position_impacts])
        top3_losses = sum(sorted_losses[:3])
        loss_concentration = abs(top3_losses) / abs(sum(sorted_losses)) if sum(sorted_losses) != 0 else 0.0

        return {
            "max_position_loss": round(max_position_loss, 2),
            "max_position_loss_pct": round(max_position_loss_pct, 4),
            "sector_losses": {k: round(v, 2) for k, v in sector_losses.items()},
            "loss_concentration": round(loss_concentration, 4),
            "positions_at_risk": len([p for p in position_impacts if p["loss"] < 0]),
        }

    def _summarize_scenarios(self, results: List[Dict]) -> Dict:
        """汇总多个场景的统计信息"""
        if not results:
            return {}

        losses = [r["loss_percentage"] for r in results]
        worst_scenario = min(results, key=lambda x: x["loss_percentage"])
        best_scenario = max(results, key=lambda x: x["loss_percentage"])

        return {
            "worst_scenario": worst_scenario["scenario_name"],
            "worst_loss": round(worst_scenario["loss_percentage"], 4),
            "best_scenario": best_scenario["scenario_name"],
            "best_loss": round(best_scenario["loss_percentage"], 4),
            "avg_loss": round(sum(losses) / len(losses), 4),
            "scenarios_tested": len(results),
        }

    def _calculate_max_drawdown(self, returns: List[float]) -> float:
        """计算最大回撤"""
        if not returns or len(returns) < 2:
            return 0.0

        cumulative = 1.0
        peak = 1.0
        max_dd = 0.0

        for ret in returns:
            cumulative *= (1 + ret)
            if cumulative > peak:
                peak = cumulative
            dd = (peak - cumulative) / peak
            if dd > max_dd:
                max_dd = dd

        return max_dd

    def _calculate_volatility(self, returns: List[float]) -> float:
        """计算年化波动率"""
        if not returns or len(returns) < 2:
            return 0.0

        import math

        mean_return = sum(returns) / len(returns)
        variance = sum((r - mean_return) ** 2 for r in returns) / (len(returns) - 1)
        daily_vol = math.sqrt(variance)

        # 年化（假设252个交易日）
        annual_vol = daily_vol * math.sqrt(252)
        return annual_vol
