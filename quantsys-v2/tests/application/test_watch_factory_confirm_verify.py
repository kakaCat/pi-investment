"""确认核验流水线生产装配（2026-10-20，机会闭环 M2 · watch-factory-wiring）

验收口径：
  0) 生产装配下 pipeline 非 None，且 news / liquidity / sector 三服务就位；
  1) 装配切换不破坏既有行为：开关关闭 → pipeline=None，引擎照常构造；
  2) 装配失败（服务缺失/构造异常）→ 降级为 None + 可诊断日志，不阻断引擎启动。

设计纪律：只替身「失败注入」与「引擎类」，其余走 factory 的真实装配函数
（仓储/服务构造均为惰性，不连库、不外呼）。
"""
from datetime import datetime
from types import SimpleNamespace

import pytest

from qs_watch.application.services.watch_engine import factory as factory_mod
from qs_watch.application.services.watch_engine.liquidity_check_service import (
    LiquidityCheckService,
)
from qs_watch.application.services.watch_engine.sector_resonance_service import (
    SectorResonanceService,
)

_ENV_KEYS = (
    'WATCH_CONFIRM_VERIFY_ENABLED',
    'WATCH_CONFIRM_VERIFY_MIN_AMOUNT',
    'WATCH_CONFIRM_VERIFY_MIN_VOLUME_RATIO',
    'WATCH_CONFIRM_VERIFY_TRAP_BIG_ORDER_RATIO',
    'WATCH_SECTOR_RESONANCE_POOL_ID',
)


def _clear_env(monkeypatch):
    for key in _ENV_KEYS:
        monkeypatch.delenv(key, raising=False)


class _EngineStub:
    """引擎替身：只记录 factory 传进来的 kwargs（不跑真引擎）。"""

    def __init__(self, **kwargs):
        self.kwargs = kwargs


class _LoggerCapture:
    """structlog 替身：直接收消息与 kwargs（structlog 默认不走 stdlib caplog）。"""

    def __init__(self):
        self.calls = []

    def _record(self, level):
        def _fn(message, **kwargs):
            self.calls.append((level, str(message), kwargs))
        return _fn

    def __getattr__(self, name):
        if name in ('info', 'warning', 'error', 'debug'):
            return self._record(name)
        raise AttributeError(name)

    def of(self, level):
        return [c for c in self.calls if c[0] == level]


# ── 0. 生产装配：三服务就位 + pipeline 注入引擎 ─────────────────────────

def test_production_assembly_yields_pipeline_with_three_services(monkeypatch):
    _clear_env(monkeypatch)

    pipeline = factory_mod.build_confirm_verify_pipeline()

    assert pipeline is not None
    # 利空核验：消息监控服务（单标的只读查询口）
    assert pipeline.news_service is not None
    assert callable(getattr(pipeline.news_service, 'query_negative_news', None))
    # 流动性核验：服务实例 + 生产阈值（显式默认，不是「未配置 → 永久 skipped」）
    assert isinstance(pipeline.liquidity_service, LiquidityCheckService)
    thresholds = pipeline.liquidity_service.thresholds
    assert thresholds.min_amount == factory_mod.DEFAULT_MIN_AMOUNT
    assert thresholds.min_volume_ratio == factory_mod.DEFAULT_MIN_VOLUME_RATIO
    assert thresholds.trap_big_order_ratio == factory_mod.DEFAULT_TRAP_BIG_ORDER_RATIO
    # 板块共振核验：服务实例 + 候选池端口（重建线程的数据来源）
    assert isinstance(pipeline.resonance_service, SectorResonanceService)
    assert callable(getattr(pipeline.resonance_service, 'refresh', None))
    assert getattr(pipeline.resonance_service, '_candidate_source', None) is not None
    # 盘口补数 provider：补成交额/量比，不伪造大单占比
    assert callable(pipeline.liquidity_quote_provider)


def test_create_watch_engine_injects_production_pipeline(monkeypatch):
    _clear_env(monkeypatch)
    monkeypatch.setattr(factory_mod, 'WatchEngine', _EngineStub)
    # 闭环服务与本卡无关，隔离掉（避免 env 影响的库表装配）
    monkeypatch.setattr(factory_mod, 'build_watch_loop_services',
                        lambda: (None, None, None, None, None))

    engine = factory_mod.create_watch_engine()

    assert isinstance(engine, _EngineStub)
    pipeline = engine.kwargs['confirm_verify_pipeline']
    assert pipeline is not None
    # 消息监控与利空核验共用同一实例（不建两份新闻源/留痕口径）
    assert engine.kwargs['news_watch_service'] is pipeline.news_service
    assert isinstance(engine.kwargs['avg_volume_provider'], object)
    assert callable(engine.kwargs['avg_volume_provider'])


def test_threshold_env_configures_liquidity_stage(monkeypatch):
    _clear_env(monkeypatch)
    monkeypatch.setenv('WATCH_CONFIRM_VERIFY_MIN_AMOUNT', '12000000')
    monkeypatch.setenv('WATCH_CONFIRM_VERIFY_MIN_VOLUME_RATIO', '1.5')
    monkeypatch.setenv('WATCH_CONFIRM_VERIFY_TRAP_BIG_ORDER_RATIO', '0.55')

    pipeline = factory_mod.build_confirm_verify_pipeline()

    thresholds = pipeline.liquidity_service.thresholds
    assert thresholds.min_amount == 12_000_000.0
    assert thresholds.min_volume_ratio == 1.5
    assert thresholds.trap_big_order_ratio == 0.55


