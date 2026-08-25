"""M1 市场感知服务（RFC 007）

三个能力从"即用即弃的一次性计算"变为"可查询的时间序列资产"：
- M1-1 regime 每日落库（trend_up/trend_down/range/panic/euphoria + 判定依据）
- M1-3 情绪时间序列落库（涨跌家数/新高新低/量能/波动率 + coverage 自查）
- M1-2 每日主线识别（涨停聚类 + 封板资金热度 + catalyst 由盘后例程 LLM 回写）

设计约束：
- 落库走 SQLAlchemy session（infrastructure.persistence.orm.get_session）
- 涨停池/指数日线走数据源管理器（get_data_provider_manager）
- 不造数据：数据源不可用时跳过落库并在返回中显式标记
"""
from datetime import datetime, date as date_cls, timedelta
from typing import Any, Dict, List, Optional

import structlog
from sqlalchemy import text

logger = structlog.get_logger(__name__)

# regime 判定阈值（RFC 007 §3，调整阈值不改表结构）
PANIC_SENTIMENT = 20
PANIC_INDEX_5D = -3.0
EUPHORIA_SENTIMENT = 80
EUPHORIA_VOLUME_RATIO = 2.0
EUPHORIA_UP_PCT = 70.0
TREND_5D_THRESHOLD = 1.0
COVERAGE_MIN = 4000          # 全市场量级自查线
THEME_MIN_LIMIT_UP = 3       # ≥3 只涨停才成团


def _get_session():
    from infrastructure.persistence.orm import get_session
    return get_session()


def _latest_trade_date(session) -> Optional[str]:
    row = session.execute(text(
        "SELECT MAX(trade_date) FROM quant.daily_klines"
    )).fetchone()
    return str(row[0]) if row and row[0] else None


class _KlineOnlyDS:
    """轻量 ds 替代：只挂 KlineORMRepository。

    MarketSentimentService 全程只用 ds.kline.*（breadth/turnover/returns/high_low），
    完整 DataService 会拉起 tushare→infrastructure.config 重链（2026-08-20 该链在
    新鲜检出上因 v2 架构迁移中态而不可导入），此处刻意绕开，保证本服务独立可用。
    """

    def __init__(self):
        from adapters.outbound.repositories import KlineORMRepository
        self.kline = KlineORMRepository()


