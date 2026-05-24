"""
量化系统 API 服务

提供RESTful API供前端调用
"""

from flask import Flask, jsonify, request
from flask_cors import CORS
import sys
import os
import json
import uuid
import time
import subprocess
import threading
import logging
import numpy as np
import math
from pathlib import Path
from datetime import datetime, timezone, date
from psycopg2.extras import RealDictCursor

# JSON encoder to handle NaN values and date objects
def sanitize_for_json(obj):
    """递归清理对象中的 NaN 和 Infinity，使其可以被 JSON 序列化"""
    if isinstance(obj, float):
        if math.isnan(obj) or math.isinf(obj):
            return None
        return obj
    elif isinstance(obj, dict):
        return {k: sanitize_for_json(v) for k, v in obj.items()}
    elif isinstance(obj, (list, tuple)):
        return [sanitize_for_json(item) for item in obj]
    elif isinstance(obj, (datetime, date)):
        return obj.isoformat()
    elif hasattr(obj, 'isoformat'):
        return obj.isoformat()
    else:
        return obj

class NaNEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, float):
            if math.isnan(obj) or math.isinf(obj):
                return None
        if isinstance(obj, (datetime, )):
            return obj.isoformat()
        if hasattr(obj, 'isoformat'):  # date, datetime, time
            return obj.isoformat()
        return super().default(obj)

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from quantsys.factors.calculator import FactorCalculator
from quantsys.factors.factor_service import FactorService
from quantsys.data.db import Database
from quantsys.data.fetchers.klines import KlineFetcher
from quantsys.data.fetchers.minute_klines import MinuteKlineFetcher
from quantsys.data.data.data_service import DataService
from quantsys.ml.features.feature_engineering import FeatureEngineer

# ---- 补丁：analyze_feature_importance.py 已重构为 API client，
#        load_model / get_feature_names / analyze_feature_importance 在此内联定义 ----

import joblib
import pandas as pd
from typing import List
from quantsys.data.db import normalize_symbol

def load_model(path: str):
    """加载 pkl 模型（XGBoost 或 sklearn 兼容）"""
    return joblib.load(path)

def get_feature_names() -> List[str]:
    """从 FeatureEngineer 获取特征名列表"""
    report_path = Path(__file__).parent.parent / 'quantsys' / 'ml' / 'models' / 'training_report_latest.json'
    if report_path.exists():
        try:
            with open(report_path) as f:
                report = json.load(f)
            feature_names = report.get('feature_names')
            if isinstance(feature_names, list) and feature_names:
                return feature_names
        except Exception:
            pass

    engineer = FeatureEngineer()
    return engineer.get_feature_names()

def analyze_feature_importance(model, model_path: str = None) -> pd.DataFrame:
    """分析模型的特征重要性"""
    try:
        feature_names = get_feature_names()
        if hasattr(model, 'feature_importances_'):
            importances = model.feature_importances_
        elif hasattr(model, 'coef_'):
            importances = abs(model.coef_[0]) if len(model.coef_.shape) > 1 else abs(model.coef_)
        else:
            return pd.DataFrame({'Feature': ['N/A'], 'Importance': [0], 'Percentage': [0], 'Cumulative': [0]})

        if len(feature_names) < len(importances):
            feature_names.extend([f'feature_{idx}' for idx in range(len(feature_names), len(importances))])

        total = sum(importances) or 1
        df = pd.DataFrame({
            'Feature': feature_names[:len(importances)],
            'Importance': importances,
        })
        df['Percentage'] = (df['Importance'] / total * 100).round(2)
        df = df.sort_values('Importance', ascending=False).reset_index(drop=True)
        df['Cumulative'] = df['Percentage'].cumsum().round(1)
        return df
    except Exception:
        return pd.DataFrame({'Feature': ['N/A'], 'Importance': [0], 'Percentage': [0], 'Cumulative': [0]})

app = Flask(__name__)
CORS(app)  # 允许跨域

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)

# ---- 认证中间件 ----
def require_ops_auth():
    """检查操作 API token"""
    expected_token = os.environ.get('OPS_API_TOKEN')
    if not expected_token:
        return None  # 未配置 token，跳过认证

    # 从 header 提取 token
    token = request.headers.get('x-pi-ops-token')
    if not token:
        auth_header = request.headers.get('Authorization', '')
        if auth_header.startswith('Bearer '):
            token = auth_header[7:]

    if token == expected_token:
        return None  # 认证通过

    return jsonify({'success': False, 'error': 'Missing or invalid operations token'}), 401

@app.before_request
def check_auth():
    """在每个请求前检查认证"""
    # 健康检查端点不需要认证
    if request.path == '/health':
        return None

    # 需要认证的端点
    protected_paths = ['/api/backtest', '/api/training', '/api/signals', '/api/jobs', '/api/platform', '/api/scheduler', '/api/strategies']
    if any(request.path.startswith(path) for path in protected_paths):
        return require_ops_auth()

    return None

# ---- 异步任务追踪 ----
_scripts_dir = Path(__file__).parent.parent / 'scripts'
_jobs_dir = Path(__file__).parent.parent.parent / '.pi-invest' / 'jobs'
_jobs_dir.mkdir(parents=True, exist_ok=True)
_pipeline_runs_dir = Path(__file__).parent.parent.parent / '.pi-invest' / 'pipeline-runs'
_pipeline_runs_dir.mkdir(parents=True, exist_ok=True)

WEB_JOB_TYPES = {
    'data_update',
    'factor_compute',
    'signal_generate',
    'model_train',
    'backtest_run',
    'daily_report',
    'risk_check',
}

PIPELINE_STEP_DEFINITIONS = [
    {'key': 'resolve', 'name': '标的识别', 'type': 'resolve'},
    {'key': 'data_update', 'name': '行情补齐', 'type': 'job', 'job_type': 'data_update'},
    {'key': 'factor_compute', 'name': '因子计算', 'type': 'job', 'job_type': 'factor_compute'},
    {'key': 'model_train', 'name': '模型训练', 'type': 'job', 'job_type': 'model_train'},
    {'key': 'signal_generate', 'name': '信号生成', 'type': 'job', 'job_type': 'signal_generate'},
    {'key': 'risk_check', 'name': '风险过滤', 'type': 'job', 'job_type': 'risk_check'},
    {'key': 'backtest_run', 'name': '回测验证', 'type': 'job', 'job_type': 'backtest_run'},
    {'key': 'daily_report', 'name': '结果汇总', 'type': 'job', 'job_type': 'daily_report'},
]

SCHEDULER_TASK_DEFINITIONS = [
    {
        'id': 'data_update',
        'name': '数据更新',
        'scheduleKind': 'cron',
        'scheduleExpr': '0 17 * * 1-5',
        'payload': {'job_type': 'data_update', 'params': {'source': 'hs300', 'days': 5, 'force': False}},
        'compensationEnabled': True,
        'compensationCheckAfter': '18:00',
        'compensationMaxAttempts': 1,
        'deleteAfterRun': False,
    },
    {
        'id': 'factor_compute',
        'name': '因子计算',
        'scheduleKind': 'cron',
        'scheduleExpr': '30 17 * * 1-5',
        'payload': {'job_type': 'factor_compute', 'params': {}},
        'compensationEnabled': True,
        'compensationCheckAfter': '18:30',
        'compensationMaxAttempts': 1,
        'deleteAfterRun': False,
    },
    {
        'id': 'signal_generate',
        'name': '信号生成',
        'scheduleKind': 'cron',
        'scheduleExpr': '0 18 * * 1-5',
        'payload': {'job_type': 'signal_generate', 'params': {}},
        'compensationEnabled': True,
        'compensationCheckAfter': '19:00',
        'compensationMaxAttempts': 1,
        'deleteAfterRun': False,
    },
    {
        'id': 'daily_report',
        'name': '日报生成',
        'scheduleKind': 'cron',
        'scheduleExpr': '30 18 * * 1-5',
        'payload': {'job_type': 'daily_report', 'params': {}},
        'compensationEnabled': True,
        'compensationCheckAfter': '19:30',
        'compensationMaxAttempts': 1,
        'deleteAfterRun': False,
    },
    {
        'id': 'risk_check',
        'name': '风险检查',
        'scheduleKind': 'cron',
        'scheduleExpr': '0 9 * * 1-5',
        'payload': {'job_type': 'risk_check', 'params': {}},
        'compensationEnabled': True,
        'compensationCheckAfter': '09:30',
        'compensationMaxAttempts': 1,
        'deleteAfterRun': False,
    },
    {
        'id': 'model_train',
        'name': '模型训练',
        'scheduleKind': 'cron',
        'scheduleExpr': '0 20 * * 5',
        'payload': {'job_type': 'model_train', 'params': {'days': 90, 'model': 'xgboost', 'cvSplits': 5}},
        'compensationEnabled': True,
        'compensationCheckAfter': '22:00',
        'compensationMaxAttempts': 1,
        'deleteAfterRun': False,
    },
    {
        'id': 'backtest_run',
        'name': '回测运行',
        'scheduleKind': 'cron',
        'scheduleExpr': '0 21 * * 5',
        'payload': {'job_type': 'backtest_run', 'params': {}},
        'compensationEnabled': False,
        'compensationMaxAttempts': 1,
        'deleteAfterRun': False,
    },
]

JOB_STATUS_MAP = {
    'created': 'queued',
    'completed': 'success',
}


def _create_job(job_type: str, params: dict = None) -> str:
    """创建异步任务到 PostgreSQL，返回 job_id"""
    job_id = f"{job_type}_{uuid.uuid4().hex[:8]}"

    conn = _connect_postgres()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO quant.jobs (id, type, status, params, created_at, attempts)
                VALUES (%s, %s, %s, %s, NOW(), 0)
            """, (job_id, job_type, 'created', json.dumps(params or {})))
        conn.commit()
    finally:
        conn.close()

    return job_id


def _timestamp_to_iso(value):
    if value is None:
        return None
    if isinstance(value, str):
        return value
    try:
        return datetime.fromtimestamp(float(value), timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    except (TypeError, ValueError):
        return None


# ── Scheduler task DB helpers ──────────────────────────────────────────

def _seed_scheduler_tasks():
    """将 SCHEDULER_TASK_DEFINITIONS 种子数据写入 quant.scheduler_tasks（仅当表为空时）。"""
    conn = _connect_postgres()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM quant.scheduler_tasks")
            count = cur.fetchone()[0]
            if count > 0:
                return
        with conn.cursor() as cur:
            for task in SCHEDULER_TASK_DEFINITIONS:
                cur.execute("""
                    INSERT INTO quant.scheduler_tasks
                        (id, name, schedule_kind, schedule_expr, payload, enabled,
                         compensation_enabled, compensation_check_after,
                         compensation_max_attempts, delete_after_run)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (id) DO NOTHING
                """, (
                    task['id'],
                    task['name'],
                    task.get('scheduleKind', 'cron'),
                    task.get('scheduleExpr', ''),
                    json.dumps(task.get('payload', {})),
                    True,
                    task.get('compensationEnabled', False),
                    task.get('compensationCheckAfter'),
                    task.get('compensationMaxAttempts', 1),
                    task.get('deleteAfterRun', False),
                ))
        conn.commit()
    finally:
        conn.close()


def _load_scheduler_tasks_from_db() -> list:
    """从 quant.scheduler_tasks 加载所有任务定义。"""
    conn = _connect_postgres()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT id, name, schedule_kind, schedule_expr, payload,
                       enabled, compensation_enabled, compensation_check_after,
                       compensation_max_attempts, delete_after_run,
                       created_at, updated_at
                FROM quant.scheduler_tasks
                ORDER BY created_at
            """)
            rows = cur.fetchall()
        tasks = []
        for row in rows:
            payload = row['payload'] if isinstance(row['payload'], dict) else json.loads(row['payload'] or '{}')
            # normalize: ensure 'command' exists (frontend reads payload.command)
            if not payload.get('command') and payload.get('job_type'):
                payload['command'] = payload['job_type']
            tasks.append({
                'id': row['id'],
                'name': row['name'],
                'scheduleKind': row['schedule_kind'],
                'scheduleExpr': row['schedule_expr'],
                'payload': payload,
                'enabled': row['enabled'],
                'compensationEnabled': row['compensation_enabled'],
                'compensationCheckAfter': str(row['compensation_check_after']) if row['compensation_check_after'] else None,
                'compensationMaxAttempts': row['compensation_max_attempts'],
                'deleteAfterRun': row['delete_after_run'],
            })
        return tasks
    finally:
        conn.close()


def _get_scheduler_task_from_db(task_id: str) -> dict:
    """从 DB 加载单个调度任务。"""
    conn = _connect_postgres()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT id, name, schedule_kind, schedule_expr, payload,
                       enabled, compensation_enabled, compensation_check_after,
                       compensation_max_attempts, delete_after_run
                FROM quant.scheduler_tasks
                WHERE id = %s
            """, (task_id,))
            row = cur.fetchone()
        if not row:
            return None
        payload = row['payload'] if isinstance(row['payload'], dict) else json.loads(row['payload'] or '{}')
        if not payload.get('command') and payload.get('job_type'):
            payload['command'] = payload['job_type']
        return {
            'id': row['id'],
            'name': row['name'],
            'scheduleKind': row['schedule_kind'],
            'scheduleExpr': row['schedule_expr'],
            'payload': payload,
            'enabled': row['enabled'],
            'compensationEnabled': row['compensation_enabled'],
            'compensationCheckAfter': str(row['compensation_check_after']) if row['compensation_check_after'] else None,
            'compensationMaxAttempts': row['compensation_max_attempts'],
            'deleteAfterRun': row['delete_after_run'],
        }
    finally:
        conn.close()


def _save_scheduler_task_to_db(task: dict) -> dict:
    """插入或更新一条调度任务到 DB。返回持久化后的任务字典。"""
    task_id = task.get('id') or f"task_{uuid.uuid4().hex[:8]}"
    conn = _connect_postgres()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO quant.scheduler_tasks
                    (id, name, schedule_kind, schedule_expr, payload, enabled,
                     compensation_enabled, compensation_check_after,
                     compensation_max_attempts, delete_after_run)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (id) DO UPDATE SET
                    name = EXCLUDED.name,
                    schedule_kind = EXCLUDED.schedule_kind,
                    schedule_expr = EXCLUDED.schedule_expr,
                    payload = EXCLUDED.payload,
                    enabled = EXCLUDED.enabled,
                    compensation_enabled = EXCLUDED.compensation_enabled,
                    compensation_check_after = EXCLUDED.compensation_check_after,
                    compensation_max_attempts = EXCLUDED.compensation_max_attempts,
                    delete_after_run = EXCLUDED.delete_after_run,
                    updated_at = NOW()
            """, (
                task_id,
                task.get('name', ''),
                task.get('scheduleKind', 'cron'),
                task.get('scheduleExpr', ''),
                json.dumps(task.get('payload', {})),
                task.get('enabled', True),
                task.get('compensationEnabled', False),
                task.get('compensationCheckAfter'),
                task.get('compensationMaxAttempts', 1),
                task.get('deleteAfterRun', False),
            ))
        conn.commit()
    finally:
        conn.close()
    return _get_scheduler_task_from_db(task_id)


def _delete_scheduler_task_from_db(task_id: str) -> bool:
    """从 DB 中删除一条调度任务。返回是否成功删除。"""
    conn = _connect_postgres()
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM quant.scheduler_tasks WHERE id = %s", (task_id,))
            deleted = cur.rowcount > 0
        conn.commit()
        return deleted
    finally:
        conn.close()


def _set_scheduler_task_enabled(task_id: str, enabled: bool) -> bool:
    """启用或停用一条调度任务。"""
    conn = _connect_postgres()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE quant.scheduler_tasks SET enabled = %s, updated_at = NOW() WHERE id = %s",
                (enabled, task_id),
            )
            updated = cur.rowcount > 0
        conn.commit()
        return updated
    finally:
        conn.close()


def _query_jobs_from_db(limit: int = 50, offset: int = 0,
                        job_type: str = None, status: str = None) -> list:
    """从 quant.jobs 查询任务运行记录。"""
    conn = _connect_postgres()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            clauses = []
            params = []
            if job_type:
                clauses.append("type = %s")
                params.append(job_type)
            if status:
                clauses.append("status = %s")
                params.append(status)
            where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
            params.extend([limit, offset])
            cur.execute(f"""
                SELECT id, type, status, params, result, error, logs,
                       created_at, updated_at, started_at, finished_at, attempts
                FROM quant.jobs
                {where}
                ORDER BY created_at DESC
                LIMIT %s OFFSET %s
            """, params)
            rows = cur.fetchall()
        jobs = []
        for row in rows:
            jobs.append({
                'job_id': row['id'],
                'type': row['type'],
                'status': row['status'],
                'params': row['params'],
                'result': row['result'],
                'error': row['error'],
                'logs': row['logs'],
                'created_at': row['created_at'].timestamp() if row['created_at'] else None,
                'updated_at': row['updated_at'].timestamp() if row['updated_at'] else None,
                'started_at': row['started_at'].timestamp() if row['started_at'] else None,
                'completed_at': row['finished_at'].timestamp() if row['finished_at'] else None,
                'attempts': row['attempts'],
            })
        return jobs
    finally:
        conn.close()


def _latest_job_for_type(job_type: str) -> dict:
    """从 PostgreSQL 获取指定类型的最新任务（替代旧的基于文件的实现）。"""
    jobs = _query_jobs_from_db(limit=1, job_type=job_type)
    return jobs[0] if jobs else None


def _normalize_job_for_web(job: dict) -> dict:
    job_id = job.get('id') or job.get('job_id')
    status = JOB_STATUS_MAP.get(job.get('status'), job.get('status', 'queued'))
    created_at = _timestamp_to_iso(job.get('createdAt') or job.get('created_at')) or datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    started_at = _timestamp_to_iso(job.get('startedAt') or job.get('started_at'))
    finished_at = _timestamp_to_iso(job.get('finishedAt') or job.get('completed_at'))
    updated_at = finished_at or started_at or created_at

    normalized = {
        'id': job_id,
        'type': job.get('type', 'unknown'),
        'status': status,
        'params': job.get('params') or {},
        'logs': job.get('logs') or [],
        'attempts': job.get('attempts') or 0,
        'createdAt': created_at,
        'updatedAt': updated_at,
    }
    if started_at:
        normalized['startedAt'] = started_at
    if finished_at:
        normalized['finishedAt'] = finished_at
    if job.get('result') is not None:
        normalized['result'] = job.get('result')
    if job.get('error') is not None:
        normalized['error'] = job.get('error') if isinstance(job.get('error'), str) else json.dumps(job.get('error'), ensure_ascii=False)
    return normalized


