#!/usr/bin/env python
"""存量决策教训回填（REQ-9bcd0a WP1，2026-09-12，w-c8cae280）

背景：DecisionScoreService 历史版本只回写 score/band/detail，learned_lesson 恒空
（实测 27 条已评分决策 0 条有教训）→ Autonomy L2『评估 → 教训 → 规则』回流边断裂。

本脚本对"已打分（score 非空）但 learned_lesson 为空"的决策，用 evaluation_result
明细重新生成教训并回写。**幂等**：只处理 learned_lesson 为空的行，重复执行无副作用。
不扫描/不改动任何分数，只补教训字段。

用法（在 quantsys-v2 目录下）：
    venv/bin/python scripts/backfill_learned_lessons.py --dry-run   # 只预览不写
    venv/bin/python scripts/backfill_learned_lessons.py             # 回填（.env 指向的库）
"""
import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv

load_dotenv(PROJECT_ROOT / ".env")

import logging  # noqa: E402

from adapters.outbound.repositories.agent_intelligence_repository import (  # noqa: E402
    AgentIntelligenceORMRepository,
)
from application.services.evolution.lesson_generator import generate_lesson  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("backfill_lessons")

ACTION_BY_TYPE = {"trade_buy": "buy", "trade_sell": "sell", "missed_opportunity": "miss"}


def build_lesson(row: dict):
    """从打分明细重建教训；信息不足时返回 (None, 原因)。"""
    detail = row.get("evaluation_result") or {}
    if not isinstance(detail, dict) or not detail:
        return None, "无 evaluation_result 明细（可能由旧评估器写入）"
    action = ACTION_BY_TYPE.get(row.get("decision_type") or "")
    if action is None:
        return None, f"非打分类型 decision_type={row.get('decision_type')}"
    params = row.get("parameters") or {}
    symbol = row.get("related_entity_id") or params.get("symbol")
    trade_price = detail.get("trade_price", params.get("price"))
    trade_date = detail.get("trade_date")
    ref_date = detail.get("ref_date")
    excess = detail.get("excess_return")
    score = row.get("score", detail.get("score"))
    band = row.get("score_band") or detail.get("band")
    missing = [k for k, v in (("symbol", symbol), ("trade_price", trade_price),
                              ("trade_date", trade_date), ("ref_date", ref_date),
                              ("excess_return", excess), ("band", band),
                              ("score", score)) if v is None]
    if missing:
        return None, f"明细缺字段: {','.join(missing)}"
    return generate_lesson(
        action=action,
        decision_type=row.get("decision_type") or "",
        symbol=symbol,
        trade_price=float(trade_price),
        trade_date=str(trade_date),
        ref_date=str(ref_date),
        excess_return=float(excess),
        band=str(band),
        score=float(score),
        window_trading_days=int(detail.get("window_trading_days") or 20),
        benchmark=str(detail.get("benchmark") or "sh000300"),
        benchmark_missing=bool(detail.get("benchmark_missing")),
        context=row.get("context") if isinstance(row.get("context"), dict) else None,
    ), None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="只预览不写库")
    ap.add_argument("--limit", type=int, default=1000, help="扫描的已评分决策上限")
    args = ap.parse_args()

    repo = AgentIntelligenceORMRepository()
    rows = repo.list_scored_decisions(limit=args.limit)
    todo = [r for r in rows if not (r.get("learned_lesson") or "").strip()]

    logger.info(f"已评分 {len(rows)} 条，其中缺教训 {len(todo)} 条"
                f"{'（dry-run）' if args.dry_run else ''}")

    filled, skipped = 0, []
    for r in todo:
        lesson, reason = build_lesson(r)
        if lesson is None:
            skipped.append((r.get("decision_id"), reason))
            continue
        if args.dry_run:
            if filled < 5:
                print(f"[预览] {r.get('decision_id')}: {lesson}")
            filled += 1
            continue
        out = repo.update_decision(r["decision_id"], {"learned_lesson": lesson})
        if out is None:
            skipped.append((r.get("decision_id"), "回写失败"))
        else:
            filled += 1

    logger.info(f"完成: filled={filled} skipped={len(skipped)}")
    for did, reason in skipped[:10]:
        logger.warning(f"  跳过 {did}: {reason}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
