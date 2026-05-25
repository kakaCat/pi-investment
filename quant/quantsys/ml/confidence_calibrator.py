"""
Confidence Calibrator — 置信度校准器

从 factor_values 和 daily_klines 中提取历史数据，计算每个技术指标的
信息系数 (IC) 和最优分档阈值，输出 JSON 配置文件供 TypeScript 信号生成器使用。

实现：原生 SQL 聚合 + Python 统计，避免 pandas pivot 大量数据。

用法：
    python -m quantsys.ml.confidence_calibrator --forward-days 5 --output .pi-invest/quant/confidence_config.json
"""

from __future__ import annotations

import json
import math
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import numpy as np
from scipy.stats import spearmanr

from quantsys.data.db import Database


# ═══════════════════════════════════════════════════════════════
# 因子到数据库列的映射
# ═══════════════════════════════════════════════════════════════

FACTOR_DB_COLUMNS: dict[str, str] = {
    "rsi": "RSI6",
    "ma5": "MA5",
    "ma20": "MA20",
    "ma60": "MA60",
    "macd_histogram": "MACD_macd_histogram",
    "bb_upper": "BOLL_bb_upper",
    "bb_middle": "BOLL_bb_middle",
    "bb_lower": "BOLL_bb_lower",
    "vr": "VR",
}

REQUIRED_FACTORS = list(FACTOR_DB_COLUMNS.values())


