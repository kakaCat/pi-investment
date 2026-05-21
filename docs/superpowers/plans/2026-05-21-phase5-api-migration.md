# Phase 5: API Migration — v2 补齐路由 + 前端切换

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** v2 API 补齐前端直调的 14 条 Must-have 路由，前端 `PythonBackendClient` 切换到 v2，旧 API 降级为回退。

**Architecture:** 前端 Node.js Express → `PythonBackendClient` (`localhost:5000`) → v2 `api/server.py` → `DataService` → `Repository` → PostgreSQL。不新增 Service 层，直接在路由函数内调用现有 DataService 或写内联逻辑。

**Tech Stack:** Python Flask, psycopg2, PostgreSQL, XGBoost pickle

---

## Current State

| Item | Old (`quant/api/server.py`) | v2 (`quantsys-v2/api/server.py`) |
|------|---------------------------|----------------------------------|
| Total routes | 64 | 33 |
| Port | 5001 | 5000 |
| Frontend proxies | 14 routes via `PythonBackendClient` | 0 |
| ML model loaded | `model` global (XGBoost) | None |
| Helper functions | `_create_job`, `_normalize_symbols`, etc. | `sanitize_for_json` only |

## File Layout

| File | Action | Role |
|------|--------|------|
| `quantsys-v2/api/server.py` | MODIFY | Add 14 routes + helpers |
| `quantsys-v2/api/ml_utils.py` | CREATE | ML model loading, prediction, feature importance |
| `quantsys-v2/api/training_utils.py` | CREATE | Training report file management |
| `quantsys-v2/api/job_utils.py` | CREATE | Async job lifecycle |
| `quantsys-v2/tests/test_api_migration.py` | CREATE | Tests for new routes |
| `src/infrastructure/http/python-backend-client.ts` | MODIFY | Switch base URL to v2, verify compatibility |

---

### Task 1: ML utilities — model loading, prediction, feature importance

**Files:**
- Create: `quantsys-v2/api/ml_utils.py`
- Create: `quantsys-v2/tests/test_ml_utils.py`

The old `quant/api/server.py` loads XGBoost model globally and uses `_analyze_stock_factors()` for prediction. This task extracts ML logic into a standalone module.

- [ ] **Step 1: Find the old ML code**

```bash
grep -n "xgb\|XGB\|model\|_analyze_stock_factors\|feature_importance" /Users/mac/Documents/ai/pi-investment/quant/api/server.py | head -40
```

Read the referenced sections to understand model loading path, prediction logic, and feature importance calculation.

- [ ] **Step 2: Write `ml_utils.py`**

