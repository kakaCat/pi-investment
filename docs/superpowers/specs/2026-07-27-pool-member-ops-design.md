# 股票池 add_member / remove_member 工具设计

- **日期**：2026-07-27
- **状态**：已确认（用户已批准设计）
- **Worktree**：`.claude/worktrees/pool-member-ops`，分支 `feat/pool-member-ops`

## 背景与目标

agent 目前无法直接往已有股票池加/删股票：`pool_manage` 只有 `update_member`（改描述/买点/卖点/标签）和 `get_member`，没有 add/remove 动作；后端 Flask 也只有 `PUT /api/pools/<id>/members/<symbol>`（更新），没有 add/remove 端点。唯一迂回路径是 `update` 全量替换 symbols——容易出错且不同步 members 元数据。

**目标**：为 agent 提供 `pool_manage` 的 `add_member` / `remove_member` 动作，支持批量、幂等、动态池警告，数据链路为：agent 工具 → TS client → Flask API（+ FastAPI parity 镜像）→ StockPoolService。

## 关键决策（已与用户确认）

1. **工具形态**：扩展现有 `pool_manage`（新增两个 action），不新建工具。
2. **批量**：`symbols` 数组，一次调用可加/删多只。
3. **动态池**：允许手动增删，但响应附带 warning（refresh 会按 filter_template 重建成员，手动改动可能被覆盖）。
4. **FastAPI parity**：FastAPI 侧同步加端点（加在 `pools_async.py`——Flask 路由的完整镜像文件；`fastapi_app/routes/pools.py` 是只有基础 CRUD 的新式 DDD 路由，不动）。

## 方案选型

采用 **RESTful 批量端点**（方案 A）：

- `POST /api/pools/<id>/members`（body: `{symbols, description?, buy_point?, sell_point?, tags?}`）
- `DELETE /api/pools/<id>/members`（body: `{symbols}`）

否决的替代方案：
- 复用 `update` 全量替换 symbols：agent 需传全量列表，易错且 members 元数据不同步。
- 单端点操作语义 `POST .../members/ops {op}`：不符合现有路由风格。

## 详细设计

### 1. 后端 Service（`quantsys-v2/application/services/stock_pool_service.py`）

新增两个方法，风格对齐现有 `update_member`：

**`add_members(pool_id, symbols, member_data=None) -> dict`**
- 池不存在 → `ValueError(f"Pool {pool_id} not found")`（路由转 404）
- 幂等：已在池中的 symbol 跳过，记入 `skipped`
- 新成员结构：`{symbol, name, description, buy_point, sell_point, tags}`；`name` 用 `stock_repo.batch_get_names(new_symbols)` 补齐；`member_data` 的可选元数据应用到所有本次新增成员
- 同时维护两个字段：`symbols`（list）与 `members`（JSON list），一次 `pool_repo.update(pool_id, {'symbols': ..., 'members': ...})`
- 返回：`{pool: <更新后池详情>, added: [...], skipped: [...], warning?: str}`
- `pool_type == 'dynamic'` 时附 `warning`：动态池 refresh 将按筛选条件重建成员，手动增删可能被覆盖

**`remove_members(pool_id, symbols) -> dict`**
- 池不存在 → `ValueError`（404）
- 不在池中的 symbol 跳过，记入 `skipped`
- 同步从 `symbols` 与 `members` 中移除，一次 update
- 返回：`{pool, removed: [...], skipped: [...], warning?: str}`（动态池同样附 warning）

**一致性要求**：`symbols` 与 `members` 必须同步更新（参照 `update_member` 对 members 的重建逻辑——若 members 为空则先从 symbols 重建再操作，保持两个字段不漂移）。

### 2. 后端路由

**Flask（`quantsys-v2/adapters/inbound/api/routes/pools.py`）**：

```
POST   /api/pools/<int:pool_id>/members    body: {symbols: [...], description?, buy_point?, sell_point?, tags?}
DELETE /api/pools/<int:pool_id>/members    body: {symbols: [...]}
```