def _get_job(job_id: str) -> dict:
    """从 PostgreSQL 读取任务状态"""
    conn = _connect_postgres()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT id, type, status, params, result, error,
                       created_at, updated_at, started_at, finished_at, attempts
                FROM quant.jobs
                WHERE id = %s
            """, (job_id,))
            row = cur.fetchone()

        if not row:
            return None

        # 转换为旧格式兼容
        return {
            'job_id': row['id'],
            'type': row['type'],
            'status': row['status'],
            'params': row['params'],
            'result': row['result'],
            'error': row['error'],
            'created_at': row['created_at'].timestamp() if row['created_at'] else None,
            'started_at': row['started_at'].timestamp() if row['started_at'] else None,
            'completed_at': row['finished_at'].timestamp() if row['finished_at'] else None,
            'attempts': row['attempts']
        }
    finally:
        conn.close()


def _write_job(job_id: str, job: dict):
    """更新任务状态到 PostgreSQL"""
    conn = _connect_postgres()
    try:
        with conn.cursor() as cur:
            # 构建更新字段
            updates = []
            params = []

            if 'status' in job:
                updates.append("status = %s")
                params.append(job['status'])

            if 'result' in job:
                updates.append("result = %s")
                params.append(json.dumps(job['result']) if job['result'] else None)

            if 'error' in job:
                updates.append("error = %s")
                params.append(job['error'])

            if 'started_at' in job and job['started_at']:
                updates.append("started_at = %s")
                params.append(datetime.fromtimestamp(job['started_at'], timezone.utc))

            if 'completed_at' in job and job['completed_at']:
                updates.append("finished_at = %s")
                params.append(datetime.fromtimestamp(job['completed_at'], timezone.utc))

            updates.append("updated_at = NOW()")
            params.append(job_id)

            query = f"UPDATE quant.jobs SET {', '.join(updates)} WHERE id = %s"
            cur.execute(query, params)
        conn.commit()
    finally:
        conn.close()


def _pipeline_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')


def _pipeline_run_path(run_id: str) -> Path:
    return _pipeline_runs_dir / f"{run_id}.json"


def _write_pipeline_run(run: dict):
    _pipeline_runs_dir.mkdir(parents=True, exist_ok=True)
    run['updatedAt'] = _pipeline_now_iso()
    path = _pipeline_run_path(run['id'])
    tmp_file = _pipeline_runs_dir / f".{run['id']}.{uuid.uuid4().hex}.tmp"
    with open(tmp_file, 'w') as f:
        json.dump(run, f, indent=2, ensure_ascii=False)
    os.replace(tmp_file, path)


def _get_pipeline_run(run_id: str) -> dict:
    path = _pipeline_run_path(run_id)
    if not path.exists():
        return None
    with open(path, 'r') as f:
        return json.load(f)


def _pipeline_step_template(step: dict) -> dict:
    return {
        'key': step['key'],
        'name': step['name'],
        'type': step['type'],
        'jobType': step.get('job_type'),
        'status': 'queued',
        'jobId': None,
        'input': None,
        'output': None,
        'logs': [],
        'error': None,
        'startedAt': None,
        'finishedAt': None,
    }


def _create_pipeline_run(params: dict) -> dict:
    now = _pipeline_now_iso()
    symbols = _normalize_symbols(params.get('symbols'))
    run = {
        'id': f"pipeline_{uuid.uuid4().hex[:8]}",
        'status': 'queued',
        'symbols': symbols,
        'validSymbols': [],
        'invalidSymbols': [],
        'params': params,
        'currentStep': 'resolve',
        'progress': 0,
        'error': None,
        'steps': [_pipeline_step_template(step) for step in PIPELINE_STEP_DEFINITIONS],
        'createdAt': now,
        'updatedAt': now,
        'startedAt': None,
        'finishedAt': None,
    }
    _write_pipeline_run(run)
    return run


def _set_pipeline_step(run: dict, step_key: str, **kwargs):
    for step in run.get('steps', []):
        if step.get('key') == step_key:
            step.update(kwargs)
            break


def _pipeline_job_params(job_type: str, params: dict, symbols: list) -> dict:
    days = params.get('days', 180)
    common = {'symbols': symbols}
    if job_type == 'data_update':
        return {**common, 'days': days, 'force': params.get('force', True)}
    if job_type == 'model_train':
        return {
            **common,
            'days': days,
            'model': params.get('model', 'xgboost'),
            'futureDays': params.get('futureDays', 5),
            'threshold': params.get('threshold', 0.05),
            'useFeatureEngineering': params.get('useFeatureEngineering', True),
        }
    if job_type == 'backtest_run':
        return {**common, 'days': days}
    if job_type in {'factor_compute', 'signal_generate', 'risk_check'}:
        return common
    return {}


def _wait_for_pipeline_job(job_id: str, step_name: str, run_id: str, step_key: str, poll_seconds: float = 2.0) -> dict:
    while True:
        run = _get_pipeline_run(run_id)
        if run and run.get('status') == 'cancelled':
            _update_job(job_id, status='cancelled', completed_at=time.time())
            raise RuntimeError('Pipeline run cancelled')

        job = _get_job(job_id)
        if not job:
            raise RuntimeError(f'{step_name} 任务记录不存在: {job_id}')
        normalized = _normalize_job_for_web(job)
        status = normalized.get('status')

        if run:
            _set_pipeline_step(run, step_key, logs=normalized.get('logs') or [])
            _write_pipeline_run(run)

        if status == 'success':
            return normalized
        if status in {'failed', 'cancelled'}:
            raise RuntimeError(normalized.get('error') or f'{step_name} 执行失败')
        time.sleep(poll_seconds)


def _refresh_pipeline_progress(run: dict):
    steps = run.get('steps') or []
    finished = sum(1 for step in steps if step.get('status') in {'success', 'skipped'})
    run['progress'] = round((finished / len(steps)) * 100) if steps else 0


def _sync_pipeline_run_jobs(run: dict) -> dict:
    if run.get('status') not in {'running', 'queued'}:
        return run

    changed = False
    failed = None
    all_terminal = True
    for step in run.get('steps', []):
        job_id = step.get('jobId')
        if not job_id or step.get('status') in {'success', 'failed', 'cancelled', 'skipped'}:
            if step.get('status') not in {'success', 'failed', 'cancelled', 'skipped'}:
                all_terminal = False
            continue
        job = _get_job(job_id)
        if not job:
            all_terminal = False
            continue
        normalized = _normalize_job_for_web(job)
        previous = step.get('status')
        status = normalized.get('status')
        if status == 'success':
            step.update({'status': 'success', 'output': normalized.get('result'), 'finishedAt': normalized.get('finishedAt')})
        elif status == 'failed':
            step.update({'status': 'failed', 'error': normalized.get('error'), 'finishedAt': normalized.get('finishedAt')})
            failed = step
        elif status == 'cancelled':
            step.update({'status': 'cancelled', 'finishedAt': normalized.get('finishedAt')})
            failed = step
        else:
            step.update({'status': 'running', 'logs': normalized.get('logs') or []})
            all_terminal = False
        changed = changed or previous != step.get('status')

    _refresh_pipeline_progress(run)
    if failed:
        run['status'] = 'failed' if failed.get('status') == 'failed' else 'cancelled'
        run['error'] = failed.get('error')
        run['finishedAt'] = run.get('finishedAt') or _pipeline_now_iso()
        changed = True
    elif all_terminal and run.get('status') == 'running':
        run['status'] = 'success'
        run['progress'] = 100
        run['finishedAt'] = run.get('finishedAt') or _pipeline_now_iso()
        changed = True

    if changed:
        _write_pipeline_run(run)
    return run


def _run_pipeline_async(run_id: str):
    run = _get_pipeline_run(run_id)
    if not run:
        return

    try:
        run['status'] = 'running'
        run['startedAt'] = run.get('startedAt') or _pipeline_now_iso()
        _write_pipeline_run(run)

        valid_symbols = []
        for step_def in PIPELINE_STEP_DEFINITIONS:
            run = _get_pipeline_run(run_id) or run
            if run.get('status') == 'cancelled':
                return
            step_key = step_def['key']
            run['currentStep'] = step_key
            _set_pipeline_step(run, step_key, status='running', startedAt=_pipeline_now_iso())
            _write_pipeline_run(run)

            if step_def['type'] == 'resolve':
                resolved = _resolve_symbols_for_pipeline(run.get('symbols') or [], run.get('params', {}).get('days', 180))
                valid_symbols = [item['symbol'] for item in resolved.get('valid', [])]
                run['validSymbols'] = valid_symbols
                run['invalidSymbols'] = [item.get('symbol') for item in resolved.get('invalid', [])]
                _set_pipeline_step(run, step_key, status='success', output=resolved, finishedAt=_pipeline_now_iso())
                if not valid_symbols:
                    raise ValueError('没有可执行标的：本地和外部接口均未找到可用股票')
                _refresh_pipeline_progress(run)
                _write_pipeline_run(run)
                continue

            job_type = step_def['job_type']
            params = _pipeline_job_params(job_type, run.get('params') or {}, valid_symbols)
            job_id = _start_job_for_type(job_type, params)
            _set_pipeline_step(
                run,
                step_key,
                status='running',
                jobId=job_id,
                input=params,
            )
            _write_pipeline_run(run)
            normalized = _wait_for_pipeline_job(job_id, step_def['name'], run_id, step_key)
            run = _get_pipeline_run(run_id) or run
            _set_pipeline_step(
                run,
                step_key,
                status='success',
                output=normalized.get('result'),
                logs=normalized.get('logs') or [],
                finishedAt=normalized.get('finishedAt') or _pipeline_now_iso(),
            )
            _refresh_pipeline_progress(run)
            _write_pipeline_run(run)

        run = _get_pipeline_run(run_id) or run
        run['status'] = 'success'
        run['progress'] = 100
        run['finishedAt'] = run.get('finishedAt') or _pipeline_now_iso()
        _write_pipeline_run(run)
    except Exception as exc:
        run = _get_pipeline_run(run_id) or run
        run['status'] = 'failed'
        run['error'] = str(exc)
        run['finishedAt'] = run.get('finishedAt') or _pipeline_now_iso()
        _set_pipeline_step(run, run.get('currentStep'), status='failed', error=str(exc), finishedAt=_pipeline_now_iso())
        _write_pipeline_run(run)


def _resolve_symbols_for_pipeline(symbols: list, required_days: int) -> dict:
    db = _quant_database()
    try:
        stocks = []
        valid = []
        invalid = []
        for symbol in symbols:
            local_stock = _lookup_local_stock(db, symbol)
            if local_stock:
                item = _resolved_stock_response(db, local_stock, 'local', required_days)
                stocks.append(item)
                valid.append(item)
                continue

            external = _lookup_external_stock(symbol)
            if not external or external.get('error'):
                item = {'symbol': symbol, 'reason': '外部接口未找到该股票'}
                stocks.append(item)
                invalid.append(item)
                continue

            payload = _stock_payload_from_external(symbol, external)
            db.upsert_stocks([payload])
            item = _resolved_stock_response(db, payload, 'external_added', required_days)
            stocks.append(item)
            valid.append(item)
        return {'stocks': stocks, 'valid': valid, 'invalid': invalid}
    finally:
        db.close()


def _update_job(job_id: str, **kwargs):
    """更新任务状态"""
    job = _get_job(job_id) or {}
    if job.get('status') == 'cancelled' and kwargs.get('status') != 'cancelled':
        return
    job.update(kwargs)
    _write_job(job_id, job)


def _complete_job_without_executor(job_id: str, result: dict = None):
    _update_job(job_id, status='completed', started_at=time.time(), completed_at=time.time(), result=result or {'message': 'No executor configured'})


def _run_data_update_job(job_id: str, data: dict):
    try:
        _update_job(job_id, status='running', started_at=time.time())
        symbols = _normalize_symbols(data.get('symbols'))
        source = 'symbols' if symbols else data.get('source', 'all')
        days = data.get('days', 5)
        force = data.get('force', False)
        result = _execute_data_update(source, days, force, symbols=symbols or None)
        _update_job(job_id, status='completed', completed_at=time.time(), result=result)
    except Exception as e:
        _update_job(job_id, status='failed', completed_at=time.time(), error=str(e))


def _run_risk_check_job(job_id: str, data: dict):
    """风险检查执行器：检查持仓集中度、止损、流动性风险。"""
    try:
        _update_job(job_id, status='running', started_at=time.time())
        symbols = _normalize_symbols(data.get('symbols'))
        account_value = data.get('account_value')

        portfolio_path = _project_root / '.pi-invest' / 'portfolio.json'
        holdings = []
        if portfolio_path.exists():
            with open(portfolio_path, 'r') as f:
                pf = json.load(f)
                holdings = pf.get('holdings', [])

        if symbols:
            holdings = [h for h in holdings if h.get('symbol') in symbols]

        checks = []
        total_risk_score = 100

        for h in holdings:
            symbol = h.get('symbol', 'unknown')
            quantity = h.get('quantity', 0)
            avg_cost = h.get('avg_cost', 0)
            position_value = quantity * avg_cost

            current_price = None
            try:
                conn = get_db()
                cursor = conn.execute(
                    "SELECT close FROM daily_klines WHERE symbol=? ORDER BY date DESC LIMIT 1",
                    (symbol,)
                )
                row = cursor.fetchone()
                conn.close()
                if row:
                    current_price = row[0]
            except Exception:
                pass

            item_checks = []
            item_score = 100

            if account_value and account_value > 0:
                concentration = (position_value / account_value) * 100
                if concentration > 30:
                    item_checks.append({'type': 'concentration', 'level': 'high',
                                       'message': f'{symbol} 仓位集中度 {concentration:.1f}% > 30%',
                                       'suggestion': '建议分散持仓'})
                    item_score -= 30
                elif concentration > 20:
                    item_checks.append({'type': 'concentration', 'level': 'medium',
                                       'message': f'{symbol} 仓位集中度 {concentration:.1f}% > 20%'})
                    item_score -= 15

            if current_price and avg_cost > 0:
                pnl_pct = ((current_price - avg_cost) / avg_cost) * 100
                if pnl_pct < -8:
                    item_checks.append({'type': 'stop_loss', 'level': 'high',
                                       'message': f'{symbol} 浮亏 {pnl_pct:.1f}%，已触及止损线',
                                       'suggestion': '建议立即止损'})
                    item_score -= 40
                elif pnl_pct < -5:
                    item_checks.append({'type': 'stop_loss', 'level': 'medium',
                                       'message': f'{symbol} 浮亏 {pnl_pct:.1f}%，接近止损线'})
                    item_score -= 20

            checks.append({
                'symbol': symbol,
                'name': h.get('name', ''),
                'position_value': position_value,
                'current_price': current_price,
                'avg_cost': avg_cost,
                'pnl_pct': ((current_price - avg_cost) / avg_cost * 100) if current_price and avg_cost else None,
                'checks': item_checks,
                'score': max(0, item_score),
            })
            total_risk_score = min(total_risk_score, item_score)

        if total_risk_score >= 80:
            risk_level = 'low'
        elif total_risk_score >= 50:
            risk_level = 'medium'
        else:
            risk_level = 'high'

        result = {
            'risk_score': total_risk_score,
            'risk_level': risk_level,
            'holdings_count': len(holdings),
            'checks': checks,
        }
        _update_job(job_id, status='completed', completed_at=time.time(), result=result)
    except Exception as e:
        _update_job(job_id, status='failed', completed_at=time.time(), error=str(e))


def _run_daily_report_job(job_id: str, data: dict):
    """日报生成执行器：调用 scripts/daily_report.py 生成每日报告。"""
    try:
        _update_job(job_id, status='running', started_at=time.time())
        script = _scripts_dir / 'daily_report.py'
        if not script.exists():
            raise FileNotFoundError(f'日报脚本不存在: {script}')
        proc = subprocess.run(
            [sys.executable, str(script)],
            capture_output=True, text=True, timeout=300,
        )
        if proc.returncode == 0:
            _update_job(job_id, status='completed', completed_at=time.time(),
                       result={'stdout': proc.stdout[-500:], 'stderr': proc.stderr[-500:]})
        else:
            _update_job(job_id, status='failed', completed_at=time.time(),
                       error=proc.stderr[-1000:] or f'exit code {proc.returncode}')
    except Exception as e:
        _update_job(job_id, status='failed', completed_at=time.time(), error=str(e))


def _models_dir() -> Path:
    return _project_root / 'quant' / 'quantsys' / 'ml' / 'models'


def _strategies_dir() -> Path:
    return _project_root / '.pi-invest' / 'quant' / 'strategies'


def _charts_dir() -> Path:
    return _project_root / '.pi-invest' / 'quant' / 'charts'


def _load_json_file(path: Path):
    with open(path, 'r') as f:
        return json.load(f)


def _report_n_features(report: dict) -> int:
    if isinstance(report.get('n_features'), int):
        return report['n_features']
    data = report.get('data')
    if isinstance(data, dict):
        value = data.get('n_features')
        if isinstance(value, int):
            return value
    feature_names = report.get('feature_names')
    if isinstance(feature_names, list):
        return len(feature_names)
    return 0


def _iter_training_report_files():
    models_dir = _models_dir()
    if not models_dir.exists():
        return []
    return sorted(
        [
            path for path in models_dir.glob('training_report_*.json')
            if path.name != 'training_report_latest.json'
        ],
        reverse=True,
    )


def _training_status_from_job(job: dict) -> dict:
    normalized = _normalize_job_for_web(job)
    status = normalized['status']
    training_status = {
        'queued': 'running',
        'running': 'running',
        'success': 'completed',
        'failed': 'failed',
        'cancelled': 'failed',
    }.get(status, 'running')
    return {
        'id': normalized['id'],
        'status': training_status,
        'progress': 100 if training_status == 'completed' else 0,
        'startTime': normalized.get('startedAt') or normalized.get('createdAt'),
        'endTime': normalized.get('finishedAt'),
        'params': normalized.get('params') or {},
        'result': normalized.get('result'),
        'error': normalized.get('error'),
    }


def _build_training_args(params: dict) -> list:
    model = params.get('model', 'xgboost')
    if model == 'random_forest':
        model = 'randomforest'

    args = ['--days', str(params.get('days', 90)), '--model', str(model)]
    symbols = _normalize_symbols(params.get('symbols'))
    if symbols:
        args.extend(['--symbols', ','.join(symbols)])
    if params.get('cvSplits') is not None:
        args.extend(['--cv-splits', str(params['cvSplits'])])
    if params.get('useFeatureEngineering', True):
        args.append('--use-feature-engineering')
    return args


def _normalize_symbols(value) -> list:
    if value is None:
        return []
    if isinstance(value, str):
        raw_symbols = [part for part in value.replace('，', ',').replace('\n', ',').split(',')]
    elif isinstance(value, list):
        raw_symbols = value
    else:
        return []

    symbols = []
    seen = set()
    for raw_symbol in raw_symbols:
        symbol = normalize_symbol(str(raw_symbol))
        if not symbol or symbol in seen:
            continue
        seen.add(symbol)
        symbols.append(symbol)
    return symbols


def _validate_pagination_params(page, page_size, max_page_size=100):
    """Validate and normalize pagination parameters.

    Args:
        page: Page number (may be None or default value from request.args)
        page_size: Items per page (may be None or default value from request.args)
        max_page_size: Maximum allowed page size, default 100

    Returns:
        (validated_page, validated_page_size) tuple, both integers

    Raises:
        ValueError: When parameters are invalid
    """
    if page is None:
        page = 1
    if page_size is None:
        page_size = 10

    if not isinstance(page, int):
        raise ValueError("Invalid page parameter: must be an integer")
    if not isinstance(page_size, int):
        raise ValueError("Invalid pageSize parameter: must be an integer")

    if page < 1:
        raise ValueError("Invalid page parameter: must be >= 1")
    if page_size < 1:
        raise ValueError("Invalid pageSize parameter: must be >= 1")
    if page_size > max_page_size:
        raise ValueError(f"Invalid pageSize parameter: must be <= {max_page_size}")

    return (page, page_size)


def _calculate_pagination_metadata(page, page_size, total):
    """Calculate pagination metadata.

    Args:
        page: Current page number
        page_size: Items per page
        total: Total record count

    Returns:
        Dict with page, pageSize, total, totalPages, hasNext, hasPrev
    """
    total_pages = math.ceil(total / page_size) if total > 0 else 0
    return {
        "page": page,
        "pageSize": page_size,
        "total": total,
        "totalPages": total_pages,
        "hasNext": page < total_pages,
        "hasPrev": page > 1,
    }


def _paginate_query(query, params, page, page_size):
    """Append LIMIT and OFFSET clauses to a SQL query.

    Args:
        query: Original SQL query string
        params: Original query parameters list
        page: Page number
        page_size: Items per page

    Returns:
        (paginated_query, paginated_params) tuple
    """
    offset = (page - 1) * page_size
    paginated_query = f"{query} LIMIT ? OFFSET ?"
    paginated_params = params + [page_size, offset]
    return (paginated_query, paginated_params)


def _build_paginated_response(items, page, page_size, total, items_key="items"):
    """Build standard paginated response format.

    Args:
        items: Data list
        page: Current page number
        page_size: Items per page
        total: Total record count
        items_key: Key name for the items list in response, default 'items'

    Returns:
        {"success": True, "data": {items_key: [...], "pagination": {...}}}
    """
    pagination = _calculate_pagination_metadata(page, page_size, total)
    return {
        "success": True,
        "data": {
            items_key: items,
            "pagination": pagination,
        },
    }


def _symbols_args(params: dict) -> list:
    symbols = _normalize_symbols(params.get('symbols'))
    return ['--symbols', ','.join(symbols)] if symbols else []


def _scheduler_run_from_job(task: dict, job: dict, trigger_type: str) -> dict:
    normalized = _normalize_job_for_web(job)
    status = 'triggered'
    if normalized['status'] == 'running':
        status = 'running'
    elif normalized['status'] == 'success':
        status = 'success'
    elif normalized['status'] == 'failed':
        status = 'failed'
    elif normalized['status'] == 'cancelled':
        status = 'skipped'

    now = datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
    return {
        'id': normalized['id'],
        'taskId': task['id'],
        'taskName': task['name'],
        'scheduledFor': now,
        'triggerType': trigger_type,
        'status': status,
        'triggeredAt': normalized.get('createdAt') or now,
        'startedAt': normalized.get('startedAt'),
        'finishedAt': normalized.get('finishedAt'),
        'error': normalized.get('error'),
        'payload': task.get('payload') or {},
        'createdAt': normalized.get('createdAt') or now,
        'updatedAt': normalized.get('updatedAt') or now,
    }


def _scheduler_task_summary(task: dict) -> dict:
    payload = task.get('payload') or {}
    job_type = payload.get('command') or payload.get('job_type')
    latest_job = _latest_job_for_type(job_type) if job_type else None
    last_run = _scheduler_run_from_job(task, latest_job, 'scheduled') if latest_job else None
    today = datetime.now(timezone.utc).strftime('%Y-%m-%d')
    today_triggered = bool(last_run and str(last_run.get('createdAt', '')).startswith(today))
    today_success = bool(today_triggered and last_run and last_run.get('status') == 'success')

    return {
        **task,
        'enabled': task.get('enabled', True),
        'nextRunAt': None,
        'lastRun': last_run,
        'todayTriggered': today_triggered,
        'todaySuccess': today_success,
        'compensationDue': bool(task.get('compensationEnabled') and today_triggered and not today_success),
    }


def _start_job_for_type(job_type: str, data: dict) -> str:
    job_id = _create_job(job_type, data)

    if job_type == 'data_update':
        _update_job(job_id, params={**data, 'async': True})
        threading.Thread(
            target=lambda: _run_data_update_job(job_id, data),
            daemon=True,
        ).start()
    elif job_type == 'model_train':
        threading.Thread(
            target=lambda: _run_ml_retrain_job(job_id, data),
            daemon=True,
        ).start()
    elif job_type == 'factor_compute':
        threading.Thread(
            target=lambda: _run_factor_compute_job(job_id, data),
            daemon=True,
        ).start()
    elif job_type == 'signal_generate':
        threading.Thread(
            target=lambda: _run_signal_generate_job(job_id, data),
            daemon=True,
        ).start()
    elif job_type == 'backtest_run':
        threading.Thread(
            target=lambda: _run_backtest_job(job_id, data),
            daemon=True,
        ).start()
    elif job_type == 'risk_check':
        threading.Thread(
            target=lambda: _run_risk_check_job(job_id, data),
            daemon=True,
        ).start()
    elif job_type == 'daily_report':
        threading.Thread(
            target=lambda: _run_daily_report_job(job_id, data),
            daemon=True,
        ).start()
    else:
        threading.Thread(
            target=lambda: _complete_job_without_executor(job_id),
            daemon=True,
        ).start()

    return job_id


def _normalize_strategy(strategy: dict, strategy_id: str = None) -> dict:
    normalized = {
        **strategy,
        'id': strategy.get('id') or strategy_id or f"strategy_{uuid.uuid4().hex}",
        'name': strategy.get('name') or '未命名策略',
        'description': strategy.get('description') or '',
        'enabled': strategy.get('enabled', True),
        'created_at': strategy.get('created_at') or datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
    }
    normalized.setdefault('screening', {'filters': {}})
    normalized.setdefault('entry', {'conditions': [], 'logic': 'AND'})
    normalized.setdefault('exit', {'conditions': []})
    normalized.setdefault('position', {'max_position_pct': 20, 'max_stocks': 5})
    normalized['entry'].setdefault('conditions', [])
    normalized['entry'].setdefault('logic', 'AND')
    normalized['exit'].setdefault('conditions', [])
    normalized['position'].setdefault('max_position_pct', 20)
    normalized['position'].setdefault('max_stocks', 5)
    return normalized


def _strategy_path(strategy_id: str) -> Path:
    return _strategies_dir() / f'{strategy_id}.json'


def _read_strategy(strategy_id: str):
    path = _strategy_path(strategy_id)
    if not path.exists():
        return None
    return _normalize_strategy(_load_json_file(path), strategy_id)


def _write_strategy(strategy: dict) -> dict:
    _strategies_dir().mkdir(parents=True, exist_ok=True)
    normalized = _normalize_strategy(strategy)
    path = _strategy_path(normalized['id'])
    tmp_path = path.with_name(f'.{path.stem}.{uuid.uuid4().hex}.tmp')
    with open(tmp_path, 'w') as f:
        json.dump(normalized, f, indent=2, ensure_ascii=False)
    os.replace(tmp_path, path)
    return normalized


def _list_strategies() -> list:
    directory = _strategies_dir()
    if not directory.exists():
        return []
    strategies = []
    for path in directory.glob('*.json'):
        try:
            strategies.append(_normalize_strategy(_load_json_file(path), path.stem))
        except Exception:
            continue
    return sorted(strategies, key=lambda item: item.get('created_at', ''), reverse=True)


def _signals_file_path() -> Path:
    project_path = _project_root / 'quant' / '.pi-invest' / 'signals.json'
    if project_path.exists():
        return project_path
    return Path(__file__).parent.parent / '.pi-invest' / 'signals.json'


def _normalize_signal(signal: dict) -> dict:
    raw_signal = str(signal.get('signal') or signal.get('action') or 'hold').lower()
    if raw_signal == 'buy':
        action = 'buy'
    elif raw_signal == 'sell':
        action = 'sell'
    else:
        action = 'hold'

    strategy_name = signal.get('strategy_name') or signal.get('strategy') or signal.get('strategy_id') or ''
    reason = signal.get('reason') or signal.get('reasons') or ''
    reasons = reason if isinstance(reason, list) else ([reason] if reason else [])
    return {
        'symbol': signal.get('symbol', ''),
        'name': signal.get('name', ''),
        'signal': action,
        'confidence': float(signal.get('confidence') or 0),
        'strategy_id': signal.get('strategy_id') or strategy_name,
        'strategy_name': strategy_name,
        'reasons': reasons,
        'price': float(signal.get('price') or 0),
        'timestamp': signal.get('timestamp') or signal.get('date') or datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
        'date': signal.get('date', ''),
    }


def _load_dashboard_signals() -> list:
    """加载信号数据 - 优先从数据库读取，JSON作为fallback"""
    try:
        db = _quant_database()
        if db and db.provider == 'postgres':
            signals = db.get_signal_history(days=30)
            return [_normalize_signal(signal) for signal in signals]
    except Exception as e:
        logger.warning(f"Database read failed, falling back to JSON: {e}")

    # Fallback: 读取JSON文件
    path = _signals_file_path()
    if not path.exists():
        return []
    data = _load_json_file(path)
    signals = data.get('signals', []) if isinstance(data, dict) else data
    if not isinstance(signals, list):
        return []
    return [_normalize_signal(signal) for signal in signals]


def _default_backtest_result(initial_capital: float, start_date: str, end_date: str) -> dict:
    return {
        'total_return': 0.0,
        'annual_return': 0.0,
        'max_drawdown': 0.0,
        'win_rate': 0.0,
        'sharpe_ratio': 0.0,
        'profit_loss_ratio': 0.0,
        'total_trades': 0,
        'winning_trades': 0,
        'losing_trades': 0,
        'daily_equity': [
            {'date': start_date, 'equity': initial_capital},
            {'date': end_date, 'equity': initial_capital},
        ],
    }


def _performance_for_strategy(strategy_id: str, days: int) -> dict:
    strategy = _read_strategy(strategy_id) or {'id': strategy_id, 'name': strategy_id}
    signals = [signal for signal in _load_dashboard_signals() if not signal.get('strategy_id') or signal.get('strategy_id') == strategy_id or signal.get('strategy_name') == strategy.get('name')]
    total = len(signals)
    return {
        'strategy_id': strategy_id,
        'strategy_name': strategy.get('name', strategy_id),
        'total_signals': total,
        'win_rate': 0.0,
        'avg_profit_pct': 0.0,
        'max_profit_pct': 0.0,
        'max_loss_pct': 0.0,
        'sharpe_ratio': None,
        'max_drawdown_pct': 0.0,
        'days': days,
    }


def _chart_response(chart_type: str) -> dict:
    _charts_dir().mkdir(parents=True, exist_ok=True)
    chart_path = _charts_dir() / f'{chart_type}.png'
    if not chart_path.exists():
        chart_path.write_bytes(
            b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01'
            b'\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89'
            b'\x00\x00\x00\rIDATx\x9cc\xf8\xff\xff?\x00\x05\xfe\x02'
            b'\xfeA\xe2!\xbc\x00\x00\x00\x00IEND\xaeB`\x82'
        )
    return {'chart_path': str(chart_path), 'stats': {}}


# 全局变量
db = None
model = None
factor_calculator = None
feature_engineer = None

# 初始化数据库路径（模块级别，确保在Flask重启时也可用）
_project_root = Path(__file__).parent.parent.parent  # quant/api/ → quant/ → project_root/
_project_db = _project_root / '.pi-invest' / 'stock-db' / 'stocks.db'
_home_db = Path.home() / '.pi-invest' / 'stock-db' / 'stocks.db'
db_path = _project_db if _project_db.exists() else _home_db


def init_services():
    """初始化服务"""
    global db, model, factor_calculator, feature_engineer

    # 清理孤儿job（服务器重启前未完成的job）
    try:
        conn = _connect_postgres()
        with conn.cursor() as cur:
            # 查找所有状态为 created 或 running 的job（这些job在服务器重启后不会被执行）
            cur.execute("""
                SELECT COUNT(*) FROM quant.jobs
                WHERE status IN ('created', 'running')
            """)
            orphaned_count = cur.fetchone()[0]

            if orphaned_count > 0:
                # 标记为失败
                cur.execute("""
                    UPDATE quant.jobs
                    SET status = 'failed',
                        error = '服务器重启导致任务未执行',
                        finished_at = NOW()
                    WHERE status IN ('created', 'running')
                """)
                conn.commit()
                print(f"⚠️ Cleaned up {orphaned_count} orphaned jobs from previous server session")
        conn.close()
    except Exception as e:
        print(f"⚠️ Failed to clean up orphaned jobs: {e}")

    # 尝试多个模型路径（优先加载新模型）
    model_paths = [
        Path(__file__).parent.parent / 'quantsys' / 'ml' / 'models' / 'xgboost_latest.pkl',
        Path(__file__).parent.parent / 'quantsys' / 'ml' / 'models' / 'xgboost_model.pkl',
        Path(__file__).parent.parent.parent / '.pi-invest' / 'quant' / 'models' / 'signal_confidence.pkl',
    ]

    for model_path in model_paths:
        if model_path.exists():
            try:
                model = load_model(str(model_path))
                print(f"✅ Model loaded from: {model_path}")
                break
            except Exception as e:
                print(f"⚠️ Failed to load model from {model_path}: {e}")

    if model is None:
        print("⚠️ No model loaded - ML features will be unavailable")

    factor_calculator = FactorCalculator()
    feature_engineer = FeatureEngineer()


def _file_details(path: Path):
    if not path.exists():
        return None
    stat = path.stat()
    return {
        'path': str(path),
        'size_bytes': stat.st_size,
        'modified_at': datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat().replace('+00:00', 'Z'),
    }


def _status_check(name: str, path: Path, healthy_message: str, missing_message: str, extra_details: dict = None):
    details = _file_details(path)
    if not details:
        return {
            'name': name,
            'status': 'unavailable',
            'message': missing_message,
            'details': {'path': str(path), 'exists': False},
        }
    if extra_details:
        details.update(extra_details)
    details['exists'] = True
    return {
        'name': name,
        'status': 'healthy',
        'message': healthy_message,
        'details': details,
    }


def _ensure_schema(conn):
    """确保数据库包含必要的表（增量迁移，不破坏已有数据）"""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS factor_values (
            symbol TEXT NOT NULL,
            date TEXT NOT NULL,
            factor_name TEXT NOT NULL,
            factor_value REAL,
            PRIMARY KEY (symbol, date, factor_name)
        )
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_factor_values_symbol
        ON factor_values(symbol)
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_factor_values_date
        ON factor_values(date)
    """)
    conn.commit()


