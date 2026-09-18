# t-60bbe1 返工：需求级：交付结论可复核（证据齐全、与技术设计一致、无范围蔓延）

> 需求：REQ-a33899 项目看板：记录并展示每个流程节点（阶段过程）的 Token 消耗
> 验收标准：需求级：交付结论可复核（证据齐全、与技术设计一致、无范围蔓延）

---
## 汇报 1（2026-09-18T05:39:05.628Z，窗口 session-b11b0a40-5c65-4c8d-88c7-23988b4979b0）

需求级返工复核：交付结论可复核——发版已生效（launchd job gui/501/com.pi-investment.dsh，新接口 200）；证据链完整（10 个测试文件、typecheck、build:client、迁移白名单外 0、线上真实数据）；无范围蔓延（只动 dsh-pmboard 与本需求文档）。

### 完成项

- 线上 /requirements/REQ-a33899/token 返回真实 process 快照与提示词成本
- 返工任务 9 项全部按「发版 + 线上取数」证据关闭
- 验证链：tests/*token* 全绿、typecheck 通过、build:client verify OK

### 改动文件

- `/Users/yunpeng/pi-investment/agent-dh/packages/pages/dsh-pmboard/src/application/query/QueryRequirementToken.ts`
- `/Users/yunpeng/pi-investment/agent-dh/packages/pages/dsh-pmboard/src/client/token-info.ts`

### 下一步

重新提交验收 v2（只含未过项）

---
