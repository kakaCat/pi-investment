# 股票池 add_member / remove_member 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为 agent 提供 `pool_manage` 的 `add_member` / `remove_member` 动作，支持批量、幂等、动态池警告。

**Architecture:** 三层改动——quantsys-v2 后端（StockPoolService 两个方法 + Flask 路由 + FastAPI parity 镜像）→ agent-ts TS client 两个函数 → `pool_manage` 工具两个 action。规格见 `docs/superpowers/specs/2026-07-27-pool-member-ops-design.md`。

**Tech Stack:** Python 3.13 / Flask / FastAPI / pytest；TypeScript / Jest（ESM，`npm test`，禁止裸 `npx jest`）。

**Worktree:** 所有工作在 `/Users/mac/Documents/ai/pi-investment/.claude/worktrees/pool-member-ops`（分支 `feat/pool-member-ops`）中进行。

**测试命令约定：**
- Python（在 worktree 的 `quantsys-v2/` 下）：`source activate-py313.sh && python -m pytest <path> -v`
- TS（在 worktree 的 `agent-ts/` 下）：`npm test -- <path>`

---

### Task 1: 后端 Service — add_members / remove_members

**Files:**
- Modify: `quantsys-v2/application/services/stock_pool_service.py`（在 `update_member` 方法后插入两个新方法）
- Test: `quantsys-v2/tests/test_stock_pool_service.py`（文件末尾追加 `TestPoolMemberOps` 类）

背景：service 现有 `update_member` 的模式是——`pool_repo.get_pool(pool_id)` 取池、`members` 为空则从 `symbols` 重建、改完后 `pool_repo.update(pool_id, {...})` 一次落库。池 dict 含 `symbols`（List[str]）、`members`（List[dict]）、`pool_type` 字段。`stock_repo.batch_get_names(symbols)` 返回 `{symbol: name}`。

- [ ] **Step 1: 写失败测试**

在 `quantsys-v2/tests/test_stock_pool_service.py` 末尾追加（文件已有 `from unittest.mock import Mock` 和 `StockPoolService` 导入；若没有则补上）：

