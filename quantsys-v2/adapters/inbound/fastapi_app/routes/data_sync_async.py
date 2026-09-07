"""
数据同步路由
提供 K线、财务等数据的增量同步 API
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, List
import structlog
from datetime import datetime, timedelta

from application.services.data_backfiller import DataBackfiller
from adapters.outbound.repositories.kline_repository import KlineORMRepository
from infrastructure.persistence.orm import get_session

logger = structlog.get_logger(__name__)
router = APIRouter()


class KlineSyncRequest(BaseModel):
    """K线同步请求"""
    date: Optional[str] = None  # YYYY-MM-DD，默认昨日
    symbols: Optional[List[str]] = None  # 指定股票代码列表（默认全市场活跃股）


class KlineSyncResponse(BaseModel):
    """K线同步响应"""
    success: bool
    sync_date: str
    success_count: int
    failed_count: int
    total_stocks: int
    total_rows: int
    elapsed_time: float
    message: str
    failed_symbols: list[str] = []


def get_active_stocks() -> set[str]:
    """获取所有活跃股票代码"""
    try:
        from infrastructure.persistence.orm import close_session
        session = get_session()
        from infrastructure.persistence.orm.models import Stock

        stocks = session.query(Stock.symbol).filter(
            Stock.is_delisted == False
        ).all()

        result = {s[0] for s in stocks}

        # 2026-08-30 修复：显式关闭 Session，避免空闲事务阻塞
        close_session()

        return result

    except Exception as e:
        logger.error(f"获取活跃股票失败: {e}")
        # 确保异常时也关闭 Session
        try:
            from infrastructure.persistence.orm import close_session
            close_session()
        except:
            pass
        raise


@router.post("/api/data/sync-daily-klines", response_model=KlineSyncResponse)
def sync_daily_klines(request: KlineSyncRequest):
    # 2026-08-30 修复：原 async def 直接在事件循环内执行阻塞式 backfill_batch，
    # 大同步会挂死整个 uvicorn（health/其他接口全无响应）。
    # 改为同步 def，FastAPI 自动放入线程池执行，事件循环保持可用。
    """
    同步每日K线数据
    
    Args:
        request: 同步请求，包含日期（可选，默认昨日）
    
    Returns:
        同步结果：成功数、失败数、数据量、耗时
    """
    # 确定同步日期（默认昨日）
    if request.date:
        try:
            sync_date = datetime.strptime(request.date, '%Y-%m-%d').strftime('%Y-%m-%d')
        except ValueError:
            raise HTTPException(status_code=400, detail=f"无效日期格式: {request.date}，应为 YYYY-MM-DD")
    else:
        sync_date = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
    
    logger.info(f"开始同步 {sync_date} K线数据")
    
    try:
        # 获取同步标的：优先用请求指定的 symbols，否则全市场活跃股
        symbols = list(request.symbols) if request.symbols else list(get_active_stocks())
        
        if not symbols:
            raise HTTPException(status_code=500, detail="未获取到任何活跃股票")
        
        logger.info(f"获取到 {len(symbols)} 只活跃股票")
        
        # 构建回填任务
        kline_repo = KlineORMRepository()
        backfiller = DataBackfiller(kline_repo=kline_repo)
        
        backfill_tasks = {}
        for symbol in symbols:
            backfill_tasks[symbol] = [{
                'start': sync_date,
                'end': sync_date,
                'days': 1
            }]
        
        # 执行批量回填
        start_time = datetime.now()
        result = backfiller.backfill_batch(
            backfill_tasks=backfill_tasks,
            max_workers=10,
            max_retries=3
        )
        elapsed = (datetime.now() - start_time).total_seconds()
        
        # 构建响应
        success_rate = result['success_count'] / result['total_stocks'] if result['total_stocks'] > 0 else 0
        
        response = KlineSyncResponse(
            success=success_rate >= 0.8,  # 成功率 ≥80% 视为成功
            sync_date=sync_date,
            success_count=result['success_count'],
            failed_count=result['failed_count'],
            total_stocks=result['total_stocks'],
            total_rows=result['total_days_filled'],
            elapsed_time=elapsed,
            message=f"✅ 同步完成，成功率 {success_rate*100:.1f}%" if success_rate >= 0.8 else f"⚠️ 同步部分失败，成功率 {success_rate*100:.1f}%",
            failed_symbols=result['failed_symbols'][:20] if result['failed_symbols'] else []
        )
        
        logger.info(f"同步完成: {response.message}")
        return response
        
    except Exception as e:
        logger.exception(f"同步失败: {e}")
        raise HTTPException(status_code=500, detail=f"同步失败: {str(e)}")


@router.get("/api/data/sync-status")
async def get_sync_status():
    """
    获取数据同步状态
    
    Returns:
        最近同步状态、数据完整性等信息
    """
    try:
        session = get_session()
        from infrastructure.persistence.orm.models import DailyKline
        from sqlalchemy import func, desc
        
        # 查询最近的数据日期
        latest_date = session.query(
            func.max(DailyKline.trade_date)
        ).scalar()
        
        if not latest_date:
            return {
                "status": "empty",
                "latest_date": None,
                "total_rows": 0,
                "message": "数据库为空，未同步任何数据"
            }
        
        # 查询最近日期的股票数
        latest_count = session.query(
            func.count(DailyKline.symbol)
        ).filter(
            DailyKline.trade_date == latest_date
        ).scalar()
        
        # 查询活跃股票总数
        from infrastructure.persistence.orm.models import Stock
        active_stocks_count = session.query(
            func.count(Stock.symbol)
        ).filter(
            Stock.is_delisted == False
        ).scalar()
        
        # 计算覆盖率
        coverage = (latest_count / active_stocks_count * 100) if active_stocks_count > 0 else 0
        
        return {
            "status": "ok" if coverage >= 80 else "incomplete",
            "latest_date": latest_date.strftime('%Y-%m-%d'),
            "latest_count": latest_count,
            "active_stocks_count": active_stocks_count,
            "coverage": f"{coverage:.1f}%",
            "message": f"最新数据：{latest_date.strftime('%Y-%m-%d')}，覆盖 {latest_count}/{active_stocks_count} 只股票 ({coverage:.1f}%)"
        }
        
    except Exception as e:
        logger.exception(f"获取同步状态失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取状态失败: {str(e)}")