def get_db_provider():
    """Return the configured quant data provider for read APIs."""
    provider = os.environ.get('QUANT_DB_PROVIDER', 'postgres').strip().lower()
    if provider in {'postgresql', 'pg'}:
        return 'postgres'
    if provider not in {'sqlite', 'postgres'}:
        return 'postgres'
    return provider


class PostgresCompatCursor:
    """Small DB-API cursor wrapper that accepts the SQLite-style SQL used here."""

    TABLE_REPLACEMENTS = {
        'daily_klines': 'quant_compat.daily_klines',
        'factor_values': 'quant_compat.factor_values',
        'daily_quotes': 'quant_compat.daily_quotes',
        'signals': 'quant_compat.signals',
        'stocks': 'quant_compat.stocks',
        'stock_data_summary': 'quant_compat.stock_data_summary',
        'position_history': 'quant.position_history',
        'trades': 'quant.trades',
        'orders': 'quant.orders',
        'agent_orders': 'quant.orders',
    }

    def __init__(self, cursor):
        self.cursor = cursor

    def execute(self, sql, params=None):
        rewritten = self._rewrite_sql(sql)
        self.cursor.execute(rewritten, params)
        return self

    def fetchone(self):
        return self.cursor.fetchone()

    def fetchall(self):
        return self.cursor.fetchall()

    @classmethod
    def _rewrite_sql(cls, sql):
        import re

        rewritten = sql.replace('?', '%s')
        for table, compat_table in cls.TABLE_REPLACEMENTS.items():
            rewritten = re.sub(
                rf'(?<![\w.]){table}(?![\w.])',
                compat_table,
                rewritten,
            )
        return rewritten


class PostgresCompatConnection:
    """Connection wrapper exposing the subset of sqlite3 API used by server.py."""

    def __init__(self, connection):
        self.connection = connection

    def execute(self, sql, params=None):
        cursor = PostgresCompatCursor(self.connection.cursor())
        return cursor.execute(sql, params)

    def commit(self):
        self.connection.commit()

    def close(self):
        self.connection.close()


def _connect_postgres():
    import psycopg2

    database_url = os.environ.get('DATABASE_URL') or os.environ.get('QUANT_DATABASE_URL')
    if database_url:
        return psycopg2.connect(database_url)
    return psycopg2.connect(
        dbname=os.environ.get('PGDATABASE', 'quant_investment'),
        host=os.environ.get('PGHOST', '127.0.0.1'),
        port=os.environ.get('PGPORT'),
        user=os.environ.get('PGUSER'),
        password=os.environ.get('PGPASSWORD'),
    )


def get_db():
    """获取线程安全的数据库连接"""
    if get_db_provider() != 'postgres':
        raise RuntimeError("SQLite is no longer supported. Please use PostgreSQL (QUANT_DB_PROVIDER=postgres)")

    return PostgresCompatConnection(_connect_postgres())


def _quant_database() -> Database:
    """Open the pipeline Database for write-oriented data operations."""
    db_file = _project_root / '.pi-invest' / 'stock-db' / 'stocks.db'
    return Database(str(db_file))


@app.route('/api/health', methods=['GET'])
def health_check():
    """健康检查"""
    db_connected = False
    db_info = None

    try:
        if get_db_provider() == 'postgres':
            conn = get_db()
            row = conn.execute(
                "SELECT current_database(), pg_database_size(current_database())"
            ).fetchone()
            conn.close()

            size_bytes = int(row[1]) if row and row[1] is not None else 0
            size_mb = size_bytes / (1024 * 1024)
            db_connected = True
            db_info = {
                'provider': 'postgres',
                'database': row[0] if row else os.environ.get('PGDATABASE', 'quant_investment'),
                'size_mb': round(size_mb, 2),
                'size_display': f"{size_mb / 1024:.1f} GB" if size_mb >= 1024 else f"{size_mb:.1f} MB"
            }
            return jsonify({
                'status': 'ok',
                'model_loaded': model is not None,
                'db_connected': db_connected,
                'db_info': db_info
            })

        # Check if database file exists and is accessible
        # Note: We don't actually connect to avoid lock issues with concurrent processes
        if db_path.exists() and db_path.is_file():
            # Verify it's a valid SQLite database by checking the header
            with open(db_path, 'rb') as f:
                header = f.read(16)
                # SQLite files start with "SQLite format 3\x00"
                if header.startswith(b'SQLite format 3'):
                    db_connected = True

            # Get database file info
            size_bytes = db_path.stat().st_size
            size_mb = size_bytes / (1024 * 1024)

            # Format size display
            if size_mb < 1:
                size_display = f"{size_bytes / 1024:.1f} KB"
            elif size_mb < 1024:
                size_display = f"{size_mb:.1f} MB"
            else:
                size_display = f"{size_mb / 1024:.1f} GB"

            db_info = {
                'provider': 'sqlite',
                'path': str(db_path),
                'size_mb': round(size_mb, 2),
                'size_display': size_display
            }
    except Exception as e:
        import traceback
        print(f"Health check error: {e}", file=sys.stderr)
        traceback.print_exc()

    return jsonify({
        'status': 'ok',
        'model_loaded': model is not None,
        'db_connected': db_connected,
        'db_info': db_info
    })


@app.route('/api/strategies', methods=['GET'])
def list_strategies():
    return jsonify({'success': True, 'data': _list_strategies()})


@app.route('/api/strategies/<strategy_id>', methods=['GET'])
def get_strategy(strategy_id):
    strategy = _read_strategy(strategy_id)
    if strategy is None:
        return jsonify({'success': False, 'error': 'Strategy not found'}), 404
    return jsonify({'success': True, 'data': strategy})


@app.route('/api/strategies', methods=['POST'])
def create_strategy():
    data = request.get_json() or {}
    strategy = _write_strategy(data)
    return jsonify({'success': True, 'data': strategy}), 201


@app.route('/api/strategies/<strategy_id>', methods=['PUT'])
def update_strategy(strategy_id):
    existing = _read_strategy(strategy_id)
    if existing is None:
        return jsonify({'success': False, 'error': 'Strategy not found'}), 404
    updates = request.get_json() or {}
    updated = _write_strategy({**existing, **updates, 'id': strategy_id, 'created_at': existing['created_at']})
    return jsonify({'success': True, 'data': updated})


@app.route('/api/strategies/<strategy_id>', methods=['DELETE'])
def delete_strategy(strategy_id):
    path = _strategy_path(strategy_id)
    if not path.exists():
        return jsonify({'success': False, 'error': 'Strategy not found'}), 404
    path.unlink()
    return jsonify({'success': True, 'message': 'Strategy deleted'})


@app.route('/api/strategies/<strategy_id>/enable', methods=['POST'])
def enable_strategy(strategy_id):
    existing = _read_strategy(strategy_id)
    if existing is None:
        return jsonify({'success': False, 'error': 'Strategy not found'}), 404
    existing['enabled'] = True
    return jsonify({'success': True, 'data': _write_strategy(existing)})


@app.route('/api/strategies/<strategy_id>/disable', methods=['POST'])
def disable_strategy(strategy_id):
    existing = _read_strategy(strategy_id)
    if existing is None:
        return jsonify({'success': False, 'error': 'Strategy not found'}), 404
    existing['enabled'] = False
    return jsonify({'success': True, 'data': _write_strategy(existing)})


