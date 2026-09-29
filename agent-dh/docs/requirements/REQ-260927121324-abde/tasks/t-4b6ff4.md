# t-4b6ff4 迁移与兼容验证（无 schema 变更 / 旧台账可载入 / 回滚路径）

> 任务卡骨架（reqboard_decompose 自动生成）；汇报经 reqboard_task_report 追加到本文件

## 在做什么
迁移与兼容验证（无 schema 变更 / 旧台账可载入 / 回滚路径）

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 范围
- 阶段：test
- 端侧：backend

## 得到什么结果
cd packages/web/dsh-pmboard && npx vitest run tests/ledger-v6-token.test.ts tests/migration.test.ts 通过；grep -n "export const REQBOARD_SCHEMA_VERSION" src/shared/protocol.ts 返回 = 8。

## 实施方案（implementation）
确认 REQBOARD_SCHEMA_VERSION 仍为 8、不新增 v9/迁移脚本、不回填历史；验证 v5~v8 旧台账照常载入且缺 token 字段即无快照；确认回滚 = 还原 host 代码 + agent-dh/scripts/restart-with-build.sh，已写快照字段是既有可选项无需清洗；复用/补齐 tests/migration.test.ts 与 tests/ledger-v6-token.test.ts 的 v5 容错断言。

## 上游产出摘要（dependsSummary）
- 新增执行快照收敛助手（任务执行唯一写入口）
- 需求迁移写路径统一经收敛点并带写时快照
- agent 任务执行与中途汇报改经执行助手
- 看板任务流转/建卡改卡带写时快照
- 自动链任务执行与接手推进改经执行助手并带快照
- 读路径把快照缺失与不可得同等计入 degraded

## 执行方式提示（executorHint）
优先新窗口或 subagent 执行；按本卡自足执行，不读会话历史
## 汇报 1（2026-09-27T07:21:28.329Z，窗口 session-4ac706ad-a118-4505-b6ac-ce9355d92f5d）

迁移与兼容验证通过：台账 schema 仍是 8（无 v9、无迁移脚本、不回填历史），v5~v8 旧台账照常载入、缺 token 字段即「无快照」；回滚=还原 host 代码 + restart-with-build.sh，已写快照是既有可选字段无需清洗。

### 完成项

- grep -n "export const REQBOARD_SCHEMA_VERSION" src/shared/protocol.ts → = 8（未新增 v9）
- npx vitest run tests/ledger-v6-token.test.ts tests/migration.test.ts → 2 files / 17 tests 全绿
- v5~v8 旧台账载入容错断言保持绿；缺 token 字段不迁移、不补 0
- 回滚路径确认：源码还原 + agent-dh/scripts/restart-with-build.sh 重新发版即可，无需数据清洗

### 下一步

t-5a68f8 同步说明书与 RTM（文档）

---
