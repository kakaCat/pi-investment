from typing import Any, Dict, Optional

from fastapi import APIRouter, Body, Query
from fastapi.responses import JSONResponse

from adapters.outbound.repositories.simulation_repository import SimulationORMRepository
from adapters.outbound.repositories.t_trade_repository import TTradeRepository
from adapters.outbound.repositories.watch_rule_repository import WatchRuleRepository
from qs_trading.application.services.t_trade_service import TTradeService
from qs_trading.domain.trading.exceptions import TradingError
from qs_watch.application.services.watch_engine.lifecycle.t_trade_watch_service import (
    TTradeWatchService,
)

router = APIRouter(prefix="/api/t-trades", tags=["Range T Trading"])


def _build_services():
    simulation_repo = SimulationORMRepository()
    cycle_repo = TTradeRepository(simulation_repo=simulation_repo)
    service = TTradeService(repo=cycle_repo, simulation_repo=simulation_repo)
    watch = TTradeWatchService(
        rule_repo=WatchRuleRepository(), cycle_repo=cycle_repo,
    )
    return service, watch


def _error(exc: TradingError) -> JSONResponse:
    body = {"success": False, "error": str(exc)}
    if exc.details is not None:
        body["details"] = exc.details
    return JSONResponse(body, status_code=exc.status_code)


def _sync(watch, cycle) -> Dict[str, Any]:
    try:
        return watch.reconcile(cycle)
    except Exception as exc:  # noqa: BLE001
        return {"status": "error", "error": str(exc)[:500], "retry": "reconcile"}


@router.post("", status_code=201)
def create_cycle(payload: Dict[str, Any] = Body(...)):
    try:
        service, watch = _build_services()
        cycle = service.create_cycle(
            account=payload.get("account"),
            symbol=payload.get("symbol"),
            upper_price=payload.get("upper_price"),
            lower_price=payload.get("lower_price"),
            shares=payload.get("shares"),
            reason=payload.get("reason"),
            invalidation=payload.get("invalidation") or "",
            slippage_bps=payload.get("slippage_bps", 10),
        )
        return {
            "success": True,
            "data": {"cycle": cycle.to_dict(), "rule_sync": _sync(watch, cycle)},
        }
    except TradingError as exc:
        return _error(exc)
    except Exception as exc:
        return JSONResponse({"success": False, "error": str(exc)}, status_code=500)


@router.get("")
def list_cycles(account: Optional[str] = Query(None), status: Optional[str] = Query(None),
                limit: int = Query(100, ge=1, le=500)):
    try:
        service, _ = _build_services()
        rows = service.repo.list_cycles(account=account, status=status, limit=limit)
        return {"success": True, "data": {"cycles": [row.to_dict() for row in rows]}}
    except Exception as exc:
        return JSONResponse({"success": False, "error": str(exc)}, status_code=500)


@router.get("/{cycle_id}")
def get_cycle(cycle_id: int):
    try:
        service, _ = _build_services()
        return {"success": True, "data": {"cycle": service.get_cycle(cycle_id).to_dict()}}
    except TradingError as exc:
        return _error(exc)
    except Exception as exc:
        return JSONResponse({"success": False, "error": str(exc)}, status_code=500)


@router.post("/{cycle_id}/execute")
def execute_cycle(cycle_id: int, payload: Dict[str, Any] = Body(default_factory=dict)):
    try:
        service, watch = _build_services()
        result = service.execute(cycle_id)
        result["rule_sync"] = _sync(watch, service.get_cycle(cycle_id))
        return {"success": True, "data": result}
    except TradingError as exc:
        return _error(exc)
    except Exception as exc:
        return JSONResponse({"success": False, "error": str(exc)}, status_code=500)


@router.post("/{cycle_id}/record-fill")
def record_fill(cycle_id: int, payload: Dict[str, Any] = Body(...)):
    try:
        service, watch = _build_services()
        cycle = service.record_fill(cycle_id, payload.get("trade_id"))
        return {
            "success": True,
            "data": {"cycle": cycle.to_dict(), "rule_sync": _sync(watch, cycle)},
        }
    except TradingError as exc:
        return _error(exc)
    except Exception as exc:
        return JSONResponse({"success": False, "error": str(exc)}, status_code=500)


@router.post("/{cycle_id}/cancel")
def cancel_cycle(cycle_id: int, payload: Dict[str, Any] = Body(...)):
    try:
        service, watch = _build_services()
        cycle = service.cancel(cycle_id, payload.get("reason"))
        return {
            "success": True,
            "data": {"cycle": cycle.to_dict(), "rule_sync": _sync(watch, cycle)},
        }
    except TradingError as exc:
        return _error(exc)
    except Exception as exc:
        return JSONResponse({"success": False, "error": str(exc)}, status_code=500)


@router.post("/{cycle_id}/reconcile")
def reconcile_cycle(cycle_id: int):
    try:
        service, watch = _build_services()
        cycle = service.get_cycle(cycle_id)
        return {"success": True, "data": {"cycle": cycle.to_dict(), "rule_sync": watch.reconcile(cycle)}}
    except TradingError as exc:
        return _error(exc)
    except Exception as exc:
        return JSONResponse({"success": False, "error": str(exc)}, status_code=500)
