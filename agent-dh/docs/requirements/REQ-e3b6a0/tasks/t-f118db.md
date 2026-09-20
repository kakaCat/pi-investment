# t-f118db 实测 V1 契约：surface replace 是否唤醒 driver

> 任务卡骨架（reqboard_decompose 自动生成）；汇报经 reqboard_task_report 追加到本文件

## 在做什么
实测 V1 契约：surface replace 是否唤醒 driver

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 范围
- 阶段：analysis
- 端侧：backend

## 得到什么结果
在一次性 agent（不得用本会话）上执行一次 replace，记录结果并写入 design/interfaces.md §8；结论必须是"H4 用 followup"或"H4 只发摘要"二者之一

## 实施方案（implementation）
读 dsh-agent-loop/lib/index.js 的 send/inbox；在隔离环境建一次性 agent 跑 replace；只写文档不改产品代码

## 上游产出摘要（dependsSummary）
- （无依赖）

## 执行方式提示（executorHint）
优先新窗口或 subagent 执行；按本卡自足执行，不读会话历史
## 汇报 1（2026-09-20T03:42:49.249Z，窗口 session-878da638-a076-4266-ae40-70a2390060f2）

V1 契约实测完成，结论为「replace 不唤醒 driver」→ H4 必须显式 followup。用真实 dsh-session 写了运行时探针（不碰本会话、不碰产品代码），跑出 replace 后 surface 收敛为 [系统段, 节点输入包]、历史不可见，且 Session 公开 API 零唤醒原语；源码侧 followup→send(...,true) 与 isReplacementSurfaceEvent 仅清 retained 句柄两条旁证一致。

### 完成项

- 写了运行时探针 scripts/spike/replace-wake-probe.mjs（user/message 形状逐字对齐 NodeIsolationAdapter.replace）
- 实测输出：Session 公开方法 12 个、唤醒类 API = []；replace 前 surface [0,1,2] → 后 [0,3]；模型可见 = system:系统段 | user:节点输入包；历史不可见
- 源码旁证：followup(i)→send(i,"next-turn",true)；isReplacementSurfaceEvent 在 agent-loop 里只把 this.retained 置 null，不投递不唤醒
- 结论写入 design/interfaces.md §8.1，并同步对设计的影响（Phase B 顺序先 H2 后 H4、H4 用简短摘要、H2 降级时才带提示词全文）

### 改动文件

- `scripts/spike/replace-wake-probe.mjs`
- `docs/requirements/REQ-e3b6a0/design/interfaces.md`

### 下一步

t1 收尾（integrating → testing → in_review → done）后开工 t2（建闸门领域 domain/gate：GateSpec + GateCatalog，收敛四处重复定义）

---