```python
"""ML model utilities — XGBoost loading, prediction, feature importance."""
import os
import pickle
import logging
from typing import Dict, Any, List, Optional

import numpy as np
import xgboost as xgb

logger = logging.getLogger(__name__)

_MODEL = None
_FEATURE_IMPORTANCE_CACHE = None


def _model_dir():
    return os.environ.get(
        "QUANT_ML_MODEL_DIR",
        os.path.join(os.path.dirname(__file__), "..", "quant", ".pi-invest", "ml", "models")
    )


def load_model() -> Optional[xgb.XGBClassifier]:
    global _MODEL
    if _MODEL is not None:
        return _MODEL
    model_path = os.path.join(_model_dir(), "xgboost_latest.pkl")
    if not os.path.exists(model_path):
        logger.warning(f"Model not found: {model_path}")
        return None
    try:
        with open(model_path, "rb") as f:
            _MODEL = pickle.load(f)
        return _MODEL
    except Exception as e:
        logger.warning(f"Failed to load model: {e}")
        return None


def get_feature_names() -> List[str]:
    """Return ordered list of 38 feature names matching the model."""
    return [
        "ma5", "ma10", "ma20",
        "ema5", "ema10", "ema20",
        "rsi", "macd", "macd_signal", "macd_hist",
        "bb_upper", "bb_middle", "bb_lower",
        "atr", "volume_ma5", "volume_ratio",
        "momentum_5", "momentum_10", "momentum_20",
        "roc_5", "roc_10", "roc_20",
        "williams_r",
        "close_to_ma5", "close_to_ma10", "close_to_ma20",
        "high_low_ratio", "amplitude",
        "pe", "pb", "roe",
        "debt_ratio", "current_ratio", "gross_margin", "net_margin",
        "profit_growth", "revenue_growth", "eps",
    ]


def predict(symbol: str, factors: Dict[str, float]) -> Dict[str, Any]:
    """Run ML prediction for a symbol given its factor values.

    Returns: {'symbol': str, 'probability': float, 'confidence': float|None}
    """
    model = load_model()
    if model is None:
        return {"symbol": symbol, "probability": None, "confidence": None, "error": "Model not loaded"}

    feature_names = get_feature_names()
    features = []
    for name in feature_names:
        val = factors.get(name)
        if val is None or (isinstance(val, float) and (np.isnan(val) or np.isinf(val))):
            features.append(0.0)
        else:
            features.append(float(val))

    X = np.array([features])
    proba = model.predict_proba(X)[0]
    prob_up = float(proba[1]) if len(proba) > 1 else float(proba[0])
    return {"symbol": symbol, "probability": prob_up, "confidence": None}


def batch_predict(stocks_factors: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Batch predict for multiple symbols."""
    return [predict(item["symbol"], item.get("factors", {})) for item in stocks_factors]


def analyze_feature_importance() -> List[Dict[str, Any]]:
    """Return feature importance ranked list."""
    global _FEATURE_IMPORTANCE_CACHE
    if _FEATURE_IMPORTANCE_CACHE is not None:
        return _FEATURE_IMPORTANCE_CACHE

    model = load_model()
    if model is None:
        return []

    feature_names = get_feature_names()
    if hasattr(model, "feature_importances_"):
        importances = model.feature_importances_
    elif hasattr(model, "get_booster"):
        booster = model.get_booster()
        scores = booster.get_score(importance_type="gain")
        importances = np.array([scores.get(f"f{i}", 0.0) for i in range(len(feature_names))])
    else:
        return []

    total = float(np.sum(importances)) or 1.0
    result = [
        {"feature": name, "importance": float(imp), "percentage": round(float(imp) / total * 100, 2)}
        for name, imp in sorted(
            zip(feature_names, importances), key=lambda x: x[1], reverse=True
        )
    ]

    _FEATURE_IMPORTANCE_CACHE = result
    return result
```

- [ ] **Step 3: Write tests**

`quantsys-v2/tests/test_ml_utils.py`:

```python
import pytest
import numpy as np
from unittest.mock import patch, MagicMock
from api.ml_utils import predict, batch_predict, analyze_feature_importance, get_feature_names


class TestMLUtils:
    def test_get_feature_names(self):
        names = get_feature_names()
        assert len(names) == 38
        assert names[0] == "ma5"

    def test_predict_model_not_found(self):
        with patch("api.ml_utils.load_model", return_value=None):
            result = predict("000001.SZ", {"ma5": 10.5})
        assert result["error"] == "Model not loaded"
        assert result["probability"] is None

    def test_predict_with_factors(self):
        mock_model = MagicMock()
        mock_model.predict_proba.return_value = np.array([[0.35, 0.65]])
        factors = {name: 0.0 for name in get_feature_names()}

        with patch("api.ml_utils.load_model", return_value=mock_model):
            result = predict("000001.SZ", factors)

        assert result["probability"] == 0.65
        assert result["symbol"] == "000001.SZ"

    def test_predict_nan_factors(self):
        mock_model = MagicMock()
        mock_model.predict_proba.return_value = np.array([[0.5, 0.5]])
        factors = {"ma5": float("nan"), "ma10": 10.0}

        with patch("api.ml_utils.load_model", return_value=mock_model):
            result = predict("000001.SZ", factors)

        assert result["probability"] is not None

    def test_batch_predict(self):
        mock_model = MagicMock()
        mock_model.predict_proba.return_value = np.array([[0.4, 0.6]])
        items = [{"symbol": "000001.SZ", "factors": {}}, {"symbol": "600519.SH", "factors": {}}]

        with patch("api.ml_utils.load_model", return_value=mock_model):
            results = batch_predict(items)

        assert len(results) == 2
        assert results[0]["symbol"] == "000001.SZ"

    def test_analyze_feature_importance_no_model(self):
        from api.ml_utils import _FEATURE_IMPORTANCE_CACHE
        # Reset cache
        import api.ml_utils as mu
        mu._FEATURE_IMPORTANCE_CACHE = None

        with patch("api.ml_utils.load_model", return_value=None):
            result = analyze_feature_importance()
        assert result == []

    def test_feature_importance_sorted(self):
        mock_model = MagicMock()
        mock_model.feature_importances_ = np.random.random(38)

        import api.ml_utils as mu
        mu._FEATURE_IMPORTANCE_CACHE = None

        with patch("api.ml_utils.load_model", return_value=mock_model):
            result = analyze_feature_importance()

        assert len(result) == 38
        percentages = [r["percentage"] for r in result]
        assert percentages == sorted(percentages, reverse=True)
```

