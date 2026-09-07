"""DataQualityGate 单元测试"""
import pytest
from datetime import datetime, timedelta
from application.services.scoring.data_quality_gate import DataQualityGate


def _klines(n, end_date=None, dirty=False):
    """构造 n 根日K（升序），end_date 为最后一根日期"""
    end = end_date or datetime.now().strftime('%Y-%m-%d')
    end_dt = datetime.strptime(end, '%Y-%m-%d')
    out = []
    for i in range(n):
        d = (end_dt - timedelta(days=n - 1 - i)).strftime('%Y-%m-%d')
        bar = {'trade_date': d, 'open': 10, 'high': 11, 'low': 9,
               'close': 10.5, 'volume': 1000, 'amount': 10500}
        if dirty and i == n - 1:
            bar['amount'] = 0  # 07-13 事故模式：amount=0 但 volume>0
        out.append(bar)
    return out


class FakeProvider:
    """模拟 DataProviderManager"""
    def __init__(self, new_bars):
        self._new = new_bars
        self.calls = 0
    def get_klines(self, symbol, period, start_date, end_date):
        self.calls += 1
        return {'success': True, 'data': self._new}


class TestDirtyBars:
    def test_dirty_bar_removed(self):
        """amount=0 且 volume>0 的 bar 被剔除，修复记录可见"""
        gate = DataQualityGate(data_provider=None)
        report = gate.check('A', _klines(130, dirty=True))
        assert report.ok
        assert len(report.klines) == 129
        assert any('剔除' in r for r in report.repairs)

    def test_too_few_after_cleaning_skips(self):
        """剔除脏 bar 后不足 120 根 → 跳过"""
        gate = DataQualityGate(data_provider=None)
        report = gate.check('A', _klines(120, dirty=True))
        assert not report.ok
        assert report.skip_reason == 'insufficient_klines'

    def test_historical_amount_zero_tolerated(self):
        """07-13 事故遗留：历史 bar amount=0 不容剔除（指标不依赖 amount）"""
        gate = DataQualityGate(data_provider=None)
        bars = _klines(130)
        for b in bars[:-10]:  # 除最近10根外全部 amount=0（事故遗留模式）
            b['amount'] = 0
        report = gate.check('A', bars)
        assert report.ok
        assert len(report.klines) == 130


class TestGapRepair:
    def test_recent_gap_triggers_repair(self):
        """最后一根 K 线距今 >4 天 → 触发补抓并合并"""
        old_end = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
        new_bars = _klines(3)
        provider = FakeProvider(new_bars)
        gate = DataQualityGate(data_provider=provider)
        report = gate.check('A', _klines(130, end_date=old_end))
        assert provider.calls == 1
        assert report.ok
        assert len(report.klines) == 133
        assert any('补抓' in r for r in report.repairs)
        assert gate.repair_report['succeeded'] == 1

    def test_no_provider_no_repair(self):
        """无 data_provider → 不补抓，数据旧但可用则照常评分"""
        old_end = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
        gate = DataQualityGate(data_provider=None)
        report = gate.check('A', _klines(130, end_date=old_end))
        assert report.ok  # 130 根够用，照常评分
        assert any('数据截至' in r for r in report.repairs)

    def test_repair_budget(self):
        """修复预算：超过 budget 后不再尝试"""
        old_end = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
        provider = FakeProvider(_klines(1))
        gate = DataQualityGate(data_provider=provider, repair_budget=2)
        for i in range(4):
            gate.check(f'S{i}', _klines(130, end_date=old_end))
        assert provider.calls == 2
        assert gate.repair_report['skipped_over_budget'] == 2

    def test_failed_repair_counted(self):
        """补抓失败 → failed 计数，不炸"""
        class BoomProvider:
            def get_klines(self, *a, **k):
                raise RuntimeError('network')
        old_end = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
        gate = DataQualityGate(data_provider=BoomProvider())
        report = gate.check('A', _klines(130, end_date=old_end))
        assert report.ok  # 旧数据仍可用
        assert gate.repair_report['failed'] == 1