```python
class TestPoolMemberOps:
    """add_members / remove_members 单元测试"""

    @pytest.fixture
    def mock_stock_repo(self):
        repo = Mock()
        repo.batch_get_names.return_value = {
            '600519.SH': '贵州茅台', '000858.SZ': '五粮液', '000001.SZ': '平安银行',
        }
        return repo

    def _make_service(self, mock_stock_repo, pool):
        pool_repo = Mock()
        pool_repo.get_pool.return_value = pool
        pool_repo.update.return_value = dict(pool)
        return StockPoolService(mock_stock_repo, pool_repo=pool_repo), pool_repo

    def _static_pool(self):
        return {
            'id': 1, 'name': '测试池', 'pool_type': 'static',
            'symbols': ['600519.SH'],
            'members': [
                {'symbol': '600519.SH', 'name': '贵州茅台', 'description': None,
                 'buy_point': None, 'sell_point': None, 'tags': []},
            ],
        }

    def test_add_members_adds_new_with_names_and_metadata(self, mock_stock_repo):
        svc, pool_repo = self._make_service(mock_stock_repo, self._static_pool())
        result = svc.add_members(1, ['000858.SZ', '000001.SZ'],
                                 member_data={'description': '关注', 'tags': ['白酒']})
        assert result['added'] == ['000858.SZ', '000001.SZ']
        assert result['skipped'] == []
        assert 'warning' not in result
        # symbols 与 members 同步落库，且只 update 一次
        pool_repo.update.assert_called_once()
        args = pool_repo.update.call_args[0]
        assert args[0] == 1
        assert args[1]['symbols'] == ['600519.SH', '000858.SZ', '000001.SZ']
        new_members = args[1]['members'][1:]
        assert new_members[0]['name'] == '五粮液'
        assert new_members[0]['description'] == '关注'
        assert new_members[0]['tags'] == ['白酒']
        assert new_members[1]['name'] == '平安银行'

    def test_add_members_skips_existing(self, mock_stock_repo):
        svc, pool_repo = self._make_service(mock_stock_repo, self._static_pool())
        result = svc.add_members(1, ['600519.SH', '000858.SZ'])
        assert result['added'] == ['000858.SZ']
        assert result['skipped'] == ['600519.SH']

    def test_add_members_all_existing_no_update(self, mock_stock_repo):
        svc, pool_repo = self._make_service(mock_stock_repo, self._static_pool())
        result = svc.add_members(1, ['600519.SH'])
        assert result['added'] == []
        assert result['skipped'] == ['600519.SH']
        pool_repo.update.assert_not_called()

    def test_add_members_pool_not_found(self, mock_stock_repo):
        svc, _ = self._make_service(mock_stock_repo, None)
        with pytest.raises(ValueError, match="Pool 999 not found"):
            svc.add_members(999, ['600519.SH'])

    def test_add_members_dynamic_pool_warning(self, mock_stock_repo):
        pool = self._static_pool()
        pool['pool_type'] = 'dynamic'
        svc, _ = self._make_service(mock_stock_repo, pool)
        result = svc.add_members(1, ['000858.SZ'])
        assert 'warning' in result
        assert 'refresh' in result['warning']

    def test_add_members_rebuilds_members_from_symbols(self, mock_stock_repo):
        pool = {'id': 1, 'name': '旧池', 'pool_type': 'static',
                'symbols': ['600519.SH'], 'members': []}
        svc, pool_repo = self._make_service(mock_stock_repo, pool)
        svc.add_members(1, ['000858.SZ'])
        args = pool_repo.update.call_args[0]
        # members 先从 symbols 重建，再追加新成员
        assert [m['symbol'] for m in args[1]['members']] == ['600519.SH', '000858.SZ']

    def test_remove_members_removes_from_symbols_and_members(self, mock_stock_repo):
        pool = self._static_pool()
        pool['symbols'].append('000858.SZ')
        pool['members'].append({'symbol': '000858.SZ', 'name': '五粮液',
                                'description': None, 'buy_point': None,
                                'sell_point': None, 'tags': []})
        svc, pool_repo = self._make_service(mock_stock_repo, pool)
        result = svc.remove_members(1, ['000858.SZ'])
        assert result['removed'] == ['000858.SZ']
        assert result['skipped'] == []
        args = pool_repo.update.call_args[0]
        assert args[1]['symbols'] == ['600519.SH']
        assert [m['symbol'] for m in args[1]['members']] == ['600519.SH']

    def test_remove_members_skips_missing(self, mock_stock_repo):
        svc, pool_repo = self._make_service(mock_stock_repo, self._static_pool())
        result = svc.remove_members(1, ['000858.SZ'])
        assert result['removed'] == []
        assert result['skipped'] == ['000858.SZ']
        pool_repo.update.assert_not_called()

    def test_remove_members_pool_not_found(self, mock_stock_repo):
        svc, _ = self._make_service(mock_stock_repo, None)
        with pytest.raises(ValueError, match="Pool 999 not found"):
            svc.remove_members(999, ['600519.SH'])

    def test_remove_members_dynamic_pool_warning(self, mock_stock_repo):
        pool = self._static_pool()
        pool['pool_type'] = 'dynamic'
        svc, _ = self._make_service(mock_stock_repo, pool)
        result = svc.remove_members(1, ['600519.SH'])
        assert 'warning' in result
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd quantsys-v2 && source activate-py313.sh && python -m pytest tests/test_stock_pool_service.py::TestPoolMemberOps -v`
Expected: FAIL — `AttributeError: 'StockPoolService' object has no attribute 'add_members'`

- [ ] **Step 3: 实现两个 service 方法**

在 `quantsys-v2/application/services/stock_pool_service.py` 的 `update_member` 方法之后插入：

