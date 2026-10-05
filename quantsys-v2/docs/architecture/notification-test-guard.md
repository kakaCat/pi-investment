---
title: 测试期通知外发守卫
type: architecture
tags: [testing, notification, guard]
updated: 2026-10-03
---

# 测试期通知外发守卫（QuantSys V2）

**来源**：[REQ-261003150739-b98d](../requirements/REQ-261003150739-b98d/requirement.md)（2026-10-03）

## 一句话

pytest 进程**不得**向真实通知渠道（Agent OS 网关 / 飞书 webhook）投递消息；
漏桩必须是一条**红的用例**，而不是一封发给用户的假任务卡片。

## 事故形态（为什么会存在这条规则）

2026-10-02 的包拆分（`daily_jobs_bootstrap.py` → `daily_jobs/`）把 `_send_feishu` 的
**取值导入**留在了 `runtime.py`（`from ...alerting import _send_feishu`），而测试的桩
跟着注释搬到了 `alerting` 模块——**改的名字与用的名字不是同一个**，桩静默失效，
测试进程经 `NotificationFacade` 真发通知。实测：跑 `tests/test_false_success_guard.py`
一个文件就向真实渠道发出 4 张 `fake_job` 假卡片（用户拿着卡片来问"这个总触发是什么原因"），
e2e 手动触发用例再发 2 张，并在测试库里真跑了生产 handler。

## 两条规则

### 1. 打桩点：桩打在**被调函数所在模块**

- ✅ `monkeypatch.setattr(runtime, '_send_feishu', …)`（`runtime._run_job` 读的就是它）
- ❌ `monkeypatch.setattr(alerting, '_send_feishu', …)`（符号来源模块）
- ❌ `monkeypatch.setattr(daily_jobs_bootstrap, '_send_feishu', …)`（转发壳）

后两者**名字存在、打桩不报错，但不生效**——这是最危险的一类失效。

### 2. 守卫：传输层按 URL 分类，命中即拦截

`tests/notify_guard.py` + 根 `conftest.py`：给全局 `requests.post/get` 套一层包装器。

- 命中通知接收端 → **拦截 + 记账**（返回合成成功响应，不发起真实请求）；
- 未命中 → 原样放行（对数据源/HTTP 客户端测试完全透明）。

判据：**路径特征**（`/api/v1/notifications/send`、`/open-apis/bot/`、**整段** `/wake`）
+ 配置里的 **authority（主机 + 端口）**。

| 开关 `QUANTSYS_NOTIFY_GUARD` | 行为 |
|---|---|
| 未设（默认） | `fail`：未声明的真实外发 → **该用例失败** |
| `report` | 只拦截 + 记账，不判失败 |
| `off` | 完全不安装（回滚） |

会话末打印一行：`notify-guard intercepted=N egress=0 offenders=[...]`。
`egress` 结构性恒为 0（拦截先于出网）。

## 判据为什么必须精确（实测教训）

首轮全量清点（`report` 模式）时，判据只比**主机名**——而 `AGENT_API_URL=http://127.0.0.1:8080`
让**任何** `127.0.0.1` 请求都被判成通知外发（连 `127.0.0.1:9/api/embeddings` 都中），
整套测试误伤 **58 个用例**。改为 authority（主机+端口）后 offenders 58 → 3 → 0。

**结论：改判据必须先以 `report` 全量清点，再切 `fail`。**

## 已知限制

只覆盖模块级 `requests.post/get`；`requests.Session(...).post` 与其它 HTTP 客户端不经包装器
（当前通知链路不使用 Session）。

## 相关

- 守卫实现：`tests/notify_guard.py`
- 守卫单测：`tests/test_notify_guard.py`
- 需求与验收材料：`docs/requirements/REQ-261003150739-b98d/`