- [ ] **Step 4: Run ML tests**

```bash
cd /Users/mac/Documents/ai/pi-investment/quantsys-v2 && PGDATABASE=quant_investment python -m pytest tests/test_ml_utils.py -v -o "addopts="
```

Expected: 7 passed

- [ ] **Step 5: Commit**

```bash
cd /Users/mac/Documents/ai/pi-investment/quantsys-v2 && git add api/ml_utils.py tests/test_ml_utils.py && git commit -m "feat: add ML utilities — model loading, prediction, feature importance"
```

---

### Task 2: Training report utilities

**Files:**
- Create: `quantsys-v2/api/training_utils.py`

The old `quant/api/server.py` reads `training_report_*.json` from `quant/.pi-invest/ml/models/` directory. Extract this into a standalone module.

- [ ] **Step 1: Create `training_utils.py`**

```python
"""Training report utilities — list, read, and manage training history."""
import os
import json
import glob
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


def _reports_dir():
    return os.environ.get(
        "QUANT_ML_REPORTS_DIR",
        os.path.join(os.path.dirname(__file__), "..", "quant", ".pi-invest", "ml", "models")
    )


def list_reports(limit: int = 20) -> List[Dict[str, Any]]:
    """List recent training report files."""
    d = _reports_dir()
    if not os.path.isdir(d):
        return []

    pattern = os.path.join(d, "training_report_*.json")
    files = sorted(glob.glob(pattern), reverse=True)

    result = []
    for fp in files[:limit]:
        fname = os.path.basename(fp)
        try:
            stat = os.stat(fp)
            result.append({
                "filename": fname,
                "size": stat.st_size,
                "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
            })
        except OSError:
            result.append({"filename": fname, "size": 0, "modified": None})

    return result


def read_report(filename: str) -> Optional[Dict[str, Any]]:
    """Read a single training report by filename."""
    fp = os.path.join(_reports_dir(), filename)
    if not os.path.isfile(fp):
        return None
    try:
        with open(fp, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        logger.warning(f"Failed to read report {filename}: {e}")
        return None


def training_history(limit: int = 30) -> List[Dict[str, Any]]:
    """Aggregate training history from all report files."""
    reports = list_reports(limit=limit)
    history = []
    for r in reports:
        data = read_report(r["filename"])
        if data:
            history.append({
                "filename": r["filename"],
                "modified": r["modified"],
                "accuracy": data.get("accuracy"),
                "precision": data.get("precision"),
                "recall": data.get("recall"),
                "f1_score": data.get("f1_score"),
                "auc": data.get("auc"),
                "feature_count": data.get("feature_count"),
                "training_date": data.get("training_date"),
            })
    return history
```

- [ ] **Step 2: Verify training utils import**

```bash
cd /Users/mac/Documents/ai/pi-investment/quantsys-v2 && python3 -c "
from api.training_utils import list_reports, read_report, training_history
print('Import OK')
print(f'Reports found: {len(list_reports())}')
"
```

