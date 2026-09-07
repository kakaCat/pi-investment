"""筹码分布编排服务 — 增量更新、回填、换手率回退、查询

换手率回退链（spec §计算模型）：
  daily_klines.turnover_rate（%，可能为 None）
  → volume × close / circulating_mv（流通市值反推流通股）
  → 当日全市场换手率中位数
"""
from __future__ import annotations

from typing import Any, Dict, Optional

import structlog

from domain.chip_distribution.calculator import ChipDistribution

logger = structlog.get_logger(__name__)


def normalize_symbol(symbol: str) -> str:
    """归一化为库内 bare 格式：600519.SH/sh600519 → 600519。

    生产 daily_klines/stocks 全部使用无后缀代码（2026-08-11 验证：
    5685/5852 个 symbol 均为 bare 格式）。
    """
    s = symbol.strip().upper()
    if "." in s:
        s = s.split(".")[0]
    for prefix in ("SH", "SZ", "BJ"):
        if s.startswith(prefix):
            s = s[len(prefix):]
            break
    return s


class ChipDistributionService:
    def __init__(self, repo):
        self.repo = repo

    # ---------- 换手率回退 ----------

    def _resolve_turnover(self, symbol: str, row: Dict[str, Any]) -> float:
        tr = row.get("turnover_rate")
        if tr is not None:
            return float(tr)
        mv = self.repo.get_circulating_mv(symbol)
        close = row.get("close")
        volume = row.get("volume")
        if mv and close and volume:
            float_shares = mv / close
            if float_shares > 0:
                return min(volume / float_shares * 100.0, 100.0)
        median = self.repo.get_median_turnover(row["trade_date"])
        if median:
            logger.warning(f"chip turnover fallback to market median: {symbol} {row['trade_date']}")
            return median
        return 0.0

    # ---------- 增量更新 ----------

    def update_symbol(self, symbol: str) -> Dict[str, Any]:
        """把 symbol 的筹码分布推进到最新 K 线。返回 {days_applied, ...}。"""
        symbol = normalize_symbol(symbol)
        state = self.repo.get_state(symbol)
        after = state["last_trade_date"] if state else None
        rows = self.repo.get_klines(symbol, after_date=after)
        if not rows:
            if state:
                return {"symbol": symbol, "days_applied": 0}
            return {"symbol": symbol, "days_applied": 0,
                    "error": "无 K 线数据或 symbol 不存在"}

        if state:
            dist = ChipDistribution.from_bytes(
                state["price_min"], state["bin_width"], state["counts"])
        else:
            dist = ChipDistribution.empty(
                min(r["low"] for r in rows), max(r["high"] for r in rows))

        for row in rows:
            t = self._resolve_turnover(symbol, row)
            dist.apply_day(row["low"], row["high"], row["close"], t)

        last = rows[-1]
        self.repo.upsert_state(symbol, dist, last["trade_date"])
        metrics = dist.metrics(last["close"])
        self.repo.upsert_metrics(symbol, last["trade_date"], metrics)
        return {"symbol": symbol, "days_applied": len(rows),
                "last_trade_date": str(last["trade_date"])}

    def daily_update(self, limit: Optional[int] = None) -> Dict[str, Any]:
        """全市场增量：所有有新 K 线的股票。返回汇总统计。"""
        pending = self.repo.get_symbols_with_pending_klines()
        if limit:
            pending = pending[:limit]
        ok, failed, days = 0, 0, 0
        for p in pending:
            try:
                r = self.update_symbol(p["symbol"])
                if "error" in r:
                    failed += 1
                else:
                    ok += 1
                    days += r["days_applied"]
            except Exception as e:
                failed += 1
                logger.error(f"chip daily_update {p['symbol']} failed: {e}")
        summary = {"pending": len(pending), "updated": ok,
                   "failed": failed, "days_applied": days}
        logger.info(f"chip daily_update done: {summary}")
        return summary

    # ---------- 查询 ----------

    def get_distribution(self, symbol: str) -> Dict[str, Any]:
        """完整分布曲线 + 最新指标（从 state 还原，不重新计算）"""
        symbol = normalize_symbol(symbol)
        state = self.repo.get_state(symbol)
        if not state:
            return {"symbol": symbol, "error": "筹码分布未计算，请先运行更新任务"}
        dist = ChipDistribution.from_bytes(
            state["price_min"], state["bin_width"], state["counts"])
        close = self.repo.get_latest_close(symbol)
        total = dist.counts.sum()
        centers = dist.bin_centers()
        # 只返回非零桶，减小响应体积
        curve = [
            {"price": round(float(c), 4), "weight": float(w) / float(total)}
            for c, w in zip(centers, dist.counts) if w > 0
        ] if total > 0 else []
        return {
            "symbol": symbol,
            "as_of": str(state["last_trade_date"]),
            "close": close,
            "curve": curve,
            "metrics": dist.metrics(close) if close else None,
        }