```python
    # 动态池手动增删成员的覆盖警告
    DYNAMIC_POOL_WARNING = (
        '动态池 refresh 将按筛选条件重建成员，手动增删的成员可能被覆盖'
    )

    def _ensure_members(self, pool: dict) -> list:
        """返回池的 members 列表；为空时从 symbols 重建（不持久化）。"""
        members = pool.get('members') or []
        if members:
            return list(members)
        symbols = pool.get('symbols') or []
        names_by_symbol = self.stock_repo.batch_get_names(symbols) if symbols else {}
        return [
            {'symbol': s, 'name': names_by_symbol.get(s), 'description': None,
             'buy_point': None, 'sell_point': None, 'tags': []}
            for s in symbols
        ]

    def add_members(self, pool_id: int, symbols: List[str],
                    member_data: dict = None) -> dict:
        """
        批量添加池子成员（幂等：已在池中的跳过）。

        Returns:
            {pool, added, skipped, warning?}
        """
        if not self._pool_repo:
            raise RuntimeError("StockPoolRepository not configured")
        pool = self._pool_repo.get_pool(pool_id)
        if not pool:
            raise ValueError(f"Pool {pool_id} not found")

        member_data = member_data or {}
        current_symbols = list(pool.get('symbols') or [])
        members = self._ensure_members(pool)

        existing = set(current_symbols)
        to_add = [s for s in symbols if s not in existing]
        skipped = [s for s in symbols if s in existing]

        if to_add:
            names_by_symbol = self.stock_repo.batch_get_names(to_add)
            for s in to_add:
                members.append({
                    'symbol': s,
                    'name': names_by_symbol.get(s),
                    'description': member_data.get('description'),
                    'buy_point': member_data.get('buy_point'),
                    'sell_point': member_data.get('sell_point'),
                    'tags': member_data.get('tags') or [],
                })
                current_symbols.append(s)
            updated = self._pool_repo.update(
                pool_id, {'symbols': current_symbols, 'members': members})
            if not updated:
                raise ValueError(f"Failed to update pool {pool_id}")

        result = {
            'pool': self.get_pool(pool_id),
            'added': to_add,
            'skipped': skipped,
        }
        if pool.get('pool_type') == 'dynamic':
            result['warning'] = self.DYNAMIC_POOL_WARNING
        return result

    def remove_members(self, pool_id: int, symbols: List[str]) -> dict:
        """
        批量移除池子成员（幂等：不在池中的跳过）。

        Returns:
            {pool, removed, skipped, warning?}
        """
        if not self._pool_repo:
            raise RuntimeError("StockPoolRepository not configured")
        pool = self._pool_repo.get_pool(pool_id)
        if not pool:
            raise ValueError(f"Pool {pool_id} not found")

        current_symbols = list(pool.get('symbols') or [])
        members = self._ensure_members(pool)

        existing = set(current_symbols)
        to_remove = [s for s in symbols if s in existing]
        skipped = [s for s in symbols if s not in existing]

        if to_remove:
            remove_set = set(to_remove)
            current_symbols = [s for s in current_symbols if s not in remove_set]
            members = [m for m in members if m.get('symbol') not in remove_set]
            updated = self._pool_repo.update(
                pool_id, {'symbols': current_symbols, 'members': members})
            if not updated:
                raise ValueError(f"Failed to update pool {pool_id}")

        result = {
            'pool': self.get_pool(pool_id),
            'removed': to_remove,
            'skipped': skipped,
        }
        if pool.get('pool_type') == 'dynamic':
            result['warning'] = self.DYNAMIC_POOL_WARNING
        return result
```

- [ ] **Step 4: 跑测试确认通过**

Run: `cd quantsys-v2 && source activate-py313.sh && python -m pytest tests/test_stock_pool_service.py -v`
Expected: 全部 PASS（含文件中原有用例）

- [ ] **Step 5: Commit**

```bash
cd /Users/mac/Documents/ai/pi-investment/.claude/worktrees/pool-member-ops
git add quantsys-v2/application/services/stock_pool_service.py quantsys-v2/tests/test_stock_pool_service.py
git commit -m "feat(pools): StockPoolService 增加 add_members/remove_members（批量、幂等、动态池警告）"
```

---

### Task 2: Flask 路由 — POST/DELETE /api/pools/<id>/members

**Files:**
- Modify: `quantsys-v2/adapters/inbound/api/routes/pools.py`（在 `update_member` 路由后插入）
- Test: `quantsys-v2/tests/api/test_pools_routes.py`（文件末尾追加 `TestPoolMemberRoutes` 类）

- [ ] **Step 1: 写失败测试**

在 `quantsys-v2/tests/api/test_pools_routes.py` 末尾追加（沿用现有 `@patch('api.routes.pools._get_services')` 模式）：

