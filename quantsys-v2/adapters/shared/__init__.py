"""中立共享基础设施层 — 供 Flask 与 FastAPI 两个 API 层共用的框架无关代码

从 adapters/inbound/api/shared.py 解耦而来：服务单例、纯函数、任务状态、
文件存储、行情解析。两个 API 框架都从这里 import，互不依赖。
"""
from adapters.shared.services import (
    ds, strategy_service, stock_pool_service, scoring_service,
    stock_scoring_service, sector_rotation_service, pool_validation_service,
    pool_repo, strategy_repository, factor_adapter, ServiceFactory,
)
from adapters.shared.json_helpers import (
    _safe_float, sanitize_for_json, to_camel_case, to_snake_case,
    convert_keys_to_camel, convert_keys_to_snake,
)
from adapters.shared.tasks import (
    acquire_task, release_task, get_running_tasks, get_running_tasks_snapshot,
)
from adapters.shared.stores import (
    _V2_ROOT, _PROJECT_ROOT_PATH, _LEGACY_QUANT_ROOT,
    _load_pipeline_runs, _save_pipeline_runs, _get_pipeline_run, _update_pipeline_run,
    _read_watchlist, _write_watchlist, _read_groups, _write_groups,
)
from adapters.shared.market_helpers import (
    _parse_sina_a_quote, _parse_sina_hk_quote, enrich_stock_data,
    signal_to_opportunity, _aggregate_weekly, _aggregate_monthly,
)
