"""market_style_update_job 交易日解析单测（2026-09-05 回归防护）。

回归背景：旧 _resolve_trade_date 回退只信 daily_klines 最近交易日；全市场 K 线同步
滞后时（09-03/09-04 每交易日仅 24 行入库）get_latest_trade_date 停在旧日期，导致
09-03 收盘截面被误标 09-02、upsert 覆盖了 09-02 的真实行（value/0.6206）。

修复：以 301 market_daily_snapshot 独立落库的 market_regime / market_sentiment_daily
为优先交易日锚（22:00 以真实数据源 data_date 落库，不依赖 kline 同步），daily_klines
仅作补充源。本测试覆盖 _pick_trade_date 纯函数的全部决策分支。
"""
import pytest

from infrastructure.jobs.market_style_update_job import _pick_trade_date


def _pick(explicit=None, today='2026-09-05', regime=None, sentiment=None,
          kline=None, kline_today=False):
    return _pick_trade_date(
        explicit=explicit, today=today,
        regime_latest=regime, sentiment_latest=sentiment,
        kline_latest=kline, kline_has_today=kline_today,
    )


class TestPickTradeDate:
    def test_explicit_iso_priority(self):
        """显式指定 YYYY-MM-DD 优先于一切锚点（历史补算/审计回放）。"""
        assert _pick(explicit='2026-09-02', regime='2026-09-04',
                     sentiment='2026-09-04', kline='2026-09-04') == '2026-09-02'

    def test_explicit_compact_format(self):
        """兼容 YYYYMMDD 紧凑格式。"""
        assert _pick(explicit='20260902', regime='2026-09-04',
                     sentiment='2026-09-04', kline='2026-09-04') == '2026-09-02'

    def test_regime_confirms_today_beats_stale_kline(self):
        """回归核心：regime/sentiment 已落今天（301 22:00 独立落库）而 kline 仍滞后
        在昨天 → 必须用今天，不得用滞后的 kline 日期覆盖昨天行。"""
        # 复现 09-03 23:30 场景：kline 只有 09-02，regime/sentiment 已是 09-03
        assert _pick(today='2026-09-03', regime='2026-09-03',
                     sentiment='2026-09-03', kline='2026-09-02') == '2026-09-03'

    def test_sentiment_confirms_today(self):
        """仅 sentiment 确证今天也可用今天（regime 缺失场景）。"""
        assert _pick(today='2026-09-03', regime='2026-09-02',
                     sentiment='2026-09-03', kline='2026-09-02') == '2026-09-03'

    def test_kline_today_flag_confirms_today(self):
        """daily_klines 已有今天行也算今天确证。"""
        assert _pick(today='2026-09-03', regime='2026-09-02',
                     sentiment='2026-09-02', kline='2026-09-02',
                     kline_today=True) == '2026-09-03'

    def test_nontrading_day_falls_back_to_latest_source(self):
        """周末/节假日（今天无任何源确证）→ 取各源最近交易日最大者。"""
        assert _pick(today='2026-09-06', regime='2026-09-04',
                     sentiment='2026-09-04', kline='2026-09-04') == '2026-09-04'

    def test_all_sources_empty_falls_back_today(self):
        """全源不可用 → 今天兜底。"""
        assert _pick(today='2026-09-05') == '2026-09-05'

    def test_ignores_holiday_today(self):
        """节假日工作日（今天不是交易日，各源停在节前）→ 用节前交易日，不误标假日。"""
        assert _pick(today='2026-10-01', regime='2026-09-30',
                     sentiment='2026-09-30', kline='2026-09-30') == '2026-09-30'

    def test_invalid_explicit_falls_through_to_anchors(self):
        """非法显式格式 → 静默走锚点逻辑（不抛错、不返回垃圾）。"""
        assert _pick(explicit='abc', today='2026-09-05', regime='2026-09-04',
                     sentiment='2026-09-04', kline='2026-09-04') == '2026-09-04'
