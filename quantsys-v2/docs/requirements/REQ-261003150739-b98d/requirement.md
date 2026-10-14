# REQ-261003150739-b98d: 修复 pytest 向真实通知渠道发消息（打桩点漂移）

**需求ID**: REQ-261003150739-b98d
**类型**: feature（缺陷修复性质）
**作用域**: `quantsys-v2/`（测试层为主：`tests/`、根 `conftest.py`）
**档位**: 轻档（L3 依据见文末；出现"要动通知架构/生产投递语义"信号即单向升级重档）

## TL;DR

**跑测试会真的发通知。** 用户看到的「✅ 每日任务完成：fake_job / 测试任务 / 耗时 0.0 分钟 /
symbols_updated=10」不是生产任务，而是 **`tests/test_false_success_guard.py` 的桩没打上**，
测试进程经 `NotificationFacade` 真实投递出去的假卡片。

根因一句话：`runtime.py` 用 **取值导入** 拿到了 `_send_feishu`，
而测试把桩打在 **`alerting` 模块属性** 上——改的与用的不是同一个名字。

```
runtime.py:19   from ...alerting import _send_feishu      ← 导入时把函数对象绑进 runtime 的全局名
tests/...:156   monkeypatch.setattr(host_alerting, '_send_feishu', ...)   ← 改的是 alerting 的属性
runtime.py:135  _send_feishu("✅ 每日任务完成：...")        ← 查 runtime 自己的全局名 = 真函数
                └─▶ 真实投递（agent 优先 / 飞书降级）
```

**实测证据（本机可复现）**：把 `NotificationFacade` 换成计数器后跑测试，数真实投递：

| 跑的用例 | 真实投递数 | 内容 |
|---|---|---|
| `tests/test_false_success_guard.py`（整文件） | **4** | 开始/失败/开始/完成，均 `fake_job` |
| `tests/e2e/test_daily_orchestrator.py::TestManualTrigger::test_trigger_known_job_returns_success` | **2** | 开始/完成，`watch_rule_health`（**真跑了真 handler**） |

**漂移史**：2026-10-02 提交 `c4fc27a4` 把 1147 行的 `daily_jobs_bootstrap.py` 拆成 `daily_jobs/` 包。
拆分前桩打在同模块（`host._send_feishu`），**同模块查全局名，有效**；拆分后桩跟着注释搬到了
`alerting`，方向就错了——`_mark_running/_mark_done` 搬对了（打到 `runtime`），`_send_feishu` 没搬对。
同类事故本仓已有前科：`tests/test_freshness_guard.py` 文件头自述"打桩点搬家"是**第三次**。

## 边界

### 做什么

1. **修正打桩点**：让 `test_false_success_guard.py` 的两处桩落到 `_run_job` 真正读取的命名空间。
2. **e2e 不再拉真 handler**：`test_trigger_known_job_returns_success` 不得真跑生产 job（`watch_rule_health`）。
3. **加测试期外发守卫**：会话级拦截，使"测试真的把消息发出去"这件事要么被拦住、要么**响亮失败**，
   不再依赖每个用例自己记得打桩。
4. **回归锁**：一条可跑的判定，证明上述两个文件跑完真实投递数为 0。

### 不做什么

- **不改生产投递语义**：`NotificationFacade` 的 "agent 优先 / 飞书降级" 策略、`_send_feishu` 的实现与调用点保持不动。
- **不做全仓测试副作用普查**：只覆盖已实证的两处 + 一层通用守卫；其余用例的漏桩留待守卫自己抓。
- **不动 `daily_jobs/` 的模块拆分结构**：不为了"好打桩"回退包结构。

### 边界理由

- 用户可感知的成本是**噪声与误判**（假卡片冒充生产结果、提示 0.0 分钟与虚构计数），
  修法小且局部；顺手动生产通知链路会把"修测试"放大成"改通知架构"，风险与收益完全不成比例。
- 一处漏桩能静默存在是因为**没有兜底**：只修这一处，下一个拆分（本仓已发生三次）还会再犯。
  故"修正 + 守卫"必须同批做，才算真关掉这一类事故。

## 产品定义

### 一句话

让 `pytest` 的任何一次运行都**不可能**向真实渠道（agent 通道 / 飞书）投递消息；
一旦有人漏桩，守卫当场报错，而不是让用户收到假任务卡片。

### 为什么现在做

1. **已经在发生且被用户看到**：本次即由用户拿着假卡片来问"这个总触发是什么原因"。
2. **假卡片在语义上是有害的**：它冒充"每日任务成功"，与本仓反复审计的"假成功"是同一类
   信任风险——看的人会以为任务真跑过。
3. **e2e 那条不只是通知噪声**：它在测试库里真跑了生产 handler，属"测试期真实副作用"。
4. **同类事故有复发史**：拆分搬家导致的打桩点漂移在本仓已至少三次（`test_freshness_guard.py` 自述），
   缺的正是"漏桩会响亮失败"这道兜底。

