# t-da7cf8 pm 卡面新增 blockedReason/closePolicy 字段·研发

> 需求：REQ-261019224003-0041 改用dsh-workprocess的内容

## 在做什么
pm 卡面新增 blockedReason/closePolicy 字段·研发

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 得到什么结果
改动已落盘，相关测试或命令跑通并附输出摘要

---
## 汇报 1（2026-10-19T17:38:57.337Z，窗口 session-66f19830-f3c9-42a7-a3cc-3791a19cd16f）

t4 研发段完成（Worker 产出，本窗口复核）：任务卡新增 blockedReason/closePolicy，口径=缺失即默认、写期非法抛 REQBOARD_INVALID_INPUT、读侧不抛；13 个单测全过。代码在 dsh-pmboard 仓（pm-core/src/domain/task/CardFields.ts 等 9 文件）。

### 完成项

- CardFields.ts 单一事实源（缺省/枚举/断言）
- protocol-domain/validateQueue/QueueRepository/http/卡面类型与显示七处接线
- 13/13 单测过（task-card-fields.test.ts）
- 我人工复核：缺失即默认/写期抛错/读侧不炸三口径与设计文档一致

### 改动文件

- `docs/requirements/REQ-261019224003-0041/tasks/t-da7cf8.md`

### 下一步

联调子卡 t-f0116e

---
