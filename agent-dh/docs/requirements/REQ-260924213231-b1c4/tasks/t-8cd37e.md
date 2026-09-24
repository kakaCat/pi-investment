# t-8cd37e 定义新契约类型与端口·研发

> 需求：REQ-260924213231-b1c4 修 REQ 流水线设计阶段死锁（产物登记入口 + 闸门语义 + 弹框超时）

## 在做什么
定义新契约类型与端口·研发

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 得到什么结果
改动已落盘，相关测试或命令跑通并附输出摘要

---
## 汇报 1（2026-09-24T14:40:06.552Z，窗口 session-a4d082b8-bb32-4506-80a5-876ddd6051ff）

研发子卡对应的工作已在本窗口完成：三类契约类型 + 一个端口落到共享协议层，配套形状测试通过并已合并 main。

### 完成项

- protocol.ts 增 InterruptionRecord / DesignDocRegistration / PendingConfirmation(+Outcome) / PENDING_CONFIRM_TICKET_PREFIX，RequirementRecord.interruption?
- ports.ts 增 PendingConfirmPort + UseCaseDeps.pendingConfirms?
- tests/contract-shapes.test.ts 8 例全绿；tsc 23 条=基线、新文件 0 报错

### 改动文件

- `packages/web/dsh-pmboard/src/shared/protocol.ts`
- `packages/web/dsh-pmboard/src/application/ports.ts`
- `packages/web/dsh-pmboard/tests/contract-shapes.test.ts`

### 下一步

联调/复核/测试子卡由自动链执行；引擎 start_failed 时按人工核对收口。

---
