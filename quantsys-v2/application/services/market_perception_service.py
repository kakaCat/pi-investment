"""M1 市场感知服务（RFC 007）

三个能力从"即用即弃的一次性计算"变为"可查询的时间序列资产"：
- M1-1 regime 每日落库（trend_up/trend_down/range/panic/euphoria + 判定依据）
- M1-3 情绪时间序列落库（涨跌家数/新高新低/量能/波动率 + coverage 自查）
- M1-2 每日主线识别（涨停聚类 + 封板资金热度 + catalyst 由盘后例程 LLM 回写）

设计约束：
- 落库一律走 ORM Repository（MarketRegimeRepository 等），服务层禁止裸 SQL
- daily_klines 聚合查询归 KlineORMRepository（get_market_breadth_history）
- 涨停池/指数日线走数据源管理器（get_data_provider_manager）
- 不造数据：数据源不可用时跳过落库并在返回中显式标记
"""
import bisect
from datetime import datetime
from typing import Any, Dict, List, Optional

import structlog

logger = structlog.get_logger(__name__)

# ------------------------------------------------------------------
# 常量（RFC 007 §3，调整阈值不改表结构）
# ------------------------------------------------------------------
PANIC_SENTIMENT = 20
PANIC_INDEX_5D_PCT = -3.0
EUPHORIA_SENTIMENT = 80
EUPHORIA_VOLUME_RATIO = 2.0
EUPHORIA_UP_PCT = 70.0
TREND_5D_THRESHOLD_PCT = 1.0
COVERAGE_MIN = 4000            # 全市场量级自查线
THEME_MIN_LIMIT_UP = 3         # ≥3 只涨停才成团
THEME_TOP_STOCKS = 5           # 主线落库最多保留的成分股数
INDEX_5D_LOOKBACK = 6          # 5 日涨跌需要 6 个数据点（含当日）
MA20_PERIOD = 20
MA60_PERIOD = 60
INDEX_MIN_HISTORY = 60         # MA60 所需最少历史


def _ma(values: List[float], period: int) -> float:
    """简单移动平均。"""
    return sum(values[-period:]) / period


