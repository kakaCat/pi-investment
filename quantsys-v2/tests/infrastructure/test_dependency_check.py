"""启动依赖检查（E-201）单测 —— 全部 mock，不依赖真实 DB/Redis/TALib。"""
import sys
from types import SimpleNamespace

import pytest

from infrastructure.diagnostics import dependency_check as dep_mod
from infrastructure.diagnostics.dependency_check import (
    _check_postgresql,
    _check_redis,
    _check_talib,
    check_dependencies,
    summarize,
)


def _fake_pg_settings():
    """返回形如 settings.database 的 fake（含 database_url 与展示字段）。"""
    return SimpleNamespace(
        database=SimpleNamespace(
            database_url='postgresql://u:p@localhost:5432/db',
            pghost='localhost',
            pgport=5432,
            pgdatabase='db',
        )
    )


def _patch_settings_getter(monkeypatch):
    """把 infrastructure.config.settings.get_settings patch 成返回 fake。"""
    import infrastructure.config.settings as settings_mod
    monkeypatch.setattr(settings_mod, 'get_settings', _fake_pg_settings)
    return settings_mod


class TestCheckTalib:
    def test_talib_ok(self, monkeypatch):
        fake_talib = SimpleNamespace(__version__='0.7.1')
        monkeypatch.setitem(sys.modules, 'talib', fake_talib)
        result = _check_talib()
        assert result['name'] == 'TA-Lib'
        assert result['ok'] is True
        assert result['level'] == 'critical'
        assert '0.7.1' in result['detail']

    def test_talib_missing(self, monkeypatch):
        # 先移除缓存，确保 import 走 __import__（可被 patch 拦截）
        monkeypatch.delitem(sys.modules, 'talib', raising=False)
        import builtins
        real_import = builtins.__import__

        def fake_import(name, *args, **kwargs):
            if name == 'talib':
                raise ImportError("No module named 'talib'")
            return real_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, '__import__', fake_import)
        result = _check_talib()
        assert result['ok'] is False
        assert result['level'] == 'critical'


class TestCheckPostgresql:
    def test_pg_ok(self, monkeypatch):
        _patch_settings_getter(monkeypatch)
        import sqlalchemy
        captured = {}

        class FakeConn:
            def __enter__(self):
                return self

            def __exit__(self, *a):
                return None

            def execute(self, *a, **k):
                return None

        class FakeEngine:
            def connect(self):
                return FakeConn()

            def dispose(self):
                return None

        def fake_create_engine(url, **kwargs):
            captured['url'] = url
            captured['connect_args'] = kwargs.get('connect_args', {})
            return FakeEngine()

        monkeypatch.setattr(sqlalchemy, 'create_engine', fake_create_engine)
        result = _check_postgresql()
        assert result['ok'] is True
        assert captured['url'].startswith('postgresql://')
        assert 'connect_timeout' in captured['connect_args']

    def test_pg_unreachable(self, monkeypatch):
        _patch_settings_getter(monkeypatch)
        import sqlalchemy

        def boom_create_engine(url, **kwargs):
            raise ConnectionError('connection refused')

        monkeypatch.setattr(sqlalchemy, 'create_engine', boom_create_engine)
        result = _check_postgresql()
        assert result['ok'] is False
        assert result['level'] == 'critical'
        assert 'connection refused' in result['detail']


class TestCheckRedis:
    def test_redis_ok(self, monkeypatch):
        import infrastructure.config as infra_cfg
        monkeypatch.setattr(
            infra_cfg, 'get_redis_config',
            lambda: {'host': 'localhost', 'port': 6379, 'db': 0, 'password': None})

        class FakeRedisClient:
            def ping(self):
                return True

            def close(self):
                return None

        fake_redis_mod = SimpleNamespace(Redis=lambda **kw: FakeRedisClient())
        monkeypatch.setitem(sys.modules, 'redis', fake_redis_mod)
        result = _check_redis()
        assert result['name'] == 'Redis'
        assert result['ok'] is True
        assert result['level'] == 'warning'

    def test_redis_down(self, monkeypatch):
        import infrastructure.config as infra_cfg
        monkeypatch.setattr(
            infra_cfg, 'get_redis_config',
            lambda: {'host': 'localhost', 'port': 6379, 'db': 0, 'password': None})

        def boom_redis(**kw):
            raise ConnectionError('Connection refused')

        fake_redis_mod = SimpleNamespace(Redis=boom_redis)
        monkeypatch.setitem(sys.modules, 'redis', fake_redis_mod)
        result = _check_redis()
        assert result['ok'] is False
        assert result['level'] == 'warning'  # 降级依赖不算 critical
        assert '降级为内存缓存' in result['detail']


class TestCheckDependencies:
    def test_checker_exception_does_not_abort(self, monkeypatch):
        """单个检查器抛异常时，其余检查照常执行，结果含失败项不抛异常。"""
        def boom():
            raise RuntimeError('checker crashed')

        monkeypatch.setattr(dep_mod, '_CHECKERS', (boom,))
        results = check_dependencies(include_redis=False)
        assert len(results) == 1
        assert results[0]['ok'] is False
        assert results[0]['level'] == 'critical'
        assert '检查器异常' in results[0]['detail']

    def test_include_redis_false_skips(self, monkeypatch):
        """include_redis=False 跳过 Redis 检查（is 判定需 patch 模块属性）。"""
        calls = {'redis': 0}

        def fake_talib():
            return {'name': 'TA-Lib', 'ok': True, 'level': 'critical', 'detail': 'v1'}

        def fake_pg():
            return {'name': 'PostgreSQL', 'ok': True, 'level': 'critical', 'detail': 'ok'}

        def fake_redis():
            calls['redis'] += 1
            return {'name': 'Redis', 'ok': True, 'level': 'warning', 'detail': 'ok'}

        # 模块函数体运行时按全局名取 _check_redis，因此 patch 模块属性即可生效
        monkeypatch.setattr(dep_mod, '_check_talib', fake_talib)
        monkeypatch.setattr(dep_mod, '_check_postgresql', fake_pg)
        monkeypatch.setattr(dep_mod, '_check_redis', fake_redis)
        monkeypatch.setattr(
            dep_mod, '_CHECKERS',
            (dep_mod._check_talib, dep_mod._check_postgresql, dep_mod._check_redis))

        results = check_dependencies(include_redis=False)
        names = [r['name'] for r in results]
        assert 'Redis' not in names
        assert calls['redis'] == 0

        # include_redis=True（默认）会带上 Redis
        results2 = check_dependencies(include_redis=True)
        assert 'Redis' in [r['name'] for r in results2]
        assert calls['redis'] == 1


class TestSummarize:
    def test_all_critical_ok(self):
        results = [
            {'name': 'TA-Lib', 'ok': True, 'level': 'critical'},
            {'name': 'PostgreSQL', 'ok': True, 'level': 'critical'},
            {'name': 'Redis', 'ok': False, 'level': 'warning'},
        ]
        s = summarize(results)
        assert s['all_critical_ok'] is True
        assert s['failed'] == []
        assert s['degraded'] == ['Redis']
        assert s['checked'] == 3

    def test_critical_failed(self):
        results = [
            {'name': 'TA-Lib', 'ok': False, 'level': 'critical'},
            {'name': 'PostgreSQL', 'ok': True, 'level': 'critical'},
        ]
        s = summarize(results)
        assert s['all_critical_ok'] is False
        assert s['failed'] == ['TA-Lib']