```python
class TestPoolMemberRoutes:
    @patch('api.routes.pools._get_services')
    def test_add_members(self, mock_get, client):
        mock_svc = MagicMock()
        mock_svc.add_members.return_value = {
            'pool': {'id': 1, 'name': '测试池'},
            'added': ['000858.SZ'], 'skipped': [],
        }
        mock_get.return_value = (mock_svc, MagicMock())

        resp = client.post('/api/pools/1/members', json={
            'symbols': ['000858.SZ'], 'description': '关注', 'buyPoint': '120以下',
        })
        assert resp.status_code == 200
        body = resp.get_json()
        assert body['success'] is True
        assert body['data']['added'] == ['000858.SZ']
        mock_svc.add_members.assert_called_once_with(
            pool_id=1, symbols=['000858.SZ'],
            member_data={'description': '关注', 'buy_point': '120以下',
                         'sell_point': None, 'tags': []},
        )

    @patch('api.routes.pools._get_services')
    def test_add_members_missing_symbols(self, mock_get, client):
        mock_get.return_value = (MagicMock(), MagicMock())
        resp = client.post('/api/pools/1/members', json={})
        assert resp.status_code == 400
        assert resp.get_json()['success'] is False

    @patch('api.routes.pools._get_services')
    def test_add_members_pool_not_found(self, mock_get, client):
        mock_svc = MagicMock()
        mock_svc.add_members.side_effect = ValueError('Pool 999 not found')
        mock_get.return_value = (mock_svc, MagicMock())
        resp = client.post('/api/pools/999/members', json={'symbols': ['600519.SH']})
        assert resp.status_code == 404
        assert resp.get_json()['success'] is False

    @patch('api.routes.pools._get_services')
    def test_remove_members(self, mock_get, client):
        mock_svc = MagicMock()
        mock_svc.remove_members.return_value = {
            'pool': {'id': 1, 'name': '测试池'},
            'removed': ['000858.SZ'], 'skipped': [],
        }
        mock_get.return_value = (mock_svc, MagicMock())

        resp = client.delete('/api/pools/1/members', json={'symbols': ['000858.SZ']})
        assert resp.status_code == 200
        body = resp.get_json()
        assert body['success'] is True
        assert body['data']['removed'] == ['000858.SZ']
        mock_svc.remove_members.assert_called_once_with(
            pool_id=1, symbols=['000858.SZ'])

    @patch('api.routes.pools._get_services')
    def test_remove_members_missing_symbols(self, mock_get, client):
        mock_get.return_value = (MagicMock(), MagicMock())
        resp = client.delete('/api/pools/1/members', json={})
        assert resp.status_code == 400

    @patch('api.routes.pools._get_services')
    def test_remove_members_pool_not_found(self, mock_get, client):
        mock_svc = MagicMock()
        mock_svc.remove_members.side_effect = ValueError('Pool 999 not found')
        mock_get.return_value = (mock_svc, MagicMock())
        resp = client.delete('/api/pools/999/members', json={'symbols': ['600519.SH']})
        assert resp.status_code == 404
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd quantsys-v2 && source activate-py313.sh && python -m pytest tests/api/test_pools_routes.py::TestPoolMemberRoutes -v`
Expected: FAIL — 404/405（路由不存在）

- [ ] **Step 3: 实现两个路由**

在 `quantsys-v2/adapters/inbound/api/routes/pools.py` 的 `update_member` 路由（`PUT /api/pools/<int:pool_id>/members/<symbol>`）之后插入：

```python
@pools_bp.route('/api/pools/<int:pool_id>/members', methods=['POST'])
def add_members(pool_id):
    """批量添加池子成员（幂等：已在池中的跳过）"""
    svc, _ = _get_services()
    data = request.get_json() or {}
    symbols = data.get('symbols')
    if not symbols or not isinstance(symbols, list):
        return jsonify({'success': False, 'error': 'symbols must be a non-empty array'}), 400
    try:
        result = svc.add_members(
            pool_id=pool_id,
            symbols=symbols,
            member_data={
                'description': data.get('description'),
                'buy_point': data.get('buyPoint') or data.get('buy_point'),
                'sell_point': data.get('sellPoint') or data.get('sell_point'),
                'tags': data.get('tags', [])
            }
        )
        return jsonify({'success': True, 'data': result})
    except ValueError as e:
        return jsonify({'success': False, 'error': str(e)}), 404
    except Exception as e:
        logger.error(f"Add members failed: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@pools_bp.route('/api/pools/<int:pool_id>/members', methods=['DELETE'])
def remove_members(pool_id):
    """批量移除池子成员（幂等：不在池中的跳过）"""
    svc, _ = _get_services()
    data = request.get_json() or {}
    symbols = data.get('symbols')
    if not symbols or not isinstance(symbols, list):
        return jsonify({'success': False, 'error': 'symbols must be a non-empty array'}), 400
    try:
        result = svc.remove_members(pool_id=pool_id, symbols=symbols)
        return jsonify({'success': True, 'data': result})
    except ValueError as e:
        return jsonify({'success': False, 'error': str(e)}), 404
    except Exception as e:
        logger.error(f"Remove members failed: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500
```

- [ ] **Step 4: 跑测试确认通过**

Run: `cd quantsys-v2 && source activate-py313.sh && python -m pytest tests/api/test_pools_routes.py -v`
Expected: 全部 PASS

- [ ] **Step 5: Commit**

```bash
cd /Users/mac/Documents/ai/pi-investment/.claude/worktrees/pool-member-ops
git add quantsys-v2/adapters/inbound/api/routes/pools.py quantsys-v2/tests/api/test_pools_routes.py
git commit -m "feat(pools): Flask 增加 POST/DELETE /api/pools/<id>/members 批量增删成员端点"
```

