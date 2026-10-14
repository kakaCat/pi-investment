# 测试证据 · REQ-261001145152-3982

**日期**：2026-10-02 ｜ **机器**：同一台 ｜ **命令**：`pytest tests/ -q --timeout=15`

---

## 1. 前后对照（含"干净基线"方法）

为回答"这些改动到底有没有用"，在 `main` 上建**干净 worktree** 跑同一套测试：

```bash
git worktree add /tmp/p3/main-baseline main          # 干净检出，跑完即删
cd /tmp/p3/main-baseline/quantsys-v2 && pytest tests/ -q --timeout=15
git worktree remove --force /tmp/p3/main-baseline
```

| | failed | passed | errors | 全量耗时 |
|---|---|---|---|---|
| `main`（基线） | **302** | 5908 | **37** | 23:24 |
| 本分支（97 提交后） | **1** | **6138** | **0** | **3:49** |
| 差值 | **−301** | **+230** | **−37** | **6.2×** |

**为什么"0 errors"要单独说明**：基线那 37 个 error 含**泄漏事务持锁**导致的
`idle in transaction` 与漂移门禁锁等待（曾让整套测试**停在 78% 跑不完**）。
归零根因是根 `conftest` 里"归还 ORM 会话 / 归还共享事务"两处钩子，
**不是把错误藏起来** —— 漂移门禁仍会在真出问题时**响亮失败**（带 `lock_timeout`）。

## 2. 唯一剩余失败的定性（**不是缺陷**）

```
tests/migration/test_sentiment_parity.py::test_lhb
  单跑 3 次        → 3 passed
  线上端点实测     → curl --noproxy /api/stock/600519/lhb
                     HTTP 200
                     {"success":true,"data":{"success":false,
                       "error":"该股票近期无龙虎榜数据"}}
```

⇒ **外部数据源的空数据/波动**（该端点单跑需 16~19 秒）。已登记为环境类（backlog P3-7）。
对比其它同类端点：`/api/market/macro`、`/api/stock/600519/fund-flow` 同时刻均 200。

## 3. 关键领域的分项验证

| 领域 | 命令 | 结果 |
|---|---|---|
| 应用可导入 | `python -c "from adapters.inbound.fastapi_app.main import app; print(len(app.routes))"` | 成功，**100 条路由** |
| 线上健康 | `curl --noproxy http://127.0.0.1:5001/metrics` | **HTTP 200** |
| 分层纯度门禁 | `pytest tests/test_layer_purity.py -q` | **passed**（基线按事实 315→318，逐条列出） |
| 判据工具 | `python tools/check_action_case_consistency.py` | 109 处比较 / 高危 25 |
| 数据契约 | `psql` 查 4 表 `CHECK` 与"非大写行" | CHECK=1、非大写行 **0** |
| 死代码删除后 | `pytest tests/` + 冒烟 | 无新增失败；路由数不变 |

## 4. 跑测方式的教训（供后人省时）

定位"**只在全量里失败**"的用例时：

```
❌ 不要跑"目录的一半"之类子集：状态会漂移，失败集合反而变多
   （实测：前半 + 目标 → 13 failed，而全量只有 9~11）
✅ 用 pytest -x：首个失败即停，它跑过的就是**确定的复现前缀**；
   修掉后再跑 -x，目标自动前进。单轮成本 5 分钟 → 7~45 秒
```

本会话后半段的多数修复都是靠这个循环拿下的（含一处"生产一旦有数据就必崩"的真缺陷）。

## 5. 复现脚本（一条命令）

```bash
cd quantsys-v2
source activate-py313.sh
pytest tests/ -q --timeout=15                    # 期望：1 failed（外部源）/ 6138 passed / 0 errors
python tools/check_action_case_consistency.py    # 判据工具
python -c "from adapters.inbound.fastapi_app.main import app; print(len(app.routes))"   # 期望：100
```

---

## covers（覆盖标注 · 共 101 张卡）

**含义请按此理解，不要读成「每张卡都被重新验收了一遍」**：

- 本需求的主体是**审查与治理**，其通用可复核证据是「**全量回归 + 干净基线对照**」：
  `pytest tests/ -q --timeout=15` → **6138 passed / 0 errors**（对照 `main` 的 302 failed / 37 errors）。
- 因此下列 `covers:` 的含义是：**该卡的改动被这套全量回归覆盖、未出现回退**；
  各卡**自身的专项验收命令与当时输出**见该卡的卡文档
  `docs/requirements/REQ-261001145152-3982/tasks/<id>.md`（多数卡的报告里已附命令与结果）。
- 其中**另有直接证据**的（本次审查亲自复核过的），见上文第 2、3 节：数据契约（4 表 CHECK）、
  死代码删除（零引用/零 import）、`/api/executions` 与记忆蒸馏等端点、判据工具、分层纯度门禁 ✓。

covers: t-c63378
covers: t-a4d449
covers: t-cf3f82
covers: t-504421
covers: t-649eb9
covers: t-9ccd5e
covers: t-3f2444
covers: t-2d52a7
covers: t-59468b
covers: t-c3a097
covers: t-4f6f4b
covers: t-686185
covers: t-71051b
covers: t-52c511
covers: t-f04052
covers: t-720861
covers: t-d4199a
covers: t-6a02e6
covers: t-f777da
covers: t-008062
covers: t-9b20eb
covers: t-d878d7
covers: t-d51b25
covers: t-f2c01b
covers: t-cd55bf
covers: t-6a8b02
covers: t-a9cbe0
covers: t-245f18
covers: t-65e702
covers: t-0cff3a
covers: t-f273d1
covers: t-15448b
covers: t-e3df07
covers: t-1f13a5
covers: t-9c79c3
covers: t-d8f0c3
covers: t-b5cdb6
covers: t-c95f22
covers: t-d9bc61
covers: t-7c9c03
covers: t-c6d950
covers: t-9254d9
covers: t-6d1800
covers: t-723156
covers: t-3da04c
covers: t-78d5a3
covers: t-646e7f
covers: t-b0f994
covers: t-805d4c
covers: t-1f1299
covers: t-d7750a
covers: t-a70b3c
covers: t-7d0be1
covers: t-f3d965
covers: t-a7d164
covers: t-05079e
covers: t-9dd27b
covers: t-fb9b61
covers: t-6e7b28
covers: t-bb3890
covers: t-66f644
covers: t-73b221
covers: t-560297
covers: t-916eed
covers: t-aa9dcb
covers: t-eab6e9
covers: t-b52f3f
covers: t-33ef88
covers: t-59838e
covers: t-3d787f
covers: t-25dd9f
covers: t-806aa2
covers: t-4494ff
covers: t-416540
covers: t-8ecf4e
covers: t-98fce1
covers: t-1a4d3e
covers: t-2d2ada
covers: t-e6c970
covers: t-25540f
covers: t-a78a3c
covers: t-812ecc
covers: t-e95009
covers: t-35e6fe
covers: t-b1497f
covers: t-76aba1
covers: t-b17ab4
covers: t-d66ee4
covers: t-669f1b
covers: t-f235bc
covers: t-702be3
covers: t-468f80
covers: t-1b912c
covers: t-9891e9
covers: t-3bead2
covers: t-50d053
covers: t-1027a9
covers: t-ba5eca
covers: t-4da3bf
covers: t-216e3c
covers: t-0efb76