- 校验：`symbols` 缺失或非空数组 → 400 `{success: false, error}`
- 错误码与现有路由对齐：`ValueError` → 404，其他异常 → 500，均包 `{success, error}`
- 成功响应：`{success: true, data: <service 返回值>}`
- body 字段兼容 camelCase/snake_case（`buyPoint`/`buy_point`），与现有 `update_member` 路由一致

**FastAPI parity（`quantsys-v2/adapters/inbound/fastapi_app/routes/pools_async.py`）**：
- 镜像上述两个路由（该文件使用全路径风格 `@router.post('/api/pools/{pool_id}/members')`），行为与 Flask 逐字节对齐，复用同一 service 方法

### 3. TS Client（`agent-ts/src/infrastructure/adapters/quant/quant-v2-client.ts`）

新增，风格对齐 `updatePoolMember`：

```ts
export interface PoolMembersAddParams {
  symbols: string[];
  description?: string;
  buy_point?: string;
  sell_point?: string;
  tags?: string[];
}
export async function addPoolMembers(poolId: number, params: PoolMembersAddParams): Promise<any>
export async function removePoolMembers(poolId: number, symbols: string[]): Promise<any>
```

### 4. Agent 工具（`agent-ts/src/infrastructure/tools/pool/pool-manage-tool.ts`）

- `action` 联合类型新增 `"add_member"` / `"remove_member"`
- 参数复用：现有 `symbols`（数组）+ `member_description` / `buy_point` / `sell_point` / `tags`（add 时可选元数据）
- 校验：`add_member` / `remove_member` 需要 `pool_id` 和非空 `symbols`
- `description` 文案补充两个 action 的用法说明与动态池警告提示
- `_formatResult` 新增两个分支，输出：
  - ✅ 已添加/已移除的 symbols（含名称）
  - ⏭️ 跳过的 symbols 及原因（已在池中 / 不在池中）
  - ⚠️ 动态池 warning（若返回）
  - 当前池成员总数

### 5. 测试

**Python**（`quantsys-v2/tests/api/test_pools_routes.py` 增补用例）：
- add 正常路径（含名称补齐、元数据落库）
- add 幂等（重复 symbol 进 skipped）
- remove 正常路径（symbols/members 同步移除）
- remove 不在池中 symbol 进 skipped
- 池不存在 → 404
- symbols 缺失/空数组 → 400
- 动态池 → 响应含 warning

**TypeScript**（pool 工具测试，参照 `pool-optimization.test.ts` 风格，mock client）：
- `add_member` / `remove_member` 参数校验（缺 pool_id / 空 symbols 报错）
- 格式化输出包含 added/removed、skipped、warning

## 影响面

- 改动文件：
  - `quantsys-v2/application/services/stock_pool_service.py`
  - `quantsys-v2/adapters/inbound/api/routes/pools.py`
  - `quantsys-v2/adapters/inbound/fastapi_app/routes/pools_async.py`
  - `quantsys-v2/tests/api/test_pools_routes.py`（或新增测试文件）
  - `agent-ts/src/infrastructure/adapters/quant/quant-v2-client.ts`
  - `agent-ts/src/infrastructure/tools/pool/pool-manage-tool.ts`
  - agent-ts 新增工具测试文件
- 不改动：`fastapi_app/routes/pools.py`（新式 DDD 路由，非 parity 镜像）、`pool-validate-tool.ts`、web-frontend
- 端口/IP 不涉及（worktree 规则：不引入非固定 IP）

## 验收标准

1. agent 可通过 `pool_manage({action: "add_member", pool_id, symbols: [...]})` 批量加股票，重复加幂等
2. agent 可通过 `pool_manage({action: "remove_member", pool_id, symbols: [...]})` 批量删股票
3. 动态池操作返回覆盖警告
4. Flask 与 FastAPI 两端点行为一致（parity）
5. Python 与 TS 测试全部通过（agent-ts 用 `npm test`，quantsys-v2 用 `python -m pytest`）
