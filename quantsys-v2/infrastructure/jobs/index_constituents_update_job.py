"""
指数成分股更新Job

填充 quant.index_constituents（沪深300 / 创业板指 / 科创50）。
该表是机会扫描热门池（stock_pool_service.get_hot_stocks）的数据来源——
2026-07-28 前表内 0 行，导致 opportunity_scan 扫描池静默为空。

数据源：中证指数官网（csindex）优先，新浪 fallback（均不依赖东财，
规避东财 WAF 封 IP 风险）。

调度配置：task_name=index_constituents_update, cron '40 15 * * 1-5'
也可手动执行：python -m infrastructure.jobs.index_constituents_update_job
"""
import os
os.environ['OMP_NUM_THREADS'] = '1'
os.environ['MKL_NUM_THREADS'] = '1'
os.environ['OPENBLAS_NUM_THREADS'] = '1'

import sys
import logging
from datetime import datetime
from pathlib import Path

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

logger = logging.getLogger(__name__)

# 热门池指数（与 StockPoolService.HOT_INDEX_CODES 一致）
INDICES = {
    '000300.SH': '000300',  # 沪深300（中证）
    '000688.SH': '000688',  # 科创50（中证）
    '399006.SZ': '399006',  # 创业板指（深交所，csindex 无，走新浪）
}


def _fetch_constituents(code: str) -> list:
    """获取单个指数的成分股代码列表（裸 6 位代码）"""
    from adapters.outbound.datasources import get_data_provider_manager
    provider_manager = get_data_provider_manager()

    # 中证系指数优先走官网
    try:
        df = provider_manager.call_akshare('index_stock_cons_csindex', symbol=code)
        if df is not None and not df.empty:
            return [str(c).zfill(6) for c in df['成分券代码'].tolist()]
    except Exception as e:
        logger.warning(f"csindex 获取 {code} 失败: {type(e).__name__} {str(e)[:80]}")

    # fallback：新浪
    try:
        df = provider_manager.call_akshare('index_stock_cons_sina', symbol=code)
        if df is not None and not df.empty:
            return [str(c).zfill(6) for c in df['code'].tolist()]
    except Exception as e:
        logger.warning(f"sina 获取 {code} 失败: {type(e).__name__} {str(e)[:80]}")

    return []


def execute(**params):
    """
    更新全部热门指数成分股

    Returns:
        dict: 执行结果 {success, indices: {index_code: count}, errors}
    """
    from infrastructure.persistence.orm import get_session
    from infrastructure.persistence.orm.models import IndexConstituent

    logger.info("=" * 70)
    logger.info(f"指数成分股更新任务开始: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("=" * 70)

    session = get_session()
    results = {}
    errors = []

    for index_code, code in INDICES.items():
        try:
            symbols = _fetch_constituents(code)
            if not symbols:
                errors.append(f"{index_code}: 无数据")
                continue

            # 全量替换该指数的成分
            session.query(IndexConstituent).filter(
                IndexConstituent.index_code == index_code
            ).delete(synchronize_session=False)

            session.add_all([
                IndexConstituent(index_code=index_code, symbol=s, weight=0.0)
                for s in symbols
            ])
            session.commit()
            results[index_code] = len(symbols)
            logger.info(f"✓ {index_code}: {len(symbols)} 只成分股")
        except Exception as e:
            session.rollback()
            errors.append(f"{index_code}: {type(e).__name__} {str(e)[:80]}")
            logger.error(f"✗ {index_code} 更新失败: {e}")

    success = len(results) == len(INDICES)
    logger.info(f"成分股更新完成: {results}, errors={errors}")
    return {
        'success': success,
        'indices': results,
        'errors': errors,
        'timestamp': datetime.now().isoformat(),
    }


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO,
                        format='%(asctime)s %(levelname)s %(name)s: %(message)s')
    result = execute()
    sys.exit(0 if result.get('success') else 1)
