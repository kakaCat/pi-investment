"""数据质量 API - FastAPI 版（从 Flask data_quality.py 迁移，响应契约保持一致）

复用 DataQualityORMRepository 与 DataQualityService。Flask 直接 jsonify(result)，故同样处理。
"""
from typing import Any, Dict, Optional

from fastapi import APIRouter, Query, Body
from fastapi.responses import JSONResponse
import structlog

from adapters.outbound.repositories import DataQualityORMRepository
from adapters.shared.services import data_quality_service

logger = structlog.get_logger(__name__)

router = APIRouter(tags=["Data Quality - 数据质量"])


def _err(e: Exception, code: int = 500):
    return JSONResponse(status_code=code, content={'success': False, 'error': str(e)})


@router.get('/api/data/quality-report')
def get_quality_report(symbol: Optional[str] = Query(None), start_date: Optional[str] = Query(None),
                       end_date: Optional[str] = Query(None), min_score: Optional[float] = Query(None),
                       max_score: Optional[float] = Query(None), grade: Optional[str] = Query(None),
                       limit: int = Query(100), offset: int = Query(0)):
    try:
        limit = min(limit, 1000)
        repository = DataQualityORMRepository()
        records = repository.get_quality_records(
            symbol=symbol, start_date=start_date, end_date=end_date,
            min_score=min_score, max_score=max_score, grade=grade, limit=limit, offset=offset)
        return {'success': True, 'data': {
            'records': records, 'total': len(records), 'limit': limit, 'offset': offset,
            'filters': {'symbol': symbol, 'start_date': start_date, 'end_date': end_date,
                        'min_score': min_score, 'max_score': max_score, 'grade': grade}}}
    except Exception as e:
        return _err(e)


@router.get('/api/data/quality-stats')
def get_quality_stats(symbol: Optional[str] = Query(None), start_date: Optional[str] = Query(None),
                      end_date: Optional[str] = Query(None), limit: int = Query(30)):
    try:
        repository = DataQualityORMRepository()
        stats = repository.get_daily_stats(symbol=symbol, start_date=start_date, end_date=end_date, limit=limit)
        return {'success': True, 'data': {'stats': stats, 'symbol': symbol}}
    except Exception as e:
        return _err(e)


@router.get('/api/data/quality-summary')
def get_quality_summary(days: int = Query(7)):
    try:
        repository = DataQualityORMRepository()
        summary = repository.get_quality_summary(days=days)
        return {'success': True, 'data': summary}
    except Exception as e:
        return _err(e)


@router.get('/api/data/quality-trend')
def get_quality_trend(symbol: Optional[str] = Query(None), days: int = Query(30)):
    try:
        repository = DataQualityORMRepository()
        stats = repository.get_daily_stats(symbol=symbol, limit=days)
        stats.reverse()
        return {'success': True, 'data': {
            'dates': [s['date'] for s in stats],
            'scores': [s['avg_overall'] for s in stats],
            'error_counts': [s['total_errors'] for s in stats],
            'warning_counts': [s['total_warnings'] for s in stats],
            'symbol': symbol}}
    except Exception as e:
        return _err(e)


@router.get('/api/data/quality-record/{record_id}')
def get_quality_record_detail(record_id: int):
    try:
        repository = DataQualityORMRepository()
        records = repository.get_quality_records(limit=1, offset=0)
        return {'success': True, 'data': records[0] if records else None}
    except Exception as e:
        return _err(e)


@router.post('/api/data/quality-submit')
def submit_quality_record(payload: Optional[Dict[str, Any]] = Body(None)):
    if not payload:
        return JSONResponse(status_code=400, content={'success': False, 'error': '请求体不能为空'})
    required_fields = ['symbol', 'period', 'original_count', 'cleaned_count',
                       'completeness_score', 'consistency_score', 'accuracy_score', 'overall_score']
    for field in required_fields:
        if field not in payload:
            return JSONResponse(status_code=400, content={'success': False, 'error': f'缺少必填字段: {field}'})
    try:
        repository = DataQualityORMRepository()
        record_id = repository.save_quality_record(payload)
        return {'success': True, 'data': {'record_id': record_id, 'message': '质量记录保存成功'}}
    except Exception as e:
        return _err(e)


# ---- DataQualityService 驱动的补救/校验端点 ----

@router.get('/api/data/check')
def check_data_quality_v2(symbols: Optional[str] = Query(None), start_date: Optional[str] = Query(None),
                          end_date: Optional[str] = Query(None), include_report: str = Query('false')):
    try:
        symbol_list = symbols.split(',') if symbols else None
        result = data_quality_service.check_data_quality(
            symbols=symbol_list, start_date=start_date, end_date=end_date,
            include_report=include_report.lower() == 'true')
        return JSONResponse(status_code=200 if result.get('success') else 500, content=result)
    except Exception as e:
        return _err(e)


@router.post('/api/data/detect-gaps')
def detect_gaps(payload: Optional[Dict[str, Any]] = Body(None)):
    try:
        data = payload or {}
        result = data_quality_service.detect_missing_data(
            symbols=data.get('symbols'), start_date=data.get('start_date'), end_date=data.get('end_date'))
        return JSONResponse(status_code=200 if result.get('success') else 500, content=result)
    except Exception as e:
        return _err(e)


@router.post('/api/data/backfill')
def backfill_data(payload: Optional[Dict[str, Any]] = Body(None)):
    try:
        data = payload or {}
        result = data_quality_service.backfill_missing_data(
            symbols=data.get('symbols'), start_date=data.get('start_date'), end_date=data.get('end_date'),
            mode=data.get('mode', 'auto'), max_workers=data.get('max_workers', 8))
        return JSONResponse(status_code=200 if result.get('success') else 500, content=result)
    except Exception as e:
        return _err(e)


@router.post('/api/data/validate')
def validate_data_v2(payload: Optional[Dict[str, Any]] = Body(None)):
    try:
        data = payload or {}
        result = data_quality_service.validate_data(
            symbols=data.get('symbols'), start_date=data.get('start_date'), end_date=data.get('end_date'))
        return JSONResponse(status_code=200 if result.get('success') else 500, content=result)
    except Exception as e:
        return _err(e)