Expected: Import OK, reports count printed

- [ ] **Step 3: Commit**

```bash
cd /Users/mac/Documents/ai/pi-investment/quantsys-v2 && git add api/training_utils.py && git commit -m "feat: add training report utilities"
```

---

### Task 3: Job utilities — async job lifecycle

**Files:**
- Create: `quantsys-v2/api/job_utils.py`

Old `quant/api/server.py` uses `_create_job()`, `_get_job()`, `_update_job()` to manage async jobs in PostgreSQL `quant.jobs` table. Extract minimal job management.

- [ ] **Step 1: Create `job_utils.py`**

```python
"""Async job lifecycle utilities."""
import uuid
import time
import json
import logging
from typing import Dict, Any, Optional
from core.base_repository import _resolve_db_dsn

import psycopg2
from psycopg2.extras import RealDictCursor

logger = logging.getLogger(__name__)

VALID_JOB_TYPES = ("model_train", "data_update", "signal_generate", "backtest_run",
                   "factor_compute", "risk_check", "report_daily")


def _get_conn():
    dsn = _resolve_db_dsn()
    if not dsn:
        raise RuntimeError("Database connection not configured")
    return psycopg2.connect(dsn, cursor_factory=RealDictCursor)


def create_job(job_type: str, params: Dict[str, Any] = None) -> str:
    """Create a new job record. Returns job_id."""
    if job_type not in VALID_JOB_TYPES:
        raise ValueError(f"Invalid job type: {job_type}")

    job_id = f"{job_type}_{uuid.uuid4().hex[:8]}"
    conn = _get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            """INSERT INTO quant.jobs (job_id, job_type, status, params, created_at)
               VALUES (%s, %s, 'pending', %s, NOW())""",
            (job_id, job_type, json.dumps(params or {})),
        )
        conn.commit()
        cur.close()
        return job_id
    finally:
        conn.close()


def get_job(job_id: str) -> Optional[Dict[str, Any]]:
    """Get a job by ID."""
    conn = _get_conn()
    try:
        cur = conn.cursor()
        cur.execute("SELECT * FROM quant.jobs WHERE job_id = %s", (job_id,))
        row = cur.fetchone()
        cur.close()
        return dict(row) if row else None
    finally:
        conn.close()


def update_job(job_id: str, status: str = None, result: Dict = None,
               error: str = None, completed_at: float = None) -> None:
    """Update job status/result/error."""
    conn = _get_conn()
    try:
        cur = conn.cursor()
        sets = []
        vals = []
        if status is not None:
            sets.append("status = %s")
            vals.append(status)
        if result is not None:
            sets.append("result = %s")
            vals.append(json.dumps(result))
        if error is not None:
            sets.append("error = %s")
            vals.append(error)
        if completed_at is not None:
            sets.append("completed_at = to_timestamp(%s)")
            vals.append(completed_at)
        if not sets:
            return
        vals.append(job_id)
        cur.execute(f"UPDATE quant.jobs SET {', '.join(sets)} WHERE job_id = %s", vals)
        conn.commit()
        cur.close()
    finally:
        conn.close()
```

- [ ] **Step 2: Commit**

```bash
cd /Users/mac/Documents/ai/pi-investment/quantsys-v2 && git add api/job_utils.py && git commit -m "feat: add job lifecycle utilities"
```

---

### Task 4: Add 14 Must-have API routes to v2 server.py

**Files:**
- Modify: `quantsys-v2/api/server.py` (before `if __name__`)

- [ ] **Step 1: Add imports at top of server.py**

```python
from api.ml_utils import predict, batch_predict, analyze_feature_importance, load_model
from api.training_utils import list_reports, read_report, training_history
from api.job_utils import create_job, get_job, update_job
import threading
import os
```

- [ ] **Step 2: Add `/api/feature-importance` GET**

```python
@app.route('/api/feature-importance', methods=['GET'])
def feature_importance():
    result = analyze_feature_importance()
    return jsonify({'features': result, 'count': len(result)})
```