class MarketPerceptionService:
    """M1 市场感知：每日快照（情绪 + regime + 主线）落库与查询。"""

    def __init__(self, kline_repo=None):
        if kline_repo is None:
            from infrastructure.services.service_factory import ServiceFactory
            kline_repo = ServiceFactory.get_kline_repository()
        self.kline_repo = kline_repo
        from adapters.outbound.repositories import (
            MarketRegimeRepository, MarketSentimentDailyRepository,
            MarketThemeRepository,
        )
        self.regime_repo = MarketRegimeRepository()
        self.sentiment_repo = MarketSentimentDailyRepository()
        self.theme_repo = MarketThemeRepository()

    # ------------------------------------------------------------------
    # 入口：每日快照
    # ------------------------------------------------------------------
    def run_daily_snapshot(self, trade_date: Optional[str] = None) -> Dict[str, Any]:
        """执行当日完整快照：M1-3 情绪 → M1-1 regime → M1-2 主线。

        各步骤独立容错：单步失败不影响其他步骤落库，失败原因显式返回。
        """
        result: Dict[str, Any] = {'trade_date': trade_date, 'steps': {}}

        sentiment = self._snapshot_sentiment(trade_date)
        result['steps']['sentiment'] = sentiment
        resolved_date = sentiment.get('trade_date') or trade_date

        regime = self._judge_and_store_regime(resolved_date)
        result['steps']['regime'] = regime

        themes = self.detect_and_store_themes(resolved_date)
        result['steps']['themes'] = themes

        result['trade_date'] = resolved_date
        all_stored = all(s.get('stored') for s in result['steps'].values())
        any_stored = any(s.get('stored') for s in result['steps'].values())
        result['success'] = any_stored
        result['all_steps_success'] = all_stored
        result['partial_success'] = any_stored and not all_stored
        failed = [k for k, v in result['steps'].items() if not v.get('stored')]
        result['failed_steps'] = failed or None
        return result

    # ------------------------------------------------------------------
    # M1-3 情绪时间序列落库
    # ------------------------------------------------------------------
    def _snapshot_sentiment(self, trade_date: Optional[str] = None) -> Dict[str, Any]:
        """复用 MarketSentimentService 计算，落库 market_sentiment_daily。

        coverage < COVERAGE_MIN 时 partial=true（K线当日同步未完成的自卫）。
        """
        from application.services.market_sentiment_service import MarketSentimentService

        try:
            raw = MarketSentimentService(self.kline_repo).analyze_market_sentiment()
        except Exception as e:
            logger.error(f"M1-3 情绪计算失败: {e}", exc_info=True)
            return {'stored': False, 'error': str(e)}

        if raw.get('error'):
            return {'stored': False, 'error': raw['error']}

        ind = raw.get('indicators', {})
        ad = ind.get('advance_decline') or {}
        vol = ind.get('volume') or {}
        vlt = ind.get('volatility') or {}
        nhl = ind.get('new_high_low') or {}

        if ad.get('error'):
            return {'stored': False, 'error': f"涨跌家数不可用: {ad['error']}"}

        resolved_date = trade_date or ad.get('data_date')
        if not resolved_date:
            return {'stored': False, 'error': '无法确定交易日期'}

        up = int(ad.get('up_count') or 0)
        down = int(ad.get('down_count') or 0)
        flat = int(ad.get('flat_count') or 0)
        coverage = up + down + flat
        partial = coverage < COVERAGE_MIN

        ok = self.sentiment_repo.upsert(
            resolved_date,
            up_count=up, down_count=down, flat_count=flat,
            ad_ratio=ad.get('ratio'),
            new_high_count=nhl.get('new_high_count'),
            new_low_count=nhl.get('new_low_count'),
            volume_ratio=vol.get('volume_ratio'),
            total_turnover=vol.get('recent_avg_volume'),
            volatility=vlt.get('volatility'),
            fear_greed_index=raw.get('fear_greed_index'),
            coverage=coverage, partial=partial,
        )
        if not ok:
            return {'stored': False, 'error': 'sentiment upsert 失败（详见日志）'}

        return {
            'stored': True, 'trade_date': resolved_date,
            'coverage': coverage, 'partial': partial,
            'fear_greed_index': raw.get('fear_greed_index'),
            'degraded': raw.get('degraded', False),
        }

    # ------------------------------------------------------------------
    # M1-1 regime 判定与落库
    # ------------------------------------------------------------------
    def _index_trend(self, trade_date: Optional[str] = None) -> Optional[Dict[str, float]]:
        """沪深300 趋势指标：close、MA20、MA60、5 日涨跌、趋势得分。

        数据源：provider get_index_daily('sh000300')（daily_klines 不含指数）。
        """
        history = self._fetch_index_history()
        if not history:
            return None

        rows = history
        if trade_date:
            rows = [r for r in rows if r['date'] <= trade_date]
        if len(rows) < INDEX_MIN_HISTORY:
            return None

        closes = [r['close'] for r in rows]
        close = closes[-1]
        ma20 = _ma(closes, MA20_PERIOD)
        ma60 = _ma(closes, MA60_PERIOD)
        chg5d = ((close / closes[-INDEX_5D_LOOKBACK] - 1) * 100
                 if len(closes) >= INDEX_5D_LOOKBACK else 0.0)
        # 趋势得分：相对 MA20/MA60 位置，[-1,1]
        score = ((1 if close > ma20 else -1) + (1 if ma20 > ma60 else -1)) / 2
        return {
            'date': rows[-1]['date'], 'close': close, 'ma20': ma20, 'ma60': ma60,
            'chg5d_pct': round(chg5d, 2), 'trend_score': score,
        }

    def _fetch_index_history(self) -> Optional[List[Dict[str, Any]]]:
        """拉取沪深300 全量日线（升序），失败返回 None。"""
        from adapters.outbound.datasources.manager import get_data_provider_manager

        try:
            result = get_data_provider_manager().get_index_daily('sh000300')
        except Exception as e:
            logger.warning(f"指数日线获取失败: {e}")
            return None
        if not result.get('success') or not result.get('data'):
            return None

        records = result['data'].data.get('records', [])

        def _close(r):
            return r.get('close') or r.get('收盘')

        def _date(r):
            return str(r.get('date') or r.get('日期'))

        rows = sorted(
            [{'date': _date(r), 'close': float(_close(r))} for r in records if _close(r)],
            key=lambda x: x['date'],
        )
        return rows or None

    @staticmethod
    def _classify_regime(sentiment: float, volume_ratio: Optional[float],
                         up_pct: Optional[float], chg5d: float,
                         close: float, ma20: float, ma60: float) -> str:
        """RFC 007 §3 判定规则（按优先级：panic > euphoria > trend > range）。"""
        vr = volume_ratio or 1.0
        up = up_pct if up_pct is not None else 50.0
        if (sentiment <= PANIC_SENTIMENT and vr < 1.0
                and chg5d < PANIC_INDEX_5D_PCT):
            return 'panic'
        if (sentiment >= EUPHORIA_SENTIMENT and vr > EUPHORIA_VOLUME_RATIO
                and up > EUPHORIA_UP_PCT):
            return 'euphoria'
        if close > ma20 and ma20 > ma60 and chg5d > TREND_5D_THRESHOLD_PCT:
            return 'trend_up'
        if close < ma20 and ma20 < ma60 and chg5d < -TREND_5D_THRESHOLD_PCT:
            return 'trend_down'
        return 'range'

    @staticmethod
    def _build_reason(sentiment: float, volume_ratio: Optional[float],
                      up_pct: Optional[float], chg5d: float, close: float,
                      ma20: float, ma60: float, regime: str,
                      prefix: str = '') -> str:
        """reason 字段统一拼装（判定依据含全部指标值）。"""
        return (
            f"{prefix}情绪{sentiment:.0f}, "
            f"量能{round(volume_ratio, 2) if volume_ratio else None}, "
            f"涨家占比{round(up_pct, 1) if up_pct is not None else None}%, "
            f"指数5日{chg5d:+.1f}%, "
            f"close{'>' if close > ma20 else '<'}MA20, "
            f"MA20{'>' if ma20 > ma60 else '<'}MA60 → {regime}"
        )

    def _judge_and_store_regime(self, trade_date: Optional[str] = None) -> Dict[str, Any]:
        """读取当日情绪落库行 + 指数趋势，按规则判定 regime 并落库。"""
        if not trade_date:
            trade_date = self._latest_trade_date()
        if not trade_date:
            return {'stored': False, 'error': '无交易日数据'}

        srow = self.sentiment_repo.get_by_date(trade_date)
        if not srow:
            return {'stored': False, 'error': f'{trade_date} 情绪未落库（先跑 M1-3）'}

        metrics = self._regime_metrics(srow)
        trend = self._index_trend(str(trade_date))
        if not trend:
            return {'stored': False,
                    'error': '指数趋势不可用（sh000300 数据源失败或历史不足60日）'}

        regime = self._classify_regime(
            metrics['sentiment'], metrics['volume_ratio'], metrics['up_pct'],
            trend['chg5d_pct'], trend['close'], trend['ma20'], trend['ma60'],
        )
        reason = self._build_reason(
            metrics['sentiment'], metrics['volume_ratio'], metrics['up_pct'],
            trend['chg5d_pct'], trend['close'], trend['ma20'], trend['ma60'], regime,
        )

        ok = self.regime_repo.upsert(
            trade_date, regime, reason,
            index_trend_score=trend['trend_score'],
            sentiment_score=metrics['sentiment'],
            volume_ratio=metrics['volume_ratio'],
            ad_ratio=metrics['ad_ratio'],
        )
        if not ok:
            return {'stored': False, 'error': 'regime upsert 失败（详见日志）'}
        return {'stored': True, 'trade_date': str(trade_date),
                'regime': regime, 'reason': reason}

    def _latest_trade_date(self) -> Optional[str]:
        """最新交易日（daily_klines 最大日期）。"""
        return self.kline_repo.get_latest_trade_date()

    @staticmethod
    def _regime_metrics(srow) -> Dict[str, Any]:
        """从情绪落库行提取 regime 判定所需指标。"""
        total = (srow.up_count or 0) + (srow.down_count or 0) + (srow.flat_count or 0)
        return {
            'sentiment': float(srow.fear_greed_index or 50),
            'volume_ratio': srow.volume_ratio,
            'up_pct': (srow.up_count or 0) / total * 100 if total else None,
            'ad_ratio': ((srow.up_count or 0) / srow.down_count
                         if srow.down_count else None),
        }

    # ------------------------------------------------------------------
    # M1-2 主线识别（涨停聚类 + 封板资金热度）
    # ------------------------------------------------------------------
    def detect_and_store_themes(self, trade_date: Optional[str] = None,
                                top_n: int = 3) -> Dict[str, Any]:
        """涨停池按所属行业聚类，≥3 只成团，按涨停数+封板资金排序取 Top3 落库。

        catalyst 字段由盘后例程 agent（LLM）回写（PUT /api/market/perception/themes/{id}）。
        数据源不可用时跳过落库并显式标记（不造数据）。
        """
        records, fetch_err, date_arg = self._fetch_zt_pool(trade_date)
        if fetch_err:
            return {'stored': False, 'error': fetch_err, 'trade_date': date_arg}

        top = self._cluster_top_themes(records, top_n)
        if not top:
            return {'stored': False,
                    'error': f'{date_arg} 无 ≥{THEME_MIN_LIMIT_UP} 只涨停的板块',
                    'trade_date': date_arg}

        return self._store_themes(date_arg, top)

    def _fetch_zt_pool(self, trade_date: Optional[str]):
        """拉取涨停池记录。返回 (records, error, date_str)。"""
        from adapters.outbound.datasources.manager import get_data_provider_manager

        date_arg = (trade_date or datetime.now().strftime('%Y-%m-%d')).replace('-', '')
        try:
            result = get_data_provider_manager().get_zt_pool(date_arg)
        except Exception as e:
            logger.warning(f"涨停池获取失败: {e}")
            return None, str(e), date_arg
        if not result.get('success') or not result.get('data'):
            return None, '涨停池数据源不可用', date_arg
        records = result['data'].data.get('records', [])
        if not records:
            return None, f'{date_arg} 涨停池为空（非交易日？）', date_arg
        return records, None, date_arg

    @staticmethod
    def _cluster_top_themes(records: List[dict], top_n: int) -> List[tuple]:
        """按行业聚类并排序，返回 Top N [(sector, rows)]。"""
        clusters: Dict[str, List[dict]] = {}
        for row in records:
            sector = row.get('所属行业') or '未知'
            clusters.setdefault(sector, []).append({
                'symbol': str(row.get('代码', '')),
                'name': row.get('名称', ''),
                'change_pct': row.get('涨跌幅', 0),
                'seal_fund': row.get('封板资金', 0) or 0,
            })

        candidates = [
            (sector, rows) for sector, rows in clusters.items()
            if len(rows) >= THEME_MIN_LIMIT_UP and sector != '未知'
        ]
        candidates.sort(
            key=lambda kv: (len(kv[1]), sum(r['seal_fund'] for r in kv[1])),
            reverse=True)
        return candidates[:top_n]

    def _store_themes(self, date_arg: str, top: List[tuple]) -> Dict[str, Any]:
        """Top 主线落库。commit 成功后才构造返回值（修复：stored 与 DB 一致）。"""
        fmt_date = f"{date_arg[:4]}-{date_arg[4:6]}-{date_arg[6:8]}"

        # 幂等：当日重跑先清无 catalyst 的旧记录（保留 LLM 已回写的）
        self.theme_repo.delete_without_catalyst(fmt_date)

        stored = []
        for rank, (sector, rows) in enumerate(top, start=1):
            seal_total = sum(r['seal_fund'] for r in rows) / 1e8  # → 亿
            confidence = min(1.0, 0.4 + len(rows) * 0.08 + min(seal_total, 50) * 0.01)
            stocks = [{k: v for k, v in r.items() if k != 'seal_fund'}
                      for r in rows[:THEME_TOP_STOCKS]]
            row_id = self.theme_repo.upsert(
                fmt_date, rank, sector, sector,
                limit_up_count=len(rows), stocks=stocks,
                fund_flow=round(seal_total, 2), confidence=round(confidence, 2),
            )
            if row_id is None:
                return {'stored': False,
                        'error': f'theme upsert 失败 rank={rank}（详见日志）',
                        'trade_date': fmt_date}
            stored.append({'id': row_id, 'rank': rank, 'sector': sector,
                           'limit_up_count': len(rows),
                           'seal_fund_yi': round(seal_total, 2)})

        return {'stored': True, 'trade_date': fmt_date, 'themes': stored}

    # ------------------------------------------------------------------
    # M1-1c 历史回填
    # ------------------------------------------------------------------
    def backfill_regime(self, days: int = 120) -> Dict[str, Any]:
        """回填近 N 个交易日的 regime。

        breadth/量能来自 KlineORMRepository.get_market_breadth_history；
        指数趋势来自 provider 全量历史；情绪分无法历史重算，用映射近似并在
        reason 标注 [回填近似]。批量 upsert（无 N+1）。
        """
        breadth = self.kline_repo.get_market_breadth_history(days)
        if not breadth:
            return {'success': False, 'error': 'daily_klines 无历史数据'}

        irows = self._fetch_index_history()
        if not irows or len(irows) < INDEX_MIN_HISTORY:
            return {'success': False, 'error': '指数历史不可用或不足60日'}
        icloses = [r['close'] for r in irows]
        idates = [r['date'] for r in irows]

        rows_to_upsert = []
        for b in breadth:
            row = self._build_backfill_row(b, idates, icloses)
            if row:
                rows_to_upsert.append(row)

        stored = self.regime_repo.upsert_batch(rows_to_upsert)
        return {'success': stored > 0, 'stored': stored,
                'errors': len(rows_to_upsert) - stored, 'requested_days': days}

    def _build_backfill_row(self, b: Dict[str, Any], idates: List[str],
                            icloses: List[float]) -> Optional[Dict[str, Any]]:
        """构造单日回填行；历史不足 MA60 时返回 None。"""
        d = str(b['trade_date'])
        pos = bisect.bisect_right(idates, d) - 1
        if pos < INDEX_MIN_HISTORY - 1:
            return None

        closes = icloses[:pos + 1]
        close = closes[-1]
        ma20 = _ma(closes, MA20_PERIOD)
        ma60 = _ma(closes, MA60_PERIOD)
        chg5d = ((close / closes[-INDEX_5D_LOOKBACK] - 1) * 100
                 if len(closes) >= INDEX_5D_LOOKBACK else 0.0)

        total = b['up'] + b['down'] + b['flat']
        up_pct = b['up'] / total * 100 if total else None
        vr = b['volume_ratio']
        # 情绪分近似（历史截面数据不可得）：涨家占比 + 量能比映射
        sentiment_approx = max(0.0, min(100.0,
            50 + ((up_pct or 50) - 50) * 0.8 + (((vr or 1) - 1) * 20)))

        regime = self._classify_regime(sentiment_approx, vr, up_pct,
                                       chg5d, close, ma20, ma60)
        score = ((1 if close > ma20 else -1) + (1 if ma20 > ma60 else -1)) / 2
        reason = self._build_reason(sentiment_approx, vr, up_pct, chg5d,
                                    close, ma20, ma60, regime,
                                    prefix='[回填近似] 情绪为映射值, ')

        return {
            'trade_date': b['trade_date'], 'regime': regime, 'reason': reason,
            'index_trend_score': score,
            'sentiment_score': round(sentiment_approx, 1),
            'volume_ratio': vr,
            'ad_ratio': (b['up'] / b['down'] if b['down'] else None),
        }
