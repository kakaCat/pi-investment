"""启动依赖检查（E-201）。

应用启动时尽早暴露关键依赖缺失（TA-Lib / PostgreSQL / Redis），
避免"部署后才发现问题、错误信息不明确、难以排查"。

设计约定：
- check_dependencies() 返回结构化结果列表，不抛异常——启动检查不应
  中断进程（与 main.lifespan 现有逐项 try/except 容错风格一致）。
- 分级：
    critical = 缺失/不可用将直接导致核心功能不可用（TA-Lib 因子库、
              PostgreSQL 主库）→ 记 ERROR 并纳入 failed 集合
    warning  = 缺失/不可用可降级（Redis → 内存缓存，见 cache_factory
              自动 fallback）→ 记 WARNING，不计入 failed
- DB/Redis 均为延迟 import + 显式超时，避免检查本身阻塞启动或拖垮进程。
"""
import os
import time
from typing import Dict, List, Optional

import structlog

logger = structlog.get_logger(__name__)

# 各依赖检查默认超时（秒）
_DB_CHECK_TIMEOUT_S = float(os.getenv('DEP_CHECK_DB_TIMEOUT', '5'))
_REDIS_CHECK_TIMEOUT_S = float(os.getenv('DEP_CHECK_REDIS_TIMEOUT', '3'))


def _check_talib() -> Dict[str, object]:
    """TA-Lib：import 级检查（quantlib 因子计算依赖，缺失不可用）。"""
    try:
        import talib  # noqa: F401
    except ImportError as e:
        return {
            'name': 'TA-Lib',
            'ok': False,
            'level': 'critical',
            'detail': f'import talib 失败: {e}。安装: brew install ta-lib && pip install TA-Lib',
        }
    version = getattr(talib, '__version__', 'unknown')
    return {'name': 'TA-Lib', 'ok': True, 'level': 'critical', 'detail': f'v{version}'}


def _check_postgresql() -> Dict[str, object]:
    """PostgreSQL：连接 + SELECT 1（使用 settings 的 database_url）。"""
    try:
        from infrastructure.config.settings import get_settings
        settings = get_settings()
        database_url = settings.database.database_url
    except Exception as e:  # settings 本身不可读也算 critical
        return {
            'name': 'PostgreSQL',
            'ok': False,
            'level': 'critical',
            'detail': f'读取数据库配置失败: {e}',
        }

    try:
        import sqlalchemy
        from sqlalchemy import text
        engine = sqlalchemy.create_engine(
            database_url,
            pool_pre_ping=True,
            connect_args={'connect_timeout': int(_DB_CHECK_TIMEOUT_S)},
        )
        started = time.monotonic()
        with engine.connect() as conn:
            conn.execute(text('SELECT 1'))
        elapsed_ms = int((time.monotonic() - started) * 1000)
        engine.dispose()
        return {
            'name': 'PostgreSQL',
            'ok': True,
            'level': 'critical',
            'detail': f'SELECT 1 ok ({elapsed_ms}ms, {settings.database.pghost}:{settings.database.pgport}/{settings.database.pgdatabase})',
        }
    except Exception as e:
        return {
            'name': 'PostgreSQL',
            'ok': False,
            'level': 'critical',
            'detail': f'连接失败: {e}',
        }


def _check_redis() -> Dict[str, object]:
    """Redis：连接 + ping（可选依赖——cache_factory 失败自动降级内存缓存）。"""
    try:
        from infrastructure.config import get_redis_config
        import redis as redis_py

        cfg = get_redis_config()
        client = redis_py.Redis(
            host=cfg['host'],
            port=cfg['port'],
            db=cfg['db'],
            password=cfg.get('password'),
            socket_connect_timeout=_REDIS_CHECK_TIMEOUT_S,
            socket_timeout=_REDIS_CHECK_TIMEOUT_S,
        )
        started = time.monotonic()
        pong = client.ping()
        elapsed_ms = int((time.monotonic() - started) * 1000)
        client.close()
        if pong:
            return {
                'name': 'Redis',
                'ok': True,
                'level': 'warning',
                'detail': f'PING ok ({elapsed_ms}ms, {cfg["host"]}:{cfg["port"]}/{cfg["db"]})',
            }
        return {
            'name': 'Redis',
            'ok': False,
            'level': 'warning',
            'detail': 'PING 返回异常（将降级为内存缓存）',
        }
    except Exception as e:
        return {
            'name': 'Redis',
            'ok': False,
            'level': 'warning',
            'detail': f'连接失败: {e}（将降级为内存缓存，见 cache_factory）',
        }


_CHECKERS = (
    _check_talib,
    _check_postgresql,
    _check_redis,
)


def check_dependencies(include_redis: Optional[bool] = None) -> List[Dict[str, object]]:
    """执行全部启动依赖检查。

    Args:
        include_redis: 是否检查 Redis。None=自动（检查），False=跳过。

    Returns:
        List[Dict]: 每项含 name/ok/level/detail。
    """
    results: List[Dict[str, object]] = []
    for checker in _CHECKERS:
        if checker is _check_redis and include_redis is False:
            continue
        try:
            result = checker()
        except Exception as e:  # 检查器自身异常不应中断其余检查
            result = {
                'name': getattr(checker, '__name__', 'unknown').replace('_check_', '').capitalize(),
                'ok': False,
                'level': 'critical',
                'detail': f'检查器异常: {e}',
            }
        results.append(result)
        _log_result(result)
    return results


def _log_result(result: Dict[str, object]) -> None:
    """按级别输出日志。"""
    name = result['name']
    ok = result['ok']
    level = result['level']
    detail = result['detail']
    if ok:
        logger.info('dependency_check_ok', dependency=name, detail=detail)
    elif level == 'critical':
        logger.error('dependency_check_failed', dependency=name, detail=detail)
    else:
        logger.warning('dependency_check_degraded', dependency=name, detail=detail)


def summarize(results: List[Dict[str, object]]) -> Dict[str, object]:
    """汇总检查结果：是否全部 critical 通过、failed 清单。"""
    critical_failed = [r for r in results if not r['ok'] and r['level'] == 'critical']
    degraded = [r for r in results if not r['ok'] and r['level'] == 'warning']
    return {
        'all_critical_ok': len(critical_failed) == 0,
        'failed': [r['name'] for r in critical_failed],
        'degraded': [r['name'] for r in degraded],
        'checked': len(results),
    }