- [ ] **Step 3: Add performance comparison routes**

```python
@app.route('/api/performance/comparison', methods=['GET'])
@app.route('/api/performance/compare', methods=['GET'])
def performance_comparison():
    """Compare strategy performance from backtest results."""
    strategies = request.args.get('strategies', '')
    symbols = request.args.getlist('symbols')
    results = ds.backtest.get_all(limit=200)
    comparison = {}
    for r in results:
        s_name = r.get('strategy_name', 'unknown')
        if strategies and s_name not in strategies.split(','):
            continue
        if s_name not in comparison:
            comparison[s_name] = {
                'count': 0, 'total_return': 0, 'avg_sharpe': 0,
                'avg_max_drawdown': 0, 'avg_win_rate': 0,
            }
        metrics = r.get('metrics', {}) or {}
        comparison[s_name]['count'] += 1
        comparison[s_name]['total_return'] += float(metrics.get('total_return', 0) or 0)
        comparison[s_name]['avg_sharpe'] += float(metrics.get('sharpe_ratio', 0) or 0)
        comparison[s_name]['avg_max_drawdown'] += float(metrics.get('max_drawdown', 0) or 0)
        comparison[s_name]['avg_win_rate'] += float(metrics.get('win_rate', 0) or 0)
    for k, v in comparison.items():
        if v['count'] > 0:
            v['avg_total_return'] = round(v.pop('total_return') / v['count'], 4)
            v['avg_sharpe'] = round(v['avg_sharpe'] / v['count'], 4)
            v['avg_max_drawdown'] = round(v['avg_max_drawdown'] / v['count'], 4)
            v['avg_win_rate'] = round(v['avg_win_rate'] / v['count'], 4)
    return jsonify({'strategies': comparison})
```

- [ ] **Step 4: Add chart data routes**

```python
@app.route('/api/charts/accuracy', methods=['GET'])
def chart_accuracy():
    from api.training_utils import _reports_dir
    path = os.path.join(_reports_dir(), 'chart_accuracy.json')
    if os.path.exists(path):
        with open(path) as f:
            return jsonify(json.load(f))
    return jsonify({'error': 'Chart data not found'}), 404


@app.route('/api/charts/importance', methods=['GET'])
def chart_importance():
    from api.training_utils import _reports_dir
    path = os.path.join(_reports_dir(), 'chart_importance.json')
    if os.path.exists(path):
        with open(path) as f:
            return jsonify(json.load(f))
    return jsonify({'error': 'Chart data not found'}), 404


@app.route('/api/charts/equity', methods=['GET'])
def chart_equity():
    from api.training_utils import _reports_dir
    path = os.path.join(_reports_dir(), 'chart_equity.json')
    if os.path.exists(path):
        with open(path) as f:
            return jsonify(json.load(f))
    return jsonify({'error': 'Chart data not found'}), 404


@app.route('/api/charts/comparison', methods=['GET'])
def chart_comparison():
    from api.training_utils import _reports_dir
    path = os.path.join(_reports_dir(), 'chart_comparison.json')
    if os.path.exists(path):
        with open(path) as f:
            return jsonify(json.load(f))
    return jsonify({'error': 'Chart data not found'}), 404


@app.route('/api/charts/image/<chart_type>', methods=['GET'])
def chart_image(chart_type):
    valid = ('accuracy_trend', 'equity_curve', 'strategy_comparison', 'feature_importance')
    if chart_type not in valid:
        return jsonify({'error': f'Invalid chart type: {chart_type}'}), 400
    from api.training_utils import _reports_dir
    path = os.path.join(_reports_dir(), f'{chart_type}.png')
    if not os.path.exists(path):
        return jsonify({'error': 'Chart image not found'}), 404
    from flask import send_file
    return send_file(path, mimetype='image/png')
```

- [ ] **Step 5: Add training routes**