---

### Task 3: FastAPI parity 镜像端点 + parity 测试

**Files:**
- Modify: `quantsys-v2/adapters/inbound/fastapi_app/routes/pools_async.py`（在 `update_member` 路由后插入）
- Test: `quantsys-v2/tests/migration/test_pools_parity.py`（文件末尾追加 3 个用例）

注意：该文件复用 Flask 的同一个 `stock_pool_service`（模块级 `svc = stock_pool_service`），路由用全路径风格；`error_response(payload, status)` 用于错误响应。`PUT /api/pools/{pool_id}/members/{symbol}` 已存在，新增 `/members`（无 symbol 段）不冲突。

- [ ] **Step 1: 写失败 parity 测试**

在 `quantsys-v2/tests/migration/test_pools_parity.py` 末尾追加：

```python
ADD_MEMBERS_NF = "/api/pools/999999/members"   # 不存在 → 404


def test_add_members_not_found(flask_client, fastapi_client):
    assert_parity(flask_client, fastapi_client, "POST", ADD_MEMBERS_NF,
                  json_body={"symbols": ["600519.SH"]})


def test_add_members_missing_symbols(flask_client, fastapi_client):
    assert_parity(flask_client, fastapi_client, "POST", ADD_MEMBERS_NF,
                  json_body={})


def test_remove_members_not_found(flask_client, fastapi_client):
    assert_parity(flask_client, fastapi_client, "DELETE", ADD_MEMBERS_NF,
                  json_body={"symbols": ["600519.SH"]})
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd quantsys-v2 && source activate-py313.sh && python -m pytest tests/migration/test_pools_parity.py -k "members" -v`
Expected: FAIL — FastAPI 侧 404/405 与 Flask 200/404 不一致（路由未注册时 FastAPI 返回 404 detail 体，parity 断言响应体不一致）

- [ ] **Step 3: 实现 FastAPI 镜像路由**

在 `quantsys-v2/adapters/inbound/fastapi_app/routes/pools_async.py` 的 `update_member` 路由之后插入：

```python
@router.post('/api/pools/{pool_id}/members')
def add_members(pool_id: int, payload: Optional[Dict[str, Any]] = Body(None)):
    data = payload or {}
    symbols = data.get('symbols')
    if not symbols or not isinstance(symbols, list):
        return error_response({'success': False, 'error': 'symbols must be a non-empty array'}, 400)
    try:
        result = svc.add_members(
            pool_id=pool_id, symbols=symbols,
            member_data={
                'description': data.get('description'),
                'buy_point': data.get('buyPoint') or data.get('buy_point'),
                'sell_point': data.get('sellPoint') or data.get('sell_point'),
                'tags': data.get('tags', []),
            })
        return {'success': True, 'data': result}
    except ValueError as e:
        return error_response({'success': False, 'error': str(e)}, 404)
    except Exception as e:
        logger.error(f"Add members failed: {e}")
        return error_response({'success': False, 'error': str(e)}, 500)


@router.delete('/api/pools/{pool_id}/members')
def remove_members(pool_id: int, payload: Optional[Dict[str, Any]] = Body(None)):
    data = payload or {}
    symbols = data.get('symbols')
    if not symbols or not isinstance(symbols, list):
        return error_response({'success': False, 'error': 'symbols must be a non-empty array'}, 400)
    try:
        result = svc.remove_members(pool_id=pool_id, symbols=symbols)
        return {'success': True, 'data': result}
    except ValueError as e:
        return error_response({'success': False, 'error': str(e)}, 404)
    except Exception as e:
        logger.error(f"Remove members failed: {e}")
        return error_response({'success': False, 'error': str(e)}, 500)
```

- [ ] **Step 4: 跑 parity 测试确认通过**

Run: `cd quantsys-v2 && source activate-py313.sh && python -m pytest tests/migration/test_pools_parity.py -v`
Expected: 全部 PASS（含 3 个新用例；新端点在 Flask/FastAPI 两侧状态码与响应体一致）

- [ ] **Step 5: Commit**

```bash
cd /Users/mac/Documents/ai/pi-investment/.claude/worktrees/pool-member-ops
git add quantsys-v2/adapters/inbound/fastapi_app/routes/pools_async.py quantsys-v2/tests/migration/test_pools_parity.py
git commit -m "feat(pools): FastAPI parity 同步 POST/DELETE /api/pools/{id}/members 端点"
```

---

### Task 4: TS Client — addPoolMembers / removePoolMembers

