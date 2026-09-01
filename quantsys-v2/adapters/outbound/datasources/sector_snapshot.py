"""sector 板块列表 DB 快照（stale-while-error 兜底缓存）

2026-09-01 (investor w-8366e526)：GET /api/market/sectors 只有 Eastmoney 单一
数据源（manager.sector_providers），外部源故障/超时（实测 12.8-20s 抖动卡 20s
阈值）时整个端点失败。本模块把最近一次成功数据持久化到 quant.sector_snapshot，
供数据源故障时回退——成功落库、失败读快照、标注 degraded，链路不中断。

用法（路由层）：
    result = mgr.get_sector_list()
    if result.get('success'):
        save_snapshot(result.get('data'), source=result.get('source'))
        return result
    snapshot = load_snapshot()
    if snapshot:
        return {'success': True, 'data': snapshot, 'degraded': True, ...}
    return result
"""
import json
import logging
from datetime import date
from typing import Dict, Optional

logger = logging.getLogger(__name__)

_TABLE = 'quant.sector_snapshot'


def _extract_industries_concepts(data) -> Optional[Dict]:
    """从 provider 返回的 data（MarketData 对象或 dict）提取 industries/concepts。

    provider 可能返回 MarketData 对象（.data 属性才是 dict），需统一转换
    （对齐 2026-08-25 sectors 500 根因修复的模式）。
    """
    d = data
    if not isinstance(d, dict) and hasattr(d, 'data'):
        d = d.data
    if not isinstance(d, dict):
        return None
    industries = d.get('industries') or []
    concepts = d.get('concepts') or []
    if not industries and not concepts:
        return None
    return {
        'industries': industries,
        'concepts': concepts,
        'total': len(industries) + len(concepts),
    }


def save_snapshot(data, source: str = 'eastmoney') -> bool:
    """保存当日快照（snapshot_date 同日 UPSERT 覆盖）。失败不影响主流程。"""
    try:
        extracted = _extract_industries_concepts(data)
        if not extracted:
            logger.warning('sector 快照：无可保存数据（industries/concepts 均为空）')
            return False

        from infrastructure.persistence.orm.config import get_session
        from sqlalchemy import text

        session = get_session()
        try:
            session.execute(
                text(f"""
                    INSERT INTO {_TABLE}
                        (snapshot_date, industries, concepts, total, source, updated_at)
                    VALUES (:d, :ind, :con, :total, :src, now())
                    ON CONFLICT (snapshot_date) DO UPDATE SET
                        industries = EXCLUDED.industries,
                        concepts = EXCLUDED.concepts,
                        total = EXCLUDED.total,
                        source = EXCLUDED.source,
                        updated_at = now()
                """),
                {
                    'd': date.today(),
                    'ind': json.dumps(extracted['industries'], ensure_ascii=False),
                    'con': json.dumps(extracted['concepts'], ensure_ascii=False),
                    'total': extracted['total'],
                    'src': source or 'eastmoney',
                },
            )
            session.commit()
        finally:
            session.close()
        logger.info(f'sector 快照已保存: {extracted["total"]} 个板块 (source={source})')
        return True
    except Exception as e:  # noqa: BLE001 缓存失败不影响主链路
        logger.warning(f'sector 快照保存失败: {e}')
        return False


def load_snapshot() -> Optional[Dict]:
    """读最近一次快照，组装成与 manager.get_sector_list 兼容的结构。

    返回 None 表示无快照（首次运行/表不存在）。组装结构对齐正常返回：
    data.data.industries / data.data.concepts / total / industry_count / concept_count。
    """
    try:
        from infrastructure.persistence.orm.config import get_session
        from sqlalchemy import text

        session = get_session()
        try:
            row = session.execute(
                text(f"""
                    SELECT snapshot_date, industries, concepts, total, source
                    FROM {_TABLE}
                    ORDER BY snapshot_date DESC, updated_at DESC
                    LIMIT 1
                """)
            ).mappings().first()
        finally:
            session.close()

        if not row:
            return None

        industries = row['industries'] or []
        concepts = row['concepts'] or []
        return {
            'data_type': 'sector_list',
            'data': {
                'industries': industries,
                'concepts': concepts,
                'total': row['total'] if row['total'] else len(industries) + len(concepts),
                'industry_count': len(industries),
                'concept_count': len(concepts),
            },
            'source': 'database_snapshot',
            'timestamp': str(row['snapshot_date']),
        }
    except Exception as e:  # noqa: BLE001
        logger.warning(f'sector 快照读取失败: {e}')
        return None