```python
@app.route('/api/training/history', methods=['GET'])
def api_training_history():
    limit = request.args.get('limit', 30, type=int)
    return jsonify({'history': training_history(limit=limit)})


@app.route('/api/training/reports', methods=['GET'])
def api_training_reports():
    return jsonify({'reports': list_reports(limit=20)})


@app.route('/api/training/report/<filename>', methods=['GET'])
def api_training_report(filename):
    data = read_report(filename)
    if data is None:
        return jsonify({'error': 'Report not found'}), 404
    return jsonify(data)


@app.route('/api/training/start', methods=['POST'])
def api_training_start():
    """Start ML model training in background thread."""
    data = request.get_json() or {}
    days = data.get('days', 365)
    model_type = data.get('model_type', 'xgboost')

    job_id = create_job('model_train', {'days': days, 'model_type': model_type})

    def _run_training():
        try:
            update_job(job_id, status='running')
            import subprocess, sys
            project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            script = os.path.join(project_root, 'quant', 'scripts', 'ml_retrain.py')
            result = subprocess.run(
                [sys.executable, script, '--days', str(days), '--model-type', model_type],
                capture_output=True, text=True, timeout=3600, cwd=os.path.dirname(script)
            )
            if result.returncode == 0:
                update_job(job_id, status='completed',
                           result={'stdout': result.stdout[-500:], 'stderr': result.stderr[-200:]},
                           completed_at=time.time())
            else:
                update_job(job_id, status='failed', error=result.stderr[:500],
                           completed_at=time.time())
        except Exception as e:
            update_job(job_id, status='failed', error=str(e),
                       completed_at=time.time())

    threading.Thread(target=_run_training, daemon=True).start()
    return jsonify({'success': True, 'job_id': job_id})


@app.route('/api/training/status/<task_id>', methods=['GET'])
def api_training_status(task_id):
    job = get_job(task_id)
    if job is None:
        return jsonify({'error': 'Job not found'}), 404
    return jsonify({'job_id': task_id, 'status': job.get('status'), 'result': job.get('result'),
                    'error': job.get('error'), 'created_at': job.get('created_at')})


@app.route('/api/training/logs/<task_id>', methods=['GET'])
def api_training_logs(task_id):
    job = get_job(task_id)
    if job is None:
        return jsonify({'error': 'Job not found'}), 404
    return jsonify({'job_id': task_id, 'logs': (job.get('result') or {}).get('stdout', '')})
```

- [ ] **Step 6: Add stock ML predict route**

```python
@app.route('/api/stock/<symbol>/ml-predict', methods=['GET'])
def stock_ml_predict(symbol):
    """ML prediction for a single stock."""
    factors_raw = ds.factor.get_latest_factors(symbol)
    if not factors_raw:
        return jsonify({'error': f'No factors found for {symbol}'}), 404
    result = predict(symbol, factors_raw)
    return jsonify(result)
```

- [ ] **Step 7: Verify import succeeds**

```bash
cd /Users/mac/Documents/ai/pi-investment/quantsys-v2 && python3 -c "from api.server import app; print('Import OK, routes:', len(app.url_map._rules))" 2>&1
```

Expected: Import OK, routes: ~48

- [ ] **Step 8: Run API tests**

```bash
cd /Users/mac/Documents/ai/pi-investment/quantsys-v2 && PGDATABASE=quant_investment python -m pytest tests/test_api.py -v --tb=short 2>&1 | tail -30
```

Expected: all existing API tests still pass

- [ ] **Step 9: Commit**

```bash
cd /Users/mac/Documents/ai/pi-investment/quantsys-v2 && git add api/server.py && git commit -m "feat: add 14 Must-have API routes — training, charts, ML predict, performance"
```

---

### Task 5: Write migration API tests

**Files:**
- Create: `quantsys-v2/tests/test_api_migration.py`

- [ ] **Step 1: Write tests for new routes**

