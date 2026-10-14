# 拆分计划（REQ-261003150739-b98d）

**上游**：design/[architecture.md](design/architecture.md)（守卫落点）·
[interfaces.md](design/interfaces.md)（守卫 API 与打桩点契约）·
[test-cases.md](design/test-cases.md)（用例与验收命令）
**目标**：把"测试期真实外发通知"这件事关掉——**修正打桩点**（止住当前的 6 张假卡片）
+ **加一层传输层守卫**（让下一次漏桩变成一条红的用例，而不是一封发给用户的假卡片）。

## TL;DR

```
  4 张卡 / 两条并行支线 / 一个汇合点

  t1 修 test_false_success_guard 打桩点 ┐
                                       ├─▶ t4 回归锁 + 切 fail 模式 + 回滚验证
  t2 e2e 手动触发不再真跑 handler      ┤
                                       │
  t3 守卫模块 + conftest 接线(report)  ┘

  ★ 汇合点 t4 必须先等 t1/t2 修完：否则守卫一装上就是红的（那正是它的设计意图）
```

## 改动盘点（对照设计文档）

| 类别 | 内容 | 规模 | 归属卡 |
|---|---|---|---|
| **修改** | `tests/test_false_success_guard.py` 两处打桩点（alerting → runtime） | 2 行 + 注释 | t1 |
| **修改** | `tests/e2e/test_daily_orchestrator.py` 手动触发用例打桩 `_run_job` | 1 用例 | t2 |
| **新增** | `tests/notify_guard.py`（URL 分类 + 拦截记账 + 断言） | 1 文件 | t3 |
| **修改** | 根 `conftest.py`：会话级安装 / fixture / sessionfinish 汇总 / 环境开关 | ~30 行 | t3 |
| **新增** | `tests/test_notify_guard.py`（classify 单测 + egress 回归） | 1 文件 | t4 |
| **无改动** | 生产代码零改动（`application/notification/**`、`infrastructure/notification/**`、`daily_jobs/**`） | 0 | — |
| **无改动** | 数据库：无 DDL、无迁移、无新表 | 0 | — |

## 需求条款覆盖对照表

| 需求条款 | 条款内容 | 接收任务 |
|---|---|---|
| FR-1 | 打桩点对齐实现命名空间 | t1 |
| FR-2 | e2e 手动触发用例不再执行真实 handler | t2 |
| FR-3 | 测试期外发守卫 | t3（report 接线）· t4（fail 模式收敛） |
| FR-4 | 回归锁 | t4 |

**无"本轮不做"条款**：FR-1…FR-4 全部有接收任务。

## 迁移与兼容（为什么没有单独的迁移卡）

本需求**没有数据迁移、没有生产调用方变更**：改的全在测试层，生产二进制与配置一字不动。
唯一的"灰度"是守卫自身的启用顺序，它被拆进两张卡、而不是单列一张迁移卡：

1. **兼容态（t3）**：默认 `QUANTSYS_NOTIFY_GUARD=report`——只拦截+记账、不判失败。
   既有用例（含自己打桩 `requests.post` 的 `tests/infrastructure/test_agent_channel_agent_os.py`、
   自己打桩门面的 `tests/services/test_feishu_service_facade_delegation.py`）行为不变。
2. **收敛态（t4）**：切到 `fail`（未声明的外发 → teardown 判失败）。
3. **回滚路径**：`QUANTSYS_NOTIFY_GUARD=off` 一条环境变量即回到改造前行为（t3/t4 各自验收里都跑一次）。
   无数据需要回滚，因此不设独立迁移卡——这是**有意的裁剪**，不是遗漏。

## 任务表

| key | title | phase | side | depends_on | implementation | acceptance |
|---|---|---|---|---|---|---|
| t1 | 修正 test_false_success_guard 的打桩点 | implement | backend | — | 把两处 `monkeypatch.setattr(host_alerting, '_send_feishu', …)` 改为打在 `daily_jobs.runtime`（文件内已导入 host_runtime）；保留 `_mark_running/_mark_done` 桩与全部断言；把 146-150 行注释改成正确的打桩点规则 | ① `pytest tests/test_false_success_guard.py -q` → 17 passed；② 机制自证：把 `runtime._send_feishu` 换成记录器后跑 `_run_job`，记录器被调用且文本含「每日任务完成」（证明 `_run_job` 读的就是该模块的全局名）；③ 反例确认：桩改回 `alerting` 时真实 facade 调用数 > 0 |
| t2 | e2e 手动触发用例不再执行真实 handler | implement | backend | — | `tests/e2e/test_daily_orchestrator.py::test_trigger_known_job_returns_success`：先打桩 `daily_jobs.runtime._run_job`（记录调用），再调 `trigger_job(JOBS[0].job_id, force=True)`；断言返回 success 且记录器收到该 job_id | ① `pytest tests/e2e/test_daily_orchestrator.py -q` → 15 passed；② `pytest tests/e2e/test_daily_orchestrator.py -k trigger_known -s 2>&1 | grep -c inprocess_job_start` → 0（无真实任务启动） |
| t3 | 新增测试期通知外发守卫（report 模式接线） | implement | backend | — | 新增 `tests/notify_guard.py`（`classify` / `install_notify_guard` / `attempts` / `real_egress_count` / `assert_no_real_egress`）；`conftest.py` 会话级安装 + `notify_guard` fixture + `pytest_sessionfinish` 汇总 + `QUANTSYS_NOTIFY_GUARD` 开关；默认 report（只拦截记账） | ① `pytest tests/test_notify_guard.py -q` 全过（classify 四类：agent / feishu / wake / None）；② `pytest tests/test_false_success_guard.py -q` 仍全过且汇总打出 `egress=0`；③ `QUANTSYS_NOTIFY_GUARD=off` 时守卫未安装（断言通过） |
| t4 | 回归锁 + 切换 fail 模式并验证回滚 | test | backend | t1, t2, t3 | 新增 `tests/test_notify_guard.py` 的回归段（`egress == 0`、两个已知文件的 `intercepted` 计数）；把默认模式切到 fail；做一次反向验证并留证 | ① `pytest tests/test_false_success_guard.py tests/e2e/test_daily_orchestrator.py tests/test_freshness_guard.py -q` → 全过，汇总 `egress=0 offenders=[]`；② 反向验证记录 ≥1 条（卡文档粘贴：失败的用例名 + 打出的目标 URL）；③ `QUANTSYS_NOTIFY_GUARD=off` 重跑仍全过 |

## 本轮不做

- **不做全仓测试副作用普查**：只覆盖已实证的两处 + 一层通用守卫（其余靠守卫自己抓）。
- **不动生产通知链**：facade / 渠道 / `_send_feishu` 的实现与调用点保持原样。
- **不回退 `daily_jobs/` 包结构**（不为了好打桩把模块合回去）。
- **不引入"测试模式"开关到通知域**（一旦需要，按 L3 升级触发停手并升重档）。
