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
import logging
from datetime import date
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

# 2026-09-14（w-32314d00，REQ-24e15d B2）：原先这里有个 _TABLE = 'quant.sector_snapshot'
# 常量，被 f-string 插进三处 SQL —— 表名写错只会被 except 吞成"无快照"。
# 现在表名由 ORM 模型（models/sector_snapshot.py）唯一确定，常量与 json 依赖一并删除。


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

        # 2026-09-14（w-32314d00，REQ-24e15d B2）：裸 text() SQL → SectorSnapshotRepository
        # （表名此前走模块常量插值，写错只会静默失败；现在表名由 ORM 模型唯一确定）。
        from adapters.outbound.repositories.sector_snapshot_repository import SectorSnapshotRepository
        ok = SectorSnapshotRepository().upsert_snapshot(
            industries=extracted['industries'],
            concepts=extracted['concepts'],
            total=extracted['total'],
            source=source or 'eastmoney',
            snapshot_date=date.today(),
        )
        if not ok:
            return False
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
        from adapters.outbound.repositories.sector_snapshot_repository import SectorSnapshotRepository
        row = SectorSnapshotRepository().get_latest()
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


def load_snapshots(limit: int = 5) -> List[Dict]:
    """读最近 N 天板块快照（按日期倒序，最新在前）。

    2026-09-11（REQ-cf627b，w-f436d4ea）：为 /api/market/sectors 的 days 多窗口
    提供数据基础——此前该端点忽略 days 参数（任何窗口都返回当日快照）。
    返回 [{'snapshot_date','industries','concepts'}]；无表/失败返回 []。
    """
    try:
        from adapters.outbound.repositories.sector_snapshot_repository import SectorSnapshotRepository
        return SectorSnapshotRepository().list_recent(limit)
    except Exception as e:  # noqa: BLE001
        logger.warning(f'sector 快照历史读取失败: {e}')
        return []
