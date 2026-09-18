# t-f2c54b 到期巡检任务

> 任务卡骨架（reqboard_decompose 自动生成）；汇报经 reqboard_task_report 追加到本文件

## 目标
到期巡检任务

## 背景摘要（context）
（待补充）

## 范围
- 阶段：implement
- 端侧：backend

## 验收标准
运行 python -m pytest tests/application/test_sla_job.py 通过；造超时待办后 1 分钟内断言 flow_state 晋升；断言已在 L3 超时则写 timeout 回执存在

## 实施方案（implementation）
WatchSlaJob 每分钟扫描 list_overdue；晋升/回执/升级给用户；注册高频调度；补停摆注入测试

## 上游产出摘要（dependsSummary）
- TodoService 与仓储端口

## 执行方式提示（executorHint）
优先新窗口或 subagent 执行；按本卡自足执行，不读会话历史
## 汇报 1（2026-09-17T17:49:01.814Z，窗口 session-9b2b54f3-a3f4-4087-84f4-d1038fd1dd98）

到期巡检（不得滞留的机械保证）：WatchSlaJob 机械推进 L1→L2→L3、L3 超时写 timeout 回执；ReceiptService 三段回执幂等；回执仓储带写库前校验。主 agent 复核：文件范围精确、24 用例通过。

### 完成项

- domain/watch/ports.py：新增 RECEIPT_KINDS 与 IWatchReceiptRepository（record/list_by_todo/exists），文档写明幂等键 (todo_id, kind, payload_digest) 与 digest 必填、失败必须上抛
- adapters/outbound/repositories/watch_receipt_repository.py（新增）：触碰 session 之前先校验 kind∈RECEIPT_KINDS、digest 非空且 ≤64；exists 失败上抛绝不静默 False（静默 False 会导致重复发回执）
- application/services/watch_engine/receipt_service.py（新增）：三段回执 escalate/result/timeout；幂等（exists→发送→record）；sender 可注入、缺省 log-only 且 delivery_status=log_only —— **绝不写 sent**（不许假装已发）；sender 抛错记 failed 不打断，仓储异常上抛
- adapters/inbound/fastapi_app/watch_sla_job.py（新增）：run_once 机械编排——L1→L2、L2→L3（写 escalate 回执）、L3 超时写 timeout 回执并 escalate_count+1；单条异常继续、扫描抛错返回 degraded 不崩；不自建调度器、不直发飞书
- tests/application/test_sla_job.py（新增 24 例）：含三连轮机械推进、同 due 周期幂等、单条异常继续、扫描失败降级、回执仓储抛错不崩、log-only 不冒充 sent、未知流转态跳过、签名防漂移
- 子代理变异测试两处：破坏幂等（exists 短路）→ 4 红；破坏 L1 晋升分支 → 5 红；改回均 24 绿 → 用例有牙
- 主 agent 复核：文件范围精确（5 文件，仅 ports.py 为既有文件）；pytest tests/application/test_sla_job.py → 24 passed；排除两个已知漂移文件后全量 watch → 311 passed
- 诚实设计取舍（已复核认可）：delivery_status 增设第三态 log_only（该列无 DB CHECK）；L3 超时用 promote(todo_id,"L3",escalate_count+1) 复用端口而非新增 bump 方法；幂等当前是 check-then-act，多实例需补唯一约束（超本卡范围，已列入 t12 待办）

### 改动文件

- `quantsys-v2/domain/watch/ports.py`
- `quantsys-v2/adapters/outbound/repositories/watch_receipt_repository.py`
- `quantsys-v2/application/services/watch_engine/receipt_service.py`
- `quantsys-v2/adapters/inbound/fastapi_app/watch_sla_job.py`
- `quantsys-v2/tests/application/test_sla_job.py`

### 下一步

t12：把 WatchSlaJob 注册成定时任务（进程外，1 分钟）；补 (todo_id,kind,payload_digest) 唯一索引以满足多实例幂等；close 响应补 receipt（receipt_to_dict 已就绪）

---