### 现状实测（2026-10-03 采集）

| 维度 | 实测值 | 证据 |
|---|---|---|
| 单文件真实投递 | 4 张 | `pytest tests/test_false_success_guard.py -s` + facade 计数插件 |
| e2e 真实投递 | 2 张 | `pytest tests/e2e/test_daily_orchestrator.py -k trigger_known -s` + 同插件 |
| 桩点错位 | 是 | `runtime.py:19` 取值导入 vs `tests/test_false_success_guard.py:156,176` 打在 alerting |
| 环境闸门 | 无 | `.env.test` 无通知开关；`conftest.py` 无任何外发拦截 |
| 漂移引入点 | `c4fc27a4`（2026-10-02） | `git log -S'host_alerting' -- tests/test_false_success_guard.py` |

## 用户与角色

- **项目所有者（人类）**：不应再被假任务卡片打扰；判定标准是"跑测试 → 渠道里没有新卡片"。
- **窗口 AI Agent（本需求的实施者）**：按 FR 逐条改，改动集中在测试层 + `conftest.py`。
- **后续维护者 / 新会话**：需要一条"打桩点怎么找"的可靠规则（桩要打在**实现所在模块**，
  而不是转发壳或符号来源模块），并把这条规则沉淀进测试或文档。

## 功能点

**FR-1: 打桩点对齐实现命名空间**
修正 `tests/test_false_success_guard.py` 的两处 `_send_feishu` 桩，
使其作用于 `_run_job` 实际读取的模块命名空间（`daily_jobs.runtime`）；
保留原断言（`marks` 的 status 与 error 文本）不变。

**FR-2: e2e 手动触发用例不再执行真实 handler**
`tests/e2e/test_daily_orchestrator.py::TestManualTrigger::test_trigger_known_job_returns_success`
必须在不真正执行生产 job handler 的前提下验证 `trigger_job` 的返回契约
（打桩 `_run_job` 或 job handler，而不是放任后台线程跑真逻辑）。

**FR-3: 测试期外发守卫**
在测试层加入会话级守卫：pytest 进程内的真实外发（`NotificationFacade.send_card` / `send_text`）
被拦截并记录；**允许**用例在显式打桩下断言"我调用了通知"（如 `test_freshness_guard.py` 的
`sent` 列表），但**不得**触达真实通道。守卫须能区分"被拦截的调用"与"通道被真的使用"。

**FR-4: 回归锁**
新增回归测试：跑 FR-1/FR-2 涉及的两个文件时，真实投递计数为 0；
且当有人再次把桩打错命名空间时，守卫以**失败**（而非静默）呈现。

## 验收标准（跑什么、看到什么算过）

1. 判定命令：`pytest tests/test_false_success_guard.py tests/e2e/test_daily_orchestrator.py -q`
   → 全过，且真实投递计数 **0**（计数器由守卫自身提供，见 FR-3）。
2. `pytest tests/test_freshness_guard.py -q` → 全过（该用例仍能断言告警文本，证明守卫没有把
   "正常的通知断言"一并打死）。
3. 反向验证：临时把 FR-1 的桩改回 `alerting` → 守卫**报错**（证明它真能抓住漂移，而非空转）。
4. 生产不受影响：`git diff` 里不含 `application/notification/**` 与 `daily_jobs/alerting.py`
   的投递语义改动。

## 相关

- 事故现场：`tests/test_false_success_guard.py`、`adapters/inbound/fastapi_app/daily_jobs/runtime.py:19`
- 引入提交：`c4fc27a4`（REQ-261001145152-3982 t-686185 文件拆分）
- 同类前科：`tests/test_freshness_guard.py`（文件头自述第三次打桩点漂移）

## 轻档依据（L3）与升级触发

- **为什么可以走轻档**：改动集中在测试层（打桩点 + `conftest.py` 守卫 + 一条回归），
  不新增子系统、不改数据模型、不动生产架构；决策点唯一（守卫拦到什么粒度由本需求的 FR-3 定死）。
- **单向升级触发**：一旦实施中发现必须修改 `NotificationFacade` 的生产投递语义
  （例如需要新增"测试模式"开关到通知域本身），或需要新增配置项/子系统，**立即停手升级重档**。

<!-- reqboard:marks:begin 机器维护，请勿手改 -->

#### 条款接收状态（随卡的生命周期自动更新）

| 编号 | 接收状态 | 承载任务 |
|------|---------|---------|
| FR-1 | ✅ 已接收 | t1 |
| FR-2 | ✅ 已接收 | t2 |
| FR-3 | 🔴 **未被接收** | — |
| FR-4 | ✅ 已接收 | t4 |

> 🔴 **未被接收（1 条）**：FR-3

<!-- reqboard:marks:end -->
