"""
市场风格更新任务执行器（task 312 修复，2026-09-03）

修复前：analysis_jobs.MarketStyleUpdateJob 为壳层——直接返回 ok("市场风格检测完成（待实现）",
details={"style": "unknown"})，从不拉数据、从不落库；market_style_state 中残留 2026-06-02
style='unknown'/conf=0.0 的伪造行（从未检测就写死）。审计判定为假成功。

修复后：真实执行闭环——
  1. 拉取新浪行业板块当日/最近收盘截面（akshare，49 行业）
  2. 调用 market_style_detector.compute_style_from_boards 做真实风格计算（显式映射桶、真实分数）
  3. 落库 market_style_state（按 trade_date upsert，指标明细进 metrics）

诚实性原则：
  - 无真实数据（拉取失败/空）→ 不落库、不伪造 → 返回 success=False + 明确 error
  - 数据可用但三风格分化不足 → 落库 style='unknown'/conf=0.0 为【真实观测】（无显著主导风格），
    metrics 注明 basis=当日截面 + 实际桶中位数；与历史伪造 unknown 行可区分（metrics 含真实依据）
  - 绝不写 growth/0.33 之类编造默认

单位口径：新浪行业 涨跌幅 为百分点（如 -1.0559 = -1.06%），bucket_medians/confidence 均为该口径。
"""
import argparse
import sys
import time
from datetime import datetime
from typing import Any, Dict, List, Optional
import structlog

logger = structlog.get_logger(__name__)


def _pick_trade_date(*, explicit: Optional[str], today: str,
                     regime_latest: Optional[str], sentiment_latest: Optional[str],
                     kline_latest: Optional[str], kline_has_today: bool) -> str:
    """纯函数：从多个真实交易日锚点中选出应落库的交易日（无 DB 副作用，可单测）。

    决策语义（对应 A 股板块收盘截面的归属交易日）：
      1. 显式指定（--trade_date/params）→ 用之（历史补算/审计回放）；
      2. 今天被任一独立源确认为真实交易日
         （regime/sentiment 已有今天的行——301 market_daily_snapshot 于 22:00 以真实
         数据源落库；或 daily_klines 今天已有行）→ 用今天；
      3. 否则（周末/节假日/盘后补跑，新浪板块显示的是最近一个已收盘截面）→
         取 regime/sentiment/daily_klines 三个源最近日期的最大者；
      4. 全部不可用 → 今天兜底。

    2026-09-05 回归修复背景：旧实现回退只信 daily_klines 最近交易日，而全市场 K 线
    同步滞后（09-03/09-04 每交易日仅 24 行入库）时 get_latest_trade_date 会停在旧日期，
    导致 09-03 收盘截面被误标 09-02、按 trade_date upsert 覆盖了 09-02 的真实行。
    本实现以 301 独立落库的 market_regime / market_sentiment_daily 为优先锚，kline 仅作补充。
    """
    if explicit:
        s = str(explicit).strip()
        if len(s) == 10:  # YYYY-MM-DD
            return s
        try:
            return datetime.strptime(s, '%Y%m%d').strftime('%Y-%m-%d')
        except ValueError:
            pass  # 非法格式 → 继续走锚点逻辑
    today_confirmed = (regime_latest == today) or (sentiment_latest == today) or kline_has_today
    if today_confirmed:
        return today
    candidates = [d for d in (regime_latest, sentiment_latest, kline_latest) if d]
    if candidates:
        return max(candidates)
    return today


def _resolve_trade_date(params: Dict[str, Any]) -> str:
    """解析落库交易日：params['trade_date'] 优先；否则以多真实源交易日锚点决策。

    真实源锚点（均按日期倒序取最新一条）：
      - market_regime / market_sentiment_daily：301 market_daily_snapshot 每日 22:00
        用真实行情/情绪数据落库（数据源自带 data_date，不依赖 daily_klines 同步进度）
      - daily_klines：数据地基 K 线最新交易日（补充源，可能滞后）
    """
    explicit = params.get('trade_date')
    today = datetime.now().strftime('%Y-%m-%d')
    regime_latest = sentiment_latest = kline_latest = None
    kline_has_today = False
    try:
        from adapters.outbound.repositories.market_perception_repository import (
            MarketRegimeRepository, MarketSentimentDailyRepository,
        )
        regime_rows = MarketRegimeRepository().get_recent(1)
        if regime_rows:
            regime_latest = regime_rows[0].trade_date.isoformat()
        sent_rows = MarketSentimentDailyRepository().get_recent(1)
        if sent_rows:
            sentiment_latest = sent_rows[0].trade_date.isoformat()
    except Exception as e:
        logger.warning(f"读取 regime/sentiment 交易日锚失败, 降级: {e}")
    try:
        from adapters.outbound.repositories.kline_repository import KlineORMRepository
        kline_latest = KlineORMRepository().get_latest_trade_date()
        if kline_latest == today:
            kline_has_today = True
    except Exception as e:
        logger.warning(f"读取 daily_klines 最近交易日失败: {e}")
    return _pick_trade_date(explicit=explicit, today=today,
                            regime_latest=regime_latest, sentiment_latest=sentiment_latest,
                            kline_latest=kline_latest, kline_has_today=kline_has_today)