class MarketPerceptionService:
    """M1 市场感知：每日快照（情绪 + regime + 主线）落库与查询。"""

    def __init__(self, ds=None):
        self.ds = ds if ds is not None else _KlineOnlyDS()

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
        result['success'] = any(
            s.get('stored') for s in result['steps'].values()
        )
        return result

    # ------------------------------------------------------------------
    # M1-3 情绪时间序列落库
    # ------------------------------------------------------------------
    def _snapshot_sentiment(self, trade_date: Optional[str] = None) -> Dict[str, Any]:
        """复用 MarketSentimentService 计算，落库 quant.market_sentiment_daily。

        coverage < 4000 时 partial=true（K线当日同步未完成的自卫，RFC 007 §4）。
        """
        from application.services.market_sentiment_service import MarketSentimentService

        try:
            raw = MarketSentimentService(self.ds).analyze_market_sentiment()
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

        session = _get_session()
        try:
            session.execute(text("""
                INSERT INTO quant.market_sentiment_daily
                    (trade_date, up_count, down_count, flat_count, ad_ratio,
                     new_high_count, new_low_count, volume_ratio, total_turnover,
                     volatility, fear_greed_index, coverage, partial)
                VALUES (:d, :up, :down, :flat, :adr, :nh, :nl, :vr, :to, :vlt, :fgi, :cov, :partial)
                ON CONFLICT (trade_date) DO UPDATE SET
                    up_count=EXCLUDED.up_count, down_count=EXCLUDED.down_count,
                    flat_count=EXCLUDED.flat_count, ad_ratio=EXCLUDED.ad_ratio,
                    new_high_count=EXCLUDED.new_high_count, new_low_count=EXCLUDED.new_low_count,
                    volume_ratio=EXCLUDED.volume_ratio, total_turnover=EXCLUDED.total_turnover,
                    volatility=EXCLUDED.volatility, fear_greed_index=EXCLUDED.fear_greed_index,
                    coverage=EXCLUDED.coverage, partial=EXCLUDED.partial
            """), {
                'd': resolved_date, 'up': up, 'down': down, 'flat': flat,
                'adr': ad.get('ratio'),
                'nh': nhl.get('new_high_count'), 'nl': nhl.get('new_low_count'),
                'vr': vol.get('volume_ratio'), 'to': vol.get('recent_avg_volume'),
                'vlt': vlt.get('volatility'), 'fgi': raw.get('fear_greed_index'),
                'cov': coverage, 'partial': partial,
            })
            session.commit()
        except Exception as e:
            session.rollback()
            logger.error(f"M1-3 情绪落库失败: {e}", exc_info=True)
            return {'stored': False, 'error': str(e)}

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
        from adapters.outbound.datasources.manager import get_data_provider_manager

        try:
            result = get_data_provider_manager().get_index_daily('sh000300')
        except Exception as e:
            logger.warning(f"指数日线获取失败: {e}")
            return None
        if not result.get('success') or not result.get('data'):
            return None

        records = result['data'].data.get('records', [])
        if len(records) < 60:
            return None

        # 兼容中文/英文键
        def _close(r):
            return r.get('close') or r.get('收盘')
        def _date(r):
            return str(r.get('date') or r.get('日期'))

        rows = sorted(
            [{'date': _date(r), 'close': float(_close(r))} for r in records if _close(r)],
            key=lambda x: x['date'],
        )
        if trade_date:
            rows = [r for r in rows if r['date'] <= trade_date]
        if len(rows) < 60:
            return None

        closes = [r['close'] for r in rows]
        close = closes[-1]
        ma20 = sum(closes[-20:]) / 20
        ma60 = sum(closes[-60:]) / 60
        chg5d = (close / closes[-6] - 1) * 100 if len(closes) >= 6 else 0.0
        # 趋势得分：相对 MA20/MA60 位置，[-1,1]
        score = ((1 if close > ma20 else -1) + (1 if ma20 > ma60 else -1)) / 2
        return {
            'date': rows[-1]['date'], 'close': close, 'ma20': ma20, 'ma60': ma60,
            'chg5d_pct': round(chg5d, 2), 'trend_score': score,
        }

    @staticmethod
    def _classify_regime(sentiment: float, volume_ratio: Optional[float],
                         up_pct: Optional[float], chg5d: float,
                         close: float, ma20: float, ma60: float) -> str:
        """RFC 007 §3 判定规则（按优先级）。"""
        vr = volume_ratio or 1.0
        up = up_pct if up_pct is not None else 50.0
        if sentiment <= PANIC_SENTIMENT and vr < 1.0 and chg5d < PANIC_INDEX_5D:
            return 'panic'
        if sentiment >= EUPHORIA_SENTIMENT and vr > EUPHORIA_VOLUME_RATIO and up > EUPHORIA_UP_PCT:
            return 'euphoria'
        if close > ma20 and ma20 > ma60 and chg5d > TREND_5D_THRESHOLD:
            return 'trend_up'
        if close < ma20 and ma20 < ma60 and chg5d < -TREND_5D_THRESHOLD:
            return 'trend_down'
        return 'range'

    def _judge_and_store_regime(self, trade_date: Optional[str] = None) -> Dict[str, Any]:
        """读取当日情绪落库行 + 指数趋势，按规则判定 regime 并落库。"""
        session = _get_session()
        if not trade_date:
            trade_date = _latest_trade_date(session)
        if not trade_date:
            return {'stored': False, 'error': '无交易日数据'}

        srow = session.execute(text("""
            SELECT fear_greed_index, volume_ratio, up_count, down_count, flat_count
            FROM quant.market_sentiment_daily WHERE trade_date = :d
        """), {'d': trade_date}).fetchone()
        if not srow:
            return {'stored': False, 'error': f'{trade_date} 情绪未落库（先跑 M1-3）'}

        sentiment = float(srow[0] or 50)
        volume_ratio = srow[1]
        total = (srow[2] or 0) + (srow[3] or 0) + (srow[4] or 0)
        up_pct = (srow[2] or 0) / total * 100 if total else None

        trend = self._index_trend(trade_date)
        if not trend:
            return {'stored': False, 'error': '指数趋势不可用（sh000300 数据源失败或历史不足60日）'}

        regime = self._classify_regime(
            sentiment, volume_ratio, up_pct,
            trend['chg5d_pct'], trend['close'], trend['ma20'], trend['ma60'],
        )
        ad_ratio = (srow[2] / srow[3]) if srow[3] else None
        reason = (
            f"情绪{sentiment:.0f}, 量能{volume_ratio and round(volume_ratio, 2)}, "
            f"涨家占比{up_pct and round(up_pct, 1)}%, "
            f"指数5日{trend['chg5d_pct']:+.1f}%, "
            f"close{'>' if trend['close'] > trend['ma20'] else '<'}MA20, "
            f"MA20{'>' if trend['ma20'] > trend['ma60'] else '<'}MA60 → {regime}"
        )

        try:
            session.execute(text("""
                INSERT INTO quant.market_regime
                    (trade_date, regime, index_trend_score, sentiment_score,
                     volume_ratio, ad_ratio, reason)
                VALUES (:d, :r, :ts, :ss, :vr, :ar, :reason)
                ON CONFLICT (trade_date) DO UPDATE SET
                    regime=EXCLUDED.regime, index_trend_score=EXCLUDED.index_trend_score,
                    sentiment_score=EXCLUDED.sentiment_score, volume_ratio=EXCLUDED.volume_ratio,
                    ad_ratio=EXCLUDED.ad_ratio, reason=EXCLUDED.reason
            """), {
                'd': trade_date, 'r': regime, 'ts': trend['trend_score'],
                'ss': sentiment, 'vr': volume_ratio, 'ar': ad_ratio, 'reason': reason,
            })
            session.commit()
        except Exception as e:
            session.rollback()
            logger.error(f"M1-1 regime 落库失败: {e}", exc_info=True)
            return {'stored': False, 'error': str(e)}

        return {'stored': True, 'trade_date': trade_date, 'regime': regime, 'reason': reason}

    # ------------------------------------------------------------------
    # M1-2 主线识别（涨停聚类 + 封板资金热度）
    # ------------------------------------------------------------------
    def detect_and_store_themes(self, trade_date: Optional[str] = None,
                                top_n: int = 3) -> Dict[str, Any]:
        """涨停池按所属行业聚类，≥3 只成团，按涨停数+封板资金排序取 Top3 落库。

        catalyst 字段由盘后例程 agent（LLM）回写（PUT /api/market/themes/{id}）。
        数据源不可用时跳过落库并显式标记（不造数据）。
        """
        from adapters.outbound.datasources.manager import get_data_provider_manager

        date_arg = (trade_date or datetime.now().strftime('%Y-%m-%d')).replace('-', '')
        try:
            result = get_data_provider_manager().get_zt_pool(date_arg)
        except Exception as e:
            logger.warning(f"涨停池获取失败: {e}")
            return {'stored': False, 'error': str(e)}
        if not result.get('success') or not result.get('data'):
            return {'stored': False, 'error': '涨停池数据源不可用', 'trade_date': date_arg}

        records = result['data'].data.get('records', [])
        if not records:
            return {'stored': False, 'error': f'{date_arg} 涨停池为空（非交易日？）',
                    'trade_date': date_arg}

        # 按行业聚类
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
        # 排序：涨停数优先，封板资金次之
        candidates.sort(key=lambda kv: (len(kv[1]), sum(r['seal_fund'] for r in kv[1])),
                        reverse=True)
        top = candidates[:top_n]
        if not top:
            return {'stored': False, 'error': f'{date_arg} 无 ≥{THEME_MIN_LIMIT_UP} 只涨停的板块',
                    'trade_date': date_arg}

        # 格式化日期 YYYYMMDD → YYYY-MM-DD
        fmt_date = f"{date_arg[:4]}-{date_arg[4:6]}-{date_arg[6:8]}"
        
        session = _get_session()
        stored = []
        try:
            # 幂等：当日重跑先清旧记录（保留 LLM 已回写 catalyst 的记录）
            session.execute(text(
                "DELETE FROM quant.market_theme WHERE trade_date = :d AND catalyst IS NULL"
            ), {'d': fmt_date})
            for rank, (sector, rows) in enumerate(top, start=1):
                seal_total = sum(r['seal_fund'] for r in rows) / 1e8  # → 亿
                confidence = min(1.0, 0.4 + len(rows) * 0.08 + min(seal_total, 50) * 0.01)
                import json
                cur = session.execute(text("""
                    INSERT INTO quant.market_theme
                        (trade_date, rank, theme, sector, limit_up_count, stocks,
                         fund_flow, confidence)
                    VALUES (:d, :rank, :theme, :sector, :cnt, CAST(:stocks AS jsonb), :ff, :conf)
                    ON CONFLICT (trade_date, rank) DO UPDATE SET
                        theme=EXCLUDED.theme, sector=EXCLUDED.sector,
                        limit_up_count=EXCLUDED.limit_up_count, stocks=EXCLUDED.stocks,
                        fund_flow=EXCLUDED.fund_flow, confidence=EXCLUDED.confidence
                    RETURNING id
                """), {
                    'd': fmt_date, 'rank': rank, 'theme': sector, 'sector': sector,
                    'cnt': len(rows),
                    'stocks': json.dumps(
                        [{k: v for k, v in r.items() if k != 'seal_fund'} for r in rows[:5]],
                        ensure_ascii=False),
                    'ff': round(seal_total, 2), 'conf': round(confidence, 2),
                })
                stored.append({'id': cur.fetchone()[0], 'rank': rank, 'sector': sector,
                               'limit_up_count': len(rows), 'seal_fund_yi': round(seal_total, 2)})
            session.commit()
        except Exception as e:
            session.rollback()
            logger.error(f"M1-2 主线落库失败: {e}", exc_info=True)
            return {'stored': False, 'error': str(e)}

        return {'stored': True, 'trade_date': fmt_date, 'themes': stored}

    # ------------------------------------------------------------------
    # M1-1c 历史回填（纯 SQL：daily_klines 重算近 N 日 breadth/量能 + 指数趋势）
    # ------------------------------------------------------------------
    def backfill_regime(self, days: int = 120) -> Dict[str, Any]:
        """回填近 N 个交易日的 regime。

        breadth/量能量来自 daily_klines（SQL 聚合）；指数趋势来自 provider 全量历史。
        情绪分无法历史重算（新高新低等依赖截面数据），用映射近似并在 reason 标注。
        """
        session = _get_session()

        # 每日 breadth + 量能（SQL 聚合，close vs 前收 用 LAG）
        rows = session.execute(text("""
            WITH px AS (
                SELECT symbol, trade_date, close,
                       LAG(close) OVER (PARTITION BY symbol ORDER BY trade_date) AS prev_close,
                       volume, amount
                FROM quant.daily_klines
                WHERE trade_date > CURRENT_DATE - INTERVAL '1 day' * (:days * 2)
            ),
            daily AS (
                SELECT trade_date,
                       COUNT(*) FILTER (WHERE prev_close IS NOT NULL AND close > prev_close) AS up,
                       COUNT(*) FILTER (WHERE prev_close IS NOT NULL AND close < prev_close) AS down,
                       COUNT(*) FILTER (WHERE prev_close IS NOT NULL AND close = prev_close) AS flat,
                       SUM(amount) AS turnover
                FROM px GROUP BY trade_date
            ),
            vol_ratio AS (
                SELECT trade_date, up, down, flat, turnover,
                       AVG(turnover) OVER (ORDER BY trade_date ROWS BETWEEN 4 PRECEDING AND CURRENT ROW)
                       / NULLIF(AVG(turnover) OVER (ORDER BY trade_date ROWS BETWEEN 24 PRECEDING AND 5 PRECEDING), 0)
                       AS vr
                FROM daily
            )
            SELECT trade_date, up, down, flat, turnover, vr FROM vol_ratio
            ORDER BY trade_date DESC LIMIT :days
        """), {'days': days}).fetchall()

        if not rows:
            return {'success': False, 'error': 'daily_klines 无历史数据'}

        # 指数全量历史（一次拉取，内存算 MA）
        from adapters.outbound.datasources.manager import get_data_provider_manager
        iresult = get_data_provider_manager().get_index_daily('sh000300')
        if not iresult.get('success'):
            return {'success': False, 'error': '指数历史不可用'}
        irecords = iresult['data'].data.get('records', [])
        def _ic(r): return r.get('close') or r.get('收盘')
        def _id(r): return str(r.get('date') or r.get('日期'))
        irows = sorted(
            [{'date': _id(r), 'close': float(_ic(r))} for r in irecords if _ic(r)],
            key=lambda x: x['date'])
        icloses = [r['close'] for r in irows]
        idates = [r['date'] for r in irows]
        import bisect

        stored = 0
        errors = 0
        for trade_date, up, down, flat, turnover, vr in rows:
            d = str(trade_date)
            pos = bisect.bisect_right(idates, d) - 1
            if pos < 59:
                continue  # 历史不足 60 日无法算 MA60
            closes = icloses[:pos + 1]
            close = closes[-1]
            ma20 = sum(closes[-20:]) / 20
            ma60 = sum(closes[-60:]) / 60
            chg5d = (close / closes[-6] - 1) * 100 if len(closes) >= 6 else 0.0
            total = (up or 0) + (down or 0) + (flat or 0)
            up_pct = (up or 0) / total * 100 if total else None
            # 情绪分近似（历史截面数据不可得）：由涨家占比和量能比映射，reason 标注
            sentiment_approx = max(0.0, min(100.0,
                50 + ((up_pct or 50) - 50) * 0.8 + (((vr or 1) - 1) * 20)))
            regime = self._classify_regime(sentiment_approx, vr, up_pct, chg5d, close, ma20, ma60)
            score = ((1 if close > ma20 else -1) + (1 if ma20 > ma60 else -1)) / 2
            ad_ratio = (up / down) if down else None
            reason = (f"[回填近似] 情绪≈{sentiment_approx:.0f}(映射), 量能{vr and round(float(vr), 2)}, "
                      f"涨家占比{up_pct and round(up_pct, 1)}%, 指数5日{chg5d:+.1f}%, "
                      f"close{'>' if close > ma20 else '<'}MA20, "
                      f"MA20{'>' if ma20 > ma60 else '<'}MA60 → {regime}")
            try:
                session.execute(text("""
                    INSERT INTO quant.market_regime
                        (trade_date, regime, index_trend_score, sentiment_score,
                         volume_ratio, ad_ratio, reason)
                    VALUES (:d, :r, :ts, :ss, :vr, :ar, :reason)
                    ON CONFLICT (trade_date) DO UPDATE SET
                        regime=EXCLUDED.regime, index_trend_score=EXCLUDED.index_trend_score,
                        sentiment_score=EXCLUDED.sentiment_score,
                        volume_ratio=EXCLUDED.volume_ratio, ad_ratio=EXCLUDED.ad_ratio,
                        reason=EXCLUDED.reason
                """), {'d': d, 'r': regime, 'ts': score, 'ss': round(sentiment_approx, 1),
                       'vr': float(vr) if vr else None, 'ar': ad_ratio, 'reason': reason})
                stored += 1
                if stored % 20 == 0:
                    session.commit()
            except Exception as e:
                session.rollback()
                errors += 1
                logger.warning(f"回填 {d} 失败: {e}")
        session.commit()

        return {'success': True, 'stored': stored, 'errors': errors,
                'requested_days': days}