class ConfidenceCalibrator:
    """
    置信度校准器 —— SQL 原生聚合版本。

    对每个因子独立计算 Rank IC 和最优分档阈值，内存占用极小。
    """

    def __init__(
        self,
        db_path: str,
        forward_days: int = 5,
        return_threshold: float = 0.02,
        min_samples_per_bin: int = 100,
        max_symbols: int = 500,
        lookback_days: int = 180,
    ):
        self.db_path = db_path
        self.forward_days = forward_days
        self.return_threshold = return_threshold
        self.min_samples_per_bin = min_samples_per_bin
        self.max_symbols = max_symbols
        self.lookback_days = lookback_days

    # ── Public API ────────────────────────────────────────────

    def calibrate_all(self) -> dict[str, Any]:
        print("=" * 60)
        print(f"[Calibrator] 开始校准 (forward={self.forward_days}d, "
              f"threshold={self.return_threshold*100:.0f}%)")
        print("=" * 60)

        # 采样符号和日期范围
        symbols = self._sample_symbols()
        date_range = self._date_range()
        print(f"[Calibrator] {len(symbols)} 个符号, "
              f"{date_range['start']} ~ {date_range['end']}")

        # 预加载价格数据 (symbol, date) → close
        price_map = self._load_price_map(symbols, date_range)
        print(f"[Calibrator] 价格数据: {len(price_map)} 条")

        # 预计算 forward return 索引 (symbol, date) → forward_return
        print("[Calibrator] 预计算 forward return...")
        date_index = self._build_forward_index(price_map)
        fwd_return_map: dict[tuple[str, str], float | None] = {}
        for (sym, date), price in price_map.items():
            future_date = self._lookup_forward_date(sym, date, date_index)
            if future_date and (sym, future_date) in price_map and price > 0:
                price_future = price_map[(sym, future_date)]
                fwd_return_map[(sym, date)] = (price_future - price) / price
            else:
                fwd_return_map[(sym, date)] = None

        valid_fwd = sum(1 for v in fwd_return_map.values() if v is not None)
        print(f"[Calibrator] Forward return 覆盖: {valid_fwd}/{len(fwd_return_map)}")

        # 逐因子校准
        factors_config: dict[str, Any] = {}

        for config_key, db_col in [
            ("rsi", "RSI6"),
            ("vr", "VR"),
        ]:
            cfg = self._calibrate_range_factor(config_key, db_col, symbols, date_range, fwd_return_map)
            if cfg:
                factors_config[config_key] = cfg

        for config_key in ["ma_bullish", "ma_bearish", "ma5_cross", "macd_positive", "bb_position"]:
            cfg = self._calibrate_derived_factor(config_key, symbols, date_range, fwd_return_map)
            if cfg:
                factors_config[config_key] = cfg

        # 归一化权重
        factors_config = self._normalize_weights(factors_config)

        # 构建配置
        config = {
            "version": "1.0",
            "generated_at": datetime.now().isoformat(),
            "forward_return_days": self.forward_days,
            "return_threshold": self.return_threshold,
            "total_samples": sum(
                cfg.get("samples", 0)
                for cfg in factors_config.values()
            ) // max(len(factors_config), 1),
            "factors": factors_config,
            "meta": {
                "calibration_method": "IC-weighted threshold optimization (SQL-native)",
                "data_range": {
                    "start": date_range["start"],
                    "end": date_range["end"],
                },
                "symbols_count": len(symbols),
            },
        }

        return config

    # ── Data Loading ──────────────────────────────────────────

    def _database(self) -> Database:
        return Database(self.db_path)

    def _execute(self, sql: str, params: tuple[Any, ...] = ()) -> list[tuple[Any, ...]]:
        database = self._database()
        try:
            conn = database._get_connection()
            if database.provider == "postgres":
                sql = self._rewrite_sql_for_postgres(sql)
                cursor = conn.cursor()
                cursor.execute(sql, params)
                rows = cursor.fetchall()
                cursor.close()
                return rows

            cursor = conn.execute(sql, params)
            return cursor.fetchall()
        finally:
            database.close()

    def _scalar(self, sql: str, params: tuple[Any, ...] = ()) -> tuple[Any, ...] | None:
        rows = self._execute(sql, params)
        return rows[0] if rows else None

    def _rewrite_sql_for_postgres(self, sql: str) -> str:
        """Translate the SQLite-compatible calibration SQL to PostgreSQL compat views."""
        rewritten = sql
        replacements = {
            "FROM factor_values": "FROM quant_compat.factor_values",
            "FROM daily_klines": "FROM quant_compat.daily_klines",
            "FROM factor_values f": "FROM quant_compat.factor_values f",
        }
        for source, target in replacements.items():
            rewritten = rewritten.replace(source, target)
        rewritten = rewritten.replace("RANDOM()", "random()")
        rewritten = rewritten.replace("?", "%s")
        return rewritten

    def _sample_symbols(self) -> list[str]:
        """随机采样有足够因子数据的符号。"""
        rows = self._execute(
            """
            SELECT symbol
            FROM factor_values
            WHERE factor_name = 'RSI6'
            GROUP BY symbol
            HAVING COUNT(DISTINCT date) >= 60
            ORDER BY RANDOM()
            LIMIT ?
            """,
            (self.max_symbols,),
        )
        return [r[0] for r in rows]

    def _date_range(self) -> dict[str, str]:
        row = self._scalar(
            """
            SELECT MIN(date), MAX(date)
            FROM factor_values
            WHERE factor_name = 'RSI6'
            """
        )
        if not row or not row[0]:
            raise ValueError("factor_values 表为空")

        end_date = row[1]
        start_date = row[0]

        if self.lookback_days:
            limited = (
                datetime.strptime(str(end_date), "%Y-%m-%d")
                - timedelta(days=self.lookback_days)
            ).strftime("%Y-%m-%d")
            if limited > start_date:
                start_date = limited

        return {"start": start_date, "end": end_date}

    def _load_price_map(
        self, symbols: list[str], date_range: dict[str, str]
    ) -> dict[tuple[str, str], float]:
        """加载 (symbol, date) → close 映射表。"""
        symbol_placeholders = ",".join(["?"] * len(symbols))
        rows = self._execute(
            f"""
            SELECT symbol, date, close
            FROM daily_klines
            WHERE symbol IN ({symbol_placeholders})
              AND date >= ? AND date <= ?
            ORDER BY symbol, date
            """,
            tuple(symbols) + (date_range["start"], date_range["end"]),
        )
        return {(r[0], r[1]): r[2] for r in rows}

    # ── Factor Calibration ────────────────────────────────────

    def _calibrate_range_factor(
        self,
        config_key: str,
        db_col: str,
        symbols: list[str],
        date_range: dict[str, str],
        fwd_return_map: dict[tuple[str, str], float | None],
    ) -> dict[str, Any] | None:
        """
        校准连续值因子（如 RSI、VR）。
        从 factor_values 读取因子值，从 fwd_return_map 获取 forward return。
        """
        print(f"\n[Calibrator] --- {config_key} ({db_col}) ---")

        symbol_placeholders = ",".join(["?"] * len(symbols))
        rows = self._execute(
            f"""
            SELECT symbol, date, factor_value
            FROM factor_values
            WHERE factor_name = ?
              AND symbol IN ({symbol_placeholders})
              AND date >= ? AND date <= ?
            ORDER BY symbol, date
            """,
            (db_col,) + tuple(symbols) + (date_range["start"], date_range["end"]),
        )

        if len(rows) < self.min_samples_per_bin * 3:
            print(f"  ⚠ 样本不足 ({len(rows)}), 跳过")
            return None

        # 构建 (factor_value, forward_return) 数组
        values = []
        returns = []

        for symbol, date, factor_val in rows:
            if factor_val is None:
                continue
            fwd_ret = fwd_return_map.get((symbol, date))
            if fwd_ret is not None:
                values.append(factor_val)
                returns.append(fwd_ret)

        if len(values) < self.min_samples_per_bin * 3:
            print(f"  ⚠ 有效样本不足 ({len(values)}), 跳过")
            return None

        values_arr = np.array(values)
        returns_arr = np.array(returns)

        # 过滤异常值
        mask = np.abs(returns_arr) < 0.5  # 剔除涨跌停等极端值
        values_arr = values_arr[mask]
        returns_arr = returns_arr[mask]

        # Rank IC
        ic, ic_pvalue = spearmanr(values_arr, returns_arr)
        print(f"  Rank IC: {ic:.4f} (p={ic_pvalue:.4f}), 样本: {len(values_arr)}")

        # 分档统计
        if config_key == "rsi":
            thresholds = [0, 20, 30, 40, 50, 60, 70, 80, 100]
            neutral_range = (40, 60)
        elif config_key == "vr":
            thresholds = [0, 0.5, 0.8, 1.0, 1.2, 1.5, 2.0, 3.0, 10.0]
            neutral_range = (0.8, 1.2)
        else:
            # 通用分档：基于分位数
            percentiles = [0, 10, 20, 30, 40, 50, 60, 70, 80, 90, 100]
            thresholds = [float(np.percentile(values_arr, p)) for p in percentiles]
            # 去重
            thresholds = sorted(set(round(t, 4) for t in thresholds))
            if len(thresholds) < 3:
                thresholds = [float(values_arr.min()), float(values_arr.mean()), float(values_arr.max())]
            neutral_range = (thresholds[len(thresholds)//2 - 1], thresholds[len(thresholds)//2 + 1])

        bins = []
        thresholds_sorted = sorted(set(thresholds))

        for i in range(len(thresholds_sorted) - 1):
            lo, hi = thresholds_sorted[i], thresholds_sorted[i + 1]
            mask_bin = (values_arr >= lo) & (values_arr < hi)
            n_bin = mask_bin.sum()
            if n_bin < self.min_samples_per_bin:
                continue

            bin_rets = returns_arr[mask_bin]
            mean_ret = float(bin_rets.mean())
            hit_rate = float((bin_rets > self.return_threshold).mean())
            mid = (lo + hi) / 2
            in_neutral = neutral_range[0] <= mid <= neutral_range[1]

            extra_ret = mean_ret - float(returns_arr.mean())
            score_bonus = round(np.clip(extra_ret * 2.0, -0.2, 0.2), 4)

            bins.append({
                "range": [lo, hi],
                "mean_return": round(mean_ret, 6),
                "hit_rate": round(hit_rate, 4),
                "samples": int(n_bin),
                "neutral": in_neutral,
                "score_bonus": 0.0 if in_neutral else score_bonus,
            })

        return {
            "type": "range",
            "column": db_col,
            "rank_ic": round(float(ic), 4),
            "ic_pvalue": round(float(ic_pvalue), 4),
            "raw_weight": round(abs(float(ic)), 4),
            "bins": bins,
        }

    def _calibrate_derived_factor(
        self,
        config_key: str,
        symbols: list[str],
        date_range: dict[str, str],
        fwd_return_map: dict[tuple[str, str], float | None],
    ) -> dict[str, Any] | None:
        """校准派生因子。"""
        if config_key in ("ma_bullish", "ma_bearish", "ma5_cross"):
            return self._calibrate_ma_factor(config_key, symbols, date_range, fwd_return_map)
        elif config_key == "macd_positive":
            return self._calibrate_macd_factor(symbols, date_range, fwd_return_map)
        elif config_key == "bb_position":
            return self._calibrate_bb_factor(symbols, date_range, fwd_return_map)
        return None

    def _calibrate_ma_factor(
        self,
        config_key: str,
        symbols: list[str],
        date_range: dict[str, str],
        fwd_return_map: dict[tuple[str, str], float | None],
    ) -> dict[str, Any] | None:
        """校准均线因子（bullish/bearish/cross）。"""
        print(f"\n[Calibrator] --- {config_key} ---")

        symbol_placeholders = ",".join(["?"] * len(symbols))
        rows = self._execute(
            f"""
            SELECT f.symbol, f.date,
                   MAX(CASE WHEN f.factor_name='MA5' THEN f.factor_value END) AS ma5,
                   MAX(CASE WHEN f.factor_name='MA20' THEN f.factor_value END) AS ma20,
                   MAX(CASE WHEN f.factor_name='MA60' THEN f.factor_value END) AS ma60
            FROM factor_values f
            WHERE f.symbol IN ({symbol_placeholders})
              AND f.date >= ? AND f.date <= ?
              AND f.factor_name IN ('MA5','MA20','MA60')
            GROUP BY f.symbol, f.date
            HAVING MAX(CASE WHEN f.factor_name='MA5' THEN f.factor_value END) IS NOT NULL
               AND MAX(CASE WHEN f.factor_name='MA20' THEN f.factor_value END) IS NOT NULL
               AND MAX(CASE WHEN f.factor_name='MA60' THEN f.factor_value END) IS NOT NULL
            ORDER BY f.symbol, f.date
            """,
            tuple(symbols) + (date_range["start"], date_range["end"]),
        )

        if len(rows) < self.min_samples_per_bin * 2:
            print(f"  ⚠ 样本不足 ({len(rows)}), 跳过")
            return None

        true_returns = []
        false_returns = []

        for symbol, date, ma5, ma20, ma60 in rows:
            fwd_ret = fwd_return_map.get((symbol, date))
            if fwd_ret is None:
                continue

            if config_key == "ma_bullish":
                cond = ma5 > ma20 and ma20 > ma60
            elif config_key == "ma_bearish":
                cond = ma5 < ma20 and ma20 < ma60
            elif config_key == "ma5_cross":
                cond = ma5 > ma20
            else:
                continue

            if cond:
                true_returns.append(fwd_ret)
            else:
                false_returns.append(fwd_ret)

        if len(true_returns) < self.min_samples_per_bin:
            print(f"  ⚠ True 样本不足 ({len(true_returns)}), 跳过")
            return None

        true_arr = np.array(true_returns)
        false_arr = np.array(false_returns) if false_returns else np.array([0.0])

        true_mean = float(true_arr.mean())
        false_mean = float(false_arr.mean())
        excess_ret = true_mean - false_mean
        hit_rate = float((true_arr > self.return_threshold).mean())

        # IC: 点二列相关
        all_values = np.concatenate([
            np.ones(len(true_returns)),
            np.zeros(len(false_returns)),
        ])
        all_returns = np.concatenate([true_arr, false_arr])
        ic, ic_pvalue = spearmanr(all_values, all_returns)

        direction = "buy" if config_key in ("ma_bullish", "ma5_cross") else "sell"
        condition_map = {
            "ma_bullish": "MA5 > MA20 AND MA20 > MA60",
            "ma_bearish": "MA5 < MA20 AND MA20 < MA60",
            "ma5_cross": "MA5 > MA20",
        }

        print(f"  Rank IC: {ic:.4f} (p={ic_pvalue:.4f})")
        print(f"  True 平均收益: {true_mean*100:.2f}%, False: {false_mean*100:.2f}%, 超额: {excess_ret*100:.2f}%")

        return {
            "type": "boolean",
            "condition": condition_map.get(config_key, "unknown"),
            "rank_ic": round(float(ic), 4),
            "ic_pvalue": round(float(ic_pvalue), 4),
            "raw_weight": round(abs(float(ic)), 4),
            "direction": direction,
            "mean_return": round(true_mean, 6),
            "hit_rate": round(hit_rate, 4),
            "samples": int(len(true_returns)),
            "excess_return": round(excess_ret, 6),
        }

    def _calibrate_macd_factor(
        self,
        symbols: list[str],
        date_range: dict[str, str],
        fwd_return_map: dict[tuple[str, str], float | None],
    ) -> dict[str, Any] | None:
        """校准 MACD histogram > 0 因子。"""
        print(f"\n[Calibrator] --- macd_positive ---")

        symbol_placeholders = ",".join(["?"] * len(symbols))
        rows = self._execute(
            f"""
            SELECT symbol, date, factor_value
            FROM factor_values
            WHERE factor_name = 'MACD_macd_histogram'
              AND symbol IN ({symbol_placeholders})
              AND date >= ? AND date <= ?
            ORDER BY symbol, date
            """,
            tuple(symbols) + (date_range["start"], date_range["end"]),
        )

        true_rets = []
        false_rets = []
        for symbol, date, val in rows:
            fwd_ret = fwd_return_map.get((symbol, date))
            if fwd_ret is None or val is None:
                continue
            if val > 0:
                true_rets.append(fwd_ret)
            else:
                false_rets.append(fwd_ret)

        return self._build_boolean_result("macd_positive", true_rets, false_rets,
                                          "MACD_histogram > 0", "buy")

    def _calibrate_bb_factor(
        self,
        symbols: list[str],
        date_range: dict[str, str],
        fwd_return_map: dict[tuple[str, str], float | None],
    ) -> dict[str, Any] | None:
        """校准 Bollinger Band position 因子。"""
        print(f"\n[Calibrator] --- bb_position ---")

        symbol_placeholders = ",".join(["?"] * len(symbols))
        rows = self._execute(
            f"""
            SELECT f.symbol, f.date,
                   MAX(CASE WHEN f.factor_name='BOLL_bb_upper' THEN f.factor_value END) AS bb_up,
                   MAX(CASE WHEN f.factor_name='BOLL_bb_lower' THEN f.factor_value END) AS bb_lo
            FROM factor_values f
            WHERE f.symbol IN ({symbol_placeholders})
              AND f.date >= ? AND f.date <= ?
              AND f.factor_name IN ('BOLL_bb_upper','BOLL_bb_lower')
            GROUP BY f.symbol, f.date
            HAVING MAX(CASE WHEN f.factor_name='BOLL_bb_upper' THEN f.factor_value END) IS NOT NULL
               AND MAX(CASE WHEN f.factor_name='BOLL_bb_lower' THEN f.factor_value END) IS NOT NULL
            ORDER BY f.symbol, f.date
            """,
            tuple(symbols) + (date_range["start"], date_range["end"]),
        )

        values = []
        returns = []
        for symbol, date, bb_up, bb_lo in rows:
            fwd_ret = fwd_return_map.get((symbol, date))
            if fwd_ret is None:
                continue
            # Use BB middle as price proxy for position calculation
            bb_mid = (bb_up + bb_lo) / 2
            bb_range = bb_up - bb_lo
            if bb_range <= 0:
                continue
            bb_pos = (bb_mid - bb_lo) / bb_range
            values.append(bb_pos)
            returns.append(fwd_ret)

        if len(values) < self.min_samples_per_bin * 3:
            print(f"  ⚠ 有效样本不足 ({len(values)}), 跳过")
            return None

        values_arr = np.array(values)
        returns_arr = np.array(returns)

        # Rank IC
        ic, ic_pvalue = spearmanr(values_arr, returns_arr)
        print(f"  Rank IC: {ic:.4f} (p={ic_pvalue:.4f}), 样本: {len(values_arr)}")

        # 分档
        thresholds = [0.0, 0.1, 0.2, 0.3, 0.5, 0.7, 0.8, 0.9, 1.0]
        neutral_range = (0.4, 0.6)
        bins = []

        for i in range(len(thresholds) - 1):
            lo, hi = thresholds[i], thresholds[i + 1]
            mask_bin = (values_arr >= lo) & (values_arr < hi)
            n_bin = mask_bin.sum()
            if n_bin < self.min_samples_per_bin:
                continue

            bin_rets = returns_arr[mask_bin]
            mean_ret = float(bin_rets.mean())
            hit_rate = float((bin_rets > self.return_threshold).mean())
            mid = (lo + hi) / 2
            in_neutral = neutral_range[0] <= mid <= neutral_range[1]

            extra_ret = mean_ret - float(returns_arr.mean())
            score_bonus = round(np.clip(extra_ret * 2.0, -0.2, 0.2), 4)

            bins.append({
                "range": [lo, hi],
                "mean_return": round(mean_ret, 6),
                "hit_rate": round(hit_rate, 4),
                "samples": int(n_bin),
                "neutral": in_neutral,
                "score_bonus": 0.0 if in_neutral else score_bonus,
            })

        return {
            "type": "range",
            "column": "bb_position",
            "rank_ic": round(float(ic), 4),
            "ic_pvalue": round(float(ic_pvalue), 4),
            "raw_weight": round(abs(float(ic)), 4),
            "bins": bins,
        }

    # ── Helpers ───────────────────────────────────────────────

    def _build_forward_index(
        self, price_map: dict[tuple[str, str], float]
    ) -> dict[str, list[str]]:
        """构建 symbol → sorted dates 索引，用于快速查找 N 日后的日期。"""
        index: dict[str, list[str]] = {}
        for sym, date in price_map:
            if sym not in index:
                index[sym] = []
            index[sym].append(date)
        for sym in index:
            index[sym].sort()
        return index

    def _lookup_forward_date(
        self, symbol: str, date: str,
        date_index: dict[str, list[str]],
    ) -> str | None:
        """查找 symbol 在 date 之后第 N 个交易日的日期。"""
        dates = date_index.get(symbol, [])
        try:
            idx = dates.index(date)
            target_idx = idx + self.forward_days
            if target_idx < len(dates):
                return dates[target_idx]
        except ValueError:
            pass
        return None

    def _build_boolean_result(
        self,
        config_key: str,
        true_rets: list[float],
        false_rets: list[float],
        condition: str,
        direction: str,
    ) -> dict[str, Any] | None:
        """从 true/false 收益列表构建布尔因子结果。"""
        if len(true_rets) < self.min_samples_per_bin:
            print(f"  ⚠ True 样本不足 ({len(true_rets)}), 跳过")
            return None

        true_arr = np.array(true_rets)
        false_arr = np.array(false_rets) if false_rets else np.array([0.0])

        true_mean = float(true_arr.mean())
        false_mean = float(false_arr.mean())
        excess_ret = true_mean - false_mean
        hit_rate = float((true_arr > self.return_threshold).mean())

        all_values = np.concatenate([
            np.ones(len(true_rets)),
            np.zeros(len(false_rets)),
        ])
        all_returns = np.concatenate([true_arr, false_arr])
        ic, ic_pvalue = spearmanr(all_values, all_returns)

        print(f"  Rank IC: {ic:.4f} (p={ic_pvalue:.4f})")
        print(f"  True 平均收益: {true_mean*100:.2f}%, False: {false_mean*100:.2f}%, 超额: {excess_ret*100:.2f}%")

        return {
            "type": "boolean",
            "condition": condition,
            "rank_ic": round(float(ic), 4),
            "ic_pvalue": round(float(ic_pvalue), 4),
            "raw_weight": round(abs(float(ic)), 4),
            "direction": direction,
            "mean_return": round(true_mean, 6),
            "hit_rate": round(hit_rate, 4),
            "samples": int(len(true_rets)),
            "excess_return": round(excess_ret, 6),
        }

    def _normalize_weights(self, factors: dict[str, Any]) -> dict[str, Any]:
        total_raw = sum(
            cfg.get("raw_weight", 0) for cfg in factors.values()
            if isinstance(cfg, dict)
        )
        if total_raw == 0:
            print("[Calibrator] ⚠ 所有因子 IC 为 0，使用均匀权重")
            total_raw = 1.0

        for cfg in factors.values():
            if isinstance(cfg, dict) and "raw_weight" in cfg:
                cfg["weight"] = round(cfg["raw_weight"] / total_raw, 4)
            else:
                cfg["weight"] = 0.0
        return factors

    def save_config(self, config: dict[str, Any], output_path: str) -> None:
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        print(f"\n[Calibrator] ✅ 配置已保存: {output_file}")

    def print_summary(self, config: dict[str, Any]) -> None:
        print("\n" + "=" * 60)
        print("校准摘要")
        print("=" * 60)
        print(f"版本: {config['version']}")
        print(f"生成时间: {config['generated_at']}")
        print(f"Forward 天数: {config['forward_return_days']}")
        print(f"样本总数: {config['total_samples']:,}")
        print(f"数据范围: {config['meta']['data_range']['start']} ~ {config['meta']['data_range']['end']}")
        print(f"覆盖股票: {config['meta']['symbols_count']}")

        print("\n因子权重:")
        print(f"{'因子':<20} {'IC':>8} {'权重':>8} {'类型':>8} {'方向':>6}")
        print("-" * 55)
        for name, cfg in sorted(config["factors"].items(), key=lambda x: -x[1].get("weight", 0)):
            ic = cfg.get("rank_ic", 0)
            weight = cfg.get("weight", 0)
            ftype = cfg.get("type", "")
            direction = cfg.get("direction", "")
            print(f"{name:<20} {ic:>8.4f} {weight:>8.4f} {ftype:>8} {direction:>6}")
        print("=" * 60)


# ═══════════════════════════════════════════════════════════════
# Entry point
# ═══════════════════════════════════════════════════════════════

def run_calibration(
    db_path: str | None = None,
    forward_days: int = 5,
    return_threshold: float = 0.02,
    output_path: str | None = None,
    max_symbols: int = 500,
    lookback_days: int = 180,
) -> dict[str, Any]:
    if db_path is None:
        candidates = [".pi-invest/stock-db/stocks.db"]
        db_path = next((c for c in candidates if Path(c).exists()), None)
        if db_path is None:
            raise FileNotFoundError("未找到 stocks.db")

    if output_path is None:
        output_path = ".pi-invest/quant/confidence_config.json"

    calibrator = ConfidenceCalibrator(
        db_path=db_path,
        forward_days=forward_days,
        return_threshold=return_threshold,
        max_symbols=max_symbols,
        lookback_days=lookback_days,
    )

    config = calibrator.calibrate_all()
    calibrator.save_config(config, output_path)
    calibrator.print_summary(config)

    return config


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="置信度校准器")
    parser.add_argument("--db-path", type=str, default=None)
    parser.add_argument("--forward-days", type=int, default=5)
    parser.add_argument("--threshold", type=float, default=0.02)
    parser.add_argument("--max-symbols", type=int, default=500)
    parser.add_argument("--lookback-days", type=int, default=180)
    parser.add_argument("--output", type=str, default=None)
    args = parser.parse_args()

    run_calibration(
        db_path=args.db_path,
        forward_days=args.forward_days,
        return_threshold=args.threshold,
        output_path=args.output,
        max_symbols=args.max_symbols,
        lookback_days=args.lookback_days,
    )
