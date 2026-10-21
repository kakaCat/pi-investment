"""池级盯盘绑定的仓储适配器 + 池成员来源（2026-10-20）

两张职责：
  · WatchPoolBindingRepository：绑定配置 CRUD（watch 自己的表，ORM）
  · PoolMemberSource：读 quant.stock_pools 的池列表/成员（ADR-001：SQL 只在适配器层；
    stock_pools 是 qs_sourcing 领域的表，盯盘只读不写——成员来源单飞，不复用 qs_sourcing
    服务层，避免 watch→sourcing 的运行时依赖）

失败语义：读失败抛错（调用方 reconcile 前已 fail-closed）；写失败抛错。
"""
from typing import Any, Dict, List, Optional

import structlog
from sqlalchemy import text

from infrastructure.persistence.orm import get_session
from infrastructure.persistence.orm.models import WatchPoolBinding

logger = structlog.get_logger(__name__)


def _to_dict(b: WatchPoolBinding) -> Dict[str, Any]:
    return {
        'id': b.id, 'pool_id': b.pool_id, 'pool_name': b.pool_name or '',
        'conditions_template': b.conditions_template,
        'use_member_points': bool(b.use_member_points),
        'member_points_mode': b.member_points_mode or 'breakout',
        'intent': b.intent or 'trend_observe',
        'account': b.account,
        'cooldown_sec': b.cooldown_sec,
        'max_members': int(b.max_members or 100),
        'enabled': bool(b.enabled),
        'last_sync_summary': b.last_sync_summary,
        'created_at': b.created_at.isoformat() if b.created_at else None,
        'updated_at': b.updated_at.isoformat() if b.updated_at else None,
    }


class WatchPoolBindingRepository:
    """绑定配置 CRUD（返回 dict 投影，与 noise 仓储同口径）"""

    def list_bindings(self, enabled: Optional[bool] = None) -> List[Dict[str, Any]]:
        q = get_session().query(WatchPoolBinding)
        if enabled is not None:
            q = q.filter(WatchPoolBinding.enabled.is_(enabled))
        return [_to_dict(b) for b in q.order_by(WatchPoolBinding.id).all()]

    def get_binding(self, binding_id: int) -> Optional[Dict[str, Any]]:
        b = get_session().query(WatchPoolBinding).filter(
            WatchPoolBinding.id == int(binding_id)).first()
        return _to_dict(b) if b is not None else None

    def create_binding(self, **fields) -> Dict[str, Any]:
        b = WatchPoolBinding(**fields)
        session = get_session()
        session.add(b)
        session.commit()
        return _to_dict(b)

    def update_binding(self, binding_id: int, **fields) -> Optional[Dict[str, Any]]:
        b = get_session().query(WatchPoolBinding).filter(
            WatchPoolBinding.id == int(binding_id)).first()
        if b is None:
            return None
        for k, v in fields.items():
            setattr(b, k, v)
        from sqlalchemy import func as _func
        b.updated_at = _func.now()
        get_session().commit()
        return _to_dict(b)

    def save_sync_summary(self, binding_id: int, summary: Dict[str, Any]) -> None:
        b = get_session().query(WatchPoolBinding).filter(
            WatchPoolBinding.id == int(binding_id)).first()
        if b is None:
            raise RuntimeError('绑定不存在：%s' % binding_id)
        b.last_sync_summary = summary
        get_session().commit()


class PoolMemberSource:
    """stock_pools 只读来源（qs_watch domain 端口 IPoolMemberSource 的实现）"""

    def list_pools(self) -> List[Dict[str, Any]]:
        rows = get_session().execute(text(
            "SELECT id, name, pool_type, jsonb_array_length(COALESCE(members,'[]'::jsonb)) AS n "
            "FROM quant.stock_pools ORDER BY id")).mappings().all()
        return [dict(r) for r in rows]

    def get_members(self, pool_id: int) -> List[Dict[str, Any]]:
        """成员投影：symbol（裸码）、buy_point/sell_point、description/tags"""
        row = get_session().execute(text(
            "SELECT members FROM quant.stock_pools WHERE id=:pid"),
            {'pid': int(pool_id)}).first()
        if row is None or row[0] is None:
            return []
        out = []
        for m in row[0]:
            if isinstance(m, dict) and m.get('symbol'):
                out.append({
                    'symbol': str(m['symbol']).split('.')[0],
                    'name': m.get('name'),
                    'buy_point': m.get('buy_point'),
                    'sell_point': m.get('sell_point'),
                    'description': m.get('description'),
                    'tags': m.get('tags') or [],
                })
        return out