**Files:**
- Modify: `agent-ts/src/infrastructure/adapters/quant/quant-v2-client.ts`（在 `updatePoolMember` 之后插入）

背景：`fetchV2<T>(url, {method, body})` 返回解析后的 JSON 整体（后端响应为 `{success, data}` 信封，fetchV2 不解包，调用方自行处理，与 `updatePoolMember` 相同）。

- [ ] **Step 1: 实现两个 client 函数**

在 `agent-ts/src/infrastructure/adapters/quant/quant-v2-client.ts` 的 `updatePoolMember` 函数之后插入：

```typescript
export interface PoolMembersAddParams {
  symbols: string[];
  description?: string;
  buy_point?: string;
  sell_point?: string;
  tags?: string[];
}

export async function addPoolMembers(
  poolId: number,
  params: PoolMembersAddParams,
): Promise<any> {
  const url = `${V2_API_BASE}/api/pools/${poolId}/members`;
  return fetchV2(url, { method: "POST", body: params });
}

export async function removePoolMembers(
  poolId: number,
  symbols: string[],
): Promise<any> {
  const url = `${V2_API_BASE}/api/pools/${poolId}/members`;
  return fetchV2(url, { method: "DELETE", body: { symbols } });
}
```

- [ ] **Step 2: 类型检查**

Run: `cd agent-ts && npx tsc -p tsconfig.build.json --noEmit`
Expected: 无错误

- [ ] **Step 3: Commit**

```bash
cd /Users/mac/Documents/ai/pi-investment/.claude/worktrees/pool-member-ops
git add agent-ts/src/infrastructure/adapters/quant/quant-v2-client.ts
git commit -m "feat(agent): quant-v2-client 增加 addPoolMembers/removePoolMembers"
```

---

### Task 5: pool_manage 工具 — add_member / remove_member action

**Files:**
- Modify: `agent-ts/src/infrastructure/tools/pool/pool-manage-tool.ts`
- Test: `agent-ts/src/infrastructure/tools/pool/pool-manage-tool.test.ts`（新建）

- [ ] **Step 1: 写失败测试**

新建 `agent-ts/src/infrastructure/tools/pool/pool-manage-tool.test.ts`（沿用 `watch-manage-tool.test.ts` 的 `jest.unstable_mockModule` 模式；mock 必须导出 pool-manage-tool  import 的全部名字）：

```typescript
import { beforeEach, describe, expect, it, jest } from "@jest/globals";

const mockAddPoolMembers = jest.fn<(...args: any[]) => Promise<any>>();
const mockRemovePoolMembers = jest.fn<(...args: any[]) => Promise<any>>();

jest.unstable_mockModule("../../adapters/quant/quant-v2-client.js", () => ({
  createPool: jest.fn(),
  listPools: jest.fn(),
  getPool: jest.fn(),
  updatePool: jest.fn(),
  deletePool: jest.fn(),
  refreshPool: jest.fn(),
  scanAndCreatePool: jest.fn(),
  updatePoolMember: jest.fn(),
  scanPoolSignals: jest.fn(),
  addPoolMembers: mockAddPoolMembers,
  removePoolMembers: mockRemovePoolMembers,
}));

const { poolManageTool } = await import("./pool-manage-tool.js");

beforeEach(() => {
  mockAddPoolMembers.mockReset();
  mockRemovePoolMembers.mockReset();
});

const exec = (params: any) => poolManageTool.execute("test-id", params);

describe("pool_manage add_member", () => {
  it("缺 pool_id 报错且不调用 client", async () => {
    const result = await exec({ action: "add_member", symbols: ["600519.SH"] });
    expect(result.content[0].text).toContain("add_member 需要 pool_id");
    expect(mockAddPoolMembers).not.toHaveBeenCalled();
  });

  it("空 symbols 报错且不调用 client", async () => {
    const result = await exec({ action: "add_member", pool_id: 1, symbols: [] });
    expect(result.content[0].text).toContain("symbols");
    expect(mockAddPoolMembers).not.toHaveBeenCalled();
  });

  it("映射到 addPoolMembers 并传元数据", async () => {
    mockAddPoolMembers.mockResolvedValue({
      success: true,
      data: {
        pool: { id: 1, name: "测试池", members: [{ symbol: "600519.SH" }] },
        added: ["600519.SH"],
        skipped: [],
      },
    });
    const result = await exec({
      action: "add_member", pool_id: 1, symbols: ["600519.SH"],
      member_description: "关注", tags: ["白酒"],
    });
    expect(mockAddPoolMembers).toHaveBeenCalledWith(1, {
      symbols: ["600519.SH"],
      description: "关注",
      buy_point: undefined,
      sell_point: undefined,
      tags: ["白酒"],
    });
    expect(result.content[0].text).toContain("600519.SH");
  });

  it("输出包含 skipped 与动态池 warning", async () => {
    mockAddPoolMembers.mockResolvedValue({
      success: true,
      data: {
        pool: { id: 1, name: "动态池", members: [{ symbol: "600519.SH" }] },
        added: [],
        skipped: ["600519.SH"],
        warning: "动态池 refresh 将按筛选条件重建成员，手动增删的成员可能被覆盖",
      },
    });
    const result = await exec({ action: "add_member", pool_id: 1, symbols: ["600519.SH"] });
    const text = result.content[0].text;
    expect(text).toContain("跳过");
    expect(text).toContain("600519.SH");
    expect(text).toContain("⚠️");
    expect(text).toContain("refresh");
  });
});

describe("pool_manage remove_member", () => {
  it("缺 symbols 报错且不调用 client", async () => {
    const result = await exec({ action: "remove_member", pool_id: 1 });
    expect(result.content[0].text).toContain("symbols");
    expect(mockRemovePoolMembers).not.toHaveBeenCalled();
  });

  it("映射到 removePoolMembers 并格式化输出", async () => {
    mockRemovePoolMembers.mockResolvedValue({
      success: true,
      data: {
        pool: { id: 1, name: "测试池", members: [] },
        removed: ["000858.SZ"],
        skipped: ["999999.SH"],
      },
    });
    const result = await exec({
      action: "remove_member", pool_id: 1, symbols: ["000858.SZ", "999999.SH"],
    });
    expect(mockRemovePoolMembers).toHaveBeenCalledWith(1, ["000858.SZ", "999999.SH"]);
    const text = result.content[0].text;
    expect(text).toContain("000858.SZ");
    expect(text).toContain("999999.SH");
  });
});
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd agent-ts && npm test -- src/infrastructure/tools/pool/pool-manage-tool.test.ts`
Expected: FAIL — `addPoolMembers is not a function`（client 尚未被工具引用/参数校验不存在）

