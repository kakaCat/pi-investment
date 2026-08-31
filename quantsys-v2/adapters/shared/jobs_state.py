"""后台任务（Job）共享状态与执行（框架无关）— 从 adapters/inbound/api/routes/health.py 解耦而来

Flask 与 FastAPI 两个 API 层共享同一内存 job 存储与执行逻辑。
注意：_execute_job_by_type 中 data_update 分支调用的 _execute_data_update 在
原 Flask 代码中即未定义（latent bug），此处原样保留（parity）。
"""
import json
import os
import threading
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

from adapters.shared.services import get_stock_repo, get_kline_repo, get_signal_repo, get_factor_repo

stock_repo = get_stock_repo()
kline_repo = get_kline_repo()
signal_repo = get_signal_repo()
factor_repo = get_factor_repo()

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
            all_stocks = stock_repo.get_all(limit=50)
            symbols = [s['symbol'] for s in all_stocks]
        from datetime import timedelta
        end_date = datetime.now().strftime('%Y-%m-%d')
        start_date = (datetime.now() - timedelta(days=120)).strftime('%Y-%m-%d')
        from domain.backtest.stages.factor_stage import FactorStage
        factor_stage = FactorStage(name="factors")
        computed = 0
        for sym in symbols:
            klines_df = kline_repo.get_daily_klines(sym, start_date, end_date)
            if klines_df is not None and not klines_df.is_empty() and len(klines_df) >= 20:
                try:
                    klines = klines_df.to_dicts()
                    result = factor_stage.process({'symbol': sym, 'klines': klines})
                    factors = result.get('factors', {})
                    latest_date = klines[-1]['trade_date']
                    factor_repo.save_factors(sym, str(latest_date), factors)
                    computed += len(factors)
                except Exception:
                    pass
        return {'action': 'factor_compute', 'symbols': len(symbols), 'computed': computed}
    elif job_type == 'signal_generate':
        symbols = params.get('symbols', [])
        if not symbols:
            all_stocks = stock_repo.get_all(limit=100)
            symbols = [s['symbol'] for s in all_stocks]
        count = 0
        for sym in symbols:
            s = signal_repo.get_signals_by_symbol(sym, '2024-01-01', datetime.now().strftime('%Y-%m-%d'))
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
        klines_df = kline_repo.get_daily_klines(symbol, start_date, end_date)
        import polars as pl
        klines = klines_df.to_dicts() if isinstance(klines_df, pl.DataFrame) and not klines_df.is_empty() else []
        data = {'symbol': symbol, 'klines': klines}
        return {
            'action': 'backtest_run', 'strategy': strategy, 'symbol': symbol,
            'klines': len(data.get('klines', [])),
            'factors': list(data.get('factor_history', {}).keys()),
        }
    elif job_type == 'daily_report':
        return {
            'action': 'daily_report',
            'total_stocks': 0,
            'top_signals': 0,
        }
    elif job_type == 'risk_check':
        return {
            'action': 'risk_check',
            'holdings_count': 0,
        }
    raise ValueError(f'Unknown job type: {job_type}')
