---
req_id: REQ-261003150739-b98d
title: 守卫落点与模块边界（测试期通知外发）
doc: design/architecture
serves: FR-1, FR-2, FR-3
---

# 架构设计（REQ-261003150739-b98d）

**前提**：本需求**不改运行时架构**，只动测试层。生产通知链
（`NotificationFacade` → `domain.notification.NotificationService` → `AgentChannel` / `FeishuChannel`）
与 `daily_jobs/` 的包结构一行不改。

## 目标与判定（serves: FR-1, FR-2, FR-3）

**目标**：pytest 进程内的任何一次运行，都**不能**把消息投到真实接收端（Agent OS 通知网关 / 飞书 webhook）。

可证伪判定：

1. `pytest tests/test_false_success_guard.py tests/e2e/test_daily_orchestrator.py -q` 全过；
2. 同一条命令下，守卫记账的 **egress（真正发出去的请求数）= 0**；
3. 人为制造漂移（把 FR-1 的桩改回 `alerting._send_feishu`）→ 守卫让**该用例失败**，并打出目标 URL。

## 根因结构（serves: FR-1）

失败模式不是"忘了打桩"，而是**桩打在了另一个命名空间**：

```
daily_jobs/runtime.py:19   from ...alerting import _send_feishu   ← 取值导入：函数对象存进 runtime 的全局名
测试（拆分前）              monkeypatch.setattr(host, '_send_feishu', …)   ← 同模块，查全局名 → 命中
测试（拆分后）              monkeypatch.setattr(alerting, '_send_feishu', …) ← 改了 alerting 的属性 → runtime 看不见
runtime.py:135             _send_feishu("✅ 每日任务完成：…")      ← 真函数 → 真实投递
```

**打桩点规则（本需求的判据）**：桩必须打在**被调函数所在的模块**；
"转发壳"（`daily_jobs_bootstrap`）与"符号来源模块"（`alerting`）都不是它。
拆分/搬运一旦发生，这条规则就是唯一能让人一次打对的东西。

同类前科已在 `tests/test_freshness_guard.py` 文件头自述两次（第三次即本次），故只修桩不够，
需要 FR-3 的兜底把"漏桩"从静默变成响亮。

## 守卫落点：传输层 URL 分类（serves: FR-3）

**候选落点与取舍**：

- ✗ **门面层**（替换 `get_notification_facade`）：会打断仍在断言门面行为的用例
  （`tests/services/test_feishu_service_facade_delegation.py` 自己打桩门面并断言调用），
  且门面只是便利入口，不是唯一的出网口。
- ✗ **渠道模块绑定层**（替换 `agent_channel.requests`）：`tests/infrastructure/test_agent_channel_agent_os.py`
  直接 `monkeypatch.setattr(requests, "post", fake)`（打全局 `requests`），改绑定会让这些用例失效。
- ✓ **传输层包装器**：在 `conftest.py` 给全局 `requests.post` / `requests.get` 套一层**按 URL 分类**的包装器。
  - 命中通知接收端 → **拦截并记账**（返回合成响应，不发起真实请求）；
  - 未命中 → 原样调用真实函数（对数据源、HTTP 客户端等测试**完全透明**）。

**拦截即拦截**：命中时返回合成响应对象（`status_code=200`、`json()` → `{"success": true, "code": 0, "StatusCode": 0}`、
`text=''`），使 `AgentChannel` 的 `status_code==200 & success` 分支与 `FeishuChannel` 的
`code/StatusCode==0` 分支都走"成功"，上层语义不变——**测试不会因为守卫而红，红的是"漏桩"**。

**接收端清单从配置派生**（不写死）：`AGENT_API_URL` 主机、`FEISHU_WEBHOOK_URL` 主机，
外加路径特征 `/api/v1/notifications/send`、`/wake`、`/open-apis/bot/`（前者是渠道、
第三者是飞书 webhook、中间那条是 `AgentNotificationService` 的 wake 通道）。

**已知限制（如实登记，不假装全覆盖）**：只覆盖模块级 `requests.post/get`；
`requests.Session(...).post` 与其它 HTTP 客户端不经此包装器（当前通知链路不使用 Session）。
`wake` 路径另有 `AGENT_NOTIFY_ALLOW_TEST` 生产闸门，本守卫是它的第二道。

## 启用顺序与回滚（serves: FR-3）

1. **记账模式**（只拦截+记录，不判失败）：全量跑一遍，清点"仍有真实外发的用例"；
2. **判失败模式**（默认）：仍发生未声明外发的用例在 teardown 被判失败；
3. **回滚**：`QUANTSYS_NOTIFY_GUARD=off`（单开关）或摘掉 `conftest.py` 的安装行——
   两者都不影响生产代码，回滚成本一条语句。

若实测存在**必须**真实外发才能验证的用例（预期为 0 个），用显式 marker
`@pytest.mark.notify_egress_expected` 标注并写明理由，禁止静默放行。

## 不改什么（serves: FR-1, FR-2, FR-3）

- `application/notification/**`、`infrastructure/notification/**`、`daily_jobs/alerting.py` 一律不改（投递语义不动）。
- `daily_jobs/` 包结构不回退（不为了"好打桩"把模块合回去）。
- 既有两个测试文件的**断言**（marks 的 status / error 文本、`trigger_job` 返回契约）不改。
