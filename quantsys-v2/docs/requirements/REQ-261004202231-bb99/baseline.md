# 删除前基线（REQ-261004202231-bb99）

> **为什么有这份文件**：`design/architecture.md` 的「行为等价验证设计」要求**删前取基线**——
> 一旦 t2/t3 落地，非记忆端点的现状与测试总数就再也抓不到了。本文件即那份基线，供删除后逐项比对。
> 抓取时间：**2026-10-04 21:5x**（本机，服务运行中）。

## 一、非记忆端点（删除后必须不变）

| 端点 | 状态码 | 体积 | 响应片段 |
|---|---|---|---|
| `GET /api/health` | **200** | 163 B | `{"status":"ok","db_connected":true,"db_info":{...}}` |
| `GET /api/stock/600519/klines` | **200** | 9,553 B | `{"symbol":"600519","count":65,"klines":[...]}` |
| `GET /api/simulation/accounts` | **200** | 1,398 B | `{"success":true,"data":{"accounts":[{"account_name":"v15_simulation",...}]}}` |

## 二、记忆端点（本次删除对象，删除后应全部 404）

| 端点 | 状态码（删前） |
|---|---|
| `GET /api/memory/health` | 200 |
| `GET /api/memory/search` | 200 |
| `GET /api/memory/recall-audit/stats` | 200 |

## 三、测试基线

- **收集总数：6,565**（`./venv/bin/python -m pytest tests/ -q --collect-only` → `6565 tests collected`）
  —— 删除 `tests/domain/memory/` 后，总数应与「基线 − 被删用例数」**一致**。
- 分层纯净性：见下方当时输出（`pytest tests/test_layer_purity.py -q`）——
  删除 `domain/memory`（含 `domain→adapters` / `domain→infrastructure` 方向违规）后，该基线**只允许下降**。
  **实测解读**：当前 **322 条**（阈值 318）→ 该用例此刻是 **failed**；输出里可见多条正是
  `domain/memory/distiller.py` 自己造成的（删它会直接消掉这些行），其余条目属**其它需求在飞改动**
  （如 `domain/trading/services/trade_guard_service.py`），不由本需求负责，也不该由本需求「顺手」修。

```
E     domain/memory/distiller.py: domain → adapters.outbound.repositories.agent_intelligence_repository
E     domain/memory/distiller.py: domain → adapters.outbound.repositories.memory_repository
E     domain/memory/distiller.py: domain → infrastructure.persistence.orm（顶层）
E     domain/trading/services/trade_guard_service.py: domain → application.services.trading_calendar_service
E   assert 322 <= 318
=========================== short test summary info ============================
FAILED tests/test_layer_purity.py::test_total_layer_violations_do_not_increase
========================= 1 failed, 1 skipped in 2.69s =========================
```

## 四、agent 侧基线（记忆的新家）

- `agent-os :8080` **已可用**（2026-10-04 本机重建，见 `agent-dh/docs/work-logs/2026-10/agent-os-restore.md`）：
  `/health` ok；`POST /api/v1/memory` 可写；`GET /api/v1/memory?category=experience&limit=100` → `{memories:[…],total:1}`。
- 看板 M6 探针（t8 改造后）用的正是上面那个 URL → 当日新增 1 → 探针判 `confirmed`。

## 五、重跑命令

```bash
curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:5001/api/health
curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:5001/api/stock/600519/klines
curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:5001/api/simulation/accounts
curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:5001/api/memory/search     # 删后应为 404
./venv/bin/python -m pytest tests/ -q --collect-only | tail -1
./venv/bin/python -m pytest tests/test_layer_purity.py -q | tail -3
```