```python
"""Tests for newly migrated API routes."""
import pytest
import json
from api.server import app


@pytest.fixture
def client():
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client


class TestFeatureImportance:
    def test_feature_importance(self, client):
        rv = client.get('/api/feature-importance')
        assert rv.status_code == 200
        data = json.loads(rv.data)
        assert 'features' in data


class TestCharts:
    def test_chart_accuracy_not_found(self, client):
        rv = client.get('/api/charts/accuracy')
        assert rv.status_code in (200, 404)

    def test_chart_image_invalid_type(self, client):
        rv = client.get('/api/charts/image/bad_type')
        assert rv.status_code == 400


class TestTraining:
    def test_training_history(self, client):
        rv = client.get('/api/training/history')
        assert rv.status_code == 200
        assert 'history' in json.loads(rv.data)

    def test_training_reports(self, client):
        rv = client.get('/api/training/reports')
        assert rv.status_code == 200
        assert 'reports' in json.loads(rv.data)

    def test_training_report_not_found(self, client):
        rv = client.get('/api/training/report/nonexistent.json')
        assert rv.status_code == 404

    def test_training_start(self, client):
        rv = client.post('/api/training/start', json={'days': 30})
        assert rv.status_code == 200
        assert 'job_id' in json.loads(rv.data)

    def test_training_status_not_found(self, client):
        rv = client.get('/api/training/status/nonexistent')
        assert rv.status_code == 404

    def test_training_logs_not_found(self, client):
        rv = client.get('/api/training/logs/nonexistent')
        assert rv.status_code == 404


class TestMLPredict:
    def test_ml_predict_no_factors(self, client):
        rv = client.get('/api/stock/999999.SZ/ml-predict')
        assert rv.status_code == 404


class TestPerformance:
    def test_performance_comparison(self, client):
        rv = client.get('/api/performance/compare')
        assert rv.status_code == 200
        assert 'strategies' in json.loads(rv.data)

    def test_performance_comparison_alias(self, client):
        rv = client.get('/api/performance/comparison')
        assert rv.status_code == 200
```

- [ ] **Step 2: Run migration tests**

```bash
cd /Users/mac/Documents/ai/pi-investment/quantsys-v2 && PGDATABASE=quant_investment python -m pytest tests/test_api_migration.py -v --tb=short -o "addopts="
```

Expected: all pass (some may skip if DB not available)

- [ ] **Step 3: Commit**

```bash
cd /Users/mac/Documents/ai/pi-investment/quantsys-v2 && git add tests/test_api_migration.py && git commit -m "test: add migration API route tests"
```

---

### Task 6: Switch frontend to v2 API

**Files:**
- Modify: `src/infrastructure/http/python-backend-client.ts`

- [ ] **Step 1: Find the current base URL configuration**

```bash
grep -n "5000\|5001\|PYTHON_BACKEND\|baseUrl\|base.url" /Users/mac/Documents/ai/pi-investment/src/infrastructure/http/python-backend-client.ts | head -10
grep -rn "localhost:500" /Users/mac/Documents/ai/pi-investment/src/ --include="*.ts" | head -20
```

- [ ] **Step 2: Verify the port change works**

Both old and v2 run on different ports. V2 is on 5000 by default. Verify `PythonBackendClient` already points to `localhost:5000`.

- [ ] **Step 3: Verify frontend compatibility**

```bash
cd /Users/mac/Documents/ai/pi-investment/quantsys-v2 && PGDATABASE=quant_investment python3 api/server.py &
sleep 2
# Test each of the 14 proxied routes
curl -s http://localhost:5000/api/training/history | python3 -m json.tool | head -5
curl -s http://localhost:5000/api/feature-importance | python3 -m json.tool | head -5
curl -s http://localhost:5000/api/charts/accuracy | python3 -m json.tool | head -5
kill %1 2>/dev/null
```

Expected: valid JSON responses from all endpoints

- [ ] **Step 4: Commit any TypeScript config changes**

---

### Task 7: Full suite regression

- [ ] **Step 1: Run all tests**

```bash
cd /Users/mac/Documents/ai/pi-investment/quantsys-v2 && PGDATABASE=quant_investment python -m pytest tests/ --tb=short 2>&1 | tail -5
```

Expected: all pass (no regressions from route additions)

- [ ] **Step 2: Fix any failures and commit**