def test_invalid_threshold_env_falls_back_with_warning(monkeypatch):
    _clear_env(monkeypatch)
    capture = _LoggerCapture()
    monkeypatch.setattr(factory_mod, 'logger', capture)
    monkeypatch.setenv('WATCH_CONFIRM_VERIFY_MIN_AMOUNT', 'not-a-number')

    pipeline = factory_mod.build_confirm_verify_pipeline()

    assert pipeline is not None
    assert pipeline.liquidity_service.thresholds.min_amount == \
        factory_mod.DEFAULT_MIN_AMOUNT
    assert any('MIN_AMOUNT' in c[2].get('key', '') for c in capture.of('warning'))


def test_liquidity_quote_provider_enriches_amount_and_volume_ratio(monkeypatch):
    """引擎 quote 只有价格/量/额 → 补成交额与量比；大单占比无源则不填。"""
    _clear_env(monkeypatch)
    avg_calls = []

    def _avg(symbol):
        avg_calls.append(symbol)
        return 1_000_000.0

    provider = factory_mod.make_liquidity_quote_provider(
        _avg, now_fn=lambda: datetime(2026, 10, 20, 15, 0))
    quote = SimpleNamespace(symbol='600519.SH', price=101.0,
                            amount=2e8, volume=1_500_000)

    payload = provider('600519.SH', quote)
    again = provider('600519.SH', quote)

    assert payload['amount'] == 2e8
    assert payload['volume_ratio'] == pytest.approx(1.5)   # 1.5M / 1M（收盘=1.0）
    assert 'big_order_ratio' not in payload                # 无源不臆造
    assert again == payload
    assert avg_calls == ['600519']                         # 同标的同日只取一次均量


def test_liquidity_quote_provider_survives_fetch_failure(monkeypatch):
    """取数失败 → 只缺量比字段（服务 fail-open skipped），不抛、不阻断确认核验。"""
    _clear_env(monkeypatch)
    capture = _LoggerCapture()
    monkeypatch.setattr(factory_mod, 'logger', capture)

    def _boom(symbol):
        raise RuntimeError('kline source down')

    provider = factory_mod.make_liquidity_quote_provider(
        _boom, now_fn=lambda: datetime(2026, 10, 20, 15, 0))
    payload = provider('600519.SH', SimpleNamespace(
        amount=2e8, volume=1_000_000))

    assert payload['amount'] == 2e8
    assert 'volume_ratio' not in payload
    assert 'big_order_ratio' not in payload
    assert any('均量取数失败' in c[1] for c in capture.of('warning'))


# ── 1. 装配切换：开关关闭 = 未装配路径，行为不变 ────────────────────────

def test_switch_off_returns_none_and_keeps_engine_constructible(monkeypatch):
    _clear_env(monkeypatch)
    monkeypatch.setenv('WATCH_CONFIRM_VERIFY_ENABLED', 'false')
    monkeypatch.setattr(factory_mod, 'WatchEngine', _EngineStub)
    monkeypatch.setattr(factory_mod, 'build_watch_loop_services',
                        lambda: (None, None, None, None, None))

    assert factory_mod.build_confirm_verify_pipeline() is None

    engine = factory_mod.create_watch_engine()
    assert isinstance(engine, _EngineStub)
    assert engine.kwargs['confirm_verify_pipeline'] is None
    # 消息监控本身仍装配（与核验开关解耦，sidecar 扫描不退回旧行为）
    assert engine.kwargs['news_watch_service'] is not None


# ── 2. 装配失败：降级 None + 可诊断日志，不阻断引擎启动 ─────────────────

def test_assembly_failure_degrades_to_none_with_stage_and_error(monkeypatch):
    _clear_env(monkeypatch)
    capture = _LoggerCapture()
    monkeypatch.setattr(factory_mod, 'logger', capture)

    def _boom():
        raise RuntimeError('liquidity source unavailable')

    monkeypatch.setattr(factory_mod, '_build_liquidity_check_service', _boom)

    pipeline = factory_mod.build_confirm_verify_pipeline(news_service=object())

    assert pipeline is None
    errors = capture.of('error')
    assert errors, '装配失败必须留下 error 日志'
    message, kwargs = errors[-1][1], errors[-1][2]
    assert 'liquidity' in message                 # 哪一段失败
    assert kwargs.get('stage') == 'liquidity'
    assert 'liquidity source unavailable' in kwargs.get('error', '')


def test_engine_startup_survives_news_service_assembly_failure(monkeypatch):
    _clear_env(monkeypatch)
    capture = _LoggerCapture()
    monkeypatch.setattr(factory_mod, 'logger', capture)

    def _boom():
        raise RuntimeError('news repo down')

    monkeypatch.setattr(factory_mod, '_build_news_watch_service', _boom)
    monkeypatch.setattr(factory_mod, 'WatchEngine', _EngineStub)
    monkeypatch.setattr(factory_mod, 'build_watch_loop_services',
                        lambda: (None, None, None, None, None))

    engine = factory_mod.create_watch_engine()

    # 引擎照常构造；消息服务与核验流水线各自降级为 None
    assert isinstance(engine, _EngineStub)
    assert engine.kwargs['news_watch_service'] is None
    assert engine.kwargs['confirm_verify_pipeline'] is None
    errors = ' '.join(c[1] + ' ' + str(c[2]) for c in capture.of('error'))
    assert '消息监控服务装配失败' in errors
    assert '确认核验流水线装配失败' in errors
    assert 'news repo down' in errors