注意：必须用 `npm test`（package.json 已带 `--experimental-vm-modules`），裸 `npx jest` 会误报 TS1378。

- [ ] **Step 3: 实现工具改动**

对 `agent-ts/src/infrastructure/tools/pool/pool-manage-tool.ts` 做四处修改：

**3a. import 增加两个函数：**

```typescript
import {
  createPool,
  listPools,
  getPool,
  updatePool,
  deletePool,
  refreshPool,
  scanAndCreatePool,
  updatePoolMember,
  scanPoolSignals,
  addPoolMembers,
  removePoolMembers,
} from "../../adapters/quant/quant-v2-client.js";
```

**3b. description 文案更新**（替换现有 description 字符串）：

```typescript
  description:
    "管理股票池：创建静态/动态池、列出所有池、查看详情、更新、删除、刷新动态池、筛选建池、扫描信号。" +
    "动态池保存筛选条件(filter_template)，可定时自动刷新。" +
    "筛选建池(scan_create)：执行多因子扫描后自动创建池子。" +
    "成员管理：add_member 批量加股票（幂等，可附描述/买点/卖点/标签），remove_member 批量删股票，" +
    "update_member 更新单个股票的描述/买点/卖点/标签，get_member 查看单个股票详情。" +
    "注意：动态池的成员由 filter_template 定时重建，add_member/remove_member 的手动改动可能在 refresh 时被覆盖。" +
    "信号扫描(scan_signals)：对池内所有股票执行策略，检测实时买卖信号。",
```

**3c. action 联合类型与 symbols 参数描述**：

```typescript
    action: Type.Union(
      [
        Type.Literal("create"),
        Type.Literal("list"),
        Type.Literal("get"),
        Type.Literal("update"),
        Type.Literal("delete"),
        Type.Literal("refresh"),
        Type.Literal("scan_create"),
        Type.Literal("add_member"),
        Type.Literal("remove_member"),
        Type.Literal("update_member"),
        Type.Literal("get_member"),
        Type.Literal("scan_signals"),
      ],
      { description: "操作类型" },
    ),
```

`symbols` 参数描述改为：`"股票代码列表 (create static 手动指定；add_member/remove_member 批量增删)"`；`member_description`/`buy_point`/`sell_point`/`tags` 描述各加 `(add_member/update_member 使用)`。

**3d. execute 的 switch 新增两个分支**（放在 `case "update_member"` 之前）：

