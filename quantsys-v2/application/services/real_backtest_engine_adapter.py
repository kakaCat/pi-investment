"""
RealBacktestEngineAdapter — 真实回测引擎适配器（2026-09-01，E-1/E-3 修复）

背景：
- BacktestAsyncEngine._simulate_trading 曾用 random.uniform 生成假收益/假夏普
  （ sharpe 恒落 0.5~2.5 ），是 ServiceFactory.get_backtest_engine() 的唯一实现——
  任何调用方拿到的都是随机数（M3-2 combo 端点 500 的部分根因）。
- 本适配器把真实引擎 StrategyCodeService.backtest_strategy（M3-2 回测矩阵同款、
  539 条落库数据验证过）包装成 combo/调度等调用方期望的同步接口：
      backtest(strategy, symbols, start_date, end_date, initial_capital) -> {
          strategy_id, equity_curve[{date,value}], metrics{total_return,sharpe_ratio}
      }

设计要点：
- StrategyCodeService 惰性解析（首次 backtest 时才 get），避免
  StrategyCodeService -> shared -> service_factory -> 本模块 的循环 import
- equity_curve 键名转换：真实引擎用 {date, equity}，combo 服务消费 {date, value}
- symbols 为列表时逐股回测并聚合（等权平均权益曲线按日期对齐）
"""
from typing import Any, Dict, List, Optional

import structlog

logger = structlog.get_logger(__name__)


class RealBacktestEngineAdapter:
    """StrategyCodeService 的同步 backtest 接口适配器。"""

    def __init__(self, strategy_service: Any = None):
        # 允许测试注入；生产路径惰性解析
        self._strategy_service = strategy_service

    def _svc(self):
        if self._strategy_service is None:
            from adapters.shared.services import get_strategy_service
            self._strategy_service = get_strategy_service()
        return self._strategy_service

    def backtest(
        self,
        strategy: Dict[str, Any],
        symbols: Optional[List[str]] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        initial_capital: float = 1_000_000.0,
        **kwargs,
    ) -> Dict[str, Any]:
        """对单策略×（单股或多股）执行真实回测。

        Args:
            strategy: 策略 dict（至少含 strategy_id 或 id）
            symbols: 股票代码列表；多股时逐股回测并按日期对齐等权聚合
            start_date / end_date: YYYY-MM-DD
            initial_capital: 每股初始资金
        """
        sid = strategy.get("strategy_id") or strategy.get("id")
        if sid is None:
            raise ValueError("strategy 缺少 strategy_id")

        symbol_list = [s for s in (symbols or []) if s]
        if not symbol_list:
            raise ValueError("symbols 不能为空")

        per_symbol = []
        for sym in symbol_list:
            result = self._svc().backtest_strategy(
                strategy_id=sid,
                symbol=sym,
                start_date=start_date,
                end_date=end_date,
                initial_cash=initial_capital,
            )
            curve = [
                {"date": str(p["date"])[:10], "value": p["equity"]}
                for p in result.get("equity_curve", [])
            ]
            per_symbol.append({
                "curve": curve,
                "total_return": result.get("total_return", 0),
                "sharpe_ratio": result.get("sharpe_ratio", 0),
            })

        if len(per_symbol) == 1:
            only = per_symbol[0]
            return {
                "strategy_id": sid,
                "equity_curve": only["curve"],
                "metrics": {
                    "total_return": only["total_return"],
                    "sharpe_ratio": only["sharpe_ratio"],
                },
            }

        # 多股聚合：按日期对齐等权平均（缺日期沿用该股票最近值）
        combined = self._combine_curves([p["curve"] for p in per_symbol])
        n = len(per_symbol)
        return {
            "strategy_id": sid,
            "equity_curve": combined,
            "metrics": {
                "total_return": sum(p["total_return"] for p in per_symbol) / n,
                "sharpe_ratio": sum(p["sharpe_ratio"] for p in per_symbol) / n,
            },
        }

    @staticmethod
    def _combine_curves(curves: List[List[Dict[str, Any]]]) -> List[Dict[str, Any]]:
        all_dates = sorted({p["date"] for c in curves for p in c})
        combined = []
        for date in all_dates:
            total = 0.0
            for curve in curves:
                value = curve[0]["value"] if curve else 0.0
                for point in curve:
                    if point["date"] <= date:
                        value = point["value"]
                    else:
                        break
                total += value
            combined.append({"date": date, "value": round(total / max(len(curves), 1), 2)})
        return combined
