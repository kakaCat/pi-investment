---
req_id: REQ-261004202231-bb99
title: 验证矩阵（删干净、没删坏）
doc: design/test-cases
serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6
---

# 验证矩阵（REQ-261004202231-bb99）

| # | 判据 | 命令 | 期望 | 实测 |
|---|---|---|---|---|
| TC-1 | 端点全灭 | 对 15 个 `/api/memory*` 逐个 curl | 全 404 | ✅ 全 404 |
| TC-2 | 非记忆端点不受影响 | `curl /api/health`、`/api/simulation/accounts`、`/api/stock/600519/klines` | 200 且形状不变 | ✅ 200 / 163B、200 / 1398B、200 |
| TC-3 | 无残留符号 | `grep -rn 'MemoryService\|MemoryRepository\|domain\.memory\|IMemoryRepository'` 于 domain/application/adapters/infrastructure/tests | 0 命中 | ✅ 0 |
| TC-4 | 启动无记忆注册 | 重启后日志 `grep 'Registered: memory'` / `Failed to import memory` | 0 / 0 | ✅ 0 / 0 |
| TC-5 | 测试总数可解释 | `pytest --collect-only` | 6565 − 被删数 | ✅ 6488（−77） |
| TC-6 | 分层纯净性只降不升 | `pytest tests/test_layer_purity.py` | memory 相关违规 0、总数下降 | ✅ 322 → 319、memory 0 |
| TC-7 | 数据面 | `select count(*) from quant.memory_entries` | relation does not exist | ✅ 两库皆然 |
| TC-8 | 漂移门禁 | `pytest tests/test_orm_db_drift.py` | 全过 | ✅ 6 passed |
| TC-9 | agent-dh 工具清单 | 重建产物 `grep` 五个工具名 | recall_audit=0、其余 4 个在 | ✅ 0 / 7、5、7、3 |
| TC-10 | 看板探针改源 | agent-os 口径 URL 取当日新增 | 能取到数、不可用时 degraded | ✅ 今日新增 1 |
| TC-11 | agent-ts 无 v2 记忆残留 | `grep -rn 'api/memory' agent-ts/src` | 0 命中 | ✅ 0 |
| TC-12 | agent-ts 测试 | 5 个触及的套件 | 全绿 | ✅ 26 条通过 |
