"""DELETE /api/pools/{id} 的约束冲突必须返回 409（不是 500）——2026-09-13 事件 fc47fb7d 回归测。

原始现场：pool_change_log 外键（当时无 ON DELETE 动作）让 DELETE /api/pools/54 抛
IntegrityError → 路由落到通用 except → 500，并被 Agent OS 采集为 error 事件。
现在：①DB 侧外键已按 R-020 声明删除动作 ②路由侧把这类"数据依赖"显式返回 409 + 指引。
"""
import pytest
from sqlalchemy.exc import IntegrityError


def test_delete_pool_returns_409_on_integrity_error(monkeypatch):
    from adapters.inbound.fastapi_app.routes import pools_async

    def boom(pool_id):
        raise IntegrityError(
            'DELETE FROM quant.stock_pools WHERE id = %(id)s',
            {'id': pool_id},
            Exception('update or delete on table "stock_pools" violates foreign key constraint "x_fkey"'),
        )

    monkeypatch.setattr(pools_async.svc, 'delete_pool', boom)
    resp = pools_async.delete_pool(999999)
    assert getattr(resp, 'status_code', None) == 409, resp
    body = resp.body.decode()
    assert '数据依赖' in body
    assert 'x_fkey' in body or 'unknown' in body


def test_delete_pool_still_404_on_value_error(monkeypatch):
    from adapters.inbound.fastapi_app.routes import pools_async

    def missing(pool_id):
        raise ValueError(f'Pool {pool_id} not found')

    monkeypatch.setattr(pools_async.svc, 'delete_pool', missing)
    resp = pools_async.delete_pool(999999)
    assert getattr(resp, 'status_code', None) == 404