@app.route('/api/platform/status', methods=['GET'])
def platform_status():
    """返回 quant-web 运维总览需要的平台健康状态。"""
    try:
        signals_path = _project_root / 'quant' / '.pi-invest' / 'signals.json'
        model_report_path = _project_root / 'quant' / 'quantsys' / 'ml' / 'models' / 'training_report_latest.json'
        daily_report_path = _project_root / 'quant' / '.pi-invest' / 'daily_report.json'

        if get_db_provider() == 'postgres':
            try:
                conn = get_db()
                row = conn.execute("SELECT current_database(), pg_database_size(current_database())").fetchone()
                conn.close()
                size_bytes = int(row[1]) if row and row[1] is not None else 0
                size_mb = size_bytes / (1024 * 1024)
                database_check = {
                    'name': 'database',
                    'status': 'healthy',
                    'message': 'PostgreSQL database is connected.',
                    'details': {
                        'provider': 'postgres',
                        'database': row[0] if row else os.environ.get('PGDATABASE', 'quant_investment'),
                        'size_mb': round(size_mb, 2),
                        'size_display': f"{size_mb / 1024:.1f} GB" if size_mb >= 1024 else f"{size_mb:.1f} MB",
                        'exists': True,
                    },
                }
            except Exception as db_error:
                database_check = {
                    'name': 'database',
                    'status': 'unavailable',
                    'message': 'PostgreSQL database is not connected.',
                    'details': {
                        'provider': 'postgres',
                        'database': os.environ.get('PGDATABASE', 'quant_investment'),
                        'error': str(db_error),
                        'exists': False,
                    },
                }
        else:
            database_path = _project_root / '.pi-invest' / 'stock-db' / 'stocks.db'
            database_check = _status_check(
                'database',
                database_path,
                'SQLite stock database is present.',
                'SQLite stock database was not found.',
                {'provider': 'sqlite'},
            )

        checks = [
            database_check,
            _status_check(
                'signals',
                signals_path,
                'Fallback signals file was found.',
                'No signal files were found.',
                {'source': 'signals_fallback'},
            ),
            _status_check(
                'model',
                model_report_path,
                'Model freshness artifact is present.',
                'Model freshness artifact was not found.',
                {'source': 'training_report'},
            ),
            _status_check(
                'daily_report',
                daily_report_path,
                'Daily report JSON was found.',
                'Daily report JSON was not found.',
                {'source': 'daily_report_json'},
            ),
        ]

        if checks[0]['status'] == 'unavailable':
            overall_status = 'unavailable'
        elif all(check['status'] == 'healthy' for check in checks):
            overall_status = 'healthy'
        else:
            overall_status = 'degraded'

        return jsonify({
            'success': True,
            'data': {
                'overall_status': overall_status,
                'generated_at': datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
                'checks': checks,
            },
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/feature-importance', methods=['GET'])
def get_feature_importance():
    """获取因子重要性"""
    try:
        if model is None:
            return jsonify({'error': '模型未加载'}), 500

        # 获取模型路径（优先使用新模型）
        model_path = None
        for path in [
            Path(__file__).parent.parent / 'quantsys' / 'ml' / 'models' / 'xgboost_latest.pkl',
            Path(__file__).parent.parent.parent / '.pi-invest' / 'quant' / 'models' / 'signal_confidence.pkl',
        ]:
            if path.exists():
                model_path = str(path)
                break

        df = analyze_feature_importance(model, model_path)

        # 转换为前端期望的格式（小写字段名）
        features = []
        for _, row in df.iterrows():
            features.append({
                'feature': row['Feature'],
                'importance': float(row['Importance']),
                'percentage': float(row['Percentage']) if row['Percentage'] is not None else 0.0,
                'cumulative': float(row['Cumulative']) if row['Cumulative'] is not None else 0.0
            })

        return jsonify({
            'features': features,
            'total_features': len(df),
            'top_20_percent_count': len(df[df['Cumulative'] <= 80]) if 'Cumulative' in df.columns else 0
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


def _analyze_stock_factors(symbol, date=None):
    """核心逻辑：分析股票因子（内部函数，不是路由）"""
    if model is None:
        raise ValueError('模型未加载')

    conn = get_db()

    # 获取最新日期
    if date is None:
        cursor = conn.execute(
            "SELECT MAX(date) FROM daily_klines WHERE symbol = ?",
            (symbol,)
        )
        date = cursor.fetchone()[0]
        if not date:
            conn.close()
            raise ValueError(f'未找到股票 {symbol} 的数据')

    # 获取K线数据
    cursor = conn.execute("""
        SELECT open, high, low, close, volume, amount, turnover_rate
        FROM daily_klines
        WHERE symbol = ? AND date = ?
    """, (symbol, date))

    kline = cursor.fetchone()
    if not kline:
        conn.close()
        raise ValueError('未找到价格数据')

    # 获取因子数据
    cursor = conn.execute("""
        SELECT factor_name, factor_value
        FROM factor_values
        WHERE symbol = ? AND date = ?
    """, (symbol, date))

    factors = {}
    for row in cursor.fetchall():
        factors[row[0]] = row[1]

    conn.close()

    # 从训练报告读取特征顺序（使用与加载模型匹配的报告）
    import json
    report_path = Path(__file__).parent.parent / 'quantsys' / 'ml' / 'models' / 'training_report_20260519_112515.json'
    with open(report_path) as f:
        report = json.load(f)
        feature_names = report['feature_names']

    # 构建特征字典（K线数据 + 因子），处理None值
    all_features = {
        'open': kline[0] if kline[0] is not None else 0.0,
        'high': kline[1] if kline[1] is not None else 0.0,
        'low': kline[2] if kline[2] is not None else 0.0,
        'close': kline[3] if kline[3] is not None else 0.0,
        'volume': kline[4] if kline[4] is not None else 0.0,
        'amount': kline[5] if kline[5] is not None else 0.0,
        'turnover_rate': kline[6] if kline[6] is not None else 0.0,
        **factors
    }

    # 按训练时的顺序构建特征数组
    features = []
    missing_features = []
    for name in feature_names:
        value = all_features.get(name, None)
        if value is None or (isinstance(value, float) and np.isnan(value)):
            missing_features.append(name)
            features.append(0.0)
        else:
            features.append(float(value))

    # 预测
    X = np.array(features).reshape(1, -1)
    if hasattr(model, 'predict_proba'):
        proba = model.predict_proba(X)[0]
        up_prob = float(proba[1])
    else:
        up_prob = float(model.predict(X)[0])

    # 计算因子贡献
    if hasattr(model, 'feature_importances_'):
        importances = model.feature_importances_
        contributions = np.array(features) * importances

        key_factors = []
        for i, name in enumerate(feature_names):
            key_factors.append({
                'name': name,
                'value': float(features[i]),
                'importance': float(importances[i]),
                'contribution': float(contributions[i])
            })

        # 按贡献排序
        key_factors.sort(key=lambda x: abs(x['contribution']), reverse=True)
    else:
        key_factors = []

    return {
        'symbol': symbol,
        'date': date,
        'price': float(kline[3]),
        'prediction': {
            'up_probability': up_prob,
            'direction': 'UP' if up_prob > 0.5 else 'DOWN',
            'confidence': abs(up_prob - 0.5) * 2
        },
        'key_factors': key_factors[:10],
        'factors': {k: float(v) if not (isinstance(v, float) and np.isnan(v)) else 0.0
                   for k, v in all_features.items()},
        'missing_features': missing_features if missing_features else None
    }


@app.route('/api/stock/<symbol>/factors', methods=['GET'])
@app.route('/api/stocks/<symbol>/factors', methods=['GET'])
def get_stock_factors(symbol):
    """获取股票因子分析"""
    try:
        date = request.args.get('date')
        result = _analyze_stock_factors(symbol, date)
        return jsonify(result)
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/api/stocks/compare', methods=['POST'])
def compare_stocks():
    """对比多只股票"""
    try:
        data = request.get_json()
        symbols = data.get('symbols', [])
        date = data.get('date')

        if not symbols:
            return jsonify({'error': '请提供股票代码'}), 400

        if len(symbols) > 5:
            return jsonify({'error': '最多对比5只股票'}), 400

        results = []
        for symbol in symbols:
            try:
                # 直接调用核心分析函数（已返回正确格式）
                result = _analyze_stock_factors(symbol, date)
                results.append(result)
            except Exception as e:
                print(f"Failed to analyze {symbol}: {e}")
                import traceback
                traceback.print_exc()
                continue

        # 按上涨概率排序
        results.sort(key=lambda x: x['prediction']['up_probability'], reverse=True)

        return jsonify({
            'comparisons': results,
            'count': len(results)
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/api/signals', methods=['GET'])
def get_signals():
    """获取交易信号 - 优先从数据库读取，JSON作为fallback"""
    try:
        date = request.args.get('date')
        signal_type = request.args.get('signal_type')
        min_confidence = request.args.get('min_confidence', type=float, default=0.0)
        strategy_name = request.args.get('strategy_name')

        # 尝试从数据库读取
        try:
            db = _quant_database()
            if db and db.provider == 'postgres':
                signals = db.get_trading_signals(
                    date=date,
                    signal_type=signal_type,
                    min_confidence=min_confidence,
                    strategy_name=strategy_name
                )
                return jsonify({
                    'signals': signals,
                    'count': len(signals),
                    'date': date or (signals[0]['date'] if signals else ''),
                    'source': 'database'
                })
        except Exception as db_error:
            logger.warning(f"Database read failed, falling back to JSON: {db_error}")

        # Fallback: 读取信号文件
        signals_path = Path(__file__).parent.parent / '.pi-invest' / 'signals.json'

        if not signals_path.exists():
            return jsonify({'signals': [], 'count': 0, 'source': 'json'})

        import json
        with open(signals_path, 'r') as f:
            data = json.load(f)
            signals = data.get('signals', [])
            if not isinstance(signals, list):
                signals = []

        # 过滤日期/信号类型/置信度
        if date:
            signals = [s for s in signals if s.get('date') == date]
        if signal_type:
            signals = [s for s in signals if s.get('signal') == signal_type]
        if min_confidence:
            signals = [s for s in signals if s.get('confidence', 0) >= min_confidence]
        if strategy_name:
            signals = [s for s in signals if s.get('strategy') == strategy_name]

        return jsonify({
            'signals': signals,
            'count': len(signals),
            'date': data.get('date', ''),
            'source': 'json'
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/signals/history', methods=['GET'])
def get_signals_history():
    """旧 dashboard 兼容：返回规范化信号数组。"""
    try:
        return jsonify({'success': True, 'data': _load_dashboard_signals()})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/signals/scan', methods=['POST'])
def scan_signals():
    """旧 dashboard 兼容：对传入股票返回 hold 占位信号。"""
    data = request.get_json() or {}
    stocks = data.get('stocks') or []
    if not isinstance(stocks, list):
        return jsonify({'success': False, 'error': 'Missing required parameters: strategy_id, stocks (array)'}), 400

    strategy_id = data.get('strategy_id', '')
    signals = [
        {
            'symbol': stock.get('symbol', ''),
            'name': stock.get('name', ''),
            'signal': 'hold',
            'confidence': 0.0,
            'strategy_id': strategy_id,
            'strategy_name': strategy_id,
            'reasons': ['兼容接口未执行实时扫描'],
            'price': 0.0,
            'timestamp': datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
        }
        for stock in stocks
    ]
    return jsonify({'success': True, 'data': signals})


@app.route('/api/stock/<symbol>/klines', methods=['GET'])
def get_stock_klines(symbol):
    """获取K线数据（兼容 quant_api.py 格式）"""
    try:
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        limit = request.args.get('limit', type=int, default=100)

        klines = _get_klines_raw(symbol, limit=limit, start_date=start_date, end_date=end_date)

        if not klines:
            return jsonify({'error': f'No kline data for {symbol}'}), 404

        return jsonify({
            'symbol': symbol,
            'count': len(klines),
            'klines': klines
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500


def _get_klines_raw(symbol, limit=100, start_date=None, end_date=None):
    """内部辅助：获取K线原始数据"""
    conn = get_db()
    query = """
        SELECT date, open, high, low, close, volume, amount
        FROM daily_klines
        WHERE symbol = ?
    """
    params = [symbol]
    if start_date:
        query += " AND date >= ?"
        params.append(start_date)
    if end_date:
        query += " AND date <= ?"
        params.append(end_date)
    query += " ORDER BY date DESC"
    if limit:
        query += f" LIMIT {limit}"

    cursor = conn.execute(query, params)
    rows = cursor.fetchall()
    conn.close()

    klines = []
    for row in rows:
        klines.append({
            'date': row[0],
            'open': float(row[1]) if row[1] is not None else 0.0,
            'high': float(row[2]) if row[2] is not None else 0.0,
            'low': float(row[3]) if row[3] is not None else 0.0,
            'close': float(row[4]) if row[4] is not None else 0.0,
            'volume': float(row[5]) if row[5] is not None else 0.0,
            'amount': float(row[6]) if row[6] is not None else 0.0
        })
    klines.sort(key=lambda x: x['date'])
    return klines


@app.route('/api/stock/<symbol>/technical', methods=['GET'])
def get_technical_indicators(symbol):
    """计算技术指标（兼容 quant_api.py 格式）"""
    try:
        indicators_param = request.args.get('indicators')
        indicators_list = indicators_param.split(',') if indicators_param else None

        klines = _get_klines_raw(symbol, limit=100)

        if not klines:
            return jsonify({'error': f'No kline data for {symbol}'}), 404

        if len(klines) < 20:
            return jsonify({'error': f'Insufficient data for {symbol} (need 20+ days, got {len(klines)})'}), 400

        # 转换为 pandas DataFrame
        import pandas as pd
        df = pd.DataFrame(klines)
        df['date'] = pd.to_datetime(df['date'], format='mixed')
        df = df.sort_values('date')

        result_indicators = {}

        # RSI
        if not indicators_list or 'RSI' in indicators_list:
            delta = df['close'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
            rs = gain / loss
            rsi = 100 - (100 / (1 + rs))
            result_indicators['RSI'] = float(rsi.iloc[-1]) if not pd.isna(rsi.iloc[-1]) else None

        # MA5, MA10, MA20, MA60
        for period in [5, 10, 20, 60]:
            key = f'MA{period}'
            if not indicators_list or key in indicators_list:
                ma = df['close'].rolling(window=period).mean()
                result_indicators[key] = float(ma.iloc[-1]) if not pd.isna(ma.iloc[-1]) else None

        # MACD
        if not indicators_list or 'MACD' in indicators_list or 'MACD_DIF' in indicators_list:
            exp1 = df['close'].ewm(span=12, adjust=False).mean()
            exp2 = df['close'].ewm(span=26, adjust=False).mean()
            macd_dif = exp1 - exp2
            macd_dea = macd_dif.ewm(span=9, adjust=False).mean()
            macd_histogram = macd_dif - macd_dea

            result_indicators['MACD_DIF'] = float(macd_dif.iloc[-1]) if not pd.isna(macd_dif.iloc[-1]) else None
            result_indicators['MACD_DEA'] = float(macd_dea.iloc[-1]) if not pd.isna(macd_dea.iloc[-1]) else None
            result_indicators['MACD'] = float(macd_histogram.iloc[-1]) if not pd.isna(macd_histogram.iloc[-1]) else None

        # 计算当前价格
        current_price = float(df['close'].iloc[-1])

        return jsonify({
            'symbol': symbol,
            'date': klines[-1]['date'],
            'price': current_price,
            'indicators': result_indicators
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/api/stocks/list', methods=['GET'])
def get_stock_list():
    """获取股票列表（兼容 quant_api.py 格式，支持分页）"""
    try:
        # 验证分页参数
        page, page_size = _validate_pagination_params(
            request.args.get('page', type=int, default=1),
            request.args.get('pageSize', type=int, default=10)
        )

        market = request.args.get('market')
        industry = request.args.get('industry')
        keyword = request.args.get('keyword')
        has_data = request.args.get('has_data', type=bool, default=False)

        conn = get_db()

        if has_data:
            data_query = """
                SELECT DISTINCT s.symbol, s.name, s.market, s.industry
                FROM stocks s
                INNER JOIN daily_klines k ON s.symbol = k.symbol
            """
            count_query = """
                SELECT COUNT(DISTINCT s.symbol)
                FROM stocks s
                INNER JOIN daily_klines k ON s.symbol = k.symbol
            """
            conditions = []
            filter_params = []
            if market:
                conditions.append("s.market = ?")
                filter_params.append(market)
            if industry:
                conditions.append("s.industry = ?")
                filter_params.append(industry)
            if keyword:
                conditions.append("(LOWER(s.symbol) LIKE LOWER(?) OR LOWER(s.name) LIKE LOWER(?))")
                filter_params.extend([f"%{keyword}%", f"%{keyword}%"])
            filter_clause = (" WHERE " + " AND ".join(conditions)) if conditions else ""
            order_clause = " ORDER BY s.symbol"
        else:
            data_query = "SELECT symbol, name, market, industry FROM stocks"
            count_query = "SELECT COUNT(*) FROM stocks"
            conditions = []
            filter_params = []
            if market:
                conditions.append("market = ?")
                filter_params.append(market)
            if industry:
                conditions.append("industry = ?")
                filter_params.append(industry)
            if keyword:
                conditions.append("(LOWER(symbol) LIKE LOWER(?) OR LOWER(name) LIKE LOWER(?))")
                filter_params.extend([f"%{keyword}%", f"%{keyword}%"])
            filter_clause = (" WHERE " + " AND ".join(conditions)) if conditions else ""
            order_clause = " ORDER BY symbol"

        # 获取总数
        total = conn.execute(
            count_query + filter_clause, filter_params
        ).fetchone()[0]

        # 构建并执行分页查询
        full_query = data_query + filter_clause + order_clause
        paginated_query, paginated_params = _paginate_query(
            full_query, filter_params, page, page_size
        )
        cursor = conn.execute(paginated_query, paginated_params)
        rows = cursor.fetchall()
        conn.close()

        stocks = []
        for row in rows:
            stocks.append({
                'symbol': row[0],
                'name': row[1],
                'market': row[2],
                'industry': row[3] or ''
            })

        return jsonify(_build_paginated_response(
            stocks, page, page_size, total, items_key='stocks'
        ))

    except ValueError as e:
        return jsonify({'success': False, 'error': str(e)}), 400
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/report/daily', methods=['GET'])
def get_daily_report():
    """获取每日报告（兼容 quant_api.py 格式）"""
    try:
        date = request.args.get('date')

        # 读取报告文件
        reports_dir = Path(__file__).parent.parent.parent / '.pi-invest' / 'reports'

        if date:
            report_file = Path(__file__).parent.parent.parent / '.pi-invest' / f'daily_report_{date}.json'
        else:
            report_file = Path(__file__).parent.parent.parent / '.pi-invest' / 'daily_report.json'

        if not report_file.exists():
            # 尝试从 .pi-invest/reports/ 查找
            if date:
                alt_file = reports_dir / f'{date}-review.md'
            else:
                # 找最新的报告
                md_files = sorted(reports_dir.glob('*-review.md'), reverse=True)
                alt_file = md_files[0] if md_files else None

            if alt_file and alt_file.exists():
                with open(alt_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                return jsonify({
                    'date': alt_file.stem.replace('-review', ''),
                    'report': {'content': content, 'format': 'markdown'}
                })

            return jsonify({'error': 'Daily report not found'}), 404

        with open(report_file, 'r', encoding='utf-8') as f:
            report = json.load(f)

        return jsonify(report)

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/stock/<symbol>/ml-predict', methods=['GET'])
def get_ml_prediction(symbol):
    """获取ML预测（供 predict_stock_ml 工具使用）"""
    try:
        if model is None:
            return jsonify({'error': '模型未加载'}), 500

        conn = get_db()

        # 获取最新日期
        cursor = conn.execute(
            "SELECT MAX(date) FROM factor_values WHERE symbol = ?",
            (symbol,)
        )
        row = cursor.fetchone()
        date = row[0] if row else None
        if not date:
            conn.close()
            return jsonify({'error': f'未找到股票 {symbol} 的数据'}), 404

        # 获取因子值
        cursor = conn.execute("""
            SELECT factor_name, factor_value
            FROM factor_values
            WHERE symbol = ? AND date = ?
        """, (symbol, date))
        factors = {row[0]: row[1] for row in cursor.fetchall()}

        # 获取价格数据（优先用因子日期，fallback 到最近有K线的日期）
        cursor = conn.execute("""
            SELECT open, high, low, close, volume, amount, turnover_rate
            FROM daily_klines
            WHERE symbol = ? AND date = ?
        """, (symbol, date))
        row = cursor.fetchone()
        
        # 如果因子日期没有K线，fallback到最近有K线的日期
        if not row:
            cursor = conn.execute("""
                SELECT open, high, low, close, volume, amount, turnover_rate
                FROM daily_klines
                WHERE symbol = ?
                ORDER BY date DESC LIMIT 1
            """, (symbol,))
            row = cursor.fetchone()
        
        conn.close()

        if not row:
            return jsonify({'error': '未找到价格数据'}), 404

        feature_dict = {
            'open': row[0], 'high': row[1], 'low': row[2],
            'close': row[3], 'volume': row[4], 'amount': row[5],
            'turnover_rate': row[6]
        }
        feature_dict.update(factors)

        # 从训练报告读取特征顺序
        import json
        report_path = Path(__file__).parent.parent / 'quantsys' / 'ml' / 'models' / 'training_report_latest.json'
        if not report_path.exists():
            # Try fallback path
            report_path = Path(__file__).parent.parent / 'quantsys' / 'ml' / 'models' / 'training_report.json'
        if not report_path.exists():
            return jsonify({'error': '训练报告文件不存在，请先训练模型'}), 500

        with open(report_path) as f:
            report = json.load(f)
            feature_names = report['feature_names']

        # 按训练顺序构建特征数组
        features = []
        for name in feature_names:
            value = feature_dict.get(name, None)
            features.append(float(value) if value is not None else 0.0)

        # ML预测
        X = np.array(features).reshape(1, -1)
        if hasattr(model, 'predict_proba'):
            proba = model.predict_proba(X)[0]
            up_prob = float(proba[1])
        else:
            up_prob = float(model.predict(X)[0])

        # 因子贡献
        key_factors = []
        if hasattr(model, 'feature_importances_'):
            importances = model.feature_importances_
            contributions = np.array(features) * importances
            for i, name in enumerate(feature_names):
                key_factors.append({
                    'name': name,
                    'value': float(features[i]),
                    'importance': float(importances[i]),
                    'contribution': float(contributions[i])
                })
            key_factors.sort(key=lambda x: abs(x['contribution']), reverse=True)

        return jsonify({
            'symbol': symbol,
            'date': date,
            'price': feature_dict['close'],
            'prediction': {
                'up_probability': up_prob,
                'direction': 'UP' if up_prob > 0.5 else 'DOWN',
                'confidence': abs(up_prob - 0.5) * 2
            },
            'key_factors': key_factors[:5]
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/api/backtest/results', methods=['GET'])
def get_backtest_results():
    """获取回测结果"""
    try:
        import json
        import glob

        symbol = request.args.get('symbol')
        date = request.args.get('date')

        backtest_dir = Path(__file__).parent.parent / '.pi-invest'

        if symbol and date:
            # 获取特定股票特定日期的回测结果
            report_file = backtest_dir / f'backtest_report_{symbol}_{date}.json'
            if not report_file.exists():
                return jsonify({'error': f'未找到回测报告: {symbol} {date}'}), 404

            with open(report_file, 'r') as f:
                report = json.load(f)
            return jsonify(report)

        elif symbol:
            # 获取特定股票的所有回测结果
            pattern = str(backtest_dir / f'backtest_report_{symbol}_*.json')
            files = glob.glob(pattern)

            reports = []
            for file in sorted(files, reverse=True):
                with open(file, 'r') as f:
                    reports.append(json.load(f))

            return jsonify({
                'symbol': symbol,
                'count': len(reports),
                'reports': reports
            })

        else:
            # 获取所有回测结果的汇总
            pattern = str(backtest_dir / 'backtest_report_*_*.json')
            files = glob.glob(pattern)

            if not files:
                # 没有回测报告，返回空列表
                return jsonify({
                    'count': 0,
                    'summary': []
                })

            summary = []
            for file in files:
                with open(file, 'r') as f:
                    report = json.load(f)
                    # 提取关键信息
                    best_strategy = max(report['results'], key=lambda x: x.get('total_return', -999))
                    summary.append({
                        'symbol': report['symbol'],
                        'date': report['report_date'],
                        'best_strategy': best_strategy['strategy_name'],
                        'best_return': best_strategy['total_return'],
                        'sharpe_ratio': best_strategy['sharpe_ratio'],
                        'max_drawdown': best_strategy['max_drawdown'],
                        'win_rate': best_strategy['win_rate']
                    })

            # 按收益率排序
            summary.sort(key=lambda x: x['best_return'], reverse=True)

            return jsonify({
                'count': len(summary),
                'summary': summary
            })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/api/backtest', methods=['POST'])
def run_dashboard_backtest():
    """旧 dashboard 兼容：同步返回可展示回测结构。"""
    data = request.get_json() or {}
    strategy_id = data.get('strategy_id')
    start_date = data.get('start_date')
    end_date = data.get('end_date')
    initial_capital = float(data.get('initial_capital') or 100000)

    if not strategy_id or not start_date or not end_date:
        return jsonify({'success': False, 'error': 'Missing required parameters: strategy_id, start_date, end_date'}), 400
    if _read_strategy(strategy_id) is None:
        return jsonify({'success': False, 'error': 'Strategy not found'}), 404

    return jsonify({'success': True, 'data': _default_backtest_result(initial_capital, start_date, end_date)})


@app.route('/api/performance/strategy/<strategy_id>', methods=['GET'])
def get_strategy_performance(strategy_id):
    days = request.args.get('days', default=30, type=int)
    if _read_strategy(strategy_id) is None:
        return jsonify({'success': False, 'error': 'Strategy not found'}), 404
    return jsonify({'success': True, 'data': _performance_for_strategy(strategy_id, days)})


@app.route('/api/performance/compare', methods=['GET'])
@app.route('/api/performance/comparison', methods=['GET'])
def compare_strategy_performance():
    days = request.args.get('days', default=30, type=int)
    raw_ids = request.args.get('strategy_ids')
    if raw_ids:
        strategy_ids = [item for item in raw_ids.split(',') if item]
    else:
        strategy_ids = [strategy['id'] for strategy in _list_strategies()]
    return jsonify({
        'success': True,
        'data': [_performance_for_strategy(strategy_id, days) for strategy_id in strategy_ids],
    })


@app.route('/api/training/history', methods=['GET'])
def get_training_history():
    """获取训练历史"""
    try:
        models_dir = Path(__file__).parent.parent / 'quantsys' / 'ml' / 'models'

        import glob
        import json
        pattern = str(models_dir / 'training_report_*.json')
        files = glob.glob(pattern)

        # 排除 latest 文件
        files = [f for f in files if 'latest' not in f]

        history = []
        for file in sorted(files, reverse=True):
            with open(file, 'r') as f:
                report = json.load(f)
                history.append({
                    'timestamp': report['timestamp'],
                    'model_type': report['model_type'],
                    'n_features': report['data']['n_features'],
                    'total_samples': report['data']['total_samples'],
                    'cv_accuracy': report['cv_results']['mean_scores']['accuracy'],
                    'cv_auc': report['cv_results']['mean_scores']['auc'],
                    'test_accuracy': report['test_metrics']['accuracy'],
                    'test_auc': report['test_metrics']['auc'],
                    'class_balance': report['data']['class_balance']
                })

        return jsonify({
            'count': len(history),
            'history': history
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/api/training/reports', methods=['GET'])
def get_training_reports():
    """获取历史训练报告列表（quant-web 兼容）。"""
    try:
        reports = []
        for path in _iter_training_report_files()[:20]:
            report = _load_json_file(path)
            timestamp = path.name.replace('training_report_', '').replace('.json', '')
            reports.append({
                'filename': path.name,
                'timestamp': timestamp,
                'metrics': report.get('metrics') or report.get('test_metrics'),
                'params': report.get('params'),
                'n_features': _report_n_features(report),
            })
        return jsonify({'success': True, 'data': reports})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/training/report/<filename>', methods=['GET'])
def get_training_report(filename):
    """获取单个训练报告详情。"""
    try:
        if '..' in filename or '/' in filename or '\\' in filename:
            return jsonify({'success': False, 'error': 'Invalid filename'}), 400

        report_path = _models_dir() / filename
        if not report_path.exists() or not report_path.is_file():
            return jsonify({'success': False, 'error': 'Report not found'}), 404

        return jsonify({'success': True, 'data': _load_json_file(report_path)})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/training/start', methods=['POST'])
def start_training():
    """启动模型训练任务（quant-web 兼容）。"""
    data = request.get_json() or {}
    days = int(data.get('days', 90))
    model = data.get('model', 'xgboost')
    cv_splits = int(data.get('cvSplits', 5))

    if days < 30 or days > 365:
        return jsonify({'success': False, 'error': 'days must be between 30 and 365'}), 400
    if model not in {'xgboost', 'lightgbm', 'random_forest', 'randomforest'}:
        return jsonify({'success': False, 'error': 'model must be one of: xgboost, lightgbm, random_forest'}), 400
    if cv_splits < 2 or cv_splits > 10:
        return jsonify({'success': False, 'error': 'cvSplits must be between 2 and 10'}), 400

    params = {
        'days': days,
        'model': model,
        'cvSplits': cv_splits,
        'useFeatureEngineering': data.get('useFeatureEngineering', True),
    }
    job_id = _start_job_for_type('model_train', params)
    return jsonify({
        'success': True,
        'data': {
            'taskId': job_id,
            'status': 'running',
            'message': 'Training started successfully',
        },
    }), 202


@app.route('/api/training/status/<task_id>', methods=['GET'])
def get_training_status(task_id):
    """查询训练任务状态。"""
    job = _get_job(task_id)
    if job is None:
        return jsonify({'success': False, 'error': 'Training task not found'}), 404
    return jsonify({'success': True, 'data': _training_status_from_job(job)})


@app.route('/api/training/logs/<task_id>', methods=['GET'])
def get_training_logs(task_id):
    """获取训练任务日志。"""
    job = _get_job(task_id)
    if job is None:
        return jsonify({'success': False, 'error': 'Training task not found'}), 404
    return jsonify({'success': True, 'data': {'taskId': task_id, 'logs': job.get('logs') or []}})


@app.route('/api/charts/accuracy', methods=['GET'])
def get_accuracy_chart():
    return jsonify({'success': True, 'data': _chart_response('accuracy_trend')})


@app.route('/api/charts/importance', methods=['GET'])
def get_importance_chart():
    return jsonify({'success': True, 'data': _chart_response('feature_importance')})


@app.route('/api/charts/equity', methods=['GET'])
def get_equity_chart():
    return jsonify({'success': True, 'data': _chart_response('equity_curve')})


@app.route('/api/charts/comparison', methods=['GET'])
def get_comparison_chart():
    return jsonify({'success': True, 'data': _chart_response('strategy_comparison')})


@app.route('/api/charts/image/<chart_type>', methods=['GET'])
def get_chart_image(chart_type):
    valid_types = {'accuracy_trend', 'equity_curve', 'strategy_comparison', 'feature_importance'}
    if chart_type not in valid_types:
        return jsonify({'success': False, 'error': f'Invalid chart type: {chart_type}'}), 400
    chart_path = Path(_chart_response(chart_type)['chart_path'])
    return app.response_class(chart_path.read_bytes(), mimetype='image/png')


@app.route('/api/stocks/data-status', methods=['GET'])
def get_stocks_data_status():
    """获取所有股票的数据状态（支持分页）"""
    try:
        # 分页参数
        page = request.args.get('page', 1, type=int)
        page_size = request.args.get('pageSize', 20, type=int)

        # 限制 page_size 范围
        page_size = max(1, min(page_size, 1000))
        page = max(1, page)

        offset = (page - 1) * page_size

        conn = get_db()

        # 优化策略：使用预计算的 stock_data_summary 表
        # 从 25秒 优化到 0.01秒（2500x 加速）

        # 先获取总数和统计
        cursor = conn.execute("""
            SELECT
                COUNT(*) as total,
                COUNT(CASE WHEN s.kline_days > 0 AND s.factor_days > 0 AND s.factor_count >= 30 THEN 1 END) as complete
            FROM stock_data_summary s
            WHERE s.factor_count >= 30
        """)
        stats = cursor.fetchone()
        total_stocks = stats[0]
        complete_stocks = stats[1]

        # 获取分页数据
        if get_db_provider() == 'postgres':
            query = """
                SELECT
                    s.symbol,
                    st.name,
                    st.market,
                    s.kline_days,
                    s.earliest_date,
                    s.latest_date,
                    s.factor_days,
                    s.factor_count
                FROM stock_data_summary s
                JOIN stocks st ON s.symbol = st.symbol
                WHERE s.factor_count >= 30
                ORDER BY s.symbol
                LIMIT %s OFFSET %s
            """
            cursor = conn.execute(query, (page_size, offset))
        else:
            query = """
                SELECT
                    s.symbol,
                    st.name,
                    st.market,
                    s.kline_days,
                    s.earliest_date,
                    s.latest_date,
                    s.factor_days,
                    s.factor_count
                FROM stock_data_summary s
                JOIN stocks st ON s.symbol = st.symbol
                WHERE s.factor_count >= 30
                ORDER BY s.symbol
                LIMIT ? OFFSET ?
            """
            cursor = conn.execute(query, (page_size, offset))

        rows = cursor.fetchall()
        conn.close()

        stocks = []
        for row in rows:
            stocks.append({
                'symbol': row[0],
                'name': row[1],
                'market': row[2],
                'kline_days': row[3] or 0,
                'earliest_date': row[4],
                'latest_date': row[5],
                'factor_days': row[6] or 0,
                'factor_count': row[7] or 0,
                'data_complete': (row[3] or 0) > 0 and (row[6] or 0) > 0 and (row[7] or 0) >= 30
            })

        return jsonify({
            'total_stocks': total_stocks,
            'complete_stocks': complete_stocks,
            'incomplete_stocks': total_stocks - complete_stocks,
            'stocks': stocks,
            'pagination': {
                'page': page,
                'pageSize': page_size,
                'total': total_stocks
            }
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/api/stocks/search', methods=['GET'])
def search_stocks():
    """搜索股票（支持代码和名称模糊匹配）"""
    # 获取搜索参数
    query = request.args.get('q', '').strip()
    page = request.args.get('page', 1, type=int)
    page_size = request.args.get('pageSize', 20, type=int)

    # 参数验证
    if not query:
        return jsonify({'error': '搜索关键词不能为空'}), 400

    page_size = max(1, min(page_size, 100))
    page = max(1, page)
    offset = (page - 1) * page_size

    conn = get_db()
    try:
        # 先获取总数
        if get_db_provider() == 'postgres':
            count_query = """
                SELECT COUNT(*) as total
                FROM stock_data_summary s
                JOIN stocks st ON s.symbol = st.symbol
                WHERE (s.symbol ILIKE %s OR st.name ILIKE %s)
                  AND s.factor_count >= 30
            """
            search_pattern = f'%{query}%'
            cursor = conn.execute(count_query, (search_pattern, search_pattern))
        else:
            count_query = """
                SELECT COUNT(*) as total
                FROM stock_data_summary s
                JOIN stocks st ON s.symbol = st.symbol
                WHERE (s.symbol LIKE ? OR st.name LIKE ?)
                  AND s.factor_count >= 30
            """
            search_pattern = f'%{query}%'
            cursor = conn.execute(count_query, (search_pattern, search_pattern))

        total = cursor.fetchone()[0]

        # 获取分页数据
        if get_db_provider() == 'postgres':
            data_query = """
                SELECT
                    s.symbol,
                    st.name,
                    st.market,
                    s.kline_days,
                    s.earliest_date,
                    s.latest_date,
                    s.factor_days,
                    s.factor_count,
                    CASE
                        WHEN s.kline_days > 0 AND s.factor_days > 0 AND s.factor_count >= 30
                        THEN true
                        ELSE false
                    END as data_complete
                FROM stock_data_summary s
                JOIN stocks st ON s.symbol = st.symbol
                WHERE (s.symbol ILIKE %s OR st.name ILIKE %s)
                  AND s.factor_count >= 30
                ORDER BY s.symbol
                LIMIT %s OFFSET %s
            """
            cursor = conn.execute(data_query, (search_pattern, search_pattern, page_size, offset))
        else:
            data_query = """
                SELECT
                    s.symbol,
                    st.name,
                    st.market,
                    s.kline_days,
                    s.earliest_date,
                    s.latest_date,
                    s.factor_days,
                    s.factor_count,
                    CASE
                        WHEN s.kline_days > 0 AND s.factor_days > 0 AND s.factor_count >= 30
                        THEN 1
                        ELSE 0
                    END as data_complete
                FROM stock_data_summary s
                JOIN stocks st ON s.symbol = st.symbol
                WHERE (s.symbol LIKE ? OR st.name LIKE ?)
                  AND s.factor_count >= 30
                ORDER BY s.symbol
                LIMIT ? OFFSET ?
            """
            cursor = conn.execute(data_query, (search_pattern, search_pattern, page_size, offset))

        rows = cursor.fetchall()

        # 转换为字典列表
        stocks = []
        for row in rows:
            stocks.append({
                'symbol': row[0],
                'name': row[1],
                'market': row[2],
                'kline_days': row[3],
                'earliest_date': row[4],
                'latest_date': row[5],
                'factor_days': row[6],
                'factor_count': row[7],
                'data_complete': bool(row[8])
            })

        return jsonify({
            'total': total,
            'page': page,
            'pageSize': page_size,
            'stocks': stocks
        })

    except Exception as e:
        logger.error(f'搜索股票失败: {e}')
        return jsonify({'error': '搜索失败', 'message': str(e)}), 500
    finally:
        conn.close()


@app.route('/api/stocks/my-stocks', methods=['GET'])
def get_my_stocks():
    """获取用户的持仓和自选股"""
    conn = None
    try:
        conn = get_db()

        # Detect database provider
        provider = get_db_provider()

        # Query positions (quantity > 0) with JOIN to stocks table
        if provider == 'postgres':
            positions_query = """
                SELECT p.symbol, s.name
                FROM quant.positions p
                JOIN quant.stocks s ON p.symbol = s.symbol
                WHERE p.quantity > 0
                ORDER BY p.symbol
            """
        else:
            positions_query = """
                SELECT p.symbol, s.name
                FROM positions p
                JOIN stocks s ON p.symbol = s.symbol
                WHERE p.quantity > 0
                ORDER BY p.symbol
            """

        positions_cursor = conn.execute(positions_query)
        positions_rows = positions_cursor.fetchall()

        positions = [
            {'symbol': row[0], 'name': row[1]}
            for row in positions_rows
        ]

        # Query watchlist with JOIN to stocks table
        if provider == 'postgres':
            watchlist_query = """
                SELECT w.symbol, s.name
                FROM quant.watchlist w
                JOIN quant.stocks s ON w.symbol = s.symbol
                ORDER BY w.symbol
            """
        else:
            watchlist_query = """
                SELECT w.symbol, s.name
                FROM watchlist w
                JOIN stocks s ON w.symbol = s.symbol
                ORDER BY w.symbol
            """

        watchlist_cursor = conn.execute(watchlist_query)
        watchlist_rows = watchlist_cursor.fetchall()

        watchlist = [
            {'symbol': row[0], 'name': row[1]}
            for row in watchlist_rows
        ]

        return jsonify({
            'positions': positions,
            'watchlist': watchlist
        })

    except Exception as e:
        logger.error(f'获取持仓和自选股失败: {e}')
        return jsonify({
            'error': str(e),
            'positions': [],
            'watchlist': []
        }), 500
    finally:
        if conn:
            conn.close()



def _lookup_local_stock(db: Database, symbol: str):
    rows = db.get_stock_identity_rows()
    for row in rows:
        if normalize_symbol(row.get('symbol', '')) == symbol:
            return {
                'symbol': symbol,
                'name': row.get('name') or symbol,
                'market': db.get_market(symbol) or ('HK' if len(symbol) <= 5 else 'A'),
            }
    return None


def _lookup_external_stock(symbol: str):
    """Query external stock info. Returns a stock dict or an error payload."""
    try:
        from infrastructure.akshare_ts import get_stock_info  # type: ignore
    except Exception:
        get_stock_info = None

    if get_stock_info is not None:
        try:
            payload = json.loads(get_stock_info(symbol))
            if not payload.get('error'):
                return payload
        except Exception:
            pass

    try:
        import akshare as ak
        df = ak.stock_zh_a_spot_em()
        if df is not None and not df.empty:
            match = df[df['代码'].astype(str) == symbol]
            if not match.empty:
                row = match.iloc[0]
                return {
                    'symbol': symbol,
                    'name': str(row.get('名称') or symbol),
                    'market': 'A',
                    'industry': row.get('所属行业'),
                    'market_cap': row.get('总市值'),
                    'pe': row.get('市盈率-动态'),
                    'pb': row.get('市净率'),
                }
    except Exception as exc:
        return {'error': str(exc), 'symbol': symbol}

    return {'error': 'not found', 'symbol': symbol}


def _stock_payload_from_external(symbol: str, payload: dict) -> dict:
    market_cap = payload.get('market_cap')
    if market_cap is None and payload.get('market_cap_billion') is not None:
        try:
            market_cap = float(payload.get('market_cap_billion')) * 100
        except (TypeError, ValueError):
            market_cap = None

    return {
        'symbol': normalize_symbol(payload.get('symbol') or symbol),
        'name': payload.get('name') or symbol,
        'market': payload.get('market') or ('HK' if len(symbol) <= 5 else 'A'),
        'industry': payload.get('industry') or payload.get('sector'),
        'sector': payload.get('sector'),
        'market_cap': market_cap,
        'pe': payload.get('pe') if payload.get('pe') is not None else payload.get('pe_ttm'),
        'pb': payload.get('pb'),
        'list_date': payload.get('list_date') or payload.get('listed_date'),
    }


def _resolved_stock_response(db: Database, stock: dict, source: str, required_days: int) -> dict:
    symbol = normalize_symbol(stock['symbol'])
    coverage = db.get_kline_coverage(symbol)
    kline_count = int(coverage.get('existing_days') or 0)
    return {
        'symbol': symbol,
        'name': stock.get('name') or symbol,
        'market': stock.get('market') or db.get_market(symbol) or ('HK' if len(symbol) <= 5 else 'A'),
        'source': source,
        'hasKlines': kline_count > 0,
        'klineCount': kline_count,
        'latestKlineDate': coverage.get('last_date'),
        'enoughForFactor': kline_count >= 60,
        'enoughForTraining': kline_count >= required_days,
    }


@app.route('/api/stocks/resolve', methods=['POST'])
def resolve_stocks():
    """Resolve user-entered symbols against local DB, external source, and K-line coverage."""
    data = request.get_json() or {}
    symbols = _normalize_symbols(data.get('symbols'))
    required_days = int(data.get('requiredDays') or data.get('days') or 180)
    if not symbols:
        return jsonify({'success': False, 'error': '请提供股票代码'}), 400
    return jsonify({'success': True, 'data': _resolve_symbols_for_pipeline(symbols, required_days)})


# =====================================================
# 新增端点：异步任务管理
# =====================================================

@app.route('/api/jobs/<job_id>', methods=['GET'])
def get_job_status(job_id):
    """查询异步任务状态"""
    job = _get_job(job_id)
    if job is None:
        return jsonify({'error': f'Job {job_id} not found'}), 404
    return jsonify({'success': True, 'data': _normalize_job_for_web(job)})


@app.route('/api/jobs', methods=['GET'])
def list_jobs():
    """列出所有任务（最近50个）"""
    conn = _connect_postgres()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT id, type, status, params, result, error,
                       created_at, updated_at, started_at, finished_at, attempts
                FROM quant.jobs
                ORDER BY created_at DESC
                LIMIT 50
            """)
            rows = cur.fetchall()

        jobs = []
        for row in rows:
            job = {
                'job_id': row['id'],
                'type': row['type'],
                'status': row['status'],
                'params': row['params'],
                'result': row['result'],
                'error': row['error'],
                'created_at': row['created_at'].timestamp() if row['created_at'] else None,
                'started_at': row['started_at'].timestamp() if row['started_at'] else None,
                'completed_at': row['finished_at'].timestamp() if row['finished_at'] else None,
                'attempts': row['attempts']
            }
            jobs.append(_normalize_job_for_web(job))

        return jsonify({'success': True, 'count': len(jobs), 'jobs': jobs})
    finally:
        conn.close()


@app.route('/api/jobs/<job_type>/run', methods=['POST'])
def run_web_job(job_type):
    """quant-web 兼容任务入口。"""
    if job_type not in WEB_JOB_TYPES:
        return jsonify({'success': False, 'error': f'Unsupported job type: {job_type}'}), 400

    data = request.get_json() or {}
    job_id = _start_job_for_type(job_type, data)
    return jsonify({'success': True, 'data': _normalize_job_for_web(_get_job(job_id))}), 202


@app.route('/api/jobs/<job_id>/retry', methods=['POST'])
def retry_web_job(job_id):
    """quant-web 兼容任务重试入口。"""
    job = _get_job(job_id)
    if job is None:
        return jsonify({'success': False, 'error': f'Job {job_id} not found'}), 404

    status = JOB_STATUS_MAP.get(job.get('status'), job.get('status'))
    if status != 'failed':
        return jsonify({'success': False, 'error': f'Only failed jobs can be retried: {job_id}'}), 409

    _update_job(job_id, status='created', started_at=None, completed_at=None, error=None)
    threading.Thread(
        target=lambda: _complete_job_without_executor(job_id, {'message': 'Retried without executor'}),
        daemon=True,
    ).start()
    return jsonify({'success': True, 'data': _normalize_job_for_web(_get_job(job_id))}), 202


@app.route('/api/jobs/<job_id>/cancel', methods=['POST'])
def cancel_web_job(job_id):
    """quant-web 兼容任务取消入口。"""
    job = _get_job(job_id)
    if job is None:
        return jsonify({'success': False, 'error': f'Job {job_id} not found'}), 404

    status = JOB_STATUS_MAP.get(job.get('status'), job.get('status'))
    if status in {'success', 'failed'}:
        return jsonify({'success': False, 'error': f'Completed jobs cannot be cancelled: {job_id}'}), 409

    _update_job(job_id, status='cancelled', completed_at=time.time())
    return jsonify({'success': True, 'data': _normalize_job_for_web(_get_job(job_id))})


@app.route('/api/pipeline/runs', methods=['POST'])
def create_pipeline_run():
    data = request.get_json() or {}
    symbols = _normalize_symbols(data.get('symbols'))
    if not symbols:
        return jsonify({'success': False, 'error': '请提供股票代码'}), 400

    params = {
        **data,
        'symbols': symbols,
        'days': int(data.get('days') or 180),
    }
    run = _create_pipeline_run(params)
    threading.Thread(target=lambda: _run_pipeline_async(run['id']), daemon=True).start()
    return jsonify({'success': True, 'data': run}), 202


@app.route('/api/pipeline/runs', methods=['GET'])
def list_pipeline_runs():
    page = max(int(request.args.get('page', 1)), 1)
    page_size = max(min(int(request.args.get('pageSize', 10)), 100), 1)
    runs = []
    _pipeline_runs_dir.mkdir(parents=True, exist_ok=True)
    for path in _pipeline_runs_dir.glob('pipeline_*.json'):
        try:
            run = _sync_pipeline_run_jobs(_load_json_file(path))
            runs.append(run)
        except Exception:
            continue
    runs.sort(key=lambda item: item.get('createdAt') or '', reverse=True)
    total = len(runs)
    start = (page - 1) * page_size
    end = start + page_size
    return jsonify({
        'success': True,
        'data': {
            'items': runs[start:end],
            'total': total,
            'page': page,
            'pageSize': page_size,
        },
    })


@app.route('/api/pipeline/runs/<run_id>', methods=['GET'])
def get_pipeline_run(run_id):
    run = _get_pipeline_run(run_id)
    if run is None:
        return jsonify({'success': False, 'error': f'Pipeline run {run_id} not found'}), 404
    return jsonify({'success': True, 'data': _sync_pipeline_run_jobs(run)})


@app.route('/api/pipeline/runs/<run_id>/cancel', methods=['POST'])
def cancel_pipeline_run(run_id):
    run = _get_pipeline_run(run_id)
    if run is None:
        return jsonify({'success': False, 'error': f'Pipeline run {run_id} not found'}), 404
    if run.get('status') in {'success', 'failed', 'cancelled'}:
        return jsonify({'success': False, 'error': f'Completed pipeline runs cannot be cancelled: {run_id}'}), 409

    run['status'] = 'cancelled'
    run['finishedAt'] = _pipeline_now_iso()
    for step in run.get('steps', []):
        if step.get('status') == 'running':
            step['status'] = 'cancelled'
            step['finishedAt'] = run['finishedAt']
        job_id = step.get('jobId')
        if job_id:
            job = _get_job(job_id)
            if job and JOB_STATUS_MAP.get(job.get('status'), job.get('status')) not in {'success', 'failed', 'cancelled'}:
                _update_job(job_id, status='cancelled', completed_at=time.time())
    _write_pipeline_run(run)
    return jsonify({'success': True, 'data': run})


def _resolve_job_type_and_params(task: dict):
    """从 task payload 中提取 job_type 和 params，兼容新旧两种格式。"""
    payload = task.get('payload') or {}
    job_type = payload.get('command') or payload.get('job_type')
    if 'params' in payload and isinstance(payload.get('params'), dict):
        params = payload['params']
    else:
        params = {k: v for k, v in payload.items()
                  if k not in ('command', 'description', 'job_type')}
    return job_type, params


@app.route('/api/scheduler/tasks', methods=['GET'])
def list_scheduler_tasks():
    """返回 quant-web 运维页需要的调度任务摘要。"""
    _seed_scheduler_tasks()
    tasks = _load_scheduler_tasks_from_db()
    return jsonify({
        'success': True,
        'tasks': [_scheduler_task_summary(task) for task in tasks],
    })


@app.route('/api/scheduler/tasks', methods=['POST'])
def create_scheduler_task():
    """创建新的调度任务。"""
    data = request.get_json() or {}
    if not data.get('name') or not data.get('scheduleExpr'):
        return jsonify({'success': False, 'error': '任务名称和 Cron 表达式为必填项'}), 400

    payload = data.get('payload', {})
    if isinstance(payload, str):
        try:
            payload = json.loads(payload)
        except (json.JSONDecodeError, TypeError):
            payload = {}

    task = {
        'name': data.get('name'),
        'scheduleKind': data.get('scheduleKind', 'cron'),
        'scheduleExpr': data.get('scheduleExpr'),
        'payload': payload,
        'enabled': data.get('enabled', True),
    }
    saved = _save_scheduler_task_to_db(task)
    return jsonify({'success': True, 'data': _scheduler_task_summary(saved)}), 201


@app.route('/api/scheduler/tasks/<task_id>', methods=['PUT'])
def update_scheduler_task(task_id):
    """更新调度任务。"""
    existing = _get_scheduler_task_from_db(task_id)
    if not existing:
        return jsonify({'success': False, 'error': f'Scheduler task {task_id} not found'}), 404

    data = request.get_json() or {}
    payload = data.get('payload', {})
    if isinstance(payload, str):
        try:
            payload = json.loads(payload)
        except (json.JSONDecodeError, TypeError):
            payload = {}

    existing['name'] = data.get('name', existing['name'])
    existing['scheduleKind'] = data.get('scheduleKind', existing['scheduleKind'])
    existing['scheduleExpr'] = data.get('scheduleExpr', existing['scheduleExpr'])
    existing['payload'] = payload if payload else existing['payload']
    existing['enabled'] = data.get('enabled', existing['enabled'])

    saved = _save_scheduler_task_to_db(existing)
    return jsonify({'success': True, 'data': _scheduler_task_summary(saved)})


@app.route('/api/scheduler/tasks/<task_id>', methods=['DELETE'])
def delete_scheduler_task(task_id):
    """删除调度任务。"""
    deleted = _delete_scheduler_task_from_db(task_id)
    if not deleted:
        return jsonify({'success': False, 'error': f'Scheduler task {task_id} not found'}), 404
    return jsonify({'success': True})


@app.route('/api/scheduler/tasks/<task_id>/enable', methods=['POST'])
def enable_scheduler_task(task_id):
    """启用调度任务。"""
    updated = _set_scheduler_task_enabled(task_id, True)
    if not updated:
        return jsonify({'success': False, 'error': f'Scheduler task {task_id} not found'}), 404
    return jsonify({'success': True})


@app.route('/api/scheduler/tasks/<task_id>/disable', methods=['POST'])
def disable_scheduler_task(task_id):
    """停用调度任务。"""
    updated = _set_scheduler_task_enabled(task_id, False)
    if not updated:
        return jsonify({'success': False, 'error': f'Scheduler task {task_id} not found'}), 404
    return jsonify({'success': True})


@app.route('/api/scheduler/tasks/<task_id>/trigger', methods=['POST'])
def trigger_scheduler_task(task_id):
    """手动触发一个调度任务。"""
    task = _get_scheduler_task_from_db(task_id)
    if task is None:
        return jsonify({'success': False, 'error': f'Scheduler task {task_id} not found'}), 404

    job_type, params = _resolve_job_type_and_params(task)
    if not job_type:
        return jsonify({'success': False, 'error': 'Task payload 中缺少 command/job_type'}), 400

    job_id = _start_job_for_type(job_type, params)
    return jsonify({
        'success': True,
        'data': _scheduler_run_from_job(task, _get_job(job_id), 'manual'),
    }), 202


@app.route('/api/scheduler/tasks/<task_id>/compensate', methods=['POST'])
def compensate_scheduler_task(task_id):
    """补偿触发一个调度任务。"""
    task = _get_scheduler_task_from_db(task_id)
    if task is None:
        return jsonify({'success': False, 'error': f'Scheduler task {task_id} not found'}), 404
    if not task.get('compensationEnabled'):
        return jsonify({'success': False, 'error': f'Scheduler task {task_id} does not enable compensation'}), 409

    job_type, params = _resolve_job_type_and_params(task)
    if not job_type:
        return jsonify({'success': False, 'error': 'Task payload 中缺少 command/job_type'}), 400

    job_id = _start_job_for_type(job_type, params)
    return jsonify({
        'success': True,
        'data': _scheduler_run_from_job(task, _get_job(job_id), 'compensation'),
    }), 202


@app.route('/api/scheduler/tasks/<task_id>/runs', methods=['GET'])
def list_task_runs(task_id):
    """返回指定调度任务的运行记录。"""
    task = _get_scheduler_task_from_db(task_id)
    if task is None:
        return jsonify({'success': False, 'error': f'Scheduler task {task_id} not found'}), 404

    limit = int(request.args.get('limit', 20))
    job_type = (task.get('payload') or {}).get('command') or (task.get('payload') or {}).get('job_type')

    jobs = _query_jobs_from_db(limit=limit, job_type=job_type) if job_type else []
    runs = [_scheduler_run_from_job(task, job, 'scheduled') for job in jobs]

    return jsonify({'success': True, 'runs': runs})


@app.route('/api/scheduler/runs', methods=['GET'])
def list_scheduler_runs():
    """返回调度任务运行记录（支持 status 过滤）。"""
    try:
        limit = int(request.args.get('limit', 50))
        offset = int(request.args.get('offset', 0))
        status = request.args.get('status')

        jobs = _query_jobs_from_db(limit=limit, offset=offset, status=status)

        _seed_scheduler_tasks()
        tasks = _load_scheduler_tasks_from_db()
        tasks_by_job_type = {}
        for t in tasks:
            jt = (t.get('payload') or {}).get('command') or (t.get('payload') or {}).get('job_type')
            if jt:
                tasks_by_job_type[jt] = t

        runs = []
        for job in jobs:
            task = tasks_by_job_type.get(job.get('type', ''))
            if task:
                runs.append(_scheduler_run_from_job(task, job, 'scheduled'))
            else:
                normalized = _normalize_job_for_web(job)
                runs.append({
                    'id': normalized['id'],
                    'taskId': job.get('type', ''),
                    'taskName': job.get('type', ''),
                    'scheduledFor': normalized.get('createdAt', ''),
                    'triggerType': 'scheduled',
                    'status': normalized['status'],
                    'triggeredAt': normalized.get('createdAt'),
                    'startedAt': normalized.get('startedAt'),
                    'finishedAt': normalized.get('finishedAt'),
                    'error': normalized.get('error'),
                    'payload': job.get('params') or {},
                    'createdAt': normalized.get('createdAt'),
                    'updatedAt': normalized.get('updatedAt'),
                })

        return jsonify({
            'success': True,
            'count': len(runs),
            'runs': runs,
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/scheduler/runs/failed', methods=['GET'])
def list_failed_scheduler_runs():
    """返回失败的调度任务运行记录。"""
    try:
        limit = int(request.args.get('limit', 50))
        failed_jobs = _query_jobs_from_db(limit=limit, status='failed')

        _seed_scheduler_tasks()
        tasks = _load_scheduler_tasks_from_db()
        tasks_by_job_type = {}
        for t in tasks:
            jt = (t.get('payload') or {}).get('command') or (t.get('payload') or {}).get('job_type')
            if jt:
                tasks_by_job_type[jt] = t

        failed_runs = []
        for job in failed_jobs:
            task = tasks_by_job_type.get(job.get('type', ''))
            if task:
                run = _scheduler_run_from_job(task, job, 'scheduled')
                if run['status'] in ('failed', 'skipped'):
                    failed_runs.append(run)

        return jsonify({
            'success': True,
            'count': len(failed_runs),
            'runs': failed_runs,
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# =====================================================
# 新增端点：风险检查
# =====================================================

@app.route('/api/risk/check', methods=['POST'])
def risk_check():
    """风险检查 - 检查持仓的集中度、止损、流动性风险"""
    try:
        data = request.get_json() or {}
        symbols = data.get('symbols')
        account_value = data.get('account_value')

        # 读取持仓数据
        portfolio_path = Path(__file__).parent.parent.parent / '.pi-invest' / 'portfolio.json'
        holdings = []
        if portfolio_path.exists():
            with open(portfolio_path, 'r') as f:
                pf = json.load(f)
                holdings = pf.get('holdings', [])

        if symbols:
            holdings = [h for h in holdings if h.get('symbol') in symbols]

        # 计算风险指标
        checks = []
        total_risk_score = 100

        for h in holdings:
            symbol = h.get('symbol', 'unknown')
            quantity = h.get('quantity', 0)
            avg_cost = h.get('avg_cost', 0)
            position_value = quantity * avg_cost

            # 获取当前价格
            current_price = None
            try:
                conn = get_db()
                cursor = conn.execute(
                    "SELECT close FROM daily_klines WHERE symbol=? ORDER BY date DESC LIMIT 1",
                    (symbol,)
                )
                row = cursor.fetchone()
                conn.close()
                if row:
                    current_price = row[0]
            except Exception:
                pass

            item_checks = []
            item_score = 100

            # 集中度检查
            if account_value and account_value > 0:
                concentration = (position_value / account_value) * 100
                if concentration > 30:
                    item_checks.append({'type': 'concentration', 'level': 'high',
                                       'message': f'{symbol} 仓位集中度 {concentration:.1f}% > 30%',
                                       'suggestion': '建议分散持仓'})
                    item_score -= 30
                elif concentration > 20:
                    item_checks.append({'type': 'concentration', 'level': 'medium',
                                       'message': f'{symbol} 仓位集中度 {concentration:.1f}% > 20%'})
                    item_score -= 15

            # 止损检查
            if current_price and avg_cost > 0:
                pnl_pct = ((current_price - avg_cost) / avg_cost) * 100
                if pnl_pct < -8:
                    item_checks.append({'type': 'stop_loss', 'level': 'high',
                                       'message': f'{symbol} 浮亏 {pnl_pct:.1f}%，已触及止损线',
                                       'suggestion': '建议立即止损'})
                    item_score -= 40
                elif pnl_pct < -5:
                    item_checks.append({'type': 'stop_loss', 'level': 'medium',
                                       'message': f'{symbol} 浮亏 {pnl_pct:.1f}%，接近止损线'})
                    item_score -= 20

            checks.append({
                'symbol': symbol,
                'name': h.get('name', ''),
                'position_value': position_value,
                'current_price': current_price,
                'avg_cost': avg_cost,
                'pnl_pct': ((current_price - avg_cost) / avg_cost * 100) if current_price and avg_cost else None,
                'checks': item_checks,
                'score': max(0, item_score)
            })
            total_risk_score = min(total_risk_score, item_score)

        # 整体风险等级
        if total_risk_score >= 80:
            risk_level = 'low'
        elif total_risk_score >= 50:
            risk_level = 'medium'
        else:
            risk_level = 'high'

        return jsonify({
            'risk_score': total_risk_score,
            'risk_level': risk_level,
            'holdings_count': len(holdings),
            'checks': checks
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


# =====================================================
# 新增端点：信号生成
# =====================================================

@app.route('/api/signals/generate', methods=['POST'])
def generate_signals():
    """生成交易信号（异步任务）"""
    try:
        data = request.get_json() or {}
        job_id = _create_job('signal_generate', data)

        # 在后台线程中执行
        threading.Thread(
            target=lambda: _run_signal_generate_job(job_id, data),
            daemon=True
        ).start()

        return jsonify({
            'job_id': job_id,
            'status': 'created',
            'check_url': f'/api/jobs/{job_id}'
        })
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


# =====================================================
# 新增端点：数据更新（ETL 触发）
# =====================================================

def _resolve_stock_list(source: str, db: Database) -> list:
    """根据 source 解析股票列表"""
    project_root = Path(__file__).parent.parent.parent  # pi-investment root

    if source == 'portfolio':
        portfolio_path = project_root / '.pi-invest' / 'portfolio.json'
        if not portfolio_path.exists():
            raise ValueError('portfolio.json not found')
        with open(portfolio_path) as f:
            holdings = json.load(f).get('holdings', [])
        stocks = []
        for h in holdings:
            symbol = h.get('symbol', '')
            if h.get('market', 'A') != 'A' or symbol.startswith('5'):
                continue  # skip HK and ETFs
            stocks.append({'symbol': symbol, 'name': h.get('name', '')})
        return stocks

    elif source == 'watchlist':
        watchlist_path = project_root / '.pi-invest' / 'watchlist.json'
        if not watchlist_path.exists():
            raise ValueError('watchlist.json not found')
        with open(watchlist_path) as f:
            items = json.load(f).get('items', [])
        stocks = []
        for it in items:
            symbol = it.get('symbol', '')
            if symbol.startswith('5'):
                continue  # skip ETFs
            stocks.append({'symbol': symbol, 'name': it.get('name', '')})
        return stocks

    elif source == 'hs300':
        import akshare as ak
        df = ak.index_stock_cons_csindex(symbol='000300')
        stocks = []
        stock_rows = []
        for _, row in df.iterrows():
            symbol = row['成分券代码']
            name = row['成分券名称']
            stock_rows.append({'symbol': symbol, 'name': name, 'market': 'A'})
            stocks.append({'symbol': symbol, 'name': name})
        db.upsert_stocks(stock_rows)
        return stocks

    elif source == 'all':
        return db.get_stock_identity_rows('A')

    else:
        raise ValueError(f'Unknown source: {source}')


def _stock_list_from_symbols(symbols: list, db: Database) -> list:
    stocks = []
    identities = {normalize_symbol(row.get('symbol', '')): row for row in db.get_stock_identity_rows()}
    for symbol in symbols:
        row = identities.get(symbol) or {'symbol': symbol, 'name': symbol}
        stocks.append({'symbol': symbol, 'name': row.get('name') or symbol})
    return stocks


def _check_kline_coverage(db: Database, symbol: str) -> dict:
    """检查某只股票已有的K线数据覆盖情况"""
    return db.get_kline_coverage(symbol)


def _execute_data_update(source: str, days: int, force: bool, symbols: list = None) -> dict:
    """执行数据更新核心逻辑（同步/异步共用）"""
    db_path = Path(__file__).parent.parent.parent / '.pi-invest' / 'stock-db' / 'stocks.db'
    db = Database(str(db_path))
    fetcher = KlineFetcher(db)

    normalized_symbols = _normalize_symbols(symbols)
    stocks = _stock_list_from_symbols(normalized_symbols, db) if normalized_symbols else _resolve_stock_list(source, db)
    details = []
    updated = 0
    skipped = 0
    failed = 0

    for stock in stocks:
        symbol = stock['symbol']
        name = stock['name']
        detail = {'symbol': symbol, 'name': name, 'status': '', 'existing_days': 0, 'new_days': 0, 'error': None}

        try:
            if not force:
                coverage = _check_kline_coverage(db, symbol)
                detail['existing_days'] = coverage['existing_days']
                if coverage['existing_days'] > 0 and coverage['existing_days'] >= days * 0.9:
                    detail['status'] = 'skipped'
                    detail['new_days'] = 0
                    skipped += 1
                    details.append(detail)
                    continue

            fetch_result = fetcher.run(symbols=[symbol], days=days, market='A')
            if getattr(fetch_result, 'failed', 0):
                failures = getattr(fetch_result, 'failures', [])
                error = failures[0].get('error') if failures else 'Kline fetch failed'
                raise RuntimeError(error)

            new_coverage = _check_kline_coverage(db, symbol)
            detail['status'] = 'updated'
            detail['new_days'] = new_coverage['existing_days'] - detail['existing_days']
            detail['existing_days'] = new_coverage['existing_days']
            updated += 1

        except Exception as e:
            detail['status'] = 'failed'
            detail['error'] = str(e)[:200]
            failed += 1

        details.append(detail)

    db.close()
    return {
        'success': True,
        'source': source,
        'days': days,
        'total': len(stocks),
        'updated': updated,
        'skipped': skipped,
        'failed': failed,
        'details': details,
    }


@app.route('/api/data/update', methods=['POST'])
def unified_data_update():
    """统一数据更新入口

    Request JSON:
      source: "portfolio" | "watchlist" | "hs300" | "all"
      days:   正整数
      async:  false(默认, 同步返回) | true(返回 job_id)
      force:  false(默认, 跳过已有数据) | true(强制全拉)
    """
    data = request.get_json() or {}
    source = data.get('source', 'all')
    days = data.get('days', 5)
    async_mode = data.get('async', False)
    force = data.get('force', False)
    symbols = _normalize_symbols(data.get('symbols'))
    if symbols:
        source = 'symbols'

    valid_sources = ['portfolio', 'watchlist', 'hs300', 'all', 'symbols']
    if source not in valid_sources:
        return jsonify({'success': False, 'error': f'source must be one of {valid_sources}'}), 400
    if not isinstance(days, int) or days < 1:
        return jsonify({'success': False, 'error': 'days must be a positive integer'}), 400

    if async_mode:
        job_id = _create_job('data_update', {'source': source, 'symbols': symbols, 'days': days, 'force': force})
        def _run_inline():
            try:
                _update_job(job_id, status='running', started_at=time.time())
                result = _execute_data_update(source, days, force, symbols=symbols or None)
                _update_job(job_id, status='completed', completed_at=time.time(), result=result)
            except Exception as e:
                _update_job(job_id, status='failed', completed_at=time.time(), error=str(e))
        threading.Thread(target=_run_inline, daemon=True).start()
        return jsonify({
            'success': True,
            'job_id': job_id,
            'message': f'数据更新任务已提交 ({source}, {days}天)'
        })

    try:
        result = _execute_data_update(source, days, force, symbols=symbols or None)
        return jsonify(result)
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/data/download-klines', methods=['POST'])
def download_klines():
    """下载K线数据（支持多种周期）

    Request JSON:
      symbols: 股票代码列表，例如 ["600519", "000001"]
      period: K线周期 - "daily", "weekly", "monthly", "1min", "5min", "15min", "30min", "60min"
      days: 下载天数（对于日/周/月线）
      market: 市场类型 - "A", "HK" 等（可选）
      async: false(默认, 同步返回) | true(返回 job_id)
    """
    data = request.get_json() or {}
    symbols = data.get('symbols', [])
    period = data.get('period', 'daily')
    days = data.get('days', 730)
    market = data.get('market')
    async_mode = data.get('async', False)

    # 验证参数
    valid_periods = ['daily', 'weekly', 'monthly', '1min', '5min', '15min', '30min', '60min']
    if period not in valid_periods:
        return jsonify({'success': False, 'error': f'period must be one of {valid_periods}'}), 400

    if not symbols:
        return jsonify({'success': False, 'error': 'symbols参数不能为空'}), 400

    if not isinstance(days, int) or days < 1:
        return jsonify({'success': False, 'error': 'days must be a positive integer'}), 400

    if async_mode:
        job_id = _create_job('download_klines', {'symbols': symbols, 'period': period, 'days': days, 'market': market})
        def _run_inline():
            try:
                _update_job(job_id, status='running', started_at=time.time())
                result = _execute_kline_download(symbols, period, days, market)
                _update_job(job_id, status='completed', completed_at=time.time(), result=result)
            except Exception as e:
                _update_job(job_id, status='failed', completed_at=time.time(), error=str(e))
        threading.Thread(target=_run_inline, daemon=True).start()
        return jsonify({
            'success': True,
            'job_id': job_id,
            'message': f'K线下载任务已提交 ({len(symbols)}只股票, {period})'
        })

    try:
        result = _execute_kline_download(symbols, period, days, market)
        return jsonify(result)
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


def _execute_kline_download(symbols: list, period: str, days: int, market: str = None) -> dict:
    """执行K线数据下载（使用多数据源支持）"""
    # 使用 PostgreSQL 连接
    conn = _connect_postgres()

    # 初始化 DataService（支持多数据源自动降级）
    data_service = DataService(cache_enabled=False, validate_data=True)

    # 计算日期范围
    from datetime import datetime, timedelta
    end_date = datetime.now().strftime("%Y%m%d")
    start_date = (datetime.now() - timedelta(days=days)).strftime("%Y%m%d")

    total = len(symbols)
    succeeded = 0
    failed = 0
    failures = []
    total_rows = 0

    # 分钟级数据暂时使用旧的 fetcher（待扩展 DataService 支持）
    if period in ['1min', '5min', '15min', '30min', '60min']:
        # 对于分钟线，仍然使用 SQLite（待后续迁移）
        db_path = Path(__file__).parent.parent.parent / '.pi-invest' / 'stock-db' / 'stocks.db'
        db = Database(str(db_path))
        minute_period = period.replace('min', '')
        fetcher = MinuteKlineFetcher(db)
        result = fetcher.run(symbols=symbols, period=minute_period, market=market)
        db.close()
        conn.close()
        return {
            'success': True,
            'period': period,
            'total': result.total,
            'succeeded': result.succeeded,
            'failed': result.failed,
            'failures': result.failures,
            'total_rows': 0,  # MinuteKlineFetcher 不返回行数
        }

    # 日/周/月线数据使用 DataService（多数据源支持）
    try:
        for symbol in symbols:
            try:
                # 使用 DataService 获取数据（自动尝试 Tushare -> AkShare）
                print(f"[DEBUG] Fetching data for {symbol}...")
                print(f"[DEBUG] Date range: {start_date} to {end_date}")

                df = data_service.get_daily_klines(
                    symbol=symbol,
                    start_date=start_date,
                    end_date=end_date,
                    adjust="qfq",
                    use_cache=False
                )

                import sys
                print(f"[DEBUG] get_daily_klines returned, type: {type(df)}", flush=True)
                sys.stdout.flush()
                print(f"[DEBUG] df is None: {df is None}", flush=True)
                sys.stdout.flush()
                if df is not None:
                    print(f"[DEBUG] df.empty: {df.empty}", flush=True)
                    sys.stdout.flush()
                    print(f"[DEBUG] len(df): {len(df)}", flush=True)
                    sys.stdout.flush()
                print(f"[DEBUG] Received {len(df) if df is not None else 0} rows for {symbol}", flush=True)
                sys.stdout.flush()

                if df is not None and not df.empty:
                    print(f"[DEBUG] Writing {len(df)} rows to PostgreSQL for {symbol}...")
                    # 存储到 PostgreSQL 数据库
                    with conn.cursor() as cur:
                        for _, row in df.iterrows():
                            try:
                                cur.execute("""
                                    INSERT INTO quant.daily_klines
                                    (symbol, trade_date, open, high, low, close, volume, amount)
                                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                                    ON CONFLICT (symbol, trade_date)
                                    DO UPDATE SET
                                        open = EXCLUDED.open,
                                        high = EXCLUDED.high,
                                        low = EXCLUDED.low,
                                        close = EXCLUDED.close,
                                        volume = EXCLUDED.volume,
                                        amount = EXCLUDED.amount
                                """, (
                                    symbol,
                                    row['date'],
                                    float(row.get('open')) if row.get('open') is not None else None,
                                    float(row.get('high')) if row.get('high') is not None else None,
                                    float(row.get('low')) if row.get('low') is not None else None,
                                    float(row.get('close')) if row.get('close') is not None else None,
                                    float(row.get('volume', 0)),
                                    float(row.get('amount', 0))
                                ))
                            except Exception as e:
                                print(f"Error inserting row for {symbol} on {row['date']}: {e}")
                                raise

                    conn.commit()
                    succeeded += 1
                    total_rows += len(df)
                    print(f"✓ {symbol}: {len(df)} rows written to PostgreSQL (commit successful)")
                else:
                    failed += 1
                    failures.append({'symbol': symbol, 'error': 'No data returned'})
                    print(f"✗ {symbol}: No data")

            except Exception as exc:
                failed += 1
                failures.append({'symbol': symbol, 'error': str(exc)})
                print(f"✗ {symbol}: {exc}")
                import traceback
                traceback.print_exc()
    finally:
        conn.close()

    # 获取数据源健康状态
    health_status = data_service.get_health_status()

    return {
        'success': True,
        'period': period,
        'total': total,
        'succeeded': succeeded,
        'failed': failed,
        'failures': failures,
        'total_rows': total_rows,
        'data_sources': health_status,
    }


@app.route('/api/stocks/add', methods=['POST'])
def add_stock():
    """添加股票到数据库

    Request JSON:
      symbol: 股票代码（必填）
      name: 股票名称（必填）
      market: 市场类型 - "A", "HK" 等（必填）
      industry: 行业（可选）
      sector: 板块（可选）
      list_date: 上市日期（可选，格式：YYYY-MM-DD）
    """
    data = request.get_json() or {}
    symbol = data.get('symbol', '').strip()
    name = data.get('name', '').strip()
    market = data.get('market', '').strip()
    industry = data.get('industry')
    sector = data.get('sector')
    list_date = data.get('list_date')

    # 验证必填参数
    if not symbol:
        return jsonify({'success': False, 'error': 'symbol参数不能为空'}), 400
    if not name:
        return jsonify({'success': False, 'error': 'name参数不能为空'}), 400
    if not market:
        return jsonify({'success': False, 'error': 'market参数不能为空'}), 400

    try:
        db_path = Path(__file__).parent.parent.parent / '.pi-invest' / 'stock-db' / 'stocks.db'
        db = Database(str(db_path))

        # 检查股票是否已存在
        conn = db._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT symbol FROM quant.stocks WHERE symbol = %s", (symbol,))
        existing = cursor.fetchone()

        if existing:
            db.close()
            return jsonify({'success': False, 'error': f'股票 {symbol} 已存在'}), 400

        # 插入股票
        cursor.execute("""
            INSERT INTO quant.stocks (symbol, name, market, industry, sector, list_date, is_st, is_suspended)
            VALUES (%s, %s, %s, %s, %s, %s, false, false)
        """, (symbol, name, market, industry, sector, list_date))
        conn.commit()
        db.close()

        return jsonify({
            'success': True,
            'message': f'股票 {symbol} ({name}) 添加成功',
            'stock': {
                'symbol': symbol,
                'name': name,
                'market': market,
                'industry': industry,
                'sector': sector,
                'list_date': list_date
            }
        })

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# =====================================================
# 新增端点：因子计算（同步）
# =====================================================

@app.route('/api/compute/factors', methods=['POST'])
def trigger_compute_factors():
    """触发因子计算（异步）"""
    data = request.get_json() or {}
    job_id = _create_job('factor_compute', data)

    # 启动后台线程执行因子计算
    threading.Thread(
        target=lambda: _run_factor_compute_job(job_id, data),
        daemon=True,
    ).start()

    return jsonify({'job_id': job_id, 'status': 'created', 'check_url': f'/api/jobs/{job_id}'})


@app.route('/api/compute/historical-factors', methods=['POST'])
def trigger_compute_historical_factors():
    """触发历史因子计算"""
    result = _run_etl_script('calculate_historical_factors.py')
    return jsonify(result)


# =====================================================
# 新增端点：ML 重训练（异步）
# =====================================================

@app.route('/api/ml/predict-batch', methods=['POST'])
def predict_batch():
    """批量 ML 预测"""
    try:
        data = request.get_json() or {}
        symbols = data.get('symbols', [])

        if not symbols:
            return jsonify({'error': '请提供 symbols 参数'}), 400

        if model is None:
            return jsonify({'error': '模型未加载'}), 500

        # 读取训练报告获取特征顺序
        report_path = Path(__file__).parent.parent / 'quantsys' / 'ml' / 'models' / 'training_report_latest.json'
        if not report_path.exists():
            report_path = Path(__file__).parent.parent / 'quantsys' / 'ml' / 'models' / 'training_report.json'
        if not report_path.exists():
            return jsonify({'error': '训练报告文件不存在'}), 500

        with open(report_path) as f:
            report = json.load(f)
            feature_names = report['feature_names']

        conn = get_db()

        # 获取最新日期
        cursor = conn.execute("SELECT MAX(date) FROM factor_values")
        date_row = cursor.fetchone()
        latest_date = date_row[0] if date_row else None
        if not latest_date:
            conn.close()
            return jsonify({'error': '无因子数据'}), 500

        predictions = []
        for symbol in symbols:
            try:
                # 获取因子
                cursor = conn.execute(
                    "SELECT factor_name, factor_value FROM factor_values WHERE symbol=? AND date=?",
                    (symbol, latest_date))
                factors = {row[0]: row[1] for row in cursor.fetchall()}
                if not factors:
                    continue

                # 获取价格
                cursor = conn.execute(
                    "SELECT open,high,low,close,volume,amount,turnover_rate FROM daily_klines WHERE symbol=? AND date=?",
                    (symbol, latest_date))
                row = cursor.fetchone()
                if not row:
                    cursor = conn.execute(
                        "SELECT open,high,low,close,volume,amount,turnover_rate FROM daily_klines WHERE symbol=? ORDER BY date DESC LIMIT 1",
                        (symbol,))
                    row = cursor.fetchone()
                if not row:
                    continue

                feature_dict = {
                    'open': row[0], 'high': row[1], 'low': row[2],
                    'close': row[3], 'volume': row[4], 'amount': row[5],
                    'turnover_rate': row[6]
                }
                feature_dict.update(factors)

                # 构建特征向量
                features = []
                for name in feature_names:
                    value = feature_dict.get(name)
                    features.append(float(value) if value is not None else 0.0)

                X = np.array(features).reshape(1, -1)
                if hasattr(model, 'predict_proba'):
                    proba = model.predict_proba(X)[0]
                    up_prob = float(proba[1])
                else:
                    up_prob = float(model.predict(X)[0])

                predictions.append({
                    'symbol': symbol,
                    'date': latest_date,
                    'direction': 'UP' if up_prob > 0.5 else 'DOWN',
                    'probability': up_prob,
                    'confidence': abs(up_prob - 0.5) * 2,
                    'price': feature_dict['close']
                })
            except Exception:
                continue

        conn.close()

        # 按概率排序
        predictions.sort(key=lambda x: x['probability'], reverse=True)

        return jsonify({
            'date': latest_date,
            'count': len(predictions),
            'predictions': predictions
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/api/ml/retrain', methods=['POST'])
def trigger_ml_retrain():
    """触发ML模型重训练（异步）"""
    try:
        data = request.get_json() or {}
        job_id = _create_job('ml_retrain', data)

        # 在后台线程中执行训练
        def run_training():
            import threading
            from quantsys.ml.training_service import MLTrainingService

            conn = _connect_postgres()
            try:
                # 更新任务状态为 running
                with conn.cursor() as cur:
                    cur.execute("""
                        UPDATE quant.jobs
                        SET status = 'running', started_at = NOW()
                        WHERE id = %s
                    """, (job_id,))
                conn.commit()

                # 解析参数
                days = int(data.get('days', 180))
                future_days = int(data.get('future_days', 5))
                threshold = float(data.get('threshold', 5.0)) / 100.0  # 百分比转小数
                model_type = data.get('model', 'xgboost')

                symbols = data.get('symbols')
                if symbols:
                    if isinstance(symbols, str):
                        # 分割逗号分隔的字符串
                        symbols = [s.strip() for s in symbols.split(',') if s.strip()]
                    elif not isinstance(symbols, list):
                        symbols = None

                # 检查并自动计算缺失的因子
                if symbols:
                    logger.info(f"检查因子数据: {symbols}")
                    from quantsys.factors.factor_service import FactorService

                    pg_config = {
                        'dbname': os.environ.get('PGDATABASE', 'quant_investment'),
                        'host': os.environ.get('PGHOST', 'localhost'),
                        'port': os.environ.get('PGPORT', '5432'),
                        'user': os.environ.get('PGUSER'),
                        'password': os.environ.get('PGPASSWORD'),
                    }

                    factor_service = FactorService(pg_config=pg_config)
                    latest_kline_date = factor_service.get_latest_kline_date()

                    # 检查哪些股票缺少因子
                    missing_symbols = []
                    for symbol in symbols:
                        if not factor_service.check_factors_exist(symbol, latest_kline_date):
                            missing_symbols.append(symbol)

                    # 自动计算缺失的因子
                    if missing_symbols:
                        logger.info(f"自动计算缺失因子: {missing_symbols}")
                        factor_service.calculate_factors(symbols=missing_symbols, force=False)
                        logger.info(f"因子计算完成")
                    else:
                        logger.info(f"所有股票因子已存在，跳过计算")

                # 执行训练
                service = MLTrainingService(conn)
                data_df, labels_df = service.load_training_data(
                    days=days,
                    future_days=future_days,
                    return_threshold=threshold,
                    symbols=symbols
                )

                X, y, feature_names = service.prepare_features(data_df)

                if model_type == 'xgboost':
                    report = service.train_xgboost(X, y, feature_names)
                else:
                    raise ValueError(f"Unsupported model type: {model_type}")

                # 保存训练报告
                service.save_training_report(report, job_id)

                # 更新任务状态为 success
                with conn.cursor() as cur:
                    cur.execute("""
                        UPDATE quant.jobs
                        SET status = 'success', finished_at = NOW()
                        WHERE id = %s
                    """, (job_id,))
                conn.commit()

            except Exception as e:
                # 回滚事务
                conn.rollback()

                # 更新任务状态为 failed
                with conn.cursor() as cur:
                    cur.execute("""
                        UPDATE quant.jobs
                        SET status = 'failed', error = %s, finished_at = NOW()
                        WHERE id = %s
                    """, (str(e), job_id))
                conn.commit()
                logger.exception(f"Training job {job_id} failed")
            finally:
                conn.close()

        # 启动后台线程
        import threading
        thread = threading.Thread(target=run_training, daemon=True)
        thread.start()

        return jsonify({'job_id': job_id, 'status': 'created',
                       'check_url': f'/api/jobs/{job_id}'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


def _run_ml_retrain_job(job_id: str, data: dict):
    """运行ML模型训练任务（服务端函数）"""
    from quantsys.ml.training_service import MLTrainingService

    conn = _connect_postgres()
    try:
        # 更新任务状态为 running
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE quant.jobs
                SET status = 'running', started_at = NOW()
                WHERE id = %s
            """, (job_id,))
        conn.commit()

        # 解析参数
        days = int(data.get('days', 180))
        future_days = int(data.get('futureDays') or data.get('future_days', 5))
        threshold = float(data.get('threshold', 0.05))
        if threshold > 1:  # 如果是百分比形式
            threshold = threshold / 100.0
        model_type = data.get('model', 'xgboost')

        symbols = data.get('symbols')
        if symbols:
            if isinstance(symbols, str):
                symbols = [s.strip() for s in symbols.split(',') if s.strip()]
            elif not isinstance(symbols, list):
                symbols = None

        # 检查并自动计算缺失的因子
        if symbols:
            logger.info(f"检查因子数据: {symbols}")
            from quantsys.factors.factor_service import FactorService

            pg_config = {
                'dbname': os.environ.get('PGDATABASE', 'quant_investment'),
                'host': os.environ.get('PGHOST', 'localhost'),
                'port': os.environ.get('PGPORT', '5432'),
                'user': os.environ.get('PGUSER'),
                'password': os.environ.get('PGPASSWORD'),
            }

            factor_service = FactorService(pg_config=pg_config)
            latest_kline_date = factor_service.get_latest_kline_date()

            # 检查哪些股票缺少因子
            missing_symbols = []
            for symbol in symbols:
                if not factor_service.check_factors_exist(symbol, latest_kline_date):
                    missing_symbols.append(symbol)

            # 自动计算缺失的因子
            if missing_symbols:
                logger.info(f"自动计算缺失因子: {missing_symbols}")
                factor_service.calculate_factors(symbols=missing_symbols, force=False)
                logger.info(f"因子计算完成")
            else:
                logger.info(f"所有股票因子已存在，跳过计算")

        # 执行训练
        service = MLTrainingService(conn)
        data_df, labels_df = service.load_training_data(
            days=days,
            future_days=future_days,
            return_threshold=threshold,
            symbols=symbols
        )

        X, y, feature_names = service.prepare_features(data_df)

        if model_type == 'xgboost':
            report = service.train_xgboost(X, y, feature_names)
        else:
            raise ValueError(f"Unsupported model type: {model_type}")

        # 保存训练报告
        service.save_training_report(report, job_id)

        # 更新任务状态为 success
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE quant.jobs
                SET status = 'success', finished_at = NOW()
                WHERE id = %s
            """, (job_id,))
        conn.commit()

    except Exception as e:
        # 回滚事务
        conn.rollback()

        # 更新任务状态为 failed
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE quant.jobs
                SET status = 'failed', error = %s, finished_at = NOW()
                WHERE id = %s
            """, (str(e), job_id))
        conn.commit()
        logger.exception(f"Training job {job_id} failed")
    finally:
        conn.close()


def _run_factor_compute_job(job_id: str, data: dict):
    """运行因子计算任务（服务端函数，支持并行处理）"""
    conn = _connect_postgres()
    try:
        # 更新任务状态为 running
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE quant.jobs
                SET status = 'running', started_at = NOW(), updated_at = NOW()
                WHERE id = %s
            """, (job_id,))
        conn.commit()

        # 解析参数
        symbols = _normalize_symbols(data.get('symbols'))
        parallel = data.get('parallel', True)  # 默认启用并行
        max_workers = data.get('max_workers', 4)  # 默认4个线程
        force = data.get('force', False)  # 默认增量计算（跳过已有）

        # 构建 PostgreSQL 配置
        pg_config = {
            'dbname': os.environ.get('PGDATABASE', 'quant_investment'),
            'host': os.environ.get('PGHOST', 'localhost'),
            'port': os.environ.get('PGPORT', '5432'),
            'user': os.environ.get('PGUSER'),
            'password': os.environ.get('PGPASSWORD'),
        }

        # 执行因子计算
        if parallel and len(symbols) > 1:
            # 并行处理多个股票
            from concurrent.futures import ThreadPoolExecutor, as_completed

            logger.info(f"并行计算 {len(symbols)} 只股票的因子（{max_workers} 线程）")

            results = []
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                # 为每个股票创建独立的服务实例
                futures = {
                    executor.submit(
                        lambda s: FactorService(pg_config=pg_config).calculate_factors(symbols=[s], force=force),
                        symbol
                    ): symbol
                    for symbol in symbols
                }

                for future in as_completed(futures):
                    symbol = futures[future]
                    try:
                        result = future.result()
                        results.append(result)
                        logger.info(f"✓ {symbol} 计算完成")
                    except Exception as e:
                        logger.error(f"✗ {symbol} 计算失败: {e}")

            # 合并结果
            result = {
                'success': True,
                'total_symbols': len(symbols),
                'completed': len(results),
                'parallel': True
            }
        else:
            # 串行处理
            service = FactorService(pg_config=pg_config)
            result = service.calculate_factors(symbols=symbols, force=force)
            result['parallel'] = False

        # 更新任务状态为 success
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE quant.jobs
                SET status = 'success', result = %s, finished_at = NOW(), updated_at = NOW()
                WHERE id = %s
            """, (json.dumps(sanitize_for_json(result)), job_id))
        conn.commit()

    except Exception as e:
        conn.rollback()
        logger.error(f"因子计算失败: {e}", exc_info=True)

        # 更新任务状态为 failed
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE quant.jobs
                SET status = 'failed', error = %s, finished_at = NOW(), updated_at = NOW()
                WHERE id = %s
            """, (str(e), job_id))
        conn.commit()

    finally:
        conn.close()


def _run_signal_generate_job(job_id: str, data: dict):
    """运行信号生成任务（服务端函数）"""
    try:
        # 更新任务状态为 running
        conn = _connect_postgres()
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE quant.jobs
                SET status = 'running', started_at = NOW(), updated_at = NOW()
                WHERE id = %s
            """, (job_id,))
        conn.commit()
        conn.close()

        # 解析参数
        symbols = _normalize_symbols(data.get('symbols'))

        # 使用 Database 类（已经只支持 PostgreSQL）
        from scripts.generate_signals import SignalGenerator, persist_signals_to_database

        db = Database()  # Database 类会自动连接 PostgreSQL
        generator = SignalGenerator(db)

        # 获取最新日期
        latest_date = generator.get_latest_date()
        logger.info(f"最新数据日期: {latest_date}")

        # 获取股票范围
        if symbols is None:
            symbols = db.get_all_symbols(market='A')

        logger.info(f"共 {len(symbols)} 只股票需要生成信号")

        # 生成信号
        signals, all_factors_map = generator.generate_signals(symbols, latest_date)

        logger.info(f"信号生成完成: 总信号数 {len(signals)}")
        logger.info(f"买入信号: {len([s for s in signals if s['signal'] == 'BUY'])}")
        logger.info(f"卖出信号: {len([s for s in signals if s['signal'] == 'SELL'])}")

        # 持久化到数据库
        persist_signals_to_database(db, signals, latest_date, all_factors_map)

        # 构建结果
        result = {
            'success': True,
            'date': latest_date,
            'total_signals': len(signals),
            'buy_signals': len([s for s in signals if s['signal'] == 'BUY']),
            'sell_signals': len([s for s in signals if s['signal'] == 'SELL']),
            'signals': signals[:20]  # 只返回前20个信号
        }

        # 更新任务状态为 success
        conn = _connect_postgres()
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE quant.jobs
                SET status = 'success', result = %s, finished_at = NOW(), updated_at = NOW()
                WHERE id = %s
            """, (json.dumps(sanitize_for_json(result)), job_id))
        conn.commit()
        conn.close()

    except Exception as e:
        logger.error(f"信号生成失败: {e}", exc_info=True)

        # 更新任务状态为 failed
        conn = _connect_postgres()
        conn.rollback()
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE quant.jobs
                SET status = 'failed', error = %s, finished_at = NOW(), updated_at = NOW()
                WHERE id = %s
            """, (str(e), job_id))
        conn.commit()
        conn.close()


def _run_backtest_job(job_id: str, data: dict):
    """运行回测任务（服务端函数）"""
    try:
        # 更新任务状态为 running
        conn = _connect_postgres()
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE quant.jobs
                SET status = 'running', started_at = NOW(), updated_at = NOW()
                WHERE id = %s
            """, (job_id,))
        conn.commit()
        conn.close()

        # 解析参数
        symbols = _normalize_symbols(data.get('symbols'))
        days = data.get('days', 30)
        start_date = data.get('start_date')
        end_date = data.get('end_date')
        capital = data.get('capital', 1000000.0)

        # 使用 Database 类（已经只支持 PostgreSQL）
        from scripts.weekly_backtest import WeeklyBacktester

        # WeeklyBacktester 需要 quant_dir 参数
        quant_dir = str(Path(__file__).parent.parent)
        backtester = WeeklyBacktester(
            quant_dir=quant_dir,
            initial_capital=capital
        )

        # 执行回测（对每个股票运行所有策略）
        logger.info(f"开始回测: symbols={symbols}, days={days}")

        all_results = []
        for symbol in symbols:
            logger.info(f"回测股票: {symbol}")
            results = backtester.run_all_backtests(
                symbol=symbol,
                start_date=start_date,
                end_date=end_date,
                days=days
            )
            all_results.extend(results)

        # 对结果排名
        ranked_results = backtester.rank_strategies(all_results)

        logger.info(f"回测完成: 共 {len(all_results)} 个策略结果")

        # 构建结果
        result = {
            'success': True,
            'total_backtests': len(all_results),
            'symbols': symbols,
            'results': ranked_results[:10]  # 只返回前10个最佳策略
        }

        # 更新任务状态为 success
        conn = _connect_postgres()
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE quant.jobs
                SET status = 'success', result = %s, finished_at = NOW(), updated_at = NOW()
                WHERE id = %s
            """, (json.dumps(sanitize_for_json(result)), job_id))
        conn.commit()
        conn.close()

    except Exception as e:
        logger.error(f"回测失败: {e}", exc_info=True)

        # 更新任务状态为 failed
        conn = _connect_postgres()
        conn.rollback()
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE quant.jobs
                SET status = 'failed', error = %s, finished_at = NOW(), updated_at = NOW()
                WHERE id = %s
            """, (str(e), job_id))
        conn.commit()
        conn.close()


# =====================================================
# 新增端点：回测（异步）
# =====================================================

@app.route('/api/backtest/run', methods=['POST'])
def trigger_backtest():
    """触发回测（异步）"""
    try:
        data = request.get_json() or {}
        symbols = data.get('symbols', [])
        if not symbols:
            return jsonify({'error': '请提供 symbols 参数'}), 400

        job_id = _create_job('backtest', {'symbols': symbols})
        extra_args = ['--symbols', ','.join(symbols)]
        if data.get('start_date'):
            extra_args.extend(['--start', data['start_date']])
        if data.get('end_date'):
            extra_args.extend(['--end', data['end_date']])

        # 使用服务端函数而不是脚本调用
        threading.Thread(
            target=lambda: _run_backtest_job(job_id, data),
            daemon=True,
        ).start()

        return jsonify({'job_id': job_id, 'status': 'created',
                       'check_url': f'/api/jobs/{job_id}'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# =====================================================
# 新增端点：周度绩效
# =====================================================

@app.route('/api/performance/weekly', methods=['POST'])
def trigger_weekly_performance():
    """触发周度绩效计算"""
    result = _run_etl_script('weekly_performance.py')
    return jsonify(result)


# =====================================================
# 交易历史端点
# =====================================================

@app.route('/api/trades/list', methods=['GET'])
def list_trades():
    """获取交易历史列表"""
    try:
        page, page_size = _validate_pagination_params(
            request.args.get('page', type=int, default=1),
            request.args.get('pageSize', type=int, default=20)
        )
        symbol = request.args.get('symbol')
        direction = request.args.get('direction')  # buy/sell
        keyword = request.args.get('keyword')
        start_date = request.args.get('startDate')
        end_date = request.args.get('endDate')

        conn = get_db()

        conditions = []
        params = []

        if symbol:
            conditions.append("symbol = ?")
            params.append(symbol)

        if direction:
            conditions.append("action = ?")
            params.append(direction)

        if start_date:
            conditions.append("trade_date >= ?")
            params.append(start_date)

        if end_date:
            conditions.append("trade_date <= ?")
            params.append(end_date)

        if keyword:
            conditions.append("(symbol LIKE ? OR reason LIKE ?)")
            params.append(f'%{keyword}%')
            params.append(f'%{keyword}%')

        where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""

        count_query = f"SELECT COUNT(*) FROM trades {where_clause}"
        cursor = conn.execute(count_query, params)
        total = cursor.fetchone()[0]

        base_query = f"""
            SELECT id, symbol, name, action, price, quantity, amount,
                   fee, stamp_duty, trade_date, reason, order_id, pnl, pnl_percent
            FROM trades
            {where_clause}
            ORDER BY trade_date DESC
        """
        paginated_query, paginated_params = _paginate_query(
            base_query, params, page, page_size
        )
        cursor = conn.execute(paginated_query, paginated_params)
        rows = cursor.fetchall()
        conn.close()

        trades = []
        for row in rows:
            trades.append({
                'id': row[0],
                'symbol': row[1],
                'name': row[2],
                'action': row[3],
                'price': float(row[4]) if row[4] is not None else 0.0,
                'quantity': row[5],
                'amount': float(row[6]) if row[6] is not None else 0.0,
                'fee': float(row[7]) if row[7] is not None else 0.0,
                'stampDuty': float(row[8]) if row[8] is not None else 0.0,
                'tradeDate': str(row[9]) if row[9] is not None else None,
                'reason': row[10],
                'orderId': row[11],
                'pnl': float(row[12]) if row[12] is not None else None,
                'pnlPercent': float(row[13]) if row[13] is not None else None,
            })

        return jsonify(_build_paginated_response(
            trades, page, page_size, total, items_key='trades'
        ))

    except ValueError as e:
        return jsonify({'success': False, 'error': str(e)}), 400
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500


_cron_scheduler_started = False
_cron_triggered_cache = set()  # (task_id, minute_key) tuples to prevent duplicate triggers


def _cron_field_matches(field: str, actual: int) -> bool:
    """检查单个 cron 字段是否匹配实际值。"""
    if field == '*':
        return True
    for part in field.split(','):
        part = part.strip()
        if not part:
            continue
        if '/' in part:
            base_str, step_str = part.split('/', 1)
            base = 0 if base_str == '*' else int(base_str)
            step = int(step_str)
            if step <= 0:
                continue
            if actual >= base and (actual - base) % step == 0:
                return True
        elif '-' in part:
            lo_str, hi_str = part.split('-', 1)
            if int(lo_str) <= actual <= int(hi_str):
                return True
        else:
            try:
                if int(part) == actual:
                    return True
            except ValueError:
                continue
    return False


def _cron_matches(cron_expr: str, dt: datetime) -> bool:
    """检查 5 字段 cron 表达式是否匹配给定时间。"""
    parts = cron_expr.strip().split()
    if len(parts) != 5:
        return False
    minute_f, hour_f, dom_f, month_f, dow_f = parts

    if not _cron_field_matches(minute_f, dt.minute):
        return False
    if not _cron_field_matches(hour_f, dt.hour):
        return False
    if not _cron_field_matches(dom_f, dt.day):
        return False
    if not _cron_field_matches(month_f, dt.month):
        return False

    # Python weekday(): 0=Mon .. 6=Sun
    # Cron    dow:     0=Sun, 1=Mon .. 6=Sat, 7=Sun
    python_dow = dt.weekday()
    cron_dow = 7 if python_dow == 6 else python_dow + 1  # Mon=1 .. Sun=7
    if _cron_field_matches(dow_f, cron_dow):
        return True
    if python_dow == 6 and _cron_field_matches(dow_f, 0):
        return True
    return False


def _cron_scheduler_loop():
    """后台线程：每分钟检查 DB 中的启用任务，cron 匹配时自动触发。"""
    logger = logging.getLogger(__name__)
    logger.info("Cron scheduler background thread started")
    while True:
        try:
            now = datetime.now(timezone.utc)
            minute_key = now.strftime('%Y%m%d%H%M')
            # 等 5 秒让秒针过整点
            time.sleep(5)

            tasks = _load_scheduler_tasks_from_db()
            for task in tasks:
                if not task.get('enabled'):
                    continue
                cron_expr = task.get('scheduleExpr', '')
                if not cron_expr:
                    continue
                if not _cron_matches(cron_expr, now):
                    continue

                cache_key = (task['id'], minute_key)
                if cache_key in _cron_triggered_cache:
                    continue
                _cron_triggered_cache.add(cache_key)

                job_type, params = _resolve_job_type_and_params(task)
                if not job_type:
                    continue

                _start_job_for_type(job_type, params)
                logger.info("Cron triggered task %s (%s) at %s", task['id'], task['name'], minute_key)

            # 清理旧缓存（保留最近 120 分钟的 key）
            stale_keys = set()
            for key in _cron_triggered_cache:
                try:
                    key_minute = key[1]
                    if key_minute < now.strftime('%Y%m%d%H%M')[:10] + '0000':  # 跨天简化清理
                        stale_keys.add(key)
                except Exception:
                    stale_keys.add(key)
            if len(_cron_triggered_cache) > 500:
                _cron_triggered_cache.clear()

            # 等到下一分钟
            time.sleep(55)
        except Exception:
            logging.getLogger(__name__).exception("Cron scheduler loop error")
            time.sleep(60)


def _start_cron_scheduler():
    """启动 cron 调度后台线程（仅启动一次）。"""
    global _cron_scheduler_started
    if _cron_scheduler_started:
        return
    _cron_scheduler_started = True
    t = threading.Thread(target=_cron_scheduler_loop, daemon=True, name='cron-scheduler')
    t.start()


if __name__ == '__main__':
    host = os.environ.get('QUANT_API_HOST', '127.0.0.1')
    port = int(os.environ.get('QUANT_API_PORT', '5002'))
    print('🚀 启动量化系统API服务...')
    init_services()
    print('✅ 服务初始化完成')
    print(f'📡 API地址: http://{host}:{port}')
    print(f'📊 健康检查: http://{host}:{port}/api/health')
    print('📈 可用端点:')
    print('   GET /api/health')
    print('   GET /api/feature-importance')
    print('   GET /api/stock/<symbol>/factors')
    print('   GET /api/stock/<symbol>/klines')
    print('   GET /api/stock/<symbol>/technical')
    print('   GET /api/stock/<symbol>/ml-predict')
    print('   POST /api/stocks/compare')
    print('   GET /api/stocks/list')
    print('   GET /api/stocks/data-status')
    print('   GET /api/stocks/search')
    print('   GET /api/signals')
    print('   POST /api/signals/generate')
    print('   GET /api/report/daily')
    print('   GET /api/backtest/results')
    print('   POST /api/backtest/run')
    print('   GET /api/training/history')
    print('   GET /api/training/reports')
    print('   GET /api/training/report/<filename>')
    print('   POST /api/training/start')
    print('   GET /api/training/status/<task_id>')
    print('   GET /api/training/logs/<task_id>')
    print('   POST /api/ml/retrain')
    print('   POST /api/risk/check')
    print('   POST /api/data/update')
    print('   POST /api/compute/factors')
    print('   POST /api/compute/historical-factors')
    print('   POST /api/performance/weekly')
    print('   GET /api/jobs/<job_id>')
    print('   GET /api/jobs')
    print('   GET /api/scheduler/tasks')
    print('   POST /api/scheduler/tasks/<task_id>/trigger')
    print('   POST /api/scheduler/tasks/<task_id>/compensate')
    _start_cron_scheduler()
    app.run(host=host, port=port, debug=False)
