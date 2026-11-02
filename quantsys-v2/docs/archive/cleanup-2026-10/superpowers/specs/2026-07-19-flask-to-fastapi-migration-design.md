# Flask → FastAPI 全量迁移总体设计

- **日期**: 2026-07-19
- **状态**: 已批准（目标/策略/验证方式已与用户确认）
- **范围**: quantsys-v2 后端 `adapters/inbound/api/`（Flask）→ `adapters/inbound/fastapi_app/`（FastAPI）
- **本文档**: 总体设计（epic）。每个 Phase 单独走 spec → plan → 实现 循环。

---

## 1. 背景与问题

系统曾启动 Flask → FastAPI 迁移（CLAUDE.md 记载 2026-06-29 "已完成"），但实际**远未完成**：

- 生产 5001 端口仍跑旧 **Flask** `adapters/inbound/api/server.py`。
- FastAPI 端虽生成了 62 个路由文件，其中 **37 个是自动生成的 TODO 空桩**（`dividends_async.py` 即其一），注册时被 `try/except ImportError` 静默跳过。
- 这直接导致线上 bug：agent 的 `data_fetch_dividend` screen 模式返回 0（空桩无逻辑）。

### 量化缺口（ground truth，基于真实启动的 FastAPI `/openapi.json`）

| 项 | 数量 |
|----|------|
| Flask 端点总数 | 426（61 路由文件 / 56 blueprint） |
| FastAPI 当前**真实可服务**路径 | 111 |
| **web-frontend 需要的路径** | **169** |
| 已覆盖 | 15 |
| **缺失（web 无法用 FastAPI）** | **154，跨 33 个域** |
| agent-ts 需要的路径 | ~180 |
| 冗余 server 入口文件 | 7（main / server / server_final / server_100_complete / server_async / server_complete / websocket_server） |

> 注：web-frontend 当前连 Flask（5001）所以能用；一旦切到 FastAPI，154/169 接口 404。本设计的目标是消除这 154 个缺口。

缺失端点按域分布（Top）：stocks(21)、strategies(14)、agent控制(12)、pools(12)、indicators(9)、signals(9)、risk(8)、data(7)、portfolio(6)、analysis(5)、ml(5)、orders(5)、pipeline(5)、executions(4)、scheduler(4)、v{id}(4)、jobs(3)，及一批 1-2 个的长尾域。

## 2. 目标与非目标

### 目标（已确认）
- **核心目标**：web-frontend 调用 v2（FastAPI，5001）全部可用。
- 逐域迁移 154 个缺失端点，最后统一切换、下线 Flask。

### 非目标（本期不做）
- 不重构 service / repository 业务逻辑层（原样复用）。
- 不迁移 web-frontend 用不到的纯遗留/管理端点（426 全量中非 web 非 agent 的部分）——除非某个域顺带覆盖。
- 不改变任何 API 的请求/响应契约（web 依赖精确形状）。

## 3. 关键设计决策（已与用户确认）

| 决策点 | 结论 |
|--------|------|
| 核心目标 | 保证 web 端调用 v2 可用 |
| 迁移策略 | **逐域迁移（big-bang per domain），全部完成后统一切换** |
| 验证方式 | **Flask ↔ FastAPI 响应比对（parity）框架** |
| 切入点 | 第一个实现周期 = P0（框架+入口收敛）+ P1（stocks 域垂直切片） |

## 4. 迁移机制（为什么可行）

关键观察：**Flask 路由几乎全是薄封装**——解析请求 → 调用 `application/services/` → `jsonify` 返回。业务逻辑与框架无关。

迁移 = **逐域把路由层从 Flask 改写成 FastAPI，service 层原样复用**。

标准映射模式：

```python
# Flask
@stocks_bp.route('/api/stocks/list', methods=['GET'])
@handle_errors
def list_stocks():
    market = request.args.get('market')
    result = service.list_stocks(market)
    return jsonify(result)

# FastAPI
@router.get('/api/stocks/list')
async def list_stocks(market: Optional[str] = Query(None)):
    return service.list_stocks(market)   # dict，FastAPI 自动序列化
```

映射规则：
- `request.args.get('x', default)` → `x: Optional[T] = Query(default)`
- `request.get_json()` → Pydantic `BaseModel` 或 `Body(...)`
- `jsonify(result)` → `return result`（保持 dict 结构一致）
- `@handle_errors` → FastAPI 异常处理（保持错误响应 `{success: False, error: ...}` 形状一致）
- **契约冻结**：响应 JSON 的字段名、嵌套结构、类型必须与 Flask 一致（timestamp 等易变字段的值除外，见 §5 忽略清单），由 parity 框架强制保证。

