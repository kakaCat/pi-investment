"""晚间管线休市日因子段门单测（REQ-261005203907-2b8c · TC-4）

判据（设计与实现的唯一口径）：
    跳过因子段 ⇔ 非交易日 **且** K 线本次无更新 **且** K 线段不是 error

⚠️ 最要紧的一条是 `test_trading_day_never_skips_factor`：**交易日绝不跳因子**——
交易日若 K 线已由别的路径同步过（覆盖度新鲜），`kline_sync` 同样是 `skipped`，
但当日因子还没算；只看"K 线 skipped"就会在正常交易日漏算因子。

## 打桩纪律（桩打在被调函数所在模块）

- `pipeline.is_non_trading_day`（模块级导入）、`pipeline._kline_coverage`、
  `pipeline._probe_kline_sources`、`pipeline._last_trading_day`（避免真实日历链连库/联网）；
- `update_gem_klines` / `handle_factor_compute` 是**函数内局部 import** →
  打源头模块：`infrastructure.jobs.kline_update_job.*` / `application.services.scheduler_tasks.*`；
- `get_engine` 同为函数内局部 import → 打 `infrastructure.persistence.database.engine.get_engine`。

**零网络零 DB**：所有外部取数入口都被替换，用例只验编排。
"""
from __future__ import annotations

import pytest

from adapters.inbound.fastapi_app.daily_jobs import pipeline as pipe


def _cov(total=5277, covered=5265, coverage=0.998, stale=12, oldest='2026-09-29'):
    return {'total': total, 'covered': covered, 'coverage': coverage,
            'stale': stale, 'oldest_stale': oldest}


@pytest.fixture
def env(monkeypatch):
    """把 `_job_evening_pipeline` 的全部外部入口替换掉，返回可操控的把手。"""
    from application.services import scheduler_tasks
    from infrastructure.jobs import kline_update_job
    from infrastructure.persistence.database import engine as engine_mod

    state = {'non_trading': True, 'cov': _cov(), 'sync': None, 'factor_calls': 0}

    def _factor_compute(_params):
        state['factor_calls'] += 1
        return {'status': 'success', 'computed': 5268}

    monkeypatch.setattr(pipe, 'is_non_trading_day', lambda: state['non_trading'])
    monkeypatch.setattr(pipe, '_kline_coverage', lambda _engine, _expected: state['cov'])
    monkeypatch.setattr(pipe, '_probe_kline_sources', lambda: True)
    monkeypatch.setattr(pipe, '_last_trading_day', lambda _ref: '2026-09-30')
    monkeypatch.setattr(engine_mod, 'get_engine', lambda: object())
    monkeypatch.setattr(kline_update_job, 'update_gem_klines',
                        lambda **kw: state['sync'])
    monkeypatch.setattr(scheduler_tasks, 'handle_factor_compute', _factor_compute)
    return state


class TestHolidayFactorGate:
    """TC-4 六行真值表"""

    def test_holiday_fresh_kline_skips_factor(self, env):
        """休市日 + K 线覆盖度已新鲜（kline_sync=skipped）→ 因子段不跑（本需求要消灭的空跑）。"""
        env['non_trading'] = True
        env['cov'] = _cov()

        result = pipe._job_evening_pipeline()

        assert env['factor_calls'] == 0
        assert result['kline_sync']['status'] == 'skipped', 'K 线段行为必须原样保留'
        assert result['factor_compute']['skipped'] is True
        assert result['factor_compute']['status'] == 'skipped'
        assert '非交易日' in result['factor_compute']['reason']

    def test_holiday_repaired_kline_runs_factor(self, env):
        """休市日但 K 线段真的修了数据（success>0）→ 因子段必须照跑，否则留因子空洞。"""
        env['non_trading'] = True
        env['cov'] = _cov(coverage=0.5, covered=2600, stale=2600)  # 触发同步分支
        env['sync'] = {'status': 'success', 'success': 137, 'failed': 0, 'stale': 12}

        result = pipe._job_evening_pipeline()

        assert env['factor_calls'] == 1
        assert result['factor_compute']['computed'] == 5268

    def test_holiday_zero_success_skips_factor(self, env):
        """休市日 + 同步跑了但一只没成功 → 因子段跳过（无任何新数据可算）。"""
        env['non_trading'] = True
        env['cov'] = _cov(coverage=0.5, covered=2600, stale=2600)
        env['sync'] = {'status': 'success', 'success': 0, 'failed': 0, 'stale': 5271}

        result = pipe._job_evening_pipeline()

        assert env['factor_calls'] == 0
        assert result['factor_compute']['skipped'] is True

    def test_holiday_kline_error_still_computes_then_raises(self, env):
        """休市日 + K 线段 error：既有语义不变——先按现有数据算完因子，再上抛失败。"""
        env['non_trading'] = True
        env['cov'] = _cov(coverage=0.5, covered=2600, stale=2600)
        env['sync'] = {'status': 'error', 'error': 'boom'}

        with pytest.raises(RuntimeError) as ei:
            pipe._job_evening_pipeline()

        assert env['factor_calls'] == 1, 'error 路径必须保住"因子仍按现有数据算完"'
        assert 'boom' in str(ei.value)

    def test_trading_day_never_skips_factor(self, env):
        """**回归锁**：交易日 + K 线 skipped（已被别的路径同步过）→ 因子必须照跑。"""
        env['non_trading'] = False
        env['cov'] = _cov()

        result = pipe._job_evening_pipeline()

        assert env['factor_calls'] == 1, '交易日漏算因子是本次改造最危险的回归'
        assert result['factor_compute'].get('skipped') is not True

    def test_result_passes_failure_classifier(self, env):
        """跳过形态必须被内层失败分类器判为"非失败"（否则任务会假红）。"""
        from infrastructure.scheduler.job_executor import find_result_failure

        env['non_trading'] = True
        env['cov'] = _cov()

        result = pipe._job_evening_pipeline()

        assert find_result_failure(result) is None
