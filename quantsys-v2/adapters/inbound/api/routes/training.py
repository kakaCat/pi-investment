"""
training routes.
"""
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path
import re
import uuid

from flask import Blueprint, jsonify, request

import os

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

training_bp = Blueprint('training', __name__)

_TRAINING_REPORTS_DIR = Path(os.getcwd()) / 'ml' / 'models'


@training_bp.route('/api/training/start', methods=['POST'])
@handle_api_error
def training_start():
    """启动模型训练（兼容 Express 前端）"""
    try:
        from application.services.ml_pipeline.trainer import MLTrainer
        from application.services.ml_pipeline.feature_engineering import FeatureEngineer
        from datetime import datetime, timedelta
        import pandas as pd
    except ImportError as e:
        return jsonify({'success': False, 'error': f'ML module not available: {e}'}), 503

    data = request.get_json(silent=True) or {}

    model_type = data.get('model', data.get('model_type', 'xgboost'))
    days = data.get('days', 90)
    cv_splits = data.get('cvSplits', data.get('cv_splits', 5))
    start_date = data.get('start_date') or (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
    end_date = data.get('end_date') or datetime.now().strftime('%Y-%m-%d')
    test_size = 1.0 / max(cv_splits, 1)

    all_stocks = ds.stock.get_all(limit=1000)
    stock_list = [s['symbol'] for s in all_stocks[:100]]

    klines_dict = {}
    for symbol in stock_list:
        klines_df = ds.kline.get_daily_klines(symbol, start_date, end_date)
        if klines_df is not None and not klines_df.is_empty() and len(klines_df) >= 120:
            klines_dict[symbol] = klines_df.to_dicts()

    if len(klines_dict) == 0:
        return jsonify({'success': False, 'error': 'No sufficient training data available'}), 400

    engineer = FeatureEngineer(scaler_type='standard')
    features_df = engineer.extract_features(klines_dict)

    if 'roc_5' in features_df.columns:
        target = (features_df['roc_5'].fillna(0) > 0).astype(int)
    else:
        target = (features_df.select_dtypes(include=['float64', 'int64']).iloc[:, 0].fillna(0) > 0).astype(int)

    metadata, scaled_features = engineer.prepare_features(
        features_df, handle_missing='drop', fit_scaler=True
    )
    target = target[scaled_features.index]

    if len(scaled_features) < 50:
        return jsonify({'success': False, 'error': 'Insufficient training samples after preprocessing'}), 400

    trainer = MLTrainer(model_type=model_type)
    training_results = trainer.train(scaled_features, target, test_size=test_size, params=data.get('params'))
    model_path = trainer.save_model(version='latest')

    report = {
        'timestamp': datetime.now().isoformat(),
        'start_time': datetime.now().isoformat(),
        'end_time': datetime.now().isoformat(),
        'duration_seconds': 0,
        'model_type': model_type,
        'n_features': int(scaled_features.shape[1]) if hasattr(scaled_features, 'shape') else 0,
        'total_samples': int(len(scaled_features)),
        'metrics': training_results.get('test_metrics', {}),
        'cv_results': training_results.get('cv_results', {}),
        'params': data,
    }
    _TRAINING_REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    report_filename = f"training_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    report_path = _TRAINING_REPORTS_DIR / report_filename
    report_path.write_text(json.dumps(sanitize_for_json(report), ensure_ascii=False, indent=2), encoding='utf-8')

    latest_path = _TRAINING_REPORTS_DIR / 'training_report_latest.json'
    latest_path.write_text(json.dumps(sanitize_for_json(report), ensure_ascii=False, indent=2), encoding='utf-8')

    return api_response({
        'model_path': str(model_path),
        'training_results': sanitize_for_json(training_results),
        'samples_trained': len(scaled_features),
        'symbols_count': len(klines_dict),
        'report_filename': report_filename,
    }, message='Training completed')


@training_bp.route('/api/training/reports', methods=['GET'])
@handle_api_error
def training_reports():
    """列出训练报告"""
    if not _TRAINING_REPORTS_DIR.exists():
        return api_response({'reports': []})

    files = sorted(
        [f for f in _TRAINING_REPORTS_DIR.iterdir()
         if f.name.startswith('training_report_') and f.name.endswith('.json')
         and f.name != 'training_report_latest.json'],
        reverse=True
    )
    reports = []
    for fp in files[:20]:
        try:
            content = json.loads(fp.read_text(encoding='utf-8'))
            reports.append({
                'filename': fp.name,
                'timestamp': content.get('timestamp', ''),
                'metrics': content.get('metrics', {}),
                'params': content.get('params', {}),
                'n_features': content.get('n_features', 0),
                'total_samples': content.get('total_samples', 0),
                'model_type': content.get('model_type', ''),
            })
        except (json.JSONDecodeError, OSError):
            pass

    return api_response({'reports': reports, 'count': len(reports)})


@training_bp.route('/api/training/report/<filename>', methods=['GET'])
@handle_api_error
def training_report_detail(filename):
    """获取指定训练报告"""
    if '..' in filename or '/' in filename or '\\' in filename:
        return jsonify({'success': False, 'error': 'Invalid filename'}), 400

    report_path = _TRAINING_REPORTS_DIR / filename
    if not report_path.exists():
        return jsonify({'success': False, 'error': 'Report not found'}), 404

    try:
        content = json.loads(report_path.read_text(encoding='utf-8'))
        return api_response(content)
    except json.JSONDecodeError:
        return jsonify({'success': False, 'error': 'Invalid report file'}), 500


@training_bp.route('/api/training/history', methods=['GET'])
@handle_api_error
def training_history():
    """训练历史摘要"""
    if not _TRAINING_REPORTS_DIR.exists():
        return api_response({'history': [], 'count': 0})

    files = sorted(
        [f for f in _TRAINING_REPORTS_DIR.iterdir()
         if f.name.startswith('training_report_') and f.name.endswith('.json')
         and f.name != 'training_report_latest.json'],
        reverse=True
    )
    history = []
    for fp in files[:50]:
        try:
            content = json.loads(fp.read_text(encoding='utf-8'))
            cv_results = content.get('cv_results', {}) or {}
            metrics = content.get('metrics', {}) or {}
            history.append({
                'timestamp': content.get('timestamp', ''),
                'start_time': content.get('start_time', ''),
                'end_time': content.get('end_time', ''),
                'duration_seconds': content.get('duration_seconds', 0),
                'model_type': content.get('model_type', ''),
                'n_features': content.get('n_features', 0),
                'total_samples': content.get('total_samples', 0),
                'cv_accuracy': cv_results.get('mean_scores', {}).get('accuracy', 0),
                'cv_auc': cv_results.get('mean_scores', {}).get('auc', 0),
                'test_accuracy': metrics.get('accuracy', 0),
                'test_auc': metrics.get('auc', 0),
            })
        except (json.JSONDecodeError, OSError):
            pass

    return api_response({'history': history, 'count': len(history)})