def execute(**params: Any) -> Dict[str, Any]:
    """执行市场风格检测并落库（scheduler job / __main__ 共用入口）。

    Args:
        trade_date: 落库交易日 YYYY-MM-DD（默认=最近有K线的交易日）
        dry_run: true 则只计算不落库（默认 false）
    """
    start = time.time()
    dry_run = bool(params.get('dry_run', False))
    trade_date = _resolve_trade_date(params)
    degraded: Optional[str] = None
    updated = False

    # 1. 拉取真实行业截面
    try:
        from application.services.market_style_detector import (
            compute_style_from_boards,
            fetch_sina_sector_boards,
        )
    except Exception as e:
        return {
            'success': False,
            'trade_date': trade_date,
            'error': f"import market_style_detector 失败: {e}",
            'elapsed_s': round(time.time() - start, 2),
        }

    boards = fetch_sina_sector_boards()
    if not boards:
        degraded = '新浪行业板块数据拉取失败或为空，未落库（不伪造）'
        return {
            'success': False,
            'trade_date': trade_date,
            'style': None,
            'confidence': None,
            'degraded': True,
            'error': degraded,
            'source': 'sina_sector_spot',
            'elapsed_s': round(time.time() - start, 2),
        }

    # 2. 真实计算
    result = compute_style_from_boards(boards)
    style = result.get('style')            # value/growth/cycle/unknown
    confidence = result.get('confidence', 0.0)
    indicators = result.get('indicators', {})

    # 3. 落库（dry_run 跳过）
    if not dry_run:
        try:
            from adapters.outbound.repositories.market_style_repository import (
                MarketStyleORMRepository,
            )
            metrics = {
                'scores': result.get('scores'),
                'indicators': indicators,
                'source': 'sina_sector_spot',
                'computed_at': datetime.utcnow().isoformat() + 'Z',
            }
            MarketStyleORMRepository().save_market_style(
                trade_date=trade_date, style=style, confidence=confidence, metrics=metrics,
            )
            updated = True
        except Exception as e:
            return {
                'success': False,
                'trade_date': trade_date,
                'style': style,
                'confidence': confidence,
                'error': f"落库 market_style_state 失败: {e}",
                'elapsed_s': round(time.time() - start, 2),
            }
    else:
        logger.info("market_style_update dry_run", trade_date=trade_date, style=style, confidence=confidence)

    return {
        'success': True,
        'trade_date': trade_date,
        'style': style,
        'confidence': confidence,
        'scores': result.get('scores'),
        'bucket_medians': indicators.get('bucket_medians'),
        'boards_total': indicators.get('boards_total'),
        'mapped_total': indicators.get('mapped_total'),
        'coverage': indicators.get('coverage'),
        'degraded': indicators.get('degraded', False),
        'source': 'sina_sector_spot',
        'updated': updated,
        'dry_run': dry_run,
        'note': indicators.get('note') or ('真实计算' if style in ('value', 'growth', 'cycle') else '真实观测：无显著主导风格'),
        'elapsed_s': round(time.time() - start, 2),
    }


def main(argv: Optional[List[str]] = None) -> int:
    """CLI 入口：python -m infrastructure.jobs.market_style_update_job [--trade_date 2026-09-02] [--dry-run]"""
    parser = argparse.ArgumentParser(description='市场风格检测并落库 (task 312)')
    parser.add_argument('--trade_date', default=None, help='落库交易日 YYYY-MM-DD（默认=最近有K线交易日）')
    parser.add_argument('--dry-run', action='store_true', help='只计算不落库')
    args = parser.parse_args(argv)
    result = execute(trade_date=args.trade_date, dry_run=args.dry_run)
    print(f"[market_style_update] {result}")
    return 0 if result.get('success') else 1


if __name__ == '__main__':
    sys.exit(main())
