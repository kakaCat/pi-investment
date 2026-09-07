"""training API - FastAPI 版（从 Flask training.py 迁移，响应契约保持一致）

覆盖端点：
- GET /api/training/reports  列出训练报告
- GET /api/training/history  训练历史摘要
"""
import json
import os
from pathlib import Path

from fastapi import APIRouter
import structlog

from adapters.inbound.fastapi_app.shared import (
    api_response, handle_api_error,
)

logger = structlog.get_logger(__name__)

router = APIRouter(tags=["Training - 训练报告"])

_TRAINING_REPORTS_DIR = Path(os.getcwd()) / 'ml' / 'models'


@router.get('/api/training/reports')
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


@router.get('/api/training/history')
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
