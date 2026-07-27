"""文件存储助手（框架无关）— 从 adapters/inbound/api/shared.py 解耦而来

路径常量 + pipeline 运行记录 + watchlist/groups 文件读写。
"""
import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# ── 路径常量 ──
# 本文件位于 quantsys-v2/adapters/shared/stores.py，向上3级即 quantsys-v2 根
_V2_ROOT = Path(__file__).resolve().parent.parent.parent
_PROJECT_ROOT_PATH = _V2_ROOT.parent
_LEGACY_QUANT_ROOT = _PROJECT_ROOT_PATH / 'quant'


def _safe_float(value, default=0.0):
    """安全转换为浮点数"""
    try:
        return float(value) if value is not None else default
    except (ValueError, TypeError):
        return default


# ── Pipeline 运行管理 ──
_PIPELINE_RUNS_FILE = _V2_ROOT / 'data' / 'pipeline_runs.json'


def _load_pipeline_runs():
    """加载 pipeline 运行记录"""
    if not _PIPELINE_RUNS_FILE.exists():
        return []
    try:
        with open(_PIPELINE_RUNS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"加载 pipeline 运行记录失败: {e}")
        return []


def _save_pipeline_runs(runs):
    """保存 pipeline 运行记录"""
    try:
        _PIPELINE_RUNS_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(_PIPELINE_RUNS_FILE, 'w', encoding='utf-8') as f:
            json.dump(runs, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"保存 pipeline 运行记录失败: {e}")


def _get_pipeline_run(run_id):
    """获取指定的 pipeline 运行记录"""
    runs = _load_pipeline_runs()
    for run in runs:
        if run.get('run_id') == run_id:
            return run
    return None


def _update_pipeline_run(run_id, updates):
    """更新 pipeline 运行记录"""
    runs = _load_pipeline_runs()
    for run in runs:
        if run.get('run_id') == run_id:
            run.update(updates)
            _save_pipeline_runs(runs)
            return True
    return False


# ── Watchlist 管理 ──
_WATCHLIST_FILE = _V2_ROOT / '.pi-invest' / 'watchlist.json'


def _read_watchlist():
    """读取自选股列表"""
    if not _WATCHLIST_FILE.exists():
        return {'items': []}
    try:
        with open(_WATCHLIST_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
            if isinstance(data, list):
                return {'items': data}
            return data
    except Exception as e:
        logger.error(f"读取自选股列表失败: {e}")
        return {'items': []}


def _write_watchlist(watchlist):
    """写入自选股列表"""
    try:
        _WATCHLIST_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(_WATCHLIST_FILE, 'w', encoding='utf-8') as f:
            json.dump(watchlist, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"写入自选股列表失败: {e}")


def _read_groups():
    """读取分组配置"""
    groups_file = _V2_ROOT / 'data' / 'groups.json'
    if not groups_file.exists():
        return {}
    try:
        with open(groups_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"读取分组配置失败: {e}")
        return {}


def _write_groups(groups):
    """写入分组配置"""
    groups_file = _V2_ROOT / 'data' / 'groups.json'
    try:
        groups_file.parent.mkdir(parents=True, exist_ok=True)
        with open(groups_file, 'w', encoding='utf-8') as f:
            json.dump(groups, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"写入分组配置失败: {e}")