```typescript
        case "add_member":
          if (!pool_id) return _err("add_member 需要 pool_id 参数");
          if (!symbols || symbols.length === 0) {
            return _err("add_member 需要 symbols 参数（非空数组）");
          }
          result = await addPoolMembers(pool_id, {
            symbols,
            description: member_description,
            buy_point,
            sell_point,
            tags,
          });
          break;

        case "remove_member":
          if (!pool_id) return _err("remove_member 需要 pool_id 参数");
          if (!symbols || symbols.length === 0) {
            return _err("remove_member 需要 symbols 参数（非空数组）");
          }
          result = await removePoolMembers(pool_id, symbols);
          break;
```

**3e. `_formatResult` 新增两个分支**（放在 `case "update_member"` 之前）：

```typescript
    case "add_member": {
      const added: string[] = data.added || [];
      const skipped: string[] = data.skipped || [];
      const members = data.pool?.members || [];
      let text = `✅ 已添加 ${added.length} 只股票` +
        (added.length > 0 ? `: ${added.join(", ")}` : "") + "\n";
      if (skipped.length > 0) {
        text += `⏭️ 跳过（已在池中）: ${skipped.join(", ")}\n`;
      }
      text += `  当前池成员: ${members.length}只`;
      if (data.warning) text += `\n⚠️ ${data.warning}`;
      return text;
    }

    case "remove_member": {
      const removed: string[] = data.removed || [];
      const skipped: string[] = data.skipped || [];
      const members = data.pool?.members || [];
      let text = `🗑️ 已移除 ${removed.length} 只股票` +
        (removed.length > 0 ? `: ${removed.join(", ")}` : "") + "\n";
      if (skipped.length > 0) {
        text += `⏭️ 跳过（不在池中）: ${skipped.join(", ")}\n`;
      }
      text += `  当前池成员: ${members.length}只`;
      if (data.warning) text += `\n⚠️ ${data.warning}`;
      return text;
    }
```

- [ ] **Step 4: 跑测试确认通过**

Run: `cd agent-ts && npm test -- src/infrastructure/tools/pool/`
Expected: 全部 PASS（含原有 pool-optimization.test.ts）

- [ ] **Step 5: Commit**

```bash
cd /Users/mac/Documents/ai/pi-investment/.claude/worktrees/pool-member-ops
git add agent-ts/src/infrastructure/tools/pool/pool-manage-tool.ts agent-ts/src/infrastructure/tools/pool/pool-manage-tool.test.ts
git commit -m "feat(agent): pool_manage 增加 add_member/remove_member 批量成员管理"
```

---

### Task 6: 文档更新（agent-ts/CLAUDE.md L2.7）

**Files:**
- Modify: `agent-ts/CLAUDE.md`（L2.7 股票池管理层一节）

- [ ] **Step 1: 更新文档**

在 `agent-ts/CLAUDE.md` L2.7 一节的 `pool_manage` 条目改为：

```markdown
- `pool_manage` — 股票池 CRUD（创建/列表/查看/更新/删除/刷新/筛选建池）
  - 支持静态池（手动指定stocks）和动态池（保存filter_template，可定时刷新）
  - `scan_create` 操作：执行多因子扫描后自动创建池子
  - `add_member` / `remove_member`：批量增删池成员（幂等；动态池手动改动可能在 refresh 时被覆盖，响应附 warning）
  - `update_member` / `get_member`：单成员元数据（描述/买点/卖点/标签）管理
```

并在该节 **API 端点** 列表中 `POST /api/pools/:id/refresh` 之后插入两行：

```markdown
- `POST /api/pools/:id/members` — 批量添加池成员
- `DELETE /api/pools/:id/members` — 批量移除池成员
```

- [ ] **Step 2: Commit**

```bash
cd /Users/mac/Documents/ai/pi-investment/.claude/worktrees/pool-member-ops
git add agent-ts/CLAUDE.md
git commit -m "docs(agent): CLAUDE.md L2.7 补充 add_member/remove_member 与成员端点"
```

---

### Task 7: 全量回归验证

- [ ] **Step 1: Python 全量相关测试**

Run: `cd quantsys-v2 && source activate-py313.sh && python -m pytest tests/test_stock_pool_service.py tests/api/test_pools_routes.py tests/migration/test_pools_parity.py -v`
Expected: 全部 PASS

- [ ] **Step 2: TS 全量测试**

Run: `cd agent-ts && npm test`
Expected: 全部 PASS（关注 pool、tools 相关套件无回归）

- [ ] **Step 3: TS 构建检查**

Run: `cd agent-ts && npx tsc -p tsconfig.build.json --noEmit`
Expected: 无错误