## 5. 安全网：Parity 响应比对框架（P0 先建）

这是让"big-bang 切换"真正安全的核心。**先于任何域迁移建立**，之后每个域迁移都用它验收。

### 工作方式
1. 测试时同时起两个实例：Flask（内部端口 5002）+ FastAPI（5001 或测试端口）。
2. 对每个已迁移端点，用**相同输入**分别请求两边。
3. **diff JSON 响应**：状态码一致；响应体深度比对，忽略易变字段（timestamp、trace_id、duration 等，配置化忽略清单）。
4. 读端点（GET）做全量 diff；写端点（POST/PUT/DELETE）比对响应形状 + 副作用（DB 状态）在测试库验证。

### 落地形态
- 每个域一个 `tests/migration/test_<domain>_parity.py`。
- 共享比对工具 `tests/migration/parity.py`：发起双请求、规范化（排序/去易变字段）、输出可读 diff。
- 全部跑在**测试库**（`quant_test`），符合项目既有的 test/prod 库隔离与安全机制。
- 每个 Phase 的完成标准 = 该域 parity 测试全绿。

## 6. 分期计划

按依赖、体量、风险排序。每期 = 独立 spec → plan → 实现 → parity 验收。

| 期 | 域 | 端点数 | 说明 |
|----|----|:--:|------|
| **P0** | parity 比对框架 + 入口收敛 | — | 地基。合并 7 server→`main.py`；删除 37 空桩（被真实实现取代）；明确唯一启动入口 |
| **P1** | stocks | 21 | 最大、最基础的域，作为垂直切片验证整个模式 |
| **P2** | strategies(+strategy) | 15 | 核心 |
| **P3** | signals + pools | 21 | 核心 |
| **P4** | agent 控制 + scheduler + jobs | 19 | agent 运维 |
| **P5** | portfolio + orders + trades + executions + trading + v{id} | 21 | 交易链路 |
| **P6** | risk + analysis + indicators + compute | 23 | 分析 |
| **P7** | data + config + adapters + client + simulation + report | 13 | 数据/配置 |
| **P8** | ml + pipeline + diagnosis + decisions + knowledge + learning + backtest + alerts + chan | 21 | 长尾 |
| **P9** | **切换 + Flask 下线** | — | 见 §7 |

> 每期完成后更新本表的进度勾选。端点数为 web-frontend 缺失口径；实现时顺带覆盖该域内 agent 需要的端点。

## 7. 切换方案（P9）

1. P0–P8 全部 parity 通过。
2. **全量回归**：parity 框架对 169 个 web 端点 + ~180 个 agent 端点整体跑一遍。
3. 切换：web-frontend `API_BASE_URL` 本就是 `127.0.0.1:5001`（无需改代码）；停 Flask、起 FastAPI。
4. **灰度/回滚**：保留 Flask 代码 1–2 周；若发现问题，改回进程即可秒级回滚。稳定后删除 Flask `adapters/inbound/api/` 与相关文档。

## 8. 入口收敛与清理（P0 一部分）

- **唯一入口**：FastAPI `adapters/inbound/fastapi_app/main.py`（REST 5001）+ `websocket_server.py`（5003）。
- 删除冗余 server 文件：`server.py` / `server_final.py` / `server_100_complete.py` / `server_async.py` / `server_complete.py`。
- 删除 37 个空桩 `*_async.py`（真实实现落在对应域文件，命名保持 `*_async.py` 或并入主文件，由第一期确定命名约定）。
- `register_routes()` 的 `try/except ImportError` 静默跳过机制改为**显式注册**（缺失即报错），杜绝"桩被静默跳过"这类隐患。
- 修正文档：`start_all.py` 已不存在，CLAUDE.md 的启动说明需同步更新。

## 9. 风险与缓解

| 风险 | 缓解 |
|------|------|
| 响应形状不一致导致 web 前端异常 | parity 框架逐端点 diff，契约冻结，不一致不过验收 |
| 154 端点盲迁出 bug | 先建框架；每期 parity 验收；逐域推进而非一次性 |
| service 层隐式依赖 Flask 上下文（request g 等） | 迁移时排查；service 本就框架无关，个别依赖在路由层解耦 |
| 切换期线上故障 | 保留 Flask 可秒级回滚；灰度观察 1-2 周 |
| 工作量超预期（154 端点） | 分期交付，每期可独立验收；P1 垂直切片先验证效率再排后续 |

## 10. 成功标准

- FastAPI 启动后 `/openapi.json` 覆盖 web-frontend 全部 169 个端点（及 agent 的 ~180 个）。
- 全部 9 期 parity 测试通过。
- web-frontend 指向 FastAPI 后各页面功能正常，Flask 安全下线。
