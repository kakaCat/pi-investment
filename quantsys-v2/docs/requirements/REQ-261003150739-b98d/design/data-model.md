---
req_id: REQ-261003150739-b98d
title: 守卫记账结构（无持久化）
doc: design/data-model
serves: FR-3, FR-4
---

# 数据模型设计（REQ-261003150739-b98d）

**先说结论**：本需求**没有新增/修改任何数据结构**——无 DDL、无迁移、无新表、无落盘文件。
下面的"数据模型"只有一样东西：守卫在**进程内存**里的记账结构。

## 记账结构（serves: FR-3）

单条记录 `NotifyAttempt`（`tests/notify_guard.py` 内的 dataclass）：

- `ts: float` —— 命中时刻（`time.time()`）
- `method: str` —— `'post' | 'get'`
- `url: str` —— 被调用的完整 URL（断言失败时原样打出来）
- `sink: str` —— 分类结果：`'agent' | 'feishu' | 'wake'`（由 `classify()` 决定）
- `test_nodeid: str | None` —— 归属用例（由当前 pytest 用例上下文取；会话级调用为 `None`）
- `blocked: bool` —— 是否被拦截（正常路径恒为 `True`）

## 不改表、不落库（serves: FR-3, FR-4）

- 不新增 `quant.*` 表、不改任何 ORM 模型、不写迁移脚本；
- 不产出报表文件（守卫只在 pytest 输出里打印一行汇总）；
- 会话结束即随进程丢弃——**没有需要清理的残留**，也就没有回滚数据的负担。

## 判定数据（serves: FR-4）

回归与门禁只读三个派生量：

- `intercepted` —— `len(attempts())`：被拦下的通知请求数（>0 说明确实有人走到了发送这一步）；
- `egress` —— `real_egress_count()`：**真正出网的**通知请求数（恒 0；这是"零噪声"的硬保证）；
- `offenders` —— 发生未声明外发的用例 nodeid 列表（为空 = 全部用例都规规矩矩打了桩）。

三者都从 `attempts()` 现算，不额外存状态（**只有一份真相**，避免"两处都写必然漂移"）。
