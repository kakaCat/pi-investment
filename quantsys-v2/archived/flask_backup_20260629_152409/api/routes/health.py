"""
health routes.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta
from pathlib import Path
import re
import uuid
from typing import Any, Dict, Optional

from flask import Blueprint, jsonify, request

import os

import threading

from adapters.inbound.api.shared import (
    ds,
    api_response,
    handle_api_error,
    sanitize_for_json,
    convert_keys_to_snake,
    convert_keys_to_camel,
    _safe_float,
    _V2_ROOT,
    _PROJECT_ROOT_PATH,
    _LEGACY_QUANT_ROOT,
    _load_pipeline_runs,
    _save_pipeline_runs,
    _get_pipeline_run,
    _update_pipeline_run,
    acquire_task,
    release_task,
    get_running_tasks_snapshot,
    strategy_service,
    stock_pool_service,
    factor_adapter,
    scoring_service,
    _read_watchlist,
    _write_watchlist,
    _read_groups,
    _write_groups,
    _parse_sina_a_quote,
    _parse_sina_hk_quote,
    to_camel_case,
    to_snake_case,
    get_query_params_snake_case,
    enrich_stock_data,
    signal_to_opportunity,
)

health_bp = Blueprint('health', __name__)

@health_bp.route('/api/health', methods=['GET'])
def health_check():
    """健康检查"""
    try:
        from adapters.outbound.repositories import StockORMRepository
        repo = StockORMRepository()
        stocks = repo.get_all(limit=1)
        return jsonify({
            'status': 'ok',
            'db_connected': True,
            'db_info': {
                'provider': 'postgres',
                'stock_count': len(stocks),
                'version': 'v2'
            }
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'db_connected': False,
            'error': str(e)
        }), 500


@health_bp.route('/api/platform/status', methods=['GET'])
def platform_status():
    """Platform status with database, signals, model, and report checks."""
    try:
        holdings = ds.portfolio.get_all_holdings()
        balance = ds.risk.get_latest_balance()
        signals = ds.signal.get_latest_signals(limit=10)

        model_loaded = False
        model_paths = [
            Path(os.getcwd()) / 'ml' / 'models' / 'xgboost_latest.pkl',
            Path(os.getcwd()) / 'quant' / 'quantsys' / 'ml' / 'models' / 'xgboost_latest.pkl',
        ]
        for mp in model_paths:
            if mp.exists():
                model_loaded = True
                break

        report_dir = Path(os.getcwd()) / '.pi-invest' / 'reports'
        recent_report = False
        if report_dir.exists():
            cutoff = datetime.now().timestamp() - 86400
            for f in report_dir.iterdir():
                if f.is_file() and f.stat().st_mtime > cutoff:
                    recent_report = True
                    break

        db_connected = balance is not None

        return jsonify({
            'success': True,
            'data': {
                'status': 'running' if db_connected else 'degraded',
                'holdings_count': len(holdings),
                'balance': sanitize_for_json(balance),
                'recent_signals': len(signals),
                'db_connected': db_connected,
                'model_loaded': model_loaded,
                'recent_report': recent_report,
            }
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@health_bp.route('/api/platform/backups', methods=['POST'])
def create_platform_backup():
    """Create a backup of .pi-invest state."""
    import shutil as _shutil

    pi_dir = Path(os.getcwd()) / '.pi-invest'
    backup_dir = pi_dir / 'backups' / datetime.now().strftime('%Y%m%d_%H%M%S')

    try:
        backup_dir.mkdir(parents=True, exist_ok=True)

        for sub in ['jobs', 'pipeline', 'audit']:
            src = pi_dir / sub
            if src.exists():
                _shutil.copytree(src, backup_dir / sub, dirs_exist_ok=True)

        signal_dir = pi_dir / 'signals'
        if signal_dir.exists():
            _shutil.copytree(signal_dir, backup_dir / 'signals', dirs_exist_ok=True)

        report_dir = pi_dir / 'reports'
        if report_dir.exists():
            _shutil.copytree(report_dir, backup_dir / 'reports', dirs_exist_ok=True)

        backed_up = [p.name for p in backup_dir.iterdir() if p.is_dir()]

        return jsonify({
            'success': True,
            'data': {
                'backup_dir': str(backup_dir),
                'backed_up': backed_up,
                'created_at': datetime.now().isoformat(),
            }
        }), 201
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@health_bp.route('/api/platform/restore-plan', methods=['POST'])
def preview_platform_restore():
    """Preview what would be restored from a backup."""
    data = request.get_json(silent=True)
    if not data:
        return jsonify({'success': False, 'error': 'Request body is required'}), 400

    backup_dir_str = data.get('backupDir', '')
    if not backup_dir_str:
        return jsonify({'success': False, 'error': 'backupDir is required'}), 400

    backup_path = Path(backup_dir_str)
    if not backup_path.exists():
        return jsonify({'success': False, 'error': f'Backup directory not found: {backup_dir_str}'}), 404

    items = []
    for p in backup_path.iterdir():
        if p.is_dir():
            count = sum(1 for _ in p.rglob('*') if _.is_file())
            items.append({'name': p.name, 'type': 'directory', 'files': count})
        else:
            items.append({'name': p.name, 'type': 'file'})

    return jsonify({
        'success': True,
        'data': {
            'backup_dir': backup_dir_str,
            'items': items,
            'confirmation_required': True,
            'confirmation_token': backup_path.name,
        }
    })


@health_bp.route('/api/platform/restore', methods=['POST'])
def execute_platform_restore():
    """Execute restore from a backup."""
    import shutil as _shutil

    data = request.get_json(silent=True)
    if not data:
        return jsonify({'success': False, 'error': 'Request body is required'}), 400

    backup_dir_str = data.get('backupDir', '')
    confirmation = data.get('confirmation', '')

    if not backup_dir_str:
        return jsonify({'success': False, 'error': 'backupDir is required'}), 400

    backup_path = Path(backup_dir_str)
    if not backup_path.exists():
        return jsonify({'success': False, 'error': f'Backup directory not found: {backup_dir_str}'}), 404

    if confirmation != backup_path.name:
        return jsonify({'success': False, 'error': 'Invalid confirmation token'}), 400

    pi_dir = Path(os.getcwd()) / '.pi-invest'
    restored = []

    try:
        for sub in backup_path.iterdir():
            if sub.is_dir():
                dest = pi_dir / sub.name
                if dest.exists():
                    _shutil.rmtree(dest)
                _shutil.copytree(str(sub), str(dest), dirs_exist_ok=True)
                restored.append(sub.name)

        return jsonify({
            'success': True,
            'data': {
                'restored': restored,
                'backup_dir': backup_dir_str,
                'restored_at': datetime.now().isoformat(),
            }
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@health_bp.route('/api/report/daily', methods=['GET'])
def get_daily_report():
    """获取每日报告"""
    try:
        date = request.args.get('date')
        risk_summary = ds.get_risk_summary()
        signals = ds.signal.get_latest_signals(limit=10)

        return jsonify(sanitize_for_json({
            'date': date or risk_summary.get('updated_at'),
            'risk_summary': risk_summary,
            'signals': signals,
            'signal_count': len(signals)
        }))
    except Exception as e:
        return jsonify({'error': str(e)}), 500


_JOB_TYPES = {'data_update', 'factor_compute', 'signal_generate', 'model_train', 'backtest_run', 'daily_report', 'risk_check'}
_jobs_lock = threading.Lock()
_jobs: Dict[str, Dict[str, Any]] = {}

_JOB_AUDIT_DIR = Path(os.getcwd()) / '.pi-invest' / 'audit'
_JOB_AUDIT_FILE = _JOB_AUDIT_DIR / 'jobs.jsonl'


def _audit_job(action: str, job: Dict[str, Any], actor: Optional[str] = None):
    """Record a job audit event."""
    try:
        _JOB_AUDIT_DIR.mkdir(parents=True, exist_ok=True)
        entry = {
            'action': action,
            'job_id': job.get('id', job.get('job_id', '')),
            'job_type': job.get('type', ''),
            'status': job.get('status', ''),
            'actor': actor,
            'timestamp': datetime.now().isoformat(),
        }
        with open(_JOB_AUDIT_FILE, 'a', encoding='utf-8') as f:
            f.write(json.dumps(entry, ensure_ascii=False) + '\n')
    except Exception:
        pass


def _execute_job_by_type(job_type: str, params: Dict[str, Any]) -> Dict[str, Any]:
    """Execute a job by type, returning result dict."""
    if job_type == 'data_update':
        source = params.get('source', 'watchlist')
        days = params.get('days', 730)
        force = params.get('force', False)
        return _execute_data_update(source, days, force)
    elif job_type == 'factor_compute':
        symbols = params.get('symbols', [])
        if not symbols:
            all_stocks = ds.stock.get_all(limit=50)
            symbols = [s['symbol'] for s in all_stocks]
        from datetime import timedelta
        end_date = datetime.now().strftime('%Y-%m-%d')
        start_date = (datetime.now() - timedelta(days=120)).strftime('%Y-%m-%d')
        from domain.quantlib.stages.factor_stage import FactorStage
        factor_stage = FactorStage(name="factors")
        computed = 0
        for sym in symbols:
            klines_df = ds.kline.get_daily_klines(sym, start_date, end_date)
            if klines_df is not None and not klines_df.is_empty() and len(klines_df) >= 20:
                try:
                    klines = klines_df.to_dicts()
                    result = factor_stage.process({'symbol': sym, 'klines': klines})
                    factors = result.get('factors', {})
                    latest_date = klines[-1]['trade_date']
                    ds.factor.save_factors(sym, str(latest_date), factors)
                    computed += len(factors)
                except Exception:
                    pass
        return {'action': 'factor_compute', 'symbols': len(symbols), 'computed': computed}
    elif job_type == 'signal_generate':
        symbols = params.get('symbols', [])
        if not symbols:
            all_stocks = ds.stock.get_all(limit=100)
            symbols = [s['symbol'] for s in all_stocks]
        count = 0
        for sym in symbols:
            s = ds.signal.get_signals_by_symbol(sym, '2024-01-01', datetime.now().strftime('%Y-%m-%d'))
            count += len(s)
        return {'action': 'signal_generate', 'symbols': len(symbols), 'signals_found': count}
    elif job_type == 'model_train':
        from application.services.ml_pipeline.trainer import MLTrainer
        model_type = params.get('model_type', 'xgboost')
        symbols = params.get('symbols', [])
        days = params.get('days', 730)
        trainer = MLTrainer(model_type=model_type)
        result = trainer.train(symbols=symbols, days=days) if symbols else trainer.train_all(days=days)
        return {'action': 'model_train', 'model_type': model_type, 'result': str(result)[:200]}
    elif job_type == 'backtest_run':
        strategy = params.get('strategy_name', 'default')
        symbol = params.get('symbol', '000001.SZ')
        from datetime import timedelta
        end_date = params.get('end_date', datetime.now().strftime('%Y-%m-%d'))
        start_date = params.get('start_date', (datetime.now() - timedelta(days=90)).strftime('%Y-%m-%d'))
        data = ds.get_backtest_workflow_data(symbol, start_date, end_date)
        return {
            'action': 'backtest_run', 'strategy': strategy, 'symbol': symbol,
            'klines': len(data.get('klines', [])),
            'factors': list(data.get('factor_history', {}).keys()),
        }
    elif job_type == 'daily_report':
        overview = ds.get_market_overview() if hasattr(ds, 'get_market_overview') else {}
        top_signals = ds.get_top_signals(limit=10) if hasattr(ds, 'get_top_signals') else []
        return {
            'action': 'daily_report',
            'total_stocks': overview.get('total_stocks', 0),
            'top_signals': len(top_signals),
        }
    elif job_type == 'risk_check':
        portfolio = ds.get_portfolio_risk_analysis() if hasattr(ds, 'get_portfolio_risk_analysis') else {}
        return {
            'action': 'risk_check',
            'holdings_count': portfolio.get('holdings_count', 0),
        }
    raise ValueError(f'Unknown job type: {job_type}')


_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
_PI_INVEST_DIR = os.path.join(_PROJECT_ROOT, '.pi-invest')

_WATCHLIST_FILE = os.path.join(_PI_INVEST_DIR, 'watchlist.json')
_GROUPS_FILE = os.path.join(_PI_INVEST_DIR, 'watchlist_groups.json')


def _read_watchlist():
    """读取自选股列表"""
    if not os.path.exists(_WATCHLIST_FILE):
        return {'items': []}
    with open(_WATCHLIST_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)


def _write_watchlist(data):
    """写入自选股列表"""
    os.makedirs(os.path.dirname(_WATCHLIST_FILE), exist_ok=True)
    with open(_WATCHLIST_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _read_groups():
    """读取自选股分组列表"""
    if not os.path.exists(_GROUPS_FILE):
        default_groups = {
            'groups': [{
                'id': 'default',
                'name': '默认分组',
                'created_at': datetime.now().isoformat()
            }]
        }
        return default_groups
    with open(_GROUPS_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)


def _write_groups(data):
    """写入自选股分组列表"""
    os.makedirs(os.path.dirname(_GROUPS_FILE), exist_ok=True)
    with open(_GROUPS_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


_STOP_LOSS_FILE = os.path.join(_PI_INVEST_DIR, 'stop_loss_rules.json')


def _read_stop_loss():
    """读取止损规则"""
    if not os.path.exists(_STOP_LOSS_FILE):
        return {'rules': []}
    with open(_STOP_LOSS_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)


def _write_stop_loss(data):
    """写入止损规则"""
    os.makedirs(os.path.dirname(_STOP_LOSS_FILE), exist_ok=True)
    with open(_STOP_LOSS_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _normalize_stock_code(value):
    """Return a 6-digit A-share code from a raw value, or None if invalid."""
    text = str(value).strip()
    if text.endswith('.0'):
        text = text[:-2]
    text = text.upper()
    for suffix in ('.SH', '.SZ', '.BJ'):
        if text.endswith(suffix):
            text = text[:-len(suffix)]
            break
    for prefix in ('SH', 'SZ', 'BJ'):
        if text.startswith(prefix) and len(text) > 6:
            text = text[len(prefix):]
            break
    return text if re.fullmatch(r'\d{6}', text) else None


def _looks_like_component_code_column(name, values):
    """Heuristic fallback for akshare variants with renamed component code columns."""
    column_name = str(name).strip().lower()
    if '指数' in column_name or 'index' in column_name:
        return False
    if not any(token in column_name for token in ('成分', '证券', '股票', '代码', 'code', 'symbol')):
        return False

    codes = [_normalize_stock_code(value) for value in values]
    codes = [code for code in codes if code]
    return bool(codes) and len(set(codes)) > 1


# ==================== 数据库连接池监控端点 ====================

@health_bp.route('/api/health/db', methods=['GET'])
def health_db_pool():
    """数据库连接池健康检查。

    Returns:
        200: 健康(utilization < 80%)
        200: 降级(80% <= utilization < 100%)
        503: 不健康(pool 未初始化或连接数已满)

    Response:
        {
            "status": "healthy" | "degraded" | "unhealthy",
            "utilization": "45.2%",
            "pool_status": {
                "initialized": true,
                "pool_size": 10,
                "checked_in": 8,
                "checked_out": 2,
                "overflow": 0,
                "total": 10
            },
            "reason": "..." (仅在 unhealthy/degraded 时)
        }
    """
    import logging
    logger = logging.getLogger(__name__)

    try:
        from infrastructure.persistence.database.engine import get_pool_status
        status = get_pool_status()

        if not status.get('initialized', False):
            return jsonify({
                'status': 'unhealthy',
                'reason': 'Connection pool not initialized'
            }), 503

        # 计算利用率
        total = status.get('total', 0)
        checked_out = status.get('checked_out', 0)
        utilization = (checked_out / total * 100) if total > 0 else 0

        response = {
            'status': 'healthy',
            'utilization': f'{utilization:.1f}%',
            'pool_status': status
        }

        # 告警阈值:80%
        if utilization >= 100:
            response['status'] = 'unhealthy'
            response['reason'] = f'Pool exhausted: {checked_out}/{total} connections in use'
            logger.error(f"DB pool unhealthy: {response}")
            return jsonify(response), 503
        elif utilization >= 80:
            response['status'] = 'degraded'
            response['reason'] = f'High utilization: {checked_out}/{total} connections in use'
            logger.warning(f"DB pool degraded: {response}")
            return jsonify(response), 200

        return jsonify(response), 200

    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return jsonify({
            'status': 'unhealthy',
            'reason': f'Health check error: {str(e)}'
        }), 503


@health_bp.route('/api/health/db/metrics', methods=['GET'])
def db_metrics():
    """Prometheus 格式的连接池指标。

    Returns:
        Plain text metrics in Prometheus format.

    Example:
        # HELP db_pool_size Current pool size
        # TYPE db_pool_size gauge
        db_pool_size 10

        # HELP db_pool_checked_out Connections currently checked out
        # TYPE db_pool_checked_out gauge
        db_pool_checked_out 2
    """
    import logging
    logger = logging.getLogger(__name__)

    try:
        from infrastructure.persistence.database.engine import get_pool_status
        status = get_pool_status()

        if not status.get('initialized', False):
            return "# Pool not initialized\n", 503

        total = status.get('total', 0)
        checked_out = status.get('checked_out', 0)
        utilization = (checked_out / total * 100) if total > 0 else 0

        metrics = []

        # Pool size
        metrics.append("# HELP db_pool_size Current pool size")
        metrics.append("# TYPE db_pool_size gauge")
        metrics.append(f"db_pool_size {status.get('pool_size', 0)}")

        # Checked out
        metrics.append("# HELP db_pool_checked_out Connections currently checked out")
        metrics.append("# TYPE db_pool_checked_out gauge")
        metrics.append(f"db_pool_checked_out {checked_out}")

        # Checked in
        metrics.append("# HELP db_pool_checked_in Connections currently checked in")
        metrics.append("# TYPE db_pool_checked_in gauge")
        metrics.append(f"db_pool_checked_in {status.get('checked_in', 0)}")

        # Overflow
        metrics.append("# HELP db_pool_overflow Overflow connections")
        metrics.append("# TYPE db_pool_overflow gauge")
        metrics.append(f"db_pool_overflow {status.get('overflow', 0)}")

        # Total
        metrics.append("# HELP db_pool_total Total pool capacity")
        metrics.append("# TYPE db_pool_total gauge")
        metrics.append(f"db_pool_total {total}")

        # Utilization
        metrics.append("# HELP db_pool_utilization Pool utilization percentage")
        metrics.append("# TYPE db_pool_utilization gauge")
        metrics.append(f"db_pool_utilization {utilization:.2f}")

        return "\n".join(metrics) + "\n", 200, {'Content-Type': 'text/plain; charset=utf-8'}

    except Exception as e:
        logger.error(f"Metrics collection failed: {e}")
        return f"# Error: {str(e)}\n", 503, {'Content-Type': 'text/plain; charset=utf-8'}


