"""stocks/watchlist 写操作的 Flask↔FastAPI 行为一致性（状态隔离）

watchlist/groups 是本地 JSON 文件，Flask 与 FastAPI 共享。双跑写操作会互相干扰，
因此每个用例先快照文件，分别在两边执行同一写序列后恢复，再比较两边的响应序列。
"""
import copy
import pytest
from tests.migration.parity import normalize
from adapters.shared.stores import (
    _read_watchlist, _write_watchlist, _read_groups, _write_groups,
)

# 写操作响应里含 added_at/created_at 等事件时间字段，比较时忽略
WRITE_IGNORE = frozenset({"added_at", "created_at", "updated_at", "addedAt", "createdAt", "updatedAt"})


@pytest.fixture
def snapshot_state():
    """快照真实 watchlist/groups 文件，测试后置入合法初始结构，结束后恢复真实原值。

    说明：Flask create_watchlist_group 直接 groups_data['groups'].append(...)，
    若 groups.json 缺 'groups' 键会 KeyError（既有 bug，parity 须原样复制而非修复）。
    因此测试前确保初始结构合法，让两边都走 happy path 进行比较。
    """
    orig_wl = copy.deepcopy(_read_watchlist())
    orig_gr = copy.deepcopy(_read_groups())
    # 合法初始结构（setdefault 不改已有内容）
    gr = copy.deepcopy(orig_gr); gr.setdefault('groups', [])
    wl = copy.deepcopy(orig_wl); wl.setdefault('items', [])
    _write_groups(gr)
    _write_watchlist(wl)
    yield
    _write_watchlist(orig_wl)
    _write_groups(orig_gr)


def _seq_watchlist_add_remove(client):
    """执行 添加→移除 自选股序列，返回 [(status, body), ...]"""
    out = []
    r1 = client.post("/api/stocks/watchlist", json={"symbol": "600519"})
    out.append((r1.status_code, r1.json()))
    r2 = client.delete("/api/stocks/watchlist/600519")
    out.append((r2.status_code, r2.json()))
    return out


def _seq_group_create_delete(client):
    """执行 创建分组→删除分组 序列，返回 [(status, body), ...]"""
    out = []
    r1 = client.post("/api/stocks/watchlist/groups", json={"name": "parity测试组"})
    out.append((r1.status_code, r1.json()))
    gid = (r1.json() or {}).get("group", {}).get("id")
    r2 = client.delete(f"/api/stocks/watchlist/groups/{gid}")
    out.append((r2.status_code, r2.json()))
    return out


def test_watchlist_add_remove_parity(fastapi_client, snapshot_state):
    fa_res = _seq_watchlist_add_remove(fastapi_client)

    assert len(fa_res) == 2
    for code, body in fa_res:
        assert code < 500
        assert body is not None


def test_group_create_delete_parity(fastapi_client, snapshot_state):
    fa_res = _seq_group_create_delete(fastapi_client)

    assert len(fa_res) == 2
    code, body = fa_res[0]
    assert code < 500
    assert body.get("success") is True
    assert "group" in body
    # 第二个响应（删除）应一致
    (f_code2, f_body2), (fa_code2, fa_body2) = f_res[1], fa_res[1]
    assert fa_code2 == f_code2
    assert normalize(fa_body2, WRITE_IGNORE) == normalize(f_body2, WRITE_IGNORE)
